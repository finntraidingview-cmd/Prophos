#!/usr/bin/env python3
"""
Prophos Copier-Panel — kleines Web-Frontend für den lokalen MT5-Copier auf DIESEM PC.

Zweck: Multiplikator, Symbol-Mapping, max_lots und Modus im Browser setzen statt in der
Textdatei — für mehrere Master/Prop-Firmen gleichzeitig. Zeigt außerdem live, was der
Copier pro Master gerade macht (Konten, offene Hedges, Log), und kann das jeweilige
Master-Terminal starten (MT5 merkt sich den Login pro Ordner — hier werden KEINE
Zugangsdaten gespeichert).

Bewusst eigenständig: Prophos (app.py / prophos.html) wird NICHT angefasst.

Technik:
  · Nur Python-Standardbibliothek — kein pip install, keine Cloud, keine Schlüssel.
  · Bindet ausschließlich an 127.0.0.1 — aus dem Netz nicht erreichbar.
  · Jede config*.json im Ordner ist ein Master (config.json, config-master2.json, …).
    Seit 13.08.2026 bedient EIN copier.py-Prozess alle Configs zugleich; der Status
    je Master liegt in der passenden status*.json.

Start:  python panel.py     →  http://127.0.0.1:8770
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime

import provision

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PANEL_PORT", "8770"))

# Nur diese Felder darf das Panel schreiben. Terminal-Pfade, magic und die erwarteten
# Kontonummern bleiben tabu — das sind die Sicherheitsanker des Copiers.
WRITABLE = {"multiplier", "symbol_map", "max_lots_per_hedge", "mode"}
MODES = ("dryrun", "demo", "live")
# Dieselbe strenge Namensregel wie in copier.py — Explorer-Kopien wie
# "config - Kopie.json" oder "config (2).json" sind KEINE Instanz (Audit 13.08.2026:
# solche Karten sahen echt aus, steuerten aber nichts).
CONFIG_RE = re.compile(r"config(?:[-_][A-Za-z0-9]{1,24})?\.json", re.I)
TEMPLATES = ("config.example.json", "config.fusion-test.json")
SYMBOL_RE = re.compile(r"[A-Za-z0-9._#!&\-]{1,32}")


def instances():
    """Alle Master-Configs -> [{name, config_file, status_file}]. Schlüssel für alle
    API-Aufrufe ist config_file — der abgeleitete Name ist reine Anzeige (Audit-Fund:
    config-master2.json und config_master2.json ergaben denselben Namen, und der
    Save traf die falsche Datei)."""
    out = []
    for fn in sorted(os.listdir(HERE)):
        if fn in TEMPLATES or not CONFIG_RE.fullmatch(fn):
            continue
        name = fn[len("config"):-len(".json")].lstrip("-_") or "standard"
        out.append({"name": name, "config_file": fn,
                    "status_file": re.sub(r"^config", "status", fn, count=1, flags=re.I)})
    return out


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def snapshot():
    data, conflicts = [], []
    seen_magic, seen_snap = {}, {}
    for inst in instances():
        cfg = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
        st = read_json(os.path.join(HERE, inst["status_file"]), {}) or {}
        age = None
        if st.get("updated_at"):
            try:
                age = round((datetime.now() - datetime.fromisoformat(st["updated_at"])).total_seconds())
            except Exception:
                age = None
        magic = cfg.get("magic", 770001)
        snapf = str(cfg.get("snapshot_file", "prophos_master.csv")).lower()
        seen_magic.setdefault(magic, []).append(inst["config_file"])
        seen_snap.setdefault(snapf, []).append(inst["config_file"])
        data.append({
            "name": inst["name"],
            "file": inst["config_file"],
            "mode": cfg.get("mode"),
            "multiplier": cfg.get("multiplier"),
            "max_lots": cfg.get("max_lots_per_hedge"),
            "symbol_map": cfg.get("symbol_map") or {},
            "magic": magic,
            "snapshot_file": cfg.get("snapshot_file"),
            "master_expected": cfg.get("master_expected_login"),
            "hedge_expected": cfg.get("hedge_expected_login"),
            "master_server": cfg.get("master_server"),
            "has_terminal": bool(cfg.get("master_terminal_path")),
            "status": st,
            "age": age,
            # "lebt" = Statusdatei ist frisch. Der Copier schreibt alle ~3s.
            "alive": bool(st.get("running")) and age is not None and age <= 15,
        })
    # Konflikte, die der Copier beim Start mit Abbruch quittieren wuerde — hier
    # schon anzeigen, BEVOR jemand den Neustart auslöst.
    for magic, fs in seen_magic.items():
        if len(fs) > 1:
            conflicts.append(f"magic {magic} doppelt: {', '.join(fs)} — der Copier startet so nicht.")
    for snapf, fs in seen_snap.items():
        if len(fs) > 1:
            conflicts.append(f"snapshot_file '{snapf}' doppelt: {', '.join(fs)} — der Copier startet so nicht.")
    job = None
    if PROV_JOB:
        job = {"name": PROV_JOB["name"], "done": PROV_JOB["done"], "error": PROV_JOB["error"],
               "steps": [{"key": k, **PROV_JOB["steps"][k]} for k in PROV_STEPS]}
    return {"instances": data, "conflicts": conflicts, "job": job,
            "plans": advance_plans(data), "version": _local_version()}


def patch_config(fname, patch):
    """Nur erlaubte Felder schreiben, Datei atomar ersetzen."""
    path = os.path.join(HERE, fname)
    cfg = read_json(path)
    if cfg is None:
        return False, f"{fname} nicht lesbar"
    changed = []
    for k, v in patch.items():
        if k not in WRITABLE:
            continue
        if k == "mode":
            v = str(v).lower()
            if v not in MODES:
                return False, f"Modus '{v}' ungueltig"
        if k in ("multiplier", "max_lots_per_hedge"):
            try:
                v = float(v)
            except (TypeError, ValueError):
                return False, f"{k}: '{v}' ist keine Zahl"
            if v <= 0:
                return False, f"{k} muss groesser als 0 sein"
        if k == "symbol_map":
            if not isinstance(v, dict):
                return False, "symbol_map muss Text→Text sein"
            for a, b in v.items():
                if not isinstance(a, str) or not isinstance(b, str) \
                        or not SYMBOL_RE.fullmatch(a) or not SYMBOL_RE.fullmatch(b):
                    # Verengt auf Symbolzeichen — haelt auch Anfuehrungszeichen aus dem
                    # HTML fern (Audit-Fund: ein " im Symbolfeld verdrehte die Karte).
                    return False, f"Symbol ungueltig: '{a}' → '{b}'"
        if cfg.get(k) != v:
            cfg[k] = v
            changed.append(k)
    if not changed:
        return True, "keine Aenderung"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return True, "gespeichert: " + ", ".join(changed)


# ── Trade-Plaene: geplant -> laufend -> beendet (15.08.2026, Prophos-Logik) ────
# Ein Plan entsteht beim "Trade starten" (geplant), wechselt AUTOMATISCH auf
# "laufend", sobald der Master wirklich eine Position oeffnet, und auf
# "beendet", wenn sie wieder zu ist — getrieben vom Positionsstand aus den
# status*.json, nicht von Klicks. Ein aktiver Plan (geplant/laufend) pro
# Account; ein erneuter Start aktualisiert ihn nur.
PLANS_FILE = os.path.join(HERE, "plans.json")
PLANS_LOCK = threading.Lock()


def _load_plans():
    return read_json(PLANS_FILE, []) or []


def _save_plans(plans):
    tmp = PLANS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(plans, f, ensure_ascii=False, indent=1)
    os.replace(tmp, PLANS_FILE)


def upsert_plan(file, name, multiplier, max_lots, mode):
    with PLANS_LOCK:
        plans = _load_plans()
        now = datetime.now().isoformat(timespec="seconds")
        for p in plans:
            if p["file"] == file and p["status"] in ("geplant", "laufend"):
                p.update({"multiplier": multiplier, "max_lots": max_lots,
                          "mode": mode, "armed_at": now})
                _save_plans(plans)
                return p
        pid = max([p["id"] for p in plans], default=0) + 1
        p = {"id": pid, "file": file, "name": name, "multiplier": multiplier,
             "max_lots": max_lots, "mode": mode, "created_at": now,
             "armed_at": now, "started_at": None, "ended_at": None,
             "status": "geplant"}
        plans.append(p)
        _save_plans(plans)
        return p


def delete_plan(pid):
    with PLANS_LOCK:
        plans = _load_plans()
        keep = [p for p in plans if p["id"] != pid]
        if len(keep) == len(plans):
            return False
        _save_plans(keep)
        return True


def _instances_snapshot():
    """Nur die Instanz-Daten (ohne den ganzen API-Payload) — fuer den
    Plan-Ticker, der die Zustandsmaschine unabhaengig vom Browser treibt."""
    out = []
    for inst in instances():
        st = read_json(os.path.join(HERE, inst["status_file"]), {}) or {}
        age = None
        if st.get("updated_at"):
            try:
                age = round((datetime.now() - datetime.fromisoformat(st["updated_at"])).total_seconds())
            except Exception:
                age = None
        out.append({"file": inst["config_file"], "status": st, "age": age,
                    "alive": bool(st.get("running")) and age is not None and age <= 15})
    return out


def _plan_ticker():
    while True:
        time.sleep(5)
        try:
            advance_plans(_instances_snapshot())
        except Exception as e:
            print(f"[panel] plan-ticker: {type(e).__name__}: {e}", flush=True)


def advance_plans(instances_data):
    """Zustandsmaschine, bei jedem Status-Abruf ausgefuehrt (idempotent).
    Uebergaenge nur bei frischem, warnungsfreiem Master-Status — ein
    eingefrorener Snapshot darf keinen Plan faelschlich beenden."""
    with PLANS_LOCK:
        plans = _load_plans()
        by_file = {d["file"]: d for d in instances_data}
        now = datetime.now().isoformat(timespec="seconds")
        changed = False
        for p in plans:
            d = by_file.get(p["file"])
            if not d or not d.get("alive") or (d.get("status") or {}).get("note"):
                continue
            pos = len((d.get("status") or {}).get("master_positions") or [])
            if p["status"] == "geplant" and pos > 0:
                p["status"] = "laufend"
                p["started_at"] = now
                changed = True
            elif p["status"] == "laufend" and pos == 0:
                p["status"] = "beendet"
                p["ended_at"] = now
                changed = True
        # Historie begrenzen: die letzten 50 beendeten reichen
        done = [p for p in plans if p["status"] == "beendet"]
        if len(done) > 50:
            drop = {p["id"] for p in done[:len(done) - 50]}
            plans = [p for p in plans if p["id"] not in drop]
            changed = True
        if changed:
            _save_plans(plans)
        return plans


# ── Provisionierung: "Account hinzufuegen" ─────────────────────────────────────
# Ein Job zur Zeit. Das Passwort liegt NUR im Speicher des Worker-Threads und in
# der transienten Startdatei, die provision.py garantiert loescht — im Job-Status
# (den der Browser pollt) taucht es nie auf.
PROV_STEPS = ("pruefen", "klonen", "login", "ea", "neustart", "config")
PROV_LOCK = threading.Lock()
PROV_JOB = None  # {"name", "steps": {key: {"state", "note"}}, "error", "done"}


def prov_start(name, login, password, server):
    global PROV_JOB
    with PROV_LOCK:
        if PROV_JOB and not PROV_JOB.get("done"):
            return False, "Es laeuft schon eine Provisionierung — erst fertig laufen lassen."
        cfg = read_json(os.path.join(HERE, "config.json"), {}) or {}
        template = cfg.get("master_terminal_path") or ""
        job = {"name": name, "error": None, "done": False,
               "steps": {k: {"state": "pending", "note": None} for k in PROV_STEPS}}
        PROV_JOB = job

    def report(step, state, note=None):
        st = job["steps"].get(step)
        if st:
            st["state"] = state
            if note:
                st["note"] = note

    def worker():
        try:
            provision.run_provision(name=name, login=login, password=password,
                                    server=server, template_exe=template,
                                    folder=HERE, report=report)
        except provision.ProvisionError as e:
            job["error"] = str(e)
            for st in job["steps"].values():
                if st["state"] == "running":
                    st["state"] = "error"
        except Exception as e:  # unerwartet — trotzdem lesbar anzeigen
            job["error"] = f"{type(e).__name__}: {e}"
            for st in job["steps"].values():
                if st["state"] == "running":
                    st["state"] = "error"
        finally:
            job["done"] = True

    threading.Thread(target=worker, daemon=True).start()
    return True, "gestartet"


# Laufende Heilungen pro Installation — verhindert, dass mehrfaches Klicken
# mehrere Kill/Restart-Zyklen uebereinanderlegt.
HEAL_ACTIVE = set()
HEAL_LOCK = threading.Lock()


def _heal_ea(fname, cfg, install_dir, started_ts, wait_s=45):
    """Hintergrund-Selbstheilung (15.08.2026): Nach einem Terminal-Start pruefen,
    ob der Snapshot wieder fliesst. Tut er es nicht, fehlt das Lese-EA auf dem
    Chart (passiert nach unsauberem Beenden — Chart-Stand verloren). Dann:
    Terminal beenden und mit [StartUp]-Startdatei neu starten, die das EA samt
    richtigem InpFileName automatisch aufzieht — derselbe Mechanismus wie bei
    der Provisionierung. Seit dem Abend auch fuer BEREITS LAUFENDE Terminals
    mit eingefrorenem Snapshot (Fund: Terminal lief noch vom vorigen Versuch,
    der Start-Knopf holte es nur nach vorn und uebersprang die Heilung — ein
    Terminal, das nichts liefert, ist zum Kopieren nutzlos, und die Positionen
    liegen beim Broker, ueberleben den Neustart also)."""
    with HEAL_LOCK:
        if install_dir in HEAL_ACTIVE:
            return
        HEAL_ACTIVE.add(install_dir)
    try:
        _heal_ea_inner(fname, cfg, install_dir, started_ts, wait_s)
    finally:
        with HEAL_LOCK:
            HEAL_ACTIVE.discard(install_dir)


def _heal_ea_inner(fname, cfg, install_dir, started_ts, wait_s):
    time.sleep(wait_s)
    snap = str(cfg.get("snapshot_file") or "prophos_master.csv")
    common = cfg.get("common_files_dir") or os.path.join(
        os.environ.get("APPDATA", ""), "MetaQuotes", "Terminal", "Common", "Files")
    snap_path = os.path.join(common, snap)
    try:
        if os.path.getmtime(snap_path) > started_ts:
            return  # Snapshot fliesst — EA war noch auf dem Chart, nichts zu tun
    except OSError:
        pass  # Datei fehlt ganz -> heilen
    data_dir = provision.data_dir_for(install_dir)
    if not data_dir:
        print(f"[panel] {fname}: Selbstheilung — Datenordner nicht gefunden.", flush=True)
        return
    ex5 = os.path.join(data_dir, "MQL5", "Experts", provision.EA_NAME + ".ex5")
    if not os.path.exists(ex5):
        print(f"[panel] {fname}: Selbstheilung — {provision.EA_NAME}.ex5 fehlt im "
              f"Datenordner, bitte einmal im Terminal kompilieren.", flush=True)
        return
    name = os.path.splitext(fname)[0].replace("config", "", 1).strip("-_") or "standard"
    preset = f"prophos-heal-{name}.set"
    os.makedirs(os.path.join(data_dir, "MQL5", "Presets"), exist_ok=True)
    with open(os.path.join(data_dir, "MQL5", "Presets", preset), "w",
              encoding=provision.SET_ENCODING) as f:
        f.write(provision.build_preset(snap))
    print(f"[panel] {fname}: Snapshot fliesst nicht — EA fehlt wohl. Starte Terminal "
          f"neu und ziehe {provision.EA_NAME} automatisch auf (InpFileName={snap}).", flush=True)
    for pid in provision.terminal_pids(install_dir):
        provision._taskkill(pid)
    ini = os.path.join(install_dir, "prophos-heal.ini")
    with open(ini, "w", encoding=provision.INI_ENCODING) as f:
        f.write(provision.build_startup_ini(preset=preset))
    try:
        subprocess.Popen([os.path.join(install_dir, "terminal64.exe"),
                          f"/config:{ini}"], cwd=install_dir)
    finally:
        # ini nach dem Start wegraeumen (ein weiterer Start damit haengte das EA
        # auf einen ZWEITEN Chart)
        time.sleep(30)
        try:
            os.remove(ini)
        except OSError:
            pass


def start_terminal(fname):
    """Startet das Master-Terminal der Instanz — oder holt das LAUFENDE Fenster
    nach vorn. Ein zweiter Start derselben Installation wuerde ein frisches
    Fenster ohne die laufende Sitzung oeffnen, das nach dem Login fragt
    (Fund 14.08.2026: genau daher kam der stoerende OK-Dialog). Pfad kommt
    AUSSCHLIESSLICH aus der Config (nicht ueber die API setzbar)."""
    cfg = read_json(os.path.join(HERE, fname), {}) or {}
    path = str(cfg.get("master_terminal_path") or "").strip()
    if not path:
        return False, "master_terminal_path ist in der Config nicht gesetzt"
    if os.path.basename(path).lower() != "terminal64.exe":
        return False, "master_terminal_path muss auf eine terminal64.exe zeigen"
    if not os.path.exists(path):
        return False, f"nicht gefunden: {path}"
    pids = provision.terminal_pids(os.path.dirname(path))
    if pids:
        # Laeuft schon: nur das Fenster nach vorn holen — ABER auch hier die
        # Selbstheilung anstossen: liefert das laufende Terminal keinen frischen
        # Snapshot (EA fehlt), wird es nach kurzer Pruefung neu gestartet und
        # das EA automatisch aufgezogen.
        try:
            subprocess.run(["powershell", "-Command",
                            f"(New-Object -ComObject WScript.Shell).AppActivate({pids[0]})"],
                           capture_output=True, timeout=15)
        except Exception:
            pass
        threading.Thread(target=_heal_ea,
                         args=(fname, cfg, os.path.dirname(os.path.abspath(path)),
                               time.time(), 8),
                         daemon=True).start()
        return True, "Terminal läuft — EA wird geprüft und notfalls automatisch aufgezogen"
    try:
        subprocess.Popen([path], cwd=os.path.dirname(path))
        # Selbstheilung im Hintergrund: fliesst der Snapshot in 45 s nicht,
        # wird das EA automatisch per [StartUp] nachgezogen.
        threading.Thread(target=_heal_ea,
                         args=(fname, cfg, os.path.dirname(os.path.abspath(path)), time.time()),
                         daemon=True).start()
        return True, "Terminal gestartet — Login automatisch; EA wird geprüft und notfalls selbst aufgezogen"
    except OSError as e:
        return False, f"Start fehlgeschlagen: {e}"


PAGE = r"""<!doctype html><html lang=de><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Copier-Panel</title><style>
/* Design-Tokens aus prophos.html uebernommen (14.08.2026) — gleiche Sprache wie Prophos */
:root{
  --violet:#5447CE;--violet-dark:#4539b8;--violet-tint:rgba(84,71,206,.08);
  --ink:#101828;--ink-2:#1D2939;--sub:#667085;--sub-2:#98A2B3;
  --border:#E5E7EB;--border-soft:#EEF2F6;--surface:#FFFFFF;--surface-tint:#F2F4F7;--bg:#FAFBFC;
  --good:#12B76A;--warn:#F79009;--danger:#F04438;
  --r-sm:8px;--r-md:12px;--r-lg:16px;
  --shadow-card:0 1px 2px rgba(16,24,40,.04);
  --shadow-card-hover:0 4px 12px rgba(16,24,40,.06);
  --shadow-input-focus:0 0 0 4px rgba(84,71,206,.12);
  --ease:cubic-bezier(.4,0,.2,1);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:'Inter','Segoe UI',system-ui,sans-serif;line-height:1.5;
  -webkit-font-smoothing:antialiased}
