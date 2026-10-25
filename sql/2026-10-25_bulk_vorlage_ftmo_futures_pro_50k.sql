-- Zentrale Bulk-Vorlage FTMO Futures Pro 50k (Finn 25.10.2026, Rechnung Nacht 24./25.10.):
-- Ziel 3.000, Max DD 3.000 (EOD trailing), Daily Loss HART 1.000 (Eval + Funded: Konto weg) → Loss/Trade 1.000,
-- Konsistenz 50 % → Profit/Trade 1.500. Preis 139 $ im Monats-Abo; die Vorlage rechnet nur in €,
-- deshalb umgerechnet ~120 € (1 Monat). Firma „FTMO Futures", damit sie nicht mit der CFD-Firma „FTMO" zusammenfällt.
insert into bulk_vorlagen (name, firm, account_type, account_size, starting_balance, purchase_cost, max_drawdown,
  max_daily_drawdown, max_loss_per_trade, max_profit_per_trade, name_template, plattform, sortierung, aktiv, wd_farm)
select 'FTMO Futures 50k Pro', 'FTMO Futures', 'challenge', 50000, 50000, 120, 3000,
  1000, 1000, 1500, '50k FTMO Futures {ex}', 'Tradovate', 48, true, false
where not exists (select 1 from bulk_vorlagen where name = 'FTMO Futures 50k Pro');
