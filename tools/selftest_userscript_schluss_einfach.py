#!/usr/bin/env python3
"""Selbsttest USERSCRIPT-SCHLUSS EINFACH (30.10.2026, Finn „Idee 1": „Puls hat das Konto bestätigt, Position sicher weg, dann Hedge sofort zu"): der Balance-Beweis
(kurzEndeBeweis) ist nur noch Nachkontrolle. Über JavaScriptCore mit den echten Werten aus trade_plans (b74d6b68, 2676339d, 3be7bc94): jetzt zu; Balance fehlt: zu + ok false;
Bündel im selben Login: bleibt gesperrt, auch wenn ein anderer Grund früher zuschlüge; Puls unterwegs/Anker ungültig: kurzEndeKontoPasst bleibt nein. Dazu Railway: 🔴 kurz_balance_nein,
erst ab > 20 Pkt neben dem Fenster, Balance fehlt nur 🟠 kurz_balance_fehlt, Radar-Alarmtext mit reader_kurz_nein. Aufruf:  python3 tools/selftest_userscript_schluss_einfach.py"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta

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


UMGEBUNG = r"""
const window = {}, KONTO_KURZ_MIN = 12
function hedgeKontoPasst(t, id){ return String(t).split(/[^A-Z0-9]+/).includes(id) }
function tvGeldText(v){ const n = Number(String(v).replace(/[^0-9.\-]/g, '')); return isFinite(n) ? n : null }
function tvBalanceAus(s){ return { balance: s && typeof s.Balance === 'number' ? s.Balance : null, equity: s && typeof s.Equity === 'number' ? s.Equity : null } }
let _unterwegs = '', _pulsAktivAt = 0, tradePlans = [], accounts = []
function hedgePulsUnterwegs(){ return _unterwegs }
let _osActive = null, _tvBalLesenLaeuft = new Set()
const kurzPolar = () => false
const _kurzAnker = new Map(), _kurzFenster = new Map()
"""
code = "\n".join([UMGEBUNG, zeile("  const KURZ_TOL_PKT"), js_funktion("kontoTextBezug"), js_funktion("kurzPlanFill"), js_funktion("kurzEndeEntscheid"), js_funktion("kurzUmschalterBalance"),
                  js_funktion("summaryKeysKurz"), zeile("  const kurzEndeSperrt ="), js_funktion("kurzEndeBeweis"), js_funktion("kurzAnkerGilt"), js_funktion("kurzEndeKontoPasst"),
                  zeile("  const PULS_OHNE_TV_ROUTEN"), js_funktion("pulsSignalOhneTv"), js_funktion("hedgeTvUnterwegs")])

# echte Werte: mt5_baseline.tv und hedge.reader_kurz_nein
FAELLE = {
    "b74d6b68": dict(richtung="buy", kt=2, b0=105953.3, e=29011, b1=103467.1, f=28952.75, konto="PAAPEX668794000000", ext="PAAPEX6687940000003", exit=28948.85),
    "2676339d": dict(richtung="sell", kt=2, b0=98303.8, e=28894.75, b1=96987.6, f=28922.75, konto="PAAPEX684332000000", ext="PAAPEX6843320000004", exit=28927.66),
    "3be7bc94": dict(richtung="sell", kt=2, b0=152196.4, e=28973.75, b1=152470.6, f=28911, konto="FTDFYSLX1503720604", ext="FTDFYSLX150372060459", exit=28905.2, wz="MNQ"),
}
lauf = "const F = " + json.dumps(FAELLE) + r""", out = {}
const plan = (id, c) => ({ id, status: 'open', masterAccountId: 'a' + id, richtung: c.richtung, masterContracts: c.kt, mt5Baseline: { tv: { balance_start: c.b0, einstieg_quelle: 'fill', einstieg_nq: c.e }, hedge: {} } })
const stand = (c, o) => Object.assign({ konto: c.konto, summary_alter_s: 1, summary: { Balance: c.b1, Equity: c.b1 }, positionen_tab: 'puls-a', positionen_ok: true, positionen_alter_s: 0.2, positionen: [] }, o || {})
const fenster = (id, c) => _kurzFenster.set(id, { lo: c.f, hi: c.f, wz: c.wz || 'NQ', at: Date.now(), zu: Date.now() })
for(const id of Object.keys(F)){ const c = F[id], p = plan(id, c); accounts = [{ id: p.masterAccountId, externalId: c.ext }]; tradePlans = [p]; fenster(id, c)
  const k = kurzEndeBeweis(p, c.ext, stand(c), c.wz || 'NQ'); out[id] = { ok: k.ok, sperrt: kurzEndeSperrt(k), exit: k.exit, grund: k.grund } }
