#!/usr/bin/env python3
"""Selbsttest: zu_spaet-Ursache über das Neuladen des PC-Tabs (prophos.html _suTabSeit / suWarteLaden / suWarteSpeichern, Fehler-Muster
29.10.2026: 8× „der Prophos-Tab am PC lief nicht (offen erst seit 13:59)" auf drei PCs in 12 s — der Tab lief seit Stunden, das
Update-Neuladen setzte Tab-Uhr und Warte-Gründe zurück). Schneidet die Blöcke aus prophos.html und lässt sie mit einem
nachgebauten sessionStorage laufen (JavaScriptCore des Macs, ohne node) (zwei „Seitenladungen" teilen ihn).  Aufruf: python3 tools/selftest_su_neuladen.py"""
import json
import os
import subprocess
import sys
import tempfile

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
HTML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prophos.html")


def schnitt(src, von, bis):
    i = src.index(von)
    return src[i:src.index(bis, i)]


def main():
    src = open(HTML, encoding="utf-8").read()
    tab = schnitt(src, "  const SU_TAB_SEIT_SS = ", "  const _suClaimGrund = ")
    warte = schnitt(src, "  const _suWarte = new Map()", "  const _suVorcheckGrund = ")
    rest = schnitt(src, "  // Ein Tick: alle fälligen, ungeclaimten Puls-Pläne", "  window._suWarte = ")
    ursache = schnitt(src, "        const ursache = gFrisch ?", "        if(rkGilt(plan)")
    js = r"""
const speicher = {}
globalThis.sessionStorage = { getItem: k => (k in speicher ? speicher[k] : null), setItem: (k, v) => { speicher[k] = String(v) } }
let uhr = Date.parse('2026-10-29T09:00:00Z')
const echtNow = Date.now
Date.now = () => uhr
function seite(){   // eine Seitenladung: frischer Modul-Zustand, derselbe sessionStorage
  return new Function('tradePlans', 'grund', `
    const suNichtGestartet = p => p.status === 'planned' && !p.startUmGestartetAt
    const suPulsWeg = p => true
    const suWarteGrundFuer = (p, o) => grund()
    const tpStartUmText = s => s
    """ + json.dumps(tab + warte + rest)[1:-1].replace("`", "\\`").replace("${", "\\${") + r"""
    function ursacheFuer(plan, verspaetet){
      const startMs0 = new Date(plan.startUm).getTime(), gFrisch = false, g0 = null
      const wh = suWarteHaupt(plan.id), gesehen = _suGesehen.get(String(plan.id)) || 0
      const suUhr = ms => new Date(ms).toISOString().slice(11, 16)
      """ + json.dumps(ursache)[1:-1].replace("`", "\\`").replace("${", "\\${") + r"""
      return ursache
    }
    return { tick: suWarteTick, ursacheFuer, tabSeit: _suTabSeit }
  `)
}
const plan = { id: 'p-1', status: 'planned', startUm: '2026-10-29T10:00:00Z' }
let g = 'Puls für Topstep nicht scharf → Admin → Winning Days → Ablauf „Puls für Topstep" auf „scharf"'
const out = {}
// Ladung 1 um 09:00 (Tab läuft seit vor der Startzeit), Tick jede Minute bis 12:59 — Plan wartet auf „Puls für Topstep"
let s1 = seite()([plan], () => g)
for(uhr = Date.parse('2026-10-29T09:00:00Z'); uhr <= Date.parse('2026-10-29T12:59:00Z'); uhr += 60000) s1.tick({ now: uhr })
out.tabSeit1 = s1.tabSeit
// Update-Neuladen 12:59:28 → Ladung 2, gleicher sessionStorage
uhr = Date.parse('2026-10-29T12:59:28Z')
let s2 = seite()([plan], () => '')
s2.tick({ now: uhr })
out.tabSeit2 = s2.tabSeit
out.ursache = s2.ursacheFuer(plan, uhr - Date.parse(plan.startUm))
// ganz neuer Tab (anderer sessionStorage) erst nach der Startzeit → weiter „lief nicht"
for(const k of Object.keys(speicher)) delete speicher[k]
let s3 = seite()([plan], () => '')
out.ursacheNeu = s3.ursacheFuer(plan, uhr - Date.parse(plan.startUm))
// Neuladen ohne gemerkten Grund (z. B. Speicher voll) → ehrlich „neu geladen", nicht „lief nicht"
speicher['prophos_su_tab_seit'] = String(Date.parse('2026-10-29T09:00:00Z'))
let s4 = seite()([plan], () => '')
out.ursacheOhneGrund = s4.ursacheFuer(plan, uhr - Date.parse(plan.startUm))
// sessionStorage wirft (privater Modus) → Seite lädt trotzdem, Tab-Uhr = jetzt
globalThis.sessionStorage = { getItem: () => { throw new Error('verboten') }, setItem: () => { throw new Error('verboten') } }
let s5 = seite()([plan], () => g)
s5.tick({ now: uhr })
out.ohneSpeicher = s5.tabSeit === uhr
print(JSON.stringify(out))
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
        t.write(js)
    try:
        r = subprocess.run([JSC, t.name], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(t.name)
    if r.returncode != 0 or not r.stdout.strip():
        print(r.stdout[-1000:], r.stderr[-2000:])
        print("FEHLER (jsc)")
        return 1
    o = json.loads(r.stdout.strip().splitlines()[-1])
    f = []
    ok = lambda b, t: f.append(t) if not b else print("✓", t)   # noqa: E731
    neun = 1793264400000   # 29.10.2026 09:00 UTC
    ok(o["tabSeit1"] == neun and o["tabSeit2"] == neun, "Tab-Uhr überlebt das Neuladen (09:00 statt 12:59)")
    ok("Puls für Topstep nicht scharf" in o["ursache"] and "lief nicht" not in o["ursache"] and o["ursache"].startswith("17"),
       f"nach dem Neuladen nennt zu_spaet den Warte-Grund von vorher ({o['ursache'][:70]}…)")
    ok("lief nicht" in o["ursacheNeu"], "wirklich neuer Tab nach der Startzeit → weiter „Tab lief nicht“")
    ok("neu geladen" in o["ursacheOhneGrund"] and "lief nicht" not in o["ursacheOhneGrund"], "Neuladen ohne gemerkten Grund → „lief, wurde neu geladen“")
    ok(o["ohneSpeicher"], "sessionStorage gesperrt → Seite läuft, Tab-Uhr = jetzt")
    for t in f:
        print("✗", t)
    print("alle Tests bestanden" if not f else f"FEHLER ({len(f)})")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
