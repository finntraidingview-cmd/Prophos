#!/usr/bin/env python3
"""Selbsttest „Konto weg → Urteil aus dem letzten Trade“ und „Abhaken bestanden → Review“ (Finn 02.11.2026, Vorfall Ina Tradeify 150k …622221, Plan 7085e82a).
Rechnet die echten Funktionen aus prophos.html (JavaScriptCore) und app.py, ohne Netz und ohne DB.

Aufruf:  python3 tools/selftest_konto_weg_letzter_trade.py"""
import json
import os
import re
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
app = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
fehler = []


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        fehler.append(text)


def block(anfang, ende):
    i = html.index(anfang)
    return html[i:html.index(ende, i)]


code = (block("  const KONTO_WEG_LIQ_NAH_ANTEIL", "  window._kontoWegUrteil")
        + block("  const KW_ENDE_TP", "  window._kontoWegLetztesEnde")
        + block("  function kontoWegStand(acc){", "  const _kontoWegErledigt")
        + block("  const _kontoWegErledigt", "  window._kontoWegFolge"))
STUBS = """
const window = {}; let log = [];
function kontoGroesseAnzeige(){ return 150000 }
function isAccountArchived(){ return false }
function archiveAccount(id, g){ log.push('archiv:' + g) }
async function archivPlaeneEntfernen(){ log.push('plaene_weg') }
async function baselinePatchIn(id, k, p){ log.push('plan:' + (p.konto_weg_urteil || '')) }
function renderTradePlans(){} function renderAccounts(){} function atToast(){}
async function _pushTok(){ return '' }
const WATCHER_HOME = ''; async function fetch(){ return {} }
const supabase = { from: () => { const q = { _u: null, update(u){ q._u = u; return q }, eq(){ return q }, is(){ return q },
  select: async () => { log.push('konto:' + JSON.stringify(q._u)); return { data: [{ id: 'k' }], error: null } } }; return q } };
let accounts = [], tradePlans = [];
"""
def lauf(acc, plaene):
    return ("accounts = [" + json.dumps(acc) + "]; tradePlans = " + json.dumps(plaene) + "; log = [];"
            "await kontoWegFolge(" + json.dumps(acc["id"]) + ", {}, 'endlesung'); ergebnisse.push(log);")

INA = {"id": "k1", "firm": "Tradeify", "externalId": "TDFY622221", "name": "150k TDFY622221 → Phase 1", "type": "challenge", "maxDrawdown": 4500,
       "tvBalance": 157051, "tvBalanceAt": "2026-11-02T10:14:00Z", "zielUsd": 159000, "autoPlaner": True}
PLAN = {"id": "7085e82a", "masterAccountId": "k1", "status": "review", "startedAt": "2026-11-02T12:00:00Z", "endedAt": "2026-11-02T12:30:00Z",
        "masterTp": 1989, "masterSl": None, "masterPl": None, "mt5Baseline": {"hedge": {"grund": "master_ende_reader"}, "final": {"grund": "level_tp"}}}
def p(**k):
    x = json.loads(json.dumps(PLAN)); x.update(k); return x
def mit_final(**f):
    x = p(); x["mt5Baseline"]["final"] = f; return x

faelle = [
    ("TP-Ende (Level) + Konto weg → Review", INA, [p()]),
    ("SL-Ende (Demo-Liq) + Konto weg → geblowt", INA, [mit_final(grund="demo_liq")]),
    ("Hand-Schluss + Konto weg → prüfen", INA, [mit_final(grund="hand")]),
    ("kein Ende bekannt, Stand unter Start → alte Regel", dict(INA, tvBalance=146200), [mit_final()]),
    ("TP-Ende aus P&L gegen TP (Ina: +1.989 $ am TP)", INA, [dict(mit_final(), masterPl=1989)]),
    ("Funded am TP → prüfen, nie bestanden", dict(INA, type="funded"), [p()]),
    ("SL-Ende, Stand weit über dem Boden → prüfen", INA, [dict(mit_final(grund="demo_sl"), masterPl=-1200)]),
    ("SL-Ende, Stand am Boden → geblowt", dict(INA, tvBalance=146400), [dict(mit_final(grund="demo_sl"), masterPl=-600)]),
    ("Hedge-SL ist Liq-Level → geblowt", INA, [dict(p(), mt5Baseline={"hedge": {"grund": "level_sl", "sl_art": "liquidation"}, "final": {}})]),
    ("Hedge-SL am Daily-Loss-Level, Stand über dem Boden → prüfen", INA, [dict(p(), masterPl=-2000, mt5Baseline={"hedge": {"grund": "level_sl", "sl_art": "liquidation", "liq_art": "daily_loss"}, "final": {}})]),
    ("alter Trade (vor der Lesung, > 24 h) → Balance-Regel", dict(INA, tvBalance=149000, tvBalanceAt="2026-11-01T10:00:00Z"), [dict(p(), startedAt="2026-10-20T10:00:00Z", endedAt="2026-10-20T11:00:00Z")]),
]
def eigen(i, acc, plaene):   # je Fall ein eigenes Konto: kontoWegFolge läuft je Konto nur einmal
    kid = f"k{i}"
    return dict(acc, id=kid), [dict(x, masterAccountId=kid) for x in plaene]
