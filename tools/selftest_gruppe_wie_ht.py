#!/usr/bin/env python3
"""Selbsttest GRUPPE WIE HT (app.py, 30.10.2026, Finn: „Emins Trades sollen eins zu eins mit der gleichen Logik geplant werden wie bei
Hermann Technologies … er bestätigt sie einzeln" + „Emin hat eine eigene Waage … jede Gruppe wiegt für sich"). Ohne Netz:
- reine Helfer: ap_gruppe_ausgeblendet, ap_planer_gruppen (gestellte Gruppen-Daten), ap_gruppe_von_uid, ap_gruppe_tag
- ap_gruppe_planen: Protokoll in auto_plan_gruppe, nacht_tag als Claim (Hand-Lauf behält ihn), trocken schreibt nichts
- ap_gruppen_nacht_tick: je aktiver Gruppe genau einmal je Tag, schon geplante Gruppe übersprungen
- Quelltext-Verträge: ap_planen (IDs = Gruppe, kein HT-Claim/-Protokoll, Stand nur Gruppe, nie auto-bestätigt), Umsteller ohne
  Gruppen-Ausschluss, gp_tick nicht mehr in ap_loop, eigene Waage je Gruppe, Delta/Waage-Start mit Gruppen-Stand
Aufruf: python3 tools/selftest_gruppe_wie_ht.py"""
import os
import re
import sys
import threading
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
SRC = open(APP, encoding="utf-8").read()
FEHLER = []


def ok(bed, txt):
    print(("  ok   " if bed else "  FEHL ") + txt)
    if not bed:
        FEHLER.append(txt)


def block(name):
    i = SRC.index(f"\ndef {name}(") + 1
    return SRC[i:SRC.find("\n\n\n", i)]


def fn_text(name):
    i = SRC.index(f"\ndef {name}(") + 1
    m = re.search(r"\n(def |@app\.route|# ══)", SRC[i:])
    return SRC[i:i + m.start()] if m else SRC[i:]


# ── gestellte Umgebung ──
GRUPPEN_DATEN = {"gruppen": [{"id": "g-emin", "name": "Emin", "verwalter_id": "u-emin"},
                             {"id": "g-ht", "name": "Hermann Technologies", "verwalter_id": None},
                             {"id": "g-ohne", "name": "Ohne Zeile", "verwalter_id": "u-x"}],
                 "mitglieder": [{"user_id": "u-ahmad", "gruppe_id": "g-emin"}, {"user_id": "u-amir", "gruppe_id": "g-emin"},
                                {"user_id": "u-finn", "gruppe_id": "g-ht"}, {"user_id": "u-y", "gruppe_id": "g-ohne"}]}
ZEILEN = [{"gruppe_id": "g-emin", "aktiv": True, "letzter_lauf": {"tag": "2026-10-29", "nacht_tag": "2026-10-29"}}]
UPDATES, PLAENE = [], []

ns = {"datetime": datetime, "timedelta": timedelta, "timezone": timezone, "time": time, "threading": threading,
      "_kurz_cache_lock": threading.Lock(), "AP_TZ_LAUF": "Asia/Dubai", "AP_NACHT_STANDARD": {"uhr": "01:00", "tz": "Asia/Dubai"},
      "admin_gruppen_daten": lambda: GRUPPEN_DATEN, "_ap_tz": ZoneInfo, "print": lambda *a, **k: None}


def sb_select(tab, params):
    assert tab == "auto_plan_gruppe"
    return [dict(z) for z in ZEILEN]


def sb_update(tab, filt, upd):
    UPDATES.append((tab, filt, upd))
    for z in ZEILEN:
        if f"eq.{z['gruppe_id']}" == filt.get("gruppe_id"):
            z.update(upd)
    return [1]


def ap_planen(tag=None, trocken=False, quelle="hand", seed=None, gruppe=None, **kw):
    PLAENE.append({"tag": tag, "trocken": trocken, "quelle": quelle, "gruppe": gruppe})
    return {"ok": True, "tag": tag or "2026-10-30", "quelle": quelle, "geplant": [{"start": "09:00"}], "ausgelassen": [],
            "gruppe_id": (gruppe or {}).get("gruppe_id")}


