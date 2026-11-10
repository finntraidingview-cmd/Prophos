#!/usr/bin/env python3
"""Selbsttest B1+B2 (RA1, Master 11.11.2026): zwei Echo-Pläne (The5%ers 100k, 10.11.) endeten mit „KEINE Bestätigung — Server „Only position closing is
allowed“ … Position nicht am Konto“, wurden als UNKLAR markiert und vom Tages-Reset nach Überprüfen geschoben, obwohl der Server die Order abgelehnt hatte.
 B1) ORDER_GRUND_REGELN kennt „Only position closing is allowed“ → Grund mit Quelle „Journal: […]“, Satz bleibt wörtlich (E1-Muster nur_schliessen).
 B2) journal_order_zaehlung + server_abgelehnt_urteil (Schnittstelle mit S1): Journal-Regel-Grund mit „failed …“ seit dem Klick bzw. roter Dialog-Text per
     Regel, Journal lesbar, keine Erfolgszeile, nicht mehr Anfragen als Ablehnungen = nachweislich abgelehnt; sonst kein Beleg.
     run(): mit Beleg server_abgelehnt True + grund, retry_ok bleibt False, Kopf trägt „nichts platziert“ (sfVorOrderBeleg); ohne Beleg wie heute (kein Feld).
Journal-Zeilen mit Platzhalter-Login. Aufruf: python3 tools/selftest_b1b2_nur_schliessen.py"""
import inspect
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


# B1
g = ob.order_grund_aus_text("Only position closing is allowed")
check(bool(g) and g[0] == "Konto nimmt nur Schließen an (Server: Only position closing is allowed)" and "nicht neu starten" in g[1],
      "B1 Regel erkennt „Only position closing is allowed“")
j = ("Only position closing is allowed", "2026.11.10 07:58:12.345 Trades '12345678': failed market sell 3 NAS100 [Only position closing is allowed]")
gb = ob.order_grund_bestimmen(j, "", {"balance": 100044.66})
check(gb[2] == "Journal: [Only position closing is allowed]" and gb[0].startswith("Konto nimmt nur Schließen an (Server: ") and "Kontostand 100 044.66" in gb[0],
      "B1 order_grund_bestimmen: Quelle „Journal: […]“ statt „Journal“, Kontostand dabei")
with open(os.path.join(WURZEL, "app.py"), encoding="utf-8") as f:
    app_src = f.read()
check("Only position closing is allowed" in gb[0] and re.search(r'"art": "nur_schliessen", "re": re\.compile\(r"Only position closing is allowed"', app_src),
      "B1 Satz bleibt wörtlich → E1-Regel nur_schliessen (app.py) trifft weiter")
check(ob.order_grund_aus_text("[Trade disabled]")[0].startswith("Handel am Konto gesperrt"), "B1 übrige Regeln unverändert (Trade disabled)")

# B2 Journal-Beleg
def NA(zeilen, login=None, symbol="NAS100", richtung="sell", ab_s=None, stufen=1):
    z = ob.journal_order_zaehlung(zeilen, login if login is not None else L, symbol, richtung, ab if ab_s is None else ab_s)
    return ob.server_abgelehnt_urteil("Journal: [Only position closing is allowed]", z, bool(zeilen), "Konto nimmt nur Schließen an", stufen), \
        z["failed_zeile"] if z["abgelehnt"] else None


