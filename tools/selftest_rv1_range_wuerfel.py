#!/usr/bin/env python3
"""Selbsttest RV1 „Range-Würfel“ im Challenge-Planer CFD (Finn 11.11.2026 07:35 über den Master: „75 % der Trades bleiben gleich, und nur bei 25 % der Trades
wird's angepasst … Stop Loss, Take Profit und Lotanzahl, alles drei … für alle drei wird einzeln gewürfelt“). Konstrukt: side-session-notes
2026-11-11_RV1_range_wuerfel_konstrukt.md.

Rechnet die REIN RECHNENDEN Funktionen aus app.py ohne Netz/DB (Muster selftest_ff2_pump.py): rv_faktoren, rv_anwenden, rv_planer_haken mit den echten
Phasen-Werten aus auto_plan_regeln (Stand 11.11.2026, nur gelesen) und ap_konto_rechnen. Feste Zahlenbeispiele FundedNext / The5%ers / FTMO + Zufalls-Prüfung
(je Lauf neue Zufallszahlen — 20 Läufe = 20 verschiedene Stichproben). Platzhalter-Konten, keine echten Kennungen.

Aufruf:  python3 tools/selftest_rv1_range_wuerfel.py"""
import hashlib
import os
import random
import re
import sys
from datetime import datetime, timezone, timedelta

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.environ.get("SELFTEST_APP") or os.path.join(W, "app.py"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "random": random, "hashlib": hashlib}


def lade(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^\S)", app, re.S | re.M)
    if not m:
        raise LookupError(name)
    exec(m.group(0), ns)


def ruf(fn, *a, **k):
    for _ in range(80):
        try:
            return ns[fn](*a, **k)
        except NameError as e:
            lade(str(e).split("'")[1])
    raise RuntimeError(fn)


for n in ("RV_MIN_PKT", "RV_STANDARD", "RV_STUFE", "AP_SL_HINTER_BODEN", "AP_TAGES_PUFFER", "AP_CFD_ROUTEN",   # Konstanten zuerst (Standard-Argumente)
          "rv_wurf", "rv_faktoren", "rv_anwenden", "rv_einstellung", "rv_planer_haken", "fest_wurf", "tw_wurf", "_wd_num", "ap_konto_rechnen",
          "ap_klein_normal", "ap_tagesgrenze", "eh_hedge"):
    try:
        lade(n)
    except LookupError:
        print(f"✗ fehlt: {n} (app.py)")
        sys.exit(1)

# ── Phasen-Werte aus auto_plan_regeln (DB-Lesung 11.11.2026), Punktwerte aus firm_specs ──
FN = {"namen": ["fundednext"], "route": "mt5v2", "dd_pct": 10, "boden": "statisch", "groessen": [50000, 100000], "ziel_pct": {"phase1": 8, "phase2": 5},
      "phasen": {"phase1": {"sl": [2250, 3150], "tp": [5400, 7200], "menge": [2.1, 3.2], "puffer": [25, 50], "ziel_pct": 8, "boden_pct": 10, "menge_schritt": 0.1},
                 "phase2": {"sl": [2250, 3150], "tp": [5400, 7200], "menge": [2.1, 3.2], "puffer": [25, 50], "ziel_pct": 5, "boden_pct": 10, "menge_schritt": 0.1}}}
T5 = {"namen": ["the5ers"], "route": "mt5v2", "dd_pct": 10, "boden": "statisch", "groessen": [100000, 200000], "skaliert": True,
      "phasen": {"phase1": {"sl": [1800, 2160], "tp": [5400, 6300], "menge": [20, 30], "puffer": [25, 50], "ziel_pct": 8, "boden_pct": 10, "menge_schritt": 1}}}
FT = {"namen": ["ftmo"], "route": "mt5v2", "dd_pct": 10, "boden": "statisch", "groessen": [100000, 200000],
      "phasen": {"phase1": {"sl": [2070, 2475], "tp": [4500, 7200], "menge": [25, 35], "puffer": [25, 50], "ziel_pct": 10, "boden_pct": 10, "menge_schritt": 1}}}
