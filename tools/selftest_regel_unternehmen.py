#!/usr/bin/env python3
"""Selbsttest REGEL JE UNTERNEHMEN = STANDARD + ABWEICHUNG JE FELD (Phase 1 Challenge-Planer, Finn 05.11.2026 über den Master): wirksame Regel eines
Unternehmens = Standard (auto_plan_regeln id=1) überlagert mit seinen Abweichungen (auto_plan_gruppe.regeln) und firmen_modell. Prüft mit den echten
Firmen-Regeln (tools/selftest_orbit_prio2_firmen.json): leer = Standard bitgleich, Abweichung je Feld, Standard folgt live, nur Phase-1-Felder, nur
vorhandene Pfade, Wert = Standard → keine Abweichung, ↺ zurück, Startfenster, Rechte der Routen (Admin, Verwalter, fremd), Planer-Hook. Ohne Netz.
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_regel_unternehmen.py"""
import copy
import json
import os
import sys

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


FIRMEN = json.load(open(os.path.join(HIER, "selftest_orbit_prio2_firmen.json"), encoding="utf-8"))
FIRMEN.append({"namen": ["fundednextfutures"], "route": "tvv2", "planen": False, "boden": "nachziehend", "groessen": [50000, 150000],
               "phasen": {"challenge": {"tp": [1800, 2000], "menge": [2, 2], "ziel_pct": 6}},
               "je_groesse": {"50000": {"dd_usd": 1500, "phasen": {"challenge": {"tp": [900, 980], "menge": [1, 1], "ziel_pct": 5, "tp_max": 1000}}}}})
STD = {"firmen": FIRMEN, "zufall": {"x": 1}}
LU = ["je_groesse", "50000", "phasen", "challenge", "tp"]
hol = lambda r, k, pfad: app._unt_hol(next(f for f in r["firmen"] if f["namen"][0] == k), pfad)[1]   # noqa: E731

print("1) Merge Standard + Abweichung")
check(json.dumps(app.ap_unt_regeln(STD, {}, {}), sort_keys=True) == json.dumps(STD, sort_keys=True), "leere Abweichung = Standard bitgleich")
abw = {"firmen": {"lucidtrading": {"je_groesse": {"50000": {"phasen": {"challenge": {"tp": [1300, 1400]}}}}}}}
r = app.ap_unt_regeln(STD, abw, {})
check(hol(r, "lucidtrading", LU) == [1300, 1400] and hol(r, "lucidtrading", ["je_groesse", "50000", "phasen", "challenge", "ziel_pct"]) == 6,
      "Abweichung TP Lucid 50k wirkt, übrige Felder der Phase bleiben Standard")
std2 = copy.deepcopy(STD); next(f for f in std2["firmen"] if f["namen"][0] == "lucidtrading")["je_groesse"]["50000"]["phasen"]["challenge"]["menge"] = [2, 2]
check(hol(app.ap_unt_regeln(std2, abw, {}), "lucidtrading", ["je_groesse", "50000", "phasen", "challenge", "menge"]) == [2, 2],
      "Standard ändert sich → nicht geändertes Feld folgt live")
r = app.ap_unt_regeln(STD, {"firmen": {"lucidtrading": {"je_groesse": {"50000": {"phasen": {"challenge": {"ziel_pct": 3, "tp_max": 1}}}}}, "gibtsnicht": {"x": 1}}}, {})
check(hol(r, "lucidtrading", ["je_groesse", "50000", "phasen", "challenge", "ziel_pct"]) == 3
      and hol(r, "lucidtrading", ["je_groesse", "50000", "phasen", "challenge", "tp_max"]) == 1500,
      "Phase 2: Ziel % wirkt aus der Abweichung, Consistency (tp_max) bleibt Standard")
