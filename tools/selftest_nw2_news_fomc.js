/* Selbsttest NW2 (27.11.2026): News-Fenster je Firma × Kontoart — FOMC jeder Stufe (prophos.html newsIstFomc / newsFensterZeile /
 * newsFomcTermine / newsFomcSperre (nur Start-Sperre), dazu newsStartSperre / newsStartBezug / newsKeinKlick / acNewsFaellig unverändert für rot).
 * Finn 27.11.2026, Korrektur: „Mach alle Prop für uns bei FOMC, nicht nur Blue Guardian, alle" — jede Funded-CFD-Firma, kein Firmenname im Code.
 * Rein rechnend, ohne Browser. */
// Läuft unter Node und unter dem JavaScriptCore von macOS (kein Node auf dem Mac nötig, wie .claude/jscheck.sh):
//   node tools/selftest_nw2_news_fomc.js [prophos.html]
//   /System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc tools/selftest_nw2_news_fomc.js -- [prophos.html]
const IST_NODE = typeof require === 'function' && typeof process !== 'undefined';
const ARG = IST_NODE ? process.argv[2] : (typeof scriptArgs !== 'undefined' && scriptArgs[0]) || (typeof arguments !== 'undefined' && arguments[0]);
const SRC = IST_NODE ? require('fs').readFileSync(ARG || require('path').join(__dirname, '..', 'prophos.html'), 'utf8') : readFile(ARG || 'prophos.html');
const aus = IST_NODE ? (t => console.log(t)) : (t => print(t));

function fn(name) {
  let a = SRC.indexOf(`\n  function ${name}(`);
  if (a < 0) a = SRC.indexOf(`\n  async function ${name}(`);
  if (a < 0) throw new Error(`Funktion ${name} nicht gefunden`);
  const e = SRC.indexOf('\n  }\n', a + 1);
  return SRC.slice(a + 1, e + 4);
}
function zeile(anfang, bis) {
  const a = SRC.indexOf('\n' + anfang);
  if (a < 0) throw new Error(`Zeile „${anfang}" nicht gefunden`);
  const e = SRC.indexOf(bis, a + 1);
  return SRC.slice(a + 1, e + bis.length);
}
if (/blue\s*g[u]?ardian/i.test([fn('newsIstFomc'), fn('newsFensterZeile'), fn('newsFomcTermine'), fn('newsPlanKonto'), fn('newsFomcFenster'),
  fn('newsFomcSperre'), fn('newsStartSperre'), fn('newsStartBezug'), zeile('  const NEWS_FOMC_STANDARD = ', '}\n')].join('\n'))) throw new Error('Firmenname im Code');

// Umgebung der herausgeschnittenen Funktionen: als Globale, der Code läuft in EINEM indirekten eval (const bleibt darin)
const ctx = globalThis;
Object.assign(ctx, {
  newsState: { events: [], loaded: true, fetched: 0, regelAn: true },
  newsFenster: { zeilen: [] },
  accounts: [],
  newsFensterLaden: () => {},
  routeIstEcho: r => r === 'mt5' || r === 'mt5v2',
  _newsKalenderGesperrt: new Map(),
});
(0, eval)([
  zeile('  const NEWS_REGEL = ', '}\n'),
  zeile('  const NEWS_FOMC_STANDARD = ', '}\n'),
  'const newsUhr = ms => new Date(ms).toISOString().slice(11, 16)',
  ...['newsHash01', 'newsBloecke', 'newsRegelStand', 'newsIstFundedCfd', 'newsStartSperre', 'newsStartBezug', 'newsKeinKlick', 'newsIstFomc', 'newsFirmaKey',
    'newsFensterZeile', 'newsFomcTermine', 'newsPlanKonto', 'newsFomcFenster', 'newsFomcSperre', 'acNewsFaellig'].map(fn),
  'globalThis.N = { NEWS_REGEL, newsBloecke, newsStartSperre, newsStartBezug, newsKeinKlick, newsIstFomc, newsFensterZeile, newsFomcTermine, newsFomcSperre, acNewsFaellig }',
].join('\n'));
const N = globalThis.N;

let fehler = 0;
const ok = (b, t) => { aus((b ? '  ✓ ' : '  ✗ ') + t); if (!b) fehler++; };
const M = 60000, T = Date.parse('2026-12-02T15:00:00Z');   // ein Mittwoch, frei gewählt
const iso = ms => new Date(ms).toISOString();

