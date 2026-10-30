#!/usr/bin/env python3
"""Selbsttest NOVA-SCHLIESS-PUNKT (30.10.2026, Prüfer S2 zu Auge 0.3.2): führt den echten hedgeTsxSchnellTick über JavaScriptCore aus und prüft die Wirkung auf die Uhren. Langsamer Takt (Messung 1,2–2 s
alt) schließt; Nachzügler (3,2 s alt, frisch angekommen) schließt nicht, lässt Konto-Uhr und Sichtung stehen und meldet nicht blind; danach schließt der echte Stand; Stand > 1 s ab Ankunft verwirft wie bisher.
Aufruf:  python3 tools/selftest_tsx_messung_jung.py"""
import json
import os
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def fn(kopf):
    i = HTML.index(kopf)
    return HTML[i:HTML.index("\n  }\n", i) + 4]


def zeile(anfang):
    i = HTML.index(anfang)
    return HTML[i:HTML.index("\n", i)]


UMGEBUNG = r"""
var uhr = 1000000; const DateEcht = Date; Date.now = () => uhr
globalThis.console = { warn: (...a) => print('WARN ' + a.join(' ')), info: () => {}, log: () => {} }
const window = { mtcApi: async () => antwort }, MT5_LOCAL = true
let antwort = null, tradePlans = [], accounts = []
const spur = { blind: 0, repar: 0, stempel: [], zu: 0 }
const _tsxSchnellKonto = new Map(), _tsxSchnellLeer = new Map(), _tsxGesehenAt = new Map(), _hedgeMasterGesehen = new Set()
let _tsxSchnellBusy = false, _tsxStandFehler = 0, _tsxBlindSeit = 0, _tsxBlindN = 0, _tsxTraege = { ab: 0, max: 0 }
const hedgePcId = () => 'pc-x', hedgePulsUnterwegs = () => '', tsxTraegeMerken = () => {}, tsxAugeGesehenMerken = () => {}, tpIstNova = () => true, tsxLs = { get: () => null }
const tsxBlindZurueck = () => {}, tsxBlindReparaturErlaubt = () => { spur.blind++; return true }, tsxBlindUrteil = () => ({ seit: 1, n: 1, faellig: false }), tsxReloginAnstossen = () => { spur.repar++; return false }
const tsxKontoGleich = (a, b) => a === b, tsxStandListe = st => st.positionen, hedgeKontoPasst = (a, b) => a === b
function tvSymbolWurzel(s){ return /^MNQ/.test(String(s)) ? 'MNQ' : /^NQ/.test(String(s)) ? 'NQ' : '' }
const hedgeMasterWegStempeln = (p, q) => { spur.stempel.push(q) }, hedgeMasterWegAusfuehren = async () => { spur.zu++ }
"""
code = "\n".join([UMGEBUNG, zeile("  const TSX_FLACH_FOLGE ="), zeile("  const TSX_MESSUNG_MAX_MS"), zeile("  function tsxMessungJung("), fn("  function tsxFlachSchnell("), fn("  function hedgeMasterTeilweise("),
                  fn("  function hedgeMasterWegEntscheid("), fn("  async function hedgeTsxSchnellTick(")])
