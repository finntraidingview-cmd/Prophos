#!/usr/bin/env python3
"""Selbsttest ZWEI ORBIT AUFS HANDY (03.11.2026, Auftrag Z6): 🟠 „Zweiter Big Trade gestartet“ (alarm_tick, Abstand beim Start aus dem Klick-Riegel),
„Zweiter Big Trade wartet“ (Klick-Riegel + DB-Sperre, einmal je Plan), „Puls hat das Konto gewechselt (Priorität)“ (/alarm/heimweg mit prio, einmal je
Wechsel). app.py importiert, DB/Push ersetzt. Ohne Netz. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_zwei_orbit_alarme.py"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


U = "48f272b4-0000-4000-8000-000000000001"
JETZT = datetime(2026, 11, 3, 14, 0, tzinfo=timezone.utc)
A = {"id": "aaaaaaaa-1111-4111-8111-111111111111", "user_id": U, "status": "open", "route": "tvv2", "hedge_eur": 2433, "orbit_v3": True,
     "master_name": "150k FTDFYSLX150742744758 → Funded", "master_firm": "Tradeify", "richtung": "buy", "master_contracts": "3.000", "master_symbol_root": "NQ",
     "started_at": "2026-11-03T12:40:00+00:00", "mt5_baseline": {"hedge": {"pc": "pc-3wghru"}}}
B = dict(A, id="bbbbbbbb-2222-4222-8222-222222222222", master_name="100k PAAPEX6843320000005 → Funded", master_firm="Apex Trader", richtung="sell",
         master_contracts="2.000", started_at="2026-11-03T13:52:00+00:00")
WD = dict(A, id="cccccccc-3333-4333-8333-333333333333", winning_day=True)
APEX = dict(A, id="dddddddd-4444-4444-8444-444444444444", ah_status="mit")
TSX = dict(A, id="eeeeeeee-5555-4555-8555-555555555555", route="tsv2", master_firm="Topstep", master_name="150k TOPSTEP12345 → Funded")
OHNE_HEDGE = dict(A, id="ffffffff-6666-4666-8666-666666666666", hedge_eur=0, orbit_v3=False)

GESENDET, LOG = [], set()
OFFEN, GEPLANT = [], []
EP = {"konto": "PAAPEX6843320000005105", "updated_at": (JETZT - timedelta(seconds=5)).isoformat()}
app._ap_namen = lambda: ({U: "Finn + Pascal"}, set())
app._alarm_empfaenger = lambda: {U: 2}
app._alarm_fremd_verwaltet = lambda uid: False
app.alarm_im_log = lambda keys, s: {k for k in keys if k in LOG}
REGEL = {"aktiv": True, "tp_usd": 2000, "liq_usd": 2000, "big_max_je_id": 2, "zweit_usd": 2500}
app._puls_heim_regel = lambda: REGEL


def senden(prio, art, titel, text, **kw):
    GESENDET.append({"prio": prio, "art": art, "titel": titel, "text": text, **kw})
    LOG.add(kw.get("schluessel"))
    return 1, 1


app.alarm_senden = senden
app._sb_all = lambda t, p: [dict(z) for z in (GEPLANT if p.get("status") == "eq.planned" else OFFEN)]
NAEHE_RUFE = []
app._puls_heim_naehe = lambda plaene, schw: NAEHE_RUFE.append([p["id"] for p in plaene]) or [
    (p, {}, {"plan": p["id"], "konto": "x", "rest_tp_usd": 4100.0, "rest_liq_usd": 9000.0}, "x", "BUY 3 NQ") for p in plaene]


def sb_select(t, p):
    if t == "echoplus_live":
        return [dict(EP)]
    if t == "trade_plans":
        ids = str(p.get("id") or "")
        alle = OFFEN + GEPLANT + [A, B]
        return [dict(x) for x in alle if x["id"] in ids][:2]
    return []


app.sb_select = sb_select


def reset():
    GESENDET.clear(); LOG.clear(); app._alarm["gemeldet"].clear(); app._ZWEIT_START_MERK.clear(); NAEHE_RUFE.clear()


print("1) Gruppen und Texte (rein rechnend)")
g = app.zweit_gruppen([A, B, WD, APEX, TSX, OHNE_HEDGE, dict(A, id="x9", status="planned")])
check(len(g) == 1 and g[0][1] == "tv" and [p["id"] for p in g[0][2]] == [A["id"], B["id"]],
      "zwei offene Big Trades derselben ID im TV-Fenster → eine Gruppe, B = jüngster; WD, Apex-Challenge, TopstepX, ohne Hedge, geplant zählen nicht")
check(app.zweit_gruppen([A, TSX]) == [] and app.zweit_gruppen([A]) == [], "TV + TopstepX (eigene Fenster) bzw. einer allein → nichts")
check(app.zweit_konto_name(A) == "Tradeify …4758" and app.zweit_konto_name(B) == "Apex Trader …0005" and app.zweit_art(A) == "BUY 3 NQ", "Kontoname und Art")
check(app.zweit_puls_wo("PAAPEX6843320000005105", [A, B]) == "Apex Trader …0005" and app.zweit_puls_wo("FTDFYSLX150742744758", [A, B]) == "Tradeify …4758"
      and app.zweit_puls_wo("FTMO32734148", [A, B]) == "FTMO32734148" and app.zweit_puls_wo("", [A, B]) is None,
      "Puls-Konto: Balance klebt / voll / fremdes Konto roh / leer")
merk = {"andere": [{"plan": A["id"], "konto": "Tradeify …4758", "rest_tp_usd": 3120.4, "rest_liq_usd": 11850}]}
ev = app.zweit_gestartet_ereignis(U, "tv", [A, B], {U: "Finn + Pascal"}, merk, {}, "Apex Trader …0005")
check(ev[0] == f"{B['id']}|zweit_gestartet" and ev[1] == 2 and ev[3] == "Zweiter Big Trade gestartet", f"Schlüssel je B, 🟠: {ev[0]}")
check(all(s in ev[4] for s in ("Finn + Pascal · TradingView", "Tradeify …4758 BUY 3 NQ", "3.120 $ vor TP", "11.850 $ vor Liq", "beim Start von B",
                               "Apex Trader …0005 SELL 2 NQ", "Puls steht in Apex Trader …0005")), f"Text: {ev[4]}")
ev2 = app.zweit_gestartet_ereignis(U, "tv", [A, B], {U: "Finn + Pascal"}, None, {A["id"]: {"rest_tp_usd": 4100, "rest_liq_usd": 9000}}, None)
check("4.100 $ vor TP" in ev2[4] and "(jetzt)" in ev2[4] and "unbekannt" in ev2[4], "ohne Merker (Railway-Neustart) → Wert von jetzt, Puls unbekannt")
w = app.zweit_wartet_ereignis(B, "firma_laeuft", "Big Trade „x“ läuft schon bei Apex Trader — je Firma nur einer gleichzeitig", {U: "Finn + Pascal"})
check(w[0] == f"{B['id']}|zweit_wartet" and "gleiche Firma" in w[4] and w[3] == "Zweiter Big Trade wartet", f"wartet: {w[4]}")
pv = app.zweit_prio_ereignis(U, B, A, 22.5, 8.0, {U: "Finn + Pascal"}, 1793712000000)
check(pv[3] == "Puls hat das Konto gewechselt (Priorität)" and "von Apex Trader …0005 (22 Pkt" in pv[4] and "Tradeify …4758 (8 Pkt)" in pv[4]
      and pv[0].startswith(f"{A['id']}|prio_wechsel|bbbbbbbb|"), f"Prio: {pv[4]}")

print("2) alarm_tick-Teil: einmal je B, Abstand beim Start aus dem Klick-Riegel")
reset()
OFFEN[:] = [A, B, WD]
app.zweit_start_merken(B["id"], [{"plan": A["id"], "konto": "Tradeify …4758", "art": "BUY 3 NQ", "rest_tp_usd": 3120.4, "rest_liq_usd": 11850}])
app.zweit_alarm_tick(set(), JETZT)
check(len(GESENDET) == 1 and GESENDET[0]["art"] == "zweit_gestartet" and "beim Start von B" in GESENDET[0]["text"] and not NAEHE_RUFE
      and "Puls steht in Apex Trader …0005" in GESENDET[0]["text"], f"gesendet mit Start-Abstand, ohne Neuberechnung: {GESENDET and GESENDET[0]['text']}")
app.zweit_alarm_tick(set(), JETZT + timedelta(minutes=1))
check(len(GESENDET) == 1, "nächster Takt → nicht noch einmal")
app._alarm["gemeldet"].clear()
app.zweit_alarm_tick(set(), JETZT + timedelta(minutes=2))
check(len(GESENDET) == 1, "nach Railway-Neustart (Speicher leer) → alarm_log verhindert die Wiederholung")
reset()
EP["updated_at"] = (JETZT - timedelta(minutes=10)).isoformat()
app.zweit_alarm_tick(set(), JETZT)
check(len(GESENDET) == 1 and NAEHE_RUFE == [[A["id"]]] and "(jetzt)" in GESENDET[0]["text"] and "unbekannt" in GESENDET[0]["text"],
      "ohne Merker → Abstand von jetzt; Reader-Konto alt → Puls unbekannt")
EP["updated_at"] = (JETZT - timedelta(seconds=5)).isoformat()
reset()
app.zweit_alarm_tick({U}, JETZT)
check(GESENDET == [], "ausgenommene ID (aus) → nichts")

print("3) „wartet“ einmal je Plan — DB-Sperre und Klick-Riegel")
reset()
OFFEN[:] = []
GEPLANT[:] = [dict(B, status="planned", ss={"art": "markt", "text": "Markteröffnung 09:28–09:35 New York (bis 18:35 Dubai): kein weiterer Big Trade"}),
              dict(A, id="99999999-9999-4999-8999-999999999999", status="planned", ss={"art": "irgendwas"})]
app.zweit_alarm_tick(set(), JETZT)
check(len(GESENDET) == 1 and GESENDET[0]["art"] == "zweit_wartet" and "Markteröffnung" in GESENDET[0]["text"], f"DB-Sperre markt → gemeldet: {GESENDET and GESENDET[0]['text']}")
app.zweit_wartet_melden(B["id"], "zweit_wartet", "1. Trade Tradeify …4758 ist 1.800 $ vor dem TP — zweiter Start wartet")
time.sleep(0.3)
check(len(GESENDET) == 1, "derselbe Plan danach im Klick-Riegel → nicht noch einmal")
reset()
GEPLANT[:] = []
app.zweit_wartet_melden(B["id"], "zweit_wartet", "1. Trade Tradeify …4758 ist 1.800 $ vor dem TP — zweiter Start wartet (Spanne 2.500 $)")
time.sleep(0.3)
app.zweit_wartet_melden(B["id"], "zweit_wartet", "noch einmal")
time.sleep(0.3)
check(len(GESENDET) == 1 and "zu nah" in GESENDET[0]["text"] and "1.800 $" in GESENDET[0]["text"], f"Klick-Riegel → einmal: {GESENDET and GESENDET[0]['text']}")

REGEL["big_max_je_id"] = 1
reset()
GEPLANT[:] = [dict(B, status="planned", ss={"art": "zweit", "text": "schon 1 Big Trades in diesem Fenster (höchstens 1)"}),
              dict(A, id="88888888-8888-4888-8888-888888888888", status="planned", ss={"art": "firma", "text": "Big Trade „x“ läuft schon bei Tradeify"})]
app.zweit_alarm_tick(set(), JETZT)
check([x["data"] if False else x["text"].split(": wartet — ")[1].split(":")[0] for x in GESENDET] == ["gleiche Firma"],
      f"Schalter 1: „voll“ (art zweit) → kein Alarm, gleiche Firma → Alarm ({[x['text'] for x in GESENDET]})")
REGEL["big_max_je_id"] = 2
GEPLANT[:] = []

print("4) /alarm/heimweg mit prio")
reset()
OFFEN[:] = [A, B]
app.push_uid = lambda req: U
c = app.app.test_client()
JETZT_MS = int(time.time() * 1000)
body = {"plan_id": A["id"], "ok": True, "grund": "Heim-Wache", "dauer_ms": 4200, "prio": {"von": B["id"], "nach": A["id"], "a_von": 22.5, "a_nach": 8.0, "at": JETZT_MS}}
r = c.post("/alarm/heimweg", json=body)
arten = [x["art"] for x in GESENDET]
check(r.status_code == 200 and arten == ["heimweg_ok", "prio_wechsel"], f"Heimweg ok + Prio-Wechsel → zwei Zeilen: {arten}")
c.post("/alarm/heimweg", json=body)
check([x["art"] for x in GESENDET].count("prio_wechsel") == 1, "derselbe Wechsel erneut gemeldet → nur einmal")
GESENDET.clear()
c.post("/alarm/heimweg", json=dict(body, prio=dict(body["prio"], nach=B["id"])))
c.post("/alarm/heimweg", json=dict(body, ok=False, msg="x"))
c.post("/alarm/heimweg", json=dict(body, prio=dict(body["prio"], von="kein-uuid")))
check("prio_wechsel" not in [x["art"] for x in GESENDET], "nach ≠ Plan / Heimweg gescheitert / von ungültig → kein Prio-Alarm")
GESENDET.clear()
fremd = dict(B, id="77777777-7777-4777-8777-777777777777", user_id="11111111-1111-4111-8111-111111111111")
OFFEN[:] = [A, fremd]
c.post("/alarm/heimweg", json=dict(body, prio=dict(body["prio"], von=fremd["id"], at=JETZT_MS + 120000)))
check("prio_wechsel" not in [x["art"] for x in GESENDET], "von gehört einer anderen ID → nie")
OFFEN[:] = [A, B]
reset()
for i in range(5):
    c.post("/alarm/heimweg", json=dict(body, prio=dict(body["prio"], at=1700000000000 + i * 3600000)))
check([x["art"] for x in GESENDET].count("prio_wechsel") == 1, "at weit weg von jetzt (5 verschiedene) → auf Serverzeit geklemmt → nur ein Alarm")
reset()
alt = app._ap_namen
app._ap_namen = lambda: ({U: "Finn + Pascal"}, {U})
c.post("/alarm/heimweg", json=body)
app._ap_namen = alt
check("prio_wechsel" not in [x["art"] for x in GESENDET], "ausgenommene ID → kein Prio-Alarm")

print("5) Klick-Riegel merkt den Abstand (puls_heim_zweit_pruefen)")
app._sb_all = lambda t, p: [dict(A)]
app._puls_heim_naehe = lambda plaene, schw: [(p, {"nah": False, "grund": "", "rest_tp_usd": 3120.4, "rest_liq_usd": 11850}, {"plan": p["id"], "konto": "Tradeify …4758",
                                              "rest_tp_usd": 3120.4, "rest_liq_usd": 11850}, "Tradeify …4758", "BUY 3 NQ") for p in plaene]
app.puls_heim_markt_oeffnung = lambda jetzt=None: None
neu = dict(B, status="planned", started_at=None)
r = app.puls_heim_zweit_pruefen(neu)
check(r["frei"] and r.get("zweit_andere") and r["zweit_andere"][0]["plan"] == A["id"] and r["zweit_andere"][0]["rest_tp_usd"] == 3120.4,
      f"frei mit laufendem A → zweit_andere mit Abstand: {r.get('zweit_andere')}")
app._sb_all = lambda t, p: []
check("zweit_andere" not in app.puls_heim_zweit_pruefen(neu), "keiner läuft → kein zweit_andere")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
