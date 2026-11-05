-- LUCID CONSISTENCY 40 % (Finn 05.11.2026 ~21:20 Dubai: „wir haben 40 % Consistency Rule, keine 50 %, also darf ein Trade nur 3.600 sein wie bei
-- Tradeify“). Anlass: Auto-Planer plante Lucid-150k-Challenges mit TP 4.450–4.500 (Ziel 6 % = 9.000 → 50 %); heute 5 Lucid-Trades mit +4.279…+4.823.
-- Nur Einstellung (auto_plan_regeln.regeln.firmen[lucid]), kein Code (Memory feedback-modell-ueber-einstellung).
--   150k: tp 4450–4500 / tp_max 4500  →  tp 3450–3550 / tp_max 3600   (= Tradeify 150k, 40 % von 9.000)
--   50k:  tp 1450–1500 / tp_max 1500  →  tp 1150–1180 / tp_max 1200   (40 % von 3.000)
-- Rückbau: dieselbe Abfrage mit den alten Werten (oben links).

update public.auto_plan_regeln r
   set regeln = jsonb_set(r.regeln, '{firmen}', (
         select jsonb_agg(
                  case when f->'namen' ? 'lucid' or f->'namen' ? 'lucidtrading' then
                    jsonb_set(jsonb_set(jsonb_set(jsonb_set(f,
                      '{phasen,challenge,tp}', '[3450,3550]'::jsonb),
                      '{phasen,challenge,tp_max}', '3600'::jsonb),
                      '{je_groesse,50000,phasen,challenge,tp}', '[1150,1180]'::jsonb),
                      '{je_groesse,50000,phasen,challenge,tp_max}', '1200'::jsonb)
                  else f end order by ord)
           from jsonb_array_elements(r.regeln->'firmen') with ordinality as t(f, ord))),
       updated_at = now()
 where r.id = 1;
