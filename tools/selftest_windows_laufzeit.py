#!/usr/bin/env python3
"""Selbsttest PU1 (05.11.2026): panel.py _windows_laufzeit_s — Überlauf nach ≈ 24,8 Tagen Betriebszeit.
GetTickCount64 lief ohne restype; ctypes nimmt dann c_int (32 Bit mit Vorzeichen) → ab 2^31 ms negative/falsche Sekunden, und _boot_terminals
hielt einen Panel-Neustart für „frisch gebootet". Der Test holt die Funktion per ast aus panel.py (ohne Panel-Start) und gibt ihr ein
gemocktes kernel32, das den Rückgabewert genau so abschneidet, wie ctypes es je nach restype täte. Aufruf: python3 tools/selftest_windows_laufzeit.py"""
import ast
import ctypes
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
FEHLER = []
TAG_MS = 86400 * 1000


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


class FakeFn:
    """Wie eine ctypes-Funktion: liefert ms, abgeschnitten nach restype (None = ctypes-Standard c_int)."""

    def __init__(self, ms):
        self.ms = ms
        self.restype = None
        self.argtypes = None

    def __call__(self):
        rt = self.restype or ctypes.c_int
        return rt(self.ms).value


class FakeK32:
    def __init__(self, ms, mit64=True):
        if mit64:
            self.GetTickCount64 = FakeFn(ms)
        self.GetTickCount = FakeFn(ms)


def lade():
    src = open(os.path.join(HIER, "..", "mt5-copier", "panel.py"), encoding="utf-8").read()
    fn = [n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "_windows_laufzeit_s"][0]
    ns = {}
    exec(compile(ast.Module([fn], []), "panel._windows_laufzeit_s", "exec"), ns)
    return ns["_windows_laufzeit_s"]


def main():
    lz = lade()
    # Gegenprobe: so lief es vorher (kein restype) — ab 24,8 Tagen falsch
    alt = FakeFn(30 * TAG_MS)
    check(alt() / 1000.0 < 0, "Gegenprobe: ohne restype wären 30 Tage negativ (der alte Fehler)")
    for tage in (1, 24, 25, 30, 49, 50, 60, 400):
        ms = tage * TAG_MS + 1234
        check(lz(FakeK32(ms)) == ms / 1000.0, f"GetTickCount64: {tage} Tage → {ms / 1000.0:.3f} s")
    k = FakeK32(30 * TAG_MS)
    lz(k)
    check(k.GetTickCount64.restype is ctypes.c_ulonglong and k.GetTickCount64.argtypes == [], "restype c_ulonglong, argtypes [] gesetzt")
    # Rückfall ohne GetTickCount64 (Windows vor Vista): c_uint32, nie negativ
    check(lz(FakeK32(30 * TAG_MS, mit64=False)) == 30 * 86400.0, "Rückfall GetTickCount (c_uint32): 30 Tage richtig (vorher negativ)")
    w = lz(FakeK32(60 * TAG_MS, mit64=False))
    check(w is not None and w >= 0 and w == ((60 * TAG_MS) % 2 ** 32) / 1000.0,
          f"Rückfall GetTickCount: 60 Tage laufen nach 49,7 Tagen über ({w:.0f} s), aber nie negativ")
    k = FakeK32(1, mit64=False)
    lz(k)
    check(k.GetTickCount.restype is ctypes.c_uint32, "Rückfall: restype c_uint32 gesetzt")

    class Kaputt:
        def __getattr__(self, n):
            raise OSError("kein kernel32")
    check(lz(Kaputt()) is None, "Fehler → None (wie bisher, _boot_terminals tut dann nichts)")
    check(lz() is None if not hasattr(ctypes, "windll") else isinstance(lz(), float), "ohne Windows → None, mit Windows → Zahl")
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
