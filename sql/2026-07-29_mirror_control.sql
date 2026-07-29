-- Steuertabelle für den lokalen Topstep-Mirror-Agent (läuft pro PC statt auf Railway).
-- Prophos schreibt den AUFTRAG hier rein (was gespiegelt werden soll); der Agent auf dem
-- jeweiligen PC liest seine Zeilen, führt den Mirror lokal aus (Verbindung aus der PC-IP,
-- nicht mehr aus Amsterdam) und schreibt Status/Log zurück.
--
-- WICHTIG: Hier stehen KEINE Secrets. TopstepX-API-Key/-Username und MetaApi-Token liegen
-- ausschließlich lokal im config.json auf dem jeweiligen PC — sie verlassen den PC nie.
-- Im Supabase SQL-Editor ausführen.

create table if not exists public.mirror_control (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users(id) on delete cascade,
  agent_id       text not null,                 -- welcher PC/welche Person: z.B. "moritz-pc"
  pair_id        text not null,                 -- eindeutige Mirror-Paarung (Master↔Slave)
  active         boolean not null default false,-- Prophos schaltet hiermit an/aus
  -- Operative, NICHT-geheime Parameter (identisch zu /mirror/start im alten Backend):
  tsx_account_id text,
  ma_account_id  text,
  multiplier     numeric default 1.0,
  target_risk_eur numeric default 0,
  poll_interval  numeric default 0.5,
  base_instrument text default 'MNQ',
  direction      text default 'tsx_to_mt',
  engine         text default 'polling',
  symbol_map     jsonb default '{"MNQ":"NAS100","NQ":"NAS100","ES":"US500","MES":"US500"}'::jsonb,
  -- Rückschreibefelder (Agent → Prophos, für Anzeige):
  status         text default 'stopped',        -- running | stopped | error
  last_heartbeat timestamptz,
  log            jsonb default '[]'::jsonb,      -- Ring-Puffer der letzten Log-Zeilen
  positions      jsonb default '{}'::jsonb,      -- offene gespiegelte Positionen (Anzeige)
  updated_at     timestamptz default now(),
  unique (user_id, pair_id)
);

alter table public.mirror_control enable row level security;

drop policy if exists mirror_control_owner on public.mirror_control;
create policy mirror_control_owner on public.mirror_control
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create index if not exists mirror_control_agent_idx
  on public.mirror_control (agent_id, active);

comment on table public.mirror_control is
  'Auftrag + Status für den lokalen Topstep-Mirror-Agent pro PC. Keine Secrets — die liegen lokal im config.json auf dem PC.';
