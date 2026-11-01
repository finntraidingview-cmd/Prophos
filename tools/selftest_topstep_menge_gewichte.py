#!/usr/bin/env python3
"""Selbsttest TSX-MENGE (app.py _ap_spanne mit gewichte, Finn 02.11.2026): Topstep-Challenge würfelt 20 % 1 NQ, 70 % 2 NQ, 10 % 3 NQ. Ohne Gewichte wie bisher, andere Firmen unverändert.
TP und SL in $ hängen nicht an der Menge. Ohne Netz. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_topstep_menge_gewichte.py"""
import os
import random
import sys

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


G = {"1": 20, "2": 70, "3": 10}
KETTE_ALT = {"menge": [2, 2.6667], "t1_sl": [1250, 1750], "t1_tp": [1950, 2650], "t2_ab": "11:00", "puffer": [25, 40], "t1_bis": "11:00", "t2_bis": "19:30",
             "t2_menge": [2, 2.6667], "daily_usd": 3000, "tagesziel_usd": 4500, "t2_abstand_min": [5, 20], "blow_puffer_usd": 200, "t2_streuung_min": [0, 45]}
KETTE = dict(KETTE_ALT, menge_gewichte=G, t2_menge_gewichte=G)
CH = {"sl": None, "tp": [4350, 4450], "menge": [2, 2.6667], "dd_usd": 4500, "tp_max": 4500, "ziel_pct": 6, "menge_schritt": 1,
      "puffer_je_menge": {"1": [10, 15], "2": [15, 25], "3": [25, 40]}}
TOPSTEP = {"boden": "nachziehend", "kette": KETTE, "namen": ["topstep"], "route": "tsv2", "dd_usd": 4500, "phasen": {"challenge": dict(CH, menge_gewichte=G)},
           "planen": True, "symbol": "NQ", "tp_max": 4500, "groessen": [150000], "kauf_eur": 237, "ziel_pct": {"challenge": 6}}

print("Verteilung")
rnd = random.Random(20261102)
n = 200000
zaehl = {1: 0, 2: 0, 3: 0}
for _ in range(n):
    zaehl[int(app._ap_spanne([2, 2.6667], rnd.random(), gewichte=G))] += 1
for m, soll in ((1, 20), (2, 70), (3, 10)):
    ist = zaehl[m] / n * 100
    check(abs(ist - soll) < 0.5, f"{m} NQ: {ist:.1f} % (soll {soll} %)")

print("Grenzen und Rückfall")
check(app._ap_spanne(None, 0.0, gewichte=G) == 1 and app._ap_spanne(None, 1.0, gewichte=G) == 3, "u 0 = 1 NQ, u 1 = 3 NQ")
check(app._ap_spanne(None, 0.1999, gewichte=G) == 1 and app._ap_spanne(None, 0.2, gewichte=G) == 2 and app._ap_spanne(None, 0.8999, gewichte=G) == 2 and app._ap_spanne(None, 0.9, gewichte=G) == 3, "Schwellen 20 % und 90 %")
check(app._ap_spanne(None, 0.0, gewichte={"3": 10, "1": 20, "2": 70}) == 1, "Reihenfolge der Schlüssel egal")
check(app._ap_spanne(None, 0.0, gewichte={"10": 1, "9": 1}) == 9, "Zahlen, nicht Text sortiert")
check(app._ap_spanne(None, 1.0, 2.0, gewichte=G) == 6, "Faktor wie bei der Spanne")
for schlecht, name in ((None, "fehlt"), ({}, "leer"), ({"2": 0}, "nur Null"), ({"x": 5}, "kein Zahl-Schlüssel"), ("kaputt", "kein Objekt")):
    check(app._ap_spanne([2, 3], 0.5, gewichte=schlecht) == 2.5, f"Gewichte {name}: Spanne")

