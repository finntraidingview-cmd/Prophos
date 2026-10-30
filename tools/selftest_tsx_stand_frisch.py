#!/usr/bin/env python3
"""Selbsttest tsxStandFrisch (30.10.2026, Prüfer S2 zu Auge 0.3.2): ein spät ankommendes altes „flach" hat im Panel ein frisches alter_s, die Messung selbst (stand.ts) ist aber alt → nicht frisch,
der Schnell-Wächter hedgeTsxSchnellTick schließt darauf nicht. Aufruf:  python3 tools/selftest_tsx_stand_frisch.py"""
import json
import os
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
i = HTML.index("  function tsxStandFrisch(")
code = HTML[i:HTML.index("\n  }\n", i) + 4]
lauf = """const J = 1000000, F = tsxStandFrisch
print(JSON.stringify({ frisch: F(0.1, { ts: J - 200 }, J), grenze: F(1.0, { ts: J - 1000 }, J), spaet: F(0.05, { ts: J - 3200 }, J), alt: F(1.5, { ts: J - 100 }, J), ohne_ts: F(0.1, {}, J), ohne_alter: F(null, { ts: J }, J), ohne_stand: F(0.1, null, J) }))
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(code + "\n" + lauf)
    pfad = f.name
r = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=60)
os.unlink(pfad)
e = json.loads(r.stdout.strip().splitlines()[-1])
fehler = 0
for name, ok in (("frisch: Ankunft und Messung jung", e["frisch"] is True), ("Grenze 1 s gilt noch", e["grenze"] is True), ("spät angekommen, Messung 3,2 s alt → nicht frisch", e["spaet"] is False),
                 ("alter_s > 1 → nicht frisch", e["alt"] is False), ("ohne ts → nicht frisch", e["ohne_ts"] is False), ("ohne alter_s → nicht frisch", e["ohne_alter"] is False), ("ohne Stand → nicht frisch", e["ohne_stand"] is False),
                 ("Schnell-Wächter fragt tsxStandFrisch", "if(!st || !tsxStandFrisch(r.alter_s, st, Date.now())){" in HTML)):
    print(("ok   " if ok else "FEHL ") + name)
    fehler += 0 if ok else 1
print("\nALLES OK" if not fehler else f"\n{fehler} FEHLER")
sys.exit(1 if fehler else 0)
