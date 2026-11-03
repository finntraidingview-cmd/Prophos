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
const konstBig = SRC.match(/\n  const BTH_WECHSEL_PKT = \d+, BTH_HALTE_MS = [\d *]+/)
if(!konstBig) throw new Error('BTH_WECHSEL_PKT/BTH_HALTE_MS nicht gefunden')

// Umgebung: _hwPulsWegAt (Heim-Wache-Anstoß), Kurs fest 20950 (NQ und MNQ), Symbol-Wurzel am Präfix
const bau = new Function(konst[0] + konstBig[0] + '\nlet _hwPulsWegAt = 0\nconst console = { info(){} }\n'
  + 'const tvSymbolWurzel = s => (/^MNQ/.test(String(s)) ? "MNQ" : "NQ")\nconst hedgeKursDerWurzel = () => 20950\n'
  + fn('wdHeimAbstand') + '\n' + fn('heimNaechster')
  + '\nreturn { heimNaechster, wdHeimAbstand, wegAt: () => _hwPulsWegAt, PKT: BTH_WECHSEL_PKT, HALTE: BTH_HALTE_MS }')
const { heimNaechster, wdHeimAbstand, wegAt, PKT, HALTE } = bau()

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

// ── BIG TRADES IN PUNKTEN (S2-Stopp 03.11.2026) ──
// 12) wdHeimAbstand: $ wie bisher, mit punkte = true die NQ-Punkte (3 NQ: 50 Pkt = 3.000 $)
const P3 = { id: 'p3', masterContracts: 3, masterSymbol: 'NQ1!', mt5Baseline: { hedge: { tp_level_nq: 21000, sl_level_nq: 20800 } } }
ok(wdHeimAbstand(P3) === 3000, '12: $-Rest 3 NQ × 50 Pkt × 20 = 3.000 $')
ok(wdHeimAbstand(P3, true) === 50, '12: Rest in Punkten = 50')
ok(PKT === 15 && HALTE === 180000, '12: Vorgabe 15 Pkt / 3 min')
const big = (rest, extra) => o(rest, Object.assign({ wechsel: PKT, halten: HALTE, einheit: 'Pkt' }, extra || {}))

// 13) 3 NQ, Reste kreuzen sich alle 60 s um ±5 Pkt (= ±300 $, früher Wechsel jede Minute) → nie ein Wechsel, 20 min lang
st = { id: 'a', at: uhr }
let wechsel = 0
for(let i = 1; i <= 20; i++){
  uhr += 60000
  const r = i % 2 ? { a: 40, b: 35 } : { a: 35, b: 40 }
  if(heimNaechster([A, B], juengster, st, big(r)) !== A) wechsel++
}
ok(wechsel === 0 && st.id === 'a', '13: kreuzende Reste (±5 Pkt) → kein Pendeln (' + wechsel + ' Wechsel)')

// 14) deutlicher Abstand (B 20 Pkt näher): vor Ablauf der Haltezeit A, danach B
st = { id: 'a', at: uhr - 60000 }
ok(heimNaechster([A, B], juengster, st, big({ a: 60, b: 40 })) === A, '14: 20 Pkt näher, Wahl 1 min alt → A bleibt')
st = { id: 'a', at: uhr - 181000 }
ok(heimNaechster([A, B], juengster, st, big({ a: 60, b: 40 })) === B, '14: 20 Pkt näher, Wahl > 3 min alt → B')
// 14b) 14 Pkt näher, Haltezeit vorbei → A bleibt (unter BTH_WECHSEL_PKT)
st = { id: 'a', at: uhr - 600000 }
ok(heimNaechster([A, B], juengster, st, big({ a: 54, b: 40 })) === A, '14b: nur 14 Pkt näher → A bleibt')

// 15) nach der Order von B (Merker zurückgesetzt wie bigTradeHeimNachOrder) → sofort der nähere, keine Haltezeit
st = { id: '', at: 0 }
ok(heimNaechster([A, B], juengster, st, big({ a: 30, b: 33 })) === A && st.at === uhr, '15: nach Order sofort Prio-Wahl ohne Haltezeit')
ok(SRC.includes("_bthBigWahl[f] = { id: '', at: 0 }"), '15: bigTradeHeimNachOrder setzt den Big-Trade-Merker zurück')
ok(SRC.includes('abstand: p => wdHeimAbstand(p, true), wechsel: BTH_WECHSEL_PKT, halten: BTH_HALTE_MS'), '16: bigTradePlan rechnet Big Trades in Punkten mit BTH_WECHSEL_PKT/BTH_HALTE_MS')

if(fehler.length){ aus('FEHLER selftest_heim_wahl (' + fehler.length + ' von ' + n + '):\n  ' + fehler.join('\n  ')); if(istNode) process.exit(1); else throw new Error('rot') }
aus('OK selftest_heim_wahl: ' + n + ' Prüfungen — näherer gewinnt, Hysterese WD 30 $ / 60 s, Big Trades 15 Pkt / 3 min ohne Pendeln, ohne Kurs die bisherige Wahl bzw. der jüngste, geschlossener zählt nicht, Wache nur TradingView')
