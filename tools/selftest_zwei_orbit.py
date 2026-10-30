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
NEU = {"id": "n1", "user_id": U, "status": "planned", "route": "tvv2", "orbit_v3": True, "hedge_eur": 400}
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
ZEILEN[:] = [{"id": "a", "user_id": U, "status": "open", "route": "tvv2", "orbit_v3": True, "hedge_eur": 400}]
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
ZEILEN.append({"id": "b", "user_id": U, "status": "planned", "route": "tvv2", "orbit_v3": True,
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

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
