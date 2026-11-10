-- 2026-11-10 — FH1b (Master, Finn wartet): ein Funded-Vorschlag (Apex 100k, Plan f06fd3ec…) wurde um 01:31 Dubai VOR FH1 (.2134) angelegt und zeigt noch die alte
-- Hedge-Basis (echte offene Kosten 514,70 €, 2,79 Lot). Neu gerechnet mit app.py fdp_konto_rechnen/fdp_kosten_theorie (FH1 Variante B) — gleiche Balance
-- 108.363,04, Liq 100.100, TP 3.636,96, SL 2.500, 2 NQ, € je Punkt Fusion dieser ID 0,8926 (aus den gespeicherten Plan-Werten):
--   Hedge-Basis 1.470,54 € (Pump-Kosten bis Balance) · Verhältnis 0,17797 € je $ · Multiplikator 3,9876 → 7,98 Lot · Fusion am TP −647,65 € / am SL +444,91 €.
-- Guard wie das ±500-Neurechnen (fdp_vorschlag_neu): nur geplant, unbestätigt, ohne Startzeit/Claim, nie gestartet, keine Hand-Werte, updated_at wie gelesen.
update public.trade_plans
   set master_risk = 8263.04, slave_risk = 1470.54, multiplier = 3.9876, hedge_faktor = 3.988, hedge_eur = 647.65,
       notes = 'Funded-Planer · Vorschlag · Zyklus 1 · Ziel 112.000 $ · Liq 100.100 $ · Stufe 4 (Daily Loss 2.500 $) · Hedge-Basis 1.471 € = Pump-Kosten bis Balance (B) · echt 515 €',
       mt5_baseline = jsonb_set(mt5_baseline, '{funded_plan}', coalesce(mt5_baseline->'funded_plan', '{}'::jsonb) || jsonb_build_object(
         'offen_eur', 1470.54, 'offen_kosten_eur', 514.70, 'hedge_basis', 'pump_b', 'hedge_quelle', 'Pump-Kosten bis Balance (B) 1.471 € · echt 515 €',
         'verhaeltnis', 0.17797, 'hedge_tp_eur', 647.26, 'hedge_sl_eur', 444.91))
 where id = 'f06fd3ec-d8a5-4356-aa16-fbdeddb2f922'
   and status = 'planned' and auto_bestaetigt_at is null and start_um is null and start_um_gestartet_at is null and started_at is null and hand_werte_at is null
   and updated_at = '2026-11-09 21:31:28.550183+00'
returning id, slave_risk, multiplier, hedge_eur, mt5_baseline->'funded_plan'->>'offen_eur' as basis;
