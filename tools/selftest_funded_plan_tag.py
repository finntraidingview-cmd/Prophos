#!/usr/bin/env python3
"""Selbsttest PLANUNGSTAG DER FUNDED-PLANER = TAG DES NACHTLAUFS (app.py fd_plan_tag, Vorfall 03.11.2026 ~02:30 Dubai: Nachtlauf 1105 um 21:30 UTC plante den
03.11., Funded-Lauf 1119 um 22:11 UTC rechnete mit dem 02.11. → „heute schon getradet“ / Tagesdeckel für Chris und Ina).

Aufruf:  python3 tools/selftest_funded_plan_tag.py
Ohne Netz: fd_plan_tag mit den echten Nachtlauf-Funktionen (ap_nacht_param, ap_nacht_lauf_um, ap_nacht_ziel) und _cme_handelstag; beide Planer rufen ihn auf."""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        FEHLER.append(text)


def block(name):
    i = SRC.index(f"\ndef {name}(") + 1
    return SRC[i:SRC.find("\n\n\n", i)]


ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta}
konst = [re.search(rf"^{k} = .*$", SRC, re.M).group(0) for k in ("AP_NACHT_STANDARD", "AP_TZ_TAG")]
exec("\n".join(konst) + "\n" + "\n\n".join(block(n) for n in ("_ap_tz", "_cme_handelstag", "ap_nacht_param", "ap_nacht_lauf_um", "ap_nacht_ziel", "fd_plan_tag", "fd_fenster_basis")), ns)
T, CME = ns["fd_plan_tag"], ns["_cme_handelstag"]
u = lambda s: datetime.fromisoformat(s).replace(tzinfo=timezone.utc)   # noqa: E731

# Vorfall: 22:11 UTC (02:11 Dubai 03.11.), Fensterbeginn 02:26 Dubai = 22:26 UTC → CME-Tag noch 02.11.
fenster = CME("2026-11-02T22:26:00Z")
check(fenster == "2026-11-02", f"Ausgangslage: CME-Tag des Fensterbeginns 02.11. ({fenster})")
check(T(u("2026-11-02T22:11:00"), fenster, {}) == "2026-11-03", "Lauf 1119 (22:11 UTC): Planungstag 03.11. wie der Nachtlauf 1105")
check(T(u("2026-11-02T21:30:00"), CME("2026-11-02T21:45:00Z"), {}) == "2026-11-03", "direkt nach dem Nachtlauf (21:30 UTC): 03.11.")
check(T(u("2026-11-02T20:30:00"), CME("2026-11-02T20:45:00Z"), {}) == "2026-11-02", "vor dem Nachtlauf (00:30 Dubai): weiter 02.11.")
check(T(u("2026-11-03T10:00:00"), CME("2026-11-03T10:15:00Z"), {}) == "2026-11-03", "tagsüber: CME-Tag = Nachtlauf-Tag")
check(T(u("2026-11-06T22:00:00"), CME("2026-11-06T22:15:00Z"), {}) == "2026-11-06", "Freitagabend: kein Lauf für Samstag, bleibt 06.11.")
check(T(u("2026-11-08T21:30:00"), CME("2026-11-08T21:45:00Z"), {}) == "2026-11-09", "Sonntagabend nach dem Lauf für Montag: 09.11.")
check(T(u("2026-11-02T22:11:00"), fenster, {"nachtlauf": {"uhr": "03:00", "tz": "Asia/Dubai"}}) == "2026-11-02", "Nachtlauf-Uhr aus den Regeln (03:00 Dubai): vorher noch 02.11.")
check(T(u("2026-11-02T22:11:00"), "2026-11-04", {}) == "2026-11-04", "nie hinter den CME-Tag zurück (max)")
check(T(u("2026-11-02T22:11:00"), fenster, "kaputt") == "2026-11-03", "kaputte zeiten → Standard-Nachtlauf")

# Funded-CFD-Lauf 1124 (02:26 Dubai, Fenster in Dubai-Zeit): Tag 03.11., Slots ab 03:00 Dubai erlaubt (im_tag), Fenster nicht verschoben
FB = ns["fd_fenster_basis"]
dub, ber = ns["_ap_tz"]("Asia/Dubai"), ns["_ap_tz"]("Europe/Berlin")
jetzt = u("2026-11-02T22:26:00")
mn = jetzt.astimezone(dub).replace(hour=0, minute=0, second=0, microsecond=0)
tag = T(jetzt, CME((mn + timedelta(minutes=161)).astimezone(timezone.utc).isoformat()), {})
m2, ab2 = FB(mn, 161.0, 120, tag, dub)
check(tag == "2026-11-03" and m2 == mn and ab2 == 161.0, "Lauf 1124 (Dubai-Fenster): Tag 03.11., Fenster ab jetzt wie bisher")
slot = CME((m2 + timedelta(minutes=600)).astimezone(timezone.utc).isoformat())
check(slot == "2026-11-03" and CME((m2 + timedelta(minutes=170)).astimezone(timezone.utc).isoformat()) == "2026-11-02",
      "Slot 10:00 Dubai zählt zum 03.11. (vorher alle verworfen → „kein freier Slot“), 02:50 Dubai bleibt gesperrt (CME-Grenze)")
# Fenster in deutscher Zeit: Nachtlauf 23:00 dt plant den 03.11., lokal ist noch der 02.11. → Fenster ab 03.11. 00:00 dt + von
mb = jetzt.astimezone(ber).replace(hour=0, minute=0, second=0, microsecond=0)
m3, ab3 = FB(mb, 1420.0, 60, "2026-11-03", ber)
check(m3.date().isoformat() == "2026-11-03" and ab3 == 60.0, f"Fenster in dt: Basis 03.11. 00:00, ab Fensterbeginn ({m3}, {ab3})")
check(FB(mb, 1420.0, 60, "kaputt", ber) == (mb, 1420.0), "ungültiger Tag → unverändert")
check(SRC.count("= fd_fenster_basis(mitternacht, ab_min, von_min,") == 2, "beide Planer verschieben das Fenster")

# beide Planer nutzen ihn, die Startzeit-Grenze (im_tag) bleibt am CME-Tag
check("cme_heute = fd_plan_tag(jetzt, _cme_handelstag(" in SRC and "plan_tag = fd_plan_tag(jetzt, _cme_handelstag(" in SRC, "fdp_planen und fcp_planen rufen fd_plan_tag")
check("im_tag = lambda m: _cme_handelstag(" in SRC, "Startzeiten weiter nur im CME-Tag (03:00 Dubai im Winter)")
check(SRC.count("def ap_nacht_ziel(") == 1, "keine zweite Tagesfunktion")

print("\nselftest_funded_plan_tag: " + ("alle Prüfungen grün" if not FEHLER else f"{len(FEHLER)} FEHLER: {FEHLER}"))
sys.exit(1 if FEHLER else 0)
