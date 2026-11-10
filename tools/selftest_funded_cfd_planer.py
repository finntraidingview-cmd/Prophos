#!/usr/bin/env python3
"""Selbsttest: FUNDED-CFD-PLANER (fcp_*, 30.10.2026, Finn: „Ja, bauen"). Rechnet je Firma × Größe mit den Regeln aus
sql/2026-10-30_funded_cfd_planer.sql (Ziel, TP aufs Ziel inkl. Verlust-Nachholen, The5ers 750 im 1. Zyklus, SL/Lots im Bereich, 1-%-Regel,
Hedge-€ auf DD), Richtungsschutz, Gruppen-Sicht und einen ganzen Lauf fcp_planen gegen eine nachgebaute DB (nichts geschrieben).
Ohne Netz. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_funded_cfd_planer.py"""
import json
import os
import random
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


def firmen_aus_sql():
    sql = open(os.path.join(WURZEL, "sql", "2026-10-30_funded_cfd_planer.sql"), encoding="utf-8").read()
    m = re.search(r"'(\[\s*\{.*?\]\s*)'::jsonb", sql, re.S)
    return json.loads(m.group(1))


FIRMEN = firmen_aus_sql()
PPL = {"the5ers": 1.0, "fundednext": 10.0, "fundingpips": 20.0, "tradeifycfd": 10.0}      # firm_specs live (30.10.2026)


def jg(firma, g):
    return app.fcp_je_groesse(app.ap_regel_finden(FIRMEN, firma), g)


print("1) Regeln je Firma × Größe")
for firma, g in (("The5%ers", 100000), ("The5%ers", 200000), ("FundedNext", 50000), ("FundedNext", 100000), ("FundedNext", 200000),
                 ("FundingPips", 50000), ("FundingPips", 100000), ("Tradeify CFD", 100000)):
    j = jg(firma, g)
    check(bool(j), f"{firma} {g // 1000}k hat Werte")
    key = app._ap_norm(firma)
    for erster in (True, False):
        for s in range(30):
            r = app.fcp_konto_rechnen(j, g, g, erster, False, PPL[key], 0.85, random.Random(s))
            if r["aktion"] != "planen":
                check(False, f"{firma} {g} frisch plant ({r.get('grund')})")
                break
            lo, hi = j["sl"]
            if not (lo <= r["sl"] <= hi and j["lots"][0] <= r["lots"] <= j["lots"][1]):
                check(False, f"{firma} {g} SL/Lots im Bereich ({r['sl']}, {r['lots']})")
                break
            soll = j.get("tp_erster") if (erster and j.get("tp_erster")) else None
            if soll and r["tp"] != soll:
                check(False, f"{firma} {g} TP 1. Zyklus {soll}")
                break
            if not soll and not (j["ziel"][0] <= r["tp"] <= j["ziel"][1]):
                check(False, f"{firma} {g} TP aufs Ziel ({r['tp']})")
                break
            # Hedge: hedge_eur € auf dd $ — Fusion verliert am Master-SL hedge_eur × SL / DD
            if abs(r["slave_risk"] - j["hedge_eur"]) > 0.01 or abs(r["hedge_sl_eur"] - j["hedge_eur"] * r["sl"] / j["dd"]) > 0.05:
                check(False, f"{firma} {g} Hedge-€ auf DD")
                break
        else:
            check(True, f"{firma} {g // 1000}k {'1. Zyklus' if erster else 'ab 2. Zyklus'}: 30 Würfe im Bereich")

print("2) Beispielrechnungen")
j = jg("FundedNext", 100000)
r = app.fcp_konto_rechnen(j, 98000, 100000, False, False, 10.0, 0.85, random.Random(7), {"namen": ["fundednext"], "tp_deckel_plus": 99999})
check(r["aktion"] == "planen" and 3500 <= r["tp"] <= 3850 and r["tp_art"] == "nachholen", f"FundedNext 100k nach −2k ohne Deckel (alter Aufruf ohne Regel): TP {r.get('tp')} (3.500–3.850)")
print(f"     → Balance 98.000 · Ziel {r['ziel']:.0f} · TP {r['tp']:.0f} $ ({r['tp_pkt']} Pkt) · SL {r['sl']:.0f} $ · {r['lots']} Lot · "
      f"Hedge {r['hedge_lots']} Lot Fusion, {r['hedge_eur']:.0f} € auf {r['dd']:.0f} $ DD → am SL +{r['hedge_sl_eur']:.0f} €, am TP {r['hedge_tp_eur']:.0f} €")
r1 = app.fcp_konto_rechnen(j, 100000, 100000, True, True, 10.0, 0.85, random.Random(3))
check(670 <= r1["sl"] <= 780 and r1["eins_prozent"], f"FundedNext 100k mit 1-%-Regel: SL {r1['sl']} (670–780)")
check(app.fcp_konto_rechnen(j, 101600, 100000, False, False, 10.0, 0.85)["aktion"] == "ziel", "FundedNext +1.600 → Ziel erreicht (ab +1.500)")
j5 = jg("The5%ers", 100000)
check(app.fcp_konto_rechnen(j5, 100750, 100000, True, False, 1.0, 0.85)["tp"] == 750, "The5ers 1. Zyklus nach +750: nächster TP wieder 750")
check(app.fcp_konto_rechnen(j5, 101500, 100000, True, False, 1.0, 0.85)["aktion"] == "ziel", "The5ers +1.500 → Ziel erreicht")
r2 = app.fcp_konto_rechnen(j5, 100000, 100000, False, False, 1.0, 0.85, random.Random(1))
check(1300 <= r2["tp"] <= 1500, f"The5ers 2. Zyklus: ein Trade TP {r2['tp']} (1.300–1.500)")
check(app.fcp_konto_rechnen(j5, 90000, 100000, False, False, 1.0, 0.85)["aktion"] == "aus", "The5ers am Boden (−10k) → aus")
check(app.fcp_konto_rechnen(j5, 100000, 100000, False, False, None, 0.85)["aktion"] == "aus", "ohne Punktwert → aus")
check(app.fcp_konto_rechnen(jg("FundingPips", 50000), 100000, 50000, True, False, 20, 0.85)["aktion"] == "aus", "unplausible Balance (100k auf 50k) → aus")
check(jg("FundingPips", 200000) is None, "FundingPips 200k gibt es nicht")
rm = app.fcp_konto_rechnen(j5, 101290, 100000, False, False, 1.0, 0.85, random.Random(2), param=dict(app.fcp_param_standard(), ziel_toleranz_pct=0.0))   # ZT1: ohne Toleranz (prüft den Mindest-TP)
check(rm["tp"] >= app.FCP_TP_MIN_USD, f"Rest bis Ziel winzig → Mindest-TP ({rm['tp']}, {rm['tp_art']})")
check(app.ap_regel_finden(FIRMEN, "Tradeify") is None and app.ap_regel_finden(FIRMEN, "Tradeify CFD")["namen"] == ["tradeifycfd"],
      "Tradeify-Futures trifft keine Regel, Tradeify CFD seine eigene")
rt = app.fcp_konto_rechnen(jg("Tradeify CFD", 100000), 98500, 100000, True, False, 10.0, 0.85, random.Random(5))
check(rt["aktion"] == "planen" and 3000 <= rt["tp"] <= 4000 and 2.5 <= rt["lots"] <= 3.1 and 1750 <= rt["sl"] <= 2400,
      f"Tradeify CFD 100k nach −1.500: TP {rt.get('tp')} (3.000–4.000), {rt.get('lots')} Lot, SL {rt.get('sl')}")

