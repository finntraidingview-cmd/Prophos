#!/usr/bin/env python3
"""Selbsttest: Weiche „TV-Konten lesen auf" (app.py tv_konten_pcs_aus / tv_konten_pc_frei, 29.10.2026, Finn: „Ich möchte nicht immer
Railway-Variablen hinzufügen"). DB-Wert auto_plan_regeln.regeln.tv_konten_pcs schlägt die Railway-Variable; fehlt er, gilt die Variable.
Rein rechnend, Funktionen aus app.py geschnitten.  Aufruf: python3 tools/selftest_tvk_weiche.py"""
import os
import re
import sys

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "os": os, "time": __import__("time")}
    teile = [re.search(r"^TVK_PCS_MUSTER = .*$", src, re.M).group(0), "_tvk_pcs_merk = {'s': 0.0, 'liste': None, 'quelle': ''}"]
    ns["sb_select"] = lambda *a, **k: (_ for _ in ()).throw(AssertionError("kein Netz im Test"))
    for name in ("tv_konten_pcs_aus", "_tv_konten_pcs", "tv_konten_pc_frei"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n\n".join(teile), ns)
    return ns


def main():
    ns = lade()
    A, F = ns["tv_konten_pcs_aus"], ns["tv_konten_pc_frei"]
    f = []
    ok = lambda b, t: f.append(t) if not b else print("✓", t)   # noqa: E731
    ok(A({"tv_konten_pcs": ["pc-c19p2l"]}, "pc-anders1") == (["pc-c19p2l"], "db"), "DB-Wert schlägt die Railway-Variable")
    ok(A({"tv_konten_pcs": []}, "pc-c19p2l") == ([], "db"), "leere DB-Liste = kein PC (Variable zählt dann nicht mehr)")
    ok(A({}, "pc-c19p2l, PC-7FTP5L") == (["pc-7ftp5l", "pc-c19p2l"], "railway"), "ohne DB-Schlüssel → Railway-Variable (Fallback)")
    ok(A(None, "") == ([], "aus") and A({"tv_konten_pcs": "pc-c19p2l"}, "") == ([], "aus"), "nichts gesetzt / DB-Wert keine Liste → aus")
    ok(A({"tv_konten_pcs": ["pc-c19p2l", "alle", "böse;drop", "pc-x"]}, "")[0] == ["alle", "pc-c19p2l"], "nur pc-… und „alle“ werden übernommen")
    # Weiche greift im Abhol-Weg: DB-Liste über den Merker (ohne Netz)
    ns["_tvk_pcs_merk"].update(s=ns["time"].time(), liste=["pc-c19p2l"], quelle="db")
    ok(F("pc-c19p2l") and not F("pc-7ftp5l") and not F(""), "DB-Weiche: nur der eingetragene PC holt Aufträge")
    ns["_tvk_pcs_merk"].update(liste=["alle"])
    ok(F("pc-7ftp5l") and F("pc-c19p2l"), "DB-Weiche „alle“: jeder PC")
    ok(F("pc-c19p2l", roh="pc-c19p2l") and not F("pc-7ftp5l", roh="pc-c19p2l") and F("x", roh="alle"), "Text-Weg (roh) wie bisher")
    for t in f:
        print("✗", t)
    print("alle Tests bestanden" if not f else f"FEHLER ({len(f)})")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
