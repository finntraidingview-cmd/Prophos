#!/usr/bin/env python3
"""Selbsttest Nachtlauf-Uhrzeit des Auto-Planers (app.py, 07.10.2026: 01:00 Dubai statt 00:00 dt, mit Nachholen) — ohne Netz.

Aufruf:  python3 tools/selftest_auto_nachtlauf.py
Lädt die Funktionen per Quelltext aus app.py (app.py zieht beim Import Flask und Threads). sb_select/ap_planen sind
nachgebaut: ap_planen claimt wie das Original über den Unique-Index (zweiter Claim desselben Tags = „schon geplant").
Geprüft: Dubai ↔ dt im Sommer (CEST, 01:00 Dubai = 23:00 dt) und Winter (CET, = 22:00 dt), Zieltag Di aus Mo-Abend,
Wochenende, Parameter-Rückfall, Nachholen nach dem Deploy am 07.10.2026 genau einmal (auch mit zwei Instanzen + Neustart)."""
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "time": time, "datetime": datetime, "timezone": timezone, "timedelta": timedelta}

    def block(name):
        i = src.index(f"def {name}(")
        return src[i:src.find("\n\n\n", i)]

    def konst(name):
        return re.search(rf"^{name} = .*$", src, re.M).group(0)
    exec("\n".join([konst(k) for k in ("AP_TZ_TAG", "AP_NACHT_STANDARD")] + [block(f) for f in (
        "_ap_tz", "ap_nacht_param", "ap_nacht_lauf_um", "ap_nacht_ziel", "ap_nacht_tick", "ap_richtung_fest_plan")]), ns)
    return ns


FEHLER = []


def pruef(name, ist, soll):
    ok = ist == soll
    print(("✅" if ok else "❌"), name, "" if ok else f"→ ist {ist!r}, soll {soll!r}")
    if not ok:
        FEHLER.append(name)


