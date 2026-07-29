#!/usr/bin/env python3
"""
Topstep-Mirror-Agent — lokal pro PC statt zentral in Amsterdam.

Zweck: Die TopstepX-API-Verbindung (Fills lesen) kommt jetzt aus der EIGENEN PC-IP der
Person — dieselbe IP wie deren manuelle TopstepX-Order — statt aus dem gemeinsamen
Railway-Server (Amsterdam). Damit verschwindet die IP-Klammer über alle Accounts.

Steuerung: autonom über Supabase-Tabelle `mirror_control`. Prophos schreibt dort den
Auftrag rein (active=true + Parameter), der Agent liest seine Zeilen (agent_id) und führt
den Mirror lokal aus. Braucht KEINEN offenen Browser/Tab — läuft als Dienst 24/7.

Secrets (TopstepX-API-Key/-Username, MetaApi-Token) liegen NUR lokal in config.json,
niemals in Supabase.

Die Mirror-Kernlogik (Polling, tsx_to_mt) ist 1:1 aus app.py portiert, inkl. der dort
dokumentierten Bugfixes (Zombie-Schutz per Session-Identität, Backoff, Token-Refresh).
Nicht getestet gegen echte Konten — vor Live-Einsatz gegen einen Sim/Demo-Account prüfen.
"""

import json
import os
import sys
import time
import threading
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TSX_BASE = "https://api.topstepx.com"
MA_BASE  = "https://mt-client-api-v1.london.agiliumtrade.ai"
TOKEN_REFRESH_INTERVAL = 20 * 60  # 20 Minuten (wie app.py)

# ── Config laden ──────────────────────────────────────────────────────────────
def load_config():
    path = os.environ.get("AGENT_CONFIG", os.path.join(os.path.dirname(__file__), "config.json"))
    if not os.path.exists(path):
        sys.exit(f"config.json nicht gefunden ({path}). config.example.json kopieren und ausfüllen.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

CONFIG = load_config()
SB_URL = CONFIG["supabase_url"].rstrip("/")
SB_KEY = CONFIG["supabase_key"]
AGENT_ID = CONFIG["agent_id"]
CONTROL_POLL = float(CONFIG.get("poll_control_interval", 3))
SECRETS = CONFIG.get("accounts", {})  # pair_id -> {tsx_username, tsx_api_key, ma_token}

SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}

# Aktive Mirror-Sessions: pair_id -> session-dict (analog mirror_sessions in app.py)
mirror_sessions = {}

# ── Supabase REST (PostgREST) ───────────────────────────────────────────────────
def sb_get_active_rows():
    """Alle aktiven Steuerzeilen für DIESEN Agent holen."""
    try:
        r = requests.get(
            f"{SB_URL}/rest/v1/mirror_control",
            headers=SB_HEADERS,
            params={"agent_id": f"eq.{AGENT_ID}", "select": "*"},
            timeout=15)
        if r.ok:
            return r.json()
        print(f"[control] Supabase GET {r.status_code}: {r.text[:120]}")
    except Exception as e:
        print(f"[control] Supabase GET error: {type(e).__name__}: {str(e)[:120]}")
    return None

def sb_patch(pair_id, fields):
    """Status/Log/Positions in die Steuerzeile zurückschreiben."""
    try:
        requests.patch(
            f"{SB_URL}/rest/v1/mirror_control",
            headers=SB_HEADERS,
            params={"agent_id": f"eq.{AGENT_ID}", "pair_id": f"eq.{pair_id}"},
            json={**fields, "updated_at": "now()"},
            timeout=15)
    except Exception as e:
        print(f"[{pair_id}] Supabase PATCH error: {type(e).__name__}: {str(e)[:100]}")

