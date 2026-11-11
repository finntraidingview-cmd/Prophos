#!/usr/bin/env python3
"""Selbsttest AD1c (Master 11.11.2026): /konto-ziele liefert gewinntage.tage (Gewinn-Tage des laufenden Zyklus) und gewinntage.zyklen (alle Zyklen) —
für „Tag n/m“ je Trade im Funded-CFD-Verlauf der Account-Detail-Seite (AD1b .2174). Prüft: dieselbe Zählung wie fcp_gewinntage_ist (Zufallsvergleich),
Grenzen wie fcp_zyklus_start / kz_payouts „fcp“ (Payout-Tag gehört zum alten Zyklus), Nummer wie nrVon im Frontend, Korrektur von Hand nur im laufenden
Zyklus. Ohne Netz, Platzhalter-IDs. Aufruf: python3 tools/selftest_ad1c_gewinntage_liste.py"""
import os
import random
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


K = "a0000000-0000-0000-0000-00000000000a"
GT = {"anzahl": 3, "min": 500, "tp": [550, 650]}
_n = [0]


def tr(ende, pl, status="completed", konto=K):
    _n[0] += 1
    return {"id": f"p{_n[0]}", "master_account_id": konto, "status": status, "master_pl": pl, "ended_at": ende, "started_at": ende}


print("1) Grenzen wie fcp_zyklus_start")
PEND = [{"id": "q1", "account_id": K, "requested_at": "2026-10-10T08:00:00Z", "status": "received", "received_tx_id": "t1"},
        {"id": "q2", "account_id": K, "requested_at": None, "created_at": "2026-10-20T23:30:00Z", "status": "pending"}]   # 01:30 Berlin (Sommerzeit) am 21.10.
BUCH = [{"id": "t1", "account_id": K, "occurred_at": "2026-10-14T09:00:00Z"},     # verbucht → zählt nicht (Empfangstag)
        {"id": "t2", "account_id": K, "occurred_at": "2026-11-01"}]                # freie Buchung, reines Datum
VERW = [{"id": "m1", "account_id": K, "payout_date": "2026-11-01", "created_at": "2026-11-01T10:00:00Z"}]   # zweiter Payout am selben Tag
gz = app.fcp_zyklus_grenz_tage(PEND, VERW, BUCH, K)
check(gz == ["2026-10-10", "2026-10-21", "2026-11-01", "2026-11-01"], f"alle Payout-Tage, Berlin, doppelte bleiben, verbuchte Buchung fällt weg ({gz})")
zs = app.fcp_zyklus_start(PEND, VERW, BUCH).get(K)
check(zs == "2026-11-02", f"fcp_zyklus_start = Folgetag des letzten Grenz-Tags ({zs})")
check(len(gz) == app.fcp_payouts_zaehlen(PEND, VERW, BUCH).get(K), "Anzahl = fcp_payouts_zaehlen (Zyklus-Nummer = Anzahl + 1)")
check(app.fcp_zyklus_grenz_tage(PEND, VERW, BUCH, "anderes") == [], "fremdes Konto → nichts")

print("2) Gewinn-Tage je Zyklus")
PL = [tr("2026-10-01T09:00:00Z", 300), tr("2026-10-01T13:00:00Z", 250),       # Zyklus 1: 01.10. 550 (zwei Trades)
      tr("2026-10-05T10:00:00Z", 499.99),                                       # unter min
      tr("2026-10-10T07:00:00Z", 800),                                          # Payout-Tag 10.10. → noch Zyklus 1
      tr("2026-10-15T10:00:00Z", 600, "review"),                                # Zyklus 2, review zählt
      tr("2026-10-21T10:00:00Z", 700),                                          # Payout-Tag 21.10. (Berlin) → Zyklus 2
      tr("2026-10-25T10:00:00Z", 900), tr("2026-10-25T12:00:00Z", -500),        # Zyklus 3: 25.10. Summe 400 → zählt nicht
      tr("2026-10-28T22:30:00Z", 510),                                          # 23:30 Berlin am 28.10. (Winterzeit) → Zyklus 3
      tr("2026-11-02T10:00:00Z", 650), tr("2026-11-03T10:00:00Z", 520),         # Zyklus 5 (laufend; Zyklus 4 = leer zwischen zwei Payouts am 01.11.)
      tr("2026-11-04T10:00:00Z", 900, "open"), tr("2026-11-04T10:00:00Z", 900, konto="fremd"),
      {"id": "px", "master_account_id": K, "status": "completed", "master_pl": None, "ended_at": "2026-11-04T10:00:00Z"}]
