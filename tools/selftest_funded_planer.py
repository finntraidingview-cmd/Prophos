#!/usr/bin/env python3
"""Selbsttest: FUNDED-PLANER (fdp_*, 27.10.2026, Finn: „einen Auto-Planer für Funded … erst mal für alle Fundeds von Apex"). Rechnet Finns
Szenario-Baum (über den Master, 27.10.2026; 100k-Kosten 350 €) mit den echten Funktionen aus app.py nach — TP/SL/Liq/Stufe/Hedge je Tag
für 150k und 100k —, dazu Kontrakt-Verteilung, Fenster des Challenge-Planers, Tagesdeckel je ID, zufällige Startzeiten mit 15 min
Firmen-Abstand und einen Tag mit allen 13 Apex-Fundeds (Trockenlauf gegen nachgebaute DB). Rein rechnend, ohne Netz.
Aufruf: python3 tools/selftest_funded_planer.py"""
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
FEHLER = []
SRC = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


def block(name):
    i = SRC.index(f"\ndef {name}(") + 1
    return SRC[i:SRC.find("\n\n\n", i)]


HILFEN = ("_wd_num", "_liq_de", "_cme_handelstag", "ist_topstep_express", "liq_konto_boden", "liq_stufe", "_ap_norm", "ap_regel_finden",
          "_wd_konto_groesse", "ap_balance_live", "liq_peak", "liq_regel_waehlen", "_wd_futures_frontcode", "_ap_tz")


def laden():
    """Hilfsfunktionen aus app.py + der ganze FUNDED-PLANER-Block (bis zur Route)."""
    i, j = SRC.index("FDP_TAKT_S = 300"), SRC.index('@app.route("/admin/funded-plan"')
    ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "random": random, "time": time,
          "GP_SLAVE_PPL": 0.85, "_firm_norm": lambda x: str(x or "")}
    exec("\n".join(block(n) for n in HILFEN) + "\n" + SRC[i:j], ns)
    return ns


# liq_regeln id 4 (150k) und id 13 (100k), Stand 27.10.2026 (Apex Help Center, vom Master gegengeprüft)
ST150 = [{"minis": 4, "ab_balance": 150000, "daily_loss_usd": 2500}, {"minis": 5, "ab_balance": 152000, "daily_loss_usd": 2500},
         {"minis": 7, "ab_balance": 153000, "daily_loss_usd": 2500}, {"minis": 10, "ab_balance": 155000, "daily_loss_usd": 3000},
         {"minis": 10, "ab_balance": 160000, "daily_loss_usd": 4000}]
ST100 = [{"minis": 3, "ab_balance": 100000, "daily_loss_usd": 1750}, {"minis": 4, "ab_balance": 102000, "daily_loss_usd": 1750},
         {"minis": 5, "ab_balance": 103000, "daily_loss_usd": 1750}, {"minis": 6, "ab_balance": 105000, "daily_loss_usd": 2500},
         {"minis": 6, "ab_balance": 110000, "daily_loss_usd": 3500}]


