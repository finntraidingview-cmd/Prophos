#!/usr/bin/env python3
"""Selbsttest HEUTE TRADEN (app.py heute_traden_info, Finn 16.10.2026: Funded Futures, die heute noch nicht getradet sind) — rein rechnend.

Aufruf:  python3 tools/selftest_heute_traden.py
Lädt die Funktion per Quelltext aus app.py (Muster selftest_auto_ext: app.py zieht beim Import Flask und Threads)."""
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]
    ns = {"datetime": datetime, "timezone": timezone, "re": __import__("re")}
    for f in ("_ap_ts", "heute_traden_info", "heute_pl_info"):
        exec(block(f), ns)
    return ns


def main():
    ns = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    f, tz, heute = ns["heute_traden_info"], ZoneInfo("Europe/Berlin"), "2026-10-16"
    check(f([], heute, tz) == {"getradet": False, "geplant_um": None}, "ohne Pläne: nicht getradet, nichts geplant")
    check(f([{"status": "open", "started_at": "2026-10-14T10:00:00Z"}], heute, tz)["getradet"], "läuft gerade (open) = getradet, egal seit wann")
    check(f([{"status": "completed", "started_at": "2026-10-16T08:00:00Z", "completed_at": "2026-10-16T09:00:00Z"}], heute, tz)["getradet"],
          "heute beendet + abgehakt = getradet")
    check(f([{"status": "review", "started_at": "2026-10-16T08:00:00Z", "ended_at": "2026-10-16T09:00:00Z"}], heute, tz)["getradet"],
          "heute beendet, noch in Überprüfen = getradet")
    check(not f([{"status": "review", "started_at": "2026-10-15T08:00:00Z", "ended_at": "2026-10-15T09:00:00Z"}], heute, tz)["getradet"],
          "gestern beendet (Überprüfen offen) zählt nicht für heute")
    # Tagesgrenze Berlin: 2026-10-15 22:30 UTC = 16.10. 00:30 Berlin
    check(f([{"status": "completed", "started_at": "2026-10-15T22:30:00Z"}], heute, tz)["getradet"],
          "Tagesgrenze in Berliner Zeit (00:30 Berlin zählt zum 16.)")
    g = f([{"status": "planned", "start_um": "2026-10-16T14:00:00Z"}, {"status": "planned", "start_um": "2026-10-16T09:30:00Z"}], heute, tz)
    check(g == {"getradet": False, "geplant_um": "2026-10-16T09:30:00Z"}, "heute geplant: früheste Startzeit, noch nicht getradet")
    check(f([{"status": "planned", "start_um": "2026-10-17T09:30:00Z"}], heute, tz)["geplant_um"] is None, "morgen geplant zählt nicht")
    g2 = f([{"status": "completed", "started_at": "2026-10-16T08:00:00Z"}, {"status": "planned", "start_um": "2026-10-16T15:00:00Z"}], heute, tz)
    check(g2 == {"getradet": True, "geplant_um": None}, "getradet schlägt geplant")

    # HEUTE IM POLAR-DROPDOWN (21.10.2026): heute_pl_info — P&L je Seite, läuft, Anzahl
    h = ns["heute_pl_info"]
    check(h([], heute, tz) == {"getradet": False, "laeuft": False, "pl": None, "n": 0}, "heute_pl: ohne Pläne nichts")
    m1 = {"status": "completed", "started_at": "2026-10-16T08:00:00Z", "completed_at": "2026-10-16T09:00:00Z", "master_pl": 159, "slave_pl": -40}
    m2 = {"status": "review", "started_at": "2026-10-16T10:00:00Z", "ended_at": "2026-10-16T10:30:00Z", "master_pl": "-42.5"}
    check(h([(m1, "master"), (m2, "master")], heute, tz) == {"getradet": True, "laeuft": False, "pl": 116.5, "n": 2}, "heute_pl: Master-Summe aus master_pl (auch als Text)")
    check(h([(m1, "slave")], heute, tz)["pl"] == -40, "heute_pl: als Slave zählt slave_pl")
    check(h([({"status": "review", "started_at": "2026-10-16T08:00:00Z"}, "master")], heute, tz) == {"getradet": True, "laeuft": False, "pl": None, "n": 1},
          "heute_pl: getradet ohne Betrag → pl None")
    check(h([({"status": "open", "started_at": "2026-10-14T10:00:00Z"}, "slave"), (m1, "master")], heute, tz) == {"getradet": True, "laeuft": True, "pl": 159.0, "n": 1},
          "heute_pl: läuft + heute beendet")
    check(h([({"status": "completed", "started_at": "2026-10-15T08:00:00Z", "completed_at": "2026-10-15T09:00:00Z", "master_pl": 300}, "master")], heute, tz)["getradet"] is False,
          "heute_pl: gestern zählt nicht")

    print("OK" if ok else "FEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
