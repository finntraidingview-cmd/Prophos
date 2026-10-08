-- FUNDINGPIPS 100k FLEX (08.10.2026, Finn über Master: „Jacob …733 ist Flex" — Flex soll wie Flex laufen; bis hier ließ der Planer das
-- 100k-Flex-Konto mit „FundingPips 100k Flex: Werte fehlen" aus, sql/2026-10-08_fundingpips_flex_standard.sql). Werte prozentual gleich
-- den 50k-Flex-Werten (× 2): Ziel P1 10 % / P2 5 %, Max-Verlust 12 % (Boden), SL 2.500–3.000 $, TP P1 5.000–6.000 / P2 2.000–2.500 $,
-- Lots 1,0–1,4 (Schritt 0,01 wie 50k), Puffer 75–100 $ absolut (wie 50k). Nur Regel, kein Code (app.py ap_regel_flex liest
-- flex.je_groesse je Größe). Wiederholbar (überschreibt den 100k-Block). Rückbau: flex.je_groesse - '100000'.
update public.auto_plan_regeln
   set regeln = jsonb_set(regeln, '{firmen}', (
         select jsonb_agg(case when f->'namen' ? 'fundingpips' and jsonb_typeof(f->'flex') = 'object'
                               then jsonb_set(f, '{flex,je_groesse,100000}', jsonb_build_object(
                                      'dd_pct', 12,
                                      'ziel_pct', jsonb_build_object('phase1', 10, 'phase2', 5),
                                      'phasen', jsonb_build_object(
                                        'phase1', jsonb_build_object('sl', jsonb_build_array(2500, 3000), 'tp', jsonb_build_array(5000, 6000),
                                                                     'menge', jsonb_build_array(1.0, 1.4), 'puffer', jsonb_build_array(75, 100),
                                                                     'boden_pct', 12, 'menge_schritt', 0.01),
                                        'phase2', jsonb_build_object('sl', jsonb_build_array(2500, 3000), 'tp', jsonb_build_array(2000, 2500),
                                                                     'menge', jsonb_build_array(1.0, 1.4), 'puffer', jsonb_build_array(75, 100),
                                                                     'boden_pct', 12, 'menge_schritt', 0.01))), true)
                               else f end order by o)
           from jsonb_array_elements(regeln->'firmen') with ordinality as e(f, o))),
       updated_at = now()
 where id = 1;
-- Prüfen: select f->'flex'->'je_groesse'->'100000' from auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f
--          where id = 1 and f->'namen' ? 'fundingpips';