print("2b) TP-Deckel beim Nachholen (Finn 30.10.2026 ~07:20)")
R5 = dict(app.ap_regel_finden(FIRMEN, "The5%ers"), tp_modus="zyklen")   # alte Zyklus-Deckel nur noch mit ausdrücklichem Modus
j52 = jg("The5%ers", 200000)
for z, soll in ((1, 750), (2, 1500), (3, 3000), (4, 6000), (7, 6000)):
    t = app.fcp_konto_rechnen(j52, 185977, 200000, z, False, 1.0, 0.85, random.Random(1), R5)
    check(t["tp"] == soll, f"The5ers 200k …4186 bei −14.023, Zyklus {z}: TP {t['tp']} (Deckel {soll})")
t = app.fcp_konto_rechnen(j5, 93326, 100000, 2, False, 1.0, 0.85, random.Random(1), R5)
check(t["tp"] == 1500 and t["tp_art"] == "gedeckelt", f"The5ers 100k …8441 bei −6.674, Zyklus 2 (1 Payout): TP {t['tp']} statt 8.089")
t = app.fcp_konto_rechnen(j5, 100500, 100000, 3, False, 1.0, 0.85, random.Random(1), R5)
check(800 <= t["tp"] <= 1000 and t["tp_art"] == "ziel", f"The5ers Zyklus 3 mit +500: Rest bis Ziel {t['tp']} (unter dem Deckel)")
t = app.fcp_konto_rechnen(j5, 92000, 100000, True, False, 1.0, 0.85, random.Random(1), R5)
check(t["tp"] == 750, "The5ers Zyklus 1 nach −8.000: TP bleibt 750")
RF = app.ap_regel_finden(FIRMEN, "FundedNext")
t = app.fcp_konto_rechnen(j, 95000, 100000, 2, False, 10.0, 0.85, random.Random(1), RF)
check(t["tp"] == 1850 + 1000 and t["tp_art"] == "gedeckelt", f"FundedNext 100k −5.000: TP {t['tp']} = ziel[bis] 1.850 + 1.000")
t = app.fcp_konto_rechnen(j, 98000, 100000, 2, False, 10.0, 0.85, random.Random(7), RF)
check(t["tp"] == 2850 and t["tp_art"] == "gedeckelt", f"FundedNext 100k −2.000: TP {t['tp']} (Deckel 2.850, Rest morgen)")
RP, RT = app.ap_regel_finden(FIRMEN, "FundingPips"), app.ap_regel_finden(FIRMEN, "Tradeify CFD")
check(app.fcp_tp_deckel(RP, jg("FundingPips", 50000), 2) == (2000.0, "ziel_plus") and app.fcp_tp_deckel(RT, jg("Tradeify CFD", 100000), 1) == (3500.0, "ziel_plus"),
      "Deckel FundingPips 50k 2.000, Tradeify CFD 3.500 (auch Zyklus 1)")
check(app.fcp_tp_deckel(dict(R5, tp_zyklen=[500, 900]), j5, 5) == (900.0, "zyklus"), "tp_zyklen aus der Regel gewinnt (letzter Wert gilt weiter)")

print("2d) The5ers-Consistency (C5 04.11.2026; seit E1b 05.11.2026 Weg A: Endziel max(Z, B ÷ p × 1,02), Deckel p × F × 0,95, Rest gleich verteilt)")
RC = app.ap_regel_finden(FIRMEN, "The5%ers")
check(app.fcp_tp_modus(RC) == "consistency50" and app.fcp_tp_modus(app.ap_regel_finden(FIRMEN, "FundedNext")) is None, "Standard: nur The5ers consistency50")
GM = app.fcp_gewinne([{"status": "completed", "master_pl": 635.70}, {"status": "completed", "master_pl": 603.84}, {"status": "completed", "master_pl": 61.05},
                      {"status": "completed", "master_pl": -1315.00}, {"status": "planned", "master_pl": None}])
check(GM == 1300.59, f"Gewinne Moritz …2352 = 635,70 + 603,84 + 61,05 = {GM} (Verlust und geplanter zählen nicht)")
check(app.fcp_gewinne([{"status": "completed", "master_pl": 500}, {"status": "completed", "master_pl": None}]) is None, "beendeter Trade ohne P&L → nicht lesbar")
# Zyklus-Grenze: Payout am 02.11. → Zyklus ab 03.11. (Berlin); Gewinne davor zählen nicht, ein Trade ohne P&L aus dem alten Zyklus stört nicht
ZY = [{"status": "completed", "master_pl": 1470.0, "ended_at": "2026-10-28T10:00:00+00:00"},
      {"status": "completed", "master_pl": None, "ended_at": "2026-10-29T10:00:00+00:00"},
      {"status": "completed", "master_pl": 750.0, "ended_at": "2026-11-03T09:00:00+00:00"},
      {"status": "completed", "master_pl": -400.0, "ended_at": "2026-11-03T15:00:00+00:00"}]
check(app.fcp_gewinne(ZY, "2026-11-03") == 750.0, "nur Gewinne seit dem Zyklus-Beginn (alte 1.470 und alter Trade ohne P&L zählen nicht)")
check(app.fcp_zyklus_start([{"account_id": "k", "requested_at": "2026-11-02T18:00:00+00:00"}], [], []) == {"k": "2026-11-03"}, "Zyklus-Beginn = Tag nach der Payout-Anfrage")
check(app.fcp_gewinne(ZY[:1], "2026-11-03") == 0.0, "nur Gewinne vor dem Payout → Zyklus-Gewinne 0")
check(app.fcp_gewinne([{"status": "completed", "master_pl": 1470.0}], "2026-11-03") is None, "beendeter Trade ohne Zeit → Zyklus nicht zuordenbar → nicht lesbar (750)")


class Fest:            # Ziel genau auf einen Wert würfeln (Beispiele aus Finns Diktat)
    def __init__(self, ziel):
        self.z = ziel
    def uniform(self, lo, hi):
        return self.z if lo <= self.z <= hi else (lo + hi) / 2


# seit O1 (05.11.2026 ~07:45/07:50) CONSISTENCY NACH FINN statt Weg A: Rest R = Z − G (erhöht, bis B ≤ p × (W + R)), Deckel p × (W + R) × 0,95,
# TP = Zufall (p − 5 %) … p der Distanz (Fest → Mitte 47,5 %), Rest ≤ Deckel → genau der Rest. tage alt (B, Trades) → W ≈ max(G, B), keine Serie
tm = app.fcp_konto_rechnen(j5, 98685, 100000, 2, False, 1.0, 0.85, Fest(1310), RC, gewinne=GM, tage=(635.70, 3))
check(tm["tp"] == 1247 and tm["tp_art"] == "consistency" and tm["consistency"]["n"] == 2 and tm["consistency"]["rest"] == 2625,
      f"Moritz …2352: G −1.315, B 635,70, Z 1.310 → noch 2.625, Deckel 1.549, TP 47,5 % → {tm['tp']} (Soll 1.247), 2 Trades")
