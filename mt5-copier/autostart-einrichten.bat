@echo off
rem EINMAL ausfuehren: legt einen Starter in den Windows-Autostart-Ordner.
rem Ab dann startet der komplette Stack (Copier + Panel + Hedge-Terminal)
rem bei jeder PC-Anmeldung von selbst.
rem Entfernen: die Datei prophos-copier-autostart.bat im Startup-Ordner loeschen.
cd /d "%~dp0"
set "SU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
(
  echo @echo off
  echo start "" "%~dp0start-alles.bat"
) > "%SU%\prophos-copier-autostart.bat"
echo.
echo Autostart eingerichtet:
echo   %SU%\prophos-copier-autostart.bat
echo.
echo Ab der naechsten Anmeldung startet alles von selbst.
echo Jetzt sofort starten: start-alles.bat doppelklicken.
pause
