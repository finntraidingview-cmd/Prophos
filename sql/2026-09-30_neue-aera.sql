-- Kapitel 2 heißt „Neue Ära" statt „Ohne Hedge" + Winning-Days-Hedge zählt nach Datum (30.09.2026, Finn).
-- Anlass: „In dieser Ära gibt es sehr wohl Hedges" — der Winning-Days-Gegenhedge (Fusion, seit 24.09.2026) und
-- später Order-Paare, die sich gegenseitig hedgen. Außerdem zeigte Finanzen im neuen Kapitel bei „WD-Hedge" nur
-- „—": alle 15 Buchungen kind 'wd_hedge' (24.–29.09.2026, Summe +411,54 €, 3 IDs) standen auf Kapitel 1, weil
-- Buchungen das Kapitel ihres KONTOS erben (Regel .448) und das Fusion-Hedge-Konto (488579) aus der Hedge-Ära stammt.
--
-- a) kapitel 2: nur name + beschreibung. key 'ohne_hedge' und hedge = false BLEIBEN — daran hängen
--    set_kapitel (V2-Routen → Kapitel ohne Hedge-Flag), Backend (hedge_aus spart die Hedge-Rechnung) und Views.
-- b) set_kapitel(): wortgleich wie sql/2026-09-27_admin_zugang_buchung_nach_datum.sql, einzige Ergänzung im
--    transactions-Zweig: kind 'wd_hedge' → kapitel_fuer(occurred_at). Ein WD-Hedge ist ein Trade-Ergebnis des
--    Tages, kein Posten des (alten) Fusion-Kontos. Alle anderen Buchungen unverändert (Regel .448 / admin_zugang).
-- c) Backfill der bestehenden wd_hedge-Buchungen nach Datum. Der Trigger feuert nur bei INSERT oder UPDATE OF
--    account_id — das UPDATE hier ändert nur kapitel_id und läuft deshalb nicht durch den Trigger.
-- Idempotent: mehrfach ausführbar, ändert beim zweiten Lauf nichts mehr.

-- a) Umbenennen
update public.kapitel
   set name = 'Neue Ära',
       beschreibung = 'Seit 24.09.2026: Prop-Konten ohne durchgehenden Realmoney-Gegen-Hedge (Echo V2 / Orbit V2); gezielte Hedges wie der Winning-Days-Gegenhedge gehören dazu.'
 where id = 2 and key = 'ohne_hedge'
   and (name is distinct from 'Neue Ära'
        or beschreibung is distinct from 'Seit 24.09.2026: Prop-Konten ohne durchgehenden Realmoney-Gegen-Hedge (Echo V2 / Orbit V2); gezielte Hedges wie der Winning-Days-Gegenhedge gehören dazu.');

-- b) Trigger-Funktion (gemeinsam für accounts, trade_plans, transactions, pending_payouts)
create or replace function public.set_kapitel()
 returns trigger
 language plpgsql
 set search_path to ''
as $function$
declare
  v_ohne smallint;
  v_konto smallint;
begin
  if tg_table_name = 'trade_plans' then
    if coalesce(new.route, '') in ('mt5v2', 'tvv2', 'tsv2') then
      select id into v_ohne from public.kapitel where hedge = false order by von desc limit 1;
      if v_ohne is not null then
        new.kapitel_id := v_ohne;
        return new;
      end if;
    end if;
    if new.kapitel_id is null then
      new.kapitel_id := public.kapitel_fuer(coalesce(new.created_at, now())::date);
    end if;
    return new;
  end if;
  if tg_table_name in ('transactions', 'pending_payouts') then
    -- Winning-Days-Hedge (30.09.2026): zählt zum Kapitel seines DATUMS, nicht zum Kapitel des Fusion-Kontos
    if tg_table_name = 'transactions' and new.kind = 'wd_hedge' then
      new.kapitel_id := public.kapitel_fuer(coalesce(new.occurred_at, current_date));
      return new;
    end if;
    if new.account_id is not null
       and not exists (select 1 from public.admin_zugang z
                        where z.user_id = new.user_id and z.nur_eigene) then
      select a.kapitel_id into v_konto from public.accounts a where a.id = new.account_id;
      if v_konto is not null then
        new.kapitel_id := v_konto;
        return new;
      end if;
    end if;
    if new.kapitel_id is null then
      if tg_table_name = 'transactions' then
        new.kapitel_id := public.kapitel_fuer(coalesce(new.occurred_at, current_date));
      else
        new.kapitel_id := public.kapitel_fuer(coalesce(new.requested_at, current_date));
      end if;
    end if;
    return new;
  end if;
  if new.kapitel_id is null then
    new.kapitel_id := public.kapitel_fuer(coalesce(new.created_at, now())::date);
  end if;
  return new;
end;
$function$;

-- c) Backfill: bestehende WD-Hedge-Buchungen nach Datum
update public.transactions t
   set kapitel_id = public.kapitel_fuer(t.occurred_at::date)
 where t.kind = 'wd_hedge'
   and t.kapitel_id is distinct from public.kapitel_fuer(t.occurred_at::date);

-- Prüf-Abfragen (nach dem Lauf):
-- 1) Kapitel 2 heißt „Neue Ära", key/hedge unverändert:
--    select id, key, name, hedge, beschreibung from public.kapitel order by id;
--    → 2 | ohne_hedge | Neue Ära | false | Seit 24.09.2026: …
-- 2) Alle wd_hedge-Buchungen im Kapitel ihres Datums (erwartet vorher: 15 Zeilen, +411,54, alle auf 1 → jetzt 2):
--    select kapitel_id, public.kapitel_fuer(occurred_at) as soll, count(*), round(sum(amount)::numeric, 2)
--      from public.transactions where kind = 'wd_hedge' group by 1, 2 order by 1;
--    → nur Zeilen mit kapitel_id = soll
-- 3) Funktion enthält den neuen Zweig:
--    select pg_get_functiondef('public.set_kapitel()'::regprocedure) like '%wd_hedge%';   → true
-- 4) Andere Buchungsarten unverändert (Stichprobe: Anzahl je kind/kapitel vorher = nachher):
--    select kind, kapitel_id, count(*) from public.transactions group by 1, 2 order by 1, 2;
