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
    j = src.index("def puls_inventar_saeubern(")
    exec("\n".join([re.search(r"^PC_ID_MUSTER = .*$", src, re.M).group(0), re.search(r"^PULS_DIAGNOSE_MAX = .*$", src, re.M).group(0),
                    re.search(r"^PULS_INVENTAR_MAX = .*$", src, re.M).group(0),
                    src[i:src.find("\n\n\n", i)], src[j:src.find("\n\n\n", j)]]), ns)
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

    d5 = s({"modus": "tsxlesen", "schritt": "tsx_vorbereitet", "spur": "x" * 5000})
    check(d5["schritt"] == "tsx_vorbereitet" and len(d5["spur"]) == 1800, "B17: Spur + Schritt, Spur auf 1800 gekuerzt")

    pi = a["puls_inventar_saeubern"]
    di = pi({"ok": True, "titel": "NQZ26 $30,921.75", "url": "topstepx.com/trade", "erkannt": {"titel_tsx": 1, "x": 1},
             "tabs": [{"name": "Prophos", "tsx": 0, "tv": 0, "boese": 1}], "seite": [0, 120, 2560, 1400],
             "inventar": {"grund": [["$150K EXPRESS", "Text", [20, 160, 120, 180]], ["x", "Text", "kaputt"]], "boese": [1]},
             "zeilen_kandidaten": [["$150K EXPRESS | EXPRESS-…", [20, 160, 220, 180]]], "edits": ["Adress- und Suchleiste"], "hack": 1})
    check(di and "hack" not in di and di["erkannt"] == {"titel_tsx": True, "url_tsx": False, "titel_tv": False}
          and di["tabs"] == [{"name": "Prophos", "tsx": False, "tv": False}] and "boese" not in di["inventar"]
          and di["inventar"]["grund"][1][2] is None and di["zeilen_kandidaten"][0][1] == [20, 160, 220, 180],
          "B20 Inventar: nur bekannte Felder, Rechtecke nur als Zahlen")
    check(pi(None) is None and pi({"inventar": {"grund": [["n" * 90, "Text", [0, 0, 1, 1]]] * 400}})["inventar"]["grund"].__len__() == 260,
          "B20 Inventar: Unsinn abgewiesen, höchstens 260 Elemente je Zustand")

    d6 = pi({"inventar": {"felder_bracket": [["", "CheckBox", [940, 870, 956, 890], "", 1], ["Risk (~$)", "Edit", [1, 2, 3, 4], "250", True]]}})
    check(d6["felder"]["felder_bracket"] == [["", "CheckBox", [940, 870, 956, 890], "", 1], ["Risk (~$)", "Edit", [1, 2, 3, 4], "250", None]],
          "B26 Inventar v2: Felder mit Wert + Haken, Haken nur als Zahl")

    print("\nALLES GRUEN" if ok else "\nFEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
