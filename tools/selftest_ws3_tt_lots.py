#!/usr/bin/env python3
"""Selbsttest WS3 (10.11.2026, Master; Finn: „Wenn der zweite Trade 6 % vom gesamten Take Profit ausmacht, dann soll er nur 6 % von den Lots vom ersten
kaufen.“): Neben-Teile der Tagesteilung (app.py tt_teil, tt_sl_pkt, tt_planer_haken, tt_folge_rechnen). Lots = Haupt-Lots × Anteil (lots_bezug
„tagesziel“) bzw. × Anteil ÷ Haupt-Anteil („haupt“), × Lots-Würfel neben_lots_streu (WS3d, Standard 0,7–1,3), Lot-Schritt, Mindest-Lot mit Vermerk;
TP-/SL-Punkte = Haupt ÷ Teiler (WS3b/c, gewürfelt 3–5, derselbe für TP und SL), TP höchstens Rest bis Ziel. Übernommen auf origin/main mit TT1 (11.11.2026).
Zahlen des The5%ers-Tests vom 10.11. (Tagesziel 11.193 $, 76/8/8/8, Haupt 53 Lot, SL 3.824 $, 1 $/Pkt/Lot, Schritt 1). Ohne Netz.
Aufruf: python3 tools/selftest_ws3_tt_lots.py"""
import os
import random
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_ws2_tagesteilung as ws2  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


a = ws2.lade()
P, T, SP = a["tt_param"], a["tt_teil"], a["tt_sl_pkt"]
std0 = P({})
std = P({"tagesteilung": {"neben_tp_teiler": 4, "neben_lots_streu": 1}})          # fester Teiler 4, ohne Lots-Streuung für die genauen Beispielzahlen
hp = P({"tagesteilung": {"lots_bezug": "haupt", "neben_tp_teiler": 4, "neben_lots_streu": 1}})
check(std0["lots_bezug"] == "tagesziel" and hp["lots_bezug"] == "haupt" and P({"tagesteilung": {"lots_bezug": "x"}})["lots_bezug"] == "tagesziel",
      "lots_bezug: Standard „tagesziel“ (Finns Formel), „haupt“ wählbar, Unsinn → Standard")
neu, g = a["tt_einst_anwenden"]({}, {"lots_bezug": "haupt"})
check(neu["tagesteilung"]["lots_bezug"] == "haupt" and a["tt_einst_anwenden"]({}, {"lots_bezug": 1})[1] == "lots_bezug = tagesziel | haupt",
      "Einstellung schreibbar, falscher Wert mit Grund")

print("1) Beispiel The5%ers 10.11. (Tagesziel 11.193 $, Haupt 76 %, 53 Lot, SL 3.824 $, Teiler 4)")
Z, H, LH, SLH = 11193.0, 0.76, 53, 3824.0
TPH = a["tt_tp_pkt_haupt"](Z, H, LH, 1.0)
slp = SP(SLH, LH, "cfd", 1.0)
check(abs(TPH - 160.51) < 0.01 and abs(slp - 72.15) < 0.01, f"Haupt: TP {TPH:.2f} Pkt (8.507 $ ÷ 53), SL {slp:.2f} Pkt")
check(std0["neben_tp_teiler"] == [3.0, 5.0] and std["neben_tp_teiler"] == [4.0, 4.0] and P({"tagesteilung": {"neben_tp_teiler": [2, 6]}})["neben_tp_teiler"] == [2.0, 6.0]
      and P({"tagesteilung": {"neben_tp_teiler": 0.5}})["neben_tp_teiler"] == [3.0, 5.0] and P({"tagesteilung": {"neben_tp_teiler": [5, 3]}})["neben_tp_teiler"] == [3.0, 5.0],
      "neben_tp_teiler: Standard Spanne 3–5, einzelner Wert = fest, 1–20, Unsinn → Standard")
