-- ============================================================================
-- Prophos: Auto-Close vor Market Close (22.09.2026)
--
-- Finn: „Wenn Orders noch offen sind, sollen sie 10 Minuten vor Market Close
-- eigenständig geschlossen werden — von 23:45 Dubai-Zeit bis 00:00 (Market
-- Close) geht der Bot in einem zufälligen Intervall hin und schließt alle
-- Trades. Erst für Echo, dann Orbit; mit Frontend zum Managen und einer
-- Übersicht, welche Trades geschlossen wurden; plus Benachrichtigung."
--
-- auto_close_regeln: EINE Zeile pro Prophos-Login (Fenster, Zeitzone, Wege,
--   Intervall). Ausgeführt wird nur am PC-Tab (dort läuft der Copier); Mac und
--   Handy sehen dieselbe Regel und dasselbe Log.
-- auto_close_log: jeder Schließ-Versuch (ok/fehler + Meldung des Bots) — die
--   Übersicht im Frontend liest hier.
-- Per-User-RLS wie order_signale (Auslöse-Kanal, nie geteilt).
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.auto_close_regeln (
  user_id     uuid primary key default auth.uid(),
  aktiv       boolean not null default false,
  start_hhmm  text not null default '23:45',
  ende_hhmm   text not null default '00:00',
  tz          text not null default 'Asia/Dubai',
  routen      text[] not null default array['mt5'],      -- 'mt5' = Echo, 'tvplus' = Orbit
  min_s       integer not null default 45,               -- Zufalls-Intervall zwischen zwei Versuchen
  max_s       integer not null default 150,
  updated_at  timestamptz not null default now()
);

alter table public.auto_close_regeln enable row level security;
drop policy if exists "auto_close_regeln eigene" on public.auto_close_regeln;
create policy "auto_close_regeln eigene" on public.auto_close_regeln
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

create table if not exists public.auto_close_log (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid(),
  plan_id     text not null,
  route       text,
  master_name text,
  symbol      text,
  pc          text,
  ok          boolean not null default false,
  msg         text,
  created_at  timestamptz not null default now()
);

create index if not exists auto_close_log_user_zeit_idx on public.auto_close_log (user_id, created_at desc);

alter table public.auto_close_log enable row level security;
drop policy if exists "auto_close_log eigene" on public.auto_close_log;
create policy "auto_close_log eigene" on public.auto_close_log
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
