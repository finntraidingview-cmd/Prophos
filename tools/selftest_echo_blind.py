#!/usr/bin/env python3
"""Selbsttest: Echo blind (30.10.2026, Befund RADAR-PNL-FEHLT — Jacob …2655 Lese-EA eingefroren, Chris' PC offline): app.py lt_echo_pl_grund,
lt_echo_felder (pl_grund statt „–" im Radar), echo_frost_urteil / echo_frost_faellig (🔴 je offenem Echo-Plan, einmal + Erinnerung nach
30 min). Rein rechnend, ohne Netz. Zahlen frei erfunden.  Aufruf: python3 tools/selftest_echo_blind.py"""
import os
import re
import sys
from datetime import datetime, timezone, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_wd_num", "echo_terminal_zu", "lt_echo_pl_grund", "lt_echo_felder", "echo_frost_urteil", "echo_gesehen_belegt", "echo_frost_stufe", "echo_frost_karenz", "echo_frost_faellig")
KONSTANTEN = ("KAPITEL_TZ", "LT_ECHO_MAX_ALTER_S", "ECHO_FROST_ALT_S, ECHO_FROST_ERINNERN_S, ECHO_FROST_KARENZ_S", "ECHO_TERMINAL_ZU_TXT")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta}
    teile = []
    for k in KONSTANTEN:
        i = re.search(rf"^{re.escape(k)} = ", src, re.M).start()
        teile.append(src[i:src.index("\n", i)])
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def main():
    ns = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    jetzt = datetime(2026, 10, 29, 14, 10, tzinfo=timezone.utc).timestamp()
    iso = lambda s_vor: datetime.fromtimestamp(jetzt - s_vor, timezone.utc).isoformat()
    G = ns["lt_echo_pl_grund"]
    check(G(None, 1060, "2026-10-29T12:52:16+00:00") == "PC offline seit 16:52", "Grund: Meldung > 90 s alt → 'PC offline seit HH:MM' (Dubai)")
    check(G("Snapshot eingefroren — Lese-EA im Master-Terminal pruefen!", 3, iso(3)) == "Lese-EA eingefroren", "Grund: Copier-Hinweis eingefroren → kurz")
    check(G("warte auf Snapshot des Master-Terminals", 3, iso(3)) == "warte auf Snapshot des Master-Terminals", "Grund: anderer Hinweis gekürzt")

    F = ns["lt_echo_felder"]
    plan = {"status": "open", "mt5_baseline": {"master_balance": 98344.31}}
    frost = {"updated_at": iso(3), "note": "Snapshot eingefroren — Lese-EA …", "eq": 97751.07, "bal": 97751.07, "pos": []}
    gut = {"updated_at": iso(3), "note": None, "eq": 98500.0, "bal": 98344.31, "pos": [{"ident": "1", "volume": 1.8}]}
    frost_pos = dict(frost, pos=[{"ident": "1", "volume": 0.3}])
    frost_hd = dict(frost, hd={"288016262": [{"ticket": 1, "volume": 1.76}]})
    plan_g = dict(plan, mt5_baseline=dict(plan["mt5_baseline"], echo_pos_gesehen_at=iso(1800)))
    check(F(plan_g, frost, jetzt)["pl_grund"].startswith("Master-Terminal zu") and F(plan_g, frost, jetzt)["pl_live"] is None
          and F(plan, frost, jetzt)["pl_grund"] == "Lese-EA eingefroren"
          and F(plan_g, frost_pos, jetzt)["pl_grund"] == "Lese-EA eingefroren" and F(plan_g, frost_hd, jetzt)["pl_grund"] == "Lese-EA eingefroren",
          "Feld: eingefroren ohne Position/Hedge + Beleg → 'Master-Terminal zu …'; ohne Beleg (EA tot vor dem Einstieg) oder mit Position/Hedge → 'Lese-EA eingefroren'")
    T = ns["echo_frost_stufe"]
    check(T(frost, "Lese-EA eingefroren", True)[0] == 3 and T(frost, "Lese-EA eingefroren", True)[1].startswith("Master-Terminal zu")
          and T(frost, "Lese-EA eingefroren", False)[0] == 1 and "keine Master-Position" in T(frost, "Lese-EA eingefroren", False)[1]
          and T(frost_pos, "Lese-EA eingefroren", True) == (1, "Lese-EA eingefroren")
          and T(frost_hd, "Lese-EA eingefroren", True) == (1, "Lese-EA eingefroren")
          and T(None, "Copier-Meldung 9 min alt (PC offline?)", True)[0] == 1,
          "Alarm: Terminal zu nur mit Beleg → ⚪; ohne Beleg (Jacob-Fall), mit Position/Hedge, PC offline → 🔴")
    B = ns["echo_gesehen_belegt"]
    check(B(gut, jetzt - 600, jetzt) is True and B(dict(gut, pos=[], hd={"1": [{"ticket": 2}]}), jetzt - 600, jetzt) is True
          and B(dict(gut, pos=[]), jetzt - 600, jetzt) is False and B(frost_pos, jetzt - 600, jetzt) is False
          and B(gut, jetzt + 60, jetzt) is False and B(dict(gut, updated_at=iso(600)), jetzt - 3600, jetzt) is False and B(None, None, jetzt) is False,
          "Beleg: nur frische, nicht eingefrorene Zeile nach dem Start mit Position oder Hedge")
    check(F(plan, dict(gut, updated_at=iso(1060)), jetzt)["pl_grund"].startswith("PC offline seit"), "Feld: alt → PC offline")
    check(F(plan, None, jetzt)["pl_grund"] == "keine Copier-Meldung", "Feld: keine Zeile → keine Copier-Meldung")
    check(F(plan, gut, jetzt)["pl_grund"] is None and F(plan, gut, jetzt)["pl_live"] == 155.69, "Feld: frisch → P&L, kein Grund")
    check(F(dict(plan, status="completed"), frost, jetzt)["pl_grund"] is None, "Feld: beendeter Plan → kein Grund (nichts zu zeigen)")

    U, W = ns["echo_frost_urteil"], ns["echo_frost_faellig"]
    check(U(frost, jetzt) == (True, "Lese-EA eingefroren") and U(None, jetzt)[0] is True
          and U(dict(gut, updated_at=iso(541)), jetzt) == (True, "Copier-Meldung 9 min alt (PC offline?)")
          and U(dict(gut, updated_at=iso(400)), jetzt) == (False, "") and U(gut, jetzt) == (False, ""),
          "Wache: eingefroren / keine Zeile / > 9 min alt → gestört; 400 s alt oder frisch → ruhig")
    K = ns["echo_frost_karenz"]
    check(K(None, "Lese-EA eingefroren", jetzt) == (False, jetzt) and K(jetzt - 539, "Lese-EA eingefroren", jetzt)[0] is False
          and K(jetzt - 540, "Lese-EA eingefroren", jetzt)[0] is True and K(None, "Copier-Meldung 9 min alt (PC offline?)", jetzt)[0] is True,
          "Karenz: eingefroren erst nach 9 min durchgehend (Panel heilt vorher), Alter-Gründe sofort")
    merk = {}
    check(W(merk, "p1", jetzt) == 0, "Drossel: erste Meldung")
    merk["p1"] = {"erst": jetzt, "n": 1}
    check(W(merk, "p1", jetzt + 29 * 60) is None and W(merk, "p1", jetzt + 30 * 60) == 1, "Drossel: Erinnerung erst nach 30 min")
    merk["p1"] = {"erst": jetzt, "n": 2}
    check(W(merk, "p1", jetzt + 5 * 3600) is None, "Drossel: danach nichts mehr")

    src = open(APP, encoding="utf-8").read()
    tick = src[src.index("\ndef echo_frost_tick("):src.index("\n\n\n", src.index("\ndef echo_frost_tick("))]
    check("if prio == 3 and n:" in tick and "prio, grund = 1, roh" in tick, "Tick: Erinnerung zu einem 🔴 bleibt 🔴, nie ⚪")
    check('"art") == "echo_terminal_zu"' in tick and '"schluessel,at,art"' in tick, "Tick: nach Railway-Neustart keine Erinnerung zu einem ⚪")
    check('"echo_pos_gesehen_at"' in tick and '"p_status": "open"' in tick and "mt5_baseline_patch" in tick and "eg:mt5_baseline->>echo_pos_gesehen_at" in src,
          "Tick: Beleg dauerhaft per Merge-RPC (Guard open) am Plan, alarm_tick liest ihn mit")

    print("\n" + ("alle Tests bestanden" if ok else "FEHLER"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
