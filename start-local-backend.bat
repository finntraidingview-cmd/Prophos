@echo off
title Prophos lokal (Topstep laeuft ueber DIESEN PC)
cd /d "%~dp0"

echo =========================================================
echo  Prophos-Backend lokal
echo  Danach im Browser oeffnen:  http://localhost:5000
echo  Fenster zu = Backend aus. Einfach minimieren.
echo =========================================================
echo.

:loop
python app.py
echo.
echo [%date% %time%] Backend beendet - Neustart in 10 Sekunden...
timeout /t 10 /nobreak >nul
goto loop
