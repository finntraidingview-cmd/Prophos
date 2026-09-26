#!/usr/bin/env python3
"""Selbsttest Live Trades — Liquidations-Level (app.py, LIVE TRADES, 26.09.2026) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_live_trades.py
Laedt die Funktionen per Quelltext aus app.py (wie selftest_reader_wacht: app.py zieht beim Import Flask und Threads).
Prueft Finns Regel „Der Max-Drawdown ist quasi der SL": Nicht-WD-Konten bekommen das Level aus max_drawdown auch ohne
Start-Balance (BUY/SELL, NQ/MNQ, mehrere Kontrakte), ohne max_drawdown keins; Winning Days unveraendert."""
import os
import re
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone}

    def block(name):
        i = src.index(f"def {name}(")
        return src[i:src.find("\n\n\n", i)]

    def const(name):
        return re.search(rf"^{name} = .*$", src, re.M).group(0)
    exec("\n".join([const("LT_WD_BLOW_PLUS"), const("WD_HEUTE_PPL")]
                   + [block(f) for f in ("_wd_num", "_wd_level", "_wd_konto_groesse", "_lt_liq_balance", "_lt_liq", "_lt_demo")]), ns)
    return ns


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    liq, ppl = a["_lt_liq"], a["WD_HEUTE_PPL"]
    tradeify = {"account_type": "funded", "max_drawdown": 4500, "starting_balance": 150000, "name": "Tradeify 150k"}
    plan = {"konto_typ": "funded"}
    # BUY NQ 1 Kontrakt, ohne Start-Balance: 4.500 $ / (20 $ × 1) = 225 Punkte unter dem Einstieg
    r = liq(tradeify, plan, None, 30000.0, "buy", ppl["NQ"], 1)
    check(r["level"] == 29775.0 and r["balance"] is None and r["pl_usd"] == -4500 and r["regel"] == "Max-Drawdown 4.500 $ als SL",
          "BUY NQ ×1 ohne Start-Balance → Level 29.775, keine Liq-Balance, P&L −4.500 $")
    r = liq(tradeify, plan, None, 30000.0, "sell", ppl["NQ"], 3)
    check(r["level"] == 30075.0, "SELL NQ ×3 → 75 Punkte über dem Einstieg (30.075)")
    r = liq(tradeify, plan, None, 30000.0, "buy", ppl["MNQ"], 6)
    check(r["level"] == 29625.0, "BUY MNQ ×6 → 375 Punkte unter dem Einstieg (29.625)")
    r = liq(dict(tradeify, max_drawdown=4000), plan, 151200.0, 30000.0, "sell", ppl["MNQ"], 10)
    check(r["level"] == 30200.0 and r["balance"] == 147200.0 and r["pl_usd"] == -4000,
          "SELL MNQ ×10 mit Start-Balance → Level 30.200 + Liq-Balance 147.200 zusätzlich")
    r = liq(dict(tradeify, max_drawdown=None), plan, 151200.0, 30000.0, "buy", ppl["NQ"], 1)
    check(r["level"] is None and r["balance"] is None and r["regel"] == "kein Max-Drawdown am Konto",
          "ohne max_drawdown → kein Level, nichts geraten")
    check(liq(tradeify, plan, None, None, "buy", ppl["NQ"], 1)["level"] is None
          and liq(tradeify, plan, None, 30000.0, "buy", ppl["NQ"], 0)["level"] is None,
          "ohne Einstieg oder ohne Kontrakte → kein Level")
    # Winning Day unveraendert: Kontogroesse + 100 $, braucht die Start-Balance
    wd = {"account_type": "winning_days", "starting_balance": 150000, "max_drawdown": 4500}
    r = liq(wd, {"konto_typ": "winning_days"}, None, 30000.0, "buy", ppl["NQ"], 2)
    check(r["level"] is None and r["balance"] == 150100.0, "Winning Day ohne Start-Balance → kein Level (wie bisher)")
    r = liq(wd, {"konto_typ": "winning_days"}, 152100.0, 30000.0, "buy", ppl["NQ"], 2)
    check(r["level"] == 29950.0 and r["pl_usd"] == -2000.0, "Winning Day mit Start-Balance → Level aus Kontogröße + 100 $")
    # Demo gegen Kerzen: das neue Level liquidiert
    k = [{"minute": "2026-09-26T10:00:00+00:00", "h": 30010, "l": 29990}, {"minute": "2026-09-26T10:01:00+00:00", "h": 30000, "l": 29770}]
    d = a["_lt_demo"]("buy", 30300.0, 29775.0, k, "2026-09-26T10:00:20+00:00")
    check(d["status"] == "liquidiert" and d["preis"] == 29775.0, "Demo: Kerze unter dem Max-Drawdown-Level → liquidiert")

    # B5: beendete Trades — Kerzen nach dem Ende zaehlen nicht
    dm = a["_lt_demo"]
    k2 = [{"minute": f"2026-09-25T{h:02d}:{m:02d}:00+00:00", "h": 30010, "l": 29990} for h, m in ((1, 0), (1, 10), (1, 17))] \
        + [{"minute": "2026-09-25T09:00:00+00:00", "h": 30400, "l": 29500}]
    d = dm("sell", 29700.0, 30350.0, k2, "2026-09-25T00:59:30+00:00", "2026-09-25T01:17:40+00:00")
    check(d["status"] == "beendet_ohne_treffer" and d["minuten"] == 3 and d["at"].startswith("2026-09-25T01:17"),
          "beendet ohne Treffer: nur Kerzen bis zur Ende-Minute, Kerze danach (TP + Liq) zaehlt nicht")
    d = dm("sell", 29700.0, 30350.0, k2, "2026-09-25T00:59:30+00:00")
    check(d["status"] == "beide_in_minute", "ohne Ende wie bisher (laufender Trade sieht spaetere Kerzen)")
    d = dm("sell", 29995.0, 30350.0, k2, "2026-09-25T00:59:30+00:00", "2026-09-25T01:17:40+00:00")
    check(d["status"] == "tp", "Treffer vor dem Ende bleibt Treffer")
    check(dm("sell", 29700.0, None, k2, "2026-09-25T02:00:00+00:00", "2026-09-25T03:00:00+00:00")["status"] == "ohne_kurs",
          "Ende ohne Kerze im Fenster → ohne_kurs")
    check(dm("sell", 29700.0, None, k2, "2026-09-25T00:59:30+00:00", "kaputt")["status"] == "tp",
          "kaputtes Ende wirft nicht, rechnet wie ohne Ende")

    print("\nALLES GRUEN" if ok else "\nFEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
