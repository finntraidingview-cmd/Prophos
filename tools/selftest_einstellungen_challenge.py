#!/usr/bin/env python3
"""Selbsttest EINSTELLUNGEN CHALLENGE-PLANER (04.11.2026, Auftrag E3): GET /admin/auto-plan/einstellungen (nur lesen) und POST
/admin/auto-plan/kernwert (nur vorhandene Felder, gleicher Typ, Grenzen, Admin). app.py importiert, DB ersetzt. Ohne Netz.
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_einstellungen_challenge.py"""
import json
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


FIRMEN = [
    {"namen": ["the5ers"], "route": "mt5v2", "boden": "statisch", "dd_pct": 10, "groessen": [100000, 200000], "kauf_eur": {"100000": 146, "200000": 226},
     "ziel_pct": {"phase1": 8, "phase2": 5}, "skaliert": True,
     "phasen": {"phase1": {"sl": [1800, 2160], "tp": [5400, 6300], "menge": [20, 30], "ziel_pct": 8, "menge_schritt": 1}},
     "je_groesse": {"200000": {"phasen": {"phase1": {"tp": [10800, 12600], "menge": [50, 60]}}}}},
    {"namen": ["topstep"], "route": "tsv2", "dd_usd": 4500, "planen": True, "kauf_eur": 237, "tp_max": 4500,
     "kette": {"t1_bis": "11:00", "t1_sl": [1250, 1750], "tagesziel_usd": 4500}, "phasen": {"challenge": {"sl": None, "tp": [4350, 4450]}}},
]
REG = {"id": 1, "aktiv": True, "updated_at": "2026-11-02T00:15:55+00:00",
       "zeiten": {"nachtlauf": {"tz": "Asia/Dubai", "uhr": "01:30"}, "cfd_ab": {"tz": "Asia/Dubai", "uhr": "02:15"}},
       "regeln": {"firmen": FIRMEN, "auto_bestaetigen": "cfd", "echo_hedge": {"an": True}, "apex_hedge": {"an": True},
                  "tradeify_final_hedge": {"an": False}, "ausgleich": {"aktiv": True, "takt_min": 3}}}

print("1) ap_einst_wert / ap_einst_anwenden (rein rechnend)")
W = app.ap_einst_wert
check(W(146, 150, "kauf_eur") == (150, None) and isinstance(W(146, 150, "kauf_eur")[0], int), "Zahl: ganze Zahl bleibt ganz")
check(W(0.1, 0.05, "menge_schritt") == (0.05, None), "Lot-Schritt 0,05")
check(W([5400, 6300], [5000, 6000], "tp") == ([5000, 6000], None), "Spanne [von, bis]")
check(W([5400, 6300], [7000, 6000], "tp")[0] is None, "von > bis → nie")
check(W([5400, 6300], 6000, "tp")[0] is None and W(146, [1, 2], "kauf_eur")[0] is None, "anderer Typ (Zahl ↔ Spanne) → nie")
check(W(8, 80, "ziel_pct")[0] is None and W(8, -1, "ziel_pct")[0] is None, "Ziel % außerhalb 0,1–50 → nie")
check(W(None, 5, "sl")[0] is None, "bisher null (kein SL) → nicht änderbar")
check(W(True, False, "planen") == (False, None) and W(True, 0, "planen")[0] is None, "Schalter nur true/false")
check(W("statisch", "nachziehend", "boden")[0] is None and W(1, 2, "irgendwas")[0] is None, "unbekanntes Feld → nie")
check(W(146, True, "kauf_eur")[0] is None, "true ist keine Zahl")
A = app.ap_einst_anwenden
neu, g = A(FIRMEN, "the5ers", [{"pfad": ["je_groesse", "200000", "phasen", "phase1", "tp"], "wert": [11000, 12000]}])
check(g is None and neu[0]["je_groesse"]["200000"]["phasen"]["phase1"]["tp"] == [11000, 12000] and FIRMEN[0]["je_groesse"]["200000"]["phasen"]["phase1"]["tp"] == [10800, 12600],
      "tiefer Pfad je Größe geändert, Original unberührt")
neu, g = A(FIRMEN, "the5ers", [{"pfad": ["kauf_eur", "200000"], "wert": 230}, {"pfad": ["phasen", "phase1", "tp"], "wert": [1, "x"]}])
check(neu is None and "phase1/tp" in g, f"alles oder nichts: ein Fehler → nichts geändert ({g})")
check(A(FIRMEN, "the5ers", [{"pfad": ["phasen", "phase2", "tp"], "wert": [1, 2]}])[0] is None, "Pfad, den es nicht gibt → nie (keine neuen Schlüssel)")
check(A(FIRMEN, "the5ers", [{"pfad": ["route"], "wert": "tvv2"}])[0] is None and A(FIRMEN, "the5ers", [{"pfad": ["namen"], "wert": ["x"]}])[0] is None,
      "route / namen nie änderbar")
