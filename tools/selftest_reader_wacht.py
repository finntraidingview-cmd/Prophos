#!/usr/bin/env python3
"""Selbsttest fuer den Reader-Wachhund (app.py, READER-WACHT, 25.09.2026) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_reader_wacht.py
Laedt die Funktionen per Quelltext aus app.py (wie selftest_wd_heute: app.py zieht beim Import
Flask, Threads und Umgebungsvariablen). Prueft: CME-Marktzeit (Sonntag-Oeffnung, Tagespause,
Freitag-Schluss, Samstag, Sommer-/Winterzeit), Deckel „seit Oeffnung", Frisch-Regel (delayed/stale)
und die Zustandsmaschine (Beginn ab 120 s, Erinnerung 10 min / dann 30 min, Ende mit Dauer,
Marktschluss beendet still, Kerzen-Aussetzer einmal je Vorfall)."""
import os
import re
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone}

    def block(name):
        i = src.index(f"def {name}(")
        j = src.find("\n\n\n", i)
        return src[i:j]

    def const(name):
        return re.search(rf"^{name} = .*$", src, re.M).group(0)

    code = "\n".join([const(c) for c in ("READER_WACHT_SCHWELLE_S", "READER_WACHT_KERZEN_S",
                                         "READER_WACHT_ERINNERUNG_1_S", "READER_WACHT_ERINNERUNG_N_S",
                                         "READER_WACHT_TZ", "READER_WACHT_KERZEN_HAUPT")]
                     + [block(f) for f in ("cme_markt_offen", "_cme_offen_seit_s", "_rw_uhr", "_rw_kurs_text",
                                           "reader_wacht_schritt", "_rw_frisch")])
    exec(code, ns)
    return ns


