#!/usr/bin/env python3
"""Selbsttest SUCHE ÜBER MEHRERE ZÜGE (app.py ap_umplanen, 08.10.2026, Slave-Terminal 3 — Finn über Master: „Der Bot soll quasi die
ganze Zeit schauen … und immer die beste Kombination suchen").

Aufruf:  python3 tools/selftest_auto_suche.py
Ohne Netz, Platzhalter-IDs. Lage wie Finns: 3× Apex short (Tageslimit-Klippe bei +20 Pkt) laufen, viele geplante Longs später am Tag.
Geprüft: mehrere Züge je Lauf (≤ AP_SUCHE_ZUEGE), jeder hebt das Minimum ±30 um ≥ AP_SZENARIO_MIN_GEWINN_EUR (nachgerechnet), Ergebnis
mindestens so gut wie ein Zug allein und wie Greedy (Breite 1); in der Kombination alle Abstände (Firma zwischen IDs, je ID, je ID ×
Firma ≥ ½-Stufe) und kein Gegenhedge über IDs; Hinausschieben eines Shorts aus den 60 min; Hand-Plan, toter PC, ruhender Plan nie;
Pingpong (heute hinausgeschoben → nicht vorziehen, heute vorgezogen → nicht hinausschieben); ein Zug je Plan; Laufzeit < 3 s bei 40
Plänen; ausgeglichenes Buch → nichts."""
import collections
import os
import random
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


S = 180.0 / 2500.0
APEX = {"richtung": "sell", "satz": S, "usd_pro_pkt": 100.0, "wert": 180.0, "polster_usd": 2500.0, "daily_usd": 2000.0,
        "tp_punkte": 40.0, "sl_punkte": None}
LAUFEND = [dict(APEX) for _ in range(3)]
Z = {"fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30", "abstand_id_min": 3}
JETZT = 200


def plan(pid, uid, firma, richtung, start, **kw):
    p = {"plan_id": pid, "user_id": uid, "user": uid.capitalize(), "firma": firma, "firma_name": firma.capitalize(), "richtung": richtung,
         "start_min": float(start), "delta_abs": 1.0, "einsatz_abs": 100.0, "aenderbar": True, "fest_durch": None, "auto_plan": True,
         "bestaetigt": True, "route": "tvv2", "satz_eur_je_usd": 0.06, "usd_pro_pkt": 40.0, "wert_eur": 900.0, "polster_usd": 3000.0,
         "daily_usd": None, "tp_punkte": 40.0, "sl_punkte": None}
    p.update(kw)
    return p


