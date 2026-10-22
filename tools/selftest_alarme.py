#!/usr/bin/env python3
"""Selbsttest: Alarme an die Master-IDs (app.py alarm_prio_aus_titel / alarm_ereignisse, 22.10.2026 — Finn: „Notifications ans Handy …
mit den Prioritäten, wenn irgendwas schiefgeht"). Rein rechnend, ohne Netz. Zahlen frei erfunden.  Aufruf: python3 tools/selftest_alarme.py"""
import os
import re
import sys
from datetime import datetime, timezone, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_wd_num", "gp_push_ereignisse", "alarm_prio_aus_titel", "_alarm_ts", "alarm_ereignisse")
KONSTANTEN = ("ALARM_PRIO_TITEL", "HEDGE_LEBT", "ALARM_HEDGE_OFFEN_S", "ALARM_OHNE_HEDGE_S", "ALARM_HEDGE_ZU_MASTER_S",
              "ALARM_ERINNERN_S", "ALARM_RADAR_GRUENDE")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta}
    teile = []
    for k in KONSTANTEN:
        i = re.search(rf"^{k} = ", src, re.M).start()
        teile.append(src[i:src.index("\n", i)] if not src[i:src.index("\n", i)].rstrip().endswith(",")
                     else src[i:src.index("))\n", i) + 2])
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def main():
    ns = lade()
    prio, ereig = ns["alarm_prio_aus_titel"], ns["alarm_ereignisse"]
    f = []
    ok = lambda b, t: f.append(t) if not b else None

    # Einstufung der bestehenden Meldungen
    for titel, p in (("⚠ Gegenhedge", 1), ("🖥 PC aus · Ina", 2), ("💀 Geblowt", 2), ("🗄 Konto weg", 2), ("🎯 Ziel erreicht", 3),
                     ("Trade läuft", 3), ("Trade beendet", 3), ("Irgendwas Neues", 3), ("Mike: ⚠ Trade nicht gestartet", 2)):
        ok(prio(titel) == p, f"Stufe {titel!r}: {prio(titel)} statt {p}")

    jetzt = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)
    iso = lambda s: (jetzt - timedelta(seconds=s)).isoformat()
    seit = iso(1200)
    namen = {"u1": "Finn + Pascal"}
    basis = {"user_id": "u1", "master_firm": "Lucid Trading", "master_name": "150k …0001", "route": "tvv2", "orbit_v3": True,
             "hedge_eur": "3500"}
    plaene = [
        dict(basis, id="a", status="completed", final_at=iso(120), hedge={"status": "offen", "lots": 14.9, "symbol": "NAS100"}),
        dict(basis, id="b", status="completed", final_at=iso(20), hedge={"status": "offen"}),                     # erst 20 s → still
        dict(basis, id="c", status="open", started_at=iso(200), hedge=None),                                         # ohne Hedge
        dict(basis, id="d", status="open", started_at=iso(30), hedge=None),                                          # zu früh
        dict(basis, id="e", status="open", started_at=iso(600), hedge={"status": "geschlossen", "closed_at": iso(400), "grund": "level_tp"}),
        dict(basis, id="f", status="open", started_at=iso(600), hedge={"status": "geschlossen", "closed_at": iso(10), "grund": "level_tp"}),
        dict(basis, id="g", status="completed", final_at=iso(300), hedge={"status": "geschlossen", "closed_at": iso(300), "grund": "tp_feed"}),
        dict(basis, id="h", status="completed", final_at=iso(300), hedge={"status": "geschlossen", "closed_at": iso(300), "grund": "master_ende_reader"}),
        dict(basis, id="i", status="open", started_at=iso(600), hedge={"status": "offen", "close_fehler": "Panel nicht erreichbar"}),
        dict(basis, id="j", status="open", started_at=iso(600), orbit_v3=False, hedge_eur=None, route="mt5v2", hedge=None),  # Echo V2
        dict(basis, id="k", status="completed", final_at=iso(4000), hedge={"status": "geschlossen", "closed_at": iso(4000), "grund": "sl_feed"}),
        dict(basis, id="l", status="open", started_at=iso(60), sf={"status": "rot", "at": iso(60), "msg": "Konto nicht im Login"}),
    ]
    ev = {e[0].split("|")[0] + "|" + e[2]: e for e in ereig(plaene, namen, jetzt, seit)}
    ok("a|hedge_offen" in ev and ev["a|hedge_offen"][1] == 1, f"a: Hedge offen nach Master-Ende fehlt: {sorted(ev)}")
    ok("14.9 Lot NAS100" in ev.get("a|hedge_offen", ("",) * 5)[4], "a: Lots nicht im Text")
    ok(not any(k.startswith("b|") for k in ev), "b: 20 s nach Ende schon gemeldet")
    ok("c|ohne_hedge" in ev and ev["c|ohne_hedge"][1] == 1, "c: Master ohne Hedge fehlt")
    ok(not any(k.startswith("d|") for k in ev), "d: 30 s nach Start schon gemeldet")
    ok("e|ohne_hedge" in ev, "e: Hedge seit 400 s zu, Master offen fehlt")
    ok(not any(k.startswith("f|") for k in ev), "f: Hedge erst 10 s zu → gemeldet")
    ok("g|radar_schloss" in ev and ev["g|radar_schloss"][1] == 2, "g: Radar-Schluss fehlt")
    ok(not any(k.startswith("h|") for k in ev), "h: normaler Userscript-Schluss gemeldet")
    ok("i|hedge_close_fehler" in ev, "i: Close-Fehler fehlt")
    ok(not any(k.startswith("j|") for k in ev), "j: Echo V2 ohne Hedge gemeldet")
    ok(not any(k.startswith("k|") for k in ev), "k: alter Radar-Schluss (vor seit) gemeldet")
    ok("l|nicht_gestartet" in ev and ev["l|nicht_gestartet"][1] == 2, "l: Start-Fehler fehlt")
    ok(not any(e[2] == "gestartet" for e in ev.values()), "Start wird doppelt gemeldet (push_trade_wache macht das)")

    # Erinnerung: neuer Schlüssel je 15 min, höchstens 3
    k1 = [e[0] for e in ereig([dict(plaene[0], final_at=iso(1000))], namen, jetzt, seit)]
    k2 = [e[0] for e in ereig([dict(plaene[0], final_at=iso(9000))], namen, jetzt, seit)]
    ok(k1 == ["a|hedge_offen|1"] and k2 == ["a|hedge_offen|3"], f"Erinnerungs-Schlüssel {k1} {k2}")

    if f:
        print("ROT:\n  " + "\n  ".join(f))
        sys.exit(1)
    print(f"OK — alarm_ereignisse/alarm_prio_aus_titel grün")


if __name__ == "__main__":
    main()
