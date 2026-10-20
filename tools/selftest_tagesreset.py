#!/usr/bin/env python3
"""Selbsttest TAGES-RESET LIEGENGEBLIEBENER PLÄNE (21.10.2026, Finn 20.10.2026 ~23:50 Dubai: „Das soll immer daily resetten, also wenn ein
Trade gemacht wurde oder geplant wurde und er nicht durchläuft, wird er am Tagesende resetet.").
Aufruf:  python3 tools/selftest_tagesreset.py
Prüft tagesreset_art/tagesreset_hinweis (app.py, aus dem Quelltext) an den zehn liegengebliebenen Plänen vom 20.10.2026 (Prüfstand des
Masters, Werte wie in der DB, Logins/PCs durch Platzhalter ersetzt) + Chris' Plan d1c5980f + gezielten Unsicher-Fällen; dazu ap_tagesreset
gegen eine nachgebaute DB: löschen nur mit Guard, „Überprüfen" mit Grund am toten Tag, Fehler halten den Lauf nicht auf; Einhängen VOR
ap_planen im Nachtlauf. Ohne Netz."""
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(name):
    i = SRC.index(f"\ndef {name}(") + 1
    return SRC[i:SRC.find("\n\n\n", i)]


ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone, "_ap_tz": ZoneInfo}
for zeile in ("TR_FILL_FELDER", "TR_GRUND"):
    m = re.search(r"^" + zeile + r" = .*?(?=\n\S)", SRC, re.M | re.S)
    exec(m.group(0), ns)
for name in ("_ap_ts", "tagesreset_tag", "tagesreset_hinweis", "tagesreset_art", "ap_tagesreset"):
    exec(fn(name), ns)
ART = ns["tagesreset_art"]
TZ = ZoneInfo("Asia/Dubai")
JETZT = datetime(2026, 10, 20, 21, 0, tzinfo=timezone.utc)     # Nachtlauf 01:00 Dubai am 21.10.
TAG = "2026-10-21"


def sf(at, schritt, unklar=False, status="tagesende", versuche=0):
    return {"at": at, "pc": "pc-x", "msg": "…", "login": "LOGIN", "status": status, "unklar": unklar, "schritt": schritt, "versuche": versuche}


