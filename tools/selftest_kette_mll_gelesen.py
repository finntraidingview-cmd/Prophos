#!/usr/bin/env python3
"""Selbsttest MLL AUS TOPSTEPX-LESUNG / TAGESSCHLUSS (app.py ap_kette_mll_belegt + ap_kette_trade1, 15.10.2026).

Anlass: Mike …17758280 stand in „Braucht dich" als „geblowt? Balance 147.124 auf/unter dem MLL 147.799", TopstepX zeigte MLL 145.500 —
beide Trades am selben Handelstag (12.10. 23:39 UTC +2.299, 13.10. 09:41 UTC −5.175), der Zwischenstand 152.299 galt als Hochpunkt.

Aufruf:  python3 tools/selftest_kette_mll_gelesen.py
Geprüft: (1) Mikes Fall → MLL 145.500 aus der Lesung, Konto lebt, Reparatur-Tag; (2) ohne Lesung: Zwischenstand zählt nicht, nur der
Tagesschluss (150.000 → 145.500); (3) ohne Lesung, Tagesschluss 152.000 an einem beendeten Tag → 147.500; (4) Tagesschluss 152.000 NACH
einer älteren Lesung 145.500 → 147.500; (5) laufender Handelstag zählt nicht; (6) Express-Lesung (0-basiert) fällt raus;
(7) alte Rechnung ap_kette_mll bleibt für Aufrufer ohne Lesung erhalten."""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


KONTO = {"id": "k-mike", "account_type": "challenge", "name": "150k 17758280", "external_id": "150KTC-SKU-V2-DLL-682437-17758280"}
REGEL = {"namen": ["topstep"], "route": "tsv2", "dd_usd": 4500, "groessen": [150000], "ziel_pct": {"challenge": 6},
         "phasen": {"challenge": {"sl": None, "tp": [4350, 4450], "menge": [2, 3], "tp_max": 4500, "menge_schritt": 1, "puffer_je_menge": {"2": [15, 25], "3": [25, 40]}}},
         "kette": {"daily_usd": 3000}}


def zeile(i, st, en, bs, be, mll=None, typ="challenge"):
    return {"id": f"p{i}", "master_account_id": KONTO["id"], "konto_typ": typ, "started_at": st, "ended_at": en,
            "bal_start": bs, "bal_end": be, "mll_start": mll}


def main():
    a = sd.lade()
    f = a["ap_kette_mll_belegt"]
    jetzt = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)

    # (1) Mike: zwei Trades am selben Handelstag (13.10. nach Chicago-Zählung), beide Lesungen 145.500
    mike = [zeile(1, "2026-10-12T23:39:03+00:00", "2026-10-13T00:06:00+00:00", 150000.0, 152298.66, 145500.0),
            zeile(2, "2026-10-13T09:41:30+00:00", "2026-10-13T11:04:00+00:00", 152298.66, 147123.54, 145500.0)]
    mll, q = f(150000, 4500, KONTO, mike, jetzt)
    check(mll == 145500.0 and "TopstepX-Lesung 13.10. 09:41" in str(q), f"Mike: MLL {mll} aus der Lesung ({q})")
    u = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}
    w, grund = a["ap_konto_rechnen"](REGEL, "challenge", 147123.54, u, peak=152298.66, mll_belegt=(mll, q))
    check(w and not grund and "Reparatur-Tag" in w["stufe"] and w["kette"]["mll"] == 145500.0 and w["kette"]["mll_quelle"] == q
          and w["sl"] == round(147123.54 - 145500 + 200),
          f"Mike: Konto lebt → Reparatur-Tag, SL {w and w.get('sl')} = Luft 1.624 + 200 ({grund or w['stufe']})")
    w2, grund2 = a["ap_konto_rechnen"](REGEL, "challenge", 147123.54, u, peak=152298.66)
    check(w2 is None and "geblowt?" in str(grund2) and "147.799" in str(grund2) and "Hochpunkt" in str(grund2),
          f"ohne Lesung rechnete der alte Weg aus dem Zwischenstand 152.299 → „{grund2}“")

    # (2) ohne Lesung: Zwischenstand zählt nicht, Tagesschluss 147.124 < Größe → 145.500
    ohne = [dict(z, mll_start=None) for z in mike]
    mll, q = f(150000, 4500, KONTO, ohne, jetzt)
    check(mll == 145500.0 and "Startgröße" in str(q), f"ohne Lesung: Zwischenstand 152.299 zählt nicht → MLL {mll} ({q})")

    # (3) Tagesschluss 152.000 an einem beendeten Tag → 147.500
    hoch = [zeile(1, "2026-10-06T14:00:00+00:00", "2026-10-06T15:00:00+00:00", 150000.0, 152000.0),
            zeile(2, "2026-10-07T14:00:00+00:00", "2026-10-07T15:00:00+00:00", 152000.0, 150000.0)]
    mll, q = f(150000, 4500, KONTO, hoch, jetzt)
    check(mll == 147500.0 and "Tagesschluss 152.000 (06.10.)" in str(q), f"Tagesschluss 152.000 → MLL {mll} ({q})")

    # (4) Lesung 145.500 am 06.10., danach Tagesschluss 152.000 am 07.10. → 147.500 (Lesung veraltet)
    spaet = [zeile(1, "2026-10-06T14:00:00+00:00", "2026-10-06T15:00:00+00:00", 150000.0, 150500.0, 145500.0),
             zeile(2, "2026-10-07T14:00:00+00:00", "2026-10-07T15:00:00+00:00", 150500.0, 152000.0)]
    mll, q = f(150000, 4500, KONTO, spaet, jetzt)
    check(mll == 147500.0 and "nach der TopstepX-Lesung" in str(q), f"Tagesschluss nach älterer Lesung → MLL {mll} ({q})")

    # (5) laufender Handelstag (jetzt = 15.10. 14:00 UTC → Handelstag 15.10.) zählt nicht
    heute = [zeile(1, "2026-10-15T09:00:00+00:00", "2026-10-15T10:00:00+00:00", 150000.0, 153000.0)]
    mll, q = f(150000, 4500, KONTO, heute, jetzt)
    check(mll == 145500.0, f"laufender Handelstag: Schluss 153.000 zählt noch nicht → MLL {mll}")

    # (6) Express-Lesung (0-basiert, z. B. −4.500) fällt raus
    express = [zeile(1, "2026-10-13T09:00:00+00:00", "2026-10-13T10:00:00+00:00", 0.0, 1200.0, -4500.0)]
    mll, q = f(150000, 4500, KONTO, express, jetzt)
    check(mll == 145500.0 and "Startgröße" in str(q), f"Express-Lesung −4.500 zählt nicht → MLL {mll}")
    check(f(None, 4500, KONTO, mike, jetzt) == (None, None) and f(150000, 4500, {"id": "x", "account_type": "funded"}, mike, jetzt)[1] is not None,
          "ohne Größe → (None, None); fremde Phase sieht Mikes Pläne nicht")

    # (7) alte Rechnung unverändert
    check(a["ap_kette_mll"](150000, 4500, 152298.66, 147123.54) == 147798.66, "ap_kette_mll (Hochpunkt) rechnet wie bisher")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
