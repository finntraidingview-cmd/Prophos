-- ============================================================================
-- Prophos: trade_plans.richtung — Buy/Sell wird Teil des Plans (28.08.2026)
--
-- Finns Jetzt-starten-Flow: TP ($), SL (= Risiko Master $) und Lots (Anzahl
-- Kontrakte) stehen längst am Plan — mit der Richtung ist die Order damit
-- KOMPLETT beim Planen erfasst. Die Plan-Karte bekommt dafür „Jetzt starten":
-- lokal startet das direkt den Trade-Start-Check, am Handy/Mac geht das
-- Signal über order_signale an den PC und Puls platziert. Das bisherige
-- Order-Popup (Weiter → Richtung/TP/SL eintippen) bleibt als zweiter Weg.
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

alter table public.trade_plans add column if not exists richtung text;
