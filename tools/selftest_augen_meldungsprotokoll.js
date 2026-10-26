/* Selbsttest augen.js — Meldungsprotokoll (toasts.log je Textknoten), 26.10.2026, Routine „Puls-Fehler".
 * Muster „unklar: ergebnis unklar — … in 15 s weder fill-meldung noch neue position": 2 PCs (16.10. Seite 2195×1100, 26.10. Seite
 * 1536×730), Spur „Show more 1/4 … 4/4: kein Knopf ganz im Bild (Stapel [56, 721, 416, 9])" + „gruppen: orders(zu, 4 Texte) · log 375 Z"
 * + „Meldungen roh: nichts" — die Order lag. Der Stapel klebt an der Unterkante, die Preiszeile liegt unter dem Fensterrand, und der
 * Rückfall auf role=log las textContent („Buy 1at 29,289.50" — RX_D_EN fand nichts).
 * Läuft in echtem Chromium (Playwright für Node): node tools/selftest_augen_meldungsprotokoll.js [pfad/zu/augen.js]
 * Nachgebaut (kein Live-TradingView): A Stapel zu, Preiszeilen unter dem Rand, Protokoll = Toast-Liste (spans ohne Leerzeichen) →
 * Fill + TP kommen aus dem Protokoll · B Stapel ganz im Bild → Gruppe UND Protokoll liefern dieselbe Meldung (Bot entdoppelt über den
 * Schlüssel) · C kein role=log → log leer, Gruppe wie bisher. */
const fs = require('fs');
const path = require('path');
let pw;
try { pw = require('playwright'); } catch (_) {
  try { pw = require(require('child_process').execSync('npm root -g').toString().trim() + '/playwright'); }
  catch (e) { console.log('Playwright für Node fehlt — Test übersprungen (npm i -g playwright)'); process.exit(3); }
}
const { chromium } = pw;
const AUGEN = fs.readFileSync(process.argv[2] || path.join(__dirname, '..', 'mt5-copier', 'augen.js'), 'utf8');
// Toast wie TradingView: Titel, dann „Buy 1" und „at 29,289.50" in EIGENEN spans ohne Leerzeichen dazwischen
const T = (titel, seite, preis) => `<div class="toast"><div class="titel">${titel}</div><div class="zeile"><span>${seite}</span><span>at ${preis}</span></div></div>`;
function seite(top, mitLog) {
  const list = `<div ${mitLog ? 'role="log" aria-live="polite"' : ''} class="toastListInner-x" style="position:fixed;left:56px;top:${top}px;width:416px">
      <div class="toastGroup-x"><div class="leiste"><button data-name="toast-group-expand-button-orders" aria-expanded="false">Show more 1</button>
        <button data-name="toast-group-close-button-orders">×</button></div>
        ${T('Take Profit order placed', 'Sell 1', '29,367.75')}${T('Market order executed', 'Buy 1', '29,289.50')}</div></div>`;
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><style>
    body{margin:0;width:1536px;height:730px;font-family:sans-serif} .toast{height:44px;padding:2px 8px} .titel{height:20px;line-height:20px}
    .zeile{height:20px;line-height:20px} .zeile span{display:inline-block}
  </style></head><body><div id="app">Chart</div>${list}</body></html>`;
}
const F = {
  A: seite(721, true),    // Stapel-Oberkante 721 bei 730 px Fenster: nur der Titel „Take Profit order placed" ragt ins Bild, Preiszeilen darunter
  B: seite(500, true),    // alles im Bild
  C: seite(500, false),   // kein role=log
};
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1536, height: 730 } });
  let fehl = 0;
  function pr(ok, name, info) { console.log((ok ? 'OK  ' : 'FEHL') + ' ' + name + ' ' + info); if (!ok) fehl++; }
  for (const [name, html] of Object.entries(F)) {
    await pg.setContent(html);
    const st = await pg.evaluate(AUGEN + '\nPROPHOS_AUGEN.stand()');
    const t = st.toasts || {}, ms = t.meldungen || [], log = t.log || [], gr = (t.gruppen || [])[0] || {};
    const fillLog = ms.filter(m => m.gruppe === 'log' && m.art === 'fill' && m.status === 'ausgefuehrt' && m.seite === 'buy' && m.menge === 1 && m.preis === 29289.5);
    const tpLog = ms.filter(m => m.gruppe === 'log' && m.art === 'tp' && m.seite === 'sell' && m.preis === 29367.75);
    const fillGr = ms.filter(m => m.gruppe === 'orders' && m.art === 'fill' && m.preis === 29289.5);
    const info = `gruppe ${gr.gruppe || '-'}(${gr.offen === false ? 'zu' : gr.offen}, ${(gr.texte || []).length} Texte) · log ${log.length} (${log.map(l => (l.texte || []).length + ' Knoten, ' + (l.text || '').length + ' Z').join('; ')}) · meldungen ${ms.length}: ${ms.map(m => m.gruppe + ':' + m.art + ' ' + m.seite + ' ' + m.menge + ' @' + m.preis).join(' | ')}`;
    if (name === 'A') pr(gr.offen === false && (gr.texte || []).length < 4 && fillLog.length === 1 && tpLog.length === 1 && fillGr.length === 0
                         && log.length === 1 && / at 29,289\.50/.test(log[0].text) && log[0].texte.length === 8, 'A Stapel unter dem Rand → Fill + TP aus dem Protokoll', info);
    if (name === 'B') pr(fillLog.length === 1 && fillGr.length === 1 && tpLog.length === 1 && fillLog[0].text === fillGr[0].text, 'B Stapel im Bild → Gruppe und Protokoll, gleicher Text', info);
    if (name === 'C') pr(log.length === 0 && fillGr.length === 1 && fillLog.length === 0, 'C ohne role=log → Gruppe wie bisher, log leer', info);
  }
  await b.close();
  console.log(fehl ? `${fehl} FEHLER` : 'alle Prüfungen bestanden');
  process.exit(fehl ? 1 : 0);
})().catch(e => { console.log('FEHL Testlauf: ' + e); process.exit(2); });
