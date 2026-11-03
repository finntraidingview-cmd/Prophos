#!/usr/bin/env python3
"""Selbsttest WD-ANZEIGE „HEUTE" (W3, Finn 03.11.2026 ~19:05 Dubai) + S2-Stopp zu 23811525: die Ansicht bleibt bis zum Tageslauf 00:10 Dubai auf dem
laufenden Tag, der Admin-Reiter trägt den NÄCHSTEN Lauf-Tag trotzdem wie bisher schon abends ein (IDs ohne PC-Tab) — ohne die Anzeige-Zeilen zu ersetzen
und ohne „heute schon getradet" des angezeigten Tags. Text-Prüfung am Quelltext (kein Node auf dem Mac); wdLaufTag ist im Browser über window._wdLaufTag
getestet. Aufruf: python3 tools/selftest_wd_heute_anzeige.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = open(os.path.join(os.path.dirname(HIER), "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def block(start, ende="\n  }\n"):
    i = HTML.index(start)
    return HTML[i:HTML.index(ende, i)]


lt = block("  function wdLaufTag(r, j){")
check("WD_TAGESLAUF_HHMM" in lt and "wdTagPlus(j.tag, -1)" in lt, "wdLaufTag: vor dem Tageslauf der Vortag")
check("return wdHandelstag(j.wochentag) ? j.tag : wdNaechsterTag(r, j)" in lt, "wdLaufTag: Handelstag bleibt bis zum Tageslauf, Wochenende → nächster")
check("wdBisHhmm(r)" not in lt, "wdLaufTag: kein Sprung mehr um Spätestens + 2 h")

nl = block("  async function wdNeuLaden(){")
check(re.search(r"if\(!_wd\.tagHand\)\{[^}]*wdLaufTag\(", nl) is not None, "wdNeuLaden: Tag zieht nach dem Tageslauf selbst nach (außer von Hand)")
i_auto, i_naechst = nl.index("wdAutoEintragen(tag)"), nl.index("wdAutoEintragen(naechster, { nurEintragen: true })")
check(i_auto < i_naechst and "wdNaechsterTag(_wd.regeln || {}, jN)" in nl and "naechster !== tag" in nl,
      "wdNeuLaden: nächster Lauf-Tag wird zusätzlich eingetragen, wenn er nicht angezeigt ist")

ae = block("  async function wdAutoEintragen(tag, opt){")
check("_wd.autoAtJe[tag]" in ae and "Date.now() - (_wd.autoAtJe[tag] || 0) < 5 * 60000" in ae, "wdAutoEintragen: 5-min-Takt je Tag (angezeigt + nächster getrennt)")
check("ohneHeute: true" in ae and "if(nurE){" in ae, "wdAutoEintragen nurEintragen: ohne „heute getradet“, Rückkehr vor Würfeln/Neuzeichnen")
check(ae.index("if(nurE){") < ae.index("wdWuerfelnSchreiben(tag, false)") < ae.index("_wd.rows = wdUmsortiertAuflegen"), "nurEintragen würfelt nicht und zeichnet nicht neu")

al = block("  async function wdAlleEintragen(tag, opt){", "\n    for(const e of await")
check("wdErwartet(opt && opt.ohneHeute ? { ohneHeute: true } : undefined)" in al and "wdRowsLaden(tag, !!(opt && opt.ohneHeute))" in al,
      "wdAlleEintragen: anderer Tag → ohne heute-Flag, Anzeige-Zeilen bleiben")
rl = block("  async function wdRowsLaden(tag, ohneMerken){")
check(rl.index("if(ohneMerken) return rows") < rl.index("_wd.rows = rows"), "wdRowsLaden(ohneMerken) ersetzt _wd.rows nicht")
er = HTML[HTML.index("  function wdErwartet(opt){"):HTML.index("  function wdErwartet(opt){") + 1500]
check("!!r.heute_gestartet && !(opt && opt.ohneHeute)" in er, "wdErwartet: heute schon getradet nur für den angezeigten Tag")

if FEHLER:
    print(f"\n{len(FEHLER)} Fehler")
    sys.exit(1)
print("\nalle grün")
