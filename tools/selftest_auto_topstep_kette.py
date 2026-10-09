#!/usr/bin/env python3
"""Selbsttest TOPSTEP-KETTE (app.py ap_kette_*, ap_konto_rechnen, ap_zeiten_verteilen, 08.10.2026, Slave-Terminal 3 — Finn: je Konto und
Tag am Ende nur „+4.500 $" oder geblowt, aber in ZWEI Trades; Konzept als Baum bestätigt).

Aufruf:  python3 tools/selftest_auto_topstep_kette.py
Ohne Netz, Platzhalter-IDs. Seit DLL 3.000 (Finn 08.10.2026 ~21:55 Dubai): Trade 1 SL 1.250–1.750 / TP 1.950–2.650 $, Verlustgrenze
min(3.000, Tagesstart − MLL) + 200 = 3.200; MLL EOD-trailing 4.500, Lock 150.000 (ap_kette_mll); angefressen (Abstand MLL < 3.000) seit
Weg B (Finn 08.10.2026 ~22:15 Dubai): unter 150.000 Reparatur-Tag (Tagesziel 150.000 − Balance + Puffer, Verlustgrenze Abstand + 200,
T1-SL/TP gedeckelt, T2 aus dem Block, T1 am MLL = blown), ab 150.000 normal mit Verlustgrenze Abstand + 200, Balance ≤ MLL = geblowt;
Abhaken: Reparatur-Tag am MLL = blown, Plausibilität bei kleinem Abstand; Finns Beispiel −1.250 → TP2 5.750 / SL2 1.950; Abhaken: −3.000 = Tageslimit (nicht blown), MLL = blown; Kette ohne
daily_usd rechnet wie bisher (DD + 200). Vorher: Trade 1 (00:00–11:00 dt, SL/TP 1.950–2.650 $, 3–4 NQ, Tagesziel 4.500, Verlustgrenze 4.700);
Trade 1 2–3 NQ, Trade 2 3–4 NQ; Finns Beispiele für Trade 2 (−2.500 → TP 7.000 / SL 2.200; +2.500 → TP 2.000 / SL 7.200); zweiter Tag (154.500, Rest 4.500 + Puffer);
Blow / Tagesziel schon erreicht → kein Trade 2; nur genaue Puls-Nachlesung in TopstepX zählt; ap_kette_tick legt Trade 2 an (Start ≥ Ende
+ 5 min und ≥ 11:00, ≤ 19:30 dt, Bestätigung geerbt, nie doppelt, ohne Nachlesung nichts), Richtung ohne Gegenhedge über IDs; Trade 1
nur bis 11:00 in ap_zeiten_verteilen; Firmen ohne Kette unverändert."""
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


TOPSTEP = {"namen": ["topstep"], "route": "tsv2", "symbol": "NQ", "boden": "nachziehend", "dd_usd": 4500, "groessen": [150000],
           "ziel_pct": {"challenge": 6}, "planen": True,
           "phasen": {"challenge": {"sl": None, "tp": [4350, 4450], "menge": [2, 3], "dd_usd": 4500, "tp_max": 4500, "ziel_pct": 6,
                                    "menge_schritt": 1, "puffer_je_menge": {"2": [15, 25], "3": [25, 40]}}}}
KETTE = dict(TOPSTEP, kette={})