r = app.ap_unt_regeln(STD, {"firmen": {"tradeify": {"je_groesse": {"150000": {"phasen": {"challenge": {"tp": [1, 2]}}}}}}}, {})
check("je_groesse" not in next(f for f in r["firmen"] if f["namen"][0] == "tradeify"), "Pfad, den es im Standard nicht gibt → wirkt nie (kein neuer Größen-Block)")
r = app.ap_unt_regeln(STD, {}, {"fundednextfutures": "orbit_v2", "lucidtrading": "aus"})
check(next(f for f in r["firmen"] if f["namen"][0] == "fundednextfutures")["planen"] is True and next(f for f in r["firmen"] if f["namen"][0] == "lucidtrading")["planen"] is False,
      "firmen_modell geht in die wirksame Regel ein (FNF an, Lucid aus)")
check(app.ap_unt_zeiten({"fenster": [["02:00", "20:00", 100]], "nachtlauf": {"uhr": "01:30"}}, {"zeiten": {"fenster": [["04:00", "18:00", 100]]}})
      == {"fenster": [["04:00", "18:00", 100]], "nachtlauf": {"uhr": "01:30"}}, "Startfenster-Abweichung, übrige Zeiten Standard")

print("2) Schreiben (ap_unt_kernwert / ap_unt_zeiten_aendern)")
a2, fm2, f2, g = app.ap_unt_kernwert(FIRMEN, {}, {}, "lucidtrading", [{"pfad": LU, "wert": [1300, 1400]}])
check(g is None and a2 == abw and app._unt_hol(f2, LU)[1] == [1300, 1400], f"TP Lucid 50k gesetzt → nur diese Abweichung gespeichert ({a2})")
a3, _fm, _f, g = app.ap_unt_kernwert(FIRMEN, a2, {}, "lucidtrading", [{"pfad": LU, "wert": [1450, 1500]}])
check(g is None and a3 == {}, "Wert = Standard → Abweichung weg")
a4, _fm, _f, g = app.ap_unt_kernwert(FIRMEN, a2, {}, "lucidtrading", [], [LU])
check(g is None and a4 == {}, "↺ auf Standard zurück")
_a, _fm, _f, g = app.ap_unt_kernwert(FIRMEN, {}, {}, "lucidtrading", [{"pfad": ["je_groesse", "50000", "phasen", "challenge", "ziel_pct"], "wert": 4}])
check(g is None and _a == {"firmen": {"lucidtrading": {"je_groesse": {"50000": {"phasen": {"challenge": {"ziel_pct": 4}}}}}}}, f"Phase 2: Ziel % im Unternehmen änderbar ({g or _a})")
_a, _fm, _f, g = app.ap_unt_kernwert(FIRMEN, {}, {}, "lucidtrading", [{"pfad": ["je_groesse", "50000", "dd_usd"], "wert": 2500}])
check(g is None and _a == {"firmen": {"lucidtrading": {"je_groesse": {"50000": {"dd_usd": 2500}}}}}, f"Phase 2: Max DD im Unternehmen änderbar ({g or _a})")
_a, _fm, _f, g = app.ap_unt_kernwert(FIRMEN, {}, {}, "lucidtrading", [{"pfad": ["je_groesse", "50000", "phasen", "challenge", "tp_max"], "wert": 1200}])
check(bool(g) and "für alle" in g, f"Consistency (tp_max) gilt für alle ({g})")
_a, _fm, _f, g = app.ap_unt_kernwert(FIRMEN, {}, {}, "lucidtrading", [{"pfad": LU, "wert": [0, 1]}])
check(bool(g), f"Grenzen wie der Standard (TP 0 abgelehnt: {g})")
_a, fm5, f5, g = app.ap_unt_kernwert(FIRMEN, {}, {}, "fundednextfutures", [{"pfad": ["planen"], "wert": True}])
check(g is None and fm5 == {"fundednextfutures": "orbit_v2"} and f5["planen"] is True, "FNF im Unternehmen an → firmen_modell Orbit V2 (Standard plant nicht)")
_a, fm6, _f, g = app.ap_unt_kernwert(FIRMEN, {}, {"lucidtrading": "aus"}, "lucidtrading", [{"pfad": ["planen"], "wert": True}])
check(g is None and fm6 == {}, "Lucid wieder an → wie Standard (kein Eintrag)")
z, zw, g = app.ap_unt_zeiten_aendern({"fenster": [["02:00", "20:00", 100]]}, {}, [{"pfad": ["fenster", "0", "0"], "wert": "04:00"}])
check(g is None and z == {"zeiten": {"fenster": [["04:00", "20:00", 100]]}}, f"Startfenster des Unternehmens ({z})")
check(app.ap_unt_zeiten_aendern({"fenster": [["02:00", "20:00", 100]]}, z, [], standard=True)[0] == {}, "↺ Startfenster auf Standard")
check(app.ap_unt_zeiten_aendern({}, {}, [{"pfad": ["neu_bis", "uhr"], "wert": "15:00"}])[2], "andere Zeiten im Unternehmen nicht änderbar")

