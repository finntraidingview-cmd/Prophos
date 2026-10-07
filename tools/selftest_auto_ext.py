#!/usr/bin/env python3
"""Selbsttest: Auto-Planer lässt Puls-Konten ohne External ID aus (app.py ap_ext_fehlt, 08.10.2026) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_auto_ext.py
Lädt die Funktion per Quelltext aus app.py (Muster selftest_reader_wacht: app.py zieht beim Import Flask und Threads)."""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {}
    i = src.index("AP_GRUND_EXT = ")
    j = src.index("\n\n\ndef _ap_konten_laden(", i)
    exec(src[i:j], ns)
    return ns


def main():
    ns = lade()
    f, grund = ns["ap_ext_fehlt"], ns["AP_GRUND_EXT"]
    faelle = [
        ({"external_id": ""}, {"route": "tvv2"}, True, "Orbit ohne External ID → aus"),
        ({"external_id": None}, {"route": "tsv2"}, True, "Topstep V2 ohne External ID → aus"),
        ({"external_id": "   "}, {"route": "tvv2"}, True, "nur Leerzeichen zählt als leer"),
        ({"external_id": "APEX-0000-0001"}, {"route": "tvv2"}, False, "Orbit mit External ID → planen"),
        ({"external_id": ""}, {"route": "mt5v2"}, False, "Echo braucht keine External ID"),
        ({"external_id": ""}, {}, False, "ohne route gilt mt5v2 (Standard des Planers)"),
        ({"external_id": ""}, None, False, "ohne Regel nichts auslassen (die Regel-Prüfung läuft davor)"),
        ({}, {"route": "tvv2"}, True, "Konto ohne Feld external_id → aus"),
    ]
    fehler = 0
    for a, regel, soll, name in faelle:
        ist = f(a, regel)
        ok = ist is soll
        fehler += 0 if ok else 1
        print(("OK  " if ok else "FEHL") + " " + name + (f" (ist {ist}, soll {soll})" if not ok else ""))
    if "External ID" not in grund or "Accounts" not in grund:
        fehler += 1
        print("FEHL Grund-Text nennt External ID + Accounts nicht: " + grund)
    else:
        print("OK   Grund-Text: " + grund)
    print(f"{len(faelle) + 1 - fehler}/{len(faelle) + 1} ok")
    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    main()
