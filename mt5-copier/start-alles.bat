@echo off
title Prophos-Start
rem Ein Klick startet den ganzen Stack: Copier-Fenster + Panel-Fenster + Backend.
rem Das Hedge-Terminal startet der Copier selbst, falls es nicht laeuft.
rem NUR EINMAL klicken -- laufende Instanzen schuetzen sich selbst
rem (Copier: Status-Sperre, Panel: Port belegt, Backend: Port-Probe).
cd /d "%~dp0"

rem ── Vorpruefung (01.09.2026, Finns neuer PC) ────────────────────────────
rem Bisher hat dieser Starter blind drei cmd-Fenster aufgemacht. Fehlt auf
rem einem frischen Rechner eine Voraussetzung, sterben die drei sofort MIT
rem ihrem Fehlertext -- uebrig bleibt ein PC, auf dem "einfach nichts
rem passiert". Das ist der teuerste Zustand, den eine Software haben kann:
rem sie kennt den Grund und zeigt ihn niemandem.
where python >nul 2>&1
if errorlevel 1 (
  echo.
  echo   ============================================================
  echo    PYTHON FEHLT auf diesem PC.
  echo   ============================================================
  echo   Backend, Panel und Copier sind Python-Programme -- ohne Python
  echo   startet keines davon. Auf einem neuen Rechner ist das der
  echo   Normalfall, es ist nichts kaputt.
  echo.
  echo   Eine Taste druecken = Python jetzt installieren.
  echo   Fenster schliessen  = nichts tun.
  echo.
  pause
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  echo.
  echo   Installation durch. WICHTIG: dieses Fenster schliessen und
  echo   start-alles.bat erneut doppelklicken -- der Suchpfad fuer python
  echo   wird erst in einem NEUEN Fenster wirksam.
  echo.
  pause
  exit /b
)
if not exist "start-prophos.bat" (
  echo.
  echo   ============================================================
  echo    FALSCHER ORDNER.
  echo   ============================================================
  echo   Neben start-alles.bat muessen start-prophos.bat, start-panel.bat
  echo   und start-copier.bat liegen. Hier liegt: %CD%
  echo.
  pause
  exit /b
)

rem ── Geschwister-.bat auffrischen, BEVOR sie starten (01.09.2026) ────────
rem Die drei Starter hatten nie ein Selbst-Update: sie laufen in Endlos-
rem schleifen, und eine LAUFENDE Batchdatei zu ersetzen ist unter Windows
rem undefiniert (cmd liest sie zeilenweise per Dateiposition weiter). Hier
rem ist der einzige sichere Moment -- gleich starten sie erst. Antwortet
rem trotzdem schon jemand auf 5000 oder 8770, laeuft der Stack bereits und
rem es wird NICHTS ersetzt.
set _frisch=1
call :portbelegt 5000
if not errorlevel 1 set _frisch=0
call :portbelegt 8770
if not errorlevel 1 set _frisch=0
if "%_frisch%"=="1" call :bat_auffrischen
if "%_frisch%"=="0" echo   (Panel/Backend laufen schon - Starter-Dateien bleiben unangetastet)