ns.update(sb_select=sb_select, sb_update=sb_update, ap_planen=ap_planen)
for n in ("gp_tag_wahl", "ap_gruppe_ausgeblendet", "ap_planer_gruppen", "ap_gruppe_tag", "ap_gruppe_planen"):
    exec(block(n), ns)
exec(re.search(r"^_ap_gruppen_cache = .*$", SRC, re.M).group(0), ns)
exec(fn_text("ap_gruppe_von_uid"), ns)
exec(re.search(r"^_ap_gruppen_nacht = .*$", SRC, re.M).group(0), ns)
exec(block("ap_gruppen_nacht_tick"), ns)

print("Helfer")
ok(ns["ap_gruppe_ausgeblendet"](["a", "b", "c", "d"], {"b", "c"}) == {"a", "d"}, "ausgeblendet = alle außer der Gruppe")
ok(ns["ap_gruppe_ausgeblendet"](None, None) == set(), "ausgeblendet ohne Daten = leer")
gr = ns["ap_planer_gruppen"]()
ok([g["gruppe_id"] for g in gr] == ["g-emin"], "nur Verwalter-Gruppen MIT Zeile in auto_plan_gruppe (HT und Gruppe ohne Zeile raus)")
ok(gr and gr[0]["ids"] == frozenset({"u-emin", "u-ahmad", "u-amir"}), "IDs = Verwalter + Mitglieder")
ok(ns["ap_gruppe_von_uid"]("u-amir", gr)["gruppe_id"] == "g-emin", "Mitglied → seine Gruppe")
ok(ns["ap_gruppe_von_uid"]("u-emin")["gruppe_id"] == "g-emin", "Verwalter → seine Gruppe (gemerkte Liste)")
ok(ns["ap_gruppe_von_uid"]("u-finn", gr) is None, "HT-ID → None")
ZEILEN[0]["aktiv"] = False
ok(ns["ap_planer_gruppen"](nur_aktiv=True) == [], "nur_aktiv: ausgeschaltete Gruppe fehlt")
ZEILEN[0]["aktiv"] = True
ok(ns["ap_gruppe_tag"](None) is None and ns["ap_gruppe_tag"]("heute") is None, "tag leer/heute → None (ap_planen: heute Dubai)")
fr = datetime(2026, 10, 30, 8, 0, tzinfo=timezone.utc)   # Freitag
ok(ns["ap_gruppe_tag"]("morgen", fr) == "2026-11-02", "morgen am Freitag → Montag")
try:
    ns["ap_gruppe_tag"]("quatsch", fr)
    ok(False, "ungültiger Tag wirft ValueError")
except ValueError:
    ok(True, "ungültiger Tag wirft ValueError")

print("ap_gruppe_planen")
UPDATES.clear(); PLAENE.clear()
e = ns["ap_gruppe_planen"]("g-emin", trocken=True)
ok(PLAENE[-1]["gruppe"]["gruppe_id"] == "g-emin" and PLAENE[-1]["trocken"], "trocken: ap_planen mit gruppe")
ok(not UPDATES, "trocken: kein Protokoll")
ns["ap_gruppe_planen"]("g-emin", quelle="hand")
ok(UPDATES and UPDATES[-1][2]["letzter_lauf"].get("nacht_tag") == "2026-10-29", "Hand-Lauf: nacht_tag (Claim) bleibt erhalten")
ns["ap_gruppe_planen"]("g-emin", quelle="nacht", tag="2026-11-02")
ok(UPDATES[-1][2]["letzter_lauf"].get("nacht_tag") == "2026-11-02", "Nachtlauf: nacht_tag = geplanter Tag")
ok(ns["ap_gruppe_planen"]("g-unbekannt").get("ok") is False, "fremde/unbekannte Gruppe → ok False")
ok(ns["ap_gruppe_planen"]("g-emin", tag="quatsch").get("ok") is False, "ungültiger Tag → ok False")

