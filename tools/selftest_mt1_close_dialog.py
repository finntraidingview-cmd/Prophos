#!/usr/bin/env python3
"""Selbsttest MT1 Punkt 2, 3 und 5 (11.11.2026, Finn ~06:55: „MetaTrader muss fehlerfrei laufen“; 07:05: am Master nur Klicks, API nur LESEN).
Die ECHTEN Funktionen aus mt5-copier/order_bot.py laufen gegen Attrappen — ohne Windows, ohne MetaTrader, mit Stub-Uhr.
 a) close_dialog_rueckfall_urteil / close_knopf_journal_urteil (rein)
 b) _close_klicken: „Position schließen“ geklickt, weder Dialog noch Schluss → (nach NZ2) EIN Rückfall über den Positionsdialog (Doppelklick auf
    DIESELBE bewiesene Zeile), nur wenn das Journal lesbar ist und seit dem Klick KEINE Anfrage zum Ticket zeigt — auch auf Netting-Konten
    (dort der einzige Zweitversuch). Nur der gelbe Knopf mit dem Ticket wird gedrückt; Ändern-Ansicht → ESC, nichts geklickt.
 c) Schließen-Knopf-Kaskade: zeigt das Journal die Anfrage, kommt KEIN weiterer Weg (der Dialog bleibt als Ergebnis-Seite stehen).
 d) 50 gewürfelte Abläufe: nie zwei Doppelklicks, nie ein Doppelklick ohne Journal-Beweis, nach einer Anfrage im Journal nie ein weiterer Knopf-Weg.
 e) Ergebnis-Codes (aendern_ergebnis_code / close_ergebnis_code) + Einbau in run / run_close / _sltp_nachziehen.
 f) DPI des Terminal-Fensters in der Spur (_fenster_zustand_text), kein order_send im Bot.
Aufruf: python3 tools/selftest_mt1_close_dialog.py"""
import inspect
import os
import random
import re
import sys
import types

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []
T = 627122537


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


class Uhr:
    """Stub für das Modul time in order_bot: jede Abfrage rückt 0,05 s vor — Warteschleifen enden ohne echtes Warten."""
    def __init__(self):
        self.t = 1000.0

    def time(self):
        self.t += 0.05
        return self.t

    def sleep(self, s):
        self.t += s

    def localtime(self, *a):
        import time as _t
        return _t.localtime(*a)


def mit(ersatz, f):
    vorher = {k: getattr(ob, k) for k in ersatz}
    for k, v in ersatz.items():
        setattr(ob, k, v)
    try:
        return f()
    finally:
        for k, v in vorher.items():
            setattr(ob, k, v)


# ── a) reine Urteile ────────────────────────────────────────────────────────────────────────────────────────────────────────────────
U = ob.close_dialog_rueckfall_urteil
check(U(True, [], False)[0] is True, "a1: Journal lesbar, keine Anfrage → Rückfall erlaubt")
check(U(False, [], False)[0] is False and "nicht lesbar" in U(False, [], False)[1], "a2: Journal nicht lesbar → kein Rückfall (kein Beweis)")
check(U(True, ["market sell 1 NAS100, close #627122537"], False)[0] is False, "a3: Journal zeigt eine Anfrage → kein Rückfall")
check(U(True, [], True)[0] is False, "a4: Echo pausiert → kein Rückfall")
K = ob.close_knopf_journal_urteil
check(K(["market sell 3.4 NAS100, close #627122537 buy 3.4 NAS100 27007.10"]) == "gesendet", "a5: Close-Zeile → gesendet")
check(K(["failed market sell 3.4 NAS100, close #627122537 buy 3.4 NAS100 [Off quotes]"]) == "abgelehnt", "a6: failed → abgelehnt")
check(K(["modify #627122537 buy 3.4 NAS100 -> sl: 1, tp: 2"]) is None and K([]) is None and K(None) is None, "a7: Ändern-Zeile / leer → None")
check(K(["LL\t0\t10:00:05.120\tTrades\t'1': market sell 17.99 NAS100"]) == "gesendet" and K(["failed market sell 17.99 NAS100 [Off quotes]"]) == "abgelehnt",
      "a9 (2. Prüfer MUSS): Netting-Zeile ohne „close #“ zählt im Knopf-Weg als gesendet / abgelehnt")
