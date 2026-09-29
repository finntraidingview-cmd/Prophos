-- MT5-Balance dauerhaft am Konto (29.09.2026, Finn: unter Accounts stand bei den MT5-Konten — The5ers bei „Finn + Pascal" — nur „–").
-- Die Master-Balance kam bisher nur live aus mt5_live (Copier bzw. Lese-EA im Master-Terminal); war das Terminal zu, war sie weg.
-- Das Frontend (PC-Tab) schreibt jede frische Master-Balance jetzt in accounts.tv_balance/tv_equity/tv_balance_at — mit
-- tv_balance_quelle 'mt5'. Ohne diese Erweiterung schreibt es ohne Quelle (null); die Anzeige erkennt MT5 dann am Nicht-Futures-Konto.
-- Nur die Check-Liste wird erweitert, keine Daten angefasst.
alter table public.accounts drop constraint if exists accounts_tv_balance_quelle_check;
alter table public.accounts add constraint accounts_tv_balance_quelle_check
  check (tv_balance_quelle is null or tv_balance_quelle in ('puls', 'dashboard', 'mt5'));
