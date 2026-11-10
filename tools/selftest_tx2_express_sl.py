"""TX2 (10.11.2026): Topstep Express im WD-Zufalls-SL. Prüft wd_sl_express_mll / wd_sl_fuer_plan (app.py, ausgeschnitten wie selftest_wd_sl_wuerfel.py)
und im Frontend hedgeLiqLevel: Würfel-Level nur, wenn Puls den Risk bei Topstep wirklich gesetzt hat (sonst MLL wie bisher).
Aufruf: python3 tools/selftest_tx2_express_sl.py"""
import json, os, subprocess, sys, tempfile
from datetime import datetime, timezone, timedelta
HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_wd_sl_wuerfel as ws1   # noqa: E402

FEHLER = []
def check(ok, t):
    print(("✓ " if ok else "✗ ") + t)
    if not ok: FEHLER.append(t)

class Folge:
    def __init__(self, *w): self.w = list(w)
    def random(self): return self.w.pop(0) if self.w else 0.5

ns = ws1.lade()
mll_f, fuer = ns["wd_sl_express_mll"], ns["wd_sl_fuer_plan"]
regel = ns["_wd_sl_std"]()
J = datetime.now(timezone.utc)
J0 = datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)   # feste Uhr mitten im CME-Handelstag (Test unabhängig von der Tageszeit)
iso = lambda d: d.isoformat()
ACC = {"id": "a1", "firm": "Topstep", "account_type": "winning_days", "name": "150k EXPRESS-V2-DLL-000000-00000000 → Winning Days",
       "external_id": "EXPRESS-V2-DLL-000000-00000000", "max_drawdown": 4500, "tv_balance": 1707.86, "tv_balance_at": iso(J - timedelta(minutes=30))}
def tr(start_h, ende_h, mll=None, bal_end=None, b=None):
    b = b or J
    return {"master_account_id": "a1", "started_at": iso(b - timedelta(hours=start_h)), "ended_at": iso(b - timedelta(hours=ende_h)), "mll_start": mll, "bal_end": bal_end}

# MLL-Rechnung
m, q = mll_f(ACC, [tr(5, 4.9, 0, 1707.86)])
check(m == 0 and "Lesung" in q, f"Lesung 0 (eingerastet) → MLL 0 ({q})")
m, q = mll_f(ACC, [tr(2, 1.9, -4500, 1000, J0)])
check(m == -3500, "Lesung −4.500, Ende heute bei 1.000 → laufender Tag zählt vorsichtig mit: 1.000 − 4.500 = −3.500")
m, q = mll_f(ACC, [tr(80, 79.9, -4500, -100), tr(50, 49.9, None, 1000)])
check(m == -3500 and "Schluss-Balance" in q, f"Tagesschluss 1.000 nach der Lesung → MLL 1.000 − 4.500 = −3.500 ({q})")
m, q = mll_f(ACC, [tr(80, 79.9, -4500, -100), tr(50, 49.9, None, 6000)])
check(m == 0, "Tagesschluss 6.000 → nachgezogen, höchstens 0")
m, q = mll_f(ACC, [tr(80, 79.9, -2000, -100), tr(50, 49.9, None, 500)])
check(m == -2000, "Tagesschluss unter Lesung + DD → Lesung bleibt (MLL zieht nie nach unten)")
# Gegenprüfung S1: Planung 22:00 UTC (02:00 Dubai, noch CME-Tag D) für den Start an D+1 — Lesung 14:30 UTC −2.000, Trade schließt +1.500, Max DD 2.000
P = datetime(2026, 11, 10, 22, 0, tzinfo=timezone.utc)
m, q = mll_f(dict(ACC, max_drawdown=2000), [tr(7.5, 7.0, -2000, 1500, P)])
check(m == -500, f"Planung vor dem CME-Wechsel: Schluss 1.500 − 2.000 = −500 statt Lesung −2.000 ({q})")
m, q = mll_f(ACC, [tr(80, 79.9, None, 4000), tr(5, 4.9, -4500, -200)])
check(m == -500, "Schluss VOR der Lesung (Lesung kurz nach Sessionbeginn) zählt auch: 4.000 − 4.500 = −500")
m, q = mll_f(dict(ACC, max_drawdown=None), [tr(80, 79.9, None, 4000), tr(5, 4.9, -4500, None)])
check(m == -4500, "Max DD fehlt, nur Schluss vor der Lesung → Lesung")
m, q = mll_f(ACC, [tr(80, 79.9, -1000, -900), tr(5, 4.9, -3000, -2500)])
check(m == -3000, "mehrere Lesungen → die jüngste gilt (−3.000), Schlüsse − Max DD liegen tiefer und heben nichts")
# Prüfer TX2 (a): Puffer-Balance zählt mit — Gewinn-/Hand-Trade ohne bal_end hob den Stand, Lesung älter
m, q = mll_f(ACC, [tr(80, 79.9, -4500, -100), tr(50, 49.9, None, None)], 3000)
check(m == -1500, f"Balance 3.000 (Trade ohne bal_end) → MLL 3.000 − 4.500 = −1.500 statt Lesung −4.500 ({q})")
m, q = mll_f(ACC, [tr(80, 79.9, -4500, -100)], 9000)
check(m == 0, "Balance 9.000 → MLL höchstens 0")
m, q = mll_f(dict(ACC, max_drawdown=None), [tr(80, 79.9, -4500, None)], 3000)
check(m is None and "Max DD" in q, "Balance da, Max DD fehlt → unbekannt (nicht nachziehbar)")
w = fuer(regel, {"master_firm": "Topstep"}, dict(ACC, tv_balance=3000, tv_balance_at=iso(J)), [{"x": 1}], [tr(80, 79.9, -4500, -100), tr(50, 49.9, None, None)], rnd=Folge(0.59, 0.5))
check(w and not w["ohne"] and w["liq_balance"] == -1400.0 and w["puffer"] == 4400.0, f"Würfel: Puffer = 3.000 − (−1.500 + 100) = 4.400 statt 7.400 ({w and w.get('puffer')})")
m, q = mll_f(ACC, [tr(5, 4.9, None, 1707.86)])
check(m is None and "MLL-Lesung" in q, "ohne Lesung → unbekannt, kein Raten")
m, q = mll_f(dict(ACC, max_drawdown=None), [tr(80, 79.9, -4500, -100), tr(50, 49.9, None, 1000)])
check(m is None and "Max DD" in q, "Tagesschluss nach Lesung, Max DD fehlt → unbekannt")
m, q = mll_f(ACC, [tr(5, 4.9, 145500, 1000)])
check(m is None, "absolute MLL (> 1.000, keine Express-Lesung) zählt nicht")