print("ap_gruppen_nacht_tick")
PLAENE.clear()
ns["ap_nacht_ziel"] = lambda jetzt, param: ((date(2026, 11, 3), jetzt), None)
ZEILEN[0]["letzter_lauf"] = {"nacht_tag": "2026-11-02"}
ns["_ap_gruppen_nacht"].clear(); ns["_ap_gruppen_nacht"].update(fehler="", letzt={})
ns["ap_gruppen_nacht_tick"](fr, {})
ok(len(PLAENE) == 1 and PLAENE[0]["quelle"] == "nacht" and PLAENE[0]["tag"] == "2026-11-03", "fälliger Tag → ein Nachtlauf je Gruppe")
ns["ap_gruppen_nacht_tick"](fr, {})
ok(len(PLAENE) == 1, "zweiter Takt im selben Tag (10-min-Bremse) → kein zweiter Lauf")
ns["_ap_gruppen_nacht"]["geprueft"] = 0
ns["ap_gruppen_nacht_tick"](fr, {})
ok(len(PLAENE) == 1, "nach der Bremse: nacht_tag schon gesetzt → übersprungen")
ns["ap_nacht_ziel"] = lambda jetzt, param: (None, None)
ok(ns["ap_gruppen_nacht_tick"](fr, {}) is None, "nichts fällig → nichts")

print("Quelltext-Verträge")
ap = fn_text("ap_planen")
ok("gruppe=None" in ap.split("\n")[0] + ap.split("\n")[1], "ap_planen hat den Parameter gruppe")
ok('uids = sorted(str(u) for u in (gruppe.get("ids") or ()))' in ap, "ap_planen: IDs = Gruppe")
ok('if quelle == "nacht" and not trocken and not gruppe:' in ap, "ap_planen: kein HT-Nacht-Claim für die Gruppe")
ok("ausgeblendet = ap_gruppe_ausgeblendet(namen, uids)" in ap, "ap_planen: Stand nur aus der Gruppe")
ok("and not gruppe:   # NACHPLANEN ohne Treffer" in ap, "ap_planen: kein auto_plan_lauf-Protokoll für die Gruppe")
ok('if param["auto_start"] and not gruppe:' in ap, "ap_planen: Gruppen-Pläne nie automatisch bestätigt")
for n in ("_eh_tick_lauf", "ehv_tick", "tfh_tick", "ah_tick"):
    t = fn_text(n)
    ok("ap_planer_gruppen_ids()" in t and "gp_verwalter_karte()" not in t, f"{n}: Verwalter-Gruppen laufen wie HT")
loop = fn_text("ap_loop")
ok(not re.search(r"^\s+gp_tick\(\)", loop, re.M) and "ap_gruppen_nacht_tick(" in loop, "ap_loop: gp_tick aus, Gruppen-Nachtlauf an")
w = fn_text("ap_waage_tick")
ok("ap_planer_gruppen(nur_aktiv=True)" in w and "ap_gruppe_ausgeblendet(namen, gr[\"ids\"])" in w, "Waage: eigene Waage je Gruppe")
ok("ap_waage_nachschub(st_g, w_g" in w and "st_g = _ap_stand_laden(reg" in w,
   "Gruppen-Waage: derselbe Stand-Lader + Nachschub wie HT")
ok('"eh_an": eh_param(regeln)["an"]' in fn_text("_ap_stand_laden"), "_ap_stand_laden setzt eh_an (gilt damit auch für den Gruppen-Stand)")
ok("stand.get(\"eh_an\")" in fn_text("ap_waage_nachschub") and "ap_eh_wird_hedgen(z, eh_an)" in fn_text("_ap_waage_kandidat"),
   "Waage-Fix 30.10. (nie einen Plan vorziehen, den eh_tick hedgt) greift über ap_waage_nachschub auch in der Gruppen-Waage")
ok("ap_gruppe_von_uid(plan.get(\"user_id\"))" in fn_text("admin_auto_plan_waage_start"), "Waage-Start: Gruppen-Plan wiegt mit der Gruppe")
ok("isinstance(sicht_d, frozenset)" in fn_text("admin_auto_plan_delta"), "Delta: Gruppen-Sicht lädt den Gruppen-Stand")
ok("ap_gruppe_planen(gid" in fn_text("admin_gruppen_plan"), "Gruppen-Knöpfe rechnen mit dem HT-Planer")
ok("ap_gruppe_von_uid(uid)" in fn_text("admin_auto_plan"), "GET /admin/auto-plan: Verwalter sieht den Lauf seiner Gruppe")

print("\nALLES OK" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
