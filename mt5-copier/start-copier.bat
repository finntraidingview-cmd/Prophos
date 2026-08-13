@echo off
title MT5-Hedge-Copier (Testversion)
cd /d "%~dp0"

echo ==========================================================
echo  MT5-Hedge-Copier - EIGENSTAENDIGE Testversion
echo  Duplikum laeuft davon unbeeinflusst weiter.
echo  Modus steht in config.json (Start immer mit "dryrun").
echo  Fenster zu = Copier aus.
echo ==========================================================
echo.

python copier.py
echo.
echo Beendet. Fenster kann geschlossen werden.
pause
