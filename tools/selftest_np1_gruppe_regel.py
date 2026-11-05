#!/usr/bin/env python3
"""Selbsttest NP1 (05.11.2026, Master: Emins FNF …6243 / Lucid …0002 blieben mit „keine Regel für diese Firma" bis morgen draußen, obwohl die Gruppe
Modell/Firma inzwischen eingeschaltet hatte). Im Gruppen-Nachplanen gilt eine Änderung an der Regel des Unternehmens als „Regel geändert":
Bezug = jüngster von auto_plan_regeln.updated_at, auto_plan_gruppe.regeln_at (falls Spalte) und dem Prozess-Merker der Schreibwege.
Ohne Netz. Aufruf: python3 tools/selftest_np1_gruppe_regel.py"""
import os
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        FEHLER.append(text)


B = app.ap_gruppe_regel_bezug
R, L, M = "2026-11-05T00:47:23.041024+00:00", "2026-11-05T02:06:14+00:00", "2026-11-05T02:30:00+00:00"
check(B(R, {}, None) == R and B(R, {"regeln_at": None}, None) == R, "ohne Gruppen-Änderung: Bezug = auto_plan_regeln.updated_at (bitgleich wie bisher)")
check(B(R, {}, M) == M, "Prozess-Merker (Modell geändert, Spalte fehlt) zählt")
check(B(R, {"regeln_at": M}, None) == M, "Spalte regeln_at zählt")
check(B(M, {"regeln_at": R}, None) == M, "der jüngste gewinnt")
check(B(R, {"regeln_at": "kaputt"}, None) == R and B(None, {}, None) is None, "unlesbare Werte fallen weg")
check(B("2026-11-05T02:30:00Z", {}, "2026-11-05T03:30:00+01:00") in ("2026-11-05T02:30:00Z", "2026-11-05T03:30:00+01:00"), "Zeitzonen werden als Zeit verglichen")

app._ap_gruppe_regel_at.clear()
app.ap_gruppe_regel_geaendert("g1", M)
app.ap_gruppe_regel_geaendert("g1", R)
check(app._ap_gruppe_regel_at.get("g1") == M, "Merker behält den jüngsten Zeitpunkt je Gruppe")

# Wirkung in ap_nachplan_kandidaten: „keine Regel"-Zeile eines Laufs um L; Bezug nach L → Konto wieder Kandidat, vorher fest
konten = [{"id": "k1", "user_id": "u1", "account_type": "challenge", "auto_planer": True}]
letzter = {"at": L, "tag": "2026-11-05", "ausgelassen": [{"konto_id": "k1", "grund": "keine Regel für diese Firma"}]}
tz = app._ap_tz(app.AP_TZ_TAG)
jetzt = datetime(2026, 11, 5, 3, 0, tzinfo=timezone.utc)
vorher = app.ap_nachplan_kandidaten(konten, [], "2026-11-05", tz, letzter, set(), regeln_at=B(R, {}, None), jetzt=jetzt)
nachher = app.ap_nachplan_kandidaten(konten, [], "2026-11-05", tz, letzter, set(), regeln_at=B(R, {}, M), jetzt=jetzt)
check(vorher == [] and nachher == ["k1"], f"„keine Regel“ fest ohne Änderung ({vorher}), nach Modell-Änderung neu gerechnet ({nachher})")

src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
i = src.index("\ndef ap_gruppen_nachplan_tick(")
np_ = src[i:src.index("\ndef ", i + 10)]
check("ua = ap_gruppe_regel_bezug(reg.get(\"updated_at\"), z, _ap_gruppe_regel_at.get(str(gid)))" in np_ and "return dict(reg, updated_at=ua)" in np_,
      "Gruppen-Nachplanen: Bezug auch ohne Abweichung (Modell/Firma an-aus in firmen_modell)")
check(src.count("ap_gruppe_regel_geaendert(gid, _j)") == 1 and src.count("ap_gruppe_regel_geaendert(gid, jetzt_iso)") == 2, "drei Schreibwege setzen den Merker (Modell, Firmenwerte, Startfenster)")
print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
