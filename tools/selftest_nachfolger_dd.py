#!/usr/bin/env python3
"""Selbsttest NACHFOLGER MAX DRAWDOWN (prophos.html sucDdVorschlag/sucDdNachtragen, 30.10.2026 — Finn: „bei CFDs von Phase 1 zu Phase 2 immer genau das Gleiche,
auch wenn es noch nicht hinterlegt ist"; DD1 06.11.2026: „Schablone und Nachfolger-Anlegen IMMER mit Max Drawdown" — auch Futures, FundingPips Standard, Bulk, Reset,
/admin/konto-anlegen). Aufruf: python3 tools/selftest_nachfolger_dd.py   (ohne Netz; Quelltext-Prüfung, die Fälle liefen im Stub)."""
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
check("pos(acc.maxDrawdown) || !SUC_DD_TYPEN.includes(zielTyp)" in fn, "Vorgänger mit Wert gewinnt; nur Prop-Firm-Typen")
check("const SUC_DD_TYPEN = ['challenge', 'phase1', 'phase2', 'funded', 'funded_cfd']" in html, "DD1: CFD und Futures, nie Live/Winning Days")
check("if(liste.length && !einig) return null" in fn and "zielTyp === 'phase1' || zielTyp === 'phase2'" in fn, "Schablonen uneinig: leer; andere Phase nur für Phase 1/2, Funded nur mit eigener Schablone")
check("sucDdNieRaten(acc)) return null" in fn and "sucDdNieRaten(acc)) return null" in html[html.index("async function sucDdErmitteln("):]
      and "=== 'fundingpips' && /flex/i.test(String(acc.name || ''))" in html, "DD1: FundingPips nur mit „Flex“ im Namen leer (12 % weiß nur Finn), sonst Standard-Wert")
check("&typ=${encodeURIComponent(zielTyp || '')}" in html, "DD1: Zieltyp geht an den Server (Funded CFD → Funded-CFD-Regel)")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.py"), encoding="utf-8").read()
ns = {"re": re}
for fn_name in ("_wd_num", "_ap_norm", "ap_regel_finden", "konto_dd_aus_regel", "konto_dd_ergaenzen"):
    k = src.index(f"\ndef {fn_name}(") + 1
    exec(src[k:src.find("\n\n\n", k)], ns)
R, E = ns["konto_dd_aus_regel"], ns["konto_dd_ergaenzen"]
F = [{"namen": ["the5ers"], "dd_pct": 10, "je_groesse": {"200000": {"dd_pct": None, "dd_usd": None}}}, {"namen": ["fundingpips"], "dd_pct": 10, "flex": {"dd_pct": 12}},
     {"namen": ["topstep"], "dd_usd": 4500, "groessen": [150000]}, {"namen": ["blue"], "dd_pct": 8, "je_groesse": {"50000": {"dd_pct": 6}}},
     {"namen": ["apextrader"], "dd_usd": 4000, "groessen": [100000, 150000], "je_groesse": {"100000": {"dd_usd": 3000}}}, {"namen": ["tradeify"], "dd_usd": 4500, "groessen": [150000]}]
FC = [{"namen": ["the5ers"], "je_groesse": {"100000": {"dd": 9000}}}]
check(R(F, "The5%ers", 200000) == 20000 and R(F, "The5%ers", 100000) == 10000, "Regel: The5%ers 200k → 20.000 (leerer je_groesse-Block fällt auf dd_pct), 100k → 10.000")
check(R(F, "FundingPips", 100000) == 10000, "DD1: FundingPips → Standard-Wert 10 % (wie leer in ap_konto_flex)")
check(R(F, "Topstep", 150000) == 4500 and R(F, "Apex Trader", 100000) == 3000 and R(F, "Apex Trader", 150000) == 4000, "DD1: Futures dd_usd je Größe, sonst Firmen-Wert für eine Größe aus groessen")
check(R(F, "Tradeify", 300000) is None and R(F, "Unbekannt", 100000) is None and R(F, "The5%ers", 0) is None, "Größe außerhalb groessen, unbekannte Firma, ohne Größe → leer")
check(R(F, "Blue", 50000) == 3000 and R(F, "Blue", 100000) == 8000, "Regel: dd_pct je Größe vor dem Firmen-Wert")
check(R(F, "The5%ers", 100000, "funded_cfd", FC) == 9000 and R(F, "The5%ers", 100000, "phase1", FC) == 10000, "DD1: Funded CFD erst funded_cfd_plan_regeln je_groesse.dd")
z = {"name": "100k X → Phase 1", "firm": "The5%ers", "account_type": "phase1"}
check(E(z, {"max_drawdown": 20000, "account_size": 200000}, F) == "kernwert" and z["max_drawdown"] == 10000, "Ergänzen: Schablone anderer Größe zählt nicht → Kernwert")
z = {"name": "200k X → Phase 1", "firm": "The5%ers", "account_type": "phase1"}
check(E(z, {"max_drawdown": 20000, "account_size": 200000}, F) == "schablone" and z["max_drawdown"] == 20000, "Ergänzen: Schablone gleicher Größe vor dem Kernwert")
z = {"name": "150k X → Funded", "firm": "Apex Trader", "account_type": "funded", "max_drawdown": 5000}
check(E(z, None, F) is None and z["max_drawdown"] == 5000, "Ergänzen: vorhandener Wert bleibt")
z = {"name": "Fusion Live", "firm": "Fusion Markets", "account_type": "live"}
check(E(z, None, F) is None and "max_drawdown" not in z and E({"name": "150k", "firm": "Apex Trader", "account_type": "winning_days"}, None, F) is None, "Ergänzen: Live und Winning Days nie")
z = {"name": "100k X → Phase 1 · Flex", "firm": "FundingPips", "account_type": "phase1"}
check(E(z, None, F) is None and E({"name": "100k Y → Phase 1", "firm": "FundingPips", "account_type": "phase1"}, None, F, namen=("100k X → Phase 2 · Flex",)) is None,
      "Gegenprüfung: Server lässt FundingPips Flex leer, auch über den alten Namen beim Reset")
