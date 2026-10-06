#!/usr/bin/env python3
"""Selbsttest Klumpen-Regel + Startfenster-Ende des Auto-Planers (app.py, Finn 07.10.2026) — ohne Netz.

Aufruf:  python3 tools/selftest_auto_klumpen.py
Nutzt den Lader und die nachgebaute DB aus selftest_auto_delta.py. Geprüft: 2 × 720 € short hintereinander = Klumpen
(1.440 € > max 800 €, kein Gegenstück); der Optimierer paart sie (frei) bzw. trennt eine aufgeteilte Tranche (gleiche ID,
gleiche Richtung) mit Gegenstücken dazwischen; Reihenfolge max_netto → Band; laufende Trades über der Grenze machen neue
Trades nicht unmöglich; Bot greift bei Klumpen; Planer lässt lieber aus (Grund im Protokoll); kein Start nach 16:30 dt (auch
nicht das letzte Konto einer Tranche), kein Rückfall auf 20:00."""
import importlib.util
import os
import random
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("sd", os.path.join(HIER, "selftest_auto_delta.py"))
sd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sd)

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def T(fest, user, firma, start, d, e, gruppe=None):
    return {"fest": fest, "user": user, "firma": firma, "start": start, "delta_abs": d, "einsatz_abs": e, "gruppe": gruppe}


