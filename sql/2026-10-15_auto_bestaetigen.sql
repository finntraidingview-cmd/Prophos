-- 15.10.2026 (Finn am Screenshot „Zu bestätigen · 0 / Braucht dich 10": „Dann muss der Bot den Trade zu bestätigen packen. Das muss ich
-- nicht immer machen. Das ist ein Knopf, den man drücken muss. Das kann auch der Bot machen."): Schalter für app.py ap_auto_best_tick —
-- alle 2 min bestätigt Railway jeden Auto-Vorschlag (planned, auto_plan, unbestätigt, keine Puls-Pause), dessen Konto-Balance live ist
-- (ap_balance_live, derselbe Riegel wie der ✓-Knopf). Aus = alles wie bisher (nur Hand). Rückweg: denselben Schlüssel auf false setzen.
update auto_plan_regeln
   set regeln = coalesce(regeln, '{}'::jsonb) || '{"auto_bestaetigen": true}'::jsonb
 where id = 1;
