-- The5ers: Puffer des letzten Trades 55–75 $ (Finn 12.10.2026: „für The5ers maximal 55 bis 75 Puffer"; vorher 50–75).
-- Gilt zusammen mit .1449: der Planer nimmt wieder den Firmen-Puffer statt 10 Pkt × Lots × $/Pkt.
update public.auto_plan_regeln
   set regeln = jsonb_set(regeln, '{firmen}', (
         select jsonb_agg(case when f->'namen' ? 'the5ers'
                               then jsonb_set(jsonb_set(f, '{phasen,phase1,puffer}', '[55,75]'), '{phasen,phase2,puffer}', '[55,75]')
                               else f end order by i)
           from jsonb_array_elements(regeln->'firmen') with ordinality t(f, i)))
 where id = 1;