PPL = {"fn": 10.0, "t5": 1.0, "ft": 1.0}
MITTE = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}


def normal(regel, bal, u=MITTE, phase="phase1", ppl=10.0):
    w, g = ruf("ap_konto_rechnen", regel, phase, bal, dict(u), ppl=ppl)
    assert w and not g, g
    return w


def fk(tp, sl, lots):
    return {"f_tp": tp, "f_sl": sl, "f_lots": lots, "pct": 25, "von": 10, "bis": 100}


MIN = ns["RV_MIN_PKT"]

print("── 1. Würfel: Anteil, Spanne, fest, unabhängig ──")
check(ruf("rv_faktoren", "challenge_cfd", "konto-a", "2026-11-12", None) is None, "kein Wert → normaler Trade")
check(ruf("rv_faktoren", "challenge_cfd", "konto-a", "2026-11-12", 0) is None, "0 % → normaler Trade")
check(ruf("rv_faktoren", "challenge_cfd", "", "2026-11-12", 100) is None, "ohne Konto-ID → normaler Trade")
f100 = ruf("rv_faktoren", "challenge_cfd", "konto-a", "2026-11-12", 100)
check(bool(f100) and all(0.1 <= f100[x] <= 1.0 for x in ("f_tp", "f_sl", "f_lots")), f"100 % → immer klein, Faktoren 0,1–1,0 ({f100})")
check(ruf("rv_faktoren", "challenge_cfd", "konto-a", "2026-11-12", 100) == f100, "fest: gleiches Konto × Tag → gleiche Faktoren")
check(ruf("rv_faktoren", "challenge_cfd", "konto-a", "2026-11-12T08:00:00", 100) == f100, "Tag aus Zeitstempel (erste 10 Zeichen) → gleicher Wurf")
fv = ruf("rv_faktoren", "challenge_cfd", "konto-a", "2026-11-12", 100, 150, -5)
check(fv["von"] == 1.0 and fv["bis"] == 100.0, f"Spanne auf 1–100 begrenzt und sortiert ({fv['von']}–{fv['bis']})")
fe = ruf("rv_faktoren", "challenge_cfd", "konto-a", "2026-11-12", 100, 40, 40)
check(fe["f_tp"] == fe["f_sl"] == fe["f_lots"] == 0.4, "von = bis → genau dieser Faktor")
n, klein, tw_n, beide, gleich, fs = 0, 0, 0, 0, 0, []
for i in range(3000):
    kid, tag = f"konto-{i % 300}", f"2026-11-{10 + i // 300:02d}"
    f = ruf("rv_faktoren", "challenge_cfd", kid, tag, 25)
    n += 1
    handelt = ruf("tw_wurf", "challenge_cfd", kid, tag) * 100 < 75
    tw_n += handelt
    if f:
        klein += 1
        beide += handelt
        fs.append(f)
        gleich += f["f_tp"] == f["f_sl"] == f["f_lots"]
anteil = klein / n * 100
check(21 <= anteil <= 29, f"25 % eingestellt → {anteil:.1f} % klein (3.000 Konto-Tage)")
check(abs(beide / max(1, klein) * 100 - tw_n / n * 100) < 6, f"unabhängig vom Handels-Würfel: unter den kleinen handeln {beide / max(1, klein) * 100:.1f} % (alle {tw_n / n * 100:.1f} %)")
check(all(0.1 <= x[k] <= 1.0 for x in fs for k in ("f_tp", "f_sl", "f_lots")), "alle Faktoren in 10–100 %")
check(gleich == 0, "drei Faktoren einzeln gewürfelt (nie alle drei gleich)")
_m = lambda xs: sum(xs) / len(xs)   # noqa: E731
_kov = _m([x["f_tp"] * x["f_sl"] for x in fs]) - _m([x["f_tp"] for x in fs]) * _m([x["f_sl"] for x in fs])
_sd = (_m([x["f_tp"] ** 2 for x in fs]) - _m([x["f_tp"] for x in fs]) ** 2) ** 0.5 * (_m([x["f_sl"] ** 2 for x in fs]) - _m([x["f_sl"] for x in fs]) ** 2) ** 0.5
check(abs(_kov / _sd) < 0.12, f"TP- und SL-Faktor unkorreliert (r = {_kov / _sd:+.3f})")
check(0.5 < _m([x["f_lots"] for x in fs]) < 0.6, f"Faktor im Mittel ≈ 55 % ({_m([x['f_lots'] for x in fs]):.3f})")

