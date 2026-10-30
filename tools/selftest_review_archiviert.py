#!/usr/bin/env python3
"""Selbsttest REVIEW TROTZ NACHFOLGER (prophos.html wdlKontoArchiviert, 30.10.2026 — Finn: Simon Topstep …9002 stand nach dem Nachfolger weiter in Review, „bestanden 18:08").
Aufruf:  python3 tools/selftest_review_archiviert.py   (ohne Netz; Quelltext-Prüfung, der Ablauf läuft im Stub)."""
import json
import os
import subprocess
import sys
import tempfile

html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


f = html[html.index("function wdlKontoArchiviert("):html.index("function wdlBestandenChip(")]
check("(t.konto || {}).archiviert" in f and "getArchive()" in f, "Archiv: fremde IDs vom Server, eigene ID lokal")
b = html[html.index("function wdlBestandenChip("):]
check("if(wdlKontoArchiviert(t)) return ''" in b[:400], "kein Bestanden-Chip auf archiviertem Konto: keine lokale Review-Zeile, kein „Trade abhaken“")
la = html[html.index("function bstLokalAnwenden("):html.index("function abhakZielNachziehen(")]
check("wdlKontoArchiviert(t)" in la and "_bstLokal.delete(kid)" in la, "vorhandene lokale Zeile fällt nach dem Archivieren weg")
check("m.schritt === 'geparkt') && !wdlKontoArchiviert(t)" in html, "geparkter Trade eines archivierten Kontos steht nicht unter Review")

# RADAR-REVIEW BIS NACHFOLGER (R1, 30.10.2026): Rechnung im echten JS (jsc), Verdrahtung am Quelltext
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"


def fn(name):
    i = html.index("function " + name + "(")
    j = html.index("\n  }\n", i)
    return html[i:j + 4]


probe = fn("bstServerZeileGilt") + fn("archivStandGleich") + fn("nachfolgerNochOffen") + r"""
const a = JSON.stringify
const e = new Set(['e1'])
print(a([
  bstServerZeileGilt({konto_id:'k1'}, e, {k1:{archived:true,reason:'passed'}}),
  bstServerZeileGilt({konto_id:'k1'}, e, {k1:{archived:false}}),
  bstServerZeileGilt({konto_id:'k1'}, e, {}),
  bstServerZeileGilt({konto_id:'e1'}, e, {}),
  bstServerZeileGilt(null, e, {}),
  bstServerZeileGilt({konto_id:'k1'}, e, null),
  archivStandGleich({a:{archived:true,reason:'passed',at:'1'}}, {a:{archived:true,reason:'passed',at:'2'}}),
  archivStandGleich({}, {a:{archived:true,reason:'passed'}}),
  archivStandGleich({a:{archived:true,reason:'passed_pending'}}, {a:{archived:true,reason:'passed',successorId:'x'}}),
  archivStandGleich({a:{archived:true}, b:{archived:false}}, {a:{archived:true}}),
  nachfolgerNochOffen({archived:true,reason:'passed',successorId:'n1'}),
  nachfolgerNochOffen({archived:true,reason:'passed_pending'}),
  nachfolgerNochOffen(undefined),
]))
"""
d = tempfile.mkdtemp()
pf = os.path.join(d, "probe.js")
open(pf, "w", encoding="utf-8").write(probe)
aus = subprocess.run([JSC, pf], capture_output=True, text=True, timeout=30)
w = json.loads(aus.stdout.strip() or "[]") if aus.returncode == 0 else []
check(w[:6] == [False, True, True, False, False, True], f"Serverliste: lokal archiviert raus, sonst drin, eigene nicht doppelt ({w[:6]})")
check(w[6:10] == [True, False, False, True], f"Archiv-Abgleich: Zeitstempel egal, neuer Eintrag und neuer Grund zählen ({w[6:10]})")
check(w[10:] == [False, True, True], f"Assistent: mit Nachfolger zu, passed_pending und ohne Eintrag offen ({w[10:]})")

