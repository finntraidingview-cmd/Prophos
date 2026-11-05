#!/usr/bin/env python3
"""Selbsttest TRADEIFY ÜBER ORBIT PRIO 2 + EIN HEDGE JE PLAN (TM1, 05.11.2026, Finn über den Master: „du kannst ja machen bei Tradeify, auch über Orbit,
Prio 2 bei ihm“ — Emin). Tradeify ist im Modell-Dropdown wählbar; Prio 2 (ah_tick, hedge_art 'apex') nimmt nur die NICHT-finalen Tradeify-Trades, der
finale Trade bleibt beim eigenen Gegenhedge (tfh_tick, hedge_art 'tradeify_final'). Ein ganzer ah_tick und tfh_tick laufen gegen eine nachgebaute DB mit
den echten Regeln (Tradeify 150k: Kauf 215 €, Max DD 4.500 $, Boden nachziehend, Liq-Regel 1 EOD-Trailing; Schalter-Werte live 05.11.2026:
apex_hedge.netto_faktor 1, tradeify_final_hedge.netto_faktor 1, max_lots 100). Ohne Netz.
Fälle: (1) Emin Tradeify-Challenge normal + Gruppe Prio 2 → ah_tick merkt vor, tfh_tick nicht; (2) Emin finaler Tradeify → ah_tick nie, tfh_tick merkt vor;
(3) HT Tradeify (Standard Orbit V2) → ah_tick nichts, finaler über tfh_tick wie bisher; (4) alte Prio-2-Marke am finalen Plan wird weggeräumt;
(5) schon auf Prio 2 umgestellt (apex_hedge 'mit') → tfh_tick lässt ihn aus; (6) Modell setzen (HT + Gruppe) und Einstellungs-Sicht.
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_tradeify_prio2.py"""
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


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


FIRMEN = json.load(open(os.path.join(HIER, "selftest_orbit_prio2_firmen.json"), encoding="utf-8"))
HT, EMIN = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"
JETZT = datetime(2026, 11, 5, 6, 0, tzinfo=timezone.utc)
START = (JETZT + timedelta(minutes=60)).isoformat()
FUS = {HT: "fus-ht-0000-0000-0000-000000000001", EMIN: "fus-em-0000-0000-0000-000000000002"}


def konto(i, u, bal):
    return {"id": i, "user_id": u, "name": f"150k {i[-4:]} → Challenge", "firm": "Tradeify", "account_type": "challenge", "starting_balance": 150000,
            "external_id": "EXT" + i[-4:], "max_drawdown": 4500, "max_daily_drawdown": None, "ziel_usd": None, "tv_balance": bal, "_bal": bal}


KONTEN = [konto("a0000000-0000-4000-8000-0000000e0001", EMIN, 150000.0),    # Emin, normaler Trade
          konto("a0000000-0000-4000-8000-0000000e0002", EMIN, 157000.0),    # Emin, finaler Trade (Rest 2.000 $ bis 159.000)
          konto("a0000000-0000-4000-8000-0000000a0001", HT, 150000.0),      # HT, normaler Trade
          konto("a0000000-0000-4000-8000-0000000a0002", HT, 157000.0)]      # HT, finaler Trade


def plan(k, notes, tp, kt=2):
    return {"id": "p" + k["id"][-8:], "user_id": k["user_id"], "master_account_id": k["id"], "master_name": k["name"], "master_firm": "Tradeify",
            "master_contracts": kt, "master_symbol": "NQZ6", "master_symbol_root": "NQ", "master_tp": tp, "master_risk": None, "slave_risk": None,
            "multiplier": None, "hedge_faktor": None, "richtung": "buy", "start_um": START, "notes": notes, "mt5_baseline": {},
            "updated_at": "2026-11-05T05:00:00+00:00", "auto_bestaetigt_at": None, "hedge_freigabe_at": None}


