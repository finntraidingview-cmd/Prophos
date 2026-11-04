#!/usr/bin/env python3
"""Selbsttest GEDULDIGE FENSTERSUCHE (F1, Befund Lotse L4 03.11.2026, Marco FundedNext …3615: Terminal seit 1:45 min eingeloggt, die Suche lief
genau einmal und gab auf). mt5-copier/order_bot.py _finde_terminal_geduldig — bis TERMINAL_SUCHE_S lang alle 2–3 s neu suchen. Ohne Windows:
Suche, Warten und Uhr sind gestellt. Aufruf: python3 tools/selftest_fenstersuche_geduldig.py"""
import os
import re
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(os.path.dirname(HIER), "mt5-copier", "order_bot.py")
FEHLER = []


def lade():
    src = open(BOT, encoding="utf-8").read()
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in ("TERMINAL_SUCHE_S", "TERMINAL_SUCHE_BIS", "TERMINAL_SUCHE_TAKT")]
    i = src.index("\ndef _finde_terminal_geduldig(") + 1
    teile.append(src[i:src.find("\n\n\n", i)])
    ns = {"time": time, "_finde_terminal": None, "_warte": None}
    exec("\n".join(teile), ns)
    return ns, src


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


class Uhr:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def main():
    ns, src = lade()
    g = ns["_finde_terminal_geduldig"]
    check(ns["TERMINAL_SUCHE_S"] == 30 and ns["TERMINAL_SUCHE_TAKT"] == (2.0, 1.0) and ns["TERMINAL_SUCHE_BIS"] == 200, "30 s, Takt 2–3,5 s (gestreut), nur bis Lauf-Sekunde 200")

    # Fenster sofort da → eine Suche, kein Warten
    uhr, pausen = Uhr(), []
    w, n = g(14353615, finder=lambda login: "FENSTER", warte=lambda a, b: pausen.append((a, b)), uhr=uhr)
    check(w == "FENSTER" and n == 1 and pausen == [], "Fenster sofort da → 1 Suche, kein Warten")

    # Fenster erscheint bei der 4. Suche (Fall L4) → gefunden
    uhr, aufrufe = Uhr(), []

    def finder(login):
        aufrufe.append(login)
        return "FENSTER" if len(aufrufe) >= 4 else None

    def warte(a, b):
        uhr.t += a + b / 2
    w, n = g(14353615, finder=finder, warte=warte, uhr=uhr)
    check(w == "FENSTER" and n == 4, f"Fenster nach 3 Fehlversuchen gefunden ({n} Suchen)")

    # Fenster kommt nie → nach ~30 s aufgeben, ~12–15 Suchen, letzte Suche nach Ablauf der Frist
    uhr, n_warte = Uhr(), []

    def warte2(a, b):
        n_warte.append(1)
        uhr.t += a + b / 2
    w, n = g(14353615, finder=lambda login: None, warte=warte2, uhr=uhr)
    check(w is None and 11 <= n <= 16 and uhr.t >= 30, f"nie gefunden → aufgeben nach ~30 s ({n} Suchen, {uhr.t:.1f} s)")

    # Lauf schon spät (Sekunde ≥ 200): Frist 0 → genau eine Suche wie früher, kein Warten
    uhr, pausen = Uhr(), []
    w, n = g(1, dauer_s=0, finder=lambda login: None, warte=lambda a, b: pausen.append(1), uhr=uhr)
    check(w is None and n == 1 and pausen == [], "Frist 0 → eine Suche, kein Warten")
    # Einbau: der Order-Start nutzt die geduldige Suche, die Meldung bleibt „Kein MT5-Fenster mit Konto" (Beleg „nicht platziert" im Tab)
    i = src.index("# 2b) Ins (vom Check bereits geoeffnete) Terminal gehen -> Guard")
    teil = src[i:i + 1500]
    check("_finde_terminal_geduldig(expected, dauer_s=min(TERMINAL_SUCHE_S, max(0, TERMINAL_SUCHE_BIS - trail.sekunden())))" in teil and 'f"Kein MT5-Fenster mit Konto {expected} gefunden' in teil and '"retry_ok": True' in teil,
          "run(): geduldige Suche, Meldung + retry_ok unverändert")
    if FEHLER:
        print(f"\n{len(FEHLER)} Fehler")
        sys.exit(1)
    print("\nalle grün")


if __name__ == "__main__":
    main()
