#!/usr/bin/env python3
"""Selbsttest FP-PUF (17.11.2026, Finn ~15:15 Dubai: „Bei der Regel gerne Puffer, gerne auch 10 % Puffer oder so. Hier mehr Puffer einbauen, nicht vergessen.“):
Funded-Planer Futures — der Trade, der das Ziel erreichen soll, bekommt TP = Rest + max(Rest × ziel_puffer_pct %, ziel_puffer_min_usd), gedeckelt auf max_trade
und den Consistency-Deckel der Firma (app.py fdp_ziel_puffer_cfg / fdp_ziel_puffer / fdp_ziel_puffer_text, eingebaut in fdp_konto_rechnen, fdp_pump_trade1,
fdp_pump_trade2, fdp_planen, fdp_pump_tick, fdp_regeln_aendern).
Anlass: Apex 100k, Ziel 112.000 $, Rest 5.992 $ getroffen, gebucht +5.948,80 $ → 42,90 $ unter dem Ziel, kein Wechsel zu Winning Days.
Platzhalter-Konten, keine echten Kennungen. Aufruf: python3 tools/selftest_fp_puf_ziel_puffer.py"""
import os
import random
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_funded_planer as fp  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


ns = fp.laden()
ns.setdefault("hashlib", __import__("hashlib"))   # fdp_ziel_gewinn (Spanne) braucht hashlib, laden() bringt es nicht mit
R, JG, H = ns["fdp_konto_rechnen"], ns["fdp_je_groesse"], ns["fdp_hedge"]
CFG, PUF, TXT = ns["fdp_ziel_puffer_cfg"], ns["fdp_ziel_puffer"], ns["fdp_ziel_puffer_text"]
T1, T2, PK = ns["fdp_pump_trade1"], ns["fdp_pump_trade2"], ns["fdp_pump_konto"]
AUS = {"ziel_puffer_pct": 0, "ziel_puffer_min_usd": 0}
# Apex wie live (funded_plan_regeln 17.11.2026): 100k Ziel 12.000, max_trade 6.000, dd 3.000, Consistency 50 %
APEX = dict(ns["FDP_FIRMEN_STANDARD"][0], consistency_pct=50)
j100 = JG(APEX, 100000)

print("1) Einstellung je Firma")
check(CFG({}) == {"pct": 10.0, "min": 100.0, "cons_pct": None}, f"ohne Einstellung: 10 % / 100 $, kein Consistency-Deckel ({CFG({})})")
check(CFG(APEX)["cons_pct"] == 50.0, "consistency_pct der Firma wird Deckel")
check(CFG({"ziel_puffer_pct": 5, "ziel_puffer_min_usd": 250}) == {"pct": 5.0, "min": 250.0, "cons_pct": None}, "eigene Werte je Firma")
check(CFG({"ziel_puffer_pct": 80, "ziel_puffer_min_usd": -1, "consistency_pct": 100}) == {"pct": 10.0, "min": 100.0, "cons_pct": None},
      "außerhalb der Grenzen (0–50 % / 0–5.000 $ / Consistency 10–99) → Standard")
check(CFG({"ziel_puffer_pct": True})["pct"] == 10.0 and CFG(None)["pct"] == 10.0, "bool/None → Standard")
check(PUF(CFG(AUS), 5992.0, 6000, 6008) == (5992.0, None), "0 % / 0 $ = aus → TP = Rest")
check(PUF(None, 5992.0) == (5992.0, None), "cfg None (reine Funktion ohne Einstellung) → TP = Rest")

print("2) Mikes Fall: Apex 100k …0004, Start 100.000, Balance 106.008, Ziel 112.000 → Rest 5.992")
tp, i = PUF(CFG({}), 5992.0)
check(tp == 6591.2 and i["puffer"] == 599.2 and i["deckel"] is None, f"ohne Deckel: 5.992 + 10 % = 6.591,20 ({tp})")
tp, i = PUF(CFG(APEX), 5992.0, 6000, 6008.0)
check(tp == 6000.0 and i["puffer"] == 8.0 and i["deckel"] == "Max-Trade 6.000 $", f"Apex: gedeckelt auf Max-Trade 6.000 ({tp}, {i['deckel']})")
tp, i = PUF(CFG(APEX), 5992.0, 7000, 6008.0)
check(tp == 6008.0 and i["deckel"].startswith("Consistency 50 %"), f"mit Max-Trade 7.000: Consistency 50 % → TP ≤ bisheriger Gewinn 6.008 ({tp}, {i['deckel']})")
r = R(APEX, j100, fp.ST100, 106008.0, 106008.0, 350.0, 100000, 100000, kt_fest=2, konto_id="k-0004", zyklus=1)
r0 = R(dict(APEX, **AUS), j100, fp.ST100, 106008.0, 106008.0, 350.0, 100000, 100000, kt_fest=2, konto_id="k-0004", zyklus=1)
check(r["aktion"] == "planen" and r0["tp"] == 5992.0 and r["tp"] == 6000.0 and r["ziel"] == 112000.0, f"Planer: TP {r0['tp']} → {r['tp']} (gedeckelt)")
check(r["sl"] == r0["sl"] == 2500.0 and r["kontrakte"] == r0["kontrakte"] and r["stufe"] == r0["stufe"] == 4 and r["dll"] == 2500,
      f"SL, Kontrakte, Stufe bleiben (SL {r['sl']}, {r['kontrakte']} NQ, Stufe {r['stufe']})")