ns, _ = a["tt_einst_anwenden"]({}, {"neben_tp_teiler": 4})
check(ns["tagesteilung"]["neben_tp_teiler"] == [4.0, 4.0] and a["tt_einst_anwenden"]({}, {"neben_tp_teiler": [6, 3]})[0] is None, "Einstellung: Zahl = fest, Spanne geprüft")
lo_ = T(0.08, H, "cfd", 1.0, LH, TPH, slp, std0, 0.0, 0.5, schritt=1)
hi_ = T(0.08, H, "cfd", 1.0, LH, TPH, slp, std0, 1.0, 0.5, schritt=1)
check(lo_["teiler"] == 3.0 and hi_["teiler"] == 5.0 and abs(lo_["tp"] - 214.0) < 0.02 and abs(hi_["tp"] - 128.4) < 0.02 and abs(lo_["tp_pkt"] / lo_["sl_pkt"] - hi_["tp_pkt"] / hi_["sl_pkt"]) < 0.05,
      f"Teiler gewürfelt 3–5: TP 53,5–32,1 Pkt (214–128 $ bei 4 Lot), SL mit demselben Teiler ({lo_['tp']}/{hi_['tp']} $, SL {lo_['sl']}/{hi_['sl']} $)")
ws = {round(T(0.08, H, "cfd", 1.0, LH, TPH, slp, std0, random.Random(i).random(), 0.5, schritt=1)["teiler"], 1) for i in range(200)}
check(min(ws) >= 3.0 and max(ws) <= 5.0 and len(ws) > 10, "Teiler gleichverteilt in [3, 5]")
nb = T(0.08, H, "cfd", 1.0, LH, TPH, slp, std, 0.5, 0.5, schritt=1)
check(nb["menge"] == 4 and abs(nb["tp"] - 160.5) < 0.02 and abs(nb["tp_pkt"] - 40.13) < 0.02 and nb["sl"] == 72.15 and nb["sl_pkt"] == 18.04 and nb["lots_roh"] == 4.24
      and not nb["aufgerundet"] and nb["teiler"] == 4.0, f"Neben 8 %: 4 Lot (53 × 8 % = 4,24), TP 40 Pkt ≈ 161 $, SL 18 Pkt = 72 $ ({nb})")
check(abs(nb["tp_pkt"] / nb["sl_pkt"] - TPH / slp) < 0.02, "TP:SL wie beim Haupt-Trade")
nb12 = T(0.12, H, "cfd", 1.0, LH, TPH, slp, std, 0.5, 0.5, schritt=1)
check(nb12["menge"] == 6 and nb12["tp"] == 240.76 and nb12["sl"] == 108.23, f"Neben 12 %: 6 Lot, TP 241 $, SL 108 $ ({nb12})")
nbh = T(0.08, H, "cfd", 1.0, LH, TPH, slp, hp, 0.5, 0.5, schritt=1)
check(nbh["menge"] == 6 and nbh["tp"] == 240.76, f"Variante „haupt“: 53 × 8/76 = 5,58 → 6 Lot, gleiche Punkte ({nbh})")
nb2 = T(0.02, H, "cfd", 1.0, LH, TPH, slp, std, 0.5, 0.5, schritt=1)
check(nb2["menge"] == 1 and nb2["lots_roh"] == 1.06 and not nb2["aufgerundet"] and nb2["tp"] == 40.13, f"Neben 2 %: 1 Lot, TP 40 $ ({nb2})")
nb3 = T(0.005, H, "cfd", 1.0, LH, TPH, slp, std, 0.5, 0.5, schritt=1)
check(nb3["menge"] == 1 and nb3["aufgerundet"], f"Neben 0,5 %: 0,27 Lot → Mindest-Lot 1, Vermerk ({nb3})")
check(T(0.1, 0.8, "cfd", 10.0, 2.6, 40, None, std, 0.5, 0.5, schritt=0.1)["menge"] == 0.3, "CFD mit Schritt 0,1: 2,6 × 10 % = 0,26 → 0,3")
check(T(0.01, 0.8, "cfd", 10.0, 2.6, 40, None, std, 0.5, 0.5, schritt=0.1)["menge"] == 0.1, "CFD unter dem Schritt → kleinstes Lot 0,1")
cap = T(0.08, H, "cfd", 1.0, LH, TPH, slp, std, 0.5, 0.5, schritt=1, tp_max_usd=100)
check(cap["tp"] == 100.0 and cap["tp_pkt"] == 25.0 and cap["sl"] == 72.15, f"Rest bis Ziel 100 $ < 161 $ → TP 100 $, SL bleibt ({cap})")

