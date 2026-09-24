#!/usr/bin/env python3
"""
Echo (Prophos) — MT5-Hedge-Executor: EIN Prozess bedient ALLE Master-Konten dieses PCs.

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
from datetime import datetime, timezone

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


# ── Echo-Pause (28.08.2026, Finns Not-Aus-Knopf) ───────────────────────────────
# Ein Klick in Prophos legt/entfernt die Datei echo_pause.flag im Copier-Ordner
# (Panel /api/pause). Existiert sie, stoppt der Copier NUR NEUE Aktionen: keine
# neuen Hedges (Opens) und keine neuen Notfall-SL/TP-Modifies. Bewusst NICHT
# betroffen: Closes (eigene Hedges abbauen ist nie falsch, genau wie ausserhalb
# des Trade-Fensters) — laufende Hedges bleiben also offen und werden weiter
# sauber geschlossen, wenn der Master zugeht. Der Order-Bot liest dieselbe Datei.
_PAUSE_FLAG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "echo_pause.flag")


def is_paused():
    return os.path.exists(_PAUSE_FLAG)


_REPO = "finntraidingview-cmd/Prophos"


def _repo_sha(timeout=8):
    """Kennung des neuesten Commits auf main (Git-Schnittstelle, kein Zwischenspeicher) — oder None."""
    try:
        req = urllib.request.Request(f"https://github.com/{_REPO}.git/info/refs?service=git-upload-pack",
                                     headers={"User-Agent": "git/2.40"})
        roh = urllib.request.urlopen(req, timeout=timeout).read()
        m = re.search(rb"([0-9a-f]{40}) refs/heads/main", roh)
        return m.group(1).decode("ascii") if m else None
    except Exception:
        return None


def _copier_code_geaendert():
    """Wuerde ein Neustart den LAUFENDEN Copier-Code aendern? copier.py aus GENAU dem
    neuesten Stand (Commit-Kennung) gegen die laufende Datei. True auch bei
    Unsicherheit (kein Netz) — dann gilt der alte Weg: Neustart."""
    sha = _repo_sha()
    if not sha:
        return True
    try:
        neu = urllib.request.urlopen(f"https://raw.githubusercontent.com/{_REPO}/{sha}/mt5-copier/copier.py",
                                     timeout=10).read()
        if len(neu) < 10000 or b"def main" not in neu:
            return True
        with open(os.path.abspath(__file__), "rb") as f:
            alt = f.read()
        glatt = lambda b: b.replace(b"\r\n", b"\n").lstrip(b"\xef\xbb\xbf").strip()
        return glatt(neu) != glatt(alt)
    except Exception:
        return True


def _version_uebernehmen(version):
    """VERSION-Datei nachziehen, ohne Neustart."""
    try:
        ziel = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
        with open(ziel + ".tmp", "w", encoding="utf-8") as f:
            f.write(version + "\n")
        os.replace(ziel + ".tmp", ziel)
    except OSError:
        pass


def _version_watcher():
    # NUR neu starten, wenn copier.py sich wirklich geaendert hat (23.09.2026, Finn:
    # "bei Echo wird auf manchen PCs immer wieder das Slave-Terminal nach vorn geholt").
    # Jeder VERSION-Bump — in Finns Testnacht 12 in 100 min, fast alle nur Frontend —
    # startete den Copier auf jedem PC mit flachen Mastern neu, und jeder Start haengt
    # sich per initialize() ans Hedge-Terminal, was dessen Fenster nach vorn reisst.
    # Gleicher Code im neuesten Commit → nur die VERSION-Datei nachziehen.
    # _REMOTE_VERSION["neustart"] traegt die Entscheidung in die Hauptschleife.
    while True:
        try:
            with urllib.request.urlopen(UPDATE_URL, timeout=10) as r:
                remote = r.read().decode("utf-8", "replace").strip()
            lokal = local_version()
            if remote and lokal and remote != lokal:
                if _copier_code_geaendert():
                    _REMOTE_VERSION.update(v=remote, neustart=True)
                else:
                    _version_uebernehmen(remote)
                    log(f"↻ Update {lokal} → {remote}: copier.py unveraendert — kein Neustart, "
                        f"VERSION nachgezogen.")
                    _REMOTE_VERSION.update(v=remote, neustart=False)
            else:
                _REMOTE_VERSION["v"] = remote
        except Exception:
            pass  # kein Internet o.ae. — einfach beim alten Stand bleiben
        time.sleep(60)

# ── Hedge-Terminal-Fenster: Vordergrund nach initialize() zurueckgeben (23.09.2026) ──
# Umbau 24.09.2026 (Finn: "bei manchen PCs wird immer wieder das Echo-Slave-Terminal
# in den Vordergrund geholt — aus dem Nichts"): die erste Fassung prueft GENAU EINMAL,
# direkt nachdem initialize() zurueckkam. Zwei Luecken: (1) das Terminal aktiviert
# sein Fenster oft erst kurz DANACH (Konto-Sync nach dem IPC-Anschluss) — der Check
# sah noch das alte Vordergrundfenster und tat nichts; (2) die Fenster-Erkennung lief
# ueber provision.terminal_pids und damit ueber wmic, das auf Windows 11 24H2+ fehlt —
# dort war die Liste immer leer, die Rueckgabe totes Recht. Jetzt: Fenster werden
# ueber den Exe-Pfad ihres Prozesses erkannt (Win32, ohne wmic), und ein Waechter
# beobachtet einige Sekunden lang und stellt jedes Nach-vorn-Reissen zurueck.
def _fenster_pfad(hwnd):
    """Exe-Pfad des Prozesses hinter einem Fenster (Windows) oder None."""
    try:
        import ctypes
        import ctypes.wintypes as wt
        import provision
        pid = wt.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return provision.prozess_pfad(pid.value) if pid.value else None
    except Exception:
        return None


def _hedge_fenster(hpath):
    """Sichtbare Hauptfenster der terminal64.exe DIESER Hedge-Installation:
    [(hwnd, minimiert)] — leer, wenn kein Windows / kein Pfad / nichts laeuft.
    Erkennung ueber den Exe-Pfad des Fensterprozesses; PIDs aus
    provision.terminal_pids nur noch als zweites Kriterium."""
    if os.name != "nt" or not hpath:
        return []
    try:
        import ctypes
        import ctypes.wintypes as wt
        import provision
        u32 = ctypes.windll.user32
        want = os.path.normcase(os.path.normpath(os.path.dirname(os.path.abspath(hpath))))
        pids = set(provision.terminal_pids(os.path.dirname(os.path.abspath(hpath))))
        pfad_cache = {}
        out = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
        def _cb(h, _lp):
            try:
                if not u32.IsWindowVisible(h) or u32.GetWindow(h, 4):   # GW_OWNER: nur Hauptfenster
                    return True
                if u32.GetWindowTextLengthW(h) <= 0:
                    return True
                pid = wt.DWORD()
                u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                if pid.value in pids:
                    out.append((int(h), bool(u32.IsIconic(h))))
                    return True
                if pid.value not in pfad_cache:
                    pfad_cache[pid.value] = provision.prozess_pfad(pid.value)
                pfad = pfad_cache[pid.value]
                if pfad and os.path.basename(pfad).lower() == "terminal64.exe" and \
                   os.path.normcase(os.path.normpath(os.path.dirname(pfad))) == want:
                    out.append((int(h), bool(u32.IsIconic(h))))
            except Exception:
                pass
            return True
        u32.EnumWindows(_cb, 0)
        return out
    except Exception:
        return []


def _vordergrund_merken(hpath):
    if os.name != "nt":
        return None
    try:
        import ctypes
        vorn = int(ctypes.windll.user32.GetForegroundWindow() or 0)
        return {"vorn": vorn, "hedge": dict(_hedge_fenster(hpath)), "hpath": hpath}
    except Exception:
        return None


def _vordergrund_geben(u32, ziel):
    """Einem anderen Fenster den Vordergrund geben, obwohl Windows das nur dem
    aktuellen Vordergrund-Thread erlaubt: unseren Thread an den Thread des
    aktuellen Vordergrundfensters haengen (AttachThreadInput), dann setzen.
    Rueckfall: Alt-Tastendruck (gibt den Foreground-Lock frei, wie im Panel)."""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        vorn = u32.GetForegroundWindow()
        mein = k32.GetCurrentThreadId()
        fremd = u32.GetWindowThreadProcessId(vorn, None) if vorn else 0
        angehaengt = bool(fremd and fremd != mein and u32.AttachThreadInput(fremd, mein, True))
        try:
            u32.SetForegroundWindow(ziel)
        finally:
            if angehaengt:
                u32.AttachThreadInput(fremd, mein, False)
        if int(u32.GetForegroundWindow() or 0) == int(ziel):
            return True
        u32.keybd_event(0x12, 0, 0, 0); u32.keybd_event(0x12, 0, 2, 0)   # Alt druecken/loslassen
        u32.SetForegroundWindow(ziel)
        return int(u32.GetForegroundWindow() or 0) == int(ziel)
    except Exception:
        return False


def _vordergrund_zurueck(vorher, dauer_s=0.0):
    """Hat initialize() das Hedge-Terminal nach vorn geholt? Dann zurueck in den
    Zustand von vorher: war es minimiert (oder vorher gar nicht sichtbar) → wieder
    minimieren; sonst hinter alle anderen Fenster, und dem vorherigen Fenster den
    Vordergrund zurueckgeben. Stand das Terminal schon vorher vorn (Finn arbeitet
    gerade darin), passiert nichts. dauer_s > 0: so lange beobachten (alle 0,2 s)
    und JEDES Nach-vorn-Reissen in dem Fenster zuruecknehmen — das Terminal
    aktiviert sich nach dem IPC-Anschluss oft erst mit Verzoegerung, und manchmal
    zweimal. Liefert die Zahl der Eingriffe."""
    if not vorher or os.name != "nt":
        return 0
    eingriffe = 0
    try:
        import ctypes
        u32 = ctypes.windll.user32
        alt_vorn = int(vorher.get("vorn") or 0)
        ende = time.time() + max(0.0, float(dauer_s))
        while True:
            jetzt = dict(_hedge_fenster(vorher.get("hpath")))
            vorn = int(u32.GetForegroundWindow() or 0)
            if vorn in jetzt and vorn != alt_vorn:
                war_min = vorher.get("hedge", {}).get(vorn)
                if war_min or vorn not in vorher.get("hedge", {}):
                    u32.ShowWindow(vorn, 6)                       # SW_MINIMIZE
                    wie = "wieder minimiert"
                else:
                    # HWND_BOTTOM=1, SWP_NOSIZE|SWP_NOMOVE|SWP_NOACTIVATE = 0x0013
                    u32.SetWindowPos(vorn, 1, 0, 0, 0, 0, 0x0013)
                    wie = "nach hinten gestellt"
                if alt_vorn and u32.IsWindow(alt_vorn):
                    _vordergrund_geben(u32, alt_vorn)
                eingriffe += 1
                if eingriffe == 1:
                    log(f"Hedge-Terminal kam durch initialize() nach vorn — {wie}, "
                        f"Vordergrund zurueckgegeben.")
            if time.time() >= ende:
                break
            time.sleep(0.2)
    except Exception:
        pass
    return eingriffe


def _vordergrund_waechter_starten(vorher, dauer_s=8.0):
    """_vordergrund_zurueck im Hintergrund, damit der Copier-Start nicht wartet."""
    if not vorher or os.name != "nt":
        return None
    t = threading.Thread(target=_vordergrund_zurueck, args=(vorher, dauer_s),
                         name="vordergrund-waechter", daemon=True)
    t.start()
    return t


# Dieselbe Namensregel wie im Panel (panel.py) — bewusst streng, damit
# Explorer-Kopien wie "config - Kopie.json" oder "config (2).json" NICHT als
# Instanz durchgehen (Audit-Fund 13.08.2026: solche Karten sahen echt aus,
# steuerten aber nichts).
CONFIG_RE = re.compile(r"config(?:[-_][A-Za-z0-9]{1,24})?\.json", re.I)
TEMPLATES = ("config.example.json", "config.fusion-test.json")


_LOG_RING = []
# Globaler Log-Spiegel (26.08.2026, Finns Wunsch: die CMD-Meldungen direkt in
# Prophos lesen koennen). Anders als die status-*.json lebt diese Datei auch
# dann, wenn der Copier beim START abbricht (Flotten-Konflikt, Konto-Guard) —
# genau die Faelle, in denen das CMD bisher die einzige Fehlerquelle war.
_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "copier-log.json")


def _log_datei_schreiben():
    try:
        tmp = _LOG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"lines": _LOG_RING[-120:], "pid": os.getpid(),
                       "updated_at": datetime.now().isoformat(timespec="seconds")},
                      f, ensure_ascii=False)
        for _ in range(3):
            try:
                os.replace(tmp, _LOG_PATH)
                return
            except PermissionError:
                time.sleep(0.05)   # Leser-Kollision (Panel) — immer transient
    except Exception:
        pass


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    _LOG_RING.append(line)
    if len(_LOG_RING) > 200:
        del _LOG_RING[:-200]
    _log_datei_schreiben()


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
        # os.replace mit Retry (25.08.2026, Finns Live-Log: sporadischer
        # WinError 5): Windows verweigert das Ersetzen, solange ein Leser die
        # Zieldatei offen hat — Panel UND Prophos pollen die Status-Dateien
        # alle ~3 s, die Kollision ist also normal und IMMER transient
        # (Lesevorgang < 1 ms). Ohne Retry fiel der ganze Write aus, die Karte
        # wurde 3 s blind und die Bot-Freigabe (alive-Check) verzoegerte sich.
        last = None
        for _ in range(5):
            try:
                os.replace(tmp, path)
                return
            except PermissionError as e:
                last = e
                time.sleep(0.05)
        raise last
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
    """Liefert (closed_ring, last_vol, last_tickets). last_vol ist die
    persistierte Schwund-Waechter-Baseline {ident(str): Gesamtvolumen} — ohne
    sie waere der Waechter nach jedem Neustart blind und ein extern
    geschlossener Hedge in der Copier-Downtime ergaebe spaeter eine plausible
    falsche closed_sum (Review-Fund 15.08.2026). last_tickets {ident(str):
    [Tickets]} kam am 27.08.2026 dazu (Notfall-SL/TP): nur ueber die Tickets
    kann der Waechter nach einem Schwund in der Deal-History nachschlagen, OB
    der Broker auf unserem eigenen Notfall-Level geschlossen hat — auch wenn
    der Fill in eine Copier-Downtime fiel. Alte Formate (reine Liste, dict
    ohne tickets) werden toleriert."""
    try:
        data = load_json(path)
        if isinstance(data, list):
            return data, {}, {}
        if isinstance(data, dict):
            closed = data.get("closed")
            lv = data.get("last_vol")
            lt = data.get("last_tickets")
            return (closed if isinstance(closed, list) else []), \
                   ({str(k): float(v) for k, v in lv.items()} if isinstance(lv, dict) else {}), \
                   ({str(k): [int(t) for t in v] for k, v in lt.items()} if isinstance(lt, dict) else {})
        return [], {}, {}
    except Exception:
        return [], {}, {}


def write_closed(path, entries, last_vol=None, last_tickets=None):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"closed": entries[-50:], "last_vol": last_vol or {},
                       "last_tickets": last_tickets or {}},
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


# ── Gezielter Magic-Umzug (11.09.2026, Jakobs The5ers-Vorfall) ─────────────────
# Live-Fund 10./11.09.2026: Hedges der Master 26674215/26674216 wurden am
# GEMEINSAMEN Fusion-Hedge-Konto sofort wieder geschlossen (oeffnen → fremd-
# schliessen → oeffnen → …, danach griffen Hand-Close-Sperre bzw. Mehrfach-
# Hedge-Schutz und es wurde gar nicht mehr gehedgt). Ursache: ein Copier auf
# einem ANDEREN PC traegt dieselbe magic — alle PCs vergeben ab dem Default-
# Block 770000, die magic_base-Bloecke aus provision.py wurden nie pro PC
# gesetzt. Das ist exakt der check_fleet-Fall "gleiche magic → Copier
# schliessen sich gegenseitig die Hedges", nur PC-uebergreifend, wo keine
# Startpruefung hinsieht. Finns Ansage: NUR diese zwei Accounts anfassen,
# sonst nichts — deshalb eine feste Liste statt einer Flotten-Umstellung.
# Ziel = 779000er-Block, aus dem Login abgeleitet: bleibt in der Prophos-
# Familie 770000-779999 (hedge_fremde zaehlt weiter richtig) und kollidiert
# weder mit Bestand noch mit einer kuenftigen Block-Vergabe (779000 waere
# erst der zehnte PC).
MAGIC_UMZUG = {26674215: 779215, 26674216: 779216}

# Prophos-Magic-Familie am geteilten Hedge-Konto: alles in diesem Bereich gilt
# als "einer von uns" (anderer PC der Flotte) und loest keinen hedge_fremde-
# Alarm aus. 11.09.2026 nachmittags nach UNTEN auf 760000 erweitert (Finns
# Flotten-Umzug: alle 7 Bestands-PCs haben 770000-776000 belegt, 777/778 sind
# die letzten freien Bloecke) — nach unten, damit Bestand UND 779er-Umzugs-
# Reservat exakt unangetastet bleiben. Neue PC-Bloecke ab jetzt in dieser
# Reihenfolge: 777000, 778000, dann 760000, 761000, … 769000.
FAMILIE_MIN = 760000
FAMILIE_MAX = 779999

# ── Eigenstaendige Fusion-Position („Solo-Hedge", 24.09.2026 abends) ──────────
# Finn: „Winning Days jetzt gegenhedgen, ohne Duplikum: Puls platziert in
# TradingView, direkt danach geht auf Fusion die Gegen-Order im Verhaeltnis rein,
# und sobald NQ den Take Profit (+ 2–3 Punkte) erreicht, wird sie geschlossen."
# Die Position gehoert zu KEINEM Master-Snapshot — deshalb eine magic AUSSERHALB
# der Familie 760000–779999: kein Copier auf keinem PC am geteilten Fusion-Konto
# haelt sie fuer einen eigenen Hedge ohne Master und schliesst sie (hedge_book
# filtert nach fleet_magics UND Kommentar '<prefix>-<Ziffern>'; der Kommentar
# hier traegt bewusst keinen Bindestrich-Ziffern-Block). Befehle kommen vom
# Panel per Datei (dasselbe Muster wie plans.json/echo_pause.flag): das Panel
# schreibt hedge_solo_auftrag.json, der Copier arbeitet pro Tick ab und legt das
# Ergebnis in hedge_solo_ergebnis.json — EIN Prozess am Hedge-Terminal, wie
# README.md verlangt (zwei Python-Prozesse am selben Terminal sind nicht stabil).
SOLO_MAGIC = 790001
SOLO_KOMMENTAR = "PXsolo"
SOLO_KOMMENTAR_MAX = 31    # MT5: Order-Kommentar hoechstens 31 Zeichen


def solo_kommentar(plan_id):
    """REIN RECHNEND (testbar): Order-Kommentar der Solo-Position, 25.09.2026 (Koordination: Finns Fusion-Konto
    488579 ist zwischen allen PCs geteilt; hedge_solo zeigte alle Solo-Positionen ohne Zuordnung, ein verpasster
    oder verlorener Hedge — Jacobs Plan 2089a033 — war nicht sicher wiederzufinden). 'PXsolo:<plan8>' mit den
    ersten 8 Zeichen der plan_id (nur [0-9a-zA-Z-]), ohne plan_id wie bisher 'PXsolo'. Erkennung eigener
    Positionen bleibt die magic 790001 — der Kommentar ist nur Zusatz (manche Broker kuerzen/ueberschreiben ihn)."""
    p8 = re.sub(r"[^0-9A-Za-z-]", "", str(plan_id or ""))[:8]
    return (f"{SOLO_KOMMENTAR}:{p8}" if p8 else SOLO_KOMMENTAR)[:SOLO_KOMMENTAR_MAX]


def solo_plan8(kommentar):
    """REIN RECHNEND (testbar): plan8 aus einem Solo-Kommentar ('PXsolo:2089a033' → '2089a033'); alte 'PXsolo'
    ohne Kennung, der Close-Kommentar 'PXsoloc' und Fremdes → None."""
    m = re.match(r"^PXsolo:([0-9A-Za-z-]{1,8})", str(kommentar or "").strip())
    return m.group(1) if m else None
SOLO_AUFTRAG = "hedge_solo_auftrag.json"
SOLO_ERGEBNIS = "hedge_solo_ergebnis.json"
SOLO_MAX_ALTER_S = 40.0        # aeltere Auftraege werden verworfen, nie verspaetet ausgefuehrt
SOLO_ERGEBNIS_MAX = 100        # Ring der letzten Ergebnisse (= Erledigt-Liste, neustart-fest)


def solo_lots(eur, punkte, wert_pro_punkt, si):
    """REIN RECHNEND (testbar): Lots fuer „eur Euro Risiko ueber punkte Punkte".
    wert_pro_punkt = Kontowaehrung je Punkt je Lot (tick_value / tick_size beim
    Broker). Ergebnis auf das Broker-Raster (norm_vol); 0.0 = unter Mindestlot."""
    if not (float(eur) > 0 and float(punkte) > 0 and float(wert_pro_punkt) > 0):
        return 0.0
    return norm_vol(si, float(eur) / (float(punkte) * float(wert_pro_punkt)))


def solo_lots_waehlen(lots_roh, eur, punkte, wert_pro_punkt, si):
    """REIN RECHNEND (testbar): Lots fuer den Solo-Open. Schickt das Frontend
    lots explizit (Popup 1 klassischer Multiplikator: Kontrakte × Multiplikator,
    z. B. 0,94 — Koordination 24.09.2026 spaet), werden sie auf das Broker-Raster
    gebracht (norm_vol: volume_step, min, max) statt roh gesendet; sonst wie
    bisher aus eur / (punkte × Punktwert). -> (lots_gesendet, lots_angefragt,
    quelle 'lots'|'eur'); 0.0 = unter Mindestlot / nicht rechenbar."""
    roh = float(lots_roh or 0)
    if roh > 0:
        return norm_vol(si, roh), roh, "lots"
    return solo_lots(eur or 0, punkte or 0, wert_pro_punkt, si), None, "eur"


def solo_notfall_sl(fill, richtung, punkte, *, faktor, point, digits, puffer=0.0):
    """REIN RECHNEND (testbar): NOTFALL-SL der Solo-Position im Terminal — Finn (25.09.2026,
    Koordination): „Die Fusion-Position erst schliessen, wenn der Preis 8 Ticks ueber dem
    Master-TP ist — und zusaetzlich auf dem Slave im Notfall ein Stop-Loss bei 110 % vom
    Master-Take-Profit, wie bei der alten Logik." Der NORMALWEG ist seit .5xx wieder der
    Waechter im PC-Tab ueber den (jetzt sekuendlichen) NQ-Feed: er schickt den Close-Auftrag
    mit grund 'tp_feed'/'sl_feed'. Dieses Level hier ist das Sicherheitsnetz dahinter:
    Distanz = punkte × faktor (Standard 1,10), nie naeher als punkte + 1 Punkt — sonst
    fuellte der Notfall-SL VOR dem Waechter. puffer bleibt als Alt-Parameter (0.5xx: Distanz
    = punkte + puffer) und wird nur genommen, wenn kein Faktor da ist.
    richtung = Richtung der HEDGE-Order: SELL-Hedge verliert bei steigendem Kurs → SL ueber
    dem Fill, BUY-Hedge darunter. Kein Master-SL → kein TP am Hedge (solo_level_tp)."""
    if not (float(fill) > 0 and float(punkte) > 0):
        return 0.0
    p = float(punkte)
    if faktor is not None and float(faktor) > 0:
        dist = max(p * float(faktor), p + 1.0)
    else:
        dist = p + max(0.0, float(puffer or 0))
    lvl = float(fill) + dist if str(richtung).lower() == "sell" else float(fill) - dist
    return max(round(lvl, int(digits)), float(point))


def solo_level_tp(fill, richtung, sl_punkte, *, puffer, point, digits):
    """REIN RECHNEND (testbar): Reserve-Level (TP am Hedge) fuer den Fall, dass der MASTER
    seinen SL erreicht. Entscheidung Koordination 25.09.2026: auf der Master-SL-Seite ist der
    Feed-Waechter im PC-Tab der HAUPTWEG (schliesst bei Kurs = Master-SL, ohne Puffer — Finn:
    „am SL des Masters genauso"); dieses Terminal-Level ist NUR die Reserve dahinter und muss
    deshalb HINTER dem Master-SL liegen: Distanz = sl_punkte + puffer. Die Fassung davor
    (sl_punkte − puffer) lag DAVOR — Fusion haette vor dem Master-SL geschlossen, und bei einer
    Umkehr stuende der Master ungehedgt. SELL-Hedge gewinnt bei fallendem Kurs → TP unter dem
    Fill; BUY-Hedge darueber. 0.0 = kein Level (kein Master-SL)."""
    if not (float(fill) > 0 and float(sl_punkte or 0) > 0):
        return 0.0
    dist = float(sl_punkte) + max(0.0, float(puffer or 0))
    lvl = float(fill) - dist if str(richtung).lower() == "sell" else float(fill) + dist
    return max(round(lvl, int(digits)), float(point))


def kerze_fortschreiben(k1m, k1m_vor, wurzel, symbol, preis, jetzt_s):
    """REIN RECHNEND (testbar): (laufende Kerze, letzte abgeschlossene) nach einem
    Tick — dieselbe Form wie kurs_1m im reader-server (o/h/l/c/n, minute = Anfang
    der Minute in Server-UTC-Sekunden), damit das Frontend beide Quellen mit
    derselben Bruecke nach tv_kurs_1m schreiben kann (Spalte wurzel trennt sie).
    Zweiter Kurs-Feed (Koordination 24.09.2026 spaet): der Copier hat den NAS100-
    Tick ohnehin — EHRLICH: NAS100 ist ein CFD, laeuft parallel zu NQ mit Basis-
    Abstand und anderen Handelszeiten. Fuer den Hedge ist es der richtige Kurs
    (die Level liegen beim Broker), fuer NQ-Demo-Orders nur 'ungefaehr'."""
    minute = int(jetzt_s // 60) * 60
    p = float(preis)
    if k1m and k1m.get("minute") == minute and k1m.get("wurzel") == wurzel:
        k1m["h"] = max(k1m["h"], p)
        k1m["l"] = min(k1m["l"], p)
        k1m["c"] = p
        k1m["n"] += 1
        return k1m, k1m_vor
    neu = {"minute": minute, "wurzel": wurzel, "symbol": symbol, "o": p, "h": p, "l": p, "c": p, "n": 1}
    return neu, (k1m if k1m else k1m_vor)


def utc_iso():
    """Zeitstempel fuer die Solo-Quittungen/den Abschluss-Ring in UTC mit 'Z' (Review
    24.09.2026 spaet): datetime.now().isoformat() ohne Zeitzone deutete der Mac in
    Dubai als seine Ortszeit — die Karte lag Stunden daneben."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


SOLO_ZU = "hedge_solo_zu.json"      # Ring der selbst erkannten Abschluesse + zuletzt bekannte Tickets (neustart-fest)
SOLO_ZU_MAX = 20


def solo_zu_erkennen(bekannt, aktuell):
    """REIN RECHNEND (testbar): welche Solo-Tickets sind seit dem letzten Tick
    verschwunden? bekannt/aktuell = {ticket: {symbol, lots, richtung, fill}}.
    -> Liste der verschwundenen Eintraege (mit ticket), Reihenfolge nach Ticket.
    Koordination 24.09.2026 spaet: der Copier erkennt den Abschluss der Solo-
    Position SELBST — der PC-Tab (und ueber mt5_live der Mac) sieht 'Level
    gefuellt, −4,20 €, level_tp' auch dann, wenn zwischen Fuellen und dem
    naechsten Waechter-Tick ein Tab-Neustart lag oder nie ein Close-Auftrag kam."""
    out = []
    for t in sorted(int(k) for k in (bekannt or {})):
        if t not in {int(k) for k in (aktuell or {})}:
            e = dict((bekannt.get(t) if t in bekannt else bekannt.get(str(t))) or {})
            e["ticket"] = t
            out.append(e)
    return out


def solo_zu_ring(ring, eintrag, maximum=SOLO_ZU_MAX):
    """REIN RECHNEND (testbar): Eintrag {ticket, …} in den Ring — ein Ticket steht
    nie doppelt (der Erste gewinnt), aelteste fliegen raus, juengster hinten."""
    ring = [r for r in (ring or []) if isinstance(r, dict)]
    if any(int(r.get("ticket") or 0) == int(eintrag.get("ticket") or 0) for r in ring):
        return ring
    ring.append(dict(eintrag))
    return ring[-int(maximum):]


def solo_deal_grund(reason):
    """REIN RECHNEND (testbar): DEAL_REASON des schliessenden Deals → Grund aus
    Sicht des MASTERS. Hedge-SL gefuellt = der Master hat seinen TP erreicht
    ('level_tp'); Hedge-TP gefuellt = Master-SL ('level_sl'); EXPERT = unser
    eigener Close-Auftrag ('close'); CLIENT/MOBILE/WEB = von Hand im Terminal
    ('hand'); SO = Stop-Out ('stopout'); sonst 'unbekannt'."""
    try:
        r = int(reason)
    except (TypeError, ValueError):
        return "unbekannt"
    return {4: "level_tp", 5: "level_sl", 3: "close", 0: "hand", 1: "hand", 2: "hand", 6: "stopout"}.get(r, "unbekannt")


def solo_auftraege_lesen(pfad, erledigt, jetzt):
    """REIN RECHNEND (testbar): offene Auftraege aus der Datei — nur mit cmd_id,
    noch nicht erledigt, juenger als SOLO_MAX_ALTER_S. -> (auftraege, verworfen)"""
    try:
        roh = load_json(pfad)
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError):
        return [], []
    if not isinstance(roh, list):
        return [], []
    offen, verworfen = [], []
    for a in roh:
        if not isinstance(a, dict) or not a.get("cmd_id"):
            continue
        cid = str(a["cmd_id"])
        if cid in erledigt:
            continue
        try:
            alter = float(jetzt) - float(a.get("at") or 0)
        except (TypeError, ValueError):
            alter = 1e9
        if alter > SOLO_MAX_ALTER_S:
            verworfen.append(cid)
            continue
        offen.append(a)
    return offen, verworfen