# ── Logging (lokaler Ring-Puffer + periodischer Rückschrieb nach Supabase) ──────
def log_msg(pair_id, msg, kind=None):
    print(f"[{pair_id}] {msg}")
    s = mirror_sessions.get(pair_id)
    if not s:
        return
    if kind is None:
        first = msg[:3] if msg else ""
        if any(e in first for e in ["✅", "🔄", "🆕", "📊"]): kind = "ok"
        elif any(e in first for e in ["❌", "💥", "⛔", "🔒"]): kind = "err"
        elif any(e in first for e in ["⚠️", "⏱", "🔌", "📦"]): kind = "warn"
        else: kind = "info"
    s["log"].append({"ts": time.strftime("%H:%M:%S"), "msg": msg, "kind": kind})
    if len(s["log"]) > 500:
        s["log"] = s["log"][-500:]

def flush_status(pair_id):
    """Log/Status/Positions in Supabase spiegeln (für die Prophos-Anzeige)."""
    s = mirror_sessions.get(pair_id)
    if not s:
        return
    sb_patch(pair_id, {
        "status": "running" if s.get("active") else "stopped",
        "last_heartbeat": "now()",
        "log": s.get("log", [])[-200:],
        "positions": s.get("positions", {}),
    })

# ── TopstepX-Auth: eigener Login per API-Key (loginKey) + Refresh (validate) ─────
def tsx_login_key(pair_id, http):
    """Initialen JWT über Username + API-Key holen. Keys kommen aus dem lokalen config."""
    sec = SECRETS.get(pair_id, {})
    username = sec.get("tsx_username")
    api_key  = sec.get("tsx_api_key")
    if not username or not api_key:
        log_msg(pair_id, "❌ Keine tsx_username/tsx_api_key in config.json für dieses Pair")
        return False
    try:
        r = http.post(f"{TSX_BASE}/api/Auth/loginKey",
            json={"userName": username, "apiKey": api_key},
            headers={"Content-Type": "application/json"}, timeout=15)
        d = r.json() if r.ok else {}
        if r.ok and d.get("success") and d.get("token"):
            s = mirror_sessions.get(pair_id)
            if s:
                s["tsxToken"] = d["token"]
                s["lastTokenRefresh"] = time.time()
            log_msg(pair_id, "🔄 TSX Login (API-Key) ok")
            return True
        log_msg(pair_id, f"❌ TSX loginKey fehlgeschlagen: {r.status_code} {str(d)[:120]}")
    except Exception as e:
        log_msg(pair_id, f"❌ TSX loginKey exception: {type(e).__name__}: {str(e)[:100]}")
    return False

def refresh_tsx_token(pair_id, session_obj, max_retries=3):
    """JWT über /api/Auth/validate erneuern. Bei endgültigem Ablauf: loginKey neu."""
    s = mirror_sessions.get(pair_id)
    if not s: return False
    for attempt in range(1, max_retries + 1):
        try:
            r = session_obj.post(f"{TSX_BASE}/api/Auth/validate",
                headers={"Authorization": f"Bearer {s['tsxToken']}", "Content-Type": "application/json"},
                timeout=10)
            if r.status_code == 401:
                log_msg(pair_id, "🔒 Token abgelaufen — neuer loginKey")
                return tsx_login_key(pair_id, session_obj)
            if 500 <= r.status_code < 600:
                if attempt < max_retries:
                    time.sleep(2 ** attempt); continue
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
            return False
        except requests.exceptions.Timeout:
            if attempt < max_retries: time.sleep(2 ** attempt); continue
            return False
        except requests.exceptions.ConnectionError:
            if attempt < max_retries: time.sleep(2 ** attempt); continue
            return False
        except Exception as e:
            log_msg(pair_id, f"⚠️ Token-Refresh exception: {type(e).__name__}: {str(e)[:80]}")
            return False
    return False

# ── Micro/Mini-Umrechnung (1:1 aus app.py) ──────────────────────────────────────
def _instr_scale(fill_base, plan_base):
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

