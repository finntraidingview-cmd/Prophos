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
var harnessLeer = "var leerMerkMs = 0, schritt = 1000; var kontoMerk = {text: 'KONTO-A', ts: 0}; function kontoNrAus(t) { return String(t).match(/^[A-Z][A-Z-]*[0-9]{5,}/); } var document = {body:{}, getElementById:function(){return null}}; var Date = {now:function(){ leerMerkMs += schritt; return leerMerkMs; }};" + codeLeer +
  "; return {leerBeweis:leerBeweis, leerStrukturPasst:leerStrukturPasst, uhr:function(){ return leerMerkMs; }, setSchritt:function(n){ schritt = n; }, setKonto:function(k){ kontoMerk.text = k; }, leerTextPasst:leerTextPasst, setDoc:function(d){ document = d; }};";
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
// 0.10.3 (30.10.2026): dritte Leer-Ansicht „Make …" mit Buy/Sell-Knoepfen — nur in der Positions-Tabelle, direkt nach „Position ID", ohne Datenzelle
function td(label, text) { return { textContent: text, getAttribute: function (a) { return a === "data-label" ? label : null; } }; }
// td-Zellen: ohne Angabe der Text hinter dem LETZTEN Spaltenkopf „Position ID" als eine Leer-Zelle (Form der echten Leer-Ansicht)
function restNachKopf(text) { var m, re = /positions?[\s-]*id/gi, e = -1; while ((m = re.exec(text))) e = m.index + m[0].length; return e < 0 ? "" : text.slice(e); }
function tabelle(text, zellen, zeilen, tds) {
  var r = tds || (restNachKopf(text).trim() ? [{ textContent: restNachKopf(text) }] : []);
  return { textContent: text, querySelectorAll: function (sel) { return sel === "td[data-label]" ? (zellen || []) : sel === "tr" ? (zeilen || []) : sel === "td" ? r : []; } };
}
function tr(texte) { return { querySelectorAll: function (sel) { return sel === "td" ? texte.map(function (t) { return { textContent: t }; }) : []; } }; }
var KOPF = "SymbolSideQtyAvg Fill PriceProfitUpdate TimePosition ID";
var tabMake = tabelle(KOPF + "Make your first trade SellBuy");
var r7 = reiter("true"); var p7 = el("Positions Orders " + tabMake.textContent, [r7], tabMake); h5.setDoc(doc(r7));
check(h5.leerBeweis() === true, "leerBeweis: 'Make …' direkt nach 'Position ID' in der Positions-Tabelle → flach");
check(h5.leerTextPasst("x", tabelle(KOPF + "Make ")) === true, "leerTextPasst: abgeschnittener Inventar-Text '…Position IDMake ' → flach");
check(h5.leerTextPasst(KOPF + "Make your first trade", null) === false, "leerTextPasst: 'Make' ohne Tabellen-Element → nicht flach");
check(h5.leerTextPasst("x", tabelle(KOPF + "MNQZ6Long129,086.50-8.50USD4470324 Make", [td("Symbol", "MNQZ6"), td("Position ID", "4470324")])) === false,
      "leerTextPasst: Datenzeile zwischen Kopf und 'Make' → nicht flach");
