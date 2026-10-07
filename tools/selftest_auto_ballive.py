#!/usr/bin/env python3
"""Selbsttest: Balance live je Plan (app.py ap_balance_live / ap_letzt_je_konto, 08.10.2026, Finn: „nur starten/bestätigen, wenn es
perfekt ist") — rein rechnend, ohne Netz. Aufruf: python3 tools/selftest_auto_ballive.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    i = src.index("def ap_balance_live(")
    j = src.index("\n\n\ndef _ap_konten_laden(", i)
    # acc_balance_wahl als Attrappe: Stand = Feld „stand" am Konto (die echte Wahl hat eigene Tests)
    ns = {"acc_balance_wahl": lambda a, e, d: (1, "USD", "TV", (a or {}).get("stand") or "")}
    for k in ("AP_GRUND_BAL_LIVE", "AP_GRUND_BAL_FEHLER"):
        exec(re.search(rf"^{k} = .*$", src, re.M).group(0), ns)
    exec(src[i:j], ns)
    return ns["ap_balance_live"], ns["ap_letzt_je_konto"], ns["ap_bal_guard"]


def main():
    live, letzt, guard = lade()
    f = []
    def check(ok, name):
        f.append(0 if ok else 1); print(("OK  " if ok else "FEHL") + " " + name)
    check(live("2026-10-07T22:13:30+00:00", "2026-10-07T20:00:00+00:00") is True, "Lesung nach dem Trade-Ende → live")
    check(live("2026-10-07T19:00:00+00:00", "2026-10-07T20:00:00+00:00") is False, "Lesung vor dem Trade-Ende → nicht live")
    check(live("", "2026-10-07T20:00:00+00:00") is False, "keine Lesung, aber beendeter Trade → nicht live")
    check(live(None, "") is True, "kein beendeter Trade → immer live (auch ohne Lesung)")
    check(live("2026-10-07 22:13:30+00", "2026-10-07T20:00:00+00:00") is True, "SQL-Form (Leerzeichen/+00) gegen PostgREST-Form")
    check(live("2026-10-07T19:59:59Z", "2026-10-07 20:00:00+00") is False, "Z-Form, eine Sekunde zu früh → nicht live")
    pl = [{"master_account_id": "k-1", "status": "completed", "ended_at": "2026-10-07T18:00:00+00:00"},
          {"master_account_id": "k-1", "status": "review", "completed_at": "2026-10-07T20:00:00+00:00"},
          {"master_account_id": "k-2", "status": "planned", "ended_at": "2026-10-07T21:00:00+00:00"},
          {"master_account_id": "k-3", "status": "completed", "ended_at": ""}]
    je = letzt(pl)
    check(je == {"k-1": "2026-10-07T20:00:00+00:00"}, f"jüngstes Ende je Konto aus review/completed, planned/leer zählen nicht ({je})")
    # Bestätigen-Guard (08.10.2026): live → None, nicht live → 400 mit Konto, Lesefehler → 503 (nie durchlassen)
    pl = [{"id": 1, "master_account_id": "k-1", "master_name": "Konto A"}, {"id": 2, "master_account_id": "k-2", "master_name": "Konto B"}]
    accs = {"k-1": {"stand": "2026-10-07T21:00:00+00:00"}, "k-2": {"stand": "2026-10-07T19:00:00+00:00"}}
    ende = {"k-1": "2026-10-07T20:00:00+00:00", "k-2": "2026-10-07T20:00:00+00:00"}
    check(guard(lambda: (pl[:1], accs, ende, {}, {})) is None, "Guard: Balance nach dem Trade-Ende gelesen → bestätigen")
    g = guard(lambda: (pl, accs, ende, {}, {}))
    check(g is not None and g[0] == 400 and "Konto B" in g[1] and "Konto A" not in g[1], f"Guard: ein Konto nicht live → 400 mit Namen ({g})")
    check(guard(lambda: (pl[1:], {}, ende, {}, {}))[0] == 400, "Guard: Konto nicht gefunden, aber Trade beendet → 400")

    def kaputt():
        raise ConnectionError("PostgREST weg")
    g = guard(kaputt)
    check(g is not None and g[0] == 503 and "nicht möglich" in g[1], f"Guard: Lesefehler → 503, nicht bestätigen ({g})")
    g = guard(lambda: (pl, None, ende, {}, {}))
    check(g is not None and g[0] == 503, f"Guard: kaputte Daten (accs None) → 503 ({g})")
    print(f"{len(f) - sum(f)}/{len(f)} ok")
    sys.exit(1 if sum(f) else 0)


if __name__ == "__main__":
    main()
