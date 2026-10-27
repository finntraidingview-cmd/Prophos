// ==UserScript==
// @name         Prophos TopstepX-Auge
// @namespace    prophos
// @version      0.1.0
// @description  Liest im TopstepX-Tab des Puls-Chrome Konto, offene Positionen und den Flach-Beweis (dieselbe Lesung wie der Puls-Bot: augen_tsx.js) und meldet sie alle 0,25 s an das lokale Panel (127.0.0.1:8770). Prophos schließt damit den Fusion-Hedge eines Topstep-Trades, sobald die Position in TopstepX zu ist. Nur lesen — klickt nie.
// @match        https://topstepx.com/*
// @match        https://*.topstepx.com/*
// @require      https://prophos.pages.dev/mt5-copier/augen_tsx.js?v=tsx-0.6.3
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// @run-at       document-idle
// @updateURL    https://prophos.pages.dev/tv-reader/tsx-auge.user.js
// @downloadURL  https://prophos.pages.dev/tv-reader/tsx-auge.user.js
// ==/UserScript==

/* TOPSTEPX-AUGE (27.10.2026, Finn: „Für das Schließen fehlen saubere Wege. In erster Instanz ein Tampermonkey-Script im TopstepX-Tab, bei
 * dem der Trade mit der gleichen Prio behandelt wird wie ein Orbit Big Trade: sobald der Trade in TopstepX geschlossen wird, sieht das Auge
 * des Scripts das und schließt den Hedge direkt"). Gegenstück zum Prophos TV-Reader (tv-reader.user.js) für TopstepX:
 *  - Gelesen wird NICHT neu, sondern mit augen_tsx.js (per @require, dieselbe Datei, die der Puls-Bot per CDP in den Tab legt) — Konto
 *    (konto.kontonr, abgekuerzt), Positionen aus der Positions-Tabelle unten, flach NUR mit Beweis (flachBeweis: „No Active Position" in
 *    der Order-Karte bzw. leeres Grid + gesperrter Close-Knopf), Reiter „Positions", Kopf (BAL/MLL, relativ bei Express).
 *  - Gemeldet wird an das Panel dieses PCs (POST http://127.0.0.1:8770/api/tsx-stand, nur im Speicher). Prophos (hedgeTsxSchnellTick)
 *    fragt dort alle 0,05 s, solange ein Topstep-Hedge offen ist, und schließt Fusion nur nach denselben Regeln wie beim Orbit-Reader
 *    (Konto exakt, frisch, Konto-Ruhe, Master vorher gesehen, flach bewiesen).
 *  - Takt aus einem Web Worker wie tv-reader 0.4.0: Chrome drosselt setInterval in verdeckten/minimierten Tabs auf 1/s bzw. nach 5 min auf
 *    1/min; der Worker-Takt nicht. Verbietet TopstepX blob:-Worker (CSP), bleibt es beim gedrosselten setInterval — langsamer, aber die
 *    Frische-Regel in Prophos (Stand ≤ 1 s alt) lässt dann nur Radar und Fusion-Level schließen, nie ein altes Bild.
 * Nur im Puls-Chrome installieren (Anleitung tv-reader/TSX-AUGE.md). Ein zweites TopstepX in einem normalen Chrome mit diesem Script würde
 * ebenfalls melden — Prophos nimmt den jüngsten Tab und schließt nur bei exakt passendem Konto.
 * Update von augen_tsx.js: Tampermonkey hält @require im Cache; bei einer neuen augen_tsx.js-Version Query-Teil und @version anheben. */