const c = F.b74d6b68, p = plan('b74d6b68', c), S = kurzEndeSperrt
accounts = [{ id: p.masterAccountId, externalId: c.ext }]; tradePlans = [p]; fenster('b74d6b68', c)
{ const k = kurzEndeBeweis(p, c.ext, stand(c, { summary: { 'Net Liq': 1 } }), 'NQ'); out.balance_fehlt = { ok: k.ok, sperrt: S(k), grund: k.grund, keys: k.summary_keys } }
{ const k = kurzEndeBeweis(p, c.ext, stand(c, { summary_alter_s: 60 }), 'NQ'); out.summary_alt = { ok: k.ok, sperrt: S(k), grund: k.grund } }
_kurzFenster.delete('b74d6b68')
{ const k = kurzEndeBeweis(p, c.ext, stand(c), 'NQ'); out.ohne_fenster = { ok: k.ok, sperrt: S(k), grund: k.grund } }
fenster('b74d6b68', c)
// Beweis geht durch: Ausstieg im Fenster
{ const c2 = Object.assign({}, c, { f: 28949 }); fenster('b74d6b68', c2); const k = kurzEndeBeweis(p, c.ext, stand(c), 'NQ'); out.passt = { ok: k.ok, sperrt: S(k) } }
// Bündel: anderer offener Plan auf Konto mit demselben gekürzten Text — sperrt, auch wenn das Fenster fehlt oder die Zusammenfassung alt ist
const q = { id: 'q', status: 'open', masterAccountId: 'aq' }; accounts = [{ id: p.masterAccountId, externalId: c.ext }, { id: 'aq', externalId: 'PAAPEX6687940000004' }]; tradePlans = [p, q]; fenster('b74d6b68', c)
{ const k = kurzEndeBeweis(p, c.ext, stand(c), 'NQ'); out.buendel = { ok: k.ok, sperrt: S(k), grund: k.grund } }
{ const k = kurzEndeBeweis(p, c.ext, stand(c, { summary_alter_s: 60 }), 'NQ'); out.buendel_alt = { ok: k.ok, sperrt: S(k) } }
_kurzFenster.delete('b74d6b68')
{ const k = kurzEndeBeweis(p, c.ext, stand(c), 'NQ'); out.buendel_ohne_fenster = { sperrt: S(k) } }
tradePlans = [p, Object.assign({}, q, { status: 'review', endedAt: new Date(Date.now() - 3600000).toISOString() })]; fenster('b74d6b68', c)
{ const k = kurzEndeBeweis(p, c.ext, stand(c), 'NQ'); out.nachbar_beendet = { sperrt: S(k) } }
tradePlans = [p, Object.assign({}, q, { status: 'review', endedAt: new Date(Date.now() - 30000).toISOString() })]
{ const k = kurzEndeBeweis(p, c.ext, stand(c), 'NQ'); out.nachbar_frisch = { sperrt: S(k) } }
tradePlans = [p]
out.voller_text_null = S(null)
// Anker bleibt die Tür: kurzEndeKontoPasst
const st = stand(c), ank = (o) => _kurzAnker.set(c.ext.toUpperCase(), Object.assign({ text: c.konto, at: 1000, quelle: 'fill' }, o || {}))
ank(); out.anker_gilt = kurzEndeKontoPasst(c.konto, c.ext, st)
_unterwegs = 'Puls-Order'; out.anker_puls_unterwegs = kurzEndeKontoPasst(c.konto, c.ext, st); _unterwegs = ''
_pulsAktivAt = 2000; out.anker_nach_puls = kurzEndeKontoPasst(c.konto, c.ext, st); _pulsAktivAt = 0
ank({ text: 'PAAPEX670837000000' }); out.anker_anderer_text = kurzEndeKontoPasst(c.konto, c.ext, st)
_kurzAnker.clear(); out.anker_fehlt = kurzEndeKontoPasst(c.konto, c.ext, st)
ank(); out.anker_nicht_puls_tab = kurzEndeKontoPasst(c.konto, c.ext, stand(c, { positionen_tab: 't1' }))
// Signal-Lauf ohne TV (Echo/Nova): für Anker und Ende-Pfade nicht unterwegs; alles andere bleibt unterwegs
const sig = (route, o) => { tradePlans = [p, { id: 's', route, status: 'open' }]; _osActive = { planId: (o && o.plan) || 's' }; _unterwegs = (o && o.g) || 'Signal-Lauf'; _tvBalLesenLaeuft = new Set((o && o.bal) ? ['x'] : [])
  ank(); const r = { u: hedgeTvUnterwegs(), anker: kurzEndeKontoPasst(c.konto, c.ext, st) }; _unterwegs = ''; _osActive = null; _tvBalLesenLaeuft = new Set(); return r }
