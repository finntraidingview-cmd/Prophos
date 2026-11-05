#!/usr/bin/env python3
"""Selbsttest O1 (05.11.2026, Finn ~07:20 Dubai): FundedNext On-Demand-Konten + festes Ziel je Funded-CFD-Konto (app.py fcp_on_demand_regel,
fcp_on_demand_anwenden, fcp_ziel_fest, fcp_konto_rechnen(ziel_fest=…), Verdrahtung in fcp_planen). Ohne Netz, Regeln erfundenen Form wie live.
Kern: (1) ohne On Demand und ohne festes Ziel = genau wie heute; (2) mit festem Ziel = gleiche Pläne bis auf das Ziel selbst (Diff-Test, gleicher
Zufalls-Verbrauch); (3) On Demand: Ziel 2.000–2.250 $ je 100k skaliert, Consistency 40 %, kein Refund — Z 2.180 → 3 Trades; (4) Consistency nach Finn
(Summe der Gewinn-Tage, TP 35–40 % der Distanz, letzter Trade = Rest; Pflicht-Beispiele −2.000 → +3.000 und frisch 2.150).
Aufruf: python3 tools/selftest_fcp_on_demand.py"""
import copy
import os
import random
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
import app  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


FN = {"an": True, "name": "FundedNext", "namen": ["fundednext"], "tp_deckel_plus": 1000,
      "erster_payout": {"ziel": [50, 150], "hedge_eur_je_dd": 0.5, "lots_faktor": 0.1},
      "je_groesse": {"100000": {"dd": 10000, "sl": [2000, 2300], "sl_1pct": [700, 780], "lots": [1.0, 1.75], "ziel": [5000, 5500], "hedge_eur": 1500},
                     "50000": {"dd": 5000, "sl": [1000, 1150], "lots": [0.5, 0.85], "ziel": [2500, 2750], "hedge_eur": 750},
                     "200000": {"dd": 20000, "sl": [4000, 4600], "lots": [2.0, 3.5], "ziel": [10000, 11000], "hedge_eur": 3000}}}
T5 = {"an": True, "name": "The5%ers", "namen": ["the5ers"], "tp_modus": "consistency50", "tp_zyklen": [750, 1500, 3000, 6000],
      "je_groesse": {"100000": {"dd": 10000, "sl": [1000, 1200], "lots": [1.0, 1.4], "ziel": [1300, 1500], "hedge_eur": 1000, "tp_erster": 750}}}
BG = {"an": True, "name": "Blue Guardian", "namen": ["blueguardian"], "erster_payout": {"ziel": [50, 100], "hedge_eur_je_dd": 0.5},
      "je_groesse": {"100000": {"dd": 8000, "sl": [1500, 1800], "lots": [1.0, 1.2], "ziel": [1000, 1200], "hedge_eur": 1000,
                                "gewinntage": {"anzahl": 3, "min": 500, "tp": [550, 650]}}}}
FT = {"an": True, "name": "FTMO", "namen": ["ftmo"], "je_groesse": {"100000": {"dd": 10000, "sl": [1500, 2000], "lots": [1.0, 1.5], "ziel": [1500, 2500], "hedge_eur": 1200}}}
JG = app.fcp_je_groesse
R = app.fcp_konto_rechnen

print("— On-Demand-Regel —")
od = app.fcp_on_demand_regel(FN)
ok(od == {"ziel_je_100k": [2000.0, 2250.0], "consistency_pct": 40.0}, f"FundedNext Code-Standard {od}")
ok(app.fcp_on_demand_regel(dict(FN, on_demand={"ziel_je_100k": [1800, 2000], "consistency_pct": 35})) == {"ziel_je_100k": [1800.0, 2000.0], "consistency_pct": 35.0},
   "Regel je Firma überschreibt den Standard")
