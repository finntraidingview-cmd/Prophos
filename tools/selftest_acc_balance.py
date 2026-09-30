#!/usr/bin/env python3
"""Selbsttest Konto-Balance der Admin-Übersicht (app.py acc_balance_wahl, 26.09.2026, B8) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_acc_balance.py
Prueft die Rangfolge TSX → MT5 → Echo → juengere von TradingView/Duplikum und dass die manuelle accounts.balance
kein Rueckfall mehr ist (ohne Live-Wert → None, „ohne Wert")."""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {}
    for name in ("def _wd_num(", "def ist_topstep_express(", "def acc_balance_wahl("):   # Express-Regel seit 01.10.2026
        i = src.index(name)
        exec(src[i:src.find("\n\n\n", i)], ns)
    return ns["acc_balance_wahl"]


def main():
    f = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    acc = {"external_id": "TDFYSL1", "balance": 150000}
    check(f(acc, {}, {}) == (None, None, None, ""), "nur manuelle Balance → None (kein Rueckfall mehr)")
    check(f(dict(acc, topstep_balance=151000, tv_balance=152000), {}, {})[2] == "TSX", "Topstep-Sync zuerst")
    check(f(dict(acc, meta_api_balance=0, tv_balance=152000, tv_balance_at="2026-09-26T19:00:00+00:00"), {}, {})[:3] == (152000.0, "USD", "TV"),
          "MetaApi 0 = unbekannt, TradingView greift")
    check(f(dict(acc, tv_balance=152000), {"TDFYSL1": (153000, "USD", "2026-09-26")}, {})[2] == "Echo", "Echo vor TradingView")
    dup = {"TDFYSL1": (151500, "USD", "2026-09-26T18:00:00+00:00")}
    check(f(dict(acc, tv_balance=152000, tv_balance_at="2026-09-26T19:00:00+00:00"), {}, dup)[2] == "TV", "TV juenger als Duplikum → TV")
    check(f(dict(acc, tv_balance=152000, tv_balance_at="2026-09-26T17:00:00+00:00"), {}, dup)[:3] == (151500.0, "USD", "Duplikum"),
          "Duplikum juenger → Duplikum")
    check(f(dict(acc, tv_balance=0), {}, dup)[2] == "Duplikum" and f(dict(acc, tv_balance=152000), {}, {})[2] == "TV",
          "TV 0 → Duplikum; nur TV → TV")
    check(f(None, None, None) == (None, None, None, ""), "leeres Konto wirft nicht")
    # Topstep Express (01.10.2026, gemeinsame Regel): 0-basiert — 0/negativ sind echte Stände; alter TSX-Sync verliert gegen jüngere Lesung
    xp = {"firm": "Topstep", "account_type": "funded", "name": "150k topstep", "external_id": "KONTO-TEST-1",
          "topstep_balance": 150400, "topstep_last_check": "2026-09-20T10:00:00+00:00", "tv_balance": 0, "tv_balance_at": "2026-10-01T09:00:00+00:00"}
    check(f(xp, {}, {})[:3] == (0.0, "USD", "TV") and f(dict(xp, tv_balance=-300), {}, {})[:3] == (-300.0, "USD", "TV"),
          "Express: Lesung 0 bzw. −300 gilt, der alte TSX-Stand (≈ Kontogröße) nicht")
    check(f(dict(xp, topstep_last_check="2026-10-01T10:00:00+00:00"), {}, {})[2] == "TSX" and f(dict(xp, tv_balance=None), {}, {})[2] == "TSX",
          "Express: TSX nur, wenn nicht älter als die Lesung (oder ohne Lesung)")
    check(f(dict(xp, account_type="challenge", topstep_balance=None), {}, {})[0] is None,
          "Combine (nicht Express): 0 bleibt „unbekannt\" wie bisher")

    print("\nALLES GRUEN" if ok else "\nFEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
