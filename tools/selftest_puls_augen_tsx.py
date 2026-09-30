#!/usr/bin/env python3
"""Selbsttest Topstep-Paket B (app.py, 30.09.2026) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_puls_augen_tsx.py
Prüft: puls_augen_saeubern nimmt die TopstepX-Arten (stand_tsx, inventar_tsx, inventar_tsx_<teil>, wie der live ausgeführte
DB-Check) an und nichts sonst, die daten-Schlüssel zustand/bot bleiben, 60-KB-Deckel je Zeile; /puls-regel meldet tsx 'cdp'|'uia'
über puls_augen_modus (Schalter je PC); PULS_ERGEBNIS_FELDER enthält die neuen TopstepX-Felder und puls_ergebnis_saeubern kappt
positionen wie positionen_danach."""
import json
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "json": json}

    def block(name):
        i = src.index(f"def {name}(")
        return src[i:src.find("\n\n\n", i)]

    def zuweisung(name):
        i = src.index(f"\n{name} = ") + 1
        j = src.index("\n", i)
        while src[i:j].count("(") > src[i:j].count(")"):
            j = src.index("\n", j + 1)
        return src[i:j]
    exec("\n".join([zuweisung(n) for n in ("PULS_AUGEN_MAX", "PULS_AUGEN_ARTEN", "_PULS_AUGEN_ART_TEIL", "PULS_ERGEBNIS_MAX",
                                              "PULS_ERGEBNIS_FELDER", "_PLAN_ID_MUSTER")]
                   + [block(n) for n in ("puls_augen_modus", "puls_augen_saeubern", "puls_ergebnis_saeubern")]), ns)
    return ns


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    S = a["puls_augen_saeubern"]
    for art in ("stand", "inventar", "stand_tsx", "inventar_tsx", "inventar_tsx_grund", "inventar_tsx_konto", "inventar_tsx_bracket"):
        g = S({"art": art, "daten": {"url": "https://topstepx.com/trade", "unbekannt": 1}})
        check(g and g[0] == art and g[1] == {"url": "https://topstepx.com/trade"}, f"Art {art} erlaubt, fremde Schlüssel fallen weg")
    for art in ("inventar_tsx_", "inventar_tsx_Grund", "inventar_tsx_a1", "inventar_tsx_" + "x" * 17, "stand_tv", "tsx", None, 3):
        check(S({"art": art, "daten": {}}) is None, f"Art {art!r} abgelehnt")
    g = S({"art": "inventar_tsx_konto", "daten": {"zustand": "konto_liste_offen", "bot": "2026-09-22.876", "inventar": [1]}})
    check(g and g[1] == {"zustand": "konto_liste_offen", "bot": "2026-09-22.876", "inventar": [1]}, "Schlüssel zustand und bot bleiben erhalten")
    gross = {"art": "inventar_tsx_grund", "daten": {"inventar": "x" * (a["PULS_AUGEN_MAX"] + 10)}}
    check(S(gross) is None, "über 60 KB je Zeile → abgelehnt")

    T = a["puls_augen_modus"]   # /puls-regel: tsx = puls_augen_modus(pc, puls_topstep_pcs)
    check(T("pc-l5o8bv", ["pc-l5o8bv", "pc-c19p2l"]) == "cdp" and T("pc-usq1i6", ["pc-l5o8bv"]) == "uia"
          and T("pc-l5o8bv", []) == "uia" and T("pc-l5o8bv", None) == "uia", "tsx: 'cdp' nur für PCs in puls_topstep_pcs, sonst 'uia'")

    F = a["PULS_ERGEBNIS_FELDER"]
    neu = ("mll", "rpl", "tp_level", "sl_level", "positionen", "plattform", "konto", "klick_at", "bestaetigung", "quelle",
           "balance_start", "balance_end", "today_pnl", "equity_end")
    check(all(k in F for k in neu), "PULS_ERGEBNIS_FELDER enthält die TopstepX-Felder")
    z = a["puls_ergebnis_saeubern"]({"plan_id": "69cc4322-aaaa-bbbb", "art": "order", "stufe": "ende",
                                     "ergebnis": {"ok": True, "mll": 146000, "rpl": -120.5, "tp_level": 30830.25, "sl_level": 30760.0,
                                                  "positionen": [{"symbol": "MNQZ6"}] * 14, "plattform": "tsx", "fremd": 1}}, "pc-l5o8bv")
    e = z["ergebnis"]
    check(e["mll"] == 146000 and e["plattform"] == "tsx" and len(e["positionen"]) == 10 and "fremd" not in e,
          "Ergebnis: TopstepX-Felder bleiben, positionen auf 10 gekappt, fremde fallen weg")

    print("\nALLES OK" if ok else "\nFEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
