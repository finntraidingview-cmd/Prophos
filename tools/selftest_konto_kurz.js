/* Selbsttest: gekürzte und angeklebte Kontotexte im Reader (prophos.html kontoTextBezug / kontoTextEindeutig / kontoKlebtBalance / hedgeMasterWegEntscheid
 * mit kontoBewiesen), 27.10.2026, Slave 6 — Befund Heim-Wache WD-Plan 4a1a8a79: 56 Heimwege mit Umschalter-Klick, obwohl der Puls-Chrome
 * im WD-Konto stand. Das Userscript liefert für 20-stellige Namen nur den Anfang („FTDFYSLX1500000000", TradingView kürzt mit „…") und für
 * 18-stellige die ID mit angeklebten Balance-Ziffern („TDFYSL150000000000156"). Kennungen frei erfunden (Repo öffentlich), Form wie echt.
 * Rein rechnend, ohne Browser: node tools/selftest_konto_kurz.js [pfad/zu/prophos.html] */
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const SRC = fs.readFileSync(process.argv[2] || path.join(__dirname, '..', 'prophos.html'), 'utf8');

// Funktion samt Rumpf herausschneiden: beginnt mit „\n  function NAME(", endet an der ersten Zeile „  }" auf derselben Einrückung
function fn(name) {
  const a = SRC.indexOf(`\n  function ${name}(`);
  if (a < 0) throw new Error(`Funktion ${name} nicht gefunden`);
  const e = SRC.indexOf('\n  }\n', a + 1);
  return SRC.slice(a + 1, e + 4);
}
const konst = SRC.match(/\n  const KONTO_KURZ_MIN = \d+\n/);
if (!konst) throw new Error('KONTO_KURZ_MIN nicht gefunden');
const ctx = { tvSymbolWurzel: (s) => (/^MNQ/.test(String(s)) ? 'MNQ' : 'NQ') };
vm.createContext(ctx);
vm.runInContext([konst[0], fn('hedgeKontoPasst'), fn('kontoTextBezug'), fn('kontoTextEindeutig'), fn('kontoKlebtBalance'), fn('hedgeMasterWegEntscheid'),
  'this.bez = kontoTextBezug; this.eind = kontoTextEindeutig; this.bal = kontoKlebtBalance; this.weg = hedgeMasterWegEntscheid;'].join('\n'), ctx);
const { bez, eind, bal, weg } = ctx;

const fehler = [];
const ok = (b, t) => { if (!b) fehler.push(t); };

// Kennungen (Form wie echt, Ziffern erfunden)
const TFY = 'FTDFYSLX150000000052', TFY_ANDERS = 'FTDFYSLX150000001189';         // Tradeify 20-stellig, Anfang je Konto verschieden
const TDF = 'TDFYSL150000000000';                                                  // 18-stellig, nicht gekürzt
const APX1 = 'PAAPEX60000000000001', APX5 = 'PAAPEX60000000000005';                // Apex: alle Konten eines Users beginnen gleich
const KURZ_TFY = 'FTDFYSLX1500000000', KURZ_APX = 'PAAPEX600000000000', KLEBT_TDF = 'TDFYSL150000000000156';

// 1) Bezug
ok(bez(TFY, TFY) === 'ja', 'volle ID = ja');
ok(bez(`${TFY} 151,407.70 USD`, TFY) === 'ja', 'volle ID mit Balance = ja');
ok(bez(KURZ_TFY, TFY) === 'kurz', `Tradeify gekürzt: ${bez(KURZ_TFY, TFY)}`);
ok(bez(`${KURZ_TFY}… 151,407.70 USD`, TFY) === 'kurz', 'Umschalter-Text mit „…" = kurz');
ok(bez(KURZ_TFY.toLowerCase(), TFY) === 'kurz', 'Groß/klein egal');
ok(bez(KLEBT_TDF, TDF) === 'klebt', `angeklebte Balance: ${bez(KLEBT_TDF, TDF)}`);
ok(bez(`${TDF}1569`, TDF) === '', '4 angeklebte Ziffern = kein Bezug (keine Balance-Ziffern mehr)');
ok(bez(`${TDF}X`, TDF) === '', 'angeklebter Buchstabe = kein Bezug');
ok(bez(KURZ_APX, APX1) === 'kurz' && bez(KURZ_APX, APX5) === 'kurz', 'Apex-Anfang passt auf beide Konten');
ok(bez('FTDFYSLX15', TFY) === '', 'Anfang < 12 Zeichen = kein Bezug');
ok(bez(KURZ_TFY, TFY_ANDERS) === '', 'anderes Tradeify-Konto = kein Bezug');
ok(bez(TFY_ANDERS, TFY) === '', 'fremde volle ID = kein Bezug');
ok(bez('', TFY) === '' && bez(KURZ_TFY, '') === '', 'leer = kein Bezug');

