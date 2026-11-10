#!/usr/bin/env python3
"""Selbsttest: WD-SL-Würfel (app.py wd_sl_wuerfel_regel / wd_sl_wuerfeln / wd_sl_fuer_plan, WS1a 09.11.2026, Finn: „bau das Ganze“ — je WD-Trade
50 % kein SL · 10 % 10–20 % · 10 % 20–30 % · 30 % 30–40 % des Puffers = Balance vor dem Trade − Liq-Balance). Rein rechnend, ohne Netz: die Funktionen
werden aus app.py gelesen, die Liq-Rechnung (hf_wd_master_verlust → liq_regel_felder) läuft echt.
Aufruf: python3 tools/selftest_wd_sl_wuerfel.py"""
import json
import os
import random
import re
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")

FUNKTIONEN = ("_wd_num", "_cme_handelstag", "_wd_level", "_wd_konto_groesse", "liq_konto_groesse", "ist_topstep_express", "plan_balance_relativ",
              "plan_ist_wd", "plan_ist_apex_hedge", "ah_dll_balance", "liq_regel_waehlen", "liq_stufe", "_liq_de", "liq_aus_regel", "liq_tagesstart",
              "liq_boden_kernwerte", "liq_konto_boden", "_liq_pl_de", "liq_kw_daily", "liq_regel_felder", "hf_wd_master_verlust",
              "_wd_sl_std", "wd_sl_wuerfel_regel", "wd_sl_wuerfeln", "wd_sl_balance", "wd_sl_express_mll", "wd_sl_fuer_plan")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "json": json, "random": random, "datetime": datetime, "timezone": timezone,
          "_firm_norm": lambda n: (n or "").strip() or "—"}
    for k in ("MODELL_NAME", "LT_WD_BLOW_PLUS", "TX2_MLL_VOR"):
        exec(re.search(rf"^{k} = .*$", src, re.M).group(0), ns)
    i = src.index("\nWD_SL_WUERFEL_STD = ")
    exec(src[i:src.index("\n\n\ndef _wd_sl_std(", i)], ns)
    for fn in FUNKTIONEN:
        i = src.index(f"\ndef {fn}(") + 1
        m = re.compile(r"\n(?=\S)").search(src, src.index("\n", i))
        exec(src[i:m.start() if m else len(src)], ns)
    return ns


class Folge:
    """Zufallsquelle mit festen Werten (rnd.random())."""
    def __init__(self, *werte):
        self.w = list(werte)

    def random(self):
        return self.w.pop(0)


