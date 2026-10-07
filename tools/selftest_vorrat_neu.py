#!/usr/bin/env python3
"""Selbsttest: Vorrat rechnet sofort neu, wenn Konten nach dem letzten Lauf angelegt wurden (app.py vorrat2_neu_seit_lauf,
08.10.2026, Anlass: 3 neue Tradeify-Konten fehlten bis zum nächsten 6-h-Takt). Rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_vorrat_neu.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    i = src.index("def vorrat2_neu_seit_lauf(")
    j = src.index("\n\n\ndef vorrat2_anhaengen(", i)
    ns = {}
    exec(src[i:j], ns)
    return ns["vorrat2_neu_seit_lauf"]


def main():
    f = lade()
    lauf = "2026-10-07T17:00:25.597576+00:00"
    faelle = [
        ([{"_angelegt": ["2026-10-07T22:12:24.486485+00:00"]}], lauf, True, "Konto nach dem Lauf angelegt → neuer Lauf"),
        ([{"_angelegt": ["2026-10-01T09:00:00+00:00", "2026-10-07T16:59:00+00:00"]}], lauf, False, "alle Konten vor dem Lauf → nichts"),
        ([{"_angelegt": []}, {"_angelegt": None}], lauf, False, "Zellen ohne Konten → nichts"),
        ([{"_angelegt": [None, "2026-10-07T22:12:24+00:00"]}], lauf, True, "leere Einträge werden übersprungen"),
        ([{"_angelegt": ["2026-10-07T22:12:24+00:00"]}], None, False, "ohne Lauf-Zeit keine Aussage (es läuft ohnehin einer)"),
        ([], lauf, False, "keine Zellen → nichts"),
        ([{"_angelegt": ["2026-10-07T22:12:24.486485+00:00"]}], "2026-10-07 17:00:25.597576+00", True, "Lauf-Zeit mit Leerzeichen/+00 (SQL-Form) → gleiche Form, Konto danach"),
        ([{"_angelegt": ["2026-10-07T16:30:00+00:00"]}], "2026-10-07 17:00:25+00", False, "SQL-Form: Konto VOR dem Lauf am selben Tag → nichts (vorher machte T gegen Leerzeichen jeden Tagesstempel groesser)"),
        ([{"_angelegt": ["2026-10-07 22:12:24+00"]}], "2026-10-07T17:00:25Z", True, "gemischte Formen inkl. Z"),
    ]
    fehler = 0
    for zellen, at, soll, name in faelle:
        ist = f(zellen, at)
        ok = ist is soll
        fehler += 0 if ok else 1
        print(("OK  " if ok else "FEHL") + " " + name + (f" (ist {ist}, soll {soll})" if not ok else ""))
    print(f"{len(faelle) - fehler}/{len(faelle)} ok")
    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    main()
