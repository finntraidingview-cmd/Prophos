#!/usr/bin/env python3
"""Selbsttest KLEIN-TRADE KURZ VOR DEM ZIEL + PUFFER IN PUNKTEN (app.py ap_konto_rechnen, ap_klein_trade, ap_cfd_ppl, 09.10.2026 —
Finn: „wenn nur noch ein paar hundert Dollar zum Ziel sind … Lots runterschrauben … Puffer 15–20 … SL wie beim normalen Trade";
normaler letzter CFD-Trade: Puffer 10 Pkt × Lots × $/Pkt). Rein rechnend, ohne Netz. Regel-Werte wie auto_plan_regeln, Konten erfunden.
Fälle: die drei Rest-Fälle vom 09.10. (FN Rest 36, FP Rest 56, FN Rest 62), Punkte-Puffer FN 2,8 Lots → 280 $, Schwelle FN 420 $,
grober Lot-Schritt → Hinweis, Rest 5 $ → Handarbeit, ohne Punktwert → Handarbeit, Futures: Rest < 100 → Meldung Rest von Hand, kein Trade (20.10.2026).
Loader kennt seit 20.10.2026 auch ap_kw_param (ap_konto_rechnen ruft es seit den Kernwerten — der Test lief seitdem auf NameError).
Aufruf: python3 tools/selftest_klein_trade.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_wd_num", "_ap_norm", "ap_groesse", "_ap_spanne", "_ap_runden", "_ap_boden", "ap_kette_regel", "ap_kette_mll",
              "ap_kette_trade1", "ap_kw_param", "ap_konto_rechnen", "ap_klein_trade", "_ap_de", "ap_cfd_ppl", "ap_notiz", "zw_erreicht")
KONSTANTEN = ("AP_REST_MIN", "AP_REST_MIN_CFD", "AP_KLEIN_PKT", "AP_KLEIN_PUFFER", "AP_KLEIN_SCHRITT", "AP_KLEIN_TP_PKT_HINWEIS",
              "AP_PUFFER_PKT", "AP_PUFFER_PKT_FUT", "AP_PUFFER_JE_KT_FUT", "AP_GEBUEHR_JE_KT_FUT", "AP_PUNKTWERT_FUT", "AP_CFD_ROUTEN", "AP_GROESSE_TOLERANZ", "AP_KETTE_STANDARD", "AP_KETTE_TXT")
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


FN = {"namen": ["fundednext"], "boden": "statisch", "route": "mt5v2", "dd_pct": 10, "groessen": [50000, 100000],
      "ziel_pct": {"phase1": 8, "phase2": 5},
      "phasen": {"phase1": {"sl": [2500, 3500], "tp": [6000, 8000], "menge": [2.1, 3.2], "puffer": [100, 100], "ziel_pct": 8,
                            "boden_pct": 10, "menge_schritt": 0.1},
                 "phase2": {"sl": [2500, 3500], "tp": [6000, 8000], "menge": [2.1, 3.2], "puffer": [100, 100], "ziel_pct": 5,
                            "boden_pct": 10, "menge_schritt": 0.1}}}
FP = {"namen": ["fundingpips"], "boden": "statisch", "route": "mt5v2", "dd_pct": 10, "groessen": [50000, 100000],
      "ziel_pct": {"phase1": 8, "phase2": 5},
      "phasen": {"phase1": {"sl": [2000, 2500], "tp": [3500, 4000], "menge": [1, 1.5], "puffer": [50, 75], "tp_max": 4000,
                            "ziel_pct": 8, "boden_pct": 10, "menge_schritt": 0.1}}}
FTMO = {"namen": ["ftmo"], "boden": "statisch", "route": "mt5v2", "dd_pct": 10, "groessen": [100000, 200000],
        "ziel_pct": {"phase1": 10, "phase2": 5},
        "phasen": {"phase1": {"sl": [2300, 2750], "tp": [5000, 8000], "menge": [25, 35], "puffer": [75, 75], "ziel_pct": 10,
                              "boden_pct": 10, "menge_schritt": 1}}}
TDFY = {"namen": ["tradeify"], "route": "tvv2", "symbol": "NQ", "boden": "nachziehend", "dd_usd": 4500, "groessen": [150000],
        "ziel_pct": {"challenge": 6},
        "phasen": {"challenge": {"sl": None, "tp": [3450, 3550], "menge": [2, 3], "tp_max": 3600, "menge_schritt": 1,
                                 "puffer_je_menge": {"2": [15, 25], "3": [25, 40]}}}}


def main():
    a = lade()
    R, K = a["ap_konto_rechnen"], a["ap_klein_trade"]
    u = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.6}

    # 1) Chris FN 100k P1, Rest 36 $ → 0,18 Lots, Puffer 18 (u 0,6 in 15–20), TP 54, SL normal 3.000
    w, g = R(FN, "phase1", 107963.98, u, ppl=10)
    check(g is None and w["menge"] == 0.18 and w["puffer"] == 18 and w["tp"] == 54 and w["sl"] == 3000,
          f"FN Rest 36 $ → 0,18 Lots, TP 54 $, SL 3.000 $ ({w and (w['menge'], w['puffer'], w['tp'], w['sl'])}, {g})")
    check(w["stufe"] == "Klein-Trade · Rest 36 $ · 0,18 Lots · TP 54 $ (Rest + Puffer 18 $)", f"Stufen-Text Chris: {w['stufe']}")

    # 2) Moritz FP 100k P1, Rest 56 $ → 0,14 Lots (56 ÷ 400), SL normale FP-Spanne 2.250
    w, g = R(FP, "phase1", 107944, u, ppl=20)
    check(g is None and w["menge"] == 0.14 and w["tp"] == 56 + w["puffer"] and 15 <= w["puffer"] <= 20 and w["sl"] == 2250,
          f"FP Rest 56 $ → 0,14 Lots, TP Rest + 15–20, SL 2.250 ({w and (w['menge'], w['puffer'], w['tp'], w['sl'])}, {g})")

    # 3) Ina FN 100k P1, Rest 62 $ → 0,31 Lots
    w, g = R(FN, "phase1", 107938, u, ppl=10)
    check(g is None and w["menge"] == 0.31 and w["tp"] == 62 + w["puffer"] and "Klein-Trade" in w["stufe"],
          f"FN Rest 62 $ → 0,31 Lots ({w and (w['menge'], w['tp'], w['stufe'])}, {g})")

    # 4) Puffer-Spanne 15–20 an beiden Enden des Zufalls
    p0, p1 = K(36, 10, 0.1, 0.0)["puffer"], K(36, 10, 0.1, 1.0)["puffer"]
    check((p0, p1) == (15, 20), f"Klein-Puffer Zufall 0 → 15 $, 1 → 20 $ ({p0}, {p1})")

    # 5) Normaler letzter Trade FN 2,8 Lots, Rest 2.964 → Puffer 10 Pkt × 2,8 × 10 ÷ 3 = 93 $ (÷ 3 seit 12.10.2026), TP 3.057
    u28 = dict(u, menge=(2.8 - 2.1) / 1.1)
    w, g = R(FN, "phase1", 105036, u28, ppl=10)
    check(g is None and w["menge"] == 2.8 and w["puffer"] == 93 and w["tp"] == 3057 and w["stufe"].startswith("letzter Trade"),
          f"FN letzter Trade 2,8 Lots → Puffer 93 $, TP 3.057 ({w and (w['menge'], w['puffer'], w['tp'], w['stufe'])}, {g})")
    # ohne Punktwert: wie bisher fester Firmen-Puffer 100
    w, g = R(FN, "phase1", 105036, u28)
    check(g is None and w["puffer"] == 100 and w["tp"] == 3064, f"ohne Punktwert → alter Puffer 100 $ ({w and (w['puffer'], w['tp'])})")
    # Etappe (Rest groß) bleibt Zufall aus der TP-Spanne
    w, g = R(FN, "phase1", 100000, u, ppl=10)
    check(g is None and w["stufe"] == "Etappe" and w["tp"] == 7000, f"FN Rest 8.000 → Etappe TP 7.000 ({w and (w['stufe'], w['tp'])})")

    # 6) Schwelle FN: 20 Pkt × 2,1 Lots × 10 $ = 420 $
    w, _g = R(FN, "phase1", 108000 - 419, u, ppl=10)
    check("Klein-Trade" in w["stufe"] and w["menge"] == 2.09, f"FN Rest 419 → Klein-Trade 2,09 Lots ({w['stufe']})")
    w, _g = R(FN, "phase1", 108000 - 421, u, ppl=10)
    check(w["stufe"].startswith("letzter Trade") and 2.1 <= w["menge"] <= 3.2 and w["puffer"] == round(100 * w["menge"] / 3), f"FN Rest 421 → normaler letzter Trade, Punkte-Puffer ÷ 3 ({w['stufe']}, {w['menge']}, {w['puffer']})")

    # 7) grober Lot-Schritt (FTMO, Schritt 1, 0,85 $/Pkt): Rest 33 → 1 Lot, TP 53 $ = 62 Pkt → trotzdem geplant, mit Hinweis
    w, g = R(FTMO, "phase1", 110000 - 33, dict(u, puffer=1.0), ppl=0.85)
    check(g is None and w["menge"] == 1 and w["tp"] == 53 and "Pkt weit (Lot-Schritt grob)" in w["stufe"],
          f"FTMO Rest 33 → 1 Lot, TP 53 $, Hinweis > 60 Pkt ({w and w['stufe']}, {g})")
    w, g = R(FTMO, "phase1", 110000 - 100, u, ppl=1)
    check(g is None and w["menge"] == 5 and w["stufe"].startswith("Klein-Trade · Rest 100 $ · 5 Lots"),
          f"FTMO Rest 100 → 5 Lots ({w and w['stufe']})")

    # 8) Rest 5 $ (CFD) → Handarbeit mit genauem Grund
    w, g = R(FN, "phase1", 107995, u, ppl=10)
    check(w is None and g.startswith("Rest 5 $ bis Ziel — von Hand") and "unter 10 $" in g, f"Rest 5 $ → Handarbeit ({g})")
    # Rest 50 ohne Punktwert → Handarbeit mit Fix
    w, g = R(FN, "phase1", 107950, u)
    check(w is None and "kein Punktwert" in g, f"Rest 50 ohne Punktwert → Handarbeit ({g})")

    # 9) Futures unverändert: mit und ohne ppl dasselbe, Challenge-Rest < 100 → Ziel erreicht
    w1, _ = R(TDFY, "challenge", 158000, u)
    w2, _ = R(TDFY, "challenge", 158000, u, ppl=20)
    # seit 17.10.2026 (Finn: „2 NQ Puffer 40, 3 NQ Puffer 60"): letzter Futures-Trade genau 20 $ je Kontrakt, kein Punkte-Puffer mehr
    fut = 20 * float(w1["menge"])
    check(w1 == w2 and w1["puffer"] == fut and "Klein" not in w1["stufe"],
          f"Tradeify unverändert ({w1['stufe']}, Puffer {w1['puffer']} = 20 $ × {w1['menge']} NQ)")
    # BESTANDEN ERST AM ZIEL (Finn 20.10.2026 20:35–20:45 Dubai, Lucid …0001: 158.916 von 159.000 — „Es soll eine Meldung kommen: Es fehlen
    # noch ein paar Dollar, bitte manuell den Rest machen"): Futures-Rest < 100 ist NICHT mehr „Ziel erreicht" und bekommt KEINEN Trade —
    # Meldung „Rest … von Hand"; genau am Ziel → erreicht; Rest 4.537 → Etappe wie bisher
    w, g = R(TDFY, "challenge", 158950, u, ppl=20)
    check(w is None and g.startswith("Rest 50 $ bis Ziel — von Hand"), f"Futures Rest 50 → kein Trade, Meldung ({g})")
    LUCID = {"namen": ["lucidtrading", "lucid"], "route": "tvv2", "symbol": "NQ", "boden": "nachziehend", "dd_usd": 4500, "groessen": [150000],
             "ziel_pct": {"challenge": 6}, "phasen": {"challenge": {"sl": [2500, 2500], "tp": [4450, 4500], "menge": [2, 3], "tp_max": 4500,
                                                                     "menge_schritt": 1, "puffer_je_menge": {"2": [30, 40], "3": [30, 40]}}}}
    w, g = R(LUCID, "challenge", 158916, u)
    check(w is None and g.startswith("Rest 84 $ bis Ziel — von Hand (der Bot plant hier keinen Trade mehr"), f"Lucid Rest 84 → kein Trade, Meldung ({g})")   # seit 20.10.2026 22:55 mit Hinweis „→ Trade-Planer" (tools/selftest_rest_planer.py)
    w, g = R(LUCID, "challenge", 159000, u)
    check(w is None and g.startswith("Ziel erreicht"), f"Lucid genau am Ziel → Ziel erreicht ({g})")
    w, g = R(LUCID, "challenge", 154463, u)
    check(w is not None and w["stufe"] == "Etappe" and 4450 <= w["tp"] <= 4500, f"Lucid Rest 4.537 → Etappe wie bisher ({(w or {}).get('stufe') or g}, TP {(w or {}).get('tp')})")
    # Gebühren: der Puffer des letzten Futures-Trades liegt nie unter den Gebühren (20 $ ≥ 6 $ je Kontrakt); knapp unter dem Deckel wird
    # der Rest komplett zum letzten Trade (4.505 + 40 = 4.545 ≤ 5.000), über dem Deckel bleibt die Etappe
    check(a["AP_GEBUEHR_JE_KT_FUT"] <= a["AP_PUFFER_JE_KT_FUT"], "Gebühren je Kontrakt liegen unter dem Futures-Puffer")
    LUCID2 = dict(LUCID, phasen={"challenge": dict(LUCID["phasen"]["challenge"], tp_max=5000, menge=[2, 2])})
    u_hoch = dict(u, tp=1.0, menge=0.0)
    w, g = R(LUCID2, "challenge", 154495, u_hoch)
    check(w is not None and w["tp"] == 4545 and w["puffer"] == 40 and w["stufe"].startswith("letzter Trade"), f"Rest 4.505 unter Deckel 5.000 → letzter Trade mit 40 $ Puffer ({(w or {}).get('stufe') or g}, TP {(w or {}).get('tp')})")
    w, g = R(LUCID, "challenge", 154495, u_hoch)
    check(w is not None and w["stufe"] == "Etappe" and w["tp"] == 4500, f"Rest 4.505 über Deckel 4.500 → Etappe ({(w or {}).get('stufe') or g})")
    # Ziel-Wache ohne Toleranz (zw_erreicht): 84 $ unter dem Ziel = nicht erreicht, genau am Ziel = erreicht, auch bei Challenge
    ZE = a["zw_erreicht"]
    check(ZE(159000, 158916, "challenge") is False and ZE(159000, 159000, "challenge") is True and ZE(159000, 159001, "phase1") is True
          and ZE(159000, 158999.5, "phase1") is False, "zw_erreicht: Rest 84 → nein, Rest 0 → ja (keine 100-$-Toleranz mehr)")

    # 10) ap_cfd_ppl: erst die ID, sonst der häufigste Wert der Firma
    P = a["ap_cfd_ppl"]
    ctx = {"ppl": {("u1", "ftmo"): (0.85, None, "Lots")}, "ppl_firma": {"ftmo": (1.0, None, "Lots"), "fundednext": (10.0, None, "Lots")}}
    check(P(ctx, {"user_id": "u1", "firm": "FTMO"}) == 0.85 and P(ctx, {"user_id": "u2", "firm": "FTMO"}) == 1.0
          and P(ctx, {"user_id": "u2", "firm": "Blue Guardian"}) is None and P(None, {"firm": "FTMO"}) is None,
          "ap_cfd_ppl: ID-Wert vor Firmen-Wert, unbekannt → None")
    ctx_k = {"ppl": {("u1", "fundednext"): (2.0, "MNQ", "Kontrakte")}, "ppl_firma": {"ftmo": (1.0, None, None)}}
    check(P(ctx_k, {"user_id": "u1", "firm": "FundedNext"}) is None and P(ctx_k, {"user_id": "u9", "firm": "FTMO"}) == 1.0,
          "ap_cfd_ppl: Einheit „Kontrakte“ → None (Handarbeit), Einheit leer → Lots")

    # 11) Notiz (09.10.2026, live stand „0.18 Lots"): Lots mit Komma, Rest/Balance mit Tausender-Punkt, Frontend-Muster greift weiter
    N = a["ap_notiz"]
    st = K(36, 10, 0.1, 0.8)["stufe"]
    n = N(st, f"{36:,}".replace(",", "."), 107963.98, "Echo")
    check(n == "Auto-Planer · Klein-Trade · Rest 36 $ · 0,18 Lots · TP 55 $ (Rest + Puffer 19 $) · Rest 36 $ bis Ziel · Balance 107.964 (Echo)",
          f"Notiz Klein-Trade mit Komma-Lots ({n})")
    m = re.search(r"Auto-Planer · (.+?) · Rest ([\d.]+) \$ bis Ziel · Balance ([\d.]+)", n)
    check(bool(m) and m.group(1) == st and m.group(2) == "36" and m.group(3) == "107.964", "Frontend-Muster planAutoNotiz liest Stufe/Rest/Balance")
    n2 = N("letzter Trade (Rest bis Ziel)", f"{3964:,}".replace(",", "."), 105036, "TV")
    check(n2 == "Auto-Planer · letzter Trade (Rest bis Ziel) · Rest 3.964 $ bis Ziel · Balance 105.036 (TV)", f"Tausender bleiben ({n2})")

    print(f"\n{'ALLES OK' if not FEHLER else f'{len(FEHLER)} FEHLER'}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
