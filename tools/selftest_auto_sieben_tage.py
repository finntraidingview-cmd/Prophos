#!/usr/bin/env python3
"""Selbsttest: „Letzte 7 Tage" je ID für /admin/auto-plan/ids (app.py ap_sieben_tage / _ap_ts, 08.10.2026, Master/Slave 8) —
rein rechnend, ohne Netz. Aufruf: python3 tools/selftest_auto_sieben_tage.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone}
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in ("AP_TYPEN", "AP_7T_TZ")]
    for name in ("_ap_tz", "_ap_ts", "ap_sieben_tage"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def main():
    ns = lade()
    S = ns["ap_sieben_tage"]
    f = []

    def check(ok, name):
        f.append(0 if ok else 1)
        print(("OK  " if ok else "FEHL") + " " + name)

    # jetzt = 08.10.2026 03:30 Dubai (= 07.10. 23:30 UTC) → Fenster ab 02.10.2026 00:00 Dubai (= 01.10. 20:00 UTC)
    jetzt = datetime(2026, 10, 7, 23, 30, tzinfo=timezone.utc)
    konten = {"k-1": {"user_id": "u-a", "account_type": "challenge"}, "k-2": {"user_id": "u-a", "account_type": "phase1"},
              "k-3": {"user_id": "u-a", "account_type": "challenge"}, "k-4": {"user_id": "u-b", "account_type": "phase2"},
              "k-5": {"user_id": "u-b", "account_type": "challenge", "ziel_erreicht_at": "2026-10-06 10:00:00.12345+00"},
              "k-6": {"user_id": "u-b", "account_type": "challenge", "ziel_erreicht_at": "2026-09-20T10:00:00+00:00"},
              "k-7": {"user_id": "u-a", "account_type": "phase1", "ziel_erreicht_at": "2026-10-05T10:00:00+00:00"}}
    archiv = [
        {"k-1": {"archived": True, "reason": "blown", "at": "2026-10-07T22:02:31.172Z"},           # im Fenster → geblasen
         "k-2": {"archived": True, "reason": "passed", "at": "2026-10-03T08:00:00.000Z", "successorId": "k-9"},  # bestanden
         "k-3": {"archived": True, "reason": "blown", "at": "2026-10-01T19:59:00.000Z"},           # 1 min vor dem Fenster → nicht
         "k-4": {"archived": True, "reason": "passed_pending", "at": "2026-10-01T20:00:00.000Z"},  # genau Fensterbeginn → zählt
         "k-8": {"archived": True, "reason": "blown", "at": "2026-10-05T08:00:00.000Z"}},           # Konto unbekannt/Funded → nicht
        {"k-1": {"archived": True, "reason": "blown", "at": "2026-10-07T22:05:00.000Z"},           # zweiter Nutzer, gleicher Eintrag
         "k-7": {"archived": True, "reason": "manual", "at": "2026-10-06T08:00:00.000Z"}},          # manuell zählt nicht
    ]
    plaene = [
        {"user_id": "u-a", "master_account_id": "k-1", "konto_typ": "challenge", "auto_plan": True, "status": "completed", "completed_at": "2026-10-07T21:00:00+00:00"},
        {"user_id": "u-a", "master_account_id": "k-2", "konto_typ": None, "auto_plan": True, "status": "completed", "completed_at": "2026-10-02 08:00:00.5+00"},
        {"user_id": "u-a", "master_account_id": "k-2", "konto_typ": "phase1", "auto_plan": False, "status": "completed", "completed_at": "2026-10-04T08:00:00+00:00"},
        {"user_id": "u-b", "master_account_id": "k-4", "konto_typ": "phase2", "auto_plan": True, "status": "completed", "completed_at": "2026-09-30T08:00:00+00:00"},
        {"user_id": "u-b", "master_account_id": "k-x", "konto_typ": "funded", "auto_plan": True, "status": "completed", "completed_at": "2026-10-05T08:00:00+00:00"},
        {"user_id": "u-b", "master_account_id": "k-5", "konto_typ": "challenge", "auto_plan": True, "status": "review", "ended_at": "2026-10-07T08:00:00+00:00"},
        {"user_id": "u-b", "master_account_id": "k-5", "konto_typ": "challenge", "auto_plan": True, "status": "completed", "completed_at": None, "ended_at": "2026-10-06T08:00:00+00:00"},
    ]
    out, ab = S(jetzt, konten, archiv, plaene)
    check(ab.startswith("2026-10-02T00:00:00+04:00"), f"Fenster = 7 Dubai-Tage ab 02.10. 00:00 ({ab})")
    a, b = out.get("u-a", {}), out.get("u-b", {})
    check(a.get("geblasen_7t") == 1, f"geblasen: k-1 im Fenster einmal (doppelter Eintrag), k-3 1 min vorher nicht ({a})")
    check(a.get("bestanden_7t") == 2, f"bestanden u-a: k-2 passed + k-7 Ziel-Wache (manual-Archiv zählt nicht als Grund) ({a})")
    check(b.get("bestanden_7t") == 2, f"bestanden u-b: k-4 passed_pending am Fensterbeginn + k-5 Ziel-Wache; k-6 zu alt ({b})")
    check(a.get("beendet_7t") == 2, f"beendet u-a: 2 Auto-Pläne completed (Handplan zählt nicht) ({a})")
    check(b.get("beendet_7t") == 1 and b.get("geblasen_7t") == 0,
          f"beendet u-b: Plan vom 30.09. zu alt, Funded zählt nicht, review zählt nicht, completed nur mit ended_at zählt ({b})")
    check("u-x" not in out, "ID ohne Ereignis taucht nicht auf (Aufrufer setzt 0)")

    o2, _ = S(jetzt, konten, None, plaene)
    check(o2["u-a"]["bestanden_7t"] is None and o2["u-a"]["geblasen_7t"] is None and o2["u-a"]["beendet_7t"] == 2,
          f"Archiv nicht ladbar → bestanden/geblasen null, beendet bleibt ({o2['u-a']})")
    o3, _ = S(jetzt, konten, archiv, None)
    check(o3["u-a"]["beendet_7t"] is None and o3["u-a"]["geblasen_7t"] == 1, f"Pläne nicht ladbar → beendet null ({o3['u-a']})")
    o4, _ = S(jetzt, {}, archiv, [])
    check(o4 == {}, "keine Challenge/Phase-Konten → nichts gezählt")

    T = ns["_ap_ts"]
    check(T("2026-09-24 08:46:09.72215+00") is not None and T("kaputt") is None and T(None) is None, "_ap_ts: Postgres-Form ok, Müll → None")
    print(f"{len(f) - sum(f)}/{len(f)} ok")
    sys.exit(1 if sum(f) else 0)


if __name__ == "__main__":
    main()
