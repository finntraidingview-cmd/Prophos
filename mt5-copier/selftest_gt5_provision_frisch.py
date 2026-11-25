#!/usr/bin/env python3
"""Selbsttest GT5 (25.11.2026): das Panel lädt provision.py vor jeder Einrichtung neu, wenn die Datei auf der Platte vom geladenen Abbild abweicht
(Befund GT4 pc-2zc2we: GT3-panel.py lief, im Speicher aber noch das alte provision.py → jede Einrichtung wieder mit EURUSD). Prüft provision_frisch
(echter Quelltext aus panel.py): gleich → nichts; neuer gültiger Stand → neu laden + Abbild nachziehen; kaputte Datei → alter Stand bleibt;
unlesbar → nichts; Fehler beim Laden → alter Stand; Aufruf im Einrichtungs-Worker VOR run_provision. Ohne Windows. Aufruf: python3 mt5-copier/selftest_gt5_provision_frisch.py"""
import ast
import os
import sys
import types

HIER = os.path.dirname(os.path.abspath(__file__))
FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


SRC = open(os.path.join(HIER, "panel.py"), encoding="utf-8").read()
baum = ast.parse(SRC)
fns = {x.name: x for x in baum.body if isinstance(x, ast.FunctionDef)}


def laden(alt):
    mod = types.ModuleType("provision"); mod.__file__ = "/x/provision.py"; mod.WERT = "alt"
    ns = {"os": os, "HERE": "/x", "provision": mod, "_GELADEN": {"provision": alt}, "print": lambda *a, **k: None}
    for n in ("_code_glatt", "provision_probe", "provision_frisch"):
        exec(compile(ast.Module(body=[fns[n]], type_ignores=[]), "panel.py", "exec"), ns)
    return ns


ALT = b"X = 1\r\n"
NEU = b"X = 2\n"
print("1) provision_frisch")
ns = laden(ALT)
geladen = []
check(ns["provision_frisch"](lesen=lambda p: b"\xef\xbb\xbfX = 1\n", neu_laden=lambda: geladen.append(1)) == "gleich" and not geladen,
      "gleicher Stand (nur BOM/Zeilenenden anders) → nichts neu laden")
r = ns["provision_frisch"](lesen=lambda p: NEU, neu_laden=lambda: geladen.append(1))
check(r == "neu" and geladen == [1] and ns["_GELADEN"]["provision"] == NEU, f"neuer Stand → neu laden, Abbild nachgezogen ({r})")
check(ns["provision_frisch"](lesen=lambda p: NEU, neu_laden=lambda: geladen.append(1)) == "gleich" and geladen == [1], "danach gleich → kein zweites Laden")
ns = laden(ALT)
r = ns["provision_frisch"](lesen=lambda p: b"def kaputt(:\n", neu_laden=lambda: geladen.append(2))
check(r.startswith("fehler") and 2 not in geladen and ns["_GELADEN"]["provision"] == ALT, f"kaputte Datei → nicht laden, alter Stand bleibt ({r})")
check(ns["provision_frisch"](lesen=lambda p: None, neu_laden=lambda: geladen.append(3)) == "gleich" and 3 not in geladen, "Datei unlesbar → nichts")


def wirft():
    raise ImportError("x")


r = ns["provision_frisch"](lesen=lambda p: NEU, neu_laden=wirft)
check(r.startswith("fehler") and ns["_GELADEN"]["provision"] == ALT, f"Fehler beim Laden → alter Stand bleibt ({r})")

print("1b) GT5b: neuester Stand aus dem Repo (start-panel.bat lädt provision.py nicht)")
REPO = b"def run_provision():\n    pass\n" + b"# " + b"x" * 6000 + b"\n"
platte = {"d": ALT}
geschrieben, geladen = [], []
ns = laden(ALT)


def schreib(p, neu, alt):
    geschrieben.append((p, alt))
    platte["d"] = neu


r = ns["provision_frisch"](lesen=lambda p: platte["d"], neu_laden=lambda: geladen.append(1), holen=lambda: REPO, schreiben=schreib)
check(r == "neu" and geschrieben == [("/x/provision.py", ALT)] and geladen == [1] and ns["_GELADEN"]["provision"] == REPO,
      f"Repo neuer als Platte → atomar schreiben (alter Stand als .prev), dann laden ({r})")
r = ns["provision_frisch"](lesen=lambda p: platte["d"], neu_laden=lambda: geladen.append(2), holen=lambda: REPO, schreiben=schreib)
check(r == "gleich" and len(geschrieben) == 1 and 2 not in geladen, "Repo = Platte = geladen → nichts")
ns = laden(ALT)
platte["d"] = ALT
for kaputt, warum in ((b"def run_provision():\n", "zu klein"), (b"x = 1\n" * 2000, "ohne run_provision"), (b"def run_provision(:\n" + b"#" * 6000, "Syntaxfehler")):
    geschrieben.clear()
    r = ns["provision_frisch"](lesen=lambda p: platte["d"], neu_laden=lambda: geladen.append(3), holen=lambda k=kaputt: k, schreiben=schreib)
    check(r == "gleich" and not geschrieben and platte["d"] == ALT, f"Repo-Stand {warum} → nicht schreiben, Platte bleibt ({r})")


