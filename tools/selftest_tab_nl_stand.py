#!/usr/bin/env python3
"""Selbsttest Neulade-Grund je PC (02.11.2026): Das Panel schickt Grund und letztes Ergebnis mit, Railway merkt beides, Admin zeigt es im Hinweis. Ohne Netz. Aufruf: python3 tools/selftest_tab_nl_stand.py"""
import ast
import json
import os
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, urlparse

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def py_fn(pfad, name, ns):
    src = open(os.path.join(W, pfad), encoding="utf-8").read()
    for n in ast.parse(src).body:
        if isinstance(n, ast.FunctionDef) and n.name == name:
            exec(ast.get_source_segment(src, n), ns)
            return
    raise ValueError(name)


# Railway
ns = {}
py_fn("app.py", "tab_nl_merken", ns)
m = {}
merken = ns["tab_nl_merken"]
merken(m, "pc-a", "Tab .1954 hinter .1981 — wartet: Puls", "", None, 100.0)
check(m["pc-a"]["grund_at"] == 100.0 and m["pc-a"]["ergebnis"] == "", "Grund ohne Ergebnis wird gemerkt")
merken(m, "pc-a", "Tab .1954 hinter .1981 — wartet: Puls", "", None, 160.0)
check(m["pc-a"]["grund_at"] == 100.0, "gleicher Grund behält seine Zeit")
merken(m, "pc-a", "x → neu geladen: Strg+F5 in „Prophos“", "x → neu geladen: Strg+F5 in „Prophos“", "150", 200.0)
check(m["pc-a"]["ergebnis_at"] == 150.0, "Ergebnis trägt die Zeit des Panels")
merken(m, "pc-a", "", "x → neu geladen: Strg+F5 in „Prophos“", "150", 260.0)
check(m["pc-a"]["grund"] == "" and m["pc-a"]["ergebnis"].startswith("x →"), "Tab aktuell: Grund weg, letztes Ergebnis bleibt")
merken(m, "pc-b", "", "y", "kaputt", 300.0)
check(m["pc-b"]["ergebnis_at"] == 300.0, "unlesbare Panel-Zeit → jetzt")
merken(m, "pc-c", "", "", None, 300.0)
check(m["pc-c"]["ergebnis"] == "" and m["pc-c"]["grund"] == "", "altes Panel ohne Felder stört nicht")
APP = open(os.path.join(W, "app.py"), encoding="utf-8").read()
check('!= "prophos-agent":   # der Lotse-Agent schickt keine Spur' in APP, "der Lotse-Agent leert den Grund nicht")

# Panel
urls = []
ns = {"TAB_NL": {"ergebnis": "", "ergebnis_at": 0.0}, "json": json, "code_holen": lambda u, timeout=0: (urls.append(u), b'{"ok": true}')[1]}
py_fn("mt5-copier/panel.py", "_tab_stand_holen", ns)
ns["_tab_stand_holen"]("pc-a", "")
check(urls[-1] == "/code/tab-stand/pc-a", "ohne Spur und Ergebnis bleibt der Aufruf wie vorher")
ns["_tab_stand_holen"]("pc-a", "Grund ä → x")
check(parse_qs(urlparse(urls[-1]).query) == {"panel": ["Grund ä → x"]}, "Spur kommt unverändert an")
ns["TAB_NL"].update(ergebnis="Tab → neu geladen & ok", ergebnis_at=123.9)
r = ns["_tab_stand_holen"]("pc-a", "")
q = parse_qs(urlparse(urls[-1]).query)
check(q == {"ergebnis": ["Tab → neu geladen & ok"], "ergebnis_at": ["123"]} and r == {"ok": True}, "Ergebnis läuft mit, Sonderzeichen überleben, Antwort unverändert")
PANEL = open(os.path.join(W, "mt5-copier", "panel.py"), encoding="utf-8").read()
check("TAB_NL.update(ergebnis=grund, ergebnis_at=jetzt)" in PANEL, "der Wächter merkt die Zeit zum Ergebnis")

# Admin-Hinweis
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
i = HTML.index("function admPcsNlText(")
j = HTML.index("\n  }\n", i)
JS = HTML[i:j + 4] + """
print(JSON.stringify([admPcsNlText(null), admPcsNlText({grund: '', ergebnis: ''}), admPcsNlText({grund: 'G', ergebnis: ''}), admPcsNlText({grund: '', ergebnis: 'E', ergebnis_at: 1793589052}), admPcsNlText({grund: 'G', ergebnis: 'E', ergebnis_at: 1793589052})]))
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
    t.write(JS)
r = subprocess.run([JSC, t.name], capture_output=True, text=True, timeout=30)
os.unlink(t.name)
if r.returncode or not r.stdout.strip():
    print(r.stdout, r.stderr)
    sys.exit(1)
o = json.loads(r.stdout.strip().splitlines()[-1])
check(o[0] == "" and o[1] == "", "ohne Stand kein Text")
check(o[2] == "Panel: G", "nur Grund")
check(o[3].startswith("Letzter Neulade-Versuch ") and o[3].endswith(": E"), "nur Ergebnis mit Uhrzeit")
check(o[4].startswith("Panel: G\n"), "beides, je eine Zeile")
print("ROT:" if FEHLER else "alles grün", FEHLER if FEHLER else "")
sys.exit(1 if FEHLER else 0)
