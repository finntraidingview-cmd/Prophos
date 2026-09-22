-- ============================================================================
-- Prophos: trade_plans.start_um — geplante Startzeit (22.09.2026)
--
-- Finn: „Ich plane einen Trade und kann ihm eine Uhrzeit geben, wann der Bot
-- die Order losschicken soll." Der PC-Tab (dort läuft Puls) feuert zur Zeit
-- (+ 0–60 s Zufall) exakt den Weg des „Starten"-Klicks: Duplikum-Check → Puls.
-- start_um_gestartet_at ist der Claim: nur der Tab, dessen Update von NULL auf
-- jetzt durchgeht, feuert — zwei PC-Tabs feuern nie doppelt. Mehr als 10 min
-- verspätet (Tab war zu) wird NICHT nachgefeuert, die Karte sagt „verpasst".
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================
alter table public.trade_plans
  add column if not exists start_um timestamptz,
  add column if not exists start_um_gestartet_at timestamptz;