def main():
    a = sd.lade()
    lage = a["ap_einsatz_lage"]
    EK = {"basis": 0.0, "fest_ev": [], "max_netto": 800.0, "paar_ab": 300.0, "paar_extra": []}

    # ── 1 Lage: 2 × 720 € short hintereinander
    el = lage(0, [(600, -720), (610, -720)], 800, 300)
    check(el["ueber_eur"] == 640 and el["netto_eur_max_abs"] == 1440 and el["paar_fehlt"] == 2,
          f"2 × 720 € short = 1.440 € → 640 € über max, 2 ohne Gegenstück ({el})")
    el = lage(0, [(600, -720), (615, 720), (640, -720), (650, 720)], 800, 300)
    check(el["ueber_eur"] == 0 and el["paar_fehlt"] == 0, f"getrennt + gepaart: Netto ≤ 800, jedes Gegenstück ±30 min ({el})")
    el = lage(0, [(600, -720), (700, 500)], 800, 300)
    check(el["paar_fehlt"] == 2, "Gegenstück 100 min später zählt nicht (±30 min)")
    el = lage(0, [(600, -720)], 800, 300, paar_extra=[(590, 1)])
    check(el["paar_fehlt"] == 0, "heute schon gestarteter Long 10 min davor ist Gegenstück")
    el = lage(-975, [(600, 387)], 800, None)
    check(el["ueber_eur"] == 0, "laufend schon −975 €: ein ausgleichender Long ist erlaubt (Grenze = Betrag der Laufenden)")
    el = lage(-975, [(600, -100)], 800, None)
    check(el["ueber_eur"] == 100, "laufend −975 €: ein weiterer Short macht es schlimmer → 100 € über")

    # ── 2 Optimierer paart / trennt
    tr = {"A|tradeify": T(None, "A", "tradeify", 600, 3.0, 720), "B|tradeify": T(None, "B", "tradeify", 625, 3.0, 720)}
    r, _m, w = a["ap_richtungen_delta"](tr, 0, 0, random.Random(1), 25, einsatz=EK, mit_wert=True)
    check(r["A|tradeify"] != r["B|tradeify"] and w[0] == 0 and w[1] == 0, f"2 × 720 € frei → gepaart (gegenläufig) {r}")
    tr = {"A|tradeify#1": T(None, "A", "tradeify", 600, 3.0, 720, "A|tradeify"),
          "A|tradeify#2": T(None, "A", "tradeify", 660, 3.0, 720, "A|tradeify"),
          "B|apex": T(None, "B", "apex", 610, 2.0, 700), "C|fundednext": T(None, "C", "fundednext", 670, 2.0, 700)}
    for s in range(4):
        r, _m, w = a["ap_richtungen_delta"](tr, 0, 0, random.Random(s), 25, einsatz=EK, mit_wert=True)
        check(r["A|tradeify#1"] == r["A|tradeify#2"] and r["B|apex"] != r["A|tradeify#1"] and r["C|fundednext"] != r["A|tradeify#1"]
              and w[0] == 0 and w[1] == 0, f"aufgeteilte Tranche (seed {s}): beide Tradeify gleich gerichtet, je ein Gegenstück dazwischen")
    tr = {"A|tradeify#1": T("sell", "A", "tradeify", 600, 3.0, 720, "A|tradeify"),
          "A|tradeify#2": T(None, "A", "tradeify", 660, 3.0, 720, "A|tradeify")}
    r, _m = a["ap_richtungen_delta"](tr, 0, 0, random.Random(2), 25, einsatz=EK)
    check(r == {"A|tradeify#1": "sell", "A|tradeify#2": "sell"}, "Richtungsschutz: fester Teil legt die ganze Gruppe fest")
    tr = {"A|x": T(None, "A", "x", 600, 1.0, 700), "B|y": T(None, "B", "y", 700, 5.0, 700)}
    r, _m, w = a["ap_richtungen_delta"](tr, 0, 0, random.Random(3), 100, einsatz=EK, mit_wert=True)
    check(r["A|x"] != r["B|y"] and w[0] == 0, "max_netto_eur vor Delta-Band")

    # ── 3 Bot greift bei Klumpen
    plaene = [{"plan_id": "p1", "user_id": "A", "firma": "tradeify", "richtung": "sell", "start_min": 700, "delta_abs": 3.0,
               "aenderbar": True, "einsatz_abs": 720},
              {"plan_id": "p2", "user_id": "B", "firma": "tradeify", "richtung": "sell", "start_min": 760, "delta_abs": 3.0,
               "aenderbar": True, "einsatz_abs": 720}]
    erg = a["ap_umplanen"](plaene, 0.0, 0.0, 600, sd.ZEITEN, 100, random.Random(4), einsatz=EK)
    check(erg["aenderungen"] and erg["vorher"]["ueber_eur"] == 640 and erg["nachher"]["ueber_eur"] == 0
          and "Netto-Einsatz" in (erg["ausloeser"] or ""), f"Bot: Klumpen erkannt und aufgelöst ({erg['ausloeser']})")
    ohne = a["ap_umplanen"](plaene, 0.0, 0.0, 600, sd.ZEITEN, 100, random.Random(4))
    check(ohne["aenderungen"] == [], "Bot ohne Einsatz-Kontext wie bisher (Band 100 % hält)")

    # ── 4 Startfenster bis 16:30
    z = {"fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "abstand_id_min": 3}
    trs = [{"key": f"k{i}", "user": f"U{i}", "firma": "f", "dauer_min": 2 + (i % 3) * 2} for i in range(40)]
    m = a["ap_zeiten_verteilen"](trs, z, random.Random(5))
    letzter = max(m[t["key"]] + t["dauer_min"] - 2 for t in trs)
    check(len(m) == 40 and letzter < 16 * 60 + 30, f"40 Tranchen, letzter Start (auch letztes Konto) vor 16:30 ({letzter:.0f} min)")
    alt = {"fenster": [["00:00", "14:30", 40], ["14:30", "17:30", 40], ["17:30", "19:30", 20]], "abstand_id_min": 3}
    m = a["ap_zeiten_verteilen"](trs, alt, random.Random(5))
    check(max(m.values()) < 16 * 60 + 30, "alte Fenster bis 19:30 → per start_bis (Standard 16:30) gekappt")
    m = a["ap_zeiten_verteilen"](trs[:3], z, random.Random(5), frueheste_min=17 * 60)
    check(m == {}, "nach 16:30 kein Rückfall auf 20:00 — keine Startzeit mehr")
    check(a["ap_fenster_von"](alt, 17 * 60) is None and a["ap_fenster_von"](alt, 15 * 60) == (870, 990), "Bot-Fenster gekappt auf 16:30")
    _x, f = a["ap_eingriff_pruefen"]("p1", "start", [dict(plaene[0], user="Eins")], 600, alt, neu_start_min=17 * 60)
    check(f and "außerhalb" in f, f"Eingriff von Hand nach 16:30 → 400: {f}")

    # ── 5 Planer-Rauch-Lauf: max_netto klein → lieber auslassen, Grund im Protokoll
    from zoneinfo import ZoneInfo
    jetzt = datetime.now(timezone.utc)
    tag = jetzt.astimezone(ZoneInfo("Europe/Berlin")) + timedelta(days=1)
    while tag.weekday() >= 5:
        tag += timedelta(days=1)
    reg, _g = sd.db_stubs(a, jetzt)
    erg = a["ap_planen"](tag.strftime("%Y-%m-%d"), trocken=True, seed=4711)
    e = erg.get("einsatz") or {}
    check(erg.get("ok") and e.get("ueber_eur") == 0 and all("einsatz_eur" in g for g in erg["geplant"]),
          f"Planer: Einsatz-Lage im Protokoll, nichts über der Grenze ({e})")
    # ohne laufende Trades (Basis 0), sonst wäre die Grenze deren Betrag (975 €)
    sb_all = a["_sb_all"]
    a["_sb_all"] = lambda t, p: [x for x in sb_all(t, p) if not (t == "trade_plans" and x.get("status") == "open")]
    reg["regeln"]["ausgleich"]["max_netto_eur"] = 50
    erg = a["ap_planen"](tag.strftime("%Y-%m-%d"), trocken=True, seed=4711)
    a["_sb_all"] = sb_all
    e = erg.get("einsatz") or {}
    raus = [x for x in erg["ausgelassen"] if str(x.get("grund", "")).startswith("Einsatz-Klumpen")]
    check(raus and e.get("ueber_eur") == 0, f"max 50 € → {len(raus)} Trade(s) ausgelassen mit Grund, Rest hält die Grenze")
    check(all(int(g["start"][:2]) * 60 + int(g["start"][3:]) < 16 * 60 + 30 for g in erg["geplant"]), "Planer: kein Start nach 16:30")

    print()
    if FEHLER:
        print(f"FEHLER: {len(FEHLER)}")
        sys.exit(1)
    print("ALLES OK")


if __name__ == "__main__":
    main()
