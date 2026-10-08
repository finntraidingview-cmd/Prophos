#!/usr/bin/env python3
"""Selbsttest: Anlaufsperre der schreibenden Auto-Planer-Takte (app.py AP_ANLAUF_S / ap_anlauf_rest / ap_loop, 08.10.2026, Slave 1:
beim Railway-Rollout liefen zwei Container 05:12:22/05:12:23 je einen Bot-Lauf). Rein rechnend + Aufbau von ap_loop geprüft.
Aufruf: python3 tools/selftest_anlaufsperre.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def main():
    src = open(APP, encoding="utf-8").read()
    ns = {}
    exec(re.search(r"^AP_ANLAUF_S = .*$", src, re.M).group(0), ns)
    i = src.index("\ndef ap_anlauf_rest(") + 1
    exec(src[i:src.find("\n\n\n", i)], ns)
    R, S = ns["ap_anlauf_rest"], ns["AP_ANLAUF_S"]
    f = []

    def check(ok, name):
        f.append(0 if ok else 1)
        print(("OK  " if ok else "FEHL") + " " + name)

    check(20 <= S <= 120, f"Sperre 20–120 s (überholter Container im Beleg nach < 10 s weg, Pushes im Minutentakt) ({S})")
    check(R(1000, 1000) == S and R(1000, 1004) == S - 4, "direkt nach dem Start: volle Sperre (Bot lief im Beleg nach 4 s)")
    check(R(1000, 1000 + S) == 0 and R(1000, 1000 + S + 30) == 0, "nach Ablauf: frei, nie negativ")
    check(R(1000, 1000, sperre=10) == 10, "Sperre einstellbar")

    # Aufbau: in ap_loop kommt das Warten VOR der Schleife, alle schreibenden Takte erst danach
    a = src.index("\ndef ap_loop(")
    b = src.find("\n\n\n", a)
    loop = src[a:b]
    warte, schleife = loop.find("_schleife_schlafen(rest)"), loop.find("while True:")
    check(0 < warte < schleife, "ap_loop: Anlaufsperre vor der Takt-Schleife")
    takte = ("ap_nacht_tick(", "ap_nachplan_tick(", "_ap_kette_takt(", "_ap_bot_tick(")
    pos = {t: loop.find(t) for t in takte}
    check(all(p > schleife for p in pos.values()), f"Nachtlauf, Nachplanen, Kette, Bot erst in der Schleife ({pos})")
    zw = [m.start() for m in re.finditer(r"zw_tick\(", loop)]
    check(len(zw) == 2 and zw[0] < warte and zw[1] > schleife, f"Ziel-Wache auch in der Sperre (vor dem Warten) und in der Schleife ({zw})")
    # außerhalb von ap_loop ruft kein Hintergrund-Takt die schreibenden Takte (nur die Hand-Route ausgleichen)
    rest_src = src[:a] + src[b:]
    for t in ("ap_nacht_tick(", "ap_nachplan_tick(", "_ap_kette_takt(", "_ap_bot_tick(", "zw_tick("):
        n = len([m for m in re.finditer(re.escape(t), rest_src) if not rest_src[max(0, m.start() - 4):m.start()].endswith("def ")])
        check(n == 0, f"{t[:-1]} wird außerhalb von ap_loop nicht aufgerufen ({n})")
    print(f"{len(f) - sum(f)}/{len(f)} ok")
    sys.exit(1 if sum(f) else 0)


if __name__ == "__main__":
    main()