L = "12345678"
ab = 7 * 3600 + 58 * 60 + 0.0   # Klick 07:58:00
anfr = f"2026.11.10 07:58:01.100 Trades '{L}': market sell 3 NAS100 sl: 0 tp: 0"
fail = f"2026.11.10 07:58:01.400 Trades '{L}': failed market sell 3 NAS100 sl: 0 tp: 0 [Only position closing is allowed]"
ok_z = f"2026.11.10 07:58:02.000 Trades '{L}': accepted market sell 3 NAS100"
deal = f"2026.11.10 07:58:03.000 Trades '{L}': deal #998877 sell 3 NAS100 at 20000.0 done"
check(NA([anfr, fail]) == (True, fail), "B2a Anfrage + failed → nachweislich abgelehnt")
check(NA([fail])[0] is True, "B2b nur failed-Zeile → Beleg")
check(NA([anfr, fail, ok_z])[0] is False, "B2c accepted danach → kein Beleg")
check(NA([anfr, fail, deal])[0] is False, "B2d deal # … done → kein Beleg")
anfr2 = anfr.replace("07:58:01.100", "07:58:05.100")
check(NA([anfr, fail, anfr2])[0] is False, "B2e zweite Anfrage ohne Ablehnung → kein Beleg")
check(NA([anfr])[0] is False, "B2f nur Anfrage, keine Ablehnung → kein Beleg")
check(NA([])[0] is False, "B2g Journal leer/unlesbar → kein Beleg")
alt = fail.replace("07:58:01.400", "07:40:01.400")
check(NA([alt])[0] is False, "B2h Ablehnung VOR dem Klick (alter Lauf) → kein Beleg")
check(NA([fail.replace(L, "87654321")])[0] is False, "B2i anderes Konto → kein Beleg")
check(NA([fail], richtung="buy")[0] is False, "B2j andere Richtung → kein Beleg")
mod = f"2026.11.10 07:58:01.900 Trades '{L}': modify #1179274 sell 3 NAS100 sl: 1 tp: 2 done"
check(NA([anfr, fail, mod])[0] is True, "B2k „modify #…“ einer anderen Position zählt nicht")
mitter = f"2026.11.10 00:00:00.300 Trades '{L}': failed market sell 3 NAS100 [Only position closing is allowed]"
check(NA([mitter], ab_s=86399.5)[0] is True, "B2l über Mitternacht (Klick 23:59:59) → Beleg")

zr = {"anfragen": 0, "abgelehnt": 0, "erfolg": 0, "zeilen_seit_klick": 3, "failed_unbekannt": 0}
GS = "SL/TP ungültig (Server: Invalid stops)"
check(ob.server_abgelehnt_urteil("Order-Dialog", zr, True, GS) is True, "B2q roter Dialog-Text (Server-Antwort), Journal seit Klick ohne Anfrage/Erfolg → abgelehnt")
check(ob.server_abgelehnt_urteil("Order-Dialog", zr, False, GS) is False, "B2r Dialog-Text, Journal unlesbar → kein Beleg")
check(ob.server_abgelehnt_urteil("Order-Dialog", dict(zr, anfragen=1), True, GS) is False, "B2s Dialog-Text, aber Anfrage ohne Ablehnung im Journal → kein Beleg")
check(ob.server_abgelehnt_urteil("Order-Dialog", zr, True, "Algo Trading im Terminal aus") is False
      and ob.server_abgelehnt_urteil("Order-Dialog", zr, True, "zu viele Anfragen (Server)") is False,
      "B2w Prüfer S2: „Algo Trading“/„zu viele“ (statische Dialog-Beschriftung möglich) → kein Dialog-Beleg")
check(ob.server_abgelehnt_urteil("Order-Dialog", dict(zr, zeilen_seit_klick=0), True, GS) is False,
      "B2x Prüfer S1: Journal ohne Zeile seit dem Klick (z. B. still die Datei von gestern) → kein Beleg")
check(ob.server_abgelehnt_urteil("Journal", dict(zr, abgelehnt=1), True) is False, "B2t unbekannter Journal-Text (Quelle „Journal“ ohne Regel) → kein Beleg")
check(ob.server_abgelehnt_urteil("API", dict(zr, abgelehnt=1), True) is False, "B2u API-Rechnung (Marge/Konto) → kein Beleg")
check(ob.server_abgelehnt_urteil("Journal: [Trade disabled]", zr, True) is False, "B2v Journal-Regel, aber keine failed-Zeile seit Klick → kein Beleg")

