#!/usr/bin/env python3
"""Selbsttest BOT: GEGENRICHTUNG GLEICHZEITIG, KEIN HORIZONT-PINGPONG (app.py ap_umplanen, 09.10.2026, Slave-Terminal 3 — Finn ~03:50 Dubai:
„Ich will den Saldo schon ausgleichen … am Anfang so viele Accounts zur Verfügung, wie es nur geht … man kann die Trades ja gleichzeitig
starten, wenn es verschiedene IDs und verschiedene Profile sind"; Befund S5 zum Pingpong 23:36/23:40 UTC).

Aufruf:  python3 tools/selftest_bot_gleichzeitig.py
Ohne Netz, Platzhalter-IDs. Geprüft:
(A) Pingpong 23:36 UTC: schwerer Short am Rand der 60 min, Longs später → Takt 1 zieht einen Long an den Short (Vorziehen vor Hinausschieben),
    Takt 2 (+3,5 min) zieht nichts mehr vor;
(B) nur der Short ist beweglich → Hinausschieben nur auf ≥ jetzt + 60 + Laufzeit (nie +4 min), Takt 2 ohne Zug;
(C) 4 Longs am Anfang (verschiedene IDs/Firmen) → der Short von später landet am ersten Long (± Streuung), nicht eine Stunde danach;
(D) 23:49 UTC: zwei leichte Longs laufen, ein schwerer Hand-Short startet in 8 min → ein Long von später wird an den SHORT gezogen
    (Anker = Start der Gegenrichtung), nicht an die früheste freie Minute; der Hand-Short selbst bleibt (fest);
(E) Hand-Werte (aenderbar false) fasst der Bot nie an."""
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


Z = {"fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30", "abstand_id_min": 3}
JETZT = 200
LAUFZ = 120


def plan(pid, uid, firma, richtung, start, **kw):
    p = {"plan_id": pid, "user_id": uid, "user": uid.capitalize(), "firma": firma, "firma_name": firma.capitalize(), "richtung": richtung,
         "start_min": float(start), "delta_abs": 1.0, "einsatz_abs": 100.0, "aenderbar": True, "fest_durch": None, "auto_plan": True,
         "bestaetigt": True, "route": "tvv2", "satz_eur_je_usd": 0.06, "usd_pro_pkt": 40.0, "wert_eur": 900.0, "polster_usd": 3000.0,
         "daily_usd": None, "tp_punkte": 40.0, "sl_punkte": None}
    p.update(kw)
    return p


LONG_LAUF = {"richtung": "buy", "satz": 0.03, "usd_pro_pkt": 40.0, "wert": 300.0, "polster_usd": 3000.0, "daily_usd": None,
             "tp_punkte": 40.0, "sl_punkte": None}
SHORT_LAUF = dict(LONG_LAUF, richtung="sell")   # .1545: nur ein LAUFENDES Buch rechtfertigt ein Vorziehen — geplante Trades nie