// Einstellung wie in sql/2026-11-27_nw2_news_fomc_je_firma.sql
const ZEILE = { name: 'Alle Firmen', firmen: ['*'], kontoarten: ['funded_cfd'], fomc_jede_stufe: true, vor_min: 7, nach_min: 6, streu_min: 2, aktiv: true };
const AUS = Object.assign({}, ZEILE, { fomc_jede_stufe: false });
const NUR_BG_AUS = { name: 'Blue Guardian', firmen: ['blueguardian'], kontoarten: ['funded_cfd'], fomc_jede_stufe: false, vor_min: 7, nach_min: 6, streu_min: 2, aktiv: true };
const REDE = { title: 'FOMC Member Williams Speaks', country: 'USD', date: iso(T), impact: 'Low' };
const ROT = { title: 'CPI m/m', country: 'USD', date: iso(T + 6 * 3600000), impact: 'High' };   // 21:00, Block 19:00–21:15…18
const kalender = (events) => { ctx.newsState.events = events; ctx.newsState.loaded = true; ctx.newsState.fetched = T; ctx.newsState.regelAn = true; };

ctx.accounts = [
  { id: 'bgF', firm: 'Blue Guardian', type: 'funded_cfd' },
  { id: 'bgP1', firm: 'Blue Guardian', type: 'phase1' },
  { id: 'bgP2', firm: 'Blue Guardian', type: 'phase2' },
  { id: 'fnF', firm: 'FundedNext', type: 'funded_cfd' },
  { id: 'ftF', firm: 'FTMO', type: 'funded_cfd' },
  { id: 'fnP1', firm: 'FundedNext', type: 'phase1' },
  { id: 'ch', firm: 'Tradeify', type: 'challenge' },
  { id: 'apx', firm: 'Apex', type: 'winning_days' },
];
const plan = (acc, extra) => Object.assign({ id: 'p-' + acc, masterAccountId: acc, status: 'open', route: 'mt5', startUm: iso(T) }, extra || {});

aus('1) FOMC-Erkennung am Titel');
for (const t of ['FOMC Member Williams Speaks', 'FOMC Meeting Minutes', 'FOMC Statement', 'FOMC Press Conference', 'FOMC Economic Projections',
  'Federal Funds Rate', 'Fed Chair Powell Speaks', 'Fed Chair Powell Testifies', 'fomc member bowman speaks']) ok(N.newsIstFomc(t), `FOMC: ${t}`);
for (const t of ['CPI m/m', 'Beige Book', 'Unemployment Claims', 'Non-Farm Employment Change', 'Treasury Sec Speaks', 'President Speaks', '', null])
  ok(!N.newsIstFomc(t), `kein FOMC: ${t}`);

aus('2) Einstellung: Standard alle Firmen, Tabelle geht vor');
ok(!!N.newsFensterZeile([], 'Blue Guardian', 'funded_cfd') && !!N.newsFensterZeile(null, 'FTMO', 'funded_cfd') && !!N.newsFensterZeile([], '', 'funded_cfd'), 'ohne Tabellen-Zeile: Standard an für jede Firma, Funded CFD');
ok(N.newsFensterZeile([], 'Blue Guardian', 'phase1') === null && N.newsFensterZeile([], 'FTMO', 'challenge') === null && N.newsFensterZeile([], 'Apex', 'winning_days') === null && N.newsFensterZeile([], 'x', '') === null, 'Standard: Phase 1 / Challenge / Winning Days / ohne Kontoart → keine Zeile');
ok(N.newsFensterZeile([ZEILE], 'FundedNext', 'FUNDED_CFD') === ZEILE, 'Tabellen-Zeile „*" gilt für jede Firma');
ok(N.newsFensterZeile([AUS], 'Blue Guardian', 'funded_cfd') === null && N.newsFensterZeile([AUS], 'FTMO', 'funded_cfd') === null, 'Zeile „*" aus → für alle aus (kein Rückfall auf den Standard)');
ok(N.newsFensterZeile([Object.assign({}, ZEILE, { aktiv: false })], 'FTMO', 'funded_cfd') === null, 'Zeile „*" aktiv false → aus');
ok(N.newsFensterZeile([ZEILE, NUR_BG_AUS], 'Blue Guardian', 'funded_cfd') === null && N.newsFensterZeile([ZEILE, NUR_BG_AUS], 'FTMO', 'funded_cfd') === ZEILE, 'Zeile mit Firmenname geht für diese Firma vor, die anderen bleiben bei „*"');
ok(N.newsFensterZeile([ZEILE], 'Blue Guardian', 'phase2') === null, 'Tabellen-Zeile: Phase 2 → keine Zeile');

aus('3) Fenster-Termine');
let ft = N.newsFomcTermine([REDE, ROT, { title: 'FOMC Statement', country: 'USD', date: iso(T), impact: 'High' },
  { title: 'FOMC Member X Speaks', country: 'EUR', date: iso(T), impact: 'Low' }, { title: 'CB Consumer Confidence', country: 'USD', date: iso(T), impact: 'Medium' },
  { title: 'FOMC Member Bowman Speaks', country: 'USD', date: iso(T + 3600000), impact: 'Medium' }], ZEILE);
