#!/usr/bin/env python3
"""Selbsttest: ZWEI ORBIT Stück 1 (30.10.2026) — puls_heim_zweit_pruefen und puls_heim_pruefen(route=…) gegen nachgebaute DB (app.py
importiert, _sb_all / _puls_heim_regel / _puls_heim_naehe ersetzt). Ohne Netz. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_zwei_orbit.py"""
import os
import sys
from datetime import datetime, timedelta, timezone

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


U = "11111111-1111-1111-1111-111111111111"
NEU = {"id": "n1", "user_id": U, "status": "planned", "route": "tvv2", "orbit_v3": True, "hedge_eur": 400, "master_firm": "Tradeify"}
REGEL = {"aktiv": True, "tp_usd": 2000, "liq_usd": 2000, "big_max_je_id": 1, "zweit_usd": 2500}
ZEILEN = []
NAEHE = {}


def sb_all(t, p):
    return [dict(z) for z in ZEILEN]


app._sb_all = sb_all
app._puls_heim_regel = lambda: REGEL
app._puls_heim_naehe = lambda plaene, schw: [(p, NAEHE[p["id"]], {"plan": p["id"]}, "Apex …" + p["id"], "BUY 2 NQ") for p in plaene]
nah = lambda n, tp=3000, liq=4000: {"nah": n, "grund": "x $ vor dem TP", "rest_tp_usd": tp, "rest_liq_usd": liq, "tp_level": 1, "liq_level": 1}   # noqa: E731

