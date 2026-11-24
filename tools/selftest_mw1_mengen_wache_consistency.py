#!/usr/bin/env python3
"""Selbsttest MW1 (Master 24.11.2026, Review LC1c): die Mengen-Wache (app.py ap_menge_wache → ap_menge_fix) rechnet mit derselben Konto-Regel wie die
Planer, also MIT Consistency (ap_cons_regel). Fall wie Chris Lucid 150k …0018 vor dem letzten Trade: Balance 157.362, größter Tag 3.894,50 →
Consistency-Ziel 159.737, Plan „letzter Trade (Rest bis Ziel)“ TP 2.415 (Rest 2.375 + Puffer 40), aber 4 Kontrakte (außerhalb 2–2,8) → die Wache
korrigiert die Menge. Ohne MW1 setzte sie dabei den TP auf den Rest bis zum REGEL-Ziel (1.678) zurück — das Konto endete unter dem Required profit.
Ohne Netz: DB-Aufrufe am Modul ersetzt. Aufruf: python3 tools/selftest_mw1_mengen_wache_consistency.py"""
import os
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
import app  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


LUCID = {"namen": ["lucidtrading", "lucid"], "route": "tvv2", "groessen": [50000, 150000], "ziel_pct": {"challenge": 6}, "boden": "nachziehend",
         "dd_usd": 4500, "phasen": {"challenge": {"sl": None, "tp": [3450, 3550], "menge": [2, 2.8], "dd_usd": 4500, "tp_max": 3600, "ziel_pct": 6,
                                                  "menge_schritt": 1}}}
REG = {"id": 1, "regeln": {"firmen": [LUCID]}, "zeiten": {}}
KONTO = {"id": "k-chris", "user_id": "u1", "firm": "Lucid Trading", "account_type": "challenge", "account_size": 150000, "name": "150k LFE1 → Challenge",
         "consistency_pct": None, "ziel_erreicht_at": None}
TAGE = {"2026-11-18": 3894.5, "2026-11-20": 3468.0}
JETZT = datetime(2026, 11, 23, 0, 0, tzinfo=timezone.utc)


def plan(tp, menge=4, stufe="letzter Trade (Rest bis Ziel)", rest="2.375", bal="157.362"):
    return {"id": "p1", "user_id": "u1", "master_account_id": "k-chris", "master_firm": "Lucid Trading", "route": "tvv2",
            "master_contracts": str(menge), "master_tp": str(tp), "notes": f"Auto-Planer · {stufe} · Rest {rest} $ bis Ziel · Balance {bal} (TV)",
            "start_um": "2026-11-23T08:00:00Z", "richtung": "buy", "hand_werte_at": None, "mt5_baseline": {}}


def lauf(p, tage=TAGE, laden_fehler=False):
    geschrieben, gelesen = [], []
    app._sb_all = lambda t, q: [dict(p)] if t == "trade_plans" else []
    app._ap_konten_laden = lambda q: [dict(KONTO)]
    app.ap_unt_je_uid = lambda reg: ({}, set())
    app.ap_unt_wache_reg = lambda reg, uid, je, gs: reg

    def _laden(ids):
        gelesen.append(list(ids))
        if laden_fehler:
            raise RuntimeError("Timeout")
        return {"k-chris": dict(tage)}
    app._zw_cons_tage_laden = _laden
    app.sb_update = lambda t, w, patch: geschrieben.append(patch) or [{}]
    app._sb_anfrage = lambda *a, **k: None
    app._sb_pruefen = lambda r: None
    out = app.ap_menge_wache(JETZT, REG)
    return out, geschrieben, gelesen


print("— MW1: Mengen-Wache mit Consistency —")
out, gs, gl = lauf(plan(2415))
print("  Patch:", gs, out)
ok(gs and float(gs[0]["master_contracts"]) == 3 and gs[0].get("master_tp") == 2375 + 60,
   f"Chris-Fall: Menge 4 → 3, TP = Rest zum Consistency-Ziel 2.375 + Puffer 3 Kt 60 = 2.435 (ohne MW1: 1.698 zum Regel-Ziel) ({gs})")
ok(gl == [["k-chris"]], f"Trade-Tage nur für den korrigierten Plan gelesen ({gl})")

out, gs, gl = lauf(plan(2415, menge=2))
ok(not gs and gl == [], "Menge passt → nichts geschrieben, nichts gelesen (kein neuer Lese-Weg)")

# Vergleich: ohne Consistency-Tage (größter Tag klein) bleibt alles wie vor MW1 — TP auf Rest bis Regel-Ziel + Puffer
out, gs, gl = lauf(plan(1700, rest="1.638"), tage={"2026-11-18": 3000.0, "2026-11-20": 3000.0})
ok(gs and gs[0].get("master_tp") == 1638 + 60, f"größter Tag ≤ 40 %: Rechnung wie bisher (TP Rest 1.638 + Puffer 60 zum Regel-Ziel) ({gs})")

out, gs, gl = lauf(plan(2415), laden_fehler=True)
ok(not gs, f"Lesefehler der Tage → Plan unverändert (nie ohne Consistency neu gerechnet) ({gs})")

print()
print("ALLES OK" if not FEHLER else f"{len(FEHLER)} ROT")
sys.exit(1 if FEHLER else 0)