def szenario(ns):
    REGEL = ns["FDP_FIRMEN_STANDARD"][0]
    R, jg = ns["fdp_konto_rechnen"], ns["fdp_je_groesse"]
    j150, j100 = jg(REGEL, 150000), jg(REGEL, 100000)
    check(j150["kosten_eur"] == 550 and j100["kosten_eur"] == 350, "Kontokosten Seed: 150k 550 €, 100k 350 € (Finn 27.10.2026)")

    def t(r, tp, sl, hsl, htp):
        # Finns Werte auf ganze € (abgeschnitten) → ±1 €
        ok = r["aktion"] == "planen" and r["tp"] == tp and r["sl"] == sl and abs(r["hedge_sl_eur"] - hsl) <= 1 and abs(r["hedge_tp_eur"] - htp) <= 1
        return ok, f"TP {r.get('tp')} / SL {r.get('sl')}, Hedge +{r.get('hedge_sl_eur')} / −{r.get('hedge_tp_eur')}"

    print("150k (Kosten 550 €)")
    r = R(REGEL, j150, ST150, 150000, None, 550, 150000, 150000)
    ok, txt = t(r, 7500, 2500, 344, 1031)
    check(ok and r["liq"] == 146000 and r["kontrakte"] == 2 and r["stufe"] == 1, "Tag 1: " + txt + f", Liq {r.get('liq')}, {r.get('kontrakte')} NQ")
    offen = ns["fdp_offen"](550, [-r["hedge_tp_eur"]])
    check(abs(offen - 1581.25) < 0.01, f"Gewinn Tag 1: offene Kosten {offen} € (550 + 1.031,25)")
    r2 = R(REGEL, j150, ST150, 157500, 157500, offen, 150000, 150000)
    ok, txt = t(r2, 7500, 3000, 641, 1602)
    check(ok and r2["liq"] == 150100 and r2["ziel"] == 165000, "Tag 2 nach Gewinn: " + txt + f", Liq {r2.get('liq')} (Lock), Ziel {r2.get('ziel')}")
    z = R(REGEL, j150, ST150, 165000, 165000, 3183.85, 150000, 150000)
    check(z["aktion"] == "ziel" and "Winning Days" in z["grund"], "165.000 → Ziel erreicht → Winning Days")
    rv = R(REGEL, j150, ST150, 147500, 150000, ns["fdp_offen"](550, [r["hedge_sl_eur"]]), 150000, 150000)
    ok, txt = t(rv, 2500, 1500, 206, 344)
    check(ok and rv["tp_art"] == "break_even" and rv["liq"] == 146000, "Verlust Tag 1 → 147.500, Tag 2: " + txt + " (Break-even, SL = Rest bis Liq)")
    offen_3 = ns["fdp_offen"](550, [-r["hedge_tp_eur"], r2["hedge_sl_eur"]])
    check(round(offen_3) == 940, f"157.500 → Verlust → 154.500: offen {offen_3} € (≈ 940)")
    r3 = R(REGEL, j150, ST150, 154500, 157500, offen_3, 150000, 150000)
    check(r3["sl"] == 2500 and r3["tp"] == 7500 and r3["liq"] == 150100, f"Tag 3 bei 154.500: TP {r3.get('tp')} / SL {r3.get('sl')} (Stufe ab 153.000)")
    r4 = R(REGEL, j150, ST150, 162000, 162000, offen_3 + r3["hedge_tp_eur"], 150000, 150000)
    check(r4["tp"] == 3000 and r4["sl"] == 4000, f"Gewinn → 162.000, Tag 4: TP {r4.get('tp')} / SL {r4.get('sl')} (Rest bis Ziel, Stufe ab 160.000)")

    print("100k (Kosten 350 €, Verhältnis 350/3.000)")
    q = R(REGEL, j100, ST100, 100000, None, 350, 100000, 100000)
    ok, txt = t(q, 6000, 1750, 204, 700)
    check(ok and q["liq"] == 97000 and abs(q["verhaeltnis"] - 350 / 3000) < 1e-4, "Tag 1: " + txt + f", Liq {q.get('liq')}")
    o2 = ns["fdp_offen"](350, [-q["hedge_tp_eur"]])
    q2 = R(REGEL, j100, ST100, 106000, 106000, o2, 100000, 100000)
    check(q2["sl"] == 2500 and q2["tp"] == 6000 and q2["liq"] == 100100 and q2["ziel"] == 112000 and abs(o2 - 1050) < 0.01,
          f"Gewinn → 106.000: offen {o2} €, Tag 2 TP {q2.get('tp')} / SL {q2.get('sl')}, Liq {q2.get('liq')} (Lock) → Ziel 112.000")
    ov = ns["fdp_offen"](350, [q["hedge_sl_eur"]])
    qv = R(REGEL, j100, ST100, 98250, 100000, ov, 100000, 100000)
    check(qv["tp"] == 1750 and qv["sl"] == 1250 and abs(qv["hedge_sl_eur"] - 145.83) < 0.02,
          f"Verlust → 98.250 (offen {ov} €), Tag 2: TP {qv.get('tp')} / SL {qv.get('sl')}, Hedge +{qv.get('hedge_sl_eur')} / −{qv.get('hedge_tp_eur')}")


