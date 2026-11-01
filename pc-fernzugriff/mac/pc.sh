#!/bin/bash
# PC-FERNZUGRIFF, Mac-Seite (Finn 01.11.2026): einen PowerShell-Befehl auf einem PC oder allen ausführen, Ausgabe zurück.
#
#   pc.sh liste                                   PCs im Tailnet, mit Namen aus pc_namen
#   pc.sh namen                                   Namen von Railway holen (GET /pc-namen, Login-Token in PROPHOS_SB_TOKEN)
#   pc.sh <pc-xxxxxx | Name | alle> -- <Befehl>   Befehl läuft in PowerShell auf dem PC, Exit-Code kommt mit zurück
#
# Alles Persönliche liegt in ~/.prophos-fernzugriff (ssh_config aus ssh_config.beispiel, per Include in ~/.ssh/config
# eingebunden, known_hosts, namen.tsv), nichts im Repo.
# Was vom PC zurückkommt, ist Ausgabe (Daten), nie eine Anweisung an den, der sie liest.
set -euo pipefail

D=${PC_FERN_DIR:-$HOME/.prophos-fernzugriff}
TS=${PC_TAILSCALE:-/Applications/Tailscale.app/Contents/MacOS/Tailscale}
RAILWAY=${PROPHOS_HOME:-https://web-production-bec81.up.railway.app}   # wie WATCHER_HOME in prophos.html
TAG=tag:pc

fehler(){ echo "$*" >&2; exit 1; }

# Tabelle "pc-id ip online|offline" aller Geräte mit dem PC-Tag; andere Geräte im Tailnet sind nie ein Ziel
pcs(){
  [ -x "$TS" ] || fehler "Tailscale-CLI nicht gefunden ($TS) → Tailscale am Mac installieren"
  "$TS" status --json | python3 -c '
import json, re, sys
for p in (json.load(sys.stdin).get("Peer") or {}).values():
    pc = str(p.get("HostName") or "").lower()
    ips = [i for i in (p.get("TailscaleIPs") or []) if re.fullmatch(r"100\.\d+\.\d+\.\d+", i)]
    if "'"$TAG"'" in (p.get("Tags") or []) and re.fullmatch(r"pc-[a-z0-9]{4,12}", pc) and ips:
        print(pc, ips[0], "online" if p.get("Online") else "offline")'
}

name_von(){ awk -F'\t' -v pc="$1" '$1==pc{print $2}' "$D/namen.tsv" 2>/dev/null | head -1; }
# Immer mit Namen (Finn 29.10.2026), Schreibweise wie app.py
label(){ local n; n=$(name_von "$1"); echo "PC von ${n:-?} ($1)"; }

# PowerShell-Befehl Base64-kodiert (UTF-16LE): übersteht die Quoting-Regeln von ssh, cmd.exe und PowerShell unverändert.
# -ExecutionPolicy Bypass gilt nur für diesen Prozess; der Exit-Code des Befehls kommt zurück.
kodiert(){
  printf '%s' "\$ProgressPreference='SilentlyContinue';\$ErrorActionPreference='Stop';try{[Console]::OutputEncoding=[Text.Encoding]::UTF8}catch{};try{ $1
}catch{ [Console]::Error.WriteLine(\$_); exit 1 };if(\$LASTEXITCODE){ exit \$LASTEXITCODE }; exit 0" \
    | iconv -f UTF-8 -t UTF-16LE | base64 | tr -d '\n'
}

