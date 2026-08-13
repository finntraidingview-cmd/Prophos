#!/usr/bin/env python3
"""
Prophos MT5-Hedge-Executor — eigenstaendige Testversion, getrennt vom Duplikum-Setup.

ARCHITEKTUR (nach Technik-Recherche 13.08.2026 bewusst so gewaehlt):

  PROP-Terminal              gemeinsamer Ordner        LIVE-Terminal
  ProphosHedgeReader.mq5  →  prophos_master.csv    →   dieses Programm
  (nur lesend, kein                                    (haengt NUR hier,
   OrderSend im Code)                                   setzt den Hedge)

Warum so und nicht mit Python auf beiden Seiten: Der `path=`-Parameter von
mt5.initialize() greift laut mehreren dokumentierten Faellen nicht zuverlaessig —
man kann an der FALSCHEN Terminal-Installation landen (Fehler -10003). Ein Python-
Prozess, der versehentlich am Prop-Terminal haengt und dort Orders sendet, ist das
schlimmste denkbare Szenario. Deshalb: Python haengt an GENAU EINEM Terminal (dem
Live-Konto), die Master-Seite ist ein reines Lese-EA. Zusaetzlich wird nach dem
Verbinden hart geprueft, ob wirklich das erwartete Konto dranhaengt (siehe
verify_attached()) — bei Abweichung Abbruch, ohne eine einzige Order.

DEKLARATIVES MODELL statt Event-Copier: Der Reader publiziert den KOMPLETTEN
Positionsstand. Dieses Programm berechnet daraus pro Master-Position ein
Soll-Volumen und bringt den Hedge darauf. Damit sind Teil-Schliessungen,
verpasste Events, Teilfuellungen und Crash-Recovery derselbe Codepfad statt vier
Sonderfaelle.

DREI STUFEN (config "mode"):
  1. dryrun (Default) — nur protokollieren, KEINE Order. Zum Vergleich mit dem
     laufenden Duplikum.
  2. demo — echte Orders, aber nur wenn das Live-Terminal auf einem DEMO-Konto ist.
  3. live — echtes Geld. Vorher Duplikum fuer dieses Paar abschalten.

Nicht gegen echte Konten getestet — Stufe 1 und 2 sind genau dafuer da.
"""

import json
import os
import sys
import time
from datetime import datetime

TOL = 1e-6


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_config():
    p = os.environ.get("COPIER_CONFIG") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if not os.path.exists(p):
        sys.exit(f"config.json nicht gefunden ({p}) — config.example.json kopieren und ausfuellen.")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Snapshot des Prop-Terminals lesen ───────────────────────────────────────────
def read_snapshot(path):
    """Gibt (seq, login, margin_mode, [positions]) oder None bei unvollstaendiger Datei."""
    try:
        with open(path, "r", encoding="ascii", errors="replace") as f:
            lines = [l.strip() for l in f if l.strip()]
    except FileNotFoundError:
        return None
    except OSError:
        return None
    if not lines or not lines[0].startswith("PROPHOS1;"):
        return None

    head = lines[0].split(";")
    try:
        seq = int(head[1]); login = int(head[3]); server = head[4]
        margin_mode = int(head[5]); count = int(head[6])
    except (IndexError, ValueError):
        return None

    positions = []
    footer_ok = False
    for l in lines[1:]:
        if l.startswith("P;"):
            f_ = l.split(";")
            try:
                positions.append({
                    "ident": int(f_[1]), "symbol": f_[2], "type": int(f_[3]),
                    "volume": float(f_[4]), "contract_size": float(f_[5]),
                })
            except (IndexError, ValueError):
                return None
        elif l.startswith("END;"):
            f_ = l.split(";")
            try:
                footer_ok = int(f_[1]) == seq and int(f_[2]) == len(positions)
            except (IndexError, ValueError):
                return None
    if not footer_ok or len(positions) != count:
        return None  # halb geschriebene Datei → diesen Tick ueberspringen
    return {"seq": seq, "login": login, "server": server, "margin_mode": margin_mode, "positions": positions}


