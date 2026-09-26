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
  "var kontoMerk={text:null,ts:0}; var kursMerk={}; var letzteEingabeMs=0; var EINGABE_RUHE_MS=120000;" +
  "var geplant=[]; function setTimeout(f){ geplant.push(f); }" + code +
  "; return {feedPflegen:feedPflegen, feedHeilen:feedHeilen, tabRolle:tabRolle, feedMarkiert:feedMarkiert, kontoAngemeldet:kontoAngemeldet," +
  " sess:sess, store:store, kontoMerk:kontoMerk, kursMerk:kursMerk, location:location, geplant:geplant, setEingabe:function(t){letzteEingabeMs=t}};";
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
var fehl = aus.filter(function (z) { return z.indexOf("FEHL") === 0; }).length;
return aus.join("\n") + "\n" + (fehl ? "FEHLER (" + fehl + ")" : "alle Tests bestanden");
}
