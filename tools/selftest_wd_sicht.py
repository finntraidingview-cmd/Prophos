#!/usr/bin/env python3
"""Selbsttest WD-SICHT (app.py, 30.10.2026, Slave 7): wd_sicht_fuer — Verwalter und Mitglieder einer Verwalter-Gruppe sehen genau ihre
Gruppe, alle anderen (Hermann Technologies) alles außer den Verwalter-Gruppen; Route /wd-sicht nur eingeloggt, Gruppen nicht lesbar → 502.
Aufruf: python3 tools/selftest_wd_sicht.py"""
import os
import re
import sys

from flask import Flask, jsonify, request

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HIER, "..", "app.py")
FEHLER = []
EMIN, AHMAD, MIKE, FINN = "e" * 8, "a" * 8, "m" * 8, "f" * 8
DATEN = {"gruppen": [{"id": "g-ht", "name": "Hermann Technologies", "verwalter_id": None}, {"id": "g-emin", "name": "Emin", "verwalter_id": EMIN}],
         "mitglieder": [{"user_id": MIKE, "gruppe_id": "g-ht"}, {"user_id": FINN, "gruppe_id": "g-ht"}, {"user_id": AHMAD, "gruppe_id": "g-emin"}]}


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade(login, daten):
    src = open(APP, encoding="utf-8").read()
    i = src.index("\ndef _admin_verwalter_gruppen_ids(") + 1
    vg = src[i:src.find("\n\n\n", i)]
    a = src.index("# ══ WD-SICHT FÜR JEDEN LOGIN")
    b = src.index('@app.route("/admin/wd-plaene"', a)
    app = Flask("t")

    def gruppen():
        if isinstance(daten, Exception):
            raise daten
        return daten
    ns = {"app": app, "jsonify": jsonify, "request": request, "re": re, "admin_gruppen_daten": gruppen,
          "_login_uid_mail": (lambda: (None, None, (jsonify({"error": "Nicht angemeldet"}), 401))) if login is None else (lambda: login)}
    exec(vg + "\n" + src[a:b], ns)
    return app, ns


def main():
    _app, ns = lade((MIKE, "m@x", None), DATEN)
    F = ns["wd_sicht_fuer"]
    check(F(EMIN, DATEN) == {"art": "gruppe", "ids": sorted([EMIN, AHMAD])}, "Verwalter Emin → seine Gruppe inkl. sich selbst")
    check(F(AHMAD, DATEN) == {"art": "gruppe", "ids": sorted([EMIN, AHMAD])}, "Mitglied Ahmad → dieselbe Gruppe")
    check(F(MIKE, DATEN) == {"art": "ht", "ausser": sorted([EMIN, AHMAD])}, "HT-Mitglied Mike → alles außer der Emin-Gruppe")
    check(F("neu12345", DATEN)["art"] == "ht", "ID ohne Gruppen-Zeile = HT")
    check(F(MIKE, {"gruppen": [], "mitglieder": []}) == {"art": "ht", "ausser": []}, "keine Gruppen → HT ohne Ausnahmen")
    app, _ = lade((EMIN, "e@x", None), DATEN)
    d = app.test_client().get("/wd-sicht").get_json()
    check(d["ok"] and d["art"] == "gruppe" and EMIN in d["ids"] and MIKE not in d["ids"], "Route als Emin: nur seine Gruppe")
    app, _ = lade(None, DATEN)
    check(app.test_client().get("/wd-sicht").status_code == 401, "nicht eingeloggt → 401")
    app, _ = lade((MIKE, "m@x", None), RuntimeError("DB weg"))
    check(app.test_client().get("/wd-sicht").status_code == 502, "Gruppen nicht lesbar → 502 (Browser zeigt dann nur die eigene ID)")
    print(f"\n{'ALLES OK' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