def magic_umzug_ziel(master_login, magic, belegte_magics):
    """REIN RECHNEND (testbar): neue magic fuer einen Umzugs-Kandidaten oder
    None. Zieht nur um, wenn der Master in MAGIC_UMZUG steht, die alte magic
    noch im Default-Block liegt (< 771000 — schon umgezogene oder bewusst
    hoeher gesetzte Configs bleiben unangetastet) und das Ziel auf DIESEM PC
    frei ist (nie einen neuen lokalen Konflikt erzeugen)."""
    ziel = MAGIC_UMZUG.get(int(master_login or 0))
    if not ziel or int(magic) == ziel or int(magic) >= 771000:
        return None
    if ziel in belegte_magics:
        return None
    return ziel


def plan_armed_files(plans, now):
    """REIN RECHNEND (testbar): welche config-Dateien haben ein offenes
    Trade-Fenster?  Finns Ansage 25.08.2026 (nach der Geisterposition auf dem
    Live-Konto): der Copier soll NICHT 24/7 scharf sein — neue Hedges gibt es
    nur zwischen 'Trade starten' in Prophos (Panel-Plan 'geplant') und dem
    Trade-Ende ('beendet'). Regeln:
      · 'laufend'  → Fenster offen (ein Trade kann Tage laufen)
      · 'geplant'  → Fenster offen, aber nur 6 h ab armed_at — ein vergessener
                     geplanter Plan darf den Master nicht dauerhaft scharf halten
      · alles andere / ohne brauchbare Zeit → Fenster zu
    Closes bleiben IMMER erlaubt (eigene Hedges abbauen ist nie falsch) —
    das Fenster gilt nur fuer OPENS."""
    armed = set()
    for p in plans or []:
        st = p.get("status")
        if st == "laufend":
            armed.add(p.get("file"))
        elif st == "geplant":
            try:
                age = (now - datetime.fromisoformat(str(p.get("armed_at") or ""))).total_seconds()
            except (TypeError, ValueError):
                continue
            if age <= 6 * 3600:
                armed.add(p.get("file"))
    return armed


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
                pos = {
                    "ident": int(f_[1]), "symbol": f_[2], "type": int(f_[3]),
                    "volume": float(f_[4]), "contract_size": float(f_[5]),
                }
            except (IndexError, ValueError):
                return None
            # P-Zeile v5 (27.08.2026, Notfall-SL/TP): Entry/SL/TP hinten
            # angehaengt. Altes EA schreibt 6 Felder — dann bleiben die Werte
            # None ('Beweis oder leer': ein erfundener 0.0-Entry saehe wie ein
            # echter Preis aus und ergaebe falsche Notfall-Level). SL/TP 0.0
            # dagegen ist eine ECHTE Aussage des EAs: 'kein Level gesetzt'.
            pos["price_open"] = pos["sl"] = pos["tp"] = None
            try:
                if len(f_) >= 9:
                    pos["price_open"] = float(f_[6])
                    pos["sl"] = float(f_[7])
                    pos["tp"] = float(f_[8])
            except (IndexError, ValueError):
                pos["price_open"] = pos["sl"] = pos["tp"] = None
            positions.append(pos)
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


