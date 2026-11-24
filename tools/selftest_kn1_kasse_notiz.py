#!/usr/bin/env python3
"""Selbsttest KN1 PAYOUT-NOTIZ JE KONTO IN DER KASSE (Finn 19.11.2026, Admin → Payouts · alle IDs, #kasse: „füg das ich hier auch Payouts Notizen machen
kann hinzu“). Ohne Netz: Auth, Supabase-Lesen und -Schreiben ersetzt. Prüft Leser (_kasse_notizen_lesen), Route PATCH /admin/kasse-notiz (Rechte wie PU3,
Spalte fehlt → 409, leer = löschen), die Übergabe in payout_ready und die Frontend-/SQL-Verdrahtung als Textprüfung.
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_kn1_kasse_notiz.py"""
import inspect
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import requests  # noqa: E402
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


class Antw:
    def __init__(self, text, code=400):
        self.text, self.status_code = text, code


def spalte_fehlt_fehler(spalte="payout_notiz"):
    e = requests.exceptions.HTTPError("400 Client Error")
    e.response = Antw('{"code":"42703","message":"column accounts.%s does not exist"}' % spalte)
    return e


K1, K2 = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
HT, EMIN = "u-ht", "u-emin"

print("1) Leser: nur Konten mit Text, Fehler kosten nur die Notizen")
_alt_all = app._sb_all
GEFRAGT = []
app._sb_all = lambda t, p: (GEFRAGT.append((t, dict(p))) or [{"id": K1, "payout_notiz": "Absprache: erst nach KYC"}, {"id": K2, "payout_notiz": "  "}, {"id": None, "payout_notiz": "x"}])
check(app._kasse_notizen_lesen() == {K1: "Absprache: erst nach KYC"}, "nur Konten mit Text, leere/ohne id fallen raus")
check(GEFRAGT and GEFRAGT[0][0] == "accounts" and GEFRAGT[0][1].get("payout_notiz") == "not.is.null" and GEFRAGT[0][1].get("select") == "id,payout_notiz",
      "liest accounts.payout_notiz mit not.is.null, nur id + Notiz")
app._sb_all = lambda t, p: (_ for _ in ()).throw(spalte_fehlt_fehler())
check(app._kasse_notizen_lesen() == {}, "Spalte fehlt (SQL noch nicht eingespielt) → leer, kein Fehler")
app._sb_all = lambda t, p: (_ for _ in ()).throw(RuntimeError("Netz weg"))
check(app._kasse_notizen_lesen() == {}, "anderer Lesefehler → leer, Kasse bleibt")
app._sb_all = _alt_all

print("2) Übergabe in payout_ready (admin_build_overview)")
src = inspect.getsource(app.admin_build_overview) if hasattr(app, "admin_build_overview") else open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
check("kasse_notiz = _kasse_notizen_lesen()" in src, "Übersicht liest die Notizen einmal je Aufbau")
check('"payout_notiz": kasse_notiz.get(aid, "")' in src, "jede Kasse-Zeile trägt payout_notiz ('' ohne Notiz)")

print("3) Route PATCH /admin/kasse-notiz")
ST = {"rolle": "voll", "gruppe": None, "konten": {K1: {"id": K1, "user_id": HT, "payout_notiz": None}, K2: {"id": K2, "user_id": EMIN, "payout_notiz": "alt"}},
      "upd": [], "sel_fehler": None, "upd_fehler": None}


def fake_admin_voll():
    if ST["rolle"] == "voll":
        return "u-finn", None
    return None, (app.jsonify({"error": "Kein Admin"}), 403)


def fake_wd_login():
    if ST["rolle"] == "anonym":
        return None, (app.jsonify({"error": "Nicht angemeldet"}), 401)
    app.g.admin_sicht = ST["gruppe"]
    return "u-x", None


def fake_select(t, p):
    if ST["sel_fehler"]:
        raise ST["sel_fehler"]
    assert t == "accounts", t
    aid = p["id"].split("eq.", 1)[1]
    k = ST["konten"].get(aid)
    return [dict(k)] if k else []


def fake_update(t, p, body):
    if ST["upd_fehler"]:
        raise ST["upd_fehler"]
    assert t == "accounts", t
    aid = p["id"].split("eq.", 1)[1]
    ST["upd"].append((aid, dict(body)))
    if aid not in ST["konten"]:
        return []
    ST["konten"][aid].update(body)
    return [dict(ST["konten"][aid])]


app._admin_voll = fake_admin_voll
app._wd_login = fake_wd_login
app._admin_verwalter = lambda: ST["rolle"] == "verwalter"
app.sb_select = fake_select
app.sb_update = fake_update
c = app.app.test_client()


def patch(body):
    r = c.patch("/admin/kasse-notiz?ansicht=admin", json=body, headers={"sb-token": "t"})
    return r.status_code, (r.get_json(silent=True) or {})


