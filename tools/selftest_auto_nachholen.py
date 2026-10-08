#!/usr/bin/env python3
"""Selbsttest NACHHOLEN VERPASSTER PLÄNE (app.py ap_nachhol_minute, 08.10.2026, Master: Mikes PC offline — „kommt der PC wieder, sollen
seine verpassten Pläne automatisch sauber neu eingeplant werden (Firmen-Abstand, Gegenhedge, Klumpen), nicht still verfallen und nicht
alle auf einmal starten"). Vorher setzte sfNeuEinplanen jeden verpassten Plan auf jetzt + 2–6 min — alle auf einmal, ohne Regeln.
Ohne Netz, Platzhalter-IDs. Aufruf: python3 tools/selftest_auto_nachholen.py
Geprüft: frühestens jetzt + 2–4 min; Firmen-Abstand (seit 08.10.2026 1 min, jede ID); nacheinander nachgeholte Pläne einer ID nur noch
PC-Abstand auseinander (abstand_id_min 3 + 2 = 5 min — 20/60 min je ID seit 08.10.2026 weg, Finn: „Nur eben nicht gleichzeitig"); Richtungsschutz derselben ID × Firma; über IDs nur kein
gegenläufiger Start derselben Firma ±AP_GEGEN_FIRMA_MIN (seit 08.10.2026 ~17:00 Dubai keine Laufzeit-Sperre mehr, Finn: „kann natürlich eine
ANDERE ID Tradeify short gehen"); verpasste Pläne mit Start in der Vergangenheit blockieren nicht; nach start_bis → Klartext statt Minute."""
import os
import random
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade():
    a = sd.lade()
    src = open(sd.APP, encoding="utf-8").read()
    teile = []
    for k in ("AP_START_HAND_VORLAUF_MIN", "AP_VERTEIL_GEGEN_MIN", "AP_GEGEN_FIRMA_MIN", "AP_NACHHOL_VORLAUF_MIN", "AP_ABSTAND_ID_MIN",
              "AP_ABSTAND_ID_FIRMA_MIN", "AP_FIRMA_ABSTAND_MIN", "AP_START_BIS_STANDARD"):
        if k not in a:
            teile.append(re.search(rf"^{k} = .*$", src, re.M).group(0))
    for fn in ("ap_start_bis", "ap_start_hand_pruefen", "_ap_gegen_firma", "ap_nachhol_minute"):
        if fn not in a:
            i = src.index(f"\ndef {fn}(") + 1
            teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), a)
    return a