# Rennen im Abgleich (S2 zu 9f3788bb): echte Funktion mit nachgebautem Lesen, das während des await etwas ändert
renn = fn("archivStandGleich") + fn("archivCloudAbgleich").replace("function archivCloudAbgleich", "async function ab") + r"""
const ARCH_LS = 'k', _archNeu = {}, speicher = {}
const localStorage = { getItem: k => speicher[k] ?? null }
const _origLocalStorageSetItem = { call: (_, k, v) => { speicher[k] = v } }
const getArchive = () => JSON.parse(speicher.k || '{}')
const renderAccounts = () => {}
let currentUserId = 'u1', beimLesen = () => {}
const fetchSetting = async () => { beimLesen(); return { x: { archived: true, reason: 'passed' } } }
;(async () => {
  const aus = []
  speicher.k = '{}'; aus.push(await ab(), speicher.k)
  speicher.k = '{}'; beimLesen = () => { currentUserId = 'u2' }; aus.push(await ab(), speicher.k)
  speicher.k = '{"y":{"archived":true}}'; beimLesen = () => { speicher.k = '{}' }; aus.push(await ab(), speicher.k)
  print(JSON.stringify(aus))
})()
"""
pf2 = os.path.join(d, "renn.js")
open(pf2, "w", encoding="utf-8").write(renn)
aus2 = subprocess.run([JSC, pf2], capture_output=True, text=True, timeout=30)
r = json.loads(aus2.stdout.strip() or "[]") if aus2.returncode == 0 else []
check(r[:2] == [True, '{"x":{"archived":true,"reason":"passed"}}'], f"Abgleich übernimmt die Cloud ({r[:2]}{aus2.stderr[:120]})")
check(r[2:4] == [False, "{}"], f"ID-Wechsel während des Lesens: verworfen ({r[2:4]})")
check(r[4:6] == [False, "{}"], f"Entarchivieren während des Lesens: Konto kommt nicht zurück ({r[4:6]})")
b2 = html[html.index("const bstZeilen = () =>"):html.index("const bstTab = (zz")]
check("bstServerZeileGilt(z, eigeneIds, archB)" in b2, "bstZeilen filtert die Serverliste gegen das lokale Archiv")
ok = html[html.index("getElementById('successorConfirm')"):html.index("/* ========== ARCHIV-FILTER")]
de = html[html.index("getElementById('successorDefer')"):html.index("/* NACHFOLGER = TRADE ABHAKEN")]
check("nachfolgerRadarNachziehen()" in ok and "nachfolgerRadarNachziehen()" in de, "Anlegen und Später eintragen zeichnen den Radar neu, von jedem Weg aus")
hl = html[html.index("async function handLaden("):html.index("function handZielAbgleich(")]
check("archivCloudAbgleich()" in hl and "wdlAktiv()" in hl, "offener Radar gleicht das Archiv im Handarbeit-Takt ab")
ab = fn("archivCloudAbgleich")
check("_archNeu" in ab and "_origLocalStorageSetItem" in ab and "saveArchive" not in ab, "Abgleich schreibt nur lokal, ohne Upload, eigene Einträge bleiben")
sp = html[html.index("async function mklWdErledigtSpeichern("):html.index("document.getElementById('mwdErledigtClose')")] if "async function mklWdErledigtSpeichern(" in html else ""
check("kontoStatus === 'passed'" in sp and "if(nachfolgerNochOffen(arch[ar.konto_id])) setTimeout(() => openSuccessorWizard(ar.konto_id)" in sp and "await archivCloudAbgleich()" in sp and "reason: 'passed_pending'" in sp, "Abhaken „Phase bestanden“ am eigenen Konto öffnet den Assistenten")
check("archivieren" not in fn("nachfolgerRadarNachziehen").lower() and "erledigt" not in fn("nachfolgerRadarNachziehen").lower(), "Nachziehen ist nur Anzeige: kein Abhaken, kein P&L")
print(f"\n{'selftest_review_archiviert: alle Prüfungen grün' if not FEHLER else f'✗ {len(FEHLER)} Fehler'}")
sys.exit(1 if FEHLER else 0)