z = T(0.01, 0.8, "cfd", 1.0, 1.0, 150.0, 150.0, std, 0.5, 0.5, schritt=0.01)
check(z["menge"] == 0.01 and z["sl"] == 0.38 and z["tp"] == 0.38, f"Prüfer S2: 0,01 Lot × 37,5 Pkt = 0,38 $ (auf Cent, nie 0 $) ({z})")

print("2) Futures")
o = T(0.12, 0.8, "fut", 20.0, 3, 60.0, None, std, 0.5, 0.0, symbol="NQ")
check(o["symbol"] == "MNQ" and o["menge"] == 4 and o["tp_pkt"] == 15.0 and o["tp"] == 120 and o["sl_pkt"] == 15.0,
      f"Orbit: 3 NQ × 12 % = 0,36 → 4 MNQ, TP 60 ÷ 4 = 15 Pkt = 120 $, ohne Haupt-SL Faktor 1 × TP ({o})")
o = T(0.34, 0.66, "fut", 20.0, 3, 60.0, None, std, 0.5, 0.5, symbol="NQ")
check(o["symbol"] == "NQ" and o["menge"] == 1 and o["tp"] == 300, f"Orbit: 3 × 34 % = 1,02 → 10 MNQ = 1 NQ, 15 Pkt = 300 $ ({o})")
o = T(0.02, 0.8, "fut", 20.0, 2, 60.0, None, std, 0.5, 0.5, symbol="NQ")
check(o["symbol"] == "MNQ" and o["menge"] == 1 and o["aufgerundet"], f"Orbit: 2 × 2 % = 0,04 NQ = 0,4 MNQ → Mindest 1 MNQ, Vermerk ({o})")
t = T(0.2, 0.8, "fut_nq", 20.0, 3, 75.0, SP(1500, 3, "fut_nq", 20.0), std, 0.5, 0.5, symbol="NQ")
check(t["symbol"] == "NQ" and t["menge"] == 1 and t["tp_pkt"] == 18.75 and t["sl_pkt"] == 10.0 and t["sl"] == 200,
      f"Topstep: 3 × 20 % = 0,6 → 1 NQ, TP 75 ÷ 4, SL 25 ÷ 4 = 6,25 → Mindest 10 Pkt (WS3c) ({t})")
check(SP(300, 15, "fut", 20.0, "MNQ") == 10.0 and SP(None, 3, "fut", 20.0) is None and SP(100, 0, "cfd", 1.0) is None, "SL-Punkte: MNQ mit 2 $/Pkt, ohne SL None")
check(T(0, 0.8, "cfd", 1, 10, 40, None, std, 0.5, 0.5) is None and T(0.1, 0.8, "cfd", 0, 10, 40, None, std, 0.5, 0.5) is None
      and T(0.1, 0, "cfd", 1, 10, 40, None, hp, 0.5, 0.5) is None and T(0.1, 0.8, "cfd", 1, 10, None, None, std, 0.5, 0.5) is None,
      "ohne Anteil/Punktwert/Haupt-TP bzw. ohne Haupt-Anteil (Variante haupt) → None")

print("2b) WS3c: Deckel Haupt-Lots, Mindest-Punkte, Lot-Schritt")
gr = P({"tagesteilung": {"neben_tp_teiler": 4, "neben_lots_streu": 3, "lots_bezug": "haupt"}})
d = T(0.3, 0.6, "cfd", 1.0, 10, 160.0, 72.0, gr, 0.5, 0.5, schritt=1, u_l=0.5)
check(d["menge"] == 10 and d["gedeckelt"] and d["lots_roh"] == 10, f"Lots nie über den Haupt-Lots: 10 × 0,3/0,6 × 3 = 15 → 10, Vermerk gedeckelt ({d})")
o = T(0.9, 0.1, "fut", 20.0, 2, 60.0, None, gr, 0.5, 0.5, symbol="NQ", u_l=0.5)
check(o["menge"] == 2 and o["symbol"] == "NQ" and o["gedeckelt"], f"Orbit: Deckel in NQ (2 NQ, nicht 20 MNQ) ({o})")
check(T(0.01, 0.8, "fut_nq", 20.0, 0.5, 75.0, None, std, 0.5, 0.5, symbol="NQ") is None, "Mindest-Lot (1 NQ) größer als der Haupt-Trade → kein Neben-Trade")
check(std0["neben_min_pkt"] == 10.0 and P({"tagesteilung": {"neben_min_pkt": 5}})["neben_min_pkt"] == 5.0 and P({"tagesteilung": {"neben_min_pkt": 0}})["neben_min_pkt"] == 10.0
      and a["tt_einst_anwenden"]({}, {"neben_min_pkt": 12})[0]["tagesteilung"]["neben_min_pkt"] == 12 and a["tt_einst_anwenden"]({}, {"neben_min_pkt": 0})[0] is None,
      "neben_min_pkt: Standard 10 Pkt, 1–100, Unsinn → Standard, Schreibweg prüft")
