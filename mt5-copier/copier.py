#!/usr/bin/env python3
"""
Lokaler MT5-Hedge-Copier — EIGENSTÄNDIGE Testversion, getrennt vom laufenden Duplikum-Setup.

Idee: Auf dem PC der Person laufen zwei MT5-Terminals — eines mit dem Prop-MASTER (dort
wird manuell getradet), eines mit dem LIVE-HEDGE-Konto. Dieses Programm hängt sich an
BEIDE laufenden Terminals, liest die Master-Positionen und setzt die Gegenposition
(Reverse-Hedge) im Hedge-Terminal.

WICHTIG — was dieses Programm NICHT tut:
  · Es loggt sich NIE selbst bei einem Broker ein (keine Zugangsdaten nötig). Es benutzt
    den Account, der im jeweiligen Terminal schon eingeloggt ist.
  · Es sendet NIE eine Order an das Master-Terminal. Der Reader-Prozess enthält keinen
    Order-Code — das ist strukturell ausgeschlossen, nicht nur per Flag.
  · Es fasst Duplikum, app.py, prophos.html oder die Supabase-Tabellen NICHT an.

DREI STUFEN über `mode` in der config:
  1. "dryrun"  (Default) — liest nur, LOGGT was es tun würde. Keine einzige Order.
     → Damit kann man parallel zum laufenden Duplikum vergleichen, ob Richtung, Lots
       und Symbol übereinstimmen. Null Risiko, null Nebenwirkung.
  2. "demo"    — sendet echte Orders, aber NUR wenn das Hedge-Terminal auf einem
     DEMO-Konto eingeloggt ist. Bei einem Echtgeld-Konto verweigert es den Versand.
  3. "live"    — echte Orders auf echtem Konto. Erst wenn Stufe 1+2 sauber liefen.
     ⚠ Für dasselbe Master-Paar dann Duplikum abschalten, sonst doppelter Hedge.

Nicht getestet gegen echte Konten — Stufe 1 und 2 sind genau dafür da.
"""

import json
import multiprocessing as mp
import os
import queue
import sys
import time
from datetime import datetime

# ── Config ─────────────────────────────────────────────────────────────────────
def load_config(path=None):
    path = path or os.environ.get("COPIER_CONFIG") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if not os.path.exists(path):
        sys.exit(f"config.json nicht gefunden ({path}) — config.example.json kopieren und ausfuellen.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def log(tag, msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{tag}] {msg}", flush=True)


# ── Reader: haengt am MASTER-Terminal, liest NUR ────────────────────────────────
# Dieser Prozess importiert order_send nie und ruft es nie auf. Er kann auf dem
# Prop-Konto nichts veraendern.
def reader_proc(cfg, out_q, stop_ev):
    import MetaTrader5 as mt5

    path = cfg["master_terminal_path"]
    if not mt5.initialize(path=path):
        out_q.put({"type": "fatal", "who": "reader", "msg": f"initialize(master) fehlgeschlagen: {mt5.last_error()}"})
        return

    info = mt5.account_info()
    if info is None:
        out_q.put({"type": "fatal", "who": "reader", "msg": "account_info(master) leer — laeuft das Terminal und ist es eingeloggt?"})
        mt5.shutdown()
        return
    out_q.put({"type": "hello", "who": "reader",
               "login": info.login, "server": info.server, "name": info.name,
               "trade_mode": int(info.trade_mode)})

    poll = float(cfg.get("poll_interval", 0.5))
    known = {}  # ticket -> {"volume": float, "type": int, "symbol": str}

    while not stop_ev.is_set():
        try:
            positions = mt5.positions_get()
            if positions is None:
                positions = []
            current = {}
            for p in positions:
                current[int(p.ticket)] = {"volume": float(p.volume), "type": int(p.type), "symbol": str(p.symbol)}

            # neue Positionen
            for tkt, pos in current.items():
                if tkt not in known:
                    out_q.put({"type": "open", "ticket": tkt, **pos})

            # Teil-Schliessung (Volumen geschrumpft)
            for tkt, pos in current.items():
                prev = known.get(tkt)
                if prev and pos["volume"] < prev["volume"] - 1e-9:
                    out_q.put({"type": "partial", "ticket": tkt,
                               "volume_before": prev["volume"], "volume_now": pos["volume"], **{k: pos[k] for k in ("type", "symbol")}})

            # ganz geschlossen
            for tkt, prev in list(known.items()):
                if tkt not in current:
                    out_q.put({"type": "close", "ticket": tkt, **prev})

            known = current
        except Exception as e:
            out_q.put({"type": "error", "who": "reader", "msg": f"{type(e).__name__}: {str(e)[:150]}"})
        time.sleep(poll)

    mt5.shutdown()
    out_q.put({"type": "bye", "who": "reader"})


