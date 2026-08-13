#!/usr/bin/env python3
"""
Prophos MT5-Hedge-Executor — EIN Prozess bedient ALLE Master-Konten dieses PCs.

ARCHITEKTUR (Umbau 13.08.2026 nach Multi-Instanz-Audit):

  MASTER-Terminal 1 ── prophos_master.csv  ──┐
  MASTER-Terminal 2 ── prophos_master2.csv ──┼──►  dieses Programm  ──►  HEDGE-Terminal
  MASTER-Terminal N ── prophos_masterN.csv ──┘     (ein Prozess)         (ein Live-Konto)

Warum EIN Prozess statt einem Prozess pro Master: Das Audit vom 13.08.2026 hat
gezeigt, dass zwei getrennte Copier auf demselben Hedge-Konto eine ganze Klasse
von Fehlern erzeugen — geteilte magic → sie schliessen sich gegenseitig die
Hedges; geteilte Snapshot-Datei → jeder hedged den fremden Master; kein
Prozess-Lock → ein Doppelstart pendelt das Konto auf. Ein einzelner Prozess kann
sich nicht selbst in die Quere kommen: der Hedge-Bestand wird EINMAL pro Tick
gelesen und strikt nach magic pro Master partitioniert.

Jede config*.json im Ordner ist ein Master. Pro Master MUESSEN eindeutig sein
(wird beim Start erzwungen, sonst Abbruch):
  · magic            — der Primaerfilter, an dem der Copier SEINE Hedges erkennt
  · snapshot_file    — die Datei des Lese-EAs (== InpFileName im Master-Terminal)
  · master_expected_login — ab zwei Mastern Pflicht, sonst ist der einzige
    Schutz gegen einen vertauschten Snapshot stumm abgeschaltet

Master-Seite bleibt ein reines Lese-EA (ProphosHedgeReader.mq5) — Python haengt
ausschliesslich am Hedge-Terminal. Begruendung und alle Sicherheitsmechanismen:
siehe Kommentare im Code und README.

DREI STUFEN pro Master (config "mode"):
  1. dryrun (Default) — nur protokollieren, KEINE Order.
  2. demo — echte Orders, aber nur wenn das Hedge-Terminal auf einem DEMO-Konto ist.
  3. live — echtes Geld. Vorher Duplikum fuer dieses Paar abschalten.
"""

import json
import os
import re
import sys
import time
from datetime import datetime

TOL = 1e-6

# Dieselbe Namensregel wie im Panel (panel.py) — bewusst streng, damit
# Explorer-Kopien wie "config - Kopie.json" oder "config (2).json" NICHT als
# Instanz durchgehen (Audit-Fund 13.08.2026: solche Karten sahen echt aus,
# steuerten aber nichts).
CONFIG_RE = re.compile(r"config(?:[-_][A-Za-z0-9]{1,24})?\.json", re.I)
TEMPLATES = ("config.example.json", "config.fusion-test.json")


_LOG_RING = []


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    _LOG_RING.append(line)
    if len(_LOG_RING) > 200:
        del _LOG_RING[:-200]


def write_status(path, data):
    """Zustand als status-<name>.json neben der config ablegen (Panel/Prophos lesen sie).
    Erst in eine .tmp schreiben und dann umbenennen, damit nie eine halb
    geschriebene Datei gelesen wird. pid/started_at dienen als Instanz-Sperre."""
    try:
        data = dict(data)
        data["log"] = _LOG_RING[-60:]
        data["pid"] = os.getpid()
        data["updated_at"] = datetime.now().isoformat(timespec="seconds")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except Exception as e:
        print(f"[status] konnte {os.path.basename(path)} nicht schreiben: {type(e).__name__}: {e}", flush=True)