start "MT5-Hedge-Copier" cmd /c start-copier.bat
start "Copier-Panel" cmd /c start-panel.bat
start "Prophos-Backend" cmd /c start-prophos.bat
rem Orbit-Dateien auffrischen, BEVOR Reader/Verbinder starten (30.08.2026,
rem Finns Ansage "kannst du nicht alle Sachen in start-alles reinmachen").
rem Hintergrund: C:\tv-reader hatte nie ein Selbst-Update -- der Ordner lag
rem zwei Wochen auf dem Stand des Installationstags, waehrend das Repo lief.
rem Das erzeugte ein Versionspaar, das nie jemand getestet hat (Userscript 0.3
rem gegen einen reader-server ohne /bedienfeld -- der nahm die Geometrie als
rem Positionsstand und meldete "flat" mit frischem Zeitstempel).
rem BEWUSST nur die .py-Dateien: die werden von python beim Start EINMAL
rem gelesen, ein Austausch ist gefahrlos. Die .bat dort werden hier NICHT
rem angefasst -- sie koennten in diesem Moment selbst laufen, und eine
rem laufende Batchdatei zu ueberschreiben ist unter Windows undefiniert.
rem Sie halten sich seit .190 selbst aktuell (Update in ihrem eigenen Start).
rem Reader-Ordner (01.10.2026): alt C:\tv-reader, seit der Userscript-Einrichtung per PowerShell C:\Prophos\tv-reader
set "_tvr=C:\tv-reader"
if not exist "C:\tv-reader\start-reader.bat" if exist "C:\Prophos\tv-reader\start-reader.bat" set "_tvr=C:\Prophos\tv-reader"
if exist "%_tvr%\reader-server.py" (
  powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue';$b='https://raw.githubusercontent.com/finntraidingview-cmd/Prophos/main/tv-reader/';$d='%_tvr%\';foreach($f in @('reader-server.py','tv_verbinder.py','tv_snapshot.py')){try{Invoke-RestMethod ($b+$f) -OutFile ($d+$f+'.newa') -TimeoutSec 25}catch{}}"
  call :swap "%_tvr%\reader-server.py" 4000
  call :swap "%_tvr%\tv_verbinder.py" 4000
  call :swap "%_tvr%\tv_snapshot.py" 4000
)

rem Orbit (28.08.2026, Fund von PC 1): "Alles neu starten" killt ALLE
rem python.exe -- auf PCs mit TV-Reader starben Reader + Verbinder mit und
rem blieben tot, weil sie hier fehlten. Deshalb: mitstarten, wenn der
rem Ordner existiert. PCs ohne tv-reader bleiben unberuehrt.
rem Reader nur, wenn er nicht schon laeuft (Port 8790) — sonst kreiste ein zweites Fenster im 10-s-Neustart
call :portbelegt 8790
if errorlevel 1 if exist "%_tvr%\start-reader.bat" (
  start "Prophos TV-Reader" /d "%_tvr%" cmd /c start-reader.bat
)
rem TV-Verbinder NICHT mehr mitstarten (02.10.2026): er speist die alte Copier-Instanz „tvplus" (Echo + / alter Orbit vor dem
rem 28.08.) und spiegelte bei Moritz einen Orbit-V2-Trade OHNE Hedge als ungewollten Fusion-Hedge (3,69 Lot). Wer ihn wirklich braucht,
rem startet start-verbinder.bat von Hand.
rem (15.08.2026) Nur PCs mit ALTEM Backend-Setup betrifft das -- seit 01.09.2026
rem steht der Hinweis deshalb hinter einer Pruefung, statt auf jedem frischen
rem Rechner Ratlosigkeit zu stiften (Finn am neuen PC: "warum geht es nicht mehr").
if exist "C:\prophos" (
  echo.
  echo   ACHTUNG, alter Backend-Ordner C:\prophos gefunden:
  echo   Nicht nur das alte start-local-backend-Fenster schliessen -- auch die
  echo   Aufgabenplanungs-Task des alten Starts LOESCHEN (Aufgabenplanung
  echo   oeffnen, Task suchen, loeschen). Sonst rennen nach dem naechsten
  echo   Reboot ZWEI app.py um Port 5000, und das alte (nie updatende) gewinnt.
)

