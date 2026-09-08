-- ============================================================================
-- Prophos: topstep_credentials — TopstepX-Zugang pro Prophos-User
--
-- Zweck: Der TopstepX-Zugang (Username + API-Key) hing bisher am Browser: der
-- API-Key wurde nach dem Verbinden verworfen (prophos.html tsConnect), nur der
-- Token lag in localStorage. Folgen:
--   1. Auf jedem neuen Gerät / nach localStorage-Reset muss Username UND API-Key
--      komplett neu eingetippt werden.
--   2. Der TopstepX-Token lebt ~24h — ohne gespeicherten Key kein 1-Klick-Reconnect.
-- Mit dieser Tabelle hängt der Zugang am PROPHOS-USER: die Topstep-Mirror-Seite
-- füllt Username + API-Key automatisch vor, ein Klick auf „Verbinden" genügt.
-- Der nächtliche Auto-Disconnect (00:00 DE-Zeit, im Frontend) trennt nur den
-- Token — die Zugangsdaten hier bleiben.
--
-- Sicherheit: RLS erlaubt ausschließlich Zugriff auf die EIGENE Zeile
-- (auth.uid() = user_id). Gleiche Vertrauensstufe wie duplikum_credentials und
-- accounts.cred_password, wo Prophos bereits Zugangsdaten ablegt.
--
-- Im Supabase SQL Editor einfügen und auf „Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.topstep_credentials (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  username   text not null,
  api_key    text not null,
  updated_at timestamptz not null default now()
);

alter table public.topstep_credentials enable row level security;

drop policy if exists "own topstep_credentials select" on public.topstep_credentials;
create policy "own topstep_credentials select"
  on public.topstep_credentials for select using (auth.uid() = user_id);

drop policy if exists "own topstep_credentials insert" on public.topstep_credentials;
create policy "own topstep_credentials insert"
  on public.topstep_credentials for insert with check (auth.uid() = user_id);

drop policy if exists "own topstep_credentials update" on public.topstep_credentials;
create policy "own topstep_credentials update"
  on public.topstep_credentials for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own topstep_credentials delete" on public.topstep_credentials;
create policy "own topstep_credentials delete"
  on public.topstep_credentials for delete using (auth.uid() = user_id);

-- updated_at automatisch (nutzt dieselbe Funktion wie accounts / duplikum_credentials)
drop trigger if exists topstep_credentials_set_updated_at on public.topstep_credentials;
create trigger topstep_credentials_set_updated_at
  before update on public.topstep_credentials
  for each row execute function public.set_updated_at();
