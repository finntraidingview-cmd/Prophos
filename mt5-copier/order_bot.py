#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Order-Bot — platziert die MASTER-Order per SICHTBARER Maus-/Tastatur-Steuerung
(15.08.2026, Finns Ansage: die Order muss serverseitig wie ein Handklick
aussehen — eine API-Order traegt die Expert-Markierung, ein echter Klick nicht).

Choreografie (sichtbar, wie mit Finn geuebt):
  1. Maus faehrt in die Taskleiste und klickt den Terminal-Tab
  2. Fenster-Guard: Titelzeile MUSS die Kontonummer tragen, sonst Abbruch
  3. F9 -> Order-Dialog, Symbol waehlen, Volumen ECHT eintippen (Tastatur-
     Events, kein set_text — s. _feld_tippen) und zuruecklesen
  4. Maus faehrt auf den Buy/Sell-Knopf und klickt — der einzige unumkehrbare Schritt
  5. Bestaetigung NICHT der UI glauben: Positionsliste des Kontos (nur LESEND
     ueber die MetaTrader5-API — Lesen traegt keine Order-Markierung)
  6. SL/TP vom ECHTEN Einstiegskurs rechnen und PER KLICK im Aendern-Dialog
     der Position eintragen (18.08.2026, Finns Ansage: auch die SL/TP-Aenderung
     muss wie Handarbeit aussehen — der fruehere TRADE_ACTION_SLTP-Weg lief
     ueber denselben API-Kanal wie ein EA, unnoetiges Restrisiko). Bestaetigt
     wird auch das nur LESEND am Positionsstand.

Die API wird ausschliesslich LESEND benutzt: aktueller Kurs fuer die
$->Preis-Umrechnung, Positionsstand vorher/nachher, SL/TP-Kontrolle.
mt5.order_send existiert in dieser Datei bewusst NICHT.

Aufruf (vom Panel als kurzlebiger Subprozess):
  python order_bot.py <config-datei.json> "<befehl-json>"
  python order_bot.py inspect <config-datei.json>     (Dialog-Dump, platziert nichts)
Befehl:  {"symbol": "NDX100", "richtung": "buy", "volumen": 0.2,
          "sl_usd": 100, "tp_usd": 300}
Antwort: EINE JSON-Zeile auf stdout.

retry_ok-Regel: True nur, solange sicher NICHTS gesendet wurde (jeder Abbruch
VOR dem Buy/Sell-Klick). Nach dem Klick ist jede Unsicherheit retry_ok=False —
'erst im Terminal nachsehen, nie blind wiederholen'.
"""

import json
import math
import os
import random
import re
import sys
import time


# ---------------------------------------------------------------------------
# REIN RECHNENDE Funktionen — ohne Windows/MetaTrader testbar (selftest.py)
# ---------------------------------------------------------------------------

def pruefe_befehl(cmd):
    """Liste von Fehlertexten; leer = Befehl ok."""
    fehler = []
    if not isinstance(cmd, dict):
        return ["Befehl ist kein JSON-Objekt."]
    if not str(cmd.get("symbol") or "").strip():
        fehler.append("symbol fehlt")
    if str(cmd.get("richtung") or "").lower() not in ("buy", "sell"):
        fehler.append("richtung muss buy oder sell sein")
    try:
        v = float(cmd.get("volumen") or 0)
        # isfinite deckt NaN und Infinity ab ('nan <= 0' waere still False)
        if not math.isfinite(v) or v <= 0:
            fehler.append("volumen fehlt oder <= 0")
    except (TypeError, ValueError):
        fehler.append("volumen ist keine Zahl")
    # SL/TP sind OPTIONAL (18.08.2026, Schalter im Order-Popup): beide gesetzt
    # -> Bot traegt sie nach dem Fill per Klick ein; beide leer -> Order pur,
    # SL/TP macht Finn von Hand. NUR EINES gesetzt ist ein Fehler.
    gesetzt = {}
    for k in ("sl_usd", "tp_usd"):
        roh = cmd.get(k)
        if roh in (None, "", 0, "0"):
            gesetzt[k] = False
            continue
        gesetzt[k] = True
        try:
            v = float(roh)
            if not math.isfinite(v) or v <= 0:
                fehler.append(f"{k} <= 0 oder keine Zahl")
        except (TypeError, ValueError):
            fehler.append(f"{k} ist keine Zahl")
    if gesetzt.get("sl_usd") != gesetzt.get("tp_usd"):
        fehler.append("sl_usd und tp_usd nur ZUSAMMEN setzen (oder beide weglassen)")
    return fehler


def fmt_preis(x, digits):
    """Preis mit PUNKT als Dezimaltrenner — MT5-Eingabefelder erwarten den Punkt
    unabhaengig von der Windows-Sprache."""
    return f"{float(x):.{int(digits)}f}"


def berechne_sl_tp(richtung, ref_preis, volumen, contract_size, sl_usd, tp_usd, digits=2):
    """$-Betraege -> absolute Preise. 1.0 Preis-Einheit ist volumen*contract_size
    wert (Index-CFD in USD) — dieselbe Basis wie die Exposure-Formel im Copier."""
    ref = float(ref_preis)
    je_einheit = float(volumen) * float(contract_size)
    if je_einheit <= 0:
        raise ValueError("volumen*contract_size muss > 0 sein")
    kauf = str(richtung).lower() == "buy"
    d_sl = float(sl_usd) / je_einheit
    d_tp = float(tp_usd) / je_einheit
    sl = round(ref - d_sl if kauf else ref + d_sl, int(digits))
    tp = round(ref + d_tp if kauf else ref - d_tp, int(digits))
    return sl, tp


def finde_neue_position(vorher_tickets, positionen, symbol, richtung, volumen, tol=0.005):
    """Die frisch platzierte Position wiederfinden: neues Ticket, richtiges
    Symbol, richtige Richtung, Volumen im Toleranzfenster (Lot-Raster)."""
    will_typ = 0 if str(richtung).lower() == "buy" else 1
    for p in positionen:
        if p["ticket"] in vorher_tickets:
            continue
        if p["symbol"] != symbol or p["typ"] != will_typ:
            continue
        if abs(p["volumen"] - float(volumen)) <= tol:
            return p
    return None


def ist_aendern_knopf(text):
    """Erkennt den Aendern-Knopf des Positions-Dialogs an der Beschriftung —
    und schliesst alles aus, was loeschen/schliessen/abbrechen koennte. Reine
    Textlogik, damit der Mac-Selbsttest sie abdeckt."""
    t = (text or "").strip().lower()
    if not t:
        return False
    for verboten in ("abbre", "cancel", "schlie", "close", "delet", "loesch", "lösch"):
        if verboten in t:
            return False
    return any(k in t for k in ("ändern", "aendern", "modify", "change"))


def ist_bestaetigen_knopf(text):
    """Der LANGE Bestaetigen-Knopf des Aendern-Dialogs — NICHT der 'Position
    aendern'-Reiter links (Fund 18.08.2026: ist_aendern_knopf traf im UI-Baum
    zuerst den Reiter, der Bot drueckte bei jedem Lauf brav den Reiter statt
    zu bestaetigen — Dialog blieb wirkungslos offen und wurde verworfen).
    Der Bestaetigen-Knopf traegt die Order-Daten in der Beschriftung:
    '#<Ticket> buy 1 NAS100 ... sl: ... tp: ... aendern'."""
    t = (text or "").strip().lower()
    if not ist_aendern_knopf(t):
        return False
    if t in ("position ändern", "position aendern", "modify position"):
        return False
    return ("#" in t or "sl:" in t or "tp:" in t
            or bool(re.search(r"(?<!\d)\d{7,}(?!\d)", t)))


def sltp_bestaetigt(pos_sl, pos_tp, sl, tp, digits):
    """Traegt die Position die gewuenschten SL/TP? Toleranz: 1.5 Einheiten der
    letzten Kursstelle (Server normalisieren minimal). 0.0 heisst 'nicht
    gesetzt' und faellt damit automatisch durch."""
    tol = 1.5 * (10 ** -int(digits))
    return (abs(float(pos_sl) - float(sl)) <= tol
            and abs(float(pos_tp) - float(tp)) <= tol)


def zahl_gleich(text, wert, tol=1e-9):
    """Zeigt der ZURUECKGELESENE Feldtext wirklich den getippten Wert? Vergleich
    als Zahl, nicht als String — MT5 formatiert um ('2' -> '2.00') und kann je
    nach Windows-Locale Komma/Leerzeichen einstreuen."""
    try:
        a = float(str(text).strip().replace(" ", "").replace(",", "."))
        b = float(str(wert).strip().replace(",", "."))
    except (TypeError, ValueError):
        return False
    return abs(a - b) <= tol * max(1.0, abs(b)) + 1e-12


def zeile_nennt_ticket(text, ticket):
    """Steht die Ticket-Nummer als eigenstaendige Zahl im Element-Text? So wird
    die Zeile der Position in der Handel-Liste erkannt, ohne dass 9123456789
    faelschlich auf 123456789 passt."""
    return bool(re.search(r"(?<!\d)" + re.escape(str(int(ticket))) + r"(?!\d)",
                          text or ""))


def ist_handelszeile(text, symbol):
    """Sieht der UIA-Text wie eine Zeile der HANDEL-Liste aus? Symbol UND
    buy/sell muessen drinstehen. Fund 18.08.2026: der .54-Filter (Symbol plus
    Mindestlaenge) traf auch den Chart-Titel ('NAS100,M1: US Tech 100 Index')
    und den Navigator-Eintrag ('ProphosHedgeReader - NAS100,M1') — der
    Doppelklick darauf oeffnete den EA-Eigenschaften-Dialog. Beide tragen
    nie buy/sell."""
    t = (text or "").lower()
    return bool(symbol) and symbol.lower() in t and ("buy" in t or "sell" in t)


