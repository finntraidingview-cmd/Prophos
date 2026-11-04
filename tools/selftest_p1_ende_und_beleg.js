// Selbsttest P1 (Finn 05.11.2026 ~05:25 Dubai: „manche Trades laden einfach nicht den P&L") — im Browser auf prophos.html (Konsole oder javascript_tool):
//  1. window._atEndeWeg: ein lokal erkanntes Ende eines offenen Plans geht IMMER nach „Überprüfen", auch wenn der Ende-Merker pendingFinish schon stand
//     (Mike FP …8534 c4db1e61, Marco FN …3615 114a10de am 04.11.: Tagesreset → Überprüfen → zurück zu Geplant, Merker blieb, Plan blieb „open").
//  2. window._sfVorOrderBeleg: „nichts gesendet" zählt auch, wenn davor eine eckige Klammer im Fehlertext steht (Marco pc-t8wg97 ohne DNS:
//     b98697dc, 2e876ab9, 9fe28549, b2aeaca4 wurden unklar statt nachgeholt); die Bot-Spur „ [0.0s·…" bleibt draußen.
//  3. window._sf.still (sfStillUrteil) mit genau diesen Plänen: unklar false → sfTick holt nach, keine Gegenrichtungs-Sperre (DB prüft start_fehler.unklar = 'true').
(() => {
  const f = [], ok = (c, n) => f.push((c ? '✓ ' : '✗ ') + n)
  const W = window._atEndeWeg, B = window._sfVorOrderBeleg
  ok(typeof W === 'function' && typeof B === 'function', 'Test-Haken da')
  ok(W({ id: 'c4db1e61', status: 'open' }, false, true) === 'nur_review', 'c4db1e61: Merker vom Vortag, Ende lokal erkannt → trotzdem nach Überprüfen')
  ok(W({ id: '114a10de', status: 'open' }, false, true) === 'nur_review', '114a10de: dito')
  ok(W({ id: 'x', status: 'open' }, false, false) === 'normal', 'ohne Merker → normaler Weg (Merker, Popup, Überprüfen)')
  ok(W({ id: 'x', status: 'review' }, true, true) === 'nichts', 'vom Server gemeldet, Merker da → nichts (kein zweites Popup)')
  ok(W({ id: 'x', status: 'review' }, true, false) === 'normal', 'vom Server gemeldet, neu → Popup wie bisher, ohne Schreiben')
  ok(W({ id: 'x', status: 'review' }, false, true) === 'nichts', 'Plan schon in Überprüfen → nichts')
  const marco = 'Riegel-Prüfung (Gegenrichtung) nicht erreichbar: <urlopen error [Errno 11001] getaddrinfo failed> — nichts gesendet, der Start wird später erneut versucht.'
  ok(B(marco), 'Marco pc-t8wg97: „[Errno 11001]" vor „nichts gesendet" → Beleg')
  ok(B('F9-Dialog nicht gefunden — Abbruch, nichts gesendet. [0.0s·Hand…]'), 'Spur hinten bleibt draußen, Kopf zählt')
  ok(!B("ok [0.0s·Hand → Volumen-Feld leert nicht ('0.00') — nichts platziert]"), 'Spur-Text zählt weiter nicht (nur Kopf)')
  ok(!B('KEINE Bestaetigung binnen 12 s — Position nicht am Konto, Dialog geschlossen. Spur: [… Volumen-Feld leert nicht — nichts platziert …]'), '„Spur:" schneidet weiter ab')
  ok(!B('Order-Bot Timeout (300s) — [Errno 110] im Terminal pruefen'), 'Zeitlimit bleibt nie Beleg, auch mit Klammer')
  ok(!B('Verbindung zum Panel brach nach 17 s mitten in der Order ab [Errno 104] — nichts gesendet?'), 'Verbindungsabriss bleibt nie Beleg')
  const S = window._sf && window._sf.still
  if(typeof S === 'function'){
    const claim = '2026-11-04T04:25:00.985Z', jetzt = Date.parse('2026-11-04T04:29:59.205Z')
    const p = { id: 'b2aeaca4', route: 'mt5', status: 'planned', startUmGestartetAt: claim, startedAt: null, orbitGesendetAt: null,
      mt5Baseline: { puls_spur: { at: '2026-11-04T04:25:53.684Z', ok: false, msg: marco } } }
    const u = S(p, jetzt, false, null)
    ok(u && u.unklar === false && /nichts gesendet/.test(u.msg), `b2aeaca4 (Marco …6725): unklar false → nachholen (${u && u.msg && u.msg.slice(0, 60)})`)
    const u2 = S(Object.assign({}, p, { mt5Baseline: { puls_spur: { at: '2026-11-04T04:25:53Z', ok: false, msg: 'Order-Bot Timeout (300s)' } } }), jetzt, false, null)
    ok(u2 && u2.unklar === true, 'Gegenprobe: Zeitlimit bleibt unklar')
  } else ok(false, 'window._sf.still fehlt')
  return f
})()