NORMAL = "Auto-Planer · Etappe · Rest 9.000 $ bis Ziel"
FINAL = "Auto-Planer · letzter Trade (Rest bis Ziel) · Rest 2.000 $ bis Ziel"
PLAENE = [plan(KONTEN[0], NORMAL, 3500), plan(KONTEN[1], FINAL, 2050), plan(KONTEN[2], NORMAL, 3500), plan(KONTEN[3], FINAL, 2050)]
EN, EF, HN, HF = (p["id"] for p in PLAENE)
LIQ_REGELN = [{"id": 1, "firma": "Tradeify", "kontotyp": "challenge", "groesse": None, "art": "fest", "betrag_usd": 4500, "lock_ueber_start_usd": None,
               "stufen": None, "wie_kontotyp": None, "maxdd_art": "eod_trailing", "maxdd_lock_ueber_groesse_usd": None, "maxdd_usd": None}]
ZUSTAND = {"firmen": FIRMEN, "gruppe": {}, "geschrieben": [], "mit": []}


def sb_all(t, p):
    if t == "liq_regeln":
        return LIQ_REGELN
    if t == "trade_plans" and "bal_end" in str(p.get("select") or ""):
        return []
    if t == "trade_plans":
        if "mt5_baseline->apex_hedge->>status" in p:
            return [copy.deepcopy(x) for x in ZUSTAND["mit"]]
        if "mt5_baseline->tradeify_hedge->>status" in p:
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


app._eh_regeln = lambda: {"firmen": ZUSTAND["firmen"], "apex_hedge": {"an": True, "netto_faktor": 1},
                          "tradeify_final_hedge": {"an": True, "netto_faktor": 1, "max_lots": 100}}
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


def marken(art):
    return {str(pid)[3:]: (u.get("mt5_baseline") or {}).get("hedge_vorschau") for pid, u in ZUSTAND["geschrieben"]
            if (u.get("mt5_baseline") or {}).get("hedge_art") == art}


def ah(gruppe=None, firmen=None):
    ZUSTAND.update(firmen=firmen if firmen is not None else FIRMEN, gruppe=gruppe or {}, geschrieben=[])
    app._liq_verlauf_cache.clear()
    app._liq_regeln_cache.update(at=0.0, zeilen=None)
    app.ah_tick(jetzt=JETZT, force=True)
    return marken("apex")


def tfh(gruppe=None):
    ZUSTAND.update(gruppe=gruppe or {}, geschrieben=[])
    app.tfh_tick(jetzt=JETZT, force=True)
    return marken("tradeify_final")


ohne_at = lambda v: {k: x for k, x in (v or {}).items() if k != "at"}   # noqa: E731
PRIO2 = {"tradeify": "orbit_prio2"}

print("1) Final-Erkennung — eine Funktion für beide Wege")
check(app.tfh_ist_final(PLAENE[0], KONTEN[0]) is False and app.tfh_ist_final(PLAENE[1], KONTEN[1]) is True, "Notiz „Etappe“ = normal, „letzter Trade“ = final")
check(app.tfh_ist_final(dict(PLAENE[0], notes="frei"), dict(KONTEN[0], ziel_usd=159000, tv_balance=157000)) is True
      and app.tfh_ist_final(dict(PLAENE[0], notes="frei", master_tp=1500), dict(KONTEN[0], ziel_usd=159000, tv_balance=157000)) is False,
      "ohne Planer-Notiz: TP ≥ Ziel − Balance (wie prophos_plan_final)")
check(app.ah_tradeify_final(PLAENE[1], KONTEN[1]) and not app.ah_tradeify_final(dict(PLAENE[1], master_firm="Tradeify CFD"), KONTEN[1])
      and not app.ah_tradeify_final(dict(PLAENE[1], master_firm="Lucid Trading"), KONTEN[1]), "ah_tradeify_final: nur Tradeify-Futures, nicht Tradeify CFD/andere")

