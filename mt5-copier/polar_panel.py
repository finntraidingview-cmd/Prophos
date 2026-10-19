"""POLAR — Panel-Teil (13.10.2026, Finn). EIGENES MODUL, bewusst: panel.py bekommt nur Haken (Routen-Weiterleitung, Riegel,
Datei-Verteilung); Start, Zustand und Sperre stehen hier. Der alte Puls (order_bot.py) bleibt unverändert.

  POST /api/polar-start   {seite: master|slave, lauf_id, plan_id, …Auftrag}  → startet polar_bot.py als LANGLEBIGEN Prozess (Popen)
  GET  /api/polar-stand   [?lauf_id=]                                        → Zustand (stand_<seite>.json des Laufs, Prozess lebt?)
  POST /api/polar-abbruch {lauf_id}                                          → abbruch.json (wirkt nur VOR der Feuerzeit)

PRIORITÄT 1 (Finn: „wenn Polar läuft, darf kein anderer Puls-Bot oder irgendwas diesen PC bedienen — beide PCs nicht anfassen"):
solange polar_aktiv.json auf einen lebenden Prozess zeigt, antwortet das Panel auf JEDE andere POST-Route mit 409 polar_aktiv
(seit 20.10.2026 alle Wege außer FREI_PFADE, vorher nur die Maus-Wege; Code vorher puls_beschaeftigt), und der Selbst-Neustart des Panels
wird vertagt. Der Tab fragt denselben Zustand über GET /api/polar-stand (polarLaeuft() in prophos.html)."""
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
POLAR_ORDNER = os.path.join(HERE, "polar")
FLAG = os.path.join(HERE, "polar_aktiv.json")
BOT = os.path.join(HERE, "polar_bot.py")
PROZESSE = {}            # lauf_id → Popen (nur die von DIESEM Panel-Prozess gestarteten)
_LOCK = threading.Lock()
# Alles, was Maus/Tastatur/Fenster anfasst — während Polar läuft gesperrt (Liste aus den panel.py-Routen, 13.10.2026)
PULS_PFADE = ("/api/tv-konto", "/api/tsx-konto", "/api/tsx-lesen", "/api/tsx-inventar", "/api/tv-lesen", "/api/tv-close", "/api/tv-order",
              "/api/master-order", "/api/master-close", "/api/mouse-test", "/api/tv-fokus", "/api/tv-start", "/api/hedge-solo",
              "/api/start-terminal", "/api/start-hedge-terminal", "/api/close-idle-terminals", "/api/provision", "/api/mt5-update-einrichten")


