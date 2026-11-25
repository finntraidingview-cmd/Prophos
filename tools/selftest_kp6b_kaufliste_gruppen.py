#!/usr/bin/env python3
"""Selbsttest KP6b (26.11.2026, Master: Emin-Zellen liegen seit KP6 getrennt in zellen_gruppen, abrufbar über ?gruppe=<Emin-Gruppe>):
Admin → Alle Accounts → Kaufliste bekommt je Gruppe mit Verwalter einen eigenen Abschnitt unter Hermann Technologies — eigene Summe, nie
gemischt (Kopf-Summe nur HT, keine ID in zwei Abschnitten), gleiche Zeilen/Knöpfe/Rechte (Zeilen laufen durch dieselben Wege: rid, Gekauft,
Später, Pack). Verwalter (Emin) bzw. eigener Code: KEIN zweiter Abruf (der Server zeigt ihm ohnehin nur seine Gruppe). Im Stub belegt.
Aufruf:  python3 tools/selftest_kp6b_kaufliste_gruppen.py
"""
import os
import sys

HTML = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prophos.html"), encoding="utf-8").read()
n = 0


def check(ok, text):
    global n
    if not ok:
        print("✗", text)
        sys.exit(1)
    n += 1
    print("✓", text)


g = HTML[HTML.index("window._admVerwalterGruppen = () =>"):HTML.index("window._admVerwalterGruppen = () =>") + 300]
check("(!admData || admEingeschraenkt() || eigenerCode) ? []" in g and "filter(x => x && x.id && !x.ht)" in g,
      "Gruppen-Abschnitte nur für die volle Sicht (HT-Admin); Verwalter/eigener Code/ohne Übersicht → keiner (nie doppelt)")
lad = HTML[HTML.index("// KP6b (Master 25.11.2026): Admin → Alle Accounts"):HTML.index("d.gruppen_abschnitte = gruppen")]
check("if(cfg.alle) for(const g of" in lad, "nur der Admin-Ort (Alle Accounts), nie Accounts der eigenen ID")
check("/admin/kaufliste?${q}&gruppe=${encodeURIComponent(g.id)}" in lad, "Abruf mit ?gruppe=<Gruppe> (KP6 zellen_gruppen, Server-Lesefilter) + gleiche ansicht/frisch")
check("const gz = (dg.zeilen || []).filter(z => !ht.has(String(z.user_id)))" in lad, "keine ID in zwei Abschnitten")
check("z._gruppe = g.id" in lad and "d.spaeter = [...(d.spaeter || []), ...(dg.spaeter" in lad and "d.pausiert = [..." in lad,
      "Gruppen-Zeilen, „Später“ und „pausiert“ laufen durch dieselben Wege (rid, Gekauft, Später, Freigeben)")
check("gruppen.push({ id: g.id, name: g.name, fehler: String(e.message || e) })" in lad and "if(veraltet()) return" in lad,
      "Fehler je Abschnitt benannt, ID-Wechsel während des Ladens verworfen")
rd = HTML[HTML.index("// KP6b: Abschnitt je Unternehmen — Hermann Technologies"):HTML.index("function idsHtml(zeilen, leerText){")]
check("const htZ = zeilen.filter(x => !x.z._gruppe)" in rd and "<b>Hermann Technologies</b>" in rd and "${summe(htZ)}" in rd, "HT-Abschnitt mit eigener Summe zuerst")
check("const gz = zeilen.filter(x => x.z._gruppe === g.id)" in rd and "${summe(gz)}" in rd and "h += idsHtml(gz, true)" in rd, "je Gruppe eigener Kopf + eigene Summe, gleiche Zeilen")
check("const oben = zeilen.filter(x => !x.z._gruppe)" in HTML and "${summe(oben)}" in HTML, "Kopf-Summe der Karte nur Hermann Technologies (nie mit Emin gemischt)")
check("if(abschn.length) h +=" in rd and "h += idsHtml(htZ, !abschn.length)" in rd, "ohne Gruppen (Verwalter, Accounts) alles wie bisher")
check("#kl-admin-karte .kl-gr-kopf{" in HTML, "Abschnitts-Kopf im Design der Karte")
print(f"\n{n} Prüfungen grün")