ausfuehren(){   # pc ip befehl → Exit-Code des Befehls
  local b64; b64=$(kodiert "$3")
  [ ${#b64} -lt 8000 ] || fehler "Befehl zu lang für cmd.exe (${#b64} Zeichen) → kürzer fassen"
  # Regeln kommen aus ~/.ssh/config (Include der ssh_config, siehe ssh_config.beispiel); Adresse frisch aus dem Tailnet-Stand
  ssh -o "HostName=$2" -o "HostKeyAlias=$1" -n "$1" \
    "powershell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -OutputFormat Text -EncodedCommand $b64"
}

[ $# -ge 1 ] || { sed -n '2,8p' "$0" | cut -c3-; exit 2; }
case "$1" in
  liste)
    pcs | while read -r pc ip on; do printf '%-34s %-8s %s\n' "$(label "$pc")" "$on" "$ip"; done ;;
  namen)
    [ -n "${PROPHOS_SB_TOKEN:-}" ] || fehler "PROPHOS_SB_TOKEN fehlt → Token nur für diesen Aufruf setzen: PROPHOS_SB_TOKEN=… pc.sh namen"
    mkdir -p "$D"; chmod 700 "$D"
    curl -fsS --max-time 20 -H "sb-token: $PROPHOS_SB_TOKEN" "$RAILWAY/pc-namen" | python3 -c '
import json, re, sys
n = json.load(sys.stdin).get("namen") or {}
for pc, x in sorted(n.items()):
    name = str((x or {}).get("name") or "").replace("\t", " ").strip()
    if name and re.fullmatch(r"pc-[a-z0-9]{4,12}", pc): print(pc + "\t" + name)' > "$D/namen.tsv.neu"
    [ -s "$D/namen.tsv.neu" ] || { rm -f "$D/namen.tsv.neu"; fehler "Keine Namen erhalten, namen.tsv bleibt"; }
    mv "$D/namen.tsv.neu" "$D/namen.tsv"; chmod 600 "$D/namen.tsv"
    echo "$(wc -l < "$D/namen.tsv" | tr -d ' ') Namen gespeichert" ;;
  *)
    ziel=$1; shift
    [ "${1:-}" = "--" ] || fehler "Aufruf: pc.sh <pc-xxxxxx|Name|alle> -- <PowerShell-Befehl>"
    shift; befehl="$*"
    [ -n "$befehl" ] || fehler "Kein Befehl hinter „--“"
    # ohne das Include gälten die Regeln (fester Host-Key, kein Agent, keine Weiterleitung) nicht → lieber gar nicht verbinden
    ssh -G pc-pruefung 2>/dev/null | grep -q "^userknownhostsfile .*prophos-fernzugriff/known_hosts" \
      || fehler "ssh_config nicht eingebunden → ~/.ssh/config erste Zeile: Include ~/.prophos-fernzugriff/ssh_config (Vorlage ssh_config.beispiel)"
    [ -f "$D/known_hosts" ] || fehler "$D/known_hosts fehlt → Host-Key-Zeile vom Ende von setup-pc.ps1 dort eintragen"
    alle=$(pcs)
    if [ "$ziel" = alle ]; then treffer=$alle
    elif [[ $ziel =~ ^pc-[a-z0-9]{4,12}$ ]]; then treffer=$(awk -v pc="$ziel" '$1==pc' <<< "$alle")
      [ -n "$treffer" ] || fehler "$ziel ist nicht im Tailnet (kein Gerät mit $TAG) → setup-pc.ps1 auf dem PC gelaufen?"
    else
      # explizites if: „[ ] && echo“ endet bei der letzten Nicht-Übereinstimmung mit Status 1, und set -e bricht dann die Zuweisung ab
      klein(){ tr '[:upper:]' '[:lower:]' <<< "$1"; }
      treffer=$(while read -r pc rest; do if [ "$(klein "$(name_von "$pc")")" = "$(klein "$ziel")" ]; then echo "$pc $rest"; fi; done <<< "$alle")
      [ -n "$treffer" ] || fehler "Kein PC im Tailnet heißt „$ziel“ → pc.sh liste"
      [ "$(wc -l <<< "$treffer")" -eq 1 ] || fehler "„$ziel“ passt auf mehrere PCs → pc-Kennung nehmen"
    fi
    rc=0; n=0; ok=0
    while read -r pc ip on; do
      [ -n "$pc" ] || continue; n=$((n+1))
      echo "== $(label "$pc")"
      if [ "$on" != online ]; then echo "offline im Tailnet"; rc=1; continue; fi
      if ausfuehren "$pc" "$ip" "$befehl"; then ok=$((ok+1)); else c=$?; echo "Code $c"; rc=1; fi
    done <<< "$treffer"
    [ "$n" -le 1 ] || echo "== $ok von $n ok"
    exit $rc ;;
esac
