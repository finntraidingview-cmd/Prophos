#!/usr/bin/env python3
"""Selbsttest: Admin-Reiter „Trade-Planer" für jeden Admin-Login (app.py ap_eingriff_sicht / ap_admin_reiter_ok / ap_sicht_uid,
08.10.2026, Finn als „Finn + Pascal": „Im Admin soll jeder die Trades von allen sehen. Im normalen Trade-Planer sieht jeder nur die
eigenen.") — rein rechnend. Aufruf: python3 tools/selftest_auto_admin_reiter.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone}
    teile = [re.search(r"^AP_SICHT_ADMIN = .*$", src, re.M).group(0)]
    for name in ("ap_sicht_uid", "ap_eingriff_sicht", "ap_admin_reiter_ok", "ap_eingriff_filter"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    k = re.search(r"^AP_EINGRIFF_MAX = .*$", src, re.M).group(0)
    exec("\n".join([k] + teile), ns)
    return ns


def main():
    ns = lade()
    es, ok_, su = ns["ap_eingriff_sicht"], ns["ap_admin_reiter_ok"], ns["ap_sicht_uid"]
    f = []

    def check(bed, name):
        f.append(0 if bed else 1)
        print(("OK  " if bed else "FEHL") + " " + name)

    FP, FINN, EMIN = "u-finnpascal", "u-finn", "u-emin"
    # Login ohne nur_eigene im Admin-Reiter → alle IDs (im Planer oder nicht)
    check(es(False, FP, True, False, "admin") is None, "Finn + Pascal (im Planer) im Admin-Reiter: alle IDs bestätigen/zurück")
    check(es(False, FINN, False, False, "admin") is None, "Login NICHT im Planer im Admin-Reiter: alle IDs (neu seit 08.10.2026)")
    check(ok_(False, False, False, "admin") is True, "Lese-Zugang /delta + Lauf-GET: Login nicht im Planer mit sicht=admin → erlaubt")
    check(su(False, FINN, False, "admin") is None, "Delta-Sicht im Admin-Reiter: alle IDs")
    # Emin (admin_zugang nur_eigene) bleibt überall bei sich
    check(es(False, EMIN, False, True, "admin") == EMIN and es(False, EMIN, True, True, "admin") == EMIN, "Emin (nur eigene) im Admin-Reiter: nur eigene ID")
    check(ok_(False, False, True, "admin") is False, "Emin nicht im Planer: Lese-Zugang bleibt 403")
    check(su(False, EMIN, True, "admin") == EMIN, "Emin Delta-Sicht: nur eigene ID")
    # normale Trade-Planer-Seite (ohne sicht=admin) → nur eigene
    check(es(False, FP, True, False) == FP and es(False, FP, True, False, "alle") == FP, "normale Planer-Seite (ohne/mit sicht=alle): nur eigene ID")
    check(su(False, FP, False, "") == FP and su(False, FP, False, "alle") == FP, "normale Planer-Seite Delta-Sicht: nur eigene ID")
    check(ok_(False, False, False, "") is False and ok_(False, False, False, "alle") is False, "Login nicht im Planer ohne sicht=admin: 403 wie bisher")
    check(ok_(False, True, False, "") is True, "Login im Planer: Lese-Zugang wie bisher")
    # Admin unverändert, Groß/Klein egal
    check(es(True, "adm", False, False) is None and su(True, "adm", False, "") is None and ok_(True, False, False, ""), "Admin (ADMIN_EMAILS): alle IDs wie bisher")
    check(es(False, FINN, False, False, " Admin ") is None, "sicht „ Admin “ (Leerzeichen/Groß) zählt")
    # Guard für fremde Bestätigungen: ohne user_id-Filter bei alle IDs, mit Filter bei Emin
    pid = "00000000-0000-0000-0000-00000000aa01"
    p1, b1, a1 = ns["ap_eingriff_filter"]("bestaetigen", [pid], es(False, FINN, False, False, "admin"))
    p2, _b, _a = ns["ap_eingriff_filter"]("bestaetigen", [pid], es(False, EMIN, False, True, "admin"))
    check(p1 is not None and "user_id" not in p1 and p2.get("user_id") == f"eq.{EMIN}", "Filter: Admin-Reiter ohne user_id-Grenze, Emin mit eigener ID")
    print(f"{len(f) - sum(f)}/{len(f)} ok")
    sys.exit(1 if sum(f) else 0)


if __name__ == "__main__":
    main()
