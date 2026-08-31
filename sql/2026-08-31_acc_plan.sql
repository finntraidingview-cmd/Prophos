-- ============================================================================
-- Prophos: Kaufplan — was soll auf welcher ID geparkt werden (31.08.2026)
--
-- Finns Wunsch, in seinen Worten: „bau ein feature wo ich als admin so acc
-- planen kann die in zukunft bei der jeweiligen id gekauft werden sollen —
-- weil aktuell mach ich das immer in google sheets etc". Ersetzt eine
-- Google-Keep-Notiz.
--
-- Der Zuschnitt hat an EINEM Tag zwei Korrekturen von Finn bekommen, und die
-- stehen hier, weil sie erklären, warum die Tabelle so schmal ist:
--   1. „Es ist nicht wirklich so ein Plan, wo ich sage: ich möchte drei
--      Accounts kaufen … ich weiß ja nicht, wenn ich zwei Accounts kaufe, ob
--      ich beide blowe."  → keine Stückzahlen, keine Kosten, kein Abhaken.
--   2. „mach das viel simpler — einfach nur id auswählen und dann prop firm
--      auswählen und dann ein notiz feld … das mit dropdown, plus etc is
--      overkill."         → drei Felder, Ende.
--
-- Was NICHT in der Tabelle steht und trotzdem angezeigt wird: der Ist-Stand.
-- Die Oberfläche zeigt neben jeder Zeile, was auf dieser ID bei dieser Firma
-- gerade liegt („2× Funded · 1× Phase 1") — gelesen aus `accounts`, archivierte
-- raus. Bewusst NICHT als Spalte hier: ein gespeicherter Stand wäre eine
-- zweite Wahrheit neben den Accounts, und die beiden würden auseinanderlaufen.
--
-- RECHTE — bewusst NICHT das geteilte Kasse-Muster (2026-08-11_kasse.sql):
--   Die Kasse teilen sich alle eingeloggten User absichtlich. Hier steht, was
--   für FREMDE IDs geplant ist — das gehört keinem Teilnehmer auf den Tisch,
--   auch nicht per API-Aufruf am UI-Gate vorbei. Deshalb: RLS an, aber GAR
--   KEINE Policy. Gelesen und geschrieben wird nur über app.py mit dem
--   Service-Key hinter dem ADMIN_EMAILS-Gate (_admin_auth, wie 2026-08-28_rechnungen.sql).
--
-- Im Supabase SQL Editor einfügen und auf „Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.acc_plan (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null,               -- die ID/Person, auf der geparkt wird
  firma       text not null default '',    -- Tradeify, Apex, Topstep …
  notiz       text not null default '',    -- „bis da ein 150k Funded steht"
  created_by  text not null default '',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists acc_plan_user_idx
  on public.acc_plan (user_id, created_at desc);

alter table public.acc_plan enable row level security;

-- Bewusst KEINE Policy. RLS ohne Policy = für jeden Client dicht; der
-- Service-Key von app.py geht daran vorbei. Falls hier je eine Policy
-- entsteht, gehört vorher die Frage beantwortet, wer den Plan sehen darf.
drop policy if exists "acc_plan_select_own" on public.acc_plan;
