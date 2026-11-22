#!/usr/bin/env python3
"""Selbsttest HG2/HG2b (Finn 23.11.2026 ~03:45: „Schau, dass so ein Fehler nicht mehr kommt“; Befund HG1/NV3, Prüfer S2): Topstep (route tsv2,
hedge_eur > 0) mit verlorener Puls-Antwort lief ohne Fusion-Hedge — die Ersatzwege öffneten nur für tvv2. Jetzt öffnen beide auch für tsv2:
(A) pulsErgebnisseUebernehmen (Antwort verloren → „Läuft“ + Hedge), (B) Selbstheilung im hedgeWacheTick (laufender Plan ohne hedge-Objekt, 20 s–3 min).
Topstep fragt das TopstepX-Auge (hedgeLotsMasterDa), nicht den TV-Reader; nicht sicher zu sagen → kein Hedge (fail-closed).
HG2b: (1) Nachholen bei tsv2 nur, wenn der Puls-Klick ≤ 10 min alt ist (sonst Vermerk klick_alt); (2) „flach“ bei tsv2 erst nach einem zweiten Blick
≥ 4 s später endgültig (Nachholen: zweite Lesung nach dem Warten; Selbstheilung: nächster Takt). tvv2 unverändert, hedgeSpaetAlterS unberührt.

Aufruf:  python3 tools/selftest_hg2_tsv2_hedge_nachholen.py
Ohne Netz und ohne Node: schneidet die Blöcke aus prophos.html und führt sie mit macOS-JavaScriptCore (jsc) gegen Attrappen aus. Platzhalter-IDs."""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HIER, "..", "prophos.html")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def schnitt(text, start, ende):
    a = text.index(start)
    return text[a:text.index(ende, a)]


HARNESS = r"""
var LOG = [];
function log(x){ LOG.push(x) }
var window = {}, MT5_LOCAL = true, currentUserId = 'u1', _peLaeuft = false, _tpOrbitLaeuft = false, _suLaeuft = false, _rsAktiv = false;
var PE_GNADE_MS = 120000, PE_GNADE_HEDGE_MS = 15000;
var ECHT_JETZT = Date.now, VERSATZ = 0, WARTEN = [];
Date.now = function(){ return ECHT_JETZT() + VERSATZ };
var setTimeout = function(f, ms){ WARTEN.push(ms); VERSATZ += ms; f(); return 0 };   // Warten = Uhr vorstellen, sofort weiter
var JETZT = Date.now();
var ERG = [], ROWS = {}, tradePlans = [];
function q(tab){
  var f = {}, me = {
    select: function(){ return me }, is: function(){ return me }, order: function(){ return me }, limit: function(){ return Promise.resolve({ data: tab === 'puls_ergebnisse' ? ERG : [], error: null }) },
    eq: function(k, v){ f[k] = v; return me }, maybeSingle: function(){ return Promise.resolve({ data: ROWS[f.id] || null }) },
    insert: function(z){ log({ insert: tab, z: z }); return Promise.resolve({}) }, update: function(){ return me },
    then: function(ok){ return Promise.resolve({}).then(ok) } };
  return me;
}
var supabase = { from: q };
function rowToPlan(r){ return { id: r.id, route: r.route, status: r.status, hedgeEur: Number(r.hedge_eur) || 0, masterName: r.master_name, mt5Baseline: r.mt5_baseline || {}, startedAt: r.started_at } }
async function pulsErgebnisAbgeholt(id, art){ log({ abgeholt: id, art: art }) }
function sfFlag(){ return null } async function sfMelden(){} async function pulsUnklarMarke(){}
function atToast(t){ log({ toast: t }) }
function tsxBaselineAusOrder(p, e){ return { puls: 'tsx', klick_at: e.klick_at } }
function tvV2BaselineAusOrder(p, e){ return { puls: 'tv', klick_at: e.klick_at } }
function tvV2Konto(){ return 'K' } function tvV2Handelstag(){ return '2026-11-20' } function tvV2OrderLevel(){ return {} }
async function v2PlanAufOpen(id){ log({ open: id }); var p = tradePlans.find(function(x){ return x.id === id }); if(p) p.status = 'open' }
async function baselinePatchIn(){}
async function hedgeSoloOeffnen(p, r){ log({ hedge: p.id, route: p.route, nachgeholt: !!(r && r.nachgeholt), tp_limit: (r && r.tp_limit) || null, einstieg: (r && r.einstieg) || null }) }
var MASTER_FLACH = {}, AUGE = {}, AUGE_FRAGEN = [], READER_FRAGEN = [];
function hedgeReaderMasterDa(p){ READER_FRAGEN.push(p.id); return MASTER_FLACH[p.id] ? false : true }
// Topstep: TopstepX-Auge (true gesehen / false flach / null nicht zu sagen); Liste = je Lesung der nächste Wert
async function hedgeLotsMasterDa(p){
  AUGE_FRAGEN.push(p.id)
  if(!Object.prototype.hasOwnProperty.call(AUGE, p.id)) return null
  var v = AUGE[p.id]
  return Array.isArray(v) ? (v.length > 1 ? v.shift() : v[0]) : v
}
async function hedgeAmPlanSchreiben(id, h){ log({ hedgeSchreiben: id, status: h.status, grund_code: h.grund_code || null, msg: h.msg || '' }) }
function hedgePcId(){ return 'pc-xxxxxx' }
function hedgeSpaetAlterS(){ return null }
function renderTradePlans(){} function tsxEndeFelder(){ return {} } async function tvV2EndeSetzen(){} function tvSymbolPasst(){ return true }
function tpOrbitWerte(){ return {} } function pulsPlattform(){ return 'TopstepX' }
// Selbstheilung
var _hedgeNachgeholt = new Set();
function hedgeSoloListeFrisch(){ return [] }
async function hedgeSperre(){ return true }
function hedgeFehlerSicher(){ return false }
function hedgeLevelAusPlan(){ return {} }
"""


