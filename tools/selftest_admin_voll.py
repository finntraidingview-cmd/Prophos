#!/usr/bin/env python3
"""Selbsttest ADMIN-VOLL (30.10.2026, Finn als „Finn + Pascal" — nicht in ADMIN_EMAILS): admin_voll_frei (rein rechnend, aus app.py exec'd
mit ap_eingriff_sicht) + Verdrahtung am Quelltext: Payout erhalten und Hedge-Freigabe über _admin_voll, Hedge-Freigabe beim ✓ für jeden
Login mit allen IDs (sicht None). ADMIN_EMAILS-Weg, Verwalter-Weg der Payout-Route und Rechnungen unverändert.
Aufruf:  python3 tools/selftest_admin_voll.py"""
import os
import re
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = open(os.path.join(W, "app.py"), encoding="utf-8").read()
fehler = 0


def soll(name, ok):
    global fehler
    print(("ok   " if ok else "FEHL ") + name)
    fehler += 0 if ok else 1


def block(name):
    i = APP.index(f"\ndef {name}(") + 1
    return APP[i:APP.find("\n\n\n", i)]


ns = {}
exec("\n".join([re.search(r"^AP_SICHT_ADMIN = .*$", APP, re.M).group(0), block("ap_eingriff_sicht"), block("admin_voll_frei")]), ns)
f = ns["admin_voll_frei"]

# Teil A: Bedingung
soll("im Planer, nicht nur eigene, kein Verwalter → voll (Finn + Pascal)", f(True, False, False) is True)
soll("nicht im Planer → nicht voll", f(False, False, False) is False)
soll("admin_zugang „nur eigene“ (Emin) → nicht voll", f(True, True, False) is False)
soll("Verwalter → nicht voll (bleibt bei seiner Gruppe)", f(True, False, True) is False and f(True, True, True) is False)
soll("gleich dem Bestätigen-Recht im Admin-Reiter (ap_eingriff_sicht … 'admin' → None)",
     all(f(p, n, False) == (ns["ap_eingriff_sicht"](False, "u", p, n, "admin", None) is None) for p in (True, False) for n in (True, False)))

# Teil B: Verdrahtung
av = block("_admin_voll")
soll("_admin_voll: ADMIN_EMAILS zuerst, sonst Login + admin_sicht_lesen + user_ids → admin_voll_frei",
     "_admin_auth()" in av and "_wd_login()" in av and "admin_sicht_lesen(" in av and "user_ids" in av and "admin_voll_frei(" in av)
soll("_admin_voll: Lesefehler → 502, sonst der 403 von _admin_auth", '"Anmeldung nicht prüfbar"' in av and "return None, err" in av)
pe = block("admin_payout_erhalten")
soll("Payout erhalten über _admin_voll, Verwalter-Weg bleibt", "_, err = _admin_voll()" in pe and "_admin_verwalter()" in pe)
hf = block("admin_auto_plan_hedge_freigabe")
soll("Hedge-Freigabe-Route über _admin_voll, kein reines admin-Gate mehr", "uid, err = _admin_voll()" in hf and "if not admin:" not in hf)
ei = block("_ap_eingriff")
soll("✓ gibt den Hedge frei bei sicht None (nicht mehr nur ADMIN_EMAILS)",
     'if aktion == "bestaetigen" and sicht is None else 0' in ei and "and admin and sicht is None" not in ei)
soll("Rechnungen bleiben bei _admin_auth (ADMIN_EMAILS)", "Rechnungen gesperrt" in block("_admin_auth"))
print("ALLE OK" if not fehler else f"{fehler} FEHLER")
sys.exit(1 if fehler else 0)