Z = app.fcp_gewinntage_zyklen(GT, K, PL, gz, "2026-09-30T10:00:00Z")
kurz = [(z["nr"], z["seit"], z["bis"], z["laufend"], [(t["tag"], t["summe"], t["n"]) for t in z["tage"]]) for z in Z]
check(kurz == [(1, "2026-09-30", "2026-10-10", False, [("2026-10-01", 550.0, 1), ("2026-10-10", 800.0, 2)]),
               (2, "2026-10-11", "2026-10-21", False, [("2026-10-15", 600.0, 1), ("2026-10-21", 700.0, 2)]),
               (3, "2026-10-22", "2026-11-01", False, [("2026-10-28", 510.0, 1)]),
               (5, "2026-11-02", None, True, [("2026-11-02", 650.0, 1), ("2026-11-03", 520.0, 2)])],
      f"Zyklen ältester zuerst, Payout-Tag inklusive im alten Zyklus, Nummer wie nrVon (zwei Payouts am 01.11. → Zyklus 5), review zählt, Summe je Tag ({kurz})")
check(Z[0]["tage"][0]["plaene"] == ["p1", "p2"], "Plan-IDs je Tag nach Trade-Ende aufsteigend")
check(len(Z[-1]["tage"]) == app.fcp_gewinntage_ist(GT, K, PL, zs)[0], "laufender Zyklus: Anzahl = fcp_gewinntage_ist")
Zk = app.fcp_gewinntage_zyklen(GT, K, PL, gz, "2026-09-30T10:00:00Z", 1)
check([t["n"] for t in Zk[-1]["tage"]] == [2, 3] and [t["n"] for t in Zk[0]["tage"]] == [1, 2], "Korrektur +1: nur der laufende Zyklus zählt ab 2")
Zm = app.fcp_gewinntage_zyklen(GT, K, PL, gz, "2026-09-30T10:00:00Z", -1)
check([t["n"] for t in Zm[-1]["tage"]] == [None, 1] and app.fcp_gewinntage_ist(GT, K, PL, zs, -1)[0] == 1, "Korrektur −1: erster Tag zählt nicht (n None), letzter = ist")
Zc = app.fcp_gewinntage_zyklen(GT, K, PL, [], "2026-10-12T10:00:00Z")
check(len(Zc) == 1 and Zc[0]["seit"] == "2026-10-12" and Zc[0]["tage"][0]["tag"] == "2026-10-15", "ohne Payout: ein Zyklus ab dem Anlegetag (Challenge-Tage zählen nie)")
check(app.fcp_gewinntage_zyklen(None, K, PL, gz, None) is None and app.fcp_gewinntage_zyklen({"anzahl": 3, "min": 0}, K, PL, gz, None) is None,
      "Regel ohne gewinntage / min 0 → None (wie fcp_gewinntage_ist)")
check(app.fcp_gewinntage_zyklen({"anzahl": 0.5, "min": 500}, K, PL, gz, None) is None and app.fcp_gewinntage_ist({"anzahl": 0.5, "min": 500}, K, PL, None) is None,
      "anzahl 0 < x < 1 → None wie fcp_gewinntage_ist (Prüfer KANN 2)")

print("3) Zufallsvergleich mit fcp_gewinntage_ist (laufender Zyklus)")
rnd = random.Random(1111)
basis = datetime(2026, 9, 1, tzinfo=timezone.utc)
abw = []
for lauf in range(300):
    pl = [tr((basis + timedelta(hours=rnd.randint(0, 24 * 70))).isoformat(), rnd.choice([-400, 100, 250, 499, 500, 650, 900]),
             rnd.choice(["completed", "completed", "review", "open"])) for _ in range(rnd.randint(0, 25))]
    pays = [{"account_id": K, "requested_at": (basis + timedelta(hours=rnd.randint(0, 24 * 70))).isoformat()} for _ in range(rnd.randint(0, 3))]
    angelegt = (basis + timedelta(hours=rnd.randint(-48, 24 * 20))).isoformat()
    korr = rnd.choice([0, 0, 1, -1, 2])
    seit = app.fcp_gewinntage_seit(app.fcp_zyklus_start(pays, [], []).get(K), angelegt)
    soll = app.fcp_gewinntage_ist(GT, K, pl, seit, korr)
    z = app.fcp_gewinntage_zyklen(GT, K, pl, app.fcp_zyklus_grenz_tage(pays, [], [], K), angelegt, korr)
    ist = max(0, len(z[-1]["tage"]) + korr)
    nr = len(pays) + 1
    if ist != soll[0] or z[-1]["seit"] != seit or z[-1]["nr"] != nr or sum(len(x["tage"]) for x in z) > len({t["tag"] for x in z for t in x["tage"]}):
        abw.append((lauf, ist, soll, z[-1]["seit"], seit))
check(not abw, f"300 Zufallsfälle: Anzahl + Korrektur = ist, seit = fcp_gewinntage_seit, nr = Payouts + 1, kein Tag doppelt ({abw[:3]})")

print()
print("FEHLER: " + ", ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
