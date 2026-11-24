#!/usr/bin/env python3
"""Selbsttest PE1 (24.11.2026, Simon pc-pmqd8g Plan db8ebbf1): letzter Blick vor dem Sell (_echo_scharf_abwarten mit max_s 0.0) las
status_<cfg>.json genau einmal — ersetzt der Copier die Datei gleichzeitig per os.replace, wirft Windows PermissionError → Fehlstart.
Kein MT5, keine Order. Prüft: (1) _json_lesen_geduldig liest nach PermissionError/halber Datei erneut (höchstens ECHO_STATUS_LESEN_VERSUCHE,
~1 s), fehlende Datei sofort; (2) _echo_scharf_abwarten mit max_s 0.0 wird scharf, wenn die erste Lesung an PermissionError scheitert und die
zweite klappt; (3) bleibt die Datei gesperrt, ehrlich „Status-Datei nicht lesbar (PermissionError)“ wie bisher."""
import builtins
import io
import json
import os
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


echt_open = builtins.open
alt_warte = ob._warte
ob._warte = lambda *a, **k: None
try:
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "status_x.json")   # wie _echo_scharf_abwarten: config_x.json → status_x.json
        with echt_open(p, "w", encoding="utf-8") as f:
            json.dump({"ok": 1}, f)
        n = {"k": 0}

        def offen(gesperrt_n):
            def o(pfad, *a, **k):
                if str(pfad) == p:
                    n["k"] += 1
                    if n["k"] <= gesperrt_n:
                        raise PermissionError(13, "Der Prozess kann nicht auf die Datei zugreifen")
                return echt_open(pfad, *a, **k)
            return o
        # (1)
        builtins.open = offen(2)
        try:
            dd, e = ob._json_lesen_geduldig(p)
        finally:
            builtins.open = echt_open
        check(dd == {"ok": 1} and e is None and n["k"] == 3, f"2× PermissionError, 3. Lesung klappt ({n['k']} Lesungen)")
        n["k"] = 0
        builtins.open = offen(99)
        try:
            dd, e = ob._json_lesen_geduldig(p)
        finally:
            builtins.open = echt_open
        check(dd is None and isinstance(e, PermissionError) and n["k"] == ob.ECHO_STATUS_LESEN_VERSUCHE,
              f"dauerhaft gesperrt → nach {ob.ECHO_STATUS_LESEN_VERSUCHE} Lesungen PermissionError zurück")
        dd, e = ob._json_lesen_geduldig(os.path.join(d, "fehlt.json"))
        check(dd is None and isinstance(e, FileNotFoundError), "fehlende Datei → sofort zurück, kein Warten")
        halb = os.path.join(d, "halb.json")
        with echt_open(halb, "w", encoding="utf-8") as f:
            f.write('{"ok": ')
        dd, e = ob._json_lesen_geduldig(halb)
        check(dd is None and isinstance(e, ValueError), "halb geschriebene Datei → nachgelesen, am Ende ValueError")
        check(ob.ECHO_STATUS_LESEN_VERSUCHE * 0.4 <= 2.0, "Nachlesen höchstens ~1–2 s")

        # (2) + (3) _echo_scharf_abwarten mit max_s 0.0
        cfg = os.path.join(d, "config_x.json")
        alt_u = ob.echo_scharf_urteil
        ob.echo_scharf_urteil = lambda st, plans, datei, jetzt, immer_scharf=False: ("scharf", "") if st == {"ok": 1} else ("warten", "x")
        try:
            n["k"] = 0
            builtins.open = offen(1)
            try:
                tr = []
                ok, grund = ob._echo_scharf_abwarten(cfg, 0.0, tr)
            finally:
                builtins.open = echt_open
            check(ok is True and any("Copier scharf" in z for z in tr), f"max_s 0.0: erste Lesung PermissionError, zweite scharf → weiter ({grund!r})")
            n["k"] = 0
            builtins.open = offen(99)
            try:
                ok, grund = ob._echo_scharf_abwarten(cfg, 0.0, [])
            finally:
                builtins.open = echt_open
            check(ok is False and grund == "Status-Datei nicht lesbar (PermissionError)", f"dauerhaft gesperrt → wie bisher ehrlich ({grund!r})")
        finally:
            ob.echo_scharf_urteil = alt_u
finally:
    ob._warte = alt_warte
    builtins.open = echt_open

print()
print("ALLES OK" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
