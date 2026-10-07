#!/usr/bin/env python3
"""Selbsttest ID-Mischung im Auto-Planer (app.py ap_id_misch + ap_richtungen_delta + ap_umplanen, 08.10.2026; Finn ~02:50 Dubai:
Chris 7 Pläne alle long, Aurel 2× short — „dass eine ID komplett long und eine andere komplett short ist, ist ein Mischmasch … bei 7
ist das zu viel. Nicht so hart.") — ohne Netz. Aufruf: python3 tools/selftest_auto_id_misch.py
Fälle: Chris 7 Pläne über 3 Firmen → 4/3 (keine Seite > 67 %) · 2 Pläne → keine Vorgabe · eine Firma → keine Vorgabe · globales Band
hält weiter (Band vor Mischung) · Bot dreht nie so, dass die ID-Mischung schlechter wird."""
import os
import random
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402


def main():
    a = sd.lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    M, R = a["ap_id_misch"], a["ap_richtungen_delta"]
    C, A = "chris", "aurel"
    # ── ap_id_misch direkt ──
    tr = {"c|fn": {"user": C, "firma": "fundednext", "n_plaene": 4}, "c|fp": {"user": C, "firma": "fundingpips", "n_plaene": 2},
          "c|ts": {"user": C, "firma": "topstep", "n_plaene": 1}, "a|apex": {"user": A, "firma": "apextrader", "n_plaene": 2}}
    st, je = M({"c|fn": "buy", "c|fp": "buy", "c|ts": "buy", "a|apex": "sell"}, tr)
    check(st == 33 and je[C]["long"] == 7 and je[C]["short"] == 0 and je[C]["regel"] is True, f"Chris 7/0 long → Strafe 33 (1,00 − 0,67) ({st}, {je[C]})")
    check(je[A]["regel"] is False and je[A]["short"] == 2, "Aurel 2 Pläne, eine Firma → keine Vorgabe (zählt nur)")
    st2, je2 = M({"c|fn": "buy", "c|fp": "sell", "c|ts": "sell", "a|apex": "sell"}, tr)
    check(st2 == 0 and je2[C]["long"] == 4 and je2[C]["short"] == 3, "Chris 4/3 → Strafe 0")
    st3, _ = M({"x|fn": "buy", "x|fp": "buy"}, {"x|fn": {"user": "x", "firma": "fundednext", "n_plaene": 2}, "x|fp": {"user": "x", "firma": "fundingpips", "n_plaene": 1}})
    check(st3 == 0, "3 Pläne über 2 Firmen → unter AP_ID_MISCH_AB, keine Vorgabe")
    st4, je4 = M({"y|fn": "buy", "y|fn#2": "buy"}, {"y|fn": {"user": "y", "firma": "fundednext", "n_plaene": 3}, "y|fn#2": {"user": "y", "firma": "fundednext", "n_plaene": 3}})
    check(st4 == 0 and je4["y"]["n"] == 6 and je4["y"]["regel"] is False, "6 Pläne, nur eine Firma → keine Vorgabe (Richtungsschutz je Firma bleibt)")
    check(M({}, {}) == (0, {}) and M({"k": "buy"}, {}) == (0, {}), "leer / Tranche ohne user → nichts")

    # ── ap_richtungen_delta: Chris-Fall — Band hält locker (50 %), Mischung entscheidet ──
    T = {"c|fn": {"fest": None, "user": C, "firma": "fundednext", "start": 60, "delta_abs": 2.0, "einsatz_abs": 800.0, "n_plaene": 4},
         "c|fp": {"fest": None, "user": C, "firma": "fundingpips", "start": 120, "delta_abs": 1.0, "einsatz_abs": 400.0, "n_plaene": 2},
         "c|ts": {"fest": None, "user": C, "firma": "topstep", "start": 180, "delta_abs": 1.0, "einsatz_abs": 200.0, "n_plaene": 1},
         "a|apex": {"fest": "sell", "user": A, "firma": "apextrader", "start": 240, "delta_abs": 4.0, "einsatz_abs": 1400.0, "n_plaene": 2}}
    z, _m, w = R(T, 0.0, 0.0, random.Random(7), 50.0, mit_wert=True)
    st_c, je_c = M(z, T)
    check(st_c == 0 and max(je_c[C]["long"], je_c[C]["short"]) == 4 and min(je_c[C]["long"], je_c[C]["short"]) == 3,
          f"Chris 7 Pläne/3 Firmen → 4/3 statt 7/0 (long {je_c[C]['long']}, short {je_c[C]['short']})")
    check(z["a|apex"] == "sell", "feste Tranche (Richtungsschutz) bleibt sell")
    check(len(w) == 5 and w[2] == 0, f"Wert-Tupel ohne Einsatz: (Band, Malus, ID-Mischung, |Netto|, Ende) — Mischung 0 ({w})")
    # mit Einsatz-Kontext: Tupel (Malus, Netto-Stufe, Mischung, Große-Folge, |Netto|, Ende)
    ek = {"basis": 0.0, "fest_ev": [], "gross_ab": 10000.0, "laufzeit": 180}
    z2, _m2, w2 = R(T, 0.0, 0.0, random.Random(7), 50.0, einsatz=ek, mit_wert=True)
    st_c2, je_c2 = M(z2, T)
    check(len(w2) == 6 and st_c2 == 0 and max(je_c2[C]["long"], je_c2[C]["short"]) == 4, f"mit Einsatz: Mischung an Stelle 3, Chris 4/3 ({w2}, {je_c2[C]})")
    # globales Band geht vor der Mischung: enges Band (5 %) — die gewählte Zuteilung hat die kleinste Band-Überschreitung aller 8 Zuteilungen
    V = a["ap_verlauf"]
    frei = ["c|fn", "c|fp", "c|ts"]
    def band_ueber(zz):
        ev = [(T[k]["start"], T[k]["delta_abs"] * (1 if zz[k] == "buy" else -1)) for k in T]
        v = V(0.0, 0.0, ev, 5.0)
        return round(max([abs(x["netto_delta"]) - x["band_delta"] for x in v["verlauf"]] + [0.0]), 1)
    alle = []
    for bits in range(8):
        zz = {"a|apex": "sell"}; zz.update({k: ("buy" if (bits >> i) & 1 else "sell") for i, k in enumerate(frei)})
        alle.append(band_ueber(zz))
    z3, _m3, w3 = R(T, 0.0, 0.0, random.Random(3), 5.0, mit_wert=True)
    check(abs(w3[0] - min(alle)) < 1e-9, f"enges Band: gewählte Zuteilung hat die kleinste Band-Überschreitung ({w3[0]} = min {min(alle)}) — Band steht vor der Mischung")

    # ── Bot: Drehung nur, wenn die ID-Mischung nicht schlechter wird ──
    U = a["ap_umplanen"]
    plaene = [{"plan_id": f"c{i}", "user_id": C, "user": "Chris", "firma": "fundednext", "richtung": "buy", "start_min": 600 + i, "delta_abs": 1.0, "einsatz_abs": 200.0, "aenderbar": True} for i in range(4)]
    plaene += [{"plan_id": "c5", "user_id": C, "user": "Chris", "firma": "fundingpips", "richtung": "sell", "start_min": 650, "delta_abs": 1.0, "einsatz_abs": 200.0, "aenderbar": True},
               {"plan_id": "c6", "user_id": C, "user": "Chris", "firma": "topstep", "richtung": "sell", "start_min": 700, "delta_abs": 1.0, "einsatz_abs": 200.0, "aenderbar": True},
               {"plan_id": "c7", "user_id": C, "user": "Chris", "firma": "ftmo", "richtung": "sell", "start_min": 720, "delta_abs": 1.0, "einsatz_abs": 200.0, "aenderbar": True}]
    zeiten = {"fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30", "abstand_id_min": 3}
    # Netto stark long (Basis +9) → Bot will drehen; drehen darf er fundednext (4 long → short: 4/3 → 3/4, Mischung gleich), nie die Shorts
    erg = U(plaene, 9.0, 9.0, 590, zeiten, 5.0, random.Random(1), einsatz={"basis": 1800.0, "brutto": 1800.0, "gross_ab": 10000.0, "laufzeit": 180})
    dreh = [x for x in erg["aenderungen"] if x["art"] == "richtung"]
    # Chris 4 long (fundednext) / 3 short: jede Drehung einer Tranche machte 7/0 bzw. 0/7 → Mischung schlechter → der Bot dreht NICHT
    check(dreh == [], f"Bot dreht keine Tranche, wenn die ID-Mischung dadurch schlechter würde ({[(x['firma'], x['von_richtung'], x['nach_richtung']) for x in dreh]})")
    # Chris 5 long (fundednext 3 + fundingpips 2) / 1 short (topstep), Netto zu long → Drehung von fundingpips verbessert die Mischung (3/3)
    pl2 = [{"plan_id": f"d{i}", "user_id": C, "user": "Chris", "firma": "fundednext", "richtung": "buy", "start_min": 600 + i, "delta_abs": 1.0, "einsatz_abs": 200.0, "aenderbar": True} for i in range(3)]
    pl2 += [{"plan_id": f"e{i}", "user_id": C, "user": "Chris", "firma": "fundingpips", "richtung": "buy", "start_min": 650 + i, "delta_abs": 1.0, "einsatz_abs": 200.0, "aenderbar": True} for i in range(2)]
    pl2 += [{"plan_id": "f1", "user_id": C, "user": "Chris", "firma": "topstep", "richtung": "sell", "start_min": 700, "delta_abs": 1.0, "einsatz_abs": 200.0, "aenderbar": True}]
    erg2 = U(pl2, 9.0, 9.0, 590, zeiten, 5.0, random.Random(1), einsatz={"basis": 1800.0, "brutto": 1800.0, "gross_ab": 10000.0, "laufzeit": 180})
    dreh2 = [x for x in erg2["aenderungen"] if x["art"] == "richtung"]
    # Netto steht vor der Mischung: der Bot nimmt die Drehung mit dem größeren Netto-Gewinn (fundednext, 3 Pläne → Chris 2/4 = 67 %, Strafe 0),
    # solange die Mischung dabei nicht schlechter wird — hier wird sie von 16 auf 0 besser
    check(dreh2 and all(x["nach_richtung"] == "sell" for x in dreh2) and erg2["nachher"]["id_misch"] == 0 and erg2["vorher"]["id_misch"] > 0,
          f"Bot dreht eine Long-Tranche von Chris → Mischung {erg2['vorher']['id_misch']} → {erg2['nachher']['id_misch']} ({[(x['firma'], x['von_richtung'], x['nach_richtung']) for x in dreh2]})")
    check("id_misch" in erg["vorher"] and "id_misch" in erg["nachher"], "Bot-Antwort trägt id_misch in vorher/nachher")
    print("\nID-MISCH:", "alles grün" if ok else "FEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
