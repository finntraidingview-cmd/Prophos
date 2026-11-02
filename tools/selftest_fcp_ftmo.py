#!/usr/bin/env python3
"""Selbsttest FTMO im Funded-CFD-Planer (Finn 03.11.2026 ~01:10 Dubai). Rechnet die echten Funktionen aus app.py mit der Regel aus
sql/2026-11-03_funded_cfd_ftmo.sql, ohne Netz und ohne DB. Finns Beispiele (Mitte 13,75 Lot, Ziel 2.000 $): normal 13,75 Lot, TP ≈ 145 Pkt;
Refund 50 $ → 0,68 Lot, 75 $ → 1,03, 100 $ → 1,37 (je ≈ 73 Pkt).

Aufruf:  python3 tools/selftest_fcp_ftmo.py"""
import json
import os
import re
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
sql = open(os.path.join(W, "sql", "2026-11-03_funded_cfd_ftmo.sql"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = {"re": re}


def lade(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^\S)", app, re.S | re.M)
    exec(m.group(0), ns)


def ruf(fn, *a, **k):
    for _ in range(40):
        try:
            return ns[fn](*a, **k)
        except NameError as e:
            lade(str(e).split("'")[1])
    raise RuntimeError(fn)


for n in ("FCP_ERSTER_PAYOUT_STANDARD", "FCP_LOT_SCHRITT", "fcp_konto_rechnen", "ap_regel_finden"):
    lade(n)
FTMO = json.loads(re.search(r"firmen \|\| '(\[.*?\])'::jsonb", sql, re.S).group(1))[0]
check(FTMO["namen"] == ["ftmo"] and FTMO["an"] is True, "SQL: Firma FTMO, Schlüssel ftmo, an")
check(ruf("ap_regel_finden", [FTMO], "FTMO") is FTMO and ruf("ap_regel_finden", [FTMO], "FTMO Futures") is None, "trifft „FTMO“, nie „FTMO Futures“")
jg = FTMO["je_groesse"]["100000"]
r = ruf("fcp_konto_rechnen", jg, 100000.0, 100000, 2, False, 1.0, 0.85, None, FTMO)
check(r["aktion"] == "planen" and r["lots"] == 13.75 and r["tp"] == 2000 and 144 <= r["tp_pkt"] <= 147, f"normal: 13,75 Lot, TP 2.000 $ ≈ 145 Pkt ({r.get('lots')}, {r.get('tp')}, {r.get('tp_pkt')})")
check(r["hedge_eur"] == 1500 and r["sl"] == 2100, f"normal: Hedge 1.500 €, SL Mitte 2.100 $ ({r.get('hedge_eur')}, {r.get('sl')})")
for ziel, soll in ((50, 0.68), (75, 1.03), (100, 1.37)):
    reg = dict(FTMO, erster_payout=dict(FTMO["erster_payout"], ziel=[ziel, ziel]))
    r = ruf("fcp_konto_rechnen", jg, 100000.0, 100000, 1, False, 1.0, 0.85, None, reg)
    check(r["aktion"] == "planen" and r["erster_payout"] and r["lots"] == soll and 70 <= r["tp_pkt"] <= 76,
          f"Refund {ziel} $ → {soll} Lot ≈ 73 Pkt ({r.get('lots')}, {r.get('tp_pkt')} Pkt)")
r = ruf("fcp_konto_rechnen", jg, 100000.0, 100000, 1, False, 1.0, 0.85, None, FTMO)
check(r["hedge_eur"] == 5000 and r["tp"] == 75, f"Refund-Zyklus: Hedge 5.000 € auf 10.000 $, Ziel Mitte 75 $ ({r.get('hedge_eur')}, {r.get('tp')})")
r = ruf("fcp_konto_rechnen", FTMO["je_groesse"]["200000"], 200000.0, 200000, 1, False, 1.0, 0.85, None, FTMO)
check(r["hedge_eur"] == 10000, f"200k Refund: Hedge 10.000 € auf 20.000 $ ({r.get('hedge_eur')})")
ohne = {k: v for k, v in FTMO.items() if k != "erster_payout"}
r = ruf("fcp_konto_rechnen", jg, 100000.0, 100000, 1, False, 1.0, 0.85, None, ohne)
check(r["erster_payout"] and r["hedge_eur"] == 5000, "Refund greift auch ohne erster_payout in der Regel (Standard je Schlüssel ftmo)")
r = ruf("fcp_konto_rechnen", jg, 100000.0, 100000, 2, False, None, 0.85, None, FTMO)
check(r["aktion"] == "aus" and "Punktwert" in r["grund"], "ohne Punktwert → aus mit Grund, nichts geplant")
print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
