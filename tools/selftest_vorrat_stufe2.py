#!/usr/bin/env python3
"""Selbsttest Vorrat Stufe 2 (app.py, VORRAT STUFE 2, 06.10.2026) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_vorrat_stufe2.py
Lädt die Funktionen per Quelltext aus app.py (wie selftest_vorrat: app.py zieht beim Import Flask und Threads).
Modell-Fälle mit festen Stufen; dazu die Kette aus den Kernwerten (auto_plan_regeln, Einträge wie
sql/2026-10-06_auto_plan_kernwerte.sql + Planer-Phasen aus sql/2026-10-05_auto_planer.sql). Fälle = Finns Beispiele: FundedNext 100k bei 92.000 → 11 %,
Tradeify-Kette 56 % × 56 % × 69 %, fünf frische Tradeify ≈ 71 %, ID F × FundedNext → 2 × 100k (Erwartungswert), Apex-Evaluation
≈ 30 % (Finn 06.10.2026). IDs und Konten sind erfunden."""
import os
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")

FN = {   # FundedNext / The5ers / FundingPips / FTMO wie im SQL
    "phase1": {"modell": "statisch", "ziel_pct": 8, "boden_pct": 10, "folge": "phase2"},
    "phase2": {"modell": "statisch", "ziel_pct": 5, "boden_pct": 10, "folge": "funded_cfd"},
    "funded_cfd": {"modell": "bestand", "boden_pct": 10, "sl_normal_usd": 3000, "skaliert": True},
}
T5 = dict(FN, funded_cfd={"modell": "bestand", "boden_pct": 10, "sl_normal_usd": 2250, "skaliert": True})
TRADEIFY = {
    "challenge": {"modell": "trades", "risiko_usd": 4500, "tps_usd": [3600, 3600, 1800], "folge": "funded"},
    "funded": {"modell": "trades", "risiko_usd": 4500, "tps_usd": [14500], "folge": "winning_days"},
    "winning_days": {"modell": "bestand", "boden_ueber_start_usd": 100},
}
APEX = {"challenge": {"modell": "tage", "tages_usd": 2000, "gesamt_usd": 4000, "ziel_usd": 9000, "puffer_usd": 100,
                      "folge": "funded"},
        "funded": {"modell": "siege", "tages_usd": 2500, "tp_tag_usd": 7500, "ziel_usd": 15000, "verlusttage_max": 2,
                   "folge": "winning_days"},
        "winning_days": {"modell": "bestand"}}
ZIEL_FN = {"art": "groessen_summe", "typen": ["funded_cfd", "funded"], "von": 200000, "bis": 300000,
           "kauf_einheit": "100k 2-Step Standard", "kauf_groesse": 100000, "kauf_stufe": "phase1"}
ZIEL_T5 = {"art": "stueck", "typen": ["funded_cfd", "funded"], "groessen": [{"groesse": 100000, "stueck": 1},
           {"groesse": 200000, "stueck": 1}], "kauf_einheit": "Summer Plan", "kauf_stufe": "phase1"}


