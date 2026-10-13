#!/usr/bin/env python3
"""Selbsttest GRUPPEN-PLANER (app.py, 13.10.2026, Emin-Gruppe): reine Rechenteile ohne Netz.
Geprüft: Multiplikator wie tpMultiplierAusRisiko (Proben aus Emins echten Plänen: The5ers 10.000 $ / 30 Lot / 142 € → ×0,0167,
FundingPips 12.000 $ / 2,5 Lot / 492 € → ×0,9647), Hedge-Gründe (Max-DD, Kaufpreis, Punktwert, < 0,01 Lot), Max-DD-Rückfall,
Richtung (fest zuerst, große auf die leichtere Seite), Startzeiten (Fenster, Abstand je ID, voll), Takt-Fenster (Mo–Fr, lauf … bis − 15).
Aufruf: python3 tools/selftest_gruppen_planer.py"""
import os
import random
import re
import sys
from datetime import datetime

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FEHLER = []


def ok(bed, txt):
    print(("  ok   " if bed else "  FEHL ") + txt)
    if not bed:
        FEHLER.append(txt)


def lade():
    src = open(APP, encoding="utf-8").read()

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]

    def konst(name):
        return re.search(rf"^{name} = .*$", src, re.M).group(0)

    teile = [konst(k) for k in ("GP_SLAVE_PPL", "GP_MIN_LOT", "GP_VORLAUF_MIN", "GP_DD_PLAUSIBEL", "GP_MARGE_RESERVE")]
    teile += [block(n) for n in ("_ap_hhmm", "gp_multiplikator", "gp_dd", "gp_hedge", "gp_richtungen", "gp_zeiten", "gp_takt_faellig", "gp_marge_verteilen", "gp_push_ereignisse")]

    def _wd_num(v):
        try:
            f = float(v)
            return f if f == f else None
        except (TypeError, ValueError):
            return None
    ns = {"_wd_num": _wd_num, "random": random}
    exec("\n".join(teile), ns)
    return ns


