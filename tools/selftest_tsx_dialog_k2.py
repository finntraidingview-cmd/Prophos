#!/usr/bin/env python3
"""Selbsttest TOPSTEP-DIALOG-K2 (20.10.2026, Slave-Terminal 3 — Finn live am Marc-PC, Lauf 15:14 UTC mit Bot .1650: „das Pop-up kommt, der Bot
drückt nie auf Close, er beendet direkt"). Die Loss-Limit-Meldung kam erst nach dem Stand-Lesen am Rundenanfang; der Ziel-Beweis fand sie
unter dem Konto-Auslöser → „Klick ohne Beweis". Jetzt: tsx_k2_meldung_nachgelesen am frischesten Stand vor dem Klick und nach „kein Druck"
→ Runde von vorn, der Rundenanfang schließt sie (tsx_blow_dialog_knopf, Dedupe .1650) und wechselt dann.
Geprüft mit genau der Rohliste des Marc-PCs ('Close', 'See details', 'Reset Trading Combine', X mit aria 'Close'). Alle Kennungen erfunden.
Aufruf: python3 tools/selftest_tsx_dialog_k2.py"""
import os
import re
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
    R = [120, 300, 80, 28]
    popup = {"titel": "", "text": "You Hit Your Maximum Loss Limit.", "text_voll": "You Hit Your Maximum Loss Limit.Account: 150KTC-SKU-V2-DLL-6",
             "knoepfe": [{"text": "Close", "rect": R}, {"text": "See details", "rect": [220, 300, 90, 28]},
                         {"text": "Reset Trading Combine", "rect": [320, 300, 160, 28]}, {"text": "", "aria": "Close", "rect": [470, 120, 20, 20], "icon": "CloseIcon"}]}
    st_mit = {"konto": {"aktiv": "150KTC-SKU-V2-DLL-000000-10000001", "rect": [68, 4, 194, 34]}, "popups": [popup]}
    st_ohne = {"konto": {"aktiv": "150KTC-SKU-V2-DLL-000000-10000001", "rect": [68, 4, 194, 34]}, "popups": []}

    bd = ob.tsx_blow_dialog(st_mit["popups"])
    check(bd is not None and bd["art"] == "maximum_loss" and bd["konto"] == "150KTC-SKU-V2-DLL-6", "Marc-Rohliste: Meldung erkannt (maximum_loss, gekürzte Kennung)")
    k = ob.tsx_blow_dialog_knopf(bd["popup"])
    check(k is not None and k["text"] == "Close" and not k.get("aus_aria") and k["rect"] == R, "Marc-Rohliste: Schließ-Knopf = Text-„Close“ (Dedupe .1650)")
    check(ob.tsx_blow_dialog_verletzung(bd) == {}, "gekürzte Kennung → nichts archivieren")

    check(ob.tsx_k2_meldung_nachgelesen(st_mit, {}) is True, "Meldung im frischen Stand, noch nicht versucht → Runde von vorn")
    check(ob.tsx_k2_meldung_nachgelesen(st_mit, {"_blow_dialog_versucht": True}) is False, "Meldung schon einmal versucht → nicht erneut (nie ein zweiter Druck)")
    check(ob.tsx_k2_meldung_nachgelesen(st_ohne, {}) is False, "keine Meldung → wie bisher klicken")
    check(ob.tsx_k2_meldung_nachgelesen({"popups": [{"text": "Session disconnected", "knoepfe": []}]}, {}) is False, "fremder Dialog → kein Blow-Zweig")
    check(ob.tsx_k2_meldung_nachgelesen(None, None) is False and ob.tsx_k2_meldung_nachgelesen("x", []) is False, "kaputter Stand/res → False")

    # Quelltext-Vertrag: beide Nachlese-Stellen im K2-Weg, vor dem Klick und nach „kein Druck", beide → continue (Runde von vorn)
    src = open(ob.__file__, encoding="utf-8").read()
    i = src.index("def _tsx_konto_sichern(")
    j = src.index("\ndef ", i + 10)
    k2 = src[i:j]
    a = k2.find("_tsx_ausloeser_stabil(s, st, ko, r, trail)\n        if tsx_k2_meldung_nachgelesen(st, bd_res)")
    b = k2.find("st = s.stand()", k2.find("if not gedrueckt:"))
    c = k2.find("tsx_k2_meldung_nachgelesen(st, bd_res)", b)
    d = k2.find('_raus("konto_nicht_erreicht", "Konto-Auslöser nicht gedrückt (Klick ohne Beweis)', c)
    check(a > 0, "Nachlese (a) direkt nach dem Stabil-Lesen, vor dem Auslöser-Klick")
    check(0 < b < c < d, "Nachlese (b) nach „kein Druck“: Stand neu lesen → Meldung → vor dem ehrlichen Ende")
    check(k2.count("geklickt = False\n            continue") >= 2 or k2.count("geklickt = False\n                continue") >= 1, "beide Stellen: geklickt zurück, Runde von vorn")
    check(k2.find("bd_offen = tsx_blow_dialog(") < a, "Rundenanfang schließt die Meldung (bestehender Zweig) — Nachlese nur davor/danach")

    print()
    if FEHLER:
        print(f"{len(FEHLER)} FEHLER:", *FEHLER, sep="\n  ")
        sys.exit(1)
    print("alle Prüfungen bestanden")


if __name__ == "__main__":
    main()
