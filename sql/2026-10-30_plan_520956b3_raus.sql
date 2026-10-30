-- Hängender Plan des Kontos The5ers 200k …0448 (Finn 30.10.2026 14:2x: Konto temporär deaktiviert, „Authorization failed"). Plan 520956b3 ist seit 07:21 UTC geclaimt und nie gestartet: die Knöpfe
-- Löschen/Zurück greifen nicht (Guard start_um_gestartet_at is null). Raus, damit er beim Aktivieren nicht überfällig startet. Der Planer legt danach neu an.
-- Enge Bedingung: genau diese ID, geplant, nie gesendet, nie gestartet, kein Hedge am Plan (S2 zu 76497131). Trifft 1 Zeile oder 0 (dann lief inzwischen etwas — nicht weiter eingreifen).
delete from public.trade_plans
 where id = '520956b3-2318-4d0d-b7e2-2c43b7e12b1e'
   and status = 'planned' and started_at is null and orbit_gesendet_at is null
   and master_account_id = '62b824a2-b4bb-43f9-90cd-c93e995cfd49'
   and mt5_baseline->'hedge' is null
returning id, status, start_um;
