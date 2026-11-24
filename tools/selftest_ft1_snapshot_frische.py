#!/usr/bin/env python3
"""Selbsttest FT1 (Master 24.11.2026, Befund PW1 Marc FundedNext …7821): der Flotten-Takt des PC-Tabs schrieb eingefrorene Echo-Stände mit frischem
tv_balance_at ans Konto. Geprüft: (1) panel.py snapshot() liefert je Instanz snap_alter_s = Alter der Snapshot-Datei des Lese-EAs (None ohne Datei);
(2) prophos.html mt5InstBalanceFrisch nimmt eine Copier-/Lese-Instanz nur, wenn die Datei ≤ 15 s alt ist (alte Panels ohne Feld wie bisher) — damit
schreiben weder Flotten-Takt (mt5BalanceAusInstanzen) noch „↻ Balance lesen“ (mt5KontoBalanceJetzt) einen eingefrorenen Stand als frisch.
Ohne Netz, temporäres Verzeichnis. Aufruf: python3 tools/selftest_ft1_snapshot_frische.py"""
import json
import os
import subprocess
import sys
import tempfile
import time

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


import panel as P  # noqa: E402

print("1) panel.py snapshot(): snap_alter_s je Instanz")
tmp = tempfile.mkdtemp(prefix="ft1-")
for name, snapf in (("a", "snap_a.csv"), ("b", "snap_b.csv"), ("c", "fehlt.csv")):
    with open(os.path.join(tmp, f"config-{name}.json"), "w") as f:
        json.dump({"snapshot_file": snapf, "common_files_dir": tmp, "magic": 770001 + ord(name), "master_expected_login": 1}, f)
for snapf, alter in (("snap_a.csv", 2), ("snap_b.csv", 3 * 86400)):
    p = os.path.join(tmp, snapf)
    with open(p, "w") as f:
        f.write("PROPHOS1;1;x;1;srv;0;0;104915.95;104915.95;USD\nEND;1;0\n")
    os.utime(p, (time.time() - alter, time.time() - alter))
P.HERE = tmp
erg = {i["name"]: i for i in P.snapshot()["instances"]}
check(erg["a"].get("snap_alter_s") is not None and erg["a"]["snap_alter_s"] <= 5, f"frische Datei → Alter ~2 s ({erg['a'].get('snap_alter_s')})")
check(erg["b"].get("snap_alter_s", 0) >= 3 * 86400 - 5, f"Datei von vor 3 Tagen → Alter ~259.200 s ({erg['b'].get('snap_alter_s')})")
check(erg["c"].get("snap_alter_s") is None, "keine Datei → None")

print("2) prophos.html mt5InstBalanceFrisch")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
i = html.index("  function mt5InstBalanceFrisch(inst){")
fn = html[i:html.index("\n  }\n", i) + 4]
k = html.index("  const MT5_SNAP_FRISCH_S = ")
konst = html[k:html.index("\n", k)]
FAELLE = {
    "frisch": {"alive": True, "snap_alter_s": 1.2, "status": {"master_balance": 100000.0, "master_login": "14367821"}},
    "eingefroren": {"alive": True, "snap_alter_s": 259200, "status": {"master_balance": 104915.95, "master_login": "14367821"}},
    "grenze": {"alive": True, "snap_alter_s": 15, "status": {"master_balance": 100000.0, "master_login": "1"}},
    "altes_panel": {"alive": True, "status": {"master_balance": 100000.0, "master_login": "1"}},
    "note": {"alive": True, "snap_alter_s": 1, "status": {"master_balance": 100000.0, "master_login": "1", "note": "Snapshot eingefroren"}},
    "lesen_alt": {"lesen": True, "snap_alter_s": 40, "status": {"master_balance": 100000.0, "master_login": "1"}},
}
js = konst + "\n" + fn + "\nconst F = " + json.dumps(FAELLE) + ";\nconst R = {}; for(const k in F) R[k] = mt5InstBalanceFrisch(F[k]);\nprint(JSON.stringify(R));\n"
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as d:
    d.write(js)
r = subprocess.run([JSC, d.name], capture_output=True, text=True, timeout=60)
os.unlink(d.name)
check(r.returncode == 0, f"jsc läuft ({r.stderr[:200]})")
R = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}
check((R.get("frisch") or {}).get("balance") == 100000.0, "frische Datei (1,2 s) → Balance wird geschrieben")
check(R.get("eingefroren") is None, "Datei 3 Tage alt, Copier gerade gestartet (noch ohne note) → NICHT geschrieben (Fall …7821)")
check((R.get("grenze") or {}).get("balance") == 100000.0, "genau 15 s → noch frisch (wie LESE_FRISCH_S)")
check((R.get("altes_panel") or {}).get("balance") == 100000.0, "altes Panel ohne Feld → wie bisher")
check(R.get("note") is None and R.get("lesen_alt") is None, "note gesetzt / Lese-Instanz mit 40 s alter Datei → nicht geschrieben")
check("mt5InstBalanceFrisch(inst)" in html[html.index("  function mt5BalanceAusInstanzen("):html.index("  function mt5BalanceAusInstanzen(") + 400]
      and "let f = mt5InstBalanceFrisch(inst)" in html, "Flotten-Takt und „↻ Balance lesen“ gehen beide über mt5InstBalanceFrisch")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ alle Prüfungen grün")