print("── 2. Zahlenbeispiele (Normal-Trade = Spannen-Mitte) ──")
w = normal(FN, 100000.0, ppl=PPL["fn"])
check((w["menge"], w["tp"], w["sl"], w["stufe"]) == (2.7, 6300, 2700, "Etappe"), f"FundedNext Ph1 100k normal: 2,7 Lots · TP 6.300 · SL 2.700 ({w['menge']}, {w['tp']}, {w['sl']})")
a = ruf("rv_anwenden", w, fk(0.2, 0.9, 0.5), 0.1, PPL["fn"])
check((a["menge"], a["tp"], a["sl"], a["risiko"]) == (1.3, 1260, 2430, 2430), f"FN TP 20 / SL 90 / Lots 50 % → 1,35 abgerundet 1,3 Lots · TP 1.260 · SL 2.430 ({a['menge']}, {a['tp']}, {a['sl']})")
check(a["range"]["tp_pkt"] == 96.9 and a["range"]["sl_pkt"] == 186.9, f"   Punkte ändern sich: TP 96,9 / SL 186,9 Pkt ({a['range']['tp_pkt']} / {a['range']['sl_pkt']})")
check(a["stufe"] == "Etappe · Range-Würfel TP 20 % · SL 90 % · Lots 48 %", f"   Stufe zeigt die wirklichen Anteile (Lots 1,3 ÷ 2,7 = 48 %): {a['stufe']}")
b = ruf("rv_anwenden", w, fk(1.0, 0.1, 0.1), 0.1, PPL["fn"])
check((b["menge"], b["tp"], b["sl"]) == (0.2, 6300, 270), f"FN TP 100 / SL 10 / Lots 10 % → 0,27 abgerundet 0,2 Lots · TP 6.300 · SL 270 ({b['menge']}, {b['tp']}, {b['sl']})")
w5 = normal(T5, 100000.0, ppl=PPL["t5"])
check((w5["menge"], w5["tp"], w5["sl"]) == (25, 5850, 1980), f"The5%ers 100k normal: 25 Lots · TP 5.850 · SL 1.980 ({w5['menge']}, {w5['tp']}, {w5['sl']})")
c = ruf("rv_anwenden", w5, fk(0.1, 0.1, 1.0), 1, PPL["t5"])
check((c["menge"], c["tp"], c["sl"]) == (25, 585, 250) and c["range"]["sl_angehoben"] and not c["range"]["tp_angehoben"],
      f"The5%ers TP 10 / SL 10 / Lots 100 % → SL 198 $ wären 7,9 Pkt → auf 10 Pkt = 250 $ angehoben ({c['menge']}, {c['tp']}, {c['sl']})")
c2 = ruf("rv_anwenden", w5, fk(0.5, 0.5, 0.13), 1, PPL["t5"])
check(c2["menge"] == 3 and isinstance(c2["menge"], int), f"The5%ers Lots 13 % → 3,25 abgerundet 3 (Raster 1, ganzzahlig) ({c2['menge']!r})")
wf = normal(FT, 100000.0, ppl=PPL["ft"])
check((wf["menge"], wf["tp"], wf["sl"]) == (30, 5850, 2272), f"FTMO 100k normal: 30 Lots · TP 5.850 · SL 2.272 ({wf['menge']}, {wf['tp']}, {wf['sl']})")
d = ruf("rv_anwenden", wf, fk(0.5, 0.5, 0.5), 1, PPL["ft"])
check((d["menge"], d["tp"], d["sl"]) == (15, 2925, 1136), f"FTMO alle 50 % → 15 Lots · TP 2.925 · SL 1.136 ({d['menge']}, {d['tp']}, {d['sl']})")
d2 = ruf("rv_anwenden", wf, fk(0.1, 0.1, 0.01), 1, PPL["ft"])
check(d2["menge"] == 1, f"FTMO Lots 1 % → mindestens ein Schritt (1 Lot) ({d2['menge']})")

