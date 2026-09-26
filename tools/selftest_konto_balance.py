#!/usr/bin/env python3
"""Selbsttest Konto-Balance auf Zuruf (app.py, KONTO-BALANCE LESEN, 27.09.2026, B12) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_konto_balance.py
Prueft Rechte (Admin/Besitzer), Signal-Zeile (plan_id 'konto:<id>', params) und Stand inkl. Verfall nach 10 min."""
import os
import re
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone}

    def block(name):
        i = src.index(f"def {name}(")
        return src[i:src.find("\n\n\n", i)]
    exec("\n".join([re.search(r"^KONTO_BALANCE_VERFALL_S = .*$", src, re.M).group(0), block("_wd_num"),
                    block("konto_balance_darf"), block("konto_balance_signal"), block("konto_balance_stand")]), ns)
    return ns


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    konto = {"id": "11111111-1111-1111-1111-111111111111", "user_id": "u-moritz", "name": "Tradeify 150k",
             "firm": "Tradeify", "external_id": " TDFYSL150813173931 "}
    d = a["konto_balance_darf"]
    check(d("u-moritz", "moritz@x", konto, {"finn@x"}) and d("u-finn", "finn@x", konto, {"finn@x"})
          and not d("u-jacob", "jacob@x", konto, {"finn@x"}) and not d("u-jacob", "", konto, set()) and not d("u", "m", None, {"m"}),
          "Rechte: Besitzer ja, Admin ja, fremder Nutzer nein, ohne Konto nein")
    z = a["konto_balance_signal"](konto, "admin")
    check(z["user_id"] == "u-moritz" and z["plan_id"] == "konto:11111111-1111-1111-1111-111111111111" and z["status"] == "wartet"
          and z["params"] == {"aktion": "konto_balance", "account_id": konto["id"], "external_id": "TDFYSL150813173931",
                              "firm": "Tradeify", "name": "Tradeify 150k", "von": "admin"},
          "Signal im Namen des Besitzers, plan_id konto:<id>, params mit getrimmter External ID")
    st = a["konto_balance_stand"]
    t0 = datetime(2026, 9, 27, 10, 0, tzinfo=timezone.utc)
    sig = {"status": "fertig", "created_at": t0.isoformat(), "updated_at": t0.isoformat(), "pc": "pc-usq1i6",
           "params": {"account_id": konto["id"]},
           "ergebnis": {"ok": True, "balance": 152340.5, "equity": 152400, "balance_at": "2026-09-27T10:01:00Z", "msg": "gelesen"}}
    r = st(sig, t0.timestamp() + 90)
    check(r["status"] == "fertig" and r["balance"] == 152340.5 and r["equity"] == 152400.0 and r["pc"] == "pc-usq1i6"
          and r["grund"] == "gelesen" and r["account_id"] == konto["id"] and not r["verfallen"], "fertig: Balance/Equity/Grund durchgereicht")
    r = st(dict(sig, status="wartet", ergebnis=None), t0.timestamp() + 601)
    check(r["status"] == "verfallen" and r["verfallen"] and "abgeholt" in r["grund"], "wartet > 10 min → verfallen (kein PC-Tab)")
    r = st(dict(sig, status="laeuft", ergebnis=None), t0.timestamp() + 599)
    check(r["status"] == "laeuft" and not r["verfallen"] and r["balance"] is None, "laeuft < 10 min → laeuft")
    r = st(dict(sig, status="fehler", ergebnis={"ok": False, "msg": "Puls-Fenster unklar"}), t0.timestamp() + 5000)
    check(r["status"] == "fehler" and r["grund"] == "Puls-Fenster unklar" and not r["verfallen"], "fehler bleibt fehler, Grund aus ergebnis")

    print("\nALLES GRUEN" if ok else "\nFEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