out.sig_mt5 = sig('mt5'); out.sig_mt5v2 = sig('mt5v2'); out.sig_tsv2 = sig('tsv2'); out.sig_tvv2 = sig('tvv2'); out.sig_unbekannt = sig('mt5', { plan: 'weg' }); out.sig_balance = sig('mt5', { bal: true }); out.rueck_login = sig('mt5', { g: 'Rück-Login ins Big-Trade-Konto' }); out.puls_order = sig('tsv2', { g: 'Puls-Order' })
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

for id_, c in FAELLE.items():
    x = e[id_]
    soll(f"{id_}: Beweis fällt durch wie live (Ausstieg {c['exit']}), schließt jetzt trotzdem", x["ok"] is False and x["sperrt"] is False and abs(x["exit"] - c["exit"]) < 0.02 and "außerhalb" in x["grund"])
soll("Balance fehlt: Hedge zu, ok false, Grund + Label-Namen bleiben", e["balance_fehlt"] == {"ok": False, "sperrt": False, "grund": "Balance fehlt", "keys": ["Net Liq"]})
soll("Zusammenfassung alt: Hedge zu", e["summary_alt"]["sperrt"] is False and e["summary_alt"]["ok"] is False)
soll("Fenster fehlt: Hedge zu", e["ohne_fenster"]["sperrt"] is False and e["ohne_fenster"]["ok"] is False)
soll("Beweis passt: Hedge zu, ok true", e["passt"] == {"ok": True, "sperrt": False})
soll("Bündel im selben Login: bleibt gesperrt", e["buendel"]["sperrt"] is True and "selben gekürzten Login" in e["buendel"]["grund"])
soll("Bündel schlägt jeden anderen Grund (Zusammenfassung alt, Fenster fehlt)", e["buendel_alt"]["sperrt"] is True and e["buendel_ohne_fenster"]["sperrt"] is True)
soll("Nachbarkonto längst beendet (review, 1 h): sperrt nicht", e["nachbar_beendet"]["sperrt"] is False)
soll("Nachbarkonto gerade beendet (review, 30 s): sperrt", e["nachbar_frisch"]["sperrt"] is True)
soll("Voller Kontotext (kurz = null): schließt", e["voller_text_null"] is False)
soll("Anker gilt: Tür offen", e["anker_gilt"] is True)
for k, t in (("anker_puls_unterwegs", "Puls unterwegs"), ("anker_nach_puls", "Puls seit dem Anker aktiv"), ("anker_anderer_text", "Text anders"), ("anker_fehlt", "kein Anker"), ("anker_nicht_puls_tab", "nicht Puls-Tab")):
    soll(f"Anker ungültig bleibt gesperrt: {t}", e[k] is False)

