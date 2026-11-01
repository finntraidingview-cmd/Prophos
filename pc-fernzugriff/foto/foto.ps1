# foto.ps1 — per SSH vom Mac aufgerufen (01.11.2026, Auftrag FOTO): stößt die Aufgabe „Prophos Foto“ an, wartet bis zu
# 10 s auf das neue PNG in C:\mt5-copier\fotos und gibt dessen Pfad als EINZIGE stdout-Zeile aus (mac/foto.sh liest sie).
# Warum über die Aufgabe: diese SSH-Sitzung sitzt in Session 0 und sieht den Desktop nicht; die Aufgabe läuft in der
# angemeldeten Sitzung (Anlage: foto-aufgabe.ps1). Hier wird nichts geklickt, nichts fokussiert, nichts beendet.
# Exit 0 = Pfad steht da. Exit 2 = Aufgabe fehlt (foto-aufgabe.ps1 ausführen). Exit 3 = kein Bild in 10 s (Grund aus
# fehler.txt, falls der Schuss einen hinterließ; sonst meist: niemand angemeldet / Sperrbildschirm / Aufgabe lief nicht).

$ErrorActionPreference = 'Stop'
$Ordner   = 'C:\mt5-copier\fotos'
$TaskName = 'Prophos Foto'
$WarteS   = 10

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
    [Console]::Error.WriteLine("Aufgabe '$TaskName' fehlt — erst foto-aufgabe.ps1 als angemeldeter Nutzer ausführen.")
    exit 2
}

New-Item -ItemType Directory -Force -Path $Ordner | Out-Null
$Fehler = Join-Path $Ordner 'fehler.txt'
if (Test-Path $Fehler) { Remove-Item -Force $Fehler -ErrorAction SilentlyContinue }
$start = Get-Date
$schon = @(Get-ChildItem $Ordner -Filter '*.png' | ForEach-Object { $_.Name })   # was es vor dem Anstoß schon gab

try { Start-ScheduledTask -TaskName $TaskName } catch {
    [Console]::Error.WriteLine("Aufgabe '$TaskName' ließ sich nicht starten: $($_.Exception.Message)")
    exit 3
}

$ende = $start.AddSeconds($WarteS)
while ((Get-Date) -lt $ende) {
    Start-Sleep -Milliseconds 300
    $neu = Get-ChildItem $Ordner -Filter '*.png' |
           Where-Object { $schon -notcontains $_.Name -and $_.LastWriteTime -ge $start.AddSeconds(-2) } |
           Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($neu) {
        Write-Output $neu.FullName
        exit 0
    }
    if (Test-Path $Fehler) { break }
}

$grund = if (Test-Path $Fehler) { (Get-Content $Fehler -Raw).Trim() } else {
    $info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
    "kein Bild nach $WarteS s (Aufgabe: Status $((Get-ScheduledTask -TaskName $TaskName).State), letzter Lauf $($info.LastRunTime), Ergebnis $($info.LastTaskResult)). " +
    "Meist: niemand angemeldet, Sperrbildschirm oder Nutzer der Aufgabe ≠ angemeldeter Nutzer."
}
[Console]::Error.WriteLine("Kein Foto: $grund")
exit 3