print("1) Zweiter Big Trade frei?")
check(app.puls_heim_zweit_pruefen(dict(NEU, status="open"))["frei"], "nicht geplant → frei (kein Eingriff)")
check(app.puls_heim_zweit_pruefen({"id": "x", "user_id": U, "status": "planned", "route": "mt5", "hedge_eur": 400})["frei"], "Echo → frei")
check(app.puls_heim_zweit_pruefen(NEU)["frei"], "keiner läuft → frei")
ZEILEN[:] = [{"id": "a", "user_id": U, "status": "open", "route": "tvv2", "orbit_v3": True, "hedge_eur": 400, "master_firm": "Apex Trader"}]
NAEHE["a"] = nah(False)
r = app.puls_heim_zweit_pruefen(NEU)
check(not r["frei"] and r["code"] == "zweit_wartet" and r["max_je_id"] == 1, f"big_max 1 + einer läuft (TV) → wartet wie heute: {r.get('grund')}")
check(app.puls_heim_zweit_pruefen(dict(NEU, route="tsv2"))["frei"], "Nova (tsv2) neben Orbit (tvv2) → frei (eigenes Fenster)")
REGEL["big_max_je_id"] = 2
check(app.puls_heim_zweit_pruefen(NEU)["frei"], "big_max 2, erster > 2.500 $ weg → frei")
NAEHE["a"] = nah(True, 1800)
r = app.puls_heim_zweit_pruefen(NEU)
check(not r["frei"] and r["code"] == "zweit_wartet" and r.get("big_trade") == {"plan": "a"} and r["rest_tp_usd"] == 1800, f"erster in der Spanne → wartet: {r.get('grund')}")
NAEHE["a"] = nah(None)
check(app.puls_heim_zweit_pruefen(NEU)["code"] == "big_trade_unklar", "erster nicht prüfbar → unklar")
ZEILEN.append({"id": "b", "user_id": U, "status": "planned", "route": "tvv2", "orbit_v3": True, "master_firm": "Lucid Trading",
               "orbit_gesendet_at": (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat()})
NAEHE["a"] = nah(False)
check(app.puls_heim_zweit_pruefen(NEU)["code"] == "zweit_wartet", "zweiter gerade gesendet → schon 2 bei big_max 2 → wartet")
ZEILEN[1]["orbit_gesendet_at"] = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
check(app.puls_heim_zweit_pruefen(NEU)["frei"], "alter Sende-Stempel zählt nicht")
NAEHE["a"] = nah(True, 1000)
check(app.puls_heim_zweit_pruefen(dict(NEU, orbit_gesendet_at="2026-10-30T08:00:00+00:00"))["frei"],
      "eigener Plan schon gesendet → frei (Nachklick/Neustart nie sperren, wie prophos_big_trade_halten)")
NAEHE["a"] = nah(False)
app._sb_all = lambda t, p: (_ for _ in ()).throw(RuntimeError("DB weg"))
check(app.puls_heim_zweit_pruefen(NEU)["code"] == "big_trade_unklar", "DB-Fehler → nicht frei (fail-closed)")
app._sb_all = sb_all
REGEL["big_max_je_id"] = 1

print("1b) Je Firma nur einer + Markteröffnung (03.11.2026, Z5)")
echt_markt = app.puls_heim_markt_oeffnung
UHR = {"t": datetime(2026, 11, 3, 14, 40, tzinfo=timezone.utc)}          # 18:40 Dubai (EST: 09:40 New York)
app.puls_heim_markt_oeffnung = lambda jetzt=None: echt_markt(UHR["t"])
NAEHE["a"] = nah(False)
ZEILEN[:] = [{"id": "a", "user_id": U, "status": "open", "route": "tvv2", "orbit_v3": True, "hedge_eur": 400, "master_firm": "Tradeify",
              "master_name": "150k …3058"}]
r = app.puls_heim_zweit_pruefen(NEU)
check(not r["frei"] and r["code"] == "zweit_wartet", f"big_max 1, gleiche Firma im selben Fenster → alter Weg (voll) wie heute: {r.get('code')}")
REGEL["big_max_je_id"] = 2
r = app.puls_heim_zweit_pruefen(NEU)
check(not r["frei"] and r["code"] == "firma_laeuft" and r.get("firma") == "Tradeify" and "je Firma nur einer" in r["grund"],
      f"big_max 2, Firma doppelt → gesperrt: {r.get('grund')}")
check(not app.puls_heim_zweit_pruefen(dict(NEU, master_firm="Tradeify Futures"))["frei"], "Schreibweise der Firma egal (_firm_norm)")
ZEILEN[0]["route"] = "tsv2"
r = app.puls_heim_zweit_pruefen(NEU)
check(not r["frei"] and r["code"] == "firma_laeuft", f"gleiche Firma im anderen Fenster (TopstepX) → auch gesperrt: {r.get('code')}")
REGEL["big_max_je_id"] = 1
check(app.puls_heim_zweit_pruefen(NEU)["code"] == "firma_laeuft", "Firma über beide Fenster auch bei big_max 1")
REGEL["big_max_je_id"] = 2
ZEILEN[0].update(route="tvv2", master_firm="Apex Trader")
check(app.puls_heim_zweit_pruefen(NEU)["frei"], "andere Firma, 18:40 Dubai → frei (Schalter 2)")
check(app.puls_heim_zweit_pruefen(dict(NEU, master_firm="Apex"))["code"] == "firma_laeuft", "„Apex“ = „Apex Trader“ → gesperrt")
UHR["t"] = datetime(2026, 11, 3, 14, 30, tzinfo=timezone.utc)          # 18:30 Dubai = 09:30 New York
r = app.puls_heim_zweit_pruefen(NEU)
check(not r["frei"] and r["code"] == "markt_oeffnung" and r.get("bis") == "2026-11-03T14:35:00+00:00" and "18:35 Dubai" in r["grund"],
      f"18:30 Dubai mit 1 laufend → gesperrt: {r.get('grund')}")
ZEILEN.append({"id": "c", "user_id": U, "status": "open", "route": "tvv2", "orbit_v3": True, "hedge_eur": 400, "master_firm": "Lucid Trading"})
NAEHE["c"] = nah(False)
check(app.puls_heim_zweit_pruefen(NEU)["code"] == "zweit_wartet", "18:30 Dubai, schon 2 → voll wie bisher (Markteröffnung ändert nichts)")
ZEILEN[:] = []
check(app.puls_heim_zweit_pruefen(NEU)["frei"], "18:30 Dubai mit 0 laufend → frei")
ZEILEN[:] = [{"id": "t", "user_id": U, "status": "open", "route": "tsv2", "hedge_eur": 400, "master_firm": "Topstep"}]
check(app.puls_heim_zweit_pruefen(NEU)["frei"], "18:30 Dubai, nur im anderen Fenster einer (TopstepX) → frei")
ZEILEN[:] = [{"id": "a", "user_id": U, "status": "open", "route": "tvv2", "orbit_v3": True, "hedge_eur": 400, "master_firm": "Apex Trader"}]
UHR["t"] = datetime(2026, 11, 3, 14, 35, tzinfo=timezone.utc)
check(app.puls_heim_zweit_pruefen(NEU)["frei"], "18:35:00 Dubai (Fensterende) → frei")
UHR["t"] = datetime(2026, 11, 3, 14, 40, tzinfo=timezone.utc)
check(app.puls_heim_zweit_pruefen(NEU)["frei"], "18:40 Dubai → frei")
app.puls_heim_markt_oeffnung = echt_markt
REGEL["big_max_je_id"] = 1

print("2) Puls bleibt zu Hause je Route")
check(app.puls_heim_pruefen("pc-abcd", route="mt5")["frei"] and app.puls_heim_pruefen("pc-abcd", route="mt5v2")["frei"], "Echo wartet nie")
pc_zeilen = [{"id": "t1", "user_id": U, "status": "open", "route": "tsv2", "hedge_eur": 400, "master_account_id": None, "mt5_baseline": {"hedge": {"pc": "pc-abcd"}}}]
app._sb_all = lambda t, p: [dict(z) for z in pc_zeilen]
gesehen = []
app._puls_heim_naehe = lambda plaene, schw: gesehen.append([p["id"] for p in plaene]) or []
app.sb_select = lambda t, p: []
app._wd_fruehere_trades = lambda ids: {}
app._liq_regeln_laden = app._liq_kw_laden = lambda: []
app._liq_verlauf_laden = lambda ids: []
app._kurs_jetzt = lambda: {}
check(app.puls_heim_pruefen("pc-abcd", route="tvv2")["frei"], "TV-Aktion: naher TopstepX-Big-Trade sperrt nicht (eigenes Fenster)")
r = app.puls_heim_pruefen("pc-abcd", route="tsv2")
check(not r["frei"] and r["code"] == "big_trade_unklar", f"TopstepX-Aktion: TopstepX-Big-Trade ohne Kurs → unklar wie bisher ({r.get('code')})")
check(not app.puls_heim_pruefen("pc-abcd")["frei"], "ohne Route: alle Fenster wie bisher")

print("3) Rangfolge Big Trade → Apex-Challenge → Winning Day (02.11.2026)")
hd = {"hedge": {"pc": "pc-abcd"}}
B = {"id": "b1", "status": "open", "route": "tvv2", "hedge_eur": 400, "orbit_v3": True, "master_account_id": None, "mt5_baseline": hd}
A = {"id": "a1", "status": "open", "route": "tvv2", "hedge_eur": 50, "master_account_id": None, "mt5_baseline": dict(hd, apex_hedge={"status": "mit"})}
W = {"id": "w1", "status": "open", "route": "tvv2", "hedge_eur": 100, "winning_day": True, "master_account_id": None, "mt5_baseline": hd}
NAH = {}
app._lt_zeile = lambda p, *a, **k: {"id": p["id"], "richtung": "buy", "kt": 2, "symbol_root": "NQ"}
app.puls_heim_kurs_frisch = lambda kurse, w: 20000.0
app.puls_heim_nah = lambda z, kurs, schw: dict(nah(NAH.get(z["id"], False)), schw=schw)
app._sb_all = lambda t, p: [dict(z) for z in pc_zeilen]
pc_zeilen[:] = [W, A, B]
check(app.puls_heim_pruefen("pc-abcd", route="tvv2")["frei"], "keiner nah → frei")
NAH.update(a1=True, w1=True)
r = app.puls_heim_pruefen("pc-abcd", route="tvv2")
check(not r["frei"] and r["code"] == "big_trade_nah" and r["grund"].startswith("Apex-Challenge") and r["big_trade"]["plan"] == "a1" and r["big_trade"].get("apex_hedge") is True,
      f"Apex und WD nah → Apex zuerst ({r.get('grund')})")
NAH.update(b1=True)
check(app.puls_heim_pruefen("pc-abcd", route="tvv2")["big_trade"]["plan"] == "b1", "Big Trade nah → Big Trade zuerst")
NAH.clear(); NAH.update(w1=True)
r = app.puls_heim_pruefen("pc-abcd", route="tvv2")
check(r["big_trade"]["plan"] == "w1" and r["big_trade"].get("winning_day") is True and r["grund"].startswith("Winning Day"), "nur WD nah → wie bisher")
NAH.clear(); NAH.update(a1=None)
check(app.puls_heim_pruefen("pc-abcd", route="tvv2")["frei"], "Apex nicht prüfbar → frei wie beim WD (Rest bis TP über der Grenze)")
pc_zeilen[:] = [A]
NAH.clear(); NAH.update(a1=True)
check(not app.puls_heim_pruefen("pc-abcd", route="tvv2")["frei"], "Apex allein nah → nicht frei")
check(app.puls_heim_pruefen("pc-abcd", ausser="a1", route="tvv2")["frei"], "der Plan selbst sperrt sich nicht")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
