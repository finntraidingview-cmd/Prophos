#!/usr/bin/env python3
"""Selbsttest M1 (05.11.2026): Funded-CFD-Planer würfelt nie in die Index-Pause. Vorfall 03./04.11.2026: Blue Guardian …8631 um 02:11 Dubai,
FundingPips …8534 um 02:27 Dubai vorgeschlagen — NAS100 handelt dann nicht (CME 16:00–17:00 Chicago = Winter 02:00–03:00 Dubai).
Prüft fcp_cfd_offen (Pause, Puffer, cfd_ab des Challenge-Planers, Sommer/Winter, Wochenende), fcp_pause_verschieben, fdp_start_verteilen
mit erlaubt (Bestätigen) und ganze Läufe fcp_planen gegen eine nachgebaute DB (Würfeln + Verschieben bestehender Pläne). Ohne Netz.
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_fcp_index_pause.py"""
import json
import os
import random
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
U = timezone.utc


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


# auto_plan_regeln.zeiten live (05.11.2026, SELECT)
AP_Z = {"tz": "Europe/Berlin", "cfd_ab": {"tz": "Asia/Dubai", "uhr": "02:15"}, "cfd_bis": {"tz": "Asia/Dubai", "uhr": "18:00"},
        "fenster": [["02:00", "20:00", 100]], "nachtlauf": {"tz": "Asia/Dubai", "uhr": "01:30"}, "start_bis": "20:00",
        "fenster_tz": "Asia/Dubai", "abstand_id_min": 3, "abstand_konto_s": [60, 120], "pause_firma_min": [25, 45]}
DUBAI = app._ap_tz("Asia/Dubai")
dub = lambda t: t.astimezone(DUBAI).strftime("%d.%m %H:%M")   # noqa: E731
offen = lambda t, z=AP_Z: app.fcp_cfd_offen(t, z)              # noqa: E731

print("1) fcp_cfd_offen — Index-Pause, Puffer, cfd_ab")
for t, soll, text in [
        (datetime(2026, 11, 3, 22, 11, tzinfo=U), False, "Vorfall Blue Guardian 04.11 02:11 Dubai (Winter, Pause)"),
        (datetime(2026, 11, 3, 22, 27, tzinfo=U), False, "Vorfall FundingPips 04.11 02:27 Dubai (Winter, Pause)"),
        (datetime(2026, 11, 3, 23, 0, tzinfo=U), False, "03:00 Dubai Winter — Öffnung, im Puffer"),
        (datetime(2026, 11, 3, 23, 14, tzinfo=U), False, "03:14 Dubai Winter — noch im Puffer"),
        (datetime(2026, 11, 3, 23, 15, tzinfo=U), True, "03:15 Dubai Winter — offen"),
        (datetime(2026, 11, 4, 4, 0, tzinfo=U), True, "08:00 Dubai Mittwoch — offen"),
        (datetime(2026, 11, 4, 16, 0, tzinfo=U), True, "20:00 Dubai Mittwoch — offen (Fensterende setzt der Planer)"),
        (datetime(2026, 10, 14, 21, 30, tzinfo=U), False, "Sommer 01:30 Dubai — CME-Pause (16:30 CDT)"),
        (datetime(2026, 10, 14, 22, 10, tzinfo=U), False, "Sommer 02:10 Dubai — Puffer / vor cfd_ab 02:15"),
        (datetime(2026, 10, 14, 22, 20, tzinfo=U), True, "Sommer 02:20 Dubai — offen"),
        (datetime(2026, 11, 7, 8, 0, tzinfo=U), False, "Samstag — zu"),
        (datetime(2026, 11, 8, 22, 0, tzinfo=U), False, "Sonntag 02:00 Dubai Montag — vor Wochenöffnung"),
        (datetime(2026, 11, 8, 23, 20, tzinfo=U), True, "Montag 03:20 Dubai — Woche offen")]:
    check(offen(t) is soll, f"{text}: {offen(t)}")
check(app.fcp_cfd_offen(datetime(2026, 11, 3, 23, 16, tzinfo=U), {}) is False and app.fcp_cfd_offen(datetime(2026, 11, 3, 23, 21, tzinfo=U), {}) is True,
      "ohne Challenge-Zeiten: Code-Standard cfd_ab 00:20 dt (= 03:20 Dubai im Winter)")