check(h5.leerTextPasst("x", tabelle(KOPF + "Make ", [td("Symbol", "MNQZ6")])) === false, "leerTextPasst: 'Make' direkt nach Kopf, aber Symbol-Zelle mit Text → nicht flach");
check(h5.leerTextPasst("x", tabelle(KOPF + "Make ", [td("Symbol", " "), td("Update Time", "")])) === true, "leerTextPasst: leere Zellen stoeren nicht");
check(h5.leerTextPasst("x", tabelle(KOPF)) === false, "leerTextPasst: nur Kopf → nicht flach");
check(h5.leerTextPasst("x", { textContent: KOPF + "Make ", querySelectorAll: function () { throw "kaputt"; } }) === false, "leerTextPasst: querySelectorAll wirft → nicht flach (fail-closed)");
var r8 = reiter("false"); var p8 = el("Positions " + tabMake.textContent, [r8], tabMake); h5.setDoc(doc(r8));
check(h5.leerBeweis() === false, "leerBeweis: 'Make …' bei nicht gewaehltem Reiter Positions → nicht flach");
// 0.10.4 (30.10.2026): Leer-Beweis ohne festen Text — Aufbau der Positions-Tabelle; geschuetzte Leerzeichen in den Texten
check(!!h5.leerStrukturPasst(tabelle(KOPF + "Nothing here yet. Place an order to get started")) === true, "Struktur: unbekannter Leer-Text nach dem Kopf → flach");
check(!!h5.leerStrukturPasst(tabelle(KOPF + "Nothing to show yet. You")) === true, "Struktur/NBSP: 'Nothing to show yet' mit U+00A0 → flach");
check(h5.leerTextPasst("Positions Nothing to show yet", tabelle(KOPF + "Nothing to show yet")) === true, "RX_LEER_NEU trifft U+00A0");
check(!!h5.leerStrukturPasst(tabelle("SymbolSideQtyAvg Fill PriceProfitUpdate TimePositions-IDKeine Positionen")) === true, "Struktur: deutscher Kopf 'Positions-ID' → flach");
check(!!h5.leerStrukturPasst(tabelle(KOPF + "Loading positions")) === false, "Struktur: 'Loading' → nicht flach");
check(!!h5.leerStrukturPasst(tabelle(KOPF + "Positionen werden geladen")) === false, "Struktur: 'geladen' → nicht flach");
check(!!h5.leerStrukturPasst(tabelle(KOPF + "Connecting to broker")) === false && !!h5.leerStrukturPasst(tabelle(KOPF + "Something went wrong, error 500")) === false,
      "Struktur: Verbinden/Fehler → nicht flach");
check(!!h5.leerStrukturPasst(tabelle(KOPF + "Bitte warten…")) === false && !!h5.leerStrukturPasst(tabelle(KOPF + "Please wait...")) === false, "Struktur: Ellipse/warten → nicht flach");
check(!!h5.leerStrukturPasst(tabelle(KOPF)) === false && !!h5.leerStrukturPasst(tabelle(KOPF + " 12 ")) === false, "Struktur: kein Wort-Text unter dem Kopf → nicht flach");
check(!!h5.leerStrukturPasst(tabelle("Symbol Side Qty Profit Nothing here")) === false, "Struktur: ohne Spaltenkopf Position ID → nicht flach");
check(!!h5.leerStrukturPasst(tabelle(KOPF + "MNQZ6Long129,086.50-8.50USD4470324", [td("Symbol", "MNQZ6"), td("Qty", "1"), td("Position ID", "4470324")])) === false,
      "Struktur: Datenzeile mit Text → nicht flach");
check(!!h5.leerStrukturPasst(tabelle(KOPF + "Nothing here", [td("Update Time", "00:16:07")])) === false, "Struktur: irgendeine data-label-Zelle mit Text → nicht flach");
check(!!h5.leerStrukturPasst(tabelle(KOPF + "Nothing here", [td("Symbol", "  "), td("Update Time", "")])) === true, "Struktur: nur leere data-label-Zellen → flach");
check(!!h5.leerStrukturPasst({ textContent: KOPF + "Nothing here", querySelectorAll: function () { throw "kaputt"; } }) === false, "Struktur: querySelectorAll wirft → nicht flach");
check(!!h5.leerStrukturPasst(tabelle(KOPF + "MNQZ6Long129,086.50-8.50USD4470324", [], [tr(["MNQZ6", "Long", "1", "29,086.50", "-8.50USD", "", "4470324"])])) === false,
      "Struktur: Datenzeile OHNE data-label (mehrere Zellen mit Text) → nicht flach");
check(!!h5.leerStrukturPasst(tabelle(KOPF + "Make your first trade SellBuy", [], [tr(["Make your first trade SellBuy"])])) === true, "Struktur: eine Leer-Zelle in der Zeile → flach");
check(!!h5.leerStrukturPasst({ textContent: KOPF + "Nothing here", querySelectorAll: function (s) { return s === "tr" ? [{ querySelectorAll: function () { throw "kaputt"; } }] : []; } }) === false,
      "Struktur: Zeile nicht lesbar → nicht flach");
