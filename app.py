import requests
import urllib3
import threading
import calendar
import concurrent.futures
import base64
import json
import hashlib
import hmac
import time
import uuid
import logging
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from flask import Flask, request, jsonify, Response, send_from_directory
import os
from signalrcore.hub_connection_builder import HubConnectionBuilder

# ── signalrcore-Hotfixes (21.07.2026, beide im Live-Test nachgewiesen) ──
# 1. CloseMessage hat kein __str__ — die Library loggt "Close message received from
#    server <object at 0x…>" und versteckt damit ausgerechnet die Server-Begründung
#    fürs Trennen. Mit __str__-Patch steht der Grund im Log.
# 2. WebsocketTransport definiert connection_alive nie (nur SSE/LongPolling-Transports
#    tun das) — schlägt ein Reconnect-Versuch fehl (z.B. HTTP 429), crasht
#    deferred_reconnect() mit AttributeError und die Reconnect-Maschinerie stirbt
#    still: Verbindung wirkt verbunden, ist aber tot, on_close feuert nie.
try:
    from signalrcore.messages.close_message import CloseMessage as _SrCloseMessage
    _SrCloseMessage.__str__ = lambda self: "CloseMessage(error={0}, allow_reconnect={1})".format(
        getattr(self, "error", None), getattr(self, "allow_reconnect", None))
    _SrCloseMessage.__repr__ = _SrCloseMessage.__str__
    from signalrcore.transport.websockets.websocket_transport import WebsocketTransport as _SrWsTransport
    if not hasattr(_SrWsTransport, "connection_alive"):
        _SrWsTransport.connection_alive = False
except Exception:
    pass

app = Flask(__name__)

# Bei jedem Deploy-relevanten app.py-Change hochzählen — /version macht endlich
# VERIFIZIERBAR, welcher Stand auf Railway wirklich läuft (ein HTTP 200 auf
# irgendeinen Endpoint beweist gar nichts, Lesson vom 21.07.2026).
APP_BUILD = "2026-08-16.5"

@app.route("/version", methods=["GET"])
def version():
    return jsonify({
        "build": APP_BUILD,
        "commit": (os.environ.get("RAILWAY_GIT_COMMIT_SHA") or "")[:12]
    })

# ── Forex-Factory News-Kalender (öffentlicher Wochen-Feed, gecacht) ──
# FF hat keine offizielle API, aber einen öffentlichen JSON-Feed pro Woche.
# Wir proxien + cachen serverseitig (30 min), damit der Browser weder CORS noch
# Rate-Limit trifft. Nur USD-Events werden durchgereicht.
_news_cache = {"ts": 0, "data": None}
_news_lock = threading.Lock()
NEWS_TTL = 30 * 60
FF_URLS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
]

@app.route("/news/calendar", methods=["GET", "OPTIONS"])
def news_calendar():
    if request.method == "OPTIONS":
        return "", 200
    now = time.time()
    with _news_lock:
        if _news_cache["data"] is not None and (now - _news_cache["ts"]) < NEWS_TTL:
            return jsonify(_news_cache["data"])
    events = []
    try:
        for url in FF_URLS:
            r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0 (Prophos)"})
            if r.status_code != 200:
                continue
            for ev in (r.json() or []):
                if str(ev.get("country") or "").upper() != "USD":
                    continue
                events.append({
                    "id": ev.get("id") or (str(ev.get("title")) + str(ev.get("date"))),
                    "title": ev.get("title"),
                    "country": ev.get("country"),
                    "date": ev.get("date"),
                    "impact": ev.get("impact"),
                    "forecast": ev.get("forecast"),
                    "previous": ev.get("previous"),
                })
    except Exception as e:
        with _news_lock:
            if _news_cache["data"] is not None:
                return jsonify(_news_cache["data"])  # stale liefern statt Fehler
        return jsonify({"error": str(e), "events": []}), 502
    payload = {"events": events, "fetched": now}
    with _news_lock:
        _news_cache["data"] = payload
        _news_cache["ts"] = now
    return jsonify(payload)

TSX_BASE = "https://api.topstepx.com"
RTC_BASE = "https://rtc.topstepx.com"   # ProjectX Gateway Real-Time Hub (SignalR)
MA_BASE  = "https://mt-client-api-v1.london.agiliumtrade.ai"
DUP_BASE = "https://www.trade-copier.com/webservice/v4"

# Token Refresh Interval (TSX Tokens leben 24h, wir refreshen alle 20min proaktiv)
TOKEN_REFRESH_INTERVAL = 20 * 60  # 20 Minuten

# Duplikium tokens leben 48h — wir refreshen alle 40h proaktiv
DUP_REFRESH_INTERVAL = 40 * 60 * 60  # 40 Stunden

# Dauerhafte Duplikum-Credentials via Railway Env-Vars.
# Damit überlebt die Verbindung Restarts/Redeploys/mehrere Gunicorn-Worker:
# jeder Worker kann jederzeit selbstständig einen frischen Token holen,
# ohne dass im Frontend neu verbunden werden muss.
DUP_EMAIL    = (os.environ.get("DUP_EMAIL") or "").strip()
DUP_PASSWORD = os.environ.get("DUP_PASSWORD") or ""

# Active mirror sessions: pair_id -> session data
mirror_sessions = {}
# Echtzeit-Modus: SignalR-Hub-Objekte pro pair_id, damit /mirror/stop die Verbindung
# SOFORT trennen kann statt nur "active":False zu setzen und auf die nächste Loop-
# Iteration zu warten (bis zu 8s Fenster, in dem die alte Verbindung noch weiter
# mitgespiegelt hätte — echter Bug, hat zu doppelten Hedge-Orders geführt, 21.07.2026).
mirror_hubs = {}

# Duplikium credential cache (in-memory): user_email -> {token, password, last_refresh}
# Hinweis: Passwort wird nur in Memory gehalten, NICHT auf Disk geschrieben.
duplikum_sessions = {}

# ── Kurz-Cache + Single-Flight für Duplikum-LESE-Endpoints (22.07.2026) ──
# Problem: wenn mehrere Leute/Tabs gleichzeitig traden, pollen sie dieselben Lese-
# Endpoints (offene Positionen etc.) im Sekundentakt → Duplikums 20-Calls/min-Limit
# reißt, Calls hängen bis zum Timeout (Response-Time-Spikes bis 20s bei idle-CPU,
# per Railway-Metrics bestätigt). Fix: (1) identische, gleichzeitige Anfragen werden
# zusammengefasst (Single-Flight — nur EIN Upstream-Call, alle warten auf dasselbe
# Ergebnis); (2) das Ergebnis wird ~3s gecacht, sodass Folge-Polls sofort bedient
# werden ohne Duplikum überhaupt anzufassen. NUR Lese-Endpoints; Mutationen
# (setSettings/addAccount/deleteAccount/mapping) laufen IMMER direkt durch.
DUP_CACHEABLE = {
    "position/getopenpositions.php",
    "account/getaccounts.php",
    "position/getclosedpositions.php",
}
DUP_CACHE_TTL = 3.0   # Sekunden
_dup_cache = {}                      # key -> (expires_ts, status, content_bytes, content_type)
_dup_cache_lock = threading.Lock()   # schützt _dup_cache + _dup_inflight
_dup_inflight = {}                   # key -> threading.Lock (Single-Flight pro Key)

def flatten_php_form(data, parent_key=""):
    """Konvertiert nested dict/list zu PHP-Bracket-Form für x-www-form-urlencoded.

    Beispiel: {'settings': [{'id_slave': '29524'}]}
    →        [('settings[0][id_slave]', '29524')]

    Wird von Duplikium V4 verlangt für Endpoints die Arrays nehmen (z.B. setSettings.php).
    Flache Dicts ohne Nesting bleiben unverändert (Backwards-Compat zu getAccounts etc.).
    """
    items = []
    if isinstance(data, dict):
        for k, v in data.items():
            new_key = f"{parent_key}[{k}]" if parent_key else str(k)
            if isinstance(v, (dict, list)):
                items.extend(flatten_php_form(v, new_key))
            elif v is None:
                items.append((new_key, ""))
            elif isinstance(v, bool):
                items.append((new_key, "1" if v else "0"))
            else:
                items.append((new_key, str(v)))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            new_key = f"{parent_key}[{i}]"
            if isinstance(v, (dict, list)):
                items.extend(flatten_php_form(v, new_key))
            elif v is None:
                items.append((new_key, ""))
            elif isinstance(v, bool):
                items.append((new_key, "1" if v else "0"))
            else:
                items.append((new_key, str(v)))
    return items

@app.after_request
def cors(r):
    r.headers["Access-Control-Allow-Origin"] = "*"
    # sb-token gehört dazu, sonst blockt der Browser den Admin-Endpoint schon im
    # Preflight ("Failed to fetch", 15.08.2026 live aufgetreten).
    r.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, ma-token, ma-account, dup-token, dup-user, sb-token"
    r.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return r

@app.route("/")
def index():
    # Optional (nur für lokale PC-Installationen): Frontend LIVE von einer URL holen,
    # damit prophos.html auf den PCs nie veraltet — Updates laufen dann weiter normal
    # über GitHub/Cloudflare, ohne dass auf jedem PC etwas nachgezogen werden muss.
    # Aktivierung per Env-Var PROPHOS_FRONTEND (setzt start-local-backend.bat).
    # Ohne die Var bleibt das Verhalten unverändert (Railway ist damit nicht betroffen).
    # Bei jedem Fehler/Timeout: Fallback auf die lokale Datei, damit der PC offline
    # weiterarbeiten kann.
    remote = (os.environ.get("PROPHOS_FRONTEND") or "").strip()
    if remote:
        try:
            r = requests.get(remote, timeout=10)
            if r.ok and len(r.content) > 50000:
                return Response(r.content, mimetype="text/html")
            print(f"[frontend] Remote lieferte HTTP {r.status_code} / {len(r.content)} Bytes — nutze lokale Datei")
        except Exception as e:
            print(f"[frontend] Remote-Fetch fehlgeschlagen ({type(e).__name__}) — nutze lokale Datei")
    # Serve prophos.html if present, otherwise fall back to old index.html
    if os.path.exists("prophos.html"):
        return send_from_directory(".", "prophos.html")
    return send_from_directory(".", "index.html")

# ── TopstepX Proxy ──
@app.route("/api/<path:path>", methods=["GET","POST","OPTIONS"])
def tsx_proxy(path):
    if request.method == "OPTIONS": return "", 200
    h = {"Content-Type": "application/json"}
    t = request.headers.get("Authorization", "")
    if t: h["Authorization"] = t
    try:
        r = requests.request(request.method, f"{TSX_BASE}/api/{path}",
            json=request.get_json(silent=True), headers=h, timeout=10)
        return Response(r.content, status=r.status_code, content_type="application/json")
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

# ── MetaApi Proxy ──
@app.route("/ma/<path:path>", methods=["GET","POST","OPTIONS"])
def ma_proxy(path):
    if request.method == "OPTIONS": return "", 200
    token      = request.headers.get("ma-token", "")
    account_id = request.headers.get("ma-account", "")
    h = {"Content-Type": "application/json", "auth-token": token}
    if account_id and path == "account":
        url = f"{MA_BASE}/users/current/accounts/{account_id}/account-information"
    elif account_id:
        url = f"{MA_BASE}/users/current/accounts/{account_id}/{path}"
    else:
        url = f"{MA_BASE}/users/current/{path}"
    try:
        r = requests.request(request.method, url,
            json=request.get_json(silent=True), headers=h, timeout=15, verify=False)
        return Response(r.content, status=r.status_code, content_type="application/json")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── MT5-Copier Panel-Proxy (Etappe 3, 15.08.2026) ──
# prophos.html erreicht darueber die Panel-API des eigenen Hedge-Copier-Stacks
# auf DIESEM PC (127.0.0.1:8770, siehe mt5-copier/panel.py). Bewusst nur
# localhost: der Copier ist eine Pro-PC-Angelegenheit — auf Railway existiert
# kein Panel, dort antwortet die Route sauber mit 502 und das Frontend zeigt
# "nur am lokalen PC verfuegbar". Die Duplikium-Logik bleibt komplett
# unberuehrt; das hier ist die parallele Schnittstelle zum eigenen Copier.
COPIER_PANEL = "http://127.0.0.1:8770"

@app.route("/copier/<path:path>", methods=["GET","POST","OPTIONS"])
def copier_proxy(path):
    if request.method == "OPTIONS": return "", 200
    # SICHERHEIT (Review 15.08.2026): Das Panel schuetzt sich selbst nur, solange
    # es direkt angesprochen wird — es bindet an 127.0.0.1 und prueft Host+Origin.
    # Dieser Proxy darf diese Grenze NICHT aufweichen. Zwei Riegel:
    #  1) Nur lokale Aufrufer. app.py lauscht auf 0.0.0.0 (Railway/LAN), aber der
    #     Copier ist eine reine Loopback-Sache. Ein LAN-Geraet (fremde remote_addr)
    #     darf hier nichts schalten — sonst koennte es Accounts auf 'live' setzen.
    #  2) Browser-Origin durchreichen, damit die Origin-Pruefung des Panels wieder
    #     greift (schuetzt gegen Drive-by-POSTs fremder Seiten trotz CORS '*').
    if request.remote_addr not in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
        return jsonify({"ok": False, "copier_offline": True,
                        "error": "Copier ist nur lokal auf dem PC selbst erreichbar."}), 403
    h = {"Content-Type": "application/json"}
    origin = request.headers.get("Origin")
    if origin: h["Origin"] = origin
    try:
        r = requests.request(
            request.method, f"{COPIER_PANEL}/api/{path}",
            params=request.args,
            json=request.get_json(silent=True) if request.method == "POST" else None,
            headers=h, timeout=25)
        return Response(r.content, status=r.status_code, content_type="application/json")
    except Exception as e:
        return jsonify({"ok": False, "copier_offline": True,
                        "error": f"Copier-Panel auf diesem PC nicht erreichbar ({type(e).__name__})"}), 502

# ── Stack-Neustart per Knopf (15.08.2026, Finns Wunsch) ──
# Das Hand-Ritual — CMD-Fenster zu, taskkill python, start-alles.bat — als EIN
# Klick im MT5-Tab. Killt bewusst auch DIESES Backend; die .bat startet alles
# frisch, laufende Instanzen schuetzen sich selbst (Copier-Status-Sperre,
# Panel/Backend-Port-Probe). Nur Lokal-Modus + nur Loopback (gleiche Riegel
# wie der Copier-Proxy — ein LAN-Geraet darf den Stack nicht neu starten).
@app.route("/local/restart-stack", methods=["POST", "OPTIONS"])
def local_restart_stack():
    if request.method == "OPTIONS":
        return "", 200
    if request.remote_addr not in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
        return jsonify({"ok": False, "msg": "Nur lokal auf dem PC selbst erlaubt."}), 403
    if os.name != "nt" or not (os.environ.get("PROPHOS_FRONTEND") or "").strip():
        return jsonify({"ok": False, "msg": "Nur im Lokal-Modus (PROPHOS_FRONTEND) verfuegbar."}), 403
    bat = (os.environ.get("PROPHOS_STACK_BAT") or r"C:\mt5-copier\start-alles.bat").strip()
    if not os.path.exists(bat):
        return jsonify({"ok": False, "msg": f"start-alles.bat nicht gefunden: {bat}"})
    import subprocess
    import tempfile
    # Helfer-Bat, DETACHED: erst die alten Loop-Fenster schliessen (die wuerden
    # gekillte Pythons sonst sofort respawnen), dann alle python.exe (trifft
    # absichtlich auch dieses Backend — exakt Finns Hand-Ritual), dann frisch
    # starten. Antwort geht raus, bevor der Kill greift (2s-Puffer).
    helper = os.path.join(tempfile.gettempdir(), "prophos-restart-stack.bat")
    with open(helper, "w", encoding="ascii") as f:
        f.write("@echo off\r\n"
                "timeout /t 2 /nobreak >nul\r\n"
                "taskkill /f /fi \"WINDOWTITLE eq MT5-Hedge-Copier*\" >nul 2>&1\r\n"
                "taskkill /f /fi \"WINDOWTITLE eq Copier-Panel*\" >nul 2>&1\r\n"
                "taskkill /f /fi \"WINDOWTITLE eq Prophos-Backend*\" >nul 2>&1\r\n"
                "taskkill /f /im python.exe >nul 2>&1\r\n"
                "timeout /t 2 /nobreak >nul\r\n"
                f"start \"\" \"{bat}\"\r\n")
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    subprocess.Popen(["cmd", "/c", helper],
                     creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                     close_fds=True, cwd=os.path.dirname(bat))
    print("[stack] Neustart angestossen — dieses Backend wird gleich mitgekillt.", flush=True)
    return jsonify({"ok": True, "msg": "Stack startet neu."})

