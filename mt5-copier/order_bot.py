#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Order-Bot — platziert die MASTER-Order per MetaTrader5-API (15.08.2026).

Ersetzt den UI-Automation-Testaufbau aus order-bot/ (14.08.2026): seit die
Master-Terminals von der Provisionierung selbst verwaltet werden, geht die
Order direkt ueber die Python-API des jeweiligen Terminals — exakte SL/TP-
Preise, echte Bestaetigung per Retcode, kein Dialog-Getippe.

Aufruf (vom Panel als kurzlebiger Subprozess):
  python order_bot.py <config-datei.json> "<befehl-json>"
Befehl:  {"symbol": "NDX100", "richtung": "buy", "volumen": 0.2,
          "sl_usd": 100, "tp_usd": 300}
Antwort: EINE JSON-Zeile auf stdout, z.B.
  {"ok": true, "retcode": 10009, "price": 29981.2, "sl": 29481.2, "tp": ...}

Sicherheits-Grundsaetze (wie Copier):
- Verbindung NUR an das Terminal der Config (path=master_terminal_path),
  mt5.login() wird NIE aufgerufen — eingeloggt ist, wer eingeloggt ist.
- Login-Guard: account_info().login muss master_expected_login sein, sonst
  Abbruch VOR jeder Order (Falsch-Konto-Vorfall 15.08.2026).
