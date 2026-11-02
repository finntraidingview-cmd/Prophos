# PC-Agent — Maus, Tastatur, Fenster, Foto vom Mac aus (02.11.2026)

Finn: „Ich muss die PCs eigenständig bedienen können, Maus, Tastatur, alles sehen, und es muss viel schneller gehen.“
Vorher ~45 s je Aktion (Skript per scp, Aufgabe anlegen, Wartezeit, Foto per scp). Jetzt läuft `agent.py` dauerhaft in der
angemeldeten Windows-Sitzung und nimmt Aufträge als JSON-Dateien entgegen; der Mac braucht eine SSH-Verbindung je Auftrag
(ControlMaster), Ziel: Foto < 3 s, Aktion + Foto < 5 s.

## Teile
| Datei | Wo | Was |
|---|---|---|
| `agent.py` | PC, Aufgabe „Prophos Agent“ (pythonw, bei Anmeldung, Neustart bei Absturz) | wartet auf `…\fernzugriff\auftraege\<id>.json` (200 ms), schreibt `…\ergebnisse\<id>.json` + `<id>-<n>.png`, Log `…\fernzugriff\agent.log` |
| `auftrag.py` | PC, per SSH von `do.sh` gestartet | legt den Auftrag ab, wartet aufs Ergebnis (max. 20 s), druckt das JSON |
| `agent-aufgabe.ps1` | PC, einmal als Autologon-Nutzer | legt die Aufgabe an und startet sie; schreibt den echten python.exe-Pfad nach `…\fernzugriff\python.txt` (do.sh holt ihn einmal und merkt ihn in `~/.prophos-fernzugriff/python.<pc>`) |
| `mac/do.sh` | Mac | `do.sh <pc> '<json>'` oder `do.sh <pc> datei.json` → Ergebnis-JSON + `BILD <pfad>` je Foto |

Das Foto nimmt der Agent aus `foto/foto-schuss.py` (GDI, reines Python — PowerShell-Screenshots blockte AMSI am 29.10.2026).
Auf dem PC liegt alles unter `C:\mt5-copier\fernzugriff\` (`agent\`, `foto\` als Repo-Kopien; `auftraege\`, `ergebnisse\`,
`agent.log` daneben). Fotos am Mac: `~/Prophos-Fernzugriff/quarantaene/<pc>/`.

## Aktionen (Feld `aktion`)
| Aktion | Felder | Was |
|---|---|---|
| `foto` | optional `fenster` (Titel-Teil) oder `tab` (Text aus Titel/Adresse) | PNG aller Monitore, nur dieses Fenster (PrintWindow) oder ein Tab des Puls-Chrome ohne Tabwechsel |
| `tabs` | — | Tabs des Puls-Chrome: Titel und Adresse ohne Query |
| `fenster` | — | Liste sichtbarer Fenster: titel, klasse, x/y/w/h, pid, minimiert, vorne, `erlaubt` (puls_chrome/browser/konsole/frei oder null = gesperrt); plus `vorne` |
| `maus` | `x`, `y` | Zeiger setzen (Pixel wie im Foto, bei einem Monitor mit Ursprung 0/0); nicht auf TopstepX |
| `klick` | `x`, `y` (ganze Zahlen im Bildschirm), `art` links/rechts/doppelt, optional `fenster` | Klick, nie auf TopstepX, mit `fenster` nur, wenn dieses vorn ist |
| `tasten` | `fenster` (PFLICHT), `text` oder `kombi` | tippt nur, wenn das Vordergrundfenster diesen Titel trägt und nicht TopstepX ist; sonst Fehler, nichts getippt |
| `start` | `programm`, optional `ziel` (vorhandener lokaler Ordner, nur für explorer.exe) | nur `explorer.exe`, `cmd.exe`, `powershell.exe`, `pwsh.exe`, `wt.exe`, `ms-settings:…`. Kein Browser, keine Adresse, keine Datei |
| `vorholen` | `fenster` (Titel-Teil) | Fenster nach vorn, ohne Klick und ohne Taste, nie TopstepX. Windows kann das verweigern, dann kommt ein Fehler |
| `schliessen` | `fenster` (Titel-Teil) | WM_CLOSE, nie an TopstepX oder einen Browser oder Windows Terminal (hinten kann eine Betriebs-Konsole liegen) |
| `warte` | `ms` (≤ 10000) | Pause |
| `scroll` | `x`, `y`, `schritte` (−3 = 3 runter) | Mausrad, nie über TopstepX |

`kombi`: Tasten mit `+`, z. B. `enter`, `ctrl+c`, `win+r`, `f5`; Namen deutsch oder englisch (strg/ctrl, entf/del …). Im Browser keine Schließ-Kombis.
Wartezeit am Mac: 20 s, bei langen Aufträgen automatisch Σ `warte` + 1,5 s je Foto + 5 s (`DO_WARTE_S` hebt den Mindestwert).
Nach dem ersten Fehler stoppt der Auftrag; jede Aktion steht einzeln mit `ok`, `ms`, ggf. `fehler` im Ergebnis.

## Beispiele
```bash
bash pc-fernzugriff/mac/do.sh pc-7ftp5l '{"aktionen":[{"aktion":"foto"}]}'
bash pc-fernzugriff/mac/do.sh pc-7ftp5l '{"aktionen":[{"aktion":"fenster"}]}'
bash pc-fernzugriff/mac/do.sh pc-7ftp5l '{"aktionen":[{"aktion":"tabs"}]}'
bash pc-fernzugriff/mac/do.sh pc-7ftp5l '{"aktionen":[{"aktion":"foto","tab":"topstepx"}]}'
bash pc-fernzugriff/mac/do.sh pc-7ftp5l '{"aktionen":[
  {"aktion":"start","programm":"powershell.exe"},{"aktion":"warte","ms":800},
  {"aktion":"tasten","fenster":"PowerShell","text":"Get-Date\n"},
  {"aktion":"foto","fenster":"PowerShell"},
  {"aktion":"schliessen","fenster":"PowerShell"}]}'
