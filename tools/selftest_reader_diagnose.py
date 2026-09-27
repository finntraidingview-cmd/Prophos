#!/usr/bin/env python3
"""Selbsttest Reader-Diagnose (app.py, READER-DIAGNOSE, 26.09.2026, B9) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_reader_diagnose.py
Prueft reader_diagnose_saeubern (Rolle, bekannte Felder, kurze Texte, Groessendeckel) und das Kennungs-Muster."""
import json
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "json": json}
    i = src.index("def reader_diagnose_saeubern(")
    exec("\n".join([re.search(r"^READER_KENNUNG_MUSTER = .*$", src, re.M).group(0),
                    re.search(r"^READER_DIAGNOSE_MAX = .*$", src, re.M).group(0), src[i:src.find("\n\n\n", i)]]), ns)
    return ns


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    m, s = a["READER_KENNUNG_MUSTER"], a["reader_diagnose_saeubern"]
    check(m.fullmatch("pc-usq1i6") and m.fullmatch("host-desktop-4ab") and not m.fullmatch("host-") and not m.fullmatch("pc-x/../y"),
          "Kennung: pc-… oder host-…, nichts anderes")
    r, d = s({"rolle": "aufsicht", "version": "0.9.7", "pid": 123, "sha_fehler": "URLError: " + "x" * 500, "boese": 1,
              "wartend": {"sha": "a" * 40, "version": "0.9.8", "seit": 1.0, "daten": "RIESIG"},
              "tausch": {"sha": "b" * 40, "version": "0.9.6", "at": 2.0, "bewiesen": 0},
              "schlecht": ["c" * 40], "meldungen": [f"m{i}" for i in range(20)], "pid_str": "nein"})
    check(r == "aufsicht" and "boese" not in d and len(d["sha_fehler"]) == 200 and "daten" not in d["wartend"]
          and d["tausch"]["bewiesen"] is False and len(d["meldungen"]) == 8 and d["meldungen"][-1] == "m19",
          "Aufsicht-Paket: bekannte Felder, gekuerzt, wartendes Update ohne Dateiinhalt, letzte 8 Meldungen")
    check(s({"rolle": "kind", "pid": "1; drop"})[1]["pid"] is None and s({"rolle": "hacker"}) == (None, None) and s(None) == (None, None),
          "Kind-Paket: Zahlen nur als Zahl; falsche Rolle/Unsinn abgewiesen")

    r3, d3 = s({"rolle": "kind", "port_pids": [5120, 7344, "x", True], "tick_kerzen_5min": 240, "sperre": True,
                "beendet": ["Reader-Baum 100"] * 9, "einzel_meldung": "alte(n) Reader beendet"})
    check(r3 == "kind" and d3["port_pids"] == [5120, 7344] and d3["tick_kerzen_5min"] == 240 and d3["sperre"] is True
          and len(d3["beendet"]) == 6 and d3["einzel_meldung"] == "alte(n) Reader beendet",
          "0.9.8-Felder: Port-Lauscher nur Zahlen, Tick-Updates, Sperre, hoechstens 6 Beendete")

    print("\nALLES GRUEN" if ok else "\nFEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
