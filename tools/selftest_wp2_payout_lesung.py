#!/usr/bin/env python3
"""Selbsttest WP2 (Master 23.11.2026, Befund WP1): nach einer Payout-Anfrage stellt der Funded-CFD-Planer ein Konto erst wieder auf
„Ziel erreicht → Waiting for Payout“, wenn eine ECHTE Balance-Lesung (accounts.tv_balance_at) NACH Anfrage/Auszahlung vorliegt — der
Echo-Heartbeat (mt5_live.updated_at, auch im Standby frisch) zählt dafür nicht. Ohne Lesung: ausgelassen mit FCP_GRUND_PAYOUT_UNGELESEN.
Fälle nachgebaut mit den Werten aus der DB (Logins/Namen durch Platzhalter ersetzt): Konto A FundedNext (Lesung vor der Anfrage → halten),
Konto B FundedNext und Konto C FundingPips (echte Lesung nach dem Payout zeigt keinen Abzug → weiter Waiting, das ist Fall B, nicht WP2),
Normalfall (Lesung nach dem Payout zeigt Abzug → planen, kein Waiting), dazu 72-h-Fenster unverändert.
Ohne Netz, schreibt nichts. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_wp2_payout_lesung.py"""
import json
import os
import re
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


T = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))   # noqa: E731

print("1) fcp_payout_bezug")
b = app.fcp_payout_bezug([
    {"account_id": "m", "created_at": "2026-11-18T22:37:12+00:00", "approved_at": "2026-11-19T13:14:42+00:00"},
    {"account_id": "j", "created_at": "2026-11-01T23:35:05+00:00", "approved_at": None},
    {"account_id": "j", "created_at": "2026-11-17T23:27:40+00:00", "approved_at": "2026-11-17T23:56:55+00:00"},
    {"account_id": "x", "created_at": None, "approved_at": None},
])
check(b.get("m") == T("2026-11-19T13:14:42+00:00"), "Auszahlung bestätigt nach der Anfrage → Bezug = approved_at")
check(b.get("j") == T("2026-11-17T23:56:55+00:00"), "mehrere Payouts → jüngster Zeitpunkt über alle Zeilen")
check("x" not in b, "Zeile ohne Zeitpunkte zählt nicht")

print("2) fcp_payout_lesung_fehlt")
BEZ = T("2026-11-19T13:14:42+00:00")
check(app.fcp_payout_lesung_fehlt(BEZ, [], {"tv_balance": 104915.95, "tv_balance_at": "2026-11-18T14:35:57+00:00"}) is True,
      "Konto A: letzte Lesung vor dem Payout → Lesung fehlt")
check(app.fcp_payout_lesung_fehlt(BEZ, [], {"tv_balance": 104915.95, "tv_balance_at": "2026-11-22T21:31:35+00:00"}) is False,
      "Lesung nach dem Payout → Ziel darf zählen")
check(app.fcp_payout_lesung_fehlt(BEZ, [], {"tv_balance": None, "tv_balance_at": "2026-11-22T21:31:35+00:00"}) is True,
      "Lesung ohne Wert zählt nicht")
check(app.fcp_payout_lesung_fehlt(BEZ, [], {}) is True, "nie gelesen → Lesung fehlt")
check(app.fcp_payout_lesung_fehlt(BEZ, [{"status": "completed", "ended_at": "2026-11-20T10:00:00+00:00"}], {}) is False,
      "Trade nach dem Payout zu Ende → Balance enthält den Trade, Regel greift nicht (wie bisher)")
check(app.fcp_payout_lesung_fehlt(BEZ, [{"status": "open", "ended_at": "2026-11-20T10:00:00+00:00"},
                                         {"status": "completed", "ended_at": "2026-11-18T14:35:00+00:00"}], {}) is True,
      "nur offene oder ältere Trades → Lesung fehlt weiter")
check(app.fcp_payout_lesung_fehlt(BEZ, [], {"tv_balance": 100000.0, "tv_balance_at": "2026-11-22T21:31:35+00:00"}, 104915.95) is True,
      "Gegenprüfung: Lesung nach dem Payout zeigt 100.000, Planer rechnet mit eingefrorenem Echo 104.915,95 → weiter halten")
check(app.fcp_payout_lesung_fehlt(BEZ, [], {"tv_balance": 101701.97, "tv_balance_at": "2026-11-22T21:31:35+00:00"}, 101702.5) is False,
      "Lesung nach dem Payout passt zur Planer-Balance (± 1 $) → Ziel darf zählen")
check(app.fcp_payout_lesung_fehlt(None, [], {}) is False, "ohne Payout → Regel greift nie")
check(app.fcp_payout_lesung_fehlt("2026-11-19T13:14:42+00:00", [], {"tv_balance": 1, "tv_balance_at": "2026-11-19T13:14:43+00:00"}) is False,
      "Bezug als ISO-Text geht auch")

