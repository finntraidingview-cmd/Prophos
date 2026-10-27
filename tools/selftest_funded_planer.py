#!/usr/bin/env python3
"""Selbsttest: FUNDED-PLANER (fp_*, 27.10.2026, Finn: „einen Auto-Planer für Funded … erst mal für alle Fundeds von Apex"). Rechnet Finns
Szenario-Baum (über den Master, 27.10.2026) mit den echten Funktionen aus app.py nach — TP/SL/Liq/Stufe/Hedge je Tag für 150k und 100k —
dazu Zeitverteilung, Zyklus und offene Kosten. Rein rechnend, ohne Netz. Aufruf: python3 tools/selftest_funded_planer.py"""
import os
import random
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


def laden():
    src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]

    def zeile(anfang):
        i = src.index("\n" + anfang) + 1
        return src[i:src.index("\n", i)]
    ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "random": random}
    code = "\n".join([zeile("GP_SLAVE_PPL = "), zeile("FP_NQ_PPL = "), zeile("FP_SLAVE_PPL = "), zeile("FP_SL_MIN_USD = ")]
                     + [block(n) for n in ("_wd_num", "_liq_de", "_cme_handelstag", "ist_topstep_express", "liq_konto_boden", "liq_stufe",
                                           "fp_je_groesse", "fp_liq", "fp_stufe", "fp_tp", "fp_sl", "fp_kontrakte", "fp_hedge", "fp_offen",
                                           "fp_zyklus", "fp_tage", "fp_konto_rechnen", "fp_zeiten")])
    exec(code, ns)
    return ns


# liq_regeln id 4 (150k) und id 13 (100k), Stand 27.10.2026 (Apex Help Center, vom Master gegengeprüft)
ST150 = [{"minis": 4, "ab_balance": 150000, "daily_loss_usd": 2500}, {"minis": 5, "ab_balance": 152000, "daily_loss_usd": 2500},
         {"minis": 7, "ab_balance": 153000, "daily_loss_usd": 2500}, {"minis": 10, "ab_balance": 155000, "daily_loss_usd": 3000},
         {"minis": 10, "ab_balance": 160000, "daily_loss_usd": 4000}]
ST100 = [{"minis": 3, "ab_balance": 100000, "daily_loss_usd": 1750}, {"minis": 4, "ab_balance": 102000, "daily_loss_usd": 1750},
         {"minis": 5, "ab_balance": 103000, "daily_loss_usd": 1750}, {"minis": 6, "ab_balance": 105000, "daily_loss_usd": 2500},
         {"minis": 6, "ab_balance": 110000, "daily_loss_usd": 3500}]
REGEL = {"namen": ["apextrader", "apex"], "an": True, "sl_pkt": 60,
         "je_groesse": {"150000": {"ziel_gewinn": 15000, "max_trade": 7500, "kosten_eur": 550, "dd": 4000},
                        "100000": {"ziel_gewinn": 12000, "max_trade": 6000, "kosten_eur": 412.5, "dd": 3000}}}


