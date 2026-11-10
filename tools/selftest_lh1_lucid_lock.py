#!/usr/bin/env python3
"""Selbsttest LH1 Lucid-Lock (10.11.2026, Master; Quelle support.lucidtrading.com/en/articles/12945815-lucidflex-drawdown: „the MLL locks at the initial
balance plus $100“): der nachziehende Boden von Lucid sitzt bei Start + 100 fest (150.100 / 50.100), nicht am Start. Kernwerte (ap_kw_param.lock_plus_usd,
_ap_kw_lock, ap_kontowert), Vorrat-Chance (vorrat_chance_stufe), Planer-Boden (_ap_boden), Apex-Hedge-Boden (_ah_boden_eod, Quelltext) und tfh_mll.
FundedNext Futures (Lock am Start, plus 0) bitgleich. Aufruf: python3 tools/selftest_lh1_lucid_lock.py"""
import ast
import os
import re
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "app.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


baum = ast.parse(SRC)
ns = {"re": re}
for x in baum.body:
    if isinstance(x, ast.Assign) and getattr(x.targets[0], "id", "") in ("AP_GROESSE_TOLERANZ", "AP_KW_PHASEN", "AP_KW_FUNDED", "AP_KW_TYP_NAME"):
        exec(compile(ast.Module(body=[x], type_ignores=[]), "app.py", "exec"), ns)
for f in ("_wd_num", "ap_groesse", "ap_kw_param", "_ap_kw_kauf", "_ap_kw_wachsen", "_ap_kw_lock", "ap_kontowert", "_ap_boden", "vorrat_chance_stufe", "_vr2_num",
          "tfh_mll"):
    k = next(x for x in baum.body if isinstance(x, ast.FunctionDef) and x.name == f)
    exec(compile(ast.Module(body=[k], type_ignores=[]), "app.py", "exec"), ns)
KWP, KW, LOCK, BODEN, MLL = ns["ap_kw_param"], ns["ap_kontowert"], ns["_ap_kw_lock"], ns["_ap_boden"], ns["tfh_mll"]

LU = {"boden": "nachziehend", "namen": ["lucidtrading", "lucid"], "dd_usd": 4500, "phasen": {"challenge": {"tp": [3450, 3550], "tp_max": 3600}},
      "groessen": [50000, 150000], "kauf_eur": {"50000": 78, "150000": 170}, "ziel_pct": {"challenge": 6}, "daily_usd": 2700, "lock_bei_start": True,
      "je_groesse": {"50000": {"dd_usd": 2000, "kauf_eur": 78, "daily_usd": 1200, "phasen": {"challenge": {"tp": [1150, 1180], "tp_max": 1200}}}}}
FNF = {"boden": "nachziehend", "namen": ["fundednextfutures"], "dd_usd": 4000, "phasen": {"challenge": {"tp_max": 3200}}, "groessen": [50000, 150000],
       "kauf_eur": 200, "ziel_pct": {"challenge": 6}, "lock_bei_start": True, "je_groesse": {"50000": {"dd_usd": 1500, "phasen": {"challenge": {"tp_max": 1000}}}}}

# 1 · Kernwerte
check(KWP(LU)["lock_plus_usd"] == 100.0, "Lucid: lock_plus_usd 100")
check(KWP(FNF)["lock_plus_usd"] == 0.0, "FundedNext Futures: lock_plus_usd 0 (Lock am Start bleibt)")
check(KWP(dict(LU, lock_plus_usd=50))["lock_plus_usd"] == 50.0, "eigenes Feld lock_plus_usd gewinnt")


# 2 · _ap_kw_lock: plus 0 = alte Formel Wort für Wort
def alt(wert, gewinn, dd, etappe):
    rest, fertig = gewinn, 0.0
    while rest >= etappe - 1e-9:
        wert *= 1 + etappe / dd
        rest -= etappe
        fertig += etappe
        if fertig >= dd - 1e-9:
            return wert * gewinn / fertig, gewinn, True
    wert *= 1 + max(rest, 0) / dd
    return (wert, gewinn, True) if gewinn >= dd - 1e-9 else (wert, dd, False)


ok = all(LOCK(100.0, g, dd, et) == alt(100.0, g, dd, et) for g in (0, 500, 3199, 3200, 3999, 4000, 6400, 7000, 12000)
         for dd, et in ((4000, 3200), (1500, 1000), (4500, 3600)))
