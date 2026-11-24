#!/usr/bin/env python3
"""Selbsttest FZ2 (24.11.2026, Finn: „Bei Ina ist ja On Demand, aber wir haben immer diesen Puffer eingestellt. Nur weil jetzt ein paar hundert Dollar da
fehlen: Es müsste eigentlich schon bestanden sein, also → Waiting for Payout“): FundedNext On Demand — „erreicht“ ab dem Firmen-Minimum (min_je_100k,
2.000 $ je 100k), das gewürfelte Ziel (ziel_je_100k, Finns Einstellung 2.050–2.300) bleibt nur Planungs-Ziel. Consistency bleibt echte Bedingung.
Fall Ina FundedNext 100k On Demand …0774, Zyklus 2, festes Ziel 2.197 $: Trades +770,74 · +747,79 · +634,01 → Profit 2.152,54 $, größter Tag 770,74 $ (35,8 %).
Ohne Netz. Aufruf: python3 tools/selftest_fz2_od_firmen_minimum.py"""
import os
import random
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
import app  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


FN = {"an": True, "name": "FundedNext", "namen": ["fundednext"], "tp_deckel_plus": 1000,
      "erster_payout": {"ziel": [50, 150], "hedge_eur_je_dd": 0.5, "lots_faktor": 0.1},
      "on_demand": {"ziel_je_100k": [2050, 2300]},            # wie live (funded_cfd_plan_regeln, Finns Einstellung)
      "je_groesse": {"100000": {"dd": 10000, "sl": [2000, 2300], "sl_1pct": [700, 780], "lots": [1.0, 1.75], "ziel": [5000, 5500], "hedge_eur": 1500}}}
G = 100000.0
JG = app.fcp_je_groesse(FN, G)
RK, JGO = app.fcp_on_demand_anwenden(FN, JG, G)
ZF = {"zyklus": 2, "usd": 2197}
R = app.fcp_konto_rechnen
SEIT = "2026-11-18"


def tage(trades):
    return app.fcp_tage_zyklus_w([{"status": "completed", "ended_at": t, "master_pl": pl} for t, pl in trades], SEIT)


INA = [("2026-11-19T16:05:00+00:00", 770.74), ("2026-11-23T00:20:00+00:00", 747.79), ("2026-11-24T08:26:09+00:00", 634.01)]
GEW = round(sum(pl for _t, pl in INA), 2)

print("— Regel —")
ok(app.fcp_on_demand_regel(FN)["min_je_100k"] == 2000.0, "Firmen-Minimum aus dem Code-Standard (2.000 je 100k), Ziel aus der Einstellung")
ok(JGO["ziel"] == [2050.0, 2300.0] and JGO["ziel_min"] == 2000.0, f"jg: Planungs-Ziel {JGO['ziel']}, Minimum {JGO.get('ziel_min')}")
ok(app.fcp_on_demand_anwenden(FN, JG, 50000.0)[1]["ziel_min"] == 1000.0, "50k → Minimum 1.000 (linear)")
ok("ziel_min" not in app.fcp_on_demand_anwenden(dict(FN, on_demand={"ziel_je_100k": [2050, 2300], "min_je_100k": 0}), JG, G)[1],
   "min_je_100k 0 → kein Minimum (wie vor FZ2)")
ok(app.fcp_ziel_schwelle(2197, {"ziel_toleranz_pct": 0.0, "ziel_min_usd": 2000.0}) == 2000.0, "Schwelle On Demand = Firmen-Minimum")
ok(app.fcp_ziel_schwelle(2197, {"ziel_toleranz_pct": 0.0}) == 2197.0, "ohne Minimum = Ziel (unverändert)")
ok(app.fcp_ziel_schwelle(1800, {"ziel_toleranz_pct": 0.0, "ziel_min_usd": 2000.0}) == 1800.0, "Minimum über dem Ziel → Ziel (nie höher als vorher)")
ok(app.fcp_ziel_schwelle(2000, {"ziel_toleranz_pct": 10.0}) == 1800.0, "normale Funded-CFD-Toleranz unverändert (ZT1)")

print("— Fall Ina …0774 —")
tw = app.fcp_tw_netto(tage(INA), GEW)
ok(GEW == 2152.54 and tw["b"] == 770.74, f"Profit {GEW}, größter Tag {tw['b']} ({round(tw['b'] / GEW * 100, 1)} %)")
oz = app.fcp_od_ziel(40, 2197, GEW, tw, JGO["ziel_min"])
print("  fcp_od_ziel:", oz)
ok(oz["bereit"] is True and oz["fehlt"] == 0 and oz["firma_usd"] == 2000.0 and oz["usd"] == 2197.0, "od_ziel: bereit gegen 2.000, Planungs-Ziel bleibt 2.197")
oz0 = app.fcp_od_ziel(40, 2197, GEW, tw)
ok(oz0["bereit"] is False and abs(oz0["fehlt"] - 44.46) < 0.01 and "firma_usd" not in oz0, "ohne Minimum wie bisher: fehlen 44,46 (Vorher-Zustand)")
r = R(JGO, G + GEW, G, 2, False, 1.0, 0.85, random.Random(3), regel=RK, tage=tage(INA), ziel_fest=ZF,
      param=dict(app.fcp_param_standard(), ziel_toleranz_pct=0.0))