# Die zehn vom 20.10.2026 (planned, planned_for < 21.10., started_at leer) — Ina/Pascal: Tab lief nicht, Claim nur für „zu_spaet";
# Mike: Terminal-Verbindung scheiterte (IPC timeout, retry_ok → unklar false); Marc: nie geclaimt; Moritz: Handplan vom 02.10. ohne Start
ZEHN = {
    "24d06afc": ({"route": "tvv2", "auto_plan": False, "planned_for": "2026-10-02", "start_um": None, "start_um_gestartet_at": None, "mt5_baseline": None}, "weg"),
    "2269bb01": ({"route": "tvv2", "auto_plan": True, "planned_for": "2026-10-19", "start_um": "2026-10-19 02:43:37+00", "start_um_gestartet_at": "2026-10-19 19:12:54.413+00",
                  "mt5_baseline": {"start_fehler": sf("2026-10-19T19:12:54.590Z", "zu_spaet")}}, "weg"),
    "a5d99d78": ({"route": "tvv2", "auto_plan": True, "planned_for": "2026-10-19", "start_um": "2026-10-19 03:16:00+00", "start_um_gestartet_at": "2026-10-19 17:03:03.483+00",
                  "mt5_baseline": {"start_fehler": sf("2026-10-19T17:03:03.705Z", "zu_spaet")}}, "weg"),
    "5d7b762c": ({"route": "mt5v2", "auto_plan": True, "planned_for": "2026-10-19", "start_um": "2026-10-19 03:25:07.2+00", "start_um_gestartet_at": "2026-10-19 03:25:09.846+00",
                  "mt5_baseline": {"puls_spur": {"ok": False, "msg": "Terminal-Verbindung fehlgeschlagen: IPC timeout"}, "v2_vorher": {"snap": True, "idents": []},
                                   "start_fehler": sf("2026-10-19T03:27:50.707Z", "v2order", status="rot", versuche=3)}}, "weg"),
    "c015b269": ({"route": "mt5v2", "auto_plan": True, "planned_for": "2026-10-19", "start_um": "2026-10-19 03:35:34.8+00", "start_um_gestartet_at": "2026-10-19 03:35:37.808+00",
                  "mt5_baseline": {"puls_spur": {"ok": False}, "v2_vorher": {"snap": True, "idents": []},
                                   "start_fehler": sf("2026-10-19T03:38:29.601Z", "v2order", status="rot", versuche=3)}}, "weg"),
    "24ea32bf": ({"route": "mt5v2", "auto_plan": True, "planned_for": "2026-10-19", "start_um": "2026-10-19 04:46:00+00", "start_um_gestartet_at": "2026-10-19 19:12:55.172+00",
                  "mt5_baseline": {"start_fehler": sf("2026-10-19T19:12:55.327Z", "zu_spaet")}}, "weg"),
    "f7cb8395": ({"route": "mt5v2", "auto_plan": True, "planned_for": "2026-10-19", "start_um": "2026-10-19 05:41:00+00", "start_um_gestartet_at": "2026-10-19 19:12:56.125+00",
                  "mt5_baseline": {"start_fehler": sf("2026-10-19T19:12:56.275Z", "zu_spaet")}}, "weg"),
    "9969b6b6": ({"route": "mt5v2", "auto_plan": True, "planned_for": "2026-10-19", "start_um": "2026-10-19 07:02:00+00", "start_um_gestartet_at": "2026-10-19 19:12:57.17+00",
                  "mt5_baseline": {"start_fehler": sf("2026-10-19T19:12:57.336Z", "zu_spaet")}}, "weg"),
    "8504982a": ({"route": "tvv2", "auto_plan": True, "planned_for": "2026-10-19", "start_um": "2026-10-19 12:35:00+00", "start_um_gestartet_at": "2026-10-19 19:12:58.216+00",
                  "mt5_baseline": {"start_fehler": sf("2026-10-19T19:12:58.379Z", "zu_spaet")}}, "weg"),
    "fe1c95ea": ({"route": "mt5v2", "auto_plan": True, "planned_for": "2026-10-19", "start_um": "2026-10-19 18:16:05.663+00", "start_um_gestartet_at": None,
                  "mt5_baseline": {"start_fehler": {"hand": True, "status": "neu", "versuche": 1}, "start_sperre": {"art": "richtung", "versuche": 78},
                                   "richtung_konflikt": {"status": "aufgegeben", "versuche": 5}}}, "weg"),
}
for pid, (p, soll) in ZEHN.items():
    e = ART(dict(p, id=pid, status="planned", started_at=None), TAG, JETZT, TZ)
    check(e["art"] == soll, f"{pid}: {soll} — {e['grund']}")

# Chris d1c5980f (vom Master schon per SQL gelöscht): geclaimt, Puls gab mit „konto_weg" auf, kein Fill → weg
CHRIS = {"id": "d1c5980f", "status": "planned", "started_at": None, "route": "tvv2", "planned_for": "2026-10-19", "start_um": "2026-10-19T12:09:40+00:00",
         "start_um_gestartet_at": "2026-10-19T12:10:54.203+00:00", "notes": "Winning-Day-Farmer",
         "mt5_baseline": {"final": {"at": "2026-10-19T12:12:43.890Z", "grund": "konto_weg", "konto_weg": True, "puls_aufgegeben": True,
                                    "puls_fehler": "konto_weg: Konto bei Tradovate nicht mehr vorhanden"}}}
e = ART(CHRIS, TAG, JETZT, TZ)
check(e["art"] == "weg" and "konto_weg" in e["grund"], f"Chris d1c5980f: Puls gab vor dem Kauf auf → weg — {e['grund']}")

# UNSICHER → pruefen (nie löschen)
BASIS = {"id": "x", "status": "planned", "started_at": None, "route": "tvv2", "planned_for": "2026-10-19", "start_um": "2026-10-19T10:00:00+00:00",
         "start_um_gestartet_at": "2026-10-19T10:00:02+00:00", "orbit_gesendet_at": None}
