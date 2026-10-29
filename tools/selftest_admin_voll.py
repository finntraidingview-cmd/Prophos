#!/usr/bin/env python3
"""Selbsttest ADMIN-VOLL (30.10.2026, Finn als „Finn + Pascal" — nicht in ADMIN_EMAILS; Master-Stopp für 95197c02: nicht über
auto_plan_regeln.user_ids, dort stehen alle Kunden-IDs): admin_voll_frei (rein rechnend) + _admin_voll mit gestellter Anmeldung (Kunde aus
user_ids → 403, Liste admin_voll → frei, eingeschränkt → 403, Lesefehler → 502) + Verdrahtung am Quelltext (Payout, ✓-Freigabe, Route,
SQL ohne E-Mail). Rechnungen bleiben bei ADMIN_EMAILS.
Aufruf:  python3 tools/selftest_admin_voll.py"""
import os
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = open(os.path.join(W, "app.py"), encoding="utf-8").read()
SQL = open(os.path.join(W, "sql", "2026-10-30_admin_voll.sql"), encoding="utf-8").read()
fehler = 0


def soll(name, ok):
    global fehler
    print(("ok   " if ok else "FEHL ") + name)
    fehler += 0 if ok else 1


def block(name):
    i = APP.index(f"\ndef {name}(") + 1
    return APP[i:APP.find("\n\n\n", i)]


FINN, KUNDE = "48f272b4-0000-4000-a000-00000000f1nn", "00000000-0000-4000-a000-00000000c0de"

# Teil A: Bedingung
ns = {}
exec(block("admin_voll_frei"), ns)
f = ns["admin_voll_frei"]
soll("Login in admin_voll, im Admin nicht eingeschränkt → voll", f(FINN, frozenset({FINN}), None) is True)
soll("Kunde aus user_ids, nicht in admin_voll → nicht voll", f(KUNDE, frozenset({FINN}), None) is False)
soll("in admin_voll, aber eingeschränkt (Verwalter/Gruppe/nur eigene) → nicht voll",
     f(FINN, frozenset({FINN}), FINN) is False and f(FINN, frozenset({FINN}), frozenset({FINN})) is False)
soll("leere Liste (Tabelle fehlt) / kein Login → nie frei", f(FINN, frozenset(), None) is False and f("", frozenset({""}), None) is False)

# Teil B: _admin_voll mit gestellter Anmeldung (ADMIN_EMAILS sagt 403, Login gesetzt)
class Req:
    environ = {}


def lauf(uid, voll, sicht_l=None, wirft=False):
    Req.environ = {"prophos.admin_uid": uid}

    def _admin_auth():
        return None, ("Nur für Admins", 403)

    def admin_voll_uids():
        if wirft:
            raise RuntimeError("DB weg")
        return frozenset(voll)
    g = {"request": Req, "_admin_auth": _admin_auth, "admin_voll_uids": admin_voll_uids, "admin_sicht_lesen": lambda u: (sicht_l, False),
         "jsonify": lambda d: d, "admin_voll_frei": f}
    exec(block("_admin_voll"), g)
    return g["_admin_voll"]()


u, e = lauf(KUNDE, {FINN})
soll("Kunde aus user_ids → 403", u is None and e[1] == 403)
u, e = lauf(FINN, {FINN})
soll("Finn + Pascal (admin_voll) → frei", u == FINN and e is None)
u, e = lauf(FINN, {FINN}, sicht_l=FINN)
soll("admin_voll, aber im Admin eingeschränkt → 403", u is None and e[1] == 403)
u, e = lauf(FINN, {FINN}, wirft=True)
soll("Liste nicht lesbar → 502, nie still frei", u is None and e[1] == 502)

# Teil C: Verdrahtung
uids = block("admin_voll_uids")
soll("admin_voll_uids: 60 s gemerkt, Tabelle fehlt → leer, sonst werfen",
     "AUTH_LISTE_CACHE_S" in uids and "admin_gruppen_tabelle_fehlt(e)" in uids and "raise" in uids)
soll("kein Zugriff über auto_plan_regeln.user_ids mehr", "user_ids" not in block("_admin_voll") and "user_ids" not in block("admin_voll_frei").split('"""')[2])
pe = block("admin_payout_erhalten")
soll("Payout erhalten über _admin_voll, Verwalter-Weg bleibt", "_, err = _admin_voll()" in pe and "_admin_verwalter()" in pe)
hf = block("admin_auto_plan_hedge_freigabe")
soll("Hedge-Freigabe-Route über _admin_voll", "uid, err = _admin_voll()" in hf)
ei = block("_ap_eingriff")
soll("✓ gibt den Hedge nur bei vollem Admin UND sicht None frei",
     'admin_voll_frei(uid, admin_voll_uids(), sicht_l)' in ei and 'if aktion == "bestaetigen" and voll and sicht is None else 0' in ei)
soll("✓: Lesefehler der Liste → keine Freigabe, Bestätigung bleibt", "voll = False" in ei)
soll("Rechnungen bleiben bei _admin_auth (ADMIN_EMAILS)", "Rechnungen gesperrt" in block("_admin_auth"))
soll("SQL: Tabelle mit RLS ohne Policy, Befüllung aus admin_mail_leser, keine E-Mail",
     "create table if not exists public.admin_voll" in SQL and "enable row level security" in SQL and "create policy" not in SQL
     and "select user_id from public.admin_mail_leser on conflict do nothing" in SQL and "@" not in SQL)
print("ALLE OK" if not fehler else f"{fehler} FEHLER")
sys.exit(1 if fehler else 0)
