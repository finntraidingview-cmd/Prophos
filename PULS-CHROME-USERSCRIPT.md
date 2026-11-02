# Puls-Chrome + Reader + Userscript einrichten (je Puls-/Hedge-PC)

Stand 14.10.2026. Bereinigte Fassung der Schritte vom 01.10. Geändert gegenüber damals:
Repo ist privat. Stand 02.11.2026: Der erste Stand kommt als Paket vom Mac, jedes Update danach mit `code_token.txt` über Railway. Dateien von prophos.pages.dev zu laden, geht nicht mehr: Pages antwortet auf fehlende Pfade mit der Startseite, das sähe wie ein erfolgreicher Download aus.
Ordner ist **`C:\mt5-copier`** (nicht `C:\mt5-copier\mt5-copier`). Alles PowerShell, eine Zeile je Block.

---

## A. Panel + Copier + Backend (falls noch nicht da)

Am Mac das Paket bauen (keine Zugangsdaten darin):

```bash
git -C /Applications/Prophos fetch -q origin && git -C /Applications/Prophos archive --format=zip -o "$HOME/Desktop/prophos-pc-paket.zip" origin/main mt5-copier/start-alles.bat mt5-copier/start-copier.bat mt5-copier/start-panel.bat mt5-copier/start-prophos.bat mt5-copier/autostart-einrichten.bat mt5-copier/puls-chrome-starten.bat mt5-copier/copier.py mt5-copier/panel.py mt5-copier/provision.py mt5-copier/order_bot.py mt5-copier/augen.js mt5-copier/augen_tsx.js mt5-copier/ProphosHedgeReader.mq5 mt5-copier/config.vorlage.json mt5-copier/VERSION app.py prophos.html tv-reader/start-reader.bat tv-reader/reader-server.py tv-reader/tv_verbinder.py tv-reader/tv_snapshot.py tv-reader/start-verbinder.bat tv-reader/verbinder.config.example.json pc-fernzugriff
```

`prophos-pc-paket.zip` per Parsec auf den Schreibtisch des PCs legen. Geht die Dateiübertragung dort nicht: USB-Stick oder Drive. Dann auf dem PC:

```powershell
& { $ErrorActionPreference='Stop'; $w=[Environment]::GetFolderPath('Desktop'); $z="$w\prophos-pc-paket.zip"; if(-not (Test-Path $z)){ throw "Paket fehlt: $z" }; $t="$env:TEMP\prophos-paket"; if(Test-Path $t){ Remove-Item $t -Recurse -Force }; Expand-Archive $z $t; $k=@(Get-ChildItem "$t\mt5-copier","$t\tv-reader","$t\app.py","$t\prophos.html" -File | Where-Object { $_.Length -lt 200 -and $_.Name -ne 'VERSION' }); if($k.Count){ throw "Paket unbrauchbar, Datei zu klein: $($k.Name -join ', ')" }; if((Get-Content "$t\mt5-copier\VERSION" -TotalCount 1) -notmatch '^[0-9-]+\.[0-9]+$'){ throw 'Paket unbrauchbar: VERSION falsch' }; $d='C:\mt5-copier'; $r='C:\Prophos\tv-reader'; New-Item -ItemType Directory -Force $d,$r | Out-Null; Copy-Item "$t\mt5-copier\*","$t\app.py","$t\prophos.html" $d -Force; Copy-Item "$t\tv-reader\*" $r -Force; Copy-Item "$t\pc-fernzugriff" $w -Recurse -Force; if(Get-Command winget -ErrorAction SilentlyContinue){ winget install -e --id Microsoft.VCRedist.2015+.x64 --accept-source-agreements --accept-package-agreements } else { Write-Warning 'winget fehlt: VC++ von Hand installieren' }; python -m pip install flask requests signalrcore MetaTrader5 pywinauto; if($LASTEXITCODE){ throw 'pip fehlgeschlagen: Block nochmal starten' }; cmd /c "$d\autostart-einrichten.bat"; Start-Process "$d\start-alles.bat" }
```

Bricht der Block mit „Paket unbrauchbar“ ab, ist nichts kopiert: Paket neu bauen und neu ablegen.

Fertig, wenn vier schwarze Fenster offen sind (Copier, Panel, Backend, Reader) und Chrome `http://localhost:5000` öffnet.
Alle Fenster offen lassen. Fragt Windows wegen VC++ nach: **Ja**.

Dort mit dem Login der ID einloggen (nur ein Tab). Dann Schlüssel abwarten und Kennung lesen:

```powershell
while(-not (Test-Path C:\mt5-copier\code_token.txt)){ Start-Sleep 5 }; 'Schluessel da'; Get-Content C:\mt5-copier\pc_id.json
```

Fertig, wenn `"pc_id": "pc-xxxxxx"` kommt. **Diese Kennung an den Master schicken** (Eintrag in
`puls_augen_cdp`, bei Topstep-Konten zusätzlich `puls_topstep_pcs`).

## B. Reader starten

Der Reader liegt schon da (Paket aus A) und `start-alles.bat` hat ihn gestartet. Steht das Fenster „Prophos TV-Reader“ bereits, B überspringen. Sonst, auch wenn der Ordner fehlt (holt über Railway, braucht `code_token.txt` aus A):

