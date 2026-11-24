#!/usr/bin/env python3
"""Selbsttest PW1 (Finn 24.11.2026, Marc FundedNext 100k On Demand …7821 + Zielbild: „Wenn ich den Payout eines Kontos anfrage, soll es bei CFD direkt
wieder rüberspringen zu Typ Funded CFD, und es sollen da weitere Trades geplant werden. Die Balance soll wieder neu gelesen werden, 1 bis 12 Stunden nachdem
der Payout angefragt wurde … Sobald die neue Balance ausgelesen ist und der Profit abgebucht wurde, dann ganz normal wieder im Tradeplaner einbauen.“).
Geprüft: fcp_lesung_aus_signalen / fcp_payout_phase / fcp_payout_lesen_faellig / fcp_waiting_zurueck (rein), ap_bal_auto_payout (Balance-Takt (F)),
fcp_planen trocken + scharf (Waiting → Funded CFD nur HT, Übergangsrechnung bis zur Abbuchung, Beobachtung danach = Balance, kein doppelter Abzug).
Vor-Balance = End-Balance (final.master_balance) des letzten Trades vor der Anfrage. Fälle wie in der DB (24.11.): Marc …7821, Mike …7057, ein Konto mit
gelesener Abbuchung, ein Konto, das zu Recht wartet. Ohne Netz. Aufruf: python3 tools/selftest_pw1_payout_lesung_waiting.py"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


T = lambda s: app._ap_ts(s)   # noqa: E731
sig = lambda kid, at, bal, st="fertig", ok=True, akt="mt5_balance": {"plan_id": "konto:" + kid, "status": st, "params": {"aktion": akt},   # noqa: E731
                                                                    "created_at": at, "updated_at": at, "ergebnis": {"ok": ok, "balance": bal, "balance_at": at}}
le = lambda at, b: {"at": T(at), "balance": b}   # noqa: E731
tr = lambda e, pl, bal: {"status": "completed", "ended_at": e, "completed_at": e, "master_pl": pl, "final": {"master_balance": bal}}   # noqa: E731

print("1) reine Helfer")
L = app.fcp_lesung_aus_signalen([sig("a", "2026-11-20T10:00:00+00:00", 100000), sig("a", "2026-11-22T10:00:00+00:00", 100010),
                                 sig("b", "2026-11-22T10:00:00+00:00", 0), sig("c", "2026-11-22T10:00:00+00:00", 5, st="fehler"),
                                 sig("d", "2026-11-22T10:00:00+00:00", 5, ok=False), sig("e", "2026-11-22T10:00:00+00:00", 5, akt="mt5_terminal"),
                                 sig("f", "2026-11-22T10:00:00+00:00", 51000, akt="konto_balance")])
check(L.get("a", {}).get("balance") == 100010 and set(L) == {"a", "f"}, "Lese-Aufträge: jüngster je Konto; ohne Wert/Fehler/ok false/Terminal zählen nicht")
A = T("2026-11-18T22:37:12+00:00")
VOR = [tr("2026-11-18T14:35:34+00:00", 79.34, 104915.95)]
P = app.fcp_payout_phase
check(P(None, 100000, None, VOR) is None, "keine Anfrage → None")
check(P(A, 100000, None, [tr("2026-11-18T14:35:34+00:00", -500, 99500.0)]) is None, "kein Gewinn vor der Anfrage → None (normal rechnen)")
oh = P(A, 100000, None, [{"status": "completed", "ended_at": "2026-11-18T14:35:34+00:00", "master_pl": 80}])
check(oh == {"phase": "offen", "abzug": 0.0, "vor": None, "beobachtet": False, "letzte": None} and app.fcp_payout_lesen_faellig(A, oh, A + timedelta(hours=2)),
      "Review (3): Vor-Balance unbekannt (Trade ohne End-Balance) → offen ohne Abzug (kein Waiting, (F) liest), nie normal auf alter Balance")
oh2 = P(A, 100000, le("2026-11-19T14:00:00+00:00", 100050.0), [])
check(oh2["phase"] == "abgebucht" and oh2["balance"] == 100050.0, "… danach gilt die erste Beobachtung als Balance")
o = P(A, 100000, None, VOR)
check(o == {"phase": "offen", "abzug": 4915.95, "vor": 104915.95, "beobachtet": False, "letzte": None}, f"Marc: nie beobachtet → offen, abzug 4.915,95 ({o})")
check(P(A, 100000, le("2026-11-18T22:00:00+00:00", 100000.0), VOR)["beobachtet"] is False, "Lesung VOR der Anfrage zählt nicht")
check(P(A, 100000, le("2026-11-19T02:00:00+00:00", 104915.95), VOR)["phase"] == "offen", "Lesung danach ohne Abzug → offen (beobachtet)")
ab = P(A, 100000, le("2026-11-19T14:00:00+00:00", 100000.0), VOR)
check(ab["phase"] == "abgebucht" and ab["balance"] == 100000.0, "Lesung danach mit Abzug → abgebucht, ihre Balance")
check(P(A, 100000, le("2026-11-19T14:00:00+00:00", 101215.95), VOR)["phase"] == "abgebucht", "Teil-Payout On Demand (3.700 von 4.916 abgezogen) → abgebucht")
check(P(A, 100000, le("2026-11-19T14:00:00+00:00", 104600.0), VOR)["phase"] == "offen", "nur 316 $ weniger (Kursrauschen/Gebühr) → noch offen")
nach = VOR + [tr("2026-11-20T10:00:00+00:00", 800.0, 100800.0)]
x = P(A, 100000, None, nach)
check(x["phase"] == "abgebucht" and x["balance"] == 100800.0, "Trade nach der Anfrage, End-Balance 100.800 (abgebucht + Trade) → abgebucht — kein doppelter Abzug")
nach2 = VOR + [tr("2026-11-20T10:00:00+00:00", 800.0, 105715.95)]
check(P(A, 100000, None, nach2)["phase"] == "offen", "Trade danach, End-Balance 105.716 (noch nicht abgebucht + Trade) → offen")
F = app.fcp_payout_lesen_faellig
check(not F(A, o, A + timedelta(minutes=30)), "30 min nach der Anfrage → noch nicht lesen (nicht instant)")
check(F(A, o, A + timedelta(hours=2)), "ohne Konto (Versatz 1 h): 2 h nach der Anfrage, nie beobachtet → lesen")
check(not F(A, P(A, 100000, le("2026-11-19T00:00:00+00:00", 104915.95), VOR), A + timedelta(hours=5)),
      "PW4: gelesen, noch ohne Abbuchung → erst 12 h nach dieser Lesung wieder (nicht in jedem Takt)")
V = app.fcp_payout_lese_versatz
vs = [V(f"konto-{i}", A) for i in range(400)]
check(all(timedelta(hours=1) <= v <= timedelta(hours=12) for v in vs) and V("konto-1", A) == V("konto-1", A)
      and min(vs) < timedelta(hours=2) and max(vs) > timedelta(hours=11) and len({v for v in vs}) > 250,
      f"PW4: Versatz je Konto + Anfrage fest, 1–12 h gestreut ({min(vs)} … {max(vs)})")
check(V("konto-1", A) != V("konto-1", A + timedelta(minutes=1)) or V("konto-1", A) != V("konto-2", A), "neue Anfrage → neuer Wurf")
vk = V("k-marc", A)
check(not F(A, o, A + vk - timedelta(minutes=1), "k-marc") and F(A, o, A + vk + timedelta(minutes=1), "k-marc"),
      f"PW4: mit Konto erst ab dem gestreuten Zeitpunkt (Marc: {vk} nach der Anfrage)")
check(not F(A, ab, A + timedelta(hours=5)), "abgebucht → nicht mehr lesen")
check(F(A, o, A + timedelta(days=5)), "nach 12 h, nie beobachtet → lesen (alte Fälle Marc/Mike)")
ob = P(A, 100000, le("2026-11-23T02:00:00+00:00", 104915.95), VOR)
check(not F(A, ob, T("2026-11-23T10:00:00+00:00")) and F(A, ob, T("2026-11-23T15:00:00+00:00")),
      "nach 12 h, noch nicht abgebucht → höchstens alle 12 h weiter lesen (Review: Firma bucht später als 12 h ab)")
W = app.fcp_waiting_zurueck
check(W("2026-11-18T16:17:03+00:00", A, o), "Anfrage nach Waiting → zurück (Finn: sofort Funded CFD)")
check(W("2026-11-23T03:26:18+00:00", A, o), "Waiting nach der Anfrage, nie beobachtet → zurück (Marc)")
check(not W("2026-11-23T03:26:18+00:00", A, ob) and not W("2026-11-23T03:26:18+00:00", A, ab) and not W(None, A, o) and not W("2026-11-23T03:26:18+00:00", None, None),
      "Waiting nach einer Beobachtung (auch von Hand) / abgebucht / ohne Waiting / ohne Anfrage → bleibt")

print("2) Balance-Takt (F)")
JETZT = datetime(2026, 11, 24, 6, 0, tzinfo=timezone.utc)
KA = {"id": "k-marc", "external_id": "14367821", "firm": "FundedNext", "account_type": "funded_cfd", "waiting_payout_since": "2026-11-23T03:26:18+00:00",
      "account_size": 100000, "name": "100k 14367821"}
KN, KG = dict(KA, id="k-neu", waiting_payout_since=None), dict(KA, id="k-gelesen", waiting_payout_since=None)
anf = {"k-marc": A, "k-neu": JETZT - timedelta(minutes=20), "k-gelesen": JETZT - timedelta(hours=3)}
plv = {"k-marc": VOR, "k-neu": [tr("2026-11-23T10:00:00+00:00", 900, 101900.0)], "k-gelesen": [tr("2026-11-23T10:00:00+00:00", 900, 104000.0)]}
f = app.ap_bal_auto_payout([KA, KN, KG], {"k-gelesen": le("2026-11-24T04:00:00+00:00", 100000.0)}, anf, plv, JETZT)
check("k-marc" in f and "k-neu" not in f and "k-gelesen" not in f, f"Marc → lesen; Anfrage vor 20 min → noch nicht; Abbuchung gelesen → nicht ({sorted(f)})")
check(app.ap_bal_auto_payout([dict(KA, auto_planer=False), dict(KN, id="k-x", external_id="")], {}, {"k-marc": A, "k-x": A}, plv, JETZT) == {},
      "Haken Auto-Planer aus / ohne External ID → nicht lesen")
check(app.ap_bal_auto_funded([KA], {}, set(), {}, {}, set(), payout={}) == {}, "Futures-Quelle (E) unverändert")
src = open(os.path.join(WURZEL, "app" + ".py"), encoding="utf-8").read()
tk, gt = src[src.index("def ap_bal_auto_tick("):src.index("def _ap_bal_auto_senden(")], src[src.index("def ap_bal_auto_gruppen_tick("):src.index("# ══ VON SELBST BESTÄTIGEN")]
check('globals()["_ap_bal_payout_kandidaten"](uids, jetzt, set(kand), archiv)' in tk and "_ap_bal_payout_kandidaten" not in gt,
      "PW1b: nur der HT-Takt hängt die Quelle (F) an, der Gruppen-Takt nicht ((E) lädt keine Funded-CFD-Konten)")

print("3) Funded-CFD-Planer (trocken + scharf)")
sql = open(os.path.join(WURZEL, "sql", "2026-10-30_funded_cfd_planer.sql"), encoding="utf-8").read()
FIRMEN = json.loads(re.search(r"'(\[\s*\{.*?\]\s*)'::jsonb", sql, re.S).group(1))
H1 = "11111111-1111-1111-1111-111111111111"
HEART = (JETZT - timedelta(minutes=2)).isoformat()


def konto(i, n, bal, waiting=None):
    return {"id": i, "user_id": H1, "name": n, "firm": "FundedNext", "account_type": "funded_cfd", "external_id": "L" + i[-4:], "tv_balance": bal,
            "tv_balance_at": "2026-11-23T19:31:24+00:00", "tv_balance_quelle": "mt5", "waiting_payout_since": waiting, "created_at": "2026-10-01T00:00:00+00:00", "_bal": bal}


MARC = konto("c1000000-0000-0000-0000-000000000001", "100k 14367821 → Funded", 104915.95, "2026-11-23T03:26:18+00:00")
M7057 = konto("c1000000-0000-0000-0000-000000000002", "100k 14357057 → Funded", 101445.70, "2026-11-19T16:17:03+00:00")
GELESEN = konto("c1000000-0000-0000-0000-000000000003", "100k 3 → Funded", 101900.00, "2026-11-19T10:00:00+00:00")
WARTET = konto("c1000000-0000-0000-0000-000000000004", "100k 4 → Funded", 102300.00, "2026-11-22T10:00:00+00:00")
KONTEN = [MARC, M7057, GELESEN, WARTET]
TRADES = [dict(tr(e, 500.0, a["_bal"]), id="t" + a["id"][-1], user_id=H1, master_account_id=a["id"], master_firm="FundedNext", started_at=e,
               notes="Funded-CFD-Planer · Vorschlag", planned_for=e[:10])
          for a, e in ((MARC, "2026-11-18T14:35:34+00:00"), (M7057, "2026-11-19T15:59:37+00:00"), (GELESEN, "2026-11-18T09:00:00+00:00"),
                       (WARTET, "2026-11-21T09:00:00+00:00"))]
PEND = [{"account_id": MARC["id"], "received_tx_id": "x1", "requested_at": "2026-11-18", "created_at": "2026-11-18T22:37:12+00:00",
         "approved_at": "2026-11-19T13:14:42+00:00", "received_at": "2026-11-19"},
        {"account_id": M7057["id"], "received_tx_id": None, "requested_at": "2026-11-19", "created_at": "2026-11-19T17:00:00+00:00",
         "approved_at": "2026-11-20T11:04:03+00:00", "received_at": None},
        {"account_id": GELESEN["id"], "received_tx_id": None, "requested_at": "2026-11-19", "created_at": "2026-11-19T12:00:00+00:00",
         "approved_at": "2026-11-20T08:00:00+00:00", "received_at": None},
        {"account_id": WARTET["id"], "received_tx_id": None, "requested_at": "2026-11-10", "created_at": "2026-11-10T12:00:00+00:00",
         "approved_at": "2026-11-11T08:00:00+00:00", "received_at": None}]
LES = [sig(GELESEN["id"], "2026-11-21T08:00:00+00:00", 100000.0)]
REG = {"id": 1, "aktiv": False, "auto_bestaetigen": False, "ziel_auto_wartet": False, "user_ids": [H1], "firmen": FIRMEN,
       "zeiten": {"firma_abstand_min": 15, "abstand_id_min": 10, "vorlauf_min": 15}}
GESCHR = []


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
        return [dict(x) for x in PEND]
    if t == "order_signale":
        return [dict(x) for x in LES]
    if t == "user_settings":
        return [{"user_id": H1, "value": {"accountId": "f1"}}]
    if t == "firm_specs":
        return [{"user_id": H1, "name": "FundedNext", "ppl": 10.0, "unit": "Lots"}]
    if t == "id_gruppe_mitglied":
        return [{"user_id": H1, "gruppe_id": "ht"}]
    return []


app.sb_select, app._sb_all = sb_select, sb_all
app.sb_insert = lambda t, z: GESCHR.append(("insert", t, z))
app.sb_update = lambda t, f, u: GESCHR.append(("update", t, f, u)) or [{"id": f.get("id", "")[3:]}]
app._sb_anfrage = lambda m, *a, **k: (GESCHR.append(("post", m) + a) if m != "GET" else None) or None   # nie ins Netz
app._sb_pruefen = lambda r: None
app._ap_archiviert = lambda streng=False: set()
app._ap_namen = lambda: ({H1: "HT-1"}, set())
app.admin_gruppen_daten = lambda: {"gruppen": [{"id": "ht", "name": "Hermann Technologies", "verwalter_id": None}], "mitglieder": [{"user_id": H1, "gruppe_id": "ht"}]}
ALARME, IM_LOG = [], set()
app.alarm_senden = lambda *a, **k: ALARME.append((a, k)) or (1, 1)
app.alarm_im_log = lambda keys, seit_s: {k for k in keys if k in IM_LOG}
app.tw_pause_grund = lambda *a, **k: None
app._ap_balance_karten = lambda: ({a["external_id"]: (a["_bal"], "USD", HEART) for a in KONTEN}, {})   # Echo im Standby: alter Stand, frischer Heartbeat
erg = app.fcp_planen(trocken=True, jetzt=JETZT, seed=7)
aus = {z["konto_id"]: z for z in erg.get("ausgelassen") or []}
gepl = {z["konto_id"]: z for z in erg.get("geplant") or []}
zur = {z["konto_id"]: z for z in erg.get("waiting_zurueck") or []}
for z in erg.get("ausgelassen") or []:
    print(f"     AUS  {z['konto']}: {z.get('grund')}")
for z in erg.get("geplant") or []:
    print(f"     PLAN {z['konto']}: Gewinn {z.get('gewinn')} · {z.get('bal_quelle')}")
check(MARC["id"] in zur and MARC["id"] not in gepl and aus.get(MARC["id"], {}).get("grund") == app.FCP_GRUND_PAYOUT_LESEN and aus[MARC["id"]].get("lesen_ab"),
      f"PW4 Marc: Waiting zurück (Funded CFD), aber NICHT geplant bis zur Lesung — kein „Balance − Gewinn“ ({aus.get(MARC['id'], {}).get('grund')})")
check(M7057["id"] in zur and M7057["id"] not in gepl and aus.get(M7057["id"], {}).get("grund") == app.FCP_GRUND_PAYOUT_LESEN,
      "PW4 Mike …7057: Anfrage nach Waiting → zurück, wartet auf die Lesung")
check(not [z for z in (erg.get("geplant") or []) if z.get("payout_offen")], "PW4: kein Plan mit abgezogener Balance mehr")
pg = gepl.get(GELESEN["id"], {})
check(GELESEN["id"] in zur and pg.get("gewinn") == 0.0 and pg.get("bal_quelle") == "Lesung nach Payout" and not pg.get("payout_offen"),
      "Abbuchung gelesen (100.000 statt 101.900) → Waiting zurück, normal geplant mit der Lesung")
check(WARTET["id"] not in zur and "Waiting for Payout" in aus.get(WARTET["id"], {}).get("grund", ""),
      "Konto wartet zu Recht (alte Anfrage, danach getradet und beobachtet, Waiting danach) → bleibt Waiting")
check(not [g for g in GESCHR if g[0] in ("update", "post")], "Trockenlauf schreibt nichts")

GESCHR.clear()
app.fcp_planen(trocken=False, jetzt=JETZT, seed=7)
leer = [g for g in GESCHR if g[0] == "update" and g[1] == "accounts" and g[3] == {"waiting_payout_since": None}]
ids = {g[2]["id"][3:] for g in leer}
check(ids == {MARC["id"], M7057["id"], GELESEN["id"]}, f"scharf: genau drei Konten zurück auf Funded CFD ({len(ids)})")
check(all(g[2].get("waiting_payout_since", "").startswith("eq.") and g[2].get("account_type") == "eq.funded_cfd" for g in leer),
      "scharf: Update nur mit Guard (derselbe Waiting-Zeitstempel, Funded CFD)")
ziel_w = [g for g in GESCHR if g[0] == "update" and "fcp_ziel" in g[3] and g[2].get("id", "")[3:] in (MARC["id"], M7057["id"])]
check(not ziel_w, "scharf: Zyklus-Ziel der offenen Konten erst mit der neuen Balance festgeschrieben (noch nicht)")

print("4) PW1b: 🟠 12 h nach der Anfrage ohne Abbuchung")
pa = [x for x in ALARME if x[0][1] == "fcp_payout_offen"]
keys = {x[1].get("schluessel") for x in pa}
check(len(pa) == 2 and keys == {f"fcp_payout_offen|{MARC['id']}|2026-11-18T22:37:12+00:00", f"fcp_payout_offen|{M7057['id']}|2026-11-19T17:00:00+00:00"},
      f"scharf: genau Marc + Mike …7057 (offen, Anfrage > 12 h her), nicht das abgebuchte Konto ({len(pa)})")
check(all(x[0][0] == 2 and "Payout abgelehnt/ausstehend?" in x[0][2] for x in pa), "Prio 2 (🟠), Titel „Payout abgelehnt/ausstehend?“")
t_marc = next((x for x in pa if MARC["id"] in x[1].get("schluessel", "")), ((), {}))
check("HT-1 · FundedNext 100k …0001" in t_marc[0][2] and "HT-1 · FundedNext 100k …0001" in t_marc[0][3] and "seit 24 h keine erfolgreiche Lesung" in t_marc[0][3]
      and "nicht geplant" in t_marc[0][3] and "−" not in t_marc[0][3],
      f"Konto als ID · Firma Größe …4, Text ohne Abzug (PW4) ({t_marc[0][3][:160] if t_marc[0] else ''})")
AF = app.fcp_payout_alarm_faellig
A2 = T("2026-11-20T10:00:00+00:00")
o_nie = {"phase": "offen", "beobachtet": False, "letzte": None}
o_frueh = {"phase": "offen", "beobachtet": True, "letzte": A2 + timedelta(hours=2)}
o_spaet = {"phase": "offen", "beobachtet": True, "letzte": A2 + timedelta(hours=14)}
check(not AF(A2, o_frueh, A2 + timedelta(hours=13)) and AF(A2, o_spaet, A2 + timedelta(hours=14, minutes=5)),
      "Review PW4: Lesung 2 h nach der Anfrage ohne Abbuchung → bei 12 h noch kein 🟠; erst wenn eine Lesung ≥ 12 h danach nichts zeigt")
check(not AF(A2, o_nie, A2 + timedelta(hours=12, minutes=5)) and AF(A2, o_nie, A2 + timedelta(hours=24)),
      "nie gelesen (Versatz bis 12 h) → 🟠 erst nach 24 h ohne Lesung")
check(not AF(A2, {"phase": "abgebucht"}, A2 + timedelta(days=3)) and not AF(None, o_nie, A2 + timedelta(days=3)), "abgebucht / ohne Anfrage → nie")
ALARME.clear()
IM_LOG.update(keys)
app.fcp_planen(trocken=False, jetzt=JETZT, seed=7)
check(not [x for x in ALARME if x[0][1] == "fcp_payout_offen"], "zweiter Lauf: schon im alarm_log → keine zweite Meldung")
ALARME.clear()
IM_LOG.clear()
app.alarm_im_log = lambda keys, seit_s: None
app.fcp_planen(trocken=False, jetzt=JETZT, seed=7)
check(not [x for x in ALARME if x[0][1] == "fcp_payout_offen"], "alarm_log nicht lesbar → diesmal keine Meldung (lieber später als doppelt)")
app.alarm_im_log = lambda keys, seit_s: {k for k in keys if k in IM_LOG}
ALARME.clear()
app.fcp_planen(trocken=False, jetzt=datetime(2026, 11, 19, 8, 0, tzinfo=timezone.utc), seed=7)
check(not [x for x in ALARME if x[0][1] == "fcp_payout_offen" and MARC["id"] in x[1].get("schluessel", "")],
      "Marc 9,4 h nach der Anfrage → noch keine Meldung (erst ab 12 h)")
ALARME.clear()
app.fcp_planen(trocken=True, jetzt=JETZT, seed=7)
check(not [x for x in ALARME if x[0][1] == "fcp_payout_offen"], "Trockenlauf meldet nichts")


def _kaputt():
    raise RuntimeError("Gruppen nicht lesbar")


print("5) PW1b: nur Hermann Technologies")
GESCHR.clear()
ALARME.clear()
app.admin_gruppen_daten = _kaputt
e2 = app.fcp_planen(trocken=False, jetzt=JETZT, seed=7)
leer2 = [g for g in GESCHR if g[0] == "update" and g[1] == "accounts" and g[3] == {"waiting_payout_since": None}]
aus2 = {z["konto_id"]: z for z in e2.get("ausgelassen") or []}
check(not leer2 and not (e2.get("waiting_zurueck") or []) and all("Gruppen nicht lesbar" in aus2.get(k["id"], {}).get("grund", "") for k in KONTEN),
      "Gruppen nicht lesbar → Waiting bleibt, nichts geschrieben, Konten mit Anfrage heute nicht geplant (fail-closed, nie volle Balance vor der Abbuchung)")
check(not [x for x in ALARME if x[0][1] == "fcp_payout_offen"], "… und keine Payout-Meldung")
app.admin_gruppen_daten = lambda: {"gruppen": [{"id": "em", "name": "Emin", "verwalter_id": "22222222-2222-2222-2222-222222222222"}],
                                   "mitglieder": [{"user_id": H1, "gruppe_id": "em"}]}
GESCHR.clear()
e3 = app.fcp_planen(trocken=False, jetzt=JETZT, seed=7)
leer3 = [g for g in GESCHR if g[0] == "update" and g[1] == "accounts" and g[3] == {"waiting_payout_since": None}]
p3 = [z for z in e3.get("geplant") or [] if z.get("payout_offen") or z.get("bal_quelle") == "Lesung nach Payout"]
check(not leer3 and not (e3.get("waiting_zurueck") or []) and not p3 and not [x for x in ALARME if x[0][1] == "fcp_payout_offen"],
      "ID in einer Gruppe mit Verwalter (Emin) → keine PW1-Rechnung, kein Zurückstellen, keine Meldung")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ alle Prüfungen grün")
