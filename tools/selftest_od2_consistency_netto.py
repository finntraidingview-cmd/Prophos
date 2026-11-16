#!/usr/bin/env python3
"""Selbsttest OD2 (17.11.2026, Finn ~03:10 Dubai): FundedNext On Demand — Waiting for Payout erst, wenn AUCH die Consistency gegen den Netto-Profit
erfüllt ist (app.py fcp_tw_netto, fcp_od_ziel, fcp_on_demand_anwenden consistency_basis, fcp_konto_rechnen cons_netto, /konto-ziele On-Demand-Kachel).
Fall aus Finns Screenshot (FundedNext-Dashboard, 100k On Demand, Zyklus 1): Profit 2.226,83 $, Highest profit 1.960,56 $, 88,04 %, Required profit
4.901,40 $ → NICHT bereit. Trades des Zyklus (Werte wie in der DB, Konto ohne Kennung): −2.444,99 · +1.960,56 · +1.780,15 · −1.814,76 · +991,01 ·
+746,78 · +1.008,08. Ohne Netz, Regel in der Form wie live.
Aufruf: python3 tools/selftest_od2_consistency_netto.py"""
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
      "je_groesse": {"100000": {"dd": 10000, "sl": [2000, 2300], "sl_1pct": [700, 780], "lots": [1.0, 1.75], "ziel": [5000, 5500], "hedge_eur": 1500}}}
G100 = 100000.0
JG = app.fcp_je_groesse(FN, G100)
RK, JGO = app.fcp_on_demand_anwenden(FN, JG, G100)
ZF = {"zyklus": 1, "usd": 2161}            # festes Ziel des Zyklus wie am Konto (fcp_ziel.usd 2161)
R = app.fcp_konto_rechnen

# Trades des Zyklus (Ende UTC wie in trade_plans.ended_at) — Berlin-Tage alle verschieden
TRADES = [("2026-11-05T15:20:05+00:00", -2444.99), ("2026-11-06T08:42:05+00:00", 1960.56), ("2026-11-09T07:44:21+00:00", 1780.15),
          ("2026-11-11T14:45:25+00:00", -1814.76), ("2026-11-12T05:12:25+00:00", 991.01), ("2026-11-13T13:12:56+00:00", 746.78),
          ("2026-11-16T13:25:24+00:00", 1008.08)]
PLAENE = [{"status": "completed", "ended_at": t, "master_pl": pl} for t, pl in TRADES]
GEWINN = round(sum(pl for _t, pl in TRADES), 2)
BAL = G100 + GEWINN

print("— Fall Marc …7821 (Screenshot 17.11.2026) —")
tw = app.fcp_tage_zyklus_w(PLAENE, "2026-11-02")
ok(GEWINN == 2226.83 and tw["b"] == 1960.56 and tw["w"] == 6486.58,
   f"Zyklus aus den Trades: Profit {GEWINN} · größter Tag {tw['b']} · Summe Gewinn-Tage {tw['w']}")
ok(round(tw["b"] / GEWINN * 100, 2) == 88.04, f"größter Tag ÷ Profit = {round(tw['b'] / GEWINN * 100, 2)} % (Dashboard 88,04 %)")
oz = app.fcp_od_ziel(40, 2161, GEWINN, app.fcp_tw_netto(tw, GEWINN))
print("  fcp_od_ziel:", oz)
ok(oz["usd"] == 4901.4 and oz["grund"] == "consistency" and oz["bereit"] is False and oz["fehlt"] == 2674.57,
   "nicht bereit — On-Demand-Ziel 4.901,40 $ (Consistency), fehlen 2.674,57 $")