FAELLE = [
    ("geclaimt, nichts am Plan", {}, "pruefen", "kein Ergebnis"),
    ("Start-Fehler unklar (Klick kann raus sein)", {"mt5_baseline": {"start_fehler": sf("2026-10-19T10:01:00Z", "knopf", unklar=True)}}, "pruefen", "unklar"),
    ("Start-Fehler schritt unklar", {"mt5_baseline": {"start_fehler": sf("2026-10-19T10:01:00Z", "unklar", unklar=None)}}, "pruefen", "unklar"),
    ("Puls-Unklar-Marke", {"mt5_baseline": {"puls_unklar": {"code": "unklar"}, "start_fehler": sf("2026-10-19T10:01:00Z", "ticket")}}, "pruefen", "unklar"),
    ("Start-Fehler älter als der Claim (neuer Versuch ohne Ergebnis)", {"mt5_baseline": {"start_fehler": sf("2026-10-19T09:00:00Z", "konto")}}, "pruefen", "kein Ergebnis"),
    ("Start-Fehler ohne unklar-Feld (altes Format)", {"mt5_baseline": {"start_fehler": {"at": "2026-10-19T10:01:00Z", "schritt": "puls"}}}, "pruefen", "kein Ergebnis"),
    ("TradingView-Spur mit Einstieg", {"mt5_baseline": {"tv": {"einstieg_nq": 29757, "klick_at": "2026-10-19T10:00:20Z"}}}, "pruefen", "TradingView"),
    ("an Orbit gesendet", {"orbit_gesendet_at": "2026-10-19T10:00:05+00:00"}, "pruefen", "Orbit"),
    ("Fusion-Hedge", {"mt5_baseline": {"hedge": {"status": "offen"}}}, "pruefen", "Hedge"),
    ("Echo-Ticket", {"route": "mt5v2", "mt5_baseline": {"ticket": 123}}, "pruefen", "Ticket"),
    ("Polar mit Lauf-Zeile", {"route": "polar", "polar_lauf": [{"id": "l1", "status": "bereit"}], "mt5_baseline": {"polar_auftrag": {"lots": 1}}}, "pruefen", "Polar"),
    ("Polar mit Abrechnung", {"route": "polar", "start_um_gestartet_at": None, "mt5_baseline": {"polar": {"status": "fertig"}}}, "pruefen", "Polar"),
    ("Puls-Pause (Trade evtl. von Hand)", {"start_um_gestartet_at": None, "mt5_baseline": {"puls_pause": "Polar von Hand"}}, "pruefen", "Pause"),
    ("Ende mit Fill trotz Aufgabe", {"mt5_baseline": {"final": {"puls_aufgegeben": True, "today_pnl": -310.5}}}, "pruefen", "Fill"),
    ("Ende ohne Aufgabe", {"mt5_baseline": {"final": {"grund": "demo_liq"}}}, "pruefen", "Ende-Eintrag"),
]
for name, extra, soll, wort in FAELLE:
    p = dict(BASIS, **{k: v for k, v in extra.items()})
    e = ART(p, TAG, JETZT, TZ)
    check(e["art"] == soll and wort.lower() in e["grund"].lower(), f"{name}: {soll} — {e['grund']}")

# NICHT BETROFFEN → None
NICHT = [
    ("heutiger Plan", {"planned_for": "2026-10-21", "start_um": "2026-10-21T08:00:00+00:00", "start_um_gestartet_at": None}),
    ("schon gestartet", {"started_at": "2026-10-19T10:00:30+00:00"}),
    ("läuft (open)", {"status": "open"}),
    ("Claim < 2 h her (wird gerade platziert)", {"start_um": "2026-10-20T17:00:00+00:00", "start_um_gestartet_at": "2026-10-20T20:10:00+00:00"}),
    ("Start < 2 h her", {"start_um": "2026-10-20T19:30:00+00:00", "start_um_gestartet_at": None}),
    ("ohne Datum und ohne Start", {"planned_for": None, "start_um": None}),
]
# S2-Prüfung 21.10.2026, Finns Testplan 009fc61b: Polar gespeichert (nur polar_auftrag, kein Claim, kein start_um) → bleibt stehen, nie „Order prüfen"
NICHT.append(("Polar nur gespeichert (polar_auftrag, kein Lauf)", {"route": "polar", "planned_for": "2026-10-20", "start_um": None, "start_um_gestartet_at": None,
                                                                  "polar_lauf": [], "mt5_baseline": {"polar_auftrag": {"lots": 1.2, "sl_pkt": 80, "tp_pkt": 120, "kontrakte": 3}}}))
for name, extra in NICHT:
    e = ART(dict(BASIS, **extra), TAG, JETZT, TZ)
    check(e["art"] is None, f"{name}: nicht betroffen — {e['grund']}")