# ── Notfall-SL/TP auf dem Hedge (27.08.2026, Finns Ansage) ─────────────────────
# Das Szenario: Echo faellt aus (PC tot, Copier haengt), der Master laeuft in
# seinen SL — ohne eigene Level liefe der Hedge endlos weiter. Deshalb bekommt
# der Hedge Notfall-Level, die der BROKER serverseitig ausfuehrt, auch wenn der
# ganze PC weg ist. Im Normalfall spiegelt Echo den Close lange vorher.
def plan_sltp(mp, *, faktor, min_puffer_punkte, point, digits):
    """REIN RECHNEND (testbar in selftest.py): Notfall-SL/TP fuer die
    Hedge-Position zu einer Master-Position.

    Gekreuzte Zuordnung, weil der Hedge GEGEN den Master laeuft:
      Master-SL → Hedge-TP (wo der Master verliert, gewinnt der Hedge)
      Master-TP → Hedge-SL
    Der Puffer liegt IMMER in Ausloeserichtung HINTER dem Master-Level.
    Bewusst NICHT 'Entry ± Faktor × Distanz': bei einem in den Gewinn
    nachgezogenen Master-SL laege der Level sonst VOR dem Master-SL im
    Kursverlauf — der Hedge schloesse sich, BEVOR der Master ausgestoppt ist,
    und liesse einen laufenden Master ohne Hedge zurueck.
      Puffer = (faktor − 100)% der Distanz Entry↔Level,
               mindestens min_puffer_punkte × point.
    Der Mindest-Puffer faengt den Breakeven-SL (Distanz 0): ohne ihn wuerde
    ein winziger Kurs-Unterschied zwischen den Brokern sofort fuellen.
    Nebeneffekt der 'dahinter'-Regel: fuellt ein Notfall-Level, ist der
    Master-Level sicher schon durchschritten — beide Seiten enden zusammen.

    mp braucht price_open/sl/tp aus dem Snapshot (EA v5). None = altes EA
    ohne die Felder → Rueckgabe None, es wird NICHTS angefasst.
    sl/tp == 0.0 heisst 'Master hat keinen Level' → der Gegenpart auf dem
    Hedge wird 0.0 (= loeschen). Sonst {"sl": x, "tp": y} in Hedge-Digits."""
    entry = mp.get("price_open")
    msl, mtp = mp.get("sl"), mp.get("tp")
    if not entry or msl is None or mtp is None:
        return None
    # Ausloeserichtung haengt NUR an Positionstyp und Level-Art: der SL einer
    # BUY-Position fuellt bei fallendem Kurs — auch wenn er im Gewinn steht.
    lang = int(mp.get("type", 0)) == 0

    def hinter(level, richtung):  # richtung: -1 = fallend, +1 = steigend
        puffer = max((float(faktor) / 100.0 - 1.0) * abs(float(level) - float(entry)),
                     float(min_puffer_punkte) * float(point))
        return max(round(float(level) + richtung * puffer, int(digits)), float(point))

    return {"tp": hinter(msl, -1 if lang else +1) if msl else 0.0,
            "sl": hinter(mtp, +1 if lang else -1) if mtp else 0.0}