check(K(["failed market sell 1 NAS100, close #1 [Off quotes]", "market sell 1 NAS100, close #1"]) == "gesendet"
      and K(["market sell 1 NAS100, close #1", "failed market sell 1 NAS100, close #1 [x]"]) == "abgelehnt", "a8: die JÜNGSTE Zeile entscheidet")


# ── b/c) _close_klicken mit Attrappen ───────────────────────────────────────────────────────────────────────────────────────────────
class Knopf:
    def __init__(self, z):
        self.z = z

    def window_text(self):
        return f"Schliessen #{T} buy 17.99 NAS100 zum Marktpreis"

    def rectangle(self):
        return Rect(10, 10, 200, 40)

    def set_focus(self):
        pass

    def has_keyboard_focus(self):
        return True

    def click(self):
        self.z["knopf"].append(".click()")
        self.z["nach_knopf"]()

    def click_input(self):
        self.z["knopf"].append("click_input")
        self.z["nach_knopf"]()


class Dlg:
    def is_visible(self):
        return True                       # MT5: die Ergebnis-Seite bleibt stehen (UIA meldet sichtbar)


AENDERN_DLG = object()


def lauf(menue_wirkt=False, hedging=False, nz2_wirkt=False, journal_lesbar=True, journal_vorher=(), doppel_oeffnet="close",
         knopf_wirkt=True, knopf_journal="gesendet", menue_offen_vor_doppel=False, ohne_beweis=False, weg_vor_rueckfall=False,
         fenster_offen=(), dialog_schon_da=False, journal_spaeter_unlesbar=False, journal_bei_doppel=False, fenster_spaet=False):
    """doppel_oeffnet: 'close' (gelber Knopf mit Ticket), 'aendern' (nur Ändern-Ansicht), None (nichts).
    knopf_wirkt: Schließen-Knopf schließt die Position; knopf_journal: was das Journal nach dem Knopf zeigt ('gesendet'/'abgelehnt'/None)."""
    z = {"zu": False, "menue": [], "doppel": [], "knopf": [], "esc_aendern": 0, "journal": list(journal_vorher), "dialog": False,
         "maus": None, "phase": "start"}

    def nach_knopf():
        if knopf_journal == "gesendet":
            z["journal"].append(f"market sell 17.99 NAS100, close #{T} buy 17.99 NAS100")
        elif knopf_journal == "abgelehnt":
            z["journal"].append(f"failed market sell 17.99 NAS100, close #{T} buy 17.99 NAS100 [Off quotes]")
        if knopf_wirkt:
            z["zu_bald"] = True
    z["nach_knopf"] = nach_knopf
    knopf = Knopf(z)

    def _klick_absolut(x, y, taste="links", doppel=False):
        if taste == "rechts":
            z["maus"] = y
        if doppel:
            z["doppel"].append(y)
            if journal_bei_doppel:   # die Anfrage des ERSTEN Klicks zeigt sich erst jetzt (Server-/Journal-Verzug)
                z["journal"].append(f"market sell 17.99 NAS100, close #{T} buy 17.99 NAS100")
            if doppel_oeffnet == "close":
                z["dialog"] = "close"
            elif doppel_oeffnet == "aendern":
                z["dialog"] = "aendern"
        elif z["dialog"] == "close" and taste == "links" and z["phase"] == "knopf":
            z["knopf"].append("SendInput")
            nach_knopf()
        return True

    def _menue(timeout=0.8, klick_zuerst=False):
        if abs(z["maus"] - 684) <= 9:
            z["menue"].append(klick_zuerst)
            if menue_wirkt or (nz2_wirkt and klick_zuerst):
                z["zu"] = True
            return "geklickt"
        return "ausgegraut" if 600 <= z["maus"] <= 1000 else "kein_menue"

    def position_weg():
        if weg_vor_rueckfall and len(z["menue"]) >= (2 if hedging else 1) and not z["doppel"]:
            z["pw_n"] = z.get("pw_n", 0) + 1
            if z["pw_n"] > 3:
                return True
        if z.get("zu_bald"):
            z["zu"] = True
        return z["zu"]

    def _finde_close_dialog(w, ticket):
        if dialog_schon_da and len(z["menue"]) >= (2 if hedging else 1) and not z["doppel"] and z.get("rueckfall_blick"):
            z["dialog"] = "close"
        if z["dialog"] == "close":
            z["phase"] = "knopf"
            return Dlg(), knopf
        return None, None

    def _el_tasten(el, keys, set_foreground=True, **k):
        if keys == "{SPACE}" and el is knopf:
            z["knopf"].append("Leertaste")
            nach_knopf()
        if keys == "{ESC}" and el is AENDERN_DLG:
            z["esc_aendern"] += 1
            z["dialog"] = False

    def journal_seit_klick():
        if not hedging:
            return False, [], "kein Hedging-Konto"
        return (True, [x for x in z["journal"]], "") if journal_lesbar else (False, [], "Journal von heute nicht lesbar")

    def journal_beweis():
        z["rueckfall_blick"] = True
        if journal_spaeter_unlesbar and z["knopf"]:
            return False, [], "Journal von heute nicht lesbar"
        return (True, [x for x in z["journal"]], "") if journal_lesbar else (False, [], "Journal von heute nicht lesbar")

    ersatz = dict(
        time=Uhr(),
        _einklick_haftung_annehmen=lambda w, trail, melden=False: "keiner", _fremde_dialoge_schliessen=lambda w: None,
        _close_reste_raeumen=lambda w, trail: [], _handel_tab_aktivieren=lambda w, trail, mg, anker_pfad=None: "suche",
        is_paused=lambda: False, _anker_lesen=lambda p: {}, _anker_schreiben=lambda p, **k: None, _maus_fahren=lambda x, y, schritte=3: None,
        klick_zoegern=lambda *a, **k: (0, 0), _warte=lambda a, b: None, _klick_absolut=_klick_absolut, _kontextmenue_close_klicken=_menue,
        _kein_menue_offen=lambda pid=None: not (menue_offen_vor_doppel and len(z["menue"]) >= 1), _el_tasten=_el_tasten,
        _finde_close_dialog=_finde_close_dialog, _punkt_frei=lambda w, x, y: True, _prozess_fenster_offen=lambda w: (z.__setitem__("fo_n", z.get("fo_n", 0) + 1) or
                                           (list(fenster_offen) if (not fenster_spaet or z["fo_n"] >= 2) else [])),
        _finde_aendern_dialog=lambda w, timeout=0.3: AENDERN_DLG if z["dialog"] == "aendern" else None,
        _echo_klickziel=lambda r: (20, 20))
    t = Spur()
    aus = mit(ersatz, lambda: ob._close_klicken(Haupt(), T, t, "/tmp/anker-x.json", position_weg, journal_seit_klick=journal_seit_klick,
                                                journal_beweis=None if ohne_beweis else journal_beweis))
    return aus, z, " | ".join(t)