KERN = [
    {"namen": ["tradeify"], "groessen": [150000], "kauf_eur": 215, "dd_usd": 4500, "boden": "nachziehend", "ziel_pct": {"challenge": 6},
     "phasen": {"challenge": {"ziel_pct": 6, "dd_usd": 4500, "tp_max": 3600}}},
    {"namen": ["apextrader", "apex"], "groessen": [150000], "kauf_eur": 150, "dd_usd": 4000, "boden": "statisch", "daily_usd": 2000,
     "soft": True, "ziel_pct": {"challenge": 6}, "phasen": {"challenge": {"ziel_pct": 6, "puffer": [100, 100]}}},
    {"namen": ["fundednext"], "groessen": [100000], "kauf_eur": {"50000": 261, "100000": 500}, "dd_pct": 10, "boden": "statisch",
     "ziel_pct": {"phase1": 8, "phase2": 5}, "wert_groessen": [50000, 100000],
     "phasen": {"phase1": {"sl": [2500, 3500]}, "phase2": {"sl": [2500, 3500]}}},
    {"namen": ["the5ers"], "groessen": [100000, 200000], "skaliert": True, "kauf_eur": {"100000": 146, "200000": 226}, "dd_pct": 10,
     "boden": "statisch", "ziel_pct": {"phase1": 8, "phase2": 5}, "phasen": {"phase2": {"sl": [2000, 2500]}}},
    {"namen": ["topstep"], "planen": False, "kauf_eur": 237, "dd_usd": 4500, "boden": "nachziehend", "tp_max": 4500,
     "ziel_pct": {"challenge": 6}, "groessen": [150000]},
    {"namen": ["ftmo"], "planen": False, "kauf_eur": 446, "dd_pct": 10, "boden": "statisch", "ziel_pct": {"phase1": 10, "phase2": 5},
     "groessen": [100000, 200000]},
]


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"datetime": datetime, "timezone": timezone}

    def block(name):
        i = src.index(f"def {name}(")
        return src[i:src.find("\n\n\n", i)]
    i = src.index("VORRAT2_SQL = ")
    konst = src[i:src.index("_vr2_info = ", i)]
    i = src.index("AP_GROESSE_TOLERANZ = ")
    teile = ["import random\nimport zlib\nimport re", konst, src[i:src.index("\n", i)], block("pb_handelstag")]
    j = src.index("AP_KW_FUNDED = ")
    teile.append(src[j:src.index("\n\n\n", j)])
    teile += [block(f) for f in ("_ap_norm", "ap_regel_finden", "ap_groesse", "ap_kw_param", "_ap_kw_kauf", "_ap_kw_wachsen",
                                 "ap_kontowert", "vorrat_stufen_aus_kernwerten")]
    teile += [block(f) for f in ("_vr2_num", "vorrat_chance_stufe", "vorrat_chance_kette", "vorrat_bestand_konto",
                                 "vorrat_alter_handelstage", "vorrat_mc", "vorrat_score", "vorrat_totband", "vorrat_anzeige_n",
                                 "vorrat_quoten", "vorrat2_zelle", "vorrat2_slot")]
    exec("\n\n".join(teile), ns)
    return ns


