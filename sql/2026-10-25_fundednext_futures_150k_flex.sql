-- Vorlage „FundedNext Futures 150k Challenge" heißt jetzt „FundedNext Futures 150k Flex" (Finn 25.10.2026: beide FNF-Pläne sind
-- Flex, wie die neue 50k Flex). Nur der Name — Werte, Kontoart (challenge) und Präfix bleiben. Idempotent.
update bulk_vorlagen set name = 'FundedNext Futures 150k Flex', updated_at = now()
where name = 'FundedNext Futures 150k Challenge'
  and not exists (select 1 from bulk_vorlagen where name = 'FundedNext Futures 150k Flex');

-- Consistency 40 % wie die 50k Flex (Finn 25.10.2026; passt zu Max Profit/Trade 3.200 = 40 % von 8.000 Ziel).
update bulk_vorlagen set consistency_pct = 40, updated_at = now()
where name = 'FundedNext Futures 150k Flex' and consistency_pct is distinct from 40;
