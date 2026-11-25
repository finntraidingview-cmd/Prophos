#!/usr/bin/env python3
"""Selbsttest KP5 (26.11.2026, Finn sucht die Kaufplan-Einstellungen): Admin-Reiter „Kaufplan" mit genau den drei Blöcken des Vorrat-Views
(Ziele je Unternehmen mit KP3-Umschalter, Mindest-Chance aufs Ziel, Freigeschaltet je ID und Firma) — EIN Baustein (vrEinstHtml) für beide Orte,
dieselben Handler und Speicherwege (POST /admin/vorrat), dieselben Rechte (Server-Gate; Reiter für Admin + Verwalter, nicht für eingeschränkte
Logins ohne Gruppe). Nach jedem Speichern neu rechnen (aktion rechnen) und die Kaufliste frisch laden. Im Stub belegt (Reiter, Klicks, Aufrufe).
Aufruf:  python3 tools/selftest_kp5_kaufplan.py
"""
import os
import re
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


check('<button class="subtab adm-tab" data-admtab="kaufplan">Kaufplan</button>' in HTML, "Reiter „Kaufplan“ im Admin (neben „Alle Accounts“)")
i = HTML.index('data-admtab="konten">Alle Accounts</button>')
check(HTML.index('data-admtab="kaufplan"') - i < 600, "Reiter steht direkt hinter „Alle Accounts“")
check('<div id="adm-pane-kaufplan" hidden>' in HTML and 'id="adm-kp-root"' in HTML, "eigener Bereich im Admin")
check("$('adm-pane-kaufplan').hidden = name !== 'kaufplan'" in HTML and "if(name === 'kaufplan') window._vrKaufplanOeffnen?.()" in HTML, "Reiter-Umschaltung zeigt/lädt den Bereich")
ht = re.search(r"const KASSE_REITER_HT = new Set\(\[([^\]]*)\]\)", HTML).group(1)
eig = re.search(r"const KASSE_REITER_EIGENE = new Set\(\[([^\]]*)\]\)", HTML).group(1)
check("kaufplan" not in ht and "kaufplan" not in eig, "Rechte: Admin + Verwalter sehen den Reiter, eingeschränkte Logins ohne Gruppe nicht (wie bisher je Reiter)")
check(HTML.count("function vrEinstHtml(d, name){") == 1 and HTML.count("${vrEinstHtml(d, name)}") == 1 and "+ vrEinstHtml(d, name)" in HTML,
      "EIN Baustein für die Einstellungen — Vorrat-View und Admin → Kaufplan")
blk = HTML[HTML.index("function vrEinstHtml(d, name){"):HTML.index("function vrRender(){ vrRenderVorrat();")]
check("vrZieleHtml(d)" in blk and "data-vr-sich-box" in blk and "vrMatrixHtml(d, name)" in blk, "drei Blöcke: Ziele (mit KP3-Umschalter), Mindest-Chance, Freigaben")
check("vrZieleVerdrahten(root)" in blk and "vrSchalten(b.dataset.vrU, b.dataset.vrF, b.dataset.vrS)" in blk and "vrSichRender(d, vrS2(d))" in blk,
      "dieselben Handler (Ziel speichern, Unternehmen-Umschalter, Freigabe, Mindest-Chance)")
check("document.querySelectorAll('[data-vr-sich-box]').forEach(el => vrSichBox(el, d, s2))" in HTML and 'id="vr-sich"' not in HTML, "Mindest-Chance an beiden Orten (keine doppelte id)")
check("function vrRender(){ vrRenderVorrat(); try{ vrKaufplanRender() }" in HTML, "jede Änderung zeichnet beide Orte")
rechnen = HTML[HTML.index("async function vrNeuRechnen(){"):HTML.index("async function vrNeuRechnen(){") + 600]
check("await vrLaden(true)" in rechnen and "window._klNeu?.()" in rechnen, "nach dem Speichern: Lauf neu (aktion rechnen), dann Kaufliste frisch")
check(HTML.count("await vrNeuRechnen()") == 2 and "_vr.kpTimer = setTimeout(() => { vrNeuRechnen() }, 1500)" in HTML,
      "Ziel + Mindest-Chance rechnen sofort neu, Freigabe-Klicks gebündelt (1,5 s Ruhe = ein Lauf)")
check("window._klNeu = () => { for(const o of orte) if(o.I.d) o.laden(true) }" in HTML, "Kaufliste beider Orte frisch (am Server-Merker vorbei)")
check(":is(#vr-view,#adm-kp-root) .vr-zl{" in HTML and ":is(#vr-view,#adm-kp-root) .vr-mx-z{" in HTML and ":is(#vr-view,#adm-kp-root) .vr-sich{" in HTML,
      "Design der Blöcke gilt auch im Admin")
check("kaufplan: 'Kaufplan · Ziele, Mindest-Chance, Freigaben'" in HTML, "Untertitel im Kopf")
print(f"\n{n} Prüfungen grün")