# Prüfer-Nachzug: echtes Datei-Format („IE\t0\t…“), Stufen, unbekannter Grund, weitere Erfolgszeilen
E = lambda t, rest: f"IE\t0\t{t}\tTrades\t'{L}': {rest}"   # noqa: E731
r_anfr, r_fail = E("07:58:01.100", "market sell 3 NAS100 sl: 0 tp: 0"), E("07:58:01.400", "failed market sell 3 NAS100 sl: 0 tp: 0 [Only position closing is allowed]")
check(NA([r_anfr, r_fail]) == (True, r_fail), "B2y echtes Journal-Format → Beleg")
check(NA([r_anfr, r_fail], stufen=2)[0] is False, "B2z Prüfer S3: zwei Stufen gedrückt, nur eine Ablehnung → kein Beleg")
r_fail2 = E("07:58:31.400", "failed market sell 3 NAS100 [Only position closing is allowed]")
check(NA([r_anfr, r_fail, E("07:58:31.100", "market sell 3 NAS100"), r_fail2], stufen=2)[0] is True, "B2z2 zwei Stufen, zwei Ablehnungen → Beleg")
r_to = E("07:58:01.500", "failed market sell 3 NAS100 [Request canceled by timeout]")
check(NA([r_anfr, r_fail, r_to])[0] is False, "B2h2 Hinweis: eigene Ablehnung mit unbekanntem Grund (Timeout) → kein Beleg")
check(NA([r_anfr, E("07:58:01.600", "failed market sell 3 NAS100 [Request canceled by timeout]")])[0] is False, "B2h3 nur Timeout-Ablehnung → kein Beleg")
check(NA([r_anfr, r_fail, E("07:58:02.000", "order #5566 sell 3 / 3 NAS100 done")])[0] is False
      and NA([r_anfr, r_fail, E("07:58:02.000", "market sell 3 NAS100 placed for execution")])[0] is False,
      "B2c2 „order #… done“ / „placed for execution“ → kein Beleg")
check(NA([E("07:40:00.000", "irgendwas"), E("07:41:00.000", "failed market sell 3 NAS100 [Only position closing is allowed]")])[0] is False,
      "B2x2 Journal endet vor dem Klick (alte Datei) → kein Beleg")
src0 = inspect.getsource(ob.run)
check('_stufen = sum(1 for _e in list(trail)[_klick_spur_i:] if f"{muster}-Knopf: " in str(_e))' in src0 and "_klick_spur_i = len(trail)" in src0,
      "B2n2 run() zählt die gedrückten Stufen seit dem Klick")

# B2 Verdrahtung run()
src = inspect.getsource(ob.run)
i_g = src.find("    if grund:\n")
blk = src[i_g:src.find("return {\"ok\": False, \"retry_ok\": False, \"grund\": grund[0]", i_g)]
check("server_abgelehnt_urteil(" in blk and '"retry_ok": False, "server_abgelehnt": True' in blk and '"grund": grund[0]' in blk,
      "B2m run(): mit Beleg server_abgelehnt True + grund, retry_ok bleibt False")
check(src.count('"server_abgelehnt"') == 1, "B2m2 das Feld kommt nur in diesem einen Ausgang vor (ohne Beleg kein Feld)")
check("_klick_ab_s = _jetzt_s() - 1.0" in src and src.find("_klick_ab_s = _jetzt_s()") < src.find("ausgeloest, anfrage_gesehen = stufen_ausloesen("),
      "B2n Klickzeit vor den Auslöse-Stufen gemerkt")
# Kopf der Meldung → sfVorOrderBeleg (prophos.html) „nicht platziert“
with open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8") as f:
    html = f.read()
msg = (f"KEINE Bestaetigung binnen 12 s — Grund: {gb[0]} ({gb[2]}) → {gb[1]}. Position nicht am Konto, vom Server abgelehnt — nichts platziert. "
       "Spur: [0.1s·Hand: x → y] · Dialog: d")
kopf = re.split(r"\s+(?:Spur:|\[(?=[\d…]|\.\.\.))", msg)[0]
check("/nichts platziert/i" in html and "nichts platziert" in kopf and "(API:" not in kopf, "B2o Kopf trägt „nichts platziert“ → sfVorOrderBeleg greift")
check(bool(re.search(r"^KEINE Bestaetigung binnen \d+ s — Grund: [^(]*\((Server|Journal): ", kopf, re.I)), "B2p Kopf trifft auch die Server-/Journal-Regel des Tabs")

print()
print("FEHLER: " + ", ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
