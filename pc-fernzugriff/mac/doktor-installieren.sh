#!/bin/bash
# FEHLSTART-DOKTOR am Mac ein-/ausschalten (FX2, 10.11.2026). launchd-Muster wie com.prophos.flask, aber OHNE KeepAlive: launchd startet doktor.py alle 120 s,
# jeder Lauf endet nach Sekunden. launchd startet im Ruhezustand nicht und weckt den Mac nicht — nichts hält ihn wach (feedback-mac-nicht-durchlaufen).
#
#   doktor-installieren.sh an     Job anlegen + laden (vorher ~/.prophos-fernzugriff/doktor.key anlegen, Inhalt = Railway-Variable DOKTOR_KEY)
#   doktor-installieren.sh aus    Job entladen + entfernen (Railway-Gehirn läuft weiter, nur ohne Hände: Aufträge verfallen, Meldungen kommen weiter)
#   doktor-installieren.sh stand  zeigt, ob der Job geladen ist, und die letzten Log-Zeilen
# Schnell-Aus ohne launchctl: touch ~/.prophos-fernzugriff/doktor-aus (Datei löschen = wieder an).
set -euo pipefail
LABEL=com.prophos.doktor
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SKRIPT="$(cd "$(dirname "$0")" && pwd)/doktor.py"
case "${1:-}" in
  an)
    [ -f "$HOME/.prophos-fernzugriff/doktor.key" ] || { echo "~/.prophos-fernzugriff/doktor.key fehlt (Inhalt = Railway-Variable DOKTOR_KEY)"; exit 1; }
    chmod 600 "$HOME/.prophos-fernzugriff/doktor.key"
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string><string>-c</string>
    <string>PATH=/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin exec python3 -u "$SKRIPT"</string>
  </array>
  <key>StartInterval</key><integer>120</integer>
  <key>RunAtLoad</key><false/>
  <key>ProcessType</key><string>Background</string>
  <key>LowPriorityIO</key><true/>
  <key>Nice</key><integer>10</integer>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/prophos-doktor.out</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/prophos-doktor.out</string>
</dict></plist>
EOF
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    rm -f "$HOME/.prophos-fernzugriff/doktor-aus"
    echo "Doktor am Mac AN (alle 2 min, nur Handelszeit, Akku ≥ 20 %)" ;;
  aus)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Doktor am Mac AUS" ;;
  stand)
    launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null | grep -E "state|last exit" || echo "nicht geladen"
    tail -n 15 "$HOME/Library/Logs/prophos-doktor.log" 2>/dev/null || true ;;
  *) sed -n '2,9p' "$0" | cut -c3-; exit 2 ;;
esac