# ── Duplikium Connect (Basic Auth → Token) ──
@app.route("/duplikum/connect", methods=["POST","OPTIONS"])
def duplikum_connect():
    """
    Body: {"email": "...", "password": "..."}
    Macht Basic-Auth-POST gegen getToken.php und gibt Token zurück.
    Token + Creds werden in-memory gecached für Auto-Refresh.
    """
    if request.method == "OPTIONS": return "", 200
    data = request.get_json(silent=True) or {}
    email    = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"ok": False, "error": "email und password sind nötig"}), 400

    try:
        r = requests.post(
            f"{DUP_BASE}/access/getToken.php",
            auth=(email, password),
            timeout=15
        )
        # Duplikium gibt entweder JSON {token: "..."} oder den Token direkt als Plain-Text zurück.
        # Wir behandeln beide Fälle defensiv.
        token = None
        try:
            d = r.json()
            if isinstance(d, dict):
                token = d.get("token") or d.get("access_token") or (d.get("data") or {}).get("token")
            elif isinstance(d, str):
                token = d
        except Exception:
            # Plain-Text-Response
            txt = (r.text or "").strip().strip('"')
            if txt and len(txt) < 2000 and " " not in txt:
                token = txt

        if not r.ok or not token:
            return jsonify({
                "ok": False,
                "status": r.status_code,
                "error": "Login fehlgeschlagen — prüfe E-Mail/Passwort und ob 'Enable access' im Trade-Copier-Dashboard aktiviert ist.",
                "raw": (r.text or "")[:300]
            }), 401

        # Cache (Memory only)
        duplikum_sessions[email] = {
            "token": token,
            "password": password,
            "last_refresh": time.time()
        }
        return jsonify({"ok": True, "token": token, "email": email})

    except requests.exceptions.RequestException as e:
        return jsonify({"ok": False, "error": f"Netzwerkfehler: {e}"}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

def refresh_duplikum_token(email):
    """Holt einen neuen Token. Nutzt gecachte Creds ODER dauerhafte Env-Creds
    (überlebt Restarts/Worker-Wechsel). Returns neuer Token oder None."""
    s = duplikum_sessions.get(email)
    password = (s or {}).get("password")
    # Fallback: dauerhafte Env-Creds, falls der In-Memory-Cache leer ist
    # (z.B. nach Railway-Restart oder in einem anderen Gunicorn-Worker).
    if not password and email and DUP_EMAIL and email.lower() == DUP_EMAIL.lower():
        password = DUP_PASSWORD
    if not password:
        return None
    try:
        r = requests.post(
            f"{DUP_BASE}/access/getToken.php",
            auth=(email, password),
            timeout=15
        )
        token = None
        try:
            d = r.json()
            if isinstance(d, dict):
                token = d.get("token") or d.get("access_token") or (d.get("data") or {}).get("token")
            elif isinstance(d, str):
                token = d
        except Exception:
            txt = (r.text or "").strip().strip('"')
            if txt and len(txt) < 2000 and " " not in txt:
                token = txt
        if r.ok and token:
            # Session (neu) aufbauen, damit Folge-Refreshes wieder aus dem Cache gehen
            duplikum_sessions[email] = {
                "token": token,
                "password": password,
                "last_refresh": time.time()
            }
            print(f"[duplikum] 🔄 Token refreshed für {email}")
            return token
    except Exception as e:
        print(f"[duplikum] ⚠️ Refresh error: {e}")
    return None

# ── Duplikium Generic Proxy ──
@app.route("/duplikum/<path:path>", methods=["GET","POST","OPTIONS"])
def duplikum_proxy(path):
    """
    Generischer Proxy für alle Duplikium V4 Endpoints.
    Frontend schickt:
      - dup-token Header (Bearer Token)
      - dup-user  Header (Email — für Auto-Refresh nötig)
      - Body als JSON (wir konvertieren zu application/x-www-form-urlencoded
        weil Duplikium keine JSON-Body unterstützt)
    """
    if request.method == "OPTIONS": return "", 200
    token = request.headers.get("dup-token", "")
    email = request.headers.get("dup-user", "")
    if not token:
        return jsonify({"error": "dup-token Header fehlt"}), 401

    url = f"{DUP_BASE}/{path}"

    # JSON Body vom Frontend → form-encoded für Duplikium
    # WICHTIG: Duplikium V4 will PHP-Bracket-Notation für nested arrays
    # (z.B. setSettings.php braucht settings[0][id_slave]=...).
    # Flat dicts wie {email: 'x'} bleiben dabei unverändert.
    body_data = None
    if request.method == "POST":
        raw = request.get_json(silent=True) or {}
        body_data = flatten_php_form(raw) if raw else None

    path_norm = path.lower()
    is_cacheable = request.method == "POST" and path_norm in DUP_CACHEABLE
    # Read-Endpoints dürfen schneller aufgeben (12s) — hängt Duplikum länger, hilft
    # Warten eh nicht; Mutationen behalten die vollen 20s.
    req_timeout = 12 if is_cacheable else 20

    def do_request(tok):
        h = {
            "Authorization": f"Bearer {tok}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        return requests.request(
            request.method,
            url,
            params=request.args,
            data=body_data,  # Dict → automatisch form-encoded
            headers=h,
            timeout=req_timeout
        )

    def do_full_request():
        """Ein echter Upstream-Call inkl. 401-Refresh. Gibt (status, content, ctype, new_tok) zurück."""
        r = do_request(token)
        refresh_email = email or DUP_EMAIL
        if r.status_code == 401 and refresh_email:
            # SICHERHEIT (04.08.2026, Review-Finding): Refresh nur, wenn der Aufrufer den
            # zuletzt bekannten Token dieser Session vorlegt — wie bei /duplikum/refresh.
            # Ohne die Prüfung wäre der Endpoint ein Token-Automat: dup-user ist frei
            # wählbar, CORS steht auf *, und ein beliebiger abgelaufener Token würde
            # reichen, um sich über den 401-Pfad einen FRISCHEN Token für ein fremdes
            # Konto generieren zu lassen (X-New-Dup-Token). Der Refresh rotiert jetzt nur
            # noch einen Token, den man nachweislich schon besaß.
            sess_known = ((duplikum_sessions.get(refresh_email) or {}).get("token") or "").strip()
            if sess_known and hmac.compare_digest((token or "").strip(), sess_known):
                new_tok = refresh_duplikum_token(refresh_email)
                if new_tok:
                    r = do_request(new_tok)
                    return r.status_code, r.content, r.headers.get("Content-Type", "application/json"), new_tok
        # Duplikum meldet einen ABGELAUFENEN Token als HTTP 200 mit code 1006 —
        # ohne diesen Zweig hat der Proxy nie nachgeholt und das Frontend lief in
        # eine tote Session (06.08.2026 live beobachtet).
        if r.status_code == 200 and refresh_email:
            try:
                body = r.json()
            except Exception:
                body = None
            if isinstance(body, dict) and _dup_is_expired_token(body.get("error"), body.get("code")):
                sess_known = ((duplikum_sessions.get(refresh_email) or {}).get("token") or "").strip()
                if sess_known and hmac.compare_digest((token or "").strip(), sess_known):
                    new_tok = refresh_duplikum_token(refresh_email)
                    if new_tok:
                        r = do_request(new_tok)
                        return r.status_code, r.content, r.headers.get("Content-Type", "application/json"), new_tok
        return r.status_code, r.content, r.headers.get("Content-Type", "application/json"), None

    # ── Nicht-cachebare Calls (Mutationen etc.): direkt durch, wie bisher ──
    if not is_cacheable:
        try:
            status, content, ctype, new_tok = do_full_request()
            # Mapping-Endpoints auch bei 200 loggen: editMapping.php kann mit HTTP 200 aber
            # "updated_count":0 antworten (kein passender old_symbol/old_symbol_master-Treffer)
            # — reiner Status->=400-Check hätte das unsichtbar gemacht (Body sah "erfolgreich"
            # aus, war aber ein No-Op).
            is_mapping_call = "mapping/" in path_norm
            # PROPHOS_DEBUG_DUP=1 (nur lokal setzen): loggt zusätzlich die kompletten
            # getSettings-Antworten — zum Diagnostizieren, welche Mapping-Zeilen Duplikum
            # für einen Slave wirklich zurückgibt (id_master vs. id_group etc.).
            debug_dup = bool(os.environ.get("PROPHOS_DEBUG_DUP"))
            is_settings_read = "getsettings" in path_norm
            if status >= 400 or is_mapping_call or (debug_dup and is_settings_read):
                limit = 6000 if (debug_dup and is_settings_read) else 300
                snippet = (content or b"")[:limit].decode("utf-8", errors="replace")
                icon = "⚠️" if status >= 400 else "ℹ️"
                # flush=True: unter nohup ist stdout block-gepuffert — ohne Flush tauchen
                # die Zeilen erst KB-weise später (oder nie) im Log auf.
                print(f"[duplikum] {icon} {path} → HTTP {status}: {snippet}", flush=True)
                if body_data:
                    print(f"[duplikum]    ↳ Request war: {str(body_data)[:300]}", flush=True)
            resp = Response(content, status=status, content_type=ctype)
            if new_tok: resp.headers["X-New-Dup-Token"] = new_tok
            return resp
        except requests.exceptions.RequestException as e:
            return jsonify({"error": f"Netzwerkfehler: {e}"}), 502
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ── Cachebare Lese-Calls: Kurz-Cache + Single-Flight ──
    key = hashlib.md5(
        (path_norm + "|" + token + "|" + json.dumps(body_data or {}, sort_keys=True)
         + "|" + json.dumps(dict(request.args), sort_keys=True)).encode()
    ).hexdigest()
    now = time.time()

    # 1. Schneller Pfad: frischer Cache-Treffer → sofort, ohne Duplikum
    with _dup_cache_lock:
        hit = _dup_cache.get(key)
    if hit and hit[0] > now:
        return Response(hit[2], status=hit[1], content_type=hit[3])

    # 2. Single-Flight: nur EIN Thread pro Key macht den echten Call, der Rest wartet
    with _dup_cache_lock:
        lk = _dup_inflight.get(key)
        if lk is None:
            lk = threading.Lock()
            _dup_inflight[key] = lk
    with lk:
        # Re-Check: ein anderer Thread hat evtl. gerade eben schon gefüllt
        with _dup_cache_lock:
            hit = _dup_cache.get(key)
        if hit and hit[0] > time.time():
            return Response(hit[2], status=hit[1], content_type=hit[3])
        try:
            status, content, ctype, new_tok = do_full_request()
        except requests.exceptions.RequestException as e:
            return jsonify({"error": f"Netzwerkfehler: {e}"}), 502
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        # Nur erfolgreiche Antworten cachen (kein 401/Fehler)
        if status == 200:
            with _dup_cache_lock:
                _dup_cache[key] = (time.time() + DUP_CACHE_TTL, status, content, ctype)
                # opportunistisches Aufräumen abgelaufener Einträge, damit das Dict nicht wächst
                if len(_dup_cache) > 200:
                    tnow = time.time()
                    for k in [k for k, v in _dup_cache.items() if v[0] <= tnow]:
                        _dup_cache.pop(k, None)
        resp = Response(content, status=status, content_type=ctype)
        if new_tok: resp.headers["X-New-Dup-Token"] = new_tok
        return resp

@app.route("/duplikum/refresh", methods=["POST","OPTIONS"])
def duplikum_refresh():
    """Erzwingt einen frischen Duplikum-Token (nächtlicher Auto-Reconnect im Frontend).

    Nutzt die im RAM liegenden Zugangsdaten der bestehenden Session (bzw. die Env-Creds).
    Das Passwort bleibt damit ausschließlich serverseitig — das Frontend braucht es nicht
    zu speichern. Ist keine Session mehr da (z.B. nach einem Backend-Neustart), kommt
    needs_login zurück und das Frontend bittet um einmaliges Neuverbinden.
    """
    if request.method == "OPTIONS":
        return "", 200
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or request.headers.get("dup-user") or "").strip()
    if not email:
        return jsonify({"ok": False, "error": "email fehlt"}), 400

    # SICHERHEIT: Der Aufrufer muss den AKTUELL gültigen Token dieser Session vorlegen.
    # Ohne diese Prüfung wäre der Endpoint ein offener Token-Automat — CORS steht auf "*",
    # d.h. jeder, der die E-Mail kennt, könnte sich sonst einen gültigen Duplikum-Token
    # ausstellen lassen (und damit über den Proxy handeln). Der Refresh rotiert also nur
    # einen Token, den man ohnehin schon besitzt — er vergibt keinen neuen Zugang.
    sess = duplikum_sessions.get(email) or {}
    presented = (request.headers.get("dup-token") or data.get("token") or "").strip()
    known = (sess.get("token") or "").strip()
    if not presented or not known or not hmac.compare_digest(presented, known):
        return jsonify({"ok": False, "error": "Nicht autorisiert"}), 401

    has_creds = bool(sess.get("password")) or \
                bool(DUP_EMAIL and email.lower() == DUP_EMAIL.lower() and DUP_PASSWORD)
    if not has_creds:
        return jsonify({"ok": False, "needs_login": True,
                        "error": "Keine gespeicherten Zugangsdaten — bitte einmal neu verbinden."}), 200
    token = refresh_duplikum_token(email)
    if not token:
        return jsonify({"ok": False, "error": "Token-Refresh fehlgeschlagen"}), 502
    print(f"[duplikum] 🔄 Auto-Reconnect: neuer Token für {email}", flush=True)
    return jsonify({"ok": True, "token": token})

@app.route("/duplikum/disconnect", methods=["POST","OPTIONS"])
def duplikum_disconnect():
    if request.method == "OPTIONS": return "", 200
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    if email and email in duplikum_sessions:
        del duplikum_sessions[email]
    return jsonify({"ok": True})

# ── Token Refresh ──
def refresh_tsx_token(pair_id, session_obj, max_retries=3):
    """
    Refresh TSX JWT via /api/Auth/validate. Returns True bei Erfolg.
    Probiert bis zu max_retries-mal mit exponentiellem Backoff falls Validate-API selbst fehlschlägt.
    """
    s = mirror_sessions.get(pair_id)
    if not s: return False

    for attempt in range(1, max_retries + 1):
        try:
            r = session_obj.post(f"{TSX_BASE}/api/Auth/validate",
                headers={"Authorization": f"Bearer {s['tsxToken']}", "Content-Type": "application/json"},
                timeout=10)
            # 401 → Token komplett abgelaufen, kein Retry sinnvoll
            if r.status_code == 401:
                log_msg(pair_id, "🔒 Token-Refresh: 401 — Token endgültig abgelaufen, neuer Login nötig")
                return False
            # 5xx → Server-seitig, Retry macht Sinn
            if 500 <= r.status_code < 600:
                if attempt < max_retries:
                    backoff = 2 ** attempt
                    log_msg(pair_id, f"⚠️ Token-Refresh HTTP {r.status_code} (Versuch {attempt}/{max_retries}) — Retry in {backoff}s")
                    time.sleep(backoff)
                    continue
                log_msg(pair_id, f"⚠️ Token-Refresh aufgegeben nach {max_retries} Versuchen")
                return False
            if not r.ok:
                log_msg(pair_id, f"⚠️ Token-Refresh HTTP {r.status_code}: {r.text[:100]}")
                return False
            d = r.json()
            if d.get("success") and d.get("newToken"):
                s["tsxToken"] = d["newToken"]
                s["lastTokenRefresh"] = time.time()
                log_msg(pair_id, "🔄 TSX Token refreshed")
                return True
            log_msg(pair_id, f"⚠️ Token-Refresh: {d.get('errorMessage', d)}")
            return False
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                backoff = 2 ** attempt
                log_msg(pair_id, f"⏱ Token-Refresh Timeout (Versuch {attempt}/{max_retries}) — Retry in {backoff}s")
                time.sleep(backoff)
                continue
            log_msg(pair_id, "⚠️ Token-Refresh Timeout — aufgegeben")
            return False
        except requests.exceptions.ConnectionError as e:
            if attempt < max_retries:
                backoff = 2 ** attempt
                log_msg(pair_id, f"🔌 Token-Refresh Connection error (Versuch {attempt}/{max_retries}) — Retry in {backoff}s")
                time.sleep(backoff)
                continue
            log_msg(pair_id, f"⚠️ Token-Refresh Connection error — aufgegeben")
            return False
        except Exception as e:
            log_msg(pair_id, f"⚠️ Token-Refresh exception: {type(e).__name__}: {str(e)[:80]}")
            return False
    return False

# ── Mirror Control ──
@app.route("/mirror/start", methods=["POST","OPTIONS"])
def mirror_start():
    if request.method == "OPTIONS": return "", 200
    data = request.get_json()
    pair_id     = data.get("pairId")
    tsx_token   = data.get("tsxToken")
    tsx_acc_id  = data.get("tsxAccountId")
    ma_token    = data.get("maToken")
    ma_acc_id   = data.get("maAccountId")
    multiplier  = float(data.get("multiplier", 0.5))
    symbol_map  = data.get("symbolMap", {"MNQ": "NAS100", "NQ": "NAS100", "ES": "US500", "MES": "US500"})
    # "polling" (Default, bewährt) oder "realtime" (SignalR/GatewayUserTrade, 20.07.2026,
    # noch nicht live-getestet) — Alt bleibt unangetastet als Fallback erreichbar.
    engine = data.get("engine", "polling")

    if pair_id in mirror_sessions:
        return jsonify({"ok": True, "msg": "Already running"})

    session = {
        "pairId": pair_id,
        "tsxToken": tsx_token,
        "tsxAccountId": tsx_acc_id,
        "maToken": ma_token,
        "maAccountId": ma_acc_id,
        "multiplier": multiplier,
        "targetRiskEur": float(data.get("targetRiskEur", 0)),
        "pollInterval": float(data.get("pollInterval", 0.5)),
        "direction": data.get("direction", "tsx_to_mt"),
        "engine": engine,
        # Kontrakt-Basis, auf die sich der Multiplier bezieht ("MNQ" oder "NQ").
        # Fällt der echte Fill auf dem jeweils anderen Kontrakt der Familie, rechnet
        # open_hedge den Faktor 10 automatisch um (Finn handelt mal MNQ, mal NQ —
        # ein stur angewendeter Multiplier wäre dann ein 10x-Fehler im Hedge).
        "baseInstrument": str(data.get("baseInstrument") or "MNQ").upper(),
        "symbolMap": symbol_map,
        "reverseSymbolMap": {"NAS100": "MNQ", "US500": "MES", "US30": "MYM", "OIL": "CL", "XAUUSD": "GC"},
        "active": True,
        "positions": {},
        "log": [],
        "lastTokenRefresh": time.time(),
    }
    mirror_sessions[pair_id] = session

    if session["direction"] == "mt_to_tsx":
        worker_fn = run_mirror_mt_to_tsx
    elif engine == "realtime":
        worker_fn = run_mirror_realtime
    else:
        worker_fn = run_mirror

    # Watchdog: falls der Worker durch eine unerwartete Exception crasht
    # (sollte mit den neuen except-Klauseln nicht mehr passieren, aber zur Sicherheit),
    # startet er sich automatisch neu — solange SEINE Session (Identität, nicht nur
    # pair_id — Zombie-Bug 21.07.2026) noch aktiv ist.
    def watchdog(pid, fn, sess):
        max_restarts = 5
        restarts = 0
        while mirror_sessions.get(pid) is sess and sess.get("active") and restarts <= max_restarts:
            try:
                fn(pid)
                # Worker ist sauber returnt (z.B. weil active=False) → Loop verlassen
                break
            except Exception as e:
                restarts += 1
                log_msg(pid, f"💥 Worker crashed ({type(e).__name__}: {str(e)[:100]}) — Auto-Restart {restarts}/{max_restarts}")
                time.sleep(2 * restarts)  # kurzer Cooldown
        if restarts > max_restarts:
            log_msg(pid, f"⛔ Worker zu oft gecrasht ({restarts} Restarts) — Pair gestoppt")
            if mirror_sessions.get(pid) is sess:
                sess["active"] = False

    thread = threading.Thread(target=watchdog, args=(pair_id, worker_fn, session), daemon=True)
    thread.start()

    return jsonify({"ok": True})

@app.route("/mirror/stop", methods=["POST","OPTIONS"])
def mirror_stop():
    if request.method == "OPTIONS": return "", 200
    data = request.get_json()
    pair_id = data.get("pairId")
    if pair_id in mirror_sessions:
        mirror_sessions[pair_id]["active"] = False
        del mirror_sessions[pair_id]
    # Echtzeit-Hub SOFORT trennen (nicht erst nächste Loop-Iteration) — sonst spiegelt
    # die alte SignalR-Verbindung noch bis zu 8s weiter, während schon ein Neustart
    # eine zweite Verbindung aufbaut → doppelte Hedge-Orders.
    hub = mirror_hubs.pop(pair_id, None)
    if hub:
        try: hub.stop()
        except Exception: pass
    return jsonify({"ok": True})

@app.route("/mirror/status", methods=["GET"])
def mirror_status():
    # Wenn ?pairId=... gesetzt: nur diesen einen Pair zurückgeben (Frontend-Format)
    pid = request.args.get("pairId")
    if pid:
        s = mirror_sessions.get(pid)
        if not s:
            return jsonify({"active": False, "log": [], "positions": {}})
        # Frontend erwartet die "log"-Einträge in einem Format mit "timestamp"/"message"/"kind"
        return jsonify({
            "active": s.get("active", False),
            "engine": s.get("engine", "polling"),
            "log": s.get("log", [])[-200:],  # neue Log-Konsole zeigt die volle Historie scrollbar
            "positions": s.get("positions", {}),
            "closedHedges": s.get("closedHedges", [])[-20:]
        })
    # Ohne Param: alles (für Debug/Übersicht)
    result = {}
    for pid, s in mirror_sessions.items():
        result[pid] = {"active": s["active"], "log": s["log"][-50:], "positions": s["positions"]}
    return jsonify(result)

