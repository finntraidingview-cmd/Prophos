@echo off
rem Prophos TV-Reader-Empfaenger starten (Windows, 28.08.2026)
rem Doppelklick reicht. Fenster offen lassen — die Live-Zeile zeigt, was der
rem Reader sieht. Schliessen beendet den Empfaenger (der Tampermonkey-Badge
rem in TradingView wird dann orange: "Copier OFFLINE").
cd /d "%~dp0"
title Prophos TV-Reader

rem Selbst-Update (30.08.2026, Fund an Finns PC): der Copier holt sich seine
rem Dateien seit dem 14.08. selbst, der tv-reader-Ordner NICHT — er lag zwei
rem Wochen auf dem Stand vom Installationstag, waehrend das Repo weiterlief.
rem Aufgefallen ist es, als Userscript 0.3 an einen reader-server ohne
rem /bedienfeld sendete. Gleiches Muster wie start-copier.bat: Download in
rem .newc, Uebernahme nur bei plausibler Groesse, alter Stand als .prev.
rem Einmalig beim Start (dieser Prozess startet sich nicht selbst neu).
call :update

python reader-server.py
if errorlevel 1 (
  echo.
  echo Fehler beim Start — ist Python installiert? ^("python --version" pruefen^)
  pause
)
exit /b

:update
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue';$b='https://raw.githubusercontent.com/finntraidingview-cmd/Prophos/main/tv-reader/';foreach($f in @('reader-server.py')){try{Invoke-RestMethod ($b+$f) -OutFile ($f+'.newc') -TimeoutSec 25}catch{}}"
call :swap reader-server.py 4000
exit /b

:swap
rem Ersetzt %1 durch %1.newc, wenn der Download mindestens %2 Bytes hat.
if not exist "%~1.newc" exit /b
for %%F in ("%~1.newc") do if %%~zF LSS %~2 (del "%~1.newc" & exit /b)
if exist "%~1" copy /y "%~1" "%~1.prev" >nul
move /y "%~1.newc" "%~1" >nul
exit /b
