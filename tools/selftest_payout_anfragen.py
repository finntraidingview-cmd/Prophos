#!/usr/bin/env python3
"""Selbsttest: POST /admin/payout-anfragen (31.10.2026, Admin → Payouts). Anfrage geht auf die ID des Kontos, keine doppelte, ohne Recht 403, keine Buchung.
Ohne Netz: Auth und Supabase-Aufrufe ersetzt. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_payout_anfragen.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


print("1) payout_anfrage_konto_felder (rein)")
F = app.payout_anfrage_konto_felder
MANUELL = {"goal_done_offset": 0, "goal_manual_last": None, "goal_kind": "winning_days", "goal_manual": True}
check(F({"account_type": "winning_days", "firm": "Tradeify", "goal_target": 5}, None, "M") == dict(MANUELL, goal_target=5), "Futures-WD: Stand 0, Haken weg")
check(F({"account_type": "funded", "firm": "Apex Trader"}, None, "M") == dict(MANUELL, goal_target=5), "Futures-Funded implizit Ziel 5")
check(F({"account_type": "funded_cfd", "firm": "FTMO", "goal_kind": "winning_days", "goal_target": 3}, None, "M") == {"goal_since": "M"}, "automatisch gezählt: goal_since morgen")
check(F({"account_type": "funded_cfd", "firm": "FTMO", "goal_kind": "trading_days", "goal_target": 4}, None, "M") == {}, "Trading Days bleiben")
check(F({"account_type": "funded_cfd", "firm": "Tradeify CFD"}, None, "M") == {}, "Tradeify CFD ist nicht Futures")
check(F({"account_type": "funded_cfd", "firm": "FTMO", "payout_ready_at": "2026-10-30"}, None, "M") == {"payout_ready_at": None}, "ohne Termin: stehender wird geleert")
check(F({"account_type": "funded_cfd", "firm": "FTMO", "payout_ready_at": "2026-10-30"}, "2026-11-13", "M") == {"payout_ready_at": "2026-11-13"}, "mit Termin: gesetzt")
check(F({"account_type": "funded_cfd", "firm": "FTMO", "waiting_payout_since": "2026-10-25"}, None, "M") == {"waiting_payout_since": None}, "Waiting geleert")

print("2) Route")
AID, OWN, ADMIN = "aaaaaaaa-1111-2222-3333-444444444444", "u-besitzer", "u-admin"
S = {}


def reset():
    S.update(offen=[], inserts=[], updates=[], insert_fehler=False, konto_fehler=False, aussen=set(),
             konto={"id": AID, "user_id": OWN, "name": "150k TDFY0431 → Winning Days", "firm": "Tradeify", "account_type": "winning_days", "goal_target": 5, "payout_ready_at": "2026-10-30"})


def sel(t, p):
    if t == "accounts":
        return [dict(S["konto"])] if p.get("id") == f"eq.{AID}" else []
    if t == "pending_payouts":
        assert p.get("status") == "eq.pending" and p.get("account_id") == f"eq.{AID}"
        return list(S["offen"])
    raise AssertionError("unerwartet gelesen: " + t)


def ins(t, b):
    S["inserts"].append((t, dict(b)))
    if S["insert_fehler"]:
        raise RuntimeError("kaputt")
    return dict(b, id="p-1", status="pending")


def upd(t, p, b):
    S["updates"].append((t, dict(p), dict(b)))
    if S["konto_fehler"]:
        raise RuntimeError("Spalte gesperrt")
    return [dict(S["konto"], **b)]


app.sb_select, app.sb_insert, app.sb_update = sel, ins, upd
app._admin_standard_aus = lambda: S["aussen"]
app._admin_voll = lambda: (ADMIN, None)
cl = app.app.test_client()
OK = {"account_id": AID, "amount": 4050, "currency": "USD", "liegt_bei": "Pascal", "requested_at": "2026-10-31"}


def post(**ueber):
    return cl.post("/admin/payout-anfragen", json=dict(OK, **ueber))


reset()
r = post(user_id="u-fremd")
d = r.get_json()
check(r.status_code == 200 and d.get("ok"), "angelegt")
t, zeile = S["inserts"][0]
check(t == "pending_payouts" and len(S["inserts"]) == 1, "nur pending_payouts, keine Buchung in transactions")
check(zeile["user_id"] == OWN, "ID des Kontos, nicht Admin und nicht user_id aus dem Body")
check(zeile["amount"] == 4050 and zeile["currency"] == "USD" and zeile["liegt_bei"] == "Pascal" and zeile["requested_at"] == "2026-10-31", "Betrag, Währung, liegt bei, Datum")
check(zeile["account_id"] == AID and zeile["account_name"].startswith("150k") and zeile["account_firm"] == "Tradeify", "Konto-Felder wie der Login")
check("status" not in zeile, "status bleibt beim Tabellen-Standard pending")
kt, kp, kb = S["updates"][0]
check(kt == "accounts" and kp["user_id"] == f"eq.{OWN}" and kb["goal_done_offset"] == 0 and kb["payout_ready_at"] is None, "Konto wie der Login: Zähler 0, Termin geleert, Guard Besitzer")
check(d["zaehler_neu"] is True and d["balance_lesen"] is False, "Antwort: Zähler neu, Futures ohne Balance-Lesung")

reset()
S["offen"] = [{"id": "x", "amount": 100, "currency": "USD", "requested_at": "2026-10-20"}]
r = post()
check(r.status_code == 409 and not S["inserts"] and not S["updates"], "offene Anfrage auf dem Konto → 409, nichts geschrieben")

reset()
for ueber, text in (({"amount": 0}, "Betrag 0"), ({"amount": -5}, "Betrag negativ"), ({"amount": None}, "ohne Betrag"), ({"currency": "CHF"}, "falsche Währung"), ({"requested_at": "31.10."}, "falsches Datum"), ({"naechster_payout": "x"}, "falscher Termin"), ({"account_id": "kaputt"}, "falsche Konto-ID")):
    r = post(**ueber)
    check(r.status_code == 400 and not S["inserts"], f"{text} → 400")

reset()
S["aussen"] = {OWN}
r = post()
check(r.status_code == 403 and not S["inserts"], "voller Admin, ID in Gruppe mit Verwalter → 403")

reset()
S["insert_fehler"] = True
r = post()
check(r.status_code == 502 and not S["updates"], "Insert scheitert → 502, Konto unangetastet")

reset()
S["konto_fehler"] = True
r = post()
check(r.status_code == 200 and r.get_json()["konto_fehler"], "Konto-Schritt scheitert → Anfrage steht, Fehler in der Antwort")

print("3) Rechte ohne vollen Admin")
reset()
with app.app.test_request_context():
    verboten = (app.jsonify({"error": "Kein Zugang"}), 403)
app._admin_voll = lambda: (None, verboten)
app._wd_login = lambda: ("u-mitglied", None)
app._admin_verwalter = lambda: False
r = post()
check(r.status_code == 403 and not S["inserts"], "normale ID → 403, nichts geschrieben")

app._admin_verwalter = lambda: True
orig = app.g
class G:
    admin_sicht = frozenset({"u-andere"})
app.g = G()
r = post()
check(r.status_code == 403 and not S["inserts"], "Verwalter, Konto außerhalb seiner Gruppe → 403")
G.admin_sicht = frozenset({OWN})
r = post()
check(r.status_code == 200 and S["inserts"][0][1]["user_id"] == OWN, "Verwalter, Konto seiner Gruppe → angelegt auf die ID des Kontos")
app.g = orig

print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER: {FEHLER}")
sys.exit(1 if FEHLER else 0)
