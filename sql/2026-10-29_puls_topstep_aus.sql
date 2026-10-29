-- Puls für Topstep AUS (Finn 29.10.2026 ~14:05 Dubai: „bevor wir einen weiteren Topstep-Trade starten, erstmal gucken, dass nicht der
-- Fehler wieder auftritt"). Vorfall Simon …89059002 (Plan 523545ee): Brackets (Risk/To Make) nach dem Fill nicht gesetzt, Position lief
-- 8 h ohne SL/TP, Prophos beendete per Kurs-Schätzung. Bis der Fix (S5 Bot-Retry + Rücklesung, S4 nie Schätz-Ende ohne Brackets) live
-- und bewiesen ist, startet Puls keine Topstep-Order. Rücknahme: puls_topstep = 'scharf'.
update public.wd_farmer_regeln set puls_topstep = 'aus' where id = 1;
