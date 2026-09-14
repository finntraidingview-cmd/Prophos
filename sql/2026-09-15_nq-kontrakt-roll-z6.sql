-- NQ-Kontrakt-Roll September → Dezember 2026 (15.09.2026, Finns Fund:
-- „Duplikum geht NQU6 nicht mehr, nur noch NQZ6").
--
-- Befund in der Live-DB: alle 36 Futures-Firmen-Zeilen (Alpha Future, Apex,
-- Lucid, Tradeify, MyFoundedFutures — 9 Logins) tragen in dup_symbol den
-- KONKRETEN Kontrakt „NQU6". Der ist seit dem Roll-Donnerstag 10.09. tot:
-- Duplikum/Broker nehmen nur noch den Dezember-Kontrakt NQZ6 an.
--
-- Ab Build 2026-09-15.274 dreht das Frontend den Monatscode beim Lesen
-- selbst auf den aktuellen Front-Monat (dupFuturesRollen → tpFuturesFrontcode,
-- Roll = 8 Tage vor dem 3. Freitag) — funktional wäre dieses UPDATE also
-- nicht mehr nötig. Es passiert trotzdem, damit die Firmen-Einstellungen im
-- Panel die WAHRHEIT zeigen (dort steht der rohe DB-Wert) und niemand „NQU6"
-- liest und für einen Fehler hält. Beim nächsten Roll (Dezember → H7) muss
-- hier niemand mehr ran; das Frontend rechnet.
--
-- Bewusst über alle Logins hinweg, nicht nur Finns — der tote Kontrakt trifft
-- jede ID gleich (Muster wie 2026-09-04_emin-the5ers-dup-symbol.sql).
-- Reversibel: replace(dup_symbol, 'NQZ6', 'NQU6').
UPDATE firm_specs
SET dup_symbol = replace(dup_symbol, 'NQU6', 'NQZ6')
WHERE dup_symbol ILIKE '%NQU6%';
