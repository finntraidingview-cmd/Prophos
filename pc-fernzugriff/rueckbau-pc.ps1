# PC-FERNZUGRIFF, Rueckbau (Finn 01.11.2026, Slave 14): nimmt alles wieder weg, was setup-pc.ps1 angelegt hat.
#   - OpenSSH-Server: Dienst gestoppt, deaktiviert, Windows-Feature entfernt, C:\ProgramData\ssh weg
#   - administrators_authorized_keys: unsere Zeile raus (Marker prophos-fernzugriff), fremde Zeilen bleiben; leer -> Datei weg
#   - Firewall: alle Regeln der Gruppe 'Prophos Fernzugriff' weg
#   - Tailscale: abgemeldet (Geraet verlaesst das Tailnet) und deinstalliert
#   - Foto-Aufgabe 'Prophos Foto' (und der alte Name ProphosFernzugriffFoto) weg, dazu C:\ProgramData\prophos-fernzugriff
#   - C:\mt5-copier\fernzugriff weg: den Ordner legt setup-pc.ps1 an (Kopie des Repo-Ordners), darin liegen auch die Fotos (foto\)
#
# Aufruf als Administrator, am PC selbst (Parsec oder vor Ort), wiederholbar:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\rueckbau-pc.ps1
#
# In C:\mt5-copier wird nur der Ordner fernzugriff angefasst. Copier, Puls, Chrome-Profile, MT5, pc_id.json bleiben unberuehrt.
# War Tailscale oder OpenSSH laut stand.json schon VOR setup-pc.ps1 da, bleibt es stehen (nur unsere Teile gehen weg).
# Mit -Alles geht trotzdem alles weg.
#
# Nur ASCII (ae/oe/ue) mit Absicht: Windows PowerShell 5.1 liest eine .ps1 ohne BOM als ANSI, Umlaute werden zu Zeichenmuell.
# Nicht unter Windows getestet (gebaut am Mac): erst am Pilot-PC ausserhalb der Handelszeit laufen lassen.
#Requires -RunAsAdministrator
[CmdletBinding()]
param(
  [switch]$Alles     # auch Tailscale/OpenSSH entfernen, wenn sie laut stand.json schon vorher da waren
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$WURZEL    = Join-Path $env:ProgramData 'prophos-fernzugriff'
$STAND     = Join-Path $WURZEL 'stand.json'
$SSH_DIR   = Join-Path $env:ProgramData 'ssh'
$AUTH_KEYS = Join-Path $SSH_DIR 'administrators_authorized_keys'
$TS_EXE    = Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
$FW_GRUPPE = 'Prophos Fernzugriff'
$AUFGABEN  = @('ProphosFernzugriffFoto', 'Prophos Foto')   # 'Prophos Foto' legt foto/foto-aufgabe.ps1 (S13) an; der erste Name stammt aus einem frueheren Entwurf von setup-pc.ps1
$MARKER    = 'prophos-fernzugriff'
$FERN_MT5  = 'C:\mt5-copier\fernzugriff'   # einziger Ordner in C:\mt5-copier, den setup-pc.ps1 anlegt (S9, 01.11.2026)
$UTF8_OHNE_BOM = New-Object System.Text.UTF8Encoding($false)

function Schritt([string]$text){ Write-Host "`n== $text" -ForegroundColor Cyan }

# stand.json-Felder StrictMode-sicher lesen: fehlt ein Feld (aeltere setup-Version), gilt $null statt Abbruch
function Feld($obj, [string]$name){
  if($null -eq $obj){ return $null }
  $p = $obj.PSObject.Properties[$name]
  if($p){ return $p.Value } else { return $null }
}

# Native Programme (tailscale.exe, winget) melden Fehler ueber den Exit-Code, nicht als PowerShell-Fehler
function Nativ([string]$exe, [string[]]$argumente){
  $alt = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try{
    $text = (& $exe @argumente 2>&1 | ForEach-Object { "$_" }) -join "`n"
    return [pscustomobject]@{ code = $LASTEXITCODE; text = $text }
  } finally { $ErrorActionPreference = $alt }
}

if($env:SSH_CONNECTION){
  throw 'Dieses Skript entfernt den SSH-Zugang und wuerde sich mitten im Lauf selbst abschneiden -> am PC selbst ausfuehren (Parsec oder vor Ort).'
}

# stand.json schreibt setup-pc.ps1 beim ersten Lauf: was schon vorher da war, bleibt ohne -Alles stehen
$stand = $null
if(Test-Path -LiteralPath $STAND){
  try { $stand = Get-Content -LiteralPath $STAND -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $stand = $null }
}
$tsBehalten  = (-not $Alles) -and [bool](Feld $stand 'tailscale_war_da')
$sshBehalten = (-not $Alles) -and [bool](Feld $stand 'openssh_war_da')

Schritt 'Foto-Aufgabe'
foreach($name in $AUFGABEN){
  if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){
    Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $name -Confirm:$false
    Write-Host "Aufgabe $name entfernt"
  }
}
if(Test-Path -LiteralPath $FERN_MT5){ Remove-Item -LiteralPath $FERN_MT5 -Recurse -Force; Write-Host "$FERN_MT5 entfernt" }