def main():
    a = sd.lade()
    R = a["ap_konto_rechnen"]

    # ── 1 Trade 1 ─────────────────────────────────────────────────────────────────────────────────────────────────────────
    check(a["ap_kette_regel"](TOPSTEP) is None and a["ap_kette_regel"](KETTE)["tagesziel_usd"] == 4500, "Kette nur mit Block kette, Standardwerte")
    ohne, _ = R(TOPSTEP, "challenge", 150000.0, {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5})
    check(ohne["sl"] is None and ohne["tp"] >= 4350 and "kette" not in ohne, "ohne Kette: wie bisher ein Trade ohne SL")
    werte = [R(KETTE, "challenge", 150000.0, {"tp": u, "sl": 1 - u, "menge": u, "puffer": u})[0] for u in (0.0, 0.37, 0.81, 0.999)]
    check(all(1950 <= w["tp"] <= 2650 and 1250 <= w["sl"] <= 1750 and w["menge"] in (2, 3) for w in werte)
          and {w["menge"] for w in werte} == {2, 3},
          f"Trade 1 (DLL 3.000): TP 1.950–2.650 $, SL 1.250–1.750 $, 2–3 NQ ({[(w['tp'], w['sl'], w['menge']) for w in werte]})")
    w1 = werte[1]
    check(w1["kette"] == {"nr": 1, "tagesziel": 4500, "verlust_grenze": 3200, "daily_usd": 3000, "mll": 145500.0, "tagesstart_plan": 150000.0,
                          "tag_typ": "erster"}
          and w1["risiko"] == w1["sl"] and "Topstep-Kette 1/2" in w1["stufe"],
          f"Tag 1 frisch (150.000): Tagesziel +4.500, Verlustgrenze 3.200 (DLL + 200), MLL 145.500 ({w1['kette']})")
    w2, _ = R(KETTE, "challenge", 154500.0, {"tp": 0.5, "sl": 0.5, "menge": 0.0, "puffer": 0.5}, peak=154500.0)
    check(4525 <= w2["kette"]["tagesziel"] <= 4540 and w2["kette"]["verlust_grenze"] == 3200 and w2["kette"]["mll"] == 150000.0,
          f"Tag 2 nach T1-Gewinn (154.500): Tagesziel = Rest + Puffer ({w2['kette']['tagesziel']}), Verlustgrenze 3.200, MLL gelockt 150.000")
    wv, _ = R(KETTE, "challenge", 148750.0, {"tp": 0.5, "sl": 0.5, "menge": 0.0, "puffer": 0.5}, peak=150000.0)
    check(wv and wv["kette"]["verlust_grenze"] == 3200 and wv["kette"]["mll"] == 145500.0,
          f"nach Verlusttag 148.750 (Abstand MLL 3.250 ≥ 3.000): Plan mit Verlustgrenze 3.200 ({wv and wv['kette']})")
    # Weg B (Finn 08.10.2026 ~22:15 Dubai): angefressen unter der Startgröße → Reparatur-Tag zurück auf 150.000 + Puffer, Tag endet am MLL
    wa, ga = R(KETTE, "challenge", 147000.0, {"tp": 0.5, "sl": 0.5, "menge": 0.0, "puffer": 0.5}, peak=150000.0)
    ka = (wa or {}).get("kette") or {}
    check(wa and ka.get("tagesziel") == 3000 + wa["puffer"] and 25 <= wa["puffer"] <= 40 and ka.get("verlust_grenze") == 1700
          and ka.get("mll") == 145500.0 and ka.get("reparatur") is True and ka.get("angefressen") is True and ka.get("abstand_mll") == 1500.0
          and wa["sl"] <= 1700 and wa["tp"] <= ka["tagesziel"] and wa["risiko"] == wa["sl"],
          f"Reparatur 147.000 / MLL 145.500: Tagesziel 3.000 + Puffer, Verlustgrenze 1.700 (Abstand + 200), T1-SL ≤ 1.700, T1-TP ≤ Tagesziel ({ga or ka})")
    check(wa and wa["stufe"] == f"Topstep-Kette 1/2 (Reparatur auf 150.000: +{ka['tagesziel']:,} $)".replace(",", "."),
          f"Stufe erkennbar im Planer: „{wa and wa['stufe']}“")
    ws, _ = R(KETTE, "challenge", 147000.0, {"tp": 0.5, "sl": 0.999, "menge": 0.0, "puffer": 0.5}, peak=150000.0)
    check(ws and ws["sl"] == 1700 and ws["risiko"] == 1700, f"T1-SL 1.750 > Verlustgrenze 1.700 → SL = 1.700 ({ws and ws['sl']})")
    wk, _ = R(KETTE, "challenge", 149000.0, {"tp": 0.5, "sl": 0.5, "menge": 0.0, "puffer": 0.0}, peak=151500.0)
    check(wk and wk["kette"]["tagesziel"] == 1025 and wk["tp"] == 1025 and wk["kette"]["verlust_grenze"] == 2200
          and "Reparatur auf 150.000: +1.025 $" in wk["stufe"],
          f"Reparatur 149.000 / MLL 147.000 (Grenzfall 150k − MLL = 3.000): Tagesziel 1.025 < T1-TP 2.300 → T1-TP = Tagesziel ({wk and (wk['tp'], wk['kette'], wk['stufe'])})")
    # Master 08.10.2026 (Nachbesserung zu cc7a857): Reparatur nur, wenn 150.000 den Abstand zurückbringt (Startgröße − MLL ≥ DLL)
    wm, gm = R(KETTE, "challenge", 149900.0, {"tp": 0.5, "sl": 0.5, "menge": 0.0, "puffer": 0.5}, peak=153000.0)
    km = (wm or {}).get("kette") or {}
    check(wm and km.get("tagesziel") == 4500 and km.get("verlust_grenze") == 1600 and km.get("mll") == 148500.0 and km.get("angefressen") is True
          and "reparatur" not in km and wm["stufe"] == "Topstep-Kette 1/2 (Tagesziel +4.500 $)" and wm["sl"] <= 1600,
          f"149.900 / Höchststand 153.000 (MLL 148.500, 150k − MLL 1.500 < 3.000) → keine Reparatur, normal 4.500, Verlustgrenze 1.600 ({gm or (wm['stufe'], km)})")
    wr, gr = R(KETTE, "challenge", 148000.0, {"tp": 0.5, "sl": 0.5, "menge": 0.0, "puffer": 0.5}, peak=151000.0)
    kr_ = (wr or {}).get("kette") or {}
    check(wr and kr_.get("reparatur") is True and kr_.get("mll") == 146500.0 and kr_.get("tagesziel") == 2000 + wr["puffer"]
          and kr_.get("verlust_grenze") == 1700 and "Reparatur auf 150.000" in wr["stufe"],
          f"148.000 / Höchststand 151.000 (MLL 146.500, 150k − MLL 3.500 ≥ 3.000) → Reparatur +2.000 + Puffer ({gr or (wr['stufe'], kr_)})")
    # ab der Startgröße (MLL gelockt bei 150.000): normal weiter, Verlustgrenze = Abstand + 200
    wn, gn = R(KETTE, "challenge", 151500.0, {"tp": 0.5, "sl": 0.999, "menge": 0.0, "puffer": 0.5}, peak=154500.0)
    kn = (wn or {}).get("kette") or {}
    check(wn and kn.get("tagesziel") == 4500 and kn.get("verlust_grenze") == 1700 and kn.get("mll") == 150000.0 and wn["sl"] == 1700
          and kn.get("angefressen") is True and "reparatur" not in kn and wn["stufe"] == "Topstep-Kette 1/2 (Tagesziel +4.500 $)",
          f"151.500 / MLL 150.000 (gelockt): normal 4.500, Verlustgrenze 1.700, T1-SL gedeckelt ({gn or (wn['sl'], kn, wn['stufe'])})")
    wb, gb = R(KETTE, "challenge", 150000.0, {"tp": 0.5, "sl": 0.5, "menge": 0.0, "puffer": 0.5}, peak=152000.0)
    check(wb and wb["kette"]["tagesziel"] == 4500 and wb["kette"]["verlust_grenze"] == 2700 and wb["kette"]["mll"] == 147500.0
          and not wb["kette"].get("reparatur"),
          f"Höchststand 152.000, jetzt 150.000 (= Startgröße) → MLL 147.500, normal mit Verlustgrenze 2.700 ({gb or wb['kette']})")
    wg, gg = R(KETTE, "challenge", 147400.0, {"tp": 0.5, "sl": 0.5, "menge": 0.0, "puffer": 0.5}, peak=152000.0)
    check(wg is None and gg == "Balance 147.400 auf/unter dem MLL 147.500 — geblowt?", f"Balance unter dem nachgezogenen MLL → geblowt, kein Plan ({gg})")
    check(a["ap_kette_mll"](150000, 4500, None, 150000) == 145500.0 and a["ap_kette_mll"](150000, 4500, 156000, 151000) == 150000.0
          and a["ap_kette_mll"](150000, 4500, 152000, 150000) == 147500.0, "MLL: frisch 145.500, gelockt 150.000, nachgezogen 147.500")
    ALT = dict(TOPSTEP, kette={"daily_usd": 0, "t1_sl": [1950, 2650]})
    wo, _ = R(ALT, "challenge", 147000.0, {"tp": 0.5, "sl": 0.5, "menge": 0.0, "puffer": 0.5}, peak=150000.0)
    check(wo and wo["kette"] == {"nr": 1, "tagesziel": 4500, "verlust_grenze": 4700, "tag_typ": "normal"} and 1950 <= wo["sl"] <= 2650,
          f"Kette ohne daily_usd: wie bisher (Verlustgrenze 4.700, kein angefressen) ({wo and wo['kette']})")
    w3, _ = R(KETTE, "challenge", 157500.0, {"tp": 0.9, "sl": 0.5, "menge": 0.0, "puffer": 0.0})
    # TAG-TYP für die Spalte „Schritt" im Trade Plan (09.10.2026): erster / reparatur / final / normal — nur Anzeige
    check([x and x["kette"].get("tag_typ") for x in (w1, wa, w2, w3, wv, wb, wn, wm)]
          == ["erster", "reparatur", "final", "final", "normal", "normal", "normal", "normal"],
          f"Tag-Typ: frisch erster, 147.000 Reparatur, 154.500/157.500 final (Rest ≤ 4.500), 148.750/150.000 nach Höchststand/151.500/149.900 normal "
          f"({[x and x['kette'].get('tag_typ') for x in (w1, wa, w2, w3, wv, wb, wn, wm)]})")
    check(w3["tp"] == w3["kette"]["tagesziel"] == 1525, f"Rest kleiner als TP von Trade 1: Trade 1 holt das Ziel allein (TP {w3['tp']})")

    # ── 2 Trade 2 aus dem Ergebnis von Trade 1 (Finns Beispiele) ──────────────────────────────────────────────────────────────
    T2 = lambda k, b0, b1: a["ap_kette_trade2"](k, b0, b1, KETTE, a["ap_kette_regel"](KETTE), 0.3)   # noqa: E731
    k1 = {"nr": 1, "tagesziel": 4500, "verlust_grenze": 4700}
    v, _ = T2(k1, 150000, 147500)
    check((v["tp"], v["sl"], v["e1"]) == (7000, 2200, -2500.0) and v["menge"] in (3, 4), f"SL −2.500 → TP 7.000 / SL 2.200, Trade 2 3–4 NQ ({v})")
    check({a["ap_kette_trade2"](k1, 150000, 147500, KETTE, a["ap_kette_regel"](KETTE), u_)[0]["menge"] for u_ in (0.0, 0.99)} == {3, 4},
          "Trade 2: 3–4 NQ (t2_menge), Trade 1 2–3 NQ (menge) — Finn 08.10.2026")
    v, _ = T2(k1, 150000, 152500)
    check((v["tp"], v["sl"]) == (2000, 7200), f"TP +2.500 → TP 2.000 / SL 7.200 ({v['tp']} / {v['sl']})")
    v, _ = T2({"nr": 1, "tagesziel": 4530, "verlust_grenze": 4700}, 154500, 152000)
    check((v["tp"], v["sl"]) == (7030, 2200), f"Tag 2: −2.500 → TP 7.030 / SL 2.200 ({v['tp']} / {v['sl']})")
    check(T2(k1, 150000, 145400)[0] is None and "geblowt" in T2(k1, 150000, 145400)[1], "Trade 1 geblowt → kein Trade 2")
    check(T2(k1, 150000, 154480)[0] is None and "Tagesziel" in T2(k1, 150000, 154480)[1], "Tagesziel schon erreicht → kein Trade 2")
    check(T2(k1, 0, 147500)[0] is None and "unplausibel" in T2(k1, 0, 147500)[1], "Start relativ, Ende absolut → unplausibel, kein Trade 2")
    # DLL 3.000 (Finn 08.10.2026): Trade 1 aus dem Planer trägt mll/daily_usd
    kd = {"nr": 1, "tagesziel": 4500, "verlust_grenze": 3200, "daily_usd": 3000, "mll": 145500.0}
    v, _ = T2(kd, 150000, 148750)
    check((v["tp"], v["sl"]) == (5750, 1950) and v["mll"] == 145500.0, f"Finns Beispiel: T1 −1.250 → TP2 5.750 / SL2 1.950, schlimmster Tag −3.000 ({v['tp']} / {v['sl']})")
    v, _ = T2(kd, 150000, 152000)
    check((v["tp"], v["sl"]) == (2500, 5200), f"T1 +2.000 → TP2 2.500 / SL2 5.200 (Tag endet am DLL bzw. MLL) ({v['tp']} / {v['sl']})")
    v, _ = T2(dict(kd, tagesziel=1525), 157500, 156000)
    check((v["tp"], v["sl"]) == (3025, 1700), f"letzter Tag (Rest 1.525): T1 −1.500 → TP2 3.025 / SL2 1.700 ({v['tp']} / {v['sl']})")
    g = T2(kd, 150000, 145490)
    check(g[0] is None and "MLL geblowt" in g[1], f"T1 bis unter den MLL → geblowt, kein Trade 2 ({g[1]})")
    g = T2(kd, 150000, 147000)
    check(g[0] is None and "Tageslimit" in g[1], f"T1 −3.000 (DLL) → Tageslimit, kein Trade 2 ({g[1]})")
    # Weg B: Trade 2 eines Reparatur-Tags (Tagesziel 3.030, Verlustgrenze 1.700) aus dem Kette-Block von Trade 1
    kr = {"nr": 1, "tagesziel": 3030, "verlust_grenze": 1700, "daily_usd": 3000, "mll": 145500.0, "tagesstart_plan": 147000.0,
          "angefressen": True, "abstand_mll": 1500.0, "reparatur": True}
    v, g = T2(kr, 147000, 146000)
    check(v and (v["tp"], v["sl"]) == (4030, 700) and v.get("angefressen") is True and v.get("reparatur") is True and v.get("mll") == 145500.0,
          f"Reparatur: T1 −1.000 → TP2 = Tagesziel + 1.000 = 4.030, SL2 700, Einstufung geerbt ({g or v})")
    v, g = T2(kr, 147000, 148500)
    check(v and (v["tp"], v["sl"]) == (1530, 3200), f"Reparatur: T1 +1.500 → TP2 1.530 / SL2 3.200 ({g or (v['tp'], v['sl'])})")
    g = T2(kr, 147000, 145500)
    check(g[0] is None and "MLL geblowt" in g[1], f"Reparatur: T1 am MLL (145.500) → blown, kein Trade 2 ({g[1]})")
    g = T2(kr, 147000, 145300)
    check(g[0] is None and "MLL geblowt" in g[1], f"Reparatur: T1 am SL 1.700 (hinter dem MLL) → blown, kein Trade 2 ({g[1]})")
    g = T2(kr, 147000, 145520)
    check(g[0] is None and "MLL geblowt" in g[1], f"Reparatur: T1 −1.480 (20 $ über MLL, Toleranz 50) → blown, kein Trade 2 ({g[1]})")
    v, g = T2(kr, 147000, 145560)
    check(v and (v["tp"], v["sl"]) == (4470, 260), f"Reparatur: T1 −1.440 (60 $ über MLL) → lebt, TP2 4.470 / SL2 260 ({g or v})")
    v, g = T2(kd, 150000, 145530)
    check(g and "MLL" not in g and "Tageslimit" in g, f"gesund: T1 30 $ über dem MLL → keine Toleranz, Tageslimit statt Blow ({g})")
    ang = a["ap_kette_angefressen"]
    check(ang(kr) and ang({"verlust_grenze": 1700, "daily_usd": 3000, "mll": 145500}) and not ang(kd)
          and not ang({"verlust_grenze": 4700}) and not ang(None) and not ang(dict(kr, angefressen=False)),
          "ap_kette_angefressen: Flag, sonst aus Verlustgrenze < DLL + 200 abgeleitet; gesund/ohne DLL → nein")
    fertig = a["ap_kette_t1_fertig"]
    gut = {"mt5_baseline": {"tv": {"balance_start": 150000}, "final": {"balance_end": 147500, "quelle": "puls", "plattform": "tsx"}}}
    check(fertig(gut) == ((150000.0, 147500.0), None), "genaue Puls-Nachlesung in TopstepX → fertig")
    check(fertig({"mt5_baseline": {"tv": {"balance_start": 150000}, "final": {"balance_end": 147500, "quelle": "hand"}}})[0] is None
          and fertig({"mt5_baseline": {"tv": {"balance_start": 150000}, "final": {"balance_end": 147500, "quelle": "puls", "plattform": "tsx",
                                                                                  "balance_quelle": "folgetrade"}}})[0] is None
          and fertig({"mt5_baseline": {"final": {"balance_end": 1, "quelle": "puls", "plattform": "tsx"}}})[0] is None,
          "Hand-Ende, Folgetrade-Wert oder ohne Start-Balance → wartet")

    # ── 3 ap_kette_tick: Trade 2 anlegen ──────────────────────────────────────────────────────────────────────────────────
    BER = ZoneInfo("Europe/Berlin")
    jetzt = datetime(2026, 10, 9, 10, 2, tzinfo=BER).astimezone(timezone.utc)          # 10:02 dt, Trade 1 endete 09:58
    mitt = datetime(2026, 10, 9, tzinfo=BER)
    U1, U2 = sd.U1, sd.U2
    t1 = {"id": "00000000-0000-0000-0000-00000000k001", "user_id": U1, "master_account_id": "k-ts", "master_firm": "Topstep",
          "master_name": "TS-000000", "master_symbol": "NQZ6", "richtung": "buy", "auto_plan": True, "auto_bestaetigt_at": "2026-10-08T22:00:00Z",
          "ended_at": (mitt + timedelta(hours=9, minutes=58)).isoformat(), "planned_for": "2026-10-09", "status": "review",
          "mt5_baseline": {"kette": dict(k1, tag_typ="normal"), "tv": {"balance_start": 150000}, "final": {"balance_end": 147500, "quelle": "puls", "plattform": "tsx"}}}
    zustand = {"t1": [t1], "t2": [], "ins": []}
    andere = []

    def sb_select(table, params):
        if table == "auto_plan_regeln":
            return [{"id": 1, "zeiten": {"tz": "Europe/Berlin", "fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30"},
                     "regeln": {"firmen": [KETTE], "ausgleich": {"laufzeit_min": 180}}}]
        if table == "trade_plans" and params.get("route") == "eq.tsv2":
            return [dict(x) for x in zustand["t1"]]
        if table == "trade_plans" and "mt5_baseline->kette->>vor" in params:
            return [{"id": "x", "vor": x["mt5_baseline"]["kette"]["vor"]} for x in zustand["ins"]]
        return []

    def stand_laden(reg, j=None, *a_, **k_):
        jm = (j - mitt).total_seconds() / 60.0
        return {"mitternacht": mitt, "jetzt_min": jm, "zeiten": reg["zeiten"], "offen": [], "geplant": list(andere), "folgetag": [],
                "starts_heute": [{"user_id": U1, "firma": "topstep", "start": 400.0, "richtung": "buy"}], "id_fest": {}, "firmen": [KETTE]}
    a["sb_select"] = sb_select
    a["requests"] = __import__("requests")
    a["sb_insert"] = lambda t, z: zustand["ins"].append(z) or z
    gruende_db = []
    a["_ap_kette_grund"] = lambda t1_, g: gruende_db.append((t1_["id"], g))
    a["_ap_stand_laden"] = stand_laden
    erg = a["ap_kette_tick"](jetzt, random.Random(3))
    z = zustand["ins"][0] if zustand["ins"] else {}
    st = datetime.fromisoformat(z.get("start_um", "2000-01-01T00:00:00+00:00")).astimezone(BER) if z else None
    check(len(zustand["ins"]) == 1 and (z["master_tp"], z["master_sl"]) == (7000, 2200) and z["route"] == "tsv2"
          and z["mt5_baseline"]["kette"]["nr"] == 2 and z["mt5_baseline"]["kette"]["vor"] == t1["id"] and z["master_contracts"] in (3, 4),
          f"Trade 2 angelegt: TP 7.000 / SL 2.200, Kette 2 nach Trade 1 ({erg.get('neu')})")
    check(st is not None and st.hour * 60 + st.minute >= 11 * 60 and st.hour * 60 + st.minute < 19 * 60 + 30,
          f"Start im Fenster 11:00–19:30 dt ({st.strftime('%H:%M') if st else '—'})")
    check(bool(z.get("auto_bestaetigt_at")) and z.get("auto_plan") is True and "Topstep-Kette 2/2" in z.get("notes", ""),
          "Bestätigung von Trade 1 geerbt, Notiz „Topstep-Kette 2/2“")
    check(any("Trade 2 angelegt" in g for _i, g in gruende_db), "Ergebnis an Trade 1 sichtbar (kette.t2_grund)")
    check(z and z["mt5_baseline"]["kette"].get("tag_typ") == "normal",
          f"Trade 2 erbt den Tag-Typ von Trade 1 ({z and z['mt5_baseline']['kette'].get('tag_typ')})")
    a["ap_kette_tick"](jetzt, random.Random(4))
    check(len(zustand["ins"]) == 1, "zweiter Takt: nie doppelt")
    # Unique-Index meldet 409 (zweiter Container war schneller) → still „schon da", kein Fehler
    class _R:
        status_code = 409
    import requests as _rq
    ins_alt = a["sb_insert"]
    a["sb_insert"] = lambda t, z: (_ for _ in ()).throw(_rq.exceptions.HTTPError(response=_R()))
    zustand.update(ins=[])
    e409 = a["ap_kette_tick"](jetzt, random.Random(5))
    check(e409.get("neu") == [], "409 vom Unique-Index → kein Fehler, nichts doppelt")
    a["sb_insert"] = ins_alt
    zustand.update(ins=[z])
    # ohne genaue Nachlesung: nichts
    zustand.update(t1=[dict(t1, id="00000000-0000-0000-0000-00000000k002", mt5_baseline=dict(t1["mt5_baseline"], final={"quelle": "hand", "balance_end": 147500}))], ins=[])
    e2 = a["ap_kette_tick"](jetzt, random.Random(3))
    check(not zustand["ins"] and "Nachlesung" in " ".join((e2.get("gruende") or {}).values())
          and any("Nachlesung" in g for _i, g in gruende_db), f"ohne genaue Nachlesung kein Trade 2, Grund am Trade 1 ({e2.get('gruende')})")
    # über IDs (seit 08.10.2026 ~17:00 Dubai, Finn: „kann natürlich eine ANDERE ID … short gehen"): andere ID bei Topstep um 11:10 dt
    # SHORT geplant → Trade 2 darf LONG sein, startet aber nie ±AP_GEGEN_FIRMA_MIN (3 min) neben diesem Short
    zustand.update(t1=[t1], ins=[])
    andere[:] = [{"plan_id": "p-x", "user_id": U2, "user": "X", "firma_key": "topstep", "firma": "Topstep", "richtung": "sell", "start_min": 670.0,
                  "delta_abs": 1.0, "aenderbar": False, "fest_durch": "Handplan", "einsatz_abs": 0.0}]
    gegen_ok = True
    for seed in range(12):
        zustand["ins"] = []
        a["ap_kette_tick"](jetzt, random.Random(seed))
        for zz in zustand["ins"]:
            m = (datetime.fromisoformat(zz["start_um"]) - mitt).total_seconds() / 60.0
            if zz["richtung"] == "buy" and abs(m - 670.0) <= a["AP_GEGEN_FIRMA_MIN"]:
                gegen_ok = False
    check(gegen_ok, "Trade 2 nie ±3 min neben einem gegenläufigen Plan einer anderen ID derselben Firma (Laufzeit über IDs frei)")
    # Weg B: Trade 2 zu einem Reparatur-Tag trägt angefressen/reparatur + MLL (Abhaken) und nennt den MLL als Tagesende
    andere[:] = []
    t1r = dict(t1, id="00000000-0000-0000-0000-00000000k003",
               mt5_baseline={"kette": kr, "tv": {"balance_start": 147000}, "final": {"balance_end": 146000, "quelle": "puls", "plattform": "tsx"}})
    zustand.update(t1=[t1r], ins=[])
    a["ap_kette_tick"](jetzt, random.Random(7))
    zr = zustand["ins"][0] if zustand["ins"] else {}
    k2r = (zr.get("mt5_baseline") or {}).get("kette") or {}
    check((zr.get("master_tp"), zr.get("master_sl")) == (4030, 700) and k2r.get("angefressen") is True and k2r.get("reparatur") is True
          and k2r.get("mll") == 145500.0 and k2r.get("verlust_grenze") == 1700 and "oder MLL 145.500 (Blow)" in zr.get("notes", ""),
          f"Reparatur-Trade 2 angelegt: TP 4.030 / SL 700, Kette-Block mit angefressen/reparatur/MLL, Notiz „oder MLL … (Blow)“ ({k2r}, {zr.get('notes')})")
    zustand.update(t1=[t1], ins=[])

    # ── 3b automatisch abhaken (Finn 08.10.2026: nach der Prüfung direkt erledigt, nicht mehr im Radar abhaken) ───────────────
    rev = [dict(t1, id="r-t1", route="tsv2", status="review", updated_at="2026-10-09T08:00:00Z", master_pl=None, konto_typ=None),
           {"id": "r-t2", "route": "tsv2", "status": "review", "user_id": U1, "updated_at": "2026-10-09T13:00:00Z", "ended_at": None,
            "mt5_baseline": {"kette": {"nr": 2, "vor": "r-t1", "verlust_grenze": 4700, "balance_start_tag": 150000},
                             "tv": {"balance_start": 147500}, "final": {"balance_end": 145480, "quelle": "puls", "plattform": "tsx"}}},
           dict(t1, id="r-warte", status="review", mt5_baseline=dict(t1["mt5_baseline"], final={"quelle": "hand", "balance_end": 1})),
           {"id": "r-t2b", "route": "tsv2", "status": "review", "user_id": U1, "updated_at": "y", "ended_at": None,
            "mt5_baseline": {"kette": {"nr": 2, "vor": "r-x", "verlust_grenze": 4700, "tagesziel": 4500, "balance_start_tag": 150000},
                             "tv": {"balance_start": 152650}, "final": {"balance_end": 145480, "quelle": "puls", "plattform": "tsx"}}},
           dict(t1, id="r-relativ", route="tsv2", status="review", updated_at="x",
                mt5_baseline=dict(t1["mt5_baseline"], final={"quelle": "puls", "plattform": "tsx", "balance_end": 2000})),
           # DLL 3.000: Tag endet bei −3.000 (Konto über dem MLL) → Tageslimit, nicht blown; Tag endet am MLL → blown
           {"id": "r-dll", "route": "tsv2", "status": "review", "user_id": U1, "updated_at": "d", "ended_at": None,
            "mt5_baseline": {"kette": {"nr": 2, "vor": "r-x1", "verlust_grenze": 3200, "daily_usd": 3000, "mll": 145500, "balance_start_tag": 150000},
                             "tv": {"balance_start": 148750}, "final": {"balance_end": 147000, "quelle": "puls", "plattform": "tsx"}}},
           {"id": "r-mll", "route": "tsv2", "status": "review", "user_id": U1, "updated_at": "m", "ended_at": None,
            "mt5_baseline": {"kette": {"nr": 2, "vor": "r-x2", "verlust_grenze": 3200, "daily_usd": 3000, "mll": 147500, "balance_start_tag": 151000},
                             "tv": {"balance_start": 149750}, "final": {"balance_end": 147400, "quelle": "puls", "plattform": "tsx"}}},
           # reiner DLL-Tag genau am MLL (Abstand 3.000): −3.000 → Tageslimit, NIE blown (sichere Variante, Prüfung Slave 2)
           {"id": "r-dllmll", "route": "tsv2", "status": "review", "user_id": U1, "updated_at": "dm", "ended_at": None,
            "mt5_baseline": {"kette": {"nr": 2, "vor": "r-x3", "verlust_grenze": 3200, "daily_usd": 3000, "mll": 147500, "balance_start_tag": 150500},
                             "tv": {"balance_start": 149250}, "final": {"balance_end": 147500, "quelle": "puls", "plattform": "tsx"}}},
           # Weg B: Reparatur-Tag (147.000, MLL 145.500) — T1 endet am MLL (Tag −1.500 < DLL + 50) → blown
           {"id": "r-rep1", "route": "tsv2", "status": "review", "user_id": U1, "updated_at": "r1", "ended_at": None,
            "mt5_baseline": {"kette": dict(kr), "tv": {"balance_start": 147000}, "final": {"balance_end": 145500, "quelle": "puls", "plattform": "tsx"}}},
           # Reparatur-Tag, T1 +2.300, T2 läuft in den MLL (eigener P&L −3.800) → plausibel, blown
           {"id": "r-rep2", "route": "tsv2", "status": "review", "user_id": U1, "updated_at": "r2", "ended_at": None,
            "mt5_baseline": {"kette": {"nr": 2, "vor": "r-x4", "tagesziel": 3030, "verlust_grenze": 1700, "daily_usd": 3000, "mll": 145500,
                                       "angefressen": True, "reparatur": True, "balance_start_tag": 147000},
                             "tv": {"balance_start": 149300}, "final": {"balance_end": 145500, "quelle": "puls", "plattform": "tsx"}}},
           # Reparatur-Tag erreicht das Tagesziel (150.030) → erledigt, nicht blown
           {"id": "r-rep3", "route": "tsv2", "status": "review", "user_id": U1, "updated_at": "r3", "ended_at": None,
            "mt5_baseline": {"kette": {"nr": 2, "vor": "r-x5", "tagesziel": 3030, "verlust_grenze": 1700, "daily_usd": 3000, "mll": 145500,
                                       "angefressen": True, "reparatur": True, "balance_start_tag": 147000},
                             "tv": {"balance_start": 146000}, "final": {"balance_end": 150030, "quelle": "puls", "plattform": "tsx"}}},
           # sehr kleiner Abstand (50 → Verlustgrenze 250): T1 +2.300, T2 am MLL mit −2.350 eigenem P&L — früher „unplausibel" (Grenze −2.000)
           {"id": "r-rep4", "route": "tsv2", "status": "review", "user_id": U1, "updated_at": "r4", "ended_at": None,
            "mt5_baseline": {"kette": {"nr": 2, "vor": "r-x6", "tagesziel": 4480, "verlust_grenze": 250, "daily_usd": 3000, "mll": 145500,
                                       "balance_start_tag": 145550},
                             "tv": {"balance_start": 147850}, "final": {"balance_end": 145500, "quelle": "puls", "plattform": "tsx"}}},
           # Toleranz am MLL (Master 08.10.2026): angefressener Tag endet 30 $ über dem MLL → blown; 60 $ darüber → nicht blown
           {"id": "r-tol1", "route": "tsv2", "status": "review", "user_id": U1, "updated_at": "t1", "ended_at": None,
            "mt5_baseline": {"kette": dict(kr), "tv": {"balance_start": 147000}, "final": {"balance_end": 145530, "quelle": "puls", "plattform": "tsx"}}},
           {"id": "r-tol2", "route": "tsv2", "status": "review", "user_id": U1, "updated_at": "t2", "ended_at": None,
            "mt5_baseline": {"kette": dict(kr), "tv": {"balance_start": 147000}, "final": {"balance_end": 145560, "quelle": "puls", "plattform": "tsx"}}},
           # gesunder Tag 30 $ über dem MLL mit Tagesverlust > DLL + 50 → ohne Toleranz NICHT blown
           {"id": "r-tol3", "route": "tsv2", "status": "review", "user_id": U1, "updated_at": "t3", "ended_at": None,
            "mt5_baseline": {"kette": {"nr": 2, "vor": "r-x7", "verlust_grenze": 3200, "daily_usd": 3000, "mll": 147500, "balance_start_tag": 151000},
                             "tv": {"balance_start": 149750}, "final": {"balance_end": 147530, "quelle": "puls", "plattform": "tsx"}}},
           # Balance-Sprung (08.10.2026): Balance −2.500, RP&L des Tages ab dem Klick nur −500 (z. B. Auszahlung dazwischen)
           dict(t1, id="r-sprung", route="tsv2", status="review", updated_at="z",
                mt5_baseline=dict(t1["mt5_baseline"], tv={"balance_start": 150000, "today_pnl_start": 0, "datum_start": "2026-10-09"},
                                  final={"quelle": "puls", "plattform": "tsx", "balance_end": 147500, "today_pnl": -500, "datum": "2026-10-09"}))]
    upds, gruende_ab = [], []
    a["_ap_kette_grund"] = lambda t_, g: gruende_ab.append((t_["id"], g))
    a["sb_select"] = lambda t, prm: [dict(x) for x in rev] if prm.get("status") == "eq.review" else []
    a["sb_update"] = lambda t, f, u: upds.append((f, u)) or [u]
    weg = a["ap_kette_abhaken"](jetzt)
    u1 = next((u for f, u in upds if f["id"] == "eq.r-t1"), {})
    u2 = next((u for f, u in upds if f["id"] == "eq.r-t2"), {})
    check(sorted(weg) == ["r-dll", "r-dllmll", "r-mll", "r-rep1", "r-rep2", "r-rep3", "r-rep4", "r-t1", "r-t2", "r-t2b", "r-tol1", "r-tol2", "r-tol3"]
          and u1.get("status") == "completed" and u1.get("master_pl") == -2500.0
          and u1.get("pl_quelle") == "tv" and u1.get("konto_typ") == "challenge" and not u1.get("blown")
          and all(f.get("status") == "eq.review" and f.get("updated_at") for f, _u in upds),
          f"Trade 1 nach genauer Lesung automatisch erledigt (P&L −2.500, pl_quelle tv, Sperre review/updated_at) — {weg}")
    check(u2.get("master_pl") == -2020.0 and u2.get("blown") is True,
          "Trade 2: −2.020 nach −2.500 = Tag −4.520 → blown (Tag zählt, nicht nur der eigene P&L)")
    u2b = next((u for f, u in upds if f["id"] == "eq.r-t2b"), {})
    check(u2b.get("master_pl") == -7170.0 and u2b.get("blown") is True,
          f"Trade 2 nach +2.650 blowt mit −7.170 eigenem P&L → trotzdem plausibel, abgehakt + blown ({u2b.get('master_pl')})")
    check("eq.r-warte" not in [f["id"] for f, _u in upds], "ohne genaue Puls-Lesung bleibt der Trade in Überprüfen")
    ud = next((u for f, u in upds if f["id"] == "eq.r-dll"), {})
    um = next((u for f, u in upds if f["id"] == "eq.r-mll"), {})
    check(ud.get("status") == "completed" and ud.get("master_pl") == -1750.0 and not ud.get("blown"),
          f"DLL: Tag −3.000 (147.000, MLL 145.500) → erledigt, NICHT blown — Tageslimit ({ud})")
    check(um.get("status") == "completed" and um.get("blown") is True, f"MLL: Tag −3.600 endet bei 147.400 ≤ MLL 147.500 → blown ({um})")
    udm = next((u for f, u in upds if f["id"] == "eq.r-dllmll"), {})
    check(udm.get("status") == "completed" and not udm.get("blown"), f"reiner DLL-Tag (−3.000) genau am MLL → Tageslimit, nicht blown ({udm})")
    ur = {i: next((u for f, u in upds if f["id"] == f"eq.{i}"), {}) for i in ("r-rep1", "r-rep2", "r-rep3", "r-rep4")}
    check(ur["r-rep1"].get("status") == "completed" and ur["r-rep1"].get("master_pl") == -1500.0 and ur["r-rep1"].get("blown") is True,
          f"Reparatur-Tag: T1 endet am MLL (Tag −1.500, unter DLL + 50) → blown ({ur['r-rep1']})")
    check(ur["r-rep2"].get("master_pl") == -3800.0 and ur["r-rep2"].get("blown") is True,
          f"Reparatur-Tag: T2 nach T1 +2.300 am MLL (eigener P&L −3.800) → plausibel, blown ({ur['r-rep2']})")
    check(ur["r-rep3"].get("status") == "completed" and ur["r-rep3"].get("master_pl") == 4030.0 and not ur["r-rep3"].get("blown"),
          f"Reparatur-Tag am Tagesziel (150.030) → erledigt, nicht blown ({ur['r-rep3']})")
    check(ur["r-rep4"].get("master_pl") == -2350.0 and ur["r-rep4"].get("blown") is True
          and not any(i == "r-rep4" and "unplausibel" in g for i, g in gruende_ab),
          f"Abstand 50 (Verlustgrenze 250, ohne Flag abgeleitet): T2 −2.350 am MLL → nicht unplausibel, blown ({ur['r-rep4']})")
    ut = {i: next((u for f, u in upds if f["id"] == f"eq.{i}"), {}) for i in ("r-tol1", "r-tol2", "r-tol3")}
    check(ut["r-tol1"].get("status") == "completed" and ut["r-tol1"].get("blown") is True,
          f"angefressen: Ende 30 $ über dem MLL (Toleranz 50) → blown ({ut['r-tol1']})")
    check(ut["r-tol2"].get("status") == "completed" and not ut["r-tol2"].get("blown"),
          f"angefressen: Ende 60 $ über dem MLL → nicht blown ({ut['r-tol2']})")
    check(ut["r-tol3"].get("status") == "completed" and not ut["r-tol3"].get("blown"),
          f"gesund: Ende 30 $ über dem MLL, Tag −3.470 → ohne Toleranz nicht blown ({ut['r-tol3']})")
    check("eq.r-relativ" not in [f["id"] for f, _u in upds] and any(i == "r-relativ" and "unplausibel" in g for i, g in gruende_ab),
          "Start absolut 150.000, Ende relativ 2.000 → nicht abgehakt, Grund „unplausibel — von Hand abhaken“ (Prüfer Slave 2)")
    check("eq.r-sprung" not in [f["id"] for f, _u in upds] and any(i == "r-sprung" and "Balance-Sprung" in g and "Differenz -2.000" in g for i, g in gruende_ab),
          f"Balance −2.500 · Tages-P&L −500 → nicht abgehakt, Grund „Balance-Sprung … (Auszahlung?)“ ({[g for i, g in gruende_ab if i == 'r-sprung']})")

    # ── 4 Trade 1 nur bis 11:00 dt im Planer ──────────────────────────────────────────────────────────────────────────────
    Z = {"fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30"}
    tr = [{"key": f"u{i}|topstep", "user": f"u{i}", "gruppe": f"u{i}|topstep", "fkey": "topstep", "dauer_min": 2, "bis_min": 660} for i in range(6)]
    spaet = 0
    for seed in range(50):
        for _k, mm in a["ap_zeiten_verteilen"](tr, Z, random.Random(seed)).items():
            spaet += mm >= 660
    check(spaet == 0, f"ap_zeiten_verteilen: Trade 1 nie ab 11:00 dt (50 Seeds, {spaet} zu spät)")

    # ── 5 Bot: Topstep V2 ohne Kette fest (startet nur von Hand), Kette fest (Befund Slave 4: Suche zog Topstep „über Fenster" vor) ──
    BER5 = ZoneInfo("Europe/Berlin")
    tag5 = datetime.now(timezone.utc).astimezone(BER5) + timedelta(days=1)
    mitt5 = datetime(tag5.year, tag5.month, tag5.day, tzinfo=BER5)
    jetzt5 = mitt5 + timedelta(hours=6)

    def p5(pid, start, **kw):
        return dict({"id": pid, "user_id": sd.U1, "master_account_id": "k-2", "master_firm": "FundedNext", "status": "planned", "richtung": "sell",
                     "master_tp": 2000, "master_sl": 2200, "master_contracts": 3, "route": "tsv2", "master_symbol": "NQZ6",
                     "start_um": (mitt5 + timedelta(hours=start)).isoformat(), "auto_plan": True, "auto_bestaetigt_at": jetzt5.isoformat(),
                     "created_at": jetzt5.isoformat()}, **kw)
    b = sd.lade()
    reg5, _g5 = sd.db_stubs(b, jetzt5, [p5("p-ts", 15), p5("p-kt", 9, kt={"nr": 1, "tagesziel": 4500}), p5("p-mt", 10, route="mt5v2")])
    st5 = {z["plan_id"]: z for z in b["_ap_stand_laden"](reg5, jetzt=jetzt5)["geplant"]}
    check(st5["p-ts"]["fest_durch"] == b["AP_FEST_TSV2"] and st5["p-kt"]["fest_durch"] == b["AP_FEST_KETTE"] and st5["p-mt"]["aenderbar"],
          f"Stand: Topstep V2 ohne Kette fest „von Hand“, Kette fest, Echo änderbar ({ {k: v['fest_durch'] for k, v in st5.items()} })")

    # ── 6 Startwert ≠ erste Lesung (09.10.2026, Vorfall Ina Topstep …3822: Plan mit 150.000 gerechnet, echt 147.093,66) ─────────
    c = sd.lade()
    T2c = lambda k, b0, b1: c["ap_kette_trade2"](k, b0, b1, KETTE, c["ap_kette_regel"](KETTE), 0.3)   # noqa: E731
    kst = {"nr": 1, "tagesziel": 4500, "verlust_grenze": 3200, "daily_usd": 3000, "mll": 145500.0, "tagesstart_plan": 150000.0}
    wi, gi = T2c(kst, 147093.66, 146593.66)            # T1 −500 auf dem angefressenen Konto
    check(wi and wi["verlust_grenze"] == 1794 and wi["sl"] == 1294 and wi.get("angefressen") is True and wi.get("abstand_mll") == 1593.66
          and wi.get("verlust_aus_start") is True,
          f"(i) echte Start-Balance 147.093,66: Verlustgrenze 1.794 (Abstand 1.593,66 + 200) statt 3.200 → SL2 1.294 statt 2.700, angefressen ({gi or wi})")
    wj, gj = T2c(kst, 147093.66, 148093.66)            # T1 +1.000
    check(wj and wj["sl"] == 2794 and wj["tp"] == 3500, f"(i) T1 +1.000: SL2 = 1.794 + 1.000 = 2.794 (vorher 4.200), TP2 3.500 ({gj or wj})")
    wn2, gn2 = T2c(kst, 150000.0, 148750.0)
    check(wn2 and wn2["verlust_grenze"] == 3200 and wn2["sl"] == 1950 and not wn2.get("verlust_aus_start"),
          f"(i) echte Start-Balance = Startwert: unverändert (Verlustgrenze 3.200, SL2 1.950) ({gn2 or wn2})")
    wx, gx = T2c(kst, 145400.0, 145300.0)
    check(wx is None and "auf/unter dem MLL" in (gx or ""), f"(i) Start schon unter dem MLL → kein Trade 2 ({gx})")
    wg2, _ = T2c(dict(kst, verlust_grenze=1700, angefressen=True, abstand_mll=1500, reparatur=True, tagesziel=3030), 147000.0, 146000.0)
    check(wg2 and wg2["verlust_grenze"] == 1700 and wg2["sl"] == 700, f"(i) Block schon kleiner (Reparatur-Plan): bleibt 1.700 ({wg2})")

    # Balance-Wahl wie im Backend für ein Topstep-Konto ohne Sync: tv_balance (Puls) mit Zeitstempel; ohne Lesung None
    c["acc_balance_wahl"] = lambda a, e, d: ((float(a["tv_balance"]), "USD", "TV", a.get("tv_balance_at") or "") if (a or {}).get("tv_balance")
                                             else (None, None, None, ""))
    V = c["ap_kette_startwert_veraltet"]
    planv = {"id": "p-sw", "status": "planned", "auto_plan": True, "auto_bestaetigt_at": None, "start_um_gestartet_at": None, "started_at": None,
             "orbit_gesendet_at": None, "created_at": "2026-10-09T02:39:40+00:00", "mt5_baseline": {"kette": kst},
             "notes": "Auto-Planer · Topstep-Kette 1/2 (Tagesziel +4.500 $) · Rest 9.000 $ bis Ziel · Balance 150.000 (Startwert (frisches Konto))"}
    kontov = {"id": "k-sw", "tv_balance": 147093.66, "tv_balance_at": "2026-10-09T02:44:57+00:00", "external_id": "x"}
    ja, grund = V(planv, kontov)
    check(ja and grund == "Kettenplan mit Startwert 150.000 gerechnet, erste Lesung 147.093,66 (TV) — neu planen", f"(ii) Startwert-Plan, erste Lesung 147.093,66 → neu planen ({grund})")
    falle = {"bestätigt": (dict(planv, auto_bestaetigt_at="2026-10-09T03:00:00Z"), kontov),
             "geclaimt": (dict(planv, start_um_gestartet_at="2026-10-09T03:00:00Z"), kontov),
             "gestartet": (dict(planv, started_at="2026-10-09T03:00:00Z"), kontov),
             "ohne Startwert-Notiz": (dict(planv, notes="Auto-Planer · Topstep-Kette 1/2 (Tagesziel +4.500 $) · Balance 150.000 (TV)"), kontov),
             "Lesung vor dem Anlegen": (planv, dict(kontov, tv_balance_at="2026-10-09T02:30:00+00:00")),
             "Abweichung ≤ 50": (planv, dict(kontov, tv_balance=149960)),
             "Trade 2": (dict(planv, mt5_baseline={"kette": dict(kst, nr=2)}), kontov),
             "keine Lesung": (planv, {"id": "k-sw"})}
    nein = [n for n, (pl, ko) in falle.items() if V(pl, ko)[0]]
    check(not nein, f"(ii) nie bei bestätigt/geclaimt/gestartet/ohne Startwert/alter Lesung/≤ 50 $/Trade 2/ohne Lesung ({nein})")
    geloescht, gruende_sw = [], []
    ZEITEN = {"tz": "Europe/Berlin", "fenster": [["00:00", "16:30", 100]], "start_bis": "16:30"}
    c["sb_select"] = lambda t, prm: ([dict(planv, master_account_id="k-sw")] if t == "trade_plans" else [kontov] if t == "accounts"
                                     else [{"zeiten": ZEITEN}] if t == "auto_plan_regeln" else [])
    c["sb_delete"] = lambda t, prm: geloescht.append(dict(prm)) or [{"id": prm["id"][3:]}]
    c["_ap_kette_grund"] = lambda t1_, g: gruende_sw.append((t1_["id"], g))
    BER6 = ZoneInfo("Europe/Berlin")
    im_fenster = datetime(2026, 10, 9, 5, 0, tzinfo=BER6).astimezone(timezone.utc)      # Fr 05:00 dt
    nach_fenster = datetime(2026, 10, 9, 16, 20, tzinfo=BER6).astimezone(timezone.utc)  # Fr 16:20 dt > 16:30 − 15 min
    weg_spaet = c["ap_kette_startwert_neu"](nach_fenster)
    check(weg_spaet == [] and not geloescht and gruende_sw and "heute kein Nachplanen mehr" in gruende_sw[0][1] and "147.093,66" in gruende_sw[0][1],
          f"(ii) nach dem Nachplan-Fenster: NICHT löschen, Warnung am ⛓ von Trade 1 ({weg_spaet}, {gruende_sw})")
    c["sb_select"] = lambda t, prm: ([dict(planv, master_account_id="k-sw")] if t == "trade_plans" else [kontov] if t == "accounts"
                                     else (_ for _ in ()).throw(RuntimeError("weg")) if t == "auto_plan_regeln" else [])
    check(c["ap_kette_startwert_neu"](im_fenster) == [] and not geloescht, "(ii) Regeln nicht lesbar → wie Fenster zu, nichts gelöscht")
    c["sb_select"] = lambda t, prm: ([dict(planv, master_account_id="k-sw")] if t == "trade_plans" else [kontov] if t == "accounts"
                                     else [{"zeiten": ZEITEN}] if t == "auto_plan_regeln" else [])
    weg = c["ap_kette_startwert_neu"](im_fenster)
    g0 = geloescht[0] if geloescht else {}
    check(weg == ["p-sw"] and g0.get("status") == "eq.planned" and g0.get("auto_bestaetigt_at") == "is.null"
          and g0.get("start_um_gestartet_at") == "is.null" and g0.get("started_at") == "is.null" and g0.get("orbit_gesendet_at") == "is.null",
          f"(ii) Takt löscht genau diesen Plan, Guard im Filter (Rennen mit Bestätigen/Claim) ({weg}, {g0})")
    c["sb_delete"] = lambda t, prm: []                  # Guard griff (inzwischen bestätigt) → nicht als gelöscht melden
    check(c["ap_kette_startwert_neu"](im_fenster) == [], "(ii) Guard greift → nichts gemeldet")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