print("3) Ganzer Lauf gegen nachgebaute DB (trocken)")
sql = open(os.path.join(WURZEL, "sql", "2026-10-30_funded_cfd_planer.sql"), encoding="utf-8").read()
FIRMEN = json.loads(re.search(r"'(\[\s*\{.*?\]\s*)'::jsonb", sql, re.S).group(1))
PPL = {"fundednext": 10.0, "fundingpips": 20.0}
JETZT = datetime(2026, 11, 23, 4, 0, tzinfo=timezone.utc)          # Montag 08:00 Dubai
H1 = "11111111-1111-1111-1111-111111111111"
HEARTBEAT = (JETZT - timedelta(minutes=2)).isoformat()               # Echo-Heartbeat frisch — auch im Standby


def konto(i, n, f, bal, tv_at, **x):
    return dict({"id": i, "user_id": H1, "name": n, "firm": f, "account_type": "funded_cfd", "external_id": "L" + i[-4:],
                 "tv_balance": bal, "tv_balance_at": tv_at, "created_at": "2026-10-01T00:00:00+00:00"}, **x, _bal=bal)


KONTO_A = konto("b2000000-0000-0000-0000-000000000001", "100k 1 → Funded", "FundedNext", 104915.95, "2026-11-18T14:35:57+00:00")
KONTO_B = konto("b2000000-0000-0000-0000-000000000002", "100k 2 → Funded", "FundedNext", 101701.97, "2026-11-22T21:31:35+00:00")
KONTO_C = konto("b2000000-0000-0000-0000-000000000003", "100k 3 → Funded", "FundingPips", 101528.60, "2026-11-22T11:40:19+00:00")
NORMAL = konto("b2000000-0000-0000-0000-000000000004", "100k 4 → Funded", "FundedNext", 100000.00, "2026-11-21T09:00:00+00:00")
FRISCH = konto("b2000000-0000-0000-0000-000000000005", "100k 5 → Funded", "FundedNext", 104000.00, "2026-11-22T22:00:00+00:00")
KONTEN = [KONTO_A, KONTO_B, KONTO_C, NORMAL, FRISCH]
# Letzter Trade je Konto (vor dem Payout) — so steht es in der DB
TRADES = [{"id": "t" + a["id"][-1], "user_id": H1, "master_account_id": a["id"], "master_firm": a["firm"], "status": "completed",
           "started_at": s, "ended_at": e, "completed_at": e, "master_pl": pl, "notes": "Funded-CFD-Planer · Vorschlag", "planned_for": e[:10]}
          for a, s, e, pl in ((KONTO_A, "2026-11-18T13:27:15+00:00", "2026-11-18T14:35:34+00:00", 79.34),
                              (KONTO_B, "2026-11-03T02:19:19+00:00", "2026-11-03T13:31:42+00:00", 1701.97),
                              (KONTO_C, "2026-11-04T02:52:49+00:00", "2026-11-04T10:25:56+00:00", 1533.75),
                              (NORMAL, "2026-11-10T08:00:00+00:00", "2026-11-10T09:00:00+00:00", 2100.00),
                              (FRISCH, "2026-11-19T08:00:00+00:00", "2026-11-19T09:00:00+00:00", 2000.00))]
PEND = [{"account_id": KONTO_A["id"], "received_tx_id": None, "requested_at": "2026-11-18", "created_at": "2026-11-18T22:37:12+00:00",
         "approved_at": "2026-11-19T13:14:42+00:00"},
        {"account_id": KONTO_B["id"], "received_tx_id": None, "requested_at": "2026-11-01", "created_at": "2026-11-01T23:35:05+00:00", "approved_at": None},
        {"account_id": KONTO_B["id"], "received_tx_id": None, "requested_at": "2026-11-18", "created_at": "2026-11-17T23:27:40+00:00",
         "approved_at": "2026-11-17T23:56:55+00:00"},
        {"account_id": KONTO_C["id"], "received_tx_id": None, "requested_at": "2026-11-18", "created_at": "2026-11-18T18:33:00+00:00",
         "approved_at": "2026-11-20T04:37:33+00:00"},
        {"account_id": NORMAL["id"], "received_tx_id": None, "requested_at": "2026-11-11", "created_at": "2026-11-11T08:00:00+00:00",
         "approved_at": "2026-11-12T08:00:00+00:00"},
        # 72-h-Fenster: Anfrage vor 10 h, Lesung danach, Balance noch alt → weiter der bisherige Text (unverändert)
        {"account_id": FRISCH["id"], "received_tx_id": None, "requested_at": "2026-11-22", "created_at": (JETZT - timedelta(hours=10)).isoformat(),
         "approved_at": None}]
REG = {"id": 1, "aktiv": False, "auto_bestaetigen": False, "ziel_auto_wartet": False, "user_ids": [H1], "firmen": FIRMEN,
       "zeiten": {"firma_abstand_min": 15, "abstand_id_min": 10, "vorlauf_min": 15}}
GESCHRIEBEN = []


def sb_select(t, p):
    if t == "funded_cfd_plan_regeln":
        return [REG]
    if t == "auto_plan_regeln":
        return [{"zeiten": {"fenster_tz": "Asia/Dubai", "fenster": [["04:00", "18:00"]]}}]
    return []


