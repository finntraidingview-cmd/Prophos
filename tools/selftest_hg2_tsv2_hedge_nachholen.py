#!/usr/bin/env python3
"""Selbsttest HG2 (Finn 23.11.2026 ~03:45: „Schau, dass so ein Fehler nicht mehr kommt“; Befund HG1/NV3): Topstep (route tsv2, hedge_eur > 0) mit
verlorener Puls-Antwort lief ohne Fusion-Hedge — die Ersatzwege öffneten nur für tvv2. Jetzt öffnen beide auch für tsv2: (A) pulsErgebnisseUebernehmen
(Antwort verloren → „Läuft“ + Hedge), (B) Selbstheilung im hedgeWacheTick (laufender Plan ohne hedge-Objekt, 20 s–3 min nach dem Start).
tvv2 unverändert, Pläne ohne hedge_eur nie, hedgeSpaetAlterS (90-s-Grenze) unberührt (Finns Entscheidung).

Aufruf:  python3 tools/selftest_hg2_tsv2_hedge_nachholen.py
Ohne Netz und ohne Node: schneidet beide Blöcke aus prophos.html und führt sie mit macOS-JavaScriptCore (jsc) gegen Attrappen aus. Platzhalter-IDs."""
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
// Topstep: TopstepX-Auge (true gesehen / false flach / null nicht zu sagen) — der TV-Reader kennt TopstepX nicht
async function hedgeLotsMasterDa(p){ AUGE_FRAGEN.push(p.id); return Object.prototype.hasOwnProperty.call(AUGE, p.id) ? AUGE[p.id] : null }
async function hedgeAmPlanSchreiben(id, h){ log({ hedgeSchreiben: id, status: h.status, grund_code: h.grund_code || null }) }
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
    pe = schnitt(text, "  async function pulsErgebnisseUebernehmen(){", "  window._pulsErgebnisseUebernehmen = pulsErgebnisseUebernehmen")
    wt = schnitt(text, "        const liste0 = hedgeSoloListeFrisch()", "      // PC-Kennung gewechselt")
    js = HARNESS + pe + "\nasync function heal(_tp){ var amPc = true; {\n" + wt + "\n}\n" + r"""
function plan(id, route, eur, status, extra){ return Object.assign({ id: id, route: route, status: status, hedge_eur: eur, master_name: 'WD ' + route, mt5_baseline: {}, started_at: new Date(JETZT - 60000).toISOString() }, extra || {}) }
async function laufA(){
  // (A) Antwort verloren: Ergebnis 20 s alt (über der 15-s-Gnade für Hedge-Pläne, unter den 120 s für den Rest)
  var at = new Date(JETZT - 20000).toISOString();
  ROWS = { ts1: plan('ts1', 'tsv2', 90.11, 'planned'), tv1: plan('tv1', 'tvv2', 120, 'planned'), ts0: plan('ts0', 'tsv2', 0, 'planned'),
           tsf: plan('tsf', 'tsv2', 90, 'planned'), tsu: plan('tsu', 'tsv2', 90, 'planned') };
  MASTER_FLACH = { tsf: true };                 // Reader würde „flach“ sagen — bei Topstep darf er nicht gefragt werden
  AUGE = { ts1: true, tsf: false };             // tsu: Auge nicht zu sagen (null)
  tradePlans = [];
  ERG = ['ts1', 'tv1', 'ts0', 'tsf', 'tsu'].map(function(id){ return { plan_id: id, art: 'order', pc_id: 'pc-xxxxxx', at: at, ergebnis: { ok: true, gesendet: true, einstieg: '26327', msg: 'Order platziert' } } });
  LOG = []; AUGE_FRAGEN = []; READER_FRAGEN = [];
  await pulsErgebnisseUebernehmen();
  return { log: LOG, auge: AUGE_FRAGEN, reader: READER_FRAGEN };
}
async function laufB(){
  // (B) Selbstheilung: laufend, ohne hedge-Objekt, 60 s nach dem Start
  var k = new Date(JETZT - 60000).toISOString();
  var tp = [rowToPlan(plan('h1', 'tsv2', 90.11, 'open', { mt5_baseline: { tv: { puls: 'tsx', klick_at: k, tp_level_nq: 26273.0 } } })),
            rowToPlan(plan('h2', 'tvv2', 120, 'open', { mt5_baseline: { tv: { einstieg_nq: 26327, klick_at: k } } })),
            rowToPlan(plan('h3', 'tsv2', 0, 'open')),
            rowToPlan(plan('h4', 'mt5v2', 90, 'open')),
            rowToPlan(plan('h5', 'tsv2', 90, 'open', { started_at: new Date(JETZT - 5000).toISOString() })),
            rowToPlan(plan('h6', 'tsv2', 90, 'open', { mt5_baseline: { tv: { puls: 'tsx', klick_at: k } } })),
            rowToPlan(plan('h7', 'tsv2', 90, 'open', { mt5_baseline: { tv: { puls: 'tsx', klick_at: k, einstieg_nq: 26330, einstieg_quelle: 'reader_klick' } } })),
            rowToPlan(plan('h8', 'tsv2', 90, 'open', { mt5_baseline: { tv: { puls: 'tsx', klick_at: k, einstieg_nq: 26331, einstieg_quelle: 'fill' } } })),
            rowToPlan(plan('h9', 'tsv2', 90, 'open', { mt5_baseline: { tv: { puls: 'tsx', klick_at: k } } }))];
  AUGE = { h1: true, h5: true, h7: true, h8: true, h9: false };   // h6: nicht zu sagen
  LOG = []; _hedgeNachgeholt = new Set(); AUGE_FRAGEN = []; READER_FRAGEN = [];
  await heal(tp);
  return { log: LOG, nachgeholt: Array.from(_hedgeNachgeholt), auge: AUGE_FRAGEN, reader: READER_FRAGEN };
}
(async function(){
  var a = await laufA(), b = await laufB();
  print(JSON.stringify({ a: a, b: b }));
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
    A, B = e["a"], e["b"]
    a, b = A["log"], B["log"]
    hedge_a = {x["hedge"]: x for x in a if "hedge" in x}
    open_a = {x["open"] for x in a if "open" in x}
    print("(A) Nachholen nach verlorener Antwort")
    check("ts1" in open_a and hedge_a.get("ts1", {}).get("nachgeholt") is True, "tsv2, Auge sieht die Position: „Läuft“ UND Fusion-Hedge geöffnet (vorher nur „Läuft“)")
    check("tv1" in open_a and "tv1" in hedge_a, "tvv2 unverändert: „Läuft“ + Hedge")
    check("ts0" not in open_a and "ts0" not in hedge_a, "tsv2 ohne hedge_eur: nach 20 s noch nicht übernommen (normale 120-s-Gnade), kein Hedge")
    check("tsf" in open_a and "tsf" not in hedge_a and any(x.get("hedgeSchreiben") == "tsf" and x.get("grund_code") == "master_flach" for x in a),
          "tsv2, Auge zeigt den Master schon flach → kein Hedge, Vermerk master_flach")
    check("tsu" in open_a and "tsu" not in hedge_a and any("TopstepX-Auge sieht die Position nicht sicher" in str(x.get("toast", "")) for x in a),
          "tsv2, Auge nicht zu sagen → KEIN Hedge (fail-closed, Ersatz für die fehlende 90-s-Grenze), Toast „in TopstepX prüfen“")
    check(set(A["auge"]) == {"ts1", "tsf", "tsu"} and "tv1" in A["reader"] and not ({"ts1", "tsf", "tsu"} & set(A["reader"])),
          "Topstep fragt das TopstepX-Auge, tvv2 den Reader (unverändert)")
    print("(B) Selbstheilung im Wächter")
    hedge_b = {x["hedge"]: x for x in b if "hedge" in x}
    check("h1" in hedge_b and hedge_b["h1"]["tp_limit"] == 26273.0 and hedge_b["h1"]["einstieg"] is None,
          "tsv2 laufend ohne hedge-Objekt, Auge sieht die Position → Hedge nachgeholt, TP am TopstepX-Bracket (tp_limit), kein erfundener Einstieg")
    check("h2" in hedge_b and hedge_b["h2"]["tp_limit"] is None and hedge_b["h2"]["einstieg"] == "26327", "tvv2 unverändert (Einstieg aus dem Puls-Fill, ohne tp_limit)")
    check("h3" not in hedge_b and "h4" not in hedge_b, "ohne hedge_eur bzw. andere Route (mt5v2) → nie")
    check("h5" not in hedge_b, "tsv2 erst ab 20 s nach dem Start (Fenster 20–180 s unverändert)")
    check("h6" not in hedge_b and "h6" not in B["nachgeholt"], "tsv2, Auge nicht zu sagen → kein Hedge, nächster Tick darf es erneut versuchen")
    check("h7" in hedge_b and hedge_b["h7"]["einstieg"] is None, "tsv2 mit Reader-Einstieg (einstieg_quelle ≠ fill) → kein Einstieg an den Kern (sonst ohne Zuschlag als Fill)")
    check("h8" in hedge_b and hedge_b["h8"]["einstieg"] == "26331", "tsv2 mit echtem Fill-Einstieg → Einstieg wird übergeben")
    check("h9" not in hedge_b and any(x.get("hedgeSchreiben") == "h9" and x.get("grund_code") == "master_flach" for x in b), "tsv2, Auge flach → kein Hedge, Vermerk master_flach")
    check("h2" in B["reader"] and not ({"h1", "h6", "h7", "h8", "h9"} & set(B["reader"])), "Selbstheilung: Topstep fragt das Auge, tvv2 den Reader")
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
