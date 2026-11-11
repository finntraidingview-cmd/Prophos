#!/usr/bin/env python3
"""Selbsttest F-A/F-B Railway-Teil (Master 11.11.2026 nach FS2; Panel/Bot Slave 4 98c62e41/8e292a66, PC-Tab Slave 1 ddf655b1):
(1) /copier-Proxy gibt „vorflug“ 50 s statt 25 s (Panel liest bis 40 s), (2) die E1-Wache kk_tick nimmt rote Vorflüge (mt5_baseline.vorflug.{a|b})
als Treffer an — gleiche Regeln, Schwellen, Breite, Deckel; (3) /code/tab-stand liefert next_start_um (nur Pläne, die von selbst starten).
Ohne Netz, DB nachgebaut, Platzhalter-IDs. Aufruf: python3 tools/selftest_fab_railway.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

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


SRC = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
print("1) Proxy-Zeitlimit")
check(re.search(r'else 50 if path == "vorflug" else 25\)', SRC) is not None, "/copier: vorflug 50 s (≥ 45 s, Panel-Lese-Deckel 40 s), sonst 25 s wie bisher")

print("2) Vorflug-Treffer in der E1-Wache")
JETZT = datetime(2026, 11, 11, 6, 0, tzinfo=timezone.utc)
m = lambda x: (JETZT - timedelta(minutes=x)).isoformat()   # noqa: E731
J = "11111111-1111-1111-1111-111111111111"
KN, KB = "b0000000-0000-0000-0000-00000000000b", "b0000000-0000-0000-0000-00000000000c"
NUR = "Konto nimmt nur Schließen an (Server: Only position closing is allowed) — letzte Order im Journal abgelehnt: [Only position closing is allowed]"
PL = [{"id": "p1", "user_id": J, "master_name": "100k N → Funded", "master_firm": "FirmaN",
       "vf": {"a": {"at": m(22), "lesbar": True, "rot": True, "art": "nur_schliessen", "grund": NUR},
              "b": {"at": m(9), "lesbar": True, "rot": True, "art": "nur_schliessen", "grund": NUR}}},
      {"id": "p2", "user_id": J, "master_name": "100k B → Phase 1", "master_firm": "FirmaB",
       "vf": {"a": {"at": m(30), "lesbar": False, "rot": True, "grund": NUR}, "b": {"at": m(12), "rot": False, "art": "ok", "grund": ""}}},
      {"id": "p3", "user_id": J, "master_name": "x", "master_firm": "y", "vf": {"a": {"at": m(5000), "rot": True, "grund": NUR}}}]
z = app.kk_vorflug_zeilen(PL, m(72 * 60))
check([(r["plan_id"], r["quelle"]) for r in z] == [("p1", "vorflug"), ("p1", "vorflug")] and z[0]["msg"] == NUR and z[0]["konto"] == "100k N → Funded",
      "nur gelesene, rote Vorflüge mit Grund im Fenster (lesbar False / grün / zu alt fallen raus)")
check(app.kk_vorflug_zeilen([{"id": "q", "vf": "kaputt"}, {"id": "r"}], None) == [], "kaputte/fehlende Spur → nichts")
# VF1/H5 (11.11.2026): „getrennt“ ist kein Konto-Zustand — nie ein Treffer, auch mit einem Grund, den eine Regel treffen würde
_GT = {"at": m(9), "lesbar": True, "rot": True, "art": "getrennt", "grund": "Terminal nicht mit dem Server verbunden"}
check(app.kk_vorflug_zeilen([{"id": "g", "vf": {"a": _GT, "b": dict(_GT, grund=NUR)}}], m(72 * 60)) == [],
      "Vorflug „getrennt“ zählt nie (H5), auch nicht mit Regel-Text")
_ZT = [{"id": "z", "vf": {"a": {"at": m(9), "lesbar": True, "rot": True, "art": a, "grund": NUR}}} for a in ("konto_gesperrt", "nur_schliessen", "falsches_konto")]
check(len(app.kk_vorflug_zeilen(_ZT, m(72 * 60))) == 3, "gesperrt / nur schließen / falsches Konto bleiben Treffer-Zeilen")

# Prüfer F-A MUSS a: Journal-Vorflüge (dieselbe alte Ablehnung) zählen höchstens einmal je Tag, nie nach einem Fehlstart desselben Tags, anderer Login nie
F = app.kk_vorflug_filtern
fs = lambda at: {"at": at, "msg": "x", "quelle": None}                                                 # noqa: E731
vj = lambda at, lg=None: {"at": at, "msg": NUR, "quelle": "vorflug", "journal": True, "login": lg}    # noqa: E731
vs = lambda at: {"at": at, "msg": "Zustand", "quelle": "vorflug", "journal": False, "login": None}     # noqa: E731
check(len(F([vj(m(22)), vj(m(9))], None)) == 1, "zwei Journal-Vorflüge am selben Tag → ein Treffer")
check(len(F([fs(m(30)), vj(m(20)), vj(m(9))], None)) == 1, "Fehlstart am Tag davor → Journal-Vorflüge danach zählen nicht (keine Schleife nach dem Reaktivieren)")
check(len(F([vj(m(30)), fs(m(5))], None)) == 2, "Journal-Vorflug VOR dem ersten Fehlstart + Fehlstart = 2 Treffer (früher erkannt)")
check(len(F([vj(m(20), "999"), fs(m(5))], "123")) == 1 and len(F([vj(m(20), "123"), fs(m(5))], "123")) == 2, "Vorflug eines anderen Logins fällt weg")
check(len(F([vs(m(22)), vs(m(9))], None)) == 2, "Zustands-Vorflüge (kein Journal) zählen je Lesung")
# Prüfer Runde 2: UTC-Tagesgrenze — Fehlstart 10.11. 21:00Z (01:00 Dubai), Vorflüge 11.11. 05:00Z / 05:10Z → nur der Fehlstart zählt
U = lambda tx: {"at": tx, "msg": "x", "quelle": None}   # noqa: E731
check(len(F([U("2026-11-10T21:00:00Z"), vj("2026-11-11T05:00:00Z"), vj("2026-11-11T05:10:00Z")], None)) == 1,
      "Fehlstart kurz vor Mitternacht UTC + Journal-Vorflüge am Morgen → ein Treffer (24 h rollend)")
check(len(F([vj("2026-11-10T21:00:00Z"), vj("2026-11-11T05:00:00Z")], None)) == 1 and len(F([vj("2026-11-10T05:00:00Z"), vj("2026-11-11T06:00:00Z")], None)) == 2,
      "höchstens ein Journal-Vorflug je 24 h (rollend)")

KONTEN = [{"id": KN, "user_id": J, "name": "100k N → Funded", "firm": "FirmaN", "deaktiviert_at": None, "external_id": "123"},
          {"id": KB, "user_id": J, "name": "100k B → Phase 1", "firm": "FirmaB", "deaktiviert_at": None, "external_id": "456"}]
DB = {"upd": [], "alarm": [], "fehl": []}


def sb_select(t, p):
    if t == "puls_fehlstarts":
        stueck = p["msg"].replace("ilike.", "").strip("*").lower()
        return [dict(r) for r in DB["fehl"] if stueck in r["msg"].lower()]
    if t == "trade_plans" and "id" in p and str(p["id"]).startswith("in.("):
        return [{"id": x, "master_account_id": {"p1": KN, "p2": KB, "pf": KN}.get(x, "")} for x in p["id"][4:-1].split(",")]
    return []


def sb_all(t, p):
    if t == "accounts":
        return [dict(a) for a in KONTEN]
    if t == "trade_plans" and p.get("mt5_baseline->vorflug") == "not.is.null":
        return [dict(x) for x in PL]
    return []


app.sb_select = sb_select
app._sb_all = sb_all
app.sb_update = lambda t, f, u: DB["upd"].append((t, f, u)) or [dict(u)]
app._sb_anfrage = lambda *a, **k: None
app.alarm_senden = lambda *a, **k: DB["alarm"].append((a, k)) or (1, 1)
app.admin_gruppen_daten = lambda: {"gruppen": [{"id": "ht", "name": "Hermann Technologies", "verwalter_id": None}], "mitglieder": [{"user_id": J, "gruppe_id": "ht"}]}
app._ap_namen = lambda: ({J: "HT-1"}, set())
FEHLSTART = ("KEINE Bestaetigung binnen 12 s — Grund: Konto nimmt nur Schließen an (Server: Only position closing is allowed) (Journal: [Only position "
             "closing is allowed]) → Konto bei der Firma prüfen — nicht neu starten.")
e = app.kk_tick(JETZT)
check(not e["gesperrt"], f"nur zwei Journal-Vorflüge derselben alten Ablehnung → nicht gesperrt ({e['gesperrt']})")
PL[0]["vf"].pop("b")
DB["fehl"] = [{"at": m(5), "user_id": J, "plan_id": "pf", "konto": "100k N → Funded", "firma": "FirmaN", "msg": FEHLSTART, "pc": "pc-aaaa"}]
e = app.kk_tick(JETZT)
gesperrt = {g["konto_id"]: g["art"] for g in e["gesperrt"]}
check(gesperrt == {KN: "nur_schliessen"}, f"roter Journal-Vorflug (T−15) + Fehlstart 17 min später → gesperrt nach dem ERSTEN Fehlstart ({gesperrt})")
check(any(a[1] == "nur_schliessen" for a, k in DB["alarm"]), "⚪ wie ein Fehlstart-Treffer")
DB["fehl"] = []
e = app.kk_tick(JETZT)
check(not e["gesperrt"], "ein einzelner roter Vorflug sperrt nicht (Schwelle der Regel bleibt)")
app._sb_all = lambda t, p: (_ for _ in ()).throw(RuntimeError("weg")) if t == "trade_plans" else sb_all(t, p)
e = app.kk_tick(JETZT)
check("vorflug: RuntimeError" in (e.get("fehler_regeln") or []) and not e["gesperrt"], "Vorflüge nicht lesbar → Wache läuft wie bisher, Spur in fehler_regeln")
app._sb_all = sb_all

print("3) /code/tab-stand next_start_um")
T = lambda mm: (JETZT + timedelta(minutes=mm)).isoformat()   # noqa: E731
pl = [{"status": "planned", "start_um": T(3)}, {"status": "planned", "start_um": T(3)}, {"status": "planned", "start_um": T(8)},
      {"status": "planned", "start_um": T(12)}, {"status": "planned", "start_um": T(-1)}, {"status": "open", "start_um": T(2)},
      {"status": "planned", "start_um": T(4), "start_um_gestartet_at": T(0)}, {"status": "planned", "start_um": T(5), "auto_plan": True},
      {"status": "planned", "start_um": T(6), "auto_plan": True, "auto_bestaetigt_at": T(-60)}, {"status": "planned", "start_um": None}]
ns = app.tab_stand_next_starts(pl, JETZT)
check(ns == ["2026-11-11T06:03:00Z", "2026-11-11T06:06:00Z", "2026-11-11T06:08:00Z"],
      f"nur geplante, ungeclaimte, startbare Pläne in (jetzt, +10 min], doppelt einmal, aufsteigend, Z-Format ({ns})")
check("\"next_start_um\": tab_stand_next_starts(plaene, jetzt)" in SRC, "Route liefert next_start_um")
# VF1 (11.11.2026, offen aus 3814e641): auch eine Startzeit mit anderer Zone / Bruchteil kommt als UTC MIT Zone („Z“) raus
ns2 = app.tab_stand_next_starts([{"status": "planned", "start_um": "2026-11-11T10:04:30.25+04:00"}], JETZT)
check(ns2 == ["2026-11-11T06:04:30.250000Z"], f"Startzeit +04:00 mit Bruchteil → UTC mit „Z“ ({ns2})")
# Panel-Leser (8e292a66 tab_vorflug_starts) liest ISO-Liste
check(all(datetime.fromisoformat(x.replace("Z", "+00:00")).tzinfo for x in ns), "Format passt zu panel.tab_vorflug_starts (fromisoformat nach Z → +00:00)")

print()
print("FEHLER: " + ", ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
