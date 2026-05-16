import requests
import urllib3
import threading
import json
import time
import uuid
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from flask import Flask, request, jsonify, Response, send_from_directory
import os

app = Flask(__name__)
TSX_BASE = "https://api.topstepx.com"
MA_BASE  = "https://mt-client-api-v1.london.agiliumtrade.ai"
DUP_BASE = "https://www.trade-copier.com/webservice/v4"

# Token Refresh Interval (TSX Tokens leben 24h, wir refreshen alle 20min proaktiv)
TOKEN_REFRESH_INTERVAL = 20 * 60  # 20 Minuten

# Duplikium tokens leben 48h — wir refreshen alle 40h proaktiv
DUP_REFRESH_INTERVAL = 40 * 60 * 60  # 40 Stunden

# Active mirror sessions: pair_id -> session data
mirror_sessions = {}

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
    """Holt mit gecachten Creds einen neuen Token. Returns neuer Token oder None."""
    s = duplikum_sessions.get(email)
    if not s or not s.get("password"): return None
    try:
        r = requests.post(
            f"{DUP_BASE}/access/getToken.php",
            auth=(email, s["password"]),
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
            s["token"] = token
            s["last_refresh"] = time.time()
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

        # 401 → Token abgelaufen → versuchen zu refreshen mit gecachten Creds
        if r.status_code == 401 and email:
            new_tok = refresh_duplikum_token(email)
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
    else:
        worker_fn = run_mirror

    # Watchdog: falls der Worker durch eine unerwartete Exception crasht
    # (sollte mit den neuen except-Klauseln nicht mehr passieren, aber zur Sicherheit),
    # startet er sich automatisch neu — solange die Session noch active ist.
    def watchdog(pid, fn):
        max_restarts = 5
        restarts = 0
        while mirror_sessions.get(pid, {}).get("active") and restarts <= max_restarts:
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
            if pid in mirror_sessions:
                mirror_sessions[pid]["active"] = False

    thread = threading.Thread(target=watchdog, args=(pair_id, worker_fn), daemon=True)
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
            "log": s.get("log", [])[-50:],  # letzte 50 statt 20 — User will mehr Detail sehen
            "positions": s.get("positions", {})
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

    while mirror_sessions.get(pair_id, {}).get("active"):
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
        lots = round(qty * multiplier, 2)

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

    while mirror_sessions.get(pair_id, {}).get("active"):
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
