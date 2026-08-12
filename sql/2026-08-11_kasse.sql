-- ============================================================================
-- Prophos: Kasse — gemeinsame 50:50-Kasse (Finn & Pascal)
--
-- Bewusst NICHT nach user_id getrennt: die Kasse ist profilübergreifend.
-- Jeder eingeloggte Prophos-User (egal welches Duplikum-/Personen-Profil)
-- sieht und bearbeitet DIESELBE Kasse. Der Zugriffscode (7856) sitzt im
-- Frontend als UI-Gate — die DB-Regel erlaubt jedem authentifizierten User
-- Lesen/Schreiben.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.kasse_entries (
  id          uuid primary key default gen_random_uuid(),
  who         text not null check (who in ('finn','pascal')),
  amount      numeric not null check (amount > 0),
  note        text,
  entry_date  date not null default current_date,
  created_at  timestamptz not null default now()
);

alter table public.kasse_entries enable row level security;

drop policy if exists "kasse read"   on public.kasse_entries;
drop policy if exists "kasse insert" on public.kasse_entries;
drop policy if exists "kasse delete" on public.kasse_entries;

-- Alle authentifizierten Prophos-User teilen sich die Kasse (profilübergreifend).
create policy "kasse read"   on public.kasse_entries for select to authenticated using (true);
create policy "kasse insert" on public.kasse_entries for insert to authenticated with check (true);
create policy "kasse delete" on public.kasse_entries for delete to authenticated using (true);

create index if not exists kasse_entries_date_idx
  on public.kasse_entries (entry_date desc, created_at desc);