def bausteine(ns):
    print("Bausteine")
    REGEL = ns["FDP_FIRMEN_STANDARD"][0]
    R, jg = ns["fdp_konto_rechnen"], ns["fdp_je_groesse"]
    j150, j100 = jg(REGEL, 150000), jg(REGEL, 100000)
    b = R(REGEL, j150, ST150, 145990, 150000, 550, 150000, 150000)
    check(b["aktion"] == "aus" and "geblowt" in b["grund"], "Balance unter der Liquidation → aus (geblowt?)")
    k = R(REGEL, j150, ST150, 146050, 150000, 550, 150000, 150000)
    check(k["aktion"] == "aus" and "zu klein" in k["grund"], "50 $ über der Liquidation → aus (Abstand zu klein)")
    check(R(REGEL, None, ST150, 150000, None, 550, None, 150000)["aktion"] == "aus", "Größe ohne Werte → aus")
    u = R(REGEL, j100, ST100, 150074.4, None, 350, 100000, 100000)
    check(u["aktion"] == "aus" and "unplausibel" in u["grund"], "100k mit 150.074 $ (Fehllesung Chris) → aus, nicht „Ziel erreicht“")
    h = R(REGEL, j150, ST150, 150000, None, 550, 150000, 150000)
    check(h["master_risk"] == 4000 and h["slave_risk"] == 550 and h["lots"] == 6.47 and abs(h["hedge_eur"] - 1031.15) < 0.02,
          f"Plan-Felder wie Trade-Popup: master_risk {h['master_risk']}, slave_risk {h['slave_risk']}, {h['lots']} Lot, hedge_eur {h['hedge_eur']}")
    # Kontrakte (Finn 27.10.2026): 100k 1/2 je 50 %, 150k 2 mit 75 % / 3 mit 25 %, gedeckelt auf die Minis der Stufe
    K = ns["fdp_kontrakte"]
    rnd = random.Random(11)
    n = 20000
    z150 = [K(j150["kontrakte"], 4, rnd) for _ in range(n)]
    z100 = [K(j100["kontrakte"], 3, rnd) for _ in range(n)]
    a2, a3 = z150.count(2) / n, z150.count(3) / n
    b1, b2 = z100.count(1) / n, z100.count(2) / n
    check(set(z150) == {2, 3} and abs(a2 - 0.75) < 0.015 and abs(a3 - 0.25) < 0.015, f"150k: 2 NQ {a2:.1%} / 3 NQ {a3:.1%} (Soll 75/25)")
    check(set(z100) == {1, 2} and abs(b1 - 0.5) < 0.015 and abs(b2 - 0.5) < 0.015, f"100k: 1 NQ {b1:.1%} / 2 NQ {b2:.1%} (Soll 50/50)")
    check(K({"3": 1}, 2, rnd) == 2 and K(j150["kontrakte"], 2, random.Random(5)) <= 2, "Deckel: nie mehr als die Minis der Stufe")
    check(K(j150["kontrakte"], 4) == 2 and K(j100["kontrakte"], 3) == 1 and K(None, 3) == 1, "ohne Würfel: wahrscheinlichster Wert (Gleichstand: kleinerer)")
    r = R(REGEL, j150, ST150, 150000, None, 550, 150000, 150000, random.Random(3))
    check(r["tp_pkt"] == round(7500 / (20 * r["kontrakte"]), 2) and r["sl_pkt"] == round(2500 / (20 * r["kontrakte"]), 2),
          f"Punkte = $ ÷ (Kontrakte × 20 $): {r['kontrakte']} NQ → TP {r['tp_pkt']} / SL {r['sl_pkt']} Punkte")
    tg = ns["fdp_tage"]([{"status": "completed", "started_at": "2026-10-20T14:00:00+00:00", "master_pl": 7384},
                         {"status": "completed", "started_at": "2026-10-21T14:00:00+00:00", "master_pl": 7500},
                         {"status": "planned", "started_at": None, "master_pl": None}])
    c = R(REGEL, j150, ST150, 164884, 164884, 3000, 150000, 150000, None, tg)
    check(tg == {"2026-10-20": 7384, "2026-10-21": 7500} and c["consistency_pct"] == 50.4 and c["aktion"] == "planen" and c["tp"] == 116,
          f"Anzeige „größter Tag {c['consistency_pct']} %“ (Marc 20./21.10.) — keine Wache, nächster TP normal ({c['tp']} $ bis Ziel)")
    z = ns["fdp_zyklus"](150000, [], [])
    check(z == {"nr": 1, "ab": None, "start": 150000.0}, "Zyklus 1 ohne Payout ab Kontogröße")
    z2 = ns["fdp_zyklus"](150000, ["2026-10-20T10:00:00+00:00"], [{"started_at": "2026-10-19T10:00:00+00:00", "bal_start": 160000},
                                                                   {"started_at": "2026-10-21T10:00:00+00:00", "bal_start": 151200}])
    check(z2["nr"] == 2 and z2["start"] == 151200, "Zyklus 2 ab erstem Trade nach dem Payout")

    print("Fenster, Tagesdeckel, Zeiten")
    F = ns["fdp_fenster"]
    ch = {"tz": "Europe/Berlin", "fenster": [["02:00", "20:00", 100]], "fenster_tz": "Asia/Dubai", "start_bis": "20:00"}
    check(F(ch) == ("Asia/Dubai", 120, 1200), f"Fenster des Challenge-Planers (live-Form): {F(ch)} = 02:00–20:00 Dubai")
    check(F({"fenster": [["02:00", "14:00", 37], ["14:00", "16:30", 25]], "tz": "Europe/Berlin"}) == ("Europe/Berlin", 120, 990), "mehrere Fenster: frühestes von bis spätestes bis")
    check(F({}) == ("Asia/Dubai", 120, 1200), "ohne Fenster: Rückfall 02:00–20:00 Dubai")
    gew, ueber = ns["fdp_auswahl"]([("u1", f"k{i}") for i in range(5)] + [("u2", "m1"), ("u2", "m2"), ("u3", "x")], {"u2": 1}, 2, random.Random(4))
    je = {}
    for u, _k in gew:
        je[u] = je.get(u, 0) + 1
    check(je == {"u1": 2, "u2": 1, "u3": 1} and len(ueber) == 4, f"Tagesdeckel 2 je ID (u2 hatte heute schon 1): {je}, {len(ueber)} auf morgen")
    kand = [("u1", "a", "apex"), ("u1", "b", "apex"), ("u2", "c", "apex"), ("u3", "d", "apex"), ("u4", "e", "tradeify")]
    m, rest = ns["fdp_zeiten"](kand, {"u1": [600.0]}, {"apex": [300.0, 305.0]}, 120, 1200, 90, 15, random.Random(9))
    neu = sorted(m[k] for k in "abcd")
    check(not rest and all(abs(x - y) >= 15 for x in neu for y in [300.0, 305.0]) and all(b - a >= 15 for a, b in zip(neu, neu[1:]))
          and abs(m["a"] - m["b"]) >= 90 and all(abs(m[k] - 600) >= 90 for k in "ab"),
          f"zufällig im Fenster, ≥ 15 min zu jedem Apex-Start (auch Challenge 05:00/05:05), ≥ 90 min je ID: {[f'{int(x)//60:02d}:{int(x)%60:02d}' for x in neu]}")
    m2, rest2 = ns["fdp_zeiten"]([("u1", "a", "apex"), ("u2", "b", "apex")], {}, {}, 120, 1200, 90, 15, random.Random(1), erlaubt=lambda x: x >= 180)
    check(not rest2 and min(m2.values()) >= 180, "nur erlaubte Minuten (CME-Handelstag), sonst neu gewürfelt")
    m3, rest3 = ns["fdp_zeiten"]([("u1", "a", "apex")], {}, {"apex": [float(x) for x in range(120, 1201, 10)]}, 120, 1200, 90, 15, random.Random(1))
    check(rest3 == ["a"] and not m3, "kein freier Slot (alle 10 min belegt) → ausgelassen statt hinten angehängt")
    t1 = ns["fdp_zeiten"]([("u1", "a", "apex"), ("u2", "b", "apex"), ("u3", "c", "apex")], {}, {}, 120, 1200, 90, 15, random.Random(1))[0]
    t2 = ns["fdp_zeiten"]([("u1", "a", "apex"), ("u2", "b", "apex"), ("u3", "c", "apex")], {}, {}, 120, 1200, 90, 15, random.Random(2))[0]
    check(t1 != t2, "kein festes Raster: anderer Würfel → andere Zeiten")