tf = app.fcp_konto_rechnen(j5, 100000, 100000, 1, False, 1.0, 0.85, Fest(1500), RC, gewinne=0.0, tage=(0.0, 0))
check(tf["tp"] == 712 and tf["consistency"]["n"] == 3, f"Zyklus-Beginn, Z 1.500 → TP {tf['tp']} (Soll 712 = Deckel), 3 Trades")
tx = app.fcp_konto_rechnen(j5, 95354, 100000, 1, False, 1.0, 0.85, Fest(1500), RC, gewinne=None, tage=None)
check(tx["tp"] == 712 and tx["tp_art"] == "consistency_ohne_zyklus", f"Zyklus nicht lesbar → Deckel mit F = Z: TP {tx['tp']} (Soll 712, fail-closed)")
tg = app.fcp_konto_rechnen(j5, 100500, 100000, 3, False, 1.0, 0.85, Fest(1400), RC, gewinne=900.0, tage=(900.0, 2))
check(tg["tp"] == 445 and tg["consistency"]["rest"] == 936 and tg["consistency"]["n"] == 2,
      f"großer Tag 900 bei G 500 → Rest erhöht auf 936 (B ≤ 50 % × W), TP {tg['tp']} (Soll 445), 2 Trades")
tk = app.fcp_konto_rechnen(j, 98000, 100000, 2, False, 10.0, 0.85, random.Random(7), app.ap_regel_finden(FIRMEN, "FundedNext"), gewinne=0.0)
check(tk["tp"] == 2850 and tk["tp_art"] == "gedeckelt", "FundedNext unverändert (Ziel + tp_deckel_plus)")

print("2e) Erster Payout = Refund (Finn 30.10.2026 ~08:00, nur FundedNext)")
RFN = app.ap_regel_finden(FIRMEN, "FundedNext")
for gg, hed in ((50000, 2500), (100000, 5000), (200000, 10000)):
    t = app.fcp_konto_rechnen(jg("FundedNext", gg), gg, gg, 1, False, 10.0, 0.85, random.Random(2), RFN)
    check(t["erster_payout"] and 50 <= t["tp"] <= 150 and t["hedge_eur"] == hed and t["tp_art"] == "erster_payout_refund",
          f"FundedNext {gg // 1000}k ohne Payout: TP {t['tp']} (50–150), Hedge {t['hedge_eur']} € (Soll {hed})")
t = app.fcp_konto_rechnen(j, 100100, 100000, 1, False, 10.0, 0.85, random.Random(2), RFN)
check(t["aktion"] == "ziel", "ohne Payout ab +50 → Ziel erreicht (Waiting for Payout)")
t = app.fcp_konto_rechnen(j, 97500, 100000, 1, False, 10.0, 0.85, Fest(100) if "Fest" in dir() else random.Random(3), RFN)
check(2550 <= t["tp"] <= 2650 and t.get("tp_deckel") is None, f"ohne Payout nach −2.500: TP {t['tp']} = ganzer Rest, kein Deckel")
t = app.fcp_konto_rechnen(j, 100030, 100000, 1, False, 10.0, 0.85, Fest(51) if "Fest" in dir() else random.Random(3), RFN)
check(t["tp"] >= 25, f"Rest winzig → mindestens 25 $ ({t['tp']})")
t = app.fcp_konto_rechnen(j, 100000, 100000, 2, False, 10.0, 0.85, random.Random(2), RFN)
check(not t["erster_payout"] and 1500 <= t["tp"] <= 1850 and t["hedge_eur"] == 1500, f"ab dem 1. Payout normal: TP {t['tp']}, Hedge {t['hedge_eur']}")
t = app.fcp_konto_rechnen(j, 100000, 100000, 1, True, 10.0, 0.85, random.Random(3), RFN)
check(t["erster_payout"] and 670 <= t["sl"] <= 780, "1-%-Regel bleibt (SL 670–780) auch im Refund-Zyklus")
check(not app.fcp_konto_rechnen(j5, 100000, 100000, 1, False, 1.0, 0.85, random.Random(2), app.ap_regel_finden(FIRMEN, "The5%ers"))["erster_payout"],
      "The5ers: kein Refund-Modus")
check(not app.fcp_konto_rechnen(j, 100000, 100000, 1, False, 10.0, 0.85, random.Random(2), dict(RFN, erster_payout=False))["erster_payout"],
      "erster_payout false in der Regel → aus")

PZ = app.fcp_payouts_zaehlen([{"account_id": "k1", "received_tx_id": "t1"}], [{"account_id": "k2"}],
                              [{"id": "t1", "account_id": "k1"}, {"id": "t2", "account_id": "k3"}, {"id": "t3", "account_id": None}])
check(PZ == {"k1": 1, "k2": 1, "k3": 1}, f"Payouts zählen: Anfrage + verknüpfte Buchung einmal, managed, nur gebucht (Prüfer S2) — {PZ}")

print("2f) Refund-Lots nach Verhältnis × 2 (Finn 03.11.2026 ~01:00 Dubai: „die Werte gefallen mir sehr gut“; vorher × 0,1 aus .2002, ÷ 5 seit 30.10.2026)")


class Folge:           # Würfe der Reihe nach: Ziel, SL, Lots, Normal-Ziel (nur Refund) wie beim echten Plan
    def __init__(self, *w):
        self.w = list(w)
    def uniform(self, lo, hi):
        return self.w.pop(0)


RFL = app.ap_regel_finden(FIRMEN, "FundedNext")
# Finns 5 Beispiele mit den Mittelwerten 1,375 Lot / 1.675 $ (Refund-TP = Ziel − Gewinn, Gewinn 0 → Ziel = TP)
for tp_soll, lots_soll in ((50, 0.08), (71, 0.11), (100, 0.16), (150, 0.24)):
    r = app.fcp_konto_rechnen(j, 100000, 100000, 1, False, 10.0, 0.85, Folge(tp_soll, 2000, 1.375, 1675), RFL)
    check(r["tp"] == tp_soll and r["lots"] == lots_soll, f"Refund-TP {tp_soll} → {r['lots']} Lot (soll {lots_soll})")
r = app.fcp_konto_rechnen(j, 98920, 100000, 1, False, 10.0, 0.85, Folge(50, 2000, 1.375, 1675), RFL)
# 1,375 kommt beim Würfeln schon auf 2 Stellen gerundet (fcp_wuerfel → 1,38) — gedeckelt wird auf die gezogenen Normal-Lots; mit 1,37 gezogen → 1,37
check(r["tp"] == 1130 and r["lots"] == 1.38, f"Refund-TP 1.130 (nach −1.080) → gedeckelt auf die gezogenen Normal-Lots ({r['tp']}, {r['lots']})")
r = app.fcp_konto_rechnen(j, 98920, 100000, 1, False, 10.0, 0.85, Folge(50, 2000, 1.37, 1675), RFL)
check(r["lots"] == 1.37, f"TP 1.130 mit 1,37 gezogen → 1,37 ({r['lots']})")
check(abs(app.fcp_konto_rechnen(j, 100000, 100000, 1, False, 10.0, 0.85, Folge(100, 2000, 1.375, 1675), RFL)["tp_pkt"] - 1675 / 13.75 / 2) < 3,
      "halber Punktabstand des Normal-Trades (≈ 61 Pkt)")
