-- ============================================================================
-- Prophos: Chain-Coins zählen im Meta-Wallet mit (25.08.2026, zweiter Teil)
--
-- Neben USDT wird jetzt auch der native Coin jeder Chain getrackt (ETH auf
-- Arbitrum, POL auf Polygon, SOL, TRX) und per Binance-Kurs in USDT
-- umgerechnet. Der Snapshot speichert beides getrennt:
--   coin_amount — Coin-Menge zum Snapshot-Zeitpunkt (z.B. 0.0042 ETH)
--   coin_usdt   — ihr USDT-Wert zum damaligen Kurs (fließt in den Verlauf ein)
-- usdt behält seine Bedeutung (nur der USDT-Token). Alte Zeilen bleiben null —
-- der Verlaufs-Chart rechnet null als 0.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

alter table public.wallet_snapshots
  add column if not exists coin_amount numeric,
  add column if not exists coin_usdt   numeric;
