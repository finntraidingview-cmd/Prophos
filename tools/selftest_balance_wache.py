#!/usr/bin/env python3
"""Selbsttest BALANCE-WACHE (app.py ap_plan_bal_abweichung + Warten in ap_auto_best_kandidaten, 22.10.2026) — rein rechnend, ohne Netz.
Vorfall Chris Apex 100k …0018: Nachtlauf 01:30 Dubai plante mit der Nachlesung 102.436 (19.10.), 01:36 las der Bot 105.999,50, 01:37
bestätigte er trotzdem → voller Trade 50 Cent unter dem Ziel. Jetzt: Abweichung > 50 $ → nicht bestätigen, die Wache nimmt den Plan heraus.
Aufruf:  python3 tools/selftest_balance_wache.py"""
import os
import re
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade():
    src = open(APP, encoding="utf-8").read()
    # acc_balance_wahl als Attrappe: Balance/Stand aus den Feldern bal/stand am Konto
    ns = {"re": re, "datetime": datetime, "timezone": timezone,
          "acc_balance_wahl": lambda a, e, d: ((a or {}).get("bal"), "USD", "TV", (a or {}).get("stand") or "")}
    for fn in ("_ap_ts", "ap_balance_live"):
        i = src.index(f"def {fn}(")
        exec(src[i:src.index("\n\n\ndef ", i)], ns)
    i = src.index("AP_AUTO_BEST_TAKT_S = ")
    exec(src[i:src.index("\n\n\ndef ap_auto_best_tick(", i)], ns)
    return ns


def main():
    ns = lade()
    ab, kand = ns["ap_plan_bal_abweichung"], ns["ap_auto_best_kandidaten"]
    notiz = "Auto-Planer · letzter Trade (Rest bis Ziel) · Rest 3.564 $ bis Ziel · Balance 102.436 (Nachlesung)"
    letzt = "2026-10-19T04:26:23.63+00:00"                     # Ende des Trades vom 19.10.
    frisch = {"id": "k", "bal": 105999.5, "stand": "2026-10-21T21:36:54+00:00"}   # Lesung 22.10. 01:36 Dubai
    alt = {"id": "k", "bal": 102435.7, "stand": "2026-10-19T04:26:23+00:00"}      # nicht live (vor dem Trade-Ende)
    p = {"id": "p1", "status": "planned", "auto_plan": True, "master_account_id": "k", "master_name": "100k APEX…0018", "notes": notiz}

    r = ab(p, frisch, {}, {}, letzt)
    check(r == (102436.0, 105999.5), f"Vorfall …0018: 102.436 geplant, 105.999,50 gelesen → Abweichung ({r})")
    check(ab(p, alt, {}, {}, letzt) is None, "Balance nicht live → keine Aussage (der Balance-Takt liest erst)")
    check(ab(p, dict(frisch, bal=102470.0), {}, {}, letzt) is None, "34 $ Abweichung ≤ 50 $ → Plan bleibt")
    check(ab(p, dict(frisch, bal=102300.0), {}, {}, letzt) == (102436.0, 102300.0), "136 $ darunter → auch Abweichung")
    check(ab(dict(p, notes="Hand-Plan ohne Balance"), frisch, {}, {}, letzt) is None, "ohne Balance in den notes → nie")
    check(ab(p, None, {}, {}, letzt) is None, "ohne Konto → nie")
    check(ab(p, dict(frisch, bal=None), {}, {}, letzt) is None, "ohne Balance → nie")
    tv = dict(p, notes="Auto-Planer · Etappe · Rest 9.000 $ bis Ziel · Balance 150.000 (TV)")
    check(ab(tv, {"id": "k", "bal": 150000.0, "stand": "2026-10-22T01:00:00+00:00"}, {}, {}, None) is None, "geplant = gelesen → Plan bleibt")

    check(ab(dict(p, kette={"nr": 1}), frisch, {}, {}, letzt) is None and ab(dict(p, tage_mini={"tag": "x"}), frisch, {}, {}, letzt) is None,
          "Topstep-Kette / Tage-Mini → nie (eigene Balance-Logik)")
    ok, warten = kand([p], {"k": frisch}, {"k": letzt}, {}, {})
    check(ok == [] and len(warten) == 1 and "Balance-Wache" in warten[0]["warum"] and "102.436" in warten[0]["warum"]
          and "105.999,50" in warten[0]["warum"], f"Auto-Bestätigen wartet beim Vorfall ({warten})")
    ok2, _ = kand([p], {"k": dict(frisch, bal=102436.0)}, {"k": letzt}, {}, {})
    check(ok2 == ["p1"], "passende Balance → Auto-Bestätigen bestätigt wie bisher")
    print(f"\n{'ALLES OK' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