// Pruefer S2 30.10.2026: nur ganze Leer-Phrasen am Anfang — Zustandstexte mit Einzelwoertern (yet/keine/empty/leer/nothing) nie leer
["Keine Berechtigung", "Keine Daten", "Account not ready yet", "Positions are not available yet", "Broker not authorized yet",
 "Empty response", "Market closed — nothing to show", "Market closed - nothing to show", "Leer", "Noch nicht verbunden", "Not yet loaded",
 "Nothing", "No access", "Keine Verbindung zum Broker", "Positions empty",
 "No position data available", "No position information", "No position", "No positions — permission denied", "Nothing here. Account restricted",
 "Nothing here, broker not supported", "No positions available for this broker", "Keine Positionen verfügbar", "Nothing to show: access disabled",
 "Keine offenen Positionen (Zugriff verweigert)"].forEach(function (t) {
  check(!!h5.leerStrukturPasst(tabelle(KOPF + t)) === false, "Struktur: Zustandstext '" + t + "' → nicht flach");
});
["Nothing to show yet. You have no open positions", "Nothing here yet", "No open positions", "No positions", "Make your first trade",
 "Keine offenen Positionen", "Noch keine Positionen"].forEach(function (t) {
  check(!!h5.leerStrukturPasst(tabelle(KOPF + t)) === true, "Struktur: Leer-Phrase '" + t + "' → flach (nach zweiter Lesung)");
});
// Pruefung 30.10.2026: Positiv-Liste statt Sperrliste, keine Ziffer, Zeilen ohne tr/td
["Something went wrong", "Request failed", "Log in to see positions", "Session expired", "Offline", "Timeout", "Fetching positions",
 "Positionen abrufen", "Aktualisieren", "Please reconnect", "Update Time", "Account Summary"].forEach(function (t) {
  check(!!h5.leerStrukturPasst(tabelle(KOPF + t)) === false, "Struktur: '" + t + "' → nicht flach");
});
check(!!h5.leerStrukturPasst(tabelle(KOPF + "MNQZ6 Long 1 29,086.50 -8.50 USD 4470324 Nothing")) === false,
      "Struktur: Datenzeile als div-Grid (ohne tr/td/data-label) mit Ziffern → nicht flach");
check(!!h5.leerStrukturPasst(tabelle(KOPF + "Nothing to show yet 1")) === false, "Struktur: irgendeine Ziffer im Leer-Block → nicht flach");
check(!!h5.leerStrukturPasst(tabelle("SymbolSideQtyPosition IDAvg Fill PriceProfitUpdate Time", [], [], [])) === false,
      "Struktur: Spalten umgestellt, Tabelle laedt (nur Kopf-Namen nach Position ID) → nicht flach");
check(!!h5.leerStrukturPasst(tabelle("SymbolSideQtyPosition IDAvg Fill PriceProfitUpdate TimeNothing to show yet")) === false,
      "Struktur: Spalten umgestellt (Phrase nicht direkt nach Position ID) → kein Struktur-Beweis (fail-closed)");
