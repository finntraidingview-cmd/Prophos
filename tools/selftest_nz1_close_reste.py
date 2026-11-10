#!/usr/bin/env python3
"""Selbsttest NZ1 — Echo-Schließweg robuster (Master 10.11.2026 nach CPI 14:30: News-Schließung bei Moritz 4× „Zeilen-Scan ohne Treffer“,
bei Jacob 5× „geklickt, aber kein Close-Dialog“, bei Artur 1× „Zeile nicht gefunden“; in jeder Spur stand ein offenes „Order: …“-Fenster).
Die ECHTEN Funktionen aus mt5-copier/order_bot.py laufen gegen Attrappen (Maus, Menü, Fenster, pywinauto) — ohne Windows.
 a) close_rest_art: Order-/Ändern-/Druck-Rest ja; Haftungsausschluss, Login, Charts, Werkzeugleiste nie.
 b) _close_reste_raeumen: Order-Rest per ESC, Druckdialog per Abbrechen, Haftungsausschluss/Chart unberührt, Unsichtbares übersprungen,
    stehen gebliebener Rest gezählt und in der Spur.
 c) _close_klicken: bleibt ein sichtbarer Rest stehen → „rest_offen“, KEIN einziger Klick; hängt ein Menü → Abbruch ohne weiteren
    Links-Klick; Zeile im Band wie bisher; nie ein Punkt über der Fenstermitte.
 d) Quelltext: Reste werden VOR dem Handel-Reiter geräumt; jedem ESC am F9-Dialog in run() folgt _f9_dialog_zu (vor und nach dem Fill).
 e) _f9_dialog_zu: zu nach ESC → still True; bleibt offen → Fokus+ESC; ganz stur → False + Warnung in der Spur.
 f) close_journal_zeilen (Grund aus dem Journal bei „geklickt, aber kein Close-Dialog“) und _kein_menue_offen.
Aufruf: python3 tools/selftest_nz1_close_reste.py"""
import os
import sys
import types

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


class Spur(list):
    def sekunden(self):
        return 0.0


# ── a) close_rest_art ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────
A = ob.close_rest_art
check(A("Order: NAS100 - NASDAQ 100 I", ["Sell by Market", "Buy by Market"]) == "order", "a: F9-Dialog „Order: NAS100 …“ = Rest")
check(A("Order: NDX100 - US Tech 100 ", []) == "order", "a: „Order: NDX100 - US Tech 100“ = Rest")
check(A("Order", ["OK"]) == "order", "a: Ergebnis-Seite „Order“ = Rest")
check(A("Position #123", ["#1234567 buy 1.00 NAS100 sl: 1 tp: 2 Ändern", "Abbrechen"]) == "aendern", "a: Ändern-Dialog (langer Knopf) = Rest")
check(A("Drucken", ["Drucken", "Abbrechen"]) == "drucken", "a: Druckdialog = Rest")
check(A("Marktübersicht", ["Exchange"]) is None and A("Panel", ["Modify"]) is None and A("x", ["Position ändern"]) is None,
      "a: „Exchange“/„Modify“/Reiter „Position ändern“ allein = kein Ändern-Rest")
check(A("Ein-Klick-Handel", ["Ich akzeptiere die allgemeinen Geschäftsbedingungen", "Abbrechen"]) is None, "a: Haftungsausschluss nie")
check(A("Haftung", ["I accept the terms and conditions"]) is None, "a: Zustimmen-Knopf ohne Titel nie")
check(A("Einloggen", ["OK", "Abbrechen"]) is None, "a: Login-Dialog nie")
check(A("Login", ["OK"]) is None, "a: Login-Dialog EN nie")
check(A("NAS100,M1", []) is None, "a: Chart nie")
check(A("Werkzeuge", []) is None and A("Toolbox", []) is None and A("Ordner", []) is None, "a: Werkzeuge/Toolbox/„Ordner“ nie")
check(A("", []) is None and A(None, None) is None, "a: leer = nichts")

