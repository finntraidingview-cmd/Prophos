# PC-FERNZUGRIFF, Einrichtung (Finn 01.11.2026): Claude am Mac soll bei Puls-Fehlern nachsehen und Updates einspielen,
# ohne dass Finn PowerShell-Befehle und Screenshots zwischen Mac und PCs hin- und herkopiert. Weg: Tailscale + SSH,
# Claude selbst laeuft nur am Mac. Mac-Seite: pc-fernzugriff/mac/pc.sh.
#
# Aufruf als Administrator, am PC selbst (Parsec oder vor Ort), wiederholbar:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-pc.ps1
#
# Liest aus C:\mt5-copier nur pc_id.json. Veraendert dort nichts, auch nicht Chrome-Profile oder MT5.
# Der Auth-Key wird nur abgefragt und landet in keiner Datei. Er soll in der Tailscale-Verwaltung getaggt (tag:pc)
# und NICHT wiederverwendbar sein: ein getaggtes Geraet hat im Tailnet keine Nutzer-Rechte, und der Key ist nach dem
# Beitritt wertlos. Was die PCs erreichen duerfen, regelt die ACL (eigene Datei): nichts, auch den Mac nicht.
#
# Nur ASCII (ae/oe/ue) mit Absicht: Windows PowerShell 5.1 liest eine .ps1 ohne BOM als ANSI, Umlaute werden dann zu
# Zeichenmuell, und typografische Anfuehrungszeichen beendet es sogar als String.
#Requires -RunAsAdministrator
[CmdletBinding()]
param(
  [string]$PcId,               # sonst aus C:\mt5-copier\pc_id.json
  [string]$WindowsBenutzer,    # sonst der an der Konsole angemeldete Nutzer (Autologon)
  [string]$MacSchluessel       # oeffentlicher Schluessel des Macs; sonst Abfrage, falls noch keiner eingetragen ist
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$WURZEL     = Join-Path $env:ProgramData 'prophos-fernzugriff'
$STAND      = Join-Path $WURZEL 'stand.json'
$SSH_DIR    = Join-Path $env:ProgramData 'ssh'
$SSHD_CFG   = Join-Path $SSH_DIR 'sshd_config'
$AUTH_KEYS  = Join-Path $SSH_DIR 'administrators_authorized_keys'
$TS_EXE     = Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
$FW_GRUPPE  = 'Prophos Fernzugriff'
$MARKER     = 'prophos-fernzugriff'
$TAG_PC     = 'tag:pc'
$UTF8_OHNE_BOM = New-Object System.Text.UTF8Encoding($false)

function Schritt([string]$text){ Write-Host "`n== $text" -ForegroundColor Cyan }

# Windows PowerShell 5.1 macht aus stderr eines Programms unter 'Stop' sonst einen Abbruch. Fehlertext ja, Argumente nie:
# bei tailscale up steht der Auth-Key in den Argumenten.
function Nativ([string]$exe, [string[]]$argumente){
  $alt = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try{
    $text = (& $exe @argumente 2>&1 | ForEach-Object { "$_" }) -join "`n"
    return [pscustomobject]@{ code = $LASTEXITCODE; text = $text }
  } finally { $ErrorActionPreference = $alt }
}

if($env:SSH_CONNECTION){
  throw 'Dieses Skript startet sshd neu und wuerde die eigene Verbindung kappen -> am PC selbst ausfuehren (Parsec oder vor Ort).'
}

# ---------- PC-Kennung und Windows-Nutzer ----------
Schritt 'PC-Kennung und Windows-Nutzer'
if(-not $PcId){
  $datei = 'C:\mt5-copier\pc_id.json'
  if(-not (Test-Path -LiteralPath $datei)){ throw "$datei fehlt -> Kennung mitgeben: -PcId pc-xxxxxx" }
  $PcId = (Get-Content -LiteralPath $datei -Raw -Encoding UTF8 | ConvertFrom-Json).pc_id
}
if($PcId -cnotmatch '^pc-[a-z0-9]{4,12}$'){ throw "Kennung '$PcId' passt nicht zum Muster pc-[a-z0-9]{4,12} -> -PcId pc-xxxxxx mitgeben" }

if($WindowsBenutzer){
  $konto = "$env:COMPUTERNAME\$WindowsBenutzer"
} else {
  $konto = (Get-CimInstance Win32_ComputerSystem).UserName    # Get-CimInstance, nicht wmic: fehlt auf 24H2+ teils
  if(-not $konto){ throw 'Niemand an der Konsole angemeldet (RDP zaehlt nicht) -> -WindowsBenutzer <name> mitgeben' }
}
# klein geschrieben (Pruefer S9, 01.11.2026): Win32-OpenSSH vergleicht AllowUsers in Kleinschreibung; mit 'Dubai' kaeme niemand
# rein, und sshd -t merkt das nicht
$kurz = (($konto -split '\\')[-1]).ToLowerInvariant()
if($kurz -notmatch '^[A-Za-z0-9._][A-Za-z0-9._ -]*$'){ throw "Windows-Nutzer '$kurz' enthaelt Zeichen, die dieses Skript nicht abdeckt" }
Write-Host "PC $PcId, Windows-Nutzer $konto"

# ---------- Stand von vorher merken, nur beim ersten Lauf: daraus baut der Rueckbau den alten Zustand zurueck ----------
Schritt 'Stand von vorher merken'
if(-not (Test-Path -LiteralPath $WURZEL)){ New-Item -ItemType Directory -Path $WURZEL | Out-Null }
& icacls $WURZEL /inheritance:r /grant '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' | Out-Null
if($LASTEXITCODE -ne 0){ throw "icacls auf $WURZEL fehlgeschlagen (Code $LASTEXITCODE)" }

if(-not (Test-Path -LiteralPath $STAND)){
  $dienst = Get-Service -Name sshd -ErrorAction SilentlyContinue
  $fwAlt = @(Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP','sshd' -ErrorAction SilentlyContinue | Where-Object { $_.Enabled -eq 'True' } | ForEach-Object { $_.Name })
  $stand = [ordered]@{
    tailscale_war_da = [bool](Test-Path -LiteralPath $TS_EXE)
    openssh_war_da   = [bool]$dienst
    sshd_lief        = [bool]($dienst -and $dienst.Status -eq 'Running')
    sshd_starttyp    = $(if($dienst){ "$($dienst.StartType)" } else { '' })
    fw_regeln_aktiv  = $fwAlt
    sshd_config_da   = [bool](Test-Path -LiteralPath $SSHD_CFG)
    gesetzt_at       = (Get-Date).ToString('s')
  }
  if($stand.sshd_config_da){ Copy-Item -LiteralPath $SSHD_CFG -Destination (Join-Path $WURZEL 'sshd_config.vorher') -Force }
  [IO.File]::WriteAllText($STAND, ($stand | ConvertTo-Json), $UTF8_OHNE_BOM)
  Write-Host 'Stand gemerkt.'
} else { Write-Host 'Stand von einem frueheren Lauf bleibt gueltig.' }

# ---------- Mac-Schluessel frueh pruefen: Tippfehler sollen auffallen, bevor etwas installiert ist ----------
Schritt 'Schluessel des Macs'
$schonDa = @()
if(Test-Path -LiteralPath $AUTH_KEYS){ $schonDa = @(Get-Content -LiteralPath $AUTH_KEYS | Where-Object { $_ -like "*$MARKER" }) }
if(-not $MacSchluessel -and $schonDa.Count -eq 0){
  $MacSchluessel = Read-Host 'Oeffentlichen Schluessel des Macs einfuegen (eine Zeile, ssh-ed25519 ...)'
}
$schluesselZeile = $null
if($MacSchluessel){
  $teile = $MacSchluessel.Trim() -split '\s+'
  if($teile.Count -lt 2 -or $teile[0] -cne 'ssh-ed25519' -or $teile[1] -notmatch '^[A-Za-z0-9+/]+={0,2}$'){
    throw 'Das ist kein oeffentlicher ed25519-Schluessel -> Inhalt von prophos_fern_ed25519.pub einfuegen (NIE die Datei ohne .pub)'
  }
  # from=: der Schluessel gilt auch dann nur aus dem Tailnet, falls die Firewall einmal anders steht
  $schluesselZeile = "from=`"100.64.0.0/10`",no-port-forwarding,no-agent-forwarding,no-X11-forwarding $($teile[0]) $($teile[1]) $MARKER"
} else { Write-Host 'Schluessel ist schon eingetragen und bleibt.' }

# ---------- Tailscale ----------
Schritt 'Tailscale'
if(-not (Test-Path -LiteralPath $TS_EXE)){
  $wg = Get-Command winget -ErrorAction SilentlyContinue
  if(-not $wg){ throw 'winget fehlt -> App-Installer aus dem Microsoft Store installieren, dann nochmal starten' }
  $r = Nativ $wg.Source @('install','-e','--id','Tailscale.Tailscale','--silent','--accept-package-agreements','--accept-source-agreements')
  if(-not (Test-Path -LiteralPath $TS_EXE)){ throw "Tailscale nicht installiert (winget Code $($r.code)): $($r.text)" }
}
$backend = ''
$r = $null
for($i = 0; $i -lt 30; $i++){
  $r = Nativ $TS_EXE @('status','--json')
  if($r.text -match 'BackendState'){
    try { $backend = ($r.text | ConvertFrom-Json).BackendState } catch { $backend = '' }
    if($backend -and $backend -ne 'NoState'){ break }
  }
  Start-Sleep -Seconds 2
}
if(-not $backend){ throw "Tailscale-Dienst antwortet nicht: $($r.text)" }

if($backend -eq 'Running'){
  # Schon angemeldet, aber wo und als was? Ohne unser Tag laesst die ACL den Mac nicht zu diesem PC, und 'tailscale set' kann
  # keine Tags vergeben (Gegenpruefung 01.11.2026): dann klar abbrechen statt gruen enden und still unerreichbar sein.
  $tags = @()
  try { $tags = @(($r.text | ConvertFrom-Json).Self.Tags) } catch { $tags = @() }
  if($tags -notcontains $TAG_PC){
    throw "Tailscale ist schon angemeldet, aber ohne $TAG_PC (Tags: $($tags -join ', ' )) -> am PC 'tailscale logout', dann dieses Skript nochmal mit dem Auth-Key"
  }
  Write-Host 'Schon im Tailnet mit dem richtigen Tag, kein Auth-Key noetig.'
  $r = Nativ $TS_EXE @('set',"--hostname=$PcId",'--accept-dns=false','--accept-routes=false','--exit-node=','--shields-up=false')
  if($r.code -ne 0){ throw "tailscale set fehlgeschlagen: $($r.text)" }
} else {
  # Normale Eingabe statt SecureString (Pilot pc 01.11.2026: Rechtsklick-Einfuegen lieferte in der SecureString-Abfrage nur ein
  # Zeichen). Read-Host landet nicht in der PSReadLine-Chronik; die Konsole wird nach dem Beitritt geleert. Deshalb KEIN Parameter
  # fuer den Key: eine getippte Befehlszeile mit Key stuende in ConsoleHost_history.txt.
  # Mit der GPO 'PowerShell-Transkription' schriebe Windows die Eingabe in eine Textdatei (Pruefer S9, 02.11.2026): dann abbrechen
  $tr = Get-ItemProperty -Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\Transcription' -ErrorAction SilentlyContinue
  if($tr -and $tr.EnableTranscripting -eq 1){
    throw 'PowerShell-Transkription ist per Richtlinie an, der Auth-Key landete im Transkript -> Richtlinie aus (gpedit: Windows PowerShell > PowerShell-Transkription aktivieren = Deaktiviert), dann nochmal'
  }
  Write-Host 'Der Key ist beim Einfuegen sichtbar; die Konsole wird nach dem Beitritt geleert. Kein Start-Transcript laufen lassen.' -ForegroundColor Yellow
  $key = (Read-Host 'Tailscale Auth-Key (tskey-auth-...)').Trim()
  $r = $null
  try {
    if($key -notlike 'tskey-auth-*'){ throw 'Das ist kein Auth-Key (beginnt mit tskey-auth-)' }
    # accept-dns/accept-routes aus und kein Exit-Node: Internet-Weg, DNS und damit die IP des PCs bleiben, wie sie sind.
    # unattended: Tailscale bleibt auch ohne angemeldeten Nutzer im Netz (Neustart vor dem Autologon).
    # Der Key steht fuer die Sekunden des Aufrufs in der Kommandozeile von tailscale.exe (Task-Manager, Prozess-Audit 4688 falls
    # eingeschaltet, Standard aus). Deshalb ein NICHT wiederverwendbarer Key: nach dem Beitritt ist er wertlos.
    $r = Nativ $TS_EXE @('up',"--auth-key=$key","--hostname=$PcId","--advertise-tags=$TAG_PC",'--accept-dns=false','--accept-routes=false','--unattended','--reset')
  } finally {
    $key = $null
    try { Clear-Host } catch {}
    # Konsole leer, aber der Key liegt noch in der Zwischenablage (und evtl. im Win+V-Verlauf): Einmal-Key, trotzdem sagen
    Write-Host "== Tailscale: Konsole geleert, der Key stand sichtbar darin. Zwischenablage selbst leeren." -ForegroundColor Cyan
    if($r){ Write-Host "tailscale up fuer $PcId ist gelaufen (Code $($r.code))." }
  }
  if($r.code -ne 0){ throw "tailscale up fehlgeschlagen: $($r.text)" }
}
$r = Nativ $TS_EXE @('ip','-4')
if($r.code -ne 0 -or $r.text -notmatch '^100\.'){ throw "Keine Tailnet-Adresse: $($r.text)" }
$tsIp = ($r.text -split "`n")[0].Trim()
Write-Host "Im Tailnet als $PcId, Adresse $tsIp"

# ---------- Firewall VOR dem ersten sshd-Start ----------
Schritt 'Firewall: Port 22 nur aus dem Tailnet'
# OpenSSH-Server anlegen, falls noetig. Erst das winget-Paket (Pilot pc 01.11.2026, Windows 11 25H2: Add-WindowsCapability
# OpenSSH.Server lief fehlerfrei durch, der Dienst sshd fehlte trotzdem; Microsoft.OpenSSH.Preview brachte ihn sofort),
# die Windows-Capability nur als Rueckfall. Fehlt der Dienst nach beidem, steht der Capability-State mit in der Meldung.
# Beide Wege legen eine Firewall-Regel an, die Port 22 fuer alle oeffnet, und starten den Dienst mit Standard-Konfiguration
# (Passwort an): fuer Sekunden, bis Stop-Service und das Abschalten der Freigaben unten greifen. REIHENFOLGE NICHT UMSTELLEN
# (Pruefer S9, 02.11.2026): Installation -> Stop-Service -> fremde Freigaben aus -> Allow nur Tailnet -> Keys/Config -> Start.
$sshdDienst = { Get-Service -Name sshd -ErrorAction SilentlyContinue }
if(-not (& $sshdDienst)){
  $wg = Get-Command winget -ErrorAction SilentlyContinue
  $wgText = 'winget fehlt'
  if($wg){
    $r = Nativ $wg.Source @('install','-e','--id','Microsoft.OpenSSH.Preview','--silent','--accept-package-agreements','--accept-source-agreements')
    $wgText = "winget Code $($r.code)"
  }
  Stop-Service -Name sshd -ErrorAction SilentlyContinue
  if(-not (& $sshdDienst)){
    Write-Warning "OpenSSH per winget nicht da ($wgText) -> Rueckfall Windows-Capability"
    $cap = Get-WindowsCapability -Online | Where-Object { $_.Name -like 'OpenSSH.Server*' } | Select-Object -First 1
    if($cap){ try { Add-WindowsCapability -Online -Name $cap.Name | Out-Null } catch { Write-Warning "Add-WindowsCapability $($cap.Name): $($_.Exception.Message)" } }
    Stop-Service -Name sshd -ErrorAction SilentlyContinue
  }
  if(-not (& $sshdDienst)){
    $state = (Get-WindowsCapability -Online | Where-Object { $_.Name -like 'OpenSSH.Server*' } | ForEach-Object { "$($_.Name)=$($_.State)" }) -join ', '
    throw "OpenSSH-Dienst sshd fehlt nach winget ($wgText) und Capability (State: $(if($state){ $state } else { 'kein OpenSSH.Server angeboten' })) -> Neustart und nochmal, sonst winget install -e --id Microsoft.OpenSSH.Preview von Hand"
  }
}
Stop-Service -Name sshd -ErrorAction SilentlyContinue
Get-NetFirewallRule -Group $FW_GRUPPE -ErrorAction SilentlyContinue | Remove-NetFirewallRule
# Jede FREMDE eingehende Freigabe auf TCP 22 aus (die der Capability, die des winget-Pakets, eine alte von Hand). Nur Regeln mit
# genau Port 22, nie Regeln mit 'Any' (das waeren Programm-Freigaben wie Parsec oder Chrome). Namen in fw_deaktiviert.json,
# damit der Rueckbau sie wieder einschalten kann.
# Ohne -PolicyStore ActiveStore: der liefert auch GPO-Regeln, die sich nicht abschalten lassen (Gegenpruefung 02.11.2026)
$fremd = @(Get-NetFirewallPortFilter | Where-Object { $_.Protocol -eq 'TCP' -and (@($_.LocalPort) -contains '22') } |
  Get-NetFirewallRule | Where-Object { $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow' -and $_.Enabled -eq 'True' -and $_.Group -ne $FW_GRUPPE })
if($fremd.Count){
  $merk = Join-Path $WURZEL 'fw_deaktiviert.json'
  $alt = @(); if(Test-Path -LiteralPath $merk){ try { $alt = @(Get-Content -LiteralPath $merk -Raw | ConvertFrom-Json) } catch { $alt = @() } }
  $namen = @($alt + ($fremd | ForEach-Object { $_.Name }) | Select-Object -Unique)
  [IO.File]::WriteAllText($merk, (ConvertTo-Json @($namen)), $UTF8_OHNE_BOM)
  # je Regel einzeln: eine Regel, die sich nicht abschalten laesst, darf den Lauf hier (sshd ist gestoppt) nicht abbrechen
  foreach($fr in $fremd){ try { $fr | Disable-NetFirewallRule } catch { Write-Warning "Port-22-Freigabe '$($fr.DisplayName)' nicht abschaltbar: $($_.Exception.Message) -> im Pilot von aussen auf Port 22 pruefen" } }
  Write-Host "Fremde Port-22-Freigaben aus: $(($fremd | ForEach-Object { $_.DisplayName }) -join ', ')"
}
# Bereichsregeln wie 20-25 decken Port 22 mit, ohne '22' zu enthalten (Pruefer S9, 02.11.2026): nur melden, nicht abschalten,
# so eine Regel hat jemand mit Absicht breit angelegt
$bereich = @(Get-NetFirewallPortFilter | Where-Object { $_.Protocol -eq 'TCP' -and (@($_.LocalPort) | Where-Object { $_ -match '^(\d+)-(\d+)$' -and [int]$Matches[1] -le 22 -and [int]$Matches[2] -ge 22 }) } |
  Get-NetFirewallRule | Where-Object { $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow' -and $_.Enabled -eq 'True' })
foreach($br in $bereich){ Write-Warning "Bereichsregel '$($br.DisplayName)' deckt Port 22 -> von Hand pruefen (Windows-Firewall, eingehende Regeln)" }
# 'Ohne Allow-Regel = blockiert' gilt nur, wenn das Profil an ist und eingehend standardmaessig blockt (Pruefer S9, 02.11.2026)
foreach($pf in @(Get-NetFirewallProfile | Where-Object { $_.Enabled -ne 'True' -or $_.DefaultInboundAction -eq 'Allow' })){
  Write-Warning "Firewall-Profil '$($pf.Name)': Enabled=$($pf.Enabled), eingehend=$($pf.DefaultInboundAction) -> Port 22 waere dort offen; Profil einschalten bzw. eingehend auf Blockieren (Windows-Sicherheit > Firewall)"
}
# Nur nach Absender-Adresse, NICHT an den Tailscale-Adapter gebunden (Gegenpruefung 01.11.2026): Windows merkt sich den Adapter
# ueber seine Kennung; legt ein Tailscale-Update ihn neu an, griffe die Regel nicht mehr und jeder PC waere still unerreichbar.
New-NetFirewallRule -DisplayName 'Prophos Fernzugriff SSH aus dem Tailnet' -Group $FW_GRUPPE -Direction Inbound -Action Allow `
  -Protocol TCP -LocalPort 22 -RemoteAddress '100.64.0.0/10' -Profile Any | Out-Null
# KEINE Block-Regel mehr (Pilot pc 01.11.2026: 'Mindestens ein Adresspraefix ist ungueltig' fuer den Bereich ab 0.0.0.0).
# Sie war Guertel zu Hosentraeger: Windows blockt eingehend von Haus aus alles ohne Allow-Regel, die fremden Port-22-Freigaben
# sind oben aus, und der Schluessel traegt from=Tailnet. ListenAddress <Tailnet-IP> in der sshd_config waere der andere Weg,
# aber sshd startet nach einem Neustart vor dem Tailscale-Adapter und kaeme dann mit einer noch fehlenden Adresse nicht hoch.
Write-Host 'Allow-Regel gesetzt: Port 22 nur aus 100.64.0.0/10.'

# ---------- Schluessel-Datei ----------
Schritt 'Schluessel-Datei und sshd-Konfiguration'
if(-not (Test-Path -LiteralPath $SSH_DIR)){ New-Item -ItemType Directory -Path $SSH_DIR | Out-Null }
# Host-Keys selbst erzeugen (ssh-keygen -A liegt neben sshd.exe) statt den Dienst einmal mit seiner Standard-Konfiguration
# (Passwort an) zu starten. Rechte danach wie der Dienst sie setzt: nur SYSTEM und Administratoren, sonst lehnt sshd die Keys ab.
$sshdExe = ((Get-CimInstance Win32_Service -Filter "Name='sshd'").PathName).Trim('"')
$hostKeyPub = Join-Path $SSH_DIR 'ssh_host_ed25519_key.pub'
if(-not (Test-Path -LiteralPath $hostKeyPub)){
  $keygen = Join-Path (Split-Path -Parent $sshdExe) 'ssh-keygen.exe'
  if(-not (Test-Path -LiteralPath $keygen)){ throw "$keygen fehlt (OpenSSH unvollstaendig)" }
  $r = Nativ $keygen @('-A')
  if(-not (Test-Path -LiteralPath $hostKeyPub)){ throw "ssh-keygen -A hat keine Host-Keys in $SSH_DIR angelegt (Code $($r.code)): $($r.text)" }
  foreach($k in Get-ChildItem -LiteralPath $SSH_DIR -Filter 'ssh_host_*_key'){
    & icacls $k.FullName /reset | Out-Null
    & icacls $k.FullName /inheritance:r /grant '*S-1-5-32-544:F' '*S-1-5-18:F' | Out-Null
    if($LASTEXITCODE -ne 0){ throw "icacls auf $($k.FullName) fehlgeschlagen (Code $LASTEXITCODE)" }
  }
}
if($schluesselZeile){
  # Fremde Zeilen bleiben stehen, nur unsere wird ersetzt (neuer Schluessel = alter ist raus)
  $alt = @()
  if(Test-Path -LiteralPath $AUTH_KEYS){ $alt = @(Get-Content -LiteralPath $AUTH_KEYS | Where-Object { $_ -and $_ -notlike "*$MARKER" }) }
  # WriteAllText statt Set-Content: 5.1 schreibt sonst mit BOM, und sshd verwirft die Datei still
  [IO.File]::WriteAllText($AUTH_KEYS, ((@($alt) + $schluesselZeile) -join "`n") + "`n", $UTF8_OHNE_BOM)
}
if(-not (Test-Path -LiteralPath $AUTH_KEYS)){ throw "$AUTH_KEYS fehlt -> mit -MacSchluessel nochmal starten" }
# SIDs statt Gruppennamen: auf deutschem Windows heisst die Gruppe Administratoren. Andere Rechte = sshd ignoriert die Datei.
# /reset vorweg: /inheritance:r nimmt nur geerbte Eintraege weg, ein frueher von Hand gesetzter Fremd-Eintrag bliebe sonst stehen.
& icacls $AUTH_KEYS /reset | Out-Null
& icacls $AUTH_KEYS /inheritance:r /grant '*S-1-5-32-544:F' '*S-1-5-18:F' | Out-Null
if($LASTEXITCODE -ne 0){ throw "icacls auf $AUTH_KEYS fehlgeschlagen (Code $LASTEXITCODE)" }

# ---------- sshd_config: ganz schreiben statt flicken, der alte Stand liegt in sshd_config.vorher ----------
# AuthorizedKeysFile global statt 'Match Group administrators': der Gruppenname haengt an der Windows-Sprache.
# AllowUsers mit Nutzer allein (ohne Rechner-Teil), ein Leerzeichen im Namen braucht Anfuehrungszeichen.
$cfg = @"
# Von pc-fernzugriff/setup-pc.ps1 geschrieben
Port 22
AddressFamily inet
PubkeyAuthentication yes
PasswordAuthentication no
PermitEmptyPasswords no
KbdInteractiveAuthentication no
GSSAPIAuthentication no
AuthorizedKeysFile __PROGRAMDATA__/ssh/administrators_authorized_keys
AllowUsers "$kurz"
AllowTcpForwarding no
AllowAgentForwarding no
GatewayPorts no
PermitTunnel no
X11Forwarding no
MaxAuthTries 3
LoginGraceTime 30
Subsystem sftp sftp-server.exe
"@
$cfgVorher = $null
if(Test-Path -LiteralPath $SSHD_CFG){ $cfgVorher = [IO.File]::ReadAllText($SSHD_CFG) }
[IO.File]::WriteAllText($SSHD_CFG, ($cfg -replace "`r`n", "`n") + "`n", $UTF8_OHNE_BOM)

$r = Nativ $sshdExe @('-t')
if($r.code -ne 0){
  if($null -ne $cfgVorher){ [IO.File]::WriteAllText($SSHD_CFG, $cfgVorher, $UTF8_OHNE_BOM) } else { Remove-Item -LiteralPath $SSHD_CFG -Force }
  throw "sshd lehnt die neue Konfiguration ab, alte wiederhergestellt: $($r.text)"
}
Set-Service -Name sshd -StartupType Automatic
Start-Service -Name sshd
Write-Host 'sshd laeuft, nur Schluessel-Anmeldung.'

# ---------- Repo-Dateien auf den PC: C:\mt5-copier\fernzugriff ----------
# Master 01.11.2026: die Helfer der anderen Teile (Foto: foto\foto.ps1, Diagnose) erwarten ihren Platz dort. Eigener, neuer
# Unterordner; alles andere in C:\mt5-copier bleibt unberuehrt. Beim Update den Ordner am Mac neu kopieren und nochmal starten.
Schritt 'Repo-Dateien nach C:\mt5-copier\fernzugriff'
$zielOrdner = 'C:\mt5-copier\fernzugriff'
if(-not (Test-Path -LiteralPath 'C:\mt5-copier')){ throw 'C:\mt5-copier fehlt -> erst Prophos einrichten (NEUER-PC-EINRICHTEN.md), dann dieses Skript' }
if((Resolve-Path -LiteralPath $PSScriptRoot).Path.TrimEnd('\') -ieq $zielOrdner){
  Write-Host 'Skript laeuft schon aus dem Zielordner, nichts zu kopieren.'
} else {
  if(-not (Test-Path -LiteralPath $zielOrdner)){ New-Item -ItemType Directory -Path $zielOrdner | Out-Null }
  # Nur die bekannten Dateien, nie '*' (Pruefer S9, 01.11.2026): liegt das Skript z. B. in Downloads, waere sonst der ganze Ordner
  # (Installer, Kontoauszuege) nach fernzugriff gewandert. Fehlt ein Teil, klar sagen, aber weiterlaufen: die anderen Teile
  # kommen aus eigenen Auftraegen und koennen beim Pilot noch fehlen.
  # foto\ und agent\ komplett (Repo-Kopien, Ziel wird vorher geleert). Laufzeitdateien des Agents (auftraege\, ergebnisse\,
  # agent.log) liegen laut agent\README.md NEBEN agent\, nicht darin, und bleiben so erhalten (S13 56d95c59, 02.11.2026).
  $bekannt = @('setup-pc.ps1', 'rueckbau-pc.ps1', 'diagnose.ps1', 'foto', 'agent')
  $fehlt = @()
  foreach($name in $bekannt){
    $quelle = Join-Path $PSScriptRoot $name
    if(-not (Test-Path -LiteralPath $quelle)){ $fehlt += $name; continue }
    if(Test-Path -LiteralPath $quelle -PathType Container){
      $zielUnter = Join-Path $zielOrdner $name
      if(Test-Path -LiteralPath $zielUnter){ Remove-Item -LiteralPath $zielUnter -Recurse -Force }   # alter Stand komplett weg
      Copy-Item -LiteralPath $quelle -Destination $zielUnter -Recurse -Force
    } else {
      Copy-Item -LiteralPath $quelle -Destination (Join-Path $zielOrdner $name) -Force
    }
  }
  Write-Host "Kopiert nach ${zielOrdner}: $(($bekannt | Where-Object { $fehlt -notcontains $_ }) -join ', ')"
  if($fehlt.Count){ Write-Warning "Nicht neben setup-pc.ps1 gefunden, daher nicht kopiert: $($fehlt -join ', ') -> den ganzen Ordner pc-fernzugriff aus dem Repo auf den PC legen und nochmal starten" }
}

# ---------- Foto-Aufgabe (S13) ----------
# foto\foto-aufgabe.ps1 traegt die Aufgabe 'Prophos Foto' fuer den Nutzer ein, der sie ausfuehrt ($env:USERNAME), und muss darum
# als der am Desktop angemeldete Nutzer laufen. Bei Autologon mit einem Admin-Konto ist das dieser Lauf; sonst (anderer Admin)
# klar sagen, was noch fehlt (Pilot pc 01.11.2026: foto.ps1 Exit 2, Aufgabe fehlte).
Schritt 'Foto-Aufgabe'
$fotoAufgabe = Join-Path $zielOrdner 'foto\foto-aufgabe.ps1'
if(-not (Test-Path -LiteralPath $fotoAufgabe)){
  Write-Warning "NOCH OFFEN: $fotoAufgabe fehlt (Ordner foto\ nicht mitkopiert) -> Repo-Ordner komplett auf den PC, nochmal starten"
} elseif($env:USERNAME.ToLowerInvariant() -ne $kurz){
  Write-Warning "NOCH OFFEN: dieses Fenster laeuft als $env:USERNAME, angemeldet ist $kurz -> als $kurz ausfuehren: powershell -NoProfile -ExecutionPolicy Bypass -File $fotoAufgabe"
} else {
  $r = Nativ 'powershell.exe' @('-NoProfile','-ExecutionPolicy','Bypass','-File',$fotoAufgabe)
  if($r.code -eq 0){ Write-Host "Foto-Aufgabe angelegt. $($r.text)" }
  else { Write-Warning "NOCH OFFEN: Foto-Aufgabe nicht angelegt (Code $($r.code)): $($r.text) -> Ursache beheben, dann: powershell -NoProfile -ExecutionPolicy Bypass -File $fotoAufgabe" }
}

# ---------- Fertig: was am Mac einzutragen ist ----------
# Host-Key und Adresse kommen ueber diesen Bildschirm (Parsec / vor Ort) zum Mac, nicht ueber das Netz: so prueft der Mac beim
# ersten Verbinden schon den richtigen Schluessel (StrictHostKeyChecking yes in mac/ssh_config.beispiel).
Schritt 'Fertig'
$hk = (Get-Content -LiteralPath $hostKeyPub -Raw).Trim() -split '\s+'
Write-Host 'Am Mac an ~/.prophos-fernzugriff/known_hosts anhaengen (eine Zeile):' -ForegroundColor Green
Write-Host "$PcId $($hk[0]) $($hk[1])" -ForegroundColor Green
Write-Host 'Und in ~/.prophos-fernzugriff/ssh_config VOR dem Block "Host pc-*" einfuegen:' -ForegroundColor Green
Write-Host "Host $PcId" -ForegroundColor Green
Write-Host "  HostName $tsIp" -ForegroundColor Green
Write-Host "  HostKeyAlias $PcId" -ForegroundColor Green
Write-Host "  User $kurz" -ForegroundColor Green
Write-Host "Danach pruefen: pc-fernzugriff/mac/pc.sh $PcId -- hostname"
