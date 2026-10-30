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
rm = app.fcp_konto_rechnen(j5, 101290, 100000, False, False, 1.0, 0.85, random.Random(2))
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

print("2d) The5ers-Consistency (Finn 30.10.2026 ~07:40): TP = min(Rest, max(Rest/2, Gewinne))")
RC = app.ap_regel_finden(FIRMEN, "The5%ers")
check(app.fcp_tp_modus(RC) == "consistency50" and app.fcp_tp_modus(app.ap_regel_finden(FIRMEN, "FundedNext")) is None, "Standard: nur The5ers consistency50")
GM = app.fcp_gewinne([{"status": "completed", "master_pl": 635.70}, {"status": "completed", "master_pl": 603.84}, {"status": "completed", "master_pl": 61.05},
                      {"status": "completed", "master_pl": -1315.00}, {"status": "planned", "master_pl": None}])
check(GM == 1300.59, f"Gewinne Moritz …2352 = 635,70 + 603,84 + 61,05 = {GM} (Verlust und geplanter zählen nicht)")
check(app.fcp_gewinne([{"status": "completed", "master_pl": 500}, {"status": "completed", "master_pl": None}]) is None, "beendeter Trade ohne P&L → nicht lesbar")


class Fest:            # Ziel genau auf einen Wert würfeln (Beispiele aus Finns Diktat)
    def __init__(self, ziel):
        self.z = ziel
    def uniform(self, lo, hi):
        return self.z if lo <= self.z <= hi else (lo + hi) / 2


tm = app.fcp_konto_rechnen(j5, 98685, 100000, 2, False, 1.0, 0.85, Fest(1310), RC, gewinne=GM)
check(tm["tp"] == 1312 and tm["tp_art"] == "consistency", f"Moritz …2352: Rest 2.625, Gewinne 1.300,59 → TP {tm['tp']} (Soll 1.312)")
tf = app.fcp_konto_rechnen(j5, 95354, 100000, 1, False, 1.0, 0.85, Fest(1500), RC, gewinne=0.0)
check(tf["tp"] == 3073, f"Finn + Pascal …5250: keine Gewinne, Rest 6.146 → TP {tf['tp']} (Soll 3.073)")
tf2 = app.fcp_konto_rechnen(j5, 95354 + 3073, 100000, 1, False, 1.0, 0.85, Fest(1500), RC, gewinne=3073.0)
check(tf2["tp"] == 3073, f"…5250 danach: Rest 3.073, Gewinne 3.073 → TP {tf2['tp']} (Soll 3.073)")
tx = app.fcp_konto_rechnen(j5, 95354, 100000, 1, False, 1.0, 0.85, Fest(1500), RC, gewinne=None)
check(tx["tp"] == 3073 and tx["tp_art"] == "consistency_ohne_gewinne", "Gewinne nicht lesbar → Rest/2 (fail-closed)")
tg = app.fcp_konto_rechnen(j5, 100500, 100000, 3, False, 1.0, 0.85, Fest(1400), RC, gewinne=5000.0)
check(tg["tp"] == 900, f"große Gewinne: TP nie über den Rest ({tg['tp']} = 900)")
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
fest = app.fcp_fest_richtung([{"user_id": "u1", "master_firm": "FundedNext", "status": "planned", "richtung": "sell"},
                              {"user_id": "u1", "master_firm": "FundedNext", "status": "open", "richtung": "buy"},
                              {"user_id": "u2", "master_firm": "The5%ers", "status": "completed", "richtung": "buy"}])
check(fest == {"u1|" + app._ap_norm(app._firm_norm("FundedNext")): "buy"}, f"laufender Trade schlägt geplanten, beendete zählen nicht ({fest})")
check(all(app.fcp_richtung("sell", random.Random(s)) == "sell" for s in range(20)), "feste Richtung wird übernommen")
check({app.fcp_richtung(None, random.Random(s)) for s in range(40)} == {"buy", "sell"}, "ohne Trade gewürfelt")
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
        return [{"id": v, "name": "Fusion " + v, "firm": "Fusion Markets"} for v in FUS.values()]
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
check(gp["100k 1 → Funded"]["richtung"] == "sell" and gp["100k 2 → Funded"]["richtung"] == "sell", "H1 FundedNext: beide wie der laufende Short")
check(gp["100k 1 → Funded"]["tp_art"] == "erster_payout_refund" and 2050 <= gp["100k 1 → Funded"]["tp"] <= 2150 and gp["100k 1 → Funded"]["hedge_eur"] == 5000,
      "Konto mit −2k ohne Payout: Refund-Ziel ganz nachholen (2.050–2.150), Hedge 5.000 €")
check(gp["100k 7 → Funded"]["eins_prozent"] and gp["100k 7 → Funded"]["sl"] <= 780, "Emin-Konto mit 1-%-Regel: kleiner SL")
z3 = gp["200k 3 → Funded"]
check(z3["tp_art"] == "consistency" and 650 <= z3["tp"] <= 750, f"The5ers 200k frisch, ohne Gewinne: TP {z3['tp']} = Rest/2 (Consistency)")
check([z["konto"] for z in erg["ziel"]] == ["100k 4 → Funded"], "The5ers +1.600 → Ziel (Waiting for Payout)")
aus = {z["konto"]: z["grund"] for z in erg["ausgelassen"]}
check("Flex" in aus.get("100k Flex 6 → Funded", ""), "Flex nicht geplant")
check("Waiting for Payout" in aus.get("100k 8 → Funded", ""), "Waiting for Payout nie planen")
mins = {}
for z in erg["geplant"]:
    mins.setdefault(z["user_id"], []).append(datetime.fromisoformat(z["start_um"]))
check(all(abs((a - b).total_seconds()) >= 600 for v in mins.values() for i, a in enumerate(v) for b in v[i + 1:]), "≥ 10 min zwischen Starts derselben ID")
check(not GESCHRIEBEN, "Trockenlauf schreibt nichts")
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
zeilen = [z for t, z in GESCHRIEBEN if t == "trade_plans"]
check(len(zeilen) == 5 and all(z["start_um"] is None and z["auto_bestaetigt_at"] is None and z["route"] == "mt5" and z["auto_plan"] is False
                               and z["slave_account_id"] and z["mt5_baseline"]["funded_plan"]["art"] == "cfd" for z in zeilen),
      "scharf: 5 Vorschläge ohne start_um, Echo mit Slave, Kennung funded_plan.art cfd")
check(not [g for g in GESCHRIEBEN if g[0] == "update"], "Ziel erreicht stellt ohne ziel_auto_wartet nichts um")
check(all(z["mt5_baseline"]["funded_plan"]["start_um"] for z in zeilen), "Vorschlagszeit in mt5_baseline.funded_plan.start_um")
s = app.fcp_sicht(erg, frozenset({E1}))
check({z["user_id"] for z in s["geplant"] + s["ausgelassen"]} == {E1}, "Sicht Emin: nur Emins Zeilen")
z0 = zeilen[0]
check(abs(z0["multiplier"] * z0["master_contracts"] - [g for g in erg2["geplant"] if g["konto_id"] == z0["master_account_id"]][0]["hedge_lots"]) < 0.02,
      "multiplier × Lots = Hedge-Lots")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
