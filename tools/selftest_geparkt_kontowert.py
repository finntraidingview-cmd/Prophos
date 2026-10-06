#!/usr/bin/env python3
"""Selbsttest Geparktes Kapital nach Kontowert (app.py, gp_zuwachs_konto / gp_konto_geparkt, 07.10.2026) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_geparkt_kontowert.py
Lädt die Funktionen per Quelltext aus app.py (wie selftest_auto_kontowert: app.py zieht beim Import Flask und Threads).
Regel (Finn/Master 07.10.2026): Wert = echte Gesamtkosten der Kette (Kauf + Hedge) + Kontowert-Zuwachs der ungehedgten Trades;
Payouts ≥ Wert → im Plus, zählt gar nicht; sonst Rest = Wert − Payouts. Kernwerte = auto_plan_regeln.regeln.firmen (Live-Stand)."""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")

FIRMEN = [
    {"namen": ["tradeify"], "groessen": [150000], "kauf_eur": 215, "dd_usd": 4500, "boden": "nachziehend",
     "ziel_pct": {"challenge": 6}, "phasen": {"challenge": {"tp_max": 3600, "ziel_pct": 6}}},
    {"namen": ["apextrader", "apex"], "groessen": [150000], "kauf_eur": 150, "dd_usd": 4000, "boden": "statisch",
     "daily_usd": 2000, "ziel_pct": {"challenge": 6}},
    {"namen": ["fundednext"], "groessen": [100000], "kauf_eur": {"50000": 261, "100000": 500}, "dd_pct": 10,
     "boden": "statisch", "ziel_pct": {"phase1": 8, "phase2": 5}, "wert_groessen": [50000, 100000]},
    {"namen": ["altefirma"], "groessen": [100000]},   # ohne Kernwerte
]


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re}

    def block(name):
        i = src.index(f"def {name}(")
        return src[i:src.find("\n\n\n", i)]

    def konst(name):
        return re.search(rf"^{name} = .*$", src, re.M).group(0)
    exec("\n".join([konst(k) for k in ("AP_GROESSE_TOLERANZ", "AP_KW_FUNDED", "AP_KW_PHASEN")]
                   + [block(f) for f in ("_wd_num", "_ap_norm", "ap_regel_finden", "ap_groesse", "ap_kw_param", "_ap_kw_kauf",
                                         "_ap_kw_wachsen", "_ap_kw_lock", "ap_kontowert", "gp_zuwachs_konto",
                                         "gp_konto_geparkt")]), ns)
    return ns


FEHLER = []


def pruef(name, ok, info=""):
    print(("✓ " if ok else "✗ ") + name + (f"  [{info}]" if info else ""))
    if not ok:
        FEHLER.append(name)


