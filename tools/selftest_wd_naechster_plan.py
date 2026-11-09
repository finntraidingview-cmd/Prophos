#!/usr/bin/env python3
"""Selbsttest RC2 (10.11.2026): app.py wd_naechster_plan — nächster Plan je Konto für Admin → Payouts (Recoverer/Recovery).
Rein rechnend, ohne Netz. Aufruf: python3 tools/selftest_wd_naechster_plan.py"""
import os
import re
import sys

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re}
    for name in ("wd_ist_recoverer_plan", "wd_naechster_plan"):
        i = src.index(f"\ndef {name}(") + 1
        exec(src[i:src.find("\n\n\n", i)], ns)
    return ns["wd_naechster_plan"]


def main():
    f, fehler = lade(), []
    ok = lambda b, t: fehler.append(t) if not b else None
    apex = {"winning_day": True, "master_firm": "Apex Trader"}
    r = f([dict(apex, id="a", master_account_id="k1", status="planned", start_um="2026-11-10T14:05:00Z", master_symbol="NQZ6"),
           dict(apex, id="b", master_account_id="k1", status="planned", start_um="2026-11-10T12:00:00Z", master_symbol="MNQZ6"),
           {"id": "c", "master_account_id": "k2", "status": "open", "started_at": "2026-11-10T10:00:00Z", "master_firm": "Tradeify", "wd_ausgleich": "true"},
           {"id": "d", "master_account_id": "k2", "status": "planned", "start_um": "2026-11-10T09:00:00Z"},
           dict(apex, id="e", master_account_id="k3", status="planned", start_um=None, master_symbol_root="NQ"),
           {"id": "f", "master_account_id": "k5", "status": "planned", "start_um": "2026-11-10T09:00:00Z"},
           {"id": "g", "master_account_id": "k5", "status": "open", "started_at": "2026-11-10T08:00:00Z"},
           {"id": "x", "master_account_id": "k4", "status": "completed"}, {"id": "y", "status": "planned"}])
    ok(r.get("k1", {}).get("id") == "a" and r["k1"]["recoverer"] is True, f"k1 Recovery-Plan vor früherem normalen: {r.get('k1')}")
    ok(r.get("k2", {}).get("id") == "c" and r["k2"]["recoverer"] is True and r["k2"]["start_um"] == "2026-11-10T10:00:00Z", f"k2 Tradeify-Ausgleich offen: {r.get('k2')}")
    ok(r.get("k3", {}).get("recoverer") is True and r["k3"]["start_um"] is None, f"k3 ohne Startzeit: {r.get('k3')}")
    ok(r.get("k5", {}).get("id") == "g" and r["k5"]["recoverer"] is False, f"k5 laufender vor geplantem: {r.get('k5')}")
    ok("k4" not in r and "" not in r, f"erledigt/ohne Konto drin: {sorted(r)}")
    ok(f([]) == {} and f(None) == {}, "leer")
    if fehler:
        print("ROT:\n  " + "\n  ".join(fehler))
        sys.exit(1)
    print("OK — wd_naechster_plan grün")


if __name__ == "__main__":
    main()
