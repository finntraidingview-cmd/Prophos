-- SK1 — Striking-Add-on für Apex (Finn 20.11.2026 ~04:15 Dubai: Konstrukt „passt“, Hedge „0.2 auf max drawdown“).
-- Spezifikation: .claude/master/berichte/2026-11-20_SK1_striking_apex_konstrukt.md, Abschnitt „Datenmodell“ (verbindlich für S1 Backend + S3 Frontend).
-- Planer: app.py fdp_planen (Striking-Weg, Rechnung in striking_apex.py). Idempotent. Die Apex-Pause (sql/2026-11-20_apex_pause.sql) bleibt
-- unberührt und sperrt Striking NICHT (Nachtrag 3, Finn 20.11. ~04:35: „Nur den Planer gerade nur für Marc freischalten … Jede ID einzeln prüfen“):
-- Striking hat sein eigenes Gate — striking_regeln.aktiv (globaler Not-Aus, Standard AUS) + eine addon_firma-Zeile je ID + Startwerte je Konto.

-- 1) Regeln (eine Zeile, id 1) — Caps je Payout-Nr. als Tabelle, nicht hart im Code
create table if not exists public.striking_regeln (
  id         int primary key default 1 check (id = 1),
  apex       jsonb not null default '{}'::jsonb,
  aktiv      boolean not null default false,
  updated_at timestamptz not null default now()
);
alter table public.striking_regeln add column if not exists aktiv boolean not null default false;

-- min_profit gilt nur mit Trader Probation (ab Zyklus-Start); ohne Probation gilt min_payout_balance (absolute Balance, Nachtrag 2: Jacob)
insert into public.striking_regeln (id, apex) values (1, '{
  "caps":         {"100000": [2000, 2500, 2500, 3000, 4000, 4000], "150000": [2500, 3000, 3000, 3000, 4000, 5000]},
  "min_profit":   {"100000": 3600, "150000": 4600},
  "min_payout_balance": {"100000": 103600, "150000": 154600},
  "tag_schwelle": {"100000": 300,  "150000": 350},
  "klein_tp":     [370, 420],
  "deckel_pct":   50,
  "puffer":       0.95,
  "sl_pct":       [60, 90],
  "hedge_satz":   0.2
}'::jsonb)
on conflict (id) do nothing;
update public.striking_regeln set apex = apex || '{"min_payout_balance": {"100000": 103600, "150000": 154600}}'::jsonb, updated_at = now()
 where id = 1 and not (apex ? 'min_payout_balance');

alter table public.striking_regeln enable row level security;
drop policy if exists striking_regeln_lesen on public.striking_regeln;
create policy striking_regeln_lesen on public.striking_regeln for select to authenticated using (true);
drop policy if exists striking_regeln_admin on public.striking_regeln;
create policy striking_regeln_admin on public.striking_regeln for all to authenticated using (public.wd_admin()) with check (public.wd_admin());

-- 2) Add-on je ID × Firma (Apex-Tacho im Muster-Portfolio: „+ Striking“) — gilt für alle Apex-Fundeds (funded / winning_days) dieser ID
create table if not exists public.addon_firma (
  user_id    uuid    not null references auth.users(id) on delete cascade,
  firma      text    not null,
  addon      text    not null,
  an         boolean not null default true,
  updated_at timestamptz not null default now(),
  primary key (user_id, firma, addon)
);

alter table public.addon_firma enable row level security;
-- wie user_settings: eigene Zeilen; dazu Voll-Admins (wd_admin = admin_voll) für alle IDs
drop policy if exists addon_firma_eigen on public.addon_firma;
create policy addon_firma_eigen on public.addon_firma for all to authenticated
  using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists addon_firma_admin on public.addon_firma;
create policy addon_firma_admin on public.addon_firma for all to authenticated
  using (public.wd_admin()) with check (public.wd_admin());

-- Backup-Rolle liest mit (wie jede Tabelle, sql/2026-09-29_backup-reader-vollstaendig.sql)
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'backup_reader') then
    execute 'grant select on public.striking_regeln, public.addon_firma to backup_reader';
    execute 'drop policy if exists backup_reader_select on public.striking_regeln';
    execute 'create policy backup_reader_select on public.striking_regeln for select to backup_reader using (true)';
    execute 'drop policy if exists backup_reader_select on public.addon_firma';
    execute 'create policy backup_reader_select on public.addon_firma for select to backup_reader using (true)';
  end if;
end $$;

-- 3) Zyklus je Konto, von Hand pflegbar. Ohne Start, Seit und Payout-Nr. plant Striking das Konto nicht (fail-closed, „Startwerte fehlen“).
--    striking_zyklus_start = Balance zu Zyklus-Beginn (Probation-Start bzw. Balance nach dem letzten Payout)
--    striking_zyklus_seit  = Beginn des Zyklus (Probation = 2026-11-18, nach Payout = Payout-Datum) — gezählt werden NUR Trades mit Ende ab hier
--                            (Profit, bester Tag, Tage ≥ Schwelle, Consistency), nie die Lebensdauer des Kontos (Nachtrag 1)
--    striking_payout_nr    = Nummer des NÄCHSTEN Payouts (1–6) → Cap aus striking_regeln.apex.caps
--    striking_probation    = Trader Probation (Marc): nötiger Profit 3.600 / 4.600 ab Zyklus-Start; false (Jacob): Balance ≥ min_payout_balance
alter table public.accounts add column if not exists striking_zyklus_start numeric;
alter table public.accounts add column if not exists striking_zyklus_seit timestamptz;
alter table public.accounts add column if not exists striking_payout_nr int;
alter table public.accounts add column if not exists striking_probation boolean not null default false;
alter table public.accounts drop constraint if exists accounts_striking_payout_nr_check;
-- nur ≥ 1: die Obergrenze kommt aus der Cap-Tabelle (striking_regeln.apex.caps, Einstellung) — der Planer prüft 1–len(caps)
alter table public.accounts add constraint accounts_striking_payout_nr_check check (striking_payout_nr is null or striking_payout_nr >= 1);

-- Freischalten (nur auf Finns Wort, je ID einzeln): Startwerte je Konto (sql/2026-11-20_marc_apex_wieder_aktiv.sql), dann die ID, dann der Not-Aus
-- update public.accounts set striking_zyklus_start = <balance>, striking_zyklus_seit = '<JJJJ-MM-TT>', striking_payout_nr = <n>, striking_probation = <true|false>
--  where id = '<konto_id>';
-- insert into public.addon_firma (user_id, firma, addon, an) values ('<user_id>', 'apex', 'striking', true)
--   on conflict (user_id, firma, addon) do update set an = excluded.an, updated_at = now();
-- update public.striking_regeln set aktiv = true, updated_at = now() where id = 1;