// 2) Eindeutig im Login
ok(eind(KURZ_TFY, TFY, [TFY, TFY_ANDERS, TDF]) === true, 'Tradeify-Anfang eindeutig');
ok(eind(KURZ_APX, APX1, [APX1, APX5]) === false, 'Apex-Anfang NIE eindeutig');
ok(eind(KURZ_APX, APX1, [APX1]) === true, 'Apex allein im Login = eindeutig');
ok(eind(KLEBT_TDF, TDF, [TDF, TFY]) === true, 'angeklebt eindeutig');
ok(eind(KLEBT_TDF, TDF, [TDF, `${TDF}1`]) === false, 'angeklebt, aber ein Konto „ID+1" existiert → nicht eindeutig');
ok(eind(KURZ_TFY, TFY, []) === true, 'ohne Kontoliste eindeutig (Aufrufer verlangt bei „kurz" zusätzlich den Beleg)');

// 3) Angeklebte Ziffern = Anfang der Balance (Prüfer S2: sonst passte ein nicht erfasstes Konto „ID + Ziffern")
ok(bal(KLEBT_TDF, TDF, [156981.2, null]) === true, 'Balance 156,981.20 → „156" passt');
ok(bal(KLEBT_TDF, TDF, [null, 156400]) === true, 'Equity statt Balance passt auch');
ok(bal(KLEBT_TDF, TDF, [155981.2, 155500]) === false, 'Balance 155,981 → „155" ≠ „156"');
ok(bal(`${TDF}1`, TDF, [1056981]) === true, 'Balance 1,056,981 → „1" passt');
ok(bal(`${TDF}15`, TDF, [156981.2]) === false, '„15" ≠ Tausender-Gruppe „156"');
ok(bal(KLEBT_TDF, TDF, [null, null]) === false && bal(KLEBT_TDF, TDF, []) === false, 'ohne Balance nie');

// 4) Hedge-Schließ-Entscheid: Konto nur mit Beweis (kontoBewiesen = readerKontoPasst des Aufrufers)
const basis = { liste: [], positionenOk: true, alterMs: 500, sekundenSeitOpen: 600, wurzel: 'NQ', richtung: 'buy', kontoPlan: TDF,
  kontoAktiv: KLEBT_TDF, kontenAnzahl: 99, kontoStabilMs: 120000, leerSeitMs: 40000, schnell: true, gesehen: true };
ok(weg(basis) === false, 'angeklebt OHNE kontoBewiesen → nie schließen (wie bisher)');
ok(weg(Object.assign({}, basis, { kontoBewiesen: true })) === true, 'angeklebt MIT kontoBewiesen, flach, Ruhe → schließen');
ok(weg(Object.assign({}, basis, { kontoBewiesen: true, liste: [{ symbol: 'NQZ6', menge_zahl: 2, richtung: 'buy' }] })) === false, 'Master offen → nie schließen');
ok(weg(Object.assign({}, basis, { kontoBewiesen: true, unterwegs: 'Puls-Order' })) === false, 'Puls unterwegs → nie schließen');
ok(weg(Object.assign({}, basis, { kontoBewiesen: true, kontoStabilMs: 1000 })) === false, 'Konto-Ruhe gilt weiter');
ok(weg(Object.assign({}, basis, { kontoBewiesen: false })) === false, 'kontoBewiesen false → wie bisher Token-Vergleich');
ok(weg(Object.assign({}, basis, { kontoAktiv: TDF })) === true, 'volle ID ohne kontoBewiesen → wie bisher');

if (fehler.length) { console.log(`FEHLER (${fehler.length}):\n - ` + fehler.join('\n - ')); process.exit(1); }
console.log('OK — gekürzte/angeklebte Kontotexte: Bezug, Eindeutigkeit, Balance-Ziffern, Schließ-Entscheid');
