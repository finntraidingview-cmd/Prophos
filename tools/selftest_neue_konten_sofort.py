#!/usr/bin/env python3
"""Selbsttest NEUE KONTEN SOFORT (app.py, Finn 16.10.2026): neu angelegtes Konto / Nachfolger im Fenster → spätestens nach 10 min erkannt,
geplant, bestätigt, gestartet. Fenster je Klasse: Futures 02:00–20:00 Dubai (zeiten.fenster/start_bis), CFD bis 18:00 Dubai (zeiten.cfd_bis).

Aufruf:  python3 tools/selftest_neue_konten_sofort.py
Finn-Korrektur 16.10.2026: in ≤ 10 min erkannt, gelesen, eingeplant und bestätigt — die Startzeit bleibt normal im Fenster verteilt.
Geprüft: ap_cfd_ab/ap_cfd_bis rechnen 02:15/18:00 Dubai je Tag in deutsche Minuten (Sommer/Winter), ohne Schlüssel wie bisher;
ap_klasse_bis CFD/Futures; ap_wecker_pruefen weckt bei neuem Konto/frischer Balance, nie beim ersten Blick; bis_min hält CFD vor 18:00 Dubai."""
import os
import random
import sys
from datetime import date

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_alle_ids as sa  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade_extra(ns):
    src = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
    for fn in ("ap_zeit_dt_min", "ap_fenster_liste", "ap_start_bis", "ap_cfd_ab", "ap_cfd_bis", "ap_klasse_bis", "ap_wecker_pruefen"):
        i = src.index(f"\ndef {fn}(") + 1
        exec(src[i:src.index("\n\n\n", i)], ns)
    return ns


def main():
    a = lade_extra(sa.lade())
    cb, kb, wp = a["ap_cfd_bis"], a["ap_klasse_bis"], a["ap_wecker_pruefen"]
    Z = {"tz": "Europe/Berlin", "fenster": [["00:00", "18:00", 100]], "start_bis": "18:00", "cfd_bis": {"tz": "Asia/Dubai", "uhr": "18:00"}}
    ab = a["ap_cfd_ab"]
    check(ab(dict(Z, cfd_ab={"tz": "Asia/Dubai", "uhr": "02:15"}), date(2026, 10, 16)) == 15, "CFD-Beginn 02:15 Dubai = 00:15 dt im Sommer")
    check(ab({}) == 20 and ab({"cfd_ab": "00:30"}) == 30, "CFD-Beginn ohne Dubai-Angabe wie bisher (Standard 00:20, HH:MM dt)")
    check(cb(Z, date(2026, 10, 16)) == 16 * 60, "CFD-Ende 18:00 Dubai = 16:00 dt im Sommer")
    check(cb(Z, date(2026, 10, 27)) == 15 * 60, "CFD-Ende 18:00 Dubai = 15:00 dt im Winter")
    check(cb({"cfd_bis": "16:00"}) == 16 * 60, "CFD-Ende als HH:MM deutscher Zeit")
    check(cb({}) is None and cb(None) is None, "ohne cfd_bis: kein eigenes CFD-Ende")
    check(kb(Z, "mt5v2", date(2026, 10, 16)) == 16 * 60, "Klasse CFD (mt5v2) → 16:00 dt")
    check(kb(Z, "tvv2", date(2026, 10, 16)) == 18 * 60, "Klasse Futures (tvv2) → start_bis 18:00 dt (= 20:00 Dubai)")
    check(kb({"start_bis": "18:00"}, "mt5v2") == 18 * 60, "CFD ohne cfd_bis → start_bis")
    # Futures-Fenster in Dubai-Zeit (fenster_tz, 16.10.2026): DST-fest wie CFD
    fl, sb = a["ap_fenster_liste"], a["ap_start_bis"]
    ZD = {"fenster_tz": "Asia/Dubai", "fenster": [["02:00", "20:00", 100]], "start_bis": "20:00"}
    check(fl(ZD, date(2026, 10, 16)) == [["00:00", "18:00", 100]], "Futures-Fenster 02:00–20:00 Dubai = 00:00–18:00 dt im Sommer")
    check(fl(ZD, date(2026, 10, 27)) == [["00:00", "17:00", 100]], "Winter: 20:00 Dubai = 17:00 dt, Beginn auf 00:00 gekappt")
    check(fl({"fenster": [["00:00", "16:30", 1]]}) == [["00:00", "16:30", 1]], "ohne fenster_tz: Fenster unverändert (deutsche Zeit)")
    check(fl({}) == [] and fl(None) == [], "ohne Fenster: leer")
    check(sb({"start_bis": "16:30"}) == 16 * 60 + 30, "start_bis ohne fenster_tz: deutsche Zeit wie bisher")
    check(sb(dict(ZD)) in (17 * 60, 18 * 60), "start_bis 20:00 Dubai → 18:00 (Sommer) bzw. 17:00 dt (Winter) für heute")
    # Wecker
    alt = {"konto": "2026-10-16T06:00:00+00:00", "balance": "2026-10-16T06:10:00+00:00"}
    check(wp(alt, None) == (False, False), "Wecker: erster Blick weckt nie")
    check(wp(alt, alt) == (False, False), "Wecker: nichts Neues → schläft")
    check(wp(dict(alt, konto="2026-10-16T06:01:00+00:00"), alt) == (True, False), "Wecker: neues Konto → wecken")
    check(wp(dict(alt, balance="2026-10-16T06:11:00+00:00"), alt) == (False, True), "Wecker: frische Balance → wecken")
    check(wp({"konto": None, "balance": None}, alt) == (False, False), "Wecker: leere Antwort → schläft")
    # CFD-Ende per bis_min: sofort-Tranche nach dem CFD-Ende bekommt keinen Platz
    verteilen = a["ap_zeiten_verteilen"]
    ZV = {"fenster": [["00:00", "18:00", 1]], "start_bis": "18:00"}
    m = verteilen([{"key": "c|fn#1", "user": "c", "gruppe": "c|fn", "fkey": "fn", "dauer_min": 2, "bis_min": 16 * 60}],
                  ZV, random.Random(1), frueheste_min=16 * 60 + 5)
    check("c|fn#1" not in m, "CFD nach 18:00 Dubai (16:00 dt): kein Platz mehr heute")
    zu_spaet = 0
    for seed in range(200):
        m = verteilen([{"key": "c|fn#1", "user": "c", "gruppe": "c|fn", "fkey": "fn", "dauer_min": 2, "bis_min": 16 * 60, "ab_min": 15}],
                      ZV, random.Random(seed), frueheste_min=8 * 60 + 16)
        if m.get("c|fn#1") is None or not (8 * 60 + 16 <= m["c|fn#1"] < 16 * 60):
            zu_spaet += 1
    check(zu_spaet == 0, "CFD-Nachplan um 10:00 Dubai: Start verteilt zwischen jetzt + 15 und 18:00 Dubai (200 Seeds)")
    print(f"\n{'ALLES OK' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
