#!/usr/bin/env python3
"""Selbsttest Liq-Regeln (app.py, LIQ-REGELN, 30.09.2026) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_liq_regeln.py
Lädt die Funktionen per Quelltext aus app.py (wie selftest_live_trades: app.py zieht beim Import Flask und Threads).
Regeln = die 7 Zeilen von public.liq_regeln nach sql/2026-09-30_liq-regeln.sql + -2.sql. Anlass: Moritz Apex …0008 (Winning Days,
BUY 3 × NQ @ 30.706, Start-Balance 159.398,98) — Radar zeigte die Liquidation bei Kontogröße + 100 $, echt Apex-Stufe 3."""
import os
import re
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")

STUFEN = [{"ab_balance": 150000, "daily_loss_usd": 2500, "minis": 4, "micros": 40},
          {"ab_balance": 152000, "daily_loss_usd": 2500, "minis": 5, "micros": 50},
          {"ab_balance": 155000, "daily_loss_usd": 3000, "minis": 10, "micros": 100},
          {"ab_balance": 160000, "daily_loss_usd": 4000, "minis": 10, "micros": 100}]
REGELN = [
    {"id": 1, "firma": "Tradeify", "kontotyp": "challenge", "groesse": None, "art": "fest", "betrag_usd": "4500"},
    {"id": 2, "firma": "Tradeify", "kontotyp": "funded", "groesse": None, "art": "fest", "betrag_usd": "4500"},
    {"id": 7, "firma": "Tradeify", "kontotyp": "winning_days", "groesse": None, "art": "boden", "lock_ueber_start_usd": "100"},
    {"id": 3, "firma": "Apex Trader", "kontotyp": "challenge", "groesse": None, "art": "tagesstart", "betrag_usd": "2000"},
    {"id": 4, "firma": "Apex Trader", "kontotyp": "funded", "groesse": "150000", "art": "stufen", "stufen": STUFEN},
    {"id": 5, "firma": "FundedNext", "kontotyp": None, "groesse": None, "art": None},
    {"id": 6, "firma": None, "kontotyp": "winning_days", "groesse": None, "art": None, "wie_kontotyp": "funded"},
]


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone, "time": __import__("time")}

    def block(name):
        i = src.index(f"def {name}(")
        return src[i:src.find("\n\n\n", i)]
    i = src.index("_FIRM_RULES = [")
    firm_rules = src[i:src.index("\n]\n", i) + 2]
    exec("\n".join([firm_rules] + [block(f) for f in (
        "_wd_num", "_wd_level", "_wd_konto_groesse", "_firm_norm", "_cme_handelstag", "liq_regel_waehlen", "liq_stufe", "_liq_de",
        "liq_aus_regel", "liq_tagesstart", "liq_regel_felder")]), ns)
    return ns


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    F = a["liq_regel_felder"]
    T = a["liq_tagesstart"]

    # 1) Moritz Apex …0008 — erster Trade des CME-Handelstags 30.09 (voriger Trade 29.09. 16:15 UTC = Handelstag 29.09)
    moritz = {"firm": "Apex Trader", "account_type": "winning_days", "name": "150k Apex PAAPEX6416990000008→ Funded"}
    plan = {"id": "aeae87ef", "master_account_id": "m8", "started_at": "2026-09-30T00:21:07.233+00:00"}
    fruehere = [{"id": "33c2e2a7", "master_account_id": "m8", "started_at": "2026-09-29T16:15:06.879+00:00", "bal_start": 159369.02}]
    ts, q = T(plan, 159398.98, fruehere)
    check(ts == 159398.98 and "dieses Trades" in q, f"Moritz: Tagesstart = Start-Balance (Vortag zählt nicht) → {ts} ({q})")
    z = F(REGELN, moritz, plan, 159398.98, ts, 30706, "buy", 20, 3)
    check(z["liq_regel_balance"] == 156398.98, f"Moritz: Liq-Balance 156.398,98 (Stufe 3, 3.000 $) → {z['liq_regel_balance']}")
    check(z["liq_regel_level_nq"] == 30656.0, f"Moritz: Level 30.656,00 (50 Pkt unter 30.706) → {z['liq_regel_level_nq']}")
    check("Stufe 3" in z["liq_regel_text"] and "winning_days wie funded" in z["liq_regel_text"], f"Moritz: Text → {z['liq_regel_text']}")
    zs = F(REGELN, moritz, plan, 159398.98, ts, 30706, "sell", 20, 3)
    check(zs["liq_regel_level_nq"] == 30756.0, f"Moritz als SELL: Level 30.756,00 (über dem Einstieg) → {zs['liq_regel_level_nq']}")

    # 2) zweiter Trade am selben Handelstag: Tagesstart = Start-Balance des FRÜHESTEN Trades des Tages
    plan2 = {"id": "neu", "master_account_id": "m8", "started_at": "2026-09-30T03:00:00+00:00"}
    fr2 = fruehere + [{"id": "a1", "master_account_id": "m8", "started_at": "2026-09-30T00:21:07.233+00:00", "bal_start": 159398.98},
                      {"id": "a0", "master_account_id": "m8", "started_at": "2026-09-29T23:05:00+00:00", "bal_start": 159500.0},
                      {"id": "x", "master_account_id": "andere", "started_at": "2026-09-29T22:30:00+00:00", "bal_start": 1.0}]
    ts2, q2 = T(plan2, 158000.0, fr2)
    check(ts2 == 159500.0 and "erster Trade" in q2, f"2. Trade: Tagesstart = frühester Trade des Tages 159.500 → {ts2} ({q2})")
    z2 = F(REGELN, moritz, plan2, 158000.0, ts2, 30700, "buy", 20, 3)
    # Liq = 159.500 − 3.000 = 156.500; Abstand ab Start 158.000 = 1.500 $ = 25 Pkt
    check(z2["liq_regel_balance"] == 156500.0 and z2["liq_regel_level_nq"] == 30675.0,
          f"2. Trade: Liq 156.500, Level 30.675 (Tagesverlust zählt mit) → {z2['liq_regel_balance']} / {z2['liq_regel_level_nq']}")

    # 3) Tradeify Winning Days: Boden 150.100 schlägt „wie funded"
    twd = {"firm": "Tradeify", "account_type": "winning_days", "starting_balance": 150000}
    z3 = F(REGELN, twd, {"id": "t"}, 155000.0, None, 30000, "buy", 2, 1)
    check(z3["liq_regel_balance"] == 150100.0 and z3["liq_regel_level_nq"] == 27550.0 and "Boden" in z3["liq_regel_text"],
          f"Tradeify WD: Boden 150.100, Level 27.550 (4.900 $ ÷ 2) → {z3}")
    z3b = F(REGELN, twd, {"id": "t"}, 150050.0, None, 30000, "buy", 2, 1)
    check(z3b["liq_regel_level_nq"] is None and "nicht darüber" in z3b["liq_regel_text"], f"Tradeify WD unter dem Boden: kein Level → {z3b}")

    # 4) Tradeify Challenge / Funded: fest 4.500 — auch ohne Start-Balance ein Level (wie die Max-Drawdown-Rechnung)
    tch = {"firm": "tradeify", "account_type": "challenge", "name": "150k Tradeify Challenge"}
    z4 = F(REGELN, tch, {"id": "c"}, 150000.0, None, 30000, "buy", 2, 2)
    check(z4["liq_regel_balance"] == 145500.0 and z4["liq_regel_level_nq"] == 28875.0, f"Tradeify Challenge fest: 145.500 / 28.875 → {z4}")
    z4b = F(REGELN, tch, {"id": "c"}, None, None, 30000, "buy", 2, 2)
    check(z4b["liq_regel_balance"] is None and z4b["liq_regel_level_nq"] == 28875.0, f"Tradeify Challenge ohne Start-Balance: Level aus Betrag → {z4b}")
    tfu = {"firm": "Tradeify", "account_type": "funded", "starting_balance": 150000}
    z4c = F(REGELN, tfu, {"id": "f"}, 156000.0, None, 30000, "sell", 20, 1)
    check(z4c["liq_regel_balance"] == 151500.0 and z4c["liq_regel_level_nq"] == 30225.0, f"Tradeify Funded fest (SELL): 151.500 / 30.225 → {z4c}")

    # 5) Apex Evaluation: Daily Loss 2.000 ab Tagesstart
    ach = {"firm": "Apex", "account_type": "challenge", "name": "50k Apex Eval"}
    z5 = F(REGELN, ach, {"id": "e"}, 50000.0, None, 30000, "buy", 2, 4)
    check(z5["liq_regel_balance"] == 48000.0 and z5["liq_regel_level_nq"] == 29750.0, f"Apex Evaluation: 48.000 / 29.750 → {z5}")

    # 6) Apex-Funded-Stufen an den Grenzen
    S = a["liq_stufe"]
    for bal, nr in ((149000, 1), (151999.99, 1), (152000, 2), (154999, 2), (155000, 3), (159999.99, 3), (160000, 4), (170000, 4)):
        n, st = S(STUFEN, bal)
        check(n == nr, f"Stufe bei {bal:,.2f}: {nr} → {n} (Daily Loss {st and st['daily_loss_usd']})")
    afu = {"firm": "Apex Trader", "account_type": "funded", "name": "150k Apex Funded"}
    z6 = F(REGELN, afu, {"id": "af"}, 152500.0, None, 30000, "buy", 20, 1)
    check(z6["liq_regel_balance"] == 150000.0 and "Stufe 2" in z6["liq_regel_text"], f"Apex Funded 150k bei 152.500: Stufe 2, Liq 150.000 → {z6}")

    # 7) ohne passende bzw. offene Regel: keine Felder, kein Fehler
    z7 = F(REGELN, {"firm": "Apex Trader", "account_type": "funded", "name": "50k Apex Funded"}, {"id": "k"}, 51000.0, None, 30000, "buy", 2, 1)
    check(z7["liq_regel_balance"] is None and z7["liq_regel_level_nq"] is None and "keine Liq-Regel" in z7["liq_regel_text"],
          f"Apex Funded 50k: keine Regel → {z7['liq_regel_text']}")
    z8 = F(REGELN, {"firm": "FundedNext", "account_type": "funded_cfd", "starting_balance": 100000}, {"id": "n"}, 100500.0, None, 20000, "buy", 1, 1)
    check(z8["liq_regel_level_nq"] is None and "offen" in z8["liq_regel_text"], f"FundedNext CFD: Regel offen → {z8['liq_regel_text']}")
    z9 = F(REGELN, {"firm": "FundedNext Futures", "account_type": "funded", "starting_balance": 150000}, {"id": "nf"}, 150500.0, None, 30000, "buy", 2, 1)
    check("keine Liq-Regel" in z9["liq_regel_text"], f"FundedNext Futures ≠ FundedNext → {z9['liq_regel_text']}")
    z10 = F(REGELN, {"firm": "Lucid Trading", "account_type": "winning_days", "starting_balance": 50000}, {"id": "l"}, 51000.0, None, 30000, "buy", 2, 1)
    check(z10["liq_regel_level_nq"] is None, f"Lucid WD: generische Zeile ohne Funded-Regel → {z10['liq_regel_text']}")
    z11 = F(REGELN, {"firm": "Tradeify", "account_type": "funded", "name": "150k Tradeify"}, {"id": "h", "hedge_eur": 100}, 155000.0, None, 30000, "buy", 2, 1)
    check("Boden" in z11["liq_regel_text"], f"Plan mit hedge_eur > 0 zählt als Winning Day → {z11['liq_regel_text']}")
    z12 = F(REGELN, {"firm": "Tradeify", "account_type": "winning_days", "name": "Tradeify ohne Größe"}, {"id": "o"}, 155000.0, None, 30000, "buy", 2, 1)
    check(z12["liq_regel_level_nq"] is None and "Kontogröße unbekannt" in z12["liq_regel_text"], f"Boden ohne Kontogröße: klarer Grund → {z12['liq_regel_text']}")

    print("\nALLES OK" if ok else "\nFEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