def sb_all(t, p):
    if t == "accounts" and p.get("account_type") == "eq.funded_cfd":
        return [{k: v for k, v in a.items() if k != "_bal"} for a in KONTEN]
    if t == "accounts":
        return [{"id": "f1", "user_id": H1, "external_id": "900001", "name": "Fusion f1", "firm": "Fusion Markets"}]
    if t == "trade_plans" and "master_account_id" in p:
        return [dict(x) for x in TRADES]
    if t == "trade_plans":
        return []
    if t == "pending_payouts":
        check("approved_at" in str(p.get("select")), "Planer lädt approved_at aus pending_payouts") if not GELADEN else None
        GELADEN.append(1)
        return [dict(x) for x in PEND]
    if t == "user_settings":
        return [{"user_id": H1, "value": {"accountId": "f1"}}]
    if t == "firm_specs":
        return [{"user_id": H1, "name": n, "ppl": PPL[app._ap_norm(n)], "unit": "Lots"} for n in ("FundedNext", "FundingPips")]
    if t == "id_gruppe_mitglied":
        return [{"user_id": H1, "gruppe_id": "ht"}]
    return []


GELADEN = []
app.sb_select, app._sb_all = sb_select, sb_all
app.sb_insert = lambda t, z: GESCHRIEBEN.append((t, z))
app.sb_update = lambda *a: GESCHRIEBEN.append(("update",) + a)
app._ap_archiviert = lambda streng=False: set()
app._ap_namen = lambda: ({H1: "HT-1"}, set())
# Echo liefert für alle Konten die Planer-Balance mit frischem Heartbeat (wie mt5_live im Standby)
app._ap_balance_karten = lambda: ({a["external_id"]: (a["_bal"], "USD", HEARTBEAT) for a in KONTEN}, {})
erg = app.fcp_planen(trocken=True, jetzt=JETZT, seed=7)
ziel = {z["konto_id"]: z for z in erg.get("ziel") or []}
aus = {z["konto_id"]: z for z in erg.get("ausgelassen") or []}
gepl = {z["konto_id"]: z for z in erg.get("geplant") or []}
for z in erg.get("ziel") or []:
    print(f"     ZIEL {z['konto']}: {z.get('grund')}")
for z in erg.get("ausgelassen") or []:
    print(f"     AUS  {z['konto']}: {z.get('grund')}")
for z in erg.get("geplant") or []:
    print(f"     PLAN {z['konto']}: Gewinn {z.get('gewinn')}")

check(KONTO_A["id"] not in ziel and aus.get(KONTO_A["id"], {}).get("grund") == app.FCP_GRUND_PAYOUT_UNGELESEN
      and aus[KONTO_A["id"]].get("payout_bezug", "").startswith("2026-11-19T13:14:42"),
      "Konto A: Heartbeat frisch, echte Lesung vor dem Payout → kein Waiting, Grund „Balance nach Payout noch nicht gelesen“")
check(KONTO_B["id"] in ziel and KONTO_B["id"] not in aus,
      "Konto B: echte Lesung 22.11. nach dem Payout zeigt keinen Abzug → weiter Ziel/Waiting (Fall B, nicht WP2)")
check(KONTO_C["id"] in ziel and KONTO_C["id"] not in aus,
      "Konto C: echte Lesung 22.11. nach der Auszahlung 20.11. zeigt keinen Abzug → weiter Ziel/Waiting (Fall B, nicht WP2)")
check(NORMAL["id"] in gepl and NORMAL["id"] not in ziel,
      "Normalfall: Lesung nach dem Payout zeigt Abzug (100.000) → geplant, kein Waiting")
check(FRISCH["id"] not in ziel and "Balance noch von vor der Auszahlung" in aus.get(FRISCH["id"], {}).get("grund", ""),
      "72-h-Fenster unverändert: Anfrage vor 10 h → bisheriger Text, kein Waiting")
check(GELADEN, "pending_payouts wurde gelesen")
check(not GESCHRIEBEN, "Trockenlauf schreibt nichts")

print("4) Scharfer Lauf: nur Konto B + C werden umgestellt, Konto A nicht")
app.admin_gruppen_daten = lambda: {"gruppen": [{"id": "ht", "name": "Hermann Technologies", "verwalter_id": None}],
                                   "mitglieder": [{"user_id": H1, "gruppe_id": "ht"}]}
app.alarm_senden = lambda *a, **k: (1, 1)
app.sb_update = lambda t, f, u: (GESCHRIEBEN.append(("update", t, f, u)) or ([{"id": f["id"][3:]}] if "waiting_payout_since" in u else []))
app.fcp_planen(trocken=False, jetzt=JETZT, seed=7)
umgestellt = {g[2]["id"][3:] for g in GESCHRIEBEN if g[0] == "update" and "waiting_payout_since" in g[3]}
check(KONTO_A["id"] not in umgestellt, "Konto A wird NICHT auf Waiting gestellt")
check({KONTO_B["id"], KONTO_C["id"]} <= umgestellt, "Konto B + C wie bisher umgestellt (echte Lesung nach dem Payout)")
check(NORMAL["id"] not in umgestellt and FRISCH["id"] not in umgestellt, "Normalfall und 72-h-Fall nicht umgestellt")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ alle Prüfungen grün")