# ── b) _close_reste_raeumen mit Attrappen-Desktop ────────────────────────────────────────────────────────────────────────────────────
class Knopf:
    def __init__(self, text, fenster=None, wirkt=True):
        self.text, self.fenster, self.wirkt, self.geklickt = text, fenster, wirkt, 0

    def window_text(self):
        return self.text

    def click(self):
        self.geklickt += 1
        if self.wirkt and self.fenster is not None:
            self.fenster.sichtbar = False


class Fenster:
    def __init__(self, titel, knoepfe=(), pid=7, klasse="#32770", esc_wirkt=True, sichtbar=True, handle=None):
        self.titel, self.pid, self.esc_wirkt, self.sichtbar = titel, pid, esc_wirkt, sichtbar
        self.element_info = types.SimpleNamespace(process_id=pid, class_name=klasse, handle=handle)
        self.handle = handle
        self.knoepfe = [Knopf(t, self) if isinstance(t, str) else t for t in knoepfe]
        self.esc = 0
        self.fokus = 0

    def window_text(self):
        return self.titel

    def is_visible(self):
        return self.sichtbar

    def descendants(self, control_type=None):
        return list(self.knoepfe) if control_type == "Button" else []

    def set_focus(self):
        self.fokus += 1


haupt = Fenster("26696076 - Demo: Terminal", klasse=ob.MT5_KLASSE)
order_rest = Fenster("Order: NAS100 - NASDAQ 100 I", ["Sell by Market", "Buy by Market"], handle=101)
druck = Fenster("Drucken", ["Drucken", "Abbrechen"], handle=102)
haftung = Fenster("Ein-Klick-Handel", ["Ich akzeptiere die allgemeinen Geschäftsbedingungen", "Abbrechen"], handle=103)
chart = Fenster("NAS100,M1", [], klasse="AfxFrameOrView", handle=104)
unsichtbar = Fenster("Order: NAS100", ["Buy"], sichtbar=False, handle=105)
fremd = Fenster("Order: EURUSD", ["Buy"], pid=99, handle=106)
stur = Fenster("Order: NAS100 - zweiter", ["Buy"], esc_wirkt=False, handle=107)                       # Dialog (#32770): WM_CLOSE erlaubt
stur_kind = Fenster("Order: NAS100 - Kind", ["Buy"], esc_wirkt=False, klasse="AfxWnd140", handle=108)  # kein Dialog: nie WM_CLOSE
posted = []
import ctypes  # noqa: E402
_windll_alt = getattr(ctypes, "windll", None)


def _post(h, msg, wp, lp):
    posted.append((h, msg))
    for f in (stur, stur_kind):
        if f.handle == h:
            f.sichtbar = False
    return 1


ctypes.windll = types.SimpleNamespace(user32=types.SimpleNamespace(PostMessageW=_post))

fake_pw = types.ModuleType("pywinauto")


class _Desk:
    def __init__(self, backend=None):
        pass

    def windows(self):
        return [haupt, druck, haftung, fremd, unsichtbar]


fake_pw.Desktop = _Desk
alt = {k: getattr(ob, k) for k in ("_kind_fenster", "_el_tasten", "_warte")}
sys.modules["pywinauto"] = fake_pw


def _el_tasten(el, text, set_foreground=True, **kw):
    if text == "{ESC}" and isinstance(el, Fenster):
        el.esc += 1
        if el.esc_wirkt:
            el.sichtbar = False