def szenario(ns):
    R, jg = ns["fp_konto_rechnen"], ns["fp_je_groesse"]
    j150, j100 = jg(REGEL, 150000), jg(REGEL, 100000)

    def t(r, tp, sl, hsl, htp, extra=""):
        ok = r["aktion"] == "planen" and r["tp"] == tp and r["sl"] == sl and abs(r["hedge_sl_eur"] - hsl) <= 1 and abs(r["hedge_tp_eur"] - htp) <= 1   # Finns Werte auf ganze € (abgeschnitten)
        return ok, f"TP {r.get('tp')} / SL {r.get('sl')}, Hedge +{r.get('hedge_sl_eur')} / −{r.get('hedge_tp_eur')} {extra}"

    print("150k")
    r = R(REGEL, j150, ST150, 150000, None, 550, 150000, {}, 150000)
    ok, txt = t(r, 7500, 2500, 344, 1031)
    check(ok and r["liq"] == 146000 and r["kontrakte"] == 2 and r["stufe"] == 1, "Tag 1: " + txt + f", Liq {r.get('liq')}, {r.get('kontrakte')} NQ")
    # Gewinn → 157.500: Liq lockt bei 150.100, offen 550 + 1.031,25
    offen = ns["fp_offen"](550, [-r["hedge_tp_eur"]])
    check(abs(offen - 1581.25) < 0.01, f"Gewinn Tag 1: offene Kosten {offen} € (550 + 1.031,25)")
    r2 = R(REGEL, j150, ST150, 157500, 157500, offen, 150000, {}, 150000)
    ok, txt = t(r2, 7500, 3000, 641, 1602)
    check(ok and r2["liq"] == 150100 and r2["ziel"] == 165000, "Tag 2 nach Gewinn: " + txt + f", Liq {r2.get('liq')} (Lock), Ziel {r2.get('ziel')}")
    z = R(REGEL, j150, ST150, 165000, 165000, 3183.85, 150000, {}, 150000)
    check(z["aktion"] == "ziel", "165.000 → Ziel erreicht (Waiting for Payout)")
    # Verlust Tag 1 → 147.500, offen 550 − 343,75
    offen_v = ns["fp_offen"](550, [r["hedge_sl_eur"]])
    rv = R(REGEL, j150, ST150, 147500, 150000, offen_v, 150000, {}, 150000)
    ok, txt = t(rv, 2500, 1500, 206, 344)
    check(ok and rv["tp_art"] == "break_even" and rv["liq"] == 146000, "Verlust Tag 1 → 147.500, Tag 2: " + txt + " (Break-even, SL = Rest bis Liq)")
    # 157.500 → Verlust (SL 3.000) → 154.500, offen 940
    offen_3 = ns["fp_offen"](550, [-r["hedge_tp_eur"], r2["hedge_sl_eur"]])
    check(round(offen_3) == 940, f"157.500 → Verlust → 154.500: offen {offen_3} € (≈ 940)")
    r3 = R(REGEL, j150, ST150, 154500, 157500, offen_3, 150000, {}, 150000)
    check(r3["sl"] == 2500 and r3["tp"] == 7500 and r3["liq"] == 150100, f"Tag 3 bei 154.500: TP {r3.get('tp')} / SL {r3.get('sl')} (Stufe ab 153.000)")
    r4 = R(REGEL, j150, ST150, 162000, 162000, offen_3 + r3["hedge_tp_eur"], 150000, {}, 150000)
    check(r4["tp"] == 3000 and r4["sl"] == 4000, f"Gewinn → 162.000, Tag 4: TP {r4.get('tp')} / SL {r4.get('sl')} (Rest bis Ziel, Stufe ab 160.000)")

    print("100k")
    q = R(REGEL, j100, ST100, 100000, None, 412.5, 100000, {}, 100000)
    ok, txt = t(q, 6000, 1750, 241, 825)
    check(ok and q["liq"] == 97000, "Tag 1: " + txt + f", Liq {q.get('liq')}")
    q2 = R(REGEL, j100, ST100, 106000, 106000, ns["fp_offen"](412.5, [-q["hedge_tp_eur"]]), 100000, {}, 100000)
    check(q2["sl"] == 2500 and q2["tp"] == 6000 and q2["liq"] == 100100 and q2["ziel"] == 112000,
          f"Gewinn → 106.000, Tag 2: TP {q2.get('tp')} / SL {q2.get('sl')}, Liq {q2.get('liq')} (Lock) → Ziel 112.000")
    qv = R(REGEL, j100, ST100, 98250, 100000, ns["fp_offen"](412.5, [q["hedge_sl_eur"]]), 100000, {}, 100000)
    check(qv["tp"] == 1750 and qv["sl"] == 1250, f"Verlust → 98.250, Tag 2: TP {qv.get('tp')} / SL {qv.get('sl')}")