# ---------------------------------------------------------------------------
# LESENDER API-Teil — Kurse + Positionsstand (traegt keine Order-Markierung)
# ---------------------------------------------------------------------------

def _api_lesen(path, expected, symbol=None):
    """Einmal andocken, lesen, sofort trennen. Rueckgabe:
    {"login", "positionen": [...], "ref_ask", "ref_bid", "contract_size",
     "digits"} oder {"fehler": ...}."""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return {"fehler": "MetaTrader5-Paket fehlt (nur auf dem PC lauffaehig)."}
    if not mt5.initialize(path=path):
        return {"fehler": f"Terminal-Verbindung fehlgeschlagen: {mt5.last_error()}"}
    try:
        ai = mt5.account_info()
        if ai is None:
            return {"fehler": "Kein Konto verbunden (account_info leer)."}
        if expected and int(ai.login) != expected:
            return {"fehler": f"Terminal ist im FALSCHEN Konto ({ai.login} statt {expected})."}
        out = {"login": int(ai.login), "positionen": []}
        for p in (mt5.positions_get() or []):
            out["positionen"].append({"ticket": int(p.ticket), "symbol": str(p.symbol),
                                      "typ": int(p.type), "volumen": float(p.volume),
                                      "sl": float(p.sl), "tp": float(p.tp),
                                      "preis": float(p.price_open)})
        if symbol:
            # Symbol in die Marktuebersicht holen (15.08.2026, Finns Fund: nach
            # frischem Login ist NASDAQ nie da). symbol_select(..., True) ist eine
            # reine Watchlist-Aktion — KEINE Order, also keine Expert-Markierung.
            # Damit taucht das Symbol danach auch im F9-Dialog-Dropdown auf.
            if mt5.symbol_info(symbol) is None:
                # Broker kennt diese Schreibweise gar nicht — Mapping pruefen.
                return {"fehler": f"Broker kennt Symbol '{symbol}' nicht — Schreibweise im "
                                  f"Symbol-Mapping der Copier-Karte pruefen (z.B. NAS100 vs NDX100)."}
            if not mt5.symbol_select(symbol, True):
                return {"fehler": f"Symbol '{symbol}' liess sich nicht zur Marktuebersicht "
                                  f"hinzufuegen."}
            si = mt5.symbol_info(symbol)
            tick = mt5.symbol_info_tick(symbol)
            # Nach frischem Hinzufuegen kann der erste Tick kurz fehlen — bis 3s
            # nachfassen, bevor 'Markt zu' gemeldet wird.
            _t0 = time.time()
            while (tick is None or not (tick.ask and tick.bid)) and time.time() - _t0 < 3:
                _warte(0.3, 0.3)
                tick = mt5.symbol_info_tick(symbol)
            if si is None or tick is None or not (tick.ask and tick.bid):
                return {"fehler": f"Keine Kurse fuer '{symbol}' (Markt zu?)."}
            out["ref_ask"] = float(tick.ask)
            out["ref_bid"] = float(tick.bid)
            out["contract_size"] = float(getattr(si, "trade_contract_size", 0) or 0) or 1.0
            out["digits"] = int(getattr(si, "digits", 2) or 2)
        return out
    finally:
        mt5.shutdown()


# _sltp_setzen (TRADE_ACTION_SLTP) ist am 18.08.2026 bewusst GELOESCHT worden:
# die Aenderung lief ueber denselben API-Kanal wie ein EA — Finns Ansage: auch
# SL/TP wird per Klick eingetragen, die API bleibt komplett lesend.


# ---------------------------------------------------------------------------
# SICHTBARER Klick-Teil (pywinauto) — nur bei run/inspect importiert
# ---------------------------------------------------------------------------

MT5_KLASSE = "MetaQuotes::MetaTrader::5.00"

# Echo-Pause (28.08.2026, Finns Not-Aus): dieselbe Flag-Datei wie der Copier
# (echo_pause.flag im Bot-Ordner, gelegt vom Panel /api/pause). Ist sie da,
# steigt der Bot aus seiner SL/TP-Klick-Schleife aus, statt weiter am Terminal
# herumzuklicken — genau der Fall, den Finn nicht mehr per Task-Manager killen
# will. Die Order selbst ist da laengst platziert; abgebrochen werden nur die
# NEUEN Klick-Versuche.
_PAUSE_FLAG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "echo_pause.flag")


def is_paused():
    return os.path.exists(_PAUSE_FLAG)


def _warte(minimum, streuung):
    """Wartezeit mit Zufalls-Streuung: minimum + 0..streuung Sekunden.

    28.08.2026, Finns Sorge: platziert die Flotte gleichzeitig, tickte bisher
    JEDER Schritt — F9, Symbol, Volumen, Buy-Klick, SL/TP-Eintrag — auf allen
    Instanzen im exakt gleichen Sekunden-Raster (fixe sleeps). Die Streuung
    zieht die Ablaeufe pro Lauf und pro Instanz auseinander; jeder Aufruf
    wuerfelt neu, dadurch unterscheiden sich auch die Abstaende ZWISCHEN den
    Schritten eines einzelnen Laufs.

    Das Minimum bleibt unangetastet — es ist die Zeit, die die MT5-UI wirklich
    braucht (Tempo-Kalibrierung aus .73 gilt weiter), gewuerfelt wird nur
    OBENDRAUF. Bewusst OHNE Streuung bleiben die 12-ms-Animationsschritte in
    _maus_fahren (fluessige Bewegung) und die Diagnose-Modi mousetest/inspect."""
    time.sleep(minimum + random.uniform(0.0, streuung))


def _klick_absolut(x, y, taste="links", doppel=False):
    """Echter Maus-Klick als EIN atomarer SendInput-Batch mit ABSOLUT-
    Koordinaten (18.08.2026): Bewegen+Druecken+Loslassen in einem Aufruf.
    pywinautos click_input bewegt erst und klickt dann getrennt — genau in
    diese Luecke funkt Parsec mit der lokalen Mausposition (Fund 16.08.).
    Ein Batch laesst dem keinen Raum, und fuer MT5 ist das Ergebnis von
    einem Hand-Klick nicht unterscheidbar. taste='rechts' fuer Kontextmenues,
    doppel=True haengt Druecken+Loslassen als Doppelklick an."""
    import ctypes
    user32 = ctypes.windll.user32
    W, H = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    ax = int(round(int(x) * 65535 / max(1, W - 1)))
    ay = int(round(int(y) * 65535 / max(1, H - 1)))
    PUL = ctypes.POINTER(ctypes.c_ulong)

    class _MI(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                    ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong), ("dwExtraInfo", PUL)]

    class _INP(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("mi", _MI)]

    MOVE, ABS = 0x0001, 0x8000
    DOWN, UP = (0x0002, 0x0004) if taste == "links" else (0x0008, 0x0010)
    folge = [MOVE | ABS, MOVE | DOWN | ABS, MOVE | UP | ABS]
    if doppel:
        folge += [MOVE | DOWN | ABS, MOVE | UP | ABS]
    batch = (_INP * len(folge))()
    for i, fl in enumerate(folge):
        batch[i].type = 0  # INPUT_MOUSE
        batch[i].mi = _MI(ax, ay, 0, fl, 0, None)
    return user32.SendInput(len(folge), batch, ctypes.sizeof(_INP)) == len(folge)


def _cursor_pos():
    import ctypes
    import ctypes.wintypes as wt
    pt = wt.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def _cursor_set(x, y):
    """Cursor per tiefster Windows-API setzen (15.08.2026): SetCursorPos greift
    auch ueber Parsec zuverlaessig auf den ECHTEN Windows-Cursor — der
    pywinauto-Weg zeigte ueber Remote-Sitzungen manchmal nur den lokalen
    Parsec-Cursor, waehrend sich der echte lautlos woanders bewegte."""
    import ctypes
    ctypes.windll.user32.SetCursorPos(int(x), int(y))


def _maus_fahren(x, y, schritte=18):
    """Den ECHTEN Mauszeiger sichtbar hinfahren (nicht teleportieren) — Finns
    Ansage: man soll sehen, wie der Bot die Kontrolle uebernimmt. SetCursorPos
    statt pywinauto.mouse (Parsec-Doppelcursor, s.o.)."""
    try:
        cx, cy = _cursor_pos()
    except Exception:
        cx, cy = x, y
    for i in range(1, schritte + 1):
        try:
            _cursor_set(int(cx + (x - cx) * i / schritte),
                        int(cy + (y - cy) * i / schritte))
        except Exception:
            break
        time.sleep(0.012)


def _bildschirm_groesse():
    import ctypes
    return (ctypes.windll.user32.GetSystemMetrics(0),
            ctypes.windll.user32.GetSystemMetrics(1))


