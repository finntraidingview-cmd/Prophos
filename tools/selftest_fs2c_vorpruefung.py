#!/usr/bin/env python3
"""Selbsttest FS2-C (Master 11.11.2026 nach dem FS2-Befund; Finn: „… diese Fehlerklassen mit so was wie Lots eliminieren“): Order-Vorprüfung vor F9.
Die ECHTEN Funktionen aus mt5-copier/order_bot.py laufen ohne Windows und ohne MetaTrader5 — die API-Lesung ist eine Attrappe.
Fälle = die K5-Formen aus den Code-Spuren (Rohwerte aus der DB fehlen dieser Session; Platzhalter statt echter Konten):
 a) Lots nicht auf dem Raster → gerundet wie copier.norm_vol, Korrektur in der Spur; 2,7 Lot bei Step 0,01 bleibt unverändert (Float).
 b) Lots unter Minimum / über Maximum → nicht senden, Grund mit Zahlen.
 c) „No money“ (Fall 20.10.: 4 Lot gescheitert) → Marge mit den KORRIGIERTEN Lots, nicht senden.
 d) „Trade disabled“ / GR1 (Volumen-Feld gesperrt, Handel am Konto aus) → nicht senden, Text trifft sfGesperrt + FD_REZEPTE „konto“ (Schlüssel).
 e) „Only position closing“ (Symbol close-only) und LONGONLY/SHORTONLY gegen die Plan-Richtung → nicht senden.
 f) „Invalid stops“ → F9-SL/TP auf den Mindestabstand, nur weiter weg; ohne Stops-Level unverändert.
 g) API unlesbar → keine Prüfung, kein Abbruch (Stand vorher).
 h) Verdrahtung in run(): Vorprüfung vor dem ersten Fenster-Schritt, Abbruch mit code vorpruefung + retry_ok True, Stops-Klemme nach berechne_sl_tp.
Aufruf: python3 tools/selftest_fs2c_vorpruefung.py"""
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


NAS = {"symbol": "NAS100", "verbunden": True, "handel_konto": True, "symbol_modus": 4, "balance": 100000.0,
       "marge_frei": 95000.0, "volume_step": 0.01, "volume_min": 0.01, "volume_max": 100.0, "stops_level": 0.0, "point": 0.01}


def api(**ueber):
    d = dict(NAS)
    d.update(ueber)
    return d


# a) Raster
u = ob.order_vorpruefung_urteil(2.7, "buy", api())
check(u["abbruch"] is None and u["vol"] == 2.7 and not u["korrekturen"], "a1 2,7 Lot bei Step 0,01: keine Korrektur (Float sauber)")
u = ob.order_vorpruefung_urteil(2.75, "sell", api(volume_step=0.1, volume_min=0.1))
check(u["abbruch"] is None and abs(u["vol"] - 2.8) < 1e-9 and u["korrekturen"] and "2.75 → 2.8" in u["korrekturen"][0],
      "a2 2,75 Lot bei Step 0,1 → 2,8 mit Grund")
u = ob.order_vorpruefung_urteil(3.004, "buy", api())
check(u["abbruch"] is None and u["vol"] == 3.0, "a3 3,004 Lot → 3 (Rest unter einem Step)")
u = ob.order_vorpruefung_urteil(1.3, "buy", api(volume_step=1.0, volume_min=1.0))
check(u["abbruch"] is None and u["vol"] == 1.0, "a4 1,3 Lot bei ganzen Lots → 1")
check(ob.vol_auf_raster(2.5, None, None, None) == (2.5, None), "a5 ohne Step: Größe unverändert")
check(ob.vol_auf_raster(1.15, 0.1, 0.1, 100)[0] == 1.1 and ob.vol_auf_raster(2.5, 1, 1, 100)[0] == 2.0,
      "a6 Rundung wie copier.norm_vol (1,15 → 1,1 Float; 2,5 → 2 zur geraden Zahl) — deterministisch")

# b) Minimum / Maximum
u = ob.order_vorpruefung_urteil(0.4, "buy", api(volume_step=1.0, volume_min=1.0))
check(u["abbruch"] and "unter dem Minimum 1" in u["abbruch"][0] and u["abbruch"][0].startswith("Volumen ungültig"),
      "b1 0,4 Lot bei Minimum 1 → nicht senden, Grund mit Zahlen")
u = ob.order_vorpruefung_urteil(150, "buy", api())
check(u["abbruch"] and "über dem Maximum 100" in u["abbruch"][0], "b2 150 Lot über Maximum 100 → nicht senden (nie still klemmen)")