ez = app.fcp_konto_rechnen(j, 100002.11, 100000, 1, False, 10.0, 0.85, Folge(73, 2374, 1.33, 1675), RFL)
check(ez["lots"] == 0.11 and ez["refund_lots"] == {"normal_lots": 1.33, "normal_ziel": 1675, "tp": 71}, f"EzPoker 1,33 Lot, TP 71 → {ez['lots']} ({ez.get('refund_lots')})")
check(ez["tp"] == 71 and ez["sl"] == 2374, f"TP-$ und SL-$ wie vorher ({ez['tp']} / {ez['sl']})")
check(ez["hedge_eur"] == 5000 and ez["hedge_sl_eur"] == 1187 and ez["hedge_tp_eur"] == -35.5, f"Hedge-€ wie vorher (5.000 auf 10.000 DD, SL +{ez['hedge_sl_eur']}, TP {ez['hedge_tp_eur']})")
alt = app.gp_hedge(10000, 5000, 1.33, 10.0, 0.85)[0]
check(ez["multiplier"] == alt["multiplier"], f"multiplier unverändert ({ez['multiplier']}), hängt nur an € ÷ DD")
check(abs(ez["hedge_lots"] - 0.11 * ez["multiplier"]) < 0.011 and ez["hedge_lots"] < alt["lots"], f"Fusion-Lots folgen den Master-Lots ({alt['lots']} → {ez['hedge_lots']})")
nz = app.fcp_konto_rechnen(j, 100000, 100000, 2, False, 10.0, 0.85, Folge(1600, 2000, 1.33), RFL)
check(nz["lots"] == 1.33 and nz["hedge_eur"] == 1500 and not nz["erster_payout"] and "refund_lots" not in nz, "Payout-Fall unverändert (1,33 Lot, Hedge 1.500)")
check(app.fcp_lots_faktor(1, 0.1) == 0.1 and app.fcp_lots_faktor(1.33, 0.1) == 0.13 and app.fcp_lots_faktor(0.05, 0.1) == 0.01, "Rückfall-Faktor ohne Normal-Ziel: abrunden, Mindest-Lot 0,01")
V = app.fcp_lots_verhaeltnis
check(V(1.0, 10, 1850, 2.0) == 0.01 and V(None, 100, 1500) is None and V(1.5, 100, 0) is None, "Mindest-Schritt 0,01, fehlende Werte → None")
winz = app.fcp_konto_rechnen(j, 100000, 100000, 1, False, 10.0, 0.85, Folge(100, 2000, 1.5, 1500), dict(RFL, erster_payout={"ziel": [50, 150], "hedge_eur_je_dd": 0.0005}))
check(winz["aktion"] == "aus" and "Lot" in winz["grund"], f"Hedge unter Min-Lot → aus, kein Plan ({winz.get('grund')})")
src_app = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
check("(Refund: halber Normal-Abstand)" in src_app, "Vorschlags-Notiz „≈ X Pkt (Refund: halber Normal-Abstand)“")

print("2c) 1-%-Konto über den Namen + SL nie über max_risiko_trade (Vorfall Jacob …7924, 30.10.2026)")
E = app.fcp_eins_prozent
check(E({"name": "100k 14197924 → Funded · 1% RULE"}) and E({"name": "x 1%-RULE"}) and E({"name": "x 1 % rule"}) and E({"max_risiko_trade": 1000}),
      "1-%-Konto: Name „1% RULE“ (alle Schreibweisen) oder max_risiko_trade")
check(not E({"name": "100k → Funded"}) and not E({"name": "11% rule"}) and not E({"name": "x", "max_risiko_trade": 0}), "kein 1-%-Konto ohne Kennung")
RF2 = app.ap_regel_finden(FIRMEN, "FundedNext")
jj = app.fcp_konto_rechnen(j, 96882, 100000, 1, E({"name": "100k 14197924 → Funded · 1% RULE"}), 10.0, 0.85, random.Random(4), RF2)
check(jj["eins_prozent"] and 670 <= jj["sl"] <= 780, f"Jacob …7924 ohne max_risiko_trade, nur Name: SL {jj['sl']} (670–780 statt 2.417)")
for s_ in range(20):
    t = app.fcp_konto_rechnen(j5, 100000, 100000, 2, False, 1.0, 0.85, random.Random(s_), R5, max_sl=1000)
    if t["sl"] > 1000:
        break
check(t["sl"] <= 1000 and t.get("sl_gedeckelt"), f"The5ers mit max_risiko_trade 1.000: SL {t['sl']} (nie darüber, auch ohne sl_1pct)")
check(app.fcp_konto_rechnen(j, 100000, 100000, 1, True, 10.0, 0.85, random.Random(3), RF2, max_sl=700)["sl"] <= 700, "1-%-SL zusätzlich auf max_risiko_trade 700 gedeckelt")

print("3) Richtungsschutz + Sicht")
app.FCP_RICHTUNG_LAUFEND_UEBERNEHMEN = True       # Logik der Übernahme (Schalter für den Rückweg) — danach wieder wie live
fest = app.fcp_fest_richtung([{"user_id": "u1", "master_firm": "FundedNext", "status": "planned", "richtung": "sell"},
                              {"user_id": "u1", "master_firm": "FundedNext", "status": "open", "richtung": "buy"},
                              {"user_id": "u2", "master_firm": "The5%ers", "status": "completed", "richtung": "buy"}])
check(fest == {"u1|" + app._ap_norm(app._firm_norm("FundedNext")): "buy"}, f"laufender Trade schlägt geplanten, beendete zählen nicht ({fest})")
check(all(app.fcp_richtung("sell", random.Random(s)) == "sell" for s in range(20)), "feste Richtung wird übernommen")
check({app.fcp_richtung(None, random.Random(s)) for s in range(40)} == {"buy", "sell"}, "ohne Trade gewürfelt")
check(app.fcp_fest_richtung([{"user_id": "u1", "master_firm": "FundedNext", "status": "planned", "richtung": "sell"}]) == {},
      "geplanter Plan gibt keine Richtung vor (Finn 30.10.2026 ~08:05)")
app.FCP_RICHTUNG_LAUFEND_UEBERNEHMEN = False
check(app.fcp_fest_richtung([{"user_id": "u1", "master_firm": "FundedNext", "status": "open", "richtung": "sell"}]) == {},
      "live (.1934): auch ein laufender Trade gibt keine Richtung mehr vor — der Start dreht (fa00bea0)")
lo = sum(app.fcp_richtung(None, random.Random(s)) == "buy" for s in range(400))
check(170 <= lo <= 230, f"50/50 gewürfelt ({lo} von 400 long)")
gr = {"e1": frozenset({"e1", "e2"}), "e2": frozenset({"e1", "e2"})}
von = lambda u: gr.get(u)   # noqa: E731
check(app.fcp_gruppen_sicht("h1", ["h1", "h2", "e1", "e2"], von) == frozenset({"h1", "h2"}), "HT-Login sieht nur HT")
check(app.fcp_gruppen_sicht("e2", ["h1", "e1", "e2"], von) == frozenset({"e1", "e2"}), "Emin-Login sieht nur Emins Gruppe")
check(app.fcp_gruppen_sicht("x9", ["h1", "x9"], von, nur_eigene=True) == frozenset({"x9"}), "„nur eigene“ ohne Gruppe sieht nur sich")
check(app.fcp_schreib_sicht(None, frozenset({"h1"})) == frozenset({"h1"}), "Admin schreibt nur in der eigenen Gruppe")
pf, _a = app.fdp_eingriff_filter("bestaetigen", ["11111111-2222-4333-8444-555555555555"])
pc, _a = app.fdp_eingriff_filter("bestaetigen", ["11111111-2222-4333-8444-555555555555"], art="cfd")
check(pf["mt5_baseline->funded_plan->>art"] == "is.null" and pc["mt5_baseline->funded_plan->>art"] == "eq.cfd",
      "Funded-Routen fassen nur Apex-Vorschläge an, CFD-Routen nur CFD")
check(app.fcp_schreib_sicht("e1", frozenset({"h1"})) == "e1", "eigene ID bleibt eigene ID (nur eigene Pläne)")