check(ok, "plus 0: _ap_kw_lock bitgleich mit der alten Formel (27 Fälle)")
v, pol, fest = LOCK(170.0, 4550, 4500, 3600, 100)
check(not fest and pol == 4500, "Lucid +4.550 (Boden 150.050): noch nicht gelockt, Polster 4.500")
v, pol, fest = LOCK(170.0, 4600, 4500, 3600, 100)
check(fest and pol == 4500, "Lucid +4.600 (Initial Trail Balance 154.600): gelockt bei 150.100, Polster 4.500")
v, pol, fest = LOCK(170.0, 6972.5, 4500, 3600, 100)
check(fest and pol == 6872.5, "Simon 156.972,50: gelockt, Polster 6.872,50 (= Balance − 150.100)")
v, pol, fest = LOCK(100.0, 9000, 4500, 4500, 100)   # Lock in voller Etappe: 4.500 < 4.600, erst die zweite Etappe lockt
check(fest and pol == 8900 and abs(v - 100 * 2 * 2 * 8900 / 8900) < 1e-9, "Lock in einer vollen Etappe: Polster Gewinn − 100")

# 3 · ap_kontowert
kv = KW("challenge", 156972.5, KWP(LU))
check(kv["polster"] == 6872 or kv["polster"] == 6873, f"Lucid-Kontowert Simon: Polster {kv['polster']} (Balance − 150.100, vorher 6.973)")
kv = KW("challenge", 154550, KWP(LU))
check(kv["polster"] == 4500, "Lucid 154.550: Boden zieht noch nach, Polster 4.500")
kv_f = KW("challenge", 157000, KWP(FNF))
p_alt = dict(KWP(FNF)); p_alt.pop("lock_plus_usd")
check(kv_f == KW("challenge", 157000, p_alt) and kv_f["polster"] == 7000, "FundedNext Futures 157.000: Polster 7.000 wie bisher (Lock am Start)")
kv5 = KW("challenge", 52200, KWP(LU))
check(kv5["polster"] == 2100, f"Lucid 50k 52.200: gelockt bei 50.100, Polster 2.100 ({kv5['polster']})")

# 4 · Planer-Boden
check(BODEN(LU, {}, 150000, 156000)[0] == 150100, "Planer-Boden Lucid 156.000: 150.100")
check(BODEN(LU, {}, 150000, 154000)[0] == 149500, "Planer-Boden Lucid 154.000: zieht nach 149.500")
check(BODEN(FNF, {}, 150000, 156000)[0] == 150000, "Planer-Boden FundedNext Futures 156.000: 150.000 wie bisher")

# 5 · Vorrat-Chance (modell trades + lock)
VC = ns["vorrat_chance_stufe"]
r = {"modell": "trades", "ziel_pct": 6, "risiko_usd": 4500, "etappe_usd": 3600, "lock_bei_start": True}
a, b = VC(dict(r, lock_plus_usd=100.0), 156000, 150000), VC(r, 156000, 150000)
check(a.get("boden") == 150100 and b.get("boden") == 150000, f"Vorrat-Chance: Boden Lucid 150.100, ohne plus 150.000 ({a.get('boden')}, {b.get('boden')})")
# Prüfer LH1: Folge-Trades ab dem Start (3.600/3.600/1.800) — 3. Trade Polster 7.100 (Lock 150.100) statt 7.200
a, b = VC(dict(r, lock_plus_usd=100.0), 150000, 150000), VC(r, 150000, 150000)
pa, pb = [t["polster"] for t in (a.get("trades") or [])], [t["polster"] for t in (b.get("trades") or [])]
check(len(pa) == 3 and pa[2] == 7100 and pb[2] == 7200 and pa[:2] == pb[:2], f"Vorrat-Chance Folge-Trades: Lucid {pa}, ohne plus {pb}")

# 6 · tfh_mll
ns["ap_regel_finden"] = lambda firmen, firm: LU
ns["_wd_konto_groesse"] = lambda a: 150000.0 if "150" in str(a.get("name")) else 50000.0
check(MLL({"firm": "Lucid Trading", "name": "150K LFE…0003", "max_drawdown": 4500}, []) == 4500, "tfh_mll 150k: 4.500")
check(MLL({"firm": "Lucid Trading", "name": "150K", "max_drawdown": None}, []) == 4500, "tfh_mll ohne Konto-Wert: Kernwerte 4.500")
check(MLL({"firm": "Lucid Trading", "name": "50K", "max_drawdown": 2000}, []) == 2000, "tfh_mll 50k: 2.000 (je Größe)")
check(MLL({"firm": "Lucid Trading", "name": "150K", "max_drawdown": 3000}, []) is None, "tfh_mll Konto 3.000 ≠ Kernwerte 4.500 → None (kein Hedge)")

# 7 · Apex-Hedge-Boden (Quelltext)
check("boden = min(boden, float(b_gr) + float(kw.get(\"lock_plus_usd\") or 0.0))" in SRC and "kw_lock=" not in SRC,
      "_ah_boden_eod: Kernwerte-Lock bei Größe + lock_plus_usd (Lucid 150.100), liq_regeln-Lock gewinnt weiter")
check("support.lucidtrading.com/en/articles/12945815-lucidflex-drawdown" in SRC, "Quelle im Kommentar")

print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