print("3) Routen + Planer-Hook")
EMIN = "22222222-2222-4222-8222-222222222222"
ZEILE = {"gruppe_id": "gr-emin", "aktiv": True, "firmen_modell": {}, "regeln": {}}
UPD = []
app.sb_select = lambda t, p: [{"id": 1, "regeln": STD, "zeiten": {"fenster": [["02:00", "20:00", 100]]}, "user_ids": []}] if t == "auto_plan_regeln" else \
    ([dict(ZEILE)] if t == "auto_plan_gruppe" else [])
app.sb_update = lambda t, f, u: (UPD.append((t, f, u)), [u])[1]
app._planer_schreib_gate = lambda: None
app.admin_gruppen_daten = lambda: {"gruppen": [{"id": "gr-emin", "name": "Emin", "verwalter_id": EMIN}, {"id": "gr-x", "name": "X", "verwalter_id": "x"}]}
from flask import jsonify as _j  # noqa: E402
with app.app.app_context():
    _403 = (_j({"ok": False, "msg": "Diese ID ist nicht im Auto-Planer"}), 403)
reg0 = app.sb_select("auto_plan_regeln", {})[0]
app._ap_zugang = lambda admin_reiter=False: (False, EMIN, reg0, _403)
c = app.app.test_client()
r = c.post("/admin/auto-plan/kernwert", json={"gruppe_id": "gr-emin", "firma": "lucidtrading", "aenderungen": [{"pfad": LU, "wert": [1300, 1400]}]})
check(r.status_code == 200 and UPD and UPD[-1][2]["regeln"] == abw, f"Verwalter Emin ändert TP seiner Gruppe ({r.status_code})")
r = c.post("/admin/auto-plan/kernwert", json={"gruppe_id": "gr-x", "firma": "lucidtrading", "aenderungen": [{"pfad": LU, "wert": [1300, 1400]}]})
check(r.status_code == 403, "Verwalter: fremdes Unternehmen → 403")
r = c.post("/admin/auto-plan/kernwert", json={"firma": "lucidtrading", "aenderungen": [{"pfad": LU, "wert": [1300, 1400]}]})
check(r.status_code == 403, "Verwalter ohne gruppe_id: Standard nie (403)")
r = c.post("/admin/auto-plan/ablaufwert", json={"gruppe_id": "gr-emin", "auto_bestaetigen": "alle"})
check(r.status_code == 400, "Schalter (Bestätigen) im Unternehmen nicht änderbar")
r = c.get("/admin/auto-plan/einstellungen")
d = r.get_json() or {}
check(r.status_code == 200 and (d.get("unternehmen") or {}).get("gruppe_id") == "gr-emin" and d.get("gruppe_darf") is True and d.get("admin") is False,
      f"GET im Login Emin: wirksame Regel seines Unternehmens ({r.status_code}, {(d.get('unternehmen') or {}).get('name')})")
ZEILE["regeln"] = abw
d = c.get("/admin/auto-plan/einstellungen").get_json() or {}
lu = next(f for f in d.get("firmen") or [] if f["namen"][0] == "lucidtrading")
check(app._unt_hol(lu, LU)[1] == [1300, 1400] and LU in (d.get("abweichung") or {}).get("firmen", {}).get("lucidtrading", []),
      "GET zeigt die Abweichung wirksam und markiert sie")
