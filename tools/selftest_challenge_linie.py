#!/usr/bin/env python3
"""Selbsttest LINIE VON HEUTE (prophos.html apgCvHeutePunkte + app.py ap_verlauf_zeilen.ende, 30.10.2026, Auftrag C2 — Finn: „nur eine kleine Linie im Verlauf von heute").
Aufruf:  python3 tools/selftest_challenge_linie.py   (ohne Netz; läuft echt in JavaScriptCore)."""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
app = open(os.path.join(HIER, "..", "app.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


fn = html[html.index("const apgCvCent ="):html.index("function apgCvKacheln(")]
JETZT = "2026-10-30T14:00:00Z"   # 18:00 Dubai
FAELLE = {"gemischt": {"fh": 100.1, "schritte": [{"ende": "2026-10-30T10:00:00Z", "eur": -50}, {"ende": "2026-10-30T06:00:00Z", "eur": 150.1}]},
          "ohne Hypo": {"fh": 0, "schritte": []},
          "ohne Endzeit": {"fh": 30, "schritte": [{"eur": 30}]},
          "Float": {"fh": 0.1 + 0.2, "schritte": [{"ende": "2026-10-30T06:00:00Z", "eur": 0.1}, {"ende": "2026-10-30T07:00:00Z", "eur": 0.2}]}}
js = fn + f"\nconst F = {json.dumps(FAELLE)}, J = Date.parse({json.dumps(JETZT)}), A = {{}}; for(const k in F) A[k] = apgCvHeutePunkte(F[k], J); print(JSON.stringify(A));"
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d.name], capture_output=True, text=True)
os.unlink(d.name)
check(r.returncode == 0, f"jsc läuft ({r.stderr[:200]})")
E = json.loads(r.stdout.strip().splitlines()[-1])
g = E["gemischt"]
check(g[0] == {"x": 0, "y": 0}, "startet 00:00 bei 0 €")
check([p["x"] for p in g] == [0, 10, 14, 18] and [p["y"] for p in g] == [0, 150.1, 100.1, 100.1], f"nach Endzeit sortiert, Dubai-Stunden, Schritt je Trade ({g})")
check([p["y"] for p in E["ohne Hypo"]] == [0, 0], "ohne Hypo-Wert: flach auf 0")
check(E["ohne Endzeit"][-1] == {"x": 18, "y": 30}, "ohne Endzeit: zählt als jetzt")
check(E["Float"][-1]["y"] == 0.3 == E["Float"][-2]["y"], "Endpunkt auf Cent gleich der Heute-Kachel")
check('"ende": z.get("ende")' in app[app.index("def ap_verlauf_zeilen("):app.index("def ap_verlauf_gemerkt(")], "Backend liefert die Endzeit")
for tot in ("apgCvSummen", "apgCvTagHtml", "apg-cv-tip", "apg-cv-tag", "_apgCv.tag", "Tag im Plus"):
    check(tot not in html, f"entfernt: {tot}")
check("Am nächsten am Pass" in html and "apgCvKacheln(c)" in html, "Kacheln und „Am nächsten am Pass“ bleiben")
print("\n" + (f"✗ {len(FEHLER)} Fehler" if FEHLER else "✓ alles grün"))
sys.exit(1 if FEHLER else 0)
