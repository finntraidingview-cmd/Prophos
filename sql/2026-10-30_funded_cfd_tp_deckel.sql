-- FUNDED-CFD-PLANER: TP-DECKEL BEIM NACHHOLEN (Finn 30.10.2026 ~07:20, Anlass Trockenlauf S4: The5ers 200k …4186 bei −14.023 $ hätte
-- TP 15.410 $ bekommen, The5ers 100k …8441 bei −6.674 $ TP 8.089 $ — ein so großer Tag bricht bei The5ers die 50-%-Consistency).
-- Je Trade höchstens:
--   The5ers: tp_zyklen[Payout-Zyklus − 1], Zyklus = bisherige Payouts + 1 — 1: 750 (immer genau 750, auch nach Verlust), 2: 1.500,
--            3: 3.000, ab 4: 6.000 (letzter Wert gilt weiter).
--   FundedNext, FundingPips, Tradeify CFD: ziel[bis] + tp_deckel_plus (1.000 $); der Rest kommt an den nächsten Tagen.
-- app.py (fcp_tp_deckel) hat dieselben Werte als Standard; diese Zeilen machen sie in der Regel sichtbar/änderbar.
-- Idempotent: || überschreibt nur die zwei Schlüssel, Reihenfolge der Firmen bleibt.
update public.funded_cfd_plan_regeln r
   set firmen = (select coalesce(jsonb_agg(case when f->'namen' ? 'the5ers'
                                                 then f || '{"tp_zyklen": [750, 1500, 3000, 6000]}'::jsonb
                                                 else f || '{"tp_deckel_plus": 1000}'::jsonb end order by i), '[]'::jsonb)
                   from jsonb_array_elements(r.firmen) with ordinality e(f, i)),
       updated_at = now()
 where r.id = 1;
