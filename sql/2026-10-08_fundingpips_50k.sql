-- FundingPips 50k = FLEX-Konten (Finn 08.10.2026 ~07:52 Dubai, Master-Chat: „Da handelt es sich aktuell noch um die Flex-Pläne. In
-- Zukunft kommen da nur Standards.“). Werte für Flex 50k:
--   Ziel Phase 1 5.000 $ (10 %), Phase 2 5 % · Max-Verlust 6.000 $ (12 %, statisch → Boden 44.000 $) in beiden Phasen
--   SL je Trade 1.250–1.500 $ · Lots 0,5–0,7 (Lot-Schritt 0,01) · TP je Trade 2.500–3.000 $ · Puffer letzter Trade 75–100 $
--   (ersetzt Finns erste Angabe von 07:47: SL 1.250–1.750, Lots 1,25–1,75, Puffer 75/50 — das waren keine Flex-Werte)
-- Kommen später 50k-STANDARD-Konten, brauchen sie eigene Werte und eine Unterscheidung Flex/Standard am Konto (Finn fragen).
-- Setzt Code .1308 voraus (regel.je_groesse inkl. ziel_pct/dd_pct je Größe) — VORHER deployen.
-- Wiederholbar. Rückbau: je_groesse entfernen und 50000 aus groessen nehmen.

update auto_plan_regeln r
set regeln = jsonb_set(r.regeln, '{firmen}', (
      select jsonb_agg(
               case when f.elem->'namen' ? 'fundingpips' then
                 f.elem || jsonb_build_object(
                   'groessen', jsonb_build_array(50000, 100000),
                   'je_groesse', coalesce(f.elem->'je_groesse', '{}'::jsonb) || jsonb_build_object('50000', jsonb_build_object(
                     'flex', true,
                     'ziel_pct', jsonb_build_object('phase1', 10, 'phase2', 5),
                     'dd_pct', 12,
                     'phasen', jsonb_build_object(
                       'phase1', jsonb_build_object('sl', jsonb_build_array(1250, 1500), 'tp', jsonb_build_array(2500, 3000),
                                                    'menge', jsonb_build_array(0.5, 0.7), 'menge_schritt', 0.01,
                                                    'puffer', jsonb_build_array(75, 100), 'boden_pct', 12),
                       'phase2', jsonb_build_object('sl', jsonb_build_array(1250, 1500), 'tp', jsonb_build_array(2500, 3000),
                                                    'menge', jsonb_build_array(0.5, 0.7), 'menge_schritt', 0.01,
                                                    'puffer', jsonb_build_array(75, 100), 'boden_pct', 12)))))
               else f.elem end
               order by f.ord)
      from jsonb_array_elements(r.regeln->'firmen') with ordinality as f(elem, ord))),
    updated_at = now()
where r.id = 1;
