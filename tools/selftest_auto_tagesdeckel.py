#!/usr/bin/env python3
"""Selbsttest: Tagesdeckel je Firma (app.py ap_tagesdeckel, 19.10.2026 — Finn: „2 bis 3 Trades pro ID bei Apex", CFD weiter wie
immer). Rein rechnend, ohne Netz. Konten frei erfunden.
Aufruf: python3 tools/selftest_auto_tagesdeckel.py"""
import os
import random
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_ap_norm", "ap_regel_finden", "_ap_plan_am_tag", "ap_tagesdeckel")
KONSTANTEN = ("AP_GRUND_TAGESDECKEL",)


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime}
    teile = []
    for k in KONSTANTEN:
        m = re.search(rf"^{k} = .*?(?=\n\S)", src, re.M | re.S)
        teile.append(m.group(0))
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def kand(uid, firm, n):
    return [{"a": {"id": f"{uid}-{firm}-{i}", "firm": firm, "user_id": uid}, "tkey": f"{uid}|{firm.lower()}",
             "zeile": {"user": uid, "konto_id": f"{uid}-{firm}-{i}", "firma": firm}} for i in range(n)]


def main():
    ns = lade()
    deckel = ns["ap_tagesdeckel"]
    tz = ZoneInfo("Europe/Berlin")
    tag = "2026-10-19"
    firmen = [{"namen": ["apextrader", "apex"], "max_konten_tag": [2, 3]}, {"namen": ["fundingpips"]}]
    f = []
    ok = lambda b, t: f.append(t) if not b else None

    # 1) Apex: 8 Konten einer ID → 2 oder 3 bleiben, Rest ausgelassen mit Grund; FundingPips ohne Feld: alle bleiben
    k = kand("finn", "Apex Trader", 8) + kand("finn", "FundingPips", 6)
    for seed in range(20):
        beh, raus = deckel(firmen, k, [], tag, tz, random.Random(seed))
        apex = [x for x in beh if x["a"]["firm"] == "Apex Trader"]
        ok(2 <= len(apex) <= 3, f"seed {seed}: Apex behalten {len(apex)} (soll 2–3)")
        ok(len([x for x in beh if x["a"]["firm"] == "FundingPips"]) == 6, f"seed {seed}: FundingPips angefasst")
        ok(len(raus) == 8 - len(apex), f"seed {seed}: ausgelassen {len(raus)}")
        ok(all("Tagesdeckel" in r["grund"] for r in raus), "Grund fehlt")
    # Wiederholbar mit Seed, Reihenfolge wie Kandidatenliste
    b1, _ = deckel(firmen, k, [], tag, tz, random.Random(7))
    b2, _ = deckel(firmen, k, [], tag, tz, random.Random(7))
    ok([x["a"]["id"] for x in b1] == [x["a"]["id"] for x in b2], "Seed nicht wiederholbar")
    ok([x["a"]["id"] for x in b1] == [x["a"]["id"] for x in k if x["a"]["id"] in {y["a"]["id"] for y in b1}], "Reihenfolge verändert")
    # über viele Seeds kommen 2 UND 3 vor
    zahlen = {len([x for x in deckel(firmen, kand("finn", "Apex", 8), [], tag, tz, random.Random(s))[0]]) for s in range(40)}
    ok(zahlen == {2, 3}, f"Spanne nicht gezogen: {zahlen}")

    # 2) Zwei IDs: je ID eigener Deckel
    k2 = kand("finn", "Apex", 5) + kand("pascal", "Apex", 5)
    beh, raus = deckel(firmen, k2, [], tag, tz, random.Random(1))
    for uid in ("finn", "pascal"):
        n = len([x for x in beh if x["a"]["user_id"] == uid])
        ok(2 <= n <= 3, f"{uid}: {n} behalten")

    # 3) Heute schon belegt (laufend + heute geplant + heute beendet) zählt mit; morgen geplant zählt nicht
    plaene = [{"user_id": "finn", "master_firm": "Apex Trader", "status": "open"},
              {"user_id": "finn", "master_firm": "apex", "status": "planned", "start_um": "2026-10-19T13:00:00+00:00"},
              {"user_id": "finn", "master_firm": "Apex", "status": "completed", "ended_at": "2026-10-19T01:00:00+00:00"},
              {"user_id": "finn", "master_firm": "Apex", "status": "planned", "start_um": "2026-10-20T13:00:00+00:00"},
              {"user_id": "pascal", "master_firm": "Apex", "status": "open"}]
    beh, raus = deckel(firmen, kand("finn", "Apex", 5), plaene, tag, tz, random.Random(3))
    ok(len(beh) == 0, f"3 belegt → 0 frei, aber {len(beh)} behalten")
    ok(all("3 heute schon belegt" in r["grund"] for r in raus), f"belegt-Hinweis fehlt: {raus[0]['grund'] if raus else '-'}")
    beh, raus = deckel(firmen, kand("pascal", "Apex", 5), plaene, tag, tz, random.Random(3))
    ok(1 <= len(beh) <= 2, f"1 belegt → 1–2 frei, aber {len(beh)} behalten")

    # 3b) Zwei Schreibweisen derselben Firma bei einer ID → EIN Deckel
    k3 = kand("finn", "Apex", 4) + kand("finn", "Apex Trader", 4)
    beh, _ = deckel(firmen, k3, [], tag, tz, random.Random(5))
    ok(2 <= len(beh) <= 3, f"zwei Schreibweisen: {len(beh)} behalten (soll 2–3)")

    # 4) Zahl statt Spanne, kaputtes Feld → unverändert
    beh, _ = deckel([{"namen": ["apex"], "max_konten_tag": 1}], kand("finn", "Apex", 4), [], tag, tz, random.Random(0))
    ok(len(beh) == 1, f"Zahl 1 → {len(beh)}")
    beh, _ = deckel([{"namen": ["apex"], "max_konten_tag": "x"}], kand("finn", "Apex", 4), [], tag, tz, random.Random(0))
    ok(len(beh) == 4, f"kaputtes Feld → {len(beh)}")
    beh, _ = deckel([{"namen": ["apex"], "max_konten_tag": None}], kand("finn", "Apex", 4), [], tag, tz, random.Random(0))
    ok(len(beh) == 4, f"None → {len(beh)}")

    if f:
        print("FEHLER:\n  " + "\n  ".join(f))
        sys.exit(1)
    print("OK selftest_auto_tagesdeckel: Apex 2–3 je ID und Tag, Belegung zählt, CFD unberührt, Seed wiederholbar")


if __name__ == "__main__":
    main()
