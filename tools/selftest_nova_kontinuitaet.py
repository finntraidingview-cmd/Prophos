#!/usr/bin/env python3
"""Selbsttest NV3 (Finn 10.11.2026, PC von Marco pc-t8wg97): führt den echten hedgeTsxSchnellTick über JavaScriptCore mit den Zeitlinien zweier echter Nova-Fälle aus.
  3d0c3e06 — Order-Ende 14:38:53,8 UTC, Auge flach ab 14:39:10,5, danach galt Puls noch bis ~14:39:52 als unterwegs (Augen-Lauf u. a.), Auge träge (1,5–2,7/s, einzelne
             Stände bis 2,2 s alt). Vorher: Fusion erst 14:40:22,4 (71,9 s). Soll: Fusion < 2 s nach flach_seit.
  937e9256 — Fill 14:29:35, Finn schloss ~14:29:56 während des eigenen Puls-Laufs (Plan noch „planned"), Order-Ende 14:30:04,4. Vorher: Fusion nie (bis Hand-Ende).
             Soll: Sichtung aus dem Lauf zählt, Fusion < 2 s nach flach_seit — auch während Puls noch arbeitet (Plan „planned").
Gegenproben: Auge zeigt ein anderes Konto → nie zu; Master nie gesehen und kein Fill-Beleg → nie zu.
Aufruf:  python3 tools/selftest_nova_kontinuitaet.py"""
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
var uhr = 0; const DateEcht = Date; Date.now = () => uhr
const warnungen = []
globalThis.console = { warn: (...a) => { warnungen.push(a.map(String).join(' ')) }, info: () => {}, log: () => {} }
const window = { mtcApi: async () => antwort }, MT5_LOCAL = true
let antwort = null, tradePlans = [], accounts = [], pulsUnterwegs = ''
const spur = { zu: [], stempel: [] }
const _tsxSchnellKonto = new Map(), _tsxSchnellLeer = new Map(), _tsxGesehenAt = new Map(), _hedgeMasterGesehen = new Set(), _hedgeWegLaeuft = new Set()
let _tsxSchnellBusy = false, _tsxStandFehler = 0, _tsxBlindSeit = 0, _tsxBlindN = 0, _tsxTraege = { ab: 0, max: 0 }
const hedgePcId = () => 'pc-t8wg97', hedgePulsUnterwegs = () => pulsUnterwegs, tsxTraegeMerken = () => {}, tsxAugeGesehenMerken = () => {}, tpIstNova = () => true, tsxLs = { get: () => null }
const tsxBlindZurueck = () => {}, tsxBlindReparaturErlaubt = () => false, tsxBlindUrteil = () => ({ seit: 1, n: 1, faellig: false }), tsxReloginAnstossen = () => false
const tsxKontoGleich = (a, b) => a === b, tsxStandListe = st => st.positionen, hedgeKontoPasst = (a, b) => a === b
function tvSymbolWurzel(s){ return /^MNQ/.test(String(s)) ? 'MNQ' : /^NQ/.test(String(s)) ? 'NQ' : '' }
const hedgeMasterWegStempeln = (p, q, ab) => { spur.stempel.push(ab) }, hedgeMasterWegAusfuehren = async (p) => { spur.zu.push(uhr); p.mt5Baseline.hedge.status = 'geschlossen' }
"""
code = "\n".join([UMGEBUNG, zeile("  const TSX_FLACH_FOLGE ="), zeile("  const TSX_MESSUNG_MAX_MS"), zeile("  const TSX_STAND_MAX_S"), zeile("  function tsxMessungJung("),
                  fn("  function tsxFlachSchnell("), fn("  function hedgeMasterTeilweise("), fn("  function tsxKontoEndung("), fn("  function tsxKontoAusEndung("),
                  fn("  function tsxKontoPasst("), "const tsxKontoExtIdsJetzt = () => []", fn("  function tsxFillBeleg("), zeile("  const _tsxSichtung"), fn("  function tsxSichtungGilt("),
                  fn("  async function hedgeTsxSchnellTick("),
                  fn("  function hedgeScharfDatenTsx("), zeile("  const _tsxPanelEndeVersuch"), zeile("  let _tsxPanelEndeBusy"), fn("  function tsxPanelEndeKandidat("),
                  fn("  async function hedgeTsxPanelEndeTick(")])
lauf = r"""
const T = s => DateEcht.parse('2026-11-10T' + s + 'Z')
const K = 'EXPRESS-V2-DLL-696284-33122225', ANDERES = 'EXPRESS-V2-DLL-696284-99999999'
// Ablauf: je 250 ms ein Tab-Tick. Auge: Messung alle ~400 ms (träge: einzelne Lücken bis 2,2 s), Stand-Alter = seit der letzten Messung
async function fall(o){
  uhr = o.start; _tsxSchnellKonto.clear(); _tsxSchnellLeer.clear(); _tsxGesehenAt.clear(); _hedgeMasterGesehen.clear(); _tsxSichtung.clear(); spur.zu = []; spur.stempel = []
  if(o.altSichtung){ _hedgeMasterGesehen.add('p'); _tsxSichtung.set('p', { ticket: 1111, at: o.start - 600000 }) }   // Sichtung aus einem früheren Lauf (anderes Ticket)
  accounts = [{ id: 'a', externalId: K }]
  const plan = { id: 'p', route: 'tsv2', status: 'planned', richtung: 'buy', masterAccountId: 'a', mt5Baseline: { hedge: { status: 'offen', pc: 'pc-t8wg97', opened_at: new DateEcht(o.hedgeOpen).toISOString(), symbol_nq: 'MNQZ26', ticket: 4711 } } }
  tradePlans = [plan]
  let messung = 0, flachSeit = 0, folge = 0
  for(; uhr <= o.ende; uhr += 250){
    if(uhr >= o.planOpen) plan.status = 'open'
    pulsUnterwegs = (uhr >= o.pulsVon && uhr < o.pulsBis) ? 'Puls-Order' : ''
    const luecke = (o.luecken || []).some(([a, b]) => uhr >= a && uhr < b)
    if(!luecke && uhr - messung >= 400) messung = uhr
    const konto = (o.anderesKonto && uhr >= o.anderesKonto[0] && uhr < o.anderesKonto[1]) ? ANDERES : (uhr >= o.kontoAb ? K : ANDERES)
    const offen = uhr >= o.posVon && uhr < o.posBis
    const flach = !offen && (uhr >= o.posBis || (o.vorFlach && uhr >= o.hedgeOpen && uhr < o.posVon))   // vorFlach: Konto flach zwischen Hedge-Open und Fill
    if(flach){ if(!flachSeit || konto !== K) flachSeit = messung; folge++ } else { flachSeit = 0; folge = 0 }
    antwort = { ok: true, tabs: 1, script: '0.3.4', alter_s: (uhr - messung) / 1000 + 0.05,
      stand: { ts: messung, konto: { kontonr: konto, abgekuerzt: false, liste_offen: false }, ausgeloggt: false,
               positionen: offen && konto === K ? [{ symbol: 'MNQZ6', wurzel: 'MNQ', richtung: 'buy', menge_zahl: 1 }] : [],
               flach: flach && konto === K, flach_folge: flach ? folge : 0, flach_seit: flach && konto === K ? flachSeit : null } }
    if(plan.mt5Baseline.hedge.status === 'offen') await hedgeTsxSchnellTick()
  }
  return { zu: spur.zu.length ? (spur.zu[0] - o.posBis) / 1000 : null, stempel: spur.stempel.length ? (spur.stempel[0] - o.posBis) / 1000 : null,
           vor_fill: spur.zu.length ? spur.zu[0] < o.posVon : false }
}
;(async () => { const out = {}
  const marco3d = { start: T('14:38:00'), kontoAb: T('14:38:05'), hedgeOpen: T('14:38:29.6'), posVon: T('14:38:28'), posBis: T('14:39:10.5'), planOpen: T('14:38:53.8'),
    pulsVon: T('14:38:00'), pulsBis: T('14:39:52'), luecken: [[T('14:38:32'), T('14:38:34')], [T('14:39:00'), T('14:39:02')]], ende: T('14:40:40') }
  out.f3d0c3e06 = await fall(marco3d)
  out.f937e9256 = await fall({ start: T('14:29:10'), kontoAb: T('14:29:12'), hedgeOpen: T('14:29:38.4'), posVon: T('14:29:36'), posBis: T('14:29:56'), planOpen: T('14:30:04.4'),
    pulsVon: T('14:29:10'), pulsBis: T('14:30:06'), ende: T('14:31:00') })
  // Gegenprobe: Auge zeigt ab dem Flach ein ANDERES Konto (Rück-Login woanders hin, dort leer) → nie zu (Schutz 1: nur das Plan-Konto zählt)
  out.anderes_konto = await fall(Object.assign({}, marco3d, { anderesKonto: [T('14:39:10'), T('14:41:00')] }))
  // Gegenprobe: Master nie gesehen (Position nie in der Tabelle) → nie zu
  out.nie_gesehen = await fall(Object.assign({}, marco3d, { posVon: T('14:50:00'), posBis: T('14:38:20') }))
  // Prüfer MUSS 2: zweiter Lauf desselben Plans, Sichtung aus Lauf 1 (anderes Ticket), Konto flach zwischen Hedge-Open und Fill → nie vor dem Fill zu; danach normal
  out.zweiter_lauf = await fall(Object.assign({}, marco3d, { altSichtung: true, vorFlach: true, hedgeOpen: T('14:38:10'), posVon: T('14:38:40') }))
  // Prüfer MUSS 1: Plan-Ende nach dem Panel-Schluss — Hedge so, wie hedgeZuAusRing ihn aus dem echten Ring bucht (level_mt5, grund_copier 'close', kein close_at)
  accounts = [{ id: 'a', externalId: K, firm: 'Topstep' }]
  uhr = T('14:39:20')
  const ring = { status: 'geschlossen', grund: 'level_mt5', grund_copier: 'close', pc: 'pc-t8wg97', closed_at: '2026-11-10T14:39:13Z', ticket: 4711 }
  const pe = (o, h) => Object.assign({ id: 'pe', route: 'tsv2', status: 'open', masterAccountId: 'a', startedAt: '2026-11-10T14:38:00Z', masterSymbol: 'MNQZ6',
    mt5Baseline: { hedge: Object.assign({}, ring, h || {}) } }, o || {})
  const augeSt = (o) => ({ ok: true, tabs: 1, script: '0.3.4', alter_s: 0.1, stand: Object.assign({ ts: uhr - 100, konto: { kontonr: K, abgekuerzt: false, liste_offen: false },
    ausgeloggt: false, positionen: [], flach: true, flach_folge: 5, flach_seit: uhr - 3000 }, o || {}) })
  const ende = async (plan, a) => { _tsxPanelEndeVersuch.clear(); tradePlans = [plan]; spur.zu = []; antwort = a || augeSt(); await hedgeTsxPanelEndeTick(); uhr += 1000; await hedgeTsxPanelEndeTick(); uhr -= 1000; return spur.zu.length }
  out.panel_ende = { ring: await ende(pe()), panel_grund: await ende(pe(null, { grund: 'master_ende_panel', grund_copier: null })),
    eigener_close: await ende(pe(null, { close_at: '2026-11-10T14:39:12Z' })), hand: await ende(pe(null, { grund: 'hand', grund_copier: 'client' })),
    planned: await ende(pe({ status: 'planned' })), alt: await ende(pe({ startedAt: '2026-11-10T15:00:00Z' })), final: await ende(pe({ mt5Baseline: { final: {}, hedge: ring } })),
    anderer_pc: await ende(pe(null, { pc: 'pc-xxx' })),
    auge_position: await ende(pe(), augeSt({ flach: false, flach_folge: 0, positionen: [{ symbol: 'MNQZ6', wurzel: 'MNQ', richtung: 'buy', menge_zahl: 1 }] })),
    auge_anderes_konto: await ende(pe(), augeSt({ konto: { kontonr: ANDERES, abgekuerzt: false, liste_offen: false } })),
    auge_alt: await ende(pe(), Object.assign(augeSt(), { alter_s: 3.5 })), auge_ausgeloggt: await ende(pe(), augeSt({ ausgeloggt: true })),
    auge_folge1: await ende(pe(), augeSt({ flach_folge: 1 })), zu_spaet: await ende(pe(null, { closed_at: '2026-11-10T14:20:00Z' })) }
  // Daten fürs Panel: Plan-Konto, MNQ, Richtung, TopstepX-Konten der ID, gesehen nur mit Sichtung zu DIESEM Ticket
  const pd = { id: 'pd', route: 'tsv2', masterAccountId: 'a', richtung: 'buy', masterContracts: 1, mt5Baseline: { hedge: { symbol_nq: 'MNQZ26', ticket: 9 } } }
  _tsxSichtung.clear(); const d1 = hedgeScharfDatenTsx(pd); _tsxSichtung.set('pd', { ticket: 8, at: uhr }); const d2 = hedgeScharfDatenTsx(pd)
  _tsxSichtung.set('pd', { ticket: 9, at: uhr }); const d3 = hedgeScharfDatenTsx(pd)
  out.daten = { d1, g2: d2.gesehen, g3: d3.gesehen }
  out.warnungen = warnungen.slice(0, 5)
  print(JSON.stringify(out))
})().catch(e => print('FEHLER ' + e + ' ' + (e && e.stack)))
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(code + "\n" + lauf)
    pfad = f.name
r = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=120)
os.unlink(pfad)
try:
    e = json.loads(r.stdout.strip().splitlines()[-1])
except Exception:
    print(r.stdout, r.stderr)
    sys.exit(1)
f3, f9, kw, nie = e["f3d0c3e06"], e["f937e9256"], e["anderes_konto"], e["nie_gesehen"]
fehler = 0
for name, ok in (("3d0c3e06: Fusion < 2 s nach flach_seit (vorher 71,9 s)", f3["zu"] is not None and 0 <= f3["zu"] < 2),
                 ("3d0c3e06: Master-Ende-Stempel = flach_seit des Auges", f3["stempel"] is not None and abs(f3["stempel"]) < 0.5),
                 ("937e9256: Fusion < 2 s nach flach_seit, schon im eigenen Lauf (vorher nie)", f9["zu"] is not None and 0 <= f9["zu"] < 2),
                 ("Auge zeigt anderes Konto: nie zu", kw["zu"] is None),
                 ("Master nie gesehen: nie zu", nie["zu"] is None),
                 ("Zweiter Lauf, Sichtung aus Lauf 1 (anderes Ticket), Konto vor dem Fill flach: nie vor dem Fill zu (Prüfer MUSS 2)", not e["zweiter_lauf"]["vor_fill"]),
                 ("Zweiter Lauf: nach Fill + Flach trotzdem < 2 s zu", e["zweiter_lauf"]["zu"] is not None and 0 <= e["zweiter_lauf"]["zu"] < 2),
                 ("Panel-Schluss wie aus dem echten Ring (level_mt5/close, kein close_at) + Auge flach: Plan-Ende genau einmal (Prüfer MUSS 1)", e["panel_ende"]["ring"] == 1),
                 ("Panel-Schluss mit Grund master_ende_panel: Plan-Ende", e["panel_ende"]["panel_grund"] == 1),
                 ("kein Ende: eigener Close (close_at) / hand / planned / alter Lauf / final / anderer PC / > 15 min",
                  all(e["panel_ende"][k] == 0 for k in ("eigener_close", "hand", "planned", "alt", "final", "anderer_pc", "zu_spaet"))),
                 ("kein Ende ohne Auge-Beweis: Position da / anderes Konto / Stand alt / ausgeloggt / Folge 1",
                  all(e["panel_ende"][k] == 0 for k in ("auge_position", "auge_anderes_konto", "auge_alt", "auge_ausgeloggt", "auge_folge1"))),
                 ("Daten fürs Panel: quelle tsx, Plan-Konto, MNQ, buy; gesehen nur mit Sichtung zu diesem Ticket",
                  e["daten"]["d1"] == {"quelle": "tsx", "ext_id": "EXPRESS-V2-DLL-696284-33122225", "wurzel": "MNQ", "richtung": "buy", "menge": 1, "nachbarn": [], "gesehen": False}
                  and e["daten"]["g2"] is False and e["daten"]["g3"] is True),
                 ("hedgeZuAusRing bucht den Ring-Grund als grund_copier und ohne close_at als level_mt5 (Grundlage für das Plan-Ende)",
                  "grund_copier: zu.grund || null" in HTML and "hedgeGrundEcht(Object.assign({}, hAkt, { grund: 'level_mt5', grund_copier: zu.grund }))" in HTML),
                 ("keine abgefangene Ausnahme im Tick (z. B. ReferenceError in der Konsolenzeile)", not e["warnungen"])):
    print(("ok   " if ok else "FEHL ") + name)
    fehler += 0 if ok else 1
print(json.dumps(e))
print("\nALLES OK" if not fehler else f"\n{fehler} FEHLER")
sys.exit(1 if fehler else 0)
