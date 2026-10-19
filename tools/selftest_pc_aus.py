#!/usr/bin/env python3
"""Selbsttest: PC aus → Handy (app.py pc_aus_faelle, 19.10.2026 — Finn: „wenn der Prophos-Tab nicht erreichbar ist, heißt das meistens,
dass der PC aus ist … ich bekomme direkt am Handy eine Notification"). Rein rechnend, ohne Netz. IDs/Pläne frei erfunden.
Aufruf: python3 tools/selftest_pc_aus.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_ap_ts", "pc_aus_dauer", "pc_aus_faelle", "pc_stand_zusammenfassen")
KONSTANTEN = ("PC_STAND_LEBT_S", "PC_AUS_S", "PC_AUS_PUSH_VORLAUF_MIN")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone}
    teile = []
    for k in KONSTANTEN:
        m = re.search(rf"^{k} = .*?(?=\n\S)", src, re.M | re.S)
        teile.append(m.group(0))
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


FEHLER = []


def ok(bed, was):
    print(("OK   " if bed else "FEHL ") + was)
    if not bed:
        FEHLER.append(was)


def main():
    ns = lade()
    jetzt = datetime(2026, 10, 19, 9, 0, tzinfo=timezone.utc)
    iso = lambda dt: dt.isoformat()   # noqa: E731
    # Stand: Ina aus seit 2 Tagen, Chris lebt, Mike seit 4 min still (nicht „lebt", aber noch nicht „aus")
    rows = [{"pc_name": "pc-ina", "updated_at": iso(jetzt - timedelta(days=2)), "user_id": "ina"},
            {"pc_name": "pc-chris", "updated_at": iso(jetzt - timedelta(seconds=10)), "user_id": "chris"},
            {"pc_name": "pc-mike", "updated_at": iso(jetzt - timedelta(minutes=4)), "user_id": "mike"}]
    stand = ns["pc_stand_zusammenfassen"](rows, jetzt)
    ok(stand["ina"]["aus"] and not stand["ina"]["lebt"], "Ina: 2 T still = aus")
    ok(not stand["chris"]["aus"] and stand["chris"]["lebt"], "Chris: lebt, nicht aus")
    ok(not stand["mike"]["aus"] and not stand["mike"]["lebt"], "Mike: 4 min still = nicht lebt, aber noch nicht aus (Neuladen reißt keine Meldung)")
    plaene = [{"user_id": "ina", "start_um": iso(jetzt - timedelta(minutes=30)), "master_firm": "FTMO", "master_name": "FTMO 8634"},
              {"user_id": "ina", "start_um": iso(jetzt + timedelta(minutes=20)), "master_firm": "Tradeify", "master_name": "150k 1274"},
              {"user_id": "ina", "start_um": iso(jetzt + timedelta(hours=5)), "master_firm": "FundingPips", "master_name": "9872"},
              {"user_id": "chris", "start_um": iso(jetzt + timedelta(minutes=5)), "master_firm": "Apex", "master_name": "0021"},
              {"user_id": "mike", "start_um": iso(jetzt - timedelta(minutes=5)), "master_firm": "Topstep", "master_name": "8280"}]
    merker = {}
    f = ns["pc_aus_faelle"](stand, plaene, merker, jetzt)
    ok([x["uid"] for x in f] == ["ina"], f"nur Ina wird gemeldet (Chris lebt, Mike noch nicht aus): {[x['uid'] for x in f]}")
    ok(f and len(f[0]["plaene"]) == 2, "Ina: verpasster + in 20 min = 2 wartende, der in 5 h zählt (noch) nicht")
    ok(f and f[0]["pc"] == "pc-ina" and f[0]["alt_s"] >= 2 * 86400, "Fall trägt PC-Name und Alter")
    ok(merker["ina"]["gemeldet"] is True, "Merker gesetzt")
    f2 = ns["pc_aus_faelle"](stand, plaene, merker, jetzt + timedelta(minutes=2))
    ok(f2 == [], "zweiter Takt: nichts doppelt")
    # ohne wartende Trades keine Meldung (Wochenende Ina/EzPoker)
    m3 = {}
    f3 = ns["pc_aus_faelle"](stand, [p for p in plaene if p["user_id"] != "ina"], m3, jetzt)
    ok(f3 == [] and m3["ina"]["gemeldet"] is False, "PC aus ohne wartende Trades: keine Meldung, Merker frei")
    # PC kommt zurück → Merker frei → nächster Ausfall meldet wieder
    stand2 = dict(stand, ina=dict(stand["ina"], aus=False, lebt=True, alt_s=5))
    ns["pc_aus_faelle"](stand2, plaene, merker, jetzt + timedelta(hours=1))
    ok(merker["ina"]["gemeldet"] is False, "PC wieder da: Merker frei")
    f4 = ns["pc_aus_faelle"](stand, plaene, merker, jetzt + timedelta(hours=2))
    ok([x["uid"] for x in f4] == ["ina"], "erneuter Ausfall: wieder gemeldet")
    # Plan erst in 5 h → noch keine Meldung, später (in Reichweite) schon
    m5 = {}
    f5 = ns["pc_aus_faelle"](stand, [plaene[2]], m5, jetzt)
    ok(f5 == [], "Trade erst in 5 h: noch keine Meldung")
    f6 = ns["pc_aus_faelle"](stand, [plaene[2]], m5, jetzt + timedelta(hours=4, minutes=30))
    ok([x["uid"] for x in f6] == ["ina"], "Trade in 30 min: jetzt melden")
    ok(ns["pc_aus_dauer"](90) == "2 min" and ns["pc_aus_dauer"](7200) == "2 h" and ns["pc_aus_dauer"](3 * 86400) == "3 T", "Dauer-Text")
    print(f"{'FEHLER ' + str(len(FEHLER)) if FEHLER else 'OK'} selftest_pc_aus: PC aus + wartende Trades → eine Meldung je Ausfall")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
