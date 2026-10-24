#!/usr/bin/env python3
"""Selbsttest GEWINNTAGE (app.py ap_tage_ist / ap_tage_gewinn / ap_konto_rechnen regel.gewinntage, Blue Guardian, Finn 25.10.2026):
Blue Guardian zählt nur Tage mit ≥ 500 $ geschlossenem Gewinn (3 je Phase). Solange zwei oder mehr fehlen, plant der Bot nur Gewinntag-
Trades (TP ~1.000 $, SL und Lots wie die Regel), erst bei höchstens einem fehlenden Tag die Big Trades. Der 0,01-Lot-Mini zählt hier nie.

Aufruf:  python3 tools/selftest_gewinntage.py
Ohne Netz."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


# Blue Guardian wie in auto_plan_regeln (25.10.2026) + gewinntage
BG = {"namen": ["blueguardian"], "route": "mt5v2", "groessen": [100000], "ziel_pct": {"phase1": 8, "phase2": 4}, "boden": "statisch", "dd_pct": 8,
      "gewinntage": {"tp": [1000, 1100]},
      "phasen": {"phase1": {"sl": [3000, 3500], "tp": [5500, 6500], "menge": [4, 5.3], "puffer": [100, 100], "boden_pct": 8, "menge_schritt": 0.1},
                 "phase2": {"sl": [3000, 3500], "tp": [3000, 3500], "menge": [4, 5.3], "puffer": [100, 100], "boden_pct": 8, "menge_schritt": 0.1}}}
U = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}
PPL = 10.0


def main():
    a = sd.lade()
    R, IST, GEW, KONTO = a["ap_konto_rechnen"], a["ap_tage_ist"], a["ap_tage_gewinn"], a["ap_tage_konto"]

    # --- Zählung ---
    k = {"id": "k1", "goal_kind": "winning_days", "goal_target": 3, "goal_min_profit": 500, "goal_since": "2026-10-22", "goal_done_offset": 0}
    plaene = [
        {"master_account_id": "k1", "status": "completed", "master_pl": 4075.2, "started_at": "2026-10-22T08:00:00+00:00", "ended_at": "2026-10-22T09:00:00+00:00"},
        {"master_account_id": "k1", "status": "completed", "master_pl": -0.58, "started_at": "2026-10-23T08:00:00+00:00", "ended_at": "2026-10-23T08:01:00+00:00"},
        # zwei Trades an einem Tag: 300 + 250 = 550 ≥ 500 → zählt
        {"master_account_id": "k1", "status": "completed", "master_pl": 300, "started_at": "2026-10-26T08:00:00+00:00", "ended_at": "2026-10-26T09:00:00+00:00"},
        {"master_account_id": "k1", "status": "review", "master_pl": 250, "started_at": "2026-10-26T10:00:00+00:00", "ended_at": "2026-10-26T11:00:00+00:00"},
        # 499 → zählt nicht; vor goal_since → zählt nicht; laufend → zählt nicht; fremdes Konto → zählt nicht
        {"master_account_id": "k1", "status": "completed", "master_pl": 499, "started_at": "2026-10-27T08:00:00+00:00", "ended_at": "2026-10-27T09:00:00+00:00"},
        {"master_account_id": "k1", "status": "completed", "master_pl": 2000, "started_at": "2026-10-21T08:00:00+00:00", "ended_at": "2026-10-21T09:00:00+00:00"},
        {"master_account_id": "k1", "status": "open", "master_pl": 900, "started_at": "2026-10-28T08:00:00+00:00"},
        {"master_account_id": "k2", "status": "completed", "master_pl": 900, "started_at": "2026-10-28T08:00:00+00:00", "ended_at": "2026-10-28T09:00:00+00:00"},
    ]
    check(IST(k, plaene) == (2, 3), f"Gewinntage: 22.10. + 26.10. (300+250) = 2/3, Mini/499/vor goal_since/laufend/fremd zählen nicht ({IST(k, plaene)})")
    check(IST(dict(k, goal_done_offset=1), plaene) == (3, 3), "goal_done_offset kommt dazu")
    check(GEW(k) == 500.0 and KONTO(k), "ap_tage_gewinn 500, ap_tage_konto ja")
    check(GEW(dict(k, goal_manual=True)) is None and IST(dict(k, goal_manual=True), plaene) is None,
          "manuelle Winning Days (Futures-Funded) bleiben draußen")
    check(GEW(dict(k, goal_min_profit=None)) is None and IST(dict(k, goal_min_profit=None), plaene) is None,
          "winning_days ohne Mindestgewinn: kein Planer-Zähler (wie bisher)")
    kt = {"id": "k1", "goal_kind": "trading_days", "goal_target": 3, "goal_since": "2026-10-22"}
    check(IST(kt, plaene) == (5, 3), f"trading_days unverändert: jeder Start-Tag ab goal_since (22., 23., 26., 27., 28.) ({IST(kt, plaene)})")

    # --- Planer: Phase 2 frisch, 0/3 → Gewinntag-Trade, SL wie die Regel ---
    w, g = R(BG, "phase2", 100000.0, U, ppl=PPL, tage=(0, 3))
    check(w and w["tp"] == 1050 and w["puffer"] == 0 and 3000 <= w["sl"] <= 3500 and 4 <= w["menge"] <= 5.3
          and w["stufe"].startswith("Gewinntag 0/3 sammeln · TP 1.050 $") and "Big Trade erst" in w["stufe"],
          f"P2 0/3: Gewinntag-Trade TP 1.050, SL/Lots normal ({g or w})")
    w1, g1 = R(BG, "phase2", 101050.0, U, ppl=PPL, tage=(1, 3))
    check(w1 and w1["tp"] == 1050 and "Gewinntag 1/3" in w1["stufe"], f"P2 1/3: noch ein Gewinntag-Trade ({g1 or w1})")
    # 2/3 → Big Trade: Rest 1.900 + Puffer → letzter Trade
    w2, g2 = R(BG, "phase2", 102100.0, U, ppl=PPL, tage=(2, 3))
    check(w2 and "Gewinntag" not in w2["stufe"] and w2["tp"] > 1900, f"P2 2/3: normaler Trade ans Ziel ({g2 or w2})")
    # 2/3, Rest 300 < Gewinntag-TP → Gewinntag-Trade statt Klein-Trade
    w3, g3 = R(BG, "phase2", 103700.0, U, ppl=PPL, tage=(2, 3))
    check(w3 and w3["tp"] == 1050 and "Rest unter dem Gewinntag-TP" in w3["stufe"], f"P2 2/3 Rest 300: Gewinntag-Trade statt Klein ({g3 or w3})")
    # 3/3, Rest 300 → normaler Klein-Trade wie bisher
    w4, g4 = R(BG, "phase2", 103700.0, U, ppl=PPL, tage=(3, 3))
    check(w4 and "Klein-Trade" in w4["stufe"], f"P2 3/3 Rest 300: Klein-Trade wie bisher ({g4 or w4})")
    # Ziel erreicht, Tage fehlen → kein Mini, Grund
    w5, g5 = R(BG, "phase2", 104075.0, U, ppl=PPL, tage=(1, 3))
    check(w5 is None and "Gewinntage 1/3" in (g5 or "") and "von Hand" in (g5 or ""), f"Ziel erreicht 1/3: kein Mini, von Hand ({g5})")
    w6, g6 = R(BG, "phase2", 104075.0, U, ppl=PPL, tage=(3, 3))
    check(w6 is None and g6 == "Ziel erreicht — Phase umstellen", f"Ziel erreicht 3/3: Phase umstellen ({g6})")
    # Phase 2 im Minus (…602629: 96.615, 0/3) → Gewinntag-Trade, SL am Boden 92.000 gekappt? 4.615 Luft ≥ SL → normal
    w7, g7 = R(BG, "phase2", 96615.0, U, ppl=PPL, tage=(0, 3))
    check(w7 and w7["tp"] == 1050 and w7["sl"] <= 3500, f"P2 im Minus 0/3: Gewinntag-Trade ({g7 or w7})")
    # nahe am Boden: SL hinter den Boden wie die Regel
    w8, g8 = R(BG, "phase2", 93500.0, U, ppl=PPL, tage=(0, 3))
    check(w8 and w8["tp"] == 1050 and w8["sl"] < 3000 and "SL hinter den Boden" in w8["stufe"], f"nahe Boden: SL gekappt ({g8 or w8})")
    # Phase 1 frisch 0/3 → Gewinntag-Trade
    w9, g9 = R(BG, "phase1", 100000.0, U, ppl=PPL, tage=(0, 3))
    check(w9 and w9["tp"] == 1050 and "Gewinntag 0/3" in w9["stufe"], f"P1 0/3: Gewinntag-Trade ({g9 or w9})")
    # ohne gewinntage in der Regel → unverändert Etappe
    BG0 = {x: v for x, v in BG.items() if x != "gewinntage"}
    w10, g10 = R(BG0, "phase2", 100000.0, U, ppl=PPL, tage=(0, 3))
    check(w10 and w10["stufe"] == "Etappe", f"Regel ohne gewinntage: Etappe wie bisher ({g10 or w10})")
    # ohne tage (Konto ohne Ziel-Feld) → unverändert
    w11, g11 = R(BG, "phase2", 100000.0, U, ppl=PPL, tage=None)
    check(w11 and w11["stufe"] == "Etappe", f"ohne Tage: Etappe wie bisher ({g11 or w11})")

    print()
    print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
