-- OD-NEUPLANUNG DER 3 ON-DEMAND-PLÄNE (NK1-F2, Master 05.11.2026 Variante a) — Slave 3
-- Die 3 FundedNext-On-Demand-Pläne von heute stammen aus dem Nachtlauf VOR .2055 (alte Regel: Ziel 1.500–1.850, TP = ganze Distanz → verletzt
-- Consistency 40 %). Werte = fcp_planen (.2066-Code) im Trockenlauf, Takt 2026-11-05T02:45Z (06:45 Dubai), Daten = Selects 06:50 Dubai,
-- alte Pläne ausgeblendet; Zeilen exakt so, wie fcp_planen sie anlegen würde (abgefangen, nichts geschrieben). Startzeit, Richtung, Bestätigung,
-- Status bleiben ALT. funded_plan.start_um = alter Start. Nur status planned + started_at null + start_um_gestartet_at null. Idempotent:
-- zweiter Lauf setzt dieselben Werte; fcp_ziel nur, solange es leer ist (wie der Planer-Guard).
-- NICHT von Slave 3 eingespielt.

begin;

-- …3608 (Plan 74d88726, Start 11:14 Dubai, buy — bleibt):
--   Ziel 101796 → 102194 · TP 813 → 460 · SL 2094 → 1887 · Lots 1.6 → 1.26 · Fusion-Lots 2.82 → 2.22 · Fusion am TP -121.95 → -69.0 € · am SL +314.1 → +283.05 €
--   master_risk 10000.0 · slave_risk 1500.0 · multiplier 1.7647 (unverändert gegenüber alt) · fcp_ziel → {"zyklus": 3, "usd": 2194.0, "at": "2026-11-05T02:45:00+00:00"}
update public.trade_plans set
  master_contracts = 1.26, master_tp = 460.0, master_sl = 1887.0, master_risk = 10000.0,
  slave_risk = 1500.0, multiplier = 1.7647, slave_account_id = '774a6d36-571c-4785-8fa4-920a4e4e9c81', slave_name = 'Echo +', slave_firm = 'Fusion Markets',
  notes = 'Funded-CFD-Planer · Gewinn 983 $ → Ziel 102.194 $ · TP consistency · Hedge 1.500 € auf 10.000 $ DD · On Demand · Ziel fest · Consistency 40 % · noch 1.211 $ · Trade 1 von 3 · größter Tag 0 $',
  mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('funded_plan', '{"start": 100000.0, "gewinn": 982.96, "ziel": 102194.0, "ziel_von": 102000.0, "dd": 10000.0, "tp_art": "consistency", "eins_prozent": false, "hedge_eur": 1500.0, "hedge_lots": 2.22, "hedge_tp_eur": -69.0, "hedge_sl_eur": 283.05, "erster_zyklus": false, "zyklus": 3, "tp_deckel": null, "gewinne": null, "consistency": {"tp": 460.0, "ende": 2194, "deckel": 460.2, "rest": 1211.04, "n": 3, "k": 0, "bester_tag": 0.0, "summe_tage": 0.0, "distanz": 1211.04, "anteil": 0.3844, "p": 40.0, "fertig": false, "lesbar": true}, "erster_payout": false, "gewinntage": null, "ziel_fest": {"zyklus": 3, "usd": 2194.0, "neu": true}, "on_demand": true, "art": "cfd", "start_um": "2026-11-05T07:14:33.600000+00:00", "richtung_geschuetzt": false}'::jsonb),
  updated_at = now()
where id = '74d88726-14a7-4afc-88d3-f2d017ee504e' and master_account_id = '05daf6c6-386a-4883-9bc7-f7a58add89fc' and status = 'planned' and started_at is null and start_um_gestartet_at is null;

update public.accounts set fcp_ziel = '{"zyklus": 3, "usd": 2194.0, "at": "2026-11-05T02:45:00+00:00"}'::jsonb
where id = '05daf6c6-386a-4883-9bc7-f7a58add89fc' and account_type = 'funded_cfd' and fcp_ziel is null;

-- …7427 (Plan f901b52c, Start 13:27 Dubai, sell — bleibt):
--   Ziel 101656 → 102057 · TP 1656 → 748 · SL 2300 → 1852 · Lots 1.05 → 1.29 · Fusion-Lots 1.85 → 2.28 · Fusion am TP -248.4 → -112.2 € · am SL +345 → +277.8 €
--   master_risk 10000.0 · slave_risk 1500.0 · multiplier 1.7647 (unverändert gegenüber alt) · fcp_ziel → {"zyklus": 2, "usd": 2057.0, "at": "2026-11-05T02:45:00+00:00"}
update public.trade_plans set
  master_contracts = 1.29, master_tp = 748.0, master_sl = 1852.0, master_risk = 10000.0,
  slave_risk = 1500.0, multiplier = 1.7647, slave_account_id = '774a6d36-571c-4785-8fa4-920a4e4e9c81', slave_name = 'Echo +', slave_firm = 'Fusion Markets',
  notes = 'Funded-CFD-Planer · Gewinn 0 $ → Ziel 102.057 $ · TP consistency · Hedge 1.500 € auf 10.000 $ DD · On Demand · Ziel fest · Consistency 40 % · noch 2.057 $ · Trade 1 von 3 · größter Tag 0 $',
  mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('funded_plan', '{"start": 100000.0, "gewinn": 0.0, "ziel": 102057.0, "ziel_von": 102000.0, "dd": 10000.0, "tp_art": "consistency", "eins_prozent": false, "hedge_eur": 1500.0, "hedge_lots": 2.28, "hedge_tp_eur": -112.2, "hedge_sl_eur": 277.8, "erster_zyklus": false, "zyklus": 2, "tp_deckel": null, "gewinne": null, "consistency": {"tp": 748.0, "ende": 2057, "deckel": 781.66, "rest": 2057.0, "n": 3, "k": 0, "bester_tag": 0.0, "summe_tage": 0.0, "distanz": 2057.0, "anteil": 0.3637, "p": 40.0, "fertig": false, "lesbar": true}, "erster_payout": false, "gewinntage": null, "ziel_fest": {"zyklus": 2, "usd": 2057.0, "neu": true}, "on_demand": true, "art": "cfd", "start_um": "2026-11-05T09:27:43.800000+00:00", "richtung_geschuetzt": false}'::jsonb),
  updated_at = now()
