#!/usr/bin/env python3
"""Selbsttest ORBIT PRIO 2 (MO1, 05.11.2026, Finn „ja bau ma“): der Apex-Challenge-Weg (ah_tick: Marke hedge_art 'apex', Vorschau, Umstellen auf den
WD-Weg mit Fusion-Hedge) heißt „Orbit Prio 2“ und ist je Firma wählbar (regeln.firmen[].modell, Gruppe: auto_plan_gruppe.firmen_modell).
Prüft mit den echten Firmen-Regeln (Apex, Lucid, Tradeify — live gelesen 05.11.2026, tools/selftest_orbit_prio2_firmen.json) einen ganzen ah_tick gegen
eine nachgebaute DB: (1) ohne Feld genau wie bisher — nur Apex wird vorgemerkt, Vorschau bitgleich zum alten Stand (Datei ORBIT_PRIO2_ALT, s. unten);
(2) Lucid 50k mit orbit_prio2 (HT und Emins Gruppe getrennt) → Vorschau 78 € auf 2.000 $ (Kaufpreis ÷ Max DD), Boden 48.000; (3) orbit_v2 bei Apex →
Apex nicht mehr vorgemerkt; (4) ap_modell_setzen (Grenzen, CFD fest). Ohne Netz.
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_orbit_prio2.py   (mit ORBIT_PRIO2_NUR_APEX=1 nur Fall 1 — so läuft er auch gegen einen alten Stand)"""
import copy
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []
NUR_APEX = os.environ.get("ORBIT_PRIO2_NUR_APEX") == "1"


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


FIRMEN = json.load(open(os.path.join(HIER, "selftest_orbit_prio2_firmen.json"), encoding="utf-8"))
HT, EMIN = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"
JETZT = datetime(2026, 11, 5, 6, 0, tzinfo=timezone.utc)
START = (JETZT + timedelta(minutes=60)).isoformat()
FUS = {HT: "fus-ht-0000-0000-0000-000000000001", EMIN: "fus-em-0000-0000-0000-000000000002"}

konto = lambda i, u, firm, g, bal, dll: {"id": i, "user_id": u, "name": f"{g // 1000}k {i[-4:]} → Challenge", "firm": firm, "account_type": "challenge",   # noqa: E731
                                         "starting_balance": g, "external_id": "EXT" + i[-4:], "max_drawdown": {50000: 2000, 100000: 3000, 150000: 4500}.get(g), "max_daily_drawdown": dll, "_bal": bal}
KONTEN = [konto("a0000000-0000-4000-8000-00000000a150", HT, "Apex Trader", 150000, 150000.0, 2000),
          konto("a0000000-0000-4000-8000-00000000a100", HT, "Apex Trader", 100000, 100400.0, 1500),
          konto("a0000000-0000-4000-8000-00000000c050", HT, "Lucid Trading", 50000, 50000.0, None),
          konto("a0000000-0000-4000-8000-00000000e050", EMIN, "Lucid Trading", 50000, 50000.0, None),
          konto("a0000000-0000-4000-8000-00000000d150", HT, "Tradeify", 150000, 150000.0, None)]
plan = lambda k, kt=2, tp=9000: {"id": "p" + k["id"][-8:], "user_id": k["user_id"], "master_account_id": k["id"], "master_name": k["name"],   # noqa: E731
                                 "master_firm": k["firm"], "master_contracts": kt, "master_symbol": "NQZ6", "master_symbol_root": "NQ", "master_tp": tp,
                                 "master_risk": None, "slave_risk": None, "multiplier": None, "hedge_faktor": None, "richtung": "buy", "start_um": START,
                                 "notes": "Auto-Planer", "mt5_baseline": {}, "updated_at": "2026-11-05T05:00:00+00:00", "auto_bestaetigt_at": None,
                                 "hedge_freigabe_at": None}
PLAENE = [plan(KONTEN[0]), plan(KONTEN[1]), plan(KONTEN[2], 1, 1500), plan(KONTEN[3], 1, 1500), plan(KONTEN[4], 2, 3500)]
ZUSTAND = {"firmen": FIRMEN, "gruppe": {}, "geschrieben": []}


