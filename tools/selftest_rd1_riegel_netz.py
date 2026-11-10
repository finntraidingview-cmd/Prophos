#!/usr/bin/env python3
"""Selbsttest RD1 (10.11.2026, Master; Fehler-Muster FA1): Riegel-Prüfung vor dem Start (mt5-copier/panel.py richtung_frei → Railway /richtung/frei).
Nur Netzfehler (DNS „getaddrinfo failed“, Zeitlimit, Verbindung) werden bis zu 2× nach gestreuter Pause wiederholt; HTTP-Fehler, unklare Antworten und echte
Sperren bleiben wie bisher (ein sofortiger zweiter Versuch bzw. keiner). Ohne Antwort nie frei (fail-closed). Ohne Netz, urlopen nachgebaut.
Aufruf: python3 tools/selftest_rd1_riegel_netz.py"""
import io
import json
import os
import socket
import sys
import urllib.error

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "mt5-copier"))
import panel  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


PID = "11111111-2222-3333-4444-555555555555"
DNS = urllib.error.URLError(socket.gaierror(11001, "getaddrinfo failed"))


class Antwort(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def lauf(folge, **kw):
    """folge = Liste aus Ausnahmen oder dict-Antworten, je Aufruf eins. -> (Ergebnis, Aufrufe, Pausen)"""
    q, n, pausen = list(folge), [0], []

    def urlopen(req, timeout=None):
        n[0] += 1
        x = q.pop(0) if q else DNS
        if isinstance(x, BaseException):
            raise x
        return Antwort(json.dumps(x).encode("utf-8"))
    import urllib.request
    alt_u, alt_s, alt_t = urllib.request.urlopen, panel.time.sleep, panel.code_token
    urllib.request.urlopen, panel.time.sleep, panel.code_token = urlopen, (lambda s: pausen.append(s)), (lambda: "tok")
    try:
        return panel.richtung_frei(PID, "buy", **kw), n[0], pausen
    finally:
        urllib.request.urlopen, panel.time.sleep, panel.code_token = alt_u, alt_s, alt_t


print("1) Netzfehler erkennen")
NF = panel.riegel_netzfehler
check(NF(DNS) and NF(urllib.error.URLError(socket.timeout("timed out"))) and NF(socket.timeout()) and NF(ConnectionResetError())
      and NF(urllib.error.URLError(ConnectionRefusedError())), "DNS, Zeitlimit, Verbindung abgelehnt/abgebrochen = Netz")
check(not NF(urllib.error.HTTPError("u", 503, "x", {}, None)) and not NF(urllib.error.HTTPError("u", 401, "x", {}, None)) and not NF(ValueError("json")),
      "HTTP 4xx/5xx und kaputte Antwort = kein Netzfehler")

print("2) Riegel-Abfrage")
(r, n, p) = lauf([DNS, DNS, {"ok": True, "frei": True}])
check(r == (True, "", "") and n == 3 and len(p) == 2 and 1.0 <= p[0] <= 2.5 and 2.5 <= p[1] <= 5.0,
      f"DNS-Lücke zweimal, dann frei → gestartet nach 2 gestreuten Pausen ({[round(x, 2) for x in p]} s)")
(r, n, p) = lauf([DNS, DNS, DNS, {"ok": True, "frei": True}])
check(r[0] is False and r[2] == "riegel_unerreichbar" and n == 3 and len(p) == 2 and "nach 3 Versuchen mit Pause" in r[1] and "getaddrinfo" in r[1],
      "dreimal DNS → fail-closed riegel_unerreichbar, nichts gesendet, Grund nennt die Versuche")
(r, n, p) = lauf([{"ok": True, "frei": False, "grund": "läuft in Gegenrichtung"}])
check(r[0] is False and r[2] == "gegenrichtung" and n == 1 and not p, "echte Sperre: sofort gesperrt, keine Wiederholung")
(r, n, p) = lauf([{"ok": True, "frei": False, "code": "big_trade_nah", "grund": "Big Trade nah"}])
check(r[0] is False and r[2] == "big_trade_nah" and n == 1 and not p, "Big-Trade-Sperre: sofort, keine Wiederholung")
(r, n, p) = lauf([urllib.error.HTTPError("u", 503, "x", {}, None), urllib.error.HTTPError("u", 503, "x", {}, None), {"ok": True, "frei": True}])
check(r[0] is False and r[2] == "riegel_unerreichbar" and n == 2 and not p, "HTTP 503: wie bisher zwei sofortige Versuche, keine Pause, dann fail-closed")
(r, n, p) = lauf([{"ok": False, "msg": "x"}, {"ok": True, "frei": True}])
check(r == (True, "", "") and n == 2 and not p, "unklare Antwort: wie bisher ein sofortiger zweiter Versuch")
(r, n, p) = lauf([{"ok": True, "frei": True}])
check(r == (True, "", "") and n == 1 and not p, "frei beim ersten Mal: ein Aufruf, keine Pause (bitgleich)")
check(panel.richtung_frei("probe", "buy") == (True, "", ""), "ohne Plan-UUID (Probe): frei wie bisher, keine Abfrage")

print("3) Polar-Master ohne Netz-Pausen (RD1b, 10.11.2026: der Slave feuert unabhängig — der Master darf nie bis ~25 s später starten)")
(r, n, p) = lauf([DNS, DNS, {"ok": True, "frei": True}], netz_wiederholen=False)
check(r[0] is False and r[2] == "riegel_unerreichbar" and n == 2 and not p and "Versuchen mit Pause" not in r[1],
      "zweimal DNS: wie vor RD1 zwei sofortige Versuche, keine Pause, dann nicht gestartet")
(r, n, p) = lauf([DNS, {"ok": True, "frei": True}], netz_wiederholen=False)
check(r == (True, "", "") and n == 2 and not p, "DNS, dann frei: sofortiger zweiter Versuch ohne Pause")
(r, n, p) = lauf([urllib.error.HTTPError("u", 503, "x", {}, None), {"ok": False, "msg": "x"}, {"ok": True, "frei": True}], netz_wiederholen=False)
check(r[0] is False and n == 2 and not p, "HTTP/unklar: zwei sofortige Versuche wie bisher")
(r, n, p) = lauf([{"ok": True, "frei": False, "grund": "Gegenrichtung"}], netz_wiederholen=False)
check(r[0] is False and r[2] == "gegenrichtung" and n == 1 and not p, "echte Sperre: sofort")
q = open(os.path.join(os.path.dirname(HIER), "mt5-copier", "panel.py"), encoding="utf-8").read()
i = q.index('if u.path == "/api/polar-start" and str(body.get("seite") or "") == "master":')
polar = q[i:q.index("polar_panel.behandle_post(", i)]
check("richtung_frei(_pid, _ri, netz_wiederholen=False)" in polar and q.count("netz_wiederholen=False") == 1,
      "panel.py: nur polar-start (Master) ohne Netz-Pausen, alle anderen Aufrufer wie in RD1")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
