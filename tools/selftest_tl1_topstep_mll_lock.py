#!/usr/bin/env python3
"""Selbsttest TL1 — Topstep-MLL-Lock (Master 12.11.2026, Antwort des Topstep-Supports an Finn: „Once the MLL reaches the starting balance (e.g. $150,000 on a
150K account), it locks permanently and will not trail any higher.“ / Express: „locks at $0 once the balance reaches the threshold“).

Aufruf:  python3 tools/selftest_tl1_topstep_mll_lock.py
Ohne Netz, Platzhalter-IDs, echte Funktionen aus app.py. Prüft: Marc-Fall (Lesungen 05.11. 145.500, 06.11. 148.092, 09.11. 150.000 in einem Plan OHNE konto_typ,
Tagesschluss 06.11. 157.087) → MLL 150.000 und kein Blow bei 152.352; Mike-Fall vom 15.10. (Lesung 145.500, Zwischenstand 152.299 zählt nicht) bleibt 145.500;
Lock bei der Startgröße ohne Lesung; unter dem Lock wie bisher; Express-Lock bei 0; Blow-Urteil nimmt die neueste Lesung des Plans."""
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


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


K = "00000000-0000-0000-0000-00000000aa01"
ACC = {"id": K, "account_type": "challenge", "firm": "Topstep"}
MB = app.ap_kette_mll_belegt


def zeile(start, ende, bal_end, mll=None, typ="challenge"):
    return {"master_account_id": K, "konto_typ": typ, "started_at": start, "ended_at": ende, "bal_end": bal_end, "mll_start": mll}


print("1) Marc …22631094 (Vorfall 11.11.2026)")
MARC = [zeile("2026-11-05T16:36:05Z", "2026-11-05T16:38:00Z", 152592.44, 145500),
        zeile("2026-11-06T05:53:39Z", "2026-11-06T06:02:00Z", 154894.88, 148092.44),
        zeile("2026-11-06T10:37:46Z", "2026-11-06T11:41:00Z", 157087.32, 148092.44),
        zeile("2026-11-09T13:33:34Z", "2026-11-09T15:10:59Z", 154087.32, 150000, typ=None)]     # Plan 272809d8: konto_typ fehlte
PLAN_AM = datetime(2026, 11, 10, 22, 0, tzinfo=timezone.utc)
m, q = MB(150000, 4500, ACC, MARC, jetzt=PLAN_AM)
check(m == 150000.0 and "09.11." in q, f"Planung 11.11.: MLL 150.000 aus der Lesung vom 09.11. (Plan ohne konto_typ zählt) — {m} · {q}")
m2, q2 = MB(150000, 4500, ACC, MARC[:3], jetzt=PLAN_AM)
check(m2 == 150000.0 and "gelockt" in q2, f"ohne die Lesung vom 09.11.: Tagesschluss 157.087 − 4.500 = 152.587 → gelockt bei 150.000 — {m2} · {q2}")
m3, _ = MB(150000, 4500, ACC, MARC[:3] + [dict(MARC[3], konto_typ="funded")], jetzt=PLAN_AM)
check(m3 == 150000.0, "eine Lesung mit ANDEREM konto_typ zählt nicht — der Lock hält trotzdem bei 150.000")
K109 = {"nr": 1, "mll": 152587.32, "daily_usd": 3000, "angefressen": True, "reparatur": True, "verlust_grenze": 1592}
TV109 = {"mll_start": 150000, "balance_start": 153979.76}
u = app.ap_kette_mll_urteil(K109, TV109)
blown = 152352.2 <= u + app.AP_KETTE_MLL_TOLERANZ
check(u == 150000.0 and not blown, f"Blow-Urteil Plan 109bf70d: Lesung beim Start 150.000 geht dem Plan-MLL 152.587 vor → 152.352 ist NICHT blown (MLL {u})")
check(152352.2 <= 152587.32 + app.AP_KETTE_MLL_TOLERANZ, "Gegenprobe: mit dem alten Plan-MLL wäre es blown gewesen (der Vorfall)")

print("2) Mike …17758280 (15.10.2026) bleibt")
MIKE = [zeile("2026-10-12T23:30:00Z", "2026-10-12T23:39:00Z", 152299.0, 145500),     # Zwischenstand desselben CME-Tags
        zeile("2026-10-13T09:00:00Z", "2026-10-13T09:41:00Z", 147124.0, 145500)]
mm, qm = MB(150000, 4500, ACC, MIKE, jetzt=datetime(2026, 10, 15, 6, 0, tzinfo=timezone.utc))
check(mm == 145500.0, f"Mike: Lesung 145.500 bleibt (Tagesschluss 147.124 − 4.500 liegt darunter, der Zwischenstand 152.299 zählt nie) — {mm} · {qm}")

