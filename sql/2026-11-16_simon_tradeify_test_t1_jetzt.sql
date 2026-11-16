-- Simons Tradeify-Test (Finn 16.11.2026 ~05:37 Dubai: „Kannst du diesen Trade so machen wie vorher … wie den ersten Trade“):
-- Vorschlag ec15d9e0 (150k FTDFYSLX150373284577, Pump-Weg „zwei“, Trade 1: TP 7.478 $, SL 4.692 $, Hedge 850 €, Ziel 167.194 $)
-- wie „Bestätigen“ (_fdp_eingriff: start_um + auto_bestaetigt_at), Start in ~3 min statt der vorgeschlagenen 13:34 Dubai (Fenster T1 03:00–15:00 Dubai).
update public.trade_plans
   set start_um = now() + interval '3 minutes', auto_bestaetigt_at = now()
 where id = 'ec15d9e0-4d1a-4f23-8404-1465ad9e3723'
   and status = 'planned' and start_um is null and started_at is null and start_um_gestartet_at is null;