print("4) Ganzer Lauf gegen nachgebaute DB")
JETZT = datetime(2026, 11, 2, 4, 0, tzinfo=timezone.utc)          # Montag 08:00 Dubai
H1, H2, E1 = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "33333333-3333-3333-3333-333333333333"
FUS = {H1: "f1", H2: "f2", E1: "f3"}
frisch = (JETZT - timedelta(minutes=30)).isoformat()
konto = lambda i, u, n, f, b, **x: dict({"id": i, "user_id": u, "name": n, "firm": f, "account_type": "funded_cfd", "external_id": "L" + i[-4:],
                                          "tv_balance": None, "created_at": "2026-10-01T00:00:00+00:00"}, **x, _bal=b)   # noqa: E731
KONTEN = [konto("a1000000-0000-0000-0000-000000000001", H1, "100k 1 → Funded", "FundedNext", 98000.0),
          konto("a1000000-0000-0000-0000-000000000002", H1, "100k 2 → Funded", "FundedNext", 100000.0),
          konto("a1000000-0000-0000-0000-000000000003", H2, "200k 3 → Funded", "The5%ers", 200000.0),
          konto("a1000000-0000-0000-0000-000000000004", H2, "100k 4 → Funded", "The5%ers", 101600.0),
          konto("a1000000-0000-0000-0000-000000000005", H2, "50k 5 → Funded", "FundingPips", 50000.0, max_risiko_trade=None),
          konto("a1000000-0000-0000-0000-000000000006", H2, "100k Flex 6 → Funded", "FundingPips", 100000.0),
          konto("a1000000-0000-0000-0000-000000000007", E1, "100k 7 → Funded", "FundedNext", 100000.0, max_risiko_trade=1000),
          konto("a1000000-0000-0000-0000-000000000008", E1, "100k 8 → Funded", "FundedNext", 101000.0, waiting_payout_since="2026-10-30T00:00:00+00:00")]
OFFEN = [{"user_id": H1, "master_firm": "FundedNext", "status": "open", "richtung": "sell", "started_at": (JETZT - timedelta(hours=1)).isoformat()}]
REG = {"id": 1, "aktiv": False, "auto_bestaetigen": False, "ziel_auto_wartet": False, "user_ids": [H1, H2, E1], "firmen": FIRMEN,
       "zeiten": {"firma_abstand_min": 15, "abstand_id_min": 10, "vorlauf_min": 15}}
GESCHRIEBEN = []


def sb_select(t, p):
    if t == "funded_cfd_plan_regeln":
        return [REG]
    if t == "auto_plan_regeln":
        return [{"zeiten": {"fenster_tz": "Asia/Dubai", "fenster": [["04:00", "18:00"]]}}]
    return []


def sb_all(t, p):
    if t == "accounts" and p.get("account_type") == "eq.funded_cfd":
        return [{k: v for k, v in a.items() if k != "_bal"} for a in KONTEN]
    if t == "accounts":
        # M3 (05.11.2026): seit 02.11. nimmt der Planer nur ein Hedge-Konto der EIGENEN ID (gp_hedge_settings_eigen liest id,user_id,external_id) — der Stub
        # nennt darum den Besitzer; ohne user_id galt jedes Fusion-Konto als fremd und kein Konto wurde geplant
        return [{"id": v, "user_id": u, "external_id": "9" + v[1:] + "0001", "name": "Fusion " + v, "firm": "Fusion Markets"} for u, v in FUS.items()]
    if t == "trade_plans" and "status" in p:
        return OFFEN
    if t == "user_settings":
        return [{"user_id": u, "value": {"accountId": f}} for u, f in FUS.items()]
    if t == "firm_specs":
        return [{"user_id": u, "name": n, "ppl": PPL[app._ap_norm(n)], "unit": "Lots"} for u in FUS for n in ("FundedNext", "The5%ers", "FundingPips")]
    if t == "id_gruppe_mitglied":
        return [{"user_id": H1, "gruppe_id": "ht"}, {"user_id": H2, "gruppe_id": "ht"}, {"user_id": E1, "gruppe_id": "emin"}]
    return []


app.sb_select, app._sb_all = sb_select, sb_all
app.sb_insert = lambda t, z: GESCHRIEBEN.append((t, z))
app.sb_update = lambda *a: GESCHRIEBEN.append(("update",) + a)
app._ap_archiviert = lambda streng=False: set()
app._ap_namen = lambda: ({H1: "HT-1", H2: "HT-2", E1: "Emin-1"}, set())
app._ap_balance_karten = lambda: ({a["external_id"]: (a["_bal"], "USD", frisch) for a in KONTEN}, {})
erg = app.fcp_planen(trocken=True, jetzt=JETZT, seed=42)
print(f"     Tag {erg['tag']} · Fenster {erg['zeiten']['von']}–{erg['zeiten']['bis']} {erg['zeiten']['tz']}")
for z in erg["geplant"]:
    print(f"     PLAN {z['user']:7} {z['firma']:11} {z['konto']:22} {z['start']} {z['richtung']:4}{' (Schutz)' if z['richtung_geschuetzt'] else '':9} "
          f"Gewinn {z['gewinn']:>7.0f} → TP {z['tp']:>5.0f} ({z['tp_art']}) SL {z['sl']:>5.0f} {z['lots']:>5} Lot · Hedge {z['hedge_lots']} Lot / {z['hedge_eur']:.0f} €")
for z in erg["ziel"]:
    print(f"     ZIEL {z['konto']}: {z['grund']}")
for z in erg["ausgelassen"]:
    print(f"     AUS  {z['konto']}: {z['grund']}")
gp = {z["konto"]: z for z in erg["geplant"]}
check(len(erg["geplant"]) == 5, f"5 Vorschläge ({len(erg['geplant'])})")
_r = []
for _s in range(12):
    _e = app.fcp_planen(trocken=True, jetzt=JETZT, seed=_s)
    _r += [z["richtung"] for z in _e["geplant"] if z["user_id"] in (H1, H2)]
check(set(_r) == {"buy", "sell"}, "Konten derselben ID würfeln je selbst — auch neben einem laufenden Short (keine Bindung, kein Übernehmen)")
check(gp["100k 1 → Funded"]["tp_art"] == "erster_payout_refund" and 2050 <= gp["100k 1 → Funded"]["tp"] <= 2150 and gp["100k 1 → Funded"]["hedge_eur"] == 5000,
      "Konto mit −2k ohne Payout: Refund-Ziel ganz nachholen (2.050–2.150), Hedge 5.000 €")
check(gp["100k 7 → Funded"]["eins_prozent"] and gp["100k 7 → Funded"]["sl"] <= 780, "Emin-Konto mit 1-%-Regel: kleiner SL")
z3 = gp["200k 3 → Funded"]
check(str(z3["tp_art"]).startswith("consistency") and z3["tp"] <= 0.5 * 0.95 * z3["ziel_bis"] + 1, f"The5ers 200k frisch: TP {z3['tp']} ≤ Deckel (Consistency Weg A)")
check([z["konto"] for z in erg["ziel"]] == ["100k 4 → Funded"], "The5ers +1.600 → Ziel (Waiting for Payout)")
aus = {z["konto"]: z["grund"] for z in erg["ausgelassen"]}
check("Flex" in aus.get("100k Flex 6 → Funded", ""), "Flex nicht geplant")
check("Waiting for Payout" in aus.get("100k 8 → Funded", ""), "Waiting for Payout nie planen")
mins = {}
for z in erg["geplant"]:
    mins.setdefault(z["user_id"], []).append(datetime.fromisoformat(z["start_um"]))
