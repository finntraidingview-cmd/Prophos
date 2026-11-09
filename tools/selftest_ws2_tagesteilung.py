#!/usr/bin/env python3
"""Selbsttest WS2 TRADES PRO TAG AUFTEILEN (app.py tt_*, Finn 09.11.2026 abends — Konstrukt WS2 abgesegnet; Master-Vorgaben bis Finn antwortet:
nur HT, finaler Orbit-Trade 1 Trade, FTMO-/FundedNext-Futures nicht in der Standardliste, Topstep-Haupt an Platz 1 mit der Trade-1-SL-Spanne).

Aufruf:  python3 tools/selftest_ws2_tagesteilung.py
Ohne Netz, Platzhalter-IDs. Prüft: Würfel 80/12/6/2 über 100.000 Würfe, Haupt 70–90 %, Neben 10–25 Pkt mit höchstens halben Haupt-Lots und SL 1–2 × TP,
Zusammenlegen unter 300 $, 1-Trade-Tag bitgleich (Orbit/Echo ohne kette), Topstep-Ein-Trade-Tag, genaue Lesung je Weg, Folge-Teil aus der echten Balance
(Topstep über ap_kette_trade2, Orbit/Echo über ap_konto_rechnen), Stopp bei Ziel/Rest/Verlust, Einstellungen (tt_param/tt_einst_anwenden) und tt_tick
(Folge-Teil anlegen, nie doppelt, Abhaken mit Nachfolger, Tagesende am letzten Teil)."""
import os as _os_mk, sys as _sys_mk
_sys_mk.path.insert(0, _os_mk.path.dirname(_os_mk.path.abspath(__file__)))
import modell_name_test  # noqa: F401 — MODELL_NAME aus app.py für die exec-Ausschnitte
import os
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

APP = os.path.join(HIER, "..", "app.py")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade():
    a = sd.lade()
    src = open(APP, encoding="utf-8").read()
    i = src.index("# ══ WS2 TRADES PRO TAG AUFTEILEN")
    j = src.index("\ndef _ap_bot_tick(", i)
    for name in ("ap_echte_balancen", "ap_blow_lesung_at"):
        k = src.index(f"\ndef {name}(") + 1
        exec(src[k:src.find("\n\n\n", k)], a)
    exec(src[i:j], a)
    return a


TRADEIFY = {"namen": ["tradeify"], "route": "tvv2", "symbol": "NQ", "boden": "nachziehend", "dd_usd": 4500, "groessen": [150000], "ziel_pct": {"challenge": 6},
            "phasen": {"challenge": {"sl": None, "tp": [3450, 3550], "menge": [2, 2.8], "dd_usd": 4500, "tp_max": 3600, "ziel_pct": 6, "menge_schritt": 1,
                                     "puffer_je_menge": {"2": [15, 25], "3": [25, 40]}}}}
TOPSTEP = {"namen": ["topstep"], "route": "tsv2", "symbol": "NQ", "boden": "nachziehend", "dd_usd": 4500, "groessen": [150000],
           "ziel_pct": {"challenge": 6}, "planen": True, "kette": {},
           "phasen": {"challenge": {"sl": None, "tp": [4350, 4450], "menge": [2, 3], "dd_usd": 4500, "tp_max": 4500, "ziel_pct": 6,
                                    "menge_schritt": 1, "puffer_je_menge": {"2": [15, 25], "3": [25, 40]}}}}
CFD = {"namen": ["fundednext"], "route": "mt5v2", "boden": "statisch", "dd_pct": 10, "groessen": [100000], "ziel_pct": {"phase1": 8},
       "phasen": {"phase1": {"sl": [2250, 3150], "tp": [5400, 7200], "menge": [2.1, 3.2], "puffer": [25, 50], "ziel_pct": 8, "boden_pct": 10,
                             "menge_schritt": 0.1}}}
U = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}


