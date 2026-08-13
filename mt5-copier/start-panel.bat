@echo off
title Copier-Panel
cd /d "%~dp0"

echo =========================================================
echo  Prophos Copier-Panel
echo  Im Browser oeffnen:  http://127.0.0.1:8770
echo  Selbst-Update aktiv. Nur lokal erreichbar.
echo  Fenster zu = Panel aus (die Copier laufen weiter).
echo =========================================================
echo.

start "" http://127.0.0.1:8770

:loop
call :update
python panel.py
echo.
echo [%date% %time%] Panel beendet - Neustart in 10 Sekunden...
timeout /t 10 /nobreak >nul
goto loop

:update
rem Downloads in .newp-Dateien (eigene Endung, damit sich Copier- und
rem Panel-Schleife nicht in die Quere kommen).
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue';$b='https://raw.githubusercontent.com/finntraidingview-cmd/Prophos/main/mt5-copier/';foreach($f in @('panel.py','VERSION')){try{Invoke-RestMethod ($b+$f) -OutFile ($f+'.newp') -TimeoutSec 25}catch{}}"
call :swap panel.py 10000
call :swap VERSION 3
exit /b

:swap
if not exist "%~1.newp" exit /b
for %%F in ("%~1.newp") do if %%~zF LSS %~2 (del "%~1.newp" & exit /b)
if exist "%~1" copy /y "%~1" "%~1.prev" >nul
move /y "%~1.newp" "%~1" >nul
exit /b
