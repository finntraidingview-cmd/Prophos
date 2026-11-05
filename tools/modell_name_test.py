"""MK1b (05.11.2026): Hilfe für Selbsttests, die nur einzelne Funktionen aus app.py per exec(…, ns) ausführen.

app.py nennt Modelle seit MK1b über die zentrale Tabelle MODELL_NAME (Echo, Echo V2, Orbit, Orbit V2, Orbit Prio 2, Nova, Topstep V2,
Winning Day …). Ein exec-Ausschnitt ohne diese Zeile kennt den Namen nicht (NameError). Der Import dieser Datei liest die Tabelle aus
app.py (eine Zeile, ast.literal_eval — nichts ausgeführt) und legt sie als builtins.MODELL_NAME ab: jeder exec-Namensraum findet sie
dort, ohne dass jeder Test seinen Namensraum einzeln ergänzen muss. Tests, die app.py ganz importieren, nutzen ohnehin deren eigene.
Kein Selbsttest (Name ohne selftest_), nur lesen.
"""
import ast
import builtins
import os
import re

_APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
MODELL_NAME = ast.literal_eval(re.search(r"^MODELL_NAME = (\{.*\})\s*$", open(_APP, encoding="utf-8").read(), re.M).group(1))
builtins.MODELL_NAME = MODELL_NAME
