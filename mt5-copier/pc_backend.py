#!/usr/bin/env python3
"""Prophos Mini-Backend für PCs (PS1, 25.11.2026, Finn: „Das Wissen darf nicht auf dem PC liegen").

Anlass: Auf jedem PC lief bisher die komplette app.py (58.000 Zeilen, mit Auto-Planer, Firmenregeln, Payout- und
Konsistenz-Logik) als lokales Backend auf localhost:5000 — und lag damit lesbar auf der Platte fremder Leute (erster
Fall: Aarons Laptop, 25.11.2026). Der PC braucht davon nur fünf Dinge. Genau die stehen hier, 1:1 aus app.py
übernommen (gleiche Riegel, gleiche Zeitlimits), alles andere reicht diese Datei unverändert an Railway durch:

  /                      Oberfläche, mit dem PC-Schlüssel von Railway geholt (nur im Arbeitsspeicher, nie auf Platte)
  /mt5-copier/VERSION    Stand für den Neulade-Wächter des Tabs
  /sw.js                 Service Worker (muss vom selben Ursprung kommen wie die Seite)
  /copier/<pfad>         Brücke zum Panel auf diesem PC (127.0.0.1:8770)
  /local/restart-stack   Knopf „Alles schließen & neu starten"
  alles andere           → Railway (derselbe Pfad, dieselbe Methode, derselbe Inhalt)

Diese Datei RECHNET und ENTSCHEIDET nichts über Trades. Ein Fehler hier heißt „Auftrag kommt nicht an", nie „falscher
Auftrag". Sie läuft nur auf PCs, die auf Railway in MINI_BACKEND_PCS stehen (start-prophos-mini.bat); alle anderen PCs
starten weiter app.py wie bisher.
"""
import os
import random
import re
import sys
import threading
import time

import requests
from flask import Flask, Response, jsonify, request

app = Flask(__name__)

HIER = os.path.dirname(os.path.abspath(__file__))
CODE_QUELLE = "https://web-production-bec81.up.railway.app"      # Railway: Code-Auslieferung und Ziel des Durchreichens
COPIER_PANEL = "http://127.0.0.1:8770"
LOKALE_AUFRUFER = ("127.0.0.1", "::1", "::ffff:127.0.0.1")
EIGENE_DATEI = "mt5-copier/pc_backend.py"                         # Pfad dieser Datei im Repo (für den Update-Vergleich)


# ── PC-Schlüssel (code_token.txt neben dieser Datei, legt der Prophos-Tab über das Panel ab) ──
def _code_token_lokal():
    try:
        with open(os.path.join(HIER, "code_token.txt"), "r", encoding="utf-8") as f:
            return f.read().strip()[:200] or None
    except OSError:
        return None


def _code_holen(pfad_url, timeout=10):
    """GET CODE_QUELLE + pfad_url mit X-Code-Token → Antwort (nur 200) oder None."""
    tok = _code_token_lokal()
    if not tok:
        return None
    try:
        r = requests.get(CODE_QUELLE + pfad_url, headers={"X-Code-Token": tok}, timeout=timeout)
        return r if r.status_code == 200 else None
    except Exception:
        return None


@app.after_request
def cors(r):
    # wie app.py: sb-token, PATCH/DELETE — sonst scheitert schon der Preflight („Failed to fetch")
    r.headers["Access-Control-Allow-Origin"] = "*"
    r.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, ma-token, ma-account, dup-token, dup-user, sb-token"
    r.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
    return r


# ── Oberfläche ──
# Die Seite kommt mit dem PC-Schlüssel von Railway und bleibt im Arbeitsspeicher. Anders als app.py gibt es KEINE lokale
# prophos.html als Reserve (die soll gerade nicht auf der Platte liegen). Ist Railway kurz weg (Deploy ~1 min), liefert
# die letzte gute Fassung aus dem Speicher; gab es noch keine, eine kleine Warteseite, die sich alle 10 s neu lädt.
_seite = {"html": None}
WARTESEITE = ('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="10"><title>Prophos</title>'
              '<body style="font-family:system-ui;background:#0b0f14;color:#cbd5e1;display:grid;place-items:center;height:100vh;margin:0">'
              '<div style="text-align:center"><div style="font-size:18px">Prophos lädt …</div>'
              '<div style="font-size:13px;opacity:.7;margin-top:8px">%s<br>Die Seite versucht es alle 10 Sekunden von selbst.</div></div>')


