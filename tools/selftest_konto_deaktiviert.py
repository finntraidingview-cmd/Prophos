#!/usr/bin/env python3
"""Selbsttest: KONTO DEAKTIVIERT (30.10.2026, Finn 14:2x). Deaktiviert = kein Vorschlag im Funded-CFD-Planer und Funded-Planer, Grund sichtbar; aktiviert = wie vorher; Haken auto_planer
bleibt unberührt; Spalte fehlt = niemand deaktiviert. Ohne Netz. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_konto_deaktiviert.py"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


print("1) Merker")
K = [{"id": "a", "auto_planer": True}, {"id": "b", "auto_planer": True}, {"id": "c", "auto_planer": False}]
app.ap_deaktiviert_anwenden(K, frozenset({"a"}))
check(K[0]["auto_planer"] is False and K[0]["deaktiviert"] and K[1]["auto_planer"] is True and "deaktiviert" not in K[1], "nur das deaktivierte Konto, nur im gelesenen Stand")
check("deaktiviert" not in K[2], "Haken aus ist nicht deaktiviert (eigener Grund)")


class R:
    text = 'column accounts.deaktiviert_at does not exist'


def fehlt(t, p):
    e = requests.exceptions.HTTPError("400")
    e.response = R()
    raise e


app._sb_all = fehlt
app._ap_deakt_merk.update(bis=0.0)
check(app._ap_deaktiviert_ids() == frozenset(), "Spalte fehlt → niemand deaktiviert")
app._ap_deakt_merk.update(bis=0.0)
app._sb_all = lambda t, p: (_ for _ in ()).throw(RuntimeError("DB weg"))
try:
    app._ap_deaktiviert_ids()
    fc = False
except RuntimeError:
    fc = True
check(fc, "anderer Lesefehler fliegt durch (Lauf bricht ab, plant nichts)")

print("2) Funded-CFD-Planer")
sql = open(os.path.join(WURZEL, "sql", "2026-10-30_funded_cfd_planer.sql"), encoding="utf-8").read()
FIRMEN = json.loads(re.search(r"'(\[\s*\{.*?\]\s*)'::jsonb", sql, re.S).group(1))
U = "11111111-1111-1111-1111-111111111111"
KONTEN = [{"id": "62b824a2", "user_id": U, "name": "200k 26710448 → Funded", "firm": "The5%ers", "account_type": "funded_cfd", "external_id": "L1", "auto_planer": True},
          {"id": "bbbbbbbb", "user_id": U, "name": "100k 26754186 → Funded", "firm": "The5%ers", "account_type": "funded_cfd", "external_id": "L2", "auto_planer": True}]
JETZT = datetime(2026, 11, 2, 4, 0, tzinfo=timezone.utc)
FRISCH = (JETZT - timedelta(minutes=30)).isoformat()
REG = {"id": 1, "aktiv": False, "auto_bestaetigen": False, "user_ids": [U], "firmen": FIRMEN, "zeiten": {"firma_abstand_min": 15, "abstand_id_min": 10, "vorlauf_min": 15}}
DEAKT = {"ids": ["62b824a2"]}


def sb_all(t, p):
    if t == "accounts" and p.get("deaktiviert_at"):
        return [{"id": i} for i in DEAKT["ids"]]
    if t == "accounts" and p.get("account_type") == "eq.funded_cfd":
        return [dict(a) for a in KONTEN]
    if t == "accounts":
        return [{"id": "f", "name": "Fusion", "firm": "Fusion Markets"}]
    if t == "user_settings":
        return [{"user_id": U, "value": {"accountId": "f"}}]
    if t == "firm_specs":
        return [{"user_id": U, "name": "The5%ers", "ppl": 1.0, "unit": "Lots"}]
    return []


app._sb_all = sb_all
app.sb_select = lambda t, p: [REG] if t == "funded_cfd_plan_regeln" else ([{"zeiten": {"fenster_tz": "Asia/Dubai", "fenster": [["04:00", "18:00"]]}}] if t == "auto_plan_regeln" else [])
app._ap_archiviert = lambda streng=False: set()
app._ap_namen = lambda: ({U: "Finn + Pascal"}, set())
app._ap_balance_karten = lambda: ({"L1": (200000.0, "USD", FRISCH), "L2": (100000.0, "USD", FRISCH)}, {})
app._fd_gruppen_ids = lambda: set()
app._ap_deakt_merk.update(bis=0.0)
e = app.fcp_planen(trocken=True, jetzt=JETZT, seed=1)
aus = {z["konto"]: z["grund"] for z in e["ausgelassen"]}
check([z["konto"] for z in e["geplant"]] == ["100k 26754186 → Funded"], f"deaktiviert = kein Vorschlag, das andere Konto schon ({[z['konto'] for z in e['geplant']]})")
check("deaktiviert" in aus.get("200k 26710448 → Funded", ""), f"Grund sichtbar ({aus})")
DEAKT["ids"] = []
app._ap_deakt_merk.update(bis=0.0)
e2 = app.fcp_planen(trocken=True, jetzt=JETZT, seed=1)
check(sorted(z["konto"] for z in e2["geplant"]) == ["100k 26754186 → Funded", "200k 26710448 → Funded"], "aktiviert = wie vorher")

print("3) Quelltext")
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
check(src.count("AP_GRUND_DEAKTIVIERT if a.get(\"deaktiviert\")") == 4, "Challenge-, Gruppen-, Funded- und CFD-Planer nennen den Grund")
check("ap_deaktiviert_anwenden(_ap_konten_lesen(params))" in src, "alle Wege über _ap_konten_laden (Nachplanen, Balance-Takt) sehen den Merker")
s = open(os.path.join(WURZEL, "sql", "2026-10-30_konto_deaktiviert.sql"), encoding="utf-8").read()
check("add column if not exists deaktiviert_at" in s and "return null" in s and "trade_plans_a00_konto_deaktiviert" in s, "SQL: Spalte + Halte-Trigger am Claim")
d = open(os.path.join(WURZEL, "sql", "2026-10-30_plan_520956b3_raus.sql"), encoding="utf-8").read()
check("id = '520956b3-2318-4d0d-b7e2-2c43b7e12b1e'" in d and "started_at is null" in d and "orbit_gesendet_at is null" in d, "Plan-Löschung eng begrenzt")
h = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("planKontoDeaktiviert(p)) return 'Konto deaktiviert'" in h and "deaktiviert_at: an ?" in h, "Frontend: Start-Sperre und Knopf")
print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
