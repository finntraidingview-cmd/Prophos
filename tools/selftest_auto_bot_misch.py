#!/usr/bin/env python3
"""Selbsttest: Ausgleichs-Bot stellt die ID-Mischung auch ohne Band-Anlass her (app.py ap_umplanen, 08.10.2026; Finn: „warum ist bei
Chris immer noch alles long?" — 7 Pläne vor .1220 angelegt, Bot drehte nur bei Band-Überschreitung). Rein rechnend, ohne Netz.
Aufruf: python3 tools/selftest_auto_bot_misch.py"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest_auto_delta as sd  # noqa: E402

C, A = "u-chris", "u-andere"
ZEITEN = {"fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30", "abstand_id_min": 3}
EINSATZ = {"basis": 0.0, "brutto": 2000.0, "gross_ab": 100000.0, "laufzeit": 180}


def plan(pid, uid, firma, richtung, start, **kw):
    p = {"plan_id": pid, "user_id": uid, "user": "Chris" if uid == C else "Andere", "firma": firma, "firma_name": firma.capitalize(),
         "richtung": richtung, "start_min": start, "delta_abs": 1.0, "einsatz_abs": 100.0, "aenderbar": True, "auto_plan": True,
         "bestaetigt": False}
    p.update(kw)
    return p


def chris(**fp):
    """Chris 6/1: FundedNext 4× long, FundingPips 2× long, Topstep 1× short (Live-Befund 08.10.2026). Dazu eine andere ID mit
    5× short bei einer Firma (keine Mischungs-Regel), damit das Netto ausgeglichen ist und das Band hält."""
    pl = [plan(f"fn{i}", C, "fundednext", "buy", 600 + i * 4) for i in range(4)]
    pl += [plan(f"fp{i}", C, "fundingpips", "buy", 700 + i * 4, **fp) for i in range(2)]
    pl += [plan("ts1", C, "topstep", "sell", 760)]
    pl += [plan(f"x{i}", A, "apex", "sell", 605 + i * 4) for i in range(5)]
    return pl


def main():
    a = sd.lade()
    U = a["ap_umplanen"]
    ok = True

    def check(bed, text):
        nonlocal ok
        ok = ok and bool(bed)
        print(("✓ " if bed else "✗ ") + text)

    def lauf(pl, band=100.0, zuletzt=None, id_fest=None):
        erg = U(pl, 0.0, 0.0, 300, ZEITEN, band, random.Random(1), einsatz=EINSATZ, zuletzt=zuletzt, id_fest=id_fest)
        # nur Drehungen: die Verteilung (08.10.2026, Startzeiten dichter Pläne derselben ID × Firma) prüft selftest_auto_verteilen
        erg["aenderungen"] = [x for x in erg["aenderungen"] if x.get("art") == "richtung"]
        return erg

    def gedreht(erg):
        return sorted((x["firma"], x["plan_id"], x["nach_richtung"]) for x in erg["aenderungen"])

    # 1) Chris 6/1, Band hält → genau eine Drehung: die kleinere Long-Tranche FundingPips → short = 4/3
    erg = lauf(chris())
    d = gedreht(erg)
    check(erg["vorher"]["ueber_band"] <= erg["daempfung"]["hysterese"], f"Ausgangslage: Band hält (über Band {erg['vorher']['ueber_band']} €)")
    check(d == [("fundingpips", "fp0", "sell"), ("fundingpips", "fp1", "sell")],
          f"Chris 6/1 → genau eine Drehung, FundingPips 2× → short ({d})")
    check(erg["vorher"]["id_misch"] > 0 and erg["nachher"]["id_misch"] == 0, f"Mischung {erg['vorher']['id_misch']} → {erg['nachher']['id_misch']} (4/3)")
    check(erg["aenderungen"] and all(x["grund"].startswith("ID-Mischung: ") and "6/1 → 4/3" in x["grund"] for x in erg["aenderungen"]),
          f"Protokoll-Grund „ID-Mischung …“ mit 6/1 → 4/3 ({erg['aenderungen'][0]['grund'] if erg['aenderungen'] else '—'})")
    check(str(erg["ausloeser"]).startswith("ID-Mischung"), f"Auslöser ohne Band-Anlass = ID-Mischung ({erg['ausloeser']})")

    # 2) danach ist Ruhe: zweiter Lauf auf dem neuen Stand dreht nichts mehr
    nach = {x["plan_id"]: x["nach_richtung"] for x in erg["aenderungen"]}
    pl2 = [dict(p, richtung=nach.get(p["plan_id"], p["richtung"])) for p in chris()]
    check(erg["aenderungen"] and gedreht(lauf(pl2)) == [], "zweiter Lauf auf 4/3 → keine Drehung")

    # 3) BESTÄTIGT (seit 08.10.2026, Finn: „Dass bei Chris 7 Trades long gehen, finde ich nicht geil" — alle bestätigt): gedreht, wenn der
    #    früheste Plan der ID × Firma ≥ AP_MISCH_BESTAETIGT_AB_MIN entfernt ist; die ganze ID × Firma, Grund „ID-Mischung (bestätigt)"
    e3 = lauf(chris(bestaetigt=True))
    check(gedreht(e3) == [("fundingpips", "fp0", "sell"), ("fundingpips", "fp1", "sell")],
          f"FundingPips 2× bestätigt, Start in ≥ 30 min → beide short, 6/1 → 4/3 ({gedreht(e3)})")
    check(e3["aenderungen"] and all(x["grund"].startswith("ID-Mischung (bestätigt): ") for x in e3["aenderungen"]),
          f"Protokoll-Grund „ID-Mischung (bestätigt): …“ ({e3['aenderungen'][0]['grund'] if e3['aenderungen'] else '—'})")
    nah = [dict(p, start_min=310 + i * 4) if p["firma"] == "fundingpips" else p for i, p in enumerate(chris(bestaetigt=True))]
    e3n = lauf(nah)
    check(not any(x["firma"] == "fundingpips" for x in e3n["aenderungen"]), f"bestätigt, aber Start in < 30 min → nicht gedreht ({gedreht(e3n)})")
    check(len({x["firma"] for x in e3n["aenderungen"]}) <= 1, f"höchstens EINE Mischungs-Drehung je Lauf ({gedreht(e3n)})")
    e3b = lauf(chris(aenderbar=False, fest_durch="schon gestartet"))
    check(not any(x["firma"] == "fundingpips" for x in e3b["aenderungen"]), f"FundingPips fest (gestartet) → nie gedreht ({gedreht(e3b)})")
    pl3 = [dict(p, bestaetigt=True) if p["firma"] in ("fundednext", "fundingpips") else p for p in chris()]
    check(len({x["firma"] for x in lauf(pl3)["aenderungen"]}) == 1, "alle Long-Tranchen bestätigt → genau EINE ID × Firma gedreht (die kleinste)")
    teil = [dict(p, bestaetigt=True, hand_werte=True, aenderbar=(p["plan_id"] != "fp1"), fest_durch=(None if p["plan_id"] != "fp1" else "Werte von Hand geändert"))
            if p["firma"] == "fundingpips" else p for p in chris()]
    check(not any(x["firma"] == "fundingpips" for x in lauf(teil)["aenderungen"]),
          "ein Plan der ID × Firma mit Werten von Hand → die ganze ID × Firma bleibt (nie halb gedreht)")
    # verteilt (seit dem Verteilen 08.10.2026 liegen die Pläne einer ID × Firma ≥ 60 min auseinander = Teil-Tranchen, die die alte
    # Mischung nie drehte — darum hing Chris live): die ganze ID × Firma dreht trotzdem gemeinsam
    vt = [dict(p, start_min=700 + i * 75, bestaetigt=True) if p["firma"] == "fundingpips" else p for i, p in enumerate(chris())]
    vt = [dict(p, start_min=700 + (0 if p["plan_id"] == "fp0" else 80)) if p["firma"] == "fundingpips" else p for p in vt]
    ev = lauf(vt)
    check(gedreht(ev) == [("fundingpips", "fp0", "sell"), ("fundingpips", "fp1", "sell")],
          f"verteilte ID × Firma (80 min auseinander, bestätigt) → beide gemeinsam short ({gedreht(ev)})")
    pl3h = [dict(p, auto_plan=False) if p["firma"] == "fundingpips" else p for p in chris()]
    check(not any(x["firma"] == "fundingpips" for x in lauf(pl3h)["aenderungen"]), "Handplan-Tranche → nie gedreht")
    e3r = lauf(chris(), id_fest={f"{C}|fundingpips": {"richtung": "buy"}})
    check(not any(x["firma"] == "fundingpips" for x in e3r["aenderungen"]), f"Richtungsschutz (id_fest) FundingPips → nie gedreht ({gedreht(e3r)})")
    e3z = lauf(chris(), zuletzt={"fp0": 290})
    check(not any(x["firma"] == "fundingpips" for x in e3z["aenderungen"]), f"Ruhezeit (fp0 vor 10 min angefasst) → FundingPips ruht ({gedreht(e3z)})")

    # 4) nur 3 Pläne der ID → keine Vorgabe, keine Drehung
    pl4 = [plan("fn0", C, "fundednext", "buy", 600), plan("fp0", C, "fundingpips", "buy", 700), plan("fp1", C, "fundingpips", "buy", 704),
           plan("x0", A, "apex", "sell", 605), plan("x1", A, "apex", "sell", 609), plan("x2", A, "apex", "sell", 613)]
    check(gedreht(lauf(pl4)) == [], "Chris mit 3 Plänen → keine Drehung")

    # 5) Band würde schlechter: Band 60 % — vorher 80 € über dem Band (unter der Hysterese 200 €), nach der Drehung 240 € → keine Drehung
    e5 = lauf(chris(), band=60.0)
    check(e5["vorher"]["ueber_band"] <= e5["daempfung"]["hysterese"] and gedreht(e5) == [],
          f"enges Band: Drehung würde das Band über die Hysterese schieben → keine Drehung ({gedreht(e5)}, vorher {e5['vorher']['ueber_band']} €)")

    print("\nBOT-MISCHUNG:", "alles grün" if ok else "FEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
