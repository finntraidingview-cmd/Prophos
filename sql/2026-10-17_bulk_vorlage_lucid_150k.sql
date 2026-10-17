-- Zentrale Bulk-Vorlage Lucid 150k Challenge (Finn 17.10.2026, Kaufpreis 222 €):
-- Regeln 1:1 wie Topstep 150k (Ziel 9.000, Max Loss 4.500, Profit/Trade 4.500 = Konsistenz 50 %),
-- einziger Unterschied: Daily Loss 2.700 → auch Loss/Trade 2.700 (wie bei den anderen Vorlagen = Daily).
-- Firmenname „Lucid Trading" wie bei den bestehenden Lucid-Konten.
insert into bulk_vorlagen (name, firm, account_type, account_size, starting_balance, purchase_cost, max_drawdown,
  max_daily_drawdown, max_loss_per_trade, max_profit_per_trade, name_template, plattform, sortierung, aktiv, wd_farm)
select 'Lucid 150k Challenge', 'Lucid Trading', 'challenge', 150000, 150000, 222, 4500,
  2700, 2700, 4500, '150k Lucid {ex}', 'Tradovate', 25, true, false
where not exists (select 1 from bulk_vorlagen where name = 'Lucid 150k Challenge');
