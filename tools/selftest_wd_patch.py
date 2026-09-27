#!/usr/bin/env python3
"""Selbsttest WD-PATCH (app.py, B39 28.09.2026) — master_contracts als Ganzzahl ≥ 1, rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_wd_patch.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def main():
    src = open(APP, encoding="utf-8").read()
    i = src.index("def wd_kontrakte_pruefen(")
    ns = {}
    exec(src[i:src.find("\n\n\n", i)], ns)
    exec(re.search(r"^WD_PATCH_FELDER = \{.*?\}", src, re.M | re.S).group(0), ns)
    p = ns["wd_kontrakte_pruefen"]
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)
    check("master_contracts" in ns["WD_PATCH_FELDER"], "master_contracts ist patchbar")
    check(p(3) == (3, None) and p("3") == (3, None) and p(2.0) == (2, None) and p("1") == (1, None), "3 / '3' / 2.0 / '1' gültig")
    check(all(p(v)[0] is None and p(v)[1] for v in (0, -1, 1.5, "abc", None, "", True, float("nan"))),
          "0, −1, 1.5, Text, leer, bool, NaN → Fehler (400)")
    # Vorfall 28.09.2026 22:47 UTC: Chris' Plan (Start 23:30) wurde beim Laden des Folgetags gelöscht
    from datetime import datetime, timezone
    k = src.index("def wd_plan_wegraeumbar(")
    ns2 = {"datetime": datetime, "timezone": timezone}
    exec(src[k:src.find("\n\n\n", k)], ns2)
    w = ns2["wd_plan_wegraeumbar"]
    j = datetime(2026, 9, 28, 22, 47, tzinfo=timezone.utc)
    check(w("2026-09-28T23:30:00+00:00", j) is False, "Start in 43 min → nie löschen (Chris 79633d2e)")
    check(w("2026-09-28T21:00:00+00:00", j) is False, "Start vor 1:47 h → nicht löschen")
    check(w("2026-09-28T20:00:00Z", j) is True and w(None, j) is True, "Start > 2 h her oder ohne start_um → wegräumbar")
    check(w("kaputt", j) is False, "unlesbarer start_um → stehen lassen")
    print("\nALLES GRUEN" if ok else "\nFEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