js = STUBS + code + "\n(async () => { const ergebnisse = [];\n" + "".join(lauf(*eigen(i, a, pl)) for i, (_n, a, pl) in enumerate(faelle)) + "print(JSON.stringify(ergebnisse)); })().catch(e => print('FEHLER ' + e));"
js += """
const E = window._kontoWegLetztesEnde;
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run([JSC, d.name], capture_output=True, text=True, timeout=60)
os.unlink(d.name)
try:
    erg = json.loads(r.stdout.strip().splitlines()[-1])
except Exception:
    print(r.stdout[-500:], r.stderr[-500:]); erg = [[]] * len(faelle)
for (name, _a, _p), log in zip(faelle, erg):
    print("   ", name, log)
tp, sl, hand, alt, tppl, fund, sl_hoch, sl_boden, hedge_liq, hedge_dl, alt_trade = erg
check(any(x.startswith('konto:') and '"ziel_erreicht_at"' in x and '159040' in x for x in tp) and not any(x.startswith('archiv') for x in tp) and 'plan:bestanden' not in tp,
      "TP + Konto weg: Ziel markiert (157.051 + TP 1.989 = 159.040), nicht archiviert")
check('archiv:blown' in sl, "Liquidation (demo_liq) + Konto weg: als geblowt archiviert")
check(not any(x.startswith('archiv') for x in sl_hoch) and any('"auto_planer":false' in x for x in sl_hoch), "SL über dem Boden: kein Blow, prüfen (Stopp S9)")
check('archiv:blown' in sl_boden, "SL mit Stand am Boden: geblowt")
check('archiv:blown' in hedge_liq, "Hedge-SL am Liq-Level: geblowt")
check(not any(x.startswith('archiv') for x in hedge_dl) and any('"auto_planer":false' in x for x in hedge_dl), "Hedge-SL am Daily-Loss-Level: SL-Zweig, über dem Boden kein Blow (prüfen)")
check(not any('"ziel_erreicht_at"' in x for x in alt_trade) and not any(x.startswith('archiv') for x in alt_trade), "alter TP-Trade vor der letzten Lesung zählt nicht: Balance-Regel (149.000 unter Start, über dem Boden → prüfen)")
check(not any(x.startswith('archiv') for x in hand) and any('"auto_planer":false' in x for x in hand), "Hand-Schluss + Konto weg: nicht archiviert, Auto-Planer aus (prüfen)")
check('archiv:blown' in alt, "ohne bekanntes Ende gilt die Balance-Regel weiter (nahe Liq → geblowt)")
check(any('"ziel_erreicht_at"' in x for x in tppl) and not any(x.startswith('archiv') for x in tppl), "Ende aus P&L am TP erkannt")
check(not any(x.startswith('archiv') for x in fund) and not any('"ziel_erreicht_at"' in x for x in fund), "Funded am TP: prüfen, kein Ziel, kein Archiv")

# Abhaken „bestanden“ → Review, kein Archiv-Eintrag (app.py)
m = re.search(r"^def wd_erl_review_upd\(.*?(?=^\S)", app, re.S | re.M)
ns = {"_wd_num": lambda v: float(v) if v not in (None, "") else None}
exec(m.group(0), ns)
f, u = ns["wd_erl_review_upd"]("k1", {"mt5_baseline": {"tv": {"balance_start": 157051}, "final": {}}}, 1989, "2026-11-02T12:34:00Z")
check(f == {"id": "eq.k1", "ziel_erreicht_at": "is.null"} and u == {"ziel_erreicht_at": "2026-11-02T12:34:00Z", "ziel_erreicht_bal": 159040.0}, f"Abhaken bestanden: Ziel nur setzen, wenn leer, Balance 159.040 ({u})")
f2, u2 = ns["wd_erl_review_upd"]("k1", {"mt5_baseline": {"final": {"balance_end": 159008.02}}}, 1989, "x")
check(u2["ziel_erreicht_bal"] == 159008.02, "gelesene Endbalance geht vor")
check('f_arch = pool.submit(_archivieren) if konto_status == "blown" else None' in app and 'f_rev = pool.submit(_review) if konto_status == "passed" else None' in app,
      "Erledigt-Route: bestanden → Review, nur geblowt archiviert")

print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