def einzeln(ns):
    print("Bausteine")
    R = ns["fp_konto_rechnen"]
    j150 = ns["fp_je_groesse"](REGEL, 150000)
    b = R(REGEL, j150, ST150, 145990, 150000, 550, 150000, {}, 150000)
    check(b["aktion"] == "aus" and "geblowt" in b["grund"], "Balance unter der Liquidation → aus (geblowt?)")
    k = R(REGEL, j150, ST150, 146050, 150000, 550, 150000, {}, 150000)
    check(k["aktion"] == "aus" and "zu klein" in k["grund"], "50 $ über der Liquidation → aus (Abstand zu klein)")
    check(R(REGEL, None, ST150, 150000, None, 550, None, {}, 150000)["aktion"] == "aus", "Größe ohne Werte → aus")
    j100 = ns["fp_je_groesse"](REGEL, 100000)
    u = R(REGEL, j100, ST100, 150074.4, None, 412.5, 100000, {}, 100000)
    check(u["aktion"] == "aus" and "unplausibel" in u["grund"], "100k mit 150.074 $ (Fehllesung Chris) → aus, nicht „Ziel erreicht“")
    h = R(REGEL, j150, ST150, 150000, None, 550, 150000, {}, 150000)
    # Multiplikator wie tpMultiplierAusRisiko: Risiko Master 4.000 $ bei 2 NQ = 100 Punkte, Risiko Slave 550 € → 6,47 Lot
    check(h["master_risk"] == 4000 and h["slave_risk"] == 550 and h["lots"] == 6.47 and abs(h["hedge_eur"] - 1031.15) < 0.02,
          f"Plan-Felder: master_risk {h['master_risk']}, slave_risk {h['slave_risk']}, {h['lots']} Lot, hedge_eur {h['hedge_eur']}")
    check(ns["fp_kontrakte"](2500, 4) == 2 and ns["fp_kontrakte"](3000, 10) == 3 and ns["fp_kontrakte"](1250, 3) == 1 and ns["fp_kontrakte"](9000, 4) == 4,
          "Kontrakte ~60 Punkte SL, höchstens Minis der Stufe")
    z = ns["fp_zyklus"](150000, [], [])
    check(z == {"nr": 1, "ab": None, "start": 150000.0}, "Zyklus 1 ohne Payout ab Kontogröße")
    z2 = ns["fp_zyklus"](150000, ["2026-10-20T10:00:00+00:00"], [{"started_at": "2026-10-19T10:00:00+00:00", "bal_start": 160000},
                                                                  {"started_at": "2026-10-21T10:00:00+00:00", "bal_start": 151200}])
    check(z2["nr"] == 2 and z2["start"] == 151200, "Zyklus 2 ab erstem Trade nach dem Payout")
    tg = ns["fp_tage"]([{"status": "completed", "started_at": "2026-10-20T14:00:00+00:00", "master_pl": 7384},
                        {"status": "completed", "started_at": "2026-10-21T14:00:00+00:00", "master_pl": 7500},
                        {"status": "planned", "started_at": None, "master_pl": None}])
    check(tg == {"2026-10-20": 7384, "2026-10-21": 7500}, "Ergebnis je CME-Handelstag")
    c = R(REGEL, j150, ST150, 164884, 164884, 3000, 150000, tg, 150000)
    check(c["consistency_pct"] == 50.4, f"Consistency-Angabe: größter Tag {c['max_tag']} von {c['gewinn']} = {c['consistency_pct']} % (Marc 20./21.10.)")

    print("Zeitverteilung")
    rnd = random.Random(7)
    kand = [("u1", f"k{i}") for i in range(5)] + [("u2", "m1")]
    m, rest = ns["fp_zeiten"](kand, {"u2": [600.0]}, None, 150, 1200, 100, [90, 150], 15, rnd)
    u1 = sorted(m[f"k{i}"] for i in range(5) if f"k{i}" in m)
    check(len(u1) == 5 and all(b - a >= 90 for a, b in zip(u1, u1[1:])) and u1[0] >= 150 and u1[-1] <= 1200,
          f"5 Konten einer ID über 02:30–20:00 verteilt, ≥ 90 min Abstand ({[int(x) for x in u1]})")
    check("m1" in m and abs(m["m1"] - 600) >= 90, f"Abstand zu schon geplantem Big Trade derselben ID ({int(m.get('m1', 0))} vs 600)")
    m2, rest2 = ns["fp_zeiten"]([("u1", "a"), ("u1", "b")], {}, None, 150, 1200, 1150, [90, 150], 15, random.Random(1))
    check(rest2 == ["a", "b"] or (len(m2) <= 1 and len(rest2) >= 1), "kurz vor Fensterende: was nicht passt, bleibt ausgelassen")


