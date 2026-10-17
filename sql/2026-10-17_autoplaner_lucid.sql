-- 17.10.2026 Finn: Trade-Planer für Lucid 150k Challenge — Regeln 1:1 wie Topstep (MLL 4.500 nachziehend, Lock bei Start,
-- Consistency 50 % → höchstens 4.500 am Tag), aber Daily Loss 2.700 (Soft Breach) und ohne Topstep-Kette:
--   ein Trade pro Tag, 2–3 NQ, TP 4.450–4.500 (unter der 50-%-Grenze, Slippage), SL 2.500 (bleibt unter dem Daily Loss).
--   Reparaturtag nach einem Verlust (147.500, Liquidation 145.500): TP bleibt 4.450–4.500, der SL rutscht von selbst hinter den
--   Boden (ap_konto_rechnen: Abstand < SL → SL = Abstand + AP_SL_HINTER_BODEN) — „TP oder geblowt", wie Finn will.
--   Letzter Trade: Rest bis Ziel + 30–40 $ (+ Futures-Punkte-Puffer, gedeckelt auf 4.500). Nur Challenge; Funded = Handarbeit.
-- Weg Orbit V2 (tvv2), ohne Gegenhedge. Name „Lucid Trading" → _ap_norm „lucidtrading" (exakter Vergleich).
-- Geplant wird nur, wo die Firma im Muster-Portfolio frei ist (seit 17.10.2026 nur „Finn + Pascal").
update auto_plan_regeln
   set regeln = jsonb_set(regeln, '{firmen}', (regeln->'firmen') || jsonb_build_array(jsonb_build_object(
         'namen', jsonb_build_array('lucidtrading', 'lucid'),
         'route', 'tvv2', 'symbol', 'NQ', 'planen', true,
         'boden', 'nachziehend', 'lock_bei_start', true, 'dd_usd', 4500, 'daily_usd', 2700,
         'groessen', jsonb_build_array(150000), 'kauf_eur', 222,
         'ziel_pct', jsonb_build_object('challenge', 6),
         'phasen', jsonb_build_object('challenge', jsonb_build_object(
             'sl', jsonb_build_array(2500, 2500), 'tp', jsonb_build_array(4450, 4500), 'tp_max', 4500,
             'menge', jsonb_build_array(2, 3), 'menge_schritt', 1, 'dd_usd', 4500, 'ziel_pct', 6,
             'puffer_je_menge', jsonb_build_object('2', jsonb_build_array(30, 40), '3', jsonb_build_array(30, 40))))))),
       updated_at = now()
 where id = 1
   and not exists (select 1 from jsonb_array_elements(regeln->'firmen') f where f->'namen' ? 'lucidtrading');
-- Prüfen: select f from auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f where f->'namen' ? 'lucidtrading';
