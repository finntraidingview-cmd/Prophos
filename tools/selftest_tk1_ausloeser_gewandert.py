#!/usr/bin/env python3
"""Selbsttest TK1 KONTO-AUSLÖSER GEWANDERT (27.11.2026, Slave Terminal 1 — Fehlstart „Nichts platziert · Konto-Auslöser nicht gedrückt (Klick
ohne Beweis) — nichts gewechselt.", Simon · Topstep …6316 07:46 und Marco · Topstep …4844 09:41 Dubai, dazu 5 weitere seit 25.11., alle direkt
nach der Google-Anmeldung). Beleg aus den Spuren: „Konto-Auslöser: am Zielpunkt @127,106 liegt nicht das Ziel ('popup cta') [drin ja, klein
NEIN, Text NEIN …, Ziel [68, 4, 192, 34], k iframe [0, 0, 1920, 71]] — kein Druck" — TopstepX schiebt nach dem Laden ein Werbe-Band über die
Seite, der Auslöser rutscht um ~71 px nach unten. Geprüft mit nachgebauter Sitzung (kein Browser, kein Klick): tsx_ausloeser_gewandert;
_tsx_konto_sichern macht nach dem abgelehnten Druck GENAU einen zweiten Versuch am neuen Ort, aber nur, wenn der Auslöser bewiesen woanders
und ruhig steht; echte Verdeckung am alten Ort → raus wie bisher (Schlüssel-Text unverändert); nie ein dritter Druck. Aufruf:
python3 tools/selftest_tk1_ausloeser_gewandert.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "mt5-copier"))
FEHLER = []
TEXT = "Konto-Auslöser nicht gedrückt (Klick ohne Beweis) — nichts gewechselt."


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


EXT = "150KTC-SKU-V2-DLL-000000-00000002"
ALT = "150KTC-SKU-V2-DLL-000000-00000001"
A, B = [68, 4, 192, 34], [68, 75, 192, 34]            # vor / nach dem Werbe-Band (71 px hoch), Maße aus den Spuren vom 27.11.2026


def konto(nr, rect, zu=None, offen=False):
    return {"konto": {"aktiv": f"150K DLL Combine|{nr}", "kontonr": nr, "abgekuerzt": False, "rect": rect, "liste_offen": offen, "zu": zu or {}}}


class Sitz:
    def __init__(self, staende, klick_antworten):
        self.staende, self.i, self.klick_antworten, self.klicks, self.trail = staende, 0, list(klick_antworten), [], None

    def stand(self, opts=None):
        x = self.staende[min(self.i, len(self.staende) - 1)]
        self.i += 1
        return x

    def klick(self, rect, name, pruef=None, doppel=False):
        self.klicks.append((name, list(rect), dict(pruef or {})))
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
    gw = ob.tsx_ausloeser_gewandert
    check(gw(A, konto(ALT, B)["konto"], True) is True, "gewandert: anderer Ort, ruhig, frei → ja")
    check(gw(A, konto(ALT, A)["konto"], True) is False and gw(A, konto(ALT, [69, 5, 192, 34])["konto"], True) is False,
          "gewandert: gleicher Ort (± 2 px) → nein")
    check(gw(A, konto(ALT, B)["konto"], False) is False, "gewandert: nicht zweimal gleich gelesen → nein")
    check(gw(A, konto(ALT, B, zu={"verdeckt": True})["konto"], True) is False and gw(A, konto(ALT, B, zu={"disabled": True})["konto"], True) is False
          and gw(A, konto(ALT, B, offen=True)["konto"], True) is False, "gewandert: verdeckt / gesperrt / Liste offen → nein")
    check(gw(A, {}, True) is False and gw(A, None, True) is False and gw(None, konto(ALT, B)["konto"], True) is False
          and gw(A, {"rect": [68, 75, 0, 0]}, True) is False, "gewandert: kein/kaputtes Rechteck → nein")

    # die echte Spur-Zeile vom 27.11.2026 07:46 Dubai (pc-pmqd8g)
    band = (False, "Konto-Auslöser: am Zielpunkt @127,106 liegt nicht das Ziel ('popup cta') [drin ja, klein NEIN, Text NEIN ('150k dll combine "
                   "(...268'), Tabu nein, Knopf nein, Ziel [68, 4, 192, 34], k iframe [0, 0, 1920, 71]] — kein Druck")

    # Stände: Anfang A · Ruhe-Lesung A · (Druck abgelehnt) · frisch B · zwei Ruhe-Lesungen B · (Druck) · Ziel-Konto
    ok, code, msg, s, sp = lauf(ob, [konto(ALT, A), konto(ALT, A), konto(ALT, B), konto(ALT, B), konto(ALT, B), konto(EXT, B)], [band, (True, "")])
    check(ok and len(s.klicks) == 2 and s.klicks[0][1] == A and s.klicks[1][1] == B and "gewandert [68, 4, 192, 34] → [68, 75, 192, 34]" in sp,
          f"Werbe-Band schiebt die Seite → genau ein zweiter Versuch am neuen Ort ({[k[1] for k in s.klicks]}, {code})")
    check(len(s.klicks) == 2 and s.klicks[1][2].get("rect") == B and s.klicks[1][2].get("tabu") == ob.TSX_K0_TABU.pattern
          and bool(s.klicks[1][2].get("text")), "zweiter Versuch trägt den Ziel-Beweis (neues Rechteck, Kennung, Tabu)")

    ok, code, msg, s, sp = lauf(ob, [konto(ALT, A)] * 8, [band, (True, "")])
    check(not ok and code == "konto_nicht_erreicht" and msg == TEXT and len(s.klicks) == 1 and "Auslöser zuletzt bei [68, 4, 192, 34]" in sp,
          f"Auslöser steht am alten Ort (echte Verdeckung) → kein zweiter Versuch, Schlüssel-Text unverändert, Spur ({len(s.klicks)} Klicks, '{msg}')")

    ok, code, msg, s, sp = lauf(ob, [konto(ALT, A), konto(ALT, A)] + [konto(ALT, B, zu={"verdeckt": True, "oben": {"tag": "iframe", "text": ""}})] * 6,
                                [band, (True, "")])
    check(not ok and msg == TEXT and len(s.klicks) == 1 and "verdeckt True" in sp,
          f"gewandert, aber am neuen Ort verdeckt → kein zweiter Versuch ({len(s.klicks)} Klicks)")

    wandert = [konto(ALT, A), konto(ALT, A)] + [konto(ALT, [68, 10 + 9 * i, 192, 34]) for i in range(8)]
    ok, code, msg, s, sp = lauf(ob, wandert, [band, (True, "")])
    check(not ok and msg == TEXT and len(s.klicks) == 1, f"Auslöser wandert noch (nie zweimal gleich) → kein zweiter Versuch ({len(s.klicks)} Klicks)")

    ok, code, msg, s, sp = lauf(ob, [konto(ALT, A), konto(ALT, A)] + [konto(ALT, B)] * 8, [band, band, (True, "")])
    check(not ok and code == "konto_nicht_erreicht" and msg == TEXT and len(s.klicks) == 2,
          f"auch am neuen Ort ohne Beweis → ehrlich raus, nie ein dritter Druck ({len(s.klicks)} Klicks)")

    ok, code, msg, s, sp = lauf(ob, [konto(ALT, A), konto(ALT, A), konto(EXT, B), konto(EXT, B), konto(EXT, B)], [band, (True, "")])
    check(ok and len(s.klicks) == 1, f"nach dem abgelehnten Druck steht schon das Ziel-Konto → kein zweiter Druck ({len(s.klicks)} Klicks, {code})")

    # die alten Wege bleiben: „nicht mehr das Ziel" → zweiter Versuch; anderer Grund → keiner
    verschoben = (False, "Konto-Auslöser: nach der Hover-Pause liegt am Zielpunkt nicht mehr das Ziel ('150k dll combine|…') — kein Druck")
    ok, code, msg, s, sp = lauf(ob, [konto(ALT, A), konto(ALT, A), konto(ALT, B), konto(ALT, B), konto(ALT, B), konto(EXT, B)], [verschoben, (True, "")])
    check(ok and len(s.klicks) == 2 and "hat sich verschoben" in sp and s.klicks[1][1] == B, f"alter Weg „nicht mehr das Ziel“ unverändert ({len(s.klicks)} Klicks)")
    anders = (False, "Konto-Auslöser: am Zielpunkt liegt ein anderes Fenster — kein Druck")
    ok, code, msg, s, sp = lauf(ob, [konto(ALT, A), konto(ALT, A)] + [konto(ALT, B)] * 6, [anders, (True, "")])
    check(not ok and len(s.klicks) == 1 and msg == TEXT, f"anderer Fehlgrund → kein zweiter Versuch ({len(s.klicks)} Klicks)")
    hover = (False, "Konto-Auslöser: Maus steht @127,106, Ziel NICHT unter dem Zeiger (Hover) — kein Druck")
    ok, code, msg, s, sp = lauf(ob, [konto(ALT, A), konto(ALT, A)] + [konto(ALT, B)] * 6, [hover, (True, "")])
    check(not ok and len(s.klicks) == 1, f"Hover nicht bewiesen → kein zweiter Versuch ({len(s.klicks)} Klicks)")

    # Gegenprüfung 27.11.2026: der einzige Weg „False NACH physischem Druck" — nie ein zweiter Versuch (er schlösse die Liste wieder)
    gedrueckt = (False, "Konto-Auslöser: SendInput abgelehnt")
    ok, code, msg, s, sp = lauf(ob, [konto(ALT, A), konto(ALT, A)] + [konto(ALT, B)] * 6, [gedrueckt, (True, "")])
    check(not ok and len(s.klicks) == 1, f"SendInput abgelehnt (evtl. gedrückt) → kein zweiter Versuch ({len(s.klicks)} Klicks)")

    ok, code, msg, s, sp = lauf(ob, [konto(ALT, A), konto(ALT, A), konto(EXT, A), konto(EXT, A), konto(EXT, A)], [band, (True, "")])
    check(ok and len(s.klicks) == 1, f"gleicher Ort, aber inzwischen steht das Ziel-Konto → Runde neu, kein zweiter Druck ({len(s.klicks)} Klicks, {code})")

    blow = {"popups": [{"titel": "You Hit Your Maximum Loss Limit", "text": "You Hit Your Maximum Loss Limit. Account: " + ALT, "role": "dialog",
                        "rect": [600, 300, 500, 200], "knoepfe": []}]}
    if ob.tsx_blow_dialog(blow["popups"]):
        mit_meldung = dict(konto(ALT, B), **blow)
        ok, code, msg, s, sp = lauf(ob, [konto(ALT, A), konto(ALT, A)] + [mit_meldung] * 8, [band, (True, "")])
        check(not ok and len(s.klicks) <= 1 and "gewandert" not in sp, f"Loss-Limit-Meldung nach dem abgelehnten Druck → kein zweiter Auslöser-Versuch ({len(s.klicks)} Klicks, {code})")
    else:
        check(False, "Test-Meldung wird von tsx_blow_dialog nicht erkannt (Test anpassen)")

    kaputt = {"konto": {"aktiv": f"150K DLL Combine|{ALT}", "kontonr": ALT, "rect": [None, None, 192, 34], "liste_offen": False, "zu": {}}, "popups": "x"}
    try:
        ok, code, msg, s, sp = lauf(ob, [konto(ALT, A), konto(ALT, A)] + [kaputt] * 8, [band, (True, "")])
        check(not ok and msg == TEXT and len(s.klicks) == 1, f"kaputtes Rechteck/Popups im frischen Stand → sauberer Abbruch, keine Ausnahme ({len(s.klicks)} Klicks)")
    except Exception as e:
        check(False, f"kaputtes Rechteck im frischen Stand wirft {type(e).__name__}: {e}")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
