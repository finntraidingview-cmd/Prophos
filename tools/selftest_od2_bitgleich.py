#!/usr/bin/env python3
"""Diff-Test OD2 (17.11.2026, Prüfer S2): Nicht-On-Demand-Konten (FundedNext, The5ers, Blue Guardian, FTMO, FundingPips — normal und mit Striking)
rechnen in fcp_konto_rechnen bitgleich wie vor OD2. Vergleicht die app.py dieser Kopie mit der app.py eines Referenz-Commits (Standard b7d17749 =
origin/main vor OD2, holt sie per `git show` in ein Temp-Verzeichnis). Gleiches Ergebnis-dict (JSON) UND gleicher Zufalls-Verbrauch je Fall.
On Demand soll sich dagegen dort ändern, wo Netto-Profit ≠ Summe der Gewinn-Tage (nur gezählt, kein Fehler).
Aufruf: python3 tools/selftest_od2_bitgleich.py [referenz-commit]"""
import copy
import json
import os
import random
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
REF = sys.argv[1] if len(sys.argv) > 1 else "b7d17749"

tmp = tempfile.mkdtemp(prefix="od2_ref_")
with open(os.path.join(tmp, "app_alt.py"), "wb") as f:
    f.write(subprocess.check_output(["git", "-C", WURZEL, "show", f"{REF}:app.py"]))
sys.path.insert(0, WURZEL)
sys.path.insert(0, tmp)
import app as neu  # noqa: E402
import app_alt as alt  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


FN = {"an": True, "name": "FundedNext", "namen": ["fundednext"], "tp_deckel_plus": 1000,
      "erster_payout": {"ziel": [50, 150], "hedge_eur_je_dd": 0.5, "lots_faktor": 0.1},
      "je_groesse": {"100000": {"dd": 10000, "sl": [2000, 2300], "sl_1pct": [700, 780], "lots": [1.0, 1.75], "ziel": [5000, 5500], "hedge_eur": 1500}}}
T5 = {"an": True, "name": "The5%ers", "namen": ["the5ers"], "tp_modus": "consistency50", "tp_zyklen": [750, 1500, 3000, 6000],
      "je_groesse": {"100000": {"dd": 10000, "sl": [1000, 1200], "lots": [1.0, 1.4], "ziel": [1300, 1500], "hedge_eur": 1000, "tp_erster": 750}}}
BG = {"an": True, "name": "Blue Guardian", "namen": ["blueguardian"], "erster_payout": {"ziel": [50, 100], "hedge_eur_je_dd": 0.5},
      "je_groesse": {"100000": {"dd": 8000, "sl": [1500, 1800], "lots": [1.0, 1.2], "ziel": [1000, 1200], "hedge_eur": 1000,
                                "gewinntage": {"anzahl": 3, "min": 500, "tp": [550, 650]}}}}
FT = {"an": True, "name": "FTMO", "namen": ["ftmo"], "je_groesse": {"100000": {"dd": 10000, "sl": [1500, 2000], "lots": [1.0, 1.5], "ziel": [1500, 2500], "hedge_eur": 1200}}}
FP = {"an": True, "name": "FundingPips", "namen": ["fundingpips"], "je_groesse": {"100000": {"dd": 10000, "sl": [1500, 2000], "lots": [1.0, 1.5], "ziel": [1500, 2500], "hedge_eur": 1200}}}
G = 100000.0
TAGE = (None, (0.0, 0), (500.0, 1), {"b": 1960.56, "w": 6486.58, "n": 7, "serie": 2745.87, "serie_n": 3, "heute": 0.0},
        {"b": 800, "w": 2200, "n": 3, "serie": 2200, "serie_n": 3, "heute": 300.0})


def regel_fuer(mod, regel, jg, art):
    if art == "striking":
        x = mod.fcp_striking_anwenden(regel, jg, G)
        return (x[0], x[1]) if x else None
    return regel, jg


def j(x):
    return json.dumps(x, sort_keys=True, default=str)


print(f"— Bitgleich gegen {REF} (Nicht-On-Demand, normal + Striking) —")
faelle = abw = 0
beisp = []
for regel in (FN, T5, BG, FT, FP):
    for art in ("normal", "striking"):
        jg0 = neu.fcp_je_groesse(regel, G)
        a_ = regel_fuer(alt, copy.deepcopy(regel), copy.deepcopy(jg0), art)
        n_ = regel_fuer(neu, copy.deepcopy(regel), copy.deepcopy(jg0), art)
        if a_ is None and n_ is None:
            continue
        if j(a_) != j(n_):
            abw += 1
            beisp.append(("Regel", regel["namen"][0], art))
            continue
        rk, jg = n_
        for bal in (G - 3000, G - 200, G, G + 300, G + 700, G + 1250, G + 2226.83, G + 4000, G + 6000):
            for zyk in (1, 2, 3):
                for tage in TAGE:
                    for gti in (None, (0, 3), (3, 3), (2, 7), (7, 7)):
                        for zf in (None, {}, {"zyklus": zyk, "usd": 2161}):
                            for seed in (1, 42):
                                kw = dict(regel=rk, gewinne=None, gewinntage=gti, tage=tage, max_sl=900 if art == "striking" else None)
                                ra, rn = random.Random(seed), random.Random(seed)
                                A = alt.fcp_konto_rechnen(copy.deepcopy(jg), bal, G, zyk, False, 1.0, 0.85, ra, ziel_fest=copy.deepcopy(zf), **kw)
                                B = neu.fcp_konto_rechnen(copy.deepcopy(jg), bal, G, zyk, False, 1.0, 0.85, rn, ziel_fest=copy.deepcopy(zf), **kw)
                                faelle += 1
                                if j(A) != j(B) or ra.random() != rn.random():
                                    abw += 1
                                    if len(beisp) < 3:
                                        beisp.append((regel["namen"][0], art, bal, zyk, tage, gti, zf))
ok(faelle > 20000 and abw == 0, f"{faelle} Fälle, {abw} Abweichungen {beisp}")

print("— On Demand (soll sich ändern, wo Netto ≠ Summe der Gewinn-Tage) —")
od_f = od_d = 0
for bal in (G - 3000, G, G + 700, G + 2226.83, G + 4000):
    for tage in ((0.0, 0), {"b": 1960.56, "w": 6486.58, "n": 7, "serie": 2745.87, "serie_n": 3, "heute": 0.0}):
        for seed in (1, 2):
            rk, jgo = neu.fcp_on_demand_anwenden(FN, neu.fcp_je_groesse(FN, G), G)
            A = alt.fcp_konto_rechnen(jgo, bal, G, 1, False, 1.0, 0.85, random.Random(seed), regel={k: v for k, v in rk.items() if k != "consistency_basis"},
                                      tage=tage, ziel_fest={"zyklus": 1, "usd": 2161})
            B = neu.fcp_konto_rechnen(jgo, bal, G, 1, False, 1.0, 0.85, random.Random(seed), regel=rk, tage=tage, ziel_fest={"zyklus": 1, "usd": 2161})
            od_f += 1
            od_d += (A.get("aktion"), A.get("tp")) != (B.get("aktion"), B.get("tp"))
print(f"  {od_f} Fälle, {od_d} mit anderem Urteil/TP (erwartet > 0)")
ok(od_d > 0, "On Demand rechnet anders als vor OD2")

print()
print("FEHLER:" if FEHLER else "ALLES OK", FEHLER if FEHLER else "")
sys.exit(1 if FEHLER else 0)
