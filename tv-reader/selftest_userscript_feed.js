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
var fehl = aus.filter(function (z) { return z.indexOf("FEHL") === 0; }).length;
return aus.join("\n") + "\n" + (fehl ? "FEHLER (" + fehl + ")" : "alle Tests bestanden");
}
