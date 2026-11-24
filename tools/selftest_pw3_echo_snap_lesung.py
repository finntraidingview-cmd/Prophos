#!/usr/bin/env python3
"""Selbsttest PW3 (Master 24.11.2026, Fall Marc FundedNext 100k On Demand …7821): mt5_live.updated_at ist der Push des PC-Tabs (alle 30 s auch im
Standby), nicht das Alter des Echo-Snapshots — ein eingefrorener Echo-Stand (Terminal zu, Payout dazwischen abgebucht) schlug in acc_balance_wahl jede
jüngere Lesung (tv_balance). Geprüft: (1) acc_balance_wahl rein — mit Snapshot-Datum (4. Element) gewinnt eine NEUERE Lesung, sonst wie bisher (Echo vor TV,
3-Tupel/ohne snap_at unverändert); (2) die drei mt5_live-Lader (_ap_balance_karten, Admin, Prop-Baum) lesen status->>snap_at; (3) prophos.html pusht
snap_at aus snap_alter_s (FT1-Panel) und zählt es nicht als Änderung (fp). Ohne Netz. Aufruf: python3 tools/selftest_pw3_echo_snap_lesung.py"""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


W = app.acc_balance_wahl
K = {"external_id": "14367821", "tv_balance": 100000, "tv_balance_at": "2026-11-24T17:29:48.609+00:00"}
PUSH = "2026-11-24 17:40:00.000+00"   # mt5_live.updated_at: Lebenszeichen, immer frisch

print("1) acc_balance_wahl")
r = W(K, {"14367821": ("104915.95", "USD", PUSH, "2026-11-18T14:40:02.000Z")}, {})
check(r[0] == 100000 and r[2] == "TV" and r[3] == K["tv_balance_at"],
      f"Fall …7821: Echo eingefroren seit 18.11. (Snapshot), Lesung 24.11. → 100.000 aus der Lesung ({r})")
r = W(K, {"14367821": ("100012.5", "USD", PUSH, "2026-11-24T17:39:55.000Z")}, {})
check(r[0] == 100012.5 and r[2] == "Echo" and r[3] == PUSH, f"Snapshot jünger als die Lesung → Echo wie bisher ({r})")
r = W(K, {"14367821": ("104915.95", "USD", PUSH)}, {})
check(r[0] == 104915.95 and r[2] == "Echo", "3-Tupel (alter Lader) → Echo wie bisher")
r = W(K, {"14367821": ("104915.95", "USD", PUSH, None)}, {})
check(r[0] == 104915.95 and r[2] == "Echo", "snap_at null (altes Panel) → Echo wie bisher")
r = W(dict(K, tv_balance=None, tv_balance_at=None), {"14367821": ("104915.95", "USD", PUSH, "2026-11-18T14:40:02Z")}, {})
check(r[0] == 104915.95 and r[2] == "Echo", "ohne Lesung → Echo (auch eingefroren besser als nichts)")
r = W(dict(K, tv_balance=0), {"14367821": ("104915.95", "USD", PUSH, "2026-11-18T14:40:02Z")}, {})
check(r[0] == 104915.95 and r[2] == "Echo", "tv_balance 0 (= unbekannt) → Echo")
r = W(dict(K, tv_balance_at="2026-11-24 17:29:48.609+00"), {"14367821": ("104915.95", "USD", PUSH, "2026-11-24T17:29:49Z")}, {})
check(r[2] == "Echo", "SQL-Format „ …+00“ gegen „…Z“: Snapshot 0,4 s jünger → Echo (Zeit richtig verglichen, kein String-Vergleich)")
r = W(dict(K, tv_balance_at="2026-11-24 17:29:48.609+00"), {"14367821": ("104915.95", "USD", PUSH, "2026-11-24T17:29:48Z")}, {})
check(r[2] == "TV", "… Snapshot 0,6 s älter → Lesung")
r = W(K, {"14367821": ("104915.95", "USD", PUSH, "kaputt")}, {})
check(r[2] == "Echo", "snap_at nicht lesbar → wie bisher")
r = W(dict(K, meta_api_balance=100500), {"14367821": ("104915.95", "USD", PUSH, "2026-11-18T14:40:02Z")}, {})
check(r[2] == "MT5", "MetaApi bleibt vor allem (Rangfolge unverändert)")
r = W(K, {"14367821": ("104915.95", "USD", PUSH, "2026-11-18T14:40:02Z")}, {"14367821": (100200, "USD", "2026-11-24T18:00:00+00:00")})
check(r[2] == "Duplikum" and r[0] == 100200, "Echo übersprungen → TV/Duplikum wie bisher: der jüngere gewinnt")

print("2) Lader")
src = open(os.path.join(WURZEL, "app" + ".py"), encoding="utf-8").read()
check(src.count('snap:status->>snap_at"}') == 3 and src.count('at, row.get("snap"))') == 3,
      "alle drei mt5_live-Lader lesen snap_at und geben es als 4. Element mit")

print("3) prophos.html")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
i = html.index("            snap_at: (inst.snap_alter_s != null")
zeile = html[i:html.index("\n", i)].strip().rstrip(",")
ausdr = zeile[len("snap_at: "):]
js = ("const T0 = Date.now(); const R = {};\n"
      "for(const [k, inst] of Object.entries({frisch:{snap_alter_s:2}, alt:{snap_alter_s:259200}, ohne:{}, leer:{snap_alter_s:null}, kaputt:{snap_alter_s:'x'}})){\n"
      f"  const v = {ausdr}; R[k] = v == null ? null : (T0 - Date.parse(v)) / 1000 }}\nprint(JSON.stringify(R));\n")
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as d:
    d.write(js)
p = subprocess.run([JSC, d.name], capture_output=True, text=True, timeout=60)
os.unlink(d.name)
R = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else {}
check(p.returncode == 0 and 1 <= R.get("frisch", -1) <= 4 and 259199 <= R.get("alt", 0) <= 259203 and R.get("ohne") is None
      and R.get("leer") is None and R.get("kaputt") is None, f"snap_at = jetzt − snap_alter_s, ohne/kaputt → null ({R} {p.stderr[:120]})")
check("{ kurs_bruecke: null, snap_at: null }" in html, "snap_at zählt nicht als Änderung (kein Push alle 5 s bei offenem Terminal)")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ alle Prüfungen grün")
