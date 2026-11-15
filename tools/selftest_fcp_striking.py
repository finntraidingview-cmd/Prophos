#!/usr/bin/env python3
"""Selbsttest ST1 (Master 15.11.2026, Finns FundingPips-Regeln): Add-on „Striking“ für FundingPips Funded CFD (app.py FCP_STRIKING_STANDARD,
fcp_striking_regel, fcp_striking_anwenden, fcp_max_sl, Gewinntag-SL in fcp_konto_rechnen, Verdrahtung fcp_planen / kz_rechnen / zw_funded_cfd,
fcp_regel_patch striking.*; prophos.html Chip + Name + Einstellung).
Kern: (1) DIFF-TEST gegen origin/main — ohne Striking rechnet fcp_konto_rechnen für FundedNext, The5ers, Blue Guardian, FTMO und FundingPips bitgleich
(gleicher Zufalls-Verbrauch); (2) Striking: erst 7 Gewinntage ≥ 0,5 % (je Tag ein Trade, TP 550–750 / SL 700–800 je 100k), gesammelt auch über das
Ziel hinaus, Verlusttage zählen nicht; danach Consistency 35 % (Payout-Trade gedeckelt: W 4.550 → höchstens ≈ 2.450); jeder Trade SL < 1 % der Größe.
Ohne Netz, Regeln in der Form wie live (FundingPips: ziel 1.250–2.000, sl 1.300–1.600, lots 0,75–0,8 je 100k; keine Consistency, kein Refund).
Aufruf: python3 tools/selftest_fcp_striking.py"""
import copy
import importlib.util
import json
import os
import random
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


FN = {"an": True, "name": "FundedNext", "namen": ["fundednext"], "tp_deckel_plus": 1000,
      "erster_payout": {"ziel": [50, 150], "hedge_eur_je_dd": 0.5, "lots_faktor": 0.1},
      "je_groesse": {"100000": {"dd": 10000, "sl": [2000, 2300], "sl_1pct": [700, 780], "lots": [1.0, 1.75], "ziel": [5000, 5500], "hedge_eur": 1500}}}
T5 = {"an": True, "name": "The5%ers", "namen": ["the5ers"], "tp_modus": "consistency50", "tp_zyklen": [750, 1500, 3000, 6000],
      "je_groesse": {"100000": {"dd": 10000, "sl": [1000, 1200], "lots": [1.0, 1.4], "ziel": [1300, 1500], "hedge_eur": 1000, "tp_erster": 750}}}
BG = {"an": True, "name": "Blue Guardian", "namen": ["blueguardian"], "erster_payout": {"ziel": [50, 100], "hedge_eur_je_dd": 0.5},
      "je_groesse": {"100000": {"dd": 8000, "sl": [1500, 1800], "lots": [1.0, 1.2], "ziel": [1000, 1200], "hedge_eur": 1000,
                                "gewinntage": {"anzahl": 3, "min": 500, "tp": [550, 650]}}}}
FT = {"an": True, "name": "FTMO", "namen": ["ftmo"], "je_groesse": {"100000": {"dd": 10000, "sl": [1500, 2000], "lots": [1.0, 1.5], "ziel": [1500, 2500], "hedge_eur": 1200}}}
FP = {"an": True, "name": "FundingPips", "namen": ["fundingpips"], "consistency_pct": 0, "ohne_namen": ["flex"],
      "je_groesse": {"100000": {"dd": 10000, "sl": [1300, 1600], "lots": [0.75, 0.8], "ziel": [1250, 2000], "hedge_eur": 2000},
                     "50000": {"dd": 5000, "sl": [650, 800], "lots": [0.375, 0.4], "ziel": [625, 1000], "hedge_eur": 1000}}}
JG = app.fcp_je_groesse
R = app.fcp_konto_rechnen

