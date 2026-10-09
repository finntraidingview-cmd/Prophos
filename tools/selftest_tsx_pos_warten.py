#!/usr/bin/env python3
"""Selbsttest TOPSTEPX POSITIONS-BEREICH ABWARTEN (09.10.2026, Terminal 2 — Ina DLL-Konto 333d4791, 08:19 Dubai: Konto + BAL korrekt,
„Positions-Bereich in TopstepX nicht sichtbar", nichts platziert). Geprüft: order_bot.py liest bei tabelle_unklar ohne Positions-Bereich
gedrosselt nach (feste Anzahl, Lesefehler → letzter Befund), schreibt sonst das Inventar (TSX_POS_INVENTAR_JS, ohne account-testids) in
ergebnis.diagnose; augen_tsx.js: RX_KEINE_POS mit Varianten (Syntax = Python re), Text-Rückfall keinePosPerText, leeres Grid + Close-Position
gesperrt = flach. Aufruf: python3 tools/selftest_tsx_pos_warten.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    bot = open(os.path.join(HIER, "..", "mt5-copier", "order_bot.py"), encoding="utf-8").read()
    js = open(os.path.join(HIER, "..", "mt5-copier", "augen_tsx.js"), encoding="utf-8").read()

    i = bot.index('if code == "tabelle_unklar" and isinstance(st, dict) and st.get("positionen_sichtbar") is not True:')
    block = bot[i:i + 2200]
    check("for _n in range(8):" in block and "_warte(0.9, 0.4)" in block and "time.time()" not in block,
          "Nachlesen: feste Anzahl (8×), gedrosselt über _warte, nicht an der Uhr")
    check("except Exception:\n                    break" in block, "Lesefehler beim Nachlesen → letzter ehrlicher Befund bleibt")
    check('res["diagnose"] = {"tsx_positionen_inventar": inv}' in block and "TSX_POS_INVENTAR_JS" in block,
          "Inventar nur bei weiterem Fehlschlag, landet in ergebnis.diagnose")
    m = re.search(r'TSX_POS_INVENTAR_JS = r"""(.*?)"""', bot, re.S)
    inv = m.group(1) if m else ""
    check("/account/i.test(t)" in inv and ".click(" not in inv and ".value =" not in inv and "dispatchEvent" not in inv,
          "Inventar-JS: Konto-Auslöser ausgenommen, nur Lesen")
    check(bot.index("for _n in range(8):") < bot.index("res.update(felder)", i), "Nachlesen vor der Übernahme der Felder")

    rx = re.search(r"var RX_KEINE_POS = /(.+)/i;", js).group(1)
    r = re.compile(rx, re.I)
    for t in ("No Active Position", "No open position", "No positions", "No position", "Keine aktive Position"):
        check(bool(r.search(t)), f"RX_KEINE_POS erkennt „{t}“")
    check(not r.search("Close Position") and not r.search("Positions"), "RX_KEINE_POS: „Close Position“/„Positions“ nicht")
    check("var keine = ankerPositionen() || keinePosPerText();" in js, "positionenLesen: Text-Rückfall ohne data-testid")
    check("if (g.da && !g.zeilen.length && zuK && zustand(zuK).disabled) return { sichtbar: true, zeilen: [], flach: true };" in js,
          "leeres Positions-Grid + Close Position gesperrt = flach (zwei Belege)")
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