def tag_13(ns):
    """Ein Tag mit allen 13 Apex-Fundeds (Verteilung wie HT 27.10.2026: 5 / 4 / 1 / 1 / 1 / 1 je ID), dazu 3 Apex-Challenge-Starts des
    Challenge-Planers einer anderen ID. Trockenlauf + scharfer Lauf gegen nachgebaute DB."""
    print("Tag mit 13 Apex-Fundeds (Trockenlauf, nachgebaute DB)")
    U = {n: f"00000000-0000-4000-a000-0000000000{i:02d}" for i, n in enumerate(["A", "B", "C", "D", "E", "F", "G"], 1)}
    verteil = [("A", 5, "100k"), ("B", 2, "100k"), ("B", 2, "150k"), ("C", 1, "100k"), ("D", 1, "150k"), ("E", 1, "100k"), ("F", 1, "150k")]
    konten, n = [], 0
    for wer, anz, gr in verteil:
        for _ in range(anz):
            n += 1
            konten.append({"id": f"k{n:02d}", "user_id": U[wer], "name": f"{gr} PAAPEX0000000000{n:02d} → Funded", "firm": "Apex Trader",
                           "account_type": "funded", "auto_planer": True, "tv_balance": 150000 if gr == "150k" else 100000,
                           "tv_balance_at": "2026-10-27T01:00:00+00:00"})
    # Challenge-Planer: Apex-Challenge-Starts von ID G um 06:00, 06:10 und 13:00 Dubai (planned) — der Funded-Planer muss 15 min halten
    ch = [{"user_id": U["G"], "master_firm": "Apex Trader", "status": "planned", "route": "tvv2", "orbit_v3": False, "hedge_eur": None,
           "winning_day": None, "start_um": (datetime(2026, 10, 28, 0, 0, tzinfo=timezone.utc) + timedelta(hours=h - 4)).isoformat()}
          for h in (6.0, 6 + 1 / 6, 13.0)]
    geschrieben = []

    def sb_all(tab, par):
        if tab == "accounts":
            return [dict(a) for a in konten]
        if tab == "trade_plans" and "master_account_id" in par:
            return []
        if tab == "trade_plans" and "user_id" in par:
            return [dict(c) for c in ch]
        return []

    def sb_select(tab, par):
        if tab == "funded_plan_regeln":
            return [{"id": 1, "aktiv": False, "user_ids": list(U.values()), "firmen": ns["FDP_FIRMEN_STANDARD"], "zeiten": dict(ns["FDP_ZEITEN_STANDARD"])}]
        if tab == "auto_plan_regeln":
            return [{"zeiten": {"tz": "Europe/Berlin", "fenster": [["02:00", "20:00", 100]], "fenster_tz": "Asia/Dubai", "start_bis": "20:00"}}]
        return []
    ns.update(_sb_all=sb_all, sb_select=sb_select, sb_insert=lambda t, b: geschrieben.append((t, b)),
              sb_update=lambda t, p, b: geschrieben.append((t, b)), _ap_archiviert=lambda: set(), _liq_verlauf_laden=lambda ids: [],
              _liq_regeln_laden=lambda: [{"firma": "Apex Trader", "kontotyp": "funded", "groesse": 150000, "art": "stufen", "stufen": ST150},
                                         {"firma": "Apex Trader", "kontotyp": "funded", "groesse": 100000, "art": "stufen", "stufen": ST100}],
              _ap_namen=lambda: ({v: k for k, v in U.items()}, set()))
    jetzt = datetime(2026, 10, 27, 21, 0, tzinfo=timezone.utc)   # 01:00 Dubai, vor dem Fenster → plant den Handelstag 28.10.
    e = ns["fdp_planen"](trocken=True, jetzt=jetzt, seed=27)
    je = {}
    for z in e["geplant"]:
        je[z["user_id"]] = je.get(z["user_id"], 0) + 1
    namen = {v: k for k, v in U.items()}
    check(e["ok"] and not geschrieben and e["tag"] == "2026-10-28", f"Trockenlauf schreibt nichts, plant den Handelstag {e.get('tag')}")
    check(len(e["geplant"]) == 8 and all(v <= 2 for v in je.values()) and je.get(U["A"]) == 2 and je.get(U["B"]) == 2,
          f"13 Fundeds → {len(e['geplant'])} geplant (max. 2 je ID): " + ", ".join(f"{namen[u]} {v}" for u, v in sorted(je.items(), key=lambda x: namen[x[0]])))
    ueber = [z for z in e["ausgelassen"] if "Tagesdeckel" in z.get("grund", "")]
    check(len(ueber) == 5, f"{len(ueber)} wegen Tagesdeckel auf morgen (A 3, B 2)")
    hm = lambda iso: datetime.fromisoformat(iso).astimezone(timezone(timedelta(hours=4)))
    starts = sorted(hm(z["start_um"]) for z in e["geplant"])
    # jeder Funded-Start zu jedem anderen Apex-Start (Funded + Challenge); Challenge untereinander (06:00/06:10) bleibt bei 1 min
    andere = starts + [hm(c["start_um"]) for c in ch]
    gap = min(abs((a - b).total_seconds()) / 60 for i, a in enumerate(starts) for j, b in enumerate(andere) if j != i)
    check(gap >= 15, f"kleinster Abstand Funded-Start ↔ jeder andere Apex-Start (Funded + Challenge) {gap:.1f} min ≥ 15")
    check(all((2, 0) <= (s.hour, s.minute) <= (20, 0) for s in starts), "alle Starts im Challenge-Fenster 02:00–20:00 Dubai")
    print("    Startzeiten (Dubai): " + ", ".join(f"{s:%H:%M} {namen[z['user_id']]}·{z['kontrakte']}NQ"
                                                  for s, z in sorted(((hm(z['start_um']), z) for z in e['geplant']), key=lambda x: x[0])))
    print("    Challenge (Dubai):   " + ", ".join(f"{hm(c['start_um']):%H:%M}" for c in ch))
    je_id_min = []
    for u in U.values():
        st = sorted(hm(z["start_um"]) for z in e["geplant"] if z["user_id"] == u)
        je_id_min += [(b - a).total_seconds() / 60 for a, b in zip(st, st[1:])]
    check(ns["FDP_ZEITEN_STANDARD"]["abstand_id_min"] == 90 and all(x >= 90 for x in je_id_min),
          f"zwei Funded derselben ID ≥ 90 min auseinander ({[round(x) for x in je_id_min]})")
    e2 = ns["fdp_planen"](trocken=False, jetzt=jetzt, seed=27)
    zeilen = [b for t, b in geschrieben if t == "trade_plans"]
    z1 = zeilen[0] if zeilen else {}
    check(len(zeilen) == 8 and all(b["route"] == "tvv2" and b["orbit_v3"] is True and b["hedge_eur"] > 0 and b["auto_plan"] is False
                                   and b["master_symbol"].startswith("NQ") for b in zeilen),
          f"scharf: 8 Pläne tvv2 + orbit_v3 + hedge_eur ({z1.get('master_symbol')}, Plan-Tag {e2.get('tag')})")
    # Finn 27.10.2026: jeden Funded-Trade von Hand bestätigen — Standard = Vorschlag OHNE start_um (kein PC-Tab startet ihn)
    check(all(b["start_um"] is None and b["auto_bestaetigt_at"] is None and b["mt5_baseline"]["funded_plan"]["start_um"]
              and "Vorschlag" in b["notes"] for b in zeilen) and all(z.get("vorschlag") for z in e2["geplant"]),
          "Standard (auto_bestaetigen aus): Vorschlag ohne start_um/auto_bestaetigt_at, Zeit nur in mt5_baseline.funded_plan.start_um")


