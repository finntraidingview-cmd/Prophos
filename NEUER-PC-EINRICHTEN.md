# Prophos auf einem neuen PC einrichten (Echo + Puls)

Stand 14.10.2026, Version .1542. Ersetzt den Stand vom 08.10. Jeder Schritt ist ein
Block zum Kopieren (Strg+C) und Einfügen (Strg+V, dann Enter). Darunter steht, wann
der Schritt fertig ist.

Alles läuft aus **einem Ordner: `C:\mt5-copier`**. `start-alles.bat` öffnet vier
Fenster: **Copier** (Echo), **Panel** (Port 8770), **Backend** (Port 5000), **TV-Reader** (Port 8790).

> Repo ist privat. Updates holt der PC erst, wenn `code_token.txt` im Ordner liegt.
> Die Datei legt der Prophos-Tab nach dem Login auf localhost:5000 selbst ab (Schritt 4).

---

## 0. Vorab in Prophos (am Mac, nicht am PC)

- Die ID braucht einen **Prophos-Login**. Marc hat noch keinen, Marco schon.
- Die **Prop-Konten der ID** in Prophos anlegen, sonst hat Echo in Schritt 5 nichts zum Klonen.
- Je Futures-Firma den **Tradovate-Benutzernamen** hinterlegen: Einstellungen → Firmen →
  Firma bearbeiten → Feld „TV-Login“. Ohne den weiß Puls bei mehreren Logins nicht, welches Konto gemeint ist.

## 1. Windows vorbereiten

PowerShell **als Administrator** öffnen: Windows-Taste + X → „Terminal (Administrator)“.
Oder aus einer normalen PowerShell:

```powershell
Start-Process powershell -Verb RunAs
```

Dann im Admin-Fenster:

```powershell
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements; winget install -e --id Microsoft.VCRedist.2015+.x64 --accept-source-agreements --accept-package-agreements; winget install -e --id Google.Chrome --accept-source-agreements --accept-package-agreements
```

Fertig, wenn alle drei „Erfolgreich installiert“ oder „bereits installiert“ melden.

**Intelligente App-Steuerung prüfen** (blockt sonst die MetaTrader5-DLL, Vorfall Jacob 08.10.):

```powershell
(Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy' -Name VerifiedAndReputablePolicyState -ErrorAction SilentlyContinue).VerifiedAndReputablePolicyState
```

Fertig, wenn `0` oder nichts kommt. Bei `1` oder `2` Windows-Sicherheit öffnen und ausschalten
(App- & Browsersteuerung → Intelligente App-Steuerung → **Aus**):

```powershell
start windowsdefender:
```

Danach **PowerShell schließen und neu öffnen** (normal, nicht Admin) und prüfen:

```powershell
python --version; pip --version
```

Fertig, wenn beide eine Version zeigen. Kommt „python wurde nicht gefunden“: Python-Installer
von Hand starten und **„Add python.exe to PATH“** anhaken.

## 2. Prophos-Dateien aufspielen

Seit 02.11.2026 gibt es dafür keinen Download von pages.dev mehr. Railway liefert Code nur mit dem Schlüssel `code_token.txt`, und den legt erst der eingeloggte Prophos-Tab ab (Schritt 4). Der erste Stand kommt deshalb als Paket vom Mac. Danach holt sich der PC jedes Update selbst über Railway.

Am Mac das Paket bauen. Es liegt danach auf dem Schreibtisch und enthält keine Zugangsdaten:

```bash
git -C /Applications/Prophos fetch -q origin && git -C /Applications/Prophos archive --format=zip -o "$HOME/Desktop/prophos-pc-paket.zip" origin/main mt5-copier/start-alles.bat mt5-copier/start-copier.bat mt5-copier/start-panel.bat mt5-copier/start-prophos.bat mt5-copier/autostart-einrichten.bat mt5-copier/puls-chrome-starten.bat mt5-copier/copier.py mt5-copier/panel.py mt5-copier/provision.py mt5-copier/order_bot.py mt5-copier/augen.js mt5-copier/augen_tsx.js mt5-copier/ProphosHedgeReader.mq5 mt5-copier/config.vorlage.json mt5-copier/VERSION app.py prophos.html tv-reader/start-reader.bat tv-reader/reader-server.py tv-reader/tv_verbinder.py tv-reader/tv_snapshot.py tv-reader/start-verbinder.bat tv-reader/verbinder.config.example.json pc-fernzugriff
```