ob._kind_fenster = lambda w, voll=False: [order_rest, chart, stur, stur_kind]
ob._el_tasten = _el_tasten
ob._warte = lambda a, b: None
t = Spur()
blieb = ob._close_reste_raeumen(haupt, t)
spur = " | ".join(t)
check(not order_rest.sichtbar and order_rest.esc == 1 and order_rest.fokus == 1, "b: Order-Rest (Kind-Fenster) per Fokus + ESC zu")
check(not druck.sichtbar and druck.knoepfe[1].geklickt == 1 and druck.knoepfe[0].geklickt == 0, "b: Druckdialog per Abbrechen zu, „Drucken“ nie")
check(haftung.sichtbar and haftung.esc == 0 and all(k.geklickt == 0 for k in haftung.knoepfe), "b: Haftungsausschluss unberührt")
check(chart.sichtbar and chart.esc == 0, "b: Chart unberührt")
check(fremd.esc == 0 and unsichtbar.esc == 0, "b: fremder Prozess + unsichtbares Fenster übersprungen")
check(not stur.sichtbar and posted == [(107, 0x0010)], "b: sturer Dialog (#32770) per WM_CLOSE zu")
check(blieb == 1 and stur_kind.sichtbar and all(h != 108 for h, _ in posted), "b: Kind-Fenster ohne Dialogklasse nie WM_CLOSE, als stehen geblieben gezählt")
check("'Order: NAS100' im Prozess, aber unsichtbar — übersprungen" in spur, "b: unsichtbares Order-Fenster steht in der Spur")
check("'Order: NAS100 - NASDAQ 100 I' (order) weggeräumt (ESC)" in spur and "(drucken) weggeräumt (Abbrechen)" in spur
      and "'Order: NAS100 - zweiter' (order) weggeräumt (Fenster-X)" in spur and "'Order: NAS100 - Kind' (order) blieb stehen" in spur,
      "b: Spur nennt jeden Fund und seinen Ausgang")
if _windll_alt is None:
    del ctypes.windll
else:
    ctypes.windll = _windll_alt
# ohne pywinauto (Mac/andere Selbsttests): still 0, kein Absturz
del sys.modules["pywinauto"]
_imp = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__


def _ohne_pw(name, *a, **k):
    if name == "pywinauto":
        raise ImportError("kein pywinauto")
    return _imp(name, *a, **k)


import builtins  # noqa: E402
builtins.__import__ = _ohne_pw
try:
    check(ob._close_reste_raeumen(haupt, Spur()) == 0, "b: ohne pywinauto → 0, kein Absturz")
finally:
    builtins.__import__ = _imp

# ── c) _close_klicken ────────────────────────────────────────────────────────────────────────────────────────────────────────────────
class Rect:
    def __init__(self, l, t, r, b):
        self.left, self.top, self.right, self.bottom = l, t, r, b


class Haupt:
    def __init__(self, hoehe=1000):
        self.r = Rect(0, 0, 1600, hoehe)

    def rectangle(self):
        return self.r


def lauf(liste_von, liste_bis, zeile_y, hoehe=1000, reste=0, menue_haengt_ab=None):
    """liste_von..liste_bis = y-Bereich der Handel-Liste (Menü, Eintrag ausgegraut); zeile_y ± 9 = Positions-Zeile (Eintrag klickbar);
    außerhalb: Chart (kein_menue). reste = Rückgabe von _close_reste_raeumen; menue_haengt_ab = ab dem n-ten Punkt bleibt ein Menü offen.
    Rückgabe (ausgang, rechtsklick-y-Liste, links-klick-Zahl, spur)."""
    klicks, links, maus = [], [0], {"y": None}
    zustand = {"zu": False, "punkt": 0}

    def _klick_absolut(x, y, taste="links"):
        if taste == "rechts":
            klicks.append(y)
            maus["y"] = y
        else:
            links[0] += 1
        return True

    def _menue(timeout=0.8):
        zustand["punkt"] += 1
        y = maus["y"]
        if zeile_y is not None and abs(y - zeile_y) <= 9:
            zustand["zu"] = True
            return "geklickt"
        if liste_von <= y <= liste_bis:
            return "ausgegraut"
        return "kein_menue"

    def _kein_menue_offen(pid=None):
        return not (menue_haengt_ab is not None and zustand["punkt"] >= menue_haengt_ab)

    ersatz = dict(
        _einklick_haftung_annehmen=lambda w, trail, melden=False: "keiner",
        _fremde_dialoge_schliessen=lambda w: None,
        _close_reste_raeumen=lambda w, trail: reste,
        _handel_tab_aktivieren=lambda w, trail, mg, anker_pfad=None: "suche",
        is_paused=lambda: False,
        _anker_lesen=lambda p: {},
        _anker_schreiben=lambda p, **k: None,
        _maus_fahren=lambda x, y, schritte=3: None,
        klick_zoegern=lambda *a, **k: (0, 0),
        _warte=lambda a, b: None,
        _klick_absolut=_klick_absolut,
        _kontextmenue_close_klicken=_menue,
        _kein_menue_offen=_kein_menue_offen,
        _el_tasten=lambda *a, **k: None,
        _finde_close_dialog=lambda w, ticket: (None, None),
    )
    vorher = {k: getattr(ob, k) for k in ersatz}
    for k, v in ersatz.items():
        setattr(ob, k, v)
    try:
        t = Spur()
        aus = ob._close_klicken(Haupt(hoehe), 627122537, t, "/tmp/anker-x.json", lambda: zustand["zu"])
    finally:
        for k, v in vorher.items():
            setattr(ob, k, v)
    return aus, klicks, links[0], " | ".join(t)