for k, t in (("sig_mt5", "Echo"), ("sig_mt5v2", "Echo V2"), ("sig_tsv2", "Nova")):
    soll(f"Signal-Lauf {t}: nicht unterwegs, Anker gilt", e[k] == {"u": "", "anker": True})
for k, t in (("sig_tvv2", "Orbit-Signal"), ("sig_unbekannt", "Plan unbekannt"), ("sig_balance", "Balance-Lesung zugleich")):
    soll(f"Signal-Lauf {t}: bleibt unterwegs, Anker gesperrt", e[k]["u"] == "Signal-Lauf" and e[k]["anker"] is False)
soll("Rück-Login und Puls-Order: bleiben unterwegs", e["rueck_login"]["anker"] is False and e["puls_order"]["u"] == "Puls-Order")
_r = HTML[HTML.index("  async function hedgeReaderSchnellTick("):HTML.index("  setInterval(hedgeReaderSchnellTick")]
soll("Schnell-Wächter fragt nur hedgeTvUnterwegs", "hedgeTvUnterwegs()" in _r and "hedgePulsUnterwegs()" not in _r)
soll("1-s-Wächter fragt nur hedgeTvUnterwegs", "const unterwegs = hedgeTvUnterwegs()" in HTML and "const unterwegs = hedgePulsUnterwegs()" not in HTML)
_h = js_funktion("hedgePulsUnterwegs")
soll("hedgePulsUnterwegs selbst unverändert", "if(_osActive) return 'Signal-Lauf'" in _h)

# Verdrahtung beider Ende-Pfade
soll("Schnell-Wächter: nur Sperre hält auf", "if(kurzEndeSperrt(kurz)){ kurzEndeMelden(p, kurz); continue }" in HTML)
soll("1-s-Wächter: nur Sperre hält auf", "if(kurzEndeSperrt(kurz)) kurzEndeMelden(p, kurz)\n              else {" in HTML)
soll("Kein 3,6-s-Warten bei gekürztem Text", "else if(!kurz && p.route !== 'tsv2'){ try{ _balR = await hedgeReaderEndBalance" in HTML)
soll("Busy/Backoff: Ergebnis wird trotzdem geschrieben", "if(zusatzKurz && !(rsW && rsW.ok))" in HTML)
soll("kein Pfad mehr, der bei !ok abbricht", "if(kurz && !kurz.ok){ kurzEndeMelden(p, kurz); continue }" not in HTML)
soll("reader_kurz geht MIT dem Schließ-Auftrag raus, inkl. ok", "reader_kurz: { ok: kurz.ok === true," in HTML and "hedgeSoloSchliessen(p, 'master_ende_reader', kurs, zusatzKurz)" in HTML)
soll("End-Balance nur aus bestandenem Beweis", "if(kurz && kurz.ok && kurz.b1 > 1000) _balR" in HTML)

