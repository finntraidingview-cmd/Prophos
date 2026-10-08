-- FUNDINGPIPS STANDARD: SL je Trade 2.000–2.500 $ statt 2.500–3.500 $ (08.10.2026, Finn: „stopp nein sl max 2000-2500")
-- Gilt für beide Phasen des Standard-Blocks (firmen[fundingpips].phasen.phase1/phase2.sl, 100k Standard). Flex (flex.je_groesse)
-- bleibt unberührt. Wiederholbar. Rückbau: sl wieder [2500,3500].
update public.auto_plan_regeln r
   set regeln = jsonb_set(r.regeln, '{firmen}', (
         select jsonb_agg(
                  case when f::text ilike '%fundingpips%' and f ? 'phasen'
                       then jsonb_set(jsonb_set(f, '{phasen,phase1,sl}', '[2000,2500]'::jsonb), '{phasen,phase2,sl}', '[2000,2500]'::jsonb)
                       else f end
                  order by o)
           from jsonb_array_elements(r.regeln->'firmen') with ordinality as x(f, o)))
 where r.id = 1;
-- Prüfen: select f->'phasen'->'phase1'->'sl', f->'phasen'->'phase2'->'sl' from auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f where f::text ilike '%fundingpips%';
