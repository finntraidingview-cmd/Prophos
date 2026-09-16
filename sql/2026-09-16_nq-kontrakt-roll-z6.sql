-- NQ-Kontrakt wieder auf den Dezember-Kontrakt NQZ6 (16.09.2026, Finn:
-- „bitte wieder zu NQZ ändern alles").
--
-- Dritter Wechsel in zwei Tagen, deshalb die Historie:
--   15.09. früh   2026-09-15_nq-kontrakt-roll-z6.sql          NQU6 → NQZ6 (Build .274)
--   15.09. abends 2026-09-15_nq-kontrakt-roll-zurueck-u6.sql  NQZ6 → NQU6 (Build .280,
--                 „war ein Fehler, ist noch NQU")
--   16.09.        diese Datei                                  NQU6 → NQZ6 (Build .292)
--
-- Funktional entscheidet seit .274 nicht mehr der DB-Wert, sondern
-- tpFuturesFrontcode (dupFuturesRollen dreht den Monatscode beim Lesen) —
-- das UPDATE sorgt nur dafür, dass das Einstellungs-Panel den rohen Wert
-- zeigt, der auch gepusht wird. Alle Futures-Firmen, alle Logins (36 Zeilen).
-- Reversibel: replace(dup_symbol, 'NQZ6', 'NQU6').
UPDATE firm_specs
SET dup_symbol = replace(dup_symbol, 'NQU6', 'NQZ6')
WHERE dup_symbol ILIKE '%NQU6%';