Schritt 'Schluessel des Macs'
if(Test-Path -LiteralPath $AUTH_KEYS){
  $rest = @(Get-Content -LiteralPath $AUTH_KEYS | Where-Object { $_ -and $_ -notlike "*$MARKER*" })
  if($rest.Count -gt 0 -and $sshBehalten){
    # WriteAllText statt Set-Content: 5.1 schreibt sonst mit BOM, und sshd verwirft die Datei still
    [IO.File]::WriteAllText($AUTH_KEYS, ($rest -join "`n") + "`n", $UTF8_OHNE_BOM)
    Write-Host 'unsere Zeile entfernt, fremde Zeilen bleiben'
  } else {
    Remove-Item -LiteralPath $AUTH_KEYS -Force
    Write-Host 'administrators_authorized_keys entfernt'
  }
} else { Write-Host 'keine Schluessel-Datei da' }

Schritt 'Firewall'
$regeln = @(Get-NetFirewallRule -Group $FW_GRUPPE -ErrorAction SilentlyContinue)
if($regeln.Count -gt 0){ $regeln | Remove-NetFirewallRule; Write-Host "$($regeln.Count) Regel(n) der Gruppe '$FW_GRUPPE' entfernt" }
else { Write-Host 'keine Regeln der Gruppe da' }
# setup-pc.ps1 hat die Standard-Regel des OpenSSH-Servers abgeschaltet; bleibt sshd (sshBehalten), kommt sie wieder
if($sshBehalten){
  foreach($n in @(Feld $stand 'fw_regeln_aktiv')){ if($n){ Enable-NetFirewallRule -Name $n -ErrorAction SilentlyContinue } }
}

