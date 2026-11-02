#!/usr/bin/env python3
"""Selbsttest Userscript 0.10.9 KEIN RUECKSTAU (02.11.2026, Lotse Simon: /positions.ts lief der Uhr 101 → 323 s hinterher). postEinzeln mit langsamem Fake-Server:
je Endpunkt höchstens ein offener POST, Ticks dazwischen merken nur den neuesten Stand, nach der Antwort geht genau dieser raus — nie eine Warteschlange.
Ohne Netz, jsc. Aufruf: python3 tools/selftest_reader_kein_rueckstau.py"""
import json
import os
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
US = open(os.path.join(W, "tools", "userscript-test", "tv-reader-0.10.9.user.js"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


i = US.index("  const POST_HAENGT_MS = 10000;")
j = US.index("  function sendeBedienfeld() {")
JS = US[i:j] + r"""
let uhr = 0; Date.now = () => uhr
const offen = [], gesendet = []
const fake = (o) => { offen.push(o); gesendet.push({ url: o.url, data: o.data, at: uhr }) }   // langsamer Server: antwortet erst, wenn der Test es sagt
const antworte = (art) => { const o = offen.shift(); o[art || 'onload']({ responseText: '{}' }) }
const P = 'http://127.0.0.1:8790/positions', B = 'http://127.0.0.1:8790/bedienfeld'
const out = {}
let handler = 0
// 200 Ticks à 50 ms, der Server braucht 3 s für die erste Antwort
for(let k = 0; k < 200; k++){ uhr = k * 50; postEinzeln({ url: P, data: 'stand' + k, onload: () => { handler++ } }, fake) }
out.waehrend = { gesendet: gesendet.length, offen: offen.length }
uhr = 3000; antworte()
out.nach1 = { gesendet: gesendet.length, letzter: gesendet[gesendet.length - 1].data, offen: offen.length, ms: _postLauf[P].ms, handler }
uhr = 3020; antworte()
out.nach2 = { gesendet: gesendet.length, offen: offen.length, busy: _postLauf[P].busy }
postEinzeln({ url: P, data: 'neu', onerror: () => {} }, fake); uhr = 3100; antworte('onerror')
out.fehler = { busy: _postLauf[P].busy, ms: _postLauf[P].ms }
postEinzeln({ url: P, data: 'a' }, fake); postEinzeln({ url: P, data: 'b' }, fake); uhr = 3200; antworte('ontimeout')
out.timeout = { letzter: gesendet[gesendet.length - 1].data, offen: offen.length }
antworte()
postEinzeln({ url: P, data: 'p' }, fake); postEinzeln({ url: B, data: 'bf' }, fake)
out.getrennt = { offen: offen.length, urls: offen.map(o => o.url) }
out.badge = postMs(P)
antworte(); antworte()
postEinzeln({ url: P, data: 'haengt' }, fake); uhr = 20000; postEinzeln({ url: P, data: 'danach' }, fake)
out.haengt = { offen: offen.length, letzter: gesendet[gesendet.length - 1].data }
print(JSON.stringify(out))
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
    t.write(JS)
r = subprocess.run([JSC, t.name], capture_output=True, text=True, timeout=30)
os.unlink(t.name)
if r.returncode or not r.stdout.strip():
    print(r.stdout, r.stderr)
    sys.exit(1)
o = json.loads(r.stdout.strip().splitlines()[-1])
check(o["waehrend"] == {"gesendet": 1, "offen": 1}, "200 Ticks bei langsamem Server: genau ein POST unterwegs, keine Warteschlange")
check(o["nach1"]["gesendet"] == 2 and o["nach1"]["letzter"] == "stand199" and o["nach1"]["offen"] == 1, "nach der Antwort geht sofort nur der neueste Stand (stand199) raus")
check(o["nach1"]["ms"] == 3000 and o["nach1"]["handler"] == 1, "Laufzeit 3000 ms gemessen, Antwort-Handler läuft einmal")
check(o["nach2"] == {"gesendet": 2, "offen": 0, "busy": False}, "nichts Neues gemerkt → nach der zweiten Antwort frei, nichts nachgeschoben")
check(o["fehler"]["busy"] is False, "onerror gibt den Weg frei")
check(o["timeout"]["letzter"] == "b" and o["timeout"]["offen"] == 1, "ontimeout gibt frei und schickt den neuesten (b), nicht a")
check(o["getrennt"]["offen"] == 2 and sorted(o["getrennt"]["urls"]) == sorted(["http://127.0.0.1:8790/positions", "http://127.0.0.1:8790/bedienfeld"]), "/positions und /bedienfeld getrennt, je einer offen")
check(o["badge"].endswith(" ms"), "Plakette zeigt die Laufzeit (" + o["badge"].strip(" ·") + ")")
check(US.count("postEinzeln({") == 2 and "    GM_xmlhttpRequest({\n      method: 'POST',\n      url: ENDPOINT," not in US, "/positions und /bedienfeld laufen über postEinzeln")
check("Puls-Chrome · ${positionen.length} Pos${postMs(ENDPOINT)}" in US, "Puls-Chrome-Plakette mit ms")
check(o["haengt"] == {"offen": 2, "letzter": "danach"}, "kommt 10 s keine Antwort, geht der nächste Stand trotzdem raus (nie für immer still)")
print("ROT:" if FEHLER else "alles grün", FEHLER if FEHLER else "")
sys.exit(1 if FEHLER else 0)
