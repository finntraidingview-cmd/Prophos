#!/usr/bin/env python3
"""Selbsttest BESTANDEN-DATUM (prophos.html bstZeitKurz / bstZeitVon / bstTsSort, 21.10.2026 — Finn 04:50 Dubai: „das Datum, wann der Account
gepasst wurde, und bei den Apex-Accounts auch die Uhrzeit … automatisch nach Zeit sortieren: die neuesten ganz oben"). Zieht die drei reinen
Funktionen aus prophos.html und führt sie in JavaScriptCore aus (osascript -l JavaScript, auf jedem Mac da — kein Node nötig).
Fälle: heute → „heute HH:MM" fett; gestern → „gestern" (Apex mit Uhrzeit); 3 Tage → „vor 3 T"; ≥ 7 Tage → „TT.MM." (Apex mit Uhrzeit);
Kalendertag nach Dubai (21:30 UTC = nächster Tag); ohne Zeitstempel „–"; Quelle Ziel-Tag vor Trade-Ende; Sortierung absteigend, null unten.
Aufruf: python3 tools/selftest_bestanden_datum.py"""
import json
import os
import re
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(os.path.dirname(HIER), "prophos.html")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def funktion(src, name):
    i = src.index(f"\n  function {name}(") + 1
    return src[i:src.index("\n  }\n", i) + 4]