def utc(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    offen, seit = a["cme_markt_offen"], a["_cme_offen_seit_s"]
    # Sommerzeit (CDT = UTC−5): So 27.09.2026, Mo 28.09., Fr 25.09., Sa 26.09.
    check(not offen(utc("2026-09-27T21:59:00")) and offen(utc("2026-09-27T22:00:00")),
          "Sonntag 16:59 CT zu, 17:00 CT offen")
    check(seit(utc("2026-09-27T22:00:00")) == 0.0 and seit(utc("2026-09-28T15:00:00")) == 17 * 3600,
          "seit Oeffnung: So 17:00 CT = 0 s, Mo 10:00 CT = 17 h")
    check(offen(utc("2026-09-28T20:59:00")) and not offen(utc("2026-09-28T21:00:00"))
          and not offen(utc("2026-09-28T21:30:00")) and offen(utc("2026-09-28T22:00:00")),
          "Montag 15:59 offen, 16:00 zu, 16:30 zu (Tagespause), 17:00 offen")
    check(seit(utc("2026-09-28T22:00:30")) == 30.0, "nach der Tagespause zaehlt die Oeffnung 17:00 CT neu")
    check(offen(utc("2026-09-25T20:59:00")) and not offen(utc("2026-09-25T21:00:00"))
          and not offen(utc("2026-09-25T23:00:00")), "Freitag 15:59 offen, ab 16:00 CT zu (auch 18:00)")
    check(not offen(utc("2026-09-26T12:00:00")) and not offen(utc("2026-09-26T23:30:00")), "Samstag zu")
    # Winterzeit (CST = UTC−6): Mo 07.12.2026
    check(offen(utc("2026-12-07T21:30:00")) and offen(utc("2026-12-07T21:59:00"))
          and not offen(utc("2026-12-07T22:00:00")) and offen(utc("2026-12-07T23:00:00")),
          "Winterzeit: 21:30 UTC offen (15:30 CST), 22:00 UTC zu, 23:00 UTC offen")
    check(not offen(utc("2026-12-06T22:59:00")) and offen(utc("2026-12-06T23:00:00")),
          "Winterzeit: Sonntag-Oeffnung 23:00 UTC")
    check(offen(int(utc("2026-09-28T15:00:00").timestamp())), "Unix-Sekunden werden angenommen")

    fr = a["_rw_frisch"]
    check(fr({"stale": False, "preis": 30000, "modus": "streaming"}) and fr({"stale": False, "preis": 1, "modus": None}),
          "frisch: streaming bzw. ohne modus, stale false, Kurs da")
    check(not fr({"stale": False, "preis": 30000, "modus": "delayed_streaming_600"})
          and not fr({"stale": True, "preis": 30000, "modus": "streaming"})
          and not fr({"stale": False, "preis": None, "modus": "streaming"}),
          "nicht frisch: delayed_*, stale true, ohne Kurs")

    s = a["reader_wacht_schritt"]
    T = utc("2026-09-28T15:00:00").timestamp()       # Mo 10:00 CT, Markt offen seit 17 h
    SO = 17 * 3600
    leer = {"feed": None, "kerzen": None}
    kw = dict(seit_offen_s=SO, letzter_kurs=30448.25, kurs_wurzel="NQ", pc="pc-usq1i6")

    z, ev = s(leer, T, 119, True, **kw)
    check(ev == [] and z["feed"] is None, "119 s alt → keine Meldung")
    z, ev = s(leer, T, 121, True, **kw)
    check(len(ev) == 1 and ev[0]["art"] == "feed_beginn" and ev[0]["push"] and ev[0]["renotify"]
          and "seit 2 min" in ev[0]["titel"] and "NQ 30448.25" in ev[0]["text"] and "pc-usq1i6" in ev[0]["text"]
          and abs(z["feed"]["von"] - (T - 121)) < 1e-6,
          "121 s alt → EINE Meldung „Kurs-Feed steht seit 2 min“ mit Kurs + PC, von = letzter frischer Kurs")
    # 14:57:59 UTC = 18:57 Dubai (UTC+4)
    check("18:57" in ev[0]["text"] and "Dubai" in ev[0]["text"], "Uhrzeit in Dubai-Zeit (14:57:59 UTC → 18:57)")
    b = T
    z1, ev = s(z, b + 30, 151, True, **kw)
    check(ev == [], "30 s spaeter: keine zweite Meldung")
    z1, ev = s(z1, b + 599, 720, True, **kw)
    check(ev == [], "nach 9:59 min: noch keine Erinnerung")
    z1, ev = s(z1, b + 600, 721, True, **kw)
    check(len(ev) == 1 and ev[0]["art"] == "feed_erinnerung" and ev[0]["push"] and z1["feed"]["gemeldet"] == 2,
          "nach 10 min: Erinnerung")
    z1, ev = s(z1, b + 600 + 1799, 2520, True, **kw)
    check(ev == [], "Erinnerung + 29:59 min: nichts")
    z1, ev = s(z1, b + 2400, 2521, True, **kw)
    check(len(ev) == 1 and ev[0]["art"] == "feed_erinnerung" and z1["feed"]["gemeldet"] == 3, "dann alle 30 min")
    z1, ev = s(z1, b + 4200, 4321, True, **kw)
    check(len(ev) == 1 and z1["feed"]["gemeldet"] == 4, "… und wieder 30 min spaeter")
    z2, ev = s(z1, b + 4230, 3, True, **kw)
    check(len(ev) == 1 and ev[0]["art"] == "feed_ende" and ev[0]["push"] and ev[0]["renotify"]
          and ev[0]["dauer_s"] == 4230 + 121 and "(73 min)" in ev[0]["titel"]
          and ev[0]["titel"].startswith("Reader wieder da — Ausfall von 18:57 bis 20:10") and z2["feed"] is None,
          "Feed zurueck → EINE Meldung „Reader wieder da — Ausfall von HH:MM bis HH:MM (n min)“")
    z3, ev = s(z2, b + 4260, 3, True, **kw)
    check(ev == [], "danach Ruhe")

    zz, ev = s(z, b + 60, None, False, seit_offen_s=None)
    check(len(ev) == 1 and ev[0]["art"] == "feed_still" and not ev[0]["push"] and zz["feed"] is None,
          "Marktschluss beendet einen laufenden Ausfall still (nur Protokoll)")
    zz, ev = s(leer, b, None, False, seit_offen_s=None)
    check(ev == [] and zz["feed"] is None, "Markt zu, keine frische Zeile → kein Alarm")

    zd, ev = s(leer, T, None, True, **kw)
    check(len(ev) == 1 and ev[0]["art"] == "feed_beginn", "nur delayed/stale-Zeilen (feed_alter None) → Ausfall")
    zo, ev = s(leer, T, 3600, True, **{**kw, "seit_offen_s": 30})
    check(ev == [], "30 s nach der Oeffnung: letzte frische Zeile 1 h alt ist KEIN Ausfall (Deckel)")
    zo, ev = s(leer, T, 3600, True, **{**kw, "seit_offen_s": 125})
    check(len(ev) == 1 and ev[0]["art"] == "feed_beginn", "… aber 125 s nach der Oeffnung ohne frischen Kurs schon")

    zk, ev = s(leer, T, 10, True, kerzen_alter_s=200, kerzen_wurzel="MNQ", **kw)
    check(len(ev) == 1 and ev[0]["art"] == "kerzen_beginn" and ev[0]["push"] and "Kerzen fehlen seit" in ev[0]["titel"]
          and "MNQ" in ev[0]["text"], "Feed frisch, jüngste Kerze 200 s alt → „Reader: Kerzen fehlen seit …“")
    zk2, ev = s(zk, T + 30, 10, True, kerzen_alter_s=230, kerzen_wurzel="MNQ", **kw)
    check(ev == [] and zk2["kerzen"], "Kerzen-Vorfall nur einmal gemeldet")
    zk3, ev = s(zk2, T + 60, 10, True, kerzen_alter_s=30, kerzen_wurzel="MNQ", **kw)
    check(len(ev) == 1 and ev[0]["art"] == "kerzen_ende" and not ev[0]["push"] and zk3["kerzen"] is None,
          "Kerzen wieder da → Vorfall still geschlossen")
    _, ev = s(leer, T, 10, True, kerzen_alter_s=170, **kw)
    check(ev == [], "Kerze 170 s alt → kein Aussetzer")
    _, ev = s(leer, T, 10, True, kerzen_alter_s=None, **kw)
    check(ev == [], "Kerzen unbekannt (Abfrage gescheitert) → keine Aussage")
    zf, ev = s(zk, T + 30, 300, True, kerzen_alter_s=None, **kw)
    check([e["art"] for e in ev] == ["kerzen_still", "feed_beginn"] and zf["kerzen"] is None and zf["feed"],
          "Feed-Ausfall schliesst den Kerzen-Vorfall still und meldet den Ausfall")

    zr, ev = s(z1, b + 4230, 3, True, kerzen_alter_s=4000, kerzen_wurzel="NQ", **kw)
    check([e["art"] for e in ev] == ["feed_ende"], "direkt nach „wieder da“ kein Kerzen-Alarm (Reader fuellt nach)")
    zr, ev = s(zr, b + 4230 + 180, 3, True, kerzen_alter_s=4180, kerzen_wurzel="NQ", **kw)
    check(ev == [], "… auch 3 min danach noch nicht")
    zr, ev = s(zr, b + 4230 + 210, 3, True, kerzen_alter_s=4210, kerzen_wurzel="NQ", **kw)
    check([e["art"] for e in ev] == ["kerzen_beginn"], "… fehlen sie 3:30 min nach der Rueckkehr noch → Meldung")

    # Kerzen je Wurzel (25.09.2026): laut nur MNQ, NQ-only leise — der Fall von heute (Chart 11:44 auf MNQ1! gewechselt)
    check(a["READER_WACHT_KERZEN_HAUPT"] == "MNQ", "Hauptwurzel MNQ")
    zn, ev = s(leer, T, 3, True, kerzen_je={"MNQ": 40, "NQ": 1200}, **kw)
    check([e["art"] for e in ev] == ["kerzen_leise_beginn"] and not ev[0]["push"] and "NQ-Kerzen" in ev[0]["titel"]
          and zn["kerzen"] is None and zn["kerzen_leise"]["wurzel"] == "NQ",
          "nur NQ ohne Kerzen, MNQ laeuft → leiser Hinweis, kein Push")
    zn2, ev = s(zn, T + 30, 3, True, kerzen_je={"MNQ": 10, "NQ": 1230}, **kw)
    check(ev == [] and zn2["kerzen_leise"], "leiser Hinweis nur einmal")
    zn3, ev = s(zn2, T + 60, 3, True, kerzen_je={"MNQ": 20, "NQ": 30}, **kw)
    check([e["art"] for e in ev] == ["kerzen_leise_ende"] and not ev[0]["push"] and zn3["kerzen_leise"] is None,
          "NQ-Kerzen wieder da → leises Ende")
    zm, ev = s(leer, T, 3, True, kerzen_je={"MNQ": 4600, "NQ": 30}, **kw)
    check([e["art"] for e in ev] == ["kerzen_beginn"] and ev[0]["push"] and "MNQ-Kerzen fehlen" in ev[0]["titel"]
          and zm["kerzen"]["wurzel"] == "MNQ", "MNQ ohne Kerzen (10:25–11:43) → laut mit Wurzel im Titel")
    zb, ev = s(leer, T, 3, True, kerzen_je={"MNQ": 400, "NQ": 500}, **kw)
    check(sorted(e["art"] for e in ev) == ["kerzen_beginn", "kerzen_leise_beginn"]
          and [e["push"] for e in ev if e["art"] == "kerzen_beginn"] == [True], "beide fehlen → MNQ laut + NQ leise")
    zo2, ev = s(leer, T, 3, True, kerzen_je={"NQ": 500}, **kw)
    check([e["art"] for e in ev] == ["kerzen_beginn"] and ev[0]["push"], "MNQ tickt gar nicht → schlechteste Wurzel laut wie bisher")
    zf2, ev = s(zb, T + 30, 300, True, kerzen_je=None, **kw)
    check(sorted(e["art"] for e in ev) == ["feed_beginn", "kerzen_leise_still", "kerzen_still"] and zf2["kerzen_leise"] is None,
          "Feed-Ausfall schliesst beide Kerzen-Vorfaelle still")
    zc, ev = s(zb, T + 30, 3, False, kerzen_je={"MNQ": 400, "NQ": 500}, **kw)
    check(sorted(e["art"] for e in ev) == ["kerzen_leise_still", "kerzen_still"], "Marktschluss schliesst beide still")

    print("\nALLES GRUEN" if ok else "\nFEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