print("3) Lock ohne Lesung, unter dem Lock, Rückfall")
OHNE = [zeile("2026-11-02T10:00:00Z", "2026-11-02T11:00:00Z", 156200.0), zeile("2026-11-03T10:00:00Z", "2026-11-03T11:00:00Z", 155000.0)]
mo, qo = MB(150000, 4500, ACC, OHNE, jetzt=PLAN_AM)
check(mo == 150000.0 and "gelockt" in qo, f"ohne Lesung, Tagesschluss 156.200: 151.700 → gelockt 150.000 — {mo} · {qo}")
mu, qu = MB(150000, 4500, ACC, [zeile("2026-11-02T10:00:00Z", "2026-11-02T11:00:00Z", 152000.0)], jetzt=PLAN_AM)
check(mu == 147500.0 and "gelockt" not in qu, f"unter dem Lock wie bisher: 152.000 − 4.500 = 147.500 — {mu}")
mr, _ = MB(150000, 4500, ACC, [], jetzt=PLAN_AM, peak=157000, balance=156000)
check(mr == 150000.0, "ohne Lesung und Tagesschluss: Hochpunkt 157.000 → gelockt 150.000")
check(app.ap_kette_mll(150000, 4500, 157087, 154000) == 150000.0 and app.ap_kette_mll(150000, 4500, 151000, 150500) == 146500.0
      and app.ap_kette_mll(50000, 2000, 53000, 52000) == 50000.0, "ap_kette_mll: min(Startgröße, Höchststand − dd) — auch 50K")
NACH = MARC[:2] + [zeile("2026-11-03T10:00:00Z", "2026-11-03T11:00:00Z", 151000.0, 146000)]
mn, qn = MB(150000, 4500, ACC, NACH, jetzt=PLAN_AM)
check(mn == 150000.0 or mn == 148092.44, f"Lesung 06.11. + Tagesschluss danach (157.087 − 4.500) höchstens 150.000 — {mn} · {qn}")

print("4) Express (0-basiert): Lock bei 0")
EX = {"id": K, "account_type": "funded", "max_drawdown": 2000}
ex = [{"master_account_id": K, "mll_start": -2000, "started_at": "2026-11-05T10:00:00Z", "ended_at": "2026-11-05T11:00:00Z", "bal_end": 2600}]
e1, q1 = app.wd_sl_express_mll(EX, ex)
check(e1 == 0.0, f"Express: Schluss 2.600 − 2.000 = 600 → gelockt bei 0 — {e1} · {q1}")
e2, _ = app.wd_sl_express_mll(EX, [dict(ex[0], bal_end=1200)])
check(e2 == -800.0, "Express unter der Schwelle: 1.200 − 2.000 = −800 (trailt weiter)")
e3, _ = app.wd_sl_express_mll(EX, [dict(ex[0], mll_start=0, bal_end=5000)])
check(e3 == 0.0, "Express: Lesung 0 bleibt 0, auch bei hohem Stand")

print("5) Blow-Urteil-Helfer")
check(app.ap_kette_mll_urteil({"mll": 152587.32}, None) == 152587.32 and app.ap_kette_mll_urteil({"mll": 152587.32}, {}) == 152587.32,
      "ohne Lesung: Plan-MLL")
check(app.ap_kette_mll_urteil({"mll": 145500}, {"mll_start": 148092.44}) == 148092.44, "neuere Lesung höher als das Plan-MLL → die Lesung gilt (neueste Wahrheit)")
check(app.ap_kette_mll_urteil({"mll": 150000}, {"mll_start": -1500}) == 150000 and app.ap_kette_mll_urteil({"mll": 150000}, {"mll_start": 0}) == 150000,
      "0-basierte / leere Lesung im Combine-Plan zählt nicht")
check(app.ap_kette_mll_urteil({}, {"mll_start": 150000}) == 150000.0 and app.ap_kette_mll_urteil(None, None) is None, "ohne Plan-MLL: Lesung bzw. None")

print("6) Anker")
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
ab = src[src.index("def ap_kette_abhaken("):src.index("def ap_kette_abhaken(") + 12000]
check('ap_kette_mll_urteil(k, _kb.get("tv"))' in ab and "float(bal[1]) <= _mll_u + AP_KETTE_MLL_TOLERANZ" in ab and "float(bal[1]) <= _mll_u and" in ab,
      "ap_kette_abhaken (setzte am 11.11. blown=true) urteilt mit der neuesten Lesung")
check('ap_kette_mll_urteil(k, (p.get("mt5_baseline") or {}).get("tv"))' in src and "blown = echt[1] <= _mll_u + AP_KETTE_MLL_TOLERANZ" in src,
      "tt_tick-Tagesende (Topstep) urteilt genauso")
check("mll = min(st, pk - dd)" in src and "kein Lock mehr (13.10.2026)" not in src, "Chance-Rechnung: MLL = min(Start, Höchststand − dd), Kommentar auf den Support-Beleg")
check('(f.get("konto_typ") and str(f["konto_typ"]).lower() != typ)' in src, "Lesung ohne konto_typ zählt (nur ein anderer Typ fällt raus)")

print()
if FEHLER:
    print(f"{len(FEHLER)} FEHLER")
    sys.exit(1)
print("alles grün")