# ── Mirror Logic (Polling) TSX → MT5 ──
def run_mirror(pair_id):
    s = mirror_sessions.get(pair_id)
    if not s: return

    # Connection Pooling: eine Session pro Mirror Thread
    http = requests.Session()
    http.verify = False

    log_msg(pair_id, f"🚀 Mirror gestartet — TSX → MT5")
    log_msg(pair_id, f"📊 TSX Account: {s.get('tsxAccountId','?')} · MT5 Account: {s.get('maAccountId','?')}")
    target_eur = float(s.get("targetRiskEur", 0))
    multiplier = float(s.get("multiplier", 1.0))
    if target_eur > 0:
        log_msg(pair_id, f"⚙️ Risiko-Mode: dynamisch ({target_eur}€ Ziel pro Trade)")
    else:
        log_msg(pair_id, f"⚙️ Risiko-Mode: Multiplier {multiplier}x")
    log_msg(pair_id, f"⏱ Polling-Intervall: {s.get('pollInterval', 0.5)}s")

    known_positions = {}
    consecutive_errors = 0
    last_heartbeat = time.time()
    HEARTBEAT_INTERVAL = 120  # alle 2 Minuten ein "alles ruhig"-Log
    MAX_BACKOFF = 60  # max 60s zwischen retries

    # Session-IDENTITÄT prüfen (is s), nicht nur active per pair_id — nach Stop+Neustart
    # existiert unter derselben pair_id eine NEUE Session, und der alte Thread würde sonst
    # als Zombie ewig weiterlaufen und parallel spiegeln (Doppel-Orders, 21.07.2026).
    while mirror_sessions.get(pair_id) is s and s.get("active"):
        # Proaktiver Token Refresh alle 20 min
        if time.time() - s.get("lastTokenRefresh", 0) > TOKEN_REFRESH_INTERVAL:
            refresh_tsx_token(pair_id, http)

        # Heartbeat — bestätigt periodisch dass der Mirror lebt
        if time.time() - last_heartbeat > HEARTBEAT_INTERVAL:
            n_open = len(known_positions)
            log_msg(pair_id, f"💓 Mirror läuft — {n_open} offene Position{'en' if n_open != 1 else ''}")
            last_heartbeat = time.time()

        try:
            r = http.post(f"{TSX_BASE}/api/Position/searchOpen",
                headers={"Authorization": f"Bearer {s['tsxToken']}", "Content-Type": "application/json"},
                json={"accountId": int(s["tsxAccountId"])},
                timeout=10)

            # 401 → Token abgelaufen → refresh versuchen
            if r.status_code == 401:
                log_msg(pair_id, "🔒 401 Unauthorized — versuche Token Refresh")
                if refresh_tsx_token(pair_id, http):
                    consecutive_errors = 0
                    continue  # sofort retry mit neuem Token
                else:
                    consecutive_errors += 1
                    backoff = min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))
                    log_msg(pair_id, f"❌ Token Refresh fehlgeschlagen — warte {backoff}s")
                    time.sleep(backoff)
                    continue

            if not r.ok:
                consecutive_errors += 1
                backoff = min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))
                log_msg(pair_id, f"Poll error: {r.status_code} {r.text[:100]} — warte {backoff}s")
                time.sleep(backoff)
                continue

            # Erfolgreicher Poll → error counter reset
            consecutive_errors = 0

            d = r.json()
            positions = d.get("positions", d.get("data", []))
            current = {str(p.get("id", p.get("positionId", ""))): p for p in positions}

            for pid, pos in current.items():
                if pid not in known_positions:
                    raw_side = pos.get("side", pos.get("action", ""))
                    raw_type = pos.get("type", 0)
                    if raw_type == 1 or raw_side in ("Buy", "buy", "BUY", "Long", 0, "0"):
                        side = "Buy"
                    else:
                        side = "Sell"
                    contract = pos.get("contractId", "")
                    qty = int(pos.get("size", pos.get("quantity", 1)))
                    tsx_risk = float(pos.get("initialRisk", pos.get("risk", 0)) or 0)
                    log_msg(pair_id, f"🆕 TSX Position erkannt: {side} {qty}× {contract}" + (f" · Risk ${tsx_risk}" if tsx_risk > 0 else ""))
                    log_msg(pair_id, f"➡️ Spiegle nach MT5…")
                    open_hedge(pair_id, pid, side, contract, qty, tsx_risk)
                    last_heartbeat = time.time()  # Trade ist Aktivität → Heartbeat reset

            for pid in list(known_positions.keys()):
                if pid not in current:
                    log_msg(pair_id, f"🔚 TSX Position geschlossen: {pid[:12]}…")
                    log_msg(pair_id, f"➡️ Schließe Hedge auf MT5…")
                    close_hedge(pair_id, pid)
                    last_heartbeat = time.time()

            known_positions = current

        except requests.exceptions.Timeout:
            consecutive_errors += 1
            backoff = min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))
            log_msg(pair_id, f"⏱ Timeout — warte {backoff}s")
            time.sleep(backoff)
            continue
        except requests.exceptions.ConnectionError as e:
            consecutive_errors += 1
            backoff = min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))
            log_msg(pair_id, f"🔌 Connection error: {str(e)[:80]} — warte {backoff}s")
            time.sleep(backoff)
            continue
        except (requests.exceptions.JSONDecodeError, ValueError, KeyError, TypeError) as e:
            # API hat unerwartetes/partielles JSON geschickt (z.B. während Maintenance)
            consecutive_errors += 1
            backoff = min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))
            log_msg(pair_id, f"📦 Bad data from TSX: {type(e).__name__} {str(e)[:80]} — warte {backoff}s")
            time.sleep(backoff)
            continue
        except Exception as e:
            # Wirklich unerwartete Exception — niemals den Worker sterben lassen
            consecutive_errors += 1
            backoff = min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))
            log_msg(pair_id, f"⚠️ Unerwarteter Fehler: {type(e).__name__}: {str(e)[:120]} — warte {backoff}s")
            time.sleep(backoff)
            continue

        time.sleep(s.get("pollInterval", 0.5))

    http.close()
    log_msg(pair_id, "Mirror gestoppt")

# ── TSX → MT5 Mirror, Echtzeit (SignalR statt Polling, 20.07.2026) ──
# Ersetzt das 0,5s-Poll-Intervall durch den ProjectX User-Hub (GatewayUserTrade-Event
# pro Fill statt Snapshot-Diff) — behebt die Over-/Undershoot-Probleme aus dem alten
# Poll-Modell (zwischen zwei Polls konnten schon mehrere Fills passiert sein).
# Bewusst NEU statt Ersatz für run_mirror(): Alt bleibt als Fallback/Vergleich nutzbar,
# `engine` in /mirror/start wählt den Worker (Default weiter "polling").
#
# Positions-Tracking läuft über Netto-Menge pro Contract aus dem Trade-Stream selbst
# (nicht über ein GatewayUserPosition "geschlossen"-Signal — dessen genaue Semantik ist
# in der ProjectX-Doku nicht dokumentiert, das selbst berechnete Netto ist dagegen aus
# klar dokumentierten GatewayUserTrade-Feldern (side, size) ableitbar und damit sicherer).
# Reconciliation läuft nur als Log-Warnung (kein Auto-Fix) — bewusst konservativ für die
# erste Version mit echtem Geld; Auto-Heal kann nachgezogen werden sobald das im Alltag
# eine Weile sauber gelaufen ist.
# 1s: seit die Reconciliation selbst heilt (Auto-Übernahme/Auto-Close statt Warnung),
# ist sie das eigentliche Arbeitstier solange der Stream zickt — 60 searchOpen/min
# bleibt klar unter dem dokumentierten Rate-Limit (200 Req/60s, History ausgenommen).
RT_RECONCILE_INTERVAL = 1

def run_mirror_realtime(pair_id):
    s = mirror_sessions.get(pair_id)
    if not s: return

    http = requests.Session()
    http.verify = False

    log_msg(pair_id, "🚀 Mirror gestartet — TSX → MT5 (Echtzeit/SignalR)")
    log_msg(pair_id, f"📊 TSX Account: {s.get('tsxAccountId','?')} · MT5 Account: {s.get('maAccountId','?')}")
    target_eur = float(s.get("targetRiskEur", 0))
    multiplier = float(s.get("multiplier", 1.0))
    if target_eur > 0:
        log_msg(pair_id, f"⚙️ Risiko-Mode: dynamisch ({target_eur}€ Ziel pro Trade)")
    else:
        log_msg(pair_id, f"⚙️ Risiko-Mode: Multiplier {multiplier}x")

    # Netto-Menge pro Contract (signed: + = Long, - = Short) + Referenz-ID für close_hedge
    net = {}           # contractId -> signed qty
    ref = {}           # contractId -> hedge reference id (für s["positions"] / close_hedge)
    seen_trades = {}   # trade-id -> ts. Dedup gegen doppelt zugestellte Events (z.B. nach
                       # Reconnect oder falls serverseitig je doppelt abonniert) — ein doppelt
                       # verarbeiteter Fill würde net verfälschen und falsche Hedges auslösen.
    sub_lock = threading.Lock()
    # pos_lock serialisiert ALLE net/ref-Mutationen inkl. Hedge-Auslösung — Event-Thread
    # (on_trade) und Worker-Thread (Baseline/Heal) dürfen nie gleichzeitig dieselbe
    # Position adoptieren, sonst öffnen beide einen Hedge (Race → Doppel-Order).
    pos_lock = threading.Lock()
    first_event_logged = [False]
    reconnects = [0]
    opened_at = {}         # contractId -> Zeitpunkt der lokalen Übernahme. Ersetzt den alten
                           # 2-Pass-Phantom-Zähler: statt zwei Abgleich-Runden zu warten
                           # (kostete beim Schließen 4-6s, Finns Kritik 21.07.), reicht EIN
                           # Pass, solange die Position älter ist als der REST-Snapshot sein
                           # kann (2,5s-Guard gegen das Race "Event eröffnet Position, während
                           # der gerade gezogene ältere Snapshot sie noch nicht kennt").
    last_rebuild = [0]     # Cap gegen Rebuild-Loops (erster Heal darf sofort)
    rebuild_count = [0]    # nach 3 erfolglosen Neuaufbauten: nur noch alle 5 min versuchen
    stream_events = [0]    # empfangene GatewayUserTrade-Events — Diagnose: Stream lebt vs. tot
    conn_mode = ["direct"] # "direct" (skip_negotiation, wie ProjectX-JS-Doku) | "negotiate"
                           # (Standard-SignalR-Handshake). Liefert der Direktmodus nachweislich
                           # keine Events (Heal nötig, 0 Events), wird beim Neuaufbau auf
                           # Negotiation gewechselt — Verdacht: Load-Balancer hinter
                           # rtc.topstepx.com braucht das Handshake für korrektes Routing.

    # SignalR-interne Logs (INFO+) in die Pair-Konsole spiegeln — wenn der SERVER die
    # Verbindung aktiv trennt, nennt er den Grund in einer Close-Message, die die Library
    # nur auf INFO-Level loggt. Ohne diese Bridge flogen wir bei Verbindungsproblemen
    # blind (Reconnect-Bursts beim Live-Test 21.07.2026, Ursache unsichtbar).
    class _SrLogBridge(logging.Handler):
        def emit(self, record):
            try:
                if not session_alive():
                    return
                m = record.getMessage()
                if not m:
                    return
                log_msg(pair_id, f"📶 SignalR: {str(m)[:180]}", "warn" if record.levelno >= logging.WARNING else "info")
            except Exception:
                pass
    _sr_logger = logging.getLogger("SignalRCoreClient")
    _sr_bridge = _SrLogBridge(level=logging.INFO)
    _sr_logger.addHandler(_sr_bridge)

    # WICHTIG (Lesson vom 21.07.2026, Zombie-Thread-Bug): Session-IDENTITÄT prüfen, nicht
    # nur active-Flag per pair_id. Nach Stop+Neustart existiert unter derselben pair_id eine
    # NEUE Session — der alte Thread muss sich selbst als überholt erkennen und beenden,
    # sonst spiegeln zwei Verbindungen parallel (Doppel-Orders).
    def session_alive():
        return mirror_sessions.get(pair_id) is s and s.get("active")

    def hub_is_current(h):
        return mirror_hubs.get(pair_id) is h

    def fetch_risk_for_contract(contract_id):
        """Best-effort: initialRisk für eine gerade neu erkannte Position nachladen,
        damit der dynamische Risiko-Modus (targetRiskEur) auch im Echtzeit-Pfad
        funktioniert. Schlägt der Call fehl, fällt open_hedge auf Multiplier zurück."""
        try:
            r = http.post(f"{TSX_BASE}/api/Position/searchOpen",
                headers={"Authorization": f"Bearer {s['tsxToken']}", "Content-Type": "application/json"},
                json={"accountId": int(s["tsxAccountId"])}, timeout=8)
            if not r.ok: return 0
            positions = r.json().get("positions", r.json().get("data", []))
            for p in positions:
                if p.get("contractId") == contract_id:
                    return float(p.get("initialRisk", p.get("risk", 0)) or 0)
        except Exception:
            pass
        return 0

    def is_dup_trade(tid):
        if tid is None: return False
        key = str(tid)
        if key in seen_trades: return True
        seen_trades[key] = time.time()
        if len(seen_trades) > 2000:
            for k in sorted(seen_trades, key=seen_trades.get)[:1000]:
                seen_trades.pop(k, None)
        return False

    def on_trade(h, args):
        try:
            if not session_alive() or not hub_is_current(h):
                return  # überholte Verbindung/Session — nichts mehr auslösen
            # Defensive: Event-Payload kann [tradeObj] oder [accountId, tradeObj] sein
            data = None
            if args and isinstance(args[0], dict): data = args[0]
            elif args and len(args) > 1 and isinstance(args[1], dict): data = args[1]
            if data is None: return
            stream_events[0] += 1
            if not first_event_logged[0]:
                first_event_logged[0] = True
                log_msg(pair_id, f"📡 Erstes Trade-Event empfangen: {json.dumps(data)[:220]}")
            evt_acc = data.get("accountId")
            if evt_acc is not None and str(evt_acc) != str(s.get("tsxAccountId")):
                return  # Event für einen anderen Account auf derselben Connection
            if is_dup_trade(data.get("id")):
                return  # exakt dieses Trade-Event wurde schon verarbeitet
            contract = data.get("contractId", "")
            raw_side = data.get("side", 0)
            size = int(data.get("size", 0) or 0)
            if not contract or size <= 0:
                return
            signed = size if raw_side in (0, "0", "Buy", "buy", "BUY", "Long", "long", "B") else -size

            with pos_lock:
                prev = net.get(contract, 0)
                new = prev + signed
                net[contract] = new

                if prev == 0 and new != 0:
                    # Neue Position
                    rid = ref.get(contract) or f"rt-{contract}-{uuid.uuid4().hex[:8]}"
                    ref[contract] = rid
                    opened_at[contract] = time.time()
                    side_label = "Buy" if new > 0 else "Sell"
                    log_msg(pair_id, f"🆕 TSX Fill erkannt (Echtzeit): {side_label} {abs(new)}× {contract}")
                    risk = fetch_risk_for_contract(contract) if target_eur > 0 else 0
                    log_msg(pair_id, "➡️ Spiegle nach MT5…")
                    open_hedge(pair_id, rid, 0 if new > 0 else 1, contract, abs(new), risk)
                elif prev != 0 and new == 0:
                    # Position komplett geschlossen
                    rid = ref.pop(contract, None)
                    opened_at.pop(contract, None)
                    log_msg(pair_id, f"🔚 TSX Position geschlossen (Echtzeit): {contract}")
                    if rid:
                        log_msg(pair_id, "➡️ Schließe Hedge auf MT5…")
                        close_hedge(pair_id, rid)
                elif prev != 0 and new != 0 and (prev > 0) != (new > 0):
                    # Durchgerutscht (Long→Short direkt ohne 0-Zwischenstand) — alten Hedge zu,
                    # neuen auf. Seltener Fall (ein einzelner großer Gegen-Trade).
                    rid_old = ref.pop(contract, None)
                    if rid_old:
                        log_msg(pair_id, f"🔁 TSX Position durch Gegen-Trade gedreht: {contract} — schließe alten Hedge…")
                        close_hedge(pair_id, rid_old)
                    rid_new = f"rt-{contract}-{uuid.uuid4().hex[:8]}"
                    ref[contract] = rid_new
                    opened_at[contract] = time.time()
                    risk = fetch_risk_for_contract(contract) if target_eur > 0 else 0
                    log_msg(pair_id, "➡️ Öffne gedrehten Hedge auf MT5…")
                    open_hedge(pair_id, rid_new, 0 if new > 0 else 1, contract, abs(new), risk)
                elif prev != 0 and new != 0:
                    # Größe innerhalb einer offenen Position geändert (Nachkauf/Teilverkauf) —
                    # wie im alten Poll-Modell (das reagiert auch nur auf neu/weg, nicht auf
                    # Größenänderung) wird das hier nur geloggt, nicht automatisch nachjustiert.
                    log_msg(pair_id, f"ℹ️ Positionsgröße geändert: {contract} {prev}→{new} (Hedge-Größe bleibt wie beim Opening — nicht automatisch angepasst)")
        except Exception as e:
            log_msg(pair_id, f"⚠️ Fehler beim Verarbeiten eines Trade-Events: {type(e).__name__}: {str(e)[:120]}")

    def sync_baseline(heal=False):
        """Bereits offene TSX-Positionen (offen vor Verbindungsaufbau, oder während eines
        Reconnects/Stream-Ausfalls verpasst) per REST übernehmen — der Event-Stream liefert
        nur NEUE Fills. Läuft bei jedem (Re-)Connect UND als Heal aus der Reconciliation;
        bereits getrackte Contracts werden übersprungen. heal=True ändert nur die Log-Texte."""
        try:
            r = http.post(f"{TSX_BASE}/api/Position/searchOpen",
                headers={"Authorization": f"Bearer {s['tsxToken']}", "Content-Type": "application/json"},
                json={"accountId": int(s["tsxAccountId"])}, timeout=10)
            if not r.ok:
                log_msg(pair_id, f"⚠️ Baseline-Sync: HTTP {r.status_code} — {r.text[:80]}", "warn")
                return 0
            positions = r.json().get("positions", r.json().get("data", []))
            taken = 0
            with pos_lock:
                for pos in positions:
                    contract = pos.get("contractId", "")
                    if not contract or contract in ref: continue
                    raw_side = pos.get("side", pos.get("action", ""))
                    raw_type = pos.get("type", 0)
                    is_buy = raw_type == 1 or raw_side in (0, "0", "Buy", "buy", "BUY", "Long")
                    qty = int(pos.get("size", pos.get("quantity", 1)) or 0)
                    if qty <= 0: continue
                    tsx_risk = float(pos.get("initialRisk", pos.get("risk", 0)) or 0)
                    net[contract] = qty if is_buy else -qty
                    rid = f"rt-{contract}-{uuid.uuid4().hex[:8]}"
                    ref[contract] = rid
                    opened_at[contract] = time.time()
                    taken += 1
                    if heal:
                        log_msg(pair_id, f"🛟 Stream-Lücke — übernehme TSX-Position per REST: {'Buy' if is_buy else 'Sell'} {qty}× {contract}", "warn")
                    else:
                        log_msg(pair_id, f"🆕 Bereits offene TSX-Position übernommen: {'Buy' if is_buy else 'Sell'} {qty}× {contract}")
                    log_msg(pair_id, "➡️ Spiegle nach MT5…")
                    open_hedge(pair_id, rid, 0 if is_buy else 1, contract, qty, tsx_risk)
            # Auch Stille diagnostizierbar machen — beim letzten Mal war unklar, ob der
            # Baseline-Sync überhaupt gelaufen ist. (Nur beim Connect-Sync, Heals sind eh laut.)
            if not heal:
                if not positions:
                    log_msg(pair_id, "📊 Baseline-Sync: keine offenen TSX-Positionen")
                elif taken == 0:
                    log_msg(pair_id, "📊 Baseline-Sync: alle offenen Positionen bereits getrackt")
            return taken
        except Exception as e:
            log_msg(pair_id, f"⚠️ Baseline-Sync fehlgeschlagen: {type(e).__name__}: {str(e)[:100]}", "warn")
            return 0

    def do_subscribe(h):
        if not session_alive() or not hub_is_current(h):
            return  # überholte Verbindung soll weder abonnieren noch Baseline-Hedges auslösen
        with sub_lock:
            if getattr(h, "_pph_subscribed", False):
                return  # schon abonniert auf DIESER Verbindung — ein zweites SubscribeTrades
                        # würde jedes Event doppelt zustellen (→ falsche net-Stände)
            try:
                # on_invocation: Server-Completion abwarten — nur so wissen wir sicher,
                # ob das Abonnement überhaupt akzeptiert wurde (Ablehnung käme als
                # Error-Completion und landet über on_error in der Konsole).
                def _sub_confirmed(completion, hh=h):
                    if hub_is_current(hh):
                        log_msg(pair_id, "✅ Subscription vom Server bestätigt")
                h.send("SubscribeTrades", [int(s["tsxAccountId"])], on_invocation=_sub_confirmed)
                h._pph_subscribed = True
            except Exception as e:
                log_msg(pair_id, f"⚠️ Subscribe fehlgeschlagen: {type(e).__name__}: {str(e)[:100]}", "warn")
                return
        log_msg(pair_id, "🔌 Verbunden & auf Trades abonniert (User Hub)")
        sync_baseline()

    def on_hub_reopen(h):
        # Nach einem Reconnect ist es serverseitig eine NEUE Verbindung — Subscription
        # ist weg und muss neu angemeldet werden.
        with sub_lock:
            h._pph_subscribed = False
        reconnects[0] += 1
        log_msg(pair_id, f"🔁 Stream-Reconnect #{reconnects[0]}", "warn")
        do_subscribe(h)

    def on_hub_close(h):
        with sub_lock:
            h._pph_subscribed = False
        if session_alive() and hub_is_current(h):
            log_msg(pair_id, "🔌 Verbindung getrennt — automatischer Reconnect läuft…", "warn")

    def build_hub(token):
        # Callbacks werden fest an DIESES Hub-Objekt gebunden (Parameter h, nicht die äußere
        # hub-Variable!) — sonst greifen die Callbacks einer alten Verbindung nach einem
        # Token-Refresh auf die NEUE Verbindung zu und der Identitäts-Check läuft ins Leere.
        use_negotiate = conn_mode[0] == "negotiate"
        log_msg(pair_id, f"🔧 Verbindungsmodus: {'Negotiation-Handshake' if use_negotiate else 'Direkt (skip negotiation)'}")
        h = HubConnectionBuilder()\
            .with_url(f"{RTC_BASE}/hubs/user?access_token={token}", options={"skip_negotiation": not use_negotiate}) \
            .configure_logging(logging.INFO) \
            .with_automatic_reconnect({
                "type": "interval",
                "keep_alive_interval": 10,
                "intervals": [1, 2, 5, 10, 15, 30, 60]
            }).build()
        h.on_open(lambda: do_subscribe(h))
        h.on_reconnect(lambda: on_hub_reopen(h))
        h.on_close(lambda: on_hub_close(h))
        # Completion-Errors kommen als CompletionMessage-Objekt — .error extrahieren,
        # sonst steht nur der Objektname im Log statt der Server-Begründung.
        h.on_error(lambda e: log_msg(pair_id, f"⚠️ Hub-Fehler: {str(getattr(e, 'error', None) or e)[:150]}", "warn"))
        h.on("GatewayUserTrade", lambda args: on_trade(h, args))
        return h

    def rebuild_connection(reason, flip_mode=False):
        # Registrierung ZUERST auf die neue Verbindung umbiegen, dann alte stoppen —
        # so erkennen sich alle Callbacks der alten sofort als überholt.
        nonlocal hub
        if flip_mode:
            conn_mode[0] = "negotiate" if conn_mode[0] == "direct" else "direct"
        log_msg(pair_id, f"🔁 Stream-Verbindung wird neu aufgebaut — {reason}")
        old = hub
        hub = build_hub(s["tsxToken"])
        mirror_hubs[pair_id] = hub
        try: old.stop()
        except Exception: pass
        try:
            hub.start()
        except Exception as e:
            log_msg(pair_id, f"❌ Stream-Neuaufbau fehlgeschlagen: {str(e)[:120]}", "err")

    hub = build_hub(s["tsxToken"])
    mirror_hubs[pair_id] = hub  # VOR start() registrieren — on_open kann sofort feuern
    try:
        hub.start()
    except Exception as e:
        log_msg(pair_id, f"❌ Verbindungsaufbau fehlgeschlagen: {type(e).__name__}: {str(e)[:150]}", "err")
        if mirror_hubs.get(pair_id) is hub:
            mirror_hubs.pop(pair_id, None)
        try:
            _sr_logger.removeHandler(_sr_bridge)
        except Exception:
            pass
        return

    # Reconciliation-Watchdog mit SELBSTHEILUNG (21.07.2026): der Live-Test hat gezeigt,
    # dass der SignalR-Stream de facto ausfallen kann (Reconnect-Burst beim Start, danach
    # nominell verbunden, aber keine Events mehr) — reine Warnungen halfen Finn nicht,
    # die Position blieb ungespiegelt bis zum manuellen Neustart. Deshalb handelt der
    # Abgleich jetzt selbst:
    #  - Position auf TSX ohne lokalen Hedge → sofort per sync_baseline(heal) übernehmen
    #    (racefrei durch pos_lock + ref-Check; schlimmstenfalls ~3-6s Latenz statt nie).
    #  - Lokal getrackt, aber auf TSX weg → Hedge schließen, aber erst nach 2 Pässen in
    #    Folge (~6s): schützt gegen den Race, dass ein frisch per Event eröffneter Trade
    #    im gerade gezogenen (älteren) REST-Snapshot noch fehlt.
    #  - Nach jedem Heal gilt der Stream als defekt → Verbindung wird neu aufgebaut
    #    (max. 1×/60s, damit kein Rebuild-Loop entsteht).
    last_heartbeat = time.time()
    HEARTBEAT_INTERVAL = 120
    while session_alive():
        if time.time() - s.get("lastTokenRefresh", 0) > TOKEN_REFRESH_INTERVAL:
            if refresh_tsx_token(pair_id, http):
                # Frischer Token → Hub braucht neue Verbindung (access_token steckt in der URL)
                rebuild_connection("Token erneuert")

        if time.time() - last_heartbeat > HEARTBEAT_INTERVAL:
            n_open = len(ref)
            log_msg(pair_id, f"💓 Mirror läuft (Echtzeit) — {n_open} offene Position{'en' if n_open != 1 else ''} · {reconnects[0]} Reconnects bisher")
            last_heartbeat = time.time()

        try:
            r = http.post(f"{TSX_BASE}/api/Position/searchOpen",
                headers={"Authorization": f"Bearer {s['tsxToken']}", "Content-Type": "application/json"},
                json={"accountId": int(s["tsxAccountId"])}, timeout=10)
            if r.ok:
                positions = r.json().get("positions", r.json().get("data", []))
                rest_contracts = {p.get("contractId") for p in positions if p.get("contractId")}
                with pos_lock:
                    tracked_contracts = {c for c, q in net.items() if q != 0}
                missing_locally = rest_contracts - tracked_contracts    # TSX hat's, wir nicht
                phantom_locally = tracked_contracts - rest_contracts    # wir haben's, TSX nicht mehr
                healed = False

                if missing_locally:
                    log_msg(pair_id, f"🛟 Abgleich: {len(missing_locally)} TSX-Position(en) ohne Hedge ({', '.join(list(missing_locally)[:3])}) — übernehme automatisch…", "warn")
                    if sync_baseline(heal=True) > 0:
                        healed = True

                # Phantom = lokal getrackt, auf TSX weg → Hedge schließen. EIN Pass reicht,
                # solange die Position älter ist als der REST-Snapshot sein kann (2,5s) —
                # der alte 2-Pass-Zähler kostete beim Schließen 4-6s (Finns Kritik 21.07.).
                # Frisch eröffnete Positionen (< 2,5s) überspringen: der gerade verarbeitete
                # Snapshot könnte VOR ihrer Eröffnung gezogen worden sein (Race).
                for c in phantom_locally:
                    if time.time() - opened_at.get(c, 0) < 2.5:
                        continue
                    with pos_lock:
                        rid = ref.pop(c, None)
                        net[c] = 0
                        opened_at.pop(c, None)
                    log_msg(pair_id, f"🛟 Abgleich: {c} auf TSX geschlossen — schließe Hedge automatisch…", "warn")
                    if rid:
                        close_hedge(pair_id, rid)
                    healed = True

                if healed:
                    # Nach 3 Neuaufbau-Versuchen ohne dass der Stream je geliefert hat:
                    # Frequenz auf 5 min drosseln — die Reconnect-Stürme haben beim Live-Test
                    # serverseitig HTTP 429 (Rate-Limit) provoziert und machen es nur schlimmer.
                    cooldown = 60 if rebuild_count[0] < 3 else 300
                    if last_rebuild[0] == 0 or time.time() - last_rebuild[0] > cooldown:
                        last_rebuild[0] = time.time()
                        rebuild_count[0] += 1
                        # Hat der Stream in diesem Verbindungsmodus noch NIE ein Event geliefert,
                        # ist der Modus selbst verdächtig → beim Neuaufbau auf den anderen wechseln
                        # (direct ↔ negotiate). Kamen früher schon Events, Modus beibehalten.
                        rebuild_connection("Stream hat Events verpasst", flip_mode=(stream_events[0] == 0))
        except Exception:
            pass  # Reconciliation ist nur ein Sicherheitsnetz, Fehler hier sollen den Mirror nicht stoppen

        time.sleep(RT_RECONCILE_INTERVAL)

    if mirror_hubs.get(pair_id) is hub:
        mirror_hubs.pop(pair_id, None)
    try:
        hub.stop()
    except Exception:
        pass
    try:
        _sr_logger.removeHandler(_sr_bridge)
    except Exception:
        pass
    http.close()
    log_msg(pair_id, "Mirror gestoppt")

