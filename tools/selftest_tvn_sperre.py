#!/usr/bin/env python3
"""Selbsttest ROLLOUT SCHNELLER (02.11.2026): tvnPlanSperre und tvnBlickTsx. Ohne Netz, jsc. Aufruf: python3 tools/selftest_tvn_sperre.py"""
import json
import os
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(name):
    i = HTML.index(f"function {name}(")
    j = HTML.index("{", HTML.index(")", i))
    t = 0
    for k in range(j, len(HTML)):
        t += {"{": 1, "}": -1}.get(HTML[k], 0)
        if t == 0:
            return HTML[i:k + 1]
    raise ValueError(name)


JS = "\n".join(["const TVN_START_ABSTAND_MS = 5 * 60000, TVN_UEBERFAELLIG_MS = 65 * 60000", "let tradePlans = []", fn("tvnPlanSperre"), fn("tvnBlickTsx"), r"""
const J = 1e12, iso = m => new Date(J + m * 60000).toISOString(), P = (route, m) => ({ status: 'planned', route, startUm: iso(m) })
const S = (l, a) => tvnPlanSperre(l, J, a)
const R = st => ({ ok: true, alter_s: 1, script: '0.3.2', stand: st })
const G = (st, plaene) => { tradePlans = plaene || []; return tvnBlickTsx(R(st)).posGrund }
print(JSON.stringify({
  echo_offen: [S([{ status: 'open', route: 'mt5' }], true), S([{ status: 'open', route: 'mt5v2' }], false)],
  tv_offen: [S([{ status: 'open', route: 'tvv2' }], false), S([{ status: 'open', route: 'tsv2' }], true), S([{ status: 'open' }], false)],
  start_tv: [S([P('tvv2', 4)], false), S([P('tvv2', 4)], true), S([P('tvv2', 6)], true)],
  start_mt5: [S([P('mt5', 4)], false), S([P('mt5', 4)], true), S([P('mt5v2', 4)], false), S([P('mt5v2', 6)], true)],
  ueberfaellig: [S([P('tvv2', -60)], false), S([P('tvv2', -70)], false)],
  flach_ohne_trade: G({ flach: false, positionen: [] }), aus_ohne_trade: G({ ausgeloggt: true }), null_ohne_trade: G({ flach: null }),
  pos_ohne_trade: G({ flach: false, positionen: [{ symbol: 'NQ' }] }),
  flach_mit_trade: G({ flach: false, positionen: [] }, [{ status: 'open', route: 'tsv2' }]), aus_mit_trade: G({ ausgeloggt: true }, [{ status: 'open', route: 'tsv2' }]),
  flach_beweis_mit_trade: G({ flach: true, positionen: [] }, [{ status: 'open', route: 'tsv2' }]), mt5_trade: G({ flach: false }, [{ status: 'open', route: 'mt5' }]),
}))
"""])
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
    t.write(JS)
r = subprocess.run([JSC, t.name], capture_output=True, text=True, timeout=30)
os.unlink(t.name)
if r.returncode or not r.stdout.strip():
    print(r.stdout, r.stderr)
    sys.exit(1)
e = json.loads(r.stdout.strip().splitlines()[-1])
check(e["echo_offen"] == ["", ""], "offene mt5/mt5v2 sperren nicht")
check(e["tv_offen"] == ["offener Plan"] * 3, "offene tvv2, tsv2, ohne Route sperren")
check(e["start_tv"] == ["Start in < 5 min", "Start in < 5 min", ""], "Start tvv2: unter 5 min sperrt beide Wege, 6 min frei")
check(e["start_mt5"] == ["", "Start in < 5 min", "", ""], "Start mt5: sperrt nur Tampermonkey")
check(e["ueberfaellig"][0] != "" and e["ueberfaellig"][1] == "", "Überfällig bleibt bei 65 min")
check(e["flach_ohne_trade"] == "" and e["aus_ohne_trade"] == "" and e["null_ohne_trade"] == "", "ohne TopstepX-Trade: flach unbewiesen oder ausgeloggt sperrt nicht")
check(bool(e["pos_ohne_trade"]), "gelesene Position sperrt immer")
check(bool(e["flach_mit_trade"]) and bool(e["aus_mit_trade"]) and e["flach_beweis_mit_trade"] == "" and e["mt5_trade"] == "", "mit tsv2-Trade: nur flach bewiesen ist frei; Echo zählt nicht")
check("tvnRuhe(b, true)" in HTML and "dbFrei(true)" in HTML and "dbFrei(false)" in HTML and "&weg=neuladen" in HTML, "Tampermonkey alle Routen, Neuladen nur Nicht-MT5, auch bei blindem Reader")
print("\nTVN-SPERRE: alles grün" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