def lauf_test():
    """fp_planen als Trockenlauf gegen nachgebaute DB-Antworten (kein Netz): Lader, Ausschlüsse, Plan-Zeile, nichts geschrieben."""
    print("Trockenlauf (nachgebaute DB)")
    src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]
    i, j = src.index("FP_TAKT_S = 300"), src.index('@app.route("/admin/funded-plan"')
    ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "random": random, "time": __import__("time"),
          "GP_SLAVE_PPL": 0.85, "_firm_norm": lambda x: str(x or "")}
    code = "\n".join(block(n) for n in ("_wd_num", "_liq_de", "_cme_handelstag", "ist_topstep_express", "liq_konto_boden", "liq_stufe", "_ap_norm",
                                        "ap_regel_finden", "_wd_konto_groesse", "ap_balance_live", "liq_peak", "liq_regel_waehlen",
                                        "_wd_futures_frontcode", "_ap_tz"))
    exec(code + "\n" + src[i:j], ns)
    U1, U2 = "00000000-0000-4000-a000-0000000000a1", "00000000-0000-4000-a000-0000000000a2"
    konten = [
        {"id": "k1", "user_id": U1, "name": "150k PAAPEX000000000001 → Funded", "firm": "Apex Trader", "account_type": "funded", "auto_planer": True,
         "tv_balance": 150000, "tv_balance_at": "2026-10-27T01:00:00+00:00"},
        {"id": "k2", "user_id": U1, "name": "100k PAAPEX000000000002 → Funded", "firm": "Apex Trader", "account_type": "funded", "auto_planer": True,
         "tv_balance": None, "tv_balance_at": None},
        {"id": "k3", "user_id": U2, "name": "100k PAAPEX000000000003 → Funded", "firm": "Apex Trader", "account_type": "funded", "auto_planer": True,
         "tv_balance": 106000, "tv_balance_at": "2026-10-27T01:00:00+00:00"},
        {"id": "k4", "user_id": U2, "name": "150k PAAPEX000000000004 → Funded", "firm": "Apex Trader", "account_type": "funded", "auto_planer": True,
         "tv_balance": 165100, "tv_balance_at": "2026-10-27T01:00:00+00:00"},
        {"id": "k5", "user_id": U2, "name": "150k TDFY000005 → Funded", "firm": "Tradeify", "account_type": "funded", "auto_planer": True,
         "tv_balance": 150000, "tv_balance_at": "2026-10-27T01:00:00+00:00"},
        {"id": "k6", "user_id": U1, "name": "150k PAAPEX000000000006 → Funded", "firm": "Apex Trader", "account_type": "funded", "auto_planer": True,
         "tv_balance": 150000, "tv_balance_at": "2026-10-27T01:00:00+00:00"},
    ]
    plaene = [{"id": "p3", "master_account_id": "k3", "status": "completed", "started_at": "2026-10-26T14:00:00+00:00", "ended_at": "2026-10-26T15:00:00+00:00",
               "master_pl": 6000, "slave_pl": -825, "orbit_v3": True, "hedge_eur": 825, "bal_start": 100000, "konto_typ": "funded"},
              {"id": "p6", "master_account_id": "k6", "status": "planned", "started_at": None, "orbit_v3": True, "hedge_eur": 1000}]
    geschrieben = []

    def sb_all(tab, par):
        if tab == "accounts":
            return [dict(a) for a in konten]
        if tab == "trade_plans" and "master_account_id" in par:
            return [dict(p) for p in plaene]
        return []
    ns.update(_sb_all=sb_all, sb_select=lambda t, p: [{"id": 1, "aktiv": False, "user_ids": [U1, U2], "firmen": ns["FP_FIRMEN_STANDARD"], "zeiten": {}}]
              if t == "funded_plan_regeln" else [],
              sb_insert=lambda t, b: geschrieben.append((t, b)), sb_update=lambda t, p, b: geschrieben.append((t, b)),
              _ap_archiviert=lambda: set(), _liq_verlauf_laden=lambda ids: [{"master_account_id": "k3", "konto_typ": "funded", "id": "p3",
                                                                            "ended_at": "2026-10-26T15:00:00+00:00", "bal_end": 106000}],
              _liq_regeln_laden=lambda: [{"firma": "Apex Trader", "kontotyp": "funded", "groesse": 150000, "art": "stufen", "stufen": ST150},
                                         {"firma": "Apex Trader", "kontotyp": "funded", "groesse": 100000, "art": "stufen", "stufen": ST100}],
              _ap_namen=lambda: ({U1: "Eins", U2: "Zwei"}, set()))
    jetzt = datetime(2026, 10, 27, 4, 0, tzinfo=timezone.utc)   # 08:00 Dubai
    e = ns["fp_planen"](trocken=True, jetzt=jetzt, seed=3)
    g = {z["konto_id"]: z for z in e["geplant"]}
    a = {z["konto_id"]: z for z in e["ausgelassen"]}
    check(e["ok"] and not geschrieben, "Trockenlauf schreibt nichts")
    check(set(g) == {"k1", "k3"}, f"geplant: k1 (150k frisch) + k3 (100k nach Gewinn) — {sorted(g)}")
    check("k2" in a and "nicht live" in a["k2"]["grund"], "ohne Balance → ausgelassen (Balance lesen)")
    check("k6" in a and a["k6"]["grund"] == "schon geplant", "Konto mit geplantem Plan → ausgelassen")
    check([z["konto_id"] for z in e["ziel"]] == ["k4"], "165.100 → Ziel erreicht")
    check("k5" not in g and "k5" not in a, "Tradeify (aus) wird gar nicht betrachtet")
    k3 = g.get("k3") or {}
    check(k3.get("liq") == 100100 and k3.get("sl") == 2500 and k3.get("tp") == 6000 and abs((k3.get("offen_eur") or 0) - 1237.5) < 0.01,
          f"k3: Liq {k3.get('liq')} (Lock aus Höchststand 106.000), SL {k3.get('sl')}, TP {k3.get('tp')}, offen {k3.get('offen_eur')} €")
    e2 = ns["fp_planen"](trocken=False, jetzt=jetzt, seed=3)
    zeilen = [b for t, b in geschrieben if t == "trade_plans"]
    z1 = next((b for b in zeilen if b["master_account_id"] == "k1"), {})
    check(len(zeilen) == 2 and z1.get("route") == "tvv2" and z1.get("orbit_v3") is True and (z1.get("hedge_eur") or 0) > 0
          and z1.get("auto_plan") is False and z1.get("auto_bestaetigt_at") and z1.get("master_symbol", "").startswith("NQ")
          and z1.get("master_tp") == 7500 and z1.get("master_sl") == 2500 and z1.get("master_contracts") == 2,
          f"scharf: 2 Pläne tvv2 + orbit_v3 + hedge_eur, auto-bestätigt ({z1.get('hedge_eur')} €, {z1.get('master_symbol')})")
    check(any(t == "accounts" and b.get("waiting_payout_since") for t, b in geschrieben), "scharf: Ziel-Konto → waiting_payout_since")
    starts = sorted(datetime.fromisoformat(b["start_um"]) for b in zeilen)
    check(all(s >= jetzt + timedelta(minutes=15) for s in starts), "Startzeiten frühestens jetzt + 15 min")


if __name__ == "__main__":
    ns = laden()
    szenario(ns)
    einzeln(ns)
    lauf_test()
    if FEHLER:
        print(f"\n✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("\n✓ alle Prüfungen grün")
