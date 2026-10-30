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
print(f"\n{'selftest_abhaken_ein_klick: alle Prüfungen grün' if not FEHLER else f'✗ {len(FEHLER)} Fehler'}")
sys.exit(1 if FEHLER else 0)
