#!/usr/bin/env python3
"""Selbsttest ADMIN-KONTO-BESTÄTIGEN (29.10.2026, Slave 7 — Finn 07:15: „Ja — im Admin soll man alle bestätigen können."): POST /admin/konto-anlegen
legt ein Konto für den BESITZER einer TV-Zeile an. Ohne Netz, Flask-Testclient mit Attrappen für Login, Gate-Listen und Supabase:
(A) Gate — Kunde (uneingeschränkt, nicht Admin) und Mitglied (eingeschränkt) → 403; Finn (ADMIN_EMAILS) und Finn + Pascal (admin_mail_leser)
    legen für Marc an; Emin (Verwalter) nur mit ?ansicht=admin und nur für IDs seiner Gruppe.
(B) Whitelist — Zugangsdaten, wd_farm, fremde user_id/id im Body kommen nie in die Zeile; live/ohne External ID/falsche user_id → 400; ID unbekannt → 404.
(C) Doppel — External ID normiert (Apex-Form PA-APEX-685010-01 ↔ PAAPEX6850100000001) oder Kontoname enthält die Nummer → 409 mit Kontoname.
(D) tv_konten — Tabelle fehlt → angelegt, nur nicht markiert, ohne Hinweis; Tabelle da → angelegt_account_id gesetzt (Guard is.null);
    Kaufpreis → Kauf-Transaktion wie saveAccount (EUR, negativ).
Aufruf: python3 tools/selftest_admin_konto_anlegen.py"""
import os
import re
import sys
from datetime import datetime, timezone

import requests
from flask import Flask, g, jsonify, request

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HIER, "..", "app.py")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


FINN, FP, EMIN, AMIR, MARC, INA, MITGL = ("f1111111-0000-4000-8000-000000000001", "f2222222-0000-4000-8000-000000000002",
                                          "e3333333-0000-4000-8000-000000000003", "a4444444-0000-4000-8000-000000000004",
                                          "c5555555-0000-4000-8000-000000000005", "d6666666-0000-4000-8000-000000000006",
                                          "b7777777-0000-4000-8000-000000000007")
TOKEN = {"finn": FINN, "fp": FP, "emin": EMIN, "ina": INA, "mitglied": MITGL}
KONTEN = {MARC: [{"id": "k1", "name": "150k PAAPEX6850100000001 → Funded", "external_id": "PA-APEX-685010-01"},
                 {"id": "k2", "name": "50k TDFYSL50000000777 → Challenge (archiviert)", "external_id": None}]}
LOG = {"insert": [], "update": []}
TV = {"fehlt": True}


def _wd_login():
    uid = TOKEN.get(request.headers.get("sb-token") or "")
    if not uid:
        return None, (jsonify({"error": "Nicht angemeldet"}), 401)
    if uid == EMIN:
        admin = request.args.get("ansicht") == "admin"
        g.admin_sicht, g.admin_verwalter = (frozenset({EMIN, AMIR}), True) if admin else (frozenset({EMIN}), False)
    elif uid == MITGL:
        g.admin_sicht, g.admin_verwalter = frozenset({MITGL}), False
    return uid, None


def _admin_auth():
    uid = TOKEN.get(request.headers.get("sb-token") or "")
    request.environ["prophos.admin_uid"] = uid
    return ("finn@example.com", None) if uid == FINN else (None, (jsonify({"error": "Nur für Admins"}), 403))


class _Antwort:
    def json(self):
        return {"users": [{"id": u} for u in (FINN, FP, EMIN, AMIR, MARC, INA, MITGL)]}


class _Resp:
    status_code = 404
    text = '{"code":"PGRST205","message":"Could not find the table public.tv_konten"}'


def sb_select(tabelle, params):
    assert tabelle == "accounts"
    return KONTEN.get(params["user_id"][3:], [])


class _ConsResp:
    status_code = 400
    text = '{"code":"PGRST204","message":"Could not find the \'consistency_pct\' column of \'accounts\'"}'


def sb_insert(tabelle, body):
    LOG["insert"].append((tabelle, dict(body)))
    if TV.get("cons_fehlt") and tabelle == "accounts" and "consistency_pct" in body:
        raise requests.exceptions.HTTPError(response=_ConsResp())
    return dict(body, id="neu-1") if tabelle == "accounts" else body


def sb_update(tabelle, params, body):
    if TV["fehlt"]:
        raise requests.exceptions.HTTPError(response=_Resp())
    LOG["update"].append((tabelle, params, body))
    return [dict(body)]


