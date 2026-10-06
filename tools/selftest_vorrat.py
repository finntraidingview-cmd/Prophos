#!/usr/bin/env python3
"""Selbsttest Vorrat (app.py, VORRAT, 05.10.2026) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_vorrat.py
Lädt die Funktionen per Quelltext aus app.py (wie selftest_liq_regeln: app.py zieht beim Import Flask und Threads).
Ziele = die 7 Zeilen von public.vorrat_ziele nach sql/2026-10-05_vorrat.sql. Fälle = Finns Beispiele vom 05.10.2026:
Tradeify Winning Days 164.000 → +14.000 und 160.000 → +10.000, Topstep Express 3.000 → +3.000, Funded vor dem Big Trade
ist kein Vorrat, The5ers 1 × 100k + 1 × 200k. IDs und Konten sind erfunden."""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")

ZIELE = {
    "Tradeify":    {"art": "plus_ueber_start", "typen": ["winning_days"], "von": 20000, "bis": 30000, "groessen": None, "reihe": 1},
    "Topstep":     {"art": "plus_ueber_start", "typen": ["winning_days"], "von": 20000, "bis": 30000, "groessen": None, "reihe": 2},
    "Apex Trader": {"art": "stueck", "typen": ["winning_days"], "von": None, "bis": None,
                    "groessen": [{"groesse": None, "stueck": 1}], "reihe": 3},
    "FTMO":        {"art": "groessen_summe", "typen": ["funded_cfd", "funded"], "von": 100000, "bis": 200000, "groessen": None,
                    "kauf_einheit": "100k oder 200k", "reihe": 4},
    "FundedNext":  {"art": "groessen_summe", "typen": ["funded_cfd", "funded"], "von": 200000, "bis": 300000, "groessen": None, "reihe": 5},
    "FundingPips": {"art": "groessen_summe", "typen": ["funded_cfd", "funded"], "von": 150000, "bis": 250000, "groessen": None, "reihe": 6},
    "The5%ers":    {"art": "stueck", "typen": ["funded_cfd", "funded"], "von": None, "bis": None,
                    "groessen": [{"groesse": 100000, "stueck": 1}, {"groesse": 200000, "stueck": 1}], "reihe": 7},
}
A, B, C = "id-a", "id-b", "id-c"


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {}

    def block(name):
        i = src.index(f"def {name}(")
        return src[i:src.find("\n\n\n", i)]
    i = src.index("VORRAT_TYPEN = (")
    konst = src[i:src.index("VORRAT_SQL", i)]
    exec("\n".join([konst] + [block(f) for f in ("vorrat_groesse", "vorrat_bestand", "vorrat_rechnen")]), ns)
    return ns


def k(uid, firma, typ, balance=None, groesse=None, express=False, waiting=False):
    return {"user_id": uid, "firma": firma, "typ": typ, "groesse": groesse, "balance": balance, "express": express, "waiting": waiting}