# ── Writer: haengt am HEDGE-Terminal, platziert die Gegenposition ───────────────
def writer_proc(cfg, in_q, stop_ev):
    import MetaTrader5 as mt5

    mode = str(cfg.get("mode", "dryrun")).lower()
    path = cfg["hedge_terminal_path"]
    if not mt5.initialize(path=path):
        log("writer", f"FATAL initialize(hedge) fehlgeschlagen: {mt5.last_error()}")
        return

    info = mt5.account_info()
    if info is None:
        log("writer", "FATAL account_info(hedge) leer — Terminal offen und eingeloggt?")
        mt5.shutdown()
        return

    # trade_mode: 0 = DEMO, 1 = CONTEST, 2 = REAL
    is_real = int(info.trade_mode) == 2
    log("writer", f"Hedge-Konto {info.login} @ {info.server} · {'ECHTGELD' if is_real else 'DEMO/CONTEST'} · Modus '{mode}'")

    if mode == "demo" and is_real:
        log("writer", "⛔ ABBRUCH: Modus 'demo', aber das Hedge-Terminal ist auf einem ECHTGELD-Konto. "
                      "Entweder Demo-Konto einloggen oder bewusst mode='live' setzen.")
        mt5.shutdown()
        return
    if mode == "live" and not is_real:
        log("writer", "ℹ Modus 'live', Konto ist aber Demo — es wird auf Demo gehandelt.")

    prefix = cfg.get("comment_prefix", "PH")
    magic = int(cfg.get("magic", 770001))
    symbol_map = cfg.get("symbol_map", {})
    multiplier = float(cfg.get("multiplier", 1.0))
    max_lots = float(cfg.get("max_lots_per_hedge", 5.0))
    deviation = int(cfg.get("deviation_points", 30))
    filling_name = str(cfg.get("filling", "IOC")).upper()
    filling = mt5.ORDER_FILLING_FOK if filling_name == "FOK" else mt5.ORDER_FILLING_IOC

    def hedge_positions_by_master():
        """Bestehende Hedges anhand des Kommentars wiedererkennen (Idempotenz nach Neustart)."""
        out = {}
        try:
            for p in (mt5.positions_get() or []):
                c = str(getattr(p, "comment", "") or "")
                if c.startswith(prefix + "-"):
                    try:
                        mtkt = int(c.split("-", 1)[1])
                    except (ValueError, IndexError):
                        continue
                    out[mtkt] = {"ticket": int(p.ticket), "volume": float(p.volume), "symbol": str(p.symbol), "type": int(p.type)}
        except Exception as e:
            log("writer", f"Konnte bestehende Hedges nicht lesen: {type(e).__name__}: {e}")
        return out

    mapping = hedge_positions_by_master()
    if mapping:
        log("writer", f"↩ {len(mapping)} bestehende Hedge-Position(en) wiedererkannt — keine Doppel-Hedges.")

    def calc_lots(hedge_symbol, master_volume):
        lots = master_volume * multiplier
        si = mt5.symbol_info(hedge_symbol)
        if si is None:
            return None, f"Symbol {hedge_symbol} im Hedge-Terminal nicht gefunden"
        step = float(si.volume_step or 0.01)
        lots = round(round(lots / step) * step, 8)
        lots = max(float(si.volume_min), min(lots, float(si.volume_max)))
        if lots > max_lots:
            return None, f"Sicherheitsgrenze: {lots} > max_lots_per_hedge {max_lots}"
        return lots, None

    def send(request, what):
        if mode == "dryrun":
            log("writer", f"DRYRUN — wuerde senden: {what}")
            return None
        res = mt5.order_send(request)
        if res is None:
            log("writer", f"❌ order_send lieferte None ({mt5.last_error()}) für {what}")
            return None
        if res.retcode != mt5.TRADE_RETCODE_DONE:
            log("writer", f"❌ {what} abgelehnt: retcode={res.retcode} {getattr(res,'comment','')}")
            return None
        log("writer", f"✅ {what} · deal={res.deal} order={res.order}")
        return res

    def open_hedge(ev):
        m_symbol = ev["symbol"]
        h_symbol = symbol_map.get(m_symbol)
        if not h_symbol:
            log("writer", f"⚠ Kein Symbol-Mapping für '{m_symbol}' — übersprungen (in config symbol_map ergänzen).")
            return
        lots, err = calc_lots(h_symbol, ev["volume"])
        if err:
            log("writer", f"⚠ {err} — übersprungen.")
            return
        # REVERSE: Master BUY (0) -> Hedge SELL, Master SELL (1) -> Hedge BUY
        h_type = mt5.ORDER_TYPE_SELL if ev["type"] == 0 else mt5.ORDER_TYPE_BUY
        side = "SELL" if h_type == mt5.ORDER_TYPE_SELL else "BUY"
        if not mt5.symbol_select(h_symbol, True):
            log("writer", f"⚠ symbol_select({h_symbol}) fehlgeschlagen")
        tick = mt5.symbol_info_tick(h_symbol)
        price = (tick.bid if h_type == mt5.ORDER_TYPE_SELL else tick.ask) if tick else 0.0
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": h_symbol,
            "volume": lots,
            "type": h_type,
            "price": price,
            "deviation": deviation,
            "magic": magic,
            "comment": f"{prefix}-{ev['ticket']}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }
        what = f"HEDGE OPEN {side} {lots} {h_symbol} (Master #{ev['ticket']} {ev['volume']} {m_symbol})"
        res = send(req, what)
        if res is not None:
            mapping.update(hedge_positions_by_master())

    def close_hedge(master_ticket, portion=1.0):
        h = mapping.get(master_ticket) or hedge_positions_by_master().get(master_ticket)
        if not h:
            log("writer", f"ℹ Kein Hedge zu Master #{master_ticket} gefunden (schon zu / nie gesetzt).")
            return
        vol = h["volume"] if portion >= 1.0 else round(h["volume"] * portion, 2)
        si = mt5.symbol_info(h["symbol"])
        if si:
            step = float(si.volume_step or 0.01)
            vol = round(round(vol / step) * step, 8)
            vol = max(float(si.volume_min), min(vol, h["volume"]))
        close_type = mt5.ORDER_TYPE_BUY if h["type"] == 1 else mt5.ORDER_TYPE_SELL
        tick = mt5.symbol_info_tick(h["symbol"])
        price = (tick.ask if close_type == mt5.ORDER_TYPE_BUY else tick.bid) if tick else 0.0
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": h["symbol"],
            "volume": vol,
            "type": close_type,
            "position": h["ticket"],
            "price": price,
            "deviation": deviation,
            "magic": magic,
            "comment": f"{prefix}c-{master_ticket}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }
        what = f"HEDGE CLOSE {vol} {h['symbol']} (Master #{master_ticket}{'' if portion>=1 else f', anteilig {portion:.2%}'})"
        res = send(req, what)
        if res is not None or mode == "dryrun":
            if portion >= 1.0:
                mapping.pop(master_ticket, None)
            else:
                mapping.update(hedge_positions_by_master())

    adopt = bool(cfg.get("adopt_existing_master_positions", False))
    started = time.time()

    while not stop_ev.is_set():
        try:
            ev = in_q.get(timeout=1.0)
        except queue.Empty:
            continue

        t = ev.get("type")
        if t == "hello":
            tm = {0: "DEMO", 1: "CONTEST", 2: "ECHTGELD"}.get(ev.get("trade_mode"), "?")
            log("reader", f"Master-Konto {ev['login']} @ {ev['server']} · {tm}")
        elif t == "fatal":
            log(ev.get("who", "?"), f"FATAL {ev['msg']}")
            break
        elif t == "error":
            log(ev.get("who", "?"), f"Fehler: {ev['msg']}")
        elif t == "open":
            # Positionen, die beim Start schon offen waren, nicht ungefragt hedgen
            if not adopt and time.time() - started < 3.0:
                log("writer", f"⏭ Master #{ev['ticket']} war beim Start schon offen — nicht übernommen "
                              f"(adopt_existing_master_positions=true, wenn gewünscht).")
                continue
            log("reader", f"🆕 Master-Position: {'BUY' if ev['type']==0 else 'SELL'} {ev['volume']} {ev['symbol']} #{ev['ticket']}")
            open_hedge(ev)
        elif t == "partial":
            before, now = ev["volume_before"], ev["volume_now"]
            portion = max(0.0, min(1.0, (before - now) / before)) if before > 0 else 0.0
            log("reader", f"↘ Master #{ev['ticket']} teil-geschlossen: {before} → {now} ({portion:.2%})")
            close_hedge(ev["ticket"], portion)
        elif t == "close":
            log("reader", f"🔚 Master #{ev['ticket']} geschlossen → Hedge zu")
            close_hedge(ev["ticket"], 1.0)
        elif t == "bye":
            break

    mt5.shutdown()
    log("writer", "beendet")


