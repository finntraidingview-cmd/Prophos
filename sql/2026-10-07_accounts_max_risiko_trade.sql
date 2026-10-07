-- Max Risiko je Trade (Finn 07.10.2026): manche Funded-Konten haben eine 1-%-Regel — nie mehr als X $ pro Trade riskieren.
-- Eigene Spalte statt max_loss_per_trade: die ist über das Bulk-Add bei ~260 Konten mit den Firmen-Limits befüllt
-- (2000/4000/4500 …) und taugt deshalb nicht als Markierung. max_risiko_trade ist nur gesetzt, wo Finn den Wert bewusst
-- einträgt (Konto-Popup) — genau diese Konten bekommen in der Accounts-Liste den Chip „⚠ max X $/Trade". Wert in Dollar.

alter table public.accounts add column if not exists max_risiko_trade numeric;

do $$ begin
  alter table public.accounts add constraint accounts_max_risiko_trade_positiv
    check (max_risiko_trade is null or max_risiko_trade > 0);
exception when duplicate_object then null; end $$;

-- Prüfen:
-- select firm, name, account_type, max_risiko_trade from public.accounts where max_risiko_trade is not null;
