@echo off
rem Prophos TV-Verbinder starten (Windows, 28.08.2026) — Orbit
rem Liest den Reader-Stand (Port 8790) und schreibt das PROPHOS1-CSV,
rem aus dem der Copier (C:\mt5-copier) den Fusion-Hedge spiegelt.
rem Reihenfolge egal — der Verbinder wartet geduldig auf Reader und Copier.
cd /d "%~dp0"
title Prophos TV-Verbinder

rem Selbst-Update wie in start-reader.bat (30.08.2026) — Begruendung dort.
rem verbinder.config.json bleibt UNBERUEHRT: die gehoert dem PC.
call :update

python tv_verbinder.py
if errorlevel 1 (
  echo.
  echo Start fehlgeschlagen — Meldung oben lesen ^(fehlt verbinder.config.json?^)
  pause
)
exit /b

:update
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue';$t='';try{$t=(Get-Content 'feed_token.txt' -TotalCount 1 -EA Stop).Trim()}catch{};$r='https://web-production-bec81.up.railway.app/code/datei/tv-reader/';$b='https://raw.githubusercontent.com/finntraidingview-cmd/Prophos/main/tv-reader/';foreach($f in @('tv_verbinder.py','tv_snapshot.py')){$ok=$false;if($t){try{Invoke-WebRequest ($r+$f) -Headers @{'X-Code-Token'=$t} -OutFile ($f+'.newc') -TimeoutSec 25 -UseBasicParsing;$ok=$true}catch{}};if(-not $ok){try{Invoke-RestMethod ($b+$f) -OutFile ($f+'.newc') -TimeoutSec 25}catch{}}}"
call :swap tv_verbinder.py 4000
call :swap tv_snapshot.py 4000
exit /b

:swap
if not exist "%~1.newc" exit /b
for %%F in ("%~1.newc") do if %%~zF LSS %~2 (del "%~1.newc" & exit /b)
if exist "%~1" copy /y "%~1" "%~1.prev" >nul
move /y "%~1.newc" "%~1" >nul
exit /b
