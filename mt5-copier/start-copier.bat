@echo off
title MT5-Hedge-Copier (alle Master)
cd /d "%~dp0"

echo ==========================================================
echo  MT5-Hedge-Copier - EIN Prozess fuer ALLE config*.json
echo  Selbst-Update: laedt vor jedem Start die aktuellen
echo  Dateien von GitHub (ersetzt nur vollstaendige Downloads,
echo  Vorversion bleibt als .prev liegen).
echo  Fenster zu = Copier aus.
echo ==========================================================
echo.

:loop
call :update
python copier.py
echo.
echo [%date% %time%] Copier beendet - Neustart in 10 Sekunden...
timeout /t 10 /nobreak >nul
goto loop

:update
rem Downloads in .newc-Dateien; bei Fehlern bleibt einfach der alte Stand.
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue';$b='https://raw.githubusercontent.com/finntraidingview-cmd/Prophos/main/mt5-copier/';foreach($f in @('copier.py','provision.py','VERSION','ProphosHedgeReader.mq5')){try{Invoke-RestMethod ($b+$f) -OutFile ($f+'.newc') -TimeoutSec 25}catch{}}"
call :swap copier.py 10000
call :swap provision.py 5000
call :swap VERSION 3
call :swap ProphosHedgeReader.mq5 1000
exit /b

:swap
rem Ersetzt %1 durch %1.newc, wenn der Download mindestens %2 Bytes hat.
if not exist "%~1.newc" exit /b
for %%F in ("%~1.newc") do if %%~zF LSS %~2 (del "%~1.newc" & exit /b)
if exist "%~1" copy /y "%~1" "%~1.prev" >nul
move /y "%~1.newc" "%~1" >nul
exit /b
