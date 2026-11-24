#!/usr/bin/env python3
"""Selbsttest WD1 (24.11.2026, Befund KC1): der WD-Farmer räumt GECLAIMTE Farmer-Fehlstarts früherer Tage weg, wenn der Nachtlauf sie
ebenfalls löschen würde (tagesreset_art „weg“) — sonst blockierten sie das Konto bis zum Tages-Reset 01:30 Dubai, der Farmer plant ~00:10.
Anlass: Ina · Tradeify 150k WD …2550, Plan 76ac7805 (24.11., Claim 14:55 Dubai, Tradovate-Login „nichts platziert“) → WD-Zeile 25.11.
„hat schon einen geplanten/laufenden Plan“.
Aufruf:  python3 tools/selftest_wd1_vortag_weg.py      (ohne Netz; Funktionen aus dem Quelltext von app.py)"""
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


# timedelta: in app.py global über „from datetime import timedelta“ auf Modulebene (wie tagesreset_art) — hier geprüft, nicht nur gesetzt
check(re.search(r"^from datetime import timedelta\s*$", SRC, re.M) is not None, "app.py importiert timedelta auf Modulebene")
ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone, "_ap_tz": ZoneInfo}
for zeile in ("TR_FILL_FELDER", "TR_GRUND", "WD_VORTAG_SEL", "WD_VORTAG_MERK_S", "_WD_VORTAG_NICHT"):
    m = re.search(r"^" + zeile + r" = .*?(?=\n\S)", SRC, re.M | re.S)
    exec(m.group(0), ns)
for name in ("_ap_ts", "tagesreset_tag", "tagesreset_hinweis", "tagesreset_art", "wd_plan_wegraeumbar", "wd_vortag_weg", "_wd_vortag_aufraeumen"):
    exec(fn(name), ns)
WEG = ns["wd_vortag_weg"]
JETZT = datetime(2026, 11, 24, 20, 10, tzinfo=timezone.utc)      # 25.11. 00:10 Dubai — WD-Lauf vor dem Nachtlauf
TAG = "2026-11-25"


def plan(**kw):
    p = {"id": "76ac7805-3f5e-4b74-9fe6-9d2a4bf2e5d0", "notes": "Winning-Day-Farmer", "status": "planned", "route": "tvv2", "auto_plan": False,
         "planned_for": "2026-11-24", "start_um": "2026-11-24T10:55:00+00:00", "start_um_gestartet_at": "2026-11-24T10:55:12.4+00:00",
         "start_claim_art": "start", "orbit_gesendet_at": None, "started_at": None, "master_name": "150k FTDFYSLX150235122550 → Funded",
         "polar_lauf": [],
         "mt5_baseline": {"wd_sl": {"sl": 1982}, "start_fehler": {"at": "2026-11-24T10:57:28.280Z", "pc": "pc-x", "status": "rot", "unklar": False,
                                                                  "schritt": "konto", "msg": "Nichts platziert · Tradovate-Login … (login_formular)"}}}
    for k, v in kw.items():
        if k == "sf":
            p["mt5_baseline"]["start_fehler"].update(v)
        elif k == "b":
            p["mt5_baseline"].update(v)
        else:
            p[k] = v
    return p


