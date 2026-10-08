#!/usr/bin/env python3
"""Selbsttest: eigene Planer-Werte je Kontogröße (app.py ap_konto_rechnen, regel.je_groesse, 08.10.2026 — Finn: FundingPips 50k mit
eigenem SL/Lots/Puffer; korrigiert: 50k sind FLEX-Konten — Ziel P1 10 %, Max-Verlust 12 %, SL 1.250–1.500, Lots 0,5–0,7,
TP 2.500–3.000, Puffer 75–100). Rein rechnend, ohne Netz. Werte wie Finns Angabe, Konten frei erfunden.
Aufruf: python3 tools/selftest_auto_je_groesse.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_wd_num", "ap_groesse", "_ap_spanne", "_ap_runden", "_ap_boden", "ap_konto_rechnen", "ap_kw_param", "ap_boden_konto")
KONSTANTEN = ("AP_REST_MIN", "AP_GROESSE_TOLERANZ")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re}
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in KONSTANTEN]
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


FP = {"namen": ["fundingpips"], "boden": "statisch", "route": "mt5v2", "dd_pct": 10, "groessen": [50000, 100000],
      "kauf_eur": {"50000": 240, "100000": 464}, "ziel_pct": {"phase1": 8, "phase2": 5},
      "phasen": {"phase1": {"sl": [2500, 3500], "tp": [3500, 4000], "menge": [1, 1.5], "puffer": [50, 75], "tp_max": 4000,
                            "ziel_pct": 8, "boden_pct": 10, "menge_schritt": 0.1},
                 "phase2": {"sl": [2500, 3500], "tp": [2000, 2500], "menge": [1, 1.5], "puffer": [50, 75], "tp_max": 2500,
                            "ziel_pct": 5, "boden_pct": 10, "menge_schritt": 0.1}},
      "je_groesse": {"50000": {"ziel_pct": {"phase1": 10, "phase2": 5}, "dd_pct": 12, "phasen": {
          "phase1": {"sl": [1250, 1500], "tp": [2500, 3000], "menge": [0.5, 0.7], "menge_schritt": 0.01, "puffer": [75, 100],
                     "boden_pct": 12},
          "phase2": {"sl": [1250, 1500], "tp": [2500, 3000], "menge": [0.5, 0.7], "menge_schritt": 0.01, "puffer": [75, 100],
                     "boden_pct": 12}}}}}


def main():
    ns = lade()
    rechnen = ns["ap_konto_rechnen"]
    f = []
    ok = lambda b, t: f.append(t) if not b else None
    mitte = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}

    # 50k Flex Phase 1, Balance 48.916: Ziel 55.000 (10 %), Boden 44.000 (12 %), eigene Werte, Etappe mit TP 2.500–3.000
    w, g = rechnen(FP, "phase1", 48916.0, mitte)
    ok(g is None, f"50k P1 ohne Grund erwartet, kam {g}")
    ok(w and w["groesse"] == 50000, f"Größe 50k erwartet: {w}")
    ok(w and abs(w["ziel"] - 55000) < 0.01, f"Ziel 55.000 (10 %) erwartet: {w}")
    ok(w and w["sl"] == 1375, f"SL Mitte 1.375 erwartet: {w}")
    ok(w and abs(w["menge"] - 0.6) < 1e-9, f"Lots Mitte 0,6 erwartet: {w}")
    ok(w and w["puffer"] == 88, f"Puffer Mitte 87,5 → 88 erwartet: {w}")
    ok(w and w["tp"] == 2750 and w["stufe"] == "Etappe", f"TP Mitte 2.750 als Etappe erwartet: {w}")
    w0, _ = rechnen(FP, "phase1", 48916.0, {"tp": 0, "sl": 0, "menge": 0, "puffer": 0})
    w1, _ = rechnen(FP, "phase1", 48916.0, {"tp": 1, "sl": 1, "menge": 1, "puffer": 1})
    ok(w0 and w0["sl"] == 1250 and abs(w0["menge"] - 0.5) < 1e-9 and w0["tp"] == 2500, f"Untergrenze: {w0}")
    ok(w1 and w1["sl"] == 1500 and abs(w1["menge"] - 0.7) < 1e-9 and w1["tp"] == 3000, f"Obergrenze: {w1}")
    # SL-Deckel am Flex-Boden 44.000: Balance 45.000 → SL höchstens 1.000 (mit 10 % wäre der Boden 45.000 → geblowt)
    wb, gb = rechnen(FP, "phase1", 45000.0, mitte)
    ok(gb is None and wb and wb["sl"] == 1000, f"SL auf Flex-Boden gekappt erwartet (1.000): {wb} {gb}")
    # letzter Trade: Rest < TP-Obergrenze → TP = Rest + Puffer
    wl, _ = rechnen(FP, "phase1", 53000.0, mitte)
    ok(wl and wl["tp"] == 2000 + 88, f"letzter Trade Rest + Puffer erwartet: {wl}")
    # 50k Phase 2: Ziel 52.500 (5 %)
    w2, g2 = rechnen(FP, "phase2", 50200.0, mitte)
    ok(g2 is None and w2 and abs(w2["ziel"] - 52500) < 0.01, f"50k P2: {w2} {g2}")
    # Balance-Balken zeigt denselben Flex-Boden
    bk = ns["ap_boden_konto"](FP, "phase1", 48916.0)
    ok(bk and abs((bk.get("boden") or 0) - 44000) < 0.01, f"Balken-Boden 44.000 erwartet: {bk}")
    bk100 = ns["ap_boden_konto"](FP, "phase1", 101000.0)
    ok(bk100 and abs((bk100.get("boden") or 0) - 90000) < 0.01, f"100k-Boden 90.000 erwartet: {bk100}")
    # 100k bleibt bei den 100k-Werten
    wh, gh = rechnen(FP, "phase1", 101000.0, mitte)
    ok(gh is None and wh and wh["groesse"] == 100000 and wh["sl"] == 3000 and abs(wh["menge"] - 1.2) < 1e-9,
       f"100k unverändert erwartet (SL 3.000, Lots 1,2): {wh} {gh}")
    # Kein Rückfall: 50k-Override ohne phase2 → Grund statt 100k-Werte
    import copy
    fp2 = copy.deepcopy(FP)
    del fp2["je_groesse"]["50000"]["phasen"]["phase2"]
    w3, g3 = rechnen(fp2, "phase2", 50200.0, mitte)
    ok(w3 is None and g3 and "50k" in g3, f"ohne 50k-Phase-2 Grund erwartet, kam {w3} {g3}")
    # Ohne je_groesse und ohne 50k in groessen: wie bisher „passt zu keiner Kontogröße"
    fp3 = copy.deepcopy(FP)
    fp3.pop("je_groesse")
    fp3["groessen"] = [100000]
    w4, g4 = rechnen(fp3, "phase1", 48916.0, mitte)
    ok(w4 is None and "Kontogröße" in (g4 or ""), f"alter Weg erwartet: {g4}")
    # Ziel erreicht (FundedNext-50k-Fall 54.019 bei 5 % → 52.500)
    w5, g5 = rechnen(FP, "phase2", 54019.0, mitte)
    ok(w5 is None and "Ziel erreicht" in (g5 or ""), f"Ziel erreicht erwartet: {g5}")

    if f:
        print("ROT:")
        for t in f:
            print(" -", t)
        sys.exit(1)
    print("selftest_auto_je_groesse: alle Prüfungen grün")


if __name__ == "__main__":
    main()
