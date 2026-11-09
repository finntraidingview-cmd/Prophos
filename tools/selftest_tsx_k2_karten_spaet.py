#!/usr/bin/env python3
"""Selbsttest TX1 K2 KARTEN KOMMEN SPÄT (09.11.2026, ab 03:05 Dubai scheiterten alle Topstep-Läufe mit „Konto nicht in der Liste (0×) …
[Liste 0: ]"): nach dem eigenen Klick auf den Konto-Auslöser meldet TopstepX die Liste sofort offen, die Karten kommen aber erst später.
Geprüft mit nachgebauter Sitzung (Muster selftest_tsx_k2_stabil): Karten kommen nach zwei leeren Lesungen → Zeile gedrückt, Konto
gewechselt; Karten kommen nie → ehrlich raus wie bisher, genau EIN Auslöser-Klick, kein Zeilen-Klick; Liste geht während des Wartens
zu → „Liste nicht erkannt" wie bisher. Aufruf: python3 tools/selftest_tsx_k2_karten_spaet.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "mt5-copier"))
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


EXT = "150KTC-SKU-V2-DLL-000000-00000002"
ALT = "150KTC-SKU-V2-DLL-000000-00000001"
R = [60, 4, 190, 34]


def konto(nr, offen=False, liste=None):
    return {"konto": {"aktiv": f"150K DLL Combine|{nr}", "kontonr": nr, "abgekuerzt": False, "rect": R, "liste_offen": offen,
                      "liste": list(liste or []), "zu": {}}}


def zeile(nr, y):
    return {"text": f"150K DLL Combine|{nr}", "label": "150K DLL Combine", "id": nr, "rect": [60, y, 300, 30], "zu": {}}


class Sitz:
    def __init__(self, staende, klick_antworten):
        self.staende, self.i, self.klick_antworten, self.klicks, self.trail = staende, 0, list(klick_antworten), [], None

    def stand(self, opts=None):
        x = self.staende[min(self.i, len(self.staende) - 1)]
        self.i += 1
        return x

    def klick(self, rect, name, pruef=None, doppel=False):
        self.klicks.append((name, list(rect)))
        ok, spur = self.klick_antworten.pop(0) if self.klick_antworten else (False, "")
        if spur:
            self.trail.append(spur)
        return ok

    def taste(self, *a, **k):
        pass


def lauf(ob, staende, antworten):
    s = Sitz(staende, antworten)
    s.i = 1
    trail = ob._StempelSpur()
    s.trail = trail
    ok, code, msg, st, ex = ob._tsx_konto_sichern(s, EXT, staende[0], trail)
    return ok, code, msg, s, " > ".join(trail)


def main():
    import order_bot as ob
    ob._warte = lambda *a, **k: None
    ob._tsx_pause = lambda *a, **k: None
    ob._cdp_esc = lambda *a, **k: None
    ob.TSX_LISTE_KARTEN_S = 0.3
    liste = [zeile(ALT, 50), zeile(EXT, 85)]

    # zu, (stabil) zu, nach Klick offen+leer, offen+leer, offen+Karten, nach Zeilen-Klick Ziel steht
    spaet = [konto(ALT), konto(ALT), konto(ALT), konto(ALT, True), konto(ALT, True), konto(ALT, True, liste), konto(EXT), konto(EXT)]
    ok, code, msg, s, sp = lauf(ob, spaet, [(True, ""), (True, "")])
    namen = [k[0] for k in s.klicks]
    check(ok and namen == ["Konto-Auslöser", f"Konto {EXT}"] and "Liste offen ohne Karten" in sp,
          f"Karten kommen spät → gewartet, Zeile gedrückt, Konto gewechselt ({namen}, {code}: {msg})")

    nie = [konto(ALT), konto(ALT), konto(ALT), konto(ALT, True)]
    ok, code, msg, s, sp = lauf(ob, nie, [(True, "")])
    namen = [k[0] for k in s.klicks]
    check(not ok and code == "konto_nicht_erreicht" and "nicht in der Liste" in msg and namen == ["Konto-Auslöser"],
          f"Karten kommen nie → ehrlich raus wie bisher, nur der Auslöser-Klick ({namen}, {msg})")

    zu = [konto(ALT), konto(ALT), konto(ALT), konto(ALT, True), konto(ALT)]
    ok, code, msg, s, sp = lauf(ob, zu, [(True, "")])
    namen = [k[0] for k in s.klicks]
    check(not ok and code == "konto_nicht_erreicht" and namen == ["Konto-Auslöser"] and "Liste zu" in sp,
          f"Liste geht beim Warten zu → raus wie bisher, kein zweiter Klick ({namen}, {msg})")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