ZEILE.pop("regeln")
r = c.post("/admin/auto-plan/kernwert", json={"gruppe_id": "gr-emin", "firma": "lucidtrading", "aenderungen": [{"pfad": LU, "wert": [1300, 1400]}]})
check(r.status_code == 409 and "noch nicht freigeschaltet" in (r.get_json() or {}).get("msg", ""), f"Spalte regeln fehlt → klare Meldung „noch nicht freigeschaltet“ ({r.status_code})")
UPD.clear()
r = c.post("/admin/auto-plan/kernwert", json={"gruppe_id": "gr-emin", "firma": "fundednextfutures", "aenderungen": [{"pfad": ["planen"], "wert": True}]})
check(r.status_code == 200 and UPD and "regeln" not in UPD[-1][2] and UPD[-1][2].get("firmen_modell") == {"fundednextfutures": "orbit_v2"},
      f"ohne Spalte regeln: Firma an/aus geht trotzdem (nur firmen_modell geschrieben) ({r.status_code})")
r = c.post("/admin/auto-plan/ablaufwert", json={"gruppe_id": "gr-emin", "zeiten": [{"pfad": ["fenster", "0", "0"], "wert": "04:00"}]})
check(r.status_code == 409 and "noch nicht freigeschaltet" in (r.get_json() or {}).get("msg", ""), "ohne Spalte regeln: Startfenster → klare Meldung")
_h = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("Einstellungen je Unternehmen noch nicht freigeschaltet</b>" in _h and "spalte_regeln === false) ? [] : (D.unt_felder" in _h,
      "Frontend: ohne Spalte nur Anzeige + Hinweis „noch nicht freigeschaltet“")
ZEILE["regeln"] = abw
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
ap = src[src.index("\ndef ap_planen("):src.index("\ndef ", src.index("\ndef ap_planen(") + 10)]
check("reg = ap_reg_unternehmen(reg, (sb_select(\"auto_plan_gruppe\"" in ap and "if gruppe:" in ap, "ap_planen: Gruppen-Lauf plant mit der wirksamen Regel des Unternehmens")
eff = app.ap_reg_unternehmen({"regeln": STD, "zeiten": {"fenster": [["02:00", "20:00", 100]]}}, {"regeln": abw, "firmen_modell": {"fundednextfutures": "orbit_v2"}})
check(hol(eff["regeln"], "lucidtrading", LU) == [1300, 1400] and next(f for f in eff["regeln"]["firmen"] if f["namen"][0] == "fundednextfutures")["planen"] is True,
      "ap_reg_unternehmen: TP-Abweichung + FNF an in einem Stück")
check(app.ap_reg_unternehmen({"regeln": STD}, None) == {"regeln": STD}, "HT (keine Unternehmens-Zeile) → Standard unverändert")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("data-e3-std=" in html and "data-e3-unt=" in html and "'?unternehmen=' + encodeURIComponent(_e3.untWahl)" in html
      and "&& (!_e3.untFelder || ((_e3.untFelder.has(feld) || feld === 'planen') && !(pfad || []).some(k => k === 'kette' || k === 'gewinntage')))" in html
      and "e3An(feld_, an, admin && !D.unternehmen)" in html, "Frontend: Unternehmen wählen, nur Phase-1-Felder (ohne Kette/Mindesttage), ↺ je Feld, Hedge-Schalter nur Anzeige")

print("4) Fremd-Review: Grenzen, fail-closed, Wachen")
check(not app.ap_unt_feld_ok(["kette", "menge"]) and not app.ap_unt_feld_ok(["gewinntage", "tp"]) and app.ap_unt_feld_ok(LU),
      "Topstep-Kette und Mindesttage bleiben Standard (Trade 2 der Kette kommt aus dem Standard)")
_cfd = [{"namen": ["ftmo"], "route": "mt5", "planen": False}, {"namen": ["topstep"], "route": "tsv2", "planen": False}]
check(all(app.ap_unt_kernwert(_cfd, {}, {}, k, [{"pfad": ["planen"], "wert": True}])[3] for k in ("ftmo", "topstep")),
      "CFD / Topstep V2, die der Standard nicht plant: im Unternehmen nicht anschaltbar (kein Modell wählbar)")
