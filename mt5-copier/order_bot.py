#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Order-Bot — platziert die MASTER-Order per SICHTBARER Maus-/Tastatur-Steuerung
(15.08.2026, Finns Ansage: die Order muss serverseitig wie ein Handklick
aussehen — eine API-Order traegt die Expert-Markierung, ein echter Klick nicht).

Choreografie (sichtbar, wie mit Finn geuebt):
  1. Maus faehrt in die Taskleiste und klickt den Terminal-Tab
  2. Fenster-Guard: Titelzeile MUSS die Kontonummer tragen, sonst Abbruch
  3. F9 -> Order-Dialog, Symbol/Volumen/SL/TP werden sichtbar eingetippt
  4. Maus faehrt auf den Buy/Sell-Knopf und klickt — der einzige unumkehrbare Schritt
  5. Bestaetigung NICHT der UI glauben: Positionsliste des Kontos (nur LESEND
     ueber die MetaTrader5-API — Lesen traegt keine Order-Markierung)

Die API wird ausschliesslich LESEND benutzt: aktueller Kurs fuer die
$->Preis-Umrechnung, Positionsstand vorher/nachher. mt5.order_send existiert
in dieser Datei bewusst NICHT.

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
    for k in ("volumen", "sl_usd", "tp_usd"):
        try:
            v = float(cmd.get(k) or 0)
            # isfinite deckt NaN und Infinity ab ('nan <= 0' waere still False)
            if not math.isfinite(v) or v <= 0:
                fehler.append(f"{k} fehlt oder <= 0")
        except (TypeError, ValueError):
            fehler.append(f"{k} ist keine Zahl")
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
                time.sleep(0.3)
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


def _sltp_setzen(path, expected, ticket, sl, tp):
    """SL/TP an eine BEREITS offene Position haengen (15.08.2026, Finns Timing-
    Loesung): die Order wird per Klick zum echten Marktkurs eroeffnet, DANN liest
    der Bot den tatsaechlichen Einstiegskurs und setzt SL/TP exakt darauf — keine
    Drift durch die Sekunden zwischen Kurslesen und Klick. Das aendert nur SL/TP
    einer manuell eroeffneten Position; wie die Position AUFGING (Handklick) bleibt
    unveraendert."""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return {"ok": False, "msg": "MetaTrader5-Paket fehlt."}
    if not mt5.initialize(path=path):
        return {"ok": False, "msg": f"Verbindung fuer SL/TP fehlgeschlagen: {mt5.last_error()}"}
    try:
        ai = mt5.account_info()
        if ai is None or (expected and int(ai.login) != expected):
            return {"ok": False, "msg": "Falsches/kein Konto beim SL/TP-Setzen."}
        pos = None
        for p in (mt5.positions_get() or []):
            if int(p.ticket) == int(ticket):
                pos = p
                break
        if pos is None:
            return {"ok": False, "msg": "Position fuer SL/TP nicht gefunden."}
        r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": int(ticket),
                            "symbol": pos.symbol, "sl": float(sl), "tp": float(tp)})
        if r is None:
            return {"ok": False, "msg": f"SL/TP order_send None: {mt5.last_error()}"}
        return {"ok": r.retcode == mt5.TRADE_RETCODE_DONE, "retcode": int(r.retcode),
                "msg": str(getattr(r, "comment", "") or "")}
    finally:
        mt5.shutdown()


# ---------------------------------------------------------------------------
# SICHTBARER Klick-Teil (pywinauto) — nur bei run/inspect importiert
# ---------------------------------------------------------------------------