ok(ft.length === 2 && ft[0].titel === REDE.title && /Bowman/.test(ft[1].titel), 'nur USD-FOMC unter rot (gelb + orange), rot und Nicht-FOMC nicht');
ok(ft.every(x => x.vor >= 7 * M && x.vor <= 9 * M && x.nach >= 6 * M && x.nach <= 8 * M), 'Fenster 7–9 min vor, 6–8 min nach (gestreut)');
const ft2 = N.newsFomcTermine([REDE], ZEILE);
ok(ft2[0].vor === ft[0].vor && ft2[0].nach === ft[0].nach, 'Streuung je Termin fest (auf jedem Gerät gleich)');
ok(N.newsFomcTermine([REDE], Object.assign({}, ZEILE, { vor_min: 1, nach_min: 0, streu_min: 0 }))[0].vor === 6 * M, 'nie unter 6 min, auch bei kleinerer Einstellung');
ok(N.newsFomcTermine([REDE], null).length === 0, 'ohne Zeile keine Termine');

aus('4) Start-Sperre');
ctx.newsFenster.zeilen = [ZEILE];
kalender([REDE, ROT]);
const X = N.newsFomcTermine([REDE], ZEILE)[0];
let s = N.newsStartSperre(plan('bgF'), T);
ok(s && s.fomc && /FOMC-Termin FOMC Member Williams Speaks/.test(s.text) && s.bis === X.t1, 'Blue-Guardian-Funded: Start im Fenster gesperrt, bis Fenster-Ende');
for (const a of ['fnF', 'ftF']) { const y = N.newsStartSperre(plan(a), T); ok(y && y.fomc && y.bis === X.t1, `dieselbe Rede, ${a} (Funded CFD): ebenso gesperrt`); }
ok(!!N.newsStartSperre(plan('bgF'), T - 6 * M) && !!N.newsStartSperre(plan('bgF'), T + 5.9 * M), '6 min davor und 5,9 min danach gesperrt');
ok(N.newsStartSperre(plan('bgF'), T - 9.1 * M) === null && N.newsStartSperre(plan('bgF'), T + 8.1 * M) === null, 'außerhalb des Fensters frei');
ok(N.newsStartSperre(plan('bgP1'), T) === null && N.newsStartSperre(plan('bgP2'), T) === null && N.newsStartSperre(plan('fnP1'), T) === null, 'Phase 1 und 2 (jede Firma): nicht gesperrt');
ok(N.newsStartSperre(plan('ch'), T) === null, 'Challenge: nicht gesperrt');
ok(N.newsStartSperre(plan('apx'), T) === null, 'Winning Days: nicht gesperrt');
ok(!!N.newsStartSperre({ id: 'x', masterAccountId: 'fehlt', masterFirm: 'Blue Guardian', fundedCfd: true }, T), 'Konto nicht im Cache: Firma + Kennung am Plan reichen');
ctx.newsFenster.zeilen = [];
ok(!!N.newsStartSperre(plan('bgF'), T) && !!N.newsStartSperre(plan('ftF'), T), 'Tabelle leer / nicht lesbar: Standard an, gesperrt');
ctx.newsFenster.zeilen = [AUS];
ok(N.newsStartSperre(plan('bgF'), T) === null && N.newsStartSperre(plan('fnF'), T) === null, 'Schalter FOMC aus: wie vor NW2, nichts gesperrt');
ctx.newsFenster.zeilen = [ZEILE];

aus('5) Rot wie bisher');
const tr = Date.parse(ROT.date);
s = N.newsStartSperre(plan('bgF'), tr - 60 * M);
ok(s && !s.fomc && /USD-News CPI/.test(s.text), 'rote News sperrt Blue Guardian wie bisher (120 min vorher)');
s = N.newsStartSperre(plan('fnF'), tr - 60 * M);
ok(s && /USD-News CPI/.test(s.text), 'rote News sperrt jede andere Funded-CFD-Firma wie bisher');
ok(N.newsStartSperre(plan('bgP1'), tr) === null, 'rote News: Phase 1 frei wie bisher');
const nurRot = N.newsBloecke([REDE, ROT]);
ok(nurRot.length === 1 && nurRot[0].termine.length === 1 && nurRot[0].termine[0].titel === 'CPI m/m', 'rote Blöcke enthalten die gelbe Rede nicht');
ok(N.newsKeinKlick(T) === null && !!N.newsKeinKlick(tr), 'newsKeinKlick (rot) kennt die gelbe Rede nicht');
ctx.newsState.fetched = 0;
s = N.newsStartSperre(plan('bgF'), T);
ok(s && s.kalender === true, 'Kalender fehlt: bestehende Fail-closed-Sperre, unverändert');
kalender([REDE, ROT]);
ctx.newsState.regelAn = false;
ok(N.newsStartSperre(plan('bgF'), T) === null, 'Schalter News-Regel aus: auch FOMC aus');
ctx.newsState.regelAn = true;

