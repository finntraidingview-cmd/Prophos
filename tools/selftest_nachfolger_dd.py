#!/usr/bin/env python3
"""Selbsttest NACHFOLGER MAX DRAWDOWN (prophos.html sucDdVorschlag/sucDdNachtragen, 30.10.2026 — Finn: „bei CFDs von Phase 1 zu Phase 2 immer genau das Gleiche,
auch wenn es noch nicht hinterlegt ist"). Aufruf: python3 tools/selftest_nachfolger_dd.py   (ohne Netz; Quelltext-Prüfung, die Fälle liefen im Stub)."""
import os
import re
import sys

html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


i = html.index("function sucDdVorschlag(")
fn = html[i:html.index("window._sucDdVorschlag", i)]
ein = html[html.index("async function sucDdNachtragen("):html.index("function openSuccessorWizard(")]
check("pos(acc.maxDrawdown) || !sucIstCfd(acc)" in fn, "Vorgänger mit Wert oder Futures: kein Rückfall")
check("tpFirmIstFutures(acc.firm) && !istTradeifyCfd(acc.firm)" in html[i - 400:i], "nur CFD-Firmen, Tradeify CFD zählt als CFD")
check(".size === 1 ? phasen[0] : null" in fn and "zielTyp === 'phase1' || zielTyp === 'phase2'" in fn, "andere Phase nur für Phase 1/2 und nur bei einem Wert, Funded nur mit eigener Schablone")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.py"), encoding="utf-8").read()
ns = {"ap_regel_finden": lambda fs, f: next((x for x in fs if f in x["namen"]), None)}
k = src.index("\ndef konto_dd_aus_regel(") + 1
exec(src[k:src.find("\n\n\n", k)], ns)
R = ns["konto_dd_aus_regel"]
F = [{"namen": ["The5%ers"], "dd_pct": 10}, {"namen": ["FundingPips"], "dd_pct": 10, "flex": {"dd_pct": 12}}, {"namen": ["Topstep"], "dd_usd": 4500},
     {"namen": ["Blue"], "dd_pct": 8, "je_groesse": {"50000": {"dd_pct": 6}}}]
check(R(F, "The5%ers", 200000) == 20000 and R(F, "The5%ers", 100000) == 10000, "Regel: The5%ers 200k → 20.000, 100k → 10.000")
check(R(F, "FundingPips", 100000) is None, "Regel: FundingPips (Standard/Flex) → leer")
check(R(F, "Topstep", 150000) is None and R(F, "Unbekannt", 100000) is None and R(F, "The5%ers", 0) is None, "Regel: Futures, unbekannte Firma, ohne Größe → leer")
check(R(F, "Blue", 50000) == 3000 and R(F, "Blue", 100000) == 8000, "Regel: dd_pct je Größe vor dem Firmen-Wert")
check('"/konto/dd-vorschlag"' in src and "_uid, err = _wd_login()" in src, "Route nur mit Login")
check("String(el.value || '').trim() !== ''" in ein and "String(_successorParentAccId) !== String(acc.id)" in ein, "Hand-Eingabe und anderer Vorgänger werden nie überschrieben")
check(re.search(r"sucWdBlockRender\(acc\)\n\s+sucDdNachtragen\(acc, sucType\.value\)", html) is not None, "Assistent ruft den Rückfall mit dem Zieltyp auf")
check("if(!maxDrawdown){" in html and "Max Drawdown ist nötig" in html, "Pflichtfeld bleibt: Futures ohne Wert wird weiter abgelehnt")
print(f"\n{'selftest_nachfolger_dd: alle Prüfungen grün' if not FEHLER else f'✗ {len(FEHLER)} Fehler'}")
sys.exit(1 if FEHLER else 0)