# ── Hedge öffnen/schließen (1:1 aus app.py, MetaApi) ─────────────────────────────
def open_hedge(pair_id, order_id, side, contract, qty, tsx_risk_usd=0):
    s = mirror_sessions.get(pair_id)
    if not s: return
    ma_token = SECRETS.get(pair_id, {}).get("ma_token")

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
            log_msg(pair_id, f"⚖️ Kontrakt-Umrechnung: Fill {base}, Basis {s.get('baseInstrument','MNQ')} → Faktor {scale} → {lots} Lots")
    lots = max(0.01, lots)

    mt_side = "ORDER_TYPE_SELL" if side in (0, "0", "Buy", "buy", "BUY", "Long", "long", "B") else "ORDER_TYPE_BUY"
    body = {"symbol": mt_symbol, "volume": lots, "actionType": mt_side, "comment": f"HM-{str(order_id)[:8]}"}
    try:
        r = requests.post(f"{MA_BASE}/users/current/accounts/{s['maAccountId']}/trade",
            headers={"auth-token": ma_token, "Content-Type": "application/json"},
            json=body, timeout=15, verify=False)
        try: d = r.json()
        except (ValueError, requests.exceptions.JSONDecodeError): d = {}
        if r.ok:
            pos_id = str(d.get("positionId") or d.get("orderId", ""))
            s["positions"][order_id] = pos_id
            log_msg(pair_id, f"✅ Hedge OPEN: {mt_side.split('_')[-1]} {lots}x {mt_symbol} | pos={pos_id}")
        else:
            log_msg(pair_id, f"❌ Open failed: {r.status_code} {r.text[:150]}")
    except requests.exceptions.Timeout:
        log_msg(pair_id, "⏱ Open timeout (Trade ggf. trotzdem ausgeführt — MT5 prüfen!)")
    except requests.exceptions.ConnectionError as e:
        log_msg(pair_id, f"🔌 Open connection error: {str(e)[:100]}")
    except Exception as e:
        log_msg(pair_id, f"❌ Open error: {type(e).__name__}: {str(e)[:120]}")

def close_hedge(pair_id, ref_id):
    s = mirror_sessions.get(pair_id)
    if not s: return
    ma_token = SECRETS.get(pair_id, {}).get("ma_token")
    pos_id = s["positions"].get(ref_id)
    if not pos_id:
        log_msg(pair_id, f"ℹ️ Keine gespiegelte MT-Position für {ref_id} (manuell geschlossen?)")
        return
    body = {"actionType": "POSITION_CLOSE_ID", "positionId": pos_id}
    try:
        r = requests.post(f"{MA_BASE}/users/current/accounts/{s['maAccountId']}/trade",
            headers={"auth-token": ma_token, "Content-Type": "application/json"},
            json=body, timeout=15, verify=False)
        if r.ok:
            log_msg(pair_id, f"✅ Hedge CLOSED: pos={pos_id}")
            s["positions"].pop(ref_id, None)
            s.setdefault("closedHedges", []).append({"mtPosId": str(pos_id), "ts": time.time()})
            if len(s["closedHedges"]) > 50:
                s["closedHedges"] = s["closedHedges"][-50:]
        else:
            err_text = r.text[:100]
            log_msg(pair_id, f"❌ Close failed: {r.status_code} {err_text}")
            if r.status_code == 404 or "not found" in err_text.lower() or "no position" in err_text.lower():
                log_msg(pair_id, "ℹ️ MT-Position bereits weg — entferne aus Tracking")
                s["positions"].pop(ref_id, None)
    except requests.exceptions.Timeout:
        log_msg(pair_id, "⏱ Close timeout (Position ggf. trotzdem geschlossen — MT5 prüfen!)")
    except requests.exceptions.ConnectionError as e:
        log_msg(pair_id, f"🔌 Close connection error: {str(e)[:100]}")
    except Exception as e:
        log_msg(pair_id, f"❌ Close error: {type(e).__name__}: {str(e)[:120]}")

