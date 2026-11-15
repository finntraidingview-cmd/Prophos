#!/usr/bin/env python3
"""Selbsttest NP1 (16.11.2026, Master/Finn) — Abhaken ist kein Handeln: abgehakte Konten kommen am selben Tag zurück in die Nachplanung.

Anlass: Finn hakte die Freitagstrades vom 13.11. am 16.11. ~03:00 Dubai ab (= 00:00 deutsche Zeit, AP_TZ_TAG). completed_at fiel auf den neuen Tag,
_ap_plan_am_tag belegte die Konten als „heute gehandelt“ (Schleife über started_at/ended_at/completed_at/start_um, ein Treffer reichte) — 5 Konten blieben
den ganzen Tag draußen, auch nachdem der Master den Überprüfen-Grund per SQL freigegeben hatte.

Aufruf:  python3 tools/selftest_np1_abgehakt_nachplan.py
Ohne Netz, Platzhalter-IDs. Lädt die Auto-Planer-Funktionen wie selftest_auto_nachplanen und prüft:
  _ap_plan_am_tag (completed): started_at/ended_at entscheiden; Freitag gehandelt + heute abgehakt → frei; heute beendet (Inas Tagesstopp) → belegt;
  start_um/completed_at nur als Rückfall ohne beide Handelszeiten · Überprüfen/laufend/geplant/kette_te unverändert · Fall 16.11. über die Nachplan-Kandidaten
  (Lauf ohne Überprüfen-Zeilen wie _ap_nachplan_rechnen) · ap_planen nutzt _ap_plan_am_tag für „heute schon gehandelt“."""
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_nachplanen as sn  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


a = sn.lade()
src = open(sn.sd.APP, encoding="utf-8").read()
PT, K, LO = a["_ap_plan_am_tag"], a["ap_nachplan_kandidaten"], a["ap_gruppe_lauf_ohne_erledigt"]
TZ = ZoneInfo("Europe/Berlin")
TAG = "2026-11-16"
GRUND = "letzter Trade noch nicht erledigt (Überprüfen)"


def kid(n):
    return f"00000000-0000-0000-0000-{n:012d}"


# ── _ap_plan_am_tag, status completed ──
fr = {"status": "completed", "planned_for": "2026-11-13", "start_um": "2026-11-13T14:02:00+00:00", "started_at": "2026-11-13T14:02:28+00:00",
      "ended_at": "2026-11-13T14:29:08+00:00", "completed_at": "2026-11-15T23:00:11+00:00"}          # wie live: Freitag gehandelt, Mo 00:00 dt abgehakt
check(PT(fr, TAG, TZ) is False, "Freitagstrade, Montag 00:00 dt abgehakt → belegt Montag NICHT (Abhaken ist kein Handeln)")
check(PT(fr, "2026-11-13", TZ) is True, "derselbe Trade belegt seinen Handelstag (13.11.)")
ina = {"status": "completed", "start_um": "2026-11-15T21:00:00+00:00", "started_at": "2026-11-15T21:00:30+00:00",
       "ended_at": "2026-11-15T23:57:00+00:00", "completed_at": "2026-11-16T02:00:00+00:00"}          # gestern (dt) gestartet, heute 00:57 dt im Tagesstopp beendet
check(PT(ina, TAG, TZ) is True, "Inas Fall: heute beendet (Tagesstopp) → belegt weiter")
check(PT(dict(fr, started_at="2026-11-16T05:00:00+00:00", ended_at="2026-11-16T05:30:00+00:00"), TAG, TZ) is True, "heute gehandelt und abgehakt → belegt")
check(PT(dict(fr, ended_at=None), TAG, TZ) is False, "nur started_at (Freitag) → frei, auch wenn completed_at heute")
check(PT(dict(fr, start_um="2026-11-16T06:00:00+00:00"), TAG, TZ) is False, "Handelszeiten vorhanden → start_um zählt nicht mit")
check(PT({"status": "completed", "start_um": "2026-11-16T06:00:00+00:00", "completed_at": "2026-11-17T07:00:00+00:00"}, TAG, TZ) is True,
      "ohne started/ended: start_um heute → belegt (Rückfall)")
