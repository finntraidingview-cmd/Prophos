-- 2026-11-10 — FX2 Fehlstart-Doktor (Master; Konstrukt FX1 von S5, Finn 10.11.2026: Mac-Aufgabe ja, sichere Reparaturen ohne Rückfrage ja, Takt 10 min im Handel
-- UND sofort bei neuem Fehlstart). Gehirn auf Railway (app.py fd_*: Rezepte, Riegel, Protokoll, Nachplanen, Meldungen), Hände auf dem Mac
-- (pc-fernzugriff/mac/doktor.py, launchd, nur Befehle aus seiner festen Liste über pc.sh).
--
-- fehlstart_doktor_regel (id 1): an = Doktor läuft (Standard AUS), reparieren = sichere Reparaturen + Nachplanen (Standard AUS → nur lesen und melden),
--   stand_at = bis wohin puls_fehlstarts gelesen ist (Railway schreibt), bericht_tag = letzter Tagesbericht.
-- fehlstart_doktor: ein Protokoll-Eintrag je Fehlstart (fehlstart_id = puls_fehlstarts.id, eindeutig) — Rezept, Befund, Aktion, Ergebnis, braucht_finn.
--   status: nichts (heilt von selbst / unbekannt) · gemeldet (braucht Finn) · gesperrt (Riegel: offener Trade, Start ≤ 10 min, Puls läuft, Signal offen, unklar)
--   · wartet_mac (Auftrag für den Mac) · laeuft · behoben · fertig · verfallen (Mac hat ihn nicht abgeholt).
-- Nur service_role (RLS an, keine Policy). Idempotent.
-- Einschalten:  update public.fehlstart_doktor_regel set an = true where id = 1;                 (nur lesen + melden)
--               update public.fehlstart_doktor_regel set reparieren = true where id = 1;         (dazu sichere Reparaturen + Nachplanen)
-- Ausschalten:  update public.fehlstart_doktor_regel set an = false where id = 1;
-- Rückbau:      drop table if exists public.fehlstart_doktor; drop table if exists public.fehlstart_doktor_regel;

create table if not exists public.fehlstart_doktor_regel (
  id          int primary key default 1 check (id = 1),
  an          boolean not null default false,
  reparieren  boolean not null default false,
  stand_at    timestamptz,
  bericht_tag text,
  updated_at  timestamptz not null default now()
);
insert into public.fehlstart_doktor_regel (id) values (1) on conflict (id) do nothing;

create table if not exists public.fehlstart_doktor (
  id            bigserial primary key,
  at            timestamptz not null default now(),
  fehlstart_id  bigint unique,
  fehlstart_at  timestamptz,
  plan_id       text,
  user_id       uuid,
  pc            text,
  rezept        text,
  muster        text,
  befund        text,
  befehle       jsonb,
  ausgabe       jsonb,
  aktion        text,
  status        text not null default 'neu',
  ergebnis      text,
  braucht_finn  boolean not null default false,
  ablauf_at     timestamptz,
  updated_at    timestamptz not null default now()
);
create index if not exists fehlstart_doktor_status_idx on public.fehlstart_doktor (status, ablauf_at);
create index if not exists fehlstart_doktor_pc_at_idx on public.fehlstart_doktor (pc, at desc);

alter table public.fehlstart_doktor_regel enable row level security;
alter table public.fehlstart_doktor enable row level security;

-- Kontrolle: select * from public.fehlstart_doktor_regel; select status, count(*) from public.fehlstart_doktor group by 1;
