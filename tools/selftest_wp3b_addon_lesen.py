#!/usr/bin/env python3
"""Selbsttest WP3b (Master 23.11.2026): (1) Balance-Takt Fall (E) liest auch Striking-Konten (Apex mit allen Startwerten) unabhängig vom Firmen-„an“
im Funded-Planer, gleiches Gate wie fdp_planen; deaktivierte nie. RTP (Topstep Express) bewusst nicht — Express liest der Takt nie. Fall (Platzhalter):
Apex 100k Striking, Apex im Funded-Planer aus, Payout bestätigt nach der letzten Lesung → Lese-Auftrag. (2) Payouts/Lesung nicht lesbar → Striking in
der Kasse fail-closed (payouts_unlesbar).
Ohne Netz, schreibt nichts. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_wp3b_addon_lesen.py"""
import os
import sys
from datetime import datetime

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


U_SK, U_RTP, U_AUS = "u-sk", "u-rtp", "u-aus"
SK = {"id": "k-sk", "user_id": U_SK, "firm": "Apex Trader", "account_type": "winning_days", "name": "100k WD", "external_id": "PA-000003",
      "tv_balance": 103500.0, "tv_balance_at": "2026-11-19T16:02:57+00:00", "auto_planer": True}
SK_OHNE_START = dict(SK, id="k-sk2")
SK_FUNDED = dict(SK, id="k-sk3", account_type="funded")
RTP = {"id": "k-rtp", "user_id": U_RTP, "firm": "Topstep", "account_type": "funded", "name": "50k XFA", "external_id": "XFA-000000",
       "tv_balance": 1200.0, "tv_balance_at": "2026-11-19T10:00:00+00:00", "auto_planer": True}
RTP_WD = dict(RTP, id="k-rtp2", account_type="winning_days")
FREMD = dict(SK, id="k-fremd", user_id="u-ohne-addon")
ZF = {"k-sk": {"start": 100000.0, "seit": "2026-11-20", "nr": 2, "probation": False}, "k-sk2": None,
      "k-sk3": {"start": 100000.0, "seit": "2026-11-20", "nr": 1, "probation": False}}

print("1) ap_bal_auto_addon_auswahl (Gate wie fdp_planen)")
aus = app.ap_bal_auto_addon_auswahl([SK, SK_OHNE_START, SK_FUNDED, RTP, RTP_WD, FREMD], {U_SK}, ZF)
ids = [a["id"] for a in aus]
check("k-sk" in ids and "k-sk3" in ids, "Striking-Konten (WD und funded) mit allen Startwerten → lesen")
check("k-sk2" not in ids, "Striking ohne Startwerte → nicht lesen (fail-closed wie fdp_planen)")
check("k-rtp" not in ids and "k-rtp2" not in ids, "RTP/Topstep nie (Express liest der Takt nicht)")
check(app.ist_topstep_express(RTP), "Begründung: ein RTP-Konto ist Topstep Express (ist_topstep_express)")
check("k-fremd" not in ids, "ID ohne Add-on → nicht")
check(app.ap_bal_auto_addon_auswahl([SK, SK_FUNDED], {U_SK}, ZF, schon={"k-sk"}) == [SK_FUNDED], "schon in (E) → keine Dublette")
check(app.ap_bal_auto_addon_auswahl([SK], {U_SK}, None) == [], "Zyklus-Felder nicht lesbar (None) → kein Striking-Konto")

print("2) _ap_bal_auto_funded_konten: Add-on-Konten auch bei Firma aus")
ALT = (app._fdp_regeln_laden, app._sk_lesen, app._fdp_ids_aus, app._sb_all, app.sb_select, app._ap_deaktiviert_ids)
ABFRAGEN = []


def sb_all(t, p):
    ABFRAGEN.append((t, dict(p)))
    if t == "accounts" and p.get("firm") == "ilike.*apex*":
        return [dict(SK), dict(SK_OHNE_START), dict(SK, id="k-aus", user_id=U_AUS), dict(SK, id="k-deakt")]
    return []


def sb_select(t, p):
    if t == "accounts" and "striking_zyklus_start" in str(p.get("select")):
        return [{"id": "k-sk", "striking_zyklus_start": 100000, "striking_zyklus_seit": "2026-11-20", "striking_payout_nr": 2, "striking_probation": False},
                {"id": "k-sk2", "striking_zyklus_start": None, "striking_zyklus_seit": None, "striking_payout_nr": None},
                {"id": "k-deakt", "striking_zyklus_start": 100000, "striking_zyklus_seit": "2026-11-20", "striking_payout_nr": 1, "striking_probation": False}]
    return []


