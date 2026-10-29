#!/usr/bin/env python3
"""Selbsttest fuer wd_erl_konto_umstellen_upd (app.py, 29.10.2026) — Radar „Trade erledigt" mit Account-Status
„⏳ Waiting for Payout" / „🏆 → Winning Days". Rein rechnend, ohne Flask/Netz.

Aufruf:  python3 tools/selftest_wd_erl_konto_umstellen.py
Laedt wd_erl_konto_umstellen_upd, ap_klasse, _ist_tradeify_cfd und die Firmen-Konstanten per Quelltext aus app.py. Prueft:
waiting nur Funded CFD ohne waiting_payout_since; winning_days nur Funded einer Futures-Firma (nie Tradeify CFD, nie FundedNext
CFD); notes wie accWdUmstellen im Frontend (alte „Winning Days seit …" raus, neue Zeile ans Ende, leer → None); Konto fehlt /
Ziel unbekannt → None mit Grund."""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re}

    def block(name):
        i = src.index(f"def {name}(")
        return src[i:src.find("\n\n\n", i)]

    def const(name):
        return re.search(rf"^{name} = .*$", src, re.M).group(0)
    exec("\n".join([const("WD_FUTURES_FIRMEN"), const("WD_BALANCE_FUTURES"), const("AP_CFD_ROUTEN")]
                   + [block(n) for n in ("_ist_tradeify_cfd", "ap_klasse", "wd_erl_konto_umstellen_upd")]), ns)
    return ns


def main():
    f = lade()["wd_erl_konto_umstellen_upd"]
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    T, H = "2026-10-29T13:32:00Z", "29.10.2026"
    upd, g = f({"account_type": "funded_cfd", "firm": "FundedNext"}, "waiting", T, H)
    check(upd == {"waiting_payout_since": T} and g == "", "Funded CFD → waiting_payout_since = jetzt")
    upd, g = f({"account_type": "funded_cfd", "firm": "FundedNext", "waiting_payout_since": "2026-10-20T00:00:00Z"}, "waiting", T, H)
    check(upd is None and "schon" in g, "schon Waiting → nichts geschrieben")
    upd, g = f({"account_type": "funded", "firm": "Tradeify"}, "waiting", T, H)
    check(upd is None, "Waiting nur bei Funded CFD (nicht Funded Futures)")
    upd, g = f({"account_type": "winning_days", "firm": "Tradeify"}, "waiting", T, H)
    check(upd is None, "Waiting nicht bei Winning Days")

    upd, g = f({"account_type": "funded", "firm": "Apex Trader", "notes": None}, "winning_days", T, H)
    check(upd == {"account_type": "winning_days", "notes": f"Winning Days seit {H}"}, "Funded Apex → Winning Days + notes")
    upd, g = f({"account_type": "funded", "firm": "Tradeify", "notes": "Kauf 01.10.\nWinning Days seit 05.10.2026"}, "winning_days", T, H)
    check(upd and upd["notes"] == f"Kauf 01.10.\nWinning Days seit {H}", "alte „Winning Days seit …\" ersetzt, Rest bleibt")
    # wie accWdUmstellen (split → filter → concat → join → trim): eine Leerzeile mittendrin bleibt stehen, nur außen wird getrimmt
    upd, g = f({"account_type": "funded", "firm": "Tradeify", "notes": "Kauf 01.10.\n"}, "winning_days", T, H)
    check(upd and upd["notes"] == f"Kauf 01.10.\n\nWinning Days seit {H}", "notes genau wie im Frontend (Leerzeile bleibt)")
    for firm in ("Topstep", "Lucid Trading", "FundedNext Futures", "FTMO Futures", "Alpha Futures"):
        upd, g = f({"account_type": "funded", "firm": firm}, "winning_days", T, H)
        check(upd and upd["account_type"] == "winning_days", f"Futures-Firma {firm} → Winning Days")
    for firm in ("Tradeify CFD", "FundedNext", "Blue Guardian", ""):
        upd, g = f({"account_type": "funded", "firm": firm}, "winning_days", T, H)
        check(upd is None and "Futures" in g, f"CFD-Firma „{firm}\" → nie Winning Days")
    upd, g = f({"account_type": "funded_cfd", "firm": "Tradeify"}, "winning_days", T, H)
    check(upd is None, "Winning Days nur bei Kontotyp funded")
    upd, g = f({"account_type": "challenge", "firm": "Apex Trader"}, "winning_days", T, H)
    check(upd is None, "Challenge → nie Winning Days")

    upd, g = f(None, "waiting", T, H)
    check(upd is None and "nicht gefunden" in g, "Konto fehlt → None + Grund")
    upd, g = f({"account_type": "funded_cfd"}, "blown", T, H)
    check(upd is None and "unbekannt" in g, "anderes Ziel → None")

    print("alle Tests bestanden" if ok else "FEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
