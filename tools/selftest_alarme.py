#!/usr/bin/env python3
"""Selbsttest: Alarme an die Master-IDs (app.py alarm_prio_aus_titel / alarm_ereignisse, 22.10.2026 — Finn: „Notifications ans Handy …
mit den Prioritäten, wenn irgendwas schiefgeht"). Rein rechnend, ohne Netz. Zahlen frei erfunden.  Aufruf: python3 tools/selftest_alarme.py"""
import os
import re
import sys
from datetime import datetime, timezone, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_wd_num", "_ap_tz", "gp_push_ereignisse", "alarm_prio_aus_titel", "_alarm_ts", "tsx_brackets_fehlen", "_tsx_brackets_kern", "alarm_ereignisse")
KONSTANTEN = ("PULS_BILD_PFAD_RE", "ALARM_PRIO_TITEL", "HEDGE_LEBT", "ALARM_HEDGE_OFFEN_S", "ALARM_OHNE_HEDGE_S", "ALARM_HEDGE_ZU_MASTER_S",
              "ALARM_ERINNERN_S", "ALARM_RADAR_GRUENDE")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta}   # _ap_tz importiert ZoneInfo selbst
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

    # NOVA OHNE SL/TP + WIEDER OFFEN (29.10.2026, NOVA-ENDE-NUR-MIT-BEWEIS)
    bf = ns["tsx_brackets_fehlen"]
    w = "Risk 1000 $ nicht gesetzt (kein Feld); To Make 2000 $ nicht gesetzt (Dialog)"
    ok(bf("tsv2", {"warnung": w}) == {"risk": True, "tp": True}, "Warnung beide → risk+tp")
    ok(bf("tsv2", {"warnung": "To Make 2000 $ nicht gesetzt"}) == {"risk": False, "tp": True}, "Warnung nur TP")
    ok(bf("tsv2", {"warnung": "Risk steht auf 900 $ (TopstepX-Bracket), der Plan hat keinen SL"}) is None, "Risk steht → nichts fehlt")
    ok(bf("tsv2", {"brackets_fehlen": {"risk": True, "tp": False}}) == {"risk": True, "tp": False}, "Bot-Feld brackets_fehlen")
    ok(bf("tsv2", {"brackets_fehlen": {"risk": True}, "brackets_ok_at": iso(10)}) is None, "nachgewiesen → nichts fehlt")
    ok(bf("tvv2", {"warnung": w}) is None and bf("tsv2", None) is None, "nur tsv2")
    ok(bf("tsv2", {"warnung": "Brackets in TopstepX prüfen: Reiter „Positions“ unten nicht gefunden"}) == {"risk": True, "tp": True},
       "fail-closed: Reiter nicht gefunden → beide fehlen")
    ok(bf("tsv2", {"warnung": "Brackets in TopstepX prüfen: TopstepX hat eine Order abgelehnt: x; To Make 2000 $ nicht gesetzt (y)"})
       == {"risk": True, "tp": True}, "fail-closed: abgelehnt + TP → beide")
    ok(bf("tsv2", {"warnung": "Brackets in TopstepX prüfen: Risk steht auf 900 $ (TopstepX-Bracket), der Plan hat keinen SL"}) is None,
       "mit Präfix: Risk steht → nichts")
    ok(bf("tsv2", {"warnung": "Brackets in TopstepX prüfen: " + w}) == {"risk": True, "tp": True}, "mit Präfix beide")
    nova = {"user_id": "u1", "master_firm": "Topstep", "master_name": "150k …0002", "route": "tsv2", "richtung": "buy", "master_contracts": 2}
    pl2 = [
        dict(nova, id="m", status="open", started_at=iso(100), tv_w=w, tv_ein="21345.25", master_contracts=2.0),
        dict(nova, id="n", status="open", started_at=iso(100), tv_bf={"risk": False, "tp": True}, tv_ok=iso(5)),       # nachgewiesen
        dict(nova, id="o", status="review", started_at=iso(100), tv_bf={"risk": True, "tp": True}),                     # nicht mehr open
        dict(nova, id="q", status="open", started_at=iso(3000), fv={"verworfen_at": iso(30), "quelle": "demo", "grund": "demo_tp"}),
        dict(nova, id="r", status="open", started_at=iso(9000), fv={"verworfen_at": iso(5000), "quelle": "demo"}),       # alt (vor seit)
        dict(nova, id="s", status="review", started_at=iso(3000), fv={"verworfen_at": iso(30), "quelle": "demo"}),       # wieder beendet
    ]
    ev2 = {e[0].split("|")[0] + "|" + e[2]: e for e in ereig(pl2, namen, jetzt, seit)}
    em = ev2.get("m|nova_ohne_sltp")
    ok(em is not None and em[1] == 1 and em[3] == "Nova ohne SL/TP", f"m: Nova ohne SL/TP fehlt: {sorted(ev2)}")
    ok(em is not None and "BUY 2 @ 21.345,25" in em[4] and "SL (Risk) und TP (To Make)" in em[4] and "in TopstepX setzen" in em[4],
       f"m: Text {em and em[4]!r}")
    ok(em is not None and em[0] == "m|ohne_sltp|0", f"m: Schlüssel {em and em[0]}")
    ok(not any(k.startswith(("n|", "o|", "r|", "s|")) for k in ev2), f"n/o/r/s gemeldet: {sorted(ev2)}")
    eq = ev2.get("q|plan_wieder_offen")
    ok(eq is not None and eq[1] == 1 and "noch offen" in eq[4] and "TopstepX" in eq[4], f"q: wieder offen fehlt/Text: {eq}")
    # S5-Felder (9286f5f9): Objekt mit bild, Dialog-Titel, Foto-Link im Push
    bfx = bf("tsv2", {"brackets_fehlen": {"risk": False, "tp": True, "bild": "pc-abcd12/2026-10-29/20261029-060000-a1b2c3"},
                      "bracket_dialog": "Daily Loss Limit"})
    ok(bfx == {"risk": False, "tp": True, "bild": "pc-abcd12/2026-10-29/20261029-060000-a1b2c3", "dialog": "Daily Loss Limit"}, f"S5-Objekt {bfx}")
    ok(bf("tsv2", {"brackets_fehlen": True}) == {"risk": True, "tp": True}, "alter Bot: true")
    ok("bild" not in (bf("tsv2", {"brackets_fehlen": {"risk": True, "bild": "../geheim"}}) or {}), "Bild-Pfad ungültig → weg")
    ok(bf("tsv2", {"bracket_dialog": "X"}) is None, "nur Dialog, nichts fehlt → kein Alarm")
    e5 = ereig([dict(nova, id="t", status="open", started_at=iso(100), tv_bf={"risk": True, "tp": False},
                     tv_bd="Daily Loss Limit", tv_bdb="pc-abcd12/2026-10-29/20261029-060000-a1b2c3")], namen, jetzt, seit)
    ok(len(e5) == 1 and "SL (Risk) nicht gesetzt (Dialog „Daily Loss Limit“)" in e5[0][4] and "Foto" in e5[0][4]
       and len(e5[0]) == 8 and e5[0][7].endswith("#fehlerbild=pc-abcd12/2026-10-29/20261029-060000-a1b2c3"), f"Text/Link mit Dialog+Foto: {e5}")
    ok(len(ev2["m|nova_ohne_sltp"]) == 7, "ohne Foto kein Link")
    k3 = [e[0] for e in ereig([dict(pl2[0], started_at=iso(2000))], namen, jetzt, seit)]
    ok(k3 == ["m|ohne_sltp|2"], f"Erinnerung ohne SL/TP {k3}")

    # FINALER TRADEIFY GEHALTEN (29.10.2026): ⚪ einmal je Plan, kein „Richtungsschutz"
    ss = {"art": "final_halten", "at": iso(30), "naechster": "2026-10-23T12:09:00+00:00", "text": "finaler Tradeify-Trade wartet auf Gegenhedge"}
    tf = {"user_id": "u1", "master_firm": "Tradeify", "master_name": "150k …0003", "route": "tvv2", "master_tp": 2039}
    e6 = ereig([dict(tf, id="v", status="planned", ss=ss), dict(tf, id="w", status="open", ss=ss),
                dict(tf, id="x", status="planned", ss=dict(ss, at=iso(5000)))], namen, jetzt, seit)
    k6 = {e[0]: e for e in e6}
    ok(list(k6) == ["v|final_halten"], f"final_halten Schlüssel {list(k6)}")
    ok(k6.get("v|final_halten", (0, 0))[1] == 3 and "Gegenhedge" in k6["v|final_halten"][4] and "23.10. 16:09" in k6["v|final_halten"][4],
       f"final_halten Prio/Text {k6.get('v|final_halten')}")
    ok(not any("richtungsschutz" == e[2] for e in e6), "final_halten als Richtungsschutz gemeldet")
    gp = ns["gp_push_ereignisse"]([dict(tf, id="v", status="planned", ss=ss)], namen, seit)
    ok(not gp, f"gp_push meldet final_halten: {gp}")

    if f:
        print("ROT:\n  " + "\n  ".join(f))
        sys.exit(1)
    print(f"OK — alarm_ereignisse/alarm_prio_aus_titel grün")


if __name__ == "__main__":
    main()