app._fdp_regeln_laden = lambda: {"firmen": [{"name": "Apex Trader", "namen": ["apex"], "an": False}], "user_ids": [U_SK]}
app._sk_lesen = lambda frisch=False: (frozenset({U_SK, U_AUS}), None, False)
app._fdp_ids_aus = lambda: {U_AUS}
app._ap_deaktiviert_ids = lambda: frozenset({"k-deakt"})
app._sb_all, app.sb_select = sb_all, sb_select
konten, letzt = app._ap_bal_auto_funded_konten()
kids = sorted(str(a["id"]) for a in konten)
check(kids == ["k-deakt", "k-sk"], f"Firma Apex aus: trotzdem Striking-Konten mit Startwerten, ohne ids_aus und ohne fehlende Startwerte ({kids})")
check(any(t == "trade_plans" for t, _p in ABFRAGEN), "letztes Trade-Ende wird für die Add-on-Konten geladen")
ev = {"k-sk": datetime.fromisoformat("2026-11-20T15:06:00+00:00"), "k-deakt": datetime.fromisoformat("2026-11-20T15:06:00+00:00")}
k = app.ap_bal_auto_funded(konten, {"k-sk": "2026-11-19T16:02:18+00:00", "k-deakt": "2026-11-19T16:02:18+00:00"}, set(), {}, {}, set(), payout=ev)
check(k.get("k-sk") == "Funded-Planer: Balance vor dem Payout gelesen", f"Striking-Konto: Lesung vor dem Payout → Lese-Auftrag ({k.get('k-sk')})")
check("k-deakt" not in k, "deaktiviertes Konto → kein Lese-Auftrag (auto_planer False über ap_deaktiviert_anwenden)")
app._ap_deaktiviert_ids = lambda: (_ for _ in ()).throw(RuntimeError("weg"))
check(app._ap_bal_auto_funded_konten() == ([], {}), "deaktivierte nicht lesbar → in diesem Takt keine Funded-Lesung (fail-closed)")
app._ap_deaktiviert_ids = lambda: frozenset()
app._sk_lesen = lambda frisch=False: (_ for _ in ()).throw(RuntimeError("weg"))
konten2, _l = app._ap_bal_auto_funded_konten()
check(konten2 == [], "Add-on-Gate nicht lesbar → nichts zusätzlich, kein Absturz (Firma aus → leer wie bisher)")
(app._fdp_regeln_laden, app._sk_lesen, app._fdp_ids_aus, app._sb_all, app.sb_select, app._ap_deaktiviert_ids) = ALT

print("3) Kasse: Payouts nicht lesbar → fail-closed")
_alt_all = app._sb_all
app._sb_all = lambda t, p: (_ for _ in ()).throw(RuntimeError("weg")) if t == "pending_payouts" else []
check(app._ap_payout_ereignisse(["k-sk"], streng=True) is None, "streng: Lesefehler → None (Striking fail-closed)")
check(app._ap_payout_ereignisse(["k-sk"]) == {}, "Takt (nicht streng): Lesefehler → {} wie bisher")
app._sb_all = _alt_all
zf = {"start": 100000.0, "seit": "2026-11-20", "nr": 2, "probation": False}
check(app.sk_payout_feld(zf, [], 103600, payouts_unlesbar=True).get("payouts_unlesbar") is True, "Feld striking.payouts_unlesbar an die Kasse")
check("payouts_unlesbar" not in app.sk_payout_feld(zf, [], 103600), "lesbar → kein Schlüssel (wie bisher)")
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
ah = src[src.index("def sk_payout_anhaengen("):src.index("def sk_payout_nach_seit(")]
check("_ap_payout_ereignisse(zids, streng=True)" in ah and "unlesbar = ev is None or tv_at is None or kid not in tv_at" in ah,
      "sk_payout_anhaengen: Payouts/Lesung nicht lesbar → payouts_unlesbar")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("o.payoutsStand === 'fehler' ? 'Payouts nicht lesbar'" in html and "payoutsStand: accPayoutsStand()" in html
      and "payoutsStand: s.payouts_unlesbar === true ? 'fehler' : 'ok'" in html, "skApexRechnung: Accounts-Zeile + Kasse fail-closed ohne Payout-Daten")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ alle Prüfungen grün")
