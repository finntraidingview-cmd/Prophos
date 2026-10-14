# Prophos auf einem neuen PC einrichten (Echo + Puls)

Stand 14.10.2026, Version .1542. Ersetzt den Stand vom 08.10. Jeder Schritt ist ein
Block zum Kopieren (Strg+C) und Einfügen (Strg+V, dann Enter). Darunter steht, wann
der Schritt fertig ist.

Alles läuft aus **einem Ordner: `C:\mt5-copier`**. `start-alles.bat` öffnet drei
Fenster: **Copier** (Echo), **Panel** (Port 8770), **Backend** (Port 5000).

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

## 2. Prophos-Dateien holen (normale PowerShell)

```powershell
$d='C:\mt5-copier'; New-Item -ItemType Directory -Force $d | Out-Null; $ProgressPreference='SilentlyContinue'; $b='https://prophos.pages.dev/'; 'start-alles.bat','start-copier.bat','start-panel.bat','start-prophos.bat','autostart-einrichten.bat','puls-chrome-starten.bat','copier.py','panel.py','provision.py','order_bot.py','augen.js','augen_tsx.js','ProphosHedgeReader.mq5','config.vorlage.json','VERSION' | % { iwr ($b+'mt5-copier/'+$_) -OutFile "$d\$_" -UseBasicParsing }; 'app.py','prophos.html','firm_rules.json' | % { iwr ($b+$_) -OutFile "$d\$_" -UseBasicParsing }; python -m pip install flask requests signalrcore MetaTrader5 pywinauto; Get-ChildItem $d | Select Name,Length
```

Fertig, wenn 18 Dateien stehen. Kontrolle auf leere Dateien:

```powershell
Get-ChildItem C:\mt5-copier | Where-Object Length -eq 0
```

Fertig, wenn **nichts** ausgegeben wird. Wird eine Datei genannt, Schritt 2 wiederholen.

## 3. Starten + Autostart

```powershell
cd C:\mt5-copier; cmd /c autostart-einrichten.bat; Start-Process C:\mt5-copier\start-alles.bat
```

Fertig, wenn drei Fenster offen sind: „MT5-Hedge-Copier“, „Copier-Panel“, „Prophos-Backend“.
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

Seit .1543 holt `start-alles.bat` den Reader beim Start selbst von pages.dev, wenn er fehlt, und
startet ihn mit (viertes Fenster „Prophos TV-Reader“). Von Hand nur nötig, wenn das Fenster fehlt:

```powershell
$d='C:\Prophos\tv-reader'; New-Item -ItemType Directory -Force $d | Out-Null; $ProgressPreference='SilentlyContinue'; 'reader-server.py','tv_verbinder.py','tv_snapshot.py','start-reader.bat','start-verbinder.bat','verbinder.config.example.json' | % { iwr ('https://prophos.pages.dev/tv-reader/'+$_) -OutFile "$d\$_" -UseBasicParsing }
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
| Ordner `C:\prophos` existiert noch | alter Backend-Starter: Fenster schließen **und** die Aufgabenplanungs-Task löschen |

Nützliche Prüfbefehle jederzeit:

```powershell
Get-Content C:\mt5-copier\VERSION; Get-Content C:\mt5-copier\pc_id.json; Test-Path C:\mt5-copier\code_token.txt; irm http://127.0.0.1:9333/json/version
```
