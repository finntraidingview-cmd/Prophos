/* Selbsttest augen.js — Dialog-X (xIn), 13.10.2026, Routine „Puls-Fehler".
 * Muster „konto/konto_balance: tradovate-login '#' nicht geschafft (abmelden): kontextmenü neben 'tradovate' blieb leer: dialog
 * 'Go ad-free. Everywhere' liegt über der seite" — 34 Fehlstarts in 24 h auf 3 PCs, Spur: „erkannt, aber kein eindeutiges X (keins)".
 * Läuft in echtem Chromium (Playwright für Node): node tools/selftest_augen_dialog_x.js [pfad/zu/augen.js]
 * Braucht: npm i -g playwright (+ Chromium) — in der Cloud-Routine vorhanden; ohne Playwright meldet der Test das und endet mit 3.
 * Nachgebaut (kein Live-TradingView): A Vollbild-Dialog, Karte mittig, X nur Symbol · B X mit aria-label · C zwei namenlose X →
 * mehrdeutig · D namenloses X verdeckt → keins · E normaler „Close position"-Dialog mit „Close menu"-X + Submit (wie bisher) ·
 * F einziger Eck-Knopf trägt ein Wort (Upgrade) → keins · G Symbol in einem div ohne role → keins. */
const fs = require('fs');
const path = require('path');
let pw;
try { pw = require('playwright'); } catch (_) {
  try { pw = require(require('child_process').execSync('npm root -g').toString().trim() + '/playwright'); }
  catch (e) { console.log('Playwright für Node fehlt — Test übersprungen (npm i -g playwright)'); process.exit(3); }
}
const { chromium } = pw;
const AUGEN = fs.readFileSync(process.argv[2] || path.join(__dirname, '..', 'mt5-copier', 'augen.js'), 'utf8');
const SVG = '<svg width="18" height="18" viewBox="0 0 18 18"><path d="M3 3l12 12M15 3L3 15" stroke="#000"/></svg>';
function seite(body) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><style>
    body{margin:0;width:1600px;height:900px;font-family:sans-serif}
    .schleier{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:1000}
    .karte{position:absolute;left:500px;top:200px;width:600px;height:400px;background:#fff;border-radius:8px}
    .x{position:absolute;right:16px;top:16px;width:28px;height:28px;border:0;background:none;padding:0}
    .klein{position:absolute;left:600px;top:300px;width:400px;height:220px;background:#fff;border:1px solid #888}
    .cta{position:absolute;left:40px;bottom:30px;width:200px;height:44px}
    .deckel{position:absolute;left:1060px;top:200px;width:60px;height:60px;background:#f00;z-index:5}
  </style></head><body><div id="app">Chart</div>${body}</body></html>`;
}
const F = {
  // A: Vollbild-Dialog (role=dialog = Schleier), Karte mittig, X nur Symbol
  A: seite(`<div role="dialog" data-dialog-name="go-pro" class="schleier"><div class="karte"><h2>Go ad-free. Everywhere.</h2>
        <p>Upgrade now and never see ads again</p><button class="x">${SVG}</button><button class="cta">Upgrade now</button></div></div>`),
  // B: wie A, X mit aria-label
  B: seite(`<div role="dialog" class="schleier"><div class="karte"><h2>Go ad-free. Everywhere.</h2>
        <button class="x" aria-label="Close">${SVG}</button><button class="cta">Upgrade now</button></div></div>`),
  // C: zwei namenlose Knöpfe in der Ecke → mehrdeutig
  C: seite(`<div role="dialog" class="schleier"><div class="karte"><h2>Go ad-free. Everywhere.</h2>
        <button class="x">${SVG}</button><button class="x" style="right:52px">${SVG}</button><button class="cta">Upgrade now</button></div></div>`),
  // D: namenloses X, aber verdeckt → nichts
  D: seite(`<div role="dialog" class="schleier"><div class="karte"><h2>Go ad-free. Everywhere.</h2>
        <button class="x">${SVG}</button><button class="cta">Upgrade now</button></div><div class="deckel"></div></div>`),
  // E: normaler kleiner Dialog mit benanntem X („Close menu") und Submit — wie bisher
  E: seite(`<div role="dialog" data-name="close-position-dialog" class="klein"><h2>Close position</h2>
        <button class="x"><span style="position:absolute;width:1px;height:1px;overflow:hidden">Close menu</span>${SVG}</button>
        <button data-name="submit-button" class="cta">Close position</button></div>`),
  // F: Karte, einziger Eck-Knopf trägt ein Wort (Upgrade) → kein X
  F: seite(`<div role="dialog" class="schleier"><div class="karte"><h2>Go ad-free. Everywhere.</h2>
        <button class="x" style="width:60px">Upgrade</button></div></div>`),
  // G: namenloses X ist ein div ohne role → kein X
  G: seite(`<div role="dialog" class="schleier"><div class="karte"><h2>Go ad-free. Everywhere.</h2>
        <div class="x">${SVG}</div><button class="cta">Upgrade now</button></div></div>`),
};
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1600, height: 900 } });
  let fehl = 0;
  function pr(ok, name, info) { console.log((ok ? 'OK  ' : 'FEHL') + ' ' + name + ' ' + info); if (!ok) fehl++; }
  for (const [name, html] of Object.entries(F)) {
    await pg.setContent(html);
    const st = await pg.evaluate(AUGEN + '\nPROPHOS_AUGEN.stand()');
    const p = (st.popups || [])[0] || null;
    const x = p && p.x;
    const info = JSON.stringify({ n: (st.popups || []).length, titel: p && p.titel, x: x });
    if (name === 'A') pr(x && x.rect && x.namenlos === true && x.rect[0] > 1000 && x.rect[1] < 260, name, info);
    if (name === 'B') pr(x && x.rect && !x.namenlos && x.aria === 'Close', name, info);
    if (name === 'C') pr(x && x.mehrdeutig === 2, name, info);
    if (name === 'D') pr(x === null, name, info);
    if (name === 'E') pr(x && x.rect && !x.namenlos && /Close menu/.test(x.text) && p.submit && p.submit.dn === 'submit-button', name, info);
    if (name === 'F') pr(x === null, name, info);
    if (name === 'G') pr(x === null, name, info);
  }
  await b.close();
  console.log(fehl ? `FEHLER: ${fehl}` : 'alle grün');
  process.exit(fehl ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