print("— 1) Diff-Test gegen origin/main: ohne Striking bitgleich —")
alt = None
try:
    src_alt = subprocess.run(["git", "-C", WURZEL, "show", "origin/main:app.py"], capture_output=True, text=True, timeout=60, check=True).stdout
    d = tempfile.mkdtemp(prefix="st1_alt_")
    pfad = os.path.join(d, "app_alt_st1.py")
    with open(pfad, "w", encoding="utf-8") as fh:
        fh.write(src_alt)
    spec = importlib.util.spec_from_file_location("app_alt_st1", pfad)
    alt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(alt)
except Exception as e:  # noqa: BLE001
    print(f"   origin/main nicht ladbar: {type(e).__name__}: {e}")
ok(alt is not None and not hasattr(alt, "fcp_striking_regel"), "origin/main geladen (ohne Striking) als Vergleich")
faelle = abw = rnd_abw = 0
if alt is not None:
    for regel in (FN, T5, BG, FT, FP):
        jg = JG(regel, 100000)
        for bal in (97000, 99800, 100000, 100300, 100700, 101250, 102200, 104000):
            for zyk in (1, 2, 3):
                for tage in (None, (0.0, 0), {"b": 500.0, "w": 900.0, "n": 2, "serie": 900.0, "serie_n": 2}):
                    for gti in ((None, (0, 3), (3, 3)) if regel is BG else (None,)):
                        for eins, ms in ((False, None), (True, 1000), (False, 900)):
                            for seed in (1, 7, 42):
                                kw = dict(regel=regel, gewinne=None, gewinntage=gti, tage=tage, max_sl=ms)
                                ra, rb = random.Random(seed), random.Random(seed)
                                a = R(jg, bal, 100000, zyk, eins, 1.0, 0.85, ra, **kw)
                                b = alt.fcp_konto_rechnen(alt.fcp_je_groesse(regel, 100000), bal, 100000, zyk, eins, 1.0, 0.85, rb, **kw)
                                faelle += 1
                                if a != b:
                                    abw += 1
                                if ra.random() != rb.random():
                                    rnd_abw += 1
    ok(faelle > 3000 and abw == 0, f"{faelle} Fälle (FundedNext, The5ers, Blue Guardian, FTMO, FundingPips): Ergebnis wie origin/main ({abw} Abweichungen)")
    ok(rnd_abw == 0, f"gleicher Zufalls-Verbrauch — weitere Würfe im Lauf bleiben gleich ({rnd_abw} Abweichungen)")
    zb_abw = sum(1 for r_ in (FN, T5, BG, FT, FP) for z in (1, 2) for od in (False, True)
                 if app.fcp_konto_ziel_boden(r_, 100000, z, "100k X", on_demand=od) != alt.fcp_konto_ziel_boden(r_, 100000, z, "100k X", on_demand=od))
    ok(zb_abw == 0, "fcp_konto_ziel_boden (Radar-Ziel) unverändert")
    e_abw = sum(1 for r_ in (FN, T5, BG, FT, FP) if {k: v for k, v in app.fcp_firma_einstellung(r_).items() if k not in ("striking", "striking_eff")}
                != alt.fcp_firma_einstellung(r_))
    ok(e_abw == 0, "fcp_firma_einstellung: alte Felder unverändert, nur striking/striking_eff dazu")
    p_abw = 0
    for body in ({"firma": "FundedNext", "feld": "on_demand.consistency_pct", "wert": 35}, {"firma": "FundingPips", "feld": "on_demand.consistency_pct", "wert": 35},
                 {"firma": "FundingPips", "feld": "ohne_namen", "wert": ["flex", "abc"]}, {"firma": "FundingPips", "feld": "quatsch", "wert": 1}):
        z0 = {"id": 1, "firmen": [copy.deepcopy(FN), copy.deepcopy(FP)]}
        if app.fcp_regel_patch(copy.deepcopy(z0), body) != alt.fcp_regel_patch(copy.deepcopy(z0), body):
            p_abw += 1
    ok(p_abw == 0, "fcp_regel_patch: bisherige Felder (on_demand.*, ohne_namen, unbekannt) unverändert")

