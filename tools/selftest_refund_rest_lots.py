#!/usr/bin/env python3
"""Selbsttest LOTS FÜR REFUND- UND REST-TRADES NACH VERHÄLTNIS (Finn 03.11.2026 ~00:25 Dubai: „Beim Refund-Trade war ich bisher sehr zufrieden … für den
Refund die Formel gleich lassen, nur das ×2 am Ende weglassen, also dass die Lotanzahl um die Hälfte kleiner wird. Bei den Rest-Trades die Formel ×2 gleich
lassen." Konstrukt: .claude/master/berichte/2026-11-01_refund-konstrukt.md)

Aufruf:  python3 tools/selftest_refund_rest_lots.py
Ohne Netz. Regel-Werte wie auto_plan_regeln / funded_cfd_plan_regeln (Dump 02.11.2026). Geprüft:
  fcp_lots_verhaeltnis  Lots_n × (Ziel_klein ÷ Ziel_n) × Faktor, abgerundet auf den Schritt, mindestens ein Schritt, höchstens Lots_n
  Refund                seit 03.11.2026 ~00:50 wieder Lots × 0,1 (Funded-Test 2f), die Formel unten nur für Rest-Trades
  Rest CFD              ap_klein_normal + ap_klein_trade über ap_konto_rechnen: FundedNext 100k Rest 281 $ (29.10.: heute 1,4 Lots) → 0,16–0,33
  Rest Futures          Lucid 150k Rest 84 $ → 1 MNQ wie bisher (Formel < 1); ab Rest 100 $ plant der Bot einen normalen letzten Trade"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_rest_planer as rp  # noqa: E402

rp.FUNKTIONEN = rp.FUNKTIONEN + ("ap_klein_normal", "fcp_lots_verhaeltnis")
rp.KONSTANTEN = rp.KONSTANTEN + ("FCP_LOT_SCHRITT", "AP_KLEIN_PUFFER_MIN")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


a = rp.lade()
V, R, KN, KT, KF = a["fcp_lots_verhaeltnis"], a["ap_konto_rechnen"], a["ap_klein_normal"], a["ap_klein_trade"], a["ap_klein_trade_fut"]

# ── Formel ──
check(V(2.65, 281, 6300, 2.0) == 0.23 and V(2.1, 281, 7200, 2.0) == 0.16 and V(3.2, 281, 5400, 2.0) == 0.33, "Rest 281 FN: ×2 → 0,23 Mitte, 0,16–0,33")
check(V(2.1, 5, 7200, 2.0) == 0.01, "winziger Rest → mindestens ein Schritt (0,01)")
check(V(2.1, 9000, 5400, 2.0) == 2.1, "großer Rest → höchstens die Normal-Lots")
check(V(25, 300, 5850, 2.0, 1) == 2 and V(25, 20, 5850, 2.0, 1) == 1, "Schritt 1 (FTMO/The5ers): abgerundet, mindestens 1")
check(V(0, 1, 1) is None and V(1, 0, 1) is None and V(1, 1, None) is None, "fehlende Werte → None (alter Weg)")

# ── Rest CFD über ap_konto_rechnen: FundedNext 100k Phase 1, Rest 281 $ ──
FN = {"namen": ["fundednext"], "boden": "statisch", "route": "mt5v2", "dd_pct": 10, "groessen": [50000, 100000], "ziel_pct": {"phase1": 5},
      "phasen": {"phase1": {"sl": [2250, 3150], "tp": [5400, 7200], "menge": [2.1, 3.2], "puffer": [25, 50], "menge_schritt": 0.1}}}
for name, uu, soll in (("Mitte", 0.5, None), ("wenig Lots/großer TP", 0.0, 0.16), ("viel Lots/kleiner TP", 1.0, 0.33)):
    u = {"tp": 1.0 - uu, "sl": 0.5, "menge": uu, "puffer": 0.5}
    n = KN(FN["phasen"]["phase1"], u, 1.0)
    w, g = R(FN, "phase1", 104719, u, ppl=10)
    erw = soll if soll is not None else a["fcp_lots_verhaeltnis"](n[0], 281, n[1], 2.0, 0.01)
    check(g is None and "Klein-Trade" in w["stufe"] and w["menge"] == erw and w["puffer"] == max(3, int(1.5 * w["menge"] * 10 + 1e-9))
          and w["tp"] == 281 + w["puffer"] and w["sl"] >= 2250,
          f"FN Rest 281 ({name}, Normal {n[0]} Lot / {n[1]:.0f} $) → {w and w['menge']} Lot, TP {w and w['tp']} $, SL {w and w['sl']} $ — {(w or {}).get('stufe') or g}")
w, g = R(FN, "phase1", 104719, {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}, ppl=10)
check(abs(w["tp"] / (w["menge"] * 10) - 6300 / (2.6 * 10) / 2) < 15, f"halber Punktabstand des Normal-Trades ({w['tp'] / (w['menge'] * 10):.0f} Pkt gegen {6300 / 26 / 2:.0f})")
check(KT(281, 10, 0.1, 0.5)["menge"] == 1.4, "ohne normal: alter Weg (Rest in 20 Pkt) — 1,4 Lots wie am 29.10.")

# ── Rest Futures ──
LUCID = rp.LUCID
w, g = R(LUCID, "challenge", 158916, {"tp": 0.5, "sl": 0.5, "menge": 1.0, "puffer": 0.6}, rest_planer=True)
check(g is None and w["menge"] == 1 and w["symbol"] == "MNQ" and w["tp"] == 104 and w["sl"] == 2500, f"Lucid Rest 84, 3 NQ normal → 1 MNQ wie bisher ({(w or {}).get('stufe') or g})")
kf = KF(300, {"symbol": "NQ"}, {"menge_schritt": 1}, normal=(2.0, 4475.0))
check(kf["menge"] == 2 and kf["puffer"] == 20 and kf["tp"] == 320 and kf["tp_punkte"] == 80.0, f"Futures-Formel: 2 NQ = 20 MNQ × 300 ÷ 4.475 × 2 → 2 MNQ, TP 320 ({kf['stufe']})")
kf = KF(300, {"symbol": "NQ"}, {"menge_schritt": 1}, normal=(3.0, 4475.0))
check(kf["menge"] == 4 and kf["tp_punkte"] == 40.0, f"3 NQ → 4 MNQ, 40 Pkt ({kf['stufe']})")
kf = KF(84, {"symbol": "NQ"}, {"menge_schritt": 1})
check(kf["menge"] == 1 and kf["tp"] == 104, "ohne normal: 1 MNQ wie bisher")

print("\nselftest_refund_rest_lots: " + ("alle Prüfungen grün" if not FEHLER else f"{len(FEHLER)} FEHLER: {FEHLER}"))
sys.exit(1 if FEHLER else 0)