check(all(abs((a - b).total_seconds()) >= 600 for v in mins.values() for i, a in enumerate(v) for b in v[i + 1:]), "≥ 10 min zwischen Starts derselben ID")
check(not GESCHRIEBEN, "Trockenlauf schreibt nichts")
# Konto 100k 2 (FundedNext, frisch) hatte einen Payout, der nur als transactions-Buchung steht → kein Refund-Modus
_a0 = app._sb_all
app._sb_all = lambda t, p: ([{"id": "tx9", "account_id": KONTEN[1]["id"]}] if t == "transactions" else _a0(t, p))
_e = app.fcp_planen(trocken=True, jetzt=JETZT, seed=42)
_z = {z["konto"]: z for z in _e["geplant"]}
check(not _z["100k 2 → Funded"]["erster_payout"] and _z["100k 2 → Funded"]["hedge_eur"] == 1500 and _z["100k 1 → Funded"]["erster_payout"],
      "Payout nur als Buchung (transactions kind payout) → normale Regeln, Hedge 1.500 statt 5.000")
def _kaputt(t, p):
    if t == "transactions":
        raise RuntimeError("weg")
    return _a0(t, p)
app._sb_all = _kaputt
_e = app.fcp_planen(trocken=True, jetzt=JETZT, seed=42)
check(not any(z["erster_payout"] for z in _e["geplant"]), "Payouts nicht lesbar → kein Refund-Modus (fail-closed)")
app._sb_all = _a0
_alt = app._sb_all
PLAN_OFFEN = {"id": "p1", "user_id": H1, "master_account_id": KONTEN[0]["id"], "master_firm": "FundedNext", "status": "open", "richtung": "sell",
              "started_at": "2026-10-31T05:00:00+00:00", "master_contracts": 1.2, "multiplier": 1.5, "notes": "Funded-CFD-Planer · Vorschlag"}
app._sb_all = lambda t, p: [dict(PLAN_OFFEN)] if t == "trade_plans" and "master_account_id" in p else _alt(t, p)
ws = app.fcp_planen(trocken=True, jetzt=datetime(2026, 10, 31, 6, 0, tzinfo=timezone.utc))
app._sb_all = _alt
check(ws.get("msg", "").startswith("Wochenende") and not ws["geplant"], "Samstag: nichts geplant")
pw = (ws.get("plaene") or [{}])[0]
check(len(ws.get("plaene") or []) == 1 and pw.get("funded_cfd_plan") and pw.get("groesse") == 100000 and pw.get("dd") == 10000 and pw.get("balance") == 98000,
      "Samstag: bestehender Plan trotzdem in plaene, mit Größe/DD/Balance (Notiz als Kennung)")
erg2 = app.fcp_planen(trocken=False, jetzt=JETZT, seed=42)
zeilen = [g[1] for g in GESCHRIEBEN if g[0] == "trade_plans"]   # O1: GESCHRIEBEN enthält auch Updates (3-Tupel)
check(len(zeilen) == 5 and all(z["start_um"] is None and z["auto_bestaetigt_at"] is None and z["route"] == "mt5" and z["auto_plan"] is False
                               and z["slave_account_id"] and z["mt5_baseline"]["funded_plan"]["art"] == "cfd" for z in zeilen),
      "scharf: 5 Vorschläge ohne start_um, Echo mit Slave, Kennung funded_plan.art cfd")
# WP3 (Finn 10.11.2026 ~01:40: „Das soll einfach kein Schalter dafür sein"): Ziel erreicht → IMMER Waiting for Payout, auch mit ziel_auto_wartet False,
# Guard wie der Knopf (funded_cfd, waiting_payout_since leer); Meldung nur, wenn das Update eine Zeile geändert hat (der Stub liefert None → keine)
_wu = [g for g in GESCHRIEBEN if g[0] == "update" and "waiting_payout_since" in (g[3] if len(g) > 3 else {})]
check(REG["ziel_auto_wartet"] is False and len(_wu) == 1 and _wu[0][2] == {"id": f"eq.{KONTEN[3]['id']}", "account_type": "eq.funded_cfd", "waiting_payout_since": "is.null"}
      and not [g for g in GESCHRIEBEN if g[0] == "update" and not ({"fcp_ziel", "waiting_payout_since"} & set(g[3] if len(g) > 3 else {}))],
      "WP3: Ziel erreicht stellt auch mit ziel_auto_wartet aus auf Waiting for Payout um (Guard funded_cfd + waiting_payout_since leer)")
check(erg2.get("ziel_auto_wartet") is True and erg2.get("wartet_neu") == [], "WP3: Antwort ziel_auto_wartet immer an; Guard ohne geänderte Zeile → kein Eintrag, keine Meldung")
_MELD, _GESCH0 = [], list(GESCHRIEBEN)
_al, _upd0 = app.alarm_senden, app.sb_update
app.alarm_senden = lambda *a, **k: _MELD.append((a, k)) or (1, 1)
app._alarm_fremd_verwaltet = lambda uid: str(uid) == E1
app.sb_update = lambda t, f, u: (GESCHRIEBEN.append(("update", t, f, u)) or ([{"id": f["id"][3:]}] if "waiting_payout_since" in u else []))
# Unternehmen (Nachzug 10.11.2026): HT = Gruppe ohne Verwalter, Emin = Gruppe mit Verwalter
_gd0 = app.admin_gruppen_daten
app.admin_gruppen_daten = lambda: {"gruppen": [{"id": "ht", "name": "Hermann Technologies", "verwalter_id": None}, {"id": "emin", "name": "Emin", "verwalter_id": E1}],
                                   "mitglieder": [{"user_id": H1, "gruppe_id": "ht"}, {"user_id": H2, "gruppe_id": "ht"}, {"user_id": E1, "gruppe_id": "emin"}]}
erg3 = app.fcp_planen(trocken=False, jetzt=JETZT, seed=42)
_wn = erg3.get("wartet_neu") or []
check(len(_wn) == 1 and _wn[0]["umgestellt"] is True and _wn[0]["konto_id"] == KONTEN[3]["id"] and _wn[0]["gewinn"] == 1600 and _wn[0]["ziel"]
      and len(_MELD) == 1 and _MELD[0][0][0] == 3 and _MELD[0][0][2] == "Ziel erreicht → Waiting for Payout"
      and "HT-2 · 100k 4 → Funded · Gewinn 1.600 $ / Ziel" in _MELD[0][0][3] and _MELD[0][1]["schluessel"].startswith(f"fcp-wartet-{KONTEN[3]['id']}-"),
      f"WP3: umgestellt → Eintrag wartet_neu + eine ⚪-Meldung an die Master-IDs ({_MELD[0][0][3] if _MELD else '—'})")
_lauf = [g[1] for g in GESCHRIEBEN[len(_GESCH0):] if g[0] == "auto_plan_lauf"]
check(_lauf and _lauf[-1]["ergebnis"].get("wartet_neu") == _wn, "WP3: Eintrag auch im Planer-Lauf (auto_plan_lauf.ergebnis.wartet_neu)")
# Nachzug 10.11.2026: Emin-Konto am Ziel (Gruppe mit Verwalter) → NICHT umgestellt, nur angezeigt, keine Meldung, und ohne Umstellung keine Lauf-Zeile
KONTEN[6]["_bal"] = 104000.0
_MELD.clear()
_n0 = len(GESCHRIEBEN)
_KONTEN_ALLE = list(KONTEN)
KONTEN[:] = [KONTEN[6], KONTEN[7]]          # nur Emins Konten: eins am Ziel, eins schon Waiting → kein Plan, keine echte Umstellung
erg4 = app.fcp_planen(trocken=False, jetzt=JETZT, seed=42)
KONTEN[:] = _KONTEN_ALLE
_wn4 = {z["konto_id"]: z for z in erg4.get("wartet_neu") or []}
_neu4 = GESCHRIEBEN[_n0:]
check(_wn4.get(KONTEN[6]["id"], {}).get("umgestellt") is False and "nicht Hermann Technologies" in _wn4[KONTEN[6]["id"]].get("grund", "")
      and not [g for g in _neu4 if g[0] == "update" and "waiting_payout_since" in g[3]] and not _MELD,
      "Nachzug: Konto einer Gruppe mit Verwalter (Emin) wird nicht umgestellt, nur angezeigt, keine Meldung")
