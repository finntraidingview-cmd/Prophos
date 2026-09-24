#!/usr/bin/env python3
"""Selbsttest fuer PATCH /admin/wd-plaene {aktion:'ende'} (app.py, 25.09.2026) — rein rechnend, ohne Flask/Netz.

Aufruf:  python3 tools/selftest_wd_ende.py
Laedt _wd_ende_upd per Quelltext aus app.py. Prueft: offen → review mit final/live in der Frontend-Form
(tvV2EndeSetzen + atMoveToReview), hedge und andere Baseline-Felder unveraendert; schon review → 409;
falsche Route → 409; kein Plan → 404; Grund gekuerzt, Standard 'hand'."""
import copy
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    i = src.index("def _wd_ende_upd(")
    ns = {}
    exec(src[i:src.find("\n\n\n", i)], ns)
    return ns["_wd_ende_upd"]


def main():
    f = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    hedge = {"status": "offen", "ticket": 227086304, "lots": 0.09, "sl": 30493.29}
    plan = {"id": "55eb8344-aaaa-bbbb-cccc-000000000000", "route": "tvv2", "status": "open",
            "mt5_baseline": {"tv": {"today_pnl_start": 12.5, "datum_start": "2026-09-25"}, "hedge": hedge,
                             "live": {"offen": True, "pl": 40.0, "at": "alt"}}}
    vorher = copy.deepcopy(plan)
    upd, err = f(plan, "2026-09-25T20:15:00Z", "2026-09-25", None)
    b = upd["mt5_baseline"] if upd else {}
    check(err is None and upd["status"] == "review" and upd["ended_at"] == "2026-09-25T20:15:00Z",
          "offen → review mit ended_at")
    check(b.get("final") == {"today_pnl": None, "datum": "2026-09-25", "at": "2026-09-25T20:15:00Z", "quelle": "hand", "grund": "hand"},
          "final in der Frontend-Form (today_pnl null, datum, at, quelle) + grund Standard 'hand'")
    check(b.get("live") == {"offen": False, "pl": 40.0, "at": "2026-09-25T20:15:00Z"},
          "live: offen false + at, übrige live-Felder bleiben")
    check(b.get("hedge") == hedge and b.get("tv") == vorher["mt5_baseline"]["tv"] and plan == vorher,
          "hedge und tv unverändert, Eingabe nicht mutiert")
    lang = "  Finn vom Mac beendet, weil der Tag vorbei ist und so weiter und so fort  "
    upd2, _ = f(plan, "t", "d", lang)
    g = upd2["mt5_baseline"]["final"]["grund"]
    check(g == lang.strip()[:60] and len(g) == 60 and not g.startswith(" "),
          "grund getrimmt, max. 60 Zeichen")
    check(f(dict(plan, status="review"), "t", "d")[1] == (409, "nicht offen"), "schon review → 409 nicht offen")
    check(f(dict(plan, route="tsv2"), "t", "d")[1] == (409, "nicht offen"), "falsche Route (tsv2) → 409")
    check(f(None, "t", "d")[1][0] == 404 and f({}, "t", "d")[1][0] == 404, "kein Plan → 404")
    ohne = f({"id": "x" * 12, "route": "tvv2", "status": "open", "mt5_baseline": None}, "t", "d")[0]
    check(ohne and ohne["mt5_baseline"]["final"]["quelle"] == "hand" and ohne["mt5_baseline"]["live"] == {"offen": False, "at": "t"},
          "Plan ohne Baseline: final + live neu angelegt")
    print("\n" + ("alle Tests bestanden" if ok else "FEHLER"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
