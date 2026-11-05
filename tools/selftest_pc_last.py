#!/usr/bin/env python3
"""Selbsttest SW1 (05.11.2026): Last des PCs messen (panel.py, LAST DES PCs MESSEN), Schließ-Wache ohne Dauer-Lesen der Status-Dateien (panel.py) und
positions.json gedrosselt (tv-reader/reader-server.py 0.9.11). Rein rechnend, ohne Windows und ohne Netz. Aufruf: python3 tools/selftest_pc_last.py"""
import json
import os
import random
import sys
import tempfile
import time
import types

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "mt5-copier", "panel.py"), encoding="utf-8").read()
RSRC = open(os.path.join(W, "tv-reader", "reader-server.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


# ── 1) Messung: Block zwischen _code_glatt und „Nur diese Felder“ (wie selftest_panel_lauf) ──
tmp = tempfile.mkdtemp()
open(os.path.join(tmp, "panel.py"), "wb").write(b"# p\n")
open(os.path.join(tmp, "provision.py"), "wb").write(b"# q\n")
ns = {"os": os, "time": time, "random": random, "json": json, "sys": sys, "HERE": tmp, "PORT": 8770, "__file__": os.path.join(tmp, "panel.py"),
      "provision": types.SimpleNamespace(__file__=os.path.join(tmp, "provision.py")),
      "read_json": lambda p, d=None: (json.load(open(p)) if os.path.exists(p) else d)}
i, j = SRC.index("def _code_glatt("), SRC.index("# Nur diese Felder darf das Panel schreiben.")
exec(SRC[i:j], ns)
A = ns["pc_last_auswerten"]
MB = 1048576
vorher = {10: ("chrome.exe", 0), 11: ("chrome.exe", 0), 20: ("python.exe", 1_000_000), 21: ("python.exe", 0), 30: ("msmpeng.exe", 0), 40: ("terminal64.exe", 5)}
jetzt = time.time()
proz = [
    {"pid": 10, "ppid": 1, "name": "chrome.exe", "cpu": 6e7, "ws": 500 * MB, "priv": 400 * MB, "start_s": jetzt - 3600},
    {"pid": 11, "ppid": 10, "name": "chrome.exe", "cpu": 3e7, "ws": 300 * MB, "priv": 200 * MB, "start_s": jetzt - 3600},
    {"pid": 20, "ppid": 99, "name": "python.exe", "cpu": 1_000_000 + 12e7, "ws": 80 * MB, "priv": 70 * MB, "start_s": jetzt - 2 * 86400},   # panel
    {"pid": 21, "ppid": 20, "name": "python.exe", "cpu": 6e6, "ws": 60 * MB, "priv": 50 * MB, "start_s": jetzt - 30},                      # Kind des Panels
    {"pid": 22, "ppid": 5, "name": "python.exe", "cpu": 1e5, "ws": 40 * MB, "priv": 30 * MB, "start_s": jetzt - 7200},                     # copier, neu
    {"pid": 30, "ppid": 4, "name": "MsMpEng.exe", "cpu": 24e7, "ws": None, "priv": None, "start_s": None},                                # geschützt: nur CPU
    {"pid": 40, "ppid": 1, "name": "terminal64.exe", "cpu": None, "ws": 9 * MB, "priv": 8 * MB, "start_s": None},                         # kein Zugriff auf Zeiten
    {"pid": 50, "ppid": 1, "name": "chrome.exe", "cpu": 9e9, "ws": 10 * MB, "priv": 10 * MB, "start_s": jetzt},                           # neu: kein Vorwert
    {"pid": "x", "name": "kaputt"},
]
namen, py, neu = A(proz, vorher, 60.0, 6, {22: "copier"}, 20)
g = {x["name"]: x for x in namen}
# Nenner 60 s × 1e7 × 6 Kerne = 3,6e9 → chrome (6e7+3e7)/3,6e9 = 2,5 %, panel 12e7 = 3,3 %, Defender 24e7 = 6,7 %
check(abs(g["chrome.exe"]["cpu_pct"] - 2.5) < 0.05 and g["chrome.exe"]["n"] == 3 and g["chrome.exe"]["priv_mb"] == 610,
      f"chrome: 3 Prozesse, CPU nur mit Vorwert (2,5 % des PCs), Speicher summiert ({g['chrome.exe']})")
check(abs(g["msmpeng.exe"]["cpu_pct"] - 6.7) < 0.05 and g["msmpeng.exe"]["priv_mb"] == 0, "Defender ohne Speicherzugriff: CPU zählt trotzdem")
check(g["terminal64.exe"]["cpu_pct"] is None and g["terminal64.exe"]["priv_mb"] == 8, "ohne Prozesszeiten: CPU unbekannt (None), nicht 0")
check(namen[0]["name"] == "msmpeng.exe", "Liste nach CPU sortiert, größter Fresser zuerst")
r = {x["pid"]: x for x in py}
check(r[20]["rolle"] == "panel" and r[21]["rolle"] == "panel-kind" and r[22]["rolle"] == "copier", "python-Rollen: panel / Kind des Panels (Order-Bot) / copier aus Status")
check(r[20]["alter_h"] == 48.0 and r[22]["cpu_pct"] is None and abs(r[20]["cpu_pct"] - 3.3) < 0.05, "python: Laufzeit in h, CPU nur mit Vorwert")
check(py[0]["pid"] == 20, "python-Liste nach CPU sortiert")
check(set(neu) == {10, 11, 20, 21, 22, 30, 50} and neu[30] == ("msmpeng.exe", 24e7), "Vorwerte für die nächste Runde: nur Prozesse mit lesbarer CPU-Zeit")
namen2, _, _ = A(proz, {10: ("anders.exe", 0)}, 60.0, 6, {}, 20)
check({x["name"]: x for x in namen2}["chrome.exe"]["cpu_pct"] is None, "PID neu vergeben (anderer Name) → kein Delta, keine Fantasie-CPU")
namen3, _, _ = A(proz, vorher, None, 6, {}, 20)
check(all(x["cpu_pct"] is None for x in namen3), "erste Runde (kein dt) → keine CPU-Werte")
viele = [{"pid": k, "ppid": 1, "name": f"p{k}.exe", "cpu": k * 1e6, "ws": k * MB, "priv": (100 - k) * MB} for k in range(1, 60)]
nv, _, _ = A(viele, {k: (f"p{k}.exe", 0) for k in range(1, 60)}, 60, 6, {}, None)
check(len(nv) <= 2 * ns["PC_LAST_TOP_N"] and nv[0]["name"] == "p59.exe" and any(x["name"] == "p1.exe" for x in nv),
      f"Top-Liste klein (≤ {2 * ns['PC_LAST_TOP_N']}): die größten nach CPU UND nach RAM")
pys = [{"pid": k, "ppid": 1, "name": "python.exe", "cpu": 1, "ws": MB, "priv": MB} for k in range(100, 140)]
_, pv, _ = A(pys, {}, 60, 6, {}, None)
check(len(pv) == ns["PC_LAST_PY_MAX"], "python-Liste gedeckelt (mt5_live-Zeilen klein halten)")
S = ns["pc_last_system"]
s = S(88, 8 * 1073741824, 1 * 1073741824, (100, 500, 500), (0, 0, 0), 3 * 86400000)
check(s == {"ram_gesamt_gb": 8.0, "ram_frei_gb": 1.0, "ram_belegt_pct": 88, "cpu_pct": 90.0, "betrieb_h": 72.0},
      f"System: idle 100 von 1000 → 90 % CPU, 8 GB / 1 GB frei, 72 h Betrieb ({s})")
check(S(10, 0, None, None, None, 0)["cpu_pct"] is None, "System ohne Vorwert → CPU unbekannt")
ns["tages_neustart_info"] = lambda: None   # DR1 (05.11.2026): eigener Test tools/selftest_tages_neustart.py
ns["_PC_LAST"] = {"cpu_pct": 1}
check(ns["panel_lauf_info"]()["last"] == {"cpu_pct": 1}, "Herzschlag: panel_lauf.last trägt die letzte Messung")
ns["_PC_LAST"] = None
check(ns["panel_lauf_info"]()["last"] is None, "vor der ersten Messung: last None")
check("threading.Thread(target=_pc_last_waechter, daemon=True).start()" in SRC, "Mess-Wache startet mit dem Panel")
w = SRC[SRC.index("def _pc_last_waechter("):SRC.index("def panel_lauf_info(")]
check('if os.name != "nt":' in w and "random.uniform" in w and "except Exception" in w, "Wache: nur Windows, gestreut (Jitter-Regel), wirft nie")
r_ = SRC[SRC.index("def _pc_last_runde("):SRC.index("def _pc_last_waechter(")]
check("subprocess" not in SRC[SRC.index("# ══ LAST DES PCs MESSEN"):SRC.index("def panel_lauf_info(")] and "CloseHandle(h)" in SRC and "CloseHandle(snap)" in SRC,
      "Messung ohne Unterprozess, jedes Handle geschlossen")
check("_PC_LAST = erg" in r_ and ".clear()" not in r_, "Messung wird als Ganzes ersetzt (kein halber Stand im Herzschlag)")
blk = SRC[SRC.index("# ══ LAST DES PCs MESSEN"):SRC.index("def panel_lauf_info(")]
check("OpenProcess(0x1000, False, pid)" in blk and "0x0010" not in blk.replace("# ", "").split("h = k32.OpenProcess")[1][:80],
      "nur Mindestrecht 0x1000 (kein VM_READ auf lsass & Co., S9-Gegenprüfung)")
check(ns["PC_LAST_TAKT_S"] >= 300 and "60.0 if runde == 1" in blk, "5-min-Takt (≤ 1 zusätzlicher mt5_live-Upsert je 5 min), zweite Runde nach ~60 s für erste CPU-Werte")

# ── 2) Schließ-Wache: Status-Dateien höchstens alle 0,5 s ──
k = SRC.index("# SCHLIESS-WACHE OHNE DAUER-LESEN")
ns2 = {"time": time}
exec(SRC[k:SRC.index("def _scharf_stand_lesen(")], ns2)
T = ns2["scharf_copier_tickets"]
z = {"n": 0}


def lesen():
    z["n"] += 1
    return {111: "abc", 222: ""}


check(T(100.0, lesen) == {111, 222} and z["n"] == 1, "erste Runde liest die Status-Dateien")
check(T(100.1, lesen) == {111, 222} and T(100.45, lesen) == {111, 222} and z["n"] == 1, "innerhalb 0,5 s: kein neues Lesen (vorher je 0,05–0,1 s)")
T(100.5, lesen)
check(z["n"] == 2, "nach 0,5 s wieder frisch gelesen")
T(50.0, lesen)
check(z["n"] == 3, "Uhr rückwärts → neu lesen, nie ewig alter Stand")
ns2["_SCHARF_COPIER_CACHE"].update(t=None, wert=None)
check(T(1.0, lambda: None) is None and T(1.1, lesen) is None, "nicht prüfbar (None) wird gemerkt wie bisher als None weitergegeben")


def kaputt():
    raise OSError("x")


ns2["_SCHARF_COPIER_CACHE"].update(t=None, wert=None)
try:
    T(5.0, kaputt)
    check(False, "Lesefehler wirft weiter (Aufrufer fängt ihn wie bisher)")
except OSError:
    check(ns2["_SCHARF_COPIER_CACHE"]["t"] is None, "Lesefehler wird nicht gemerkt (nächste Runde liest neu)")
wa = SRC[SRC.index("def _scharf_wache():"):SRC.index("# ══ LESE-SPERRE")]
check("tickets = scharf_copier_tickets()" in wa and "st = _scharf_stand_lesen()" in wa, "Wache: Reader-Stand weiter JEDE Runde, nur die Copier-Liste aus dem Zwischenspeicher")
check(ns2["SCHARF_COPIER_CACHE_S"] <= 1.0, "Zwischenspeicher nie länger als der Status-Takt des Copiers (1 s)")

# ── 3) Reader: positions.json gedrosselt ──
ns3 = {"time": time}
a = RSRC.index("DATEI_TAKT_S = 1.0")
exec(RSRC[a:RSRC.index("def _schreibe_datei_gedrosselt(")], ns3)
F = ns3["datei_faellig"]
check(F(True, 10.0, 9.99) and not F(False, 10.5, 10.0) and F(False, 11.0, 10.0) and F(False, 5.0, 10.0),
      "Datei: Änderung sofort, sonst erst nach 1 s, Uhr rückwärts → schreiben")
check(RSRC.count("_schreibe_datei_gedrosselt(lambda: _mit_an(_stand), wichtig=") == 2 and RSRC.count("_schreibe_datei(_mit_an(_stand))") == 1,
      "beide POST-Wege gedrosselt, nur der Schalter (_schalte) schreibt weiter sofort")
check('wichtig=(daten.get("positionen") != _pos_vorher) or _war_blind)' in RSRC and "wichtig=not _war_blind" in RSRC,
      "Positionswechsel und blind ↔ sehend schreiben sofort")
check(RSRC.index('_pos_vorher = (_t.get("stand")') < RSRC.index('_t["stand"], _t["stand_s"] = daten, time.time()'), "Vorher-Stand gelesen, bevor er überschrieben wird")
check('READER_VERSION = "0.9.11"' in RSRC, "Reader-Version gebumpt (0.9.11)")

print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
