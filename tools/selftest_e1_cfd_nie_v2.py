"""Selbsttest E1 (03.11.2026): CFD-Challenges nie als Echo V2 / ohne Fusion-Hedge.
python3 tools/selftest_e1_cfd_nie_v2.py → „alle OK" oder Exit 1. Rein lesend (kein DB-Zugriff)."""
import ast, os, re, subprocess, sys, tempfile
from datetime import datetime, timezone

H = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
src = open(os.path.join(H, "app.py"), encoding="utf-8").read()
html = open(os.path.join(H, "prophos.html"), encoding="utf-8").read()
sql = open(os.path.join(H, "sql", "2026-11-03_cfd_challenge_nie_ohne_hedge.sql"), encoding="utf-8").read()
t = ast.parse(src)
fehler = 0


def ok(b, text):
    global fehler
    print(("OK   " if b else "FEHL ") + text)
    fehler += 0 if b else 1


def fn(name):
    n = [x for x in t.body if isinstance(x, ast.FunctionDef) and x.name == name][0]
    return compile(ast.Module([n], []), name, "exec")


ns = {}
exec(fn("eh_fenster_oder"), ns)
von, bis = datetime(2026, 11, 3, 10, 7, tzinfo=timezone.utc), datetime(2026, 11, 3, 10, 57, tzinfo=timezone.utc)
ok(ns["eh_fenster_oder"](von, bis) == "(start_um.is.null,and(start_um.gte.2026-11-03T10:07:00+00:00,start_um.lte.2026-11-03T10:57:00+00:00))",
   "eh-Fenster: im Fenster ODER ohne Startzeit")
ok(src.count('"or": eh_fenster_oder(von, bis)') == 2, "eh_tick und eh_schnell_tick nutzen das Fenster mit Handstart")
ok('"or": f"(start_um.is.null,start_um.gte.' in fn_src if (fn_src := ast.get_source_segment(src, [x for x in t.body if isinstance(x, ast.FunctionDef) and x.name == "ehv_tick"][0])) else False,
   "Vorschau auch für Pläne ohne Startzeit")
ok("oder_echo if feld == \"echo_hedge\" else oder" in src, "vorgemerkte Echo-Hedges zählen auch ohne Startzeit")
exec(fn("eh_ohne_text"), ns)
ok(all(ns["eh_ohne_text"](c, "x").startswith("startet nicht") for c in ("balance", "lesung", "groesse", "klein", "marge", "grenze", "kein_konto")),
   "⚪-Text: kein Code startet mehr ohne Hedge")

# SQL-Riegel
ok("coalesce(new.route, '') not in ('mt5v2', 'mt5')" in sql and "kt not in ('challenge', 'phase1', 'phase2')" in sql, "Riegel: alle CFD-Challenges auf mt5v2/mt5")
ok("prophos_ht_echo_hedge_an" not in sql.split("$$")[1] and "new.auto_plan" not in sql.split("$$")[1], "Riegel: unabhängig von Schalter und Auto-Plan")
ok("new.slave_account_id is not null and coalesce(new.multiplier, 0) > 0" in sql, "Riegel: Echo nur mit Fusion-Slave und Multiplikator")
ok("coalesce(gefunden, false) and kt not in" in sql, "Riegel: Konto nicht lesbar → halten (fail-closed)")
ok("coalesce(new.start_claim_art, 'start') <> 'start'" in sql, "Verbrauchs-Claims laufen durch")

# PC-Tab
m = re.search(r"  const ECHO_V2_GESPERRT_TYPEN = .*?\n  window\._echoV2Gesperrt", html, re.S)
ok(bool(m), "echoV2Gesperrt im PC-Tab")
ok("const v2Sperre = echoV2Gesperrt(plan," in html and "fail('v2hedge', escapeHtml(v2Sperre" in html, "tpPreflightMt5V2 sperrt (Schritt 2a)")
ok("_tpRoute === 'mt5v2' && ['challenge', 'phase1', 'phase2'].includes(kt)" in html, "Plan-Popup: kein neues Echo V2 für Challenges")
jsc = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
if m and os.path.exists(jsc):
    js = m.group(0).replace("\n  window._echoV2Gesperrt", "\n") + r"""
const F = [
 ['Julian FTMO phase1 Auto', {route:'mt5v2', autoPlan:true}, {type:'phase1'}, true],
 ['Emin Tradeify CFD phase1', {route:'mt5v2'}, {type:'phase1'}, true],
 ['phase2 Mini', {route:'mt5v2', mt5Baseline:{tage_mini:{}}}, {type:'phase2'}, true],
 ['challenge Hand-Plan', {route:'mt5v2', autoPlan:false}, {type:'challenge'}, true],
 ['Konto fehlt, konto_typ phase1', {route:'mt5v2', kontoTyp:'phase1'}, null, true],
 ['Konto + Typ fehlen (fail-closed)', {route:'mt5v2'}, null, true],
 ['funded_cfd Echo V2', {route:'mt5v2'}, {type:'funded_cfd'}, false],
 ['phase1 Echo mt5', {route:'mt5'}, {type:'phase1'}, false],
]
let n = 0
for(const [t, p, a, soll] of F){ const ist = !!echoV2Gesperrt(p, a); print((ist === soll ? 'OK   ' : 'FEHL ') + 'JS: ' + t); if(ist === soll) n++ }
print('JSERG ' + (n === F.length ? 'ok' : 'rot'))
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js)
    out = subprocess.run([jsc, f.name], capture_output=True, text=True).stdout
    print(out.replace("JSERG ok\n", "").replace("JSERG rot\n", ""), end="")
    ok("JSERG ok" in out, "echoV2Gesperrt: 8 Fälle")
print("alle OK" if not fehler else f"{fehler} FEHLER")
sys.exit(1 if fehler else 0)
