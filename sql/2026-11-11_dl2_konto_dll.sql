-- DL2 (11.11.2026): Tagesverlust-Limit JE KONTO — das Limit, an dem die FIRMA den Master zumacht (Soft Breach), damit der Fusion-Hedge dort mitschließt.
-- Anlass WH1: Emin, Tradeify 150k …0887 (Plan 51c33a09), WD SELL 3 MNQ ohne SL — der Master war zu, der Fusion-Hedge lag am Boden 150.100 und blieb offen
-- (WH1 vermutete ein Tradeify-DLL; Finn 21:30: Tradeify hat KEIN Daily Loss Limit). Finn 21:10: „Der Master hatte den Stop Loss als Daily Drawdown, aber das Daily Drawdown im Radar hat
-- es nicht gezählt. Der Fusion-TP war auf dem Liquidation-Level und nicht auf dem Level vom Stop Loss.“
--
-- accounts.dll_usd: > 0 = dieses Limit ab Tagesstart; 0 = ausdrücklich keins; NULL = Standard aus liq_regeln (Firma × Kontotyp, bei
-- Winning Days zuerst die WD-Zeile, hat die kein Tageslimit, die Funded-Zeile derselben Firma/Größe — Lucid funded id 17: 2.700 $).
-- Für Firmen, deren Konten unterschiedliche Tageslimits haben (eine liq_regeln-Zeile gilt für alle Konten einer Firma × Kontoart × Größe).
-- Leser: prophos.html hedgeLiqDll (Fusion-Hedge-Level am WD-Trade, ≥ 100 $ davor). max_daily_drawdown bleibt unverändert (dort steht bei Tradeify die 4.500 Max DD).
-- Einspielen nur durch den Master: DDL per apply_migration, die Konto-Zeile per execute_sql. Idempotent.

alter table public.accounts add column if not exists dll_usd numeric;
comment on column public.accounts.dll_usd is
  'DL2 11.11.2026: Tagesverlust-Limit des Kontos ab Tagesstart, an dem die Firma den Master schließt (0 = keins). NULL = Standard aus liq_regeln.';

-- Finn 11.11.2026 21:30: „Tradeify haben nie ein Daily Loss Limit, gar nichts, bei Tradeify ändert sich nichts.“ → KEIN Wert für Tradeify-Konten (auch nicht …0887).
-- Lucid: 2.700 $ überall über liq_regeln (id 17 funded, id 18 winning_days 150k). Die Spalte bleibt leer, bis eine Firma je Konto verschiedene Limits hat.

-- Kontrolle: select id, firm, account_type, dll_usd from public.accounts where dll_usd is not null;
-- Rückbau: alter table public.accounts drop column dll_usd;
