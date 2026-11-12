#!/usr/bin/env python3
"""Selbsttest IW1 (12.11.2026, Finn ~18:35 Dubai: „Warum dauert ID-Wechsel bei Prophos gerade wieder so ewig?", Master-OK a + b + c).
Aufruf:  python3 tools/selftest_iw1_id_wechsel.py
Lädt die ECHTEN Funktionen aus prophos.html per osascript/JXA und prüft:
  (a) profPufferAufraeumen räumt nur Puffer-Schlüssel (prophos_cache_*, tpl_cache, wd_cache) aus ALLEN Buckets — Einstellungen, Archiv-Merker,
      tw_hand, Filter/Chips, Sitzungen und die losen Puffer der aktiven ID bleiben; läuft nicht, solange ein Wechsel läuft; zweiter Lauf = 0.
  (b) cachePlaeneAuswahl: offene/geplante/Überprüfen-Pläne und Pläne mit nicht geschlossenem Hedge immer; abgeschlossene nur aus den letzten
      2 Tagen, neueste zuerst, bis 150 K Zeichen; Reihenfolge wie geladen; Größe bei realistischen Plänen (4,5 K Zeichen) ≤ 300 KB.
  (c) Messung: Marken in profSwitchTo/Kern in der richtigen Reihenfolge, Ausgabe nur console.debug, Haken im Boot (Text).
Ohne Netz, Platzhalter-IDs."""
import json
import os
import shutil
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = open(os.path.join(os.path.dirname(HIER), "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def jxa(script):
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", script], capture_output=True, text=True)
    try:
        return json.loads(r.stdout.strip()), ""
    except ValueError:
        return None, (r.stderr or r.stdout).strip()[:400]


def stueck(anfang, ende):
    a = HTML.find(anfang)
    b = HTML.find(ende, a)
    check(a > 0 and b > a, f"Block gefunden: {anfang.strip()[:50]}")
    return HTML[a:b + len(ende)]


CP = stueck("  const CACHE_PLAN_TAGE = 2, CACHE_PLAN_MAX_Z = 150 * 1024", "    return liste.filter(p => nimm.has(p))\n  }")
PROF = stueck("  const PROF_LS       = 'prophos_profiles'", "    } finally { _profBulkWrite = false }\n  }")
AUF = stueck("  function profPufferAufraeumen(){", "    return _profCachesAusBuckets([])\n  }")

VORSPANN = r"""
function FakeLS(){ this.m = new Map() }
FakeLS.prototype = { get length(){ return this.m.size }, key(i){ const ks = [...this.m.keys()]; return i < ks.length ? ks[i] : null },
  getItem(k){ return this.m.has(k) ? this.m.get(k) : null }, removeItem(k){ this.m.delete(k) }, setItem(k, v){ this.m.set(k, String(v)) } }
var localStorage = new FakeLS(), sessionStorage = { m: {}, setItem(k, v){ this.m[k] = String(v) }, getItem(k){ return k in this.m ? this.m[k] : null }, removeItem(k){ delete this.m[k] } }
var console = { warn(){}, log(){}, debug(){} }, atToast = null
function Storage(){}
var window = { addEventListener(){}, get localStorage(){ return localStorage } }
var setInterval = () => 0, clearInterval = () => {}, document = { createElement(){ return { dataset: {} } }, body: { appendChild(){} } }, location = { reload(){} }
var _profWechselLaeuft = false
const X = n => 'x'.repeat(n)
"""

if not shutil.which("osascript"):
    print("… osascript fehlt — nur Textprüfungen")
else:
    # (a) Aufräumen
    v, err = jxa(VORSPANN + PROF + AUF + r"""
const echt = { prophos_account_archive: X(3000), prophos_tw_hand: '{"x":1}', prophos_tp_filter: 'heute', prophos_chips_firma: '["Apex"]', 'prophos_kasse_frei:a': '1' }
const voll = Object.assign({}, echt, { prophos_cache_plans: X(90000), prophos_cache_accounts: X(40000), prophos_tpl_cache: X(30000), prophos_wd_cache: X(9000) })
localStorage.setItem('prophos_bucket_a', JSON.stringify(voll)); localStorage.setItem('prophos_bucket_b', JSON.stringify(voll)); localStorage.setItem('prophos_bucket_c', JSON.stringify(echt))
localStorage.setItem('prophos_psession_a', '{"refresh_token":"r"}'); localStorage.setItem('sb-gxh-auth-token', '{"t":1}')
localStorage.setItem('prophos_cache_plans', X(5000)); localStorage.setItem('prophos_tpl_cache', X(100)); localStorage.setItem('prophos_account_archive', X(10))
const c0 = localStorage.getItem('prophos_bucket_c')
_profWechselLaeuft = true; const gesperrt = profPufferAufraeumen(); const nachSperre = Object.keys(JSON.parse(localStorage.getItem('prophos_bucket_a'))).length
_profWechselLaeuft = false
const n1 = profPufferAufraeumen(), n2 = profPufferAufraeumen()
const K = k => Object.keys(JSON.parse(localStorage.getItem('prophos_bucket_' + k))).sort()
const A = JSON.parse(localStorage.getItem('prophos_bucket_a'))
JSON.stringify({ gesperrt, nachSperre, n1, n2, a: K('a'), b: K('b'), cGleich: localStorage.getItem('prophos_bucket_c') === c0,
  werteGleich: Object.keys(echt).every(k => A[k] === echt[k]),
  lose: ['prophos_cache_plans', 'prophos_tpl_cache', 'prophos_account_archive', 'prophos_psession_a', 'sb-gxh-auth-token'].map(k => localStorage.getItem(k) != null) })""")
    ECHT = sorted(["prophos_account_archive", "prophos_tw_hand", "prophos_tp_filter", "prophos_chips_firma", "prophos_kasse_frei:a"])
    check(bool(v) and v["gesperrt"] == -1 and v["nachSperre"] == 9, f"(a) läuft ein Wechsel, räumt es nichts ({v and v['gesperrt']} / {v and v['nachSperre']} Keys) {err}")
    check(bool(v) and v["n1"] == 8 and v["a"] == ECHT and v["b"] == ECHT, f"(a) 8 Puffer aus 2 Buckets geräumt, nur echte Keys bleiben ({v and v['a']})")
    check(bool(v) and v["werteGleich"] and v["cGleich"], "(a) Werte der echten Keys unverändert, Bucket ohne Puffer gar nicht neu geschrieben")
    check(bool(v) and v["n2"] == 0, "(a) zweiter Lauf: nichts mehr zu tun")
    check(bool(v) and v["lose"] == [True] * 5, "(a) lose Keys der aktiven ID (auch ihre Puffer), psession_*, sb-* bleiben unberührt")

    # IW1b: beginnt ein anderer Tab mittendrin einen Wechsel, schreibt das Räumen keinen Bucket mehr (je Bucket neu geprüft)
    v, err = jxa(VORSPANN + PROF + AUF + r"""
const voll = JSON.stringify({ prophos_tw_hand: '{}', prophos_cache_plans: X(5000) })
for(const k of ['a', 'b', 'c']) localStorage.setItem('prophos_bucket_' + k, voll)
const merker = () => JSON.stringify({ tab: 'anderer-tab', von: 'x', nach: 'y', at: Date.now(), bis: Date.now() + 10000 })
// Fall 1: Merker schon da → nichts geräumt
localStorage.setItem(PROF_WECHSEL_LS, merker())
const n0 = _profCachesAusBuckets([])
const unber0 = ['a', 'b', 'c'].every(k => localStorage.getItem('prophos_bucket_' + k) === voll)
localStorage.removeItem(PROF_WECHSEL_LS)
// Fall 2: Merker erscheint, nachdem der erste Bucket gelesen wurde (anderer Tab startet mittendrin)
const roh = localStorage.getItem.bind(localStorage); let gelesen = 0
localStorage.getItem = k => { const v = roh(k); if(String(k).startsWith('prophos_bucket_') && ++gelesen === 1) localStorage.m.set(PROF_WECHSEL_LS, merker()); return v }
const n1 = _profCachesAusBuckets([])
localStorage.getItem = roh
const geraeumt = ['a', 'b', 'c'].filter(k => !localStorage.getItem('prophos_bucket_' + k).includes('prophos_cache_plans'))
// Fall 3: eigener Wechsel-Merker (dieser Tab) bremst nicht
localStorage.m.set(PROF_WECHSEL_LS, JSON.stringify({ tab: PROF_TAB_ID, bis: Date.now() + 10000 }))
const n2 = _profCachesAusBuckets([])
JSON.stringify({ n0, unber0, n1, geraeumt, n2 })""")
    check(bool(v) and v["n0"] == 0 and v["unber0"], f"IW1b: Wechsel in anderem Tab läuft → nichts geräumt, Buckets unberührt ({v or err})")
    check(bool(v) and v["n1"] == 1 and len(v["geraeumt"]) == 1, f"IW1b: anderer Tab beginnt mittendrin → nach dem ersten Bucket Schluss ({v and v['geraeumt']})")
    check(bool(v) and v["n2"] == 2, f"IW1b: eigener Wechsel-Merker bremst das Werfen nicht (Rückfall beim eigenen Wegsichern) ({v and v['n2']})")

    # (b) Plan-Auswahl
    v, err = jxa("const X = n => 'x'.repeat(n)\n" + CP.replace("window._cachePlaeneAuswahl", "var _x") + r"""
const T = Date.parse('2026-11-12T14:00:00Z'), H = 3600000
const bl = n => ({ tv: { x: X(n) } })
const plan = (id, status, stundenAlt, extra) => Object.assign({ id, status, createdAt: new Date(T - stundenAlt * H - 600000).toISOString(),
  endedAt: status === 'completed' ? new Date(T - stundenAlt * H).toISOString() : null, mt5Baseline: bl(4300) }, extra || {})
// geladen wie loadTradePlansFromSupabase: created_at absteigend
const liste = [plan('p1', 'planned', 0), plan('o1', 'open', 1), plan('r1', 'review', 3), plan('c1', 'completed', 4), plan('c2', 'completed', 20),
  plan('c3', 'completed', 47), plan('c4', 'completed', 60), plan('h1', 'completed', 200, { mt5Baseline: { hedge: { status: 'unklar' } } }),
  plan('h2', 'completed', 210, { mt5Baseline: { hedge: { status: 'geschlossen' } } }), plan('alt', 'completed', 400),
  plan('u1', 'completed', 220, { mt5Baseline: { hedge: { status: 'uebersprungen' } } }), plan('f1', 'completed', 230, { mt5Baseline: { hedge: { status: 'fehler' } } })]
const ids = a => a.map(p => p.id)
const r1 = ids(cachePlaeneAuswahl(liste, T))
const r2 = ids(cachePlaeneAuswahl(liste, T, 20000))   // eng: Pflicht (p1 o1 r1 h1) + nur so viele abgeschlossene, wie passen (neueste zuerst)
const r3 = ids(cachePlaeneAuswahl(liste, T, 100))     // Pflicht nie weg, auch über dem Deckel
// realistisch: 400 abgeschlossene Pläne über 10 Tage à ~4.500 Zeichen + 8 offene
const gross = []; for(let i = 0; i < 8; i++) gross.push(plan('g' + i, 'planned', 0))
for(let i = 0; i < 400; i++) gross.push(plan('z' + i, 'completed', i * 0.6))
const s = JSON.stringify(cachePlaeneAuswahl(gross, T)), alles = JSON.stringify(gross)
JSON.stringify({ r1, r2, r3, n: cachePlaeneAuswahl(gross, T).length, z: s.length, zAlles: alles.length, leer: cachePlaeneAuswahl(null, T).length })""")
    check(bool(v) and v["r1"] == ["p1", "o1", "r1", "c1", "c2", "c3", "h1"], f"(b) offen/geplant/review + Hedge im Zwischenzustand (unklar ja; geschlossen/uebersprungen/fehler alt nein) + abgeschlossen ≤ 2 Tage, Reihenfolge wie geladen ({v and v['r1']}) {err}")
    check(bool(v) and v["r2"][:3] == ["p1", "o1", "r1"] and "h1" in v["r2"] and "c3" not in v["r2"] and "c1" in v["r2"], f"(b) enger Deckel: neueste abgeschlossene zuerst, ältere fallen weg ({v and v['r2']})")
    check(bool(v) and v["r3"] == ["p1", "o1", "r1", "h1"], f"(b) Pflicht-Pläne nie weggelassen, auch über dem Deckel ({v and v['r3']})")
    check(bool(v) and v["z"] <= 150 * 1024 and v["n"] >= 30, f"(b) realistisch 408 Pläne / {v and round(v['zAlles'] / 1024)} K Zeichen → {v and v['n']} Pläne / {v and round(v['z'] / 1024)} K Zeichen (≤ 150 K = 300 KB UTF-16)")
    check(bool(v) and v["leer"] == 0, "(b) ohne Liste → leer")

# Text: Einbau
check("cacheWrite(CACHE_PLAN_LS, cachePlaeneAuswahl(tradePlans))" in HTML and HTML.count("cacheWrite(CACHE_PLAN_LS") == 1, "(b) einziger Schreiber des Plan-Puffers nutzt die Auswahl")
check("if(s.length > 900 * 1024){ localStorage.removeItem(key); return }" in HTML, "(b) zu großer Puffer nimmt auch den alten weg")
k = HTML[HTML.index("  async function profSwitchToKern(userId){"):HTML.index("  // \"Account hinzufügen\"")]
reihe = ["iwMarke('snapshot')", "iwMarke('restore')", "iwMarke('session')", "iwMarke('archiv')", "iwVorNeuladen(curId, userId)", "location.reload()"]
pos = [k.find(x) for x in reihe]
check(all(p > 0 for p in pos) and pos == sorted(pos), f"(c) Marken im Wechsel in Reihenfolge snapshot → restore → session → archiv → reload ({pos})")
check("_iw.t0 = performance.now(); _iw.ph = {}; iwMarke('start')" in HTML, "(c) Start-Marke beim Klick (profSwitchTo)")
m = HTML[HTML.index("  const IW_MESS_SS = 'prophos_iw_messung'"):HTML.index("  window._iwNachLaden = iwNachLaden")]
check("console.debug('[IW]" in m and "console.log" not in m and "console.info" not in m and "console.warn" not in m, "(c) Ausgabe nur console.debug")
check("window._iwNachLaden?.('dashboard')" in HTML and HTML.count("window._iwNachBild?.()") == 2 and "iwNachLaden('gerendert')" in HTML, "(c) Boot setzt dashboard + gerendert")
check("setTimeout(() => { try{ const n = profPufferAufraeumen()" in HTML, "(a) Aufräumen läuft verzögert je Seitenstart")
check(HTML.count("if(window._profPufferGesperrt?.()) return") == 3 and "window._profPufferGesperrt = () => { try{ return !!_profWechselLaeuft }" in HTML,
      "(a) während des Wechsels schreibt keiner der drei Puffer-Schreiber (cacheWrite, tplCacheSchreiben, wdCacheSchreiben)")
w = HTML[HTML.index("  async function wdTick(){"):HTML.index("  async function wdTick(){") + 3000]
check("if(window._tpFrischUid !== uid){" in w and w.index("if(window._tpFrischUid !== uid){") < w.index("_wd.laeuft = true") and "window._tpFrischUid = currentUserId" in HTML,
      "(b) WD-Farmer beginnt erst nach frischer Plan-Ladung dieser ID (nicht auf dem gedeckelten Puffer)")
check("m.abs0 > 60000" in HTML, "(c) liegengebliebene Messung > 60 s wird verworfen")
ab = HTML[HTML.index("  async function abgleichTick(){"):HTML.index("  async function abgleichTick(){") + 1200]
check("if(window._tpFrischUid !== currentUserId) return" in ab and ab.index("if(window._tpFrischUid !== currentUserId) return") < ab.index("_ab.laeuft = true"),
      "IW1b: abgleichTick erst nach frischer Plan-Ladung dieser ID (vor _ab.laeuft, wie wdTick)")
cb = HTML[HTML.index("  function _profCachesAusBuckets(schonen){"):HTML.index("    return n\n  }", HTML.index("  function _profCachesAusBuckets(schonen){"))]
check("for(const k of ks){" in cb and cb.index("if(profFremdWechsel()) break") > cb.index("for(const k of ks){"), "IW1b: _profCachesAusBuckets prüft den fremden Wechsel je Bucket")

print()
if FEHLER:
    print(f"FEHLER ({len(FEHLER)}):")
    for f in FEHLER:
        print("  - " + f)
    sys.exit(1)
print("ALLES GRÜN")
