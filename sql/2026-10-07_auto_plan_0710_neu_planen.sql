-- Mi 07.10.2026 neu planen (Finn/Master 07.10.2026: „server-seitig genau wie Jetzt planen"). Der Nachtlauf-Claim des Tages
-- (Unique-Index auto_plan_lauf_nacht_uq: tag where quelle='nacht') wird nur umbenannt, nicht gelöscht — das Protokoll des
-- alten Laufs bleibt lesbar. Seit .1096 sieht der Nachtlauf-Thread (ap_nacht_tick) alle 10 min nach, ob der Claim noch da ist,
-- und plant den Tag dann neu — ohne Railway-Neustart: ap_planen ersetzt alle unbestätigten, nie gestarteten Auto-Vorschläge,
-- Bestätigtes und Laufendes bleibt, frühester Start jetzt + 10 min. Wiederholbar (auch für einen anderen Tag: Datum ändern).

update public.auto_plan_lauf
set quelle = 'nacht_ersetzt'
where tag = '2026-10-07' and quelle = 'nacht';