`prophos-pc-paket.zip` per Parsec auf den Schreibtisch des PCs legen. Geht die Dateiübertragung dort nicht: USB-Stick oder Drive. Dann auf dem PC (normale PowerShell):

```powershell
& { $ErrorActionPreference='Stop'; $w=[Environment]::GetFolderPath('Desktop'); $z="$w\prophos-pc-paket.zip"; if(-not (Test-Path $z)){ throw "Paket fehlt: $z" }; $t="$env:TEMP\prophos-paket"; if(Test-Path $t){ Remove-Item $t -Recurse -Force }; Expand-Archive $z $t; $k=@(Get-ChildItem "$t\mt5-copier","$t\tv-reader","$t\app.py","$t\prophos.html" -File | Where-Object { $_.Length -lt 200 -and $_.Name -ne 'VERSION' }); if($k.Count){ throw "Paket unbrauchbar, Datei zu klein: $($k.Name -join ', ')" }; if((Get-Content "$t\mt5-copier\VERSION" -TotalCount 1) -notmatch '^[0-9-]+\.[0-9]+$'){ throw 'Paket unbrauchbar: VERSION falsch' }; $d='C:\mt5-copier'; $r='C:\Prophos\tv-reader'; New-Item -ItemType Directory -Force $d,$r | Out-Null; Copy-Item "$t\mt5-copier\*","$t\app.py","$t\prophos.html" $d -Force; Copy-Item "$t\tv-reader\*" $r -Force; Copy-Item "$t\pc-fernzugriff" $w -Recurse -Force; python -m pip install flask requests signalrcore MetaTrader5 pywinauto; if($LASTEXITCODE){ throw 'pip fehlgeschlagen: Block nochmal starten' }; Get-ChildItem $d | Select Name,Length }
```

Fertig, wenn in `C:\mt5-copier` 17 Dateien stehen. Bricht der Block mit „Paket unbrauchbar“ ab, ist nichts kopiert: Paket am Mac neu bauen und neu ablegen. Kontrolle auf leere Dateien:

```powershell
Get-ChildItem C:\mt5-copier | Where-Object Length -eq 0
```

Fertig, wenn **nichts** ausgegeben wird.

## 3. Starten + Autostart

```powershell
cd C:\mt5-copier; cmd /c autostart-einrichten.bat; Start-Process C:\mt5-copier\start-alles.bat
```

Fertig, wenn vier Fenster offen sind: „MT5-Hedge-Copier“, „Copier-Panel“, „Prophos-Backend“, „Prophos TV-Reader“.
**Minimieren, nicht schließen.** Der erste Start dauert ein paar Minuten (Backend lädt Pakete).

Kontrolle nach 2–3 Minuten:

```powershell
(iwr http://localhost:5000 -UseBasicParsing).StatusCode; (iwr http://localhost:8770 -UseBasicParsing).StatusCode
```

Fertig, wenn zweimal `200` kommt. Bleibt `start-alles` bei „BACKEND LAEUFT NICHT“ stehen:
`start-prophos.bat` einzeln doppelklicken, dort steht der Fehlertext.

## 4. Einloggen + Code-Schlüssel + pc_id

```powershell
start http://localhost:5000
```

Dort mit dem **Login der ID** einloggen, **nicht** auf pages.dev. **Nur einen Tab** öffnen,
zwei Tabs mit derselben pc_id schreiben abwechselnd in `mt5_live`. Tab offen lassen.

Warten, bis der Schlüssel da ist, und die pc_id ablesen:

