#!/usr/bin/env python3
"""Selbsttest fuer PATCH /admin/wd-plaene {aktion:'balance'} (app.py, 08.10.2026, Slave-Terminal 3) — rein rechnend, ohne Flask/Netz.

Aufruf:  python3 tools/selftest_wd_balance.py
Laedt _wd_balance_signal per Quelltext aus app.py. Prueft: MT5-Konto mit Login → 'mt5_balance' im Namen des Besitzers, Futures-Firma
→ 'konto_balance'; CFD ohne Login → 409 (nie Tradovate, 08.10.2026); ohne Konto/Besitzer/ID → Fehler mit Code; die Route und das Gate kennen 'balance'/'balance_stand'."""
import os
import re

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {}
    i = src.index("WD_FUTURES_FIRMEN = ")
    exec(src[i:src.find("\n", i)], ns)
    i = src.index("WD_BALANCE_FUTURES = ")
    exec(src[i:src.find("\n", i)], ns)
    ns["re"] = re
    i = src.index("def balance_lese_weg(")
    exec(src[i:src.find("\n\n\n", i)], ns)
    i = src.index("def _wd_balance_signal(")
    exec(src[i:src.find("\n\n\n", i)], ns)
    return ns["_wd_balance_signal"], src


def main():
    sig, src = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    uid = "32b854d1-866f-4e7e-ba0b-9bf63df2d993"
    acc = {"id": "a1b2c3d4-0000-4000-8000-000000000001", "user_id": uid, "name": "Muster 100k", "firm": "FundingPips", "external_id": "MUSTER-000001"}
    z, f = sig(acc, "12345678")
    check(f is None and z == {"user_id": uid, "plan_id": "konto:" + acc["id"], "status": "wartet",
                              "params": {"account_id": acc["id"], "external_id": "MUSTER-000001", "firm": "FundingPips", "name": "Muster 100k", "von": "admin",
                                         "aktion": "mt5_balance", "login": "12345678"}}, "CFD-Konto mit MT5-Login → mt5_balance im Namen des Besitzers")
    # 08.10.2026 (Finn: „Bei The5%ers ist CFD. Da gibt es keinen Tradovate-Nutzernamen.“): CFD nie über Tradovate
    z, f = sig(acc, "")
    check(z is None and f[0] == 409 and "CFD" in f[1] and "Tradovate" in f[1], "CFD-Konto ohne MT5-Login und ohne MT5-Nummer → 409, nie konto_balance")
    z, f = sig(dict(acc, firm="The5%ers", external_id="10000001"), "")
    check(f is None and z["params"]["aktion"] == "mt5_balance" and z["params"]["login"] == "10000001", "The5%ers ohne mt5_links, External ID = MT5-Nummer → mt5_balance mit dieser Nummer")
    z, f = sig(dict(acc, firm="Topstep"), "12345678")
    check(f is None and z["params"]["aktion"] == "konto_balance", "Futures-Firma trotz Login → konto_balance")
    for firma in ("Tradeify", "Apex Trader", "Lucid Trading", "FundedNext Futures", "MyFundedFutures", "Alpha Futures"):
        z, f = sig(dict(acc, firm=firma), "1")
        check(f is None and z["params"]["aktion"] == "konto_balance", f"{firma} → konto_balance")
    check(sig(None, "1")[1][0] == 404, "kein Konto → 404")
    check(sig(dict(acc, user_id=None), "1")[1][0] == 409, "ohne Besitzer → 409")
    check(sig(dict(acc, id="x"), "1")[1][0] == 400, "ohne id → 400")
    check(sig(dict(acc, firm=None), None)[1][0] == 409, "Firma/Login None sicher (unbekannte Firma = kein Tradovate)")
    # Route + Gate (Quelltext)
    check('daten.get("aktion") == "balance"' in src and "_wd_balance_signal(acc[0] if acc else None" in src and '"mt5_login"' in src,
          "Route: aktion 'balance' liest accounts + mt5_links und legt das Signal an")
    check('in ("endlesung_stand", "balance_stand")' in src and '"mt5_balance", "konto_balance")' in src, "balance_stand = endlesung_stand, kennt die Balance-Signale")
    check(re.search(r'akt in \("endlesung_stand", "balance_stand"\)', src) and re.search(r'akt in \("farm", "balance"\)', src), 'Gate „nur eigene“: balance → accounts, balance_stand → order_signale')
    print("OK" if ok else "FEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
