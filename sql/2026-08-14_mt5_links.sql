-- ============================================================================
-- Prophos: mt5_links — MT5-Copier-Account ↔ manueller Prophos-Account
--
-- Zweck: Die Verlinkung der (manuell hinzugefügten) MT5-Copier-Accounts mit
-- den manuellen Prophos-Accounts lag zunächst als JSON-Blob in user_settings
-- (Key mt5_links, Muster dup_links). Finns Vorgabe vom 14.08.2026: die
-- Speicherung soll als richtige SQL-Tabelle in Supabase liegen — abfragbar,
-- mit Constraints, statt als Blob.
--
-- Modell: 1 MT5-Login ↔ 1 manueller Account, pro Prophos-User.
--   - Schlüssel ist der MT5-LOGIN (Kontonummer des Hedge-Accounts im Terminal),
--     NICHT der Instanz-Dateiname des Copiers: der Login ist PC-übergreifend
--     stabil, die .json-Dateinamen des Copiers nicht.
--   - unique (user_id, account_id) erzwingt die 1:1-Beziehung auch auf DB-Seite;
--     das Frontend löst Konflikte vorher selbst (löscht den Alt-Link), die
--     Constraint ist der Backstop.
--
-- Sicherheit: RLS ausschließlich auf die EIGENEN Zeilen (auth.uid() = user_id),
-- gleiches Muster wie duplikum_credentials.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.mt5_links (
  user_id    uuid not null references auth.users(id) on delete cascade,
  mt5_login  text not null,              -- Kontonummer im MT5-Terminal (als Text: führende Nullen, Broker-Eigenheiten)
  account_id uuid not null references public.accounts(id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, mt5_login),
  unique (user_id, account_id)
);

alter table public.mt5_links enable row level security;

drop policy if exists "own mt5_links select" on public.mt5_links;
create policy "own mt5_links select"
  on public.mt5_links for select using (auth.uid() = user_id);

drop policy if exists "own mt5_links insert" on public.mt5_links;
create policy "own mt5_links insert"
  on public.mt5_links for insert with check (auth.uid() = user_id);

drop policy if exists "own mt5_links update" on public.mt5_links;
create policy "own mt5_links update"
  on public.mt5_links for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own mt5_links delete" on public.mt5_links;
create policy "own mt5_links delete"
  on public.mt5_links for delete using (auth.uid() = user_id);

-- updated_at automatisch (nutzt dieselbe Funktion wie accounts)
drop trigger if exists mt5_links_set_updated_at on public.mt5_links;
create trigger mt5_links_set_updated_at
  before update on public.mt5_links
  for each row execute function public.set_updated_at();