e = T(0.08, H, "cfd", 1.0, LH, 30.0, 12.0, std, 0.5, 0.5, schritt=1)
check(e["tp_pkt"] == 10.0 and e["sl_pkt"] == 10.0 and e["tp"] == 40.0, f"Haupt 30/12 Pkt ÷ 4 = 7,5/3 Pkt → beide auf Mindest 10 Pkt ({e})")
zk = T(0.08, H, "cfd", 1.0, LH, TPH, slp, std, 0.5, 0.5, schritt=1, tp_max_usd=30)
check(zk and zk.get("zu_eng") and "Mindest 10 Pkt" in zk["grund"], f"Rest bis Ziel 30 $ bei 4 Lot = 7,5 Pkt → kein Neben-Trade (zu_eng) ({zk})")
_kg = [T(0.08, 0.8, "cfd", 0.85, x / 100, 40.0, 30.0, std, 0.5, 0.5, schritt=0.01) for x in range(10, 300)]
check(not any(x and x.get("zu_eng") for x in _kg), "ppl 0,85 / Schritt 0,01: Cent-Rundung allein ist nie „zu eng“ (Prüfer WS3c)")
check(T(0.1, 0.8, "cfd", 10.0, 26, 40, None, std, 0.5, 0.5, schritt=None)["menge"] == 3, "CFD ohne Lot-Schritt → Schritt 1 wie beim Haupt (26 × 10 % = 2,6 → 3)")

print("3) Planer-Haken und Folge-Teil")
CFD5 = {"namen": ["the5ers"], "route": "mt5", "boden": "statisch", "dd_pct": 10, "groessen": [200000], "ziel_pct": {"phase1": 8},
        "phasen": {"phase1": {"sl": [3500, 4000], "tp": [8000, 9000], "menge": [50, 56], "puffer": [25, 50], "ziel_pct": 8, "boden_pct": 10, "menge_schritt": 1}}}
w = {"menge": 53, "tp": 11193, "sl": 3824, "risiko": 3824, "stufe": "Etappe", "rest": 21096, "puffer": 30}
ok_n = ok_h = False
for sd in range(60):
    w1 = a["tt_planer_haken"](dict(w), CFD5, "phase1", std0, random.Random(sd), ppl=1.0, n_fest=4)   # Standard: Teiler 3–5 + Streuung 0,7–1,3
    k = w1.get("kette") or {}
    a1 = k.get("plan", {}).get("anteile", [0])[0]
    if k.get("rolle") == "neben":
        ah = k["plan"]["anteile"][k["plan"]["haupt_an"] - 1]
        st, te = k["lots_streu"], k["tp_teiler"]
        m1 = max(1, round(53 * a1 * st))
        ok_n = (0.7 <= st <= 1.3 and 3.0 <= te <= 5.0 and w1["menge"] == m1 and abs(w1["tp"] - 11193 * ah / 53 / te * m1) < 0.02
                and abs(w1["sl"] - 3824 / 53 / te * m1) < 0.02 and k["lots_roh"] == round(53 * a1 * st, 4) and k["lots_bezug"] == "tagesziel"
                and " Lot" in w1["stufe"])
    elif k.get("rolle") == "haupt":
        ok_h = w1["menge"] == 53 and w1["tp"] == round(11193 * a1) and w1["sl"] == 3824
