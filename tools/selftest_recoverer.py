#!/usr/bin/env python3
"""Selbsttest Recoverer (app.py wd_zyklus_*, 02.11.2026) — rein rechnend, ohne Netz. Beispiele aus dem Konstrukt
(.claude/master/berichte/2026-11-01_apex-wd-konstrukt.md Abschnitt 7), Satz-Stützpunkt 0 = max(Satz aus Staffel, 400) laut Auftrag.

Aufruf:  python3 tools/selftest_recoverer.py"""
import os
import re
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
REGEL = {"stuetz": [{"v": 2000, "ziel": 750, "satz": 400}, {"v": 4000, "ziel": 1500, "satz": 300}],
         "firmen": ["apex", "apex100"], "ab_zyklus": 2, "bis": "2x_bester", "satz_normal": None, "kt": None, "aktiv": True}
VORPLAN = {"regeln": {"fu": {"apex": [370, 390], "apex100": [320, 340]},
                      "staffelFirma": {"apex": [{"von": 0, "eur": 50}, {"von": 4000, "eur": 100}, {"von": 10000, "eur": 175}]}}}
MIKE = {"id": "k1", "name": "150k PAAPEX 0001", "firm": "Apex", "wd_farm": True, "live_balance": 160029.26}
PAY = [{"requested_at": "2026-10-26", "status": "received"}]


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone}
    for name in ("def _wd_num(", "def wd_tsx_master_pl(", "def _wd_konto_groesse(", "def _wd_berlin_tag(", "def wd_plan_pnl(", "def wd_zyklus_stand(",
                 "def _wd_staffel_eur(", "def wd_zyklus_firma_key(", "def wd_zyklus_normal(", "def wd_zyklus_werte(", "def wd_zyklus_bis(", "def wd_zyklus_konto("):
        i = src.index(name)
        exec(src[i:src.find("\n\n\n", i)], ns)
    i = src.index("WD_ZYKLUS_VORGABE = {")
    exec(src[i:src.index("def _wd_berlin_tag(")], ns)
    return ns


def plan(tag, pnl, status="completed", **x):
    return dict({"status": status, "started_at": f"{tag}T10:00:00+00:00", "master_pl": pnl, "route": "tvv2"}, **x)