- SL und TP sind Pflicht — nackte Orders platziert der Bot nicht.
"""

import json
import math
import os
import sys


# ---------------------------------------------------------------------------
# REIN RECHNENDE Funktionen — ohne MetaTrader testbar (selftest.py, Mac)
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
            # isfinite deckt NaN und Infinity ab (Review-Fund 15.08.2026): 'nan <= 0'
            # ist False und haette die Pruefung still passiert.
            if not math.isfinite(v) or v <= 0:
                fehler.append(f"{k} fehlt oder <= 0")
        except (TypeError, ValueError):
            fehler.append(f"{k} ist keine Zahl")
    return fehler


def berechne_sl_tp(richtung, ref_preis, volumen, contract_size, sl_usd, tp_usd, digits=2):
    """$-Betraege → absolute Preise. 1.0 Preis-Einheit ist volumen*contract_size
    wert (Index-CFD in USD) — dieselbe Basis wie die Exposure-Formel im Copier
    und berechne_sl_tp aus dem order-bot/-Testaufbau (die Rechnung ueberlebt,
    nur der Ausfuehrungsweg ist neu). Rueckgabe: (sl_preis, tp_preis)."""
    ref = float(ref_preis)
    je_einheit = float(volumen) * float(contract_size)  # $ pro 1.0 Preisbewegung
    if je_einheit <= 0:
        raise ValueError("volumen*contract_size muss > 0 sein")
    kauf = str(richtung).lower() == "buy"
    d_sl = float(sl_usd) / je_einheit
    d_tp = float(tp_usd) / je_einheit
    sl = round(ref - d_sl if kauf else ref + d_sl, int(digits))
    tp = round(ref + d_tp if kauf else ref - d_tp, int(digits))
    return sl, tp


# ---------------------------------------------------------------------------
# Ausfuehrung — nur auf dem PC mit MetaTrader5-Paket
# ---------------------------------------------------------------------------

def run(cfg_path, cmd):
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return {"ok": False, "msg": "MetaTrader5-Paket fehlt (nur auf dem PC lauffaehig)."}
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as e:
        return {"ok": False, "msg": f"Config nicht lesbar: {e}"}
    path = str(cfg.get("master_terminal_path") or "").strip()
    expected = int(cfg.get("master_expected_login") or 0)
    if not path or not os.path.exists(path):
        return {"ok": False, "msg": f"master_terminal_path fehlt/nicht gefunden: {path}"}
    if not expected:
        # Hart statt still (Review-Fund 15.08.2026): ohne das Feld waere die
        # einzige Falsch-Konto-Sperre wirkungslos — dann lieber keine Order.
        return {"ok": False, "msg": "master_expected_login fehlt in der Config — "
                                    "keine Order ohne Login-Guard."}

    if not mt5.initialize(path=path):
        return {"ok": False, "msg": f"Terminal-Verbindung fehlgeschlagen: {mt5.last_error()}"}
    try:
        ai = mt5.account_info()
        if ai is None:
            return {"ok": False, "msg": "Kein Konto verbunden (account_info leer)."}
        if expected and int(ai.login) != expected:
            return {"ok": False, "msg": f"Terminal ist im FALSCHEN Konto ({ai.login} statt "
                                        f"{expected}) — keine Order platziert."}

        symbol = str(cmd["symbol"]).strip()
        if not mt5.symbol_select(symbol, True):
            return {"ok": False, "msg": f"Symbol '{symbol}' nicht waehlbar (Schreibweise pruefen)."}
        si = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if si is None or tick is None or not (tick.ask and tick.bid):
            return {"ok": False, "msg": f"Keine Kurse fuer '{symbol}' (Markt zu?)."}

        kauf = str(cmd["richtung"]).lower() == "buy"
        vol = float(cmd["volumen"])
        ref = float(tick.ask if kauf else tick.bid)
        cs = float(getattr(si, "trade_contract_size", 0) or 0) or 1.0
        digits = int(getattr(si, "digits", 2) or 2)
        sl, tp = berechne_sl_tp(cmd["richtung"], ref, vol, cs,
                                cmd["sl_usd"], cmd["tp_usd"], digits)

        # Broker-Mindestabstand: zu enge Stops lehnt der Server sowieso ab —
        # hier mit klarer Ansage statt kryptischem Retcode.
        min_dist = float(getattr(si, "trade_stops_level", 0) or 0) * float(si.point)
        if min_dist > 0 and (abs(ref - sl) < min_dist or abs(ref - tp) < min_dist):
            return {"ok": False, "msg": f"SL/TP zu nah am Kurs — Broker-Minimum ist "
                                        f"{min_dist:.{digits}f} Preis-Einheiten Abstand."}

        # Filling-Kaskade wie im Copier: IOC → FOK → RETURN
        fillings = [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN]
        r = None
        for filling in fillings:
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": vol,
                "type": mt5.ORDER_TYPE_BUY if kauf else mt5.ORDER_TYPE_SELL,
                "price": ref,
                "sl": float(sl),
                "tp": float(tp),
                "deviation": int(cfg.get("deviation_points", 30)),
                "comment": "Prophos-Order",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling,
            }
            r = mt5.order_send(req)
            if r is None:
                return {"ok": False, "msg": f"order_send None: {mt5.last_error()}"}
            if r.retcode != 10030:  # invalid filling → naechste Variante probieren
                break
        # Retcode-Ehrlichkeit (Review-Fund 15.08.2026): ok=false heisst NICHT
        # automatisch 'keine Order im Markt'. 10010 = Teilausfuehrung (Position
        # existiert!), 10008 = Order liegt im Orderbuch. retry_ok sagt dem
        # Frontend, ob ein erneuter Versuch gefahrlos ist — nur bei eindeutig
        # ABGELEHNTEN Retcodes, im Zweifel False ('erst im Terminal pruefen').
        ok = r.retcode in (mt5.TRADE_RETCODE_DONE, 10010)   # DONE, DONE_PARTIAL
        msg = str(getattr(r, "comment", "") or "")
        if r.retcode == 10010:
            msg = "Teilausfuehrung — Positionsgroesse im Terminal pruefen."
        elif r.retcode == 10008:
            msg = "Order liegt im Markt (placed) — NICHT erneut senden, im Terminal pruefen."
        elif r.retcode == 10027:
            msg = ("AutoTrading ist im Terminal deaktiviert — den 'Algo-Handel'-Knopf "
                   "oben in der Werkzeugleiste einschalten, dann erneut starten.")
        abgelehnt = {10004, 10006, 10013, 10014, 10015, 10016, 10017, 10018,
                     10019, 10021, 10027, 10030}
        return {"ok": ok, "retcode": int(r.retcode), "msg": msg,
                "retry_ok": (not ok) and int(r.retcode) in abgelehnt,
                "order": int(getattr(r, "order", 0) or 0),
                "deal": int(getattr(r, "deal", 0) or 0),
                "price": float(getattr(r, "price", 0) or ref),
                "sl": float(sl), "tp": float(tp), "volumen": vol,
                "richtung": "buy" if kauf else "sell", "symbol": symbol}
    finally:
        mt5.shutdown()


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"ok": False, "msg": "Aufruf: order_bot.py <config.json> '<befehl-json>'"}))
        return 2
    try:
        cmd = json.loads(sys.argv[2])
    except ValueError as e:
        print(json.dumps({"ok": False, "msg": f"Befehl kein gueltiges JSON: {e}"}))
        return 2
    fehler = pruefe_befehl(cmd)
    if fehler:
        print(json.dumps({"ok": False, "msg": "Befehl unvollstaendig: " + " · ".join(fehler)},
                         ensure_ascii=False))
        return 2
    res = run(sys.argv[1], cmd)
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