def main():
    ns = lade()
    regel_f, wuerfeln, fuer_plan = ns["wd_sl_wuerfel_regel"], ns["wd_sl_wuerfeln"], ns["wd_sl_fuer_plan"]
    f = []

    def check(ok, name):
        f.append(0 if ok else 1)
        print(("OK  " if ok else "FEHL") + " " + name)

    std, q = regel_f(ns["WD_SL_WUERFEL_STD"])
    check(q == "db" and [s["anteil"] for s in std["stufen"]] == [50, 10, 10, 30], "Standard ist gültig (50/10/10/30)")

    # 1) Verteilung über viele Würfe grob 50/10/10/30, Prozent immer in der Spanne der Stufe
    rnd = random.Random(20261109)
    n, je, spanne_ok = 100000, [0, 0, 0, 0], True
    for _ in range(n):
        w = wuerfeln(std, 14900, 165000, 150100, rnd=rnd)
        je[w["stufe"]] += 1
        s = std["stufen"][w["stufe"]]
        if s["von"] is None:
            spanne_ok &= w["ohne"] is True and w["usd"] is None and w["pct"] is None
        else:
            spanne_ok &= (w["ohne"] is False and s["von"] <= w["pct"] <= s["bis"]
                          and abs(w["usd"] - 14900 * w["pct"] / 100) <= 0.5 and isinstance(w["usd"], int))
    anteile = [round(100 * x / n, 1) for x in je]
    print(f"     Verteilung {anteile}")
    check(all(abs(a - b) < 1.0 for a, b in zip(anteile, (50, 10, 10, 30))), "Verteilung ≈ 50/10/10/30 (±1 Prozentpunkt)")
    check(spanne_ok, "Prozent in der Spanne, usd = Puffer × pct auf ganze $")

    # 2) Finns Beispiel: Tradeify 150k, Balance 165.000, Liq 150.100 → Puffer 14.900 → 1.490–5.960 $
    rnd = random.Random(7)
    usds = [wuerfeln(std, 14900, rnd=rnd)["usd"] for _ in range(20000)]
    usds = [u for u in usds if u is not None]
    check(min(usds) >= 1490 and max(usds) <= 5960, f"Beispiel Puffer 14.900 → SL {min(usds)}–{max(usds)} $ in 1.490–5.960")
    check(wuerfeln(std, 14900, rnd=Folge(0.0, 0.0))["stufe"] == 0, "Wurf 0,00 → Stufe 0 (ohne SL)")
    w = wuerfeln(std, 14900, rnd=Folge(0.55, 0.0))
    check(w["stufe"] == 1 and w["pct"] == 10 and w["usd"] == 1490, "Stufe 1 unten: 10 % → 1.490 $")
    w = wuerfeln(std, 14900, rnd=Folge(0.999999, 0.999999))
    check(w["stufe"] == 3 and w["pct"] == 40 and w["usd"] == 5960, "Stufe 3 oben: 40 % → 5.960 $")
    w = wuerfeln(std, 14900, rnd=Folge(0.65, 0.53))
    check(w["stufe"] == 2 and w["pct"] == 25.3 and w["usd"] == 3770, "Stufe 2: 25,3 % → 3.770 $")
    w = wuerfeln(std, 14900, rnd=Folge(0.59, 0.53))
    check(w["stufe"] == 1 and w["pct"] == 15.3 and w["usd"] == 2280, "Schnittstellen-Beispiel: 15,3 % von 14.900 → 2.280 $")

    # 3) über die echte Liq-Rechnung (hf_wd_master_verlust): Tradeify 150k WD, Liq-Regel Boden Größe + 100
    liq_regeln = [{"id": 1, "firma": "Tradeify", "kontotyp": "winning_days", "groesse": None, "art": "boden", "betrag_usd": None,
                   "lock_ueber_start_usd": 100, "stufen": None, "wie_kontotyp": None}]
    acc = {"id": "k-1", "name": "150k TDFY1 → Funded", "firm": "Tradeify", "account_type": "winning_days", "max_drawdown": 4500,
           "tv_balance": 165000, "tv_balance_at": "2026-11-09T01:00:00+00:00"}
    plan = {"master_account_id": "k-1", "start_um": "2026-11-09T06:00:00+00:00", "route": "tvv2", "master_firm": "Tradeify"}
    w = fuer_plan(std, plan, acc, liq_regeln, [], rnd=Folge(0.59, 0.53))
    check(w["puffer"] == 14900 and w["balance"] == 165000 and w["liq_balance"] == 150100 and w["usd"] == 2280 and w["regel"] == "sl_wuerfel",
          f"Tradeify über liq_regel_felder: Puffer {w['puffer']} · Liq {w['liq_balance']} · SL {w['usd']} $")
    w = fuer_plan(std, plan, dict(acc, tv_balance=150050), liq_regeln, [], rnd=Folge(0.59, 0.53))
    check(w["ohne"] is True and w["usd"] is None and w.get("grund"), f"Balance unter der Liq → ohne SL ({w.get('grund')})")
    w = fuer_plan(std, plan, dict(acc, tv_balance=None), liq_regeln, [], rnd=Folge(0.59, 0.53))
    check(w["ohne"] is True and "Balance" in (w.get("grund") or ""), f"keine Balance → ohne SL ({w.get('grund')})")
    w = fuer_plan(std, plan, None, liq_regeln, [], rnd=Folge(0.59, 0.53))
    check(w["ohne"] is True and w["usd"] is None, "Konto nicht lesbar → ohne SL")
    tx = dict(acc, firm="Topstep", name="150k EXPRESS-V2-1", account_type="winning_days", tv_balance=3200)
    w = fuer_plan(std, plan, tx, liq_regeln, [], rnd=Folge(0.59, 0.53))
    check(w["ohne"] is True and "Express" in (w.get("grund") or ""), "Topstep Express → ohne SL (MLL unbekannt)")
    # Apex: Daily Loss (Stufen) ab Tagesstart ist enger als Größe + 100 → Puffer bis zum Daily Loss
    apex_r = [{"id": 2, "firma": "Apex", "kontotyp": "winning_days", "groesse": None, "art": "stufen", "betrag_usd": None, "lock_ueber_start_usd": None,
               "stufen": [{"ab_balance": 0, "daily_loss_usd": 3000}], "wie_kontotyp": None}]
    a2 = dict(acc, firm="Apex", name="150k APEX1 → PA", tv_balance=160000)
    w = fuer_plan(std, dict(plan, master_firm="Apex"), a2, apex_r, [], rnd=Folge(0.59, 0.0))
    check(w["puffer"] == 3000 and w["liq_balance"] == 157000 and w["usd"] == 300, f"Apex Daily Loss: Puffer {w['puffer']} → SL 10 % = {w['usd']} $")
    w = fuer_plan(std, dict(plan, master_firm="Apex"), a2, [], [], rnd=Folge(0.59, 0.0))
    check(w["ohne"] is True and "liq_regeln" in (w.get("grund") or ""), "liq_regeln nicht geladen → ohne SL (nie Größe + 100 statt Daily Loss)")
    # Balance vor dem Trade (Prüfer WS1a): tv_balance nur, wenn NACH dem Ende des letzten Trades gelesen; sonst dessen balance_end; fehlt die → ohne
    fr_alt = [{"id": "p0", "master_account_id": "k-1", "ended_at": "2026-11-08T20:00:00+00:00", "bal_end": 160000}]
    w = fuer_plan(std, plan, acc, liq_regeln, fr_alt, rnd=Folge(0.59, 0.53))
    check(w["balance"] == 165000 and w["puffer"] == 14900, "tv_balance nach dem letzten Trade gelesen → gilt")
    fr_neu = [{"id": "p0", "master_account_id": "k-1", "ended_at": "2026-11-09T02:00:00+00:00", "bal_end": 160000}]
    w = fuer_plan(std, plan, acc, liq_regeln, fr_neu, rnd=Folge(0.59, 0.53))
    check(w["balance"] == 160000 and w["puffer"] == 9900 and w["usd"] == 1515, f"tv_balance älter als das Trade-Ende → balance_end 160.000 (SL {w['usd']} $)")
    w = fuer_plan(std, plan, acc, liq_regeln, [dict(fr_neu[0], bal_end=None)], rnd=Folge(0.59, 0.53))
    check(w["ohne"] is True and "nachgelesen" in (w.get("grund") or ""), "Nachlesung steht aus → ohne SL")
    w = fuer_plan(std, plan, acc, liq_regeln, [dict(fr_neu[0], master_account_id="k-2")], rnd=Folge(0.59, 0.53))
    check(w["balance"] == 165000, "Trade eines anderen Kontos zählt nicht")
    # Randfälle des Würfels
    r0 = {"an": True, "stufen": [{"anteil": 0, "von": None, "bis": None}, {"anteil": 100, "von": 25, "bis": 25}]}
    w = wuerfeln(r0, 10000, rnd=Folge(0.0, 0.7))
    check(w["stufe"] == 1 and w["pct"] == 25 and w["usd"] == 2500, "Stufe mit Anteil 0 nie gewählt; von == bis → fester Prozentwert")
    w = wuerfeln(r0, 1, rnd=Folge(0.5, 0.0))
    check(w["ohne"] is True and w["usd"] is None, "SL unter 1 $ → ohne SL")
    r1 = {"an": True, "stufen": [{"anteil": 50, "von": None, "bis": None}, {"anteil": 50, "von": 10, "bis": 20}]}
    w = wuerfeln(r1, 10000, rnd=Folge(0.9999999999999999, 0.0))
    check(w["stufe"] == 1, "Wurf ganz oben → letzte Stufe")

    # 4) Spalte fehlt / null / aus → kein SL, kein wd_sl
    check(regel_f(None) == (None, "aus"), "Spalte fehlt/null → aus")
    check(regel_f({"an": False, "stufen": std["stufen"]}) == (None, "aus"), "an=false → aus")
    check(regel_f("null") == (None, "aus"), "JSON-Text null → aus")
    for aus in (0, None, "off", "no", "aus"):
        check(regel_f({"an": aus, "stufen": std["stufen"]}) == (None, "aus"), f"an={aus!r} → aus")
    check(wuerfeln(None, 14900) is None and fuer_plan(None, plan, acc, liq_regeln, []) is None, "Würfel aus → kein wd_sl, kein SL")

    # 5) kaputte Einstellung → Standard
    kaputt = {
        "Summe ≠ 100": {"an": True, "stufen": [{"anteil": 50, "von": None, "bis": None}, {"anteil": 40, "von": 10, "bis": 20}]},
        "von > bis": {"an": True, "stufen": [{"anteil": 50, "von": None, "bis": None}, {"anteil": 50, "von": 30, "bis": 20}]},
        "bis > 100": {"an": True, "stufen": [{"anteil": 50, "von": None, "bis": None}, {"anteil": 50, "von": 30, "bis": 120}]},
        "von < 0": {"an": True, "stufen": [{"anteil": 50, "von": None, "bis": None}, {"anteil": 50, "von": -5, "bis": 20}]},
        "Anteil < 0": {"an": True, "stufen": [{"anteil": 110, "von": None, "bis": None}, {"anteil": -10, "von": 10, "bis": 20}]},
        "nur von": {"an": True, "stufen": [{"anteil": 50, "von": None, "bis": None}, {"anteil": 50, "von": 10, "bis": None}]},
        "Text statt Zahl": {"an": True, "stufen": [{"anteil": "x", "von": None, "bis": None}]},
        "Stufen leer": {"an": True, "stufen": []},
        "Stufen fehlen": {"an": True},
        "kein Objekt": [1, 2, 3],
        "kaputter Text": "{an: true",
    }
    for name, roh in kaputt.items():
        r, q = regel_f(roh)
        check(q == "standard" and r == std, f"kaputt ({name}) → Standard")
    eigen = {"an": True, "stufen": [{"anteil": "20", "von": None, "bis": None}, {"anteil": 80, "von": "5", "bis": 15}]}
    r, q = regel_f(eigen)
    check(q == "db" and r["stufen"][1] == {"anteil": 80, "von": 5.0, "bis": 15.0}, "gültige eigene Einstellung (Zahlen als Text) wird übernommen")
    r, q = regel_f(json.dumps(eigen))
    check(q == "db", "Einstellung als JSON-Text wird gelesen")

    print("ALLE OK" if not any(f) else f"{sum(f)} FEHLER")
    return 1 if any(f) else 0


if __name__ == "__main__":
    sys.exit(main())
