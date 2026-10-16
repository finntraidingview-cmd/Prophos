#!/usr/bin/env python3
"""Selbsttest REVIEW OHNE ABHAKEN (app.py ap_review_weiter_pruefen, Finn 16.10.2026): ein beendeter Plan in 'review', dessen Konto schon
weiter ist (Nachfolger/archiviert/andere Phase), wird selbst abgehakt — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_review_weiter.py
Lädt die Funktionen per Quelltext aus app.py (Muster selftest_auto_ext: app.py zieht beim Import Flask und Threads)."""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]
    ns = {}
    exec(re.search(r"^AP_REVIEW_WEITER_GRUENDE = .*$", src, re.M).group(0), ns)
    for f in ("_wd_num", "ap_echte_balancen", "ap_review_weiter_pruefen"):
        exec(block(f), ns)
    return ns


def main():
    ns = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    f = ns["ap_review_weiter_pruefen"]
    # Aurel 16.10.2026: Orbit V2, Endlesung nur Demo (Puls liest ein bestandenes Tradeify-Konto nicht mehr), Konto per Nachfolger archiviert
    aurel = {"status": "review", "route": "tvv2", "konto_typ": "challenge", "master_pl": 2412.72,
             "mt5_baseline": {"tv": {"balance_start": 157023.64}, "final": {"balance_end": 159436.36, "quelle": "demo"}}}
    acc = {"account_type": "challenge"}
    k = f(aurel, acc, {"archived": True, "reason": "passed", "successorId": "x"})
    check(k and k["pl"] == 2412.72 and k["quelle"] == "ende_demo" and k["grund"] == "archiviert_passed",
          "Aurel: Nachfolger angelegt (archiviert passed) → abhaken mit +2.412,72 aus Ende − Start (Demo, wie das Radar)")
    check(f(aurel, acc, None) is None, "Konto nicht weiter (nicht archiviert, gleiche Phase) → bleibt im Radar")
    check(f(aurel, acc, {"archived": True, "reason": "blown"}) is None, "geblowt archiviert → nicht hier (Blow-Weg / Finn)")
    check(f(aurel, {"account_type": "phase2"}, None)["grund"] == "phase_phase2", "Phase umgestellt (challenge → phase2) → abhaken")
    puls = dict(aurel, mt5_baseline={"tv": {"balance_start": 150000}, "final": {"balance_end": 153432.72, "quelle": "puls"}})
    check(f(puls, acc, {"archived": True, "reason": "passed_pending"})["quelle"] == "puls", "echte Puls-Lesung hat Vorrang")
    nur_plan = dict(aurel, mt5_baseline={})
    check(f(nur_plan, acc, {"archived": True, "reason": "manual"}) == {"pl": 2412.72, "quelle": "plan", "grund": "archiviert_manual"},
          "ohne Lesung: master_pl am Plan")
    check(f(dict(nur_plan, master_pl=None), acc, {"archived": True, "reason": "manual"}) is None, "ohne jede Zahl → bleibt im Radar")
    check(f(dict(aurel, hedge_eur=120), acc, {"archived": True, "reason": "passed"}) is None, "mit Gegenhedge (Fusion-P&L) → von Hand")
    man = dict(aurel, mt5_baseline=dict(aurel["mt5_baseline"], manuell={"at": "2026-10-16T00:00:00Z"}))
    check(f(man, acc, {"archived": True, "reason": "passed"}) is None, "„Manuelle Arbeit“-Kennzeichen → bleibt")
    check(f(dict(aurel, status="completed"), acc, {"archived": True, "reason": "passed"}) is None, "schon abgehakt → nichts")
    check(f(dict(aurel, blown=True), acc, {"archived": True, "reason": "passed"}) is None, "blown → nichts")

    print("OK" if ok else "FEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
