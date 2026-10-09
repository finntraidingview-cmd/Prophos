#!/usr/bin/env python3
"""Selbsttest Journal-Grund mit echten MT5-Zeilenformaten (mt5-copier/order_bot.py, 09.10.2026, Fall 08.10. 23:47 UTC Plan 1c3f7ecd:
F9-Dialog, BUY 2.7 NDX100 mit SL/TP, alle Klickwege ausgelöst, keine Position, Konto bei 90.002 $ an der Verlustgrenze).
Ergänzt tools/selftest_order_grund.py um das Tab-Format der Journal-Datei logs/JJJJMMTT.log, Störzeilen davor/danach und eine
echte UTF-16-Datei. Kein Terminal, keine Order.

Aufruf:  python3 tools/selftest_order_journal_echt.py"""
import os
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "mt5-copier"))
import order_bot as ob  # noqa: E402

OK = True


def check(bed, text):
    global OK
    print(("✓ " if bed else "✗ ") + text)
    OK = OK and bool(bed)


def s(hms):
    h, m, x = (int(v) for v in hms.split(":"))
    return h * 3600 + m * 60 + x


# Journal wie im Terminal (Tab-getrennt: Kennung, Stufe, Uhrzeit, Quelle, Text); Kontonummer als Platzhalter
ZEILEN = [
    "KP\t0\t03:40:01.112\tTrades\t'00000000': market sell 2.7 NDX100 sl: 31300.00 tp: 31000.00 [Trade disabled]",   # alter Lauf, andere Richtung
    "GH\t0\t03:47:50.210\tTrades\t'00000000': market buy 2.7 NDX100 sl: 30751.17 tp: 31042.20",                     # Anfrage, ohne Antwort
    "MN\t0\t03:47:50.344\tTrades\t'00000000': failed market buy 2.7 NDX100 sl: 30751.17 tp: 31042.20 [Trade disabled]",
    "QR\t0\t03:47:52.001\tNetwork\t'00000000': ping to current access point 12.34 ms",                              # Störzeile danach
]
jetzt = s("03:48:01")

j = ob.order_journal_grund(ZEILEN, "NDX100", "buy", jetzt)
check(j is not None and j[0] == "Trade disabled", "Fall 1c3f7ecd: failed market buy … [Trade disabled] wird gefunden")
check(j is not None and "failed market buy" in j[1], "die gefundene Zeile ist die Server-Antwort, nicht die Anfrage")
g = ob.order_grund_bestimmen(j, "", {})
check(g is not None and g[0].startswith("Handel am Konto gesperrt") and g[2] == "Journal: [Trade disabled]",
      "Grund = Handel am Konto gesperrt, Quelle Journal")
check(g is not None and "nicht neu starten" in g[1], "Handgriff: Konto prüfen, nicht neu starten")

check(ob.order_journal_grund(ZEILEN, "NDX100", "sell", jetzt) is None, "Sell-Zeile von 03:40 ist älter als 3 min → zählt nicht")
check(ob.order_journal_grund(ZEILEN, "US30", "buy", jetzt) is None, "anderes Symbol → nichts")
check(ob.order_journal_grund(ZEILEN[:2], "NDX100", "buy", jetzt) is None, "Anfrage ohne Antwort in [ ] → kein Grund (alte Meldung)")

# Symbol mit Endung beim Broker (NDX100.cash), Auftrag ohne Endung
j2 = ob.order_journal_grund(["AB\t0\t10:00:00.000\tTrades\t'00000000': failed market buy 1 NDX100.cash [Market closed]"],
                            "NDX100", "buy", s("10:00:20"))
check(j2 is not None and ob.order_grund_bestimmen(j2, "", {})[0].startswith("Markt geschlossen"), "Symbol mit Endung, Market closed")

# echte UTF-16-Datei mit BOM, wie das Terminal sie schreibt
import datetime as dtm
with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "logs"))
    pfad = os.path.join(d, "logs", dtm.datetime.now().strftime("%Y%m%d") + ".log")
    with open(pfad, "wb") as f:
        f.write(("﻿" + "\r\n".join(ZEILEN) + "\r\n").encode("utf-16-le"))
    z = ob._mt5_journal_zeilen(d)
    check(len(z) == len(ZEILEN) and z[2].endswith("[Trade disabled]"), "UTF-16-Datei mit BOM + CRLF wird zeilengenau gelesen")
    check(ob.order_journal_grund(z, "NDX100", "buy", jetzt)[0] == "Trade disabled", "Ende-zu-Ende aus der Datei: Trade disabled")

print("\nALLES GRÜN" if OK else "\nFEHLER")
sys.exit(0 if OK else 1)
