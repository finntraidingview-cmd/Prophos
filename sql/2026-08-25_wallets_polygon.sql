-- ============================================================================
-- Prophos: Polygon als vierte Chain im Meta-Wallet-Tracking (25.08.2026)
--
-- id_wallets.chain war per CHECK auf arbitrum/solana/tron festgenagelt —
-- ohne dieses ALTER schlägt jeder Polygon-Insert mit einem Constraint-Fehler
-- fehl, obwohl das Frontend die Chain schon anbietet.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

alter table public.id_wallets drop constraint if exists id_wallets_chain_check;
alter table public.id_wallets add constraint id_wallets_chain_check
  check (chain in ('arbitrum','polygon','solana','tron'));
