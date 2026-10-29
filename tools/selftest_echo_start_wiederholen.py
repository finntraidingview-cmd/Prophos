#!/usr/bin/env python3
"""Selbsttest: Echo mit Hedge (route mt5, tpPreflightMt5) wiederholt master-order bei „Terminal heilt" (30.10.2026, Befund Marco e7e9782d
03:11 Dubai: 409 terminal_heilt → EIN Versuch, kein Start-Fehler, stiller Claim). Prüft die Verdrahtung in prophos.html und spielt die
Schleife mit gestellten Antworten nach (dieselbe Regel wie mt5OrderWiederholen). Aufruf: python3 tools/selftest_echo_start_wiederholen.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def wiederholen(r, seit_ms):
    """Python-Spiegel von mt5OrderWiederholen (prophos.html) — die Quelle wird unten auf genau diese Regel geprüft."""
    wartbar = bool(r and not r.get("ok") and r.get("retry_ok") is True and (r.get("grund") == "terminal_heilt"
                   or re.search(r"Verbindung|initialize|IPC|Terminal nicht", str(r.get("msg") or ""), re.I)))
    return wartbar and seit_ms <= (180000 if r.get("grund") == "terminal_heilt" else 90000)


def schleife(antworten, takt_ms=6000):
    """Spielt die for(;;)-Schleife nach: → (gesendete Aufträge, letzte Antwort)."""
    n, t, r = 0, 0, None
    for a in antworten:
        n += 1
        r = a
        if not wiederholen(r, t):
            break
        t += takt_ms
    return n, r


def main():
    html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
    f = html[html.index("function mt5OrderWiederholen("):html.index("window._mt5OrderWiederholen = ")]
    check("r.retry_ok === true" in f and "r.grund === 'terminal_heilt'" in f and "Verbindung|initialize|IPC|Terminal nicht" in f
          and "180000 : 90000" in f, "Regel im Frontend = Spiegel hier (retry_ok, terminal_heilt 180 s, sonst 90 s)")
    t = html[html.index("async function tpPreflightMt5(plan){"):html.index("async function tpPreflightMt5(plan){") + 60000]
    o = t[t.index("WIEDERHOLEN BEI „TERMINAL HEILT“") if "WIEDERHOLEN BEI „TERMINAL HEILT“" in t else t.index('WIEDERHOLEN BEI „TERMINAL HEILT"'):]
    check("for(;;){" in o and "if(!mt5OrderWiederholen(r, Date.now() - t0)) break" in o and "5000 + Math.random() * 2000" in o
          and "String(_pfPlanId) !== String(plan.id)" in o, "tpPreflightMt5: Schleife, gestreut 5–7 s, bricht ab, wenn das Popup zu ist")
    check("const vonTick = _rkTickStart.delete(String(plan.id))" in t and t.count("if(vonTick") >= 2 and "schritt: 'm5order'" in t,
          "Start zur Startzeit → Start-Fehler (sfMelden) statt stillem Claim, auch bei gestörtem Abschuss (unklar)")
    heilt = {"ok": False, "retry_ok": True, "grund": "terminal_heilt", "msg": "Terminal wird gerade geheilt"}
    ok = {"ok": True, "price": 1.0, "ticket": 7}
    n, r = schleife([heilt, heilt, heilt, ok, ok])
    check(n == 4 and r is ok, f"terminal_heilt → Wiederholung → Order genau einmal platziert ({n} Aufträge, der letzte ok, danach keiner)")
    n, r = schleife([heilt] * 40)
    check(n == 32 and not r.get("ok"), f"terminal_heilt bleibt → nach 180 s Schluss ({n} Versuche), dann Start-Fehler")
    unklar = {"ok": False, "retry_ok": False, "msg": "Zeitlimit"}
    check(schleife([unklar, ok])[0] == 1, "unklar (retry_ok false) → nie wiederholt (keine Doppel-Order)")
    abgelehnt = {"ok": False, "retry_ok": True, "msg": "Markt geschlossen (10018)"}
    check(schleife([abgelehnt, ok])[0] == 1, "abgelehnt mit retry_ok, aber kein Terminal-Grund → nicht wiederholt (Start-Fehler)")
    verb = {"ok": False, "retry_ok": True, "msg": "IPC-Verbindung zum Terminal fehlt"}
    check(schleife([verb, verb, ok])[0] == 3 and schleife([verb] * 40)[0] == 17, "Verbindungsfehler → wiederholt, Deckel 90 s")
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