# ── Regel (rein rechnend) ──
check(WEG(plan(), TAG, JETZT) is True, "Ina …2550 (Claim + Start-Fehler „nichts platziert“ danach) → weg")
check(WEG(plan(sf={"unklar": True}), TAG, JETZT) is False, "Start-Fehler unklar → bleibt (Order kann raus sein)")
check(WEG(plan(sf={"schritt": "unklar"}), TAG, JETZT) is False, "Schritt „unklar“ → bleibt")
check(WEG(plan(sf={"at": "2026-11-24T10:50:00Z"}), TAG, JETZT) is False, "Start-Fehler VOR dem Claim (neu geclaimt) → bleibt")
check(WEG(plan(b={"hedge": {"status": "offen"}}), TAG, JETZT) is False, "Fusion-Hedge am Plan → bleibt")
check(WEG(plan(b={"tv": {"einstieg": 1}}), TAG, JETZT) is False, "TradingView-Spur → bleibt")
check(WEG(plan(b={"puls_unklar": True}), TAG, JETZT) is False, "Puls unklar → bleibt")
check(WEG(plan(b={"final": {"grund": "x", "master_pl": 12}}), TAG, JETZT) is False, "Ende-Eintrag mit Fill → bleibt")
check(WEG(plan(orbit_gesendet_at="2026-11-24T10:56:00Z"), TAG, JETZT) is False, "an Orbit gesendet → bleibt")
check(WEG(plan(route="polar"), TAG, JETZT) is False, "Polar → bleibt")
check(WEG(plan(polar_lauf=[{"id": 1, "status": "fertig"}]), TAG, JETZT) is False, "Polar-Lauf am Plan → bleibt")
check(WEG(plan(notes="Auto-Planer · Etappe"), TAG, JETZT) is False, "kein Farmer-Plan → nicht hier (Nachtlauf)")
check(WEG(plan(planned_for="2026-11-25"), TAG, JETZT) is False, "Plan desselben Tags → nie")
check(WEG(plan(planned_for=None), TAG, JETZT) is False, "ohne planned_for → nie")
check(WEG(plan(), "", JETZT) is False, "ohne Lauf-Tag → nie")
check(WEG(plan(status="open"), TAG, JETZT) is False, "läuft → nie")
check(WEG(plan(started_at="2026-11-24T10:56:00Z"), TAG, JETZT) is False, "gestartet → nie")
_kurz = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
check(WEG(plan(start_um="2026-11-24T11:00:00+00:00", start_um_gestartet_at="2026-11-24T11:00:05+00:00",
               sf={"at": "2026-11-24T11:01:00Z"}), TAG, _kurz) is False, "Start/Claim < 2 h her → bleibt")
check(WEG(plan(start_claim_art="verbrauch", sf={"at": "2026-11-24T10:50:00Z"}), TAG, JETZT) is True, "nur verbraucht → weg")
check(WEG(plan(mt5_baseline=None, start_um_gestartet_at=None), TAG, JETZT) is True, "nie geclaimt → weg (wie bisher)")
check(WEG(plan(sf={"at": "kaputt"}), TAG, JETZT) is False, "unlesbare Fehler-Zeit → bleibt")
check(WEG({"notes": "Winning-Day-Farmer", "planned_for": "2026-11-24", "status": "planned", "mt5_baseline": "x", "start_um": "??"}, TAG, JETZT) is False,
      "kaputte Zeile → False, wirft nicht")
# Review WD1 SOLLTE 1: Farmer lädt einen KÜNFTIGEN Tag, während der Plan-Tag in Dubai noch läuft → bleibt (sfBehoben kann neu starten)
_tags = datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc)      # 24.11. 19:00 Dubai, Fehlstart 14:57 → > 2 h her
check(WEG(plan(), "2026-11-25", _tags) is False, "Plan-Tag läuft noch (24.11. 19:00 Dubai), Farmer lädt 25.11. → bleibt")
check(WEG(plan(), "2026-11-26", JETZT) is True, "Farmer lädt übermorgen, Plan-Tag in Dubai vorbei → weg")
check(isinstance(WEG(plan(), TAG), bool), "ohne jetzt aufrufbar")

# ── Aufräumen gegen nachgebaute DB ──
ZEILEN, GELOESCHT, AUFRUFE = {}, [], []


def _sb_all(table, params):
    AUFRUFE.append(("all", table, dict(params)))
    if ns.get("_lese_fehler"):
        raise RuntimeError("weg")
    ids = params["id"][4:-1].split(",")
    return [dict(ZEILEN[i]) for i in ids if i in ZEILEN]


def sb_delete(table, params):
    AUFRUFE.append(("del", table, dict(params)))
    pid = params["id"][3:]
    if ns.get("_del_fehler") == pid:
        raise RuntimeError("Netz")
    if ns.get("_guard_greift") == pid:
        return []
    GELOESCHT.append(pid)
    return [{"id": pid}]


ns.update(_sb_all=_sb_all, sb_delete=sb_delete)
AUF = ns["_wd_vortag_aufraeumen"]
ZEILEN = {"a": plan(id="a"), "b": plan(id="b", sf={"unklar": True}), "c": plan(id="c", start_claim_art="verbrauch", sf={"at": "2026-11-24T10:50:00Z"}),
          "d": plan(id="d"), "e": plan(id="e")}
