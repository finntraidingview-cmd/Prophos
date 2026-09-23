-- 2026-09-24: Kapitel — zeitliche Trennung der Daten in „Hedge-Ära" und „Ohne Hedge".
-- Finn (24.09.2026): „Ab jetzt wird es nicht mehr gegengehedgt mit Realmoney. Das heißt, in den
-- Datenbanken, dass wir das Ganze zeitlich trennen können mit den vorherigen Daten, sodass man es
-- auseinanderhalten kann — und dass man auch in Prophos in so einem neuen Chapter alles da sieht."
--
-- Kapitel 1 = Hedge-Ära: alle Bestandsdaten bis einschließlich 23.09.2026 (Kauf, Hedge-Kosten,
-- Payouts über Echo/Orbit/Duplikum). Kapitel 2 = Ohne Hedge: ab 24.09.2026, offen (bis = null).
-- Die Zuordnung ist REIN ZEITLICH (Datum der Zeile → Kapitel) — bewusst keine Regel- oder
-- Compliance-Prüfung, Prophos ist Ausführungs-Infrastruktur. Einzige Ausnahme im Backfill:
-- Pläne auf den V2-Wegen (mt5v2/tvv2) gehören per Definition ins Kapitel 2, egal wann angelegt.
--
-- Bausteine: Tabelle kapitel (Seed 1+2, Finn bearbeitet Name/Datum später im Admin-Tab),
-- Funktion kapitel_fuer(date), Spalte kapitel_id auf accounts / trade_plans / transactions,
-- BEFORE-INSERT-Trigger (setzt nur, wenn kapitel_id leer ist), Backfill der Bestandsdaten.

-- 1) Tabelle kapitel ------------------------------------------------------------------------
create table if not exists public.kapitel (
  id           smallint primary key,
  key          text not null unique,
  name         text not null,
  von          date not null,
  bis          date,                          -- null = offenes Kapitel
  hedge        boolean not null default false,
  farbe        text,                          -- Hex, z. B. '#7C3AED'
  beschreibung text,
  created_at   timestamptz default now(),
  updated_at   timestamptz default now()
);

-- RLS Muster A wie kompass_regeln: alle Angemeldeten dürfen lesen und schreiben — das Kapitel
-- ist für alle IDs dasselbe, und Finn pflegt Name/Datum aus dem Admin-Tab.
alter table public.kapitel enable row level security;
drop policy if exists "kapitel angemeldet" on public.kapitel;
create policy "kapitel angemeldet" on public.kapitel
  for all to authenticated using (true) with check (true);

-- updated_at automatisch (dieselbe Funktion wie accounts / mt5_links)
drop trigger if exists kapitel_set_updated_at on public.kapitel;
create trigger kapitel_set_updated_at
  before update on public.kapitel
  for each row execute function public.set_updated_at();

insert into public.kapitel (id, key, name, von, bis, hedge, farbe, beschreibung) values
  (1, 'hedge', 'Hedge-Ära', '2026-04-29', '2026-09-23', true, '#7C3AED',
   'Prop-Konten mit Gegen-Hedge auf Live-Konten (Echo/Orbit/Duplikum). Kauf, Hedge-Kosten und Payouts bis 23.09.2026.'),
  (2, 'ohne_hedge', 'Ohne Hedge', '2026-09-24', null, false, '#0E7A78',
   'Seit 24.09.2026 kein Gegen-Hedge mit Realmoney mehr — Puls platziert nur (Echo V2 / Orbit V2).')
on conflict (id) do nothing;

-- 2) kapitel_fuer(date) ---------------------------------------------------------------------
-- Liefert die id des Kapitels, in dessen Zeitraum d fällt (von <= d <= bis, bis null = offen).
-- Überlappen sich Kapitel, gewinnt das mit dem größten von. Fällt d in kein Kapitel: liegt d vor
-- allen Kapiteln → das früheste; sonst → das offene bzw. das mit dem größten von. Gibt also nie
-- null zurück, solange die Tabelle nicht leer ist — jede Zeile bekommt ein Kapitel.
create or replace function public.kapitel_fuer(d date)
returns smallint
language sql
stable
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

-- 3) Spalte kapitel_id + Indizes ------------------------------------------------------------
alter table public.accounts     add column if not exists kapitel_id smallint references public.kapitel(id);
alter table public.trade_plans  add column if not exists kapitel_id smallint references public.kapitel(id);
alter table public.transactions add column if not exists kapitel_id smallint references public.kapitel(id);

create index if not exists accounts_user_kapitel_idx     on public.accounts     (user_id, kapitel_id);
create index if not exists trade_plans_user_kapitel_idx  on public.trade_plans  (user_id, kapitel_id);
create index if not exists transactions_user_kapitel_idx on public.transactions (user_id, kapitel_id);

-- 4) BEFORE-INSERT-Trigger ------------------------------------------------------------------
-- Eine generische Funktion, die je Tabelle das passende Datum nimmt. Greift nur, wenn der
-- Aufrufer kein kapitel_id mitgibt — Frontend/Backend dürfen also bewusst ein Kapitel setzen.
create or replace function public.set_kapitel()
returns trigger
language plpgsql
as $$
begin
  if new.kapitel_id is null then
    if tg_table_name = 'transactions' then
      new.kapitel_id := public.kapitel_fuer(coalesce(new.occurred_at, current_date));
    else
      -- accounts und trade_plans: Anlagedatum
      new.kapitel_id := public.kapitel_fuer(coalesce(new.created_at, now())::date);
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists accounts_set_kapitel on public.accounts;
create trigger accounts_set_kapitel
  before insert on public.accounts
  for each row execute function public.set_kapitel();

drop trigger if exists trade_plans_set_kapitel on public.trade_plans;
create trigger trade_plans_set_kapitel
  before insert on public.trade_plans
  for each row execute function public.set_kapitel();

drop trigger if exists transactions_set_kapitel on public.transactions;
create trigger transactions_set_kapitel
  before insert on public.transactions
  for each row execute function public.set_kapitel();

-- 5) Backfill der Bestandsdaten (nur Zeilen ohne Kapitel) -----------------------------------
update public.accounts
   set kapitel_id = public.kapitel_fuer(created_at::date)
 where kapitel_id is null;

update public.transactions
   set kapitel_id = public.kapitel_fuer(occurred_at)
 where kapitel_id is null;

-- Pläne: Abschlussdatum, sonst Anlagedatum. AUSNAHME V2: die Wege mt5v2 (Echo V2) und tvv2
-- (Orbit V2) sind per Definition „ohne Hedge" und der Anfang des neuen Kapitels — auch der
-- erste V2-Plan vom 23.09. gehört ins Kapitel 2, nicht in die Hedge-Ära.
update public.trade_plans
   set kapitel_id = case
         when route in ('mt5v2', 'tvv2') then 2
         else public.kapitel_fuer(coalesce(completed_at, created_at)::date)
       end
 where kapitel_id is null;

-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