h = H(r["slave_risk"], 106008.0, r["liq"], 6000.0, r["sl"], r["kontrakte"], sppl=ns["FDP_SLAVE_PPL"])
check(all(r[k] == h[k] for k in h), "Fusion-Hedge = dieselbe Formel (fdp_hedge) mit dem neuen TP")
check(r["master_risk"] == r0["master_risk"] and r["slave_risk"] == r0["slave_risk"] and r["multiplier"] == r0["multiplier"] and r["hedge_eur"] > r0["hedge_eur"],
      f"Risiko/Lots gleich, nur Hedge am TP wächst mit dem TP ({r0['hedge_eur']} → {r['hedge_eur']} €)")
check(r["ziel_puffer"]["deckel"] == "Max-Trade 6.000 $" and "gedeckelt: Max-Trade 6.000 $" in TXT(r["ziel_puffer"]), f"Notiz: {TXT(r['ziel_puffer'])}")
# Folgetag bei Mikes echtem Ergebnis (111.957,10): Rest 42,90 → TP 142,90 (Mindest-Puffer 100 $)
r2 = R(APEX, j100, fp.ST100, 111957.10, 111957.10, 350.0, 100000, 100000, kt_fest=2, konto_id="k-0004", zyklus=1)
check(r2["aktion"] == "planen" and r2["tp"] == 142.9, f"42,90 $ unter dem Ziel → nächster TP 42,90 + 100 = 142,90 ({r2.get('tp')})")
# Ziel-Check unverändert
check(R(APEX, j100, fp.ST100, 112000.0, 112000.0, 350.0, 100000, 100000, kt_fest=2, konto_id="k", zyklus=1)["aktion"] == "ziel", "Balance = Ziel → Winning Days (wie bisher)")
check(R(APEX, j100, fp.ST100, 112100.0, 112100.0, 350.0, 100000, 100000, kt_fest=2, konto_id="k", zyklus=1)["aktion"] == "ziel", "Balance über dem Ziel (Puffer getroffen) → Winning Days")

print("3) Bitgleich, wo der Trade nicht bis zum Ziel geht")
n = abw = rabw = 0
for g, st in ((100000, fp.ST100), (150000, fp.ST150)):
    jg = JG(APEX, g)
    mt = jg["max_trade"]
    for bal in [g - 2000, g - 400, g, g + 1500, g + jg["ziel_gewinn"] - mt - 1, g + jg["ziel_gewinn"] - mt - 900]:
        for seed in range(8):
            ra, rb = random.Random(seed), random.Random(seed)
            a = R(APEX, jg, st, float(bal), float(max(bal, g)), 350.0, g, g, ra, konto_id=f"k{seed}", zyklus=1)
            b = R(dict(APEX, **AUS), jg, st, float(bal), float(max(bal, g)), 350.0, g, g, rb, konto_id=f"k{seed}", zyklus=1)
            n += 1
            abw += a != b
            rabw += ra.random() != rb.random()
check(n == 96 and abw == 0 and rabw == 0, f"{n} Apex-Fälle (Break-even, frisch, Etappe über Max-Trade): Ergebnis und Würfel gleich ({abw}/{rabw})")
TR = {"ziel_gewinn": [13000, 19000], "dd": 4500, "hedge_eur": 850, "hedge_auf_usd": 4500, "pump2_pct": 100, "ein_kontrakte": {"3": 1}, "ein_sl": [4500, 4700],
      "t1_tp": [4000, 8000], "t1_kontrakte": {"2": 0.5, "3": 0.5}, "t1_sl": [4500, 4700], "sl_kein_pct": 50, "sl_hinter_liq": True, "t2_kontrakte": {"3": 1},
      "t2_sl_be_pct": 50}
n = abw = 0
for seed in range(40):
    a = T1(TR, "zwei", 150000.0, 150000.0, 145500.0, 166000.0, random.Random(seed), puffer=CFG({}))
    b = T1(TR, "zwei", 150000.0, 150000.0, 145500.0, 166000.0, random.Random(seed))
    n += 1
    abw += a != b