print("— 2) Striking-Regel —")
st = app.fcp_striking_regel(FP)
ok(st == {"gewinntage_anzahl": 7, "gewinntag_min_je_100k": 500.0, "consistency_pct": 35.0, "tp_je_100k": [550.0, 750.0], "sl_je_100k": [700.0, 800.0],
          "verlust_max_pct": 1.0}, f"FundingPips Code-Standard {st}")
ok(app.fcp_striking_regel(dict(FP, striking={"consistency_pct": 30}))["consistency_pct"] == 30.0
   and app.fcp_striking_regel(dict(FP, striking={"consistency_pct": 30}))["gewinntage_anzahl"] == 7, "Override je Feld über dem Standard (Rest bleibt)")
ok(app.fcp_striking_regel(dict(FP, striking=False)) is None, "striking: false = keine Striking-Regel")
ok(all(app.fcp_striking_regel(r_) is None for r_ in (FN, T5, BG, FT)), "andere Firmen ohne Striking-Regel")
ok(app.fcp_striking_regel(dict(FP, striking={"tp_je_100k": [0, 0]})) is None, "kaputter Wert → None (nie halb gültig)")
for g, mn, tp, sl, dk in ((100000, 500.0, [550.0, 750.0], [700.0, 800.0], 950.0), (50000, 250.0, [275.0, 375.0], [350.0, 400.0], 475.0),
                          (200000, 1000.0, [1100.0, 1500.0], [1400.0, 1600.0], 1900.0)):
    r2, jg2, deckel = app.fcp_striking_anwenden(FP, JG(FP, g) or JG(FP, 100000), g)
    ok(jg2["gewinntage"] == {"anzahl": 7, "min": mn, "tp": tp, "sl": sl, "cons_mit": True} and deckel == dk, f"{g // 1000}k: 7 × ≥ {mn:g} $, TP {tp}, SL {sl}, SL-Deckel {dk:g} $")
r2, jg2, deckel = app.fcp_striking_anwenden(FP, JG(FP, 100000), 100000)
ok(app.fcp_consistency_pct(r2) == 35.0 and app.fcp_erster_payout(r2) is None and jg2["ziel"] == [1250, 2000] and jg2["sl"] == [1300, 1600]
   and jg2["lots"] == [0.75, 0.8] and jg2["hedge_eur"] == 2000, "Consistency 35 %, kein Refund; Ziel/SL/Lots/Hedge der Größe bleiben")
ok("striking" not in FP and "gewinntage" not in FP["je_groesse"]["100000"], "Regel selbst unverändert (Kopie)")
ok(app.fcp_striking_anwenden(BG, JG(BG, 100000), 100000) is None and app.fcp_striking_anwenden(FP, JG(FP, 100000), None) is None,
   "Firma ohne Regel / Größe fehlt → None (Planer plant normal)")
ok(app.fcp_max_sl(None, 950) == 950 and app.fcp_max_sl(1000, 950) == 950 and app.fcp_max_sl(800, 950) == 800 and app.fcp_max_sl(None, None) is None,
   "SL-Deckel: das engere von 1 % Rule (max_risiko_trade) und Striking")

print("— 3) Phase A: 7 Gewinntage sammeln, auch über das Ziel hinaus —")
MS = app.fcp_max_sl(None, deckel)
fehl = []
for seed in range(40):
    for bal, ist in ((100000, 0), (100600, 1), (102000, 3), (103900, 6), (99200, 2)):
        r = R(jg2, bal, 100000, 2, False, 1.0, 0.85, random.Random(seed), regel=r2, gewinntage=(ist, 7), max_sl=MS,
              tage={"b": 700.0, "w": 700.0 * ist, "n": ist, "serie": 0.0, "serie_n": 0})
        if not (r["aktion"] == "planen" and r["tp_art"] == "gewinntag" and 550 <= r["tp"] <= 750 and 700 <= r["sl"] <= 800):
            fehl.append((seed, bal, ist, r.get("aktion"), r.get("tp_art"), r.get("tp"), r.get("sl")))
