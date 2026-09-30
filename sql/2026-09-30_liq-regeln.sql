-- 2026-09-30: Liquidations-Regeln je Firma / Kontotyp / Größe (Finn, Sprachnotiz über den Master: „Die Liquidation ist bei uns immer
-- der Stop Loss bzw. das Daily Loss, das nutzen wir immer komplett aus. Leg dafür eine Tabelle an, am besten in der Datenbank, damit
-- wir das für spätere Probleme sauber haben."). Anlass: Radar .853, Moritz · Apex …0008 (Winning-Days-Konto, BUY 3 × NQ): die Spanne
-- zeigte die Liquidation ~155 Pkt unter dem Einstieg (Kontogröße + 100 $ = 150.100), echt liegt sie bei Apex-Stufe 3 nur 3.000 $
-- (= 50 Pkt) unter der Tagesstart-Balance.
--
-- Heute rechnet Prophos die Liquidation in app.py (_lt_liq_balance / _lt_liq / wd_sl_zeile): Winning Day = Kontogröße + 100 $,
-- alle anderen = accounts.max_drawdown als fester $-Abstand ab Einstieg, Topstep V2 = MLL aus TopstepX. Diese Tabelle ist NUR die
-- Wahrheit zum Nachschlagen — verdrahtet ist noch nichts (eigener Auftrag). Die Fusion-Hedge-Logik der Winning Days (schließt am
-- Liquidations-Level, echtes Geld) bleibt davon unberührt, bis Finn es ausdrücklich anders entscheidet.
--
-- Bedeutung der Spalten:
--   firma       wie accounts.firm („Tradeify", „Apex Trader", „FundedNext" …); null = alle Firmen
--   kontotyp    challenge | phase1 | phase2 | funded | funded_cfd | winning_days | live; null = alle Typen der Firma
--   groesse     Kontogröße in $ (150000); null = alle Größen
--   art         fest          Liquidation = Balance beim Trade-Start − betrag_usd (heutige Max-Drawdown-Rechnung)
--               trailing_lock wie fest, aber nie über (groesse + lock_ueber_start_usd): Liq = min(Start − betrag, Größe + Lock)
--               stufen        Daily Loss je Stufe nach Balance: Stufe = letzte mit ab_balance ≤ Tagesstart-Balance,
--                             Liq = Tagesstart-Balance − daily_loss_usd der Stufe
--               tagesstart    Daily Loss: Liq = Balance zu Tagesbeginn (CME-Handelstag) − betrag_usd
--               null          noch offen (siehe notiz)
--   wie_kontotyp  Regel eines anderen Kontotyps derselben Firma übernehmen (Winning Days → funded)
--   stufen      [{ab_balance, daily_loss_usd, minis, micros}] aufsteigend
--   notiz       Finns Wortlaut, Quellenhinweise und „offen: …", wo etwas unklar ist
-- Nachschlagen: die spezifischste Zeile gewinnt (firma+kontotyp+groesse vor firma+kontotyp vor firma vor alle); wie_kontotyp
-- wird aufgelöst. Firmennamen beim Vergleich normalisieren (wie _firm_norm in app.py).
--
-- Lesen darf jeder Eingeloggte (Radar/Karten sollen die Regel anzeigen können), schreiben nur service_role (Railway / Master).
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent (Seed nur, wo die Kombination firma/kontotyp/groesse fehlt).

create table if not exists public.liq_regeln (
  id                   bigint generated always as identity primary key,
  firma                text,
  kontotyp             text check (kontotyp is null or kontotyp in ('challenge', 'phase1', 'phase2', 'funded', 'funded_cfd', 'winning_days', 'live')),
  groesse              numeric check (groesse is null or groesse > 0),
  art                  text check (art is null or art in ('fest', 'trailing_lock', 'stufen', 'tagesstart')),
  betrag_usd           numeric check (betrag_usd is null or betrag_usd > 0),
  lock_ueber_start_usd numeric,
  stufen               jsonb check (stufen is null or jsonb_typeof(stufen) = 'array'),
  wie_kontotyp         text check (wie_kontotyp is null or wie_kontotyp in ('challenge', 'phase1', 'phase2', 'funded', 'funded_cfd')),
  notiz                text,
  quelle               text,
  updated_at           timestamptz not null default now()
);

-- eine Regel je Kombination (null zählt als „alle")
create unique index if not exists liq_regeln_eindeutig
  on public.liq_regeln ((coalesce(lower(firma), '')), (coalesce(kontotyp, '')), (coalesce(groesse, 0)));

-- updated_at bei jeder Änderung nachziehen
create or replace function public.liq_regeln_touch() returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_at := now();
  return new;
end $$;
drop trigger if exists liq_regeln_touch on public.liq_regeln;
create trigger liq_regeln_touch before update on public.liq_regeln for each row execute function public.liq_regeln_touch();

alter table public.liq_regeln enable row level security;
drop policy if exists liq_regeln_lesen on public.liq_regeln;
create policy liq_regeln_lesen on public.liq_regeln for select to authenticated using (true);
revoke insert, update, delete on public.liq_regeln from anon, authenticated;
grant select on public.liq_regeln to authenticated;

-- Offsite-Backup (sql/2026-09-01_backup-reader.sql) sieht neue Tabellen nicht von selbst
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'backup_reader') then
    execute 'grant select on table public.liq_regeln to backup_reader';
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'liq_regeln' and policyname = 'backup_reader_select') then
      execute 'create policy backup_reader_select on public.liq_regeln for select to backup_reader using (true)';
    end if;
  end if;
end $$;

-- ── Seed: GENAU Finns Angaben vom 30.09.2026; Unklares = null + notiz ──
insert into public.liq_regeln (firma, kontotyp, groesse, art, betrag_usd, lock_ueber_start_usd, stufen, wie_kontotyp, notiz, quelle)
select v.firma, v.kontotyp, v.groesse, v.art, v.betrag_usd, v.lock_ueber_start_usd, v.stufen, v.wie_kontotyp, v.notiz, v.quelle
from (values
  ('Tradeify', 'challenge', null::numeric, 'fest', 4500::numeric, null::numeric, null::jsonb, null::text,
   'Finn: „Tradeify Challenge: immer 4.500 $" → Liquidation = Stop Loss. Größe nicht genannt (in accounts sind alle Tradeify-Konten 150k; '
   || 'firm_rules.json: 4.500 $ = 150K Select Eval, EOD-Trailing, kein DLL). Offen: einige Tradeify-Challenges haben max_drawdown 8.000 — anderer Plan?',
   'Finn 30.09.2026 (Sprachnotiz über den Master)'),
  ('Tradeify', 'funded', null::numeric, 'trailing_lock', 4500::numeric, 100::numeric, null::jsonb, null::text,
   'Finn: „ebenfalls 4.500 $, trailt aber nur bis Start + 100 $, dann fest (bei 150k: Liq bleibt ab 150.100)". '
   || 'firm_rules.json: lockt bei EOD-Balance ≥ Start + 4.500 + 100 (150K: 154.600) → Floor 150.100. '
   || 'Offen: Nebensatz „außer wenn …" war unverständlich.',
   'Finn 30.09.2026 (Sprachnotiz über den Master)'),
  ('Apex Trader', 'challenge', null::numeric, 'tagesstart', 2000::numeric, null::numeric, null::jsonb, null::text,
   'Finn: „Apex Evaluation: 2.000 $". Größe nicht genannt. Art abgeleitet: in accounts steht bei Apex-Challenges max_daily_drawdown 2.000 '
   || '(max_drawdown 4.000) → Daily Loss ab Tagesbeginn. Offen: Daily Loss ab Tagesbeginn oder fester Abstand ab Trade-Start?',
   'Finn 30.09.2026 (Sprachnotiz über den Master)'),
  ('Apex Trader', 'funded', 150000::numeric, 'stufen', null::numeric, null::numeric,
   '[{"ab_balance":150000,"daily_loss_usd":2500,"minis":4,"micros":40},
     {"ab_balance":152000,"daily_loss_usd":2500,"minis":5,"micros":50},
     {"ab_balance":155000,"daily_loss_usd":3000,"minis":10,"micros":100},
     {"ab_balance":160000,"daily_loss_usd":4000,"minis":10,"micros":100}]'::jsonb, null::text,
   'Finn: Apex Funded — Stufen nach aktueller Balance (Screenshots aus Apex, 150k): ab 150.000 Daily Loss 2.500 $ (4 Minis/40 Micros), '
   || 'ab 152.000 2.500 $ (5/50), ab 155.000 3.000 $ (10/100), ab 160.000 (Max) 4.000 $ (10/100). Daily Loss zählt je Handelstag. '
   || 'Offen: welche Balance bestimmt die Stufe (Tagesbeginn oder live)? Andere Größen als 150k?',
   'Finn 30.09.2026 (Screenshots Apex 150k, über den Master)'),
  ('FundedNext', null::text, null::numeric, null::text, null::numeric, null::numeric, null::jsonb, null::text,
   'Finn: „FundedNext: immer bei Beginn" — keine Zahlen genannt. Offen: ab Anfangs-Balance des Kontos (statisch) oder ab Tagesbeginn? '
   || 'Gilt das auch für „FundedNext Futures" (eigene Firma in accounts)? Hinweise ohne Finns Bestätigung: firm_rules.json (Stand 01.05.2026, '
   || 'CFD Stellar 2-Step) statisch vom Initial Balance, Daily Loss 5 %, Max Loss 10 %; accounts FundedNext 100k: max_drawdown 10.000, max_daily 5.000.',
   'Finn 30.09.2026 (Sprachnotiz über den Master)'),
  (null::text, 'winning_days', null::numeric, null::text, null::numeric, null::numeric, null::jsonb, 'funded',
   'Finn: „Winning-Days-Konten folgen der Regel ihrer Firma im Funded-Zustand."',
   'Finn 30.09.2026 (Sprachnotiz über den Master)')
) as v(firma, kontotyp, groesse, art, betrag_usd, lock_ueber_start_usd, stufen, wie_kontotyp, notiz, quelle)
where not exists (
  select 1 from public.liq_regeln r
  where coalesce(lower(r.firma), '') = coalesce(lower(v.firma), '') and coalesce(r.kontotyp, '') = coalesce(v.kontotyp, '')
    and coalesce(r.groesse, 0) = coalesce(v.groesse, 0));

-- Prüfen:
-- select firma, kontotyp, groesse, art, betrag_usd, lock_ueber_start_usd, jsonb_array_length(stufen) stufen_n, wie_kontotyp, left(notiz, 80)
--   from public.liq_regeln order by firma nulls last, kontotyp nulls first;
