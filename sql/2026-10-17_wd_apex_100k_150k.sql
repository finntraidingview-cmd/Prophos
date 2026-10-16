-- 17.10.2026 Finn: Winning Days bei Apex nach Kontogröße — 150k Gewinntag 350 $, 100k Gewinntag 300 $ (Apex EOD-PA:
-- Mindestgewinn je Payout-Tag). TP 20–40 $ darüber wie bei Tradeify: 150k 370–390 $, 100k 320–340 $ („ja passt").
-- Kontrakte je Winning Day 3–4 für beide Größen. Schlüssel 'apex' bleibt = 150k, neu 'apex100' = 100k.
-- Vorher stand Apex auf 55–75 $ / 4–5 Kontrakte (alte 53-$-Regel) — es gab noch kein Apex-Konto auf Winning Days.
update wd_farmer_regeln
   set vorplan = jsonb_set(jsonb_set(vorplan,
         '{regeln,fu}', coalesce(vorplan->'regeln'->'fu', '{}'::jsonb) || '{"apex": [370, 390], "apex100": [320, 340]}'::jsonb),
         '{regeln,kt}', coalesce(vorplan->'regeln'->'kt', '{}'::jsonb) || '{"apex": [3, 4], "apex100": [3, 4]}'::jsonb),
       updated_at = now()
 where id = 1;
-- Prüfen: select vorplan->'regeln'->'fu', vorplan->'regeln'->'kt' from wd_farmer_regeln where id = 1;