aus, z, sp = lauf(menue_wirkt=True)
check(aus == "zu" and len(z["menue"]) == 1 and not z["doppel"], "b1: Menü wirkt → zu, kein Rückfall (wie bisher)")
aus, z, sp = lauf(hedging=False)
check(aus == "zu" and len(z["menue"]) == 1 and len(z["doppel"]) == 1 and abs(z["doppel"][0] - 684) <= 9 and z["knopf"] == ["Leertaste"]
      and "Positionsdialog-Rückfall: Doppelklick auf die Zeile" in sp,
      "b2: Netting, Menü ohne Wirkung, Journal leer → EIN Doppelklick an DERSELBEN Zeile, gelber Knopf einmal → zu")
aus, z, sp = lauf(hedging=False, journal_vorher=[f"market sell 17.99 NAS100, close #{T}"])
check(aus == "ohne_wirkung" and not z["doppel"] and "Kein Positionsdialog-Rückfall: Journal zeigt eine Anfrage" in sp,
      "b3: Journal zeigt eine Anfrage → kein Rückfall (ein zweiter Close liefe hinter dem ersten her)")
aus, z, sp = lauf(hedging=False, journal_lesbar=False)
check(aus == "ohne_wirkung" and not z["doppel"] and "Kein Positionsdialog-Rückfall: Journal von heute nicht lesbar" in sp,
      "b4: Journal nicht lesbar → kein Rückfall, Grund in der Spur")
