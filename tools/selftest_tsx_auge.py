#!/usr/bin/env python3
"""Selbsttest: TOPSTEPX-AUGE + TOPSTEP BIG TRADE (27.10.2026, Finn: „In erster Instanz ein Tampermonkey-Script im TopstepX-Tab … sobald der
Trade in TopstepX geschlossen wird, sieht das Auge das und schließt den Hedge direkt"; „Liq aus TopstepX-MLL statt Größe + 100").
Prüft rein rechnend: Panel (mt5-copier/panel.py tsx_stand_herkunft_ok/tsx_stand_merken/tsx_stand_ausgabe), Userscript (tv-reader/tsx-auge.user.js
mit nachgebautem Auge) und Frontend (prophos.html tsxStandListe, tsxKontoGleich, hedgeMasterWegEntscheid, hedgeLiqLevel) über das macOS-eigene
JavaScriptCore (ohne Node, wie .claude/jscheck.sh). Aufruf: python3 tools/selftest_tsx_auge.py"""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlparse

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


def panel_test():
    src = open(os.path.join(WURZEL, "mt5-copier", "panel.py"), encoding="utf-8").read()
    i, j = src.index("TSX_STAND_MAX = 60_000"), src.index("class Handler(BaseHTTPRequestHandler):")
    ns = {"re": re, "time": time, "threading": threading, "urlparse": urlparse}
    exec(src[i:j], ns)
    ok = ns["tsx_stand_herkunft_ok"]
    for o, soll in [(None, True), ("https://topstepx.com", True), ("https://www.topstepx.com", True), ("chrome-extension://abc", True),
                    ("http://127.0.0.1:5000", True), ("https://evil.com", False), ("https://topstepx.com.evil.com", False),
                    ("http://localhost.evil", False)]:
        check(ok(o) is soll, f"Panel: Herkunft {o!r} → {soll}")
    m, a = ns["tsx_stand_merken"], ns["tsx_stand_ausgabe"]
    check(a(100)["ok"] is False, "Panel: ohne Meldung ok:false")
    m({"tab": "t1", "stand": {"x": 1}}, 100)
    m({"tab": "t2", "stand": {"x": 2}}, 101)
    r = a(101.5)
    check(r["ok"] and r["tab"] == "t2" and r["alter_s"] == 0.5 and r["tabs"] == 2, f"Panel: jüngster Tab mit Alter ({r})")
    m({"tab": "t3", "stand": {}}, 140)
    check(a(140)["tabs"] == 1, "Panel: Tab-Stände älter als 30 s fallen weg")
    check(m({"tab": "", "stand": {}})[0] is False and m({"tab": "x"})[0] is False, "Panel: ohne tab/stand abgelehnt")


def fn(src, name):
    i = src.index("  function " + name + "(")
    return src[i:src.index("\n  }\n", i) + 4]


def jsc(code):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(code)
        p = f.name
    try:
        return subprocess.run([JSC, p], capture_output=True, text=True, timeout=30).stdout
    finally:
        os.unlink(p)


