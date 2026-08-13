#!/usr/bin/env python3
"""
Account-Provisionierung fuer den MT5-Hedge-Copier.

Legt einen neuen Account an, ohne dass jemand Ordner klickt, Kontonummern in
Terminals tippt oder Dateinamen von Hand vergibt. Genau das Tippen von Hand war
naemlich die scharfe Falle: das Lese-EA schreibt seinen Snapshot in den
GEMEINSAMEN MT5-Ordner (FILE_COMMON), den sich alle Installationen eines
Windows-Benutzers teilen. Zwei Master mit dem Vorgabenamen "prophos_master.csv"
ueberschreiben sich alle 200 ms gegenseitig. Dasselbe gilt fuer `magic`: beide
Vorlagen haben heute 770001, und der Copier erkennt seine eigenen Hedges primaer
an der Magic — bei Gleichstand haelt Instanz A die Hedges von B fuer verwaist und
schliesst sie. Deshalb vergibt dieses Skript snapshot_file, magic und
comment_prefix selbst und fortlaufend; sie koennen gar nicht mehr kollidieren.
(13.08.2026, nach dem Multi-Account-Audit.)

Was es NICHT tut, mit Absicht:
- Es startet das Prop-/Master-Terminal nicht neu. Dort tradest du per Parsec.
  Es legt EA und Preset nur bereit, das Aufziehen auf den Chart bleibt dein Klick.
- Es ruft nie mt5.login() und fasst copier.py nicht an. Der Login passiert beim
  Start eines frischen Hedge-Terminals, das noch keine Position offen hat —
  der Sicherheitsanker des Copiers ("ein Terminal-Ordner = ein Konto") bleibt heil.
- Es traegt keine Zugangsdaten ein. accounts.json wird mit leeren Passwortfeldern
  angelegt; die fuellst du selbst.

Benutzung (Windows):

    python provision.py scan
    python provision.py new ftmo                 # legt den Eintrag in accounts.json an
    ... accounts.json ausfuellen ...
    python provision.py add ftmo                 # zeigt nur den Plan
    python provision.py add ftmo --apply         # fuehrt ihn aus

Der laufende Copier braucht danach keinen Neustart-Befehl von dir: er liest alle
config*.json des Ordners als Flotte (copier.py: discover_configs).

Nur Standardbibliothek. Die reinen Funktionen laufen auch auf dem Mac, damit man
den Plan pruefen kann, ohne Windows zu haben.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Muss zu copier.py/panel.py passen — dort entscheidet dieses Muster, ob eine
# Datei ueberhaupt als Instanz erkannt wird. Name darf keine Bindestriche
# enthalten, sonst faellt die fertige Config stumm aus der Flotte heraus.
CONFIG_RE = re.compile(r"config(?:[-_][A-Za-z0-9]{1,24})?\.json", re.I)
TEMPLATES = ("config.example.json", "config.fusion-test.json")
NAME_RE = re.compile(r"[A-Za-z0-9]{1,24}")

ACCOUNTS_FILE = "accounts.json"      # steht in .gitignore — enthaelt Passwoerter
EA_NAME = "ProphosHedgeReader"
MAGIC_BASE = 770000                  # erste vergebene Magic ist 770001

# MT5 legt fuer jede Installation einen Datenordner unter
# %APPDATA%\MetaQuotes\Terminal\<HASH> an. Den Hash kann man nicht ausrechnen,
# aber jeder Datenordner enthaelt eine origin.txt mit seinem Installationspfad —
# darueber ist die Zuordnung eindeutig und ohne Raterei moeglich.
ORIGIN_FILE = "origin.txt"


# ---------------------------------------------------------------- reine Logik

def name_ok(name):
    return bool(NAME_RE.fullmatch(name or ""))


def terminals_root(appdata=None):
    """Wurzel der MT5-Datenordner. Auf dem Mac gibt es kein APPDATA — dann None,
    damit `scan` sauber meldet statt mit einem KeyError abzubrechen."""
    appdata = appdata or os.environ.get("APPDATA")
    if not appdata:
        return None
    return os.path.join(appdata, "MetaQuotes", "Terminal")


def read_origin(data_dir):
    """Installationspfad, zu dem dieser Datenordner gehoert (oder None)."""
    p = os.path.join(data_dir, ORIGIN_FILE)
    try:
        with open(p, "r", encoding="utf-16") as f:
            return f.read().strip().strip("﻿")
    except (OSError, UnicodeError):
        pass
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip().strip("﻿")
    except OSError:
        return None


def map_installs(root):
    """{normalisierter Installationspfad: Datenordner} fuer alle Installationen.
    'Common' ist der geteilte Ordner, keine Installation — der fliegt raus."""
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


def data_dir_for(install_dir, root):
    """Datenordner einer Installation, ueber origin.txt. None = Terminal lief
    dort noch nie (der Datenordner entsteht erst beim ersten Start)."""
    return map_installs(root).get(os.path.normcase(os.path.normpath(install_dir)))


def existing_configs(folder):
    out = []
    for fn in sorted(os.listdir(folder)):
        if fn in TEMPLATES or fn.endswith(".tmp"):
            continue
        if CONFIG_RE.fullmatch(fn):
            out.append(os.path.join(folder, fn))
    return out


def used_values(folder):
    """Was in der Flotte schon vergeben ist — inklusive der Vorlagen. Die
    Vorlagen zaehlen bewusst mit: config.fusion-test.json ist eine echte
    Testinstanz, deren magic 770001 sonst doppelt vergeben wuerde."""
    magics, snapshots, prefixes = set(), set(), set()
    for fn in sorted(os.listdir(folder)):
        if not CONFIG_RE.fullmatch(fn) or fn.endswith(".tmp"):
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
    """PH, PH2, PH3 … Der Copier sucht den Token als Praefix 'PH-<identifier>';
    'PH2-' faengt nicht mit 'PH-' an, die Praefixe sind also trennscharf."""
    idx = magic - MAGIC_BASE
    cand = "PH" if idx <= 1 else f"PH{idx}"
    while cand in taken:
        idx += 1
        cand = f"PH{idx}"
    return cand


def build_config(base, name, hedge_path, hedge_login, master_login,
                 snapshot_file, magic, comment_prefix):
    """Neue Instanz-Config aus der Vorlage. mode bleibt hart auf dryrun — eine
    frisch angelegte Instanz darf niemals scharf starten, egal was in der
    Vorlage stand."""
    cfg = dict(base)
    cfg["mode"] = "dryrun"
    cfg["hedge_terminal_path"] = hedge_path
    cfg["hedge_portable"] = False
    cfg["hedge_expected_login"] = int(hedge_login)
    cfg["master_expected_login"] = int(master_login)
    cfg["snapshot_file"] = snapshot_file
    cfg["magic"] = magic
    cfg["comment_prefix"] = comment_prefix
    cfg["_provisioned"] = f"angelegt von provision.py fuer Account '{name}'"
    return cfg


def build_ini(login, password, server, expert=None, preset=None,
              symbol="EURUSD", period="M1"):
    """Startdatei fuer terminal64.exe. [Common] loggt das Terminal selbst ein,
    [StartUp] zieht das EA mit dem richtigen Preset auf."""
    lines = ["[Common]", f"Login={login}", f"Password={password}", f"Server={server}"]
    if expert:
        lines += ["", "[StartUp]", f"Expert={expert}", f"Symbol={symbol}", f"Period={period}"]
        if preset:
            lines.append(f"ExpertParameters={preset}")
    return "\n".join(lines) + "\n"


def build_set(snapshot_file, timer_ms=200):
    """Preset fuer das Lese-EA. Der Dateiname wird hier vergeben, nicht getippt —
    genau deshalb kann die Snapshot-Kollision nicht mehr passieren."""
    return f"InpFileName={snapshot_file}\nInpTimerMs={timer_ms}\n"


def plan_account(acc, folder=HERE, root=None, template_install=None):
    """Was passieren wuerde, als Liste von Schritten. Kein Schreibzugriff.
    Jeder Schritt: (art, ziel, inhalt_oder_quelle, hinweis)."""
    name = acc["name"]
    problems = []
    if not name_ok(name):
        problems.append(f"Name '{name}' ist unbrauchbar — erlaubt sind 1-24 Zeichen A-Z/a-z/0-9, "
                        f"KEIN Bindestrich (sonst erkennt der Copier die Config nicht).")
    cfg_path = os.path.join(folder, f"config-{name}.json")
    if os.path.exists(cfg_path):
        problems.append(f"{os.path.basename(cfg_path)} existiert schon — Account '{name}' ist bereits angelegt.")

    for feld in ("hedge_login", "hedge_password", "hedge_server", "master_login"):
        if not acc.get(feld):
            problems.append(f"accounts.json: '{feld}' ist leer.")

    tpl = os.path.join(folder, "config.example.json")
    base = {}
    if os.path.exists(tpl):
        try:
            with open(tpl, "r", encoding="utf-8") as f:
                base = json.load(f)
        except ValueError as e:
            problems.append(f"config.example.json ist kaputt: {e}")
    else:
        problems.append("config.example.json fehlt — daraus wird die neue Config abgeleitet.")

    magics, snapshots, prefixes = used_values(folder)
    magic = next_magic(magics)
    prefix = prefix_for(magic, prefixes)
    snapshot = f"prophos_master_{name}.csv"
    if snapshot.lower() in snapshots:
        problems.append(f"snapshot_file '{snapshot}' ist schon vergeben.")

    hedge_install = acc.get("hedge_install") or (
        os.path.join(os.path.dirname(template_install), f"MT5-Hedge-{name}")
        if template_install else "")
    hedge_exe = os.path.join(hedge_install, "terminal64.exe") if hedge_install else ""

    steps = []
    if template_install:
        if not os.path.isdir(template_install):
            problems.append(f"Vorlage-Installation nicht gefunden: {template_install}")
        if hedge_install and os.path.exists(hedge_install):
            problems.append(f"Zielordner existiert schon: {hedge_install} — nichts wird ueberschrieben.")
        steps.append(("kopieren", hedge_install, template_install,
                      "MT5-Installation klonen (neuer Pfad = eigener Datenordner)"))
        steps.append(("schreiben", os.path.join(hedge_install, "config", f"prophos-{name}.ini"),
                      build_ini(acc.get("hedge_login", ""), "***", acc.get("hedge_server", "")),
                      "Startdatei mit Login fuer das Hedge-Terminal"))
        steps.append(("starten", hedge_exe, f"config\\prophos-{name}.ini",
                      "Terminal einmal hochfahren — loggt sich selbst ein"))

    master_install = acc.get("master_install") or ""
    master_data = data_dir_for(master_install, root) if (master_install and root) else None
    if master_install and not master_data:
        problems.append(f"Kein Datenordner fuer {master_install} gefunden (origin.txt). "
                        f"Das Terminal muss dort einmal gelaufen sein.")
    if master_data:
        steps.append(("kopieren", os.path.join(master_data, "MQL5", "Experts", EA_NAME + ".ex5"),
                      os.path.join(folder, EA_NAME + ".ex5"),
                      "kompiliertes Lese-EA ins Master-Terminal legen"))
        steps.append(("schreiben", os.path.join(master_data, "MQL5", "Presets", f"prophos-{name}.set"),
                      build_set(snapshot),
                      "Preset mit dem eindeutigen Snapshot-Namen"))

    steps.append(("schreiben", cfg_path,
                  json.dumps(build_config(base, name, hedge_exe, acc.get("hedge_login") or 0,
                                          acc.get("master_login") or 0, snapshot, magic, prefix),
                             ensure_ascii=False, indent=2),
                  f"Instanz-Config (magic {magic}, prefix {prefix}, mode dryrun)"))

    return {"name": name, "magic": magic, "prefix": prefix, "snapshot": snapshot,
            "hedge_install": hedge_install, "master_data": master_data,
            "steps": steps, "problems": problems}


# ------------------------------------------------------------------ Ausfuehren

def apply_plan(plan, acc, encoding="utf-8"):
    """Fuehrt den Plan aus. Wird nur aufgerufen, wenn plan['problems'] leer ist."""
    started = None
    for art, ziel, quelle, _hinweis in plan["steps"]:
        if art == "kopieren":
            if os.path.isdir(quelle):
                print(f"  kopiere {quelle} -> {ziel} (dauert)")
                shutil.copytree(quelle, ziel)
            else:
                if not os.path.exists(quelle):
                    print(f"  UEBERSPRUNGEN: {quelle} fehlt (EA erst kompilieren)")
                    continue
                os.makedirs(os.path.dirname(ziel), exist_ok=True)
                shutil.copy2(quelle, ziel)
                print(f"  kopiert {os.path.basename(quelle)} -> {ziel}")
        elif art == "schreiben":
            os.makedirs(os.path.dirname(ziel), exist_ok=True)
            inhalt = quelle
            # Das Passwort steht im Plan nur als *** — beim echten Schreiben
            # kommt es aus accounts.json, damit es nie im Klartext geloggt wird.
            if ziel.endswith(".ini"):
                inhalt = build_ini(acc.get("hedge_login", ""), acc.get("hedge_password", ""),
                                   acc.get("hedge_server", ""))
            with open(ziel, "w", encoding=encoding) as f:
                f.write(inhalt)
            print(f"  geschrieben {ziel}")
        elif art == "starten":
            started = (ziel, quelle)
    if started:
        exe, ini = started
        if os.path.exists(exe):
            print(f"  starte {exe} {ini}")
            subprocess.Popen([exe, ini], cwd=os.path.dirname(exe))
        else:
            print(f"  UEBERSPRUNGEN: {exe} nicht gefunden")


# ----------------------------------------------------------------------- CLI

def load_accounts(folder=HERE):
    p = os.path.join(folder, ACCOUNTS_FILE)
    if not os.path.exists(p):
        return {"accounts": []}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_accounts(data, folder=HERE):
    p = os.path.join(folder, ACCOUNTS_FILE)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    return p


def cmd_scan(args):
    root = args.root or terminals_root()
    if not root:
        print("Kein MT5-Datenordner gefunden (APPDATA fehlt — das hier ist kein Windows).")
        print("Zum Testen: provision.py scan --root <ordner>")
        return 1
    installs = map_installs(root)
    if not installs:
        print(f"Keine Installationen unter {root} gefunden.")
        return 1
    print(f"MT5-Installationen laut origin.txt (Wurzel: {root}):\n")
    for origin, data in sorted(installs.items()):
        print(f"  {origin}")
        print(f"      Datenordner: {data}")
    return 0


def cmd_new(args):
    if not name_ok(args.name):
        print(f"Name '{args.name}' ist unbrauchbar — 1-24 Zeichen A-Z/a-z/0-9, kein Bindestrich.")
        return 1
    data = load_accounts()
    if any(a.get("name") == args.name for a in data.get("accounts", [])):
        print(f"Account '{args.name}' steht schon in {ACCOUNTS_FILE}.")
        return 1
    data.setdefault("accounts", []).append({
        "name": args.name,
        "hedge_install": "",
        "hedge_login": "",
        "hedge_password": "",
        "hedge_server": "",
        "master_install": "",
        "master_login": "",
    })
    p = save_accounts(data)
    print(f"Eintrag '{args.name}' angelegt in {p}.")
    print("Jetzt die leeren Felder ausfuellen (Kontonummern, Passwort, Servername,")
    print("Installationspfade — 'provision.py scan' zeigt die Pfade). Danach:")
    print(f"    python provision.py add {args.name}")
    return 0


def cmd_add(args):
    data = load_accounts()
    acc = next((a for a in data.get("accounts", []) if a.get("name") == args.name), None)
    if acc is None:
        print(f"Account '{args.name}' steht nicht in {ACCOUNTS_FILE}. Erst: provision.py new {args.name}")
        return 1
    root = args.root or terminals_root()
    plan = plan_account(acc, HERE, root, args.template)

    print(f"\nPLAN fuer Account '{plan['name']}'")
    print(f"  magic {plan['magic']} · prefix {plan['prefix']} · snapshot {plan['snapshot']}\n")
    for i, (art, ziel, _q, hinweis) in enumerate(plan["steps"], 1):
        print(f"  {i}. [{art}] {ziel}")
        print(f"       {hinweis}")
    if plan["problems"]:
        print("\nPROBLEME — nichts wird ausgefuehrt:")
        for p in plan["problems"]:
            print(f"  - {p}")
        return 1
    if not args.apply:
        print("\nNur der Plan. Ausfuehren mit  --apply")
        return 0

    print("\nAUSFUEHREN:")
    apply_plan(plan, acc, encoding=args.ini_encoding)
    print(f"\nFertig. Der Copier nimmt config-{plan['name']}.json beim naechsten Durchlauf")
    print("automatisch in die Flotte auf (mode: dryrun). Noch offen, von Hand:")
    print(f"  - im Master-Terminal das EA {EA_NAME} auf einen Chart ziehen")
    print(f"    und beim Aufziehen das Preset 'prophos-{plan['name']}' laden")
    print("  - im Panel pruefen, dass die neue Karte auftaucht und laeuft")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Accounts fuer den MT5-Hedge-Copier anlegen.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="MT5-Installationen und ihre Datenordner zeigen")
    s.add_argument("--root", help="Wurzel der Datenordner (Standard: %%APPDATA%%\\MetaQuotes\\Terminal)")
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser("new", help="leeren Account-Eintrag in accounts.json anlegen")
    s.add_argument("name")
    s.set_defaults(func=cmd_new)

    s = sub.add_parser("add", help="Account provisionieren (ohne --apply nur der Plan)")
    s.add_argument("name")
    s.add_argument("--template", help="MT5-Installation, die als Vorlage geklont wird")
    s.add_argument("--root", help="Wurzel der Datenordner (fuer Tests)")
    s.add_argument("--ini-encoding", default="utf-8",
                   help="Kodierung der Startdatei. Ignoriert das Terminal die ini, "
                        "ist utf-16 der naechste Versuch — siehe Kopf der Datei.")
    s.add_argument("--apply", action="store_true", help="Plan wirklich ausfuehren")
    s.set_defaults(func=cmd_add)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
