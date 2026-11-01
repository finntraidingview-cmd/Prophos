#!/usr/bin/env bash
# mac/foto.sh <pc> [ssh-ziel] — Bildschirmfoto eines Windows-PCs vom Mac holen (01.11.2026, Auftrag FOTO).
# Warum: Finn will nicht mehr per Parsec Screenshots hin- und herkopieren; Claude läuft nur auf dem Mac und soll das
# Foto selbst holen (Tailscale + SSH). Ablauf: per SSH foto.ps1 auf dem PC starten (löst die Aufgabe „Prophos Foto“
# in der angemeldeten Sitzung aus, siehe foto-aufgabe.ps1), den gemeldeten Pfad per scp nach
# ~/Prophos-Fernzugriff/quarantaene/<pc>/ holen und den lokalen Pfad als letzte Zeile ausgeben.
# Nur fotografieren: kein Klick, keine Taste, kein Fokus. Keine Zugangsdaten hier — SSH-Schlüssel und Hosts kommen
# aus derselben Datei wie bei mac/pc.sh (S11): ~/.prophos-fernzugriff/ssh_config, per `ssh -F`, Host = PC-Kennung.
# Notweg: 2. Argument user@ip (dann ohne diese Datei, Schlüssel aus ~/.ssh wie üblich).
#
#   bash pc-fernzugriff/foto/mac/foto.sh pc-7ftp5l
#   bash pc-fernzugriff/foto/mac/foto.sh pc-7ftp5l finn@100.64.1.23
#
# Umgebung (optional): PROPHOS_FOTO_PS1 = Pfad von foto.ps1 auf dem PC (Standard: C:\mt5-copier\fernzugriff\foto\foto.ps1),
# PROPHOS_SSH_CONFIG = andere ssh_config (Standard: ~/.prophos-fernzugriff/ssh_config).
# Exit ≠ 0 mit Grund auf stderr: 2 = Aufruf, 3 = SSH/Skript auf dem PC (dessen Meldung wird durchgereicht), 4 = scp.

set -u
pc="${1:-}"
ziel="${2:-$pc}"
ssh_config="${PROPHOS_SSH_CONFIG:-$HOME/.prophos-fernzugriff/ssh_config}"
ps1="${PROPHOS_FOTO_PS1:-C:\\mt5-copier\\fernzugriff\\foto\\foto.ps1}"

if [[ -z "$pc" || ! "$pc" =~ ^pc-[a-z0-9]{6}$ ]]; then
    echo "Aufruf: $0 <pc-kennung wie pc-7ftp5l> [ssh-ziel]" >&2
    exit 2
fi

# Ohne 2. Argument läuft alles über die gemeinsame ssh_config (-F); mit Notweg user@ip ohne sie.
cfg=()
if [[ -z "${2:-}" ]]; then
    if [[ ! -r "$ssh_config" ]]; then
        echo "Fehlt: $ssh_config (legt mac/pc.sh an) — oder Notweg: $0 $pc user@ip" >&2
        exit 2
    fi
    cfg=(-F "$ssh_config")
fi

lokal_dir="$HOME/Prophos-Fernzugriff/quarantaene/$pc"
mkdir -p "$lokal_dir" && chmod 700 "$HOME/Prophos-Fernzugriff" "$lokal_dir" 2>/dev/null

# BatchMode: nie nach Kennwort fragen (Schlüssel oder nichts). -n: kein stdin. Das Skript gibt genau eine Pfad-Zeile aus.
ssh_opts=(${cfg[@]+"${cfg[@]}"} -n -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=5)
roh="$lokal_dir/.letzte-ausgabe.txt"
ssh "${ssh_opts[@]}" "$ziel" powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "\"$ps1\"" >"$roh" 2>"$lokal_dir/.letzter-fehler.txt"
rc=$?
pfad="$(tr -d '\r' < "$roh" | grep -E '^[A-Za-z]:\\' | tail -n 1)"
rm -f "$roh"
if [[ -z "$pfad" ]]; then
    echo "Kein Foto von $pc (ssh/foto.ps1 Exit $rc): $(tr -d '\r' < "$lokal_dir/.letzter-fehler.txt")" >&2
    exit 3
fi

# Windows-Pfad für scp: Backslashes → Schrägstriche (OpenSSH auf Windows versteht C:/…), damit keine Shell sie schluckt.
pfad_scp="${pfad//\\//}"
name="$(basename "$pfad_scp")"
lokal="$lokal_dir/$name"
# macOS-scp nutzt SFTP; fehlt auf einem PC das sftp-Subsystem, zweiter Versuch mit dem alten scp-Protokoll (-O).
if ! scp -q ${cfg[@]+"${cfg[@]}"} -o BatchMode=yes -o ConnectTimeout=10 "$ziel:$pfad_scp" "$lokal" 2>>"$lokal_dir/.letzter-fehler.txt" \
   && ! scp -q ${cfg[@]+"${cfg[@]}"} -O -o BatchMode=yes -o ConnectTimeout=10 "$ziel:$pfad_scp" "$lokal" 2>>"$lokal_dir/.letzter-fehler.txt"; then
    echo "scp von $pc fehlgeschlagen ($pfad): $(tail -n 3 "$lokal_dir/.letzter-fehler.txt" | tr -d '\r')" >&2
    exit 4
fi
chmod 600 "$lokal"
rm -f "$lokal_dir/.letzter-fehler.txt"
echo "$lokal"