alt = R(JGO, BAL, G100, 1, False, 1.0, 0.85, random.Random(3), regel=dict(RK, consistency_basis=None), tage=tw, ziel_fest=ZF)
ok(alt["aktion"] == "ziel", f"Basis Summe der Gewinn-Tage (bis OD2) → „{alt.get('grund')}“ — so kam der Fehler zustande")
neu = R(JGO, BAL, G100, 1, False, 1.0, 0.85, random.Random(3), regel=RK, tage=tw, ziel_fest=ZF)
print("  neu:", {k: neu.get(k) for k in ("aktion", "grund", "tp", "tp_art", "ziel", "od_ziel")})
ok(neu["aktion"] == "planen" and neu["tp_art"] == "consistency", "On Demand (Basis Netto-Profit) → kein Waiting, der Planer plant weiter")
ok(neu["od_ziel"]["usd"] == 4901.4 and abs(neu["ziel"] - 104901.4) < 0.01, f"Ziel des Plans = Größe + 4.901,40 ({neu['ziel']})")
ok(neu["tp"] <= tw["b"], f"TP {neu['tp']} ≤ bisheriger größter Tag {tw['b']} — der größte Tag wächst nicht")
echt, _w = app.fcp_ziel_echt(alt)
ok(echt, "(Gegenprobe) das alte Urteil wäre durch fcp_ziel_echt gekommen → Waiting am 16.11.")

print("— Serie bis zum Payout (alle TPs treffen genau) —")
for seed in range(40):
    rnd = random.Random(seed)
    pl = list(PLAENE)
    g_, schritte, fertig = GEWINN, [], None
    for i in range(8):
        t = app.fcp_tage_zyklus_w(pl, "2026-11-02")
        r = R(JGO, G100 + g_, G100, 1, False, 1.0, 0.85, rnd, regel=RK, tage=t, ziel_fest=ZF)
        if r["aktion"] != "planen":
            fertig = (r, t)
            break
        schritte.append(r["tp"])
        g_ = round(g_ + r["tp"], 2)
        pl.append({"status": "completed", "ended_at": f"2026-11-{17 + i:02d}T10:00:00+00:00", "master_pl": r["tp"]})
    r, t = fertig
    gut = (r["aktion"] == "ziel" and t["b"] == 1960.56 and 4901.4 <= g_ <= 4903.5 and max(schritte) < 1960.56 and len(schritte) == 2
           and t["b"] <= 0.4 * g_ + 0.005 and app.fcp_ziel_echt(r)[0])
    if not gut or seed == 0:
        print(f"  seed {seed}: TPs {schritte} → Profit {g_} · größter Tag {t['b']} · {round(t['b'] / g_ * 100, 2)} % · {r['aktion']}")
    if not gut:
        FEHLER.append(f"Serie seed {seed}")
ok(not [f for f in FEHLER if f.startswith("Serie")],
   "Fall A, 40 Serien: 2 Trades, jeder < 1.960,56 $, Ende 4.901,40–4.903,50 $ (kein Überschießen), größter Tag ≤ 40 % → dann sofort Waiting")
r = R(JGO, G100 + 4901.40, G100, 1, False, 1.0, 0.85, random.Random(3), regel=RK, tage=app.fcp_tage_zyklus_w(PLAENE, "2026-11-02"), ziel_fest=ZF)
ok(r["aktion"] == "ziel" and app.fcp_ziel_echt(r)[0], "Fall A: Profit 4.901,40 (über der Spanne 2.000–2.250) → Waiting for Payout")
r = R(JGO, G100 + 4900.00, G100, 1, False, 1.0, 0.85, random.Random(3), regel=RK, tage=app.fcp_tage_zyklus_w(PLAENE, "2026-11-02"), ziel_fest=ZF)
ok(r["aktion"] == "planen" and r["tp"] >= 50, f"Fall A: 4.900,00 (1,40 $ zu wenig) → noch nicht, TP {r.get('tp')}")
r = R(JGO, G100 + 4901.39, G100, 1, False, 1.0, 0.85, random.Random(3), regel=RK, tage=app.fcp_tage_zyklus_w(PLAENE, "2026-11-02"), ziel_fest=ZF)
ok(r["aktion"] == "planen" and r["od_ziel"]["bereit"] is False, "Fall A: 4.901,39 (1 Cent zu wenig) → noch nicht (Toleranz × p, wie FundedNext)")
r = R(JGO, G100 + 1500, G100, 1, False, 1.0, 0.85, random.Random(4), regel=RK, tage={"b": 400.0, "w": 1500.0, "n": 3, "serie": 1500.0, "serie_n": 3}, ziel_fest={})
ok(r["aktion"] == "planen" and abs(r["od_ziel"]["wachstum"] - (r["ziel"] - G100)) < 0.01 and r["od_ziel"]["wachstum"] == r["ziel_fest"]["usd"],
   f"ohne gespeichertes Ziel: od_ziel nimmt das gewürfelte Ziel des Plans ({r['od_ziel']['wachstum']} = {r['ziel_fest']['usd']})")

