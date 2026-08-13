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


def norm_vol(si, vol):
    """Volumen auf den Broker-Raster bringen: volume_step runden, auf min/max klemmen,
    auf die Stellenzahl des Steps normalisieren (sonst 10014 invalid volume)."""
    step = float(si.get("volume_step") or 0.01)
    v = round(round(vol / step) * step, 8)
    st = f"{step:.8f}".rstrip("0")
    dec = len(st.split(".")[1]) if "." in st else 0
    v = round(v, dec)
    if v < float(si.get("volume_min") or 0.01) - TOL:
        return 0.0
    return min(v, float(si.get("volume_max") or 1e9))


def plan_actions(positions, hedges, *, multiplier, symbol_map, max_lots, sym_info,
                 skip_idents=frozenset()):
    """REIN RECHNENDE Funktion — keine MT5-Aufrufe, deshalb testbar (siehe selftest.py).

    positions: Master-Positionen aus dem Snapshot
               [{ident, symbol, type(0=BUY/1=SELL), volume, contract_size}, …]
    hedges:    aktueller Hedge-Bestand, {ident: [{ticket, symbol, type, volume}, …]}
    sym_info:  callable(symbol) -> {volume_step, volume_min, volume_max, trade_contract_size} | None

    Rückgabe: (actions, warnings)
      actions: [{"kind":"open", ident, symbol, hedge_type, volume},
                {"kind":"close", ident, ticket, symbol, volume}]

    Prinzip: SOLL-Volumen pro Master-Position berechnen und den Ist-Bestand darauf
    bringen. Dadurch sind Teil-Schließungen, verpasste Events und Recovery nach einem
    Neustart derselbe Codepfad.
    """
    actions, warnings = [], []
    desired = {}

    for mp in positions:
        if mp["ident"] in skip_idents:
            continue
        hsym = symbol_map.get(mp["symbol"])
        if not hsym:
            warnings.append(f"Kein Symbol-Mapping für '{mp['symbol']}'")
            continue
        si = sym_info(hsym)
        if si is None:
            warnings.append(f"Symbol {hsym} im Hedge-Terminal nicht gefunden")
            continue
        # Exposure statt Lots: derselbe Index hat je Broker andere Kontraktgrößen
        m_cs = float(mp.get("contract_size") or 0) or 1.0
        h_cs = float(si.get("trade_contract_size") or 0) or 1.0
        v = norm_vol(si, mp["volume"] * multiplier * (m_cs / h_cs))
        if v > max_lots:
            warnings.append(f"Sicherheitsgrenze: {v} > max_lots_per_hedge {max_lots} ({hsym})")
            continue
        if v <= TOL:
            warnings.append(f"Berechnetes Volumen unter Mindest-Lot ({hsym})")
            continue
        desired[mp["ident"]] = {"symbol": hsym, "type": mp["type"], "volume": v}

    # Ist auf Soll bringen
    for ident, d in desired.items():
        have = sum(h["volume"] for h in hedges.get(ident, []))
        if have < d["volume"] - TOL:
            si = sym_info(d["symbol"])
            missing = norm_vol(si, d["volume"] - have)
            if missing > TOL:
                actions.append({"kind": "open", "ident": ident, "symbol": d["symbol"],
                                "hedge_type": 1 if d["type"] == 0 else 0,  # REVERSE
                                "volume": missing})
        elif have > d["volume"] + TOL:
            excess = have - d["volume"]
            for h in sorted(hedges.get(ident, []), key=lambda x: x["volume"]):
                if excess <= TOL:
                    break
                si = sym_info(h["symbol"])
                take = norm_vol(si, min(h["volume"], excess))
                if take > TOL:
                    actions.append({"kind": "close", "ident": ident, "ticket": h["ticket"],
                                    "symbol": h["symbol"], "volume": take})
                    excess -= take

    # Master-Position weg -> zugehörige Hedges komplett schließen.
    # WICHTIG (Bug gefunden 13.08.2026): Es wird gegen die im Snapshot VORHANDENEN
    # Positionen geprüft, nicht gegen `desired`. Sonst würde eine übersprungene
    # Startup-Position (skip_idents) als "Master weg" gelten und ihr bestehender Hedge
    # sofort geschlossen — nach einem Copier-Neustart wäre eine laufende Position
    # unbemerkt ungehedged. Übersprungene Positionen werden hier bewusst NICHT
    # angefasst; ihr Hedge wird erst geschlossen, wenn der Master wirklich zugeht.
    present = {p["ident"] for p in positions}
    for ident, hs in hedges.items():
        if ident in desired or ident in present:
            continue
        for h in hs:
            actions.append({"kind": "close", "ident": ident, "ticket": h["ticket"],
                            "symbol": h["symbol"], "volume": h["volume"]})

    return actions, warnings


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

    def sym_info(symbol):
        """Symbol-Daten fuer plan_actions() — auf dem Hedge-Terminal abgefragt."""
        si = mt5.symbol_info(symbol)
        if si is None:
            mt5.symbol_select(symbol, True)
            si = mt5.symbol_info(symbol)
        if si is None:
            return None
        return {"volume_step": float(si.volume_step or 0.01),
                "volume_min": float(si.volume_min or 0.01),
                "volume_max": float(si.volume_max or 1e9),
                "trade_contract_size": float(si.trade_contract_size or 1.0)}

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
    # Dryrun führt einen VIRTUELLEN Hedge-Bestand: sonst würde jede Aktion bei jedem
    # Poll neu geplant und geloggt (0,5s-Spam), weil real nie ein Hedge entsteht.
    virtual = {}
    virtual_ticket = -1
    # Reopen-Guard: Falls ein Hedge nicht wiedererkannt wird (z.B. Broker hat den
    # Kommentar verändert), würde der Executor alle 0,5s nachlegen. Nach
    # OPEN_MAX_TRIES Versuchen pro Master-Position wird gestoppt und laut gewarnt.
    OPEN_COOLDOWN = 3.0
    OPEN_MAX_TRIES = 3
    open_last = {}
    open_tries = {}
    blocked = set()
    last_snap_change = time.time()
    last_seq_seen = None
    stale_warned = False

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

            # Snapshot-Timeout: aktualisiert das EA die Datei nicht mehr, laeuft es nicht.
            if snap["seq"] != last_seq_seen:
                last_seq_seen = snap["seq"]
                last_snap_change = time.time()
                stale_warned = False
            elif not stale_warned and time.time() - last_snap_change > 15:
                log("⚠ Snapshot seit 15s unveraendert — laeuft das Lese-EA im Master-Terminal noch? "
                    "(Chart offen, Algo-Handel, Reiter 'Experten' pruefen)")
                stale_warned = True

            current = virtual if mode == "dryrun" else hedges_by_ident()
            # Dieselbe Funktion, die selftest.py prueft — Test und Betrieb rechnen identisch.
            actions, warns = plan_actions(
                snap["positions"], current,
                multiplier=multiplier, symbol_map=symbol_map, max_lots=max_lots,
                sym_info=sym_info, skip_idents=(startup_idents or frozenset()))

            for w in warns:
                if w not in warned_missing:
                    log(f"⚠ {w} — uebersprungen.")
                    warned_missing.add(w)

            for a in actions:
                ident = a["ident"]
                if a["kind"] == "open":
                    if ident in blocked:
                        continue
                    if time.time() - open_last.get(ident, 0) < OPEN_COOLDOWN:
                        continue  # zu kurz her — Broker/Terminal Zeit geben
                    open_tries[ident] = open_tries.get(ident, 0) + 1
                    if open_tries[ident] > OPEN_MAX_TRIES:
                        blocked.add(ident)
                        log(f"⛔ Master-Pos {ident}: Hedge wurde nach {OPEN_MAX_TRIES} Versuchen nicht "
                            f"wiedererkannt — weitere Versuche gestoppt (Schutz gegen Mehrfach-Hedge). "
                            f"Bitte im Hedge-Terminal pruefen.")
                        continue
                    open_last[ident] = time.time()
                    ok = open_hedge(ident, a["symbol"],
                                    0 if a["hedge_type"] == 1 else 1,  # master-Typ zurueckrechnen
                                    a["volume"])
                    if ok and mode == "dryrun":
                        virtual.setdefault(ident, []).append({
                            "ticket": virtual_ticket, "volume": a["volume"],
                            "symbol": a["symbol"], "type": a["hedge_type"]})
                        virtual_ticket -= 1
                else:
                    if mode == "dryrun":
                        hs = virtual.get(ident, [])
                        rest = a["volume"]
                        for h in list(hs):
                            if rest <= TOL:
                                break
                            take = min(h["volume"], rest)
                            h["volume"] = round(h["volume"] - take, 8)
                            rest -= take
                            if h["volume"] <= TOL:
                                hs.remove(h)
                        if not hs:
                            virtual.pop(ident, None)
                        log(f"DRYRUN — wuerde senden: HEDGE CLOSE {a['volume']} {a['symbol']} (Master-Pos {ident})")
                        open_tries.pop(ident, None); open_last.pop(ident, None); blocked.discard(ident)
                    else:
                        open_pos = next((h for h in current.get(ident, []) if h["ticket"] == a["ticket"]), None)
                        if open_pos and close_part(open_pos, a["volume"]):
                            open_tries.pop(ident, None); open_last.pop(ident, None); blocked.discard(ident)

            time.sleep(poll)
    except KeyboardInterrupt:
        log("Gestoppt.")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
