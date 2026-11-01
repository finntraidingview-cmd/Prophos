# agent-aufgabe.ps1 — EINMAL je PC ausführen (als der Nutzer, der am Desktop angemeldet ist; lokal oder per SSH).
# Warum (02.11.2026, Auftrag PC-AGENT, Finn: „Ich muss die PCs eigenständig bedienen können … und es muss viel schneller
# gehen“): Eine SSH-Sitzung (Session 0) sieht weder Desktop noch Maus. Darum läuft agent.py DAUERHAFT in der angemeldeten
# Sitzung als geplante Aufgabe „Prophos Agent“: Start bei Anmeldung dieses Nutzers, pythonw.exe (kein Fenster), Neustart
# bei Absturz (3 × im Abstand von 1 min), keine Laufzeitgrenze. Prinzipal wie die Foto-Aufgabe (Interactive, nur wenn
# angemeldet, kein Kennwort). Nach dem Anlegen wird die Aufgabe sofort gestartet.
# Wiederholtes Ausführen: Aufgabe wird ersetzt (-Force) und neu gestartet (der alte Agent beendet sich über den Mutex nicht
# selbst, darum vorher Stop-ScheduledTask). Rückbau: Unregister-ScheduledTask 'Prophos Agent' (S14s rueckbau-pc.ps1).

$ErrorActionPreference = 'Stop'
$Ordner   = 'C:\mt5-copier\fernzugriff\agent'
$TaskName = 'Prophos Agent'
$Agent    = Join-Path $Ordner 'agent.py'

if (-not (Test-Path $Agent)) { throw "fehlt: $Agent — Ordner pc-fernzugriff\agent zuerst nach $Ordner kopieren (setup-pc.ps1)." }
if (-not (Test-Path 'C:\mt5-copier\fernzugriff\foto\foto-schuss.py')) { throw "fehlt: fernzugriff\foto\foto-schuss.py (der Agent importiert daraus das Foto)." }
foreach ($u in 'auftraege', 'ergebnisse') { New-Item -ItemType Directory -Force -Path (Join-Path 'C:\mt5-copier\fernzugriff' $u) | Out-Null }

# Echtes Python wie in foto-aufgabe.ps1 (sys.executable; Store-Stub unter \WindowsApps\ würde den Store öffnen).
$py = & python.exe -c "import sys; print(sys.executable)" 2>$null
if (-not $py -or $py -like '*\WindowsApps\*' -or -not (Test-Path $py)) {
    throw "echtes python.exe nicht gefunden (PATH: '$py') — Python liegt auf jedem PC für den Copier; Store-Alias abschalten / PATH prüfen."
}
$pyw = Join-Path (Split-Path $py) 'pythonw.exe'
if (-not (Test-Path $pyw)) { throw "pythonw.exe fehlt neben $py" }
# Für do.sh am Mac: denselben python.exe-Pfad ablegen (Prüfer S9: „python“ ohne Pfad könnte in der SSH-Sitzung der Store-Stub sein).
[IO.File]::WriteAllText('C:\mt5-copier\fernzugriff\python.txt', $py, (New-Object Text.UTF8Encoding $false))

$alt = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($alt) { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500 }

$a = New-ScheduledTaskAction -Execute $pyw -Argument ('"' + $Agent + '"') -WorkingDirectory $Ordner
$t = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$p = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -Hidden
Register-ScheduledTask -TaskName $TaskName -Action $a -Trigger $t -Principal $p -Settings $s -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 2
$info = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Output "Aufgabe '$TaskName' angelegt für $env:USERDOMAIN\$env:USERNAME (bei Anmeldung, Neustart bei Absturz): $pyw $Agent"
Write-Output "Stand: $((Get-ScheduledTask -TaskName $TaskName).State), letzter Lauf $($info.LastRunTime), Ergebnis $($info.LastTaskResult)"
Write-Output "Probe vom Mac: bash pc-fernzugriff/mac/do.sh <pc> '{\"aktionen\":[{\"aktion\":\"fenster\"},{\"aktion\":\"foto\"}]}'"