def main():
    a = lade()
    P = a["tt_param"]
    std = P({})
    # ── 1 Einstellungen ─────────────────────────────────────────────────────────────────────────────────────────────────
    check(std["an"] is False and std["anteile"] == [80, 12, 6, 2] and std["haupt_pct"] == [70, 90] and std["neben_pkt"] == [10, 25]
          and std["neben_sl_faktor"] == [1, 2] and std["abstand_min"] == [1, 180] and std["schluss_pct"] == [5, 10] and std["schluss_min"] == [2, 120]
          and std["gruppen"] == [] and "fundednextfutures" not in std["firmen"] and "ftmofutures" not in std["firmen"]
          and not any(f.startswith("apex") for f in std["firmen"]), "Standard: aus, 80/12/6/2, 70–90 %, 10–25 Pkt, 1–2×, 1–180 min, nur HT, ohne FTMO-/FN-Futures/Apex")
    kaputt = P({"tagesteilung": {"an": "ja", "anteile": [80, 12, 6, 1], "haupt_pct": [95, 70], "neben_pkt": "x", "min_tp_usd": -5, "test_n": 7,
                                 "nur_konten": ["kein-uuid"], "abstand_min": [5, 30]}})
    check(kaputt["an"] is False and kaputt["anteile"] == std["anteile"] and kaputt["haupt_pct"] == std["haupt_pct"] and kaputt["min_tp_usd"] == 300
          and kaputt["test_n"] is None and kaputt["nur_konten"] == [] and kaputt["abstand_min"] == [5, 30],
          "tt_param: Kaputtes fällt einzeln auf den Standard, Gültiges (abstand 5–30) gilt")
    E = a["tt_einst_anwenden"]
    keys = {"tradeify", "topstep", "fundednext"}
    r, g = E({"firmen": []}, {"anteile": [70, 20, 8, 2], "an": True}, keys)
    check(g is None and r["tagesteilung"]["anteile"] == [70, 20, 8, 2] and r["tagesteilung"]["an"] is True and r["tagesteilung"]["haupt_pct"] == [70, 90],
          "tt_einst_anwenden: legt den Block aus dem Standard an und setzt nur die Felder")
    check(E({}, {"anteile": [80, 12, 6, 0]}, keys) == (None, "anteile: Summe 98 statt 100"), "Anteile ≠ 100 → eine Ursache mit Wert")
    check(E({}, {"haupt_pct": [90, 70]}, keys)[1].startswith("haupt_pct") and E({}, {"firmen": ["apextrader"]}, keys)[1].startswith("firmen")
          and E({}, {"foo": 1}, keys)[1].endswith("nicht änderbar") and E({}, {"test_n": 5}, keys)[1].startswith("test_n")
          and E({}, {"an": 1}, keys)[1].startswith("an"), "tt_einst_anwenden: Grenzen, unbekannte Firma/Feld, test_n, an bool")
    G = a["tt_gilt"]
    pa = dict(std, an=True)
    GID = "00000000-0000-0000-0000-0000000000a1"
    check(G(pa, "tradeify", None, "k1", "challenge") and not G(std, "tradeify", None, "k1", "challenge") and not G(pa, "tradeify", GID, "k1", "challenge")
          and not G(pa, "apextrader", None, "k1", "challenge") and not G(pa, "fundednextfutures", None, "k1", "challenge")
          and not G(pa, "tradeify", None, "k1", "funded") and G(dict(pa, gruppen=[GID]), "tradeify", GID, "k1", "challenge")
          and not G(dict(pa, nur_konten=["00000000-0000-0000-0000-000000000001"]), "tradeify", None, "k1", "challenge"),
          "tt_gilt: Schalter, Firma, HT immer / Unternehmen nur in gruppen, Apex nie, Challenge-Typen, nur_konten")
    check(E({}, {"gruppen": [GID]}, keys, {GID})[0]["tagesteilung"]["gruppen"] == [GID] and E({}, {"gruppen": [GID]}, keys, set())[1].startswith("gruppen")
          and E({}, {"gruppen": ["x"]}, keys, {GID})[1].startswith("gruppen")
          and a["tt_gruppen_auswahl"]([{"id": GID, "name": "Unternehmen B"}], dict(std, gruppen=[GID])) == [{"gruppe_id": GID, "name": "Unternehmen B", "an": True}]
          and P({"tagesteilung": {"gruppen": [GID, "kaputt"]}})["gruppen"] == [GID],
          "gruppen: nur bekannte Unternehmen-IDs, Auswahl mit Häkchen, Kaputtes fällt raus")
    fa = a["tt_firmen_auswahl"]([TRADEIFY, TOPSTEP, CFD, {"namen": ["apextrader"], "route": "tvv2"}], std)
    check([(x["key"], x["art"], x["an"]) for x in fa] == [("tradeify", "futures", True), ("topstep", "topstep", True), ("fundednext", "cfd", True)],
          f"tt_firmen_auswahl: ohne Apex, Art je Weg ({fa})")

    # ── 2 Würfel ───────────────────────────────────────────────────────────────────────────────────────────────────────
    W = a["tt_wuerfeln"]
    rnd = random.Random(7)
    zahl, haupt_ok, summe_ok, platz = {1: 0, 2: 0, 3: 0, 4: 0}, True, True, {}
    N = 100000
    for _ in range(N):
        w = W(std, rnd)
        zahl[w["n"]] += 1
        h = w["anteile"][w["haupt_an"] - 1]
        haupt_ok &= (w["n"] == 1 and h == 1.0) or (0.6999 <= h <= 0.9001 and all(x <= h for x in w["anteile"]))
        summe_ok &= abs(sum(w["anteile"]) - 1) < 0.002 and len(w["anteile"]) == w["n"]
        if w["n"] == 3:
            platz[w["haupt_an"]] = platz.get(w["haupt_an"], 0) + 1
    pct = {n: 100.0 * c / N for n, c in zahl.items()}
    check(all(abs(pct[n] - p) <= 0.5 for n, p in ((1, 80), (2, 12), (3, 6), (4, 2))), f"Würfel über {N} Würfe ≈ 80/12/6/2 ({pct})")
    check(haupt_ok and summe_ok, "Haupt-Anteil 70–90 % und größter Teil, Anteile summieren zu 1")
    check(set(platz) == {1, 2, 3} and min(platz.values()) > 0.28 * sum(platz.values()), f"Haupt-Platz zufällig (3 Trades: {platz})")
    Z = a["tt_zusammenlegen"]
    zl = Z({"n": 3, "haupt_an": 2, "anteile": [0.04, 0.8, 0.16]}, 4500, 300)
    check(zl["n"] == 2 and zl["haupt_an"] == 1 and abs(sum(zl["anteile"]) - 1) < 1e-9, f"Teil unter 300 $ (180 $) wird mit dem nächsten zusammengelegt ({zl})")
    zl = Z({"n": 2, "haupt_an": 1, "anteile": [0.95, 0.05]}, 3000, 300)
    check(zl["n"] == 1 and zl["anteile"] == [1.0], f"letzter kleiner Teil geht in den vorigen ({zl})")

    # ── 3 Neben-Trade ──────────────────────────────────────────────────────────────────────────────────────────────────
    NB = a["tt_neben"]
    ok = True
    for i in range(400):
        rr = random.Random(i)
        tp = rr.uniform(300, 1400)
        for art, pv, hm, sch in (("fut", 20.0, 2, None), ("fut", 20.0, 3, None), ("fut_nq", 20.0, 2, None), ("cfd", 10.0, 2.6, 0.1), ("cfd", 1.0, 25, 1)):
            nb = NB(tp, art, pv, hm, std, rr.random(), rr.random(), schritt=sch, symbol="NQ")
            einheit = 10.0 if art == "fut" else 1.0
            menge_nq = nb["menge"] / einheit if (art == "fut" and nb["symbol"] == "MNQ") else nb["menge"]
            ok &= 10 - 1e-6 <= nb["tp_pkt"] <= 25 + 1e-6 and 1 - 1e-6 <= nb["sl_pkt"] / nb["tp_pkt"] <= 2 + 1e-6
            ok &= menge_nq <= max(hm * 0.5, (0.1 if art == "fut" else sch or 1)) + 1e-9 and nb["menge"] > 0
            ok &= nb["tp"] <= tp + 1 or nb["tp_pkt"] <= 10 + 1e-6
            if not ok:
                print("   ", art, tp, hm, nb)
                break
    check(ok, "Neben: 10–25 Pkt, SL 1–2 × TP-Abstand, höchstens halbe Haupt-Lots, mindestens ein Schritt, TP nie über dem Anteil (außer Mindest-Punkte)")
    nb = NB(300, "fut", 20.0, 2, std, 0.5, 0.5, symbol="NQ")
    check(nb["symbol"] == "MNQ" and nb["menge"] < 10, f"Orbit-Neben unter 1 NQ läuft als MNQ ({nb})")
    nb = NB(500, "fut", 20.0, 2, std, 0.5, 0.5, symbol="NQ")
    check(nb["symbol"] == "NQ" and nb["menge"] == 1, f"10 MNQ (= halbe Haupt-Lots) laufen als 1 NQ ({nb})")
    nb = NB(500, "fut_nq", 20.0, 2, std, 0.5, 0.5, symbol="NQ")
    check(nb["symbol"] == "NQ" and nb["menge"] == 1, f"Topstep-Neben nur NQ, 1 Kontrakt ({nb})")

    # ── 4 Planer-Haken (Trade 1) ───────────────────────────────────────────────────────────────────────────────────────
    R = a["ap_konto_rechnen"]
    H = a["tt_planer_haken"]
    w, _ = R(TRADEIFY, "challenge", 150000.0, U)
    w1 = H(w, TRADEIFY, "challenge", pa, random.Random(1), n_fest=1)
    check(w1 is w and "kette" not in w1, "Orbit 1 Trade: Plan bitgleich zu heute, kein kette-Block")
    w3 = H(w, TRADEIFY, "challenge", pa, random.Random(2), n_fest=3)
    k = w3.get("kette") or {}
    check(k.get("nr") == 1 and k.get("von") in (2, 3) and k.get("rolle") in ("haupt", "neben") and k.get("tagesziel") == w["tp"]
          and abs(sum(k["plan"]["anteile"]) - 1) < 0.002 and w3["stufe"].startswith("Tag 1/"), f"Orbit 3 Trades: Trade 1 trägt kette nr 1/von/plan ({k})")
    for s in range(30):
        wx = H(w, TRADEIFY, "challenge", pa, random.Random(100 + s), n_fest=2)
        kx = wx.get("kette") or {}
        if kx.get("rolle") == "haupt":
            ok_h = wx["menge"] == w["menge"] and wx["sl"] is None and abs(wx["tp"] - w["tp"] * kx["plan"]["anteile"][0]) <= 1
        else:
            ok_n = wx["sl"] and wx["tp"] < w["tp"] * 0.31 and 10 <= kx["tp_pkt"] <= 25
    check(ok_h and ok_n, "Orbit 2 Trades: Haupt mit normalen Lots, ohne SL, TP = Anteil; Neben klein mit eigenem SL")
    wf, _ = R(TRADEIFY, "challenge", 156500.0, U)                       # Rest bis Ziel 2.500 → letzter Trade
    check("letzter Trade" in wf["stufe"] and H(wf, TRADEIFY, "challenge", pa, random.Random(3), n_fest=3) is wf, "finaler Orbit-Trade bleibt 1 Trade")
    wt, _ = R(TOPSTEP, "challenge", 150000.0, U)
    wt1 = H(wt, TOPSTEP, "challenge", pa, random.Random(4), n_fest=1)
    kt = wt1["kette"]
    check(kt["von"] == 1 and kt["rolle"] == "haupt" and wt1["tp"] == kt["tagesziel"] == 4500 and 1250 <= wt1["sl"] <= 1750,
          f"Topstep 1 Trade: TP = Tagesziel 4.500, SL Trade-1-Spanne 1.250–1.750 ({wt1['tp']} / {wt1['sl']})")
    for s in range(40):
        wx = H(wt, TOPSTEP, "challenge", pa, random.Random(200 + s), n_fest=2)
        if wx["kette"]["rolle"] == "haupt":
            break
    check(wx["kette"]["rolle"] == "haupt" and 1250 <= wx["sl"] <= 1750 and 3150 <= wx["tp"] <= 4050,
          f"Topstep Haupt an Platz 1: SL Trade-1-Spanne, TP 70–90 % von 4.500 ({wx['tp']} / {wx['sl']})")
    wc, _ = R(CFD, "phase1", 100000.0, U, ppl=1.0)
    wc2 = H(wc, CFD, "phase1", pa, random.Random(5), ppl=1.0, n_fest=2)
    check(wc2["kette"]["ppl"] == 1.0 and wc2["kette"]["menge_schritt"] == 0.1 and H(wc, CFD, "phase1", pa, random.Random(5), ppl=None, n_fest=2) is wc,
          "CFD: Punktwert/Schritt in der Kette; ohne Punktwert ein Trade")
    zs = [a["tt_zschluss"](std, random.Random(i)) for i in range(20000)]
    treffer = [z for z in zs if z]
    check(0.06 <= len(treffer) / len(zs) <= 0.09 and all(2 <= z["nach_min"] <= 120 for z in treffer), f"Zufalls-Schluss ≈ 7,5 %, 2–120 min ({len(treffer)}/20000)")

    check(all(z.get("topstep") is False and z.get("news_sperre") is True for z in treffer)
          and all(z.get("topstep") is True and z.get("news_sperre") is False
                  for z in filter(None, (a["tt_zschluss"](dict(std, schluss_topstep=True, schluss_news_sperre=False), random.Random(i)) for i in range(500))))
          and std["schluss_topstep"] is False and std["schluss_news_sperre"] is True
          and E({}, {"schluss_topstep": True}, keys)[0]["tagesteilung"]["schluss_topstep"] is True and E({}, {"schluss_news_sperre": "ja"}, keys)[0] is None,
          "Schalter schluss_topstep (aus) / schluss_news_sperre (an): Standard, Schreibweg, Kopie in zschluss")
    # ── 5 Genaue Lesung je Weg ─────────────────────────────────────────────────────────────────────────────────────────
    EC = a["tt_echt"]
    check(EC({"route": "tvv2", "mt5_baseline": {"tv": {"balance_start": 150000}, "final": {"quelle": "puls", "balance_end": 151000}}}) == (150000.0, 151000.0)
          and EC({"route": "tvv2", "mt5_baseline": {"tv": {"balance_start": 150000}, "final": {"quelle": "demo", "balance_end": 151000}}}) is None
          and EC({"route": "tsv2", "mt5_baseline": {"tv": {"balance_start": 150000}, "final": {"quelle": "puls", "balance_end": 151000, "balance_quelle": "folgetrade"}}}) is None
          and EC({"route": "mt5", "mt5_baseline": {"master_balance": 100000, "bal_nach": {"ok": True, "quelle": "nachlesung", "balance": 101000}}}) == (100000.0, 101000.0)
          and EC({"route": "mt5", "mt5_baseline": {"master_balance": 100000, "bal_nach": {"ok": False, "balance": 101000}}}) is None,
          "tt_echt: Orbit nur Puls-Endlesung, nie Folgetrade/Demo; Echo mit Hedge nur Nachlesung ok")

    # ── 6 Folge-Teil ───────────────────────────────────────────────────────────────────────────────────────────────────
    F = a["tt_folge_rechnen"]
    k1 = {"nr": 1, "von": 3, "rolle": "neben", "plan": {"n": 3, "haupt_an": 2, "anteile": [0.12, 0.7, 0.18]}, "tagesziel": 3500, "haupt_menge": 2}
    wh, gh = R(TRADEIFY, "challenge", 150400.0, U)
    v, g = F(k1, 150000.0, 150400.0, TRADEIFY, pa, random.Random(1), w_h=wh, grund_h=gh)
    check(g is None and v["nr"] == 2 and v["rolle"] == "haupt" and v["menge"] == wh["menge"] and v["e_bisher"] == 400
          and v["tp"] == round(3100 * 0.7 / 0.88) and v["sl"] is None and v["risiko"] == wh["risiko"],
          f"Orbit Teil 2 (Haupt): Rest 3.100 × 0,7/0,88 = {round(3100 * 0.7 / 0.88)}, ohne SL, Risiko wie der Planer ({v})")
    v, g = F(dict(k1, plan={"n": 3, "haupt_an": 2, "anteile": [0.12, 0.8, 0.08]}), 150000.0, 150400.0, TRADEIFY, pa, random.Random(1), w_h=wh, grund_h=gh)
    check(g is None and v["plan"]["n"] == 2 and v["tp"] == min(3100, wh["tp"]),
          f"Teil 3 wäre 282 $ < 300 $ → mit dem Haupt-Trade zusammengelegt, Haupt nimmt den Rest ({v and v['plan']})")
    k2 = dict(k1, nr=2, rolle="haupt")
    v, g = F(k2, 150000.0, 153250.0, TRADEIFY, pa, random.Random(1), w_h=wh, grund_h=gh)
    check(v is None and g[0] == "rest_klein", f"letzter Teil mit Rest 250 $ < Mindest-TP 300 $ → Tag fertig ({g})")
    v, g = F(k2, 150000.0, 153480.0, TRADEIFY, pa, random.Random(1), w_h=wh, grund_h=gh)
    check(v is None and g[0] == "ziel", f"Rest ≤ 50 $ → Tagesziel erreicht ({g})")
    v, g = F(k2, 150000.0, 150000.0, TRADEIFY, pa, random.Random(1), w_h=None, grund_h="Balance auf/unter dem Boden — geblowt?")
    check(v is None and g[0] == "verlust", f"Planer-Grund Boden → Verlust-Stopp ({g})")
    v, g = F(k2, 150000.0, 150600.0, TRADEIFY, pa, random.Random(3), w_h=wh, grund_h=gh)
    check(g is None and v["nr"] == 3 and v["rolle"] == "neben" and v["sl"] and 10 <= v["tp_pkt"] <= 25, f"Orbit Teil 3 (Neben, letzter) ({v})")
    v, g = F(dict(k1, nr=3), 150000.0, 150600.0, TRADEIFY, pa, random.Random(3), w_h=wh, grund_h=gh)
    check(v is None and g[0] == "alle", "nach dem letzten Teil: alle Trades gelaufen")
    kt2 = dict(wt1["kette"], von=2, rolle="haupt", plan={"n": 2, "haupt_an": 2, "anteile": [0.2, 0.8]})
    v, g = F(kt2, 150000.0, 149500.0, TOPSTEP, pa, random.Random(1), kette_r=a["ap_kette_regel"](TOPSTEP))
    check(g is None and v["rolle"] == "haupt" and v["tp"] == 5000 and v["sl"] == kt2["verlust_grenze"] - 500,
          f"Topstep Teil 2 Haupt: TP Rest 5.000, SL = Verlustgrenze + E (Restbudget) ({v})")
    v, g = F(kt2, 150000.0, 150000.0 - kt2["verlust_grenze"] + 20, TOPSTEP, pa, random.Random(1), kette_r=a["ap_kette_regel"](TOPSTEP))
    check(v is None and g[0] == "verlust", f"Topstep: Tageslimit fast erreicht → Tag fertig ({g})")

    # ── 7 tt_tick ──────────────────────────────────────────────────────────────────────────────────────────────────────
    BER = ZoneInfo("Europe/Berlin")
    mitt = datetime(2026, 11, 10, tzinfo=BER)
    jetzt = (mitt + timedelta(hours=10, minutes=2)).astimezone(timezone.utc)
    T1 = "00000000-0000-0000-0000-00000000t001"
    t1 = {"id": T1, "user_id": sd.U1, "master_account_id": "k-tf", "master_firm": "Tradeify", "master_name": "TF-000000", "master_symbol": "NQZ6",
          "richtung": "buy", "route": "tvv2", "status": "review", "auto_plan": True, "auto_bestaetigt_at": "2026-11-09T22:00:00Z",
          "ended_at": (mitt + timedelta(hours=9, minutes=55)).isoformat(), "planned_for": "2026-11-10", "konto_typ": "challenge", "updated_at": "u1",
          "mt5_baseline": {"kette": dict(k1), "tv": {"balance_start": 150000}, "final": {"quelle": "puls", "balance_end": 150400, "at": (mitt + timedelta(hours=9, minutes=58)).isoformat()}}}
    db = {"plaene": [t1], "ins": [], "upd": [], "patch": []}
    REG = {"id": 1, "zeiten": {"tz": "Europe/Berlin", "fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30"},
           "regeln": {"firmen": [TRADEIFY], "ausgleich": {"laufzeit_min": 180}, "tagesteilung": dict(std, an=True)}}

    def sb_select(table, params):
        if table == "auto_plan_regeln":
            return [REG]
        if table == "accounts":
            return [{"id": "k-tf", "user_id": sd.U1, "firm": db.get("firm", "Tradeify"), "account_type": db.get("typ", "challenge"), "account_size": 150000}]
        if table == "trade_plans" and "mt5_baseline->kette->>von" in params:
            return [dict(x) for x in db["plaene"]]
        if table == "trade_plans" and "mt5_baseline->kette->>vor" in params:
            want = params["mt5_baseline->kette->>vor"]
            return [{"id": "n", "status": "planned", "vor": z["mt5_baseline"]["kette"]["vor"]} for z in db["ins"]
                    if want.startswith("in.") or want == "eq." + z["mt5_baseline"]["kette"]["vor"]]
        if table == "trade_plans" and "mt5_baseline->kette->>tag_id" in params:
            return []
        if table == "trade_plans" and params.get("id"):
            return [dict(x) for x in db["plaene"] if "eq." + x["id"] == params["id"]]
        return []

    def stand(reg, uid, j=None, **k_):
        return {"mitternacht": mitt, "jetzt_min": (j - mitt).total_seconds() / 60.0, "zeiten": reg["zeiten"], "offen": [], "geplant": [], "folgetag": [],
                "starts_heute": [], "id_fest": {}, "firmen": [TRADEIFY]}
    a.update(sb_select=sb_select, sb_insert=lambda t, z: db["ins"].append(z) or z, sb_update=lambda t, f, u: db["upd"].append((f, u)) or [u],
             _ap_stand_fuer_uid=stand, _ap_sperren=lambda: set(), requests=__import__("requests"),
             _tt_patch=lambda pid, patch, key="kette": db["patch"].append((pid, patch)) or True,
             ap_regel_unternehmen=lambda uid, firmen, firm, **k_: a["ap_regel_finden"](firmen, firm))
    a.setdefault("_firm_norm", lambda n: str(n or ""))
    erg = a["tt_tick"](jetzt, random.Random(11))
    z = db["ins"][0] if db["ins"] else {}
    kz = (z.get("mt5_baseline") or {}).get("kette") or {}
    st = datetime.fromisoformat(z["start_um"]).astimezone(BER) if z else None
    check(len(db["ins"]) == 1 and kz.get("nr") == 2 and kz.get("von") == 3 and kz.get("vor") == T1 and kz.get("tag_id") == T1
          and kz.get("rolle") == "haupt" and kz.get("e_bisher") == 400 and z["master_sl"] is None and z["master_risk"] and kz.get("balance_start_tag") == 150000 and z["route"] == "tvv2",
          f"tt_tick: Teil 2 angelegt (nr 2/3, vor/tag_id = Trade 1, bisher +400) ({erg})")
    check(st is not None and st >= mitt + timedelta(hours=9, minutes=59) and st.hour * 60 + st.minute <= 16 * 60 + 30
          and bool(z.get("auto_bestaetigt_at")) and z["notes"].startswith("Auto-Planer · Tag 2/3 · Haupt"),
          f"Start nach der Lesung + Abstand, im Fenster, Bestätigung geerbt ({st and st.strftime('%H:%M')})")
    a["tt_tick"](jetzt, random.Random(12))
    check(len(db["ins"]) == 1, "zweiter Takt: nie doppelt")
    check(any(f.get("id") == f"eq.{T1}" and u.get("status") == "completed" and u.get("master_pl") == 400 for f, u in db["upd"]),
          "Trade 1 mit Nachfolger: automatisch abgehakt, P&L aus der genauen Lesung")
    t3 = dict(t1, id="00000000-0000-0000-0000-00000000t003", master_pl=None,
              mt5_baseline={"kette": dict(k1, nr=3, rolle="neben", tag_id=T1, vor="x", balance_start_tag=150000), "tv": {"balance_start": 153000},
                            "final": {"quelle": "puls", "balance_end": 153450}})
    db.update(plaene=[t3], ins=[], upd=[], patch=[])
    a["tt_tick"](jetzt, random.Random(13))
    te = next((p["tagesende"] for pid, p in db["patch"] if p.get("tagesende")), None)
    check(not db["ins"] and te and te["ende_grund"] == "alle" and te["tag_pl"] == 3450 and te["balance"] == 153450
          and any(u.get("master_pl") == 450 and "status" not in u for _f, u in db["upd"]),
          f"letzter Teil: Tagesende (alle, Tag +3.450), P&L eingetragen, bleibt in Überprüfen ({te})")
    t_ohne = dict(t1, mt5_baseline=dict(t1["mt5_baseline"], final={"quelle": "demo"}))
    db.update(plaene=[t_ohne], ins=[], upd=[], patch=[])
    a["tt_tick"](jetzt, random.Random(14))
    check(not db["ins"] and any(p.get("lesen_bis") for _pid, p in db["patch"]) and not any(p.get("tagesende") for _pid, p in db["patch"]),
          "ohne genaue Lesung: lesen_bis geschrieben, kein Teil, kein Tagesende")
    a["tt_tick"]((mitt + timedelta(hours=17)).astimezone(timezone.utc), random.Random(14))
    check(any((p.get("tagesende") or {}).get("ende_grund") == "keine_lesung" for _pid, p in db["patch"]), "nach Fensterende ohne Lesung: Tag fertig (keine_lesung)")
    REG["regeln"]["tagesteilung"]["an"] = False
    db.update(plaene=[t1], ins=[], upd=[], patch=[])
    a["tt_tick"](jetzt, random.Random(15))
    check(not db["ins"] and any((p.get("tagesende") or {}).get("ende_grund") == "aus" for _pid, p in db["patch"]), "Tagesteilung aus: laufende Kette endet nach dem Teil")
    REG["regeln"]["tagesteilung"]["an"] = True
    db.update(plaene=[dict(t1, mt5_baseline=dict(t1["mt5_baseline"], zschluss={"nach_min": 30, "status": "geschlossen"}))], ins=[], upd=[], patch=[])
    a["tt_tick"](jetzt, random.Random(16))
    check(not db["ins"] and any((p.get("tagesende") or {}).get("ende_grund") == "zschluss" for _pid, p in db["patch"]), "Zufalls-Schluss geschlossen: Tag fertig")
    for st_ in ("war_flach", "fehler"):
        db.update(plaene=[dict(t1, mt5_baseline=dict(t1["mt5_baseline"], zschluss={"nach_min": 30, "status": st_}))], ins=[], upd=[], patch=[])
        a["tt_tick"](jetzt, random.Random(16))
        check(not db["ins"] and any((p.get("tagesende") or {}).get("ende_grund") == "zschluss" for _pid, p in db["patch"]), f"Zufalls-Schluss {st_}: kein Folge-Teil")

    # ── 7b Gegenprüfung 09.11.2026 ─────────────────────────────────────────────────────────────────────────────────────
    t1m = dict(t1, master_symbol="MNQZ6", mt5_baseline=dict(t1["mt5_baseline"], kette=dict(k1)))
    db.update(plaene=[t1m], ins=[], upd=[], patch=[])
    a["tt_tick"](jetzt, random.Random(11))
    zm = db["ins"][0] if db["ins"] else {}
    check(zm.get("master_symbol") == "NQZ6" and (zm.get("mt5_baseline") or {}).get("kette", {}).get("rolle") == "haupt",
          f"Haupt nach einem MNQ-Neben läuft wieder auf NQ, Frontmonat bleibt ({zm.get('master_symbol')})")
    check(any(p.get("folge_id") for _pid, p in db["patch"]), "nach dem Anlegen steht folge_id am Vorgänger")
    db.update(plaene=[dict(t1, mt5_baseline=dict(t1["mt5_baseline"], kette=dict(k1, folge_id="x")))], ins=[], upd=[], patch=[])
    a["tt_tick"](jetzt, random.Random(17))
    check(not db["ins"] and any((p.get("tagesende") or {}).get("ende_grund") == "geloescht" for _pid, p in db["patch"]),
          "Folge-Trade gelöscht → Tag fertig, nie still neu anlegen")
    ok_b = a["tt_bal_wache_ok"]
    check(ok_b({"nr": 1, "von": 3}) and not ok_b({"nr": 2, "von": 3}) and not ok_b({"nr": 1, "von": 2, "verlust_grenze": 2775}) and not ok_b({"nr": 1})
          and not ok_b(None), "Balance-Wache: nur Trade 1 eines Orbit-/Echo-Tags, nie Topstep oder Folge-Teile")
    nb = NB(1400, "fut", 20.0, 2, std, 0.0, 0.5, symbol="NQ")
    check(nb["tp_pkt"] == 25 and nb["tp"] == 500, f"Neben am Lots-Deckel: TP auf neben_pkt.hi gekürzt ({nb})")
    v, g = F(dict(k1, nr=1, rolle="neben", plan={"n": 3, "haupt_an": 3, "anteile": [0.1, 0.1, 0.8]}), 150000.0, 150300.0, TRADEIFY, pa,
             random.Random(1), w_h=wh, grund_h=gh)
    check(g is None and v["rolle"] == "neben" and v["symbol"] in ("NQ", "MNQ"), f"Neben-Futures trägt sein Symbol immer ({v and v['symbol']})")
    # Echo: ohne Hedge-Kandidat nie Echo V2 als Ersatz
    CFDR = dict(CFD, namen=["fundednext"])
    tc = dict(t1, route="mt5", master_firm="FundedNext", master_symbol=None, konto_typ="phase1",
              mt5_baseline={"kette": dict(k1, ppl=1.0, menge_schritt=0.1, tagesziel=6000, haupt_menge=2.6), "master_balance": 100000,
                            "bal_nach": {"ok": True, "quelle": "nachlesung", "balance": 100500, "at": t1["mt5_baseline"]["final"]["at"]}})
    REG["regeln"]["firmen"] = [TRADEIFY, CFDR]
    a["ap_echo_hedge_anlegen"] = lambda zeilen, konten, regeln: {"echo": 0, "weg": []}
    db.update(plaene=[tc], ins=[], upd=[], patch=[], firm="FundedNext", typ="phase1")
    a["tt_tick"](jetzt, random.Random(18))
    check(not db["ins"] and any((p.get("tagesende") or {}).get("ende_grund") == "kein_hedge" for _pid, p in db["patch"]),
          "Echo-Teil ohne stellbaren Hedge → kein Echo V2, Tag fertig (kein_hedge)")
    a["ap_echo_hedge_anlegen"] = lambda zeilen, konten, regeln: (zeilen[0].update(route="mt5") or {"echo": 1, "weg": []})
    db.update(plaene=[tc], ins=[], upd=[], patch=[])
    a["tt_tick"](jetzt, random.Random(18))
    check(len(db["ins"]) == 1 and db["ins"][0]["route"] == "mt5" and not any(u.get("status") for _f, u in db["upd"]),
          "Echo-Teil mit Hedge angelegt; der Vorgänger mit Hedge bleibt bei Finn (kein Auto-Abhaken)")
    REG["regeln"]["firmen"] = [TRADEIFY]
    db.update(firm="Tradeify", typ="challenge")
    # Topstep-Blow wie ap_kette_abhaken: gesund am MLL ohne Tagesverlust über DLL + 50 → nicht geblowt
    kts = dict(kt, nr=2, von=2, rolle="haupt", balance_start_tag=150000, mll=147800.0, daily_usd=3000, dll_puffer=225, angefressen=False, tag_id="t")
    ts = dict(t1, route="tsv2", master_firm="Topstep", mt5_baseline={"kette": kts, "tv": {"balance_start": 149000},
              "final": {"quelle": "puls", "plattform": "tsx", "balance_end": 147790}})
    REG["regeln"]["firmen"] = [TRADEIFY, TOPSTEP]
    db.update(plaene=[ts], ins=[], upd=[], patch=[])
    a["tt_tick"](jetzt, random.Random(19))
    te = next((p["tagesende"] for _pid, p in db["patch"] if p.get("tagesende")), {})
    check(te.get("blown") is False and not any(u.get("blown") for _f, u in db["upd"]),
          f"Topstep gesund: Ende unter dem gerechneten MLL, Tagesverlust −2.210 < DLL + 50 → nicht geblowt ({te.get('blown')})")
    db.update(plaene=[dict(ts, mt5_baseline=dict(ts["mt5_baseline"], final={"quelle": "puls", "plattform": "tsx", "balance_end": 146900}))],
              ins=[], upd=[], patch=[])
    a["tt_tick"](jetzt, random.Random(19))
    te = next((p["tagesende"] for _pid, p in db["patch"] if p.get("tagesende")), {})
    check(te.get("blown") is True, "Topstep gesund: Ende unter dem MLL und Tagesverlust −3.100 > DLL + 50 → geblowt")
    REG["regeln"]["firmen"] = [TRADEIFY]

    # ── 8 Alte Wege lassen WS2-Ketten aus ──────────────────────────────────────────────────────────────────────────────
    src = open(APP, encoding="utf-8").read()
    check('not ((p.get("mt5_baseline") or {}).get("kette") or {}).get("von")]   # WS2-Ketten: tt_tick' in src
          and '.get("von"):\n            continue                                  # WS2-Kette (09.11.2026): Abhaken und Tagesende macht tt_tick' in src,
          "ap_kette_tick und ap_kette_abhaken lassen Pläne mit kette.von aus")
    check("WS2-Kette (09.11.2026): Teile hakt tt_tick ab" in src and "_tt_takt()" in src and '"tagesteilung": sicher(tt_param)' in src
          and 'body.get("tagesteilung") is not None' in src, "Normal-Auto-Abhaken lässt Ketten aus; Takt in ap_loop; Einstellungen lesen/schreiben")

    print(f"\n{'selftest_ws2_tagesteilung: alle Prüfungen grün' if not FEHLER else f'✗ {len(FEHLER)} Fehler'}")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
