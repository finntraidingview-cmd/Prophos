-- 30.10.2026 ~03:32 Dubai (Master): Echo-Notbremse.
-- Marcs FundedNext 100k …14328075 (Plan 4d8ee602, route mt5) lief ab 03:07 ohne Fusion-Hedge (hedges {}).
-- Damit nichts weiteres ungehedgt startet, wurden alle bestätigten, noch nicht gestarteten Auto-Pläne
-- wieder auf „unbestätigt“ gesetzt (~47 Pläne). Finn bestätigt nach dem Fix im Admin → Planer neu.
-- Bereits geclaimte Pläne (Marco 26774754, Marc 200k 26800437, Ina 541478634) waren davon nicht betroffen.
-- Befund danach: The5ers/FTMO (NAS100, US100.cash) hedgen normal — offen ist nur FundedNext (NDX100, contract_size 10).
update public.trade_plans
   set auto_bestaetigt_at = null
 where status = 'planned'
   and auto_plan = true
   and auto_bestaetigt_at is not null
   and start_um_gestartet_at is null
   and started_at is null;
