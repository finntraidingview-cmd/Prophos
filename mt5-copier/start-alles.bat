@echo off
rem Ein Klick startet den ganzen Stack: Copier-Fenster + Panel-Fenster + Backend.
rem Das Hedge-Terminal startet der Copier selbst, falls es nicht laeuft.
rem NUR EINMAL klicken -- laufende Instanzen schuetzen sich selbst
rem (Copier: Status-Sperre, Panel: Port belegt, Backend: Port-Probe).
cd /d "%~dp0"
start "MT5-Hedge-Copier" cmd /c start-copier.bat
start "Copier-Panel" cmd /c start-panel.bat
start "Prophos-Backend" cmd /c start-prophos.bat
rem Echo + (28.08.2026, Fund von PC 1): "Alles neu starten" killt ALLE
rem python.exe -- auf PCs mit TV-Reader starben Reader + Verbinder mit und
rem blieben tot, weil sie hier fehlten. Deshalb: mitstarten, wenn der
rem Ordner existiert. PCs ohne tv-reader bleiben unberuehrt.
if exist "C:\tv-reader\start-reader.bat" (
  start "Prophos TV-Reader" cmd /c "C:\tv-reader\start-reader.bat"
)
if exist "C:\tv-reader\start-verbinder.bat" (
  start "Prophos TV-Verbinder" cmd /c "C:\tv-reader\start-verbinder.bat"
)
echo.
echo (15.08.2026) WICHTIG bei PCs mit ALTEM Backend-Setup (C:\prophos):
echo Nicht nur das alte start-local-backend-Fenster schliessen -- auch die
echo Aufgabenplanungs-Task des alten Starts LOESCHEN (Aufgabenplanung
echo oeffnen, Task suchen, loeschen). Sonst rennen nach dem naechsten
echo Reboot ZWEI app.py um Port 5000, und das alte (nie updatende) gewinnt.
echo.
timeout /t 15 >nul
