-- Testphase „alles von Hand" (Finn 29.10.2026 ~23:00 Dubai: „für die nächsten Tage … dass gar kein Trade automatisch bestätigt wird, dass
-- sich alle Trades abhaken, bevor sie verschwinden, weil wir etwas Neues testen und komplett sehen wollen, was passiert … dass ich alles
-- manuell bestätigen muss"). Vorher: auto_bestaetigen true (Railway bestätigt Planer-Vorschläge selbst), abhaken_auto_normal true,
-- abhaken_auto_blow false. Jetzt alle drei false. Rücknahme: auto_bestaetigen + abhaken_auto_normal wieder true.
update public.auto_plan_regeln
   set regeln = regeln || '{"auto_bestaetigen": false, "abhaken_auto_normal": false, "abhaken_auto_blow": false}'::jsonb,
       updated_at = now()
 where id = 1;
