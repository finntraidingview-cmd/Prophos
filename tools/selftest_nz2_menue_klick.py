#!/usr/bin/env python3
"""Selbsttest NZ2 (Master 10.11.2026, Befund JU1: Echo-Justage 24 von 65 gescheitert, 22× „Aendern-Dialog nach 22–35 s nicht offen“ — fast nur
4K-/2560er-PCs; dieselbe Form wie die CPI-Close-Fehler bei Jacob „geklickt, aber kein Close-Dialog“): „Menü zu“ beweist auf diesen PCs nicht,
dass der Menübefehl lief. Die ECHTEN Funktionen aus mt5-copier/order_bot.py laufen gegen Attrappen — ohne Windows.
 a) _menuepunkt_ausloesen: klick_zuerst → echter Klick VOR invoke(); Standard wie bisher invoke zuerst.
 b) _reihen_scan: Menü „Ändern…“ geklickt, aber kein Dialog → an DERSELBEN Stelle Doppelklick (vorher: nächster Punkt bis zur 20-s-Frist).
    Treffer per Menü bleibt wie bisher ohne Doppelklick; ausgegraut/kein Menü unverändert; Frist abgelaufen → kein Doppelklick.
 c) _close_klicken: Menü „Position schliessen“ geklickt, kein Dialog → Warten CLOSE_NACH_MENUE_S, dann EIN Zweitversuch an derselben Stelle mit
    echtem Klick; Position inzwischen weg → kein Zweitversuch; nie mehr als zwei Menü-Klicks je Lauf.
Aufruf: python3 tools/selftest_nz2_menue_klick.py"""
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


class Rect:
    def __init__(self, l, t, r, b):
        self.left, self.top, self.right, self.bottom = l, t, r, b


class Haupt:
    def __init__(self, hoehe=1000):
        self.r = Rect(0, 0, 1600, hoehe)
        self.element_info = types.SimpleNamespace(process_id=7)

    def rectangle(self):
        return self.r


def mit(ersatz, f):
    vorher = {k: getattr(ob, k) for k in ersatz}
    for k, v in ersatz.items():
        setattr(ob, k, v)
    try:
        return f()
    finally:
        for k, v in vorher.items():
            setattr(ob, k, v)


# ── a) _menuepunkt_ausloesen ────────────────────────────────────────────────────────────────────────────────────────────────────────
class Item:
    def __init__(self, log):
        self.log = log

    def invoke(self):
        self.log.append("invoke")

    def rectangle(self):
        return Rect(10, 10, 100, 30)

    def click_input(self):
        self.log.append("click_input")


for zuerst, erwartet in ((True, "klick"), (False, "invoke")):
    log = []
    offen = {"n": 1}

    def _menue_offen():
        return offen["n"] > 0

    def _echo_klick(r, schritte=3):
        log.append("klick")
        offen["n"] = 0
        return True

    def _invoke_zu():
        pass
    it = Item(log)
    it.invoke = (lambda: (log.append("invoke"), offen.update(n=0)))
    ok = mit(dict(_menue_offen=_menue_offen, _echo_klick=_echo_klick, _warte=lambda a, b: None),
             lambda: ob._menuepunkt_ausloesen(it, klick_zuerst=zuerst))
    check(ok and log[0] == erwartet and len(log) == 1, f"a: klick_zuerst={zuerst} → zuerst {erwartet}, dann Schluss (Menü zu)")

# ── b) _reihen_scan ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
DLG = object()


def scan(zeile_y=684, menue_wirkt=False, doppel_wirkt=True, bis_abgelaufen=False, liste=(600, 1000)):
    klicks = []
    maus = {"y": None}

    def _klick_absolut(x, y, taste="links", doppel=False):
        klicks.append(("doppel" if doppel else taste, y))
        maus["y"] = y
        if doppel:
            maus["doppel"] = y
        return True

    def _menue(timeout=0.8):
        y = maus["y"]
        if abs(y - zeile_y) <= 9:
            maus["menue_ok"] = y
            return "geklickt"
        if liste[0] <= y <= liste[1]:
            return "ausgegraut"
        return "kein_menue"

    def _finde(w, timeout=1.2):
        if menue_wirkt and maus.get("menue_ok") is not None and "doppel" not in maus:
            return DLG
        if doppel_wirkt and maus.get("doppel") is not None and abs(maus["doppel"] - zeile_y) <= 9:
            return DLG
        return None

    import time as _t
    ersatz = dict(
        _punkt_frei=lambda w, x, y: True, _maus_fahren=lambda x, y, schritte=3: None, klick_zoegern=lambda *a, **k: (0, 0),
        _warte=lambda a, b: None, _klick_absolut=_klick_absolut, _kontextmenue_aendern_klicken=_menue, _finde_aendern_dialog=_finde,
        _el_tasten=lambda *a, **k: None, _dialog_gehoert_zu=lambda d, t: True, _anker_lesen=lambda p: {}, _anker_schreiben=lambda p, **k: None,
        _fremde_dialoge_schliessen=lambda w: None, is_paused=lambda: False)
    t = Spur()
    d = mit(ersatz, lambda: ob._reihen_scan(Haupt(), 627122537, t, 500, anker_pfad="/tmp/anker-x.json",
                                            bis=(_t.time() - 1) if bis_abgelaufen else (_t.time() + 60), max_punkte=10))
    return d, klicks, " | ".join(t)


