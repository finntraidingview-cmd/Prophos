#!/usr/bin/env python3
"""Selbsttest LQ1 (05.11.2026, Finn: „also im Radar dann auch 2.700 Daily“): liq_regel_felder nimmt den Tagesverlust der Firma aus den
Planer-Kernwerten (daily_usd, je Größe) als dritte Grenze, wenn die liq_regeln-Zeile kein Tageslimit kennt — Liq = min(Daily, Max Loss).
Fälle: Lucid 150k (Simon c1ed32a3 / Pascal 9dd4573b, Orbit V2 ohne Hedge, Balance 150.000) → 147.300 statt 145.500; Lucid 50k → 48.800;
unter dem EOD-Hoch gilt der engere Boden; Apex (liq_regeln tagesstart), Winning Days, Orbit Prio 2, Firma ohne daily_usd und ohne Kernwerte
unverändert; weicher Kernwert → Tageslimit wie Apex. Lader wie tools/selftest_liq_regeln.py. Aufruf: python3 tools/selftest_liq_daily.py"""
import importlib.util
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("liq_basis", os.path.join(HIER, "selftest_liq_regeln.py"))
basis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(basis)
SRC = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


a = basis.lade()
i = SRC.index("def liq_kw_daily(")
exec(SRC[i:SRC.find("\n\n\n", i)], a)
F, D = a["liq_regel_felder"], a["liq_kw_daily"]

REGELN = [
    {"id": 12, "firma": "Lucid Trading", "kontotyp": None, "groesse": None, "art": None, "maxdd_art": "eod_trailing"},
    {"id": 14, "firma": "Lucid Trading", "kontotyp": "winning_days", "groesse": None, "art": "boden", "lock_ueber_start_usd": "100",
     "maxdd_art": "eod_trailing", "maxdd_lock_ueber_groesse_usd": "100"},
    {"id": 3, "firma": "Apex Trader", "kontotyp": "challenge", "groesse": None, "art": "tagesstart", "betrag_usd": "2000",
     "maxdd_art": "eod_trailing", "maxdd_lock_ueber_groesse_usd": "100"},
    {"id": 1, "firma": "Tradeify", "kontotyp": "challenge", "groesse": None, "art": "fest", "betrag_usd": "4500", "maxdd_art": "eod_trailing"},
]
# Planer-Kernwerte wie live (auto_plan_regeln.regeln.firmen[], gekürzt): Lucid 2.700 / 50k 1.200 (hart), Apex 2.000 weich, Tradeify ohne Daily
KW = [
    {"namen": ["lucidtrading", "lucid"], "daily_usd": 2700, "dd_usd": 4500, "boden": "nachziehend", "je_groesse": {"50000": {"dd_usd": 2000, "daily_usd": 1200}}},
    {"namen": ["apextrader", "apex"], "daily_usd": 2000, "soft": True, "dd_usd": 4000, "boden": "statisch", "je_groesse": {"100000": {"dd_usd": 3000, "daily_usd": 1500}}},
    {"namen": ["tradeify"], "dd_usd": 4500, "boden": "nachziehend"},
    {"namen": ["weichfirma"], "daily_usd": 1000, "soft": True},
]
L150 = {"firm": "Lucid Trading", "account_type": "challenge", "starting_balance": 150000, "max_drawdown": 4500, "max_daily_drawdown": 2700,
        "name": "150k LFE15098351860005 → Challenge"}
PLAN = {"route": "tvv2", "master_contracts": 2, "richtung": "sell"}


def f(acc, bal=150000.0, ts=None, peak=None, plan=PLAN, kw=KW, regeln=REGELN):
    return F(regeln, acc, plan, bal, bal if ts is None else ts, 21000.0, plan.get("richtung"), 20.0, 2.0,
             peak=peak if peak is not None else bal, peak_eod=peak if peak is not None else bal, kw_firmen=kw)


r = f(L150)
check(r["liq_regel_balance"] == 147300.0 and r["liq_gilt"] == "regel" and r["liq_regel_art"] == "tageslimit" and r["liq_regel_soft"] is False,
      f"Lucid 150k: Liq 147.300 (Daily 2.700), vorher 145.500 — {r['liq_regel_text']}")
