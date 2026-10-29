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
    for k in ("LT_BALANCE_SPRUNG_USD", "AP_TYPEN", "AP_HB_ECHT_QUELLEN", "AP_BLOW_AUTO_ROUTEN", "AP_NORMAL_AUTO_ROUTEN", "AP_REVIEW_WEITER_GRUENDE",
              "AP_REVIEW_WEITER_ROUTEN", "AP_REVIEW_WEITER_RANG"):
        exec(re.search(rf"^{k} = .*$", src, re.M).group(0), ns)
    for f in ("_wd_num", "lt_pl_balance", "lt_balance_sprung", "ap_echte_balancen", "ap_review_weiter_pruefen"):
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
    P = {"archived": True, "reason": "passed", "successorId": "x"}
    acc = {"account_type": "challenge"}
    # echte Puls-Endlesung, Konto per Nachfolger archiviert → abhaken
    puls = {"status": "review", "route": "tvv2", "konto_typ": "challenge",
            "mt5_baseline": {"tv": {"balance_start": 150000}, "final": {"balance_end": 153432.72, "quelle": "puls"}}}
    k = f(puls, acc, P)
    check(k == {"pl": 3432.72, "quelle": "puls", "grund": "archiviert_passed"}, "Nachfolger angelegt + echte Puls-Lesung → abhaken (+3.432,72)")
    check(f(puls, acc, {"archived": True, "reason": "passed_pending"})["grund"] == "archiviert_passed_pending", "passed_pending ebenso")
    check(f(puls, acc, None) is None, "Konto nicht weiter → bleibt im Radar")
    # MUSS 1: nur echte Ergebnisse — Aurel-Fall (nur Demo-Endlesung, master_pl ohne echte Quelle) bleibt bei Finn
    aurel = {"status": "review", "route": "tvv2", "konto_typ": "challenge", "master_pl": 2412.72,
             "mt5_baseline": {"tv": {"balance_start": 157023.64}, "final": {"balance_end": 159436.36, "quelle": "demo"}}}
    check(f(aurel, acc, P) is None, "MUSS 1: nur Demo-Endlesung → nicht automatisch (Finn hakt ab)")
    check(f(dict(aurel, pl_quelle="tv"), acc, P) == {"pl": 2412.72, "quelle": "plan_tv", "grund": "archiviert_passed"},
          "MUSS 1: master_pl mit echter pl_quelle (tv) → abhaken")
    sprung = dict(puls, mt5_baseline={"tv": {"balance_start": 150000, "today_pnl_start": 0, "datum_start": "2026-10-16"},
                                      "final": {"balance_end": 153432.72, "quelle": "puls", "today_pnl": 5000, "datum": "2026-10-16"}})
    check(f(sprung, acc, P) is None, "MUSS 1: Balance-Sprung (Differenz ≠ Tages-P&L) → Finn")
    # MUSS 2: nur echte Phasen-Schritte, Winning Days nie
    check(f(puls, {"account_type": "phase2"}, None)["grund"] == "phase_phase2", "MUSS 2: challenge → phase2 = weiter")
    check(f(puls, {"account_type": "funded"}, None)["grund"] == "phase_funded", "MUSS 2: challenge → funded = weiter")
    check(f(dict(puls, konto_typ="phase2"), {"account_type": "phase1"}, None) is None, "MUSS 2: Rückstufung (Typ-Korrektur) ≠ weiter")
    check(f(dict(puls, konto_typ="winning_days"), {"account_type": "funded"}, None) is None, "MUSS 2: winning_days-Plan auf funded-Konto ≠ weiter")
    check(f(dict(puls, konto_typ="funded"), {"account_type": "winning_days"}, None) is None, "MUSS 2: funded → winning_days nie automatisch")
    # MUSS 3: Routen und Slave
    check(f(dict(puls, route="dup"), acc, P) is None, "MUSS 3: Duplikum-Route → nicht")
    check(f(dict(puls, route="mt5"), acc, P) is None, "MUSS 3: Hedge-Route mt5 → nicht")
    check(f(dict(puls, slave_account_id="s1"), acc, P) is None, "MUSS 3: Plan mit Slave-Konto → nicht")
    check(f(dict(puls, slave_pl=-120.5), acc, P) is None, "MUSS 3: vorhandener Fusion-P&L → nicht überschreiben")
    # MUSS 4: manual (Archivieren-Knopf, auch bei geblowten Konten) und blown nie
    check(f(puls, acc, {"archived": True, "reason": "manual"}) is None, "MUSS 4: manuell archiviert → nicht")
    check(f(puls, acc, {"archived": True, "reason": "blown"}) is None, "geblowt archiviert → nicht")
    # sonst
    check(f(dict(puls, hedge_eur=120), acc, P) is None, "mit Gegenhedge → von Hand")
    man = dict(puls, mt5_baseline=dict(puls["mt5_baseline"], manuell={"at": "2026-10-16T00:00:00Z"}))
    check(f(man, acc, P) is None, "„Manuelle Arbeit“-Kennzeichen → bleibt")
    check(f(dict(puls, status="completed"), acc, P) is None, "schon abgehakt → nichts")
    check(f(dict(puls, blown=True), acc, P) is None, "blown → nichts")
    echo = {"status": "review", "route": "mt5v2", "konto_typ": "phase1",
            "mt5_baseline": {"master_balance": 100000, "bal_nach": {"ok": True, "balance": 101250}}}
    check(f(echo, {"account_type": "phase2"}, None) == {"pl": 1250.0, "quelle": "mt5_nachlesung", "grund": "phase_phase2"},
          "Echo V2: Phase 1 → Phase 2 mit Nachlesung → abhaken")

    # Nova-Endlesung aus dem TopstepX-Auge (29.10.2026): tsv2 mit final.quelle 'auge' zählt als echte Lesung, tvv2 nie
    auge = {"status": "review", "route": "tsv2", "konto_typ": "challenge",
            "mt5_baseline": {"tv": {"balance_start": 150000}, "final": {"balance_end": 150018.78, "quelle": "auge"}}}
    check(f(auge, {"account_type": "funded"}, None) == {"pl": 18.78, "quelle": "auge", "grund": "phase_funded"}, "Topstep V2 mit Auge-Endlesung → abhaken wie Puls")
    tv_auge = dict(auge, route="tvv2")
    check(f(tv_auge, {"account_type": "funded"}, None) is None, "Orbit V2 mit quelle 'auge' → nie (nur Topstep)")

    print("OK" if ok else "FEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
