#!/usr/bin/env python3
"""Selbsttest Radar Bestanden je Gruppe (Finn 02.11.2026: Julian aus Emins Gruppe stand im HT-Radar). Rechnet _wd_personen aus app.py mit nachgebauten Logins, ohne Netz.

Aufruf:  python3 tools/selftest_radar_bestanden_sicht.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
app = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


src = re.search(r"^def _wd_personen\(.*?(?=^\S)", app, re.S | re.M).group(0)
HT, FP, EMIN, JULIAN = "ht1", "finnpascal", "emin", "julian"
GRUPPE_EMIN = {EMIN, JULIAN}
zustand = {}


class Antwort:
    def json(self):
        return {"users": [{"id": u, "email": u + "@x", "user_metadata": {"name": u}} for u in (HT, FP, EMIN, JULIAN)]}


ns = {"_auth_liste_anfrage": Antwort, "ADMIN_EXCLUDE_EMAILS": {"emin@x"}, "_admin_nur_uid": lambda: zustand.get("nur"),
      "_admin_sicht": lambda: zustand.get("ein") or zustand.get("chip"), "_admin_eingeschraenkt": lambda: zustand.get("ein"),
      "_admin_filter_ist_ht": lambda: zustand.get("chip_ht", False), "_admin_standard_aus": lambda: set() if (zustand.get("ein") or zustand.get("chip")) else set(GRUPPE_EMIN),
      "admin_gruppen_daten": lambda: "daten", "_admin_verwalter_gruppen_ids": lambda d: set(GRUPPE_EMIN)}
exec(src, ns)
P = ns["_wd_personen"]

zustand.clear()
check(JULIAN in P(radar=True)[1] and JULIAN in P()[1], "HT ohne Chip: Julian (Emins Gruppe) ausgeblendet")
zustand.update(chip=frozenset(GRUPPE_EMIN))
check(JULIAN not in P()[1] and HT in P()[1], "Admin-Popup mit Chip „Emin“: wie bisher nur Emins Gruppe")
check(JULIAN in P(radar=True)[1] and HT not in P(radar=True)[1], "Radar mit gemerktem Chip „Emin“: trotzdem HT, Julian raus")
zustand.clear(); zustand.update(nur=EMIN, ein=frozenset(GRUPPE_EMIN))
check(JULIAN not in P(radar=True)[1] and HT in P(radar=True)[1], "Login aus Emins Gruppe: Radar zeigt Emins Gruppe, HT raus")
check('schluessel += "|g=" + str(request.args.get("gruppe")' in app and "_n_r, aus_radar = _wd_personen(radar=True)" in app and "archiv, namen, aus_radar," in app, "Handarbeit: Cache je Chip, radar_bestanden mit der Radar-Sicht")

print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