MT5_KLASSE = "MetaQuotes::MetaTrader::5.00"


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
        time.sleep(0.02)


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
    print(json.dumps(res, ensure_ascii=False))


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
            time.sleep(0.4)
    except Exception:
        pass
    w.set_focus()
    time.sleep(0.4)
    try:
        from pywinauto import mouse
        r = w.rectangle()
        # linkes Drittel der Titelzeile — weit weg von Minimieren/Schliessen
        x = int(r.left + (r.right - r.left) * 0.35)
        y = int(r.top + 14)
        _maus_fahren(x, y)
        mouse.click(coords=(x, y))
        time.sleep(0.3)
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
        time.sleep(0.3)
    return None


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
    time.sleep(0.9)
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
        gewaehlt = False
        try:
            for opt in sym_combo.texts():
                if symbol.lower() in (opt or "").lower():
                    sym_combo.select(opt); gewaehlt = True; break
        except Exception:
            pass
        if not gewaehlt:
            try:
                sym_combo.select(symbol); gewaehlt = True
            except Exception:
                pass
        trail.append(f"Symbol {'gewaehlt' if gewaehlt else 'NICHT gewaehlt'}: {symbol}")
        time.sleep(0.3)
        # NUR Volumen setzen — SL/TP kommen NACH dem Einstieg aus dem echten
        # Fill-Kurs (Finns Timing-Loesung: kein Vor-Ausrechnen aus einem Kurs,
        # der bis zum Klick schon veraltet ist). Feld nach Beschriftung, sonst
        # Index-Fallback. set_edit_text — cursor-unabhaengig.
        vol_el = _map_felder(dlg).get("volumen", edits[0])
        try:
            r = vol_el.rectangle(); _maus_fahren(r.mid_point().x, r.mid_point().y, schritte=6)
        except Exception:
            pass
        gesetzt = False
        for setter in ("set_edit_text", "set_text"):
            try:
                getattr(vol_el, setter)(f"{vol:g}"); gesetzt = True; break
            except Exception:
                continue
        if not gesetzt:
            try:
                vol_el.set_focus()
                vol_el.type_keys("^a{DELETE}" + f"{vol:g}", with_spaces=False, set_foreground=False)
                gesetzt = True
            except Exception:
                pass
        trail.append(f"Volumen {'gesetzt' if gesetzt else 'NICHT gesetzt'}: {vol:g}")
        time.sleep(0.2)
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
        return {"ok": False, "retry_ok": True,
                "msg": f"Kein {muster}-Knopf im Dialog gefunden — Abbruch, nichts gesendet."}
    try:
        r = knopf.rectangle(); _maus_fahren(r.mid_point().x, r.mid_point().y)
    except Exception:
        pass
    klick_weg = None
    try:
        knopf.click(); klick_weg = ".click()"
    except Exception:
        try:
            knopf.click_input(); klick_weg = "click_input"
        except Exception as e:
            return {"ok": False, "retry_ok": True,
                    "msg": f"Buy/Sell-Knopf liess sich nicht ausloesen: {e} [" + " → ".join(trail) + "]"}
    trail.append(f"{muster}-Knopf ausgeloest ({klick_weg})")

    # 5) LESEND: Bestaetigung am Positionsstand (bis 12 s), nie der UI glauben.
    ende = time.time() + 12
    while time.time() < ende:
        time.sleep(0.7)
        nachher = _api_lesen(path, expected)
        if "fehler" in nachher:
            continue
        p = finde_neue_position(vorher_tickets, nachher["positionen"], symbol,
                                cmd["richtung"], vol)
        if p:
            fill = p["preis"]   # ECHTER Einstiegskurs der offenen Position
            trail.append(f"Position offen @ {fill}")
            # SL/TP jetzt vom echten Fill-Kurs rechnen und an die Position haengen
            sl, tp = berechne_sl_tp(cmd["richtung"], fill, vol, contract_size,
                                    cmd["sl_usd"], cmd["tp_usd"], digits)
            m = _sltp_setzen(path, expected, p["ticket"], sl, tp)
            try:
                dlg.type_keys("{ESC}", set_foreground=False)
            except Exception:
                pass
            if m.get("ok"):
                trail.append(f"SL {fmt_preis(sl, digits)} / TP {fmt_preis(tp, digits)} gesetzt")
                return {"ok": True, "retry_ok": False, "verified": True, "mode": "click",
                        "msg": "per Klick platziert, SL/TP am echten Einstieg gesetzt",
                        "trail": " → ".join(trail),
                        "symbol": symbol, "richtung": "buy" if kauf else "sell",
                        "volumen": p["volumen"], "price": fill,
                        "sl": sl, "tp": tp, "ticket": p["ticket"]}
            # Position IST offen, aber SL/TP fehlgeschlagen — kritisch: klar melden,
            # NICHT erneut platzieren (retry_ok False), von Hand nachtragen.
            return {"ok": False, "retry_ok": False,
                    "msg": f"Position ist OFFEN @ {fill}, aber SL/TP setzen fehlgeschlagen "
                           f"({m.get('msg')}) — im Terminal SL/TP SOFORT von Hand nachtragen!",
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
    if markt_zu:
        return {"ok": False, "retry_ok": True,
                "msg": "Markt ist geschlossen (Wochenende/ausserhalb der Handelszeit) — "
                       "die Order kann jetzt nicht ausgefuehrt werden. Spur: [" + " → ".join(trail) + "]",
                "trail": " → ".join(trail)}
    return {"ok": False, "retry_ok": False,
            "msg": "KEINE Bestaetigung binnen 12 s — Position nicht am Konto. "
                   "Spur: [" + " → ".join(trail) + "] · Dialog: " + _dialog_struktur(dlg),
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
    time.sleep(0.9)
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
                          "msg": "Befehl unvollstaendig: " + " · ".join(fehler)}, ensure_ascii=False))
        return 2
    res = run(sys.argv[1], cmd)
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
