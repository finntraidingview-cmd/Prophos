#!/usr/bin/env python3
"""Selbsttest ABHAKEN EIN KLICK (prophos.html wdlEinKlickGrund, 30.10.2026 — Finn: „Trades, bei denen nichts passiert … immer ein Klick zu viel").
Aufruf:  python3 tools/selftest_abhaken_ein_klick.py   (ohne Netz; Quelltext-Prüfung, die Fälle laufen im Stub über window._wdlEinKlickGrund)."""
import os
import sys

html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


fn = html[html.index("function wdlEinKlickGrund("):html.index("window._wdlEinKlickGrund")]
for marker, name in (("wdlGeblowtUrteil(t)", "geblowt → Popup"), ("wdlBestandenChip(t)", "bestanden → Popup"), ("wdlFcfdZielErreicht(t)", "Funded-CFD-Ziel → Popup"),
                     ("t.tage_mini", "Tage-Mini → Popup"), ("zahl(t.pl_balance)", "ohne echte Lesung → Popup"), ("wdlManuell(t)", "manuell → Popup"),
                     ("t.hedge.status !== 'geschlossen'", "Hedge offen → Popup"), ("Hedge-P&L fehlt", "Hedge-P&L fehlt → Popup"), ("mklWdEigenerPlan(", "eigener Plan → Popup")):
    check(marker in fn, name)
check("kette_tag" not in fn, "Topstep-Tagesergebnis allein erzwingt kein Popup")
oe = html[html.index("function mklWdErledigtOeffnen("):html.index("function mwdErlStatusUI(")]
check("opts.einKlick" in oe and "mklWdErledigtSpeichern(); return" in oe and "!wdhCb?.checked" in oe, "Ein Klick speichert über den Popup-Weg, Winning-Day-Vorschlag öffnet das Popup")
check(oe.index("opts.einKlick") < oe.index("getElementById('mwdErledigtModal')?.classList.add('open')"), "Prüfung läuft vor dem Öffnen")
check("wdlEinKlickGrund(t); if(ein)" in html and "Date.now() - _wdlEinKlickAt < 600" in html, "Klick fragt die Prüfung, Doppelklick bucht die nächste Zeile nicht mit")
check("Number(t.balance_end) > 0" in fn and "dm.status === 'liquidiert'" in fn, "Balance 0 und Demo an der Liq → Popup")
check("const sicht = _mwdErlSicht, ohneHedge" in html, "Werte für Anfrage und Toast vor dem await festgehalten")
sp = html[html.index("async function mklWdErledigtSpeichern("):html.index("document.getElementById('mwdErledigtClose')")]
check("wdlLokalVergessen(pid)" in sp and "Abhaken nicht gespeichert" in sp, "Fehler: Toast und Zeile zurück")
# ── Echter Lauf von wdlEinKlickGrund in JavaScriptCore (ohne Node), Helfer per Merker am Trade ──
import json
import subprocess
import tempfile
STUBS = """
const flag = n => t => !!(t && t['_' + n]);
const wdlIstPolar = flag('polar'), mklWdEigenerPlan = () => false, wdlAbhakenSperre = () => '', wdlManuell = flag('man'), wdlGeblowtUrteil = flag('blow'), wdlKontoWeg = flag('weg'),
  wdlKontoWegErg = () => '', wdlTpUndWeg = flag('tpweg'), wdlBestandenChip = flag('best'), wdlFehltChip = flag('fehlt'), wdlZielMarkiert = flag('ziel'), wdlFcfdZielErreicht = flag('fz'),
  wdlWartet = flag('wart'), wdlPlGesch = flag('gesch'), wdlLiqIstTag = flag('tag'), wdlTid = t => t.id;
const wdlBlowStand = t => t._ohneLiq ? { liq: null } : { liq: 90000 };
const WDL_UEBERGANG = { challenge: 'x', phase1: 'x', phase2: 'x' };
"""
BASIS = {"id": "p", "status": "review", "route": "mt5v2", "konto_typ": "phase1", "konto_aktuell": {"typ": "phase1", "ziel_erreicht_at": None}, "ziel_usd": 110000,
         "balance_end": 100700, "pl_balance": 700, "master_tp": 700, "master_sl": 700, "endlesung": {"balance_end": 100700, "quelle": "puls"}}
