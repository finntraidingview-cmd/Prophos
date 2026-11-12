#!/usr/bin/env python3
"""Selbsttest TX3 — Topstep Express: Liquidations-Level des Fusion-Hedges aus der TopstepX-MLL auch ohne balance_relativ (Master 12.11.2026, Vorfall Ina PRO
…8936 / Plan 0ad96857: liq_balance 150.100 gegen BAL 20.524 → kein Liq-Level). Fail-closed: unklares Express nie „Größe + 100“, nie ein falsches Level.

Aufruf:  python3 tools/selftest_tx3_express_hedge_liq.py
prophos.html hedgeLiqLevel + kontoIstTopstepExpress echt in JavaScriptCore (osascript), Rest gestubbt. Fälle: Ina (rel null, MLL 0 nach dem Lock) → Level MLL + 100;
Combine 150k MLL 145.500 unverändert; Express vor dem Lock (MLL −2.500) mit und ohne Merkmal; Express mit MLL > 0 (gibt es nicht, Lock bei 0) → Hinweis;
Express ohne Lesung (Hedge vor dem Puls-Ergebnis) → Hinweis statt 150.100; Express mit balance_relativ false → Hinweis; Combine ohne Lesung wie bisher."""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(name):
    i = html.index(f"  function {name}(")
    j = html.index("\n  }\n", i) + 4
    return html[i:j]