check(abw == 0, f"Pump Trade 1 von 2 (mit kette, geht nicht bis zum Ziel): {n} Würfe gleich ({abw})")

print("4) Modus „rest“ (FTMO Futures) und Pump")
FT = {"name": "FTMO Futures", "namen": ["ftmofutures"], "an": True, "tp_modus": "rest", "lock_usd": 0,
      "je_groesse": {"50000": {"ziel_gewinn": [4000, 4500], "dd": 3000, "daily_usd": 1000, "hedge_eur": 450, "kosten_eur": 120, "sl": [750, 850], "kontrakte": {"1": 1}}}}
jf = JG(FT, 50000)
w = R(FT, jf, None, 50000.0, 50000.0, 120.0, 50000, 50000, random.Random(1), konto_id="f1", zyklus=1)
w0 = R(dict(FT, **AUS), jf, None, 50000.0, 50000.0, 120.0, 50000, 50000, random.Random(1), konto_id="f1", zyklus=1)
check(w["tp"] == round(w0["tp"] * 1.1, 2) and w["sl"] == w0["sl"] and w["kontrakte"] == w0["kontrakte"], f"FTMO: TP {w0['tp']} → {w['tp']} (+10 %), SL gleich")
w = R(FT, jf, None, w0["ziel"] - 500, w0["ziel"] - 500, 120.0, 50000, 50000, random.Random(1), konto_id="f1", zyklus=1)
check(w["tp"] == 600.0, f"FTMO Rest 500 → mindestens 100 $ Puffer → TP 600 ({w.get('tp')})")
e = T1(TR, "ein", 150000.0, 150000.0, 145500.0, 166000.0, random.Random(4), puffer=CFG({}))
e0 = T1(TR, "ein", 150000.0, 150000.0, 145500.0, 166000.0, random.Random(4))
check(e["tp"] == 17600.0 and e0["tp"] == 16000.0 and e["sl"] == e0["sl"] and e["risiko"] == e0["risiko"] and e["hedge_eur"] == e0["hedge_eur"],
      f"Pump „ein“: TP 16.000 → 17.600, SL/Risiko/Risiko-Hedge gleich ({e['tp']})")
z, g2 = T2(TR, {"tp": 6000}, 150000.0, 156000.0, 145500.0, 166000.0, random.Random(2), start=150000.0, puffer=CFG({}))
z0, _g = T2(TR, {"tp": 6000}, 150000.0, 156000.0, 145500.0, 166000.0, random.Random(2), start=150000.0)
check(g2 is None and z["tp"] == 11000.0 and z0["tp"] == 10000.0 and z["sl"] == z0["sl"] and z["risiko"] == z0["risiko"], f"Pump Trade 2: TP 10.000 → 11.000 ({z['tp']})")
check({k: v for k, v in z.items() if k not in ("tp", "ziel_puffer")} == {k: v for k, v in z0.items() if k != "tp"}, "Pump Trade 2: sonst alles gleich")
PR = {"name": "Tradeify", "namen": ["tradeify"], "an": True, "tp_modus": "pump2", "lock_usd": 100, "je_groesse": {"150000": dict(TR, pump2_pct=0)}}
k = PK(PR, PR["je_groesse"]["150000"], 150000.0, 150000.0, 150000.0, 150000, "t1", 1, "2026-11-18", random.Random(3), sppl=0.85)
k0 = PK(dict(PR, **AUS), PR["je_groesse"]["150000"], 150000.0, 150000.0, 150000.0, 150000, "t1", 1, "2026-11-18", random.Random(3), sppl=0.85)
hk = H(850 / 4500 * (150000 - k["liq"]), 150000.0, k["liq"], k["tp"], k["sl"] if k["sl"] is not None else min(150000 - k["liq"], k["pump"]["risiko"]), k["kontrakte"], sppl=0.85)
check(k["tp"] == round(k0["tp"] * 1.1, 2) and all(k[x] == hk[x] for x in hk) and k["master_risk"] == k0["master_risk"], f"Pump-Konto: TP {k0['tp']} → {k['tp']}, Hedge = fdp_hedge mit neuem TP")
check(k["ziel_puffer"]["puffer"] == round(k["tp"] - k0["tp"], 2) and "ziel_puffer" not in k0, "Pump-Konto trägt ziel_puffer (Notiz), ohne Puffer nicht")