e = ART(dict(BASIS, planned_for=None, start_um="2026-10-20T19:59:00+00:00", start_um_gestartet_at=None), TAG, datetime(2026, 10, 20, 22, 30, tzinfo=timezone.utc), TZ)
check(e["art"] == "weg", f"ohne planned_for: Tag aus start_um in Dubai (20.10. 23:59) < 21.10. → weg — {e['grund']}")

# ap_tagesreset gegen nachgebaute DB
DB = {"geloescht": [], "update": [], "rpc": [], "delete_params": [], "update_params": []}
ROWS = [dict(ZEHN["24d06afc"][0], id="24d06afc-0000", status="planned", started_at=None, orbit_gesendet_at=None, master_name="Konto A", result_notes=None),
        dict(BASIS, id="pruef-0001", master_name="Konto B", result_notes="alt", mt5_baseline={"puls_unklar": {"code": "unklar"}, "final": {"puls_versuche": 1}}),
        dict(BASIS, id="heute-0002", planned_for="2026-10-21", start_um="2026-10-21T08:00:00+00:00", start_um_gestartet_at=None, master_name="Konto C"),
        dict(CHRIS, id="kaputt-0003", master_name="Konto D"),
        # S2-Prüfung 21.10.2026: an Orbit gesendet → pruefen; das Update darf NICHT am Guard „orbit_gesendet_at is.null" scheitern
        dict(BASIS, id="orbit-0004", orbit_gesendet_at="2026-10-19T10:00:05+00:00", master_name="Konto E", result_notes=None, mt5_baseline=None),
        # zwischen Lesen und Schreiben neu geclaimt (Claim jetzt frisch) → Guard greift, nichts passiert
        dict(BASIS, id="frisch-0005", master_name="Konto F", result_notes=None, mt5_baseline=None, _claim_neu="2026-10-20T20:55:00+00:00")]


def passt(row, params):
    """wertet den PostgREST-Guard gegen die Zeile aus (eq/is.null und das or für den Claim)"""
    for k, v in params.items():
        if k == "id":
            if v != "eq." + row["id"]:
                return False
        elif k == "or":
            m = re.match(r"\(start_um_gestartet_at\.is\.null,start_um_gestartet_at\.lt\.(.+)\)$", v)
            c = ns["_ap_ts"](row.get("_claim_neu") or row.get("start_um_gestartet_at"))
            if not m or not (c is None or c < ns["_ap_ts"](m.group(1))):
                return False
        elif v == "is.null":
            if row.get(k) is not None:
                return False
        elif v.startswith("eq."):
            if str(row.get(k)) != v[3:]:
                return False
        else:
            return False
    return True


class Antwort:
    def json(self):
        return []


def _sb_all(table, params):
    return [r for r in ROWS if (params.get("planned_for") == "is.null") == (r.get("planned_for") is None)]


def sb_delete(table, params):
    DB["delete_params"].append(params)
    if params["id"] == "eq.kaputt-0003":
        raise RuntimeError("Netz weg")
    treffer = [r for r in ROWS if passt(r, params)]
    DB["geloescht"] += [r["id"] for r in treffer]
    return [{"id": r["id"]} for r in treffer]


def sb_update(table, params, body):
    DB["update_params"].append(params)
    treffer = [r for r in ROWS if passt(r, params)]
    DB["update"] += [(r["id"], body) for r in treffer]
    return [{"id": r["id"]} for r in treffer]


def _sb_anfrage(meth, url, **kw):
    DB["rpc"].append(kw.get("json"))
    return Antwort()


ns.update(_sb_all=_sb_all, sb_delete=sb_delete, sb_update=sb_update, _sb_anfrage=_sb_anfrage, _sb_pruefen=lambda r: None,
          _sb_headers=lambda *a: {}, SUPABASE_URL="https://x", print=lambda *a, **k: None)
out = ns["ap_tagesreset"](TAG, JETZT, trocken=True)
check([z["plan_id"] for z in out["weg"]] == ["24d06afc-0000", "kaputt-0003"] and [z["plan_id"] for z in out["pruefen"]] == ["pruef-0001", "orbit-0004", "frisch-0005"]
      and not DB["geloescht"] and not DB["update"], f"trocken: nur einteilen, nichts schreiben — {out}")
out = ns["ap_tagesreset"](TAG, JETZT)
check(DB["geloescht"] == ["24d06afc-0000"] and out["fehler"] == 1 and [z["plan_id"] for z in out["weg"]] == ["24d06afc-0000"],
      f"weg: gelöscht, ein Fehler (kaputt-0003) hält den Lauf nicht auf — {DB['geloescht']} · fehler {out['fehler']}")