# Würfel für den Plan (Folge: 0.59 → Stufe 30–40 %, 0.5 → 35 %)
w = fuer(regel, {"master_firm": "Topstep"}, ACC, [{"x": 1}], [tr(5, 4.9, 0, 1707.86)], rnd=Folge(0.59, 0.5))
check(w and not w["ohne"] and w["puffer"] == 1607.86 and w["liq_balance"] == 100.0 and w["usd"] == round(1607.86 * w["pct"] / 100),
      f"Express: Puffer = Balance 1.707,86 − (MLL 0 + 100) = 1.607,86 → SL {w and w.get('usd')} $ ({w and w.get('pct')} %)")
w = fuer(regel, {"master_firm": "Topstep"}, dict(ACC, tv_balance=-2876.34), [{"x": 1}], [tr(5, 4.9, -4500, -2876.34)], rnd=Folge(0.59, 0.5))
check(w and not w["ohne"] and w["puffer"] == round(-2876.34 - (-4400), 2), f"Express negativ (0-basiert): Puffer {w and w.get('puffer')} $")
w = fuer(regel, {"master_firm": "Topstep"}, dict(ACC, tv_balance=50), [{"x": 1}], [tr(5, 4.9, 0, 50)], rnd=Folge(0.59, 0.5))
check(w and w["ohne"] and "MLL" in (w.get("grund") or ""), f"Balance unter MLL + 100 → ohne SL ({w and w.get('grund')})")
w = fuer(regel, {"master_firm": "Topstep"}, ACC, [{"x": 1}], [], rnd=Folge(0.59, 0.5))
check(w and w["ohne"] and "MLL-Lesung" in (w.get("grund") or ""), "ohne Lesung → ohne SL mit Grund (wie bisher)")
w = fuer(regel, {"master_firm": "Topstep"}, dict(ACC, tv_balance_at=None), [{"x": 1}], [tr(5, 4.9, 0, None)], rnd=Folge(0.59, 0.5))
check(w and w["ohne"], "Balance nach dem letzten Trade nicht gelesen → ohne SL")
w = fuer(regel, {"master_firm": "Topstep"}, ACC, [{"x": 1}], [tr(5, 4.9, 0, 1707.86)], rnd=Folge(0.1, 0.5))
check(w and w["ohne"] and w["grund"] == "gewürfelt: ohne SL", "Stufe „kein SL“ bleibt ohne SL")

# Frontend: hedgeLiqLevel — Würfel-Level nur mit gesetztem Risk
html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
def s(a, e):
    i = html.index(a); return html[i:html.index(e, i)]