def seite_gueltig(inhalt):
    """REIN RECHNEND (testbar): ist das die echte Oberfläche? Gleiche Probe wie app.py (Größe + OS_TAB_BUILD)."""
    return isinstance(inhalt, (bytes, bytearray)) and len(inhalt) > 50000 and b"OS_TAB_BUILD" in inhalt


@app.route("/")
def index():
    r0 = _code_holen("/code/datei/prophos.html", timeout=15)
    if r0 is not None and seite_gueltig(r0.content):
        _seite["html"] = r0.content
        return Response(r0.content, mimetype="text/html")
    if _seite["html"]:
        print("[frontend] Railway lieferte die Seite nicht — nutze die letzte Fassung aus dem Speicher", flush=True)
        return Response(_seite["html"], mimetype="text/html")
    grund = ("Noch kein PC-Schlüssel (code_token.txt) — er kommt nach dem ersten Login von selbst."
             if not _code_token_lokal() else "Der Server ist gerade nicht erreichbar.")
    return Response(WARTESEITE % grund, mimetype="text/html", headers={"Cache-Control": "no-store"})


# ── Frontend-Version für den Build-Wächter (wie app.py: 30 s gecacht, Format JJJJ-MM-TT.N) ──
_frontend_ver = {"at": 0.0, "wert": None}
_FRONTEND_VER_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.\d+$")


@app.route("/mt5-copier/VERSION", methods=["GET"])
def frontend_version():
    now = time.time()
    if _frontend_ver["wert"] and now - _frontend_ver["at"] < 30:
        wert = _frontend_ver["wert"]
    else:
        wert = None
        r0 = _code_holen("/code/stand")
        try:
            v0 = str(((r0.json() or {}).get("version") if r0 is not None else "") or "").strip()
            if _FRONTEND_VER_RE.match(v0):
                wert = v0
        except Exception:
            pass
        if not wert:
            try:      # Reserve: die VERSION-Datei, die der Copier-Starter neben diese Datei legt
                with open(os.path.join(HIER, "VERSION"), "r", encoding="utf-8") as f:
                    t = f.read().strip()
                wert = t if _FRONTEND_VER_RE.match(t) else None
            except Exception:
                wert = None
        if wert:
            _frontend_ver.update(at=now, wert=wert)
    if not wert:
        return Response("", status=404, mimetype="text/plain")
    resp = Response(wert, mimetype="text/plain")
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/sw.js", methods=["GET"])
def push_service_worker():
    r0 = _code_holen("/code/datei/sw.js")
    if r0 is not None and r0.text.strip():
        return r0.text, 200, {"Content-Type": "application/javascript", "Cache-Control": "no-store"}
    return "// sw.js nicht erreichbar — Benachrichtigungen aus\n", 200, {"Content-Type": "application/javascript"}


# ── Panel-Brücke (1:1 aus app.py copier_proxy, Stand 25.11.2026) ──
# UPDATE-SCHUTZ (29.10.2026): jeder Aufruf zählt mit; der Update-Wächter unten startet nur bei 0 neu und schließt die
# Brücke vorher (neue Aufrufe bekommen 503 „nichts gesendet" statt mitten im Lauf abzureißen → kein „Ergebnis UNKLAR").
_PROXY = {"n": 0, "zu": False}
_PROXY_LOCK = threading.Lock()
# Zeitlimits je Pfad — der äußere Abbruch darf nie vor dem Bot kommen (Doppel-Order-Pfad, Vorfälle 15.08./28.08./30.09.2026)
_COPIER_LANG = ("master-order", "master-close", "tv-order", "tv-lesen", "tv-close",
                "tsx-konto", "tsx-lesen", "tsx-inventar", "tsx-close", "tv-konten-liste")


