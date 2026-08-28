-- ============================================================================
-- Prophos: BNB Chain als fünfte Chain im Meta-Wallet-Tracking (28.08.2026)
--
-- id_wallets.chain war per CHECK auf arbitrum/polygon/solana/tron festgenagelt —
-- ohne dieses ALTER schlägt jeder BNB-Insert mit einem Constraint-Fehler fehl,
-- obwohl das Frontend die Chain schon anbietet. (Gleiche Mechanik wie beim
-- Polygon-Einbau am 25.08., siehe 2026-08-25_wallets_polygon.sql.)
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

alter table public.id_wallets drop constraint if exists id_wallets_chain_check;
alter table public.id_wallets add constraint id_wallets_chain_check
  check (chain in ('arbitrum','polygon','bnb','solana','tron'));
