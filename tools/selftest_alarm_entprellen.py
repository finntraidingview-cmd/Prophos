#!/usr/bin/env python3
"""Selbsttest ALARM-ENTPRELLEN (30.10.2026, Triage Slave 1, Master: „kleine Alarm-Fixes in einem Commit"):
#3 „Konto weg … war schon archiviert" ohne Push (konto_weg_push_still), #2b Entprellung über alarm_log.schluessel statt nur im Speicher
(alarm_im_log_filter + Verdrahtung in alarm_tick und skript_wacht_tick), #7 Nova ohne SL/TP höchstens 2 Meldungen je Plan.
Aufruf:  python3 tools/selftest_alarm_entprellen.py"""
import os
import re
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = open(os.path.join(W, "app.py"), encoding="utf-8").read()
fehler = 0


def soll(name, ok):
    global fehler
    print(("ok   " if ok else "FEHL ") + name)
    fehler += 0 if ok else 1


def block(name):
    i = APP.index(f"\ndef {name}(") + 1
    return APP[i:APP.find("\n\n\n", i)]


ns = {}
exec(block("konto_weg_push_still") + "\n" + block("alarm_im_log_filter"), ns)
still, filt = ns["konto_weg_push_still"], ns["alarm_im_log_filter"]

# #3
soll("war schon archiviert (kein Urteil, nicht archiviert) → still", still("", False) is True and still(None, None) is True)
soll("eben archiviert → Push", still("", True) is False)
soll("Urteil bestanden / prüfen → Push", still("bestanden", False) is False and still("pruefen", False) is False)
km = block("konto_weg_melden")
soll("Route: still vor der Push-Schleife, Spur bleibt", km.index("konto_weg_push_still(") < km.index("push_an_user(") and "still (schon archiviert)" in km)

# #2b
soll("Filter: Schlüssel mit „|“ in Anführungszeichen, sortiert, doppelte einmal",
     filt(["b|x|1", "a|y", "a|y"]) == 'in.("a|y","b|x|1")')
soll("Filter: leer / None → None, Schlüssel mit \" oder \\ fallen weg", filt([]) is None and filt([None, ""]) is None
     and filt(['a"b', "c\\d", "ok"]) == 'in.("ok")')
im = block("alarm_im_log")
soll("alarm_im_log: Lesefehler → None (dann wie bisher senden)", "return None" in im and "except Exception" in im)
at = block("alarm_tick")
soll("alarm_tick: vor dem Senden alarm_log der letzten 24 h, Gefundenes nur merken",
     "alarm_im_log([ev[0] for ev in evs], 86400)" in at and "if schon and key in schon:" in at
     and at.index('_alarm["gemeldet"][key] = time.time()') < at.index("if schon and key in schon:"))
sw = block("skript_wacht_tick")
soll("Skript-Wache: userscript_alt / tsx_auge_alt über alarm_log (24 h) entprellt",
     'f"userscript|{pc}|{soll}"' in sw and 'f"tsx_auge|{pc}|{soll_tsx}"' in sw and "SKRIPT_WACHT_WIEDER_S)" in sw
     and sw.index("alarm_im_log(") < sw.index('alarm_senden(3, "userscript_alt"'))

# #7
soll("Nova ohne SL/TP: Schlüssel-Zähler höchstens 1 (= 2 Meldungen je Plan)",
     re.search(r'f"\{pid\}\|ohne_sltp\|\{min\(int\(s // ALARM_ERINNERN_S\), 1\)\}"', APP) is not None)
print("ALLE OK" if not fehler else f"{fehler} FEHLER")
sys.exit(1 if fehler else 0)
