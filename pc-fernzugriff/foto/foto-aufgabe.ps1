# foto-aufgabe.ps1 — EINMAL je PC ausführen (als der Nutzer, der am Desktop angemeldet ist; lokal oder per SSH).
# Warum (01.11.2026, Auftrag FOTO, Fernzugriff Tailscale + SSH): Eine SSH-Sitzung läuft in Session 0 und sieht den
# Desktop nicht. Das Foto muss in der ANGEMELDETEN Sitzung entstehen. Darum eine geplante Aufgabe „Prophos Foto“, die
# als dieser Nutzer interaktiv läuft („Nur ausführen, wenn der Benutzer angemeldet ist“, kein Kennwort nötig, kein
# Zeitplan) und bei Auslösung foto-schuss.py startet. Ausgelöst wird sie von foto.ps1 (per SSH).
#
# Das Foto macht reines Python (foto-schuss.py, GDI/ctypes wie das Puls-Fehlerfoto in order_bot.py), NICHT PowerShell:
# Windows Defender/AMSI blockte am 29.10.2026 ein CopyFromScreen-Skript als ScriptContainedMaliciousContent.
# Gestartet wird es mit pythonw.exe (GUI-Programm): kein Konsolenfenster, kein Fokuswechsel — nichts stört den Order-Bot.
# Dieses Skript legt nur die Aufgabe an und schreibt keine Skriptdateien.
#
# Anlage wie mt5-update in provision.py: Register-ScheduledTask, Principal = aktueller Nutzer, LogonType Interactive,
# keine höheren Rechte. Wiederholtes Ausführen überschreibt die Aufgabe (-Force). Ablage ausschließlich unter
# C:\mt5-copier\fernzugriff\: Skripte in foto\ (Repo-Kopie, setup-pc.ps1 löscht und kopiert sie bei jedem Setup neu),
# Bilder + fehler.txt in fotos\ daneben, damit sie ein erneutes Setup überleben. Fotos > 7 Tage löscht der Schuss selbst.

$ErrorActionPreference = 'Stop'
$Ordner   = 'C:\mt5-copier\fernzugriff\foto'
$TaskName = 'Prophos Foto'
$Schuss   = Join-Path $Ordner 'foto-schuss.py'

if (-not (Test-Path $Schuss)) { throw "fehlt: $Schuss — Ordner pc-fernzugriff\foto zuerst nach $Ordner kopieren (setup-pc.ps1)." }
New-Item -ItemType Directory -Force -Path 'C:\mt5-copier\fernzugriff\fotos' | Out-Null

# pythonw.exe neben dem python.exe, das auch der Copier nutzt (PATH). Ohne Konsole, darum kein Fenster.
# Den echten Pfad von Python selbst erfragen (sys.executable): Get-Command kann den Microsoft-Store-Stub unter
# \WindowsApps\ liefern — der würde beim Auslösen den Store ÖFFNEN (Fenster in der Sitzung). Review 01.11.2026.
$py = & python.exe -c "import sys; print(sys.executable)" 2>$null
if (-not $py -or $py -like '*\WindowsApps\*' -or -not (Test-Path $py)) {
    throw "echtes python.exe nicht gefunden (PATH: '$py') — Python liegt auf jedem PC für den Copier; Store-Alias abschalten / PATH prüfen."
}
$pyw = Join-Path (Split-Path $py) 'pythonw.exe'
if (-not (Test-Path $pyw)) { throw "pythonw.exe fehlt neben $py" }

$a = New-ScheduledTaskAction -Execute $pyw -Argument ('"' + $Schuss + '"') -WorkingDirectory $Ordner
$p = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -Hidden
# Kein Trigger: die Aufgabe läuft nur, wenn foto.ps1 sie anstößt.
Register-ScheduledTask -TaskName $TaskName -Action $a -Principal $p -Settings $s -Force | Out-Null

Write-Output "Aufgabe '$TaskName' angelegt für $env:USERDOMAIN\$env:USERNAME (nur wenn angemeldet): $pyw $Schuss"
Write-Output "Probe: powershell -NoProfile -ExecutionPolicy Bypass -File $Ordner\foto.ps1"