ok(not fehl, f"Gewinntage 0–6 von 7 (auch Gewinn 2.000–3.900 ≥ Ziel 1.250–2.000): immer Gewinntag-Trade TP 550–750, SL 700–800 ({fehl[:2]})")
r = R(jg2, 100000, 100000, 2, False, 1.0, 0.85, random.Random(3), regel=r2, gewinntage=None, max_sl=MS)
ok(r["tp_art"] == "gewinntag", "Zählung nicht lesbar → Phase A (nie ein Ziel-Trade auf Verdacht)")
gt50 = app.fcp_striking_anwenden(FP, JG(FP, 50000), 50000)
r = R(gt50[1], 50000, 50000, 2, False, 1.0, 0.85, random.Random(5), regel=gt50[0], gewinntage=(0, 7), max_sl=app.fcp_max_sl(None, gt50[2]))
ok(r["tp_art"] == "gewinntag" and 275 <= r["tp"] <= 375 and 350 <= r["sl"] <= 400, f"50k: TP {r['tp']:g} (275–375), SL {r['sl']:g} (350–400)")
bgn = R(JG(BG, 100000), 100000, 100000, 2, False, 1.0, 0.85, random.Random(9), regel=BG, gewinntage=(0, 3))
ok(bgn["tp_art"] == "gewinntag" and 1500 <= bgn["sl"] <= 1800, "Blue Guardian (kein gt.sl): Gewinntag-SL wie bisher aus je_groesse.sl")


def plan(tag, pl):
    return {"master_account_id": "k1", "status": "completed", "master_pl": pl, "started_at": f"{tag}T08:00:00+00:00", "ended_at": f"{tag}T09:00:00+00:00"}


GTS = jg2["gewinntage"]
pl = [plan("2026-11-02", 620), plan("2026-11-03", -760), plan("2026-11-04", 499), plan("2026-11-05", 300), plan("2026-11-05", 250), plan("2026-11-06", 700)]
gi = app.fcp_gewinntage_ist(GTS, "k1", pl, "2026-11-01")
ok(gi == (3, 7), f"Zählung: 620 ✓, Verlusttag −760 ✗, 499 ✗, 300 + 250 an einem Tag ✓ (Tagessumme), 700 ✓ → 3/7 ({gi})")

print("— 3b) Consistency läuft beim Sammeln mit (Finn 15.11.2026, Basis = Summe der Gewinn-Tage) —")
SG = app.fcp_striking_gt_tp
t, c = SG(700.0, 35, GTS, (0, 7), {"b": 0.0, "w": 0.0})
ok(t == 700.0 and not c["gedeckelt"] and c["tage_offen"] == 7 and c["deckel"] == 1688.0, f"Tag 1 von 7: TP 700 bleibt (Deckel {c['deckel']:g} = 35 % × 6 × 550 ÷ 65 % × 0,95)")
t, c = SG(560.0, 35, GTS, (1, 7), {"b": 2500.0, "w": 2500.0})
ok(t == 750.0 and c["anteil"] == 1.0, f"großer Hand-Tag 2.500 schon da (100 %): TP zieht auf 750 (Bereichs-Obergrenze), damit der Zyklus schneller auf 35 % kommt ({t:g})")
GTW = dict(GTS, tp=[550.0, 2500.0], anzahl=3)
t, c = SG(2200.0, 35, GTW, (0, 3), {"b": 0.0, "w": 0.0})
ok(t == 562.0 and c["gedeckelt"], f"TP-Bereich 550–2.500 als Override, 3 Tage: TP 2.200 → gedeckelt auf {t:g} (sonst wäre der Tag nie unter 35 % zu drücken)")
t, c = SG(700.0, 35, GTS, None, None)
ok(t == 700.0 and c["lesbar"] is False, "Zyklus nicht lesbar → TP unverändert")
fehl = []
for seed in range(40):
    rg = dict(r2)
    jw = dict(jg2, gewinntage=dict(GTS, tp=[550.0, 2500.0]))
    rnd, W, B, ist = random.Random(seed), 0.0, 0.0, 0
    for _ in range(7):
        r = R(jw, 100000 + W, 100000, 2, False, 1.0, 0.85, rnd, regel=rg, gewinntage=(ist, 7), max_sl=MS, tage={"b": B, "w": W, "n": ist, "serie": W, "serie_n": ist})
        W += r["tp"]; B = max(B, r["tp"]); ist += 1
    if not (B <= 0.35 * W + 0.5):
        fehl.append((seed, B, W))
