#!/usr/bin/env python3
"""Selbsttest VR1 (Master 25.11.2026, Befund Prüfer S2 bei KP2/KP2d): POST /admin/vorrat — Sperr-Matrix (status), bestellt, bestellt_weg und die
„nur Admin"-Aktionen (einstellung, ziel, ziel_neu, ki_hinweis, ki_hinweis_weg). Vorher sperrte _admin_darf_uid nur eingeschränkte Logins; jede HT-ID
ohne admin_zugang durfte fremde IDs schreiben. Jetzt wie kaufliste_spaeter / konto-anlegen (kapital_app._gate): eigene ID immer; fremd eingeschränkt
wie bisher (Verwalter = seine Gruppe, Mitglied = nur er), uneingeschränkt nur ADMIN_EMAILS oder admin_mail_leser. Flask-Testclient, ohne Netz.
Aufruf: python3 tools/selftest_vr1_vorrat_rechte.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402
from flask import g, jsonify  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


ICH, FREMD, GRUPPE_MIT, LESER, ADMIN = ("aaaaaaaa-0000-0000-0000-00000000000" + c for c in "12345")
LOGIN = {}          # aktueller Login: uid, sicht (None | frozenset), verwalter, admin_mail (bool)
GESCHRIEBEN = []


def wd_login():
    g.login_uid = LOGIN["uid"]
    if LOGIN.get("sicht") is not None:
        g.admin_nur_uid, g.admin_sicht, g.admin_verwalter = LOGIN["uid"], LOGIN["sicht"], LOGIN.get("verwalter", False)
    return LOGIN["uid"], None


def admin_auth():
    return ("admin@x", None) if LOGIN.get("admin_mail") else (None, (jsonify({"error": "nein"}), 403))


class Antwort:
    status_code = 201
    text = ""


def sb_anfrage(methode, url, **kw):
    GESCHRIEBEN.append(("anfrage", methode, url.rsplit("/", 1)[-1], kw.get("json") or kw.get("params")))
    return Antwort()


app._wd_login = wd_login
app._admin_auth = admin_auth
app.admin_mail_leser_uids = lambda: {LESER}
app._sb_anfrage = sb_anfrage
app._sb_pruefen = lambda r: None
app.sb_insert = lambda t, z: (GESCHRIEBEN.append(("insert", t, z)), dict(z, id=7, at="2026-11-25T00:00:00Z"))[1]
app.sb_update = lambda t, f, u: (GESCHRIEBEN.append(("update", t, f, u)), [{"id": 7}])[1]
app.sb_select = lambda t, p: [{"parameter": {}}] if t == "vorrat_einstellung" else []
app._vorrat2_tabellen = lambda: ([], {"bestellt_h": 48}, [], True)
app.vorrat2_lauf = lambda q: None
app.admin_build_vorrat = lambda: {}
app._vorrat_antwort = lambda d: {"zellen": []}
C = app.app.test_client()


def post(login, body):
    LOGIN.clear()
    LOGIN.update(login)
    GESCHRIEBEN.clear()
    r = C.post("/admin/vorrat", json=body, headers={"sb-token": "t"})
    return r.status_code, list(GESCHRIEBEN)


KUNDE = {"uid": ICH}                                              # HT-ID ohne admin_zugang, kein Admin
ADM = {"uid": ADMIN, "admin_mail": True}                          # ADMIN_EMAILS
LES = {"uid": LESER}                                              # admin_mail_leser („Finn + Pascal")
VERW = {"uid": ICH, "sicht": frozenset({ICH, GRUPPE_MIT}), "verwalter": True}
MITGL = {"uid": ICH, "sicht": frozenset({ICH})}
ST = lambda z: {"user_id": z, "firma": "FundedNext", "status": "gesperrt"}
BE = lambda z: {"aktion": "bestellt", "user_id": z, "firma": "FundedNext", "anzahl": 2}

print("1) Sperr-Matrix (status)")
s, w = post(KUNDE, ST(FREMD))
check(s == 403 and not w, f"HT-ID ohne admin_zugang → fremde Zelle 403, nichts geschrieben ({s}) — die Lücke")
s, w = post(KUNDE, ST(ICH))
check(s == 200 and w and w[0][3]["user_id"] == ICH, f"eigene Zelle weiter erlaubt ({s})")
check(post(ADM, ST(FREMD))[0] == 200 and post(LES, ST(FREMD))[0] == 200, "ADMIN_EMAILS und admin_mail_leser → fremde Zelle erlaubt")
check(post(VERW, ST(GRUPPE_MIT))[0] == 200 and post(VERW, ST(FREMD))[0] == 403, "Verwalter: Mitglied seiner Gruppe ja, fremde ID nein (wie bisher)")
check(post(MITGL, ST(FREMD))[0] == 403 and post(MITGL, ST(ICH))[0] == 200, "eingeschränktes Mitglied: nur eigene (wie bisher)")

print("2) Bestellung (bestellt)")
s, w = post(KUNDE, BE(FREMD))
check(s == 403 and not w, f"HT-ID ohne admin_zugang → fremde Bestellung 403 ({s})")
s, w = post(KUNDE, BE(ICH))
check(s == 200 and w and w[0][1] == "vorrat_bestellt" and w[0][2]["user_id"] == ICH, f"eigene Bestellung erlaubt ({s})")
check(post(ADM, BE(FREMD))[0] == 200 and post(LES, BE(FREMD))[0] == 200 and post(VERW, BE(GRUPPE_MIT))[0] == 200 and post(VERW, BE(FREMD))[0] == 403,
      "Admin/Leser fremd ja, Verwalter nur Gruppe")

print("3) Bestellung zurücknehmen (bestellt_weg)")
s, w = post(KUNDE, {"aktion": "bestellt_weg", "id": 7})
check(s == 200 and w and w[0][2].get("user_id") == f"eq.{ICH}", f"HT-ID ohne admin_zugang: nur eigene Bestellungen ({w and w[0][2]})")
s, w = post(ADM, {"aktion": "bestellt_weg", "id": 7})
check(s == 200 and w and "user_id" not in w[0][2], "Admin: jede Bestellung (ohne user_id-Filter, wie bisher)")
s, w = post(VERW, {"aktion": "bestellt_weg", "id": 7})
check(s == 200 and w and "in.(" in str(w[0][2].get("user_id")), f"Verwalter: Filter auf seine Gruppe (wie bisher) ({w and w[0][2].get('user_id')})")

print("4) „nur Admin“-Aktionen")
for body in ({"aktion": "einstellung", "sicherheit": 0.5}, {"aktion": "ki_hinweis", "text": "Test"}, {"aktion": "ki_hinweis_weg", "id": "x"},
             {"aktion": "ziel", "firma": "FundedNext", "von": 1, "bis": 2}, {"aktion": "ziel_neu", "firma": "FundedNext"}):
    s, w = post(KUNDE, body)
    check(s == 403 and not w, f"{body['aktion']}: HT-ID ohne admin_zugang → 403 ({s})")
    s2, _ = post(VERW, body)
    check(s2 == 403, f"{body['aktion']}: Verwalter → 403 (wie bisher) ({s2})")
s, w = post(ADM, {"aktion": "einstellung", "sicherheit": 0.5})
check(s == 200 and w, f"einstellung: ADMIN_EMAILS erlaubt ({s})")
s, w = post(LES, {"aktion": "ki_hinweis", "text": "Bitte vorsichtig"})
check(s == 200 and w, f"ki_hinweis: admin_mail_leser erlaubt ({s})")
print("5) Admin-Prüfung nicht möglich (Review)")
_alt_auth = app._admin_auth
app._admin_auth = lambda: (None, (jsonify({"error": "Admin-Prüfung nicht verfügbar"}), 502))
s, w = post(KUNDE, ST(FREMD))
check(s == 502 and not w, f"fremde Zelle: 502 wird weitergereicht, nichts geschrieben ({s})")
check(post(KUNDE, ST(ICH))[0] == 200, "eigene Zelle braucht keine Admin-Prüfung → weiter erlaubt")
s, w = post(KUNDE, {"aktion": "einstellung", "sicherheit": 0.5})
check(s == 502 and not w, f"einstellung: 502 weitergereicht ({s})")
s, w = post(KUNDE, {"aktion": "bestellt_weg", "id": 7})
check(s == 200 and w and w[0][2].get("user_id") == f"eq.{ICH}", f"bestellt_weg: eigene Bestellung trotzdem zurücknehmbar, nur eigene ({s})")
app._admin_auth = _alt_auth
s, _ = post(KUNDE, {"aktion": "rechnen"})
check(s == 200, f"rechnen (nur neu rechnen, schreibt keine fremden Daten): jeder Login wie bisher ({s})")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ alle Prüfungen grün")
