#!/usr/bin/env python3
"""Selbsttest: POLAR SCHLIESSEN PER × (20.10.2026, Finn: „egal wer zuerst zu ist, der andere schließt in 1–2 s — einfach auf das X").
Rein rechnend: polar_app.zu_eintragen/warte_zu_fertig/zu_erste_seite (erste zu-Meldung gewinnt, zweite = Bestätigung, Warten nur auf
die ANDERE Seite) und polar_bot.profit_x_wahl (nie die × neben S/L, T/P) / chart_x_wahl (genau ein Chart-×) / schliess_urteil /
zu_signal_urteil. Aufruf: python3 tools/selftest_polar_close.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
STAMM = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(STAMM, "mt5-copier"))
import polar_bot as pb  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


def lade_app():
    """polar_app ohne Flask: nur die reinen Funktionen + ENDE aus dem Quelltext."""
    src = open(os.path.join(STAMM, "polar_app.py"), encoding="utf-8").read()
    ns = {"re": re}
    teile = [re.search(r"^ENDE = .*$", src, re.M).group(0)]
    for name in ("_zahl", "zu_erste_seite", "zu_eintragen", "warte_zu_fertig", "abrechnung_rechnen"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def main():
    A = lade_app()
    zu, warte, erste, abr = A["zu_eintragen"], A["warte_zu_fertig"], A["zu_erste_seite"], A["abrechnung_rechnen"]
    print("1) zu_eintragen — erste Meldung gewinnt")
    z = {"status": "offen", "master": {}, "slave": {}}
    db, e, n = zu(z, "master", {"quelle": "reader"}, 1000)
    check(e and n and db == {"master_zu_ms": 1000} and z["zu_quelle"] == "master" and z["zu_ms"] == 1000, "Master zuerst: zu_quelle master, db master_zu_ms")
    db2, e2, n2 = zu(z, "slave", {"quelle": "slave"}, 1800)
    check(n2 and not e2 and db2 == {"slave_zu_ms": 1800} and z["zu_quelle"] == "master" and z["slave_zu_ms"] == 1800, "Slave danach: Bestätigung, zu_quelle bleibt master")
    db3, e3, n3 = zu(z, "master", {}, 2500)
    check(not n3 and not e3 and db3 == {} and z["master_zu_ms"] == 1000, "Master nochmal: nichts geändert")
    z2 = {"status": "offen"}
    db4, e4, n4 = zu(z2, "slave", {"quelle": "slave", "zu_ms": 50}, 50)
    check(e4 and n4 and z2["zu_quelle"] == "slave" and z2["slave"]["zu"]["quelle"] == "slave", "Slave zuerst (SL/TP beim Broker): zu_quelle slave, Daten am Teil")
    check(zu({"status": "offen"}, "panel", {}, 1) == ({}, False, False), "fremde Seite: nichts")
    print("2) warte_zu_fertig — nur die ANDERE Seite weckt")
    z = {"status": "offen", "master_zu_ms": 100}
    check(warte(z, "slave") is True and warte(z, "master") is False, "Master zu: Slave-Wache fertig, Master-Wache nicht (eigenes zu weckt nie)")
    z = {"status": "slave_zu", "slave_zu_ms": 100}
    check(warte(z, "master") is True and warte(z, "slave") is False, "Slave zu: Master-Wache fertig, Slave-Wache nicht")
    check(warte({"status": "fehler"}, "master") is True and warte({"status": "fertig"}, "slave") is True, "Lauf-Ende weckt beide")
    check(warte({"status": "offen"}, "master") is False, "nichts zu: weiter warten")
    print("3) zu_erste_seite — aus den DB-Zeiten")
    check(erste({"master_zu_ms": 5, "slave_zu_ms": 9}) == {"zu_ms": 5, "zu_quelle": "master"}, "Master 5 < Slave 9 → master")
    check(erste({"master_zu_ms": 9, "slave_zu_ms": 5}) == {"zu_ms": 5, "zu_quelle": "slave"}, "Slave 5 < Master 9 → slave")
    check(erste({"master_zu_ms": None, "slave_zu_ms": 7}) == {"zu_ms": 7, "zu_quelle": "slave"} and erste({}) == {"zu_ms": None, "zu_quelle": None}, "nur eine Seite / keine")
    print("4) zu_signal_urteil — Antwort von /polar/warte")
    u = pb.zu_signal_urteil
    check(u({"slave_zu_ms": 1, "status": "slave_zu"}, "master") == "zu" and u({"master_zu_ms": 1, "status": "master_zu"}, "master") is None, "Master: nur slave_zu_ms weckt")
    check(u({"master_zu_ms": 1, "status": "master_zu"}, "slave") == "zu" and u({"slave_zu_ms": 1, "status": "slave_zu"}, "slave") is None, "Slave: nur master_zu_ms weckt")
    check(u({"status": "fehler"}, "slave") == "zu" and u({"status": "fertig"}, "master") == "ende" and u({"status": "offen", "warte": True}, "slave") is None, "fehler = schließen, fertig = Ende, sonst warten")
    check(u(None, "slave") is None, "keine Antwort → warten")
    print("5) profit_x_wahl — nie S/L- oder T/P-×")
    px = pb.profit_x_wahl
    check(px(700, 1200) == (1186, 700, "rechter Listenrand 1200 − 14 px (Profit = letzte Spalte)"), "ohne Spalten: rechter Rand − 14 px")
    sp = [{"name": "Symbol", "left": 0, "right": 120}, {"name": "S / L", "left": 400, "right": 520}, {"name": "T / P", "left": 520, "right": 640},
          {"name": "Price", "left": 640, "right": 760}, {"name": "Profit", "left": 760, "right": 900}]
    r = px(700, 1200, sp)
    check(r and r[0] == 886 and r[1] == 700 and "Profit" in r[2], f"mit Spalten: Profit rechts 900 − 14 = 886 ({r})")
    check(px(700, 1200, [c for c in sp if c["name"] != "Profit"]) is None, "ohne Profit-Spalte: None (nichts raten)")
    sp2 = [{"name": "Profit", "left": 0, "right": 120}, {"name": "T / P", "left": 520, "right": 640}]
    check(px(700, 1200, sp2) is None, "Profit links von T/P: None (× wäre neben einem Level-×)")
    check(px(700, 1200, [{"name": "Profit", "left": 760, "right": 900}, {"name": "Gewinn", "left": 900, "right": 1000}]) is None, "zwei Profit-Spalten: None")
    check(px("x", 1200) is None, "unlesbare Zeile: None")
    print("6) chart_x_wahl — genau ein × der Positions-Linie im Chart")
    cx = pb.chart_x_wahl
    k_chart = {"rect": [700, 196, 18, 18], "text": "×", "aria": "", "title": "", "tooltip": "Position Schließen", "dn": "", "im_chart": True, "in_tabelle": False}
    k_tab = {"rect": [1100, 800, 18, 18], "text": "", "aria": "Close", "title": "", "tooltip": "", "dn": "close-settings-cell-button", "im_chart": False, "in_tabelle": True}
    check(cx([k_chart, k_tab]) is k_chart, "Chart-× (Tooltip „Position Schließen“) gewinnt, Tabellen-Knopf zählt nicht")
    check(cx([dict(k_chart, tooltip="", aria="Close position")]) is not None, "aria „Close position“ reicht")
    check(cx([dict(k_chart, tooltip="", aria="", title="")]) is None, "nacktes × ohne Beschriftung: None")
    check(cx([k_chart, dict(k_chart, rect=[200, 196, 18, 18])]) is None, "zwei Chart-×: None (nie raten)")
    check(cx([k_chart, dict(k_chart)]) is k_chart, "dasselbe Rechteck doppelt zählt einmal")
    check(cx([dict(k_chart, aria="Close all positions")]) is None and cx([dict(k_chart, aria="Reverse position")]) is None, "Close all / Reverse: nie")
    check(cx([dict(k_chart, im_chart=False)]) is None and cx([dict(k_chart, rect=[1, 1, 2, 2])]) is None, "außerhalb des Charts / zu klein: None")
    print("7) schliess_urteil — Beweis ≤ 2 s, sonst Rückfall")
    su = pb.schliess_urteil
    check(su(True, 0.8) == "zu" and su(True, 2.0) == "zu", "weg in 0,8 / 2,0 s → zu")
    check(su(True, 2.5) == "rueckfall" and su(True, None) == "rueckfall", "nach 2,5 s / nie weg → Rückfall")
    check(su(False, 0.1) == "rueckfall", "nicht gedrückt → Rückfall")
    check(su(True, None, dialog_knopf=True) == "dialog", "Rückfrage mit eindeutigem Knopf → dialog")
    print("8) Abrechnung — Verzug mit Vorzeichen, Slave zuerst")
    z = {"master": {"gefuellt": {"fill": 1, "klick_ms": 100}, "ende": {"balance_start": 1000, "balance_end": 1050}},
         "slave": {"gefuellt": {"fill": 1, "klick_ms": 130}, "ende": {"wache": {"profit": -40, "zu_weg": "x", "balance_end": 960}, "balance_start": 1000}},
         "master_zu_ms": 5000, "slave_zu_ms": 3800}
    e = abr(z)
    check(e["verzug_ms"] == -1200 and e["slave_zu_weg"] == "x" and e["master_pl"] == 50 and e["slave_pl"] == -40, f"Slave 1,2 s vor dem Master: verzug −1200, Wege/P&L unverändert ({e['verzug_ms']})")
    print()
    if FEHLER:
        print(f"FEHLER: {len(FEHLER)}")
        return 1
    print("OK — alle Prüfungen bestanden")
    return 0


if __name__ == "__main__":
    sys.exit(main())