ok(not fehl, f"40 Zyklen mit TP-Bereich 550–2.500: nach 7 Gewinntagen ist der größte Tag ≤ 35 % der Summe (schon beim Sammeln gesteuert) ({fehl[:2]})")
r = R(jg2, 100000, 100000, 2, False, 1.0, 0.85, random.Random(1), regel=r2, gewinntage=(2, 7), max_sl=MS, tage={"b": 700.0, "w": 1300.0, "n": 2, "serie": 1300.0, "serie_n": 2})
ok((r.get("cons_laufend") or {}).get("anteil") == round(700 / 1300, 4) and r["cons_laufend"]["p"] == 35.0, f"laufender Stand im Ergebnis (Notiz/Plan): {r.get('cons_laufend')}")
bg2 = R(JG(BG, 100000), 100000, 100000, 2, False, 1.0, 0.85, random.Random(9), regel=dict(BG, consistency_pct=30), gewinntage=(0, 3), tage={"b": 0.0, "w": 0.0})
ok("cons_laufend" not in bg2, "Blue Guardian (ohne Striking) rechnet beim Sammeln keine laufende Consistency")

print("— 4) Simulation 100k: Verlusttage überspringen, 7 Tage, dann Consistency 35 % —")


def sim(seed, verlust_tage, max_tage=40):
    """Ein Trade je Tag; an den Tagen in verlust_tage trifft der SL. → (Liste Tage, Ergebnis)."""
    rnd, bal, plaene, log = random.Random(seed), 100000.0, [], []
    for t in range(max_tage):
        tag = f"2026-12-{t + 1:02d}" if t < 31 else f"2027-01-{t - 30:02d}"
        gi = app.fcp_gewinntage_ist(GTS, "k1", plaene, "2026-11-30")
        tw = app.fcp_tage_zyklus_w(plaene, "2026-11-30")
        r = R(jg2, bal, 100000, 2, False, 1.0, 0.85, rnd, regel=r2, gewinntage=gi, max_sl=MS, tage=tw, ziel_fest={"zyklus": 2, "usd": 1600})
        if r["aktion"] != "planen":
            log.append(("ende", r["aktion"], gi, round(bal - 100000)))
            return log, r
        pl_ = -r["sl"] if t in verlust_tage else r["tp"]
        log.append((r["tp_art"], pl_, r["sl"]))
        plaene.append(plan(tag, pl_))
        bal += pl_
    return log, None


fehl, laenge = [], []
for seed in range(30):
    vt = set(random.Random(1000 + seed).sample(range(9), 3))   # alle drei Verlusttage fallen ins Sammeln (7 Gewinne + 3 Verluste = 10 Tage)
    log, r = sim(seed, vt)
    gt_trades = [x for x in log if x[0] == "gewinntag"]
    gewinn_tage = [x for x in gt_trades if x[1] > 0]
    nach = [x for x in log if x[0] not in ("gewinntag", "ende")]
    if not (r is not None and r["aktion"] == "ziel" and len(gewinn_tage) == 7 and all(x[2] <= 950 for x in log if x[0] != "ende")
            and log.index(gewinn_tage[-1]) == len(gt_trades) - 1 and all(x[2] <= 950 for x in nach)):
        fehl.append((seed, log[-3:]))
    laenge.append(len(log) - 1)
