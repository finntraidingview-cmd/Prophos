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
# MT5 schreibt seine eigenen ini/set-Dateien als UTF-16 LE; eigene Startdateien
# werden in dieser Kodierung zuverlaessig gelesen (ASCII-ini geht meist auch,
# UTF-16 ist die sichere Wahl).
INI_ENCODING = "utf-16"
SET_ENCODING = "utf-16"

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


def build_master_config(base, *, name, master_login, terminal_path, ident):
    """Neue Instanz-Config aus der bestehenden config.json abgeleitet — Hedge-
    Felder bleiben identisch (check_fleet erzwingt das), Master-Felder neu.
    mode startet hart auf dryrun: eine frisch angelegte Instanz darf niemals
    scharf loslaufen."""
    cfg = {k: v for k, v in base.items() if not k.startswith("_")}
    cfg["mode"] = "dryrun"
    cfg["master_expected_login"] = int(master_login)
    cfg["master_terminal_path"] = terminal_path
    cfg["snapshot_file"] = ident["snapshot"]
    cfg["magic"] = ident["magic"]
    cfg["comment_prefix"] = ident["prefix"]
    cfg["_provisioned"] = f"automatisch angelegt fuer '{name}'"
    return cfg


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


def _journal_says(data_dir, needles, since_ts):
    """Sucht im Terminal-Journal (<Datenordner>\\logs\\JJJJMMTT.log, UTF-16) nach
    einem der Begriffe. Heute UND gestern pruefen (Mitternachts-Rollover)."""
    import datetime as _dt
    logs = os.path.join(data_dir, "logs")
    for d in (0, 1):
        day = (_dt.date.today() - _dt.timedelta(days=d)).strftime("%Y%m%d")
        p = os.path.join(logs, day + ".log")
        try:
            if os.path.getmtime(p) < since_ts - 60:
                continue
            for enc in ("utf-16", "utf-8"):
                try:
                    with open(p, "r", encoding=enc, errors="replace") as f:
                        text = f.read()
                    break
                except (UnicodeError, OSError):
                    text = ""
            low = text.lower()
            for n in needles:
                if n.lower() in low:
                    return n
        except OSError:
            continue
    return None


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
    if os.path.exists(target_install):
        problems.append(f"Zielordner existiert schon: {target_install} — nichts wird ueberschrieben.")
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
        raise ProvisionError(f"Klon unvollstaendig — {target_exe} fehlt.")
    report("klonen", "done", target_install)

    # ── 3. Erststart mit Login ──────────────────────────────────────────────
    # Die transiente ini ist der EINZIGE Ort, an dem das Passwort die Software
    # verlaesst. finally garantiert die Loeschung — auch im Fehlerfall.
    step("login")
    login_ini = os.path.join(target_install, "prophos-login.ini")
    proc = None
    started_ts = time.time()
    try:
        with open(login_ini, "w", encoding=INI_ENCODING) as f:
            f.write(build_login_ini(login, password, server))
        proc = subprocess.Popen([target_exe, f"/config:{login_ini}"], cwd=target_install)
        # Warten, bis MT5 seinen Datenordner angelegt hat (origin.txt zeigt auf
        # uns). Bewusst NICHT am Prozess festhalten: ein LiveUpdate kann das
        # Terminal mitten im Erststart neu starten (Recherche-Stolperfalle 2).
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
        # Login im Journal verifizieren, ERST DANN gilt der Schritt als fertig.
        verdict = None
        t0 = time.time()
        while time.time() - t0 < 90:
            verdict = _journal_says(new_data, ["authorization failed", "invalid account",
                                               "authorized"], started_ts)
            if verdict:
                break
            time.sleep(3)
        if verdict != "authorized":
            raise ProvisionError(
                f"Login nicht bestaetigt ({verdict or 'kein Journal-Eintrag in 90 s'}) — "
                f"Kontonummer/Passwort/Servername pruefen (Server muss exakt stimmen, "
                f"z.B. 'FusionMarkets-Demo').")
    finally:
        try:
            os.remove(login_ini)
        except OSError:
            pass
    report("login", "done", "Login bestaetigt · Zugangsdaten-Datei geloescht")

    # ── 4. Terminal sauber beenden, dann EA + Preset einlegen ───────────────
    # Reihenfolge laut Recherche: erst sauberes Beenden (sichert accounts.dat
    # und Profil), dann Dateien in den Datenordner.
    step("ea")
    if proc is not None:
        _taskkill(proc.pid)
    experts = os.path.join(new_data, "MQL5", "Experts")
    presets = os.path.join(new_data, "MQL5", "Presets")
    os.makedirs(experts, exist_ok=True)
    os.makedirs(presets, exist_ok=True)
    shutil.copy2(ex5, os.path.join(experts, EA_NAME + ".ex5"))
    preset_name = f"prophos-{name}.set"
    with open(os.path.join(presets, preset_name), "w", encoding=SET_ENCODING) as f:
        f.write(build_preset(ident["snapshot"]))
    report("ea", "done", f"{EA_NAME}.ex5 + {preset_name}")

    # ── 5. Zweitstart: EA landet per [StartUp] auf einem Chart ──────────────
    # Diese ini enthaelt KEINE Zugangsdaten; MT5 verbindet sich selbst wieder
    # (KeepPrivate=1 beim Erststart). Der EA bleibt danach dauerhaft auf dem
    # Chart (Chart-Persistenz). Die ini wird nach Erfolg GELOESCHT — ein
    # weiterer Start damit haengte das EA auf einen ZWEITEN Chart (Duplikat).
    step("neustart")
    start_ini = os.path.join(target_install, "prophos-start.ini")
    with open(start_ini, "w", encoding=INI_ENCODING) as f:
        f.write(build_startup_ini(preset=preset_name))
    try:
        subprocess.Popen([target_exe, f"/config:{start_ini}"], cwd=target_install)
        # Snapshot-Datei ist der Beweis, dass Login UND EA stehen — der
        # staerkste Check, den es gibt: unser eigenes EA schreibt sie.
        common = os.path.join(os.environ.get("APPDATA", ""), "MetaQuotes", "Terminal",
                              "Common", "Files")
        snap_path = os.path.join(common, ident["snapshot"])
        t0 = time.time()
        while time.time() - t0 < 120:
            if os.path.exists(snap_path):
                break
            time.sleep(2)
        if not os.path.exists(snap_path):
            raise ProvisionError(f"Snapshot {ident['snapshot']} ist nach 120 s nicht erschienen. "
                                 f"Im neuen Terminal pruefen: eingeloggt? EA auf dem Chart "
                                 f"(Reiter 'Experten')?")
    finally:
        try:
            os.remove(start_ini)
        except OSError:
            pass
    report("neustart", "done", "Snapshot fliesst · Start-Datei geloescht")

    # ── 6. Config anlegen — der laufende Copier nimmt sie binnen 5 s auf ────
    step("config")
    with open(os.path.join(folder, "config.json"), "r", encoding="utf-8") as f:
        base = json.load(f)
    cfg = build_master_config(base, name=name, master_login=login,
                              terminal_path=target_exe, ident=ident)
    cfg_path = os.path.join(folder, f"config-{name}.json")
    tmp = cfg_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, cfg_path)
    report("config", "done", os.path.basename(cfg_path))
    return {"config": os.path.basename(cfg_path), **ident}
