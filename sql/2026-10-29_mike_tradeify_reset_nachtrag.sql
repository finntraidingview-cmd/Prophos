-- Mike: Tradeify-Reset von gestern Nacht nachgetragen (Finn 29.10.2026 ~15:55 Dubai: „Accounts wurden schon gekauft und dann nicht zu
-- Prophos hinzugefügt"). Mail 28.10.2026 22:10Z „Your account reset is confirmed": Previous TDFYSL150697600589 → New TDFYSL150969379267.
-- Alt (273898b6) ist seit 27.10. als blown archiviert; die neue Zeile fehlte als einzige der 13 Kauf-/Reset-Mails der letzten 30 h.
-- Neue Zeile 1:1 wie die Resets von Moritz/Ina am 28.10. (Challenge 150k, DD 4.500, max Gewinn/Trade 3.600, Kauf 213 $, Kapitel 2, Auto-Planer an).
-- Idempotent über external_id. Rücknahme: Zeile mit dieser external_id archivieren (nicht löschen).
insert into public.accounts (user_id, firm, name, external_id, account_size, account_type, starting_balance, currency, balance,
  max_drawdown, max_daily_drawdown, max_loss_per_trade, max_profit_per_trade, purchase_cost, kapitel_id, auto_planer, wd_farm, duplikum_linked, goal_manual)
select '32b854d1-866f-4e7e-ba0b-9bf63df2d993', 'Tradeify', '150k TDFYSL150969379267 → Challenge', 'TDFYSL150969379267', 150000, 'challenge', 150000, 'USD', 0,
  4500, 4500, 4500, 3600, 213, 2, true, false, false, false
where not exists (select 1 from public.accounts where external_id = 'TDFYSL150969379267');
