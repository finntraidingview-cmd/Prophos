#!/usr/bin/env python3
"""Selbsttest Blue Guardian im Funded-CFD-Planer (BG1, Finn 03.11.2026 ~23:59 Dubai). Rechnet die echten Funktionen aus app.py mit der Regel aus
sql/2026-11-03_funded_cfd_blue_guardian.sql, ohne Netz und ohne DB: Phase A (3 Gewinntage ≥ 500 $ fehlen → TP 550–650, SL 1.250–1.600), Phase B
(TP = Rest bis zum Ziel), Ziel 1.000–2.000, Hedge 1.000 € auf 8.000 $, kein Refund; Zählung nur nach dem letzten Payout; andere Firmen unverändert.

Aufruf:  python3 tools/selftest_fcp_blue_guardian.py"""
import json
import os
import random
import re
import sys
from datetime import datetime, timezone

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
sql = open(os.path.join(W, "sql", "2026-11-03_funded_cfd_blue_guardian.sql"), encoding="utf-8").read()
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


from datetime import timedelta
ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta}


def lade(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^\S)", app, re.S | re.M)
    exec(m.group(0), ns)


def ruf(fn, *a, **k):
    for _ in range(60):
        try:
            return ns[fn](*a, **k)
        except NameError as e:
            lade(str(e).split("'")[1])
    raise RuntimeError(fn)


for n in ("FCP_ERSTER_PAYOUT_STANDARD", "FCP_LOT_SCHRITT", "FCP_TP_MIN_USD", "fcp_konto_rechnen", "ap_regel_finden", "fcp_gewinntage_ist", "fcp_zyklus_start", "fcp_gewinntage_seit"):
    lade(n)
ns["_ap_tz"] = lambda name: __import__("zoneinfo").ZoneInfo(name)
BG = json.loads(re.search(r"firmen \|\| '(\[.*?\])'::jsonb", sql, re.S).group(1))[0]
check(BG["namen"][0] == "blueguardian" and BG["an"] is True and BG["erster_payout"] is False, "SQL: Firma Blue Guardian, Schlüssel blueguardian, an, kein Refund")
check(ruf("ap_regel_finden", [BG], "Blue Guardian") is BG and ruf("ap_regel_finden", [BG], "FTMO") is None, "trifft „Blue Guardian“, keine andere Firma")
jg = BG["je_groesse"]["100000"]
check(jg["ziel"] == [1000, 2000] and jg["sl"] == [1250, 1600] and jg["hedge_eur"] == 1000 and jg["dd"] == 8000 and jg["gewinntage"] == {"anzahl": 3, "min": 500, "tp": [550, 650]},
      "SQL: Ziel 1.000–2.000, SL 1.250–1.600, Hedge 1.000 € auf 8.000 $, 3 Gewinntage ≥ 500 $, Phase-A-TP 550–650")


def rechne(bal, tage, zyklus=2, rnd=None):
    return ruf("fcp_konto_rechnen", jg, float(bal), 100000, zyklus, False, 10.0, 0.85, rnd, BG, gewinntage=tage)


# Phase A
r = rechne(100000, (0, 3), zyklus=1)
check(r["aktion"] == "planen" and r["tp_art"] == "gewinntag" and r["tp"] == 600 and r["sl"] == 1425 and not r["erster_payout"],
      f"Phase A, 1. Zyklus ohne Refund: TP Mitte 600, SL Mitte 1.425 ({r.get('tp_art')}, {r.get('tp')}, {r.get('sl')}, Refund {r.get('erster_payout')})")
check(r["hedge_eur"] == 1000 and r["master_risk"] == 8000, f"Hedge 1.000 € auf 8.000 $ ({r.get('hedge_eur')}, {r.get('master_risk')})")
check(r["lots"] == 1.38 or r["lots"] == 1.37, f"Lots Mitte von [1, 1,75] wie FundedNext ({r.get('lots')})")
alle_ok, tps, sls = True, set(), set()
for seed in range(300):
    x = rechne(100000 + seed, (seed % 3, 3), rnd=random.Random(seed))
    tps.add(x.get("tp")); sls.add(x.get("sl"))
    alle_ok &= x["aktion"] == "planen" and 550 <= x["tp"] <= 650 and 1250 <= x["sl"] <= 1600 and 1 <= x["lots"] <= 1.75
