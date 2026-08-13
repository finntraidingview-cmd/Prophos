#!/usr/bin/env python3
"""
Auto-Provisionierung: neues MASTER-Terminal per Knopfdruck (13.08.2026, Neubau).

Der manuelle Ablauf (Ordner klonen, einloggen, EA kompilieren, InpFileName
setzen, Config anlegen) hat beim zweiten Master ~30 Minuten gedauert und ist
fehleranfaellig — genau die Handgriffe, die hier wegfallen. Ziel-Fluss im Panel:
Name + Login + Passwort + Server eintippen, "Fertig", Karte erscheint (dryrun).

ARCHITEKTUR (bewusst anders als der erste Anlauf, der in addc1e8 entfernt wurde):
  · Geklont wird das MASTER-Vorlage-Terminal. Das HEDGE-Terminal bleibt das
    eine, gemeinsame — check_fleet() in copier.py erzwingt das.
  · magic / comment_prefix / snapshot_file vergibt dieses Modul fortlaufend
    selbst — die Werte KOENNEN nicht mehr kollidieren (die Audit-Funde 1/2/21/22
    entstanden alle durch von Hand kopierte Configs).
  · Es wird die kompilierte .ex5 aus dem Vorlage-Terminal kopiert — auf dem
    neuen Terminal muss nie der MetaEditor geoeffnet werden.

PASSWORT-HALTUNG (die eine heikle Stelle, deshalb ausfuehrlich):
  Das Passwort wird NIRGENDS dauerhaft gespeichert. Es laeuft genau einen Weg:
  Formular (nur im Speicher) -> transiente Start-Datei fuer terminal64.exe
  (/config, offizieller MT5-Mechanismus) -> MT5 loggt sich ein und speichert
  die Zugangsdaten selbst verschluesselt in SEINEM Datenordner (wie beim
  manuellen Login mit 'Zugangsdaten speichern'). Die Start-Datei wird im
  finally-Block geloescht — auch im Fehlerfall. Kein Log, keine Config, kein
  Git-Objekt enthaelt das Passwort; die Job-Anzeige im Panel zeigt es nie.

Reine Logik (laeuft auch auf dem Mac, siehe selftest.py) ist von den
Windows-Aktionen getrennt.
"""

import json
import os
import re
import shutil
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))

# Muss zu copier.py/panel.py passen — dort entscheidet dieses Muster, ob eine
# Datei als Instanz erkannt wird.
CONFIG_RE = re.compile(r"config(?:[-_][A-Za-z0-9]{1,24})?\.json", re.I)
NAME_RE = re.compile(r"[A-Za-z0-9]{1,24}")

EA_NAME = "ProphosHedgeReader"
MAGIC_BASE = 770000
STARTUP_SYMBOL = "EURUSD"   # existiert bei allen relevanten Brokern
STARTUP_PERIOD = "H1"
# Kodierung der selbst geschriebenen Startdateien: SCHLICHTER ASCII-TEXT.
# Erster Live-Test 14.08.2026: mit UTF-16 (BOM) hat das Terminal die /config-ini
# ignoriert — kein Login-Versuch im Journal. Die funktionierenden Praxis-Beispiele
# schreiben plain text; MT5s eigene UTF-16-Dateien sind die, die es SELBST erzeugt.
INI_ENCODING = "ascii"
SET_ENCODING = "ascii"

ORIGIN_FILE = "origin.txt"


class ProvisionError(Exception):
    """Fehler mit Klartext fuer die Panel-Anzeige."""


# ---------------------------------------------------------------- reine Logik

def name_ok(name):
    return bool(NAME_RE.fullmatch(name or ""))