aus('6) Nachholen: Bezug ab Fenster-Ende');
const echtNow = Date.now;
Date.now = () => T;
ok(N.newsStartBezug(plan('bgF')) === X.t1, 'Blue-Guardian-Funded, Startzeit im FOMC-Fenster → Bezug = Fenster-Ende');
ok(N.newsStartBezug(plan('fnF')) === X.t1, 'andere Funded-CFD-Firma → ebenso Fenster-Ende');
ctx.newsFenster.zeilen = [AUS];
ok(N.newsStartBezug(plan('bgF')) === T, 'Schalter FOMC aus → Bezug = Startzeit');
ctx.newsFenster.zeilen = [ZEILE];
ok(N.newsStartBezug(plan('bgP1')) === T, 'Phase 1 → Bezug = Startzeit');
ok(N.newsStartBezug(plan('fnF', { startUm: iso(tr - 60 * M) })) === nurRot[0].t1, 'rot: Bezug = Block-Ende wie bisher');
ok(N.newsStartBezug(plan('bgF', { startUm: iso(tr - 60 * M) })) === nurRot[0].t1, 'rot bei Blue Guardian: Bezug = Block-Ende wie bisher');
// FOMC-Rede kurz vor einem roten Block: Fenster-Ende fällt in den Block → Bezug = Block-Ende
const REDE2 = { title: 'FOMC Member Bowman Speaks', country: 'USD', date: iso(nurRot[0].t0 - 3 * M), impact: 'Medium' };
kalender([REDE2, ROT]);
ok(N.newsStartBezug(plan('bgF', { startUm: REDE2.date })) === nurRot[0].t1, 'Rede direkt vor rotem Block: Bezug = Ende des roten Blocks');
kalender([REDE, ROT]);

aus('7) Schließen unverändert — das FOMC-Fenster ist nur Start-Sperre (Prüfer-Stopp zu 8ced0598)');
const offen = plan('bgF', { startedAt: iso(T - 120 * M) });
const SCHLIESS = ['acNewsFaellig', 'acNewsTick', 'acTick', 'acEchoSchliessen', 'newsKeinKlick'].map(fn).join('\n');
ok(!/[fF]omc|newsFenster/.test(SCHLIESS), 'Schließ-Wege (News-Schließen, Auto-Close, Echo-Schließen) kennen das FOMC-Fenster nicht');
// Stopp-Fall 1: FOMC-Rede 10 min vor roter News — das Schließen vor der roten News läuft wie vor NW2
for (const vor of [10, 15, 20, 30]) {
  kalender([{ title: 'FOMC Member Barr Speaks', country: 'USD', date: iso(tr - vor * M), impact: 'Low' }, ROT]);
  const mit = N.acNewsFaellig([offen], tr - 15 * M);
  kalender([ROT]);
  const ohne = N.acNewsFaellig([offen], tr - 15 * M);
  ok(mit.length === 1 && mit[0].phase === 'zu' && ohne.length === 1 && ohne[0].phase === mit[0].phase && ohne[0].frist === mit[0].frist, `Rede ${vor} min vor roter News: offener Trade wird um t − 15 geschlossen, gleich wie ohne Rede`);
}
// Stopp-Fall 2: FOMC-Fenster überdeckt das Auto-Close-Fenster 23:30–23:50 Dubai (= 19:30–19:50 UTC) — Auto-Close fragt nur newsKeinKlick (rot)
const AC0 = Date.parse('2026-12-02T19:30:00Z');
kalender([{ title: 'FOMC Member Waller Speaks', country: 'USD', date: iso(AC0 + 6 * M), impact: 'Medium' }, { title: 'Fed Chair Powell Speaks', country: 'USD', date: iso(AC0 + 14 * M), impact: 'Low' }]);
let frei = true;
for (let m = 0; m <= 20; m++) if (N.newsKeinKlick(AC0 + m * M) !== null) frei = false;
ok(frei, 'zwei FOMC-Reden über 23:30–23:50 Dubai: Auto-Close hat in jeder Minute freie Hand (newsKeinKlick = null)');
ok(!!N.newsStartSperre(plan('bgF'), AC0 + 6 * M), 'dieselbe Lage: ein neuer Start ist gesperrt');
ok(N.acNewsFaellig([offen], AC0 + 6 * M).length === 0, 'gelbe Rede allein: kein Zwangsschließen');
kalender([REDE, ROT]);
Date.now = echtNow;

aus(fehler ? `\n${fehler} FEHLER` : '\nalles grün');
if (IST_NODE) process.exit(fehler ? 1 : 0); else if (fehler) throw new Error(fehler + ' Fehler');