aus, z, sp = lauf(hedging=True)
check(aus == "zu" and z["menue"] == [False, True] and len(z["doppel"]) == 1, "b5: Hedging: NZ2-Zweitversuch ohne Wirkung, Journal weiter leer → danach EIN Rückfall")
aus, z, sp = lauf(hedging=True, nz2_wirkt=True)
check(aus == "zu" and z["menue"] == [False, True] and not z["doppel"], "b6: Hedging: NZ2-Zweitversuch wirkt → kein Rückfall")
aus, z, sp = lauf(hedging=False, doppel_oeffnet="aendern")
check(aus == "ohne_wirkung" and len(z["doppel"]) == 1 and z["esc_aendern"] == 1 and not z["knopf"] and "Ändern-Ansicht" in sp,
      "b7: Doppelklick öffnet nur die Ändern-Ansicht → ESC, kein Knopf gedrückt")
aus, z, sp = lauf(hedging=False, doppel_oeffnet=None)
check(aus == "ohne_wirkung" and len(z["doppel"]) == 1 and not z["knopf"] and "kein Dialog" in sp, "b8: Doppelklick öffnet nichts → ohne_wirkung")
aus, z, sp = lauf(hedging=False, ohne_beweis=True)
check(aus == "ohne_wirkung" and not z["doppel"], "b9: ohne journal_beweis (alter Aufrufer) → wie NZ2, kein Rückfall")
aus, z, sp = lauf(hedging=False, menue_offen_vor_doppel=True)
check(aus == "ohne_wirkung" and not z["doppel"] and "Kontextmenü steht offen" in sp, "b10: Menü offen direkt vor dem Doppelklick → kein Klick")
aus, z, sp = lauf(hedging=False, weg_vor_rueckfall=True)
check(aus == "zu" and not z["doppel"], "b11: Position vor dem Rückfall weg → zu, kein Doppelklick")

aus, z, sp = lauf(hedging=False, fenster_offen=["Order: NAS100 - Market Execution"])
check(aus == "ohne_wirkung" and not z["doppel"] and not z["knopf"] and "Fenster des Terminals offen (Order: NAS100" in sp,
      "b12 (Prüfer MUSS): ein Fenster des Terminals steht offen (spät/unerkannt geöffneter Dialog) → KEIN Doppelklick")
aus, z, sp = lauf(hedging=False, dialog_schon_da=True)
check(aus == "zu" and not z["doppel"] and z["knopf"] == ["Leertaste"] and "der Close-Dialog ist schon offen — kein Doppelklick" in sp,
      "b13 (Prüfer MUSS): Close-Dialog des Menü-Klicks kam doch noch → sein Knopf, KEIN Doppelklick")

aus, z, sp = lauf(hedging=False, fenster_offen=["Order: NAS100 - Market Execution"], fenster_spaet=True)
check(aus == "ohne_wirkung" and not z["doppel"] and "Dialog des Terminals ging eben auf" in sp,
      "b14 (2. Prüfer): Dialog geht zwischen Mausfahrt und Klick auf → KEIN Doppelklick")
aus, z, sp = lauf(hedging=False, journal_bei_doppel=True, knopf_wirkt=True)
check(aus == "ohne_wirkung" and len(z["doppel"]) == 1 and not z["knopf"] and "Knopf NICHT gedrückt" in sp,
      "b15 (2. Prüfer): die erste Anfrage zeigt sich erst nach dem Doppelklick → gelber Knopf NICHT gedrückt")
D = ob.rueckfall_fenster_ist_dialog
check(D("#32770", "Irgendwas") and D("", "Order: NAS100 - Market Execution") and not D("AfxFrameOrView140su", "NAS100,M1")
      and not D("MDIClient", "") and not D("", "EURUSD,H1"), "b16 (2. Prüfer MUSS): nur Dialoge zählen als offen, Charts nie (sonst liefe der Rückfall nie)")

