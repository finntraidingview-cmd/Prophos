@echo off
title MT5-Hedge-Copier (alle Master)
cd /d "%~dp0"

echo ==========================================================
echo  MT5-Hedge-Copier - EIN Prozess fuer ALLE config*.json
echo  Duplikum laeuft davon unbeeinflusst weiter.
echo  Modus steht pro Master in seiner config (Start: "dryrun").
echo  Fenster zu = Copier aus.
echo ==========================================================
echo.

:loop
python copier.py
echo.
echo [%date% %time%] Copier beendet - Neustart in 10 Sekunden...
echo (Absicht bei Modus-/Config-Aenderung: beim Neustart laufen alle
echo  Startpruefungen erneut. Fenster schliessen beendet endgueltig.)
timeout /t 10 /nobreak >nul
goto loop