check(ok_n and ok_h, "Trade 1: Haupt unverändert; Neben = 53 × Anteil × Streuung Lot, TP-/SL-Punkte = Haupt ÷ Teiler, beide Würfe in kette")
st_w = {a["tt_planer_haken"](dict(w), CFD5, "phase1", std0, random.Random(sd), ppl=1.0, n_fest=2).get("kette", {}).get("lots_streu") for sd in range(80)} - {None}
check(len(st_w) > 10 and min(st_w) >= 0.7 and max(st_w) <= 1.3, f"Lots-Streuung gewürfelt in [0,7, 1,3] ({len(st_w)} Werte)")
check(std0["neben_lots_streu"] == [0.7, 1.3] and P({"tagesteilung": {"neben_lots_streu": 1}})["neben_lots_streu"] == [1.0, 1.0]
      and P({"tagesteilung": {"neben_lots_streu": [0.05, 1]}})["neben_lots_streu"] == [0.7, 1.3]
      and a["tt_einst_anwenden"]({}, {"neben_lots_streu": [0.8, 1.2]})[0]["tagesteilung"]["neben_lots_streu"] == [0.8, 1.2]
      and a["tt_einst_anwenden"]({}, {"neben_lots_streu": [1.3, 0.7]})[0] is None,
      "neben_lots_streu: Standard 0,7–1,3, einzelner Wert = fest, 0,1–3, Unsinn → Standard, Schreibweg prüft")
k1 = {"nr": 1, "von": 4, "rolle": "haupt", "plan": {"n": 4, "haupt_an": 1, "anteile": [0.76, 0.08, 0.08, 0.08]}, "tagesziel": 11193, "haupt_menge": 53,
      "ppl": 1, "menge_schritt": 1}
wh = {"menge": 52, "tp": 9000, "sl": 3800, "risiko": 3800}
v, g = a["tt_folge_rechnen"](k1, 194903.91, 190986.15, CFD5, std, random.Random(1), w_h=wh, grund_h=None)
check(g is None and v["rolle"] == "neben" and v["menge"] == 4 and v["tp"] == 160.5 and abs(v["sl"] - 3800 / 52 / 4 * 4) < 0.01 and v["lots_roh"] == 4.24
      and v["lots_streu"] == 1.0 and v["tp_teiler"] == 4.0,
      f"Folge-Teil 2 nach Haupt −3.918 $: 4 Lot, TP 161 $ (40 Pkt), SL-Punkte = Haupt bei jetziger Balance ÷ 4 ({v})")
v, g = a["tt_folge_rechnen"](dict(k1, nr=3), 194903.91, 194903.91 + 11193 - 120, CFD5, std, random.Random(1), w_h=wh, grund_h=None)
check(v is None and g[0] == "rest_klein", f"Rest 120 $ unter dem Mindest-TP 300 $ → Tag fertig wie bisher ({g})")
v, g = a["tt_folge_rechnen"](dict(k1, nr=3), 194903.91, 194903.91 + 11193 - 350, CFD5, std, random.Random(1), w_h=wh, grund_h=None)
check(g is None and v["tp"] == 160.5 and v["nr"] == 4, f"Teil 4 mit Rest 350 $: TP 161 $ (Teiler, nicht Rest) ({v and v['tp']})")
z = a["_tt_zeile"]({"id": "p1", "user_id": "u", "master_account_id": "k", "route": "mt5", "master_symbol": None},
                   k1, dict(v, nr=4), ws2.datetime(2026, 11, 10, 10, tzinfo=ws2.timezone.utc), "buy", "t", (1.0, 194903.91 + 10800), 194903.91, std,
                   random.Random(1), ws2.datetime(2026, 11, 10, 9, tzinfo=ws2.timezone.utc))
kz = z["mt5_baseline"]["kette"]
check(z["master_contracts"] == v["menge"] and kz["lots_roh"] == v["lots_roh"] and kz["lots_bezug"] == "tagesziel" and "Neben 8 % · " in z["notes"],
      f"Folge-Zeile trägt Lots-Beleg und Anteil in der Notiz ({z['notes'][:80]})")