# ── c) Schließen-Knopf-Kaskade mit Journal-Beweis ───────────────────────────────────────────────────────────────────────────────────
aus, z, sp = lauf(hedging=False, knopf_wirkt=False, knopf_journal="gesendet")
check(aus == "knopf" and z["knopf"] == ["Leertaste"] and "Close-Anfrage im Journal (Fokus+Leertaste, gesendet) — kein weiterer Weg" in sp,
      "c1: Knopf sendet (Journal), Position noch offen → KEIN weiterer Weg, Ausgang lesend beim Aufrufer")
aus, z, sp = lauf(hedging=False, knopf_wirkt=False, knopf_journal="abgelehnt")
check(aus == "knopf" and z["knopf"] == ["Leertaste"] and "abgelehnt" in sp, "c2: Server lehnt ab → kein weiterer Weg")
aus, z, sp = lauf(hedging=False, knopf_wirkt=False, knopf_journal=None)
check(aus == "knopf" and len(z["knopf"]) == 4, "c3: Journal zeigt nichts → die vier Wege wie bisher")
aus, z, sp = lauf(hedging=False, knopf_wirkt=False, knopf_journal=None, journal_spaeter_unlesbar=True)
check(aus == "knopf" and z["knopf"] == ["Leertaste"] and "nach dem Rückfall nicht lesbar" in sp,
      "c4 (Prüfer SOLLTE): nach dem Rückfall Journal unlesbar → KEIN zweiter Knopf-Druck")

# ── c5) Beweis-Kombination Journal + Order-Zähler (Prüfer MUSS: Netting-Journal unbelegt, Journal schreibt evtl. spät)
B2 = ob.close_rueckfall_beweis
check(B2(True, [], [], 3, 3) == (True, [], ""), "c5a: Journal leer + Order-Zähler gleich → lesbar, nichts gesendet")
l_, z_, g_ = B2(True, [], [], 3, 4)
check(l_ and z_ and ob.close_knopf_journal_urteil(z_) == "gesendet" and not ob.close_dialog_rueckfall_urteil(l_, z_, False)[0],
      "c5b: Journal leer, aber Order-Zähler gestiegen → gilt als gesendet (kein Rückfall, kein weiterer Knopf-Weg)")
check(B2(True, [], [], None, 3)[0] is False and B2(True, [], [], 3, None)[0] is False and B2(False, [], [], 3, 3)[0] is False,
      "c5c: Order-Zähler oder Journal nicht lesbar → kein Beweis")
l_, z_, g_ = B2(True, ["market sell 1 NAS100, close #1"], [], None, (3, 0))
check(l_ is False and z_ == ["market sell 1 NAS100, close #1"] and ob.close_knopf_journal_urteil(z_) == "gesendet",
      "c5h (2. Prüfer SOLLTE): Zähler unlesbar → kein Beweis, aber gesehene Journal-Zeilen bleiben (Knopf-Kaskade stoppt an ihnen)")
check(B2(True, [], [], (3, 1), (4, 0))[1] and B2(True, [], [], (3, 1), (3, 1)) == (True, [], "") and B2(True, [], [], (3, 1), (2, 1)) == (True, [], ""),
      "c5i (2. Prüfer): Historie und offene Orders getrennt — ein Anstieg wird nicht durch einen Wechsel offen → Historie verdeckt")
l_, z_, g_ = B2(True, [], ["market sell 1 NAS100"], 3, 3)
check(z_ == ["market sell 1 NAS100"] and not ob.close_dialog_rueckfall_urteil(l_, z_, False)[0], "c5d: Symbol-Zeile ohne Ticket (Netting) → kein Rückfall")
S = ob.journal_symbol_handel_zeilen
J0 = ["LL\t0\t10:00:05.120\tTrades\t'1234': market sell 1 NAS100", "LL\t0\t10:00:06.000\tTrades\t'1234': market sell 1 EURUSD",
      "LL\t0\t09:00:00.000\tTrades\t'1234': market buy 1 NAS100", "LL\t0\t10:00:07.000\tNetwork\t'1234': NAS100 ping"]
