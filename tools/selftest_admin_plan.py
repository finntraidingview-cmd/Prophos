#!/usr/bin/env python3
"""Selbsttest ADMIN → TRADE PLANEN FÜR EINE ANDERE ID (app.py, 29.10.2026, Slave 7) — ohne Netz (Flask-Testclient, DB als Attrappe).
Geprüft:
- admin_plan_zeile:
  - Whitelist; user_id/master_account_id aus dem Konto; status planned, kein auto_plan
  - Wege nur mt5v2/tvv2/tsv2, Topstep nur als Winning Day
  - Richtung Pflicht; sofort → start_um jetzt; mit Uhrzeit Pflicht und nicht in der Vergangenheit; Zahlen geprüft
- GET /admin/plan-konto: ohne Zugangsdaten; Verwalter nur seine Gruppe; ohne Gate 403
- POST /admin/plan-anlegen:
  - user_id = Besitzer
  - Richtungsschutz gegen die Ziel-ID → 409
  - DB-Riegel (check_violation) → 409 mit Grund
  - Live-Konto → 400
Aufruf: python3 tools/selftest_admin_plan.py"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, g, jsonify, request

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HIER, "..", "app.py")
FEHLER = []
MARC = "6c206a34-c4a7-4352-8097-bb17366bcea1"
KONTO = {"id": "11111111-2222-4333-8444-555555555555", "user_id": MARC, "name": "100k 511448478 → Phase 1", "firm": "FTMO",
         "account_type": "phase1", "external_id": "511448478", "cred_login": "geheim", "cred_password": "geheim", "meta_api_token": "x"}
TOPSTEP = dict(KONTO, id="11111111-2222-4333-8444-666666666666", name="150k EXPRESS-…", firm="Topstep", account_type="funded")
LIVE = dict(KONTO, id="11111111-2222-4333-8444-777777777777", name="Fusion", firm="Fusion Markets", account_type="live")


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


class R:
    def __init__(self, status, d=None, text=""):
        self.status_code, self._d, self.text = status, d, text

    def json(self):
        return self._d


class DB:
    def __init__(self):
        self.inserts, self.frei, self.riegel = [], {"frei": True}, None

    def sb_select(self, t, q):
        if t == "trade_plans":
            return [p for p in getattr(self, "geplant", []) if p["richtung"] == q["richtung"][3:]]
        i = q.get("id", "")[3:]
        return [dict(k) for k in (KONTO, TOPSTEP, LIVE) if k["id"] == i]

    def sb_insert(self, t, row):
        if self.riegel:
            resp = requests.Response()
            resp.status_code, resp._content = 400, json.dumps({"code": "23514", "message": self.riegel}).encode()
            raise requests.exceptions.HTTPError(response=resp)
        self.inserts.append(dict(row))
        return dict(row, id="plan-1")

    def _sb_anfrage(self, m, url, json=None, headers=None, timeout=None):
        self.rpc = json
        return R(200, self.frei)


def lade(db, gate):
    src = open(APP, encoding="utf-8").read()
    i = src.index("# ══ ADMIN → TRADE PLANEN FÜR EINE ANDERE ID")
    j = src.index('@app.route("/admin/konto-mails"', i)
    app = Flask("t")
    ns = {"app": app, "jsonify": jsonify, "request": request, "g": g, "re": re, "requests": requests, "datetime": datetime,
          "timedelta": timedelta, "timezone": timezone, "sb_select": db.sb_select, "sb_insert": db.sb_insert, "_sb_anfrage": db._sb_anfrage,
          "_sb_pruefen": lambda r: None, "_sb_headers": lambda *a: {}, "SUPABASE_URL": "https://x", "_admin_konto_gate": gate,
          "_ap_norm": lambda f: re.sub(r"[^a-z0-9]", "", str(f or "").lower()), "_firm_norm": lambda f: f}
    exec(src[i:j], ns)
    return app, ns


def main():
    db = DB()
    app, ns = lade(db, lambda: (None, None))
    Z, jetzt = ns["admin_plan_zeile"], datetime(2026, 10, 29, 13, 0, tzinfo=timezone.utc)
    row = {"route": "mt5v2", "richtung": "sell", "master_contracts": 20, "master_tp": 2000, "master_sl": 1500, "master_name": "x",
           "master_firm": "FTMO", "user_id": "fremd", "status": "open", "auto_plan": True, "master_account_id": "anderes", "start_um_gestartet_at": "x",
           "notes": "Hand", "start_um": "2026-10-29T14:30:00+00:00"}
    z, f = Z({"row": row}, KONTO, jetzt)
    check(f is None and z["user_id"] == MARC and z["master_account_id"] == KONTO["id"] and z["status"] == "planned" and "auto_plan" not in z
          and "start_um_gestartet_at" not in z and z["start_um"] == "2026-10-29T14:30:00+00:00" and z["master_contracts"] == 20.0,
          "Zeile: user_id/Konto vom Besitzer, status planned, nichts Fremdes (auto_plan, Claim) durchgereicht")
    z, f = Z({"row": dict(row, start_um=None), "sofort": True}, KONTO, jetzt)
    check(f is None and z["start_um"] == jetzt.isoformat(), "sofort → start_um jetzt")
    check(Z({"row": dict(row, start_um=None)}, KONTO, jetzt)[1].startswith("Startzeit fehlt"), "mit Uhrzeit ohne Uhrzeit → Fehler")
    check("Vergangenheit" in Z({"row": dict(row, start_um="2026-10-29T12:00:00+00:00")}, KONTO, jetzt)[1], "Startzeit in der Vergangenheit → Fehler")
    check("Weg nicht erlaubt" in Z({"row": dict(row, route="dup")}, KONTO, jetzt)[1] and "Weg nicht erlaubt" in Z({"row": dict(row, route="mt5")}, KONTO, jetzt)[1],
          "klassische Wege (dup, mt5) für andere IDs nicht")
    check("Richtung" in Z({"row": dict(row, richtung=None)}, KONTO, jetzt)[1], "Richtung Pflicht")
    check("ungültig" in Z({"row": dict(row, master_tp="abc")}, KONTO, jetzt)[1] and "ungültig" in Z({"row": dict(row, master_sl=-5)}, KONTO, jetzt)[1],
          "Zahlen geprüft")
    check("Winning Day" in Z({"row": dict(row, route="tsv2")}, TOPSTEP, jetzt)[1] and "Winning Day" in Z({"row": dict(row, route="tvv2")}, TOPSTEP, jetzt)[1]
          and Z({"row": dict(row, route="tsv2", winning_day=True, orbit_v3=True, hedge_eur=40)}, TOPSTEP, jetzt)[0] is None,
          "Topstep: nur Winning Day (tsv2), nie TradingView, nie Nova")
    # Gegenprüfung 29.10.2026 (Funde 1 + 3): Weg ↔ Konto, Kennungen aus dem Konto, Hedge-Felder nur mit Hedge-Weg
    FUT = dict(KONTO, id="11111111-2222-4333-8444-888888888888", firm="Apex Trader", account_type="funded", external_id="PAAPEX6850100000001", name="150k PA …")
    FUT_OHNE = dict(FUT, external_id="")
    check("nur Echo V2" in Z({"row": dict(row, route="tvv2", orbit_v3=True, hedge_eur=50)}, KONTO, jetzt)[1], "CFD-Konto mit Orbit → abgelehnt (nur Echo V2)")
    check("nur für CFD" in Z({"row": dict(row, route="mt5v2")}, FUT, jetzt)[1], "Futures-Konto mit Echo V2 → abgelehnt")
    check("External ID" in Z({"row": dict(row, route="tvv2")}, FUT_OHNE, jetzt)[1], "Futures ohne External ID → abgelehnt")
    check("Winning-Days-Konten" in Z({"row": dict(row, route="tvv2", hedge_eur=40, orbit_v3=False)}, FUT, jetzt)[1], "Winning Day auf Funded (nicht winning_days) → abgelehnt")
    z, f = Z({"row": dict(row, route="tvv2", orbit_v3=True, hedge_eur=60, hedge_faktor=0.3)}, FUT, jetzt)
    check(f is None and z["orbit_v3"] is True and z["hedge_eur"] == 60.0, "Orbit (V3) auf Futures-Funded mit Hedge ok")
    z, f = Z({"row": dict(row, route="tvv2", hedge_eur=None)}, FUT, jetzt)
    check(f is None and z["orbit_v3"] is False and "hedge_eur" not in z, "Orbit V2 ohne Hedge: orbit_v3 false, keine Hedge-Felder")
    z, f = Z({"row": dict(row, hedge_eur=99, hedge_faktor=1, orbit_v3=True, rest_hedge=True, master_firm="Andere Firma", master_name="Falsch")}, KONTO, jetzt)
    check(f is None and "hedge_eur" not in z and "hedge_faktor" not in z and "rest_hedge" not in z and z.get("orbit_v3") is not True
          and z["master_firm"] == "FTMO" and z["master_name"] == KONTO["name"],
          "Echo V2: Hedge-Felder/rest_hedge verworfen, Firma + Name aus dem Konto (nicht aus dem Request)")
    check("Lots" in Z({"row": dict(row, master_contracts=None)}, KONTO, jetzt)[1], "Kontrakte/Lots Pflicht")
    G = ns["admin_plan_gegen_geplant"]
    norm = lambda f: re.sub(r"[^a-z0-9]", "", str(f or "").lower())   # noqa: E731
    pl = [{"status": "planned", "richtung": "buy", "master_firm": "Apex Trader", "master_name": "Apex A WD"}]
    check(G(pl, "Apex Trader", "sell", norm) == "Apex A WD" and G(pl, "Apex Trader", "buy", norm) is None and G(pl, "FTMO", "sell", norm) is None,
          "geplanter Plan derselben Firma in Gegenrichtung sperrt; gleiche Richtung / andere Firma nicht")
    z, f = Z({"row": dict(row, route="tsv2", winning_day=True, hedge_eur=40, hedge_faktor=0.8)}, TOPSTEP, jetzt)
    check(f is None and z["winning_day"] is True and z["hedge_eur"] == 40.0, "Topstep Winning Day mit Hedge-Feldern ok")

    c = app.test_client()
    print("GET /admin/plan-konto")
    d = c.get(f"/admin/plan-konto?account_id={KONTO['id']}").get_json()
    check(d["ok"] and d["konto"]["name"] == KONTO["name"] and not any(k in d["konto"] for k in ("cred_login", "cred_password", "meta_api_token")),
          "Kontozeile ohne Zugangsdaten/MetaApi")
    app_v, _ = lade(db, lambda: (frozenset({"aaaaaaaa-0000-4000-8000-000000000000"}), None))
    check(app_v.test_client().get(f"/admin/plan-konto?account_id={KONTO['id']}").status_code == 403, "Verwalter: Konto außerhalb seiner Gruppe → 403")
    app_n, _ = lade(db, lambda: (None, (jsonify({"ok": False, "msg": "Nur für Admins"}), 403)))
    check(app_n.test_client().get(f"/admin/plan-konto?account_id={KONTO['id']}").status_code == 403
          and app_n.test_client().post("/admin/plan-anlegen", json={"account_id": KONTO["id"], "row": row}).status_code == 403, "ohne Gate → 403")

    print("POST /admin/plan-anlegen")
    r = c.post("/admin/plan-anlegen", json={"account_id": KONTO["id"], "row": row})
    check(r.status_code == 200 and db.inserts[-1]["user_id"] == MARC and db.rpc["p_user"] == MARC and db.rpc["p_richtung"] == "sell"
          and db.rpc["p_ausser_konto"] == KONTO["id"], f"angelegt mit user_id = Besitzer, Richtungsschutz gegen die Ziel-ID ({r.status_code})")
    db.frei = {"frei": False, "grund": "FTMO: dein Konto läuft dort Long"}
    n = len(db.inserts)
    r = c.post("/admin/plan-anlegen", json={"account_id": KONTO["id"], "row": row})
    check(r.status_code == 409 and "Richtungs-Schutz" in r.get_json()["msg"] and len(db.inserts) == n, "Gegenrichtung bei der Ziel-ID → 409, nichts angelegt")
    db.frei, db.geplant = {"frei": True}, [{"status": "planned", "richtung": "buy", "master_firm": "FTMO", "master_name": "100k anderes FTMO"}]
    r = c.post("/admin/plan-anlegen", json={"account_id": KONTO["id"], "row": row})
    check(r.status_code == 409 and "100k anderes FTMO" in r.get_json()["msg"] and len(db.inserts) == n,
          "geplanter BUY derselben Firma bei Marc → SELL nicht gespeichert (wie das Popup, Gegenprüfung Fund 2)")
    db.geplant = []
    db.frei, db.riegel = {"frei": True}, "Challenge-/Phase-Konto „100k …“ nur ohne Hedge"
    r = c.post("/admin/plan-anlegen", json={"account_id": KONTO["id"], "row": row})
    check(r.status_code == 409 and "nur ohne Hedge" in r.get_json()["msg"], f"DB-Riegel → 409 mit Grund ({r.get_json()['msg'][:60]})")
    db.riegel = None
    check(c.post("/admin/plan-anlegen", json={"account_id": LIVE["id"], "row": row}).status_code == 400, "Live-Konto → 400")
    check(c.post("/admin/plan-anlegen", json={"account_id": "x", "row": row}).status_code == 400, "account_id ungültig → 400")
    print(f"\n{'ALLES OK' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
