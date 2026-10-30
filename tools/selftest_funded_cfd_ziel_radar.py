#!/usr/bin/env python3
"""Selbsttest: FUNDED CFD ZIEL IM RADAR (30.10.2026, Finn 14:1x). Ziel + Boden aus den Planer-Regeln (fcp_konto_ziel_boden, zw_funded_cfd), Weg nach Waiting bleibt
wd_erl_konto_umstellen_upd. Ohne Netz. Die Vorauswahl im Popup prüft der Browser-Stub. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_funded_cfd_ziel_radar.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


sql = open(os.path.join(WURZEL, "sql", "2026-10-30_funded_cfd_planer.sql"), encoding="utf-8").read()
import json  # noqa: E402
FIRMEN = json.loads(re.search(r"'(\[\s*\{.*?\]\s*)'::jsonb", sql, re.S).group(1))
R = lambda f: app.ap_regel_finden(FIRMEN, f)   # noqa: E731
Z = app.fcp_konto_ziel_boden
print("1) Ziel und Boden aus den Regeln")
check(Z(R("FundedNext"), 100000, 1) == (100050.0, 90000.0), f"FundedNext 100k ohne Payout: Refund-Ziel +50, Boden −10k ({Z(R('FundedNext'), 100000, 1)})")
check(Z(R("FundedNext"), 50000, 1) == (50050.0, 45000.0), "FundedNext 50k ohne Payout: +50, Boden −5k")
check(Z(R("FundedNext"), 100000, 2) == (101500.0, 90000.0), "FundedNext 100k nach Payout: +1.500")
check(Z(R("The5%ers"), 100000, 1) == (101300.0, 90000.0), "The5ers 100k: +1.300")
check(Z(R("FundingPips"), 100000, 2)[0] == 101250.0 and Z(R("FundingPips"), 100000, 2, "100k Flex 1") is None, "FundingPips +1.250, Flex nicht")
check(Z(R("Tradeify CFD"), 100000, 1)[0] == 101500.0, "Tradeify CFD +1.500")
check(Z(None, 100000, 1) is None and Z(R("FundingPips"), 200000, 1) is None, "ohne Regel/Größe: None — Zeile wie bisher")
print("2) Befund EzPoker a1ad322f (Zahlen aus der DB, 30.10.2026)")
zi = Z(R("FundedNext"), 100000, 1)[0]
check(100023.79 < zi, f"End-Balance 100.023,79 < Ziel {zi:,.0f} → NICHT erreicht, Popup unverändert")
print("3) Finns Beispiel + Schreibweg")
check(100000 + 3050 >= Z(R("The5%ers"), 100000, 2)[0], "The5ers +3.050 ≥ Ziel → vorausgewählt")
u, g = app.wd_erl_konto_umstellen_upd({"account_type": "funded_cfd", "waiting_payout_since": None}, "waiting", "2026-10-30T10:00:00+00:00", "30.10.2026")
check(u == {"waiting_payout_since": "2026-10-30T10:00:00+00:00"}, "vorhandener Weg setzt nur waiting_payout_since")
check(app.wd_erl_konto_umstellen_upd({"account_type": "funded_cfd", "waiting_payout_since": "x"}, "waiting", "j", "h")[0] is None, "schon Waiting: nichts")
print("4) zw_funded_cfd")
app._zw["ziele"].clear(); app._zw["boeden"].clear()
app._fcp_regeln_laden = lambda: {"firmen": FIRMEN}
K = [{"id": "k1", "name": "100k 1 → Funded", "firm": "FundedNext"}, {"id": "k2", "name": "100k 2 → Funded", "firm": "FundedNext"}, {"id": "k3", "name": "x", "firm": "FTMO"}]
app._sb_all = lambda t, p: K if t == "accounts" else ([{"id": "t1", "account_id": "k2"}] if t == "transactions" else [])
app.zw_funded_cfd()
check(app._zw["ziele"] == {"k1": 100050.0, "k2": 101500.0}, f"Refund bis zum ersten Payout, danach normal, FTMO ohne Regel leer ({app._zw['ziele']})")
alt = dict(app._zw["ziele"])
app._sb_all = lambda t, p: (_ for _ in ()).throw(RuntimeError("weg")) if t == "transactions" else K if t == "accounts" else []
try:
    app.zw_funded_cfd()
    fehler = False
except RuntimeError:
    fehler = True
check(fehler and app._zw["ziele"] == alt, "Payouts nicht lesbar: alte Werte bleiben, kein Refund-Ziel geraten (zw_tick fängt den Fehler)")
src = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("wdlFcfdZielErreicht(pw)) ? 'waiting' : 'none'" in src, "Radar-Popup: Vorauswahl nach geblowt/bestanden")
print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
