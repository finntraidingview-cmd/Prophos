-- 2026-09-27: Volles TopstepX-Inventar je PC (Auftrag Koordination B20). puls_diagnose (≤ 6 kB) reicht dafür nicht. Puls schreibt
-- beim Inventar-Lauf (Knopf „TopstepX-Inventar", Signal aktion tsx_inventar bzw. POST /api/tsx-inventar) SOFORT über
-- POST https://web-production-bec81.up.railway.app/puls-inventar/<pc_id> — unabhängig davon, ob der Aufrufer noch wartet.
-- Inhalt: titel, url, erkannt {titel_tsx, url_tsx, titel_tv}, tabs [{name, tsx, tv}], seite, edits (Edit-Namen),
-- inventar {grund, seite_150, konto_offen, bracket_offen}: [[name, typ, [l,t,r,b]]], ausloeser_kandidaten, zeilen_kandidaten
-- [[text, [l,t,r,b]]], trail. Eine Zeile je PC (immer der letzte Lauf). Nur der Service-Key schreibt (RLS an, keine Policy).
-- Lesen: select pc_id, at, inventar->'erkannt', inventar->'tabs', inventar->'zeilen_kandidaten' from puls_inventar;
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
create table if not exists public.puls_inventar (
  pc_id     text primary key check (pc_id ~ '^pc-[a-z0-9]{4,12}$'),
  inventar  jsonb not null,
  at        timestamptz not null default now()
);
alter table public.puls_inventar enable row level security;
