@echo off
rem Ein Klick startet den ganzen Stack: Copier-Fenster + Panel-Fenster + Backend.
rem Das Hedge-Terminal startet der Copier selbst, falls es nicht laeuft.
rem NUR EINMAL klicken -- laufende Instanzen schuetzen sich selbst
rem (Copier: Status-Sperre, Panel: Port belegt, Backend: Port-Probe).
cd /d "%~dp0"
start "MT5-Hedge-Copier" cmd /c start-copier.bat
start "Copier-Panel" cmd /c start-panel.bat
start "Prophos-Backend" cmd /c start-prophos.bat
echo.
echo (15.08.2026) WICHTIG bei PCs mit ALTEM Backend-Setup (C:\prophos):
echo Nicht nur das alte start-local-backend-Fenster schliessen -- auch die
echo Aufgabenplanungs-Task des alten Starts LOESCHEN (Aufgabenplanung
echo oeffnen, Task suchen, loeschen). Sonst rennen nach dem naechsten
echo Reboot ZWEI app.py um Port 5000, und das alte (nie updatende) gewinnt.
echo.
timeout /t 15 >nul
