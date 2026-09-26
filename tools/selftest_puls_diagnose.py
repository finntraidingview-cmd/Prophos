#!/usr/bin/env python3
"""Selbsttest Puls-Diagnose (app.py, PULS-DIAGNOSE, 26.09.2026, B6 Fenster-Treue) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_puls_diagnose.py
Prueft puls_diagnose_saeubern (nur bekannte Felder, kurze Texte, Groessendeckel) und das pc_id-Muster der Route."""
import json
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "json": json}
    i = src.index("def puls_diagnose_saeubern(")
    exec("\n".join([re.search(r"^PC_ID_MUSTER = .*$", src, re.M).group(0), re.search(r"^PULS_DIAGNOSE_MAX = .*$", src, re.M).group(0),
                    src[i:src.find("\n\n\n", i)]]), ns)
    return ns


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    m, s = a["PC_ID_MUSTER"], a["puls_diagnose_saeubern"]
    check(m.fullmatch("pc-usq1i6") and not m.fullmatch("pc-USQ") and not m.fullmatch("pc-a/../x") and not m.fullmatch(""),
          "pc_id-Muster: pc-usq1i6 ja, Grossbuchstaben/Pfade/leer nein")
    d = s({"modus": "tvorder", "code": "gemerkt", "eigen": "Default", "tabu": ["Profile 1"], "boese": "x" * 9999,
           "gemerkt": {"hwnd": 123, "pid": 456, "profil": "Default", "titel": "T" * 200, "at": "2026-09-26 23:00:00", "x": 1},
           "profile": [{"dir": "Default", "name": "Moritz", "extra": 1}],
           "fenster": [{"titel": "MNQ1! Nicht benannt", "profil": "Profile 1", "exe": "chrome.exe", "grund": "Reader-/Fremdprofil Terminal 1"}]})
    check(d and "boese" not in d and d["gemerkt"]["hwnd"] == 123 and "x" not in d["gemerkt"] and len(d["gemerkt"]["titel"]) == 60
          and d["profile"] == [{"dir": "Default", "name": "Moritz"}] and d["fenster"][0]["grund"].startswith("Reader"),
          "Diagnose: unbekannte Felder raus, Texte gekuerzt, gemerktes Fenster + Ausschlussgrund bleiben")
    check(s(None) is None and s("x") is None and s({"gemerkt": {"hwnd": "1; drop"}})["gemerkt"]["hwnd"] is None,
          "Diagnose: Unsinn abgewiesen, hwnd nur als Zahl")
    gross = s({"profile": [{"dir": "d" * 90, "name": "n" * 90}] * 50, "fenster": [{"titel": "t" * 90, "grund": "g" * 90}] * 50})
    check(gross is not None and len(gross["profile"]) == 12 and len(gross["fenster"]) == 12
          and len(json.dumps(gross, ensure_ascii=False)) <= a["PULS_DIAGNOSE_MAX"], "Diagnose: hoechstens 12 Profile/Fenster, unter dem Deckel")

    print("\nALLES GRUEN" if ok else "\nFEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