# ── Mirror-Worker (Polling, tsx_to_mt — 1:1 aus app.py run_mirror) ──────────────
def run_mirror(pair_id):
    s = mirror_sessions.get(pair_id)
    if not s: return
    http = requests.Session()
    http.verify = False

    if not s.get("tsxToken"):
        if not tsx_login_key(pair_id, http):
            log_msg(pair_id, "⛔ Kein TSX-Login — Worker stoppt")
            s["active"] = False
            return

    log_msg(pair_id, "🚀 Mirror gestartet — TSX → MT5 (lokal)")
    log_msg(pair_id, f"📊 TSX Account: {s.get('tsxAccountId','?')} · MT5 Account: {s.get('maAccountId','?')}")
    target_eur = float(s.get("targetRiskEur", 0)); multiplier = float(s.get("multiplier", 1.0))
    log_msg(pair_id, f"⚙️ Risiko-Mode: {'dynamisch ' + str(target_eur) + '€' if target_eur > 0 else 'Multiplier ' + str(multiplier) + 'x'}")

    known_positions = {}
    consecutive_errors = 0
    last_heartbeat = time.time()
    last_flush = 0
    HEARTBEAT_INTERVAL = 120
    MAX_BACKOFF = 60

    while mirror_sessions.get(pair_id) is s and s.get("active"):
        if time.time() - s.get("lastTokenRefresh", 0) > TOKEN_REFRESH_INTERVAL:
            refresh_tsx_token(pair_id, http)
        if time.time() - last_heartbeat > HEARTBEAT_INTERVAL:
            n_open = len(known_positions)
            log_msg(pair_id, f"💓 Mirror läuft — {n_open} offene Position{'en' if n_open != 1 else ''}")
            last_heartbeat = time.time()
        # Status regelmäßig nach Supabase spiegeln (für die Prophos-Anzeige)
        if time.time() - last_flush > 5:
            flush_status(pair_id); last_flush = time.time()

        try:
            r = http.post(f"{TSX_BASE}/api/Position/searchOpen",
                headers={"Authorization": f"Bearer {s['tsxToken']}", "Content-Type": "application/json"},
                json={"accountId": int(s["tsxAccountId"])}, timeout=10)
            if r.status_code == 401:
                log_msg(pair_id, "🔒 401 — Token Refresh")
                if refresh_tsx_token(pair_id, http):
                    consecutive_errors = 0; continue
                consecutive_errors += 1
                time.sleep(min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))); continue
            if not r.ok:
                consecutive_errors += 1
                backoff = min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))
                log_msg(pair_id, f"Poll error: {r.status_code} {r.text[:100]} — warte {backoff}s")
                time.sleep(backoff); continue
            consecutive_errors = 0

            d = r.json()
            positions = d.get("positions", d.get("data", []))
            current = {str(p.get("id", p.get("positionId", ""))): p for p in positions}

            for pid, pos in current.items():
                if pid not in known_positions:
                    raw_side = pos.get("side", pos.get("action", ""))
                    raw_type = pos.get("type", 0)
                    side = "Buy" if (raw_type == 1 or raw_side in ("Buy", "buy", "BUY", "Long", 0, "0")) else "Sell"
                    contract = pos.get("contractId", "")
                    qty = int(pos.get("size", pos.get("quantity", 1)))
                    tsx_risk = float(pos.get("initialRisk", pos.get("risk", 0)) or 0)
                    log_msg(pair_id, f"🆕 TSX Position: {side} {qty}× {contract}" + (f" · Risk ${tsx_risk}" if tsx_risk > 0 else ""))
                    open_hedge(pair_id, pid, side, contract, qty, tsx_risk)
                    last_heartbeat = time.time()

            for pid in list(known_positions.keys()):
                if pid not in current:
                    log_msg(pair_id, f"🔚 TSX Position geschlossen: {pid[:12]}… → schließe Hedge")
                    close_hedge(pair_id, pid)
                    last_heartbeat = time.time()

            known_positions = current
        except requests.exceptions.Timeout:
            consecutive_errors += 1
            time.sleep(min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))); continue
        except requests.exceptions.ConnectionError as e:
            consecutive_errors += 1
            log_msg(pair_id, f"🔌 Connection error: {str(e)[:80]}")
            time.sleep(min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))); continue
        except (requests.exceptions.JSONDecodeError, ValueError, KeyError, TypeError) as e:
            consecutive_errors += 1
            log_msg(pair_id, f"📦 Bad data: {type(e).__name__} {str(e)[:80]}")
            time.sleep(min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))); continue
        except Exception as e:
            consecutive_errors += 1
            log_msg(pair_id, f"⚠️ Unerwartet: {type(e).__name__}: {str(e)[:120]}")
            time.sleep(min(MAX_BACKOFF, 2 ** min(consecutive_errors, 6))); continue

        time.sleep(s.get("pollInterval", 0.5))

    http.close()
    flush_status(pair_id)
    log_msg(pair_id, "Mirror gestoppt")