```powershell
while(-not (Test-Path C:\mt5-copier\code_token.txt)){ Start-Sleep 5 }; 'Schluessel da'; Get-Content C:\mt5-copier\pc_id.json
```

Fertig, wenn „Schluessel da“ und eine Zeile mit `"pc_id": "pc-xxxxxx"` kommt. Dauert bis 5 Minuten.
**Diese pc_id an Finn/Master schicken** (für Schritt 6, Datenbank).

Dann Panel → **„Alles schließen & neu starten“**, damit Copier und Panel mit Schlüssel laufen.
Kontrolle in Prophos: Admin → Übersicht → **PC-Tabs**, dort steht der PC mit aktueller Version.

## 5. MT5-Konten (Echo)

MetaTrader 5 laden und Installer starten:

```powershell
iwr https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe -OutFile $env:TEMP\mt5setup.exe -UseBasicParsing; Start-Process $env:TEMP\mt5setup.exe
```

Im Installer: **„Einstellungen“ → Zielordner `C:\MT5-Master`**. Nicht nach `C:\Program Files`.
Kontrolle:

```powershell
Test-Path C:\MT5-Master\terminal64.exe
```

Fertig, wenn `True`.

Dann in Prophos (localhost:5000): **Echo → „＋ Account hinzufügen“ → „Aus Prophos-Account übernehmen“**.
Das klont die Vorlage samt EA und Config je Konto.

- **Alten PC für diese Konten vorher ausschalten.** Sonst Doppel-Hedge.
- Beim ersten Mal kommt eine **„Windows PowerShell“-Ja-Abfrage** → **Ja**. Danach laufen MT5-Updates still.
- `magic_base`: Familie 760000–779999, Reihenfolge 777 → 778 → 760 → 761 … 769. 779000 reserviert.

## 6. Puls-Chrome (Order-Bot)

### 6a. Puls-Chrome starten

```powershell
Start-Process C:\mt5-copier\puls-chrome-starten.bat
```

Öffnet ein eigenes Chrome-Profil (`%LOCALAPPDATA%\Prophos\puls-chrome`, Port 9333), getrennt vom
normalen Chrome. Die schwarze Konsole kann danach zu. Kontrolle:

```powershell
irm http://127.0.0.1:9333/json/version
```

Fertig, wenn eine Chrome-Version kommt. Kommt ein Fehler, ist das Puls-Chrome nicht offen.

### 6b. Login-Seiten direkt im Puls-Chrome öffnen

TradingView:

```powershell
irm -Method Put 'http://127.0.0.1:9333/json/new?https://www.tradingview.com/'
```

Tradovate (für den Login-Wechsel, Passwörter **hier** speichern lassen):

```powershell
irm -Method Put 'http://127.0.0.1:9333/json/new?https://trader.tradovate.com/'
```

Nur bei Topstep-PCs zusätzlich TopstepX:

```powershell
irm -Method Put 'http://127.0.0.1:9333/json/new?https://topstepx.com/'
```

Jeder Befehl öffnet einen neuen Tab im Puls-Chrome. Dort von Hand:

1. **TradingView** mit dem TV-Konto der ID einloggen. Dieses TV-Konto darf **sonst nirgends** offen
   sein (kein normales Chrome, kein Reader). Zwei Sitzungen werfen sich gegenseitig raus.
2. Handelspanel unten → **Tradovate → Demo → verbinden**, „Remember me“ an.
3. Auf **trader.tradovate.com** jeden Tradovate-Login der ID einmal einloggen und das Passwort
   in Chrome **speichern**. Der automatische Login-Wechsel findet nur Einträge für genau diese Domain.
4. Nur Topstep: TopstepX einloggen, Felder vorausgefüllt lassen, rechts die **Order-Karte**
   einstellen (nicht das DOM / Preisleiter, damit kann Puls nicht klicken).
5. Puls-Chrome **maximiert** lassen. Nicht maximiert scheitern die Läufe.

