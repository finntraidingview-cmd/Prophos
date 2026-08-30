-- ============================================================================
-- Prophos: trade_plans.master_symbol — Symbol-Override am Plan (30.08.2026)
--
-- Finns Wunsch: Das Symbol im Order-Popup soll STANDARDMÄSSIG weiter aus den
-- Firmen-Einstellungen kommen (eine Quelle, Ansage 15.08.2026) — aber es muss
-- ÜBERSCHREIBBAR sein. Konkreter Anlass: am Wochenende ist z.B. nur BTC offen,
-- und zum Testen/Bugfixen braucht der Plan dann ein anderes Symbol als das
-- Firmen-Standard-Symbol (NAS100/NDX100).
--
-- Semantik: NULL = Standard (Symbol kommt zur Laufzeit aus den Settings,
-- spätere Settings-Änderungen greifen weiter durch). Gesetzt = bewusste
-- Abweichung, gilt für Start UND Schließen dieses Plans. Geschrieben wird die
-- Spalte nur vom Order-Popup (Status-Guard eq 'planned').
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

alter table public.trade_plans add column if not exists master_symbol text;
