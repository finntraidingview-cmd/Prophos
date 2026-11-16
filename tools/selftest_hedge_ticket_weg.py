#!/usr/bin/env python3
"""Selbsttest FH3 TICKET-WEG NUR MIT BEWEIS (prophos.html hedgeTicketWegEntscheid + hedgeTicketLebt, 16.11.2026).

Anlass: Plan e7109578 (FundedNext Futures 150k, WD BUY 2 MNQ). Der Copier von Fusion 488579 sah die Positionsliste kurz LEER, alle 7 Solo-
Tickets fielen im 2-s-Takt heraus und kamen 20 s später zurück. Der PC-Tab nahm „Ticket fehlt“ als „Level gefüllt“ und schickte einen echten
Close → lebender Hedge zu, Master ungehedgt. Regel jetzt: Liste leer → nichts; Ticket fehlt, andere da → erst nach 2 Lesungen ≥ 10 s buchen;
gebucht wird ohne Close; Ring-„zu“ und P&L-Nachfrage nur, wenn das Ticket in keiner frischen Liste mehr lebt.

Aufruf:  python3 tools/selftest_hedge_ticket_weg.py
Ohne Netz und ohne Node: schneidet den FH3-Block aus prophos.html und führt ihn mit macOS-JavaScriptCore (jsc) aus. Platzhalter-Tickets.
Geprüft: (1) Liste 1× leer → nichts, Stand bleibt; (2) Ticket 1× weg, andere da → nichts (nur gemerkt); (3) 2× weg ≥ 10 s → buchen;
(4) 2. Lesung < 10 s → noch nichts; (5) Ticket wieder da → Stand weg; (6) leer zwischen zwei Weg-Lesungen zählt nicht; (7) keine Liste /
kein Ticket → nichts; (8) anderes Ticket im Stand → neu zählen; (9) hedgeTicketLebt: lokale Liste, frische Cloud-Zeile, alte Cloud-Zeile,
fremder PC; (10) der Wache-Zweig ruft hedgeSoloSchliessen(…'level_mt5') nicht mehr auf, Ring und P&L-Nachfrage hängen an hedgeTicketLebt."""
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
var window = {};
var ERG = {};
var L = function(){ return Array.prototype.slice.call(arguments).map(function(t){ return { ticket: t } }) };
var T0 = 1000000;
// (1) Liste leer
var e1 = hedgeTicketWegEntscheid([], 111, null, T0, 10000);
ERG.leer = [e1.tun, e1.stand];
// (2) 1× weg, andere da
var e2 = hedgeTicketWegEntscheid(L(222, 333), 111, null, T0, 10000);
ERG.einmal = [e2.tun, e2.stand && e2.stand.n, e2.stand && e2.stand.naechster];
// (3) 2× weg nach 10 s
var e3 = hedgeTicketWegEntscheid(L(222), 111, e2.stand, T0 + 10000, 10000);
ERG.zweimal = [e3.tun, e3.stand && e3.stand.n];
// (4) 2. Lesung zu früh
var e4 = hedgeTicketWegEntscheid(L(222), 111, e2.stand, T0 + 5000, 10000);
ERG.zufrueh = [e4.tun, e4.stand && e4.stand.n];
// (5) wieder da
var e5 = hedgeTicketWegEntscheid(L(111, 222), 111, e2.stand, T0 + 12000, 10000);
ERG.wieder = [e5.tun, e5.stand];
// (6) leer dazwischen: Stand bleibt, danach weg mit anderen → buchen erst, wenn eine NICHT leere Lesung ≥ 10 s nach der ersten kommt
var e6a = hedgeTicketWegEntscheid([], 111, e2.stand, T0 + 11000, 10000);
var e6b = hedgeTicketWegEntscheid(L(222), 111, e6a.stand, T0 + 12000, 10000);
ERG.leerZwischen = [e6a.tun, e6a.stand && e6a.stand.n, e6b.tun];
// leer IMMER (das Vorfall-Muster): 30 Lesungen leer → nie buchen
var st = null, gebucht = false;
for(var i = 0; i < 30; i++){ var x = hedgeTicketWegEntscheid([], 111, st, T0 + i * 11000, 10000); st = x.stand; if(x.tun === 'buchen') gebucht = true }
ERG.immerLeer = gebucht;
// Vorfall: 1 Lesung ohne Ticket (andere weg mit), dann Ticket zurück
var v1 = hedgeTicketWegEntscheid(L(222), 111, null, T0, 10000);
var v2 = hedgeTicketWegEntscheid(L(111, 222), 111, v1.stand, T0 + 20000, 10000);
ERG.vorfall = [v1.tun, v2.tun, v2.stand];
// (7) keine Liste / kein Ticket
ERG.ohne = [hedgeTicketWegEntscheid(null, 111, null, T0, 10000).tun, hedgeTicketWegEntscheid(L(222), null, null, T0, 10000).tun];
// Abstand < 10 s wird auf 10 s gehoben
var e7 = hedgeTicketWegEntscheid(L(222), 111, null, T0, 3000);
ERG.minAbstand = e7.stand.naechster - T0;
// (8) anderes Ticket im Stand → neu zählen
var e8 = hedgeTicketWegEntscheid(L(222), 111, { ticket: 999, n: 1, naechster: T0 }, T0 + 20000, 10000);
ERG.anderes = [e8.tun, e8.stand.n, e8.stand.ticket];
// (9) hedgeTicketLebt
var jetzt = Date.now();
window._mt5CloudRows = [
  { pc_name: 'pc-aaa', updated_at: new Date(jetzt - 5000).toISOString(), status: { hedge_solo: L(500) } },
  { pc_name: 'pc-aaa', updated_at: new Date(jetzt - 120000).toISOString(), status: { hedge_solo: L(600) } },
  { pc_name: 'pc-bbb', updated_at: new Date(jetzt - 5000).toISOString(), status: { hedge_solo: L(700) } }
];
ERG.lebt = [hedgeTicketLebt(111, 'pc-aaa', L(111)), hedgeTicketLebt(500, 'pc-aaa', null), hedgeTicketLebt(600, 'pc-aaa', null),
            hedgeTicketLebt(700, 'pc-aaa', null), hedgeTicketLebt(700, null, null), hedgeTicketLebt(800, 'pc-aaa', L(222)), hedgeTicketLebt(null, 'pc-aaa', L(111))];
