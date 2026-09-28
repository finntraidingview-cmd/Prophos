#!/usr/bin/env python3
"""Selbsttest Puls-Kauf-Knopf (mt5-copier/order_bot.py, 29.09.2026, Vorfall Jacob 47979c82 '0 Treffer') — rein rechnend.

Aufruf:  python3 tools/selftest_puls_knopf.py
Prueft tv_knopf_ausser_sicht (Knopf ohne Rechteck = ausser Sicht, Seiten-Kasten zaehlt nicht) und tv_knopf_inventar
(Panel-Elemente unter der Stop-Loss-Zeile + Knopf ausser Sicht, lesbarer Text fuer die Fehlermeldung)."""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(os.path.dirname(HIER), "mt5-copier", "order_bot.py")


def lade():
    src = open(BOT, encoding="utf-8").read()
    ns = {"re": re}
    teile = [re.search(r"^_TV_NAME_MUELL = .*$", src, re.M).group(0), re.search(r"^TV_RX_SENDEN = .*$", src, re.M).group(0)]
    for fn in ("def tv_name_norm(", "def tv_im_panel(", "def tv_knopf_ausser_sicht(", "def tv_knopf_inventar("):
        i = src.index(fn)
        ende = min(x for x in (src.find("\n\n\n", i), src.find("\n# ", i + 1)) if x > 0)
        teile.append(src[i:ende])
    exec("\n\n".join(teile), ns)
    return ns


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    ber = {"links": 752, "rechts": 1154}
    # Jacobs Fall: Knopf ausser Sicht (rect None), Seiten-Kasten sichtbar oben, SL-Zeile bei 580
    roh = [("Buy 30,650.50", (990, 240, 1060, 266), "Button"), ("Stop loss", (800, 570, 870, 590), "Text"),
           ("Buy 3 NQZ6 MARKET", None, "Button"), ("Buy 3 NQZ6 MARKET", None, "Button"),
           ("Tick value", (800, 610, 870, 625), "Text"), ("Share your idea", (100, 700, 200, 720), "Button")]
    weg = a["tv_knopf_ausser_sicht"](roh)
    check(weg == [("Buy 3 NQZ6 MARKET", "Button")], "ausser Sicht: Knopf einmal erkannt, Seiten-Kasten nicht")
    check(a["tv_im_panel"](roh, ber, a["TV_RX_SENDEN"], y_von=590) == [], "tv_im_panel verwirft den Knopf ohne Rechteck (= 0 Treffer)")
    check(a["tv_knopf_ausser_sicht"]([("Buy 30,650.50", None, "Button"), ("Sell 2 at 30,801", None, "Text")]) == [],
          "ausser Sicht: ohne Orderart (Kasten, Toast) kein Kandidat")
    liste, text = a["tv_knopf_inventar"](roh, ber, 590)
    d = {e[0]: e[2] for e in liste}
    check(len(liste) == 2 and d.get("Buy 3 NQZ6 MARKET", 0) is None and d.get("Tick value") == [800, 610, 870, 625],
          "Inventar: nur Panel unter SL + Knopf ausser Sicht, ohne Doppelte, ohne Fremdes links")
    check("Button:Buy 3 NQZ6 MARKET (ausser Sicht)" in text and "Text:Tick value@610" in text, "Inventar-Text zeigt den Knopf lesbar")
    check(a["tv_knopf_inventar"]([], ber, 590)[1] == "nichts", "Inventar leer -> 'nichts'")
    # sichtbarer Knopf: normaler Weg bleibt genau ein Treffer
    roh2 = [("Buy 3 NQZ6 MARKET", (800, 680, 1100, 708), "Button"), ("Buy 3 NQZ6 MARKET", (820, 686, 1000, 700), "Text")]
    check(len(a["tv_im_panel"](roh2, ber, a["TV_RX_SENDEN"], y_von=590)) == 1 and a["tv_knopf_ausser_sicht"](roh2) == [],
          "sichtbarer Knopf: ein Treffer, nichts ausser Sicht")
    print("\nALLES OK" if ok else "\nFEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