where id = 'f901b52c-235d-4aec-ba64-94211ecde168' and master_account_id = '373f1ba2-dbdc-4181-957e-e3c15f9e82bb' and status = 'planned' and started_at is null and start_um_gestartet_at is null;

update public.accounts set fcp_ziel = '{"zyklus": 2, "usd": 2057.0, "at": "2026-11-05T02:45:00+00:00"}'::jsonb
where id = '373f1ba2-dbdc-4181-957e-e3c15f9e82bb' and account_type = 'funded_cfd' and fcp_ziel is null;

-- …0246 (Plan 99d6206e, Start 17:27 Dubai, buy — bleibt):
--   Ziel 101554 → 102194 · TP 555 → 437 · SL 1778 → 2129 · Lots 1.48 → 1.74 · Fusion-Lots 2.61 → 3.07 · Fusion am TP -83.25 → -65.55 € · am SL +266.7 → +319.35 €
--   master_risk 10000.0 · slave_risk 1500.0 · multiplier 1.7647 (unverändert gegenüber alt) · fcp_ziel → {"zyklus": 2, "usd": 2194.0, "at": "2026-11-05T02:45:00+00:00"}
update public.trade_plans set
  master_contracts = 1.74, master_tp = 437.0, master_sl = 2129.0, master_risk = 10000.0,
  slave_risk = 1500.0, multiplier = 1.7647, slave_account_id = '774a6d36-571c-4785-8fa4-920a4e4e9c81', slave_name = 'Echo +', slave_firm = 'Fusion Markets',
  notes = 'Funded-CFD-Planer · Gewinn 999 $ → Ziel 102.194 $ · TP consistency · Hedge 1.500 € auf 10.000 $ DD · On Demand · Ziel fest · Consistency 40 % · noch 1.195 $ · Trade 1 von 3 · größter Tag 0 $',
  mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('funded_plan', '{"start": 100000.0, "gewinn": 998.67, "ziel": 102194.0, "ziel_von": 102000.0, "dd": 10000.0, "tp_art": "consistency", "eins_prozent": false, "hedge_eur": 1500.0, "hedge_lots": 3.07, "hedge_tp_eur": -65.55, "hedge_sl_eur": 319.35, "erster_zyklus": false, "zyklus": 2, "tp_deckel": null, "gewinne": null, "consistency": {"tp": 437.0, "ende": 2194, "deckel": 454.23, "rest": 1195.33, "n": 3, "k": 0, "bester_tag": 0.0, "summe_tage": 0.0, "distanz": 1195.33, "anteil": 0.3655, "p": 40.0, "fertig": false, "lesbar": true}, "erster_payout": false, "gewinntage": null, "ziel_fest": {"zyklus": 2, "usd": 2194.0, "neu": true}, "on_demand": true, "art": "cfd", "start_um": "2026-11-05T13:27:44.400000+00:00", "richtung_geschuetzt": false}'::jsonb),
  updated_at = now()
where id = '99d6206e-c036-421e-9e51-1e800d392813' and master_account_id = '320c26c6-f844-4bfe-8215-fbfeadcb16b8' and status = 'planned' and started_at is null and start_um_gestartet_at is null;

update public.accounts set fcp_ziel = '{"zyklus": 2, "usd": 2194.0, "at": "2026-11-05T02:45:00+00:00"}'::jsonb
where id = '320c26c6-f844-4bfe-8215-fbfeadcb16b8' and account_type = 'funded_cfd' and fcp_ziel is null;

-- Kontrolle (nach dem Einspielen):
-- select left(id::text,8), status, start_um, richtung, master_tp, master_sl, master_contracts, mt5_baseline->'funded_plan'->>'ziel' ziel, notes from public.trade_plans
--   where id in ('74d88726-14a7-4afc-88d3-f2d017ee504e','f901b52c-235d-4aec-ba64-94211ecde168','99d6206e-c036-421e-9e51-1e800d392813');
-- select left(id::text,8), fcp_ziel from public.accounts where id in ('05daf6c6-386a-4883-9bc7-f7a58add89fc','373f1ba2-dbdc-4181-957e-e3c15f9e82bb','320c26c6-f844-4bfe-8215-fbfeadcb16b8');

commit;
