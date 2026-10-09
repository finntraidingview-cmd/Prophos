#!/usr/bin/env python3
"""Selbsttest K2 KONTO-AUSLÖSER STABIL (09.10.2026, Terminal 2 — Ina 333d4791 Lauf e944cde2: „Konto-Auslöser: nach der Hover-Pause liegt
am Zielpunkt nicht mehr das Ziel — kein Druck", Seite 1,5 s vorher frisch geöffnet, TopstepX baute nach). Geprüft mit nachgebauter
Sitzung: tsx_rect_gleich; _tsx_konto_sichern wartet auf zwei gleiche Rechtecke vor dem Druck; „kein Druck" (Ziel verschoben) → Ziel neu,
GENAU ein zweiter Versuch; anderer Fehlgrund → kein zweiter Versuch; nie mehr als zwei Druck-Versuche. Aufruf:
python3 tools/selftest_tsx_k2_stabil.py"""
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


def konto(nr, rect):
    return {"konto": {"aktiv": f"150K DLL Combine|{nr}", "kontonr": nr, "abgekuerzt": False, "rect": rect, "liste_offen": False, "zu": {}}}


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
    s.i = 1                                   # der Anfangsstand geht direkt hinein, stand() liefert ab dem nächsten
    trail = ob._StempelSpur()
    s.trail = trail
    ok, code, msg, st, ex = ob._tsx_konto_sichern(s, EXT, staende[0], trail)
    return ok, code, msg, s, " > ".join(trail)


def main():
    import order_bot as ob
    ob._warte = lambda *a, **k: None
    ob._tsx_pause = lambda *a, **k: None
    g = ob.tsx_rect_gleich
    check(g([10, 20, 100, 30], [11, 21, 100, 30]) and not g([10, 20, 100, 30], [10, 40, 100, 30]) and not g(None, [1, 2, 3, 4]),
          "tsx_rect_gleich: ±2 px gleich, verschoben/ungültig nicht")

    r1, r2 = [60, 4, 190, 34], [68, 4, 194, 34]
    springt = [konto(ALT, r1), konto(ALT, r2), konto(ALT, r2), konto(EXT, r2)]
    ok, code, msg, s, sp = lauf(ob, springt, [(True, "")])
    check(ok and len(s.klicks) == 1 and s.klicks[0][1] == r2, f"Rechteck springt, dann ruhig → Druck auf die stabile Lage ({s.klicks}, {code})")

    verschoben = (False, "Konto-Auslöser: nach der Hover-Pause liegt am Zielpunkt nicht mehr das Ziel ('150k dll combine|…') — kein Druck")
    st2 = [konto(ALT, r2), konto(ALT, r2), konto(ALT, r1), konto(ALT, r1), konto(ALT, r1), konto(EXT, r1)]
    ok, code, msg, s, sp = lauf(ob, st2, [verschoben, (True, "")])
    check(ok and len(s.klicks) == 2 and "zweiter Versuch" in sp and s.klicks[1][1] == r1,
          f"„kein Druck“ (verschoben) → Ziel neu, genau ein zweiter Versuch ({len(s.klicks)} Klicks, {code})")

    ok, code, msg, s, sp = lauf(ob, st2, [verschoben, verschoben, (True, "")])
    check(not ok and code == "konto_nicht_erreicht" and len(s.klicks) == 2, f"zweimal verschoben → ehrlich raus, nie ein dritter Druck ({len(s.klicks)})")

    anders = (False, "Konto-Auslöser: am Zielpunkt liegt ein anderes Fenster — kein Druck")
    ok, code, msg, s, sp = lauf(ob, st2, [anders, (True, "")])
    check(not ok and len(s.klicks) == 1, f"anderer Fehlgrund → kein zweiter Versuch ({len(s.klicks)} Klicks)")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