print("2) Emins Gruppe: Tradeify = Orbit Prio 2")
vs = ah(gruppe=PRIO2)
check(sorted(vs) == [EN], f"ah_tick merkt NUR Emins normalen Tradeify-Trade vor — nicht den finalen, nicht HT ({sorted(vs)})")
v = vs.get(EN) or {}
print("     Emin Tradeify normal (Prio 2):", json.dumps(ohne_at(v), sort_keys=True))
check(v.get("eur") == round(0.0478 * 4500, 2) and v.get("polster_usd") == 4500.0 and v.get("liq_balance") == 145500.0 and v.get("abstand_usd") == 4500.0,
      f"Kontowert {v.get('eur')} € auf Polster {v.get('polster_usd')} $ (Satz 215 ÷ 4.500 = 0,0478 gerundet wie Apex/Lucid), Boden {v.get('liq_balance')}, Abstand {v.get('abstand_usd')} $")
vt = tfh(gruppe=PRIO2)
check(sorted(vt) == sorted([EF, HF]), f"tfh_tick merkt nur die beiden finalen vor (Emin + HT), nie den Prio-2-Plan ({sorted(vt)})")
print("     Emin Tradeify final (Final-Weg):", json.dumps(ohne_at(vt.get(EF)), sort_keys=True))
print("     HT Tradeify final (Final-Weg):  ", json.dumps(ohne_at(vt.get(HF)), sort_keys=True))
check(not (set(vs) & set(vt)), "kein Plan in beiden Wegen (ein Hedge je Plan)")

print("3) HT unverändert (Standard Orbit V2)")
vs0 = ah()
check(not vs0, f"ohne Gruppen-Eintrag: ah_tick merkt keinen Tradeify-Plan vor ({sorted(vs0)})")
check(sorted(tfh()) == sorted([EF, HF]), "finale Tradeify-Trades laufen wie bisher über tfh_tick")
vs_ht = ah(firmen=[dict(f, modell="orbit_prio2") if f["namen"][0] == "tradeify" else f for f in FIRMEN])
check(sorted(vs_ht) == [HN], f"HT-Regel auf Prio 2 (nur zum Beweis, live bleibt V2): nur HTs normaler Trade, Emin folgt seiner Gruppe ({sorted(vs_ht)})")

print("4) alte Prio-2-Marke am finalen Plan → weg")
_alt = copy.deepcopy(PLAENE)
PLAENE[1]["mt5_baseline"] = {"hedge_art": "apex", "hedge_vorschau": {"lots": 1.0}, "x": 1}
ah(gruppe=PRIO2)
w = [u for pid, u in ZUSTAND["geschrieben"] if str(pid) == f"eq.{EF}"]
check(w and w[0]["mt5_baseline"] == {"x": 1}, f"finaler Emin-Plan mit hedge_art 'apex' (vorgemerkt) → Marke + Vorschau entfernt, Rest bleibt ({w[:1]})")
PLAENE[:] = copy.deepcopy(_alt)

print("5) schon auf Prio 2 umgestellt → tfh_tick lässt ihn aus")
PLAENE[1]["mt5_baseline"] = {"hedge_art": "apex", "apex_hedge": {"status": "mit", "lots": 2.0}}
PLAENE[1]["hedge_eur"] = 215.0
vt = tfh(gruppe=PRIO2)
check(EF not in vt and not [u for pid, u in ZUSTAND["geschrieben"] if str(pid) == f"eq.{EF}"],
      f"finaler Plan mit apex_hedge 'mit' bekommt keinen Final-Hedge dazu, keine Schreibzeile ({sorted(vt)})")
ZUSTAND["mit"] = [dict(PLAENE[1])]
ah(gruppe=PRIO2)
check(not [u for pid, u in ZUSTAND["geschrieben"] if str(pid) == f"eq.{EF}"], "ah_tick: umgestellter finaler Plan unangetastet (nicht nachgezogen, nicht geräumt)")
ZUSTAND["mit"] = []
PLAENE[:] = copy.deepcopy(_alt)