aus, kl, li, sp = lauf(600, 1000, 700, reste=1)
check(aus == "rest_offen" and not kl and li == 0, "c1: Rest bleibt stehen → rest_offen, kein einziger Klick")
aus, kl, li, sp = lauf(600, 1000, 700)
check(aus == "zu" and kl and all(y >= 500 for y in kl), "c2: Zeile im Band wie bisher → zu, nie über der Mitte")
aus, kl, li, sp = lauf(200, 1000, 230)
check(aus == "kein_treffer" and all(y >= 500 for y in kl), "c3: Zeile über der Mitte → kein_treffer wie bisher (kein Scan nach oben)")
aus, kl, li, sp = lauf(600, 1000, None, menue_haengt_ab=3)
check(aus == "menue_haengt" and li == 3 and len(kl) == 3 and "Kontextmenü blieb offen" in sp, "c4: Menü hängt → Abbruch, kein weiterer Links-Klick")
_qk = __import__("inspect").getsource(ob._close_klicken)
_i = _qk.find("def _punkt_klicken")
_blk = _qk[_i:_qk.find("return _kontextmenue_close_klicken", _i)]
check(_blk.find("klick_zoegern()") < _blk.find("_kein_menue_offen(_pid)") < _blk.find("_klick_absolut(px_, py_)"),
      "c4: Menü-Beweis direkt vor dem Links-Klick (nach Anfahrt + Zögern), nur Menüs des Terminal-Prozesses")
check("rest_offen" in inspect_src if (inspect_src := __import__("inspect").getsource(ob.run_close)) else False,
      "c5: run_close meldet rest_offen eigens (nichts geklickt)")

# ── d) Quelltext ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
import inspect  # noqa: E402
q = inspect.getsource(ob._close_klicken)
check(0 < q.find("_close_reste_raeumen(w, trail)") < q.find("_handel_tab_aktivieren("), "d: Reste VOR dem Handel-Reiter geräumt")
qr = inspect.getsource(ob.run)
n_esc = qr.count('_el_tasten(dlg, "{ESC}", set_foreground=False)')
n_zu = qr.count("_f9_dialog_zu(dlg, trail)")
check(n_zu == 7 and n_esc >= 7, f"d: _f9_dialog_zu an allen 7 ESC-Stellen nach dem Dialog-Fund in run() ({n_zu} Aufrufe, {n_esc} ESC)")
pos_zu = [i for i in range(len(qr)) if qr.startswith("_f9_dialog_zu(dlg, trail)", i)]
check(all(qr.rfind('_el_tasten(dlg, "{ESC}", set_foreground=False)', 0, i) > qr.rfind("_f9_dialog_zu(dlg, trail)", 0, i) for i in pos_zu),
      "d: jedem _f9_dialog_zu geht ein eigenes ESC voraus")