# ── Watchdog pro Pair (1:1-Verhalten wie app.py) ────────────────────────────────
def watchdog(pair_id, sess):
    max_restarts = 5; restarts = 0
    while mirror_sessions.get(pair_id) is sess and sess.get("active") and restarts <= max_restarts:
        try:
            run_mirror(pair_id); break
        except Exception as e:
            restarts += 1
            log_msg(pair_id, f"💥 Worker crashed ({type(e).__name__}: {str(e)[:100]}) — Restart {restarts}/{max_restarts}")
            time.sleep(2 * restarts)
    if restarts > max_restarts and mirror_sessions.get(pair_id) is sess:
        sess["active"] = False
        sb_patch(pair_id, {"status": "error"})

def start_pair(row):
    pair_id = row["pair_id"]
    if pair_id in mirror_sessions:
        return
    if pair_id not in SECRETS:
        print(f"[{pair_id}] aktiv laut Supabase, aber keine Secrets in config.json — übersprungen")
        return
    session = {
        "pairId": pair_id,
        "tsxToken": None,
        "tsxAccountId": row.get("tsx_account_id"),
        "maAccountId": row.get("ma_account_id"),
        "multiplier": float(row.get("multiplier") or 1.0),
        "targetRiskEur": float(row.get("target_risk_eur") or 0),
        "pollInterval": float(row.get("poll_interval") or 0.5),
        "direction": row.get("direction") or "tsx_to_mt",
        "engine": row.get("engine") or "polling",
        "baseInstrument": str(row.get("base_instrument") or "MNQ").upper(),
        "symbolMap": row.get("symbol_map") or {"MNQ": "NAS100", "NQ": "NAS100", "ES": "US500", "MES": "US500"},
        "active": True, "positions": {}, "log": [], "lastTokenRefresh": 0,
    }
    mirror_sessions[pair_id] = session
    threading.Thread(target=watchdog, args=(pair_id, session), daemon=True).start()
    print(f"[{pair_id}] gestartet")

def stop_pair(pair_id):
    s = mirror_sessions.get(pair_id)
    if s:
        s["active"] = False
        mirror_sessions.pop(pair_id, None)
        sb_patch(pair_id, {"status": "stopped"})
        print(f"[{pair_id}] gestoppt")

# ── Steuer-Loop: Supabase pollen, Worker an-/abschalten ─────────────────────────
def control_loop():
    print(f"Topstep-Agent gestartet · agent_id={AGENT_ID} · Supabase-Poll {CONTROL_POLL}s")
    while True:
        rows = sb_get_active_rows()
        if rows is not None:
            active_ids = set()
            for row in rows:
                pid = row.get("pair_id")
                if row.get("active"):
                    active_ids.add(pid)
                    if pid not in mirror_sessions:
                        start_pair(row)
                    else:
                        # Parameter live nachziehen (Multiplier/SymbolMap etc. ohne Neustart)
                        s = mirror_sessions[pid]
                        s["multiplier"] = float(row.get("multiplier") or s["multiplier"])
                        s["targetRiskEur"] = float(row.get("target_risk_eur") or 0)
                        if row.get("symbol_map"): s["symbolMap"] = row["symbol_map"]
                        s["baseInstrument"] = str(row.get("base_instrument") or s["baseInstrument"]).upper()
                elif pid in mirror_sessions:
                    stop_pair(pid)
            # Zeilen, die ganz aus Supabase verschwunden sind → auch stoppen
            for pid in list(mirror_sessions.keys()):
                if pid not in active_ids:
                    stop_pair(pid)
        time.sleep(CONTROL_POLL)

if __name__ == "__main__":
    try:
        control_loop()
    except KeyboardInterrupt:
        print("\nAgent beendet.")