print("6) Modell setzen + Sicht")
neu, g = app.ap_modell_setzen(FIRMEN, "tradeify", "orbit_prio2")
check(g is None and neu[0].get("modell") == "orbit_prio2", "HT: Tradeify wählbar (ap_modell_setzen)")
check(app.ap_gruppe_modell_setzen({"lucidtrading": "orbit_prio2"}, FIRMEN, "tradeify", "orbit_prio2") == ({"lucidtrading": "orbit_prio2", "tradeify": "orbit_prio2"}, None),
      "Gruppe: Tradeify = Prio 2, Lucid bleibt")
check(app.ap_firma_modell(FIRMEN[0], None) == "orbit_v2" and app.ap_firma_modell(FIRMEN[0], None, PRIO2) == "orbit_prio2"
      and app.ap_firma_modell(FIRMEN[0], None, {}) == "orbit_v2", "wirksam: HT V2 (Standard), Gruppe mit Eintrag Prio 2, Gruppe ohne Eintrag V2")
check(app.ap_modell_setzen([{"namen": ["tradeifycfd"], "route": "mt5"}], "tradeifycfd", "orbit_prio2")[1] == "CFD-Firma — fährt immer Echo",
      "Tradeify CFD bleibt fest Echo")
_src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
check("AP_MODELL_NICHT_WAEHLBAR" not in _src.replace("vorher AP_MODELL_NICHT_WAEHLBAR", "") and '"modell_nicht": {}' in _src,
      "Server schickt keine Sperre mehr für Tradeify (Dropdown nicht ausgegraut)")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("(n === 'tradeify' && tf.an ? ` · Final als ${modellName('orbit')}` : '')" in html, "Kopf der Firma: „Orbit Prio 2 · Final als Orbit“")
_sql = open(os.path.join(WURZEL, "sql", "2026-11-05_tradeify_prio2.sql"), encoding="utf-8").read()
check("create trigger trade_plans_a1_ein_hedge" in _sql and "raise exception" in _sql, "DB-Riegel trade_plans_a1_ein_hedge als SQL-Datei (nicht eingespielt)")

print("7) Waage: Tradeify Futures auf Prio 2 nimmt Tradeify CFD NICHT mit aus der Waage (Fremd-Review)")
_w = app.ap_waage_ohne_modell({}, [dict(f, modell="orbit_prio2") if f["namen"][0] == "tradeify" else f for f in FIRMEN])
check("tradeify" in _w["waage_ohne"], f"Tradeify Futures Prio 2 → Schlüssel 'tradeify' in waage_ohne ({_w['waage_ohne']})")
check(app.ap_waage_ohne({"firma_key": "tradeify", "firma": "Tradeify"}, _w["waage_ohne"]) is True, "Tradeify Futures: aus der Waage wie Apex/Lucid (MO1b)")
check(app.ap_waage_ohne({"firma_key": "tradeifycfd", "firma": "Tradeify CFD"}, _w["waage_ohne"]) is False, "Tradeify CFD bleibt in der CFD-Waage")
check(app.ap_waage_ohne({"firma_key": "tradeifycfd", "firma": "Tradeify CFD"}, ["tradeifycfd"]) is True
      and app.ap_waage_ohne({"firma_key": "apextrader", "firma": "Apex Trader"}, ["apex"]) is True
      and app.ap_waage_ohne({"firma_key": "ftmo", "firma": "FTMO"}, ["apex", "tradeify"]) is False, "Hand-Eintrag 'tradeifycfd' wirkt weiter, Apex/FTMO wie bisher")
_g = app.ap_waage_param_gruppe({"waage_ohne": ["apex"]}, {}, FIRMEN, PRIO2)
check(_g["waage_ohne"] == ["apex", "tradeify"] and not app.ap_waage_ohne({"firma_key": "tradeifycfd", "firma": "Tradeify CFD"}, _g["waage_ohne"]),
      f"Emins Gruppe mit Tradeify Prio 2: waage_ohne {_g['waage_ohne']}, Tradeify CFD wiegt mit")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER:\n  - " + "\n  - ".join(FEHLER))
sys.exit(1 if FEHLER else 0)
