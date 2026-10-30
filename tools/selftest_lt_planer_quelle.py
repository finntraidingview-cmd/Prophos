#!/usr/bin/env python3
"""Selbsttest HERKUNFT IM RADAR (app.py lt_planer_quelle, 30.10.2026 — Finn: „Funded Planer CFD" / „Challenge Planer CFD" am Trade).
Aufruf:  python3 tools/selftest_lt_planer_quelle.py   (ohne Netz; prüft auch, dass alle Planer ihre Notiz noch so beginnen)"""
import os
import re
import sys

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.py")
src = open(APP, encoding="utf-8").read()
i = src.index("\ndef lt_planer_quelle(") + 1
ns = {}
exec(src[i:src.find("\n\n\n", i)], ns)
q = ns["lt_planer_quelle"]
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


for notes, soll in (("Auto-Planer · Etappe · Rest 9.039 $ bis Ziel · Balance 149.961 (TV)", "challenge"),
                    ("Auto-Planer · Topstep-Kette 2/2 · Trade 1 -1.500 $", "challenge"),
                    ("Auto-Planer · Klein-Trade\nOrbit V3 (finaler Tradeify, Gegenhedge): 3,20 Lot Fusion", "challenge"),
                    ("Funded-CFD-Planer · Gewinn 1.000 $ → Ziel 51.000 $", "fcfd"), ("Funded-CFD-Planer · Vorschlag · Gewinn", "fcfd"),
                    ("Funded-Planer · Zyklus 1 · Ziel 165.000 $", "ffut"), ("Winning-Day-Farmer", "wd"),
                    (None, None), ("", None), ("Hand-Trade: Auto-Planer war aus", None)):
    check(q(notes) == soll, f"{notes!r} → {soll}")
check('f"Funded-Planer{' in src and 'f"Funded-CFD-Planer{' in src and 'return f"Auto-Planer · {stufe}' in src and 'body.setdefault("notes", "Winning-Day-Farmer")' in src,
      "die Planer schreiben ihre Notiz noch so")
check(re.search(r'z\["planer_quelle"\] = lt_planer_quelle\(q\.get\("notes"\)\)', src) is not None, "/admin/live-trades liefert planer_quelle")
print(f"\n{'selftest_lt_planer_quelle: alle Prüfungen grün' if not FEHLER else f'✗ {len(FEHLER)} Fehler'}")
sys.exit(1 if FEHLER else 0)
