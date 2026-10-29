#!/usr/bin/env python3
"""Selbsttest SCHRITT D BEI BLINDEM READER (app.py tm_blind_frei_rechnen, 29.10.2026).

Anlass: Lader-Rollout stand — auf 10 von 12 HT-PCs ist der Puls-Chrome-Reader blind (positionen_ok false), Schritt D (Tampermonkey
„Aktualisieren") und das TV-Neuladen warteten dort für immer. Ersatz-Freigabe aus der DB über GET /alarm/userscript-frei.
Aufruf:  python3 tools/selftest_tm_blind.py
Geprüft: leer → frei; Signal läuft; Plan open; review mit lebendem Hedge (offen/oeffnet/schliesst) bzw. zu; Start < 45 / > 45 min;
überfällig bis 65 min; geclaimt ohne Start; Fremd-Position offen/weg; MT5-Position frisch/alt/Zeit unlesbar; PostgREST-Zeitformen."""
import os
import re
import sys
import time
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def laden():
    src = open(os.path.join(HIER, "..", "app.py"), encoding="utf-8").read()
    a = src.index("TM_BLIND_START_S = ")
    b = src.index('@app.route("/alarm/userscript-frei"')
    ns = {"datetime": datetime, "timezone": timezone, "re": re}
    exec(src[a:b], ns)
    return ns["tm_blind_frei_rechnen"]


def main():
    f = laden()
    jetzt = time.time()
    iso = lambda d: datetime.fromtimestamp(jetzt + d, timezone.utc).isoformat()   # noqa: E731
    pg = lambda d: datetime.fromtimestamp(jetzt + d, timezone.utc).strftime("%Y-%m-%d %H:%M:%S.12345+00")   # noqa: E731
    check(f([], [], [], jetzt) == "", "nichts → frei")
    check(f([], [], [], jetzt, [{"id": 1}]).startswith("Puls/Signal läuft"), "Signal läuft auf dem PC → gesperrt")
    check(f([{"status": "open"}], [], [], jetzt) == "offener Plan", "Plan open → gesperrt")
    for hs in ("offen", "oeffnet", "schliesst"):
        check(f([{"status": "review", "hedge_status": hs}], [], [], jetzt) != "", f"review mit Hedge {hs} → gesperrt")
    check(f([{"status": "review", "hedge_status": "geschlossen"}], [], [], jetzt) == "", "review mit geschlossenem Hedge → frei")
    check(f([{"status": "planned", "start_um": iso(1800)}], [], [], jetzt) == "Start in < 45 min", "Start in 30 min → gesperrt")
    check(f([{"status": "planned", "start_um": iso(3000)}], [], [], jetzt) == "", "Start in 50 min → frei")
    check(f([{"status": "planned", "start_um": iso(-3600)}], [], [], jetzt) != "", "60 min überfällig → noch im Startfenster, gesperrt")
    check(f([{"status": "planned", "start_um": iso(-4200)}], [], [], jetzt) == "", "70 min überfällig → frei")
    check(f([{"status": "planned", "start_um": iso(-9000), "start_um_gestartet_at": iso(-9000)}], [], [], jetzt) != "",
          "geclaimt ohne started_at → gesperrt")
    check(f([{"status": "planned", "start_um": pg(600)}], [], [], jetzt) != "", "PostgREST-Zeit (+00, 5 Stellen) wird gelesen")
    check(f([], [{"weg_at": None}], [], jetzt).startswith("Fremd-Position"), "Fremd-Position offen → gesperrt")
    check(f([], [{"weg_at": iso(-60)}], [], jetzt) == "", "Fremd-Position weg → frei")
    check(f([], [], [{"updated_at": iso(-30), "n_pos": 1}], jetzt).startswith("MT5-Position"), "MT5-Position frisch → gesperrt")
    check(f([], [], [{"updated_at": iso(-600), "n_pos": 1}], jetzt) == "", "MT5-Position 10 min alt → frei")
    check(f([], [], [{"updated_at": "müll", "n_pos": 1}], jetzt).startswith("MT5-Position"), "MT5-Zeit unlesbar mit Position → gesperrt")
    check(f([], [], [{"updated_at": "müll", "n_pos": 0}], jetzt) == "", "MT5-Zeit unlesbar ohne Position → frei")
    print(f"\n{'ALLE OK' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
