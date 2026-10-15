-- 2026-10-16: PC-Namen (Finn 16.10.2026: „In Zukunft beschrifte die PCs jeweils mit dem Namen").
-- Das Frontend zeigt überall, wo eine PC-Kennung steht, „Name · pc-xxxxxx" (pcLabel in prophos.html, Daten über GET /pc-namen).
-- Rangfolge in app.py pc_namen_zuordnen: (1) diese Tabelle, (2) Rückfall = die ID, deren Login der PC-Tab zuletzt in
-- mt5_live.status.user_id gemeldet hat. Die Tabelle braucht es nur für PCs, an denen mehrere IDs einloggen, oder wenn der
-- Login-Name nicht passt. Neue PCs bekommen ihren Namen ohne Eintrag aus dem Login.
-- RLS an, KEINE Policy: gelesen wird nur über Railway mit dem Service-Key. Idempotent. Im Supabase SQL Editor ausführen.

create table if not exists public.pc_namen (
  pc_id      text primary key check (pc_id ~ '^pc-[a-z0-9]{4,12}$'),
  name       text not null check (length(trim(name)) between 1 and 40),
  updated_at timestamptz not null default now()
);
alter table public.pc_namen enable row level security;

-- Einträge (echte Namen und Kennungen NICHT in diese Datei, nur direkt in der DB):
-- insert into public.pc_namen (pc_id, name) values ('pc-xxxxxx', 'Name')
--   on conflict (pc_id) do update set name = excluded.name, updated_at = now();

-- Lesen:
-- select pc_id, name, updated_at from public.pc_namen order by name;