k4 = dict(k1, plan={"n": 4, "haupt_an": 1, "anteile": [0.92, 0.04, 0.02, 0.02]})
v, g = a["tt_folge_rechnen"](k4, 194903.91, 190986.15, CFD5, std, random.Random(1), w_h=wh, grund_h=None)
check(g is None and v["sl"] < 50 and v["menge"] == 2, f"Prüfer M1: natürlich kleiner Neben-SL ({v and v['sl']} $) beendet den Tag nicht")
# Prüfer WS3 MUSS: TP-Deckel des Haupt-Trades (Rest bis Konto-Ziel) gilt auch für Neben-Teile
v, g = a["tt_folge_rechnen"](k1, 194903.91, 190986.15, CFD5, std, random.Random(1), w_h=dict(wh, tp=150), grund_h=None)
check(g is None and v["rolle"] == "neben" and v["tp"] <= 150, f"Folge-Neben: TP höchstens der Haupt-TP-Deckel 150 $ (Rest bis Konto-Ziel) ({v and v['tp']})")
w1c = a["tt_planer_haken"](dict(w, tp=11193), CFD5, "phase1", P({"tagesteilung": {"neben_tp_teiler": 1, "neben_lots_streu": 3, "lots_bezug": "haupt"}}),
                           random.Random(5), ppl=1.0, n_fest=2)
check(w1c["tp"] <= 11193, f"Trade 1 als Neben mit Teiler 1 / Streuung 3: TP nie über den Ein-Trade-TP ({w1c['tp']})")
check("Auto-Planer · Tag 4/4" in z["notes"] and __import__("re").search(r"→ TP \d+ \$ / SL \d+ \$ ·", z["notes"]) is not None, f"Notiz ganzzahlig ({z['notes'][:90]})")
# WS3c: Folge-Neben mit zu kleinem Rest → Tag fertig (rest_klein) statt eines zu engen Trades
v, g = a["tt_folge_rechnen"](k1, 194903.91, 190986.15, CFD5, std, random.Random(1), w_h=dict(wh, tp=30), grund_h=None)
check(v is None and g[0] == "rest_klein" and "Pkt" in g[1], f"Folge-Neben: TP-Deckel 30 $ = 7,5 Pkt < 10 → kein Neben-Trade ({g})")
k30 = dict(k1, plan={"n": 4, "haupt_an": 1, "anteile": [0.6, 0.3, 0.05, 0.05]})   # Teil 2: 53 × 30 % = 16 Lot, 10 Pkt = 160 $; Tagesgrenze kürzt auf 100 $ = 6,25 Pkt
v, g = a["tt_folge_rechnen"](k30, 194903.91, 190986.15, dict(CFD5, daily_usd=4118), std, random.Random(1), w_h=dict(wh, sl=None), grund_h=None)
check(v is None and g[0] == "verlust" and "Mindest" in g[1], f"Folge-Neben: SL von der Tagesgrenze unter 10 Pkt gekürzt → Stopp ({g})")
wz = a["tt_planer_haken"](dict(w, sl=200, risiko=200), CFD5, "phase1", std, random.Random(3), ppl=1.0, n_fest=2)
_kz = wz.get("kette") or {}
check(_kz.get("rolle") != "neben" or (wz["sl"] / wz["menge"]) >= 10 - 1e-6, f"Trade 1 als Neben nie mit SL unter 10 Pkt ({_kz.get('rolle')}, {wz.get('sl')}/{wz.get('menge')})")
# Kürzung durch die Tagesgrenze (Haupt ohne SL, daily_usd 4.050 $ nach −3.918 $ → Rest 32 $ < 50 $) → Stopp wie bisher
v, g = a["tt_folge_rechnen"](k1, 194903.91, 190986.15, dict(CFD5, daily_usd=4050), std, random.Random(1), w_h=dict(wh, sl=None), grund_h=None)
check(v is None and g[0] == "verlust", f"von der Tagesgrenze unter 50 $ gekürzt → Stopp wie bisher ({g})")

print("4) Alter Deckel weg")
src = open(os.path.join(HIER, "..", "app.py"), encoding="utf-8").read()
i = src.index("def tt_planer_haken(")
j = src.index("\n_tt = {", i)
check("tt_neben(" not in src[i:j], "tt_planer_haken / tt_folge_rechnen rufen tt_neben nicht mehr (halbe Lots / 10–25 Pkt weg)")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
