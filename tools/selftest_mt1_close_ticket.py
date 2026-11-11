#!/usr/bin/env python3
"""Selbsttest MT1 Punkt 4 (11.11.2026): Close-Ticket LESEND im Bot statt nur aus dem Copier-Schnappschuss.
Anlass MT1-Abfrage E: Auto-Close meldete 3× „Keine offene Master-Position“ (Schnappschuss leer), alle drei Positionen waren offen.
Prüft: order_bot.close_ticket_aufloesen (rein: Symbol + Richtung, genau eine Position, keins = schon zu, mehrere = Fehler), run_close nimmt
ticket 0 nur mit aufloesen, Verwechslungs-Schutz bleibt; panel.py /api/master-close lässt ticket 0 nur mit aufloesen + Richtung + Symbol durch und
reicht beides an den Bot; prophos.html: Auflösung nur mit opts.lesend, mit Hedge nur bei frischem Schnappschuss, alle vier Close-Wege senden den Body.
Ohne Netz, ohne MetaTrader. Aufruf: python3 tools/selftest_mt1_close_ticket.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
W = os.path.dirname(HIER)
BOT = open(os.path.join(W, "mt5-copier", "order_bot.py"), encoding="utf-8").read()
PANEL = open(os.path.join(W, "mt5-copier", "panel.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        FEHLER.append(text)


i = BOT.index("def close_ticket_aufloesen(")
ns = {}
exec(BOT[i:BOT.index("\n\n\ndef ", i)], ns)
A = ns["close_ticket_aufloesen"]
P = [{"ticket": 11, "symbol": "NAS100", "typ": 0, "volumen": 3.4}, {"ticket": 12, "symbol": "EURUSD", "typ": 1, "volumen": 1.0}]
check(A(P, "NAS100", "buy")[:2] == (11, "eins") and A(P, "nas100", "BUY")[:2] == (11, "eins"), "genau eine passende Position → Ticket (Groß/Klein egal)")
check(A(P, "NAS100", "sell")[:2] == (None, "keins") and A([], "NAS100", "buy")[:2] == (None, "keins"), "keine passende Position → keins")
check(A(P + [{"ticket": 13, "symbol": "NAS100.r", "typ": 0, "volumen": 1}], "NAS100", "buy")[:2] == (None, "mehrere"), "zwei passende → mehrere, nie raten")
check(A(P, "", "buy")[1] == "ungueltig" and A(P, "NAS100", "")[1] == "ungueltig" and A(P, "NAS100", "long")[1] == "ungueltig", "ohne Symbol/Richtung → ungueltig")

rc = BOT[BOT.index("def run_close("):BOT.index("\n\n\ndef ", BOT.index("def run_close("))]
check('aufloesen = ticket <= 0 and cmd.get("aufloesen") is True' in rc and '"ticket fehlt — nichts geklickt"' in rc, "run_close: ticket 0 nur mit aufloesen")
k_auf, k_pos, k_schutz = rc.index("close_ticket_aufloesen(lese"), rc.index('pos = next((p for p in lese["positionen"] if p["ticket"] == ticket)'), rc.index("f\"Verwechslungs-Schutz: {len(")
check(rc.index("lese = _login_dann_lesen(") < k_auf < k_pos < k_schutz, "Auflösung nach der Login-Guard-Lesung, vor Ticket-Prüfung und Verwechslungs-Schutz")
_k = rc[rc.index('if art_ == "keins":'):rc.index('if art_ != "eins":')]
check('"ok": False, "retry_ok": True, "aufgeloest": "keins"' in _k and '"schon_zu"' not in _k and "Keine offene Master-Position gefunden" in _k
      and "nichts geklickt, im Terminal von Hand schliessen" in rc,
      "Prüfer MT1: keins → sichtbarer Fehler mit dem alten Schlüssel-Text (nie ok/schon_zu), mehrere → Fehler ohne Klick")
check(rc.count("_close_klicken(") == 1 and rc.index("_close_klicken(") > k_schutz, "geklickt wird erst nach allen Lese-Prüfungen")
mc = PANEL[PANEL.index('if u.path == "/api/master-close":'):PANEL.index('if u.path == "/api/start-terminal":')]
check('aufloesen_c = ticket <= 0 and body.get("aufloesen") is True and richtung_c in ("buy", "sell") and bool(symbol)' in mc
      and "if ticket <= 0 and not aufloesen_c:" in mc and "cmd.update(aufloesen=True, richtung=richtung_c)" in mc,
      "Panel: ticket 0 nur mit aufloesen + Richtung + Symbol, an den Bot weitergereicht")
check(mc.index("aufloesen_c =") < mc.index('"grund": "copier_alt"') < mc.index("cmd = {"), "Panel: Frische-Riegel (Hedge geht mit) bleibt vor dem Bot-Start")
check("const rohLeer = !(Array.isArray(st.master_positions) && st.master_positions.length)" in HTML
      and "if(!poss.length && rohLeer && opts && opts.lesend && (plan.richtung === 'buy' || plan.richtung === 'sell') && sym)" in HTML,
      "Prüfer MT1: Tab löst nur bei GANZ leerem Schnappschuss lesend auf (Positionen da, keine zum Symbol → sichtbarer Fehler)")
# Verhalten von tpClosePosAufloesen wirklich ausführen (Funktionstext aus prophos.html, ohne Browser: kleine JS→Python-Nachbildung ist zu fragil —
# stattdessen der Ablauf in Python mit denselben Bedingungen, gegen die Textprüfung oben verankert)
def aufl(master_positions, symbol, richtung, lesend=True):
    roh = master_positions if isinstance(master_positions, list) else []
    sym = (symbol or "").strip().lower()
    poss = [x for x in roh if sym in str(x.get("symbol") or "").lower()] if sym else list(roh)
    if richtung in ("buy", "sell"):
        gef = [x for x in poss if int(x.get("type", -1)) == (0 if richtung == "buy" else 1)]
        if gef:
            poss = gef
    if len(poss) != 1:
        if not poss and not roh and lesend and richtung in ("buy", "sell") and sym:
            return "lesend"
        return "fehler"
    return "ticket"
check(aufl([], "NAS100", "buy") == "lesend", "leerer Schnappschuss → lesend im Bot")
check(aufl([{"symbol": "US100", "type": 0, "ident": 5}], "NAS100", "buy") == "fehler", "Positionen da, keine zum Symbol (falsches dup_symbol) → sichtbarer Fehler, NICHT lesend")
check(aufl([{"symbol": "NAS100", "type": 0, "ident": 5}], "NAS100", "buy") == "ticket", "passende Position im Schnappschuss → Ticket wie bisher")
check("return !!(route && route.inst && route.inst.alive && !st.note)" in HTML and "if(ohneHedge) return true" in HTML,
      "Tab: mit Hedge nur bei frischem, lebendigem Schnappschuss; Echo V2 immer")
check(HTML.count("tpCloseLesendErlaubt(route, false)") == 2 and HTML.count("tpCloseLesendErlaubt(routeC, false)") == 1
      and HTML.count("tpCloseLesendErlaubt(route, true)") == 1, "Tab: Hand-Knopf, Signal, Auto-Close mit Hedge-Regel; Echo V2 ohne")
check(HTML.count("JSON.stringify(tpCloseBody(") == 3 and "Object.assign({ ticket, symbol, login: route.masterLogin, ohne_hedge: true }, aufl || {})" in HTML,
      "Tab: alle vier Close-Aufrufe senden aufloesen + richtung mit")
check("const tk = Number(r && r.ticket) || t.ticket" in HTML, "Auto-Close übernimmt das vom Bot gelesene Ticket")
check("const keinePos = !!(r && r.aufgeloest === 'keins' && t.aufloesen)" in HTML and "...(keinePos ? { keine_position: true } : {})" in HTML,
      "Prüfer MT1: Bot-„keins“ nach lesender Auflösung → keine_position (WS2c: war_flach wie vor MT1-4), sonst sichtbarer Fehler")
print()
print("FEHLER: " + ", ".join(FEHLER) if FEHLER else "alles grün")
sys.exit(1 if FEHLER else 0)
