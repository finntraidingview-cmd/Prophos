#!/usr/bin/env python3
"""Selbsttest KURZ-KURS-CLOUD (30.10.2026, Slave 6 — Simon pc-pmqd8g Test 4, Plan a92dde45: im Puls-Chrome-Modus liefert das Userscript keine
Kurse, kurzKursJetzt gab 0, kurzFensterNeu löschte das Fenster, reader_kurz_nein „Fenster nicht eingefroren", Fusion blieb offen, obwohl der Reader
flach meldete). kurzKursJetzt + kurzFensterNeu per macOS-JavaScriptCore (jsc) aus prophos.html geschnitten, Quellen gestellt.
Aufruf: python3 tools/selftest_kurz_kurs_cloud.py"""
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
    i = src.index("function kurzFensterNeu(")
    fneu = src[i:src.index("\n", i)]
    harness = """
var JETZT = 1000000; var Date = { now: function () { return JETZT; } };
var epLokal = { stand: null, ab: 0 }, mkl = { kursJe: {} }, _hedgeKurs = { at: 0, wert: null, laeuft: null }, gelesen = 0, _kurzFenster = new Map();
function hedgeKursAlterJetzt(k) { return JETZT - k.at; }
function hedgeKursLesen() { gelesen++; return Promise.resolve(null); }
""" + js_funktion(src, "kurzKursJetzt") + "\n" + fneu + """
var aus = [];
// 1) nur lokaler Reader
epLokal = { stand: { kurse: { MNQ: { preis: 28950.5 } } }, ab: JETZT - 1000 }; aus.push(kurzKursJetzt('MNQ'));
// 2) kein Reader, Realtime
epLokal = { stand: null, ab: 0 }; mkl.kursJe = { MNQ: { preis: 28951, at: JETZT - 2000 } }; aus.push(kurzKursJetzt('MNQ'));
// 3) Simon: kein Reader-Kurs, kein Realtime, Cloud frisch (MNQ, 1,2 s alt, vor 0,5 s gelesen) → Cloud
mkl.kursJe = {}; _hedgeKurs = { at: JETZT - 500, wert: { preis: 28952.25, wurzel: 'MNQ', alter_ms: 1200 }, laeuft: null }; aus.push(kurzKursJetzt('MNQ'));
// 4) Cloud NQ statt MNQ (≈) → zählt
_hedgeKurs = { at: JETZT - 500, wert: { preis: 28953, wurzel: 'NQ', alter_ms: 800 }, laeuft: null }; aus.push(kurzKursJetzt('MNQ'));
// 5) Cloud zu alt (alter 4 s + 2 s seit dem Lesen) → 0, Auffrischen angestoßen
gelesen = 0; _hedgeKurs = { at: JETZT - 2000, wert: { preis: 28953, wurzel: 'MNQ', alter_ms: 4000 }, laeuft: null }; aus.push(kurzKursJetzt('MNQ')); aus.push(gelesen);
// 6) keine Quelle → 0 und Auffrischen angestoßen
gelesen = 0; _hedgeKurs = { at: 0, wert: null, laeuft: null }; aus.push(kurzKursJetzt('MNQ')); aus.push(gelesen);
// 7) Cloud-Wurzel fremd (z. B. ES) → 0
_hedgeKurs = { at: JETZT - 100, wert: { preis: 6000, wurzel: 'ES', alter_ms: 100 }, laeuft: null }; aus.push(kurzKursJetzt('MNQ'));
// 8) kurzFensterNeu mit Cloud-Kurs legt das Fenster an (statt es zu löschen)
_hedgeKurs = { at: JETZT - 500, wert: { preis: 28952.25, wurzel: 'MNQ', alter_ms: 1200 }, laeuft: null }; kurzFensterNeu('p1', 'MNQ');
var f = _kurzFenster.get('p1'); aus.push(f ? [f.lo, f.hi, f.zu] : null);
// 9) ohne jede Quelle → Fenster weg (wie bisher, kein Beweis)
_hedgeKurs = { at: 0, wert: null, laeuft: null }; kurzFensterNeu('p1', 'MNQ'); aus.push(_kurzFenster.has('p1'));
print(JSON.stringify(aus));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(harness)
    r = subprocess.run([JSC, fh.name], capture_output=True, text=True)
    os.unlink(fh.name)
    if r.returncode != 0 or not r.stdout.strip():
        print(r.stdout, r.stderr)
        sys.exit(1)
    a = json.loads(r.stdout.strip().splitlines()[-1])
    check(a[0] == 28950.5, "lokaler Reader-Kurs zuerst")
    check(a[1] == 28951, "ohne Reader: Realtime (mkl.kursJe)")
    check(a[2] == 28952.25, "Simon: ohne Reader/Realtime → Cloud-Kurs (≤ 5 s)")
    check(a[3] == 28953, "Cloud NQ für MNQ (≈ < 1 Pkt)")
    check(a[4] == 0 and a[5] >= 1, "Cloud zu alt → 0, Auffrischen angestoßen")
    check(a[6] == 0 and a[7] >= 1, "keine Quelle → 0, Auffrischen angestoßen")
    check(a[8] == 0, "fremde Wurzel → 0")
    check(a[9] == [28952.25, 28952.25, 0], "kurzFensterNeu legt das Fenster mit dem Cloud-Kurs an (offen, nicht gelöscht)")
    check(a[10] is False, "ohne jede Quelle → Fenster weg (kein Beweis, wie bisher)")
    if FEHLER:
        print(f"\nFEHLER ({len(FEHLER)})")
        sys.exit(1)
    print("\nalle Tests bestanden")


if __name__ == "__main__":
    main()
