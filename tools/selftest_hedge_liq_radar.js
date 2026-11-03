/* Selbsttest: Liq-Level am Fusion-Hedge aus dem Radar für Big Trades ohne Master-SL (prophos.html hedgeLiqAusRadarWert), 03.11.2026, Slave 3 —
 * R1 Marc Tradeify 150k Funded (SELL 3 NQ @ 28.389,25, kein master_sl): am Hedge weder sl_level_nq noch Fusion-TP auf der Liq-Seite.
 * Kennungen erfunden. Rein rechnend, ohne Browser, mit JavaScriptCore (kein Node auf dem Mac):
 *   /System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc tools/selftest_hedge_liq_radar.js -- prophos.html */
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
const W = new Function(fn('hedgeLiqAusRadarWert') + '\nreturn hedgeLiqAusRadarWert')()
const fehler = []; let n = 0
const ok = (b, t) => { n++; if(!b) fehler.push(t) }

const plan = { id: 'p1', richtung: 'sell', masterSl: null, masterName: 'Tradeify 150k …0001' }
const hedge = { status: 'offen', einstieg_nq: 28389.25, sl_level_nq: null }
const zeile = { id: 'p1', liq_regel_level_nq: 28558.71, liq_regel_balance: 145500, liq_regel_text: 'fest 4.500 $ ab Tagesstart 150.000,00 $ (End-of-Day)', einstieg_nq: 28389.25 }

// 1) Marc-Fall: Level 28.558,71, 169,46 Pkt, Liquidation
const r1 = W(plan, hedge, zeile)
ok(r1 && r1.sl_level_nq === 28558.71 && r1.sl_punkte === 169.46 && r1.sl_art === 'liquidation' && r1.liq_balance === 145500, '1: SELL ohne SL → Liq aus dem Radar ' + JSON.stringify(r1))
// 2) BUY: Liq unter dem Einstieg
const r2 = W(Object.assign({}, plan, { richtung: 'buy' }), hedge, Object.assign({}, zeile, { liq_regel_level_nq: 28314.25 }))
ok(r2 && r2.sl_punkte === 75, '2: BUY 75 Pkt darunter → ' + JSON.stringify(r2))
// 3) falsche Seite → nichts
ok(W(Object.assign({}, plan, { richtung: 'buy' }), hedge, zeile) === null, '3: BUY mit Level über dem Einstieg → null')
// 4) Master-SL da → nichts (SL-Weg wie bisher)
ok(W(Object.assign({}, plan, { masterSl: 4500 }), hedge, zeile) === null, '4: Master-SL vorhanden → null')
// 5) Hedge hat schon ein SL-/Liq-Level → nichts
ok(W(plan, Object.assign({}, hedge, { sl_level_nq: 28500 }), zeile) === null, '5: sl_level_nq schon da → null')
// 6) Hedge nicht offen → nichts
ok(W(plan, Object.assign({}, hedge, { status: 'geschlossen' }), zeile) === null, '6: Hedge zu → null')
// 7) unplausibel: < 10 Pkt bzw. > 2.000 Pkt, kein Level
ok(W(plan, hedge, Object.assign({}, zeile, { liq_regel_level_nq: 28395 })) === null, '7: 5,75 Pkt → null')
ok(W(plan, hedge, Object.assign({}, zeile, { liq_regel_level_nq: 30500 })) === null, '7: 2.110 Pkt → null')
ok(W(plan, hedge, Object.assign({}, zeile, { liq_regel_level_nq: null })) === null, '7: ohne Level → null')
// 8) Einstieg nur in der Radar-Zeile → reicht
const r8 = W(plan, Object.assign({}, hedge, { einstieg_nq: null }), zeile)
ok(r8 && r8.sl_punkte === 169.46, '8: Einstieg aus der Radar-Zeile → ' + JSON.stringify(r8))
// 9) Verdrahtung: Wächter ruft den Nachtrag nur ohne SL-Level, WD-Weg ausgenommen
ok(SRC.includes('if(!(slL > 0)) hedgeLiqAusRadar(p, h).catch(() => {})'), '9: Wächter stößt den Nachtrag ohne SL-Level an')
ok(SRC.includes("if(typeof hedgeIstWd === 'function' && hedgeIstWd(p)) return"), '9: WD/Apex/finaler Tradeify bleiben auf ihrem Weg')

if(fehler.length){ aus('FEHLER selftest_hedge_liq_radar (' + fehler.length + ' von ' + n + '):\n  ' + fehler.join('\n  ')); if(istNode) process.exit(1); else throw new Error('rot') }
aus('OK selftest_hedge_liq_radar: ' + n + ' Prüfungen — Liq aus dem Radar nur ohne Master-SL/Level, richtige Seite, 10–2.000 Pkt')