def used_values(folder):
    """Was in der Flotte (inkl. Vorlagen) schon vergeben ist. Die Vorlagen
    zaehlen bewusst mit: config.example.json traegt magic 770001, und eine
    Kollision mit einer Vorlage waere genauso toedlich wie mit einer Instanz."""
    magics, snapshots, prefixes = set(), set(), set()
    for fn in sorted(os.listdir(folder)):
        if not fn.lower().endswith(".json") or not fn.lower().startswith("config"):
            continue
        try:
            with open(os.path.join(folder, fn), "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(cfg.get("magic"), int):
            magics.add(cfg["magic"])
        if cfg.get("snapshot_file"):
            snapshots.add(str(cfg["snapshot_file"]).lower())
        if cfg.get("comment_prefix"):
            prefixes.add(str(cfg["comment_prefix"]))
    return magics, snapshots, prefixes


def next_magic(magics):
    n = MAGIC_BASE + 1
    while n in magics:
        n += 1
    return n


def prefix_for(magic, taken):
    """P2, P3, P4 … ('PH' gehoert dem ersten Master). Der Copier sucht den Token
    als Praefix '<prefix>-<identifier>'; 'P2-' faengt nicht mit 'PH-' an, die
    Praefixe sind also trennscharf."""
    idx = magic - MAGIC_BASE
    cand = "PH" if idx <= 1 else f"P{idx}"
    while cand in taken:
        idx += 1
        cand = f"P{idx}"
    return cand


def alloc_identity(folder, name):
    """Eindeutige Kennwerte fuer den neuen Master — vergeben, nicht getippt."""
    magics, snapshots, prefixes = used_values(folder)
    magic = next_magic(magics)
    prefix = prefix_for(magic, prefixes)
    snapshot = f"prophos_master_{name.lower()}.csv"
    if snapshot in snapshots:
        raise ProvisionError(f"snapshot_file '{snapshot}' ist schon vergeben — Name aendern.")
    return {"magic": magic, "prefix": prefix, "snapshot": snapshot}


def build_login_ini(login, password, server):
    """Transiente Startdatei: NUR fuer den Erststart, wird danach geloescht.
    KeepPrivate=1 ist Pflicht (Recherche 13.08.2026): damit speichert MT5 die
    Zugangsdaten verschluesselt in seiner eigenen Konto-Datenbank und verbindet
    bei jedem spaeteren Normalstart automatisch — ohne die Zeile hinge das am
    UI-Haekchen, dessen Default nirgends zugesichert ist."""
    return (f"[Common]\nLogin={login}\nPassword={password}\nServer={server}\n"
            f"KeepPrivate=1\n")


def build_startup_ini(expert=EA_NAME, symbol=STARTUP_SYMBOL, period=STARTUP_PERIOD,
                      preset=None):
    """Zweite Startdatei: haengt das EA auf einen Chart. Enthaelt KEINE
    Zugangsdaten — MT5 verbindet sich von selbst wieder mit dem letzten Konto."""
    lines = ["[StartUp]", f"Expert={expert}", f"Symbol={symbol}", f"Period={period}"]
    if preset:
        lines.append(f"ExpertParameters={preset}")
    return "\n".join(lines) + "\n"


def build_preset(snapshot_file, timer_ms=200):
    return f"InpFileName={snapshot_file}\nInpTimerMs={timer_ms}\n"


def build_master_config(base, *, name, master_login, terminal_path, ident, server=""):
    """Neue Instanz-Config aus der bestehenden config.json abgeleitet — Hedge-
    Felder bleiben identisch (check_fleet erzwingt das), Master-Felder neu.
    mode startet hart auf dryrun: eine frisch angelegte Instanz darf niemals
    scharf loslaufen. master_server dient kuenftigen Provisionierungen als
    Quelle fuer die richtige Server-Liste (The5ers-Fall 14.08.2026)."""
    cfg = {k: v for k, v in base.items() if not k.startswith("_")}
    cfg["mode"] = "dryrun"
    cfg["master_expected_login"] = int(master_login)
    cfg["master_terminal_path"] = terminal_path
    cfg["master_server"] = server
    cfg["snapshot_file"] = ident["snapshot"]
    cfg["magic"] = ident["magic"]
    cfg["comment_prefix"] = ident["prefix"]
    cfg["_provisioned"] = f"automatisch angelegt fuer '{name}'"
    return cfg


def servers_dat_source(folder, server, template_data, root=None):
    """Welche servers.dat bekommt der Klon? Reihenfolge (The5ers-Fall):
    1. ein bestehendes Master-Terminal, das auf DEMSELBEN Server laeuft —
       dessen Liste kennt den Namen garantiert;
    2. sonst die Vorlage (reicht fuer denselben Broker wie die Vorlage).
    Rueckgabe: Pfad oder None."""
    want = (server or "").strip().lower()
    root = root or terminals_root()
    if want:
        for fn in sorted(os.listdir(folder)):
            if not fn.lower().endswith(".json") or not fn.lower().startswith("config"):
                continue
            try:
                with open(os.path.join(folder, fn), "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except (OSError, ValueError):
                continue
            if str(cfg.get("master_server", "")).strip().lower() != want:
                continue
            tp = cfg.get("master_terminal_path")
            if not tp:
                continue
            dd = data_dir_for(os.path.dirname(tp), root)
            if dd and os.path.exists(os.path.join(dd, "config", "servers.dat")):
                return os.path.join(dd, "config", "servers.dat")
    p = os.path.join(template_data, "config", "servers.dat")
    return p if os.path.exists(p) else None


def plan_checks(folder, name, login, server, template_exe):
    """Alle Vorbedingungen VOR dem ersten Schreibzugriff. Liste von Problemen."""
    problems = []
    if not name_ok(name):
        problems.append("Name: 1-24 Zeichen A-Z/a-z/0-9, keine Binde-/Leerzeichen "
                        "(sonst erkennt der Copier die Config nicht).")
    try:
        if int(login) <= 0:
            problems.append("Login muss eine Kontonummer sein.")
    except (TypeError, ValueError):
        problems.append(f"Login '{login}' ist keine Zahl.")
    if not (server or "").strip():
        problems.append("Server fehlt (z.B. FusionMarkets-Demo).")
    if name_ok(name):
        cfg_path = os.path.join(folder, f"config-{name}.json")
        if os.path.exists(cfg_path):
            problems.append(f"config-{name}.json existiert schon — Account ist bereits angelegt.")
    if not template_exe or os.path.basename(template_exe).lower() != "terminal64.exe":
        problems.append("Vorlage muss eine terminal64.exe sein (master_terminal_path der config.json).")
    elif not os.path.exists(template_exe):
        problems.append(f"Vorlage nicht gefunden: {template_exe}")
    if not os.path.exists(os.path.join(folder, "config.json")):
        problems.append("config.json fehlt — daraus werden die Hedge-Felder uebernommen.")
    return problems


# ------------------------------------------------------- Windows-Hilfsfunktionen

def terminals_root(appdata=None):
    appdata = appdata or os.environ.get("APPDATA")
    return os.path.join(appdata, "MetaQuotes", "Terminal") if appdata else None


def read_origin(data_dir):
    """Installationspfad, zu dem dieser Datenordner gehoert (origin.txt, UTF-16)."""
    p = os.path.join(data_dir, ORIGIN_FILE)
    for enc in ("utf-16", "utf-8"):
        try:
            with open(p, "r", encoding=enc, errors="strict") as f:
                return f.read().strip().lstrip("﻿")
        except (OSError, UnicodeError):
            continue
    return None


def map_installs(root):
    """{normalisierter Installationspfad: Datenordner} — Zuordnung ueber
    origin.txt, den Hash im Ordnernamen kann man nicht ausrechnen."""
    out = {}
    if not root or not os.path.isdir(root):
        return out
    for entry in sorted(os.listdir(root)):
        if entry.lower() == "common":
            continue
        data_dir = os.path.join(root, entry)
        if not os.path.isdir(data_dir):
            continue
        origin = read_origin(data_dir)
        if origin:
            out[os.path.normcase(os.path.normpath(origin))] = data_dir
    return out


def data_dir_for(install_dir, root=None):
    root = root or terminals_root()
    return map_installs(root).get(os.path.normcase(os.path.normpath(install_dir)))


def _read_journals(data_dir):
    """[(pfad, text)] der Terminal-Journale von gestern und heute
    (<Datenordner>\\logs\\JJJJMMTT.log, Mitternachts-Rollover abgedeckt).
    Kodierung strikt durchprobieren — errors='replace' beim ersten Versuch
    wuerde eine ANSI-Datei still zu Zeichensalat dekodieren."""
    import datetime as _dt
    logs = os.path.join(data_dir, "logs")
    out = []
    for d in (1, 0):
        day = (_dt.date.today() - _dt.timedelta(days=d)).strftime("%Y%m%d")
        p = os.path.join(logs, day + ".log")
        if not os.path.exists(p):
            continue
        text = None
        for enc in ("utf-16", "utf-8", "cp1252"):
            try:
                with open(p, "r", encoding=enc) as f:
                    text = f.read()
                break
            except (UnicodeError, OSError):
                continue
        if text is None:
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
        out.append((p, text))
    return out


def journal_baseline(data_dir):
    """Lesezeichen VOR einer Aktion setzen: {datei: bisherige Textlaenge}.
    Alles davor ist Vergangenheit und darf die Auswertung nicht beeinflussen —
    beim The5e-Rerun (14.08.2026) fand die Pruefung sonst die alten
    authorized/failed-Zeilen der manuellen Versuche von vorhin."""
    return {p: len(t) for p, t in _read_journals(data_dir)}


def _journal_text(data_dir, baseline=None):
    baseline = baseline or {}
    return "\n".join(t[baseline.get(p, 0):] for p, t in _read_journals(data_dir))


def _journal_says(data_dir, needles, baseline=None):
    low = _journal_text(data_dir, baseline).lower()
    for n in needles:
        if n.lower() in low:
            return n
    return None


def _journal_tail(data_dir, baseline=None, n=6):
    lines = [l.strip() for l in _journal_text(data_dir, baseline).splitlines() if l.strip()]
    return " | ".join(lines[-n:]) if lines else "(Journal leer)"


def _kill_terminal_at(install_dir):
    """Beendet ein evtl. noch laufendes Terminal DIESER Installation (z.B. Rest
    eines vorherigen Fehlversuchs). Ein zweiter Start derselben Installation
    wuerde nur das laufende Fenster nach vorn holen und die /config ignorieren."""
    exe = os.path.join(install_dir, "terminal64.exe").replace("\\", "\\\\")
    try:
        r = subprocess.run(["wmic", "process", "where",
                            f"ExecutablePath='{exe}'", "get", "ProcessId"],
                           capture_output=True, text=True, timeout=30)
        for tok in (r.stdout or "").split():
            if tok.isdigit():
                _taskkill(int(tok))
    except Exception:
        pass  # wmic fehlt/zickt -> schlimmstenfalls schlaegt der Start unten fehl


def _taskkill(pid, grace_s=15):
    """Terminal beenden: erst hoeflich (WM_CLOSE), nach Ablauf hart."""
    subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True)
    t0 = time.time()
    while time.time() - t0 < grace_s:
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        if str(pid) not in (r.stdout or ""):
            return
        time.sleep(1)
    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
    time.sleep(2)


# ------------------------------------------------------------------- der Job

def run_provision(*, name, login, password, server, template_exe,
                  folder=HERE, report=lambda step, state, note=None: None):
    """Fuehrt die komplette Provisionierung aus. `report(step, state, note)`
    meldet Fortschritt ans Panel ('running' | 'done' | 'error').

    Schritte:
      pruefen -> klonen -> erststart+login -> ea -> neustart -> config
    """
    def step(key):
        report(key, "running")

    # ── 1. pruefen ──────────────────────────────────────────────────────────
    step("pruefen")
    problems = plan_checks(folder, name, login, server, template_exe)
    if os.name != "nt":
        problems.append("Provisionierung laeuft nur auf dem Windows-PC.")
    template_install = os.path.dirname(os.path.abspath(template_exe or ""))
    target_install = os.path.join(os.path.dirname(template_install), f"MT5-{name}")
    # Ein vorhandener Zielordner OHNE fertige Config ist der Rest eines
    # Fehlversuchs — wiederverwenden statt abbrechen, damit "nochmal Fertig
    # druecken" der natuerliche Retry ist (14.08.2026).
    reuse = os.path.exists(target_install)
    root = terminals_root()
    tpl_data = data_dir_for(template_install, root) if not problems else None
    ex5 = os.path.join(tpl_data, "MQL5", "Experts", EA_NAME + ".ex5") if tpl_data else None
    if not problems:
        if not tpl_data:
            problems.append(f"Kein Datenordner fuer die Vorlage {template_install} gefunden — "
                            f"das Vorlage-Terminal muss einmal gelaufen sein.")
        elif not os.path.exists(ex5):
            problems.append(f"Kompiliertes EA fehlt: {ex5} — im Vorlage-Terminal einmal "
                            f"den MetaEditor oeffnen und {EA_NAME} kompilieren.")
    if problems:
        raise ProvisionError(" · ".join(problems))
    ident = alloc_identity(folder, name)
    report("pruefen", "done", f"magic {ident['magic']} · {ident['snapshot']}")

    # ── 2. klonen ───────────────────────────────────────────────────────────
    step("klonen")
    if not reuse:
        # .log-Dateien auslassen — die haelt das laufende Vorlage-Terminal offen.
        shutil.copytree(template_install, target_install,
                        ignore=shutil.ignore_patterns("*.log"))
        # Falls die Vorlage je im portable-Modus lief, laegen Konten/Configs IM
        # Installationsordner und der Klon wuerde sie erben — vorsorglich raus
        # (Recherche-Stolperfalle 5; bei normalen Installationen existieren die
        # Ordner dort gar nicht).
        for sub in ("Config", "logs", "Bases"):
            shutil.rmtree(os.path.join(target_install, sub), ignore_errors=True)
    target_exe = os.path.join(target_install, "terminal64.exe")
    if not os.path.exists(target_exe):
        raise ProvisionError(f"Klon unvollstaendig — {target_exe} fehlt. Ordner "
                             f"{target_install} am PC loeschen und neu versuchen.")
    report("klonen", "done", target_install + (" (wiederverwendet)" if reuse else ""))

    # ── 3. Nackter Erststart: nur den Datenordner anlegen ───────────────────
    # Ein Login ist hier noch gar nicht moeglich: der frische Klon hat eine
    # LEERE Server-Liste, und die Startdatei sucht den Servernamen nur in
    # servers.dat nach (kein Live-Broker-Scan wie im Dialog). Das war der
    # zweite Fehlversuch am 14.08.2026 — Terminal las die ini, blieb aber
    # netzwerk-still stehen.
    step("login")
    # Rest eines Fehlversuchs? Ein laufendes Terminal derselben Installation
    # wuerde jeden weiteren Start schlucken (Fenster kommt nur nach vorn).
    _kill_terminal_at(target_install)
    proc = subprocess.Popen([target_exe], cwd=target_install)
    new_data = None
    t0 = time.time()
    while time.time() - t0 < 120:
        new_data = data_dir_for(target_install, root)
        if new_data:
            break
        time.sleep(2)
    if not new_data:
        raise ProvisionError("Datenordner des neuen Terminals ist nach 120 s nicht "
                             "aufgetaucht — Terminal-Fenster am PC pruefen.")
    time.sleep(3)
    _taskkill(proc.pid)
    report("login", "done", "Datenordner angelegt")

    # ── 4. Server-Liste + EA + Preset einlegen ──────────────────────────────
    # servers.dat der Vorlage enthaelt nur die bekannten Broker-Server (keine
    # Zugangsdaten) — damit kann die Startdatei den Servernamen aufloesen.
    step("ea")
    target_servers = os.path.join(new_data, "config", "servers.dat")
    if os.path.exists(target_servers):
        # Schon vorhanden = das Terminal hat den Server bereits gelernt (z.B.
        # durch einen manuellen Dialog-Login beim vorigen Versuch) — NICHT mit
        # der Vorlagen-Liste ueberschreiben, sonst verlernt es ihn wieder.
        servers_note = "servers.dat vorhanden (behalten)"
    else:
        src = servers_dat_source(folder, server, tpl_data, root)
        if not src:
            raise ProvisionError("Keine servers.dat gefunden — Vorlage-Terminal einmal "
                                 "starten und wieder schliessen.")
        os.makedirs(os.path.join(new_data, "config"), exist_ok=True)
        shutil.copy2(src, target_servers)
        servers_note = "servers.dat"
    experts = os.path.join(new_data, "MQL5", "Experts")
    presets = os.path.join(new_data, "MQL5", "Presets")
    os.makedirs(experts, exist_ok=True)
    os.makedirs(presets, exist_ok=True)
    shutil.copy2(ex5, os.path.join(experts, EA_NAME + ".ex5"))
    preset_name = f"prophos-{name}.set"
    with open(os.path.join(presets, preset_name), "w", encoding=SET_ENCODING) as f:
        f.write(build_preset(ident["snapshot"]))
    report("ea", "done", f"{servers_note} + {EA_NAME}.ex5 + {preset_name}")

    # ── 5. Start mit Login + EA in EINER Startdatei ─────────────────────────
    # Die kombinierte ini ([Common]-Login mit KeepPrivate=1 + [StartUp]-EA) ist
    # der EINZIGE Ort, an dem das Passwort die Software verlaesst — finally
    # garantiert die Loeschung. Danach: MT5 speichert die Zugangsdaten selbst
    # verschluesselt, der EA bleibt per Chart-Persistenz dauerhaft. Ein
    # weiterer Start mit der ini haengte das EA auf einen ZWEITEN Chart —
    # deshalb wird sie geloescht.
    step("neustart")
    start_ini = os.path.join(target_install, "prophos-start.ini")
    retry_ini = os.path.join(target_install, "prophos-retry.ini")
    # Lesezeichen im Journal + alten Snapshot entfernen: bei einem Rerun duerfen
    # weder alte authorized/failed-Zeilen noch eine liegengebliebene
    # Snapshot-Datei des vorigen Versuchs als frischer Erfolg zaehlen.
    jbase = journal_baseline(new_data)
    common = os.path.join(os.environ.get("APPDATA", ""), "MetaQuotes", "Terminal",
                          "Common", "Files")
    snap_path = os.path.join(common, ident["snapshot"])
    try:
        os.remove(snap_path)
    except OSError:
        pass

    def _wait_snapshot(seconds):
        t0 = time.time()
        while time.time() - t0 < seconds:
            if os.path.exists(snap_path):
                return True
            time.sleep(2)
        return os.path.exists(snap_path)

    try:
        with open(start_ini, "w", encoding=INI_ENCODING) as f:
            f.write(build_login_ini(login, password, server) + "\n"
                    + build_startup_ini(preset=preset_name))
        subprocess.Popen([target_exe, f"/config:{start_ini}"], cwd=target_install)
        # Erst den Login im Journal verifizieren. Beim ERSTEN Konto eines neuen
        # Brokers kann die Startdatei den Servernamen nicht aufloesen — MT5
        # oeffnet dann den vorausgefuellten Login-Dialog (The5ers-Fall
        # 14.08.2026). Deshalb: nach 45 s den Hinweis anzeigen und geduldig
        # weiterwarten — EIN OK-Klick des Nutzers macht den Rest, und der
        # Server ist danach dauerhaft gelernt.
        verdict = None
        t0 = time.time()
        hinted = False
        while time.time() - t0 < 240:
            verdict = _journal_says(new_data, ["authorization failed", "invalid account",
                                               "authorized"], jbase)
            if verdict:
                break
            if not hinted and time.time() - t0 > 45:
                hinted = True
                report("neustart", "running",
                       "Zeigt das neue Terminal ein Login-Fenster? Dann dort einmal "
                       "OK klicken (neuer Broker — nur beim ersten Konto noetig)")
            time.sleep(3)
        if verdict != "authorized":
            raise ProvisionError(
                f"Login nicht bestaetigt ({verdict or 'kein Journal-Eintrag in 4 min'}) — "
                f"Kontonummer/Passwort/Servername pruefen; falls ein Login-Fenster im "
                f"Terminal offen ist, dort OK klicken und nochmal 'Fertig' druecken. "
                f"Journal: {_journal_tail(new_data, jbase)}")
        # … dann der Snapshot: der Beweis, dass auch das EA laeuft — der
        # staerkste Check, den es gibt: unser eigenes EA schreibt ihn.
        if not _wait_snapshot(60):
            # Live getroffen 14.08.2026 (The5ers-Lauf): das frische Terminal hat
            # sich beim Einrichten per LiveUpdate selbst neu gestartet ("full
            # recompilation has been started" im Journal) und den [StartUp]-EA
            # dabei verworfen ("loaded successfully" → "removed"). Heilung:
            # Terminal neu starten und den EA ein zweites Mal aufziehen — die
            # Retry-ini enthaelt KEIN Passwort, der Login ist schon gespeichert.
            report("neustart", "running", "EA fehlt (Terminal-Update?) — zweiter Anlauf")
            _kill_terminal_at(target_install)
            with open(retry_ini, "w", encoding=INI_ENCODING) as f:
                f.write(build_startup_ini(preset=preset_name))
            subprocess.Popen([target_exe, f"/config:{retry_ini}"], cwd=target_install)
            if not _wait_snapshot(90):
                raise ProvisionError(
                    f"Login ok, aber Snapshot {ident['snapshot']} kam auch im zweiten "
                    f"Anlauf nicht — im neuen Terminal Reiter 'Experten' pruefen. "
                    f"Journal: {_journal_tail(new_data, jbase)}")
    finally:
        for p in (start_ini, retry_ini):
            try:
                os.remove(p)
            except OSError:
                pass
    report("neustart", "done", "Login bestaetigt · Snapshot fliesst · Startdateien geloescht")

    # ── 6. Config anlegen — der laufende Copier nimmt sie binnen 5 s auf ────
    step("config")
    with open(os.path.join(folder, "config.json"), "r", encoding="utf-8") as f:
        base = json.load(f)
    cfg = build_master_config(base, name=name, master_login=login,
                              terminal_path=target_exe, ident=ident, server=server)
    cfg_path = os.path.join(folder, f"config-{name}.json")
    tmp = cfg_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, cfg_path)
    report("config", "done", os.path.basename(cfg_path))
    return {"config": os.path.basename(cfg_path), **ident}
