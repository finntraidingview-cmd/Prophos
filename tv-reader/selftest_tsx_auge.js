// Selbsttest TopstepX-Auge 0.3.0 (Lader + Kern, 29.10.2026) — ohne Node, mit JavaScriptCore des Macs:
//   osascript -l JavaScript tv-reader/selftest_tsx_auge.js [pfad/zu/tsx-auge.user.js]
// Lader-Wege mit nachgebauten GM-Funktionen (kein Netz) und ein echter Lauf des Kerns mit nachgebautem Auge/DOM: Meldung trägt SCRIPT und
// lader, der Doppellauf-Riegel lässt keinen zweiten Kern in derselben Seite starten.
function run(argv) {
ObjC.import("Foundation");
var pfad = (argv && argv[0]) || "tv-reader/tsx-auge.user.js";
var src = $.NSString.stringWithContentsOfFileEncodingError(pfad, 4, null).js;
if (!src) return "FEHLER: " + pfad + " nicht lesbar";
var aus = [];
function check(b, t) { aus.push((b ? "OK   " : "FEHL ") + t); }
var EIN = /const EINGEBAUT = '([0-9.]+)'/.exec(src)[1];
var laderSrc = src.slice(src.indexOf("(function prophosLader()"));
function laderLauf(o) {
  var spur = { kern: 0, info: null, netz: [] };
  var store = { prophos_tsx_kern_v1: o.merk || null };
  var uw = o.uw || {};
  var fn = new Function("GM_getValue", "GM_setValue", "GM_xmlhttpRequest", "unsafeWindow", "prophosKern", "setTimeout", "Function", "window", laderSrc);
  var Fn = o.evalGesperrt ? function () { throw new Error("EvalError: Refused to evaluate a string as JavaScript"); } : Function;
  fn(o.ohneGm ? undefined : function (k, d) { return k in store ? store[k] : d; }, o.ohneGm ? undefined : function (k, v) { store[k] = v; },
     function (req) { spur.netz.push(req); }, uw,
     function () { spur.kern++; spur.info = arguments[4]; }, function () {}, Fn, {});
  spur.store = store; return spur;
}
var L1 = laderLauf({});
check(L1.kern === 1 && L1.info.quelle === "eingebaut" && L1.info.laeuft === EIN && L1.info.eval === true, "Lader: nichts gemerkt → eingebaute Fassung " + EIN + " genau einmal");
var L2 = laderLauf({ merk: { version: "9.0.0", code: "globalThis.__tsxInfo = PROPHOS_LADER; globalThis.__tsxUw = unsafeWindow;", sha: "x" } });
check(L2.kern === 0 && globalThis.__tsxInfo && globalThis.__tsxInfo.quelle === "nachgeladen" && globalThis.__tsxInfo.laeuft === "9.0.0",
      "Lader: neuere gemerkte Fassung läuft statt der eingebauten (nie beide)");
var L3 = laderLauf({ merk: { version: "9.0.0", code: "throw new Error('kaputt')", sha: "x" } });
check(L3.kern === 1 && L3.info.quelle === "eingebaut" && L3.store.prophos_tsx_kern_v1 === null, "Lader: gemerkte Fassung wirft → eingebaute läuft, Merker gelöscht");
var L4 = laderLauf({ merk: { version: "9.0.0", code: "unsafeWindow.__prophosTsxKernAn = true; throw new Error('halb')", sha: "x" } });
check(L4.info.quelle === "blind (Riegel)" && /Riegel/.test(L4.info.fehler), "Lader: Riegel gesetzt und geworfen → blind statt doppelt");
var L5 = laderLauf({ merk: { version: "0.1.0", code: "x", sha: "x" } });
check(L5.kern === 1 && L5.info.quelle === "eingebaut", "Lader: ältere gemerkte Fassung wird nie gestartet");
var L6 = laderLauf({ evalGesperrt: true, merk: { version: "9.0.0", code: "x", sha: "x" } });
check(L6.kern === 1 && L6.info.eval === false && L6.netz.length === 0, "Lader: eval gesperrt (MV3) → eingebaute Fassung, nichts nachgeladen");

var L7 = laderLauf({ ohneGm: true });
check(L7.kern === 1 && L7.info.quelle === "eingebaut", "Lader: GM_getValue/GM_setValue fehlen → eingebaute Fassung läuft trotzdem (nie ganz tot)");

// echter Kern-Lauf mit nachgebautem Auge/DOM
var kern = src.slice(src.indexOf("// ==KERN-START==\n") + 18, src.indexOf("// ==KERN-ENDE=="));
var gesendet = [], intervalle = 0;
globalThis.PROPHOS_AUGEN_TSX = { stand: function () { return { v: "tsx-test", konto: { aktiv: "KONTO-A", kontonr: "KONTO-A" }, positionen: [], flach: true, ticket: {}, kopf: {} }; } };
globalThis.location = { href: "https://topstepx.com/trade" };
globalThis.document = { visibilityState: "visible", querySelectorAll: function () { return []; }, documentElement: {} };
globalThis.setInterval = function () { intervalle++; };
var uw = {};
var info = { v: 1, laeuft: EIN, quelle: "eingebaut" };
var K = new Function("GM_xmlhttpRequest", "GM_getValue", "GM_setValue", "unsafeWindow", "PROPHOS_LADER", kern);
var gm = function (req) { gesendet.push(req); };
K(gm, function () {}, function () {}, uw, info);
var p = gesendet.length ? JSON.parse(gesendet[0].data) : null;
check(p && p.script === EIN && p.lader && p.lader.laeuft === EIN && p.stand && p.stand.flach === true && /8770\/api\/tsx-stand$/.test(gesendet[0].url),
      "Kern: meldet ans Panel mit script " + EIN + ", lader und Stand (flach)");
check(uw.__prophosTsxKernAn === true, "Kern: setzt den Doppellauf-Riegel");
var vorher = gesendet.length, iv = intervalle;
K(gm, function () {}, function () {}, uw, info);
check(gesendet.length === vorher && intervalle === iv, "Kern: zweiter Start in derselben Seite kehrt sofort um (kein zweiter Takt, keine Meldung)");
var fehl = aus.filter(function (z) { return z.indexOf("FEHL") === 0; }).length;
return aus.join("\n") + "\n" + (fehl ? "FEHLER (" + fehl + ")" : "alle Tests bestanden");
}
