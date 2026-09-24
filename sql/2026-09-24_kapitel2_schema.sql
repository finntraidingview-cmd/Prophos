-- 2026-09-24: Kapitel „Ohne Hedge" — Vollumstieg auf DB-Seite.
-- Finn (24.09.2026): „Das ist ein riesen Umstieg — geh alles durch, DB, jedes Einzelne."
-- Stand davor: Tabelle kapitel (1 Hedge-Ära, 2 Ohne Hedge), kapitel_id auf accounts /
-- trade_plans / transactions mit Trigger set_kapitel() (V2-Wege → Kapitel ohne Hedge),
-- trade_plans.ohne_hedge generiert. Hier kommen die Lücken dazu, die beim Durchgehen auffielen:
--
--   1) pending_payouts hatte kein Kapitel — offene Payouts liefen im Kapitel-Filter der
--      Finanzen nur über das Datum. Jetzt Spalte + Trigger (nach requested_at) + Backfill.
--   2) trade_plans.pl_quelle — woher der eingetragene P&L stammt (Echo-Snapshot, TradingView
--      Today's P&L, Duplikum, Hand). Ohne Hedge zählt nur noch der Master; die Herkunft ist
--      der Beweis, ob eine Zahl gemessen oder getippt wurde.
--   3) trade_plans.master_symbol_root — Buchstabenwurzel des Master-Symbols (NQZ6 → NQ,
--      MNQZ6 → MNQ, CME_MINI:MNQ1! → MNQ), damit Auswertungen NQ und MNQ trennen können.
--   4) v_kapitel_trades / v_kapitel_summen — zwei Views mit security_invoker, damit die
--      RLS des Aufrufers gilt: jeder sieht nur seine Pläne/Konten/Buchungen.
--   5) search_path der Kapitel-Funktionen fest auf '' (Supabase-Advisor
--      function_search_path_mutable) — Bodies sind vollqualifiziert, also risikolos.
--
-- Keine Regel- oder Compliance-Prüfung, nichts wird gelöscht. Idempotent.

-- 1) pending_payouts.kapitel_id ----------------------------------------------------------
alter table public.pending_payouts
  add column if not exists kapitel_id smallint references public.kapitel(id);

create index if not exists pending_payouts_user_kapitel_idx
  on public.pending_payouts (user_id, kapitel_id);

-- 2) trade_plans.pl_quelle ---------------------------------------------------------------
-- 'echo'     = Echo-Snapshot, Balance-Delta des Masters (Echo / Echo V2, _autoPnlFetchMt5)
-- 'tv'       = TradingView Today's P&L über den Rundgang (Orbit V2, _autoPnlFetchTvV2)
-- 'duplikum' = Duplikum-Push (Hedge-Ära, Orbit/Duplikum)
-- 'hand'     = von Hand ins Abschließen-Popup getippt
-- Backfill bewusst NICHT: für den Altbestand ist die Herkunft nicht mehr rekonstruierbar
-- (Echo-Auto-Wert und Handeingabe landeten im selben Feld). null = unbekannt. Das Frontend
-- setzt die Quelle ab jetzt beim Abschließen; bis dahin bleibt sie auch bei neuen Plänen leer.
alter table public.trade_plans add column if not exists pl_quelle text;

alter table public.trade_plans drop constraint if exists trade_plans_pl_quelle_check;
alter table public.trade_plans
  add constraint trade_plans_pl_quelle_check
  check (pl_quelle is null or pl_quelle in ('echo', 'tv', 'duplikum', 'hand'));

-- 3) trade_plans.master_symbol_root ------------------------------------------------------
-- Generierte Spalte (regexp_replace und substring(text from text) sind IMMUTABLE, in
-- pg_proc geprüft am 24.09.2026). Drei Schritte:
--   a) Börsen-Präfix bis zum ':' weg            CME_MINI:MNQ1! → MNQ1!
--   b) Kontrakt-Suffix Monatscode + Jahr weg    NQZ6 → NQ, MNQZ6 → MNQ, NQH26 → NQ
--      (Monatscodes F G H J K M N Q U V X Z — ohne diesen Schritt bliebe „NQZ" stehen,
--      weil Z ein Buchstabe ist; erster Lauf am 24.09. so passiert)
--   c) führende Buchstaben                       MNQ1! → MNQ, NAS100 → NAS, BTCUSD → BTCUSD
-- Ohne führenden Buchstaben (z. B. '6E') → null statt Leerstring. Leitet sich immer aus
-- master_symbol ab, kann nicht driften.
alter table public.trade_plans drop column if exists master_symbol_root;
alter table public.trade_plans
  add column master_symbol_root text
  generated always as (
    nullif(upper(substring(
      regexp_replace(regexp_replace(master_symbol, '^[^:]*:', ''), '[FGHJKMNQUVXZ][0-9]{1,4}$', '')
      from '^[A-Za-z]+')), '')
  ) stored;

