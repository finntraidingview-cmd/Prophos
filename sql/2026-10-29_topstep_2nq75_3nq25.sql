-- Topstep 2–3 NQ, nie 4 (Finn 29.10.2026 ~14:45 Dubai: „immer 2–3, nie wieder 4, zu 75 % immer 2 und zu 25 % [3], egal welcher Stil").
-- Ersetzt 2026-10-29_topstep_immer_2nq.sql ([2,2]). Der Challenge-Planer würfelt die Menge gleichverteilt aus [von, bis] und rundet
-- (app.py _ap_spanne + _ap_runden): [2, 2.6667] ergibt 3 nur, wenn 2 + 0,6667·u > 2,5 → u > 0,75 → 25 % 3 NQ, 75 % 2 NQ.
-- Gilt für Challenge, Kette Trade 1 (menge) und Kette Trade 2 (t2_menge, vorher 3–4). Rücknahme: [2,3] / [2,3] / [3,4].
update public.auto_plan_regeln r
set regeln = jsonb_set(r.regeln, '{firmen}', (
      select jsonb_agg(
               case when f->'namen' ? 'topstep' then
                 jsonb_set(jsonb_set(jsonb_set(f,
                   '{phasen,challenge,menge}', '[2,2.6667]'::jsonb),
                   '{kette,menge}', '[2,2.6667]'::jsonb),
                   '{kette,t2_menge}', '[2,2.6667]'::jsonb)
               else f end order by i)
      from jsonb_array_elements(r.regeln->'firmen') with ordinality t(f, i))),
    updated_at = now()
where r.id = 1;