def copier_zeitlimit(path):
    """REIN RECHNEND (testbar): Sekunden, die die Brücke auf das Panel wartet — dieselbe Tabelle wie app.py."""
    return (310 if path in _COPIER_LANG
            else 270 if path == "tv-konto" else 40 if path == "hedge-solo" else 100 if path == "tv-neuladen"
            else 160 if path == "tv-tm-update" else 50 if path == "vorflug" else 25)


@app.route("/copier/<path:path>", methods=["GET", "POST", "OPTIONS"])
def copier_proxy(path):
    if request.method == "OPTIONS":
        return "", 200
    # Nur der PC selbst darf das Panel schalten (kein LAN-Gerät); Browser-Origin wird durchgereicht, damit die
    # Origin-Prüfung des Panels greift.
    if request.remote_addr not in LOKALE_AUFRUFER:
        return jsonify({"ok": False, "copier_offline": True,
                        "error": "Copier ist nur lokal auf dem PC selbst erreichbar."}), 403
    with _PROXY_LOCK:
        if _PROXY["zu"]:
            return jsonify({"ok": False, "copier_offline": True, "_httpFail": True, "code": "backend_neustart", "retry_ok": True,
                            "_nichtGesendet": True,
                            "error": "Prophos-Backend startet gerade neu (Update) — nichts gesendet, gleich erneut."}), 503
        _PROXY["n"] += 1
    try:
        return _copier_proxy_lauf(path)
    finally:
        with _PROXY_LOCK:
            _PROXY["n"] -= 1


def _copier_proxy_lauf(path):
    h = {"Content-Type": "application/json"}
    origin = request.headers.get("Origin")
    if origin:
        h["Origin"] = origin
    if path == "hedge-solo":      # HEDGE-ZU-7S (02.11.2026): nur Messung, das Panel gibt den Stempel zurück
        h["X-Prophos-Proxy-Ms"] = str(round(time.time() * 1000))
    try:
        r = requests.request(
            request.method, f"{COPIER_PANEL}/api/{path}",
            params=request.args,
            json=request.get_json(silent=True) if request.method == "POST" else None,
            headers=h, timeout=copier_zeitlimit(path))
        return Response(r.content, status=r.status_code, content_type="application/json")
    except Exception as e:
        return jsonify({"ok": False, "copier_offline": True,
                        "error": f"Copier-Panel auf diesem PC nicht erreichbar ({type(e).__name__})"}), 502