ok(not fehl, f"30 Läufe mit 3 Verlusttagen: genau 7 Gewinntage gesammelt, dann Ziel + Consistency → Waiting; jeder SL ≤ 950 ({fehl[:1]})")
ok(min(laenge) >= 10, f"3 Verlusttage beim Sammeln → ≥ 10 Handelstage bis Waiting (min {min(laenge)}, max {max(laenge)})")
log, r = sim(4, set())
print("   Beispiel ohne Verlust:", " / ".join(f"{x[1]:g}" for x in log if x[0] != "ende"), "→", r["aktion"], r.get("consistency", {}).get("bester_tag") if r.get("consistency") else "")

print("— 5) Phase B: Consistency 35 % deckelt den Payout-Trade —")
W = 4550.0
tw = {"b": 700.0, "w": W, "n": 7, "serie": 0.0, "serie_n": 0}
fehl = []
for seed in range(40):
    r = R(jg2, 99000, 100000, 2, False, 1.0, 0.85, random.Random(seed), regel=r2, gewinntage=(7, 7), max_sl=MS, tage=tw, ziel_fest={"zyklus": 2, "usd": 2000})
    if not (r["aktion"] == "planen" and str(r["tp_art"]).startswith("consistency") and r["tp"] <= 0.35 * (W + r["tp"]) + 0.5 and r["sl"] <= 950):
        fehl.append((seed, r.get("tp_art"), r.get("tp"), r.get("sl")))
ok(not fehl, f"7 Tage, Gewinn −1.000 (Verluste), Ziel 2.000 → Rest 3.000: Payout-Trade ≤ 35 % (W 4.550 → ≤ 2.450), SL ≤ 950 ({fehl[:2]})")
r = R(jg2, 99000, 100000, 2, False, 1.0, 0.85, random.Random(1), regel=r2, gewinntage=(7, 7), max_sl=MS, tage=tw, ziel_fest={"zyklus": 2, "usd": 2000})
print(f"   Beispiel: TP {r['tp']:g} $ (Grenze {0.35 / 0.65 * W:.0f} $), SL {r['sl']:g} $, gedeckelt: {r.get('sl_gedeckelt')}")
r = R(jg2, 104550, 100000, 2, False, 1.0, 0.85, random.Random(1), regel=r2, gewinntage=(7, 7), max_sl=MS, tage=dict(tw, b=750.0), ziel_fest={"zyklus": 2, "usd": 2000})
ok(r["aktion"] == "ziel", "7 Gewinntage, +4.550 ≥ Ziel, größter Tag 750 ≤ 35 % → Ziel erreicht → Waiting")
r = R(jg2, 102500, 100000, 2, False, 1.0, 0.85, random.Random(1), regel=r2, gewinntage=(7, 7), max_sl=MS,
      tage={"b": 1800.0, "w": 4300.0, "n": 7, "serie": 0.0, "serie_n": 0}, ziel_fest={"zyklus": 2, "usd": 2000})
ok(r["aktion"] == "planen" and r["tp"] > 0, f"größter Tag 1.800 > 35 % von 4.300 → weiter planen, nicht Waiting (TP {r.get('tp')})")
r = R(jg2, 99000, 100000, 2, True, 1.0, 0.85, random.Random(2), regel=r2, gewinntage=(7, 7), max_sl=app.fcp_max_sl(800, deckel), tage=tw,
      ziel_fest={"zyklus": 2, "usd": 2000})
ok(r["sl"] <= 800, f"Striking + 1 % Rule mit max_risiko_trade 800: SL {r['sl']:g} ≤ 800 (das engere)")

