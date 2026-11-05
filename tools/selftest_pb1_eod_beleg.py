#!/usr/bin/env python3
"""Selbsttest PB1 (05.11.2026, Befund S2, Geld-Pfad): Boden am EOD-Hoch für den Apex-Weg mit Fusion-Hedge (Orbit Prio 2) bei nachziehenden Firmen.
Emins FundedNext Futures 50k …3807 (Plan 82a25d69): +1.000 $ am 04.11. über Duplikum (tvplus) → Balance 50.998,12; der Verlauf las nur tvv2/tsv2 → leer →
Boden 48.500 statt 49.498 → Hedge 205 € / 3,21 Lot statt ≈ 123 €. Jetzt: tvplus im Verlauf, Lesung als Tagesschluss (kein Trade heute beendet),
Beleg-Pflicht für frühere Tage (fail-closed). Echte Regeln vom 05.11.2026 (auto_plan_regeln, liq_regeln), ohne Netz.
Aufruf: python3 tools/selftest_pb1_eod_beleg.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
import app  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


FIRMEN = [
    {"boden": "nachziehend", "namen": ["fundednextfutures"], "route": "tvv2", "dd_usd": 4000, "planen": False, "symbol": "NQ", "groessen": [50000, 150000],
     "kauf_eur": {"50000": 74, "150000": 258}, "ziel_pct": {"challenge": 5.333333333333334}, "lock_bei_start": True,
     "phasen": {"challenge": {"tp": [3050, 3150], "menge": [2, 3], "dd_usd": 4000, "tp_max": 3200, "ziel_pct": 5.333333333333334}},
     "je_groesse": {"50000": {"dd_usd": 1500, "ziel_pct": {"challenge": 5}, "phasen": {"challenge": {"tp": [900, 980], "menge": [1, 1], "dd_usd": 1500, "tp_max": 1000, "ziel_pct": 5}}}}},
    {"boden": "nachziehend", "namen": ["lucidtrading", "lucid"], "route": "tvv2", "dd_usd": 4500, "planen": True, "symbol": "NQ", "groessen": [50000, 150000],
     "kauf_eur": {"50000": 78, "150000": 222}, "ziel_pct": {"challenge": 6}, "daily_usd": 2700, "lock_bei_start": True,
     "phasen": {"challenge": {"tp": [4450, 4500], "menge": [2, 2.8], "dd_usd": 4500, "tp_max": 4500, "ziel_pct": 6}},
     "je_groesse": {"50000": {"dd_usd": 2000, "kauf_eur": 78, "daily_usd": 1200, "phasen": {"challenge": {"tp": [1450, 1500], "menge": [1, 1], "dd_usd": 2000, "tp_max": 1500, "ziel_pct": 6}}}}},
    {"soft": True, "boden": "statisch", "namen": ["apextrader", "apex"], "route": "tvv2", "dd_usd": 4000, "groessen": [100000, 150000],
     "kauf_eur": {"100000": 45, "150000": 150}, "ziel_pct": {"challenge": 6}, "daily_usd": 2000, "phasen": {"challenge": {"ziel_pct": 6}},
     "je_groesse": {"100000": {"dd_usd": 3000, "daily_usd": 1500}, "150000": {"dd_usd": 4000}}}]
LIQ = [{"id": 11, "firma": "FundedNext Futures", "kontotyp": None, "maxdd_art": "eod_trailing", "maxdd_lock_ueber_groesse_usd": 100, "maxdd_usd": 4000},
       {"id": 12, "firma": "Lucid Trading", "kontotyp": None, "maxdd_art": "eod_trailing", "maxdd_lock_ueber_groesse_usd": None, "maxdd_usd": None},
       {"id": 6, "firma": None, "kontotyp": "winning_days", "wie_kontotyp": "funded"}]
JETZT = "2026-11-05T02:13:00+00:00"            # 06:13 Dubai, CME-Tag 05.11.
FNF = {"id": "949cac4b-6859-4a75-8596-80297cc00062", "user_id": "6cceb3f3", "name": "50k FNFTCHEMINSUEKUEN33807 → Challenge", "firm": "FundedNext Futures",
       "account_type": "challenge", "max_drawdown": 1500, "starting_balance": 50000.0, "tv_balance": 50998.12, "tv_balance_at": "2026-11-04T23:27:32.315+00:00"}
TVPLUS = {"id": "b53cf006", "master_account_id": FNF["id"], "konto_typ": "challenge", "status": "completed", "route": "tvplus",
          "started_at": "2026-11-04T13:06:59+00:00", "ended_at": "2026-11-04T14:45:53.985412+00:00", "bal_end": None, "bal_start": None}
VERLAUF = {}


def boden(a, verlauf):
    VERLAUF.clear()
    VERLAUF[str(a["id"])] = verlauf
    app._liq_regeln_laden = lambda: LIQ
    app._liq_verlauf_laden = lambda ids, streng=False: [z for i in ids for z in VERLAUF.get(str(i), [])]
    app._wt_now_iso = lambda: JETZT
    return app._ah_boden_eod(a, FIRMEN)


src = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
ok('"route": "in.(tvv2,tsv2,tvplus,polar)"' in src and "konto_typ,status,route,started_at,ended_at,master_pl" in src, "_liq_verlauf_laden: auch tvplus, status/route im Select")

b, g = boden(FNF, [TVPLUS])
ok(g is None and abs(b - 49498.12) < 0.01, f"…3807: Lesung 50.998,12 nach dem Duplikum-Trade = Tagesschluss → Boden 49.498,12 ({b}, {g})")
pol = app.ah_eod_polster(50998.12, 2498.12, b)
satz = 205.35 / 2498.12
ok(abs(pol - 1500.0) < 0.01 and abs(round(satz * pol, 2) - 123.3) < 0.2, f"…3807: Polster 1.500 $ → Hedge ≈ {round(satz * pol, 2)} € (vorher 205,35 € auf 2.498,12 $)")

heute = dict(TVPLUS, id="heute1", started_at="2026-11-05T01:00:00+00:00", ended_at="2026-11-05T01:30:00+00:00")
b2, g2 = boden(dict(FNF, tv_balance_at="2026-11-05T01:31:00+00:00"), [TVPLUS, heute])
ok(b2 is None and g2 and g2.startswith("Balance-Beleg fehlt") and "2026-11-04" in g2,
   f"heute schon ein Trade beendet, Vortag ohne Beleg → fail-closed, kein stiller Rückfall auf 48.500 ({g2})")
b3, g3 = boden(dict(FNF, tv_balance_at="2026-11-04T12:00:00+00:00"), [TVPLUS])
ok(b3 is None and g3 and "Balance-Beleg fehlt" in g3, f"Lesung älter als der letzte Trade → fail-closed ({g3})")
mit_beleg = dict(TVPLUS, route="tvv2", bal_end=50998.12)
b4, g4 = boden(dict(FNF, tv_balance_at="2026-11-04T12:00:00+00:00"), [mit_beleg])
ok(g4 is None and abs(b4 - 49498.12) < 0.01, f"Orbit-Trade mit final.balance_end → Boden wie bisher aus dem Verlauf ({b4})")

LUCID = {"id": "5de61735-50ef-4815-9051-fc74f37b6166", "user_id": "6cceb3f3", "name": "50k LFE05097865230003 → Challenge", "firm": "Lucid Trading",
         "account_type": "challenge", "max_drawdown": 2000, "starting_balance": 50000.0, "tv_balance": 50000.0, "tv_balance_at": "2026-11-04T21:55:43.275+00:00"}
b5, g5 = boden(LUCID, [])
ok(g5 is None and b5 == 48000.0, f"Lucid 50k …0003 ohne Trade: Boden unverändert 48.000 ({b5})")
L1 = dict(LUCID, id="5fe0ac26-a479-4b12-a781-f8476b5114c6", name="50k LFE05097865230001 → Challenge", tv_balance=51501.5, tv_balance_at="2026-11-02T22:01:03.651+00:00")
tv1 = {"master_account_id": L1["id"], "konto_typ": "challenge", "status": "completed", "route": "tvplus", "started_at": "2026-11-03T13:00:00+00:00",
       "ended_at": "2026-11-03T18:07:53+00:00", "bal_end": None, "bal_start": None}
b6, g6 = boden(L1, [tv1])
ok(b6 is None and g6 and "Balance-Beleg fehlt" in g6, f"Lucid …0001: Duplikum-Trade 03.11. ohne Beleg, Lesung vom 02.11. → fail-closed ({g6})")

# Fremd-Review PB1: jeder genutzte Beleg zählt, nicht nur die Lesung
orbit_heute = {"master_account_id": FNF["id"], "konto_typ": "challenge", "status": "completed", "route": "tvv2", "started_at": "2026-11-05T01:00:00+00:00",
               "ended_at": "2026-11-05T01:40:00+00:00", "bal_start": 50998.12, "bal_end": 51200.0, "master_pl": 201.88}
b9, g9 = boden(dict(FNF, tv_balance=51200.0, tv_balance_at="2026-11-05T01:41:00+00:00"), [TVPLUS, orbit_heute])
ok(g9 is None and abs(b9 - 49498.12) < 0.01, f"BLOCKER-Fall: Duplikum 04.11. + Orbit heute mit balance_start 50.998 → Boden 49.498 statt 48.500 ({b9}, {g9})")
ohne_typ = {"master_account_id": FNF["id"], "konto_typ": None, "status": "completed", "route": "tvv2", "started_at": "2026-11-03T10:00:00+00:00",
            "ended_at": "2026-11-03T11:00:00+00:00", "bal_end": 51000.0}
b10, g10 = boden(dict(FNF, tv_balance_at="2026-11-02T10:00:00+00:00"), [ohne_typ])
ok(b10 is None and g10 and "Balance-Beleg fehlt" in g10, f"Plan ohne konto_typ ist kein Beleg (wie liq_peak) → fail-closed ({g10})")
t1 = dict(TVPLUS, id="t1", started_at="2026-11-03T13:00:00+00:00", ended_at="2026-11-03T14:00:00+00:00", master_pl=500.0)
t2 = dict(TVPLUS, id="t2", master_pl=1000.0)
b11, g11 = boden(dict(FNF, tv_balance=51500.0), [t1, t2])
ok(g11 is None and abs(b11 - 50000.0) < 0.01, f"zwei Duplikum-Tage ohne Belege: Schluss 03.11. = Lesung − P&L danach (50.500), Hoch 51.500 → Boden 50.000 ({b11}, {g11})")
t2_ohne = dict(t2, master_pl=None)
b12, g12 = boden(dict(FNF, tv_balance=51500.0), [t1, t2_ohne])
ok(b12 is None and g12 and "2026-11-03" in g12, f"späterer Trade ohne P&L → Rekonstruktion unmöglich → fail-closed ({g12})")
heute_pl = dict(heute, master_pl=200.0)
b13, g13 = boden(dict(FNF, tv_balance=51198.12, tv_balance_at="2026-11-05T01:31:00+00:00"), [dict(TVPLUS, master_pl=1000.0), heute_pl])
ok(g13 is None and abs(b13 - 49498.12) < 0.01, f"heute ein Duplikum-Trade mit P&L: Schluss 04.11. = 51.198,12 − 200 → Boden 49.498 ({b13}, {g13})")

hoch = dict(TVPLUS, route="tvv2", bal_end=52200.0)
b7, g7 = boden(dict(FNF, tv_balance=52200.0, tv_balance_at="2026-11-04T23:27:32+00:00"), [hoch])
ok(g7 is None and b7 == 50100.0, f"FNF 50k über dem Lock: Boden = liq_regeln Größe + 100 = 50.100 (nicht 50.000 aus den Kernwerten) ({b7})")
L2 = dict(LUCID, tv_balance=53000.0, tv_balance_at="2026-11-04T23:00:00+00:00")
b8, g8 = boden(L2, [dict(TVPLUS, master_account_id=L2["id"], route="tvv2", bal_end=53000.0)])
ok(g8 is None and b8 == 50000.0, f"Lucid ohne Lock in liq_regeln: Kernwerte-Lock beim Start bleibt (50.000) ({b8})")
ok((app.ap_kw_param(app.ap_regel_finden(FIRMEN, "Apex Trader")) or {}).get("boden") == "statisch",
   "Apex: Kernwerte statisch → ah_tick ruft _ah_boden_eod nie (Weg unverändert)")
p0 = app.liq_peak({"started_at": JETZT, "master_account_id": FNF["id"]}, FNF, None, [mit_beleg], eod=True)
p1 = app.liq_peak({"started_at": JETZT, "master_account_id": FNF["id"]}, FNF, None, [mit_beleg, TVPLUS], eod=True)
ok(p0 == p1 == 50998.12, f"liq_peak: tvplus-Zeile ohne Werte ändert nichts ({p0} / {p1})")

print()
print("alle Tests bestanden" if not FEHLER else f"{len(FEHLER)} ROT")
sys.exit(1 if FEHLER else 0)
