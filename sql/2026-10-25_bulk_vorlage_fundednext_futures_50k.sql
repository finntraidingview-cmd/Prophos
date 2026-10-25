-- Zentrale Bulk-Vorlage FundedNext Futures 50k Flex (Finn 25.10.2026, Kaufpreis 74 €):
-- Profit Target 2.500, Max Loss 1.500 (EOD), kein Daily Loss → Daily = Loss/Trade = Max DD (wie bei Futures-Vorlagen
-- ohne Tageslimit). Konsistenz 40 % → Profit/Trade 1.000. Contract Limit (3 Minis / 30 Micros) hat kein Feld in der Vorlage.
-- Kontoart challenge (Futures-Evals sind Challenges, phase1/phase2 gibt es nur bei CFD).
-- Firma, Namensmuster und Präfix wie „FundedNext Futures 150k Challenge". Zuerst versehentlich als MyFundedFutures angelegt
-- (Diktat „My Funnet Future") — Zeile wird hier umbenannt, sonst neu angelegt. Idempotent.
update bulk_vorlagen
set name = 'FundedNext Futures 50k Flex', firm = 'FundedNext Futures', name_template = '50k FundedNext Futures {ex}',
    muster_praefix = 'FNFTCH', updated_at = now()
where name = 'MyFundedFutures 50k Flex'
  and not exists (select 1 from bulk_vorlagen where name = 'FundedNext Futures 50k Flex');

insert into bulk_vorlagen (name, firm, account_type, account_size, starting_balance, purchase_cost, max_drawdown,
  max_daily_drawdown, max_loss_per_trade, max_profit_per_trade, name_template, plattform, muster_praefix, sortierung, aktiv, wd_farm)
select 'FundedNext Futures 50k Flex', 'FundedNext Futures', 'challenge', 50000, 50000, 74, 1500,
  1500, 1500, 1000, '50k FundedNext Futures {ex}', 'Tradovate', 'FNFTCH', 47, true, false
where not exists (select 1 from bulk_vorlagen where name = 'FundedNext Futures 50k Flex');