def _instr_scale(fill_base, plan_base):
    """Micro/Mini-Umrechnung innerhalb einer Kontrakt-Familie (Faktor 10).
    Der Multiplier eines Plans bezieht sich auf EIN Instrument (z.B. Lots je NQ);
    fällt der echte Fill auf dem Schwester-Kontrakt (MNQ), muss die Lot-Größe
    durch 10 — sonst wäre der Hedge um Faktor 10 falsch. ProjectX benennt die
    E-minis in Contract-IDs teils ENQ/EP, deshalb beide Schreibweisen."""
    minis  = {"NQ": "NQ", "ENQ": "NQ", "ES": "ES", "EP": "ES", "YM": "YM"}
    micros = {"MNQ": "NQ", "MES": "ES", "MYM": "YM"}
    def norm(x):
        x = str(x or "").upper()
        if x in micros: return (micros[x], "micro")
        if x in minis:  return (minis[x], "mini")
        return (x, None)
    ff, fk = norm(fill_base)
    pf, pk = norm(plan_base)
    if ff != pf or fk is None or pk is None or fk == pk:
        return 1.0
    return 10.0 if (pk == "micro" and fk == "mini") else 0.1

def open_hedge(pair_id, order_id, side, contract, qty, tsx_risk_usd=0):
    s = mirror_sessions.get(pair_id)
    if not s: return

    parts = contract.split(".")
    base = parts[3] if len(parts) > 3 else (parts[2] if len(parts) > 2 else contract[:3])
    mt_symbol = s["symbolMap"].get(base, "NAS100")

    target_eur = float(s.get("targetRiskEur", 0))
    multiplier = float(s.get("multiplier", 1.0))

    if target_eur > 0 and tsx_risk_usd > 0:
        lots = round((target_eur / tsx_risk_usd) * qty * 2.33, 2)
        log_msg(pair_id, f"Lot Berechnung: ({target_eur}€ / ${tsx_risk_usd}) × {qty} × 2.33 = {lots}")
    else:
        scale = _instr_scale(base, s.get("baseInstrument", "MNQ"))
        lots = round(qty * multiplier * scale, 2)
        if scale != 1.0:
            log_msg(pair_id, f"⚖️ Kontrakt-Umrechnung: Fill auf {base}, Multiplier-Basis {s.get('baseInstrument','MNQ')} → Faktor {scale} → {lots} Lots")

    lots = max(0.01, lots)

    mt_side = "ORDER_TYPE_SELL" if side in (0, "0", "Buy", "buy", "BUY", "Long", "long", "B") else "ORDER_TYPE_BUY"

    body = {"symbol": mt_symbol, "volume": lots, "actionType": mt_side, "comment": f"HM-{str(order_id)[:8]}"}

    # Eigene Session pro hedge-call ist OK (kurzlebig), aber wir wollen nicht bei Connection-Errors crashen
    try:
        r = requests.post(
            f"{MA_BASE}/users/current/accounts/{s['maAccountId']}/trade",
            headers={"auth-token": s["maToken"], "Content-Type": "application/json"},
            json=body, timeout=15, verify=False)
        try:
            d = r.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            d = {}
        if r.ok:
            pos_id = str(d.get("positionId") or d.get("orderId", ""))
            s["positions"][order_id] = pos_id
            log_msg(pair_id, f"✅ Hedge OPEN: {mt_side.split('_')[-1]} {lots}x {mt_symbol} | pos={pos_id}")
        else:
            log_msg(pair_id, f"❌ Open failed: {r.status_code} {r.text[:150]}")
    except requests.exceptions.Timeout:
        log_msg(pair_id, f"⏱ Open timeout (Trade ggf. trotzdem ausgeführt — bitte MT5 prüfen!)")
    except requests.exceptions.ConnectionError as e:
        log_msg(pair_id, f"🔌 Open connection error: {str(e)[:100]}")
    except Exception as e:
        log_msg(pair_id, f"❌ Open error: {type(e).__name__}: {str(e)[:120]}")

def close_hedge(pair_id, ref_id):
    s = mirror_sessions.get(pair_id)
    if not s: return

    pos_id = s["positions"].get(ref_id)
    if not pos_id:
        # Falls die Master-Position bereits manuell geschlossen wurde, ignorieren
        log_msg(pair_id, f"ℹ️ Keine gespiegelte MT-Position für {ref_id} (manuell geschlossen?)")
        return

    body = {"actionType": "POSITION_CLOSE_ID", "positionId": pos_id}
    try:
        r = requests.post(
            f"{MA_BASE}/users/current/accounts/{s['maAccountId']}/trade",
            headers={"auth-token": s["maToken"], "Content-Type": "application/json"},
            json=body, timeout=15, verify=False)
        if r.ok:
            log_msg(pair_id, f"✅ Hedge CLOSED: pos={pos_id}")
            s["positions"].pop(ref_id, None)
            # Geschlossene Hedge-IDs behalten — das Auto-PnL-Prefill im Trade-Complete-
            # Modal matcht darüber die MetaApi-Deals (die positions-Map verliert die ID
            # ja gerade beim Schließen). Cap gegen unbegrenztes Wachstum.
            s.setdefault("closedHedges", []).append({"mtPosId": str(pos_id), "ts": time.time()})
            if len(s["closedHedges"]) > 50:
                s["closedHedges"] = s["closedHedges"][-50:]
        else:
            # Wenn die Position auf MT-Seite schon weg ist (404 oder 4xx-Fehler), trotzdem aus dem Tracking entfernen
            err_text = r.text[:100]
            log_msg(pair_id, f"❌ Close failed: {r.status_code} {err_text}")
            if r.status_code == 404 or "not found" in err_text.lower() or "no position" in err_text.lower():
                log_msg(pair_id, f"ℹ️ MT-Position bereits weg — entferne aus Tracking")
                s["positions"].pop(ref_id, None)
    except requests.exceptions.Timeout:
        log_msg(pair_id, f"⏱ Close timeout (Position ggf. trotzdem geschlossen — bitte MT5 prüfen!)")
    except requests.exceptions.ConnectionError as e:
        log_msg(pair_id, f"🔌 Close connection error: {str(e)[:100]}")
    except Exception as e:
        log_msg(pair_id, f"❌ Close error: {type(e).__name__}: {str(e)[:120]}")

def log_msg(pair_id, msg, kind=None):
    """
    Log eine Message für ein Pair. kind ist optional ('ok', 'warn', 'err', 'info').
    Wenn nicht angegeben, wird's aus dem Emoji-Präfix abgeleitet.
    """
    print(f"[{pair_id}] {msg}")
    if pair_id not in mirror_sessions:
        return

    # Auto-Detect kind aus Emoji wenn nicht explizit angegeben
    if kind is None:
        first_chars = msg[:3] if msg else ""
        if any(e in first_chars for e in ["✅", "🔄", "🆕", "📊"]):
            kind = "ok"
        elif any(e in first_chars for e in ["❌", "💥", "⛔", "🔒"]):
            kind = "err"
        elif any(e in first_chars for e in ["⚠️", "⏱", "🔌", "📦"]):
            kind = "warn"
        else:
            kind = "info"

    mirror_sessions[pair_id]["log"].append({
        "ts": time.strftime("%H:%M:%S"),
        "msg": msg,
        "kind": kind
    })
    # Log-Größe begrenzen damit RAM nicht explodiert
    if len(mirror_sessions[pair_id]["log"]) > 500:
        mirror_sessions[pair_id]["log"] = mirror_sessions[pair_id]["log"][-500:]

# ── MT5 → TopstepX Mirror ──
def run_mirror_mt_to_tsx(pair_id):
    s = mirror_sessions.get(pair_id)
    if not s: return

    http = requests.Session()
    http.verify = False

    log_msg(pair_id, f"🚀 Mirror gestartet — MT5 → TSX")
    log_msg(pair_id, f"📊 MT5 Account: {s.get('maAccountId','?')} · TSX Account: {s.get('tsxAccountId','?')}")
    log_msg(pair_id, f"⚙️ Multiplier: {s.get('multiplier', 1.0)}x")
    log_msg(pair_id, f"⏱ Polling-Intervall: {s.get('pollInterval', 0.5)}s")

    known_positions = {}
    consecutive_errors = 0
    last_heartbeat = time.time()
    HEARTBEAT_INTERVAL = 120
    MAX_BACKOFF = 60

    # Session-Identität statt nur active-Flag — siehe Kommentar in run_mirror (Zombie-Bug)
    while mirror_sessions.get(pair_id) is s and s.get("active"):
        # TSX Token auch hier refreshen (brauchen wir für close orders)
        if time.time() - s.get("lastTokenRefresh", 0) > TOKEN_REFRESH_INTERVAL:
            refresh_tsx_token(pair_id, http)

        # Heartbeat
        if time.time() - last_heartbeat > HEARTBEAT_INTERVAL:
            n_open = len(known_positions)
            log_msg(pair_id, f"💓 Mirror läuft — {n_open} offene Position{'en' if n_open != 1 else ''}")
            last_heartbeat = time.time()

        try:
            r = http.get(
                f"{MA_BASE}/users/current/accounts/{s['maAccountId']}/positions",
                headers={"auth-token": s["maToken"], "Content-Type": "application/json"},
                timeout=15)

            if not r.ok:
                consecutive_errors += 1
                backoff = min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))
                log_msg(pair_id, f"MT Poll error: {r.status_code} — warte {backoff}s")
                time.sleep(backoff)
                continue

            consecutive_errors = 0

            positions = r.json()
            if not isinstance(positions, list):
                positions = positions.get("positions", [])

            current = {str(p.get("id", "")): p for p in positions}

            for pid, pos in current.items():
                if pid not in known_positions:
                    mt_type = pos.get("type", "")
                    mt_symbol = pos.get("symbol", "")
                    mt_volume = float(pos.get("volume", 1))
                    tsx_symbol = s["reverseSymbolMap"].get(mt_symbol, "MNQ")
                    if "BUY" in str(mt_type).upper():
                        tsx_side = 1
                        side_label = "Sell"
                    else:
                        tsx_side = 0
                        side_label = "Buy"
                    qty = max(1, round(mt_volume * s["multiplier"]))
                    log_msg(pair_id, f"🆕 MT5 Position erkannt: {mt_type} {mt_volume}× {mt_symbol}")
                    log_msg(pair_id, f"➡️ Spiegle nach TSX als {side_label} {qty}× {tsx_symbol}…")
                    open_tsx_hedge(pair_id, pid, tsx_side, tsx_symbol, qty)
                    last_heartbeat = time.time()

            for pid in list(known_positions.keys()):
                if pid not in current:
                    log_msg(pair_id, f"🔚 MT5 Position geschlossen: {pid[:12]}…")
                    log_msg(pair_id, f"➡️ Schließe Hedge auf TSX…")
                    try:
                        r2 = http.post(f"{TSX_BASE}/api/Position/searchOpen",
                            headers={"Authorization": f"Bearer {s['tsxToken']}", "Content-Type": "application/json"},
                            json={"accountId": int(s["tsxAccountId"])}, timeout=10)
                        if r2.status_code == 401:
                            refresh_tsx_token(pair_id, http)
                            r2 = http.post(f"{TSX_BASE}/api/Position/searchOpen",
                                headers={"Authorization": f"Bearer {s['tsxToken']}", "Content-Type": "application/json"},
                                json={"accountId": int(s["tsxAccountId"])}, timeout=10)
                        tsx_positions = r2.json().get("positions", [])
                        if not tsx_positions:
                            log_msg(pair_id, f"ℹ️ Keine offenen TSX-Positionen — bereits geschlossen?")
                        for tpos in tsx_positions:
                            ttype = tpos.get("type", 0)
                            tsize = int(tpos.get("size", 1))
                            tcontract = tpos.get("contractId", "CON.F.US.MNQ.M26")
                            close_side = 1 if ttype == 1 else 0
                            close_body = {
                                "accountId": int(s["tsxAccountId"]),
                                "contractId": tcontract,
                                "type": 2,
                                "side": close_side,
                                "size": tsize
                            }
                            cr = http.post(f"{TSX_BASE}/api/Order/place",
                                headers={"Authorization": f"Bearer {s['tsxToken']}", "Content-Type": "application/json"},
                                json=close_body, timeout=10)
                            if cr.ok:
                                log_msg(pair_id, f"✅ TSX Close Order gesendet: {tsize}× {tcontract}")
                            else:
                                log_msg(pair_id, f"❌ TSX Close Order failed: {cr.status_code} {cr.text[:80]}")
                    except Exception as e:
                        log_msg(pair_id, f"❌ TSX Close error: {type(e).__name__}: {str(e)[:120]}")
                    last_heartbeat = time.time()
                    if pid in s["positions"]:
                        del s["positions"][pid]

            known_positions = current

        except requests.exceptions.Timeout:
            consecutive_errors += 1
            backoff = min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))
            log_msg(pair_id, f"⏱ MT Timeout — warte {backoff}s")
            time.sleep(backoff)
            continue
        except requests.exceptions.ConnectionError as e:
            consecutive_errors += 1
            backoff = min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))
            log_msg(pair_id, f"🔌 MT Connection error: {str(e)[:80]} — warte {backoff}s")
            time.sleep(backoff)
            continue
        except (requests.exceptions.JSONDecodeError, ValueError, KeyError, TypeError) as e:
            consecutive_errors += 1
            backoff = min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))
            log_msg(pair_id, f"📦 Bad data from MT: {type(e).__name__} {str(e)[:80]} — warte {backoff}s")
            time.sleep(backoff)
            continue
        except Exception as e:
            consecutive_errors += 1
            backoff = min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))
            log_msg(pair_id, f"⚠️ MT Unerwarteter Fehler: {type(e).__name__}: {str(e)[:120]} — warte {backoff}s")
            time.sleep(backoff)
            continue

        time.sleep(s.get("pollInterval", 0.5))

    http.close()
    log_msg(pair_id, "MT→TSX Mirror gestoppt")

