@echo off
title Topstep-Agent
cd /d "%~dp0"

echo ===============================================
echo  Topstep-Agent - laeuft dauerhaft
echo  Fenster zu = Agent aus. Einfach minimieren.
echo ===============================================
echo.

:loop
python agent.py
echo.
echo [%date% %time%] Agent beendet - Neustart in 10 Sekunden...
timeout /t 10 /nobreak >nul
goto loop
