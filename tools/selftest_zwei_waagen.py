#!/usr/bin/env python3
"""Selbsttest: ZWEI WAAGEN (app.py ap_klassen_waage / ap_waage_passt / ap_waage_nachschub / ap_waage_start_lage, Finn 17.10.2026) —
rein rechnend, Stand nachgebaut mit den Fällen vom Beobachtungstag 16.10.2026. Aufruf: python3 tools/selftest_zwei_waagen.py"""
import os
import random
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "random": random}
    teile = []
    for k in ("WD_FUTURES_FIRMEN", "WD_BALANCE_FUTURES", "AP_TYPEN", "AP_CFD_ROUTEN", "AP_KLASSE_TXT"):
        teile.append(re.search(rf"^{k} = .*$", src, re.M).group(0).split("  #")[0])
    for z in re.findall(r"^AP_WAAGE_[A-Z_]+ = .*$", src, re.M):
        teile.append(z.split("  #")[0])
    for name in ("_wd_num", "_ap_hhmm_txt", "ap_klasse", "ap_waage_an", "ap_waage_ohne_liste", "ap_waage_ohne", "ap_waage_folgt", "_ap_waage_gewicht", "_ap_waage_startet", "ap_waage_zeile_zaehlt",
                 "_ap_eur_txt", "ap_waage_passt", "ap_waage_deckel", "_ap_waage_note", "ap_klassen_waage", "_ap_waage_kandidat", "_ap_waage_rs_frei",
                 "_ap_waage_zielminute", "ap_waage_nachschub", "ap_waage_start_lage"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def lauf(pid, uid, firma, fk, route, r, eur, start=100.0):
    return {"plan_id": pid, "user_id": uid, "user": uid, "firma": firma, "firma_key": fk, "route": route, "richtung": r,
            "verlust_eur": eur, "typ": "challenge", "gehedgt": False, "start_min": start}


def plan(pid, uid, firma, fk, route, r, eur, start, bestaetigt=True, **kw):
    z = {"plan_id": pid, "user_id": uid, "user": uid, "firma": firma, "firma_key": fk, "route": route, "richtung": r,
         "verlust_eur": eur, "typ": "challenge", "gehedgt": False, "start_min": start, "auto_plan": True, "bestaetigt": bestaetigt,
         "aenderbar": True, "geclaimt": False}
    z.update(kw)
    return z


def main():
    ns = lade()
    W, P, N, S = ns["ap_klassen_waage"], ns["ap_waage_passt"], ns["ap_waage_nachschub"], ns["ap_waage_start_lage"]
    f = []

    def check(ok, name):
        f.append(0 if ok else 1)
        print(("OK  " if ok else "FEHL") + " " + name)

    TF, FN, AP, FP = ("Tradeify", "tradeify", "tvv2"), ("FundedNext", "fundednext", "mt5v2"), ("Apex Trader", "apex", "tvv2"), \
        ("FundingPips", "fundingpips", "mt5v2")
    jm = 600.0

    # 1) 07:58-Fall: drei Tradeify/Apex-Shorts, kein Futures-Long — CFD-Longs gleichen NICHT aus
    st = {"jetzt_min": jm, "offen": [lauf("o1", "mike", *TF, "sell", 215), lauf("o2", "marc", *TF, "sell", 215),
                                      lauf("o3", "moritz", *AP, "sell", 200), lauf("o4", "aurel", *FN, "buy", 300),
                                      lauf("o5", "chris", *FN, "buy", 300)], "geplant": [], "id_fest": {}, "starts_heute": []}
    w = W(st)
    check(w["futures"]["n_short"] == 2 and w["futures"]["n_long"] == 0 and not w["futures"]["passt"] and w["futures"]["leicht"] == "buy",
          f"Futures 0 : 2 passt nicht, leicht = Long — Apex-Short zählt nicht (19.10.2026) ({w['futures']['grund']})")
    check(w["cfd"]["n_long"] == 2 and w["cfd"]["leicht"] == "sell", "CFD getrennt gewogen (2 Long, kein Short)")

    # 2) Futures 2 : 1 passt, 3 : 1 nicht
    check(P("futures", {"n_long": 2, "n_short": 1, "long_eur": 430, "short_eur": 215})[0], "Futures 2 : 1 passt (Anzahl, nicht €)")
    check(not P("futures", {"n_long": 3, "n_short": 1, "long_eur": 645, "short_eur": 215})[0], "Futures 3 : 1 passt nicht")

    # 3) CFD-Toleranz aus Finns „passt"-Momenten
    check(P("cfd", {"n_long": 3, "n_short": 2, "long_eur": 562, "short_eur": 630})[0], "CFD 562 : 630 passt (04:52)")
    check(P("cfd", {"n_long": 3, "n_short": 2, "long_eur": 900, "short_eur": 720})[0], "CFD 900 : 720 passt (06:43, 20 %)")
    pr = P("cfd", {"n_long": 3, "n_short": 8, "long_eur": 300, "short_eur": 2000})
    check(not pr[0] and pr[2] == "buy", f"CFD 300 : 2.000 passt nicht, leicht = Long (15:57) — {pr[1]}")

    # 4) Beendete zählen nie, WD/Funded nie, gehedgt nie
    st2 = {"jetzt_min": jm, "offen": [lauf("o1", "a", *TF, "sell", 215), dict(lauf("w1", "b", *TF, "buy", 215), typ="winning_days"),
                                       dict(lauf("g1", "c", *TF, "buy", 215), gehedgt=True)], "geplant": []}
    w2 = W(st2)
    check(w2["futures"]["n_long"] == 0 and w2["futures"]["n_short"] == 1, "WD und gehedgt zählen nicht in der Waage")

    # 5) Start in ≤ 2 min zählt mit, später nicht, unbestätigt nicht
    st3 = {"jetzt_min": jm, "offen": [], "geplant": [plan("p1", "a", *TF, "buy", 215, jm + 1.5), plan("p2", "b", *TF, "sell", 215, jm + 10),
                                                   plan("p3", "c", *TF, "sell", 215, jm + 1, bestaetigt=False)]}
    w3 = W(st3)
    check(w3["futures"]["n_long"] == 1 and w3["futures"]["n_short"] == 0, "nur bestätigter Start in ≤ 2 min zählt")

    # 6) Nachschub 07:58: Futures-Long vorziehen, Firma A gegen B zuerst, nie drehen
    st["geplant"] = [plan("k1", "ina", *TF, "buy", 215, jm + 120), plan("k2", "ezp", *AP, "buy", 200, jm + 200),
                     plan("k3", "jacob", *TF, "sell", 215, jm + 60), plan("k4", "chris", *FP, "sell", 300, jm + 30)]
    aend, info = N(st, W(st), random.Random(1))
    fut = [a for a in aend if a["plan_id"] in ("k1", "k2", "k3")]
    check(len(fut) >= 1 and all(a["von_richtung"] == a["nach_richtung"] == "buy" for a in fut), f"Futures: nur Longs vorgezogen, nicht gedreht ({[a['plan_id'] for a in fut]})")
    check(fut and fut[0]["plan_id"] == "k1" and jm + 2 <= fut[0]["nach_start_min"] <= jm + 8, f"Tradeify-Long zuerst, Start jetzt + 2–8 min ({fut and fut[0]['nach_start_min']})")
    check("k2" not in [a["plan_id"] for a in fut], "Apex-Long wird NIE als Gegengewicht vorgezogen (19.10.2026)")
    w_n = dict(W(st)["futures"])
    for a in fut:
        w_n["n_long"] += 1
    check(P("futures", w_n)[0] or len(fut) == 2, f"Futures danach höchstens 2 : 1 ({w_n['n_long']} : {w_n['n_short']})")
    cfd = [a for a in aend if a["plan_id"] == "k4"]
    check(len(cfd) == 1 and cfd[0]["nach_richtung"] == "sell", "CFD: Short (FundingPips) gegen die zwei FN-Longs vorgezogen")
    check(all(a["grund"].startswith("[Waage]") for a in aend), "Protokoll-Grund beginnt mit [Waage]")

    # 7) Richtungsschutz: laufender Short derselben ID × Firma sperrt den Long-Kandidaten (auch WD)
    st5 = {"jetzt_min": jm, "offen": [lauf("o1", "mike", *TF, "sell", 215)], "starts_heute": [],
           "id_fest": {"ina|tradeify": {"richtung": "sell", "durch": "läuft gerade", "plan_id": "wd1"}},
           "geplant": [plan("k1", "ina", *TF, "buy", 215, jm + 120), plan("k2", "ezp", *TF, "buy", 215, jm + 150)]}
    aend5, _ = N(st5, W(st5), random.Random(2))
    check([a["plan_id"] for a in aend5] == ["k2"], f"Ina gesperrt (WD-Short läuft bei Ina × Tradeify) → EzPoker ({[a['plan_id'] for a in aend5]})")

    # 8) Unauffällig: dieselbe Firma, Gegenrichtung startete eben → mindestens 2 min danach
    st6 = {"jetzt_min": jm, "offen": [lauf("o1", "mike", *TF, "sell", 215, start=jm - 0.5)], "starts_heute": [], "id_fest": {},
           "geplant": [plan("k1", "ina", *TF, "buy", 215, jm + 120)]}
    aend6, _ = N(st6, W(st6), random.Random(3))
    check(aend6 and jm - 0.5 + 1.0 <= aend6[0]["nach_start_min"] <= jm - 0.5 + 10.0 + 3.0, f"Gegenrichtung gleiche Firma 1–10 min nach dem Short ({aend6 and aend6[0]['nach_start_min']})")
    # 8b) Zufall 1–10 min: über 40 Seeds streuen die Abstände, nichts unter 1 min, nichts über 10 min (+ PC-/Firmen-Ausweichen bis 13)
    abst = []
    for seed in range(40):
        a6, _ = N(st6, W(st6), random.Random(seed))
        abst.append(round(a6[0]["nach_start_min"] - (jm - 0.5), 2))
    check(min(abst) >= 1.0 and max(abst) <= 13.0 and (max(abst) - min(abst)) >= 4.0 and len(set(abst)) >= 20,
          f"Firmen-Abstand gestreut (Jitter-Regel): {min(abst)}–{max(abst)} min, {len(set(abst))} verschiedene Werte")

    # 9) PC belegt: derselbe User startet in ± 3 min → später
    st7 = {"jetzt_min": jm, "offen": [lauf("o1", "mike", *TF, "sell", 215, start=jm - 30)], "id_fest": {},
           "starts_heute": [{"user_id": "ina", "start": jm + 2.5}], "geplant": [plan("k1", "ina", *TF, "buy", 215, jm + 120)]}
    aend7, _ = N(st7, W(st7), random.Random(4))
    check(aend7 and aend7[0]["nach_start_min"] >= jm + 5.5, f"PC derselben ID frei (± 3 min) ({aend7 and aend7[0]['nach_start_min']})")

    # 10) CFD 75 %: Lücke 1.700 € → gezogen bis ≥ 1.275 € oder passt
    st8 = {"jetzt_min": jm, "offen": [lauf("o1", "marc", *FN, "sell", 1000), lauf("o2", "chris", *FN, "sell", 1000), lauf("o3", "aurel", *FP, "buy", 300)],
           "id_fest": {}, "starts_heute": [],
           "geplant": [plan(f"c{i}", f"u{i}", *FP, "buy", 500, jm + 30 + i * 20) for i in range(5)]}
    aend8, info8 = N(st8, W(st8), random.Random(5))
    check(len(aend8) == 3, f"CFD: 3 × 500 € Long gezogen (≥ 75 % von 1.700 €) — {len(aend8)}")

    # 11) Hand-Werte / unänderbar nie, Folgetag nie
    st9 = {"jetzt_min": jm, "offen": [lauf("o1", "mike", *TF, "sell", 215)], "id_fest": {}, "starts_heute": [],
           "geplant": [plan("k1", "ina", *TF, "buy", 215, jm + 120, aenderbar=False), plan("k2", "ezp", *TF, "buy", 215, jm + 130, folgetag=True)]}
    check(N(st9, W(st9), random.Random(6))[0] == [], "Hand-Werte/fällig/Folgetag werden nie gezogen")

    # 12) Start-Lage: erster Futures-Trade des Tages → nicht passt, nicht besser; ein Long gegen 2 Shorts → besser
    st10 = {"jetzt_min": jm, "offen": [], "geplant": [plan("p1", "a", *TF, "buy", 215, jm)]}
    L = S(st10, "p1", "buy")
    check(L and not L["nachher"]["passt"] and not L["nachher"]["besser"] and L["zaehlt"], "erster Futures-Trade: Gegentrade nötig")
    st11 = {"jetzt_min": jm, "offen": [lauf("o1", "m", *TF, "sell", 215), lauf("o2", "n", *TF, "sell", 215)],
            "geplant": [plan("p1", "a", *TF, "buy", 215, jm)]}
    L2 = S(st11, "p1", "buy")
    check(L2["nachher"]["passt"] and L2["vorher"]["n_short"] == 2, "Long gegen 2 laufende Shorts: passt (1 : 2)")
    check(not L2["gegen"]["passt"] and not L2["gegen"]["besser"], "Drehen auf Short wäre schwerer → nie")

    # 14) APEX OHNE WAAGE (Finn 19.10.2026): zählt nicht, wird nicht gezogen, startet ohne Prüfung; per regeln.ausgleich.waage_ohne=[] wieder an
    st12 = {"jetzt_min": jm, "offen": [lauf("a1", "moritz", *AP, "sell", 200), lauf("a2", "ezp", *AP, "sell", 200), lauf("a3", "ina", *AP, "buy", 200)],
            "id_fest": {}, "starts_heute": [], "geplant": [plan("p1", "mike", *AP, "buy", 200, jm), plan("k1", "jacob", *TF, "buy", 215, jm + 90)]}
    w12 = W(st12)
    check(w12["futures"]["n_long"] == 0 and w12["futures"]["n_short"] == 0 and w12["futures"]["passt"], "drei laufende Apex-Trades: Futures-Waage leer, passt")
    check(N(st12, w12, random.Random(7))[0] == [], "Apex-Schieflage zieht keinen Tradeify-Gegentrade")
    L3 = S(st12, "p1", "buy")
    check(L3 and L3.get("ohne_waage") and L3["zaehlt"] and L3["nachher"]["passt"] and L3["gegen"]["passt"] and not L3["nachher"]["besser"],
          "Apex-Plan am Start: passt (ohne Waage), nichts vorgezogen")
    st13 = {"jetzt_min": jm, "offen": [lauf("o1", "mike", *TF, "sell", 215)], "id_fest": {}, "starts_heute": [],
            "geplant": [plan("k2", "ezp", *AP, "buy", 200, jm + 90)]}
    check(N(st13, W(st13), random.Random(8))[0] == [], "Tradeify-Short allein: Apex-Long ist kein Gegengewicht → nichts gezogen")
    st13["param"] = {"waage_ohne": []}
    aend13, _ = N(st13, W(st13), random.Random(8))
    check([a["plan_id"] for a in aend13] == ["k2"], "regeln.ausgleich.waage_ohne = [] → Apex wiegt wieder mit (Rückweg ohne Code)")
    st14 = {"jetzt_min": jm, "offen": [lauf("o1", "mike", *TF, "sell", 215), lauf("a1", "moritz", *AP, "buy", 200)], "id_fest": {}, "starts_heute": [],
            "geplant": [plan("k1", "ina", *TF, "buy", 215, jm + 90)]}
    aend14, _ = N(st14, W(st14), random.Random(9))
    check([a["plan_id"] for a in aend14] == ["k1"], "Tradeify-Short + Apex-Long laufen: Apex deckt nicht → Tradeify-Long (andere ID) vorgezogen")
    check(aend14 and aend14[0]["nach_start_min"] >= jm + 2.0, f"… Tradeify gegen Tradeify frühestens jetzt + 2 min ({aend14 and aend14[0]['nach_start_min']})")

    # 15) PAARE (Finn 19.10.2026): Gegentrade einer anderen ID folgt in ≤ 10 min → Waage zieht nichts vor, der erste des Paares darf starten
    st15 = {"jetzt_min": jm, "offen": [lauf("o1", "mike", *TF, "sell", 215, start=jm - 0.2)], "id_fest": {}, "starts_heute": [],
            "geplant": [plan("p2", "moritz", *TF, "buy", 215, jm + 6.5), plan("k9", "ina", *TF, "buy", 215, jm + 120)]}
    aend15, info15 = N(st15, W(st15), random.Random(15))
    check(aend15 == [] and info15 and info15[0].get("folgt", {}).get("plan_id") == "p2", f"Moritz-Long folgt in 6,5 min → nichts vorgezogen ({[a['plan_id'] for a in aend15]})")
    st16 = {"jetzt_min": jm, "offen": [], "id_fest": {}, "starts_heute": [],
            "geplant": [plan("p1", "mike", *TF, "sell", 215, jm), plan("p2", "moritz", *TF, "buy", 215, jm + 6.5)]}
    L16 = S(st16, "p1", "sell")
    check(L16["nachher"]["passt"] and L16["nachher"].get("folgt", {}).get("plan_id") == "p2", f"erster des Paares startet: {L16['nachher']['grund']}")
    st17 = {"jetzt_min": jm, "offen": [], "id_fest": {}, "starts_heute": [],
            "geplant": [plan("p1", "mike", *TF, "sell", 215, jm), plan("p2", "moritz", *TF, "buy", 215, jm + 25)]}
    check(not S(st17, "p1", "sell")["nachher"]["passt"], "Gegentrade erst in 25 min → wie bisher Gegentrade nötig")
    st18 = {"jetzt_min": jm, "offen": [], "id_fest": {}, "starts_heute": [],
            "geplant": [plan("p1", "mike", *TF, "sell", 215, jm), plan("p2", "moritz", *AP, "buy", 215, jm + 5)]}
    check(not S(st18, "p1", "sell")["nachher"]["passt"], "Apex-Long in 5 min zählt nicht als Partner")

    # 13) Schalter
    check(ns["ap_waage_an"]({}) and ns["ap_waage_an"]({"ausgleich": {"aktiv": True}}) and not ns["ap_waage_an"]({"ausgleich": {"waage": False}}),
          "Schalter regeln.ausgleich.waage: Standard an, false = aus")

    n = sum(f)
    print(f"\n{len(f) - n}/{len(f)} OK")
    sys.exit(1 if n else 0)


if __name__ == "__main__":
    main()