# ── Stack-Neustart per Knopf (aus app.py local_restart_stack; der GitHub-Rückfall ist weg — Repo seit 07.10. privat) ──
@app.route("/local/restart-stack", methods=["POST", "OPTIONS"])
def local_restart_stack():
    if request.method == "OPTIONS":
        return "", 200
    if request.remote_addr not in LOKALE_AUFRUFER:
        return jsonify({"ok": False, "msg": "Nur lokal auf dem PC selbst erlaubt."}), 403
    if os.name != "nt":
        return jsonify({"ok": False, "msg": "Nur auf dem Windows-PC verfuegbar."}), 403
    bat = (os.environ.get("PROPHOS_STACK_BAT") or r"C:\mt5-copier\start-alles.bat").strip()
    if not os.path.exists(bat):
        return jsonify({"ok": False, "msg": f"start-alles.bat nicht gefunden: {bat}"})
    if "'" in bat:
        return jsonify({"ok": False, "msg": "Pfad mit ' wird nicht unterstuetzt: " + bat})
    import subprocess
    import tempfile
    helper = os.path.join(tempfile.gettempdir(), "prophos-restart-stack.ps1")
    skript = f"""# Von Prophos erzeugt — Knopf "Alles schliessen & neu starten".
$ErrorActionPreference = 'SilentlyContinue'
$ProgressPreference = 'SilentlyContinue'
# Antwort ans Frontend rausgehen lassen, bevor das Backend stirbt.
Start-Sleep -Seconds 2
# 1) ALLE Konsolenfenster zuerst (die Starter sind Neustart-Schleifen), 2) danach die Prozesse selbst.
Get-Process cmd | Stop-Process -Force
Get-Process python, pythonw | Stop-Process -Force
Start-Sleep -Seconds 2
# 3) start-alles.bat frisch holen (eine LAUFENDE Batchdatei darf man nicht ueberschreiben — hier ist sie sicher zu).
$bat = '{bat}'
$tok = ''
try {{ $tok = (Get-Content (Join-Path (Split-Path -Parent $bat) 'code_token.txt') -TotalCount 1 -ErrorAction Stop).Trim() }} catch {{ }}
if ($tok) {{ try {{ Invoke-WebRequest '{CODE_QUELLE}/code/datei/mt5-copier/start-alles.bat' -Headers @{{'X-Code-Token'=$tok}} -OutFile "$bat.newh" -TimeoutSec 20 -UseBasicParsing }} catch {{ }} }}
if (Test-Path "$bat.newh") {{
  if ((Get-Item "$bat.newh").Length -ge 700) {{ Move-Item -Force "$bat.newh" $bat }}
  else {{ Remove-Item -Force "$bat.newh" }}
}}
# 4) Frisch hochfahren.
Start-Process -FilePath $bat -WorkingDirectory (Split-Path -Parent $bat)
"""
    with open(helper, "w", encoding="utf-8-sig") as f:      # mit BOM: PowerShell 5.1 liest sonst ANSI
        f.write(skript)
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", helper],
                     creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, close_fds=True, cwd=os.path.dirname(bat))
    print("[stack] Neustart angestossen — ALLE Konsolen werden geschlossen, dieses Backend wird mitgekillt.", flush=True)
    return jsonify({"ok": True, "msg": "Alle Konsolen werden geschlossen, Stack startet neu."})


# ── Alles andere → Railway ──
# Der Tab ruft am PC ein paar Routen über localhost auf (TS_BACKEND/PUSH_BACKEND/ADVISOR_BASE in prophos.html:
# /api/* TopstepX, /ma/*, /news/*, /push/*, /duplikum/*, /mirror/*, /advisor/*). Auf Railway läuft dieselbe app.py —
# von pages.dev aus gehen genau diese Aufrufe heute schon dorthin. Hier wird nichts ausgewertet, nur weitergereicht.
_NICHT_WEITER = {"host", "content-length", "connection", "keep-alive", "transfer-encoding", "upgrade", "te", "trailer",
                 "proxy-authorization", "proxy-authenticate", "accept-encoding"}
_NICHT_ZURUECK = {"content-encoding", "content-length", "transfer-encoding", "connection", "keep-alive",
                  "access-control-allow-origin", "access-control-allow-headers", "access-control-allow-methods"}


def weiter_kopf(kopf):
    """REIN RECHNEND (testbar): Anfrage-Kopfzeilen, die an Railway mitgehen (ohne Host/Länge/Verbindungs-Zeilen)."""
    return {k: v for k, v in kopf if k.lower() not in _NICHT_WEITER}


def zurueck_kopf(kopf):
    """REIN RECHNEND (testbar): Antwort-Kopfzeilen von Railway für den Browser (requests hat schon entpackt; CORS setzt cors())."""
    return [(k, v) for k, v in kopf if k.lower() not in _NICHT_ZURUECK]


def nicht_durchreichen(methode, pfad):
    """REIN RECHNEND (testbar): Aufrufe, die NICHT nach Railway dürfen. Einziger Fall: die alte Mirror-Engine starten
    (POST /mirror/start). In app.py lief sie im lokalen Prozess mit Wiederaufnahme-Datei (~/.prophos/mirror-sessions.json);
    durchgereicht liefe sie auf Railway — und nach dem Not-Schalter nähme das alte Backend dasselbe Pair lokal wieder auf:
    zwei Engines, doppelte Hedge-Orders (Prüfer 25.11.2026). Deshalb hier hart Nein statt weiterreichen."""
    return str(methode).upper() == "POST" and str(pfad).strip("/").lower() == "mirror/start"