// (11) gleicher Copier-Stand zählt nicht doppelt
var s1 = hedgeTicketWegEntscheid(L(222), 111, null, T0, 10000, 5000);
var s2 = hedgeTicketWegEntscheid(L(222), 111, s1.stand, T0 + 20000, 10000, 5000);
var s3 = hedgeTicketWegEntscheid(L(222), 111, s2.stand, T0 + 21000, 10000, 26000);
ERG.gleicherStand = [s2.tun, s3.tun];
// verfallener Stand (> 5 min) fängt neu an
var s4 = hedgeTicketWegEntscheid(L(222), 111, { ticket: 111, n: 1, naechster: T0, seit: T0 }, T0 + 400000, 10000);
ERG.verfallen = [s4.tun, s4.stand.n];
// (12) Ring-Beweis
ERG.ring = [hedgeRingBeweis({ ticket: 1, grund: 'unbekannt', pl: null }), hedgeRingBeweis({ ticket: 1, grund: 'close', pl: null }),
            hedgeRingBeweis({ ticket: 1, grund: 'close', pl: 248.12 }), hedgeRingBeweis({ ticket: 1, grund: 'tp', pl: null }),
            hedgeRingBeweis({ ticket: 1, grund: 'unbekannt', fill_close: 27534.36 }), hedgeRingBeweis(null)];
