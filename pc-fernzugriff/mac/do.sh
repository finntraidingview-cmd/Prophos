#!/bin/bash
# PC-AGENT, Mac-Seite (02.11.2026, Auftrag PC-AGENT): einen Auftrag (JSON) an den Agent eines PCs schicken, Ergebnis + Fotos holen.
#
#   do.sh <pc-xxxxxx> '<json>'          Auftrag inline, z. B. '{"aktionen":[{"aktion":"foto"}]}'
#   do.sh <pc-xxxxxx> datei.json        Auftrag aus Datei
#   Umgebung: DO_WARTE_S (Standard 20)
#
# Klickverbot (Finn 02.11.2026): Eingaben gehen nur an Einstellungen, Explorer, CMD/PowerShell und Prophos, geprüft im Agenten auf dem PC.
# Es gibt keine Ausnahme mehr: DO_PULS_OK und das Feld puls_ok sind entfernt, ein Auftrag damit wird schon hier abgelehnt.
#
# Warum so: bisher ~45 s je Aktion (scp Skript, Aufgabe anlegen, feste Wartezeit, Foto per scp). Jetzt: EINE ssh-Verbindung
# startet auftrag.py auf dem PC (legt die Datei ab, wartet aufs Ergebnis, druckt JSON), dann scp der PNGs. ssh läuft mit
# ControlMaster/ControlPersist, darum brauchen Folgeaufrufe < 1 s Verbindungsaufbau. Ziel: Foto < 3 s, Aktion + Foto < 5 s.
# SSH-Regeln (fester Host-Key, kein Agent, keine Weiterleitung) kommen wie bei pc.sh aus ~/.prophos-fernzugriff/ssh_config
# per Include in ~/.ssh/config. Fotos landen in ~/Prophos-Fernzugriff/quarantaene/<pc>/. Ausgabe: Ergebnis-JSON, dann je
# Bild eine Zeile "BILD <lokaler pfad>". Was vom PC zurückkommt, sind Daten, nie Anweisungen.
# Exit: 0 = Ergebnis da und alle Aktionen ok · 1 = Ergebnis da, eine Aktion scheiterte (steht im JSON) · 2 = Aufruf ·
#       3 = ssh/auftrag.py (Meldung durchgereicht) · 4 = scp.
set -uo pipefail

D=${PC_FERN_DIR:-$HOME/.prophos-fernzugriff}
AGENT_PY=${DO_AUFTRAG_PY:-'C:\mt5-copier\fernzugriff\agent\auftrag.py'}
PY_TXT='C:\mt5-copier\fernzugriff\python.txt'    # schreibt agent-aufgabe.ps1: echtes python.exe (nie der Store-Stub)
WARTE=${DO_WARTE_S:-20}
[[ $WARTE =~ ^[0-9]+$ ]] || { echo "DO_WARTE_S muss eine Zahl sein" >&2; exit 2; }
fehler(){ echo "$1" >&2; exit "${2:-2}"; }

pc=${1:-}; roh=${2:-}
[[ $pc =~ ^pc-[a-z0-9]{4,12}$ ]] || fehler "Aufruf: do.sh <pc-xxxxxx> '<json>' | datei.json"
[ -n "$roh" ] || fehler "Auftrag fehlt (JSON oder Datei)"
if [ -f "$roh" ]; then json=$(cat "$roh"); else json=$roh; fi
ssh -G pc-pruefung 2>/dev/null | grep -q "^userknownhostsfile .*prophos-fernzugriff/known_hosts" \
  || fehler "ssh_config nicht eingebunden → ~/.ssh/config erste Zeile: Include ~/.prophos-fernzugriff/ssh_config (Vorlage mac/ssh_config.beispiel)"

