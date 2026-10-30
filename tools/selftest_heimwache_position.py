#!/usr/bin/env python3
"""Selbsttest HEIM-WACHE-SCHLEIFE (30.10.2026, Chris pc-c19p2l, Orbit f35ba6ae Apex …0005: Reader liest gekürzt „PAAPEX668794000000",
7 Apex-Konten mit diesem Anfang; ein Echo-Signal (nur MT5) entwertete den Beleg → Heim-Wache hielt das Konto für fremd → 90 s → Rück-Login,
sechs Rundläufe à ~100 s in 25 min). Prüft über JavaScriptCore:
  (a) pulsSignalOhneTv + der 250-ms-Takt: Signal-Lauf mit mt5/mt5v2/tsv2-Plan setzt _pulsAktivAt NICHT, tvv2/unbekannt/Balance-Lesung schon;
  (b) heimPositionPasst: Plan-Position im Reader = zu Hause, fail-closed bei zweitem passenden Plan, fremdem Text, altem Stand, Puls unterwegs;
  (c) hwWacheInfo-Felder + Railway heimweg_wache_daten (nur bekannte Felder, gekürzt).
Aufruf:  python3 tools/selftest_heimwache_position.py"""
import ast
import json
import os
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
APP = open(os.path.join(W, "app.py"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
fehler = 0


def soll(name, ok):
    global fehler
    print(("ok   " if ok else "FEHL ") + name)
    fehler += 0 if ok else 1


def js_funktion(name):
    i = HTML.index(f"  function {name}(")
    return HTML[i:HTML.index("\n  }\n", i) + 4]


def zeile(anfang):
    i = HTML.index(anfang)
    return HTML[i:HTML.index("\n", i)]


# Umgebung des PC-Tabs als Stub: Konten von Chris (7 Apex), Orbit-Plan …0005 mit echtem Fill, Echo-Plan (mt5)
UMGEBUNG = r"""
const KONTO_KURZ_MIN = 12
function hedgeKontoPasst(t, id){ return String(t).split(/[^A-Z0-9]+/).includes(id) }
let accounts = [1,2,3,4,5,6,7].map(n => ({ id: 'a' + n, externalId: 'PAAPEX668794000000' + n }))
let _unterwegs = '', _osActive = null, _tvBalLesenLaeuft = new Set()
function hedgePulsUnterwegs(){ return _unterwegs }
const ORBIT = { id: 'f35ba6ae', status: 'open', route: 'tvv2', richtung: 'buy', masterContracts: 2, masterSymbol: null, masterAccountId: 'a5',
  mt5Baseline: { tv: { einstieg_symbol: 'NQZ6', einstieg_quelle: 'fill', einstieg_nq: 28880 }, hedge: { pc: 'pc-c19p2l' } } }
const ECHO = { id: '81bc9461', status: 'open', route: 'mt5', richtung: 'sell', masterContracts: 0.04, masterSymbol: 'NDX100' }
let tradePlans = [ORBIT, ECHO]
const POS = { symbol: 'NQZ6', wurzel: 'NQ', richtung: 'buy', menge_zahl: 2, avg_fill: 28880, pnl: '+2,030.00USD' }
const ST = (o) => Object.assign({ konto: 'PAAPEX668794000000', positionen_tab: 'puls-abc', positionen_ok: true, positionen_alter_s: 1, positionen: [POS] }, o || {})
let _kontoBeleg = { ext: '', at: 0, voll: false }, _pulsAktivAt = 0, _pulsAktivGrund = ''
"""
code = "\n".join([UMGEBUNG, js_funktion("tvSymbolWurzel"), js_funktion("kontoTextBezug"), js_funktion("kontoTextEindeutig"),
                  zeile("  function kontoExtIds()"), js_funktion("kurzPlanFill"), zeile("  const PULS_OHNE_TV_ROUTEN"), js_funktion("pulsSignalOhneTv"),
                  js_funktion("heimPlanPosition"), js_funktion("heimPositionTrifft"), js_funktion("heimPositionPasst"), js_funktion("hwWacheInfo")])
# der Takt aus prophos.html als Funktion (statt setInterval), damit der Test ihn Schritt für Schritt fahren kann
takt = zeile("  setInterval(() => { try{ const g = hedgePulsUnterwegs();")
soll("Takt-Zeile vorhanden und nimmt Signal-Läufe ohne TV aus", "g === 'Signal-Lauf' && pulsSignalOhneTv()" in takt)
koerper = takt[takt.index("try{"):takt.rindex("}, 250)")]
code += "\nfunction taktEinmal(){ " + koerper + " }\n"

lauf = r"""
const out = {}
// (a) Signal-Läufe
_unterwegs = 'Signal-Lauf'; _osActive = { planId: '81bc9461' }; _pulsAktivAt = 0; taktEinmal(); out.a_echo = _pulsAktivAt
ECHO.route = 'mt5v2'; _pulsAktivAt = 0; taktEinmal(); out.a_mt5v2 = _pulsAktivAt
ECHO.route = 'tsv2'; _pulsAktivAt = 0; taktEinmal(); out.a_tsv2 = _pulsAktivAt
ECHO.route = 'mt5'
_osActive = { planId: 'f35ba6ae' }; _pulsAktivAt = 0; taktEinmal(); out.a_tvv2 = _pulsAktivAt > 0
_osActive = { planId: 'gibtsnicht' }; _pulsAktivAt = 0; taktEinmal(); out.a_unbekannt = _pulsAktivAt > 0
_osActive = { planId: '81bc9461' }; _tvBalLesenLaeuft.add('x'); _pulsAktivAt = 0; taktEinmal(); out.a_mit_balance = _pulsAktivAt > 0; _tvBalLesenLaeuft.clear()
_unterwegs = 'Rück-Login ins Big-Trade-Konto'; _pulsAktivAt = 0; taktEinmal(); out.a_rueckLogin = _pulsAktivAt > 0; out.a_grund = _pulsAktivGrund
_unterwegs = ''; _osActive = null
// (b) Plan-Position als Heim-Beweis
out.b_chris = heimPositionPasst(ST(), ORBIT, 'PAAPEX6687940000005', tradePlans)
out.b_eindeutig_text = kontoTextEindeutig('PAAPEX668794000000', 'PAAPEX6687940000005', kontoExtIds())
out.b_fremder_text = heimPositionPasst(ST({ konto: 'TDFYSL150463012290' }), ORBIT, 'PAAPEX6687940000005', tradePlans)
out.b_alt = heimPositionPasst(ST({ positionen_alter_s: 9 }), ORBIT, 'PAAPEX6687940000005', tradePlans)
out.b_kein_puls_tab = heimPositionPasst(ST({ positionen_tab: 't123' }), ORBIT, 'PAAPEX6687940000005', tradePlans)
out.b_blind = heimPositionPasst(ST({ positionen_ok: false }), ORBIT, 'PAAPEX6687940000005', tradePlans)
_unterwegs = 'Puls-Order'; out.b_unterwegs = heimPositionPasst(ST(), ORBIT, 'PAAPEX6687940000005', tradePlans); _unterwegs = ''
out.b_flach = heimPositionPasst(ST({ positionen: [] }), ORBIT, 'PAAPEX6687940000005', tradePlans)
out.b_falscher_fill = heimPositionPasst(ST({ positionen: [Object.assign({}, POS, { avg_fill: 28881.25 })] }), ORBIT, 'PAAPEX6687940000005', tradePlans)
out.b_falsche_menge = heimPositionPasst(ST({ positionen: [Object.assign({}, POS, { menge_zahl: 1 })] }), ORBIT, 'PAAPEX6687940000005', tradePlans)
out.b_gegenrichtung = heimPositionPasst(ST({ positionen: [Object.assign({}, POS, { richtung: 'sell' })] }), ORBIT, 'PAAPEX6687940000005', tradePlans)
// zweiter offener Plan derselben ID mit gleicher Position (Fill unbekannt) → kein Beweis; mit anderem Fill → Beweis bleibt
const ZWEI = { id: 'zwei', status: 'open', route: 'tvv2', richtung: 'buy', masterContracts: 2, masterSymbol: 'NQZ6', masterAccountId: 'a3', mt5Baseline: {} }
out.b_zweiter_ohne_fill = heimPositionPasst(ST(), ORBIT, 'PAAPEX6687940000005', [ORBIT, ECHO, ZWEI])
ZWEI.mt5Baseline = { tv: { einstieg_quelle: 'fill', einstieg_nq: 28880 } }
out.b_zweiter_gleicher_fill = heimPositionPasst(ST(), ORBIT, 'PAAPEX6687940000005', [ORBIT, ECHO, ZWEI])
ZWEI.mt5Baseline = { tv: { einstieg_quelle: 'fill', einstieg_nq: 28910.5 } }
out.b_zweiter_anderer_fill = heimPositionPasst(ST(), ORBIT, 'PAAPEX6687940000005', [ORBIT, ECHO, ZWEI])
// Plan ohne echten Fill: Wurzel/Richtung/Kontrakte reichen, aber nur ohne Doppelgänger
const OHNE = Object.assign({}, ORBIT, { id: 'ohne', mt5Baseline: { tv: { einstieg_symbol: 'NQZ6' } } })
out.b_ohne_fill = heimPositionPasst(ST(), OHNE, 'PAAPEX6687940000005', [OHNE])
// Gegenprüfung 30.10.2026: review-Plan mit gleicher Position, TV-Plan ohne Wurzel = Doppelgänger; MT5-Plan ohne Wurzel nicht
out.b_review = heimPositionPasst(ST(), ORBIT, 'PAAPEX6687940000005', [ORBIT, Object.assign({}, ZWEI, { status: 'review', mt5Baseline: {} })])
out.b_tv_ohne_wurzel = heimPositionPasst(ST(), ORBIT, 'PAAPEX6687940000005', [ORBIT, { id: 'x', status: 'open', route: 'tvv2', richtung: 'buy', masterContracts: 2, masterSymbol: null }])
out.b_mt5_ohne_wurzel = heimPositionPasst(ST(), ORBIT, 'PAAPEX6687940000005', [ORBIT, { id: 'y', status: 'open', route: 'mt5', richtung: null, masterContracts: 0, masterSymbol: null }])
out.c_klebt = hwWacheInfo('fremd', ST({ konto: 'PAAPEX6687940000005153 153,342.72 USD' }), 'PAAPEX6687940000005', 1000).text
// zwei gleiche Zeilen in der Tabelle → unklar
out.b_zwei_zeilen = heimPositionPasst(ST({ positionen: [POS, Object.assign({}, POS)] }), ORBIT, 'PAAPEX6687940000005', tradePlans)
// (c) Wache-Info
_kontoBeleg = { ext: 'PAAPEX6687940000005', at: Date.now() - 125000, voll: true }; _pulsAktivAt = Date.now() - 64000; _pulsAktivGrund = 'Signal-Lauf'
out.c = hwWacheInfo('fremd', ST(), 'PAAPEX6687940000005', 91600)
out.c_blind = hwWacheInfo('blind', ST({ blind_grund: 'kein Leer-Beweis: Leer-Text nicht erkannt | Konto: PAAPEX668794000000' }), 'PAAPEX6687940000005', 40000)
print(JSON.stringify(out))
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

soll("(a) Echo-Signal (mt5) setzt _pulsAktivAt nicht", e["a_echo"] == 0)
soll("(a) Echo-V2-Signal (mt5v2) setzt _pulsAktivAt nicht", e["a_mt5v2"] == 0)
soll("(a) Topstep-Signal (tsv2) setzt _pulsAktivAt nicht", e["a_tsv2"] == 0)
soll("(a) Orbit-Signal (tvv2) setzt _pulsAktivAt", e["a_tvv2"] is True)
soll("(a) Signal mit unbekanntem Plan setzt _pulsAktivAt (fail-closed)", e["a_unbekannt"] is True)
soll("(a) Echo-Signal + Balance-Lesung zugleich setzt _pulsAktivAt", e["a_mit_balance"] is True)
soll("(a) Rück-Login setzt _pulsAktivAt, Grund gemerkt", e["a_rueckLogin"] is True and e["a_grund"] == "Rück-Login ins Big-Trade-Konto")
soll("(b) Chris-Fall: Text nicht eindeutig (7 Apex)", e["b_eindeutig_text"] is False)
soll("(b) Chris-Fall: Plan-Position im Reader = zu Hause", e["b_chris"] is True)
for k, txt in (("b_fremder_text", "fremder Konto-Text"), ("b_alt", "Stand > 5 s"), ("b_kein_puls_tab", "nicht aus dem Puls-Chrome"),
               ("b_blind", "positionen_ok false"), ("b_unterwegs", "Puls unterwegs"), ("b_flach", "keine Position"),
               ("b_falscher_fill", "Avg Fill ≠ Plan-Fill"), ("b_falsche_menge", "Kontrakte ≠ Plan"), ("b_gegenrichtung", "Gegenrichtung"),
               ("b_zweiter_ohne_fill", "zweiter offener Plan, Fill unbekannt"), ("b_zweiter_gleicher_fill", "zweiter offener Plan, gleicher Fill"),
               ("b_zwei_zeilen", "zwei passende Zeilen")):
    soll(f"(b) kein Beweis: {txt}", e[k] is False)
soll("(b) kein Beweis: review-Plan mit gleicher Position", e["b_review"] is False)
soll("(b) kein Beweis: anderer TV-Plan ohne Wurzel (fail-closed)", e["b_tv_ohne_wurzel"] is False)
soll("(b) MT5-Plan ohne Wurzel stört nicht", e["b_mt5_ohne_wurzel"] is True)
soll("(c) Wache-Info: angeklebter Balance-Anfang fällt weg", e["c_klebt"] == "PAAPEX6687940000005")
soll("(b) zweiter offener Plan mit anderem Fill → Beweis bleibt", e["b_zweiter_anderer_fill"] is True)
soll("(b) Plan ohne echten Fill: Wurzel/Richtung/Kontrakte reichen", e["b_ohne_fill"] is True)
c = e["c"]
soll("(c) Wache-Info fremd: Felder", c.get("art") == "fremd" and c.get("text") == "PAAPEX668794000000" and c.get("bezug") == "kurz"
     and c.get("beleg_ext_passt") is True and 120 <= c.get("beleg_alter_s", 0) <= 130 and 60 <= c.get("puls_aktiv_vor_s", 0) <= 70
     and c.get("puls_aktiv_grund") == "Signal-Lauf" and c.get("lage_s") == 92 and "blind_grund" not in c)
soll("(c) Wache-Info blind: Grund ohne Konto-Anhang", e["c_blind"].get("blind_grund") == "kein Leer-Beweis: Leer-Text nicht erkannt")

# Verdrahtung am Quelltext
soll("Heim-Wache fragt heimPositionPasst", "heimKontoPasst(st.konto, konto) || heimPositionPasst(st, bt, konto, tradePlans)" in HTML)
soll("Wache-Info vor beiden Wache-Heimwegen", HTML.count("_hwWacheInfo = hwWacheInfo(") == 2)
soll("Heimweg-Alarm schickt wache nur bei Heim-Wache", "const wache = /Heim-Wache/.test(String(grund || '')) ? _hwWacheInfo : null" in HTML)

# Railway: heimweg_wache_daten (REIN) aus app.py
baum = ast.parse(APP)
fn = next(n for n in baum.body if isinstance(n, ast.FunctionDef) and n.name == "heimweg_wache_daten")
ns = {}
exec(compile(ast.Module(body=[fn], type_ignores=[]), "app.py", "exec"), ns)
hw = ns["heimweg_wache_daten"]
d = hw({"art": "fremd", "text": "PAAPEX668794000000" * 5, "bezug": "kurz", "beleg_alter_s": 125.4, "puls_aktiv_vor_s": 64, "lage_s": 92,
        "beleg_ext_passt": True, "puls_aktiv_grund": "Signal-Lauf", "boese": "x" * 999, "balance": 153342.72})
soll("Railway: bekannte Felder übernommen, Text gekürzt", d.get("art") == "fremd" and len(d.get("text")) == 40 and d.get("beleg_alter_s") == 125
     and d.get("beleg_ext_passt") is True and d.get("puls_aktiv_grund") == "Signal-Lauf")
soll("Railway: fremde Felder (Beträge) fallen weg", "boese" not in d and "balance" not in d)
soll("Railway: Unsinn → None", hw(None) is None and hw("x") is None and hw({"beleg_alter_s": True, "lage_s": -1}) is None)
soll("Railway: /alarm/heimweg hängt wache an daten", 'w = heimweg_wache_daten(d.get("wache"))' in APP and 'daten["wache"] = w' in APP)

print(f"\n{'ALLES OK' if not fehler else f'{fehler} FEHLER'}")
sys.exit(1 if fehler else 0)
