@echo off
rem Ein Klick startet den ganzen Stack: Copier-Fenster + Panel-Fenster + Backend.
rem Das Hedge-Terminal startet der Copier selbst, falls es nicht laeuft.
rem NUR EINMAL klicken -- laufende Instanzen schuetzen sich selbst
rem (Copier: Status-Sperre, Panel: Port belegt, Backend: Port-Probe).
cd /d "%~dp0"
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
if exist "C:\tv-reader\reader-server.py" (
  powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue';$b='https://raw.githubusercontent.com/finntraidingview-cmd/Prophos/main/tv-reader/';$d='C:\tv-reader\';foreach($f in @('reader-server.py','tv_verbinder.py','tv_snapshot.py')){try{Invoke-RestMethod ($b+$f) -OutFile ($d+$f+'.newa') -TimeoutSec 25}catch{}}"
  call :swap "C:\tv-reader\reader-server.py" 4000
  call :swap "C:\tv-reader\tv_verbinder.py" 4000
  call :swap "C:\tv-reader\tv_snapshot.py" 4000
)

rem Orbit (28.08.2026, Fund von PC 1): "Alles neu starten" killt ALLE
rem python.exe -- auf PCs mit TV-Reader starben Reader + Verbinder mit und
rem blieben tot, weil sie hier fehlten. Deshalb: mitstarten, wenn der
rem Ordner existiert. PCs ohne tv-reader bleiben unberuehrt.
if exist "C:\tv-reader\start-reader.bat" (
  start "Prophos TV-Reader" cmd /c "C:\tv-reader\start-reader.bat"
)
if exist "C:\tv-reader\start-verbinder.bat" (
  start "Prophos TV-Verbinder" cmd /c "C:\tv-reader\start-verbinder.bat"
)
echo.
echo (15.08.2026) WICHTIG bei PCs mit ALTEM Backend-Setup (C:\prophos):
echo Nicht nur das alte start-local-backend-Fenster schliessen -- auch die
echo Aufgabenplanungs-Task des alten Starts LOESCHEN (Aufgabenplanung
echo oeffnen, Task suchen, loeschen). Sonst rennen nach dem naechsten
echo Reboot ZWEI app.py um Port 5000, und das alte (nie updatende) gewinnt.
echo.
timeout /t 15 >nul
exit /b

:swap
rem Ersetzt %1 durch %1.newa, wenn der Download mindestens %2 Bytes hat.
rem Gleiche Mechanik wie in start-copier.bat, nur mit eigener Endung (.newa),
rem damit sich die Update-Schleifen nicht gegenseitig die Dateien wegziehen.
if not exist "%~1.newa" exit /b
for %%F in ("%~1.newa") do if %%~zF LSS %~2 (del "%~1.newa" & exit /b)
if exist "%~1" copy /y "%~1" "%~1.prev" >nul
move /y "%~1.newa" "%~1" >nul
exit /b
