#!/usr/bin/env python3
"""Selbsttest GRUPPE WIE HT (app.py, 30.10.2026, Finn: „Emins Trades sollen eins zu eins mit der gleichen Logik geplant werden wie bei
Hermann Technologies … er bestätigt sie einzeln" + „Emin hat eine eigene Waage … jede Gruppe wiegt für sich"). Ohne Netz:
- reine Helfer: ap_gruppe_ausgeblendet, ap_planer_gruppen (gestellte Gruppen-Daten), ap_gruppe_von_uid, ap_gruppe_tag
- ap_gruppe_planen: Protokoll in auto_plan_gruppe, nacht_tag als Claim (Hand-Lauf behält ihn), trocken schreibt nichts
- ap_gruppen_nacht_tick: je aktiver Gruppe genau einmal je Tag, schon geplante Gruppe übersprungen
- GRUPPE NACHPLANEN (02.11.2026): ap_gruppen_nachplan_tick, Mischen des Protokolls, Abgehakt nach dem Nachtlauf → Vorschlag, nie bestätigt
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

ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone, "time": time, "threading": threading,
      "_kurz_cache_lock": threading.Lock(), "AP_TZ_LAUF": "Asia/Dubai", "AP_NACHT_STANDARD": {"uhr": "01:00", "tz": "Asia/Dubai"},
      "admin_gruppen_daten": lambda: GRUPPEN_DATEN, "_ap_tz": ZoneInfo, "print": lambda *a, **k: None}


HT_AKTIV = {"aktiv": True}


def sb_select(tab, params):
    if tab == "auto_plan_regeln":
        return [dict(HT_AKTIV)]
    assert tab == "auto_plan_gruppe"
    return [dict(z) for z in ZEILEN]


def sb_update(tab, filt, upd):
    out = []
    for z in ZEILEN:
        if f"eq.{z['gruppe_id']}" != filt.get("gruppe_id"):
            continue
        m = re.search(r"nacht_tag\.neq\.([0-9-]+)\)", filt.get("or") or "")
        if m and (z.get("letzter_lauf") or {}).get("nacht_tag") == m.group(1):
            continue                  # Claim schon vergeben (PostgREST: Bedingung trifft nicht)
        z.update(upd)
        out.append(dict(z))
    UPDATES.append((tab, filt, upd))
    return out


def ap_planen(tag=None, trocken=False, quelle="hand", seed=None, gruppe=None, **kw):
    PLAENE.append({"tag": tag, "trocken": trocken, "quelle": quelle, "gruppe": gruppe})
    return {"ok": True, "tag": tag or "2026-10-30", "quelle": quelle, "geplant": [{"start": "09:00"}], "ausgelassen": [],
            "gruppe_id": (gruppe or {}).get("gruppe_id")}


ns.update(sb_select=sb_select, sb_update=sb_update, ap_planen=ap_planen)
for n in ("gp_tag_wahl", "ap_gruppe_ausgeblendet", "ap_planer_gruppen", "ap_gruppe_tag", "ap_gruppe_lauf_ohne_erledigt", "ap_gruppe_lauf_mischen", "ap_gruppe_planen"):
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
ok(UPDATES[-2][1].get("or") and UPDATES[-2][2]["letzter_lauf"].get("nacht_tag") == "2026-11-02", "Nachtlauf: Claim (nacht_tag) VOR dem Planen")
ok(UPDATES[-1][2]["letzter_lauf"].get("nacht_tag") == "2026-11-02", "Nachtlauf: Protokoll mit nacht_tag = geplanter Tag")
n_pl = len(PLAENE)
e2 = ns["ap_gruppe_planen"]("g-emin", quelle="nacht", tag="2026-11-02")
ok(len(PLAENE) == n_pl and "schon geplant" in str(e2.get("msg")), "zweiter Nachtlauf desselben Tags (anderer Container) → Claim fehlt, nichts geplant")
PLAENE.clear()
ns["ap_gruppe_planen"]("g-emin", quelle="nacht", tag="2026-11-04")
ok(PLAENE[-1]["tag"] == "2026-11-04", "Nachtlauf: Tag wird nie über gp_tag_wahl geklemmt (Dubai-Mitternacht)")
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
PLAENE.clear(); HT_AKTIV["aktiv"] = False
ns["ap_nacht_ziel"] = lambda jetzt, param: ((date(2026, 11, 5), jetzt), None)
ns["_ap_gruppen_nacht"]["geprueft"] = 0
ns["ap_gruppen_nacht_tick"](fr, {})
ok(not PLAENE, "HT-Planer pausiert (auto_plan_regeln.aktiv false) → auch keine Gruppe")
HT_AKTIV["aktiv"] = True

print("Quelltext-Verträge")
ap = fn_text("ap_planen")
ok("gruppe=None" in ap.split("\n")[0] + ap.split("\n")[1], "ap_planen hat den Parameter gruppe")
ok('uids = sorted(str(u) for u in (gruppe.get("ids") or ()))' in ap, "ap_planen: IDs = Gruppe")
ok('if quelle == "nacht" and not trocken and not gruppe:' in ap, "ap_planen: kein HT-Nacht-Claim für die Gruppe")
ok("ausgeblendet = ap_gruppe_ausgeblendet(namen, uids)" in ap, "ap_planen: Stand nur aus der Gruppe")
ok("if gruppe and not namen:" in ap, "ap_planen: ohne Nutzerliste keine Gruppe (nie gegen HT)")
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
ok("sicht_d <= _admin_verwalter_gruppen_ids(admin_gruppen_daten())" in fn_text("admin_auto_plan_delta"),
   "Delta: Gruppen-Stand nur für Verwalter-Gruppen (Finns HT-Chip unverändert)")
ok("gr_lauf = None\n" in fn_text("admin_auto_plan") or "gr_lauf = None" in fn_text("admin_auto_plan").split("except Exception")[1],
   "GET /admin/auto-plan: Gruppen-Lesefehler → HT-Lauf, kein HTTP 500")
ok("ap_gruppe_planen(gid" in fn_text("admin_gruppen_plan"), "Gruppen-Knöpfe rechnen mit dem HT-Planer")
ok("ap_gruppe_von_uid(uid)" in fn_text("admin_auto_plan"), "GET /admin/auto-plan: Verwalter sieht den Lauf seiner Gruppe")


print("GRUPPE NACHPLANEN (02.11.2026)")
for k in ("AP_NACHPLAN_FEST_GRUENDE", "AP_NACHPLAN_REGEL_GRUENDE"):
    exec(re.search(rf"^{k} = \([^)]*\)", SRC, re.M | re.S).group(0), ns)
for pat in (r"^AP_TYPEN = .*$", r"^AP_NACHPLAN_VORLAUF_MIN = .*$", r"^AP_NACHPLAN_REST_RE = .*$", r"^AP_REST_MIN_CFD = .*$", r"^AP_NEU_BIS_STANDARD = .*$",
            r"^AP_TZ_TAG = .*$", r"^_ap_nachplan_lock = .*$", r"^_ap_gruppen_nachplan = .*$", r"^_ap_gruppe_regel_at = .*$"):   # NP1
    exec(re.search(pat, SRC, re.M).group(0), ns)
for n in ("_ap_ts", "_ap_hhmm", "ap_zeiten_heute", "ap_start_bis", "ap_nachplan_fenster", "_ap_plan_am_tag", "ap_nachplan_letzter", "ap_nachplan_ziel_frei", "ap_konto_neu_zu_spaet",
          "ap_nachplan_kandidaten", "ap_nachplan_regeln_at", "ap_nachplan_regeln_merken", "_ap_nachplan_rechnen", "ap_gruppen_nachplan_tick",
          "ap_gruppe_regel_bezug"):   # NP1
    exec(block(n), ns)

Z_TAG = "2026-11-02"
# Nachtlauf 21:31 UTC: k-erl wurde danach abgehakt, k-rev steht noch in Überprüfen, k-heute wird heute abgehakt, k-ziel hat einen festen Grund
NACHT = {"tag": Z_TAG, "at": "2026-11-01T21:31:01+00:00", "quelle": "nacht", "nacht_tag": Z_TAG, "geplant": [{"konto_id": "k-alt"}],
         "ausgelassen": [{"konto_id": k, "grund": "letzter Trade noch nicht erledigt (Überprüfen)"} for k in ("k-erl", "k-rev", "k-heute")]
         + [{"konto_id": "k-ziel", "grund": "Ziel erreicht (Ziel-Wache) — Phase umstellen, der Bot plant hier nie"}]}
Z_KONTEN = [{"id": k, "account_type": "phase1", "user_id": "u-emin"} for k in ("k-erl", "k-rev", "k-heute", "k-ziel", "k-alt")]
Z_PLAENE = [{"master_account_id": "k-erl", "status": "completed", "started_at": "2026-10-30T05:00:00+00:00", "completed_at": "2026-11-01T21:42:00+00:00"},
            {"master_account_id": "k-rev", "status": "review", "started_at": "2026-10-30T05:00:00+00:00"},
            {"master_account_id": "k-heute", "status": "completed", "started_at": "2026-10-30T05:00:00+00:00", "completed_at": "2026-11-02T05:00:00+00:00"},
            {"master_account_id": "k-alt", "status": "planned", "planned_for": Z_TAG}]
Z_AUFRUFE = []
ANTWORT = {"geplant": [{"konto_id": "k-erl"}], "ausgelassen": []}


def z_planen(tag=None, trocken=False, quelle="hand", seed=None, gruppe=None, nur_konten=None, **kw):
    Z_AUFRUFE.append({"tag": tag, "quelle": quelle, "gruppe": (gruppe or {}).get("gruppe_id"), "nur": list(nur_konten or [])})
    return {"ok": True, "tag": tag, "quelle": quelle, "at": "2026-11-02T06:00:00+00:00", "geplant": list(ANTWORT["geplant"]), "ausgelassen": list(ANTWORT["ausgelassen"])}


HT_AKTIV.update(zeiten={"start_bis": "16:30"}, updated_at="2026-11-01T10:00:00+00:00")
ns.update(ap_planen=z_planen, _ap_konten_laden=lambda q: [dict(k) for k in Z_KONTEN], _sb_all=lambda t, q: [dict(p) for p in Z_PLAENE], _ap_archiviert=lambda: set())
ZEILEN[:] = [{"gruppe_id": "g-emin", "aktiv": True, "letzter_lauf": dict(NACHT)}]
UPDATES.clear()
TICK = ns["ap_gruppen_nachplan_tick"]
BEST = {"at": 123.0}
ns["_ap_auto_best"] = BEST
j = datetime(2026, 11, 2, 6, 0, tzinfo=timezone.utc)     # Montag 07:00 dt, im Fenster
zst = {"nachplan_at": 1000.0}

r = TICK(j, zst)
ok([a["nur"] for a in Z_AUFRUFE] == [["k-erl"]], f"Abgehakt nach dem Nachtlauf → nachgeplant; Überprüfen, heute abgehakt, Ziel, geplant nicht ({Z_AUFRUFE})")
ok(r == {"g-emin": 1}, "Tick meldet 1 Plan je Gruppe")
ok(Z_AUFRUFE and Z_AUFRUFE[0]["tag"] == Z_TAG and Z_AUFRUFE[0]["quelle"] == "nachplanen" and Z_AUFRUFE[0]["gruppe"] == "g-emin", "ap_planen: deutscher Tag, Quelle nachplanen, gruppe gesetzt")
ll = ZEILEN[0]["letzter_lauf"]
ok(ll["nacht_tag"] == Z_TAG, "Nacht-Claim bleibt: kein zweiter Nachtlauf")
ok(ll["quelle"] == "nachplanen" and sorted(x["konto_id"] for x in ll["geplant"]) == ["k-alt", "k-erl"], "Protokoll: alte + neue Pläne")
ok(sorted(x["konto_id"] for x in ll["ausgelassen"]) == ["k-heute", "k-rev", "k-ziel"], "Protokoll: k-erl aus der Ausgelassen-Liste, die übrigen Zeilen bleiben")
ok(BEST["at"] == 123.0, "kein Anstoß von Auto-Bestätigen")

n = len(Z_AUFRUFE)
TICK(j, zst)
ok(len(Z_AUFRUFE) == n, "gleicher HT-Takt → kein zweiter Lauf")

# zweiter Takt: k-erl hat jetzt einen Plan, nichts mehr zu tun
Z_PLAENE.append({"master_account_id": "k-erl", "status": "planned", "planned_for": Z_TAG})
UPDATES.clear(); zst["nachplan_at"] = 1300.0
TICK(j + timedelta(minutes=5), zst)
ok(len(Z_AUFRUFE) == n and not UPDATES, "kein Kandidat → kein Lauf, kein Schreiben")

# neues Konto ohne Treffer: Grund einmal schreiben, gleicher Grund danach nicht mehr
Z_KONTEN.append({"id": "k-neu", "account_type": "phase1", "user_id": "u-emin"})
ANTWORT.update(geplant=[], ausgelassen=[{"konto_id": "k-neu", "grund": "keine Balance bekannt"}])
UPDATES.clear(); zst["nachplan_at"] = 1600.0
TICK(j + timedelta(minutes=10), zst)
ok(len(UPDATES) == 1 and any(x["konto_id"] == "k-neu" for x in ZEILEN[0]["letzter_lauf"]["ausgelassen"]), "neuer Grund ohne Plan → einmal protokolliert")
UPDATES.clear(); zst["nachplan_at"] = 1900.0
TICK(j + timedelta(minutes=15), zst)
ok(not UPDATES, "gleicher Grund → kein Schreiben alle 5 min")

# Schalter und Fenster
n = len(Z_AUFRUFE)
zst["nachplan_at"] = 2200.0; ZEILEN[0]["aktiv"] = False
TICK(j, zst)
ok(len(Z_AUFRUFE) == n, "auto_plan_gruppe.aktiv aus → nichts")
ZEILEN[0]["aktiv"] = True; zst["nachplan_at"] = 2500.0; HT_AKTIV["aktiv"] = False
TICK(j, zst)
ok(len(Z_AUFRUFE) == n, "auto_plan_regeln.aktiv aus → nichts")
HT_AKTIV["aktiv"] = True; zst["nachplan_at"] = 2800.0
TICK(datetime(2026, 11, 2, 19, 0, tzinfo=timezone.utc), zst)
ok(len(Z_AUFRUFE) == n, "außerhalb des Fensters → nichts")
TICK(j, {})
ok(len(Z_AUFRUFE) == n, "noch kein HT-Takt → nichts")

# Fehler in ap_planen: Lock wieder frei, Fehler sichtbar
def z_wirft(*a, **k):
    raise RuntimeError("DB weg")
ns["ap_planen"] = z_wirft
zst["nachplan_at"] = 3100.0
TICK(j, zst)
ok("DB weg" in ns["_ap_gruppen_nachplan"]["fehler"] and not ns["_ap_nachplan_lock"].locked(), "Fehler steht im Merker, Sperre wieder frei")
ns["ap_planen"] = z_planen

# Lauf meldet ok False: Fehler sichtbar, Merker bleibt frei
ns["ap_planen"] = lambda *a, **k: {"ok": False, "msg": "Nutzerliste nicht lesbar"}
zst["nachplan_at"] = 3400.0
TICK(j, zst)
ok("Nutzerliste" in ns["_ap_gruppen_nachplan"]["fehler"], "ok False → Fehler sichtbar, nichts gemerkt")
ns["ap_planen"] = z_planen

# Knopf „morgen“ hat den nächsten Tag geplant: Takt lässt das Protokoll stehen
n = len(Z_AUFRUFE)
_ll_alt = ZEILEN[0]["letzter_lauf"]
ZEILEN[0]["letzter_lauf"] = dict(_ll_alt, tag="2026-11-03")
zst["nachplan_at"] = 3700.0
TICK(j, zst)
ok(len(Z_AUFRUFE) == n and ZEILEN[0]["letzter_lauf"]["tag"] == "2026-11-03", "Lauf für morgen liegt vor → Takt rechnet nicht, Protokoll bleibt")
ZEILEN[0]["letzter_lauf"] = _ll_alt

# Mischen
M = ns["ap_gruppe_lauf_mischen"]
m, g = M({"tag": "2026-11-01", "geplant": [{"konto_id": "a"}], "ausgelassen": [{"konto_id": "b", "grund": "x"}]}, {"tag": Z_TAG, "geplant": [], "ausgelassen": []}, ["c"])
ok(m["geplant"] == [] and m["ausgelassen"] == [] and g is False, "anderer Tag: alte Zeilen fallen weg")
ok(ns["ap_gruppe_lauf_ohne_erledigt"]({"ausgelassen": [{"grund": "letzter Trade noch nicht erledigt (Überprüfen)"}, {"grund": "Ziel erreicht"}]})["ausgelassen"] == [{"grund": "Ziel erreicht"}],
   "ohne_erledigt nimmt nur die „letzter Trade“-Zeilen")

# Verträge: HT unverändert, Takt in der Schleife
_hl = fn_text("ap_loop")
ok(_hl.index("ap_nachplan_tick(") < _hl.index("ap_gruppen_nachplan_tick("), "ap_loop: Gruppen-Takt direkt nach dem HT-Takt")
_rr = fn_text("_ap_nachplan_rechnen")
ok('else ap_planen(tag, quelle="nachplanen", nur_konten=kand)' in _rr and 'sb_select("auto_plan_lauf"' in _rr, "HT-Weg: ap_planen und auto_plan_lauf wie bisher")
ok('uids = [str(u) for u in (reg.get("user_ids") or [])]' in fn_text("ap_nachplan_tick"), "ap_nachplan_tick: weiter nur HT-IDs")
ok("_ap_auto_best" not in fn_text("ap_gruppen_nachplan_tick"), "Gruppen-Takt fasst Auto-Bestätigen nicht an")

print("\nALLES OK" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