check(app.fcp_cfd_offen(datetime(2026, 11, 4, 4, 0, tzinfo=U), {"cfd_ab": {"tz": "Asia/Dubai", "uhr": "09:00"}}) is False,
      "cfd_ab des Challenge-Planers greift (09:00 Dubai → 08:00 Dubai zu)")
check(app.fcp_cfd_offen("kaputt", AP_Z) is False, "nicht rechenbar → zu (fail-closed)")

print("2) fcp_pause_verschieben")
J = datetime(2026, 11, 3, 20, 40, tzinfo=U)                     # 00:40 Dubai 04.11 — Lauf des Vorfalls
fp = lambda t, **x: dict({"art": "cfd", "start_um": t}, **x)   # noqa: E731
P = [{"id": "p1", "status": "planned", "start_um": None, "funded_plan": fp("2026-11-03T22:11:22+00:00")},                 # Vorschlag in Pause
     {"id": "p2", "status": "planned", "start_um": "2026-11-03T22:27:37+00:00", "funded_plan": fp("2026-11-03T22:27:37+00:00")},   # bestätigt
     {"id": "p3", "status": "planned", "start_um": "2026-11-04T04:00:00+00:00", "funded_plan": fp("2026-11-04T04:00:00+00:00")},   # 08:00 ok
     {"id": "p4", "status": "planned", "start_um": "2026-11-03T22:15:00+00:00", "started_at": "2026-11-03T22:15:05+00:00", "funded_plan": fp("x")},
     {"id": "p5", "status": "planned", "start_um": "2026-11-03T22:15:00+00:00", "start_um_gestartet_at": "2026-11-03T22:15:01+00:00", "funded_plan": fp("x")},
     {"id": "p6", "status": "planned", "start_um": "2026-11-03T22:20:00+00:00", "funded_plan": {"start_um": "x"}},           # Futures-Planer
     {"id": "p7", "status": "completed", "start_um": "2026-11-03T22:20:00+00:00", "funded_plan": fp("x")},
     {"id": "p8", "status": "planned", "start_um": "2026-11-03T19:00:00+00:00", "funded_plan": fp("x")}]                     # überfällig, jetzt offen
ids = [p["id"] for p in app.fcp_pause_verschieben(P, J, offen)]
check(ids == ["p1", "p2"], f"nur ungestartete Funded-CFD-Pläne mit Start in der Pause: {ids}")
P += [{"id": "p9", "status": "planned", "start_um": "2026-11-03T22:05:00+00:00", "funded_plan": fp("x")},                    # 25 min überfällig
      {"id": "p10", "status": "planned", "start_um": "2026-11-04T22:30:00+00:00", "funded_plan": fp("x")}]                   # morgen 02:30 Dubai
ids = [p["id"] for p in app.fcp_pause_verschieben(P, datetime(2026, 11, 3, 22, 30, tzinfo=U), offen, bis_dt=datetime(2026, 11, 4, 16, 0, tzinfo=U))]
check("p9" in ids and "p1" in ids and "p3" not in ids, f"überfällig ≤ 30 min, während jetzt Pause ist → verschieben: {ids}")
check("p8" not in ids, "3,5 h überfällig → nicht wiederbeleben (PC-Tab verbraucht ihn)")
check("p10" not in ids, "Plan für morgen (nach dem Fensterende des Laufs) bleibt dem Lauf seines Tages")
v = app.fcp_sicht({"verschoben": [{"user_id": "u1"}, {"user_id": "u2"}], "geplant": []}, "u1")
check([x["user_id"] for x in v["verschoben"]] == ["u1"], "fcp_sicht filtert verschoben nach Sicht")

print("3) Bestätigen — fdp_start_verteilen mit erlaubt")
jetzt = datetime(2026, 11, 3, 22, 5, tzinfo=U)                  # 02:05 Dubai, Pause
pl = [{"id": "v1", "fp_start": "2026-11-03T22:11:00+00:00", "firma": "ht|bg", "user_id": "u1"},
      {"id": "v2", "fp_start": "2026-11-03T22:27:00+00:00", "firma": "ht|fp", "user_id": "u2"},
      {"id": "v3", "fp_start": "2026-11-04T05:00:00+00:00", "firma": "ht|fp", "user_id": "u3"}]
