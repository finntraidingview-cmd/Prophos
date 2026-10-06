#!/usr/bin/env python3
"""Selbsttest Einsatz-Ausgleich + Startfenster-Ende des Auto-Planers (app.py, Finn 07.10.2026: „einfach, keine 1.000 Regeln").

Aufruf:  python3 tools/selftest_auto_klumpen.py
Nutzt den Lader und die nachgebaute DB aus selftest_auto_delta.py. Geprüft: Einsatz = Kontowert × riskierte $ ÷ Polster
(FundedNext 500 € / 10.000 $ Polster, SL 2.500 $ → 125 €; Tradeify ohne SL = ganzer Wert); 2 × 720 € short hintereinander =
Klumpen (|Netto| 1.440 €, Große-Folge 1); der Optimierer gleicht in € aus (€/Pkt zählt nicht mehr), trennt eine aufgeteilte
Tranche mit Gegengewicht dazwischen, nichts wird hart ausgelassen; Bot greift über dem €-Band; Schwelle „groß" = 300 € bzw.
oberes Viertel; kein Start nach 16:30 dt (auch nicht das letzte Konto einer Tranche), kein Rückfall auf 20:00."""
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
    EK = {"basis": 0.0, "brutto": 0.0, "fest_ev": [], "gross_ab": 300.0}

    # ── 0 KPI: Finns Beispiele
    g = a["ap_trade_gewicht"]({"satz": 500 / 10000, "wert": 500, "polster": 10000}, {}, 6000, 2500)
    check(g["verlust_eur"] == 125, f"FundedNext 100k frisch: Wert 500 €, SL 2.500 $ von 10.000 Polster → 125 € Einsatz ({g})")
    g = a["ap_trade_gewicht"]({"satz": 0.16, "wert": 700, "polster": 4500}, {}, 3500, None)
    check(g["verlust_eur"] == 700, "Tradeify letzter Trade ohne SL → ganzer Wert 700 € Einsatz")

    # ── 1 Lage: 2 × 720 € short hintereinander
    el = lage(0, [(600, -720), (610, -720)], 300)
    check(el["netto_eur_max_abs"] == 1440 and el["gross_folge"] == 1, f"2 × 720 € short = 1.440 €, Große-Folge 1 ({el})")
    el = lage(0, [(600, -720), (615, 720), (640, -720), (650, 720)], 300)
    check(el["netto_eur_max_abs"] == 720 and el["gross_folge"] == 0, f"getrennt mit Gegengewicht: max 720 €, keine Folge ({el})")
    el = lage(0, [(600, -720), (600, -500)], 300)
    check(el["gross_folge"] == 1, "zwei große gleicher Richtung in derselben Minute = Folge")
    check(a["ap_gross_ab"]([100, 120, 125, 150, 180, 200, 210, 250], 300) == 200, "Schwelle groß = oberes Viertel (200 €), wenn unter 300")
    check(a["ap_gross_ab"]([100, 700, 720, 800, 900], 300) == 300, "Schwelle groß höchstens 300 €")
    check(a["ap_gross_ab"]([700, 720], 300) == 300, "unter 4 Trades: 300 €")

    # ── 2 Optimierer gleicht in € aus, €/Pkt zählt nicht
    tr = {"A|tradeify": T(None, "A", "tradeify", 600, 3.0, 720), "B|fundednext": T(None, "B", "fundednext", 640, 9.0, 125),
          "C|apex": T(None, "C", "apex", 660, 0.5, 600)}
    r, _m, w = a["ap_richtungen_delta"](tr, 0, 0, random.Random(1), 25, einsatz=EK, mit_wert=True)
    check(r["A|tradeify"] != r["C|apex"], f"Tradeify 720 € und Apex 600 € gegenläufig — nach €, nicht nach €/Pkt ({r}, {w})")
    tr = {"A|tradeify#1": T(None, "A", "tradeify", 600, 3.0, 720, "A|tradeify"),
          "A|tradeify#2": T(None, "A", "tradeify", 660, 3.0, 720, "A|tradeify"),
          "B|apex": T(None, "B", "apex", 610, 2.0, 700), "C|fundednext": T(None, "C", "fundednext", 670, 2.0, 700)}
    for s in range(4):
        r, _m, w = a["ap_richtungen_delta"](tr, 0, 0, random.Random(s), 25, einsatz=EK, mit_wert=True)
        check(r["A|tradeify#1"] == r["A|tradeify#2"] and r["B|apex"] != r["A|tradeify#1"] and r["C|fundednext"] != r["A|tradeify#1"]
              and w[2] == 0, f"aufgeteilte Tranche (seed {s}): beide Tradeify gleich gerichtet, Gegengewicht dazwischen")
    tr = {"A|tradeify#1": T("sell", "A", "tradeify", 600, 3.0, 720, "A|tradeify"),
          "A|tradeify#2": T(None, "A", "tradeify", 660, 3.0, 720, "A|tradeify")}
    r, _m = a["ap_richtungen_delta"](tr, 0, 0, random.Random(2), 25, einsatz=EK)
    check(r == {"A|tradeify#1": "sell", "A|tradeify#2": "sell"}, "Richtungsschutz: fester Teil legt die ganze Gruppe fest (nie Ablehnung)")
    tr = {"A|tradeify": T(None, "A", "tradeify", 600, 3.0, 300), "B|tradeify": T(None, "B", "tradeify", 603, 3.0, 300),
          "C|apex": T(None, "C", "apex", 700, 3.0, 300), "D|apex": T(None, "D", "apex", 703, 3.0, 300)}
    r, _m, w = a["ap_richtungen_delta"](tr, 0, 0, random.Random(3), 25, einsatz=dict(EK, gross_ab=1000), mit_wert=True)
    check(r["A|tradeify"] == r["B|tradeify"] and r["C|apex"] == r["D|apex"] and w[0] == 0,
          "Malus stark: gleiche Firma nicht gegenläufig < 10 min, auch wenn das Netto dann größer ist")

    # ── 2b Laufzeit (Master 07.10.2026: „frühe Starts gemischt long/short, kein Block aus 4 Shorts")
    el = lage(419, [(102, -49), (103, -30), (317, -163), (431, -657), (694, 271), (706, 164)], 300)
    check(el["netto_eur_max_abs"] == 480, f"Live-Plan 07.10. kumuliert bis Tagesende: max |Netto| 480 € — sah ausgeglichen aus ({el})")
    el = lage(419, [(102, -49), (103, -30), (317, -163), (431, -657), (694, 271), (706, 164)], 300, laufzeit_min=180)
    check(el["netto_eur_max_abs"] == 820, f"mit Laufzeit 180 min: Tradeify −657 € um 07:11 ohne Gegengewicht = −820 € ({el})")
    tr = {f"S{i}": T(None, f"U{i}", f"f{i}", 60 + 120 * i, 1.0, e) for i, e in enumerate([49, 30, 163, 657, 271, 164, 124, 391])}
    r, _m, w = a["ap_richtungen_delta"](tr, 0, 0, random.Random(7), 25, einsatz=dict(EK, laufzeit=180), mit_wert=True)
    morgens = [r[k] for k in sorted(tr, key=lambda k: tr[k]["start"])][:4]
    check(len(set(morgens)) == 2, f"Laufzeit-Modell: die ersten 4 Starts gemischt ({morgens})")
    v = a["ap_verlauf"](100, 100, [(60, 50), (90, -50)], 25, laufzeit_min=60)
    check([(x["min"], x["netto_delta"]) for x in v["verlauf"]] == [(0, 100.0), (60, 50.0), (90, 0.0), (120, -50.0), (150, 0.0)],
          f"ap_verlauf mit Laufzeit: Basis endet nach 60, Trades nach 60 min ({[(x['min'], x['netto_delta']) for x in v['verlauf']]})")

    # ── 2c Geblasen über den letzten Trade
    regel_t = {"groessen": [150000], "dd_usd": 4500}
    fin = lambda pnl, ende: {"ended_at": ende, "final": {"today_pnl": pnl, "grund": "demo_liq"}}
    gb = a["ap_letzter_trade_geblasen"](regel_t, 149046, [fin(3500, "2026-10-02T14:50"), fin(-4521.52, "2026-10-05T17:44")])
    check(gb and "geblasen" in gb, f"Tradeify letzter Trade −4.522 $ ≥ 95 % von 4.500 → {gb}")
    gb = a["ap_letzter_trade_geblasen"](regel_t, 153000, [fin(-4521.52, "2026-10-02T14:50"), fin(3500, "2026-10-05T17:44")])
    check(gb is None, "danach ein Gewinn → nicht geblasen")
    gb = a["ap_letzter_trade_geblasen"]({"groessen": [150000], "dd_usd": 4000}, 148097, [fin(-1884.3, "2026-10-06T17:00")])
    check(gb is None, "Apex Tagesstopp −1.884 $ (Ende „liq“) → nicht geblasen")
    gb = a["ap_letzter_trade_geblasen"]({"groessen": [100000], "dd_pct": 10}, 90400, [{"ended_at": "x", "final": {"master_pl_schaetzung": -9600}}])
    check(gb and "geblasen" in gb, "CFD 100k: −9.600 $ ≥ 95 % von 10 % → geblasen?")

    # ── 3 Bot greift über dem €-Band
    plaene = [{"plan_id": "p1", "user_id": "A", "firma": "tradeify", "richtung": "sell", "start_min": 620, "delta_abs": 3.0,
               "aenderbar": True, "einsatz_abs": 720},
              {"plan_id": "p2", "user_id": "B", "firma": "apex", "richtung": "sell", "start_min": 640, "delta_abs": 3.0,
               "aenderbar": True, "einsatz_abs": 600}]
    erg = a["ap_umplanen"](plaene, 0.0, 0.0, 600, sd.ZEITEN, 25, random.Random(4),
                           einsatz=dict(EK, basis=-500.0, brutto=500.0))
    check(erg["aenderungen"] and erg["nachher"]["ueber_band"] < erg["vorher"]["ueber_band"] and "Netto-Einsatz" in (erg["ausloeser"] or ""),
          f"Bot: laufend −500 € short + 2 Shorts geplant → dreht/zieht vor ({erg['ausloeser']})")
    ruhig = a["ap_umplanen"]([dict(plaene[0], richtung="buy")], 0.0, 0.0, 600, sd.ZEITEN, 25, random.Random(4),
                             einsatz=dict(EK, basis=-700.0, brutto=700.0))
    check(ruhig["aenderungen"] == [], "Bot: Gegengewicht schon geplant → keine Änderung")

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

    # ── 5 Planer-Rauch-Lauf
    from zoneinfo import ZoneInfo
    jetzt = datetime.now(timezone.utc)
    tag = jetzt.astimezone(ZoneInfo("Europe/Berlin")) + timedelta(days=1)
    while tag.weekday() >= 5:
        tag += timedelta(days=1)
    reg, _g = sd.db_stubs(a, jetzt)
    erg = a["ap_planen"](tag.strftime("%Y-%m-%d"), trocken=True, seed=4711)
    e = erg.get("einsatz") or {}
    check(erg.get("ok") and "netto_eur_max_abs" in e and all("einsatz_eur" in g for g in erg["geplant"])
          and not any("Einsatz" in str(x.get("grund")) for x in erg["ausgelassen"]),
          f"Planer: Einsatz im Protokoll, nichts hart ausgelassen ({e})")
    aus = erg.get("ausgleich") or {}
    check(all(k in aus for k in ("netto_eur", "long_eur", "short_eur", "band_eur", "verlauf")) and all("netto_eur" in x for x in aus["verlauf"]),
          "Probelauf: netto_eur, long_eur, short_eur, band_eur, verlauf[].netto_eur")
    check(all(int(g["start"][:2]) * 60 + int(g["start"][3:]) < 16 * 60 + 30 for g in erg["geplant"]), "Planer: kein Start nach 16:30")

    print()
    if FEHLER:
        print(f"FEHLER: {len(FEHLER)}")
        sys.exit(1)
    print("ALLES OK")


if __name__ == "__main__":
    main()