hl = fn("hedgeLiqLevel")
ke = fn("kontoIstTopstepExpress")
js = """
let accounts = [];
const planWdSlUsd = () => 0, hedgeWdSlRiskBelegt = () => true, hedgeIstTradeifyFinal = () => false, tpIstApexHedge = () => false;
const hedgeLiqStart = p => { const tv = p && p.mt5Baseline && p.mt5Baseline.tv; return tv && typeof tv.balance_start === 'number' ? { balance: tv.balance_start, quelle: 'balance_start' } : null };
const hedgeLiqDll = () => null, hedgeLiqDllApex = () => null, hedgeDllVorPkt = () => 0, hedgeDllVorEff = (a, b) => b, HEDGE_DLL_VOR_PKT = 0;
let _liqRegeln = null; const liqRegelnLaden = () => ({ catch(){} });
const tpKontoGroesseAusName = n => { const m = /(\\d+)\\s*k\\b/i.exec(String(n || '')); return m ? Number(m[1]) * 1000 : null };
""" + ke + "\n" + hl + """
const r = {};
const INA = { id: 'ina', firm: 'Topstep', name: '150k PRO-V2-DLL-688698-92558936 → Winning Days', type: 'winning_days', externalId: 'PRO-V2-DLL-688698-92558936', startingBalance: null };
const COMB = { id: 'comb', firm: 'Topstep', name: '150k 150KTC-SKU-V2-DLL-000000-00000001 → Challenge', type: 'challenge', externalId: '150KTC-SKU-V2-DLL-000000-00000001', startingBalance: 150000 };
const EX = { id: 'ex', firm: 'Topstep', name: '150k EXPRESS-V2-DLL-000000-00000002 → Funded', type: 'funded', externalId: 'EXPRESS-V2-DLL-000000-00000002', startingBalance: null };
accounts = [INA, COMB, EX];
const plan = (acc, tv) => ({ masterAccountId: acc.id, masterName: acc.name, route: 'tsv2', richtung: 'buy', mt5Baseline: tv === undefined ? {} : { tv } });
r.ina = hedgeLiqLevel(plan(INA, { mll_start: 0, balance_start: 20524.08, balance_relativ: null }), 28630, 2, 3);
r.comb = hedgeLiqLevel(plan(COMB, { mll_start: 145500, balance_start: 152000, balance_relativ: null }), 28630, 20, 2);
r.exVorMitMerkmal = hedgeLiqLevel(plan(EX, { mll_start: -2500, balance_start: 1200, balance_relativ: true }), 28630, 2, 3);
r.exVorOhneMerkmal = hedgeLiqLevel(plan(EX, { mll_start: -2500, balance_start: 1200, balance_relativ: null }), 28630, 2, 3);
r.exMllPositiv = hedgeLiqLevel(plan(EX, { mll_start: 500, balance_start: 20524.08, balance_relativ: null }), 28630, 2, 3);
r.exOhneLesung = hedgeLiqLevel(plan(EX), 28630, 2, 3);
r.exRelFalse = hedgeLiqLevel(plan(EX, { mll_start: 0, balance_start: 20524.08, balance_relativ: false }), 28630, 2, 3);
r.exAbsolut = hedgeLiqLevel(plan(EX, { mll_start: 0, balance_start: 152000, balance_relativ: null }), 28630, 2, 3);
r.exKnapp = hedgeLiqLevel(plan(EX, { mll_start: 0, balance_start: 80, balance_relativ: null }), 28630, 2, 3);
r.combOhneLesung = hedgeLiqLevel(plan(COMB), 28630, 20, 2);
JSON.stringify(r);
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(js)
try:
    aus = subprocess.run(["osascript", "-l", "JavaScript", f.name], capture_output=True, text=True, timeout=30)
    r = json.loads(aus.stdout.strip() or "{}")
    if not r:
        print(aus.stderr[:800])
except Exception as e:
    r = {}
    print(f"JXA: {type(e).__name__}: {e}")
finally:
    os.unlink(f.name)

i = r.get("ina") or {}
check(i.get("liq_art") == "mll_topstep" and i.get("liq_balance") == 100 and abs((i.get("sl_usd_hedge") or 0) - 20424.08) < 0.01
      and abs((i.get("sl_level_nq") or 0) - round(28630 - 20424.08 / 6, 2)) < 0.02 and i.get("sl_art") == "liquidation",
      f"Ina 0ad96857 (rel null, MLL 0 nach dem Lock): Liq = MLL + 100, Level {i.get('sl_level_nq')} weit unter dem Einstieg — {i}")
c = r.get("comb") or {}
check(c.get("liq_balance") == 145600 and c.get("sl_usd_hedge") == 6400 and c.get("liq_art") == "mll_topstep",
      f"Combine 150k MLL 145.500 (rel null): unverändert Liq 145.600, 6.400 $ — {c.get('liq_balance')} / {c.get('sl_usd_hedge')}")
a, b = r.get("exVorMitMerkmal") or {}, r.get("exVorOhneMerkmal") or {}
check(a.get("liq_balance") == -2400 and a.get("sl_usd_hedge") == 3600 and b.get("liq_balance") == -2400 and b.get("sl_usd_hedge") == 3600,
      "Express vor dem Lock (MLL −2.500, Balance 1.200): Liq −2.400, 3.600 $ — mit und ohne balance_relativ gleich")
for k, name in (("exMllPositiv", "Express mit MLL > 0 (gibt es nicht — Lock bei 0) → unklar"), ("exOhneLesung", "Express ohne TopstepX-Lesung (Hedge vor dem Puls-Ergebnis)"),
                ("exRelFalse", "Express, Auge sagt ausdrücklich „absolut“, Balance aber 0-basiert"), ("exAbsolut", "Express mit absolut aussehender Balance 152.000 und MLL 0")):
    x = r.get(k) or {}
    check(bool(x.get("hinweis")) and not x.get("sl_level_nq") and x.get("liq_balance") != 150100,
          f"{name}: nur Hinweis, kein Level, nie 150.100 — {x.get('hinweis')}")
kn = r.get("exKnapp") or {}
check(bool(kn.get("hinweis")) and not kn.get("sl_level_nq") and kn.get("liq_balance") == 100,
      "Express mit Balance 80 ≤ MLL + 100: kein Level (Hinweis), nichts nah am Kurs")
co = r.get("combOhneLesung") or {}
check(bool(co.get("hinweis")) and not co.get("sl_level_nq"), "Combine ohne Lesung: wie bisher Hinweis „keine Start-Balance“")

print("Anker")
check("tvT.balance_relativ === true || mllT > 1000 || expressOhneMerkmal" in hl and "mllT <= 0 && isFinite(bsT) && grT > 0 && bsT < grT / 2" in hl,
      "hedgeLiqLevel: Express ohne Merkmal nur bei MLL ≤ 0 und Start-Balance unter der halben Größe")
check(hl.index("expressOhneMerkmal)") < hl.index("Topstep Express: MLL aus TopstepX nicht sicher lesbar") < hl.index("let liq = groesse + 100"),
      "Fail-closed-Riegel liegt VOR dem Weg „Größe + 100“")
tb = html[html.index("  function tsxBaselineAusOrder("):html.index("  function tsxBaselineAusOrder(") + 5000]
check("let rel = tsxBalanceRelativ(r)" in tb and "bsR < grR / 2 && typeof kontoIstTopstepExpress === 'function' && kontoIstTopstepExpress(accR)) rel = true" in tb
      and "balance_relativ: rel" in tb, "tsxBaselineAusOrder: balance_relativ = true aus dem Konto, wenn das Auge null meldet (nur Express + 0-basiert)")
check("„150K DLL Express (…)“ (ohne $)" in hl, "Kommentar nennt die Ursache (Auge: Merkmal nur bei negativem MLL oder „$150K“ im Label)")

print()
if FEHLER:
    print(f"{len(FEHLER)} FEHLER")
    sys.exit(1)
print("alles grün")