LIQ_REGELN = [{"id": 12, "firma": "Lucid Trading", "kontotyp": None, "groesse": None, "art": None, "betrag_usd": None, "lock_ueber_start_usd": None,
               "stufen": None, "wie_kontotyp": None, "maxdd_art": "eod_trailing", "maxdd_lock_ueber_groesse_usd": None, "maxdd_usd": None}]
VERLAUF = []


def sb_all(t, p):
    if t == "liq_regeln":
        return LIQ_REGELN
    if t == "trade_plans" and "bal_end" in str(p.get("select") or ""):
        return [dict(x) for x in VERLAUF]
    if t == "trade_plans":
        if "mt5_baseline->apex_hedge->>status" in p:
            return []
        return [copy.deepcopy(x) for x in PLAENE]
    if t == "accounts":
        ids = str(p.get("id") or "")
        return [{k: v for k, v in a.items() if k != "_bal"} for a in KONTEN if a["id"] in ids] + \
               [{"id": f, "name": "Fusion", "firm": "Fusion Markets", "external_id": "L" + f[-4:]} for f in FUS.values() if f in ids]
    if t == "user_settings":
        return [{"user_id": u, "value": {"accountId": f, "hedgeLogin": "L" + f[-4:]}} for u, f in FUS.items()]
    return []


def sb_select(t, p):
    if t == "auto_plan_gruppe":
        return [{"gruppe_id": "gr-emin", "aktiv": True, "zeiten": {}, "letzter_lauf": None, "firmen_modell": ZUSTAND["gruppe"]}]
    return []


def sb_update(t, flt, upd):
    ZUSTAND["geschrieben"].append((flt.get("id"), upd))
    return [dict(upd, updated_at="2026-11-05T06:00:01+00:00")]


app._eh_regeln = lambda: {"firmen": ZUSTAND["firmen"], "apex_hedge": {"an": True}}
app._sb_all = sb_all
app.sb_select = sb_select
app.sb_update = sb_update
app._ap_namen = lambda: ({HT: "HT", EMIN: "Emin"}, {EMIN})
app.ap_planer_gruppen_ids = lambda: {EMIN}
app.ap_planer_gruppen = lambda nur_aktiv=False: [{"gruppe_id": "gr-emin", "name": "Emin", "ids": frozenset({EMIN}), "aktiv": True, "letzter_lauf": None}]
app.gp_hedge_settings_eigen = lambda rows: rows
app._ap_balance_karten = lambda: ({}, {})
app.acc_balance_wahl = lambda a, e, d: (next(k["_bal"] for k in KONTEN if k["id"] == a["id"]), "USD", "test", None)
app._ap_kauf_echt = lambda ids: {}
app.alarm_senden = lambda *a, **k: None


def lauf(firmen=None, gruppe=None):
    ZUSTAND.update(firmen=firmen if firmen is not None else FIRMEN, gruppe=gruppe or {}, geschrieben=[])
    app._liq_verlauf_cache.clear()
    app._liq_regeln_cache.update(at=0.0, zeilen=None)
    erg = app.ah_tick(jetzt=JETZT, force=True)
    vs = {str(pid)[3:]: (u.get("mt5_baseline") or {}).get("hedge_vorschau") for pid, u in ZUSTAND["geschrieben"]
          if (u.get("mt5_baseline") or {}).get("hedge_art") == "apex"}
    return erg, vs


def mit_modell(firmen, schluessel, modell):
    out = copy.deepcopy(firmen)
    for f in out:
        if (f.get("namen") or [None])[0] == schluessel:
            f["modell"] = modell
    return out


ID = lambda k: "p" + k["id"][-8:]   # noqa: E731
A150, A100, LHT, LEM, TF = (ID(k) for k in KONTEN)
ohne_at = lambda v: {k: x for k, x in (v or {}).items() if k != "at"}   # noqa: E731

