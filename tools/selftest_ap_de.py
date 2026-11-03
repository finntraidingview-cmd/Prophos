#!/usr/bin/env python3
"""Selbsttest ZAHL DEUTSCH (app.py _ap_de, 03.11.2026 — Befund S4: 1200,4 mit stellen=0 → „12 $ vor dem TP“, weil rstrip("0") auch die Ganzzahl
kürzte). Erwartet: Tausenderpunkt, Komma, Nachkomma-Nullen weg, nie „-0“. Rein rechnend, ohne Netz. Aufruf: python3 tools/selftest_ap_de.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FEHLER = []


def lade():
    src = open(APP, encoding="utf-8").read()
    i = src.index("\ndef _ap_de(") + 1
    ns = {}
    exec(src[i:src.find("\n\n\n", i)], ns)
    return ns["_ap_de"]


def check(ist, soll, name):
    ok = ist == soll
    print(("✓ " if ok else "✗ ") + f"{name}: {ist!r}" + ("" if ok else f" (soll {soll!r})"))
    if not ok:
        FEHLER.append(name)


def main():
    de = lade()
    # die fünf Werte aus dem Auftrag, Standard (2 Stellen) und 0 Stellen wie in „… $ vor dem TP“
    for x, s2, s0 in ((1200.4, "1.200,4", "1.200"), (1200, "1.200", "1.200"), (0.5, "0,5", "0"), (15000, "15.000", "15.000"),
                      (-4412.22, "-4.412,22", "-4.412")):
        check(de(x), s2, f"{x} (2 Stellen)")
        check(de(x, 0), s0, f"{x} (0 Stellen)")
    # bisherige Fälle der Notizen bleiben gleich
    check(de(0.18), "0,18", "Lots 0,18")
    check(de(2.0), "2", "Lots 2")
    check(de(2.5), "2,5", "Lots 2,5")
    check(de(1.999), "2", "1,999 → 2 (kein „2,“)")
    check(de(12.5, 1), "12,5", "1 Stelle")
    check(de(0.0151, 3), "0,015", "3 Stellen (€ je $)")
    check(de(-0.001), "0", "kein „-0“")
    check(de(1234567.891), "1.234.567,89", "Millionen")
    if FEHLER:
        print(f"\n{len(FEHLER)} Fehler")
        sys.exit(1)
    print("\nalle grün")


if __name__ == "__main__":
    main()
