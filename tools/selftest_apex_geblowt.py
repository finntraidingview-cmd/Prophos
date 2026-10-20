#!/usr/bin/env python3
"""Selbsttest: APEX GEBLOWT AM KONTO-BODEN (app.py liq_boden_kernwerte + liq_konto_boden = Radar-Boden, ap_boden_konto + ap_ende_unter_boden =
Erledigt-Klick; Finn 20.10.2026: „Apex-Accounts haben 3k Drawdown, also die 100k-Konten. Wenn sie unter 97k sind, als geblowt markieren").
Rein rechnend, Funktionen per Quelltext aus app.py (wie selftest_liq_regeln). Aufruf: python3 tools/selftest_apex_geblowt.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FEHLER = []
# Kernwerte Apex wie in auto_plan_regeln.regeln.firmen (Stand 20.10.2026): Firmen-DD 4.000, je Größe 100k = 3.000
APEX = {"namen": ["apextrader", "apex"], "boden": "statisch", "dd_usd": 4000, "daily_usd": 2000, "groessen": [100000, 150000], "kauf_eur": {"100000": 45, "150000": 150},
        "ziel_pct": {"challenge": 6}, "phasen": {"challenge": {"menge": [3, 3], "puffer": [100, 100], "ziel_pct": 6}},
        "je_groesse": {"100000": {"dd_usd": 3000, "daily_usd": 1500, "phasen": {"challenge": {"menge": [3, 3], "puffer": [100, 100], "ziel_pct": 6}}}}}
REGEL_EVAL = {"id": 3, "firma": "Apex Trader", "kontotyp": "challenge", "art": "tagesstart", "betrag_usd": "2000", "maxdd_art": "eod_trailing", "maxdd_usd": None, "maxdd_lock_ueber_groesse_usd": 100}


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re}

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]
    konst = [re.search(rf"^{k} = .*$", src, re.M).group(0).split("  #")[0] for k in ("AP_GROESSE_TOLERANZ", "AP_APEX_DD_JE_GROESSE_USD")]
    exec("\n".join(konst + [block(f) for f in ("_wd_num", "_wd_konto_groesse", "liq_konto_groesse", "_liq_de", "ist_topstep_express", "liq_konto_boden",
                                                 "_ap_norm", "ap_regel_finden", "ap_kw_param", "liq_boden_kernwerte",
                                                 "ap_groesse", "_ap_boden", "ap_boden_konto", "ap_ende_unter_boden")]), ns)
    return ns


def main():
    ns = lade()
    kern, boden, ende = ns["liq_boden_kernwerte"], ns["liq_konto_boden"], ns["ap_ende_unter_boden"]
    acc100 = {"id": "k1", "name": "100k APEX0000000000020 → Challenge", "firm": "Apex Trader", "account_type": "challenge", "max_drawdown": 3000}
    print("1) Radar-Boden (liq_boden_kernwerte → liq_konto_boden), Apex 100k Challenge")
    r, a, gr = kern(REGEL_EVAL, acc100, "challenge", False, [APEX])
    check(gr == 100000.0 and r["maxdd_usd"] == 3000.0 and r["maxdd_art"] == "statisch", f"Kernwerte je Größe: 100k → DD 3.000 statisch (war 4.000: {r['maxdd_usd']})")
    b = boden(r, a, gr, None, 98475.7)
    check(b[0] == 97000.0, f"Boden 97.000 (Chris …0020: Start 98.475,70, Ende 96.951,40 ≤ 97.000 → 💀 geblowt im Radar) — {b[1]}")
    check(boden(r, a, gr, None, 98415.7)[0] == 97000.0, "Moritz …0034: Start 98.415,70 → Boden 97.000")
    acc400 = dict(acc100, max_drawdown=400)
    r2, a2, gr2 = kern(REGEL_EVAL, acc400, "challenge", False, [APEX])
    check(a2["max_drawdown"] is None and boden(r2, a2, gr2, None, 98475.7)[0] == 97000.0, "accounts.max_drawdown 400 (Einzelfehler) zählt nicht — Kernwerte 3.000")
    print("2) Apex 150k bleibt bei 4.000")
    acc150 = dict(acc100, name="150k APEX0000000000008 → Challenge", max_drawdown=4000)
    r3, a3, gr3 = kern(REGEL_EVAL, acc150, "challenge", False, [APEX])
    check(gr3 == 150000.0 and r3["maxdd_usd"] == 4000.0 and boden(r3, a3, gr3, None, 148097)[0] == 146000.0, "150k → DD 4.000 (Finn 07.10. + 17:35), Boden 146.000")
    check(ende(APEX, "challenge", 148097, 146000) is True, "Soft-Breach-Fall 07.10. (148.097 → 146.000): geblowt, wie bisher")
    print("3) Grenze inklusive, MNQ egal (keine Menge in der Rechnung)")
    b100 = boden(r, a, gr, None, 98475.7)[0]
    check(97000.0 <= b100 and 96951.4 <= b100 and not (97000.01 <= b100), "96.951,40 und 97.000 unter/auf dem Boden, 97.000,01 darüber")
    print("4) Erledigt-Klick (ap_ende_unter_boden über ap_boden_konto, derselbe Kernwerte-DD)")
    check(ende(APEX, "challenge", 98475.7, 96951.4) is True and ende(APEX, "challenge", 98415.7, 96951.4) is True, "Chris + Moritz: Ende ≤ 97.000 → blown beim Abhaken")
    check(ende(APEX, "challenge", 98475.7, 97000.0) is True and ende(APEX, "challenge", 98475.7, 97000.01) is False, "Grenze 97.000 inklusive")
    check(ende(APEX, "challenge", 148097, 146000) is True and ende(APEX, "challenge", 148097, 146000.5) is False, "150k: 146.000 inklusive")
    print("6) Alle Apex-Größen (Finn 16:40: 150k und 250k genauso, so wie bei Apex die Regeln sind) - Tabelle als Rückfall, DB je_groesse gewinnt")
    TAB = {25000: 1500, 50000: 2500, 75000: 2750, 100000: 3000, 150000: 4000, 250000: 6500, 300000: 7500}
    check(ns["AP_APEX_DD_JE_GROESSE_USD"] == {k: float(v) for k, v in TAB.items()}, "Tabelle 25k 1.500 · 50k 2.500 · 75k 2.750 · 100k 3.000 · 150k 4.000 (Finn 17:35) · 250k 6.500 · 300k 7.500")
    kw = ns["ap_kw_param"](APEX)
    check(all(kw["dd_je_groesse"][str(g)] == float(d) for g, d in TAB.items()), "ap_kw_param.dd_je_groesse trägt alle sieben Größen (100k aus der DB, Rest Tabelle)")
    for g, d in TAB.items():
        accg = dict(acc100, name=f"{g // 1000}k APEX000000000000{g // 1000} → Challenge", max_drawdown=None)
        rg, ag, grg = kern(REGEL_EVAL, accg, "challenge", False, [APEX])
        bg = boden(rg, ag, grg, None, g - 1.0)[0]
        check(grg == float(g) and bg == float(g - d), f"Radar-Boden {g // 1000}k: {g - d:,} (DD {d:,}), ohne accounts.max_drawdown")
    # Erledigt-Klick heute (DB groessen nur 100k/150k): 150k nimmt jetzt 5.000 aus der Tabelle
    check(ende(APEX, "challenge", 148097, 146000) is True and ende(APEX, "challenge", 148097, 146000.5) is False, "150k Erledigt: Boden 146.000 (Tabelle = Firmen-DD 4.000)")
    # Erledigt-Klick nach sql/2026-10-20_apex_dd_je_groesse.sql (NUR je_groesse.dd_usd; groessen bleibt [100k, 150k] — S2: min(groessen) ist der Vorrat-Startwert)
    APEX_NEU = dict(APEX, je_groesse={**APEX["je_groesse"], **{str(g): {"dd_usd": d} for g, d in TAB.items() if g != 100000}})
    for g, d in TAB.items():
        if g in (100000, 150000):
            check(ende(APEX_NEU, "challenge", g - 100.0, g - d) is True and ende(APEX_NEU, "challenge", g - 100.0, g - d + 0.5) is False,
                  f"Erledigt {g // 1000}k nach der SQL: Boden {g - d:,} inklusive")
        else:
            check(ende(APEX_NEU, "challenge", g - 100.0, g - d) is False and ns["ap_boden_konto"](APEX_NEU, "challenge", float(g - 100))["boden"] is None,
                  f"{g // 1000}k ohne Eintrag in groessen: Erledigt-Klick/Planer ohne Boden (nie raten) — Radar-Boden gilt (Test 6)")
    bk = ns["ap_boden_konto"](APEX_NEU, "challenge", 149000.0)
    check(bk["boden"] == 146000.0 and bk["boden_art"] == "statisch", "ap_boden_konto 150k → 146.000 statisch (Planer-Anzeige = Radar)")
    print("7) Apex PA/Funded: derselbe DD je Größe, Trailing-Art + Lock der liq_regeln-Zeile bleiben (Finn 16:40: Evaluation und PA gleich)")
    REGEL_PA = {"id": 4, "firma": "Apex Trader", "kontotyp": "funded", "art": "stufen", "maxdd_art": "eod_trailing", "maxdd_usd": None, "maxdd_lock_ueber_groesse_usd": 100}
    accpa = {"id": "k9", "name": "150k APEX0000000000009 → Funded", "firm": "Apex Trader", "account_type": "funded", "max_drawdown": None}
    rp, ap_, grp = kern(REGEL_PA, accpa, "funded", False, [APEX])
    check(rp["maxdd_usd"] == 4000.0 and rp["maxdd_art"] == "eod_trailing" and ap_["max_drawdown"] is None, "150k PA ohne accounts.max_drawdown (3 Konten laut S2): DD 4.000 aus der Tabelle, Art bleibt eod_trailing")
    check(boden(rp, ap_, grp, None, 150000)[0] == 146000.0, "PA 150k ab Start: Boden 146.000")
    check(boden(rp, ap_, grp, 153000, 152500)[0] == 149000.0, "PA 150k Höchststand 153.000: Boden 149.000 (trailt)")
    check(boden(rp, ap_, grp, 156000, 155500)[0] == 150100.0, "PA 150k Höchststand 156.000: Lock bei 150.100")
    rp2, ap2, grp2 = kern(REGEL_PA, dict(accpa, max_drawdown=4000), "funded", False, [APEX])
    check(rp2["maxdd_usd"] == 4000.0 and ap2["max_drawdown"] is None, "PA mit accounts.max_drawdown 4.000: Tabelle (eine Quelle), gleicher Wert")
    print("5) Andere Firma / ohne Kernwerte unverändert")
    r4, a4, gr4 = kern({"id": 1, "firma": "Tradeify", "art": "fest", "betrag_usd": "4500"}, {"name": "150k TDFYSL000 → Challenge", "firm": "Tradeify", "account_type": "challenge", "max_drawdown": 4500}, "challenge", False, [APEX])
    check(a4.get("max_drawdown") == 4500 and gr4 == 150000.0, "Tradeify: Regel/Konto unverändert (kein Soft-Tagesstopp)")
    r5, a5, gr5 = kern(REGEL_EVAL, acc100, "challenge", False, None)
    check(a5.get("max_drawdown") == 3000 and r5 is REGEL_EVAL, "ohne Kernwerte (kw_firmen None): wie bisher accounts.max_drawdown")
    print()
    if FEHLER:
        print(f"FEHLER: {len(FEHLER)}")
        return 1
    print("OK — alle Prüfungen bestanden")
    return 0


if __name__ == "__main__":
    sys.exit(main())
