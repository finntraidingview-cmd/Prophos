#!/usr/bin/env python3
"""Selbsttest HF1b — nach „✓ Bestätigen“ im Challenge-Planer zeigt eine Hedge-Karte lokal nur dann „freigegeben“, wenn die Antwort der Route die Freigabe
gemeldet hat (app.py _ap_eingriff → hedge_frei). Anlass Finn 05.11.2026: Emin „✓ alle 4 / alle 2“ — Karten erst „bereit“, nach Neuladen „⏳ wartet auf
Hedge-Freigabe →“ (bei Emins Gruppe gibt das ✓ bewusst nichts frei, MO1). Echte Funktion apHedgeFreiLokal über JavaScriptCore + Verdrahtung.
Aufruf: python3 tools/selftest_hedge_frei_lokal.py"""
import json
import os
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
APP = open(os.path.join(W, "app.py"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


i = HTML.index("  function apHedgeFreiLokal(")
fn = HTML[i:HTML.index("  window._apHedgeFreiLokal", i)]
F = [[None, 4], [0, 4], [4, 4], [2, 4], [6, 4], [0, 0], [3, 0], ["2", "2"]]
js = fn + "\nprint(JSON.stringify(%s.map(f => apHedgeFreiLokal(f[0], f[1]))))\n" % json.dumps(F)
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run([JSC, d.name], capture_output=True, text=True, timeout=60)
os.unlink(d.name)
check(r.returncode == 0, "jsc läuft " + (r.stderr or "")[:120])
e = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else []
check(e == [True, False, True, False, True, False, False, True],
      "apHedgeFreiLokal: altes Backend → wie bisher frei; 0 gemeldet (Emin/Verwalter) → wartet; alle gemeldet → frei; Teilmenge → wartet")
check("if(aus) aus.hedgeFrei = d && d.hedge_frei !== undefined && d.hedge_frei !== null ? (Number(d.hedge_frei) || 0) : null" in HTML,
      "tplEingriff reicht hedge_frei der Antwort weiter")
check("_apIds.warteLokal.set(id, { z, at: jetzt, frei: hedgeFreiLokal })" in HTML and "const hedgeFreiLokal = apHedgeFreiLokal(aus.hedgeFrei, nHedge)" in HTML,
      "apIdsOk merkt das Ergebnis je Plan im lokalen „Wartet auf Start“")
check("hedge_frei: e.frei !== false || e.z.hedge_frei === true" in HTML and "{ hedge_frei: true }) : e.z })" not in HTML,
      "Anzeige setzt hedge_frei nur noch mit gemeldeter Freigabe (oder schon freigegebenem Plan)")
check('"hedge_frei": frei})' in APP, "app.py liefert hedge_frei in der Bestätigen-Antwort (unverändert)")
print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
