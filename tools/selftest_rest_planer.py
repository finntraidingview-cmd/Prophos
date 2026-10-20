#!/usr/bin/env python3
"""Selbsttest REST ZURÜCK IN DEN PLANER (app.py ap_konto_rechnen / ap_klein_trade_fut, 20.10.2026 — Finn 22:55 Dubai, Radar → Bestanden →
Rest von Hand: „Vor allem bei CFDs soll bei so vielen Dollar einfach noch ein Trade automatisch gemacht werden … entweder ich mache den
Trade manuell, oder ‚OK, abhaken und zurück in den Trade-Planer' — der macht den Rest automatisch fertig. Bei 300 $ Rest schiebe ich die
einfach zurück in den Planer."). Rein rechnend, ohne Netz; Regel-Werte wie auto_plan_regeln, Konten erfunden.
Fälle: CFD Rest 346 (FundingPips 100k) mit/ohne Feld → Klein-Trade (lag schon über der 10-$-Grenze); CFD Rest 5 ohne Feld → von Hand,
mit Feld → Klein-Trade 0,01 Lot; Futures Rest 84 (Lucid 150k) ohne Feld → von Hand, mit Feld → 1 MNQ, TP 104 $ (52 Pkt), SL wie die Regel,
symbol MNQ; Tage offen + Feld → Mini geht vor; genau am Ziel → Ziel erreicht; Rest ≥ Grenze ohne Feld unverändert (Etappe).
Aufruf: python3 tools/selftest_rest_planer.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_wd_num", "_ap_norm", "ap_groesse", "_ap_spanne", "_ap_runden", "_ap_boden", "ap_kette_regel", "ap_kette_mll",
              "ap_kette_trade1", "ap_kw_param", "ap_konto_rechnen", "ap_klein_trade", "ap_klein_trade_fut", "_ap_de", "ap_cfd_ppl", "ap_notiz",
              "ap_tage_mini", "zw_erreicht")
KONSTANTEN = ("AP_REST_MIN", "AP_REST_MIN_CFD", "AP_KLEIN_PKT", "AP_KLEIN_PUFFER", "AP_KLEIN_SCHRITT", "AP_KLEIN_TP_PKT_HINWEIS",
              "AP_PUFFER_PKT", "AP_PUFFER_PKT_FUT", "AP_PUFFER_JE_KT_FUT", "AP_GEBUEHR_JE_KT_FUT", "AP_PUNKTWERT_FUT", "AP_CFD_ROUTEN",
              "AP_GROESSE_TOLERANZ", "AP_KETTE_STANDARD", "AP_KETTE_TXT", "AP_SL_HINTER_BODEN", "AP_MINI_FUTURES_SYMBOL", "AP_MINI_PUNKTWERT",
              "AP_TAGE_CFD_PKT", "AP_TAGE_FUT_PKT", "AP_TAGE_PUFFER", "AP_TAGE_USD")
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


FP = {"namen": ["fundingpips"], "boden": "statisch", "route": "mt5v2", "dd_pct": 10, "groessen": [50000, 100000],
      "ziel_pct": {"phase1": 8, "phase2": 5},
      "phasen": {"phase1": {"sl": [2000, 2500], "tp": [3500, 4000], "menge": [1, 1.5], "puffer": [50, 75], "tp_max": 4000,
                            "ziel_pct": 8, "boden_pct": 10, "menge_schritt": 0.1}}}
LUCID = {"namen": ["lucidtrading", "lucid"], "route": "tvv2", "symbol": "NQ", "boden": "nachziehend", "dd_usd": 4500, "groessen": [150000],
         "ziel_pct": {"challenge": 6}, "phasen": {"challenge": {"sl": [2500, 2500], "tp": [4450, 4500], "menge": [2, 3], "tp_max": 4500,
                                                                 "menge_schritt": 1, "puffer_je_menge": {"2": [30, 40], "3": [30, 40]}}}}


def main():
    a = lade()
    R, KF = a["ap_konto_rechnen"], a["ap_klein_trade_fut"]
    u = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.6}

    # 1) CFD FundingPips 100k P1, Rest 346 $ (Chris, Radar 20.10.2026): liegt über der 10-$-Grenze → Klein-Trade mit und ohne Feld
    w0, g0 = R(FP, "phase1", 107654, u, ppl=20)
    w1, g1 = R(FP, "phase1", 107654, u, ppl=20, rest_planer=True)
    check(g0 is None and "Klein-Trade" in w0["stufe"] and w0["menge"] == 0.86 and w0["tp"] == 346 + w0["puffer"],
          f"CFD Rest 346 ohne Feld → Klein-Trade wie bisher ({(w0 or {}).get('stufe') or g0})")
    check(g1 is None and w1["menge"] == w0["menge"] and w1["tp"] == w0["tp"] and w1["sl"] == w0["sl"] and "Rest zurück im Planer" not in w1["stufe"],
          f"CFD Rest 346 mit Feld → derselbe Klein-Trade (Feld greift erst unter der Grenze) ({(w1 or {}).get('stufe') or g1})")

    # 2) CFD Rest 5 $: ohne Feld von Hand (mit Hinweis auf den Knopf), mit Feld Klein-Trade 0,01 Lot
    w, g = R(FP, "phase1", 107995, u, ppl=20)
    check(w is None and g.startswith("Rest 5 $ bis Ziel — von Hand") and "→ Trade-Planer" in g, f"CFD Rest 5 ohne Feld → von Hand ({g})")
    w, g = R(FP, "phase1", 107995, u, ppl=20, rest_planer=True)
    check(g is None and w["menge"] == 0.01 and w["tp"] == 5 + w["puffer"] and 15 <= w["puffer"] <= 20 and w["sl"] == 2250
          and "Klein-Trade" in w["stufe"] and w["stufe"].endswith("· Rest zurück im Planer") and "symbol" not in w,
          f"CFD Rest 5 mit Feld → Klein-Trade 0,01 Lot, SL 2.250 ({(w or {}).get('stufe') or g})")
    w, g = R(FP, "phase1", 107995, u, rest_planer=True)
    check(w is None and "kein Punktwert" in g, f"CFD Rest 5 mit Feld, ohne Punktwert → Handarbeit mit Fix ({g})")

    # 3) Futures Lucid 150k, Rest 84 $: ohne Feld von Hand, mit Feld 1 MNQ, TP 104 $ (52 Pkt), SL 2.500 wie die Regel
    w, g = R(LUCID, "challenge", 158916, u)
    check(w is None and g.startswith("Rest 84 $ bis Ziel — von Hand") and "→ Trade-Planer" in g, f"Futures Rest 84 ohne Feld → von Hand ({g})")
    w, g = R(LUCID, "challenge", 158916, u, rest_planer=True)
    check(g is None and w["rest"] == 84 and w["menge"] == 1 and w["tp"] == 104 and w["puffer"] == 20 and w["sl"] == 2500 and w["risiko"] == 2500
          and w.get("symbol") == "MNQ" and "1 MNQ" in w["stufe"] and "52 Pkt" in w["stufe"] and w["stufe"].endswith("· Rest zurück im Planer"),
          f"Futures Rest 84 mit Feld → 1 MNQ, TP 104 $ (≈ 52 Pkt), SL 2.500 ({(w or {}).get('stufe') or g})")
    kf = KF(84, {"symbol": "NQ", "klein_symbol": "NQ"}, {"menge_schritt": 1})
    check(kf["symbol"] == "NQ" and kf["tp"] == 104 and kf["tp_punkte"] == 5.2, f"klein_symbol NQ der Regel → 1 NQ, 5,2 Pkt ({kf['stufe']})")
    check(a["AP_GEBUEHR_JE_KT_FUT"] <= a["AP_PUFFER_JE_KT_FUT"], "Puffer je Kontrakt deckt die Gebühren")

    # 4) Feld ändert nichts über der Grenze und am Ziel
    w, g = R(LUCID, "challenge", 159000, u, rest_planer=True)
    check(w is None and g.startswith("Ziel erreicht"), f"Futures genau am Ziel mit Feld → Ziel erreicht ({g})")
    w, g = R(LUCID, "challenge", 154463, u, rest_planer=True)
    check(w is not None and w["stufe"] == "Etappe" and "symbol" not in w, f"Futures Rest 4.537 mit Feld → Etappe wie bisher ({(w or {}).get('stufe') or g})")
    w, g = R(LUCID, "challenge", 158800, u, rest_planer=True)
    check(w is not None and w["stufe"].startswith("letzter Trade") and w["menge"] >= 2 and "symbol" not in w,
          f"Futures Rest 200 mit Feld → normaler letzter Trade ({(w or {}).get('stufe') or g})")

    # 5) Mindesttage offen + Feld → der Tage-Mini geht weiter vor (12.10.2026)
    w, g = R(LUCID, "challenge", 158916, u, tage=(1, 3), rest_planer=True)
    check(w is not None and w.get("tage_mini") and "Mini" in w["stufe"], f"Tage offen + Feld → Mini-Trade vor dem Klein-Trade ({(w or {}).get('stufe') or g})")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler:"); [print("  - " + f) for f in FEHLER]; sys.exit(1)
    print("ALLES GRÜN")


if __name__ == "__main__":
    main()