check("return {\"ok\": False, \"msg\": f\"Regel des Unternehmens nicht lesbar" in ap, "Planer-Hook fail-closed: Gruppen-Zeile nicht lesbar → Gruppe plant nicht (nie still mit HT-Werten)")
_alt_upd = app.sb_update
app.sb_update = lambda t, f, u: []
r = c.post("/admin/auto-plan/kernwert", json={"gruppe_id": "gr-emin", "firma": "lucidtrading", "aenderungen": [{"pfad": LU, "wert": [1300, 1400]}]})
ZEILE["regeln_at"] = "2026-11-05T06:00:00+00:00"   # eigener Stempel (Prüfer S2), nicht updated_at
r = c.post("/admin/auto-plan/kernwert", json={"gruppe_id": "gr-emin", "firma": "lucidtrading", "aenderungen": [{"pfad": LU, "wert": [1300, 1400]}]})
r2 = c.post("/admin/auto-plan/ablaufwert", json={"gruppe_id": "gr-emin", "zeiten": [{"pfad": ["fenster", "0", "0"], "wert": "04:00"}]})
app.sb_update = _alt_upd
check(r.status_code == 409 and r2.status_code == 409, f"gleichzeitig geändert (updated_at-Guard) → 409, nichts überschrieben ({r.status_code}/{r2.status_code})")
_fm = ZEILE.pop("firmen_modell")
r = c.post("/admin/auto-plan/kernwert", json={"gruppe_id": "gr-emin", "firma": "fundednextfutures", "aenderungen": [{"pfad": ["planen"], "wert": True}]})
ZEILE["firmen_modell"] = _fm
check(r.status_code == 503, f"Firma an ohne Spalte firmen_modell → 503 statt stillem ok ({r.status_code})")
GR = [{"gruppe_id": "gr-emin", "ids": frozenset({EMIN})}]
_reg = {"regeln": STD, "zeiten": {"fenster": [["02:00", "20:00", 100]]}, "user_ids": ["h1"]}
je, gs = app.ap_unt_je_uid(_reg, GR, {"gr-emin": {"regeln": abw, "firmen_modell": {}}})
check(hol(app.ap_unt_wache_reg(_reg, EMIN, je, gs)["regeln"], "lucidtrading", LU) == [1300, 1400] and app.ap_unt_wache_reg(_reg, "h1", je, gs) is _reg,
      "Wachen: Gruppen-ID misst an der Regel ihres Unternehmens, HT-ID am Standard")
_ss = app.sb_select
app.sb_select = lambda t, p: (_ for _ in ()).throw(RuntimeError("DB weg"))
je, gs = app.ap_unt_je_uid(_reg, GR)
app.sb_select = _ss
check(app.ap_unt_wache_reg(_reg, EMIN, je, gs) is None and app.ap_unt_wache_reg(_reg, "h1", je, gs) is _reg, "Gruppen-Zeilen nicht lesbar → Wachen fassen Gruppen-Pläne nicht an")
_apg = app.ap_planer_gruppen
app.ap_planer_gruppen = lambda nur_aktiv=False: (_ for _ in ()).throw(RuntimeError("DB weg"))
je, gs = app.ap_unt_je_uid(_reg)
app.ap_planer_gruppen = _apg
check(gs is None and app.ap_unt_wache_reg(_reg, EMIN, je, gs) is None and app.ap_unt_wache_reg(_reg, "h1", je, gs) is _reg, "Gruppen gar nicht lesbar → nur HT-IDs")

# Mengen-Wache echt: Emin Lucid 50k mit Kontrakten 2–2 (Abweichung), Standard 1–1 → Emins Plan mit 2 bleibt, HT-Plan mit 2 → 1
abw_m = {"firmen": {"lucidtrading": {"je_groesse": {"50000": {"phasen": {"challenge": {"menge": [2, 2]}}}}}}}
_konto = lambda i, u: {"id": i, "user_id": u, "firm": "Lucid Trading", "account_type": "challenge", "starting_balance": 50000, "max_drawdown": 2000, "name": "50k"}  # noqa: E731
_pl = lambda i, k, u: {"id": i, "user_id": u, "master_account_id": k, "master_firm": "Lucid Trading", "route": "tvv2", "master_contracts": 2, "master_tp": 1500,  # noqa: E731
                       "notes": "Auto-Planer · Balance 50.000", "start_um": "2026-11-05T12:00:00Z", "richtung": "buy", "mt5_baseline": {}}