def frontend_test():
    s = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
    k = s.index("  const tsxKontoGleich = ")
    code = "\n".join(fn(s, n) for n in ("tvSymbolWurzel", "hedgeKontoPasst", "hedgeMasterWegEntscheid", "hedgeMasterTeilweise", "tsxStandListe", "hedgeLiqLevel"))
    code = ("var window = {}, accounts = [], _liqRegeln = null; function liqRegelnLaden(){ return { catch(){} } } function tpKontoGroesseAusName(){ return 0 }\n"
            + code + "\n" + s[k:s.index("\n", k)] + r"""
var aus = [], f = (b, t) => aus.push((b ? 'OK ' : 'ROT ') + t)
var L = tsxStandListe({ positionen: [{ symbol: 'MNQZ26', seite: 'sell', menge: 3 }] })
f(L[0].wurzel === 'MNQ' && L[0].menge_zahl === 3 && L[0].richtung === 'sell', 'Frontend: Positionen → Reader-Liste')
f(hedgeMasterTeilweise(L, 'MNQ', 'sell', 1e9) != null && hedgeMasterTeilweise(L, 'MNQ', 'buy', 1e9) == null, 'Frontend: Master da, Gegenrichtung zählt nicht')
var b = { liste: [], positionenOk: true, alterMs: 300, sekundenSeitOpen: 120, wurzel: 'MNQ', richtung: 'sell', kontoPlan: 'X', kontoAktiv: 'X', kontenAnzahl: 99, schnell: true, gesehen: true }
f(hedgeMasterWegEntscheid(Object.assign({}, b, { kontoStabilMs: 100000, leerSeitMs: 1200 })) === true, 'Frontend: Konto ruhig + 1,2 s flach → schließen')
f(hedgeMasterWegEntscheid(Object.assign({}, b, { kontoStabilMs: 100000, leerSeitMs: 500 })) === false, 'Frontend: 0,5 s flach → noch nicht')
f(hedgeMasterWegEntscheid(Object.assign({}, b, { kontoStabilMs: 20000, leerSeitMs: 5000 })) === false, 'Frontend: Wechsel-Fenster 5 s flach → nein')
f(hedgeMasterWegEntscheid(Object.assign({}, b, { kontoStabilMs: 20000, leerSeitMs: 31000 })) === true, 'Frontend: Wechsel-Fenster 31 s flach → schließen')
f(hedgeMasterWegEntscheid(Object.assign({}, b, { kontoStabilMs: 100000, leerSeitMs: 5000, alterMs: 3500 })) === false, 'Frontend: Stand zu alt → nein')
f(hedgeMasterWegEntscheid(Object.assign({}, b, { kontoStabilMs: 100000, leerSeitMs: 5000, liste: L })) === false, 'Frontend: Position da → nie')
f(tsxKontoGleich('EXPRESS-V2-000000-00000000', 'EXPRESS-V2-000000-00000000') && !tsxKontoGleich('EXPRESS-V2-000000-0000000', 'EXPRESS-V2-000000-00000000') && !tsxKontoGleich('', 'X'), 'Frontend: Konto nur exakt')
var p = { route: 'tsv2', richtung: 'sell', masterAccountId: 'x', mt5Baseline: { tv: { mll_start: 0, balance_start: 2307.82, balance_relativ: true } } }
var r = hedgeLiqLevel(p, 29460.25, 2, 3)
f(r.liq_balance === 100 && r.sl_usd_hedge === 2207.82 && r.sl_punkte === 367.97 && r.sl_level_nq === 29828.22 && r.liq_quelle === 'topstepx_mll', 'Liq: Express MLL 0 → Level über dem Einstieg (SELL)')
f(hedgeLiqLevel(Object.assign({}, p, { richtung: 'buy' }), 29460.25, 2, 3).sl_level_nq < 29460.25, 'Liq: BUY unter dem Einstieg')
var c = hedgeLiqLevel({ route: 'tsv2', richtung: 'buy', mt5Baseline: { tv: { mll_start: 145500, balance_start: 151000, balance_relativ: false } } }, 29000, 20, 3)
f(c.liq_balance === 145600 && c.sl_usd_hedge === 5400, 'Liq: Combine absolut MLL + 100')
f(/MLL/.test(hedgeLiqLevel({ route: 'tsv2', richtung: 'buy', mt5Baseline: { tv: { mll_start: 0, balance_start: 50, balance_relativ: true } } }, 29000, 2, 3).hinweis || ''), 'Liq: Balance unter MLL + 100 → kein Level, Hinweis')
f(/Kontogröße/.test(hedgeLiqLevel({ route: 'tsv2', richtung: 'buy', mt5Baseline: { tv: { mll_start: 0, balance_start: 7369, balance_relativ: null } } }, 29000, 2, 3).hinweis || ''), 'Liq: Basis unbekannt + MLL 0 → alter Weg')
f(hedgeLiqLevel({ route: 'tvv2', richtung: 'buy', mt5Baseline: { tv: { mll_start: 0, balance_start: 5000, balance_relativ: true } } }, 29000, 2, 3).liq_quelle !== 'topstepx_mll', 'Liq: Orbit (tvv2) unberührt')
print(aus.join('\n'))
""")
    # Variante B (27.10.2026): im Schnell-Wächter steht die 5-s-Sperre VOR dem Schließ-Entscheid
    i = s.index("  async function hedgeTsxSchnellTick("); t = s[i:s.index("\n  setInterval(hedgeTsxSchnellTick", i)]
    g, e = t.find("< TSX_FLACH_MIN_MS) continue"), t.find("hedgeMasterWegEntscheid(")
    check("const TSX_FLACH_MIN_MS = 5000" in s and 0 < g < e, "Frontend: Topstep schließt erst nach ≥ 5 s durchgehend flach (Variante B)")
    for z in (jsc(code) or "ROT JavaScriptCore lieferte nichts").strip().splitlines():
        check(z.startswith("OK "), z[3:] if z.startswith("OK ") else z)


