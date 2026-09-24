-- 2026-09-25 · Minutenkerzen nur noch 26 Stunden aufbewahren
--
-- Finn: „alle 24 h löschen". Der Markt-Chart zeigt höchstens 24 h; 26 h halten den Ausschnitt am Rand vollständig.
-- Die laufende Räumung macht ab .575 die Kurs-Brücke (epBrueckeTick, stündlich, vorher 14 Tage).
-- Diese Einmal-Bereinigung räumt, was davor liegt.
-- Stand beim Anwenden (25.09.2026): 0 Zeilen betroffen — 1.409 Zeilen, älteste 24.09. 07:20 UTC, 440 kB.

delete from public.tv_kurs_1m where minute < now() - interval '26 hours';
