#!/usr/bin/env python3
"""Selbsttest MUSTER-PORTFOLIO (app.py, 16.10.2026; Finn: nur zwei Zustände je ID × Firma — aktiv / gesperrt) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_muster_portfolio.py
Prüft muster_portfolio_zeilen (Tacho-Zahlen je Firma) und ap_firma_gesperrt (Auto-Planer lässt jedes Konto einer gesperrten Firma aus).
Lädt die Funktionen per Quelltext aus app.py (Muster selftest_auto_ext: app.py zieht beim Import Flask und Threads)."""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]
    ns = {}
    for f in ("_firm_norm", "muster_portfolio_zeilen", "ap_firma_gesperrt"):
        exec(block(f), ns)
    exec(re.search(r"^MP_TYP_RANG = .*$", src, re.M).group(0), ns)
    i = src.index("\n_FIRM_RULES = [") + 1
    exec(src[i:src.index("\n]\n", i) + 3], ns)     # Schreibweisen-Regeln für _firm_norm
    return ns


def main():
    ns = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    zellen = [{"firma": "The5%ers", "status": "frei", "untergrenze": 3, "bestand_echt": 2, "abdeckung": 0.9, "unterwegs_n": 2,
               "konten": [{"account_id": "k2", "name": "B", "typ": "funded_cfd", "balance": 101000.0, "chance": 0.5},
                          {"account_id": "k1", "name": "A", "typ": "phase1", "balance": 99000.0, "wert_eur": 12.0}]},
              {"firma": "Tradeify", "status": "pausiert", "untergrenze": 20000, "bestand_echt": 30000, "abdeckung": 1.0},
              {"firma": "FTMO", "status": "gesperrt", "untergrenze": 100000, "bestand_echt": 50000, "abdeckung": 0.3},
              {"firma": "Apex Trader", "status": "frei", "untergrenze": 0, "bestand_echt": 0, "abdeckung": None}]
    ziele = {"The5%ers": {"art": "stueck", "typen": ["funded_cfd"], "reihe": 7},
             "Tradeify": {"art": "plus_ueber_start", "typen": ["winning_days"], "reihe": 1},
             "FTMO": {"art": "groessen_summe", "typen": ["funded_cfd"], "reihe": 4},
             "Apex Trader": {"art": "stueck", "typen": ["winning_days"], "reihe": 3}}
    r = ns["muster_portfolio_zeilen"](zellen, ziele)
    je = {x["firma"]: x for x in r}
    check([x["firma"] for x in r] == ["Tradeify", "Apex Trader", "FTMO", "The5%ers"], "Reihenfolge nach reihe der Vorrat-Ziele")
    check(je["Tradeify"]["gesichert_pct"] == 100.0, "über dem Ziel → gedeckelt 100 %")
    check(je["The5%ers"]["gesichert_pct"] == 66.7 and je["The5%ers"]["erwartet_pct"] == 90.0, "Stück-Ziel 2/3 → 66,7 %, mit Funnel 90 %")
    check(je["FTMO"]["erwartet_pct"] == 50.0, "erwartet nie unter gesichert (abdeckung 30 % < 50 %)")
    check(je["Apex Trader"]["gesichert_pct"] is None and je["Apex Trader"]["erwartet_pct"] is None, "ohne Untergrenze kein Prozent")
    check(je["Tradeify"]["status"] == "frei", "alte „pausiert“-Zeile zeigt der Tacho als aktiv")
    check(je["FTMO"]["status"] == "gesperrt", "gesperrt bleibt gesperrt")
    kt = je["The5%ers"]["konten"]
    check([k["account_id"] for k in kt] == ["k1", "k2"], "Konten nach Stufe (Phase 1 vor Funded CFD)")
    check(set(kt[0]) == {"account_id", "name", "typ", "groesse", "balance", "ccy", "balance_at", "waiting"}, "je Konto nur Anzeige-Felder (keine Chance/Kaufwerte)")
    check(je["FTMO"]["konten"] == [], "ohne Konten leere Liste")

    g = ns["ap_firma_gesperrt"]
    sp = {("u1", "FundedNext")}
    check(g({"user_id": "u1", "firm": "FundedNext", "created_at": "2026-10-01T00:00:00+00:00"}, sp) is True,
          "gesperrt gilt für JEDES Konto der Firma (auch vor der Sperre angelegt)")
    check(g({"user_id": "u1", "firm": "fundednext"}, sp) is True, "Schreibweise egal (_firm_norm)")
    check(g({"user_id": "u1", "firm": "FundedNext Futures"}, sp) is False, "FundedNext Futures ist eine eigene Firma")
    check(g({"user_id": "u2", "firm": "FundedNext"}, sp) is False, "andere ID nicht betroffen")
    check(g({"user_id": "u1", "firm": "FundedNext"}, set()) is False, "ohne Sperr-Matrix (Lesefehler → leer) plant der Planer wie bisher")

    print("OK" if ok else "FEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
