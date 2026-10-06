-- VORRAT STUFE 2 (06.10.2026, Finn über den Master): Bestehens-Chance je Konto und Kette, Sicherheit per Monte Carlo, Nachkauf mit
-- Score/Dringlichkeit, „bestellt" gegen Doppelkauf, Lauf alle 6 h. Baut auf sql/2026-10-05_vorrat.sql auf (muss vorher drin sein).
-- Neu: vorrat_lauf (Ergebnis je Lauf), vorrat_bestellt; Spalten an vorrat_ziele und vorrat_einstellung. Ziel, Boden, Drawdown,
-- Etappe und Kaufpreis je Firma kommen NICHT von hier, sondern aus den Kernwerten in auto_plan_regeln (EINE Quelle,
-- sql/2026-10-06_auto_plan_kernwerte.sql, Finn 06.10.2026); die Funded-Wege der Futures sind Parameter in app.py (VORRAT2_STD). Alles liest/schreibt NUR das Backend (/admin/vorrat*, Service-Key): RLS an, keine Policy, nicht in der
-- Realtime-Publication (30.09.2026: das Realtime-Kontingent hat Prophos 9 h lahmgelegt).
-- IDs (ohne_ids) und der Code für das Mac-Skript (ki_code_sha256) stehen bewusst NICHT in dieser Datei (Repo öffentlich).

-- 1) Kauf-Einheit als Zahl (was Finn nachkauft; Stufe und Preis kommen aus den Kernwerten)
alter table public.vorrat_ziele add column if not exists kauf_groesse numeric;
update public.vorrat_ziele set kauf_groesse = 150000 where firma in ('Tradeify', 'Topstep', 'Apex Trader') and kauf_groesse is null;
update public.vorrat_ziele set kauf_groesse = 100000 where firma in ('FTMO', 'FundedNext', 'FundingPips') and kauf_groesse is null;
update public.vorrat_ziele set kauf_einheit = '150k EOD' where firma = 'Apex Trader' and kauf_einheit = '150k';

-- 2) Schalter. sicherheit = P(Bestand ≥ Untergrenze), Finn stellt sie auf der Seite (0,5–0,95). parameter = Überschreibungen der
-- Standardwerte in app.py (VORRAT2_STD), z. B. {"tranche_gemeinsam": true}. ohne_ids = IDs, die nicht auf der Seite stehen.
-- ki_code_sha256 = sha256 des Codes, mit dem das Mac-Skript Texte schreibt (Header X-Vorrat-Code). Muster (Code NICHT hier):
--   update public.vorrat_einstellung set ki_code_sha256 = encode(extensions.digest('<CODE>', 'sha256'), 'hex') where id = 1;
alter table public.vorrat_einstellung add column if not exists sicherheit numeric not null default 0.8
  check (sicherheit >= 0.5 and sicherheit <= 0.95);
alter table public.vorrat_einstellung add column if not exists parameter jsonb not null default '{}'::jsonb;
alter table public.vorrat_einstellung add column if not exists ohne_ids uuid[] not null default '{}';
alter table public.vorrat_einstellung add column if not exists ki_code_sha256 text;

-- 3) Ergebnis je Lauf. quelle takt (alle 6 h) | hand („Jetzt aktualisieren"). slot = Takt-Zeitpunkt; der Unique-Index ist der Claim
-- (zwei Railway-Instanzen rechnen denselben Takt nie doppelt). ergebnis = alle Zellen wie in /admin/vorrat (inkl. Totband-Stand).
-- ki_text / ki_zeilen {"user_id|firma": text} / ki_um schreibt nur /admin/vorrat/ki.
create table if not exists public.vorrat_lauf (
  id         bigserial primary key,
  at         timestamptz not null default now(),
  quelle     text not null default 'hand' check (quelle in ('takt', 'hand')),
  slot       timestamptz,
  parameter  jsonb,
  quoten     jsonb,
  ergebnis   jsonb,
  fehler     text,
  ki_text    text,
  ki_zeilen  jsonb,
  ki_um      timestamptz
);
create unique index if not exists vorrat_lauf_takt_uq on public.vorrat_lauf (slot) where quelle = 'takt';
create index if not exists vorrat_lauf_fertig_idx on public.vorrat_lauf (id desc) where ergebnis is not null;
alter table public.vorrat_lauf enable row level security;

-- 4) „bestellt": gekauft, aber noch nicht in Prophos angelegt (Kritik 06.10.2026: Doppelkauf-Lücke). Zieht anzahl − seither
-- angelegte Konten vom Vorschlag ab, bis verfall_at (Standard 48 h) oder weg_at (zurückgenommen).
create table if not exists public.vorrat_bestellt (
  id         bigserial primary key,
  user_id    uuid not null references auth.users(id) on delete cascade,
  firma      text not null,
  anzahl     smallint not null check (anzahl between 1 and 20),
  einheit    text,
  von        uuid references auth.users(id) on delete set null,
  at         timestamptz not null default now(),
  verfall_at timestamptz not null,
  weg_at     timestamptz
);
create index if not exists vorrat_bestellt_offen_idx on public.vorrat_bestellt (user_id, firma) where weg_at is null;
alter table public.vorrat_bestellt enable row level security;
