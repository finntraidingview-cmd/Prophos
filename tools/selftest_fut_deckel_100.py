#!/usr/bin/env python3
"""Selbsttest FUTURES-LETZTER-TRADE-DECKEL-100 (app.py ap_konto_rechnen, 21.10.2026, Slave-Terminal 3 — Finn 03:20 Dubai: „Bei CFDs lassen
wie es ist. Bei Futures darf der letzte Trade den TP-Deckel um bis zu 100 $ überschreiten, damit er am Ziel landet — mehr nicht, es soll in
meiner Range bleiben." Vorfall Lucid 150k …0001 20.10.2026: Rest 4.537 > Deckel 4.500 → Etappe TP 4.464 → 84 $ Rest von Hand).
Rein rechnend, ohne Netz; Regeln wie auto_plan_regeln, Konten erfunden. Fälle: Lucid Rest 4.537 → letzter Trade TP 4.577 (Rest + 40 $ Puffer
für 2 NQ, ≤ 4.600); Rest 4.590 → TP auf 4.600 gekappt; Rest 4.480 (+40 über dem Deckel) → TP 4.520 statt „auf Tageshöchstwert gedeckelt";
Rest 4.650 → Etappe wie bisher; Rest 4.000 → normaler letzter Trade unverändert; CFD (FundingPips tp_max 4.000) Rest 4.050 → Etappe und
Rest 3.980 → „auf Tageshöchstwert gedeckelt" — beides unverändert. Aufruf: python3 tools/selftest_fut_deckel_100.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_wd_num", "_ap_norm", "ap_groesse", "_ap_spanne", "_ap_runden", "_ap_boden", "ap_kette_regel", "ap_kette_mll",
              "ap_kette_trade1", "ap_kw_param", "ap_konto_rechnen", "ap_klein_trade", "ap_klein_trade_fut", "_ap_de")
KONSTANTEN = ("AP_REST_MIN", "AP_REST_MIN_CFD", "AP_KLEIN_PKT", "AP_KLEIN_PUFFER", "AP_KLEIN_SCHRITT", "AP_KLEIN_TP_PKT_HINWEIS",
              "AP_PUFFER_PKT", "AP_PUFFER_PKT_FUT", "AP_PUFFER_JE_KT_FUT", "AP_GEBUEHR_JE_KT_FUT", "AP_PUNKTWERT_FUT", "AP_FUT_DECKEL_PLUS_USD",
              "AP_CFD_ROUTEN", "AP_GROESSE_TOLERANZ", "AP_KETTE_STANDARD", "AP_KETTE_TXT", "AP_SL_HINTER_BODEN", "AP_MINI_FUTURES_SYMBOL")
FEHLER = []


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "_firm_norm": lambda n: str(n or "")}
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in KONSTANTEN]
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


LUCID = {"namen": ["lucid"], "route": "tvv2", "symbol": "NQ", "boden": "nachziehend", "dd_usd": 4500, "groessen": [150000],
         "ziel_pct": {"challenge": 6},
         "phasen": {"challenge": {"sl": None, "tp": [4400, 4500], "menge": [2, 2], "tp_max": 4500, "menge_schritt": 1}}}
FP = {"namen": ["fundingpips"], "boden": "statisch", "route": "mt5v2", "dd_pct": 10, "groessen": [50000, 100000],
      "ziel_pct": {"phase1": 8, "phase2": 5},
      "phasen": {"phase1": {"sl": [2000, 2500], "tp": [3500, 4000], "menge": [1, 1.5], "puffer": [50, 75], "tp_max": 4000,
                            "ziel_pct": 8, "boden_pct": 10, "menge_schritt": 0.1}}}
U = {"tp": 0.5, "sl": 0.5, "menge": 0.0, "puffer": 0.5}


def main():
    a = lade()
    R = a["ap_konto_rechnen"]
    check(a["AP_FUT_DECKEL_PLUS_USD"] == 100, "AP_FUT_DECKEL_PLUS_USD = 100")

    w, g = R(LUCID, "challenge", 159000 - 4537, U)          # Lucid 20.10.2026: Rest 4.537, Deckel 4.500, 2 NQ → Puffer 40
    check(w and w["rest"] == 4537 and w["menge"] == 2 and w["puffer"] == 40, f"Lucid: Rest 4.537, 2 NQ, Puffer 40 ({w or g})")
    check(w and w["tp"] == 4577 and w["stufe"] == "letzter Trade (Rest bis Ziel) · Deckel +77 $", f"Lucid: letzter Trade TP 4.577 (≤ 4.600), Stufe „{(w or {}).get('stufe')}“")
    check(w and w["tp"] <= 4600 and w["tp"] - w["rest"] >= a["AP_GEBUEHR_JE_KT_FUT"] * 2, "Lucid: TP in Finns Range und mindestens die Gebühren über dem Rest")

    w, _ = R(LUCID, "challenge", 159000 - 4590, U)           # Rest 4.590 → Rest + 40 = 4.630 → auf 4.600 gekappt
    check(w and w["tp"] == 4600 and w["stufe"].endswith("Deckel +100 $"), f"Rest 4.590: TP auf Deckel + 100 = 4.600 gekappt ({(w or {}).get('tp')})")

    w, _ = R(LUCID, "challenge", 159000 - 4480, U)           # Rest 4.480 (+40 = 4.520 über dem Deckel) → nicht mehr auf 4.500 gedeckelt
    check(w and w["tp"] == 4520 and w["stufe"].endswith("Deckel +20 $"), f"Rest 4.480: TP 4.520 statt auf 4.500 gedeckelt ({(w or {}).get('tp')})")

    w, _ = R(LUCID, "challenge", 159000 - 4650, U)           # Rest 4.650 > 4.600 → Etappe wie bisher
    check(w and w["stufe"] == "Etappe" and 4400 <= w["tp"] <= 4500, f"Rest 4.650: Etappe wie bisher ({(w or {}).get('stufe')}, TP {(w or {}).get('tp')})")

    w, _ = R(LUCID, "challenge", 159000 - 4000, U)           # Rest 4.000 + 40 ≤ 4.500 → normaler letzter Trade, unverändert
    check(w and w["tp"] == 4040 and w["stufe"] == "letzter Trade (Rest bis Ziel)", f"Rest 4.000: letzter Trade unverändert ({(w or {}).get('stufe')})")

    # CFD unverändert (FundingPips phase1, Ziel 108.000, tp_max 4.000, Puffer 62)
    w, _ = R(FP, "phase1", 108000 - 4050, U)
    check(w and w["stufe"] == "Etappe", f"CFD Rest 4.050: Etappe wie bisher ({(w or {}).get('stufe')})")
    w, _ = R(FP, "phase1", 108000 - 3980, U)
    check(w and w["tp"] == 4000 and w["stufe"] == "letzter Trade (auf Tageshöchstwert gedeckelt)", f"CFD Rest 3.980: auf Tageshöchstwert gedeckelt wie bisher ({(w or {}).get('stufe')}, TP {(w or {}).get('tp')})")

    # Mengen-Wache-Vertrag: die Stufe beginnt mit „letzter Trade (Rest bis Ziel)" (ap_menge_fix rechnet den TP dann wie hier)
    w, _ = R(LUCID, "challenge", 159000 - 4537, U)
    check(w and w["stufe"].startswith("letzter Trade (Rest bis Ziel)"), "Stufe beginnt mit „letzter Trade (Rest bis Ziel)“ (Mengen-Wache)")

    print()
    if FEHLER:
        print(f"{len(FEHLER)} FEHLER:", *FEHLER, sep="\n  ")
        sys.exit(1)
    print("alle Prüfungen bestanden")


if __name__ == "__main__":
    main()
