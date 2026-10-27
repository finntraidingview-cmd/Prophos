"""SUPPORT-CHAT „Lotse“ (27.10.2026, Finn: „Alle Leute, die Prophos nutzen, sollen mich nicht alle 10 Minuten fragen müssen. Ein
Chat-Support kommt unten rechts, da wo die Münze ist. Verbunden mit der Claude-API, ein eigener Support-Agent. Wichtig: beschränkter
Zugriff auf die Datenbank, kennt sich in der Navigation aus … ‚Mach den Trade mal raus' oder ‚Warum habe ich die Fehlermeldung?' soll
mit einem Klick gelöst sein“; Nachtrag: „wie eine eigene KI, und dass man da auch Screenshots hochladen kann, ist ganz wichtig“).
EIGENES MODUL wie polar_app: app.py bekommt nur `support_app.registrieren(app, globals())`.

  GET    /support/stand                Zugang + Rest des Tageslimits (Panel zeigt den Knopf nur bei an)
  GET    /support/unterhaltungen       Liste der eigenen Unterhaltungen
  GET    /support/unterhaltung/<id>    Blasen einer Unterhaltung (Text, Bild-Anzahl, Bestätigen-Vorschläge)
  DELETE /support/unterhaltung/<id>    Unterhaltung + ihre Bilder löschen
  POST   /support/chat                 {unterhaltung_id?, frage, bilder:[{daten(base64), typ, w, h}]} → Antwort + Vorschläge
  POST   /support/aktion               {token} → führt EINEN bestätigten Handgriff aus
  GET    /support/auftrag?id=          Stand eines Auftrags an den PC (Balance, Beendet-Prüfung, Tab neu laden)

RECHTE-RAHMEN (serverseitig, nie vom Modell): die erlaubte ID-Menge kommt aus dem Token (_wd_login + ?ansicht=admin) und support_zugang:
Verwalter = seine Gruppe; ein im Admin unbeschränkter Login MIT support_zugang.sicht = 'alle' (Finn, Pascal — Freigabe 27.10.2026 Punkt 3:
„sehen im Chat alle IDs wie im Admin") = Standard-Sicht Hermann Technologies bzw. der gewählte Gruppen-Chip (?gruppe=); alle anderen = nur
die eigene ID. Bewusst eine eigene Spalte statt „unbeschränkt" allein: im Admin ist jede HT-ID ohne admin_zugang-Zeile unbeschränkt
(admin_sicht_menge → None), im Chat sollen normale IDs aber nur sich sehen. Das Modell gibt nie eine user_id an, nur Plan-/Konto-IDs, einen
PC oder einen Personen-Namen aus der Menge; der Server prüft den Besitz gegen die Menge. Schreiben nur über die Whitelist (trade_loeschen, trade_beendet_pruefen, balance_lesen, tab_neu_laden)
und nur zweistufig: das Werkzeug erzeugt eine VORSCHAU + ein signiertes 5-min-Token, ausgeführt wird erst auf den Bestätigen-Klick
(/support/aktion), mit erneuter Prüfung. Keine Orders, kein Hedge, kein Planen/Abhaken/Buchen, keine Einstellungen.

Der API-Schlüssel liegt nur als Railway-Variable ANTHROPIC_API_KEY (trägt Finn ein). Modell per SUPPORT_MODELL (Standard Sonnet 5.5,
Konzept-Freigabe 27.10.2026). Fester Systemtext = support_wissen.md, byte-gleich je Anfrage (Prompt-Cache); alles, was je Nutzer/Zeit
wechselt, steht in der Nutzer-Nachricht. Der Verlauf wird nur angehängt, nie umgeschrieben."""
import base64
import hashlib
import hmac
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta

import requests
from flask import request, jsonify

try:
    from zoneinfo import ZoneInfo
except ImportError:          # Python < 3.9 gibt es auf Railway nicht; nur damit der Import nie das Backend kippt
    ZoneInfo = None

A = {}                        # Namensraum von app.py (Supabase-Helfer, Auth) — gefüllt in registrieren()

NAME = "Lotse"
MODELL = (os.environ.get("SUPPORT_MODELL") or "claude-sonnet-5-5").strip()
EFFORT = (os.environ.get("SUPPORT_EFFORT") or "low").strip()
MAX_TOKENS = 4000
MAX_RUNDEN = 5                # Tool-Runden je Frage; die letzte Runde ohne Werkzeuge (tool_choice none)
MAX_FRAGEN_JE_UNTERHALTUNG = 25   # danach „neue Unterhaltung" — der Verlauf wird nie vorne gekürzt (Cache + Denk-Blöcke)
FRAGE_MAX_ZEICHEN = 1500
TAGESDECKEL = int(os.environ.get("SUPPORT_TAGESDECKEL") or 600)   # alle IDs zusammen je Tag — Kosten-Notbremse
TAGESLIMIT_STANDARD = 40
BILD_MAX_JE_FRAGE = 3
BILD_MAX_JE_UNTERHALTUNG = 8
BILD_MAX_BYTES = 2_500_000
BILD_TAGE = 7
UNTERHALTUNG_TAGE = 30
AKTION_GUELTIG_S = 300
TOOL_ERGEBNIS_MAX = 9000
BUCKET = "support-bilder"
WISSEN_DATEI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "support_wissen.md")
ANKER = ("accounts", "trades", "tplaner", "wdlive", "markt", "payouts", "mt5copier", "echoplus", "news", "notes", "mail",
         "settings", "kasse")

_client = {"c": None}
_wissen = {"text": None, "mtime": 0.0}
_bild_cache = {}              # pfad → base64 (Verlauf schickt dieselben Bilder jede Runde, Zeichen für Zeichen gleich)
_bild_cache_lock = threading.Lock()
_unterhaltung_locks = {}
_locks_lock = threading.Lock()
_aufraeumen = {"at": 0.0}
_zusatz = {"an": True}        # effort + fallbacks mitschicken (fällt einmalig weg, wenn die API sie ablehnt)
_nonce_lock = threading.Lock()
_nonce_benutzt = {}           # Nonce → Ablauf (epoch); ein Prozess (gunicorn --workers 1), daher reicht das gegen Doppelklicks

ROUTE_TEXT = {"tvv2": "Orbit V2 (TradingView)", "tsv2": "Topstep V2 (TopstepX)", "mt5v2": "Echo V2 (MT5)", "mt5": "Echo (MT5)",
              "tvplus": "Orbit", "polar": "Polar", "duplikum": "Duplikum"}
STATUS_TEXT = {"planned": "geplant", "open": "läuft", "review": "Überprüfen", "completed": "abgehakt", "cancelled": "abgebrochen"}


# ── Hilfen ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _tz(name):
    try:
        return ZoneInfo(name) if ZoneInfo else timezone.utc
    except Exception:
        return timezone.utc


def _uuid(s):
    return bool(re.fullmatch(r"[0-9a-fA-F-]{36}", str(s or "")))


def _zeit(iso):
    """ISO → „27.10. 14:35“ in Dubai-Zeit (so rechnet Prophos), None bleibt None."""
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t.astimezone(_tz("Asia/Dubai")).strftime("%d.%m. %H:%M")
    except (TypeError, ValueError):
        return str(iso)[:16]