check(h5.leerTextPasst("x", tabelle("SymbolPosition IDMake your first trade")) === true, "RX_LEER_MAKE trifft U+00A0 im Kopf");
check(h5.leerTextPasst("x", tabelle(KOPF + "Nothing here yet")) === false, "leerTextPasst allein kennt den Struktur-Beweis nicht (nur ueber leerBeweis mit zweiter Lesung)");
var tabNeu = tabelle(KOPF + "Nothing here yet");
var r9 =reiter("true"); var p9 = el("Positions Orders " + tabNeu.textContent, [r9], tabNeu); h5.setDoc(doc(r9));
h5.setSchritt(1000);
check(h5.leerBeweis() === false, "Struktur/leerBeweis: ERSTE Lesung → noch nicht flach");
check(h5.leerBeweis() === true, "Struktur/leerBeweis: dieselbe Lesung 1 s spaeter → flach");
// Zweite Lesung zu frueh (Uhr 0,2 s, Merkzeit 0,15 s ueberschritten) → noch nicht; ab 0,4 s → flach
var tabNeu2 = tabelle(KOPF + "Nothing here at all");
var r11 = reiter("true"); var p11 = el("Positions " + tabNeu2.textContent, [r11], tabNeu2); h5.setDoc(doc(r11));
h5.setSchritt(200);
check(h5.leerBeweis() === false && h5.leerBeweis() === false && h5.leerBeweis() === true, "Struktur/leerBeweis: erst ab ≥ 0,4 s nach der ersten gleichen Lesung flach");
// Aufbau: erst nur Kopf (kein Leer-Block) → nie flach; danach Leer-Block → wieder erste Lesung
var tabKopf = tabelle(KOPF); var r12 = reiter("true"); var p12 = el("Positions " + KOPF, [r12], tabKopf); h5.setDoc(doc(r12));
h5.setSchritt(1000);
check(h5.leerBeweis() === false && h5.leerBeweis() === false, "Struktur/leerBeweis: Tabelle laedt (Kopf da, Zeilen/Leer-Block noch nicht) → nie flach");
var tabLaed = tabelle(KOPF + "Loading"); var r13 = reiter("true"); var p13 = el("Positions " + tabLaed.textContent, [r13], tabLaed); h5.setDoc(doc(r13));
check(h5.leerBeweis() === false && h5.leerBeweis() === false, "Struktur/leerBeweis: 'Loading' zweimal → nie flach");
var r14 = reiter("true"); var p14 = el("Positions " + tabNeu.textContent, [r14], tabNeu); h5.setDoc(doc(r14));
check(h5.leerBeweis() === false, "Struktur/leerBeweis: nach dem Laden zuerst wieder nur ERSTE Lesung");
check(h5.leerBeweis() === true, "Struktur/leerBeweis: zweite gleiche Lesung → flach");
// Kontowechsel mit demselben Leer-Text → neue erste Lesung
h5.setKonto("KONTO-B");
check(h5.leerBeweis() === false && h5.leerBeweis() === true, "Struktur/leerBeweis: Kontowechsel, gleicher Leer-Text → erst wieder erste Lesung");
h5.setKonto("KONTO-A");
// Text wechselt zwischen den Lesungen → neue erste Lesung
var tabNeu3 = tabelle(KOPF + "Nothing here right now"); var r15 = reiter("true"); var p15 = el("Positions " + tabNeu3.textContent, [r15], tabNeu3); h5.setDoc(doc(r15));
check(h5.leerBeweis() === false, "Struktur/leerBeweis: anderer Leer-Text → wieder erste Lesung");
var r10 = reiter("false"); var p10 = el("Positions " + tabNeu.textContent, [r10], tabNeu); h5.setDoc(doc(r10));
check(h5.leerBeweis() === false && h5.leerBeweis() === false, "Struktur/leerBeweis: Reiter nicht gewaehlt → nie flach");
// alter Text bleibt sofort gueltig (keine zweite Lesung noetig, wie bis 0.10.3)
var r16 = reiter("true"); var p16 = el("Positions Orders No open positions", [r16]); h5.setDoc(doc(r16));
check(h5.leerBeweis() === true, "leerBeweis: 'No open positions' weiter sofort flach");
// Pruefer S2 30.10.2026 (Stopp 335ed221): KEIN freier Leer-Text — auch nicht nach einer gerade gesehenen Position; Zustandstexte nie leer
["Updating", "Refreshing", "Initializing", "Pending", "Broker unreachable", "Session closed", "Maintenance in progress", "Please refresh the page",
 "Trading halted", "Account suspended", "Market closed", "Unauthorized", "Positions hidden", "Server busy", "Paused", "Broker not responding",
 "Reauthorize", "Your recent orders show up below"].forEach(function (t) {
  check(!!h5.leerStrukturPasst(tabelle(KOPF + t)) === false, "Struktur: Zustandstext '" + t + "' → nie leer");
  check(!!h5.leerStrukturPasst(tabelle(KOPF + t, [], [tr([t])], [{ textContent: t }])) === false, "Struktur (td/tr): Zustandstext '" + t + "' → nie leer");
});
h5.setSchritt(1000); h5.setKonto("KONTO-A");
var tabAkt = tabelle(KOPF + "Updating"); var rU = reiter("true"); var pU = el("Positions " + tabAkt.textContent, [rU], tabAkt); h5.setDoc(doc(rU));
check(h5.leerBeweis() === false && h5.leerBeweis() === false && h5.leerBeweis() === false, "leerBeweis: 'Updating' dreimal → nie flach");
check(!!h5.leerStrukturPasst(tabelle(KOPF + "Your trading activity will appear here")) === true && !!h5.leerStrukturPasst(tabelle(KOPF + "Activity will appear here")) === true,
      "Phrase: '(Your trading) activity will appear here' → flach (nach zweiter Lesung)");