create index if not exists trade_plans_user_symbol_root_idx
  on public.trade_plans (user_id, master_symbol_root);

-- 4) Funktionen mit festem search_path ---------------------------------------------------
-- Advisor-Warnung function_search_path_mutable. Alle Verweise in den Bodies sind bereits
-- vollqualifiziert (public.kapitel, public.kapitel_fuer); now()/current_date/coalesce liegen
-- in pg_catalog, das auch bei leerem search_path immer gefunden wird.
create or replace function public.kapitel_fuer(d date)
returns smallint
language sql
stable
set search_path = ''
as $$
  select coalesce(
    (select id from public.kapitel
      where von <= d and (bis is null or d <= bis)
      order by von desc limit 1),
    (select id from public.kapitel
      where d < (select min(von) from public.kapitel)
      order by von asc limit 1),
    (select id from public.kapitel
      order by (bis is null) desc, von desc limit 1)
  );
$$;

-- set_kapitel: wie bisher (V2-Regel für trade_plans, sonst nach Datum, nur wenn leer) —
-- neu der Zweig pending_payouts (Datum = requested_at, der Tag der Payout-Anfrage).
--
-- BUGFIX 24.09.2026 (beim Durchgehen gefunden): die V2-Regel aus 2026-09-24_kapitel_v2_regel
-- stand als EIN Ausdruck „tg_table_name = 'trade_plans' and coalesce(new.route, '') in (…)".
-- plpgsql löst new.route auch dann auf, wenn der linke Teil schon false ist — auf accounts
-- und transactions gibt es das Feld nicht → „record new has no field route", JEDER Insert in
-- diese beiden Tabellen (neues Konto, Buchung, Payout) schlug seit dem Abend fehl. Deshalb
-- jetzt verschachtelt: new.route wird nur im trade_plans-Zweig angefasst.
create or replace function public.set_kapitel()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_ohne smallint;
begin
  if tg_table_name = 'trade_plans' then
    if coalesce(new.route, '') in ('mt5v2', 'tvv2') then
      select id into v_ohne from public.kapitel where hedge = false order by von desc limit 1;
      if v_ohne is not null then
        new.kapitel_id := v_ohne;
        return new;
      end if;
    end if;
  end if;
  if new.kapitel_id is null then
    if tg_table_name = 'transactions' then
      new.kapitel_id := public.kapitel_fuer(coalesce(new.occurred_at, current_date));
    elsif tg_table_name = 'pending_payouts' then
      new.kapitel_id := public.kapitel_fuer(coalesce(new.requested_at, current_date));
    else
      -- accounts und trade_plans: Anlagedatum
      new.kapitel_id := public.kapitel_fuer(coalesce(new.created_at, now())::date);
    end if;
  end if;
  return new;
end;
$$;

-- set_updated_at: Body ohne Schema-Verweise (new.updated_at = now()) — search_path '' ist
-- hier ebenfalls risikolos; hängt an accounts, mt5_links, kapitel u. a.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists pending_payouts_set_kapitel on public.pending_payouts;
create trigger pending_payouts_set_kapitel
  before insert on public.pending_payouts
  for each row execute function public.set_kapitel();

-- Backfill pending_payouts (nur Zeilen ohne Kapitel)
update public.pending_payouts
   set kapitel_id = public.kapitel_fuer(requested_at)
 where kapitel_id is null;

-- 5) Views ------------------------------------------------------------------------------
-- security_invoker = on: die View läuft mit den Rechten des Aufrufers, die RLS-Policies
-- von trade_plans / accounts / transactions greifen also wie beim direkten Zugriff
-- (auth.uid() = user_id). Service-Role sieht alles. anon bekommt keinen Zugriff.

