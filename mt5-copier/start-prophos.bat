@echo off
title Prophos-Backend
cd /d "%~dp0"

rem (15.08.2026, Etappe 3) Backend-Starter nach dem start-panel.bat-Muster:
rem app.py laeuft ab jetzt HIER (mt5-copier-Ordner) und updatet sich ueber die
rem Schleife selbst -- das alte C:\prophos-Setup (start-local-backend.bat ohne
rem Selbst-Update) ist damit abgeloest.

rem Frontend immer live von pages.dev holen -> auf diesem PC veraltet nie etwas.
rem Die lokale prophos.html ist NUR Offline-Reserve fuer den Fallback der
rem Root-Route in app.py (pages.dev nicht erreichbar).
set PROPHOS_FRONTEND=https://prophos.pages.dev/prophos

echo =========================================================
echo  Prophos-Backend lokal
echo  Oberflaeche: live von pages.dev (immer aktuell)
echo  Im Browser oeffnen:  http://localhost:5000
echo  Selbst-Update aktiv. Fenster zu = Backend aus.
echo =========================================================
echo.

:loop
call :update
python app.py
echo.
echo [%date% %time%] Backend beendet - Neustart in 10 Sekunden...
timeout /t 10 /nobreak >nul
goto loop

:update
rem (15.08.2026) Abhaengigkeiten still nachziehen -- idempotent und schnell,
rem wenn schon installiert. Ohne das crasht ein frischer PC in einer
rem Import-Neustart-Schleife: mt5-copier/ hat nie eine requirements.txt
rem durchlaufen, app.py braucht aber flask/requests/signalrcore.
python -m pip install flask requests signalrcore >nul 2>&1
rem Downloads in .newb-Dateien (eigene Endung, damit sich Copier-, Panel- und
rem Backend-Schleife nicht in die Quere kommen). ACHTUNG: app.py und
rem prophos.html liegen im Repo-ROOT, nicht unter mt5-copier/.
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue';$b='https://raw.githubusercontent.com/finntraidingview-cmd/Prophos/main/';foreach($f in @('app.py','prophos.html')){try{Invoke-RestMethod ($b+$f) -OutFile ($f+'.newb') -TimeoutSec 25}catch{}}"
call :swap app.py 100000
call :swap prophos.html 500000
exit /b

:swap
if not exist "%~1.newb" exit /b
for %%F in ("%~1.newb") do if %%~zF LSS %~2 (del "%~1.newb" & exit /b)
if exist "%~1" copy /y "%~1" "%~1.prev" >nul
move /y "%~1.newb" "%~1" >nul
exit /b
