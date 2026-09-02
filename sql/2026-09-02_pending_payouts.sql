-- ============================================================================
-- Prophos: Ausstehende Payouts — angefragt, aber noch nicht auf dem Konto
-- (02.09.2026)
--
-- Finns Wunsch, in seinen Worten: „aktuell ist es so, dass ich keinen
-- Überblick mehr habe über die ganzen Payouts, da Pascal und so all dies
-- managt. Wir machen 50/50, aber trotzdem fehlt mir einfach der Überblick,
-- wo gerade Geld rumliegt und wo das geparkt wird. Dann müssten uns die
-- Rumänen noch Geld schicken, und da fehlt einfach die Übersicht."
--
-- Der Flow: Payout wird ANGEFRAGT → Eintrag hier (zählt NIRGENDS als Geld).
-- Erst wenn das Geld wirklich auf dem Konto ist, drückt Finn „Erhalten" —
-- dann entsteht die echte transactions-Buchung, und die Zeile hier wird auf
-- status='received' gestellt (bleibt stehen: so sieht man später, wie lange
-- ein Payout unterwegs war und bei wem er lag).
--
-- Warum eine EIGENE Tabelle statt eines status-Felds auf `transactions`:
-- Sämtliche Geld-Logik summiert transactions als realisiertes Geld —
-- finCalcCumulativeNetto/Zyklus im Frontend, rechnung_daten (Rechnungen sind
-- EINGEFROREN, für die Steuer), admin_build_overview (Payouts je Account).
-- Ein „pending"-Status dort müsste an JEDER dieser Stellen ausgefiltert
-- werden — eine vergessene Stelle und die Zahlen lügen. Getrennte Tabelle =
-- kein Kontakt zur bestehenden Wahrheit.
--
-- liegt_bei = wo das Geld gerade parkt / von wem es kommen muss
-- („Pascal", „Rumänen", „Topstep", Bank …) — Freitext, die Oberfläche macht
-- daraus die „wo liegt Geld"-Gruppierung.
--
-- RECHTE: wie `transactions` — jede Person verwaltet ihre eigenen Zeilen
-- (Payouts fragt jeder für seine Accounts an). Die Admin-Übersicht über ALLE
-- Personen läuft über app.py mit dem Service-Key (der geht an RLS vorbei),
-- wie /admin/overview es schon für accounts/transactions tut.
--
-- Im Supabase SQL Editor einfügen und auf „Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.pending_payouts (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null,
  account_id     uuid,                          -- optional, wie bei transactions
  account_name   text,
  account_firm   text,
  amount         numeric not null,              -- immer positiv (Payout = rein)
  currency       text not null default 'EUR',   -- Finanzen laufen in Euro
  liegt_bei      text,                          -- wo das Geld gerade liegt / wer schicken muss
  requested_at   date not null default current_date,
  notes          text,
  status         text not null default 'pending',  -- pending | received
  received_at    date,
  received_tx_id uuid,                          -- die transactions-Zeile aus dem Erhalten-Klick
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create index if not exists pending_payouts_user_idx
  on public.pending_payouts (user_id, status, requested_at desc);

alter table public.pending_payouts enable row level security;

drop policy if exists "users can view own pending payouts" on public.pending_payouts;
create policy "users can view own pending payouts" on public.pending_payouts
  for select to authenticated using (auth.uid() = user_id);

drop policy if exists "users can insert own pending payouts" on public.pending_payouts;
create policy "users can insert own pending payouts" on public.pending_payouts
  for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists "users can update own pending payouts" on public.pending_payouts;
create policy "users can update own pending payouts" on public.pending_payouts
  for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "users can delete own pending payouts" on public.pending_payouts;
create policy "users can delete own pending payouts" on public.pending_payouts
  for delete to authenticated using (auth.uid() = user_id);