MW = []
app._sb_all = lambda t, p: [_pl("pe", "ke", EMIN), _pl("ph", "kh", "h1")] if t == "trade_plans" else []
app._ap_konten_laden = lambda p: [_konto("ke", EMIN), _konto("kh", "h1")]
app.ap_planer_gruppen = lambda nur_aktiv=False: [{"gruppe_id": "gr-emin", "ids": frozenset({EMIN}), "aktiv": True}]
app.sb_select = lambda t, p: [{"gruppe_id": "gr-emin", "regeln": abw_m, "firmen_modell": {}}] if t == "auto_plan_gruppe" else []
app.sb_update = lambda t, f, u: (MW.append((f["id"], u)), [u])[1]
app._sb_anfrage = lambda *a, **k: None
app._sb_pruefen = lambda r: None
from datetime import datetime as _dt, timezone as _tz  # noqa: E402
out = app.ap_menge_wache(_dt(2026, 11, 5, 6, 0, tzinfo=_tz.utc), {"regeln": STD, "user_ids": ["h1"]})
check([m[0] for m in MW] == ["eq.ph"] and MW[0][1]["master_contracts"] == 1,
      f"Mengen-Wache: Emins Plan (2 Kontrakte = seine Regel) bleibt, HT-Plan 2 → 1 nach Standard ({MW})")

print("5) Kontoliste je Unternehmen (Finn-Foto Login Emin .2065: „0 im Planer“ bei jeder Firma)")
KS = []
app.ap_konten_stand = lambda r: KS.append(sorted(r.get("user_ids") or [])) or [{"id": "k" + u[:2], "user_id": u, "firma": "lucidtrading"} for u in r.get("user_ids") or []]
app.ap_planer_gruppen = lambda nur_aktiv=False: [{"gruppe_id": "gr-emin", "ids": frozenset({EMIN, "jona"}), "aktiv": True}]
app.sb_select = lambda t, p: [dict(ZEILE)] if t == "auto_plan_gruppe" else []
app._ap_ks_cache.clear()
r = c.get("/admin/auto-plan/konten-stand")
d = r.get_json() or {}
check(r.status_code == 200 and d.get("unternehmen") == "gr-emin" and KS[-1] == sorted([EMIN, "jona"]) and len(d.get("konten") or []) == 2,
      f"Verwalter Emin: Konten aller IDs seiner Gruppe ({r.status_code}, {KS[-1:]}) statt 403 → „0 im Planer\"")
app._ap_zugang = lambda admin_reiter=False: (True, "admin", reg0, None)
app._ap_ks_cache.clear()
r = c.get("/admin/auto-plan/konten-stand?unternehmen=gr-emin")
r0 = c.get("/admin/auto-plan/konten-stand")
check(r.status_code == 200 and (r.get_json() or {}).get("unternehmen") == "gr-emin" and r0.status_code == 200 and (r0.get_json() or {}).get("unternehmen") is None
      and KS[-1] == [], f"Admin: ?unternehmen= → Konten der Gruppe, ohne → Standard wie bisher (HT user_ids) ({KS})")
check("'/konten-stand' + (_e3.untWahl ? '?unternehmen=' + encodeURIComponent(_e3.untWahl) : '')" in html, "Frontend lädt die Kontoliste des gewählten Unternehmens")

print("7) Prüfer S2 zu UNT1: Stempel regeln_at, Nachplanen fail-safe")
check(app.ap_unt_stempel({"regeln_at": None}, "T") == ({"regeln_at": "is.null"}, {"regeln_at": "T"}) and app.ap_unt_stempel({"regeln_at": "A"}, "T")[0] == {"regeln_at": "eq.A"}
      and app.ap_unt_stempel({"updated_at": "X"}, "T") == ({}, {}), "Guard + Stempel über regeln_at; Spalte fehlt → kein Guard (updated_at setzt jeder Lauf)")
