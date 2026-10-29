#!/usr/bin/env python3
"""Selbsttest FINALER TRADEIFY HALTEN (app.py ap_tradeify_final_halten, 29.10.2026). Rein rechnend, ohne Netz.
Aufruf: python3 tools/selftest_tradeify_final_halten.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re}
    teile = []
    for name in ("_wd_num", "_ist_tradeify_cfd", "ap_tradeify_final_halten"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns["ap_tradeify_final_halten"]


def main():
    h = lade()
    f = []
    ok = lambda b, t: f.append(t) if not b else None   # noqa: E731
    letzt = {"stufe": "letzter Trade (Rest bis Ziel)", "rest": 1979, "tp": 2039}
    etappe = {"stufe": "Etappe", "rest": 9000, "tp": 3500}
    ok(h({}, "Tradeify", letzt) is True, "letzter Trade Tradeify → halten (Schalter fehlt = an)")
    ok(h({"tradeify_final_halten": True}, "Tradeify", letzt) is True, "Schalter an → halten")
    ok(h({"tradeify_final_halten": False}, "Tradeify", letzt) is False, "Schalter aus → planen")
    ok(h({}, "Tradeify CFD", letzt) is False, "Tradeify CFD nie")
    ok(h({}, "Apex Trader", letzt) is False, "andere Firma nie")
    ok(h({}, "Tradeify", etappe) is False, "Etappe nicht final")
    ok(h({}, "Tradeify", {"stufe": "Etappe", "rest": 2000, "tp": 2039}) is True, "Etappe mit TP ≥ Rest → final")
    ok(h({}, "Tradeify", {"stufe": "Etappe", "rest": 0, "tp": 500}) is True, "Rest 0 → final")
    ok(h({}, "Tradeify", {"stufe": "Tage sammeln 3/5", "rest": 100, "tp": 300}) is False, "Tage sammeln nie")
    ok(h({}, "Tradeify", {"stufe": "Klein-Trade · Rest 84 $", "rest": 84, "tp": 120}) is True, "Klein-Trade final")
    ok(h({}, "Tradeify", {"stufe": "Etappe", "tp": 3000}) is False, "ohne Rest nicht final")
    if f:
        print("ROT:\n  " + "\n  ".join(f))
        sys.exit(1)
    print("OK — ap_tradeify_final_halten grün")


if __name__ == "__main__":
    main()
