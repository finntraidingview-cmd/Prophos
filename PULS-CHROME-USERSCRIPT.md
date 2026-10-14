# Puls-Chrome + Reader + Userscript einrichten (je Puls-/Hedge-PC)

Stand 14.10.2026. Bereinigte Fassung der Schritte vom 01.10. Geändert gegenüber damals:
Repo ist privat, Dateien kommen von **prophos.pages.dev** statt raw.githubusercontent.
Ordner ist **`C:\mt5-copier`** (nicht `C:\mt5-copier\mt5-copier`). Alles PowerShell, eine Zeile je Block.

---

## A. Panel + Copier + Backend (falls noch nicht da)

```powershell
$d='C:\mt5-copier'; New-Item -ItemType Directory -Force $d | Out-Null; $ProgressPreference='SilentlyContinue'; $b='https://prophos.pages.dev/'; 'start-alles.bat','start-copier.bat','start-panel.bat','start-prophos.bat','autostart-einrichten.bat','puls-chrome-starten.bat','copier.py','panel.py','provision.py','order_bot.py','augen.js','augen_tsx.js','ProphosHedgeReader.mq5','config.vorlage.json','VERSION' | % { iwr ($b+'mt5-copier/'+$_) -OutFile "$d\$_" -UseBasicParsing }; 'app.py','prophos.html','firm_rules.json' | % { iwr ($b+$_) -OutFile "$d\$_" -UseBasicParsing }; winget install -e --id Microsoft.VCRedist.2015+.x64 --accept-source-agreements --accept-package-agreements; python -m pip install flask requests signalrcore MetaTrader5 pywinauto; cmd /c "$d\autostart-einrichten.bat"; Start-Process "$d\start-alles.bat"
```

Fertig, wenn drei schwarze Fenster offen sind (Copier, Panel, Backend) und Chrome `http://localhost:5000` öffnet.
Alle Fenster offen lassen. Fragt Windows wegen VC++ nach: **Ja**.

Dort mit dem Login der ID einloggen (nur ein Tab). Dann Schlüssel abwarten und Kennung lesen:

```powershell
while(-not (Test-Path C:\mt5-copier\code_token.txt)){ Start-Sleep 5 }; 'Schluessel da'; Get-Content C:\mt5-copier\pc_id.json
```

Fertig, wenn `"pc_id": "pc-xxxxxx"` kommt. **Diese Kennung an den Master schicken** (Eintrag in
`puls_augen_cdp`, bei Topstep-Konten zusätzlich `puls_topstep_pcs`).

## B. Reader starten

```powershell
$d='C:\Prophos\tv-reader'; New-Item -ItemType Directory -Force $d | Out-Null; $ProgressPreference='SilentlyContinue'; 'start-reader.bat','reader-server.py' | % { iwr ('https://prophos.pages.dev/tv-reader/'+$_) -OutFile "$d\$_" -UseBasicParsing }; Start-Process "$d\start-reader.bat"
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

Tampermonkey zeigt einen **Installieren**-Knopf → klicken. Kommt stattdessen eine Fehlerseite,
den Rückfall-Weg nehmen:

```powershell
irm -Method Put 'http://127.0.0.1:9333/json/new?https://prophos.pages.dev/tv-reader/tv-reader.user.js'
```

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
