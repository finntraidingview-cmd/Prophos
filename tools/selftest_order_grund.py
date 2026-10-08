#!/usr/bin/env python3
"""Selbsttest Grund bei „KEINE Bestaetigung binnen 12 s" (mt5-copier/order_bot.py, 09.10.2026).

Aufruf:  python3 tools/selftest_order_grund.py
Anlass: 5 Fälle an 4 PCs — alle Klickwege auf Buy ausgelöst, keine Position; die Konten waren serverseitig gesperrt (bestanden bzw.
an der Verlustgrenze gebrochen), die Meldung sagte nur „Dialog geschlossen". Geprüft (ohne MT5, ohne Netz): order_grund_aus_text
(Server-Antworten DE/EN), order_journal_grund (Symbol + Richtung + nur die letzten Minuten), order_grund_bestimmen (Journal vor Dialog
vor API), _mt5_journal_zeilen (UTF-16-Logdatei), Grund steht in der Meldung VOR der Spur. Platzhalter-Logins, keine echten Konten."""
import inspect
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


def main():
    g = ob.order_grund_aus_text
    check(g("[Trade disabled]")[0].startswith("Handel am Konto gesperrt") and g("Handel ist deaktiviert")[0].startswith("Handel am Konto gesperrt"),
          "Trade disabled (EN/DE) → Handel am Konto gesperrt")
    check(g("Invalid stops")[0].startswith("SL/TP ungültig") and g("Market closed")[0].startswith("Markt geschlossen")
          and g("No money")[0].startswith("zu wenig freie Marge") and g("Requote")[0].startswith("Kurs vom Server abgelehnt"),
          "Invalid stops / Market closed / No money / Requote erkannt")
    check(g("") is None and g("alles gut") is None, "kein bekannter Grund → None")

    j = ob.order_journal_grund
    jetzt = 3 * 3600 + 48 * 60 + 10                     # 03:48:10 Ortszeit
    zeilen = ["LS\t0\t03:40:01.111\tTrades\t'100001': failed market buy 1 NDX100 [Invalid stops]",
              "KQ\t0\t03:47:55.222\tTrades\t'100001': market buy 2.7 NDX100 sl: 30751.17 tp: 31042.20",
              "GH\t0\t03:47:55.300\tTrades\t'100001': failed market buy 2.7 NDX100 sl: 30751.17 tp: 31042.20 [Trade disabled]",
              "PL\t0\t03:47:58.000\tTrades\t'100001': failed market sell 1 US30 [Market closed]"]
    r = j(zeilen, "NDX100", "buy", jetzt)
    check(r and r[0] == "Trade disabled" and "2.7 NDX100" in r[1], "Journal: neueste passende Zeile (Symbol + Richtung) → [Trade disabled]")
    check(j(zeilen, "NDX100", "sell", jetzt) is None, "Journal: andere Richtung zählt nicht")
    check(j(zeilen[:1], "NDX100", "buy", jetzt) is None, "Journal: Zeile älter als 3 min zählt nicht (alter Lauf)")
    check(j(["XX\t0\t23:59:50.000\tTrades\t'1': failed market buy 1 NDX100 [No money]"], "NDX100", "buy", 5) is not None,
          "Journal: über Mitternacht (23:59:50 → 00:00:05) noch frisch")

    b = ob.order_grund_bestimmen
    r = b(("Trade disabled", "z"), "Invalid stops", {"handel_konto": True})
    check(r[0].startswith("Handel am Konto gesperrt") and r[2] == "Journal: [Trade disabled]", "Vorrang: Journal vor Dialog-Text")
    r = b(None, "Order rejected: Not enough money", {})
    check(r and r[0].startswith("zu wenig freie Marge") and r[2] == "Order-Dialog", "ohne Journal: Dialog-Text")
    r = b(None, "", {"handel_konto": False})
    check(r and "trade_allowed = False" in r[0] and r[2] == "API", "ohne Journal/Dialog: API account_info.trade_allowed False")
    check(b(None, "", {"verbunden": False})[0].startswith("Terminal nicht mit dem Server verbunden"), "API: Terminal nicht verbunden")
    check(b(None, "", {"symbol_modus": 3, "symbol": "NDX100"})[0] == "Symbol NDX100 nur Schließen erlaubt (Close only)", "API: Symbol Close only")
    check(b(None, "", {"handel_konto": True, "symbol_modus": 4, "verbunden": True}) is None, "alles erlaubt, nichts gefunden → None (alte Meldung)")
    r = b(("Unbekannte Antwort", "z"), "", {})
    check(r and "Unbekannte Antwort" in r[0] and r[2] == "Journal", "unbekannte Server-Antwort wird wörtlich genannt")

    with tempfile.TemporaryDirectory() as d:
        import datetime as _dtm
        os.makedirs(os.path.join(d, "logs"))
        pfad = os.path.join(d, "logs", _dtm.datetime.now().strftime("%Y%m%d") + ".log")
        with open(pfad, "wb") as f:
            f.write(("﻿" + "\r\n".join(zeilen) + "\r\n").encode("utf-16-le"))
        z = ob._mt5_journal_zeilen(d)
        check(len(z) == 4 and "[Trade disabled]" in z[2], "_mt5_journal_zeilen liest die UTF-16-Logdatei des Terminals")
    check(ob._mt5_journal_zeilen("") == [] and ob._mt5_journal_zeilen("/gibt/es/nicht") == [], "kein Datenordner/keine Datei → leer, kein Fehler")

    q = inspect.getsource(ob.run)
    i_grund, i_spur = q.find("KEINE Bestaetigung binnen 12 s — Grund:"), q.find('"Dialog geschlossen. Spur: [" + _spur(trail)')
    check(0 < i_grund < i_spur and '"retry_ok": False, "grund": grund[0]' in q, "Meldung: Grund VOR der Spur (überlebt das Kürzen), retry_ok bleibt False")
    check("_keine_bestaetigung_grund(path, expected, symbol, cmd[\"richtung\"]" in q, "run() fragt den Grund mit Terminal, Login, Symbol, Richtung")
    print("\nALLES OK" if OK else "\nFEHLER")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