check(S(J0, "NAS100", 10 * 3600 + 4) == ["market sell 1 NAS100"], "c5e: Symbol-Handelszeilen seit dem Klick (fremdes Symbol, ältere Zeile, Nicht-Handel zählen nicht)")
rc0 = inspect.getsource(ob.run_close)
check("_orders_vorher = _orders_zaehlen(path, expected, ticket, pos[\"symbol\"])" in rc0 and "close_rueckfall_beweis(True, tz, sz, _orders_vorher" in rc0
      and rc0.index("_orders_vorher = _orders_zaehlen(") < rc0.index("ausgang = _close_klicken("), "c5f: run_close zählt die Orders VOR dem Klick und prüft beide Lesungen")
oz = inspect.getsource(ob._orders_zaehlen)
check("history_orders_get(position=" in oz and "order_send" not in oz and "if h is None or o is None:" in oz,
      "c5g: Order-Zähler nur lesend; EINE Abfrage ohne Antwort = nicht lesbar (2. Prüfer MUSS)")
# _orders_zaehlen wirklich ausführen: Attrappe für MetaTrader5
_mt = types.ModuleType("MetaTrader5")
_mt.account_info = lambda: types.SimpleNamespace(login=1)
_mt.initialize = lambda **k: True
lage = {"h": (1, 2), "o": ()}
_mt.history_orders_get = lambda position=None: lage["h"]
_mt.orders_get = lambda symbol=None: lage["o"]
sys.modules["MetaTrader5"] = _mt
_alt_pfad = ob._MT5_PFAD
ob._MT5_PFAD = "p"
check(ob._orders_zaehlen("p", 1, T, "NAS100") == (2, 0), "c5j: Zähler = (Historie zur Position, offene zum Symbol)")
lage["h"] = None
check(ob._orders_zaehlen("p", 1, T, "NAS100") is None, "c5k: history_orders_get ohne Antwort → None (kein „0“)")
lage.update(h=(1,), o=None)
check(ob._orders_zaehlen("p", 1, T, "NAS100") is None, "c5l: orders_get ohne Antwort → None")
_mt.account_info = lambda: types.SimpleNamespace(login=2)
lage.update(h=(1,), o=())
check(ob._orders_zaehlen("p", 1, T, "NAS100") is None, "c5m: falsches Konto → None")
ob._MT5_PFAD = _alt_pfad
del sys.modules["MetaTrader5"]

# ── d) 50 gewürfelte Abläufe ────────────────────────────────────────────────────────────────────────────────────────────────────────
rnd = random.Random(1111)
verstoss = []
for i in range(50):
    o = dict(menue_wirkt=rnd.random() < 0.2, hedging=rnd.random() < 0.5, nz2_wirkt=rnd.random() < 0.3, journal_lesbar=rnd.random() < 0.8,
             journal_vorher=[f"market sell 1 NAS100, close #{T}"] if rnd.random() < 0.25 else [],
             doppel_oeffnet=rnd.choice(["close", "close", "aendern", None]), knopf_wirkt=rnd.random() < 0.6,
             knopf_journal=rnd.choice(["gesendet", "abgelehnt", None]), menue_offen_vor_doppel=rnd.random() < 0.1)
    aus, z, sp = lauf(**o)
    if len(z["doppel"]) > 1:
        verstoss.append((i, "zwei Doppelklicks"))
    if z["doppel"] and (not o["journal_lesbar"] or o["journal_vorher"]):
        verstoss.append((i, "Doppelklick ohne Journal-Beweis"))
    if z["doppel"] and (o["menue_wirkt"] or (o["hedging"] and o["nz2_wirkt"] and o["journal_lesbar"] and not o["journal_vorher"])):
        verstoss.append((i, "Doppelklick, obwohl ein Menü-Klick gewirkt hatte"))
    if o["knopf_journal"] and len(z["knopf"]) > 1:
        verstoss.append((i, "weiterer Knopf-Weg nach Anfrage im Journal"))
    if len(z["menue"]) > 2:
        verstoss.append((i, "mehr als zwei Menü-Klicks"))