def ziel_wd(ns):
    print("Ziel erreicht → Winning Days (scharf)")
    geschrieben = []
    U1 = "00000000-0000-4000-a000-0000000000a1"
    konto = {"id": "kz", "user_id": U1, "name": "150k PAAPEX000000000099 → Funded", "firm": "Apex Trader", "account_type": "funded",
             "auto_planer": True, "tv_balance": 165100, "tv_balance_at": "2026-10-27T01:00:00+00:00"}
    ns.update(_sb_all=lambda t, p: [dict(konto)] if t == "accounts" else [],
              sb_select=lambda t, p: ([{"id": 1, "aktiv": True, "user_ids": [U1], "firmen": ns["FDP_FIRMEN_STANDARD"], "zeiten": {}}]
                                      if t == "funded_plan_regeln" else []),
              sb_insert=lambda t, b: geschrieben.append((t, {}, b)), sb_update=lambda t, p, b: geschrieben.append((t, p, b)))
    e = ns["fdp_planen"](trocken=False, jetzt=datetime(2026, 10, 27, 4, 0, tzinfo=timezone.utc), seed=1)
    upd = [x for x in geschrieben if x[0] == "accounts"]
    ok = (len(e["ziel"]) == 1 and len(upd) == 1 and upd[0][2].get("account_type") == "winning_days" and upd[0][2].get("wd_farm") is True
          and upd[0][2].get("name") == "150k PAAPEX000000000099 → Winning Days" and upd[0][1].get("account_type") == "eq.funded"
          and not any("waiting_payout_since" in x[2] for x in geschrieben))
    check(ok, "165.100 → account_type winning_days + wd_farm, Name „→ Winning Days“, kein Waiting for Payout")


