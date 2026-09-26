#!/usr/bin/env python3
"""Selbsttest /admin/konten-pruefen (app.py, KONTEN PRÜFEN, 27.09.2026, B10) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_konten_pruefen.py
Prueft Eingabe-Bereinigung (Liste, trimmen, Dubletten, Deckel) und die Treffer ueber alle Nutzer (Gross/klein egal,
Person, archiviert, nur Treffer)."""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {}

    def block(name):
        i = src.index(f"def {name}(")
        return src[i:src.find("\n\n\n", i)]
    exec("\n".join([re.search(r"^KONTEN_PRUEFEN_MAX = .*$", src, re.M).group(0), block("konten_pruefen_ids"), block("konten_treffer")]), ns)
    return ns


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    ids = a["konten_pruefen_ids"]
    check(ids("x") is None and ids(None) is None, "keine Liste → None (400)")
    check(ids([" TDFYSL150813173931 ", "tdfysl150813173931", "", None, {"x": 1}, 12345]) == ["TDFYSL150813173931", "12345"],
          "trimmen, Gross/klein-Dubletten, Leere und Unsinn raus, Zahlen als Text")
    check(len(ids([f"ID{i}" for i in range(500)])) == 200, "hoechstens 200 IDs")

    konten = [{"id": "a1", "user_id": "u-moritz", "name": "Tradeify 150k", "firm": "Tradeify", "account_type": "funded",
               "external_id": "TDFYSL150813173931"},
              {"id": "a2", "user_id": "u-jacob", "name": "Tradeify 50k", "firm": "Tradeify", "account_type": "challenge",
               "external_id": " tdfysl150800892182 "},
              {"id": "a3", "user_id": "u-finn", "name": "Apex", "firm": "Apex", "account_type": "funded", "external_id": "PAAPEX6416990000008"}]
    t = a["konten_treffer"](["tdfysl150813173931", "TDFYSL150800892182", "NEU123"], konten,
                            {"u-moritz": "Moritz", "u-jacob": "Jacob"}, {"a2"})
    check([x["account_id"] for x in t] == ["a1", "a2"], "Treffer ueber ALLE Nutzer, Gross/klein + Leerzeichen egal, Reihenfolge der Eingabe")
    check(t[0] == {"external_id": "TDFYSL150813173931", "account_id": "a1", "person": "Moritz", "name": "Tradeify 150k",
                   "firm": "Tradeify", "account_type": "funded", "archiviert": False},
          "Vertrag: genau external_id, account_id, person, name, firm, account_type, archiviert")
    check(t[1]["archiviert"] is True and t[1]["external_id"] == "tdfysl150800892182", "archiviert aus dem Archiv-Stand, external_id wie gespeichert")
    check(a["konten_treffer"](["NEU123"], konten, {}, set()) == [], "neue ID → keine Treffer, keine fremden Daten")
    dop = konten + [dict(konten[0], id="a9", user_id="u-x")]
    t2 = a["konten_treffer"](["TDFYSL150813173931"], dop, {}, set())
    check([x["account_id"] for x in t2] == ["a1", "a9"] and t2[1]["person"] == "u-x", "doppelt vorhandene ID → beide Konten; Person ohne Namen = ID-Kuerzel")

    print("\nALLES GRUEN" if ok else "\nFEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
