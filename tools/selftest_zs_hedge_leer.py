#!/usr/bin/env python3
"""Selbsttest FH5 ZUFALLS-SCHLUSS: LEERE SOLO-LISTE IST KEIN „HEDGE WEG“ (prophos.html zsHedgeLesung, 16.11.2026).

Anlass: Hinweis S2 nach FH3 (Vorfall e7109578: Copier von Fusion 488579 sah die Positionsliste ~20 s leer). zsHedgeBeweis zählt zwei
Lesungen „weg“ hintereinander als „Hedge zu“ — eine leere Liste darf dabei nicht zählen, sonst unterdrückt die Lücke den Alarm „Hedge NICHT zu“.

Aufruf:  python3 tools/selftest_zs_hedge_leer.py
Ohne Netz und ohne Node: schneidet hedgeRingBeweis + zsHedgeLesung aus prophos.html, führt sie mit macOS-JavaScriptCore (jsc) aus.
Geprüft: (1) Liste leer ohne Ring → null; (2) Ticket da → false; (3) Ticket fehlt, andere da → true; (4) leer + Ring „unbekannt“ ohne Deal → null;
(5) leer + Ring mit Deal → true (Ein-Positions-Konto nach echtem Schluss); (6) eine Instanz meldet null → null; (7) keine lebende Instanz → null;
(8) Ticket in einer zweiten Instanz → false (Vereinigung); (9) Echo unverändert; (10) Filter je Hedge-Login."""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HIER, "..", "prophos.html")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def schnitt(zeilen, anfang, ende):
    a = next(i for i, z in enumerate(zeilen) if anfang in z)
    b = next(i for i, z in enumerate(zeilen) if i >= a and ende in z)
    return "".join(zeilen[a:b + 1])


TEST = r"""
var I = function(solo, ring){ return { alive: true, status: { hedge_solo: solo, hedge_solo_zu: ring || [] } } };
var L = function(){ return Array.prototype.slice.call(arguments).map(function(t){ return { ticket: t } }) };
var E = {};
E.leer = zsHedgeLesung('solo', [I([])], 111, null);
E.da = zsHedgeLesung('solo', [I(L(111, 222))], 111, null);
E.weg = zsHedgeLesung('solo', [I(L(222))], 111, null);
E.leerUnbekannt = zsHedgeLesung('solo', [I([], [{ ticket: 111, grund: 'unbekannt', pl: null }])], 111, null);
E.leerDeal = zsHedgeLesung('solo', [I([], [{ ticket: 111, grund: 'close', pl: 12.5, fill_close: 27000 }])], 111, null);
E.instNull = zsHedgeLesung('solo', [I(L(222)), { alive: true, status: { hedge_solo: null } }], 111, null);
E.keine = zsHedgeLesung('solo', [{ alive: false, status: { hedge_solo: L(222) } }], 111, null);
E.zweite = zsHedgeLesung('solo', [I(L(222)), I(L(111))], 111, null);
// (10) Login-Filter: eigenes Konto leer, fremdes Konto hat Tickets → null (nicht „andere da“)
var IL = function(login, solo, ring){ return { alive: true, status: { hedge_login: login, hedge_solo: solo, hedge_solo_zu: ring || [] } } };
E.loginLeer = zsHedgeLesung('solo', [IL('488579', []), IL('430095', L(222))], 111, null, '488579');
E.ohneLogin = zsHedgeLesung('solo', [IL('488579', []), IL('430095', L(222))], 111, null);
E.loginWeg = zsHedgeLesung('solo', [IL('488579', L(333)), IL('430095', L(111))], 111, null, '488579');
E.echoWeg = zsHedgeLesung('echo', [{ file: 'a', alive: true, status: { master_positions: [], hedges: {} } }], 5, 'a');
E.echoDa = zsHedgeLesung('echo', [{ file: 'a', alive: true, status: { master_positions: [], hedges: { '5': [{ ticket: 9 }] } } }], 5, 'a');
print(JSON.stringify(E));
"""


def main():
    if not os.path.exists(JSC):
        print("✗ jsc fehlt (" + JSC + ")")
        sys.exit(1)
    with open(HTML, encoding="utf-8") as f:
        zeilen = f.readlines()
    block = schnitt(zeilen, "  function hedgeRingBeweis(z){", "window._hedgeRingBeweis = hedgeRingBeweis")
    block += "\n" + schnitt(zeilen, "  function zsHedgeLesung(art, instances, ticket, file", "window._zsHedgeLesung = zsHedgeLesung")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
        t.write("var window = {};\n" + block + "\n" + TEST)
        pfad = t.name
    try:
        out = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(pfad)
    if out.returncode != 0 or not out.stdout.strip():
        print("✗ jsc lief nicht: " + (out.stderr or out.stdout)[:400])
        sys.exit(1)
    e = json.loads(out.stdout.strip().splitlines()[-1])
    check(e["leer"] is None, "(1) Liste komplett leer, kein Ring → null (kein Beweis, Reconnect)")
    check(e["da"] is False, "(2) Ticket in der Liste → false (Hedge da)")
    check(e["weg"] is True, "(3) Ticket fehlt, andere Tickets da → true")
    check(e["leerUnbekannt"] is None, "(4) leer + Ring „unbekannt“ ohne Deal → null (Vorfall-Muster)")
    check(e["leerDeal"] is True, "(5) leer + Ring mit Deal → true (Ein-Positions-Konto nach echtem Schluss)")
    check(e["instNull"] is None, "(6) eine Instanz meldet hedge_solo null → null")
    check(e["keine"] is None, "(7) keine lebende Instanz → null")
    check(e["zweite"] is False, "(8) Ticket in einer zweiten Instanz → false (Vereinigung)")
    check(e["echoWeg"] is True and e["echoDa"] is False, "(9) Echo unverändert")
    check(e["loginLeer"] is None and e["ohneLogin"] is True and e["loginWeg"] is True,
          "(10) mit hedge_login zählen nur die Instanzen dieses Fusion-Kontos (eigenes leer + fremdes voll → null)")
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("OK — alle Prüfungen grün")


if __name__ == "__main__":
    main()