# c) Marge mit korrigierten Lots
check(ob.order_marge_urteil(api(marge_noetig=120000.0, marge_frei=95000.0))[0].startswith("zu wenig freie Marge für dieses Volumen (Vorprüfung: nötig 120 000.00, frei 95 000.00)"),
      "c1 No money: Grund mit Zahlen, Klammer „(Vorprüfung:“ statt „(API:“ (Prüfer S2)")
check(ob.order_marge_urteil(api(marge_noetig=3000.0)) is None, "c2 Marge reicht → kein Abbruch")
check(ob.order_marge_urteil(api()) is None, "c3 Marge nicht gerechnet → keine Aussage")


class Spur(list):
    def sekunden(self):
        return 0.0


aufrufe = []


def attrappe(antworten):
    def _z(path, expected, symbol, richtung=None, volumen=None):
        aufrufe.append(volumen)
        return dict(antworten["mit"] if volumen else antworten["ohne"])
    return _z


_echt = ob._order_api_zustand
try:
    aufrufe.clear()
    ob._order_api_zustand = attrappe({"ohne": api(volume_step=0.1, volume_min=0.1),
                                      "mit": api(marge_noetig=99000.0, marge_frei=95000.0)})
    t = Spur()
    vp = ob._order_vorpruefung("C:/MT5-x/terminal64.exe", 12345678, "NAS100", "buy", 4.04, t)
    check(aufrufe == [None, 4.0], "c4 Marge wird mit den gerundeten Lots gerechnet (4,04 → 4,0)")
    check(vp["abbruch"] and "zu wenig freie Marge" in vp["abbruch"][0] and any("nicht senden" in z for z in t),
          "c5 No money (Fall 20.10.) → nicht senden, Spur sagt es")
    # g) unlesbar
    ob._order_api_zustand = lambda *a, **k: {"symbol": "NAS100"}
    t = Spur()
    vp = ob._order_vorpruefung("p", 1, "NAS100", "buy", 2.0, t)
    check(vp["abbruch"] is None and vp["vol"] == 2.0 and any("ohne Prüfung weiter" in z for z in t), "g1 API ohne Zustand → keine Prüfung, kein Abbruch")

    def wirft(*a, **k):
        raise OSError("kaputt")
    ob._order_api_zustand = wirft
    t = Spur()
    vp = ob._order_vorpruefung("p", 1, "NAS100", "buy", 2.0, t)
    check(vp["abbruch"] is None and vp["vol"] == 2.0, "g2 Lesung wirft → keine Prüfung, kein Abbruch")
    ob._order_api_zustand = attrappe({"ohne": api(), "mit": {"symbol": "NAS100"}})
    vp = ob._order_vorpruefung("p", 1, "NAS100", "buy", 2.0, Spur())
    check(vp["abbruch"] is None, "g3 Marge-Lesung leer → kein Abbruch")
finally:
    ob._order_api_zustand = _echt

# d) Konto gesperrt — Schlüssel-Texte
u = ob.order_vorpruefung_urteil(2.0, "buy", api(handel_konto=False, balance=90002.0))
g = u["abbruch"][0] if u["abbruch"] else ""
with open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8") as f:
    html = f.read()
mg = re.search(r"const sfGesperrt = m => \{ m = String\(m \|\| ''\); if\(!/(.+?)/i\.test\(m\)\)", html)
check(bool(mg), "d0 sfGesperrt-Regex in prophos.html gefunden")
check(bool(mg) and bool(re.search(mg.group(1), g, re.I)) and "Kontostand 90 002.00" in g,
      "d1 trade_allowed False → nicht senden, Text trifft sfGesperrt (Deckel sofort voll) mit Kontostand")
# FD_REZEPTE liegt in app.py — das Muster wird aus der Quelle gelesen, nicht abgeschrieben
with open(os.path.join(WURZEL, "app.py"), encoding="utf-8") as f:
    app_src = f.read()
m = re.search(r'\("konto", r"([^"]+)"', app_src)
check(bool(m) and re.search(m.group(1), ob.vorpruefung_meldung(g, "x", "spur")), "d2 Meldung trifft FD_REZEPTE „konto“ (Fehlstart-Doktor)")
u = ob.order_vorpruefung_urteil(2.0, "buy", api(verbunden=False))
check(u["abbruch"] and u["abbruch"][0] == "Terminal nicht mit dem Server verbunden", "d3 Terminal getrennt → nicht senden")

