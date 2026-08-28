@echo off
rem Prophos TV-Verbinder starten (Windows, 28.08.2026) — Orbit
rem Liest den Reader-Stand (Port 8790) und schreibt das PROPHOS1-CSV,
rem aus dem der Copier (C:\mt5-copier) den Fusion-Hedge spiegelt.
rem Reihenfolge egal — der Verbinder wartet geduldig auf Reader und Copier.
cd /d "%~dp0"
title Prophos TV-Verbinder
python tv_verbinder.py
if errorlevel 1 (
  echo.
  echo Start fehlgeschlagen — Meldung oben lesen ^(fehlt verbinder.config.json?^)
  pause
)
