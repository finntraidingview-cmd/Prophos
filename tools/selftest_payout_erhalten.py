#!/usr/bin/env python3
"""Selbsttest: PATCH /admin/payout-erhalten mit waiting_leeren (30.10.2026, Funded Planer → CFD, S3 b3a7b10b). Ohne Netz: Auth und
Supabase-Aufrufe ersetzt. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_payout_erhalten.py"""
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


print("1) payout_konto_felder (rein)")
F = app.payout_konto_felder
check(F(None, False) == {}, "ohne Termin, ohne Wunsch → Konto nicht anfassen")
check(F("2026-11-13", False) == {"payout_ready_at": "2026-11-13"}, "nur Termin")
check(F(None, True) == {"waiting_payout_since": None}, "nur Waiting leeren")
check(F("2026-11-13", True) == {"payout_ready_at": "2026-11-13", "waiting_payout_since": None}, "beides in einem Update")
check(F(None, "ja") == {}, "waiting_leeren muss genau true sein")

print("2) Route")
PID, AID, OWN = "aaaaaaaa-1111-2222-3333-444444444444", "acc-1", "u-besitzer"
STAND = {}


def reset(konto_fehler=False):
    STAND.update(pending={"id": PID, "user_id": OWN, "account_id": AID, "account_name": "100k 1 → Funded", "account_firm": "FundedNext",
                          "amount": 1200, "currency": "USD", "status": "pending", "requested_at": "2026-10-20"},
                 konto={"id": AID, "user_id": OWN, "payout_ready_at": "2026-10-20", "waiting_payout_since": "2026-10-25T00:00:00+00:00",
                        "account_type": "funded_cfd"},
                 konto_fehler=konto_fehler, updates=[])


def sel(t, p):
    return [dict(STAND["pending"])] if t == "pending_payouts" else []


def upd(t, p, body):
    STAND["updates"].append((t, dict(p), dict(body)))
    if t == "pending_payouts":
        if p.get("status") == "eq.pending" and STAND["pending"]["status"] != "pending":
            return []
        STAND["pending"].update(body)
        return [dict(STAND["pending"])]
    if t == "accounts":
        if STAND["konto_fehler"]:
            raise RuntimeError("Spalte gesperrt")
        if p.get("user_id") != f"eq.{STAND['konto']['user_id']}":
            return []
        STAND["konto"].update(body)
        return [dict(STAND["konto"])]
    return []


app.sb_select, app.sb_update = sel, upd
app.sb_insert = lambda t, b: dict(b, id="tx-1")
app._admin_voll = lambda: ("finn@x", None)
cl = app.app.test_client()

reset()
d = cl.patch("/admin/payout-erhalten", json={"pending_id": PID, "erhalten_am": "2026-10-30", "naechster_payout": "2026-11-13",
                                              "waiting_leeren": True}).get_json()
check(d.get("ok") and d.get("waiting_geleert") is True and STAND["konto"]["waiting_payout_since"] is None
      and STAND["konto"]["payout_ready_at"] == "2026-11-13", f"waiting_leeren: Waiting weg, nächster Termin gesetzt ({d.get('waiting_geleert')})")
reset()
d = cl.patch("/admin/payout-erhalten", json={"pending_id": PID, "erhalten_am": "2026-10-30"}).get_json()
check(d.get("ok") and d.get("waiting_geleert") is False and STAND["konto"]["waiting_payout_since"] and STAND["konto"]["payout_ready_at"] == "2026-10-20"
      and not [u for u in STAND["updates"] if u[0] == "accounts"], "ohne Wunsch: Konto unberührt wie bisher")
reset(konto_fehler=True)
d = cl.patch("/admin/payout-erhalten", json={"pending_id": PID, "waiting_leeren": True}).get_json()
check(d.get("ok") and d.get("waiting_geleert") is False and d.get("termin_fehler") and d.get("tx"), "Konto-Fehler → Buchung steht, waiting_geleert false")
reset()
STAND["konto"]["user_id"] = "jemand-anders"
d = cl.patch("/admin/payout-erhalten", json={"pending_id": PID, "waiting_leeren": True}).get_json()
check(d.get("ok") and d.get("waiting_geleert") is False and STAND["konto"]["waiting_payout_since"], "Konto gehört nicht dem Besitzer der Anfrage → nichts geändert")
reset()
app._admin_voll = lambda: (None, (app.jsonify({"error": "x"}), 403))
app._wd_login = lambda: ("u-verwalter", None)
app._admin_verwalter = lambda: True
app.g = type("G", (), {"admin_sicht": frozenset({"u-andere"})})()
r = cl.patch("/admin/payout-erhalten", json={"pending_id": PID, "waiting_leeren": True})
check(r.status_code == 403 and STAND["konto"]["waiting_payout_since"], "Verwalter fremder Gruppe → 403, nichts geändert")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