# Prüfer-Gegenlesen (17.11.2026): Consistency bei Trade 2 zählt Trade 1 desselben Tages mit
z, _g = T2(TR, {"tp": 4000}, 158000.0, 162000.0, 145600.0, 166000.0, random.Random(2), start=150000.0, puffer=CFG({"consistency_pct": 50}))
check(z["tp"] == 4000.0 and z["ziel_puffer"]["puffer"] == 0 and "Consistency" in z["ziel_puffer"]["deckel"],
      f"Trade 2 mit Consistency 50 %: Tag (4.000 + TP) ≤ 50 % × (12.000 + TP) → kein Puffer ({z['tp']}, {z['ziel_puffer']['deckel']})")
z, _g = T2(TR, {"tp": 2000}, 150000.0, 152000.0, 145600.0, 156000.0, random.Random(2), start=140000.0, puffer=CFG({"consistency_pct": 50}))
check(z["tp"] == 4400.0, f"Trade 2: Luft genug (Gewinn 12.000, Trade 1 2.000 → Deckel 8.000) → voller Puffer 4.000 + 400 ({z['tp']})")
tp, i = PUF(CFG({"consistency_pct": 50}), 4000.0, None, 12000.0, tag_bisher=4000.0)
check(tp == 4000.0 and i["puffer"] == 0, "reine Funktion: (50 × 12.000 − 100 × 4.000) ÷ 50 = 4.000 → nur der Rest")
# Plausi-Fenster (Pump/Rest: Balance > Ziel + dd = unplausibel): Puffer höchstens ½ DD
tp, i = PUF(CFG({"ziel_puffer_min_usd": 2000}), 7000.0, None, 0.0, dd=1500)
check(tp == 7750.0 and i["deckel"].startswith("Plausi-Fenster"), f"FNF 50k (dd 1.500), Mindest-Puffer 2.000 → höchstens 750 ({tp}, {i['deckel']})")
FN = {"ziel_gewinn": [6000, 8000], "dd": 1500, "hedge_eur": 350, "hedge_auf_usd": 1500, "pump2_pct": 0, "ein_kontrakte": {"1": 1}, "ein_sl": [1300, 1400], "sl_kein_pct": 0}
e = T1(FN, "ein", 50000.0, 50000.0, 48500.0, 58000.0, random.Random(1), puffer=CFG({}))
check(e["tp"] == 8750.0 and e["tp"] - 8000 <= 1500 / 2, f"FNF Pump Rest 8.000: 10 % = 800 > ½ DD 750 → TP 8.750 ({e['tp']})")
w = R(dict(FT, ziel_puffer_min_usd=4000), jf, None, 50000.0, 50000.0, 120.0, 50000, 50000, random.Random(1), konto_id="f1", zyklus=1)
check(w["tp"] == round(w0["tp"] + 1500, 2), f"FTMO (dd 3.000) Mindest-Puffer 4.000 → höchstens 1.500 ({w['tp']})")

print("5) Einstellung ändern (fdp_regeln_aendern) und Anzeige")
# Einstellungs-Block (E2) liegt hinter der Route, laden() hört davor auf → Abschnitt nachladen
exec(fp.SRC[fp.SRC.index("# ══ EINSTELLUNGEN FUNDED PLANER → FUTURES"):fp.SRC.index("# ── WINNING DAY JE FIRMA")], ns)
REG = {"updated_at": "u", "firmen": [dict(APEX)]}
A = ns["fdp_regeln_aendern"]
p, f = A(REG, {"updated_at": "u", "firma": {"name": "Apex Trader", "ziel_puffer_pct": 15, "ziel_puffer_min_usd": 200}})
check(f is None and p["firmen"][0]["ziel_puffer_pct"] == 15 and p["firmen"][0]["ziel_puffer_min_usd"] == 200, "Puffer je Firma setzen (neuer Schlüssel erlaubt)")
p, f = A({"updated_at": "u", "firmen": [dict(APEX, ziel_puffer_pct=15)]}, {"updated_at": "u", "firma": {"name": "Apex Trader", "ziel_puffer_pct": None}})
check(f is None and "ziel_puffer_pct" not in p["firmen"][0], "null → Schlüssel weg (Standard 10 %)")
check(A(REG, {"updated_at": "u", "firma": {"name": "Apex Trader", "ziel_puffer_pct": 60}})[1] is not None, "über 50 % → abgelehnt")
an = ns["fdp_regeln_anzeige"]({"updated_at": "u", "firmen": [dict(APEX, ziel_puffer_pct=5)]})["firmen"][0]
check(an["ziel_puffer"]["pct"] == 5.0 and an["ziel_puffer_db"] == {"ziel_puffer_pct": 5}, "Anzeige: gültiger Puffer + DB-Werte")

print()
if FEHLER:
    print(f"ROT: {len(FEHLER)} Fehler")
    sys.exit(1)
print("ALLES GRÜN")