def main():
    ns = lade()
    groesse, rechnen = ns["vorrat_groesse"], ns["vorrat_rechnen"]
    fehler, n = [], 0

    def pruef(name, ist, soll):
        nonlocal n
        n += 1
        if ist != soll:
            fehler.append(f"{name}: ist {ist!r}, soll {soll!r}")

    def zelle(erg, uid, firma):
        return next((z for z in erg["zellen"] if z["user_id"] == uid and z["firma"] == firma), None)

    # ── Kontogröße ──
    pruef("CFD 92.000 = 100k (Finn: FundedNext 100k Phase 1 bei 92.000)", groesse(None, 92000, True), 100000.0)
    pruef("CFD 60.000 = 50k", groesse(None, 60000, True), 50000.0)
    pruef("CFD 180.000 = 200k", groesse(None, 180000, True), 200000.0)
    pruef("CFD: Balance schlägt die gespeicherte Größe", groesse(50000, 104000, True), 100000.0)
    pruef("CFD ohne Balance: gespeicherte Größe", groesse(200000, None, True), 200000.0)
    pruef("Futures: gespeicherte Größe", groesse(150000, 164000, False), 150000.0)
    pruef("Futures ohne Größe: nächste Standardgröße", groesse(None, 164000, False), 150000.0)
    pruef("Futures ohne alles: unbekannt", groesse(None, None, False), None)

    # ── Finns Beispiele: Plus über Start ──
    konten = [
        k(A, "Tradeify", "winning_days", 164000, 150000), k(A, "Tradeify", "winning_days", 160000, 150000),
        k(A, "Tradeify", "funded", 153000, 150000), k(A, "Tradeify", "challenge", 150900, 150000),
        k(A, "Tradeify", "challenge", 151200, 150000),
        k(B, "Topstep", "winning_days", 3000, 150000, express=True),
        k(C, "Tradeify", "winning_days", 148000, 150000), k(C, "Tradeify", "winning_days", None, 150000),
    ]
    erg = rechnen(konten, ZIELE, {}, [A, B, C])
    z = zelle(erg, A, "Tradeify")
    pruef("Tradeify A: Bestand 14.000 + 10.000", z["bestand"], 24000.0)
    pruef("Tradeify A: im Ziel (20–30k)", (z["lage"], z["fehlt"], z["bis_voll"]), ("im_ziel", 0.0, 6000.0))
    pruef("Tradeify A: Funded vor dem Big Trade ist Funnel, kein Vorrat", (z["bestand_n"], z["funnel"]["funded"]["n"]), (2, 1))
    pruef("Tradeify A: Funnel Challenge 2 × 150k", z["funnel"]["challenge"], {"n": 2, "groesse": 300000.0})
    pruef("Tradeify A: 5 Konten", z["konten_n"], 5)
    z = zelle(erg, B, "Topstep")
    pruef("Topstep B: Express 3.000 → +3.000", z["bestand"], 3000.0)
    pruef("Topstep B: unter Ziel, fehlt 17.000, bis voll 27.000", (z["lage"], z["fehlt"], z["bis_voll"]), ("unter", 17000.0, 27000.0))
    pruef("Topstep B: Express-Größe bleibt die gespeicherte", z["funnel"]["winning_days"]["groesse"], 150000.0)
    z = zelle(erg, C, "Tradeify")
    pruef("Tradeify C: Konto unter Start zählt 0, nie negativ", z["bestand"], 0.0)
    pruef("Tradeify C: Konto ohne Balance = unklar", z["unklar"], 1)
    z = zelle(erg, B, "Tradeify")
    pruef("Tradeify B: ID ohne Konten hat trotzdem eine Zelle", (z["konten_n"], z["bestand"], z["lage"], z["fehlt"]), (0, 0.0, "unter", 20000.0))
    pruef("Reihenfolge der Firmen = reihe", [f["firma"] for f in erg["firmen"]],
          ["Tradeify", "Topstep", "Apex Trader", "FTMO", "FundedNext", "FundingPips", "The5%ers"])
    pruef("Futures-Firma ist nicht CFD, CFD-Firma schon",
          {f["firma"]: f["cfd"] for f in erg["firmen"] if f["firma"] in ("Tradeify", "FTMO")}, {"Tradeify": False, "FTMO": True})

    # ── Stückzahl: Apex, The5ers ──
    konten = [
        k(A, "Apex Trader", "winning_days", 153000, 150000), k(A, "Apex Trader", "funded", 151000, 150000),
        k(B, "Apex Trader", "funded", 151000, 150000),
        k(A, "The5%ers", "funded_cfd", 101000), k(B, "The5%ers", "funded_cfd", 101000), k(B, "The5%ers", "funded_cfd", 99000),
        k(C, "The5%ers", "funded_cfd", 100500), k(C, "The5%ers", "funded_cfd", 204000), k(C, "The5%ers", "funded_cfd", 199000),
    ]
    erg = rechnen(konten, ZIELE, {}, [A, B, C])
    z = zelle(erg, A, "Apex Trader")
    pruef("Apex A: 1 Winning-Days-Konto = im Ziel", (z["bestand"], z["lage"], z["fehlt"]), (1, "im_ziel", 0))
    z = zelle(erg, B, "Apex Trader")
    pruef("Apex B: nur Funded = fehlt 1", (z["bestand"], z["lage"], z["fehlt"]), (0, "unter", 1))
    z = zelle(erg, A, "The5%ers")
    pruef("The5ers A: 100k da, 200k fehlt", (z["bestand"], z["fehlt"], z["lage"]), (1, 1, "unter"))
    pruef("The5ers A: Fächer", z["teile"], [{"groesse": 100000.0, "soll": 1, "ist": 1, "fehlt": 0},
                                              {"groesse": 200000.0, "soll": 1, "ist": 0, "fehlt": 1}])
    z = zelle(erg, B, "The5%ers")
    pruef("The5ers B: zwei 100k ersetzen kein 200k", (z["bestand"], z["fehlt"], z["lage"], z["teile"][0]["ist"]), (1, 1, "unter", 2))
    z = zelle(erg, C, "The5%ers")
    pruef("The5ers C: 100k + 2 × 200k = über Ziel", (z["bestand"], z["fehlt"], z["lage"]), (2, 0, "ueber"))
    erg2 = rechnen([k(A, "The5%ers", "funded_cfd", 101000, waiting=True), k(A, "The5%ers", "funded_cfd", 199000)], ZIELE, {}, [A])
    pruef("The5ers: Waiting zählt bei Stückzahl als Konto, wartend = Anzahl", (zelle(erg2, A, "The5%ers")["bestand"], zelle(erg2, A, "The5%ers")["wartend"]), (2, 1))

    # ── Summe der Kontogrößen: FTMO, FundedNext, FundingPips ──
    konten = [
        k(A, "FTMO", "funded_cfd", 104000), k(A, "FTMO", "phase1", 92000), k(A, "FTMO", "phase2", 101000),
        k(A, "FundedNext", "funded_cfd", 100500),
        k(A, "FundingPips", "funded_cfd", 99000), k(A, "FundingPips", "funded_cfd", 201000),
        k(B, "FTMO", "funded_cfd", 100000, waiting=True),
        k(B, "FundedNext", "funded", 205000), k(B, "FundedNext", "funded_cfd", None, 100000), k(B, "FundedNext", "funded_cfd", None),
    ]
    erg = rechnen(konten, ZIELE, {}, [A, B])
    z = zelle(erg, A, "FTMO")
    pruef("FTMO A: 1 × 100k Funded = im Ziel", (z["bestand"], z["lage"], z["fehlt"], z["bis_voll"]), (100000.0, "im_ziel", 0.0, 100000.0))
    pruef("FTMO A: Phasen im Funnel", (z["funnel"]["phase1"], z["funnel"]["phase2"]["n"]), ({"n": 1, "groesse": 100000.0}, 1))
    z = zelle(erg, A, "FundedNext")
    pruef("FundedNext A: 100k von 200–300k", (z["bestand"], z["lage"], z["fehlt"], z["bis_voll"]), (100000.0, "unter", 100000.0, 200000.0))
    z = zelle(erg, A, "FundingPips")
    pruef("FundingPips A: 300k = über der Obergrenze", (z["bestand"], z["lage"], z["fehlt"]), (300000.0, "ueber", 0.0))
    z = zelle(erg, B, "FTMO")
    pruef("FTMO B: Waiting for Payout zählt (Finn 05.10.2026) und steht als eigener Anteil drin",
          (z["bestand"], z["wartend"], z["funnel"]["waiting"]["n"], z["funnel"]["funded_cfd"]["n"]), (100000.0, 100000.0, 1, 1))
    pruef("FTMO A: ohne Waiting ist der Anteil 0", zelle(erg, A, "FTMO")["wartend"], 0.0)
    pruef("Kauf-Einheit läuft mit dem Ziel durch", next(f["ziel"].get("kauf_einheit") for f in erg["firmen"] if f["firma"] == "FTMO"), "100k oder 200k")
    z = zelle(erg, B, "FundedNext")
    pruef("FundedNext B: CFD mit Typ funded zählt, ohne Balance die gespeicherte Größe, ohne beides unklar",
          (z["bestand"], z["unklar"], z["bestand_n"]), (300000.0, 1, 3))
    erg = rechnen(konten, ZIELE, {}, [A, B], waiting_zaehlt=False)
    z = zelle(erg, B, "FTMO")
    pruef("FTMO B: Waiting zählt nicht → Bestand 0, bleibt im Funnel", (z["bestand"], z["lage"], z["funnel"]["waiting"]["n"]), (0.0, "unter", 1))

    # ── Sperr-Matrix (frei · pausiert · gesperrt), Standard, nur Firmen mit Ziel ──
    konten = [k(A, "Tradeify", "winning_days", 175000, 150000), k(A, "Lucid Trading", "challenge", 50200, 50000),
              k(B, "Lucid Trading", "challenge", 50200, 50000), k(B, "Tradeify", "sonderbar", 150900, 150000)]
    matrix = {(A, "Tradeify"): "gesperrt", (B, "FTMO"): "pausiert", (A, "FTMO"): "kaputt", (B, "Blue Guardian"): "gesperrt",
              ("fremd", "FTMO"): "gesperrt"}
    erg = rechnen(konten, ZIELE, matrix, [A, B])
    z = zelle(erg, A, "Tradeify")
    pruef("Sperre aus der Matrix (Bestand wird trotzdem gerechnet)", (z["status"], z["gesetzt"], z["bestand"]), ("gesperrt", True, 25000.0))
    z = zelle(erg, B, "FTMO")
    pruef("pausiert (Finn 06.10.2026) läuft als dritter Zustand durch", (z["status"], z["gesetzt"], z["lage"]), ("pausiert", True, "unter"))
    pruef("unbekannter Status in der Matrix = Standard", (zelle(erg, A, "FTMO")["status"], zelle(erg, A, "FTMO")["gesetzt"]), ("frei", False))
    z = zelle(erg, B, "Tradeify")
    pruef("ohne Matrix-Zeile = Standard frei", (z["status"], z["gesetzt"]), ("frei", False))
    pruef("unbekannter Kontotyp zählt als Challenge", z["funnel"], {"challenge": {"n": 1, "groesse": 150000.0}})
    pruef("Firmen ohne Ziel sind nicht auf der Seite — auch nicht mit Konten oder gesetztem Status",
          (zelle(erg, A, "Lucid Trading"), zelle(erg, B, "Blue Guardian"), [f["firma"] for f in erg["firmen"]]),
          (None, None, ["Tradeify", "Topstep", "Apex Trader", "FTMO", "FundedNext", "FundingPips", "The5%ers"]))
    pruef("Matrix-Zeile einer fremden ID erzeugt nichts", zelle(erg, "fremd", "FTMO"), None)
    pruef("jede ID × jede Ziel-Firma = eine Zelle", len(erg["zellen"]), 14)
    erg = rechnen(konten, ZIELE, {(B, "Tradeify"): "frei"}, [A, B], standard="gesperrt")
    pruef("Standard gesperrt: alles zu, gesetztes frei bleibt frei",
          (zelle(erg, A, "Tradeify")["status"], zelle(erg, A, "FTMO")["status"], zelle(erg, B, "Tradeify")["status"]),
          ("gesperrt", "gesperrt", "frei"))
    erg = rechnen(konten, {}, {}, [A, B])
    pruef("ohne Ziele (SQL fehlt): keine Firmen, keine Zellen", (erg["firmen"], erg["zellen"]), ([], []))

    if fehler:
        print(f"FEHLER — {len(fehler)} von {n} Prüfungen:")
        for f in fehler:
            print("  ✗", f)
        sys.exit(1)
    print(f"OK — {n}/{n} Prüfungen")


if __name__ == "__main__":
    main()
