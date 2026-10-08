#!/usr/bin/env python3
"""Selbsttest FREMD-KONFLIKTE NUR GESENDET (sql/2026-10-08_fremd_konflikte_nur_gesendet.sql + app.py fp_tick, 08.10.2026, Slave-Terminal 3 —
Befund Prüfer: ein bloßer Start-Claim löste „⚠ Gegenhedge" gegen eine gewollte Hand-Position aus).

Aufruf:  python3 tools/selftest_fremd_nur_gesendet.py
Ohne Netz, statisch: (1) in prophos_fremd_konflikte zählt als Plan-Start nur coalesce(started_at, orbit_gesendet_at), der Claim
(start_um_gestartet_at) kommt im Funktionsrumpf nicht mehr vor; (2) Pläne mit start_fehler ohne started_at fallen heraus, außer „unklar"
oder „behoben"; (3) Rückgabe-Spalten und Rechte wie in sql/2026-10-08_fremd_positionen.sql; (4) app.py fp_tick schreibt gegen jeden Takt
aus der Konflikt-Lesung neu (rote Zeile verschwindet, sobald der Plan herausfällt) und pusht nur über fp_alarme. Die Regel selbst ist am
08.10.2026 gegen die Live-DB geprobt (nur SELECT): 8 konstruierte Fälle wie erwartet, Vorfall 13:35 UTC fällt heraus."""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.join(HIER, "..")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def ohne_kommentare(sql):
    return "\n".join(z.split("--", 1)[0] for z in sql.splitlines())


def main():
    neu = open(os.path.join(WURZEL, "sql", "2026-10-08_fremd_konflikte_nur_gesendet.sql"), encoding="utf-8").read()
    alt = open(os.path.join(WURZEL, "sql", "2026-10-08_fremd_positionen.sql"), encoding="utf-8").read()
    code = ohne_kommentare(neu)
    rumpf = code[code.index("create or replace function public.prophos_fremd_konflikte()"):]

    check("start_um_gestartet_at" not in rumpf, "Claim (start_um_gestartet_at) zählt nicht mehr als Plan-Start")
    check(rumpf.count("coalesce(t.started_at, t.orbit_gesendet_at)") == 2, "Start und 1-Tages-Filter = coalesce(started_at, orbit_gesendet_at)")
    check(re.search(r"not \(t\.started_at is null\s+and t\.mt5_baseline \? 'start_fehler'", rumpf) is not None
          and "'unklar', 'false') <> 'true'" in rumpf and "'status', '') <> 'behoben'" in rumpf,
          "Startfehler ohne Start fällt heraus, außer unklar/behoben")
    kopf = r"returns table\(fremd_id bigint, art text, gegen_id text, gegen_user uuid, gegen_konto text, gegen_richtung text, gegen_seit timestamptz\)"
    check(re.search(kopf, neu) is not None and re.search(kopf, alt) is not None, "Rückgabe-Spalten unverändert")
    check("grant execute on function public.prophos_fremd_konflikte() to service_role;" in neu
          and "revoke all on function public.prophos_fremd_konflikte() from public, anon, authenticated;" in neu, "Rechte unverändert")
    check("prophos_gegenhedge_konflikt" not in code, "Start-Riegel (prophos_gegenhedge_konflikt) wird nicht angefasst")

    app = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
    tick = app[app.index("def fp_tick("):app.index("def fp_loop(")]
    check("if (f.get(\"gegen\") or []) != neu:" in tick and "{\"gegen\": neu}" in tick,
          "fp_tick schreibt gegen jeden Takt aus prophos_fremd_konflikte neu (rote Zeile verschwindet von selbst)")
    check("alarme = fp_alarme(aktive, konflikte)" in tick, "Push nur für Konflikte aus der aktuellen Lesung (fp_alarme)")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