def main():
    text = open(HTML, encoding="utf-8").read()
    helfer = schnitt(text, "  const HEDGE_TSX_FLACH_ZWEITER_MS = 4000", "  window._hedgeTsxKlickZuAlt = hedgeTsxKlickZuAlt")
    karte = schnitt(text, "  const _hedgeHeilFlachSeit = new Map()", "\n") + "\n"
    pe = schnitt(text, "  async function pulsErgebnisseUebernehmen(){", "  window._pulsErgebnisseUebernehmen = pulsErgebnisseUebernehmen")
    wt = schnitt(text, "        const liste0 = hedgeSoloListeFrisch()", "      // PC-Kennung gewechselt")
    js = HARNESS + helfer + karte + pe + "\nasync function heal(_tp){ var amPc = true; {\n" + wt + "\n}\n" + r"""
function plan(id, route, eur, status, extra){ return Object.assign({ id: id, route: route, status: status, hedge_eur: eur, master_name: 'Plan ' + route, mt5_baseline: {}, started_at: new Date(JETZT - 60000).toISOString() }, extra || {}) }
async function laufA(){
  // (A) Antwort verloren: Ergebnis 20 s alt (über der 15-s-Gnade für Hedge-Pläne, unter den 120 s für den Rest)
  var at = new Date(JETZT - 20000).toISOString(), klickFrisch = JETZT - 25000, klickAlt = JETZT - 11 * 60000;
  var ids = ['ts1', 'tv1', 'ts0', 'tsf', 'tsg', 'tsh', 'tsu', 'tsa'];
  ROWS = {}; ids.forEach(function(id){ ROWS[id] = plan(id, id === 'tv1' ? 'tvv2' : 'tsv2', id === 'ts0' ? 0 : 90, 'planned') });
  MASTER_FLACH = { tsf: true };                                       // der Reader würde „flach“ sagen — bei Topstep darf er nicht gefragt werden
  AUGE = { ts1: true, tsf: [false, false], tsg: [false, true], tsh: [false, null], tsa: true };   // tsu: nicht zu sagen
  tradePlans = [];
  ERG = ids.map(function(id){ return { plan_id: id, art: 'order', pc_id: 'pc-xxxxxx', at: at,
    ergebnis: { ok: true, gesendet: true, einstieg: '26327', msg: 'Order platziert', order_klick_ms: id === 'tsa' ? klickAlt : klickFrisch } } });
  LOG = []; AUGE_FRAGEN = []; READER_FRAGEN = []; WARTEN = [];
  await pulsErgebnisseUebernehmen();
  return { log: LOG, auge: AUGE_FRAGEN, reader: READER_FRAGEN, warten: WARTEN };
}
async function laufB(){
  // (B) Selbstheilung: laufend, ohne hedge-Objekt, 60 s nach dem Start; zwei Takte, der zweite 5 s später
  var k = new Date(JETZT - 60000).toISOString();
  var tp = [rowToPlan(plan('h1', 'tsv2', 90.11, 'open', { mt5_baseline: { tv: { puls: 'tsx', klick_at: k, tp_level_nq: 26273.0 } } })),
            rowToPlan(plan('h2', 'tvv2', 120, 'open', { mt5_baseline: { tv: { einstieg_nq: 26327, klick_at: k } } })),
            rowToPlan(plan('h3', 'tsv2', 0, 'open')),
            rowToPlan(plan('h4', 'mt5v2', 90, 'open')),
            rowToPlan(plan('h5', 'tsv2', 90, 'open', { started_at: new Date(JETZT - 5000).toISOString() })),
            rowToPlan(plan('h6', 'tsv2', 90, 'open', { mt5_baseline: { tv: { puls: 'tsx', klick_at: k } } })),
            rowToPlan(plan('h7', 'tsv2', 90, 'open', { mt5_baseline: { tv: { puls: 'tsx', klick_at: k, einstieg_nq: 26330, einstieg_quelle: 'reader_klick' } } })),
            rowToPlan(plan('h8', 'tsv2', 90, 'open', { mt5_baseline: { tv: { puls: 'tsx', klick_at: k, einstieg_nq: 26331, einstieg_quelle: 'fill' } } })),
            rowToPlan(plan('h9', 'tsv2', 90, 'open', { mt5_baseline: { tv: { puls: 'tsx', klick_at: k } } })),
            rowToPlan(plan('h10', 'tsv2', 90, 'open', { mt5_baseline: { tv: { puls: 'tsx', klick_at: k } } }))];
  AUGE = { h1: true, h5: true, h7: true, h8: true, h9: [false, false], h10: [false, true] };   // h6: nicht zu sagen
  _hedgeNachgeholt = new Set(); AUGE_FRAGEN = []; READER_FRAGEN = [];
  LOG = []; await heal(tp); var t1 = { log: LOG, nachgeholt: Array.from(_hedgeNachgeholt), auge: AUGE_FRAGEN.slice(), reader: READER_FRAGEN.slice() };
  VERSATZ += 5000;
  LOG = []; await heal(tp); var t2 = { log: LOG };
  return { t1: t1, t2: t2 };
}
(async function(){
  var a = await laufA(), b = await laufB();
  var r = { alt: [window._hedgeTsxKlickZuAlt ? 'x' : null] };
  print(JSON.stringify({ a: a, b: b,
    alt: [hedgeTsxKlickZuAlt({ order_klick_ms: Date.now() - 9 * 60000 }, Date.now()), hedgeTsxKlickZuAlt({ order_klick_ms: Date.now() - 11 * 60000 }, Date.now()),
          hedgeTsxKlickZuAlt({}, Date.now()), hedgeTsxKlickZuAlt({ klick_at: new Date(Date.now() - 60000).toISOString() }, Date.now())] }));
})().catch(function(e){ print(JSON.stringify({ fehler: String(e && e.stack || e) })) });
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        pfad = f.name
    try:
        out = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(pfad)
    zeile = (out.stdout or "").strip().splitlines()[-1] if (out.stdout or "").strip() else ""
    try:
        e = json.loads(zeile)
    except ValueError:
        print(out.stdout, out.stderr)
        check(False, "jsc-Lauf liefert JSON")
        sys.exit(1)
    if e.get("fehler"):
        print(e["fehler"])
        check(False, "jsc-Lauf ohne Fehler")
        sys.exit(1)
    A = e["a"]
    a = A["log"]
    hedge_a = {x["hedge"]: x for x in a if "hedge" in x}
    open_a = {x["open"] for x in a if "open" in x}
    flach_a = {x["hedgeSchreiben"] for x in a if x.get("grund_code") == "master_flach"}
    print("(A) Nachholen nach verlorener Antwort")
    check("ts1" in open_a and hedge_a.get("ts1", {}).get("nachgeholt") is True, "tsv2, Auge sieht die Position: „Läuft“ UND Fusion-Hedge geöffnet (vorher nur „Läuft“)")
    check("tv1" in open_a and "tv1" in hedge_a and "tv1" in A["reader"], "tvv2 unverändert: „Läuft“ + Hedge, Prüfung über den Reader")
    check("ts0" not in open_a and "ts0" not in hedge_a, "tsv2 ohne hedge_eur: nach 20 s noch nicht übernommen (normale 120-s-Gnade), kein Hedge")
    check("tsf" in flach_a and "tsf" not in hedge_a and A["auge"].count("tsf") == 2, "tsv2, Auge zweimal flach → master_flach (zweiter Blick)")
    check("tsg" in hedge_a and "tsg" not in flach_a and A["auge"].count("tsg") == 2, "tsv2, erst flach, beim zweiten Blick Position da → Hedge, kein master_flach")
    check("tsh" not in hedge_a and "tsh" not in flach_a, "tsv2, erst flach, dann nicht zu sagen → kein Hedge und KEIN endgültiges master_flach")
    check("tsu" in open_a and "tsu" not in hedge_a and any("TopstepX-Auge sieht die Position nicht sicher" in str(x.get("toast", "")) for x in a),
          "tsv2, Auge nicht zu sagen → KEIN Hedge (fail-closed), Toast „in TopstepX prüfen“")
    check("tsa" in open_a and "tsa" not in hedge_a and "tsa" not in A["auge"]
          and any(x.get("hedgeSchreiben") == "tsa" and x.get("grund_code") == "klick_alt" and "11 min alt" in x.get("msg", "") for x in a),
          "tsv2, Puls-Klick 11 min alt → kein Hedge, Vermerk klick_alt, Auge gar nicht gefragt")
    check(4000 in A["warten"], "zweiter Blick nach ~4 s (HEDGE_TSX_FLACH_ZWEITER_MS)")
    check(not ({"ts1", "tsf", "tsg", "tsh", "tsu", "tsa"} & set(A["reader"])), "Topstep fragt nie den TV-Reader")
    check(e["alt"] == [None, 11, -1, None], f"hedgeTsxKlickZuAlt: 9 min ok, 11 min zu alt, ohne Zeit = zu alt, klick_at 1 min ok ({e['alt']})")
    print("(B) Selbstheilung im Wächter")
    t1, t2 = e["b"]["t1"], e["b"]["t2"]
    h1 = {x["hedge"]: x for x in t1["log"] if "hedge" in x}
    h2 = {x["hedge"]: x for x in t2["log"] if "hedge" in x}
    f1 = {x["hedgeSchreiben"] for x in t1["log"] if x.get("grund_code") == "master_flach"}
    f2 = {x["hedgeSchreiben"] for x in t2["log"] if x.get("grund_code") == "master_flach"}
    check("h1" in h1 and h1["h1"]["tp_limit"] == 26273.0 and h1["h1"]["einstieg"] is None,
          "tsv2 ohne hedge-Objekt, Auge sieht die Position → Hedge nachgeholt, TP am TopstepX-Bracket (tp_limit), kein erfundener Einstieg")
    check("h2" in h1 and h1["h2"]["tp_limit"] is None and h1["h2"]["einstieg"] == "26327" and "h2" in t1["reader"], "tvv2 unverändert (Reader, Einstieg aus dem Puls-Fill)")
    check("h3" not in h1 and "h4" not in h1, "ohne hedge_eur bzw. andere Route (mt5v2) → nie")
    check("h5" not in h1, "tsv2 erst ab 20 s nach dem Start (Fenster 20–180 s unverändert)")
    check("h6" not in h1 and "h6" not in t1["nachgeholt"], "tsv2, Auge nicht zu sagen → kein Hedge, nächster Takt darf erneut")
    check("h7" in h1 and h1["h7"]["einstieg"] is None, "tsv2 mit Reader-Einstieg (einstieg_quelle ≠ fill) → kein Einstieg an den Kern")
    check("h8" in h1 and h1["h8"]["einstieg"] == "26331", "tsv2 mit echtem Fill-Einstieg → Einstieg wird übergeben")
    check("h9" not in f1 and "h9" not in t1["nachgeholt"] and "h9" in f2 and "h9" not in h2,
          "tsv2, Auge flach: erster Takt kein Vermerk; zweiter Takt (≥ 4 s) flach bestätigt → master_flach, kein Hedge")
    check("h10" not in f1 and "h10" not in h1 and "h10" in h2 and "h10" not in f2, "tsv2, erst flach, im nächsten Takt Position da → Hedge, kein master_flach")
    check(not ({"h1", "h6", "h7", "h8", "h9", "h10"} & set(t1["reader"])), "Selbstheilung: Topstep fragt das Auge, nie den Reader")
    print("(C) Verdrahtung")
    check("function hedgeSpaetAlterS(plan, r, jetzt){\n    if(!plan || plan.route !== 'tvv2') return null" in text,
          "hedgeSpaetAlterS unberührt (90-s-Grenze weiter nur tvv2 — Finns Entscheidung)")
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("OK — alle Prüfungen grün")


if __name__ == "__main__":
    main()