print("— 6) Einstellung je Firma (Patch striking.*) —")
Z = {"id": 1, "firmen": [copy.deepcopy(FP), copy.deepcopy(FN)]}
u, f_ = app.fcp_regel_patch(copy.deepcopy(Z), {"firma": "FundingPips", "feld": "striking.gewinntage_anzahl", "wert": 8})
ok(u and u["firmen"][0]["striking"] == {"gewinntage_anzahl": 8} and app.fcp_striking_regel(u["firmen"][0])["gewinntage_anzahl"] == 8, "Gewinntage 8 → Override, Rest Standard")
u2, _ = app.fcp_regel_patch({"id": 1, "firmen": [u["firmen"][0]]}, {"firma": "FundingPips", "feld": "striking.tp_je_100k", "wert": [600, 800]})
ok(app.fcp_striking_regel(u2["firmen"][0])["tp_je_100k"] == [600.0, 800.0] and app.fcp_striking_regel(u2["firmen"][0])["gewinntage_anzahl"] == 8, "dazu TP 600–800")
u3, _ = app.fcp_regel_patch({"id": 1, "firmen": [u2["firmen"][0]]}, {"firma": "FundingPips", "feld": "striking.gewinntage_anzahl", "wert": None})
ok(u3 and u3["firmen"][0]["striking"] == {"tp_je_100k": [600.0, 800.0]}, "leer → Feld weg (Standard)")
ok(app.fcp_regel_patch(copy.deepcopy(Z), {"firma": "FundedNext", "feld": "striking.consistency_pct", "wert": 35})[0] is None, "Striking setzen nur bei FundingPips")
ok(all(app.fcp_regel_patch(copy.deepcopy(Z), {"firma": "FundingPips", "feld": "striking." + k, "wert": w})[0] is None
       for k, w in (("consistency_pct", 100), ("gewinntage_anzahl", 0), ("gewinntage_anzahl", 2.5), ("verlust_max_pct", 0), ("sl_je_100k", [0, 0]), ("quatsch", 1))),
   "ungültige Werte / unbekanntes Teilfeld → abgelehnt")
e = app.fcp_firma_einstellung(FP)
ok(e["striking"] is None and e["striking_eff"]["gewinntage_anzahl"] == 7, "Einstellung zeigt DB-Wert + was gilt")

print("— 7) Verdrahtung (Planer, Konto-Ziele, Radar-Ziel-Wache) —")
SRC = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
fp = SRC[SRC.index("def fcp_planen("):SRC.index("def fcp_sicht(")]
ok(",on_demand,fcp_ziel,striking" in fp and "st_spalte = False" in fp and 'a.get("striking") is True' in fp, "Planer liest accounts.striking, ohne Spalte wie bisher")
ok("fcp_striking_anwenden(regel, jg, g)" in fp and "regel_k, jg, st_deckel = _sta" in fp
   and 'max_sl=fcp_max_sl(a.get("max_risiko_trade"), st_deckel) if st_deckel else a.get("max_risiko_trade")' in fp, "Striking-Regel + SL-Deckel gehen in fcp_konto_rechnen")
ok("if st_an and not od_an:" in fp and 'zeile["striking_ohne_regel"] = True' in fp, "On Demand hat Vorrang; Firma ohne Regel → normal + Hinweis")
ok('**({"striking": True, "striking_sl_deckel": r.get("striking_sl_deckel"), "cons_laufend": r.get("cons_laufend")}' in fp and "if r.get(\"striking\") else {}))" in fp, "funded_plan bekommt striking nur bei Striking-Konten")
kz = SRC[SRC.index("def kz_rechnen("):SRC.index("def kz_rechnen(") + 40000]
ok("_sta = fcp_striking_anwenden(freg, jg, groesse) if (not _oda and a.get(\"striking\") is True" in kz and '"Add-on Striking"' in kz,
   "Konto-Ziele: Gewinntage n/7 + Consistency 35 % wie der Planer")
ok(",on_demand,fcp_ziel,striking\", \"id\": f\"eq.{kid}\"" in SRC, "/konto-ziele liest striking (Rückfall ohne Spalte)")
zw = SRC[SRC.index("def zw_funded_cfd("):SRC.index("def _zw_cons_tage_laden(")]
ok("st_ids" in zw and "fcp_striking_anwenden(_r, _j, _g)" in zw and "gti = fcp_gewinntage_ist(_gt_jg(a).get(\"gewinntage\")" in zw,
   "Radar-Ziel-Wache: kein „Waiting“-Vorschlag, solange Striking-Gewinntage fehlen")