def utc(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def main():
    ns = lade()
    std = ns["ap_nacht_param"]({})
    pruef("Standard ohne Parameter", std, {"uhr": "01:00", "tz": "Asia/Dubai"})
    pruef("Rückfall bei Unsinn", ns["ap_nacht_param"]({"nachtlauf": {"uhr": "25:00", "tz": "Mars/Olymp"}}), std)
    pruef("eigener Parameter", ns["ap_nacht_param"]({"nachtlauf": {"uhr": "0:30", "tz": "Europe/Berlin"}}),
          {"uhr": "00:30", "tz": "Europe/Berlin"})

    lauf_um = ns["ap_nacht_lauf_um"]
    # Sommer (CEST = UTC+2): Mi 07.10.2026 → Lauf Mi 01:00 Dubai = Di 21:00 UTC = Di 23:00 dt
    pruef("Sommer Mi 07.10. → 06.10. 21:00 UTC", lauf_um(date(2026, 10, 7), std), utc("2026-10-06T21:00"))
    dt = lauf_um(date(2026, 10, 7), std).astimezone(ns["_ap_tz"]("Europe/Berlin"))
    pruef("Sommer = 23:00 dt am Vorabend", (dt.date().isoformat(), dt.strftime("%H:%M")), ("2026-10-06", "23:00"))
    # Winter (CET = UTC+1, ab 25.10.2026): Mi 04.11.2026 → Mi 01:00 Dubai = Di 21:00 UTC = Di 22:00 dt
    dt = lauf_um(date(2026, 11, 4), std).astimezone(ns["_ap_tz"]("Europe/Berlin"))
    pruef("Winter = 22:00 dt am Vorabend", (dt.date().isoformat(), dt.strftime("%H:%M")), ("2026-11-03", "22:00"))
    # Umstellungstag: Mo 26.10.2026 (Umstellung So 25.10. 03:00→02:00) → Mo 01:00 Dubai = So 21:00 UTC = So 22:00 CET
    pruef("Umstellung Mo 26.10.", lauf_um(date(2026, 10, 26), std), utc("2026-10-25T21:00"))
    pruef("Umstellung Frühjahr Mo 30.03.2026", lauf_um(date(2026, 3, 30), std), utc("2026-03-29T21:00"))
    # 00:00 dt als Parameter = der Tagesbeginn selbst (altes Verhalten nachstellbar)
    pruef("00:00 Europe/Berlin = Tagesbeginn", lauf_um(date(2026, 10, 7), {"uhr": "00:00", "tz": "Europe/Berlin"}),
          utc("2026-10-06T22:00"))

    ziel = ns["ap_nacht_ziel"]
    # Di 01:00 Dubai (= Mo 23:00 dt) → Dienstag
    f, _ = ziel(utc("2026-10-05T21:00"), std)
    pruef("Di 01:00 Dubai plant Dienstag", f[0].isoformat() if f else None, "2026-10-06")
    f, n = ziel(utc("2026-10-05T20:59"), std)
    pruef("eine Minute vorher: Montag noch offen (läuft bis 00:00 dt)", f[0].isoformat() if f else None, "2026-10-05")
    pruef("… nächster Lauf = Dienstag", (n[0].isoformat(), n[1]), ("2026-10-06", utc("2026-10-05T21:00")))
    f, n = ziel(utc("2026-10-10T10:00"), std)
    pruef("Samstag: nichts fällig", f, None)
    pruef("Samstag: nächster = Montag (So 23:00 dt)", (n[0].isoformat(), n[1]), ("2026-10-12", utc("2026-10-11T21:00")))
    f, _ = ziel(utc("2026-10-08T21:00"), std)
    pruef("Fr 01:00 Dubai plant Freitag", f[0].isoformat() if f else None, "2026-10-09")
    f, _ = ziel(utc("2026-10-07T03:00"), std)
    pruef("Mi 05:00 dt verpasst → Mittwoch nachholen", f[0].isoformat() if f else None, "2026-10-07")

    # ── Nachholen nach dem Deploy (07.10.2026 ca. 01:15 Dubai = 06.10. 21:15 UTC): genau EIN Lauf für Mi 07.10.
    claims, laeufe = set(), []
    regeln = {"aktiv": True, "zeiten": {"tz": "Europe/Berlin"}}

    def sb_select(tabelle, params):
        return [dict(regeln)]

    def ap_planen(tag, quelle="hand"):
        if quelle == "nacht":
            if tag in claims:
                return {"ok": True, "tag": tag, "msg": "schon geplant (anderer Lauf)"}
            claims.add(tag)
        laeufe.append(tag)
        return {"ok": True, "tag": tag, "geplant": [1, 2]}
    ns["sb_select"], ns["ap_planen"] = sb_select, ap_planen
    tick = ns["ap_nacht_tick"]
    a, b = {}, {}                               # zwei Railway-Instanzen
    t0 = utc("2026-10-06T21:15")
    for i in range(30):                         # 30 Takte je Instanz, Minute für Minute
        tick(t0 + timedelta(minutes=i), a)
        tick(t0 + timedelta(minutes=i), b)
    pruef("Deploy 01:15 Dubai: Mi 07.10. genau einmal geplant", laeufe, ["2026-10-07"])
    neu = {}                                    # Neustart mitten in der Nacht: Speicher leer, Claim in der DB
    tick(utc("2026-10-06T23:40"), neu)
    pruef("Neustart danach: kein zweiter Lauf", laeufe, ["2026-10-07"])
    tick(utc("2026-10-07T21:00"), a)
    pruef("Do 01:00 Dubai: Donnerstag einmal", laeufe, ["2026-10-07", "2026-10-08"])
    tick(utc("2026-10-07T21:01"), a)
    pruef("… und nicht noch einmal", laeufe, ["2026-10-07", "2026-10-08"])
    pruef("Info: nächster Lauf Fr", a["nachtlauf"]["naechster_tag"], "2026-10-09")

    regeln["aktiv"] = False
    c = {}
    tick(utc("2026-10-08T21:05"), c)
    pruef("aktiv aus: nichts geplant", laeufe, ["2026-10-07", "2026-10-08"])
    regeln["aktiv"] = True
    tick(utc("2026-10-08T21:06"), c)
    pruef("aktiv aus → an im selben Prozess: erst nach Neustart", laeufe, ["2026-10-07", "2026-10-08"])
    tick(utc("2026-10-08T21:07"), {})
    pruef("nach Neustart mit aktiv: Freitag nachgeholt", laeufe, ["2026-10-07", "2026-10-08", "2026-10-09"])

    # ── Richtungsschutz nur gleichzeitig (Finn 07.10.2026): laufend / am selben Tag geplant = fest, sonst frei
    fest = ns["ap_richtung_fest_plan"]
    tz = ns["_ap_tz"]("Europe/Berlin")
    pruef("läuft (open) → fest", fest({"status": "open", "richtung": "buy"}, "2026-10-07", tz), True)
    pruef("beendet (review/completed) → frei", [fest({"status": s, "richtung": "buy"}, "2026-10-07", tz) for s in ("review", "completed")],
          [False, False])
    pruef("geplant heute 10:00 dt → fest", fest({"status": "planned", "richtung": "sell", "start_um": "2026-10-07T08:00:00+00:00"},
                                               "2026-10-07", tz), True)
    pruef("geplant 23:30 dt Vortag (21:30 UTC) → anderer Tag, frei",
          fest({"status": "planned", "richtung": "sell", "start_um": "2026-10-06T21:30:00+00:00"}, "2026-10-07", tz), False)
    pruef("geplant 00:30 dt (06.10. 22:30 UTC) → heute, fest",
          fest({"status": "planned", "richtung": "sell", "start_um": "2026-10-06T22:30:00+00:00"}, "2026-10-07", tz), True)
    pruef("geplant morgen (planned_for) → frei", fest({"status": "planned", "richtung": "buy", "planned_for": "2026-10-08"},
                                                     "2026-10-07", tz), False)
    pruef("geplant ohne Tag/Start → vorsichtshalber fest", fest({"status": "planned", "richtung": "buy"}, "2026-10-07", tz), True)
    pruef("ohne Richtung → nie fest", fest({"status": "open", "richtung": None}, "2026-10-07", tz), False)

    print()
    if FEHLER:
        print(f"❌ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✅ alles grün")


if __name__ == "__main__":
    main()
