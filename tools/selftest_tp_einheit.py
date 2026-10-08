#!/usr/bin/env python3
"""Selbsttest: TP/SL-Einheit im neuen TradingView-Order-Ticket (08.10.2026, Slave 1, Puls-Fehler pc-2zc2we 13:25 + pc-usq1i6 13:28 UTC
„'Take profit' steht nicht auf $ (Einheit '?')": Beschriftung „Take profit $ ▾" statt „Take profit, $"). Prüft order_bot.cdp_einheit,
die Neustart-Entscheidung (kein Chrome-Neustart bei Einheit-Fehler) und den augen.js-Quelltext (kein Node auf dem Mac).
Aufruf: python3 tools/selftest_tp_einheit.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "mt5-copier"))
import order_bot as ob  # noqa: E402


def main():
    f = []

    def check(ok, name):
        f.append(0 if ok else 1)
        print(("OK  " if ok else "FEHL") + " " + name)

    E = ob.cdp_einheit
    b = lambda t, e=None: {"einheit": e, "beschriftung": {"text": t}}
    check(E(b("Take profit, $", "$")) == "$", "alt: augen.js liefert $")
    check(E(b("Take profit $")) == "$" and E(b("Stop loss $")) == "$", "neu ohne Komma (Lesung pc-usq1i6 13:28): $ aus der Beschriftung")
    check(E(b("Take profit $ ▾")) == "$" and E(b("Take profit $▾")) == "$", "neu mit Wähler-Pfeil")
    check(E(b("Take profit USD")) == "$" and E(b("Take profit", "USD")) == "$", "USD zählt als $")
    check(E(b("Take profit ticks")) == "ticks" and E(b("Take profit, %")) == "%" and E(b("Take profit price ▾")) == "price",
          "andere Einheiten bleiben andere (Bot bricht dann weiter ab)")
    check(E(b("Take profit")) == "" and E({}) == "" and E(None) == "" and E(b("Take profit$")) == "",
          "ohne Einheit → leer ('?' in der Meldung)")

    N = ob.neustart_entscheid
    r = {"ok": False, "code": "ticket", "schritt": "ticket", "gesendet": False,
         "msg": "'Take profit' steht nicht auf $ (Einheit '?') — der Wert 15353 wäre etwas anderes. — nichts gesendet."}
    art, grund, _ = N(r, "tvv2", 30.0)
    check(art == "nein" and "Einheit" in grund, f"Einheit-Fehler → kein Chrome-Neustart ({art}, {grund})")
    art, _, _ = N(dict(r, msg="Contract nicht gewaehlt"), "tvv2", 30.0)
    check(art == "nein", "anderer Ticket-Fehler → auch kein Neustart (Master 08.10.2026: ticket/konto/login nie)")

    G = ob.puls_fenster_gross_noetig
    check(G({"zoomed": True, "normal_breite": 900})[0] is False, "maximiert → nichts tun")
    check(G({"iconic": True, "restore_max": True, "normal_breite": 900})[0] is False, "minimiert, kommt maximiert zurück → nichts tun")
    check(G({"iconic": True, "restore_max": False, "normal_breite": 929})[0] is True, "minimiert, käme halb zurück (pc-2zc2we 929 px) → maximieren")
    check(G({"normal_breite": 1034})[0] is True and G({"normal_breite": 1600})[0] is False, "normal < 1200 → maximieren, ≥ 1200 → lassen")
    check(G(None)[0] is True, "ohne Lage → maximieren (Aufrufer prüft None vorher)")
    arg = ob.puls_chrome_argumente("chrome.exe", ob.puls_chrome_profil_pfad("C:\\Users\\m\\AppData\\Local"))
    check("--start-maximized" in arg, "Puls-Chrome startet maximiert")

    js = open(os.path.join(os.path.dirname(os.path.abspath(ob.__file__)), "augen.js"), encoding="utf-8").read()
    check("VERSION = '0.8.1'" in js and "bt2.match(/,\\s*(.+)$/) || bt2.match(/\\s(\\$|" in js and "/^usd$/i.test" in js,
          "augen.js 0.8.1: Einheit mit Komma ODER Leerzeichen, USD → $")
    print(f"{len(f) - sum(f)}/{len(f)} ok")
    sys.exit(1 if sum(f) else 0)


if __name__ == "__main__":
    main()
