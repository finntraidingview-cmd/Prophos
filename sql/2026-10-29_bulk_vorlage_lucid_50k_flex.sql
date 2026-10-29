-- Zentrale Bulk-Vorlage Lucid 50k Flex (Finn 29.10.2026, Screenshot „50K FLEX EVAL", Kaufpreis 81 €; Seite zeigt 90,30 $
-- mit Gutschein): Profit Target 3.000, Max Loss 2.000 (EOD), Daily Loss 1.200 (an) → auch Loss/Trade 1.200 (wie bei den
-- anderen Vorlagen = Daily). Konsistenz 50 % → Profit/Trade 1.500. Max Size (4 Minis / 40 Micros) hat kein Feld in der Vorlage.
-- Kontoart challenge (Futures-Evals sind Challenges, phase1/phase2 gibt es nur bei CFD). Firma und Namensmuster wie
-- „Lucid 150k Challenge". Idempotent.
insert into bulk_vorlagen (name, firm, account_type, account_size, starting_balance, purchase_cost, max_drawdown,
  max_daily_drawdown, max_loss_per_trade, max_profit_per_trade, consistency_pct, name_template, plattform, sortierung, aktiv, wd_farm)
select 'Lucid 50k Flex', 'Lucid Trading', 'challenge', 50000, 50000, 81, 2000,
  1200, 1200, 1500, 50, '50k Lucid {ex}', 'Tradovate', 26, true, false
where not exists (select 1 from bulk_vorlagen where name = 'Lucid 50k Flex');
