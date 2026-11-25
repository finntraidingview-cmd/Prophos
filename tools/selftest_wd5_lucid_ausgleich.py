#!/usr/bin/env python3
"""Selbsttest WD5 (Master 25.11.2026, Finn: Finn + Pascal · Lucid 150k …0001, Zyklus 4 seit Payout-Antrag 12.11., 4/5 WD, Zyklus −1.434 $ → der Farmer plante
heute einen normalen WD statt des Ausgleichs-Trades). Ursache: Plan ec83e13a (23.11.) — Endlesung „Total P/L“ −180,50 $, Balance 156.844 → 154.076 = −2.768 $
(= master_pl). wd_plan_pnl nahm die Endlesung → Trade-Summe +1.153 $ ≠ Balance −1.434,50 $ → AG2-Gegenprobe „unbekannt“ → kein Ausgleich. Fix: weicht die
Endlesung > 50 $ von der Balance-Differenz ab und passt master_pl dazu, zählt master_pl. Echte Zahlen des Kontos, ohne Netz/DB.
Aufruf: python3 tools/selftest_wd5_lucid_ausgleich.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
FEHLER = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        FEHLER.append(text)


ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone}


def lade(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^\S)", app, re.S | re.M)
    exec(m.group(0), ns)


def ruf(fn, *a, **k):
    for _ in range(60):
        try:
            return ns[fn](*a, **k)
        except NameError as e:
            lade(str(e).split("'")[1])
    raise RuntimeError(fn)


for n in ("TRADEIFY_ZYKLUS_MIN_USD", "TRADEIFY_ZYKLUS_PUFFER", "TRADEIFY_AUSGLEICH_BESTAETIGEN", "AG2_GEGENPROBE_USD", "WD_PNL_BALANCE_TOL",
          "WD_FIRMEN_REGELN_STD", "_wd_iso_ts", "wd_plan_pnl", "tradeify_zyklus_konto", "wd_zyklus_stand", "zyklus_plus_key"):
    lade(n)
ns["_cme_handelstag"] = lambda _x: "2026-11-25"
check(ns.get("WD_PNL_BALANCE_TOL") == 50.0, "Toleranz Endlesung ↔ Balance 50 $ (wie AG2)")

# echte Pläne des Kontos seit dem Payout-Antrag 12.11. (DB 25.11.2026)
T = [("814ef28f", "2026-11-12T16:00:14+00:00", 1662.5, 1662.5, 157369.5, 159032.0),
     ("d6875269", "2026-11-17T02:10:23+00:00", 265.0, 265.0, 156032.0, 156297.0),
     ("7b872500", "2026-11-18T06:10:28+00:00", 269.5, 269.5, 156297.0, 156566.5),
     ("45e7b995", "2026-11-20T03:42:05+00:00", 277.5, 277.5, 156566.5, 156844.0),
     ("ec83e13a", "2026-11-23T06:37:12+00:00", -2768.0, -180.5, 156844.0, 154076.0),
     ("cb4267b7", "2026-11-24T08:56:07+00:00", 276.0, 276.0, 154076.0, 154352.0),
     ("5b58bec9", "2026-11-25T03:06:25+00:00", 245.5, 245.5, 154352.0, 154597.5)]


def plan(pid, s, mpl, fin, bs, be):
    tag = s[:10]
    tv = {"today_pnl_start": 0, "datum_start": tag, "balance_start": bs}
    return {"id": pid, "status": "completed", "route": "tvv2", "started_at": s, "ended_at": s, "master_pl": mpl,
            "mt5_baseline": {"tv": tv, "final": {"today_pnl": fin, "datum": tag, "balance_end": be}}, "tv": dict(tv)}


PL = [plan(*t) for t in T]
pnl = lambda p: ruf("wd_plan_pnl", p)
check(pnl(PL[4]) == -2768.0, f"ec83e13a: Endlesung −180,50 ≠ Balance −2.768 und master_pl passt → −2.768 ({pnl(PL[4])})")
check(all(pnl(p) == t[3] for p, t in zip(PL, T) if t[0] != "ec83e13a"), "alle anderen Trades: Endlesung wie bisher (stimmt mit der Balance)")
ohne_mpl = dict(PL[4], master_pl=None)
check(pnl(ohne_mpl) == -180.5, "ohne master_pl: Endlesung wie bisher (nur EINE Quelle widerspricht nicht zwei)")
mpl_falsch = dict(PL[4], master_pl=-180.5)
check(pnl(mpl_falsch) == -180.5, "master_pl passt nicht zur Balance → Endlesung wie bisher")
ohne_be = plan("x", "2026-11-23T06:37:12+00:00", -2768.0, -180.5, 156844.0, None)
check(pnl(ohne_be) == -180.5, "ohne balance_end: Endlesung wie bisher")
klein = plan("y", "2026-11-23T06:37:12+00:00", 270.0, 265.0, 156000.0, 156270.0)
check(pnl(klein) == 265.0, "Abweichung ≤ 50 $: Endlesung wie bisher (bitgleich)")

KONTO = {"id": "952df577", "name": "150k LFF15084019460001 → Winning Days", "firm": "Lucid Trading", "account_type": "winning_days", "user_id": "48f272b4",
         "max_drawdown": 4500, "wd_farm": True}
PAY = [{"requested_at": "2026-10-28", "status": "received"}, {"requested_at": "2026-11-04", "status": "received"},
       {"requested_at": "2026-11-12", "status": "received"}]
VP = {"regeln": {"fu": {"lucid": [268, 280], "tradeify": [266, 280]}, "staffel": [50, 60, 70, 80, 90]}}
LIVE, LIVE_AT = 154597.5, "2026-11-25T03:11:07+00:00"
z = ruf("tradeify_zyklus_konto", KONTO, PL, PAY, 4, 5, VP, LIVE, LIVE_AT, regel={"an": True, "usd": 1.0, "ab_zyklus": 1})
check(z["nr"] == 4 and z["firma_key"] == "lucid" and z["gewinn"] == -1434.5 and z["gesperrt"],
      f"Zyklus 4, Gewinn −1.434,50 $ aus Trades UND Balance (stimmig), Payout gesperrt ({z.get('gewinn')}, {z.get('grund_code')})")
check(z["aktiv"] and z["grund_code"] == "ausgleich" and 1466 <= (z["ziel"] or 0) <= 1496,
      f"4/5 WD → Ausgleichs-Trade TP {z.get('ziel')} $ (Fehlbetrag 1.434,50 + 1 $ + Puffer 30–60) statt normaler WD")

# Gegenprobe: wie vorher (Endlesung zuerst) wäre AG2 „unbekannt“ → kein Ausgleich (der Befund)
alt = ns["wd_plan_pnl"]
ns["wd_plan_pnl"] = lambda p: (p["mt5_baseline"]["final"]["today_pnl"] if p.get("mt5_baseline") else alt(p))
z0 = ns["tradeify_zyklus_konto"](KONTO, PL, PAY, 4, 5, VP, LIVE, LIVE_AT, regel={"an": True, "usd": 1.0, "ab_zyklus": 1})
ns["wd_plan_pnl"] = alt
check(not z0["aktiv"] and z0["grund_code"] == "unbekannt", f"vorher: AG2 „Balance ≠ Trades“ → kein Ausgleich (Befund, {z0.get('grund_code')})")

# Befund 2: Lucid-WD-TP mit Puffer (Daten-SQL)
sq = open(os.path.join(W, "sql", "2026-11-25_wd5_lucid_wd_tp_puffer.sql"), encoding="utf-8").read()
code = "\n".join(z for z in sq.splitlines() if not z.lstrip().startswith("--"))
check("jsonb_set(vorplan, '{regeln,fu,lucid}', '[285, 300]'::jsonb)" in code and "vorplan->'regeln'->'fu'->'lucid' = '[268, 280]'::jsonb" in code
      and "where id = 1" in code, "Lucid-WD-TP 268–280 → 285–300 (Puffer 35–50 $ über 250), nur wenn noch der alte Wert steht")
check(285 - 250 > 24.5, "Puffer größer als die größte gesehene Lücke TP → Ergebnis (24,50 $ am 25.11.)")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