d, kl, sp = scan(menue_wirkt=False, doppel_wirkt=True)
doppel = [y for a, y in kl if a == "doppel"]
check(d is DLG and doppel and abs(doppel[0] - 684) <= 9 and len(doppel) == 1, "b1: Menü geklickt, kein Dialog → Doppelklick an DERSELBEN Stelle öffnet ihn")
check("Aendern-Dialog offen (Doppelklick nach Menue-Scan" in sp, "b1: Spur nennt den Weg „Doppelklick nach Menue“")
d, kl, sp = scan(menue_wirkt=True)
check(d is DLG and not [y for a, y in kl if a == "doppel"], "b2: Menü wirkt → wie bisher, kein Doppelklick")
d, kl, sp = scan(menue_wirkt=False, doppel_wirkt=False)
dz = [y for a, y in kl if a == "doppel"]
check(d is None and all(abs(y - 684) <= 9 for y in dz) and len(dz) >= 1, "b3: auch der Doppelklick hilft nicht → nur an Zeilen-Punkten doppelt, sonst wie bisher")
d, kl, sp = scan(bis_abgelaufen=True)
check(d is None and not kl, "b4: Frist schon um → kein Klick")
d, kl, sp = scan(zeile_y=-999, menue_wirkt=False)
check(d is None and not [y for a, y in kl if a == "doppel"], "b5: nur ausgegraute Punkte (keine Zeile) → nie Doppelklick")

# ── c) _close_klicken ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
class _Knopf:
    gedrueckt = 0

    def window_text(self):
        return "Schliessen #627122537 buy 17.99 NAS100 zum Marktpreis"

    def rectangle(self):
        return Rect(10, 10, 200, 40)

    def set_focus(self):
        pass

    def has_keyboard_focus(self):
        return True

    def click(self):
        _Knopf.gedrueckt += 1

    def click_input(self):
        _Knopf.gedrueckt += 1


class _Dlg:
    def is_visible(self):
        return _Knopf.gedrueckt == 0


KNOPF, DLG2 = _Knopf(), _Dlg()


def close_lauf(wirkt_bei, weg_vor_zweit=False, journal=(True, []), dialog_spaet=False):
    """wirkt_bei: 'erst' = erster Menü-Klick schließt, 'zweit' = nur der echte Klick (klick_zuerst) schließt, None = nichts schließt."""
    zust = {"zu": False, "menue": 0, "zuerst": []}
    maus = {"y": None}

    def _klick_absolut(x, y, taste="links"):
        if taste == "rechts":
            maus["y"] = y
        return True

    def _menue(timeout=0.8, klick_zuerst=False):
        if abs(maus["y"] - 684) <= 9:
            zust["menue"] += 1
            zust["zuerst"].append(klick_zuerst)
            if wirkt_bei == "erst" or (wirkt_bei == "zweit" and klick_zuerst):
                zust["zu"] = True
            return "geklickt"
        return "ausgegraut" if 600 <= maus["y"] <= 1000 else "kein_menue"

    zust["pw"] = 0

    def position_weg():
        zust["pw"] += 1
        # c4: erst NACH der ersten Warteschleife weg (ihre Aufrufe laufen bis CLOSE_NACH_MENUE_S, dann prüft der neue Zweig)
        if weg_vor_zweit and zust.get("warte_vorbei"):
            return True
        return zust["zu"]

    import time as _t
    t_start = {"t": None}

    def _finde_close_dialog(w, ticket):
        if t_start["t"] is None:
            t_start["t"] = _t.time()
        if _t.time() - t_start["t"] >= 0.19:
            zust["warte_vorbei"] = True
        if dialog_spaet and zust.get("warte_vorbei"):
            return DLG2, KNOPF
        return None, None

    ersatz = dict(
        _einklick_haftung_annehmen=lambda w, trail, melden=False: "keiner", _fremde_dialoge_schliessen=lambda w: None,
        _close_reste_raeumen=lambda w, trail: [], _handel_tab_aktivieren=lambda w, trail, mg, anker_pfad=None: "suche",
        is_paused=lambda: False, _anker_lesen=lambda p: {}, _anker_schreiben=lambda p, **k: None, _maus_fahren=lambda x, y, schritte=3: None,
        klick_zoegern=lambda *a, **k: (0, 0), _warte=lambda a, b: None, _klick_absolut=_klick_absolut, _kontextmenue_close_klicken=_menue,
        _kein_menue_offen=lambda pid=None: True, _el_tasten=lambda *a, **k: zust.setdefault("esc", []).append(a[1] if len(a) > 1 else None),
        _finde_close_dialog=_finde_close_dialog,
        CLOSE_NACH_MENUE_S=0.2, _echo_klickziel=lambda r: (20, 20))
    t = Spur()
    aus = mit(ersatz, lambda: ob._close_klicken(Haupt(), 627122537, t, "/tmp/anker-x.json", position_weg,
                                                journal_seit_klick=(lambda: journal) if journal is not None else None))
    return aus, zust, " | ".join(t)