def main():
    src = open(HTML, encoding="utf-8").read()
    js = funktion(src, "bstZeitVon") + funktion(src, "bstZeitKurz")
    js += re.search(r"^  const bstTsSort = .*$", src, re.M).group(0) + "\n"
    js += r"""
    const J = '2026-10-21T00:50:00Z'   // = 21.10.2026 04:50 Dubai (Finns Uhrzeit)
    const out = {}
    out.heute = bstZeitKurz('2026-10-20T13:06:00Z', false, J)            // 17:06 Dubai am 20.10. — Dubai-Tag 20.10., jetzt ist 21.10. 04:50 → 1 Tag? nein: s.u.
    out.heuteApex = bstZeitKurz('2026-10-21T00:10:00Z', true, J)         // 04:10 Dubai heute
    out.gestern = bstZeitKurz('2026-10-20T05:10:00Z', false, J)
    out.gesternApex = bstZeitKurz('2026-10-20T05:10:00Z', true, J)
    out.vor3 = bstZeitKurz('2026-10-18T10:00:00Z', false, J)
    out.vor3Apex = bstZeitKurz('2026-10-18T10:00:00Z', true, J)
    out.alt = bstZeitKurz('2026-10-11T10:00:00Z', false, J)
    out.altApex = bstZeitKurz('2026-10-11T10:00:00Z', true, J)
    out.tagwechsel = bstZeitKurz('2026-10-20T21:30:00Z', false, '2026-10-20T22:00:00Z')   // 01:30 Dubai am 21.10., jetzt 02:00 Dubai 21.10. → heute
    out.leer = bstZeitKurz(null, false, J)
    out.quelleTag = bstZeitVon('2026-10-20T13:06:00Z', { ended_at: '2026-10-20T12:00:00Z' })
    out.quelleTrade = bstZeitVon(null, { ended_at: '2026-10-20T12:00:00Z' })
    out.quelleNix = bstZeitVon(null, null)
    out.sort = [{ ts: null, n: 'leer' }, { ts: '2026-10-18T10:00:00Z', n: 'alt' }, { ts: '2026-10-21T00:10:00Z', n: 'neu' }, { ts: '2026-10-20T05:10:00Z', n: 'mitte' }].sort(bstTsSort).map(x => x.n)
    JSON.stringify(out)
    """
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], capture_output=True, text=True)
    if r.returncode != 0:
        print("✗ JavaScriptCore:", r.stderr.strip()[:400]); sys.exit(1)
    o = json.loads(r.stdout.strip())
    # 20.10. 17:06 Dubai gegen jetzt 21.10. 04:50 Dubai = Kalendertag davor → „gestern" (Finn: „welcher heute reingelaufen ist und welcher schon vor Tagen")
    check(o["heute"]["txt"] == "gestern" and o["heute"]["tage"] == 1, f"20.10. 17:06 Dubai, jetzt 21.10. 04:50 → gestern ({o['heute']['txt']})")
    check(o["heuteApex"]["txt"] == "<b>heute 04:10</b>" and o["heuteApex"]["tage"] == 0, f"heute 04:10 Dubai → fett mit Uhrzeit ({o['heuteApex']['txt']})")
    check(o["gestern"]["txt"] == "gestern", f"gestern ohne Uhrzeit (kein Apex) ({o['gestern']['txt']})")
    check(o["gesternApex"]["txt"] == "gestern 09:10", f"Apex gestern MIT Uhrzeit Dubai ({o['gesternApex']['txt']})")
    check(o["vor3"]["txt"] == "vor 3 T", f"3 Tage → vor 3 T ({o['vor3']['txt']})")
    check(o["vor3Apex"]["txt"] == "vor 3 T · 14:00", f"Apex 3 Tage → vor 3 T · 14:00 ({o['vor3Apex']['txt']})")
    check(o["alt"]["txt"] == "11.10." and o["alt"]["tage"] == 10, f"10 Tage → Datum 11.10. ({o['alt']['txt']})")
    check(o["altApex"]["txt"] == "11.10. 14:00", f"Apex 10 Tage → 11.10. 14:00 ({o['altApex']['txt']})")
    check(o["alt"]["tip"] == "11.10.2026 14:00 Dubai", f"Tooltip voller Zeitstempel Dubai ({o['alt']['tip']})")
    check(o["tagwechsel"]["txt"] == "<b>heute 01:30</b>", f"21:30 UTC = 01:30 Dubai = heute (Kalendertag Dubai, nicht UTC) ({o['tagwechsel']['txt']})")
    check(o["leer"]["txt"] == "–" and o["leer"]["tage"] is None, f"ohne Zeitstempel → – ({o['leer']['txt']})")
    check(o["quelleTag"]["ts"] == "2026-10-20T13:06:00Z" and o["quelleTag"]["quelle"].startswith("Ziel-Wache"), f"Ziel-Tag geht vor Trade-Ende ({o['quelleTag']['quelle']})")
    check(o["quelleTrade"]["ts"] == "2026-10-20T12:00:00Z" and o["quelleTrade"]["quelle"].startswith("Trade-Ende"), f"ohne Ziel-Tag → Trade-Ende ({o['quelleTrade']['quelle']})")
    check(o["quelleNix"]["ts"] is None, "ohne beides → kein Zeitstempel")
    check(o["sort"] == ["neu", "mitte", "alt", "leer"], f"Sortierung: neueste oben, ohne Zeitstempel unten ({o['sort']})")
    # Verdrahtung: Spalte in allen vier Stationen + Sortierung je Station
    check(src.count("bstDatumZelle(") >= 4, f"bstDatumZelle an bstZeilen, Rest von Hand, Trade-/Review-Zeilen ({src.count('bstDatumZelle(')}×)")
    check("'Balance → Ziel', 'Tage', 'Bestanden', 'Status', ''" in src and "['Ergebnis', 'Konto', 'Bestanden', 'P&amp;L', 'Zu']" in src, "Spaltenkopf Bestanden in bstTab und Trade abhaken")
    check(src.count(".sort(bstTsSort)") >= 3 and "nachZiel(bestTr || [])" in src, "Sortierung nach Zeit in Tage sammeln/Review, Rest von Hand, Trade abhaken")
    check('grid-template-areas:"wer ri mi konto datum pl zeit"' in src and '"datum datum datum datum" "ri mi mi zeit"' in src, "CSS: Spalte datum (Desktop) + eigene Zeile unter dem Namen (Handy)")
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler:"); [print("  - " + f) for f in FEHLER]; sys.exit(1)
    print("ALLES GRÜN")


if __name__ == "__main__":
    main()