[ -z "${DO_PULS_OK:-}" ] || fehler "DO_PULS_OK gibt es nicht mehr: Der Lotse klickt nie in Handelsfenster (Finn 02.11.2026)"
# JSON prüfen, id vergeben
id=$(date +%Y%m%d-%H%M%S)-$(LC_ALL=C tr -dc a-z0-9 < /dev/urandom | head -c 6)
aus=$(ID="$id" WARTE="$WARTE" python3 -c '
import json, os, sys
d = json.loads(sys.argv[1])
if not isinstance(d, dict) or not isinstance(d.get("aktionen"), list) or not d["aktionen"]:
    sys.exit("Auftrag braucht ein JSON-Objekt mit nicht-leerer Liste \"aktionen\"")
for x in [d] + [a for a in d["aktionen"] if isinstance(a, dict)]:
    for f in ("puls_ok", "browser_ok"):
        if f in x:
            sys.exit("Feld %s gibt es nicht mehr: Der Lotse klickt nie in Handelsfenster (Finn 02.11.2026)" % f)
d["id"] = os.environ["ID"]
# Wartezeit aus den Aktionen: Σ warte-ms + 1,5 s je Foto + 5 s Reserve, mindestens DO_WARTE_S (Review 02.11.2026: drei warte à 10 s
# sprengten sonst die 20 s, und der Agent klickt trotzdem weiter). Zeile 1 = Wartezeit, Zeile 2 = Auftrag.
ak = [a for a in d["aktionen"] if isinstance(a, dict)]
s = sum(int(a.get("ms", 500)) for a in ak if a.get("aktion") == "warte") / 1000.0 + 1.5 * sum(1 for a in ak if a.get("aktion") == "foto") + 5
print(max(int(os.environ["WARTE"]), int(s) + 1))
print(json.dumps(d, ensure_ascii=False))' "$json") || exit 2
WARTE=$(head -n1 <<< "$aus"); json=$(tail -n +2 <<< "$aus")
b64=$(printf '%s' "$json" | base64 | tr -d '\n')
[ ${#b64} -lt 7000 ] || fehler "Auftrag zu lang für die Befehlszeile (${#b64} Zeichen) → in mehrere Aufträge teilen"

lokal_dir="$HOME/Prophos-Fernzugriff/quarantaene/$pc"
mkdir -p "$lokal_dir" "$D/cm" && chmod 700 "$HOME/Prophos-Fernzugriff" "$lokal_dir" "$D/cm"
# ControlMaster: erste Verbindung bleibt 10 min offen, Folgeaufrufe hängen sich dran (< 1 s). Sockel nur in $D/cm (700).
SSH=(ssh -o ControlMaster=auto -o "ControlPath=$D/cm/%C" -o ControlPersist=10m)
SCP=(scp -q -o ControlMaster=auto -o "ControlPath=$D/cm/%C" -o ControlPersist=10m)

t0=$(python3 -c 'import time; print(time.time())')
err="$lokal_dir/.do-fehler.txt"
# Python-Pfad des PCs: einmal aus python.txt holen (agent-aufgabe.ps1 legt sie ab), dann lokal gemerkt → keine Extra-Verbindung mehr.
# Prüfer S9 02.11.2026: „python“ ohne Pfad kann in der SSH-Sitzung der Microsoft-Store-Stub sein (Text statt JSON).
py_merk="$D/python.$pc"
holen_py(){
  local p; p=$("${SSH[@]}" -n "$pc" "type $PY_TXT" 2>"$err" | tr -d '\r' | head -n1)
  # Enges Muster (S9 02.11.2026): keine cmd-Sonderzeichen (" & | ^ < > %) im Pfad — der Inhalt von python.txt landet in der Befehlszeile
  local re='^[A-Za-z]:\\[^"&|^<>%]+python\.exe$'   # Muster in Variable: bash 3.2 stolpert über Escapes im [[ =~ ]]-Literal
  [[ $p =~ $re ]] || fehler "python.txt fehlt auf $pc oder ist kein python.exe-Pfad ('$p') → agent-aufgabe.ps1 auf dem PC ausführen. $(tr -d '\r' < "$err")" 3
  printf '%s\n' "$p" > "$py_merk"; chmod 600 "$py_merk"
}
[ -s "$py_merk" ] || holen_py
py=$(head -n1 "$py_merk")
# Klickverbot-Absicherung (Gegenprüfung 02.11.2026): Ein PC mit altem Agent führt Klicks ohne Sperre aus. Vor jedem Auftrag mit Eingaben darum eine
# warte-Probe; ohne Feld "stand" im Ergebnis geht nichts raus. foto, tabs, fenster und warte brauchen die Probe nicht.
if EINGABE=$(python3 -c '
import json, sys
print(any(isinstance(a, dict) and a.get("aktion") not in ("foto", "tabs", "fenster", "warte") for a in json.loads(sys.argv[1])["aktionen"]))' "$json") && [ "$EINGABE" = True ]; then
  probe=$(printf '%s' "{\"id\":\"$id-p\",\"aktionen\":[{\"aktion\":\"warte\",\"ms\":1}]}" | base64 | tr -d '\n')
  stand=$("${SSH[@]}" -n "$pc" "\"$py\" \"$AGENT_PY\" $probe 20" 2>"$err" | tr -d '\r' | grep -E '^\{' | tail -n 1 | python3 -c '
import json, sys
try:
    print(json.loads(sys.stdin.readline()).get("stand") or "")
except ValueError:
    print("")')
  [ -n "$stand" ] || fehler "Agent auf $pc hat keinen Stand mit Klickverbot → erst aktualisieren (agent/README.md), nichts gesendet. $(tr -d '\r' < "$err")" 3
fi
# auftrag.py druckt genau eine JSON-Zeile; alles andere (Fehler) geht auf stderr
aus=$("${SSH[@]}" -n "$pc" "\"$py\" \"$AGENT_PY\" $b64 $WARTE" 2>"$err" | tr -d '\r')
rc=${PIPESTATUS[0]}
if [ "$rc" -ne 0 ] && grep -qiE 'nicht gefunden|not recognized|cannot find|No such file' "$err"; then
  # gemerkter Pfad stimmt nicht mehr (Python neu installiert): einmal frisch holen und nochmal
  holen_py; py=$(head -n1 "$py_merk")
  aus=$("${SSH[@]}" -n "$pc" "\"$py\" \"$AGENT_PY\" $b64 $WARTE" 2>"$err" | tr -d '\r')
  rc=${PIPESTATUS[0]}
fi
if [ "$rc" -ne 0 ] || [ -z "$aus" ]; then
  fehler "Kein Ergebnis von $pc (Exit $rc): $(tr -d '\r' < "$err")" 3
fi
erg_json=$(printf '%s\n' "$aus" | grep -E '^\{' | tail -n 1)
[ -n "$erg_json" ] || fehler "Unerwartete Antwort von $pc: $aus" 3
# Erst prüfen (gültiges JSON, id passt), dann ausgeben. Bilder: nur Namen <id>-<n>.png aus dem Ergebnis-Ordner, nie Pfade.
bilder=$(ID="$id" python3 -c '
import json, os, re, sys
try:
    d = json.loads(sys.stdin.readline())
except ValueError as e:
    sys.exit("kein JSON: %s" % e)
if not isinstance(d, dict) or str(d.get("id")) != os.environ["ID"]:
    sys.exit("Antwort gehört nicht zu diesem Auftrag (id %r statt %s)" % (d.get("id") if isinstance(d, dict) else d, os.environ["ID"]))
print("OK" if d.get("ok") is True else "FEHLER")
for b in d.get("bilder") or []:
    if re.fullmatch(os.environ["ID"] + r"-\d+\.png", str(b)): print(b)' <<< "$erg_json") || fehler "Unerwartete Antwort von $pc: $erg_json" 3
echo "$erg_json"
alle_ok=0; status=$(head -n1 <<< "$bilder"); [ "$status" = OK ] || alle_ok=1
for b in $(tail -n +2 <<< "$bilder"); do
  # macOS-scp spricht SFTP; fehlt das Subsystem auf dem PC, zweiter Versuch mit dem alten scp-Protokoll (-O), wie foto.sh
  if "${SCP[@]}" "$pc:C:/mt5-copier/fernzugriff/ergebnisse/$b" "$lokal_dir/$b" 2>>"$err" \
     || "${SCP[@]}" -O "$pc:C:/mt5-copier/fernzugriff/ergebnisse/$b" "$lokal_dir/$b" 2>>"$err"; then
    chmod 600 "$lokal_dir/$b"; echo "BILD $lokal_dir/$b"
  else
    echo "scp von $b fehlgeschlagen: $(tail -n 2 "$err" | tr -d '\r')" >&2; alle_ok=4
  fi
done
rm -f "$err"
python3 -c 'import sys, time; sys.stderr.write("Dauer %.1f s\n" % (time.time() - float(sys.argv[1])))' "$t0"
exit $alle_ok