print("Topstep-Kette")
u = {"tp": 0.5, "sl": 0.5, "puffer": 0.5, "dll": 0.5}
for x, soll in ((0.1, 1), (0.5, 2), (0.95, 3)):
    w, f = app.ap_kette_trade1(TOPSTEP, app.ap_kette_regel(TOPSTEP), 150000, 159000, 150000, dict(u, menge=x))
    check(f is None and w["menge"] == soll, f"Trade 1, u {x}: {w and w['menge']} NQ")
wa, _f = app.ap_kette_trade1(TOPSTEP, app.ap_kette_regel(TOPSTEP), 150000, 159000, 150000, dict(u, menge=0.1))
wb, _f = app.ap_kette_trade1(TOPSTEP, app.ap_kette_regel(TOPSTEP), 150000, 159000, 150000, dict(u, menge=0.95))
check((wa["tp"], wa["sl"]) == (wb["tp"], wb["sl"]) and isinstance(wa["menge"], int), f"TP/SL in $ hängen nicht an der Menge ({wa['tp']}/{wa['sl']}), ganze Kontrakte")
k1 = wa["kette"]
for x, soll in ((0.1, 1), (0.5, 2), (0.95, 3)):
    t2, f = app.ap_kette_trade2(k1, 150000, 151000, TOPSTEP, app.ap_kette_regel(TOPSTEP), x)
    check(f is None and t2["menge"] == soll, f"Trade 2, u {x}: {t2 and t2['menge']} NQ")
t2a, _f = app.ap_kette_trade2(k1, 150000, 151000, TOPSTEP, app.ap_kette_regel(TOPSTEP), 0.1)
t2b, _f = app.ap_kette_trade2(k1, 150000, 151000, TOPSTEP, app.ap_kette_regel(TOPSTEP), 0.95)
check((t2a["tp"], t2a["sl"]) == (t2b["tp"], t2b["sl"]), "Trade 2: TP/SL unverändert")

print("Ohne Gewichte wie bisher")
alt = dict(TOPSTEP, kette=KETTE_ALT)
for x, soll in ((0.0, 2), (0.5, 2), (1.0, 3)):
    w, _f = app.ap_kette_trade1(alt, app.ap_kette_regel(alt), 150000, 159000, 150000, dict(u, menge=x))
    check(w["menge"] == soll, f"Trade 1 Spanne, u {x}: {soll} NQ")
    t2, _f = app.ap_kette_trade2(k1, 150000, 151000, alt, app.ap_kette_regel(alt), x)
    check(t2["menge"] == soll, f"Trade 2 Spanne, u {x}: {soll} NQ")

print("Phase ohne Kette und Mengen-Wache")
ohne = {k: v for k, v in TOPSTEP.items() if k != "kette"}
for x, soll in ((0.1, 1), (0.5, 2), (0.95, 3)):
    w, f = app.ap_konto_rechnen(ohne, "challenge", 150000, dict(u, menge=x))
    check(f is None and w["menge"] == soll, f"Challenge, u {x}: {w and w['menge']} NQ")
apex = {"boden": "statisch", "namen": ["apextrader", "apex"], "route": "tvv2", "dd_usd": 4000, "symbol": "NQ", "groessen": [150000], "ziel_pct": {"challenge": 6},
        "phasen": {"challenge": {"sl": None, "tp": None, "menge": [3, 3], "puffer": [100, 100], "menge_schritt": 1}}}
wx, _f = app.ap_konto_rechnen(apex, "challenge", 150000, dict(u, menge=0.1))
check(wx["menge"] == 3, "Apex ohne Schlüssel unverändert 3 NQ")
for m, sagt in ((1, None), (2, None), (3, None)):
    patch, _t = app.ap_menge_fix({"master_contracts": m, "master_tp": 4400, "notes": ""}, ohne, "challenge", 150000)
    check(patch is sagt, f"Mengen-Wache lässt {m} NQ stehen")
patch, _t = app.ap_menge_fix({"master_contracts": 5, "master_tp": 4400, "notes": ""}, ohne, "challenge", 150000)
check(patch and patch["master_contracts"] == 3, "Mengen-Wache: 5 NQ → 3 NQ")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ alles grün")