# ── e) _f9_dialog_zu ────────────────────────────────────────────────────────────────────────────────────────────────────────────────
ob._el_tasten = _el_tasten
ob._warte = lambda a, b: None
d1 = Fenster("Order: NAS100", sichtbar=False)
t1 = Spur()
check(ob._f9_dialog_zu(d1, t1) is True and not t1 and d1.esc == 0, "e: schon zu → True, still, kein zweites ESC")
d2 = Fenster("Order: NAS100")
t2 = Spur()
check(ob._f9_dialog_zu(d2, t2) is True and d2.fokus == 1 and d2.esc == 1 and "mit Fokus + ESC zu" in " ".join(t2), "e: offen → Fokus + ESC, Spur")
d3 = Fenster("Order: NAS100", esc_wirkt=False, handle=None)
t3 = Spur()
check(ob._f9_dialog_zu(d3, t3) is False and "⚠ F9-Dialog blieb offen" in " ".join(t3), "e: stur → False + Warnung")
# ── f) Journal + Menü ────────────────────────────────────────────────────────────────────────────────────────────────────────────
J = ["CS\t0\t13:11:40.100\tTrades\t'26696076': market sell 17.99 NAS100, close #627122537 sl: 0 tp: 0",
     "CS\t0\t13:11:41.200\tTrades\t'26696076': failed market sell 17.99 NAS100, close #627122537 [Off quotes]",
     "CS\t0\t13:11:42.000\tTrades\t'26696076': market sell 1.00 EURUSD, close #111",
     "CS\t0\t12:00:00.000\tTrades\t'26696076': market sell 17.99 NAS100, close #627122537 (alt)"]
ab = 13 * 3600 + 11 * 60 + 39
z = ob.close_journal_zeilen(J, 627122537, ab)
check(len(z) == 1 and z[0].startswith("failed market sell 17.99 NAS100, close #627122537 [Off quotes]"), "f: letzte Journal-Zeile zum Ticket, ohne Vorspann")
z2 = ob.close_journal_zeilen(J, 627122537, ab, n=5)
check(len(z2) == 2 and "#111" not in " ".join(z2) and "(alt)" not in " ".join(z2), "f: nur seit dem Klick, nur dieses Ticket")
check(ob.close_journal_zeilen(["CS\t0\t13:11:41.200\tTrades\t'1': failed market sell 1 NAS100, close #6271225370 [x]"], 627122537, ab) == [],
      "f: Ticket-Präfix (#6271225370) zählt nicht")
check(ob.close_journal_zeilen(J, None, ab) == [] and ob.close_journal_zeilen([], 627122537, ab) == [], "f: ohne Ticket/Zeilen leer")
fake_pw2 = types.ModuleType("pywinauto")
esc_log = []
sys.modules["pywinauto"] = fake_pw2
_mo, _tg = ob._menue_offen_bei, ob._tasten_gestreut
offen = {"n": 1}


def _menue_offen(pid):
    if offen["n"] > 0:
        offen["n"] -= 1
        return "Menü"
    return None


ob._menue_offen_bei = _menue_offen
ob._tasten_gestreut = lambda k, **kw: esc_log.append(k)
ob._warte = lambda a, b: None
check(ob._kein_menue_offen() is True and esc_log == ["{ESC}"], "f: offenes Menü → ESC, dann frei")
offen["n"], esc_log[:] = 99, []
check(ob._kein_menue_offen() is False and len(esc_log) == 3, "f: Menü bleibt offen → False nach 3× ESC")
ob._menue_offen_bei, ob._tasten_gestreut = _mo, _tg


class _M:
    def __init__(self, pid, klasse="#32768"):
        self.element_info = types.SimpleNamespace(class_name=klasse, control_type="Menu" if klasse == "#32768" else "Pane", process_id=pid)

    def window_text(self):
        return "Kontext"


fake_pw2.Desktop = lambda backend=None: types.SimpleNamespace(windows=lambda: [_M(55), _M(7, "Chrome_Widget")])
check(ob._menue_offen_bei(7) is None and ob._menue_offen_bei(55) == "Kontext" and ob._menue_offen_bei(None) == "Kontext",
      "f: Menü einer fremden App blockiert den Terminal-Close nicht")
del sys.modules["pywinauto"]

for k, v in alt.items():
    setattr(ob, k, v)

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER: " + "; ".join(FEHLER))
sys.exit(1 if FEHLER else 0)
