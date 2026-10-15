#!/usr/bin/env python3
"""Selbsttest RICHTUNG PER KLICK IM ADMIN-PLANER (app.py ap_richtung_plan_pruefen, Finn 14.10.2026): ein geplanter, ungeclaimter
Auto-Plan dreht nur, wenn prophos_gegenrichtung_frei „frei" sagt; gesperrt/nicht lesbar = nicht drehen (fail-closed), geclaimt,
Hand-Plan, bestätigt + fällig ebenfalls nicht. Aufruf:  python3 tools/selftest_richtung_klick.py"""
import os
import sys
from datetime import datetime, timedelta, timezone

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    i = src.index("\ndef ap_richtung_plan_pruefen(") + 1
    ns = {"datetime": datetime, "timedelta": timedelta, "AP_FAELLIG_MIN": 5}
    exec(src[i:src.find("\n\n\n", i)], ns)
    j = src.index("\ndef ap_richtung_hand_fest(") + 1
    exec(src[j:src.find("\n\n\n", j)], ns)
    # Hand-Merker muss im Stand als fest zählen und für Finns eigene Eingriffe wieder frei sein (Master 16.10.2026)
    assert "elif ap_richtung_hand_fest(p):\n            fest = AP_FEST_RICHTUNG_HAND" in src, "Stand wertet richtung_hand nicht als fest"
    assert "AP_FEST_TSV2, AP_FEST_RICHTUNG_HAND) else x" in src, "ap_eingriff_pruefen gibt AP_FEST_RICHTUNG_HAND nicht frei"
    assert "rh:mt5_baseline->richtung_hand" in src, "Stand liest richtung_hand nicht"
    return ns["ap_richtung_plan_pruefen"], ns["ap_richtung_hand_fest"]


def main():
    f, hand = lade()
    jetzt = datetime(2026, 10, 16, 6, 0, tzinfo=timezone.utc)
    iso = lambda m: (jetzt + timedelta(minutes=m)).isoformat()
    basis = {"status": "planned", "auto_plan": True, "richtung": "sell", "start_um": iso(30)}
    frei = {"frei": True}
    fehler = 0

    def soll(name, plan, fr, neu, teil=None):
        nonlocal fehler
        n, msg = f(plan, fr, jetzt)
        ok = n == neu and (teil is None or (msg and teil in msg))
        print(("ok   " if ok else "FEHL ") + name + ("" if ok else f" → {n!r} {msg!r}"))
        fehler += 0 if ok else 1

    soll("frei → gedreht", dict(basis), frei, "buy")
    soll("buy → sell", dict(basis, richtung="buy"), frei, "sell")
    soll("gesperrt → Grund", dict(basis), {"frei": False, "grund": "„X“ läuft dort LONG"}, None, "Gesperrt: „X“ läuft dort LONG")
    soll("Riegel nicht lesbar → nichts", dict(basis), None, None, "nicht lesbar")
    soll("geclaimt → nichts", dict(basis, start_um_gestartet_at=iso(-1)), frei, None, "geclaimt")
    soll("gesendet → nichts", dict(basis, orbit_gesendet_at=iso(-1)), frei, None, "geclaimt")
    soll("open → nichts", dict(basis, status="open"), frei, None, "nicht mehr geplant")
    soll("Hand-Plan → nichts", dict(basis, auto_plan=False), frei, None, "kein Auto-Plan")
    soll("bestätigt + fällig → nichts", dict(basis, auto_bestaetigt_at=iso(-60), start_um=iso(3)), frei, None, "zurück")
    soll("bestätigt, später → gedreht", dict(basis, auto_bestaetigt_at=iso(-60), start_um=iso(20)), frei, "buy")
    soll("unbestätigt + fällig → gedreht", dict(basis, start_um=iso(3)), frei, "buy")
    soll("ohne Richtung → nichts", dict(basis, richtung=None), frei, None, "keine Richtung")
    soll("Plan fehlt → nichts", None, frei, None, "nicht gefunden")
    for name, p, soll_fest in (("Merker = Richtung → fest", {"richtung": "buy", "rh": {"nach": "buy"}}, True),
                               ("Riegel hat danach gedreht → frei", {"richtung": "sell", "rh": {"nach": "buy"}}, False),
                               ("ohne Merker → frei", {"richtung": "buy", "rh": None}, False),
                               ("Merker kaputt → frei", {"richtung": "buy", "rh": "buy"}, False)):
        ok = hand(p) is soll_fest
        print(("ok   " if ok else "FEHL ") + name)
        fehler += 0 if ok else 1
    print("ALLE OK" if not fehler else f"{fehler} FEHLER")
    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    main()