(function () {
  'use strict';
  var SCRIPT = '0.1.0';
  var PANEL = 'http://127.0.0.1:8770/api/tsx-stand';
  var TAKT_MS = 250;
  var TAB = 'tsx-' + Math.random().toString(36).slice(2, 10);
  var unterwegs = false, fehlerN = 0, gesendetN = 0, letzterFehler = '';

  function auge() {
    try { return (typeof PROPHOS_AUGEN_TSX !== 'undefined' && PROPHOS_AUGEN_TSX) || globalThis.prophosAugen || null; } catch (_) { return null; }
  }
  function zahlWert(x) { return x && typeof x === 'object' ? (typeof x.wert === 'number' ? x.wert : null) : (typeof x === 'number' ? x : null); }

  // Nur was der Schließer braucht (klein halten: 4 Meldungen je Sekunde). Rechtecke, Inventar und Chart bleiben weg.
  function kurz(s) {
    var k = s.konto || {}, t = s.ticket || {}, r = (t.reiter && t.reiter.positions) || null, kp = s.kopf || {};
    var br = s.toasts && s.toasts.bracket ? s.toasts.bracket : null;
    return {
      v: s.v || null, ts: s.ts || Date.now(), url: String(location.href).slice(0, 120), sichtbar: s.sichtbar || document.visibilityState,
      konto: { aktiv: k.aktiv ? String(k.aktiv).slice(0, 80) : null, kontonr: k.kontonr || null, abgekuerzt: k.abgekuerzt == null ? null : !!k.abgekuerzt,
               liste_offen: !!k.liste_offen },
      positionen: (s.positionen || []).slice(0, 10).map(function (p) {
        return { symbol: p.symbol || null, seite: p.seite || null, menge: typeof p.menge === 'number' ? p.menge : null,
                 avg: typeof p.avg === 'number' ? p.avg : null, pl_text: p.pl_text || null, quelle: p.quelle || null };
      }),
      positionen_sichtbar: s.positionen_sichtbar == null ? null : !!s.positionen_sichtbar,
      flach: s.flach === true ? true : s.flach === false ? false : null,
      reiter_positions: r ? { aktiv: !!r.aktiv } : null,
      kopf: { balance: zahlWert(kp.balance), mll: zahlWert(kp.mll), rpl: zahlWert(kp.rpl), upl: zahlWert(kp.upl),
              balance_relativ: kp.balance_relativ == null ? null : !!kp.balance_relativ },
      bracket: br ? { fill: br.fill ? { preis: br.fill.preis, menge: br.fill.menge, seite: br.fill.seite, symbol: br.fill.symbol } : null,
                      tp: br.tp ? { preis: br.tp.preis } : null, sl: br.sl ? { preis: br.sl.preis } : null } : null,
      popups: (s.popups || []).length,
      fehler: s.fehler ? s.fehler.slice(0, 4).map(function (f) { return String(f).slice(0, 80); }) : null
    };
  }

  function tick() {
    if (unterwegs) return;                         // ein Request zur Zeit — ein hängendes Panel staut sonst Meldungen auf
    var a = auge();
    if (!a || typeof a.stand !== 'function') { letzterFehler = 'augen_tsx.js nicht geladen'; return; }
    var paket;
    try { paket = { tab: TAB, script: SCRIPT, stand: kurz(a.stand({})) }; }
    catch (e) { letzterFehler = 'Lesen: ' + String(e).slice(0, 80); return; }
    unterwegs = true;
    GM_xmlhttpRequest({
      method: 'POST', url: PANEL, timeout: 2000, data: JSON.stringify(paket), headers: { 'Content-Type': 'application/json' },
      onload: function (r) { unterwegs = false; if (r.status === 200) { gesendetN++; fehlerN = 0; letzterFehler = ''; } else { fehlerN++; letzterFehler = 'Panel HTTP ' + r.status; } },
      onerror: function () { unterwegs = false; fehlerN++; letzterFehler = 'Panel nicht erreichbar'; },
      ontimeout: function () { unterwegs = false; fehlerN++; letzterFehler = 'Panel Timeout'; }
    });
  }

  function starteTakt() {
    try {
      var quelle = 'let id=null;onmessage=e=>{if(id)clearInterval(id);id=setInterval(()=>postMessage(0),e.data)}';
      var w = new Worker(URL.createObjectURL(new Blob([quelle], { type: 'text/javascript' })));
      w.onmessage = tick;
      w.postMessage(TAKT_MS);
      return 'worker';
    } catch (_) {
      setInterval(tick, TAKT_MS);
      return 'interval';
    }
  }

  var takt = starteTakt();
  tick();
  // Lebenszeichen in der Konsole des Tabs (kein Badge im TopstepX-Bild — die Augen des Bots lesen die Seite)
  setInterval(function () { console.info('[Prophos TopstepX-Auge ' + SCRIPT + '] Takt ' + takt + ' · gesendet ' + gesendetN + (letzterFehler ? ' · ' + letzterFehler : '')); }, 60000);
})();
