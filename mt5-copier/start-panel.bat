@echo off
title Copier-Panel
cd /d "%~dp0"

echo =========================================================
echo  Prophos Copier-Panel
echo  Im Browser oeffnen:  http://127.0.0.1:8770
echo  Nur lokal erreichbar. Prophos wird nicht angefasst.
echo  Fenster zu = Panel aus (die Copier laufen weiter).
echo =========================================================
echo.

start "" http://127.0.0.1:8770

:loop
python panel.py
echo.
echo [%date% %time%] Panel beendet - Neustart in 10 Sekunden...
timeout /t 10 /nobreak >nul
goto loop
