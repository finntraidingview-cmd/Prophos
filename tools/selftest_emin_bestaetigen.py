#!/usr/bin/env python3
"""Selbsttest EMIN-BESTAETIGEN (Finn 02.11.2026 ~04:35: Emin kann von seiner ID aus die Trades seiner Gruppe nicht bestätigen, z. B. Ahmads).
Echte Routen über den Flask-Test-Client gegen eine nachgebaute DB, ohne Netz und ohne Login: Bestätigen/Zurück/Löschen in Challenge-, Funded- und
Funded-CFD-Planer sowie /plan (werte, start, richtung). Soll: Verwalter = ganze Gruppe, auch ohne sicht=admin; Mitglied = nur eigene;
HT-Login und fremde Gruppen unverändert gesperrt; nachholen (PC-Tab-Automatik) bleibt beim Verwalter ohne Marker bei der eigenen ID.
Aufruf: python3 tools/selftest_emin_bestaetigen.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""   # wie die anderen Selbsttests: kein Hintergrund-Abruf gegen die echte DB
import app  # noqa: E402
from flask import jsonify  # noqa: E402

FEHLER = []


def check(bed, text):
    print(("  ✓ " if bed else "  ✗ ") + text)
    if not bed:
        FEHLER.append(text)


EMIN = "00000000-0000-4000-a000-000000000001"
AHMAD = "00000000-0000-4000-a000-000000000002"
JULIAN = "00000000-0000-4000-a000-000000000003"
HT1 = "00000000-0000-4000-a000-000000000011"
HT_VOLL = "00000000-0000-4000-a000-000000000012"
P_AHMAD = "10000000-0000-4000-a000-000000000002"
P_EMIN = "10000000-0000-4000-a000-000000000001"
P_HT = "10000000-0000-4000-a000-000000000011"
DATEN = {"gruppen": [{"id": "g-emin", "name": "Emin", "verwalter_id": EMIN}, {"id": "g-ht", "name": "Hermann Technologies", "verwalter_id": None}],
         "mitglieder": [{"gruppe_id": "g-emin", "user_id": u} for u in (EMIN, AHMAD, JULIAN)]
         + [{"gruppe_id": "g-ht", "user_id": u} for u in (HT1, HT_VOLL)]}
BESITZER = {P_AHMAD: AHMAD, P_EMIN: EMIN, P_HT: HT1}
LOGIN = {"uid": EMIN}
GESCHRIEBEN = []


def _ids_aus(params):
    f = str(params.get("id") or "")
    if f.startswith("eq."):
        return [f[3:]]
    if f.startswith("in.("):
        return f[4:-1].split(",")
    return []


def _treffer(params):
    aus = []
    for pid in _ids_aus(params):
        u = BESITZER.get(pid)
        if u is None:
            continue
        f = str(params.get("user_id") or "")
        if f.startswith("eq.") and f[3:] != u:
            continue
        if f.startswith("in.(") and u not in f[4:-1].split(","):
            continue
        aus.append({"id": pid, "user_id": u, "master_firm": "FTMO", "master_account_id": "k-" + pid[-2:], "master_name": "Konto"})
    return aus


def _select(tabelle, params=None, **_):
    params = params or {}
    if tabelle == "auto_plan_regeln":
        return [{"id": 1, "user_ids": [HT_VOLL], "regeln": {}, "aktiv": True}]
    if tabelle == "trade_plans" and params.get("id"):
        return _treffer(params)
    return []


def _update(tabelle, params, body=None, **_):
    z = _treffer(params)
    GESCHRIEBEN.extend(str(x["id"]) for x in z)
    return z


def _einrichten():
    app._admin_auth = lambda *a, **k: (None, (jsonify({"error": "Nur für Admins"}), 403))
    app._wd_login = lambda: (LOGIN["uid"], None)
    app.admin_gruppen_daten = lambda: DATEN
    app.admin_zugang_nur_eigene = lambda u: False
    app.admin_voll_uids = lambda: frozenset({HT_VOLL})
    app.sb_select = _select
    app.sb_update = _update
    app.sb_delete = _update
    app._sb_all = lambda *a, **k: []
    app.ap_bal_guard = lambda lade: None
    app._ap_im_planer = lambda u: str(u) == HT_VOLL
    app._fdp_regeln_laden = lambda: {"user_ids": [HT_VOLL], "aktiv": True, "zeiten": {}}
    app._fcp_regeln_laden = lambda: {"user_ids": [HT_VOLL], "aktiv": True, "zeiten": {}}
    app._fd_gruppen_ids = lambda: [EMIN, AHMAD, JULIAN]
    app._ap_werte_setzen = lambda pid, body, alle, uid, gruppe=None: _werte(pid, alle, uid, gruppe)
    app._ap_nachholen = lambda pid, alle, uid, gruppe=None: _werte(pid, alle, uid, gruppe)
    app._ap_richtung_plan = lambda pid: jsonify({"ok": True, "richtung": "buy"})
    app._ap_neu_starten = lambda pid: jsonify({"ok": True})


def _werte(pid, alle, uid, gruppe):
    """Dieselbe Besitz-Prüfung wie _ap_werte_setzen/_ap_nachholen: alle | Gruppe | eigener Plan."""
    u = BESITZER.get(pid)
    darf = alle or (gruppe is not None and u in gruppe) or str(u) == str(uid)
    return (jsonify({"ok": True}), 200) if darf else (jsonify({"ok": False, "msg": "nur eigene Pläne"}), 403)


def post(pfad, uid, **body):
    LOGIN["uid"] = uid
    GESCHRIEBEN.clear()
    with app.app.test_client() as c:
        r = c.post(pfad, json=body, headers={"sb-token": "x"})
    return r.status_code, (r.get_json(silent=True) or {}), list(GESCHRIEBEN)


def main():
    _einrichten()
    print("Reine Regel")
    v = app.ap_verwalter_sicht
    check(v(frozenset({EMIN}), "") == "admin" and v(frozenset({EMIN}), None) == "admin", "Verwalter: Sicht fest admin, auch ohne Marker")
    check(v(None, "") == "" and v(None, "admin") == "admin", "alle anderen: Sicht bleibt, wie sie kam")

    for name, basis in (("Challenge", "/admin/auto-plan"), ("Funded", "/admin/funded-plan"), ("Funded CFD", "/admin/funded-cfd-plan")):
        print(name + " bestätigen")
        for sicht_txt, extra in (("mit sicht=admin", {"sicht": "admin"}), ("ohne Marker", {})):
            s, d, w = post(basis + "/bestaetigen", EMIN, plan_ids=[P_AHMAD], **extra)
            check(s == 200 and w == [P_AHMAD], f"Emin bestätigt Ahmads Plan {sicht_txt} (HTTP {s}, {d.get('msg') or 'ok'})")
        s, d, w = post(basis + "/bestaetigen", EMIN, plan_ids=[P_HT], sicht="admin")
        check(s == 403 and not w, f"Emin an HT-Plan: gesperrt (HTTP {s})")
        s, d, w = post(basis + "/bestaetigen", EMIN, plan_ids=[P_AHMAD, P_HT])
        check(s == 403 and not w, f"Emin, gemischte Liste mit HT-Plan: gesperrt, nichts geschrieben (HTTP {s})")
        s, d, w = post(basis + "/bestaetigen", AHMAD, plan_ids=[P_EMIN], sicht="admin")
        check(s == 403 and not w, f"Mitglied Ahmad an Emins Plan, auch mit sicht=admin: gesperrt (HTTP {s})")
        s, d, w = post(basis + "/bestaetigen", AHMAD, plan_ids=[P_AHMAD])
        check(s == 200 and w == [P_AHMAD], f"Mitglied Ahmad am eigenen Plan: geht (HTTP {s})")
        s, d, w = post(basis + "/bestaetigen", HT1, plan_ids=[P_HT], sicht="admin")
        check(s == 403 and d.get("nur_ansehen") is True and not w, f"HT-Login ohne admin_voll: nur ansehen (HTTP {s})")
        s, d, w = post(basis + "/zurueck", EMIN, plan_id=P_AHMAD)
        check(s == 200 and w == [P_AHMAD], f"Emin nimmt Ahmads Bestätigung zurück, ohne Marker (HTTP {s})")
        s, d, w = post(basis + "/loeschen", EMIN, plan_id=P_AHMAD)
        check(s == 200 and w == [P_AHMAD], f"Emin löscht Ahmads Vorschlag, ohne Marker (HTTP {s})")
        s, d, w = post(basis + "/loeschen", AHMAD, plan_id=P_EMIN)
        check(s == 403 and not w, f"Mitglied Ahmad löscht Emins Vorschlag: gesperrt (HTTP {s})")

    print("/admin/auto-plan/plan")
    s, d, _ = post("/admin/auto-plan/plan", EMIN, plan_id=P_AHMAD, aktion="werte", tp_usd=100)
    check(s == 200, f"Emin ändert Werte an Ahmads Plan, ohne Marker (HTTP {s})")
    s, d, _ = post("/admin/auto-plan/plan", EMIN, plan_id=P_HT, aktion="werte", tp_usd=100, sicht="admin")
    check(s == 403, f"Emin ändert Werte an HT-Plan: gesperrt (HTTP {s})")
    s, d, _ = post("/admin/auto-plan/plan", AHMAD, plan_id=P_EMIN, aktion="werte", tp_usd=100)
    check(s == 403, f"Mitglied Ahmad ändert Werte an Emins Plan: gesperrt (HTTP {s})")
    s, d, _ = post("/admin/auto-plan/plan", EMIN, plan_id=P_AHMAD, aktion="nachholen")
    check(s == 403, f"nachholen (PC-Tab-Automatik) ohne Marker: Verwalter nur eigene ID (HTTP {s})")
    s, d, _ = post("/admin/auto-plan/plan", EMIN, plan_id=P_EMIN, aktion="nachholen")
    check(s == 200, f"nachholen am eigenen Plan: geht (HTTP {s})")
    s, d, _ = post("/admin/auto-plan/plan", EMIN, plan_id=P_AHMAD, aktion="richtung_plan")
    check(s == 200, f"Emin dreht Richtung an Ahmads Plan, ohne Marker (HTTP {s})")
    s, d, _ = post("/admin/auto-plan/plan", EMIN, plan_id=P_AHMAD, aktion="neu_starten")
    check(s == 200, f"Emin startet Ahmads Plan neu, ohne Marker (HTTP {s})")
    s, d, _ = post("/admin/auto-plan/plan", EMIN, plan_id=P_HT, aktion="neu_starten")
    check(s == 403, f"Emin startet HT-Plan neu: gesperrt (HTTP {s})")
    s, d, _ = post("/admin/auto-plan/plan", EMIN, plan_id=P_HT, aktion="richtung_plan", sicht="admin")
    check(s == 403, f"Emin dreht Richtung an HT-Plan: gesperrt (HTTP {s})")
    s, d, _ = post("/admin/auto-plan/plan", AHMAD, plan_id=P_AHMAD, aktion="richtung_plan", sicht="admin")
    check(s == 403, f"Mitglied Ahmad: Richtung bleibt gesperrt wie bisher (HTTP {s})")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
