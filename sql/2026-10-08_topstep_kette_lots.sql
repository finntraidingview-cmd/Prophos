-- TOPSTEP-KETTE LOTS (08.10.2026 ~09:00 Dubai, Finn: „kleine Änderung — für den 1. Trade 2–3, für den 2. Trade 3–4 NQ"): kette.menge gilt
-- für Trade 1 (vorher [3,4]), neu kette.t2_menge für Trade 2 (app.py ab .1322; ältere Stände nehmen für Trade 2 weiter kette.menge).
-- Wiederholbar. Rückbau: menge [3,4] setzen und t2_menge entfernen (kette - 't2_menge').
update public.auto_plan_regeln
   set regeln = jsonb_set(regeln, '{firmen}', (
         select jsonb_agg(case when f->'namen' ? 'topstep' and jsonb_typeof(f->'kette') = 'object'
                               then jsonb_set(f, '{kette}', (f->'kette') || jsonb_build_object('menge', jsonb_build_array(2, 3),
                                                                                                 't2_menge', jsonb_build_array(3, 4)))
                               else f end order by o)
           from jsonb_array_elements(regeln->'firmen') with ordinality as e(f, o))),
       updated_at = now()
 where id = 1;
-- Prüfen: select f->'kette'->'menge', f->'kette'->'t2_menge' from auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f where id = 1 and f->'namen' ? 'topstep';
