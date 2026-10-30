#!/usr/bin/env python3
"""Selbsttest HEIM-WACHE LEER-TEXT (30.10.2026, Slave 6 — Master: „kein Blind-Heimweg, solange Puls laut Konto-Beleg schon im Plan-Konto
steht"; Simon pc-pmqd8g: der Reader war blind, weil er TradingViews Leer-Text nicht kannte, jeder Heimweg hielt hedgePulsUnterwegs() wach
und der Schnell-Wächter schloss Fusion nicht). hwNurLeerText per macOS-JavaScriptCore (jsc) aus prophos.html geschnitten, dazu der
Quelltext-Vertrag in heimWacheTick (nur mit kontoBelegGilt + heimKontoPasst, ohne Sperre) und das Grund-Format im Userscript.
Aufruf: python3 tools/selftest_heimwache_leertext.py"""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HIER, "..", "prophos.html")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def js_funktion(src, name):
    """Funktionsquelltext per Klammerzählung (wie tools/selftest_kurz_summary_keys.py)."""
    i = src.index(f"function {name}(")
    j = src.index("{", src.index(")", i))
    tiefe = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            tiefe += 1
        elif src[k] == "}":
            tiefe -= 1
            if tiefe == 0:
                return src[i:k + 1]
    raise ValueError(name)


def main():
    src = open(HTML, encoding="utf-8").read()
    G = "kein Leer-Beweis: Leer-Text nicht erkannt | Konto: "
    TABS = [{"tab_id": "puls-a", "alter_s": 0.4}, {"tab_id": "t-feed", "alter_s": 0.2}]
    def st(grund, tabs=TABS, tab="puls-a", pos=None):
        return {"positionen_ok": False, "blind_grund": grund, "positionen_tab": tab, "tabs": tabs, "positionen": pos or []}
    faelle = [
        # (Name, st, Plan-Konto passt zu, erwartet)
        ("Leer-Text im Plan-Konto, Tab frisch → ohne Heimweg", st(G + "PLANKONTO 150,000.00 USD"), "PLANKONTO", True),
        ("Leer-Text, Handwechsel in fremdes Konto → Heimweg", st(G + "FREMD 99,000.00 USD"), "PLANKONTO", False),
        ("Leer-Text ohne Konto-Angabe (0.10.4-Vorstand) → Heimweg", st("kein Leer-Beweis: Leer-Text nicht erkannt"), "PLANKONTO", False),
        ("Leer-Text, Puls-Tab still (alter_s 25) → Heimweg", st(G + "PLANKONTO", tabs=[{"tab_id": "puls-a", "alter_s": 25}]), "PLANKONTO", False),
        ("Leer-Text, Puls-Tab fehlt in tabs → Heimweg", st(G + "PLANKONTO", tabs=[{"tab_id": "t-feed", "alter_s": 0.2}]), "PLANKONTO", False),
        ("Leer-Text, tabs fehlt → Heimweg", st(G + "PLANKONTO", tabs=None), "PLANKONTO", False),
        ("Leer-Text, eingefrorener Stand mit pnl_unklar → Heimweg", st(G + "PLANKONTO", pos=[{"pnl_unklar": True}]), "PLANKONTO", False),
        ("Reiter Positions nicht aktiv → Heimweg", st("kein Leer-Beweis: Reiter Positions nicht aktiv"), "PLANKONTO", False),
        ("alter Sammel-Grund bis 0.10.3 → Heimweg", st("kein Leer-Beweis (Reiter Positions nicht aktiv oder Leer-Text fehlt)"), "PLANKONTO", False),
        ("pnl unlesbar → Heimweg", st("pnl unlesbar in 1 Zeile(n)"), "PLANKONTO", False),
        ("kein Konto angemeldet → Heimweg", st("kein Konto angemeldet"), "PLANKONTO", False),
        ("kein Stand → Heimweg", None, "PLANKONTO", False),
    ]
    code = js_funktion(src, "hwNurLeerText") + "\nvar F = " + json.dumps([[f[1], f[2]] for f in faelle]) + \
        ";\nprint(JSON.stringify(F.map(function (x) { return hwNurLeerText(x[0], function (t) { return t.split(' ')[0] === x[1]; }); })));\n"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(code)
    aus = json.loads(subprocess.run([JSC, f.name], capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])
    os.unlink(f.name)
    for (name, _st, _k, soll), ist in zip(faelle, aus):
        check(ist is soll, name)
    # Vertrag: nur mit Konto-Beleg, Konto-Abgleich über heimKontoPasst, OHNE Sperre (_hwBlindErledigt) im Leer-Text-Zweig
    check("if(pnlBlind && kontoBelegGilt(konto) && hwNurLeerText(st, t => heimKontoPasst(t, konto))) return" in src,
          "heimWacheTick: nur mit kontoBelegGilt + heimKontoPasst, ohne _hwBlindErledigt")
    check("if(!pnlBlind && kontoBelegGilt(konto)){ _hwBlindErledigt = pid; return }" in src, "alter Weg (nicht pnl-blind) unverändert")
    check(src.count("hwNurLeerText(") == 2 and "window._hwNurLeerText = hwNurLeerText" in src, "Test-Haken + genau ein Aufruf")
    us = open(os.path.join(HIER, "..", "tv-reader", "tv-reader.user.js"), encoding="utf-8").read()
    check("'kein Leer-Beweis: Leer-Text nicht erkannt | Konto: ' + String(kontoMerk.text || '').slice(0, 64)" in us,
          "Userscript schreibt das aktuelle Konto in den Leer-Text-Grund (Format = Regex der Heim-Wache)")
    if FEHLER:
        print(f"\nFEHLER ({len(FEHLER)})")
        sys.exit(1)
    print("\nalle Tests bestanden")


if __name__ == "__main__":
    main()