def main():
    ns = lade()
    kw, zuw, gp = ns["ap_kontowert"], ns["gp_zuwachs_konto"], ns["gp_konto_geparkt"]
    p = lambda f: ns["ap_kw_param"](ns["ap_regel_finden"](FIRMEN, f))
    fn, tr, ap = p("FundedNext"), p("Tradeify"), p("Apex Trader")

    # 1) Neues Konto, frisch: Wert = Kauf (keine Trades, kein Zuwachs)
    z = zuw("phase1", fn, 100000, 100000, [], 500)
    g = gp(500, z[0], 0)
    pruef("frisch ohne Trades: Wert = Kauf 500", g["wert"] == 500 and g["geparkt"] == 500, g)

    # 2) Neues Konto, ein ungehedgter Gewinn +3.000 $: Kontowert statt Kosten (alt: geparkt 500 = Kauf)
    z = zuw("phase1", fn, 103000, 100000, [(3000, True)], 500)
    soll = kw("phase1", 103000, fn, 500)["wert"]
    g = gp(500, z[0], 0)
    pruef("FN P1 +3.000 ohne Hedge: Wert = Kontowert 650 statt Kosten 500", g["wert"] == soll == 650, f"{g} soll {soll}")

    # 3) Verlust ohne Hedge senkt den Wert wie ein Hedge-Gewinn (500 × 7.500/10.000 = 375)
    z = zuw("phase1", fn, 97500, 100000, [(-2500, True)], 500)
    pruef("FN P1 −2.500 ohne Hedge: Zuwachs −125 → Wert 375", gp(500, z[0], 0)["wert"] == 375, z)

    # 4) Gehedgte Trades bekommen KEINEN Zuwachs (echter Hedge steckt in den Kosten), nur der ungehedgte zählt
    z = zuw("phase1", fn, 104000, 100000, [(3000, False), (1000, True)], 500)
    soll = kw("phase1", 104000, fn, 500)["wert"] - kw("phase1", 103000, fn, 500)["wert"]
    pruef("gehedgter Schritt ohne Zuwachs, ungehedgter = Δ Kontowert", z[0] == soll and z[1] == 1, f"{z} soll {soll}")
    z0 = zuw("phase1", fn, 103000, 100000, [(3000, False)], 500)
    pruef("nur gehedgte Trades → Zuwachs 0", z0 == (0.0, 0, 0), z0)

    # 5) Rückwärts vom Live-Stand = vorwärts ab Größe (Tradeify nachziehend, zwei Etappen ohne Hedge)
    zr = zuw("challenge", tr, 157200, None, [(3600, True), (3600, True)], 215)
    zv = zuw("challenge", tr, None, 150000, [(3600, True), (3600, True)], 215)
    soll = kw("challenge", 157200, tr, 215)["wert"] - kw("challenge", 150000, tr, 215)["wert"]
    pruef("Tradeify 2 Etappen: rückwärts = vorwärts = Δ Kontowert", zr[0] == zv[0] == soll and zr[1] == 2, f"{zr} {zv} soll {soll}")

    # 6) Echte Hedge-Kosten zählen voll (Tradeify-WD-Beispiel des Masters: 207 + 2.454,04 = 2.661,04 €), Zuwachs obendrauf
    z = zuw("winning_days", tr, 160270, None, [(11500, False), (270, True)], 207)
    satz = kw("winning_days", 160270, tr, 207)["satz"]
    g = gp(207 + 2454.04, z[0], 0)
    pruef("WD mit Fusion-Hedge: Wert = 2.661,04 + Zuwachs des ungehedgten Trades",
          abs(g["wert"] - (2661.04 + z[0])) < 0.01 and abs(z[0] - round(satz * 270)) <= 1, f"{g} zuwachs {z} satz {satz}")

    # 7) Herausnehmen: Payouts ≥ Wert → im Plus, zählt gar nicht (auch kein Restwert); darunter Rest
    g = gp(2661.04, 300, 3000)
    pruef("Payouts 3.000 ≥ Wert 2.961 → im Plus, geparkt 0", g["plus"] and g["geparkt"] == 0 and g["rest"] < 0, g)
    g = gp(2661.04, 300, 2961.04)
    pruef("Payouts = Wert → im Plus", g["plus"] and g["geparkt"] == 0, g)
    g = gp(2661.04, 300, 1000)
    pruef("Payouts 1.000 < Wert 2.961 → Rest 1.961 geparkt", not g["plus"] and g["geparkt"] == 1961.04, g)
    g = gp(650, 0, 0)
    pruef("ohne Payouts nie im Plus", not g["plus"] and g["geparkt"] == 650, g)

    # 8) Wert nie unter 0 (Kosten mit Hedge-Gewinn + Verlust ohne Hedge)
    g = gp(86, -200, 0)
    pruef("Wert nie negativ", g["wert"] == 0 and g["geparkt"] == 0 and not g["plus"], g)

    # 9) Ohne Kernwerte / ohne Balance und Größe: kein Zuwachs, Trades als offen gezählt
    z = zuw("phase1", p("AlteFirma"), 101000, 100000, [(1000, True)], 300)
    pruef("Firma ohne Kernwerte: Zuwachs 0, 1 offen", z == (0.0, 0, 1), z)
    z = zuw("phase1", fn, None, None, [(1000, True)], 500)
    pruef("keine Balance, keine Größe: Zuwachs 0, 1 offen", z == (0.0, 0, 1), z)
    # Balance passt zu keiner Größe (Apex 150k, Stand 120k) → offen statt Unsinn
    z = zuw("challenge", ap, 120000, None, [(500, True)], 150)
    pruef("Balance außerhalb der Größe: offen", z == (0.0, 0, 1), z)

    print()
    if FEHLER:
        print(f"{len(FEHLER)} Fehler: " + ", ".join(FEHLER))
        sys.exit(1)
    print("alle Prüfungen grün")


if __name__ == "__main__":
    main()
