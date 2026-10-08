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

    # 3) bestätigte oder feste Tranche wird nie gedreht
    e3 = lauf(chris(bestaetigt=True))
    check(not any(x["firma"] == "fundingpips" for x in e3["aenderungen"]), f"FundingPips bestätigt → nie gedreht ({gedreht(e3)})")
    check(len({x["firma"] for x in e3["aenderungen"]}) == 1, f"kleine Tranche gesperrt → höchstens EINE Mischungs-Drehung je Lauf ({gedreht(e3)})")
    e3b = lauf(chris(aenderbar=False, fest_durch="schon gestartet"))
    check(not any(x["firma"] == "fundingpips" for x in e3b["aenderungen"]), f"FundingPips fest (gestartet) → nie gedreht ({gedreht(e3b)})")
    pl3 = [dict(p, bestaetigt=True) if p["firma"] in ("fundednext", "fundingpips") else p for p in chris()]
    check(gedreht(lauf(pl3)) == [], "alle Long-Tranchen bestätigt → keine Drehung")
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
