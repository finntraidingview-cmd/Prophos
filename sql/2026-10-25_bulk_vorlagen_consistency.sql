-- Consistency Rule in die zentralen Bulk-Vorlagen (Finn 25.10.2026: „in der Schablone steht nichts drin von der
-- Consistency Rule … sollte auch noch mit rein"). Gleicher Name und Typ wie accounts.consistency_pct, damit das
-- Bulk-Hinzufügen den Wert 1:1 ans Konto weitergibt. Werte: FTMO Futures Pro 50 %, FundedNext Futures 50k Flex 40 %.
-- Idempotent.
alter table public.bulk_vorlagen add column if not exists consistency_pct numeric;

update public.bulk_vorlagen set consistency_pct = 50, updated_at = now()
where name = 'FTMO Futures 50k Pro' and consistency_pct is distinct from 50;
update public.bulk_vorlagen set consistency_pct = 40, updated_at = now()
where name = 'FundedNext Futures 50k Flex' and consistency_pct is distinct from 40;
