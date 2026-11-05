#!/usr/bin/env python3
"""Selbsttest ZU1 (05.11.2026, Befund RT1/S5): ap_klasse_bis / ap_start_bis rechnen das Fensterende für den PLAN-TAG statt für heute.
Futures-Ende zeiten.start_bis = 20:00 Dubai (fenster_tz), CFD-Ende cfd_bis = 18:00 Dubai — in deutsche Minuten des Plan-Tags umgerechnet.
Vorher nahm ap_start_bis immer das heutige Datum: plante der Nachtlauf in der Umstellungsnacht den Folgetag, war das Futures-Ende 1 h falsch.
Geprüft:
  1 echte Umstellungen (EU): 25.10.2026 Sommer→Winter, 28.03.2027 Winter→Sommer — Ende je Plan-Tag, unabhängig vom heutigen Datum
  2 NY-Umstellung 01.11.2026 ändert nichts (Dubai→DE kennt nur die EU-Umstellung)
  3 jeder normale Tag (2026-01-01 … 2027-12-31, Futures + CFD, mit/ohne fenster_tz): NEU(plan_tag) == BASIS am Plan-Tag selbst (bitgleich)
  4 ohne heute: wie bisher heute; HT und Emin teilen dieselbe Rechnung (keine Abhängigkeit vom Unternehmen)
Ohne Netz. Aufruf: python3 tools/selftest_zu1_fensterende_plantag.py [basis-commit, Standard: cfe1c129 = main vor ZU1]"""
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
BASIS = sys.argv[1] if len(sys.argv) > 1 else "cfe1c129"   # main-Commit vor ZU1
FEHLER = []
NAMEN = ("_ap_hhmm", "_ap_tz", "ap_zeit_dt_min", "ap_cfd_bis", "ap_start_bis", "ap_klasse_bis")


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        FEHLER.append(text)


def lade(src, heute_fest=None):
    """Funktionen aus src; heute_fest = Datum, das datetime.now() liefert (für die BASIS „heute = Plan-Tag")."""
    class _DT(datetime):
        @classmethod
        def now(cls, tz=None):
            d = heute_fest or date.today()
            return datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc).astimezone(tz) if tz else datetime(d.year, d.month, d.day, 12, 0)
    ns = {"re": re, "datetime": _DT, "timezone": timezone, "timedelta": timedelta, "ZoneInfo": ZoneInfo, "_ap_tz_cache": {},
          "AP_TZ_TAG": "Europe/Berlin", "AP_START_BIS_STANDARD": "16:30", "AP_CFD_ROUTEN": ("mt5v2", "mt5")}
    for n in ("AP_TZ_TAG", "AP_START_BIS_STANDARD", "AP_CFD_ROUTEN"):
        m = re.search(rf"^{n} = .*$", src, re.M)
        if m:
            exec(m.group(0), ns)
    teile = []
    for n in NAMEN:
        i = src.index(f"\ndef {n}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def main():
    neu_src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
    alt_src = subprocess.run(["git", "-C", WURZEL, "show", f"{BASIS}:app.py"], capture_output=True, text=True).stdout
    if not alt_src:
        check(False, f"Basis {BASIS}:app.py nicht lesbar")
        return 1
    Z = {"fenster_tz": "Asia/Dubai", "start_bis": "20:00", "cfd_bis": {"tz": "Asia/Dubai", "uhr": "18:00"}}
    Z_ohne = {"start_bis": "16:30", "cfd_bis": "15:00"}

    # 1 echte Umstellungen — „heute" absichtlich auf der anderen Seite der Umstellung
    for heute, plan, fut, cfd, txt in ((date(2026, 10, 24), date(2026, 10, 26), 17 * 60, 15 * 60, "Sommer → Winter 25.10.2026"),
                                       (date(2026, 10, 26), date(2026, 10, 24), 18 * 60, 16 * 60, "Winter → zurück (Plan vor der Umstellung)"),
                                       (date(2027, 3, 27), date(2027, 3, 29), 18 * 60, 16 * 60, "Winter → Sommer 28.03.2027"),
                                       (date(2027, 3, 29), date(2027, 3, 27), 17 * 60, 15 * 60, "Sommer → zurück (Plan vor der Umstellung)")):
        n = lade(neu_src, heute)
        a = lade(alt_src, heute)
        nf, nc = n["ap_klasse_bis"](Z, "tvv2", plan), n["ap_klasse_bis"](Z, "mt5v2", plan)
        af = a["ap_klasse_bis"](Z, "tvv2", plan)
        check(nf == fut and nc == cfd, f"1 {txt}: heute {heute:%d.%m.}, Plan {plan:%d.%m.} → Futures {nf // 60}:{nf % 60:02d}, CFD {nc // 60}:{nc % 60:02d} dt")
        check(af != fut, f"1 … vorher falsch: BASIS gab Futures {af // 60}:{af % 60:02d} (Lücke belegt)")
    n = lade(neu_src, date(2026, 10, 24))
    check(n["ap_klasse_bis"](Z, "tvv2", date(2026, 10, 25)) == 17 * 60 and n["ap_klasse_bis"](Z, "tvv2", date(2027, 3, 28)) == 18 * 60,
          "1 Umstellungstag selbst: 25.10. = 17:00 dt (Winter ab 01:00 UTC), 28.03. = 18:00 dt")

    # 2 NY-Umstellung (01.11.2026) — Dubai → DE unverändert
    n = lade(neu_src, date(2026, 10, 31))
    check(n["ap_klasse_bis"](Z, "tvv2", date(2026, 11, 2)) == 17 * 60 == n["ap_klasse_bis"](Z, "tvv2", date(2026, 10, 31)),
          "2 NY-Umstellung 01.11.2026: Futures-Ende bleibt 17:00 dt")

    # 3 jeder Tag 2026–2027: NEU(plan_tag) == BASIS am Plan-Tag selbst
    abw = []
    n = lade(neu_src, date(2026, 6, 15))           # „heute" fest irgendwo anders — darf keine Rolle spielen
    d = date(2026, 1, 1)
    while d <= date(2027, 12, 31):
        a = lade(alt_src, d)
        for z in (Z, Z_ohne):
            for r in ("tvv2", "mt5v2", "tsv2", "mt5"):
                if n["ap_klasse_bis"](z, r, d) != a["ap_klasse_bis"](z, r, d):
                    abw.append((d.isoformat(), r))
        d += timedelta(days=1)
    check(not abw, f"3 jeder Tag 2026–2027 × Futures/CFD × mit/ohne fenster_tz: bitgleich mit BASIS am Plan-Tag ({abw[:3] or 'keine Abweichung'})")

    # 4 ohne heute = heute; Signaturen
    for h in (date(2026, 7, 1), date(2026, 12, 1)):
        n, a = lade(neu_src, h), lade(alt_src, h)
        check(n["ap_start_bis"](Z) == a["ap_start_bis"](Z) and n["ap_klasse_bis"](Z, "tvv2") == a["ap_klasse_bis"](Z, "tvv2"),
              f"4 ohne Plan-Tag wie bisher (heute {h:%d.%m.}): {n['ap_start_bis'](Z)}")
    i = neu_src.index("\ndef ap_klasse_bis(")
    check("bis = ap_start_bis(zeiten, heute)" in neu_src[i:neu_src.find("\n\n\n", i)], "4 ap_klasse_bis gibt den Plan-Tag an ap_start_bis weiter (HT und Emin, dieselbe Funktion)")
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
