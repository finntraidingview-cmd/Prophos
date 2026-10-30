#!/usr/bin/env python3
"""Selbsttest: POLAR-SLAVE-RIEGEL (30.10.2026, Bauplan S8) — /richtung/frei im Konto-Modus {polar_lauf, seite: slave, richtung}. Ohne Netz:
Code-Token, Supabase und RPC ersetzt. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_polar_slave_riegel.py"""
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


LID, PID, AID = "11111111-aaaa-bbbb-cccc-000000000001", "22222222-aaaa-bbbb-cccc-000000000002", "33333333-aaaa-bbbb-cccc-000000000003"
SU, MU = "44444444-aaaa-bbbb-cccc-000000000004", "55555555-aaaa-bbbb-cccc-000000000005"
LAUF = {"id": LID, "plan_id": PID, "slave_user_id": SU, "slave": {"auftrag": {"account_id": AID, "richtung": "sell", "firm": "Fusion Markets"}}}
KONTO = {"id": AID, "user_id": SU, "firm": "The5%ers"}
U = app.polar_slave_riegel_urteil
print("1) Urteil (rein)")
a, st, _ = U(LAUF, SU, "sell", KONTO)
check(a == (SU, "The5%ers", "sell", PID, AID), f"passt → Prüfung Slave-ID × Slave-Firma, ohne Plan/Konto des Laufs ({a})")
check(U(LAUF, MU, "sell", KONTO)[1] == 403, "andere ID (z. B. Master) fragt → 403")
check(U(LAUF, SU, "buy", KONTO)[2].get("code") == "gegenrichtung", "Richtung ≠ Lauf → nicht frei")
check(U(LAUF, SU, "sell", dict(KONTO, user_id=MU))[1] == 400, "Konto gehört nicht der Slave-ID → 400")
check(U(None, SU, "sell", KONTO)[1] == 400, "Lauf unbekannt → 400")

print("2) Route")
app._code_stand_sha = lambda: "abc"
app._code_zugang = lambda: (SU, "pc-slave")
DB = {"lauf": dict(LAUF), "konto": dict(KONTO), "rpc": {"frei": True}, "rpc_code": 200, "rpc_args": None}
app.sb_select = lambda t, p: [DB["lauf"]] if t == "polar_lauf" and DB["lauf"] else ([DB["konto"]] if t == "accounts" else [])


class Antw:
    def __init__(self, code, d):
        self.status_code, self._d, self.text = code, d, ""

    def json(self):
        return self._d


def rpc(m, url, **k):
    DB["rpc_args"] = (url.rsplit("/", 1)[-1], k.get("json"))
    return Antw(DB["rpc_code"], DB["rpc"])


app._sb_anfrage = rpc
cl = app.app.test_client()
d = cl.post("/richtung/frei", json={"polar_lauf": LID, "seite": "slave", "richtung": "sell"}).get_json()
check(d.get("ok") and d.get("frei") is True and DB["rpc_args"][0] == "prophos_gegenrichtung_frei_konto"
      and DB["rpc_args"][1] == {"p_user": SU, "p_firma": "The5%ers", "p_richtung": "sell", "p_ausser_plan": PID, "p_ausser_konto": AID},
      f"frei: richtige DB-Funktion mit Slave-ID × Firma ({DB['rpc_args']})")
DB["rpc"] = {"frei": False, "grund": "Long läuft auf …0002"}
d = cl.post("/richtung/frei", json={"polar_lauf": LID, "seite": "slave", "richtung": "sell"}).get_json()
check(d.get("ok") and d.get("frei") is False and d.get("code") == "gegenrichtung", "Gegenrichtung → nicht frei, code gegenrichtung")
DB["rpc_code"] = 500
r = cl.post("/richtung/frei", json={"polar_lauf": LID, "seite": "slave", "richtung": "sell"})
check(r.status_code == 503, "DB-Fehler → 503 (Panel fail-closed)")
DB["rpc_code"], DB["lauf"] = 200, None
r = cl.post("/richtung/frei", json={"polar_lauf": LID, "seite": "slave", "richtung": "sell"})
check(r.status_code == 400, "Lauf nicht gefunden → 400")
r = cl.post("/richtung/frei", json={"polar_lauf": "kaputt", "seite": "slave", "richtung": "sell"})
check(r.status_code == 400, "keine UUID → 400")
r = cl.post("/richtung/frei", json={"seite": "slave", "richtung": "sell"})
check(r.status_code == 400, "seite slave ohne polar_lauf → 400 (nie still in den alten Modus)")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
