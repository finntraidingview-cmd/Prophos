-- 2026-09-27: Herkunft der TradingView-Balance (Auftrag Koordination B10 / F11). accounts.tv_balance kommt jetzt aus zwei
-- Wegen: 'puls' (Puls liest die Account Balance beim Platzieren/Nachlesen) und 'dashboard' (Finn fügt den Text des
-- Tradeify-Dashboards ein, F11). null = unbekannt/alt. Keine Rückfüllung. app.py schreibt tv_balance nirgends selbst
-- (Stand 27.09.2026 — geschrieben wird nur aus dem Frontend), setzt die Spalte also auch nicht.
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
alter table public.accounts add column if not exists tv_balance_quelle text;
alter table public.accounts drop constraint if exists accounts_tv_balance_quelle_check;
alter table public.accounts add constraint accounts_tv_balance_quelle_check
  check (tv_balance_quelle is null or tv_balance_quelle in ('puls', 'dashboard'));
