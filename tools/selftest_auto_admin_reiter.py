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
    for name in ("ap_sicht_uid", "ap_eingriff_sicht", "ap_admin_reiter_ok", "ap_eingriff_admin_reiter", "ap_eingriff_filter"):
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

    # OPTION A (Finn 08.10.2026: „Alle IDs im Trade-Planer: Aurel, Chris, Finn + Pascal, Ina, Jacob, Moritz"): sicht=admin gilt nur für
    # ADMIN_EMAILS ∪ auto_plan_regeln.user_ids, nie für admin_zugang nur_eigene — sicht ist ein Client-Parameter (Slave-2-Befund)
    FP, EZ, EMIN = "u-finnpascal", "u-ezpoker", "u-emin"
    # Planer-ID (Finn + Pascal, Ina …) im Admin-Reiter → alle IDs: lesen, bestätigen/zurück/löschen, werte/nachholen, Eingriffe
    check(es(False, FP, True, False, "admin") is None, "Planer-ID im Admin-Reiter: alle IDs bestätigen/zurück/löschen/werte")
    check(su(False, FP, False, "admin", True) is None, "Planer-ID: Delta-Sicht im Admin-Reiter alle IDs")
    check(ok_(False, True, False, "admin") is True, "Planer-ID: Lese-Zugang /delta + Lauf-GET")
    check(es(False, FP, True, False, " Admin ") is None, "sicht „ Admin “ (Leerzeichen/Groß) zählt")
    # Login NICHT im Planer (EzPoker, Mike, Marco …) mit selbst gebautem sicht=admin → nichts Fremdes
    check(es(False, EZ, False, False, "admin") == EZ, "Nicht-Planer-Login mit sicht=admin: nur eigene ID (Eingriffe an fremden → 403)")
    check(su(False, EZ, False, "admin", False) == EZ, "Nicht-Planer-Login: Delta-Sicht nur eigene ID")
    check(ok_(False, False, False, "admin") is False and ok_(False, False, False, "") is False, "Nicht-Planer-Login: Lese-Routen 403")
    # Emin (admin_zugang nur_eigene) bleibt überall bei sich — auch wenn er im Planer stünde
    check(es(False, EMIN, False, True, "admin") == EMIN and es(False, EMIN, True, True, "admin") == EMIN, "Emin (nur eigene): nur eigene ID")
    check(su(False, EMIN, True, "admin", True) == EMIN, "Emin Delta-Sicht: nur eigene ID")
    check(ok_(False, False, True, "admin") is False, "Emin nicht im Planer: Lese-Zugang 403")
    # normale Trade-Planer-Seite (ohne sicht=admin) → nur eigene, auch für Planer-IDs
    check(es(False, FP, True, False) == FP and es(False, FP, True, False, "alle") == FP, "normale Planer-Seite (ohne/mit sicht=alle): nur eigene ID")
    check(su(False, FP, False, "", True) == FP and su(False, FP, False, "alle", True) == FP, "normale Planer-Seite Delta-Sicht: nur eigene ID")
    check(ok_(False, True, False, "") is True, "Planer-ID: Lese-Zugang wie bisher")
    # Admin (ADMIN_EMAILS) immer
    check(es(True, "adm", False, False) is None and su(True, "adm", False, "") is None and ok_(True, False, False, ""), "Admin (ADMIN_EMAILS): alle IDs")
    # Filter für fremde Bestätigungen
    pid = "00000000-0000-0000-0000-00000000aa01"
    p1, b1, a1 = ns["ap_eingriff_filter"]("bestaetigen", [pid], es(False, FP, True, False, "admin"))
    p2, _b, _a = ns["ap_eingriff_filter"]("bestaetigen", [pid], es(False, EZ, False, False, "admin"))
    p3, _b, _a = ns["ap_eingriff_filter"]("bestaetigen", [pid], es(False, EMIN, False, True, "admin"))
    check(p1 is not None and "user_id" not in p1 and p2.get("user_id") == f"eq.{EZ}" and p3.get("user_id") == f"eq.{EMIN}",
          "Filter: Planer-ID ohne user_id-Grenze, Nicht-Planer und Emin mit eigener ID")
    # richtung_tauschen/start/neu_starten (Finn 08.10.2026: „Ja, sollen alle dies machen können." — alle = IDs im Trade-Planer)
    ea = ns["ap_eingriff_admin_reiter"]
    check(ea(False, FP, False, "admin", True), "Eingriffe: Planer-ID im Admin-Reiter darf")
    check(not ea(False, EZ, False, "admin", False) and not ea(False, "u-mike", False, "admin"), "Eingriffe: Nicht-Planer-Login (EzPoker, Mike) → 403")
    check(not ea(False, EMIN, True, "admin", True), "Eingriffe: Emin (nur eigene) → 403, auch im Planer")
    check(not ea(False, FP, False, "", True) and not ea(False, FP, False, "alle", True), "Eingriffe auf der normalen Planer-Seite (ohne sicht=admin): 403")
    check(ea(True, "adm", False, "") and ea(True, "adm", True, ""), "Eingriffe: Admin (ADMIN_EMAILS) immer")
    print(f"{len(f) - sum(f)}/{len(f)} ok")
    sys.exit(1 if sum(f) else 0)


if __name__ == "__main__":
    main()