for s in range(20):
    st = app.fdp_start_verteilen(pl, [], jetzt, 900, 600, rnd=random.Random(s), erlaubt=offen)
    t = {k: datetime.fromisoformat(v) for k, v in st.items()}
    if not all(offen(x) for x in t.values()) or t["v3"] != datetime(2026, 11, 4, 5, 0, tzinfo=U) or not t["v1"] >= datetime(2026, 11, 3, 23, 15, tzinfo=U):
        check(False, f"Seed {s}: {[(k, dub(v)) for k, v in t.items()]}")
        break
else:
    check(True, "20 Seeds: Pause-Vorschläge rücken hinter 03:15 Dubai, gute Zeit bleibt, alle offen")
st = app.fdp_start_verteilen(pl, [("ht|bg", "u9", True, datetime(2026, 11, 3, 23, 20, tzinfo=U))], jetzt, 900, 600, rnd=random.Random(1), erlaubt=offen)
check(abs((datetime.fromisoformat(st["v1"]) - datetime(2026, 11, 3, 23, 20, tzinfo=U)).total_seconds()) >= 900, "Firmen-Abstand gilt auch hinter der Pause")
st = app.fdp_start_verteilen(pl, [], jetzt, 900, 600, rnd=random.Random(1), erlaubt=lambda x: False)
check(all(v is None for v in st.values()), "kein erlaubter Start → None (Bestätigen lässt den Vorschlag stehen, nie in die Pause)")
a = app.fdp_start_verteilen(pl, [], jetzt, 900, 600, rnd=random.Random(7))
b = app.fdp_start_verteilen(pl, [], jetzt, 900, 600, rnd=random.Random(7), erlaubt=None)
check(a == b and datetime.fromisoformat(a["v1"]) == datetime(2026, 11, 3, 22, 11, tzinfo=U), "ohne erlaubt unverändert (Funded Futures)")

print("4) Ganze Läufe fcp_planen gegen nachgebaute DB")
sql = open(os.path.join(WURZEL, "sql", "2026-10-30_funded_cfd_planer.sql"), encoding="utf-8").read()
FIRMEN = json.loads(re.search(r"'(\[\s*\{.*?\]\s*)'::jsonb", sql, re.S).group(1))
PPL = {"the5ers": 1.0, "fundednext": 10.0, "fundingpips": 20.0}
H1, H2 = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
FUS = {H1: "f1", H2: "f2"}
konto = lambda i, u, n, f, b: {"id": i, "user_id": u, "name": n, "firm": f, "account_type": "funded_cfd", "external_id": "L" + i[-4:],   # noqa: E731
                               "tv_balance": None, "created_at": "2026-10-01T00:00:00+00:00", "_bal": b}
KONTEN = [konto("a1000000-0000-0000-0000-000000000001", H1, "100k 1 → Funded", "FundedNext", 98000.0),
          konto("a1000000-0000-0000-0000-000000000002", H1, "100k 2 → Funded", "FundedNext", 100000.0),
          konto("a1000000-0000-0000-0000-000000000003", H2, "200k 3 → Funded", "The5%ers", 200000.0),
          konto("a1000000-0000-0000-0000-000000000004", H2, "100k 4 → Funded", "The5%ers", 101600.0),
          konto("a1000000-0000-0000-0000-000000000005", H2, "50k 5 → Funded", "FundingPips", 50000.0)]
REG = {"id": 1, "aktiv": True, "auto_bestaetigen": True, "ziel_auto_wartet": False, "user_ids": [H1, H2], "firmen": FIRMEN,
       "zeiten": {"firma_abstand_min": 15, "abstand_id_min": 10, "vorlauf_min": 15}}
ST = {"plaene": [], "frisch": None}
GESCHRIEBEN = []


def sb_select(t, p):
    if t == "funded_cfd_plan_regeln":
        return [REG]
    if t == "auto_plan_regeln":
        return [{"zeiten": AP_Z}]
    if t == "trade_plans" and p.get("select") == "mt5_baseline,notes":
        pid = p["id"][3:]
        return [{"mt5_baseline": {"funded_plan": dict(next(x for x in ST["plaene"] if x["id"] == pid)["funded_plan"]), "andere": 1}, "notes": "Funded-CFD-Planer"}]
    return []


