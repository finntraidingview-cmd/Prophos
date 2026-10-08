#!/usr/bin/env python3
"""Selbsttest BRAUCHT DICH OHNE INZWISCHEN GEPLANTE KONTEN (app.py ap_aus_ohne_plan / ap_aus_ohne_plan_laden, 09.10.2026 — Finn mit Screenshot:
„Braucht dich" zeigte nach dem Nachtlauf weiter „nur noch 36/56/62 $ bis zum Ziel — von Hand prüfen", obwohl das Nachplanen die Klein-Trades
angelegt hatte). Rein rechnend, ohne Netz; Konten frei erfunden.
Geprüft: (1) Konto mit Plan am Lauf-Tag (planned/open/review/completed) → Zeile weg; (2) Plan an einem anderen Tag → Zeile bleibt;
(3) Zeilen, die den Plan selbst beschreiben („geplanten/laufenden Plan", „heute schon gehandelt", „noch nicht erledigt"), bleiben;
(4) ohne tag / ohne Pläne → unverändert, geplant[] und Summen unberührt; (5) Laden mit DB-Fehler → Ergebnis unverändert.
Aufruf: python3 tools/selftest_braucht_dich_geplant.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FEHLER = []


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone}
    teile = [re.search(r"^AP_AUS_PLAN_INFO = .*$", src, re.M).group(0), re.search(r"^AP_TZ_TAG = .*$", src, re.M).group(0)]
    for name in ("_ap_plan_am_tag", "ap_aus_ohne_plan", "ap_aus_ohne_plan_laden"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    a = lade()
    F = a["ap_aus_ohne_plan"]
    tz = ZoneInfo("Europe/Berlin")
    tag = "2026-10-09"
    erg = {"tag": tag, "geplant": [{"konto_id": "g-1"}], "summe": 7, "ausgelassen": [
        {"konto_id": "k-1", "grund": "nur noch 36 $ bis zum Ziel — von Hand prüfen"},
        {"konto_id": "k-2", "grund": "nur noch 56 $ bis zum Ziel — von Hand prüfen"},
        {"konto_id": "k-3", "grund": "nur noch 62 $ bis zum Ziel — von Hand prüfen"},
        {"konto_id": "k-4", "grund": "keine Balance bekannt"},
        {"konto_id": "k-5", "grund": "hat schon einen geplanten/laufenden Plan"},
        {"konto_id": "k-6", "grund": "heute schon gehandelt — ein Trade pro Konto und Tag"},
        {"konto_id": "k-7", "grund": "kein freies Zeitfenster mehr"}]}
    plaene = [
        {"master_account_id": "k-1", "status": "planned", "planned_for": tag},                                  # Klein-Trade, unbestätigt
        {"master_account_id": "k-2", "status": "open", "started_at": "2026-10-09T06:26:00+00:00"},             # läuft
        {"master_account_id": "k-3", "status": "planned", "planned_for": "2026-10-10"},                         # morgen → bleibt
        {"master_account_id": "k-5", "status": "planned", "planned_for": tag},
        {"master_account_id": "k-6", "status": "completed", "ended_at": "2026-10-09T08:00:00+00:00"},
        {"master_account_id": "k-7", "status": "review"}]
    out = F(erg, plaene, tz)
    ids = [x["konto_id"] for x in out["ausgelassen"]]
    check(ids == ["k-3", "k-4", "k-5", "k-6"], f"geplant am Tag weg (k-1 planned, k-2 open, k-7 review), Rest/Plan-Infos bleiben ({ids})")
    check(out["geplant"] == erg["geplant"] and out["summe"] == 7 and len(erg["ausgelassen"]) == 7, "geplant[], Summen und Original unberührt")
    check(F(dict(erg, tag=None), plaene, tz) == dict(erg, tag=None) and F(erg, [], tz) is erg and F(None, plaene, tz) is None,
          "ohne tag / ohne Pläne / ohne Ergebnis → unverändert")

    # Laden: Abfrage-Parameter + Fehlerweg
    L = a["ap_aus_ohne_plan_laden"]
    gefragt = []

    def sb_all(table, params):
        gefragt.append((table, params))
        return [dict(p) for p in plaene]
    a["_sb_all"] = sb_all
    a["_ap_tz"] = lambda n: tz
    out2 = L(erg)
    q = gefragt[0][1] if gefragt else {}
    check([x["konto_id"] for x in out2["ausgelassen"]] == ids and gefragt[0][0] == "trade_plans"
          and q.get("created_at") == "gte.2026-10-06" and "k-1" in q.get("master_account_id", ""),
          f"Laden: eine Abfrage trade_plans ab Tag − 3 für die ausgelassen-Konten ({q.get('created_at')})")

    def kaputt(table, params):
        raise RuntimeError("Supabase weg (Test)")
    a["_sb_all"] = kaputt
    check(L(erg) is erg, "DB-Fehler → Ergebnis unverändert (Braucht dich wie bisher)")

    print(f"\n{'ALLES OK' if not FEHLER else f'{len(FEHLER)} FEHLER'}")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