def main():
    ns = lade()
    m = ns["gp_multiplikator"]
    print("Multiplikator")
    ok(round(m(10000, 30, 142, 1.0, 0.85), 4) == 0.0167, "The5ers 10.000 $ / 30 Lot / 142 € → ×0,0167 (Emins Plan)")
    ok(round(m(12000, 2.5, 492, 20.0, 0.85), 4) == 0.9647, "FundingPips 12.000 $ / 2,5 Lot / 492 € → ×0,9647 (Emins Plan)")
    ok(round(m(10000, 2.5, 475, 10.0, 0.85), 4) == 0.5588, "FundedNext 10.000 $ / 2,5 Lot / 475 € → ×0,5588 (Emins Plan)")
    ok(m(0, 30, 142, 1, 0.85) is None and m(10000, 30, None, 1, 0.85) is None, "fehlender Wert → None")

    print("Hedge")
    h, g = ns["gp_hedge"](10000, 142, 30, 1.0, 0.85)
    ok(g is None and h["multiplier"] == 0.0167 and h["lots"] == 0.5 and h["slave_risk"] == 142 and h["master_risk"] == 10000,
       "The5ers: Risiko Master 10.000, Slave 142 €, 0,5 Lot Fusion")
    ok(ns["gp_hedge"](None, 142, 30, 1, 0.85)[1].startswith("Max Drawdown fehlt"), "ohne Max-DD → Grund")
    ok(ns["gp_hedge"](10000, None, 30, 1, 0.85)[1].startswith("Kaufpreis fehlt"), "ohne Kaufpreis → Grund")
    ok(ns["gp_hedge"](10000, 142, 30, None, 0.85)[1].startswith("kein Punktwert"), "ohne Punktwert → Grund")
    ok("unter 0,01" in ns["gp_hedge"](10000, 5, 0.1, 1.0, 0.85)[1].replace(".", ","), "Hedge < 0,01 Lot → Grund")
    dd = ns["gp_dd"]
    ok(dd({"max_drawdown": "10000"}, {}, 100000) == 10000, "Max-DD vom Konto")
    ok(dd({"max_drawdown": "100000"}, {"dd_pct": 10}, 100000) == 10000, "Tippfehler 100.000 auf 100k → Kernwert 10 %")
    ok(dd({}, {"dd_usd": 4500}, 150000) == 4500, "ohne Konto-Wert → dd_usd")
    ok(dd({}, {}, 100000) is None, "nichts → None")

    print("Richtung")
    rnd = random.Random(1)
    r = ns["gp_richtungen"]([("A|ftmo", 2500, None), ("B|the5ers", 2000, None), ("A|fundingpips", 500, "sell")], 0, rnd)
    ok(r["A|fundingpips"] == "sell", "feste Richtung (Richtungsschutz) bleibt")
    ok(r["A|ftmo"] == "buy" and r["B|the5ers"] == "sell", "Basis −500 → große Tranche long, nächste wieder short")
    r2 = ns["gp_richtungen"]([("X", 1000, None)], 3000, rnd)
    ok(r2["X"] == "sell", "Long-Überhang der Gruppe → neue Tranche short")

    print("Startzeiten")
    rnd = random.Random(7)
    z = ns["gp_zeiten"]([(i, "u1" if i % 2 else "u2") for i in range(40)], 420, 1040, 0, 3, {}, rnd)
    ok(len(z) == 40 and all(420 <= v <= 1040 for v in z.values()), "40 Pläne alle im Fenster 07:00–17:20")
    for u in ("u1", "u2"):
        ms = sorted(v for k, v in z.items() if ("u1" if k % 2 else "u2") == u)
        ok(all(b - a >= 3 - 1e-9 for a, b in zip(ms, ms[1:])), f"{u}: je ID ≥ 3 min Abstand")
    z2 = ns["gp_zeiten"]([(0, "u1")], 420, 1040, 900, 3, {}, random.Random(1))
    ok(900 <= z2[0] <= 1040, "frühestens jetzt + Vorlauf")
    ok(ns["gp_zeiten"]([(0, "u1")], 420, 1040, 1100, 3, {}, random.Random(1)) == {}, "Fenster vorbei → nichts")
    voll = ns["gp_zeiten"]([(i, "u1") for i in range(5)], 420, 426, 0, 3, {}, random.Random(1))
    ok(2 <= len(voll) <= 3, "Fenster 6 min, Abstand 3 → höchstens 3 Starts, Rest fehlt")

    print("Marge")
    mv = ns["gp_marge_verteilen"]
    # frei 1.200 € → Grenze 1.000 €; je Plan 400 € Marge, 180 min gebunden
    st, raus = mv([("a", "u1", 420, 400), ("b", "u2", 430, 400), ("c", "u3", 440, 400)], 1200, 180, 1040, 3, {})
    ok(st["a"] == 420 and st["b"] == 430 and raus == [] and st["c"] >= 600, "3. Hedge rückt hinter das Ende des 1. (≥ 10:00), keiner fällt raus")
    st, raus = mv([("a", "u1", 420, 1100)], 1200, 180, 1040, 3, {})
    ok(raus == ["a"] and st == {}, "ein Hedge größer als frei − Reserve → raus")
    st, raus = mv([("a", "u1", 900, 600), ("b", "u1", 910, 600)], 1200, 180, 1040, 3, {})
    ok(st == {"a": 900} and raus == ["b"], "kein Platz mehr bis 17:20 → raus")
    st, raus = mv([("a", "u1", 420, 600), ("b", "u1", 423, 600)], 1200, 180, 1040, 3, {"u1": [420, 423, 603]})
    ok(st["a"] == 420 and st["b"] == 608, "rückt wegen Marge auf 10:08 — 10:03 ist von derselben ID belegt (Abstand bleibt)")

    print("Handy-Meldungen")
    pe = ns["gp_push_ereignisse"]
    seit = "2026-10-13T16:00:00+00:00"
    namen = {"u1": "Ahmad"}
    rows = [{"id": "p1", "user_id": "u1", "master_firm": "FTMO", "master_name": "100k …1896", "richtung": "buy", "master_contracts": 2.5,
             "started_at": "2026-10-13T16:05:00+00:00"},
            {"id": "p2", "user_id": "u1", "master_firm": "The5%ers", "master_name": "…5070", "started_at": "2026-10-13T15:00:00+00:00"},
            {"id": "p3", "user_id": "u1", "master_firm": "FundingPips", "master_name": "…0874",
             "sf": {"status": "rot", "at": "2026-10-13T16:10:00.000Z", "msg": "Fusion-Marge zu wenig"}},
            {"id": "p4", "user_id": "u1", "master_firm": "Tradeify", "master_name": "…6825",
             "ss": {"text": "tradeify: dein Konto läuft dort in Gegenrichtung", "at": "2026-10-13T16:12:00+00:00"}},
            {"id": "p5", "user_id": "u1", "sf": {"status": "rot", "schritt": "ziel_erreicht", "at": "2026-10-13T16:10:00Z"}}]
    e = pe(rows, namen, seit)
    keys = [k for k, _t, _x in e]
    ok(keys == ["p1|start", "p3|sf|2026-10-13T16:10:00.000Z", "p4|ss"], "gestartet + Start-Fehler + Richtungsschutz; alter Start und Ziel erreicht nicht")
    ok("Ahmad · FTMO 100k …1896: Long 2.5 — hat alles geklappt" == e[0][2], "Text Trade gestartet, hat alles geklappt, mit ID, Konto, Richtung, Lots")
    ok(e[2][1].startswith("⛔") and "Richtungsschutz" in e[2][1], "Richtungsschutz-Titel")

    print("Takt")
    t = ns["gp_takt_faellig"]
    zt = {"lauf": "06:00", "bis": "17:20"}
    ok(t(datetime(2026, 10, 14, 6, 0), zt) and t(datetime(2026, 10, 14, 17, 4), zt), "Mi 06:00 und 17:04 → läuft")
    ok(not t(datetime(2026, 10, 14, 5, 59), zt) and not t(datetime(2026, 10, 14, 17, 5), zt), "05:59 / 17:05 → nicht")
    ok(not t(datetime(2026, 10, 17, 9, 0), zt), "Samstag → nicht")

    print()
    if FEHLER:
        print(f"ERR {len(FEHLER)} Fehler")
        sys.exit(1)
    print("ALLES OK")


if __name__ == "__main__":
    main()
