import requests
import urllib3
import threading
import json
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
APP_BUILD = "2026-07-21.6"

@app.route("/version", methods=["GET"])
def version():
    return jsonify({
        "build": APP_BUILD,
        "commit": (os.environ.get("RAILWAY_GIT_COMMIT_SHA") or "")[:12]
    })

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
    r.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, ma-token, ma-account, dup-token, dup-user"
    r.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return r

@app.route("/")
def index():
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
            timeout=20
        )

    try:
        r = do_request(token)

        # 401 → Token abgelaufen → versuchen zu refreshen (Cache- ODER Env-Creds)
        refresh_email = email or DUP_EMAIL
        if r.status_code == 401 and refresh_email:
            new_tok = refresh_duplikum_token(refresh_email)
            if new_tok:
                r = do_request(new_tok)
                resp = Response(r.content, status=r.status_code, content_type=r.headers.get("Content-Type", "application/json"))
                resp.headers["X-New-Dup-Token"] = new_tok
                return resp

        return Response(r.content, status=r.status_code, content_type=r.headers.get("Content-Type", "application/json"))
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Netzwerkfehler: {e}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
