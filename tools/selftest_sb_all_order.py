#!/usr/bin/env python3
"""Selbsttest _sb_all ohne id (16.10.2026, Fund Slave 3: „[auto-plan] ⚠️ Sperr-Matrix: HTTPError 400" bei jedem Lauf → die Gesperrt-Sperre
wirkte nie). _sb_all setzt ohne eigenes order `order=id.asc`; Tabellen OHNE id-Spalte antworten darauf mit 400 (gegen das echte PostgREST
geprüft: vorrat_matrix, bank_staende, liq_personen → 400 mit id.asc, 200/401 mit eigener Sortierung). Prüft statisch: jeder _sb_all-Aufruf
auf eine dieser Tabellen bringt ein eigenes "order" mit. Neue Tabelle ohne id → hier eintragen.

Aufruf:  python3 tools/selftest_sb_all_order.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
# Stand Live-DB 16.10.2026 (information_schema: Tabellen in public ohne Spalte id)
OHNE_ID = ("admin_zugang", "auto_close_regeln", "auto_plan_gruppe", "bank_staende", "duplikum_credentials", "echo_hedge",
           "echo_loesch_auftraege", "echo_notfall", "fleet_privat", "id_gruppe_mitglied", "liq_personen", "mirror_logs", "mt5_links",
           "pc_namen", "prop_baum_haken", "prop_baum_schnappschuss", "puls_augen", "puls_diagnose", "puls_ergebnisse", "puls_inventar",
           "reader_diagnose", "topstep_credentials", "tv_kurs_1m", "vorrat_matrix", "vorrat_ziele", "wd_tagesplan")


def main():
    src = open(APP, encoding="utf-8").read()
    ok, n = True, 0
    for m in re.finditer(r'_sb_all\(\s*"([a-z_]+)"', src):
        tab = m.group(1)
        if tab not in OHNE_ID:
            continue
        # Argumente bis zur schließenden Klammer des Aufrufs (Klammern zählen)
        i, tiefe = m.end(), 1
        while tiefe and i < len(src):
            tiefe += {"(": 1, ")": -1}.get(src[i], 0)
            i += 1
        aufruf, zeile = src[m.start():i], src.count("\n", 0, m.start()) + 1
        n += 1
        hat = '"order"' in aufruf
        print(("✓ " if hat else "✗ ") + f"app.py:{zeile} _sb_all(\"{tab}\") mit eigenem order")
        ok = ok and hat
    if n == 0:
        print("✗ keine Aufrufe gefunden — Muster veraltet?")
        ok = False
    print("OK" if ok else "FEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