bash pc-fernzugriff/mac/do.sh pc-7ftp5l '{"aktionen":[{"aktion":"klick","x":640,"y":400,"art":"doppelt"},{"aktion":"foto"}]}'
```
Ergebnis (eine Zeile JSON), dann `BILD /Users/…/quarantaene/pc-7ftp5l/20261102-101500-ab12cd-4.png`:
```json
{"id":"20261102-101500-ab12cd","ok":true,"aktionen":[{"nr":1,"aktion":"start","ok":true,"gestartet":"powershell.exe","ms":120},…],
 "bilder":["20261102-101500-ab12cd-4.png"],"ms":1480,"vorne":"Windows PowerShell","riegel":null,"stand":"2026-11-02-nur-topstepx","zeit":"2026-11-02 10:15:01"}
```

## Sperre: nur TopstepX (Finn 02.11.2026 05:55)
> „Die Klicksperre kannst du aufheben. In TradingView darfst du klicken. In TopstepX nichts klicken, nur Fotos und zugucken.“

Das ersetzt die Erlaubt-Liste von 04:42.

**Regel, die der Agent nicht prüfen kann: Der Lotse setzt, ändert und schließt keine Orders oder Positionen.** Ein Order-Knopf in TradingView oder MT5 ist für den Agenten nur ein Punkt im Fenster, und in TradingView kann schon ein Klick eine Order auslösen. Darum dort nur klicken, wenn klar ist, was unter dem Punkt liegt, und vorher ein Foto ansehen.

**Hart gesperrt** für `klick`, `maus`, `scroll`, `tasten`, `schliessen`, `vorholen`, geprüft am Vordergrund UND am Fenster unter dem Zielpunkt:
- **TopstepX:** Titel mit „topstep“ oder Kurs-Titel wie „NQZ26 $28,677.00 ▲ +0.50%“.
- **Puls-Chrome mit TopstepX vorn:** Der Fenstertitel wird in der CDP-Liste (Port 9333) gesucht, die Adresse des Tabs entscheidet. Passt kein Tab, wird die Liste einmal frisch gelesen, weil der Kurs im Titel läuft. Passt danach keiner oder ist CDP nicht lesbar: gesperrt.
- **Tab-Leiste und Adressleiste des Puls-Chrome:** Dort kann ein hinterer TopstepX-Tab liegen, auch sein ×.
- **Betriebs-Konsolen** (Titel mit copier, panel, prophos, reader, puls, polar, order_bot, mt5-update): keine Handelssperre, ein Klick hält dort per QuickEdit das Programm an.
- **Während eines Laufs** (`puls_handlauf.lock` jünger als 15 min oder `/api/beschaeftigt` belegt) gehen überall nur `foto`, `tabs`, `fenster`, `warte`. Geprüft wird vor der Aktion und nochmal direkt vor jedem Senden, beim Tippen je Paket. Das Panel meldet auch kurze Aufrufe als belegt, dann bricht eine Eingabe mit „Riegel“ ab und wird einfach wiederholt. Antwortet das Panel nicht, gilt das als Lauf. Lehnt der Port ab, läuft das Panel nicht, also auch kein Lauf.

**Bleibt außerdem:**
- `tasten` tippt nur, wenn das Vordergrundfenster den Titel aus `fenster` trägt. Beim Tippen wird vor jedem Paket neu geprüft.
- Schließ-Kombis (`ctrl+w`, `alt+f4` …) und `schliessen` gehen nie an einen Browser, `schliessen` auch nicht an Windows Terminal: Hinten kann ein anderer Tab liegen.
- `start` nimmt nur Explorer, Konsolen und `ms-settings:`, kein Browser: Er könnte im Puls-Chrome landen oder einen zweiten Prophos-Tab öffnen.
- Ein Auftrag mit `puls_ok` oder `browser_ok` wird ganz abgelehnt, auch mit `false`.
- `do.sh` schickt vor Eingaben eine Probe und sendet nichts an einen Agenten ohne `stand`.

**Foto eines hinteren Tabs:** `foto` mit `tab` ruft nur `Page.captureScreenshot` auf dem Tab, ohne Tabwechsel. Das ist der Weg für „bei TopstepX zugucken“. Verweigert wird es im Lauf und bei ausgeschaltetem Panel. Nur Tabs des Puls-Chrome.

### Was die Sperre NICHT abdeckt
- **Order-Knöpfe** in TradingView, MT5 und Prophos (siehe Regel oben).
- **SSH-Befehle mit Admin-Rechten** (`pc.sh`): Sie können alles, auch den Agenten beenden oder diese Datei ändern.
- **Panel-Aufrufe:** Finn 02.11.2026: „Der Lotse darf nicht selber aktiv klicken, aber der Puls-Bot darf. Der Lotse darf dem Puls-Bot Aufgaben geben.“ `/api/tsx-lesen` und `/api/tsx-konto` sind erlaubt und klicken über Puls. **Scharfe Orders (`scharf:true`) löst der Lotse nie aus.** Auch das ist nur Regel.
- **TopstepX in einem anderen Chrome oder in einem nicht erkannten Puls-Chrome:** Ohne CDP ist nur der Titel des aktiven Tabs sichtbar. Ein Tab, dessen Titel nichts von TopstepX verrät, wäre dort nicht erkannt. Das betrifft ein Puls-Chrome, wenn nichts auf Port 9333 lauscht und `puls_fenster.json` alt ist.
- **Zeitfenster:** Zwischen letzter Prüfung und Windows-Eingabe liegen wenige Millisekunden. Kommt genau dann TopstepX nach vorn, trifft die Eingabe dieses.

## Prüfen
- Agent läuft? `pc.sh <pc> -- "(Get-ScheduledTask 'Prophos Agent').State; Get-Content C:\mt5-copier\fernzugriff\agent.log -Tail 5"`
- Nach einem erneuten `setup-pc.ps1` (kopiert `agent\` neu): `agent-aufgabe.ps1` nochmal, damit der neue Code läuft.
- Läuft der neue Stand? Jedes Ergebnis trägt `"stand"`, hier `2026-11-02-nur-topstepx`. Probe: `do.sh <pc> '{"aktionen":[{"aktion":"warte","ms":1}]}'`.
- Selbsttest am Mac, ohne Windows: `python3 pc-fernzugriff/agent/selbsttest_sperre.py`. Nur auf echtem Windows prüfbar: dass der Titel des Puls-Chrome-Fensters den Tab in der CDP-Liste trifft (sonst ist es immer gesperrt), dass `vorholen` durchkommt, dass das Panel-Aus-Erkennen unter 3 s bleibt und dass ein hinterer TradingView-Tab ein aktuelles Bild liefert. `fenster` zeigt je Fenster `erlaubt`, das zuerst am Pilot-PC ansehen.
- Nur `agent.py` aktualisieren, ohne Puls zu stören (nicht auf Windows getestet). Vom Mac per SSH aus einem Checkout auf origin/main, nie von pages.dev. Es startet nur der Agent neu, `setup-pc.ps1` ist dafür nicht nötig (es startet sshd neu):
  Der Befehl steht bewusst ganz links: `<<'BLOCK'` verlangt seine Endmarke am Zeilenanfang.

```bash
pc=pc-xxxxxx; hash=$(shasum -a 256 pc-fernzugriff/agent/agent.py | cut -d' ' -f1)
scp pc-fernzugriff/agent/agent.py "$pc:C:/mt5-copier/fernzugriff/agent/agent.py.neu" || scp -O pc-fernzugriff/agent/agent.py "$pc:C:/mt5-copier/fernzugriff/agent/agent.py.neu"
bash pc-fernzugriff/mac/pc.sh "$pc" -- "$(sed "s/HASHWERT/$hash/" <<'BLOCK'
$b = Invoke-RestMethod -TimeoutSec 5 http://127.0.0.1:8770/api/beschaeftigt; if(-not $b.frei){ throw 'Panel belegt, spaeter nochmal' }
if(Get-ChildItem C:\mt5-copier\fernzugriff\auftraege\*.lauf -ErrorAction SilentlyContinue){ throw 'Auftrag laeuft' }
$z = 'C:\mt5-copier\fernzugriff\agent\agent.py'
if((Get-FileHash "$z.neu" -Algorithm SHA256).Hash -ne 'HASHWERT'){ throw 'Hash falsch, nichts ersetzt' }
Stop-ScheduledTask -TaskName 'Prophos Agent' -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" | Where-Object { $_.CommandLine -match 'fernzugriff\\agent\\agent\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
for($i = 0; $i -lt 20 -and (Get-ScheduledTask -TaskName 'Prophos Agent').State -eq 'Running'; $i++){ Start-Sleep -Milliseconds 500 }
try { Move-Item -Force "$z.neu" $z } finally { Start-ScheduledTask -TaskName 'Prophos Agent' }
'erledigt'
BLOCK
)"
```

  Den Beleg liefert danach `do.sh <pc> '{"aktionen":[{"aktion":"warte","ms":1}]}'` mit dem Feld `stand`.
