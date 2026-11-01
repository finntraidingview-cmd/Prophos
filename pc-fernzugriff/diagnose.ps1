<#
  diagnose.ps1 — Puls-Fehler an einem Windows-PC in EINEM Lauf einsammeln (01.11.2026, Slave 15).

  WARUM: Bei einem Puls-Fehler musste Finn bisher per Parsec auf den PC, Befehle von Hand kopieren und Bildschirme
  abtippen. Dieses Skript läuft per SSH (Tailscale) vom Mac aus und gibt als Text alles aus, was Claude zum Verstehen
  braucht: Stand des Codes, laufende Prozesse, Ports, Spuren und Logs, Platz, Uptime, Zeit, Tailscale.

  REGELN:
  · Nur lesen. Es ändert nichts, startet nichts, klickt nichts, installiert nichts.
  · Zugangsdaten nie ausgeben: code_token.txt, feed_token.txt, .env, plans.json, config*.json (cred_* vorsorglich) werden nur als
    „vorhanden, N Bytes, geändert am" gelistet. Jede Ausgabezeile läuft zusätzlich durch Maskieren() (Schlüssel-Muster,
    JWTs, password=…), falls so etwas je in einer Kommandozeile oder einem Log auftaucht.
  · Prozess-Erkennung nie über wmic (fehlt auf Windows 11 24H2+): Get-CimInstance Win32_Process.
  · Copier, Panel, Backend und Order-Bot schreiben KEINE Logdatei, nur in ihr Konsolenfenster (copier.py log() = print,
    panel.py/order_bot.py print(flush=True)). Lesbar sind: fehlerfoto.log, die Spur-Dateien (augen_*.json, puls_*.json,
    status*.json), polar/<lauf>/*.log, ProgramData\Prophos\mt5-update\mt5-update.log und die MT5-Journale (<Daten>\logs\JJJJMMTT.log).

  AUFRUF vom Mac (Datei liegt nicht im Code-Weg der PCs, /code/datei liefert nur app.py, prophos.html, sw.js, requirements.txt, mt5-copier/* und tv-reader/*; also einmal hinkopieren):
    scp pc-fernzugriff/diagnose.ps1 <pc>:C:/Prophos/diagnose.ps1
    ssh <pc> powershell -NoProfile -ExecutionPolicy Bypass -File C:/Prophos/diagnose.ps1 [-Kurz] [-Ordner C:\mt5-copier] [-LogZeilen 60]
  -Kurz = nur die ersten 20 Zeilen (die Kurzlage). Ohne Schalter folgen Prozesse, Dateien, Spuren, Logs, Journale, Aufgaben.
  STAND 01.11.2026: auf dem Mac gibt es kein PowerShell — das Skript ist NICHT gelaufen. Pilot auf einem PC macht Finn.
#>
[CmdletBinding()]
param(
    [switch]$Kurz,
    [string]$Ordner = 'C:\mt5-copier',
    [int]$LogZeilen = 60
)

$ErrorActionPreference = 'SilentlyContinue'
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$Z = New-Object System.Collections.Generic.List[string]
$Jetzt = Get-Date

# ── Maskieren: Geheimnis-Muster in JEDER Zeile unkenntlich machen, egal woher sie kommt ───────────────────────────
function Maskieren([string]$s) {
    if (-not $s) { return $s }
    $s = [regex]::Replace($s, '[0-9a-f-]{36}\.(pc-[a-z0-9]{4,12}|host-[a-z0-9-]{1,30})\.[0-9a-f]{40}', '<PC-SCHLUESSEL>')   # code_token / feed_token
    $s = [regex]::Replace($s, 'eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}', '<JWT>')                    # Supabase/TSX-JWTs
    $s = [regex]::Replace($s, 'sb_(publishable|secret)_[A-Za-z0-9_-]{6,}', '<SB-KEY>')
    $s = [regex]::Replace($s, '(?i)(password|passwort|pass|pwd|token|secret|apikey|api_key)["'']?\s*[=:]\s*["'']?\S+', '$1=<WEG>')   # auch JSON-Form "token": "x" (S9 01.11.2026)
    $s = [regex]::Replace($s, '(?i)Bearer\s+\S+', 'Bearer <WEG>')
    return $s
}
function Z([string]$s) { foreach ($t in ($s -split "`r?`n")) { $Z.Add((Maskieren $t)) } }
function Kopf([string]$s) { $Z.Add(''); $Z.Add(('── ' + $s + ' ' + ('─' * [Math]::Max(0, 90 - $s.Length)))) }
function Dt($d) { if ($d) { try { return ([datetime]$d).ToString('dd.MM. HH:mm:ss') } catch { return "$d" } } else { return '?' } }
function DateiInfo([string]$p) {
    if (Test-Path -LiteralPath $p) { $f = Get-Item -LiteralPath $p; return ('vorhanden, {0} Bytes, geändert {1}' -f $f.Length, (Dt $f.LastWriteTime)) }
    return 'fehlt'
}
function LetzteZeilen([string]$p, [int]$n) {
    if (-not (Test-Path -LiteralPath $p)) { return @("(fehlt: $p)") }
    try {
        $raw = [System.IO.File]::ReadAllBytes($p)
        if ($raw.Length -ge 2 -and $raw[0] -eq 0xFF -and $raw[1] -eq 0xFE) { $txt = [System.Text.Encoding]::Unicode.GetString($raw) }   # MT5-Journale sind UTF-16
        else { $txt = [System.Text.Encoding]::UTF8.GetString($raw) }
        $zeilen = $txt -split "`r?`n" | Where-Object { $_ -ne '' }
        if ($zeilen.Count -gt $n) { $zeilen = $zeilen[($zeilen.Count - $n)..($zeilen.Count - 1)] }
        return $zeilen
    } catch { return @("(nicht lesbar: $($_.Exception.Message))") }
}
function Kompakt([string]$p, [int]$max = 700) {
    # Kleine Spur-/Status-JSONs in einer Zeile, gekürzt (sie enthalten keine Zugangsdaten; Maskieren läuft trotzdem drüber).
    if (-not (Test-Path -LiteralPath $p)) { return 'fehlt' }
    $t = (Get-Content -LiteralPath $p -Raw -Encoding UTF8) -replace '\s+', ' '
    if ($t.Length -gt $max) { $t = $t.Substring(0, $max) + ' …' }
    return ('[{0}] {1}' -f (Dt (Get-Item -LiteralPath $p).LastWriteTime), $t)
}

# ── Grunddaten ────────────────────────────────────────────────────────────────────────────────────────────────────
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
$boot = $os.LastBootUpTime
$uptime = if ($boot) { $Jetzt - $boot } else { $null }
$anzeigeVersion = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').DisplayVersion
$pcId = '?'
try { $pcId = ((Get-Content -LiteralPath (Join-Path $Ordner 'pc_id.json') -Raw) | ConvertFrom-Json).pc_id } catch { }
if (-not $pcId) { $pcId = '?' }
$wmic = if (Get-Command wmic.exe -ErrorAction SilentlyContinue) { 'da' } else { 'FEHLT (24H2+ normal)' }

# Version im Ordner
$version = '?'; try { $version = (Get-Content -LiteralPath (Join-Path $Ordner 'VERSION') -TotalCount 1).Trim() } catch { }
$tabBuild = '?'
try {
    $m = Select-String -LiteralPath (Join-Path $Ordner 'prophos.html') -Pattern "OS_TAB_BUILD = '([0-9.-]+)'" | Select-Object -First 1
    if ($m) { $tabBuild = $m.Matches[0].Groups[1].Value }
} catch { }
$readerOrdner = @('C:\tv-reader', 'C:\Prophos\tv-reader', (Join-Path (Split-Path -Parent $Ordner) 'tv-reader')) | Where-Object { Test-Path -LiteralPath (Join-Path $_ 'reader-server.py') } | Select-Object -First 1
$readerVersion = '-'; $userscriptVersion = '-'
if ($readerOrdner) {
    $m = Select-String -LiteralPath (Join-Path $readerOrdner 'reader-server.py') -Pattern 'READER_VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($m) { $readerVersion = $m.Matches[0].Groups[1].Value }
    $us = Join-Path $readerOrdner 'tv-reader.user.js'
    if (Test-Path -LiteralPath $us) { $m = Select-String -LiteralPath $us -Pattern '@version\s+(\S+)' | Select-Object -First 1; if ($m) { $userscriptVersion = $m.Matches[0].Groups[1].Value } }
}

# Prozesse (ohne wmic)
$procs = Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw|chrome|terminal64|cmd|tailscaled|tailscale-ipn|parsecd)\.exe$' }
function ProzZeile($p) {
    $cl = [string]$p.CommandLine
    $kurz = switch -Regex ($p.Name) {
        '^python' {
            $skript = if ($cl -match '([A-Za-z0-9_\-]+\.py)') { $Matches[1] } else { '(ohne Skript)' }
            $extra = if ($cl -match 'order_bot\.py\s+"?([A-Za-z0-9_\-]+\.json)') { ' ' + $Matches[1] } else { '' }   # welche Config, nie der Befehls-JSON
            ($skript + $extra)
        }
        '^chrome' {
            if ($cl -match '--type=') { return $null }                                       # Renderer/GPU-Kinder weglassen
            $prof = if ($cl -match '--user-data-dir="?([^" ]+)') { Split-Path -Leaf $Matches[1] } else { 'Standardprofil' }
            $cdp = if ($cl -match '--remote-debugging-port=(\d+)') { ' CDP:' + $Matches[1] } else { '' }
            ('Profil ' + $prof + $cdp)
        }
        '^terminal64' { if ($cl -match '"?([A-Za-z]:\\[^"]*?)\\terminal64\.exe') { $Matches[1] } else { $p.ExecutablePath } }
        '^cmd' { if ($cl -match '([A-Za-z0-9_\-]+\.bat)') { $Matches[1] } else { return $null } }   # nur Starter-Fenster
        default { '' }
    }
    if ($null -eq $kurz) { return $null }
    $ws = [math]::Round($p.WorkingSetSize / 1MB)
    return ('{0,-14} PID {1,-6} seit {2}  {3,5} MB  {4}' -f $p.Name, $p.ProcessId, (Dt $p.CreationDate), $ws, ($kurz -join ' '))
}
$prozZeilen = @($procs | ForEach-Object { ProzZeile $_ } | Where-Object { $_ })

# Ports (Get-NetTCPConnection, Rückfall netstat)
function PortHalter([int]$port) {
    $c = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) { $pp = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue; return ('belegt (PID {0} {1})' -f $c.OwningProcess, $(if ($pp) { $pp.ProcessName } else { '?' })) }
    $n = netstat -ano 2>$null | Select-String (":$port\s") | Select-String 'ABH|LISTEN' | Select-Object -First 1
    if ($n) { return ('belegt (netstat: PID ' + (($n.Line -split '\s+')[-1]) + ')') }
    return 'FREI'
}
$ports = [ordered]@{ '5000' = 'Backend app.py'; '8770' = 'Panel'; '8790' = 'TV-Reader'; '9333' = 'Puls-Chrome CDP' }   # Text-Schlüssel: bei [ordered] wäre eine Zahl ein Index

# Platz, Zeit, Tailscale
$c = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$frei = if ($c) { ('{0:N1} GB frei von {1:N0} GB' -f ($c.FreeSpace / 1GB), ($c.Size / 1GB)) } else { '?' }
$utcAbw = 'nicht messbar'
try {
    $w = w32tm /stripchart /computer:time.windows.com /samples:1 /dataonly 2>$null | Select-String -Pattern ',\s*([+-]\d+\.\d+)s' | Select-Object -Last 1
    if ($w) { $utcAbw = ('{0}s gegen time.windows.com' -f $w.Matches[0].Groups[1].Value) }
} catch { }
$tz = (Get-TimeZone).Id
$ts = 'nicht installiert'
$tsExe = @('C:\Program Files\Tailscale\tailscale.exe', "$env:LOCALAPPDATA\Tailscale\tailscale.exe") | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if ($tsExe) {
    $ip = (& $tsExe ip -4 2>$null | Select-Object -First 1)
    $st = (& $tsExe status --self --peers=false 2>$null | Select-Object -First 1)
    $ts = ('{0} · {1}' -f $(if ($ip) { $ip } else { 'ohne IP' }), $(if ($st) { ($st -replace '\s+', ' ') } else { 'status ohne Antwort' }))
}
$sshd = Get-Service sshd -ErrorAction SilentlyContinue

# Geheimnis-Dateien: nur Metadaten
$geheim = @('code_token.txt', '.env', 'plans.json', 'pc_id.json', 'prophos-login.ini') + @(Get-ChildItem -LiteralPath $Ordner -Filter 'cred_*' -Name) + @(Get-ChildItem -LiteralPath $Ordner -Filter 'config*.json' -Name)
if ($readerOrdner) { $geheimReader = @('feed_token.txt', 'positions.json', 'feed_tabs.json') } else { $geheimReader = @() }
$geheimDa = @($geheim | Where-Object { Test-Path -LiteralPath (Join-Path $Ordner $_) })

# ── KURZLAGE (genau 20 Zeilen, das ist die Ausgabe von -Kurz) ────────────────────────────────────────────────────
Z (('PC {0} · {1} · {2} lokal ({3}) · {4} UTC' -f $pcId, $cs.Name, $Jetzt.ToString('dd.MM.yyyy HH:mm:ss'), $tz, $Jetzt.ToUniversalTime().ToString('HH:mm:ss')))
Z (('Windows {0} {1} Build {2} · wmic {3}' -f ($os.Caption -replace 'Microsoft ', ''), $anzeigeVersion, $os.BuildNumber, $wmic))
Z (('Uptime {0} · letzter Start {1}' -f $(if ($uptime) { '{0}d {1:D2}:{2:D2}' -f $uptime.Days, $uptime.Hours, $uptime.Minutes } else { '?' }), (Dt $boot)))
Z (('Zeitabweichung {0} · Platz C: {1}' -f $utcAbw, $frei))
Z (('Tailscale {0} · sshd {1}' -f $ts, $(if ($sshd) { $sshd.Status } else { 'kein Dienst' })))
Z (('VERSION {0} · OS_TAB_BUILD (lokale prophos.html) {1} · Reader {2} · Userscript {3} · Ordner {4}' -f $version, $tabBuild, $readerVersion, $userscriptVersion, $Ordner))
$py = @($prozZeilen | Where-Object { $_ -match '^python' })
Z (('Python-Prozesse {0}: {1}' -f $py.Count, (($py | ForEach-Object { ($_ -split '\s{2,}')[-1] }) -join ', ')))
Z (('Chrome-Hauptprozesse {0}: {1}' -f @($prozZeilen | Where-Object { $_ -match '^chrome' }).Count, ((@($prozZeilen | Where-Object { $_ -match '^chrome' }) | ForEach-Object { ($_ -split '\s{2,}')[-1] }) -join ', ')))
$mt = @($prozZeilen | Where-Object { $_ -match '^terminal64' })
Z (('MT5-Terminals {0}: {1}' -f $mt.Count, (($mt | ForEach-Object { ($_ -split '\s{2,}')[-1] }) -join ', ')))
Z (('Ports: ' + (($ports.Keys | ForEach-Object { '{0} {1} = {2}' -f $_, $ports[$_], (PortHalter ([int]$_)) }) -join ' · ')))
Z (('Geheimnis-Dateien im Ordner (nur Namen): {0}' -f $(if ($geheimDa) { $geheimDa -join ', ' } else { 'keine' })))
Z (('Spur: augen_regel.json {0} · augen_stand.json {1}' -f (DateiInfo (Join-Path $Ordner 'augen_regel.json')), (DateiInfo (Join-Path $Ordner 'augen_stand.json'))))
Z (('Spur: puls_fenster.json {0} · puls_handlauf.lock {1}' -f (DateiInfo (Join-Path $Ordner 'puls_fenster.json')), (DateiInfo (Join-Path $Ordner 'puls_handlauf.lock'))))
Z (('Echo-Pause (echo_pause.flag): {0} · MT5-Update abgelehnt: {1}' -f (DateiInfo (Join-Path $Ordner 'echo_pause.flag')), (DateiInfo (Join-Path $Ordner '.mt5-update-abgelehnt'))))
$warte = Join-Path $Ordner 'fehlerfoto_warte'
Z (('Fehlerfotos wartend: {0} · fehlerfoto.log {1}' -f $(if (Test-Path -LiteralPath $warte) { @(Get-ChildItem -LiteralPath $warte -File).Count } else { 'kein Ordner' }), (DateiInfo (Join-Path $Ordner 'fehlerfoto.log'))))
$prev = @(Get-ChildItem -LiteralPath $Ordner -Filter '*.prev' | Sort-Object LastWriteTime -Descending | Select-Object -First 3 | ForEach-Object { '{0} {1}' -f $_.Name, (Dt $_.LastWriteTime) })
Z (('Letzte Selbst-Updates (*.prev): {0}' -f $(if ($prev) { $prev -join ' · ' } else { 'keine' })))
$halb = @(Get-ChildItem -LiteralPath $Ordner -File | Where-Object { $_.Extension -match '^\.(newp|newc|newb|newa|newh|tmp)$' } | ForEach-Object { $_.Name })
Z (('Halbe Downloads (*.new?, *.tmp): {0}' -f $(if ($halb) { $halb -join ', ' } else { 'keine' })))
$ev = Get-WinEvent -FilterHashtable @{ LogName = 'System'; Id = 41, 1074, 6005, 6006, 6008 } -MaxEvents 3 -ErrorAction SilentlyContinue
Z (('Letzte Start/Stopp-Ereignisse: {0}' -f $(if ($ev) { (($ev | ForEach-Object { '{0} #{1}' -f (Dt $_.TimeCreated), $_.Id }) -join ' · ') } else { 'keine lesbar' })))
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$ram = if ($os) { '{0:N1}/{1:N1} GB frei' -f ($os.FreePhysicalMemory / 1MB), ($os.TotalVisibleMemorySize / 1MB) } else { '?' }
Z (('CPU-Last {0}% · RAM {1} · Benutzer {2}' -f $cpu.LoadPercentage, $ram, $env:USERNAME))
Z (('Skript diagnose.ps1 vom {0} · Ausgabe gekürzt: {1}' -f (Dt (Get-Item -LiteralPath $PSCommandPath).LastWriteTime), $(if ($Kurz) { 'ja (-Kurz)' } else { 'nein' })))

if ($Kurz) { $Z | Select-Object -First 20 | ForEach-Object { $_ }; return }

# ── LANGFASSUNG ───────────────────────────────────────────────────────────────────────────────────────────────────
Kopf 'Prozesse (Win32_Process, ohne wmic)'
if ($prozZeilen) { $prozZeilen | Sort-Object | ForEach-Object { Z $_ } } else { Z '(keine passenden Prozesse: python/chrome/terminal64/cmd)' }

Kopf 'Dateien im Ordner — Geheimnisse nur als Metadaten, nie Inhalt'
foreach ($n in $geheim) { Z ('{0,-28} {1}' -f $n, (DateiInfo (Join-Path $Ordner $n))) }
if ($readerOrdner) { foreach ($n in $geheimReader) { Z ('{0,-28} {1}' -f ('tv-reader\' + $n), (DateiInfo (Join-Path $readerOrdner $n))) } }
Z ('{0,-28} {1}' -f 'Puls-Chrome-Profil', (DateiInfo (Join-Path $env:LOCALAPPDATA 'Prophos\puls-chrome\Local State')))
Z ('{0,-28} {1}' -f '~\.prophos\mirror-sessions', (DateiInfo (Join-Path $env:USERPROFILE '.prophos\mirror-sessions.json')))

Kopf 'Code-Dateien (Stand und Alter)'
foreach ($n in @('VERSION', 'copier.py', 'panel.py', 'order_bot.py', 'app.py', 'prophos.html', 'provision.py', 'augen.js', 'augen_tsx.js', 'start-alles.bat', 'start-copier.bat', 'start-panel.bat', 'start-prophos.bat')) {
    Z ('{0,-20} {1}' -f $n, (DateiInfo (Join-Path $Ordner $n)))
}
if ($readerOrdner) { foreach ($n in @('reader-server.py', 'tv_verbinder.py', 'tv_snapshot.py', 'tv-reader.user.js', 'tsx-auge.user.js')) { Z ('{0,-20} {1}' -f ('tv-reader\' + $n), (DateiInfo (Join-Path $readerOrdner $n))) } }

Kopf 'Puls-Spur (augen_*.json, puls_*.json — kompakt)'
foreach ($n in @('augen_regel.json', 'augen_stand.json', 'augen_letzt.json', 'puls_fenster.json', 'puls_tsx_bleiben.json')) { Z ('{0}: {1}' -f $n, (Kompakt (Join-Path $Ordner $n))) }
# login_*.json nur als Metadaten (S9 01.11.2026): enthält den Broker-Benutzernamen, der soll nicht an den Mac. Kein Passwort drin, trotzdem sparsam.
$loginSpuren = @(Get-ChildItem -LiteralPath $Ordner -Filter 'login_*.json' | Sort-Object LastWriteTime -Descending | Select-Object -First 2)
foreach ($f in $loginSpuren) { Z ('{0}: {1}' -f $f.Name, (DateiInfo $f.FullName)) }

Kopf 'Echo-Status (status*.json je Master — kompakt)'
$st = @(Get-ChildItem -LiteralPath $Ordner -Filter 'status*.json' | Sort-Object Name)
if ($st) { foreach ($f in $st) { Z ('{0}: {1}' -f $f.Name, (Kompakt $f.FullName 500)) } } else { Z '(keine status*.json)' }
if ($readerOrdner) { Z ('tv-reader\positions.json: ' + (Kompakt (Join-Path $readerOrdner 'positions.json') 500)) }

Kopf ('fehlerfoto.log — letzte {0} Zeilen' -f $LogZeilen)
LetzteZeilen (Join-Path $Ordner 'fehlerfoto.log') $LogZeilen | ForEach-Object { Z $_ }

Kopf ('mt5-update.log (ProgramData\Prophos\mt5-update) — letzte {0} Zeilen' -f [Math]::Min($LogZeilen, 20))
LetzteZeilen (Join-Path $env:ProgramData 'Prophos\mt5-update\mt5-update.log') ([Math]::Min($LogZeilen, 20)) | ForEach-Object { Z $_ }

Kopf 'Polar — neuester Lauf'
$polar = Join-Path $Ordner 'polar'
$lauf = if (Test-Path -LiteralPath $polar) { Get-ChildItem -LiteralPath $polar -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1 } else { $null }
if ($lauf) {
    Z ('Lauf {0} ({1})' -f $lauf.Name, (Dt $lauf.LastWriteTime))
    foreach ($f in (Get-ChildItem -LiteralPath $lauf.FullName -Filter '*.log')) { Z ('· {0}:' -f $f.Name); LetzteZeilen $f.FullName 15 | ForEach-Object { Z ('    ' + $_) } }
} else { Z '(kein polar-Ordner oder kein Lauf)' }

Kopf ('MT5-Journale (heute, letzte {0} Zeilen je Terminal)' -f [Math]::Min($LogZeilen, 25))
$heute = $Jetzt.ToString('yyyyMMdd')
$datenOrdner = @()
$datenOrdner += Get-ChildItem -Path 'C:\' -Directory -Filter 'MT5-*' | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'logs') } | ForEach-Object { $_.FullName }   # portable
$mq = Join-Path $env:APPDATA 'MetaQuotes\Terminal'
if (Test-Path -LiteralPath $mq) { $datenOrdner += Get-ChildItem -LiteralPath $mq -Directory | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'logs') } | ForEach-Object { $_.FullName } }
if (-not $datenOrdner) { Z '(keine MT5-Datenordner mit logs\ gefunden)' }
foreach ($d in $datenOrdner) {
    $herkunft = ''
    $o = Join-Path $d 'origin.txt'
    if (Test-Path -LiteralPath $o) { try { $herkunft = ' ← ' + ([System.IO.File]::ReadAllText($o, [System.Text.Encoding]::Unicode)).Trim() } catch { } }
    Z ('· {0}{1}' -f $d, $herkunft)
    $j = Join-Path $d ('logs\' + $heute + '.log')
    if (Test-Path -LiteralPath $j) { LetzteZeilen $j ([Math]::Min($LogZeilen, 25)) | ForEach-Object { Z ('    ' + $_) } } else { Z '    (heute kein Journal)' }
}

Kopf 'Starter-Fenster (cmd mit .bat) und Konsolen-Hinweis'
Z 'Copier/Panel/Backend/Bot loggen nur in ihre Konsolenfenster. Für die Konsolenausgabe: Parsec oder das Panel (127.0.0.1:8770).'
$bats = @($prozZeilen | Where-Object { $_ -match '^cmd' })
if ($bats) { $bats | ForEach-Object { Z $_ } } else { Z '(kein Starter-Fenster offen — Stack läuft nicht über start-alles.bat?)' }

Kopf 'Geplante Aufgaben (Prophos)'
$tasks = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -match 'Prophos|Puls|mt5|Tailscale' }
if ($tasks) { foreach ($t in $tasks) { $i = $t | Get-ScheduledTaskInfo; Z ('{0,-30} {1,-10} letzter Lauf {2} ({3})' -f $t.TaskName, $t.State, (Dt $i.LastRunTime), $i.LastTaskResult) } } else { Z '(keine)' }

$Z | ForEach-Object { $_ }
