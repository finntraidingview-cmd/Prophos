#!/usr/bin/env python3
"""Selbsttest: Boden je Konto für den Balance-Balken (app.py ap_boden_konto / _ap_boden, 08.10.2026, Master/Slave 4: Skala
Liquidations-Level → Ziel) — rein rechnend, ohne Netz. Gleiche Rechnung wie der SL-Deckel in ap_konto_rechnen.
Aufruf: python3 tools/selftest_auto_boden.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_wd_num", "ap_groesse", "_ap_spanne", "_ap_runden", "ap_kw_param", "_ap_boden", "ap_boden_konto", "ap_konto_rechnen")
KONSTANTEN = ("AP_REST_MIN", "AP_GROESSE_TOLERANZ")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re}
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in KONSTANTEN]
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def regel(**kw):
    # Kernwerte wie in auto_plan_regeln.regeln.firmen[] (kauf_eur, dd, ziel_pct, Größen) — Werte frei erfunden
    r = {"kauf_eur": 100, "ziel_pct": {"phase1": 10, "challenge": 6}, "groessen": [100000, 150000],
         "phasen": {"phase1": {"menge": [1, 1], "tp": [500, 600], "sl": [3000, 3000]},
                    "challenge": {"menge": [1, 1], "tp": [500, 600], "sl": [3000, 3000]}}}
    r.update(kw)
    return r


def main():
    ns = lade()
    bk, rechnen = ns["ap_boden_konto"], ns["ap_konto_rechnen"]
    f = []

    def check(ok, name):
        f.append(0 if ok else 1)
        print(("OK  " if ok else "FEHL") + " " + name)

    st = bk(regel(boden="statisch", dd_pct=10), "phase1", 100500)
    check(st == {"boden": 90000.0, "boden_min": 90000.0, "boden_art": "statisch"}, f"statisch 10 % von 100k → 90.000 ({st})")
    st2 = bk(regel(boden="statisch", dd_usd=4000), "challenge", 151000)
    check(st2["boden"] == 146000.0 and st2["boden_art"] == "statisch", f"statisch 4.000 $ bei 150k → 146.000 ({st2})")

    lk = regel(boden="nachziehend", dd_usd=4000, lock_bei_start=True)
    a, b, c = bk(lk, "challenge", 147000), bk(lk, "challenge", 153500), bk(lk, "challenge", 156000)
    check(a["boden"] == 146000.0 and b["boden"] == 149500.0 and c["boden"] == 150000.0 and a["boden_art"] == "nachziehend_lock",
          f"nachziehend mit Lock: 147k → 146.000, 153,5k → 149.500, 156k → 150.000 fest ({a['boden']}, {b['boden']}, {c['boden']})")

    ol = bk(regel(boden="nachziehend", dd_usd=4500), "challenge", 151000)
    check(ol == {"boden": None, "boden_min": 145500.0, "boden_art": "nachziehend"},
          f"nachziehend ohne Lock: Stand unbekannt → boden null, Untergrenze 145.500 ({ol})")

    ohne = regel(boden="statisch", dd_pct=10)
    ohne.pop("kauf_eur")
    leer = {"boden": None, "boden_min": None, "boden_art": None}
    check(bk(ohne, "phase1", 100500) == leer, "ohne Kernwerte (kein Kaufpreis) → null, auch wenn ein DD da ist")
    check(bk(None, None, None) == leer and bk(regel(boden="statisch", dd_pct=10), "phase1", None) == leer,
          "ohne Regel / ohne Balance → null")
    check(bk(regel(boden="statisch", dd_pct=10), "phase1", 40000) == leer, "Balance passt zu keiner Größe → null")

    # gleiche Rechnung wie der Planer: SL wird auf Balance − Boden gekappt (3.000 → 2.000 bei 92.000 über 90.000)
    u = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}
    w, grund = rechnen(regel(boden="statisch", dd_pct=10), "phase1", 92000, u)
    check(w is not None and w["sl"] == 92000 - bk(regel(boden="statisch", dd_pct=10), "phase1", 92000)["boden"],
          f"SL-Deckel im Planer = Balance − boden ({(w or {}).get('sl')}, {grund})")
    w2, _ = rechnen(lk, "challenge", 148000, u)
    check(w2 is not None and w2["sl"] == 148000 - bk(lk, "challenge", 148000)["boden"] == 2000,
          f"Lock: SL-Deckel im Planer = Balance − boden ({(w2 or {}).get('sl')})")

    print(f"{len(f) - sum(f)}/{len(f)} ok")
    sys.exit(1 if sum(f) else 0)


if __name__ == "__main__":
    main()