def _lesen(pfad, default=None):
    try:
        with open(pfad, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _schreiben(pfad, daten):
    try:
        tmp = pfad + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(daten, f, ensure_ascii=False, default=str)
        os.replace(tmp, pfad)
    except OSError:
        pass


def _prozess_lebt(pid):
    if not pid:
        return False
    for p in list(PROZESSE.values()):
        if p.pid == pid:
            return p.poll() is None
    # nicht von diesem Panel gestartet (Panel-Neustart dazwischen): Windows über tasklist, sonst os.kill(0)
    try:
        if os.name == "nt":
            out = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/NH"], capture_output=True, text=True, timeout=5).stdout
            return str(int(pid)) in out
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def aktiv():
    """Läuft auf diesem PC ein Polar-Prozess? (Flag + lebender Prozess; eine Leiche räumt sich selbst weg)"""
    f = _lesen(FLAG)
    if not isinstance(f, dict):
        return False
    if _prozess_lebt(f.get("pid")):
        return True
    try:
        os.remove(FLAG)
    except OSError:
        pass
    return False


# POLAR-VORRANG (20.10.2026, Finn: „Polar bekommt höhere Priorität als Orbit. Wenn Polar läuft, darf gar kein einziger Trade mehr
# gestartet werden … keine einzige Order platziert, keine Balance gelesen, der Puls-Knopf darf nichts machen. Der Reader redet weiter.")
# Vorher sperrte der Riegel nur die 18 Maus-Wege oben; /api/plan, plan-delete, set-hedge (Echo-Hedge-Maschine) und jede künftige Route
# gingen durch. Jetzt gilt: läuft Polar, bekommt JEDE POST-Route 409 — außer den Polar-Routen selbst, dem Klick-Melder des Puls und den
# reinen Kennungs-Wegen. GET-Wege (/api/instances, /api/polar-stand) bleiben offen, der Tab muss den Zustand sehen. Der Reader
# (Tampermonkey, Port 8790) läuft nicht über dieses Panel und wird nie angefasst. Antwort-Code polar_aktiv (nicht mehr puls_beschaeftigt):
# der Tab weiß damit, dass Warten nichts bringt, und nennt den Lauf.
FREI_PFADE = ("/api/polar-start", "/api/polar-abbruch", "/api/polar-stand", "/api/puls-klick", "/api/code-token", "/api/pc-id")


def gesperrt(pfad):
    """Riegel für panel.py do_POST: True = diesen Weg jetzt mit 409 ablehnen (alles außer FREI_PFADE, solange Polar läuft)."""
    return pfad not in FREI_PFADE and aktiv()


def sperre_antwort(pfad):
    """-> (409, dict) | None. Nennt lauf_id + Seite, damit Tab und Mensch sehen, WELCHER Polar-Lauf den PC hält."""
    if not gesperrt(pfad):
        return None
    f = _lesen(FLAG) or {}
    lid = str(f.get("lauf_id") or "")
    return 409, {"ok": False, "retry_ok": True, "gesendet": False, "code": "polar_aktiv", "lauf_id": lid or None,
                 "seite": f.get("seite"), "plan_id": f.get("plan_id"), "pfad": pfad,
                 "msg": f"Polar läuft auf diesem PC (Lauf {lid[:8] or '?'}, {f.get('seite') or '?'}) — kein anderer Weg, bis der Polar-Trade zu ist."}


def stand(lauf_id=None):
    f = _lesen(FLAG) or {}
    lid = lauf_id or f.get("lauf_id")
    out = {"ok": True, "aktiv": aktiv(), "flag": f, "lauf_id": lid, "stand": None}
    if lid:
        ordner = os.path.join(POLAR_ORDNER, str(lid))
        for seite in ("master", "slave"):
            s = _lesen(os.path.join(ordner, f"stand_{seite}.json"))
            if s:
                out["stand"] = s
    return out


def start(body, beschaeftigt=False):
    """polar_bot.py <seite> <json> als Popen starten. -> (http, dict). Nie zwei Polar-Prozesse, nie neben einem laufenden Puls-Weg."""
    seite = str(body.get("seite") or "")
    lid = str(body.get("lauf_id") or "").strip()
    if seite not in ("master", "slave") or not lid:
        return 400, {"ok": False, "msg": "seite (master|slave) und lauf_id fehlen"}
    if not os.path.exists(BOT):
        return 503, {"ok": False, "retry_ok": True, "code": "polar_bot_fehlt",
                     "msg": "polar_bot.py liegt noch nicht auf diesem PC — das Panel holt ihn beim nächsten Takt."}
    with _LOCK:
        if aktiv():
            f = _lesen(FLAG) or {}
            if f.get("lauf_id") == lid:
                return 200, {"ok": True, "schon": True, "pid": f.get("pid"), "lauf_id": lid}
            return 409, {"ok": False, "retry_ok": True, "code": "puls_beschaeftigt",
                         "msg": f"Polar läuft schon auf diesem PC (Lauf {str(f.get('lauf_id'))[:8]})"}
        if beschaeftigt:
            return 409, {"ok": False, "retry_ok": True, "code": "puls_beschaeftigt",
                         "msg": "Ein anderer Puls-Lauf hält gerade die Maus — Polar startet, sobald er fertig ist."}
        ordner = os.path.join(POLAR_ORDNER, lid)
        os.makedirs(ordner, exist_ok=True)
        try:
            os.remove(os.path.join(ordner, "abbruch.json"))
        except OSError:
            pass
        cmd = {k: v for k, v in body.items() if k != "seite"}
        log = open(os.path.join(ordner, f"{seite}_prozess.log"), "ab")
        try:
            p = subprocess.Popen([sys.executable, BOT, seite, json.dumps(cmd, ensure_ascii=False)],
                                 stdout=log, stderr=subprocess.STDOUT, cwd=HERE)
        except Exception as e:
            log.close()
            return 500, {"ok": False, "retry_ok": True, "msg": f"Polar-Prozess nicht gestartet: {type(e).__name__}: {e}"}
        PROZESSE[lid] = p
        _schreiben(FLAG, {"lauf_id": lid, "seite": seite, "pid": p.pid, "at": time.time(), "plan_id": body.get("plan_id")})

    def _aufraeumen():
        p.wait()
        log.close()
        with _LOCK:
            f = _lesen(FLAG) or {}
            if f.get("pid") == p.pid:
                try:
                    os.remove(FLAG)
                except OSError:
                    pass
            PROZESSE.pop(lid, None)
        print(f"[polar] Prozess {seite} Lauf {lid[:8]} beendet (Exit {p.returncode})", flush=True)
    threading.Thread(target=_aufraeumen, daemon=True).start()
    print(f"[polar] ▶ {seite} Lauf {lid[:8]} gestartet (PID {p.pid})", flush=True)
    return 200, {"ok": True, "pid": p.pid, "lauf_id": lid, "seite": seite}


def abbruch(body):
    lid = str(body.get("lauf_id") or "").strip()
    if not lid:
        return 400, {"ok": False, "msg": "lauf_id fehlt"}
    ordner = os.path.join(POLAR_ORDNER, lid)
    os.makedirs(ordner, exist_ok=True)
    _schreiben(os.path.join(ordner, "abbruch.json"), {"at": time.time(), "grund": body.get("grund") or "panel"})
    return 200, {"ok": True, "msg": "Abbruch hinterlegt — wirkt nur, solange die Feuerzeit noch nicht gelesen ist"}


def behandle_post(pfad, body, beschaeftigt=False):
    """-> (http, dict) | None (nicht meine Route)"""
    if pfad == "/api/polar-start":
        return start(body, beschaeftigt)
    if pfad == "/api/polar-abbruch":
        return abbruch(body)
    return None


def behandle_get(pfad, query):
    if pfad == "/api/polar-stand":
        return 200, stand((query.get("lauf_id") or [""])[0] or None)
    return None


def ensure_source(repo_datei, sha=None):
    """polar_bot.py + polar_panel.py aus demselben Repo-Stand holen wie order_bot.py (nur ersetzen, wenn der Inhalt übersetzt).
    polar_panel.py wirkt erst nach dem nächsten Panel-Neustart (Modul ist geladen) — polar_bot.py sofort (eigener Prozess)."""
    for name in ("polar_bot.py", "polar_panel.py"):
        dst = os.path.join(HERE, name)
        try:
            data = repo_datei(f"mt5-copier/{name}", sha)
            if not data or len(data) < 500:
                continue
            compile(data, name, "exec")
            old = b""
            if os.path.exists(dst):
                with open(dst, "rb") as f:
                    old = f.read()
            if data != old:
                tmp = dst + ".tmp"
                with open(tmp, "wb") as f:
                    f.write(data)
                os.replace(tmp, dst)
                print(f"[polar] {name} aktualisiert ({len(data)} Bytes, Stand {(sha or 'main')[:7]})", flush=True)
        except Exception as e:
            print(f"[polar] {name} nicht geholt ({type(e).__name__})", flush=True)
