-- NW2 NEWS-FENSTER: FOMC JEDER STUFE FÜR ALLE FUNDED-CFD-KONTEN (Finn 27.11.2026 — Blue Guardian zog zweimal Profit ab; laut Help Center
-- „CFD news trading rules" (Stand 18.11.2026) zählt dort bei Funded jeder FOMC-Termin, auch gelb/orange und Reden, ±5 min. Finn erst „Ja, nur
-- Blue Guardian", dann korrigiert: „Mach alle Prop für uns bei FOMC, nicht nur Blue Guardian, alle … alle CFD Forex halt").
-- Die bestehende News-Regel Funded CFD (30.10.2026, rote USD-News, Werte in prophos.html NEWS_REGEL) bleibt unverändert. Diese Tabelle hält
-- Schalter und Minuten für das ZUSÄTZLICHE schmale Fenster um FOMC-Termine unter rot: kein START von vor_min vor bis nach_min nach dem
-- Termin (je + 0…streu_min gewürfelt). Nur Start-Sperre: am Schließen (Auto-Close, vor roter News, von Hand) ändert die Tabelle nichts. Zeile firmen '{*}' = alle Firmen; eine Zeile mit
-- Firmenname ginge für diese Firma vor (Abweichung als Daten, nicht im Code). Ohne Zeile gilt derselbe Standard aus prophos.html
-- (NEWS_FOMC_STANDARD: an, 7 / 6 / 2) — die Tabelle ist der Ort zum Ausschalten und Ändern.
-- Warum eine eigene Tabelle statt einer Spalte neben funded_cfd_plan_regeln.news_regel: die liest nur das Backend (app.py, /news/calendar),
-- der PC-Tab kommt an sie nicht heran; diese hier liest der PC-Tab direkt (wie liq_regeln): lesen darf jeder angemeldete Nutzer, schreiben
-- nur der Dienst-Schlüssel. Der Hauptschalter news_regel schaltet weiter beides aus.
-- Idempotent. Rückweg (FOMC-Teil aus): update public.news_fenster_regeln set fomc_jede_stufe = false where firmen = '{*}';

create table if not exists public.news_fenster_regeln (
  id              bigint generated always as identity primary key,
  name            text not null,                                   -- Anzeigename der Zeile
  firmen          text[] not null,                                 -- '{*}' = alle Firmen; sonst Schreibweisen der Firma, klein und ohne Leerzeichen
  kontoarten      text[] not null default '{funded_cfd}',          -- accounts.account_type, für die die Zeile gilt
  fomc_jede_stufe boolean not null default false,                  -- FOMC-Termine unter rot zählen (Titel: FOMC / Federal Funds Rate / Fed Chair)
  vor_min         numeric not null default 7 check (vor_min >= 6), -- Fenster-Beginn vor dem Termin (7 statt 6: ein Start braucht ~45 s vom Auslösen bis zur Order)
  nach_min        numeric not null default 6 check (nach_min >= 6),
  streu_min       numeric not null default 2 check (streu_min >= 0),  -- Streuung oben drauf, je Termin gewürfelt
  aktiv           boolean not null default true,
  notiz           text,
  updated_at      timestamptz not null default now()
);

create unique index if not exists news_fenster_regeln_name on public.news_fenster_regeln (lower(name));

alter table public.news_fenster_regeln enable row level security;
revoke all on public.news_fenster_regeln from anon, authenticated;
grant select on public.news_fenster_regeln to authenticated;
drop policy if exists news_fenster_regeln_lesen on public.news_fenster_regeln;
create policy news_fenster_regeln_lesen on public.news_fenster_regeln for select to authenticated using (true);

-- Offsite-Backup sieht neue Tabellen nicht von selbst (wie bei liq_regeln)
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'backup_reader') then
    execute 'grant select on table public.news_fenster_regeln to backup_reader';
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'news_fenster_regeln' and policyname = 'backup_reader_select') then
      execute 'create policy backup_reader_select on public.news_fenster_regeln for select to backup_reader using (true)';
    end if;
  end if;
end $$;

-- Die eine Zeile: alle Firmen, Funded CFD (Challenge, Phase 1/2, Winning Days, Futures stehen nicht in kontoarten und bleiben unberührt)
insert into public.news_fenster_regeln (name, firmen, kontoarten, fomc_jede_stufe, vor_min, nach_min, streu_min, notiz)
select 'Alle Firmen', '{*}', '{funded_cfd}', true, 7, 6, 2,
       'Finn 27.11.2026: FOMC jeder Stufe für alle CFD-Prop-Firmen (Anlass Blue Guardian, Help Center „CFD news trading rules" 18.11.2026)'
where not exists (select 1 from public.news_fenster_regeln where lower(name) = 'alle firmen');
