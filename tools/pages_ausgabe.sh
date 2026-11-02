#!/usr/bin/env bash
# PAGES-AUSGABE (02.11.2026, Eingang, Stufe 1; Bestand S12): Cloudflare Pages liefert bisher das ganze Repo ohne Login aus (app.py, order_bot.py, sql/, .claude/ …).
# Dieses Skript füllt einen Ausgabeordner mit genau der Liste unten, Pfade wie bisher. Ohne Dashboard-Einstellung (Build command + Build output directory) wirkt es nicht.
# Neue Datei auf pages.dev nötig → hier eintragen UND in tools/selftest_pages_ausgabe.py; alles andere bleibt draußen. Bewusst feste Liste, kein Muster und keine Ausschlussliste.
# Fehlt eine Datei oder ist prophos.html unbrauchbar: Abbruch, der Build schlägt fehl, die alte Fassung bleibt live. Unbekannte Pfade liefert Pages als HTTP 200 mit der Startseite,
# ein still fehlendes VERSION hieße daher: PC-Tabs laden nie mehr neu.
set -euo pipefail

WURZEL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUS="${1:-$WURZEL/_pages}"

# rm -rf nur auf einem Ordner, der wirklich so heißt (ein falsches Argument löscht sonst das Falsche)
if [ "$(basename "$AUS")" != "_pages" ]; then
  echo "pages_ausgabe: Ausgabeordner muss _pages heißen, nicht: $AUS" >&2
  exit 2
fi

DATEIEN=(
  # Oberfläche, Service Worker, Icons
  index.html
  prophos.html
  sw.js
  prophos-icon-180.png
  prophos-icon-192.png
  prophos-icon-512.png
  # Build-Wächter im Tab (prophos.html fetch('/mt5-copier/VERSION')), sonst laden die Tabs nicht neu
  mt5-copier/VERSION
  # Tampermonkey @require im TopstepX-Auge (tv-reader/tsx-auge.user.js)
  mt5-copier/augen_tsx.js
  # TopstepX-Augen von vor 29.10.2026 (a64d7cad) suchen ihr Update hier (@updateURL). Ohne die Datei blieben sie still auf altem Stand, die aktuelle Fassung aktualisiert
  # sich über das Panel. Kann weg, sobald auf allen TopstepX-PCs Auge 0.3.0 oder neuer läuft.
  tv-reader/tsx-auge.user.js
  # Sonst tv-reader/* nicht mehr (S14, 02.11.2026): Seit .1976 kommt der Reader per Paket oder Railway, das Userscript liefert der Reader auf 127.0.0.1:8790 über Railway.
  # Kein Code holt von hier, Beleg in der Commit-Nachricht. Eine alte start-alles.bat speichert schlimmstenfalls die Startseite, die neue löscht so eine Datei wieder.
)

for f in "${DATEIEN[@]}"; do
  if [ ! -s "$WURZEL/$f" ]; then
    echo "pages_ausgabe: Datei fehlt oder ist leer: $f" >&2
    exit 1
  fi
done
if ! grep -q "OS_TAB_BUILD = '" "$WURZEL/prophos.html"; then
  echo "pages_ausgabe: prophos.html ohne OS_TAB_BUILD" >&2
  exit 1
fi

rm -rf "$AUS"
for f in "${DATEIEN[@]}"; do
  mkdir -p "$AUS/$(dirname "$f")"
  cp "$WURZEL/$f" "$AUS/$f"
done
echo "pages_ausgabe: ${#DATEIEN[@]} Dateien nach $AUS"
