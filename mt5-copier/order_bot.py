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
            if not mt5.symbol_select(symbol, True):
                return {"fehler": f"Symbol '{symbol}' nicht waehlbar (Schreibweise pruefen)."}
            si = mt5.symbol_info(symbol)
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


# ---------------------------------------------------------------------------
# SICHTBARER Klick-Teil (pywinauto) — nur bei run/inspect importiert
# ---------------------------------------------------------------------------

MT5_KLASSE = "MetaQuotes::MetaTrader::5.00"


def _maus_fahren(x, y, schritte=16):
    """Den ECHTEN Mauszeiger sichtbar hinfahren (nicht teleportieren) — Finns
    Ansage: man soll sehen, wie der Bot die Kontrolle uebernimmt."""
    from pywinauto import mouse
    try:
        import win32api
        cx, cy = win32api.GetCursorPos()
    except Exception:
        cx, cy = x, y
    for i in range(1, schritte + 1):
        mouse.move(coords=(int(cx + (x - cx) * i / schritte),
                           int(cy + (y - cy) * i / schritte)))
        time.sleep(0.02)


def _taskleiste_klick(login):
    """Schritt 1 der Choreografie: Maus in die Taskleiste, Terminal-Tab klicken.
    Klappt das nicht (Tab-Gruppierung o.ae.), faellt der Lauf auf set_focus
    zurueck — die Order-Schritte danach sind identisch."""
    from pywinauto import Desktop
    try:
        tray = Desktop(backend="uia").window(class_name="Shell_TrayWnd")
        for b in tray.descendants(control_type="Button"):
            if str(login) in (b.window_text() or ""):
                r = b.rectangle()
                _maus_fahren(r.mid_point().x, r.mid_point().y)
                b.click_input()
                time.sleep(0.8)
                return True
    except Exception:
        pass
    return False


def _finde_terminal(login):
    from pywinauto import Desktop
    for w in Desktop(backend="uia").windows():
        try:
            if w.element_info.class_name == MT5_KLASSE and str(login) in (w.window_text() or ""):
                return w
        except Exception:
            continue
    return None


def _finde_order_dialog(hauptfenster, timeout=6.0):
    """Nach F9: das Order-Dialogfenster desselben Prozesses suchen."""
    from pywinauto import Desktop
    pid = hauptfenster.element_info.process_id
    ende = time.time() + timeout
    while time.time() < ende:
        for w in Desktop(backend="uia").windows():
            try:
                if (w.element_info.process_id == pid
                        and w.element_info.class_name != MT5_KLASSE
                        and w.element_info.control_type == "Window" and w.is_visible()):
                    return w
            except Exception:
                continue
        time.sleep(0.2)
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
    ref = lese["ref_ask"] if kauf else lese["ref_bid"]
    digits = lese["digits"]
    sl, tp = berechne_sl_tp(cmd["richtung"], ref, vol, lese["contract_size"],
                            cmd["sl_usd"], cmd["tp_usd"], digits)
    vorher_tickets = {p["ticket"] for p in lese["positionen"]}

    # 2) SICHTBAR: Taskleiste -> Fenster -> Guard
    if not _taskleiste_klick(expected):
        w0 = _finde_terminal(expected)
        if w0 is None:
            return {"ok": False, "retry_ok": True,
                    "msg": f"Kein MT5-Fenster mit Konto {expected} gefunden."}
        w0.set_focus()
        time.sleep(0.6)
    w = _finde_terminal(expected)
    if w is None:
        return {"ok": False, "retry_ok": True,
                "msg": f"Kein MT5-Fenster mit Konto {expected} gefunden."}
    w.set_focus()
    time.sleep(0.5)
    if str(expected) not in (w.window_text() or ""):
        return {"ok": False, "retry_ok": True,
                "msg": "Fenster-Guard: Titelzeile passt nicht — Abbruch ohne Tastendruck."}

    # 3) SICHTBAR: F9 -> Dialog -> Felder eintippen (Symbol zuerst = 'ins Asset gehen')
    w.type_keys("{F9}")
    time.sleep(0.9)
    dlg = _finde_order_dialog(w)
    if dlg is None:
        return {"ok": False, "retry_ok": True,
                "msg": "Order-Dialog (F9) nicht gefunden — Abbruch, nichts gesendet."}
    try:
        combos = dlg.descendants(control_type="ComboBox")
        edits = dlg.descendants(control_type="Edit")
        if not combos or len(edits) < 3:
            raise RuntimeError(
                f"Dialog-Felder nicht ansprechbar (ComboBoxen: {len(combos)}, "
                f"Edits: {len(edits)}) — einmal 'inspect' laufen lassen: "
                f"python order_bot.py inspect <config> im start-panel-CMD.")
        felder = [("symbol", combos[0], symbol),
                  ("volumen", edits[0], f"{vol:g}"),
                  ("sl", edits[1], fmt_preis(sl, digits)),
                  ("tp", edits[2], fmt_preis(tp, digits))]
        for _name, el, wert in felder:
            r = el.rectangle()
            _maus_fahren(r.mid_point().x, r.mid_point().y, schritte=8)
            el.click_input()
            el.type_keys("^a{DELETE}", set_foreground=False)
            el.type_keys(str(wert), with_spaces=False, set_foreground=False)
            time.sleep(0.2)
    except Exception as e:
        return {"ok": False, "retry_ok": True,
                "msg": f"Abbruch VOR dem Order-Knopf (nichts platziert): {e}"}

    # 4) SICHTBAR: Maus auf den Buy/Sell-Knopf — der unumkehrbare Schritt
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
    r = knopf.rectangle()
    _maus_fahren(r.mid_point().x, r.mid_point().y)
    knopf.click_input()

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
            # Dialog schliessen, falls MT5 ihn nach der Ausfuehrung offen laesst
            try:
                dlg.type_keys("{ESC}", set_foreground=False)
            except Exception:
                pass
            return {"ok": True, "retry_ok": False, "verified": True, "mode": "click",
                    "msg": "per Klick platziert und am Konto bestaetigt",
                    "symbol": symbol, "richtung": "buy" if kauf else "sell",
                    "volumen": p["volumen"], "price": p["preis"],
                    "sl": p["sl"] or sl, "tp": p["tp"] or tp, "ticket": p["ticket"]}
    return {"ok": False, "retry_ok": False,
            "msg": "KEINE Bestaetigung binnen 12 s — Position nicht am Konto. Im "
                   "Terminal nachsehen (Dialog offen? Order abgelehnt? Requote?). "
                   "NICHT blind wiederholen.",
            "sl": sl, "tp": tp, "price": ref}


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