def main():
    ns = lade()
    n, fehler = 0, []

    def pruef(name, ist, soll, tol=None):
        nonlocal n
        n += 1
        ok = (abs(ist - soll) <= tol) if (tol is not None and ist is not None) else (ist == soll)
        if not ok:
            fehler.append(f"{name}: ist {ist!r}, soll {soll!r}" + (f" (±{tol})" if tol else ""))

    st, kette = ns["vorrat_chance_stufe"], ns["vorrat_chance_kette"]

    # ── Chance je Stufe ──
    e = st(FN["phase1"], 92000, 100000)
    pruef("Finn: FundedNext 100k P1 bei 92.000 → 2.000 ÷ 18.000 = 11 %", e["chance"], 2000 / 18000, 1e-9)
    pruef("… Boden/Ziel", (e["boden"], e["ziel"]), (90000.0, 108000.0))
    pruef("FundedNext P1 frisch = 10.000 ÷ 18.000 = 56 % (Konzept: 56 %)", st(FN["phase1"], 100000, 100000)["chance"], 10 / 18, 1e-9)
    pruef("FTMO P1 frisch (10 % gegen 10 %) = 50 %", st({"modell": "statisch", "ziel_pct": 10, "boden_pct": 10}, 100000, 100000)["chance"], 0.5, 1e-9)
    pruef("FundedNext P2 frisch = 67 %", st(FN["phase2"], 100000, 100000)["chance"], 10 / 15, 1e-9)
    pruef("über dem Ziel = erreicht", (st(FN["phase2"], 53934, 50000)["erreicht"]), True)
    pruef("unter dem Boden = 0", st(FN["phase1"], 89000, 100000)["chance"], 0.0)
    pruef("Boden aus max_dd, wenn die Regel keinen kennt (T1: Größe − max_drawdown)",
          st({"modell": "statisch", "ziel_pct": 10}, 95000, 100000, max_dd=12000)["boden"], 88000.0)
    finn = {"modell": "trades", "risiko_usd": 4500, "tps_usd": [3500, 3500, 2000]}
    e = st(finn, 150000, 150000)
    pruef("Finn: Tradeify-Kette 56 % × 56 % × 69 %", [round(t["p"], 2) for t in e["trades"]], [0.56, 0.56, 0.69])
    pruef("… zusammen ≈ 22 %", e["chance"], 0.5625 * 0.5625 * (4500 / 6500), 1e-9)
    e = st(TRADEIFY["challenge"], 153600, 150000)
    pruef("Tradeify nach dem 1. Trade: 4.500/8.100 × 4.500/6.300", e["chance"], (4500 / 8100) * (4500 / 6300), 1e-9)
    e = st(TRADEIFY["challenge"], 148000, 150000)
    pruef("Tradeify unter Start: Polster 2.500 im ersten Trade", e["trades"][0]["polster"], 2500.0)
    pruef("Topstep Combine frisch 25 %",
          st({"modell": "trades", "risiko_usd": 4500, "tps_usd": [4500, 4500]}, 150000, 150000)["chance"], 0.25, 1e-9)
    pruef("Topstep nach Tag 1 50 %",
          st({"modell": "trades", "risiko_usd": 4500, "tps_usd": [4500, 4500]}, 154500, 150000)["chance"], 0.5, 1e-9)
    e = st(APEX["challenge"], 150000, 150000)
    pruef("Finn: Apex 2.000 ÷ 11.100, dann 2.000 ÷ 13.100", [round(t["p"], 4) for t in e["trades"]],
          [round(2000 / 11100, 4), round(2000 / 13100, 4)])
    pruef("… zusammen ≈ 30 %", e["chance"], 1 - (1 - 2000 / 11100) * (1 - 2000 / 13100), 1e-9)
    pruef("T1: Apex 145.907 unter dem Boden 146.000 → 0", st(APEX["challenge"], 145907, 150000)["chance"], 0.0)
    pruef("Apex nach einem Verlusttag (148.000): nur noch ein Tag", len(st(APEX["challenge"], 148000, 150000)["trades"]), 1)
    pruef("Regel daten_fehlen", st({"daten_fehlen": True}, 1, 1)["daten_fehlen"], True)
    e = st(APEX["funded"], 150000, 150000)
    pruef("Apex Funded: 2 Siege vor 2 Verlusttagen = 15,6 % (T1)", e["chance"], 0.25 ** 2 + 2 * 0.25 ** 2 * 0.75, 1e-9)
    pruef("… nach dem ersten Sieg (+7.500): 1 − 0,75² = 43,75 %", st(APEX["funded"], 157500, 150000)["chance"], 1 - 0.75 ** 2, 1e-9)
    pruef("ohne Balance daten_fehlen", st(FN["phase1"], None, 100000)["daten_fehlen"], True)

    # ── Kette ──
    pruef("FundedNext P1 frisch bis Funded = 56 % × 67 %", kette(FN, "phase1", 100000, 100000)["chance"], (10 / 18) * (10 / 15), 1e-9)
    pruef("P2 im Ziel zählt 95 %", kette(FN, "phase2", 53934, 50000)["chance"], 0.95, 1e-9)
    pruef("… auch mit Quoten-Faktor", kette(FN, "phase2", 53934, 50000, faktoren={"phase2": 0.9})["chance"], 0.95, 1e-9)
    e = kette(TRADEIFY, "challenge", 150000, 150000)
    pruef("Tradeify Challenge → Funded → Big Trade", e["chance"],
          (4500 / 8100) ** 2 * (4500 / 6300) * (4500 / 19000), 1e-9)
    pruef("… Wert beim Ankommen = Plus 14.500", e["wert_usd"], 14500.0)
    pruef("Faktor aus Quoten wirkt je Stufe", kette(FN, "phase1", 100000, 100000, faktoren={"phase1": 0.5})["chance"],
          0.5 * (10 / 18) * (10 / 15), 1e-9)
    pruef("fehlende Stufe → daten_fehlen", kette({"phase1": FN["phase1"]}, "phase1", 100000, 100000)["daten_fehlen"], True)

    # ── Bestand gefährdet ──
    g = ns["vorrat_bestand_konto"]
    pruef("The5ers 200k bei 184.146 (4.146 vor Boden < SL 4.500) gefährdet", g(T5["funded_cfd"], 184146, 200000)["gefaehrdet"], True)
    pruef("FundedNext 100k bei 95.950 nicht gefährdet", g(FN["funded_cfd"], 95950, 100000)["gefaehrdet"], False)
    pruef("ohne SL in der Regel nie gefährdet", g(TRADEIFY["winning_days"], 150200, 150000)["gefaehrdet"], False)

    # ── Monte Carlo ──
    p_t = 0.5625 * 0.5625 * (4500 / 6500)
    ok, _joint = ns["vorrat_mc"]([{"soll": 1, "fest": 0.0, "funnel": [(p_t, 1.0, "challenge")] * 5, "neu": (0.0, 0.0)}],
                                 0, 4000, 7)
    pruef("Finn: fünf frische Tradeify ≈ 71 % (mindestens eins)", ok(0), 1 - (1 - p_t) ** 5, 0.025)
    ok, _ = ns["vorrat_mc"]([{"soll": 1, "fest": 0.0, "funnel": [(p_t, 1.0, "challenge")] * 5, "neu": (0.0, 0.0)}],
                            0, 4000, 7, gemeinsam=True)
    pruef("tranche_gemeinsam: fünf wie eines ≈ 22 %", ok(0), p_t, 0.025)
    ok1, _ = ns["vorrat_mc"]([{"soll": 1, "fest": 0.0, "funnel": [(0.3, 1.0, "x")], "neu": (0.5, 1.0)}], 3, 500, 1)
    ok2, _ = ns["vorrat_mc"]([{"soll": 1, "fest": 0.0, "funnel": [(0.3, 1.0, "x")], "neu": (0.5, 1.0)}], 3, 500, 1)
    pruef("fester Seed: gleiche Zahl", (ok1(0, 2), ok1(0, 3)), (ok2(0, 2), ok2(0, 3)))
    pruef("P steigt mit n", ok1(0, 0) <= ok1(0, 1) <= ok1(0, 2) <= ok1(0, 3), True)

    # ── Zelle: ID F × FundedNext (Konzept 05.10.2026) ──
    zelle = ns["vorrat2_zelle"]
    idf = [{"account_id": "k1", "typ": "phase2", "groesse": 50000, "balance": 53934, "alter_tage": 0},
             {"account_id": "k2", "typ": "phase2", "groesse": 100000, "balance": 92208, "alter_tage": 0}] + \
            [{"account_id": f"k{3 + i}", "typ": "phase1", "groesse": 100000, "balance": 100000, "alter_tage": 0} for i in range(3)]
    # Master 06.10.2026: reine Formel (Finns Regel), keine Korrektur — Finns „→ 2" war geschätzt (Konzept mit P2 × 0,90)
    z = zelle(ZIEL_FN, FN, idf, "frei", seed=11)
    erw = 0.95 * 50000 + (2208 / 15000) * 100000 + 3 * (10 / 18) * (10 / 15) * 100000
    pruef("ID F × FundedNext: erwartet ≈ 173k (reine Formel)", z["erwartet"], erw, 1)
    pruef("… nach Erwartungswert 1 × 100k", z["nachkauf"]["n_erwartung"], 1)
    pruef("… bei 80 % Sicherheit 4 × 100k", z["nachkauf"]["n_roh"], 4)
    kor = {"phase2": 0.6 / (10 / 15)}
    zk = zelle(ZIEL_FN, FN, idf, "frei", faktoren=kor, seed=11)
    pruef("Konzept-Rechnung (P2 × 0,90) ergibt Finns 2 × 100k", zk["nachkauf"]["n_erwartung"], 2)
    pruef("… Dringlichkeit jetzt, Score ≥ 67", (z["lage"], z["score"] >= 67), ("jetzt", True))
    pruef("… Sicherheit mit Kauf ≥ 80 %", z["sicherheit_nach"] >= 0.8, True)
    pruef("… Score-Teile mit Bestand/Untergrenze/Zufluss/Sicherheit/Lücke",
          [t["name"] for t in z["score_teile"]][:5],
          ["Gesicherter Bestand", "Untergrenze", "Gefährdeter Bestand", "Erwarteter Zufluss (Funnel)", "Sicherheit ohne Kauf"])
    z60 = zelle(ZIEL_FN, FN, idf, "frei", param={"sicherheit": 0.55}, seed=11)
    pruef("Sicherheit 55 % → weniger Käufe als 80 %", z60["nachkauf"]["n_roh"] < z["nachkauf"]["n_roh"], True)
    pruef("pausiert: kein Kauf, keine Dringlichkeit", (lambda q: (q["nachkauf"]["n_roh"], q["lage"], q["nachkauf"]["grund"]))(
        zelle(ZIEL_FN, FN, idf, "pausiert")), (0, None, "pausiert"))
    ohne = idf[:1] + [{"account_id": "k9", "typ": "phase1", "groesse": 100000, "balance": None}]
    q = zelle(ZIEL_FN, FN, ohne, "frei")
    pruef("Konto ohne Lesung → Daten fehlen sperrt", (q["sperre"], q["nachkauf"]["n_roh"], q["lage"]), ("daten_fehlen", None, None))
    alt = idf[:1] + [dict(idf[2], alter_tage=3)]
    q = zelle(ZIEL_FN, FN, alt, "frei")
    pruef("Lesung 3 Handelstage alt → unsicher sperrt", (q["sperre"], q["nachkauf"]["n_roh"]), ("unsicher", None))
    pruef("… Konto rechnet mit Startwert (P1 frisch 33 %)", round(q["konten"][1]["chance"], 4), round((10 / 18) * (10 / 15), 4))
    gedeckt = [{"account_id": f"f{i}", "typ": "funded_cfd", "groesse": 100000, "balance": 101000, "alter_tage": 0} for i in range(3)]
    q = zelle(ZIEL_FN, FN, gedeckt, "frei")
    pruef("300k Funded = über dem Ziel → gedeckt, kein Kauf", (q["lage"], q["nachkauf"]["n_roh"], q["score"]), ("gedeckt", 0, 0))
    q = zelle(ZIEL_FN, FN, gedeckt[:2], "frei")
    pruef("200k Funded, kein Funnel: Blow drückt unter 200k → bald + Nachkauf", (q["lage"], q["nachkauf"]["grund"],
          q["nachkauf"]["n_roh"]), ("bald", "blow_reserve", 4))
    q = zelle(dict(ZIEL_FN, von=100000), FN, gedeckt[:2], "frei")
    pruef("Mindest-Funnel: 200k bei Untergrenze 100k, nichts unterwegs → 1 Konto, bald",
          (q["lage"], q["nachkauf"]["grund"], q["nachkauf"]["n_roh"], q["score"]), ("bald", "mindest_funnel", 1, 34))
    gef = [{"account_id": "g", "typ": "funded_cfd", "groesse": 100000, "balance": 91000, "alter_tage": 0}]
    q = zelle(dict(ZIEL_FN, von=50000), FN, gef, "frei")
    pruef("gefährdetes Funded zählt halb", (q["konten"][0]["gefaehrdet"], q["bestand_gewichtet"]), (True, 50000.0))
    t5 = [{"account_id": "t", "typ": "funded_cfd", "groesse": 100000, "balance": 103000, "alter_tage": 0}]
    q = zelle(ZIEL_T5, T5, t5, "frei")
    pruef("The5ers: 200k fehlt → jetzt, Teil 200k", (q["lage"], q["nachkauf"]["teile"][1]["groesse"],
          q["nachkauf"]["teile"][1]["lage"]), ("jetzt", 200000.0, "jetzt"))
    q = zelle({"art": "stueck", "typen": ["winning_days"], "groessen": [{"groesse": None, "stueck": 1}], "kauf_groesse": 150000,
               "kauf_stufe": "challenge"}, APEX, [], "frei")
    pruef("Apex ohne Konten: kein Daten-fehlen, nur Deckel-Hinweis", (q["sperre"], len(q["hinweise"]), q["nachkauf"]["n_roh"],
          q["hinweise"][0].startswith("Deckel 10")), (None, 1, 10, True))
    vl = dict(APEX, funded=dict(APEX["funded"], vorlaeufig=True, notiz="Weg vorläufig"))
    pruef("vorläufige Regel erscheint als Hinweis", zelle(q_ziel := {"art": "stueck", "typen": ["winning_days"], "groessen":
          [{"groesse": None, "stueck": 1}], "kauf_groesse": 150000, "kauf_stufe": "challenge"}, vl, [], "frei")["hinweise"][0],
          "Weg vorläufig")
    pruef("… Chance je neues Konto = Evaluation × Funded", q["nachkauf"]["teile"][0]["chance_neu"],
          (1 - (1 - 2000 / 11100) * (1 - 2000 / 13100)) * (0.25 ** 2 + 2 * 0.25 ** 2 * 0.75), 1e-9)

    # ── Score ──
    sc = ns["vorrat_score"]
    pruef("Score-Bänder", (sc("jetzt", 0, 0.8), sc("jetzt", 0.8, 0.8), sc("bald", 0, 0.8), sc("bald", 0.8, 0.8),
                           sc("gedeckt", 0.8, 0.8), sc("gedeckt", 1, 0.8)), (100, 67, 66, 34, 33, 0))

    # ── Totband + Anzeige ──
    tb = ns["vorrat_totband"]
    a = tb(2, None, "T1")
    pruef("erster Lauf übernimmt", (a["n_tb"], a["n_seit"]), (2, "T1"))
    b = tb(3, a, "T2")
    pruef("Steigen: erst gehalten", (b["n_tb"], b["n_seit"]), (2, "T1"))
    c = tb(3, b, "T3")
    pruef("… nach zwei gleichen Läufen übernommen", (c["n_tb"], c["n_seit"]), (3, "T3"))
    d = tb(1, c, "T4")
    pruef("Sinken sofort", (d["n_tb"], d["n_seit"]), (1, "T4"))
    e = tb(4, d, "T5")
    pruef("Springen 1 → 4 → 1 → 4 bleibt bei 1", tb(4, tb(1, e, "T6"), "T7")["n_tb"], 1)
    an = ns["vorrat_anzeige_n"]
    pruef("nach dem Lauf angelegte Konten zieht die Anzeige ab", an(2, "2026-10-06T11:00", ["2026-10-06T13:00", "2026-10-05"],
                                                                 [], "2026-10-06T14:00")["n"], 1)
    best = [{"id": 1, "anzahl": 2, "at": "2026-10-06T12:00", "verfall_at": "2026-10-08T12:00"}]
    r = an(2, "2026-10-06T11:00", [], best, "2026-10-06T14:00")
    pruef("bestellt 2 → Anzeige 0, offen 2", (r["n"], r["bestellt"]["offen"]), (0, 2))
    r = an(2, "2026-10-06T11:00", ["2026-10-06T13:00", "2026-10-06T13:05"], best, "2026-10-06T14:00")
    pruef("bestellt + angelegt nicht doppelt abgezogen", (r["n"], r["bestellt"]), (0, None))
    r = an(2, "2026-10-06T11:00", [], best, "2026-10-09T14:00")
    pruef("Bestellung nach 48 h verfallen", (r["n"], r["bestellt"]), (2, None))

    # ── Quoten, Handelstage, Takt ──
    qu = ns["vorrat_quoten"]
    f25 = [("FundedNext", "phase1", "bestanden")] * 5 + [("FundedNext", "phase1", "geblowt")] * 20
    r = qu(f25, {"FundedNext": FN})[("FundedNext", "phase1")]
    pruef("25 Fälle (5 bestanden): Faktor = (25/45 × 20 % + 20/45 × 50 %) ÷ 50 %", r["faktor"],
          ((25 / 45) * 0.2 + (20 / 45) * (10 / 18)) / (10 / 18), 1e-9)
    r = qu(f25[:19], {"FundedNext": FN})[("FundedNext", "phase1")]
    pruef("19 Fälle: nur Formel", r["faktor"], None)
    pruef("Funded nicht gemessen", qu([("Tradeify", "funded", "geblowt")] * 30, {"Tradeify": TRADEIFY}), {})
    al = ns["vorrat_alter_handelstage"]
    jetzt = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)          # Montag
    pruef("Freitags-Lesung am Montag = 1 Handelstag", al("2026-10-09T12:00:00+00:00", jetzt), 1)
    pruef("Mittwochs-Lesung am Montag = 3", al("2026-10-07T12:00:00+00:00", jetzt), 3)
    pruef("ohne Zeitstempel None", al(None, jetzt), None)
    sl = ns["vorrat2_slot"]
    t = ["23:00", "05:00", "11:00", "17:00"]
    a, b = sl(datetime(2026, 10, 6, 14, 50, tzinfo=timezone.utc), t)
    pruef("Takt 14:50 → letzter 11:00, nächster 17:00", (a.hour, b.hour), (11, 17))
    a, b = sl(datetime(2026, 10, 6, 23, 30, tzinfo=timezone.utc), t)
    pruef("Takt 23:30 → letzter 23:00, nächster 05:00 am Folgetag", (a.hour, b.hour, b.day), (23, 5, 7))

    # ── Kette aus den Kernwerten (EINE Quelle, auto_plan_regeln) ──
    ak, rf = ns["vorrat_stufen_aus_kernwerten"], ns["ap_regel_finden"]
    S = {f: ak(rf(KERN, f)) for f in ("Tradeify", "Apex Trader", "FundedNext", "The5%ers", "Topstep", "FTMO")}
    pruef("Tradeify: Challenge in Etappen 3.600/3.600/1.800", [t["tp"] for t in st(S["Tradeify"]["challenge"], 150000, 150000)["trades"]],
          [3600.0, 3600.0, 1800.0])
    pruef("Tradeify frisch bis Winning Days (Kernwerte = feste Regeln)", kette(S["Tradeify"], "challenge", 150000, 150000)["chance"],
          kette(TRADEIFY, "challenge", 150000, 150000)["chance"], 1e-12)
    pruef("Tradeify Wert beim Ankommen 14.500", kette(S["Tradeify"], "challenge", 150000, 150000)["wert_usd"], 14500.0)
    pruef("Tradeify WD-Boden Start + 100", S["Tradeify"]["winning_days"]["boden_ueber_start_usd"], 100)
    pruef("Topstep: Combine 25 % × Funded (4.500/9.000 × 4.500/19.000)", kette(S["Topstep"], "challenge", 150000, 150000)["chance"],
          0.25 * 0.5 * (4500 / 19000), 1e-12)
    pruef("Apex: Evaluation ≈ 30 % × Funded 15,6 %", kette(S["Apex Trader"], "challenge", 150000, 150000)["chance"],
          (1 - (1 - 2000 / 11100) * (1 - 2000 / 13100)) * (0.25 ** 2 + 2 * 0.25 ** 2 * 0.75), 1e-12)
    pruef("FundedNext P1 bei 92.000 → 11 %", st(S["FundedNext"]["phase1"], 92000, 100000)["chance"], 2000 / 18000, 1e-12)
    pruef("FundedNext Funded: normaler SL = Planer-Mitte 3.000", S["FundedNext"]["funded_cfd"]["sl_normal_usd"], 3000.0)
    pruef("The5ers Funded: SL 2.250 je 100k, skaliert", (S["The5%ers"]["funded_cfd"]["sl_normal_usd"], S["The5%ers"]["funded_cfd"]["skaliert"]),
          (2250.0, True))
    pruef("FTMO: P1 frisch 50 %, Funded-SL Standard 2.500 je 100k", (round(st(S["FTMO"]["phase1"], 100000, 100000)["chance"], 9),
          S["FTMO"]["funded_cfd"]["sl_normal_usd"], S["FTMO"]["funded_cfd"]["skaliert"]), (0.5, 2500, True))
    pruef("1-Step-Konto (CFD als challenge) rechnet wie Phase 1", kette(S["FundedNext"], "challenge", 100000, 100000)["chance"],
          kette(S["FundedNext"], "phase1", 100000, 100000)["chance"], 1e-12)
    pruef("Firma ohne Kernwerte → leer", ak(rf(KERN, "Lucid")), {})
    pruef("kein Funded-Weg im Parameter → daten_fehlen", ak(rf(KERN, "Tradeify"), {"funded_wege": {}})["funded"]["daten_fehlen"], True)
    kwf = ns["ap_kw_param"](rf(KERN, "FundedNext"))
    q = zelle(ZIEL_FN, S["FundedNext"], idf, "frei", seed=11, kw=kwf)
    pruef("Zelle aus Kernwerten = Zelle aus festen Regeln", q["nachkauf"]["n_roh"], zelle(ZIEL_FN, FN, idf, "frei", seed=11)["nachkauf"]["n_roh"])
    pruef("wert_eur je Konto: frisches 100k-P1 = Kauf 500 €", q["konten"][2]["wert_eur"], 500)
    pruef("Preis je Kauf aus kauf_eur (100k)", q["nachkauf"]["preis_eur"], 500)
    pruef("funnel_eur = Summe der Konten", q["funnel_eur"], sum(k["wert_eur"] or 0 for k in q["konten"]))
    q5 = zelle(ZIEL_T5, S["The5%ers"], t5, "frei", kw=ns["ap_kw_param"](rf(KERN, "The5%ers")))
    pruef("The5ers: Preis je Fach (200k = 226 €)", q5["nachkauf"]["teile"][1]["preis_eur"], 226)

    if fehler:
        print(f"FEHLER — {len(fehler)} von {n} Prüfungen:")
        for f in fehler:
            print("  ✗", f)
        sys.exit(1)
    print(f"OK — {n}/{n} Prüfungen")


if __name__ == "__main__":
    main()