def discover_configs(folder):
    """Alle Master-Configs des Ordners. COPIER_CONFIG (voller Pfad oder Name) engt
    auf genau eine ein — fuer Sonderfaelle; der Normalfall ist die ganze Flotte."""
    override = (os.environ.get("COPIER_CONFIG") or "").strip()
    if override:
        p = override if os.path.isabs(override) else os.path.join(folder, override)
        base = os.path.basename(p)
        if not CONFIG_RE.fullmatch(base) or os.path.normcase(os.path.dirname(os.path.abspath(p))) != os.path.normcase(os.path.abspath(folder)):
            # Audit-Fund: ein freier Pfad liesse den Status auf status.json
            # zurueckfallen und zwei Instanzen wuerden sich dieselbe Datei teilen.
            sys.exit(f"COPIER_CONFIG muss eine config<-name>.json im Copier-Ordner sein, nicht '{override}'.")
        return [p]
    out = []
    for fn in sorted(os.listdir(folder)):
        if fn in TEMPLATES or fn.endswith(".tmp"):
            continue
        if CONFIG_RE.fullmatch(fn):
            out.append(os.path.join(folder, fn))
    return out


def status_path_for(cfg_path):
    base = os.path.basename(cfg_path)
    # discover_configs() garantiert, dass "config" am Anfang steht — kein Fallback
    # auf einen gemeinsamen Namen mehr (Audit-Fund: der alte else-Zweig liess zwei
    # Instanzen dieselbe status.json ueberschreiben).
    return os.path.join(os.path.dirname(os.path.abspath(cfg_path)),
                        re.sub(r"^config", "status", base, count=1, flags=re.I))


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_fleet(cfgs):
    """REIN RECHNENDE Pruefung der Flotten-Config (testbar in selftest.py).
    cfgs: [{"_file": name, ...config-Inhalt...}]  →  (fehler, warnungen)

    Erzwingt die Eindeutigkeit, an der beim Multi-Instanz-Audit 13.08.2026 alle
    kritischen Funde hingen: gleiche magic → Copier schliessen sich gegenseitig
    die Hedges; gleiche snapshot_file → jeder hedged den fremden Master;
    master_expected_login 0 → der einzige Schutz dagegen ist stumm aus."""
    errors, warnings = [], []
    by_magic, by_snap, by_prefix = {}, {}, {}
    hedge_pairs = set()
    for c in cfgs:
        f = c.get("_file", "?")
        magic = int(c.get("magic", 770001))
        snap = str(c.get("snapshot_file", "prophos_master.csv"))
        prefix = str(c.get("comment_prefix", "PH"))
        by_magic.setdefault(magic, []).append(f)
        by_snap.setdefault(snap.lower(), []).append(f)
        by_prefix.setdefault(prefix, []).append(f)
        hedge_pairs.add((str(c.get("hedge_terminal_path") or ""), str(c.get("hedge_expected_login") or "")))
        if len(cfgs) > 1 and not int(c.get("master_expected_login") or 0):
            errors.append(f"{f}: master_expected_login fehlt/0 — ab zwei Mastern Pflicht, sonst ist der "
                          f"Schutz gegen vertauschte Snapshots aus.")
        mode = str(c.get("mode", "dryrun")).lower()
        if mode not in ("dryrun", "demo", "live"):
            errors.append(f"{f}: mode '{mode}' ungueltig (dryrun | demo | live)")
    for magic, fs in by_magic.items():
        if len(fs) > 1:
            errors.append(f"magic {magic} in {', '.join(fs)} — MUSS pro Master eindeutig sein "
                          f"(sonst schliessen sich die Copier gegenseitig die Hedges).")
    for snap, fs in by_snap.items():
        if len(fs) > 1:
            errors.append(f"snapshot_file '{snap}' in {', '.join(fs)} — MUSS pro Master eindeutig sein "
                          f"(und im jeweiligen Master-EA als InpFileName gesetzt).")
    for prefix, fs in by_prefix.items():
        if len(fs) > 1:
            warnings.append(f"comment_prefix '{prefix}' in {', '.join(fs)} geteilt — ok solange die magic "
                            f"eindeutig ist, ein eigener Praefix pro Master ist trotzdem sauberer.")
    if len(hedge_pairs) > 1:
        errors.append("hedge_terminal_path / hedge_expected_login unterscheiden sich zwischen den Configs — "
                      "alle Master dieses Prozesses muessen in DASSELBE Hedge-Terminal zeigen.")
    return errors, warnings


