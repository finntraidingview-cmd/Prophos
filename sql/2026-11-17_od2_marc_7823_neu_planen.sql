-- OD2-Folge (Finn 17.11.2026 ~04:30 Dubai: „ja ändern“): Plan 0697a418 für Marcs FundedNext 100k …7823 On Demand (302d652e) stammt aus dem
-- Funded-CFD-Nachtlauf 01:30 Dubai, also VOR OD2 (live 03:30, 53f3b07e). TP 3.967 $ bei Start 15:50 Dubai — nach OD2 Fall A erlaubt der Tagesdeckel
-- nur ~968 $ (0,95 × größter Tag 1.019,10). Gewinnt der alte Plan, würde 3.967 $ der neue größte Tag → Required profit 9.917,50 $ (Marcs …7821-Fehler).
-- Nie gestarteten Plan löschen; der Funded-CFD-Takt plant das Konto mit OD2 neu (Handels-Würfel heute 0,5 < 85, Firmen-Würfel 27,1 < 90 → handelt).
-- Guard: nur planned, ungestartet, nicht gesendet, nicht geclaimt.

delete from public.trade_plans
 where id = '0697a418-db38-4b09-99c8-948cecd6366e'
   and status = 'planned' and started_at is null and orbit_gesendet_at is null and start_claim_art is null and start_um_gestartet_at is null
returning id, master_name, master_tp;
