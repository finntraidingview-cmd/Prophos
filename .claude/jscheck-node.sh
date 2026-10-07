#!/bin/bash
# Syntax-Check des JS-Moduls in prophos.html mit Node (07.10.2026, Routine „Puls-Fehler" in der Cloud: dort gibt es
# kein macOS-jsc wie in jscheck.sh). Zieht das <script type="module"> heraus und lässt `node --check` als ES-Modul
# (.mjs) darüber laufen — parst nur, führt nichts aus.
# Aufruf: bash .claude/jscheck-node.sh [pfad/zu/prophos.html]   → "OK" oder "ERR …"
set -e
F="${1:-prophos.html}"
command -v node >/dev/null 2>&1 || { echo "ERR node fehlt — auf macOS bash .claude/jscheck.sh nehmen"; exit 1; }
T=$(mktemp -d)
python3 - "$F" "$T/mod.mjs" <<'PY'
import re, sys
s = open(sys.argv[1], encoding='utf-8').read()
m = re.findall(r'<script type="module"[^>]*>(.*?)</script>', s, re.S)
if len(m) != 1: sys.exit(f"erwartet genau 1 Modul-Skript, gefunden {len(m)}")
open(sys.argv[2], 'w', encoding='utf-8').write(m[0])
print("Modul beginnt nach Dateizeile", s[:s.find(m[0])].count('\n'), file=sys.stderr)
PY
if node --check "$T/mod.mjs" 2>"$T/err"; then echo OK; else echo "ERR $(head -c 600 "$T/err")"; rm -rf "$T"; exit 1; fi
rm -rf "$T"
