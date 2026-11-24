#!/usr/bin/env python3
"""Selbsttest EM2 (25.11.2026): „bewiesener“ MT5-Servername vom PC ersetzt den DB-Namen nur, wenn er reines ASCII ist.
Anlass: Emin · Blue Guardian 100k …1836 · Emin — DB-Zugangsdaten reines ASCII, trotzdem „Zugangsdaten enthalten Sonderzeichen/Umlaute“.
mt5ServerBewiesen (prophos.html) verglich mit /\\s+/ — JS-\\s umfasst NBSP & Co., ein Instanz-/Snapshot-Name mit Unicode-Leerzeichen galt
als „gleich“ und ging statt des sauberen DB-Namens ans Panel. Prüft den ECHTEN JS-Code in JavaScriptCore (jsc), dazu den Heil-Riegel
(mt5ServerHeilen schreibt nie einen Nicht-ASCII-Namen in die DB) und panel.mi1_feld_norm (Login/Server säubern, Passwort nie).
Aufruf:  python3 tools/selftest_em2_server_ascii.py   (macOS mit JavaScriptCore; ohne jsc wird der JS-Teil laut übersprungen = rot)"""
import json
import os
import re
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
PANEL = open(os.path.join(WURZEL, "mt5-copier", "panel.py"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


# ── JS: mt5ServerNorm / mt5ServerAscii / mt5ServerBewiesen aus prophos.html ──
i = HTML.index("  const mt5ServerNorm = x =>")
j = HTML.index("  // DB heilt sich selbst:", i)
js = HTML[i:j]
check("mt5ServerAscii(b)" in js, "mt5ServerBewiesen prüft ASCII")
heil = HTML[HTML.index("async function mt5ServerHeilen("):HTML.index("async function mt5ServerHeilen(") + 600]
check("!mt5ServerAscii(srv)" in heil, "mt5ServerHeilen heilt nie einen Nicht-ASCII-Namen in die DB")

FAELLE = [
    # (DB, Instanz-Status-Server, Instanz-Config-Server, erwartet, Name)
    ("BlueGuardian-Server", "Blue Guardian-Server", None, "BlueGuardian-Server", "NBSP im bewiesenen Namen → DB-Name bleibt"),
    ("BlueGuardian-Server", None, "BlueGuardian -Server", "BlueGuardian-Server", "Schmal-Leerzeichen in der Config → DB-Name bleibt"),
    ("BlueGuardian-Server", None, "﻿BlueGuardian-Server", "BlueGuardian-Server", "BOM vorn (trim) → gleich, DB-Name"),
    ("FTMO-Server 4", "FTMO-Server4", None, "FTMO-Server4", "Leerzeichen-Variante in ASCII → bewiesener Name (wie bisher)"),
    ("FundedNext-Server 2", None, "FundedNext-Server 2", "FundedNext-Server 2", "gleich → DB-Name"),
    ("BlueGuardian-Server", "Other-Server", None, "BlueGuardian-Server", "anderer Server → DB-Name"),
    ("", "X", None, "", "ohne DB-Server → leer"),
]
if os.path.exists(JSC):
    prog = js + "\nconst F = " + json.dumps([[d, s, c] for d, s, c, _, _ in FAELLE]) + ";\n" \
        "print(JSON.stringify(F.map(f => mt5ServerBewiesen({ status: { master_login: '631836', master_server: f[1] }, master_server: f[2] }, '631836', f[0]))));\n"
    pfad = os.path.join(os.environ.get("TMPDIR", "/tmp"), "em2_test.js")
    open(pfad, "w", encoding="utf-8").write(prog)
    r = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=30)
    try:
        aus = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        aus = None
        print(r.stdout, r.stderr)
    for k, (d, s, c, erw, name) in enumerate(FAELLE):
        check(aus is not None and aus[k] == erw, f"JS {name} ({aus[k] if aus else '?'!r})")
else:
    check(False, "jsc fehlt — JS-Teil nicht geprüft")

# ── Python: panel.mi1_feld_norm ──
ns = {}
exec(re.search(r"^_MI1_NULLBREITE = [^\n]*", PANEL, re.M).group(0), ns)
k = PANEL.index("\ndef mi1_feld_norm(") + 1
exec(PANEL[k:PANEL.find("\n\n\n", k)], ns)
N = ns["mi1_feld_norm"]
check(N("BlueGuardian-Server") == "BlueGuardian-Server" and N(" 631836 ") == "631836" and N(None) == "", "ASCII bleibt (nur außen getrimmt)")
check(N("Blue Guardian-Server") == "Blue Guardian-Server" and N("BlueGuardian-Server​") == "BlueGuardian-Server",
      "NBSP → Leerzeichen, Null-Breite weg")
check(N("６３１８３６") == "631836" and N("﻿631836") == "631836", "Vollbreit-Ziffern/BOM → ASCII-Login")
st = PANEL[PANEL.index("\ndef start_terminal("):PANEL.index("\nPAGE = r")]
check("creds = dict(creds, login=mi1_feld_norm(creds.get(\"login\")), server=mi1_feld_norm(creds.get(\"server\")))" in st
      and "password=mi1_feld_norm" not in st, "start_terminal normalisiert Login + Server, nie das Passwort")
check(st.index("mi1_feld_norm(creds.get(\"login\"))") < st.index("provision.terminal_pids(install_dir)"), "Normalisieren VOR jedem Kill")
check(st.index("mi1_feld_norm(creds.get(\"login\"))") < st.index("str(creds.get(\"login\")) != str(expected)"),
      "EM2b: Normalisieren VOR dem Abgleich mit dem erwarteten Konto")
check(st.index("mi1_feld_norm(creds.get(\"login\"))") < st.index("if creds and not (creds.get(\"server\") or cfg.get(\"master_server\")):"),
      "EM2b: Server-Pflicht prüft den gesäuberten Server")

print(f"\n{'ALLES GRÜN' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
sys.exit(1 if FEHLER else 0)