check(A(FIRMEN, "ftmo", [{"pfad": ["kauf_eur"], "wert": 1}])[0] is None, "unbekannte Firma → nie")
check(A(FIRMEN, "topstep", [{"pfad": ["kette", "t1_sl"], "wert": [1300, 1700]}])[0][1]["kette"]["t1_sl"] == [1300, 1700], "Topstep-Kette änderbar")
check(A(FIRMEN, "topstep", [{"pfad": ["kette", "t1_bis"], "wert": "12:00"}])[0] is None, "Uhrzeit-Text der Kette nicht änderbar")
neu, g = A(FIRMEN, "the5ers", [{"pfad": ["ziel_pct", "phase1"], "wert": 9}])
check(g is None and neu[0]["ziel_pct"]["phase1"] == 9, f"Ziel % je Phase (Zuordnung) speicherbar — S6-Review Befund 1 ({g})")
check(A(FIRMEN, "the5ers", [{"pfad": ["ziel_pct", "phase1"], "wert": 80}])[0] is None, "Ziel % je Phase mit Grenze 0,1–50")
check(A(FIRMEN, "the5ers", [{"pfad": ["phasen", "phase1", "menge"], "wert": [20.5, 30]}])[0] is None
      and A(FIRMEN, "the5ers", [{"pfad": ["phasen", "phase1", "menge"], "wert": [21, 31]}])[1] is None, "ganze Lots/Kontrakte bleiben ganz (20,5 nie, 21 ja)")
check(A(FIRMEN, "the5ers", [{"pfad": ["phasen", "phase1", "menge_schritt"], "wert": 0.5}])[0] is None, "Schritt 1 bleibt ganz")
check(W([2.1, 3.2], [2.2, 3.3], "menge")[1] is None, "Kommazahlen-Lots (CFD) bleiben frei")
check(W([5400, 6300], [0, 6300], "tp")[0] is None and W(4500, 0, "dd_usd")[0] is None, "TP / Drawdown nie 0")
check(A(FIRMEN, "the5ers", [])[0] is None and A(FIRMEN, "the5ers", [{"pfad": "kauf_eur", "wert": 1}])[0] is None, "leere Liste / Pfad kein Array → nie")

print("2) GET /admin/auto-plan/einstellungen")
app._ap_zugang = lambda admin_reiter=False: (True, "u", json.loads(json.dumps(REG)), None)
c = app.app.test_client()
r = c.get("/admin/auto-plan/einstellungen")
d = r.get_json()
check(r.status_code == 200 and d["ok"] and d["admin"] is True and len(d["firmen"]) == 2, "Antwort mit Firmen")
check(d["zeiten"]["nachtlauf"] == {"uhr": "01:30", "tz": "Asia/Dubai"} and d["zeiten"]["neu_bis"]["uhr"] == "16:00", "Nachtlauf aus der DB, Neue-Konten-Standard 16:00")
check(d["schalter"]["auto_bestaetigen"] == "cfd" and d["echo_hedge"]["an"] is True and d["tradeify_final_hedge"]["an"] is False, "Schalter + Hedge-Wege")
check(d["fest"]["futures"]["paar_extern_min"] == [2.0, 5.0] and d["fest"]["cfd"]["rest_min_usd"] == app.AP_REST_MIN_CFD, "Code-Konstanten wie im Planer")
check(r.headers.get("Cache-Control") == "no-store", "no-store")

print("3) POST /admin/auto-plan/kernwert")
gespeichert = []
app._planer_schreib_gate = lambda: None
app.sb_update = lambda t, f, b: gespeichert.append(b)
app._ap_kw_cache["x"] = (9e18, {})
r = c.post("/admin/auto-plan/kernwert", json={"firma": "the5ers", "aenderungen": [{"pfad": ["phasen", "phase1", "tp"], "wert": [5500, 6400]}]})
check(r.status_code == 200 and gespeichert and gespeichert[-1]["regeln"]["firmen"][0]["phasen"]["phase1"]["tp"] == [5500, 6400]
      and gespeichert[-1]["regeln"]["auto_bestaetigen"] == "cfd" and not app._ap_kw_cache, "gespeichert, Rest der Regeln unverändert, Kernwert-Cache geleert")
n = len(gespeichert)
r = c.post("/admin/auto-plan/kernwert", json={"firma": "the5ers", "aenderungen": [{"pfad": ["phasen", "phase1", "tp"], "wert": [6400, 5500]}]})
check(r.status_code == 400 and len(gespeichert) == n, "ungültig → 400, nichts geschrieben")
app._ap_zugang = lambda admin_reiter=False: (False, "u", json.loads(json.dumps(REG)), None)
r = c.post("/admin/auto-plan/kernwert", json={"firma": "the5ers", "aenderungen": [{"pfad": ["kauf_eur", "200000"], "wert": 230}]})
check(r.status_code == 403 and len(gespeichert) == n, "kein Admin → 403")
app._planer_schreib_gate = lambda: (app.jsonify({"ok": False}), 403)
r = c.post("/admin/auto-plan/kernwert", json={"firma": "the5ers", "aenderungen": [{"pfad": ["kauf_eur", "200000"], "wert": 230}]})
check(r.status_code == 403, "ohne Planer-Schreibrecht → 403")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
