#!/usr/bin/env python3
"""Selbsttest FTMO FUTURES 50k IM FUNDED-PLANER (Finn 03.11.2026 ~02:30 Dubai über den Eingang; app.py fdp_konto_rechnen Modus tp_modus 'rest',
sql/2026-11-03_funded_ftmo_futures.sql).

Aufruf:  python3 tools/selftest_funded_ftmo_futures.py
Ohne Netz. Regel wie die SQL-Datei. Geprüft: Ziel je Konto fest 4.750–5.000, 1 NQ, SL 750–850 (≤ Daily Loss 1.000 − 100, ≤ Abstand Liq), TP = Rest ohne Deckel
und ohne Break-even, Hedge 0,15 € je $ Abstand, Boden nachziehend mit Lock beim Start, Ziel → Winning Days; Apex unverändert (selftest_funded_planer).
Druckt die drei Beispiele für den Eingang (frisch, nach 1 und nach 2 Verlusttagen)."""
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
SQL = open(os.path.join(os.path.dirname(HIER), "sql", "2026-11-03_funded_ftmo_futures.sql"), encoding="utf-8").read()
FEHLER = []


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        FEHLER.append(text)


def block(name):
    i = SRC.index(f"\ndef {name}(") + 1
    return SRC[i:SRC.find("\n\n\n", i)]


HILFEN = ("_wd_num", "_liq_de", "_cme_handelstag", "ist_topstep_express", "liq_konto_boden", "liq_stufe", "_ap_norm", "ap_regel_finden",
          "_wd_konto_groesse", "ap_balance_live", "liq_peak", "liq_regel_waehlen", "_wd_futures_frontcode", "_ap_tz", "_ap_de")
i, j = SRC.index("FDP_TAKT_S = 300"), SRC.index('@app.route("/admin/funded-plan"')
import hashlib  # noqa: E402
ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "random": random, "time": time, "hashlib": hashlib,
      "GP_SLAVE_PPL": 0.85, "_firm_norm": lambda x: str(x or ""), "ap_planer_gruppen_ids": lambda: set(), "admin_gruppen_daten": lambda: {},
      "ap_deaktiviert_anwenden": lambda k, ids=None: k}
exec("\n".join(block(n) for n in HILFEN) + "\n" + SRC[i:j], ns)
R, ZG, JG = ns["fdp_konto_rechnen"], ns["fdp_ziel_gewinn"], ns["fdp_je_groesse"]

# Regel genau wie die SQL-Datei
REGEL = {"name": "FTMO Futures", "namen": ["ftmofutures"], "an": True, "symbol": "NQ", "lock_usd": 0, "tp_modus": "rest",
         "je_groesse": {"50000": {"ziel_gewinn": [4750, 5000], "sl": [750, 850], "kontrakte": {"1": 1}, "dd": 3000, "daily_usd": 1000, "hedge_eur": 450, "kosten_eur": 120}}}
for k in ("'tp_modus', 'rest'", "'lock_usd', 0", "jsonb_build_array(4750, 5000)", "jsonb_build_array(750, 850)", "jsonb_build_object('1', 1)", "'dd', 3000",
          "'daily_usd', 1000", "'hedge_eur', 450", "'an', true", "f->'namen' ? 'ftmofutures'"):
    check(k in SQL, f"SQL enthält {k}")
jg = JG(REGEL, 50000)
KID = "ftmo-535039"   # Platzhalter-ID, Ziel fest daraus

zg = ZG(jg, KID)
check(4750 <= zg <= 5000 and zg == ZG(jg, KID) and zg == int(zg), f"Ziel-Gewinn je Konto fest gewürfelt ({zg:.0f} $, gleich bei jedem Aufruf)")
werte = {ZG(jg, f"k{n}") for n in range(200)}
check(min(werte) >= 4750 and max(werte) <= 5000 and len(werte) > 50, f"verschiedene Konten streuen über 4.750–5.000 ({min(werte):.0f}–{max(werte):.0f})")
check(ZG({"ziel_gewinn": 12000}, KID) == 12000, "Apex: feste Zahl wie bisher")


def zeile(r):
    return (f"Balance {r['balance']:,.0f} · Liq {r['liq']:,.0f} · Ziel {r['ziel']:,.0f} · {r['kontrakte']} NQ · SL {r['sl']:,.0f} $ ({r['sl_pkt']} Pkt) · "
            f"TP {r['tp']:,.0f} $ ({r['tp_pkt']} Pkt) · Hedge {r['offen_eur']:,.0f} € ({r['verhaeltnis']} €/$): am SL +{r['hedge_sl_eur']:,.0f} €, "
            f"am TP {r['hedge_tp_eur']:,.0f} €, Fusion {r['lots']} Lot").replace(",", ".")


