-- Emin (elominx@gmail.com): The5%ers-Firmeneintrag ohne Duplikum-Symbol
-- (04.09.2026, Finns Fund beim ersten The5ers-Trade von Emins PC: im
-- Order-Dialog war kein Symbol vorbefuellt, TP/SL musste er von Hand tippen).
--
-- Ursache, in der Live-DB nachgewiesen: das Symbol-Prefill hat EINE Quelle
-- (dupSymbolsForFirm -> firm_specs.dup_symbol, Finns Ansage 15.08.2026 "eine
-- Quelle, kein Fallback"). Emins firm_specs wurden am 20.07.2026 aus seiner
-- ALTEN localStorage-Liste geseedet — die hatte gar keinen The5%ers-Eintrag
-- (deshalb griff auch nie die Standardliste, die seedet nur in eine LEERE
-- Tabelle). Der The5%ers-Eintrag von heute 10:51 (beim Einrichten an Emins
-- PC angelegt) kam ohne Duplikum-Symbol. Alle 7 anderen User haben dort
-- NAS100 — deshalb ging es bei Jakob und Moritz, bei Emin nicht.
--
-- Fix: exakt der Wert, den die Standardliste und alle anderen User tragen.
-- Emins "Alpha"-Zeile (ebenfalls ohne dup_symbol, Alt-Seed) bleibt bewusst
-- unangetastet, bis dort wirklich ein Trade geplant wird.
UPDATE firm_specs
SET dup_symbol = 'NAS100'
WHERE user_id = '6cceb3f3-dc78-48ee-8668-26081da3e70f'
  AND name = 'The5%ers'
  AND (dup_symbol IS NULL OR dup_symbol = '');
