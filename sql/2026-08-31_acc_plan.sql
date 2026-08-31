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
-- RECHTE — in zwei Schritten entstanden, und der zweite dreht den ersten um:
--   Zuerst war die Tabelle komplett dicht (RLS an, keine Policy), weil hier
--   steht, was für FREMDE IDs geplant ist. Dann Finn: „mach das es bei der
--   jeweiligen person dann auch angezeigt wird im dashboard seine trade todoo
--   + das er sie abhaken kann." Also darf die Person jetzt ihre EIGENEN Zeilen
--   sehen — und daran ausschließlich den Haken setzen.
--   Dafür braucht es ZWEI Mechanismen, und der zweite wird leicht übersehen:
--     * RLS-Policy    → welche ZEILEN  (nur die eigenen)
--     * Spalten-Grant → welche SPALTEN (nur erledigt + erledigt_am)
--   Eine Policy allein würde reichen, um die eigene Zeile komplett
--   umzuschreiben — auch firma und notiz.
--   Anlegen und Löschen bleibt beim Admin über app.py mit dem Service-Key
--   hinter dem ADMIN_EMAILS-Gate (_admin_auth, wie 2026-08-28_rechnungen.sql).
--
-- Im Supabase SQL Editor einfügen und auf „Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.acc_plan (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null,               -- die ID/Person, auf der geparkt wird
  firma       text not null default '',    -- Tradeify, Apex, Topstep …
  notiz       text not null default '',    -- „bis da ein 150k Funded steht"
  erledigt    boolean not null default false,
  erledigt_am timestamptz,
  created_by  text not null default '',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists acc_plan_user_idx
  on public.acc_plan (user_id, created_at desc);

alter table public.acc_plan enable row level security;

-- Anlegen/Löschen/Umschreiben bleibt dem Service-Key vorbehalten; der geht
-- an RLS und Grants ohnehin vorbei.
revoke insert, delete, update on public.acc_plan from authenticated;
grant select on public.acc_plan to authenticated;
grant update (erledigt, erledigt_am) on public.acc_plan to authenticated;

drop policy if exists "acc_plan_select_own" on public.acc_plan;
create policy "acc_plan_select_own" on public.acc_plan
  for select to authenticated
  using (user_id = auth.uid());

drop policy if exists "acc_plan_haken_own" on public.acc_plan;
create policy "acc_plan_haken_own" on public.acc_plan
  for update to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());
