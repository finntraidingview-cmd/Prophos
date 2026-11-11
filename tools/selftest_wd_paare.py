#!/usr/bin/env python3
"""Selbsttest Zu bestätigen, Apex-WD (Finn 02.11.2026): TP Master ↔ Fusion SL und Daily Loss Master ↔ Fusion TP. Rechnet die echten Funktionen aus app.py und prophos.html, ohne Netz und ohne DB.

Aufruf:  python3 tools/selftest_wd_paare.py"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
app = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


import datetime as _dt
ns = {"re": re, "datetime": _dt.datetime, "timezone": _dt.timezone, "timedelta": _dt.timedelta, "AP_TYPEN": ("challenge", "phase1", "phase2"), "_firm_norm": lambda f: str(f or "")}   # Firmen-Normalisierung hat eine eigene Tabelle, hier heißt die Firma in Regel und Konto gleich


def lade(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^\S)", app, re.S | re.M)
    if m:
        exec(m.group(0), ns)


for name in ("_wd_num", "liq_regel_waehlen", "liq_stufe", "_liq_de", "liq_aus_regel", "liq_konto_groesse", "liq_konto_boden", "liq_boden_kernwerte", "_liq_pl_de", "liq_regel_felder", "_wd_konto_groesse", "plan_ist_wd",
             "plan_ist_apex_hedge", "plan_balance_relativ", "ist_topstep_express", "_wd_level", "ah_dll_balance", "hf_wd_master_verlust"):
    lade(name)


def MV(*a, **k):   # fehlende Helfer erst beim Aufruf nachladen, statt die Liste mit app.py mitzuziehen
    for _ in range(30):
        try:
            return ns["hf_wd_master_verlust"](*a, **k)
        except NameError as e:
            fehlt = e
            lade(str(e).split("'")[1])
    raise RuntimeError("Helfer fehlen: " + str(fehlt))


STUFEN = [{"ab_balance": 150000, "daily_loss_usd": 2500}, {"ab_balance": 155000, "daily_loss_usd": 3000}, {"ab_balance": 160000, "daily_loss_usd": 4000}]
R = [{"id": 4, "firma": "Apex Trader", "kontotyp": "funded", "groesse": 150000, "art": "stufen", "stufen": STUFEN, "maxdd_art": "eod_trailing", "maxdd_lock_ueber_groesse_usd": 100},
     {"id": 9, "firma": "Apex Trader", "kontotyp": "winning_days", "wie_kontotyp": "funded"}]
ACC = {"id": "a", "firm": "Apex Trader", "name": "150k PAAPEX6708370000001 → Winning Days", "account_type": "winning_days", "tv_balance": 160029.26}
PL = {"hedge_eur": 449.77, "winning_day": True}
m = MV(R, ACC, PL)
check(m.get("usd") == 4000 and m.get("art") == "daily_loss", f"Mike 160.029 $: Daily Loss der Stufe 4.000 $ ({m})")
m = MV(R, dict(ACC, tv_balance=156000), PL)
check(m.get("usd") == 3000 and m.get("art") == "daily_loss", f"Stufe nach Balance: 156.000 $ → 3.000 $ ({m})")
m = MV(R, dict(ACC, tv_balance=150500), PL)
check(m.get("usd") == 400 and m.get("art") == "liq", f"Liq fällt früher: 150.500 $ → 400 $ bis Größe + 100 ({m})")
# Tagesstart (S9-Hinweis 02.11.2026): früherer Trade heute auf demselben Konto → Daily Loss ab dessen Start-Balance, Verlust ab Balance jetzt
PLT = dict(PL, id="neu", master_account_id="a", start_um="2026-11-02T14:00:00+00:00")
FR = [{"id": "frueh", "master_account_id": "a", "started_at": "2026-11-02T10:00:00+00:00", "bal_start": 160500}]
m = MV(R, dict(ACC, tv_balance=159500), PLT, None, FR)
check(m.get("usd") == 3000 and m.get("tagesstart") == 160500, f"Tagesstart 160.500 $, jetzt 159.500 $ → noch 3.000 $ bis Daily Loss ({m})")
m = MV(R, dict(ACC, tv_balance=159500), PLT, None, [dict(FR[0], started_at="2026-10-30T10:00:00+00:00")])
check(m.get("usd") == 3000 and m.get("tagesstart") == 159500, f"Trade an einem anderen Handelstag zählt nicht → Tagesstart = Balance jetzt ({m})")
check("grund" in MV(R, dict(ACC, tv_balance=None), PL) and "grund" in MV(R, dict(ACC, tv_balance=150050), PL) and "grund" in MV(R, None, PL), "ohne Balance oder unter der Liq: Grund statt Zahl")
check('"winning_day,notes,slave_risk,master_risk,multiplier,"' in app and 'r["master_verlust"] = hf_wd_master_verlust(' in app, "Route liefert master_verlust, master_risk im Select")

if shutil.which("osascript"):
    def fn(name):
        i = html.index("function " + name + "(")
        return html[i:html.index("\n  }\n", i) + 5]
    code = fn("hedgeMultAusRisiko") + fn("hedgeRisikoMaster") + fn("hedgeLotsSoll") + fn("ahfWdPaare")
    # DL2 (11.11.2026): Puffer vor dem Daily Loss ≥ 100 $ (hedgeDllVorPkt), Kante „zu nah“ (hedgeDllVorEff) — einzeilige Funktionen aus prophos.html
    code += "".join(html[html.index("function " + n + "("):html.index("\n", html.index("function " + n + "("))] + "\n" for n in ("hedgeDllVorPkt", "hedgeDllVorEff"))
    test = """function run(){
var window = {}, accounts = [], HEDGE_DLL_VOR_PKT = 5, HEDGE_DLL_VOR_USD = 100; function tpIstApexHedge(){ return false } function tpWdSlavePpl(){ return 0.85 } function hedgePplFuer(s){ return /^M/.test(s) ? 2 : /^NQ/.test(s) ? 20 : 0 }
""" + code + """
var M = { master_contracts: '1.000', multiplier: '7.0624', master_tp: '1499.00', slave_risk: '449.93', master_risk: '1499.00', master_symbol: 'NQZ6', master_verlust: { usd: 4000, art: 'daily_loss' } };
var C = { master_contracts: '3.000', multiplier: '1.0893', master_tp: '324.00', slave_risk: '150.00', master_risk: '324.00', master_symbol: 'MNQZ6', master_verlust: { usd: 1500, art: 'daily_loss' } };
var O = { master_contracts: 1, master_tp: 1499, multiplier: 7.0624, master_symbol: 'NQZ6', master_verlust: { grund: 'keine Balance' } };
return JSON.stringify({ m: ahfWdPaare(M), c: ahfWdPaare(C), o: ahfWdPaare(O) });
}"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(test)
    try:
        aus = subprocess.run(["osascript", "-l", "JavaScript", f.name], capture_output=True, text=True, timeout=30)
    finally:
        os.unlink(f.name)
    check(aus.returncode == 0, "Tab-Rechnung läuft (" + aus.stderr[:200] + ")")
    if aus.returncode == 0:
        r = json.loads(aus.stdout)
        check(r["m"]["lots"] == 7.06 and round(r["m"]["tpEur"]) == 450, f"Mike 1 NQ, 7,06 Lot, TP 1.499 $ → −450 € ({r['m']['tpEur']})")
        check(round(r["m"]["dlEur"]) == 1170, f"Mike Daily Loss 4.000 $ = 200 Pkt, Fusion 5 Pkt vorher → +1.170 € obere Kante ({r['m']['dlEur']})")
        # DL2: 3 MNQ → Puffer 16,75 Pkt (= ≥ 100 $) statt 5: 250 − 16,75 = 233,25 Pkt
        check(round(r["c"]["tpEur"]) == 150 and abs(r["c"]["dlEur"] - r["c"]["lots"] * 0.85 * 233.25) < 0.01 and r["c"].get("dlVorPkt") == 16.75,
              f"3 MNQ: Punktwert aus dem Plan-Symbol, TP −150 €, 1.500 $ = 250 Pkt − 16,75 (DL2: ≥ 100 $) → +{round(r['c']['dlEur'])} € ({r['c']['tpEur']}, {r['c']['dlEur']})")
        check(r["o"]["dlEur"] is None and r["o"]["dlUsd"] is None and r["o"]["dlText"] == "keine Balance", "ohne Master-Verlust: Strich und Grund im Tooltip, keine erfundene Zahl")

print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
