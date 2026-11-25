-- 2026-11-25 — WD5 Befund 2: Lucid-WD-TP mit Puffer über der Gewinntag-Grenze (Master 25.11.2026; Standard-Entscheidung, ohne Finn zu fragen).
-- Befund: der WD-TP rechnet weder Gebühren noch Slippage ein. Lucid Gewinntag = 250 $ (WD_GOOD_DAY_MIN / Lucid wie Tradeify), Farmer-Spanne
-- wd_farmer_regeln.vorplan.regeln.fu.lucid = 268–280 $ → nur 18–30 $ Luft. Finn + Pascal · Lucid 150k …0001, Zyklus 4: TP → Ergebnis
-- 278 → 265 (−13), 271 → 269,50, 280 → 277,50, 274 → (Verlust), 278 → 276, 270 → 245,50 (−24,50, 25.11. 5b58bec9 → zählt NICHT als WD).
-- Neu: 285–300 $ (Puffer 35–50 $ über 250 $, größer als die größte gesehene Lücke 24,50 $). Hedge je WD bleibt (Staffel in €), nur der Satz je $ sinkt leicht.
-- Idempotent: ändert nur, wenn noch genau der alte Wert [268, 280] steht (eine Hand-Änderung im Admin bleibt). Rückbau: unten.
-- NICHT EINGESPIELT — Ausführen nur auf Finns/Masters Wort, nicht von einem Slave.

update public.wd_farmer_regeln
   set vorplan = jsonb_set(vorplan, '{regeln,fu,lucid}', '[285, 300]'::jsonb)
 where id = 1
   and vorplan->'regeln'->'fu'->'lucid' = '[268, 280]'::jsonb;

-- Prüfen:  select vorplan->'regeln'->'fu'->'lucid' from public.wd_farmer_regeln where id = 1;   -- [285, 300]
-- Rückbau: update public.wd_farmer_regeln set vorplan = jsonb_set(vorplan, '{regeln,fu,lucid}', '[268, 280]'::jsonb)
--           where id = 1 and vorplan->'regeln'->'fu'->'lucid' = '[285, 300]'::jsonb;

-- Nachtrag Master 25.11.2026 (Prüfer S2): Tradeify hat dieselbe Lücke (07d2457f TP 276 → +244,24, zählt nicht ≥ 250) → gleich mitziehen.
update public.wd_farmer_regeln
   set vorplan = jsonb_set(vorplan, '{regeln,fu,tradeify}', '[285, 300]'::jsonb)
 where id = 1
   and vorplan->'regeln'->'fu'->'tradeify' = '[266, 280]'::jsonb;