ok(app.fcp_on_demand_regel(dict(FN, on_demand=False)) is None, "on_demand: false in der Regel = keine On-Demand-Regel")
ok(app.fcp_on_demand_regel(dict(FN, on_demand={"ziel_je_100k": [1800, 2000]}))["consistency_pct"] == 40.0, "Regel ohne p → Standard 40 % (nicht still aus)")
ok(app.fcp_on_demand_regel(dict(FN, on_demand={"ziel_je_100k": [1800, 2000], "consistency_pct": 0}))["consistency_pct"] is None, "ausdrücklich 0 = keine Consistency")
ok(app.fcp_on_demand_regel(T5) is None and app.fcp_on_demand_regel(FT) is None, "andere Firmen ohne On-Demand-Regel")
for g, ziel in ((100000, [2000.0, 2250.0]), (50000, [1000.0, 1125.0]), (200000, [4000.0, 4500.0])):
    r2, jg2 = app.fcp_on_demand_anwenden(FN, JG(FN, g), g)
    ok(jg2["ziel"] == ziel and jg2["sl"] == JG(FN, g)["sl"] and jg2["lots"] == JG(FN, g)["lots"] and jg2["hedge_eur"] == JG(FN, g)["hedge_eur"]
       and jg2["dd"] == JG(FN, g)["dd"], f"{g // 1000}k: Ziel {ziel} skaliert, SL/Lots/Hedge/DD wie normal")
r2, jg2 = app.fcp_on_demand_anwenden(FN, JG(FN, 100000), 100000)
ok(app.fcp_erster_payout(r2) is None and app.fcp_consistency_pct(r2) == 40.0, "kein Refund-Trade, Consistency 40 %")
ok("gewinntage" not in (app.fcp_on_demand_anwenden(dict(BG, on_demand={"ziel_je_100k": [2000, 2250], "consistency_pct": 40}), JG(BG, 100000), 100000) or ({}, {}))[1],
   "keine Gewinntage bei On Demand")
ok(app.fcp_on_demand_anwenden(T5, JG(T5, 100000), 100000) is None, "Firma ohne Regel → None (Planer lässt das Konto aus)")
ok(FN["je_groesse"]["100000"]["ziel"] == [5000, 5500] and "on_demand" not in FN, "Regel selbst unverändert (Kopie)")

print("— festes Ziel: gespeichert / neu —")
F = app.fcp_ziel_fest
ok(F({"zyklus": 2, "usd": 1400}, 2, [1300, 1500], 1350) == (1400.0, False), "gleicher Zyklus, im Bereich → bleibt")
ok(F({"zyklus": 1, "usd": 1400}, 2, [1300, 1500], 1350) == (1350.0, True), "neuer Zyklus (nach Payout) → neu gewürfelt")
ok(F({"zyklus": 2, "usd": 120}, 2, [1300, 1500], 1350) == (1350.0, True), "außerhalb des Bereichs (Refund → normal, Bereich geändert) → neu")
ok(F({}, 2, [1300, 1500], 1350) == (1350.0, True) and F(None, 2, [1300, 1500], 1350) == (1350.0, True) and F({"usd": "x"}, 2, [1300, 1500], 1350)[1],
   "nichts/kaputt gespeichert → neu")

print("— Diff-Test: ohne festes Ziel = heute; mit festem Ziel = gleich bis aufs Ziel —")
faelle = diff_none = diff_fest = rnd_gleich = 0
for regel in (FN, T5, BG, FT):
    for g in (100000,):
        jg = JG(regel, g)
        for bal in (g - 3000, g - 200, g, g + 300, g + 700, g + 1250, g + 4000):
            for zyk in (1, 2, 3):
                for tage in (None, (0.0, 0), (500.0, 1), (800.0, 2)):
                    for gti in ((None, (0, 3), (3, 3)) if regel is BG else (None,)):
                        for seed in (1, 7, 42):
                            kw = dict(regel=regel, gewinne=None, gewinntage=gti, tage=tage)
                            a = R(jg, bal, g, zyk, False, 1.0, 0.85, random.Random(seed), **kw)
                            rb = random.Random(seed); b = R(jg, bal, g, zyk, False, 1.0, 0.85, rb, ziel_fest={}, **kw)
                            faelle += 1
                            bz = {k: v for k, v in b.items() if k != "ziel_fest"}
                            if a != bz:
                                diff_none += 1
                            if "ziel_fest" in b:
                                st = {"zyklus": b["ziel_fest"]["zyklus"], "usd": b["ziel_fest"]["usd"]}
                                rc = random.Random(seed); c = R(jg, bal, g, zyk, False, 1.0, 0.85, rc, ziel_fest=st, **kw)
                                if not (c.get("ziel_fest", {}).get("neu") is False and {k: v for k, v in c.items() if k != "ziel_fest"} == bz):
                                    diff_fest += 1
                                if rc.random() != rb.random():
                                    rnd_gleich += 1
