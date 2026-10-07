#!/bin/bash
# Erzeugt .claude/CODEMAP.md neu — den Zeilen-Index über prophos.html und app.py.
#
# Warum: prophos.html ist ~20.500 Zeilen in einer Datei. Ohne Index muss sich
# jeder (Mensch wie Claude) per grep durch mehrdeutige Treffer tasten. Mit Index
# springt man direkt in den richtigen Zeilenbereich.
#
# Nach groesseren Aenderungen an prophos.html oder app.py einmal ausfuehren:
#   bash .claude/codemap.sh
#
# Das Script LIEST nur. Es fasst prophos.html und app.py nicht an.

set -euo pipefail
cd "$(dirname "$0")/.."

HTML=prophos.html
PY=app.py
OUT=.claude/CODEMAP.md

[ -f "$HTML" ] || { echo "FEHLER: $HTML nicht gefunden (falsches Verzeichnis?)" >&2; exit 1; }
[ -f "$PY" ]   || { echo "FEHLER: $PY nicht gefunden (falsches Verzeichnis?)" >&2; exit 1; }

# ── Block-Grenzen in prophos.html finden ────────────────────────────────────
JS_START=$(grep -n '<script type="module">' "$HTML" | head -1 | cut -d: -f1)
JS_END=$(awk -v s="$JS_START" 'NR>s && /^<\/script>/{print NR; exit}' "$HTML")
CSS1_START=$(grep -n '^<style>' "$HTML" | head -1 | cut -d: -f1)
CSS1_END=$(awk -v s="$CSS1_START" 'NR>s && /^<\/style>/{print NR; exit}' "$HTML")
HTML_TOTAL=$(wc -l < "$HTML" | tr -d ' ')

{
echo "# CODEMAP — Prophos"
echo
echo "Automatisch erzeugt von \`.claude/codemap.sh\`. Nicht von Hand pflegen —"
echo "nach Aenderungen neu erzeugen: \`bash .claude/codemap.sh\`"
echo
echo "> Zweck: direkt in den richtigen Zeilenbereich springen, statt eine"
echo "> 20.000-Zeilen-Datei mit mehrdeutigen grep-Treffern zu durchsuchen."
echo "> Lesen z.B. mit \`sed -n '13159,13400p' prophos.html\` oder Read(offset/limit)."
echo
echo '---'
echo
echo "## prophos.html — Grobstruktur ($HTML_TOTAL Zeilen)"
echo
echo '| Bereich | Zeilen | Umfang |'
echo '|---|---|---|'
printf '| CSS (Hauptblock) | %s–%s | %s |\n' "$CSS1_START" "$CSS1_END" "$((CSS1_END-CSS1_START+1))"
printf '| HTML-Markup (Views + Modals) | %s–%s | %s |\n' "$((CSS1_END+1))" "$((JS_START-1))" "$((JS_START-CSS1_END-1))"
printf '| **JS-Modul** (ein `<script type="module">`) | **%s–%s** | **%s** |\n' "$JS_START" "$JS_END" "$((JS_END-JS_START+1))"
printf '| Rest (CSS-/JS-Nachtrag) | %s–%s | %s |\n' "$((JS_END+1))" "$HTML_TOTAL" "$((HTML_TOTAL-JS_END))"

echo
echo "## prophos.html — JS-Sektionen ($JS_START–$JS_END)"
echo
echo 'Sortiert nach Zeilennummer. "bis" ist der Beginn der naechsten Sektion.'
echo
echo '| Zeilen | Umfang | Sektion |'
echo '|---|---|---|'
grep -n '^  /\* =\+ .* =\+ \*/' "$HTML" \
  | awk -F: -v s="$JS_START" -v e="$JS_END" '$1>=s && $1<=e {
      n=$1; sub(/^[0-9]+:/,""); t=$0
      gsub(/^[ \t]*\/\* =+ */,"",t); gsub(/ *=+ \*\/$/,"",t)
      line[++c]=n; title[c]=t
    }
    END{ for(i=1;i<=c;i++){ end=(i<c)?line[i+1]-1:e
      printf "| %d–%d | %d | %s |\n", line[i], end, end-line[i]+1, title[i] } }'

