// Selbsttest Feed-Tab-Selbstheilung des Userscripts (0.8.8, 26.09.2026) — ohne Node, mit JavaScriptCore des Macs:
//   osascript -l JavaScript tv-reader/selftest_userscript_feed.js [pfad/zu/tv-reader.user.js]
// Schneidet die Feed-Funktionen aus dem Userscript und prueft sie mit nachgebauten sessionStorage/localStorage/location.
function run(argv) {
ObjC.import("Foundation");
var pfad = (argv && argv[0]) || "tv-reader/tv-reader.user.js";
var src = $.NSString.stringWithContentsOfFileEncodingError(pfad, 4, null).js;
if (!src) return "FEHLER: " + pfad + " nicht lesbar";
function stueck(von, bis) { var i = src.indexOf(von), j = src.indexOf(bis, i); if (i < 0 || j < 0) throw "fehlt " + von; return src.slice(i, j); }
var code = [
  stueck("const RX_KONTO_ECHT", "function liesKonto"),
  stueck("const RX_KURS_SYMBOL", "function kursZahlText"),
  stueck("function cmeOffen", "// Letzte Maus"),
  stueck("const FEED_MARKE_MS", "// Gesamtbild fuer den Payload"),
].join("\n");
var aus = [];
var harness = "var store={}, sess={}; var sessionStorage={getItem:function(k){return k in sess?sess[k]:null},setItem:function(k,v){sess[k]=String(v)}};" +
  "var localStorage={getItem:function(k){return k in store?store[k]:null},setItem:function(k,v){store[k]=String(v)}};" +
  "var location={origin:'https://www.tradingview.com',pathname:'/chart/AbC123/',href:''};" +
  "var PULS_CHROME=false; var kontoMerk={text:null,ts:0}; var kursMerk={}; var letzteEingabeMs=0; var EINGABE_RUHE_MS=120000;" +
  "var geplant=[]; function setTimeout(f){ geplant.push(f); }" +
  "var knoepfe=[]; var sichtbar=function(){return true}; var window={innerHeight:1000}; var document={getElementById:function(){return null},querySelectorAll:function(){return knoepfe}};" + code +
  "; return {feedPflegen:feedPflegen, feedHeilen:feedHeilen, tabRolle:tabRolle, feedMarkiert:feedMarkiert, kontoAngemeldet:kontoAngemeldet," +
  " kontoIstEcht:kontoIstEcht, kontoNrAus:kontoNrAus, kontoNummerAmSchalter:kontoNummerAmSchalter, knoepfe:knoepfe," +
  " sess:sess, store:store, kontoMerk:kontoMerk, kursMerk:kursMerk, location:location, geplant:geplant, setEingabe:function(t){letzteEingabeMs=t}, setPuls:function(b){PULS_CHROME=b}};";
var h = new Function(harness)();
function check(b, t) { aus.push((b ? "OK   " : "FEHL ") + t); }
var T = Date.parse("2026-09-28T15:00:00Z");   // Montag, Markt offen
var mnq = {symbol:"MNQ1!", text:"30,700"};
// 10 min feed ohne Konto → markiert
h.feedPflegen(T, mnq); check(!h.feedMarkiert(), "nach 0 min nicht markiert");
h.feedPflegen(T + 600000, mnq); check(h.feedMarkiert(), "nach 10 min Feed markiert");
// Layout lernen (MNQ tickt)
h.kursMerk.MNQ = {text:"1", geaendert_ms: T + 600000};
h.feedPflegen(T + 600000, mnq);
var lay = JSON.parse(h.store.prophos_feed_layout || "null");
check(lay && lay.url === "https://www.tradingview.com/chart/AbC123/" && lay.symbol === "MNQ1!", "Layout + Symbol gelernt");
// Login im Feed: Rolle bleibt feed
h.kontoMerk.text = "PAAPEX6416990000008"; h.kontoMerk.ts = T + 600000;
check(h.tabRolle(T + 600001) === "feed" && h.kontoAngemeldet(T + 600001), "Login im markierten Feed-Tab → Rolle feed, Login erkannt");
// falsches Symbol, MNQ tickt weiter
var nq = {symbol:"NQ1!", text:"30,900"};
var t0 = T + 700000; h.kursMerk.MNQ.geaendert_ms = t0;
check(!h.feedHeilen(t0, nq), "falsches Symbol: sofort noch nichts");
h.kursMerk.MNQ.geaendert_ms = t0 + 119000;
check(!h.feedHeilen(t0 + 119000, nq), "… nach 119 s noch nichts");
h.setEingabe(t0 + 100000);
check(!h.feedHeilen(t0 + 121000, nq), "… nach 121 s, aber Eingabe vor 21 s → nichts");
h.setEingabe(0);
check(h.feedHeilen(t0 + 121000, nq) && h.geplant.length === 1, "… nach 121 s ohne Eingabe → zurück zum Layout");
h.geplant[0](); check(h.location.href === "https://www.tradingview.com/chart/AbC123/", "Ziel = gelernte Layout-URL");
check((h.sess.prophos_reader_reload_grund || "").indexOf("NQ1! statt MNQ1!") >= 0, "Grund landet im Payload");
check(!h.feedHeilen(t0 + 300000, nq), "Sperre: nicht zweimal binnen 10 min");
// kein MNQ-Kurs, Symbol richtig
h.kursMerk.MNQ.geaendert_ms = t0 + 700000;
var t1 = t0 + 900000;
check(h.feedHeilen(t1, mnq) && (h.sess.prophos_reader_reload_grund || "").indexOf("kein neuer MNQ-Kurs") >= 0, "kein MNQ-Kurs > 2 min bei richtigem Symbol → heilen");
// Markt zu (Samstag) → nie
var sa = Date.parse("2026-09-26T15:00:00Z");
check(!h.feedHeilen(sa, nq) && !h.feedHeilen(sa + 3600000, nq), "Markt zu → nie heilen");
// nicht markierter Tab (Handels-Tab mit Konto) → nie
var h2 = new Function(harness)();
h2.kontoMerk.text = "TDFYSL150800892182"; h2.kontoMerk.ts = T;
h2.feedPflegen(T, mnq); h2.feedPflegen(T + 700000, mnq);
check(!h2.feedMarkiert() && h2.tabRolle(T + 1000) === "broker" && !h2.feedHeilen(T + 900000, nq), "Handels-Tab mit Konto: nie markiert, nie geheilt");
// 0.9.1 (Befund Moritz 01.10.2026): Puls-Chrome-Modus — alte Feed-Markierung zaehlt nicht, nur das Konto
var h3 = new Function(harness)();
h3.sess.prophos_feed_tab = "1"; h3.kontoMerk.text = "TDFYTEST0000000001"; h3.kontoMerk.ts = T;
check(h3.tabRolle(T + 1000) === "feed", "ohne Puls-Modus: markierter Tab bleibt feed (wie 0.8.8)");
h3.setPuls(true);
check(h3.tabRolle(T + 1000) === "broker", "Puls-Modus: markierter Tab mit Konto → broker");
// 0.9.8 (05.10.2026): Kontonummern mit nur 4 Endziffern (mindestens 10 Grossbuchstaben davor) — nur erfundene Kennungen
var h4 = new Function(harness)();
var K4 = "FNFTCHMUSTERMUSTERAB0000";   // 20 Buchstaben + 4 Ziffern
check(h4.kontoIstEcht(K4), "4 Endziffern: Kennung zaehlt als Konto");
h4.kontoMerk.text = K4; h4.kontoMerk.ts = T;
check(h4.kontoAngemeldet(T + 1000) && h4.tabRolle(T + 1000) === "broker", "4 Endziffern: kontoAngemeldet, Rolle broker");
check((h4.kontoNrAus(K4 + "USD") || [])[0] === K4 && (h4.kontoNrAus(K4 + K4 + "USD") || [])[0] === K4, "4 Endziffern: Nummer aus dem Knopf-Text ohne Leerzeichen (auch doppelt)");
var RX_ALT_ECHT = /[A-Z]{2,}[A-Z0-9_-]*\d{5,}/i, RX_ALT_NR = /[A-Z]{2,}[A-Z0-9_-]*?\d{5,}/i;   // Regeln bis 0.9.7
var bisher = ["TDFYTEST0000000001", "tdfytest0000000001", "APEX-000000-01", "TDFYTEST0000000001USD", "ABCDEFGHIJ12345", "MFFUTEST00000", "XY_00000-1"];
var gleich = bisher.every(function (t) { var a = t.match(RX_ALT_NR), n = h4.kontoNrAus(t); return RX_ALT_ECHT.test(t) && h4.kontoIstEcht(t) && a && n && a[0] === n[0] && a.index === n.index; });
check(gleich, "5+ Endziffern: erkannt und Nummer bitgleich wie bis 0.9.7");
var nie = ["NQZ2026", "MNQZ2026", "MNQZ26", "NQ1!", "MNQ1! 30,700", "Positions", "Paper Trading", "Account Manager", "ABCDEFGHI1234", "ABCDEFGHIJ123", "abcdefghijkl1234", "Orders 1234", "TRADOVATE 2026"];
check(nie.every(function (t) { return !h4.kontoIstEcht(t) && !h4.kontoNrAus(t); }), "Kontrakte, Reiter, Paper Trading, 9 Buchstaben, 3 Ziffern, Kleinbuchstaben: nie Konto");
function knopf(text) { return { textContent: text, closest: function () { return null; }, contains: function () { return false; }, getBoundingClientRect: function () { return { top: 800, left: 10 }; } }; }
h4.knoepfe.length = 0; h4.knoepfe.push(knopf("Positions"), knopf(K4 + " " + K4 + " USD"), knopf("MNQZ2026"));
check(h4.kontoNummerAmSchalter() === K4, "Umschalter-Knopf mit 4 Endziffern → reine Kontonummer");
h4.knoepfe.length = 0; h4.knoepfe.push(knopf("TDFYTEST0000000001 TDFYTEST0000000001 USD"));
check(h4.kontoNummerAmSchalter() === "TDFYTEST0000000001", "Umschalter-Knopf mit 5+ Endziffern wie bisher");
h4.knoepfe.length = 0; h4.knoepfe.push(knopf("Positions"), knopf("NQZ2026"), knopf("Paper Trading"));
check(h4.kontoNummerAmSchalter() === "", "kein Konto-Knopf → leer");
// 0.9.10 (27.10.2026): gekuerzte Kennung ohne Ziffern (Login mit einem Konto) — erfundene Kennung
h4.knoepfe.length = 0; h4.knoepfe.push(knopf("Positions"), knopf("FNFTFAMUSTERMUSTERAB\u2026 155,365.92 USD"));
check(h4.kontoNummerAmSchalter() === "FNFTFAMUSTERMUSTERAB\u2026", "gekuerzte Kennung → Stueck mit … (nie als volle Nummer)");
check(h4.kontoIstEcht("FNFTFAMUSTERMUSTERAB\u2026") && !h4.kontoIstEcht("MNQZ2026\u2026") && !h4.kontoIstEcht("Positions\u2026")
      && !h4.kontoIstEcht("ABC\u2026 1,00 USD"), "gekuerzt zaehlt als Konto, kurze Woerter/Kontrakte mit … nie");
h4.kontoMerk.text = "FNFTFAMUSTERMUSTERAB\u2026"; h4.kontoMerk.ts = T;
check(h4.kontoAngemeldet(T + 1000), "gekuerzt: kontoAngemeldet (nicht mehr blind)");
// 0.9.12 (29.10.2026): Leer-Beweis — TradingViews generischer Text 'Nothing to show yet' zaehlt nur in der Positions-Tabelle
var codeLeer = stueck("const RX_LEER_POS", "function blindGrund");
var harnessLeer = "var leerMerkMs = 0; var document = {body:{}, getElementById:function(){return null}}; var Date = {now:function(){ leerMerkMs += 1000; return leerMerkMs; }};" + codeLeer +
  "; return {leerBeweis:leerBeweis, leerTextPasst:leerTextPasst, setDoc:function(d){ document = d; }};";
var h5 = new Function(harnessLeer)();
function el(text, kinder, tabelle) {   // Element-Attrappe: textContent, parentElement (wird verkettet), querySelector findet die Tabelle
  var e = { textContent: text, parentElement: null, querySelector: function (sel) { return (sel.indexOf("positions-table") >= 0) ? (tabelle || null) : null; } };
  (kinder || []).forEach(function (k) { k.parentElement = e; });
  return e;
}
function doc(reiter, kette) { return { body: {}, getElementById: function (id) { return id === "positions" ? reiter : null; } }; }
var tabLeer = { textContent: "Symbol Side Qty Avg Fill Price Profit Update Time Position ID Nothing to show yet. You have no open positions" };
var tabVoll = { textContent: "Symbol Side Qty Avg Fill Price Profit Update Time Position ID NQZ6 Long 3 29,947.75 -3,030.00 USD" };
function reiter(sel) { return { getAttribute: function (a) { return a === "aria-selected" ? sel : null; }, parentElement: null }; }
// Fall 1: alter Text im Panel → flach (wie bisher)
var r1 = reiter("true"); var p1 = el("Positions Orders No open positions", [r1]); h5.setDoc(doc(r1));
check(h5.leerBeweis() === true, "leerBeweis: alter Text 'No open positions' im Panel → flach");
// Fall 2: neuer Text in der Positions-Tabelle unter dem Panel → flach
var r2 = reiter("true"); var p2 = el("Positions Orders " + tabLeer.textContent, [r2], tabLeer); h5.setDoc(doc(r2));
check(h5.leerBeweis() === true, "leerBeweis: 'Nothing to show yet' in table[data-name$=positions-table] → flach");
// Fall 3: neuer Text irgendwo auf der Seite, Tabelle nicht gerendert (Panel eingeklappt) → NICHT flach
var r3 = reiter("true"); var p3 = el("Positions Orders", [r3]); var seite3 = el("Notifications log Nothing to show yet. Alerts", [p3]); h5.setDoc(doc(r3));
check(h5.leerBeweis() === false, "leerBeweis: generischer Text ausserhalb der Positions-Tabelle, keine Tabelle → nicht flach");
// Fall 4: Tabelle da, aber mit Position (Text 'Nothing to show yet' nur anderswo im Vorfahren) → NICHT flach
var r4 = reiter("true"); var p4 = el("Positions Nothing to show yet " + tabVoll.textContent, [r4], tabVoll); h5.setDoc(doc(r4));
check(h5.leerBeweis() === false, "leerBeweis: Positions-Tabelle mit Zeile, generischer Text daneben → nicht flach");
// Fall 5: ohne Tabellen-Element zaehlt der Spaltenkopf 'Position ID' im selben Vorfahren
check(h5.leerTextPasst("Symbol Side Qty Position ID Nothing to show yet", null) === true && h5.leerTextPasst("Nothing to show yet", null) === false, "leerTextPasst: ohne Tabellen-Element nur mit 'Position ID' daneben");
// Fall 6: Reiter nicht gewaehlt → nie flach
var r6 = reiter("false"); var p6 = el("Positions " + tabLeer.textContent, [r6], tabLeer); h5.setDoc(doc(r6));
check(h5.leerBeweis() === false, "leerBeweis: Reiter Positions nicht aktiv → nicht flach");
// 0.9.13 (29.10.2026): Konto-Liste aus dem offenen Umschalter — nur volle Nummern als erstes Wort, nie gekuerzt/angeklebt
var codeKonten = stueck("function kontenAusEintraegen", "// 0.9.13 ENDE kontenAusEintraegen");
var h6 = new Function("var RX_KONTO_KURZ=" + stueck("const RX_KONTO_KURZ = ", ";\n").replace("const RX_KONTO_KURZ = ", "") + ";" +
  "var h4 = arguments[0]; var kontoIstEcht = h4.kontoIstEcht, kontoNrAus = h4.kontoNrAus;" + stueck("function kontoEntdoppeln", "// 0.9.2: Konto-Umschalter") + codeKonten + "; return kontenAusEintraegen;")(h4);
var kl = h6([{ text: 'PAAPEX6843320000001 158,491.44 USD' }, { text: 'PAAPEX6843320000002 157,474.50 USD' }, { text: 'FTDFYSLX1502279877… 150,000.00 USD' },
  { text: 'TDFYSL150000000000156,981.20USD' }, { text: 'Paper Trading' }, { text: 'PAAPEX6843320000001 PAAPEX6843320000001 158,491.44 USD' }, { text: 'TDFYTEST0000000001 TDFYTEST0000000001 USD' }],
  'PAAPEX684332000000… 158,491.44 USD');
check(JSON.stringify(kl.map(function (k) { return k.name; })) === JSON.stringify(['PAAPEX6843320000001', 'PAAPEX6843320000002', 'TDFYTEST0000000001']),
      "kontenAusEintraegen: volle Nummern, Dubletten einmal, gekuerzt/angeklebt/Paper raus");
check(kl.every(function (k) { return k.quelle === 'dropdown'; }) && h6([{ text: 'X' }], 'TDFYSL150577127231 157,021.20 USD')[0].quelle === 'umschalter',
      "kontenAusEintraegen: quelle dropdown/umschalter (voller Umschalter-Name zaehlt allein)");
check(h6([], 'FTDFYSLX1502279877… 150,000.00 USD').length === 0 && h6(null, '').length === 0, "kontenAusEintraegen: gekuerzter Umschalter allein → nichts, leer → nichts");
check(h6([{ text: 'EXPRESS-V2-679005-57119155 150,000.00 USD' }], 'EXPRESS-V2-679005-57…').length === 1 && h6([{ text: 'FNFTFAMUSTERMUSTERAB1234 100,000.00 USD' }], 'FNFTFAMUSTERMUSTERAB…')[0].name === 'FNFTFAMUSTERMUSTERAB1234',
      "kontenAusEintraegen: Topstep-Form mit Bindestrichen und 4-Endziffern-Form zaehlen");
check(h6([{ text: 'QQQ261218C00500000' }, { text: 'SPXW261218P05000000' }], 'PAAPEX684332000000… 155,407.14 USD').length === 0,
      "kontenAusEintraegen: fremde offene Liste (Symbolsuche) → nichts, aktives Konto steht nicht drin");
check(h6([{ text: 'PAAPEX6843320000001 USD' }], '').length === 0, "kontenAusEintraegen: ohne Umschalter-Text keine Liste (nicht beweisbar Konto-Liste)");
// 0.10.0 LADER: alle Wege mit nachgebauten GM-Funktionen (setTimeout wird nur gemerkt, kein Netz)
var laderSrc = src.slice(src.indexOf("(function prophosLader()"));
function laderLauf(o) {
  var spur = { kern: 0, info: null, gesetzt: [], netz: [] };
  var store = { prophos_kern_v1: o.merk || null };
  var fn = new Function("GM_getValue", "GM_setValue", "GM_xmlhttpRequest", "GM_registerMenuCommand", "unsafeWindow", "prophosKern", "setTimeout", "Function", "window",
    laderSrc);
  var Fn = o.evalGesperrt ? function () { throw new Error("EvalError: Refused to evaluate a string as JavaScript"); } : Function;
  fn(function (k, d) { return k in store ? store[k] : d; }, function (k, v) { store[k] = v; spur.gesetzt.push(v); },
     function (req) { spur.netz.push(req); }, function () {}, {}, function () { spur.kern++; spur.info = arguments[5]; },
     function () {}, Fn, {});
  spur.store = store; return spur;
}
var L1 = laderLauf({});
check(L1.kern === 1 && L1.info.quelle === "eingebaut" && L1.info.eval === true && L1.info.laeuft === "0.10.1", "Lader: nichts gemerkt → eingebaute Fassung läuft genau einmal");
var gelaufen = 0;
var L2 = laderLauf({ merk: { version: "0.10.2", code: "globalThis.__laderInfo = PROPHOS_LADER;", sha: "x" } });
var i2 = globalThis.__laderInfo;
check(L2.kern === 0 && i2 && i2.quelle === "nachgeladen" && i2.laeuft === "0.10.2", "Lader: neuere gemerkte Fassung läuft statt der eingebauten (nie beide)");
var L3 = laderLauf({ merk: { version: "0.10.2", code: "throw new Error('kaputt')", sha: "x" } });
check(L3.kern === 1 && L3.info.quelle === "eingebaut" && L3.store.prophos_kern_v1 === null && /warf/.test(L3.info.fehler), "Lader: gemerkte Fassung wirft → eingebaute läuft, Merker gelöscht");
var L4 = laderLauf({ merk: { version: "0.10.2", code: "}{ kein js", sha: "x" } });
check(L4.kern === 1 && L4.store.prophos_kern_v1 === null && /nicht lesbar/.test(L4.info.fehler), "Lader: gemerkte Fassung nicht lesbar → eingebaute läuft, Merker gelöscht");
var L3r = laderLauf({ merk: { version: "0.10.2", code: "unsafeWindow.__prophosKernAn = true; throw new Error('halb gestartet')", sha: "x" } });
check(L3r.info.quelle === "blind (Riegel)" && /Riegel/.test(L3r.info.fehler) && L3r.store.prophos_kern_v1 === null,
      "Lader: nachgeladener Kern setzt den Riegel und wirft → eingebaute Fassung startet NICHT daneben (blind statt doppelt), Merker gelöscht");
var L5 = laderLauf({ merk: { version: "0.9.12", code: "PROPHOS_LADER.x = 1;", sha: "x" } });
check(L5.kern === 1 && L5.info.quelle === "eingebaut", "Lader: gemerkte ÄLTERE Fassung wird nie gestartet");
var L6 = laderLauf({ evalGesperrt: true, merk: { version: "0.10.2", code: "PROPHOS_LADER.x = 1;", sha: "x" } });
check(L6.kern === 1 && L6.info.eval === false && L6.info.quelle === "eingebaut" && /eval gesperrt/.test(L6.info.fehler) && L6.store.prophos_kern_v1 !== null,
      "Lader: eval gesperrt (MV3) → eingebaute Fassung, nichts nachgeladen");
var fehl = aus.filter(function (z) { return z.indexOf("FEHL") === 0; }).length;
return aus.join("\n") + "\n" + (fehl ? "FEHLER (" + fehl + ")" : "alle Tests bestanden");
}