ok(faelle > 500 and diff_none == 0, f"{faelle} Fälle: leeres festes Ziel ({{}}) = Ergebnis von heute ({diff_none} Abweichungen)")
ok(diff_fest == 0, f"gespeichertes Ziel = gewürfeltes → identischer Plan, nur „neu“ false ({diff_fest} Abweichungen)")
ok(rnd_gleich == 0, f"gleicher Zufalls-Verbrauch mit festem Ziel — weitere Würfe im Lauf bleiben gleich ({rnd_gleich} Abweichungen)")
jg = JG(FT, 100000)
a = R(jg, 100000, 100000, 2, False, 1.0, 0.85, random.Random(3), regel=FT, ziel_fest={"zyklus": 2, "usd": 2400})
b = R(jg, 100000, 100000, 2, False, 1.0, 0.85, random.Random(3), regel=FT, ziel_fest={"zyklus": 2, "usd": 1600})
ok(a["ziel"] == 100000 + 2400 or a.get("ziel_fest", {}).get("usd") == 2400, f"festes Ziel wird genommen (2.400) → TP {a.get('tp')}")
ok(a.get("tp") != b.get("tp") and a["lots"] == b["lots"] and a["sl"] == b["sl"], "anderes festes Ziel ändert nur den TP, Lots/SL gleich")
a1 = R(jg, 100000, 100000, 2, False, 1.0, 0.85, random.Random(5), regel=FT, ziel_fest={"zyklus": 2, "usd": 2000})
a2 = R(jg, 100800, 100000, 2, False, 1.0, 0.85, random.Random(99), regel=FT, ziel_fest={"zyklus": 2, "usd": 2000})
ok(a1.get("ziel_fest", {}).get("usd") == 2000 and a2.get("ziel_fest", {}).get("usd") == 2000 and a2["tp"] == 1200,
   f"zweiter Lauf, anderer Zufall: Ziel bleibt 2.000 → TP Rest 1.200 ({a2.get('tp')})")

print("— Consistency nach Finn (fcp_cons_finn): Basis Summe der Gewinn-Tage, TP (p − 5 %) … p der Distanz —")
CF = app.fcp_cons_finn


def serie(pct, Z, G0, seed, W0=0.0, B0=0.0, max_n=8):
    """Trades nacheinander, alle gewinnen (je Tag einer) → (TPs, Endgewinn, B, W, Deckel je Trade)."""
    rnd, G, W, B, S, k, tps, deckel = random.Random(seed), float(G0), float(W0), float(B0), 0.0, 0, [], []
    for _ in range(max_n):
        c = CF(pct, Z, G, {"b": B, "w": W, "n": k, "serie": S, "serie_n": k}, rnd)
        if c["fertig"]:
            break
        tps.append(c["tp"]); deckel.append(c["deckel"]); G += c["tp"]; W += c["tp"]; B = max(B, c["tp"]); S += c["tp"]; k += 1
    return tps, G, B, W, deckel


c0 = CF(40, 3000, -2000, {"b": 0, "w": 0, "n": 0, "serie": 0, "serie_n": 0}, random.Random(1))
ok(c0["rest"] == 5000 and c0["deckel"] == 1900 and c0["n"] == 3 and 1750 <= c0["tp"] <= 1900,
   f"Finn Pflicht: G −2.000, Z +3.000, p 40 → noch 5.000, Deckel 1.900, 3 Trades, TP 1 = {c0['tp']:g} (35–40 % von 5.000)")
fehl = []
for seed in range(60):
    tps, G, B, W, dk = serie(40, 3000, -2000, seed)
    if not (len(tps) == 3 and abs(G - 3000) < 0.5 and all(t <= d + 0.5 for t, d in zip(tps, dk)) and B <= 0.4 * W + 0.5):
        fehl.append((seed, tps))
