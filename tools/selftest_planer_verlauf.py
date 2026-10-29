#!/usr/bin/env python3
"""Selbsttest VERLAUF IN € (app.py ap_firma_kurz / ap_verlauf_zeilen, PLANER-VERLAUF-EURO 29.10.2026). Rein rechnend, ohne Netz.
Aufruf: python3 tools/selftest_planer_verlauf.py"""
import os
import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_ist_tradeify_cfd", "_ap_ts", "_ap_tz", "ap_firma_kurz", "ap_verlauf_zeilen")
KONSTANTEN = ("AP_HB_TZ", "AP_VERLAUF_FIRMEN")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone, "ZoneInfo": ZoneInfo}
    teile = []
    for k in KONSTANTEN:
        i = re.search(rf"^{k} = ", src, re.M).start()
        j = src.index("\n", i)
        while src[i:j].count("(") > src[i:j].count(")"):
            j = src.index("\n", j + 1)
        teile.append(src[i:j])
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def main():
    ns = lade()
    fk, vz = ns["ap_firma_kurz"], ns["ap_verlauf_zeilen"]
    f = []
    ok = lambda b, t: f.append(t) if not b else None   # noqa: E731
    for roh, soll in (("Tradeify", "Tradeify"), ("Tradeify CFD", "Tradeify CFD"), ("Apex Trader Funding", "Apex"), ("Topstep", "Topstep"),
                      ("FTMO", "FTMO"), ("FTMO Futures", "FTMO Futures"), ("FundingPips", "FundingPips"), ("FundedNext", "FundedNext"),
                      ("FundedNext Futures", "FundedNext Futures"), ("The5%ers", "The5%ers"), ("The 5ers", "The5%ers"),
                      ("Blue Guardian", "Blue Guardian"), ("Lucid Trading", "Lucid"), ("Neue Firma", "Neue Firma"), (None, "?")):
        ok(fk(roh) == soll, f"Firma {roh!r} → {fk(roh)!r} statt {soll!r}")
    zeilen = [
        {"user_id": "u1", "firma": "Apex Trader Funding", "eur": -120.5, "ergebnis_usd": -300, "art": "normal", "ende": "2026-10-28T19:59:00+00:00"},
        {"user_id": "u1", "firma": "Topstep", "eur": 80, "ergebnis_usd": 200, "art": "normal", "ende": "2026-10-28T20:01:00+00:00"},   # 00:01 Dubai
        {"user_id": "u2", "firma": "Tradeify", "eur": None, "ergebnis_usd": None, "art": "offen", "ende": "2026-10-29T05:00:00Z"},
        {"user_id": "u2", "firma": "Tradeify", "eur": 55, "ergebnis_usd": None, "art": "offen", "ende": "2026-10-29T05:00:00Z"},     # offen zählt nie
        {"user_id": "u2", "firma": "Lucid", "eur": -900, "ergebnis_usd": -2000, "art": "geblowt", "ende": "2026-10-29T06:00:00Z"},
        {"user_id": "u2", "firma": "Lucid", "eur": 1, "art": "normal", "ende": None},                                                # ohne Ende → weg
    ]
    v = vz(zeilen)
    ok(len(v) == 5, f"Anzahl {len(v)}")
    ok([r["tag"] for r in v] == ["2026-10-28", "2026-10-29", "2026-10-29", "2026-10-29", "2026-10-29"], f"Dubai-Tage {[r['tag'] for r in v]}")
    ok(v[0]["firma"] == "Apex" and v[1]["firma"] == "Topstep", "Firma kurz")
    ok(all(r["eur"] is None for r in v if r["art"] == "offen"), "offen → eur None")
    ok(any(r["art"] == "geblowt" and r["eur"] == -900 for r in v), "geblowt bleibt −Kontowert")
    if f:
        print("ROT:\n  " + "\n  ".join(f))
        sys.exit(1)
    print("OK — ap_firma_kurz / ap_verlauf_zeilen grün")


if __name__ == "__main__":
    main()
