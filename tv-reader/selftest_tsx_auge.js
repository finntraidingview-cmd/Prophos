// Selbsttest TopstepX-Auge 0.3.x (Lader + Kern, 29.10.2026; 0.3.1 Flach-Folge, Worker-Wache; 0.3.2 Worker heilt, Riegel, Diagnose) — ohne Node, mit JavaScriptCore des Macs:
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
globalThis.setInterval = function () { intervalle++; return intervalle; };
globalThis.clearInterval = function () {};
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
// 0.3.1 Flach-Folge + Diagnose in der Meldung
check(p && p.stand && p.stand.flach_folge === 1 && typeof p.stand.flach_seit === "number" && p.stand.gesendet_n === 0
      && p.stand.worker_ticks === 0 && Array.isArray(p.stand.panel_timeouts), "Kern 0.3.1: flach_folge/flach_seit + gesendet_n/worker_ticks/panel_timeouts in der Meldung");
// 0.3.1 Worker-Wache: Worker ohne Tick (CSP sperrt still) → nach 0,5 s setInterval zusätzlich, takt 'worker-tot'
var spaeter = [], wInst = null;
globalThis.setTimeout = function (f) { spaeter.push(f); return 1; };
globalThis.URL = { createObjectURL: function () { return "blob:x"; } };
globalThis.Blob = function () {};
globalThis.Worker = function () { wInst = this; this.postMessage = function () {}; };
gesendet = []; intervalle = 0;
var uw2 = {};
K(function (req) { gesendet.push(req); }, function () {}, function () {}, uw2, info);
var ivStart = intervalle;
spaeter.forEach(function (f) { f(); });
gesendet[0] && gesendet[0].onload && gesendet[0].onload({ status: 200 });
check(intervalle === ivStart + 1, "Worker-Wache: kein Worker-Tick in 0,5 s → genau ein Ersatz-setInterval");
// nächste Meldung trägt takt 'worker-tot'
var K2tick = gesendet.length;
// eine Meldung erzwingen: Worker-Ereignis simulieren (zählt als Tick, ersetzt aber nichts mehr)
var nowE = Date.now; Date.now = function () { return nowE() + 200; };   // Worker-Tick misst erst ≥ 80 ms nach dem letzten
wInst.onmessage();
Date.now = nowE;
var letzte = gesendet.length > K2tick ? JSON.parse(gesendet[gesendet.length - 1].data) : null;
check(letzte && letzte.stand.takt === "worker" && letzte.stand.worker_ticks === 1 && letzte.stand.worker_tot_n === 1 && /kein Tick/.test(letzte.stand.letzter_fehler), "0.3.2: später Worker-Tick heilt, takt wieder 'worker', Ausfall bleibt gezählt");
// lebender Worker: tickt vor Ablauf der 0,5 s → kein Ersatz
spaeter = []; gesendet = []; intervalle = 0;
var uw3 = {};
K(function (req) { gesendet.push(req); }, function () {}, function () {}, uw3, info);
var iv3 = intervalle;
gesendet.length && gesendet[0].onload({ status: 200 });
wInst.onmessage();
spaeter.forEach(function (f) { f(); });
check(intervalle === iv3, "Worker-Wache: Worker tickt → kein Ersatz-Takt");
// onerror → Ersatz
spaeter = []; gesendet = []; intervalle = 0;
K(function (req) { gesendet.push(req); }, function () {}, function () {}, {}, info);
var iv4 = intervalle;
wInst.onerror();
check(intervalle === iv4 + 1, "Worker-Wache: error-Event (CSP) → Ersatz-setInterval");
// 0.3.2 mit fester Uhr: Wache, Neustart, Riegel, Diagnose
var uhr = 1000000, echtNow = Date.now; Date.now = function () { return uhr; };
function lauf32(gmF) {
  var o = { iv: [], leer: [], gestoppt: [], worker: [], gesendet: [], later: [] };
  globalThis.setInterval = function (f, ms) { var id = o.iv.length + 1; o.iv.push({ id: id, f: f, ms: ms }); return id; };
  globalThis.clearInterval = function (id) { o.gestoppt.push(id); };
  globalThis.setTimeout = function (f) { o.later.push(f); return 1; };
  globalThis.Worker = function () { this.term = false; var self = this; this.postMessage = function () {}; this.terminate = function () { self.term = true; }; o.worker.push(this); };
  var gmS = function (req) { o.gesendet.push(req); return { abort: function () { o.abbruch = (o.abbruch || 0) + 1; } }; };
  new Function("GM_xmlhttpRequest", "GM_getValue", "GM_setValue", "unsafeWindow", "PROPHOS_LADER", kern)(gmF || gmS, function () {}, function () {}, {}, info);
  // Wache = das 1000-ms-Intervall, das nach dem Worker-Start angelegt wird (Konsolen-Zeile hat 60000)
  o.wache = o.iv.filter(function (x) { return x.ms === 1000; })[0].f;
  return o;
}
var A = lauf32();
A.gesendet[0].onload({ status: 200 });
uhr += 100; A.worker[0].onmessage(); A.gesendet[1].onload({ status: 200 });
uhr += 2100; A.wache();
var ersatz = A.iv.filter(function (x) { return x.ms === 100; });
check(ersatz.length === 1, "0.3.2 Wache: Worker > 2 s stumm → Ersatz-Takt");
uhr += 100; ersatz[0].f();
var mA = JSON.parse(A.gesendet[A.gesendet.length - 1].data).stand;
check(mA.takt === "worker-tot" && mA.worker_tot_n === 1 && /stumm/.test(mA.letzter_fehler), "0.3.2 Wache: Meldung sagt worker-tot + Grund");
A.gesendet[A.gesendet.length - 1].onload({ status: 200 });
uhr += 100; A.worker[0].onmessage();
mA = JSON.parse(A.gesendet[A.gesendet.length - 1].data).stand;
check(A.gestoppt.length === 1 && mA.takt === "worker" && A.worker.length === 1, "0.3.2 Hänger: nächster Worker-Tick beendet den Ersatz, kein neuer Worker");
check(mA.letzter_fehler && /stumm/.test(mA.letzter_fehler) && mA.fehler_n === 1, "0.3.2 Diagnose: letzter_fehler und fehler_n bleiben nach Erfolg stehen");
check(typeof mA.stand_ms === "number" && typeof mA.unterwegs_ms === "number" && mA.haenger_n === 0, "0.3.2 Diagnose: stand_ms, unterwegs_ms, haenger_n in der Meldung");
// wirklich stumm: Neustart nach 10 s, dann erst nach 20 s; alter Worker zählt nicht mehr; neuer heilt
var B = lauf32();
B.gesendet[0].onload({ status: 200 });
uhr += 100; B.worker[0].onmessage(); B.gesendet[1].onload({ status: 200 });
uhr += 2100; B.wache();
uhr += 5000; B.wache();
check(B.worker.length === 1, "0.3.2 Neustart: nicht vor 10 s");
uhr += 6000; B.wache();
check(B.worker.length === 2 && B.worker[0].term === true, "0.3.2 Neustart: nach 10 s neuer Worker, alter beendet");
uhr += 15000; B.wache();
check(B.worker.length === 2, "0.3.2 Neustart: Abstand verdoppelt sich (20 s)");
uhr += 6000; B.wache();
check(B.worker.length === 3, "0.3.2 Neustart: nach 20 s der nächste");
var tickVorher = B.gesendet.length;
B.worker[0].onmessage();
check(B.gesendet.length === tickVorher && B.gestoppt.length === 0, "0.3.2 Neustart: Tick eines beendeten Workers zählt nicht");
B.worker[2].onmessage();
check(B.gestoppt.length === 1, "0.3.2 Neustart: Tick des neuen Workers beendet den Ersatz");
// Riegel: Rückmeldung bleibt aus
var C = lauf32();
var n0 = C.gesendet.length;
uhr += 2000; C.worker[0].onmessage();
check(C.gesendet.length === n0, "0.3.2 Riegel: unter 3 s kein zweiter Request");
uhr += 1100; C.worker[0].onmessage();
check(C.gesendet.length === n0 + 1 && C.abbruch === 1, "0.3.2 Riegel: über 3 s abgebrochen, neue Meldung geht raus");
var altReq = C.gesendet[n0 - 1], neuReq = C.gesendet[n0], mC = JSON.parse(neuReq.data).stand;
altReq.onload({ status: 200 });
uhr += 100; C.worker[0].onmessage();
check(C.gesendet.length === n0 + 1, "0.3.2 Riegel: späte Rückmeldung des alten Requests gibt den neuen nicht frei");
neuReq.onload({ status: 200 });
uhr += 100; C.worker[0].onmessage();
mC = JSON.parse(C.gesendet[C.gesendet.length - 1].data).stand;
check(C.gesendet.length === n0 + 2 && mC.haenger_n === 1 && /Rückmeldung/.test(mC.letzter_fehler), "0.3.2 Riegel: danach wieder frei, haenger_n + Grund in der Meldung");
// Abbruch ruft onerror synchron: zählt nicht doppelt, Hänger-Text bleibt
var C2G = [], C2 = lauf32(function (req) { C2G.push(req); return { abort: function () { req.onerror(); } }; });
uhr += 3100; C2.worker[0].onmessage();
C2G[1].onload({ status: 200 }); uhr += 100; C2.worker[0].onmessage();
var mC2 = JSON.parse(C2G[2].data).stand;
check(mC2.haenger_n === 1 && /Rückmeldung/.test(mC2.letzter_fehler), "0.3.2 abort ruft onerror: Hänger-Grund bleibt");
// Salve nach Hänger + Lücke in der Flach-Folge
var E = lauf32();
E.gesendet[0].onload({ status: 200 });
var folge = function () { var d = JSON.parse(E.gesendet[E.gesendet.length - 1].data).stand; E.gesendet[E.gesendet.length - 1].onload({ status: 200 }); return d.flach_folge; };
uhr += 100; E.worker[0].onmessage(); var f1 = folge();
uhr += 100; E.worker[0].onmessage(); var f2 = folge();
check(f1 === 2 && f2 === 3, "0.3.2 Flach-Folge: normaler Takt zählt weiter");
uhr += 2500; E.worker[0].onmessage(); var f3 = folge();
check(f3 === 1, "0.3.2 Flach-Folge: Lücke > 0,5 s beginnt neu");
var nE = E.gesendet.length;
uhr += 2; E.worker[0].onmessage();
check(E.gesendet.length === nE, "0.3.2 Salve: Worker-Tick 2 ms nach dem letzten misst nicht");
// GM wirft synchron: Riegel sofort frei, Grund sichtbar
var wurf = true, G = [];
var F = lauf32(function (req) { if (wurf) { wurf = false; throw new Error("gm kaputt"); } G.push(req); return {}; });
uhr += 100; F.worker[0].onmessage();
var mF = JSON.parse(G[0].data).stand;
check(/Senden: .*gm kaputt/.test(mF.letzter_fehler), "0.3.2 GM wirft: Riegel frei, Grund in der nächsten Meldung");
// Lesefehler: stand() wirft → sichtbar in der nächsten Meldung
var echtStand = globalThis.PROPHOS_AUGEN_TSX.stand, wirf = true;
globalThis.PROPHOS_AUGEN_TSX.stand = function () { if (wirf) { wirf = false; throw new Error("kaputt"); } return echtStand(); };
var D = lauf32();
check(D.gesendet.length === 0, "0.3.2 Lesefehler: dieser Takt sendet nichts");
uhr += 100; D.worker[0].onmessage();
var mD = JSON.parse(D.gesendet[0].data).stand;
check(/Lesen: .*kaputt/.test(mD.letzter_fehler) && mD.fehler_n === 1, "0.3.2 Lesefehler: Grund steht in der nächsten Meldung");
globalThis.PROPHOS_AUGEN_TSX.stand = echtStand; Date.now = echtNow;
var fehl = aus.filter(function (z) { return z.indexOf("FEHL") === 0; }).length;
return aus.join("\n") + "\n" + (fehl ? "FEHLER (" + fehl + ")" : "alle Tests bestanden");
}
