#!/usr/bin/env python3
"""Selbsttest TOPSTEPX 2.4.32 (02.11.2026): der Hedge-Wächter akzeptiert die eindeutige Endung, wenn der Kopf keine volle Kennung zeigt. Kennungen erfunden, jsc. Aufruf: python3 tools/selftest_tsx_konto_endung.py"""
import json
import os
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(name):
    i = HTML.index(f"function {name}(")
    j = HTML.index("{", HTML.index(")", i))
    t = 0
    for k in range(j, len(HTML)):
        t += {"{": 1, "}": -1}.get(HTML[k], 0)
        if t == 0:
            return HTML[i:k + 1]
    raise ValueError(name)


G = [z for z in HTML.split("\n") if "const tsxKontoGleich = " in z][0]
JS = "\n".join([G, fn("tsxKontoEndung"), fn("tsxKontoPasst"), r"""
const ID = 'EXPRESS-V2-000000-00009147', ANDERS = 'EXPRESS-V2-000000-00006025', GLEICH = 'EXPRESS-V2-000001-11119147'
const K = '150K DLL Express (...9147)', P = (k, ext, ids) => tsxKontoPasst(k, ext || ID, ids || [ID, ANDERS])
print(JSON.stringify({
  marco: P({ aktiv: K, kontonr: null, abgekuerzt: true }),
  feld: P({ aktiv: 'x', endung: '9147', kontonr: null, abgekuerzt: true }),
  ellipse: P({ aktiv: '150K DLL Express (…9147)', kontonr: null }),
  fremd: P({ aktiv: '150K DLL Combine (...6025)', kontonr: null }),
  zwei: P({ aktiv: K, kontonr: null }, ID, [ID, GLEICH]),
  nicht_in_liste: P({ aktiv: K, kontonr: null }, ID, [ANDERS]),
  liste_offen: P({ aktiv: K, kontonr: null, liste_offen: true }),
  ohne_endung: P({ aktiv: '150K DLL Express', kontonr: null }),
  drei_ziffern: P({ aktiv: '150K (...147)', kontonr: null }),
  voll: P({ kontonr: ID, abgekuerzt: false }),
  voll_kurz: P({ kontonr: ID, abgekuerzt: true }),
  voll_fremd: P({ kontonr: ANDERS, abgekuerzt: false }),
}))
"""])
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
    t.write(JS)
r = subprocess.run([JSC, t.name], capture_output=True, text=True, timeout=30)
os.unlink(t.name)
if r.returncode or not r.stdout.strip():
    print(r.stdout, r.stderr)
    sys.exit(1)
e = json.loads(r.stdout.strip().splitlines()[-1])
check(e["marco"] and e["feld"] and e["ellipse"], "Kopf „(...9147)“ oder Feld endung: Konto erkannt")
check(not e["fremd"], "andere Endung: nein")
check(not e["zwei"] and not e["nicht_in_liste"], "zwei Konten mit der Endung oder Plan-Konto nicht in der Liste: nein")
check(not e["liste_offen"] and not e["ohne_endung"] and not e["drei_ziffern"], "Liste offen oder keine vierstellige Endung: nein")
check(e["voll"] and not e["voll_kurz"] and not e["voll_fremd"], "volle Kennung wie bisher")
i = HTML.index("async function hedgeTsxSchnellTick(")
t = HTML[i:HTML.index("setInterval(hedgeTsxSchnellTick", i)]
check("!tsxKontoPasst(k, kontoPlan, kontoExtIds())" in t and "st.konto.kontonr || tsxKontoEndung(st.konto)" in t, "Wächter nutzt die Regel, kein „blind“ allein wegen fehlender kontonr")
_a = open(os.path.join(W, "tv-reader", "tsx-auge.user.js"), encoding="utf-8").read()
check("s.konto.kontonr || s.konto.aktiv" in _a and "endung: k.endung || null" in _a, "Auge: Flach-Folge zählt auch ohne volle Kennung, meldet die Endung")
print("\nTSX-KONTO: alles grün" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
