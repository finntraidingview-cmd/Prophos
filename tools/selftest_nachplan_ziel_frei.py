#!/usr/bin/env python3
"""Selbsttest NACHPLANEN NIMMT CFD-REST-KONTEN WIEDER AUF (app.py ap_nachplan_ziel_frei, ap_nachplan_kandidaten ziel_frei,
_ap_nachplan_rechnen, 09.10.2026 — Master, Folge zu .1397 Klein-Trade). Anlass: drei CFD-Konten (Rest 36/56/62 $) standen im Lauf vor dem
Update mit „nur noch X $ bis zum Ziel — von Hand prüfen" im Protokoll; „bis zum Ziel" ist ein fester Nachplan-Grund → erst morgen geplant.
Geprüft: (1) CFD phase1/phase2 mit Rest ≥ 10 $ → frei, Rest < 10 $ / Challenge / ohne typ / anderer Tag → fest; (2) Kandidaten mit ziel_frei;
(3) Takt: das Konto wird genau EINMAL je Tag neu gerechnet — kommt der Grund wieder (z. B. „kein Punktwert"), bleibt es danach fest.
Konten frei erfunden. Aufruf: python3 tools/selftest_nachplan_ziel_frei.py"""
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest_auto_nachplanen as np_  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    a = np_.lade()
    F, K = a["ap_nachplan_ziel_frei"], a["ap_nachplan_kandidaten"]
    tag, tz = "2026-10-09", ZoneInfo("Europe/Berlin")
    lauf = {"tag": tag, "at": "2026-10-08T22:54:32+00:00", "ausgelassen": [
        {"konto_id": "c-1", "typ": "phase1", "grund": "nur noch 36 $ bis zum Ziel — von Hand prüfen"},
        {"konto_id": "c-2", "typ": "phase1", "grund": "nur noch 56 $ bis zum Ziel — von Hand prüfen"},
        {"konto_id": "c-3", "typ": "phase2", "grund": "nur noch 62 $ bis zum Ziel — von Hand prüfen"},
        {"konto_id": "c-4", "typ": "phase1", "grund": "nur noch 5 $ bis zum Ziel — unter 10 $ plant der Bot keinen Klein-Trade: …"},
        {"konto_id": "c-5", "typ": "challenge", "grund": "nur noch 60 $ bis zum Ziel — von Hand prüfen"},
        {"konto_id": "c-6", "grund": "nur noch 70 $ bis zum Ziel — von Hand prüfen"},
        {"konto_id": "c-7", "typ": "phase1", "grund": "keine Regel für diese Firma"},
        {"konto_id": "c-8", "typ": "phase1", "grund": "Ziel erreicht — Phase umstellen"}]}

    # 1) welche Gründe frei werden
    frei = F(lauf, tag)
    check(frei == {"c-1", "c-2", "c-3"}, f"CFD Rest 36/56/62 frei; < 10 $, Challenge, ohne typ, andere Gründe fest ({sorted(frei)})")
    check(F(lauf, "2026-10-10") == set() and F(None, tag) == set(), "Lauf eines anderen Tags / kein Lauf → nichts frei")
    check(F(lauf, tag, {"c-1", "c-3"}) == {"c-2"}, "heute schon freigegebene Konten nicht noch einmal")

    # 2) Kandidaten
    konten = [{"id": f"c-{i}", "account_type": "challenge" if i == 5 else "phase1"} for i in range(1, 9)]
    ohne = K(konten, [], tag, tz, lauf, set())
    mit = K(konten, [], tag, tz, lauf, set(), ziel_frei=frei)
    check(ohne == [] and mit == ["c-1", "c-2", "c-3"], f"Kandidaten: ohne ziel_frei keiner, mit ziel_frei genau die drei ({ohne}, {mit})")
    belegt = K(konten, [{"master_account_id": "c-2", "status": "planned", "planned_for": tag}], tag, tz, lauf, set(), ziel_frei=frei)
    check(belegt == ["c-1", "c-3"], f"schon geplantes Konto bleibt draußen ({belegt})")

    # 3) Takt gegen eine nachgebaute DB: erster Takt rechnet c-1..c-3, der zweite (gleicher Grund wieder im Protokoll) nicht mehr
    reg = {"aktiv": True, "user_ids": [np_.U1], "zeiten": {"start_bis": "16:30"}, "updated_at": "2026-10-08 20:00:00+00"}
    rows = [{"tag": tag, "quelle": "nachplanen", "at": lauf["at"], "ergebnis": lauf}]
    aufrufe = []
    a["sb_select"] = lambda t, q: [dict(reg)] if t == "auto_plan_regeln" else (rows if t == "auto_plan_lauf" else [])
    a["_ap_konten_laden"] = lambda q: [dict(k, user_id=np_.U1) for k in konten]
    a["_sb_all"] = lambda t, q: []
    a["_ap_archiviert"] = lambda: set()

    def planen(t, quelle=None, nur_konten=None):
        aufrufe.append(sorted(nur_konten or []))
        # Rückgabe wie live, wenn der Punktwert fehlt: derselbe „bis zum Ziel"-Grund kommt wieder (keine neue Lauf-Zeile)
        return {"ok": True, "geplant": [], "ausgelassen": [dict(z) for z in lauf["ausgelassen"] if z["konto_id"] in (nur_konten or [])]}
    a["ap_planen"] = planen
    zst = {}
    jetzt = datetime(2026, 10, 8, 23, 40, tzinfo=timezone.utc)      # 01:40 dt, im Fenster
    T = a["ap_nachplan_tick"]
    T(jetzt, zst)
    zst["nachplan_at"] = 0
    T(jetzt + timedelta(minutes=10), zst)
    check(aufrufe == [["c-1", "c-2", "c-3"]], f"Takt: einmal nachrechnen, danach fest (kein 10-min-Kreisel) ({aufrufe})")
    check(zst.get("nachplan_ziel") == {tag: {"c-1", "c-2", "c-3"}}, f"Merker je Tag im Prozess-Speicher ({zst.get('nachplan_ziel')})")
    # neuer Handelstag: Merker des alten Tags fliegt raus
    zst["nachplan_at"] = 0
    rows[:] = []
    T(jetzt + timedelta(days=3), zst)                          # Mo 12.10. (Sa/So kein Fenster)
    check(set(zst.get("nachplan_ziel") or {}) <= {"2026-10-12"}, f"alter Tag fliegt aus dem Merker ({zst.get('nachplan_ziel')})")

    print(f"\n{'ALLES OK' if not FEHLER else f'{len(FEHLER)} FEHLER'}")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
