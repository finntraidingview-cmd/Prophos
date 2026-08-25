-- ============================================================================
-- Prophos: RLS für transactions_backup_elominx_20260816 nachziehen
--
-- Anlass (25.08.2026): Supabase-Security-Advisor hatte gewarnt — die Backup-
-- Tabelle vom 16.08. wurde ohne RLS angelegt. Folge: Jeder mit dem Anon-Key
-- (steht öffentlich im Frontend auf pages.dev) konnte alle 508 Zeilen lesen,
-- ändern und löschen. Live von außen verifiziert (HTTP 200 ohne Login).
--
-- RLS an, KEINE Policies: von außen (anon/authenticated) ist die Tabelle damit
-- komplett zu. Dashboard und service_role kommen weiter ran. Kein Code liest
-- diese Tabelle (geprüft: prophos.html, app.py, ai_advisor.py — 0 Treffer).
--
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

alter table public.transactions_backup_elominx_20260816 enable row level security;