check(PT({"status": "completed", "start_um": "2026-11-13T06:00:00+00:00", "completed_at": "2026-11-16T07:00:00+00:00"}, TAG, TZ) is True,
      "ohne started/ended: completed_at heute → belegt (Rückfall, alte Hand-Zeile)")
check(PT({"status": "completed", "completed_at": "2026-11-15T07:00:00+00:00"}, TAG, TZ) is False, "nur completed_at gestern → frei")
check(PT({"status": "completed", "started_at": "Murks", "ended_at": "", "completed_at": "2026-11-16T07:00:00+00:00"}, TAG, TZ) is True,
      "Handelszeiten unlesbar → Rückfall auf completed_at")
check(PT({"status": "completed"}, TAG, TZ) is False, "completed ganz ohne Zeiten → frei (wie bisher)")
check(PT({"status": "review", "started_at": "2026-11-13T14:02:28+00:00"}, TAG, TZ) is True, "Überprüfen belegt weiter immer")
check(PT({"status": "open"}, TAG, TZ) is True and PT({"status": "planned", "planned_for": TAG}, TAG, TZ) is True
      and PT({"status": "planned", "planned_for": "2026-11-17"}, TAG, TZ) is False, "laufend / geplant unverändert")
te = {"status": "review", "kette_te": {"tag": "2026-11-13"}, "started_at": "2026-11-13T20:00:00+00:00", "ended_at": "2026-11-13T20:30:00+00:00"}
check(PT(te, TAG, TZ) is False and PT(te, "2026-11-13", TZ) is True, "letzter Topstep-Trade (kette_te): nur sein Handelstag belegt (unverändert)")

# ── Fall 16.11. über die Nachplan-Kandidaten (Lauf wie in _ap_nachplan_rechnen ohne Überprüfen-Zeilen) ──
konten = [{"id": kid(n), "account_type": "phase1"} for n in range(1, 8)]
lauf = {"tag": TAG, "at": "2026-11-15T21:30:40+00:00", "ausgelassen": [{"konto_id": kid(n), "grund": GRUND} for n in range(1, 8)]}
plaene = [dict(fr, master_account_id=kid(n)) for n in range(1, 6)]                                        # 5 abgehakt
plaene += [{"master_account_id": kid(n), "status": "review", "started_at": "2026-11-13T15:00:00+00:00"} for n in (6, 7)]   # 2 Topstep noch in Überprüfen
out = K(konten, plaene, TAG, TZ, LO(lauf), set())
check(out == [kid(n) for n in range(1, 6)], f"16.11.: 5 abgehakte Konten wieder Kandidat, 2 in Überprüfen bleiben draußen ({len(out)})")
out2 = K(konten, plaene + [dict(ina, master_account_id=kid(1))], TAG, TZ, LO(lauf), set())
check(kid(1) not in out2, "Konto mit heute beendetem Trade bleibt draußen (ein Trade pro Konto und Tag)")
r = src[src.index("\ndef _ap_nachplan_rechnen("):src.index("\ndef ap_nachplan_tick(")]
check("ap_gruppe_lauf_ohne_erledigt(ap_nachplan_letzter(rows))" in r and "ap_gruppe_lauf_ohne_erledigt(ll)" in r,
      "_ap_nachplan_rechnen nimmt den Überprüfen-Grund weiter heraus (S18, unverändert)")
check(src.count('p.get("status") == "completed" and _ap_plan_am_tag(p, tag, tz)') >= 2,
      "ap_planen + Gruppen-Planer: „heute schon gehandelt“ über _ap_plan_am_tag (gleiche Regel)")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ NP1 alle Prüfungen grün")