.mono{font-family:'JetBrains Mono','Consolas',monospace;font-variant-numeric:tabular-nums}
.tnum{font-variant-numeric:tabular-nums}
button{font-family:inherit;cursor:pointer}

/* Topbar */
.topbar{background:var(--surface);border-bottom:1px solid var(--border);
  padding:14px 28px;display:flex;align-items:center;gap:14px;position:sticky;top:0;z-index:20}
.topbar h1{font-size:16px;font-weight:600;margin:0;letter-spacing:-.01em}
.topbar .sub{font-size:12.5px;color:var(--sub)}
.copier-chip{margin-left:auto;display:inline-flex;align-items:center;gap:7px;
  font-size:12.5px;font-weight:500;color:var(--sub);
  background:var(--surface-tint);border:1px solid var(--border);border-radius:20px;padding:5px 12px}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.dot.on{background:var(--good);box-shadow:0 0 0 3px rgba(18,183,106,.15)}
.dot.off{background:var(--danger);box-shadow:0 0 0 3px rgba(240,68,56,.12)}

.wrap{max-width:1340px;margin:0 auto;padding:22px 28px 60px}
.view-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;gap:16px;flex-wrap:wrap}
.view-title{font-size:22px;font-weight:600;letter-spacing:-.02em;margin:0}
.view-sub{font-size:13.5px;color:var(--sub);margin:2px 0 0}