def find_notfall_deals(deals, schon_verbucht, *, out_entries, reason_sl, reason_tp):
    """REIN RECHNEND (testbar): Broker-seitige SL/TP-Fills aus einer Deal-Liste
    heraussuchen. MT5 stempelt auf jeden Deal, WARUM geschlossen wurde
    (DEAL_REASON) — nur SL/TP-Fills auf unseren eigenen Notfall-Leveln zaehlen
    als Notfall-Close; ein Hand-Close (REASON_CLIENT/MOBILE/WEB) und ein
    Stop-Out (REASON_SO) bleiben 'extern' wie bisher. schon_verbucht haelt
    die Doppelzaehlung fern (Sidecar + RAM)."""
    out = []
    for d in deals or []:
        if int(getattr(d, "entry", -1)) not in out_entries:
            continue
        if int(getattr(d, "reason", -1)) not in (reason_sl, reason_tp):
            continue
        if int(d.ticket) in schon_verbucht:
            continue
        out.append(d)
    return out


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
        # Trade-Fenster (25.08.2026): einmalige Log-Zeile pro Master-Pos, wenn
        # ausserhalb des Fensters nicht gehedgt wird — wird beim naechsten
        # offenen Fenster geleert, damit ein spaeteres Zu wieder loggt.
        self.warned_unarmed = set()
        self.armed = False
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
        # Notfall-SL/TP (27.08.2026): letzter Modify-Versuch pro Hedge-Ticket —
        # Cooldown, damit eine Broker-Ablehnung (z.B. stops_level) den Log
        # nicht im 0,5-s-Takt flutet.
        self.sltp_last = {}
        self.blocked = set()
        self.last_status = 0.0
        # closed_hedges (15.08.2026, Etappe 3): Beweisquelle fuer den Hedge-P&L in
        # Prophos. Beim Init aus dem Sidecar geladen — neustart-fest.
        self.closed_path = closed_path_for(cfg_path)
        self.closed, self.hedge_last_vol, self.hedge_last_tickets = load_closed(self.closed_path)
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
        # Notfall-SL/TP (27.08.2026, Finns Ansage: Faktor manuell veraenderbar
        # in Prophos). Defaults 110% / 100 Punkte — greifen aber erst, wenn das
        # Master-EA v5 laeuft und SL/TP im Snapshot liefert; bis zur
        # Neukompilierung bleibt das Feature still (leer statt falsch).
        self.notfall_faktor = float(cfg.get("notfall_faktor", 110.0))
        self.notfall_puffer = float(cfg.get("notfall_puffer_min_punkte", 100.0))
        self.deviation = int(cfg.get("deviation_points", 30))
        self.filling = str(cfg.get("filling", "auto")).upper()
        self.adopt = bool(cfg.get("adopt_existing_master_positions", False))
        # immer_scharf (28.08.2026, Orbit): Master ohne Prophos-Plan-Fenster —
        # der TV-Verbinder speist Finns MANUELLE TradingView-Trades ein, dort
        # gibt es kein 'Trade starten'. true = jede neue Master-Position wird
        # gehedgt (wie ein klassischer Copier). Beim Start-Connect gilt trotzdem
        # die normale Alt-Bestand-Logik (adopt) — nicht das Fenster-Uebernehmen,
        # sonst wuerde ein Copier-Neustart bewusst unhedgte Positionen nachhedgen.
        self.immer_scharf = bool(cfg.get("immer_scharf", False))
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
        # notfall_faktor/notfall_puffer_min_punkte (27.08.2026): reine
        # Rechenwerte wie multiplier — sofort uebernehmen, kein Neustart. Der
        # naechste Tick zieht die Level auf allen offenen Hedges nach.
        HOT = {"multiplier", "symbol_map", "max_lots_per_hedge", "mode",
               "notfall_faktor", "notfall_puffer_min_punkte"}
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
        if "notfall_faktor" in changed:
            self.notfall_faktor = float(new.get("notfall_faktor", 110.0))
            chg.append(f"Notfall-Faktor {self.notfall_faktor}%")
        if "notfall_puffer_min_punkte" in changed:
            self.notfall_puffer = float(new.get("notfall_puffer_min_punkte", 100.0))
            chg.append(f"Notfall-Mindest-Puffer {self.notfall_puffer} Punkte")
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
    print(f" Echo · MT5-Hedge-Executor · {len(masters)} Master, ein Hedge-Terminal")
    for m in masters:
        print(f"   {m.file:<24} magic {m.magic}  "
              f"Master {m.master_login or '?'}  Snapshot {m.snapshot_file}")
    print(" Duplikum / app.py / prophos.html werden nicht angefasst.")
    print("=" * 72)

    # UAC-Haken an allen terminal64.exe wegraeumen (09.09.2026, Finns Fund:
    # Benutzerkontensteuerung beim Terminal-Start ueber Echo — Details im
    # Docstring von provision.uac_haken_entfernen). VOR dem Hedge-Autostart
    # unten, damit schon dieser Start ohne Ja-Klick durchlaeuft. Die Copier-
    # .bat-Schleife holt provision.py vor jedem Start frisch; der try faengt
    # trotzdem alles, ein fehlender Helfer darf den Copier nie aufhalten.
    try:
        import provision
        provision.uac_haken_entfernen()
    except Exception:
        pass

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
                log("Hedge-Terminal laeuft nicht — starte es MINIMIERT (Login ist gespeichert)…")
                # OHNE Vordergrund-Klau (22.09.2026, Finn: "ich arbeite am PC, und auf einmal
                # oeffnet sich das MT5-Slave-Hedge-Terminal — obwohl ich da gar nichts mache"):
                # ein frisch gestartetes MT5 reisst den Vordergrund an sich. Der Copier BRAUCHT
                # das Hedge-Terminal (er haengt daran, es bleibt bewusst immer offen), aber es
                # muss dabei niemanden stoeren. SW_SHOWMINNOACTIVE (7): starten, minimiert,
                # nicht aktivieren. Der Knopf "Slave-Terminal starten" holt es weiter nach vorn
                # — dort hat Finn es ja selbst angefordert.
                _si = None
                if os.name == "nt":
                    try:
                        _si = subprocess.STARTUPINFO()
                        _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        _si.wShowWindow = 7   # SW_SHOWMINNOACTIVE
                    except Exception:
                        _si = None
                subprocess.Popen([hpath], cwd=os.path.dirname(os.path.abspath(hpath)),
                                 startupinfo=_si)
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
    # Vordergrund merken (23.09.2026, Finn: "bei Echo wird auf manchen PCs immer wieder
    # das Slave-Terminal nach vorn geholt, der Tab ist sowieso immer offen — aber ganz
    # vorn"): initialize() haengt sich ans Hedge-Terminal und AKTIVIERT dabei dessen
    # Fenster (holt es sogar aus der Minimierung). Bei jedem Copier-Start — und den
    # gab es in Finns Testnacht bei jedem VERSION-Bump auf jedem PC mit flachen
    # Mastern. Deshalb: vorher merken, was vorn war und wie das Terminal stand,
    # danach genau das wiederherstellen. Jede Stoerung hier ist folgenlos.
    _vorher = _vordergrund_merken(hpath)
    if not mt5.initialize(**init_kw):
        # Grund in den Log-SPIEGEL, nicht nur nach stderr (31.08.2026): stirbt der
        # Copier hier, sieht Prophos nur noch alive=false und riet bisher pauschal
        # zu start-alles.bat. Genau die laeuft in diesem Moment aber schon:
        # start-copier.bat startet copier.py in einer Endlosschleife. Nur was
        # ueber log() geht, landet in copier-log.json und damit in Prophos.
        log(f"⛔ initialize() fehlgeschlagen: {mt5.last_error()} — laeuft das Hedge-Terminal?")
        log("⛔ ABBRUCH — keine Order gesendet.")
        # Auch der Fehlversuch kann das Terminal nach vorn geholt haben — und die
        # .bat startet uns in 10 s neu (24.09.2026). Kurz synchron zuruecknehmen.
        _vordergrund_zurueck(_vorher, dauer_s=2.0)
        sys.exit(1)

    # Im Hintergrund ~8 s beobachten (24.09.2026): das Terminal aktiviert sein
    # Fenster nach dem Anschluss oft erst verzoegert, die Einmal-Pruefung griff nicht.
    _vordergrund_waechter_starten(_vorher)

    ti = mt5.terminal_info()
    ai = mt5.account_info()
    if ti is None or ai is None:
        log("⛔ terminal_info()/account_info() leer — Terminal offen und eingeloggt?")
        log("⛔ ABBRUCH — keine Order gesendet.")
        mt5.shutdown()
        sys.exit(1)

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

    # ── Gezielter Magic-Umzug (11.09.2026, s. Kommentar an MAGIC_UMZUG) ─────────
    # Bewusst erst NACH dem Hedge-Connect: umgezogen wird nur, wenn auf dem
    # Hedge-Konto KEINE Position mit der alten magic liegt — sonst wuerde ein
    # laufender Hedge zur unsichtbaren Waise (die Familie 760000-779999 loest
    # keinen hedge_fremde-Alarm aus). Blockiert eine Position (auch die eines
    # fremden PCs mit Kollisions-magic), versucht es der naechste Copier-
    # Neustart wieder. Ein Fehler hier darf den Copier nie aufhalten.
    try:
        for m in masters:
            ziel = magic_umzug_ziel(m.master_login, m.magic,
                                    {x.magic for x in masters if x is not m})
            if not ziel:
                continue
            raw = mt5.positions_get()
            offen = [p for p in (raw or []) if int(getattr(p, "magic", 0)) == m.magic]
            if raw is None or offen:
                grund = ("Hedge-Bestand nicht lesbar" if raw is None
                         else f"{len(offen)} offene Position(en) mit alter magic {m.magic}")
                log(f"↻ [{m.file}] Magic-Umzug auf {ziel} VERSCHOBEN — {grund}; "
                    f"der naechste Copier-Neustart versucht es wieder.")
                continue
            cfg = load_json(m.cfg_path)
            cfg["magic"] = ziel
            tmp = m.cfg_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            os.replace(tmp, m.cfg_path)
            alte = m.magic
            m.reload()
            log(f"✅ [{m.file}] Magic-Umzug: {alte} → {ziel} (Master {m.master_login}) — "
                f"die magic-Kollision mit einem fremden PC am gemeinsamen Hedge-Konto "
                f"ist damit fuer diesen Account beendet.")
    except Exception as e:
        log(f"⚠ Magic-Umzug uebersprungen ({type(e).__name__}: {e}) — Copier laeuft normal weiter.")

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
                # Ist-Stand der Notfall-Level (27.08.2026): 0.0 = keiner gesetzt.
                # Der Nachzieh-Block vergleicht dagegen und modifiziert nur bei
                # echter Abweichung — sonst wuerde jeder Tick senden.
                "sl": float(getattr(p, "sl", 0.0) or 0.0),
                "tp": float(getattr(p, "tp", 0.0) or 0.0),
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
                "trade_contract_size": float(si.trade_contract_size or 1.0),
                # point/digits (27.08.2026): Grundlage fuer Mindest-Puffer und
                # Preis-Rundung der Notfall-Level (10014-Verwandter 'invalid
                # price' bei zu vielen Nachkommastellen).
                "point": float(si.point or 0.01),
                "digits": int(si.digits or 2),
                # Solo-Hedge (24.09.2026): Kontowaehrung je Tick je Lot + Tickgroesse →
                # Wert je PUNKT je Lot = tick_value / tick_size (NAS100 EUR-Konto ≈ 0,85)
                "tick_value": float(getattr(si, "trade_tick_value", 0.0) or 0.0),
                "tick_size": float(getattr(si, "trade_tick_size", 0.0) or 0.0)}

    def send(m, req, what):
        # Rueckgabe seit 15.08.2026 das order_send-Result statt True: result.deal
        # ist der einzige beweisfeste Anker fuer die closed_hedges-Verbuchung
        # (vorher wurde r.deal nur geloggt und war weg). Truthiness bleibt fuer
        # alle Aufrufer erhalten: Result/True = ok, None = fehlgeschlagen.
        # m.letzter_fehler (24.09.2026 spaet, Review der Koordinations-Session): mt5.last_error()
        # spiegelt Trade-Retcodes nicht zuverlaessig (oft "(1, 'Success')") — der Solo-Hedge
        # schreibt sl_fehler/tp_fehler deshalb aus diesem Merker (retcode + Broker-Kommentar).
        m.letzter_fehler = None
        r = mt5.order_send(req)
        if r is None:
            m.letzter_fehler = f"order_send None ({mt5.last_error()})"
            log(f"[{m.file}] ❌ {m.letzter_fehler} — {what}")
            return None
        if r.retcode != mt5.TRADE_RETCODE_DONE:
            hinweis = getattr(r, "comment", "")
            if int(r.retcode) == 10027:
                hinweis = ("Algo-Handel im HEDGE-Terminal ist AUS — oben den "
                           "'Algo-Handel'-Knopf gruen schalten, sonst kann der Copier nicht hedgen!")
            m.letzter_fehler = f"retcode {r.retcode} {hinweis}".strip()
            log(f"[{m.file}] ❌ abgelehnt {m.letzter_fehler} — {what}")
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
        nur ein ECHTER Broker-Deal — nie ein geratener profit=0, denn eine
        plausible falsche Zahl ist schlimmer als ein leeres Feld ('Beweis oder
        leer'). Die Deal-History kann dem order_send-Result kurz nachhinken,
        deshalb bis zu 3 Wiederholungen a 0,3 s.
        Fusion-Live-Fall (25.08.2026, Finns erster Live-Trade: Hedge-P&L blieb
        im Ueberpruefen-Tab leer): dieser Broker meldet den Fill asynchron —
        order_send liefert retcode=DONE, aber deal=0. Der Beweis kommt dann
        aus der Deal-History der Position: der juengste, noch nicht verbuchte
        OUT-Deal (bevorzugt mit passendem Volumen). Das bleibt beweisfest —
        nachgeschlagen statt mitgeliefert, geraten wird weiterhin nie."""
        deal_id = int(getattr(result, "deal", 0) or 0)
        seen = m.booked_deals.setdefault(ident, set())
        if deal_id and deal_id in seen:
            return  # Doppelzaehlungs-Schutz: derselbe Deal wird nie zweimal verbucht
        # Auch ueber Neustarts hinweg nie doppelt buchen: der Sidecar traegt die
        # Deal-Tickets aller schon verbuchten Closes (booked_deals ist nur RAM).
        booked_sidecar = {int(c.get("deal") or 0) for c in m.closed}
        deal = None
        for attempt in range(4):
            ds = mt5.history_deals_get(position=int(h["ticket"])) or []
            if deal_id:
                deal = next((d for d in ds if int(d.ticket) == deal_id), None)
            else:
                outs = [d for d in ds
                        if int(getattr(d, "entry", -1)) in (mt5.DEAL_ENTRY_OUT, mt5.DEAL_ENTRY_OUT_BY)
                        and int(d.ticket) not in seen
                        and int(d.ticket) not in booked_sidecar]
                # bevorzugt der Deal mit exakt dem geschlossenen Volumen; gibt es
                # keinen (Teil-Fill), ist EIN einziger unverbuchter OUT-Deal
                # ebenfalls eindeutig — mehrdeutig ⇒ lieber leer als falsch.
                pick = [d for d in outs if abs(float(d.volume) - float(vol)) <= 1e-6] \
                       or (outs if len(outs) == 1 else [])
                if pick:
                    deal = max(pick, key=lambda d: (int(getattr(d, "time_msc", 0) or 0), int(d.ticket)))
            if deal is not None:
                break
            if attempt < 3:
                time.sleep(0.3)
        if deal is None:
            log(f"[{m.file}] ⚠ Close-Deal (Result deal={deal_id}, Ticket {h['ticket']}) nicht in der "
                f"History gefunden — KEIN closed_hedges-Eintrag (nie profit=0 raten).")
            return
        deal_id = int(deal.ticket)
        if deal_id in seen or deal_id in booked_sidecar:
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
        write_closed(m.closed_path, m.closed, m.hedge_last_vol, m.hedge_last_tickets)

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

    # ── Solo-Hedge: Auftraege vom Panel abarbeiten (24.09.2026 abends) ─────────
    solo_pfad = os.path.join(here, SOLO_AUFTRAG)
    solo_erg_pfad = os.path.join(here, SOLO_ERGEBNIS)
    solo_zu_pfad = os.path.join(here, SOLO_ZU)

    # Selbst erkannte Abschluesse (24.09.2026 spaet): Datei {zu: [Ring], bekannt: {ticket: …}} — beim Start
    # gelesen, damit auch Positionen zaehlen, die WAEHREND eines Copier-Neustarts gefuellt wurden.
    def solo_zu_laden():
        try:
            d = load_json(solo_zu_pfad)
            if isinstance(d, dict):
                return ([r for r in (d.get("zu") or []) if isinstance(r, dict)][-SOLO_ZU_MAX:],
                        {int(k): v for k, v in (d.get("bekannt") or {}).items() if str(k).isdigit()})
        except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError):
            pass
        return [], {}

    def solo_zu_speichern(ring, bekannt):
        tmp = solo_zu_pfad + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"zu": ring[-SOLO_ZU_MAX:], "bekannt": {str(k): v for k, v in bekannt.items()}}, f, ensure_ascii=False, indent=1)
            for _ in range(5):
                try:
                    os.replace(tmp, solo_zu_pfad)
                    return
                except PermissionError:
                    time.sleep(0.05)
        except Exception as e:
            log(f"⚠ {SOLO_ZU} nicht geschrieben: {type(e).__name__}: {e}")

    hedge_acc["solo_zu"], hedge_acc["solo_bekannt"] = solo_zu_laden()
    if hedge_acc["solo_bekannt"]:
        log(f"[solo] {len(hedge_acc['solo_bekannt'])} Solo-Ticket(s) aus {SOLO_ZU} bekannt — pruefe beim ersten Tick, ob sie noch offen sind")

    def solo_abschluesse_erkennen(solo_liste):
        """Pro Tick: verschwundene Solo-Tickets → P&L/Grund/Exit aus der Historie → Ring + Datei.
        solo_liste None (Terminal nicht lesbar) = kein Urteil, bekannt bleibt stehen."""
        if solo_liste is None:
            return
        aktuell = {int(p["ticket"]): {"symbol": p.get("symbol"), "lots": p.get("lots"), "richtung": p.get("richtung"), "fill": p.get("fill"),
                                      "plan8": p.get("plan8"), "plan_id": p.get("plan_id")}
                   for p in solo_liste if p and p.get("ticket")}
        weg = solo_zu_erkennen(hedge_acc.get("solo_bekannt") or {}, aktuell)
        ring = hedge_acc.get("solo_zu") or []
        for e in weg:
            pl, grund, exit_preis = solo_pl_aus_history(e["ticket"])
            eintrag = {"ticket": int(e["ticket"]), "pl": pl, "grund": grund or "unbekannt", "fill_close": exit_preis,
                       "closed_at": utc_iso(),
                       "symbol": e.get("symbol"), "lots": e.get("lots"), "richtung": e.get("richtung"), "fill": e.get("fill"),
                       "plan8": e.get("plan8"), "plan_id": e.get("plan_id")}
            ring = solo_zu_ring(ring, eintrag)
            log(f"[solo] Position {e['ticket']} zu ({eintrag['grund']}) · P&L {pl if pl is not None else '?'} · @ {exit_preis or '?'}")
        if weg or aktuell != hedge_acc.get("solo_bekannt"):
            hedge_acc["solo_zu"], hedge_acc["solo_bekannt"] = ring, aktuell
            solo_zu_speichern(ring, aktuell)

    def solo_ergebnisse():
        try:
            e = load_json(solo_erg_pfad)
            return e if isinstance(e, dict) else {}
        except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError):
            return {}

    def solo_ergebnis_schreiben(alle, cmd_id, erg):
        erg = dict(erg)
        erg["cmd_id"] = cmd_id
        erg["at"] = utc_iso()
        alle[cmd_id] = erg
        # Ring: aelteste raus (Schluessel-Reihenfolge = Einfuegereihenfolge)
        while len(alle) > SOLO_ERGEBNIS_MAX:
            alle.pop(next(iter(alle)))
        tmp = solo_erg_pfad + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(alle, f, ensure_ascii=False, indent=1)
            for _ in range(5):
                try:
                    os.replace(tmp, solo_erg_pfad)
                    break
                except PermissionError:
                    time.sleep(0.05)
        except Exception as e:
            log(f"⚠ Solo-Ergebnis {cmd_id} nicht geschrieben: {type(e).__name__}: {e}")

    def solo_pl_aus_history(ticket):
        """Realisierter P&L der Position aus der Deal-Historie (Profit + Kommission
        + Swap + Gebuehr) — der Beweis fuer slave_pl — plus GRUND des Schliessens
        (DEAL_REASON des letzten OUT-Deals, solo_deal_grund) und Schluss-Kurs.
        -> (pl, grund, exit_preis); (None, None, None), wenn die Historie noch
        nachhinkt ('Beweis oder leer')."""
        for _ in range(8):
            try:
                deals = mt5.history_deals_get(position=int(ticket))
            except Exception:
                deals = None
            if deals:
                out = [d for d in deals if int(getattr(d, "entry", 0)) == 1]     # DEAL_ENTRY_OUT
                if out:
                    letzter = out[-1]
                    pl = round(sum(float(d.profit) + float(d.commission) + float(d.swap)
                                   + float(getattr(d, "fee", 0.0) or 0.0) for d in deals), 2)
                    return pl, solo_deal_grund(getattr(letzter, "reason", None)), float(getattr(letzter, "price", 0.0) or 0.0)
            time.sleep(0.25)
        return None, None, None

    def solo_open(m, a):
        sym = str(a.get("symbol") or "NAS100")
        richtung = str(a.get("richtung") or "").lower()
        if richtung not in ("buy", "sell"):
            return {"ok": False, "code": "befehl", "msg": "richtung muss buy/sell sein"}
        si = sym_info(sym)
        if si is None:
            return {"ok": False, "code": "symbol", "msg": f"Symbol {sym} im Hedge-Terminal unbekannt"}
        wert = (si["tick_value"] / si["tick_size"]) if (si["tick_value"] > 0 and si["tick_size"] > 0) else 0.0
        # tp_punkte = Distanz zum Master-TP (Pflicht fuer Lots + Schliess-Level), sl_punkte = Distanz zum
        # Master-SL (optional, Koordination 24.09.2026 spaet); 'punkte' bleibt als alter Name fuer tp_punkte.
        tp_punkte = float(a.get("tp_punkte") or a.get("punkte") or 0)
        sl_punkte = float(a.get("sl_punkte") or 0)
        puffer = float(a.get("puffer") if a.get("puffer") is not None else 3)
        # Notfall-Faktor (25.09.2026): SL am Hedge = fill ± tp_punkte × faktor (Standard 1,10), Panel prueft 1,0–2,0
        try:
            notfall_faktor = float(a.get("notfall_faktor") if a.get("notfall_faktor") is not None else 1.10)
        except (TypeError, ValueError):
            notfall_faktor = 1.10
        if not (1.0 <= notfall_faktor <= 2.0):
            notfall_faktor = 1.10
        lots, lots_angefragt, lots_quelle = solo_lots_waehlen(a.get("lots"), a.get("eur"), tp_punkte, wert, si)
        if not lots > 0:
            return {"ok": False, "code": "lots", "wert_pro_punkt": wert, "lots_angefragt": lots_angefragt,
                    "msg": (f"Lots {lots_angefragt} liegen unter dem Mindestlot {si['volume_min']} des Brokers"
                            if lots_angefragt else
                            f"Lots nicht berechenbar (eur {a.get('eur')}, tp_punkte {tp_punkte}, "
                            f"{wert:.4f} {hedge_acc.get('currency') or ''}/Pkt/Lot) — unter Mindestlot oder Werte fehlen")}
        mt5.symbol_select(sym, True)
        tick = mt5.symbol_info_tick(sym)
        if tick is None or not (tick.bid and tick.ask):
            return {"ok": False, "code": "kurs", "msg": f"kein Kurs fuer {sym} (Markt zu?)"}
        typ = mt5.ORDER_TYPE_SELL if richtung == "sell" else mt5.ORDER_TYPE_BUY
        price = tick.bid if richtung == "sell" else tick.ask
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": lots, "type": typ,
               "price": price, "deviation": m.deviation, "magic": SOLO_MAGIC,
               "comment": solo_kommentar(a.get("plan_id")), "type_time": mt5.ORDER_TIME_GTC,
               "type_filling": filling_for(m, sym)}
        r = send(m, req, f"SOLO OPEN {richtung.upper()} {lots} {sym} ({a.get('eur')} € / {a.get('punkte')} Pkt)")
        if r is None:
            le = mt5.last_error()
            return {"ok": False, "code": "abgelehnt", "retry_ok": False, "lots": lots, "wert_pro_punkt": wert,
                    "msg": f"order_send abgelehnt ({getattr(m, 'letzter_fehler', None) or le}) — im Hedge-Terminal nachsehen"}
        ticket = int(getattr(r, "order", 0) or 0)
        fill = float(getattr(r, "price", 0.0) or 0.0) or float(price)
        # Ticket der POSITION ueber den Deal nachschlagen (position_id), Fill vom Deal
        try:
            d = mt5.history_deals_get(ticket=int(r.deal)) if getattr(r, "deal", 0) else None
            if d:
                ticket = int(d[0].position_id) or ticket
                fill = float(d[0].price) or fill
        except Exception:
            pass
        # Zuordnung Ticket → Plan merken (persistiert mit solo_bekannt in hedge_solo_zu.json), damit hedge_solo und
        # der Abschluss-Ring plan_id tragen, auch wenn der Broker den Kommentar kuerzt
        if ticket and a.get("plan_id"):
            hedge_acc.setdefault("solo_plan", {})[int(ticket)] = str(a.get("plan_id"))[:64]
        erg = {"ok": True, "ticket": ticket, "deal": int(getattr(r, "deal", 0) or 0), "lots": lots,
               "plan8": solo_plan8(solo_kommentar(a.get("plan_id"))), "plan_id": (str(a.get("plan_id"))[:64] if a.get("plan_id") else None),
               "fill": fill, "symbol": sym, "richtung": richtung, "wert_pro_punkt": round(wert, 5),
               "eur_je_punkt": round(wert * lots, 4), "waehrung": hedge_acc.get("currency"),
               # lots = tatsaechlich gesendet (Broker-Raster), lots_angefragt = Rohwert vom Frontend (None = aus eur gerechnet)
               "lots_angefragt": lots_angefragt, "lots_quelle": lots_quelle,
               "nas_bid": float(tick.bid), "nas_ask": float(tick.ask), "sl": 0.0, "tp": 0.0,
               "tp_punkte": tp_punkte, "sl_punkte": sl_punkte, "puffer": puffer,
               "notfall_faktor": notfall_faktor, "sl_distanz_punkte": None}
        # Schliess-Level im Terminal (Finn: „sobald der Preis in MetaTrader erreicht wird"): sl am Hedge =
        # Master-TP (tp_punkte + puffer), tp am Hedge = Master-SL (sl_punkte − puffer, optional). EIN
        # SLTP-Request fuer beide; ein Fehler hier ist kein Abbruch, die Antwort traegt sl/tp 0 + *_fehler.
        try:
            if tp_punkte > 0 and ticket:
                sl = solo_notfall_sl(fill, richtung, tp_punkte, faktor=notfall_faktor, point=si["point"], digits=si["digits"])
                erg["sl_distanz_punkte"] = round(abs(sl - fill), 2) if sl > 0 else None
                tp = solo_level_tp(fill, richtung, sl_punkte, puffer=puffer, point=si["point"], digits=si["digits"]) if sl_punkte > 0 else 0.0
                if sl > 0:
                    ok = send(m, {"action": mt5.TRADE_ACTION_SLTP, "symbol": sym, "position": ticket,
                                  "sl": sl, "tp": tp, "magic": SOLO_MAGIC},
                              f"SOLO LEVEL SL {sl} / TP {tp or '—'} {sym} (Ticket {ticket})")
                    if ok:
                        erg["sl"], erg["tp"] = sl, tp
                    elif tp > 0:
                        # Beide zusammen abgelehnt (z. B. TP zu nah am Kurs): das Master-TP-Level ist das
                        # wichtigere — noch einmal nur mit SL, damit der Hedge nie ohne Schliess-Level bleibt
                        erg["tp_fehler"] = str(getattr(m, "letzter_fehler", None) or mt5.last_error())
                        ok2 = send(m, {"action": mt5.TRADE_ACTION_SLTP, "symbol": sym, "position": ticket,
                                       "sl": sl, "tp": 0.0, "magic": SOLO_MAGIC},
                                   f"SOLO LEVEL nur SL {sl} {sym} (Ticket {ticket})")
                        if ok2:
                            erg["sl"] = sl
                        else:
                            erg["sl_fehler"] = str(getattr(m, "letzter_fehler", None) or mt5.last_error())
                    else:
                        erg["sl_fehler"] = str(getattr(m, "letzter_fehler", None) or mt5.last_error())
        except Exception as e:
            erg["sl_fehler"] = erg.get("sl_fehler") or f"{type(e).__name__}: {e}"
        return erg

    def solo_close(m, a):
        try:
            ticket = int(a.get("ticket") or 0)
        except (TypeError, ValueError):
            ticket = 0
        if not ticket:
            return {"ok": False, "code": "befehl", "msg": "ticket fehlt"}
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            # Schon zu (Level im Terminal, Hand) → P&L + Grund aus der Historie, kein Fehler
            pl, grund, exit_preis = solo_pl_aus_history(ticket)
            return {"ok": True, "schon_zu": True, "ticket": ticket, "pl": pl, "grund": grund, "fill_close": exit_preis,
                    "msg": "Position war schon zu" + (f" ({grund})" if grund else "")
                           + (f" · P&L {pl}" if pl is not None else " · P&L noch nicht in der Historie")}
        p = pos[0]
        if int(getattr(p, "magic", 0) or 0) != SOLO_MAGIC:
            return {"ok": False, "code": "fremd", "retry_ok": False,
                    "msg": f"Ticket {ticket} traegt magic {getattr(p, 'magic', 0)} — kein Solo-Hedge, wird NICHT angefasst"}
        sym = str(p.symbol)
        tick = mt5.symbol_info_tick(sym)
        lang = int(p.type) == 0
        ctype = mt5.ORDER_TYPE_SELL if lang else mt5.ORDER_TYPE_BUY
        price = (tick.bid if lang else tick.ask) if tick else 0.0
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": float(p.volume),
               "type": ctype, "position": ticket, "price": price,
               "deviation": m.deviation, "magic": SOLO_MAGIC, "comment": SOLO_KOMMENTAR + "c",
               "type_time": mt5.ORDER_TIME_GTC, "type_filling": filling_for(m, sym)}
        r = send(m, req, f"SOLO CLOSE {float(p.volume)} {sym} (Ticket {ticket}, Grund {a.get('grund') or '?'})")
        if r is None:
            return {"ok": False, "code": "abgelehnt", "retry_ok": True, "ticket": ticket,
                    "msg": f"Close abgelehnt ({getattr(m, 'letzter_fehler', None) or mt5.last_error()})"}
        pl, grund, exit_preis = solo_pl_aus_history(ticket)
        return {"ok": True, "ticket": ticket, "deal": int(getattr(r, "deal", 0) or 0),
                "fill_close": float(getattr(r, "price", 0.0) or 0.0) or exit_preis, "lots": float(p.volume), "pl": pl,
                # grund: den Grund des Auftraggebers (Waechter: 'tp_feed'/'sl_feed'/'master_ende', Karte: 'hand')
                # vor dem DEAL_REASON — unser eigener Close ist fuer MT5 immer nur EXPERT ('close')
                "grund": (str(a.get("grund"))[:40] if a.get("grund") else None) or grund or "close",
                "msg": f"geschlossen @ {getattr(r, 'price', '?')}" + (f" · P&L {pl}" if pl is not None else " · P&L folgt aus der Historie")}

    def solo_abarbeiten():
        """Pro Tick: Auftraege aus hedge_solo_auftrag.json ausfuehren, Ergebnis in
        hedge_solo_ergebnis.json (= Erledigt-Liste). Auftraege aelter als
        SOLO_MAX_ALTER_S werden mit 'verfallen' quittiert, nie ausgefuehrt — der
        Copier startet bei Updates/Config-Aenderungen neu, ein liegengebliebener
        OPEN darf Minuten spaeter nicht ploetzlich eine Position aufreissen."""
        alle = solo_ergebnisse()
        offen, verworfen = solo_auftraege_lesen(solo_pfad, set(alle.keys()), time.time())
        for cid in verworfen:
            solo_ergebnis_schreiben(alle, cid, {"ok": False, "code": "verfallen", "retry_ok": False,
                                                 "msg": f"Auftrag aelter als {SOLO_MAX_ALTER_S:.0f} s — nicht ausgefuehrt"})
        for a in offen:
            cid = str(a["cmd_id"])
            m0 = masters[0]
            try:
                if a.get("aktion") == "open":
                    if is_paused():
                        erg = {"ok": False, "code": "pausiert", "retry_ok": True,
                               "msg": "Echo ist pausiert (Not-Aus) — kein Solo-Open"}
                    else:
                        erg = solo_open(m0, a)
                elif a.get("aktion") == "close":
                    erg = solo_close(m0, a)
                else:
                    erg = {"ok": False, "code": "befehl", "msg": f"unbekannte aktion {a.get('aktion')!r}"}
            except Exception as e:
                erg = {"ok": False, "code": "absturz", "retry_ok": a.get("aktion") == "close",
                       "msg": f"{type(e).__name__}: {str(e)[:200]}"}
            log(f"[solo] {a.get('aktion')} {cid[:8]}: {'OK' if erg.get('ok') else 'FEHLER'} — {str(erg.get('msg') or '')[:160]}")
            solo_ergebnis_schreiben(alle, cid, erg)

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
            # Trade-Fenster offen? (25.08.2026) — reine Anzeige-Information
            "armed": bool(getattr(m, "armed", False)),
            # Echo pausiert? (28.08.2026, Not-Aus) — reine Anzeige fuer den Chip
            "paused": is_paused(),
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
            # Zweiter Kurs-Feed (24.09.2026 spaet): NAS100-Tick + Minutenkerzen des Fusion-Terminals.
            # null = Symbol fehlt / kein Tick. CFD, nicht NQ — siehe kerze_fortschreiben.
            "kurs_nas100": hedge_acc.get("kurs_nas100"),
            "kurs_1m_nas100": [k for k in (hedge_acc.get("k1m_vor"), hedge_acc.get("k1m")) if k],
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
            # Solo-Hedges (Winning-Day-Gegenhedge, 24.09.2026): eigene Liste, kein Alarm
            "hedge_solo": hedge_acc.get("solo"),
            # Selbst erkannte Abschluesse (24.09.2026 spaet), letzte 20, neustart-fest (hedge_solo_zu.json):
            # [{ticket, pl, grund, fill_close, closed_at, symbol, lots, richtung, fill}] — zweite Quelle fuer die Karte
            "hedge_solo_zu": hedge_acc.get("solo_zu") or [],
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
            if my_version and rv and rv != my_version and _REMOTE_VERSION.get("neustart", True):
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
            # Prophos-Familie FAMILIE_MIN-FAMILIE_MAX (seit 11.09.2026
            # 760000-779999): die Hedges der ANDEREN PCs am selben
            # Hedge-Konto tragen Familien-Magics und sind kein Alarm.
            fremde, solo = [], []
            try:
                for p_ in (mt5.positions_get() or []):
                    mg = int(getattr(p_, "magic", 0) or 0)
                    if FAMILIE_MIN <= mg <= FAMILIE_MAX:
                        continue
                    if mg == SOLO_MAGIC:
                        # Solo-Hedge (24.09.2026): kein Alarm, eigene Liste — Prophos zeigt
                        # Live-P&L + Notfall-SL auf der Winning-Day-Karte (auch am Mac via mt5_live)
                        solo.append({"ticket": int(p_.ticket), "symbol": str(p_.symbol),
                                     "type": int(p_.type), "volume": float(p_.volume),
                                     "profit": float(p_.profit), "price_open": float(p_.price_open),
                                     "sl": float(getattr(p_, "sl", 0.0) or 0.0),
                                     "tp": float(getattr(p_, "tp", 0.0) or 0.0),
                                     # Vertrag fuer das Frontend (Koordination 24.09.2026 spaet): sprechende Namen
                                     "richtung": "buy" if int(p_.type) == 0 else "sell",
                                     "lots": float(p_.volume), "fill": float(p_.price_open),
                                     "pl_live": float(p_.profit),
                                     # Zuordnung zum Plan (25.09.2026): plan8 aus dem Kommentar, plan_id aus dem Auftrag
                                     "comment": str(getattr(p_, "comment", "") or ""),
                                     "plan8": solo_plan8(getattr(p_, "comment", "")),
                                     "plan_id": ((hedge_acc.get("solo_plan") or {}).get(int(p_.ticket))
                                                 or ((hedge_acc.get("solo_bekannt") or {}).get(int(p_.ticket)) or {}).get("plan_id"))})
                        continue
                    fremde.append({"ticket": int(p_.ticket), "symbol": str(p_.symbol),
                                   "type": int(p_.type), "volume": float(p_.volume)})
            except Exception:
                fremde = None
                solo = None
            hedge_acc["fremde"] = fremde
            hedge_acc["solo"] = solo
            # Abschluesse selbst erkennen (Ring hedge_solo_zu), dann Auftraege vom Panel (open/close)
            try:
                solo_abschluesse_erkennen(solo)
            except Exception as e:
                log(f"⚠ Solo-Abschluss-Erkennung: {type(e).__name__}: {str(e)[:120]}")
            try:
                solo_abarbeiten()
            except Exception as e:
                log(f"⚠ Solo-Auftraege: {type(e).__name__}: {str(e)[:120]}")
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

            # ── NAS100-Tick als zweiter Kurs-Feed (Koordination 24.09.2026 spaet) ──
            # Kein neuer Prozess, kein Timer: EIN symbol_info_tick pro Tick (0,5 s),
            # Symbol = erstes NAS100-artiges Ziel aus symbol_map, sonst 'NAS100';
            # existiert es im Terminal nicht (einmal geprueft), bleibt alles None.
            # Kerzen aus dem Bid (kerze_fortschreiben), Form wie kurs_1m des Readers.
            if "nas_sym" not in hedge_acc:
                hedge_acc["nas_sym"] = None
                try:
                    kand = [v for m_ in masters for v in (m_.symbol_map or {}).values() if "NAS" in str(v).upper()]
                    for s_ in (kand or []) + ["NAS100"]:
                        if mt5.symbol_info(s_) is not None:
                            hedge_acc["nas_sym"] = str(s_)
                            break
                except Exception:
                    hedge_acc["nas_sym"] = None
            hedge_acc["kurs_nas100"] = None
            if hedge_acc.get("nas_sym"):
                try:
                    _tn = mt5.symbol_info_tick(hedge_acc["nas_sym"])
                    if _tn is not None and _tn.bid:
                        hedge_acc["kurs_nas100"] = {"bid": float(_tn.bid), "ask": float(_tn.ask),
                                                    "ts": int(getattr(_tn, "time_msc", 0) or int(_tn.time) * 1000),
                                                    "symbol": hedge_acc["nas_sym"]}
                        hedge_acc["k1m"], hedge_acc["k1m_vor"] = kerze_fortschreiben(
                            hedge_acc.get("k1m"), hedge_acc.get("k1m_vor"), "NAS100", hedge_acc["nas_sym"],
                            float(_tn.bid), time.time())
                except Exception:
                    hedge_acc["kurs_nas100"] = None

            # ── Trade-Fenster aus dem Panel-Plan-Store lesen (25.08.2026) ──────
            # plans.json pflegt das Panel: Prophos-Trade-Start legt 'geplant' an,
            # die Zustandsmaschine schiebt nach 'laufend'/'beendet'. Datei fehlt
            # oder ist unlesbar → KEIN Fenster offen (lieber nicht hedgen als
            # ausserhalb des Fensters hedgen — genau Finns Ansage).
            try:
                armed_files = plan_armed_files(load_json(os.path.join(here, "plans.json")),
                                               datetime.now())
            except (OSError, json.JSONDecodeError, ValueError):
                armed_files = set()

            # ── Jeden Master abarbeiten ─────────────────────────────────────────
            for m in masters:
                # immer_scharf zaehlt wie ein offenes Fenster (Orbit, 28.08.2026)
                m.armed = (m.file in armed_files) or m.immer_scharf
                if m.armed:
                    m.warned_unarmed.clear()
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
                    if now - m.last_status > 1.0:
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
                    if now - m.last_status > 1.0:
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
                    if m.armed and not m.immer_scharf:
                        # Trade-Fenster offen ⇒ KEIN startup_skip (25.08.2026, Finns
                        # Live-Fund: die Bot-Order kam, waehrend der Copier gerade neu
                        # startete — die frische Position lag beim ersten Snapshot-
                        # Connect schon da, wanderte als 'Alt-Bestand' in startup_skip
                        # und der Hedge kam NIE). Im offenen Fenster ist eine Position
                        # ohne Hedge genau der geplante Trade: uebernehmen und hedgen.
                        # Der Alt-Bestand-Schutz gilt weiter fuer Verbindungen OHNE
                        # offenes Fenster (dort entstehen Positionen nie durch uns) —
                        # UND fuer immer_scharf-Master (Orbit): dort ist eine beim
                        # Start unhedgte Position Alt-Bestand/bewusste Entscheidung,
                        # kein frisch geplanter Trade; es gilt adopt.
                        m.startup_skip = set()
                        if snap["positions"]:
                            log(f"▶ [{m.file}] Trade-Fenster offen — {len(snap['positions'])} "
                                f"Master-Position(en) werden uebernommen und gehedgt.")
                    else:
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
                cur_tickets = {str(i): sorted(h["ticket"] for h in hs) for i, hs in hedges.items() if hs}
                for ident_, prev_v in m.hedge_last_vol.items():
                    now_v = cur_vol.get(ident_, 0.0)
                    if now_v < prev_v - TOL:
                        try:
                            ident_i = int(ident_)
                        except (TypeError, ValueError):
                            ident_i = ident_
                        mark = m.own_close_mark.pop(ident_i, 0)
                        if time.time() - mark > 30:
                            # Notfall-Close zuerst (27.08.2026, Finns Ansage: 'sollte es
                            # passieren, soll der P&L trotzdem richtig eingetragen
                            # werden'): hat der BROKER auf unserem eigenen Notfall-
                            # SL/TP geschlossen (News-Kerze schneller als der Spiegel,
                            # oder Fill waehrend einer Copier-Downtime), traegt der
                            # Deal DEAL_REASON_SL/TP. Das ist ein ECHTER Broker-Deal —
                            # beweisfest verbuchen, KEINE Hand-Close-Sperre. Die
                            # Tickets kommen aus der persistierten Baseline, deshalb
                            # funktioniert das auch nach einem Neustart.
                            geb = {int(c.get("deal") or 0) for c in m.closed} \
                                  | m.booked_deals.get(ident_i, set())
                            nf = []
                            for tk in m.hedge_last_tickets.get(ident_, []):
                                try:
                                    ds = mt5.history_deals_get(position=int(tk)) or []
                                except Exception:
                                    ds = []
                                nf += [(int(tk), d) for d in find_notfall_deals(
                                    ds, geb,
                                    out_entries=(mt5.DEAL_ENTRY_OUT, mt5.DEAL_ENTRY_OUT_BY),
                                    reason_sl=mt5.DEAL_REASON_SL,
                                    reason_tp=mt5.DEAL_REASON_TP)]
                            if nf:
                                for tk, d in nf:
                                    m.booked_deals.setdefault(ident_i, set()).add(int(d.ticket))
                                    m.closed.append({
                                        "ident": ident_i, "ticket": tk, "deal": int(d.ticket),
                                        "symbol": str(getattr(d, "symbol", "") or ""),
                                        "volume": float(d.volume),
                                        "profit": float(d.profit) + float(d.commission) + float(d.swap),
                                        "note": "notfall_close",
                                        "closed_at": datetime.now().isoformat(timespec="seconds"),
                                    })
                                del m.closed[:-50]
                                log(f"🛡 [{m.file}] Notfall-Close: Broker hat SL/TP auf dem Hedge "
                                    f"von Master-Pos {ident_} serverseitig ausgefuehrt — P&L "
                                    f"verbucht ({len(nf)} Deal(s)), keine Sperre. Genau dafuer "
                                    f"sind die Notfall-Level da.")
                                # KEIN m.blocked: laeuft der Master wider Erwarten noch
                                # (Notfall-Level liegt HINTER dem Master-Level, also ist
                                # er praktisch sicher auch zu), stellt der naechste Tick
                                # den Schutz-Hedge bewusst wieder her.
                                continue
                            log(f"⚠ [{m.file}] Hedge-Bestand von Master-Pos {ident_} extern "
                                f"geschrumpft ({prev_v} → {now_v}) — Stop-Out oder Hand-Close "
                                f"im Terminal? P&L dieses Trades ist nicht mehr beweisbar.")
                            m.closed.append({"ident": ident_i, "note": "extern_geschlossen",
                                             "profit": None,
                                             "closed_at": datetime.now().isoformat(timespec="seconds")})
                            del m.closed[:-50]
                            # Hand-Close ist endgueltig (25.08.2026, Finns Ansage beim
                            # ersten Live-Kontakt: von Hand geschlossene Hedges muessen
                            # zu BLEIBEN — vorher eroeffnete der naechste Tick sofort
                            # einen neuen). Master-Pos fuer weitere Opens sperren;
                            # Closes bleiben erlaubt (Teil-Hand-Close: der Rest wird
                            # beim Master-Close noch sauber zugemacht). Nach einem
                            # Copier-Neustart haelt startup_skip voll geschlossene
                            # Positionen weiter fern; nur ein TEIL-geschlossener
                            # Hedge wuerde wieder adoptiert und aufgestockt.
                            m.blocked.add(ident_i)
                            log(f"✋ [{m.file}] Master-Pos {ident_} wird NICHT erneut "
                                f"gehedgt — Hand-Close wird respektiert.")
                if cur_vol != m.hedge_last_vol or cur_tickets != m.hedge_last_tickets:
                    # Baseline persistieren, damit der Waechter Neustarts ueberlebt —
                    # nur bei Aenderung, nicht jeden 0,5-s-Tick.
                    m.hedge_last_vol = cur_vol
                    m.hedge_last_tickets = cur_tickets
                    write_closed(m.closed_path, m.closed, m.hedge_last_vol, m.hedge_last_tickets)

                # ── Eingefrorener Snapshot = keine Order-Basis (25.08.2026) ─────
                # Live-Fund beim ersten Echtgeld-Kontakt: Master 26592415 war
                # laengst flach, aber die stehengebliebene Snapshot-Datei (Lese-EA
                # tot) listete noch Position 591067191 — der Copier eroeffnete
                # daraus nach jedem Hand-Close einen frischen Echtgeld-Hedge.
                # Eine Datei, die seit >15 s nicht mehr geschrieben wird, ist
                # kein Beweis fuer offene Master-Positionen ('Beweis oder leer'):
                # Status/Warnung laufen weiter (Karte: 'Snapshot eingefroren'),
                # aber es werden KEINE Orders mehr daraus abgeleitet. Der
                # Schwund-Waechter oben bleibt bewusst davor — er haengt am
                # frischen Hedge-Bestand, nicht am Snapshot.
                try:
                    snap_fresh = (time.time() - os.path.getmtime(snap_path)) <= 15
                except OSError:
                    snap_fresh = False
                if not snap_fresh:
                    # Offene Hedges halten den Selbst-Update-Neustart weiter auf;
                    # die eingefrorene Positionsliste zaehlt dafuer nicht.
                    m.busy = bool(hedges)
                    if time.time() - m.last_status > 1.0:
                        m.last_status = time.time()
                        if os.path.exists(m.cfg_path):
                            write_status(m.status_path, master_status(m, snap, hedges, True))
                    continue

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
                        # Echo pausiert (28.08.2026, Finns Not-Aus): keine neuen
                        # Hedges. Wie das Trade-Fenster ein reines OPEN-Gate —
                        # Closes unten laufen weiter, laufende Hedges bleiben offen.
                        if is_paused():
                            if ident not in m.warned_unarmed:
                                m.warned_unarmed.add(ident)
                                log(f"⏸ [{m.file}] Echo pausiert — Master-Pos {ident} wird NICHT "
                                    f"gehedgt (Closes laufen weiter).")
                            continue
                        # Trade-Fenster zu → keine neuen Hedges (25.08.2026, Finns
                        # Ansage: scharf nur zwischen 'Trade starten' und Trade-
                        # Ende). Closes laufen unten bewusst OHNE dieses Gate.
                        if not m.armed:
                            if ident not in m.warned_unarmed:
                                m.warned_unarmed.add(ident)
                                log(f"🔒 [{m.file}] Master-Pos {ident}: kein offenes Trade-Fenster "
                                    f"(kein geplanter/laufender Plan) — es wird NICHT gehedgt.")
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

                # ── Notfall-SL/TP auf den Hedges nachziehen (27.08.2026) ────────
                # Bei JEDER Aenderung von SL/TP auf dem Master (EA v5 liefert
                # sie im Snapshot — Finn verschiebt sie auch waehrend des
                # Trades) bekommen die Hedges ihre Notfall-Level: gekreuzt und
                # mit Puffer HINTER dem Master-Level (Formel: plan_sltp).
                # Laeuft bewusst auch ausserhalb des Trade-Fensters und fuer
                # blockierte idents — bestehende Hedges absichern ist wie
                # Closes nie falsch. Altes EA ohne die Felder ⇒ plan_sltp
                # None ⇒ es wird NICHTS angefasst (auch nichts geloescht).
                for mp in snap["positions"]:
                    hs = hedges.get(mp["ident"]) or []
                    if not hs:
                        continue
                    hsym = m.symbol_map.get(mp["symbol"])
                    si = sym_info(hsym) if hsym else None
                    if si is None:
                        continue
                    ziel = plan_sltp(mp, faktor=m.notfall_faktor,
                                     min_puffer_punkte=m.notfall_puffer,
                                     point=si["point"], digits=si["digits"])
                    if ziel is None:
                        continue
                    tol = si["point"] / 2.0
                    for h in hs:
                        if abs(float(h.get("sl") or 0.0) - ziel["sl"]) <= tol and \
                           abs(float(h.get("tp") or 0.0) - ziel["tp"]) <= tol:
                            continue
                        if time.time() - m.sltp_last.get(h["ticket"], 0) < 10:
                            continue  # Broker-Ablehnung nicht im Tick-Takt wiederholen
                        m.sltp_last[h["ticket"]] = time.time()
                        if send(m, {"action": mt5.TRADE_ACTION_SLTP,
                                    "symbol": h["symbol"], "position": h["ticket"],
                                    "sl": ziel["sl"], "tp": ziel["tp"],
                                    "magic": m.magic},
                                f"NOTFALL-LEVEL SL {ziel['sl'] or '—'} / TP {ziel['tp'] or '—'} "
                                f"{h['symbol']} (Ticket {h['ticket']})"):
                            m.sltp_last.pop(h["ticket"], None)

                # busy = dieser Master hat offene Positionen ODER offene Hedges —
                # solange wird kein Selbst-Update-Neustart ausgefuehrt.
                # Solo-Hedge offen (24.09.2026): der Close-Auftrag braucht einen laufenden
                # Copier — ein Update-Neustart wartet, bis auch die Solo-Position zu ist.
                m.busy = bool(snap["positions"]) or bool(hedges) or bool(hedge_acc.get("solo"))

                if time.time() - m.last_status > 1.0:
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
