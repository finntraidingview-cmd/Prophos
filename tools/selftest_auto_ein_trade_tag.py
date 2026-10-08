#!/usr/bin/env python3
"""Selbsttest: ein Trade pro Konto und Tag (app.py _ap_plan_am_tag / ap_nachplan_kandidaten, 08.10.2026 — Finn: „maximal ein Trade
pro Tag pro Account“; Vorfall: drei Apex-Konten endeten 03:57 Dubai im Tagesstopp, das Nachplanen legte für dieselben Konten neue
Trades für HEUTE an). Rein rechnend, ohne Netz. Konten frei erfunden.
Aufruf: python3 tools/selftest_auto_ein_trade_tag.py"""
import os
import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_ap_plan_am_tag", "ap_nachplan_kandidaten")
KONSTANTEN = ("AP_TYPEN", "AP_GRUND_HEUTE_GEHANDELT", "AP_NACHPLAN_FEST_GRUENDE")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime}
    teile = []
    for k in KONSTANTEN:
        m = re.search(rf"^{k} = .*?(?=\n\S)", src, re.M | re.S)
        teile.append(m.group(0))
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def main():
    ns = lade()
    am_tag, kand = ns["_ap_plan_am_tag"], ns["ap_nachplan_kandidaten"]
    tz = ZoneInfo("Europe/Berlin")
    tag = "2026-10-08"
    f = []
    ok = lambda b, t: f.append(t) if not b else None

    heute_fertig = {"master_account_id": "A", "status": "completed", "started_at": "2026-10-07T23:57:00+00:00",
                    "ended_at": "2026-10-08T00:30:00+00:00"}
    gestern_fertig = {"master_account_id": "B", "status": "completed", "started_at": "2026-10-07T08:00:00+00:00",
                      "ended_at": "2026-10-07T10:00:00+00:00"}
    ok(am_tag(heute_fertig, tag, tz) is True, "heute beendeter Trade muss den Tag belegen")
    ok(am_tag(gestern_fertig, tag, tz) is False, "gestern beendeter Trade darf heute nicht belegen")
    ok(am_tag({"status": "completed"}, tag, tz) is False, "abgehakt ohne Zeiten: nicht belegen (kein Rätselraten)")
    ok(am_tag({"status": "open"}, tag, tz) is True, "laufend belegt wie bisher")
    ok(am_tag({"status": "review"}, tag, tz) is True, "Überprüfen belegt wie bisher")
    ok(am_tag({"status": "planned", "start_um": "2026-10-08T12:00:00+00:00"}, tag, tz) is True, "geplant heute belegt wie bisher")

    typ = (ns["AP_TYPEN"] or ("challenge",))[0]
    konten = [{"id": "A", "account_type": typ}, {"id": "B", "account_type": typ}, {"id": "C", "account_type": typ}]
    out = kand(konten, [heute_fertig, gestern_fertig], tag, tz)
    ok(out == ["B", "C"], f"Kandidaten nur B und C erwartet (A hat heute gehandelt), kam {out}")
    g = ns["AP_GRUND_HEUTE_GEHANDELT"]
    ok(any(g.startswith(x) or x in g for x in ns["AP_NACHPLAN_FEST_GRUENDE"]), "Grund muss als fester Nachplan-Grund zählen")

    if f:
        print("ROT:")
        for t in f:
            print(" -", t)
        sys.exit(1)
    print("selftest_auto_ein_trade_tag: alle Prüfungen grün")


if __name__ == "__main__":
    main()
