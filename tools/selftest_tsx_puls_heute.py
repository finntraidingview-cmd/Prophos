#!/usr/bin/env python3
"""Selbsttest TOPSTEP-PULS-HEUTE (20.10.2026, Slave-Terminal 3 — Master-Auftrag nach Finns „weiter mit Topstep-Puls", 8 liegende tsv2-Starts).
(A) tsx_blow_dialog_knopf: Text-Knopf „Close" + Symbol-X mit aria „Close" (Marc, 4 Fehlstarts: „kein eindeutiger Schließ-Knopf") → der
    Text-Knopf; zwei X nur mit aria „Close" → das erste; OK + Close (verschiedene Wörter) → weiter nichts; Symbol-X ohne Wort wie bisher.
(B) puls_chrome_argumente trägt --hide-crash-restore-bubble (Ina: Chromes „Seiten wiederherstellen?"-Blase lag zweimal über dem Contract-Feld).
(C) tsx_knopf_gesperrt_rohtext: eine Spur-Zeile mit Knopf-Zustand, Anzeigen, Kopf, Konto, Dialogen — robust bei leerem/kaputtem Stand.
Alle Kennungen erfunden. Aufruf: python3 tools/selftest_tsx_puls_heute.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "mt5-copier"))
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    import order_bot as ob
    R = [10, 10, 60, 24]
    # (A) Marc 20.10.2026: 'Close', 'See details', 'Reset Trading Combine', 'Close' (das zweite = Symbol-X mit aria)
    marc = {"knoepfe": [{"text": "Close", "rect": R}, {"text": "See details", "rect": R}, {"text": "Reset Trading Combine", "rect": R},
                        {"text": "", "aria": "Close", "rect": [300, 4, 20, 20], "icon": "CloseIcon"}]}
    k = ob.tsx_blow_dialog_knopf(marc)
    check(k is not None and k["text"] == "Close" and not k.get("aus_aria") and k["rect"] == R, "Marc: Text-Knopf „Close“ vor dem aria-X → gedrückt wird der Text-Knopf")
    k = ob.tsx_blow_dialog_knopf({"knoepfe": [{"text": "", "aria": "Close", "rect": [300, 4, 20, 20]}, {"text": "", "aria": "close", "rect": [1, 1, 20, 20]}]})
    check(k is not None and k.get("aus_aria") and k["rect"] == [300, 4, 20, 20], "zwei aria-„Close“ → dasselbe Wort, das erste")
    check(ob.tsx_blow_dialog_knopf({"knoepfe": [{"text": "OK", "rect": R}, {"text": "Close", "rect": R}]}) is None, "OK + Close (verschiedene Wörter) → weiter nichts drücken")
    check(ob.tsx_blow_dialog_knopf({"knoepfe": [{"text": "Close", "rect": R}, {"text": "Close Position", "rect": R}]})["text"] == "Close", "Close + „Close Position“ (tabu) → Close")
    k = ob.tsx_blow_dialog_knopf({"knoepfe": [{"text": "RESET TRADING COMBINE", "rect": R}, {"text": "", "aria": "", "rect": [300, 4, 20, 20], "icon": "CloseIcon"}]})
    check(k is not None and k.get("icon_x"), "ohne Schließ-Wort: Symbol-X wie seit .1634")
    check(ob.tsx_blow_dialog_knopf({"knoepfe": [{"text": "Close", "rect": R}]})["text"] == "Close", "ein Close → Close (unverändert)")

    # (B) Chrome-Startflag
    arg = ob.puls_chrome_argumente("chrome.exe", ob.puls_chrome_profil_pfad("C:\\Users\\m\\AppData\\Local"))
    check("--hide-crash-restore-bubble" in arg and "--start-maximized" in arg and arg[-1] == ob.AUGEN_TV_URL, "Puls-Chrome: --hide-crash-restore-bubble dabei, Rest unverändert")

    # (C) Rohtext bei gesperrtem Knopf
    st = {"ticket": {"anzeigen": [{"testid": "order-card-display-value-no-position", "text": "No Active Position"}, {"testid": "order-card-display-value-bid", "text": "29,519.50"}],
                     "kauf": {"text": "Buy +3 @ Market", "zu": {"disabled": True, "verdeckt": False}},
                     "verkauf": {"text": "Sell -3 @ Market", "zu": {"disabled": True, "verdeckt": True, "oben": {"tag": "div", "text": "Trading disabled"}}}},
          "kopf": {"balance": {"text": "$14,103.66"}, "mll": {"text": "$9,603.66"}}, "konto": {"kontonr": "EXPRESS-V2-000000-10000001", "hinweis": "Ineligible"},
          "popups": [{"text": "x"}]}
    r = ob.tsx_knopf_gesperrt_rohtext(st)
    check("verkauf 'Sell -3 @ Market' disabled=True verdeckt=True oben 'Trading disabled'" in r and "kauf 'Buy +3 @ Market' disabled=True" in r, f"Knopf-Zustand in der Zeile: {r[:90]}")
    check("no-position=No Active Position | bid=29,519.50" in r and "balance $14,103.66 · mll $9,603.66" in r, "Anzeigen + Kopf in der Zeile")
    check("Konto EXPRESS-V2-000000-10000001 (Ineligible) · Dialoge 1" in r, "Konto mit Hinweis + Dialoge")
    check(ob.tsx_knopf_gesperrt_rohtext(None) == "Knöpfe - · Anzeigen - · Kopf - · Konto - · Dialoge 0", "leerer Stand → Platzhalter, kein Fehler")
    check(ob.tsx_knopf_gesperrt_rohtext({"ticket": "x", "kopf": 3, "konto": [], "popups": None}) == "Knöpfe - · Anzeigen - · Kopf - · Konto - · Dialoge 0", "kaputter Stand → Platzhalter")

    print()
    if FEHLER:
        print(f"{len(FEHLER)} FEHLER:", *FEHLER, sep="\n  ")
        sys.exit(1)
    print("alle Prüfungen bestanden")


if __name__ == "__main__":
    main()