check(not [g for g in _neu4 if g[0] == "auto_plan_lauf"] and not [g for g in _neu4 if g[0] == "trade_plans"],
      "Nachzug: Lauf ohne Plan und ohne echte Umstellung schreibt keine auto_plan_lauf-Zeile (sonst bis 288 je Tag)")
KONTEN[6]["_bal"] = 100000.0
# Gruppen nicht lesbar → niemand automatisch (fail-closed)
def _gd_kaputt():
    raise RuntimeError("weg")
app.admin_gruppen_daten = _gd_kaputt
_n0 = len(GESCHRIEBEN)
erg5 = app.fcp_planen(trocken=False, jetzt=JETZT, seed=42)
check(not [g for g in GESCHRIEBEN[_n0:] if g[0] == "update" and "waiting_payout_since" in g[3]]
      and all(not e["umgestellt"] for e in erg5["wartet_neu"]), "Nachzug: Gruppen nicht lesbar → kein Konto automatisch umgestellt")
app.admin_gruppen_daten = lambda: {"gruppen": [{"id": "ht", "name": "Hermann Technologies", "verwalter_id": None}, {"id": "emin", "name": "Emin", "verwalter_id": E1}],
                                   "mitglieder": [{"user_id": H1, "gruppe_id": "ht"}, {"user_id": H2, "gruppe_id": "ht"}, {"user_id": E1, "gruppe_id": "emin"}]}
# Merker „zurück" (Master 10.11.2026): Balance noch nicht eingetragen → Planer trägt seine Lesung ein und hält; gleiche Balance → hält; geändert → löscht + stellt um
_MK = {}
_a1 = app._sb_all
app._sb_all = lambda t, p: ([{"id": k, "fcp_wartet_zurueck": v} for k, v in _MK.items()] if t == "accounts" and p.get("select") == "id,fcp_wartet_zurueck" else _a1(t, p))
K4 = KONTEN[3]["id"]
for _m, _soll_u, _soll_m, _txt in (({"at": "2026-11-10T01:00:00+00:00", "von": "x", "balance": None}, False, 101600.0, "Merker ohne Balance → Lesung eingetragen, nicht umgestellt"),
                                   ({"at": "2026-11-10T01:00:00+00:00", "von": "x", "balance": 101600.0}, False, "kein", "Merker, Balance unverändert → nicht umgestellt"),
                                   ({"at": "2026-11-10T01:00:00+00:00", "von": "x", "balance": 100900.0}, True, None, "Merker, Balance geändert (Trade lief) → Merker gelöscht, umgestellt")):
    _MK.clear(); _MK[K4] = _m
    _n0 = len(GESCHRIEBEN)
    _e = app.fcp_planen(trocken=False, jetzt=JETZT, seed=42)
    _neu = GESCHRIEBEN[_n0:]
    _mu = [g for g in _neu if g[0] == "update" and "fcp_wartet_zurueck" in g[3]]
    _w = {z["konto_id"]: z for z in _e["wartet_neu"]}.get(K4, {})
    ok_m = (not _mu) if _soll_m == "kein" else (len(_mu) == 1 and _mu[0][2].get("fcp_wartet_zurueck->>at") == "eq." + _m["at"]
                                               and ((_mu[0][3]["fcp_wartet_zurueck"] or {}).get("balance") if _soll_m else _mu[0][3]["fcp_wartet_zurueck"]) == _soll_m)
    check(ok_m and _w.get("umgestellt") is _soll_u and (_soll_u or "zurückgesetzt" in _w.get("grund", "")), f"Merker: {_txt}")
_MK.clear()
app._sb_all = _a1
check(app.fcp_merker_urteil(None, 1.0) is None and app.fcp_merker_urteil({"balance": None}, 100.0) == "fuellen"
      and app.fcp_merker_urteil({"balance": 100.0}, 100.6) == "halten" and app.fcp_merker_urteil({"balance": 100.0}, 102.0) == "loeschen"
      and app.fcp_merker_urteil({"balance": 100.0}, None) == "halten", "fcp_merker_urteil: fuellen / halten (±1 $, keine Balance) / loeschen")
app.admin_gruppen_daten = _gd0
app.alarm_senden, app.sb_update = _al, _upd0
# rein: Consistency ungeprüft (Zyklus nicht lesbar) → nicht umstellen, nur anzeigen; Gewinntage offen → nicht
check(app.fcp_ziel_echt({"aktion": "ziel"}) == (True, None)
      and app.fcp_ziel_echt({"aktion": "ziel", "consistency": {"p": 50, "bester_tag": 900.0, "ende": 4000}})[0] is True
      and app.fcp_ziel_echt({"aktion": "ziel", "consistency": {"p": 50, "bester_tag": None, "ende": 4000}})[0] is False
      and app.fcp_ziel_echt({"aktion": "ziel", "gewinntage": [2, 3]})[0] is False and app.fcp_ziel_echt({"aktion": "planen"})[0] is False,
      "WP3 fcp_ziel_echt: nur echtes Ziel (Consistency mit lesbarem Zyklus, Gewinntage voll)")
_t, _x, _d = app.fcp_wartet_meldung({"user": "HT-1", "konto": "100k X", "gewinn": 4100.0, "consistency": {"ende": 4000}, "zyklus": 2, "konto_id": "k"})
check(_t == "Ziel erreicht → Waiting for Payout" and _x == "HT-1 · 100k X · Gewinn 4.100 $ / Ziel 4.000 $ · Zyklus 2" and app.alarm_prio_aus_titel(_t) == 3,
      f"WP3 Meldungstext ⚪ ({_x})")
# O1 (05.11.2026): festes Ziel je Konto — im echten Lauf einmal geschrieben, mit Guard „noch keins gespeichert" (fcp_ziel=is.null)
_fz = [g for g in GESCHRIEBEN if g[0] == "update" and "fcp_ziel" in (g[3] if len(g) > 3 else {})]
check(_fz and all(g[2].get("fcp_ziel") == "is.null" and isinstance(g[3]["fcp_ziel"].get("usd"), float) for g in _fz),
      f"festes Ziel je geplantem Konto gespeichert, Guard is.null ({len(_fz)} Konten)")
check(all(z["mt5_baseline"]["funded_plan"]["start_um"] for z in zeilen), "Vorschlagszeit in mt5_baseline.funded_plan.start_um")
s = app.fcp_sicht(erg, frozenset({E1}))
check({z["user_id"] for z in s["geplant"] + s["ausgelassen"]} == {E1}, "Sicht Emin: nur Emins Zeilen")
z0 = zeilen[0]
check(abs(z0["multiplier"] * z0["master_contracts"] - [g for g in erg2["geplant"] if g["konto_id"] == z0["master_account_id"]][0]["hedge_lots"]) < 0.02,
      "multiplier × Lots = Hedge-Lots")

