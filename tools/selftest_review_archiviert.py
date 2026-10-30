#!/usr/bin/env python3
"""Selbsttest REVIEW TROTZ NACHFOLGER (prophos.html wdlKontoArchiviert, 30.10.2026 — Finn: Simon Topstep …9002 stand nach dem Nachfolger weiter in Review, „bestanden 18:08").
Aufruf:  python3 tools/selftest_review_archiviert.py   (ohne Netz; Quelltext-Prüfung, der Ablauf läuft im Stub)."""
import os
import sys

html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


f = html[html.index("function wdlKontoArchiviert("):html.index("function wdlBestandenChip(")]
check("(t.konto || {}).archiviert" in f and "getArchive()" in f, "Archiv: fremde IDs vom Server, eigene ID lokal")
b = html[html.index("function wdlBestandenChip("):]
check("if(wdlKontoArchiviert(t)) return ''" in b[:400], "kein Bestanden-Chip auf archiviertem Konto: keine lokale Review-Zeile, kein „Trade abhaken“")
la = html[html.index("function bstLokalAnwenden("):html.index("function abhakZielNachziehen(")]
check("wdlKontoArchiviert(t)" in la and "_bstLokal.delete(kid)" in la, "vorhandene lokale Zeile fällt nach dem Archivieren weg")
check("m.schritt === 'geparkt') && !wdlKontoArchiviert(t)" in html, "geparkter Trade eines archivierten Kontos steht nicht unter Review")
print(f"\n{'selftest_review_archiviert: alle Prüfungen grün' if not FEHLER else f'✗ {len(FEHLER)} Fehler'}")
sys.exit(1 if FEHLER else 0)
