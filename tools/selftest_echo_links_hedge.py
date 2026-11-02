#!/usr/bin/env python3
"""Selbsttest ECHO-ZUORDNUNG (Finn 02.11.2026 ~18:15 „fix das, dass es nie wieder kommt“). Zwei Vorfälle, ein Symptom „kein Copier auf diesem PC passt zum Plan“:
Aurel pc-pw1put — Verknüpfung 14367785 nach dem Boot auf einem anderen Gerät angelegt, der Tab lud mt5_links nie nach; Emin pc-onkrbk — slave_account_id
„Fusion Live“ einer anderen ID (gleicher Fusion-Login 430095). Geprüft: Tab lädt Links bei Fehltreffer nach (gedrosselt 30 s) und löst danach auf,
voller localStorage bricht nichts, Rückfall auf den eigenen Hedge-Login nur eindeutig; Railway ersetzt bzw. verwirft ein fremdes Hedge-Konto.
Ohne Netz. Aufruf: python3 tools/selftest_echo_links_hedge.py"""
import json
import os
import re
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
APP = open(os.path.join(W, "app.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(src, name):
    i = src.index(f"function {name}(")
    if src[i - 6:i] == "async ":
        i -= 6
    j = src.index("{", src.index(")", i))
    t = 0
    for k in range(j, len(src)):
        t += {"{": 1, "}": -1}.get(src[k], 0)
        if t == 0:
            return src[i:k + 1]
    raise ValueError(name)


konst = [z for z in HTML.split("\n") if z.strip().startswith(("const MT5_LINKS_LS", "const MT5_LINKS_NACHLADEN_MS", "let _mt5LinksAt", "let _mt5LinksMem"))]
JS = "\n".join([
    "let _uhr = 1000000; Date.now = () => _uhr",
    "const console = { warn: () => {} }",
    "let MT5_LOCAL = true, currentUserId = 'u-aurel', _ls = {}, _lsVoll = false, _tabelle = [], _hedgeEinst = null, _ladungen = 0",
    "const localStorage = { getItem: k => (k in _ls ? _ls[k] : null), setItem: (k, v) => { if(_lsVoll) throw new Error('QuotaExceeded'); _ls[k] = v } }",
    "const mt5RefreshAfterLink = () => {}",
    "let accounts = []",
    r"""function kette(tab){ const k = { select: () => k, eq: () => k, maybeSingle: async () => ({ data: _hedgeEinst ? { value: _hedgeEinst } : null }),
  then: (f, r) => { _ladungen++; return Promise.resolve({ data: _tabelle, error: null }).then(f, r) } }; return k }
const supabase = { from: t => kette(t) }""",
] + konst + [fn(HTML, n) for n in ("mt5GetLinks", "mt5CacheLinks", "mt5LoadLinks", "mt5LinksNachladen", "mt5LoginForAccount", "planMt5Route", "mt5RouteResolve")] + [r"""
const inst = (m, h) => ({ status: { master_login: m, hedge_login: h } })
const o = {}
;(async () => {
  // AUREL: Plan 14367785 → Hedge 488579, der Tab bootete ohne den Link 14367785
  _tabelle = [{ mt5_login: '488579', account_id: 'fusion-aurel' }]
  await mt5LoadLinks()
  const plan = { id: 'p-aurel', masterAccountId: 'acc-14367785', slaveAccountId: 'fusion-aurel' }
  const instanzen = [inst('14367785', '488579')]
  _uhr += 31000
  o.vorher = mt5RouteResolve(plan, instanzen)
  _tabelle = [{ mt5_login: '488579', account_id: 'fusion-aurel' }, { mt5_login: '14367785', account_id: 'acc-14367785' }]   // 16:25 auf einem anderen Gerät angelegt
  const n0 = _ladungen
  o.erster_fehltreffer = mt5RouteResolve(plan, instanzen)   // stößt das Nachladen an
  await (window._mt5LinksNachladen ? null : null)
  await new Promise(r => r())
  await new Promise(r => setTimeout(r, 0))
  o.nachgeladen = _ladungen > n0
  o.danach = mt5RouteResolve(plan, instanzen)
  // Drossel: zwei Fehltreffer in 30 s → ein Nachladen
  const p2 = { id: 'p2', masterAccountId: 'gibts-nicht', slaveAccountId: 'fusion-aurel' }
  _uhr += 31000; const n1 = _ladungen
  mt5RouteResolve(p2, instanzen); await new Promise(r => setTimeout(r, 0)); _uhr += 10000; mt5RouteResolve(p2, instanzen); await new Promise(r => setTimeout(r, 0))
  o.gedrosselt = _ladungen - n1
  _uhr += 31000; mt5RouteResolve(p2, instanzen); await new Promise(r => setTimeout(r, 0))
  o.nach_30s = _ladungen - n1
  // Speicher voll: die Tabelle gilt trotzdem
  _lsVoll = true; _tabelle = [{ mt5_login: '777', account_id: 'acc-777' }]; _uhr += 31000
  await mt5LoadLinks()
  o.voll = mt5LoginForAccount('acc-777')
  _lsVoll = false
  // EMIN: Plan mit fremdem slave_account_id, eigener Hedge-Login 430095 in echo_hedge_account
  currentUserId = 'u-emin'; _tabelle = [{ mt5_login: '5551234', account_id: 'emin-master' }, { mt5_login: '430095', account_id: '901a4804' }]
  _hedgeEinst = { accountId: '901a4804', hedgeLogin: '430095' }; _uhr += 31000
  await mt5LoadLinks()
  const pe = { id: 'p-emin', masterAccountId: 'emin-master', slaveAccountId: '704925f0-fremd' }
  o.emin_eine = mt5RouteResolve(pe, [inst('5551234', '430095'), inst('999', '430095')])
  o.emin_zwei = mt5RouteResolve(pe, [inst('5551234', '430095'), inst('5551234', '430095')])
  o.emin_ohne = mt5RouteResolve(pe, [inst('5551234', '488579')])
  // S9: eigenes Slave-Konto mit ANDEREM Login (488579) → kein Rückfall; eigenes mit DEMSELBEN Login → Rückfall
  accounts = [{ id: 'fusion-488579', externalId: '488579' }, { id: 'fusion-430095', externalId: '430095' }]
  o.eigen_anders = mt5RouteResolve({ id: 'p-a', masterAccountId: 'emin-master', slaveAccountId: 'fusion-488579' }, [inst('5551234', '430095')])
  o.eigen_gleich = mt5RouteResolve({ id: 'p-b', masterAccountId: 'emin-master', slaveAccountId: 'fusion-430095' }, [inst('5551234', '430095')])
  accounts.push({ id: '704925f0-fremd', externalId: '430095', _fremd: true })
  o.fremd_markiert = mt5RouteResolve(pe, [inst('5551234', '430095')])
  accounts = []
  _hedgeEinst = null; _uhr += 31000; await mt5LoadLinks()
  o.emin_ohne_einst = mt5RouteResolve(pe, [inst('5551234', '430095')])
  print(JSON.stringify(o))
})().catch(e => print(JSON.stringify({ absturz: String(e) + ' ' + (e && e.stack) })))
"""])
JS = "const window = {};\n" + JS.replace("window._mt5LinksNachladen = mt5LinksNachladen", "")
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
    t.write(JS)
r = subprocess.run([JSC, t.name], capture_output=True, text=True, timeout=30)
os.unlink(t.name)
if r.returncode or not r.stdout.strip():
    print(r.stdout, r.stderr)
    sys.exit(1)
o = json.loads(r.stdout.strip().splitlines()[-1])
if "absturz" in o:
    print(o)
    sys.exit(1)
check(o["vorher"] is None and o["erster_fehltreffer"] is None, "Aurel: Link fehlt nach dem Boot → zunächst keine Zuordnung")
check(o["nachgeladen"] and o["danach"] and o["danach"]["masterLogin"] == "14367785", "Aurel: der Fehltreffer lädt mt5_links nach, danach passt die Instanz (≤ 30 s statt Tab neu laden)")
check(o["gedrosselt"] == 1 and o["nach_30s"] == 2, f"Nachladen gedrosselt: zwei Fehltreffer in 10 s → 1×, nach 30 s wieder ({o['gedrosselt']}, {o['nach_30s']})")
check(o["voll"] == "777", "localStorage voll: der frisch geladene Stand gilt aus dem Speicher")
check(o["emin_eine"] and o["emin_eine"]["hedgeLogin"] == "430095", "Emin: fremdes Slave-Konto, eigener Hedge-Login 430095, genau eine Instanz → aufgelöst")
check(o["emin_zwei"] is None, "Emin: zwei passende Instanzen → keine Zuordnung (nie raten)")
check(o["eigen_anders"] is None, "S9: eigenes Slave-Konto mit anderem Login (488579) → kein Rückfall auf 430095")
check(o["eigen_gleich"] and o["eigen_gleich"]["hedgeLogin"] == "430095", "eigenes Slave-Konto mit demselben Login, nur ohne Link → Rückfall")
check(o["fremd_markiert"] and o["fremd_markiert"]["hedgeLogin"] == "430095", "fremdes Slave-Konto (_fremd) → Rückfall")
check(o["emin_ohne"] is None and o["emin_ohne_einst"] is None, "ohne passende Instanz bzw. ohne eigene Einstellung → keine Zuordnung")
check("if(role === 'slave' && a._fremd) return false" in HTML and "!a.archived && !a._fremd" in HTML and "gehört nicht zu dieser ID — nicht gespeichert" in HTML,
      "Tab: Hedge-Konto nur aus eigenen Konten (Dropdown, Auto-Verknüpfung, Speichern)")

# Railway
ns = {}
i = APP.index("\ndef gp_hedge_settings_eigen_rechnen(") + 1
exec(APP[i:APP.find("\n\n\n", i)], ns)
R = ns["gp_hedge_settings_eigen_rechnen"]
konten = {"704925f0": {"user_id": "fb42b5c3", "external_id": "430095"}, "901a4804": {"user_id": "6cceb3f3", "external_id": "430095"},
          "86350acd": {"user_id": "6cceb3f3", "external_id": "430095"}}
eigene = {("6cceb3f3", "430095"): ["901a4804", "86350acd"]}
links = {("6cceb3f3", "430095"): "901a4804"}
zeile = lambda uid, acc, lg="430095": {"user_id": uid, "value": {"accountId": acc, "hedgeLogin": lg}}   # noqa: E731
neu, g = R([zeile("6cceb3f3", "704925f0"), zeile("fb42b5c3", "704925f0")], konten, eigene, links)
check(neu[0]["value"]["accountId"] == "901a4804" and "anderen ID" in g.get("6cceb3f3", ""), "Emin: fremdes Hedge-Konto → eigenes über die eigene Verknüpfung ersetzt")
check(neu[1]["value"]["accountId"] == "704925f0" and "fb42b5c3" not in g, "fb42b5c3: eigenes Konto bleibt unverändert")
neu2, g2 = R([zeile("6cceb3f3", "704925f0")], konten, eigene, {})
check(neu2 == [] and "keins eindeutig" in g2["6cceb3f3"], "zwei eigene Konten ohne Verknüpfung → verworfen (Planer plant ohne Hedge-Konto)")
neu3, g3 = R([zeile("6cceb3f3", "704925f0")], konten, {}, {})
check(neu3 == [] and "kein eigenes Konto" in g3["6cceb3f3"], "kein eigenes Konto mit dem Login → verworfen")
neu4, g4 = R([zeile("6cceb3f3", "unbekannt")], konten, eigene, links)
check(neu4[0]["value"]["accountId"] == "901a4804" and "nicht gefunden" not in g4.get("6cceb3f3", "x"), "unbekanntes Konto, Login aus der Einstellung → eigenes über die Verknüpfung")
check(len(re.findall(r'gp_hedge_settings_eigen\(_sb_all\("user_settings", \{"select": "user_id,value", "key": f"eq\.\{GP_HEDGE_KEY\}"', APP)) == 6
      and len(re.findall(r'_sb_all\("user_settings", \{"select": "user_id,value", "key": f"eq\.\{GP_HEDGE_KEY\}"', APP)) == 6,
      "alle sechs Planer-Stellen (Gruppe, Echo-Hedge, ehv, Tradeify-Final, Apex, Funded-CFD) lesen die Einstellung nur durch den Riegel")
import types as _t
ns2 = {"_sb_all": lambda *a, **k: (_ for _ in ()).throw(RuntimeError("HTTP 500")), "re": re, "print": lambda *a, **k: None}
i2 = APP.index("\n_gp_hedge_fremd = {}") + 1
exec(APP[i2:APP.index("\n\n\n", APP.index("\ndef gp_hedge_settings_eigen(") + 1)], ns2)
try:
    ns2["gp_hedge_settings_eigen"]([{"user_id": "u", "value": {"accountId": "a", "hedgeLogin": "1"}}])
    geworfen = False
except RuntimeError:
    geworfen = True
check(geworfen, "S9: Lesefehler beim Besitzer → Ausnahme, der Planer-Lauf bricht ab (nie Pläne ohne Hedge-Konto)")
print("ROT:" if FEHLER else "alles grün", FEHLER if FEHLER else "")
sys.exit(1 if FEHLER else 0)
