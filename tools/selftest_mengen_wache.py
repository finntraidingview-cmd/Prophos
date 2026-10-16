#!/usr/bin/env python3
"""Selbsttest MENGEN-WACHE (app.py ap_menge_fix, Master 16.10.2026 — Finn: „Apex — TP passt immer, aber NQ-Anzahl fix immer 3").
Aufruf:  python3 tools/selftest_mengen_wache.py
Geprüft mit der echten Apex-Regel (menge [3,3], Puffer 100, Punkte-Puffer 6 Pkt × Menge × 20 $): 4/5 NQ → 3 NQ und TP 9.460 $;
3 NQ bleibt; Etappe (TP aus der Spanne) → nur die Menge; ohne Menge → nichts."""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_alle_ids as sa  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    ns = sa.lade()
    src = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
    i = src.index("\ndef ap_menge_fix(") + 1
    exec(src[i:src.index("\n\n\n", i)], ns)
    fix = ns["ap_menge_fix"]
    apex = {"boden": "statisch", "namen": ["apextrader", "apex"], "route": "tvv2", "dd_usd": 4000, "symbol": "NQ", "groessen": [150000],
            "ziel_pct": {"challenge": 6}, "phasen": {"challenge": {"sl": None, "tp": None, "menge": [3, 3], "puffer": [100, 100], "menge_schritt": 1}}}
    rest = "Auto-Planer · letzter Trade (Rest bis Ziel) · Rest 9.000 $ bis Ziel · Balance 150.000 (TV)"
    p4, t4 = fix({"master_contracts": "4.000", "master_tp": "9580.00", "notes": rest}, apex, "challenge", 150000.0)
    check(p4 == {"master_contracts": 3, "master_tp": 9460} and "Menge 4 → 3" in t4 and "9.580 → 9.460" in t4, f"4 NQ → 3 NQ, TP 9.580 → 9.460 ({p4}, {t4})")
    p5, _ = fix({"master_contracts": "5.000", "master_tp": "9700.00", "notes": rest}, apex, "challenge", 150000.0)
    check(p5 == {"master_contracts": 3, "master_tp": 9460}, "5 NQ → 3 NQ, TP 9.460")
    check(fix({"master_contracts": "3.000", "master_tp": "9460", "notes": rest}, apex, "challenge", 150000.0)[0] is None, "3 NQ passt → nichts")
    etappe = dict(apex, phasen={"challenge": dict(apex["phasen"]["challenge"], tp=[2000, 2000], tp_max=3000)})
    pe, _ = fix({"master_contracts": "5", "master_tp": "2000", "notes": "Auto-Planer · Etappe · Rest 9.000 $ bis Ziel · Balance 150.000 (TV)"},
                etappe, "challenge", 150000.0)
    check(pe == {"master_contracts": 3}, f"Etappe: nur die Menge, TP bleibt ({pe})")
    check(fix({"master_contracts": None, "notes": rest}, apex, "challenge", 150000.0)[0] is None, "ohne Menge → nichts")
    print(f"\n{'ALLES OK' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