def sb_all(t, p):
    if t == "accounts" and p.get("account_type") == "eq.funded_cfd":
        return [{k: v for k, v in a.items() if k != "_bal"} for a in KONTEN]
    if t == "accounts":
        return [{"id": v, "name": "Fusion " + v, "firm": "Fusion Markets"} for v in FUS.values()]
    if t == "trade_plans" and "master_account_id" in p:
        return [dict(x) for x in ST["plaene"]]
    if t == "trade_plans":
        return [dict(x, fp_start=(x.get("funded_plan") or {}).get("start_um")) for x in ST["plaene"] if x.get("status") in ("planned", "open", "review")]
    if t == "user_settings":
        return [{"user_id": u, "value": {"accountId": f}} for u, f in FUS.items()]
    if t == "firm_specs":
        return [{"user_id": u, "name": n, "ppl": PPL[app._ap_norm(n)], "unit": "Lots"} for u in FUS for n in ("FundedNext", "The5%ers", "FundingPips")]
    return []


app.sb_select, app._sb_all = sb_select, sb_all
app.sb_insert = lambda t, z: GESCHRIEBEN.append(("insert", t, z))
app.sb_update = lambda t, flt, upd: (GESCHRIEBEN.append(("update", t, flt, upd)), [1])[1]
app._ap_archiviert = lambda streng=False: set()
app._ap_namen = lambda: ({H1: "HT-1", H2: "HT-2"}, set())
app._fd_gruppen_ids = lambda: []
app._fcp_gruppe_je_uid = lambda uids: {u: "ht" for u in uids}
app.gp_hedge_settings_eigen = lambda rows: rows
app._ap_balance_karten = lambda: ({a["external_id"]: (a["_bal"], "USD", ST["frisch"]) for a in KONTEN}, {})


def lauf(jetzt, seed, trocken=True):
    ST["frisch"] = (jetzt - timedelta(minutes=30)).isoformat()
    return app.fcp_planen(trocken=trocken, jetzt=jetzt, seed=seed)


for jetzt, text in [(datetime(2026, 11, 3, 20, 40, tzinfo=U), "00:40 Dubai 04.11 (Lauf des Vorfalls, vor dem Nachtlauf)"),
                    (datetime(2026, 11, 3, 21, 40, tzinfo=U), "01:40 Dubai 04.11 (nach dem Nachtlauf)"),
                    (datetime(2026, 11, 3, 22, 20, tzinfo=U), "02:20 Dubai 04.11 (mitten in der Pause)"),
                    (datetime(2026, 11, 4, 4, 0, tzinfo=U), "08:00 Dubai 04.11 (Tag)")]:
    alle, n, schlecht = [], 0, []
    for s in range(15):
        e = lauf(jetzt, s)
        for z in e["geplant"]:
            t = datetime.fromisoformat(z["start_um"])
            n += 1
            alle.append(t)
            if not offen(t):
                schlecht.append(dub(t))
    rng = f"{dub(min(alle))} – {dub(max(alle))}" if alle else "keine"
    check(not schlecht, f"{text}: {n} Starts in 15 Läufen, keiner in der Pause ({rng} Dubai){' — IN DER PAUSE: ' + ', '.join(schlecht[:4]) if schlecht else ''}")
check(sum(len(lauf(datetime(2026, 11, 4, 4, 0, tzinfo=U), s)["geplant"]) for s in range(3)) >= 9, "am Tag wird weiter normal geplant (≥ 3 je Lauf)")

print("5) Nachplanen verschiebt bestehende Pläne aus der Pause")
K1, K3, K5 = KONTEN[0]["id"], KONTEN[2]["id"], KONTEN[4]["id"]
ST["plaene"] = [
    {"id": "p1", "user_id": H1, "master_account_id": K1, "master_firm": "FundedNext", "status": "planned", "start_um": None,
     "funded_plan": {"art": "cfd", "start_um": "2026-11-03T22:11:22+00:00", "ziel": 1}},
    {"id": "p3", "user_id": H2, "master_account_id": K3, "master_firm": "The5%ers", "status": "planned", "start_um": "2026-11-03T22:27:37+00:00",
     "funded_plan": {"art": "cfd", "start_um": "2026-11-03T22:27:37+00:00"}},
    {"id": "p5", "user_id": H2, "master_account_id": K5, "master_firm": "FundingPips", "status": "planned", "start_um": "2026-11-04T05:00:00+00:00",
     "funded_plan": {"art": "cfd", "start_um": "2026-11-04T05:00:00+00:00"}}]