_np = src[src.index("\ndef ap_gruppen_nachplan_tick("):src.index("\ndef ", src.index("\ndef ap_gruppen_nachplan_tick(") + 10)]
check('sb_select("auto_plan_gruppe", {"select": "*"})' in _np and 'z.get("regeln_at")' in _np and "zeilen_g = {}" in _np,
      "Gruppen-Nachplanen: select * (ohne Spalte regeln kein 400), Lesefehler → Standard statt Abbruch, „Regel geändert\" = regeln_at")
check("Firmen an · anklicken" in html and "'Konto' : 'Konten'} im Planer" in html, "Kopf „n von m Firmen an“, Zeilen „n Konten im Planer“ (Finn-Foto Emin)")

print("6) Phase 2 (UNT3): alle Konto-Leser über ap_unt_firmen / ap_regel_unternehmen")
K0 = {"ok": True, "gid_von": {EMIN: "gr-emin"}, "zeilen": {"gr-emin": {"regeln": {}, "firmen_modell": {}}}, "ht": frozenset({"h1"}), "memo": {}}
check(app.ap_unt_firmen("h1", FIRMEN, K0) is FIRMEN and app.ap_unt_firmen(EMIN, FIRMEN, K0) is FIRMEN and app.ap_unt_firmen("fremd", FIRMEN, K0) is FIRMEN,
      "ohne Abweichung: HT, Emin und IDs ohne Unternehmen bekommen DIESELBE Liste (bitgleich)")
K1 = dict(K0, zeilen={"gr-emin": {"regeln": abw, "firmen_modell": {}}}, memo={})
e1 = app.ap_unt_firmen(EMIN, FIRMEN, K1)
check(hol({"firmen": e1}, "lucidtrading", LU) == [1300, 1400] and app.ap_unt_firmen(EMIN, FIRMEN, K1) is e1 and app.ap_unt_firmen("h1", FIRMEN, K1) is FIRMEN,
      "mit Abweichung: Emin seine Regel (gemerkt je Takt), HT Standard")
check(app.ap_regel_unternehmen(EMIN, FIRMEN, "Lucid Trading", K1)["je_groesse"]["50000"]["phasen"]["challenge"]["tp"] == [1300, 1400],
      "ap_regel_unternehmen(uid, firmen, firm) = Regel der Firma im Unternehmen der ID")
K2 = dict(K0, ok=False)
check(app.ap_unt_firmen(EMIN, FIRMEN, K2) == [] and app.ap_unt_firmen("h1", FIRMEN, K2) is FIRMEN and app.ap_unt_firmen(EMIN, FIRMEN, K2, streng=False) is FIRMEN,
      "Kontext unbekannt: schreibende Leser (streng) überspringen Nicht-HT-Konten, Anzeigen rechnen Standard")
app._ap_unt_ktx.update(bis=0)
check(app.ap_unt_kontext().get("ohne_key") is True and app.ap_unt_firmen(EMIN, FIRMEN) is FIRMEN, "ohne Service-Key (Tests, lokal): kein Unternehmen → Standard, keine Abfrage")
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
def fn(name):
    i = src.index("\ndef " + name + "(")
    return src[i:src.index("\ndef ", i + 5)]