print("── 3. Nur die Etappe, Boden, Hedge ──")
wl = normal(FN, 106000.0, ppl=PPL["fn"])
check(wl["stufe"].startswith("letzter Trade") and ruf("rv_anwenden", wl, fk(0.1, 0.1, 0.1), 0.1, PPL["fn"]) is wl, f"letzter Trade (Rest bis Ziel) bleibt ({wl['stufe']})")
wk, _g = ruf("ap_konto_rechnen", FN, "phase1", 107950.0, dict(MITTE), ppl=PPL["fn"])
check(bool(wk) and ruf("rv_anwenden", wk, fk(0.1, 0.1, 0.1), 0.1, PPL["fn"]) is wk, f"Klein-Trade bleibt ({(wk or {}).get('stufe')})")
check(ruf("rv_anwenden", w, None, 0.1, PPL["fn"]) is w and ruf("rv_anwenden", w, fk(0.5, 0.5, 0.5), 0.1, None) is w, "ohne Faktoren / ohne Punktwert → unverändert")
wb = normal(FN, 91500.0, ppl=PPL["fn"])
hb = f", SL hinter den Boden (+{ns['AP_SL_HINTER_BODEN']} $)"
check(wb["sl"] == 1550 and hb in wb["stufe"], f"FN 91.500: SL hinter den Boden 1.550 ({wb['sl']}, {wb['stufe']})")
e1 = ruf("rv_anwenden", wb, fk(0.5, 0.5, 0.5), 0.1, PPL["fn"])
check(e1["sl"] == 775 and hb not in e1["stufe"], f"SL 50 % = 775 liegt vor dem Boden → Zusatz „hinter den Boden“ weg ({e1['stufe']})")
e2 = ruf("rv_anwenden", wb, fk(0.5, 0.99, 0.5), 0.1, PPL["fn"])
check(e2["sl"] > 1500 and hb in e2["stufe"], f"SL 99 % = {e2['sl']} weiter hinter dem Boden → Zusatz bleibt")
# (d) Fusion-Hedge folgt dem Master: Lots ∝ Master-Lots, slave_risk ∝ Master-SL (Multiplier aus Plänen der letzten 5 Tage: The5%ers 0,0082, FN 0,28)
for name, mult, wn, an in (("The5%ers", 0.0082, w5, ruf("rv_anwenden", w5, fk(0.3, 1.0, 0.1), 1, 1.0)), ("FundedNext", 0.28, w, b)):
    hn, _ = ruf("eh_hedge", mult, wn["menge"], 1.0, 1.0, wn["sl"], 1.0, 0.01)
    hk, gk = ruf("eh_hedge", mult, an["menge"], 1.0, 1.0, an["sl"], 1.0, 0.01)
    check(hk is not None and hk["lots"] >= 0.01, f"{name}: kleinster Trade {an['menge']} Lots → Hedge {hk and hk['lots']} Lot ≥ 0,01 ({gk or 'ok'})")
    check(hk and abs(hk["lots"] - mult * an["menge"]) <= 0.005 and abs(hk["slave_risk"] - mult * an["sl"]) < 0.01,
          f"{name}: Hedge {hn['lots']} → {hk and hk['lots']} Lot, Slave-Risiko {hn['slave_risk']} → {hk and hk['slave_risk']} (folgt Lots und SL)")

