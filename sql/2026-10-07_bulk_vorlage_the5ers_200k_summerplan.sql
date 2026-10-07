-- Zentrale Bulk-Vorlage The5%ers 200k Summerplan Phase 1 (Finn 07.10.2026, Werte aus dem Bulk-Modal:
-- 200k = 100k-Regeln × 2 laut .claude/autoplaner-regeln.md; Kaufpreis 250 €)
insert into bulk_vorlagen (name, firm, account_type, account_size, starting_balance, purchase_cost, max_drawdown,
  max_daily_drawdown, max_loss_per_trade, max_profit_per_trade, name_template, plattform, sortierung, aktiv, wd_farm)
select 'The5ers 200k Summerplan Phase 1', 'The5%ers', 'phase1', 200000, 200000, 250, 20000,
  6000, 6000, 16000, '200k Summerplan The5er´s {ex}', 'MT5', 44, true, false
where not exists (select 1 from bulk_vorlagen where name = 'The5ers 200k Summerplan Phase 1');
