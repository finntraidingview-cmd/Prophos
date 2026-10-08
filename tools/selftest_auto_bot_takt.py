#!/usr/bin/env python3
"""Selbsttest BOT-TAKT RUND UM DIE UHR (app.py _ap_bot_tick, _ap_bot_hat_arbeit, _ap_bot_stand, 08.10.2026, Slave-Terminal 3 — Finn
über Master: „Der Bot soll quasi die ganze Zeit schauen — 24/7 laufen, wenn es geht").

Aufruf:  python3 tools/selftest_auto_bot_takt.py
Ohne Netz (Fake sb_select/ap_ausgleichen). Geprüft: Samstag 22:00 und Montag 20:00 dt laufen (früher Mo–Fr bis 19:30 gesperrt);
ohne geplante/laufende Trades nur die Vorab-Abfrage, kein ap_ausgleichen; nicht fällig vor dem Takt; Abfrage = open ODER planned ab
jetzt − 30 min, limit 1; Abfrage kaputt → Lauf trotzdem; Schalter aus → nichts; bot{}.naechster_lauf = letzter + Takt auch am Wochenende."""
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    a = sd.lade()
    BER = ZoneInfo("Europe/Berlin")
    abfragen, laeufe = [], []
    arbeit = {"rows": [{"id": "x"}], "fehler": False}

    def sb_select(table, params):
        if table == "auto_plan_regeln":
            return [{"regeln": {"ausgleich": {"aktiv": True, "takt_min": 10}}}]
        if table == "trade_plans":
            abfragen.append(dict(params))
            if arbeit["fehler"]:
                raise RuntimeError("weg")
            return arbeit["rows"]
        return []
    a["sb_select"] = sb_select
    a["ap_ausgleichen"] = lambda **k: laeufe.append(k) or {"tag": "t", "umplanungen": [], "richtungsschutz": {}}

    def neu():
        a["_ap_bot"].clear()
        abfragen.clear()
        laeufe.clear()

    neu()
    a["_ap_bot_tick"](datetime(2026, 10, 10, 22, 0, tzinfo=BER))          # Samstag 22:00
    check(len(laeufe) == 1, f"Samstag 22:00 dt mit geplanten Trades → Lauf ({len(laeufe)})")
    neu()
    a["_ap_bot_tick"](datetime(2026, 10, 12, 20, 0, tzinfo=BER))          # Montag 20:00 (früher nach AP_BOT_ENDE_MIN gesperrt)
    check(len(laeufe) == 1, "Montag 20:00 dt → Lauf (früher ab 19:30 Pause)")
    q = abfragen[0] if abfragen else {}
    check(q.get("limit") == "1" and q.get("or", "").startswith("(status.eq.open,and(status.eq.planned,start_um.gte.") and q.get("select") == "id",
          f"Vorab-Abfrage: open ODER planned ab jetzt − {a['AP_BOT_ARBEIT_VORLAUF_MIN']} min, limit 1 ({q})")
    a["_ap_bot_tick"](datetime(2026, 10, 12, 20, 3, tzinfo=BER))
    check(len(laeufe) == 1, "3 min später: Takt (10 min) nicht fällig → kein zweiter Lauf")
    neu()
    arbeit["rows"] = []
    a["_ap_bot_tick"](datetime(2026, 10, 11, 3, 0, tzinfo=BER))
    check(not laeufe and len(abfragen) == 1 and "kein Lauf nötig" in (a["_ap_bot"].get("letztes") or {}).get("msg", ""),
          "nichts geplant/laufend → nur die Vorab-Abfrage, kein Stand-Laden")
    neu()
    arbeit.update(rows=[], fehler=True)
    a["_ap_bot_tick"](datetime(2026, 10, 11, 3, 0, tzinfo=BER))
    check(len(laeufe) == 1, "Vorab-Abfrage kaputt → Lauf trotzdem")
    arbeit.update(rows=[{"id": "x"}], fehler=False)
    neu()
    a["sb_select"] = lambda t, p: [{"regeln": {"ausgleich": {"aktiv": False, "takt_min": 10}}}] if t == "auto_plan_regeln" else [{"id": "x"}]
    a["_ap_bot_tick"](datetime(2026, 10, 12, 10, 0, tzinfo=BER))
    check(not laeufe, "Schalter aus → kein Lauf")
    jetzt = datetime(2026, 10, 10, 20, 0, tzinfo=timezone.utc)                # Samstag
    a["_ap_bot"]["letzter_lauf"] = (jetzt - timedelta(minutes=4)).isoformat()
    st = a["_ap_bot_stand"]({"aktiv": True, "takt_min": 10}, jetzt)
    check(st["naechster_lauf"] == (jetzt + timedelta(minutes=6)).isoformat(), f"bot{{}}: nächster Lauf am Wochenende = letzter + Takt ({st['naechster_lauf']})")
    check(a["_ap_bot_stand"]({"aktiv": False, "takt_min": 10}, jetzt)["naechster_lauf"] is None, "bot{}: aus → kein nächster Lauf")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