ok(os.path.exists(os.path.join(WURZEL, "sql", "2026-11-15_addon_striking.sql"))
   and "add column if not exists striking boolean not null default false" in open(os.path.join(WURZEL, "sql", "2026-11-15_addon_striking.sql"), encoding="utf-8").read(),
   "SQL-Datei idempotent (Spalte accounts.striking)")

print("— 8) Frontend (prophos.html, JavaScriptCore) —")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()


def fn(name):
    i = html.index(f"  function {name}(")
    return html[i:html.index("\n  }\n", i) + 4]


i0 = html.index("  const ADDON_EINS_RE")
js = html[i0:html.index("\n", i0)] + "\n" + fn("kontoZusatzMitAddons") + fn("kontoNameMitAddons") + """
const r = {};
r.an = kontoNameMitAddons('100k 12345 → Funded', { st: true });
r.mit1 = kontoNameMitAddons('100k 12345 → Funded · 1% Rule', { st: true });
r.reihe = kontoNameMitAddons('100k 12345 → Funded · Striking · #2 · On Demand · 1% RULE', {});
r.aus = kontoNameMitAddons('100k 12345 → Funded · 1% Rule · Striking', { st: false });
r.doppelt = kontoNameMitAddons('100k 12345 → Funded · Striking', { st: true });
JSON.stringify(r);
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
    fh.write(js)
try:
    aus = subprocess.run(["osascript", "-l", "JavaScript", fh.name], capture_output=True, text=True, timeout=30)
    jr = json.loads(aus.stdout.strip() or "{}")
    if not jr:
        print(aus.stderr[:600])
finally:
    os.unlink(fh.name)
ok(jr.get("an") == "100k 12345 → Funded · Striking" and jr.get("mit1") == "100k 12345 → Funded · 1% Rule · Striking",
   f"Name: „ · Striking“ hinter 1% Rule ({jr.get('mit1')})")
ok(jr.get("reihe") == "100k 12345 → Funded · 1% RULE · On Demand · Striking · #2", f"Reihenfolge 1% Rule, On Demand, Striking, Rest ({jr.get('reihe')})")
ok(jr.get("aus") == "100k 12345 → Funded · 1% Rule" and jr.get("doppelt") == "100k 12345 → Funded · Striking", "ausschalten nimmt nur Striking raus; kein Doppel")
ah = fn("accAddonsHtml")
ok("data-acc-addon=\"st\"" in ah and "accIstFundingPipsCfd(a) || a.striking === true" in ah and "a.striking !== undefined" in ah,
   "Chip „Striking“ nur FundingPips Funded CFD (an bei anderer Firma sichtbar zum Ausschalten), ohne Spalte kein Chip")
au = html[html.index("  async function accAddonUmstellen("):html.index("  async function accAddonUmstellen(") + 4000]
ok("else if(art === 'st')" in au and "striking: !a.striking, name: kontoNameMitAddons(a.name, { st: !a.striking })" in au and "a.striking = data.striking === true" in au,
   "Klick schaltet accounts.striking + Name zusammen; 1 % Rule / On Demand unberührt")
ok("striking: row.striking === undefined ? undefined : row.striking === true," in html, "Konto-Mapping: undefined = Spalte fehlt")
ok("feld: 'striking.gewinntage_anzahl'" in html and "feld: 'striking.verlust_max_pct'" in html and "b.feld.startsWith('striking.')" in html
   and "striking: f.striking, striking_eff: f.striking_eff" in html, "Planer-Einstellung: Striking-Felder bei FundingPips")

print()
print("alle Tests bestanden" if not FEHLER else f"{len(FEHLER)} ROT")
sys.exit(1 if FEHLER else 0)