ns["_guard_greift"], ns["_del_fehler"] = "d", "e"
r = AUF(["a", "b", "c", "d", "e", "a", None], TAG, JETZT)
check(r == {"a", "c"}, f"gelöscht nur sichere + Guard bestätigt: {sorted(r)}")
check(sorted(GELOESCHT) == ["a", "c"], "b (unklar) nie gelöscht")
dels = {a[2]["id"]: a[2] for a in AUFRUFE if a[0] == "del"}
g = dels.get("eq.a", {})
check(g.get("status") == "eq.planned" and g.get("started_at") == "is.null" and g.get("orbit_gesendet_at") == "is.null"
      and g.get("start_um_gestartet_at") == "eq.2026-11-24T10:55:12.4+00:00" and g.get("start_um") == "eq.2026-11-24T10:55:00+00:00"
      and "or" not in g, f"Guard: planned/nie gestartet/nie gesendet + Claim und Start exakt wie gelesen: {g}")
check("start_claim_art" not in g and dels.get("eq.c", {}).get("start_claim_art") == "eq.verbrauch", "Verbrauch nur solange Verbrauch")
lesen = [a for a in AUFRUFE if a[0] == "all"]
check(len(lesen) == 1 and lesen[0][2]["id"] == "in.(a,b,c,d,e)" and "mt5_baseline" in lesen[0][2]["select"] and "polar_lauf" in lesen[0][2]["select"],
      "ein Lesen, volle Zeilen inkl. mt5_baseline + polar_lauf, ids einmalig")
# Merker (Review WD1 SOLLTE 3): b (nicht weg) wird 10 min nicht erneut geladen
AUFRUFE.clear(); GELOESCHT.clear()
check("b" in ns["_WD_VORTAG_NICHT"] and "a" not in ns["_WD_VORTAG_NICHT"], "„nicht weg“ gemerkt, Gelöschte nicht")
check(AUF(["b"], TAG, JETZT) == set() and not AUFRUFE, "gemerkter Plan → keine erneute Abfrage")
ns["_WD_VORTAG_NICHT"]["b"] = 0     # abgelaufen
AUF(["b"], TAG, JETZT)
check(len([a for a in AUFRUFE if a[0] == "all"]) == 1, "nach Ablauf wieder geprüft")
ns["_WD_VORTAG_NICHT"].clear(); AUFRUFE.clear(); GELOESCHT.clear()
check(AUF([], TAG, JETZT) == set() and not AUFRUFE, "keine Kandidaten → keine Abfrage")
ns["_lese_fehler"] = True
check(AUF(["a"], TAG, JETZT) == set() and not GELOESCHT, "Lesefehler → nichts gelöscht, wirft nicht")
ns["_lese_fehler"] = False
# ohne Startzeit/Claim → is.null-Guards
ZEILEN["f"] = plan(id="f", start_um=None, start_um_gestartet_at=None, mt5_baseline=None)
AUF(["f"], TAG, JETZT)
gf = {a[2]["id"]: a[2] for a in AUFRUFE if a[0] == "del"}.get("eq.f", {})
check(gf.get("start_um") == "is.null" and gf.get("start_um_gestartet_at") == "is.null", "ohne Start/Claim → is.null im Guard")

# ── Einbau in GET und POST ──
get = SRC[SRC.index("WD1 (24.11.2026): GECLAIMTE Farmer-Pläne früherer Tage"):]
get = get[:get.index('belegt[mid] = "hat schon einen geplanten/laufenden Plan"')]
check("_wd_vortag_aufraeumen(" in get and "in vortag_weg" in get and 'o.get("start_um_gestartet_at")' in get, "GET ruft das Aufräumen, überspringt Gelöschte")
check("not (nur and str(o.get(\"user_id\")) != str(nur))" in get, "GET: Verwalter-Ansicht räumt keine fremden IDs")
check("wd_plan_wegraeumbar(o.get(\"start_um\"))" in get, "GET: nie vor/kurz nach dem Start (wd_plan_wegraeumbar)")
post = SRC[SRC.index("WD1 (24.11.2026): geclaimte Farmer-Fehlstarts früherer Tage"):]
post = post[:post.index('blockiert = "hat schon einen geplanten/laufenden Plan"; break')]
check("_wd_vortag_aufraeumen(" in post and "in vortag_weg" in post and "neu_tag" in post, "POST ruft das Aufräumen mit dem Plan-Tag")
# alte Regel für ungeclaimte Pläne unverändert vorhanden
check(SRC.count('params={"id": f"eq.{o[\'id\']}", "status": "eq.planned", "start_um_gestartet_at": "is.null"}') == 2,
      "ungeclaimte Vortags-Pläne: alter Weg in GET + POST unverändert")

print(f"\n{'ALLES GRÜN' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
sys.exit(1 if FEHLER else 0)