def bestaetigen(ns):
    """Bestätigen von Hand (Finn 27.10.2026): Guard-Filter der Funded-Routen, Startzeit beim Bestätigen, Auto-Bestätigen-Schalter."""
    print("Bestätigen von Hand / Auto-Bestätigen")
    exec(block("fdp_eingriff_filter") + "\n" + block("fdp_start_bestaetigt"), ns)
    ns["AP_EINGRIFF_MAX"] = 200
    pid = "11111111-2222-4333-8444-555555555555"
    p, art = ns["fdp_eingriff_filter"]("bestaetigen", [pid])
    check(art == "patch" and p["status"] == "eq.planned" and p["mt5_baseline->funded_plan"] == "not.is.null" and p["auto_bestaetigt_at"] == "is.null"
          and p["start_um_gestartet_at"] == "is.null" and p["started_at"] == "is.null" and p["mt5_baseline->puls_pause"] == "is.null" and p["id"] == "eq." + pid,
          "bestaetigen: nur ungestartete, unbestätigte Funded-Pläne ohne Puls-Pause")
    p2, art2 = ns["fdp_eingriff_filter"]("loeschen", [pid, "kaputt"], "00000000-0000-4000-a000-0000000000a1")
    check(art2 == "delete" and "auto_bestaetigt_at" not in p2 and p2["user_id"] == "eq.00000000-0000-4000-a000-0000000000a1",
          "loeschen: Guard ohne Bestätigt-Bedingung, eigene ID bei eingeschränkter Sicht, ungültige IDs fallen weg")
    check(ns["fdp_eingriff_filter"]("starten", [pid])[0] is None and ns["fdp_eingriff_filter"]("zurueck", ["x"])[0] is None, "unbekannte Aktion / keine gültige ID → abgelehnt")
    j = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)
    check(ns["fdp_start_bestaetigt"]("2026-10-28T12:00:00+00:00", j).startswith("2026-10-28T12:00")
          and ns["fdp_start_bestaetigt"]("2026-10-28T09:00:00+00:00", j).startswith("2026-10-28T10:02")
          and ns["fdp_start_bestaetigt"](None, j).startswith("2026-10-28T10:02"),
          "Startzeit beim Bestätigen: vorgeschlagene Zeit, schon vorbei → jetzt + 2 min")
    # Vorfall 28.10.2026 10:38 Dubai: 7 Vorschläge bestätigt, 4 mit vergangener Zeit (zwei davon Chris) → alle auf jetzt + 2 min
    exec(block("fdp_start_verteilen"), ns)
    ns["FDP_BESTAETIGEN_STREU_S"] = int(re.search(r"^FDP_BESTAETIGEN_STREU_S = (\d+)", SRC, re.M).group(1))
    j2 = datetime(2026, 10, 28, 6, 38, tzinfo=timezone.utc)
    C, I, M, K = "u-chris", "u-ina", "u-marc", "u-mike"
    pl = [{"id": "c3", "fp_start": "2026-10-27T23:51:54+00:00", "firma": "apextrader", "user_id": C},
          {"id": "c6", "fp_start": "2026-10-28T04:33:55+00:00", "firma": "apextrader", "user_id": C},
          {"id": "i5", "fp_start": "2026-10-28T05:09:29+00:00", "firma": "apextrader", "user_id": I},
          {"id": "m2", "fp_start": "2026-10-27T23:15:30+00:00", "firma": "apextrader", "user_id": M},
          {"id": "k11", "fp_start": "2026-10-28T07:18:35+00:00", "firma": "apextrader", "user_id": K},
          {"id": "m4", "fp_start": "2026-10-28T09:17:25+00:00", "firma": "apextrader", "user_id": M}]
    belegt = [("tradeify", I, True, datetime(2026, 10, 28, 7, 0, tzinfo=timezone.utc))]
    st = {k: datetime.fromisoformat(v) for k, v in ns["fdp_start_verteilen"](pl, belegt, j2, 900, 5400, random.Random(3)).items()}
    zs = sorted(st.values())
    check(len(st) == 6 and all((b - a).total_seconds() >= 900 for a, b in zip(zs, zs[1:])),
          "Bestätigen mit vergangenen Zeiten: alle Starts derselben Firma ≥ 15 min auseinander (" + ", ".join(t.strftime("%H:%M") for t in zs) + " UTC)")
    check(abs((st["c6"] - st["c3"]).total_seconds()) >= 5400 and abs((st["m4"] - st["m2"]).total_seconds()) >= 5400
          and abs((st["i5"] - belegt[0][3]).total_seconds()) >= 5400, "je ID ≥ 90 min zwischen Big Trades, auch gegen einen anderen Big Trade der ID")
    check(st["k11"] == datetime(2026, 10, 28, 7, 18, 35, tzinfo=timezone.utc) or all(abs((st["k11"] - t).total_seconds()) >= 900 for k, t in st.items() if k != "k11"),
          "Vorschlag in der Zukunft ohne Konflikt bleibt, sonst gestreut")
    check(min(zs) >= j2 + timedelta(seconds=120), "kein Start vor jetzt + 2 min Vorlauf")
    st2 = ns["fdp_start_verteilen"](pl[:4], [], j2, 900, 5400, random.Random(4))
    check(len({v[11:16] for v in st2.values()}) == 4,
          "Zufall: kein fester Takt, vier verschiedene Minuten")
    U1 = "00000000-0000-4000-a000-0000000000a1"
    konto = {"id": "ka", "user_id": U1, "name": "150k PAAPEX000000000055 → Funded", "firm": "Apex Trader", "account_type": "funded",
             "auto_planer": True, "tv_balance": 150000, "tv_balance_at": "2026-10-27T01:00:00+00:00"}
    zeilen = []
    ns.update(_sb_all=lambda t, q: [dict(konto)] if t == "accounts" else [],
              sb_select=lambda t, q: ([{"id": 1, "aktiv": True, "auto_bestaetigen": True, "user_ids": [U1], "firmen": ns["FDP_FIRMEN_STANDARD"], "zeiten": {}}]
                                      if t == "funded_plan_regeln" else []),
              sb_insert=lambda t, b: zeilen.append(b) if t == "trade_plans" else None, sb_update=lambda t, q, b: None)
    ns["fdp_planen"](trocken=False, jetzt=datetime(2026, 10, 27, 4, 0, tzinfo=timezone.utc), seed=5)
    check(len(zeilen) == 1 and zeilen[0]["start_um"] and zeilen[0]["auto_bestaetigt_at"] and "Vorschlag" not in zeilen[0]["notes"],
          "Schalter auto_bestaetigen = true: Plan gleich mit start_um und auto_bestaetigt_at")