Schritt 'OpenSSH-Server'
$dienst = Get-Service -Name sshd -ErrorAction SilentlyContinue
if($dienst){
  Stop-Service -Name sshd -Force -ErrorAction SilentlyContinue
  if($sshBehalten){
    # setup-pc.ps1 hat sshd_config komplett neu geschrieben (nur Schluessel, AllowUsers). Die Datei von vorher kommt zurueck;
    # gab es vorher keine, muss unsere weg, sonst laeuft sshd mit unserer Konfiguration und ohne Schluessel-Datei: niemand kaeme rein.
    $vorher = Join-Path $WURZEL 'sshd_config.vorher'
    $cfg = Join-Path $SSH_DIR 'sshd_config'
    if((Feld $stand 'sshd_config_da') -and (Test-Path -LiteralPath $vorher)){ Copy-Item -LiteralPath $vorher -Destination $cfg -Force }
    elseif(Test-Path -LiteralPath $cfg){ Remove-Item -LiteralPath $cfg -Force }   # sshd legt beim Start die Standard-Datei neu an
    $starttyp = Feld $stand 'sshd_starttyp'
    if($starttyp){ Set-Service -Name sshd -StartupType $starttyp }
    if(Feld $stand 'sshd_lief'){ Start-Service -Name sshd }
    Write-Host 'OpenSSH war vorher schon da: Konfiguration und Dienst-Zustand von vorher wiederhergestellt (-Alles entfernt ihn trotzdem).'
  } else {
    Set-Service -Name sshd -StartupType Disabled
    $cap = Get-WindowsCapability -Online | Where-Object { $_.Name -like 'OpenSSH.Server*' -and $_.State -eq 'Installed' } | Select-Object -First 1
    if($cap){ Remove-WindowsCapability -Online -Name $cap.Name | Out-Null }
    if(-not (Get-Service -Name sshd -ErrorAction SilentlyContinue)){ Write-Host 'OpenSSH-Server entfernt' }
    else { Write-Warning 'sshd-Dienst ist nach Remove-WindowsCapability noch da: Windows raeumt ihn beim naechsten Neustart weg. Er ist gestoppt und deaktiviert.' }
    # Host-Keys, sshd_config, Protokolle: alles aus unserer Installation
    if(Test-Path -LiteralPath $SSH_DIR){ Remove-Item -LiteralPath $SSH_DIR -Recurse -Force -ErrorAction SilentlyContinue }
  }
} else { Write-Host 'kein sshd-Dienst da' }

Schritt 'Tailscale'
if(Test-Path -LiteralPath $TS_EXE){
  if($tsBehalten){
    Write-Host 'Tailscale war vorher schon da und bleibt, auch im Tailnet (-Alles entfernt es trotzdem).'
  } else {
    # logout: Geraet meldet sich beim Tailnet ab und verliert seinen Node-Key. Der Eintrag unter Machines bleibt (von Hand loeschen).
    $r = Nativ $TS_EXE @('logout')
    if($r.code -ne 0){ Write-Warning "tailscale logout: $($r.text)" } else { Write-Host 'abgemeldet' }
    $wg = Get-Command winget -ErrorAction SilentlyContinue
    if($wg){
      $r = Nativ $wg.Source @('uninstall','-e','--id','Tailscale.Tailscale','--silent','--accept-source-agreements')
    } else {
      # ohne winget: MSI-Deinstallation ueber die Registrierung
      # Feld statt $_.DisplayName: viele Uninstall-Schluessel haben kein DisplayName, StrictMode wuerde dort abbrechen
      $eintrag = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue |
        Where-Object { (Feld $_ 'DisplayName') -eq 'Tailscale' -and (Feld $_ 'UninstallString') } | Select-Object -First 1
      if($eintrag -and (Feld $eintrag 'UninstallString') -match '\{[0-9A-Fa-f-]{36}\}'){
        $r = Nativ 'msiexec.exe' @('/x', $Matches[0], '/qn', '/norestart')
      } else { $r = [pscustomobject]@{ code = -1; text = 'weder winget noch MSI-Eintrag gefunden' } }
    }
    if(Test-Path -LiteralPath $TS_EXE){ Write-Warning "Tailscale noch installiert (Code $($r.code)): $($r.text) -> Einstellungen, Apps, Tailscale deinstallieren" }
    else { Write-Host 'deinstalliert' }
  }
} else { Write-Host 'Tailscale nicht installiert' }

Schritt 'Ordner'
if(Test-Path -LiteralPath $WURZEL){ Remove-Item -LiteralPath $WURZEL -Recurse -Force; Write-Host "$WURZEL entfernt" }
else { Write-Host 'kein Fernzugriff-Ordner da' }

Schritt 'Fertig'
Write-Host 'Noch von Hand: in der Tailscale-Verwaltung unter Machines diesen PC loeschen (tailscale logout laesst den Eintrag stehen).' -ForegroundColor Green
Write-Host 'Am Mac: den PC aus ~/.prophos-fernzugriff/ssh_config und known_hosts nehmen.' -ForegroundColor Green
