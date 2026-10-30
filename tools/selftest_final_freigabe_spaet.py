#!/usr/bin/env python3
"""Selbsttest: FINAL-FREIGABE-SPAET (30.10.2026, Befund S5, Marc …7231). Eine Hedge-Freigabe nach dem geplanten Start setzt start_um auf jetzt +
3–6 min statt ihn am Halte-Trigger +1 Tag verfallen zu lassen; ein Start in der Zukunft wird nie vorgezogen. Ohne Netz.
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_final_freigabe_spaet.py"""
import os
import random
import sys
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


J = datetime(2026, 10, 30, 5, 0, tzinfo=timezone.utc)
F = app.hedge_freigabe_start
print("1) Rein")
werte = [datetime.fromisoformat(F((J - timedelta(minutes=37)).isoformat(), J, random.Random(s))) for s in range(200)]
sek = [(w - J).total_seconds() for w in werte]
check(all(180 <= x <= 360 for x in sek), f"37 min überfällig → jetzt + 3–6 min ({min(sek):.0f}–{max(sek):.0f} s)")
check(len({round(x) for x in sek}) > 50, "gewürfelt, kein fester Takt")
check(F((J + timedelta(minutes=1)).isoformat(), J) is None and F((J + timedelta(hours=5)).isoformat(), J) is None, "Start in der Zukunft: nie vorziehen")
check(F(None, J) is None and F("kaputt", J) is None, "kein/unlesbarer Start: nicht anfassen")

print("2) Schreiben")
PL = {"a0000000-0000-0000-0000-000000000001": (datetime.now(timezone.utc) - timedelta(minutes=37)).isoformat(),
      "a0000000-0000-0000-0000-000000000002": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()}
LOG = []
app.sb_select = lambda t, p: [{"id": i, "start_um": s} for i, s in PL.items()]


def upd(t, p, b):
    LOG.append((dict(p), dict(b)))
    return [{"id": 1}]


app.sb_update = upd
BASIS = {"status": "eq.planned", "start_um_gestartet_at": "is.null", "hedge_freigabe_at": "is.null"}
n = app._hedge_freigabe_schreiben(list(PL), BASIS, "uid-1")
ueber = [x for x in LOG if "start_um" in x[1]]
rest = [x for x in LOG if "start_um" not in x[1]]
check(n == 2, f"beide freigegeben ({n})")
check(len(ueber) == 1 and ueber[0][0]["id"].endswith("1") and ueber[0][0]["start_um"].startswith("lte.") and ueber[0][1].get("hedge_freigabe_von") == "uid-1",
      "überfälliger Plan: Freigabe + neuer Start im selben Update, Guard auf den überfälligen Stand")
check(len(rest) == 1 and rest[0][0]["id"].endswith("2)") and "start_um" not in rest[0][1], "Plan in der Zukunft: nur die Freigabe")
check(all(x[0]["status"] == "eq.planned" and x[0]["start_um_gestartet_at"] == "is.null" for x in LOG), "Guard (geplant, ungeclaimt) überall")
LOG.clear()
app.sb_update = lambda t, p, b: (LOG.append((dict(p), dict(b))), [] if "start_um" in b else [{"id": 1}])[1]
PL.pop("a0000000-0000-0000-0000-000000000002")
n = app._hedge_freigabe_schreiben(list(PL), BASIS, "uid-1")
check(n == 1 and len(LOG) == 2 and "start_um" not in LOG[1][1], "Start inzwischen von Hand geändert: Freigabe bleibt, Start wird nicht überschrieben")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
