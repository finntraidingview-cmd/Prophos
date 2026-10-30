// ==UserScript==
// @name         Prophos TopstepX-Auge
// @namespace    prophos
// @version      0.3.2
// @description  Liest im TopstepX-Tab des Puls-Chrome Konto, offene Positionen und den Flach-Beweis (dieselbe Lesung wie der Puls-Bot: augen_tsx.js) und meldet sie alle 0,1 s und bei jeder Änderung an das lokale Panel (127.0.0.1:8770). Prophos schließt damit den Fusion-Hedge eines Topstep-Trades, sobald die Position in TopstepX zu ist. Nur lesen — klickt nie.
// @match        https://topstepx.com/*
// @match        https://*.topstepx.com/*
// @require      https://prophos.pages.dev/mt5-copier/augen_tsx.js?v=tsx-0.6.3
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        unsafeWindow
// @connect      127.0.0.1
// @run-at       document-idle
// @updateURL    http://127.0.0.1:8770/userscript/tsx-auge.meta.js
// @downloadURL  http://127.0.0.1:8770/userscript/tsx-auge.user.js
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
 * Update von augen_tsx.js: Tampermonkey hält @require im Cache; bei einer neuen augen_tsx.js-Version Query-Teil und @version anheben.
 * 0.2.0 (29.10.2026, Finn 09:00 Dubai-PC: Tab im Hintergrund → Stand 0,4–0,98 s alt, die Schließ-Grenze ist 1 s — „geht das nicht schneller,
 * so alle 0,1 s?"): Takt 100 ms; zusätzlich meldet ein MutationObserver jede DOM-Änderung des Tabs sofort (höchstens alle 100 ms, ein
 * Request zur Zeit) — DOM-Änderungen kommen aus TopstepX' Datenstrom und werden im Hintergrund nicht gedrosselt, auch wenn die CSP den
 * Worker verbietet. stand.takt sagt, welcher Takt läuft ('worker' | 'interval'). Dazu startet der Bot das Puls-Chrome ohne
 * Hintergrund-Drosselung (order_bot.py puls_chrome_argumente).
 * AUSGELOGGT (Finn: „Wenn TopstepX ausgeloggt ist, soll nicht aus Panik geschlossen werden, sondern Puls geht auf TopstepX und loggt sich
 * wieder ein"): stand.ausgeloggt = true auf der Login-Seite (Adresse …/login|signin|sign-in, wie tsx_url_login im Bot), bei sichtbarem
 * Passwortfeld mit Login-Knopf oder einem Dialog „session expired / logged out". Prophos schließt dann nie über das Auge (auch ohne dieses
 * Feld nicht: ohne Konto-Auslöser fehlt die Kennung) und stößt den Rück-Login des Bots an (hedgeTsxSchnellTick).
 * 0.3.0 LADER (29.10.2026, Finn 10:20: „Ich will, dass sich das Auge automatisch aktualisiert — sowohl bei Topstep als auch beim
 * TradingView-Script für Orbit. Ich will nicht jedes Script von Hand aktualisieren."): dasselbe Prinzip wie tv-reader.user.js 0.10.x. Die
 * Datei ist Lader + eingebauter Kern; der Kern (zwischen KERN-START und KERN-ENDE) ist das Auge 0.2.0 Zeichen für Zeichen — nur SCRIPT,
 * der Doppellauf-Riegel ganz oben und das Feld „lader" in der Meldung sind neu. Der Lader holt im Hintergrund vom Panel DIESES PCs
 * (http://127.0.0.1:8770/userscript/tsx-kern.json: Kern + die aktuelle augen_tsx.js in einem Stück, SHA-256) eine NEUERE Fassung,
 * merkt sie in GM_setValue und fährt sie beim nächsten Laden des TopstepX-Tabs (das stößt Prophos an, nur wenn nichts läuft). eval
 * gesperrt (MV3), nichts gemerkt oder Fehler → die eingebaute Fassung mit der @require-augen_tsx.js, nie schlechter als vorher. Update
 * der Datei selbst (neuer Lader) holt Tampermonkey über @updateURL am Panel bzw. Puls einmal je PC (Knopf „Aktualisieren").
 * 0.3.1 FLACH-FOLGE (29.10.2026, Prüfer S2 zu afb622fa: das Panel hält nur den letzten Stand, Prophos holt ~alle 50 ms — zwei gesehene
 * flache Meldungen konnten eine ungesehene „nicht flach"-Messung beim Karten-Neuaufbau einschließen): der Kern zählt selbst.
 * stand.flach_folge = Zahl aufeinanderfolgender EIGENER Messungen mit flach-Beweis im selben Konto (nicht ausgeloggt); jede andere Messung
 * setzt auf 0. stand.flach_seit = Zeitpunkt (ms) der ersten Messung dieser Serie. Gemessen wird in JEDEM Takt, auch wenn die vorige Meldung
 * noch unterwegs ist (dann wird nur nicht gesendet) — sonst fiele genau die Messung weg, die das Flackern zeigt. Prophos schließt erst ab
 * flach_folge ≥ 3 über ≥ 200 ms; ohne das Feld (Auge < 0.3.1) gilt dort die alte 5-s-Regel. Kommt per Lader, kein Handgriff am PC.
 * 0.3.2 (30.10.2026, PC von Marco: „TopstepX-Auge blind", Stand 15,9 s alt, 975 Ticks, 2 Sends, kein Timeout, Konsole „worker-tot"): (1) worker-tot ist nicht mehr endgültig (s. Worker-Wache);
 * (2) von außen sichtbar: letzter_fehler + letzter_fehler_vor_s (bleibt nach Erfolg stehen), fehler_n (Summe), unterwegs_ms (Dauer des letzten Requests), haenger_n, stand_ms, worker_tot_n;
 * (3) Riegel: ein Request, dessen Rückmeldung > 3 s ausbleibt, wird abgebrochen und freigegeben (bisher blockierte er jede weitere Meldung). Weil dann zwei Meldungen unterwegs sein können,
 * prüft der Schnell-Wächter in Prophos am Schließ-Punkt auch das Alter der Messung selbst (stand.ts, tsxMessungJung). (4) Flach-Folge: Lücke > 0,5 s beendet eine Serie unter 5 s, keine Messungs-Salve nach einem Hänger. Kommt per Lader. */

/* ══ LADER 0.3.0 (s. oben): prophosKern ist das eigentliche Auge. Alles zwischen den Markern KERN-START und KERN-ENDE holt der Lader
 * neuer nach (Panel /userscript/tsx-kern.json) — die Marker nie verschieben oder doppeln (Selbsttest prueft sie). ══ */
function prophosKern(GM_xmlhttpRequest, GM_getValue, GM_setValue, unsafeWindow, PROPHOS_LADER) {
// ==KERN-START==
(function () {
  'use strict';
  // 0.3.0 DOPPELLAUF-RIEGEL: nie zwei Kerne in einer Seite (eingebaute UND nachgeladene Fassung) — lieber blind als doppelt
  if (unsafeWindow.__prophosTsxKernAn) return;
  unsafeWindow.__prophosTsxKernAn = true;
  var SCRIPT = '0.3.2';
  var PANEL = 'http://127.0.0.1:8770/api/tsx-stand';
  var TAKT_MS = 100;                               // 0.2.0: 250 → 100 ms (Finn 29.10.2026)
  var MO_ABSTAND_MS = 100;                         // MutationObserver: höchstens alle 100 ms eine Meldung
  var TAB = 'tsx-' + Math.random().toString(36).slice(2, 10);
  var unterwegs = false, fehlerN = 0, gesendetN = 0, letzterFehler = '';
  var UNTERWEGS_MAX_MS = 3000, unterwegsSeit = 0, anfrage = 0, laufend = null, haengerN = 0, rttMs = null, standMs = null, fehlerMerk = { text: '', at: 0 };   // 0.3.2
  function fehlerSetzen(t) { letzterFehler = t; fehlerN++; fehlerMerk = { text: t, at: Date.now() }; }
  var workerTicks = 0, workerLetzt = 0, timeouts = [];   // 0.3.1 Diagnose: Worker-Ticks, letzte Panel-Timeouts (ms-Zeitstempel)

  function auge() {
    try { return (typeof PROPHOS_AUGEN_TSX !== 'undefined' && PROPHOS_AUGEN_TSX) || globalThis.prophosAugen || null; } catch (_) { return null; }
  }
  function zahlWert(x) { return x && typeof x === 'object' ? (typeof x.wert === 'number' ? x.wert : null) : (typeof x === 'number' ? x : null); }

  // AUSGELOGGT (0.2.0): Login-Seite, Passwortfeld + Login-Knopf oder Dialog „Sitzung abgelaufen" — nur lesen, nie klicken
  var RX_LOGIN_URL = /topstepx\.com\/+(login|signin|sign-in)\b/i;
  var RX_LOGIN_KNOPF = /^\s*(platform login|log ?in|sign ?in)\s*$/i;
  var RX_SITZUNG_WEG = /session (has )?expired|you (have been|were) logged out|logged out|please (log|sign) in again/i;
  function sichtbarEl(e) { try { var r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; } catch (_) { return false; } }
  function ausgeloggt() {
    try {
      if (RX_LOGIN_URL.test(String(location.href))) return true;
      var pw = Array.prototype.some.call(document.querySelectorAll('input[type="password"]'), sichtbarEl);
      if (pw && Array.prototype.some.call(document.querySelectorAll('button,[role="button"],input[type="submit"]'), function (b) {
        return sichtbarEl(b) && RX_LOGIN_KNOPF.test(String(b.textContent || b.value || ''));
      })) return true;
      return Array.prototype.some.call(document.querySelectorAll('[role="dialog"],[role="alertdialog"],[aria-modal="true"]'), function (d) {
        return sichtbarEl(d) && RX_SITZUNG_WEG.test(String(d.textContent || '').slice(0, 600));
      });
    } catch (_) { return false; }
  }

  // FLACH-FOLGE (0.3.1, s. Kopf): Zähler über die eigenen Messungen — REIN bis auf die drei Variablen
  // 0.3.2 (Gegenprüfung): > 0,5 s zwischen zwei Messungen beendet die Serie — nach einem Hänger läge sonst der Abstand ≥ 200 ms über der Lücke, obwohl danach kaum beobachtet wurde.
  // Aber nur, solange die ununterbrochen flache Zeit < 5 s ist (Prüfer S2): sonst schlösse das Auge bei dauerhaft langsamem Takt nie mehr; nach 5 s flach zählt jede Messung (alte 5-s-Regel)
  var flachFolge = 0, flachSeit = null, flachKonto = null, flachLetzt = 0, flachSerieAb = 0, FOLGE_LUECKE_MS = 500, FOLGE_RUHE_MS = 5000;
  function folgeZaehlen(s, aus) {
    var k = (s && s.konto && s.konto.kontonr) || null, ts = (s && s.ts) || Date.now(), jetzt = Date.now();
    if (s && s.flach === true && k && !aus && (flachFolge === 0 || k === flachKonto)) {
      if (!flachSerieAb) flachSerieAb = jetzt;
      if (flachFolge > 0 && jetzt - flachLetzt > FOLGE_LUECKE_MS && jetzt - flachSerieAb < FOLGE_RUHE_MS) flachFolge = 0;
      if (flachFolge === 0) flachSeit = ts;
      flachFolge += 1; flachKonto = k; flachLetzt = jetzt;
    } else { flachFolge = 0; flachSeit = null; flachKonto = k; flachSerieAb = 0; }
  }

  // Nur was der Schließer braucht (klein halten: 10 Meldungen je Sekunde). Rechtecke, Inventar und Chart bleiben weg.
  function kurz(s, aus) {
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
      ausgeloggt: aus,
      flach_folge: flachFolge, flach_seit: flachSeit,
      takt: takt, gesendet_n: gesendetN, worker_ticks: workerTicks, panel_timeouts: timeouts.slice(),   // 0.3.1: von außen sichtbar
      // 0.3.2: warum es hakt (letzterFehler allein stand nur in der Konsole und wurde beim nächsten Erfolg gelöscht)
      letzter_fehler: fehlerMerk.text ? fehlerMerk.text.slice(0, 100) : null, letzter_fehler_vor_s: fehlerMerk.at ? Math.round((Date.now() - fehlerMerk.at) / 1000) : null,
      fehler_n: fehlerN, unterwegs_ms: rttMs, haenger_n: haengerN, stand_ms: standMs, worker_tot_n: workerTotN,
      fehler: s.fehler ? s.fehler.slice(0, 4).map(function (f) { return String(f).slice(0, 80); }) : null
    };
  }

  var letzterTick = 0, takt = 'start';
  function tick() {
    letzterTick = Date.now();
    var a = auge();
    if (!a || typeof a.stand !== 'function') { fehlerSetzen('augen_tsx.js nicht geladen'); folgeZaehlen(null, false); return; }
    var paket;
    try {
      var t0Stand = Date.now(), s = a.stand({}), aus = ausgeloggt();
      standMs = Date.now() - t0Stand;
      folgeZaehlen(s, aus);                         // 0.3.1: JEDE Messung zählt, auch wenn gleich nicht gesendet wird
      paket = { tab: TAB, script: SCRIPT, stand: kurz(s, aus),
        lader: (typeof PROPHOS_LADER !== 'undefined' && PROPHOS_LADER) ? Object.assign({}, PROPHOS_LADER) : null };   // 0.3.0: Lader-Stand
    }
    catch (e) { fehlerSetzen('Lesen: ' + String(e).slice(0, 80)); folgeZaehlen(null, false); return; }
    if (unterwegs) {                               // ein Request zur Zeit — ein hängendes Panel staut sonst Meldungen auf (gemessen ist schon)
      if (Date.now() - unterwegsSeit <= UNTERWEGS_MAX_MS) return;
      haengerN++; fehlerSetzen('Request ohne Rückmeldung > 3 s');   // 0.3.2: über dem Timeout von 2 s = die Rückmeldung selbst kam nicht
      anfrage++;                                   // vor abort(): ruft es onerror sofort auf, zählt das nicht mehr
      try { if (laufend && laufend.abort) laufend.abort(); } catch (_) {}
      unterwegs = false;
    }
    var id = ++anfrage, seit = Date.now();
    unterwegs = true; unterwegsSeit = seit;
    // Späte Rückmeldung eines aufgegebenen Requests gibt den Riegel des neuen nie frei
    var fertig = function () { if (id !== anfrage) return false; unterwegs = false; rttMs = Date.now() - seit; return true; };
    try {
      laufend = GM_xmlhttpRequest({
        method: 'POST', url: PANEL, timeout: 2000, data: JSON.stringify(paket), headers: { 'Content-Type': 'application/json' },
        onload: function (r) { if (!fertig()) return; if (r.status === 200) { gesendetN++; letzterFehler = ''; } else fehlerSetzen('Panel HTTP ' + r.status); },
        onerror: function () { if (fertig()) fehlerSetzen('Panel nicht erreichbar'); },
        ontimeout: function () { if (!fertig()) return; fehlerSetzen('Panel Timeout'); timeouts.push(Date.now()); if (timeouts.length > 5) timeouts.shift(); }
      });
    } catch (e) { unterwegs = false; fehlerSetzen('Senden: ' + String(e).slice(0, 80)); }
  }

  // WORKER-WACHE (0.3.1, PC von Marco 29.10.2026: Stand im Panel 2–6,5 s alt trotz takt 'worker'): new Worker(blob:) wirft bei einer
  // CSP-Sperre NICHT — der Fehler kommt später als error-Event, getickt hätte dann nur noch der MutationObserver (im Hintergrund selten).
  // Jetzt: onerror, Anlauf-Wache (kein Worker-Tick in 0,5 s) und Dauer-Wache (Worker > 2 s stumm) → setInterval zusätzlich.
  // 0.3.2 NICHT MEHR ENDGÜLTIG (Konsole Marco 30.10.2026: dauerhaft „worker-tot", obwohl worker_ticks weiter stiegen): die Wache läuft im selben Hauptfaden wie die
  // Worker-Nachrichten, ein Hänger der Seite > 2 s löste sie aus, ohne dass der Worker tot war; danach tickten Worker UND Ersatz (doppelte stand()-Last). Jetzt: der nächste Worker-Tick
  // beendet den Ersatz (takt wieder 'worker'); bleibt der Worker wirklich stumm, Neustart nach 10 s, dann 20 s … höchstens alle 5 min.
  var wAkt = null, blobUrl = null, ersatzId = null, workerStartAt = 0, neustartWarte = 10000, workerTotN = 0;
  function ersatzStart(grund) {
    if (ersatzId !== null) return;
    ersatzId = setInterval(function () { if (Date.now() - letzterTick >= 80) tick(); }, TAKT_MS);
    workerTotN++; takt = 'worker-tot'; fehlerSetzen('Worker: ' + grund);
  }
  function workerTick() {
    workerTicks++; workerLetzt = Date.now(); neustartWarte = 10000;
    if (ersatzId !== null) { clearInterval(ersatzId); ersatzId = null; }
    takt = 'worker';
    if (Date.now() - letzterTick >= 80) tick();   // gestaute Worker-Nachrichten nach einem Hänger nicht als Salve messen (zählt sonst als Flach-Folge)
  }
  function workerStart() {
    workerStartAt = Date.now();
    try {
      if (wAkt && wAkt.terminate) wAkt.terminate();
      if (!blobUrl) blobUrl = URL.createObjectURL(new Blob(['let id=null;onmessage=e=>{if(id)clearInterval(id);id=setInterval(()=>postMessage(0),e.data)}'], { type: 'text/javascript' }));
      var w = new Worker(blobUrl);
      wAkt = w;
      w.onmessage = function () { if (w === wAkt) workerTick(); };
      w.onerror = function () { if (w === wAkt) ersatzStart('Fehler beim Start (CSP?)'); };
      w.postMessage(TAKT_MS);
      return true;
    } catch (_) { return false; }
  }
  function starteTakt() {
    var ok = workerStart();
    if (!ok) ersatzStart('nicht startbar');
    else setTimeout(function () { if (!workerTicks) ersatzStart('kein Tick in 0,5 s'); }, 500);
    setInterval(function () {
      var jetzt = Date.now();
      if (ersatzId === null) { if (workerTicks && jetzt - workerLetzt > 2000) ersatzStart('über 2 s stumm'); return; }
      if (jetzt - Math.max(workerLetzt, workerStartAt) > neustartWarte) { neustartWarte = Math.min(neustartWarte * 2, 300000); workerStart(); }
    }, 1000);
    return ok ? 'worker' : 'interval';
  }

  var t0 = starteTakt();
  if (t0 === 'interval' || ersatzId === null) takt = t0;   // onerror kann nicht vorher feuern (asynchron) — sicher ist sicher
  // MutationObserver (0.2.0): jede DOM-Änderung meldet sofort — höchstens alle MO_ABSTAND_MS, ein Request zur Zeit (tick prüft unterwegs)
  try {
    new MutationObserver(function () { if (Date.now() - letzterTick >= MO_ABSTAND_MS) tick(); })
      .observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['aria-expanded', 'disabled', 'aria-selected'] });
  } catch (_) {}
  tick();
  // Lebenszeichen in der Konsole des Tabs (kein Badge im TopstepX-Bild — die Augen des Bots lesen die Seite)
  setInterval(function () { console.info('[Prophos TopstepX-Auge ' + SCRIPT + '] Takt ' + takt + ' · gesendet ' + gesendetN + (letzterFehler ? ' · ' + letzterFehler : '')); }, 60000);
})();
// ==KERN-ENDE==
}

(function prophosLader() {
  'use strict';
  const LADER_V = 1;
  const EINGEBAUT = '0.3.2';                  // = SCRIPT im Kern (Selbsttest prueft die Gleichheit)
  const KERN_URL = 'http://127.0.0.1:8770/userscript/tsx-kern.json';
  const MERK = 'prophos_tsx_kern_v1';         // GM-Speicher: {version, sha, code, at}
  const info = { v: LADER_V, eval: null, laeuft: EINGEBAUT, quelle: 'eingebaut', bereit: null, fehler: '' };
  // REIN RECHNEND: '0.10.0' > '0.9.12' (Zahl je Stelle)
  function neuer(a, b) {
    const x = String(a || '').split('.').map(Number), y = String(b || '').split('.').map(Number);
    for (let i = 0; i < Math.max(x.length, y.length); i++) {
      const d = (x[i] || 0) - (y[i] || 0);
      if (d) return d > 0;
    }
    return false;
  }
  let evalOk = false;
  try { evalOk = new Function('return 1')() === 1; } catch (e) { info.fehler = 'eval gesperrt: ' + String((e && e.message) || e).slice(0, 80); }
  info.eval = evalOk;
  const PARAM = ['GM_xmlhttpRequest', 'GM_getValue', 'GM_setValue', 'unsafeWindow', 'PROPHOS_LADER'];
  // je GM-Funktion mit typeof-Schutz (Prüfer 29.10.2026): fehlt eine (Grant-Problem, andere Engine), startet trotzdem die eingebaute Fassung —
  // ohne Schutz würfe der Lader hier, und das Auge wäre ganz tot. Ohne GM_getValue/GM_setValue wird nur nichts gemerkt.
  const gm = () => [(typeof GM_xmlhttpRequest !== 'undefined' ? GM_xmlhttpRequest : undefined), (typeof GM_getValue !== 'undefined' ? GM_getValue : undefined),
    (typeof GM_setValue !== 'undefined' ? GM_setValue : undefined),
    (typeof unsafeWindow !== 'undefined' ? unsafeWindow : (typeof window !== 'undefined' ? window : globalThis))];
  let laeuft = false;
  if (evalOk) {
    let m = null;
    try { m = GM_getValue(MERK, null); } catch (_) {}
    if (m && typeof m.code === 'string' && m.version && neuer(m.version, EINGEBAUT)) {
      let fn = null;
      try { fn = new Function(...PARAM, m.code); } catch (e) { info.fehler = 'gemerkte Fassung ' + m.version + ' nicht lesbar: ' + String((e && e.message) || e).slice(0, 80); }
      if (fn) {
        info.laeuft = m.version; info.quelle = 'nachgeladen';
        try { fn(...gm(), info); laeuft = true; }
        catch (e) { info.laeuft = EINGEBAUT; info.quelle = 'eingebaut'; info.fehler = 'gemerkte Fassung ' + m.version + ' warf: ' + String((e && e.message) || e).slice(0, 80); }
      }
      if (!laeuft) { try { GM_setValue(MERK, null); } catch (_) {} }   // kaputte Fassung nie wieder starten
    }
  }
  if (!laeuft) {
    const uw = gm()[3];
    if (uw && uw.__prophosTsxKernAn) { info.quelle = 'blind (Riegel)'; info.fehler += ' — Doppellauf-Riegel: eingebaute Fassung nicht gestartet'; }
    prophosKern(...gm(), info);
  }
  if (!evalOk || typeof GM_setValue === 'undefined' || typeof setTimeout !== 'function') return;   // ohne eval/Speicher nie etwas nachladen
  // Hintergrund: neuere Fassung vom Panel dieses PCs holen, pruefen, fuer das NAECHSTE Laden merken (nie zwei Kerne in einer Seite)
  async function sha256(t) {
    const h = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(t));
    return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, '0')).join('');
  }
  function holen() {
    try {
      GM_xmlhttpRequest({ method: 'GET', url: KERN_URL, timeout: 8000, onload: async (r) => {
        try {
          if (r.status !== 200) { info.fehler = 'tsx-kern.json HTTP ' + r.status; return; }
          const j = JSON.parse(r.responseText);
          if (!j || typeof j.kern !== 'string' || !j.version || !/^[0-9a-f]{64}$/.test(String(j.sha || ''))) { info.fehler = 'tsx-kern.json unvollstaendig'; return; }
          if (!neuer(j.version, info.laeuft)) { info.bereit = null; return; }   // nichts Neues
          if ((await sha256(j.kern)) !== j.sha) { info.fehler = 'Pruefsumme passt nicht (' + j.version + ')'; return; }
          try { new Function(...PARAM, j.kern); } catch (e) { info.fehler = 'Fassung ' + j.version + ' nicht lesbar'; return; }
          GM_setValue(MERK, { version: j.version, sha: j.sha, code: j.kern, at: Date.now() });
          info.bereit = j.version; info.fehler = '';
        } catch (e) { info.fehler = 'tsx-kern.json: ' + String((e && e.message) || e).slice(0, 80); }
      }, onerror: () => { info.fehler = 'Panel nicht erreichbar (tsx-kern.json)'; } });
    } catch (e) { info.fehler = 'holen: ' + String((e && e.message) || e).slice(0, 80); }
  }
  // gestreut (Jitter-Regel): erster Blick 10–40 s nach dem Laden, dann alle 20–40 min
  const naechster = (a, b) => a + Math.random() * (b - a);
  setTimeout(function takt() { holen(); setTimeout(takt, naechster(20 * 60000, 40 * 60000)); }, naechster(10000, 40000));
})();
