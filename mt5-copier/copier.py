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

Der Copier sendet IMMER echte Orders. Die fruehere Modus-Maschinerie
(dryrun | demo | live samt Echtgeld-Riegel) ist am 25.08.2026 auf Finns
Ansage komplett ausgebaut — es wird nur noch live gearbeitet, der Umweg
ueber Modi hat nur Klicks gekostet. Ein "mode"-Feld in Alt-Configs wird
still ignoriert. Vor dem Start Duplikum fuer die Paare abschalten.
"""

import json
import os
import re
import sys
import threading
import time
import urllib.request
from datetime import datetime

TOL = 1e-6

# ── Selbst-Update (15.08.2026, Finns Wunsch: kein manuelles Nachladen mehr) ─────
# Ein Hintergrund-Thread prueft jede Minute die VERSION-Datei auf GitHub. Weicht
# sie von der lokalen ab, beendet sich der Copier SAUBER — aber erst, wenn alle
# Master flach sind (nie mitten im Trade). Die start-copier.bat laedt in ihrer
# Schleife vor jedem Start die aktuellen Dateien und ersetzt sie nur, wenn der
# Download vollstaendig ankam. Ohne lokale VERSION-Datei (alte .bat) ist der
# Mechanismus komplett aus.
UPDATE_URL = ("https://raw.githubusercontent.com/finntraidingview-cmd/Prophos/"
              "main/mt5-copier/VERSION")
_REMOTE_VERSION = {"v": None}


def local_version():
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION"),
                  "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def _version_watcher():
    while True:
        try:
            with urllib.request.urlopen(UPDATE_URL, timeout=10) as r:
                _REMOTE_VERSION["v"] = r.read().decode("utf-8", "replace").strip()
        except Exception:
            pass  # kein Internet o.ae. — einfach beim alten Stand bleiben
        time.sleep(60)

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


# ── closed_hedges-Sidecar (15.08.2026, Etappe 3) ───────────────────────────────
# Verbuchte Hedge-Closes liegen NICHT nur im RAM: jeder Copier-Neustart
# (Moduswechsel, Selbst-Update — das exakt auf 'alle flach' = direkt nach
# Trade-Ende wartet —, Config-Anlage/-Loeschung, Netz-Exit) wuerde einen
# RAM-Ring genau dann wischen, wenn der Browser ihn fuer den P&L-Beweis
# braucht (Richter-Blocker aus dem Etappe-3-Review). Deshalb Sidecar-Datei
# closed-<name>.json neben der config, Ring 50, atomar wie write_status.
def closed_path_for(cfg_path):
    base = os.path.basename(cfg_path)
    return os.path.join(os.path.dirname(os.path.abspath(cfg_path)),
                        re.sub(r"^config", "closed", base, count=1, flags=re.I))


def load_closed(path):
    """Liefert (closed_ring, last_vol). last_vol ist die persistierte
    Schwund-Waechter-Baseline {ident(str): Gesamtvolumen} — ohne sie waere der
    Waechter nach jedem Neustart blind und ein extern geschlossener Hedge in
    der Copier-Downtime ergaebe spaeter eine plausible falsche closed_sum
    (Review-Fund 15.08.2026). Altes Format (reine Liste) wird toleriert."""
    try:
        data = load_json(path)
        if isinstance(data, list):
            return data, {}
        if isinstance(data, dict):
            closed = data.get("closed")
            lv = data.get("last_vol")
            return (closed if isinstance(closed, list) else []), \
                   ({str(k): float(v) for k, v in lv.items()} if isinstance(lv, dict) else {})
        return [], {}
    except Exception:
        return [], {}


def write_closed(path, entries, last_vol=None):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"closed": entries[-50:], "last_vol": last_vol or {}},
                      f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except Exception as e:
        print(f"[closed] konnte {os.path.basename(path)} nicht schreiben: {type(e).__name__}: {e}", flush=True)


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
    # Header v3 (15.08.2026, Etappe 3): Balance/Equity/Waehrung hinten angehaengt.
    # Alte EAs im Feld schreiben weiter 7 (bzw. 9) Felder — fehlende Werte sind
    # None, NIE 0 ('Beweis oder leer': eine erfundene 0 saehe in Prophos wie eine
    # echte Balance aus und wuerde ein falsches P&L-Delta beweisen).
    balance = equity = currency = None
    try:
        if len(head) >= 9:
            balance = float(head[7]); equity = float(head[8])
        if len(head) >= 10 and head[9]:
            currency = head[9]
    except (IndexError, ValueError):
        balance = equity = currency = None
    # Header v4 (18.08.2026): Algo-Handel-Zustand des Master-Terminals (1/0).
    # Fehlt das Feld (altes EA), bleibt es None — der Check blockt dann nicht.
    algo = None
    try:
        if len(head) >= 11 and head[10] in ("0", "1"):
            algo = head[10] == "1"
    except IndexError:
        algo = None
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
    return {"seq": seq, "login": login, "server": server, "margin_mode": margin_mode,
            "positions": positions,
            "balance": balance, "equity": equity, "currency": currency,
            "algo": algo}


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


def plan_actions(positions, hedges, *, multiplier, symbol_map, sym_info,
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
        # Keine max-Lots-Grenze mehr (15.08.2026, Finns Ansage "komplett weg"):
        # gedeckelt wird nur noch vom Broker selbst (volume_max in norm_vol).
        v = norm_vol(si, mp["volume"] * multiplier * (m_cs / h_cs))
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
        # Reopen-Guard, umgebaut 14.08.2026 (Internet-Ausfall-Szenario):
        #   open_last  — letzter Sendeversuch (Cooldown-Anker)
        #   open_fail  — FEHLGESCHLAGENE Sends in Folge (Ablehnung/keine Verbindung).
        #                Eine abgelehnte Order kann kein Duplikat erzeugen -> es wird
        #                geduldig ewig weiterversucht, mit wachsendem Abstand (3->30s).
        #   open_done  — BESTAETIGTE Sends (retcode DONE), deren Hedge danach NICHT
        #                im Bestand auftauchte. DAS ist die echte Mehrfach-Hedge-Gefahr
        #                (z.B. Broker veraendert den Kommentar) -> nach 3x blocked.
        #                Beide werden zurueckgesetzt, sobald der Hedge erkannt ist —
        #                sonst blockierte das dritte Aufstocken derselben Position
        #                faelschlich (schlummernder Fehler im alten Zaehler).
        self.open_last = {}
        self.open_fail = {}
        self.open_done = {}
        # open_seen[ident] = erkanntes Hedge-Volumen im Moment des Sendeversuchs.
        # Der Guard-Reset haengt am VOLUMENWACHSTUM seit dem letzten Send — nicht
        # an "irgendein Hedge existiert". Sonst wuerde beim Aufstocken der alte
        # Hedge den Zaehler jede halbe Sekunde loeschen und der Mehrfach-Hedge-
        # Schutz waere genau dann wirkungslos, wenn er gebraucht wird
        # (adversarische Pruefung 14.08.2026).
        self.open_seen = {}
        self.close_last = {}
        self.blocked = set()
        self.last_status = 0.0
        # closed_hedges (15.08.2026, Etappe 3): Beweisquelle fuer den Hedge-P&L in
        # Prophos. Beim Init aus dem Sidecar geladen — neustart-fest.
        self.closed_path = closed_path_for(cfg_path)
        self.closed, self.hedge_last_vol = load_closed(self.closed_path)
        if len(self.closed) > 50:
            del self.closed[:-50]
        self.booked_deals = {}    # ident -> {Deal-Tickets} — nie denselben Deal zweimal verbuchen
        # hedge_last_vol (ident -> Gesamtvolumen) kommt mit aus dem Sidecar:
        # nur so erkennt der Schwund-Waechter auch Closes, die WAEHREND einer
        # Copier-Downtime passiert sind (Review-Fund 15.08.2026).
        self.own_close_mark = {}  # ident -> Zeitpunkt des letzten EIGENEN erfolgreichen Close

    def reload(self, initial=False):
        cfg = load_json(self.cfg_path)
        self.cfg_mtime = os.path.getmtime(self.cfg_path)
        self.magic = int(cfg.get("magic", 770001))
        self.prefix = str(cfg.get("comment_prefix", "PH"))
        self.snapshot_file = str(cfg.get("snapshot_file", "prophos_master.csv"))
        self.master_login = int(cfg.get("master_expected_login") or 0)
        self.multiplier = float(cfg.get("multiplier", 1.0))
        self.symbol_map = cfg.get("symbol_map", {})
        self.deviation = int(cfg.get("deviation_points", 30))
        self.filling = str(cfg.get("filling", "auto")).upper()
        self.adopt = bool(cfg.get("adopt_existing_master_positions", False))
        self.terminal_path = cfg.get("master_terminal_path") or ""
        self.raw = cfg
        return cfg

    def hot_reload(self):
        """Panel-Aenderungen im Betrieb uebernehmen. Nur multiplier/symbol_map
        wirken sofort; alles andere (Konten, Pfade, magic) verlangt
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
        # max_lots_per_hedge bleibt in HOT, obwohl die Grenze abgeschafft ist
        # (15.08.2026): Alt-Configs tragen das Feld noch, und ein Feld-Loeschen
        # durch Panel-Save darf keinen unnoetigen Prozess-Neustart ausloesen.
        # mode genauso (25.08.2026, Modus-Ausbau): das Feld ist bedeutungslos,
        # steht aber noch in Alt-Configs — Aenderungen/Loeschen daran duerfen
        # keinen Neustart ausloesen.
        HOT = {"multiplier", "symbol_map", "max_lots_per_hedge", "mode"}
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
    print("=" * 72)
    print(f" Prophos MT5-Hedge-Executor · {len(masters)} Master, ein Hedge-Terminal")
    for m in masters:
        print(f"   {m.file:<24} magic {m.magic}  "
              f"Master {m.master_login or '?'}  Snapshot {m.snapshot_file}")
    print(" Duplikum / app.py / prophos.html werden nicht angefasst.")
    print("=" * 72)

    import MetaTrader5 as mt5

    # ── Hedge-Terminal bei Bedarf selbst starten (15.08.2026, Autostart-Stack) ──
    # Der Login ist bei MT5 gespeichert; nach einem PC-Neustart muss niemand mehr
    # klicken. Laeuft es schon, passiert hier nichts (pids-Pruefung — ein zweiter
    # Start derselben Installation waere ein leeres Fenster mit Login-Dialog).
    hpath = ref.get("hedge_terminal_path")
    if hpath and os.name == "nt" and os.path.exists(hpath):
        try:
            import provision
            import subprocess
            if not provision.terminal_pids(os.path.dirname(os.path.abspath(hpath))):
                log("Hedge-Terminal laeuft nicht — starte es (Login ist gespeichert)…")
                subprocess.Popen([hpath], cwd=os.path.dirname(os.path.abspath(hpath)))
                time.sleep(20)  # Boot + Auto-Login abwarten; notfalls wiederholt die .bat
        except Exception as e:
            log(f"⚠ Hedge-Terminal-Autostart fehlgeschlagen ({type(e).__name__}) — "
                f"initialize() versucht es gleich selbst.")

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

    # Nur noch informativ (25.08.2026, Modus-Ausbau): der fruehere demo-Riegel
    # ist weg, gearbeitet wird immer echt — egal woran das Terminal haengt.
    is_real = int(ai.trade_mode) == 2
    log(f"Hedge-Konto ist {'ECHTGELD' if is_real else 'DEMO/CONTEST'}")

    # Hedging-Modus ist Pflicht: im Netting-Modus gibt es nur EINE Position pro
    # Symbol, damit bricht die Zuordnung Master-Position ↔ Hedge-Position.
    if int(ai.margin_mode) != int(mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING):
        log("⛔ ABBRUCH: Das Hedge-Konto ist NICHT im Hedging-Modus (Netting). "
            "Hedging-Konto verwenden.")
        mt5.shutdown(); sys.exit(1)

    if not ti.trade_allowed:
        log("⛔ ABBRUCH: 'Algo Trading' ist im Hedge-Terminal nicht aktiv "
            "(Extras → Optionen → Expert Advisors). Aus Python nicht schaltbar.")
        mt5.shutdown(); sys.exit(1)

    # ── Hilfsfunktionen ─────────────────────────────────────────────────────────
    fleet_magics = {m.magic: m for m in masters}

    # Hedge-Kontostand (15.08.2026, Etappe 3): EINMAL pro Tick gelesen — nicht pro
    # Master, account_info() ist ein IPC-Roundtrip ins Terminal. Wandert in jeden
    # master_status; Prophos friert daraus die P&L-Baseline ein. Liefert das
    # Terminal nichts, bleibt es None — nie 0 ('Beweis oder leer').
    hedge_acc = {"balance": None, "equity": None, "currency": None, "algo": None}

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
                # schwebender P&L der Position — Prophos zeigt ihn auf laufenden
                # Trade-Karten live an (15.08.2026, Etappe 3)
                "profit": float(p.profit),
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
        # Rueckgabe seit 15.08.2026 das order_send-Result statt True: result.deal
        # ist der einzige beweisfeste Anker fuer die closed_hedges-Verbuchung
        # (vorher wurde r.deal nur geloggt und war weg). Truthiness bleibt fuer
        # alle Aufrufer erhalten: Result/True = ok, None = fehlgeschlagen.
        r = mt5.order_send(req)
        if r is None:
            log(f"[{m.file}] ❌ order_send None ({mt5.last_error()}) — {what}")
            return None
        if r.retcode != mt5.TRADE_RETCODE_DONE:
            hinweis = getattr(r, "comment", "")
            if int(r.retcode) == 10027:
                hinweis = ("Algo-Handel im HEDGE-Terminal ist AUS — oben den "
                           "'Algo-Handel'-Knopf gruen schalten, sonst kann der Copier nicht hedgen!")
            log(f"[{m.file}] ❌ abgelehnt retcode={r.retcode} {hinweis} — {what}")
            return None
        log(f"[{m.file}] ✅ {what} · deal={r.deal}")
        return r

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

    def book_close(m, ident, h, result, vol):
        """Close-Deal beweisfest verbuchen (15.08.2026, Etappe 3): verbucht wird
        NUR der Deal mit ticket == result.deal — nie ein geratener profit=0, denn
        eine plausible falsche Zahl ist schlimmer als ein leeres Feld ('Beweis
        oder leer'). Die Deal-History kann dem order_send-Result kurz nachhinken,
        deshalb bis zu 3 Wiederholungen a 0,3 s."""
        deal_id = int(getattr(result, "deal", 0) or 0)
        if not deal_id:
            log(f"[{m.file}] ⚠ Close ohne deal-Ticket im Result (Master-Pos {ident}) — "
                f"kein closed_hedges-Eintrag.")
            return
        seen = m.booked_deals.setdefault(ident, set())
        if deal_id in seen:
            return  # Doppelzaehlungs-Schutz: derselbe Deal wird nie zweimal verbucht
        deal = None
        for attempt in range(4):
            ds = mt5.history_deals_get(position=int(h["ticket"]))
            if ds:
                deal = next((d for d in ds if int(d.ticket) == deal_id), None)
            if deal is not None:
                break
            if attempt < 3:
                time.sleep(0.3)
        if deal is None:
            log(f"[{m.file}] ⚠ Close-Deal {deal_id} (Ticket {h['ticket']}) nicht in der "
                f"History gefunden — KEIN closed_hedges-Eintrag (nie profit=0 raten).")
            return
        seen.add(deal_id)
        m.closed.append({
            "ticket": int(h["ticket"]), "deal": deal_id, "symbol": h["symbol"],
            "volume": vol,
            # profit + commission + swap des Close-Deals = was wirklich auf dem
            # Hedge-Konto ankommt
            "profit": float(deal.profit) + float(deal.commission) + float(deal.swap),
            "closed_at": datetime.now().isoformat(timespec="seconds"),
        })
        del m.closed[:-50]
        write_closed(m.closed_path, m.closed, m.hedge_last_vol)

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
    my_version = local_version()
    if my_version:
        log(f"Version {my_version} · Selbst-Update aktiv (prueft GitHub jede Minute)")
        threading.Thread(target=_version_watcher, daemon=True).start()
    update_waiting = False
    log(f"Warte auf Snapshots von {len(masters)} Master-Terminal(s)…")

    def master_status(m, snap, hedges, connected):
        # Ein EINGEFRORENER Snapshot ist genauso blind wie ein fehlender — nur
        # unsichtbarer: die Datei von gestern liest sich gueltig (Fund 15.08.2026,
        # EA war nach unsauberem Beenden vom Chart verschwunden, Karte sah gesund
        # aus, Master-Trade blieb ungehedged). Deshalb steht das jetzt als Warnung
        # in der Karte.
        # standby (25.08.2026, Finns Einwand): die Master-Terminals sind
        # absichtlich ZU und oeffnen erst beim Trade-Start — fehlender oder
        # eingefrorener Snapshot ist dann Normalzustand, keine Stoerung. Die
        # Karte soll dann ruhig "Standby" zeigen statt der Dauer-Warnung.
        # standby ist ein reiner ANZEIGE-Hinweis: note bleibt in ALLEN
        # Stale-Faellen gesetzt, denn note ist das Frische-Siegel fuer
        # Panel-Loesch-Riegel, P&L-Beweis und master_algo — 'alt ist nicht
        # aktuell' gilt unveraendert. Alarm bleibt Alarm, sobald etwas auf
        # dem Spiel steht: offene Hedges oder Master-Positionen im letzten
        # Snapshot (der Fund vom 15.08. — EA weg, Trade ungehedged — faellt
        # genau NICHT unter standby, weil dort eine Position im Spiel war).
        note = None
        standby = False
        offene_hedges = any(hs for hs in (hedges or {}).values())
        if not connected:
            note = "warte auf Snapshot des Master-Terminals"
            standby = not offene_hedges
        elif m.last_seq is not None and time.time() - m.last_change > 15:
            note = (f"Snapshot eingefroren — Lese-EA im Master-Terminal pruefen! "
                    f"(Chart mit ProphosHedgeReader offen? Sonst neu aufziehen, "
                    f"InpFileName = {m.snapshot_file})")
            standby = (not offene_hedges) and not ((snap or {}).get("positions"))
        return {
            "running": True, "connected": connected,
            "master_login": (snap or {}).get("login") or m.master_login or None,
            "master_server": (snap or {}).get("server"),
            "hedge_login": int(ai.login), "hedge_server": str(ai.server),
            "magic": m.magic, "comment_prefix": m.prefix,
            "multiplier": m.multiplier, "symbol_map": m.symbol_map,
            "master_positions": (snap or {}).get("positions") or [],
            "hedges": {str(k): v for k, v in (hedges or {}).items()},
            "blocked": sorted(m.blocked),
            "note": note,
            "standby": standby,
            # P&L-Beweisdaten (15.08.2026, Etappe 3): Master-Seite aus dem
            # Snapshot-Header v3, Hedge-Seite aus account_info() (einmal pro
            # Tick). Fehlende Quellen bleiben None — nie 0.
            "master_balance": (snap or {}).get("balance"),
            "master_equity": (snap or {}).get("equity"),
            "master_currency": (snap or {}).get("currency"),
            "hedge_balance": hedge_acc["balance"],
            "hedge_equity": hedge_acc["equity"],
            "hedge_currency": hedge_acc["currency"],
            "hedge_usd_rate": hedge_acc.get("usd_rate"),
            # Algo-Handel beider Seiten (18.08.2026): Master aus dem Snapshot
            # (EA v4), Hedge live aus terminal_info. None = nicht pruefbar
            # (altes EA) — der Check blockt nur bei explizitem False.
            # NUR bei frischem Snapshot melden (18.08.2026, The5ers-Fund:
            # Terminal zu -> Snapshot eingefroren -> der Check verkaufte den
            # ALTEN Algo-aus-Wert als aktuell und verlangte einen Knopf in
            # einem Terminal, das gar nicht mehr offen war).
            "master_algo": ((snap or {}).get("algo") if (connected and not note) else None),
            "hedge_algo": hedge_acc.get("algo"),
            # Positionen auf dem Hedge-Konto OHNE Prophos-Magic (None = nicht
            # pruefbar): Finns 'Slave-Order ohne Master'-Alarm im Fleet-Block.
            "hedge_fremde": hedge_acc.get("fremde"),
            # Verbuchte Closes aus dem Sidecar-Ring — neustart-fest
            "closed_hedges": m.closed[-50:],
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
                            # Ist die Config VERSCHWUNDEN (Panel /api/delete, 15.08.2026),
                            # KEINEN Status mehr schreiben — sonst legt der Copier die
                            # eben geloeschte Status-Datei binnen 2 s wieder an.
                            if os.path.exists(m.cfg_path):
                                write_status(m.status_path, {"running": False,
                                                             "note": "Neustart wegen Config-Aenderung"})
                            restart = True
                    except Exception as e:
                        log(f"⚠ [{m.file}] Config-Reload fehlgeschlagen: {type(e).__name__}: {str(e)[:80]}")
                if restart:
                    break

            # Selbst-Update: neue Version auf GitHub → sauber neu starten, aber
            # NUR wenn kein Master eine Position oder einen Hedge offen hat.
            rv = _REMOTE_VERSION["v"]
            if my_version and rv and rv != my_version:
                busy = [m.file for m in masters if getattr(m, "busy", False)]
                if not busy:
                    log(f"↻ Update {my_version} → {rv} — alle Master flach, starte neu "
                        f"(start-copier.bat laedt die neuen Dateien).")
                    break
                if not update_waiting:
                    update_waiting = True
                    log(f"↻ Update {my_version} → {rv} verfuegbar — warte, bis alle Master "
                        f"flach sind ({', '.join(busy)}).")

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
            book = hedge_book()
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

            # Hedge-Kontostand einmal pro Tick auffrischen (15.08.2026, Etappe 3)
            hai = mt5.account_info()
            if hai is not None:
                hedge_acc["balance"] = float(hai.balance)
                hedge_acc["equity"] = float(hai.equity)
                hedge_acc["currency"] = str(hai.currency) or None
            else:
                hedge_acc["balance"] = hedge_acc["equity"] = hedge_acc["currency"] = None
            # Algo-Handel-Zustand des HEDGE-Terminals pro Tick (18.08.2026,
            # Finns Fund: Algo wurde NACH dem Copier-Start ausgeschaltet, die
            # Hedges liefen in retcode=10027 — der Start-Check von damals sieht
            # das nicht. Jetzt steht der Live-Zustand im Status, der Trade-
            # Start-Check blockt bei False.)
            ti_h = mt5.terminal_info()
            hedge_acc["algo"] = bool(ti_h.trade_allowed) if ti_h is not None else None
            # FREMDE Positionen auf dem Hedge-Konto (18.08.2026, Finns Wunsch:
            # auch eine Slave-Order sehen, die der Copier gar nicht kennt —
            # z.B. von Hand eroeffnet). 'Fremd' = Magic ausserhalb der
            # Prophos-Familie 770000-779999: die Hedges der ANDEREN PCs am
            # selben Hedge-Konto tragen Familien-Magics und sind kein Alarm.
            fremde = []
            try:
                for p_ in (mt5.positions_get() or []):
                    mg = int(getattr(p_, "magic", 0) or 0)
                    if 770000 <= mg <= 779999:
                        continue
                    fremde.append({"ticket": int(p_.ticket), "symbol": str(p_.symbol),
                                   "type": int(p_.type), "volume": float(p_.volume)})
            except Exception:
                fremde = None
            hedge_acc["fremde"] = fremde
            # USD-Kurs der Hedge-Waehrung fuer die Symmetrie-Anzeige (15.08.2026,
            # Finns Live-Symmetrie): Hedge fuehrt EUR, Master USD — ohne Kurs
            # waere das Verhaeltnis um den EURUSD-Abstand verzerrt. Fehlt das
            # FX-Symbol, bleibt der Wert None und das Frontend laesst das
            # Prozent einfach weg ('Beweis oder leer', nie raten).
            hedge_acc["usd_rate"] = None
            _hcur = hedge_acc.get("currency")
            if _hcur == "USD":
                hedge_acc["usd_rate"] = 1.0
            elif _hcur in ("EUR", "GBP", "AUD", "NZD"):
                _t = mt5.symbol_info_tick(_hcur + "USD")
                if _t is not None and _t.bid:
                    hedge_acc["usd_rate"] = float(_t.bid)

            # ── Jeden Master abarbeiten ─────────────────────────────────────────
            for m in masters:
                # Ohne expect_login lesen und SELBST vergleichen (15.08.2026, erster
                # Trade-Test): das Terminal oeffnete mit fremdem Konto 437916, der
                # expect_login-Filter machte den Snapshot still zu None — im Preflight
                # stand nur 'warte auf Snapshot' statt der Wahrheit. Der Mismatch muss
                # LAUT werden (note + wrong_login), kopiert wird dabei weiterhin nichts.
                snap_path = os.path.join(common, m.snapshot_file)
                snap = read_snapshot(snap_path)
                if snap is not None and m.master_login and int(snap["login"]) != int(m.master_login):
                    # Anklage nur mit LEBENDEM Beweis (Review-Fund 15.08.2026): eine
                    # alte Fremd-Datei ueberlebt Terminal-Kill und Kontowechsel — ohne
                    # mtime-Gate wuerde 'im FALSCHEN Konto eingeloggt' behauptet,
                    # obwohl laengst nichts mehr (oder das richtige Konto) laeuft,
                    # und das Panel wuerde das heilende Terminal erneut killen.
                    try:
                        file_fresh = (time.time() - os.path.getmtime(snap_path)) <= 15
                    except OSError:
                        file_fresh = False
                    if not file_fresh:
                        snap = None  # stale Fremd-Datei ist kein Beweis → 'warte auf Snapshot'
                if snap is not None and m.master_login and int(snap["login"]) != int(m.master_login):
                    if now - m.last_status > 3.0:
                        m.last_status = now
                        if os.path.exists(m.cfg_path):
                            known = book.get(m.magic, {})
                            st = master_status(m, None, known, False)
                            st["note"] = (f"Master-Terminal ist im FALSCHEN Konto eingeloggt: "
                                          f"{snap['login']} statt {m.master_login} — Trade in "
                                          f"Prophos neu starten, der Start loggt das Terminal "
                                          f"automatisch richtig ein.")
                            # Falscher Login ist nie Standby — das Terminal LAEUFT ja,
                            # nur im falschen Konto (25.08.2026).
                            st["standby"] = False
                            st["wrong_login"] = snap["login"]
                            write_status(m.status_path, st)
                    continue
                if snap is None:
                    if now - m.last_status > 3.0:
                        m.last_status = now
                        # Existenz-Check (15.08.2026): zwischen Panel-/api/delete und
                        # der Restart-Erkennung liegen bis zu 2 s — ein Tick-Write in
                        # diesem Fenster wuerde die geloeschte Status-Datei wieder anlegen.
                        if os.path.exists(m.cfg_path):
                            # Die real bekannten Hedges MITSCHREIBEN (Review-Fund
                            # 15.08.2026): ohne Snapshot sind leere Listen kein
                            # Beweis fuer 'flach', sondern Unwissen — und der
                            # Loesch-Riegel des Panels wuerde eine Instanz mit
                            # offenen Hedges sonst fuer leer halten. book ist hier
                            # garantiert frisch (Tick waere sonst uebersprungen).
                            known = book.get(m.magic, {})
                            write_status(m.status_path, master_status(m, None, known, False))
                    continue

                hedges = book.get(m.magic, {})

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

                # ── Schwund-Waechter (15.08.2026, Etappe 3) ─────────────────────
                # Schrumpft der Hedge-Bestand eines ident OHNE eigenen bestaetigten
                # Close (Stop-Out, Hand-Close im Terminal), wird das als
                # 'extern_geschlossen' markiert — Prophos laesst den Hedge-P&L
                # dann bewusst LEER statt eine plausible falsche Summe zu zeigen.
                # own_close_mark wird beim eigenen Close gesetzt; der Schwund
                # daraus erscheint im naechsten Tick (~0,5 s) und wird ueber das
                # frische Mark erkannt.
                # Schluessel als str: die Baseline kommt JSON-persistiert aus dem
                # Sidecar zurueck (Neustart-Fall) und JSON kennt nur str-Keys.
                cur_vol = {str(i): sum(h["volume"] for h in hs) for i, hs in hedges.items() if hs}
                for ident_, prev_v in m.hedge_last_vol.items():
                    now_v = cur_vol.get(ident_, 0.0)
                    if now_v < prev_v - TOL:
                        try:
                            ident_i = int(ident_)
                        except (TypeError, ValueError):
                            ident_i = ident_
                        mark = m.own_close_mark.pop(ident_i, 0)
                        if time.time() - mark > 30:
                            log(f"⚠ [{m.file}] Hedge-Bestand von Master-Pos {ident_} extern "
                                f"geschrumpft ({prev_v} → {now_v}) — Stop-Out oder Hand-Close "
                                f"im Terminal? P&L dieses Trades ist nicht mehr beweisbar.")
                            m.closed.append({"ident": ident_i, "note": "extern_geschlossen",
                                             "profit": None,
                                             "closed_at": datetime.now().isoformat(timespec="seconds")})
                            del m.closed[:-50]
                if cur_vol != m.hedge_last_vol:
                    # Baseline persistieren, damit der Waechter Neustarts ueberlebt —
                    # nur bei Aenderung, nicht jeden 0,5-s-Tick.
                    m.hedge_last_vol = cur_vol
                    write_closed(m.closed_path, m.closed, m.hedge_last_vol)

                actions, warns = plan_actions(
                    snap["positions"], hedges,
                    multiplier=m.multiplier, symbol_map=m.symbol_map,
                    sym_info=sym_info, skip_idents=(m.startup_skip or frozenset()))

                for w in warns:
                    if w not in m.warned:
                        log(f"⚠ [{m.file}] {w} — uebersprungen.")
                        m.warned.add(w)

                # Guard-Reset: NUR wenn der erkannte Bestand seit dem letzten
                # Sendeversuch GEWACHSEN ist, ist die Order angekommen und
                # wiedererkannt. (Nicht "ident hat irgendeinen Hedge" — beim
                # Aufstocken haette der Alt-Hedge den Zaehler dauernd geloescht
                # und der Mehrfach-Hedge-Schutz waere ausgehebelt gewesen.)
                for ident, hs in hedges.items():
                    ref = m.open_seen.get(ident)
                    if ref is None or sum(h["volume"] for h in hs) > ref + TOL:
                        m.open_done.pop(ident, None)
                        m.open_fail.pop(ident, None)
                        m.open_seen.pop(ident, None)

                for a in actions:
                    ident = a["ident"]
                    if a["kind"] == "open":
                        if ident in m.blocked:
                            continue
                        # Cooldown waechst mit Fehlversuchen (3s -> 30s): bei
                        # Internet-Ausfall wird geduldig weiterprobiert statt
                        # aufzugeben. Eine abgelehnte Order erzeugt kein Duplikat;
                        # der Restfall "Order kam an, Bestaetigung ging im Ausfall
                        # verloren" heilt sich selbst: sobald die Position im
                        # Bestand auftaucht, deckt sie das Soll (kein Nachschuss),
                        # und ein Zuviel wird von plan_actions als Ueberhang
                        # geschlossen.
                        cool = OPEN_COOLDOWN * (1 + min(9, m.open_fail.get(ident, 0)))
                        if time.time() - m.open_last.get(ident, 0) < cool:
                            continue
                        # Echte Mehrfach-Hedge-Gefahr: Order war BESTAETIGT (DONE),
                        # der Bestand ist aber seither nicht gewachsen (z.B. Broker
                        # veraendert den Kommentar). Nur DAS blockiert dauerhaft.
                        if m.open_done.get(ident, 0) >= OPEN_MAX_TRIES:
                            m.blocked.add(ident)
                            log(f"⛔ [{m.file}] Master-Pos {ident}: {OPEN_MAX_TRIES}x Order bestaetigt, "
                                f"aber Hedge nie wiedererkannt — gestoppt (Schutz gegen "
                                f"Mehrfach-Hedge). Im Hedge-Terminal pruefen.")
                            continue
                        m.open_last[ident] = time.time()
                        # Referenzvolumen VOR dem Send merken — daran erkennt der
                        # Guard-Reset oben, ob dieser Versuch angekommen ist.
                        m.open_seen[ident] = sum(h["volume"] for h in hedges.get(ident, []))
                        ok = open_hedge(m, ident, a["symbol"],
                                        0 if a["hedge_type"] == 1 else 1,  # Master-Typ zurueckrechnen
                                        a["volume"])
                        if ok:
                            m.open_done[ident] = m.open_done.get(ident, 0) + 1
                            m.open_fail.pop(ident, None)
                        else:
                            f = m.open_fail[ident] = m.open_fail.get(ident, 0) + 1
                            if f == 1:
                                log(f"↻ [{m.file}] Master-Pos {ident}: Order nicht durchgekommen — "
                                    f"es wird weiterversucht (Abstand waechst bis 30s), z.B. bei "
                                    f"kurzem Internet-Ausfall voellig normal.")
                    else:
                        # Auch Closes mit Cooldown wiederholen: waehrend eines
                        # Ausfalls schlaegt der Close fehl — kein Grund zur
                        # Panik, der naechste Versuch nach Reconnect sitzt.
                        if time.time() - m.close_last.get(a["ticket"], 0) < OPEN_COOLDOWN:
                            continue
                        m.close_last[a["ticket"]] = time.time()
                        open_pos = next((h for h in hedges.get(ident, [])
                                         if h["ticket"] == a["ticket"]), None)
                        res = close_part(m, open_pos, a["volume"]) if open_pos else None
                        if res:
                            m.close_last.pop(a["ticket"], None)
                            m.open_done.pop(ident, None); m.open_last.pop(ident, None)
                            m.open_seen.pop(ident, None)
                            m.blocked.discard(ident)
                            # Eigener bestaetigter Close: dem Schwund-Waechter
                            # melden (sonst saehe der naechste Tick den Schwund
                            # und stempelte ihn 'extern') und den Deal aus dem
                            # Result verbuchen (15.08.2026, Etappe 3)
                            m.own_close_mark[ident] = time.time()
                            book_close(m, ident, open_pos, res, a["volume"])

                # busy = dieser Master hat offene Positionen ODER offene Hedges —
                # solange wird kein Selbst-Update-Neustart ausgefuehrt.
                m.busy = bool(snap["positions"]) or bool(hedges)

                if time.time() - m.last_status > 3.0:
                    m.last_status = time.time()
                    # Existenz-Check wie oben (15.08.2026): keine geloeschte
                    # Status-Datei im 2-s-Fenster wieder anlegen.
                    if os.path.exists(m.cfg_path):
                        write_status(m.status_path, master_status(m, snap, hedges, True))

            time.sleep(poll)
    except KeyboardInterrupt:
        log("Gestoppt.")
    finally:
        for m in masters:
            # Geloeschte Config (Panel /api/delete, 15.08.2026): die Status-Datei
            # nicht wieder anlegen — der Loesch-Endpunkt hat sie gerade entfernt.
            if not os.path.exists(m.cfg_path):
                continue
            write_status(m.status_path, {"running": False})
        mt5.shutdown()


if __name__ == "__main__":
    main()
