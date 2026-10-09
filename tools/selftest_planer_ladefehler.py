#!/usr/bin/env python3
"""Selbsttest PLANER-LADEFEHLER SICHTBAR (prophos.html, 09.10.2026, Slave-Terminal 4 — Master: GET /admin/auto-plan lief ab ~23:37 UTC auf
HTTP 500, der Planer fiel STILL auf den Zwischenspeicher prophos_tpl_cache zurück und zeigte Finn über eine Stunde einen alten Lauf).
Quelltext-Proben (das Verhalten ist im Stub mit simuliertem 500 geprüft): Status am Fehler, Erfolgs-/Fehlerzeit, Zeile mit genau einer
Ursache in Trade-Planer, Admin-Trade-Planer und Planer-Leiste, Delta gleich, Zwischenspeicher stempelt einen Fehlschlag nie als frisch.
Aufruf: python3 tools/selftest_planer_ladefehler.py"""
import os
import sys

HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prophos.html")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    h = open(HTML, encoding="utf-8").read()
    check("f.status = r.status; f.daten = d; throw f }   // daten: z. B. abweichung (Probelauf)" in h, "apApi: HTTP-Status am Fehler")
    check("_ap.geholtAt = Date.now(); _ap.ladeFehler = null; _ap.ausCache = false" in h
          and "pr.catch(e => { if(_ap.lauf === pr) _ap.ladeFehler = { status: (e && e.status) || 0," in h,
          "apLetztenHolen: Erfolgszeit bzw. Ladefehler {status, msg, at}")
    check("`⚠ ${was} nicht geladen (${grund}) — ${stand ? `Anzeige = Zwischenspeicher von ${stand} Dubai` : 'keine Daten'}. Seite neu laden; hält es an, Backend prüfen.`" in h
          and "`HTTP ${f.status}`" in h and "`keine Verbindung: ${" in h, "Satz: genau eine Ursache (HTTP-Status bzw. keine Verbindung) + Stand")
    check("_apd.fehlerInfo = { status: (e && e.status) || 0, msg: _apd.fehler, at: Date.now() }" in h and "apLadeFehlerSatz('Delta-Daten'" in h,
          "Delta: Status gemerkt, eigener Satz mit Stand = um des letzten Deltas")
    check("const alt = (_ap.ladeFehler || _apd.fehler) ? tplCacheLesen() : null" in h
          and "const apAt = _ap.ladeFehler ? (alt && (alt.apAt || alt.at)) || 0 : (_ap.geholtAt || 0)" in h
          and "at: apAt || Date.now(), apAt," in h and "_ap.geholtAt = c.apAt || c.at }" in h,
          "Zwischenspeicher: Fehlschlag behält Lauf/Delta und Zeit des alten Stands, Lesen setzt den Stand")
    check(h.count("[apLadeFehlerText(), apdLadeFehlerText()].filter(Boolean)") == 1
          and "typeof apLadeFehlerText === 'function' ? apLadeFehlerText() : ''" in h and "const fzAp = fzHier ? apLadeFehlerText() : ''" in h,
          "Zeile im Trade-Planer, im Admin-Trade-Planer und in der Planer-Leiste")
    # 09.10.2026 (Befund Prüfer S2): Leiste steht auf der Trade-Planer-Seite über #tpl-root → dort keine zweite Zeile
    check("const fzHier = !el.closest('#tpl-view') && !!_ap.ladeFehler" in h
          and "if(!_ap.imPlaner && !vorschlaege.length && !bestaetigt && !fzHier){ el.style.display = 'none'; return }" in h,
          "Planer-Leiste: Ladefehler-Zeile nur außerhalb der Trade-Planer-Seite (dort einmal in #tpl-root)")
    check("apLetztenHolen().then(() => { _tpl.fehler = '' }, () => { _tpl.fehler = '' })" in h, "kein zweiter, roher Fehlertext für denselben Abruf")
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