print("2h) Trades je Tag (E1e, Finn 05.11.2026 ~08:30): bis N je Konto und Tag, nie gleichzeitig, Standard 1 = wie bisher")
_alt2 = app._sb_all
_heute = {"id": "pz1", "user_id": H1, "master_account_id": KONTEN[0]["id"], "master_firm": "FundedNext", "status": "completed", "master_pl": 300.0,
          "started_at": (JETZT - timedelta(hours=2)).isoformat(), "ended_at": (JETZT - timedelta(hours=1, minutes=30)).isoformat()}
app._sb_all = lambda t, p: ([dict(_heute)] if t == "trade_plans" and "master_account_id" in p else _alt2(t, p))
def _grund(e, kid):
    return next((x.get("grund") for x in e["ausgelassen"] if x.get("konto_id") == kid), None)
e1 = app.fcp_planen(trocken=True, jetzt=JETZT, seed=42)
check(_grund(e1, KONTEN[0]["id"]) == "heute schon getradet" and KONTEN[0]["id"] not in {g["konto_id"] for g in e1["geplant"]},
      "ohne Einstellung (1): nach einem Trade heute → „heute schon getradet“ (wie bisher)")
REG["zeiten"]["trades_je_tag"] = 2
e2 = app.fcp_planen(trocken=True, jetzt=JETZT, seed=42)
check(KONTEN[0]["id"] in {g["konto_id"] for g in e2["geplant"]} or not (_grund(e2, KONTEN[0]["id"]) or "").startswith("heute schon"),
      f"Trades je Tag 2: nach einem Trade heute wird das Konto wieder geplant ({_grund(e2, KONTEN[0]['id']) or 'geplant'})")
_heute2 = dict(_heute, id="pz2", started_at=(JETZT - timedelta(hours=1)).isoformat(), ended_at=(JETZT - timedelta(minutes=40)).isoformat())
app._sb_all = lambda t, p: ([dict(_heute), dict(_heute2)] if t == "trade_plans" and "master_account_id" in p else _alt2(t, p))
e3 = app.fcp_planen(trocken=True, jetzt=JETZT, seed=42)
check((_grund(e3, KONTEN[0]["id"]) or "").startswith("heute schon 2 Trades"), f"Trades je Tag 2: nach zwei Trades → aus ({_grund(e3, KONTEN[0]['id'])})")
_off = dict(_heute, id="pz3", status="open", ended_at=None)
app._sb_all = lambda t, p: ([dict(_off)] if t == "trade_plans" and "master_account_id" in p else _alt2(t, p))
e4 = app.fcp_planen(trocken=True, jetzt=JETZT, seed=42)
check(_grund(e4, KONTEN[0]["id"]) == "läuft gerade", "nie gleichzeitig: läuft ein Trade, plant er keinen zweiten")
del REG["zeiten"]["trades_je_tag"]
app._sb_all = _alt2

print("2i) WP3-Zusatz (10.11.2026): POST /admin/funded-cfd-plan/waiting-zurueck — nur Admin, Gruppe beachten, nur funded_cfd mit Waiting")
_K = {"id": KONTEN[7]["id"], "user_id": E1, "name": KONTEN[7]["name"], "firm": "FundedNext", "account_type": "funded_cfd",
      "waiting_payout_since": "2026-10-30T00:00:00+00:00"}
_UPD = []
_s0, _u0, _g0, _l0 = app.sb_select, app.sb_update, app._planer_schreib_gate, app._fcp_login
app.sb_select = lambda t, p: [dict(_K)] if t == "accounts" and p.get("id") == f"eq.{_K['id']}" else []
app.sb_update = lambda t, f, u: _UPD.append((t, f, u)) or [dict(_K, **u)]
app._planer_schreib_gate = lambda: None
_LOGIN = {"v": (True, "admin-uid", None, None, None)}
app._fcp_login = lambda: _LOGIN["v"]
_c = app.app.test_client()
_r = _c.post("/admin/funded-cfd-plan/waiting-zurueck", json={"account_id": _K["id"]})
_j = _r.get_json() or {}
check(_r.status_code == 200 and _j.get("ok") and _j.get("merker") is True and _j["konto"]["waiting_payout_since"] is None and _j["konto"]["war_seit"] == _K["waiting_payout_since"]
      and len(_UPD) == 1 and _UPD[0][1] == {"id": f"eq.{_K['id']}", "account_type": "eq.funded_cfd", "waiting_payout_since": "not.is.null"}
      and _UPD[0][2]["waiting_payout_since"] is None and _UPD[0][2]["fcp_wartet_zurueck"]["balance"] is None and _UPD[0][2]["fcp_wartet_zurueck"]["at"],
      f"Admin setzt Waiting zurück (Guard funded_cfd + Waiting gesetzt) + Merker {{at, von, balance None}} → {{ok, merker, konto}} ({_r.status_code})")
_UPD.clear()
class _Resp:
    status_code, text = 400, 'column accounts.fcp_wartet_zurueck does not exist'
def _upd_ohne_spalte(t, f, u):
    if "fcp_wartet_zurueck" in u:
        raise app.requests.exceptions.HTTPError("400", response=_Resp())
    _UPD.append((t, f, u))
    return [dict(_K, **u)]
app.sb_update = _upd_ohne_spalte
_r = _c.post("/admin/funded-cfd-plan/waiting-zurueck", json={"account_id": _K["id"]})
_j = _r.get_json() or {}
check(_r.status_code == 200 and _j.get("merker") is False and "fcp_wartet_zurueck" in _j.get("hinweis", "") and _UPD and _UPD[0][2] == {"waiting_payout_since": None},
      "Spalte fcp_wartet_zurueck fehlt → zurückgesetzt ohne Merker, Hinweis auf die SQL-Datei")
app.sb_update = lambda t, f, u: _UPD.append((t, f, u)) or [dict(_K, **u)]
_UPD.clear()
_LOGIN["v"] = (True, "admin-uid", None, frozenset({H1, H2}), None)      # HT-Admin: Schreib-Sicht nur HT
_r = _c.post("/admin/funded-cfd-plan/waiting-zurueck", json={"account_id": _K["id"]})
check(_r.status_code == 403 and not _UPD, "HT-Admin darf kein Konto aus Emins Gruppe zurücksetzen (Zwei Unternehmen getrennt)")
_LOGIN["v"] = (False, H1, None, H1, None)
_r = _c.post("/admin/funded-cfd-plan/waiting-zurueck", json={"account_id": _K["id"]})
check(_r.status_code == 403 and not _UPD, "ohne Admin: 403")
_LOGIN["v"] = (True, "admin-uid", None, None, None)
for _feld, _wert, _code, _txt in (("account_type", "funded", 400, "nur funded_cfd"), ("waiting_payout_since", None, 409, "ohne Waiting: 409")):
    _alt = _K[_feld]
    _K[_feld] = _wert
    _r = _c.post("/admin/funded-cfd-plan/waiting-zurueck", json={"account_id": _K["id"]})
    check(_r.status_code == _code and not _UPD, f"{_txt} ({_r.status_code})")
    _K[_feld] = _alt
_r = _c.post("/admin/funded-cfd-plan/waiting-zurueck", json={"account_id": "x"})
check(_r.status_code == 400 and not _UPD, "ungültige account_id: 400")
app.sb_update = lambda t, f, u: []
_r = _c.post("/admin/funded-cfd-plan/waiting-zurueck", json={"account_id": _K["id"]})
check(_r.status_code == 409, "Guard griff (inzwischen geändert): 409")
app.sb_select, app.sb_update, app._planer_schreib_gate, app._fcp_login = _s0, _u0, _g0, _l0

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