print("— Fall B: 100k, Ziel 2.200, Start mit −2.445 — kein Tag über 880 $, Ende genau im Ziel —")
ZF2 = {"zyklus": 1, "usd": 2200}
fehl_b, bsp = [], None
for seed in range(40):
    rnd = random.Random(1000 + seed)
    pl = [{"status": "completed", "ended_at": "2026-11-05T15:20:05+00:00", "master_pl": -2445.0}]
    g_, tps = -2445.0, []
    for i in range(15):
        t = app.fcp_tage_zyklus_w(pl, "2026-11-02")
        r = R(JGO, G100 + g_, G100, 1, False, 1.0, 0.85, rnd, regel=RK, tage=t, ziel_fest=ZF2)
        if r["aktion"] != "planen":
            break
        tps.append(r["tp"])
        g_ = round(g_ + r["tp"], 2)
        pl.append({"status": "completed", "ended_at": f"2026-11-{6 + i:02d}T10:00:00+00:00", "master_pl": r["tp"]})
    t = app.fcp_tage_zyklus_w(pl, "2026-11-02")
    if not (r["aktion"] == "ziel" and 2200 <= g_ <= 2200.5 and max(tps) <= 880 and t["b"] <= 0.4 * g_ and r["od_ziel"]["grund"] == "wachstum"):
        fehl_b.append((seed, tps, g_, r["aktion"]))
    bsp = bsp or (tps, g_)
print(f"  Beispiel: TPs {bsp[0]} → Profit {bsp[1]}")
ok(not fehl_b, f"Fall B, 40 Serien: jeder Tag ≤ 880 $ (auch die Erholungstage), Ende 2.200–2.200,50, Consistency erfüllt → Waiting ({fehl_b[:2]})")
# zwei Trades am selben Tag: Deckel gilt für die Tagessumme
pl = [{"status": "completed", "ended_at": "2026-11-05T15:20:05+00:00", "master_pl": -500.0},
      {"status": "completed", "ended_at": "2026-11-06T08:00:00+00:00", "master_pl": 600.0}]
t = app.fcp_tage_zyklus_w(pl, "2026-11-02", "2026-11-06")
r = R(JGO, G100 + 100, G100, 1, False, 1.0, 0.85, random.Random(2), regel=RK, tage=t, ziel_fest=ZF2)
ok(r["aktion"] == "planen" and r["tp"] <= 836 - 600 + 0.5, f"heute schon +600: TP {r.get('tp')} ≤ 836 − 600 (Tagessumme ≤ 0,95 × 880)")
pl.append({"status": "completed", "ended_at": "2026-11-06T09:00:00+00:00", "master_pl": 230.0})
t = app.fcp_tage_zyklus_w(pl, "2026-11-02", "2026-11-06")
r = R(JGO, G100 + 330, G100, 1, False, 1.0, 0.85, random.Random(2), regel=RK, tage=t, ziel_fest=ZF2)
ok(r["aktion"] == "aus" and "Tages-Deckel" in r["grund"], f"heute schon +830: „{r.get('grund')}“")
ok(app.fcp_od_ende_min(40, 2200, {"b": 880.0}) == 0.0 and app.fcp_od_ende_min(40, 2200, {"b": 880.5}) == 2202.0
   and app.fcp_od_ende_min(40, 2161, {"b": 1960.56}) == 4902.0, "Grenze Fall A/B: größter Tag 880 → B (Ziel bindet), 880,50 → A (Ende 2.202)")