aus, z, sp = close_lauf("erst")
check(aus == "zu" and z["menue"] == 1 and z["zuerst"] == [False], "c1: erster Klick wirkt → zu, kein Zweitversuch")
aus, z, sp = close_lauf("zweit")
check(aus == "zu" and z["menue"] == 2 and z["zuerst"] == [False, True] and "Zweitversuch mit echtem Klick" in sp,
      "c2: erster Klick ohne Wirkung → EIN Zweitversuch mit echtem Klick an derselben Stelle → zu")
aus, z, sp = close_lauf(None)
check(aus == "ohne_wirkung" and z["menue"] == 2, "c3: beides ohne Wirkung → ohne_wirkung, nie mehr als zwei Menü-Klicks")
aus, z, sp = close_lauf(None, weg_vor_zweit=True)
check(aus == "zu" and z["menue"] == 1, "c4: Position nach dem Warten weg → kein Zweitversuch")
check(ob.CLOSE_NACH_MENUE_S == 6.0, "c5: Warten nach dem Menüpunkt 6 s (vorher 3 s)")
aus, z, sp = close_lauf("zweit", journal=(False, []))
check(aus == "ohne_wirkung" and z["menue"] == 1 and "Journal nicht lesbar, KEIN Zweitversuch" in sp, "c6: Journal nicht lesbar → KEIN Zweitversuch (Prüfer M1)")
aus, z, sp = close_lauf("zweit", journal=(True, ["market buy 17.99 NAS100, close #627122537"]))
check(aus == "ohne_wirkung" and z["menue"] == 1 and "KEIN Zweitversuch" in sp and "Anfrage zu #627122537" in sp,
      "c7: Journal zeigt eine Anfrage zum Ticket → KEIN Zweitversuch, nur warten")
aus, z, sp = close_lauf("zweit", journal=None)
check(aus == "ohne_wirkung" and z["menue"] == 1, "c8: ohne Journal-Rückruf (alte Aufrufer) → KEIN Zweitversuch")
src = __import__("inspect").getsource(ob.run_close)
check("journal_seit_klick=journal_seit_klick" in src, "c9: run_close reicht den Journal-Rückruf durch")
aus, z, sp = close_lauf("zweit", journal=(False, [], "kein Hedging-Konto"))
check(aus == "ohne_wirkung" and z["menue"] == 1 and "kein Hedging-Konto, KEIN Zweitversuch" in sp, "c10: Netting-/unbekanntes Konto → KEIN Zweitversuch (Prüfer NZ2 R2)")
check('z.get("hedging") is not True' in src and "_mt5_journal_zeilen_tag(dp, 0, 400)" in src and 'if not heute:' in src,
      "c11: Rückruf: nur Hedging, „lesbar“ nur mit der Journal-Datei von heute")
check("ACCOUNT_MARGIN_MODE_RETAIL_HEDGING" in __import__("inspect").getsource(ob._order_api_zustand), "c12: _order_api_zustand liefert hedging aus account_info.margin_mode")
_Knopf.gedrueckt = 0
aus, z, sp = close_lauf(None, dialog_spaet=True)
check(aus in ("knopf", "zu") and _Knopf.gedrueckt >= 1 and z["menue"] == 1 and "Close-Dialog offen" in sp,
      "c13: Close-Dialog des ersten Klicks kommt spät → Knopf-Kaskade statt Zweitversuch (S1)")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER: " + "; ".join(FEHLER))
sys.exit(1 if FEHLER else 0)