def userscript_test():
    us = open(os.path.join(WURZEL, "tv-reader", "tsx-auge.user.js"), encoding="utf-8").read()
    kopf = r"""var gesendet = [], location = { href: 'https://topstepx.com/trade' }, document = { visibilityState: 'hidden' }, console = { info(){}, warn(){} };
function setInterval(){ return 1 } function GM_xmlhttpRequest(o){ gesendet.push(JSON.parse(o.data)); o.onload({ status: 200 }) } function Worker(){ throw new Error('x') }
var URL = {}, Blob = function(){};
var PROPHOS_AUGEN_TSX = { stand: function(){ return { v: 'tsx-0.6.3', ts: 1, sichtbar: 'hidden',
  konto: { aktiv: '$150K Express | EXPRESS-V2-000000-00000000', kontonr: 'EXPRESS-V2-000000-00000000', abgekuerzt: false, liste_offen: false, rect: [1,2,3,4] },
  positionen: [{ symbol: 'MNQZ26', seite: 'sell', menge: 3, avg: 29460.25, pl_text: '$12.00', quelle: 'tabelle' }], positionen_sichtbar: true, flach: false,
  ticket: { reiter: { positions: { aktiv: true, rect: [0,0,1,1] } } }, kopf: { balance: { wert: 1234.5 }, mll: { wert: -4500 }, balance_relativ: true },
  toasts: { bracket: { fill: { preis: 29460.25, menge: 3, seite: 'sell', symbol: 'MNQZ26' }, tp: { preis: 29400 }, sl: { preis: 29500 } } }, popups: [] } } };
"""
    fuss = r"""
var p = gesendet[0], s = p && p.stand
print((s && s.konto.kontonr === 'EXPRESS-V2-000000-00000000' && s.positionen[0].menge === 3 && s.flach === false && s.reiter_positions.aktiv === true
  && s.kopf.mll === -4500 && s.bracket.sl.preis === 29500 && s.konto.rect === undefined && /^tsx-/.test(p.tab) && JSON.stringify(p).length < 2000) ? 'OK' : 'ROT ' + JSON.stringify(p))
"""
    out = (jsc(kopf + us + fuss) or "").strip()
    check(out == "OK", "Userscript: Paket aus stand() (Konto, Position, flach, Reiter, MLL, Bracket, ohne Rechtecke)" + ("" if out == "OK" else " — " + out[:200]))


def main():
    print("Panel"); panel_test()
    print("Userscript"); userscript_test()
    print("Frontend"); frontend_test()
    if FEHLER:
        print(f"\n✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("\n✓ alle Prüfungen grün")


if __name__ == "__main__":
    main()
