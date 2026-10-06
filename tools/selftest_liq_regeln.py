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
        "plan_ist_wd", "liq_aus_regel", "liq_tagesstart", "liq_regel_felder", "lt_demo_liq", "_lt_demo",
        "ist_topstep_express", "plan_balance_relativ", "liq_peak", "liq_konto_groesse", "liq_konto_boden", "_liq_pl_de",
        "_ap_norm", "ap_regel_finden", "ap_kw_param", "liq_boden_kernwerte")]), ns)
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

    # 8) DEMO-LIQ: die Demo rechnet gegen die Regel-Liq, sonst wie bisher
    D = a["lt_demo_liq"]
    rf = F(REGELN, moritz, plan, 159398.98, 159398.98, 30706, "buy", 20, 3)
    lvl, pl = D(30551.02, -9298.98, rf, 159398.98, 30706, "buy", 20, 3)
    check(lvl == 30656.0 and pl == -3000.0, f"Demo-Liq Moritz: Regel-Level 30.656 / −3.000 $ statt 30.551 / −9.298,98 → {lvl} / {pl}")
    lvl2, pl2 = D(30551.02, -9298.98, {}, 159398.98, 30706, "buy", 20, 3)
    check(lvl2 == 30551.02 and pl2 == -9298.98, f"Demo-Liq ohne Regel: wie bisher → {lvl2} / {pl2}")
    lvl3, pl3 = D(None, None, {"liq_regel_level_nq": 30896.0, "liq_regel_balance": None}, None, 30671, "sell", 20, 1)
    check(lvl3 == 30896.0 and pl3 == -4500.0, f"Demo-Liq ohne Start-Balance (SELL, fest 4.500): $ aus dem Level → {lvl3} / {pl3}")
    kerzen = [{"minute": "2026-09-30T00:22:00+00:00", "h": 30720, "l": 30690}, {"minute": "2026-09-30T00:23:00+00:00", "h": 30700, "l": 30650},
              {"minute": "2026-09-30T00:24:00+00:00", "h": 30690, "l": 30660}]
    alt = a["_lt_demo"]("buy", 30801.25, 30551.02, kerzen, "2026-09-30T00:21:07+00:00")
    neu = a["_lt_demo"]("buy", 30801.25, lvl, kerzen, "2026-09-30T00:21:07+00:00")
    check(alt.get("status") == "laeuft" and neu.get("status") == "liquidiert",
          f"Demo mit Tief 30.650: alte Liq → {alt.get('status')}, Regel-Liq → {neu.get('status')} ({neu.get('at')})")

    # 9) KONTO-BODEN (LIQ-KONTOBODEN, 30.09.2026) — Regeln mit den Spalten aus sql/2026-09-30_liq-kontoboden.sql
    RB = [dict(r) for r in REGELN]
    for r in RB:
        if r["firma"] == "Tradeify":
            r.update(maxdd_art="eod_trailing", maxdd_lock_ueber_groesse_usd=None if r["kontotyp"] == "challenge" else 100)
        if r["firma"] == "Apex Trader":
            r.update(maxdd_art="eod_trailing", maxdd_lock_ueber_groesse_usd=100)
    RB += [{"id": 8, "firma": "Topstep", "kontotyp": "challenge", "art": None, "maxdd_art": "eod_trailing", "maxdd_lock_ueber_groesse_usd": 0},
           {"id": 11, "firma": "Lucid Trading", "kontotyp": None, "art": None, "maxdd_art": "statisch"}]
    P, B = a["liq_peak"], a["liq_konto_boden"]
    # 9a) Finns Beispiel: 150k, Max DD 4.000, gestern 150.000 → 147.500 verloren; heute erster Trade ab 147.500 → Liq-Abstand 1.500 $
    apex = {"id": "ap1", "firm": "Apex Trader", "account_type": "challenge", "name": "150k Apex APEX6708050000005", "max_drawdown": "4000"}
    heute = {"id": "p2", "master_account_id": "ap1", "started_at": "2026-09-30T14:00:00+00:00"}
    verlauf = [{"id": "p1", "master_account_id": "ap1", "konto_typ": "challenge", "started_at": "2026-09-29T14:00:00+00:00",
                "ended_at": "2026-09-29T15:00:00+00:00", "bal_start": 150000.0, "bal_end": 147500.0}]
    pk = P(heute, apex, 147500.0, verlauf)
    zf = F(RB, apex, heute, 147500.0, 147500.0, 30000, "buy", 20, 1, peak=pk)
    check(pk == 150000.0 and zf["liq_boden_balance"] == 146000.0 and zf["liq_regel_nur_balance"] == 145500.0,
          f"Finn: Höchststand 150.000, Boden 146.000, Regel 145.500 → {pk} / {zf['liq_boden_balance']} / {zf['liq_regel_nur_balance']}")
    check(zf["liq_regel_balance"] == 146000.0 and zf["liq_gilt"] == "boden" and zf["liq_regel_level_nq"] == 29925.0,
          f"Finn: effektiv 146.000 (Boden gilt), 1.500 $ = 75 Pkt → Level 29.925 → {zf['liq_regel_balance']} / {zf['liq_gilt']} / {zf['liq_regel_level_nq']}")
    check("Konto-Boden 146.000 $" in (zf["liq_vergleich_text"] or "") and "→ −1.500 $ ✓ gilt" in zf["liq_vergleich_text"]
          and "Regel: Daily Loss 2.000 $" in zf["liq_vergleich_text"] and "→ −2.000 $" in zf["liq_vergleich_text"],
          f"Finn: Tooltip-Vergleich → {zf['liq_vergleich_text']}")
    zst = F(REGELN, apex, heute, 147500.0, 147500.0, 30000, "buy", 20, 1, peak=pk)
    check(zst["liq_regel_balance"] == 146000.0 and zst["liq_maxdd_art"] == "statisch",
          f"Finn statisch (Spalten fehlen/unklar): ebenfalls 146.000 → {zst['liq_regel_balance']} ({zst['liq_maxdd_art']})")
    lv, pl = D(29800.0, -4000.0, zf, 147500.0, 30000, "buy", 20, 1)
    check(lv == 29925.0 and pl == -1500.0, f"Finn: Demo liquidiert bei −1.500 $ (Spanne, Chart, Demo gleich) → {lv} / {pl}")
    # 9b) EOD-trailing mit Lock (Tradeify Funded 150k, DD 4.500, Lock Größe + 100)
    tf = {"id": "tf1", "firm": "Tradeify", "account_type": "funded", "starting_balance": 150000, "max_drawdown": "4500"}
    bl, bt, dd, art = B(RB[1], tf, 150000.0, 156000.0, 153000.0)
    check(bl == 150100.0 and "Lock bei 150.100 $" in bt and dd == 4500 and art == "eod_trailing",
          f"Trailing mit Lock: Höchststand 156.000 → 151.500, gedeckelt 150.100 → {bl} ({bt})")
    zl = F(RB, tf, {"id": "x"}, 153000.0, None, 30000, "buy", 2, 1, peak=156000.0)
    check(zl["liq_regel_balance"] == 150100.0 and zl["liq_gilt"] == "boden" and zl["liq_regel_level_nq"] == 28550.0,
          f"Tradeify Funded 153.000: Boden 150.100 schlägt fest 148.500 → Abstand 2.900 $ → {zl['liq_regel_balance']} / {zl['liq_regel_level_nq']}")
    bl2, bt2, _, _ = B(RB[1], tf, 150000.0, 152000.0, 151000.0)
    check(bl2 == 147500.0 and "Lock" not in bt2, f"Trailing unter dem Lock: 152.000 − 4.500 = 147.500 → {bl2} ({bt2})")
    tc = {"id": "tc1", "firm": "Tradeify", "account_type": "challenge", "name": "150k Tradeify", "max_drawdown": "4500"}
    zc = F(RB, tc, {"id": "y"}, 155000.0, None, 30000, "buy", 2, 1, peak=156000.0)
    check(zc["liq_regel_balance"] == 151500.0 and zc["liq_gilt"] == "boden",
          f"Tradeify Challenge (kein Lock): 156.000 − 4.500 = 151.500 schlägt fest 150.500 → {zc['liq_regel_balance']} ({zc['liq_regel_text']})")
    # 9c) ohne max_drawdown: nur die Regel; maxdd_usd der Regel als Rückfall
    ohne = dict(apex, max_drawdown=None)
    zo = F(RB, ohne, heute, 147500.0, 147500.0, 30000, "buy", 20, 1, peak=150000.0)
    check(zo["liq_regel_balance"] == 145500.0 and zo["liq_gilt"] == "regel" and zo["liq_boden_balance"] is None and zo["liq_vergleich_text"] is None
          and "kein Max Drawdown" in zo["liq_boden_text"], f"ohne Max DD: Regel 145.500 gilt allein → {zo['liq_regel_balance']} ({zo['liq_boden_text']})")
    RB2 = [dict(r, maxdd_usd=3000) if r["id"] == 3 else r for r in RB]
    zr = F(RB2, ohne, heute, 147500.0, 147500.0, 30000, "buy", 20, 1, peak=150000.0)
    check(zr["liq_boden_balance"] == 147000.0 and zr["liq_regel_balance"] == 147000.0, f"maxdd_usd der Regel als Rückfall: 150.000 − 3.000 → {zr['liq_boden_balance']}")
    # 9d) Höchststand: nur dieselbe Phase, nur VOR dem Start, tv_balance nur wenn vorher gelesen
    vl = verlauf + [{"id": "ch", "master_account_id": "ap1", "konto_typ": "funded", "started_at": "2026-09-20T14:00:00+00:00",
                     "ended_at": "2026-09-20T15:00:00+00:00", "bal_start": 158000.0, "bal_end": 159000.0},
                    {"id": "sp", "master_account_id": "ap1", "konto_typ": "challenge", "started_at": "2026-09-30T16:00:00+00:00",
                     "ended_at": "2026-09-30T17:00:00+00:00", "bal_start": 147500.0, "bal_end": 151000.0},
                    {"id": "nt", "master_account_id": "ap1", "konto_typ": None, "bal_end": 170000.0, "ended_at": "2026-09-01T00:00:00+00:00"},
                    {"id": "fr", "master_account_id": "anderes", "konto_typ": "challenge", "bal_end": 180000.0, "ended_at": "2026-09-01T00:00:00+00:00"}]
    check(P(heute, apex, 147500.0, vl) == 150000.0, f"Höchststand ignoriert andere Phase, späteren Trade, ohne konto_typ, fremdes Konto → {P(heute, apex, 147500.0, vl)}")
    check(P(heute, dict(apex, tv_balance=151200.0, tv_balance_at="2026-09-30T10:00:00+00:00"), 147500.0, vl) == 151200.0
          and P(heute, dict(apex, tv_balance=151200.0, tv_balance_at="2026-09-30T18:00:00+00:00"), 147500.0, vl) == 150000.0,
          "tv_balance zählt nur, wenn vor dem Start gelesen")
    check(P({"id": "g", "master_account_id": "ap1"}, apex, None, verlauf) == 150000.0, "geplanter Trade (ohne started_at): alle belegten Werte")
    # 9e) Topstep V2 mit gelesener MLL: MLL ist der Boden; Express bekommt keinen gerechneten Boden
    ts = {"id": "ts1", "firm": "Topstep", "account_type": "challenge", "name": "Topstep 150K Combine", "max_drawdown": "4500"}
    zm = F(RB, ts, {"id": "t1"}, 148000.0, None, 30000, "buy", 2, 1, peak=151000.0, mll=146900.0)
    check(zm["liq_regel_balance"] == 146900.0 and "MLL TopstepX" in zm["liq_regel_text"] and zm["liq_maxdd_art"] == "mll",
          f"Topstep mit MLL: MLL 146.900 statt gerechnet 146.500 → {zm['liq_regel_balance']} ({zm['liq_regel_text']})")
    zt = F(RB, ts, {"id": "t2"}, 148000.0, None, 30000, "buy", 2, 1, peak=151000.0)
    check(zt["liq_regel_balance"] == 146500.0 and zt["liq_gilt"] == "boden", f"Topstep ohne MLL: trailing 151.000 − 4.500 → {zt['liq_regel_balance']}")
    zx = F(RB, dict(ts, name="Topstep Express EXPRESS-V2-1"), {"id": "t3"}, 11079.66, None, 30000, "buy", 2, 1, peak=11079.66)
    check(zx["liq_boden_balance"] is None and "Express" in zx["liq_boden_text"], f"Topstep Express: kein Konto-Boden → {zx['liq_boden_text']}")
    # 9f) Winning Day behält die Boden-Regel (Größe + 100); Gleichstand → Regel gilt
    twd2 = {"id": "w1", "firm": "Tradeify", "account_type": "winning_days", "starting_balance": 150000, "max_drawdown": "4500"}
    zw = F(RB, twd2, {"id": "w"}, 155000.0, None, 30000, "buy", 2, 1, peak=158000.0)
    check(zw["liq_regel_balance"] == 150100.0 and zw["liq_gilt"] == "regel" and "Boden 150.000 + 100" in zw["liq_regel_text"],
          f"Tradeify WD: Regel-Boden 150.100 bleibt (Konto-Boden gelockt ebenso) → {zw['liq_regel_balance']} / {zw['liq_gilt']}")
    # 9g) Boden nicht unter der Balance (Datenzweifel) → nicht angewandt; statisch ohne Zeile (Lucid)
    bz, btz, _, _ = B(None, {"max_drawdown": 4000}, 150000.0, None, 145000.0)
    check(bz is None and "nicht angewandt" in btz, f"Boden 146.000 über Balance 145.000 → nicht angewandt ({btz})")
    lu = {"id": "l1", "firm": "Lucid Trading", "account_type": "challenge", "name": "Lucid 50k", "max_drawdown": "2000"}
    zlu = F(RB, lu, {"id": "l"}, 49000.0, None, 30000, "buy", 2, 1, peak=51000.0)
    check(zlu["liq_regel_balance"] == 48000.0 and zlu["liq_maxdd_art"] == "statisch" and zlu["liq_gilt"] == "boden",
          f"Lucid (statisch, offen): 50.000 − 2.000 = 48.000 trotz Höchststand 51.000 → {zlu['liq_regel_balance']}")

    # 9h) Kontogröße aus dem Kürzel (nur für den Konto-Boden; ~60 echte Konten ohne „150k" im Namen)
    G = a["liq_konto_groesse"]
    check(G({"name": "TDFYSL150984582962"}) == 150000 and G({"name": "Tradeify FTDFYSLX150132677414 → Funded"}) == 150000
          and G({"name": "150KTC-SKU-V2-679005-56869878"}) == 150000 and G({"name": "x", "external_id": "TDFYSL50123"}) == 50000
          and G({"name": "Apex APEX6416990000001"}) is None and G({"name": "150k Apex"}) == 150000 and G({"starting_balance": 100000}) == 100000,
          "Kontogröße: TDFYSL150/FTDFYSLX150/150KTC → 150.000, TDFYSL50 → 50.000, Apex ohne Größe → None")
    tk = {"id": "k1", "firm": "Tradeify", "account_type": "challenge", "name": "TDFYSL150984582962", "max_drawdown": "4500"}
    zk = F(RB, tk, {"id": "k"}, 147000.0, None, 30000, "buy", 2, 1, peak=150000.0)
    check(zk["liq_regel_balance"] == 145500.0 and zk["liq_gilt"] == "boden",
          f"Tradeify ohne Größe im Namen: Boden 145.500 aus dem Kürzel schlägt fest 142.500 → {zk['liq_regel_balance']}")

    # 10) FUNDEDNEXT FUTURES (LIQ-FNF, 05.10.2026, Finn: Futures Flex 150K Challenge, Max loss limit 4.000 $ EOD-trailing, Boden steigt
    #     nie über die Startgröße) — Regelzeile nach sql/2026-10-05_liq_regeln_fundednext_futures.sql. Anlass: Radar zeigte bei
    #     Balance 153.198 einen Abstand von 7.198 $ (Zeile stand als Annahme auf statisch → Boden 146.000).
    FN_ALT = {"id": 12, "firma": "FundedNext Futures", "kontotyp": None, "art": None, "maxdd_art": "statisch"}
    FN_NEU = dict(FN_ALT, maxdd_art="eod_trailing", maxdd_usd=4000, maxdd_lock_ueber_groesse_usd=0)
    RF = RB + [FN_NEU]
    fn = {"id": "fn1", "firm": "FundedNext Futures", "account_type": "challenge", "name": "150k FundedNextFutres FNFTCH000000000",
          "starting_balance": "0.00", "max_drawdown": "4000"}
    check(G(fn) == 150000 and a["liq_regel_waehlen"](RF, fn["firm"], "challenge", G(fn))[0]["id"] == 12,
          "FNF: Größe 150.000 aus dem Namen 150k …FNFTCH… (starting_balance 0), Zeile FundedNext Futures gewählt (nicht FundedNext CFD)")
    zalt = F(RB + [FN_ALT], fn, {"id": "f0"}, 153198.0, None, 30000, "buy", 20, 2, peak=153198.0)
    check(zalt["liq_regel_balance"] == 146000.0 and 153198.0 - zalt["liq_regel_balance"] == 7198.0,
          f"FNF alt (statisch): 153.198 → Boden 146.000, Abstand 7.198 $ — der Befund im Radar → {zalt['liq_regel_balance']}")
    for bal, soll_boden, soll_abst in ((150000.0, 146000.0, 4000.0), (153198.0, 149198.0, 4000.0),
                                       (154000.0, 150000.0, 4000.0), (156000.0, 150000.0, 6000.0)):
        z = F(RF, fn, {"id": "f1"}, bal, None, 30000, "buy", 20, 2, peak=P({"id": "f1"}, fn, bal, []))
        check(z["liq_regel_balance"] == soll_boden and bal - z["liq_regel_balance"] == soll_abst and z["liq_gilt"] == "boden"
              and z["liq_maxdd_art"] == "eod_trailing" and z["liq_regel_level_nq"] == 30000 - soll_abst / 40,
              f"FNF Balance {bal:,.0f} → Boden {soll_boden:,.0f}, Abstand {soll_abst:,.0f} $ → {z['liq_regel_balance']} "
              f"/ Level {z['liq_regel_level_nq']} ({z['liq_boden_text']})")
    check("Lock bei 150.000 $" in F(RF, fn, {"id": "f1"}, 156000.0, None, 30000, "buy", 20, 2, peak=156000.0)["liq_boden_text"]
          and "Lock" not in F(RF, fn, {"id": "f1"}, 153198.0, None, 30000, "buy", 20, 2, peak=153198.0)["liq_boden_text"],
          "FNF: Text nennt den Lock erst ab 154.000")
    # Rückgang 153.198 → 151.000: der Höchststand kommt aus den belegten Balances früherer Pläne derselben Phase
    fn_verlauf = [{"id": "g1", "master_account_id": "fn1", "konto_typ": "challenge", "started_at": "2026-10-02T14:00:00+00:00",
                   "ended_at": "2026-10-02T15:00:00+00:00", "bal_start": 150000.0, "bal_end": 153198.0},
                  {"id": "g2", "master_account_id": "fn1", "konto_typ": "challenge", "started_at": "2026-10-05T14:00:00+00:00",
                   "ended_at": "2026-10-05T15:00:00+00:00", "bal_start": 153198.0, "bal_end": 151000.0}]
    fn_heute = {"id": "g3", "master_account_id": "fn1", "started_at": "2026-10-06T14:00:00+00:00"}
    pkf = P(fn_heute, fn, 151000.0, fn_verlauf)
    zrk = F(RF, fn, fn_heute, 151000.0, None, 30000, "buy", 20, 2, peak=pkf)
    check(pkf == 153198.0 and zrk["liq_regel_balance"] == 149198.0 and 151000.0 - zrk["liq_regel_balance"] == 1802.0,
          f"FNF nach Rückgang auf 151.000: Höchststand 153.198 bleibt → Boden 149.198, Abstand 1.802 $ → {pkf} / {zrk['liq_regel_balance']}")
    # Grenze der Belege: ohne belegten Höchststand (keine früheren Pläne mit Balance) rechnet der Boden ab der Start-Balance
    zob = F(RF, fn, fn_heute, 151000.0, None, 30000, "buy", 20, 2, peak=P(fn_heute, fn, 151000.0, []))
    check(zob["liq_regel_balance"] == 147000.0, f"FNF ohne belegten Höchststand: 151.000 − 4.000 = 147.000 (zu weit, bekannt) → {zob['liq_regel_balance']}")
    zfb = F(RF, dict(fn, max_drawdown=None), {"id": "f1"}, 150000.0, None, 30000, "buy", 20, 2, peak=150000.0)
    check(zfb["liq_regel_balance"] == 146000.0 and zfb["liq_maxdd"] == 4000, f"FNF ohne Max DD am Konto: maxdd_usd 4.000 der Zeile → {zfb['liq_regel_balance']}")

    # 11) APEX-EVAL-SOFTBREACH (07.10.2026): Apex 150k Eval mit Tippfehler max_drawdown 400 am Konto. Tagesstopp 2.000 $ = Soft
    # Breach, Blow erst am Gesamt-Drawdown der Kernwerte (dd_usd 4.000, statisch) → 146.000. Daten wie live (Regeln + Kernwerte).
    RL = [dict(r) for r in REGELN]
    for r in RL:
        if r["firma"] == "Apex Trader":
            r.update(maxdd_art="eod_trailing", maxdd_lock_ueber_groesse_usd=100)
        if r["firma"] == "Tradeify" and r["kontotyp"] in ("challenge", "funded"):
            r.update(maxdd_art="eod_trailing", maxdd_lock_ueber_groesse_usd=None if r["kontotyp"] == "challenge" else 100)
    KW = [{"namen": ["apextrader", "apex"], "soft": True, "boden": "statisch", "dd_usd": 4000, "daily_usd": 2000, "groessen": [150000],
           "kauf_eur": 150, "ziel_pct": {"challenge": 6}, "phasen": {"challenge": {"puffer": [100, 100]}}},
          {"namen": ["tradeify"], "boden": "nachziehend", "dd_usd": 4500, "groessen": [150000], "kauf_eur": 100, "ziel_pct": {"challenge": 6}}]
    aev = {"id": "ax1", "firm": "Apex Trader", "account_type": "challenge", "name": "150k Apex APEX0000000000001", "max_drawdown": "400"}
    ip = {"id": "i1", "master_account_id": "ax1", "started_at": "2026-10-06T14:50:38+00:00"}
    alt = F(RL, aev, ip, 149981.46, 149981.46, 31568.5, "buy", 20, 3, peak=150000.0)
    neu = F(RL, aev, ip, 149981.46, 149981.46, 31568.5, "buy", 20, 3, peak=150000.0, kw_firmen=KW)
    check(alt["liq_boden_balance"] == 149600.0,
          f"vorher (Live-Befund): max_drawdown 400 am Konto → Boden 149.600 → {alt['liq_boden_balance']} (148.097 hieß geblowt)")
    check(neu["liq_boden_balance"] == 146000.0 and neu["liq_maxdd"] == 4000 and neu["liq_maxdd_art"] == "statisch"
          and neu["liq_regel_nur_balance"] == 147981.46 and neu["liq_regel_balance"] == 147981.46 and neu["liq_gilt"] == "regel"
          and neu["liq_regel_soft"] is True,
          f"Apex Eval: Boden 146.000 (Kernwerte, statisch), Tagesstopp 147.981,46 gilt, soft → {neu['liq_boden_balance']} / "
          f"{neu['liq_regel_balance']} / {neu['liq_gilt']} ({neu['liq_boden_text']})")
    nach = F(RL, aev, ip, 147500.0, 147500.0, 31568.5, "buy", 20, 3, peak=150000.0, kw_firmen=KW)
    check(nach["liq_boden_balance"] == 146000.0 and nach["liq_regel_balance"] == 146000.0 and nach["liq_gilt"] == "boden",
          f"Apex Eval nach Verlust (147.500): Boden 146.000 enger als Tagesstopp 145.500 → {nach['liq_regel_balance']} ({nach['liq_gilt']})")
    # Apex Funded: bestehender Lock-Wert (eod_trailing + Lock 100, max_drawdown am Konto) — Kernwerte ändern nichts
    afd = {"id": "af1", "firm": "Apex Trader", "account_type": "funded", "name": "150k Apex Funded", "max_drawdown": "4000"}
    f1 = F(RL, afd, {"id": "f"}, 156000.0, None, 30000, "buy", 20, 1, peak=156000.0)
    f2 = F(RL, afd, {"id": "f"}, 156000.0, None, 30000, "buy", 20, 1, peak=156000.0, kw_firmen=KW)
    check(f1 == f2 and f2["liq_boden_balance"] == 150100.0, f"Apex Funded unverändert (Lock 150.100) → {f2['liq_boden_balance']}")
    # Tradeify Challenge/Funded unverändert (fest, keine weiche Regel)
    for tdy in ({"id": "t1", "firm": "Tradeify", "account_type": "challenge", "name": "150k Tradeify", "max_drawdown": "4500"},
                {"id": "t2", "firm": "Tradeify", "account_type": "funded", "starting_balance": 150000, "max_drawdown": "4500"}):
        x1 = F(RL, tdy, {"id": "x"}, 151000.0, None, 30000, "buy", 20, 1, peak=153000.0)
        x2 = F(RL, tdy, {"id": "x"}, 151000.0, None, 30000, "buy", 20, 1, peak=153000.0, kw_firmen=KW)
        check(x1 == x2, f"Tradeify {tdy['account_type']} unverändert mit Kernwerten → {x2['liq_regel_balance']}")
    # ohne Kernwerte der Firma bzw. Ladefehler (None): wie bisher
    check(F(RL, aev, ip, 149981.46, 149981.46, 31568.5, "buy", 20, 3, peak=150000.0, kw_firmen=[]) == alt,
          "Kernwerte fehlen → Konto-Boden wie bisher")

    print("\nALLES OK" if ok else "\nFEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
