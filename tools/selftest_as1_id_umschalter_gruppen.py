#!/usr/bin/env python3
"""Selbsttest AS1 (Master 25.11.2026, Finn): ID-Umschalter im Profil-Menü nach Unternehmen — oben „Hermann Technologies“, dann „Emin“ (jede
weitere Gruppe nach Name), IDs ohne bekannte Gruppe ganz unten, je Abschnitt alphabetisch; ohne Gruppen-Daten alphabetisch ohne Überschriften.
Echte Funktionen aus prophos.html in JavaScriptCore (profGruppenLesen, profGruppenMerken, profMenuAbschnitte, renderProfileMenu mit kleinem
DOM-Ersatz). Ohne Netz. Aufruf: python3 tools/selftest_as1_id_umschalter_gruppen.py"""
import json
import os
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def block(a, b):
    i = HTML.index(a)
    return HTML[i:HTML.index(b, i)]


HT = {"id": "g-ht", "name": "Hermann Technologies", "ht": True, "ids": [], "ausser": ["e1", "e2", "e3"]}
EM = {"id": "g-em", "name": "Emin", "ht": False, "ids": ["e1", "e2", "e3"]}
PROFILE = [  # Reihenfolge wie im Screenshot: durcheinander
    {"userId": "e1", "email": "emin@x", "name": "Emin"}, {"userId": "h1", "email": "moritz@x", "name": "Moritz"},
    {"userId": "h2", "email": "jacob@x", "name": "Jacob"}, {"userId": "h3", "email": "pascal@x", "name": "Pascal"},
    {"userId": "h4", "email": "ez@x", "name": "EzPoker"}, {"userId": "h5", "email": "fp@x", "name": "Finn + Pascal"},
    {"userId": "e2", "email": "amir@x", "name": "amir"}, {"userId": "n1", "email": "neu@x", "name": "Neuling"},
    {"userId": "h6", "email": "aaron@x", "name": "Aaron"}, {"userId": "e3", "email": "julian@x", "name": ""},
    {"userId": "AKTIV", "email": "finn@x", "name": "Finn"},
]

js = ("""
const _ls = {}
const localStorage = { getItem: k => (k in _ls ? _ls[k] : null), setItem: (k, v) => { _ls[k] = String(v) }, removeItem: k => { delete _ls[k] } }
const window = {}
const escapeHtml = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
const ADMIN_KRONE_IDS = new Set(), ADMIN_KRONE_SVG = ''
const PROF_LS = 'prophos_profiles', PROF_ACTIVE = 'prophos_active_profile'
function profList(){ try{ return JSON.parse(localStorage.getItem(PROF_LS) || '[]') }catch(_){ return [] } }
function profActiveId(){ return localStorage.getItem(PROF_ACTIVE) || null }
function profSwitchTo(){} function profRemove(){}
const box = { innerHTML: '', querySelectorAll: () => [] }
const document = { getElementById: id => id === 'ud-profiles' ? box : null }
"""
      + block("  const PROF_GRUPPEN_LS = ", "  const PROF_SYS_KEYS")
      + block("  function profGruppenLesen(", "  document.getElementById('ud-add-account')")
      + """
const P = %s, HT = %s, EM = %s
localStorage.setItem(PROF_LS, JSON.stringify(P)); localStorage.setItem(PROF_ACTIVE, 'AKTIV')
const kurz = a => a.map(x => [x.titel, x.liste.map(p => p.userId)])
const others = P.filter(p => p.userId !== 'AKTIV')
const out = {}
out.ohneDaten = kurz(profMenuAbschnitte(others, profGruppenLesen()))
renderProfileMenu(); out.htmlOhne = box.innerHTML
profGruppenMerken({ gruppen: [EM, HT], ohne_unternehmen: [{ id: 'n1', name: 'Neuling' }] })
out.gemerkt = JSON.parse(localStorage.getItem(PROF_GRUPPEN_LS))
out.mit = kurz(profMenuAbschnitte(others, profGruppenLesen()))
out.htmlMit = box.innerHTML
// eingeschränkte Sicht (sicht_ids) überschreibt nie die gemerkten Gruppen
profGruppenMerken({ sicht_ids: ['e1'], gruppen: [EM] }); out.nachEingeschraenkt = JSON.parse(localStorage.getItem(PROF_GRUPPEN_LS)).gruppen.length
// HT liefert ids → nur diese sind HT, der Rest unten
out.htIds = kurz(profMenuAbschnitte(others, { gruppen: [{ ...HT, ids: ['h1', 'h2'] }, EM], ohne: [] }))
// zweite Gruppe „Zeta“ + „Alpha“: nach Name hinter HT
out.mehr = kurz(profMenuAbschnitte(others, { gruppen: [{ name: 'Zeta', ht: false, ids: ['h4'] }, HT, { name: 'Alpha', ht: false, ids: ['h6'] }], ohne: [] })).map(x => x[0])
// kaputter Speicher → wie ohne Daten
localStorage.setItem(PROF_GRUPPEN_LS, '{kaputt'); out.kaputt = profGruppenLesen()
localStorage.setItem(PROF_GRUPPEN_LS, JSON.stringify({ gruppen: [] })); out.leer = profGruppenLesen()
out.keine = profMenuAbschnitte([], { gruppen: [HT, EM], ohne: [] }).length
print(JSON.stringify(out))
""" % (json.dumps(PROFILE), json.dumps(HT), json.dumps(EM)))

