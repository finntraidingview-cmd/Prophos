#!/usr/bin/env python3
"""Selbsttest FUNDINGPIPS FLEX ODER STANDARD JE KONTO (app.py ap_konto_flex, ap_regel_flex, ap_regel_konto, ap_konto_rechnen,
ap_boden_konto, 08.10.2026, Slave-Terminal 3 — Finn: „bei allen Accounts, wo das Maximum Drawdown 12 % vom Initial Balance ist — das ist
alles Flex, die anderen sind in Zukunft alles Neues immer Standard").

Aufruf:  python3 tools/selftest_auto_fp_flex.py
Ohne Netz, Platzhalter-Konten. Regel wie nach sql/2026-10-08_fundingpips_flex_standard.sql. Geprüft: 50k mit 6.000 DD → Flex-Werte
(SL 1.250–1.500, 0,5–0,7 Lots, Ziel 10 %); 50k mit 5.000 DD (10 %) → „50k Standard: Werte fehlen"; 100k mit 12.000 DD und
starting_balance 100.000 (account_size 150.000) → Flex → „100k Flex: Werte fehlen"; nur account_size 150.000 → Anfangsgröße 150k → kein
Flex; 100k mit 10.000 DD → Standard-Werte; Boden Flex 12 % / Standard 10 %; ohne max_drawdown → Standard; Regel ohne flex unverändert."""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


FLEX50 = {"dd_pct": 12, "ziel_pct": {"phase1": 10, "phase2": 5},
          "phasen": {"phase1": {"sl": [1250, 1500], "tp": [2500, 3000], "menge": [0.5, 0.7], "puffer": [75, 100], "boden_pct": 12,
                                "menge_schritt": 0.01},
                     "phase2": {"sl": [1250, 1500], "tp": [1000, 1250], "menge": [0.5, 0.7], "puffer": [75, 100], "boden_pct": 12,
                                "menge_schritt": 0.01}}}
FP = {"namen": ["fundingpips"], "route": "mt5v2", "boden": "statisch", "dd_pct": 10, "groessen": [50000, 100000],
      "ziel_pct": {"phase1": 8, "phase2": 5},
      "phasen": {"phase1": {"sl": [2500, 3500], "tp": [3500, 4000], "menge": [1, 1.5], "puffer": [50, 75], "tp_max": 4000, "ziel_pct": 8,
                            "boden_pct": 10, "menge_schritt": 0.1},
                 "phase2": {"sl": [2500, 3500], "tp": [2000, 2500], "menge": [1, 1.5], "puffer": [50, 75], "tp_max": 2500, "ziel_pct": 5,
                            "boden_pct": 10, "menge_schritt": 0.1}},
      "kauf_eur": {"50000": 240, "100000": 464}, "wert_groessen": [50000, 100000],
      "je_groesse": {}, "standard_groessen": [100000], "flex": {"ab_dd_pct": 12, "dd_pct": 12, "je_groesse": {"50000": FLEX50}}}
U = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}


def konto(dd, **kw):
    return dict({"id": "00000000-0000-0000-0000-0000000000f1", "firm": "FundingPips", "account_type": "phase1", "max_drawdown": dd}, **kw)


def main():
    a = sd.lade()
    RK, R, B, F = a["ap_regel_konto"], a["ap_konto_rechnen"], a["ap_boden_konto"], a["ap_konto_flex"]

    def plan(k, bal):
        return R(RK(FP, k, bal), k["account_type"], bal, U)

    # ── 1 Flex/Standard erkennen ──────────────────────────────────────────────────────────────────────────────────────────
    check(F(FP, konto(6000), 48900) is True and F(FP, konto(5000), 48900) is False, "50k: 6.000 DD = Flex, 5.000 DD = Standard")
    check(F(FP, konto(12000, starting_balance=100000, account_size=150000), 101000) is True,
          "Jacob-Fall: starting_balance 100.000 vor account_size 150.000 → 12.000 DD = Flex")
    check(F(FP, konto(12000, account_size=150000), 101000) is False, "nur account_size 150.000 → 8 % → Standard")
    check(F(FP, konto(None), 48900) is False and F(dict(FP, flex=None), konto(6000), 48900) is None,
          "ohne max_drawdown → Standard; Regel ohne flex → None (nichts ändert sich)")

    # ── 2 Planer-Werte ────────────────────────────────────────────────────────────────────────────────────────────────────
    w, g = plan(konto(6000), 48916.0)
    check(w and 1250 <= w["sl"] <= 1500 and 0.5 <= w["menge"] <= 0.7 and round(w["ziel"]) == 55000,
          f"Flex 50k: SL 1.250–1.500, 0,5–0,7 Lots, Ziel 10 % ({w and (w['sl'], w['menge'], round(w['ziel']))}, {g})")
    w, g = plan(konto(5000), 48916.0)
    check(w is None and str(g).startswith("FundingPips 50k Standard: Werte fehlen — 50k ist keine Standard-Größe"), f"Standard 50k → ausgelassen „{g}“")
    w, g = plan(konto(12000, starting_balance=100000, account_size=150000), 100500.0)
    check(w is None and str(g).startswith("FundingPips 100k Flex: Werte fehlen — Admin → Trade-Planer → Kernwerte"), f"Flex 100k (Jacob-Fall) → ausgelassen „{g}“")
    w, g = plan(konto(10000), 100500.0)
    check(w and 2500 <= w["sl"] <= 3500 and 1 <= w["menge"] <= 1.5 and round(w["ziel"]) == 108000,
          f"Standard 100k: Firmen-Werte SL 2.500–3.500, 1–1,5 Lots, Ziel 8 % ({w and (w['sl'], w['menge'], round(w['ziel']))}, {g})")
    nachf = konto(6000, id="00000000-0000-0000-0000-0000000000f2", account_type="phase2")
    w, g = plan(nachf, 50300.0)
    check(w and 1000 <= w["tp"] <= 1250 + 100 and 1250 <= w["sl"] <= 1500, f"Nachfolger Phase 2 mit übernommenem DD 6.000 → Flex P2 ({w and w['tp']})")

    # ── 3 Boden ───────────────────────────────────────────────────────────────────────────────────────────────────────────
    b_flex100 = B(RK(FP, konto(12000, starting_balance=100000), 100500.0), "phase1", 100500.0)
    b_std100 = B(RK(FP, konto(10000), 100500.0), "phase1", 100500.0)
    b_flex50 = B(RK(FP, konto(6000), 48916.0), "phase1", 48916.0)
    check(b_flex100["boden"] == 88000.0 and b_std100["boden"] == 90000.0 and b_flex50["boden"] == 44000.0,
          f"Boden: Flex 100k 88.000 / Standard 100k 90.000 / Flex 50k 44.000 ({b_flex100['boden']}, {b_std100['boden']}, {b_flex50['boden']})")

    # ── 4 alte Regel (vor dem SQL) unverändert ────────────────────────────────────────────────────────────────────────────
    alt = dict(FP, je_groesse={"50000": dict(FLEX50, flex=True)})
    alt.pop("flex")
    alt.pop("standard_groessen")
    w, g = R(RK(alt, konto(5000), 48916.0), "phase1", 48916.0, U)
    check(w and 1250 <= w["sl"] <= 1500, "ohne flex-Block (alter Stand): 50k-Block gilt wie bisher für jedes 50k-Konto")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
