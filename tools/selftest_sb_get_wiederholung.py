#!/usr/bin/env python3
"""Selbsttest Supabase-Pool + GET-Wiederholer + letzter guter Stand (app.py, 09.10.2026) — ohne Netz.

Aufruf:  python3 tools/selftest_sb_get_wiederholung.py
Anlass: Befund Prüfer T3 09.10.2026 — drei Netz-Aussetzer im Railway-Container (6–13 s ohne ausgehenden Verkehr) → 502 auf
/admin/live-trades und /admin/handarbeit. Lädt _sb_anfrage samt Bremse per Quelltext (app.py zieht beim Import Flask und startet
Threads) mit einer GESTELLTEN Session und prüft: GET genau EIN zweiter Versuch nach Timeout/Verbindungsfehler, POST/PATCH/DELETE/RPC
nie; 5xx-Antworten werden nicht wiederholt; offene Sicherung → kein zweiter Versuch; Aufbau-Zeitlimit 3 s, Lesen wie übergeben;
die echte Session hat Pool 20, keine urllib3-Wiederholung, keine Cookies; letzter guter Stand nur bei DB-Fehler und nur 30 min."""
import os
import sys
import threading
import time
import types
from datetime import datetime, timezone

import requests as echtes_requests

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
SRC = open(APP, encoding="utf-8").read()


def block(name):
    i = SRC.index(f"def {name}(")
    return SRC[i:SRC.find("\n\n\n", i)]


def zuweisung(name):
    i = SRC.index(f"\n{name} = ") + 1
    return SRC[i:SRC.index("\n", i)]


class Antwort:
    def __init__(self, status):
        self.status_code = status


class Session:
    """Gestellte Session: Drehbuch je Aufruf (Ausnahme-Klasse oder Status), merkt Methode + timeout."""
    def __init__(self):
        self.drehbuch, self.aufrufe = [], []

    def request(self, methode, url, timeout=None, **kw):
        self.aufrufe.append((methode, timeout))
        x = self.drehbuch.pop(0) if self.drehbuch else 200
        if isinstance(x, type) and issubclass(x, Exception):
            raise x("gestellt")
        return Antwort(x)

    def get(self, url, **kw):
        return Antwort(200)


def lade(sess):
    i = SRC.index("class SupabaseGesperrt(")
    klasse = SRC[i:SRC.find("\n\n\n", i)]
    ns = {"requests": echtes_requests, "threading": threading, "time": time, "SUPABASE_URL": "https://beispiel.invalid",
          "SUPABASE_SERVICE_KEY": "x", "_sb_headers": lambda prefer=None: {}, "_SB_SESSION": sess,
          "datetime": datetime, "timezone": timezone, "logging": __import__("logging")}
    code = "\n".join([zuweisung(n) for n in ("SB_BREMSE_N", "SB_BREMSE_STUFEN", "SB_BREMSE_HALB_S", "SB_TIMEOUT", "SB_PROBE_TIMEOUT",
                                              "SB_CONNECT_S", "SB_GET_PAUSE_S", "SB_POOL_N", "STAND_ALT_MAX_S", "STAND_ALT_MAX_N")]
                     + [klasse] + [block(n) for n in ("sb_session_neu", "sb_timeout", "sb_wiederholbar", "sb_bremse_neu",
                                                       "sb_bremse_vorher", "sb_bremse_nach")]
                     + ['_SB_BREMSE = {"rest": sb_bremse_neu(), "auth": sb_bremse_neu()}', "_SB_BREMSE_LOCK = threading.Lock()",
                        '_SB_GEHEILT_AT = {"rest": 0.0, "auth": 0.0}', "_STAND_ALT = {}", "_STAND_ALT_LOCK = threading.Lock()"]
                     + [block(n) for n in ("_sb_bremse_melden", "sb_bremse_rest_s", "_sb_probe", "_sb_anfrage",
                                           "stand_alt_merken", "stand_alt_holen")])
    exec(code, ns)
    ns["SB_GET_PAUSE_S"] = 0.0
    return ns