echo
echo '### Benannte Bloecke (Kopfzeilen `/* ══ TITEL … ══ */` und `/* TITEL (Datum …`)'
echo
echo 'Seit 10/2026 beginnen neue Bereiche mit einer Kopfzeile in Grossbuchstaben (Box-Zeichen ══ oder Titel + Klammer),'
echo 'z.B. START-FEHLER & NEU EINPLANEN, TRADE-PLANER-SEITE, MANUELLE ARBEIT. "bis" = naechster benannter Block oder ENDE-Marke.'
echo
echo '| Zeilen | Block |'
echo '|---|---|'
awk -v s="$JS_START" -v e="$JS_END" '
  NR>=s && NR<=e && (/^  \/\* ══ / || /^  \/\* [A-ZÄÖÜ0-9][A-ZÄÖÜ0-9 \-–&\/·,]{5,} \(/) {
    t=$0; sub(/^  \/\* ══ /,"",t); sub(/^  \/\* /,"",t)
    sub(/ ══ \*\/.*$/,"",t); sub(/ \(.*$/,"",t); sub(/ ══.*$/,"",t); sub(/[ \t]+$/,"",t)
    if (t=="") next
    line[++c]=NR; title[c]=t
  }
  END{ for(i=1;i<=c;i++){ end=(i<c)?line[i+1]-1:e
    if (title[i] ~ /^ENDE /) { printf "| %d | %s |\n", line[i], title[i]; continue }
    printf "| %d–%d | %s |\n", line[i], end, title[i] } }' "$HTML"

echo
echo '### Untersektionen in den grossen Bloecken'
echo
echo 'Die Sektion "INITIAL LOAD" ist ein Sammelblock — hier stecken mehrere eigenstaendige Bereiche:'
echo
echo '| ab Zeile | Block |'
echo '|---|---|'
awk -v s="$JS_START" -v e="$JS_END" '
  NR>=s && NR<=e && /^  \/\* =+$/ {
    start=NR
    if ((getline nxt) > 0) {
      sub(/^[ \t]*\*?[ \t]*/, "", nxt)          # fuehrendes " * " oder Einrueckung weg
      if (nxt != "") printf "| %d | %s |\n", start, nxt
    }
  }' "$HTML" | sort -t'|' -k2 -n | awk '!seen[$0]++'

echo
echo "## prophos.html — Views und Modals ($((CSS1_END+1))–$((JS_START-1)))"
echo
echo 'Jede `section.view` ist ein Tab im Dashboard. `modal-bg` sind die Overlays.'
echo
echo '| Zeile | Element |'
echo '|---|---|'
awk -v s="$((CSS1_END+1))" -v e="$((JS_START-1))" 'NR>=s && NR<=e {
    if (match($0, /<section class="view[^"]*" data-view="[^"]+"/)) {
      m=substr($0,RSTART,RLENGTH); sub(/.*data-view="/,"",m); sub(/".*/,"",m)
      printf "| %d | view: **%s** |\n", NR, m
    } else if (match($0, /<div class="modal-bg" id="[^"]+"/)) {
      m=substr($0,RSTART,RLENGTH); sub(/.*id="/,"",m); sub(/".*/,"",m)
      printf "| %d | modal: %s |\n", NR, m
    }
  }' "$HTML"

echo
echo "## app.py — Routen ($(wc -l < "$PY" | tr -d ' ') Zeilen)"
echo
echo '| Zeile | Route |'
echo '|---|---|'
grep -n '^@app\.route' "$PY" | sed 's/^\([0-9]*\):@app\.route(\(.*\))$/| \1 | `\2` |/'

echo
echo '## app.py — Sektionen'
echo
echo '| Zeile | Sektion |'
echo '|---|---|'
grep -n '^# ── ' "$PY" | awk -F: '{
    n=$1; t=substr($0, index($0,":")+1)
    sub(/^# ── /, "", t)
    gsub(/[ ─]+$/, "", t)                       # Trenn-Striche am Zeilenende weg
    printf "| %s | %s |\n", n, t
  }'

echo
echo '---'
echo
echo "_Erzeugt aus $HTML ($HTML_TOTAL Zeilen) und $PY._"
} > "$OUT"

echo "OK — $OUT neu erzeugt ($(wc -l < "$OUT" | tr -d ' ') Zeilen)."
