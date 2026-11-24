#!/usr/bin/env python3
"""Selbsttest VM1 (Finn 25.11.2026: „Mach dieses vorgemerkt weg, das nervt immer.“) — Radar ohne sichtbares „vorgemerkt“:
  · kein Chip „n vorgemerkt ×“, kein Toast „Vorgemerkt …“, kein „· n vorgemerkt“ in Sammel-Zeile/-Toast (Sammel zählt still Vorgemerkte als abgehakt)
  · vorgemerkt bleibt still weg bis zur Lesung (keine 6-h-Rückkehr), nach 24 h ohne Lesung EINE ruhige Zeile „Überprüfen · ohne Lesung“ in Erledigt
  · Fall Simon · FundedNext 100k …9853 · HT (Plan 0a1e29c4, 23.11., Echo mit Hedge, Fusion-Close nie gebucht): steht in der ruhigen Zeile, nicht in „Abhaken“
JS-Teil echt in JavaScriptCore (wdlOhneLesungHtml). Verhalten von wdlVorgemerktVersteckt/wdlOhneLesungLang: tools/selftest_abhaken_ein_klick.py.
Aufruf:  python3 tools/selftest_vm1_vorgemerkt_still.py"""
import json
import os
import subprocess
import sys
import tempfile

HTML = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


check("Vorgemerkt — wird abgehakt" not in HTML, "kein Toast „Vorgemerkt …“")
check("vorgemerkt ×</button>" not in HTML and "vorgemerktN" not in HTML, "kein Chip „n vorgemerkt ×“ / Zähler")
check("e.vm ?" not in HTML and "erg.vm ?" not in HTML and "erg.vm++" not in HTML, "Sammel-Zeile und -Toast ohne „vorgemerkt“, Vorgemerkte zählen als abgehakt")
check("if(t.vorgemerkt) erg.ok++;" in HTML, "Sammel: still vorgemerkt = abgehakt")
check("const WDL_VORMERK_FRIST_MS = 24 * 3600000" in HTML and "6 * 3600000" not in HTML[HTML.index("const WDL_VORMERK_GRUENDE"):HTML.index("function wdlAbhakenSperre(")],
      "Frist 24 h (keine 6-h-Rückkehr)")
r = HTML[HTML.index("    const ohneLesungLang = modellTrades"):HTML.index("    const num = v =>", HTML.index("    const ohneLesungLang = modellTrades"))]
check("!wdlVorgemerktVersteckt(t) && !wdlOhneLesungLang(t)" in r, "Render: Vorgemerkte und Lange-ohne-Lesung nicht in den Abhaken-Gruppen")
check("wdlOhneLesungHtml(ohneLesungLang)" in HTML, "Render: ruhige Zeile unten in Erledigt")
check("const ol = ev.target.closest('[data-wdl-ol]')" in HTML and "einKlick: false" in HTML[HTML.index("const ol = ev.target.closest('[data-wdl-ol]')"):][:500],
      "Klick in der ruhigen Zeile → Popup (von Hand nachtragen), kein Vormerken")

# ── JS echt: wdlOhneLesungHtml mit dem Fall …9853 ──
i = HTML.index("  function wdlOhneLesungHtml(")
fn = HTML[i:HTML.index("  function wdlVorgemerktTick(", i)]
SIMON = {"id": "0a1e29c4", "status": "review", "route": "mt5", "person": "Simon", "konto": {"firma": "FundedNext 100k", "kontonr_ende": "9853"},
         "ended_at": "2026-11-23T08:15:28Z", "pl_balance": -69.27, "slave_pl": None, "hedge_eur": None}
js = ("const escapeHtml = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');\n"
      "const wdlTid = t => t.id; const wdlEinKlickGrund = t => 'Hedge-P&L fehlt';\n" + fn +
      "\nprint(JSON.stringify([wdlOhneLesungHtml([]), wdlOhneLesungHtml([" + json.dumps(SIMON) + "])]));\n")
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
p = subprocess.run([JSC, d.name], capture_output=True, text=True)
os.unlink(d.name)
try:
    leer, zeile = json.loads(p.stdout.strip().splitlines()[-1])
except Exception:
    leer, zeile = None, ""
    print(p.stdout, p.stderr)
check(leer == "", "keine Fälle → keine Zeile")
check("Überprüfen" in zeile and "ohne Lesung seit über 24 h" in zeile and "Simon · FundedNext 100k …9853" in zeile
      and "Hedge-P&amp;L fehlt" in zeile and "23.11." in zeile and 'data-wdl-ol="0a1e29c4"' in zeile and "vorgemerkt" not in zeile,
      "Simon …9853: eine ruhige Zeile mit Grund und Datum, anklickbar, ohne „vorgemerkt“")

print(f"\n{'ALLES GRÜN' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
sys.exit(1 if FEHLER else 0)
