#!/usr/bin/env python3
"""Selbsttest ENDLESUNG ÜBER DIE DEALS (N2, Finn 04.11.2026 ~04:15 Dubai: „der P&L wird nie angezeigt"): mt5-copier/order_bot.py deals_urteil —
Zuordnung des Plan-Trades in der Deal-Historie (Richtung + Volumen + Symbol), P&L nur bei geschlossener Position. Rein rechnend, ohne MT5.
Die Entscheidung im Tab (deUrteil, sfVorOrderBeleg) prüft der Browser-Test über window._deUrteil / window._sfVorOrderBeleg.
Aufruf: python3 tools/selftest_endlesung_deals.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(os.path.dirname(HIER), "mt5-copier", "order_bot.py")
FEHLER = []


def lade():
    src = open(BOT, encoding="utf-8").read()
    i = src.index("\ndef deals_urteil(") + 1
    ns = {}
    exec(src[i:src.find("\n\n\n", i)], ns)
    return ns["deals_urteil"]


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def d(pos, entry, typ=0, sym="NAS100", vol=2.3, profit=0.0, swap=0.0, comm=0.0):
    return {"ticket": pos * 10 + entry, "position": pos, "typ": typ, "entry": entry, "symbol": sym, "volume": vol, "profit": profit, "swap": swap,
            "commission": comm}


def main():
    u = lade()
    # Deal → P&L: BUY 2,3 NAS100 rein und raus, Ausstieg −812,4 + Swap −3 + Kommission −2,1
    r = u([d(7, 0), d(7, 1, typ=1, profit=-812.4, swap=-3, comm=-2.1)], [], "buy", "2.3", "NAS100")
    check(r["treffer"] == [7] and r["pl"] == -817.5 and not r["mehrdeutig"], f"Deal gefunden → P&L −817,5 ({r})")
    # Symbol mit Endung (NAS100.cash) zählt, andere Symbole nicht
    r = u([d(8, 0, sym="NAS100.cash"), d(8, 1, typ=1, sym="NAS100.cash", profit=120)], [], "buy", 2.3, "NAS100")
    check(r["treffer"] == [8] and r["pl"] == 120, "Symbol mit Endung zählt")
    check(u([d(9, 0, sym="US30"), d(9, 1, typ=1, sym="US30", profit=50)], [], "buy", 2.3, "NAS100")["treffer"] == [], "anderes Symbol zählt nicht")
    # falsche Richtung / anderes Volumen → kein Treffer (Trade eines anderen Plans)
    check(u([d(10, 0, typ=1), d(10, 1, typ=0, profit=10)], [], "buy", 2.3, "NAS100")["treffer"] == [], "Gegenrichtung zählt nicht")
    check(u([d(11, 0, vol=2.0), d(11, 1, typ=1, vol=2.0, profit=10)], [], "buy", 2.3, "NAS100")["treffer"] == [], "anderes Volumen zählt nicht")
    # Position noch offen → kein P&L
    r = u([d(12, 0)], [12], "buy", 2.3, "NAS100")
    check(r["offen"] is True and r["pl"] is None, "Position offen → kein P&L")
    # kein Deal → leer (Entscheidung „nicht gelaufen" fällt im Tab mit der Balance-Gegenprobe)
    r = u([], [], "buy", 2.3, "NAS100")
    check(r["treffer"] == [] and r["pl"] is None and not r["mehrdeutig"], "kein Deal → keine Treffer, kein P&L")
    # Gegenprüfung N2: Einstiegs-Kommission zählt mit, zwei passende Trades = mehrdeutig, ohne Richtung/Volumen nie zuordnen
    r = u([d(14, 0, comm=-4.6), d(14, 1, typ=1, profit=300, comm=-4.6)], [], "buy", 2.3, "NAS100")
    check(r["pl"] == 290.8, f"Einstiegs-Kommission zählt mit ({r['pl']})")
    r = u([d(15, 0), d(15, 1, typ=1, profit=10), d(16, 0), d(16, 1, typ=1, profit=20)], [], "buy", 2.3, "")
    check(r["mehrdeutig"] is True and r["pl"] is None, "zwei passende Trades → mehrdeutig, kein P&L")
    check(u([d(17, 0), d(17, 1, typ=1, profit=10)], [], "", 2.3, "NAS100")["mehrdeutig"] is True, "ohne Richtung → nie zuordnen")
    check(u([d(18, 0), d(18, 1, typ=1, profit=10)], [], "buy", "", "NAS100")["mehrdeutig"] is True, "ohne Volumen → nie zuordnen")
    # SELL-Plan
    r = u([d(13, 0, typ=1, vol=20), d(13, 1, typ=0, vol=20, profit=5469)], [], "sell", 20, "NAS100")
    check(r["treffer"] == [13] and r["pl"] == 5469, "SELL-Plan mit Gewinn")
    if FEHLER:
        print(f"\n{len(FEHLER)} Fehler")
        sys.exit(1)
    print("\nalle grün")


if __name__ == "__main__":
    main()
