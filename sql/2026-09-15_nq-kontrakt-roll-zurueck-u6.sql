-- Rückdrehung des NQ-Rolls vom selben Tag (15.09.2026 abends, Finn: „Symbol-
-- Mapping bitte wieder zurück auf MNQU6 und NQU6 — war ein Fehler, ist noch
-- NQU"). Die Migration 2026-09-15_nq-kontrakt-roll-z6.sql hatte alle 36
-- Futures-Firmen-Zeilen (Alpha Future, Apex, Lucid, Tradeify, MyFoundedFutures,
-- 9 Logins) von NQU6 auf NQZ6 gedreht, weil Duplikum angeblich NQU6 nicht mehr
-- annahm. Stimmte nicht: Duplikum läuft weiter auf dem September-Kontrakt.
-- Exakt die dort notierte Umkehr; MNQZ6 → MNQU6 läuft über denselben replace.
-- Der Frontend-Schalter (tpFuturesFrontcode) steht ab Build .280 wieder auf
-- dem Verfallstag (3. Freitag = 18.09.2026), dann wird aus U6 regulär Z6.
UPDATE firm_specs
SET dup_symbol = replace(dup_symbol, 'NQZ6', 'NQU6')
WHERE dup_symbol ILIKE '%NQZ6%';