def _kurz(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[:n - 1] + "…"


def maskieren(s):
    """REIN RECHNEND: Ziffernfolgen ab 6 Stellen (Kontonummern, Logins) → „…1234“ — fürs Protokoll, nie Klartext."""
    return re.sub(r"\d{6,}", lambda m: "…" + m.group(0)[-4:], str(s or ""))


def tag_beginn_utc(jetzt=None):
    """REIN RECHNEND: Beginn des deutschen Tages (Prophos-Tagesgrenze, Winterzeit = 03:00 Dubai) als UTC-ISO."""
    jetzt = jetzt or datetime.now(timezone.utc)
    de = jetzt.astimezone(_tz("Europe/Berlin"))
    return de.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()


def _sb(methode, tabelle, params=None, body=None, prefer=None, timeout=12):
    r = A["_sb_anfrage"](methode, f"{A['SUPABASE_URL']}/rest/v1/{tabelle}", params=params or {}, json=body,
                         headers=A["_sb_headers"](prefer), timeout=timeout)
    A["_sb_pruefen"](r)
    try:
        return r.json()
    except ValueError:
        return None


def _in(menge):
    return "in.(" + ",".join(sorted(str(u) for u in menge)) + ")"


def _secret():
    s = os.environ.get("SUPPORT_SECRET") or ""
    if not s:   # abgeleitet vom Service-Key (liegt nur auf Railway) — eigener Zweck, damit das Token nie den Key verrät
        s = hmac.new((A.get("SUPABASE_SERVICE_KEY") or "").encode(), b"prophos-support-aktion", hashlib.sha256).hexdigest()
    return s.encode()


def token_bauen(daten, secret):
    """REIN RECHNEND: signiertes Aktions-Token (base64url(json).hmac)."""
    roh = base64.urlsafe_b64encode(json.dumps(daten, separators=(",", ":"), ensure_ascii=False).encode()).decode().rstrip("=")
    sig = hmac.new(secret, roh.encode(), hashlib.sha256).hexdigest()[:40]
    return f"{roh}.{sig}"


def token_lesen(token, secret, jetzt_s):
    """REIN RECHNEND: → (daten, None) oder (None, Fehlertext). Prüft Signatur und Ablauf."""
    try:
        roh, sig = str(token or "").split(".", 1)
    except ValueError:
        return None, "Token kaputt"
    soll = hmac.new(secret, roh.encode(), hashlib.sha256).hexdigest()[:40]
    if not hmac.compare_digest(soll, sig):
        return None, "Token ungültig"
    try:
        d = json.loads(base64.urlsafe_b64decode((roh + "=" * (-len(roh) % 4)).encode()))
    except Exception:
        return None, "Token kaputt"
    if not isinstance(d, dict) or float(d.get("e") or 0) < jetzt_s:
        return None, "Vorschlag abgelaufen (5 min) — frag einfach noch einmal"
    return d, None


def bild_typ(roh):
    """REIN RECHNEND: Bildformat an den ersten Bytes (nie dem Browser glauben) → Media-Type oder None."""
    if roh[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if roh[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if roh[:4] == b"RIFF" and roh[8:12] == b"WEBP":
        return "image/webp"
    if roh[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return None


def _wissen_text():
    """support_wissen.md — einmal gelesen, bei Änderung der Datei neu (nur nach einem Deploy)."""
    try:
        m = os.path.getmtime(WISSEN_DATEI)
        if _wissen["text"] is None or m != _wissen["mtime"]:
            with open(WISSEN_DATEI, encoding="utf-8") as f:
                _wissen["text"] = f.read()
            _wissen["mtime"] = m
    except OSError:
        if _wissen["text"] is None:
            _wissen["text"] = f"Du bist {NAME}, der Support von Prophos. Antworte kurz auf Deutsch."
    return _wissen["text"]


def _anthropic():
    if _client["c"] is None:
        import anthropic
        _client["c"] = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"), timeout=90.0, max_retries=2)
    return _client["c"]


def _lock(uid):
    with _locks_lock:
        if uid not in _unterhaltung_locks:
            if len(_unterhaltung_locks) > 2000:
                _unterhaltung_locks.clear()
            _unterhaltung_locks[uid] = threading.Lock()
        return _unterhaltung_locks[uid]


# ── Rechte ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def sicht_menge(me, eingeschraenkt, verwalter, zugang_sicht, ht_menge):
    """REIN RECHNEND (testbar): erlaubte user_ids des Chats. eingeschraenkt = g.admin_sicht (None = im Admin unbeschränkt), verwalter =
    Verwalter einer Gruppe, zugang_sicht = support_zugang.sicht, ht_menge = Funktion → IDs der Standard-Sicht/des Chips (nur gerufen,
    wenn gebraucht). Er selbst gehört immer dazu."""
    me = str(me)
    if eingeschraenkt is not None:
        return frozenset(str(u) for u in eingeschraenkt) | {me} if verwalter else frozenset({me})
    if zugang_sicht == "alle":
        return frozenset(str(u) for u in (ht_menge() or ())) | {me}
    return frozenset({me})


def _ht_menge():
    """Standard-Sicht wie /admin/* für einen unbeschränkten Login: ?gruppe= (Chip) → diese Gruppe, sonst Hermann Technologies ohne die
    ausgeblendeten IDs (ADMIN_EXCLUDE + Verwalter-Gruppen, _wd_personen). Der Chip gilt hier auch für POST (der Chat fragt per POST)."""
    gp = str(request.args.get("gruppe") or "").strip().lower()
    if gp:
        daten = A["admin_gruppen_daten"]()
        alle = ()
        if A["admin_gruppe_ist_ht"](gp, daten):
            r = A["_auth_liste_anfrage"]()
            if r.status_code != 200:
                raise RuntimeError("Auth-Liste nicht lesbar")
            alle = [str(u.get("id")) for u in (r.json() or {}).get("users", []) if u.get("id")]
        m = A["admin_gruppe_filter_menge"](gp, daten, alle)
        if m is not None:
            return m
    disp, excluded = A["_wd_personen"]()
    return set(disp) - set(excluded)


def _zugang(uid):
    """support_zugang-Zeile → (an, tageslimit, sicht). Tabelle fehlt / nicht lesbar → aus."""
    try:
        z = _sb("GET", "support_zugang", {"select": "an,tageslimit,sicht", "user_id": f"eq.{uid}", "limit": "1"}) or []
    except Exception:
        return False, 0, "eigene"
    if not z:
        return False, 0, "eigene"
    return bool(z[0].get("an")), int(z[0].get("tageslimit") or TAGESLIMIT_STANDARD), str(z[0].get("sicht") or "eigene")


def _login():
    """→ (uid, menge, zugang, None) oder (None, None, None, (resp, code)). Menge = erlaubte user_ids (frozenset), zugang =
    (an, tageslimit, sicht). Ist der Chat für die ID aus, ist die Menge nur sie selbst."""
    me, err = A["_wd_login"]()
    if err:
        return None, None, None, err
    zugang = _zugang(str(me))
    try:
        menge = sicht_menge(me, A["_admin_eingeschraenkt"](), A["_admin_verwalter"](), zugang[2] if zugang[0] else "eigene", _ht_menge)
    except Exception as e:
        print(f"[support] ⚠️ Sicht nicht lesbar: {type(e).__name__}: {e}", flush=True)
        return None, None, None, (jsonify({"ok": False, "msg": "Anmeldung nicht prüfbar — gleich noch einmal"}), 502)
    return str(me), menge, zugang, None


def _fragen_heute(uid=None):
    p = {"select": "id", "art": "eq.frage", "at": f"gte.{tag_beginn_utc()}", "limit": "2000"}
    if uid:
        p["user_id"] = f"eq.{uid}"
    try:
        return len(_sb("GET", "support_log", p) or [])
    except Exception:
        return 0


def _log(uid, art, **kw):
    z = {"user_id": uid, "art": art}
    for k, v in kw.items():
        if k in ("frage", "antwort"):
            v = _kurz(maskieren(v), 500 if k == "frage" else 1000)
        z[k] = v
    try:
        _sb("POST", "support_log", body=z, prefer="return=minimal")
    except Exception as e:
        print(f"[support] ⚠️ Log nicht geschrieben: {type(e).__name__}", flush=True)


def _namen(menge):
    """user_id → Anzeigename, nur für die erlaubte Menge (Verwalter sieht Namen seiner Gruppe)."""
    try:
        disp, _ = A["_wd_personen"]()
    except Exception:
        disp = {}
    return {u: disp.get(u) or u[:8] for u in menge}


# ── Werkzeuge ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Reihenfolge und Text fest (Teil des gecachten Präfixes). Das Modell gibt nie eine user_id an.

TOOLS = [
    {"name": "meine_trades",
     "description": "Trades (Pläne) des Nutzers bzw. seiner Gruppe: heute und die letzten Tage, laufende immer. Mit Konto, Firma, Weg, "
                    "Status (geplant/läuft/Überprüfen/abgehakt), Startzeit (Dubai), Start-Fehler und Ende-Grund.",
     "input_schema": {"type": "object", "properties": {
         "tage": {"type": "integer", "description": "1 = nur heute, 2 = seit gestern … (höchstens 7)"},
         "status": {"type": "string", "enum": ["alle", "geplant", "läuft", "Überprüfen", "abgehakt"]},
         "suche": {"type": "string", "description": "Teil des Konto-Namens oder der Firma (optional)"},
         "person": {"type": "string", "description": "nur diese Person (Teil des Namens) — nur wenn du mehrere IDs siehst"}},
         "additionalProperties": False}},
    {"name": "trade_details",
     "description": "Alles zu EINEM Trade: Start-Fehler mit voller Meldung, Sperren, Ende/Endlesung, Live-Stand, die letzten Aufträge an "
                    "den PC (order_signale) und Fehlstarts von Puls.",
     "input_schema": {"type": "object", "properties": {"plan_id": {"type": "string"}}, "required": ["plan_id"],
                      "additionalProperties": False}},
    {"name": "meine_konten",
     "description": "Konten des Nutzers bzw. seiner Gruppe mit Firma, Größe, Art, letzter Balance-Lesung (Wert + Zeit + Quelle), "
                    "Auto-Planer an/aus, Ziel erreicht, wartet auf Payout. External ID nur gekürzt.",
     "input_schema": {"type": "object", "properties": {
         "suche": {"type": "string", "description": "Teil des Konto-Namens oder der Firma (optional)"},
         "person": {"type": "string", "description": "nur diese Person (Teil des Namens) — nur wenn du mehrere IDs siehst"}},
         "additionalProperties": False}},
    {"name": "letzte_fehler",
     "description": "Letzte Fehlstarts von Puls und fehlgeschlagene Aufträge an den PC (Meldung, Schritt, Konto, PC).",
     "input_schema": {"type": "object", "properties": {
         "stunden": {"type": "integer", "description": "Zeitraum in Stunden (Standard 24, höchstens 72)"},
         "person": {"type": "string", "description": "nur diese Person (Teil des Namens) — nur wenn du mehrere IDs siehst"}},
         "additionalProperties": False}},
    {"name": "pc_stand",
     "description": "PCs des Nutzers bzw. seiner Gruppe: läuft der Prophos-Tab (Lebenszeichen), seit wann aus, Build.",
     "input_schema": {"type": "object", "properties": {"person": {"type": "string", "description": "nur diese Person (Teil des Namens) — nur wenn du mehrere IDs siehst"}}, "additionalProperties": False}},
    {"name": "auftrag_stand",
     "description": "Stand eines Auftrags an den PC (z. B. nach balance_lesen): wartet/läuft/fertig/fehler + Ergebnis.",
     "input_schema": {"type": "object", "properties": {"signal_id": {"type": "string"}}, "required": ["signal_id"],
                      "additionalProperties": False}},
    {"name": "trade_loeschen",
     "description": "HANDGRIFF (nur Vorschlag mit Bestätigen-Knopf): einen GEPLANTEN, noch nicht gestarteten Trade löschen. Laufende "
                    "oder gestartete Trades gehen nicht.",
     "input_schema": {"type": "object", "properties": {"plan_id": {"type": "string"}}, "required": ["plan_id"],
                      "additionalProperties": False}},
    {"name": "trade_beendet_pruefen",
     "description": "HANDGRIFF (nur Vorschlag mit Bestätigen-Knopf): Puls schaut am PC nach, ob ein LAUFENDER Trade schon zu ist (dann "
                    "geht er nach Überprüfen), bzw. liest bei einem Trade in Überprüfen das Ende nach. Schließt nie eine Position. Nur "
                    "Orbit V2 und von Puls gestartete Topstep-V2-Trades.",
     "input_schema": {"type": "object", "properties": {"plan_id": {"type": "string"}}, "required": ["plan_id"],
                      "additionalProperties": False}},
    {"name": "balance_lesen",
     "description": "HANDGRIFF (nur Vorschlag mit Bestätigen-Knopf): Puls bzw. Echo liest am PC die Balance eines Kontos neu.",
     "input_schema": {"type": "object", "properties": {"account_id": {"type": "string"}}, "required": ["account_id"],
                      "additionalProperties": False}},
    {"name": "tab_neu_laden",
     "description": "HANDGRIFF (nur Vorschlag mit Bestätigen-Knopf): der Prophos-Tab an einem PC lädt im nächsten ruhigen Moment neu "
                    "(hilft bei altem Stand/Hänger). pc = Kennung aus pc_stand (pc-…).",
     "input_schema": {"type": "object", "properties": {"pc": {"type": "string"}}, "required": ["pc"],
                      "additionalProperties": False}},
]
HANDGRIFFE = ("trade_loeschen", "trade_beendet_pruefen", "balance_lesen", "tab_neu_laden")

PLAN_SPALTEN = ("id,user_id,master_name,master_firm,route,status,planned_for,start_um,start_um_gestartet_at,started_at,ended_at,"
                "richtung,master_contracts,master_pl,winning_day,auto_plan,auto_bestaetigt_at,master_account_id,"
                "start_fehler:mt5_baseline->start_fehler,start_sperre:mt5_baseline->start_sperre,final:mt5_baseline->final")


def _person_menge(inp, ctx):
    """Optionaler Personen-Filter der Lese-Werkzeuge: Teil des Namens → Teilmenge der ERLAUBTEN Menge (nie darüber hinaus)."""
    p = str(inp.get("person") or "").strip().lower()
    if not p or len(ctx["menge"]) == 1:
        return ctx["menge"], None
    sub = frozenset(u for u in ctx["menge"] if p in str(ctx["namen"].get(u) or "").lower())
    return (sub, None) if sub else (None, f"Keine Person „{inp.get('person')}“ in deiner Sicht")


def _plan_zeile(p, namen):
    sf = p.get("start_fehler") if isinstance(p.get("start_fehler"), dict) else None
    fin = p.get("final") if isinstance(p.get("final"), dict) else None
    z = {"plan_id": p.get("id"), "konto": p.get("master_name"), "firma": p.get("master_firm"),
         "weg": ROUTE_TEXT.get(p.get("route"), p.get("route")), "status": STATUS_TEXT.get(p.get("status"), p.get("status")),
         "tag": p.get("planned_for"), "start": _zeit(p.get("start_um")), "richtung": p.get("richtung"),
         "kontrakte": p.get("master_contracts")}
    if len(namen) > 1:
        z["person"] = namen.get(str(p.get("user_id")), "?")
    if p.get("status") == "planned":
        z["start_laeuft_gerade"] = bool(p.get("start_um_gestartet_at"))
        if p.get("auto_plan"):
            z["bestaetigt"] = bool(p.get("auto_bestaetigt_at"))
    if p.get("started_at"):
        z["gestartet"] = _zeit(p.get("started_at"))
    if p.get("ended_at"):
        z["zu"] = _zeit(p.get("ended_at"))
    if p.get("master_pl") is not None:
        z["pnl"] = p.get("master_pl")
    if p.get("winning_day"):
        z["winning_day"] = True
    if sf:
        z["start_fehler"] = _kurz(sf.get("msg"), 300)
    if p.get("start_sperre"):
        z["start_sperre"] = _kurz(json.dumps(p.get("start_sperre"), ensure_ascii=False), 200)
    if fin and fin.get("grund"):
        z["ende_grund"] = fin.get("grund")
    return z


def _plan_holen(pid, menge, spalten=PLAN_SPALTEN):
    if not _uuid(pid):
        return None, "plan_id ungültig"
    rows = _sb("GET", "trade_plans", {"select": spalten, "id": f"eq.{pid}", "limit": "1"}) or []
    if not rows or str(rows[0].get("user_id")) not in menge:
        return None, "Diesen Trade gibt es für dich nicht (falsche ID oder nicht deiner)"
    return rows[0], None


def _konto_holen(aid, menge):
    if not _uuid(aid):
        return None, "account_id ungültig"
    rows = _sb("GET", "accounts", {"select": "id,user_id,name,firm,external_id,account_type", "id": f"eq.{aid}", "limit": "1"}) or []
    if not rows or str(rows[0].get("user_id")) not in menge:
        return None, "Dieses Konto gibt es für dich nicht (falsche ID oder nicht deins)"
    return rows[0], None


def t_meine_trades(inp, ctx):
    tage = max(1, min(7, int(inp.get("tage") or 1)))
    ab = (datetime.now(_tz("Europe/Berlin")) - timedelta(days=tage - 1)).date().isoformat()
    menge, f = _person_menge(inp, ctx)
    if f:
        return {"fehler": f}
    p = {"select": PLAN_SPALTEN, "user_id": _in(menge), "or": f"(planned_for.gte.{ab},status.eq.open)",
         "order": "start_um.desc.nullslast", "limit": "200"}
    st = {"geplant": "planned", "läuft": "open", "Überprüfen": "review", "abgehakt": "completed"}.get(str(inp.get("status") or ""))
    if st:
        p["status"] = f"eq.{st}"
    rows = _sb("GET", "trade_plans", p) or []
    such = str(inp.get("suche") or "").strip().lower()
    if such:
        rows = [r for r in rows if such in f"{r.get('master_name') or ''} {r.get('master_firm') or ''}".lower()]
    aus = {"ab_tag": ab, "anzahl": len(rows), "trades": [_plan_zeile(r, ctx["namen"]) for r in rows[:50]]}
    if len(rows) > 50:
        aus["hinweis"] = "Nur die 50 jüngsten gezeigt — mit person/suche/status eingrenzen"
    return aus


def t_trade_details(inp, ctx):
    p, f = _plan_holen(str(inp.get("plan_id") or "").strip(), ctx["menge"],
                       PLAN_SPALTEN + ",live:mt5_baseline->live,tv:mt5_baseline->tv,manuell:mt5_baseline->manuell")
    if f:
        return {"fehler": f}
    z = _plan_zeile(p, ctx["namen"])
    sf = p.get("start_fehler") if isinstance(p.get("start_fehler"), dict) else None
    if sf:
        z["start_fehler"] = {"meldung": _kurz(sf.get("msg"), 700), "um": _zeit(sf.get("at")), "pc": sf.get("pc"),
                             "status": sf.get("status")}
    fin = p.get("final") if isinstance(p.get("final"), dict) else None
    if fin:
        z["ende"] = {k: fin.get(k) for k in ("grund", "today_pnl", "balance_end", "quelle") if fin.get(k) is not None}
        z["ende"]["um"] = _zeit(fin.get("at"))
    live = p.get("live") if isinstance(p.get("live"), dict) else None
    if live:
        z["live"] = {"offen": live.get("offen"), "stand": _zeit(live.get("at"))}
    if isinstance(p.get("manuell"), dict):
        z["manuelle_arbeit"] = _kurz(p["manuell"].get("notiz"), 200)
    sig = _sb("GET", "order_signale", {"select": "id,status,pc,created_at,updated_at,aktion:params->>aktion,ergebnis",
                                       "plan_id": f"eq.{p['id']}", "order": "created_at.desc", "limit": "6"}) or []
    z["auftraege"] = [{"signal_id": s.get("id"), "aktion": s.get("aktion"), "status": s.get("status"), "pc": s.get("pc"),
                       "um": _zeit(s.get("created_at")),
                       "ergebnis": _kurz((s.get("ergebnis") or {}).get("msg") if isinstance(s.get("ergebnis"), dict)
                                         else s.get("ergebnis"), 300)} for s in sig]
    fs = _sb("GET", "puls_fehlstarts", {"select": "at,schritt,msg,pc", "plan_id": f"eq.{p['id']}", "order": "at.desc", "limit": "5"}) or []
    z["fehlstarts"] = [{"um": _zeit(x.get("at")), "schritt": x.get("schritt"), "pc": x.get("pc"),
                        "meldung": _kurz(re.sub(r"\[.*$", "", str(x.get("msg") or "")), 400)} for x in fs]
    return z


def t_meine_konten(inp, ctx):
    menge, f = _person_menge(inp, ctx)
    if f:
        return {"fehler": f}
    rows = _sb("GET", "accounts", {
        "select": "id,user_id,name,firm,account_type,account_size,balance,tv_balance,tv_balance_at,tv_balance_quelle,meta_api_balance,"
                  "meta_api_last_check,topstep_balance,topstep_last_check,external_id,auto_planer,waiting_payout_since,ziel_erreicht_at",
        "user_id": _in(menge), "order": "name.asc", "limit": "600"}) or []
    such = str(inp.get("suche") or "").strip().lower()
    if such:
        rows = [r for r in rows if such in f"{r.get('name') or ''} {r.get('firm') or ''}".lower()]
    aus = []
    for r in rows[:60]:
        lesungen = [(r.get("tv_balance_at"), r.get("tv_balance"), r.get("tv_balance_quelle") or "TradingView"),
                    (r.get("meta_api_last_check"), r.get("meta_api_balance"), "MT5"),
                    (r.get("topstep_last_check"), r.get("topstep_balance"), "TopstepX")]
        lesungen = [x for x in lesungen if x[0] and x[1] is not None]
        letzte = max(lesungen, key=lambda x: str(x[0])) if lesungen else None
        z = {"account_id": r.get("id"), "konto": r.get("name"), "firma": r.get("firm"), "art": r.get("account_type"),
             "groesse": r.get("account_size"), "balance": letzte[1] if letzte else r.get("balance"),
             "gelesen": _zeit(letzte[0]) if letzte else None, "quelle": letzte[2] if letzte else "von Hand",
             "external_id": ("…" + str(r.get("external_id"))[-4:]) if r.get("external_id") else None,
             "auto_planer": r.get("auto_planer")}
        if len(ctx["namen"]) > 1:
            z["person"] = ctx["namen"].get(str(r.get("user_id")), "?")
        if r.get("ziel_erreicht_at"):
            z["ziel_erreicht"] = _zeit(r.get("ziel_erreicht_at"))
        if r.get("waiting_payout_since"):
            z["wartet_auf_payout_seit"] = _zeit(r.get("waiting_payout_since"))
        aus.append(z)
    erg = {"anzahl": len(rows), "konten": aus}
    if len(rows) > 60:
        erg["hinweis"] = "Nur 60 gezeigt — mit person/suche eingrenzen"
    return erg


def t_letzte_fehler(inp, ctx):
    std = max(1, min(72, int(inp.get("stunden") or 24)))
    ab = (datetime.now(timezone.utc) - timedelta(hours=std)).isoformat()
    menge, f = _person_menge(inp, ctx)
    if f:
        return {"fehler": f}
    fs = _sb("GET", "puls_fehlstarts", {"select": "at,plan_id,user_id,firma,konto,pc,schritt,msg", "user_id": _in(menge),
                                        "at": f"gte.{ab}", "order": "at.desc", "limit": "25"}) or []
    sg = _sb("GET", "order_signale", {"select": "id,plan_id,user_id,pc,updated_at,aktion:params->>aktion,ergebnis", "user_id": _in(menge),
                                      "status": "eq.fehler", "updated_at": f"gte.{ab}", "order": "updated_at.desc", "limit": "15"}) or []
    return {"stunden": std,
            "fehlstarts": [{"um": _zeit(x.get("at")), "plan_id": x.get("plan_id"), "firma": x.get("firma"),
                            **({"person": ctx["namen"].get(str(x.get("user_id")), "?")} if len(ctx["namen"]) > 1 else {}),
                            "konto": maskieren(x.get("konto")), "pc": x.get("pc"), "schritt": x.get("schritt"),
                            "meldung": _kurz(re.sub(r"\[.*$", "", str(x.get("msg") or "")), 350)} for x in fs],
            "auftraege_fehler": [{"um": _zeit(s.get("updated_at")), "aktion": s.get("aktion"), "plan": s.get("plan_id"),
                                  **({"person": ctx["namen"].get(str(s.get("user_id")), "?")} if len(ctx["namen"]) > 1 else {}),
                                  "pc": s.get("pc"),
                                  "meldung": _kurz((s.get("ergebnis") or {}).get("msg") if isinstance(s.get("ergebnis"), dict)
                                                   else s.get("ergebnis"), 300)} for s in sg]}


def t_pc_stand(inp, ctx):
    menge, f = _person_menge(inp, ctx)
    if f:
        return {"fehler": f}
    rows = _sb("GET", "mt5_live", {"select": "id,pc_name,updated_at,user_id:status->>user_id,tab_build:status->>tab_build,"
                                             "bot_version:status->>bot_version", "status->>user_id": _in(menge),
                                   "order": "updated_at.desc", "limit": "400"}) or []
    stand = A["pc_stand_zusammenfassen"](rows, datetime.now(timezone.utc))
    try:
        namen = {str(n.get("pc_id")): n.get("name") for n in (_sb("GET", "pc_namen", {"select": "pc_id,name"}) or [])}
    except Exception:
        namen = {}
    aus = []
    for uid, s in stand.items():
        for pc, x in (s.get("je_pc") or {}).items():
            alt = int(x.get("alt_s") or 0)
            z = {"pc": pc, "name": namen.get(pc), "prophos_tab": "läuft" if x.get("lebt") else ("aus" if alt >= A["PC_AUS_S"] else "hängt?"),
                 "letztes_lebenszeichen": _zeit(x.get("zuletzt")), "vor_min": alt // 60, "build": x.get("tab_build")}
            if len(ctx["namen"]) > 1:
                z["person"] = ctx["namen"].get(uid, "?")
            aus.append(z)
    return {"pcs": aus} if aus else {"pcs": [], "hinweis": "Kein PC dieser ID hat je ein Lebenszeichen geschickt"}


def t_auftrag_stand(inp, ctx):
    sid = str(inp.get("signal_id") or "").strip()
    if not _uuid(sid):
        return {"fehler": "signal_id ungültig"}
    rows = _sb("GET", "order_signale", {"select": "id,user_id,status,pc,created_at,updated_at,aktion:params->>aktion,ergebnis",
                                        "id": f"eq.{sid}", "limit": "1"}) or []
    if not rows or str(rows[0].get("user_id")) not in ctx["menge"]:
        return {"fehler": "Auftrag nicht gefunden"}
    s = rows[0]
    e = s.get("ergebnis") if isinstance(s.get("ergebnis"), dict) else {}
    return {"aktion": s.get("aktion"), "status": s.get("status"), "pc": s.get("pc"), "angelegt": _zeit(s.get("created_at")),
            "stand": _zeit(s.get("updated_at")), "meldung": _kurz(e.get("msg") or e.get("grund"), 400),
            "balance": e.get("balance")}


# Handgriffe: Vorschau prüfen (dieselben Bedingungen wie beim Ausführen), Token anlegen. Ausgeführt wird NUR in /support/aktion.

def _vorschlag(ctx, aktion, objekt, titel, text, extra=None):
    tok = token_bauen({"u": ctx["uid"], "a": aktion, "o": objekt, "x": extra or {}, "k": ctx["unterhaltung_id"],
                       "e": int(time.time()) + AKTION_GUELTIG_S, "n": uuid.uuid4().hex[:12]}, _secret())
    ctx["vorschlaege"].append({"token": tok, "aktion": aktion, "titel": titel, "text": text})
    return {"vorschlag_angelegt": True, "text": text,
            "hinweis": "Noch NICHTS ausgeführt. Der Nutzer sieht jetzt einen Bestätigen-Knopf (5 min gültig). Sag ihm in einem Satz, was "
                       "beim Bestätigen passiert."}


# Lösch-Riegel wie der Archiv-Sweep (ap_archiv_sweep, S2-Befund 27.10.2026): ein Orbit-Plan mit gesendeter Order (orbit_gesendet_at) ist
# noch „planned", bis Duplikum/Fill da ist — gelöscht stünde eine Position ohne Plan und ohne Wächter am Markt.
LOESCH_RIEGEL = {"status": "eq.planned", "start_um_gestartet_at": "is.null", "started_at": "is.null", "orbit_gesendet_at": "is.null"}
FARMER_NOTIZ = "Winning-Day-Farmer"


def loesch_grund(p):
    """REIN RECHNEND: warum ein Plan NICHT gelöscht werden darf (Text) oder None — dieselben Bedingungen wie LOESCH_RIEGEL."""
    if p.get("status") != "planned":
        return f"der Trade ist {STATUS_TEXT.get(p.get('status'), p.get('status'))}, nur geplante lassen sich löschen"
    if p.get("start_um_gestartet_at"):
        return "der Start läuft gerade (Puls ist dran) — erst abwarten"
    if p.get("started_at") or p.get("orbit_gesendet_at"):
        return "die Order ist schon raus — der Trade läuft gleich bzw. schon, löschen geht nicht mehr"
    return None


def _offener_auftrag(plan_id):
    """Offener Auftrag an den PC für diesen Plan (order_signale wartet/laeuft)? Ein Hand-Start vom Mac/Handy (Orbit-Warteschlange,
    Echo-Remote) legt ihn an, ohne dass start_um_gestartet_at sicher gesetzt ist — bei „laeuft" klickt Puls gerade (S2-Empfehlung
    27.10.2026). Bewusst JEDER offene Auftrag, nicht nur Starts: lieber einmal zu streng. Lesefehler → als offen werten (nie raten)."""
    try:
        return bool(_sb("GET", "order_signale", {"select": "id", "plan_id": f"eq.{plan_id}", "status": "in.(wartet,laeuft)", "limit": "1"}))
    except Exception:
        return True


def _farmer_tagesplan_laeuft(plan_id, uid):
    """Steht der Farmer-Plan in einem LAUFENDEN wd_tagesplan? (nur für die Vorschau — ausgeführt wird über tagesplan_austragen)"""
    ab = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
    for x in _sb("GET", "wd_tagesplan", {"select": "konten,status", "user_id": f"eq.{uid}", "tag": f"gte.{ab}", "status": "eq.laeuft"}) or []:
        if any(isinstance(k, dict) and str(k.get("plan_id")) == str(plan_id) for k in (x.get("konten") or [])):
            return True
    return False


def tagesplan_austragen(plan_id, uid, hinweis):
    """Farmer-Plan aus dem WD-Tagesplan austragen → (ok, laeuft). 1:1 der Papierkorb-Weg tpWdTagesplanAustragen (prophos.html, .1755/.1756,
    Master 27.10.2026: „gleicher Weg wie der Papierkorb, nicht neu erfinden"): plan_id/status/start_um null, aktiv false, Hinweis; ein
    laufender Block wird nie angefasst (ok False, laeuft True); 0 geschriebene Zeilen = Block kam eben in „läuft". ok = jeder Tagesplan mit
    dieser plan_id ist ausgetragen (oder es gab keinen) — nur dann darf gelöscht werden."""
    ok, laeuft = True, False
    try:
        ab = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
        for x in _sb("GET", "wd_tagesplan", {"select": "tag,user_id,konten,status", "user_id": f"eq.{uid}", "tag": f"gte.{ab}"}) or []:
            konten = x.get("konten") or []
            if not any(isinstance(k, dict) and str(k.get("plan_id")) == str(plan_id) for k in konten):
                continue
            if x.get("status") == "laeuft":
                ok, laeuft = False, True
                continue
            konten = [dict(k, plan_id=None, status=None, start_um=None, aktiv=False, hinweis=hinweis)
                      if isinstance(k, dict) and str(k.get("plan_id")) == str(plan_id) else k for k in konten]
            status = x.get("status") if any(isinstance(k, dict) and k.get("aktiv") is not False for k in konten) else "leer"
            geschrieben = A["sb_update"]("wd_tagesplan", {"tag": f"eq.{x.get('tag')}", "user_id": f"eq.{uid}", "status": "neq.laeuft"},
                                         {"konten": konten, "status": status, "updated_at": datetime.now(timezone.utc).isoformat()})
            if not geschrieben:
                ok, laeuft = False, True
    except Exception as e:
        print(f"[support] ⚠️ Tagesplan nicht austragbar ({str(plan_id)[:8]}): {type(e).__name__}: {e}", flush=True)
        ok = False
    return ok, laeuft


def h_trade_loeschen(inp, ctx):
    p, f = _plan_holen(str(inp.get("plan_id") or "").strip(), ctx["menge"], PLAN_SPALTEN + ",orbit_gesendet_at,notes")
    if f:
        return {"fehler": f}
    g = loesch_grund(p)
    if g:
        return {"fehler": f"Geht nicht: {g}"}
    if _offener_auftrag(p["id"]):
        return {"fehler": "Geht nicht: für diesen Trade läuft gerade ein Auftrag am PC (z. B. ein Start) — erst abwarten"}
    if (p.get("notes") or "") == FARMER_NOTIZ and _farmer_tagesplan_laeuft(p["id"], p.get("user_id")):
        return {"fehler": "Geht nicht: der Winning-Day-Block dieser ID läuft gerade — nach dem Block noch einmal"}
    txt = f"Trade „{p.get('master_name')}“ ({p.get('master_firm')}, Start {_zeit(p.get('start_um')) or 'ohne Zeit'}) wird gelöscht."
    return _vorschlag(ctx, "trade_loeschen", p["id"], "Trade löschen", txt)


def h_trade_beendet_pruefen(inp, ctx):
    p, f = _plan_holen(str(inp.get("plan_id") or "").strip(), ctx["menge"], "id,user_id,route,status,master_name,mt5_baseline")
    if f:
        return {"fehler": f}
    _zeile, fehler = A["_wd_endlesung_signal"](p)
    if fehler:
        return {"fehler": f"Geht nicht: {fehler[1]}"}
    txt = (f"Puls schaut am PC nach, ob „{p.get('master_name')}“ schon zu ist — wenn ja, geht der Trade nach Überprüfen."
           if p.get("status") == "open" else f"Puls liest das Ende von „{p.get('master_name')}“ am PC nach.")
    return _vorschlag(ctx, "trade_beendet_pruefen", p["id"], "Am PC prüfen", txt)


def h_balance_lesen(inp, ctx):
    k, f = _konto_holen(str(inp.get("account_id") or "").strip(), ctx["menge"])
    if f:
        return {"fehler": f}
    ml = _sb("GET", "mt5_links", {"select": "mt5_login", "account_id": f"eq.{k['id']}", "limit": "1"}) or []
    zeile, fehler = A["_wd_balance_signal"](k, (ml[0] if ml else {}).get("mt5_login") or "")
    if fehler:
        return {"fehler": f"Geht nicht: {fehler[1]}"}
    return _vorschlag(ctx, "balance_lesen", k["id"], "Balance lesen",
                      f"Am PC wird die Balance von „{k.get('name')}“ neu gelesen "
                      f"({'MT5-Terminal' if zeile['params']['aktion'] == 'mt5_balance' else 'Puls im Browser'}).")


def h_tab_neu_laden(inp, ctx):
    pc = str(inp.get("pc") or "").strip().lower()
    if not re.fullmatch(r"pc-[a-z0-9]{3,24}", pc):
        return {"fehler": "pc ungültig (Kennung pc-… aus pc_stand)"}
    rows = _sb("GET", "mt5_live", {"select": "user_id:status->>user_id", "pc_name": f"eq.{pc}", "status->>user_id": _in(ctx["menge"]),
                                   "order": "updated_at.desc", "limit": "1"}) or []
    if not rows:
        return {"fehler": "Diesen PC gibt es für dich nicht"}
    return _vorschlag(ctx, "tab_neu_laden", pc, "Tab neu laden",
                      f"Der Prophos-Tab an {pc} lädt im nächsten ruhigen Moment neu (keine Order).", {"uid": rows[0].get("user_id")})


WERKZEUG = {"meine_trades": t_meine_trades, "trade_details": t_trade_details, "meine_konten": t_meine_konten,
            "letzte_fehler": t_letzte_fehler, "pc_stand": t_pc_stand, "auftrag_stand": t_auftrag_stand,
            "trade_loeschen": h_trade_loeschen, "trade_beendet_pruefen": h_trade_beendet_pruefen, "balance_lesen": h_balance_lesen,
            "tab_neu_laden": h_tab_neu_laden}


def _werkzeug_ausfuehren(name, inp, ctx):
    fn = WERKZEUG.get(name)
    if not fn:
        return {"fehler": f"Werkzeug {name} gibt es nicht"}, True
    if not isinstance(inp, dict):
        return {"fehler": "Eingabe ungültig"}, True
    try:
        erg = fn(inp, ctx)
    except Exception as e:
        print(f"[support] ⚠️ Werkzeug {name}: {type(e).__name__}: {e}", flush=True)
        return {"fehler": f"Gerade nicht lesbar ({type(e).__name__}) — später noch einmal"}, True
    return erg, bool(isinstance(erg, dict) and erg.get("fehler"))


def aktion_ausfuehren(d, menge):
    """Bestätigter Handgriff → (ok, text, signal_id). Dieselben Bedingungen wie in der Vorschau, noch einmal frisch geprüft."""
    a, o = d.get("a"), str(d.get("o") or "")
    if a == "trade_loeschen":
        if not _uuid(o):
            return False, "plan_id ungültig", None
        p, f = _plan_holen(o, menge, "id,user_id,status,notes,start_um_gestartet_at,started_at,orbit_gesendet_at")
        if f:
            return False, f, None
        g = loesch_grund(p)
        if g:
            return False, f"Ging nicht mehr: {g}", None
        if _offener_auftrag(o):
            return False, "Ging nicht: für diesen Trade läuft gerade ein Auftrag am PC (z. B. ein Start) — nichts gelöscht, erst abwarten.", None
        # Farmer-Plan wie der Papierkorb (.1755/.1756): ERST aus dem Tagesplan austragen, nur wenn das klappt löschen — nie eine plan_id
        # im Tagesplan ohne Plan („Plan fehlt")
        if (p.get("notes") or "") == FARMER_NOTIZ:
            ok_a, laeuft = tagesplan_austragen(o, p.get("user_id"), "Plan per Support-Chat gelöscht")
            if not ok_a:
                return False, ("Der Winning-Day-Block dieser ID läuft gerade — nichts gelöscht. Nach dem Block noch einmal fragen."
                               if laeuft else "Tagesplan nicht austragbar — nichts gelöscht. Bitte gleich noch einmal."), None
        z = A["sb_delete"]("trade_plans", dict(LOESCH_RIEGEL, id=f"eq.{o}", user_id=_in(menge)))
        if not z:
            return False, "Ging nicht mehr: der Trade ist inzwischen gestartet, schon weg oder nicht deiner.", None
        return True, f"Trade „{z[0].get('master_name')}“ gelöscht.", None
    if a == "trade_beendet_pruefen":
        p, f = _plan_holen(o, menge, "id,user_id,route,status,master_name,mt5_baseline")
        if f:
            return False, f, None
        zeile, fehler = A["_wd_endlesung_signal"](p)
        if fehler:
            return False, fehler[1], None
        sig = A["sb_insert"]("order_signale", zeile)
        return True, "Auftrag an den PC geschickt — Puls schaut nach.", str((sig or {}).get("id") or "")
    if a == "balance_lesen":
        k, f = _konto_holen(o, menge)
        if f:
            return False, f, None
        ml = _sb("GET", "mt5_links", {"select": "mt5_login", "account_id": f"eq.{k['id']}", "limit": "1"}) or []
        zeile, fehler = A["_wd_balance_signal"](k, (ml[0] if ml else {}).get("mt5_login") or "")
        if fehler:
            return False, fehler[1], None
        if zeile["params"]["aktion"] == "mt5_balance":
            ort = A["_mt5_ort_fehler"](zeile["user_id"], zeile["params"]["login"])
            if ort:
                return False, ort, None
        zeile["params"]["von"] = "support"
        sig = A["sb_insert"]("order_signale", zeile)
        return True, f"Auftrag an den PC geschickt — die Balance von „{k.get('name')}“ wird gelesen.", str((sig or {}).get("id") or "")
    if a == "tab_neu_laden":
        uid = str((d.get("x") or {}).get("uid") or "")
        if uid not in menge or not re.fullmatch(r"pc-[a-z0-9]{3,24}", o):
            return False, "Diesen PC gibt es für dich nicht", None
        sig = A["sb_insert"]("order_signale", {"user_id": uid, "plan_id": f"tab:{o}", "status": "wartet",
                                               "params": {"aktion": "tab_neu_laden", "pc": o, "von": "support"}})
        return True, f"Auftrag an {o} geschickt — der Tab lädt im nächsten ruhigen Moment neu.", str((sig or {}).get("id") or "")
    return False, "Unbekannter Handgriff", None


# ── Verlauf + Bilder ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _storage_url(pfad):
    return f"{A['SUPABASE_URL']}/storage/v1/object/{BUCKET}/{pfad}"


def _storage_kopf(typ=None):
    k = A.get("SUPABASE_SERVICE_KEY") or ""
    h = {"apikey": k, "Authorization": f"Bearer {k}"}
    if typ:
        h["Content-Type"] = typ
    return h


def _bild_speichern(pfad, roh, typ):
    r = requests.post(_storage_url(pfad), data=roh, headers=dict(_storage_kopf(typ), **{"x-upsert": "false"}), timeout=20)
    if r.status_code >= 300:
        raise RuntimeError(f"Bild nicht gespeichert (HTTP {r.status_code})")


def _bild_laden(pfad):
    with _bild_cache_lock:
        if pfad in _bild_cache:
            return _bild_cache[pfad]
    r = requests.get(_storage_url(pfad), headers=_storage_kopf(), timeout=20)
    if r.status_code != 200:
        return None
    b64 = base64.b64encode(r.content).decode()
    with _bild_cache_lock:
        if len(_bild_cache) > 60:
            _bild_cache.clear()
        _bild_cache[pfad] = b64
    return b64


def _bilder_loeschen(pfade):
    if not pfade:
        return
    try:
        requests.delete(f"{A['SUPABASE_URL']}/storage/v1/object/{BUCKET}", json={"prefixes": list(pfade)},
                        headers=_storage_kopf("application/json"), timeout=20)
    except Exception as e:
        print(f"[support] ⚠️ Bilder nicht gelöscht: {type(e).__name__}", flush=True)
    with _bild_cache_lock:
        for p in pfade:
            _bild_cache.pop(p, None)


def _api_inhalt(inhalt):
    """Gespeicherte Blöcke → API-Blöcke: Platzhalter {type:'bild', pfad, typ} wird zum Bild-Block (base64 aus dem Bucket)."""
    aus = []
    for b in inhalt:
        if isinstance(b, dict) and b.get("type") == "bild":
            b64 = _bild_laden(b.get("pfad"))
            if b64 is None:
                raise RuntimeError("Bild abgelaufen")
            aus.append({"type": "image", "source": {"type": "base64", "media_type": b.get("typ") or "image/jpeg", "data": b64}})
        else:
            aus.append(b)
    return aus


def _verlauf(uid_unterh):
    rows = _sb("GET", "support_nachricht", {"select": "id,rolle,inhalt,sichtbar", "unterhaltung_id": f"eq.{uid_unterh}",
                                            "order": "id.asc", "limit": "400"}) or []
    return [{"role": r["rolle"], "content": json.loads(r["inhalt"]), "_sichtbar": r.get("sichtbar")} for r in rows]


def _nachricht_speichern(unterh, rolle, inhalt, text=None, bilder=None, aktionen=None, sichtbar=True):
    _sb("POST", "support_nachricht", body={"unterhaltung_id": unterh, "rolle": rolle,
                                           "inhalt": json.dumps(inhalt, ensure_ascii=False, separators=(",", ":")),
                                           "text": text, "bilder": bilder or [], "aktionen": aktionen, "sichtbar": sichtbar},
        prefer="return=minimal")


def _api_antwort(system, nachrichten, letzte_runde):
    """Ein Aufruf der Messages-API. Rohes JSON (Schlüssel-Reihenfolge bleibt — der Verlauf geht Zeichen für Zeichen gleich zurück)."""
    import anthropic
    c = _anthropic()
    kw = dict(model=MODELL, max_tokens=MAX_TOKENS, system=system, tools=TOOLS, messages=nachrichten)
    if _zusatz["an"]:
        # Effort + serverseitiger Rückfall bei einer Ablehnung (claude-api-Skill: Standard für Sonnet 5.5); über extra_body, damit
        # jede SDK-Version auf Railway die Felder durchreicht
        kw.update(extra_body={"output_config": {"effort": EFFORT}, "fallbacks": "default"},
                  extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"})
    if letzte_runde:
        kw["tool_choice"] = {"type": "none"}
    try:
        raw = c.messages.with_raw_response.create(**kw)
    except anthropic.BadRequestError as e:
        # Lehnt die API die Zusatzfelder ab (anderes Modell per SUPPORT_MODELL, Beta nicht frei): einmal ohne, und ab dann ohne
        if not _zusatz["an"] or not re.search(r"fallback|output_config|effort|beta", str(e), re.I):
            raise
        _zusatz["an"] = False
        print(f"[support] ⚠️ Zusatzfelder abgelehnt, weiter ohne: {_kurz(str(e), 200)}", flush=True)
        for k in ("extra_body", "extra_headers"):
            kw.pop(k, None)
        raw = c.messages.with_raw_response.create(**kw)
    hr = getattr(raw, "http_response", None)
    if hr is not None:
        return hr.json()
    return raw.parse().model_dump(mode="json", exclude_none=True)


def _mit_cache_marke(nachrichten):
    """Kopie, deren LETZTER Block die Cache-Marke trägt (zweiter Haltepunkt neben dem Systemtext) — gespeichert wird ohne Marke."""
    if not nachrichten:
        return nachrichten
    aus = list(nachrichten[:-1])
    letzte = dict(nachrichten[-1])
    bl = [dict(b) for b in letzte["content"]]
    if bl and bl[-1].get("type") in ("text", "tool_result", "image"):
        bl[-1]["cache_control"] = {"type": "ephemeral"}
    letzte["content"] = bl
    aus.append(letzte)
    return aus


def _kontext_zeile(ctx):
    jetzt = datetime.now(_tz("Asia/Dubai"))
    tag = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][jetzt.weekday()]
    wer = ctx["namen"].get(ctx["uid"], "?")
    sicht = ("nur die eigene ID" if len(ctx["menge"]) == 1
             else f"{len(ctx['menge'])} IDs (Personen: " + ", ".join(sorted(ctx["namen"].values())[:40]) + ")")
    return f"[Kontext — vom System, nicht vom Nutzer] Jetzt: {tag} {jetzt.strftime('%d.%m.%Y %H:%M')} Dubai. Login: {wer}. Sicht: {sicht}."


def support_aufraeumen():
    """Bilder > 7 Tage löschen (Unterhaltung wird dann geschlossen), Unterhaltungen > 30 Tage ohne Aktivität löschen. Höchstens alle 6 h,
    angestoßen von einer Chat-Anfrage (kein eigener Takt nötig)."""
    if time.time() - _aufraeumen["at"] < 6 * 3600:
        return
    _aufraeumen["at"] = time.time()
    try:
        grenze = (datetime.now(timezone.utc) - timedelta(days=BILD_TAGE)).isoformat()
        alt = _sb("GET", "support_nachricht", {"select": "id,unterhaltung_id,bilder", "at": f"lt.{grenze}", "bilder": "neq.{}",
                                               "limit": "300"}) or []
        pfade = [p for r in alt for p in (r.get("bilder") or [])]
        _bilder_loeschen(pfade)
        for uid_u in sorted({str(r["unterhaltung_id"]) for r in alt}):
            _sb("PATCH", "support_unterhaltung", {"id": f"eq.{uid_u}"}, {"geschlossen": True}, prefer="return=minimal")
        for r in alt:
            _sb("PATCH", "support_nachricht", {"id": f"eq.{r['id']}"}, {"bilder": []}, prefer="return=minimal")
        grenze2 = (datetime.now(timezone.utc) - timedelta(days=UNTERHALTUNG_TAGE)).isoformat()
        _sb("DELETE", "support_unterhaltung", {"updated_at": f"lt.{grenze2}"}, prefer="return=minimal")
        if alt:
            print(f"[support] aufgeräumt: {len(pfade)} Bilder, {len(alt)} Nachrichten", flush=True)
    except Exception as e:
        print(f"[support] ⚠️ Aufräumen: {type(e).__name__}: {e}", flush=True)


def _antwort_text(inhalt):
    return "\n\n".join(b.get("text", "") for b in inhalt if isinstance(b, dict) and b.get("type") == "text").strip()


# ── Routen ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def registrieren(app, ns):
    """Routen an die Flask-App hängen. ns = globals() von app.py (Supabase-Helfer, Auth)."""
    A.update(ns)

    @app.route("/support/stand", methods=["GET", "OPTIONS"])
    def support_stand():
        if request.method == "OPTIONS":
            return "", 200
        uid, menge, zugang, err = _login()
        if err:
            return err
        an, limit, _s = zugang
        if not an:
            return jsonify({"ok": True, "an": False})
        return jsonify({"ok": True, "an": True, "name": NAME, "limit": limit, "rest": max(0, limit - _fragen_heute(uid)),
                        "eingerichtet": bool(os.environ.get("ANTHROPIC_API_KEY")), "ids": len(menge)})

    @app.route("/support/unterhaltungen", methods=["GET", "OPTIONS"])
    def support_unterhaltungen():
        if request.method == "OPTIONS":
            return "", 200
        uid, _m, _z, err = _login()
        if err:
            return err
        try:
            rows = _sb("GET", "support_unterhaltung", {"select": "id,titel,geschlossen,updated_at", "user_id": f"eq.{uid}",
                                                       "order": "updated_at.desc", "limit": "30"}) or []
        except Exception as e:
            return jsonify({"ok": False, "msg": f"nicht lesbar ({type(e).__name__})"}), 502
        return jsonify({"ok": True, "liste": [{"id": r["id"], "titel": r.get("titel") or "Unterhaltung", "zu": r.get("geschlossen"),
                                               "um": _zeit(r.get("updated_at"))} for r in rows]})

    @app.route("/support/unterhaltung/<uid_u>", methods=["GET", "DELETE", "OPTIONS"])
    def support_unterhaltung(uid_u):
        if request.method == "OPTIONS":
            return "", 200
        uid, _m, _z, err = _login()
        if err:
            return err
        if not _uuid(uid_u):
            return jsonify({"ok": False, "msg": "id ungültig"}), 400
        try:
            u = _sb("GET", "support_unterhaltung", {"select": "id,titel,geschlossen", "id": f"eq.{uid_u}", "user_id": f"eq.{uid}"}) or []
            if not u:
                return jsonify({"ok": False, "msg": "Unterhaltung nicht gefunden"}), 404
            if request.method == "DELETE":
                b = _sb("GET", "support_nachricht", {"select": "bilder", "unterhaltung_id": f"eq.{uid_u}", "bilder": "neq.{}"}) or []
                _bilder_loeschen([p for r in b for p in (r.get("bilder") or [])])
                _sb("DELETE", "support_unterhaltung", {"id": f"eq.{uid_u}", "user_id": f"eq.{uid}"}, prefer="return=minimal")
                return jsonify({"ok": True})
            rows = _sb("GET", "support_nachricht", {"select": "id,rolle,text,bilder,aktionen,at", "unterhaltung_id": f"eq.{uid_u}",
                                                    "sichtbar": "eq.true", "order": "id.asc", "limit": "400"}) or []
        except Exception as e:
            return jsonify({"ok": False, "msg": f"nicht lesbar ({type(e).__name__})"}), 502
        jetzt = time.time()
        blasen = []
        for r in rows:
            akt = []
            for v in (r.get("aktionen") or []):
                d, f = token_lesen(v.get("token"), _secret(), jetzt)
                akt.append({"token": v.get("token") if d and not v.get("erledigt") else None, "titel": v.get("titel"),
                            "text": v.get("text"), "erledigt": v.get("erledigt"), "abgelaufen": bool(f) and not v.get("erledigt")})
            blasen.append({"rolle": r["rolle"], "text": r.get("text") or "", "bilder": len(r.get("bilder") or []), "aktionen": akt,
                           "um": _zeit(r.get("at"))})
        return jsonify({"ok": True, "titel": u[0].get("titel"), "zu": u[0].get("geschlossen"), "blasen": blasen})

    @app.route("/support/chat", methods=["POST", "OPTIONS"])
    def support_chat():
        if request.method == "OPTIONS":
            return "", 200
        uid, menge, zugang, err = _login()
        if err:
            return err
        an, limit, _s = zugang
        if not an:
            return jsonify({"ok": False, "msg": "Der Support-Chat ist für deine ID nicht freigeschaltet."}), 403
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return jsonify({"ok": False, "msg": "Lotse ist noch nicht eingerichtet — der Schlüssel fehlt noch. Frag so lange Finn.",
                            "nicht_eingerichtet": True}), 503
        if (request.content_length or 0) > 12_000_000:
            return jsonify({"ok": False, "msg": "Zu groß — höchstens 3 Bilder"}), 413
        d = request.get_json(silent=True) or {}
        frage = str(d.get("frage") or "").strip()[:FRAGE_MAX_ZEICHEN]
        bilder_in = d.get("bilder") if isinstance(d.get("bilder"), list) else []
        if not frage and not bilder_in:
            return jsonify({"ok": False, "msg": "Frage fehlt"}), 400
        if len(bilder_in) > BILD_MAX_JE_FRAGE:
            return jsonify({"ok": False, "msg": f"Höchstens {BILD_MAX_JE_FRAGE} Bilder je Nachricht"}), 400
        heute = _fragen_heute(uid)
        if heute >= limit:
            _log(uid, "limit", frage=frage)
            return jsonify({"ok": False, "msg": f"Tageslimit erreicht ({limit} Fragen) — morgen geht es weiter."}), 429
        if _fragen_heute() >= TAGESDECKEL:
            _log(uid, "limit", frage=frage)
            return jsonify({"ok": False, "msg": "Der Support macht für heute Pause (Tagesdeckel erreicht) — frag Finn."}), 429
        threading.Thread(target=support_aufraeumen, daemon=True).start()

        # Bilder prüfen (Format an den Bytes, Größe) — vor jeder Speicherung
        bilder = []
        for b in bilder_in:
            try:
                roh = base64.b64decode(str((b or {}).get("daten") or "").split(",")[-1], validate=False)
            except Exception:
                return jsonify({"ok": False, "msg": "Bild nicht lesbar"}), 400
            typ = bild_typ(roh)
            if not typ:
                return jsonify({"ok": False, "msg": "Nur JPEG, PNG, WebP oder GIF"}), 400
            if len(roh) > BILD_MAX_BYTES:
                return jsonify({"ok": False, "msg": "Bild zu groß (höchstens 2,5 MB nach dem Verkleinern)"}), 400
            w, h = int((b or {}).get("w") or 0), int((b or {}).get("h") or 0)
            bilder.append((roh, typ, f"{w}×{h}" if w and h else f"{len(roh) // 1024} KB"))

        unterh = str(d.get("unterhaltung_id") or "").strip()
        with _lock(unterh or uid):
            try:
                if unterh:
                    u = _sb("GET", "support_unterhaltung", {"select": "id,geschlossen", "id": f"eq.{unterh}", "user_id": f"eq.{uid}"}) or []
                    if not u:
                        return jsonify({"ok": False, "msg": "Unterhaltung nicht gefunden"}), 404
                    if u[0].get("geschlossen"):
                        return jsonify({"ok": False, "msg": "Diese Unterhaltung ist abgelaufen — starte eine neue.", "zu": True}), 409
                    verlauf = _verlauf(unterh)
                else:
                    titel = _kurz(re.sub(r"\s+", " ", frage) or "Screenshot", 60)
                    unterh = str((_sb("POST", "support_unterhaltung", body={"user_id": uid, "titel": maskieren(titel)},
                                      prefer="return=representation") or [{}])[0].get("id") or "")
                    if not unterh:
                        raise RuntimeError("Unterhaltung nicht angelegt")
                    verlauf = []
                fragen_bisher = sum(1 for v in verlauf if v["role"] == "user" and v.get("_sichtbar"))
                if fragen_bisher >= MAX_FRAGEN_JE_UNTERHALTUNG:
                    return jsonify({"ok": False, "msg": "Diese Unterhaltung ist voll — starte eine neue (oben „Neu“).", "zu": True}), 409
                bilder_bisher = sum(1 for v in verlauf for blk in v["content"] if isinstance(blk, dict) and blk.get("type") == "bild")
                if bilder_bisher + len(bilder) > BILD_MAX_JE_UNTERHALTUNG:
                    return jsonify({"ok": False, "msg": f"Höchstens {BILD_MAX_JE_UNTERHALTUNG} Bilder je Unterhaltung — starte eine neue."}), 409

                ctx = {"uid": uid, "menge": menge, "namen": _namen(menge), "unterhaltung_id": unterh, "vorschlaege": [], "tools": []}
                pfade, inhalt = [], []
                for roh, typ, _m in bilder:
                    pfad = f"{uid}/{unterh}/{uuid.uuid4().hex}.{typ.split('/')[1]}"
                    _bild_speichern(pfad, roh, typ)
                    with _bild_cache_lock:
                        _bild_cache[pfad] = base64.b64encode(roh).decode()
                    pfade.append(pfad)
                    inhalt.append({"type": "bild", "pfad": pfad, "typ": typ})
                inhalt.append({"type": "text", "text": _kontext_zeile(ctx) + "\n\n" + (frage or "(nur Screenshot)")})
                neu = [{"role": "user", "content": inhalt, "_text": frage, "_bilder": pfade, "_sichtbar": True}]

                system = [{"type": "text", "text": _wissen_text(), "cache_control": {"type": "ephemeral"}}]
                api = [{"role": v["role"], "content": _api_inhalt(v["content"])} for v in verlauf + neu]
                tok = {"tok_ein": 0, "tok_aus": 0, "tok_cache_lesen": 0, "tok_cache_schreiben": 0}
                antwort, stop = "", None
                for runde in range(MAX_RUNDEN):
                    r = _api_antwort(system, _mit_cache_marke(api), runde == MAX_RUNDEN - 1)
                    us = r.get("usage") or {}
                    tok["tok_ein"] += int(us.get("input_tokens") or 0)
                    tok["tok_aus"] += int(us.get("output_tokens") or 0)
                    tok["tok_cache_lesen"] += int(us.get("cache_read_input_tokens") or 0)
                    tok["tok_cache_schreiben"] += int(us.get("cache_creation_input_tokens") or 0)
                    blocks = r.get("content") or []
                    stop = r.get("stop_reason")
                    api.append({"role": "assistant", "content": blocks})
                    neu.append({"role": "assistant", "content": blocks, "_sichtbar": False})
                    if stop != "tool_use":
                        antwort = _antwort_text(blocks)
                        break
                    ergebnisse = []
                    for blk in blocks:
                        if blk.get("type") != "tool_use":
                            continue
                        erg, fehler = _werkzeug_ausfuehren(blk.get("name"), blk.get("input"), ctx)
                        ctx["tools"].append({"name": blk.get("name"), "fehler": fehler})
                        txt = json.dumps(erg, ensure_ascii=False, separators=(",", ":"))
                        ergebnisse.append({"type": "tool_result", "tool_use_id": blk.get("id"),
                                           "content": txt if len(txt) <= TOOL_ERGEBNIS_MAX else txt[:TOOL_ERGEBNIS_MAX] + "…(gekürzt)",
                                           **({"is_error": True} if fehler else {})})
                    api.append({"role": "user", "content": ergebnisse})
                    neu.append({"role": "user", "content": ergebnisse, "_sichtbar": False})
                if stop == "refusal" and not antwort:
                    antwort = "Dabei kann ich dir nicht helfen — frag dazu bitte Finn."
                if not antwort:
                    antwort = "Ich habe gerade keine Antwort gefunden — frag bitte noch einmal anders."
                # Die letzte Assistenten-Nachricht ist die sichtbare Blase (mit den Vorschlägen dieser Frage)
                for v in reversed(neu):
                    if v["role"] == "assistant":
                        v["_sichtbar"], v["_text"], v["_aktionen"] = True, antwort, ctx["vorschlaege"] or None
                        break
                for v in neu:
                    _nachricht_speichern(unterh, v["role"], v["content"], v.get("_text"), v.get("_bilder"), v.get("_aktionen"),
                                         v.get("_sichtbar", True))
                _sb("PATCH", "support_unterhaltung", {"id": f"eq.{unterh}"}, {"updated_at": datetime.now(timezone.utc).isoformat()},
                    prefer="return=minimal")
            except Exception as e:
                name = type(e).__name__
                print(f"[support] ⚠️ Chat {uid[:8]}: {name}: {_kurz(str(e), 300)}", flush=True)
                _log(uid, "fehler", unterhaltung_id=unterh or None, frage=frage, antwort=f"{name}: {_kurz(str(e), 300)}", modell=MODELL)
                msg = ("Diese Unterhaltung hat ein abgelaufenes Bild — starte eine neue." if "Bild abgelaufen" in str(e)
                       else "Der Support ist gerade überlastet — gleich noch einmal." if "RateLimit" in name or "Overloaded" in name
                       else f"Gerade keine Antwort möglich ({name}) — gleich noch einmal.")
                return jsonify({"ok": False, "msg": msg, "unterhaltung_id": unterh or None}), 502
        _log(uid, "frage", unterhaltung_id=unterh, frage=frage, antwort=antwort, modell=MODELL,
             tools=ctx["tools"] or None, bilder=", ".join(m for _r, _t, m in bilder) or None, **tok)
        return jsonify({"ok": True, "unterhaltung_id": unterh, "antwort": antwort,
                        "aktionen": [{"token": v["token"], "titel": v["titel"], "text": v["text"]} for v in ctx["vorschlaege"]],
                        "rest": max(0, limit - heute - 1)})

    @app.route("/support/aktion", methods=["POST", "OPTIONS"])
    def support_aktion():
        if request.method == "OPTIONS":
            return "", 200
        uid, menge, zugang, err = _login()
        if err:
            return err
        if not zugang[0]:
            return jsonify({"ok": False, "msg": "Der Support-Chat ist für deine ID nicht freigeschaltet."}), 403
        token = str((request.get_json(silent=True) or {}).get("token") or "")
        d, f = token_lesen(token, _secret(), time.time())
        if f:
            return jsonify({"ok": False, "msg": f}), 400
        if str(d.get("u")) != uid:
            return jsonify({"ok": False, "msg": "Dieser Vorschlag gehört zu einem anderen Login"}), 403
        # Nur einmal (S2-Hinweis 27.10.2026: vorher fail-open und nicht atomar): im Prozess atomar belegen, dazu das Protokoll (überlebt
        # einen Neustart). Protokoll nicht lesbar → nicht ausführen.
        n = str(d.get("n") or "")
        with _nonce_lock:
            jetzt = time.time()
            for k in [k for k, bis in _nonce_benutzt.items() if bis < jetzt]:
                _nonce_benutzt.pop(k, None)
            if not n or n in _nonce_benutzt:
                return jsonify({"ok": False, "msg": "Schon erledigt."}), 409
            _nonce_benutzt[n] = jetzt + AKTION_GUELTIG_S + 60
        try:
            schon = _sb("GET", "support_log", {"select": "id", "user_id": f"eq.{uid}", "art": "eq.aktion_ok",
                                               "tools": f"cs.{json.dumps({'nonce': n})}", "limit": "1"}) or []
        except Exception:
            with _nonce_lock:
                _nonce_benutzt.pop(n, None)
            return jsonify({"ok": False, "msg": "Gerade nicht prüfbar — gleich noch einmal."}), 502
        if schon:
            return jsonify({"ok": False, "msg": "Schon erledigt."}), 409
        try:
            ok, text, sid = aktion_ausfuehren(d, menge)
        except Exception as e:
            print(f"[support] ⚠️ Aktion {d.get('a')}: {type(e).__name__}: {e}", flush=True)
            ok, text, sid = False, f"Ging gerade nicht ({type(e).__name__}) — gleich noch einmal.", None
        if not ok:   # nicht ausgeführt → derselbe Knopf darf es noch einmal versuchen
            with _nonce_lock:
                _nonce_benutzt.pop(n, None)
        _log(uid, "aktion_ok" if ok else "aktion_fehler", unterhaltung_id=d.get("k") if _uuid(d.get("k")) else None,
             antwort=text, tools={"aktion": d.get("a"), "objekt": maskieren(d.get("o")), "nonce": d.get("n"), "signal_id": sid})
        # Ergebnis in den Verlauf (das Modell weiß es bei der nächsten Frage) und am Vorschlag vermerken (Anzeige beim Wieder-Öffnen)
        k = str(d.get("k") or "")
        if _uuid(k):
            try:
                _nachricht_speichern(k, "user", [{"type": "text", "text": f"[System: Nutzer hat „{d.get('a')}“ bestätigt → "
                                                                          f"{'ok' if ok else 'nicht ausgeführt'}: {text}"
                                                                          f"{' · signal_id ' + sid if sid else ''}]"}],
                                     sichtbar=False)
                if ok:
                    rows = _sb("GET", "support_nachricht", {"select": "id,aktionen", "unterhaltung_id": f"eq.{k}", "aktionen": "not.is.null",
                                                            "order": "id.desc", "limit": "10"}) or []
                    for r in rows:
                        akt = r.get("aktionen") or []
                        if any(v.get("token") == token for v in akt):
                            for v in akt:
                                if v.get("token") == token:
                                    v["erledigt"] = text
                            _sb("PATCH", "support_nachricht", {"id": f"eq.{r['id']}"}, {"aktionen": akt}, prefer="return=minimal")
                            break
            except Exception as e:
                print(f"[support] ⚠️ Aktion nicht im Verlauf: {type(e).__name__}", flush=True)
        return jsonify({"ok": ok, "msg": text, "signal_id": sid}), (200 if ok else 409)

    @app.route("/support/auftrag", methods=["GET", "OPTIONS"])
    def support_auftrag():
        if request.method == "OPTIONS":
            return "", 200
        uid, menge, _z, err = _login()
        if err:
            return err
        try:
            erg = t_auftrag_stand({"signal_id": request.args.get("id")}, {"menge": menge})
        except Exception as e:
            return jsonify({"ok": False, "msg": f"nicht lesbar ({type(e).__name__})"}), 502
        if erg.get("fehler"):
            return jsonify({"ok": False, "msg": erg["fehler"]}), 404
        return jsonify({"ok": True, **erg})
