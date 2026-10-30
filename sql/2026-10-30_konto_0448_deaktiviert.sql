-- The5ers 200k …0448 deaktiviert (Finn 30.10.2026 14:2x: The5ers lässt nur einen 200k-Account gleichzeitig zu, Konto temporär aus). Aktivieren per Knopf in Accounts.
-- Reihenfolge: erst sql/2026-10-30_konto_deaktiviert.sql, dann dies, dann sql/2026-10-30_plan_520956b3_raus.sql.
update public.accounts set deaktiviert_at = now()
 where id = '62b824a2-b4bb-43f9-90cd-c93e995cfd49' and external_id = '26710448' and deaktiviert_at is null;
