-- TT6 (12.11.2026, Finn nach den Beispiel-Tagen TT5): „Die Nebentrade-Lots, so wie sie jetzt sind, immer mal 0,7.“
-- Neben-Lots = Haupt × Anteil × Streu-Würfel (neben_lots_streu, Code-Standard [0,7; 1,3], app.py WS3d). Jetzt × 0,7 → [0,49; 0,91].
-- Nur dieser eine Schlüssel in auto_plan_regeln.regeln.tagesteilung (zulässig 0,1–3,0), idempotent. Rücknahme: auf [0.7, 1.3] setzen.
update public.auto_plan_regeln
   set regeln = jsonb_set(regeln, '{tagesteilung,neben_lots_streu}', '[0.49, 0.91]'::jsonb, true), updated_at = now()
 where id = 1 and regeln->'tagesteilung'->'neben_lots_streu' is distinct from '[0.49, 0.91]'::jsonb;