def jetzt_planen(ns):
    """„Jetzt planen" (27.10.2026): Bezugszeit heute / nächster Handelstag."""
    print("Jetzt planen")
    exec(block("fdp_plan_jetzt"), ns)
    f = ns["fdp_plan_jetzt"]
    j = datetime(2026, 10, 27, 15, 40, tzinfo=timezone.utc)          # 19:40 Dubai, Fenster bis 20:00 → nach „bis − 15 min"
    b, w = f("auto", j)
    check(w == "morgen" and b.isoformat() == "2026-10-27T20:01:00+00:00", f"19:40 Dubai, auto → nächster Handelstag ab 00:01 Dubai ({b.isoformat()})")
    b2, w2 = f("auto", datetime(2026, 10, 27, 6, 0, tzinfo=timezone.utc))   # 10:00 Dubai
    check(w2 == "heute" and b2.hour == 6, "10:00 Dubai, auto → heute (jetzt)")
    check(f("morgen", datetime(2026, 10, 27, 6, 0, tzinfo=timezone.utc))[1] == "morgen" and f("heute", j)[0] == j, "heute/morgen ausdrücklich")
    # scharfer Lauf mit Bezug „morgen": Vorschlag ohne start_um, Zeit im Fenster des nächsten Tages
    U1 = "00000000-0000-4000-a000-0000000000a1"
    konto = {"id": "km", "user_id": U1, "name": "150k PAAPEX000000000066 → Funded", "firm": "Apex Trader", "account_type": "funded",
             "auto_planer": True, "tv_balance": 150000, "tv_balance_at": "2026-10-27T01:00:00+00:00"}
    zeilen = []
    ns.update(_sb_all=lambda t, q: [dict(konto)] if t == "accounts" else [],
              sb_select=lambda t, q: ([{"id": 1, "aktiv": True, "auto_bestaetigen": False, "user_ids": [U1], "firmen": ns["FDP_FIRMEN_STANDARD"], "zeiten": {}}]
                                      if t == "funded_plan_regeln" else []),
              sb_insert=lambda t, x: zeilen.append(x) if t == "trade_plans" else None, sb_update=lambda t, q, x: None)
    e = ns["fdp_planen"](trocken=False, jetzt=b, seed=8)
    z = zeilen[0] if zeilen else {}
    st = (z.get("mt5_baseline") or {}).get("funded_plan", {}).get("start_um") or ""
    check(len(zeilen) == 1 and z["start_um"] is None and z["planned_for"] == "2026-10-28" and st.startswith("2026-10-2") and e["tag"] == "2026-10-28",
          f"Lauf für morgen: Vorschlag ohne start_um, planned_for 2026-10-28, vorgeschlagen {st[:16]}")


