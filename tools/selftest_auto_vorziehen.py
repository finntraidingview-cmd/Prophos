#!/usr/bin/env python3
"""Selbsttest GEGENRICHTUNG VORZIEHEN (app.py ap_umplanen, 08.10.2026, Slave-Terminal 3 — Finn 04:46 Dubai: „Du bist dafür da, dass du
Longs/Shorts ausgleichst, wenn du was merkst. Gerade sind nur Shorts drin, viel zu viel Short. Der Bot muss das checken und in genau
solchen Phasen schnell Longs vorziehen").

Aufruf:  python3 tools/selftest_auto_vorziehen.py
Lage wie 00:45 UTC (Platzhalter-IDs): 5 Shorts laufen (Ina 3× Apex, Jacob/Finn/Pascal The5%ers), alle Pläne bestätigt, Longs über
den Tag verteilt. Geprüft: drei Bot-Läufe ziehen drei Longs nacheinander vor (je Lauf EINER, frühestens jetzt + 3, Richtung nie,
Bestätigung bleibt = nur Startzeit), keiner gegen einen laufenden Short derselben ID × Firma, Firmen-Abstand zu anderen IDs, je ID
≥ 20 min, kein Short wird vorgezogen, Ruhezeit, Grund „Ausgleich: Long vorgezogen, … (Netto … → …)". Band ok → nichts. Netto long
zu viel → Shorts werden vorgezogen."""
import os
import random
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    a = sd.lade()
    U = a["ap_umplanen"]
    Z = {"fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30", "abstand_id_min": 3}
    d = lambda h, m: h * 60 + m - 120     # noqa: E731  Dubai → Minute deutscher Zeit
    jetzt = d(4, 46)

    def plan(pid, uid, firma, hhmm, richtung, eur=200.0, **kw):
        h, m = map(int, hhmm.split(":"))
        return dict({"plan_id": pid, "user_id": uid, "user": uid.capitalize(), "firma": firma, "firma_name": firma.capitalize(),
                     "richtung": richtung, "start_min": float(d(h, m)), "delta_abs": 1.0, "einsatz_abs": eur, "aenderbar": True,
                     "fest_durch": None, "auto_plan": True, "bestaetigt": True, "route": "tvv2"}, **kw)
    laufend = [{"user_id": "ina", "firma": "apex", "start": float(jetzt - x), "richtung": "sell"} for x in (20, 16, 12)]
    laufend += [{"user_id": u, "firma": "the5ers", "start": float(jetzt - x), "richtung": "sell"} for u, x in (("jacob", 23), ("finn", 22), ("pascal", 17))]
    plaene = [plan("ina_tf", "ina", "tradeify", "10:54", "buy"), plan("chris_fp", "chris", "fundingpips", "07:30", "buy"),
              plan("moritz_fn", "moritz", "fundednext", "09:10", "buy"), plan("ina_apex_l", "ina", "apex", "08:00", "buy"),
              plan("jacob_t5_l", "jacob", "the5ers", "12:00", "buy"), plan("mike_fn", "mike", "fundednext", "06:40", "buy"),
              plan("emin_tf_s", "emin", "tradeify", "05:30", "sell"), plan("aurel_ap_s", "aurel", "apex", "06:00", "sell"),
              plan("hand_l", "simon", "topstep", "05:20", "buy", aenderbar=False, fest_durch="Werte von Hand geändert")]
    EK = {"basis": -1000.0, "brutto": 1000.0, "gross_ab": 10000.0, "laufzeit": 60}
    id_fest = {"ina|apex": {"richtung": "sell", "durch": "laufender Trade"}, "jacob|the5ers": {"richtung": "sell", "durch": "laufender Trade"},
               "finn|the5ers": {"richtung": "sell", "durch": "laufender Trade"}, "pascal|the5ers": {"richtung": "sell", "durch": "laufender Trade"}}
    start0 = {p["plan_id"]: p["start_min"] for p in plaene}
    pl, jm, zul, je_lauf, alle = [dict(p) for p in plaene], jetzt, {}, [], []
    for lauf in range(3):
        erg = U(pl, 0.0, 0.0, jm, Z, 25, random.Random(lauf), gestartet=laufend, id_fest=id_fest, einsatz=EK, zuletzt=zul, dubai_min=120)
        je_lauf.append(erg["aenderungen"])
        alle += erg["aenderungen"]
        neu = {x["plan_id"]: x["nach_start_min"] for x in erg["aenderungen"]}
        pl = [dict(p, start_min=neu.get(p["plan_id"], p["start_min"])) for p in pl]
        for k in neu:
            zul[k] = jm
        jm += 2                                           # Bot-Takt 2 min (wie heute früh)
    st = {p["plan_id"]: p["start_min"] for p in pl}
    vorg = [x["plan_id"] for x in alle]
    check([len(x) for x in je_lauf] == [1, 1, 1], f"drei Läufe → je genau EIN Plan vorgezogen ({[len(x) for x in je_lauf]})")
    check(len(set(vorg)) == 3 and all(start0[i] > st[i] for i in vorg), f"drei verschiedene Longs nach vorn ({vorg})")
    check(all(x["von_richtung"] == x["nach_richtung"] == "buy" for x in alle), "nur Longs, Richtung nie gedreht (Bestätigung bleibt: nur start_um)")
    check(all(x["nach_start_min"] >= jetzt + a["AP_VORZIEHEN_AB_MIN"] for x in alle), "frühestens jetzt + 3 min")
    check(all(x["nach_start_min"] <= d(4, 46) + 2 * 2 + a["AP_VORZIEHEN_AB_MIN"] + 25 for x in alle),
          f"schnell: alle Vorgezogenen starten in den nächsten ~30 min ({['%02d:%02d' % divmod(int(x['nach_start_min'] + 120), 60) for x in alle]} Dubai)")
    check("ina_apex_l" not in vorg and "jacob_t5_l" not in vorg,
          "nie gegen einen laufenden Short derselben ID × Firma (Ina Apex, Jacob The5%ers bleiben)")
    check(not any(i in vorg for i in ("emin_tf_s", "aurel_ap_s", "hand_l")), "keine Shorts, keine Werte von Hand")
    for x in alle:
        p = next(q for q in plaene if q["plan_id"] == x["plan_id"])
        nah_f = [o for o in laufend + [{"user_id": q["user_id"], "firma": q["firma"], "start": st[q["plan_id"]]} for q in plaene if q["plan_id"] != p["plan_id"]]
                 if o["user_id"] != p["user_id"] and o["firma"] == p["firma"] and abs(o["start"] - x["nach_start_min"]) < a["AP_FIRMA_ABSTAND_MIN"]]
        check(not nah_f, f"Firmen-Abstand ≥ 5 min zu anderen IDs ({p['plan_id']})")
    # je ID: jeder vorgezogene Plan hält Abstand zu allen anderen Plänen/Starts seiner ID (die laufenden untereinander zählen nicht)
    def id_abst_ok(pid):
        p = next(q for q in plaene if q["plan_id"] == pid)
        andere = [st[q["plan_id"]] for q in plaene if q["user_id"] == p["user_id"] and q["plan_id"] != pid]
        andere += [float(o["start"]) for o in laufend if o["user_id"] == p["user_id"]]
        return all(abs(st[pid] - s) >= a["AP_ABSTAND_ID_MIN"] * 0.25 for s in andere)
    check(all(id_abst_ok(i) for i in vorg), "je ID Abstand gehalten (vorgezogene Pläne gegen alle Pläne/Starts ihrer ID)")
    g = alle[0]["grund"] if alle else ""
    m_ = __import__("re").search(r"Netto ([+-]\d+) → ([+-]\d+)", g)
    check(g.startswith("Ausgleich: Long vorgezogen, ") and "Dubai" in g and m_ and int(m_.group(2)) > int(m_.group(1)),
          f"Protokoll-Grund mit Netto vorher → nachher am neuen Start ({g})")
    # Band ok → nichts
    ok_erg = U([dict(p) for p in plaene], 0.0, 0.0, jetzt, Z, 25, random.Random(1), gestartet=laufend, id_fest=id_fest,
               einsatz=dict(EK, basis=-100.0, brutto=1000.0))
    check(not [x for x in ok_erg["aenderungen"] if x["grund"].startswith("Ausgleich:")], "Band ok (Netto −100 bei Brutto 1.000) → nichts vorgezogen")
    # Spiegel: zu viel Long → ein Short wird vorgezogen
    sp = U([dict(p) for p in plaene], 0.0, 0.0, jetzt, Z, 25, random.Random(1), gestartet=[dict(o, richtung="buy") for o in laufend],
           id_fest={k: dict(v, richtung="buy") for k, v in id_fest.items()}, einsatz=dict(EK, basis=1000.0))
    check(len(sp["aenderungen"]) == 1 and sp["aenderungen"][0]["nach_richtung"] == "sell", f"zu viel Long → ein Short vorgezogen ({[x['plan_id'] for x in sp['aenderungen']]})")

    # ── Hysterese 100 € nur fürs Vorziehen: Über-Band 150 € (unter 200, über 100) löst aus ──────────────────────────────────────
    # nur Shorts laufend: Über-Band = |Netto| − 25 % × Brutto = 0,75 × |Netto| → Netto −200 € ergibt 150 €
    e_h = U([plan("chris_fp", "chris", "fundingpips", "07:30", "buy")], 0.0, 0.0, jetzt, Z, 25, random.Random(1),
            einsatz=dict(EK, basis=-200.0, brutto=200.0))
    check(e_h["vorher"]["ueber_band"] < 200 and len(e_h["aenderungen"]) == 1,
          f"Über-Band {e_h['vorher']['ueber_band']} € (< 200 Hysterese, > {a['AP_VORZIEHEN_HYSTERESE_EUR']:g}): Long wird vorgezogen")
    e_h0 = U([plan("chris_fp", "chris", "fundingpips", "07:30", "buy")], 0.0, 0.0, jetzt, Z, 25, random.Random(1),
             einsatz=dict(EK, basis=-120.0, brutto=120.0))
    check(not e_h0["aenderungen"], f"Über-Band {e_h0['vorher']['ueber_band']} € (< 100): nichts")

    # ── PINGPONG-BREMSE über 6 Läufe: vorgezogen → nie wieder nach hinten verteilt ───────────────────────────────────────────
    # Moritz hat zwei FundedNext-Longs 09:10/10:30; Netto short → 09:10 wird vorgezogen; die Verteilung darf ihn danach nicht zurück-
    # schieben (sie würde sonst den Klumpen gegen den laufenden Plan auflösen), auch nicht, wenn das Band wieder hält
    pp = [plan("m1", "moritz", "fundednext", "09:10", "buy"), plan("m2", "moritz", "fundednext", "05:20", "buy")]
    pl6, jm6, zul6, vorg6, vert6, verlauf = [dict(p) for p in pp], jetzt, {}, set(), set(), []
    for lauf in range(6):
        ek6 = dict(EK, basis=-600.0 if lauf < 2 else 0.0, brutto=600.0 if lauf < 2 else 0.0)   # ab Lauf 3 ausgeglichen
        e6 = U(pl6, 0.0, 0.0, jm6, Z, 25, random.Random(lauf), einsatz=ek6, zuletzt=zul6, dubai_min=120,
               vorgezogen_heute=vorg6, verteilt_heute=vert6)
        for x in e6["aenderungen"]:
            (vorg6 if x["grund"].startswith("Ausgleich:") else vert6).add(x["plan_id"])
            zul6[x["plan_id"]] = jm6
            verlauf.append((lauf, x["plan_id"], round(x["von_start_min"]), round(x["nach_start_min"]), x["grund"][:20]))
        neu6 = {x["plan_id"]: x["nach_start_min"] for x in e6["aenderungen"]}
        pl6 = [dict(p, start_min=neu6.get(p["plan_id"], p["start_min"])) for p in pl6]
        jm6 += 31                                                        # nach der Ruhezeit
    rueck = [v for v in verlauf if v[1] in vorg6 and v[4].startswith("Verteilung") and v[3] > v[2]]
    check(vorg6 and not rueck, f"6 Läufe: vorgezogener Plan wird nie wieder nach hinten verteilt ({verlauf})")
    hin_her = {}
    for v in verlauf:
        hin_her.setdefault(v[1], []).append(v[3] - v[2])
    check(all(not (any(d < 0 for d in ds) and any(d > 0 for d in ds)) for ds in hin_her.values()), "kein Plan wandert vor UND zurück")
    # verteilter Plan wird nur vorgezogen, wenn ≥ ½ Abstand bleibt (keine ¼-Stufe = 15 min)
    vt = [plan("v1", "ina", "tradeify", "05:20", "buy"), plan("v2", "ina", "tradeify", "07:00", "buy")]
    e_v = U(vt, 0.0, 0.0, jetzt, Z, 25, random.Random(1), einsatz=EK, verteilt_heute={"v2"})
    nv = {x["plan_id"]: x["nach_start_min"] for x in e_v["aenderungen"]}
    st_v = {p["plan_id"]: nv.get(p["plan_id"], p["start_min"]) for p in vt}
    check("v2" not in nv or abs(st_v["v2"] - st_v["v1"]) >= a["AP_ABSTAND_ID_FIRMA_MIN"] * 0.5,
          f"verteilter Plan: Vorziehen nur mit ≥ ½ Abstand je ID × Firma ({[(k, round(v)) for k, v in st_v.items()]})")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