def compute_startup_skip(positions, hedges, adopt):
    """REIN RECHNEND (testbar): Welche beim Start offenen Master-Positionen werden
    NICHT bedient?  Regel seit 13.08.2026: eine Position, die schon einen eigenen
    Hedge hat, wird ADOPTIERT (sie ist ja von uns — Neustart-Recovery inklusive
    Teil-Schliessungen). Nur Positionen OHNE Hedge bleiben unangetastet, damit
    Alt-Bestand nicht nachtraeglich gehedged wird."""
    if adopt:
        return set()
    return {p["ident"] for p in positions if not hedges.get(p["ident"])}


# ── Snapshot des Prop-Terminals lesen ───────────────────────────────────────────
def read_snapshot(path, expect_login=None):
    """Gibt {seq, login, server, margin_mode, positions} oder None.
    expect_login: Fremd-Logins werden bereits HIER verworfen — ein Snapshot vom
    falschen Konto ist damit strukturell unsichtbar (Audit-Fund: sonst setzte er
    den Staleness-Zaehler des eigenen Masters zurueck)."""
    try:
        with open(path, "r", encoding="ascii", errors="replace") as f:
            lines = [l.strip() for l in f if l.strip()]
    except (FileNotFoundError, OSError):
        return None
    if not lines or not lines[0].startswith("PROPHOS1;"):
        return None

    head = lines[0].split(";")
    try:
        seq = int(head[1]); login = int(head[3]); server = head[4]
        margin_mode = int(head[5]); count = int(head[6])
    except (IndexError, ValueError):
        return None
    if expect_login and int(expect_login) != login:
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
    hedges:    aktueller Hedge-Bestand DIESES Masters, {ident: [{ticket, symbol, type, volume}, …]}
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


