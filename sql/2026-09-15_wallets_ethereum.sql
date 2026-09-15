-- ============================================================================
-- Prophos: Ethereum Mainnet als sechste Chain im Meta-Wallet-Tracking (15.09.2026)
--
-- id_wallets.chain war per CHECK auf arbitrum/polygon/bnb/solana/tron festgenagelt —
-- ohne dieses ALTER schlägt jeder Ethereum-Insert mit einem Constraint-Fehler fehl,
-- obwohl das Frontend die Chain schon anbietet. (Gleiche Mechanik wie beim
-- BNB-Einbau am 28.08., siehe 2026-08-28_wallets_bnb.sql.)
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

alter table public.id_wallets drop constraint if exists id_wallets_chain_check;
alter table public.id_wallets add constraint id_wallets_chain_check
  check (chain in ('ethereum','arbitrum','polygon','bnb','solana','tron'));