def main():
    a = sd.lade()
    U = a["ap_umplanen"]

    def lauf(plaene, jetzt=JETZT, laufend=(), **kw):
        ek = {"basis": 0.0, "brutto": 0.0, "gross_ab": 100000.0, "laufzeit": LAUFZ, "szenario_laufend": list(laufend)}
        return U(plaene, 0.0, 0.0, jetzt, Z, 25, random.Random(7), einsatz=ek, dubai_min=120, **kw)

    def anwenden(plaene, erg):
        neu = {x["plan_id"]: x for x in erg["aenderungen"]}
        return [dict(p, start_min=neu[p["plan_id"]]["nach_start_min"], richtung=neu[p["plan_id"]]["nach_richtung"])
                if p["plan_id"] in neu else p for p in plaene]

    schwer = dict(usd_pro_pkt=60.0, satz_eur_je_usd=0.07, wert_eur=1200.0)

    # (A) Pingpong 23:36 UTC — seit .1545 (14.10.2026) mit LAUFENDEM Short: nur dann darf ein Long nach vorn
    pl = [plan("s1", "ezpoker", "tradeify", "sell", JETZT + 58, **schwer),
          plan("l1", "jacob", "the5ers", "buy", JETZT + 140), plan("l2", "chris", "fundingpips", "buy", JETZT + 420),
          plan("l3", "moritz", "fundednext", "buy", JETZT + 300)]
    e0 = lauf(pl)
    check(not [x for x in e0["aenderungen"] if "vorgezogen" in x["grund"]],
          f"A0 (.1545): leeres laufendes Buch → trotz geplantem Short kein Long vorgezogen ({[x['grund'][:60] for x in e0['aenderungen']]})")
    e1 = lauf(pl, laufend=[dict(SHORT_LAUF), dict(SHORT_LAUF)])
    z1 = e1["aenderungen"]
    raus = [x for x in z1 if "hinausgeschoben" in x["grund"]]
    vor = [x for x in z1 if "vorgezogen" in x["grund"]]
    check(vor and not raus, f"A Takt 1: Long vorgezogen statt Short hinausgeschoben ({[(x['plan_id'], x['nach_start_min']) for x in z1]})")
    check(all(JETZT + a["AP_VORZIEHEN_AB_MIN"] <= x["nach_start_min"] <= JETZT + a["AP_VORZIEHEN_AB_MIN"] + a["AP_VORZIEHEN_JITTER_MIN"] + 3 for x in vor),
          f"A (.1545): Shorts LAUFEN → die Longs kommen sofort (jetzt + {a['AP_VORZIEHEN_AB_MIN']} min), nicht erst zum geplanten Short — {[x['nach_start_min'] for x in vor]}")
    pl2 = anwenden(pl, e1)
    e2 = lauf(pl2, jetzt=JETZT + 3.5, vorgezogen_heute={x["plan_id"] for x in vor}, hinaus_heute={x["plan_id"] for x in raus})
    check(not [x for x in e2["aenderungen"] if "vorgezogen" in x["grund"] or "hinausgeschoben" in x["grund"]],
          f"A Takt 2 (+3,5 min): kein weiterer Zug ({[x['grund'][:70] for x in e2['aenderungen']]})")

    # (B) nur der Short ist beweglich → weit hinaus
    fest = dict(aenderbar=False, fest_durch="Werte von Hand geändert")
    pl = [plan("s1", "ezpoker", "tradeify", "sell", JETZT + 56, **schwer), plan("l1", "jacob", "the5ers", "buy", JETZT + 140, **fest)]
    e1 = lauf(pl)
    r = [x for x in e1["aenderungen"] if x["plan_id"] == "s1"]
    check(r and r[0]["nach_start_min"] >= JETZT + 60 + LAUFZ and "hinausgeschoben" in r[0]["grund"],
          f"B: Hinausschieben nur auf ≥ jetzt + 60 + Laufzeit ({r[0]['nach_start_min'] if r else None} ≥ {JETZT + 60 + LAUFZ})")
    e2 = lauf(anwenden(pl, e1), jetzt=JETZT + 3.5, hinaus_heute={"s1"})
    check(not e2["aenderungen"], f"B Takt 2: Short nicht zurück im Horizont, kein Zug ({[x['grund'][:60] for x in e2['aenderungen']]})")
    check(not [x for x in e1["aenderungen"] if x["plan_id"] == "l1"], "E: Hand-Werte-Plan nie angefasst")

    # (C) 4 Longs am Anfang → Short gleichzeitig
    fest_l = dict(aenderbar=False, fest_durch="Handplan")
    pl = [plan("l1", "jacob", "the5ers", "buy", JETZT + 5, **fest_l), plan("l2", "ezpoker", "fundednext", "buy", JETZT + 6, **fest_l),
          plan("l3", "chris", "fundingpips", "buy", JETZT + 8, **fest_l), plan("l4", "aurel", "ftmo", "buy", JETZT + 10, **fest_l),
          plan("s1", "ina", "tradeify", "sell", JETZT + 160, **schwer)]
    e0 = lauf(pl)
    check(not [x for x in e0["aenderungen"] if x["plan_id"] == "s1"],
          "C0 (.1545): vier GEPLANTE Longs sind keine Deckung — Short bleibt bei +160 (Vorfall 14.10.2026: Longs starben in Minuten)")
    e1 = lauf(pl, laufend=[dict(LONG_LAUF), dict(LONG_LAUF), dict(LONG_LAUF)])
    s = [x for x in e1["aenderungen"] if x["plan_id"] == "s1"]
    check(s and "vorgezogen" in s[0]["grund"] and abs(s[0]["nach_start_min"] - (JETZT + 5)) <= a["AP_VORZIEHEN_JITTER_MIN"],
          f"C: Longs LAUFEN → Short von +160 an den ersten geplanten Long (+5 ± {a['AP_VORZIEHEN_JITTER_MIN']}) gezogen ({s[0]['nach_start_min'] if s else None})")

    # (D) 23:49 UTC: zwei leichte Longs laufen, schwerer Hand-Short in 8 min → Long von später an den Short
    pl = [plan("s1", "ezpoker", "tradeify", "sell", JETZT + 8, aenderbar=False, fest_durch="Werte von Hand geändert", **schwer),
          plan("l5", "jacob", "the5ers", "buy", JETZT + 290), plan("l6", "chris", "fundingpips", "buy", JETZT + 400)]
    e1 = lauf(pl, laufend=[dict(LONG_LAUF), dict(LONG_LAUF)])
    v = [x for x in e1["aenderungen"] if "vorgezogen" in x["grund"]]
    check(not v, f"D (.1545): Longs laufen, der schwere Short ist nur GEPLANT → kein Long nach vorn ({[(x['plan_id'], x['nach_start_min']) for x in v]})")
    check(not [x for x in e1["aenderungen"] if x["plan_id"] == "s1"], "D/E: Hand-Short bleibt")
    # D2: läuft der schwere Short wirklich, kommt der Long an ihn heran — mit dem schlimmsten Fall im Grund
    e2 = lauf(pl, laufend=[dict(SHORT_LAUF, usd_pro_pkt=60.0, satz=0.07, wert=1200.0)])
    v2 = [x for x in e2["aenderungen"] if "vorgezogen" in x["grund"]]
    check(v2 and all(x["nach_richtung"] == "buy" for x in v2), f"D2: schwerer Short LÄUFT → Long vorgezogen ({[(x['plan_id'], x['nach_start_min']) for x in v2]})")
    check(all("schlimmster Fall" in x["grund"] for x in v2), f"D2: Grund nennt den schlimmsten Fall ({v2[0]['grund'] if v2 else ''})")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