print("  Planer:", {k: r.get(k) for k in ("aktion", "grund")})
ok(r["aktion"] == "ziel" and app.fcp_ziel_echt(r)[0], "Planer: Ziel erreicht → Waiting for Payout (fcp_ziel_echt ja)")
r_alt = R(JGO, G + GEW, G, 2, False, 1.0, 0.85, random.Random(3), regel=RK, tage=tage(INA), ziel_fest=ZF,
          param=dict(app.fcp_param_standard(), ziel_toleranz_pct=0.0, ziel_min_usd=None))
ok(r_alt["aktion"] == "ziel", "Minimum kommt aus jg, nicht aus dem Parameter-Dict des Aufrufers")
JG_ohne = {k: v for k, v in JGO.items() if k != "ziel_min"}
r0 = R(JG_ohne, G + GEW, G, 2, False, 1.0, 0.85, random.Random(3), regel=RK, tage=tage(INA), ziel_fest=ZF,
       param=dict(app.fcp_param_standard(), ziel_toleranz_pct=0.0))
ok(r0["aktion"] == "planen", f"Gegenprobe ohne Minimum: plant weiter (TP {r0.get('tp')}) — so kam Finns Frage zustande")

print("— Grenzen —")
r = R(JGO, G + 1999.0, G, 2, False, 1.0, 0.85, random.Random(3), regel=RK, ziel_fest=ZF, param=dict(app.fcp_param_standard(), ziel_toleranz_pct=0.0),
      tage=tage([("2026-11-19T16:05:00+00:00", 700.0), ("2026-11-23T00:20:00+00:00", 700.0), ("2026-11-24T08:26:09+00:00", 599.0)]))
ok(r["aktion"] == "planen", f"Profit 1.999 < 2.000 → noch nicht (TP {r.get('tp')})")
t2 = [("2026-11-19T16:05:00+00:00", 900.0), ("2026-11-23T00:20:00+00:00", 700.0), ("2026-11-24T08:26:09+00:00", 500.0)]
r = R(JGO, G + 2100.0, G, 2, False, 1.0, 0.85, random.Random(3), regel=RK, ziel_fest=ZF, param=dict(app.fcp_param_standard(), ziel_toleranz_pct=0.0), tage=tage(t2))
oz2 = app.fcp_od_ziel(40, 2197, 2100.0, app.fcp_tw_netto(tage(t2), 2100.0), 2000.0)
ok(r["aktion"] == "planen" and oz2["bereit"] is False and oz2["firma_usd"] == 2250.0 and oz2["fehlt"] == 150.0,
   f"Profit 2.100 ≥ Minimum, aber größter Tag 900 > 40 % → noch nicht, Required 2.250 (fehlen {oz2['fehlt']})")
r = R(JGO, G + 2250.0, G, 2, False, 1.0, 0.85, random.Random(3), regel=RK, ziel_fest=ZF, param=dict(app.fcp_param_standard(), ziel_toleranz_pct=0.0),
      tage=tage([("2026-11-19T16:05:00+00:00", 900.0), ("2026-11-23T00:20:00+00:00", 700.0), ("2026-11-24T08:26:09+00:00", 650.0)]))
ok(r["aktion"] == "ziel", "Profit 2.250 = größter Tag ÷ 40 % → Waiting")

print("— FZ1: letzter Trade schließt den Rest ganz (aufrunden) —")
cf = app.fcp_cons_finn(40, 2197, 1518.53, {"b": 770.74, "w": 1518.53, "n": 2, "serie": 1518.53, "serie_n": 2, "heute": 0.0})
ok(cf["tp"] == 679.0 and cf["rest"] == 678.47, f"Rest 678,47 → TP 679 (vorher 678, Ziel um 0,47 verfehlt): {cf['tp']}")
cf = app.fcp_cons_finn(40, 2197, 1497.0, {"b": 770.0, "w": 1497.0, "n": 2, "serie": 1497.0, "serie_n": 2, "heute": 0.0})
ok(cf["tp"] == 700.0, f"ganzer Rest 700 bleibt 700: {cf['tp']}")

print("— Konto-Seite / Radar (Quelltext) —")
src = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
ok(src.count('_p_zt["ziel_min_usd"] = float(_wd_num(jg["ziel_min"]))') == 1, "/konto-ziele: erreicht + Abhak-Text gegen das Minimum")
ok(src.count('_pz["ziel_min_usd"] = float(_zm)') == 1, "Radar ziele_tol: Vorauswahl Waiting gegen das Minimum")
ok(src.count('jg.get("ziel_min")) if (tzn and gewinn is not None) else None') == 1, "/konto-ziele: od_ziel mit Minimum (Popup bereit/fehlt)")

print()
print("ALLES OK" if not FEHLER else f"{len(FEHLER)} ROT")
sys.exit(1 if FEHLER else 0)
