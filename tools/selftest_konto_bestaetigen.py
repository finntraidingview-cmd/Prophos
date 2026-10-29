#!/usr/bin/env python3
"""Selbsttest KONTEN ZU BESTÄTIGEN AUS MAIL (app.py, 29.10.2026, Slave 7) — ohne Netz (Flask-Testclient, Datenbank als Attrappe).
Geprüft:
- konto_reset_zeile: Einstellungen der alten Zeile, Startbalance = Größe, Kaufpreis aus der Schablone, nie WD-Farm/Duplikum/Zugangsdaten,
  Name nach Namensregel (Mike-Reset 28.10. als Vorbild)
- konto_vorlage_finden: Firma × Typ × Größe
- POST /konto-reset-bestaetigen:
  - eigene ID: neue Zeile, Kauf-Transaktion, alte als blown archiviert
  - alte Zeile fehlt → 404 „als Kauf anlegen"
  - neue Nummer schon da → 409
  - schon archivierte alte Zeile bleibt
  - fremde ID nur mit Admin-Gate (sonst 403)
- POST /konto-verwerfen: merkt EXT normiert in user_settings konto_verworfen der Ziel-ID, TV-Zeile ignoriert, fremd nur mit Gate
- GET /konto-mails/mein: nur eigene ID, betreff Pflicht, verworfen mit
Aufruf: python3 tools/selftest_konto_bestaetigen.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, jsonify, request

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HIER, "..", "app.py")
FEHLER = []
ICH = "aff98e60-e9a0-4821-9d1d-31634571a2f4"
FREMD = "1c96cf0f-5aa6-46c6-8073-617e083e4378"


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def _wd_num(v):
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


class DB:
    def __init__(self):
        self.konten = [{"id": "alt-1", "user_id": ICH, "name": "150k TDFYSL150930752021 → Challenge", "firm": "Tradeify", "account_type": "challenge",
                        "external_id": "TDFYSL150930752021", "account_size": 150000, "starting_balance": 150000, "balance": 146100, "currency": "USD",
                        "max_drawdown": 4500, "max_daily_drawdown": 4500, "max_loss_per_trade": 4500, "max_profit_per_trade": 3600,
                        "purchase_cost": 200, "kapitel_id": 2, "auto_planer": True, "wd_farm": True, "duplikum_linked": True,
                        "cred_login": "geheim", "cred_password": "geheim", "goal_done_offset": 3, "consistency_pct": None},
                       {"id": "alt-2", "user_id": ICH, "name": "150k TDFYSL150111111111 → Challenge", "firm": "Tradeify", "account_type": "challenge",
                        "external_id": "TDFYSL150111111111", "account_size": 150000, "max_drawdown": 4500}]
        self.archiv = {"alt-2"}
        self.settings, self.inserts, self.updates, self.archiviert, self.entfernt = {}, [], [], [], []
        self.plaene = [{"id": "p-geplant", "master_account_id": "alt-1", "status": "planned"},
                       {"id": "p-claim", "master_account_id": "alt-1", "status": "planned", "start_um_gestartet_at": "2026-10-29T10:00:00Z"},
                       {"id": "p-offen", "master_account_id": "alt-1", "status": "open"},
                       {"id": "p-anderes", "master_account_id": "alt-2", "status": "planned"}]
        self.vorlagen = [{"name": "Tradeify Select 150k", "firm": "Tradeify", "account_type": "challenge", "account_size": 150000, "purchase_cost": 213, "aktiv": True},
                         {"name": "FundedNext 100k", "firm": "FundedNext", "account_type": "phase1", "account_size": 100000, "purchase_cost": 475, "aktiv": True}]

    def sb_select(self, t, q):
        if t == "accounts":
            uid = q["user_id"][3:]
            return [dict(a) for a in self.konten if a["user_id"] == uid]
        if t == "bulk_vorlagen":
            return list(self.vorlagen)
        if t == "trade_plans":
            return [dict(p) for p in self.plaene if p["master_account_id"] == q["master_account_id"][3:] and p["status"] == "planned"]
        if t == "user_settings":
            v = self.settings.get((q["user_id"][3:], q["key"][3:]))
            return [{"value": v}] if v is not None else []
        return []

    def sb_insert(self, t, row):
        self.inserts.append((t, dict(row)))
        if t == "accounts":
            row = dict(row, id=f"neu-{len(self.konten)}")
            self.konten.append(row)
        return row

    def sb_update(self, t, f, body):
        self.updates.append((t, f, body))
        return [{}]

    def _sb_anfrage(self, methode, url, params=None, json=None, headers=None, timeout=None):
        if "user_settings" in url:
            self.settings[(json["user_id"], json["key"])] = json["value"]

        class R:
            status_code = 201

            def raise_for_status(self):
                pass
        return R()

    def _sb_all(self, t, q):
        if t == "user_settings":
            ids = q["user_id"][4:-1].split(",")
            return [{"user_id": u, "value": v} for (u, k), v in self.settings.items() if k == q["key"][3:] and u in ids]
        return []


def lade(db, login, gate):
    src = open(APP, encoding="utf-8").read()

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]

    def konst(name):
        return re.search(rf"^{name} = .*$", src, re.M).group(0)

    i = src.index("# ══ KONTEN ZU BESTÄTIGEN AUS MAIL")
    j = src.index('@app.route("/admin/mail/<int:mid>"', i)
    teile = [konst(k) for k in ("ADMIN_MAIL_UID_RE", "KONTO_MAIL_BETREFF_RE", "TV_KONTEN_NAME_RE", "ADMIN_KONTO_APEX_RE", "ADMIN_KONTO_TYPEN")]
    teile += [block(n) for n in ("admin_konto_ext_norm", "admin_konto_doppel", "tv_konto_normal")]
    app = Flask("t")
    ns = {"app": app, "jsonify": jsonify, "request": request, "re": re, "requests": requests, "datetime": datetime, "timedelta": timedelta,
          "timezone": timezone, "_wd_num": _wd_num, "SUPABASE_URL": "https://x", "_sb_headers": lambda *a: {},
          "sb_select": db.sb_select, "sb_insert": db.sb_insert, "sb_update": db.sb_update, "_sb_anfrage": db._sb_anfrage, "_sb_all": db._sb_all,
          "_ap_archiviert": lambda: set(db.archiv),
          "_konto_archiv_eintragen": lambda uid, aid, grund, at, name=None: db.archiviert.append((uid, aid, grund)) or True,
          "_konto_mails_laden": lambda uids, w, tage, disp=None: [{"id": 1, "user_id": uids[0], "betreff": "Your account reset is confirmed", "text": "…"}],
          "_login_uid_mail": lambda: login, "_admin_konto_gate": gate, "AP_SWEEP_FELDER": "id",
          "ap_archiv_sweep_ziele": lambda plaene, archiv: [p for p in plaene if not p.get("start_um_gestartet_at") and p["master_account_id"] in archiv],
          "_ap_plaene_entfernen": lambda ziele: db.entfernt.extend(p["id"] for p in ziele) or [p["id"] for p in ziele]}
    exec("\n".join(teile) + "\n" + src[i:j], ns)
    return app, ns


def main():
    db = DB()
    app, ns = lade(db, (ICH, "m@x", None), lambda: (None, (jsonify({"ok": False, "msg": "Nur für Admins"}), 403)))
    print("konto_reset_zeile / konto_vorlage_finden")
    v = ns["konto_vorlage_finden"](db.vorlagen, "Tradeify", "challenge", 150000)
    check(v and v["purchase_cost"] == 213, "Schablone Tradeify × challenge × 150k gefunden")
    check(ns["konto_vorlage_finden"](db.vorlagen, "Tradeify", "challenge", 50000) is None, "falsche Größe → keine Schablone")
    z = ns["konto_reset_zeile"](db.konten[0], "TDFYSL150831535169", v)
    check(z["name"] == "150k TDFYSL150831535169 → Challenge" and z["external_id"] == "TDFYSL150831535169", f"Name nach Namensregel ({z['name']})")
    check(z["starting_balance"] == 150000 and z["account_size"] == 150000 and z["balance"] == 0, "Startbalance = Größe, Balance 0")
    check(z["purchase_cost"] == 213 and z["max_drawdown"] == 4500 and z["max_profit_per_trade"] == 3600 and "kapitel_id" not in z,
          "Kauf aus Schablone, Limits aus der alten Zeile (wie Mike-Reset), Kapitel nicht kopiert (Trigger setzt das von heute)")
    check(ns["konto_reset_zeile"](dict(db.konten[0], goal_kind="winning_days"), "X1234567", v)["goal_manual"] is True, "goal_manual folgt der Ziel-Art")
    check(z["wd_farm"] is False and z["duplikum_linked"] is False and "cred_login" not in z and "cred_password" not in z
          and "goal_done_offset" not in z and "id" not in z, "nie WD-Farm/Duplikum/Zugangsdaten/Zählstand/alte id")
    check(ns["konto_reset_zeile"](db.konten[0], "X1234567", None)["purchase_cost"] == 200, "ohne Schablone: Kauf der alten Zeile")

    c = app.test_client()
    print("POST /konto-reset-bestaetigen")
    r = c.post("/konto-reset-bestaetigen", json={"neu": "TDFYSL150831535169", "alt": "TDFYSL150930752021", "tv_name": "TDFYSL150831535169"})
    d = r.get_json()
    neu = [x for t, x in db.inserts if t == "accounts"]
    tx = [x for t, x in db.inserts if t == "transactions"]
    check(r.status_code == 200 and d["ok"] and d["archiviert"] is True, f"eigene ID: angelegt + alte archiviert ({r.status_code})")
    check(neu and neu[0]["user_id"] == ICH and neu[0]["external_id"] == "TDFYSL150831535169", "neue Zeile bei der eigenen ID")
    check(db.archiviert == [(ICH, "alt-1", "blown")], f"alte Zeile als blown archiviert ({db.archiviert})")
    check(tx and tx[0]["amount"] == -213 and tx[0]["kind"] == "account_purchase", "Kauf-Transaktion −213 € (Reset = Kauf)")
    check(any(t == "tv_konten" and b.get("angelegt_account_id") for t, _f, b in db.updates), "TV-Zeile als angelegt markiert")
    check(db.entfernt == ["p-geplant"] and d["plaene_entfernt"] == 1,
          f"geplanter Trade der alten Zeile entfernt; geclaimt/laufend/andere Zeile bleiben ({db.entfernt})")
    r = c.post("/konto-reset-bestaetigen", json={"neu": "TDFYSL150831535169", "alt": "TDFYSL150930752021"})
    check(r.status_code == 409 and "Gibt es schon" in r.get_json()["msg"], "zweites Mal → 409, nicht doppelt")
    r = c.post("/konto-reset-bestaetigen", json={"neu": "TDFYSL150999999999", "alt": "TDFYSL150000000000"})
    check(r.status_code == 404 and "als Kauf anlegen" in r.get_json()["msg"], "alte Zeile fehlt → 404 (Frontend öffnet Modal)")
    n_arch = len(db.archiviert)
    r = c.post("/konto-reset-bestaetigen", json={"neu": "TDFYSL150222222222", "alt": "TDFYSL150111111111"})
    check(r.status_code == 200 and r.get_json()["archiviert"] is False and len(db.archiviert) == n_arch, "schon archivierte alte Zeile bleibt, wie sie ist")
    check(c.post("/konto-reset-bestaetigen", json={"neu": "TDFYSL150222", "alt": "TDFYSL150222"}).status_code == 400, "neu = alt → 400")
    # zwei Zeilen mit derselben alten Nummer: die archivierte Fehl-Zeile (älter) und die aktive → die aktive wird übernommen + archiviert
    db.konten += [{"id": "dup-arch", "user_id": ICH, "name": "Fehl-Zeile", "firm": "Tradeify", "account_type": "challenge", "external_id": "TDFYSL150444444444",
                   "account_size": 150000, "max_drawdown": 1, "created_at": "2026-10-01"},
                  {"id": "dup-aktiv", "user_id": ICH, "name": "150k TDFYSL150444444444 → Challenge", "firm": "Tradeify", "account_type": "challenge",
                   "external_id": "TDFYSL150444444444", "account_size": 150000, "max_drawdown": 4500, "created_at": "2026-09-01"}]
    db.archiv.add("dup-arch")
    r = c.post("/konto-reset-bestaetigen", json={"neu": "TDFYSL150555555555", "alt": "TDFYSL150444444444"})
    neu_dup = [x for t, x in db.inserts if t == "accounts"][-1]
    check(r.status_code == 200 and db.archiviert[-1][1] == "dup-aktiv" and neu_dup["max_drawdown"] == 4500, "doppelte alte Nummer: aktive Zeile gewinnt")
    db.konten.append({"id": "live-1", "user_id": ICH, "name": "Fusion", "firm": "Fusion Markets", "account_type": "live", "external_id": "FUSION488579"})
    check(c.post("/konto-reset-bestaetigen", json={"neu": "FUSION488580", "alt": "FUSION488579"}).status_code == 400, "Live-Konto als alte Zeile → 400")
    r = c.post("/konto-reset-bestaetigen", json={"user_id": FREMD, "neu": "TDFYSL150333333333", "alt": "TDFYSL150930752021"})
    check(r.status_code == 403, "fremde ID ohne Admin-Gate → 403")

    print("POST /konto-verwerfen")
    r = c.post("/konto-verwerfen", json={"ext": "tdfysl-150207636079", "tv_name": "TDFYSL150207636079"})
    check(r.status_code == 200 and "TDFYSL150207636079" in db.settings[(ICH, "konto_verworfen")], "EXT normiert bei der eigenen ID gemerkt")
    check(any(t == "tv_konten" and b.get("ignoriert_at") and f["name"] == "eq.TDFYSL150207636079" for t, f, b in db.updates), "TV-Zeile mit ignoriert")
    check(c.post("/konto-verwerfen", json={"ext": "x"}).status_code == 400, "ext zu kurz → 400")
    check(c.post("/konto-verwerfen", json={"ext": "TDFYSL150466485987", "user_id": FREMD}).status_code == 403, "fremde ID ohne Gate → 403")
    app2, _ = lade(db, (ICH, "m@x", None), lambda: (None, None))
    r = app2.test_client().post("/konto-verwerfen", json={"ext": "TDFYSL150466485987", "user_id": FREMD})
    check(r.status_code == 200 and "TDFYSL150466485987" in db.settings[(FREMD, "konto_verworfen")], "fremde ID mit Admin-Gate → bei der Ziel-ID gemerkt")
    app3, _ = lade(db, (ICH, "m@x", None), lambda: (frozenset({ICH}), None))
    r = app3.test_client().post("/konto-verwerfen", json={"ext": "TDFYSL150466485988", "user_id": FREMD})
    check(r.status_code == 403, "Verwalter: ID außerhalb seiner Gruppe → 403")

    print("GET /konto-mails/mein")
    r = c.get("/konto-mails/mein?betreff=account%20reset%20is%20confirmed")
    d = r.get_json()
    check(r.status_code == 200 and d["mails"][0]["user_id"] == ICH and "TDFYSL150207636079" in d["verworfen"], "eigene Mails + verworfen")
    check(c.get("/konto-mails/mein").status_code == 400, "ohne betreff → 400")

    print(f"\n{'ALLES OK' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