def kein_netz():
    raise OSError("offline")


r = ns["provision_frisch"](lesen=lambda p: NEU, neu_laden=lambda: geladen.append(4), holen=kein_netz, schreiben=schreib)
check(r == "neu" and 4 in geladen and not geschrieben, f"kein Netz → Stand der Platte (neuer als geladen → laden) ({r})")
check("repo_datei(\"mt5-copier/provision.py\", sha, 10)" in SRC and "os.replace(p + \".tmp\", p)" in SRC and 'p + ".prev"' in SRC and "alt_ns = dict(provision.__dict__)" in SRC,
      "Quelle = neuester Commit (repo_sha), atomar über .tmp, alter Stand als .prev")

print("1c) Prüfer-Stopp S2: Laufzeitfehler beim Neuladen → Modul vollständig zurück, selbst geschriebene Datei zurück")
ns = laden(ALT)
mod = ns["provision"]


def halb_und_fehler():
    mod.WERT = "neu"            # reload hat schon einen Teil ausgeführt …
    mod.NUR_NEU = 1
    raise RuntimeError("Laufzeitfehler mitten im Modul")


r = ns["provision_frisch"](lesen=lambda p: NEU, neu_laden=halb_und_fehler, holen=lambda: None)
check(r.startswith("fehler") and mod.WERT == "alt" and not hasattr(mod, "NUR_NEU") and ns["_GELADEN"]["provision"] == ALT,
      f"Laufzeitfehler → Modul-Namensraum exakt wie vorher, Abbild alt ({r}, WERT={mod.WERT})")
ns = laden(ALT)
mod = ns["provision"]
platte = {"d": ALT}
schreib_log = []


def schreib2(p, neu, alt):
    schreib_log.append(neu)
    platte["d"] = neu


r = ns["provision_frisch"](lesen=lambda p: platte["d"], neu_laden=halb_und_fehler, holen=lambda: REPO, schreiben=schreib2)
check(r.startswith("fehler") and schreib_log == [REPO, ALT] and platte["d"] == ALT and mod.WERT == "alt",
      f"Repo-Stand geschrieben, Laden scheitert → Datei auf den alten Stand zurück, Modul alt ({r})")

print("1d) Prüfer S2: Kandidat probeweise ausführen — Laufzeitfehler auf Modul-Ebene → nichts schreiben, nichts laden")
LAUFZEIT = b"def run_provision():\n    pass\nraise RuntimeError('Modul-Ebene')\n# " + b"x" * 6000 + b"\n"
ns = laden(ALT)
mod = ns["provision"]
platte = {"d": ALT}
schreib_log, geladen = [], []
r = ns["provision_frisch"](lesen=lambda p: platte["d"], neu_laden=lambda: geladen.append(1), holen=lambda: LAUFZEIT, schreiben=lambda p, n, a: schreib_log.append(n))
check(r == "gleich" and not schreib_log and not geladen and mod.WERT == "alt" and platte["d"] == ALT,
      f"Repo-Kandidat mit Laufzeitfehler → nicht geschrieben (Copier/order_bot importieren die Datei selbst), Modul unverändert ({r})")
r = ns["provision_frisch"](lesen=lambda p: LAUFZEIT, neu_laden=lambda: geladen.append(2), holen=lambda: None)
check(r.startswith("fehler") and not geladen and mod.WERT == "alt" and ns["_GELADEN"]["provision"] == ALT,
      f"Platte mit Laufzeitfehler → kein Reload, Modul und Abbild unverändert ({r})")
probe_ns = {}
try:
    ns["provision_probe"](b"Y = __name__\nimport json\n", "/x/provision.py")
    ok_probe = True
except Exception:
    ok_probe = False
check(ok_probe and not hasattr(mod, "Y"), "Probe läuft im eigenen Namensraum (__name__ provision_probe), das geladene Modul bleibt unberührt")
SRC2 = open(os.path.join(HIER, "panel.py"), encoding="utf-8").read()
pf = SRC2[SRC2.index("def provision_frisch("):SRC2.index("def prov_start(")]
check(pf.index("(pruefen or provision_probe)(repo, pfad)") < pf.index("_datei_schreiben(pfad, repo, platte)")
      and pf.index("(pruefen or provision_probe)(neu, pfad)") < pf.index("alt_ns = dict(provision.__dict__)") < pf.rindex("importlib.reload(provision)"),
      "Reihenfolge: Probe → schreiben; Probe → Namensraum sichern → reload")

print("2) Einbau im Einrichtungs-Worker")
w = SRC[SRC.index("def prov_start("):]
w = w[:w.index("\ndef ", 10)]
i_f, i_sk, i_rp = w.find("provision_frisch()"), w.find('{"startup_symbols": provision.startup_symbole'), w.find("provision.run_provision(")
check(-1 < i_f < i_sk < i_rp, "provision_frisch() läuft im Worker vor dem Start-Symbol (GT3) und vor run_provision")
check("importlib.reload(provision)" in SRC and 'exec(compile(code, pfad, "exec"), {"__name__": "provision_probe", "__file__": pfad, "__builtins__": __builtins__})' in SRC, "Probe im frischen Namensraum, dann importlib.reload(provision)")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ alle Prüfungen grün")