/* Buttons — wie Prophos */
.btn{display:inline-flex;align-items:center;gap:7px;padding:8px 14px;border-radius:8px;
  font-size:13px;font-weight:500;transition:all .15s var(--ease);border:1px solid transparent}
.btn-primary{background:var(--violet);color:#fff;
  box-shadow:0 1px 2px rgba(16,24,40,.06),0 2px 6px rgba(84,71,206,.22)}
.btn-primary:hover{background:var(--violet-dark);transform:translateY(-1px)}
.btn-primary:disabled{opacity:.55;transform:none;cursor:default}
.btn-ghost{background:var(--surface);border-color:var(--border);color:var(--ink)}
.btn-ghost:hover{background:var(--surface-tint)}
.btn-sm{padding:6px 11px;font-size:12px}

/* Banner */
.banner{background:rgba(240,68,56,.08);border:1px solid rgba(240,68,56,.35);color:#c03128;
  padding:11px 14px;border-radius:var(--r-md);font-size:13px;margin-bottom:14px;white-space:pre-line}
.jobbar{background:var(--violet-tint);border:1px solid rgba(84,71,206,.25);color:var(--violet-dark);
  padding:10px 14px;border-radius:var(--r-md);font-size:13px;margin-bottom:14px;cursor:pointer;
  display:flex;align-items:center;gap:10px}
.jobbar .spin{width:14px;height:14px;border:2.5px solid rgba(84,71,206,.25);border-top-color:var(--violet);
  border-radius:50%;animation:spin .7s linear infinite;flex-shrink:0}
