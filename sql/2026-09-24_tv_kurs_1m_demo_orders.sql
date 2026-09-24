-- ============================================================================
-- Prophos: Markt live + Demo-Orders (24.09.2026 abends, zweiter Schritt)
--
-- Finn: „Ich will unter Markt den Markt auch wieder gespiegelt sehen, auch als
-- Chart, sodass ich die Orders als Demo nachstellen kann." — Idee 1 + 3 aus
-- „Live-Kursfeed & Demo-Trading im eigenen Chart (01.09.2026)".
--
-- 1) tv_kurs_1m — Minutenkerzen aus dem Reader-Feed. Der reader-server bündelt
--    die 250-ms-Ticks des Tab-Titels je Minute (O/H/L/C), die Brücke im Prophos-
--    Tab des Reader-PCs upsertet die laufende und die letzte Minute alle 5 s.
--    Ticks bleiben lokal, in die Cloud gehen nur Kerzen (1.440 Zeilen/Tag) — die
--    Brücke räumt Kerzen älter als 14 Tage weg. Lücken (PC aus, Markt zu) sind
--    Lücken, nie interpoliert.
--
-- 2) demo_orders — Papier-Orders gegen den Live-Feed: Fill zum Feed-Kurs,
--    TP/SL in $ wie im Order-Popup (Level = Entry ± $ / (Punktwert × Kt)),
--    Auswertung über die Minutenkerzen (High/Low), damit ein Treffer auch
--    zählt, wenn gerade kein Tab offen war. Pro Nutzer (RLS wie trade_plans).
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.tv_kurs_1m (
  wurzel     text not null,                       -- NQ / MNQ
  minute     timestamptz not null,                -- Minutenanfang (UTC)
  symbol     text not null default '',            -- wie im Titel: NQZ2026
  o          numeric not null,
  h          numeric not null,
  l          numeric not null,
  c          numeric not null,
  ticks      integer not null default 0,          -- wie viele Titel-Ticks in der Minute
  pc         text not null default '',            -- Reader-PC, der die Kerze geliefert hat
  updated_at timestamptz not null default now(),
  primary key (wurzel, minute)
);
create index if not exists tv_kurs_1m_minute_idx on public.tv_kurs_1m (minute desc);

alter table public.tv_kurs_1m enable row level security;
drop policy if exists "tv_kurs_1m read"   on public.tv_kurs_1m;
drop policy if exists "tv_kurs_1m insert" on public.tv_kurs_1m;
drop policy if exists "tv_kurs_1m update" on public.tv_kurs_1m;
drop policy if exists "tv_kurs_1m delete" on public.tv_kurs_1m;
create policy "tv_kurs_1m read"   on public.tv_kurs_1m for select to authenticated using (true);
create policy "tv_kurs_1m insert" on public.tv_kurs_1m for insert to authenticated with check (true);
create policy "tv_kurs_1m update" on public.tv_kurs_1m for update to authenticated using (true) with check (true);
create policy "tv_kurs_1m delete" on public.tv_kurs_1m for delete to authenticated using (true);

create table if not exists public.demo_orders (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid(),
  symbol     text not null,                       -- NQ / MNQ (Punktwert 20 / 2 $)
  richtung   text not null check (richtung in ('buy','sell')),
  kt         integer not null check (kt > 0),
  entry      numeric not null,                    -- Fill = Feed-Kurs beim Platzieren
  entry_at   timestamptz not null default now(),
  entry_pc   text not null default '',            -- Reader-PC, dessen Kurs gefüllt hat
  tp_usd     numeric,                             -- wie im Order-Popup, optional
  sl_usd     numeric,
  tp_level   numeric,                             -- gerechnetes Preis-Level
  sl_level   numeric,
  status     text not null default 'open' check (status in ('open','closed')),
  exit       numeric,
  exit_at    timestamptz,
  grund      text,                                -- tp | sl | hand
  pl_usd     numeric,
  notiz      text,
  created_at timestamptz not null default now()
);
create index if not exists demo_orders_user_status_idx on public.demo_orders (user_id, status);

alter table public.demo_orders enable row level security;
drop policy if exists "demo_orders own" on public.demo_orders;
create policy "demo_orders own" on public.demo_orders for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