check(not verstoss, f"d: 50 gewürfelte Abläufe ohne Verstoß ({verstoss[:3]})")

# ── e) Ergebnis-Codes ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
A = ob.aendern_ergebnis_code
check(A({"ok": True, "beleg": "api_ok"}, True) == "api" and A({"ok": False, "gesendet": True}, True) == "journal"
      and A({"ok": True, "msg": "geklickt"}, True) == "dialog_ok" and A({"ok": False, "msg": "Aendern-Knopf reagiert auf keinen Weg"}, True) == "api_spaet",
      "e1: Ändern bestätigt → api | journal | dialog_ok | api_spaet (Klick selbst nicht belegt)")
check(A({"ok": False, "msg": "abgelehnt [Invalid stops]"}, False) == "offen: abgelehnt [Invalid stops]" and A(None, False) == "offen: Echo pausiert"
      and A({"msg": "x"}, False, "Position schon zu") == "offen: Position schon zu", "e2: Ändern nicht bestätigt → offen: <Grund>")
C = ob.close_ergebnis_code
check(C("zu", True) == "api" and C("knopf", True) == "api" and C("ohne_wirkung", False).startswith("offen: Menüpunkt geklickt")
      and C("kein_treffer", False) == "offen: Positions-Zeile nicht gefunden" and C("neu", False) == "offen: neu", "e3: Close → api | offen: <Grund>")
rc = inspect.getsource(ob.run_close)
check(rc.count('"ergebnis_code"') == 7 and "Ergebnis Schließen: {_code}" in rc and "journal_beweis=journal_beweis" in rc
      and "return _journal_lesen(True)" in rc and "lesbar, tz, grund = _journal_lesen(False)" in rc,
      "e4: run_close: Code in jeder Antwort nach dem Klick, Journal-Rückrufe (NZ2 nur Hedging, MT1 jede Kontoart)")
nz = inspect.getsource(ob._sltp_nachziehen)
check(nz.count("aendern_ergebnis_code(") == 2 and nz.count("Ergebnis Ändern:") == 2, "e5: _sltp_nachziehen: Code bei Erfolg und Fehlschlag")
check(inspect.getsource(ob.run).count('"ergebnis_code": _code') == 2, "e6: run (Erst-Setzen): Code bei Erfolg und Fehlschlag")

# ── f) DPI + nur lesen ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
fz = inspect.getsource(ob._fenster_zustand_text)
check("GetDpiForWindow(h)" in fz and 'f"DPI {dpi} ({round(dpi * 100 / 96)} %)"' in fz and "GetDpiForWindow" in inspect.getsource(ob._u32_aendern),
      "f1: DPI des Terminal-Fensters in der Spur (Ändern-Start + Abbruch)")


class _U32:
    def __init__(self, dpi):
        self.dpi = dpi

    def IsIconic(self, h):
        return False

    def IsZoomed(self, h):
        return True

    def GetSystemMetrics(self, i):
        return 3840 if i == 0 else 2160

    def GetDpiForWindow(self, h):
        if self.dpi is None:
            raise AttributeError("fehlt")
        return self.dpi

    def GetForegroundWindow(self):
        return 5


class _W:
    handle = 5

    def rectangle(self):
        return Rect(0, 0, 3840, 2100)


for dpi, erwartet in ((144, "DPI 144 (150 %)"), (96, "DPI 96 (100 %)"), (None, None)):
    txt = mit(dict(_u32_aendern=lambda d=dpi: _U32(d), _hwnd_pid=lambda h: 1, _terminal_pid=lambda w: 1), lambda: ob._fenster_zustand_text(_W()))
    check((erwartet in txt) if erwartet else ("DPI" not in txt and "Terminal vorn" in txt), f"f2: DPI {dpi} → {erwartet or 'nichts, Rest der Spur bleibt'}")
check(re.search(r"^\s*[^#\n]*mt5\.order_send\(", open(ob.__file__, encoding="utf-8").read(), re.M) is None, "f3: order_bot.py ruft nirgends mt5.order_send auf")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER: " + "; ".join(FEHLER))
sys.exit(1 if FEHLER else 0)
