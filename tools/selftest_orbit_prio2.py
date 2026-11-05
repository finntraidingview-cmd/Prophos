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
                                         "starting_balance": g, "external_id": "EXT" + i[-4:], "max_drawdown": None, "max_daily_drawdown": dll, "_bal": bal}
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


def sb_all(t, p):
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
check(app.ap_modell_setzen(FIRMEN, "tradeify", "orbit_prio2")[1] and app.ap_firma_modell(dict(FIRMEN[0], modell="orbit_prio2"), "Tradeify") == "orbit_v2",
      "Tradeify nicht wählbar (eigener Final-Hedge) — auch ein Hand-Feld wirkt nicht")
check(app.ap_modell_setzen([{"namen": ["topstep"], "route": "tsv2"}], "topstep", "orbit_prio2")[1], "Topstep V2 nicht wählbar")
erg, vs = lauf(firmen=mit_modell(FIRMEN, "tradeify", "orbit_prio2"))
check(TF not in vs, "Tradeify mit Hand-Feld orbit_prio2 wird nicht vorgemerkt")

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
check("data-e3-modell=" in html and "apdApi('POST', '/modell', { firma, modell })" in html and "(sel.route === 'tsv2' || n === 'tradeify') ? ''" in html,
      "Einstellungen: Dropdown „Modell“ speichert über /admin/auto-plan/modell, nicht bei Tradeify/Topstep")
check("tpIstApexHedge(p) ? 'Orbit Prio 2'" in html and "'Apex-Hedge'" not in html, "Anzeige-Name „Orbit Prio 2“ statt „Apex-Hedge“")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER:\n  - " + "\n  - ".join(FEHLER))
sys.exit(1 if FEHLER else 0)