def main():
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    ex = echtes_requests.exceptions
    sess = Session()
    a = lade(sess)
    A = a["_sb_anfrage"]

    def lauf(methode, drehbuch, **kw):
        sess.drehbuch, sess.aufrufe = list(drehbuch), []
        a["_SB_BREMSE"]["rest"] = a["sb_bremse_neu"]()
        try:
            return A(methode, "https://beispiel.invalid/rest/v1/x", **kw), None
        except Exception as e:
            return None, e

    # 1) GET: genau ein zweiter Versuch
    for fehler in (ex.ReadTimeout, ex.ConnectTimeout, ex.ConnectionError):
        r, e = lauf("GET", [fehler, 200])
        check(r is not None and r.status_code == 200 and len(sess.aufrufe) == 2 and a["_SB_BREMSE"]["rest"]["folge"] == 0,
              f"GET {fehler.__name__} → zweiter Versuch gelingt, Bremse zählt keinen Fehler")
    r, e = lauf("GET", [ex.ReadTimeout, ex.ReadTimeout, 200])
    check(isinstance(e, ex.ReadTimeout) and getattr(e, "sb_netz", False) and len(sess.aufrufe) == 2
          and a["_SB_BREMSE"]["rest"]["folge"] == 1, "GET zweimal Timeout → Fehler mit sb_netz, genau 2 Aufrufe, Bremse +1")
    r, e = lauf("get", [ex.ReadTimeout, 200])
    check(r is not None and len(sess.aufrufe) == 2, "Methode klein geschrieben zählt auch als GET")
    r, e = lauf("GET", [503, 200])
    check(r is not None and r.status_code == 503 and len(sess.aufrufe) == 1, "GET 503 (Antwort, keine Ausnahme) → kein zweiter Versuch")
    r, e = lauf("GET", [ex.HTTPError, 200])
    check(e is not None and len(sess.aufrufe) == 1, "GET andere RequestException (HTTPError) → kein zweiter Versuch")

    # 2) Schreibungen und RPC nie
    for m in ("POST", "PATCH", "DELETE", "PUT"):
        for fehler in (ex.ReadTimeout, ex.ConnectTimeout, ex.ConnectionError):
            r, e = lauf(m, [fehler, 200])
            check(isinstance(e, fehler) and len(sess.aufrufe) == 1, f"{m} {fehler.__name__} → NIE wiederholt (1 Aufruf)")
    sess.drehbuch, sess.aufrufe = [ex.ReadTimeout, 200], []
    a["_SB_BREMSE"]["rest"] = a["sb_bremse_neu"]()
    try:
        A("POST", "https://beispiel.invalid/rest/v1/rpc/mt5_baseline_patch", json={}, timeout=(5, 15))
        e = None
    except Exception as x:
        e = x
    check(isinstance(e, ex.ReadTimeout) and len(sess.aufrufe) == 1, "RPC (POST /rpc/…) → nie wiederholt")
    r, e = lauf("POST", [ex.ReadTimeout, 200], kritisch=True)
    check(e is not None and len(sess.aufrufe) == 1, "kritischer POST → auch nicht wiederholt")

    # 3) Sicherung inzwischen offen → kein zweiter Versuch
    sess.drehbuch, sess.aufrufe = [ex.ReadTimeout, 200], []
    a["_SB_BREMSE"]["rest"] = a["sb_bremse_neu"]()
    alt_rest = a["sb_bremse_rest_s"]
    a["sb_bremse_rest_s"] = lambda dienst="rest": 30.0
    try:
        A("GET", "https://beispiel.invalid/rest/v1/x")
        e = None
    except Exception as x:
        e = x
    a["sb_bremse_rest_s"] = alt_rest
    check(isinstance(e, ex.ReadTimeout) and len(sess.aufrufe) == 1, "Sicherung offen → GET ohne zweiten Versuch")

    # 4) Zeitlimits: Aufbau 3 s, Lesen wie übergeben
    T = a["sb_timeout"]
    check(T(None) == (3.0, 12) and T(12) == (3.0, 12) and T((5, 15)) == (3.0, 15) and T((2, 8)) == (2.0, 8),
          "Zeitlimit: Standard (3, 12), Zahl → (3, Zahl), (5, 15) → (3, 15), kürzerer Aufbau bleibt")
    lauf("GET", [200], timeout=(5, 15))
    check(sess.aufrufe and sess.aufrufe[0][1] == (3.0, 15), "_sb_anfrage reicht (3, 15) an die Session weiter")

    # 5) echte Session: Pool, keine urllib3-Wiederholung, keine Cookies
    s = a["sb_session_neu"]()
    ad = s.get_adapter("https://beispiel.invalid/")
    check(ad._pool_maxsize == 20 and ad.max_retries.total == 0, "Session: Pool 20, urllib3 max_retries 0")
    check(s.cookies._policy.allowed_domains() == () and not s.cookies._policy.set_ok_domain(types.SimpleNamespace(domain="beispiel.invalid"), None), "Session: Cookies werden abgelehnt (kein geteilter Zustand über die Threads)")

    # 6) letzter guter Stand
    M, H = a["stand_alt_merken"], a["stand_alt_holen"]
    netz = ex.ReadTimeout("x")
    netz.sb_netz = True
    M(("live-trades", "u1", ()), {"jetzt": "j", "trades": [1]}, jetzt=1000.0)
    alt = H(("live-trades", "u1", ()), netz, jetzt=1060.0)
    check(alt and alt["stand_alt"] is True and alt["trades"] == [1] and alt["stand_at"].startswith("1970-01-01T00:16:40"),
          "DB-Fehler → gemerkter Stand mit stand_alt + stand_at (ISO)")
    check(H(("live-trades", "u1", ()), ValueError("code"), jetzt=1060.0) is None, "Code-Fehler (ohne sb_netz) → kein alter Stand")
    check(H(("live-trades", "u2", ()), netz, jetzt=1060.0) is None, "anderer Schlüssel (Login/Parameter) → kein fremder Stand")
    check(H(("live-trades", "u1", ()), netz, jetzt=1000.0 + 30 * 60 + 1) is None, "älter als 30 min → None (wieder 502)")
    gs = a["SupabaseGesperrt"](10)
    check(H(("live-trades", "u1", ()), gs, jetzt=1060.0) is not None, "offene Sicherung (SupabaseGesperrt) → alter Stand")
    check("stand_alt" not in a["_STAND_ALT"][("live-trades", "u1", ())][1], "gemerkte Antwort bleibt unverändert (Kopie)")
    for k in range(a["STAND_ALT_MAX_N"] + 5):
        M(("x", k), {}, jetzt=2000.0 + k)
    check(len(a["_STAND_ALT"]) == a["STAND_ALT_MAX_N"] and ("x", 0) not in a["_STAND_ALT"], "höchstens STAND_ALT_MAX_N Einträge, älteste fliegen")

    # 7) Quelltext: kein Supabase-Aufruf mehr am Pool vorbei
    roh = [z for z in SRC.splitlines() if "SUPABASE_URL}" in z and "requests." in z]
    check(not roh, f"kein requests.get/post direkt gegen SUPABASE_URL ({len(roh)} gefunden)")

    print("\nALLES OK" if ok else "\nFEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