lauf = r"""
const K = 'EXPRESS-V2-1', POS = [{ symbol: 'NQZ6', wurzel: 'NQ', richtung: 'buy', menge_zahl: 2 }]
const neu = () => { _tsxSchnellKonto.clear(); _tsxSchnellLeer.clear(); _tsxGesehenAt.clear(); _hedgeMasterGesehen.clear(); spur.blind = 0; spur.stempel = []; spur.zu = 0
  accounts = [{ id: 'a', externalId: K }]; tradePlans = [{ id: 'p', route: 'tsv2', status: 'open', richtung: 'buy', masterAccountId: 'a', mt5Baseline: { hedge: { status: 'offen', pc: 'pc-x', opened_at: new DateEcht(uhr - 600000).toISOString(), symbol_nq: 'NQZ6' } } }] }
const stand = (o) => Object.assign({ ts: uhr - 200, konto: { kontonr: K, abgekuerzt: false, liste_offen: false }, positionen: [], flach: false, ausgeloggt: false }, o)
const offen = (alterMs) => ({ ok: true, tabs: 1, alter_s: 0.3, stand: stand({ ts: uhr - alterMs, positionen: POS }) })
const flach = (alterMs, alterS) => ({ ok: true, tabs: 1, alter_s: alterS, stand: stand({ ts: uhr - alterMs, flach: true, flach_folge: 4, flach_seit: uhr - alterMs - 900 }) })
async function t(r, schritt){ antwort = r; await hedgeTsxSchnellTick(); uhr += schritt || 0 }
const ein = async () => { await t(offen(200), 6000); await t(offen(200), 100) }   // Konto-Uhr läuft, Sichtung im Konto-Zeitraum
;(async () => { const out = {}
  // langsamer Takt: Messung 1,2–2 s alt, Ankunft frisch
  for(const ms of [1200, 2000]){ neu(); await ein(); await t(flach(ms, 0.9)); out['langsam_' + ms] = { zu: spur.zu, stempel: spur.stempel.slice() } }
  // Grenze
  neu(); await ein(); await t(flach(2500, 0.1)); out.grenze = spur.zu
  // Nachzügler: frisch angekommen, Messung 3,2 s alt
  neu(); await ein(); const kUhr = _tsxSchnellKonto.get('p'), gUhr = _tsxGesehenAt.get('p')
  await t(flach(3200, 0.05))
  out.nach = { zu: spur.zu, blind: spur.blind, konto_gleich: _tsxSchnellKonto.get('p') === kUhr, sichtung_gleich: _tsxGesehenAt.get('p') === gUhr, leer: _tsxSchnellLeer.has('p') }
  uhr += 50; await t(offen(100)); out.nach_offen = { zu: spur.zu, konto_gleich: _tsxSchnellKonto.get('p') === kUhr }
  uhr += 50; await t(flach(200, 0.1)); out.nach_flach = spur.zu
  // Stand > 1 s ab Ankunft: wie bisher verwerfen + blind-Weg, nie schließen
  neu(); await ein(); await t(flach(200, 1.5)); out.alt = { zu: spur.zu, konto: _tsxSchnellKonto.has('p'), blind: spur.blind }
  // ohne ts: nie schließen
  neu(); await ein(); { const r = flach(200, 0.1); delete r.stand.ts; await t(r); out.ohne_ts = spur.zu }
  print(JSON.stringify(out))
})().catch(e => print('FEHLER ' + e + ' ' + (e && e.stack)))
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(code + "\n" + lauf)
    pfad = f.name
r = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=60)
os.unlink(pfad)
try:
    e = json.loads(r.stdout.strip().splitlines()[-1])
except Exception:
    print(r.stdout, r.stderr)
    sys.exit(1)
fehler = 0
for name, ok in (("langsam, Messung 1,2 s alt: schließt", e["langsam_1200"] == {"zu": 1, "stempel": ["auge"]}),
                 ("langsam, Messung 2 s alt: schließt", e["langsam_2000"] == {"zu": 1, "stempel": ["auge"]}),
                 ("Grenze 2,5 s: schließt", e["grenze"] == 1),
                 ("Nachzügler 3,2 s: schließt nicht", e["nach"]["zu"] == 0),
                 ("Nachzügler: Konto-Uhr und Sichtung bleiben stehen", e["nach"]["konto_gleich"] and e["nach"]["sichtung_gleich"]),
                 ("Nachzügler: Leer-Uhr nicht gestartet, nicht blind", e["nach"]["leer"] is False and e["nach"]["blind"] == 0),
                 ("Danach echter Stand „offen“: nichts zu, Konto-Uhr steht", e["nach_offen"] == {"zu": 0, "konto_gleich": True}),
                 ("Danach echter Stand flach: schließt", e["nach_flach"] == 1),
                 ("Ankunft > 1 s: verwirft wie bisher, nie zu", e["alt"]["zu"] == 0 and e["alt"]["konto"] is False and e["alt"]["blind"] == 1),
                 ("Ohne ts: nie zu", e["ohne_ts"] == 0)):
    print(("ok   " if ok else "FEHL ") + name)
    fehler += 0 if ok else 1
print("\nALLES OK" if not fehler else f"\n{fehler} FEHLER {e}")
sys.exit(1 if fehler else 0)