# ── Ein Master = eine config*.json ──────────────────────────────────────────────
class Master:
    def __init__(self, cfg_path):
        self.cfg_path = cfg_path
        self.file = os.path.basename(cfg_path)
        self.status_path = status_path_for(cfg_path)
        self.cfg_mtime = 0.0
        self.reload(initial=True)
        # Laufzeit-Zustand — strikt pro Master (Audit-Fund: global geteilte
        # blocked/open_tries-Zaehler vermischten zwei Konten)
        self.seen_seq = None
        self.last_seq = None
        self.last_change = time.time()
        self.stale_warned = False
        self.startup_skip = None
        self.warned = set()
        self.virtual = {}
        self.virtual_ticket = -1
        self.open_last = {}
        self.open_tries = {}
        self.blocked = set()
        self.last_status = 0.0

    def reload(self, initial=False):
        cfg = load_json(self.cfg_path)
        self.cfg_mtime = os.path.getmtime(self.cfg_path)
        self.mode = str(cfg.get("mode", "dryrun")).lower()
        self.magic = int(cfg.get("magic", 770001))
        self.prefix = str(cfg.get("comment_prefix", "PH"))
        self.snapshot_file = str(cfg.get("snapshot_file", "prophos_master.csv"))
        self.master_login = int(cfg.get("master_expected_login") or 0)
        self.multiplier = float(cfg.get("multiplier", 1.0))
        self.max_lots = float(cfg.get("max_lots_per_hedge", 5.0))
        self.symbol_map = cfg.get("symbol_map", {})
        self.deviation = int(cfg.get("deviation_points", 30))
        self.filling = str(cfg.get("filling", "auto")).upper()
        self.adopt = bool(cfg.get("adopt_existing_master_positions", False))
        self.terminal_path = cfg.get("master_terminal_path") or ""
        self.raw = cfg
        return cfg

    def hot_reload(self):
        """Panel-Aenderungen im Betrieb uebernehmen. Nur multiplier/symbol_map/
        max_lots wirken sofort; alles andere (mode, Konten, Pfade, magic) verlangt
        einen Neustart des Prozesses, damit die Startpruefungen erneut laufen.
        Rueckgabe: None = nichts, "hot" = uebernommen, "restart" = Neustart noetig."""
        try:
            m = os.path.getmtime(self.cfg_path)
        except OSError:
            return "restart"  # Config geloescht/umbenannt → sauber neu aufsetzen
        if m == self.cfg_mtime:
            return None
        self.cfg_mtime = m
        new = load_json(self.cfg_path)
        old = self.raw
        HOT = {"multiplier", "symbol_map", "max_lots_per_hedge"}
        changed = {k for k in set(old) | set(new)
                   if not k.startswith("_") and old.get(k) != new.get(k)}
        if changed - HOT:
            log(f"↻ [{self.file}] Aenderung an {', '.join(sorted(changed - HOT))} — Neustart "
                f"fuer saubere Startpruefungen.")
            return "restart"
        chg = []
        if "multiplier" in changed:
            self.multiplier = float(new["multiplier"]); chg.append(f"Multiplikator {self.multiplier}")
        if "symbol_map" in changed:
            self.symbol_map = new.get("symbol_map") or {}; chg.append("Symbol-Mapping")
            self.warned.clear()
        if "max_lots_per_hedge" in changed:
            self.max_lots = float(new["max_lots_per_hedge"]); chg.append(f"max_lots {self.max_lots}")
        self.raw = new
        if chg:
            log(f"↻ [{self.file}] Uebernommen: " + ", ".join(chg))
            return "hot"
        return None


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    cfg_paths = discover_configs(here)
    if not cfg_paths:
        sys.exit("Keine config*.json gefunden — config.example.json kopieren und ausfuellen.")

    masters = [Master(p) for p in cfg_paths]

    # ── Flotten-Pruefung: Eindeutigkeit erzwingen, nicht erhoffen ───────────────
    errors, warnings = check_fleet([dict(m.raw, _file=m.file) for m in masters])
    for w in warnings:
        log("⚠ " + w)
    if errors:
        for e in errors:
            log("⛔ " + e)
        sys.exit("Abbruch — Config-Konflikte beheben (siehe oben).")

    # ── Instanz-Sperre: laeuft schon ein Copier fuer diese Configs? ─────────────
    for m in masters:
        try:
            st = load_json(m.status_path)
            ts = datetime.fromisoformat(st.get("updated_at", "1970-01-01T00:00:00"))
            if st.get("running") and st.get("pid") != os.getpid() \
                    and (datetime.now() - ts).total_seconds() < 15:
                sys.exit(f"Es laeuft bereits ein Copier fuer {m.file} (PID {st.get('pid')}, "
                         f"Status {st.get('updated_at')}). Zweiter Prozess wuerde doppelt hedgen — Abbruch.")
        except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError):
            pass

    ref = masters[0].raw
    common = ref.get("common_files_dir") or os.path.join(
        os.environ.get("APPDATA", ""), "MetaQuotes", "Terminal", "Common", "Files")
    any_armed = any(m.mode != "dryrun" for m in masters)

    print("=" * 72)
    print(f" Prophos MT5-Hedge-Executor · {len(masters)} Master, ein Hedge-Terminal")
    for m in masters:
        print(f"   {m.file:<24} Modus {m.mode.upper():<7} magic {m.magic}  "
              f"Master {m.master_login or '?'}  Snapshot {m.snapshot_file}")
    print(" Duplikum / app.py / prophos.html werden nicht angefasst.")
    print("=" * 72)

    import MetaTrader5 as mt5

    # ── An das HEDGE-Terminal haengen (genau eines, fuer alle Master) ───────────
    init_kw = {}
    if ref.get("hedge_terminal_path"):
        init_kw["path"] = ref["hedge_terminal_path"]
    if ref.get("hedge_portable"):
        init_kw["portable"] = True
    # BEWUSST kein login/password/server: initialize() nutzt den im Terminal
    # eingeloggten Account. mt5.login() wird NIE aufgerufen — das wuerde ein
    # Terminal auf ein anderes Konto umschalten.
    if not mt5.initialize(**init_kw):
        sys.exit(f"initialize() fehlgeschlagen: {mt5.last_error()} — laeuft das Hedge-Terminal?")

    ti = mt5.terminal_info()
    ai = mt5.account_info()
    if ti is None or ai is None:
        mt5.shutdown()
        sys.exit("terminal_info()/account_info() leer — Terminal offen und eingeloggt?")

    # ── HARTE PRUEFUNG: haengen wir am richtigen Terminal/Konto? ────────────────
    log(f"Verbunden mit Terminal: {ti.path}")
    log(f"Konto {ai.login} @ {ai.server} · {ai.company}")
    problems = []
    exp_hedge_login = ref.get("hedge_expected_login")
    if exp_hedge_login and int(exp_hedge_login) != int(ai.login):
        problems.append(f"Erwartet war Hedge-Konto {exp_hedge_login}, verbunden ist aber {ai.login}")
    for m in masters:
        if m.master_login and m.master_login == int(ai.login):
            problems.append(f"GEFAHR: verbunden mit MASTER-Konto {ai.login} ({m.file}) — "
                            f"hier darf nichts platziert werden")
    if ref.get("hedge_terminal_path"):
        # Exakter Ordnervergleich — der alte Substring-Test liess "C:\MT5-Hedge2"
        # als "C:\MT5-Hedge" durchgehen (Audit-Fund 13.08.2026).
        want = os.path.normcase(os.path.normpath(os.path.dirname(os.path.abspath(ref["hedge_terminal_path"]))))
        got = os.path.normcase(os.path.normpath(os.path.abspath(str(ti.path))))
        if want != got:
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
    demo_masters = [m.file for m in masters if m.mode == "demo"]
    if demo_masters and is_real:
        log(f"⛔ ABBRUCH: Modus 'demo' in {', '.join(demo_masters)}, aber das Hedge-Terminal "
            f"haengt an einem ECHTGELD-Konto.")
        mt5.shutdown(); sys.exit(1)

    # Hedging-Modus ist Pflicht: im Netting-Modus gibt es nur EINE Position pro
    # Symbol, damit bricht die Zuordnung Master-Position ↔ Hedge-Position.
    if int(ai.margin_mode) != int(mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING):
        log("⛔ ABBRUCH: Das Hedge-Konto ist NICHT im Hedging-Modus (Netting). "
            "Hedging-Konto verwenden.")
        mt5.shutdown(); sys.exit(1)

    if any_armed and not ti.trade_allowed:
        log("⛔ ABBRUCH: 'Algo Trading' ist im Hedge-Terminal nicht aktiv "
            "(Extras → Optionen → Expert Advisors). Aus Python nicht schaltbar.")
        mt5.shutdown(); sys.exit(1)

    # ── Hilfsfunktionen ─────────────────────────────────────────────────────────
    fleet_magics = {m.magic: m for m in masters}

    def hedge_book():
        """Kompletter Hedge-Bestand, EINMAL pro Tick gelesen und nach magic
        partitioniert: {magic: {ident: [{ticket, symbol, type, volume}, …]}}.
        Jeder Master sieht ausschliesslich seine eigene Partition — die
        strukturelle Antwort auf den Audit-Fund 'Copier A schliesst B's Hedges'.

        WICHTIG: Gibt None zurueck, wenn die Terminal-Verbindung gestoert ist —
        NICHT ein leeres Dict. Sonst saehe ein Verbindungsabriss aus wie "es gibt
        keine Hedges", und bestehende Hedges wuerden doppelt aufgerissen."""
        raw = mt5.positions_get()
        if raw is None:
            return None
        book = {mg: {} for mg in fleet_magics}
        for p in raw:
            mg = int(getattr(p, "magic", 0))
            m = fleet_magics.get(mg)
            if m is None:
                continue
            c = str(getattr(p, "comment", "") or "")
            i = c.find(m.prefix + "-")
            if i < 0:
                continue
            tok = c[i + len(m.prefix) + 1:]
            digits = ""
            for ch in tok:
                if ch.isdigit():
                    digits += ch
                else:
                    break
            if not digits:
                continue
            book[mg].setdefault(int(digits), []).append({
                "ticket": int(p.ticket), "volume": float(p.volume),
                "symbol": str(p.symbol), "type": int(p.type),
            })
        return book

    def sym_info(symbol):
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

    def send(m, req, what):
        if m.mode == "dryrun":
            log(f"[{m.file}] DRYRUN — wuerde senden: {what}")
            return True
        r = mt5.order_send(req)
        if r is None:
            log(f"[{m.file}] ❌ order_send None ({mt5.last_error()}) — {what}")
            return False
        if r.retcode != mt5.TRADE_RETCODE_DONE:
            log(f"[{m.file}] ❌ abgelehnt retcode={r.retcode} {getattr(r, 'comment', '')} — {what}")
            return False
        log(f"[{m.file}] ✅ {what} · deal={r.deal}")
        return True

    def filling_for(m, sym):
        if m.filling == "IOC":
            return mt5.ORDER_FILLING_IOC
        if m.filling == "FOK":
            return mt5.ORDER_FILLING_FOK
        si = mt5.symbol_info(sym)
        mask = int(getattr(si, "filling_mode", 0) or 0)
        if mask & 2:
            return mt5.ORDER_FILLING_IOC
        if mask & 1:
            return mt5.ORDER_FILLING_FOK
        return mt5.ORDER_FILLING_RETURN

    def open_hedge(m, ident, sym, mtype, vol):
        h_type = mt5.ORDER_TYPE_SELL if mtype == 0 else mt5.ORDER_TYPE_BUY   # REVERSE
        side = "SELL" if h_type == mt5.ORDER_TYPE_SELL else "BUY"
        mt5.symbol_select(sym, True)
        tick = mt5.symbol_info_tick(sym)
        price = (tick.bid if h_type == mt5.ORDER_TYPE_SELL else tick.ask) if tick else 0.0
        # Bewusst KEIN SL/TP auf dem Hedge: ein eigener Stop wuerde die
        # Absicherung vorzeitig aufloesen.
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": vol, "type": h_type,
               "price": price, "deviation": m.deviation, "magic": m.magic,
               "comment": f"{m.prefix}-{ident}", "type_time": mt5.ORDER_TIME_GTC,
               "type_filling": filling_for(m, sym)}
        return send(m, req, f"HEDGE OPEN {side} {vol} {sym} (Master-Pos {ident})")

    def close_part(m, h, vol):
        ctype = mt5.ORDER_TYPE_BUY if h["type"] == 1 else mt5.ORDER_TYPE_SELL
        tick = mt5.symbol_info_tick(h["symbol"])
        price = (tick.ask if ctype == mt5.ORDER_TYPE_BUY else tick.bid) if tick else 0.0
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": h["symbol"], "volume": vol,
               "type": ctype, "position": h["ticket"], "price": price,
               "deviation": m.deviation, "magic": m.magic, "comment": f"{m.prefix}c",
               "type_time": mt5.ORDER_TIME_GTC, "type_filling": filling_for(m, h["symbol"])}
        return send(m, req, f"HEDGE CLOSE {vol} {h['symbol']} (Ticket {h['ticket']})")

    # ── Hauptschleife ───────────────────────────────────────────────────────────
    poll = float(ref.get("poll_interval", 0.5))
    OPEN_COOLDOWN = 3.0
    OPEN_MAX_TRIES = 3
    conn_fail = 0
    CONN_FAIL_EXIT = max(10, int(20 / max(poll, 0.1)))  # ~20 Sekunden Ausfall
    last_cfg_check = 0.0
    last_dir_check = time.time()
    known_files = {os.path.basename(p) for p in cfg_paths}
    restart = False
    log(f"Warte auf Snapshots von {len(masters)} Master-Terminal(s)…")

    def master_status(m, snap, hedges, connected):
        return {
            "running": True, "mode": m.mode, "connected": connected,
            "master_login": (snap or {}).get("login") or m.master_login or None,
            "master_server": (snap or {}).get("server"),
            "hedge_login": int(ai.login), "hedge_server": str(ai.server),
            "magic": m.magic, "comment_prefix": m.prefix,
            "multiplier": m.multiplier, "max_lots": m.max_lots, "symbol_map": m.symbol_map,
            "master_positions": (snap or {}).get("positions") or [],
            "hedges": {str(k): v for k, v in (hedges or {}).items()},
            "blocked": sorted(m.blocked),
            "note": None if connected else "warte auf Snapshot des Master-Terminals",
        }

    try:
        while not restart:
            now = time.time()

            # ── Config-Aenderungen (Panel/Prophos) alle 2s uebernehmen ──────────
            if now - last_cfg_check > 2.0:
                last_cfg_check = now
                for m in masters:
                    try:
                        if m.hot_reload() == "restart":
                            write_status(m.status_path, {"running": False, "mode": m.mode,
                                                         "note": "Neustart wegen Config-Aenderung"})
                            restart = True
                    except Exception as e:
                        log(f"⚠ [{m.file}] Config-Reload fehlgeschlagen: {type(e).__name__}: {str(e)[:80]}")
                if restart:
                    break

            # Neue/geloeschte config*.json → Neustart, damit die Flotten-Pruefung
            # und die Startpruefungen fuer den neuen Master laufen.
            if now - last_dir_check > 5.0:
                last_dir_check = now
                current_files = {os.path.basename(p) for p in discover_configs(here)}
                if current_files != known_files:
                    log(f"↻ Config-Dateien geaendert ({', '.join(sorted(current_files ^ known_files))}) — "
                        f"Neustart fuer die Flotten-Pruefung.")
                    break

            # ── Hedge-Bestand EINMAL pro Tick lesen ─────────────────────────────
            book = hedge_book() if any_armed else {mg: {} for mg in fleet_magics}
            if book is None:
                conn_fail += 1
                if conn_fail == 1:
                    log(f"⚠ Terminal-Verbindung gestoert ({mt5.last_error()}) — setze aus, "
                        f"greife NICHT auf leere Daten zu.")
                if conn_fail >= CONN_FAIL_EXIT:
                    log("⛔ Verbindung dauerhaft weg — beende mich. start-copier.bat startet "
                        "neu und prueft beim Hochlauf wieder alles durch.")
                    break
                time.sleep(poll)
                continue
            if conn_fail:
                log(f"✓ Verbindung wieder da (nach {conn_fail} Fehlversuchen).")
                conn_fail = 0

            # ── Jeden Master abarbeiten ─────────────────────────────────────────
            for m in masters:
                snap = read_snapshot(os.path.join(common, m.snapshot_file),
                                     expect_login=m.master_login)
                if snap is None:
                    if now - m.last_status > 3.0:
                        m.last_status = now
                        write_status(m.status_path, master_status(m, None, None, False))
                    continue

                hedges = m.virtual if m.mode == "dryrun" else book.get(m.magic, {})

                if m.seen_seq is None:
                    log(f"✓ [{m.file}] Snapshot verbunden — Master {snap['login']} @ {snap['server']}, "
                        f"{len(snap['positions'])} offene Position(en)")
                    m.startup_skip = compute_startup_skip(snap["positions"], hedges, m.adopt)
                    adopted = {p["ident"] for p in snap["positions"]} - m.startup_skip
                    if m.startup_skip:
                        log(f"⏭ [{m.file}] {len(m.startup_skip)} Position(en) ohne Hedge waren beim "
                            f"Start schon offen — werden nicht nachtraeglich gehedged.")
                    if adopted and not m.adopt:
                        log(f"✓ [{m.file}] {len(adopted)} Position(en) mit bestehendem Hedge "
                            f"uebernommen (Neustart-Recovery).")
                m.seen_seq = snap["seq"]

                # Staleness pro Master (Fremd-Logins sind schon in read_snapshot raus)
                if snap["seq"] != m.last_seq:
                    m.last_seq = snap["seq"]
                    m.last_change = time.time()
                    m.stale_warned = False
                elif not m.stale_warned and time.time() - m.last_change > 15:
                    log(f"⚠ [{m.file}] Snapshot seit 15s unveraendert — laeuft das Lese-EA im "
                        f"Master-Terminal noch? (Chart offen, Reiter 'Experten' pruefen)")
                    m.stale_warned = True

                actions, warns = plan_actions(
                    snap["positions"], hedges,
                    multiplier=m.multiplier, symbol_map=m.symbol_map, max_lots=m.max_lots,
                    sym_info=sym_info, skip_idents=(m.startup_skip or frozenset()))

                for w in warns:
                    if w not in m.warned:
                        log(f"⚠ [{m.file}] {w} — uebersprungen.")
                        m.warned.add(w)

                for a in actions:
                    ident = a["ident"]
                    if a["kind"] == "open":
                        if ident in m.blocked:
                            continue
                        if time.time() - m.open_last.get(ident, 0) < OPEN_COOLDOWN:
                            continue  # zu kurz her — Broker/Terminal Zeit geben
                        m.open_tries[ident] = m.open_tries.get(ident, 0) + 1
                        if m.open_tries[ident] > OPEN_MAX_TRIES:
                            m.blocked.add(ident)
                            log(f"⛔ [{m.file}] Master-Pos {ident}: Hedge nach {OPEN_MAX_TRIES} "
                                f"Versuchen nicht wiedererkannt — gestoppt (Schutz gegen "
                                f"Mehrfach-Hedge). Im Hedge-Terminal pruefen.")
                            continue
                        m.open_last[ident] = time.time()
                        ok = open_hedge(m, ident, a["symbol"],
                                        0 if a["hedge_type"] == 1 else 1,  # Master-Typ zurueckrechnen
                                        a["volume"])
                        if ok and m.mode == "dryrun":
                            m.virtual.setdefault(ident, []).append({
                                "ticket": m.virtual_ticket, "volume": a["volume"],
                                "symbol": a["symbol"], "type": a["hedge_type"]})
                            m.virtual_ticket -= 1
                    else:
                        if m.mode == "dryrun":
                            hs = m.virtual.get(ident, [])
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
                                m.virtual.pop(ident, None)
                            log(f"[{m.file}] DRYRUN — wuerde senden: HEDGE CLOSE {a['volume']} "
                                f"{a['symbol']} (Master-Pos {ident})")
                            m.open_tries.pop(ident, None); m.open_last.pop(ident, None)
                            m.blocked.discard(ident)
                        else:
                            open_pos = next((h for h in hedges.get(ident, [])
                                             if h["ticket"] == a["ticket"]), None)
                            if open_pos and close_part(m, open_pos, a["volume"]):
                                m.open_tries.pop(ident, None); m.open_last.pop(ident, None)
                                m.blocked.discard(ident)

                if time.time() - m.last_status > 3.0:
                    m.last_status = time.time()
                    write_status(m.status_path, master_status(m, snap, hedges, True))

            time.sleep(poll)
    except KeyboardInterrupt:
        log("Gestoppt.")
    finally:
        for m in masters:
            write_status(m.status_path, {"running": False, "mode": m.mode})
        mt5.shutdown()


if __name__ == "__main__":
    main()