beispiele = []
# 1) frisch
f = R(REGEL, jg, None, 50000, 50000, 0, 50000, 50000, None, konto_id=KID)
check(f["aktion"] == "planen" and f["kontrakte"] == 1 and f["sl"] == 800 and f["tp"] == zg and f["tp_art"] == "rest" and f["liq"] == 47000
      and f["offen_eur"] == 450 and abs(f["verhaeltnis"] - 0.15) < 1e-6 and f["hedge_sl_eur"] == 120, "frisch: 1 NQ, SL 800 (Mitte), TP = Ziel, Liq 47.000, Hedge 450 €")
beispiele.append(("frisch", f))
# 2) nach einem Verlusttag am SL (−800)
v1 = R(REGEL, jg, None, 49200, 50000, 0, 50000, 50000, None, konto_id=KID)
check(v1["tp"] == zg + 800 and v1["sl"] == 800 and v1["liq"] == 47000 and v1["offen_eur"] == 330, f"nach 1 Verlusttag: TP {zg + 800:.0f} (+800), Hedge 330 €")
beispiele.append(("nach 1 Verlusttag (−800)", v1))
# 3) nach zwei Verlusttagen (−1.600)
v2 = R(REGEL, jg, None, 48400, 50000, 0, 50000, 50000, None, konto_id=KID)
check(v2["tp"] == zg + 1600 and v2["sl"] == 800 and v2["offen_eur"] == 210, f"nach 2 Verlusttagen: TP {zg + 1600:.0f}, SL 800, Hedge 210 €")
beispiele.append(("nach 2 Verlusttagen (−1.600)", v2))
# nach drei Verlusttagen: Abstand 600 → SL 600 (= Liquidation)
v3 = R(REGEL, jg, None, 47600, 50000, 0, 50000, 50000, None, konto_id=KID)
check(v3["sl"] == 600 and v3["tp"] == zg + 2400, "nach 3 Verlusttagen: SL auf den Abstand zur Liq (600), TP + 2.400")
beispiele.append(("nach 3 Verlusttagen (−2.400)", v3))
v4 = R(REGEL, jg, None, 47050, 50000, 0, 50000, 50000, None, konto_id=KID)
check(v4["aktion"] == "aus" and "zu klein" in v4["grund"], f"Abstand < 100 $: kein Trade ({v4['grund']})")
check(R(REGEL, jg, None, 46900, 50000, 0, 50000, 50000, None, konto_id=KID)["aktion"] == "aus", "unter der Liq: aus (geblowt?)")

# SL gewürfelt, Tagesgrenze
sls = [R(REGEL, jg, None, 50000, 50000, 0, 50000, 50000, random.Random(s), konto_id=KID)["sl"] for s in range(300)]
check(min(sls) >= 750 and max(sls) <= 850 and len(set(sls)) > 50, f"SL gewürfelt 750–850 ({min(sls):.0f}–{max(sls):.0f})")
check(max(sls) + ns["FDP_TAGES_PUFFER"] <= 1000 - 50, f"Tageslimit: höchster SL {max(sls):.0f} + Puffer {ns['FDP_TAGES_PUFFER']} ≤ 1.000 − 50 Schlupf-Reserve")
eng = dict(jg, daily_usd=850)
check(R(REGEL, eng, None, 50000, 50000, 0, 50000, 50000, random.Random(1), konto_id=KID)["sl"] <= 750, "kleineres Daily Loss deckelt den SL (Daily − 100)")

# Ziel, Gewinn, Lock
z = R(REGEL, jg, None, 50000 + zg, 50000 + zg, 0, 50000, 50000, None, konto_id=KID)
check(z["aktion"] == "ziel", "Ziel erreicht → Winning Days wie Apex")
g2 = R(REGEL, jg, None, 52000, 52000, 0, 50000, 50000, None, konto_id=KID)
check(g2["tp"] == zg - 2000 and g2["liq"] == 49000, f"nach +2.000: TP = Rest, Boden zieht nach (Liq {g2['liq']:.0f})")
g3 = R(REGEL, jg, None, 53500, 53500, 0, 50000, 50000, None, konto_id=KID)
check(g3["liq"] == 50000, f"Boden fest beim Start (lock 0) ab Peak 53.000 (Liq {g3['liq']:.0f})")
check(R(REGEL, jg, None, 50000 + zg + 3100, 50000 + zg + 3100, 0, 50000, 50000, None, konto_id=KID)["aktion"] == "aus", "Balance weit über Ziel → unplausibel")

# Notiz + Firma
check('"tp_art") != "rest"' in SRC and "TP = Rest bis Ziel" in SRC, "Vorschlags-Notiz für FTMO ohne Stufe")
check(ns["ap_regel_finden"]([REGEL, {"namen": ["ftmo"], "an": True}], "FTMO Futures") is REGEL, "Firma „FTMO Futures“ → Schlüssel ftmofutures, nicht FTMO CFD")

print("\nBeispiele (Konto-Ziel {:.0f} $, SL ohne Würfel = Mitte 800):".format(zg))
for name, r in beispiele:
    print(f"  {name}: {zeile(r)}")
print("\nselftest_funded_ftmo_futures: " + ("alle Prüfungen grün" if not FEHLER else f"{len(FEHLER)} FEHLER: {FEHLER}"))
sys.exit(1 if FEHLER else 0)