def big_trade(ns):
    """Finn 27.10.2026: Funded-Trades GENAU wie Orbit-Big-Trades von Hand (Prio 1 vor Winning Day) — nichts Eigenes, nur die Marken
    tvv2 + orbit_v3 + hedge_eur > 0. Geprüft mit den echten Erkennern: app.py puls_heim_big_trades („Puls bleibt zu Hause") und
    prophos.html bigTradePlan (Heim-Wache, Prio 1/2) über JavaScriptCore. Die DB-Funktion prophos_big_trade sieht dieselben Felder."""
    print("Big Trade wie von Hand (Heim-Wache, Puls bleibt zu Hause)")
    ns2 = {"_wd_num": ns["_wd_num"]}
    exec(block("puls_heim_big_trades"), ns2)
    U1 = "00000000-0000-4000-a000-0000000000a1"
    konto = {"id": "kb", "user_id": U1, "name": "150k PAAPEX000000000077 → Funded", "firm": "Apex Trader", "account_type": "funded",
             "auto_planer": True, "tv_balance": 150000, "tv_balance_at": "2026-10-27T01:00:00+00:00"}
    zeilen = []
    ns.update(_sb_all=lambda t, p: [dict(konto)] if t == "accounts" else [],
              sb_select=lambda t, p: ([{"id": 1, "aktiv": True, "user_ids": [U1], "firmen": ns["FDP_FIRMEN_STANDARD"], "zeiten": {}}]
                                      if t == "funded_plan_regeln" else []),
              sb_insert=lambda t, b: zeilen.append(b) if t == "trade_plans" else None, sb_update=lambda t, p, b: None)
    ns["fdp_planen"](trocken=False, jetzt=datetime(2026, 10, 27, 4, 0, tzinfo=timezone.utc), seed=2)
    fp = dict(zeilen[0], id="funded", status="open", started_at="2026-10-27T10:00:00+00:00", mt5_baseline={"hedge": {"pc": "pc-xxxxxx"}})
    hand = {"id": "hand", "status": "open", "route": "tvv2", "orbit_v3": True, "hedge_eur": 1328.5, "winning_day": None,
            "started_at": "2026-10-27T09:00:00+00:00", "mt5_baseline": {"hedge": {"pc": "pc-xxxxxx"}}}
    wd = {"id": "wd", "status": "open", "route": "tvv2", "orbit_v3": False, "hedge_eur": 175, "winning_day": True,
          "started_at": "2026-10-27T11:00:00+00:00", "mt5_baseline": {"hedge": {"pc": "pc-xxxxxx"}}}
    ids = [p["id"] for p in ns2["puls_heim_big_trades"]([fp, hand, wd], "pc-xxxxxx")]
    check(ids == ["funded", "hand"], f"app.py puls_heim_big_trades: Funded-Plan zählt wie der Hand-Big-Trade, Winning Day nicht ({ids})")
    jsc = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
    html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()

    def fn(name):
        i = html.index("  function " + name + "(")
        return html[i:html.index("\n  }\n", i) + 4]
    js = ("var accounts = [], tradePlans = []; function tvV2Konto(){ return 'X' } function bthFenster(r){ return r === 'tsv2' ? 'tsx' : 'tv' }"
          " function wdHeimWahl(l, j){ return j(l) }\n" + fn("tpIstWdPlan") + "\n" + fn("bigTradePlan") + "\n"
          "var F = { id: 'funded', status: 'open', route: 'tvv2', orbitV3: " + ("true" if fp["orbit_v3"] else "false") + ", hedgeEur: " + str(fp["hedge_eur"])
          + ", winningDay: null, startedAt: '2026-10-27T10:00:00Z' }\n"
          "var W = { id: 'wd', status: 'open', route: 'tvv2', orbitV3: false, hedgeEur: 175, winningDay: true, startedAt: '2026-10-27T11:00:00Z' }\n"
          "tradePlans = [W, F]; var a = bigTradePlan('tv'); tradePlans = [W]; var b = bigTradePlan('tv');"
          " print((a && a.id) + ' ' + (b && b.id) + ' ' + tpIstWdPlan(F))")
    import subprocess, tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js)
    try:
        out = subprocess.run([jsc, f.name], capture_output=True, text=True, timeout=30).stdout.strip()
    finally:
        os.unlink(f.name)
    check(out == "funded wd false", f"prophos.html bigTradePlan: Funded = Prio 1 vor dem Winning Day, kein WD-Plan ({out})")


def balance_selbst(ns):
    """Quelle (E) im Balance-Takt (app.py ap_bal_auto_funded): Funded-Konten der eingeschalteten Firmen liest der Bot selbst — nie gelesen,
    ohne Wert, Stand älter als das Ende des letzten Trades. acc_balance_wahl hier vereinfacht (nur tv_balance), Rest echt."""
    print("Balance selbst lesen (Funded, Quelle E)")
    ns2 = {"re": re, "datetime": datetime, "timezone": timezone, "AP_LESE_FELDER": ("tv_balance_at", "topstep_last_check", "meta_api_last_check"),
           "acc_balance_wahl": lambda a, e, d: ((a.get("tv_balance") or None), "USD", "TV", a.get("tv_balance_at") or "")}
    exec("\n".join(block(n) for n in ("ist_topstep_express", "ap_balance_live", "ap_bal_auto_funded")), ns2)
    k = lambda i, **x: dict({"id": i, "external_id": "PAAPEX" + i, "firm": "Apex Trader", "account_type": "funded", "auto_planer": True}, **x)
    konten = [k("nie"), k("leer", tv_balance=0, tv_balance_at="2026-10-26T10:00:00+00:00"),
              k("alt", tv_balance=150000, tv_balance_at="2026-10-26T10:00:00+00:00"),
              k("frisch", tv_balance=157500, tv_balance_at="2026-10-26T16:00:00+00:00"),
              k("aus", auto_planer=False), k("arch"), k("ohne", external_id=""), k("schon"), k("payout", waiting_payout_since="2026-10-26T00:00:00+00:00")]
    r = ns2["ap_bal_auto_funded"](konten, {"alt": "2026-10-26T15:00:00+00:00", "frisch": "2026-10-26T15:00:00+00:00"}, {"schon"}, {}, {}, {"arch"})
    check(sorted(r) == ["alt", "leer", "nie"] and "nie gelesen" in r["nie"] and "ohne Wert" in r["leer"] and "nicht gelesen" in r["alt"],
          f"liest: nie gelesen, ohne Wert, älter als der letzte Trade — nicht: frisch, Haken aus, archiviert, ohne External ID, schon dran, wartet auf Payout ({sorted(r)})")
    src_tick = SRC[SRC.index("\ndef ap_bal_auto_tick("):SRC.index("\ndef ", SRC.index("\ndef ap_bal_auto_tick(") + 10)]
    check("_ap_bal_auto_funded_konten()" in src_tick and src_tick.index("_ap_bal_auto_funded_konten()") < src_tick.index("if not kand:"),
          "ap_bal_auto_tick hängt (E) vor die Sende-Schleife (eigener try, Deckel 3/Tag + 90 min gelten)")


if __name__ == "__main__":
    ns = laden()
    szenario(ns)
    bausteine(ns)
    tag_13(ns)
    ziel_wd(ns)
    bestaetigen(ns)
    jetzt_planen(ns)
    big_trade(ns)
    balance_selbst(ns)
    if FEHLER:
        print(f"\n✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("\n✓ alle Prüfungen grün")
