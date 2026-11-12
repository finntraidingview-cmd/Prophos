#!/usr/bin/env python3
"""Selbsttest TX4 — Topstep: Fusion-Hedge-Liq am NÄHEREN von MLL + 100 und Tagesstart − DLL + 100, Radar zeigt „Tageslimit“ (Finn 12.11.2026 ~21:30: „dann soll der
Fusion schließen, wenn der Account selber schließt … bei −3.000 … Radar soll eben auch drauf“).

Aufruf:  python3 tools/selftest_tx4_topstep_dll_hedge.py
(1) prophos.html hedgeLiqLevel + hedgeTopstepDll + liqRegelWaehlen + kontoIstTopstepExpress echt in JavaScriptCore: Ina (Express 0-basiert, Tagesstart 20.524, DLL 3.000
    → Level bei Tagesstart − 2.900), zweiter Trade des Tages, Express ohne DLL-SKU, Express vor dem Lock, Combine 150k (DLL näher / MLL näher), fehlender bzw.
    unplausibler Tagesstart → nur MLL, Konto-dll_usd 0/2.000, Regeln nicht geladen.
(2) app.py liq_topstep_dll + liq_regel_felder (Radar) echt: Express-DLL → „Tageslimit“ (liq_gilt regel, soft), ohne DLL → MLL, Combine unverändert."""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(name):
    i = html.index(f"  function {name}(")
    return html[i:html.index("\n  }\n", i) + 4]


REGELN = [{"id": 8, "firma": "Topstep", "kontotyp": "challenge", "groesse": None, "art": "tagesstart", "betrag_usd": 3000, "wie_kontotyp": None},
          {"id": 6, "firma": None, "kontotyp": "winning_days", "groesse": None, "art": None, "betrag_usd": None, "wie_kontotyp": None}]
