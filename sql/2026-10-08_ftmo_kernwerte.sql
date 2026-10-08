-- FTMO-Kernwerte für den Auto-Planer (Finn 08.10.2026 ~07:40 Dubai, im Master-Chat, mit Screenshots der FTMO-Handelsziele
-- und der MT5-Spezifikation): bisher stand FTMO auf „planen: false“ ohne Phasen-Werte → Braucht dich „keine Regel für diese Firma“
-- (z. B. Chris 100k FTMO Phase 1).
--   Phase 1: SL 2.300–2.750 $, TP 5.000–8.000 $, Lots 25–35, Puffer +75 $, Ziel 10 % (10.000 $)
--   Phase 2: SL 2.300–2.750 $, TP 3.500–4.500 $, Lots 20–30, Puffer 50 $,  Ziel 5 % (5.000 $)
--   Handelsziele FTMO: max. Tagesverlust 5.000 $, max. Verlust 10.000 $ (statisch, 10 %), mind. 4 Handelstage
--   MT5: US100.cash, Kontraktgröße 1, Profitwährung USD → 1 Lot = 1 $ je Punkt; Volumen-Schritt 0,01 (geplant wird in ganzen Lots)
-- daily_usd speist die Klippe der Szenario-Kurve (Ausgleichs-Bot). Mindest-Handelstage modelliert der Planer nicht.
-- 200k: es gibt aktuell keine FTMO-200k-Konten; groessen bleibt [100000, 200000] ohne „skaliert“ (Finn fragen, bevor 200k kommt).
-- Wiederholbar. Rückbau: planen → false und phasen/daily_usd entfernen.

update auto_plan_regeln r
set regeln = jsonb_set(r.regeln, '{firmen}', (
      select jsonb_agg(
               case when f.elem->'namen' ? 'ftmo' then
                 f.elem || jsonb_build_object(
                   'planen', true,
                   'daily_usd', 5000,
                   'ziel_pct', jsonb_build_object('phase1', 10, 'phase2', 5),
                   'phasen', jsonb_build_object(
                     'phase1', jsonb_build_object('sl', jsonb_build_array(2300, 2750), 'tp', jsonb_build_array(5000, 8000),
                                                  'menge', jsonb_build_array(25, 35), 'menge_schritt', 1,
                                                  'puffer', jsonb_build_array(75, 75), 'ziel_pct', 10, 'boden_pct', 10),
                     'phase2', jsonb_build_object('sl', jsonb_build_array(2300, 2750), 'tp', jsonb_build_array(3500, 4500),
                                                  'menge', jsonb_build_array(20, 30), 'menge_schritt', 1,
                                                  'puffer', jsonb_build_array(50, 50), 'ziel_pct', 5, 'boden_pct', 10)))
               else f.elem end
               order by f.ord)
      from jsonb_array_elements(r.regeln->'firmen') with ordinality as f(elem, ord))),
    updated_at = now()
where r.id = 1;

-- Punktwert laut MT5-Spezifikation: Kontraktgröße 1, USD → 1 $ je Punkt und Lot (vorher teils 0,85)
update firm_specs set ppl = 1.0 where name = 'FTMO' and ppl is distinct from 1.0;