FAELLE = [("unauffällig", {}, True), ("Hand geschlossen unter TP", {"pl_balance": 300, "endlesung": {"grund": "hand", "quelle": "puls"}}, True),
          ("SL getroffen", {"pl_balance": -700}, True), ("15 % + über TP in der Grenze", {"pl_balance": 800}, True),
          ("konto_geblowt", {"endlesung": {"konto_geblowt": {"x": 1}}}, False), ("grund tsx_geblowt", {"endlesung": {"grund": "tsx_geblowt"}}, False),
          ("puls_fehler konto_weg", {"endlesung": {"puls_fehler": "konto_weg: fehlt"}}, False), ("puls_fehler konto_nicht_erreicht", {"endlesung": {"puls_fehler": "konto_nicht_erreicht"}}, False),
          ("ohne ziel_usd", {"ziel_usd": None}, False), ("ohne Liq/Boden", {"_ohneLiq": True}, False), ("wdlZielMarkiert", {"_ziel": True}, False),
          ("ziel_erreicht_at am Konto", {"konto_aktuell": {"typ": "phase1", "ziel_erreicht_at": "2026-10-30T10:00:00Z"}}, False),
          ("Konto in anderer Phase", {"konto_aktuell": {"typ": "phase2"}}, False), ("Konto-Stand fehlt", {"konto_aktuell": None}, False),
          ("P&L weit über TP", {"pl_balance": 5000}, False), ("Verlust weit über SL", {"pl_balance": -5000}, False), ("ohne TP/SL am Plan", {"master_tp": None, "master_sl": None}, False), ("P&L genau 0", {"pl_balance": 0}, False), ("P&L genau 0 ohne TP/SL", {"pl_balance": 0, "master_tp": None, "master_sl": None}, False),
          ("t2_grund unplausibel", {"kette_grund": "Ergebnis unplausibel (−148.000 $)"}, False), ("Funded Futures", {"konto_typ": "funded", "konto_aktuell": {"typ": "funded"}}, False),
          ("Funded CFD unauffällig", {"konto_typ": "funded_cfd", "konto_aktuell": {"typ": "funded_cfd"}, "ziel_usd": None, "route": "mt5", "slave_pl": 0}, True),
          ("Balance 0", {"balance_end": 0, "pl_balance": -100000}, False), ("Hedge offen", {"hedge": {"status": "offen"}}, False), ("Lesung fehlt", {"pl_balance": None}, False)]
js = STUBS + fn + "\nconst F = " + json.dumps([dict(BASIS, **f[1]) for f in FAELLE], ensure_ascii=False) + "; print(JSON.stringify(F.map(wdlEinKlickGrund)));"
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d.name], capture_output=True, text=True)
os.unlink(d.name)
check(r.returncode == 0, f"jsc läuft ({r.stderr[:200]})")
erg = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else []
for (name, _f, soll), g in zip(FAELLE, erg):
    check((g == "") is soll, f"{name}: {'Ein Klick' if not g else 'Popup: ' + g}")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.py"), encoding="utf-8").read()
check('daten.get("nur_review") is True and plan and plan.get("status") != "review"' in src and "einKlick ? { nur_review: true }" in html, "nur_review: Ein Klick bekommt 409, wenn der Trade nicht mehr in Überprüfen steht")
print(f"\n{'selftest_abhaken_ein_klick: alle Prüfungen grün' if not FEHLER else f'✗ {len(FEHLER)} Fehler'}")
sys.exit(1 if FEHLER else 0)