check(alle_ok and len(tps) > 20, f"Phase A gewürfelt: TP immer 550–650, SL 1.250–1.600, Lots 1–1,75 ({min(tps)}–{max(tps)} / {min(sls)}–{max(sls)})")
r = rechne(101500, (2, 3))
check(r["aktion"] == "planen" and r["tp_art"] == "gewinntag", f"Ziel schon erreicht (+1.500), aber erst 2/3 Tage → weiter Phase A ({r.get('aktion')}, {r.get('tp_art')})")
r = rechne(100000, None)
check(r["aktion"] == "planen" and r["tp_art"] == "gewinntag", "Zählung nicht lesbar → Phase A (nie ein Ziel-Trade auf Verdacht)")
# Phase B
r = rechne(100600, (3, 3))
check(r["aktion"] == "planen" and r["tp_art"] == "rest" and r["tp"] == 1500 - 600 and r["tp_deckel"] is None, f"Phase B: Ziel Mitte 1.500, Gewinn 600 → TP 900 ohne Deckel ({r.get('tp_art')}, {r.get('tp')})")
r = rechne(98500, (3, 3))
check(r["tp"] == 3000 and r["tp_art"] == "rest", f"Phase B nach Verlust: TP = ganzer Rest 3.000 in einem Trade ({r.get('tp')})")
r = rechne(100950, (3, 3), rnd=random.Random(1))
check(r["aktion"] == "planen" and r["tp"] >= 250, f"Phase B kleiner Rest: mindestens FCP_TP_MIN_USD ({r.get('tp')})")
r = rechne(101000, (3, 3))
check(r["aktion"] == "ziel", f"Tage erfüllt + 1.000 $ Gewinn → Ziel erreicht → Waiting for Payout ({r.get('aktion')})")
r = rechne(92000, (0, 3))
check(r["aktion"] == "aus" and "Boden" in r["grund"], f"Balance am Boden (100k − 8.000) → aus ({r.get('grund')})")
# Zählung
plaene = [{"master_account_id": "k", "status": "completed", "master_pl": 600, "ended_at": "2026-11-01T10:00:00+00:00"},
          {"master_account_id": "k", "status": "completed", "master_pl": 480, "ended_at": "2026-11-02T10:00:00+00:00"},
          {"master_account_id": "k", "status": "completed", "master_pl": 300, "ended_at": "2026-11-03T09:00:00+00:00"},
          {"master_account_id": "k", "status": "completed", "master_pl": 250, "ended_at": "2026-11-03T12:00:00+00:00"},
          {"master_account_id": "k", "status": "completed", "master_pl": -1400, "ended_at": "2026-11-04T10:00:00+00:00"}]
check(ruf("fcp_gewinntage_ist", jg["gewinntage"], "k", plaene) == (2, 3), "Zählung: Tag mit 600 zählt, 480 nicht, 300 + 250 am selben Tag zählt, Verlust nicht → 2/3")
check(ruf("fcp_gewinntage_ist", jg["gewinntage"], "k", plaene, "2026-11-02") == (1, 3), "nur Berlin-Tage ab dem Zyklus-Beginn → 1/3")
check(ruf("fcp_gewinntage_ist", None, "k", plaene) is None, "andere Firmen ohne gewinntage → None")
zs = ruf("fcp_zyklus_start", [{"account_id": "k", "requested_at": "2026-10-20"}], [{"account_id": "k", "payout_date": "2026-10-25"}],
         [{"account_id": "k", "occurred_at": "2026-10-22"}, {"account_id": "j", "occurred_at": "2026-09-01"}])
check(zs.get("k") == "2026-10-26" and zs.get("j") == "2026-09-02", f"Zyklus-Beginn = Tag nach dem jüngsten Payout aus allen drei Quellen ({zs})")
zs = ruf("fcp_zyklus_start", [{"account_id": "k", "requested_at": "2026-11-01", "received_tx_id": "tx1"}], [],
         [{"id": "tx1", "account_id": "k", "occurred_at": "2026-11-05"}])
