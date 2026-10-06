-- Mi 07.10.2026 neu planen (Finn/Master 07.10.2026: „server-seitig genau wie Jetzt planen", nach Startfenster 16:30 +
-- Klumpen-Regel). Der Nachtlauf-Claim des 07.10. (Unique-Index auto_plan_lauf_nacht_uq: tag where quelle='nacht') wird nur
-- umbenannt, nicht gelöscht — das Protokoll des ersten Laufs bleibt lesbar. Danach holt der Nachtlauf-Thread (ap_nacht_tick)
-- den 07.10. beim ersten Takt der neu gestarteten Railway-Instanz nach: ap_planen ersetzt alle unbestätigten, nie gestarteten
-- Auto-Vorschläge, Bestätigtes und Laufendes bleibt, frühester Start jetzt + 10 min.
-- Einspielen NACH dem Push und VOR dem Start der neuen Instanz (alte Instanzen haben den Tag im Speicher als erledigt).

update public.auto_plan_lauf
set quelle = 'nacht_ersetzt'
where tag = '2026-10-07' and quelle = 'nacht';