// (13) P&L-Nachfrage
var n1 = hedgeNachfrageEntscheid([], 111, null, T0, false);
var n2 = hedgeNachfrageEntscheid(L(222), 111, null, T0, false);
var n3 = hedgeNachfrageEntscheid(L(222), 111, n2.fehltSeit, T0 + 30000, false);
var n4 = hedgeNachfrageEntscheid([], 111, n2.fehltSeit, T0 + 70000, false);
var n5 = hedgeNachfrageEntscheid(L(222), 111, n2.fehltSeit, T0 + 61000, false);
var n6 = hedgeNachfrageEntscheid(L(111), 111, n2.fehltSeit, T0 + 61000, true);
var n7 = hedgeNachfrageEntscheid([], 111, null, T0, true);
var n8 = hedgeNachfrageEntscheid(L(222), 111, n4.fehltSeit, T0 + 71000, false);   // nach leerer Lesung neu gezählt
ERG.nachfrage = [n1.ok, n2.ok, n3.ok, n4.ok, n4.fehltSeit === null, n5.ok, n6.ok, n6.fehltSeit, n7.ok, n8.ok, n8.fehltSeit === T0 + 71000];
// (14) abHedgeSolo: Vorfall-Muster (Liste leer + Ring „unbekannt“) darf nie „zu“ sagen (sonst Master zu)
var hh = { ticket: 111, hedge_login: '488579', status: 'offen' };
var inst = function(solo, ring){ return [{ alive: true, status: { hedge_login: '488579', hedge_solo: solo, hedge_solo_zu: ring } }] };
ERG.ab = [abHedgeSolo(hh, inst([], [{ ticket: 111, grund: 'unbekannt', pl: null }])).z,
          abHedgeSolo(hh, inst(L(222), [{ ticket: 111, grund: 'unbekannt', pl: null }])).z,
          abHedgeSolo(hh, inst([], [{ ticket: 111, grund: 'close', pl: 248.12 }])).z,
          abHedgeSolo(hh, inst(L(222), [{ ticket: 111, grund: 'close', pl: 248.12 }])).z,
          abHedgeSolo(hh, inst(L(111), [{ ticket: 111, grund: 'tp', pl: 5 }])).z,
          abHedgeSolo({ ticket: 111, hedge_login: '488579', status: 'geschlossen', weg_beweis: 'x', pl: null }, inst(L(222), [])).z,
          abHedgeSolo({ ticket: 111, hedge_login: '488579', status: 'geschlossen', pl: 12 }, inst(L(222), [])).z,
          abHedgeSolo({ ticket: 111, hedge_login: '488579', status: 'geschlossen', pl: 12 }, inst([], [])).z];