# e) Symbol-Modus
u = ob.order_vorpruefung_urteil(2.0, "sell", api(symbol_modus=3))
check(u["abbruch"] and "Close only" in u["abbruch"][0], "e1 Only position closing (close-only) → nicht senden")
u = ob.order_vorpruefung_urteil(2.0, "sell", api(symbol_modus=1))
check(u["abbruch"] and "LONGONLY" in u["abbruch"][0], "e2 Symbol nur Kauf, Plan Verkauf → nicht senden")
u = ob.order_vorpruefung_urteil(2.0, "buy", api(symbol_modus=1))
check(u["abbruch"] is None, "e3 Symbol nur Kauf, Plan Kauf → frei")
u = ob.order_vorpruefung_urteil(2.0, "buy", api(symbol_modus=0))
check(u["abbruch"] and "DISABLED" in u["abbruch"][0], "e4 Symbol gesperrt → nicht senden")
u = ob.order_vorpruefung_urteil(2.0, "buy", api(symbol_modus=2))
check(u["abbruch"] and "SHORTONLY" in u["abbruch"][0], "e5 Symbol nur Verkauf, Plan Kauf → nicht senden")
u = ob.order_vorpruefung_urteil(2.0, "buy", api(handel_konto=None, symbol_modus=None))
check(u["abbruch"] is None, "e6 Konto/Symbol-Modus nicht gelesen (anderer Login) → kein Abbruch")

# f) Stops-Abstand (Kauf gegen Bid, Verkauf gegen Ask, 1 point Rand)
sl, tp, tx = ob.sltp_mindestabstand("buy", 20000.5, 20000.0, 19999.9, 20000.3, 50, 0.01, 2)
check(sl == 19999.49 and tp == 20000.51 and len(tx) == 2, "f1 Kauf: SL/TP zu nah → 51 Punkte vom Bid weg")
sl, tp, tx = ob.sltp_mindestabstand("sell", 20000.5, 20000.0, 20000.6, 20000.2, 50, 0.01, 2)
check(sl == 20001.01 and tp == 19999.99 and len(tx) == 2, "f2 Verkauf: SL/TP zu nah → 51 Punkte vom Ask weg")
sl, tp, tx = ob.sltp_mindestabstand("buy", 20000.5, 20000.0, 19900.0, 20100.0, 50, 0.01, 2)
check((sl, tp, tx) == (19900.0, 20100.0, []), "f3 weit genug → unverändert (nie näher)")
sl, tp, tx = ob.sltp_mindestabstand("buy", 20000.5, 20000.0, 19999.9, 20000.3, 0, 0.01, 2)
check((sl, tp, tx) == (19999.9, 20000.3, []), "f4 Stops-Level 0 → unverändert")
sl, tp, tx = ob.sltp_mindestabstand("buy", None, None, 19999.9, 20000.3, 50, 0.01, 2)
check(tx == [], "f5 ohne Kurs → unverändert")

# q) Fälle aus Q7 (Master 11.11.2026, 14 MT5-Fälle der letzten 8 Tage, nur HT; Plan-Werte echt, Kurs/Spread/Stops-Level ANGENOMMEN — die Spur hat sie nicht)
# q1 The5%ers 100k, 29 Lot Kauf, SL 280 $, TP 5416 $, Kontostand 90 230 (SL am Rest bis zur Max-DD-Grenze): SL-Abstand 280/29 = 9,66 Punkte ab Ask.
#    Der Broker prüft gegen Bid: bei 1,5 Punkten Spread bleiben 8,16 Punkte. Mit angenommenem Stops-Level 1000 Punkte (10,00) → „Invalid stops“.
ask, bid = 26996.53, 26995.03
sl0, tp0 = ob.berechne_sl_tp("buy", ask, 29, 1.0, 280, 5416, 2)
sl, tp, tx = ob.sltp_mindestabstand("buy", ask, bid, sl0, tp0, 1000, 0.01, 2)
check(sl < sl0 and abs((bid - sl) - 10.01) < 1e-6 and tp == tp0 and len(tx) == 1,
      f"q1 Q7 11-06 The5%ers 29 Lot SL 280 $: SL auf 10,01 Punkte unter Bid geweitet (+{(sl0 - sl) * 29:.0f} $), TP unverändert → Order geht durch")
