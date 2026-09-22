-- ============================================================================
-- Prophos: trade_plans.orbit_gesendet_at — „Warte auf Duplikum" (22.09.2026)
--
-- Finn: „Wenn Puls die Order platziert hat, wird der Trade erst zu offen
-- verschoben, wenn er von Duplikum erkannt wird. Auf der Karte soll dann statt
-- ‚Starten' ‚Warte auf Duplikum' stehen — sobald Duplikum es sieht, wird es
-- automatisch zu live verschoben."
--
-- Puls stempelt hier den Zeitpunkt des Kauf-Klicks (nur solange status =
-- 'planned'). Die Karte zeigt danach „⏳ Warte auf Duplikum…" statt „Starten";
-- die Duplikum-Auto-Erkennung setzt den Plan wie gewohnt auf 'open'. Nach
-- 10 Minuten ohne Erkennung zeigt die Karte wieder „Starten" (die Order kam
-- dann nicht an — oder Duplikum sieht sie nicht; beides muss Finn sehen).
-- Eine Spalte statt localStorage, damit Mac, Handy und PC dasselbe zeigen.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================
alter table public.trade_plans
  add column if not exists orbit_gesendet_at timestamptz;
