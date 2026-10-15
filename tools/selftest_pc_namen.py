#!/usr/bin/env python3
"""Selbsttest PC-NAMEN (app.py pc_namen_zuordnen + prophos.html pcLabel, 16.10.2026).

Anlass: Finn 16.10.2026 „In Zukunft beschrifte die PCs jeweils mit dem Namen" — überall „Name · pc-xxxxxx" statt nur der Kennung.
Aufruf:  python3 tools/selftest_pc_namen.py
Geprüft: (1) Tabelle pc_namen gewinnt vor dem Login; (2) ohne Tabelle: jüngste mt5_live-Meldung je PC → Name der ID; (3) unbekannte ID /
leerer Name → kein Eintrag; (4) Frontend: eine zentrale pcLabel/pcLabelHtml, keine rohe Kennung mehr in den umgestellten Anzeigen."""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HIER, "..", "app.py")
HTML = os.path.join(HIER, "..", "prophos.html")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade():
    src = open(APP, encoding="utf-8").read()
    i = src.index("\ndef pc_namen_zuordnen(") + 1
    ns = {}
    exec(src[i:src.find("\n\n\n", i)], ns)
    return ns


def main():
    f = lade()["pc_namen_zuordnen"]
    namen = {"u1": "Marc", "u2": "Finn"}
    live = [{"pc_name": "pc-aaaaaa", "updated_at": "2026-10-16T01:00:00+00:00", "user_id": "u2"},
            {"pc_name": "pc-aaaaaa", "updated_at": "2026-10-16T02:00:00+00:00", "user_id": "u1"},
            {"pc_name": "pc-bbbbbb", "updated_at": "2026-10-16T02:00:00+00:00", "user_id": "u2"},
            {"pc_name": "pc-cccccc", "updated_at": "2026-10-16T02:00:00+00:00", "user_id": "u9"}]
    d = f([], live, namen)
    check(d.get("pc-aaaaaa") == {"name": "Marc", "quelle": "login"}, f"Login-Rückfall: jüngste Meldung zählt ({d.get('pc-aaaaaa')})")
    check(d.get("pc-bbbbbb", {}).get("name") == "Finn" and "pc-cccccc" not in d, "unbekannte ID → kein Eintrag")
    d = f([{"pc_id": "pc-bbbbbb", "name": "Büro"}, {"pc_id": "pc-dddddd", "name": " "}], live, namen)
    check(d.get("pc-bbbbbb") == {"name": "Büro", "quelle": "tabelle"} and "pc-dddddd" not in d, "Tabelle gewinnt, leerer Name zählt nicht")
    check(f(None, None, {}) == {}, "nichts → leer")

    html = open(HTML, encoding="utf-8").read()
    check(html.count("function pcLabel(pc)") == 1 and html.count("function pcLabelHtml(pc)") == 1 and "/pc-namen" in html,
          "eine zentrale pcLabel/pcLabelHtml, Daten aus /pc-namen")
    roh = [m for m in ("PC <span class=\"mono\">${escapeHtml(String(row.pc || '?'))}</span>", "(PC ${row.pc})", "(PC ${st.pc})",
                       "<td class=\"mono\">${escapeHtml(q.pc_name || '–')}</td>", "Reader auf ${pc}") if m in html]
    check(not roh, f"keine rohe Kennung mehr in den umgestellten Anzeigen ({roh})")
    src = open(APP, encoding="utf-8").read()
    rw = src[src.index("def reader_wacht_schritt("):src.index("\n\n\n", src.index("def reader_wacht_schritt("))]
    check(not re.search(r"· PC \{pc or ", src) and rw.count("_lbl(") >= 7 and "pc_namen=_rw_pc_namen()" in src and "_pc_namen_daten(" not in rw,
          "Reader-Meldungen (Handy) mit Namen, reader_wacht_schritt bleibt ohne Netz (Namen als Parameter)")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
