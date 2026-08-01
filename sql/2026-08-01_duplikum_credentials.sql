-- ============================================================================
-- Prophos: duplikum_credentials — Duplikum-Zugang pro Prophos-User
--
-- Zweck: Der Duplikum-Zugang hängt bisher am Browser (localStorage) und das
-- Passwort nur im Backend-RAM. Folgen:
--   1. Nach einem Account-Wechsel muss Duplikum manuell neu verbunden werden.
--   2. Der Token läuft nach 48h ab; nach einem Backend-Neustart fehlt das
--      Passwort für den automatischen Refresh.
-- Mit dieser Tabelle hängt der Zugang am PROPHOS-USER: Login/Wechsel verbindet
-- Duplikum automatisch, und der nächtliche Reconnect überlebt Neustarts.
--
-- Sicherheit: RLS erlaubt ausschließlich Zugriff auf die EIGENE Zeile
-- (auth.uid() = user_id). Gleiche Vertrauensstufe wie accounts.cred_password,
-- wo Prophos bereits Broker-Zugangsdaten ablegt.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.duplikum_credentials (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  email      text not null,
  password   text not null,
  token      text,                       -- zuletzt gültiger Token (spart einen Login)
  token_at   timestamptz,                -- wann der Token geholt wurde (48h-Ablauf)
  updated_at timestamptz not null default now()
);

alter table public.duplikum_credentials enable row level security;

drop policy if exists "own duplikum_credentials select" on public.duplikum_credentials;
create policy "own duplikum_credentials select"
  on public.duplikum_credentials for select using (auth.uid() = user_id);

drop policy if exists "own duplikum_credentials insert" on public.duplikum_credentials;
create policy "own duplikum_credentials insert"
  on public.duplikum_credentials for insert with check (auth.uid() = user_id);

drop policy if exists "own duplikum_credentials update" on public.duplikum_credentials;
create policy "own duplikum_credentials update"
  on public.duplikum_credentials for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own duplikum_credentials delete" on public.duplikum_credentials;
create policy "own duplikum_credentials delete"
  on public.duplikum_credentials for delete using (auth.uid() = user_id);

-- updated_at automatisch (nutzt dieselbe Funktion wie accounts)
drop trigger if exists duplikum_credentials_set_updated_at on public.duplikum_credentials;
create trigger duplikum_credentials_set_updated_at
  before update on public.duplikum_credentials
  for each row execute function public.set_updated_at();
