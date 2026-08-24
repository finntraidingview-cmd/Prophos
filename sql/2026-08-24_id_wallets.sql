-- ============================================================================
-- Prophos: Meta-Wallet-Tracking pro Person (Admin → Meta Wallet, 24.08.2026)
--
-- Jede ID/Person hat eine MetaMask-Wallet; getrackt werden die USDT-Bestände
-- auf Arbitrum, Solana und Tron — watch-only über die ÖFFENTLICHEN Adressen.
-- Es werden NIEMALS Keys oder Seed-Phrases gespeichert, nur Adressen.
--
-- Wie kasse_entries bewusst NICHT nach user_id getrennt: der Admin-Bereich
-- (Code-Gate im Frontend) verwaltet die Wallets ALLER Personen, jeder
-- authentifizierte Prophos-User liest/schreibt dieselben Zeilen.
--
-- wallet_snapshots: 1 Zeile pro Wallet und Tag (Upsert beim Laden des Tabs).
-- Daraus entsteht der Verlaufs-Chart — ganz ohne Chain-History-API, die für
-- Arbitrum/Solana einen API-Key bräuchte.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.id_wallets (
  id           uuid primary key default gen_random_uuid(),
  person_uid   text,                -- user_id des Prophos-Profils, wenn bekannt (Personen-Filter)
  person_name  text not null,       -- lesbarer Name — Anzeige + Fallback, falls kein Profil passt
  chain        text not null check (chain in ('arbitrum','solana','tron')),
  address      text not null,
  created_at   timestamptz not null default now(),
  unique (chain, address)
);

create table if not exists public.wallet_snapshots (
  id         uuid primary key default gen_random_uuid(),
  wallet_id  uuid not null references public.id_wallets(id) on delete cascade,
  day        date not null default current_date,
  usdt       numeric not null,
  taken_at   timestamptz not null default now(),
  unique (wallet_id, day)
);

alter table public.id_wallets      enable row level security;
alter table public.wallet_snapshots enable row level security;

drop policy if exists "wallets read"    on public.id_wallets;
drop policy if exists "wallets insert"  on public.id_wallets;
drop policy if exists "wallets delete"  on public.id_wallets;
drop policy if exists "snapshots read"   on public.wallet_snapshots;
drop policy if exists "snapshots upsert" on public.wallet_snapshots;
drop policy if exists "snapshots update" on public.wallet_snapshots;
drop policy if exists "snapshots delete" on public.wallet_snapshots;

create policy "wallets read"    on public.id_wallets for select to authenticated using (true);
create policy "wallets insert"  on public.id_wallets for insert to authenticated with check (true);
create policy "wallets delete"  on public.id_wallets for delete to authenticated using (true);

create policy "snapshots read"   on public.wallet_snapshots for select to authenticated using (true);
create policy "snapshots upsert" on public.wallet_snapshots for insert to authenticated with check (true);
create policy "snapshots update" on public.wallet_snapshots for update to authenticated using (true) with check (true);
create policy "snapshots delete" on public.wallet_snapshots for delete to authenticated using (true);

create index if not exists wallet_snapshots_wallet_day_idx
  on public.wallet_snapshots (wallet_id, day desc);