```powershell
& { $ErrorActionPreference='Stop'; if(-not (Test-Path 'C:\Prophos\tv-reader\reader-server.py')){ $ProgressPreference='SilentlyContinue'; $c='C:\mt5-copier\code_token.txt'; if(-not (Test-Path $c)){ throw 'code_token.txt fehlt: erst auf http://localhost:5000 einloggen, nach bis zu 5 min liegt der Schluessel da' }; $s=(Get-Content $c -TotalCount 1).Trim(); $d='C:\Prophos\tv-reader'; New-Item -ItemType Directory -Force $d | Out-Null; 'start-reader.bat','reader-server.py' | ForEach-Object { $n="$d\$_.neu"; Invoke-WebRequest ('https://web-production-bec81.up.railway.app/code/datei/tv-reader/'+$_) -Headers @{'X-Code-Token'=$s} -OutFile $n -UseBasicParsing; if((Get-Item $n).Length -lt 200){ Remove-Item $n; throw "$_ ist zu klein, keine echte Datei. Nichts ersetzt." }; Move-Item $n "$d\$_" -Force } }; Start-Process 'C:\Prophos\tv-reader\start-reader.bat' }
```

Fertig, wenn ein schwarzes Fenster „Prophos TV-Reader“ aufgeht. Offen lassen.
Ab dem nächsten Neustart startet `start-alles.bat` den Reader von selbst mit. Kontrolle:

```powershell
irm http://127.0.0.1:8790/positions
```

Fertig, wenn JSON kommt (nicht „Verbindung verweigert“).

## C. Puls-Chrome öffnen

```powershell
cd C:\mt5-copier; python order_bot.py augen start
```

Fertig, wenn ein neues Chrome-Fenster aufgeht (eigenes Profil, Port 9333). Kontrolle:

```powershell
irm http://127.0.0.1:9333/json/version
```

Im Puls-Chrome dann **TradingView** einloggen, Handelspanel → **Tradovate → Demo → verbinden**,
„Remember me“ an. Tradovate-Passwörter auf **trader.tradovate.com** speichern lassen.
Bei Topstep zusätzlich TopstepX einloggen, rechts die **Order-Karte** (nicht das DOM).

## D. Tampermonkey im Puls-Chrome (nicht im normalen Chrome)

Tab mit dem Web-Store-Eintrag im Puls-Chrome öffnen:

```powershell
irm -Method Put 'http://127.0.0.1:9333/json/new?https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo'
```

1. Dort **„Hinzufügen“** klicken.
2. In die Adresszeile des Puls-Chrome eingeben:

```
chrome://extensions
```

3. Oben rechts **Entwicklermodus** einschalten.
4. Bei Tampermonkey → **Details** → **„Nutzerscripts zulassen“** einschalten. Ohne das läuft kein Script.

## E. Userscript installieren

Diese Adresse im Puls-Chrome öffnen (Reader aus Schritt B muss laufen):

```powershell
irm -Method Put 'http://127.0.0.1:9333/json/new?http://127.0.0.1:8790/userscript/tv-reader.user.js'
```

Tampermonkey zeigt einen **Installieren**-Knopf → klicken. Kommt stattdessen eine Fehlerseite: Der Reader holt das Script über Railway und braucht dafür seinen eigenen Schlüssel `C:\Prophos\tv-reader\feed_token.txt`. Den legt der Tab auf localhost:5000 ab. Tab offen lassen, bis die Datei liegt (etwa 1 min), dann E wiederholen. **Reader nicht neu starten**, ein zweites Fenster kreist nur.

## F. Auf Puls-Chrome-Modus stellen

Im TradingView-Tab auf das **Tampermonkey-Symbol** klicken → Menüpunkt **„Puls-Chrome (Orbit V3)“**
wählen → Tab mit **F5** neu laden.

Fertig, wenn in TradingView unten das Abzeichen steht: **● Orbit V3 · Puls-Chrome · 0 Pos** (grün).

---

## Stolperstellen von den anderen PCs

| Symptom | Ursache → Lösung |
|---|---|
| Auto-Login klappt nicht (frisches Puls-Chrome) | Tradovate-Username fehlt → Prophos → Einstellungen → Prop Firms → Feld „TV-Login“ (war bei Aurel so) |
| Abzeichen „Copier OFFLINE“ | Reader-Fenster aus Schritt B läuft nicht → neu starten |
| Puls fällt auf alten Weg (UIA) zurück | pc_id nicht in `puls_augen_cdp` **oder** `augen_regel.json` älter als 12 h → `cd C:\mt5-copier; python order_bot.py augen start` |
| Kein Abzeichen in TradingView | „Nutzerscripts zulassen“ aus (Schritt D 4) oder Script nicht auf Puls-Chrome-Modus (Schritt F) |
| TradingView wirft raus | dasselbe TV-Konto ist woanders offen (normales Chrome, Reader-PC). Nur im Puls-Chrome einloggen |
| `$`-Zeichen fehlen im eingefügten Befehl | Befehl aus dieser Datei kopieren, nicht aus dem Chat |

Prüfbefehle jederzeit:

```powershell
Get-Content C:\mt5-copier\pc_id.json; Test-Path C:\mt5-copier\code_token.txt; irm http://127.0.0.1:8790/positions; irm http://127.0.0.1:9333/json/version
```
