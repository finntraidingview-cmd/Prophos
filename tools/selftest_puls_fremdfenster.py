#!/usr/bin/env python3
"""Selbsttest Puls: fremdes Fenster am Klickpunkt (mt5-copier/order_bot.py, _AugenSitzung._win_klick, 09.10.2026).

Aufruf:  python3 tools/selftest_puls_fremdfenster.py
Anlass: Balance lesen am PC pc-xxxxxx, 09.10.2026 01:42 Dubai — am Kontextmenü neben „Tradovate" lag ein normales Chrome-Fenster
(„Tradeify Futures - User Dashboard"), der Riegel verweigerte richtig, der Lauf 1 s später traf denselben Knopf. Seitdem holt Puls das
Puls-Chrome bei fremdem Fenster EINMAL neu nach vorn und prüft neu; der Riegel bleibt (nie ein Druck in ein fremdes Fenster).
Attrappe: alle Windows-/Maus-Helfer des Moduls werden ersetzt, nichts klickt wirklich.
  (a) fremd beim 1. Blick, frei beim 2. → genau EIN Druck, Spur „2. Versuch"
  (b) fremd bei beiden Blicken → kein Druck, Spur + fremd_hinweis() mit Titel und „immer im Vordergrund?"
  (c) frei beim 1. Blick → wie bisher: ein Blick, ein Druck, kein zweiter Versuch
  (d) _cdp_abmelden hängt den Hinweis an seine Meldung.
  (e) frei vor dem Hover, fremd unmittelbar vor dem Druck (SOLL-Prüfung nach dem Hover-Beweis) → kein Druck, Titel, KEIN Nach-vorn.
Je Klick gibt es seit der SOLL-Prüfung einen Fenster-Blick mehr (direkt vor SendInput)."""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "mt5-copier"))
import order_bot as ob  # noqa: E402

PULS, FREMD = 4264534, 918614
TITEL = "Tradeify Futures - User Dashboard - Google Chrome"


def sitzung():
    s = ob._AugenSitzung.__new__(ob._AugenSitzung)
    s.trail = []
    s.maus = None
    s._win_vorn = lambda: (PULS, "")
    s.lese_js = lambda js: ({"hover": True} if js != ob.WIN_GEO_JS else {})
    return s


def lauf(blicke):
    """blicke = Fenster-Kennungen, die _win_root_am_punkt der Reihe nach meldet. -> (ok, sitzung, zähler)"""
    z = {"blick": 0, "druck": 0, "vorn": 0, "fahren": 0}
    folge = list(blicke)

    def root(x, y):
        z["blick"] += 1
        w = folge.pop(0) if folge else PULS
        return w, (TITEL if w == FREMD else "NQ1! Puls-Chrome")
    ersatz = {
        "_win_root_am_punkt": root,
        "_maus_fahren": lambda x, y: z.__setitem__("fahren", z["fahren"] + 1),
        "_cursor_set": lambda x, y: None,
        "_warte": lambda a, b=0: None,
        "_win_vordergrund": lambda: PULS,
        "_win_nach_vorn": lambda h: z.__setitem__("vorn", z["vorn"] + 1),
        "_klick_absolut": lambda x, y, doppel=False: z.__setitem__("druck", z["druck"] + 1) or True,
        "tv_bildschirm_punkt": lambda r, g, k: ((400, 1280), ""),
        "_klient_rechteck": lambda h: (0, 0, 3840, 2160),
        "cdp_klickpunkt": lambda r: (100.0, 200.0),
    }
    alt = {n: getattr(ob, n) for n in ersatz}
    try:
        for n, f in ersatz.items():
            setattr(ob, n, f)
        s = sitzung()
        ok = s._win_klick([90, 190, 20, 20], "Kontextmenü neben Tradovate")
    finally:
        for n, f in alt.items():
            setattr(ob, n, f)
    return ok, s, z


def main():
    ok_ges = True

    def check(bed, text):
        nonlocal ok_ges
        print(("✓ " if bed else "✗ ") + text)
        ok_ges = ok_ges and bool(bed)

    # (a) fremd → frei
    ok, s, z = lauf([FREMD, PULS])
    spur = " | ".join(s.trail)
    check(ok and z["druck"] == 1, "(a) fremd beim 1. Blick, frei beim 2. → genau ein Druck")
    check(z["blick"] == 3 and z["vorn"] == 1 and z["fahren"] == 2, "(a) einmal nach vorn, Zeiger neu hingefahren, neu geprüft, vor dem Druck nochmal")
    check("2. Versuch" in spur and "geklickt" in spur and s.fremd_hinweis() == "", "(a) Spur nennt den 2. Versuch, kein Hinweis übrig")
    # (b) fremd → fremd
    ok, s, z = lauf([FREMD, FREMD])
    spur = " | ".join(s.trail)
    check(not ok and z["druck"] == 0, "(b) fremd bei beiden Blicken → kein Druck")
    check(z["blick"] == 2 and z["vorn"] == 1, "(b) genau ein zweiter Versuch, nicht mehr")
    h = s.fremd_hinweis()
    check("Tradeify Futures - User Dashboard" in h and "immer im Vordergrund?" in h, "(b) fremd_hinweis() nennt Titel + „immer im Vordergrund?“")
    check("liegt weiter ein anderes Fenster" in spur and "immer im Vordergrund?" in spur, "(b) Spur mit Titel-Hinweis")
    # (c) sofort frei
    ok, s, z = lauf([PULS])
    check(ok and z["druck"] == 1 and z["blick"] == 2 and z["vorn"] == 0 and z["fahren"] == 1, "(c) frei → ein Druck, Blick vor dem Hover + vor dem Druck")
    # (e) erst nach dem Hover fremd
    ok, s, z = lauf([PULS, FREMD])
    spur = " | ".join(s.trail)
    check(not ok and z["druck"] == 0 and z["vorn"] == 0 and z["blick"] == 2, "(e) fremd erst vor dem Druck → kein Druck, kein zweites Nach-vorn")
    check("vor dem Druck liegt am Zielpunkt" in spur and "Tradeify Futures - User Dashboard" in s.fremd_hinweis(), "(e) Spur + Titel-Hinweis")
    # (d) Meldung von _cdp_abmelden
    import inspect
    q = inspect.getsource(ob._cdp_abmelden)
    check("fremd_hinweis()" in q and "nicht abgemeldet." in q, "(d) _cdp_abmelden hängt den Hinweis an die Meldung")
    q_wk = inspect.getsource(ob._AugenSitzung._win_klick)
    check("time.sleep(" not in q_wk, "Jitter-Regel: keine nackten sleeps in _win_klick")
    print("\nALLES OK" if ok_ges else "\nFEHLER")
    return 0 if ok_ges else 1


if __name__ == "__main__":
    sys.exit(main())
