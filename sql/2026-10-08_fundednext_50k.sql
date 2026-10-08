-- FundedNext 50k mit eigenen Planer-Werten (Finn 08.10.2026 ~08:00 Dubai, Master-Chat):
--   Ziel Phase 1 8 % (4.000 $), Phase 2 5 % (2.500 $) · Max-Verlust 10 % in beiden Phasen (Boden 45.000 $) — wie die Firma
--   SL je Trade 2,25–2,75 % von 50k = 1.125–1.375 $ (beide Phasen)
--   TP je Trade Phase 1 3.500–4.500 $, Phase 2 2.000–2.250 $
--   Lots 1–1,5 und Puffer 50 $ — von Finn bei Phase 2 genannt („Phase 2: genau gleich“), für beide Phasen übernommen
-- Setzt Code .1308 voraus (regel.je_groesse, live seit 08.10.2026 03:51 UTC). Kontowert 50k: kauf_eur {"50000": 261} war schon da.
-- Wiederholbar. Rückbau: je_groesse."50000" entfernen und 50000 aus groessen nehmen.

update auto_plan_regeln r
set regeln = jsonb_set(r.regeln, '{firmen}', (
      select jsonb_agg(
               case when f.elem->'namen' ? 'fundednext' then
                 f.elem || jsonb_build_object(
                   'groessen', jsonb_build_array(50000, 100000),
                   'je_groesse', coalesce(f.elem->'je_groesse', '{}'::jsonb) || jsonb_build_object('50000', jsonb_build_object(
                     'phasen', jsonb_build_object(
                       'phase1', jsonb_build_object('sl', jsonb_build_array(1125, 1375), 'tp', jsonb_build_array(3500, 4500),
                                                    'menge', jsonb_build_array(1, 1.5), 'menge_schritt', 0.1,
                                                    'puffer', jsonb_build_array(50, 50), 'boden_pct', 10),
                       'phase2', jsonb_build_object('sl', jsonb_build_array(1125, 1375), 'tp', jsonb_build_array(2000, 2250),
                                                    'menge', jsonb_build_array(1, 1.5), 'menge_schritt', 0.1,
                                                    'puffer', jsonb_build_array(50, 50), 'boden_pct', 10)))))
               else f.elem end
               order by f.ord)
      from jsonb_array_elements(r.regeln->'firmen') with ordinality as f(elem, ord))),
    updated_at = now()
where r.id = 1;
