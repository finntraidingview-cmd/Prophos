#!/usr/bin/env python3
"""Selbsttest Topstep-Paket B (app.py, 30.09.2026) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_puls_augen_tsx.py
Prüft: puls_augen_saeubern nimmt die TopstepX-Arten (stand_tsx, inventar_tsx, inventar_tsx_<teil>, wie der live ausgeführte
DB-Check) an und nichts sonst, die daten-Schlüssel zustand/bot bleiben, 60-KB-Deckel je Zeile; /puls-regel meldet tsx 'cdp'|'uia'
über puls_augen_modus (Schalter je PC); PULS_ERGEBNIS_FELDER enthält die neuen TopstepX-Felder und puls_ergebnis_saeubern kappt
positionen wie positionen_danach; warnung/unklar (B37) bleiben erhalten."""
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
                                              "PULS_ERGEBNIS_FELDER", "_PLAN_ID_MUSTER", "_PULS_REGEL_CACHE", "PULS_REGEL_CACHE_S")]
                   + [block(n) for n in ("puls_augen_modus", "puls_augen_saeubern", "puls_ergebnis_saeubern", "puls_regel_stand")]), ns)
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
    g = S({"art": "stand_tsx", "daten": {"kopf": {"konto": "150KTC-…", "balance": 148210.5}, "positionen_sichtbar": True, "flach": False,
                                         "fremd": 1}})
    check(g and g[1] == {"kopf": {"konto": "150KTC-…", "balance": 148210.5}, "positionen_sichtbar": True, "flach": False},
          "AUGEN-WL-2: kopf, positionen_sichtbar und flach bleiben (stand_tsx aus augen_tsx.js), fremde fallen weg")
    check(S({"art": "stand_tsx", "daten": {"kopf": "x" * (a["PULS_AUGEN_MAX"] + 10)}}) is None, "AUGEN-WL-2: Deckel gilt auch für kopf")
    gross = {"art": "inventar_tsx_grund", "daten": {"inventar": "x" * (a["PULS_AUGEN_MAX"] + 10)}}
    check(S(gross) is None, "über 60 KB je Zeile → abgelehnt")

    T = a["puls_augen_modus"]   # /puls-regel: tsx = puls_augen_modus(pc, puls_topstep_pcs)
    check(T("pc-l5o8bv", ["pc-l5o8bv", "pc-c19p2l"]) == "cdp" and T("pc-usq1i6", ["pc-l5o8bv"]) == "uia"
          and T("pc-l5o8bv", []) == "uia" and T("pc-l5o8bv", None) == "uia", "tsx: 'cdp' nur für PCs in puls_topstep_pcs, sonst 'uia'")

    # PULS-REGEL-CACHE (30.09.2026, Vorfall Mike): die Liste gilt spätestens nach PULS_REGEL_CACHE_S Sekunden, nicht erst nach 60
    R, C, zeile, rufe = a["puls_regel_stand"], a["_PULS_REGEL_CACHE"], {"puls_augen_cdp": ["pc-usq1i6"], "puls_topstep_pcs": []}, []

    def lesen(tab, params):
        rufe.append(params["select"])
        return [dict(zeile)]
    check(a["PULS_REGEL_CACHE_S"] <= 10 and R(1000.0, lesen) and len(rufe) == 1 and T("pc-l5o8bv", C["tsx"]) == "uia",
          "Regel-Cache: erster Aufruf liest, Mikes PC noch 'uia'")
    zeile["puls_topstep_pcs"] = ["pc-l5o8bv"]
    check(R(1005.0, lesen) and len(rufe) == 1 and T("pc-l5o8bv", C["tsx"]) == "uia", "Regel-Cache: nach 5 s noch der alte Stand (kein zweiter Read)")
    check(R(1011.0, lesen) and len(rufe) == 2 and T("pc-l5o8bv", C["tsx"]) == "cdp", "Regel-Cache: nach 11 s frisch gelesen → Mikes PC 'cdp' (vorher erst nach 60 s)")

    def kaputt(tab, params):
        raise RuntimeError("DB weg")
    check(R(1030.0, kaputt) and T("pc-l5o8bv", C["tsx"]) == "cdp" and C["at"] == 1030.0,
          "Regel-Cache: DB weg → letzter guter Stand bleibt, nächster Versuch nach Ablauf")

    def ohne_spalte(tab, params):
        if "puls_topstep_pcs" in params["select"]:
            raise RuntimeError("42703")
        return [{"puls_augen_cdp": ["pc-usq1i6", "pc-neu"]}]
    check(R(1050.0, ohne_spalte) and C["cdp"] == ["pc-usq1i6", "pc-neu"] and C["tsx"] == ["pc-l5o8bv"],
          "Regel-Cache: Spalte fehlt → Augen-Regel frisch, tsx bleibt beim letzten guten Stand")
    C.update(at=0.0, gut=False, tsx_gut=False)
    check(R(2000.0, kaputt) is False, "Regel-Cache: nie gelesen und DB weg → False (503, der Bot behält seine Regel)")

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
    z2 = a["puls_ergebnis_saeubern"]({"plan_id": "69cc4322-aaaa-bbbb", "art": "order", "stufe": "ende",
                                      "ergebnis": {"ok": True, "gesendet": True, "warnung": "SL-Bracket abgelehnt " + "x" * 400}}, "pc-l5o8bv")
    z3 = a["puls_ergebnis_saeubern"]({"plan_id": "69cc4322-aaaa-bbbb", "art": "order", "stufe": "ende",
                                      "ergebnis": {"ok": False, "gesendet": True, "unklar": True, "code": "beweis", "retry_ok": False}}, "pc-l5o8bv")
    check("warnung" in F and "unklar" in F and z2["ergebnis"]["warnung"].startswith("SL-Bracket") and len(z2["ergebnis"]["warnung"]) == 300
          and z3["ergebnis"]["unklar"] is True and z3["ergebnis"]["code"] == "beweis",
          "B37: warnung (auf 300 gekappt) und unklar überleben das Säubern (Nachholen braucht beide)")

    print("\nALLES OK" if ok else "\nFEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
