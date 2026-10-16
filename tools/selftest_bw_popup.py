#!/usr/bin/env python3
"""Selbsttest BUILD-WÄCHTER: Popup sperrt nicht ewig (prophos.html bwGrund, 16.10.2026).

Anlass: Chris · pc-c19p2l hing mit tab_bw „Popup offen" auf .1565, während Copier/Bot schon .1582 hatten — ein vergessenes Popup am
unbeaufsichtigten PC hielt den Tab ohne Zeitgrenze fest.
Aufruf:  python3 tools/selftest_bw_popup.py   (macOS, osascript JavaScript)
Geprüft: (1) beliebiges Popup sperrt unter 15 min, mit Namen im Grund; (2) ab 15 min lädt der Tab trotzdem; (3) Check-/Order-Popup
sperren immer; (4) Eingabe nur bis 15 min; (5) Aufrufer mit 0 (Brücken-Selbstheilung, Fern-Lauf) sperren wie bisher."""
import json
import os
import shutil
import subprocess
import sys

HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prophos.html")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    src = open(HTML, encoding="utf-8").read()
    i = src.index("    const bwGrund = (seitMs) => {")
    j = src.index("\n    window._bwGrund = bwGrund", i)
    fn = src[i:j]
    check("tpPreflightModal" in fn and "tpOrderModal" in fn and "15 * 60 * 1000" in fn, "Quelltext: harte Popups + 15-min-Grenze")
    check("window._bwGrund(15 * 60000) : ruheMin()" in src, "„Tab neu laden“ (Admin-Zuruf) übergeht weiche Popups wie nach 15 min")
    if not shutil.which("osascript"):
        print("· JS-Lauf übersprungen (kein osascript)")
    else:
        js = ("var _tpOrbitLaeuft=false,_rsAktiv=false,_osBusy=false,_osActive=false,tvV2Poll=null,_hedgeBusy=new Set(),_suLaeuft=false,"
              "_pfV2Laeuft=false,tradePlans=[];function pulsTermine(){return []}function hedgePcId(){return 'pc-x'}\n"
              "var OFFEN=[],AKTIV=null;var document={querySelectorAll:function(){return OFFEN.map(function(id){return {id:id}})},"
              "get activeElement(){return AKTIV}};\n" + fn.replace("const bwGrund", "var bwGrund") + "\n"
              "var M=60000,r=[];OFFEN=['tradePlanModal'];r.push(bwGrund(5*M));r.push(bwGrund(16*M));r.push(bwGrund(0));"
              "OFFEN=['tpPreflightModal'];r.push(bwGrund(60*M));OFFEN=['tpOrderModal','finModal'];r.push(bwGrund(60*M));"
              "OFFEN=[];AKTIV={tagName:'INPUT',value:'abc'};r.push(bwGrund(5*M));r.push(bwGrund(16*M));AKTIV=null;r.push(bwGrund(5*M));"
              "JSON.stringify(r)")
        p = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], capture_output=True, text=True)
        try:
            r = json.loads(p.stdout.strip())
        except ValueError:
            r = None
        check(r is not None, f"JS läuft ({p.stderr.strip()[:120]})")
        if r:
            check("tradePlanModal" in r[0] and "15 min" in r[0], f"Popup < 15 min sperrt, nennt das Popup ({r[0]})")
            check(r[1] == "", f"Popup ≥ 15 min sperrt nicht mehr ({r[1]!r})")
            check(r[2] != "", "Aufrufer mit 0 (Brücke/Fern-Lauf): Popup sperrt wie bisher")
            check("tpPreflightModal" in r[3] and "Check/Order" in r[3], f"Check-Popup sperrt immer ({r[3]})")
            check("tpOrderModal" in r[4] and "finModal" not in r[4], f"Order-Popup sperrt immer, Grund nur das harte ({r[4]})")
            check(r[5].startswith("Eingabe offen") and r[6] == "" and r[7] == "", f"Eingabe nur bis 15 min ({r[5:8]})")
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