check(zs.get("k") == "2026-11-02", f"Gegenprüfung: verknüpfte Empfangs-Buchung (5.11.) verschiebt den Zyklus nicht, es gilt die Anfrage (1.11.) ({zs})")
zs = ruf("fcp_zyklus_start", [], [], [{"id": "tx2", "account_id": "k", "occurred_at": "2026-11-03T23:30:00+00:00"}])
check(zs.get("k") == "2026-11-05", f"Zeitstempel als Berlin-Tag (23:30 UTC = 4.11. Berlin → Zyklus ab 5.11.) ({zs})")
# Payout am Tag D: der Ziel-Trade von Tag D zählt nicht in den neuen Zyklus
pd = [{"master_account_id": "k", "status": "completed", "master_pl": 900, "ended_at": "2026-11-03T08:00:00+00:00"},
      {"master_account_id": "k", "status": "completed", "master_pl": 600, "ended_at": "2026-11-04T08:00:00+00:00"}]
seit = ruf("fcp_zyklus_start", [{"account_id": "k", "requested_at": "2026-11-03"}], [], []).get("k")
check(ruf("fcp_gewinntage_ist", jg["gewinntage"], "k", pd, seit) == (1, 3), f"Gegenprüfung: Ziel-Trade am Anfrage-Tag gehört zum alten Zyklus → 1/3 (ab {seit})")
check(ruf("fcp_gewinntage_seit", None, "2026-11-01T10:00:00+00:00") == "2026-11-01" and ruf("fcp_gewinntage_seit", "2026-11-03", "2026-10-01T10:00:00+00:00") == "2026-11-03"
      and ruf("fcp_gewinntage_seit", None, None) is None, "Untergrenze im 1. Zyklus = Anlegetag des Kontos, danach Zyklus-Beginn")
# andere Firmen unverändert
FNF = {"name": "FundedNext", "namen": ["fundednext"], "an": True}
jf = {"ziel": [1500, 1850], "sl": [1750, 2450], "lots": [1, 1.75], "hedge_eur": 1500, "dd": 10000}
r1 = ruf("fcp_konto_rechnen", jf, 100500.0, 100000, 2, False, 10.0, 0.85, None, FNF)
r2 = ruf("fcp_konto_rechnen", jf, 100500.0, 100000, 2, False, 10.0, 0.85, None, FNF, gewinntage=(0, 3))
check(r1 == r2 and r1["tp_art"] == "ziel" and "gewinntage" not in r1, "FundedNext ohne gewinntage-Regel: Ergebnis gleich, gewinntage wird ignoriert")
r = ruf("fcp_konto_rechnen", jf, 101700.0, 100000, 2, False, 10.0, 0.85, None, FNF)
check(r["aktion"] == "ziel", "FundedNext Ziel erreicht wie bisher")
# Verdrahtung
fp = app[app.index("def fcp_planen("):app.index("def fcp_sicht(")]
check('"select": "account_id,received_tx_id,requested_at,created_at"' in fp and '"select": "account_id,payout_date,created_at"' in fp and '"select": "id,account_id,occurred_at"' in fp,
      "fcp_planen liest die Payout-Daten für den Zyklus-Beginn")
check("fcp_gewinntage_seit(zyklus_ab.get(aid), a.get(\"created_at\"))" in fp and "zyklus_ab = fcp_zyklus_start(pend, verw, buch) if payouts_ok else {}" in fp and ("gewinntage=gti)" in fp or "gewinntage=gti,\n" in fp) and ('"erster_payout", "gewinntage")' in fp or '"erster_payout", "gewinntage",\n' in fp),   # O1: danach ziel_fest, on_demand
      "fcp_planen zählt die Gewinntage je Konto, reicht sie durch und schreibt sie in den Vorschlag")
zw = app[app.index("def zw_funded_cfd():"):app.index("def zw_tick(")]
check("if not gti or int(gti[0]) < int(gti[1]):\n                    _zw[\"ziele\"].pop(aid, None)" in zw and '"account_id,received_tx_id,requested_at,created_at"' in zw,
      "Gegenprüfung: Radar-Ziel fällt weg, solange Gewinntage fehlen (kein „Waiting for Payout“-Vorschlag), Boden bleibt")
check("[/blue\\s*g(u)?ardian/i, 1000, 8000]" in html, "Trade-Plan-Popup: Funded-Hedge-Vorgabe Blue Guardian 1.000 € auf 8.000 $")
print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