print("── 4. Planer-Haken: nur Echo-CFD-Challenge, Einstellung je Unternehmen ──")
KTX = {"ok": True, "gid_von": {"uid-emin": "gid-emin"}}
WERTE = {("challenge_cfd", ""): {"pct": 100.0, "von": 10.0, "bis": 100.0}}
a_ht = {"id": "konto-ht", "user_id": "uid-ht", "account_type": "phase1"}
h1 = ruf("rv_planer_haken", w, a_ht, FN, "2026-11-12", PPL["fn"], WERTE, KTX)
fx = ruf("rv_faktoren", "challenge_cfd", "konto-ht", "2026-11-12", 100, 10, 100)
check(h1 is not w and h1["range"]["f_tp"] == fx["f_tp"] and h1["menge"] <= w["menge"], f"HT 100 % → klein mit den Konto-Faktoren ({h1['stufe']})")
check(ruf("rv_planer_haken", w, dict(a_ht, user_id="uid-emin"), FN, "2026-11-12", PPL["fn"], WERTE, KTX) is w, "Unternehmen ohne eigene Zeile → aus (erbt HT nicht)")
check(ruf("rv_planer_haken", w, dict(a_ht, account_type="challenge"), FN, "2026-11-12", PPL["fn"], WERTE, KTX) is w, "Futures-Challenge (Kontoart challenge) → unverändert")
check(ruf("rv_planer_haken", w, a_ht, dict(FN, route="tvv2"), "2026-11-12", PPL["fn"], WERTE, KTX) is w, "Route Orbit (tvv2) → unverändert")
check(ruf("rv_planer_haken", w, a_ht, FN, "2026-11-12", PPL["fn"], {}, KTX) is w, "Tabelle leer/fehlt → aus")
check(ruf("rv_planer_haken", w, a_ht, FN, "2026-11-12", PPL["fn"], WERTE, {"ok": False}) is w, "Unternehmens-Kontext nicht lesbar → aus")
w50 = dict(normal(dict(FN, je_groesse={"50000": {"phasen": {"phase1": dict(FN["phasen"]["phase1"], menge=[1, 1.5], menge_schritt=0.5)}}}), 50000.0, ppl=PPL["fn"]))
h50 = ruf("rv_planer_haken", w50, a_ht, dict(FN, je_groesse={"50000": {"phasen": {"phase1": dict(FN["phasen"]["phase1"], menge=[1, 1.5], menge_schritt=0.5)}}}),
          "2026-11-12", PPL["fn"], WERTE, KTX)
check(abs(h50["menge"] / 0.5 - round(h50["menge"] / 0.5)) < 1e-9, f"Raster je Kontogröße (je_groesse 50k, Schritt 0,5) → {h50['menge']} Lots")
# Folge-Haupt (tt_folge_rechnen): der Beleg am Plan (kette.range) taugt als Faktoren und gibt bei gleicher Balance dieselben Werte
h2 = ruf("rv_anwenden", w, h1["range"], 0.1, PPL["fn"])
check((h2["menge"], h2["tp"], h2["sl"]) == (h1["menge"], h1["tp"], h1["sl"]), "kette.range als Faktoren → derselbe Haupt-Trade (Folge-Teil)")

