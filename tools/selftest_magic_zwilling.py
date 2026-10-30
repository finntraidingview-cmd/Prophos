#!/usr/bin/env python3
"""Selbsttest: Magic-Zwilling-Alarm (30.10.2026, Befund ECHO-FENSTER-FEHLT): app.py zwilling_ereignisse — frische mt5_live-Zeilen mit
status.zwilling → 🔴 je PC × Config × Ticket, Besitzer aus den eigenen hedges der anderen Zeile, alte/ausgeblendete Zeilen still.
Rein rechnend, ohne Netz. Zahlen frei erfunden.  Aufruf: python3 tools/selftest_magic_zwilling.py"""
import os
import re
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone}
    teile = []
    for k in ("ZWILLING_FRISCH_S", "ZWILLING_BESITZER_S"):
        i = re.search(rf"^{k} = ", src, re.M).start()
        teile.append(src[i:src.index("\n", i)])
    i = src.index("\ndef zwilling_ereignisse(") + 1
    teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns, src


def main():
    ns, src = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    jetzt = datetime(2026, 10, 30, 0, 30, tzinfo=timezone.utc).timestamp()
    iso = lambda s_vor: datetime.fromtimestamp(jetzt - s_vor, timezone.utc).isoformat()
    zw = lambda tk: [{"ident": 500000001, "ticket": tk, "volume": 0.84, "symbol": "NAS100"}]
    rows = [
        {"pc_name": "pc-aaaaaa", "config_file": "config-a.json", "master_login": "10000001", "updated_at": iso(20), "user_id": "u1",
         "mg": 770005, "hd": {}, "zw": zw(900001)},
        {"pc_name": "pc-bbbbbb", "config_file": "config-b.json", "master_login": "10000002", "updated_at": iso(10), "user_id": "u2",
         "mg": 770005, "hd": {"500000001": [{"ticket": 900001, "volume": 0.84}]}, "zw": None},
        {"pc_name": "pc-cccccc", "config_file": "config-c.json", "master_login": "10000003", "updated_at": iso(600), "user_id": "u1",
         "mg": 770005, "hd": {}, "zw": zw(900002)},                                  # zu alt
        {"pc_name": "pc-dddddd", "config_file": "config-d.json", "master_login": "10000004", "updated_at": iso(5), "user_id": "emin",
         "mg": 770005, "hd": {}, "zw": zw(900003)},                                  # ausgeblendete Gruppe
        {"pc_name": "pc-eeeeee", "config_file": "config-e.json", "master_login": "10000005", "updated_at": iso(5), "user_id": "u3",
         "mg": 770007, "hd": {}, "zw": zw(900004)},                                  # Besitzer nicht gemeldet
    ]
    # zweiter Zwilling (dritter PC, gleiche magic) sieht dasselbe Ticket mit Besitzer → kein zweites Ereignis
    rows.append({"pc_name": "pc-gggggg", "config_file": "config-g.json", "master_login": "10000007", "updated_at": iso(8), "user_id": "u1",
                 "mg": 770005, "hd": {}, "zw": zw(900001)})
    ev = ns["zwilling_ereignisse"](rows, {"emin"}, jetzt, {"pc-aaaaaa": {"name": "Anna"}, "pc-bbbbbb": {"name": "Bert"}})
    keys = [e[0] for e in ev]
    check(keys == ["zwilling|900001|besitzer", "zwilling|900004"],
          "je Ticket EIN Ereignis (Schlüssel ohne PC/Config — zwei Zwillinge, eine Meldung); alte Zeile und ausgeblendete Gruppe still")
    check([e[1] for e in ev] == [3, 1] and ev[0][2] == "Magic-Zwilling (Hedge sicher)" and ev[1][2] == "Magic-Zwilling ohne Besitzer",
          "Besitzer führt das Ticket als eigenes → ⚪ (Hedge sicher); ohne Besitzer → 🔴")
    t = ev[0][3]
    check("PC von Anna (pc-aaaaaa)" in t and "Fusion-Ticket 900001" in t and "magic 770005" in t
          and "als eigener Hedge gemeldet von PC von Bert (pc-bbbbbb) · config-b.json (Master …0002)" in t,
          "Text nennt PC mit Namen, Ticket, magic und den PC, der das Ticket als eigenen Hedge führt")
    check("Besitzer nicht gemeldet" in ev[1][3] and ev[1][4] == "u3" and ev[0][5]["besitzer_pc"] == "pc-bbbbbb",
          "ohne Besitzer-Zeile ehrlich „nicht gemeldet“; uid und daten (besitzer_pc) gesetzt")
    zu = [{"pc_name": "pc-ffffff", "config_file": "config-f.json", "master_login": "10000006", "updated_at": iso(3), "user_id": "u1",
           "mg": 770009, "hd": {}, "zw": [{"ident": 7, "ticket": 900009, "volume": 0.5, "symbol": "NAS100", "unklar": True}],
           "zs": [500000002], "zg": "Hedge von Master-Pos 500000002 gesperrt: 3x … Master laeuft OHNE Hedge."}]
    ev2 = ns["zwilling_ereignisse"](zu, set(), jetzt)
    check([e[2] for e in ev2] == ["Alt-Hedge, Besitzer unklar", "Hedge gesperrt: Magic-Zwilling"] and [e[1] for e in ev2] == [1, 1]
          and "vor dem Copier-Update" in ev2[0][3] and ev2[1][0] == "zwilling_sperre|pc-ffffff|config-f.json|500000002" and "OHNE Hedge" in ev2[1][3],
          "unklarer Alt-Hedge 🔴 mit eigenem Titel; Sperre (Master ungehedgt) eigenes 🔴 mit dem Grund des Copiers")
    # Besitzer-PC lädt gerade neu (Zeile 10 min alt): Ticket bleibt sicher (⚪); erst über 15 min → 🔴 ohne Besitzer; Zwilling selbst zu alt → still
    bes = lambda s_vor: {"pc_name": "pc-bbbbbb", "config_file": "config-b.json", "master_login": "10000002", "updated_at": iso(s_vor),
                         "user_id": "u2", "mg": 770005, "hd": {"500000001": [{"ticket": 900001, "volume": 0.84}]}, "zw": None}
    zwr = lambda s_vor: {"pc_name": "pc-aaaaaa", "config_file": "config-a.json", "master_login": "10000001", "updated_at": iso(s_vor),
                         "user_id": "u1", "mg": 770005, "hd": {}, "zw": zw(900001)}
    e10 = ns["zwilling_ereignisse"]([zwr(20), bes(600)], set(), jetzt)
    e16 = ns["zwilling_ereignisse"]([zwr(20), bes(960)], set(), jetzt)
    eal = ns["zwilling_ereignisse"]([zwr(300), bes(10)], set(), jetzt)
    check([(e[0], e[1]) for e in e10] == [("zwilling|900001|besitzer", 3)] and [(e[0], e[1]) for e in e16] == [("zwilling|900001", 1)] and eal == [],
          "Besitzer-Zeile bis 15 min alt zählt (Tab-Neuladen nach Push → ⚪, kein 🔴); älter → 🔴; Zwillings-Zeile > 180 s → still")
    check("ZWILLING_BESITZER_S, timezone.utc)" in src, "zwilling_tick liest mt5_live bis 15 min zurück (sonst fehlten die Besitzer-Zeilen)")
    kaputt = [{"pc_name": "pc-x", "updated_at": "kaputt", "zw": zw(1)},
              {"pc_name": "pc-y", "updated_at": iso(1), "zw": [{"ticket": "x"}, "nix", {"ticket": 0}], "hd": ["falsch"]}]
    check(ns["zwilling_ereignisse"](kaputt, set(), jetzt) == [], "kaputte Zeilen/Felder werfen nicht und melden nichts")
    q = src[src.index("\ndef zwilling_tick("):src.index('\n@app.route("/alarm/heimweg"')]
    check('alarm_senden(prio, "magic_zwilling"' in q and "for key, prio, titel, text, uid, daten in evs:" in q and "alarm_im_log(" in q and '_alarm["gemeldet"]' in q and "_alarm_fremd_verwaltet" in q,
          "zwilling_tick: 🔴 an die Master-IDs, entprellt (Speicher + alarm_log 24 h), Emin-Gruppe raus")
    check("zwilling_tick(aus, jetzt.timestamp())" in src[src.index("\ndef alarm_tick("):src.index("\ndef echo_frost_urteil(")],
          "läuft im alarm_tick neben der Echo-Snapshot-Wache")
    print("\nOK" if ok else "\nFEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