def _bildschirm_mitte():
    w, h = _bildschirm_groesse()
    return (w // 2, h // 2)


def modus_mousetest():
    """Isolierter Selbsttest (15.08.2026, Finns Wunsch): bewegt den Cursor
    sichtbar ueber den Bildschirm und tippt in Notepad — beantwortet die
    Grundfrage, ob Maus/Tastatur auf diesem PC ueberhaupt steuerbar sind,
    getrennt von MT5. Liest nach JEDEM Schritt die echte Cursor-Position:
    stimmt sie mit dem Ziel, bewegt sich der OS-Cursor wirklich (auch wenn
    AnyDesk/Parsec nur den lokalen Zeiger anzeigt)."""
    res = {"ok": False, "moves": [], "notepad": None}
    time.sleep(2.0)  # Haende weg
    try:
        W, H = _bildschirm_groesse()
    except Exception as e:
        print(json.dumps({"ok": False, "msg": f"Bildschirmgroesse nicht lesbar: {e}"}))
        return
    ziele = [(W // 2, H // 2), (60, 60), (W - 60, 60),
             (W - 60, H - 60), (60, H - 60), (W // 2, H // 2)]
    for tx, ty in ziele:
        _maus_fahren(tx, ty)
        time.sleep(0.6)
        try:
            ax, ay = _cursor_pos()
        except Exception:
            ax, ay = -1, -1
        res["moves"].append({"ziel": [tx, ty], "ist": [ax, ay],
                             "ok": abs(ax - tx) < 8 and abs(ay - ty) < 8})
    res["cursor_bewegt"] = bool(res["moves"]) and all(m["ok"] for m in res["moves"])
    # Notepad: Maus hin, Fokus, Zahlen tippen
    try:
        import subprocess
        from pywinauto import Desktop
        subprocess.Popen(["notepad.exe"])
        time.sleep(1.8)
        np = None
        for w in Desktop(backend="uia").windows():
            try:
                if "notepad" in (w.window_text() or "").lower() \
                        or w.element_info.class_name == "Notepad":
                    np = w
                    break
            except Exception:
                continue
        if np:
            np.set_focus()
            time.sleep(0.4)
            try:
                r = np.rectangle()
                _maus_fahren(r.mid_point().x, r.mid_point().y)
            except Exception:
                pass
            np.type_keys("123456 Prophos Maus-Test OK", with_spaces=True, set_foreground=True)
            res["notepad"] = "getippt: '123456 Prophos Maus-Test OK' — im Notepad sichtbar?"
        else:
            res["notepad"] = "Notepad-Fenster nicht gefunden"
    except Exception as e:
        res["notepad"] = f"Notepad-Test fehlgeschlagen: {type(e).__name__}: {e}"
    treffer = sum(1 for m in res["moves"] if m["ok"])
    res["ok"] = res["cursor_bewegt"]
    res["msg"] = (f"Cursor-Bewegung: {treffer}/{len(res['moves'])} Ziele getroffen "
                  f"({'OS-Cursor bewegt sich' if res['cursor_bewegt'] else 'OS-Cursor bewegt sich NICHT'}). "
                  f"Notepad: {res['notepad']}")
    print(json.dumps(res))


def _maus_zentrieren():
    """Anker-Punkt (Finns Wunsch 15.08.2026): der Bot faehrt die Maus SELBST
    sichtbar in die Bildschirmmitte und haelt kurz — fester Ausgangspunkt, den
    Finn nicht mehr treffen muss. Rueckgabe: (bewegt?, (x, y)) — bewegt=False
    heisst, der OS-Cursor liess sich nicht setzen (dann meldet run das klar)."""
    try:
        vor = _cursor_pos()
    except Exception:
        vor = None
    mx, my = _bildschirm_mitte()
    _maus_fahren(mx, my)
    time.sleep(1.0)  # sichtbar halten
    try:
        nach = _cursor_pos()
        bewegt = (vor is None) or (abs(nach[0] - mx) < 6 and abs(nach[1] - my) < 6)
        return bewegt, nach
    except Exception:
        return True, (mx, my)


def _fenster_betreten(w):
    """Schritt 1 der Choreografie: sichtbar INS Terminal gehen (15.08.2026,
    Finns Fix: NICHT ueber die Taskleiste — deren Tabs wandern je nach Sitzung.
    Das Terminal ist beim Trade-Start ohnehin schon geoeffnet und nach vorn
    geholt): Fenster wiederherstellen, Maus sichtbar auf die Titelzeile fahren
    und hineinklicken. Das Ziel kommt aus dem Fenster-Rechteck selbst —
    aufloesungs- und tab-unabhaengig, keine festen Pixel."""
    try:
        if w.is_minimized():
            w.restore()
            _warte(0.2, 0.25)
    except Exception:
        pass
    w.set_focus()
    _warte(0.25, 0.3)
    try:
        from pywinauto import mouse
        r = w.rectangle()
        # linkes Drittel der Titelzeile — weit weg von Minimieren/Schliessen
        x = int(r.left + (r.right - r.left) * 0.35)
        y = int(r.top + 14)
        _maus_fahren(x, y)
        mouse.click(coords=(x, y))
        _warte(0.15, 0.2)
    except Exception:
        pass  # Fokus steht schon — der Klick ist der sichtbare Uebernahme-Moment


def _finde_terminal(login):
    from pywinauto import Desktop
    for w in Desktop(backend="uia").windows():
        try:
            if w.element_info.class_name == MT5_KLASSE and str(login) in (w.window_text() or ""):
                return w
        except Exception:
            continue
    return None


def _ist_order_dialog(win):
    """Ein Fenster als Order-Dialog erkennen: Titel beginnt mit 'Order' ODER es
    traegt eine ComboBox + mind. 3 Edit-Felder (die Symbol/Volumen/SL/TP-Maske)."""
    try:
        t = (win.window_text() or "")
        if t.strip().lower().startswith("order"):
            return True
        combos = win.descendants(control_type="ComboBox")
        edits = win.descendants(control_type="Edit")
        return bool(combos) and len(edits) >= 3
    except Exception:
        return False


def _map_felder(dlg):
    """Edit-Felder nach ihrer BESCHRIFTUNG zuordnen statt nach Position (Fund
    15.08.2026: der Positions-Index passte nicht — Preis landete im Volumen-Feld,
    TP blieb leer). Sucht zu den Labels 'Volumen'/'Stop Loss'/'Take Profit' das
    naechste Edit-Feld rechts daneben in derselben Zeile. Rueckgabe-Dict; fehlt
    ein Schluessel, faellt run() fuer den auf den Index zurueck."""
    def _mitte_y(r):
        return (r.top + r.bottom) / 2
    labels = {}
    try:
        for t in dlg.descendants(control_type="Text"):
            txt = (t.window_text() or "").strip().lower().rstrip(":").replace(" ", "")
            r = t.rectangle()
            if txt in ("volumen", "volume"):
                labels["volumen"] = r
            elif txt in ("stoploss", "s/l", "sl"):
                labels["sl"] = r
            elif txt in ("takeprofit", "t/p", "tp"):
                labels["tp"] = r
    except Exception:
        pass
    edits = []
    try:
        for e in dlg.descendants(control_type="Edit"):
            try:
                edits.append((e, e.rectangle()))
            except Exception:
                continue
    except Exception:
        pass
    out = {}
    for key, lr in labels.items():
        best, bestd = None, 1e9
        for e, er in edits:
            if er.left >= lr.left - 4 and abs(_mitte_y(er) - _mitte_y(lr)) < 22:
                d = er.left - lr.left
                if d < bestd:
                    bestd, best = d, e
        if best is not None:
            out[key] = best
    return out


def _dialog_struktur(dlg):
    """Kurzer Struktur-Dump fuer die Diagnose: Labels + Edit-Werte."""
    teile = []
    try:
        for c in dlg.descendants():
            try:
                ct = c.element_info.control_type
                if ct in ("Edit", "Text", "ComboBox", "Button"):
                    teile.append(f"{ct}:{(c.window_text() or '')[:16]}")
            except Exception:
                continue
    except Exception:
        pass
    return " | ".join(teile[:40])


def _finde_order_dialog(hauptfenster, timeout=10.0):
    """Nach F9: den Order-Dialog suchen — als TOP-LEVEL-Fenster UND als
    Kind-Fenster des Terminals (Fund 15.08.2026: MT5 haengt den F9-Dialog als
    Child ans Hauptfenster, die reine Top-Level-Suche fand ihn nie, obwohl er
    sichtbar offen war). Titel 'Order…' oder die typische Feldstruktur."""
    from pywinauto import Desktop
    pid = hauptfenster.element_info.process_id
    ende = time.time() + timeout
    while time.time() < ende:
        # a) Top-Level-Fenster desselben Prozesses
        try:
            for w in Desktop(backend="uia").windows():
                try:
                    if w.element_info.process_id == pid and w.is_visible() \
                            and w.element_info.class_name != MT5_KLASSE \
                            and _ist_order_dialog(w):
                        return w
                except Exception:
                    continue
        except Exception:
            pass
        # b) Kind-/Nachkommen-Fenster des Hauptfensters
        try:
            for d in hauptfenster.descendants(control_type="Window"):
                if _ist_order_dialog(d):
                    return d
        except Exception:
            pass
        # c) Direkter Griff per Titel-Regex (owned window)
        try:
            cand = hauptfenster.child_window(title_re="(?i)^order")
            if cand.exists(timeout=0.3):
                return cand.wrapper_object()
        except Exception:
            pass
        _warte(0.3, 0.3)
    return None


def _feld_lesen(el):
    """Den INHALT eines Felds lesen — window_text() liefert bei UIA oft nur den
    NAMEN des Felds, also die Beschriftung 'Volumen:' (Fund 18.08.2026 im
    Trade-Start-Check: das Ruecklesen verglich gegen das Label und brach ab,
    obwohl das Tippen laengst funktionierte). Deshalb: ValuePattern zuerst,
    dann Legacy-Value, window_text() nur als letzter Rest."""
    try:
        v = el.get_value()
        if v is not None:
            return str(v)
    except Exception:
        pass
    try:
        v = el.iface_value.CurrentValue
        if v is not None:
            return str(v)
    except Exception:
        pass
    try:
        v = (el.legacy_properties() or {}).get("Value")
        if v is not None:
            return str(v)
    except Exception:
        pass
    try:
        return el.window_text() or ""
    except Exception:
        return ""


def _feld_tippen(el, wert, name, trail):
    """Wert per ECHTEN Tastenanschlaegen eintippen (18.08.2026, Finns Fund am
    PC: set_edit_text/set_text malt den Text nur in den Feld-Speicher — kein
    WM_CHAR-Event, MT5 parst nie und rechnet intern mit dem ALTEN Wert weiter.
    Sichtbar stand '2' im Volumen-Feld, das Label daneben rechnete 0.01).
    Deshalb: Fokus OHNE Cursor (set_focus — Fenster-/Tastaturbefehle gehen auch
    ueber Parsec durch, der Parsec-Fund 16.08. betraf nur Maus-Klicks), dann
    tippen wie ein Mensch, dann den Feldtext ZURUECKLESEN und als Zahl
    vergleichen. KEIN TAB danach (18.08.2026, .53): jedes WM_CHAR aktualisiert
    MT5s internen Wert schon live (das Label neben dem Feld rechnet beim Tippen
    mit), und TAB schob den Fokus ins naechste Feld — dort koennte eine
    spaetere Leertaste landen."""
    for _versuch in (1, 2):
        try:
            el.set_focus()
            _warte(0.1, 0.15)
            # Feld GARANTIERT leeren (18.08.2026, Finns 22-Einwand: steht vom
            # letzten Trade noch '2' drin und es kommt '2' dazu, sind es 22).
            # Strg+A UND Pos1+Shift+Ende — je nach Edit-Control greift nur
            # eines von beiden. Danach ZURUECKLESEN, ob es wirklich leer ist.
            el.type_keys("^a{DELETE}", set_foreground=False)
            el.type_keys("{HOME}+{END}{DELETE}", set_foreground=False)
            _warte(0.08, 0.1)
            rest = (_feld_lesen(el) or "").strip()
            if rest:
                # Feld fuellt sich selbst wieder (Auto-Format)? Dann alles
                # markieren und DRUEBERtippen — die Auswahl wird ersetzt, das
                # Ruecklesen unten beweist das Ergebnis.
                trail.append(f"{name}-Feld leert nicht ('{rest}') — tippe ueber die Auswahl")
                el.type_keys("^a", set_foreground=False)
                el.type_keys("{HOME}+{END}", set_foreground=False)
            el.type_keys(str(wert), with_spaces=False, set_foreground=False)
            _warte(0.12, 0.15)
            ist = _feld_lesen(el)
            if zahl_gleich(ist, wert):
                trail.append(f"{name} getippt: {wert}")
                return True
            trail.append(f"{name}-Ruecklesen zeigt '{ist.strip()}' statt {wert}")
        except Exception:
            continue
    trail.append(f"{name} NICHT uebernommen: {wert}")
    return False


def _ist_aendern_dialog(win):
    """Der Aendern-Dialog einer Position: traegt den langen Aendern-Knopf.
    Der F9-Neu-Order-Dialog hat keinen solchen Knopf — damit ist verwechseln
    ausgeschlossen (hier darf NIE ein Buy/Sell-Knopf gedrueckt werden)."""
    try:
        for b in win.descendants(control_type="Button"):
            if ist_aendern_knopf(b.window_text() or ""):
                return True
    except Exception:
        pass
    return False


def _dialog_gehoert_zu(dlg, ticket):
    """Gehoert der Aendern-Dialog wirklich zu UNSERER Position? Der lange
    Aendern-Knopf traegt die Ticket-Nummer ('#123456789 ... aendern'). Steht
    irgendwo eine ANDERE lange Nummer und unsere nirgends, ist es der Dialog
    einer fremden Position — dort darf nichts getippt werden. 7+ Stellen,
    damit Kurse (29989.33) nicht als Ticket zaehlen; zeigt der Dialog gar
    keine lange Nummer, gibt es keinen Widerspruch -> weitermachen."""
    zahlen = []
    try:
        for c in dlg.descendants():
            try:
                t = c.window_text() or ""
            except Exception:
                continue
            zahlen.extend(re.findall(r"(?<!\d)(\d{7,})(?!\d)", t))
    except Exception:
        pass
    if not zahlen:
        return True
    return str(int(ticket)) in zahlen


def _finde_aendern_dialog(hauptfenster, timeout=3.0):
    """Wie _finde_order_dialog (Top-Level UND Kind-Fenster — der F9-Fund vom
    15.08.2026 gilt fuer jeden MT5-Dialog), aber auf den Aendern-Dialog."""
    from pywinauto import Desktop
    pid = hauptfenster.element_info.process_id
    ende = time.time() + timeout
    while time.time() < ende:
        try:
            for w in Desktop(backend="uia").windows():
                try:
                    if w.element_info.process_id == pid and w.is_visible() \
                            and w.element_info.class_name != MT5_KLASSE \
                            and _ist_aendern_dialog(w):
                        return w
                except Exception:
                    continue
        except Exception:
            pass
        try:
            for d in hauptfenster.descendants(control_type="Window"):
                if _ist_aendern_dialog(d):
                    return d
        except Exception:
            pass
        _warte(0.3, 0.3)
    return None


def _kontextmenue_aendern_klicken(timeout=2.0):
    """Ein offenes Kontextmenue nach 'Aendern...'/'Modify...' absuchen und den
    Punkt ausloesen. Menues sind Standard-Windows-Fenster (#32768) — die sieht
    UIA auch bei MT5. Der Punkt heisst deutsch 'Aendern oder Loeschen', darf
    also NICHT durch den Loeschen-Ausschluss von ist_aendern_knopf laufen."""
    from pywinauto import Desktop
    ende = time.time() + timeout
    while time.time() < ende:
        try:
            for m in Desktop(backend="uia").windows():
                try:
                    if m.element_info.class_name != "#32768" \
                            and m.element_info.control_type != "Menu":
                        continue
                    for it in m.descendants(control_type="MenuItem"):
                        t = (it.window_text() or "").lower()
                        if any(k in t for k in ("ändern", "aendern", "andern", "modify")):
                            try:
                                it.invoke()
                                return True
                            except Exception:
                                try:
                                    it.click_input()
                                    return True
                                except Exception:
                                    pass
                except Exception:
                    continue
        except Exception:
            pass
        _warte(0.2, 0.25)
    return False


def _fremde_dialoge_schliessen(hauptfenster):
    """Versehentlich geoeffnete Fenster (z.B. EA-Eigenschaften) wieder zu —
    IMMER ueber Abbrechen/ESC, NIE ueber OK (18.08.2026: der .54-Doppelklick
    traf den Navigator, der ProphosHedgeReader-Dialog ging auf, und das ESC
    ans Hauptfenster hat ihn nicht geschlossen — er blieb bei Finn stehen).
    Aendern-Dialoge werden verschont, um die kuemmert sich der Aufrufer."""
    from pywinauto import Desktop
    try:
        pid = hauptfenster.element_info.process_id
        for d in Desktop(backend="uia").windows():
            try:
                if d.element_info.process_id != pid or not d.is_visible() \
                        or d.element_info.class_name == MT5_KLASSE \
                        or _ist_aendern_dialog(d):
                    continue
                zu = False
                for b in d.descendants(control_type="Button"):
                    if (b.window_text() or "").strip().lower() in ("abbrechen", "cancel"):
                        try:
                            b.click()
                            zu = True
                        except Exception:
                            pass
                        break
                if not zu:
                    d.type_keys("{ESC}", set_foreground=False)
            except Exception:
                continue
    except Exception:
        pass


def _reihen_scan(w, ticket, trail, maus_grenze, anker_pfad=None):
    """Finns Weg als Band-Scan, OHNE jeden UIA-Anker (18.08.2026: auf diesem
    Build sind Handel-Liste, Kontostand-Zeile UND der Position-aendern-Reiter
    im frischen F9-Dialog fuer UIA unsichtbar — der .58-Lauf hat den Reiter-
    Weg widerlegt). Die Positions-Zeile liegt irgendwo im unteren Band des
    Fensters, also wird das Band abgetastet. Pro Punkt: RECHTSKLICK -> nur
    einen LESBAREN Menuepunkt 'Aendern…' klicken -> Dialog per Ticket
    gegenpruefen. Rechtsklicks sind in Liste und Chart harmlos (oeffnen nur
    Menues), geklickt wird nie blind — 'Position schliessen' kann nicht
    passieren. Zweite Runde als Doppelklick-Scan (oeffnet auf der Zeile
    denselben Dialog, sonst nichts; Tabs-/Statusleiste bleiben unterhalb des
    Bands ausgespart). x liegt bei 40 Prozent der Fensterbreite — unterhalb
    des Charts, weg von Marktuebersicht/Navigator und Ein-Klick-Panel."""
    try:
        hr = w.rectangle()
    except Exception:
        return None
    gx = hr.left + int((hr.right - hr.left) * 0.4)

    # Gemerkter Treffer zuerst (18.08.2026, Finns Kalibrier-Idee — nur dass
    # der Bot selbst mitzaehlt: die Ticket-Pruefung sagt ihm, welcher Klick
    # der richtige war, und der wird hier gespeichert und beim naechsten
    # Trade direkt angesprungen). Passt der Anker nicht mehr (Fenster anders,
    # mehr Zeilen), faellt die Pruefung durch und der Scan uebernimmt.
    punkte = []
    if anker_pfad:
        try:
            with open(anker_pfad, encoding="utf-8") as f:
                a = json.load(f)
            ax = hr.left + int((hr.right - hr.left) * float(a["x_frac"]))
            ay = hr.bottom - int(a["y_off"])
            if maus_grenze is None or ay >= maus_grenze:
                punkte.append(("Anker", ax, ay))
        except Exception:
            pass
    # Erfahrungswert zuerst (18.08.2026, Finns Treffer beim 17. Punkt =
    # -316px): die Suche startet dort, wo die Zeile bei Standard-Toolbox
    # praktisch immer liegt, und faechert von da auf — der pro PC gemerkte
    # Anker schlaegt das ohnehin.
    offsets = sorted(range(60, 400, 16), key=lambda o: abs(o - 316))
    for off in offsets:
        y = hr.bottom - off
        if maus_grenze is not None and y < maus_grenze:
            continue
        punkte.append((f"-{off}px", gx, y))

    for runde in ("Rechtsklick-Menue", "Doppelklick"):
        for pname, px_, py_ in punkte:
            if is_paused():
                trail.append("⏸ Echo pausiert — Zeilen-Scan abgebrochen")
                return None
            _maus_fahren(px_, py_, schritte=3)
            # Finns Schritt 1: Zeile markieren, dann erst oeffnen
            _klick_absolut(px_, py_)
            _warte(0.15, 0.2)
            if runde == "Rechtsklick-Menue":
                if not _klick_absolut(px_, py_, taste="rechts"):
                    continue
                _warte(0.25, 0.3)
                if not _kontextmenue_aendern_klicken(timeout=0.8):
                    try:
                        w.type_keys("{ESC}", set_foreground=False)
                    except Exception:
                        pass
                    continue
            else:
                if not _klick_absolut(px_, py_, doppel=True):
                    continue
            d = _finde_aendern_dialog(w, timeout=1.2)
            if d is None:
                # Menue hat geklickt, aber kein Dialog (Punkt lag neben der
                # Zeile, Eintrag ausgegraut) — Menue NICHT offen stehen
                # lassen (Fund aus Finns Screenshot 18.08.)
                try:
                    w.type_keys("{ESC}", set_foreground=False)
                except Exception:
                    pass
                continue
            if _dialog_gehoert_zu(d, ticket):
                trail.append(f"Aendern-Dialog offen ({runde}-Scan @ {pname})")
                if anker_pfad:
                    try:
                        with open(anker_pfad, "w", encoding="utf-8") as f:
                            json.dump({"x_frac": (px_ - hr.left) / max(1, hr.right - hr.left),
                                       "y_off": hr.bottom - py_}, f)
                    except Exception:
                        pass
                return d
            try:
                d.type_keys("{ESC}", set_foreground=False)
            except Exception:
                pass
            _fremde_dialoge_schliessen(w)
    trail.append("Zeilen-Scan ohne Treffer")
    return None


def _handel_tab_aktivieren(w, trail=None, maus_grenze=None):
    """Toolbox auf den 'Handel'-Tab stellen, BEVOR der Bot die Position
    anklickt (28.08.2026, Finns Live-Fund auf Moritz' PC): nach einem frischen
    Terminal-Start stand die Toolbox auf 'Posteingang' (die 'neuer Account'-
    Mail). Die Order ging ueber den F9-Dialog clean durch, aber das SL/TP-
    Aendern klickte ins Leere, weil die Positionsliste gar nicht sichtbar war —
    genau Finns Analyse: erst pruefen/auf 'Handel' gehen, dann die Zeile suchen.

    Best-Effort und idempotent: bevorzugt das UIA-Select-Pattern (KEIN
    Maus-Klick, also nie im Chart-/Ein-Klick-Panel-Bereich, wo ein Klick eine
    Order waere); der Maus-Fallback klickt nur im UNTEREN Fensterbereich, wo die
    Tabs strukturell liegen. Findet der Bot den Tab nicht, laeuft der bisherige
    Positions-Scan unveraendert weiter (nichts wird schlechter)."""
    def _passt(t):
        t = (t or "").strip()
        return t == "Handel" or t == "Trade" or t.startswith(("Handel", "Trade"))
    # Breit suchen: je nach MT5-Build ist der Toolbox-Reiter TabItem, Custom,
    # Button oder Text — notfalls der ganze Baum (None). Alle Treffer sammeln.
    treffer = []
    for ct in ("TabItem", "Custom", "Button", "Text", None):
        try:
            els = w.descendants(control_type=ct) if ct else w.descendants()
        except Exception:
            continue
        for el in els:
            try:
                if _passt(el.window_text()):
                    treffer.append(el)
            except Exception:
                continue
        if treffer:
            break
    if not treffer:
        if trail is not None:
            trail.append("Handel-Tab: kein Element gefunden — Positions-Scan wie gehabt")
        return False
    # WICHTIG (28.08.2026, Finns Fund: select() wechselte den Reiter auf seinem
    # Build NICHT, warf aber auch keinen Fehler → alter Code gab faelschlich
    # 'erledigt' zurueck): select() nur STILL mitnehmen, verlassen tun wir uns
    # auf den echten Maus-Klick auf den Reiter (der liegt strukturell unten in
    # der Toolbox, also kein Chart-/Order-Bereich).
    for el in treffer:
        try:
            el.select()
        except Exception:
            pass
        try:
            r = el.rectangle()
            unten = (maus_grenze is None) or (r.top >= maus_grenze)
            if unten and r.width() > 0 and r.height() > 0:
                cx, cy = r.mid_point().x, r.mid_point().y
                _maus_fahren(cx, cy, schritte=4)
                _klick_absolut(cx, cy)
                if trail is not None:
                    trail.append(f"Handel-Tab geklickt @({cx},{cy})")
                _warte(0.3, 0.3)
                return True
        except Exception:
            continue
    if trail is not None:
        trail.append(f"Handel-Tab: {len(treffer)} Element(e) gefunden, keins unten klickbar")
    return False


def _sltp_klicken(w, ticket, symbol, sl_text, tp_text, trail, anker_pfad=None):
    """SL/TP PER KLICK an die offene Position haengen (18.08.2026, Finns
    Ansage): Zeile der Position in der Handel-Liste finden, Aendern-Dialog
    oeffnen, die vom echten Fill gerechneten Kurse eintippen, Aendern klicken.
    Mehrere Oeffnungswege in fester Reihenfolge (cursor-unabhaengig zuerst,
    Parsec-Fund 16.08.2026); jeder Versuch wird in der Spur vermerkt. Ob es
    WIRKLICH gegriffen hat, prueft ausschliesslich der Aufrufer — lesend."""
    # 1) Kandidaten-Zeilen suchen: Ticket-Treffer zuerst; sonst Zeilen, die das
    #    Symbol PLUS weitere Daten tragen (18.08.2026, Live-Fund: der Dialog
    #    liess sich nie oeffnen — je nach MT5-Build steht das Ticket nicht im
    #    UIA-Namen der Handel-Zeile). Marktuebersicht-Zeilen (nur Symbolname)
    #    fallen durch die Laengen-Bedingung. Welche Zeile die richtige war,
    #    entscheidet am Ende IMMER der Dialog selbst (_dialog_gehoert_zu).
    try:
        haupt_r = w.rectangle()
        maus_grenze = haupt_r.top + (haupt_r.bottom - haupt_r.top) // 2
    except Exception:
        maus_grenze = None
    _fremde_dialoge_schliessen(w)
    # Toolbox zuerst auf 'Handel' — sonst ist die Positionsliste unsichtbar
    # (28.08.2026, frischer Terminal-Start stand auf 'Posteingang', s.o.).
    _handel_tab_aktivieren(w, trail, maus_grenze)

    # Echo pausiert? (28.08.2026, Not-Aus) — dann gar nicht erst anfangen zu
    # klicken. Die Order ist da laengst platziert; SL/TP traegt Finn von Hand
    # nach oder nach dem Fortsetzen ein neuer Lauf.
    if is_paused():
        trail.append("⏸ Echo pausiert — keine SL/TP-Klicks")
        return None

    # 0) Finns Weg als Band-Scan — braucht keinerlei UIA-Anker (s. _reihen_scan)
    dlg = _reihen_scan(w, ticket, trail, maus_grenze, anker_pfad=anker_pfad)

    kandidaten, ticket_da = [], False
    if dlg is None:
        try:
            for ct in ("DataItem", "ListItem", "TreeItem", "Custom", "Text", None):
                for el in (w.descendants(control_type=ct) if ct else w.descendants()):
                    try:
                        t = el.window_text() or ""
                    except Exception:
                        continue
                    if zeile_nennt_ticket(t, ticket):
                        kandidaten.insert(0, el)
                        ticket_da = True
                    elif ist_handelszeile(t, symbol) and len(kandidaten) < 3:
                        kandidaten.append(el)
                if ticket_da:
                    break
        except Exception:
            pass
        trail.append(f"Zeilen-Kandidaten: {len(kandidaten)}"
                     + (" (Ticket dabei)" if ticket_da else ""))

    # 2) Je Kandidat den Aendern-Dialog oeffnen — SendInput-Doppelklick zuerst
    #    (der Weg, den auch die Hand nimmt), dann die synthetischen Wege.
    #    JEDER geoeffnete Dialog wird per Ticket gegengeprueft, bevor getippt
    #    wird — nie die falsche Position anfassen.
    for zeile in kandidaten[:3]:
        # Zwischen den Kandidaten pruefen: hat Finn waehrenddessen pausiert,
        # sofort raus statt weiter am Terminal herumzuklicken (28.08.2026).
        if is_paused():
            trail.append("⏸ Echo pausiert — Klick-Versuche abgebrochen")
            break
        try:
            r = zeile.rectangle()
            mx, my = r.mid_point().x, r.mid_point().y
        except Exception:
            r = None
            mx = my = None
        # Maus-Klicks nur im UNTEREN Fensterbereich (Toolbox): oben liegen
        # Chart und Ein-Klick-Panel — ein Doppelklick dort waere im
        # schlimmsten Fall eine ORDER (18.08.2026, nach dem Navigator-Fund).
        maus_ok = (mx is not None and maus_grenze is not None
                   and r.top >= maus_grenze)
        if maus_ok:
            _maus_fahren(mx, my, schritte=8)
            # Finns Reihenfolge (18.08.2026, manuell vorgemacht): erst die
            # Zeile ANKLICKEN (markieren), dann oeffnen
            _klick_absolut(mx, my)
            _warte(0.2, 0.25)

        def _weg_doppel():
            if not maus_ok or not _klick_absolut(mx, my, doppel=True):
                raise RuntimeError("Maus hier nicht erlaubt/fehlgeschlagen")

        def _weg_invoke():
            zeile.invoke()

        def _weg_dodefault():
            zeile.iface_legacyiaccessible.DoDefaultAction()

        def _weg_menue():
            zeile.select()
            _warte(0.2, 0.25)
            w.type_keys("+{F10}")
            _warte(0.4, 0.35)
            if not _kontextmenue_aendern_klicken():
                raise RuntimeError("kein Menuepunkt")

        def _weg_rechtsklick():
            if not maus_ok or not _klick_absolut(mx, my, taste="rechts"):
                raise RuntimeError("Maus hier nicht erlaubt/fehlgeschlagen")
            _warte(0.4, 0.35)
            if not _kontextmenue_aendern_klicken():
                raise RuntimeError("kein Menuepunkt")

        # Reihenfolge nach Finns Hand-Weg: Rechtsklick-Menue zuerst, dann
        # Doppelklick (oeffnet denselben Dialog), dann die synthetischen Wege
        for name, weg in (("Rechtsklick-Menue", _weg_rechtsklick),
                          ("SendInput-Doppelklick", _weg_doppel),
                          ("invoke", _weg_invoke),
                          ("DoDefaultAction", _weg_dodefault),
                          ("Shift-F10-Menue", _weg_menue)):
            try:
                weg()
            except Exception:
                continue
            d = _finde_aendern_dialog(w, timeout=1.5)
            if d is not None:
                if _dialog_gehoert_zu(d, ticket):
                    dlg = d
                    trail.append(f"Aendern-Dialog offen ({name})")
                    break
                trail.append(f"Dialog einer ANDEREN Position ({name}) — geschlossen")
                try:
                    d.type_keys("{ESC}", set_foreground=False)
                except Exception:
                    pass
            # haengengebliebene Menues UND versehentlich geoeffnete Fenster
            # (EA-Dialog!) schliessen, bevor der naechste Weg drankommt
            try:
                w.type_keys("{ESC}", set_foreground=False)
            except Exception:
                pass
            _fremde_dialoge_schliessen(w)
        if dlg is not None:
            break

    if dlg is None:
        # Geometrie-Fallback (18.08.2026): sieht UIA die Handel-Zeilen nicht,
        # dient die 'Kontostand'-Zeile als Anker — die Positionen stehen im
        # Handel-Tab DIREKT darueber. Blind-Doppelklick in die Zeile(n) ueber
        # dem Anker; ob der RICHTIGE Dialog aufging, entscheidet wie immer
        # _dialog_gehoert_zu, und die Maus bleibt im unteren Fensterbereich.
        anker = None
        try:
            for ct in ("Text", None):
                for el in (w.descendants(control_type=ct) if ct else w.descendants()):
                    try:
                        if (el.window_text() or "").strip().lower().startswith("kontostand"):
                            anker = el.rectangle()
                            break
                    except Exception:
                        continue
                if anker is not None:
                    break
        except Exception:
            pass
        trail.append("Kontostand-Anker " + ("gefunden" if anker is not None else "NICHT gefunden"))
        if anker is not None and maus_grenze is not None:
            gx = anker.left + 80
            menue_notiert = False
            for i, dy in enumerate((10, 29, 48), start=1):
                gy = anker.top - dy
                if gy < maus_grenze:
                    break
                if is_paused():
                    trail.append("⏸ Echo pausiert — Geometrie-Fallback abgebrochen")
                    break
                _maus_fahren(gx, gy, schritte=6)
                # Finns Hand-Weg (18.08.2026, Schritt fuer Schritt vorgemacht):
                # Zeile ANKLICKEN (markieren) -> RECHTSKLICK -> 'Aendern oder
                # loeschen' -> Dialog. Der Menuepunkt wird NUR ueber seinen
                # UIA-Text geklickt — blind mit Pfeiltasten waere 'Position
                # schliessen' einen Fehltritt entfernt. Liest sich das Menue
                # nicht, ist der Doppelklick auf die Zeile der zweite Weg
                # (oeffnet in MT5 denselben Dialog).
                d = None
                if _klick_absolut(gx, gy):
                    _warte(0.25, 0.3)
                    if _klick_absolut(gx, gy, taste="rechts"):
                        _warte(0.4, 0.35)
                        if _kontextmenue_aendern_klicken():
                            d = _finde_aendern_dialog(w, timeout=1.5)
                        else:
                            if not menue_notiert:
                                menue_notiert = True
                                trail.append("Kontextmenue per UIA nicht lesbar")
                            try:
                                w.type_keys("{ESC}", set_foreground=False)
                            except Exception:
                                pass
                if d is None:
                    if not _klick_absolut(gx, gy, doppel=True):
                        continue
                    d = _finde_aendern_dialog(w, timeout=1.5)
                if d is None:
                    continue
                if _dialog_gehoert_zu(d, ticket):
                    dlg = d
                    trail.append(f"Aendern-Dialog offen (Geometrie, Zeile -{i})")
                    break
                trail.append(f"Geometrie Zeile -{i}: fremder Dialog — geschlossen")
                try:
                    d.type_keys("{ESC}", set_foreground=False)
                except Exception:
                    pass
                _fremde_dialoge_schliessen(w)

    if dlg is None:
        _fremde_dialoge_schliessen(w)
        return {"ok": False, "msg": "Aendern-Dialog liess sich nicht oeffnen"}

    # 3) SL/TP-Felder nach Beschriftung, sonst die ersten beiden Edits
    try:
        fmap = _map_felder(dlg)
        edits = dlg.descendants(control_type="Edit")
        sl_el = fmap.get("sl", edits[0] if len(edits) >= 2 else None)
        tp_el = fmap.get("tp", edits[1] if len(edits) >= 2 else None)
        if sl_el is None or tp_el is None:
            raise RuntimeError(f"SL/TP-Felder nicht gefunden ({len(edits)} Edits). "
                               f"Struktur: {_dialog_struktur(dlg)}")
        # ECHT tippen statt set_text (18.08.2026, gleicher Fund wie beim
        # Volumen-Feld: gemalter Text kommt bei MT5 nie an, s. _feld_tippen)
        for el, wert, name in ((sl_el, sl_text, "SL"), (tp_el, tp_text, "TP")):
            if not _feld_tippen(el, wert, name, trail):
                raise RuntimeError(f"{name}-Feld uebernimmt {wert} nicht")
        _warte(0.3, 0.3)
    except Exception as e:
        try:
            dlg.type_keys("{ESC}", set_foreground=False)
        except Exception:
            pass
        return {"ok": False, "msg": f"Felder nicht befuellbar: {e}"}

    # 4) Den BESTAETIGEN-Knopf finden — nicht den 'Position aendern'-Reiter
    # (Fund 18.08.2026, s. ist_bestaetigen_knopf). Reihenfolge: Knopf mit
    # Order-Daten in der Beschriftung; sonst der BREITESTE Aendern-Kandidat
    # (der blaue Balken spannt die Dialogmitte, der Reiter ist schmal).
    knopf = None
    kandidaten_k = []
    try:
        for b in dlg.descendants(control_type="Button"):
            t = b.window_text() or ""
            if ist_bestaetigen_knopf(t):
                knopf = b
                break
            tl = t.strip().lower()
            if ist_aendern_knopf(t) and tl not in (
                    "position ändern", "position aendern", "modify position"):
                kandidaten_k.append(b)
    except Exception:
        pass
    if knopf is None and kandidaten_k:
        def _breite(b):
            try:
                rb = b.rectangle()
                return rb.right - rb.left
            except Exception:
                return 0
        knopf = max(kandidaten_k, key=_breite)
    if knopf is None:
        try:
            dlg.type_keys("{ESC}", set_foreground=False)
        except Exception:
            pass
        return {"ok": False, "msg": "kein Bestaetigen-Knopf im Dialog"}
    try:
        trail.append(f"Bestaetigen-Knopf: '{(knopf.window_text() or '')[:40]}'")
    except Exception:
        pass
    try:
        r = knopf.rectangle()
        _maus_fahren(r.mid_point().x, r.mid_point().y, schritte=8)
    except Exception:
        pass
    # Ausloesen mit ECHTER Eingabe zuerst (18.08.2026, Finns Fund: .click()
    # verpuffte auch HIER — die Felder waren fertig befuellt, aber der Bot
    # schloss den Dialog selbst per ESC, 'das Popup geht einfach weg', kein
    # Bestaetigungssound). Erfolgskriterium: der Dialog schliesst sich VON
    # SELBST (so wie bei Finns Hand-Test). ESC erst, wenn kein Weg wirkt.
    def _dialog_zu():
        try:
            return not dlg.is_visible()
        except Exception:
            return True

    def _k_leertaste():
        knopf.set_focus()
        _warte(0.1, 0.15)
        try:
            hat = bool(knopf.has_keyboard_focus())
        except Exception:
            hat = False
        if not hat:
            raise RuntimeError("kein Tastatur-Fokus")
        knopf.type_keys("{SPACE}", set_foreground=False)

    def _k_sendinput():
        r2 = knopf.rectangle()
        if not _klick_absolut(r2.mid_point().x, r2.mid_point().y):
            raise RuntimeError("SendInput abgelehnt")

    for name, weg in (("Fokus+Leertaste", _k_leertaste),
                      ("SendInput-Klick", _k_sendinput),
                      (".click()", lambda: knopf.click()),
                      ("click_input", lambda: knopf.click_input())):
        try:
            weg()
        except Exception:
            continue
        ende_k = time.time() + 2.5
        while time.time() < ende_k and not _dialog_zu():
            _warte(0.3, 0.3)
        if _dialog_zu():
            trail.append(f"Aendern-Knopf ausgeloest ({name}) — Dialog zu")
            return {"ok": True, "msg": "geklickt"}
        trail.append(f"Aendern-Knopf: {name} ohne Wirkung")
    try:
        dlg.type_keys("{ESC}", set_foreground=False)
    except Exception:
        pass
    return {"ok": False, "msg": "Aendern-Knopf reagiert auf keinen Weg"}


def run(cfg_path, cmd):
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as e:
        return {"ok": False, "retry_ok": True, "msg": f"Config nicht lesbar: {e}"}
    path = str(cfg.get("master_terminal_path") or "").strip()
    expected = int(cfg.get("master_expected_login") or 0)
    if not path or not os.path.exists(path):
        return {"ok": False, "retry_ok": True,
                "msg": f"master_terminal_path fehlt/nicht gefunden: {path}"}
    if not expected:
        return {"ok": False, "retry_ok": True,
                "msg": "master_expected_login fehlt in der Config — keine Order ohne Login-Guard."}

    try:
        import pywinauto  # noqa: F401
    except ImportError:
        return {"ok": False, "retry_ok": True,
                "msg": "pywinauto fehlt — einmal 'Alles neu starten' klicken "
                       "(das Panel installiert es dann selbst)."}
    # Flotte UIA-Timings (25.08.2026, Finns '3-5 s Pause zwischen den Steps'):
    # pywinautos Default wartet bei jedem ins Leere laufenden Element-Lookup
    # volle 5 s (window_find_timeout) — in einer Abfolge mit try/except-Pfaden
    # summiert sich das zu Kunstpausen. Der Dialog ist zu diesem Zeitpunkt
    # laengst da; 1 s Puffer reicht, die harten Abbruch-Checks bleiben.
    try:
        from pywinauto.timings import Timings
        Timings.window_find_timeout = 1.0
        Timings.exists_timeout = 0.3
    except Exception:
        pass

    symbol = str(cmd["symbol"]).strip()
    kauf = str(cmd["richtung"]).lower() == "buy"
    vol = float(cmd["volumen"])

    # 1) LESEND: Kurs + Positionsstand VORHER (+ Login-Kontrolle)
    lese = _api_lesen(path, expected, symbol=symbol)
    if "fehler" in lese:
        return {"ok": False, "retry_ok": True, "msg": lese["fehler"]}
    digits = lese["digits"]
    contract_size = lese["contract_size"]
    vorher_tickets = {p["ticket"] for p in lese["positionen"]}

    # Schritt-Spur (15.08.2026): jede Station vermerken — steht bei Erfolg UND
    # Fehler in der Meldung, damit Finn/ich sofort sieht, wo der Bot steht.
    trail = []

    # Start-Versatz (28.08.2026, Finns Sorge): starten mehrere Flotten-Instanzen
    # im selben Moment, blieben sie trotz gestreuter Einzelschritte anfangs eng
    # beieinander. 0-1.2 s Wuerfel VOR dem ersten sichtbaren Schritt zieht die
    # Laeufe von Beginn an auseinander.
    _warte(0.0, 1.2)

    # 2b) Ins (vom Check bereits geoeffnete) Terminal gehen -> Guard
    w = _finde_terminal(expected)
    if w is None:
        return {"ok": False, "retry_ok": True,
                "msg": f"Kein MT5-Fenster mit Konto {expected} gefunden."}
    _fenster_betreten(w)
    if str(expected) not in (w.window_text() or ""):
        return {"ok": False, "retry_ok": True,
                "msg": "Fenster-Guard: Titelzeile passt nicht — Abbruch ohne Tastendruck."}
    trail.append("Terminal betreten")

    # 3) F9 -> Dialog -> Felder direkt setzen (cursor-unabhaengig, s.o. Parsec)
    w.type_keys("{F9}")
    _warte(0.4, 0.35)
    dlg = _finde_order_dialog(w)
    if dlg is None:
        return {"ok": False, "retry_ok": True,
                "msg": "F9-Dialog nicht gefunden — Abbruch, nichts gesendet. [" + " → ".join(trail) + "]"}
    trail.append("F9-Dialog offen")
    try:
        combos = dlg.descendants(control_type="ComboBox")
        edits = dlg.descendants(control_type="Edit")
        if not combos or len(edits) < 3:
            # Selbst-Diagnose (15.08.2026): die Struktur des Dialogs gleich
            # mitliefern — erspart den separaten inspect-Lauf am PC.
            probe = []
            try:
                for c in dlg.descendants()[:30]:
                    try:
                        probe.append(f"{c.element_info.control_type}:"
                                     f"{(c.window_text() or '')[:18]}")
                    except Exception:
                        continue
            except Exception:
                pass
            raise RuntimeError(
                f"Dialog-Felder nicht ansprechbar (ComboBoxen: {len(combos)}, "
                f"Edits: {len(edits)}). Struktur: {' | '.join(probe) or 'leer'}")
        # Symbol im Dropdown auswaehlen (per symbol_select schon in der
        # Marktuebersicht). control-basiert (select) — cursor-unabhaengig, weil
        # Parsec den Zeiger abfaengt. Maus-Animation nur noch Kosmetik.
        sym_combo = combos[0]
        try:
            r = sym_combo.rectangle(); _maus_fahren(r.mid_point().x, r.mid_point().y, schritte=8)
        except Exception:
            pass

        # Symbol BESTAETIGEN statt nur auswaehlen (18.08.2026, Spur-Fund:
        # select() schlug still fehl und nur der zufaellig richtige Chart
        # rettete den Lauf — ohne Bestaetigung ginge die Order aufs falsche
        # Symbol). Lesen via _feld_lesen (window_text waere nur das Label).
        def _symbol_drin():
            return symbol.lower() in (_feld_lesen(sym_combo) or "").lower()

        # IMMER aktiv auswaehlen (18.08.2026, Finns Ansage: der Bot geht
        # sichtbar ins Asset-Feld und waehlt selbst — nicht nur nachschauen,
        # was das Chart-Profil vorgibt). Bestaetigt wird trotzdem per Lesen.
        # Exakter Direkt-Select ZUERST (25.08.2026, Finns Tempo-Fund: das
        # fruehere sym_combo.texts() enumerierte IMMER die komplette
        # Marktuebersicht per UIA — bei 250 Symbolen die '5 s Pause' vor der
        # Asset-Auswahl). Die Listen-Suche ist nur noch Fallback fuer
        # Broker-Suffixe (z.B. 'NAS100.r').
        try:
            sym_combo.select(symbol)
        except Exception:
            try:
                for opt in sym_combo.texts():
                    if symbol.lower() in (opt or "").lower():
                        sym_combo.select(opt)
                        break
            except Exception:
                pass
        _warte(0.15, 0.2)
        gewaehlt = _symbol_drin()
        if not gewaehlt:
            # Combo ist editierbar: Symbol ECHT eintippen (Autovervollstaendigung),
            # TAB uebergibt die Eingabe
            try:
                sym_combo.set_focus(); _warte(0.15, 0.2)
                sym_combo.type_keys("^a{DELETE}", set_foreground=False)
                sym_combo.type_keys(symbol, with_spaces=False, set_foreground=False)
                sym_combo.type_keys("{TAB}", set_foreground=False)
                _warte(0.2, 0.25)
            except Exception:
                pass
            gewaehlt = _symbol_drin()
        trail.append(f"Symbol {'bestaetigt' if gewaehlt else 'NICHT bestaetigt'}: {symbol}")
        if not gewaehlt:
            raise RuntimeError(f"Symbol '{symbol}' steht nicht bestaetigt im Dialog "
                               f"(gelesen: '{(_feld_lesen(sym_combo) or '')[:40]}') — "
                               f"Abbruch, sonst ginge die Order aufs falsche Symbol.")
        _warte(0.1, 0.15)
        # NUR Volumen setzen — SL/TP kommen NACH dem Einstieg aus dem echten
        # Fill-Kurs (Finns Timing-Loesung). Feld nach Beschriftung, sonst
        # Index-Fallback. ECHT tippen statt set_text (18.08.2026, Finns Fund am
        # PC: gemalter Text kommt bei MT5 nie an, s. _feld_tippen) — und ohne
        # bestaetigtes Ruecklesen wird NICHT geklickt (sonst handelt der Bot
        # still den alten Feld-Wert, z.B. 0.01 statt 2).
        vol_el = _map_felder(dlg).get("volumen", edits[0])
        try:
            r = vol_el.rectangle(); _maus_fahren(r.mid_point().x, r.mid_point().y, schritte=6)
        except Exception:
            pass
        if not _feld_tippen(vol_el, f"{vol:g}", "Volumen", trail):
            raise RuntimeError(f"Volumen-Feld uebernimmt {vol:g} nicht — "
                               f"Abbruch VOR dem Order-Knopf.")
        _warte(0.2, 0.25)
    except Exception as e:
        return {"ok": False, "retry_ok": True,
                "msg": f"Abbruch VOR dem Order-Knopf (nichts platziert): {e} [" + " → ".join(trail) + "]"}

    # 4) Buy/Sell-Knopf — der unumkehrbare Schritt. .click() sendet die
    # Klick-Nachricht direkt ans Control (cursor-unabhaengig); click_input als
    # Fallback. Bleibt ein Terminal-UI-Klick, KEINE Expert-/API-Order.
    muster = "buy" if kauf else "sell"
    knopf = None
    try:
        for b in dlg.descendants(control_type="Button"):
            t = (b.window_text() or "").lower()
            if muster in t and "stop" not in t and "limit" not in t:
                knopf = b
                break
    except Exception:
        pass
    if knopf is None:
        inventar = []
        try:
            for b in dlg.descendants(control_type="Button"):
                inventar.append((b.window_text() or "?")[:24])
        except Exception:
            pass
        try:
            dlg.type_keys("{ESC}", set_foreground=False)
        except Exception:
            pass
        return {"ok": False, "retry_ok": True,
                "msg": f"Kein {muster}-Knopf im Dialog gefunden — Abbruch, nichts gesendet. "
                       f"Knoepfe: {', '.join(inventar) or 'keine'} [" + " → ".join(trail) + "]"}
    try:
        r = knopf.rectangle(); _maus_fahren(r.mid_point().x, r.mid_point().y, schritte=6)
    except Exception:
        pass

    def _dialog_weg():
        try:
            return not dlg.is_visible()
        except Exception:
            return True

    def _schnell_bestaetigt(sekunden=4.0):
        """Kurzer LESE-Check nach jedem Ausloese-Versuch: neue Position da oder
        Dialog zu? Nur wenn BEIDES ausbleibt, darf der naechste Weg probiert
        werden — sonst feuern zwei Wege ZWEI Orders."""
        ende_s = time.time() + sekunden
        while time.time() < ende_s:
            _warte(0.35, 0.3)
            st = _api_lesen(path, expected)
            if "fehler" not in st and finde_neue_position(
                    vorher_tickets, st["positionen"], symbol, cmd["richtung"], vol):
                return True
            if _dialog_weg():
                return True
        return False

    # ECHTE Eingabe zuerst (18.08.2026, Live-Fund — dieselbe Lehre wie beim
    # set_text: MT5 reagiert auf echte Events. Das Volumen stand korrekt im
    # Dialog, der .click()-Weg verpuffte, der Dialog blieb einfach stehen).
    # BEWUSST kein pauschales {ENTER}: Enter drueckt den Default-Knopf des
    # Dialogs — und der koennte die falsche Richtung sein.
    def _weg_leertaste():
        knopf.set_focus()
        _warte(0.1, 0.15)
        try:
            hat_fokus = bool(knopf.has_keyboard_focus())
        except Exception:
            hat_fokus = False
        if not hat_fokus:
            # sonst tippte die Leertaste in das gerade fokussierte FELD
            raise RuntimeError("Knopf nimmt keinen Tastatur-Fokus an")
        knopf.type_keys("{SPACE}", set_foreground=False)

    def _weg_sendinput():
        r2 = knopf.rectangle()
        if not _klick_absolut(r2.mid_point().x, r2.mid_point().y):
            raise RuntimeError("SendInput abgelehnt")

    ausgeloest = None
    for weg, tu in (("Fokus+Leertaste", _weg_leertaste),
                    ("SendInput-Klick", _weg_sendinput),
                    (".click()", lambda: knopf.click()),
                    ("click_input", lambda: knopf.click_input())):
        try:
            tu()
        except Exception:
            continue
        trail.append(f"{muster}-Knopf: {weg}")
        ausgeloest = weg
        if _schnell_bestaetigt():
            break
    if ausgeloest is None:
        try:
            dlg.type_keys("{ESC}", set_foreground=False)
        except Exception:
            pass
        return {"ok": False, "retry_ok": True,
                "msg": "Buy/Sell-Knopf liess sich auf keinem Weg ausloesen "
                       "[" + " → ".join(trail) + "]"}

    # 5) LESEND: Bestaetigung am Positionsstand (bis 12 s), nie der UI glauben.
    ende = time.time() + 12
    while time.time() < ende:
        _warte(0.4, 0.35)
        nachher = _api_lesen(path, expected)
        if "fehler" in nachher:
            continue
        p = finde_neue_position(vorher_tickets, nachher["positionen"], symbol,
                                cmd["richtung"], vol)
        if p:
            fill = p["preis"]   # ECHTER Einstiegskurs der offenen Position
            trail.append(f"Position offen @ {fill}")
            # Schalter aus (18.08.2026): Order pur, SL/TP macht Finn von Hand —
            # Dialog zu, fertig, KEIN Scan.
            mit_sltp = False
            try:
                mit_sltp = (float(cmd.get("sl_usd") or 0) > 0
                            and float(cmd.get("tp_usd") or 0) > 0)
            except (TypeError, ValueError):
                pass
            if not mit_sltp:
                try:
                    dlg.type_keys("{ESC}", set_foreground=False)
                except Exception:
                    pass
                trail.append("SL/TP: manuell (Schalter aus)")
                return {"ok": True, "retry_ok": False, "verified": True, "mode": "click",
                        "msg": "per Klick platziert — SL/TP bewusst NICHT gesetzt "
                               "(Schalter aus), von Hand nachtragen",
                        "trail": " → ".join(trail), "symbol": symbol,
                        "richtung": "buy" if kauf else "sell",
                        "volumen": p["volumen"], "price": fill, "ticket": p["ticket"]}
            # SL/TP vom echten Fill-Kurs rechnen — eingetragen wird PER KLICK
            # (18.08.2026, Finns Ansage: kein API-Schreibweg mehr). Vorher den
            # F9-Dialog schliessen, er laege sonst vor der Handel-Liste.
            sl, tp = berechne_sl_tp(cmd["richtung"], fill, vol, contract_size,
                                    cmd["sl_usd"], cmd["tp_usd"], digits)
            try:
                dlg.type_keys("{ESC}", set_foreground=False)
            except Exception:
                pass
            _warte(0.2, 0.25)
            # Anker-Datei: gemerkte Treffer-Stelle des Zeilen-Scans. BEWUSST
            # mit 'anker-'-Praefix, damit sie NIE ins config-*.json-Muster
            # des Copiers faellt.
            anker_pfad = os.path.join(os.path.dirname(os.path.abspath(cfg_path)),
                                      "anker-" + os.path.basename(cfg_path))
            k = _sltp_klicken(w, p["ticket"], symbol, fmt_preis(sl, digits),
                              fmt_preis(tp, digits), trail, anker_pfad=anker_pfad)
            # Bestaetigung NUR lesend: traegt die Position die Werte wirklich?
            bestaetigt = False
            ende2 = time.time() + 10
            while time.time() < ende2 and not bestaetigt:
                _warte(0.5, 0.4)
                st = _api_lesen(path, expected)
                if "fehler" in st:
                    continue
                for q in st["positionen"]:
                    if q["ticket"] == p["ticket"] \
                            and sltp_bestaetigt(q["sl"], q["tp"], sl, tp, digits):
                        bestaetigt = True
                        break
            if bestaetigt:
                trail.append(f"SL {fmt_preis(sl, digits)} / TP {fmt_preis(tp, digits)} "
                             f"per Klick gesetzt")
                return {"ok": True, "retry_ok": False, "verified": True, "mode": "click",
                        "msg": "per Klick platziert, SL/TP per Klick am echten Einstieg gesetzt",
                        "trail": " → ".join(trail),
                        "symbol": symbol, "richtung": "buy" if kauf else "sell",
                        "volumen": p["volumen"], "price": fill,
                        "sl": sl, "tp": tp, "ticket": p["ticket"]}
            # Position IST offen, aber SL/TP nicht bestaetigt — kritisch: klar
            # melden, NICHT erneut platzieren (retry_ok False), von Hand nachtragen.
            return {"ok": False, "retry_ok": False,
                    "msg": f"Position ist OFFEN @ {fill}, aber SL/TP-Klick nicht bestaetigt "
                           f"({k.get('msg')}) — im Terminal SL {fmt_preis(sl, digits)} / "
                           f"TP {fmt_preis(tp, digits)} SOFORT von Hand nachtragen! "
                           f"Spur: [" + " → ".join(trail) + "]",
                    "trail": " → ".join(trail), "symbol": symbol,
                    "richtung": "buy" if kauf else "sell", "volumen": p["volumen"],
                    "price": fill, "sl": sl, "tp": tp, "ticket": p["ticket"]}
    # Kein neuer Positionsstand: entweder Markt zu (Wochenende) oder der Klick
    # kam nicht an. Dialog-Text auf 'geschlossen' pruefen, sonst Struktur mitgeben.
    markt_zu = False
    try:
        for t in dlg.descendants(control_type="Text"):
            if "geschloss" in (t.window_text() or "").lower() or "closed" in (t.window_text() or "").lower():
                markt_zu = True
                break
    except Exception:
        pass
    struktur = _dialog_struktur(dlg)
    # Dialog nicht offen stehen lassen (18.08.2026, Finns Live-Fund: der Bot
    # war fertig, aber der Dialog blieb minutenlang stehen — halbkonfigurierte
    # Order, die jeder versehentlich ausloesen koennte).
    try:
        dlg.type_keys("{ESC}", set_foreground=False)
    except Exception:
        pass
    if markt_zu:
        return {"ok": False, "retry_ok": True,
                "msg": "Markt ist geschlossen (Wochenende/ausserhalb der Handelszeit) — "
                       "die Order kann jetzt nicht ausgefuehrt werden. Spur: [" + " → ".join(trail) + "]",
                "trail": " → ".join(trail)}
    return {"ok": False, "retry_ok": False,
            "msg": "KEINE Bestaetigung binnen 12 s — Position nicht am Konto, Dialog "
                   "geschlossen. Spur: [" + " → ".join(trail) + "] · Dialog: " + struktur,
            "trail": " → ".join(trail)}


def modus_inspect(cfg_path):
    """Diagnose: F9-Dialog oeffnen und alle Steuerelemente dumpen — platziert
    NICHTS. Der Dump entscheidet die Feld-Zuordnung, falls run abbricht."""
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    login = int(cfg.get("master_expected_login") or 0)
    w = _finde_terminal(login)
    if not w:
        sys.exit(f"Kein MT5-Fenster mit Konto {login} gefunden (Terminal offen?).")
    print(f"Fenster: {w.window_text()!r}")
    w.set_focus()
    time.sleep(0.5)
    w.type_keys("{F9}")
    time.sleep(0.4)
    dlg = _finde_order_dialog(w)
    if not dlg:
        sys.exit("Kein Order-Dialog gefunden.")
    print(f"Dialog: {dlg.window_text()!r} — Steuerelemente:")
    dlg.print_control_identifiers(depth=4)
    print("\nDump komplett an Claude schicken — daraus wird die Feld-Zuordnung gebaut.")


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "mousetest":
        modus_mousetest()
        return 0
    if len(sys.argv) >= 3 and sys.argv[1] == "inspect":
        modus_inspect(sys.argv[2])
        return 0
    if len(sys.argv) < 3:
        print(json.dumps({"ok": False, "retry_ok": True,
                          "msg": "Aufruf: order_bot.py <config.json> '<befehl-json>'"}))
        return 2
    try:
        cmd = json.loads(sys.argv[2])
    except ValueError as e:
        print(json.dumps({"ok": False, "retry_ok": True, "msg": f"Befehl kein gueltiges JSON: {e}"}))
        return 2
    fehler = pruefe_befehl(cmd)
    if fehler:
        print(json.dumps({"ok": False, "retry_ok": True,
                          "msg": "Befehl unvollstaendig: " + " · ".join(fehler)}))
        return 2
    res = run(sys.argv[1], cmd)
    print(json.dumps(res))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