def open_tsx_hedge(pair_id, mt_pos_id, side, contract_base, qty):
    s = mirror_sessions.get(pair_id)
    if not s: return

    contract_map = {
        "MNQ": "CON.F.US.MNQ.M26",
        "NQ":  "CON.F.US.ENQ.M26",
        "MES": "CON.F.US.MES.M26",
        "ES":  "CON.F.US.EP.M26",
        "MYM": "CON.F.US.MYM.M26",
        "YM":  "CON.F.US.YM.M26",
    }
    contract_id = contract_map.get(contract_base, f"CON.F.US.{contract_base}.M26")

    body = {
        "accountId": int(s["tsxAccountId"]),
        "contractId": contract_id,
        "type": 2,
        "side": side,
        "size": qty,
        "customTag": f"HM-MT-{mt_pos_id[:8]}"
    }

    try:
        r = requests.post(f"{TSX_BASE}/api/Order/place",
            headers={"Authorization": f"Bearer {s['tsxToken']}", "Content-Type": "application/json"},
            json=body, timeout=10)
        # Bei 401 kurz refreshen und nochmal probieren
        if r.status_code == 401:
            tmp_session = requests.Session()
            if refresh_tsx_token(pair_id, tmp_session):
                r = requests.post(f"{TSX_BASE}/api/Order/place",
                    headers={"Authorization": f"Bearer {s['tsxToken']}", "Content-Type": "application/json"},
                    json=body, timeout=10)
            tmp_session.close()
        d = r.json()
        if d.get("success") or d.get("orderId"):
            order_id = str(d.get("orderId", ""))
            s["positions"][mt_pos_id] = order_id
            log_msg(pair_id, f"✅ TSX Order: {'Sell' if side==1 else 'Buy'} {qty}x {contract_base} | orderId={order_id}")
        else:
            log_msg(pair_id, f"❌ TSX Order failed: {d.get('errorMessage', d)}")
    except Exception as e:
        log_msg(pair_id, f"❌ TSX Order error: {e}")

def close_tsx_hedge(pair_id, mt_pos_id):
    s = mirror_sessions.get(pair_id)
    if not s: return

    if mt_pos_id not in s["positions"]:
        log_msg(pair_id, f"Keine TSX Position für MT {mt_pos_id}")
        return

    try:
        r = requests.post(f"{TSX_BASE}/api/Position/searchOpen",
            headers={"Authorization": f"Bearer {s['tsxToken']}", "Content-Type": "application/json"},
            json={"accountId": int(s["tsxAccountId"])}, timeout=10)
        positions = r.json().get("positions", [])

        for pos in positions:
            pos_id = str(pos.get("id", ""))
            if pos_id in s["positions"].values():
                close_r = requests.post(f"{TSX_BASE}/api/Position/closeAll",
                    headers={"Authorization": f"Bearer {s['tsxToken']}", "Content-Type": "application/json"},
                    json={"accountId": int(s["tsxAccountId"])},
                    timeout=10)
                d = close_r.json()
                if close_r.ok or d.get("success"):
                    log_msg(pair_id, f"✅ TSX Position geschlossen")
                else:
                    log_msg(pair_id, f"❌ TSX Close: {d}")
                if mt_pos_id in s["positions"]:
                    del s["positions"][mt_pos_id]
                break
        else:
            log_msg(pair_id, f"TSX Position bereits geschlossen")
            if mt_pos_id in s["positions"]:
                del s["positions"][mt_pos_id]

    except Exception as e:
        log_msg(pair_id, f"❌ TSX Close error: {e}")

@app.route("/debug/account", methods=["POST","OPTIONS"])
def debug_account():
    if request.method == "OPTIONS": return "", 200
    token = request.headers.get("Authorization","").replace("Bearer ","")
    r = requests.post(f"{TSX_BASE}/api/Account/search",
        json={"onlyActive": True},
        headers={"Authorization": f"Bearer {token}","Content-Type":"application/json"},
        timeout=10)
    return Response(r.content, status=r.status_code, content_type="application/json")

# ════════════════════════════════════════════════════════════════════════════
# SERVER-WÄCHTER — Trade-Erkennung 24/7, unabhängig vom Browser (04.08.2026)
#
# Finns Anforderung: die drei Schritte Geplant→Läuft→Überprüfen + Auto-P&L
# müssen DURCHGEHEND laufen — auch wenn kein Prophos-Tab offen ist und egal,
# in welchem Profil er gerade eingeloggt ist. Der Browser-Wächter (mpWatch)
# war der Zwischenschritt; das hier ist die echte Lösung: dieselbe Erkennung
# als Server-Loop auf Railway.
#
# Voraussetzung: SUPABASE_SERVICE_KEY als Env-Var (NUR auf Railway setzen!
# Der lokale Mac/PC-Backend darf den Key nicht bekommen, sonst laufen zwei
# Wächter gegeneinander). Ohne Key bleibt der Wächter still inaktiv und das
# Frontend fällt automatisch auf die Browser-Erkennung zurück.
#
# Die Logik ist ein 1:1-Port von atCheck/mpWatch aus prophos.html:
#   - Baseline pro Plan (erster Blick zählt nur, triggert nie)
#   - Master-Fingerabdruck (eigene Master-Position ODER id_master auf der
#     Slave-Kopie) gegen Fehltrigger bei geteiltem Slave
#   - Close erst nach 2 Messungen IN FOLGE (Schutz gegen einzelne leere/
#     fehlerhafte Duplikum-Antworten, live beobachtet 07.07.2026)
#   - Mirror-Routen-Pläne (TopstepX-Master + MetaApi-Slave) ausgeschlossen —
#     die gehören dem lokalen Mirror, Duplikum kennt sie nicht
#   - Rate-Limit-Antworten (HTTP 200 mit error-Body statt data-Array) werden
#     als FEHLER behandelt, nie als "keine Positionen" (Lehre vom 30.07.2026)
#   - Alle Status-Writes mit Guard (status=eq.planned bzw. eq.open), damit
#     manuelle Aktionen im Frontend nie überschrieben werden
#   - P&L wird im Moment des Trade-Endes geholt und persistiert; für Review-
#     Pläne mit fehlendem P&L wird jede Runde nachversucht (max. 10x)
# ════════════════════════════════════════════════════════════════════════════
SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "https://gxhkannmzpyuepxlepta.supabase.co").rstrip("/")
SUPABASE_SERVICE_KEY = (os.environ.get("SUPABASE_SERVICE_KEY")
                        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
# 30s-Takt (07.08.2026, Finns neue Priorität: "Zeit ist mir nicht so wichtig —
# Hauptsache es funktioniert zu 100%, keine Bugs"). Bei 10 Duplikum-Konten sind
# 300 getOpenPositions/Stunde erlaubt; 30s-Takt = 120/h, also weniger als die
# Hälfte — massig Luft für Browser-Preflights, Balance-Polls und die P&L-Abfragen,
# statt permanent an der Kante zu fahren wie beim 4s-Experiment (das genau
# dadurch die Erkennung lahmlegte). Erkennungslatenz: Start ~30s, Ende ~60-90s.
# BEKANNTE GRENZE (dokumentiert, kein Bug — Review-Finding 07.08.): Ein Trade,
# der KÜRZER als ein Intervall läuft (Blitz-Scalp: auf und zu innerhalb ~30s),
# fällt komplett zwischen zwei Polls — der Plan bleibt auf "Geplant" und muss
# manuell nachgetragen werden. Bewusster Tausch gegen Zuverlässigkeit.
WATCHER_INTERVAL = max(10, int(os.environ.get("WATCHER_INTERVAL") or "30"))
WATCHER_DISABLED = bool(os.environ.get("WATCHER_DISABLED"))

_watcher_state = {}       # (uid, plan_id) -> {was_open, notified, baseline, streak, base_tickets, tickets}
_watcher_pnl_tries = {}   # (uid, plan_id) -> Anzahl P&L-Nachversuche
_watcher_backoff = {}     # EMAIL -> {"until": epoch, "fails": n} — Login-Backoff (pro Duplikum-Konto)
_watcher_meta = {}        # uid -> {"links":..., "accs":..., "at": epoch} — 60s-Cache für dup_links/accounts
_watcher_tokens = {}      # EMAIL -> {"token":..., "at": epoch} — EIN Token pro Duplikum-Konto,
                          # egal wie viele Prophos-Profile es teilen (Finn hat 2 Profile
                          # auf derselben Duplikum-E-Mail — vorher wurde doppelt gepollt
                          # und doppelt eingeloggt)
_watcher_seen = {}        # EMAIL -> set(ticket) des letzten Ticks — für die Uhr-Kalibrierung
_watcher_info = {"started": False, "last_run": 0, "runs": 0, "users": 0, "last_error": "", "cycle_ms": 0}
_watcher_thread_started = False
_watcher_memo_lock = threading.Lock()
_watcher_email_locks = {}   # email -> Lock (Single-Flight: teilen sich zwei Profile
                            # eine E-Mail, holt nur EIN Thread die Positionen)


# ── Duplikum-Rate-Budget (06.08.2026) ────────────────────────────────────────
# Duplikum limitiert PRO ENDPOINT und skaliert mit der Kontoanzahl des Duplikum-
# Kontos (offizielle Doku):
#   getOpenPositions:   min(1×n, 5)/s   min(2×n, 30)/min   min(30×n, 900)/h
#   getClosedPositions: min(1×n, 5)/s   min(2×n, 15)/min   min(30×n, 300)/h
# Finn: 10 Konten ⇒ 300 Abfragen/Stunde für getOpenPositions = eine alle 12s.
# Der 4s-Takt vom 05.08. lag mit 900/h dreifach drüber — Duplikum hat fast jeden
# Tick abgewiesen, deshalb wurden Trades „manchmal gar nicht" erkannt.
#
# Statt eines starren Intervalls ein Token-Bucket über echte Zeitfenster: solange
# Budget da ist, wird im schnellen Takt gepollt; ist es knapp, drosselt sich der
# Wächter selbst. Weil Finn stoßweise tradet (planen → ausführen → schließen,
# dazwischen Stunden Ruhe, in denen gar nicht gepollt wird), steht beim Trade
# fast immer das volle Kontingent bereit → schnelle Erkennung genau dann, wenn
# sie gebraucht wird.
DUP_ENDPOINT_LIMITS = {
    "position/getopenpositions.php":   {"sec": (1, 5), "min": (2, 30), "hour": (30, 900)},
    "position/getclosedpositions.php": {"sec": (1, 5), "min": (2, 15), "hour": (30, 300)},
}
DUP_BUDGET_HEADROOM = 0.85   # 15% Reserve für Browser-Preflights u.ä.
_dup_budget_hits = {}        # (email, path) -> [epoch, ...]
_dup_budget_block = {}       # (email, path) -> epoch, bis wann gesperrt (nach 429-artigem Fehler)
_dup_budget_lock = threading.Lock()
_dup_acct_count = {}         # email -> {"n": int, "at": epoch}


def _dup_limits_for(path, accounts):
    spec = DUP_ENDPOINT_LIMITS.get(str(path).lower())
    if not spec:
        return None
    n = max(1, int(accounts or 1))
    return {k: max(1, int(min(per * n, cap) * DUP_BUDGET_HEADROOM))
            for k, (per, cap) in spec.items()}


def _dup_budget_take(email, path, accounts):
    """True = darf senden (Zeitstempel wird gebucht). False = Budget erschöpft."""
    key = (str(email).lower(), str(path).lower())
    lim = _dup_limits_for(path, accounts)
    if not lim:
        return True
    now = time.time()
    with _dup_budget_lock:
        until = _dup_budget_block.get(key)
        if until and now < until:
            return False
        hits = _dup_budget_hits.setdefault(key, [])
        cutoff = now - 3600
        if hits and hits[0] < cutoff:
            hits[:] = [t for t in hits if t >= cutoff]
        if sum(1 for t in hits if t > now - 1) >= lim["sec"]:
            return False
        if sum(1 for t in hits if t > now - 60) >= lim["min"]:
            return False
        if len(hits) >= lim["hour"]:
            return False
        # Glättung: das Stundenkontingent anteilig über die Stunde verteilen,
        # sonst wäre es in 15 Minuten verbrannt und die restlichen 45 Minuten
        # liefe gar keine Erkennung (genau dann schließt der Trade dann).
        # 10 Konten ⇒ 255/h nutzbar ⇒ ~21 pro 5 Minuten ⇒ ein Poll alle ~14s.
        if sum(1 for t in hits if t > now - 300) >= max(2, lim["hour"] // 12):
            return False
        hits.append(now)
        return True


def _dup_budget_penalize(email, path, err):
    """Duplikum hat trotz eigener Buchführung ein Limit gemeldet (z.B. weil ein
    Browser parallel gepollt hat) → dieses Konto/Endpoint kurz sperren, statt
    weiter dagegen zu laufen. Fenster aus der Fehlermeldung abgeleitet."""
    key = (str(email).lower(), str(path).lower())
    low = str(err).lower()
    wait = 65 if "per minute" in low else (300 if "per hour" in low else 3)
    with _dup_budget_lock:
        _dup_budget_block[key] = time.time() + wait
    print(f"[watcher] ⏳ Duplikum-Limit für {email} ({path}) — pausiere {wait}s: {str(err)[:90]}", flush=True)


def _dup_budget_snapshot():
    """Nur aggregierte Zahlen (Endpoint → Polls letzte Stunde) — der Endpoint ist
    unauthentifiziert, also bewusst keine E-Mails nach außen."""
    now = time.time()
    out = {}
    with _dup_budget_lock:
        for (_email, path), hits in _dup_budget_hits.items():
            out[path] = out.get(path, 0) + sum(1 for t in hits if t > now - 3600)
    return out


def wt_account_count(email, token):
    """Anzahl Trading-Konten dieses Duplikum-Kontos — bestimmt die Rate-Limits.
    Einmal pro Stunde abgefragt (eigener Endpoint, eigenes Budget)."""
    e = str(email).lower()
    hit = _dup_acct_count.get(e)
    if hit and (time.time() - hit["at"]) < 3600:
        return hit["n"]
    # Bewusst KLEINER Default (Review-Finding): mit einem zu großen Wert wäre das
    # Budget zu großzügig und wir liefen dauerhaft in Duplikums echtes Limit —
    # genau der Zustand, der heute die Erkennung lahmgelegt hat. Lieber zu langsam
    # als blind. Und ein fehlgeschlagener Abruf wird NICHT eine Stunde gecacht.
    n, ok = 3, False
    try:
        r = requests.post(f"{DUP_BASE}/account/getAccounts.php", data={"length": "1000"},
                          headers={"Authorization": f"Bearer {token}"}, timeout=15)
        d = r.json() if r.status_code == 200 else {}
        if isinstance(d, dict) and isinstance(d.get("data"), list):
            n, ok = max(1, len(d["data"])), True
    except Exception:
        pass
    if ok:
        _dup_acct_count[e] = {"n": n, "at": time.time()}
    else:
        # Kurz zwischenspeichern, damit nicht jeder Tick erneut anfragt, aber bald
        # wieder versuchen (statt eine Stunde mit dem Default zu rechnen).
        _dup_acct_count[e] = {"n": (hit or {}).get("n", n), "at": time.time() - 3300}
    return _dup_acct_count[e]["n"]


def _wt_email_lock(email):
    with _watcher_memo_lock:
        lk = _watcher_email_locks.get(email)
        if lk is None:
            # RLock: wt_email_token lockt selbst und wird auch aus bereits
            # gelocktem Kontext (_wt_memo_positions_locked) gerufen — ein
            # normales Lock wäre dort ein Deadlock.
            lk = threading.RLock()
            _watcher_email_locks[email] = lk
        return lk
# Duplikums Zeitstempel (openTime/closeTime) kommen OHNE Zeitzone. Der Offset zur
# echten UTC wird zur Laufzeit kalibriert: wenn der Wächter einen Trade-START erkennt,
# ist die neue Position höchstens ~2 Ticks alt → parse(openTime) − jetzt ≈ Offset.
# Solange unkalibriert, rechnen Vergleiche mit großzügiger Toleranz.
_dup_clock = {"offset": None}   # Sekunden: naiver Duplikum-Zeitstempel − echte UTC


def _sb_headers(prefer=None):
    h = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def sb_select(table, params):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", params=params,
                     headers=_sb_headers(), timeout=12)
    r.raise_for_status()
    return r.json()


def sb_update(table, params, body):
    """PATCH mit return=representation → Liste der WIRKLICH geänderten Zeilen.
    Leere Liste = Guard hat gegriffen (z.B. Status wurde inzwischen manuell
    geändert) — das ist ein normales Ergebnis, kein Fehler."""
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}", params=params, json=body,
                       headers=_sb_headers("return=representation"), timeout=12)
    r.raise_for_status()
    return r.json()


def dup_login(email, password):
    """Duplikum-Login → Token oder None.

    SICHERHEIT (Review-Finding 04.08.2026): Der Wächter darf duplikum_sessions
    NICHT befüllen. Der unauthentifizierte Proxy /duplikum/<path> nutzt diesen
    Cache für seinen 401-Auto-Refresh — würde der Wächter dort die Passwörter
    ALLER User ablegen, könnte jeder, der nur die E-Mail kennt, sich über den
    Proxy frische Tokens für fremde Duplikum-Konten ausstellen lassen."""
    if not email or not password:
        return None
    try:
        r = requests.post(f"{DUP_BASE}/access/getToken.php", auth=(email, password), timeout=15)
        token = None
        try:
            d = r.json()
            if isinstance(d, dict):
                token = d.get("token") or d.get("access_token") or (d.get("data") or {}).get("token")
            elif isinstance(d, str):
                token = d
        except Exception:
            txt = (r.text or "").strip().strip('"')
            if txt and len(txt) < 2000 and " " not in txt:
                token = txt
        if r.ok and token:
            return token
    except Exception as e:
        print(f"[watcher] ⚠️ Duplikum-Login {email}: {e}", flush=True)
    return None