# q2 Tradeify CFD 3,4 Lot Kauf, SL 1936 $ (569 Punkte): weit genug → keine Korrektur, die Vorprüfung ändert hier nichts
sl0, tp0 = ob.berechne_sl_tp("buy", 27007.10, 3.4, 1.0, 1936, 4342, 2)
check(ob.sltp_mindestabstand("buy", 27007.10, 27005.60, sl0, tp0, 1000, 0.01, 2)[2] == [], "q2 Q7 11-09 Tradeify CFD 3,4 Lot: Abstand groß → unverändert")
# q3 „Volumen-Feld übernimmt X nicht“ (8×, GR1: Feld im F9-Dialog gesperrt). Liefert die API dann trade_allowed False / Symbol gesperrt,
#    bricht die Vorprüfung VOR dem Terminal ab; die Q7-Meldungen tragen aber KEINEN „— Grund:“-Teil → die API sah damals nichts → dieser Teil bleibt offen
for n, lots in (("q3a", 21), ("q3b", 3.1)):
    u = ob.order_vorpruefung_urteil(lots, "buy", api(handel_konto=False))
    check(u["abbruch"] and "trade_allowed = False" in u["abbruch"][0], f"{n} Volumen-Feld-Fall mit trade_allowed False ({lots} Lot) → sauber abgelehnt")
u = ob.order_vorpruefung_urteil(21, "buy", api())
check(u["abbruch"] is None and u["vol"] == 21, "q3c Volumen-Feld-Fall OHNE API-Grund → Vorprüfung frei (offen, eigener Befund)")

# Meldung: Anfang fest, nichts gesendet, Fix
ml = ob.vorpruefung_meldung("Symbol NAS100 nur Schließen erlaubt (Close only)", "später neu starten", "0.1s·a → b")
check(ml.startswith("Vorprüfung vor F9: Symbol NAS100 nur Schließen erlaubt") and "nichts gesendet. → später neu starten" in ml,
      "m1 Meldung: feste Anfangsworte, die eine Ursache, nichts gesendet, Fix")

# m2) sfVorOrderBeleg (prophos.html): Kopf bis vor die Bot-Spur „ [0.1s·…“ — muss „nichts gesendet“ tragen und darf kein „(API:“ enthalten
check("/nichts gesendet/i" in html and "\\(API:/i.test(kopf)" in html, "m2a sfVorOrderBeleg-Regeln in prophos.html wie angenommen")
for gr in [ob.order_marge_urteil(api(marge_noetig=120000.0))[0], ob.order_vorpruefung_urteil(0.4, "buy", api(volume_step=1.0, volume_min=1.0))["abbruch"][0]]:
    kopf = re.split(r"\s+(?:Spur:|\[(?=[\d…]|\.\.\.))", ob.vorpruefung_meldung(gr, "fix", "0.1s·Hand: x → y"))[0]
    check("nichts gesendet" in kopf and "(API:" not in kopf, "m2b Beleg „nicht platziert“ im Kopf: " + gr[:40])
check("f9_vorpruefung" in ob.FEHLERFOTO_CODES_OHNE, "m3 kein Fehlerfoto bei der Vorprüfung (beweisbar nichts getippt)")

# h) Verdrahtung in run()
src = inspect.getsource(ob.run)
i_vp, i_term = src.find("_order_vorpruefung("), src.find("_finde_terminal_geduldig(")
check(0 < i_vp < i_term, "h1 Vorprüfung läuft vor dem ersten Fenster-Schritt (Terminal-Suche)")
blk = src[i_vp:i_term]
check('"code": "f9_vorpruefung"' in blk and '"retry_ok": True' in blk and "_puls_diagnose_senden" in blk,
      "h2 Abbruch: code f9_vorpruefung (nicht Polars „vorpruefung“), retry_ok True (nichts gesendet), Spur an puls_diagnose")
check("vol = _vp[\"vol\"]" in blk, "h3 korrigierte Lots ersetzen vol vor dem Tippen")
i_ber = src.find("sl_f9, tp_f9 = berechne_sl_tp(")
i_kl = src.find("sltp_mindestabstand(", i_ber)
i_tip = src.find('"F9-SL"', i_ber)
check(0 < i_ber < i_kl < i_tip, "h4 Stops-Klemme nach berechne_sl_tp und vor dem Tippen der F9-Felder")
msrc = inspect.getsource(ob.main)
check('res["vorpruefung"] = dict(_VORPRUEF_LAUF)' in msrc, "h5 Ergebnis trägt Plan-/Ist-Lots und Korrekturen")
zsrc = inspect.getsource(ob._order_api_zustand)
check("trade_stops_level" in zsrc and "volume_step" in zsrc, "h6 _order_api_zustand liest Raster und Stops-Level")

print()
print("FEHLER: " + ", ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