code, d = patch({"account_id": K1, "notiz": "  Absprache   mit Marc:\n erst Freitag  "})
check(code == 200 and d.get("payout_notiz") == "Absprache mit Marc: erst Freitag", "voller Admin speichert, Leerraum zusammengezogen")
check(ST["upd"] and ST["upd"][-1] == (K1, {"payout_notiz": "Absprache mit Marc: erst Freitag"}), "schreibt NUR payout_notiz (kein review_notiz/notes/Termin)")
code, d = patch({"account_id": K1, "notiz": "x" * 500})
check(code == 200 and len(d.get("payout_notiz") or "") == app.PAYOUT_NOTIZ_MAX, "über 200 Zeichen → gekürzt wie PU3")
code, d = patch({"account_id": K1, "notiz": "   "})
check(code == 200 and d.get("payout_notiz") == "" and ST["upd"][-1] == (K1, {"payout_notiz": None}), "leer = löschen (NULL)")
code, d = patch({"account_id": "abc", "notiz": "x"})
check(code == 400, "ungültige account_id → 400")
n_upd = len(ST["upd"])
code, d = patch({"account_id": "33333333-3333-3333-3333-333333333333", "notiz": "x"})
check(code == 404 and len(ST["upd"]) == n_upd, "unbekanntes Konto → 404, nichts geschrieben")
ST["sel_fehler"] = spalte_fehlt_fehler()
code, d = patch({"account_id": K1, "notiz": "x"})
check(code == 409 and "sql/2026-11-19_kasse_payout_notiz.sql" in str(d.get("error")), "Spalte fehlt → 409 mit SQL-Datei im Text")
ST["sel_fehler"] = RuntimeError("Netz")
code, d = patch({"account_id": K1, "notiz": "x"})
check(code == 502, "Lesefehler → 502")
ST["sel_fehler"] = None
ST["upd_fehler"] = RuntimeError("Schreiben weg")
code, d = patch({"account_id": K1, "notiz": "x"})
check(code == 502, "Schreibfehler → 502")
ST["upd_fehler"] = None

ST["rolle"], ST["gruppe"] = "verwalter", frozenset({EMIN})
n_upd = len(ST["upd"])
code, d = patch({"account_id": K1, "notiz": "fremd"})
check(code == 403 and len(ST["upd"]) == n_upd, "Verwalter: Konto außerhalb seiner Gruppe → 403, nichts geschrieben")
code, d = patch({"account_id": K2, "notiz": "eigene Gruppe"})
check(code == 200 and d.get("payout_notiz") == "eigene Gruppe", "Verwalter: Konto seiner Gruppe → gespeichert")
ST["rolle"] = "mitglied"
code, d = patch({"account_id": K2, "notiz": "x"})
check(code == 403, "weder voller Admin noch Verwalter → 403")
ST["rolle"] = "anonym"
code, d = patch({"account_id": K2, "notiz": "x"})
check(code == 401, "nicht angemeldet → 401")
r = c.open("/admin/kasse-notiz", method="OPTIONS")
check(r.status_code == 200, "OPTIONS (CORS-Vorabfrage) → 200")

print("4) Frontend + SQL (Textprüfung)")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
# KS2 (0ae0b354, 20.11.2026): Notiz als eigene Spalte .c-notiz-td statt klein unter dem Account (KN1)
check("admKasseNotizZelle(tr.querySelector('.c-notiz-td'), r)" in html, "jede Kasse-Zeile (zeile, WD + CFD) bekommt die Notiz in der eigenen Spalte (KS2)")
check(html.count("function admKasseNotizZelle(") == 1 and html.count("async function admKasseNotizSpeichern(") == 1, "Helfer genau einmal definiert")
m = re.search(r"async function admKasseNotizSpeichern\(r, wert\)\{(.*?)\n    \}\n", html, re.S)
body = m.group(1) if m else ""
check("/admin/kasse-notiz?ansicht=admin" in body and "account_id: id, notiz: neu" in body and "method: 'PATCH'" in body, "speichert über PATCH /admin/kasse-notiz mit account_id + notiz")
check("admKasseNotizSetzen(id, alt)" in body, "bei Fehler alter Text zurück")
check("payout-notiz" not in body and "review_notiz" not in body, "kein Weg über PU3-Anfrage oder Radar-Review-Notiz")
sql = open(os.path.join(WURZEL, "sql", "2026-11-19_kasse_payout_notiz.sql"), encoding="utf-8").read()
check("alter table public.accounts add column if not exists payout_notiz text;" in sql, "SQL: Spalte idempotent")
check(not re.search(r"^\s*(drop|delete|update|truncate|create policy|alter policy)\b", sql, re.I | re.M), "SQL: nur die Spalte, nichts Destruktives, keine Policy")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ KN1 Kasse-Notiz: alles grün")