GESCHRIEBEN.clear()
e = lauf(datetime(2026, 11, 3, 20, 40, tzinfo=U), 3, trocken=False)
up = {g[2]["id"][3:]: (g[2], g[3]) for g in GESCHRIEBEN if g[0] == "update" and g[1] == "trade_plans"}
print("     " + " · ".join(v["grund"] for v in e.get("verschoben") or []))
check(set(up) == {"p1", "p3"}, f"p1 + p3 verschoben, p5 (09:00 Dubai) bleibt: {sorted(up)}")
if "p1" in up:
    flt, u1 = up["p1"]
    t1 = datetime.fromisoformat(u1["mt5_baseline"]["funded_plan"]["start_um"])
    check(offen(t1) and "start_um" not in u1, f"Vorschlag p1: nur die vorgeschlagene Zeit → {dub(t1)} Dubai (offen), start_um bleibt leer")
    check(u1["mt5_baseline"].get("andere") == 1 and u1["mt5_baseline"]["funded_plan"].get("ziel") == 1, "übrige mt5_baseline/funded_plan-Felder bleiben")
    check(flt.get("status") == "eq.planned" and flt.get("started_at") == "is.null" and flt.get("start_um_gestartet_at") == "is.null",
          "Update nur, solange nie geclaimt/gestartet")
    check("Index-Pause" in u1["notes"], "Notiz-Zeile ⏱ Index-Pause")
if "p3" in up:
    u3 = up["p3"][1]
    check(u3.get("start_um") == u3["mt5_baseline"]["funded_plan"]["start_um"] and offen(datetime.fromisoformat(u3["start_um"])),
          f"bestätigter Plan p3: start_um + funded_plan.start_um → {dub(datetime.fromisoformat(u3['start_um']))} Dubai")
# nach dem Nachtlauf (01:40 Dubai): verschobene Pläne + neue Vorschläge der übrigen Konten im selben Lauf — Abstände untereinander
for s in range(10):
    GESCHRIEBEN.clear()
    e = lauf(datetime(2026, 11, 3, 21, 40, tzinfo=U), s, trocken=False)
    vs = {g[2]["id"][3:]: datetime.fromisoformat(g[3]["mt5_baseline"]["funded_plan"]["start_um"]) for g in GESCHRIEBEN if g[0] == "update" and g[1] == "trade_plans"}
    ins = [(g[2]["user_id"], g[2]["master_firm"], datetime.fromisoformat(g[2]["start_um"] or g[2]["mt5_baseline"]["funded_plan"]["start_um"]))
           for g in GESCHRIEBEN if g[0] == "insert" and g[1] == "trade_plans"]
    alle = [(H1, "FundedNext", vs.get("p1")), (H2, "The5%ers", vs.get("p3"))] + ins
    ok = set(vs) == {"p1", "p3"} and len(ins) == 1 and all(t and offen(t) for _u, _f, t in alle)
    for i, (u1, f1, t1) in enumerate(alle):
        for u2, f2, t2 in alle[i + 1:]:
            if t1 and t2 and ((u1 == u2 and abs((t1 - t2).total_seconds()) < 600) or (f1 == f2 and abs((t1 - t2).total_seconds()) < 900)):
                ok = False
    if not ok:
        check(False, f"Seed {s}: verschoben {[(k, dub(v)) for k, v in vs.items()]} neu {[(f, dub(t)) for _u, f, t in ins]}")
        break
else:
    check(True, "10 Läufe um 01:40 Dubai: p1/p3 verschoben + neuer Vorschlag Konto 2 (FundedNext, dieselbe ID wie p1; Konto 4 Ziel erreicht), alle offen, Abstand je ID ≥ 10 min / Firma ≥ 15 min")
GESCHRIEBEN.clear()
e = lauf(datetime(2026, 11, 3, 20, 40, tzinfo=U), 3, trocken=True)
check(len(e.get("verschoben") or []) == 2 and not GESCHRIEBEN, "Trockenlauf meldet verschoben, schreibt nichts")
ST["plaene"] = []

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER:\n  - " + "\n  - ".join(FEHLER))
sys.exit(1 if FEHLER else 0)