def main():
    a = sd.lade()
    U, L, T = a["ap_umplanen"], a["ap_szenario_lage"], a["ap_szenario_trade_aus_zeile"]
    EK = {"basis": 0.0, "brutto": 0.0, "gross_ab": 100000.0, "laufzeit": 60, "szenario_laufend": LAUFEND}

    def lage(plaene, neu=None, richt=None):
        neu, richt = neu or {}, richt or {}
        tr = list(LAUFEND)
        for p in plaene:
            s_ = neu.get(p["plan_id"], p["start_min"])
            if JETZT <= s_ <= JETZT + 60:
                tr.append(T(dict(p, richtung=richt.get(p["plan_id"], p["richtung"])), False))
        return L(tr)

    # Longs bei vier IDs und drei Firmen, alle später am Tag; je ID auch ein zweiter Long derselben Firma
    longs = []
    for k, (uid, firma) in enumerate([("chris", "tradeify"), ("ina", "tradeify"), ("moritz", "fundednext"), ("aurel", "topstep"),
                                      ("chris", "fundingpips"), ("ina", "fundednext")]):
        longs.append(plan(f"l{k}", uid, firma, "buy", 420 + 25 * k))
    fest = {f"{p['user_id']}|{p['firma']}": {"richtung": "buy"} for p in longs}     # Richtung fest → nur Züge in der Zeit

    # ── 1 mehrere Züge, jeder ≥ 10 €, besser als ein Zug allein und als Greedy ─────────────────────────────────────────────────
    erg = U(longs, 0.0, 0.0, JETZT, Z, 25, random.Random(1), einsatz=EK, dubai_min=120, id_fest=fest)
    zuege = [x for x in erg["aenderungen"]]
    check(2 <= len(zuege) <= a["AP_SUCHE_ZUEGE"], f"mehrere Züge in einem Lauf ({len(zuege)}, höchstens {a['AP_SUCHE_ZUEGE']})")
    neu, schritte, ok_schritt = {}, [lage(longs)["min_eur"]], True
    for x in zuege:
        neu[x["plan_id"]] = x["nach_start_min"]
        schritte.append(lage(longs, neu)["min_eur"])
        ok_schritt &= schritte[-1] >= schritte[-2] + a["AP_SZENARIO_MIN_GEWINN_EUR"] - 1e-6
    check(ok_schritt, f"jeder Zug hebt das Minimum ±30 um ≥ {a['AP_SZENARIO_MIN_GEWINN_EUR']:g} € ({[round(v) for v in schritte]})")
    check(all("schlimmster Fall" in x["grund"] and "Delta" in x["grund"] and "Zug " in x["grund"] for x in zuege),
          f"Grund nennt schlimmsten Fall, Delta und Zug n/m ({zuege[0]['grund'] if zuege else ''})")
    z_alt = a["AP_SUCHE_ZUEGE"]
    a["AP_SUCHE_ZUEGE"] = 1
    e1 = U(longs, 0.0, 0.0, JETZT, Z, 25, random.Random(1), einsatz=EK, dubai_min=120, id_fest=fest)
    a["AP_SUCHE_ZUEGE"] = z_alt
    b_alt = a["AP_SUCHE_BREITE"]
    a["AP_SUCHE_BREITE"] = 1
    eg = U(longs, 0.0, 0.0, JETZT, Z, 25, random.Random(1), einsatz=EK, dubai_min=120, id_fest=fest)
    a["AP_SUCHE_BREITE"] = b_alt
    m_suche = schritte[-1]
    m_eins = lage(longs, {x["plan_id"]: x["nach_start_min"] for x in e1["aenderungen"]})["min_eur"]
    m_gier = lage(longs, {x["plan_id"]: x["nach_start_min"] for x in eg["aenderungen"]})["min_eur"]
    check(len(e1["aenderungen"]) == 1 and m_suche > m_eins + 1e-6, f"besser als ein Zug allein ({m_eins:.0f} → {m_suche:.0f} €)")
    check(m_suche >= m_gier - 1e-6, f"mindestens so gut wie Greedy/Breite 1 ({m_gier:.0f} vs {m_suche:.0f} €)")

    # ── 2 alle Regeln in der Kombination ─────────────────────────────────────────────────────────────────────────────────────
    starts = {p["plan_id"]: neu.get(p["plan_id"], p["start_min"]) for p in longs}
    by = {p["plan_id"]: p for p in longs}
    verstoss = []
    for i in starts:
        for k in starts:
            if i >= k:
                continue
            pi, pk, d = by[i], by[k], abs(starts[i] - starts[k])
            if pi["user_id"] != pk["user_id"] and pi["firma"] == pk["firma"] and d < a["AP_FIRMA_ABSTAND_MIN"]:
                verstoss.append(("Firma", i, k, d))
            if pi["user_id"] == pk["user_id"] and d < a["AP_ABSTAND_ID_MIN"]:
                verstoss.append(("ID", i, k, d))
            if pi["user_id"] == pk["user_id"] and pi["firma"] == pk["firma"] and d < a["AP_ABSTAND_ID_FIRMA_MIN"]:
                verstoss.append(("ID×Firma", i, k, d))
    check(not verstoss, f"Kombination hält Firmen-Abstand, VOLLE Abstände je ID (20) und je ID × Firma (60) (Verstöße {verstoss})")
    check(all(JETZT + a["AP_VORZIEHEN_AB_MIN"] <= neu[i] <= JETZT + 61 for i in neu), f"vorgezogen in die nächsten 60 min ({sorted(neu.values())})")
    # Gegenhedge: ein Short einer anderen ID bei Tradeify steht in 20 min → kein Tradeify-Long daneben
    mit_s = longs + [plan("s_tf", "emin", "tradeify", "sell", JETZT + 20, aenderbar=False, fest_durch="Handplan", einsatz_abs=10.0,
                          satz_eur_je_usd=0.001)]
    eh = U(mit_s, 0.0, 0.0, JETZT, Z, 25, random.Random(1), einsatz=EK, dubai_min=120, id_fest=fest)
    gh = [x for x in eh["aenderungen"] if by.get(x["plan_id"], {}).get("firma") == "tradeify"
          and abs(x["nach_start_min"] - (JETZT + 20)) <= a["AP_GEGEN_FIRMA_MIN"]]
    check(not gh, f"kein Tradeify-Long ≤ {a['AP_GEGEN_FIRMA_MIN']} min neben dem Short einer anderen ID ({[(x['plan_id'], x['nach_start_min']) for x in gh]})")

    # ── 3 Hinausschieben: ein Short in den nächsten 60 min verschärft die Klippe rechts ──────────────────────────────────────────
    sh = [plan("s1", "jacob", "the5ers", "sell", JETZT + 30, usd_pro_pkt=80.0, satz_eur_je_usd=0.08)]
    es = U(sh, 0.0, 0.0, JETZT, Z, 25, random.Random(1), einsatz=EK, dubai_min=120, id_fest={"jacob|the5ers": {"richtung": "sell"}})
    x = es["aenderungen"][0] if es["aenderungen"] else {}
    check(x.get("plan_id") == "s1" and x.get("nach_start_min", 0) > JETZT + 60 and "hinausgeschoben" in x.get("grund", ""),
          f"Short aus den 60 min hinausgeschoben ({x.get('nach_start_min')}, {x.get('grund', '')[:60]})")
    ek_ = U(sh, 0.0, 0.0, JETZT, Z, 25, random.Random(1), einsatz=EK, dubai_min=120, id_fest={"jacob|the5ers": {"richtung": "sell"}},
            hinaus_heute={"s1"})
    check(not ek_["aenderungen"], "kein Kriechen: heute schon hinausgeschoben → nicht noch einmal hinausschieben (Ina Apex 08:43 → 08:47)")
    ep = U(sh, 0.0, 0.0, JETZT, Z, 25, random.Random(1), einsatz=EK, dubai_min=120, id_fest={"jacob|the5ers": {"richtung": "sell"}},
           vorgezogen_heute={"s1"})
    check(not ep["aenderungen"], "Pingpong: heute vorgezogen → nicht hinausschieben")
    eh2 = U(longs, 0.0, 0.0, JETZT, Z, 25, random.Random(1), einsatz=EK, dubai_min=120, id_fest=fest, hinaus_heute={p["plan_id"] for p in longs})
    check(not eh2["aenderungen"], "Pingpong: heute hinausgeschoben → nicht wieder vorziehen")

    # ── 4 nie: Hand-Plan, toter PC, ruhend; ein Zug je Plan ──────────────────────────────────────────────────────────────────
    gesperrt = [dict(longs[0], aenderbar=False, fest_durch="Werte von Hand"), longs[1], longs[2]]
    e4 = U(gesperrt, 0.0, 0.0, JETZT, Z, 25, random.Random(1), einsatz=EK, dubai_min=120, id_fest=fest,
           pc_lebt={"chris", "aurel"}, zuletzt={"l2": JETZT - 5})
    check(not e4["aenderungen"], f"Hand-Plan, toter PC (Ina), ruhender Plan (Moritz) → kein Zug ({[x['plan_id'] for x in e4['aenderungen']]})")
    doppelt = 0
    for seed in range(20):
        ee = U(longs, 0.0, 0.0, JETZT, Z, 25, random.Random(seed), einsatz=EK, dubai_min=120)
        doppelt += any(v > 1 for v in collections.Counter(x["plan_id"] for x in ee["aenderungen"]).values())
    check(doppelt == 0, f"20 Seeds ohne Richtungsschutz (Drehen erlaubt): kein Plan zweimal ({doppelt})")

    # ── 5 Laufzeit und Ruhe ──────────────────────────────────────────────────────────────────────────────────────────────────
    viele = [plan(f"v{k}", f"u{k % 7}", ["tradeify", "fundednext", "topstep", "apex", "fundingpips"][k % 5], "buy" if k % 3 else "sell",
                  230 + 17 * k) for k in range(40)]
    t0 = time.time()
    U(viele, 0.0, 0.0, JETZT, Z, 25, random.Random(1), einsatz=EK, dubai_min=120)
    dt = time.time() - t0
    check(dt < 3.0, f"40 Pläne: ein Lauf in {dt:.2f} s (< 3 s)")
    ruhig = [{"richtung": "sell", "satz": 0.09, "usd_pro_pkt": 100.0, "wert": 9999.0, "polster_usd": 1e6, "tp_punkte": None},
             {"richtung": "buy", "satz": 0.09, "usd_pro_pkt": 100.0, "wert": 9999.0, "polster_usd": 1e6, "tp_punkte": None}]
    e5 = U(longs, 0.0, 0.0, JETZT, Z, 25, random.Random(1), einsatz=dict(EK, szenario_laufend=ruhig), id_fest=fest)
    check(not e5["aenderungen"], "ausgeglichenes Buch → kein Zug")

    # ── 6 Fenster-übergreifend (Schalter ausgleich.fenster_uebergreifend, Master/Finn 08.10.2026) — Lage wie im Trockenlauf 04:06 UTC:
    # Buch leicht long (+3,8 €/Pkt, −112 € bei NQ −30), vormittags nur Longs geplant, die Shorts liegen im Nachmittagsfenster ab 14:30 dt
    lauf_l = [{"richtung": "buy", "satz": 0.0378, "usd_pro_pkt": 100.0, "wert": 9999.0, "polster_usd": 1e6, "tp_punkte": None}]
    EKf = {"basis": 0.0, "brutto": 0.0, "gross_ab": 100000.0, "laufzeit": 180, "szenario_laufend": lauf_l}
    jf = 366.0                                                    # 06:06 dt
    vm = [plan("i_tf", "u-i", "tradeify", "buy", 468, usd_pro_pkt=40.0, satz_eur_je_usd=0.05),
          plan("c_fn", "u-c", "fundednext", "buy", 615, usd_pro_pkt=28.0, satz_eur_je_usd=0.05)]
    nm = [plan("a_fn", "u-a", "fundednext", "sell", 900, usd_pro_pkt=25.0, satz_eur_je_usd=0.08, route="mt5v2"),
          plan("c_ts", "u-c", "topstep", "sell", 989, usd_pro_pkt=40.0, satz_eur_je_usd=0.05)]
    fest_f = {f"{p['user_id']}|{p['firma']}": {"richtung": p["richtung"]} for p in vm + nm}
    Lf = lambda zus: L(lauf_l + [T(dict(p, start_min=zus.get(p["plan_id"], p["start_min"])), False) for p in vm + nm  # noqa: E731
                                 if jf <= zus.get(p["plan_id"], p["start_min"]) <= jf + 60])
    # seit 08.10.2026 (Finn: Opening-Anteil laut Zeitfenster halten): im Nachmittagsfenster 4 weitere feste Pläne → Überschuss 2 über dem Soll
    fueller = [plan(f"f{k}", f"u-f{k}", "apex", "buy", 900 + 12 * k, aenderbar=False, fest_durch="Handplan", satz_eur_je_usd=0.00001)
               for k in range(4)]
    aus = U(vm + nm + fueller, 0.0, 0.0, jf, Z, 25, random.Random(1), einsatz=EKf, dubai_min=120, id_fest=fest_f)
    an = U(vm + nm + fueller, 0.0, 0.0, jf, Z, 25, random.Random(1), einsatz=dict(EKf, fenster_uebergreifend=True), dubai_min=120,
           id_fest=fest_f)
    knapp = U(vm + nm, 0.0, 0.0, jf, Z, 25, random.Random(1), einsatz=dict(EKf, fenster_uebergreifend=True), dubai_min=120, id_fest=fest_f)
    check(not knapp["aenderungen"], "Fenster-Anteil: 2 vormittags / 2 im Opening bei 50/50 → nichts aus dem Opening ziehen (Finn 08.10.2026)")
    eins = U(vm + nm + fueller[:2], 0.0, 0.0, jf, Z, 25, random.Random(1), einsatz=dict(EKf, fenster_uebergreifend=True), dubai_min=120,
             id_fest=fest_f)
    check(len(eins["aenderungen"]) == 1, f"Überschuss 1 im Opening → genau ein Zug über die Fenstergrenze ({[x['plan_id'] for x in eins['aenderungen']]})")
    zus = {x["plan_id"]: x["nach_start_min"] for x in an["aenderungen"]}
    vor_f, nach_f = Lf({}), Lf(zus)
    check(not aus["aenderungen"] and vor_f["min_eur"] < -100, f"Schalter aus: Fenstergrenze hält, kein Zug (min ±30 {vor_f['min_eur']:.0f} €)")
    check(sorted(zus) == ["a_fn", "c_ts"] and all(jf + 3 <= m <= jf + 60 for m in zus.values())
          and all("über Fenster" in x["grund"] for x in an["aenderungen"]),
          f"Schalter an: beide Nachmittags-Shorts über die Fenstergrenze in die nächsten 60 min ({zus})")
    check(nach_f["min_eur"] > vor_f["min_eur"] + 90 and abs(nach_f["delta_eur_pkt"]) < 1.0,
          f"schlimmster Fall {vor_f['min_eur']:.0f} → {nach_f['min_eur']:.0f} €, Delta {vor_f['delta_eur_pkt']:+.1f} → {nach_f['delta_eur_pkt']:+.1f} €/Pkt")
    gh_f = U(vm + nm + [plan("x_fn", "u-x", "fundednext", "buy", 380, aenderbar=False, fest_durch="Handplan", satz_eur_je_usd=0.0001)],
             0.0, 0.0, jf, Z, 25, random.Random(1), einsatz=dict(EKf, fenster_uebergreifend=True), dubai_min=120, id_fest=fest_f)
    check(not any(x["plan_id"] == "a_fn" for x in gh_f["aenderungen"]),
          "Schalter an: Gegenhedge über die Laufzeit gilt weiter (FN-Buy einer anderen ID 06:20 dt → FN-Short nicht daneben)")
    pv_f = U(nm, 0.0, 0.0, jf, Z, 25, random.Random(1), einsatz=dict(EKf, fenster_uebergreifend=True), dubai_min=120, id_fest=fest_f,
             pc_lebt={"u-c"})
    check(not any(x["plan_id"] == "a_fn" for x in pv_f["aenderungen"]), "Schalter an: toter PC → nicht vorgezogen")
    # Ina-Fall (Master 08.10.2026): zwei Shorts derselben ID × Firma im Nachmittag — vorgezogen nie enger als 60 min (keine ¼-Stufe)
    ina = [plan("i1", "u-n", "fundednext", "sell", 890, usd_pro_pkt=25.0, satz_eur_je_usd=0.08, route="mt5v2"),
           plan("i2", "u-n", "fundednext", "sell", 960, usd_pro_pkt=25.0, satz_eur_je_usd=0.08, route="mt5v2")]
    eng_n = 0
    for seed in range(15):
        ei = U(ina, 0.0, 0.0, jf, Z, 25, random.Random(seed), einsatz=dict(EKf, fenster_uebergreifend=True), dubai_min=120,
               id_fest={"u-n|fundednext": {"richtung": "sell"}})
        zi = {p["plan_id"]: p["start_min"] for p in ina}
        zi.update({x["plan_id"]: x["nach_start_min"] for x in ei["aenderungen"]})
        eng_n += abs(zi["i1"] - zi["i2"]) < a["AP_ABSTAND_ID_FIRMA_MIN"]
    check(eng_n == 0, f"Ina-Fall: zwei Shorts derselben ID × Firma nach dem Vorziehen nie enger als 60 min (15 Seeds, {eng_n} zu eng)")
    # Deckel je ID und Tag (Finn: „ab und zu mal ein, zwei Orders verschieben")
    voll = U(vm + nm + fueller, 0.0, 0.0, jf, Z, 25, random.Random(1), einsatz=dict(EKf, fenster_uebergreifend=True), dubai_min=120,
             id_fest=fest_f, zuege_heute={"u-a": a["AP_BOT_ZUEGE_JE_ID_TAG"], "u-c": a["AP_BOT_ZUEGE_JE_ID_TAG"]})
    check(not voll["aenderungen"], f"Deckel: beide IDs haben heute schon {a['AP_BOT_ZUEGE_JE_ID_TAG']} Züge → kein Zug")
    halb = U(vm + nm + fueller, 0.0, 0.0, jf, Z, 25, random.Random(1), einsatz=dict(EKf, fenster_uebergreifend=True), dubai_min=120,
             id_fest=fest_f, zuege_heute={"u-c": a["AP_BOT_ZUEGE_JE_ID_TAG"]})
    check([x["plan_id"] for x in halb["aenderungen"]] == ["a_fn"], f"Deckel nur bei Chris → nur Aurels Short ({[x['plan_id'] for x in halb['aenderungen']]})")
    gesp = U(vm + nm + fueller, 0.0, 0.0, jf, Z, 25, random.Random(1), einsatz=dict(EKf, fenster_uebergreifend=True), dubai_min=120,
             id_fest=fest_f, zuege_gesperrt=True)
    check(not gesp["aenderungen"], "Fail-safe: Protokoll nicht lesbar (zuege_gesperrt) → keine Ausgleichs-Züge")
    zj = a["ap_zuege_je_id"]([
        {"quelle": "bot", "user_id": "u1", "um": "2026-10-08T04:30:54", "firma": "FundedNext", "grund": "Ausgleich: Short vorgezogen …"},
        {"quelle": "bot", "user_id": "u1", "um": "2026-10-08T04:30:54", "firma": "FundedNext", "grund": "Ausgleich: gedreht …"},
        {"quelle": "bot", "user_id": "u1", "um": "2026-10-08T04:40:00", "firma": "Tradeify", "grund": "Netto-Einsatz …: Tranche …"},
        {"quelle": "bot", "user_id": "u1", "um": "2026-10-08T04:50:00", "firma": "Tradeify", "grund": "Verteilung: …"},
        {"quelle": "bot", "user_id": "u1", "um": "2026-10-08T05:00:00", "firma": "Tradeify", "grund": "Ausgleich: Vorziehen verpufft …"},
        {"quelle": "hand", "user_id": "u1", "um": "2026-10-08T05:10:00", "firma": "Tradeify", "grund": "Master: …"}])
    check(zj == {"u1": 2}, f"Zählung je ID: Lauf × Firma = ein Zug, ohne Verteilung/Rückfall/Hand ({zj})")
    pa = a["ap_ausgleich_param"]
    check(pa({})["fenster_uebergreifend"] is False and pa({"ausgleich": {"fenster_uebergreifend": "ja"}})["fenster_uebergreifend"] is False
          and pa({"ausgleich": {"fenster_uebergreifend": True}})["fenster_uebergreifend"] is True,
          "Regel: nur echtes true schaltet ein, Standard aus")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