def main():
    cfg = load_config()
    mode = str(cfg.get("mode", "dryrun")).lower()
    if mode not in ("dryrun", "demo", "live"):
        sys.exit(f"mode '{mode}' ungueltig — erlaubt: dryrun | demo | live")

    import MetaTrader5 as mt5

    snap_name = cfg.get("snapshot_file", "prophos_master.csv")
    common = cfg.get("common_files_dir") or os.path.join(
        os.environ.get("APPDATA", ""), "MetaQuotes", "Terminal", "Common", "Files")
    snap_path = os.path.join(common, snap_name)

    prefix = cfg.get("comment_prefix", "PH")
    magic = int(cfg.get("magic", 770001))
    symbol_map = cfg.get("symbol_map", {})
    multiplier = float(cfg.get("multiplier", 1.0))
    max_lots = float(cfg.get("max_lots_per_hedge", 5.0))
    deviation = int(cfg.get("deviation_points", 30))
    poll = float(cfg.get("poll_interval", 0.5))
    adopt = bool(cfg.get("adopt_existing_master_positions", False))
    exp_hedge_login = cfg.get("hedge_expected_login")
    exp_master_login = cfg.get("master_expected_login")

    print("=" * 72)
    print(f" Prophos MT5-Hedge-Executor · Modus {mode.upper()}")
    if mode == "dryrun":
        print(" DRYRUN — es wird KEINE Order gesendet, nur protokolliert.")
    print(f" Snapshot: {snap_path}")
    print(f" Multiplikator {multiplier} · Mapping {symbol_map}")
    print(" Duplikum / app.py / prophos.html werden nicht angefasst.")
    print("=" * 72)

    # ── An das LIVE-Terminal haengen ────────────────────────────────────────────
    init_kw = {}
    if cfg.get("hedge_terminal_path"):
        init_kw["path"] = cfg["hedge_terminal_path"]
    if cfg.get("hedge_portable"):
        init_kw["portable"] = True
    # BEWUSST kein login/password/server: initialize() nutzt den im Terminal
    # eingeloggten Account. mt5.login() wird NIE aufgerufen — das wuerde ein
    # Terminal auf ein anderes Konto umschalten.
    if not mt5.initialize(**init_kw):
        sys.exit(f"initialize() fehlgeschlagen: {mt5.last_error()} — laeuft das Live-Terminal?")

    ti = mt5.terminal_info()
    ai = mt5.account_info()
    if ti is None or ai is None:
        mt5.shutdown()
        sys.exit("terminal_info()/account_info() leer — Terminal offen und eingeloggt?")

    # ── HARTE PRUEFUNG: haengen wir am richtigen Terminal/Konto? ────────────────
    # Ohne diese Pruefung koennte ein nicht greifender path=-Parameter dazu
    # fuehren, dass wir am PROP-Terminal haengen und dort Orders senden.
    log(f"Verbunden mit Terminal: {ti.path}")
    log(f"Konto {ai.login} @ {ai.server} · {ai.company}")
    problems = []
    if exp_hedge_login and int(exp_hedge_login) != int(ai.login):
        problems.append(f"Erwartet war Hedge-Konto {exp_hedge_login}, verbunden ist aber {ai.login}")
    if exp_master_login and int(exp_master_login) == int(ai.login):
        problems.append(f"GEFAHR: verbunden mit dem MASTER-Konto {ai.login} — hier darf nichts platziert werden")
    if cfg.get("hedge_terminal_path"):
        want = os.path.normcase(os.path.dirname(os.path.abspath(cfg["hedge_terminal_path"])))
        got = os.path.normcase(os.path.abspath(str(ti.path)))
        if want not in got and got not in want:
            problems.append(f"Terminal-Pfad weicht ab: erwartet '{want}', verbunden '{got}' "
                            f"(bekanntes MT5-Problem: path= greift nicht immer)")
    if problems:
        for p in problems:
            log("⛔ " + p)
        log("⛔ ABBRUCH — keine Order gesendet.")
        mt5.shutdown()
        sys.exit(1)

    is_real = int(ai.trade_mode) == 2
    log(f"Hedge-Konto ist {'ECHTGELD' if is_real else 'DEMO/CONTEST'}")
    if mode == "demo" and is_real:
        log("⛔ ABBRUCH: Modus 'demo', aber das Hedge-Terminal haengt an einem ECHTGELD-Konto.")
        mt5.shutdown(); sys.exit(1)

    # Hedging-Modus ist Pflicht: im Netting-Modus gibt es nur EINE Position pro
    # Symbol, damit bricht die Zuordnung Master-Position ↔ Hedge-Position.
    if int(ai.margin_mode) != int(mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING):
        log("⛔ ABBRUCH: Das Hedge-Konto ist NICHT im Hedging-Modus (Netting). "
            "Im Netting-Modus laesst sich pro Symbol nur eine Position halten — "
            "Zuordnung und Teil-Schliessungen brechen. Hedging-Konto verwenden.")
        mt5.shutdown(); sys.exit(1)

    if mode != "dryrun" and not ti.trade_allowed:
        log("⛔ ABBRUCH: 'Algo Trading' ist im Live-Terminal nicht aktiv "
            "(Extras → Optionen → Expert Advisors). Aus Python nicht schaltbar.")
        mt5.shutdown(); sys.exit(1)

    # ── Hilfsfunktionen ─────────────────────────────────────────────────────────
    def hedges_by_ident():
        """Aktueller Hedge-Bestand, gruppiert nach Master-Identifier.
        Primaerfilter ist die MAGIC (broker-stabil), der Kommentar traegt die
        Zuordnung — Kommentare koennen vom Broker ergaenzt werden, deshalb wird
        nur der Praefix gesucht statt auf Gleichheit geprueft."""
        out = {}
        for p in (mt5.positions_get() or []):
            if int(getattr(p, "magic", 0)) != magic:
                continue
            c = str(getattr(p, "comment", "") or "")
            i = c.find(prefix + "-")
            if i < 0:
                continue
            tok = c[i + len(prefix) + 1:]
            digits = ""
            for ch in tok:
                if ch.isdigit():
                    digits += ch
                else:
                    break
            if not digits:
                continue
            out.setdefault(int(digits), []).append({
                "ticket": int(p.ticket), "volume": float(p.volume),
                "symbol": str(p.symbol), "type": int(p.type),
            })
        return out

    def norm_volume(sym, vol):
        si = mt5.symbol_info(sym)
        if si is None:
            return None, f"Symbol {sym} im Hedge-Terminal nicht gefunden"
        step = float(si.volume_step or 0.01)
        v = round(round(vol / step) * step, 8)
        # auf die Stellenzahl des Steps normalisieren (sonst 10014 invalid volume)
        dec = max(0, len(f"{step:.8f}".rstrip("0").split(".")[1]) if "." in f"{step:.8f}".rstrip("0") else 0)
        v = round(v, dec)
        if v < float(si.volume_min) - TOL:
            return 0.0, None
        v = min(v, float(si.volume_max))
        return v, None

    def target_volume(mpos, hedge_sym):
        """Soll-Volumen ueber EXPOSURE, nicht ueber Lots: derselbe Index hat bei
        verschiedenen Brokern unterschiedliche Kontraktgroessen."""
        si = mt5.symbol_info(hedge_sym)
        if si is None:
            return None, f"Symbol {hedge_sym} nicht gefunden"
        m_cs = float(mpos.get("contract_size") or 0) or 1.0
        h_cs = float(si.trade_contract_size or 0) or 1.0
        raw = mpos["volume"] * multiplier * (m_cs / h_cs)
        v, err = norm_volume(hedge_sym, raw)
        if err:
            return None, err
        if v > max_lots:
            return None, f"Sicherheitsgrenze: {v} > max_lots_per_hedge {max_lots}"
        return v, None

    def send(req, what):
        if mode == "dryrun":
            log(f"DRYRUN — wuerde senden: {what}")
            return True
        r = mt5.order_send(req)
        if r is None:
            log(f"❌ order_send None ({mt5.last_error()}) — {what}")
            return False
        if r.retcode != mt5.TRADE_RETCODE_DONE:
            log(f"❌ abgelehnt retcode={r.retcode} {getattr(r,'comment','')} — {what}")
            return False
        log(f"✅ {what} · deal={r.deal}")
        return True

    def filling_for(sym):
        name = str(cfg.get("filling", "auto")).upper()
        if name == "IOC":
            return mt5.ORDER_FILLING_IOC
        if name == "FOK":
            return mt5.ORDER_FILLING_FOK
        si = mt5.symbol_info(sym)
        mask = int(getattr(si, "filling_mode", 0) or 0)
        if mask & 2:
            return mt5.ORDER_FILLING_IOC
        if mask & 1:
            return mt5.ORDER_FILLING_FOK
        return mt5.ORDER_FILLING_RETURN

    def open_hedge(ident, sym, mtype, vol):
        h_type = mt5.ORDER_TYPE_SELL if mtype == 0 else mt5.ORDER_TYPE_BUY   # REVERSE
        side = "SELL" if h_type == mt5.ORDER_TYPE_SELL else "BUY"
        mt5.symbol_select(sym, True)
        tick = mt5.symbol_info_tick(sym)
        price = (tick.bid if h_type == mt5.ORDER_TYPE_SELL else tick.ask) if tick else 0.0
        # Bewusst KEIN SL/TP auf dem Hedge: bei einem Hedge wuerde ein eigener
        # Stop die Absicherung vorzeitig aufloesen.
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": vol, "type": h_type,
               "price": price, "deviation": deviation, "magic": magic,
               "comment": f"{prefix}-{ident}", "type_time": mt5.ORDER_TIME_GTC,
               "type_filling": filling_for(sym)}
        return send(req, f"HEDGE OPEN {side} {vol} {sym} (Master-Pos {ident})")

    def close_part(h, vol):
        ctype = mt5.ORDER_TYPE_BUY if h["type"] == 1 else mt5.ORDER_TYPE_SELL
        tick = mt5.symbol_info_tick(h["symbol"])
        price = (tick.ask if ctype == mt5.ORDER_TYPE_BUY else tick.bid) if tick else 0.0
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": h["symbol"], "volume": vol,
               "type": ctype, "position": h["ticket"], "price": price,
               "deviation": deviation, "magic": magic, "comment": f"{prefix}c",
               "type_time": mt5.ORDER_TIME_GTC, "type_filling": filling_for(h["symbol"])}
        return send(req, f"HEDGE CLOSE {vol} {h['symbol']} (Ticket {h['ticket']})")

    # ── Hauptschleife: Soll/Ist abgleichen ──────────────────────────────────────
    log("Warte auf Snapshot des Prop-Terminals…")
    seen_seq = None
    startup_idents = None
    warned_missing = set()

    try:
        while True:
            snap = read_snapshot(snap_path)
            if snap is None:
                time.sleep(poll)
                continue

            if exp_master_login and int(exp_master_login) != int(snap["login"]):
                log(f"⛔ Snapshot kommt von Konto {snap['login']}, erwartet war {exp_master_login} — ignoriert.")
                time.sleep(poll)
                continue

            if seen_seq is None:
                log(f"✓ Snapshot verbunden — Master-Konto {snap['login']} @ {snap['server']}, "
                    f"{len(snap['positions'])} offene Position(en)")
                if not adopt:
                    startup_idents = {p["ident"] for p in snap["positions"]}
                    if startup_idents:
                        log(f"⏭ {len(startup_idents)} Position(en) waren beim Start schon offen — "
                            f"werden nicht nachtraeglich gehedged (adopt_existing_master_positions).")
                else:
                    startup_idents = set()
            seen_seq = snap["seq"]

            current = hedges_by_ident()
            desired = {}
            for mp in snap["positions"]:
                if startup_idents and mp["ident"] in startup_idents:
                    continue
                hsym = symbol_map.get(mp["symbol"])
                if not hsym:
                    if mp["symbol"] not in warned_missing:
                        log(f"⚠ Kein Symbol-Mapping fuer '{mp['symbol']}' — uebersprungen "
                            f"(in config symbol_map ergaenzen).")
                        warned_missing.add(mp["symbol"])
                    continue
                v, err = target_volume(mp, hsym)
                if err:
                    if mp["symbol"] not in warned_missing:
                        log(f"⚠ {err} — uebersprungen.")
                        warned_missing.add(mp["symbol"])
                    continue
                desired[mp["ident"]] = {"symbol": hsym, "type": mp["type"], "volume": v}

            # 1) Soll vorhanden → Ist darauf bringen
            for ident, d in desired.items():
                have = sum(h["volume"] for h in current.get(ident, []))
                if d["volume"] <= TOL:
                    continue
                if have < d["volume"] - TOL:
                    missing, err = norm_volume(d["symbol"], d["volume"] - have)
                    if err or not missing:
                        continue
                    open_hedge(ident, d["symbol"], d["type"], missing)
                elif have > d["volume"] + TOL:
                    excess = have - d["volume"]
                    for h in sorted(current.get(ident, []), key=lambda x: x["volume"]):
                        if excess <= TOL:
                            break
                        take = min(h["volume"], excess)
                        v, err = norm_volume(h["symbol"], take)
                        if err or not v:
                            continue
                        if close_part(h, v):
                            excess -= v

            # 2) Master-Position weg → zugehoerige Hedges schliessen
            for ident, hs in current.items():
                if ident in desired:
                    continue
                for h in hs:
                    close_part(h, h["volume"])

            time.sleep(poll)
    except KeyboardInterrupt:
        log("Gestoppt.")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
