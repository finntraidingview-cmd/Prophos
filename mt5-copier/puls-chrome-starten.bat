@echo off
rem Puls-Chrome (CDP, Etappe E0, 29.09.2026) fuer den einmaligen Login starten: eigenes Profil
rem %LOCALAPPDATA%\Prophos\puls-chrome, Port 9333 nur 127.0.0.1. Beruehrt weder das normale Chrome noch den Reader.
rem Danach im neuen Chrome-Fenster: TradingView einloggen, Handelspanel - Tradovate (Demo) - verbinden, "Remember me" an.
cd /d "%~dp0"
python order_bot.py augen start
echo.
echo Puls-Chrome ist offen. Jetzt dort einloggen. Diese Konsole kann zu.
pause
