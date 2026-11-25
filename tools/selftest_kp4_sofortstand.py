#!/usr/bin/env python3
"""Selbsttest KP4 (26.11.2026, Finn: „Nach einem Reload dauert es, bis Musterportfolio und Kaufliste erscheinen — ich will sie sofort sehen").
(1) Der Speicher window._kp4 (IndexedDB, NICHT localStorage) echt in macOS-jsc mit einem kleinen IndexedDB-Ersatz: schreiben/lesen je ID,
    fremde ID sieht nichts, Größenbremse, Höchstalter, Abmelden löscht, ohne IndexedDB kein Fehler.
(2) Verdrahtung im Quelltext: Muster-Portfolio und Kaufliste zeichnen den gemerkten Stand sofort (nur gleiche ID, nur wenn noch nichts da ist),
    frisch ersetzt still; Antwort einer gewechselten ID verworfen; Kaufliste nur Accounts (nicht Admin „Alle IDs"); pa1 (grün/Countdown) nie aus
    dem Speicher; „Stand HH:MM" am gemerkten Stand; Abmelden leert; nach dem Login sofort angestoßen; kein localStorage im KP4-Weg.
Aufruf:  python3 tools/selftest_kp4_sofortstand.py
"""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = open(os.path.join(os.path.dirname(HIER), "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
n = 0


def check(ok, text):
    global n
    if not ok:
        print("✗", text)
        sys.exit(1)
    n += 1
    print("✓", text)


i = HTML.index("/* ── KP4 SOFORTSTAND ACCOUNTS")
j = HTML.index("/* ── MUSTER-PORTFOLIO (16.10.2026")
kp4 = HTML[i:j]
check("localStorage" not in kp4.replace("NICHT localStorage", "").replace("Memory „localStorage voll“", "").replace("Memory „localStorage voll\"", ""),
      "KP4-Speicher nutzt kein localStorage")

MOCK = r"""
var window = {}; var store = {};
function req(){ return { onsuccess: null, onerror: null, onupgradeneeded: null, result: null } }
var fakeDb = { transaction: function(){ return { objectStore: function(){ return {
  get: function(k){ var r = req(); Promise.resolve().then(function(){ r.result = store.hasOwnProperty(k) ? JSON.parse(JSON.stringify(store[k])) : undefined; r.onsuccess && r.onsuccess() }); return r },
  put: function(v, k){ store[k] = JSON.parse(JSON.stringify(v)) },
  delete: function(k){ delete store[k] } } } } } };
var indexedDB = { open: function(){ var r = req(); Promise.resolve().then(function(){ r.result = fakeDb; r.onupgradeneeded && r.onupgradeneeded(); r.onsuccess && r.onsuccess() }); return r } };
fakeDb.createObjectStore = function(){};
"""
TEST = r"""
var K = window._kp4, out = {};
(async function(){
  await K.schreiben('mp', 'uidA', { firmen: [{ firma: 'Tradeify' }] });
  await K.schreiben('kl', 'uidA', { zeilen: [{ firma: 'Tradeify', n: 2 }] });
  var a = await K.lesen('mp', 'uidA'); out.gleicheId = !!(a && a.d.firmen[0].firma === 'Tradeify' && a.at > 0);
  out.fremdeId = (await K.lesen('mp', 'uidB')) === null;
  out.andereArt = !!(await K.lesen('kl', 'uidA'));
  out.ohneId = (await K.lesen('mp', '')) === null;
  // Eintrag unter falschem Schlüssel (andere uid im Eintrag) wird nie angewendet
  store['mp|uidC'] = { art: 'mp', uid: 'uidA', at: Date.now(), t: '{"firmen":[]}' }; out.fremderEintrag = (await K.lesen('mp', 'uidC')) === null;
  // Größenbremse 1 MB
  var gross = { zeilen: [], x: new Array(1100000).join('a') }; await K.schreiben('kl', 'uidG', gross); out.groesse = !store.hasOwnProperty('kl|uidG');
  // Höchstalter 24 h
  store['mp|uidA'].at = Date.now() - 25 * 3600 * 1000; out.alt = (await K.lesen('mp', 'uidA')) === null;
  // kaputtes JSON → null statt Fehler
  store['kl|uidK'] = { art: 'kl', uid: 'uidK', at: Date.now(), t: '{kaputt' }; out.kaputt = (await K.lesen('kl', 'uidK')) === null;
  // Abmelden
  await K.leeren('uidA'); out.leeren = !store.hasOwnProperty('kl|uidA') && !store.hasOwnProperty('mp|uidA');
  print(JSON.stringify(out));
})().catch(function(e){ print(JSON.stringify({ fehler: String(e) })) });
"""
OHNE = r"""
var window = {};
""" + kp4 + r"""
;(async function(){ var a = await window._kp4.lesen('mp', 'x'); await window._kp4.schreiben('mp', 'x', {}); await window._kp4.leeren('x'); print(JSON.stringify({ ohneIdb: a === null })) })()
  .catch(function(e){ print(JSON.stringify({ fehler: String(e) })) });
"""


def jsc(code):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(code)
        pfad = f.name
    try:
        r = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=30)
    finally:
        os.unlink(pfad)
    if r.returncode != 0 or not r.stdout.strip():
        raise SystemExit("jsc: " + (r.stderr or r.stdout)[:600])
    return json.loads(r.stdout.strip().splitlines()[-1])


e = jsc(MOCK + kp4 + TEST)
check("fehler" not in e, f"jsc läuft {e.get('fehler', '')}")
for k, txt in [("gleicheId", "gleiche ID liest ihren Stand (mit Zeit)"), ("fremdeId", "fremde ID sieht nichts"), ("andereArt", "Kaufliste + Muster-Portfolio getrennt"),
               ("ohneId", "ohne ID nichts"), ("fremderEintrag", "Eintrag mit anderer ID im Inhalt wird nie angewendet"), ("groesse", "Größenbremse 1 MB"),
               ("alt", "älter als 24 h → nicht gezeigt"), ("kaputt", "kaputter Eintrag → kein Fehler, nichts gezeigt"), ("leeren", "Abmelden löscht beide Einträge der ID")]:
    check(e.get(k) is True, f"Speicher: {txt}")
o = jsc(OHNE)
check(o.get("ohneIdb") is True, "ohne IndexedDB: kein Fehler, einfach wie bisher")

# ── (2) Verdrahtung ──
mp = HTML[HTML.index("  async function mpLaden(){"):HTML.index("  async function mpSchalten(")]
check("if(!_mp.d && window._kp4) window._kp4.lesen('mp', uid).then(c => {" in mp and "if(!c || _mp.d || !c.d || !Array.isArray(c.d.firmen) || uid !== String(currentUserId || '')) return" in mp,
      "Muster-Portfolio: gemerkter Stand nur wenn noch nichts da + gleiche ID")
check(mp.index("window._kp4.lesen('mp'") < mp.index("const r = await fetch("), "Muster-Portfolio: Speicher-Lesen läuft parallel zum Abruf (nicht davor gewartet)")
check("if(uid !== String(currentUserId || '')){ _mp.laedt = false; return }" in mp and "window._kp4?.schreiben('mp', uid, d)" in mp,
      "Muster-Portfolio: Antwort einer gewechselten ID verworfen, frische Antwort gemerkt")
check("if(_mp.uid !== uid){ _mp.d = null; _mp.zeig = {} }" in mp, "Muster-Portfolio: ID-Wechsel leert weiter zuerst")
kl_oeff = HTML[HTML.index("    function oeffnen(){\n      const uid = String(currentUserId || '')"):HTML.index("    return { cfg, I, laden, render, oeffnen,")]
check("if(!I.d && !cfg.alle && uid && window._kp4) window._kp4.lesen('kl', uid).then(c => {" in kl_oeff and "uid !== String(currentUserId || '')) return" in kl_oeff,
      "Kaufliste: gemerkter Stand nur Accounts, nur gleiche ID, nur wenn noch nichts da")
check("I.pa1 = []; I.pa1Lokal = [];" in kl_oeff and "render(); pa1Laden()" in kl_oeff, "Kaufliste: pa1 (grün/Countdown) beim ID-Wechsel leer, nach dem Sofortstand frisch geholt — nie aus dem Speicher")
check("if(!cfg.alle) try{ window._kp4?.schreiben('kl', uid, d) }catch(_){}" in HTML, "Kaufliste: nur die Accounts-Antwort wird gemerkt")
check("pa1" not in HTML[HTML.index("if(!cfg.alle) try{ window._kp4?.schreiben('kl'"):HTML.index("if(!cfg.alle) try{ window._kp4?.schreiben('kl'") + 80], "Kaufliste: gemerkt wird I.d (Liste), nicht I.pa1")
check("(I.ausSpeicher ? ` · Stand ${new Date(I.ausSpeicher).toLocaleTimeString('de-DE'" in HTML and "I.ausSpeicher = 0" in HTML, "Kaufliste: „Stand HH:MM“ nur am gemerkten Stand, frisch löscht ihn")
check("try{ window._kp4?.leeren(currentUserId) }catch(_){}" in HTML, "Abmelden leert den Sofortstand der ID")
check("window._mpOeffnen?.(); window._klOeffnen?.()" in HTML, "nach dem Login sofort angestoßen, wenn Accounts schon offen ist")

check("if(!frisch && I.laeuft && I.laeuft.uid === uid0 && Date.now() - I.laeuft.at < 20000) return" in HTML and "try{ await ladenEcht(frisch) }finally{" in HTML,
      "Kaufliste: ein Abruf je ID gleichzeitig (Start stieß bis zu 5 an), „frisch“ nach eigenem Schreiben immer")

print(f"\n{n} Prüfungen grün")