def lade():
    src = open(APP, encoding="utf-8").read()
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in ("ADMIN_KONTO_TYPEN", "ADMIN_KONTO_ZIELE", "ADMIN_KONTO_APEX_RE", "ADMIN_MAIL_UID_RE")]
    for name in ("admin_gruppen_tabelle_fehlt", "admin_konto_ext_norm", "admin_konto_doppel", "admin_konto_zeile", "_admin_konto_gate"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    i = src.index('@app.route("/admin/konto-anlegen"')
    teile.append(src[i:src.find("\n\n\n", i)])
    app = Flask("selftest")
    ns = {"re": re, "requests": requests, "g": g, "jsonify": jsonify, "request": request, "datetime": datetime, "timezone": timezone, "app": app,
          "_wd_login": _wd_login, "_admin_auth": _admin_auth, "admin_mail_leser_uids": lambda: frozenset({FP}),
          "_auth_liste_anfrage": lambda: _Antwort(), "sb_select": sb_select, "sb_insert": sb_insert, "sb_update": sb_update}
    exec("\n".join(teile), ns)
    return ns, app


def main():
    ns, app = lade()
    cl = app.test_client()
    basis = {"name": "100k TDFYSL100000000123 → Challenge", "firm": "Tradeify", "account_type": "challenge", "external_id": "TDFYSL100000000123",
             "tv_name": "TDFYSL100000000123"}

    def post(tok, body, q=""):
        LOG["insert"].clear(); LOG["update"].clear()
        return cl.post("/admin/konto-anlegen" + q, json=body, headers={"sb-token": tok})

    # (A) Gate
    check(post("", dict(basis, user_id=MARC)).status_code == 401, "A0 ohne Login → 401")
    r = post("ina", dict(basis, user_id=MARC))
    check(r.status_code == 403 and not LOG["insert"], "A1 Kunde (uneingeschränkt, kein Admin) → 403, nichts angelegt")
    check(post("mitglied", dict(basis, user_id=MARC), "?ansicht=admin").status_code == 403, "A2 Mitglied (eingeschränkt) → 403")
    r = post("fp", dict(basis, user_id=MARC))
    ins = LOG["insert"][0][1] if LOG["insert"] else {}
    check(r.status_code == 200 and r.get_json()["ok"] and ins.get("user_id") == MARC, "A3 Finn + Pascal (admin_mail_leser) legt für Marc an")
    check(post("finn", dict(basis, user_id=MARC)).status_code == 200, "A4 Finn (ADMIN_EMAILS) legt für Marc an")
    check(post("emin", dict(basis, user_id=AMIR)).status_code == 403, "A5 Emin ohne ?ansicht=admin → 403")
    r = post("emin", dict(basis, user_id=AMIR), "?ansicht=admin")
    check(r.status_code == 200 and LOG["insert"][0][1]["user_id"] == AMIR, "A6 Emin mit ?ansicht=admin legt für Amir (seine Gruppe) an")
    r = post("emin", dict(basis, user_id=MARC), "?ansicht=admin")
    check(r.status_code == 403 and not LOG["insert"], "A7 Emin für Marc (nicht seine Gruppe) → 403")

    # (B) Whitelist
    post("finn", dict(basis, user_id=MARC, cred_password="geheim", cred_login="123", wd_farm=True, id="fremd", meta_api_token="x",
                      purchase_cost="", max_drawdown="3000", goal_kind="trading_days", goal_target=5, goal_since="2026-10-29"))
    ins = LOG["insert"][0][1]
    check(not any(k.startswith(("cred_", "meta_api")) for k in ins) and ins["wd_farm"] is False and "id" not in ins, "B1 keine Zugangsdaten/MetaApi/id, wd_farm aus")
    check(set(ins) <= {"user_id", "name", "firm", "account_type", "external_id", "purchase_cost", "max_drawdown", "max_risiko_trade", "auto_planer", "wd_farm",
                       "goal_kind", "goal_target", "goal_min_profit", "goal_done_offset", "goal_since", "goal_manual"}, f"B2 nur Whitelist-Felder ({sorted(ins)})")
    check(ins["max_drawdown"] == 3000.0 and ins["goal_kind"] == "trading_days" and ins["goal_target"] == 5, "B3 Zahlen und Ziel übernommen")
    check(post("finn", dict(basis, user_id=MARC, account_type="live")).status_code == 400, "B4 live → 400")
    check(post("finn", dict(basis, user_id=MARC, external_id="")).status_code == 400, "B5 ohne External ID → 400")
    check(post("finn", dict(basis, user_id="x' or 1=1")).status_code == 400, "B6 ungültige user_id → 400")
    check(post("finn", dict(basis, user_id="99999999-0000-4000-8000-000000000009")).status_code == 404, "B7 unbekannte ID → 404")
    check(post("finn", dict(basis, user_id=MARC, max_drawdown="viel")).status_code == 400, "B8 Zahl ungültig → 400")
    for feld, wert in (("goal_target", "abc"), ("goal_target", float("inf")), ("goal_target", True), ("goal_target", 5.9),
                       ("goal_done_offset", float("-inf")), ("goal_since", "2026-99-99"), ("goal_since", "2026-10-29x"), ("max_drawdown", True)):
        r = post("finn", dict(basis, user_id=MARC, goal_kind="trading_days", **{feld: wert}))
        check(r.status_code == 400 and not LOG["insert"], f"B9 {feld}={wert!r} → 400 (nicht 500/502)")
    post("finn", dict(basis, user_id=MARC, account_type="funded_cfd", consistency_pct=37.5, payout_ready_at="2026-11-11", waiting_payout=True))
    ins = LOG["insert"][0][1]
    check(ins["consistency_pct"] == 37.5 and ins["payout_ready_at"] == "2026-11-11" and str(ins["waiting_payout_since"]).startswith("20"),
          "B10 Consistency + Payout-Felder (Funded CFD) übernommen")
    post("finn", dict(basis, user_id=MARC, payout_ready_at="2026-11-11", waiting_payout=True))
    check("payout_ready_at" not in LOG["insert"][0][1] and "consistency_pct" not in LOG["insert"][0][1], "B11 Payout-Felder nur bei Funded CFD, Consistency nur wenn gewählt")
    check(post("finn", dict(basis, user_id=MARC, consistency_pct=150)).status_code == 400, "B12 Consistency > 100 → 400")

    # (C) Doppel
    r = post("finn", dict(basis, user_id=MARC, external_id="PAAPEX6850100000001", name="150k PAAPEX6850100000001 → Funded"))
    check(r.status_code == 409 and "150k PAAPEX6850100000001" in r.get_json()["msg"] and not LOG["insert"], "C1 Apex-Form gleich → 409 mit Kontoname")
    r = post("finn", dict(basis, user_id=MARC, external_id="tdfysl-50000000777"))
    check(r.status_code == 409 and "archiviert" in r.get_json()["msg"], "C2 Name enthält die Nummer (archiviertes Konto) → 409")
    check(post("finn", dict(basis, user_id=AMIR, external_id="PAAPEX6850100000001")).status_code == 200, "C3 gleiche Nummer bei anderer ID → kein Doppel")
    check(ns["admin_konto_ext_norm"]("APEX-12-3") == "APEX120000003" and ns["admin_konto_ext_norm"](" pa-apex-685010-01 ") == "PAAPEX6850100000001",
          "C4 Normierung wie extIdNorm")

    # (D) tv_konten + Kauf
    TV["fehlt"] = True
    d = post("finn", dict(basis, user_id=MARC, purchase_cost=89)).get_json()
    check(d["ok"] and d["markiert"] is False and d["hinweis"] == "", "D1 tv_konten fehlt → angelegt, nicht markiert, kein Hinweis")
    tx = [b for t, b in LOG["insert"] if t == "transactions"]
    check(len(tx) == 1 and tx[0]["amount"] == -89.0 and tx[0]["user_id"] == MARC and tx[0]["kind"] == "account_purchase" and tx[0]["account_id"] == "neu-1",
          "D2 Kaufpreis → Kauf-Transaktion für Marc (−89 EUR)")
    TV["fehlt"] = False
    d = post("finn", dict(basis, user_id=MARC)).get_json()
    up = LOG["update"][0] if LOG["update"] else (None, {}, {})
    check(d["markiert"] is True and up[0] == "tv_konten" and up[1] == {"user_id": f"eq.{MARC}", "name": "eq.TDFYSL100000000123", "angelegt_account_id": "is.null"}
          and up[2] == {"angelegt_account_id": "neu-1"}, "D3 tv_konten da → angelegt_account_id gesetzt (Guard is.null)")
    d = post("finn", dict(basis, user_id=MARC, external_id="TDFYSL100000000124")).get_json()
    check(d["ok"] and d["markiert"] is False and not LOG["update"] and "weicht ab" in d["hinweis"], "D5 External ID im Modal geändert → TV-Zeile nicht markiert, Hinweis")
    TV["cons_fehlt"] = True
    d = post("finn", dict(basis, user_id=MARC, consistency_pct=40)).get_json()
    acc_ins = [b for t, b in LOG["insert"] if t == "accounts"]
    check(d["ok"] and len(acc_ins) == 2 and "consistency_pct" not in acc_ins[1] and "Consistency" in d["hinweis"], "D6 Spalte consistency_pct fehlt → ohne Feld nochmal, Hinweis")
    TV["cons_fehlt"] = False
    check(cl.get("/admin/konto-anlegen").status_code == 405, "D4 nur POST")

    print(f"\n{'ALLES GRÜN' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
