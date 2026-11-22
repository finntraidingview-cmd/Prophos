#!/usr/bin/env python3
"""Selbsttest WP3 (Master 23.11.2026, Befund BA1 Prüfer S2): ein Payout ändert die Balance ohne Trade. Im Balance-Takt gilt eine Lesung VOR dem
jüngsten Payout-Ereignis (approved_at, sonst received_at) nicht als live → Lese-Auftrag (auch Winning Days); Kasse/Striking bekommt vor_payout.
Fall nachgebaut (Platzhalter statt Login/Name): Apex 100k Winning Days — letzter Trade endete 19.11. 16:02:18 UTC, Endlesung 16:02:57 UTC,
Payout bestätigt 20.11. 15:06 UTC. Ohne Netz, schreibt nichts. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_wp3_balance_vor_payout.py"""
import os
import sys
from datetime import datetime, timezone

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
KID = "c3000000-0000-0000-0000-000000000003"
ENDE = "2026-11-19T16:02:18.000+00:00"
LESUNG_VOR = "2026-11-19T16:02:57.000+00:00"
LESUNG_NACH = "2026-11-23T05:10:00.000+00:00"
PEND = [{"account_id": KID, "approved_at": "2026-11-20T15:06:00+00:00", "received_at": None},
        {"account_id": KID, "approved_at": None, "received_at": "2026-10-30"},
        {"account_id": "nur-angefragt", "approved_at": None, "received_at": None}]

print("1) ap_payout_ereignis")
ev = app.ap_payout_ereignis(PEND)
check(ev.get(KID) == T("2026-11-20T15:06:00+00:00"), "jüngstes Ereignis = approved_at 20.11. 15:06 (älterer received_at zählt nicht)")
check("nur-angefragt" not in ev, "nur angefragt (ohne approved/received) → kein Ereignis, die Firma hat noch nicht abgezogen")
check(app.ap_payout_ereignis([{"account_id": "x", "received_at": "2026-11-21"}]).get("x") == T("2026-11-21T00:00:00+00:00"),
      "nur received_at (Datum) → 00:00 UTC")

print("2) ap_balance_live mit payout")
check(app.ap_balance_live(LESUNG_VOR, ENDE) is True, "ohne payout wie bisher: Lesung nach dem Trade-Ende = live (das war die Lücke)")
check(app.ap_balance_live(LESUNG_VOR, ENDE, ev[KID]) is False, "mit payout: Lesung vor dem Payout → nicht live")
check(app.ap_balance_live(LESUNG_NACH, ENDE, ev[KID]) is True, "Lesung nach dem Payout → live")
check(app.ap_balance_live(LESUNG_VOR, None, ev[KID]) is False, "ohne Trade, aber mit Payout danach → nicht live")
check(app.ap_balance_live(LESUNG_VOR, "2026-11-21T10:00:00+00:00", ev[KID]) is False, "Trade-Ende nach dem Payout bleibt maßgeblich")
check(app.ap_balance_live(LESUNG_VOR, ENDE, None) is True and app.ap_balance_live("", None, None) is True, "payout None → alte Regel unverändert")

print("3) Balance-Takt (E) Funded/Winning Days")
konto = {"id": KID, "user_id": "u1", "name": "100k WD", "firm": "Apex Trader", "account_type": "winning_days", "external_id": "PA-000000",
         "tv_balance": 103500.0, "tv_balance_at": LESUNG_VOR, "auto_planer": True}
k = app.ap_bal_auto_funded([konto], {KID: ENDE}, set(), {}, {}, set(), payout=ev)
check(k.get(KID) == "Funded-Planer: Balance vor dem Payout gelesen", f"Lesung vor dem Payout → Lese-Auftrag ({k.get(KID)})")
check(app.ap_bal_auto_funded([konto], {KID: ENDE}, set(), {}, {}, set()) == {}, "ohne payout wie bisher kein Auftrag")
k2 = app.ap_bal_auto_funded([dict(konto, tv_balance_at=LESUNG_NACH)], {KID: ENDE}, set(), {}, {}, set(), payout=ev)
check(k2 == {}, "Lesung nach dem Payout → kein Auftrag")
k3 = app.ap_bal_auto_funded([dict(konto, waiting_payout_since="2026-11-20T00:00:00+00:00")], {KID: ENDE}, set(), {}, {}, set(), payout=ev)
check(k3 == {}, "Waiting for Payout bleibt ausgenommen (wie bisher)")

print("4) Balance-Takt (B) geplante Pläne")
plaene = [{"master_account_id": KID, "status": "planned"}]
kb = app.ap_bal_auto_kandidaten(None, "2026-11-23", plaene, {KID: konto}, {KID: ENDE}, {}, {}, set(), payout=ev)
check(kb.get(KID) == "Plan geplant, Balance vor dem Payout gelesen", f"geplanter Plan, Lesung vor dem Payout → Lese-Auftrag ({kb.get(KID)})")
kb2 = app.ap_bal_auto_kandidaten(None, "2026-11-23", plaene, {KID: dict(konto, tv_balance_at=LESUNG_NACH)}, {KID: ENDE}, {}, {}, set(), payout=ev)
check(kb2 == {}, "Lesung nach dem Payout → kein Auftrag")

print("5) Striking/Kasse: vor_payout")
check(app.sk_vor_payout({"tv_balance_at": LESUNG_VOR}, ev[KID]) is True, "Lesung vor dem Payout → vor_payout")
check(app.sk_vor_payout({"tv_balance_at": LESUNG_NACH}, ev[KID]) is False, "Lesung nach dem Payout → nicht")
check(app.sk_vor_payout({"tv_balance_at": LESUNG_VOR}, None) is False, "ohne Payout → nicht")
zf = {"start": 100000.0, "seit": "2026-11-20", "nr": 2, "probation": False}
check(app.sk_payout_feld(zf, [], 103600, vor_payout=True).get("vor_payout") is True, "Feld striking.vor_payout an die Kasse")
check("vor_payout" not in app.sk_payout_feld(zf, [], 103600), "ohne vor_payout: Feld wie bisher (kein Schlüssel)")

print("6) Verdrahtung")
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
fk = src[src.index("def _ap_bal_auto_funded_konten("):src.index("def ap_bal_auto_kandidaten(")]
check('"account_type": "in.(funded,winning_days)"' in fk, "Fall (E) liest auch Winning Days")
tick = src[src.index("def ap_bal_auto_tick("):src.index("def _ap_bal_auto_senden(")]
check("payout=payout" in tick and "payout=f_payout" in tick, "Balance-Takt übergibt die Payout-Ereignisse an (B) und (E)")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("else if(accBalVorPayout(a)) tvStandZustand = 'Stand vor Payout'" in html, "Anzeige: „Stand vor Payout“ statt „● aktuell“")
check("vorPayout: accBalVorPayout(a) > 0" in html and "vorPayout: s.vor_payout === true" in html, "Striking: Accounts-Zeile und Kasse geben vorPayout weiter")
check("o.vorPayout === true ? 'Balance vor Payout — liest'" in html, "skApexRechnung rechnet fail-closed")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ alle Prüfungen grün")