var tabAct = tabelle(KOPF + "Your trading activity will appear here"); var rA = reiter("true"); var pA = el("Positions x", [rA], tabAct); h5.setDoc(doc(rA));
check(h5.leerBeweis() === false && h5.leerBeweis() === true, "leerBeweis: Simons Leer-Text → erste Lesung nein, zweite ja");
// Pruefung 30.10.2026 zu 0.10.5: Kopf-Namen hinter „Position ID" (th) zaehlen nie als Leer-Text
var tabTh = tabelle("SymbolSideQtyPosition IDAvg Fill PriceProfitUpdate Time", [], [], []);
var rTh = reiter("true"); var pTh = el("Positions x", [rTh], tabTh); h5.setDoc(doc(rTh));
check(h5.leerBeweis() === false && h5.leerBeweis() === false, "Spalten umgestellt, nur Kopf (th) → nie flach");
// zweite Lesung: Schluessel mit vollem Umschalter-Text — Wechsel zwischen zwei gekuerzten Konten desselben Prefix = neue erste Lesung
var tabP = tabelle(KOPF + "Nothing here yet"); var rP = reiter("true"); var pP = el("Positions x", [rP], tabP); h5.setDoc(doc(rP));
h5.setKonto("FTDFYSLX15037290\u2026149,346.24USD");
check(h5.leerBeweis() === false && h5.leerBeweis() === true, "Phrase bei gekuerztem Konto: erste/zweite Lesung → flach");
h5.setKonto("FTDFYSLX15037290\u2026151,002.10USD");
check(h5.leerBeweis() === false, "Wechsel auf zweites Konto mit gleichem Prefix (andere Balance) → neue erste Lesung");
h5.setKonto("KONTO-A");
// 0.10.4: Puls-Chrome-Modus aus Schalter + Marke der Puls-Augen
var hP = new Function(stueck("function pulsChromeModus", "  const ENDPOINT") + "; return pulsChromeModus;")();
check(hP(true, null) === true && hP(false, "1") === false && hP(null, "1") === true && hP(null, null) === false && hP(undefined, "1") === true && hP(null, "0") === false,
      "pulsChromeModus: Schalter an → an; ausdruecklich aus → aus (Marke egal); nie gesetzt → Marke '1'");
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
check(L1.kern === 1 && L1.info.quelle === "eingebaut" && L1.info.eval === true && L1.info.laeuft === /const EINGEBAUT = '([0-9.]+)'/.exec(src)[1], "Lader: nichts gemerkt → eingebaute Fassung läuft genau einmal");
var gelaufen = 0;
var L2 = laderLauf({ merk: { version: "0.99.0", code: "globalThis.__laderInfo = PROPHOS_LADER;", sha: "x" } });
var i2 = globalThis.__laderInfo;
check(L2.kern === 0 && i2 && i2.quelle === "nachgeladen" && i2.laeuft === "0.99.0", "Lader: neuere gemerkte Fassung läuft statt der eingebauten (nie beide)");
var L3 = laderLauf({ merk: { version: "0.99.0", code: "throw new Error('kaputt')", sha: "x" } });
check(L3.kern === 1 && L3.info.quelle === "eingebaut" && L3.store.prophos_kern_v1 === null && /warf/.test(L3.info.fehler), "Lader: gemerkte Fassung wirft → eingebaute läuft, Merker gelöscht");
var L4 = laderLauf({ merk: { version: "0.99.0", code: "}{ kein js", sha: "x" } });
check(L4.kern === 1 && L4.store.prophos_kern_v1 === null && /nicht lesbar/.test(L4.info.fehler), "Lader: gemerkte Fassung nicht lesbar → eingebaute läuft, Merker gelöscht");
var L3r = laderLauf({ merk: { version: "0.99.0", code: "unsafeWindow.__prophosKernAn = true; throw new Error('halb gestartet')", sha: "x" } });
check(L3r.info.quelle === "blind (Riegel)" && /Riegel/.test(L3r.info.fehler) && L3r.store.prophos_kern_v1 === null,
      "Lader: nachgeladener Kern setzt den Riegel und wirft → eingebaute Fassung startet NICHT daneben (blind statt doppelt), Merker gelöscht");