# Railway: alarm_ereignisse mit dem Lader aus selftest_alarme
sys.path.insert(0, os.path.join(W, "tools"))
import selftest_alarme as sa  # noqa: E402
ns = sa.lade()
jetzt = datetime(2026, 10, 30, 10, 0, tzinfo=timezone.utc)
iso = lambda s: (jetzt - timedelta(seconds=s)).isoformat()   # noqa: E731
basis = dict(user_id="u", route="tvv2", master_name="100k PAAPEX6687940000003", master_firm="Apex Trader", status="review", started_at=iso(600), ended_at=iso(30))
RK = {"ok": False, "grund": "Ausstieg 28948.85 außerhalb 28952.75–28952.75 ± 3", "exit": 28948.85, "b1": 103467.1, "lo": 28952.75, "hi": 28952.75}
plaene = [
    dict(basis, id="a", hedge={"status": "geschlossen", "grund": "master_ende_reader", "closed_at": iso(20), "reader_kurz": dict(RK, exit=28920.0)}),
    dict(basis, id="a2", hedge={"status": "geschlossen", "grund": "master_ende_reader", "closed_at": iso(20), "reader_kurz": RK}),
    dict(basis, id="a3", hedge={"status": "geschlossen", "grund": "master_ende_reader", "closed_at": iso(20), "reader_kurz": dict(RK, exit=28972.75)}),
    dict(basis, id="a4", hedge={"status": "geschlossen", "grund": "master_ende_reader", "closed_at": iso(20), "reader_kurz": dict(RK, exit=28972.76)}),
    dict(basis, id="b", hedge={"status": "geschlossen", "grund": "master_ende_reader", "closed_at": iso(20), "reader_kurz": dict(RK, ok=True)}),
    dict(basis, id="c", hedge={"status": "geschlossen", "grund": "master_ende_reader", "closed_at": iso(9000), "reader_kurz": RK}),
    dict(basis, id="d", hedge={"status": "geschlossen", "grund": "master_ende_reader", "closed_at": iso(20), "reader_kurz": {"ok": False, "grund": "Balance fehlt", "exit": None, "b1": None}}),
    dict(basis, id="e", hedge={"status": "schliesst", "grund": "master_ende_reader", "reader_kurz": RK}),
    dict(basis, id="f", hedge={"status": "geschlossen", "grund": "sl_feed", "closed_at": iso(20), "reader_kurz_nein": {"grund": "anderer offener Plan im selben gekürzten Login"}}),
    dict(basis, id="g", hedge={"status": "geschlossen", "grund": "sl_feed", "closed_at": iso(20)}),
    dict(basis, id="m1", puls_offen_n="2", hedge={"status": "geschlossen", "grund": "master_ende_reader", "closed_at": iso(9000), "reader_kurz": RK}),
    dict(basis, id="m2", puls_offen_n="1", hedge={"status": "geschlossen", "grund": "master_ende_reader", "closed_at": iso(9000), "reader_kurz": RK}),
    dict(basis, id="m3", puls_offen_n="3", hedge={"status": "geschlossen", "grund": "master_ende_reader", "closed_at": iso(9000), "reader_kurz": dict(RK, ok=True)}),
]
ev = {x[0].split("|")[0] + "|" + x[2]: x for x in ns["alarm_ereignisse"](plaene, {"u": "Chris"}, jetzt, iso(120))}
a = ev.get("a|kurz_balance_nein")
soll("🔴 ab > 20 Pkt neben dem Fenster, Prio 1, Werte + Prüf-Hinweis", a is not None and a[1] == 1 and "Balance passt nicht zum Ausstieg" in a[4] and "28920.00" in a[4] and "32.8 Pkt" in a[4] and "103467.1" in a[4] and "von Hand prüfen, ob der Master noch läuft" in a[4])
soll("echter Fall 3,9 Pkt daneben: kein Alarm", not any(k.startswith("a2|") for k in ev))
soll("genau 20 Pkt: kein Alarm, knapp darüber 🔴", not any(k.startswith("a3|") for k in ev) and "a4|kurz_balance_nein" in ev)
soll("kein 🔴 bei bestandenem Beweis", "b|kurz_balance_nein" not in ev)
soll("kein 🔴 für alten Schluss (vor seit)", "c|kurz_balance_nein" not in ev)
d = ev.get("d|kurz_balance_fehlt")
soll("Balance fehlt: nur 🟠 (Prio 2), kein 🔴, ohne leere Werte", d is not None and d[1] == 2 and "d|kurz_balance_nein" not in ev and "Balance fehlt" in d[4] and "None" not in d[4])
soll("kein 🔴, solange der Hedge nicht zu ist", "e|kurz_balance_nein" not in ev)
soll("Radar-Text nennt die Ablehnung", "das Userscript sah das Master-Ende, Schluss abgelehnt" in ev["f|radar_schloss"][4] and "falschen Konto" not in ev["f|radar_schloss"][4])
soll("🔴 Master noch offen ab 2 Lesungen, nur bei durchgefallener Kontrolle", ev.get("m1|kurz_master_offen", (0, 0))[1] == 1 and "m2|kurz_master_offen" not in ev and "m3|kurz_master_offen" not in ev)
soll("Radar-Text ohne Ablehnung wie bisher", "nicht zuerst gesehen" in ev["g|radar_schloss"][4])

print(f"\n{'ALLES OK' if not fehler else f'{fehler} FEHLER'}")
sys.exit(1 if fehler else 0)
