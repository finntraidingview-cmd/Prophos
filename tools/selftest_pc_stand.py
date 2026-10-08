#!/usr/bin/env python3
"""Selbsttest PC-Tab-Lebenszeichen je ID (app.py pc_stand_zusammenfassen, 08.10.2026) — ohne Netz. Aufruf: python3 tools/selftest_pc_stand.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"datetime": datetime, "timezone": timezone}
    i = src.index("def pc_stand_zusammenfassen(")
    exec(re.search(r"^PC_STAND_LEBT_S = .*$", src, re.M).group(0) + "\n" + src[i:src.find("\n\n\n", i)], ns)
    return ns


def main():
    a = lade()
    jetzt = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    u1, u2 = "00000000-0000-0000-0000-0000000000a1", "00000000-0000-0000-0000-0000000000a2"
    rows = [
        {"id": "pc-aaaaaa:c1", "pc_name": "pc-aaaaaa", "updated_at": (jetzt - timedelta(seconds=40)).isoformat(), "user_id": u1, "tab_build": "2026-09-22.1177", "bot_version": "2026-09-22.1170", "copier_version": "2026-09-22.1170"},
        {"id": "pc-aaaaaa:c2", "pc_name": "pc-aaaaaa", "updated_at": (jetzt - timedelta(seconds=400)).isoformat(), "user_id": u1, "tab_build": "2026-09-22.1100", "bot_version": None, "copier_version": None},
        {"id": "pc-bbbbbb:c1", "pc_name": "pc-bbbbbb", "updated_at": (jetzt - timedelta(hours=20)).isoformat().replace("+00:00", "Z"), "user_id": u2, "tab_build": "2026-09-22.1159", "bot_version": "2026-09-22.1144", "copier_version": "2026-09-22.1144"},
        {"id": "pc-cccccc:c1", "pc_name": "pc-cccccc", "updated_at": jetzt.isoformat(), "user_id": "", "tab_build": "x"},
        {"id": "kaputt", "pc_name": "pc-dddddd", "updated_at": "nix", "user_id": u2},
    ]
    st = a["pc_stand_zusammenfassen"](rows, jetzt)
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)
    check(set(st) == {u1, u2}, "nur Zeilen mit user_id, kaputte Zeit übersprungen")
    check(st[u1]["alt_s"] == 40 and st[u1]["lebt"] is True and st[u1]["tab_build"] == "2026-09-22.1177" and st[u1]["pcs"] == ["pc-aaaaaa"],
          "jüngster Herzschlag je ID zählt (40 s, lebt, Build der jüngsten Zeile)")
    check(st[u2]["alt_s"] == 20 * 3600 and st[u2]["lebt"] is False and st[u2]["pc_name"] == "pc-bbbbbb", "20 h alt → lebt nicht (Mikes Fall)")
    check(a["pc_stand_zusammenfassen"]([], jetzt) == {} and a["pc_stand_zusammenfassen"](None, jetzt) == {}, "leer/None → {}")
    # MT5-Update je PC (08.10.2026): jüngste Zeile ohne Feld (alter Tab), ältere Instanz mit → Stand der älteren bleibt sichtbar
    mu = {"aufgabe_ok": False, "ausstehend": 1}
    r2 = [dict(rows[0]), dict(rows[1], mt5_update=mu), dict(rows[2], mt5_update={"aufgabe_ok": True})]
    s2 = a["pc_stand_zusammenfassen"](r2, jetzt)
    check(s2[u1]["je_pc"]["pc-aaaaaa"]["mt5_update"] == mu and s2[u1]["je_pc"]["pc-aaaaaa"]["tab_build"] == "2026-09-22.1177",
          "mt5_update aus der jüngsten Zeile, die es hat — Build bleibt der jüngste")
    check(s2[u2]["je_pc"]["pc-bbbbbb"]["mt5_update"] == {"aufgabe_ok": True} and st[u1]["je_pc"]["pc-aaaaaa"]["mt5_update"] is None,
          "eigene Zeile mit Feld → übernommen; ohne Feld nirgends → None")
    print("\nPC-STAND:", "alles grün" if ok else "FEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