def _wt_now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _wt_parse_ts(s):
    """'YYYY-MM-DD HH:MM:SS' (oder ISO) → naiver Epoch (als wäre der String UTC).
    Für ECHTE UTC noch _dup_clock['offset'] abziehen (falls kalibriert)."""
    try:
        return calendar.timegm(time.strptime(str(s)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return None


def _wt_calibrate_clock(slave_pos, trade_tickets):
    """Uhr-Kalibrierung: Beim erkannten Trade-START ist die neue Position höchstens
    ~1-2 Ticks alt → parse(openTime) − jetzt ≈ Offset der Duplikum-Zeitstempel zu UTC.
    Damit werden closeTime-Vergleiche zeitzonen-sicher (Toleranz 15min statt 3h)."""
    try:
        tset = {str(t) for t in (trade_tickets or [])}
        for p in slave_pos:
            if tset and str(p.get("ticket")) not in tset:
                continue
            ot = _wt_parse_ts(p.get("openTime"))
            if ot is None:
                continue
            off = ot - time.time()
            if abs(off) < 26 * 3600:
                _dup_clock["offset"] = off
                break
    except Exception:
        pass


def _dup_token_exp(token):
    """exp-Claim aus dem Duplikum-JWT (Epoch) oder None, wenn nicht lesbar."""
    try:
        payload = str(token).split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return int(json.loads(base64.urlsafe_b64decode(payload)).get("exp"))
    except Exception:
        return None


def _dup_token_alive(token, margin=1800):
    """Token noch mindestens `margin` Sekunden gültig? Unlesbare Tokens gelten
    als lebendig (dann greift die Altersheuristik bzw. die 1006-Erkennung)."""
    exp = _dup_token_exp(token)
    return True if exp is None else (exp - time.time()) > margin


def _dup_is_expired_token(err_text, code=None):
    """Duplikum meldet einen abgelaufenen Token als HTTP **200** mit
    {"code":"1006","error":"Token Expired - please generate a new token ..."} —
    NICHT als 401. Ohne diese Erkennung lief der Wächter am 06.08.2026 zwei
    Stunden blind weiter: jeder Tick wurde als 'Fehlerantwort' übersprungen, ein
    Re-Login wurde nie ausgelöst (die 40h-Altersheuristik greift erst später)."""
    t = str(err_text or "").lower()
    return str(code) == "1006" or ("token" in t and ("expired" in t or "invalid" in t))


def wt_dup_positions(token, path, email=None, accounts=None):
    """Positionsliste holen. Rückgabe: list | '401' | 'budget' | None.
      list      → Daten (auch [] = legitim keine Positionen)
      '401'     → Token tot (HTTP 401 ODER Duplikums 200/1006) → Aufrufer muss neu einloggen
      'budget'  → eigenes Rate-Budget erschöpft, GAR NICHT gesendet
      None      → sonstiger Fehler (Netz, Rate-Limit von Duplikum, kaputtes JSON)
                  → Tick überspringen, niemals als 'leer' interpretieren."""
    if email and not _dup_budget_take(email, path, accounts):
        return "budget"
    try:
        r = requests.post(f"{DUP_BASE}/{path}", data={"length": "1000"},
                          headers={"Authorization": f"Bearer {token}"}, timeout=15)
    except requests.exceptions.RequestException:
        return None
    if r.status_code == 401:
        return "401"
    if r.status_code != 200:
        return None
    try:
        d = r.json()
    except Exception:
        return None
    if isinstance(d, dict):
        if isinstance(d.get("data"), list):
            return d["data"]
        # Token-Ablauf ZUERST prüfen, unabhängig vom error-Feld: käme ein Body nur
        # mit code 1006 (ohne error-Text), würde er sonst unten als "legitim leer"
        # gelesen — also als "keine offenen Positionen" und damit als Trade-Ende
        # für ALLE laufenden Pläne. Genau die 07.07.-Fehlalarm-Klasse.
        if _dup_is_expired_token(d.get("error"), d.get("code")):
            return "401"
        if d.get("error"):
            # Rate-Limit ("You reached the request limit (574/300 per hour)") u.ä.
            # kommen ebenfalls als HTTP 200 mit error-Body.
            if email and "request limit" in str(d.get("error")).lower():
                _dup_budget_penalize(email, path, str(d.get("error")))
            return None
        # Sicherheitsnetz: ein Body ohne data-Liste UND ohne error ist laut Doku
        # eine leere Ergebnismenge — aber nur, wenn er auch sonst wie eine Antwort
        # aussieht. Alles andere (z.B. unbekannte Fehlercodes) lieber überspringen.
        if d.get("code") not in (None, "", "200", 200):
            return None
        return []
    return None


def wt_email_token(creds, force=False):
    """EIN Duplikum-Token pro Konto (E-Mail), egal wie viele Prophos-Profile es
    teilen. Reihenfolge: In-Memory-Cache (<30min) → DB-Token (<40h) → Login.

    Zwei Review-Findings (05.08.2026) sind hier eingebaut:
    - Der frische Token wird NUR in die EIGENE Zeile (user_id) zurückgeschrieben.
      Ein email=eq.-Writeback wäre ein Token-Leck: jeder, der eine Zeile mit
      fremder E-Mail (und falschem Passwort) anlegt, bekäme den echten Token des
      fremden Kontos in seine per RLS lesbare Zeile gestellt.
    - Der Backoff ist pro (E-Mail, Passwort-Hash): eine verwaiste Zeile mit
      altem Passwort darf das Konto nicht für die Zeile mit dem RICHTIGEN
      Passwort sperren.
    Login + Backoff laufen unter dem E-Mail-RLock — parallele 401s zweier
    Profile derselben E-Mail führen so zu EINEM Login, der zweite Thread nimmt
    den gerade frisch geholten Cache-Token."""
    email = (creds.get("email") or "").strip().lower()
    if not email:
        return None
    hit = _watcher_tokens.get(email)
    if not force and hit and (time.time() - hit["at"]) < 30 * 60 and _dup_token_alive(hit["token"]):
        return hit["token"]
    if not force:
        tok, tok_at = creds.get("token"), creds.get("token_at")
        # Der Token sagt SELBST, wann er abläuft (JWT-exp) — das schlägt jede
        # Altersheuristik. Die 40h-Regel bleibt als Fallback für den Fall, dass
        # der Token mal kein lesbares JWT ist.
        if tok and _dup_token_alive(tok):
            _watcher_tokens[email] = {"token": tok, "at": time.time()}
            return tok
        if tok and tok_at and _dup_token_exp(tok) is None:
            try:
                # token_at ist UTC → timegm, nicht mktime (das würde lokal interpretieren)
                age_h = (time.time() - calendar.timegm(time.strptime(tok_at[:19], "%Y-%m-%dT%H:%M:%S"))) / 3600.0
            except Exception:
                age_h = 9999
            if age_h < 40:
                _watcher_tokens[email] = {"token": tok, "at": time.time()}
                return tok
    with _wt_email_lock(email):
        # Hat ein paralleler Thread GERADE eben frisch eingeloggt (z.B. beide
        # Profile kassieren gleichzeitig 401)? → dessen Token nehmen.
        hit = _watcher_tokens.get(email)
        if hit and (time.time() - hit["at"]) < 10:
            return hit["token"]
        pw = creds.get("password") or ""
        bo_key = email + "|" + hashlib.md5(pw.encode()).hexdigest()[:10]
        bo = _watcher_backoff.get(bo_key)
        if bo and time.time() < bo["until"]:
            return None
        token = dup_login(email, pw)
        if token:
            _watcher_backoff.pop(bo_key, None)
            _watcher_tokens[email] = {"token": token, "at": time.time()}
            uid = creds.get("user_id")
            if uid:
                try:
                    sb_update("duplikum_credentials", {"user_id": f"eq.{uid}"},
                              {"token": token, "token_at": _wt_now_iso()})
                except Exception:
                    pass
            print(f"[watcher] 🔑 Neuer Duplikum-Token für {email}", flush=True)
        else:
            fails = (bo["fails"] + 1) if bo else 1
            wait = min(3600, 300 * (2 ** (fails - 1)))
            _watcher_backoff[bo_key] = {"until": time.time() + wait, "fails": fails}
            print(f"[watcher] ⚠️ Login fehlgeschlagen für {email} — Backoff {wait//60}min (Versuch {fails})", flush=True)
        return token


def wt_memo_positions(creds, memo):
    """Offene Positionen EINMAL pro Duplikum-Konto und Zyklus — alle Profile
    derselben E-Mail teilen sich das Ergebnis (halbiert die Duplikum-Last bei
    geteilten Konten). Thread-sicher über _watcher_memo_lock, inkl. 401-Refresh
    und EINEM Sofort-Retry bei Fehlerantwort (Rate-Limit-als-200) — vorher ging
    dadurch der komplette Tick verloren und die Erkennung wurde spürbar träger.
    Rückgabe (token, positions|None)."""
    email = (creds.get("email") or "").strip().lower()
    with _watcher_memo_lock:
        if email in memo:
            return memo[email]
    lock = _wt_email_lock(email)
    with lock:
        return _wt_memo_positions_locked(email, creds, memo)


def _wt_memo_positions_locked(email, creds, memo):
    # Re-Check unter dem E-Mail-Lock: ein paralleles Profil derselben E-Mail hat
    # das Ergebnis evtl. gerade eben schon geholt (Single-Flight).
    with _watcher_memo_lock:
        if email in memo:
            return memo[email]
    token = wt_email_token(creds)
    if not token:
        with _watcher_memo_lock:
            memo[email] = (None, None)
        return None, None
    n_acc = wt_account_count(email, token)
    positions = None
    for attempt in range(2):
        res = wt_dup_positions(token, "position/getOpenPositions.php", email, n_acc)
        if res == "budget":
            break            # bewusst kein Retry — Budget ist Budget
        if res == "401":
            token = wt_email_token(creds, force=True)
            if not token:
                break
            continue
        if isinstance(res, list):
            positions = res
            break
        time.sleep(0.7)   # Fehlerantwort → kurz warten, einmal sofort nachfassen
    # Uhr-Kalibrierung: Tickets, die es im LETZTEN Tick noch nicht gab, sind
    # höchstens Sekunden alt → openTime − jetzt ≈ Duplikums Uhr-Offset zu UTC.
    # Drei Gates gegen Vergiftung (Review-Findings 05.08.2026):
    # 1. Der Vergleichs-Snapshot muss FRISCH sein (≤ 3 Ticks) — nach einer Poll-
    #    Pause (nachts keine Pläne) ist "neu" bedeutungslos, ein 10h altes Ticket
    #    hätte den globalen Offset sonst um -10h verschoben.
    # 2. Erst-Kalibrierung nur gegen einen NICHT-leeren Snapshot — eine einzelne
    #    Leer-Antwort (07.07.-Klasse) lässt sonst alle Alt-Tickets "neu" aussehen.
    # 3. Ist die Uhr schon kalibriert, werden neue Werte nur bei < 10min Abweichung
    #    übernommen (der echte Offset ist eine Konstante — alles andere ist Müll).
    if isinstance(positions, list):
        try:
            cur = {str(p.get("ticket")) for p in positions if p.get("ticket") is not None}
            prev = _watcher_seen.get(email)
            fresh_prev = prev is not None and (time.time() - prev["at"]) <= WATCHER_INTERVAL * 3
            if fresh_prev and (prev["tickets"] or _dup_clock["offset"] is not None):
                for p in positions:
                    t = str(p.get("ticket"))
                    if p.get("ticket") is None or t in prev["tickets"]:
                        continue
                    ot = _wt_parse_ts(p.get("openTime"))
                    if ot is None:
                        continue
                    off = ot - time.time()
                    if abs(off) >= 26 * 3600:
                        continue
                    cur_off = _dup_clock["offset"]
                    if cur_off is None or abs(off - cur_off) < 600:
                        _dup_clock["offset"] = off
                    break
            _watcher_seen[email] = {"tickets": cur, "at": time.time()}
        except Exception:
            pass
    with _watcher_memo_lock:
        memo[email] = (token, positions)
    return token, positions


def wt_fetch_pnl(token, dup_slave, dup_master, started_epoch=None, tickets=None,
                 email=None, accounts=None):
    """P&L der zu DIESEM Plan gehörenden geschlossenen Position.

    Rückgabe (status, pnl):
      ('ok',  {master, slave})  Treffer
      ('none', None)            Liste kam, aber (noch) kein passender Kandidat → Retry
      ('401', None)             Token tot → Aufrufer refresht, Versuch zählt nicht
      ('err', None)             Netz/Rate-Limit → Versuch zählt nicht

    Zuordnung — SEIT 07.08.2026 AUSSCHLIESSLICH ÜBER TICKET-BEWEIS (Finns
    Priorität: "lieber langsamer/leer als eine falsche Zahl"):
    `tickets` sind die beim Trade beobachteten MASTER-Tickets; die Slave-Kopie
    trägt exakt diese Nummer in `masterTicket` (live verifiziert 06.08.2026).
    Kein Treffer ⇒ ('none', None) — das Feld bleibt dann bewusst leer und Finn
    trägt selbst ein. Der frühere Zeitfenster-Fallback (closeTime vs. started_at
    mit kalibrierter Duplikum-Uhr) ist RAUS: er war der letzte Pfad, der raten
    konnte, und Zeitzonen-Annahmen haben hier schon einmal Geld-Zahlen
    verfälscht. Ein leeres Feld sieht man — eine plausible falsche Zahl nicht."""
    # Ohne gemerkte Tickets gibt es nichts sicher zuzuordnen — dann auch keinen
    # API-Call verschwenden. Betrifft ALLE Pläne ohne überlebenden Ticket-Beweis
    # (Review-Finding 07.08.): kompletter Lebenszyklus in einer Downtime, vom
    # Frontend ohne Wächter-Beobachtung verschoben, oder Start beobachtet aber
    # Deploy löschte den RAM-State und der Close fiel in die Restart-Lücke.
    # Gegen Letzteres hilft die persistierte trade_plans.watch_tickets-Spalte
    # (Migration 2026-08-07) — die Aufrufer reichen sie als Fallback herein.
    ticket_set = {str(t) for t in (tickets or []) if t is not None}
    if not ticket_set:
        return "none", None
    lst = wt_dup_positions(token, "position/getClosedPositions.php", email, accounts)
    if lst == "401":
        return "401", None
    if not isinstance(lst, list):
        return "err", None   # inkl. 'budget' → Versuch zählt nicht, nächste Runde erneut
    if not lst:
        return "none", None
    cands = [p for p in lst
             if str(p.get("account_id")) == str(dup_slave)
             and (not dup_master or str(p.get("master_id")) == str(dup_master))]
    if not cands:
        return "none", None

    # `tickets` sind die beobachteten MASTER-Tickets; die Slave-Kopie trägt genau
    # diese Nummer in `masterTicket` (live verifiziert 06.08.2026: Slave 205666039
    # ↔ masterTicket 258231486). `ticket` wird zusätzlich geprüft, falls der
    # Fallback-Pfad (Master nicht verknüpft) Slave-Tickets gemerkt hat.
    hits = [p for p in cands
            if str(p.get("masterTicket")) in ticket_set or str(p.get("ticket")) in ticket_set]
    if not hits:
        return "none", None
    hits.sort(key=lambda p: str(p.get("closeTime") or ""), reverse=True)
    sp = hits[0]

    slave_pnl = None
    if sp.get("profitCcy") not in (None, ""):
        try:
            slave_pnl = float(sp["profitCcy"])
        except (TypeError, ValueError):
            slave_pnl = None
    master_pnl = None
    if sp.get("masterTicket") is not None:
        mts = str(sp["masterTicket"])
        mp = next((p for p in lst if str(p.get("account_id")) == str(dup_master)
                   and str(p.get("ticket")) == mts), None) \
             or next((p for p in lst if str(p.get("ticket")) == mts
                      and str(p.get("account_id")) != str(dup_slave)), None)
        if mp and mp.get("profitCcy") not in (None, ""):
            try:
                master_pnl = float(mp["profitCcy"])
            except (TypeError, ValueError):
                master_pnl = None
    if slave_pnl is None and master_pnl is None:
        return "none", None
    return "ok", {"master": master_pnl, "slave": slave_pnl}


def wt_write_pnl(uid, plan, pnl):
    """Nur LEERE P&L-Felder füllen, nur solange der Plan in 'review' steht —
    manuell eingetragene oder bestätigte Werte werden nie angefasst."""
    upd = {}
    if pnl.get("master") is not None and plan.get("master_pl") is None:
        upd["master_pl"] = round(pnl["master"], 2)
    if pnl.get("slave") is not None and plan.get("slave_pl") is None:
        upd["slave_pl"] = round(pnl["slave"], 2)
    if not upd:
        return False
    rows = sb_update("trade_plans",
                     {"id": f"eq.{plan['id']}", "status": "eq.review", "user_id": f"eq.{uid}"},
                     upd)
    return bool(rows)


def wt_save_tickets(uid, plan_id, tickets):
    """Master-Tickets best-effort am Plan persistieren (trade_plans.watch_tickets,
    Migration 2026-08-07). Damit überlebt der P&L-Beweis Deploys/Restarts.
    Fehlt die Spalte noch, scheitert das leise — alles läuft wie bisher, nur
    ohne Restart-Schutz. Bewusst ein SEPARATER Update: hinge das am Status-
    Übergang, würde eine fehlende Spalte die Erkennung selbst blockieren."""
    if not tickets:
        return
    try:
        sb_update("trade_plans", {"id": f"eq.{plan_id}", "user_id": f"eq.{uid}"},
                  {"watch_tickets": [str(t) for t in tickets]})
    except Exception:
        pass


def _plan_tickets(plan, state_tickets):
    """Ticket-Beweis auflösen: RAM-State zuerst, sonst die persistierte Spalte."""
    if state_tickets:
        return state_tickets
    wt = plan.get("watch_tickets")
    if isinstance(wt, list):
        return [str(t) for t in wt if t is not None]
    return None


def wt_finish_plan(uid, token, plan, dup_slave, dup_master, label, started_epoch=None, tickets=None,
                   email=None, accounts=None, pnl_ready=None):
    """open → review + sofortiger P&L-Fetch. True = Plan ist versorgt.
    pnl_ready: bereits ermittelter P&L (Sofort-Bestätigung per Ticket-Treffer) —
    dann entfällt die zweite Abfrage komplett."""
    try:
        rows = sb_update("trade_plans",
                         {"id": f"eq.{plan['id']}", "status": "eq.open", "user_id": f"eq.{uid}"},
                         {"status": "review"})
    except Exception as e:
        print(f"[watcher] ⚠️ {label}: review-Update fehlgeschlagen: {e}", flush=True)
        return False   # nächster Tick probiert es erneut
    if not rows:
        # Guard hat gegriffen — jemand hat den Plan manuell abgeschlossen. Erledigt.
        return True
    print(f"[watcher] 🔴 {label}: Trade beendet → Überprüfen ({plan.get('master_name') or '—'} → {plan.get('slave_name') or '—'})", flush=True)
    if pnl_ready:
        try:
            wt_write_pnl(uid, plan, pnl_ready)
            print(f"[watcher] 💰 {label}: Auto-P&L persistiert (master={pnl_ready.get('master')}, slave={pnl_ready.get('slave')})", flush=True)
        except Exception as e:
            print(f"[watcher] ⚠️ {label}: P&L-Write: {e}", flush=True)
            _watcher_pnl_tries[(uid, str(plan["id"]))] = 0
        return True
    time.sleep(1.0)   # Duplikum liefert die geschlossene Position leicht verzögert
    try:
        st, pnl = wt_fetch_pnl(token, dup_slave, dup_master, started_epoch, tickets, email, accounts)
        if st == "ok" and pnl:
            wt_write_pnl(uid, plan, pnl)
            print(f"[watcher] 💰 {label}: Auto-P&L persistiert (master={pnl.get('master')}, slave={pnl.get('slave')})", flush=True)
        else:
            # Noch nicht in getClosedPositions (oder Fehler) → Nachversuch-Zähler
            # startet, die Review-Retry-Schleife holt es in den nächsten Runden nach.
            _watcher_pnl_tries[(uid, str(plan["id"]))] = 0
    except Exception as e:
        print(f"[watcher] ⚠️ {label}: P&L-Fetch: {e}", flush=True)
        _watcher_pnl_tries[(uid, str(plan["id"]))] = 0
    return True


def wt_check_user(uid, creds, memo):
    label = (creds.get("email") or uid)[:24]
    plans = sb_select("trade_plans", {
        "select": "*",
        "user_id": f"eq.{uid}",
        "status": "in.(planned,open,review)",
    })
    # MT5-Route (15.08.2026): Pläne mit route='mt5' laufen über den lokalen MT5-Copier,
    # nicht über Duplikum — die gehören der Browser-Zustandsmaschine (mt5PlanPoll in
    # prophos.html). Filter DIREKT nach dem Select, damit weder die Erkennung unten
    # noch die review-P&L-Nachversuche (wt_fetch_pnl) solche Pläne anfassen — der
    # Nachversuchs-Loop würde sonst MT5-Pläne mit fremden Duplikum-Closes bestempeln.
    plans = [p for p in plans if (p.get("route") or "") != "mt5"]
    active = [p for p in plans if p.get("status") in ("planned", "open")]
    review_missing = [p for p in plans if p.get("status") == "review"
                      and (p.get("master_pl") is None or p.get("slave_pl") is None)]

    # State-Hygiene: Einträge zu Plänen, die nicht mehr aktiv/review sind, entsorgen.
    # list()-Snapshot vor der Iteration (Review-Finding): parallele Threads fügen
    # gleichzeitig Keys ein — Iteration über das lebende Dict wirft dann
    # "dictionary changed size during iteration".
    live_ids = {str(p["id"]) for p in plans}
    for k in [k for k in list(_watcher_state) if k[0] == uid and k[1] not in live_ids]:
        _watcher_state.pop(k, None)
    for k in [k for k in list(_watcher_pnl_tries) if k[0] == uid and k[1] not in live_ids]:
        _watcher_pnl_tries.pop(k, None)

    if not active and not review_missing:
        return

    # Verknüpfungen (dup_links) + Accounts (Mirror-Ausschluss) — 60s-Cache: ändern
    # sich selten, und im 4s-Takt wären das sonst 2 unnötige Supabase-Queries pro
    # User und Tick.
    def _load_meta():
        us = sb_select("user_settings", {"select": "value", "user_id": f"eq.{uid}", "key": "eq.dup_links"})
        lv = us[0].get("value") if us else None
        if isinstance(lv, str):
            try:
                lv = json.loads(lv)
            except Exception:
                lv = None
        accs = sb_select("accounts", {"select": "id,topstep_account_id,meta_api_account_id",
                                      "user_id": f"eq.{uid}"})
        m = {"links": lv if isinstance(lv, dict) else None,
             "accs": {str(a["id"]): a for a in accs}, "at": time.time()}
        _watcher_meta[uid] = m
        return m

    meta = _watcher_meta.get(uid)
    if not meta or (time.time() - meta["at"]) > 60:
        meta = _load_meta()
    # Frisch verknüpft? Hängt ein aktiver Plan an einem Slave ohne Link, kann der
    # Cache schuld sein → einmal sofort neu laden statt bis zu 60s blind zu sein.
    def _slave_unlinked(m):
        lv = m["links"] or {}
        mapped = {str(v) for v in lv.values()}
        return any(str(p.get("slave_account_id")) not in mapped for p in active)
    if active and (time.time() - meta["at"]) > 5 and _slave_unlinked(meta):
        meta = _load_meta()
    links = meta["links"]
    if not links:
        return
    acc_by_id = meta["accs"]

    def dup_id_of(acc_id):
        for dup_id, mapped in links.items():
            if str(mapped) == str(acc_id):
                return dup_id
        return None

    def is_mirror(p):
        m = acc_by_id.get(str(p.get("master_account_id")))
        s = acc_by_id.get(str(p.get("slave_account_id")))
        return bool(m and s and m.get("topstep_account_id") and s.get("meta_api_account_id"))

    # EIN Token + EIN Positions-Fetch pro Duplikum-Konto und Zyklus (memo) —
    # Profile mit derselben E-Mail teilen sich beides.
    token, positions = wt_memo_positions(creds, memo)
    if not token:
        return
    dup_email = (creds.get("email") or "").strip().lower()
    n_acc = wt_account_count(dup_email, token)

    def started_epoch_of(plan):
        return _wt_parse_ts(plan.get("started_at"))   # started_at ist UTC-ISO → timegm passt

    # ── P&L-Nachversuche für Review-Pläne (z.B. Position war noch nicht in
    # getClosedPositions, oder das Frontend hat nach review verschoben ohne P&L) ──
    for plan in review_missing:
        if is_mirror(plan):
            continue
        d_slave = dup_id_of(plan.get("slave_account_id"))
        if not d_slave:
            continue
        se = started_epoch_of(plan)
        # Zeitfenster (Review-Finding): nur junge Pläne nachversorgen. Der Zähler ist
        # In-Memory und wird bei jedem Deploy zurückgesetzt — ohne absolute Grenze
        # bekämen tagelang hängende Review-Pläne irgendwann den P&L eines SPÄTEREN
        # Trades desselben Paars eingestempelt.
        if not se or (time.time() - se) > 6 * 3600:
            continue
        key = (uid, str(plan["id"]))
        tries = _watcher_pnl_tries.get(key, 0)
        if tries >= 10:
            continue
        try:
            st, pnl = wt_fetch_pnl(token, d_slave, dup_id_of(plan.get("master_account_id")),
                                   se, _plan_tickets(plan, (_watcher_state.get(key) or {}).get("tickets")),
                                   dup_email, n_acc)
            if st == "401":
                token = wt_email_token(creds, force=True)
                if not token:
                    return
                continue   # Versuch zählt nicht — nächste Runde mit frischem Token
            if st == "err":
                continue   # Netz/Rate-Limit — Versuch zählt nicht
            _watcher_pnl_tries[key] = tries + 1
            if st == "ok" and pnl and wt_write_pnl(uid, plan, pnl):
                print(f"[watcher] 💰 {label}: P&L nachgetragen für Plan {plan['id']}", flush=True)
                _watcher_pnl_tries[key] = 10   # fertig
        except Exception as e:
            print(f"[watcher] ⚠️ {label}: P&L-Retry: {e}", flush=True)

    if not active:
        return

    dup_active = [p for p in active if not is_mirror(p)]
    if not dup_active:
        return

    if not isinstance(positions, list):
        return   # fehlerhafte Antwort trotz Retry → Tick überspringen, Streaks bleiben stehen

    # Wie viele AKTIVE Pläne (planned UND open — Review-Finding: ein offener Plan
    # auf demselben Paar macht die Ticket-Zuordnung mehrdeutig) teilen sich dasselbe
    # Master→Slave-Paar? Nur bei eindeutigem Paar darf sofort/nachträglich gestartet
    # werden.
    pair_counts = {}
    for p in dup_active:
        pk = (str(p.get("master_account_id")), str(p.get("slave_account_id")))
        pair_counts[pk] = pair_counts.get(pk, 0) + 1

    for plan in dup_active:
        d_slave = dup_id_of(plan.get("slave_account_id"))
        d_master = dup_id_of(plan.get("master_account_id"))
        if not d_slave:
            continue
        slave_pos = [p for p in positions if str(p.get("account_id")) == str(d_slave)]
        count = len(slave_pos)
        # ── Master-eigene Position ist das EINZIG verlässliche Per-Trade-Signal ──
        # Live verifiziert am 06.08.2026: Duplikum stempelt auf OFFENEN Slave-Kopien
        # NICHT den auslösenden Master (master_id == account_id == Slave). Erst bei
        # GESCHLOSSENEN Positionen steht der echte Master drin. Auf Finns Setup —
        # ein gemeinsamer Fusion-Live-Slave für ALLE Master, dazu dauerhaft offene
        # Alt-Positionen darauf — ist die Slave-Positionszahl damit als Signal
        # wertlos: sie ist immer > 0 und ändert sich durch fremde Master.
        # Deshalb: bei verknüpftem Master zählt ausschließlich dessen EIGENE offene
        # Position (Duplikum meldet die zuverlässig, auch für Tradovate-Master).
        master_pos = [p for p in positions if str(p.get("account_id")) == str(d_master)] if d_master else []
        master_ok = bool(master_pos)
        # Tickets des Master-Trades — über masterTicket lässt sich die Slave-Kopie
        # später in den geschlossenen Positionen exakt wiederfinden.
        master_tickets = [str(p.get("ticket")) for p in master_pos if p.get("ticket") is not None]
        all_tickets = [str(p.get("ticket")) for p in slave_pos if p.get("ticket") is not None]
        # has_open/was_open ebenfalls auf den Master beziehen, sobald er verknüpft
        # ist. Vorher hingen sie an der Slave-Zahl — bei dauerhaft offenen Alt-
        # Positionen war was_open sofort true, und zusammen mit "closed = kein
        # Master-Fingerabdruck" hätte ein manuell auf 'Läuft' gesetzter Plan nach
        # ~12s fälschlich 'beendet' gemeldet.
        has_open = master_ok if d_master else (count > 0)

        key = (uid, str(plan["id"]))
        prev = _watcher_state.get(key) or {"was_open": False, "notified": False, "baseline": None, "streak": 0}

        if plan["status"] == "planned":
            if d_master:
                # ── EINFACHE, ROBUSTE REGEL (10.08.2026) ──
                # Finns Realität: jeder Master fährt IMMER nur EINE Order gleichzeitig.
                # Also: hat der verknüpfte Master jetzt eine offene Position, IST das
                # der Trade dieses Plans → sofort auf "Läuft" und die Master-Tickets
                # merken. Fertig.
                #
                # Die frühere Baseline-/Uhr-/Frische-Mechanik ist RAUS. Sie sollte
                # Alt-Positionen ausschließen, hat aber genau das Gegenteil bewirkt:
                # Ging der In-Memory-State verloren (jeder Deploy, jeder Token-Hänger)
                # und die Position war beim ersten neuen Blick schon offen, wartete
                # der Plan ewig auf eine "nächste" Position, die bei 1-Order-pro-Master
                # nie kommt → Plan blieb dauerhaft auf "Geplant" (live nachgewiesen
                # 10.08.: FundedNext-Plan seit 11:22 haengend, Master handelte). Der
                # neue Weg heilt sich nach jedem State-Verlust beim naechsten Tick.
                if not master_ok:
                    _watcher_state[key] = {"was_open": False, "notified": False,
                                           "baseline": 0, "streak": 0}
                    continue
                # Mehrere aktive Pläne auf demselben Master→Slave-Paar? Dann ist nicht
                # eindeutig, welcher startet → nicht automatisch, einmal loggen.
                pk = (str(plan.get("master_account_id")), str(plan.get("slave_account_id")))
                if pair_counts.get(pk, 0) > 1:
                    if not prev.get("ambig_logged"):
                        print(f"[watcher] ⚠️ {label}: {pair_counts[pk]} aktive Pläne auf demselben Paar — "
                              f"Auto-Start ausgesetzt, bitte manuell auf 'Läuft' setzen (Plan {plan['id']})", flush=True)
                    _watcher_state[key] = {**prev, "was_open": False, "ambig_logged": True,
                                           "baseline": 1}
                    continue
                try:
                    rows = sb_update("trade_plans",
                                     {"id": f"eq.{plan['id']}", "status": "eq.planned", "user_id": f"eq.{uid}"},
                                     {"status": "open", "started_at": _wt_now_iso()})
                except Exception as e:
                    print(f"[watcher] ⚠️ {label}: Start-Update: {e} — nächster Tick versucht erneut", flush=True)
                    continue
                _watcher_state[key] = {"was_open": True, "notified": False, "baseline": 1,
                                       "streak": 0, "tickets": master_tickets}
                wt_save_tickets(uid, plan["id"], master_tickets)
                if rows:
                    print(f"[watcher] ▶ {label}: Trade gestartet ({plan.get('master_name') or '—'} → {plan.get('slave_name') or '—'})", flush=True)
                continue

            # ── Master NICHT verknüpft: alter Slave-Zählwerk-Fallback ──
            if prev["baseline"] is None:
                _watcher_state[key] = {**prev, "was_open": has_open, "baseline": count,
                                       "base_tickets": all_tickets}
                continue
            if count <= prev["baseline"]:
                _watcher_state[key] = {**prev, "was_open": has_open}
                continue
            base_set = set(prev.get("base_tickets") or [])
            trade_tickets = [t for t in all_tickets if t not in base_set]
            try:
                rows = sb_update("trade_plans",
                                 {"id": f"eq.{plan['id']}", "status": "eq.planned", "user_id": f"eq.{uid}"},
                                 {"status": "open", "started_at": _wt_now_iso()})
            except Exception as e:
                print(f"[watcher] ⚠️ {label}: Start-Update: {e} — nächster Tick versucht erneut", flush=True)
                continue
            _wt_calibrate_clock(slave_pos, trade_tickets)
            _watcher_state[key] = {"was_open": True, "notified": False, "baseline": count,
                                   "streak": 0, "tickets": trade_tickets}
            wt_save_tickets(uid, plan["id"], trade_tickets)
            if rows:
                print(f"[watcher] ▶ {label}: Trade gestartet ({plan.get('master_name') or '—'} → {plan.get('slave_name') or '—'})", flush=True)
            continue

        # status == 'open'
        if prev["baseline"] is None:
            # Re-Init nach Deploy/Restart: persistierte Tickets (watch_tickets) haben
            # Vorrang — sie stammen vom echten Start. Gibt es keine und der Master
            # hat GENAU JETZT eine offene Position, ist das der laufende Trade
            # (Master fährt immer nur 1 Order) → einfangen und sofort persistieren,
            # damit der Beweis den nächsten Restart überlebt (Review-Finding 07.08.).
            init_tickets = _plan_tickets(plan, None) or (master_tickets if d_master else all_tickets)
            if d_master and master_tickets and not _plan_tickets(plan, None):
                wt_save_tickets(uid, plan["id"], master_tickets)
            _watcher_state[key] = {"was_open": has_open, "notified": False,
                                   "baseline": (1 if master_ok else 0) if d_master else count,
                                   "streak": 0,
                                   "tickets": init_tickets}
            continue
        closed = (not master_ok) if d_master else (count < prev["baseline"])
        streak = (prev.get("streak") or 0) + 1 if closed else 0
        # ZEIT-basierte Close-Bestätigung (Review-Finding): der 07.07.-Schutz war bei
        # 15s-Takt implizit ein ~30s-Zeitfenster. Bei 4s-Takt wären 2 Ticks nur noch
        # ~8s — eine kurze Duplikum-Störung würde wieder Fehlalarme produzieren.
        # Deshalb: mindestens 2 Messungen IN FOLGE **und** ≥ 12s seit der ersten.
        closed_since = (prev.get("closed_since") or time.time()) if closed else None
        close_confirmed = (closed and streak >= 2 and closed_since is not None
                           and (time.time() - closed_since) >= 12)
        # ── Sofort-Bestätigung per POSITIVEM Beweis (06.08.2026) ──
        # Der 2-Messungen-Schutz existiert gegen ABWESENHEIT als Beweis: eine kurz
        # gestörte Duplikum-Antwort darf nicht wie "Position weg" wirken (07.07.).
        # Findet sich aber eine GESCHLOSSENE Position mit exakt dem gemerkten
        # Master-Ticket, ist das positiver Beweis — da gibt es nichts zu bestätigen.
        # Spart bei ~14s Poll-Abstand eine komplette Runde (Ende ~28s → ~14s) und
        # liefert den P&L in derselben Abfrage mit.
        pnl_now = None
        if closed and not close_confirmed and not prev["notified"] and prev["was_open"] \
           and _plan_tickets(plan, prev.get("tickets")):
            try:
                st_q, pnl_q = wt_fetch_pnl(token, d_slave, d_master, started_epoch_of(plan),
                                           _plan_tickets(plan, prev.get("tickets")), dup_email, n_acc)
                if st_q == "ok" and pnl_q:
                    close_confirmed, pnl_now = True, pnl_q
                    print(f"[watcher] ⚡ {label}: Close per Ticket-Treffer sofort bestätigt", flush=True)
            except Exception:
                pass
        if close_confirmed and prev["was_open"] and not prev["notified"]:
            ok = wt_finish_plan(uid, token, plan, d_slave, d_master, label,
                                started_epoch_of(plan), _plan_tickets(plan, prev.get("tickets")),
                                dup_email, n_acc, pnl_now)
            _watcher_state[key] = {**prev, "was_open": True, "notified": ok,
                                   "streak": streak, "closed_since": closed_since}
        elif has_open:
            _watcher_state[key] = {**prev, "was_open": True, "notified": False,
                                   "baseline": prev["baseline"] if d_master else max(prev["baseline"], count),
                                   "streak": streak, "closed_since": closed_since,
                                   "tickets": (master_tickets or prev.get("tickets")) if d_master
                                              else (prev.get("tickets") or all_tickets)}
        else:
            # was_open bleibt stehen — sonst hebelt sich der 2-Tick-Schutz selbst aus
            # (derselbe Bug steckte bis 04.08.2026 im Frontend-atCheck).
            st_new = {**prev, "streak": streak, "closed_since": closed_since}
            # Downtime-Recovery für offene Pläne: endete der Trade, während der Wächter
            # down war (State weg), wird was_open nie wieder true und der Plan hinge
            # für immer auf 'Läuft'. Bedingungen: keine Slave-Position, kein Master-
            # Fingerabdruck, Plan läuft seit >5min — dann mit EIGENEM Mehrfach-Schutz
            # (recovery_streak ≥ 3 ≈ 12s bei 4s-Takt) nach review verschieben.
            if not prev["was_open"] and not prev["notified"] and not master_ok:
                se = started_epoch_of(plan)
                if se and (time.time() - se) > 300:
                    rs = (prev.get("recovery_streak") or 0) + 1
                    st_new["recovery_streak"] = rs
                    if rs >= 3:
                        ok = wt_finish_plan(uid, token, plan, d_slave, d_master, label,
                                            se, _plan_tickets(plan, prev.get("tickets")), dup_email, n_acc)
                        st_new["notified"] = ok
                        if ok:
                            print(f"[watcher] ♻️ {label}: Plan {plan['id']} hing auf 'Läuft' (Ende während Downtime) — nachgeholt", flush=True)
            _watcher_state[key] = st_new


def watcher_cycle():
    creds_rows = sb_select("duplikum_credentials", {"select": "*"})
    _watcher_info["users"] = len(creds_rows)
    # State von Usern, deren duplikum_credentials-Zeile gelöscht wurde (Duplikum im
    # Frontend getrennt), aufräumen — sonst schleichender Leak über Monate Uptime.
    known_uids = {c.get("user_id") for c in creds_rows}
    known_emails = {(c.get("email") or "").strip().lower() for c in creds_rows}
    for k in [k for k in _watcher_state if k[0] not in known_uids]:
        _watcher_state.pop(k, None)
    for k in [k for k in _watcher_pnl_tries if k[0] not in known_uids]:
        _watcher_pnl_tries.pop(k, None)
    for u in [u for u in _watcher_meta if u not in known_uids]:
        _watcher_meta.pop(u, None)
    for e in [e for e in list(_watcher_backoff) if e.split("|")[0] not in known_emails]:
        _watcher_backoff.pop(e, None)
    for e in [e for e in _watcher_tokens if e not in known_emails]:
        _watcher_tokens.pop(e, None)
    for e in [e for e in _watcher_seen if e not in known_emails]:
        _watcher_seen.pop(e, None)
    with _watcher_memo_lock:
        for e in [e for e in _watcher_email_locks if e not in known_emails]:
            _watcher_email_locks.pop(e, None)

    # ALLE User PARALLEL (05.08.2026): jedes Duplikum-Konto hat sein eigenes
    # 2-Req/s-Limit — das alte Nacheinander mit 1,2s Abstand hat die Erkennung
    # nur künstlich verlangsamt. memo teilt Token + Positions-Fetch pro Konto.
    memo = {}
    failed = 0
    rows = [c for c in creds_rows if c.get("user_id")]
    if rows:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(rows))) as pool:
            futs = {pool.submit(wt_check_user, c["user_id"], c, memo): c for c in rows}
            for f in concurrent.futures.as_completed(futs):
                c = futs[f]
                try:
                    f.result()
                except Exception as e:
                    failed += 1
                    print(f"[watcher] ⚠️ {(c.get('email') or c.get('user_id'))[:24]}: {type(e).__name__}: {e}", flush=True)
    # Scheitern ALLE User (z.B. Supabase mitten im Zyklus weggebrochen), gilt der
    # Zyklus als fehlgeschlagen → last_run bleibt stehen → fresh kippt → Browser
    # übernimmt. Einzelne User-Fehler sind dagegen normal.
    if rows and failed == len(rows):
        raise RuntimeError(f"alle {failed} User fehlgeschlagen")


