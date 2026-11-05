#!/usr/bin/env python3
"""Selbsttest KW-Etappe je Größe (LF1-Nebenbefund, 06.11.2026): ap_kw_param las tp_max nur aus phasen.challenge der Firma — Lucid 50k (Block tp_max 1.200)
und FundedNext Futures 50k (Block 1.000) rechneten den Kontowert mit der Etappe der großen Größe (3.600 / 3.200). Jetzt gilt die Etappe des Größen-Blocks,
ohne Block wie bisher; die Konto-Consistency geht weiter vor. Aufruf: python3 tools/selftest_kw_etappe_groesse.py"""
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
for f in ("_wd_num", "ap_groesse", "ap_kw_param", "_ap_kw_kauf", "_ap_kw_wachsen", "_ap_kw_lock", "ap_kontowert", "_ap_kw_usd", "ap_kw_stufe"):
    k = next(x for x in baum.body if isinstance(x, ast.FunctionDef) and x.name == f)
    exec(compile(ast.Module(body=[k], type_ignores=[]), "app.py", "exec"), ns)
KWP, KW, ST = ns["ap_kw_param"], ns["ap_kontowert"], ns["ap_kw_stufe"]
LU = {"boden": "nachziehend", "namen": ["lucidtrading", "lucid"], "dd_usd": 4500, "phasen": {"challenge": {"tp": [3450, 3550], "tp_max": 3600}},
      "groessen": [50000, 150000], "kauf_eur": {"50000": 78, "150000": 170}, "ziel_pct": {"challenge": 6}, "daily_usd": 2700, "lock_bei_start": True,
      "je_groesse": {"50000": {"dd_usd": 2000, "kauf_eur": 78, "daily_usd": 1200, "phasen": {"challenge": {"tp": [1150, 1180], "tp_max": 1200}}}}}
FNF = {"boden": "nachziehend", "namen": ["fundednextfutures"], "dd_usd": 4000, "phasen": {"challenge": {"tp_max": 3200}}, "groessen": [50000, 150000],
       "kauf_eur": {"50000": 90, "150000": 200}, "ziel_pct": {"challenge": 6}, "lock_bei_start": True,
       "je_groesse": {"50000": {"dd_usd": 1500, "phasen": {"challenge": {"tp_max": 1000}}}}}
TR = {"boden": "nachziehend", "namen": ["tradeify"], "dd_usd": 4500, "phasen": {"challenge": {"tp": [3450, 3550], "tp_max": 3600}}, "groessen": [150000],
      "kauf_eur": 215, "ziel_pct": {"challenge": 6}}

p = KWP(LU)
check(p["etappe_je_groesse"] == {"50000": 1200.0} and p["etappe_usd"] == 3600, "Lucid: Etappe 50k aus dem Block (1.200), Firma bleibt 3.600")
kv = KW("challenge", 51800, p)
check(kv["wert"] == 162 and kv["satz"] == 0.0811, f"Lucid 50k bei 51.800: 78 × (1+1.200/2.000) × (1+600/2.000) = 162 € (vorher 148) — {kv['wert']}")
check(ST("challenge", 51800, p, kv) == "Challenge · nach Etappe 1", f"Stufe zählt mit 1.200 je Etappe — {ST('challenge', 51800, p, kv)}")
kv = KW("challenge", 156000, p)
check(kv["wert"] == 469, f"Lucid 150k unverändert (Firma 3.600): 469 € — {kv['wert']}")
check(KW("challenge", 156000, KWP(TR))["wert"] == 593 and KWP(TR)["etappe_je_groesse"] == {}, "Tradeify ohne Block: unverändert 593 €, keine Größen-Etappe")
pf = KWP(FNF)
kv = KW("challenge", 50800, pf)
check(pf["etappe_je_groesse"] == {"50000": 1000.0} and kv["wert"] == round(90 * (1 + 800 / 1500)),
      f"FundedNext Futures 50k: Etappe 1.000 (Block) — {kv['wert']}")
alt = dict(p, etappe_je_groesse={}, etappe_usd=1500.0)
check(KW("challenge", 51800, alt)["wert"] == round(78 * (1 + 1500 / 2000) * (1 + 300 / 2000)), "Konto-Consistency (etappe_usd, Block geleert) geht vor")
check("kw_k = dict(kw, etappe_usd=cp_et, etappe_je_groesse={})" in SRC, "Probelauf/Vorrat: Konto-Consistency leert die Größen-Etappe")
print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
