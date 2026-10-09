#!/usr/bin/env python3
"""Selbsttest: eigener Zufall je Konto im Auto-Planer (app.py ap_planen + ap_konto_rechnen, Finn 09.10.2026 ~07:45 Dubai: „Zu bestätigen"
Finn+Pascal, vier Tradeify-150k-Challenges einer ID alle TP 3.450 $ und 2 NQ; in der DB je ID×Firma identisch, z. B. 4× 3.521 / 3 NQ).
Ursache war ein Zufallswert je Tranche (ID × Firma), den alle Konten teilten. Rein rechnend, ohne Netz.
Aufruf: python3 tools/selftest_auto_zufall_je_konto.py
Prueft: (1) die Tranchen-Schleife zieht u je Konto (kein geteiltes u mehr); (2) 10 Konten gleicher ID×Firma (Futures, Regel wie Tradeify
150k Challenge: TP 3.450–3.550, 2–3 NQ) → 10 verschiedene TP, alle in der Spanne, ganze Kontrakte, beide Größen kommen vor; (3) CFD
(Lots 1,50–3,00, Schritt 0,01) → verschiedene Lots auf 0,01, in der Spanne; (4) Rest bis Ziel kappt weiter (letzter Trade)."""
import os
import random
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_wd_num", "ap_groesse", "_ap_spanne", "_ap_runden", "ap_kw_param", "_ap_boden", "ap_boden_konto", "ap_kette_regel", "ap_kette_mll",
              "ap_kette_trade1", "ap_konto_rechnen", "ap_klein_trade", "_ap_de", "liq_peak", "_ap_peaks", "ap_boden_sicher")
KONSTANTEN = ("AP_REST_MIN", "AP_REST_MIN_CFD", "AP_KLEIN_PKT", "AP_KLEIN_PUFFER", "AP_KLEIN_SCHRITT", "AP_KLEIN_TP_PKT_HINWEIS", "AP_PUFFER_PKT",
              "AP_CFD_ROUTEN", "AP_GROESSE_TOLERANZ", "AP_KETTE_STANDARD", "AP_KETTE_TXT", "AP_SL_HINTER_BODEN")
FEHLER = []


def check(ok, name):
    print(("OK  " if ok else "FEHL") + " " + name)
    if not ok:
        FEHLER.append(name)


SRC = open(APP, encoding="utf-8").read()
ns = {"re": re}
teile = [re.search(rf"^{k} = .*$", SRC, re.M).group(0) for k in KONSTANTEN]
for name in FUNKTIONEN:
    i = SRC.index(f"\ndef {name}(") + 1
    teile.append(SRC[i:SRC.find("\n\n\n", i)])
exec("\n".join(teile), ns)
rechnen = ns["ap_konto_rechnen"]

# (1) Quelle: in der Tranchen-Schleife wird u je Konto gezogen
i = SRC.index("\ndef ap_planen(")
plan = SRC[i:SRC.find("\n\n\ndef ", i + 10)]
sch = plan[plan.index("    for key, liste in tranchen.items():"):plan.index("rechnung.append((k, w))")]
check('u_k = {x: rnd.random() for x in ("tp", "sl", "menge", "puffer")}\n' in sch and " else u" not in sch
      and "\n        u = {" not in sch, "Tranchen-Schleife: Zufall je Konto, kein geteiltes u je ID×Firma")

# (2) Futures wie Tradeify 150k Challenge (Werte aus auto_plan_regeln, 09.10.2026)
TF = {"route": "tvv2", "symbol": "NQ", "groessen": [150000], "boden": "nachziehend", "dd_usd": 4500, "ziel_pct": {"challenge": 6},
      "phasen": {"challenge": {"tp": [3450, 3550], "tp_max": 3600, "menge": [2, 3], "menge_schritt": 1, "sl": None, "dd_usd": 4500,
                               "ziel_pct": 6, "puffer_je_menge": {"2": [15, 25], "3": [25, 40]}}}}
rnd = random.Random(20261009)
check("w.get(\"tp\") not in tps_tranche" in sch.replace("'", '"') and "for _ in range(20):" in sch and "tps_tranche.add(" in sch,
      "Tranchen-Schleife: gleicher TP in derselben ID×Firma → neu ziehen (höchstens 20×), gekappte bleiben")
erg, tps_tranche = [], set()
for _ in range(10):                  # wie die Schleife in ap_planen: je Konto ziehen, bei gleichem TP neu
    u = {x: rnd.random() for x in ("tp", "sl", "menge", "puffer")}
    w, grund = rechnen(TF, "challenge", 150000.0, u)
    for _n in range(20):
        if grund or not w or w.get("tp") not in tps_tranche or "letzter Trade" in str(w.get("stufe") or ""):
            break
        u = {x: rnd.random() for x in ("tp", "sl", "menge", "puffer")}
        w, grund = rechnen(TF, "challenge", 150000.0, u)
    if w and not grund:
        tps_tranche.add(w.get("tp"))
    erg.append(w if not grund else {"grund": grund})
tps = [w.get("tp") for w in erg]
mengen = [w.get("menge") for w in erg]
check(all(isinstance(t, int) and 3450 <= t <= 3550 for t in tps), f"Futures: alle TP in 3.450–3.550 ({tps})")
check(len(set(tps)) == 10, f"Futures: 10 Konten → 10 verschiedene TP ({len(set(tps))} verschiedene)")
check(all(m in (2, 3) for m in mengen) and set(mengen) == {2, 3}, f"Futures: ganze Kontrakte 2–3, beide kommen vor ({mengen})")
check(any(t % 50 for t in tps), "TP nicht auf glatte 50 gerundet")

# (3) CFD: Lots in 0,01-Schritten
CFD = {"route": "mt5v2", "groessen": [100000], "boden": "statisch", "dd_pct": 10, "ziel_pct": {"phase1": 10},
       "phasen": {"phase1": {"tp": [2800, 3200], "menge": [1.5, 3.0], "menge_schritt": 0.01, "sl": [2000, 2600], "boden_pct": 10}}}
lots, tps_c = [], []
for _ in range(10):
    u = {x: rnd.random() for x in ("tp", "sl", "menge", "puffer")}
    w, grund = rechnen(CFD, "phase1", 100000.0, u, ppl=1.0)
    if not grund:
        lots.append(w["menge"]); tps_c.append(w["tp"])
check(len(lots) == 10 and all(1.5 <= x <= 3.0 and abs(round(x * 100) - x * 100) < 1e-6 for x in lots), f"CFD: Lots 1,50–3,00 auf 0,01 ({lots})")
check(len(set(lots)) >= 8 and len(set(tps_c)) >= 8, f"CFD: Lots/TP streuen je Konto ({len(set(lots))} Lots, {len(set(tps_c))} TP verschieden)")

# (4) Kappung bleibt: kurz vor dem Ziel = Rest + Puffer, nicht die Spanne
w, grund = rechnen(TF, "challenge", 157000.0, {"tp": 0.9, "sl": 0.5, "menge": 0.1, "puffer": 0.5})
check(not grund and w["tp"] < 3450 and "letzter Trade" in w["stufe"], f"Rest bis Ziel kappt weiter (Balance 157.000 → TP {w and w.get('tp')}, {w and w.get('stufe')})")

print("\nALLES GRÜN" if not FEHLER else f"\nFEHLER: {FEHLER}")
sys.exit(1 if FEHLER else 0)
