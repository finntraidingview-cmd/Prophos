#!/usr/bin/env python3
"""Selbsttest Close durchdrücken im Copier (Finn 02.11.2026: „Eine Close-Order darf nicht abgelehnt werden … jede Millisekunde neu“; Simon pc-pmqd8g Plan 88b28130).
Rechnet solo_close_durchdruecken aus mt5-copier/copier.py mit einer Spiel-Uhr, ohne MetaTrader.

Aufruf:  python3 tools/selftest_solo_close_durchdruecken.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(os.path.dirname(HIER), "mt5-copier", "copier.py"), encoding="utf-8").read()
fehler = []


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        fehler.append(text)


ns = {}
for name in ("SOLO_CLOSE_DRUECKEN_S", "SOLO_CLOSE_TAKT_S", "SOLO_CLOSE_DEVIATION", "SOLO_CLOSE_ENDGUELTIG"):
    exec(re.search(r"^" + name + r"\s*=.*$", src, re.M).group(0), ns)
exec(re.search(r"^def solo_close_durchdruecken\(.*?(?=^\S)", src, re.S | re.M).group(0), ns)
D = ns["solo_close_durchdruecken"]


def lauf(ergebnisse, retcodes):
    uhr = {"t": 0.0}
    def versuch(i):
        uhr["t"] += 0.02                                # order_send dauert 20 ms
        return ergebnisse(i)
    def fehler_():
        return retcodes(len(log)), "x"
    log = []
    def schlafe(s):
        log.append(s); uhr["t"] += s
    r, v = D(versuch, fehler_, lambda: uhr["t"], schlafe)
    return r, v, uhr["t"]


r, v, t = lauf(lambda i: "deal" if i == 2 else None, lambda n: 10004)
check(r == "deal" and len(v) == 2 and t < 0.3, f"Requote zweimal, dritter Versuch zu: nach {t * 1000:.0f} ms, Versuche {[x['retcode'] for x in v]}")
r, v, t = lauf(lambda i: None, lambda n: 10027)
check(r is None and len(v) == 1, "Algo-Handel aus (10027): endgültig, sofort Fehler an den Tab")
r, v, t = lauf(lambda i: None, lambda n: None)
check(r is None and 4.9 <= t <= 5.3 and len(v) >= 40, f"order_send None dauerhaft: {len(v)} Versuche in {t:.2f} s, dann Fehler")
r, v, t = lauf(lambda i: "zu" if i == 3 else None, lambda n: 10021)
check(r == "zu" and len(v) == 3, "Position zwischendurch zu (Level/Hand): schon zu, keine weiteren Versuche")
check(ns["SOLO_CLOSE_TAKT_S"] == 0.1 and ns["SOLO_CLOSE_DEVIATION"] >= 100, "Takt 100 ms, große deviation")
check('"type_filling": fillings[i % len(fillings)]' in src and "tick = mt5.symbol_info_tick(sym)                  # frischer Tick je Versuch" in src
      and '"retry_ok": letzt.get("retcode") not in SOLO_CLOSE_ENDGUELTIG' in src and "m.letzter_retcode = int(r.retcode)" in src,
      "solo_close: frischer Tick und wechselnde Filling-Modi je Versuch, retry_ok nur bei nicht endgültigem Fehler")

print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