def watcher_loop():
    print(f"[watcher] 🚀 Server-Wächter läuft (Intervall {WATCHER_INTERVAL}s, parallel)", flush=True)
    while True:
        started = time.time()
        try:
            watcher_cycle()
            # WICHTIG (Review-Finding): last_run NUR nach erfolgreichem Zyklus stempeln.
            # Stünde es hinter dem except, bliebe fresh=true, obwohl jeder Zyklus wirft
            # (z.B. rotierter Service-Key) — alle Browser hätten ihre Erkennung
            # abgeschaltet und NIEMAND würde Trades erkennen, komplett lautlos.
            _watcher_info["last_run"] = time.time()
            _watcher_info["last_error"] = ""
        except Exception as e:
            _watcher_info["last_error"] = f"{type(e).__name__}: {e}"
            print(f"[watcher] ⚠️ Zyklus-Fehler: {e}", flush=True)
        _watcher_info["cycle_ms"] = int((time.time() - started) * 1000)
        _watcher_info["runs"] += 1
        time.sleep(max(1.0, WATCHER_INTERVAL - (time.time() - started)))


def start_watcher():
    global _watcher_thread_started
    if _watcher_thread_started:
        return
    if WATCHER_DISABLED:
        print("[watcher] ℹ️ WATCHER_DISABLED gesetzt — Server-Wächter aus.", flush=True)
        return
    if not SUPABASE_SERVICE_KEY:
        print("[watcher] ℹ️ Kein SUPABASE_SERVICE_KEY — Server-Wächter inaktiv (Browser-Erkennung übernimmt).", flush=True)
        return
    _watcher_thread_started = True
    _watcher_info["started"] = True
    threading.Thread(target=watcher_loop, daemon=True).start()


