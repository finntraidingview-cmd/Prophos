/* Selbsttest: Heimkonto bei mehreren Big Trades / WDs (prophos.html heimNaechster), 03.11.2026, Slave 3 — Finn ~17:35 Dubai: „Puls immer in
 * den Account, wo wir näher am Take Profit/Stop Loss sind". Prüft: der nähere gewinnt, Hysterese 30 $ / 60 s, ohne Kurs der jüngste, ein
 * geschlossener bisheriger zählt nicht, Prio-Wechsel stößt die Heim-Wache an. Rein rechnend, ohne Browser. Kein Node auf dem Mac, darum
 * JavaScriptCore (wie .claude/jscheck.sh):
 *   /System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc tools/selftest_heim_wahl.js -- prophos.html
 * (mit Node ebenso: node tools/selftest_heim_wahl.js [prophos.html]) */
const istNode = typeof require === 'function' && typeof process !== 'undefined'
const datei = istNode ? (process.argv[2] || require('path').join(__dirname, '..', 'prophos.html')) : ((typeof arguments !== 'undefined' && arguments[0]) || 'prophos.html')
const SRC = istNode ? require('fs').readFileSync(datei, 'utf8') : read(datei)
const aus = t => (istNode ? console.log(t) : print(t))

function fn(name){
  const a = SRC.indexOf(`\n  function ${name}(`)
  if(a < 0) throw new Error(`Funktion ${name} nicht gefunden`)
  const e = SRC.indexOf('\n  }\n', a + 1)
  return SRC.slice(a + 1, e + 4)
}
const konst = SRC.match(/\n  const BTH_WD_WECHSEL_USD = \d+, BTH_WD_HALTEN_MS = \d+/)
if(!konst) throw new Error('BTH_WD_WECHSEL_USD/BTH_WD_HALTEN_MS nicht gefunden')

// Umgebung: _hwPulsWegAt (Heim-Wache-Anstoß), wdHeimAbstand wird im Test immer über o.abstand ersetzt
const bau = new Function(konst[0] + '\nlet _hwPulsWegAt = 0\nconst wdHeimAbstand = () => null\nconst console = { info(){} }\n' + fn('heimNaechster')
  + '\nreturn { heimNaechster, wegAt: () => _hwPulsWegAt }')
const { heimNaechster, wegAt } = bau()

const fehler = []
let n = 0
const ok = (b, t) => { n++; if(!b) fehler.push(t) }
const juengster = l => l.slice().sort((a, b) => String(b.startedAt || '').localeCompare(String(a.startedAt || '')))[0] || null
const A = { id: 'a', masterName: 'A', startedAt: '2026-11-03T10:00:00Z' }
const B = { id: 'b', masterName: 'B', startedAt: '2026-11-03T11:00:00Z' }   // B ist der jüngere
const mit = rest => p => (p.id in rest ? rest[p.id] : null)
let uhr = 1000000
const o = (rest, extra) => Object.assign({ abstand: mit(rest), jetzt: () => uhr, wort: () => 'Big Trade', wache: true }, extra || {})

// 1) A näher → A (auch wenn B jünger ist); Merker gesetzt, Heim-Wache angestoßen
let st = { id: '', at: 0 }
ok(heimNaechster([A, B], juengster, st, o({ a: 900, b: 3000 })) === A, '1: A näher → A')
ok(st.id === 'a' && st.at === uhr, '1: Merker auf A')
ok(wegAt() === uhr, '1: Prio-Wechsel stößt die Heim-Wache an')

// 2) Hysterese: B nur 20 $ näher → A bleibt
uhr += 120000
ok(heimNaechster([A, B], juengster, st, o({ a: 900, b: 880 })) === A, '2: B nur 20 $ näher → A bleibt')
// 3) B 40 $ näher, aber letzte Wahl < 60 s → A bleibt
st = { id: 'a', at: uhr - 30000 }
ok(heimNaechster([A, B], juengster, st, o({ a: 900, b: 860 })) === A, '3: < 60 s seit der Wahl → A bleibt')
// 4) B 40 $ näher und ≥ 60 s → B
st = { id: 'a', at: uhr - 61000 }
ok(heimNaechster([A, B], juengster, st, o({ a: 900, b: 860 })) === B, '4: B 40 $ näher, 61 s → B')
ok(st.id === 'b' && st.at === uhr, '4: Merker auf B')

// 5) ohne Kurs/Level und ohne bisherige Wahl → der jüngste (B); mit bisheriger, noch offener Wahl → die bleibt (Kurs-Lücke kippt nichts)
st = { id: '', at: 0 }
ok(heimNaechster([A, B], juengster, st, o({})) === B, '5: ohne Kurs, ohne Wahl → der jüngste')
ok(st.id === '', '5: Merker bleibt ohne Kurs unverändert')
st = { id: 'a', at: uhr - 5000 }
ok(heimNaechster([A, B], juengster, st, o({})) === A, '5b: ohne Kurs, A gewählt und offen → A bleibt')
st = { id: 'x', at: uhr - 5000 }
ok(heimNaechster([A, B], juengster, st, o({})) === B, '5c: ohne Kurs, gewählter zu → der jüngste')

// 6) nur einer mit Abstand → der (frischer B ohne Hedge-Level, A bekannt → A)
st = { id: '', at: 0 }
ok(heimNaechster([A, B], juengster, st, o({ a: 2500 })) === A, '6: nur A rechenbar → A')

// 7) bisheriger ohne Abstand (Level weg) → sofort der rechenbare, auch < 60 s
st = { id: 'a', at: uhr - 1000 }
ok(heimNaechster([A, B], juengster, st, o({ b: 4000 })) === B, '7: bisheriger nicht rechenbar → der rechenbare')

// 8) bisheriger geschlossen (nicht mehr in der Liste) → bester, auch < 60 s
const C = { id: 'c', masterName: 'C', startedAt: '2026-11-03T12:00:00Z' }
st = { id: 'a', at: uhr - 1000 }
ok(heimNaechster([B, C], juengster, st, o({ b: 1500, c: 700 })) === C, '8: bisheriger zu → der nähere der übrigen')

// 9) einer / keiner
ok(heimNaechster([A], juengster, { id: '', at: 0 }, o({})) === A, '9: einer → der')
ok(heimNaechster([], juengster, { id: '', at: 0 }, o({})) === null, '9: keiner → null')

// 10) wache: false (TopstepX-Fenster) → Heim-Wache nicht angestoßen
const vorher = wegAt(); uhr += 500000
st = { id: '', at: 0 }
heimNaechster([A, B], juengster, st, o({ a: 100, b: 200 }, { wache: false }))
ok(wegAt() === vorher && st.id === 'a', '10: TopstepX wählt, ohne die TradingView-Wache anzustoßen')

// 11) Gleichstand → der bisherige bleibt (kein Hin und Her)
st = { id: 'b', at: uhr - 120000 }
ok(heimNaechster([A, B], juengster, st, o({ a: 500, b: 500 })) === B, '11: Gleichstand → bisheriger bleibt')

if(fehler.length){ aus('FEHLER selftest_heim_wahl (' + fehler.length + ' von ' + n + '):\n  ' + fehler.join('\n  ')); if(istNode) process.exit(1); else throw new Error('rot') }
aus('OK selftest_heim_wahl: ' + n + ' Prüfungen — näherer gewinnt, Hysterese 30 $ / 60 s, ohne Kurs die bisherige Wahl bzw. der jüngste, geschlossener zählt nicht, Wache nur TradingView')
