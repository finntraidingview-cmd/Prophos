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
    k1 = src.index("VORRAT_TYPEN = (")
    teile = ["import random\nimport zlib\nimport re", src[k1:src.index("\n", k1)], konst, src[i:src.index("\n", i)], block("pb_handelstag")]
    j = src.index("AP_KW_FUNDED = ")
    teile.append(src[j:src.index("\n\n\n", j)])
    teile += [block(f) for f in ("_ap_norm", "ap_regel_finden", "ap_groesse", "ap_kw_param", "_ap_kw_kauf", "_ap_kw_wachsen",
                                 "ap_kontowert", "vorrat_stufen_aus_kernwerten")]
    j2 = src.index("VORRAT_KI_PRIO = ")
    teile.append(src[j2:src.index("\n", j2)])
    teile += [block(f) for f in ("vorrat_ziel_pruefen", "_vr2_k", "_vr2_usd", "_vr2_unterwegs_txt", "vorrat_satz_nominal", "vorrat_satz", "vorrat_personen", "vorrat_regel_satz", "vorrat_gesamt", "vorrat_score_gruppen", "vorrat_ki_hinweis", "vorrat_fakten_text", "vorrat_ki_pruefen",
                                 "vorrat_ki_anwenden", "vorrat_tagesliste", "_vr2_num", "vorrat_chance_stufe", "vorrat_chance_kette", "vorrat_bestand_konto",
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

    def mit(regel):
        """zelle mit fester Kaufregel (Standard ist seit 06.10.2026 spät 'sicherheit' 25 %)"""
        return lambda *a, param=None, **kw: zelle(*a, param=dict(regel, **(param or {})), **kw)
    zelleS80 = mit({"kauf_regel": "sicherheit", "sicherheit": 0.8, "toleranz_pct": 0, "mindest_funnel": 1})
    zelleM = mit({"kauf_regel": "mitte", "nur_eins_firmen": ["apextrader"]})
    idf = [{"account_id": "k1", "typ": "phase2", "groesse": 50000, "balance": 53934, "alter_tage": 0},
             {"account_id": "k2", "typ": "phase2", "groesse": 100000, "balance": 92208, "alter_tage": 0}] + \
            [{"account_id": f"k{3 + i}", "typ": "phase1", "groesse": 100000, "balance": 100000, "alter_tage": 0} for i in range(3)]
    # Master 06.10.2026: reine Formel (Finns Regel), keine Korrektur — Finns „→ 2" war geschätzt (Konzept mit P2 × 0,90)
    z = zelleS80(ZIEL_FN, FN, idf, "frei", seed=11)
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
          [t["name"] for t in z["score_teile"]][:6],
          ["Gesicherter Bestand", "Untergrenze", "Gefährdeter Bestand", "Erwarteter Zufluss (Funnel)", "Lücke nach Erwartung",
           "Sicherheit ohne Kauf"])
    # Variante a) kauf_regel 'erwartung': Hauptzahl = Erwartungswert, Monte Carlo nur Info
    za = zelle(ZIEL_FN, FN, idf, "frei", param={"kauf_regel": "erwartung"}, seed=11)
    luecke = 200000 - erw
    pruef("a) erwartung: n = Lücke ÷ (37 % × 100k) = 1", (za["nachkauf"]["n_roh"], za["lage"]), (1, "jetzt"))
    pruef("a) Score = 67 + 33 × Lücke/Untergrenze", za["score"], int(round(67 + 33 * luecke / 200000)))
    pruef("a) Monte Carlo bleibt als Info", za["sicherheit"], z["sicherheit"])
    zt = zelle({"art": "plus_ueber_start", "typen": ["winning_days"], "von": 20000, "bis": 30000, "kauf_groesse": 150000,
                "kauf_stufe": "challenge"}, TRADEIFY,
               [{"account_id": f"w{i}", "typ": "winning_days", "groesse": 150000, "balance": b, "alter_tage": 0}
                for i, b in enumerate((154756, 153430, 160177))], "frei", param={"kauf_regel": "erwartung"})
    p_neu = (4500 / 8100) ** 2 * (4500 / 6300) * (4500 / 19000)
    pruef("a) Tradeify +18,4k gegen 20k: n = 1.637 ÷ (Chance × 14.500)", zt["nachkauf"]["n_roh"],
          -(-(20000 - 18363) // (p_neu * 14500)))
    z60 = zelleS80(ZIEL_FN, FN, idf, "frei", param={"sicherheit": 0.55}, seed=11)
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
    q = zelleS80(ZIEL_FN, FN, gedeckt[:2], "frei")
    pruef("200k Funded, kein Funnel: Blow drückt unter 200k → bald + Nachkauf", (q["lage"], q["nachkauf"]["grund"],
          q["nachkauf"]["n_roh"]), ("bald", "blow_reserve", 4))
    q = zelleS80(dict(ZIEL_FN, von=100000), FN, gedeckt[:2], "frei")
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
               "kauf_stufe": "challenge"}, APEX, [], "frei", param={"kauf_regel": "erwartung"})
    pruef("Apex ohne Konten: kein Daten-fehlen, nur Deckel-Hinweis", (q["sperre"], len(q["hinweise"]), q["nachkauf"]["n_roh"],
          q["hinweise"][0].startswith("Deckel 10")), (None, 1, 10, True))
    vl = dict(APEX, funded=dict(APEX["funded"], vorlaeufig=True, notiz="Weg vorläufig"))
    pruef("vorläufige Regel erscheint als Hinweis", zelle(q_ziel := {"art": "stueck", "typen": ["winning_days"], "groessen":
          [{"groesse": None, "stueck": 1}], "kauf_groesse": 150000, "kauf_stufe": "challenge"}, vl, [], "frei")["hinweise"][0],
          "Weg vorläufig")
    pruef("… Chance je neues Konto = Evaluation × Funded", q["nachkauf"]["teile"][0]["chance_neu"],
          (1 - (1 - 2000 / 11100) * (1 - 2000 / 13100)) * (0.25 ** 2 + 2 * 0.25 ** 2 * 0.75), 1e-9)

    zb = zelle(ZIEL_FN, FN, gedeckt[:2], "frei", param={"kauf_regel": "erwartung"})
    zb["kauf_regel"] = "erwartung"
    pruef("a) 200k Funded ohne Funnel: Blow-Lücke 100k → bald, n = 100k ÷ 37k = 3", (zb["lage"], zb["nachkauf"]["n_roh"],
          zb["score"]), ("bald", 3, int(round(34 + 32 * 0.5))))
    pruef("a) gedeckt mit Reserve: Score aus Monte Carlo ≤ 33", zelle(ZIEL_FN, FN, gedeckt, "frei", param={"kauf_regel": "erwartung"})["score"] <= 33, True)

    # ── Standard Erwartungswert, Variante c, Satz, Tagesliste (Master 06.10.2026) ──
    ziel_tr = {"art": "plus_ueber_start", "typen": ["winning_days"], "von": 20000, "bis": 30000, "kauf_groesse": 150000,
               "kauf_stufe": "challenge", "kauf_einheit": "150k Select"}
    fd = [{"account_id": "f", "typ": "funded", "groesse": 150000, "balance": 150000, "alter_tage": 0}]
    qc = zelle(ziel_tr, TRADEIFY, fd, "frei", param={"kauf_regel": "erwartung"})
    pbig = 4500 / 19000
    pruef("c) Tradeify-Funded zählt mit 14.500 × 23,7 % zum Bestand", (qc["bestand_gewichtet"], qc["konten"][0]["anteilig"],
          qc["unterwegs_n"]), (round(14500 * pbig, 2), True, 1))
    pruef("c) aus: Funded bleibt reiner Funnel", zelle(ziel_tr, TRADEIFY, fd, "frei", param={"funded_anteilig": False, "kauf_regel": "erwartung"})["bestand_gewichtet"], 0.0)
    pruef("c) erwartet gleich (nur umgebucht)", zelle(ziel_tr, TRADEIFY, fd, "frei", param={"funded_anteilig": False, "kauf_regel": "erwartung"})["erwartet"],
          qc["erwartet"])
    sz = ns["vorrat_satz"]
    zf = dict(zelle(ZIEL_FN, FN, [idf[2]], "frei", param={"kauf_regel": "erwartung"}, seed=11), firma="FundedNext",
              art="groessen_summe", typen=["funded_cfd", "funded"])
    pruef("Satz: nichts im Vorrat, 1 unterwegs", sz(zf, "ID F", 2),
          "ID F hat bei FundedNext noch kein Funded-Konto (Ziel 200k in Funded) und nur 1 Konto unterwegs — deshalb 2 kaufen.")
    zw = dict(zt, firma="Tradeify", art="plus_ueber_start", typen=["winning_days"])
    pruef("Satz: Tradeify-Lücke in $ + seltene Chance in Klammern", sz(zw, "ID C", 3),
          "ID C fehlen bei Tradeify noch 1.637 $ bis zum Ziel (nichts unterwegs) — deshalb 3 kaufen "
          f"(ein neues Konto kommt nur etwa jedes {round(1 / p_neu)}. Mal durch).")
    zb2 = dict(zb, firma="FundedNext", art="groessen_summe", typen=["funded_cfd"])
    pruef("Satz: Blow-Reserve", sz(zb2, "ID A", 3).startswith("ID A hat bei FundedNext genug im Vorrat, aber keine Reserve"), True)
    tl = ns["vorrat_tagesliste"]
    def tz(uid, firma, n, best=0.0, unterwegs=0, soll=200000.0, luecke=200000.0, **kw):
        return dict({"user_id": uid, "firma": firma, "status": "frei", "sperre": None, "zustand": None,
                     "nachkauf": {"n": n, "einheit": "100k", "preis_eur": 500}, "bestand_gewichtet": best, "unterwegs_n": unterwegs,
                     "untergrenze": soll, "luecke": luecke, "chance_neu": 0.37, "wert_neu": 100000, "art": "groessen_summe",
                     "typen": ["funded_cfd"]}, **kw)
    zl = [tz("u-voll", "FundedNext", 3, best=100000, unterwegs=1, luecke=60000),
          tz("u-leer", "FundedNext", 2),
          tz("u-best", "FundedNext", 4, zustand="bestellt"),
          tz("u-paus", "FundedNext", 4, status="pausiert"),
          tz("u-sperr", "FundedNext", 4, sperre="daten_fehlen"),
          tz("u-klein", "FundedNext", 1, best=150000, unterwegs=1, luecke=10000)]
    h, lg = tl(zl, {"u-leer": "ID L", "u-voll": "ID V"}, 3)
    pruef("Tagesliste: leer zuerst, dann größte Lücke, reihum, Deckel 3 — EIN Eintrag je Zelle mit heute + rest",
          [(e["user"], e["anzahl"], e["rest"], e["stufe"]) for e in h],
          [("ID L", 1, 1, "heute"), ("ID V", 1, 2, "heute"), ("u-klein", 1, 0, "heute")])
    h2, _ = tl(zl, {"u-leer": "ID L", "u-voll": "ID V"}, 2)
    pruef("Tagesliste Deckel 2: dritte Zelle nur für später (anzahl 0, rest 1, woche)",
          [(e["user"], e["anzahl"], e["rest"], e["stufe"], e["kosten_eur"]) for e in h2],
          [("ID L", 1, 1, "heute", 500), ("ID V", 1, 2, "heute", 500), ("u-klein", 0, 1, "woche", 0)])
    pruef("Tagesliste: bestellt/pausiert/gesperrt draußen, Gesamtlücke = 6 Konten", lg, 6)
    h, _ = tl(zl, {}, 25)
    pruef("Tagesliste: genug Platz → alles heute, rest 0", (sum(e["anzahl"] for e in h if e["stufe"] == "heute"), [e["rest"] for e in h]),
          (6, [0, 0, 0]))
    pruef("Tagesliste-Eintrag: Stückpreis, Zeilenkosten, Satz", (h[0]["preis_eur"], h[0]["kosten_eur"], h[0]["satz"].endswith(".")),
          (500, 500 * h[0]["anzahl"], True))

    # ── Ziele bearbeiten (Finn 06.10.2026) ──
    zp = ns["vorrat_ziel_pruefen"]
    fn_alt = {"firma": "FundedNext", "art": "groessen_summe", "typen": ["funded_cfd"], "von": 200000, "bis": 300000}
    pruef("Ziel ändern: von/bis", zp(fn_alt, {"von": 150000, "bis": "250000"}), ({"von": 150000.0, "bis": 250000.0}, None))
    pruef("Ziel: von > bis abgelehnt", zp(fn_alt, {"von": 400000})[1], "von muss ≤ bis sein")
    pruef("Ziel: negative Zahl abgelehnt", zp(fn_alt, {"bis": -1})[1], "bis muss eine Zahl ≥ 0 sein")
    pruef("Ziel: Text statt Zahl abgelehnt", zp(fn_alt, {"von": "viel"})[1], "von muss eine Zahl ≥ 0 sein")
    pruef("Ziel: nichts zu ändern", zp(fn_alt, {})[1], "nichts zu ändern")
    pruef("Ziel: Kauf-Einheit und -Größe", zp(fn_alt, {"kauf_einheit": " 100k Stellar ", "kauf_groesse": 100000})[0],
          {"kauf_einheit": "100k Stellar", "kauf_groesse": 100000.0})
    t5_alt = {"firma": "The5%ers", "art": "stueck", "typen": ["funded_cfd"], "groessen": [{"groesse": 100000, "stueck": 1}]}
    pruef("Stück-Ziel: groessen sauber", zp(t5_alt, {"groessen": [{"groesse": "200000", "stueck": 2}, {"groesse": None, "stueck": 1}]})[0],
          {"groessen": [{"groesse": 200000.0, "stueck": 2}, {"groesse": None, "stueck": 1}]})
    pruef("Stück-Ziel: stueck keine ganze Zahl", zp(t5_alt, {"groessen": [{"groesse": 100000, "stueck": 1.5}]})[1],
          "groessen: stueck muss eine ganze Zahl ≥ 0 sein")
    pruef("Stück-Ziel: groessen leeren abgelehnt", zp(t5_alt, {"groessen": []})[1], "bei art stueck sind groessen [{groesse, stueck}] Pflicht")
    pruef("Art bleibt bei Änderung", "art" in (zp(fn_alt, {"art": "stueck", "von": 1, "bis": 2})[0] or {}), False)
    pruef("Neu: Firma mit Summen-Ziel", zp({}, {"art": "groessen_summe", "typen": ["funded_cfd"], "von": 100000, "bis": 200000}, neu=True),
          ({"art": "groessen_summe", "typen": ["funded_cfd"], "von": 100000.0, "bis": 200000.0}, None))
    pruef("Neu: falscher Typ abgelehnt", zp({}, {"art": "groessen_summe", "typen": ["gold"], "von": 1, "bis": 2}, neu=True)[1].startswith("typen muss"), True)
    pruef("Neu: ohne von/bis abgelehnt", zp({}, {"art": "plus_ueber_start", "typen": ["winning_days"]}, neu=True)[1], "von und bis sind Pflicht")

    # ── Kaufregel nominal (Standard, Finn 06.10.2026: „nie über das Ziel hinausschießen") — Kontrollfälle des Masters ──
    sn = ns["vorrat_satz_nominal"]
    NOM = {"kauf_regel": "nominal"}
    ziel_apex = {"art": "stueck", "typen": ["winning_days"], "groessen": [{"groesse": None, "stueck": 1}], "kauf_groesse": 150000,
                 "kauf_stufe": "challenge", "kauf_einheit": "150k EOD"}
    apex_k = [{"account_id": "af", "typ": "funded", "groesse": 150000, "balance": 151000, "alter_tage": 0}] + \
             [{"account_id": f"ae{i}", "typ": "challenge", "groesse": 150000, "balance": 150000, "alter_tage": 0} for i in range(2)]
    q = zelle(ziel_apex, APEX, apex_k, "frei", param=NOM)
    pruef("nominal Apex: 1 Funded + 2 Eval, Ziel 1 WD → 0, gedeckt", (q["nachkauf"]["n_roh"], q["lage"]), (0, "gedeckt"))
    pruef("… Satz", sn(dict(q, firma="Apex Trader", art="stueck", typen=["winning_days"]), "ID X", 0),
          "ID X hat bei Apex Trader 1 Funded + 2 Evaluations unterwegs — reicht für das Ziel, nichts kaufen.")
    q = zelle(ziel_tr, TRADEIFY, [], "frei", param=NOM)
    pruef("nominal Tradeify leer, Ziel 20k → 2, jetzt", (q["nachkauf"]["n_roh"], q["lage"]), (2, "jetzt"))
    pruef("… Satz", sn(dict(q, firma="Tradeify", art="plus_ueber_start", typen=["winning_days"]), "ID M", 2),
          "ID M hat bei Tradeify nichts im Vorrat und nichts unterwegs — 2 kaufen (2 × 14.500 $ ≥ 20.000 $ Ziel).")
    tr3 = [{"account_id": f"t{i}", "typ": "challenge", "groesse": 150000, "balance": 150000, "alter_tage": 0} for i in range(3)]
    q = zelle(ziel_tr, TRADEIFY, tr3, "frei", param=NOM)
    pruef("nominal Tradeify 3 im Funnel → 0", (q["nachkauf"]["n_roh"], q["lage"]), (0, "gedeckt"))
    pruef("… Reserve dünn als Hinweis, nicht als Kauf", (q["hinweise"][:1], q["score"]),
          (["Reserve dünn: was unterwegs ist, reicht nur, wenn alles durchkommt"], 20))
    q = zelle(ZIEL_FN, FN, [], "frei", param=NOM)
    pruef("nominal FundedNext leer, Ziel 200k → 2 × 100k", (q["nachkauf"]["n_roh"], q["lage"]), (2, "jetzt"))
    fn2 = [{"account_id": "v", "typ": "funded_cfd", "groesse": 100000, "balance": 101000, "alter_tage": 0},
           {"account_id": "p", "typ": "phase1", "groesse": 100000, "balance": 100000, "alter_tage": 0}]
    q = zelle(ZIEL_FN, FN, fn2, "frei", param=NOM)
    pruef("nominal FundedNext 100k Vorrat + 1 P1 100k → 0", (q["nachkauf"]["n_roh"], q["lage"]), (0, "gedeckt"))
    pruef("… Satz", sn(dict(q, firma="FundedNext", art="groessen_summe", typen=["funded_cfd"]), "ID B", 0),
          "ID B hat bei FundedNext 100k im Vorrat und 1 in Phase 1 unterwegs — reicht für das Ziel, nichts kaufen.")
    q = zelle(ZIEL_FN, FN, fn2[:1], "frei", param=NOM)
    pruef("nominal FundedNext 100k Vorrat, nichts unterwegs → 1, bald (Lücke trotz Bestand)", (q["nachkauf"]["n_roh"], q["lage"]),
          (1, "bald"))
    pruef("… Satz mit Lücke", sn(dict(q, firma="FundedNext", art="groessen_summe", typen=["funded_cfd"]), "ID B", 1),
          "ID B hat bei FundedNext 100k im Vorrat und nichts unterwegs — es fehlen noch 100k, 1 kaufen (1 × 100k).")
    tot = [{"account_id": "x", "typ": "phase1", "groesse": 100000, "balance": 89000, "alter_tage": 0}]
    pruef("nominal: Konto unter dem Boden zählt nicht", zelle(ZIEL_FN, FN, tot, "frei", param=NOM)["nachkauf"]["n_roh"], 2)
    pruef("nominal: kein Mindest-Funnel über der Untergrenze", zelle(dict(ZIEL_FN, von=100000), FN, gedeckt[:2], "frei", param=NOM)["nachkauf"]["n_roh"], 0)

    # ── Kaufregel mitte (Standard, Finn 06.10.2026 abends) — Kontrollfälle des Masters ──
    pruef("Standard: kauf_regel sicherheit 25 %, mitte-g 0,5", (ns["VORRAT2_STD"]["kauf_regel"], ns["VORRAT2_STD"]["sicherheit"], ns["VORRAT2_STD"]["mitte"]), ("sicherheit", 0.25, 0.5))
    q = zelleM(ziel_apex, APEX, apex_k, "frei")
    pruef("mitte Apex: 1 Funded + 2 Eval, Ziel 1 WD → 0", (q["nachkauf"]["n_roh"], q["lage"]), (0, "gedeckt"))
    pruef("… Satz ohne Rechnung", ns["vorrat_satz"](dict(q, firma="Apex Trader", art="stueck", typen=["winning_days"]), "ID X", 0),
          "ID X hat bei Apex Trader 1 Funded + 2 Evaluations unterwegs — reicht, nichts kaufen.")
    q = zelleM(ziel_tr, TRADEIFY, [], "frei")
    pruef("mitte Tradeify leer, Ziel 20k → 3, jetzt", (q["nachkauf"]["n_roh"], q["lage"]), (3, "jetzt"))
    pruef("… Satz", ns["vorrat_satz"](dict(q, firma="Tradeify", art="plus_ueber_start", typen=["winning_days"]), "ID M", 3),
          "ID M hat bei Tradeify nichts im Vorrat und nichts unterwegs — 3 kaufen.")
    pruef("mitte Tradeify 3 frische Challenges → 0", zelleM(ziel_tr, TRADEIFY, tr3, "frei")["nachkauf"]["n_roh"], 0)
    q = zelleM(ziel_tr, TRADEIFY, tr3[:2], "frei")
    pruef("mitte Tradeify 2 frische → 1, bald", (q["nachkauf"]["n_roh"], q["lage"]), (1, "bald"))
    pruef("… Satz", ns["vorrat_satz"](dict(q, firma="Tradeify", art="plus_ueber_start", typen=["winning_days"]), "ID M", 1),
          "ID M hat bei Tradeify nichts im Vorrat und 2 Challenges unterwegs — das reicht noch nicht, 1 kaufen.")
    w2 = 0.5 + 0.5 * p_neu
    r = q["rechnung"]
    pruef("Box: Gewicht/zählt je Konto (2 frische Tradeify)", (round(q["konten"][0]["gewicht"], 4), q["konten"][0]["zaehlt_usd"]),
          (round(w2, 4), round(w2 * 14500, 2)))
    pruef("Box: Rechnung der Zelle", (r["kauf_regel"], r["mitte"], r["untergrenze"], r["bestand"], r["funnel_zaehlt"], r["zaehlt_neu_usd"],
          r["luecke"], r["n"]), ("mitte", 0.5, 20000.0, 0.0, round(2 * w2 * 14500, 2), round(w2 * 14500, 2),
          round(20000 - 2 * w2 * 14500, 2), 1))
    # Toleranz (Finn 06.10.2026: Tradeify +20k — 18k passt, ab ~16k nachkaufen), Standard 15 %
    def wd(b):
        return [{"account_id": f"w{b}", "typ": "winning_days", "groesse": 150000, "balance": 150000 + b, "alter_tage": 0}]
    q = zelleM(ziel_tr, TRADEIFY, wd(18362), "frei")
    pruef("Toleranz: Tradeify 18.362, Funnel leer → 0, gedeckt", (q["nachkauf"]["n_roh"], q["lage"], q["toleranz"]), (0, "gedeckt", True))
    pruef("… Satz", ns["vorrat_satz"](dict(q, firma="Tradeify", art="plus_ueber_start", typen=["winning_days"]), "ID C", 0),
          "ID C hat bei Tradeify 18.362 $ von 20.000 $ — nah genug am Ziel, nichts kaufen.")
    pruef("Toleranz: 16.000 → 1 (bis zur vollen Untergrenze)", zelleM(ziel_tr, TRADEIFY, wd(16000), "frei")["nachkauf"]["n_roh"], 1)
    pruef("Toleranz: 12.000 → 2", zelleM(ziel_tr, TRADEIFY, wd(12000), "frei")["nachkauf"]["n_roh"], 2)
    pruef("Toleranz: Schwelle 17.000 in der Rechnung", (q["rechnung"]["toleranz_pct"], q["rechnung"]["schwelle"]), (15.0, 17000.0))
    pruef("Toleranz 0 → 18.362 kauft 1", zelleM(ziel_tr, TRADEIFY, wd(18362), "frei", param={"toleranz_pct": 0})["nachkauf"]["n_roh"], 1)
    pruef("Toleranz gilt nicht bei Stück-Zielen", zelleM(ZIEL_T5, T5, t5, "frei")["toleranz"], False)
    fn150 = [{"account_id": "a", "typ": "funded_cfd", "groesse": 100000, "balance": 101000, "alter_tage": 0},
             {"account_id": "b", "typ": "funded_cfd", "groesse": 50000, "balance": 51000, "alter_tage": 0}]
    q = zelleM(dict(ZIEL_FN, von=175000), FN, fn150, "frei")
    pruef("Toleranz bei Summen-Zielen: FundedNext 150k gegen 175k (Schwelle 148.750) → 0", (q["nachkauf"]["n_roh"], q["toleranz"]), (0, True))
    # Overall-Score (Finn 06.10.2026)
    vg = ns["vorrat_gesamt"]
    def gz(best, funnel, soll, status="frei", sperre=None, n=0):
        return {"status": status, "sperre": sperre, "nachkauf": {"n": n},
                "rechnung": {"bestand": best, "funnel_zaehlt": funnel, "untergrenze": soll}}
    zg = [gz(0, 0, 20000, n=3), gz(10000, 5000, 20000, n=1), gz(300000, 0, 200000), gz(1, 0, 1),
          gz(0, 0, 1, status="pausiert", n=5), gz(0, 0, 200000, sperre="daten_fehlen")]
    hz = [{"stufe": "heute", "anzahl": 3, "kosten_eur": 645}, {"stufe": "woche", "anzahl": 1, "kosten_eur": 215}]
    r = vg(zg, hz, 40)
    pruef("Gesamt: Abdeckung = Mittel (0 + 0,75 + 1 + 1) ÷ 4, pausiert/gesperrt draußen", (r["abdeckung_pct"], r["zellen"]), (68.8, 4))
    pruef("Gesamt: Score 31 = mittel, Trend aus dem vorigen Lauf", (r["score"], r["wort"], r["trend"]), (31, "mittel", 40))
    pruef("Gesamt: Käufe heute/gesamt, Kosten heute", (r["kaeufe_heute"], r["kaeufe_gesamt"], r["kosten_heute_eur"]), (3, 4, 645))
    pruef("Gesamt: Wort-Grenzen", [vg([gz(b_, 0, 100)])["wort"] for b_ in (100, 76, 75, 51, 50, 26, 25, 0)],
          ["entspannt", "entspannt", "mittel", "mittel", "dringend", "dringend", "sehr dringend", "sehr dringend"])
    pruef("Gesamt: ohne Zellen → None", (vg([])["score"], vg([])["wort"]), (None, None))
    # ── Tages-Tempo, „eins vor", Fakten, KI (Master 06.10.2026, Leitfaden) ──
    q = zelleM(ziel_tr, TRADEIFY, [], "frei")
    pruef("Tagesrate Futures leer (Abdeckung 0) → 3", (q["tagesrate"], q["abdeckung"]), (3, 0.0))
    q = zelleM(ziel_tr, TRADEIFY, wd(12000), "frei")
    pruef("Tagesrate Futures 60 % → 1", (q["tagesrate"], q["abdeckung"]), (1, 0.6))
    pruef("Tagesrate Futures 18.362 (> 85 %) → 0", zelleM(ziel_tr, TRADEIFY, wd(18362), "frei")["tagesrate"], 0)
    pruef("Tagesrate CFD leer → 2", zelleM(ZIEL_FN, FN, [], "frei")["tagesrate"], 2)
    APEX_K = dict(APEX, _key="apextrader")
    q = zelleM(ziel_apex, APEX_K, [{"account_id": "a", "typ": "funded", "groesse": 150000, "balance": 146500, "alter_tage": 0}], "frei")
    pruef("Apex angefressen (lebt noch) → Tagesrate 0", q["tagesrate"], 0)
    q_apex_lebt = q["nur_eins_lebt"]
    pruef("Apex alles weg → Tagesrate 2", zelleM(ziel_apex, APEX_K, [], "frei")["tagesrate"], 2)
    eins = [{"account_id": "e", "typ": "challenge", "groesse": 150000, "balance": 157500, "alter_tage": 0}]
    q = zelleM(ziel_tr, TRADEIFY, eins, "frei")
    pruef("Tradeify-Challenge mit 1 Etappe Rest = eins vor, zählt ≥ 0,8", (q["konten"][0]["eins_vor"], q["konten"][0]["gewicht"] >= 0.8),
          (True, True))
    pruef("frische Challenge ist nicht eins vor", zelleM(ziel_tr, TRADEIFY, tr3[:1], "frei")["konten"][0]["eins_vor"], False)
    p1n = [{"account_id": "n", "typ": "phase1", "groesse": 100000, "balance": 106000, "alter_tage": 0}]
    pruef("CFD-Phase nahe am Ziel (16/18 = 89 %) = eins vor", zelleM(ZIEL_FN, FN, p1n, "frei")["konten"][0]["eins_vor"], True)
    kvb = [{"account_id": "k", "typ": "phase1", "groesse": 100000, "balance": 91000, "alter_tage": 0}]
    pruef("CFD-Phase 1.000 vor Boden = kurz vor Blow", zelleM(ZIEL_FN, FN, kvb, "frei")["konten"][0]["kurz_vor_blow"], True)
    ft = ns["vorrat_fakten_text"]
    q = zelleM(ziel_tr, TRADEIFY, wd(18362) + eins, "frei")
    txt = ft(q, "ID A", "Tradeify", ziel_tr)
    pruef("Fakten: Kopf, Vorrat, Unterwegs, Regel", [txt.split("\n")[i].split(" ")[0] for i in range(4)], ["ID", "Vorrat:", "Unterwegs:", "Regel:"])
    pruef("Fakten: eins vor + Abstände in $", ("eins vor der nächsten Stufe" in txt, "bis Boden 4.500 $" in txt), (True, True))
    pruef("Fakten: pausiert", ft(q, "ID A", "Tradeify", ziel_tr, "pausiert").endswith("Zelle pausiert — nicht kaufen."), True)
    kp = ns["vorrat_ki_pruefen"]
    lz = [{"user_id": "a", "firma": "Tradeify", "status": "frei"}, {"user_id": "a", "firma": "FundingPips", "status": "frei"},
          {"user_id": "c", "firma": "Apex Trader", "status": "frei"}, {"user_id": "c", "firma": "FTMO", "status": "pausiert"},
          {"user_id": "d", "firma": "FundedNext", "status": "frei", "sperre": "daten_fehlen"}]
    finn = {"a|Tradeify": {"heute": 0, "prio": "niedrig", "satz": "18k von 20k — passt perfekt, nichts kaufen."},
            "a|FundingPips": {"heute": 2, "einheit": "100k 2-Step", "prio": "hoch", "satz": "Nur 1 × 50k Funded — heute 2 × 100k."},
            "c|Apex Trader": {"heute": 0, "prio": "niedrig", "satz": "Alles angefressen, aber es lebt noch — nichts kaufen."}}
    sauber, f = kp(lz, finn)
    pruef("KI: Finns Beispiele gültig", (f, sauber["a|FundingPips"]["heute"], sauber["c|Apex Trader"]["heute"]), (None, 2, 0))
    pruef("KI: Summe > 30 → Fehler", kp(lz, {"a|Tradeify": {"heute": 5}, **{f"a|FundingPips": {"heute": 5}}}, max_summe=8)[1],
          "zusammen 10 Käufe — höchstens 8 am Tag")
    pruef("KI: heute 6 → Fehler", kp(lz, {"a|Tradeify": {"heute": 6}})[1], "Zeile 'a|Tradeify': heute muss eine ganze Zahl 0–5 sein")
    pruef("KI: pausierte Zelle → Fehler", kp(lz, {"c|FTMO": {"heute": 0}})[1].endswith("ist pausiert — keine Empfehlung"), True)
    pruef("KI: ohne Lesung nur 0", kp(lz, {"d|FundedNext": {"heute": 1}})[1].endswith("(heute muss 0 sein)"), True)
    pruef("KI: unbekannte Zelle → Fehler", kp(lz, {"x|Tradeify": {"heute": 1}})[1].startswith("Zelle 'x|Tradeify' gibt es"), True)
    pruef("KI: Apex lebt noch → nur 0 erlaubt", kp([{"user_id": "c", "firma": "Apex Trader", "status": "frei", "nur_eins_lebt": True}],
          {"c|Apex Trader": {"heute": 2}})[1].endswith("heute nichts kaufen (heute muss 0 sein)"), True)
    pruef("Apex angefressen: Zelle merkt sich „lebt noch\"", q_apex_lebt, True)
    pruef("KI: falsche prio → Fehler", kp(lz, {"a|Tradeify": {"heute": 1, "prio": "sofort"}})[1].endswith("hoch, mittel oder niedrig sein"), True)
    ka = ns["vorrat_ki_anwenden"]
    zz = [{"user_id": "a", "firma": "Tradeify", "status": "frei", "score": 10, "nachkauf": {"preis_eur": 215, "einheit": "150k"}},
          {"user_id": "a", "firma": "FundingPips", "status": "frei", "score": 80, "nachkauf": {"preis_eur": 464, "einheit": "100k"}},
          {"user_id": "c", "firma": "Apex Trader", "status": "frei", "score": 90, "nachkauf": {"preis_eur": 150}},
          {"user_id": "e", "firma": "FTMO", "status": "frei", "score": 50, "nachkauf": {"preis_eur": 446}}]
    h = ka(zz, dict(sauber, **{"e|FTMO": {"heute": 1, "prio": "mittel", "satz": "1 × 100k."}}), {"a": "ID A"}, "2026-10-06T17:00:00Z")
    pruef("KI: heute nur mit heute > 0, Reihenfolge prio, Apex 0 bleibt 0",
          [(e["firma"], e["anzahl"], e["quelle"], e["kosten_eur"]) for e in h], [("FundingPips", 2, "ki", 928), ("FTMO", 1, "ki", 446)])
    pruef("KI: Satz und Quelle je Zelle, unbewertet = regel", [(z["firma"], z["quelle"], z.get("satz", "")[:5]) for z in zz],
          [("Tradeify", "ki", "18k v"), ("FundingPips", "ki", "Nur 1"), ("Apex Trader", "ki", "Alles"), ("FTMO", "ki", "1 × 1")])
    zz2 = [{"user_id": "z", "firma": "Topstep", "status": "frei", "nachkauf": {}}]
    ka(zz2, {}, {}, None)
    pruef("KI: ohne Zeile → quelle regel", zz2[0]["quelle"], "regel")
    zb_ = [dict(zz[1], zustand="bestellt")]
    pruef("KI: bestellt → nicht in heute", ka(zb_, sauber, {}, None), [])
    # ── Hauptregel 25 % (Standard, Finn 06.10.2026 spät) — Kontrollfälle des Masters ──
    q = zelle(ziel_apex, APEX, apex_k, "frei")
    pruef("25 %: Apex 1 Funded + 2 Eval (≈ 23 %) → 1", (q["nachkauf"]["n_roh"], round(q["sicherheit"], 2) < 0.25, q["sicherheit_nach"] >= 0.25),
          (1, True, True))
    pruef("25 %: Apex läuft ohne Ausnahme über die Tagesrate der Futures", (q["tagesrate"], q["nur_eins_lebt"]), (3, False))
    q = zelle(ziel_tr, TRADEIFY, wd(18362), "frei")
    pruef("25 %: Tradeify 18.362 → 0 (Toleranz)", (q["nachkauf"]["n_roh"], q["toleranz"]), (0, True))
    q = zelle(ziel_tr, TRADEIFY, [], "frei")
    pruef("25 %: Tradeify leer → Deckel 10 (zwei Erfolge à 14.500 nötig, je ≈ 5 %)", (q["nachkauf"]["n_roh"], q["hinweise"][-1][:6]), (10, "Deckel"))
    q = zelle(ZIEL_FN, FN, [], "frei")
    pruef("25 %: FundedNext leer, Ziel 200k → 3 × 100k (2 ergäben nur 14 %)", (q["nachkauf"]["n_roh"], q["sicherheit_nach"] >= 0.25), (3, True))
    pruef("25 %: FundedNext 100k + 1 P1 → 0 (37 % ≥ 25 %)", zelle(ZIEL_FN, FN, fn2, "frei")["nachkauf"]["n_roh"], 0)
    pruef("25 %: kein Mindest-Funnel", zelle(dict(ZIEL_FN, von=100000), FN, gedeckt[:2], "frei")["nachkauf"]["n_roh"], 0)
    # FTMO „100k oder 200k" konkret (Finn 06.10.2026)
    ftmo_st = ns["vorrat_stufen_aus_kernwerten"](ns["ap_regel_finden"](KERN, "FTMO"))
    kw_ftmo = ns["ap_kw_param"](ns["ap_regel_finden"](KERN, "FTMO"))
    ziel_ftmo = {"art": "groessen_summe", "typen": ["funded_cfd", "funded"], "von": 100000, "bis": 200000, "kauf_groesse": 100000,
                 "kauf_einheit": "100k oder 200k"}
    q = zelle(ziel_ftmo, ftmo_st, [], "frei", kw=kw_ftmo)
    pruef("FTMO leer, Ziel 100k: 1 × 100k (Kette 33 % ≥ 25 %), Einheit konkret", (q["nachkauf"]["n_roh"], q["nachkauf"]["einheit"]), (1, "100k"))
    q = zelle(dict(ziel_ftmo, von=200000, bis=300000), ftmo_st, [], "frei", kw=kw_ftmo)
    pruef("FTMO Lücke 200k → Einheit 200k", (q["nachkauf"]["einheit"], q["nachkauf"]["preis_eur"]), ("200k", 892))
    # Score je Person / je Firma (Finn 06.10.2026)
    sg = ns["vorrat_score_gruppen"]
    def gz2(uid, firma, best, soll, status="frei", n=0, sperre=None):
        return {"user_id": uid, "firma": firma, "status": status, "sperre": sperre, "nachkauf": {"n": n},
                "rechnung": {"bestand": best, "funnel_zaehlt": 0, "untergrenze": soll}}
    zg2 = [gz2("a", "Tradeify", 0, 20000, n=3), gz2("a", "FTMO", 100000, 100000), gz2("b", "Tradeify", 15000, 20000, n=1),
           gz2("c", "FTMO", 0, 100000, status="pausiert", n=1)]
    hz2 = [{"user_id": "a", "firma": "Tradeify", "stufe": "heute", "anzahl": 3, "kosten_eur": 645},
           {"user_id": "b", "firma": "Tradeify", "stufe": "heute", "anzahl": 1, "kosten_eur": 215}]
    r = sg(zg2, hz2, "user_id")
    pruef("Score je Person: A (0 % + 100 %) → 50 dringend, heute 3, gesamt 3", r["a"], {"score": 50, "wort": "dringend",
          "abdeckung_pct": 50.0, "heute": 3, "gesamt": 3})
    pruef("Score je Person: B 75 % → 25 mittel", (r["b"]["score"], r["b"]["wort"]), (25, "mittel"))
    pruef("Score je Person: nur pausiert → —", (r["c"]["score"], r["c"]["wort"], r["c"]["gesamt"]), (None, "—", 0))
    r = sg(zg2, hz2, "firma")
    pruef("Score je Firma: Tradeify (0 % + 75 %) → 63, heute 4, gesamt 4", (r["Tradeify"]["score"], r["Tradeify"]["heute"],
          r["Tradeify"]["gesamt"]), (63, 4, 4))
    pruef("Score je Firma: FTMO nur A (100 %) → 0 entspannt", (r["FTMO"]["score"], r["FTMO"]["wort"]), (0, "entspannt"))
    # KI-Hinweise (Finn 06.10.2026)
    kh = ns["vorrat_ki_hinweis"]
    l1, f = kh([], " Tradeify diese Woche ruhiger angehen ", "u", "2026-10-06T17:00Z", "h1")
    pruef("KI-Hinweis anlegen (Text getrimmt)", (f, l1), (None, [{"id": "h1", "text": "Tradeify diese Woche ruhiger angehen", "von": "u",
          "at": "2026-10-06T17:00Z"}]))
    pruef("KI-Hinweis leer → Fehler", kh(l1, "  ", "u", "x", "h2")[1], "text fehlt")
    pruef("KI-Hinweis > 300 Zeichen → Fehler", kh(l1, "x" * 301, "u", "x", "h2")[1], "text höchstens 300 Zeichen")
    voll = [{"id": f"a{i}", "text": "t"} for i in range(50)]
    l2, _ = kh(voll, "neu", "u", "x", "neu")
    pruef("KI-Hinweise höchstens 50, ältester fällt raus", (len(l2), l2[0]["id"], l2[-1]["id"]), (50, "a1", "neu"))
    rs = ns["vorrat_regel_satz"]
    pruef("Regel-Satz mitte 0,5", rs("mitte", 0.5).startswith("Jedes laufende Konto zählt halb so, als käme es sicher durch, und halb mit"), True)
    pruef("Regel-Satz mitte 0,7", "zu 70 % so, als käme es sicher durch, und zu 30 %" in rs("mitte", 0.7), True)
    pruef("Regel-Satz Sicherheit", rs("sicherheit", sicherheit=0.8).startswith("Es wird so viel gekauft, dass das Ziel mit 80 %"), True)
    pruef("mitte FundedNext leer, Ziel 200k → 3 × 100k", zelleM(ZIEL_FN, FN, [], "frei")["nachkauf"]["n_roh"], 3)
    pruef("mitte FundedNext 100k Vorrat + 1 P1 → 1", zelleM(ZIEL_FN, FN, fn2, "frei")["nachkauf"]["n_roh"], 1)
    pruef("mitte g = 1 wie nominal (FundedNext 100k + P1 → 0)", zelleM(ZIEL_FN, FN, fn2, "frei", param={"mitte": 1})["nachkauf"]["n_roh"], 0)
    pruef("mitte g = 0 wie erwartung (Tradeify leer)", zelleM(ziel_tr, TRADEIFY, [], "frei", param={"mitte": 0})["nachkauf"]["n_roh"],
          zelleM(ziel_tr, TRADEIFY, [], "frei", param={"kauf_regel": "erwartung"})["nachkauf"]["n_roh"])
    pruef("mitte: Konto unter dem Boden zählt nicht", zelleM(ZIEL_FN, FN, tot, "frei")["nachkauf"]["n_roh"], 3)

    # ── Zusammenfassung je Person (06.10.2026 live: „alles gedeckt" bei pausiert bzw. ohne Lesung) ──
    vp = ns["vorrat_personen"]
    def pz(uid, firma, status="frei", n=0, sperre=None):
        return {"user_id": uid, "firma": firma, "status": status, "sperre": sperre, "nachkauf": {"n": n}}
    zl = [pz("m", f, "pausiert") for f in ("A", "B", "C")] + \
         [pz("p", "A", "gesperrt"), pz("p", "B", sperre="daten_fehlen"), pz("p", "C", sperre="daten_fehlen")] + \
         [pz("g", "A"), pz("g", "B", "pausiert")] + [pz("k", "A", n=2), pz("k", "B", sperre="unsicher")] + \
         [pz("x", "A", "pausiert"), pz("x", "B", "gesperrt")]
    r = {e["user_id"]: (e["zustand"], e["text"]) for e in vp(zl, {})}
    pruef("Person: alles pausiert ist nicht gedeckt", r["m"], ("pausiert", "alles pausiert"))
    pruef("Person: nur ohne Lesung → kein Vorschlag", r["p"], ("daten_fehlen", "kein Vorschlag — 2 Firmen ohne aktuelle Lesung · 1 Firma pausiert/gesperrt"))
    pruef("Person: gedeckt nur, wenn gerechnet und gedeckt", r["g"], ("gedeckt", "gedeckt · 1 Firma pausiert/gesperrt"))
    pruef("Person: kaufen mit Hinweis", r["k"], ("kaufen", "2 kaufen · 1 Firma ohne aktuelle Lesung"))
    pruef("Person: gemischt pausiert/gesperrt", r["x"], ("pausiert_gesperrt", "alles pausiert/gesperrt (1 pausiert, 1 gesperrt)"))

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
    f31 = [("Tradeify", "challenge", "bestanden")] * 5 + [("Tradeify", "challenge", "geblowt")] * 26
    r = ns["vorrat_quoten"](f31, {"Tradeify": S["Tradeify"]})[("Tradeify", "challenge")]
    p_ch = (4500 / 8100) ** 2 * (4500 / 6300)
    pruef("Quoten Tradeify (live 06.10.): Formel bei 150k = 22 %, nicht 36 % (100k)", round(r["formel"], 6), round(p_ch, 6))
    pruef("… Faktor = (31/51 × 5/31 + 20/51 × 22 %) ÷ 22 %", r["faktor"], ((31 / 51) * (5 / 31) + (20 / 51) * p_ch) / p_ch, 1e-9)
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
