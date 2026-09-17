-- ============================================================================
-- Prophos: mirror_logs — Engine-Log des Topstep-Mirrors, aus der Ferne lesbar
-- (Finn 17.09.2026: „bau mal ein Log unter Topstep Mirror ein, dass wir nachher
-- schneller in die Bugfixes kommen")
--
-- Anlass: die Pair-Konsole lebt nur im RAM des LOKALEN Backends auf dem
-- jeweiligen PC. Am 17.09.2026 liefen zwei Test-Trades auf Chriss' PC nicht
-- durch — die einzige Zeile, die den Grund nennt, stand dort und war von
-- außen nicht einsehbar; obendrein lief dort unbemerkt ein altes Backend
-- (2026-09-15.1), weil das Selbst-Update wartet, solange ein Mirror scharf ist.
--
-- Das Frontend liest /mirror/status ohnehin und schreibt den Stand hierher:
-- eine Zeile pro (User, PC, Pair) — plus eine Zeile pair_id = '_backend' mit
-- Build + Erreichbarkeit des Backends. Kein Verlauf, nur der letzte Stand
-- (Upsert) — das Log selbst trägt die letzten ~200 Zeilen.
--
-- Sicherheit: RLS, ausschließlich eigene Zeilen. Keine Token, keine Keys —
-- nur Log-Text, Positions-Map und Build-Stempel.
-- Idempotent. Danach sql/2026-09-01_backup-reader.sql erneut einspielen
-- (Hausregel: neue Tabelle → Backup-Leserecht nachziehen).
-- ============================================================================

create table if not exists public.mirror_logs (
  user_id        uuid not null references auth.users(id) on delete cascade,
  pc_id          text not null,
  pair_id        text not null,
  base           text,
  backend_build  text,
  frontend_build text,
  active         boolean,
  engine         text,
  positions      jsonb not null default '{}'::jsonb,
  log            jsonb not null default '[]'::jsonb,
  updated_at     timestamptz not null default now(),
  primary key (user_id, pc_id, pair_id)
);

alter table public.mirror_logs enable row level security;

drop policy if exists "own mirror_logs select" on public.mirror_logs;
create policy "own mirror_logs select"
  on public.mirror_logs for select using (auth.uid() = user_id);

drop policy if exists "own mirror_logs insert" on public.mirror_logs;
create policy "own mirror_logs insert"
  on public.mirror_logs for insert with check (auth.uid() = user_id);

drop policy if exists "own mirror_logs update" on public.mirror_logs;
create policy "own mirror_logs update"
  on public.mirror_logs for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own mirror_logs delete" on public.mirror_logs;
create policy "own mirror_logs delete"
  on public.mirror_logs for delete using (auth.uid() = user_id);