g = DB["delete_params"][0]
check(g.get("status") == "eq.planned" and g.get("started_at") == "is.null"
      and g.get("or") == "(start_um_gestartet_at.is.null,start_um_gestartet_at.lt.2026-10-20T19:00:00Z)",
      f"Lösch-Guard: noch planned, nie gestartet/gesendet, Claim leer oder > 2 h alt — {g}")
check([x[0] for x in DB["update"]] == ["pruef-0001", "orbit-0004"], f"Überprüfen: auch der an Orbit gesendete Plan (Guard ohne orbit_gesendet_at), der frisch geclaimte nicht — {[x[0] for x in DB['update']]}")
check(DB["delete_params"][0].get("orbit_gesendet_at") == "is.null" and all("orbit_gesendet_at" not in g for g in DB["update_params"]),
      "nie an Orbit gesendet nur im Lösch-Guard")
check([z["plan_id"] for z in out["pruefen"]] == ["pruef-0001", "orbit-0004"], f"Ergebnis zählt nur, was der Guard wirklich geschrieben hat — {[z['plan_id'] for z in out['pruefen']]}")
u = DB["update"][0] if DB["update"] else (None, {})
check(u[0] == "pruef-0001" and u[1].get("status") == "review" and u[1].get("ended_at") == BASIS["start_um"] and "master_pl" not in u[1]
      and u[1].get("result_notes", "").startswith("alt\nTages-Reset (Nachtlauf): Plan von 2026-10-19 nie fertig — Order am Konto prüfen"),
      f"pruefen: → Überprüfen am toten Tag, master_pl bleibt leer, Notiz angehängt — {u}")
check(DB["update_params"] and all(x.get("status") == "eq.planned" and x.get("started_at") == "is.null" and x.get("or", "").startswith("(start_um_gestartet_at.is.null,")
                                  for x in DB["update_params"]), "Überprüfen nur mit Guard: noch planned, nie gestartet, Claim leer oder alt")
check('"polar_lauf(id,status)"' in fn("ap_tagesreset") or "polar_lauf(id,status)" in fn("ap_tagesreset"), "Polar-Läufe werden mitgeladen (eingebettet)")
r = DB["rpc"][0] if DB["rpc"] else {}
fin = ((r.get("p_patch") or {}).get("final") or {})
check(r.get("p_status") == "review" and fin.get("grund") == "tagesende_unklar" and fin.get("quelle") == "tagesreset" and fin.get("datum") == "2026-10-19"
      and fin.get("at") == BASIS["start_um"] and fin.get("puls_versuche") == 1 and "today_pnl" not in fin and "Order am Konto prüfen" in fin.get("hinweis", ""),
      f"final: Grund + Hinweis am toten Tag, alte Felder bleiben, kein today_pnl (nicht „gelesen“) — {fin}")
check(not any(z[0] == "heute-0002" for z in DB["update"]) and "heute-0002" not in DB["geloescht"], "heutiger Plan bleibt unberührt")

# Einhängen im Nachtlauf: vor ap_planen, auch wenn der Planer aus ist, eigener try
nt = fn("ap_nacht_tick")
i_r, i_p, i_a = nt.find("ap_tagesreset(tag, jetzt)"), nt.find('ap_planen(tag, quelle="nacht")'), nt.find('if reg.get("aktiv"):')
check(0 < i_r < i_a < i_p, "Nachtlauf: Tages-Reset vor dem aktiv-Schalter und vor ap_planen")
check('zustand["tagesreset"] = {"tag": tag' in nt and "except Exception as e:" in nt[i_r:i_a], "Fehler im Reset hält den Nachtlauf nicht auf (eigener try, Stand in _ap_info)")
check("Regel" not in fn("tagesreset_art") or "Keine Regel" in SRC[SRC.find("TAGES-RESET LIEGENGEBLIEBENER"):SRC.find("TAGES-RESET LIEGENGEBLIEBENER") + 3000],
      "nur Zustand des Plans, keine Regelprüfung")

print()
if FEHLER:
    print(f"FEHLER ({len(FEHLER)}):")
    for f in FEHLER:
        print("  - " + f)
    sys.exit(1)
print("ALLES GRÜN")