z = {"name": "100k Y → Phase 1", "firm": "FundingPips", "account_type": "phase1"}
check(E(z, None, F) == "kernwert" and z["max_drawdown"] == 10000, "FundingPips ohne Flex → Standard 10.000")
r = src[src.index('@app.route("/konto-reset-bestaetigen"'):]
r = r[:r.index("\n@app.route(")]
check("konto_vorlage_finden(vorlagen, alt.get(\"firm\"), konto_reset_typ(alt.get(\"account_type\")), _gr_alt)" in r and "if _gr_alt:" in r and "namen=(alt.get(\"name\"),)" in r,
      "Gegenprüfung: Reset sucht die Schablone mit der Größe aus dem alten Namen, ohne Größe kein Max DD")
check("signal: AbortSignal.timeout(8000)" in html[html.index("async function sucDdErmitteln("):html.index("async function sucDdNachtragen(")], "Gegenprüfung: Kernwert-Abfrage bricht nach 8 s ab (Bulk hängt nie)")
check(len(re.findall(r"(?<!def )konto_dd_ergaenzen\(zeile, ", src)) == 2 and "def _konto_dd_regeln(" in src, "Reset und /admin/konto-anlegen ergänzen über denselben Weg")
b = html[html.index("async function saveBulkAccounts("):]
check("sucDdErmitteln({ firm, name, startingBalance: gr, maxDrawdown: null, userId: currentUserId }, typRow)" in b[:12000] and "ddCache" in b[:12000], "DD1: Bulk ohne Vorlage/Formular-Wert → Schablone/Kernwert, einmal je Firma × Größe × Typ")
check('"/konto/dd-vorschlag"' in src and "_uid, err = _wd_login()" in src, "Route nur mit Login")
check("String(el.value || '').trim() !== ''" in ein and "String(_successorParentAccId) !== String(acc.id)" in ein, "Hand-Eingabe und anderer Vorgänger werden nie überschrieben")
check(re.search(r"sucWdBlockRender\(acc\)\n\s+sucDdNachtragen\(acc, sucType\.value\)", html) is not None, "Assistent ruft den Rückfall mit dem Zieltyp auf")
check("if(!maxDrawdown){" in html and "Max Drawdown ist nötig" in html, "Pflichtfeld bleibt: Futures ohne Wert wird weiter abgelehnt")
m = html[html.index("async function acDdVorschlag("):html.index("  function acNameVorschlag(){")]
check("sucDdErmitteln(" in m and "sucDdVorschlag(" not in m, "Account-Modal rechnet nicht selbst, gleicher Weg wie der Nachfolger")
check("_editingAccountId || acDdFremd()" in m and "_acDdAuto = null; _acDdLauf++" in html, "Modal: Bearbeiten, Hand-Eingabe und Schablonen-Wert bleiben unangetastet")
check("Größe (k) ist Pflicht" in html and "Max Drawdown ($, optional)" in html, "Modal: Drawdown bleibt optional")
print(f"\n{'selftest_nachfolger_dd: alle Prüfungen grün' if not FEHLER else f'✗ {len(FEHLER)} Fehler'}")
sys.exit(1 if FEHLER else 0)
