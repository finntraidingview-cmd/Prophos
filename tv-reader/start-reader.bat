@echo off
rem Prophos TV-Reader-Empfaenger starten (Windows, 28.08.2026)
rem Doppelklick reicht. Fenster offen lassen — die Live-Zeile zeigt, was der
rem Reader sieht. Schliessen beendet den Empfaenger (der Tampermonkey-Badge
rem in TradingView wird dann orange: "Copier OFFLINE").
cd /d "%~dp0"
title Prophos TV-Reader
python reader-server.py
if errorlevel 1 (
  echo.
  echo Fehler beim Start — ist Python installiert? ^("python --version" pruefen^)
  pause
)
