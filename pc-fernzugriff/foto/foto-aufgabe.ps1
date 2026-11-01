# foto-aufgabe.ps1 — EINMAL je PC ausführen (als der angemeldete Nutzer, lokal oder per SSH).
# Warum (01.11.2026, Auftrag FOTO, Fernzugriff Tailscale + SSH): Eine SSH-Sitzung läuft in Session 0 und sieht den
# Desktop nicht, BitBlt liefert dort Schwarz oder scheitert. Das Foto muss in der ANGEMELDETEN Sitzung entstehen.
# Lösung: eine geplante Aufgabe „Prophos Foto“, die als dieser Nutzer interaktiv läuft („Nur ausführen, wenn der
# Benutzer angemeldet ist“, kein Kennwort nötig) und bei Auslösung ein PNG aller Monitore nach
# C:\mt5-copier\fotos\<JJJJMMTT-hhmmss>.png schreibt. Ausgelöst wird sie von foto.ps1 (per SSH), nie nach Zeitplan.
#
# Harte Regel: NUR fotografieren. Kein Klick, keine Taste, kein Fokuswechsel, kein Fenster im Vordergrund.
# Darum startet die Aufgabe nicht powershell.exe direkt (Konsolenfenster blitzt auf und kann Chrome den Fokus
# nehmen), sondern wscript.exe mit einem winzigen VBS, das PowerShell von Anfang an unsichtbar (Fensterstil 0)
# startet. Derselbe Weg wie das Puls-Fehlerfoto in order_bot.py (GDI/BitBlt → PNG), nur in .NET statt ctypes,
# damit das Foto nicht am Bot und nicht an Python hängt.
#
# Anlage (wie mt5-update in provision.py): Register-ScheduledTask, Principal = aktueller Nutzer, LogonType Interactive.
# Keine höheren Rechte nötig. Wiederholtes Ausführen überschreibt die Aufgabe (-Force).
# Aufräumen: der Schuss löscht Fotos älter als 7 Tage selbst.

$ErrorActionPreference = 'Stop'
$Ordner   = 'C:\mt5-copier\fotos'
$TaskName = 'Prophos Foto'

New-Item -ItemType Directory -Force -Path $Ordner | Out-Null

# ── 1. Der Schuss (läuft später in der angemeldeten Sitzung, unsichtbar) ─────────────────────────────────────
$Schuss = @'
# foto-schuss.ps1 — wird von der Aufgabe „Prophos Foto“ gestartet (01.11.2026). Nur lesen: BitBlt aller Monitore → PNG.
$ErrorActionPreference = 'Stop'
$Ordner = 'C:\mt5-copier\fotos'
$Fehler = Join-Path $Ordner 'fehler.txt'
try {
    Add-Type -AssemblyName System.Drawing
    Add-Type -AssemblyName System.Windows.Forms
    # Kein Add-Type -MemberDefinition (würde je Schuss csc.exe anwerfen, 1–3 s): powershell.exe ist laut Manifest selbst
    # DPI-bewusst, VirtualScreen liefert echte Pixel. Review 01.11.2026: die 10 s von foto.ps1 nicht an Kompilierung verlieren.

    $vs = [System.Windows.Forms.SystemInformation]::VirtualScreen      # alle Monitore als ein Rechteck
    if ($vs.Width -le 0 -or $vs.Height -le 0) { throw "kein Bildschirm (VirtualScreen $($vs.Width)x$($vs.Height))" }
    $bmp = New-Object System.Drawing.Bitmap $vs.Width, $vs.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    try {
        $g.CopyFromScreen($vs.Left, $vs.Top, 0, 0, $bmp.Size)         # BitBlt, kein Fokus, kein Eingriff
    } finally { $g.Dispose() }

    $name = (Get-Date).ToString('yyyyMMdd-HHmmss')
    $tmp  = Join-Path $Ordner "$name.tmp"
    $png  = Join-Path $Ordner "$name.png"
    $bmp.Save($tmp, [System.Drawing.Imaging.ImageFormat]::Png)          # erst .tmp, dann umbenennen: foto.ps1 sieht nur fertige Bilder
    $bmp.Dispose()
    Move-Item -Force $tmp $png
    if (Test-Path $Fehler) { Remove-Item -Force $Fehler }

    # Alte Fotos nach 7 Tagen weg (Auftrag), Reste von abgebrochenen Schüssen gleich mit.
    Get-ChildItem $Ordner -Filter '*.png' | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem $Ordner -Filter '*.tmp' | Where-Object { $_.LastWriteTime -lt (Get-Date).AddMinutes(-5) } | Remove-Item -Force -ErrorAction SilentlyContinue
} catch {
    # Typisch: Sperrbildschirm / UAC-Desktop (Win32Exception bei CopyFromScreen). Grund für foto.ps1 ablegen, nie ein Fenster.
    "$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss')) $($_.Exception.Message)" | Set-Content -Path $Fehler -Encoding UTF8
    exit 1
}
'@
Set-Content -Path (Join-Path $Ordner 'foto-schuss.ps1') -Value $Schuss -Encoding UTF8

# ── 2. Unsichtbarer Starter (wscript ist ein GUI-Programm: kein Konsolenfenster, kein Fokus) ──────────────────
$Vbs = @'
' foto-start.vbs — startet foto-schuss.ps1 ohne Fenster (Fensterstil 0), 01.11.2026. Nur Foto, nie Eingaben.
CreateObject("WScript.Shell").Run "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File ""C:\mt5-copier\fotos\foto-schuss.ps1""", 0, False
'@
Set-Content -Path (Join-Path $Ordner 'foto-start.vbs') -Value $Vbs -Encoding ASCII

# ── 3. Die Aufgabe ──────────────────────────────────────────────────────────────────────────────────────────
$a = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\wscript.exe" -Argument ('//B //Nologo "' + (Join-Path $Ordner 'foto-start.vbs') + '"')
$p = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -Hidden
# Kein Trigger: die Aufgabe läuft nur, wenn foto.ps1 sie anstößt.
Register-ScheduledTask -TaskName $TaskName -Action $a -Principal $p -Settings $s -Force | Out-Null

Write-Output "Aufgabe '$TaskName' angelegt für $env:USERDOMAIN\$env:USERNAME (nur wenn angemeldet). Fotos: $Ordner"
Write-Output "Probe: powershell -NoProfile -ExecutionPolicy Bypass -File <pfad>\foto.ps1"