def main():
    ns = lade()
    f, stand = ns["wd_zyklus_konto"], ns["wd_zyklus_stand"]
    fehler = []

    def check(bed, text):
        print(("✓ " if bed else "✗ ") + text)
        if not bed:
            fehler.append(text)

    mike = [plan("2026-10-27", 374.88), plan("2026-10-28", 383.88), plan("2026-10-29", 388.38), plan("2026-10-30", -3998.16)]

    # Stand
    st = stand(mike, PAY)
    check(st["nr"] == 2 and st["start"] == "2026-10-26", "Zyklus-Nr = Anfragen + 1, Start = jüngste Anfrage")
    check(st["profit"] == -2851.02 and st["bester"] == 388.38 and st["verlust"] == 3998.16, "Mike: Profit −2.851,02, bester 388,38, Verlust 3.998,16")
    check(stand([plan("2026-10-26", 500)] + mike, PAY)["profit"] == -2851.02, "Trade am Anfrage-Tag zählt zum alten Zyklus")
    check(stand(mike + [plan("2026-10-30", 100, status="planned")], PAY)["profit"] == -2851.02, "nur completed/review zählen")
    check(stand(mike, PAY + [{"requested_at": "2026-10-29", "status": "storniert"}])["nr"] == 2, "stornierte Anfrage zählt nicht")
    zwei = stand([plan("2026-11-02", 100), plan("2026-11-02", -700)], PAY)
    check(zwei["tage"] == [{"tag": "2026-11-02", "pnl": -600.0}] and zwei["verlust"] == 600.0, "mehrere Trades am Tag werden je Tag summiert")
    check(ns["wd_plan_pnl"]({"tv": {"today_pnl_start": 100, "datum_start": "x"}, "fin": {"today_pnl": 300, "datum": "x"}}) == 200, "ohne master_pl: Endlesung − Start am selben Tag")
    check(ns["wd_plan_pnl"]({"status": "completed"}) is None, "ohne Wert → None, kein 0")

    # Beispiel 5 (Mike) inkl. „bis erfüllt“
    z = f(MIKE, REGEL, VORPLAN, mike, PAY)
    check(z["aktiv"] and z["ziel"] == 1499, f"Mike −3.998 → Ziel 1.499 $ (ist {z['ziel']})")
    check(abs(z["hedge_eur"] - 450) < 1, f"Mike → Hedge ~450 € (ist {z['hedge_eur']})")
    check(z["tage_geschaetzt"] == 4, f"Mike → 4 Tage bis erfüllt (ist {z['tage_geschaetzt']})")
    check(z["rest_bis_erfuellt"] == 5996, f"Mike → noch 5.996 $ (ist {z['rest_bis_erfuellt']})")

    # Finns Satz: 4 × 400, dann −400 → aus
    s = f(MIKE, REGEL, VORPLAN, [plan("2026-11-0%d" % i, 400) for i in (2, 3, 4, 5)] + [plan("2026-11-06", -400)], PAY)
    check(not s["aktiv"] and s["grund_code"] == "erfuellt" and s["ziel"] is None, "4 × 400, dann −400: Profit 1.200 ≥ 800 → Regel aus")

    # Weitere Zeilen der Tabelle
    z1 = f(MIKE, REGEL, VORPLAN, [plan("2026-10-20", 380), plan("2026-10-21", -1500)], [])
    check(not z1["aktiv"] and z1["grund_code"] == "zyklus_1" and z1["nr"] == 1, "Zeile 1: Zyklus 1 → aus")
    z2 = f(dict(MIKE, live_balance=164027), REGEL, VORPLAN, mike[:3], PAY)
    check(not z2["aktiv"] and z2["grund_code"] == "kein_verlust", "Zeile 2: kein Verlusttag → aus")
    check(z2["staffel_eur"] == 175 and z2["plus"] == 14027, "Zeile 2: 150k → Plus über der Größe, Staffel 175 €")
    z3 = f(dict(MIKE, live_balance=157000), REGEL, VORPLAN, [plan("2026-10-27", 380), plan("2026-10-28", -1000)], PAY)   # Plus 7.000 → Staffel 100 €
    check(z3["ziel"] == 565 and z3["satz"] == 400, f"Zeile 3 (−1.000): Ziel 565 $, Satz 400 (Stützpunkt 0 = max(Staffel, 400)) — ist {z3['ziel']}/{z3['satz']}")
    z4 = f(MIKE, REGEL, VORPLAN, [plan("2026-10-27", 380), plan("2026-10-28", -2000)], PAY)
    check(z4["ziel"] == 750 and z4["hedge_eur"] == 300 and z4["tage_geschaetzt"] == 5, "Zeile 4 (−2.000): 750 $ / 300 €, 5 Tage")
    z5b = f(MIKE, REGEL, VORPLAN, [plan("2026-10-27", 380), plan("2026-10-28", -6000)], PAY)
    check(z5b["ziel"] == 1500 and z5b["hedge_eur"] == 450, "Zeile 5b: über −4.000 Deckel 1.500 $ / 450 €")
    z6 = f(MIKE, REGEL, VORPLAN, [plan("2026-10-27", 380), plan("2026-10-28", -600), plan("2026-10-29", -600)], PAY)
    check(z6["verlust"] == 600 and z6["ziel"] == 491, "Zeile 6: zählt der Einzeltag (600), nicht der Netto-Verlust → 491 $")
    z7 = f(MIKE, REGEL, VORPLAN, mike + [plan("2026-11-0%d" % i, 1499) for i in (2, 3, 4, 5)], PAY)
    check(not z7["aktiv"] and z7["grund_code"] == "erfuellt", "Zeile 7: nach 4 × 1.499 erfüllt → aus")

    # Satz nie unter Staffel, fester Satz als Parameter
    hoch = f(dict(MIKE, live_balance=164100), REGEL, VORPLAN, [plan("2026-10-27", 380), plan("2026-10-28", -1000)], PAY)
    check(hoch["satz"] > 400, f"Plus ≥ 10.000: Stützpunkt 0 = Satz_normal 461, sinkt nie unter Staffel (ist {hoch['satz']})")
    fest = f(MIKE, dict(REGEL, satz_normal=450), VORPLAN, [plan("2026-10-27", 380), plan("2026-10-28", -1000)], PAY)
    check(fest["satz"] == 425, f"satz_normal = 450 setzt Stützpunkt 0 fest (−1.000: 425, ist {fest['satz']})")

    # Schalter und Bedingungen
    aus = f(dict(MIKE, wd_zyklus_regel="aus"), REGEL, VORPLAN, mike, PAY)
    check(not aus["aktiv"] and aus["grund_code"] == "schalter_aus", "Schalter aus → nie")
    an1 = f(dict(MIKE, wd_zyklus_regel="an"), REGEL, VORPLAN, [plan("2026-10-20", 380)], [])
    check(an1["aktiv"] and an1["ziel"] is None, "Schalter an ohne Verlusttag: aktiv, aber Normalwerte")
    an2 = f(dict(MIKE, wd_zyklus_regel="an", wd_farm=False), REGEL, VORPLAN, mike, PAY)
    check(not an2["aktiv"] and an2["grund_code"] == "kein_farm", "Schalter an ohne wd_farm: aus")
    check(not f(dict(MIKE, wd_farm=False), REGEL, VORPLAN, mike, PAY)["aktiv"], "ohne wd_farm → aus")
    check(not f(MIKE, dict(REGEL, aktiv=False), VORPLAN, mike, PAY)["aktiv"], "Hauptschalter aus → aus")
    ohne = f(MIKE, None, VORPLAN, mike, PAY)
    check(not ohne["aktiv"] and ohne["grund_code"] == "keine_regel" and ohne["ziel"] is None, "Spalte zyklus_regel fehlt (SQL nicht drin) → aus")
    check(ns["wd_zyklus_firma_key"]({"firm": "Tradeify", "name": "150k"}) is None, "andere Firma: kein Schlüssel, bekommt kein Feld")
    check(ns["wd_zyklus_firma_key"]({"firm": "Apex", "name": "100k x"}) == "apex100", "100k = apex100")
    h100 = f({"id": "k", "name": "100k x", "firm": "Apex", "wd_farm": True, "live_balance": 100000}, REGEL, VORPLAN, [plan("2026-10-27", 330), plan("2026-10-28", -1000)], PAY)
    check(h100["ziel_normal"] == 330 and h100["ziel"] == 540, f"apex100: Normal 330, −1.000 → 540 (ist {h100['ziel']})")

    print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
