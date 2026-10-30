#!/usr/bin/env python3
"""Selbsttest: wdlBlowStand behandelt Balance ≤ 0 wie fehlend (Prüfer S2 30.10.2026), außer Topstep (0-basiert). Führt die echte Funktion aus prophos.html in macOS-JavaScriptCore (jsc) aus.
Aufruf: python3 tools/selftest_blowstand_null.py"""
import json
import os
import subprocess
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
i = src.index("  function wdlBlowStand(t){")
j = src.index("\n  }\n", i) + 5
js = "const WDL_TSX_SCHAETZ_TIP='';const wdlTsxBlowSchaetzung=()=>null;\n" + src[i:j] + """
const B={route:'mt5',status:'review',boden_usd:90000,balance_start:100000,ended_at:'2026-10-30T08:00:00Z'};
const f=x=>wdlBlowStand(Object.assign({},B,x));
print(JSON.stringify({null_:f({balance_end:0}),neg:f({balance_end:-5}),gut:f({balance_end:100024}),blow:f({balance_end:89000}),
 konto0:f({konto_balance:0,konto_balance_at:'2026-10-30T09:00:00Z'}),
 fallback:f({balance_end:0,konto_balance:100010,konto_balance_at:'2026-10-30T09:00:00Z'}),
 challenge:f({balance_end:0,konto_typ:'phase1'}),tsx:f({route:'tsv2',balance_end:0,boden_usd:null,liq_balance:-2000}),tsxneg:f({route:'tsv2',balance_end:-300,boden_usd:null,liq_balance:-2000})}))
"""
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
d = json.loads(subprocess.run([JSC, "-e", js], capture_output=True, text=True, check=True).stdout)
FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


check(d["null_"] is None and d["neg"] is None, "Copier-Balance 0 / negativ → wie fehlend, nicht geblowt")
check(d["challenge"] is None, "gilt auch für Challenges")
check(d["konto0"] is None, "Konto-Balance 0 ebenso")
check(d["fallback"]["bal"] == 100010 and not d["fallback"]["geblowt"], "End-Balance 0, frische Konto-Balance → die Konto-Balance zählt")
check(d["gut"]["bal"] == 100024 and not d["gut"]["geblowt"], "normale Balance unverändert")
check(d["blow"]["geblowt"] is True, "echte Balance unter dem Boden bleibt geblowt")
check(d["tsx"]["bal"] == 0 and d["tsxneg"]["bal"] == -300, "Topstep 0-basiert: 0 und negativ bleiben echte Stände")
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
