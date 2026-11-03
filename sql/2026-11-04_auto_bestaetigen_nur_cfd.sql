-- AUTO-BESTÄTIGEN NUR CFD-CHALLENGES (A1, Finn 04.11.2026 ~00:20 Dubai über den Master: „Ja für CFD-Challenge" — Futures-Challenges bleiben von Hand bestätigt).
-- Schalter auto_plan_regeln.regeln.auto_bestaetigen: true = alle Auto-Pläne (wie seit sql/2026-10-15_auto_bestaetigen.sql), "cfd" = nur Pläne auf CFD-Challenges
-- (Kontoart challenge/phase1/phase2, Weg Echo/Echo V2, Minis „Tage sammeln" eingeschlossen), alles andere = aus. Code: app.py ap_auto_best_umfang /
-- ap_auto_best_cfd / ap_auto_best_kandidaten(umfang) — der Takt ap_auto_best_tick bestätigt alle 2 min mit demselben Riegel wie der ✓-Knopf (Balance live,
-- Balance-Wache, Puls-Pause, Planer-Haken). Emins Gruppe nie (nicht in user_ids; ap_planen bestätigt Gruppen nie — Finn 30.10.2026).
-- Beendet für CFD-Challenges die „Testphase alles von Hand" (29.10.2026) — auf Finns Wort vom 04.11.2026.
-- REIHENFOLGE: erst Code pushen (der alte Code liest nur ein echtes true und ließe "cfd" als aus liegen — ungefährlich, aber erst mit Code wirksam), dann diese Datei.
-- Wiederholbar. Rückbau: update public.auto_plan_regeln set regeln = jsonb_set(regeln, '{auto_bestaetigen}', 'false'::jsonb) where id = 1;
-- NICHT vom Slave eingespielt.

update public.auto_plan_regeln
   set regeln = jsonb_set(coalesce(regeln, '{}'::jsonb), '{auto_bestaetigen}', '"cfd"'::jsonb)
 where id = 1
   and coalesce(regeln->'auto_bestaetigen', 'null'::jsonb) is distinct from '"cfd"'::jsonb;
