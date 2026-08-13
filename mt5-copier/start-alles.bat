@echo off
rem Ein Klick startet den ganzen Stack: Copier-Fenster + Panel-Fenster.
rem Das Hedge-Terminal startet der Copier selbst, falls es nicht laeuft.
rem NUR EINMAL klicken — laufende Instanzen schuetzen sich selbst
rem (Copier: Status-Sperre, Panel: Port belegt).
cd /d "%~dp0"
start "MT5-Hedge-Copier" cmd /c start-copier.bat
start "Copier-Panel" cmd /c start-panel.bat
