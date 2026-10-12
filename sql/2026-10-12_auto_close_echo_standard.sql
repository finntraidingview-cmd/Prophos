-- ============================================================================
-- Prophos: Auto-Close für Echo wird Standard (12.10.2026, .1476)
--
-- Finn: „Sollten noch Echo-Trades offen sein zwischen 23:30 und 23:50 Uhr
-- Dubai-Zeit, geht der Echo-Bot und schließt automatisch alle offenen Trades."
-- Befund: auto_close_regeln war seit 22.09. leer (0 Zeilen, 0 Log-Einträge) —
-- die Regel war Opt-in und damit bei allen 13 Logins faktisch aus.
-- Das Frontend (.1476) nimmt ohne Zeile jetzt den Standard Echo 23:30–23:50
-- Dubai; hier ziehen die Tabellen-Defaults nach, damit eine später gespeicherte
-- Zeile denselben Stand hat. Orbit bleibt Opt-in. Idempotent, keine Datenänderung.
-- ============================================================================
alter table public.auto_close_regeln alter column aktiv      set default true;
alter table public.auto_close_regeln alter column start_hhmm set default '23:30';
alter table public.auto_close_regeln alter column ende_hhmm  set default '23:50';
