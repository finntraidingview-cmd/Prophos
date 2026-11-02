#!/usr/bin/env python3
"""Selbsttest ROLLOUT BEI GESPERRTEM EVAL (02.11.2026): tvTmNoetig löst das Tampermonkey-Update nur aus, wenn der Lader nichts tauschen kann und eine ältere Fassung läuft. Ohne Netz, jsc.
Aufruf: python3 tools/selftest_tv_tm_rollout.py"""
import json
import os
import re
import subprocess
import sys
import tempfile

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
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


SOLL = re.search(r"const TVTM_VERSION_SOLL = '([\d.]+)'", HTML).group(1)
A = HTML[HTML.index("  const TVTM_LADER_SOLL = "):HTML.index("  const TVTM_NICHTS_ANGEFASST")]
N = re.search(r"  const tvnNeuer = .*?\n.*?\n", HTML).group(0)
JS = "\n".join([N, A, "const TVN_ART = { tv: { name: 'TV', erster: '0.10.0' }, tsx: { name: 'Auge', erster: '0.3.0' } }", fn("tvTmNoetig"), r"""
const SOLL = TVTM_VERSION_SOLL, ALT = '0.10.5'
const n = b => tvTmNoetig(b)
print(JSON.stringify({
  gesperrt_alt: n({ art: 'tv', lader: { v: 1, eval: false, laeuft: ALT } }),
  gesperrt_aktuell: n({ art: 'tv', lader: { v: 1, eval: false, laeuft: SOLL } }),
  gesperrt_neuer: n({ art: 'tv', lader: { v: 1, eval: false, laeuft: '9.0.0' } }),
  eval_ok_alt: n({ art: 'tv', lader: { v: 1, eval: true, laeuft: ALT } }),
  eval_unbekannt: n({ art: 'tv', lader: { v: 1, laeuft: ALT } }),
  version_aus_tab: n({ art: 'tv', version: ALT, lader: { v: 1, eval: false } }),
  version_unbekannt: n({ art: 'tv', lader: { v: 1, eval: false } }),
  lader_alt: n({ art: 'tv', lader: { v: 0, eval: true, laeuft: SOLL } }),
  tsx_gesperrt: n({ art: 'tsx', lader: { v: 1, eval: false, laeuft: '0.1.0' } }),
  ohne_lader_alt: n({ art: 'tv', version: '0.9.9' }),
  ohne_lader_neu: n({ art: 'tv', version: '0.10.5' }),
  key: tvTmKey('tv'), key_tsx: tvTmKey('tsx'), ziel: tvTmZiel('tv'), soll: SOLL,
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
check(e["gesperrt_alt"] == "" and e["version_aus_tab"] == "", "eval gesperrt, ältere Fassung: Update nötig")
check(e["gesperrt_aktuell"] and e["gesperrt_neuer"], "eval gesperrt, aktuelle oder neuere Fassung: nicht nötig")
check(e["eval_ok_alt"] and e["eval_unbekannt"], "eval frei oder unbekannt: der Lader bleibt zuständig")
check(e["version_unbekannt"], "Version unbekannt: nichts anfassen")
check(e["lader_alt"] == "", "alter Lader: wie bisher nötig")
check(e["tsx_gesperrt"], "TopstepX unverändert")
check(e["ohne_lader_alt"] == "" and e["ohne_lader_neu"], "ohne Lader wie bisher")
check(e["key"] == "prophos_tvtm_l1_v" + SOLL and e["key_tsx"] == "prophos_tvtm_tsx_l1", "Sperre je Fassung, TopstepX wie bisher")
check(e["ziel"] == SOLL, "Meldung nennt die Fassung")
check("Ab jetzt kommen Updates" not in open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read(), "tm_ok verspricht den Lader nicht mehr")
print("\nROLLOUT: alles grün" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