.jobbar.err{background:rgba(240,68,56,.08);border-color:rgba(240,68,56,.35);color:#c03128}
@keyframes spin{to{transform:rotate(360deg)}}

/* Account-Grid */
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(330px,1fr))}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);
  padding:16px;box-shadow:var(--shadow-card);transition:box-shadow .15s var(--ease)}
.card:hover{box-shadow:var(--shadow-card-hover)}
.card.live-mode{border-color:rgba(240,68,56,.45)}
.acc-top{display:flex;align-items:center;gap:8px}
.acc-name{font-size:15px;font-weight:600;letter-spacing:-.01em}
.acc-state{margin-left:auto;font-size:12px;color:var(--sub);display:inline-flex;align-items:center;gap:6px}
.pill{font-size:10.5px;font-weight:600;letter-spacing:.04em;padding:2px 8px;border-radius:20px}
.pill.dry{background:var(--surface-tint);color:var(--sub);border:1px solid var(--border)}
.pill.demo{background:rgba(18,183,106,.12);color:#0d9668}
.pill.live{background:rgba(240,68,56,.12);color:#d92d20}
.acc-broker{font-size:12.5px;color:var(--sub);margin-top:3px}
.acc-broker b{color:var(--ink);font-weight:600}
.acc-route{font-size:12px;color:var(--sub-2);margin-top:1px}
.acc-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px}
.stat{background:var(--surface-tint);border-radius:var(--r-sm);padding:7px 4px;text-align:center}
.stat b{display:block;font-size:15px;font-weight:600;font-variant-numeric:tabular-nums}
.stat span{font-size:10.5px;color:var(--sub)}
.stat.hot b{color:var(--violet)}
.acc-acts{display:flex;gap:8px;margin-top:13px;align-items:center;flex-wrap:wrap}
.warnbox{background:rgba(247,144,9,.1);border:1px solid rgba(247,144,9,.35);color:#b45309;
  padding:8px 10px;border-radius:var(--r-sm);font-size:12px;margin-top:10px}

/* Details (aufklappbar) */
.details{display:none;border-top:1px solid var(--border-soft);margin-top:14px;padding-top:13px}
.card.open .details{display:block}
label{display:block;font-size:11px;font-weight:600;color:var(--sub);margin:10px 0 4px;
  text-transform:uppercase;letter-spacing:.05em}
input,select{width:100%;background:var(--surface);border:1px solid var(--border);color:var(--ink);
  border-radius:var(--r-sm);padding:8px 10px;font:13px inherit;font-family:inherit;
  transition:border-color .12s,box-shadow .12s}
input:focus,select:focus{outline:0;border-color:var(--violet);box-shadow:var(--shadow-input-focus)}
.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.map{display:grid;grid-template-columns:1fr auto 1fr auto;gap:6px;align-items:center;margin-top:5px}
.map span{color:var(--sub-2);font-size:12px}
.x{background:none;border:0;color:var(--sub-2);font-size:15px;padding:0 4px}
.x:hover{color:var(--danger)}
.msg{font-size:12px;font-family:'JetBrains Mono','Consolas',monospace;color:#058a50;min-height:16px;flex:1}
.msg.err{color:#c03128}
.dirty-hint{font-size:11px;color:#b45309;display:none}
.card[data-dirty] .dirty-hint{display:inline}
pre.log{background:var(--surface-tint);border:1px solid var(--border-soft);border-radius:var(--r-sm);
  padding:9px;margin:10px 0 0;font-size:11px;line-height:1.55;
  font-family:'JetBrains Mono','Consolas',monospace;
  max-height:150px;overflow:auto;color:var(--sub);white-space:pre-wrap}
.empty{color:var(--sub);padding:40px 20px;text-align:center}

/* Modals — wie Prophos */
.modal-bg{position:fixed;inset:0;background:rgba(16,24,40,.5);
  backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);
  display:none;align-items:center;justify-content:center;z-index:200;padding:20px}
.modal-bg.open{display:flex;animation:fadeIn .15s var(--ease)}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg);
  padding:24px 26px;width:100%;max-width:460px;max-height:90vh;overflow-y:auto;
  box-shadow:0 20px 60px -10px rgba(16,24,40,.25);animation:modalIn .2s var(--ease)}
@keyframes modalIn{from{opacity:0;transform:translateY(8px) scale(.98)}to{opacity:1;transform:none}}
.modal-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:2px}
.modal-head h3{margin:0;font-size:18px;font-weight:600;letter-spacing:-.01em}
.modal-x{width:32px;height:32px;padding:0;display:inline-flex;align-items:center;justify-content:center;
  background:transparent;border:1px solid transparent;border-radius:8px;color:var(--sub);font-size:16px}
.modal-x:hover{background:rgba(16,24,40,.06);color:var(--ink);border-color:var(--border)}
.modal-sub{font-size:13px;color:var(--sub);margin:0 0 16px}
.modal-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:20px;align-items:center}
.modal input.big{font-size:24px;font-weight:600;padding:10px 12px;text-align:center;
  font-variant-numeric:tabular-nums}
.rule{color:var(--sub-2);font-size:11.5px;margin-top:10px;line-height:1.45}

/* Provisionierungs-Schritte */
/* Trade-Plaene: drei Spalten geplant / laufend / beendet */
.plans-grid{display:grid;gap:14px;grid-template-columns:repeat(3,1fr);margin-top:14px}
@media (max-width:1000px){.plans-grid{grid-template-columns:1fr}}
.plan-col h4{margin:0 0 8px;font-size:12px;font-weight:600;color:var(--sub);
  text-transform:uppercase;letter-spacing:.06em;display:flex;align-items:center;gap:7px}
.plan-col h4 .cnt{background:var(--surface-tint);border:1px solid var(--border);
  border-radius:12px;padding:0 7px;font-size:11px;color:var(--sub)}
.plan{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-md);
  padding:11px 13px;box-shadow:var(--shadow-card);margin-bottom:10px;font-size:13px}