# ── Start ──────────────────────────────────────────────────────────────────────
def main():
    cfg = load_config()
    mode = str(cfg.get("mode", "dryrun")).lower()
    if mode not in ("dryrun", "demo", "live"):
        sys.exit(f"mode '{mode}' ungültig — erlaubt: dryrun | demo | live")

    print("=" * 70)
    print(f" MT5-Hedge-Copier (Testversion) · Modus: {mode.upper()}")
    if mode == "dryrun":
        print(" DRYRUN: es wird KEINE Order gesendet — nur protokolliert.")
    print(f" Multiplikator: {cfg.get('multiplier')} · Symbol-Mapping: {cfg.get('symbol_map')}")
    print(" Duplikum/app.py/prophos.html werden nicht angefasst.")
    print("=" * 70)

    q = mp.Queue()
    stop = mp.Event()
    pr = mp.Process(target=reader_proc, args=(cfg, q, stop), daemon=True)
    pw = mp.Process(target=writer_proc, args=(cfg, q, stop), daemon=True)
    pr.start(); pw.start()
    try:
        while pr.is_alive() and pw.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStoppe…")
    finally:
        stop.set()
        pr.join(timeout=5); pw.join(timeout=5)
        for p in (pr, pw):
            if p.is_alive():
                p.terminate()
    print("Copier beendet.")


if __name__ == "__main__":
    mp.freeze_support()
    main()