js = """
let accounts = [];
const planWdSlUsd = () => 0, hedgeWdSlRiskBelegt = () => true, hedgeIstTradeifyFinal = () => false, tpIstApexHedge = () => false;
const hedgeLiqStart = p => { const tv = p && p.mt5Baseline && p.mt5Baseline.tv; return tv && typeof tv.balance_start === 'number' ? { balance: tv.balance_start, quelle: 'balance_start' } : null };
const hedgeLiqDll = () => null, hedgeLiqDllApex = () => null, hedgeDllVorPkt = () => 0, hedgeDllVorEff = (a, b) => b, HEDGE_DLL_VOR_PKT = 0;
const REGELN_ALL = REGELN_JSON; let _liqRegeln = REGELN_ALL; const liqRegelnLaden = () => ({ catch(){} });
const firmNormRichtung = f => String(f || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const tpKontoGroesseAusName = n => { const m = /(\\d+)\\s*k\\b/i.exec(String(n || '')); return m ? Number(m[1]) * 1000 : null };
let TS = null;   // Tagesstart-Stub: null = eigene Lesung
const hedgeTagesstart = (plan, startBal) => TS != null ? { balance: TS, quelle: 'erster_trade_tag' } : { balance: startBal, quelle: 'start_balance' };
""".replace("REGELN_JSON", json.dumps(REGELN)) + fn("kontoIstTopstepExpress") + fn("liqRegelWaehlen") + fn("hedgeTopstepDll") + fn("hedgeLiqLevel") + """
const r = {};
const INA = { id: 'ina', firm: 'Topstep', name: '150k PRO-V2-DLL-688698-92558936 → Winning Days', type: 'winning_days', externalId: 'PRO-V2-DLL-688698-92558936', startingBalance: null, dllUsd: null };
const NODLL = { id: 'nodll', firm: 'Topstep', name: 'EXPRESS-V2-682437-57131691 → Winning Days', type: 'winning_days', externalId: 'EXPRESS-V2-682437-57131691', startingBalance: 150000, dllUsd: null };
const COMB = { id: 'comb', firm: 'Topstep', name: '150k 150KTC-SKU-V2-DLL-000000-00000001 → Challenge', type: 'challenge', externalId: '150KTC-SKU-V2-DLL-000000-00000001', startingBalance: 150000, dllUsd: null };
accounts = [INA, NODLL, COMB];
const plan = (acc, tv) => ({ masterAccountId: acc.id, masterName: acc.name, masterFirm: 'Topstep', route: 'tsv2', richtung: 'buy', mt5Baseline: { tv } });
const L = (acc, tv, kt) => hedgeLiqLevel(plan(acc, tv), 28630, 2, kt || 3);
r.ina = L(INA, { mll_start: 0, balance_start: 20524.08, balance_relativ: null });
TS = 21000; r.inaZweiter = L(INA, { mll_start: 0, balance_start: 20524.08, balance_relativ: null }); TS = null;
r.nodll = L(NODLL, { mll_start: 0, balance_start: 1866.2, balance_relativ: true });
r.exVorLock = L(INA, { mll_start: -2500, balance_start: 1200, balance_relativ: true });
r.combDll = hedgeLiqLevel(plan(COMB, { mll_start: 145500, balance_start: 152000, balance_relativ: null }), 28630, 20, 2);
r.combMll = hedgeLiqLevel(plan(COMB, { mll_start: 145500, balance_start: 147000, balance_relativ: null }), 28630, 20, 2);
TS = NaN; r.tsFehlt = L(INA, { mll_start: 0, balance_start: 20524.08, balance_relativ: null }); TS = null;
TS = 24000; r.tsUnplausibel = L(INA, { mll_start: 0, balance_start: 20524.08, balance_relativ: null }); TS = null;
INA.dllUsd = 0; r.konto0 = L(INA, { mll_start: 0, balance_start: 20524.08, balance_relativ: null });
INA.dllUsd = 2000; r.konto2000 = L(INA, { mll_start: 0, balance_start: 20524.08, balance_relativ: null }); INA.dllUsd = null;
TS = 0; r.s7 = L(INA, { mll_start: -4500, balance_start: -2950, balance_relativ: true }); TS = null;
_liqRegeln = null; r.ohneRegeln = L(INA, { mll_start: 0, balance_start: 20524.08, balance_relativ: null });
INA.dllUsd = 3000; r.ohneRegelnKonto = L(INA, { mll_start: 0, balance_start: 20524.08, balance_relativ: null }); INA.dllUsd = null;
_liqRegeln = REGELN_ALL; r.nachLaden = L(INA, { mll_start: 0, balance_start: 20524.08, balance_relativ: null });
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

print("1) Hedge-Level (Tab)")
i = r.get("ina") or {}
check(i.get("liq_art") == "daily_loss" and i.get("liq_quelle") == "topstep_dll" and abs((i.get("liq_balance") or 0) - 17624.08) < 0.01 and abs((i.get("sl_usd_hedge") or 0) - 2900) < 0.01
      and abs((i.get("sl_level_nq") or 0) - round(28630 - 2900 / 6, 2)) < 0.02 and (i.get("liq_dll") or {}).get("usd") == 3000 and i.get("liq_mll_balance") == 100,
      f"Ina (Express 0-basiert, Tagesstart 20.524, DLL 3.000): Level bei Tagesstart − 2.900 (483 Pkt), näher als MLL + 100 — {i.get('liq_balance')} / {i.get('sl_usd_hedge')}")
z = r.get("inaZweiter") or {}
check(abs((z.get("liq_balance") or 0) - 18100) < 0.01 and abs((z.get("sl_usd_hedge") or 0) - 2424.08) < 0.01 and (z.get("liq_dll") or {}).get("quelle") == "erster_trade_tag",
      "zweiter Trade des Tages: Tagesstart vom ersten Trade (21.000) → Liq 18.100, nur noch 2.424 $ Luft")
n = r.get("nodll") or {}
check(n.get("liq_art") == "mll_topstep" and n.get("liq_balance") == 100 and not n.get("liq_dll"), "Express ohne DLL-SKU („EXPRESS-V2-…“ ohne DLL): nur MLL + 100")
v = r.get("exVorLock") or {}
check(v.get("liq_art") == "daily_loss" and abs((v.get("liq_balance") or 0) - (-1700)) < 0.01 and abs((v.get("sl_usd_hedge") or 0) - 2900) < 0.01,
      "Express vor dem Lock (MLL −2.500, Balance 1.200): Tageslimit −1.700 näher als MLL + 100 = −2.400")
c1, c2 = r.get("combDll") or {}, r.get("combMll") or {}
check(c1.get("liq_art") == "daily_loss" and c1.get("liq_balance") == 149100 and c1.get("sl_usd_hedge") == 2900,
      "Combine 150k, Start 152.000, MLL 145.500: Tageslimit 149.100 (+100) näher → 2.900 $")
check(c2.get("liq_art") == "mll_topstep" and c2.get("liq_balance") == 145600 and c2.get("sl_usd_hedge") == 1400,
      "Combine 150k, Start 147.000: MLL + 100 = 145.600 näher als Tageslimit 144.100 → MLL")
for k, name in (("tsFehlt", "Tagesstart fehlt"), ("tsUnplausibel", "Tagesstart 24.000 bei Start 20.524 (Limit wäre schon gerissen / andere Basis)"),
                ("konto0", "Konto dll_usd 0 (ausdrücklich kein Tageslimit)"), ("ohneRegeln", "liq_regeln noch nicht geladen, kein Konto-DLL")):
    x = r.get(k) or {}
    check(x.get("liq_art") == "mll_topstep" and x.get("liq_balance") == 100 and abs((x.get("sl_usd_hedge") or 0) - 20424.08) < 0.01,
          f"{name}: nur MLL + 100 (fail-closed, kein Level nah am Kurs)")
s7 = r.get("s7") or {}
check(s7.get("liq_art") == "mll_topstep" and abs((s7.get("liq_balance") or 0) - (-4400)) < 0.01 and abs((s7.get("sl_usd_hedge") or 0) - 1450) < 0.01 and s7.get("sl_level_nq"),
      f"TX4b S7-Fall: Tagesstart 0, 2. Trade bei −2.950, DLL 3.000 → DLL-Level −2.900 läge über der Start-Balance → MLL-Level −4.400 statt gar keins — {s7.get('liq_balance')} / {s7.get('sl_usd_hedge')}")
o, ok_, nl = r.get("ohneRegeln") or {}, r.get("ohneRegelnKonto") or {}, r.get("nachLaden") or {}
check(o.get("liq_regeln_geladen") is False and o.get("liq_art") == "mll_topstep", "TX4b: Regeln nicht geladen → MLL-Level, liq_regeln_geladen false (der Wächter zieht nach)")
check(ok_.get("liq_regeln_geladen") is True and ok_.get("liq_art") == "daily_loss", "TX4b: DLL vom Konto → geladen true auch ohne Regeln")
check(nl.get("liq_regeln_geladen") is True and nl.get("liq_art") == "daily_loss" and abs((nl.get("liq_balance") or 0) - 17624.08) < 0.01,
      "TX4b: nach dem Laden der Regeln → Nachzug auf das DLL-Level (geladen true)")
k2 = r.get("konto2000") or {}
check(k2.get("liq_art") == "daily_loss" and abs((k2.get("liq_balance") or 0) - 18624.08) < 0.01 and (k2.get("liq_dll") or {}).get("dl_quelle") == "konto",
      "Konto dll_usd 2.000 geht vor der Regel (DL2-Konto-Limit)")

print("2) Radar (app.py)")
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402
A_INA = {"id": "ina", "firm": "Topstep", "name": "150k PRO-V2-DLL-688698-92558936 → Winning Days", "external_id": "PRO-V2-DLL-688698-92558936", "account_type": "winning_days",
         "max_drawdown": 4500}
A_NO = dict(A_INA, id="no", name="EXPRESS-V2-682437-57131691 → Winning Days", external_id="EXPRESS-V2-682437-57131691")
P = {"route": "tsv2", "winning_day": True, "konto_typ": "winning_days", "mt5_baseline": {"tv": {"balance_relativ": True}}}
check(app.liq_topstep_dll(REGELN, A_INA) == (3000.0, "Topstep-DLL") and app.liq_topstep_dll(REGELN, A_NO) == (None, None)
      and app.liq_topstep_dll(REGELN, dict(A_INA, dll_usd=0)) == (None, None) and app.liq_topstep_dll(REGELN, dict(A_NO, dll_usd=2000)) == (2000.0, "Konto")
      and app.liq_topstep_dll(REGELN, dict(A_INA, firm="Tradeify")) == (None, None), "liq_topstep_dll: DLL-SKU → Regel 3.000, ohne DLL keins, Konto 0/2.000, andere Firma nie")
f1 = app.liq_regel_felder(REGELN, A_INA, P, 20524.08, 20524.08, 28630, "buy", 2, 3, mll=0)
check(f1["liq_gilt"] == "regel" and f1["liq_regel_soft"] is True and abs(f1["liq_regel_balance"] - 17524.08) < 0.01 and "Tageslimit 3.000" in f1["liq_regel_text"],
      f"Radar Ina: Tageslimit 17.524 gilt vor der MLL 0 → „Tageslimit“ (liq_gilt regel, soft) — {f1['liq_regel_text']}")
f2 = app.liq_regel_felder(REGELN, A_NO, P, 1866.2, 1866.2, 28630, "buy", 2, 3, mll=0)
check(f2["liq_gilt"] == "boden" and f2["liq_regel_balance"] == 0, "Radar ohne DLL-SKU: MLL (Liq)")
f3 = app.liq_regel_felder(REGELN, A_INA, P, 20524.08, 24000, 28630, "buy", 2, 3, mll=0)
check(f3["liq_gilt"] == "boden", "Radar mit unplausiblem Tagesstart (Limit wäre schon gerissen): nur MLL")
A_C = {"id": "c", "firm": "Topstep", "name": "150k 150KTC-SKU-V2-DLL-000000-00000001 → Challenge", "external_id": "150KTC-SKU-V2-DLL-000000-00000001", "account_type": "challenge",
       "max_drawdown": 4500}
f4 = app.liq_regel_felder(REGELN, A_C, {"route": "tsv2", "konto_typ": "challenge"}, 152000, 152000, 28630, "buy", 20, 2, mll=145500)
check(f4["liq_gilt"] == "regel" and f4["liq_regel_balance"] == 149000 and "Tageslimit 3.000" not in f4["liq_regel_text"], "Combine: wie bisher über die Topstep-Challenge-Regel (149.000)")

print("3) Anker")
hl = fn("hedgeLiqLevel")
check("let tag = liqD != null && liqD > liqM" in hl and "liq_art: tag ? 'daily_loss' : 'mll_topstep'" in hl, "Tab: das NÄHERE von MLL + 100 und Tagesstart − DLL + 100")
wa = html[html.index("const ohneRegeln = "):html.index("const ohneRegeln = ") + 6000]
check("const ohneRegeln = h.liq_quelle === 'balance_start' && !h.liq_regeln_geladen && !!_liqRegeln" in wa and "liq_quelle: 'balance_start'" in wa and "hedgeLiqDllFelder(lq)" in wa,
      "Wächter: zieht nach (liq_quelle ≠ balance_start beim ersten Mal, danach ohneRegeln) und trägt liq_regeln_geladen aus dem Ergebnis")
check("liq_regeln_geladen: geladenT" in hl and "if(tag && !(bsT - liqD > 0) && bsT - liqM > 0) tag = false" in hl, "Tab: geladen ehrlich, Rückfall aufs MLL-Level")
check(html.count("liq_art !== 'daily_loss' ? 'liq' : 'sl'") == 1, "Hedge-Grund am Tageslimit wird als „sl“ statt „liq“ gezählt wie bei den anderen Firmen (daily_loss)")

print()
if FEHLER:
    print(f"{len(FEHLER)} FEHLER")
    sys.exit(1)
print("alles grün")