print("1) ohne Feld — wie bisher: nur Apex")
erg, vs = lauf()
check(sorted(vs) == sorted([A150, A100]), f"vorgemerkt nur die beiden Apex-Pläne ({sorted(vs)})")
print("     Apex 150k:", json.dumps(ohne_at(vs.get(A150)), sort_keys=True))
print("     Apex 100k:", json.dumps(ohne_at(vs.get(A100)), sort_keys=True))
SOLL_DATEI = os.environ.get("ORBIT_PRIO2_ALT")
if SOLL_DATEI and os.path.exists(SOLL_DATEI):
    alt = json.load(open(SOLL_DATEI, encoding="utf-8"))
    check(alt == {k: ohne_at(v) for k, v in vs.items()}, "Apex-Vorschau bitgleich zum alten Stand (ORBIT_PRIO2_ALT)")
elif SOLL_DATEI:
    json.dump({k: ohne_at(v) for k, v in vs.items()}, open(SOLL_DATEI, "w", encoding="utf-8"), sort_keys=True, indent=1)
    print("     (alter Stand geschrieben:", SOLL_DATEI + ")")
if NUR_APEX:
    print("\nALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
    sys.exit(1 if FEHLER else 0)

print("2) Lucid 50k mit orbit_prio2")
erg, vs = lauf(firmen=mit_modell(FIRMEN, "lucidtrading", "orbit_prio2"))
check(sorted(vs) == sorted([A150, A100, LHT]), f"HT-Regel Lucid = Prio 2 → HT-Lucid dazu, Emins Lucid nicht (eigene Gruppe) ({sorted(vs)})")
v = vs.get(LHT) or {}
check(v.get("eur") == 78.0 and v.get("polster_usd") == 2000.0 and v.get("liq_balance") == 48000.0,
      f"Lucid 50k: Kontowert {v.get('eur')} € auf Polster {v.get('polster_usd')} $ (Kaufpreis ÷ Max DD = 78 ÷ 2.000), Boden {v.get('liq_balance')}")
nf = app.AH_STANDARD["netto_faktor"]
check(v.get("abstand_usd") == 2000.0 and v.get("blow_eur") == round(78.0 / nf, 2),
      f"Abstand {v.get('abstand_usd')} $ bis zum Boden, Blow {v.get('blow_eur')} € = 78 ÷ Netto-Faktor {nf} (wie Apex: 150 → {ohne_at(lauf()[1].get(A150)).get('blow_eur')})")
print("     Lucid 50k:", json.dumps(ohne_at(v), sort_keys=True))
KONTEN[2]["max_daily_drawdown"] = 1200          # live: alle Lucid-50k-Challenges tragen 1.200 $ Daily Loss (SELECT 05.11.2026)
_v = lauf(firmen=mit_modell(FIRMEN, "lucidtrading", "orbit_prio2"))[1].get(LHT) or {}
KONTEN[2]["max_daily_drawdown"] = None
check(_v.get("abstand_usd") == 1200.0 and _v.get("polster_usd") == 2000.0 and _v.get("blow_eur") == round(78.0 / nf, 2) and _v.get("liq_balance") == 48000.0,
      f"Lucid 50k mit Daily Loss 1.200 $: Hedge auf den Abstand bis zum Tagesende ({_v.get('abstand_usd')} $), Blow weiter {_v.get('blow_eur')} €, Boden {_v.get('liq_balance')}")
erg, vs2 = lauf(firmen=FIRMEN, gruppe={"lucidtrading": "orbit_prio2"})
check(sorted(vs2) == sorted([A150, A100, LEM]), f"Gruppen-Feld Lucid = Prio 2 → nur Emins Lucid dazu, HT bleibt Orbit V2 ({sorted(vs2)})")
check(ohne_at(vs2.get(LEM)) == dict(ohne_at(v), lots=(vs2.get(LEM) or {}).get("lots")) and (vs2.get(LEM) or {}).get("eur") == 78.0,
      "Emins Lucid: dieselbe Rechnung wie HT-Lucid")
check(ohne_at(vs2.get(A150)) == ohne_at(lauf()[1].get(A150)), "Apex unverändert, wenn Lucid umgestellt ist")

print("3) Apex auf orbit_v2 / ungültige Werte")
erg, vs = lauf(firmen=mit_modell(FIRMEN, "apextrader", "orbit_v2"))
check(not vs, f"Apex = Orbit V2 → nichts vorgemerkt ({sorted(vs)})")
erg, vs = lauf(firmen=mit_modell(FIRMEN, "apextrader", "quatsch"), gruppe={"apextrader": "quatsch"})
check(sorted(vs) == sorted([A150, A100]), "ungültiger Wert → Standard (Apex Prio 2)")
erg, vs = lauf(gruppe={"apextrader": "orbit_v2"})
check(sorted(vs) == sorted([A150, A100]), "Gruppen-Feld gilt nur der Gruppe (HT-Apex bleibt Prio 2)")

print("3b) Fremd-Review: Rückweg, Gruppen-Lesefehler, Tradeify")
# Lucid war Prio 2 und ist vorgemerkt (hedge_art apex, nicht umgestellt) → Finn stellt auf Orbit V2 zurück → Marke + Vorschau weg, kein Vormerken mehr
_alt = copy.deepcopy(PLAENE)
PLAENE[2]["mt5_baseline"] = {"hedge_art": "apex", "hedge_vorschau": {"lots": 1.03}, "x": 1}
erg, vs = lauf()
weg = [u for pid, u in ZUSTAND["geschrieben"] if str(pid)[3:] == LHT]
check(LHT not in vs and weg and weg[0]["mt5_baseline"] == {"x": 1}, f"Modell zurück auf Orbit V2: Marke + Vorschau entfernt, übrige Felder bleiben ({weg[:1]})")
PLAENE[2]["mt5_baseline"] = {"hedge_art": "apex", "apex_hedge": {"status": "mit"}}
erg, vs = lauf()
check(not [u for pid, u in ZUSTAND["geschrieben"] if str(pid)[3:] == LHT], "schon umgestellter Plan (status mit) bleibt unangetastet")
PLAENE[:] = _alt
_pg = app.ap_planer_gruppen
def _kaputt(nur_aktiv=False):
    raise RuntimeError("DB weg")
app.ap_planer_gruppen = _kaputt
erg, vs = lauf(firmen=mit_modell(FIRMEN, "lucidtrading", "orbit_prio2"))
app.ap_planer_gruppen = _pg
check(LHT in vs and LEM not in vs and A150 in vs, f"Gruppen nicht lesbar: Emins Lucid fällt NICHT auf die HT-Regel (Standard je Firma), HT/Apex wie immer ({sorted(vs)})")
# Prüfer MO1: vorgemerkter Emin-Lucid-Plan (Gruppe Prio 2) + auto_plan_gruppe nicht lesbar → Marke bleibt (kein Wegräumen bei Lesefehler)
_alt2 = copy.deepcopy(PLAENE)
PLAENE[3]["mt5_baseline"] = {"hedge_art": "apex", "hedge_vorschau": {"lots": 1.03}}
_sel0 = app.sb_select
def _sel_kaputt(t, p):
    if t == "auto_plan_gruppe":
        raise RuntimeError("DB weg")
    return _sel0(t, p)
app.sb_select = _sel_kaputt
erg, vs = lauf()
app.sb_select = _sel0
check(not [u for pid, u in ZUSTAND["geschrieben"] if str(pid)[3:] == LEM], "auto_plan_gruppe nicht lesbar → Emins vorgemerkte Marke bleibt stehen")
PLAENE[:] = _alt2
check(app.ap_modell_setzen(FIRMEN, "tradeify", "orbit_prio2")[1] and app.ap_firma_modell(dict(FIRMEN[0], modell="orbit_prio2"), "Tradeify") == "orbit_v2",
      "Tradeify nicht wählbar (eigener Final-Hedge) — auch ein Hand-Feld wirkt nicht")
check(app.ap_modell_setzen([{"namen": ["topstep"], "route": "tsv2"}], "topstep", "orbit_prio2")[1], "Topstep V2 nicht wählbar")
erg, vs = lauf(firmen=mit_modell(FIRMEN, "tradeify", "orbit_prio2"))
check(TF not in vs, "Tradeify mit Hand-Feld orbit_prio2 wird nicht vorgemerkt")

print("3c) MO1b: Boden am EOD-Hoch (nachziehend), Waage, Gruppen-Route")
# Lucid 50k: EOD-Hoch 50.800 (gestern Ende), jetzt 50.300 → echter Boden 48.800 → Polster 1.500, Wert = 78/2.000 × 1.500 = 58,50 €
VERLAUF[:] = [{"id": "alt1", "master_account_id": KONTEN[2]["id"], "konto_typ": "challenge", "started_at": "2026-11-03T14:00:00+00:00",
               "ended_at": "2026-11-03T15:00:00+00:00", "bal_start": 50000.0, "bal_end": 50800.0}]
KONTEN[2]["_bal"] = 50300.0
_v = lauf(firmen=mit_modell(FIRMEN, "lucidtrading", "orbit_prio2"))[1].get(LHT) or {}
_satz = app.ap_kontowert_konto(KONTEN[2], 50300.0, mit_modell(FIRMEN, "lucidtrading", "orbit_prio2"))["satz_eur_pro_usd"]
check(_v.get("liq_balance") == 48800.0 and _v.get("polster_usd") == 1500.0 and _v.get("eur") == round(_satz * 1500, 2) and _v.get("abstand_usd") == 1500.0,
      f"Lucid unter EOD-Hoch: Boden {_v.get('liq_balance')} (50.800 − 2.000), Polster {_v.get('polster_usd')} $, Wert {_v.get('eur')} € = Satz {_satz} × 1.500, Abstand {_v.get('abstand_usd')} $")
KONTEN[2]["_bal"] = 51200.0                       # heute über dem EOD-Hoch: Intraday zählt NICHT, Boden bleibt 48.800 → Polster 2.000 (Kontowert-Rechnung)
_v = lauf(firmen=mit_modell(FIRMEN, "lucidtrading", "orbit_prio2"))[1].get(LHT) or {}
check(_v.get("liq_balance") == 48800.0 and _v.get("polster_usd") == 2400.0, f"über dem EOD-Hoch (heute +400): Boden bleibt {_v.get('liq_balance')} (Intraday zählt nicht), Polster {_v.get('polster_usd')} $ bis zur echten Liquidation")
VERLAUF[0]["bal_end"] = 52600.0; KONTEN[2]["_bal"] = 52000.0     # Lock bei Start: Boden höchstens 50.000 (Kernwerte lock_bei_start)
_v = lauf(firmen=mit_modell(FIRMEN, "lucidtrading", "orbit_prio2"))[1].get(LHT) or {}
check(_v.get("liq_balance") == 50000.0 and _v.get("polster_usd") == 2000.0, f"EOD-Hoch 52.600 → Boden gelockt bei 50.000 (nicht 50.600) — Polster {_v.get('polster_usd')} $")
KONTEN[2]["_bal"] = 48700.0
_e, _v = lauf(firmen=mit_modell(FIRMEN, "lucidtrading", "orbit_prio2"))
check((_v.get(LHT) or {}).get("code") == "polster" and "lots" not in (_v.get(LHT) or {}),
      f"Balance unter dem EOD-Boden → kein Hedge, vorgemerkt mit Grund „polster“ (Riegel hält, wie Apex) ({(_v.get(LHT) or {}).get('fehler')})")
VERLAUF[:] = []; KONTEN[2]["_bal"] = 50000.0
check(ohne_at(lauf()[1].get(A150)) == ohne_at(json.load(open(SOLL_DATEI, encoding="utf-8"))[A150]) if SOLL_DATEI and os.path.exists(SOLL_DATEI) else True,
      "Apex (statisch) bleibt mit Liq-Regeln/Verlauf bitgleich")
# Waage
w = app.ap_waage_ohne_modell({}, mit_modell(FIRMEN, "lucidtrading", "orbit_prio2"))
check(w["waage_ohne"] == ["apex", "lucidtrading", "lucid trading"] and w["waage_ohne_modell"] == ["lucidtrading", "lucid trading"],
      f"Lucid Prio 2 → aus der Waage wie Apex ({w['waage_ohne']})")
w2 = app.ap_waage_ohne_modell(dict(w, waage_ohne=w["waage_ohne"] + ["mffu"]), FIRMEN)
check(w2["waage_ohne"] == ["apex", "mffu"] and w2["waage_ohne_modell"] == [], f"zurück auf V2 → wieder in der Waage, Hand-Einträge bleiben ({w2['waage_ohne']})")
check(app.ap_waage_ohne_modell({"waage_ohne": []}, FIRMEN)["waage_ohne"] == [], "leere Liste (alle wiegen) bleibt leer, Apex wird nicht erzwungen")
_aus = {"waage_ohne": ["apex", "lucidtrading", "lucid trading"], "waage_ohne_modell": ["lucidtrading", "lucid trading"]}
check(app.ap_waage_param_gruppe({"waage_ohne": ["apex", "lucidtrading", "lucid trading"]}, _aus, FIRMEN, {})["waage_ohne"] == ["apex"],
      "Gruppe ohne eigenes Prio 2: HT-Lucid-Eintrag gilt ihr nicht (Lucid wiegt in der Gruppe mit)")
check(app.ap_waage_param_gruppe({"waage_ohne": ["apex"]}, {}, FIRMEN, {"lucidtrading": "orbit_prio2"})["waage_ohne"] == ["apex", "lucidtrading", "lucid trading"],
      "Gruppe mit Lucid Prio 2: Lucid raus aus IHRER Waage (DB-Riegel wiegt Gruppen nicht)")
_src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
check(_src.count("ap_waage_param_gruppe(") >= 4 and 'regeln["ausgleich"] = ap_waage_ohne_modell(' in _src,
      "verdrahtet: HT-Route pflegt waage_ohne, ap_planen (Gruppe) und Gruppen-Waage des Bots nutzen das Gruppen-Modell")
# Gruppen-Route
GR = {"gruppe_id": "gr-emin", "aktiv": True, "zeiten": {}, "letzter_lauf": None, "firmen_modell": {}}
_sel_alt = app.sb_select
def _sel(t, p):
    if t == "auto_plan_regeln":
        return [{"regeln": {"firmen": FIRMEN}}]
    if t == "auto_plan_gruppe":
        return [dict(GR)]
    return []
app.sb_select = _sel
_upd = []
app.sb_update = lambda t, flt, u: (_upd.append((t, flt, u)), [u])[1]
app._planer_schreib_gate = lambda: None
app.admin_gruppen_daten = lambda: {"gruppen": [{"id": "gr-emin", "name": "Emin", "verwalter_id": EMIN}, {"id": "gr-x", "name": "X", "verwalter_id": "x"}]}
from flask import jsonify as _j  # noqa: E402
with app.app.app_context():
    _verboten = (_j({"ok": False}), 403)
app._planer_admin_auth = lambda: ("admin@test", None)
c = app.app.test_client()
r = c.post("/admin/gruppen-plan", json={"gruppe_id": "gr-emin", "aktion": "modell", "firma": "lucidtrading", "modell": "orbit_prio2"})
check(r.status_code == 200 and _upd and _upd[-1][2]["firmen_modell"] == {"lucidtrading": "orbit_prio2"}, f"Admin setzt Emins Lucid → firmen_modell ({r.get_json()})")
r = c.post("/admin/gruppen-plan", json={"gruppe_id": "gr-emin", "aktion": "modell", "firma": "tradeify", "modell": "orbit_prio2"})
check(r.status_code == 400, "Gruppe: Tradeify abgelehnt (eigener Final-Hedge)")
app._planer_admin_auth = lambda: (None, _verboten)
app._wd_login = lambda: (EMIN, None)
_upd.clear()
r = c.post("/admin/gruppen-plan", json={"gruppe_id": "gr-emin", "aktion": "modell", "firma": "apextrader", "modell": "orbit_v2"})
check(r.status_code == 200 and _upd[-1][2]["firmen_modell"] == {"apextrader": "orbit_v2"}, "Verwalter Emin setzt das Modell seiner Gruppe")
r = c.post("/admin/gruppen-plan", json={"gruppe_id": "gr-x", "aktion": "modell", "firma": "lucidtrading", "modell": "orbit_prio2"})
check(r.status_code == 403, "Verwalter: fremde Gruppe → 403")
GR.pop("firmen_modell")
app._planer_admin_auth = lambda: ("admin@test", None)
r = c.post("/admin/gruppen-plan", json={"gruppe_id": "gr-emin", "aktion": "modell", "firma": "lucidtrading", "modell": "orbit_prio2"})
check(r.status_code == 503 and "sql/2026-11-05_orbit_prio2.sql" in (r.get_json() or {}).get("msg", ""), "Spalte fehlt → 503 mit Hinweis auf die SQL-Datei")
app.sb_select = _sel_alt
app.sb_update = sb_update
gs = app.ap_gruppen_modell_sicht(FIRMEN)
check(gs and gs[0]["modelle"] == {"tradeify": "orbit_v2", "apextrader": "orbit_prio2", "lucidtrading": "orbit_v2"}, f"Gruppen-Sicht: wirksame Modelle je Firma ({gs[:1]})")

html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
# Einstellungen im Login des Verwalters (Finn-Foto Emin: „⚠ Einstellungen: Diese ID ist nicht im Auto-Planer")
_daten = {"gruppen": [{"id": "gr-emin", "name": "Emin", "verwalter_id": EMIN}]}
_gz = {"gr-emin": {"gruppe_id": "gr-emin", "aktiv": True, "firmen_modell": {"lucidtrading": "orbit_prio2"}}}
_gsv = app.ap_einst_gruppen_sicht(EMIN, _daten, _gz, {"firmen": FIRMEN, "apex_hedge": {"an": True}})
check(_gsv and _gsv["gruppe_sicht"]["name"] == "Emin" and _gsv["gruppe_admin"] is True and _gsv["admin"] is False
      and _gsv["modelle"] == {"tradeify": "orbit_v2", "apextrader": "orbit_prio2", "lucidtrading": "orbit_prio2"},
      f"Verwalter Emin: Einstellungen seiner Gruppe mit ihren Modellen ({(_gsv or {}).get('modelle')})")
check(all(set(f) <= {"namen", "route", "groessen", "planen"} for f in _gsv["firmen"]), "Gruppen-Sicht zeigt keine HT-Kernwerte (nur Name/Weg/Größen)")
check(app.ap_einst_gruppen_sicht(HT, _daten, _gz, {"firmen": FIRMEN}) is None and app.ap_einst_gruppen_sicht(EMIN, _daten, {}, {"firmen": FIRMEN}) is None,
      "kein Verwalter / Gruppe ohne Planer-Zeile → keine Gruppen-Sicht (bleibt 403)")
check("if(D.gruppe_sicht) return `<div class=\"wd-set-card\">" in html and "const darfG = admin || D.gruppe_admin === true" in html and "if(!gs) modell = mZeile('Modell · Hermann Technologies'" in html,
      "Frontend: Gruppen-Sicht zeigt nur die Zeile der eigenen Gruppe, änderbar für den Verwalter")

print("3d) MO1c: Gruppe schaltet eine Firma an, die HT nicht plant (FundedNext Futures 50k bei Emin)")
_fnf = {"namen": ["fundednextfutures"], "route": "tvv2", "planen": False, "je_groesse": {"50000": {"dd_usd": 1500}}}
check(app.ap_gruppe_firma_an(_fnf, {"fundednextfutures": "orbit_v2"}) is True and app.ap_gruppe_firma_an(_fnf, {"fundednextfutures": "orbit_prio2"}) is True,
      "Gruppen-Eintrag Orbit V2 / Prio 2 → FNF Futures in der Gruppe AN, obwohl HT planen=false")
check(app.ap_gruppe_firma_an(_fnf, {}) is False and app.ap_gruppe_firma_an(_fnf, None) is False, "ohne Eintrag wie HT (aus)")
check(app.ap_gruppe_firma_an(FIRMEN[2], {"lucidtrading": "aus"}) is False and app.ap_gruppe_firma_an(FIRMEN[2], {}) is True, "„aus“ schaltet eine HT-Firma nur in der Gruppe aus")
check(app.ap_gruppe_modell_setzen({}, FIRMEN, "lucidtrading", "aus") == ({"lucidtrading": "aus"}, None)
      and app.ap_gruppe_modell_setzen({}, FIRMEN, "tradeify", "aus")[1], "„aus“ gespeichert; Tradeify bleibt nicht wählbar")
_src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
_ap = _src[_src.index("\ndef ap_planen("):_src.index("\ndef ", _src.index("\ndef ap_planen(") + 10)]
check("ap_gruppe_firma_an(regel, _fm_gruppe) if _fm_gruppe is not None else regel.get(\"planen\") is not False" in _ap and "_fm_gruppe = None" in _ap,
      "ap_planen: HT (gruppe=None) prüft planen wie bisher, Gruppen-Lauf über ap_gruppe_firma_an")
check("const E3_MODELLE_G = [['aus', 'aus'], ...E3_MODELLE]" in html, "Gruppen-Dropdown: aus · Orbit V2 · Orbit Prio 2")

print("4) ap_firma_modell / ap_modell_setzen / Einstellungen")
fm = {(f.get("namen") or [""])[0]: app.ap_firma_modell(f, None) for f in FIRMEN}
check(fm == {"tradeify": "orbit_v2", "apextrader": "orbit_prio2", "lucidtrading": "orbit_v2"}, f"Standard je Regel: {fm}")
check(app.ap_firma_modell(None, "Apex") == "orbit_prio2" and app.ap_firma_modell(None, "Lucid Trading") == "orbit_v2", "ohne Regel: am Firmennamen wie bisher")
neu, g = app.ap_modell_setzen(FIRMEN, "lucidtrading", "orbit_prio2")
check(g is None and [f.get("modell") for f in neu] == [None, None, "orbit_prio2"] and FIRMEN[2].get("modell") is None,
      "ap_modell_setzen: nur Lucid bekommt das Feld, Original unverändert")
check(app.ap_modell_setzen(FIRMEN, "lucidtrading", "orbit_v3")[1] and app.ap_modell_setzen(FIRMEN, "gibtsnicht", "orbit_v2")[1], "falscher Wert / unbekannte Firma → Grund")
check(app.ap_modell_setzen([{"namen": ["ftmo"], "route": "mt5v2"}], "ftmo", "orbit_prio2")[1] == "CFD-Firma — fährt immer Echo mit Hedge", "CFD fest")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("data-e3-modell=" in html and "apdApi('POST', '/modell', { firma, modell })" in html and "mSel(`data-e3-modell=\"${e3E(n)}\"`, md, nichtGrund)" in html,
      "Einstellungen: Dropdown „Modell“ speichert über /admin/auto-plan/modell, Tradeify/Topstep ausgegraut mit Grund")
check("aktion: 'modell', firma, modell }, '/admin/gruppen-plan')" in html and "data-e3-gruppe=" in html, "MO1b: Zeile je Gruppe speichert über /admin/gruppen-plan")
check("tpIstApexHedge(p) ? 'Orbit Prio 2'" in html and "'Apex-Hedge'" not in html, "Anzeige-Name „Orbit Prio 2“ statt „Apex-Hedge“")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER:\n  - " + "\n  - ".join(FEHLER))
sys.exit(1 if FEHLER else 0)