ok(not fehl, f"60 Serien G −2.000 → Z 3.000: immer 3 Trades, Summe trifft das Ziel, kein Trade > Deckel, größter Tag ≤ 40 % ({fehl[:2]})")
tps, G, B, W, dk = serie(40, 3000, -2000, 7)
print("   Beispiel:", " / ".join(f"{t:g}" for t in tps), f"→ Ende {G:g}, größter Tag {B / W:.0%}")
fehl, ersten = [], set()
for seed in range(60):
    tps, G, B, W, dk = serie(40, 2150, 0, seed)
    ersten.add(tps[0] if tps else None)
    if not (len(tps) == 3 and abs(G - 2150) < 0.5 and all(t <= d + 0.5 for t, d in zip(tps, dk)) and B <= 0.4 * W + 0.5):
        fehl.append((seed, tps))
ok(not fehl, f"frisch Z 2.150, p 40: immer 3 Trades (~800 / ~780 / Rest), Summe = Ziel, unter der Consistency ({fehl[:2]})")
ok(len(ersten) > 10, f"TP streut je Trade (Zufall 35–40 %): {len(ersten)} verschiedene erste TPs in 60 Serien")
tps, G, B, W, dk = serie(40, 2150, 0, 3)
print("   Beispiel:", " / ".join(f"{t:g}" for t in tps))
fehl = []
for seed in range(40):
    tps, G, B, W, dk = serie(50, 1400, 0, seed)
    if not (abs(G - 1400) < 0.5 and B <= 0.5 * W + 0.5 and 0.45 * 1400 - 1 <= tps[0] <= 0.5 * 1400 * 0.95 + 1):
        fehl.append((seed, tps))
ok(not fehl, f"The5ers p 50: TP 45–50 % der Distanz (≤ Deckel), Ziel genau, Consistency gehalten ({fehl[:2]})")
c1 = CF(40, 2150, 1600, {"b": 1600, "w": 1600, "n": 1, "serie": 1600, "serie_n": 1}, random.Random(2))
ok(c1["rest"] >= 1600 / 0.4 * 1.02 - 1600 - 0.5 and c1["ende"] >= 4000, f"zu großer Tag (1.600): Rest erhöht bis B ≤ 40 % × W (Ende {c1['ende']:g})")
ok(CF(40, 2150, 2150, {"b": 800, "w": 2150, "n": 3, "serie": 2150, "serie_n": 3}, None)["fertig"] is True, "G ≥ Z und B ≤ 40 % × W → fertig")
ok(CF(40, 2150, 2150, {"b": 1000, "w": 2150, "n": 3, "serie": 2150, "serie_n": 3}, None)["fertig"] is False, "G ≥ Z, aber B 1.000 > 40 % × 2.150 → weiter")
cv = CF(40, 2150, 1200, {"b": 800, "w": 1500, "n": 3, "serie": 0, "serie_n": 0}, None)
ok(cv["distanz"] == cv["rest"] and cv["k"] == 0, "nach einem Verlust-Trade: neue Serie, Distanz = Rest bis zum Ziel")
ok(CF(40, 2150, 300, None, None)["lesbar"] is False and CF(40, 2150, 300, None, None)["tp"] == 817.0, "Zyklus nicht lesbar → kleinster sicherer Trade (p × Z × 0,95)")
tw = app.fcp_tage_zyklus_w([{"status": "completed", "master_pl": 400, "ended_at": "2026-11-03T10:00:00+00:00"},
                            {"status": "completed", "master_pl": -300, "ended_at": "2026-11-04T10:00:00+00:00"},
                            {"status": "completed", "master_pl": 500, "ended_at": "2026-11-05T10:00:00+00:00"},
                            {"status": "completed", "master_pl": 250, "ended_at": "2026-11-06T10:00:00+00:00"},
                            {"status": "completed", "master_pl": 900, "ended_at": "2026-10-20T10:00:00+00:00"}], "2026-11-01")
ok(tw == {"b": 500.0, "w": 1150.0, "n": 4, "serie": 750.0, "serie_n": 2}, f"Zyklus-Werte: größter Tag 500, Summe Gewinn-Tage 1.150, Serie seit Verlust 750 / 2 ({tw})")
ok(app.fcp_tage_zyklus_w([{"status": "completed", "master_pl": None, "ended_at": "2026-11-03T10:00:00+00:00"}]) is None, "P&L fehlt → nicht lesbar")

