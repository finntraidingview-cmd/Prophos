-- ============================================================================
-- Prophos: Wallet-Zweck-Vorlagen — jede in ihrer eigenen Farbe (20.09.2026)
--
-- Finn 20.09.2026: „mach die Zwecke alle in einer anderen Farbe, nicht alles rot".
-- Mit den vier Tokens von 18.09. (violet/good/danger/sub) standen Fusion Deposit
-- und Account Kauf beide auf danger. Der Check bekommt drei weitere Tokens, die
-- es im Design-System (:root in prophos.html) längst gibt: blue, teal, warn.
-- Das Frontend kennt sie ab VERSION 2026-09-20.310; ein älterer Tab zeigt einen
-- unbekannten Wert grau (Fallback sub), es bricht nichts.
--
-- Läuft NACH sql/2026-09-20_wallet_tx_kategorien_vier.sql.
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

alter table public.wallet_tx_kategorien drop constraint if exists wallet_tx_kategorien_farbe_check;
alter table public.wallet_tx_kategorien add constraint wallet_tx_kategorien_farbe_check
  check (farbe in ('violet','good','danger','sub','blue','teal','warn'));

update public.wallet_tx_kategorien set farbe = 'blue'   where name = 'Fusion Deposit';
update public.wallet_tx_kategorien set farbe = 'good'   where name = 'Payout';
update public.wallet_tx_kategorien set farbe = 'warn'   where name = 'Account Kauf';
update public.wallet_tx_kategorien set farbe = 'violet' where name = 'Interner Transfer';
