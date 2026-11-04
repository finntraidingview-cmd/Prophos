#!/usr/bin/env python3
"""Selbsttest T1 — „Trotzdem starten" im Auto-Start-Fenster + frische Ziel-Lesung (Finn 04.11.2026 ~04:40 Dubai, EzPoker-Tab, Orbit
„150k … → Challenge": „Die Meldung soll ‚Okay, trotzdem starten‘ anbieten"; Meldung nannte Ziel 159.000 aus dem Cache, live ziel_usd 159.345).
planZielErreicht in JavaScriptCore gerechnet, Verdrahtung als Text geprüft. Ohne Netz. Aufruf: python3 tools/selftest_trotzdem_auto_start.py"""
import json
import os
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


fn = HTML[HTML.index("  function planZielErreicht(plan, frisch){"):HTML.index("  const planZielText =")]
# Fälle: (Konto-Cache, Plan-Notiz-Ziel, frisch, Soll blockiert?)
FAELLE = [
    ("alter Cache-Stempel zielErreichtAt, DB sagt nicht erreicht, Balance unter Notiz-Ziel → frei", {"tvBalance": 158900, "tvBalanceAt": "2026-11-04T00:30:00Z",
     "zielErreichtAt": "2026-11-03T10:00:00Z", "zielErreichtBal": 159031, "zielUsd": 159000}, 159000, {"bal": 158900, "balAt": "2026-11-04T00:30:00Z"}, False),
    ("Cache-Stempel ohne frisch (DB nicht lesbar) → gesperrt wie bisher", {"zielErreichtAt": "2026-11-03T10:00:00Z", "zielErreichtBal": 159031, "zielUsd": 159000}, 0, None, True),
    ("ohne frisch → Notiz-Ziel 159.000, Cache-Balance 159.031 → gesperrt", {"tvBalance": 159031, "tvBalanceAt": "2026-11-04T00:30:00Z"}, 159000, None, True),
    ("frisch: Notiz-Ziel bleibt Quelle (ziel_usd nie) → gesperrt", {"tvBalance": 159031, "tvBalanceAt": "2026-11-04T00:30:00Z"}, 159000,
     {"ziel": 159345, "bal": 159031, "balAt": "2026-11-04T00:30:00Z"}, True),
    ("DB-Balance jünger und unter Ziel → frei (Cache-Balance alt)", {"tvBalance": 159031, "tvBalanceAt": "2026-11-04T00:30:00Z"}, 159000,
     {"bal": 158700, "balAt": "2026-11-04T00:35:00Z"}, False),
    ("DB-Balance jünger und über Ziel → gesperrt", {"tvBalance": 158000, "tvBalanceAt": "2026-11-04T00:30:00Z"}, 159000,
     {"bal": 159400, "balAt": "2026-11-04T00:35:00Z"}, True),
    ("DB-Balance älter als Cache → Cache zählt", {"tvBalance": 159500, "tvBalanceAt": "2026-11-04T00:40:00Z"}, 159000,
     {"bal": 158000, "balAt": "2026-11-04T00:30:00Z"}, True),
    ("ohne Notiz-Ziel nie über Balance gesperrt (auch mit frisch)", {"tvBalance": 60000, "tvBalanceAt": "2026-11-04T00:30:00Z"}, 0,
     {"ziel": 54000, "bal": 60000, "balAt": "2026-11-04T00:30:00Z"}, False),
]
js = fn + """
const planIstTageMini = () => false
let accounts = []
const planAutoNotiz = notes => notes ? JSON.parse(notes) : null
function planKontoBalance(a){ if(!a || a.tvBalance == null) return null; return { val: Number(a.tvBalance), at: Date.parse(a.tvBalanceAt || '') || 0 } }
const F = """ + json.dumps([[f[1], f[2], f[3]] for f in FAELLE]) + """
print(JSON.stringify(F.map(([k, z, fr]) => { accounts = [Object.assign({ id: 'k1' }, k)]
  const r = planZielErreicht({ masterAccountId: 'k1', notes: z ? JSON.stringify({ ziel: z }) : '' }, fr); return r ? [r.bal, r.ziel] : null })))
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d.name], capture_output=True, text=True)
os.unlink(d.name)
check(r.returncode == 0, f"jsc läuft ({r.stderr[:160]})")
erg = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else []
for f, g in zip(FAELLE, erg):
    check((g is not None) == f[4], f"{f[0]} (ist {g})")

kern = HTML[HTML.index("  async function planKontoSperreKern("):HTML.index("  async function planKontoSperreKern(") + 5000]
check("select('ziel_erreicht_at,ziel_erreicht_bal,ziel_usd,tv_balance,tv_balance_at')" in kern, "Kern liest Ziel + Balance frisch aus accounts")
check("frisch = { bal: ra.data.tv_balance, balAt: ra.data.tv_balance_at }" in kern and "planZielErreicht(plan, frisch)" in kern,
      "Kern gibt die frische Zeile an planZielErreicht (Rückfall Cache nur ohne DB)")
check("opts.newsTrotzdem" in HTML[HTML.index("  async function planKontoSperre(plan, opts){"):HTML.index("  async function planKontoSperreKern(")],
      "News-Sperre: Freigabe vom Absender (opts.newsTrotzdem)")
check("fern.melde({ ok:false, msg: sperre.text, sperre: sperre.art })" in HTML, "PC meldet die Art der Sperre im Signal-Ergebnis")
check("newsTrotzdem: (sig.params || {}).news_trotzdem === true" in HTML and "newsTrotzdem: !!fern.newsTrotzdem" in HTML, "PC übernimmt news_trotzdem vom Signal")
check("...(newsTrotzdemAn(pid) ? { news_trotzdem: true } : {})" in HTML, "Orbit-Signal trägt news_trotzdem")
check("return _rsQueueAdd(plan, { hand: !!(opts && opts.karte) })" in HTML and "_rsQueueAdd(plan, { hand: karte })" in HTML, "nur Karten-Klick gilt als Hand-Start")
check("if(opts && opts.hand) _rsHand.add(pid); else _rsHand.delete(pid)" in HTML, "automatischer Eintrag nimmt die Hand-Marke weg")
check("trotz: (!ok && trotz && _rsHand.has(String(trotz.planId))) ? trotz : null" in HTML, "Knopf nur bei Hand-Start und rotem Ergebnis")
check("(!erg.unklar && (erg.sperre === 'ziel' || erg.sperre === 'news')) ? erg.sperre" in HTML, "PC-Ergebnis ziel/news → Knopf, UNKLAR nie")
check("opts.fehl(sp.text, sp.art)" in HTML and "fehl: (kurz, sperrArt) =>" in HTML, "Absender-Check (Duplikum still) gibt die Art weiter")
tr = HTML[HTML.index("  function _rsqTrotzdem(d){"):HTML.index("  window._rsqTrotzdemTest")]
check("if(eigeneHalt){ _rsQueueHalt = null" in tr and "_rsQueue = [pid].concat(" in tr and "_rsQueuePump()" in tr,
      "Klick: nur die eigene Pause aufheben, Plan vorn, Schlange pumpt")
check("_zielTrotzdem.set(pid, Date.now())" in tr and "_newsTrotzdem.set(pid, Date.now())" in tr, "Klick setzt denselben 10-min-Merker wie der Toast")
check("items.querySelectorAll('[data-rsq-trotz]').forEach(b =>" in HTML, "eigener Handler je Knopf (kein Sammler)")
check("|| plan.orbitGesendetAt)" in tr and "(_rsAktiv && String(_rsAktiv.planId || '') === pid)" in tr, "kein zweites Signal: laufend, schon in der Schlange oder schon gesendet")
check("if(d.trotz && String(d.trotz.planId) === pid) d.trotz = null" in HTML, "neuer Start desselben Plans nimmt alten Knöpfen die Wirkung")
check("am PC gesperrt (${trotzArt === 'news' ? 'News' : 'Ziel erreicht'})" in HTML, "eigene Pausen-Meldung je Plan (Knopf hebt nie fremde Pause auf)")
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