print(JSON.stringify(ERG));
"""


def main():
    if not os.path.exists(JSC):
        print("✗ jsc fehlt (" + JSC + ")")
        sys.exit(1)
    with open(HTML, encoding="utf-8") as f:
        zeilen = f.readlines()
    text = "".join(zeilen)
    block = schnitt(zeilen, "function hedgeTicketWegEntscheid(", "window._hedgeTicketLebt = hedgeTicketLebt")
    block = (block.replace("const _hedgeWegStand", "var _hedgeWegStand").replace("const hedgeWegAbstandMs", "var hedgeWegAbstandMs")
             .replace("const _hedgeFehltSeit", "var _hedgeFehltSeit"))
    block += "\n" + schnitt(zeilen, "  function abHedgeSolo(h, instances){", "window._abHedgeSolo = abHedgeSolo")
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
    check(e["leer"] == ["nichts", None], "(1) Liste 1× leer → nichts, kein Stand")
    check(e["einmal"][0] == "nichts" and e["einmal"][1] == 1 and e["einmal"][2] == 1010000, "(2) Ticket 1× weg, andere da → nichts, gemerkt n=1")
    check(e["zweimal"] == ["buchen", 2], "(3) 2× weg ≥ 10 s auseinander → buchen")
    check(e["zufrueh"] == ["nichts", 1], "(4) 2. Lesung nach 5 s → noch nichts")
    check(e["wieder"] == ["nichts", None], "(5) Ticket wieder da → Stand gelöscht")
    check(e["leerZwischen"] == ["nichts", 1, "buchen"], "(6) leere Lesung zählt nicht, die nächste nicht leere ≥ 10 s bucht")
    check(e["immerLeer"] is False, "(6b) 30 leere Lesungen → nie buchen (Vorfall-Muster Reconnect)")
    check(e["vorfall"] == ["nichts", "nichts", None], "(6c) Vorfall e7109578: 1× weg, dann zurück → nie gebucht")
    check(e["ohne"] == ["nichts", "nichts"], "(7) keine Liste / kein Ticket → nichts")
    check(e["minAbstand"] == 10000, "(7b) Abstand unter 10 s wird auf 10 s gehoben")
    check(e["anderes"] == ["nichts", 1, 111], "(8) Stand eines anderen Tickets → neu zählen")
    check(e["gleicherStand"] == ["nichts", "buchen"], "(11) dieselbe Copier-Lesung zählt nicht doppelt, eine neuere bucht")
    check(e["verfallen"] == ["nichts", 1], "(11b) Stand älter als 5 min fängt neu an")
    check(e["ring"] == [False, False, True, True, True, False], "(12) Ring-Beweis nur mit P&L, Schlusskurs oder echtem Grund — „unbekannt“/„close“ ohne Deal nicht")
    check(e["nachfrage"] == [False, False, False, False, True, True, False, None, True, False, True],
          "(13) P&L-Nachfrage (Close-Aufruf): nie bei leerer Liste ohne Deal, erst nach 60 s Fehlen in nicht leeren Listen, nie wenn das Ticket lebt; mit Deal-Ring auch bei leerer Liste (Ein-Positions-Konto)")
    check(e["ab"] == [None, None, None, "zu", "offen", None, "zu", None],
          "(14) abHedgeSolo: leere Liste → immer warten (auch Deal-Ring), Ring mit Deal + andere da → zu, Weg-Buchung ohne P&L kein Beweis")
    check(e["lebt"] == [True, True, False, False, True, False, False],
          "(9) hedgeTicketLebt: lokal ✓, frische Cloud ✓, alte Cloud ✗, fremder PC ✗, ohne PC ✓, fehlt ✗, ohne Ticket ✗")
    # (10) Verdrahtung im Wächter
    a = text.index("async function hedgeWacheTick(")
    b = text.index("setInterval(hedgeWacheTick, 1000)")
    wache = text[a:b]
    check("hedgeSoloSchliessen(p, 'level_mt5')" not in wache, "(10a) Wächter schickt bei „Ticket fehlt“ keinen Close mehr (hedgeSoloSchliessen level_mt5 weg)")
    check("hedgeTicketWegEntscheid(liste, h.ticket" in wache and "hedgeWegBuchen(p" in wache, "(10b) Wächter entscheidet über hedgeTicketWegEntscheid und bucht über hedgeWegBuchen")
    check("zu && hedgeRingBeweis(zu) && !hedgeTicketLebt(h.ticket, h.pc, liste)" in wache, "(10c) Ring-„zu“ nur mit Deal-Beweis und wenn das Ticket nirgends mehr lebt")
    check("hedgeNachfrageEntscheid(liste, h.ticket" in wache and "if(nf.ok){ await hedgePlNachholen(p)" in wache, "(10d) P&L-Nachfrage (Close-Aufruf) nur über hedgeNachfrageEntscheid")
    check("hedgeSoloLesungFrisch()" in wache and "lesW && lesW.at" in wache, "(10g) 2. Lesung braucht einen neueren Copier-Stand (fetchedAt)")
    check("(p.status === 'open' || p.status === 'review') && h.status === 'geschlossen' && h.weg_beweis && h.pl == null" in wache and "Buchung „zu“ zurückgenommen" in wache,
          "(10f) Rücknahme: ohne Close gebucht + Ticket wieder in der Liste → wieder offen (nur laufender Plan)")
    c = text.index("async function hedgeWegBuchen(")
    buch = text[c:text.index("\n  }\n", c)]
    check("mtcApi" not in buch and "hedgeSoloSchliessen" not in buch, "(10e) hedgeWegBuchen spricht den Copier nicht an")
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("OK — alle Prüfungen grün")


if __name__ == "__main__":
    main()