-- v_kapitel_trades: ein Plan je Zeile mit Kapitelname und Master-Konto. Master über
-- master_account_id (left join — 2.300+ Altpläne ohne Konto-Verweis fallen auf die im Plan
-- gespeicherten master_name / master_firm zurück).
create or replace view public.v_kapitel_trades
with (security_invoker = on)
as
select p.id,
       p.user_id,
       p.kapitel_id,
       k.name                          as kapitel_name,
       p.route,
       p.ohne_hedge,
       coalesce(a.name, p.master_name) as master_name,
       coalesce(a.firm, p.master_firm) as master_firm,
       p.master_symbol_root,
       p.richtung,
       p.master_contracts,
       p.master_pl,
       p.slave_pl,
       p.blown,
       p.status,
       p.created_at,
       p.started_at,
       p.ended_at,
       p.completed_at,
       p.pl_quelle
  from public.trade_plans p
  left join public.kapitel  k on k.id = p.kapitel_id
  left join public.accounts a on a.id = p.master_account_id;

-- v_kapitel_summen: je user_id × kapitel_id. Zählung wie /admin/kapitel (app.py):
--   trades / trades_ohne_hedge / blown / master_pl_sum / slave_pl_sum → nur status = 'completed'
--   kauf_sum   → accounts.purchase_cost nach accounts.kapitel_id, ohne account_type 'live'
--   payouts_sum → transactions kind = 'payout';  live_pnl_sum → kind = 'live_pnl'
-- Unterschied zum Admin-Endpunkt: dort werden ausgeblendete Personen (excluded_ids) und die
-- Hedge-Kosten-Formel (_admin_hedge_ev, FX) zusätzlich gerechnet — das bleibt im Backend.
create or replace view public.v_kapitel_summen
with (security_invoker = on)
as
with
  pl as (
    select user_id, kapitel_id,
           count(*)                                   as trades,
           count(*) filter (where ohne_hedge)         as trades_ohne_hedge,
           count(*) filter (where blown)              as blown,
           coalesce(sum(master_pl), 0)                as master_pl_sum,
           coalesce(sum(slave_pl), 0)                 as slave_pl_sum
      from public.trade_plans
     where status = 'completed'
     group by user_id, kapitel_id
  ),
  ac as (
    select user_id, kapitel_id,
           coalesce(sum(purchase_cost), 0)            as kauf_sum
      from public.accounts
     where coalesce(account_type, '') <> 'live'
     group by user_id, kapitel_id
  ),
  tx as (
    select user_id, kapitel_id,
           coalesce(sum(amount) filter (where kind = 'payout'),   0) as payouts_sum,
           coalesce(sum(amount) filter (where kind = 'live_pnl'), 0) as live_pnl_sum
      from public.transactions
     group by user_id, kapitel_id
  ),
  keys as (
    select user_id, kapitel_id from pl
    union select user_id, kapitel_id from ac
    union select user_id, kapitel_id from tx
  )
select ks.user_id,
       ks.kapitel_id,
       k.name                              as kapitel_name,
       coalesce(pl.trades, 0)              as trades,
       coalesce(pl.trades_ohne_hedge, 0)   as trades_ohne_hedge,
       coalesce(pl.blown, 0)               as blown,
       coalesce(pl.master_pl_sum, 0)       as master_pl_sum,
       coalesce(pl.slave_pl_sum, 0)        as slave_pl_sum,
       coalesce(ac.kauf_sum, 0)            as kauf_sum,
       coalesce(tx.payouts_sum, 0)         as payouts_sum,
       coalesce(tx.live_pnl_sum, 0)        as live_pnl_sum
  from keys ks
  left join public.kapitel k on k.id = ks.kapitel_id
  left join pl on pl.user_id = ks.user_id and pl.kapitel_id is not distinct from ks.kapitel_id
  left join ac on ac.user_id = ks.user_id and ac.kapitel_id is not distinct from ks.kapitel_id
  left join tx on tx.user_id = ks.user_id and tx.kapitel_id is not distinct from ks.kapitel_id;

revoke all on public.v_kapitel_trades, public.v_kapitel_summen from anon;
grant select on public.v_kapitel_trades, public.v_kapitel_summen to authenticated, service_role;

-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