### 6c. Datenbank (macht der Master)

Die pc_id aus Schritt 4 kommt in `wd_farmer_regeln.puls_augen_cdp` (SQL-Datei in `sql/`).
Topstep-PCs zusätzlich in `puls_topstep_pcs`. Ohne Eintrag läuft der alte UIA-Weg.

### 6d. Danach Hände weg

Jeder Puls-Lauf holt das Puls-Chrome nach vorn und bewegt die echte Windows-Maus. Während ein
Trade startet, nicht am PC arbeiten. Popups und Toasts räumt Puls selbst weg (.1534).

## 7. TV-Reader (lokal, für Userscript + Orbit V3)

Der Reader kommt aus dem Paket von Schritt 2, `start-alles.bat` startet ihn mit (viertes Fenster „Prophos TV-Reader“). Fehlt er auf einem PC, holt ihn `start-alles.bat` beim Start selbst über Railway, sobald `code_token.txt` da ist. Von Hand nur nötig, wenn das Fenster danach fehlt:

```powershell
& { $ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; $c='C:\mt5-copier\code_token.txt'; if(-not (Test-Path $c)){ throw 'code_token.txt fehlt: erst auf http://localhost:5000 einloggen, nach bis zu 5 min liegt der Schluessel da' }; $s=(Get-Content $c -TotalCount 1).Trim(); $d='C:\Prophos\tv-reader'; New-Item -ItemType Directory -Force $d | Out-Null; 'reader-server.py','tv_verbinder.py','tv_snapshot.py','start-reader.bat','start-verbinder.bat','verbinder.config.example.json' | ForEach-Object { $n="$d\$_.neu"; Invoke-WebRequest ('https://web-production-bec81.up.railway.app/code/datei/tv-reader/'+$_) -Headers @{'X-Code-Token'=$s} -OutFile $n -UseBasicParsing; if((Get-Item $n).Length -lt 200){ Remove-Item $n; throw "$_ ist zu klein, keine echte Datei. Nichts ersetzt." }; Move-Item $n "$d\$_" -Force }; Start-Process "$d\start-reader.bat" }
```

Tampermonkey + Userscript im Puls-Chrome: siehe `PULS-CHROME-USERSCRIPT.md`.

---

## Wenn etwas nicht geht

| Symptom | Ursache → Lösung |
|---|---|
| „pywinauto fehlt“ | VC++ Runtime fehlt → Schritt 1 |
| „MetaTrader5-Paket fehlt“ / „MT5 von Windows blockiert“ | Intelligente App-Steuerung → Aus (Schritt 1). **Kein** `pip --upgrade` |
| Copier-Karten „gestoppt“, Log nur „QuickEdit aus“ | `python -m pip install MetaTrader5`, dann „Alles schließen & neu starten“ |
| PC bekommt keine Updates | `code_token.txt` fehlt → Tab auf localhost:5000 offen lassen (Schritt 4) |
| Puls läuft über UIA statt Puls-Chrome | pc_id fehlt in `puls_augen_cdp` → Schritt 6c |
| Puls: „kein_broker“ / „konto_nicht_erreicht“ | Tradovate im Puls-Chrome abgemeldet oder TV-Konto woanders offen → Schritt 6b |
| Puls bricht beim Login-Wechsel ab | Passwort nicht für **trader.tradovate.com** gespeichert → Schritt 6b Punkt 3 |
| TopstepX „anker_fehlt“ | rechts steht das DOM statt der Order-Karte → Schritt 6b Punkt 4 |
| Tab hängt auf alter Version | **F5** am PC |
| `C:\prophos\app.py` existiert noch | alter Backend-Starter: Fenster schließen **und** die Aufgabenplanungs-Task löschen |

Nützliche Prüfbefehle jederzeit:

```powershell
Get-Content C:\mt5-copier\VERSION; Get-Content C:\mt5-copier\pc_id.json; Test-Path C:\mt5-copier\code_token.txt; irm http://127.0.0.1:9333/json/version
```
