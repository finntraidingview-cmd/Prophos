-- AB1b (23.11.2026 ~03:25 Dubai): Finn + Pascal Tradeify WD 150k …0431 ist nach AB1 geblowt + archiviert
-- (sql/2026-11-23_ab1_radar_abhaken.sql). Für das Konto stand heute 10:37 Dubai noch der Recovery-WD-Plan 55265b81 —
-- das Archivieren löscht ihn nicht. Bliebe er, würde Puls um 10:37 ein geblowtes Konto anfahren → wieder eine gelbe
-- „nie gestartet“-Zeile im Radar (genau das, was Finn heute nicht mehr sehen will). Plan sichern, dann raus. Idempotent.
create table if not exists public.ab1b_plan_geblowt_20261123 as
  select * from public.trade_plans where id::text like '55265b81%' and status = 'planned';
delete from public.trade_plans
 where id in (select id from public.ab1b_plan_geblowt_20261123) and status = 'planned' and started_at is null;
