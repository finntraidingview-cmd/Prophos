#!/usr/bin/env python3
"""Selbsttest fuer reader-server.py — rein rechnende Teile (24.09.2026, Kurs-Feed 0.7.0).

Aufruf:  python3 selftest_reader.py
Prueft ohne Netz und ohne Browser: Zahl- und Wurzel-Parser, Minutenkerzen,
Uebernahme des 'kurse'-Payloads (beide Symbole, Mitte aus Bid/Ask, Kerzen nur aus
sichtbarem Tab) und die Stale-Ausgabe (Userscript-Urteil ODER Alter > 45 s)."""
import importlib.util
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))


def lade():
    spec = importlib.util.spec_from_file_location("rs", os.path.join(HIER, "reader-server.py"))
    rs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rs)
    return rs


def main():
    rs = lade()
    ok = True
    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    check(rs._kurs_zahl("30,448.25") == 30448.25 and rs._kurs_zahl("29.491,75") == 29491.75
          and rs._kurs_zahl("30,448") == 30448 and rs._kurs_zahl("−1,234.50") == -1234.5 and rs._kurs_zahl("abc") is None,
          "Zahl-Parser: beide Trenner, Tausendergruppe, U+2212, Unsinn = None")
    check(rs._kurs_wurzel("NQZ2026") == "NQ" and rs._kurs_wurzel("MNQ1!") == "MNQ"
          and rs._kurs_wurzel("CME_MINI:MNQZ2026") == "MNQ" and rs._kurs_wurzel("NQ") == "NQ",
          "Wurzel: Monat, Dauerkontrakt, Boersen-Praefix, nackt")

    k, v = rs._kerze_fortschreiben(None, None, "NQ", "NQZ2026", 100.0, 60 * 1000 + 5)
    k, v = rs._kerze_fortschreiben(k, v, "NQ", "NQZ2026", 103.0, 60 * 1000 + 10)
    k, v = rs._kerze_fortschreiben(k, v, "NQ", "NQZ2026", 99.0, 60 * 1000 + 20)
    k2, v2 = rs._kerze_fortschreiben(k, v, "NQ", "NQZ2026", 101.0, 60 * 1001 + 1)
    check((k["o"], k["h"], k["l"], k["c"], k["n"]) == (100.0, 103.0, 99.0, 99.0, 3) and v is None and v2 is k and k2["o"] == 101.0,
          "Kerze: o/h/l/c/n, Minutenwechsel schiebt nach 'vor'")

    # kurse-Payload (0.7.0): beide Wurzeln, Mitte aus Bid/Ask, Titel-Rueckfall ohne Bid/Ask
    payload = {"NQ": {"bid": "30,738.50", "ask": "30,739.00", "text": "30,738.50", "ts": 1, "quelle": "legende", "stale": False},
               "MNQ": {"bid": "30,739.25", "ask": "30,739.75", "text": "30,739.25", "ts": 1, "quelle": "legende", "stale": True},
               "XYZ": {"bid": "", "ask": "", "text": "", "ts": 1},
               "kaputt": "nix"}
    kurse, k1, kv = rs._kurse_uebernehmen(payload, True, 1000.0, {}, {}, {})
    check(set(kurse) == {"NQ", "MNQ"} and kurse["NQ"]["preis"] == 30738.75 and kurse["MNQ"]["preis"] == 30739.5
          and kurse["NQ"]["bid"] == 30738.5 and kurse["MNQ"]["stale"] is True and kurse["NQ"]["sichtbar"] is True,
          "kurse: beide Wurzeln, Mitte aus Bid/Ask, stale vom Userscript, Unlesbares raus")
    check(set(k1) == {"NQ", "MNQ"} and k1["NQ"]["o"] == 30738.75 and k1["NQ"]["n"] == 1,
          "kurse: Kerzen je Wurzel aus dem sichtbaren Tab")
    kurse2, k1b, kvb = rs._kurse_uebernehmen({"NQ": {"text": "30,740", "ts": 2, "quelle": "titel"}}, False, 1002.0, kurse, k1, kv)
    check(kurse2["NQ"]["preis"] == 30740 and kurse2["NQ"]["quelle"] == "titel" and kurse2["MNQ"]["preis"] == 30739.5
          and k1b["NQ"]["n"] == 1,
          "kurse: Titel-Rueckfall ohne Bid/Ask ersetzt den Kurs, MNQ bleibt stehen, verdeckter Tab schreibt KEINE Kerze")
    aus = rs._kurse_ausgabe(kurse2, 1010.0)
    check(aus["NQ"]["alter_s"] == 8.0 and aus["NQ"]["stale"] is False and aus["MNQ"]["alter_s"] == 10.0 and aus["MNQ"]["stale"] is True
          and "empf_s" not in aus["NQ"],
          "Ausgabe: alter_s je Wurzel, stale vom Userscript bleibt")
    aus2 = rs._kurse_ausgabe(kurse2, 1000.0 + 60)
    check(aus2["NQ"]["stale"] is True, "Ausgabe: Empfang aelter als 45 s → stale, auch ohne Userscript-Urteil")

    print("\n" + ("alle Tests bestanden" if ok else "FEHLER"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