print("— Verlust in der Serie: Ziel bleibt größter Tag ÷ p —")
pl = PLAENE + [{"status": "completed", "ended_at": "2026-11-17T10:00:00+00:00", "master_pl": -800.0}]
t = app.fcp_tage_zyklus_w(pl, "2026-11-02")
r = R(JGO, G100 + GEWINN - 800, G100, 1, False, 1.0, 0.85, random.Random(5), regel=RK, tage=t, ziel_fest=ZF)
ok(r["aktion"] == "planen" and r["od_ziel"]["usd"] == 4901.4 and r["od_ziel"]["fehlt"] == 3474.57 and r["tp"] < 1960.56,
   f"nach −800: fehlen 3.474,57, TP {r['tp']} < größter Tag")

print("— Wachstumsziel bindet (kleiner größter Tag) —")
t2 = {"b": 800.0, "w": 2200.0, "n": 3, "serie": 2200.0, "serie_n": 3}
r = R(JGO, 102200, G100, 1, False, 1.0, 0.85, random.Random(1), regel=RK, tage=t2, ziel_fest=ZF)
ok(r["aktion"] == "ziel" and r["od_ziel"]["grund"] == "wachstum" and r["od_ziel"]["usd"] == 2161.0, "2.200 Profit, größter Tag 800 (36 %) → bereit (Wachstum)")
t3 = {"b": 900.0, "w": 2200.0, "n": 3, "serie": 2200.0, "serie_n": 3}
r = R(JGO, 102200, G100, 1, False, 1.0, 0.85, random.Random(1), regel=RK, tage=t3, ziel_fest=ZF)
ok(r["aktion"] == "planen" and r["od_ziel"]["usd"] == 2250.0, f"größter Tag 900 > 40 % × 2.200 → weiter, Ziel 2.250 (TP {r.get('tp')})")

print("— Zyklus nicht lesbar / nur On Demand —")
ok(app.fcp_tw_netto(None, 100) is None and app.fcp_od_ziel(40, 2000, 100, None) is None, "nicht lesbar → None (fail-closed wie bisher)")
r = R(JGO, BAL, G100, 1, False, 1.0, 0.85, random.Random(3), regel=RK, tage=None, ziel_fest=ZF)
ok(r["aktion"] == "ziel" and app.fcp_ziel_echt(r)[0] is False, "nicht lesbar: Ziel-Urteil, aber nicht umgestellt (fcp_ziel_echt wie bisher)")
ok(RK.get("consistency_basis") == "netto" and "consistency_basis" not in FN, "nur die On-Demand-Regel trägt consistency_basis, die Firmen-Regel bleibt")
for regel in (FN, dict(FN, namen=["the5ers"], tp_modus="consistency50")):
    r = R(app.fcp_je_groesse(regel, G100), BAL, G100, 2, False, 1.0, 0.85, random.Random(3), regel=regel, tage=tw)
    ok("od_ziel" not in r, f"{regel['namen'][0]}: ohne On Demand kein od_ziel (Ergebnis wie bisher)")

print("— Verdrahtung —")
SRC = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
fp = SRC[SRC.index("def fcp_planen("):SRC.index("def fcp_sicht(")]
ok("On-Demand-Ziel {_liq_de(o['usd'])} $" in fp and "{\"od_ziel\": r.get(\"od_ziel\")} if r.get(\"on_demand\")" in fp, "Notiz + funded_plan.od_ziel nur bei On Demand")
kz = SRC[SRC.index("OD2 (Finn 17.11.2026, Marc …7821)"):][:2000]
ok("fcp_tw_netto(tzw, gewinn)" in kz and "Netto-Profit des Zyklus (wie FundedNext)" in kz, "/konto-ziele: On-Demand-Kachel rechnet gegen den Netto-Profit")

print()
print("FEHLER:" if FEHLER else "ALLES OK", FEHLER if FEHLER else "")
sys.exit(1 if FEHLER else 0)