var L5 = laderLauf({ merk: { version: "0.9.12", code: "PROPHOS_LADER.x = 1;", sha: "x" } });
check(L5.kern === 1 && L5.info.quelle === "eingebaut", "Lader: gemerkte ÄLTERE Fassung wird nie gestartet");
var L6 = laderLauf({ evalGesperrt: true, merk: { version: "0.99.0", code: "PROPHOS_LADER.x = 1;", sha: "x" } });
check(L6.kern === 1 && L6.info.eval === false && L6.info.quelle === "eingebaut" && /eval gesperrt/.test(L6.info.fehler) && L6.store.prophos_kern_v1 !== null,
      "Lader: eval gesperrt (MV3) → eingebaute Fassung, nichts nachgeladen");
// 0.10.2 EXIT-FILL-STEMPEL: Meldungen lesen (nur ausgefuehrte), neu nur bei wachsender Anzahl, Doppelte einmal mit fruehester Zeit
var FX = new Function(stueck("  const FILL_MAX = 10", "  function fillsLesen() {") + "; return { aus: fillsAusTexten, neu: fillsNeu, merk: fillsMerken };")();
var r1 = FX.aus(["Market order executed on CME_MINI:NQZ6", "Sell 1", "at 30,801.25"]);
check(r1.length === 1 && r1[0].seite === "sell" && r1[0].menge === 1 && r1[0].preis === 30801.25 && r1[0].symbol === "NQZ6" && r1[0].art === "market",
      "Exit-Fill: Titel + zwei Text-Knoten ('Sell 1' + 'at 30,801.25') → ausgeführte Market-Order mit Symbol");
check(FX.aus(["Limit order executed", "MNQZ6", "Buy 3 at 29,704.25"])[0].preis === 29704.25 && FX.aus(["Marktorder ausgeführt NQZ6", "1 zu 30.801,25 verkaufen"])[0].seite === "sell"
      && FX.aus(["Take Profit order placed on NQZ6", "Sell 1 at 31,000.00"]).length === 0 && FX.aus(["Stop Loss order cancelled", "Buy 1 at 29,000.00"]).length === 0,
      "Exit-Fill: Limit/Deutsch ja; platziert/storniert nie");
var n0 = FX.neu(null, r1), n1 = FX.neu(n0.zaehl, r1), n2 = FX.neu(n1.zaehl, r1.concat(r1));
var M1 = FX.merk([], n2.neu, 1000, "K"), M2 = FX.merk(M1, n2.neu, 5000, "K");
check(n0.neu.length === 0 && n1.neu.length === 0 && n2.neu.length === 1 && M2.length === 1 && M2[0].at === 1000 && M2[0].konto === "K",
      "Exit-Fill: beim Start Vorhandenes und alte Protokoll-Zeilen nie neu; Kopie im Protokoll zählt einmal mit der frühesten Zeit");
var fehl = aus.filter(function (z) { return z.indexOf("FEHL") === 0; }).length;
return aus.join("\n") + "\n" + (fehl ? "FEHLER (" + fehl + ")" : "alle Tests bestanden");
}