print("── 5. Zufalls-Prüfung je Firma (je Lauf neue Stichprobe) ──")
rnd = random.Random()
for name, regel, ppl, schritt, bal_von, bal_bis in (("FundedNext", FN, 10.0, 0.1, 90500, 101000), ("The5%ers", T5, 1.0, 1, 90500, 101000),
                                                     ("FTMO", FT, 1.0, 1, 90500, 103000)):
    verstoss, n_et = [], 0
    for _ in range(1500):
        u = {x: rnd.random() for x in ("tp", "sl", "menge", "puffer")}
        bal = round(rnd.uniform(bal_von, bal_bis), 2)
        w0, g0 = ruf("ap_konto_rechnen", regel, "phase1", bal, u, ppl=ppl)
        if not w0:
            continue
        f = fk(round(rnd.uniform(0.1, 1), 4), round(rnd.uniform(0.1, 1), 4), round(rnd.uniform(0.1, 1), 4))
        w1 = ruf("rv_anwenden", w0, f, schritt, ppl)
        if not str(w0["stufe"]).startswith("Etappe"):
            if w1 is not w0:
                verstoss.append(("nicht-Etappe verändert", w0["stufe"]))
            continue
        n_et += 1
        m = float(w1["menge"])
        tpp, slp = w1["tp"] / (m * ppl), w1["sl"] / (m * ppl)
        if not (m <= w0["menge"] + 1e-9 and m >= schritt - 1e-9 and abs(m / schritt - round(m / schritt)) < 1e-6):
            verstoss.append(("Lots", w0["menge"], m))
        if m > w0["menge"] * f["f_lots"] + 1e-9 and m != schritt:
            verstoss.append(("Lots nicht abgerundet", w0["menge"], f["f_lots"], m))
        if w1["tp"] > w0["tp"] or w1["sl"] > w0["sl"] or w1["risiko"] != w1["sl"]:
            verstoss.append(("über dem normalen Wert", w0["tp"], w1["tp"], w0["sl"], w1["sl"]))
        if (tpp < MIN - 1e-6 and w1["tp"] != w0["tp"]) or (slp < MIN - 1e-6 and w1["sl"] != w0["sl"]):
            verstoss.append(("enger als Mindest-Pkt", tpp, slp))
        if not w1["range"]["tp_angehoben"] and abs(w1["tp"] - w0["tp"] * f["f_tp"]) > 0.51:
            verstoss.append(("TP ≠ Faktor", w0["tp"], f["f_tp"], w1["tp"]))
        if not w1["range"]["sl_angehoben"] and abs(w1["sl"] - w0["sl"] * f["f_sl"]) > 0.51:
            verstoss.append(("SL ≠ Faktor", w0["sl"], f["f_sl"], w1["sl"]))
        if hb in w1["stufe"] and w1["sl"] <= w0["sl"] - ns["AP_SL_HINTER_BODEN"]:
            verstoss.append(("Boden-Zusatz falsch", w0["sl"], w1["sl"]))
        if ns["RV_STUFE"] not in w1["stufe"]:
            verstoss.append(("Stufe ohne Range-Würfel", w1["stufe"]))
    check(n_et > 300 and not verstoss, f"{name}: {n_et} Etappen × Zufalls-Faktoren — nie über dem Normal-Trade, Raster, ≥ {MIN:g} Pkt, Boden-Zusatz {verstoss[:2]}")

print("── 6. Einbau in app.py ──")
ap = re.search(r"^def ap_planen\(.*?(?=^def )", app, re.S | re.M).group(0)
i_rv, i_tt, i_tf = ap.find("rv_planer_haken("), ap.find("tt_planer_haken("), ap.find("ap_tradeify_final_halten(")
check(0 < i_rv < i_tf < i_tt, "ap_planen: Range-Würfel nach dem Rechnen, vor Tradeify-final und Trades pro Tag")
check('range=w["range"]' in ap and '_b["kette"] = dict(_b["kette"], range=w["range"])' in ap, "Plan-Zeile: mt5_baseline.range und kette.range")
check(re.search(r'"abstand_mll", "tag", "range"\)', app) is not None, "Folge-Teil trägt kette.range weiter (_tt_zeile)")
check(re.search(r'w_h = rv_anwenden\(w_h, k\["range"\]', app) is not None, "Folge-Haupt mit denselben Faktoren (tt_folge)")
check("rv_" not in re.search(r"^def gp_planen\(.*?(?=^def )", app, re.S | re.M).group(0), "Gruppen-Planer (gp_planen) unberührt (wie TW1)")
check("planer_range_wuerfel" not in re.search(r"^def tw_werte\(.*?(?=^def )", app, re.S | re.M).group(0), "Handels-Würfel liest seine Tabelle unverändert")

print()
if fehler:
    print(f"ROT: {len(fehler)} Prüfung(en) fehlgeschlagen")
    sys.exit(1)
print("GRÜN: alle Prüfungen bestanden")