LESER = {"zw_tick": "ap_regel_unternehmen(a.get(\"user_id\")", "_ap_blow_beim_abhaken": "ap_regel_unternehmen(", "ap_blow_auto_tick": "ap_regel_unternehmen(",
         "ap_normal_auto_tick": "ap_regel_unternehmen(", "admin_build_kontowerte": "ap_unt_firmen(a.get(\"user_id\")", "ah_tick": "fa = ap_unt_firmen(",
         "_eh_tick_lauf": "ap_unt_firmen(", "ehv_tick": "ap_unt_firmen(", "tfh_tick": "ap_unt_firmen(", "ap_echo_hedge_anlegen": "ap_unt_firmen(",
         "ap_kette_tick": "ap_regel_unternehmen(t1.get(\"user_id\")", "ap_kette_abhaken": "ap_regel_unternehmen(", "vorrat2_rechnen_lauf": "ap_unt_firmen(uid",
         "konto_dd_vorschlag": "ap_unt_firmen(", "admin_live_trades": "ap_unt_firmen(p.get(\"user_id\")", "_ap_stand_laden": "ap_unt_firmen(",
         "_ap_bewerten": "ap_regel_unternehmen(", "admin_hypo_bilanz": "ap_unt_firmen(", "konto_ziele": "ap_unt_firmen(a.get(\"user_id\")",
         "admin_build_overview": "ap_unt_firmen(a_.get(\"user_id\")", "puls_heim_pruefen": "ap_unt_firmen(", "admin_auto_plan_hedge_freigabe": "ap_unt_firmen(",
         "gp_planen": "ap_unt_regeln({\"firmen\": firmen}"}
abw_b = {"firmen": {"lucidtrading": {"je_groesse": {"50000": {"phasen": {"challenge": {"menge": [2, 2]}}}}}}}
KAB = {"ok": True, "gid_von": {EMIN: "gr-emin", "b1": "gr-b"}, "zeilen": {"gr-emin": {"regeln": abw, "firmen_modell": {}},
       "gr-b": {"regeln": abw_b, "firmen_modell": {}}}, "ht": frozenset({"h1"}), "memo": {}}
eA = app.ap_unt_firmen(EMIN, FIRMEN, KAB)
mb = ["je_groesse", "50000", "phasen", "challenge", "menge"]
check(app.ap_unt_firmen("h1", eA, KAB) is FIRMEN and app.ap_unt_firmen(EMIN, eA, KAB) is eA
      and hol({"firmen": app.ap_unt_firmen("b1", eA, KAB)}, "lucidtrading", LU) == [1450, 1500]
      and hol({"firmen": app.ap_unt_firmen("b1", eA, KAB)}, "lucidtrading", mb) == [2, 2],
      "Fremd-Review: schon wirksame Liste (Gruppen-Lauf A) → HT rechnet Standard, Gruppe B Standard + B (nie A + B)")
rA = app.ap_reg_unternehmen({"regeln": {"firmen": FIRMEN}}, {"gruppe_id": "gr-emin", "regeln": abw, "firmen_modell": {}})
check(app.ap_unt_firmen("h1", rA["regeln"]["firmen"], KAB) is FIRMEN, "ap_reg_unternehmen (Planer-Lauf) trägt die Kennung ebenso")
app.sb_select = lambda t, p: [dict(ZEILE, regeln={}, firmen_modell={})] if t == "auto_plan_gruppe" else (
    [{"id": 1, "regeln": STD, "zeiten": {"fenster": [["02:00", "20:00", 100]]}, "user_ids": []}] if t == "auto_plan_regeln" else [])
app.sb_update = lambda t, f, u: [u]
app._ap_zugang = lambda admin_reiter=False: (False, EMIN, reg0, _403)
app.admin_gruppen_daten = lambda: {"gruppen": [{"id": "gr-emin", "name": "Emin", "verwalter_id": EMIN}]}
r = c.post("/admin/auto-plan/kernwert", json={"gruppe_id": "gr-emin", "firma": "lucidtrading", "aenderungen": [{"pfad": ["je_groesse", "50000", "dd_usd"], "wert": 2500}]})
check(r.status_code == 200 and "Accounts" in str((r.get_json() or {}).get("hinweis")), f"Max DD im Unternehmen gespeichert → Hinweis auf das Max DD der Konten ({r.status_code})")
fehlt = [k for k, m in LESER.items() if m not in fn(k)]
check(not fehlt, f"{len(LESER)} Konto-Leser lesen die Regel des Unternehmens ({fehlt or 'alle'})")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER:\n  - " + "\n  - ".join(FEHLER))
sys.exit(1 if FEHLER else 0)