echo.
echo   Warte auf das Backend (Port 5000)...
echo   Beim ERSTEN Start auf einem neuen PC dauert das ein paar Minuten --
echo   das Backend-Fenster zieht sich flask/requests/signalrcore selbst nach.
echo.
call :warten
if errorlevel 1 (
  echo.
  echo   ============================================================
  echo    BACKEND LAEUFT NICHT.
  echo   ============================================================
  echo   Der Grund steht im Fenster "Prophos-Backend" -- das Fenster hier
  echo   bleibt offen, damit nichts mehr wegklappt.
  echo.
  echo   Ist das Fenster "Prophos-Backend" gar nicht da, ist es sofort
  echo   gestorben. Dann in diesem Ordner start-prophos.bat einzeln
  echo   doppelklicken: dort bleibt der Fehlertext stehen.
  echo.
  pause
  exit /b
)
echo.
echo   ============================================================
echo    Backend laeuft:  http://localhost:5000
echo    Copier-Panel:    http://127.0.0.1:8770
echo   ============================================================
echo.
rem Gezielt CHROME statt "start <url>" (01.09.2026, Finns Ansage): "start"
rem nimmt den Standardbrowser, und der ist auf diesen PCs Edge. Nur wenn
rem Chrome nirgends liegt, bleibt der Standardbrowser als Rueckfalllinie --
rem lieber der falsche Browser als gar keine Oberflaeche.
set _chrome=
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set _chrome=%ProgramFiles%\Google\Chrome\Application\chrome.exe
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set _chrome=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set _chrome=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe
if defined _chrome start "" "%_chrome%" "http://localhost:5000"
if not defined _chrome start "" "http://localhost:5000"
rem Puls-Chrome gleich mit oeffnen (01.10.2026, Finn: „was passiert, wenn der PC mal ausgeht") — darin laeuft das
rem Orbit-Userscript, ohne Puls-Chrome schliesst nach einem Neustart nur Radar. Nur auf PCs mit Puls (order_bot.py + pc_id.json);
rem laeuft es schon, kehrt „augen start" sofort zurueck.
if exist "order_bot.py" if exist "pc_id.json" start "Puls-Chrome" /min cmd /c "timeout /t 15 >nul & python order_bot.py augen start"
timeout /t 8 >nul
exit /b

:portbelegt
rem Antwortet auf 127.0.0.1:%1 jemand? errorlevel 0 = ja.
python -c "import socket,sys;s=socket.socket();s.settimeout(1);sys.exit(0 if s.connect_ex(('127.0.0.1',%1))==0 else 1)" >nul 2>&1
exit /b

:bat_auffrischen
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue';$b='https://raw.githubusercontent.com/finntraidingview-cmd/Prophos/main/mt5-copier/';foreach($f in @('start-copier.bat','start-panel.bat','start-prophos.bat')){try{Invoke-RestMethod ($b+$f) -OutFile ($f+'.newa') -TimeoutSec 25}catch{}}"
call :swap "start-copier.bat" 500
call :swap "start-panel.bat" 500
call :swap "start-prophos.bat" 500
exit /b

:warten
rem Bis zu 90 Sekunden auf den lauschenden Port 5000 warten (01.09.2026).
rem Vorher hat dieser Starter drei Fenster aufgemacht und sich nach 15
rem Sekunden selbst geschlossen -- ob davon etwas ueberlebt hat, sah man nie.
rem Genau das ist Finn am neuen PC passiert: "eine Datei doppelklicken und es
rem faehrt hoch" hat gestimmt, solange die Voraussetzungen da waren, und ist
rem stillschweigend nichts getan, als sie fehlten. Ein Starter, der nicht
rem nachsieht, ob er etwas gestartet hat, ist nur ein Wunsch.
rem Geprueft wird mit python statt mit netstat: die Zustandsspalte von netstat
rem ist UEBERSETZT ("ABHOEREN" auf deutschem Windows), ein Filter auf
rem "LISTENING" haette hier nie gegriffen und immer Misserfolg gemeldet.
rem Ein echter Verbindungsversuch beweist ausserdem mehr als ein offener Port:
rem er beweist, dass jemand ANNIMMT. Python ist an dieser Stelle sicher da,
rem die Vorpruefung oben laesst sonst gar nicht durch.
set _n=0
:warteschleife
python -c "import socket,sys;s=socket.socket();s.settimeout(1);sys.exit(0 if s.connect_ex(('127.0.0.1',5000))==0 else 1)" >nul 2>&1
if not errorlevel 1 exit /b 0
set /a _n+=1
if %_n% GEQ 18 exit /b 1
echo   ... noch nicht da (Versuch %_n% von 18)
timeout /t 5 /nobreak >nul
goto warteschleife

:swap
rem Ersetzt %1 durch %1.newa, wenn der Download mindestens %2 Bytes hat.
rem Gleiche Mechanik wie in start-copier.bat, nur mit eigener Endung (.newa),
rem damit sich die Update-Schleifen nicht gegenseitig die Dateien wegziehen.
if not exist "%~1.newa" exit /b
for %%F in ("%~1.newa") do if %%~zF LSS %~2 (del "%~1.newa" & exit /b)
if exist "%~1" copy /y "%~1" "%~1.prev" >nul
move /y "%~1.newa" "%~1" >nul
exit /b
