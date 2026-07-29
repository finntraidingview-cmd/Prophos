@echo off
title Prophos lokal (Topstep laeuft ueber DIESEN PC)
cd /d "%~dp0"

REM Frontend immer live von pages.dev holen -> auf diesem PC veraltet nie etwas.
REM Zum Abschalten (lokale prophos.html benutzen): naechste Zeile mit REM davor deaktivieren.
set PROPHOS_FRONTEND=https://prophos.pages.dev/prophos

echo =========================================================
echo  Prophos-Backend lokal
echo  Oberflaeche: live von pages.dev (immer aktuell)
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