@app.route("/<path:pfad>", methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"])
def weiterreichen(pfad):
    if request.method == "OPTIONS":
        return "", 200
    if request.remote_addr not in LOKALE_AUFRUFER:      # kein offenes Relais für das LAN
        return jsonify({"ok": False, "error": "Nur lokal auf dem PC selbst erreichbar."}), 403
    if nicht_durchreichen(request.method, pfad):
        return jsonify({"ok": False, "success": False, "code": "mini_backend",
                        "error": "Der Topstep-Spiegel (alte Mirror-Engine) läuft auf diesem PC nicht — nichts gestartet."}), 409
    try:
        r = requests.request(request.method, f"{CODE_QUELLE}/{pfad}", params=request.args,
                             data=request.get_data(), headers=weiter_kopf(request.headers.items()),
                             timeout=(10, 120), allow_redirects=False)
    except (requests.exceptions.ConnectionError, requests.exceptions.ConnectTimeout) as e:
        # keine Verbindung zustande gekommen → beweisbar nichts gesendet
        return jsonify({"ok": False, "success": False, "_nichtGesendet": True,
                        "error": f"Server nicht erreichbar — nichts gesendet ({type(e).__name__})"}), 502
    except Exception as e:
        # Verbindung stand, Antwort blieb aus (z. B. Deploy mitten im Aufruf) → der Server KANN es verarbeitet haben
        return jsonify({"ok": False, "success": False, "unklar": True,
                        "error": f"Antwort des Servers blieb aus — Ergebnis unklar ({type(e).__name__})"}), 504
    return Response(r.content, status=r.status_code, headers=zurueck_kopf(r.headers.items()))


# ── Selbst-Update (aus app.py _local_version_watcher, Stand 25.11.2026) ──
# Damit ein Update wirkt, muss dieser Prozess von selbst enden; start-prophos-mini.bat holt dann die neue Datei und
# startet neu. Auslöser wie überall: mt5-copier/VERSION. Neu gestartet wird nur, wenn sich DIESE Datei geändert hat
# (23.09.2026: sonst war localhost:5000 bei jedem Frontend-Push kurz weg) — oder wenn Railway diesen PC wieder auf das
# alte Backend stellt (Not-Schalter: PC aus MINI_BACKEND_PCS nehmen).
LOCAL_UPDATE_DECKEL_S = 15 * 60
LOCAL_UPDATE_LEERLAUF_S = 320.0   # Brücke zu, laufende Aufrufe höchstens so lange zu Ende laufen lassen (Maximum 310 s)


def _local_fetch_version():
    r = _code_holen("/code/datei/mt5-copier/VERSION")
    return r.text.strip() if r is not None and r.text.strip() else None


def _local_repo_sha():
    r = _code_holen("/code/stand")
    try:
        sha = (r.json() or {}).get("sha") if r is not None else None
        return sha if sha and re.fullmatch(r"[0-9a-f]{40}", sha) else None
    except Exception:
        return None


def code_gleich(neu, alt):
    """REIN RECHNEND (testbar): gleicher Code trotz Zeilenenden/BOM?"""
    glatt = lambda b: b.replace(b"\r\n", b"\n").lstrip(b"\xef\xbb\xbf").strip()
    return glatt(neu) == glatt(alt)


def _local_code_geaendert():
    """Würde ein Neustart den LAUFENDEN Code ändern? True auch bei Unsicherheit (kein Netz) — dann Neustart wie bisher."""
    sha = _local_repo_sha()
    if not sha:
        return True
    try:
        r = _code_holen(f"/code/datei/{EIGENE_DATEI}?sha={sha}")
        if r is None or len(r.content) < 3000:
            return True
        with open(os.path.abspath(__file__), "rb") as f:
            return not code_gleich(r.content, f.read())
    except Exception:
        return True


def _local_backend_wahl():
    """Railway fragen, welches Backend dieser PC fahren soll → 'mini' | 'alt' | None (unklar/kein Netz = nichts ändern)."""
    r = _code_holen("/code/backend-wahl", timeout=8)
    try:
        w = str((r.json() or {}).get("backend") or "") if r is not None else ""
        return w if w in ("mini", "alt") else None
    except Exception:
        return None


def local_update_entscheiden(proxy_n, panel_gruende, wartet_seit, jetzt, streu_bis, deckel_s=LOCAL_UPDATE_DECKEL_S):
    """REIN RECHNEND (testbar): darf das lokale Backend jetzt für ein Update neu starten? -> ('warten' | 'jetzt' | 'erzwingen', grund).
    panel_gruende: Liste aus GET /api/beschaeftigt ([] = frei); None = Panel nicht erreichbar/ohne Route (dann zählt nur die Brücke)."""
    if jetzt < streu_bis:
        return "warten", f"Streuung noch {int(streu_bis - jetzt)} s"
    gruende = ([f"{proxy_n} laufende(r) Copier-Aufruf(e)"] if proxy_n > 0 else []) + list(panel_gruende or [])
    if not gruende:
        return "jetzt", ""
    if wartet_seit is not None and jetzt - wartet_seit >= deckel_s:
        return "erzwingen", f"seit {int((jetzt - wartet_seit) // 60)} min belegt: " + ", ".join(gruende)[:200]
    return "warten", "belegt: " + ", ".join(gruende)[:200]


def _local_panel_gruende():
    """GET /api/beschaeftigt des Panels → Gründe gegen einen Neustart ([] = frei). None = Panel aus oder alt (404).
    Zeitüberschreitung/andere Antwort = unklar → belegt (Prüfer 29.10.2026)."""
    try:
        r = requests.get(f"{COPIER_PANEL}/api/beschaeftigt", timeout=5)
    except requests.exceptions.ConnectionError:
        return None
    except Exception as e:
        return [f"Panel antwortet nicht eindeutig ({type(e).__name__})"]
    if r.status_code == 404:
        return None
    try:
        d = r.json() if r.status_code == 200 else None
    except ValueError:
        d = None
    if not isinstance(d, dict):
        return [f"Panel antwortet nicht eindeutig (HTTP {r.status_code})"]
    lauf = d.get("lauf") if isinstance(d.get("lauf"), list) else (d.get("gruende") or [])
    return [str(x)[:80] for x in lauf]


def _local_update_spur(von, auf, grund, wartete_s):
    """Erzwungener Neustart → Railway POST /pc/update-spur (⚪ an die Master-IDs). Wirft nie."""
    tok = _code_token_lokal()
    if not tok:
        return
    pc = ""
    try:
        r = requests.get(f"{COPIER_PANEL}/api/pc-id", timeout=3)
        pc = str((r.json() or {}).get("pc_id") or "") if r.ok else ""
    except Exception:
        pass
    try:
        requests.post(CODE_QUELLE + "/pc/update-spur", headers={"X-Code-Token": tok}, timeout=5,
                      json={"pc": pc, "wer": "backend", "von": str(von)[:30], "auf": str(auf)[:30], "grund": str(grund)[:240],
                            "wartete_s": int(wartete_s or 0)})
    except Exception as e:
        print(f"[update] Spur nicht gemeldet ({type(e).__name__})")


def _local_version_watcher():
    # Boot-Baseline EINMAL holen. Schlägt das fehl (kein Netz/kein Schlüssel beim Start), alle 60 s erneut versuchen —
    # anders als app.py bleibt der Wächter nicht für immer aus: ohne ihn käme der Not-Schalter nie an.
    baseline = _local_fetch_version()
    while baseline is None:
        time.sleep(60)
        baseline = _local_fetch_version()
    upd = {"auf": None, "seit": None, "streu_bis": 0.0, "gemeldet": "", "kurz": False, "code": {}}
    while True:
        time.sleep(random.uniform(5, 10) if upd["kurz"] else 60)      # Jitter-Regel: wartet ein Update, öfter schauen
        upd["kurz"] = False
        zurueck = _local_backend_wahl() == "alt"      # Not-Schalter: nur eine KLARE Antwort „alt" zählt
        rv = _local_fetch_version()
        if not zurueck:
            if rv is None or rv == baseline:
                upd.update(auf=None, seit=None)
                continue
            if rv not in upd["code"]:                 # je Stand nur EINMAL die Datei von Railway holen
                upd["code"] = {rv: _local_code_geaendert()}
            if not upd["code"][rv]:
                print(f"[update] {baseline} → {rv}: pc_backend.py unveraendert — kein Neustart noetig.", flush=True)
                baseline = rv
                upd.update(auf=None, seit=None)
                continue
        ziel = "altes Backend (Not-Schalter)" if zurueck else rv
        # UPDATE-SCHUTZ (29.10.2026): gestreut 0–60 s, dann nur ohne laufenden /copier-Aufruf und mit freiem Panel;
        # belegt → vertagen, nach LOCAL_UPDATE_DECKEL_S trotzdem (Spur + ⚪ über Railway /pc/update-spur)
        if upd["seit"] is None:
            upd.update(seit=time.time(), streu_bis=time.time() + random.uniform(0, 60.0), gemeldet="")
        upd["auf"] = ziel
        entsch, grund = local_update_entscheiden(_PROXY["n"], _local_panel_gruende(), upd["seit"], time.time(), upd["streu_bis"])
        if entsch == "warten":
            if grund != upd["gemeldet"] and not grund.startswith("Streuung"):
                print(f"[update] ↻ {baseline} → {ziel} wartet — {grund}", flush=True)
            upd.update(gemeldet=grund, kurz=True)
            continue
        with _PROXY_LOCK:
            _PROXY["zu"] = True                       # ab hier keine neuen Aufrufe mehr (503 „nichts gesendet")
            noch = _PROXY["n"]
        if noch and entsch != "erzwingen":            # in der Lücke kam einer rein → wieder auf, warten
            with _PROXY_LOCK:
                _PROXY["zu"] = False
            upd["kurz"] = True
            continue
        try:
            if entsch == "erzwingen":
                ende = time.time() + LOCAL_UPDATE_LEERLAUF_S
                while _PROXY["n"] > 0 and time.time() < ende:
                    time.sleep(0.5)
                print(f"[update] ↻ {baseline} → {ziel}: Deckel {LOCAL_UPDATE_DECKEL_S // 60} min — Neustart ({grund})", flush=True)
                if _PROXY["n"] > 0:
                    _local_update_spur(baseline, ziel, f"{_PROXY['n']} Copier-Aufruf(e) noch offen nach {int(LOCAL_UPDATE_LEERLAUF_S)} s",
                                       time.time() - upd["seit"])
            print(f"[update] ↻ {baseline} → {ziel} — beende Prozess (der Starter holt die neuen Dateien und startet neu).", flush=True)
        finally:
            os._exit(0)                               # nie mit geschlossener Brücke weiterleben (Prüfer 29.10.2026)


def _local_port_taken(port):
    # Doppelstart-Schutz: lauscht schon jemand auf dem Port, sauber melden statt Flask sterben zu lassen
    import socket
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=1)
        s.close()
        return True
    except OSError:
        return False


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    if _local_port_taken(port):
        print("=" * 70)
        print(f"Port {port} belegt — läuft schon ein Prophos-Backend? Dieses Fenster versucht es in 10 s erneut.")
        print("=" * 70)
        sys.exit(1)
    threading.Thread(target=_local_version_watcher, daemon=True).start()
    print(f"[mini] Prophos Mini-Backend auf Port {port} — Oberfläche und alles Weitere kommen von {CODE_QUELLE}", flush=True)
    app.run(host="0.0.0.0", port=port)