js = ("const window = {}\n" + s("  function planWdSlUsd(p){", "  window._planWdSlUsd") + s("  function tsxBracketsFehlen(p){", "  // Text „SL (Risk)")
      + s("  const PULS_FEHLERBILD_RE", "\n", ) + "\n" + s("  function tsxWarnungBrackets(w){", "  window._tsxWarnungBrackets")
      + s("  function hedgeWdSlRiskBelegt(plan){", "  // -> {sl_punkte, sl_level_nq")
      + s("  function hedgeLiqLevel(plan, einstieg, ppl, kt){", "\n    // FINALER TRADEIFY MIT GEGENHEDGE") + "\n  return { hinweis: 'rest' } }\n" + r"""
const tv = { puls: 'tsx', quelle: 'tsx_order', mll_start: 0, balance_start: 1707.86, balance_relativ: true }
const wd = { ohne: false, usd: 600, pct: 37.3, balance: 1707.86, liq_balance: 100 }
const plan = (extra, route) => ({ route: route || 'tsv2', richtung: 'sell', masterSl: 600, mt5Baseline: { wd_sl: wd, tv: extra === 'kein_tv' ? undefined : Object.assign({}, tv, extra || {}) } })
const L = p => { const x = hedgeLiqLevel(p, 20000, 2, 3); return x.sl_art || ('hinweis:' + (x.liq_quelle || x.hinweis)) }
const out = {
  a: L(plan(null)), b: hedgeLiqLevel(plan({ brackets_fehlen: { risk: true, tp: false } }), 20000, 2, 3), c: L(plan({ brackets_fehlen: { risk: false, tp: true } })),
  kein_tv: L(plan('kein_tv')), nicht_puls: L(plan({ puls: 'tv' })), rueckfall: L(plan({ quelle: undefined })), ok_at: L(plan({ brackets_fehlen: { risk: true, tp: true }, brackets_ok_at: '2026-11-10T15:00:00Z' })),
  bf_true: L(plan({ brackets_fehlen: true })), warnung: L(plan({ warnung: 'Brackets in TopstepX prüfen: Risk 600 nicht gesetzt' })),
  snake: L({ route: 'tsv2', richtung: 'sell', masterSl: 600, mt5_baseline: { wd_sl: wd, tv: Object.assign({}, tv, { brackets_fehlen: { risk: true } }) } }),
  mt5: L(plan('kein_tv', 'mt5v2')),
}
print(JSON.stringify({ a: out.a, b: out.b.sl_art, bq: out.b.liq_quelle, c: out.c, kein_tv: out.kein_tv, nicht_puls: out.nicht_puls, rueckfall: out.rueckfall, ok_at: out.ok_at, bf_true: out.bf_true, warnung: out.warnung, snake: out.snake, mt5: out.mt5 }))
""")
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d.name], capture_output=True, text=True, timeout=60)
os.unlink(d.name)
try:
    e = json.loads(r.stdout.strip().splitlines()[-1])
except Exception:
    print(r.stdout[-500:], r.stderr[-500:]); e = {}
check(e.get("a") == "master_sl_wuerfel", "Hedge: Risk gesetzt → schließt am Würfel-SL-Level")
check(e.get("b") == "liquidation" and e.get("bq") == "topstepx_mll", "Hedge: Risk fehlt (🔴) → nie am Würfel-Level, MLL wie bisher")
check(e.get("c") == "master_sl_wuerfel", "Hedge: nur To Make fehlt → Würfel-Level bleibt")
check(e.get("kein_tv") not in (None, "master_sl_wuerfel"), f"Hedge-Open vor dem Start-Ergebnis (kein tv) → kein Würfel-Level, wie vor TX2 ({e.get('kein_tv')})")
check(e.get("nicht_puls") not in (None, "master_sl_wuerfel"), "tv ohne Puls-Start-Ergebnis (puls ≠ tsx) → kein Würfel-Level")
check(e.get("rueckfall") not in (None, "master_sl_wuerfel"), "Rückfall-Lesung tvV2BaselineLesen (ohne quelle tsx_order, ohne Bracket-Infos) → kein Würfel-Level")
check(e.get("ok_at") == "master_sl_wuerfel", "Risk fehlte, dann nachgewiesen (brackets_ok_at) → Würfel-Level")
check(e.get("bf_true") == "liquidation", "brackets_fehlen true (alter Bot) → MLL")
check(e.get("warnung") == "liquidation", "nur Warnungstext „Risk … nicht gesetzt“ (alter Bot) → MLL")
check(e.get("snake") not in (None, "master_sl_wuerfel"), "mt5_baseline (Schreibweise Backend) mit fehlendem Risk → kein Würfel-Level")
check(e.get("mt5") == "master_sl_wuerfel", "Nicht-Topstep (mt5v2) ohne tv → Würfel-Level unverändert")
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
