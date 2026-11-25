@echo off
title Prophos-Backend
cd /d "%~dp0"

rem (PS1, 25.11.2026, Finn: "Das Wissen darf nicht auf dem PC liegen") Starter fuer das
rem MINI-Backend. Diese Datei bekommen NUR PCs, die auf Railway in MINI_BACKEND_PCS
rem stehen -- Railway liefert sie ihnen unter dem Namen start-prophos.bat aus, darum
rem bleibt start-alles.bat unberuehrt. Alle anderen PCs behalten ihren Starter.
rem Unterschied zum alten Starter: statt app.py (58.000 Zeilen, Auto-Planer und
rem Firmenregeln) laeuft pc_backend.py -- es reicht nur durch. app.py und die lokale
rem prophos.html werden hier geloescht und nicht mehr geholt.
rem Not-Schalter: PC auf Railway aus der Liste nehmen -> die Abfrage unten sagt "alt",
rem diese Datei holt den alten Starter und uebergibt an ihn.

echo =========================================================
echo  Prophos-Backend lokal (Mini)
echo  Im Browser oeffnen:  http://localhost:5000
echo  Selbst-Update aktiv. Fenster zu = Backend aus.
echo =========================================================
echo.

:loop
call :wahl
if /i "%_wahl%"=="alt" call :zurueck
call :aufraeumen
call :update
if not exist pc_backend.py (
  echo [%date% %time%] pc_backend.py fehlt noch - kein Schluessel oder kein Netz. Neuer Versuch in 30 Sekunden...
  timeout /t 30 /nobreak >nul
  goto loop
)
python pc_backend.py
echo.
echo [%date% %time%] Backend beendet - Neustart in 10 Sekunden...
timeout /t 10 /nobreak >nul
goto loop

:wahl
rem Railway fragen, welches Backend dieser PC fahren soll. Die Antwort kommt ueber eine
rem Datei (kein for /f um einen PowerShell-Aufruf -- die Anfuehrungszeichen dort sind
rem eine Fehlerquelle). Nur eine KLARE Antwort "alt" schaltet zurueck; kein Netz, kein
rem Schluessel oder eine gesperrte ID aendern nichts.
set "_wahl="
if exist backend-wahl.txt del /q backend-wahl.txt >nul 2>&1
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue';$t='';try{$t=(Get-Content 'code_token.txt' -TotalCount 1 -EA Stop).Trim()}catch{};if($t){try{$j=Invoke-RestMethod 'https://web-production-bec81.up.railway.app/code/backend-wahl' -Headers @{'X-Code-Token'=$t} -TimeoutSec 15;$w=[string]$j.backend;if($w -eq 'alt' -or $w -eq 'mini'){Set-Content -Path 'backend-wahl.txt' -Value $w -Encoding ASCII}}catch{}}"
if exist backend-wahl.txt set /p _wahl=<backend-wahl.txt
exit /b

:zurueck
rem Not-Schalter: den ALTEN Starter holen (Railway liefert ihn wieder, sobald der PC
rem nicht mehr in der Liste steht) und an ihn uebergeben. Geprueft wird, dass es
rem wirklich der alte ist: er darf das Wort pc_backend NICHT enthalten. Liefert Railway
rem kurz noch diese Mini-Datei, wird sie verworfen -- sonst weiter mit dem Mini-Backend.
rem (Pruefer 25.11.2026: die erste Fassung suchte einen Text, den diese Datei selbst enthielt.)
if exist start-prophos-alt.bat del /q start-prophos-alt.bat >nul 2>&1
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue';$t='';try{$t=(Get-Content 'code_token.txt' -TotalCount 1 -EA Stop).Trim()}catch{};if($t){try{Invoke-WebRequest 'https://web-production-bec81.up.railway.app/code/datei/mt5-copier/start-prophos.bat' -Headers @{'X-Code-Token'=$t} -OutFile 'start-prophos-alt.bat' -TimeoutSec 25 -UseBasicParsing}catch{}}"
if not exist start-prophos-alt.bat exit /b
for %%F in ("start-prophos-alt.bat") do if %%~zF LSS 500 (del /q start-prophos-alt.bat & exit /b)
findstr /c:"pc_backend" start-prophos-alt.bat >nul 2>&1
if not errorlevel 1 (
  del /q start-prophos-alt.bat >nul 2>&1
  exit /b
)
echo [%date% %time%] Railway stellt diesen PC auf das alte Backend zurueck - uebergebe an den alten Starter.
start "Prophos-Backend" cmd /c start-prophos-alt.bat
exit

:aufraeumen
rem Was nicht mehr auf diesem PC liegen soll. Fehlt eine Datei, passiert nichts.
for %%F in (app.py app.py.prev app.py.newb prophos.html prophos.html.prev prophos.html.newb firm_rules.json) do if exist "%%F" del /q "%%F" >nul 2>&1
if exist __pycache__ del /q "__pycache__\app.*.pyc" >nul 2>&1
exit /b

:update
rem Abhaengigkeiten still nachziehen (idempotent), dann pc_backend.py frisch holen.
rem Download in .newb (eigene Endung wie beim alten Starter), erst nach der
rem Groessenpruefung ersetzen -- eine Fehlerantwort wird so nie zur Programmdatei.
python -m pip install flask requests >nul 2>&1
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue';$t='';try{$t=(Get-Content 'code_token.txt' -TotalCount 1 -EA Stop).Trim()}catch{};if($t){try{Invoke-WebRequest 'https://web-production-bec81.up.railway.app/code/datei/mt5-copier/pc_backend.py' -Headers @{'X-Code-Token'=$t} -OutFile 'pc_backend.py.newb' -TimeoutSec 25 -UseBasicParsing}catch{}}"
call :swap pc_backend.py 3000
exit /b

:swap
if not exist "%~1.newb" exit /b
for %%F in ("%~1.newb") do if %%~zF LSS %~2 (del "%~1.newb" & exit /b)
if exist "%~1" copy /y "%~1" "%~1.prev" >nul
move /y "%~1.newb" "%~1" >nul
exit /b