print("— On Demand: Z 2.180, p 40 → 3 Trades —")
rk, jgo = app.fcp_on_demand_anwenden(FN, JG(FN, 100000), 100000)
st = {"zyklus": 1, "usd": 2180}
schritte, G, W, B, S, k = [], 0.0, 0.0, 0.0, 0.0, 0
rnd = random.Random(11)
for _ in range(6):
    r = R(jgo, 100000 + G, 100000, 1, False, 1.0, 0.85, rnd, regel=rk, tage={"b": B, "w": W, "n": k, "serie": S, "serie_n": k}, ziel_fest=st)
    if r["aktion"] != "planen":
        schritte.append(r["aktion"]); break
    schritte.append(r["tp"]); G += r["tp"]; W += r["tp"]; B = max(B, r["tp"]); S += r["tp"]; k += 1
ok(len(schritte) == 4 and schritte[3] == "ziel" and abs(sum(schritte[:3]) - 2180) < 0.5 and max(schritte[:3]) <= 0.4 * 2180,
   f"Zyklus 1 (FundedNext sonst Refund): 3 Trades, Summe 2.180, größter ≤ 40 % → {schritte}")
ok(R(jgo, 100000, 100000, 1, False, 1.0, 0.85, random.Random(11), regel=rk, tage=(0.0, 0), ziel_fest=st)["tp_art"] == "consistency",
   "On Demand im 1. Zyklus: Consistency-Weg, kein Refund-Trade")
rn = R(JG(FN, 100000), 100000, 100000, 1, False, 1.0, 0.85, random.Random(11), regel=FN, tage=(0.0, 0))
ok(rn["tp_art"] == "erster_payout_refund", "dasselbe Konto ohne On Demand: Refund-Trade wie heute")
r = R(jgo, 102180, 100000, 1, False, 1.0, 0.85, random.Random(11), regel=rk, tage={"b": 1200, "w": 2180, "n": 2, "serie": 2180, "serie_n": 2}, ziel_fest=st)
ok(r["aktion"] == "planen" and r["tp"] > 0, f"Ziel 2.180 erreicht, aber größter Tag 1.200 > 40 % der Gewinn-Tage → weiter (TP {r.get('tp')})")
r = R(jgo, 102200, 100000, 1, False, 1.0, 0.85, random.Random(11), regel=rk, tage={"b": 800, "w": 2200, "n": 3, "serie": 2200, "serie_n": 3}, ziel_fest=st)
ok(r["aktion"] == "ziel", "2.200 $ Gewinn, größter Tag 800 (36 %) → Ziel erreicht → Waiting / Payout anfragbar")

print("— Verdrahtung fcp_planen —")
SRC = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
fp = SRC[SRC.index("def fcp_planen("):SRC.index("def fcp_sicht(")]
ok(",on_demand,fcp_ziel" in fp and "od_spalte = False" in fp, "Konten mit on_demand/fcp_ziel, ohne Spalten Rückfall auf den bisherigen Select")
ok("regel_k = regel" in fp and "rnd, regel_k," in fp and "fcp_on_demand_anwenden(regel, jg, g)" in fp, "On-Demand-Regel geht in fcp_konto_rechnen")
ok("ziel_fest=((a.get(\"fcp_ziel\")" in fp and "if od_spalte and payouts_ok else None" in fp, "festes Ziel nur mit Spalte + lesbaren Payouts")
ok("{\"fcp_ziel\": zf}" in fp and fp.index("{\"fcp_ziel\": zf}") > fp.index("if not trocken:") and "w_[\"fcp_ziel\"] = \"is.null\"" in fp, "festes Ziel wird nur im echten Lauf geschrieben")
ok("{\"payout_ready_at\": plan_tag}" in fp and "if not r.get(\"on_demand\") or (r.get(\"consistency\") or {}).get(\"bester_tag\") is None:" in fp,
   "On Demand am Ziel: Payout anfragbar ab heute — nur mit geprüfter Consistency")
ok("w_[\"fcp_ziel\"] = \"is.null\"" in fp and "requests.exceptions.HTTPError" in fp and "raise" in fp[fp.index("od_spalte = True"):fp.index("od_spalte = False")],
   "Erstwurf mit Guard (kein Rennen), Rückfall nur bei fehlender Spalte")
ok("\"ziel_fest\", \"on_demand\")}" in fp, "festes Ziel + On Demand stehen im funded_plan des Trades")

print()
print("alle Tests bestanden" if not FEHLER else f"{len(FEHLER)} ROT")
sys.exit(1 if FEHLER else 0)