check(r["liq_boden_balance"] == 145500.0 and "Planer-Einstellung" in r["liq_regel_text"] and "✓ gilt" in (r["liq_vergleich_text"] or ""),
      "Boden 145.500 bleibt sichtbar, Vergleich zeigt das Daily als „gilt“")
check(abs(r["liq_regel_level_nq"] - (21000.0 + 2700 / 40)) < 0.01, f"Level SELL 2 NQ: Einstieg + 67,5 Pkt ({r['liq_regel_level_nq']})")
r_alt = f(L150, kw=None)
check(r_alt["liq_regel_balance"] == 145500.0 and r_alt["liq_gilt"] == "boden", "ohne Kernwerte wie bisher (145.500 am Boden)")
r50 = f(dict(L150, starting_balance=50000, max_drawdown=2000, name="50k LFE…"), bal=50000.0)
check(r50["liq_regel_balance"] == 48800.0, f"Lucid 50k: Daily je Größe 1.200 → 48.800 ({r50['liq_regel_text']})")
rh = f(L150, bal=149000.0, peak=152000.0)
check(rh["liq_regel_balance"] == 147500.0 and rh["liq_gilt"] == "boden", "unter dem EOD-Hoch 152.000: der engere Boden 147.500 gilt (Daily 146.300)")
rt = f(L150, bal=149500.0, ts=150000.0)
check(rt["liq_regel_balance"] == 147300.0, "zweiter Trade am Tag: Daily ab Tagesstart 150.000, nicht ab Balance jetzt")
apex = {"firm": "Apex Trader", "account_type": "challenge", "starting_balance": 150000, "max_drawdown": 4000, "name": "150k APEX…"}
ra, ra0 = f(apex, kw=KW), f(apex, kw=None)
check(ra["liq_regel_balance"] == 148000.0 and ra["liq_regel_soft"] is True and "Planer-Einstellung" not in ra["liq_regel_text"],
      "Apex (liq_regeln tagesstart 2.000): unverändert, weich")
check(ra["liq_regel_balance"] == ra0["liq_regel_balance"], "Apex mit/ohne Kernwerte gleich")
wd = f(dict(L150, account_type="winning_days"), plan=dict(PLAN, notes="Winning-Day-Farmer"))
wd0 = f(dict(L150, account_type="winning_days"), plan=dict(PLAN, notes="Winning-Day-Farmer"), kw=None)
check(wd["liq_regel_balance"] == wd0["liq_regel_balance"] and "Planer-Einstellung" not in str(wd["liq_regel_text"]), "Winning Days unverändert (Boden Größe + 100)")
td = {"firm": "Tradeify", "account_type": "challenge", "starting_balance": 150000, "max_drawdown": 4500, "name": "150k TDFY…"}
check(f(td)["liq_regel_balance"] == f(td, kw=None)["liq_regel_balance"], "Firma ohne daily_usd (Tradeify) unverändert")
weich = {"firm": "Weichfirma", "account_type": "challenge", "starting_balance": 50000, "max_drawdown": 2000, "name": "50k W"}
rw = f(weich, bal=50000.0, regeln=REGELN + [{"id": 99, "firma": "Weichfirma", "kontotyp": None, "art": None, "maxdd_art": "statisch"}])
check(rw["liq_regel_balance"] == 49000.0 and rw["liq_regel_soft"] is True and rw["liq_regel_art"] == "tagesstart", "weicher Kernwert → Tageslimit (Konto lebt), wie Apex")
check(D(KW, "Lucid Trading", 150000) == (2700.0, False) and D(KW, "Lucid Trading", 50000) == (1200.0, False) and D(KW, "Apex Trader", 100000) == (1500.0, True)
      and D(KW, "Tradeify", 150000) == (None, False) and D(None, "Lucid Trading", 150000) == (None, False) and D(KW, "Lucid Trading", None) == (2700.0, False),
      "liq_kw_daily: je Größe zuerst, sonst Firma; weich aus soft; ohne Wert/Kernwerte nichts")
b = SRC[SRC.index("def liq_regel_felder("):SRC.index("def lt_demo_liq(")]
check("if not ah and not wd and kw_firmen is not None and r_art not in (\"tagesstart\", \"stufen\"):" in b, "Orbit Prio 2 (ah) und Winning Days ausgenommen, Tageslimit-Regeln haben Vorrang")

print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
