-- Auto-Abhaken: Normal-Takt AN, Blow-Takt bleibt AUS (Finn 22.10.2026, Radar → Erledigt → Abhaken mit ~15 normalen Echo-V2-/Orbit-V2-Trades:
-- „alle Trades, die kein wichtiges Ergebnis haben, sollen automatisch abgehakt werden. Wichtiges Ergebnis = der Trade trägt einen Ergebnis-Chip
-- (Profit/bestanden, Mini-Trade/Tage-Mini, Blow/geblowt). Alles andere muss ich nicht noch einmal sehen.“).
-- Ursache, warum die Trades noch standen: die getrennten Schalter (app.py e473719f/54fb43cf, sql/2026-10-21_abhaken_auto_getrennt.sql) waren
-- gebaut, die Datei aber nie ausgeführt — regeln trug weder abhaken_auto_normal noch abhaken_auto (beide Takte aus).
--
-- Trockenlauf 22.10.2026 ~16:55 Dubai mit app.py ap_normal_auto_pruefen gegen alle 29 review-Pläne Orbit V2/Echo V2 (alle Hermann Technologies):
--   13 würden abgehakt — Echo V2 am SL: Chris FN 100k …2713 −2.747,81 · Chris FP 100k …2809 −2.108,16 · Jacob FP …6925 −2.070,42 · Jacob FP …6924
--   −2.467,20 · Mike FP …7584 −1.942,50 · Mike FN …3252 −2.589,99 · Mike FN 50k …1169 −1.144,08 · Aurel FN …2548 −2.543,13 · Ina FP …7120 −1.895,52 ·
--   Marc FN …8075 −3.467,88; Echo V2 am TP: Chris FP …3222 +3.596,40 · Mike FP …3655 +2.268,96; Orbit V2 am TP: Moritz Tradeify 150k …7265 +3.447,72.
--   16 bleiben: bestanden/Ziel-Tag (FN …1805, FP …0610, Chris 50k …1801/…9815, Marc …2209, Finn + Pascal …3152, Mike …3251, Chris Apex …0018,
--   Ina Apex …0013, Moritz Apex …0032), Winning Days mit Hedge (Jacob …0459/…3794), keine echte Lesung (Ina Tradeify …2590 — Puls blieb wegen
--   Big Trade zu Hause; Marc Tradeify …1388 — Balance nur vom Reader; Ina Apex …0012/…0016 — demo_liq, nie gelesen).
--
-- Wirksam erst auf dem app.py-Stand mit ap_auto_abhaken_schalter_lesen (e473719f). Auf älterem Stand (liest nur abhaken_auto) bewirkt das hier
-- nichts — beide Takte bleiben dort aus, nie still der Blow-Takt.

update auto_plan_regeln
   set regeln = (coalesce(regeln, '{}'::jsonb) - 'abhaken_auto') || '{"abhaken_auto_normal": true, "abhaken_auto_blow": false}'::jsonb
 where id = 1;   -- 22.10.2026 ausgeführt

-- Prüfen:
--   select regeln->'abhaken_auto_normal' as normal, regeln->'abhaken_auto_blow' as blow, regeln->'abhaken_auto' as alt from auto_plan_regeln where id = 1;
-- Wieder aus:
--   update auto_plan_regeln set regeln = regeln || '{"abhaken_auto_normal": false}'::jsonb where id = 1;
-- Abgehakte finden (Kennzeichen des Normal-Takts):
--   select id, master_name, master_pl, mt5_baseline->'auto_abgehakt' from trade_plans
--    where mt5_baseline->'auto_abgehakt' ? 'vorher' and (mt5_baseline->'auto_abgehakt'->>'at')::timestamptz > now() - interval '1 day';
