-- Finn 25.11.2026: Lucid Trading 150k kostet nur noch 200 € — Schablone „Lucid 150k Challenge" anpassen (vorher 222 €). Idempotent.
update public.bulk_vorlagen set purchase_cost = 200
 where id = '6599b688-9e9f-49ef-88d4-c7ad40f27b35' and firm ilike 'lucid%' and purchase_cost = 222;
