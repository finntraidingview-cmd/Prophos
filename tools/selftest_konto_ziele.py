#!/usr/bin/env python3
"""Selbsttest KONTO-ZIELE (K1, Finn 05.11.2026 ~07:00 Dubai: „Die Propfirm-Dashboards 1:1 in Prophos holen — Payout-Eligibility, Max Drawdown, Daily Loss …").
Rechnet app.py kz_rechnen (GET /konto-ziele) mit echten Daten vom 05.11.2026 (read-only gelesen) für drei Kontoarten — Tradeify 150k Challenge …5168,
Blue Guardian 100k Funded CFD …8631, Apex 150k Winning Days …0002 — ohne Netz und ohne DB, und prüft, dass jede Zahl dieselbe ist wie in der Planer-Funktion
(ap_konten_stand_zeile, ap_boden_sicher, fcp_konto_ziel_boden, fcp_gewinntage_ist, wd_auto_stand, wd_zyklus_stand, liq_aus_regel). Dazu das Gate kz_darf.
Aufruf:  python3 tools/selftest_konto_ziele.py   (--json schreibt die drei Antworten für den Stub-Test nach stdout)"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    if "--json" not in sys.argv:
        print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "json": json}


def lade(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^[A-Za-z_@#])", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^[A-Za-z_@#])", app, re.S | re.M)
    if not m:
        raise RuntimeError("nicht gefunden: " + name)
    for _ in range(20):
        try:
            exec(m.group(0), ns)
            return
        except NameError as e:          # Konstante, die selbst eine andere Konstante nutzt
            lade(str(e).split("'")[1])


def ruf(fn, *a, **k):
    if fn not in ns:
        lade(fn)
    for _ in range(120):
        try:
            return ns[fn](*a, **k)
        except NameError as e:
            lade(str(e).split("'")[1])
    raise RuntimeError(fn)


for n in ("AP_TYPEN", "AP_KONTO_FELDER", "KZ_CHART_MAX", "KZ_BODEN_ART", "WD_FIRMEN_REGELN_STD", "WD_GOOD_DAY_MIN", "WD_ZYKLUS_VORGABE", "WD_ZYKLUS_FU",
          "WD_ZYKLUS_STAFFEL_STD", "WD_ZYKLUS_STAFFEL_VON", "FCP_ERSTER_PAYOUT_STANDARD", "FCP_TP_MODUS_STANDARD"):
    lade(n)
ns["WD_ZYKLUS_KT"], ns["WD_ZYKLUS_INSTR"] = 1, "nq"
# Helfer, die in eigenem try laufen (ein NameError dort käme nie beim Lader an)
for n in ("ap_boden_konto", "_ap_boden", "ap_kw_param", "ap_groesse", "ap_regel_konto", "ap_regel_flex", "ap_boden_sicher", "ap_regel_finden", "_ap_norm"):
    lade(n)
ns["_ap_tz"] = lambda name: __import__("zoneinfo").ZoneInfo(name)

# ── echte Daten 05.11.2026 (SELECT, gekürzt auf die genutzten Felder) ──
AP_FIRMEN = [
    {"boden": "nachziehend", "namen": ["tradeify"], "route": "tvv2", "dd_usd": 4500, "phasen": {"challenge": {"sl": None, "tp": [3450, 3550], "menge": [2, 2.8], "dd_usd": 4500,
     "tp_max": 3600, "ziel_pct": 6, "menge_schritt": 1}}, "symbol": "NQ", "groessen": [150000], "kauf_eur": 215, "ziel_pct": {"challenge": 6}},
    {"soft": True, "boden": "statisch", "namen": ["apextrader", "apex"], "route": "tvv2", "dd_usd": 4000, "phasen": {"challenge": {"ziel_pct": 6}}, "groessen": [100000, 150000], "kauf_eur": {"100000": 45, "150000": 150},
     "ziel_pct": {"challenge": 6}, "daily_usd": 2000, "je_groesse": {"100000": {"dd_usd": 3000, "daily_usd": 1500, "phasen": {"challenge": {"ziel_pct": 6}}},
                                                                 "150000": {"dd_usd": 4000, "phasen": {"challenge": {"ziel_pct": 6}}}}},
    {"boden": "statisch", "namen": ["blueguardian"], "route": "mt5v2", "dd_pct": 8, "phasen": {"phase1": {"ziel_pct": 8, "boden_pct": 8}, "phase2": {"ziel_pct": 4, "boden_pct": 8}},
     "groessen": [100000], "kauf_eur": {"100000": 300, "200000": 600}, "ziel_pct": {"phase1": 8, "phase2": 4}, "wert_groessen": [100000, 200000]}]
FCP = {"firmen": [{"an": True, "name": "Blue Guardian", "namen": ["blueguardian", "bluegardian"], "erster_payout": False,
                   "je_groesse": {"100000": {"dd": 8000, "sl": [1250, 1600], "lots": [1, 1.75], "ziel": [1000, 2000], "hedge_eur": 1000,
                                             "gewinntage": {"tp": [550, 650], "min": 500, "anzahl": 3}}}}]}
LIQ = [{"firma": None, "kontotyp": "winning_days", "wie_kontotyp": "funded"},
       {"firma": "Tradeify", "kontotyp": "challenge", "art": "fest", "betrag_usd": 4500, "maxdd_art": "eod_trailing"},
       {"firma": "Tradeify", "kontotyp": "funded", "art": "fest", "betrag_usd": 4500, "maxdd_art": "eod_trailing", "maxdd_lock_ueber_groesse_usd": 100},
       {"firma": "Apex Trader", "kontotyp": "challenge", "art": "tagesstart", "betrag_usd": 2000, "maxdd_art": "eod_trailing", "maxdd_lock_ueber_groesse_usd": 100},
       {"firma": "Apex Trader", "kontotyp": "funded", "groesse": 150000, "art": "stufen", "maxdd_art": "eod_trailing", "maxdd_lock_ueber_groesse_usd": 100,
        "stufen": [{"ab_balance": 150000, "daily_loss_usd": 2500}, {"ab_balance": 152000, "daily_loss_usd": 2500}, {"ab_balance": 153000, "daily_loss_usd": 2500},
                   {"ab_balance": 155000, "daily_loss_usd": 3000}, {"ab_balance": 160000, "daily_loss_usd": 4000}]}]
BG = {"id": "0b91ae78-ef23-422b-ad17-3538a938ddab", "user_id": "u-mike", "name": "100k 608631 → Funded", "firm": "Blue Guardian", "account_type": "funded_cfd",
      "external_id": "608631", "max_drawdown": 8000, "tv_balance": 95989.54, "created_at": "2026-10-28T06:42:38.854872+00:00"}
TF = {"id": "17c14b24-81a4-4ac4-9ec5-002302f2c56b", "user_id": "u-x", "name": "150k TDFYSL150180985168 → Challenge", "firm": "Tradeify", "account_type": "challenge",
      "external_id": "TDFYSL150180985168", "max_drawdown": 4500, "starting_balance": 150000.0, "tv_balance": 159005.44, "ziel_usd": 159000.0,
      "ziel_erreicht_at": "2026-11-04T13:58:16.961115+00:00", "created_at": "2026-11-02T13:06:12.482776+00:00", "goal_manual": False}
AX = {"id": "2aa6f1a9-ac0f-43a5-80d9-08e1f15c3a4d", "user_id": "u-y", "name": "150k PAAPEX6843320000002 → Winning Days", "firm": "Apex Trader", "account_type": "winning_days",
      "external_id": "PAAPEX6843320000002", "max_drawdown": 4000, "tv_balance": 161697.9, "goal_kind": "winning_days", "goal_target": 5, "goal_manual": True,
      "goal_done_offset": 4, "created_at": "2026-10-20T17:09:45.448569+00:00", "wd_farm": True, "wd_zyklus_regel": None, "goal_wd_korrektur": 0,
      "goal_wd_seit": "2026-10-20T17:09:45.448569+00:00", "goal_wd_hand_tage": ["2026-11-03"]}


def pl(aid, typ, route, st, en, mpl, bs=None, be=None, mb=None, tps=None, tpe=None, ds=None, de=None):
    return {"master_account_id": aid, "status": "completed", "route": route, "konto_typ": typ, "started_at": st, "ended_at": en, "completed_at": en,
            "master_pl": mpl, "tv": {"balance_start": bs, "today_pnl_start": tps, "datum_start": ds}, "fin": {"balance_end": be, "master_balance": mb, "today_pnl": tpe, "datum": de}}


PL = [pl(BG["id"], "funded_cfd", "mt5", "2026-10-28T07:05:11+00:00", "2026-10-28T13:37:27+00:00", -800.20, mb=99199.61),
      pl(BG["id"], "funded_cfd", "mt5", "2026-10-29T13:09:02+00:00", "2026-10-29T13:30:22+00:00", -1474.76, mb=97724.85),
      pl(BG["id"], "funded_cfd", "mt5", "2026-11-04T02:52:35+00:00", "2026-11-04T03:02:36+00:00", -1735.31, mb=95989.54),
      pl(TF["id"], "challenge", "tvv2", "2026-11-02T14:49:39+00:00", "2026-11-02T15:21:23+00:00", 3358.52, 150000, 153358.52),
      pl(TF["id"], "challenge", "tvv2", "2026-11-03T08:03:47+00:00", "2026-11-03T09:06:05+00:00", 3492.78, 153358.52, 156851.3),
      pl(TF["id"], "challenge", "tvv2", "2026-11-04T10:22:43+00:00", "2026-11-04T10:30:20+00:00", 2148.52, 156851.3, 158999.82),
      pl(TF["id"], "challenge", "tvv2", "2026-11-04T13:52:52+00:00", "2026-11-04T13:58:05+00:00", 5.62, 158999.82, 159005.44),
      pl(AX["id"], "funded", "tvv2", "2026-10-28T07:42:41+00:00", "2026-10-28T17:58:01+00:00", 3000.00, 150000, None, None, 0, None, "2026-10-28"),
      pl(AX["id"], "funded", "tvv2", "2026-10-28T18:50:12+00:00", "2026-10-28T18:52:28+00:00", 4328.49, 153163.8, 157474.5, None, 3163.8, 7474.5, "2026-10-28", "2026-10-28"),
      pl(AX["id"], "funded", "tvv2", "2026-10-28T23:09:00+00:00", "2026-10-29T02:01:10+00:00", 7483.80, 157474.5, 164978.3, None, 0, 7503.8, "2026-10-29", "2026-10-29"),
      pl(AX["id"], "winning_days", "tvv2", "2026-10-30T03:59:23+00:00", "2026-10-30T04:47:59+00:00", 380.88, 164978.3, 165359.18, None, 0, 380.88, "2026-10-30", "2026-10-30"),
      pl(AX["id"], "winning_days", "tvv2", "2026-11-03T05:11:26+00:00", "2026-11-03T06:12:56+00:00", 379.84, 165359.18, 165739.02, None, 0, 379.84, "2026-11-03", "2026-11-03"),
      pl(AX["id"], "winning_days", "tvv2", "2026-11-04T12:58:32+00:00", "2026-11-04T15:15:34+00:00", -4041.12, 165739.02, 161697.9, None, 0, -4041.12, "2026-11-04", "2026-11-04")]
TX = {"id": "14e31eae-22e4-4684-8272-438a821a53cf", "user_id": "u-z", "name": "150k FTDFYSLX150393423058 → Winning Days", "firm": "Tradeify",
      "account_type": "winning_days", "external_id": "FTDFYSLX150393423058", "max_drawdown": 4500, "tv_balance": 159967.22, "goal_kind": "winning_days",
      "goal_target": 5, "goal_manual": True, "goal_done_offset": 1, "created_at": "2026-10-20T12:40:42+00:00", "wd_farm": True, "goal_wd_korrektur": 0,
      "goal_wd_seit": "2026-10-30T00:00:00+00:00", "goal_wd_hand_tage": ["2026-11-04"], "payout_ready_at": "2026-11-11"}
for _st, _en, _pl, _bs, _be in (("2026-10-20T13:51:15+00:00", "2026-10-20T14:17:37+00:00", 15792.72, 150000, 165792.72),
                               ("2026-10-29T06:04:28+00:00", "2026-10-29T20:09:49+00:00", -691.80, 161698.92, 161007.12),
                               ("2026-10-30T11:01:36+00:00", "2026-10-30T19:47:24+00:00", -1543.80, 161007.12, 159463.32),
                               ("2026-11-02T07:02:42+00:00", "2026-11-02T07:34:33+00:00", 264.30, 159463.32, 159727.62),
                               ("2026-11-03T08:25:36+00:00", "2026-11-03T12:48:43+00:00", -30.76, 159727.62, 159696.86),
                               ("2026-11-04T02:12:57+00:00", "2026-11-04T02:20:46+00:00", 270.36, 159696.86, 159967.22)):
    PL.append(pl(TX["id"], "funded" if _pl > 10000 else "winning_days", "tvv2", _st, _en, _pl, _bs, _be, None, 0, None, _st[:10], _en[:10]))
TX_PAY = ([], [], [{"id": "364da3aa", "account_id": TX["id"], "amount": 3633, "currency": "EUR", "occurred_at": "2026-10-30"}])   # echte Payout-Buchung
ZR = {"bis": "2x_bester", "aktiv": True, "firmen": ["apex", "apex100"], "stuetz": [{"v": 2000, "satz": 400, "ziel": 750}, {"v": 4000, "satz": 300, "ziel": 1500}], "ab_zyklus": 2}
VP = {"regeln": {"fu": {"apex": [370, 390], "apex100": [320, 330]}}}
JETZT = "2026-11-05T03:30:00+00:00"


for _n in ("fcp_eins_prozent", "fcp_gewinne", "fcp_tage_zyklus_w", "fcp_param"):
    lade(_n)
ruf("fcp_konto_rechnen", FCP["firmen"][0]["je_groesse"]["100000"], 95989.54, 100000.0, 1, False, 1.0, 1.0, None, FCP["firmen"][0],
    param=ruf("fcp_param", FCP), tage={"b": 0, "w": 0, "n": 0, "serie": 0, "serie_n": 0}, gewinne=None, gewinntage=(0, 3), ziel_fest={"usd": 1000, "zyklus": 1})


def ctx_fuer(a):
    plaene = [p for p in PL if p["master_account_id"] == a["id"]]
    verlauf = [dict(p, id=str(i), bal_end=p["fin"]["balance_end"], bal_start=p["tv"]["balance_start"]) for i, p in enumerate(plaene) if p["route"] in ("tvv2", "tsv2")]
    c = {"bal": a["tv_balance"], "bal_quelle": "TV", "bal_stand": a.get("tv_balance_at"), "plaene": plaene, "jetzt": JETZT, "ap_firmen": AP_FIRMEN, "liq_regeln": LIQ,
         "fcp_regel": FCP, "fcp_pay": ([], [], []), "wd_firmen_regeln": {}, "wd_pay": [], "payouts": ([], [], []) if a["account_type"] in ("funded_cfd", "funded", "winning_days") else None}   # wie die Route
    if a["id"] == TX["id"]:
        c["payouts"] = TX_PAY
        c["wd_pay"] = [{"requested_at": "2026-10-30", "status": "received"}]
    c["peak"] = ruf("liq_peak", {}, a, None, verlauf)
    ts = ruf("kz_tagesstart", ruf("kz_phase_plaene", plaene, a["account_type"]), a["tv_balance"], JETZT)[0]
    c["peak_eod"] = ruf("liq_peak", {"started_at": JETZT, "master_account_id": a["id"]}, a, a["tv_balance"], verlauf, eod_tagesstart=ts, eod=True)
    if a["account_type"] == "winning_days":
        k = dict(a, live_balance=a["tv_balance"])
        c["wd_zyklus"] = ruf("wd_zyklus_konto", k, ZR, VP, plaene, [])
    return c


def kachel(o, key):
    return next((k for k in o["kacheln"] if k["key"] == key), None)


ergebnisse = {}
# ── 1. Tradeify 150k Challenge …5168: Werte = ap_konten_stand_zeile + ap_boden_sicher ──
c = ctx_fuer(TF)
o = ergebnisse["challenge"] = ruf("kz_rechnen", TF, c)
tage_pl = {"2026-11-02": 3358.52, "2026-11-03": 3492.78, "2026-11-04": 2148.52 + 5.62}
z = ruf("ap_konten_stand_zeile", TF, AP_FIRMEN[0], 159005.44, tage_pl)
check(o["stand"] == z and z["ziel"] == 159000.0 and z["ziel_usd"] == 9000.0, f"Challenge: Ziel/Consistency = ap_konten_stand_zeile (Ziel {z['ziel']}, {z['ziel_usd']} $)")
check(z["cons_pct"] == 40.0 and z["groesster_tag"] == 3492.78 and abs(z["cons_anteil"] - 0.3881) < 1e-4, f"Challenge: Consistency 40 % (tp_max 3.600 ÷ 9.000), größter Tag 3.492,78 ÷ 9.000 = {z['cons_anteil']}")
kc = kachel(o, "consistency")
check(kc["wert"] == "38,8 %" and kc["pill"] == ["In range", "gut"], f"Challenge: Kachel Consistency 38,8 % In range ({kc['wert']})")
bk = ruf("ap_boden_sicher", AP_FIRMEN, TF, 159005.44, {TF["id"]: c["peak"]})
km = kachel(o, "max_loss")
check(o["chart"]["boden"] == bk["boden"] and bk["boden"] == 159005.44 - 4500 and km["wert"] == "4.500 $",
      f"Challenge: Boden = ap_boden_sicher ({bk['boden']}, {bk['boden_art']}) · Max Loss 4.500 $ übrig")
check(kachel(o, "daily_loss")["leer"] and "kein Daily Loss" in kachel(o, "daily_loss")["info"], "Challenge: Tradeify ohne Daily Loss in Kernwerten/liq_regeln → „—“ (kein accounts.max_daily_drawdown)")
check(o["urteil"]["ok"] is True and o["urteil"]["text"] == "Bestanden", f"Challenge: Phase bestanden ({o['urteil']['grund']})")
check([p["bal"] for p in o["chart"]["punkte"]] == [153358.52, 156851.3, 158999.82, 159005.44] and o["chart"]["ziel"] == 159000.0, "Challenge: Chart = Endbalances der vier Trades, Ziel-Linie 159.000")

# ── 2. Blue Guardian 100k Funded CFD …8631: Werte = fcp_konto_ziel_boden + fcp_gewinntage_ist ──
c = ctx_fuer(BG)
o = ergebnisse["funded_cfd"] = ruf("kz_rechnen", BG, c)
zb = ruf("fcp_konto_ziel_boden", FCP["firmen"][0], 100000.0, 1, BG["name"])
check(zb == (101000.0, 92000.0) and o["chart"]["ziel"] == 101000.0 and o["chart"]["boden"] == 92000.0, f"Funded CFD: Ziel/Boden = fcp_konto_ziel_boden {zb} (wie Radar)")
check(kachel(o, "max_loss")["wert"] == "3.990 $" and kachel(o, "max_loss")["farbe"] == "warn", f"Funded CFD: Max Loss 3.989,54 → „3.990 $“ übrig, warn ({kachel(o, 'max_loss')['wert']})")
gti = ruf("fcp_gewinntage_ist", FCP["firmen"][0]["je_groesse"]["100000"]["gewinntage"], BG["id"], c["plaene"], "2026-10-28")
kt = kachel(o, "tage")
check(gti == (0, 3) and kt["wert"] == "0" and kt["klein"] == "/ 3", f"Funded CFD: Gewinntage = fcp_gewinntage_ist {gti}")
check(kachel(o, "daily_loss")["leer"], "Funded CFD: Blue Guardian ohne Daily Loss in Kernwerten/liq_regeln → „—“")
check(kachel(o, "consistency")["leer"], "Funded CFD: Blue Guardian ohne Consistency (fcp_consistency_pct None)")
check(o["urteil"]["ok"] is False and "Ziel bis Waiting" in o["urteil"]["grund"] and "Gewinntage" in o["urteil"]["grund"],
      f"Funded CFD: kein Payout — {o['urteil']['grund']}")
check(o["zyklus"]["nr"] == 1 and o["balance"]["wert"] == 95989.54, "Funded CFD: Zyklus 1, Balance 95.989,54 (tv_balance statt „—“)")
check([p["bal"] for p in o["chart"]["punkte"]] == [99199.61, 97724.85, 95989.54], "Funded CFD: Chart aus final.master_balance (Echo)")
kt = kachel(o, "trades")
check(len(o["kacheln"]) == 6 and kt["wert"] == "3" and "04.11." in kt["unter"] and "−1.735 $" in kt["unter"], f"Funded CFD: sechs Kacheln, Trades im Zyklus 3 · {kt['unter']}")

# AB1 (Abhak-Karte): dieselben Zahlen + nächster Trade aus fcp_konto_rechnen (Mitte, Ziel aus Zeile 1)
ab = o["abhak"]
nx_soll = ruf("fcp_konto_rechnen", FCP["firmen"][0]["je_groesse"]["100000"], 95989.54, 100000.0, 1, False, 1.0, 1.0, None, FCP["firmen"][0],
              param=ruf("fcp_param", FCP), tage=ruf("fcp_tage_zyklus_w", c["plaene"], "2026-10-28"), gewinne=ruf("fcp_gewinne", c["plaene"], "2026-10-28"),
              gewinntage=(0, 3), ziel_fest={"usd": 1000.0, "zyklus": 1})
check(ab["ziel_bal"] == 101000.0 and abs(ab["rest"] - 5010.46) < .01 and ab["erreicht"] is False and ab["cons"] is None and ab["gewinntage"] == [0, 3]
      and ab["bereit"] is False and ab["wartet"] is False, f"AB1 Blue Guardian: Ziel 101.000, Rest 5.010,46, keine Consistency, Gewinntage 0/3, nicht bereit ({ab})")
check(ab["naechster"] and ab["naechster"]["aktion"] == nx_soll["aktion"] == "planen" and ab["naechster"]["tp"] == nx_soll["tp"] == 600.0,
      f"AB1 Blue Guardian: nächster Trade = fcp_konto_rechnen (Gewinntag-Phase A, TP Mitte 550–650 = {ab['naechster']})")

# ── 3. Apex 150k Winning Days …0002: Werte = wd_auto_stand + wd_zyklus_stand + liq (Stufen) ──
c = ctx_fuer(AX)
o = ergebnisse["winning_days"] = ruf("kz_rechnen", AX, c)
st = ruf("wd_auto_stand", AX, c["plaene"])
kt = kachel(o, "tage")
check(st == 4 and kt["wert"] == "4" and kt["klein"] == "/ 5", f"WD: Winning Days = wd_auto_stand {st}/5")
kc = kachel(o, "consistency")
zs = ruf("wd_zyklus_stand", c["plaene"], [{"requested_at": "2026-10-19", "status": "received"}])   # Zyklus 1: alle Tage ab goal_wd_seit
check(o["zyklus"]["bester"] == zs["bester"] == 7503.8 and o["zyklus"]["profit"] == zs["profit"] and o["zyklus"]["nr"] == 1,
      f"WD: Zyklus-Tage = wd_zyklus_stand (Endlesung 7.503,80 statt master_pl, Gewinn {zs['profit']}), Zyklus 1")
check(kc["pill"] == ["Out of range", "rot"] and kc["wert"] == "65,1 %", f"WD: Apex Consistency 50 % — 7.503,80 ÷ {zs['profit']} = {kc['wert']} Out of range")
kd = kachel(o, "daily_loss")
lv, _t = ruf("liq_aus_regel", LIQ[4], 150000.0, None, 161697.9)
check(not kd["leer"] and kd["wert"] == "4.000 $" and abs(lv - 157697.9) < .01, f"WD: Daily Loss Stufe ab 160.000 = 4.000 $ (liq_aus_regel {lv})")
km = kachel(o, "max_loss")
check(not km["leer"] and o["chart"]["boden"] == 150100.0, f"WD: Max Loss Boden 150.100 (EOD, Lock Größe + 100) — {km['wert']} übrig")
kr = kachel(o, "recoverer")
check(kr is not None and kr["pill"] == ["Aus", "grau"] and "Zyklus 1" in (kr["unter"] or "") and kr["wert"] == "−4.041 $", f"WD: Recoverer aus, Verlusttag {kr and kr['wert']} — {kr and kr['unter']}")
check(next(c for c in o["urteil"]["checks"] if c[1] == "Mindest-Net-Profit")[0] == "info", "WD: Mindest-Net-Profit aus (Apex) → kein ✓, nur Hinweis")
check(o["urteil"]["ok"] is False and "Winning Days" in o["urteil"]["grund"] and "Consistency" in o["urteil"]["grund"], f"WD: kein Payout — {o['urteil']['grund']}")

# ── K2 (Finn 05.11.2026): Payout-Verlauf, „Payout ab" nur CFD ──
c = ctx_fuer(TX)
o = ergebnisse["winning_days_tradeify"] = ruf("kz_rechnen", TX, c)
check(o["payouts"] == [{"datum": "2026-10-30", "betrag": 3633.0, "waehrung": "EUR", "status": "erhalten", "anfrage": "2026-10-30", "fcp": "2026-10-30"}], f"Tradeify WD …3058: Payout-Verlauf = Buchung 30.10. 3.633 € erhalten, ZV1b-/ZV1c-Grenze 30.10. ({o['payouts']})")
check(not any(c_[1] == "Payout ab" for c_ in o["urteil"]["checks"]), "Futures/WD: keine Zeile „Payout ab“ (gibt es nur bei CFD), obwohl payout_ready_at gesetzt ist")
check(o["zyklus"]["nr"] == 2, f"Tradeify WD: Zyklus 2 nach dem Payout ({o['urteil']['sub']})")
bg_r = ruf("kz_rechnen", dict(BG, payout_ready_at="2026-11-20"), ctx_fuer(BG))
check(any(c_[1] == "Payout ab" for c_ in bg_r["urteil"]["checks"]) and bg_r["payouts"] == [], "Funded CFD: „Payout ab“ bleibt, Payout-Verlauf leer (kein Payout)")
pv = ruf("kz_payouts", [{"id": "p1", "amount": 2500, "currency": "USD", "requested_at": "2026-11-01", "status": "pending"},
                        {"id": "p2", "amount": 3000, "currency": "USD", "requested_at": "2026-10-10", "received_at": "2026-10-14", "status": "received", "received_tx_id": "t1"}],
         [{"amount": 1000, "payout_date": "2026-09-01"}], [{"id": "t1", "amount": 2700, "currency": "EUR", "occurred_at": "2026-10-14"}, {"id": "t2", "amount": 900, "currency": "EUR", "occurred_at": "2026-10-20"}])
check([(x["datum"], x["status"]) for x in pv] == [("2026-11-01", "angefragt"), ("2026-10-20", "erhalten"), ("2026-10-14", "erhalten"), ("2026-09-01", "verbucht")],
      f"kz_payouts: angefragt/erhalten/verbucht, verknüpfte Buchung nicht doppelt, neueste zuerst ({[(x['datum'], x['status']) for x in pv]})")
check([x.get("anfrage") for x in pv] == ["2026-11-01", "2026-10-20", "2026-10-10", None],
      f"ZV1b kz_payouts: Zyklusgrenze „anfrage“ = requested_at an Anfragen (auch erhalten), freie Buchung ihr Tag, verknüpfte Buchung keine, verbucht keine ({[x.get('anfrage') for x in pv]})")
pv2 = ruf("kz_payouts", [{"id": "p3", "amount": 1, "requested_at": "2026-10-01", "status": "rejected"}], [], [])
check("anfrage" not in pv2[0], "ZV1b kz_payouts: abgelehnte Anfrage ist keine Zyklusgrenze (wie wd_zyklus_stand)")
# ZV1c: Funded CFD — „fcp“ je Eintrag ergibt genau fcp_zyklus_start (Tag nach dem jüngsten) und fcp_payouts_zaehlen (Anzahl)
_p3 = [{"id": "q1", "account_id": "k", "amount": 1, "requested_at": "2026-10-01", "status": "rejected"},
       {"id": "q2", "account_id": "k", "amount": 1, "requested_at": "2026-10-10", "received_at": "2026-10-14", "status": "received", "received_tx_id": "b1"},
       {"id": "q3", "account_id": "k", "amount": 1, "created_at": "2026-11-02T22:30:00+00:00", "status": "pending"}]
_v3 = [{"id": "m1", "account_id": "k", "amount": 1, "payout_date": "2026-09-03"}, {"id": "m2", "account_id": "k", "amount": 1, "created_at": "2026-08-20T10:00:00+00:00"}]
_b3 = [{"id": "b1", "account_id": "k", "amount": 1, "occurred_at": "2026-10-14T09:00:00+00:00"}, {"id": "b2", "account_id": "k", "amount": 1, "occurred_at": "2026-10-20T23:30:00+00:00"}]
_pv3 = ruf("kz_payouts", _p3, _v3, _b3)
_f3 = sorted(x["fcp"] for x in _pv3 if x.get("fcp"))
_start = ruf("fcp_zyklus_start", _p3, _v3, _b3).get("k")
_naechst = (datetime.strptime(_f3[-1], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
check(_f3 == ["2026-08-20", "2026-09-03", "2026-10-01", "2026-10-10", "2026-10-21", "2026-11-02"] and _naechst == _start and len(_f3) == ruf("fcp_payouts_zaehlen", _p3, _v3, _b3).get("k"),
      f"ZV1c kz_payouts „fcp“: alle Anfragen (auch abgelehnt), managed, freie Buchung, verknüpfte nicht, Berliner Tag (20.10. 23:30 UTC = 21.10. Berlin) = fcp_zyklus_start {_start} / Anzahl ({_f3})")
check(ruf("kz_rechnen", TF, ctx_fuer(TF) | {"payouts": None})["payouts"] is None, "Challenge: kein Payout-Verlauf")

# ── Fremd-Review K1: Randfälle ──
o = ruf("kz_rechnen", TF, dict(ctx_fuer(TF), bal=None))
check(o["urteil"]["checks"][0][0] == "ok" and kachel(o, "daily_loss")["leer"], "Challenge ohne Balance, Ziel-Wache-Markierung gesetzt → Ziel ✓ (wie Planer)")
ax_tief = dict(AX, tv_balance=149000.0)
o = ruf("kz_rechnen", ax_tief, dict(ctx_fuer(AX), bal=149000.0))
km = kachel(o, "max_loss")
check(km["pill"] == ["Verletzt", "rot"] and "liegt nicht unter der Balance" in km["info"], f"WD unter dem Boden → Max Loss „Verletzt“ statt „—“ ({km['wert']})")
dk = ruf("kz_dl_kachel", {"betrag": 2000, "level": 148000, "uebrig": None, "weich": True, "text": "x"}, "")
check(dk["leer"] and dk["unter"] == "Balance unbekannt", "Daily Loss ohne Balance → „Balance unbekannt“, nie rot")
ts_x = {"id": "33333333-3333-3333-3333-333333333333", "user_id": "u", "name": "50k EXPRESS-V2-123", "firm": "Topstep", "account_type": "funded", "external_id": "EXPRESS-V2-123", "tv_balance": 1200.0,
        "goal_wd_korrektur": 0, "created_at": "2026-11-01T00:00:00+00:00"}
o = ruf("kz_rechnen", ts_x, {"bal": 1200.0, "plaene": [], "jetzt": JETZT, "ap_firmen": AP_FIRMEN, "liq_regeln": LIQ, "wd_firmen_regeln": {}, "wd_pay": []})
check(o["chart"]["start"] is None and kachel(o, "daily_loss")["leer"] and "Topstep Express" in kachel(o, "daily_loss")["info"]
      and kachel(o, "tage")["klein"] == "/ 5", "Topstep Express: kein Kontogrößen-Start im Chart, Daily Loss „—“ (TopstepX), WD-Ziel Standard 5")

# ── Gate ──
check(ruf("kz_darf", "u1", "u1", False, None), "Gate: eigenes Konto")
check(not ruf("kz_darf", "u1", "u2", False, None), "Gate: fremdes Konto ohne Admin/Gruppe → nein")
check(ruf("kz_darf", "u1", "u2", True, None), "Gate: Admin")
check(ruf("kz_darf", "u1", "u2", False, frozenset({"u1", "u2"})) and not ruf("kz_darf", "u1", "u3", False, frozenset({"u1", "u2"})), "Gate: nur Konten der eigenen Gruppe")
check(not ruf("kz_darf", None, "u1", True, None), "Gate: ohne Login nie")

# ── Live: kein Block ──
check(ruf("kz_rechnen", {"id": "x", "account_type": "live", "name": "Fusion"}, {"bal": 1000})["urteil"] is None, "Live-Konto: keine Kacheln")
src_route = app[app.index('@app.route("/konto-ziele"'):]
src_route = src_route[:src_route.index("\n\n\n")]
check("_wd_login()" in src_route and "kz_darf(" in src_route and '"fremdes Konto"}), 403' in src_route, "Route: Login, Gate kz_darf, 403 bei fremdem Konto")

if "--json" in sys.argv:
    print(json.dumps(ergebnisse, default=str, ensure_ascii=False))
    sys.exit(0)
print(f"\n{len(fehler)} Fehler" if fehler else "\nalle grün")
sys.exit(1 if fehler else 0)
