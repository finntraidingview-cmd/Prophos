#!/usr/bin/env python3
"""Selbsttest CS1 (06.11.2026): Consistency-Basis laut Broker (accounts.fcp_ziel.broker) im Funded-CFD-Planer.
Fall Moritz The5%ers 200k …26776641: Broker bester Tag = Zyklusgewinn = 1.476,59 → mit 50 % zwei Trades ~729 + ~807 → 203.012,59, bester Tag 49 %;
mit der DB-Zählung (nur 1.194,04 im Zyklus) wären es 590 + 652 → 54 %. Dazu: Gültigkeit bis zum nächsten Payout, Trades nach `at` zählen dazu,
Planer-Einhängung an den drei Stellen, broker bleibt beim Würfeln des festen Ziels erhalten."""
import os
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
import app  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


def plan(ende, pl, st="completed"):
    return {"status": st, "ended_at": ende, "master_pl": pl}


AT = "2026-11-06T13:30:00+00:00"
BROKER = {"broker": {"at": AT, "bester_tag": 1476.59, "zyklus_gewinn": 1476.59, "balance": 201476.59, "quelle": "the5ers_screenshot"}}
DB = [plan("2026-11-04T01:02:43+00:00", 1194.04)]          # einziger Trade im Zyklus (Payout 03.11. → Zyklus ab 04.11.)

# Gültigkeit
ok(app.fcp_broker_basis(BROKER, "2026-11-04") is not None, "gilt im laufenden Zyklus (Zyklus ab 04.11., Eintrag 06.11.)")
ok(app.fcp_broker_basis(BROKER, "2026-11-07") is None, "neuer Payout nach dem Eintrag (Zyklus ab 07.11.) → gilt nicht mehr")
ok(app.fcp_broker_basis(BROKER, None) is not None, "noch nie ein Payout → gilt")
ok(app.fcp_broker_basis({"usd": 1400, "zyklus": 2}, "2026-11-04") is None, "ohne broker-Schlüssel → DB")
ok(app.fcp_broker_basis({"broker": {"at": AT, "bester_tag": -1, "zyklus_gewinn": 5}}, None) is None, "Zahl < 0 → DB")
ok(app.fcp_broker_basis({"broker": {"bester_tag": 1, "zyklus_gewinn": 5}}, None) is None, "ohne at → DB")

# Werte: vor at nichts, nach at dazu
tw = app.fcp_tw_broker(DB, "2026-11-04", "2026-11-06", BROKER, "2026-11-04")
ok(tw == {"b": 1476.59, "w": 1476.59, "n": 0, "serie": 0.0, "serie_n": 0, "heute": 0.0, "broker": True}, f"Basis = Broker, DB-Trade vor at zählt nicht ({tw})")
tw_db = app.fcp_tw_broker(DB, "2026-11-04", "2026-11-06", None, "2026-11-04")
ok(tw_db["b"] == 1194.04 and tw_db["w"] == 1194.04 and "broker" not in tw_db, "ohne Eintrag = DB-Zählung unverändert (fcp_tage_zyklus_w)")
nach = DB + [plan("2026-11-07T10:00:00+00:00", 729.0)]
tw2 = app.fcp_tw_broker(nach, "2026-11-04", "2026-11-07", BROKER, "2026-11-04")
ok(tw2["b"] == 1476.59 and tw2["w"] == 2205.59 and tw2["serie"] == 729.0 and tw2["heute"] == 729.0, f"Trade nach at zählt dazu ({tw2})")
ok(app.fcp_tw_broker(DB + [{"status": "completed", "master_pl": 5}], None, None, BROKER, None) is None, "Trade ohne Zeit → None (fail-closed)")
ok(app.fcp_tw_broker(DB + [plan("2026-11-07T10:00:00+00:00", None)], None, None, BROKER, None) is None, "Trade nach at ohne P&L → None")


# Rechnung mit fcp_cons_finn (ohne Zufall = Mitte der Spanne) — Trade 1, dann Trade 2 an einem anderen Tag
def zwei_trades(b, w, z=1500):
    g = 1476.59
    r1 = app.fcp_cons_finn(50, z, g, {"b": b, "w": w, "serie": 0, "serie_n": 0, "heute": 0})
    g2 = g + r1["tp"]
    r2 = app.fcp_cons_finn(50, z, g2, {"b": max(b, r1["tp"]), "w": w + r1["tp"], "serie": r1["tp"], "serie_n": 1, "heute": 0})
    ende = round(200000 + g2 + (r2["tp"] or 0), 2)
    return r1["tp"], r2["tp"], ende, round(1476.59 / (ende - 200000) * 100, 1)


t1, t2, ende, anteil = zwei_trades(tw["b"], tw["w"])
ok((t1, t2, ende, anteil) == (729.0, 807.0, 203012.59, 49.0), f"Broker-Basis: {t1} + {t2} → {ende} · bester Tag {anteil} %")
d1, d2, dende, danteil = zwei_trades(1194.04, 1194.04)
ok((d1, d2, dende) == (590.0, 652.0, 202718.59) and danteil > 50, f"zum Vergleich DB-Basis: {d1} + {d2} → {dende} · {danteil} % (> 50 %, deshalb CS1)")
r3 = app.fcp_cons_finn(50, 1500, 3012.59, {"b": 1476.59, "w": 3012.59, "serie": 1536, "serie_n": 2, "heute": 0})
ok(r3["fertig"] is True, "nach beiden Trades: fertig (Ziel + bester Tag ≤ 50 %)")

# Einhängung an den drei Stellen + broker bleibt beim Würfeln
src = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
ok(src.count("fcp_tw_broker(") == 4, "fcp_tw_broker: Definition + Planer + Kontoliste + Konto-Kennzahlen")
ok('tage=fcp_tw_broker(pl, fcp_gewinntage_seit(zyklus_ab.get(aid), a.get("created_at")), heute_tag, a.get("fcp_ziel"),' in src, "Planer: tage= über fcp_tw_broker")
ok('tzw = fcp_tw_broker(plaene, seit, None, a.get("fcp_ziel"), z_ab)' in src, "Konto-Kennzahlen über fcp_tw_broker")
ok('zf = dict(zf, broker=alt["broker"])' in src and 'w_["fcp_ziel->broker->>at"]' in src, "festes Ziel würfeln: broker bleibt, Guard auf broker.at")
ok(app.fcp_ziel_fest(BROKER, 3, [1300, 1500], 1400) == (1400.0, True), "fcp_ziel nur mit broker → Ziel wird gewürfelt wie ohne Eintrag")

print(f"\n{len(FEHLER)} FEHLER" if FEHLER else "\nALLES GRÜN")
sys.exit(1 if FEHLER else 0)