def main():
    a = lade()
    N = a["ap_nachhol_minute"]
    MIKE, MO, JA = "u-mike", "u-moritz", "u-jacob"
    Z = {"start_bis": "16:30"}
    jetzt = 300.0                                        # 05:00 dt
    # Mikes Pläne: Tradeify 02:05 + Topstep 04:43 verpasst (geclaimt), FundedNext 07:59/09:03, Tradeify 14:47 kommen noch
    pl = [{"plan_id": "m-tdfy", "user_id": MIKE, "firma": "tradeify", "richtung": "buy", "start_min": 125.0},
          {"plan_id": "m-ts", "user_id": MIKE, "firma": "topstep", "richtung": "sell", "start_min": 283.0},
          {"plan_id": "m-fn1", "user_id": MIKE, "firma": "fundednext", "richtung": "sell", "start_min": 479.0},
          {"plan_id": "m-fn2", "user_id": MIKE, "firma": "fundednext", "richtung": "sell", "start_min": 543.0},
          {"plan_id": "m-tdfy2", "user_id": MIKE, "firma": "tradeify", "richtung": "buy", "start_min": 887.0},
          {"plan_id": "mo-tdfy", "user_id": MO, "firma": "tradeify", "richtung": "buy", "start_min": 306.0}]   # andere ID, Tradeify 05:06
    GFA, PC = a["AP_FIRMA_ABSTAND_MIN"], 3 + 2      # Firmen-Abstand / PC-Regel (abstand_id_min Standard 3 + Laufdauer 2)
    rnd = random.Random(1)
    p = next(x for x in pl if x["plan_id"] == "m-tdfy")
    m1, f1 = N(p, pl, [], {}, jetzt, Z, None, [], rnd)
    check(m1 is not None and m1 >= jetzt + 2, f"Tradeify nachgeholt frühestens jetzt + 2 min ({m1}, {f1})")
    check(m1 is not None and abs(m1 - 306.0) >= GFA, f"Firmen-Abstand zu Moritz' Tradeify 05:06 ≥ {GFA:g} min ({m1})")
    # nacheinander: der zweite sieht die neue Zeit des ersten
    for x in pl:
        if x["plan_id"] == "m-tdfy":
            x["start_min"] = m1
    q = next(x for x in pl if x["plan_id"] == "m-ts")
    m2, f2 = N(q, pl, [], {}, jetzt, Z, None, [], random.Random(2))
    check(m2 is not None and PC <= abs(m2 - m1) < 20, f"Topstep danach ≥ {PC} min (PC), nicht mehr 20 min nach Mikes Tradeify ({m1} → {m2})")
    check(m2 is not None and all(abs(m2 - x["start_min"]) >= PC for x in pl if x["user_id"] == MIKE and x["plan_id"] != "m-ts" and x["start_min"] >= jetzt),
          f"Topstep hält {PC} min (PC) zu allen kommenden Plänen der ID")
    # gleiche Firma: zweiter verpasster FundedNext-Plan ≥ 60 min neben dem ersten
    pl2 = [{"plan_id": "a", "user_id": MIKE, "firma": "fundednext", "richtung": "sell", "start_min": 310.0},
           {"plan_id": "b", "user_id": MIKE, "firma": "fundednext", "richtung": "sell", "start_min": 200.0}]
    m3, _ = N(pl2[1], pl2, [], {}, jetzt, Z, None, [], random.Random(3))
    check(m3 is not None and PC <= abs(m3 - 310.0) < 60, f"gleiche ID × Firma: PC-Abstand reicht, keine 60 min mehr ({m3})")
    # Richtungsschutz seit 09.10.2026 ~03:45 (Finn: Richtung je Trade frei, nur nie gleichzeitig): ein kommender SELL derselben
    # ID × Firma sperrt nichts mehr; ein heute GESTARTETER SELL (kann noch laufen) sperrt AP_RICHTUNG_LAUF_FEST_MIN ab seinem Start
    pl3 = [{"plan_id": "x", "user_id": MIKE, "firma": "apex", "richtung": "buy", "start_min": 100.0},
           {"plan_id": "y", "user_id": MIKE, "firma": "apex", "richtung": "sell", "start_min": 330.0}]
    m4, _ = N(pl3[0], pl3, [], {}, jetzt, Z, 120, [], random.Random(4))
    check(m4 is not None and m4 < 330.0, f"geplanter SELL derselben ID × Firma 05:30 sperrt den BUY nicht mehr ({m4})")
    st5 = [{"user_id": MIKE, "firma": "apex", "richtung": "sell", "start": 295.0}]
    m5, _ = N(pl3[0], pl3[:1], st5, {}, jetzt, Z, 120, [], random.Random(4))
    check(m5 is not None and m5 >= 295.0 + a["AP_RICHTUNG_LAUF_FEST_MIN"],
          f"gestarteter SELL derselben ID × Firma 04:55 → BUY erst ≥ 90 min nach dessen Start ({m5})")
    # über IDs (seit 08.10.2026 ~17:00 Dubai): Jacob läuft FundedNext SELL seit 04:50 → Mikes FundedNext BUY sofort erlaubt (keine
    # Laufzeit-Sperre mehr); startet Jacobs geplanter SELL gleich (05:03), hält Mikes BUY ±3 min Abstand zu dessen Start
    pl4 = [{"plan_id": "g", "user_id": MIKE, "firma": "fundednext", "richtung": "buy", "start_min": 250.0}]
    laufend = [{"user_id": JA, "firma": "fundednext", "richtung": "sell", "start": 290.0}]
    m5, _ = N(pl4[0], pl4, [], {}, jetzt, Z, 60, laufend, random.Random(5))
    check(m5 is not None and m5 < jetzt + 5, f"Gegenrichtung einer anderen ID läuft → kein Warten auf deren Laufzeit-Ende ({m5})")
    pl4b = pl4 + [{"plan_id": "j", "user_id": JA, "firma": "fundednext", "richtung": "sell", "start_min": 303.0}]
    m5c = [N(pl4[0], pl4b, [], {}, jetzt, Z, 60, [], random.Random(s))[0] for s in range(20)]
    check(all(m is not None and abs(m - 303.0) > a["AP_GEGEN_FIRMA_MIN"] for m in m5c) and a["AP_GEGEN_FIRMA_MIN"] == 3,
          f"gegenläufiger Start einer anderen ID 05:03 → nie ±3 min daneben (20 Seeds, {sorted(round(m, 1) for m in m5c)[:3]} …)")
    m5b, _ = N(dict(pl4[0], richtung="sell"), pl4, [], {}, jetzt, Z, 60, laufend, random.Random(5))
    check(m5b is not None and m5b < 310, f"gleiche Richtung wie Jacob → keine Sperre ({m5b})")
    # verpasste (vergangene) Pläne blockieren nicht
    pl5 = [{"plan_id": "v1", "user_id": MIKE, "firma": "tradeify", "richtung": "buy", "start_min": 120.0},
           {"plan_id": "v2", "user_id": MIKE, "firma": "topstep", "richtung": "buy", "start_min": 290.0}]
    m6, _ = N(pl5[0], pl5, [], {}, jetzt, Z, None, [], random.Random(6))
    check(m6 is not None and m6 < jetzt + 5, f"vergangene, noch nicht nachgeholte Pläne derselben ID blockieren nicht ({m6})")
    # heutige Starts derselben ID zählen (PC)
    m7, _ = N(pl5[0], pl5, [{"user_id": MIKE, "firma": "apex", "start": 298.0, "richtung": "buy"}], {}, jetzt, Z, None, [], random.Random(7))
    check(m7 is not None and m7 >= 298 + PC, f"heutiger Start derselben ID (Apex 04:58) → ≥ {PC} min danach (PC) ({m7})")
    # Tagesende
    m8, f8 = N(pl5[0], pl5, [], {}, 16 * 60 + 29, Z, None, [], random.Random(8))
    check(m8 is None and f8 and "16:30" in f8, f"nach start_bis → Klartext statt Minute ({f8})")
    # Streuung: nicht starr jetzt + 2
    ws = {N(pl5[0], pl5, [], {}, jetzt, Z, None, [], random.Random(s))[0] for s in range(20)}
    check(len(ws) > 5 and min(ws) >= jetzt + 2 and max(ws) <= jetzt + 4, f"Vorlauf gestreut 2–4 min ({sorted(ws)[:4]} …)")
    # Altweg-Vergleich: früher jetzt + 2–6 min für alle → Tradeify und Topstep binnen Minuten; jetzt ≥ PC-Abstand auseinander
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