# ════════════════════════════════════════════════════════════════════════════
# ADMIN-ÜBERSICHT — Kapitalverteilung über ALLE Personen (15.08.2026)
#
# Finns Frage: "Wie viele Accounts habe ich pro Prop-Firma und wie viel Geld
# steckt da jeweils drin?" — personenübergreifend, um Klumpenrisiko zu sehen
# (Beispiel Alpha Future: wenn eine Firma abraucht, wie viel ist weg?).
#
# Warum serverseitig: Prophos-Accounts sind per RLS pro Login abgeschottet.
# Ein eingeloggter User kann die Zahlen der anderen Personen NICHT lesen. Die
# Aggregation braucht also den Service-Key — genau wie der Wächter.
#
# Zugang: der Aufrufer muss ein gültiges Supabase-Access-Token vorlegen (also
# ein eingeloggter Prophos-User sein). Der Code im Frontend ist nur das
# UI-Schloss — prophos.html ist öffentlich lesbar, ein dort eingebettetes
# Geheimnis wäre keins.
#
# "Geparkt" = Kaufpreis + Hedge-Verluste − Payouts, exakt wie
# calcReingesteckdEur/calcAccountPayoutsEur im Frontend (Payout-Beträge sind
# bereits EUR, Hedge-P&L wird per FX umgerechnet).
# Gezählt werden NUR AKTIVE Accounts (Finns Entscheidung 15.08.): archivierte/
# geblowte fliegen raus, weil bei einem Firmen-Exit nur verloren geht, was
# noch läuft.
# ════════════════════════════════════════════════════════════════════════════
SUPABASE_ANON_KEY = (os.environ.get("SUPABASE_ANON_KEY")
                     or "sb_publishable__LWDlDHJbNIr6X7kRwfqqg_tZcjwaDS").strip()

_FIRM_RULES = [
    ("apex", "Apex"), ("tradeify", "Tradeify"), ("fundednext", "FundedNext"),
    ("founded next", "FundedNext"), ("foundednext", "FundedNext"),
    ("fundingpips", "FundingPips"), ("funding pips", "FundingPips"),
    ("topstep", "Topstep"), ("ftmo", "FTMO"), ("alpha", "Alpha Future"),
    ("fusion", "Fusion Markets"), ("lucid", "Lucid Trading"),
]


# Personen, die im Admin-Dashboard NICHT auftauchen sollen (16.08.2026).
# Freunde, die Prophos eigenständig für sich nutzen: ihre Accounts und Kosten
# gehören ihnen, nicht Finns Kapitalverteilung. Sie arbeiten normal weiter —
# es geht rein um diese eine Auswertung.
# Erweitern ohne Code-Änderung: Railway-Variable ADMIN_EXCLUDE mit
# komma-getrennten E-Mails setzen (überschreibt die Vorgabe komplett).
ADMIN_EXCLUDE_EMAILS = {
    e.strip().lower()
    for e in (os.environ.get("ADMIN_EXCLUDE")
              or "elominx@gmail.com,finn.traidingview@gmail.com").split(",")
    if e.strip()
}


def _firm_norm(name):
    """Schreibweisen zusammenführen — sonst wird das Klumpenrisiko zu klein
    angezeigt (real vorhanden: 'Apex' vs 'Apex Trader', 'MyFoundedFutures')."""
    raw = (name or "").strip()
    f = raw.lower()
    if not f:
        return "—"
    if "5%er" in f or "5ers" in f or "5%ers" in f or "five percent" in f:
        return "The5%ers"
    if ("funded" in f or "founded" in f) and "futur" in f:
        return "MyFundedFutures"
    for needle, out in _FIRM_RULES:
        if needle in f:
            return out
    return raw


def _sb_all(table, params):
    """PostgREST-Select über ALLE Zeilen — seitenweise.

    ACHTUNG (Bug 13.08.2026): Ein simples `limit=50000` reicht NICHT. Supabase
    deckelt jede Antwort serverseitig bei `db-max-rows` (1000) — der Parameter
    wird stillschweigend nach unten korrigiert, ohne Fehler und ohne Hinweis.
    Genau daran hingen falsche Hedge-Summen im Admin-Dashboard: von 1314
    abgeschlossenen trade_plans sah die Aggregation nur die ersten 1000, also
    fehlten 314 Trades in den Kosten (bei Pascal 5.792 € statt 8.197 €).
    Deshalb hier explizit blättern, bis eine Seite kürzer als PAGE ist.
    """
    PAGE = 1000
    out, offset = [], 0
    while True:
        p = dict(params)
        # Ohne feste Sortierung darf Postgres die Reihenfolge zwischen zwei
        # Seiten ändern — dann fehlen Zeilen bzw. kommen doppelt. Alle vier
        # hier genutzten Tabellen haben eine id.
        p.setdefault("order", "id.asc")
        p["limit"] = str(PAGE)
        p["offset"] = str(offset)
        chunk = sb_select(table, p)
        if not isinstance(chunk, list):
            return chunk
        out.extend(chunk)
        if len(chunk) < PAGE:
            return out
        offset += PAGE
        if offset > 500000:          # Reißleine gegen Endlosschleifen
            return out


def admin_build_overview():
    accounts = _sb_all("accounts", {"select": "id,user_id,firm,account_type,purchase_cost,name,external_id"})
    arch_rows = _sb_all("user_settings", {"select": "value", "key": "eq.archive"})
    fx_rows   = _sb_all("user_settings", {"select": "value", "key": "eq.fx_usd_eur"})
    plans     = _sb_all("trade_plans", {"select": "master_account_id,slave_account_id,slave_pl",
                                        "status": "eq.completed"})
    txs       = _sb_all("transactions", {"select": "account_id,amount", "kind": "eq.payout"})

    # Archiv-Status liegt in user_settings (aus dem localStorage gesynct) und ist
    # zwischen Profilen historisch vermischt — unkritisch, weil Account-IDs global
    # eindeutig sind: ein fremder Eintrag matcht schlicht keinen eigenen Account.
    archived = set()
    preds_of = {}          # Nachfolger-ID -> [Vorgänger-IDs]
    for r in arch_rows:
        v = r.get("value")
        if isinstance(v, str):
            try: v = json.loads(v)
            except Exception: v = None
        if isinstance(v, dict):
            for acc_id, info in v.items():
                if isinstance(info, dict) and info.get("archived"):
                    archived.add(str(acc_id))
                elif info:
                    archived.add(str(acc_id))
                # Ein archivierter Account zeigt per successorId auf den Account,
                # der ihn abgelöst hat (Phase 1 → Phase 2 → Funded). Sein Geld
                # steckt weiterhin in der Firma — über den Nachfolger.
                if isinstance(info, dict) and info.get("successorId"):
                    preds_of.setdefault(str(info["successorId"]), []).append(str(acc_id))

    fx = 0.85
    for r in fx_rows:
        try:
            val = r.get("value")
            if isinstance(val, str): val = json.loads(val)
            f = float(val if not isinstance(val, dict) else val.get("rate"))
            if 0.5 < f < 1.5: fx = f; break
        except Exception:
            pass

    by_id = {str(a["id"]): a for a in accounts}
    live_ids = {str(a["id"]) for a in accounts if (a.get("account_type") or "") == "live"}

    # Hedge-Kosten je Master-Account: nur abgeschlossene Trades auf einen LIVE-Slave.
    # Verlust (slave_pl < 0) → Kosten +, Gewinn → Kosten −. USD→EUR wie im Frontend.
    hedge = {}
    for p in plans:
        if p.get("slave_pl") is None:
            continue
        if str(p.get("slave_account_id")) not in live_ids:
            continue
        m = str(p.get("master_account_id"))
        sl = by_id.get(str(p.get("slave_account_id"))) or {}
        try: pl = float(p["slave_pl"])
        except (TypeError, ValueError): continue
        cur = _firm_norm(sl.get("firm"))
        pl_eur = pl if cur == "Fusion Markets" else pl * fx   # Fusion rechnet in €
        hedge[m] = hedge.get(m, 0.0) + (-pl_eur)

    payouts = {}
    for t in txs:
        a = str(t.get("account_id") or "")
        if not a: continue
        try: payouts[a] = payouts.get(a, 0.0) + float(t.get("amount") or 0)
        except (TypeError, ValueError): pass

    # Personen-Labels (E-Mail) über die Auth-Admin-API
    names = {}
    names_ok = False
    try:
        r = requests.get(f"{SUPABASE_URL}/auth/v1/admin/users?per_page=200",
                         headers=_sb_headers(), timeout=12)
        for u in (r.json() or {}).get("users", []):
            names[str(u.get("id"))] = u.get("email") or str(u.get("id"))[:8]
        names_ok = bool(names)
    except Exception:
        pass

    # Ausgeblendete Personen auflösen. Die Zuordnung E-Mail → user_id hängt an
    # der Auth-API; fällt die aus, KANN nicht ausgeblendet werden. Das darf nicht
    # still passieren, sonst stünden fremde Zahlen unbemerkt in der Auswertung —
    # deshalb wird in dem Fall die ganze Antwort verweigert.
    excluded_ids, excluded_names = set(), []
    if ADMIN_EXCLUDE_EMAILS:
        if not names_ok:
            raise RuntimeError("Auth-API nicht erreichbar — Ausblenden von "
                               "Personen nicht möglich, Auswertung wäre falsch.")
        for uid, mail in names.items():
            if str(mail).strip().lower() in ADMIN_EXCLUDE_EMAILS:
                excluded_ids.add(str(uid))
                excluded_names.append(mail)

    def own(aid, a=None):
        """Eigene Zahlen EINES Accounts (ohne Kette), in EUR."""
        a = a if a is not None else by_id.get(aid) or {}
        try: buy = float(a.get("purchase_cost") or 0)
        except (TypeError, ValueError): buy = 0.0
        return buy, hedge.get(aid, 0.0), payouts.get(aid, 0.0)

    def chain(aid):
        """Wie calcReingesteckdEur() im Frontend: eigene Kosten PLUS die komplette
        Vorgänger-Kette. Ein geblowter Phase-1-Account ist nicht weg — sein Geld
        steckt über den Nachfolger weiter in derselben Prop-Firma. Genau das ist
        die Zahl, die die App pro Account als „Gesamtkosten" anzeigt."""
        b, h, p, n = 0.0, 0.0, 0.0, 0
        stack, seen = [aid], {aid}
        while stack:
            cur = stack.pop()
            acc = by_id.get(cur)
            if acc is None or (acc.get("account_type") or "") == "live":
                continue
            cb, ch, cp = own(cur, acc)
            b += cb; h += ch; p += cp
            if cur != aid:
                n += 1
            for prev in preds_of.get(cur, []):
                if prev not in seen and len(seen) < 200:   # Schutz gegen Zyklen
                    seen.add(prev); stack.append(prev)
        return b, h, p, n

    # Eine flache Zeile pro Account — die UI filtert/aggregiert daraus selbst
    # (Person, Firma, aktiv/archiviert). Jede Zeile trägt BEIDE Sichten:
    #   buy/hedge/payouts/parked      = nur dieser Account
    #   c_buy/c_hedge/c_payouts/c_parked = inkl. Vorgänger-Kette (= „Gesamtkosten")
    # Warum beide: über AKTIVE Accounts ist die Kettensicht richtig (das Geld der
    # abgelösten Accounts steckt weiter in der Firma). Zeigt man aktive UND
    # archivierte zusammen, würde die Kettensicht die Vorgänger doppelt zählen —
    # dort sind die Eigen-Zahlen richtig. Die UI wählt je nach Filter.
    rows = []
    for a in accounts:
        aid = str(a["id"])
        if (a.get("account_type") or "") == "live":
            continue                                   # Hedge-Broker, keine Prop-Firma
        if str(a.get("user_id")) in excluded_ids:
            continue                                   # nutzt Prophos eigenständig
        buy, hg, po = own(aid, a)
        cb, ch, cp, npred = chain(aid)
        uid = str(a.get("user_id"))
        rows.append({
            "id": aid,
            "ext": a.get("external_id") or "",
            "name": a.get("name") or "",
            "firm": _firm_norm(a.get("firm")),
            "firm_raw": (a.get("firm") or "").strip(),
            "type": a.get("account_type") or "",
            "user_id": uid,
            "person": names.get(uid, uid[:8]),
            "archived": aid in archived,
            "buy": round(buy, 2),
            "hedge": round(hg, 2),
            "payouts": round(po, 2),
            "parked": round(buy + hg - po, 2),
            "preds": npred,
            "c_buy": round(cb, 2),
            "c_hedge": round(ch, 2),
            "c_payouts": round(cp, 2),
            "c_parked": round(cb + ch - cp, 2),
        })

    people_list = sorted(
        [{"user_id": u, "name": names.get(u, u[:8])} for u in {r["user_id"] for r in rows}],
        key=lambda p: p["name"].lower())
    firm_list = sorted({r["firm"] for r in rows})
    return {"accounts": rows, "people": people_list, "firms": firm_list,
            "fx_usd_eur": fx, "generated": _wt_now_iso(),
            "excluded": sorted(excluded_names)}


@app.route("/admin/overview", methods=["GET", "OPTIONS"])
def admin_overview():
    if request.method == "OPTIONS":
        return "", 200
    if not SUPABASE_SERVICE_KEY:
        return jsonify({"error": "Server nicht konfiguriert (SUPABASE_SERVICE_KEY fehlt)"}), 503
    token = (request.headers.get("sb-token") or "").strip()
    if not token:
        return jsonify({"error": "Nicht angemeldet"}), 401
    try:
        r = requests.get(f"{SUPABASE_URL}/auth/v1/user", timeout=12,
                         headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"})
        if r.status_code != 200 or not (r.json() or {}).get("id"):
            return jsonify({"error": "Nicht angemeldet"}), 401
    except Exception:
        return jsonify({"error": "Anmeldung nicht prüfbar"}), 502
    try:
        return jsonify(admin_build_overview())
    except Exception as e:
        print(f"[admin] ⚠️ overview: {type(e).__name__}: {e}", flush=True)
        return jsonify({"error": str(e)}), 500


@app.route("/watcher/status", methods=["GET", "OPTIONS"])
def watcher_status():
    """Frontend-Gate: läuft der Server-Wächter, schaltet der Browser seine eigene
    Erkennung ab (nur noch UI-Poll). Bewusst KEINE per-User-Daten im Response —
    der Endpoint ist unauthentifiziert."""
    if request.method == "OPTIONS":
        return "", 200
    # 45s-Mindestfenster: ein einzelner langsamer Zyklus (P&L-Nachversuche schlafen
    # je 1s) darf fresh nicht kurz kippen lassen — Flapping würde die Browser-Engines
    # unnötig an- und wieder abschalten.
    fresh = _watcher_info["started"] and (time.time() - _watcher_info["last_run"]) < max(45, WATCHER_INTERVAL * 4)
    # Review-Finding: keine Nutzerzahl und keine rohen Fehlertexte nach außen
    # (Endpoint ist offen + CORS *) — error nur als Flag, Details stehen im Railway-Log.
    return jsonify({
        "enabled": _watcher_info["started"],
        "fresh": fresh,
        "last_run": int(_watcher_info["last_run"]),
        "interval": WATCHER_INTERVAL,
        "cycle_ms": _watcher_info["cycle_ms"],
        "error": bool(_watcher_info["last_error"]),
        "polls_last_hour": _dup_budget_snapshot(),
        "build": APP_BUILD,
    })


start_watcher()

# ── Duplikum Auto-Connect + proaktiver Refresh (überlebt Restarts) ──
# Läuft auf Modul-Ebene, damit es auch unter Gunicorn (Production) startet.
# Wenn DUP_EMAIL/DUP_PASSWORD als Env-Vars gesetzt sind, hält dieser Daemon
# die Verbindung dauerhaft warm — du musst im Frontend nie wieder verbinden.
_dup_daemon_started = False

def _dup_keepalive_loop():
    # Beim Start einmal sofort einen frischen Token holen (Session warm machen)
    while True:
        try:
            tok = refresh_duplikum_token(DUP_EMAIL)
            if tok:
                print(f"[duplikum] ✅ Keepalive: Token aktiv für {DUP_EMAIL}")
            else:
                print(f"[duplikum] ⚠️ Keepalive: konnte keinen Token holen — prüfe DUP_EMAIL/DUP_PASSWORD")
        except Exception as e:
            print(f"[duplikum] ⚠️ Keepalive-Fehler: {e}")
        time.sleep(DUP_REFRESH_INTERVAL)  # 40h < 48h Ablauf

def start_dup_keepalive():
    global _dup_daemon_started
    if _dup_daemon_started:
        return
    if not (DUP_EMAIL and DUP_PASSWORD):
        print("[duplikum] ℹ️ Kein DUP_EMAIL/DUP_PASSWORD gesetzt — Auto-Keepalive inaktiv (manuelles Verbinden nötig).")
        return
    _dup_daemon_started = True
    threading.Thread(target=_dup_keepalive_loop, daemon=True).start()
    print("[duplikum] 🚀 Keepalive-Daemon gestartet")

start_dup_keepalive()

# ── Lokaler Selbst-Update-Watcher (15.08.2026, Etappe 3 MT5-Route) ──
# Anlass: start-prophos.bat hält app.py auf den PCs jetzt — wie copier.py und
# panel.py — in einer Download-Schleife. Damit ein gepushtes Update auch WIRKT,
# muss der laufende Prozess von selbst enden; sonst läuft der alte Stand, bis
# jemand das Fenster schließt. NUR im Lokal-Modus aktiv (PROPHOS_FRONTEND
# existiert nur auf den PCs) — Railway darf sich NIE selbst beenden, dort
# deployt Git. Als Trigger dient mt5-copier/VERSION (derselbe zentrale Bump,
# der auch Copier und Panel neu startet).
_LOCAL_UPDATE_URL = ("https://raw.githubusercontent.com/finntraidingview-cmd/"
                     "Prophos/main/mt5-copier/VERSION")

def _local_fetch_version():
    try:
        r = requests.get(_LOCAL_UPDATE_URL, timeout=10)
        if r.ok:
            v = r.text.strip()
            if v:
                return v
    except Exception:
        pass
    return None

def _local_version_watcher():
    # Boot-Baseline EINMAL holen. Schlägt das fehl (kein Netz beim Start),
    # bleibt der Watcher komplett inaktiv — ein Vergleich gegen None würde
    # sonst beim ersten Netz-Flackern Restart-Flattern erzeugen
    # (Richter-Fix 15.08.2026). Die .bat lädt beim nächsten Start ohnehin frisch.
    baseline = _local_fetch_version()
    if baseline is None:
        print("[update] ℹ️ Baseline-VERSION nicht ladbar — Selbst-Update-Watcher "
              "inaktiv (nächster .bat-Durchlauf holt trotzdem frische Dateien).")
        return
    waiting_logged = False
    while True:
        time.sleep(60)
        rv = _local_fetch_version()
        if rv is None or rv == baseline:
            continue
        # Update da. Exit NUR, wenn keine Mirror-Session scharf ist — ein
        # os._exit mitten im Spiegeln hieße: offene Position ohne Hedge-Pflege
        # (gleiches Muster wie copier.py: warten, bis alle Master flach sind).
        armed = [pid for pid, s in list(mirror_sessions.items()) if s.get("active")]
        if armed:
            if not waiting_logged:
                waiting_logged = True
                print(f"[update] ↻ {baseline} → {rv} verfügbar — Update wartet, "
                      f"bis kein Mirror mehr scharf ist ({', '.join(str(p) for p in armed)}).")
            continue
        print(f"[update] ↻ {baseline} → {rv} — kein Mirror scharf, beende Prozess "
              f"(start-prophos.bat lädt die neuen Dateien und startet neu).")
        os._exit(0)

def _local_port_taken(port):
    # Doppelstart-Schutz (15.08.2026, nur Lokal-Modus): lauscht schon jemand auf
    # dem Port, sauber melden statt Flask sterben zu lassen — die 10-s-Schleife
    # der .bat würde sonst endlos gegen den belegten Port anrennen, und auf den
    # PCs mit ALTEM Setup (Aufgabenplanungs-Task start-local-backend) gewinnt
    # sonst still das nie updatende alte Backend.
    import socket
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=1)
        s.close()
        return True
    except OSError:
        return False

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    if os.environ.get("PROPHOS_FRONTEND"):
        # Lokal-Modus (nur auf den PCs gesetzt): Doppelstart-Schutz + Update-Watcher.
        if _local_port_taken(port):
            import sys
            print("=" * 70)
            print(f"⛔ Port {port} belegt — läuft schon ein Prophos-Backend?")
            print("   Wenn das alte Setup (C:\\prophos) noch aktiv ist: die ALTE")
            print("   Aufgabenplanungs-Task (start-local-backend) entfernen, z.B.:")
            print("   schtasks /delete /tn \"<Name der alten Task>\" /f")
            print("   (Aufgabenplanung öffnen → Task suchen → löschen.)")
            print("=" * 70)
            sys.exit(1)  # sauber raus — die .bat wartet 10 s und probiert erneut
        threading.Thread(target=_local_version_watcher, daemon=True).start()
    app.run(host="0.0.0.0", port=port)