.plan.laufend{border-color:rgba(18,183,106,.45)}
.plan-top{display:flex;align-items:center;gap:8px}
.plan-top b{font-size:13.5px}
.plan-top .x{margin-left:auto}
.plan-meta{color:var(--sub);font-size:12px;margin-top:3px}
.plan-live{color:#0d9668;font-size:12px;margin-top:4px;font-variant-numeric:tabular-nums}
.plan-empty{color:var(--sub-2);font-size:12.5px;padding:12px 4px}
.steps{margin-top:14px;display:grid;gap:6px;font-size:13px}
.step{display:flex;gap:9px;align-items:baseline;color:var(--sub-2)}
.step .st{width:16px;text-align:center;flex-shrink:0;font-weight:700}
.step.done{color:#0d9668}.step.running{color:#b45309}.step.error{color:#c03128}
.step .note{color:var(--sub-2);font-size:11px}
</style></head><body>

<div class=topbar>
  <h1>Copier-Panel</h1>
  <span class=sub>lokal auf diesem PC · Prophos bleibt unangetastet</span>
  <span class=sub id=version-chip title="Version — aktualisiert sich selbst von GitHub"></span>
  <span class=copier-chip id=copier-chip><span class="dot off"></span>Copier</span>
</div>

<div class=wrap>
  <div class=view-head>
    <div>
      <h2 class=view-title>Accounts</h2>
      <p class=view-sub id=count-sub>–</p>
    </div>
    <button class="btn btn-primary" id=add-open>＋ Account hinzufügen</button>
  </div>
  <div id=notice></div>
  <div class=grid id=app><div class=empty>lade…</div></div>

  <div class=view-head style="margin-top:30px">
    <div>
      <h2 class=view-title style="font-size:19px">Trade-Pläne</h2>
      <p class=view-sub>geplant → laufend → beendet — wandert automatisch mit deinen Positionen</p>
    </div>
  </div>
  <div class=plans-grid id=plans></div>
</div>

<!-- Trade-Plan-Modal — dedizierte Verdrahtung (Projektregel: kein Sammel-Handler) -->
<div class=modal-bg id=plan-bg>
 <div class=modal>
  <div class=modal-head><h3 id=plan-title>Trade planen</h3>
    <button class=modal-x id=plan-x>✕</button></div>
  <p class=modal-sub id=plan-sub></p>
  <label>Multiplikator</label>
  <input class=big id=plan-mult type=number step=0.001 min=0>
  <div class=row style="margin-top:10px">
    <div><label>max Lots pro Hedge</label><input id=plan-lots type=number step=0.01 min=0></div>
    <div><label>Modus</label>
      <select id=plan-mode>
        <option value=dryrun>dryrun — nur mitlesen</option>
        <option value=demo>demo — echte Order, Demo-Konto</option>
        <option value=live>live — echtes Geld</option>
      </select></div>
  </div>
  <div class=rule>Regel: max Lots muss über Multiplikator × größter Master-Position bleiben, sonst verweigert die Sicherheitsgrenze die Order.</div>
  <div class=modal-actions>
    <span class=msg id=plan-msg></span>
    <button class="btn btn-ghost" id=plan-cancel>Abbrechen</button>
    <button class="btn btn-primary" id=plan-start>Trade starten</button>
  </div>
 </div>
</div>

<!-- Account-hinzufuegen-Modal — dedizierte Verdrahtung -->
<div class=modal-bg id=add-bg>
 <div class=modal>
  <div class=modal-head><h3>Account hinzufügen</h3>
    <button class=modal-x id=add-x>✕</button></div>
  <p class=modal-sub>klont das Master-Vorlage-Terminal, loggt ein, legt EA + Config an — alles automatisch</p>
  <div class=row>
    <div><label>Name (kurz, nur Buchstaben/Zahlen)</label><input data-p=name placeholder="z.B. ftmo1"></div>
    <div><label>Login (Kontonummer)</label><input data-p=login placeholder="z.B. 437899"></div>
  </div>
  <div class=row style="margin-top:2px">
    <div><label>Passwort (sichtbar — auf Wunsch)</label><input data-p=password autocomplete=off spellcheck=false></div>
    <div><label>Server</label><input data-p=server placeholder="z.B. FusionMarkets-Demo"></div>
  </div>
  <div id=add-steps></div>
  <div class=modal-actions>
    <span class=msg id=add-msg></span>
    <button class="btn btn-primary" id=add-start>Fertig — automatisch einrichten</button>
  </div>
 </div>
</div>

<script>
const state={}, openSet=new Set();
let lastJob=null;
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function pill(m){const c=m==='live'?'live':m==='demo'?'demo':'dry';return `<span class="pill ${c}">${esc((m||'?').toUpperCase())}</span>`}
function mapRows(map){
  const e=Object.entries(map);
  return e.map(([k,v])=>`<div class=map>
    <input value="${esc(k)}" data-mk placeholder="Master-Symbol">
    <span>→</span>
    <input value="${esc(v)}" data-mv placeholder="Hedge-Symbol">
    <button class=x data-del title="Zeile entfernen">×</button></div>`).join('')
   +`<div class=map><input data-mk placeholder="neues Master-Symbol">
     <span>→</span><input data-mv placeholder="Hedge-Symbol"><span></span></div>`;
}
function card(d){
  const s=d.status||{}, live=d.alive;
  const pos=(s.master_positions||[]).length, hed=Object.keys(s.hedges||{}).length;
  const broker=s.master_server||d.master_server||'Broker unbekannt';
  const isOpen=openSet.has(d.file);
  return `<div class="card${d.mode==='live'?' live-mode':''}${isOpen?' open':''}" data-file="${esc(d.file)}">
   <div class=acc-top><span class=acc-name>${esc(d.name)}</span>${pill(d.mode)}
     <span class=acc-state><span class="dot ${live?'on':'off'}"></span>${live?'läuft':'gestoppt'}</span></div>
   <div class=acc-broker><b>${esc(broker)}</b></div>
   <div class=acc-route><span class=mono>${esc(s.master_login||d.master_expected||'—')}</span> → Hedge <span class=mono>${esc(s.hedge_login||d.hedge_expected||'—')}</span></div>
   ${s.note?`<div class=warnbox>${esc(s.note)}</div>`:''}
   ${(s.blocked||[]).length?`<div class=warnbox>Gestoppt für Master-Pos: ${esc((s.blocked||[]).join(', '))} — im Hedge-Terminal prüfen</div>`:''}
   <div class=acc-stats>
     <div class="stat${pos?' hot':''}"><b>${pos}</b><span>Positionen</span></div>
     <div class="stat${hed?' hot':''}"><b>${hed}</b><span>Hedges</span></div>
     <div class=stat><b>×${esc(d.multiplier??'–')}</b><span>Multi</span></div>
     <div class=stat><b>${esc(d.max_lots??'–')}</b><span>max Lots</span></div>
   </div>
   <div class=acc-acts>
     <button class="btn btn-primary btn-sm" data-plan>Trade planen</button>
     <button class="btn btn-ghost btn-sm" data-toggle>${isOpen?'Details ▴':'Details ▾'}</button>
     <span class=dirty-hint>ungespeicherte Änderung</span>
     <span class=msg></span>
   </div>
   <div class=details>
     <div class=row>
       <div><label>Multiplikator</label><input type=number step=0.001 min=0 value="${esc(d.multiplier??'')}" data-f=multiplier></div>
       <div><label>max Lots pro Hedge</label><input type=number step=0.01 min=0 value="${esc(d.max_lots??'')}" data-f=max_lots_per_hedge></div>
     </div>
     <label>Modus</label>
     <select data-f=mode>
       <option value=dryrun ${d.mode==='dryrun'?'selected':''}>dryrun — nur mitlesen, keine Order</option>
       <option value=demo ${d.mode==='demo'?'selected':''}>demo — echte Order, nur Demo-Konto</option>
       <option value=live ${d.mode==='live'?'selected':''}>live — echtes Geld</option>
     </select>
     <label>Symbol-Mapping (Master → Hedge)</label>
     <div data-maps>${mapRows(d.symbol_map||{})}</div>
     <div class=acc-acts>
       <button class="btn btn-primary btn-sm" data-save>Speichern &amp; pushen</button>
       ${d.has_terminal?`<button class="btn btn-ghost btn-sm" data-term>Terminal öffnen</button>`:''}
     </div>
     <div style="font-size:11px;color:var(--sub-2);margin-top:8px">${esc(d.file)} · magic ${esc(d.magic)} · ${esc(d.snapshot_file||'')}</div>
     <pre class=log>${esc((s.log||[]).slice(-14).join('\n')||'noch keine Log-Zeilen')}</pre>
   </div>
  </div>`;
}
function jobSteps(job){
  const mark=s=>s.state==='done'?'✓':s.state==='running'?'…':s.state==='error'?'✗':'·';
  const labels={pruefen:'Prüfen & Kennwerte vergeben',klonen:'Terminal-Ordner klonen',
    login:'Erststart — Datenordner anlegen',
    ea:'Server-Liste + Lese-EA + Preset einlegen',
    neustart:'Start mit Login + EA (Zugangsdaten-Datei wird danach gelöscht)',config:'Config anlegen'};
  let h=`<div class=steps>${job.steps.map(s=>`<div class="step ${s.state}"><span class=st>${mark(s)}</span><span>${labels[s.key]||s.key}${s.note?` <span class=note>${esc(s.note)}</span>`:''}</span></div>`).join('')}`;
  if(job.error)h+=`<div class="step error" style="margin-top:6px"><span class=st>✗</span><span>${esc(job.error)}</span></div>`;
  else if(job.done)h+=`<div class="step done"><span class=st>✓</span><span>fertig — Karte „${esc(job.name)}" erscheint gleich (dryrun)</span></div>`;
  return h+'</div>';
}
async function load(){
  const r=await fetch('/api/instances'); const d=await r.json();
  lastJob=d.job;
  const app=document.getElementById('app');
  d.instances.forEach(x=>state[x.file]=x);
  // Kopf: Copier-Status + Zaehler
  const anyAlive=d.instances.some(x=>x.alive);
  document.getElementById('copier-chip').innerHTML=`<span class="dot ${anyAlive?'on':'off'}"></span>Copier ${anyAlive?'läuft':'gestoppt'}`;
  document.getElementById('version-chip').textContent=d.version?('v'+d.version):'';
  const brokers=new Set(d.instances.map(x=>(x.status||{}).master_server||x.master_server).filter(Boolean));
  document.getElementById('count-sub').textContent=`${d.instances.length} Accounts · ${brokers.size} Broker · ein Copier-Prozess`;
  // Hinweise: Konflikte + laufende Provisionierung
  let n='';
  if(d.conflicts.length)n+=`<div class=banner>⛔ ${d.conflicts.map(esc).join('\n⛔ ')}</div>`;
  if(d.job&&!d.job.done&&document.getElementById('add-bg').style.display!=='flex'){
    const cur=d.job.steps.find(s=>s.state==='running');
    n+=`<div class=jobbar id=jobbar><span class=spin></span>Account „${esc(d.job.name)}" wird eingerichtet — ${esc(cur?cur.key:'…')} … (klicken für Details)</div>`;
  }else if(d.job&&d.job.done&&d.job.error&&document.getElementById('add-bg').style.display!=='flex'){
    n+=`<div class="jobbar err" id=jobbar>✗ Account „${esc(d.job.name)}": ${esc(d.job.error.slice(0,140))}… (klicken für Details)</div>`;
  }
  document.getElementById('notice').innerHTML=n;
  const jb=document.getElementById('jobbar'); if(jb)jb.addEventListener('click',openAdd);
  // Karten
  if(!d.instances.length){app.innerHTML='<div class=empty>Keine Accounts. Oben rechts „＋ Account hinzufügen".</div>';}
  else{
    const empty=app.querySelector('.empty'); if(empty)empty.remove();
    const files=new Set(d.instances.map(x=>x.file));
    app.querySelectorAll('.card').forEach(c=>{if(!files.has(c.getAttribute('data-file')))c.remove()});
    for(const x of d.instances){
      const cur=app.querySelector(`.card[data-file="${CSS.escape(x.file)}"]`);
      // Karten mit ungespeicherten Eingaben oder Fokus NICHT überschreiben (3s-Reload)
      if(cur&&(cur.hasAttribute('data-dirty')||cur.contains(document.activeElement)))continue;
      const html=card(x);
      if(cur)cur.outerHTML=html; else app.insertAdjacentHTML('beforeend',html);
    }
  }
  // Trade-Plaene rendern (keine Eingabefelder darin -> immer neu zeichnen ok)
  renderPlans(d.plans||[]);
  // Add-Modal-Schritte live aktualisieren, wenn offen
  if(document.getElementById('add-bg').classList.contains('open'))renderAddJob();
}
function fmtT(iso){if(!iso)return'';const d=new Date(iso);return d.toLocaleDateString('de-DE',{day:'2-digit',month:'2-digit'})+' '+d.toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'})}
function dur(a,b){if(!a||!b)return'';const m=Math.round((new Date(b)-new Date(a))/60000);return m<60?`${m} min`:`${Math.floor(m/60)} h ${m%60} min`}
function planCard(p){
  const d=state[p.file]||{}, s=d.status||{};
  const pos=(s.master_positions||[]).length, hed=Object.keys(s.hedges||{}).length;
  let meta='', live='';
  if(p.status==='geplant')meta=`geplant ${fmtT(p.armed_at||p.created_at)}`;
  if(p.status==='laufend'){meta=`läuft seit ${fmtT(p.started_at)}`;
    live=`<div class=plan-live>● ${pos} Position(en) · ${hed} Hedge(s) bewacht</div>`}
  if(p.status==='beendet')meta=`${fmtT(p.started_at)} → ${fmtT(p.ended_at)} · ${dur(p.started_at,p.ended_at)}`;
  return `<div class="plan ${p.status}">
    <div class=plan-top><b>${esc(d.name||p.name)}</b>${pill(p.mode)}
      <button class=x data-plandel="${p.id}" data-planstatus="${p.status}" title="Plan löschen">×</button></div>
    <div class=plan-meta>×${esc(p.multiplier)} · max ${esc(p.max_lots)} Lots · ${esc((s.master_server||d.master_server||''))}</div>
    <div class=plan-meta>${esc(meta)}</div>
    ${live}
  </div>`;
}
function renderPlans(plans){
  const cols=[['geplant','Geplant'],['laufend','Laufend'],['beendet','Beendet']];
  document.getElementById('plans').innerHTML=cols.map(([k,label])=>{
    let list=plans.filter(p=>p.status===k);
    if(k==='beendet')list=list.slice().reverse();
    return `<div class=plan-col><h4>${label}<span class=cnt>${list.length}</span></h4>
      ${list.map(planCard).join('')||`<div class=plan-empty>${k==='geplant'?'Kein Plan — „Trade planen" auf einer Karte.':k==='laufend'?'Nichts im Markt.':'Noch keine abgeschlossenen Trades.'}</div>`}
    </div>`;
  }).join('');
}
document.getElementById('plans').addEventListener('click',async e=>{
  const pid=e.target.getAttribute&&e.target.getAttribute('data-plandel');
  if(!pid)return;
  if(e.target.getAttribute('data-planstatus')==='laufend'&&!confirm('Dieser Plan LÄUFT gerade (Position offen). Wirklich nur den Plan-Eintrag löschen? Die Position und der Hedge bleiben unberührt.'))return;
  await fetch('/api/plan-delete?id='+encodeURIComponent(pid),{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  load();
});
document.getElementById('app').addEventListener('input',e=>{
  const c=e.target.closest('.card'); if(c)c.setAttribute('data-dirty','1');
});
document.getElementById('app').addEventListener('change',e=>{
  const c=e.target.closest('.card'); if(c)c.setAttribute('data-dirty','1');
});

// ── Trade-Plan-Modal ────────────────────────────────────────────────────────
const planBg=document.getElementById('plan-bg');
function openPlan(file){
  const d=state[file]; if(!d)return;
  planBg.dataset.file=file;
  const s=d.status||{};
  document.getElementById('plan-title').textContent='Trade planen — '+d.name;
  document.getElementById('plan-sub').textContent=`${s.master_server||d.master_server||''} · Master ${d.master_expected||'—'} → Hedge ${d.hedge_expected||'—'}`;
  document.getElementById('plan-mult').value=d.multiplier??'';
  document.getElementById('plan-lots').value=d.max_lots??'';
  document.getElementById('plan-mode').value=d.mode||'dryrun';
  const m=document.getElementById('plan-msg'); m.className='msg'; m.textContent='';
  planBg.classList.add('open'); planBg.style.display='flex';
  document.getElementById('plan-mult').focus();
}
function closePlan(){planBg.classList.remove('open');planBg.style.display='none'}
document.getElementById('plan-cancel').addEventListener('click',closePlan);
document.getElementById('plan-x').addEventListener('click',closePlan);
document.getElementById('plan-start').addEventListener('click',async()=>{
  const file=planBg.dataset.file, d=state[file]||{};
  const msg=document.getElementById('plan-msg');
  // Haerteste Falle zuerst: ohne laufenden Copier wird NICHTS gehedgt.
  if(!d.alive){
    if(!confirm(`Der Copier ist GESTOPPT — deine Trades würden NICHT gehedgt!\n\nErst start-copier.bat starten, dann hier erneut auf „Trade starten".\n\nTrotzdem fortfahren (nur Werte pushen + Terminal öffnen)?`)){
      msg.className='msg err';msg.textContent='Abgebrochen — erst den Copier starten.';return}
  }
  // Liefert der Master gerade nichts (Terminal zu / EA fehlt), ist das KEIN
  // Abbruchgrund mehr: Terminal-Start + EA-Selbstheilung erledigen das, und
  // die Bereitschafts-Anzeige unten sagt, wann wirklich getradet werden darf.
  const patch={multiplier:document.getElementById('plan-mult').value,
               max_lots_per_hedge:document.getElementById('plan-lots').value,
               mode:document.getElementById('plan-mode').value};
  if(!patch.multiplier||!patch.max_lots_per_hedge){
    msg.className='msg err';msg.textContent='Multiplikator und max Lots ausfüllen.';return}
  if(+patch.max_lots_per_hedge<=+patch.multiplier){
    if(!confirm(`max Lots (${patch.max_lots_per_hedge}) ist nicht größer als der Multiplikator (${patch.multiplier}).\nSchon ab 1.0 Lot Master würde die Sicherheitsgrenze die Order verweigern.\nTrotzdem so starten?`))return;
  }
  if(patch.mode==='live'&&d.mode!=='live'){
    if(!confirm(`LIVE schalten — echtes Geld!\n\nDatei: ${file}\nMaster: ${d.master_expected||'?'}\nHedge: ${d.hedge_expected||'?'}\n\nDuplikum für dieses Paar ist aus?`)){
      msg.className='msg err';msg.textContent='Abgebrochen — nichts geändert';return}
  }
  msg.className='msg';msg.textContent='pushe…';
  const r=await fetch('/api/save?file='+encodeURIComponent(file),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(patch)});
  const s=await r.json();
  if(!s.ok){msg.className='msg err';msg.textContent='Fehler: '+s.msg;return}
  // Trade-Plan anlegen/aktualisieren: startet als "geplant" und wandert von
  // selbst nach "laufend"/"beendet", sobald die Position auf-/zugeht.
  try{await fetch('/api/plan?file='+encodeURIComponent(file),{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({multiplier:patch.multiplier,max_lots:patch.max_lots_per_hedge,mode:patch.mode})});}catch(e){}
  msg.textContent='gepusht — öffne Terminal…';
  const t=await fetch('/api/start-terminal?file='+encodeURIComponent(file),{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  const ts=await t.json();
  if(!ts.ok){msg.className='msg err';msg.textContent='Multiplikator gepusht, aber Terminal: '+ts.msg;return}
  // Bereitschafts-Ueberwachung: der Dialog bleibt offen und meldet live, wann
  // der Snapshot wirklich fliesst — erst DANN traden. Die EA-Selbstheilung im
  // Hintergrund braucht im Reparaturfall bis ~1,5 Minuten.
  const t0=Date.now();
  msg.className='msg';msg.textContent=`⏳ ×${patch.multiplier} gepusht · Terminal startet, Login automatisch…`;
  const timer=setInterval(async()=>{
    let inst=null;
    try{const rr=await fetch('/api/instances');const dd=await rr.json();inst=dd.instances.find(x=>x.file===file);}catch(e){}
    const sec=Math.round((Date.now()-t0)/1000);
    if(inst&&inst.alive&&!(inst.status||{}).note){
      clearInterval(timer);
      msg.className='msg';
      msg.textContent=`✓ Bereit — ×${patch.multiplier} aktiv, Hedge bewacht. Jetzt im Terminal traden.`;
      setTimeout(load,1000);
      return;
    }
    if(sec>170){
      clearInterval(timer);
      msg.className='msg err';
      msg.textContent='Terminal liefert nach 3 Minuten nichts — Details-Log der Karte prüfen.';
      return;
    }
    msg.textContent=sec>50
      ?`⏳ EA wird geprüft und notfalls automatisch aufgezogen… (${sec}s)`
      :`⏳ Terminal startet, Login automatisch… (${sec}s)`;
  },3000);
});

// ── Account-hinzufuegen-Modal ───────────────────────────────────────────────
const addBg=document.getElementById('add-bg');
function renderAddJob(){
  document.getElementById('add-steps').innerHTML=lastJob?jobSteps(lastJob):'';
  const busy=lastJob&&!lastJob.done;
  document.getElementById('add-start').disabled=!!busy;
  addBg.querySelectorAll('[data-p]').forEach(i=>i.disabled=!!busy);
}
function openAdd(){addBg.classList.add('open');addBg.style.display='flex';renderAddJob()}
function closeAdd(){addBg.classList.remove('open');addBg.style.display='none';load()}
document.getElementById('add-open').addEventListener('click',openAdd);
document.getElementById('add-x').addEventListener('click',closeAdd);
document.getElementById('add-start').addEventListener('click',async()=>{
  const get=k=>(addBg.querySelector(`[data-p=${k}]`)||{}).value?.trim()||'';
  const body={name:get('name'),login:get('login'),password:(addBg.querySelector('[data-p=password]')||{}).value||'',server:get('server')};
  const msg=document.getElementById('add-msg');
  if(!body.name||!body.login||!body.password||!body.server){
    msg.className='msg err';msg.textContent='Alle vier Felder ausfüllen.';return}
  if(!/^[A-Za-z0-9]{1,24}$/.test(body.name)){
    msg.className='msg err';msg.textContent='Name: nur Buchstaben/Zahlen, ohne Leer-/Bindezeichen.';return}
  msg.className='msg';msg.textContent='starte…';
  const r=await fetch('/api/provision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  const pw=addBg.querySelector('[data-p=password]'); if(pw)pw.value='';
  msg.className='msg'+(d.ok?'':' err');
  msg.textContent=d.ok?'läuft — Fortschritt unten':('Fehler: '+d.msg);
  if(d.ok)setTimeout(load,1000);
});

// ── Karten-Aktionen (delegiert) ─────────────────────────────────────────────
document.getElementById('app').addEventListener('click',async e=>{
  const cardEl=e.target.closest('.card'); if(!cardEl)return;
  const file=cardEl.getAttribute('data-file');
  const msg=cardEl.querySelector('.msg');
  if(e.target.hasAttribute('data-plan')){openPlan(file);return}
  if(e.target.hasAttribute('data-toggle')){
    if(openSet.has(file))openSet.delete(file); else openSet.add(file);
    cardEl.classList.toggle('open');
    e.target.textContent=cardEl.classList.contains('open')?'Details ▴':'Details ▾';
    return;
  }
  if(e.target.hasAttribute('data-del')){
    e.target.closest('.map').remove();
    cardEl.setAttribute('data-dirty','1');
    return;
  }
  if(e.target.hasAttribute('data-term')){
    msg.className='msg'; msg.textContent='öffne Terminal…';
    const r=await fetch('/api/start-terminal?file='+encodeURIComponent(file),{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const d=await r.json();
    msg.className='msg'+(d.ok?'':' err'); msg.textContent=d.ok?d.msg:('Fehler: '+d.msg);
    return;
  }
  if(!e.target.hasAttribute('data-save'))return;
  const patch={};
  cardEl.querySelectorAll('[data-f]').forEach(el=>patch[el.getAttribute('data-f')]=el.value);
  const map={}; let bad=null, dup=null;
  cardEl.querySelectorAll('[data-maps] .map').forEach(row=>{
    const a=(row.querySelector('[data-mk]')||{}).value?.trim()||'';
    const b=(row.querySelector('[data-mv]')||{}).value?.trim()||'';
    if(!a&&!b)return;
    if(!a||!b){bad=a||b;return}
    if(map[a]!==undefined)dup=a;
    map[a]=b;
  });
  if(bad){msg.className='msg err';msg.textContent=`Mapping-Zeile '${bad}' ist nur halb ausgefüllt`;return}
  if(dup){msg.className='msg err';msg.textContent=`Master-Symbol '${dup}' doppelt im Mapping`;return}
  patch.symbol_map=map;
  if(patch.mode==='live'&&state[file]?.mode!=='live'){
    const s=state[file]||{};
    if(!confirm(`LIVE schalten — echtes Geld!\n\nDatei: ${file}\nMaster: ${s.master_expected||'?'}\nHedge: ${s.hedge_expected||'?'}\n\nDuplikum für dieses Paar ist aus?`)){
      msg.className='msg err';msg.textContent='Abgebrochen — Modus nicht geändert';return}
  }
  msg.className='msg';msg.textContent='speichere…';
  const r=await fetch('/api/save?file='+encodeURIComponent(file),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(patch)});
  const d=await r.json();
  msg.className='msg'+(d.ok?'':' err');
  msg.textContent=d.ok?(d.msg+' — der Copier übernimmt es in ~2s'+(d.restart?' (Neustart läuft automatisch)':'')):('Fehler: '+d.msg);
  if(d.ok)cardEl.removeAttribute('data-dirty');
  setTimeout(load,2500);
});
load(); setInterval(load,3000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _local_ok(self):
        """Host/Origin auf 127.0.0.1|localhost festnageln — schuetzt gegen
        DNS-Rebinding und Requests fremder Seiten aus dem Browser heraus."""
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        if host not in ("127.0.0.1", "localhost"):
            return False
        origin = self.headers.get("Origin")
        if origin:
            o = urlparse(origin)
            if (o.hostname or "").lower() not in ("127.0.0.1", "localhost"):
                return False
        return True

    def do_GET(self):
        if not self._local_ok():
            return self._send(403, json.dumps({"error": "nur lokal"}))
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if path == "/api/instances":
            return self._send(200, json.dumps(snapshot(), ensure_ascii=False))
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if not self._local_ok():
            return self._send(403, json.dumps({"ok": False, "msg": "nur lokal"}))
        u = urlparse(self.path)
        ctype = (self.headers.get("Content-Type") or "")
        if "application/json" not in ctype:
            return self._send(400, json.dumps({"ok": False, "msg": "Content-Type muss application/json sein"}))
        if u.path == "/api/provision":
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
            name = str(body.get("name") or "").strip()
            login = str(body.get("login") or "").strip()
            password = str(body.get("password") or "")
            server = str(body.get("server") or "").strip()
            if not (name and login and password and server):
                return self._send(400, json.dumps({"ok": False, "msg": "Name, Login, Passwort und Server sind Pflicht."}))
            probs = provision.plan_checks(HERE, name, login, server,
                                          (read_json(os.path.join(HERE, "config.json"), {}) or {}).get("master_terminal_path"))
            if probs:
                return self._send(400, json.dumps({"ok": False, "msg": " · ".join(probs)}, ensure_ascii=False))
            ok, msg = prov_start(name, login, password, server)
            print(f"[panel] provision '{name}': {msg}", flush=True)  # bewusst ohne Zugangsdaten
            return self._send(200 if ok else 409, json.dumps({"ok": ok, "msg": msg}, ensure_ascii=False))

        if u.path == "/api/plan-delete":
            # braucht keinen file-Parameter — Plan-ID reicht
            try:
                pid = int((parse_qs(u.query).get("id") or ["0"])[0])
            except ValueError:
                pid = 0
            ok = delete_plan(pid)
            return self._send(200, json.dumps({"ok": ok, "msg": "geloescht" if ok else "unbekannt"}))

        fname = (parse_qs(u.query).get("file") or [""])[0]
        inst = next((i for i in instances() if i["config_file"] == fname), None)
        if not inst:
            return self._send(404, json.dumps({"ok": False, "msg": f"Instanz '{fname}' unbekannt"}))

        if u.path == "/api/start-terminal":
            ok, msg = start_terminal(inst["config_file"])
            print(f"[panel] {fname}: Terminal-Start → {msg}", flush=True)
            return self._send(200, json.dumps({"ok": ok, "msg": msg}, ensure_ascii=False))

        if u.path == "/api/plan":
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
            p = upsert_plan(inst["config_file"], inst["name"],
                            body.get("multiplier"), body.get("max_lots"),
                            str(body.get("mode") or ""))
            return self._send(200, json.dumps({"ok": True, "plan": p}, ensure_ascii=False))


        if u.path != "/api/save":
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            n = int(self.headers.get("Content-Length") or 0)
            patch = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._send(400, json.dumps({"ok": False, "msg": f"ungueltige Daten: {e}"}))
        before = read_json(os.path.join(HERE, inst["config_file"]), {}) or {}
        ok, msg = patch_config(inst["config_file"], patch)
        restart = ok and str(patch.get("mode", "")).lower() not in ("", str(before.get("mode", "")).lower())
        print(f"[panel] {fname}: {msg}", flush=True)
        self._send(200, json.dumps({"ok": ok, "msg": msg, "restart": restart}, ensure_ascii=False))

    def log_message(self, *a):
        pass  # eigenes, ruhigeres Logging oben


# ── Selbst-Update wie im Copier (15.08.2026): neue VERSION auf GitHub → Neustart
# durch die start-panel.bat-Schleife. Das Panel ist zustandslos (Configs liegen
# atomar auf Platte) — einzige Ruecksicht: nie mitten in einer Provisionierung.
UPDATE_URL = ("https://raw.githubusercontent.com/finntraidingview-cmd/Prophos/"
              "main/mt5-copier/VERSION")


def _local_version():
    try:
        with open(os.path.join(HERE, "VERSION"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def _version_watcher(my_version):
    import urllib.request
    while True:
        time.sleep(60)
        try:
            with urllib.request.urlopen(UPDATE_URL, timeout=10) as r:
                remote = r.read().decode("utf-8", "replace").strip()
        except Exception:
            continue
        if remote and remote != my_version:
            if PROV_JOB and not PROV_JOB.get("done"):
                continue  # nie mitten in einer Provisionierung
            print(f"[panel] Update {my_version} → {remote} — Neustart durch start-panel.bat.", flush=True)
            os._exit(0)


def main():
    print("=" * 66)
    print(" Prophos Copier-Panel")
    print(f" Ordner: {HERE}")
    print(f" Master: {', '.join(i['config_file'] for i in instances()) or '(keine config*.json gefunden)'}")
    ignored = [fn for fn in sorted(os.listdir(HERE))
               if fn.endswith(".json") and fn.lower().startswith("config")
               and fn not in TEMPLATES and not CONFIG_RE.fullmatch(fn)]
    if ignored:
        print(f" IGNORIERT (kein gueltiger Config-Name): {', '.join(ignored)}")
    print(f" Im Browser oeffnen:  http://127.0.0.1:{PORT}")
    print(" Nur lokal erreichbar. Prophos wird nicht angefasst.")
    v = _local_version()
    if v:
        print(f" Version {v} · Selbst-Update aktiv")
        threading.Thread(target=_version_watcher, args=(v,), daemon=True).start()
    # Plan-Zustandsmaschine unabhaengig vom Browser treiben (Review 15.08.2026):
    # advance_plans lief bisher nur bei GET /api/instances — sobald aber die
    # Prophos-View nicht offen ist, pollt niemand, und geplant→laufend→beendet
    # bliebe stehen (falsche/fehlende Zeitstempel). Ein Daemon-Tick alle 5 s
    # macht die Uebergaenge unabhaengig davon, ob ein Browser zuschaut.
    threading.Thread(target=_plan_ticker, daemon=True).start()
    print("=" * 66)
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nPanel beendet.")
    except OSError as e:
        sys.exit(f"Port {PORT} belegt oder blockiert: {e}")


if __name__ == "__main__":
    main()