with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run([JSC, d.name], capture_output=True, text=True, timeout=60)
os.unlink(d.name)
check(r.returncode == 0, f"jsc läuft ({(r.stderr or r.stdout)[:300]})")
e = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}

check(e.get("ohneDaten") == [["", ["h6", "e2", "e1", "h4", "h5", "h2", "e3", "h1", "n1", "h3"]]],
      f"ohne Gruppen-Daten: eine Liste alphabetisch (Name, sonst Mail), ohne Überschrift: {e.get('ohneDaten')}")
check("ud-sec" not in (e.get("htmlOhne") or "x") and (e.get("htmlOhne") or "").count("data-prof-switch=") == 10,
      "ohne Daten: keine Abschnitts-Überschrift, alle 10 anderen IDs da, aktive ID nicht")
check(e.get("mit") == [["Hermann Technologies", ["h6", "h4", "h5", "h2", "h1", "h3"]], ["Emin", ["e2", "e1", "e3"]], ["Ohne Gruppe", ["n1"]]],
      f"mit Gruppen: HT oben alphabetisch, dann Emin alphabetisch, ohne Unternehmen unten: {e.get('mit')}")
g = e.get("gemerkt") or {}
check([x.get("name") for x in g.get("gruppen", [])] == ["Emin", "Hermann Technologies"] and g.get("ohne") == ["n1"]
      and all(set(x) == {"name", "ht", "ids", "ausser"} for x in g.get("gruppen", [])),
      "gemerkt nur Name/ht/ids/ausser + ohne-IDs (kein Geld, keine Mail)")
h = e.get("htmlMit") or ""
check(h.count('<div class="ud-sec">') == 3 and h.index("Hermann Technologies") < h.index(">Emin</div>") < h.index("Ohne Gruppe"),
      "Menü zeichnet drei graue Überschriften in der Reihenfolge HT · Emin · Ohne Gruppe (nach dem Merken sofort neu gezeichnet)")
check(h.count("data-prof-switch=") == 10 and h.count("data-prof-remove=") == 10 and 'title="Aus der Liste entfernen"' in h,
      "Knöpfe unverändert: Klick (data-prof-switch) und × (data-prof-remove) je ID")
check(e.get("nachEingeschraenkt") == 2, "eingeschränkte Sicht (sicht_ids) überschreibt die gemerkten Gruppen nicht")
check(e.get("htIds") == [["Hermann Technologies", ["h2", "h1"]], ["Emin", ["e2", "e1", "e3"]], ["Ohne Gruppe", ["h6", "h4", "h5", "n1", "h3"]]],
      f"HT mit ids-Liste: nur diese sind HT, unbekannte unten: {e.get('htIds')}")
check(e.get("mehr") == ["Hermann Technologies", "Alpha", "Zeta", "Ohne Gruppe"], f"weitere Gruppen nach Name hinter HT: {e.get('mehr')}")
check(e.get("kaputt") is None and e.get("leer") is None and e.get("keine") == 0, "kaputter/leerer Speicher → alphabetisch wie ohne Daten; keine IDs → nichts")

# statisch: Quelle + Verdrahtung + Stil
check("const PROF_SYS_KEYS = [PROF_LS, PROF_ACTIVE, 'prophos_kasse_geraet', PROF_WECHSEL_LS, PROF_GRUPPEN_LS]" in HTML,
      "Gruppen-Merker gehört dem Browser (übersteht den ID-Wechsel, nie in einem Bucket)")
check("try{ profGruppenMerken(d) }catch(_){}" in block("    function admAnwenden(", "      window._admLadeZeit = at"),
      "Quelle: /admin/overview (admAnwenden → d.gruppen / d.ohne_unternehmen), nichts hart codiert")
check("#dashboard-view .ud-sec{" in HTML, "Stil .ud-sec im Menü (klein, grau)")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
