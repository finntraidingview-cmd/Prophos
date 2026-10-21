#!/usr/bin/env python3
"""Selbsttest: POLAR SCHLIESSEN PER × (20.10.2026, Finn: „egal wer zuerst zu ist, der andere schließt in 1–2 s — einfach auf das X").
Rein rechnend: polar_app.zu_eintragen/warte_zu_fertig/zu_erste_seite (erste zu-Meldung gewinnt, zweite = Bestätigung, Warten nur auf
die ANDERE Seite) und polar_bot.profit_x_wahl (nie die × neben S/L, T/P) / chart_x_wahl (genau ein Chart-×) / schliess_urteil /
zu_signal_urteil; Maus-Test × (20.10.2026): uia_zeile_wahl / x_abstand_rechts. Aufruf: python3 tools/selftest_polar_close.py"""
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
    import time as _tm
    ns = {"re": re, "time": _tm}
    teile = [re.search(r"^ENDE = .*$", src, re.M).group(0), re.search(r"^POLAR_PUFFER_PCT = .*$", src, re.M).group(0)]
    for name in ("_zahl", "zu_erste_seite", "zu_eintragen", "warte_zu_fertig", "abrechnung_rechnen", "slave_pkt_aus_master", "liq_vorgabe", "ende_und_balance_zeit"):
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
    print("9) Maus-Test × — uia_zeile_wahl / x_abstand_rechts")
    uz, xa = pb.uia_zeile_wahl, pb.x_abstand_rechts
    zl = [{"text": "12345 2026.10.20 buy 0.50 NAS100", "rect": [10, 700, 900, 18], "typ": "DataItem"}, {"text": "12346 sell 0.50 NAS100", "rect": [10, 718, 900, 18]}]
    check(uz(zl, "NAS100", 12346)["rect"][1] == 718, "Ticket 12346 → genau diese Zeile")
    check(uz(zl, "NAS100", 1234) is None and uz(zl, "NAS100", 99999) is None, "Ticket als Teilzahl / unbekannt → None")
    check(uz(zl, "nas100")["rect"][1] == 700 and uz(zl, "XAUUSD") is None, "ohne Ticket: erste Zeile des Symbols, fremdes Symbol → None")
    check(uz(zl + [dict(zl[1])], "NAS100", 12346) is None, "zwei Zeilen mit demselben Ticket → None (nie raten)")
    check(xa((1186, 700), 1200) == 14 and xa((1300, 0), 1200) == -100 and xa(None, 1200) is None, "Abstand zum rechten Rand, außerhalb negativ, unlesbar None")
    print("10) Slave-× nur aus der Profit-Zelle mit Tooltip-Beweis (Master-Entscheid 20.10.2026)")
    pz, xk, upz = pb.profit_x_aus_zelle, pb.x_klick_erlaubt, pb.uia_profit_zelle
    zelle = [760, 700, 140, 18]
    check(pz(zelle) == (890, 709), f"Zelle 760..900 → × bei 890 (−10 px), Zeilenmitte 709 ({pz(zelle)})")
    check(pz([760, 700, 12, 18]) is None and pz([760, 700, 140, 4]) is None and pz(None) is None, "zu schmal / zu flach / keine Zelle → None")
    check(xk(zelle, "Close #12345 buy 0.50", True) is True and xk(zelle, "Position schließen", True) is True, "Zelle + Tooltip Close/Schließen + einzige Position → Klick erlaubt")
    check(xk(zelle, "", True) is False and xk(zelle, "Take Profit", True) is False, "OHNE passenden Tooltip → kein Klick (Rückfall Rechtsklick)")
    check(xk(None, "Close", True) is False and xk(zelle, "Close", False) is False, "ohne Zelle / mehrere Positionen → kein Klick")
    zl = [760, 700, 900, 18]
    cells = [{"text": "12345", "rect": [10, 700, 80, 18]}, {"text": "S/L 1.0", "rect": [400, 700, 120, 18]}, {"text": "T/P 2.0", "rect": [520, 700, 120, 18]},
             {"text": "107.07", "rect": [760, 700, 140, 18]}, {"text": "andere Zeile", "rect": [760, 718, 140, 18]}, {"text": "Kopf Profit", "rect": [760, 640, 140, 22]}]
    check(upz(cells, zl)["text"] == "107.07", "Profit-Zelle = rechteste Zelle im Zeilenband (nicht die Nachbarzeile, nicht der Spaltenkopf)")
    check(upz([c for c in cells if c["text"] in ("andere Zeile", "Kopf Profit")], zl) is None, "keine Zelle im Band → None")
    print("10b) ×-Beweis per Bild (21.10.2026, Lauf 8870f1de: MT5-Liste ohne UIA-Zellen)")
    WEISS, GRAU, BLAU, SCHWARZ = 0xFFFFFF, 0x808080, 0x3399FF, 0x000000

    def bild(b, h, hg=WEISS):
        return [[hg] * b for _ in range(h)]

    def kreuz(p, x0, y0, n, farbe=GRAU, dick=1):
        for i in range(n):
            for d in range(dick):
                for (x, y) in ((x0 + i + d, y0 + i), (x0 + n - 1 - i + d, y0 + i)):
                    if 0 <= y < len(p) and 0 <= x < len(p[0]):
                        p[y][x] = farbe

    def kasten(p, x0, y0, b, h, farbe=SCHWARZ):
        for x in range(x0, x0 + b):
            p[y0][x] = p[y0 + h - 1][x] = farbe
        for y in range(y0, y0 + h):
            p[y][x0] = p[y][x0 + b - 1] = farbe

    tm, ixg, xg, sw = pb.tinte_maske, pb.ist_x_glyphe, pb.x_glyphen, pb.schliess_x_wahl
    p = bild(160, 60)
    kreuz(p, 140, 20, 7)
    m = tm(p)
    check(sum(map(sum, m)) == 13 and m[20][140] and not m[0][0], f"Tinte = nur das × (13 px), Hintergrund je Pixelzeile ({sum(map(sum, m))})")
    g = xg(m)
    check(len(g) == 1 and (g[0]["x"], g[0]["y"], g[0]["b"], g[0]["h"], g[0]["cx"], g[0]["cy"]) == (140, 20, 7, 7, 143, 23), f"7×7-× gefunden, Mitte 143/23 ({g})")
    p2 = bild(160, 60)
    kreuz(p2, 100, 10, 10, SCHWARZ, dick=2)                                   # dickes, kantengeglättetes ×
    kasten(p2, 20, 10, 8, 8)                                                  # Kästchen
    for i in range(9):                                                        # Plus
        p2[30][60 + i] = p2[26 + i][64] = SCHWARZ
    kasten(p2, 120, 30, 6, 9)                                                 # „0" (hoch, Kanten voll)
    for i in range(5):                                                        # „8" grob: zwei Kästchen übereinander
        p2[45][20 + i] = p2[49][20 + i] = p2[53][20 + i] = SCHWARZ
    for y in range(45, 54):
        p2[y][20] = p2[y][24] = SCHWARZ
    g2 = xg(tm(p2))
    check([(x["x"], x["y"]) for x in g2] == [(100, 10)], f"nur das dicke × zählt — nicht Kästchen, Plus, 0, 8 ({[(x['x'], x['y']) for x in g2]})")
    pk = bild(160, 60)
    kreuz(pk, 150, 20, 3)
    check(xg(tm(pk)) == [], "zu kleines × (3 px) → kein ×")
    check(ixg({(0, 0), (6, 6)}, 0, 0, 7, 7) is False, "zu wenig Tinte → kein ×")
    # Markierte Zeile (blau hinterlegt, weißes ×): der Hintergrund kommt je Pixelzeile, das × bleibt erkennbar
    p3 = bild(160, 60)
    for y in range(16, 32):
        p3[y] = [BLAU] * 160
    kreuz(p3, 138, 20, 8, WEISS)
    for x in range(10, 60):                                                   # Text links in derselben Zeile
        p3[22][x] = WEISS
    g3 = xg(tm(p3))
    check(len(g3) == 1 and g3[0]["x"] == 138, f"markierte Zeile: weißes × auf Blau gefunden ({g3})")
    # Wahl: nur am rechten Rand, genau eine Zeile, in der Ticket-Zeile
    ga = {"x": 140, "y": 20, "b": 7, "h": 7, "cx": 143, "cy": 23}
    gsl = {"x": 30, "y": 20, "b": 7, "h": 7, "cx": 33, "cy": 23}             # × neben S/L — weit links
    gb = {"x": 141, "y": 40, "b": 7, "h": 7, "cx": 144, "cy": 43}             # zweite Zeile (Order/Position)
    w1, n1, _ = sw([gsl, ga], 160, 23)
    check(w1 == ga and n1 == 1, "S/L-× links + Profit-× rechts → das rechte, in der Ticket-Zeile")
    check(sw([gsl], 160, 23)[0] is None, "nur ein × weit links (S/L/T/P) → kein Beweis")
    w2, n2, gr2 = sw([ga, gb], 160, 23)
    check(w2 is None and n2 == 2 and "nicht eindeutig" in gr2, "zwei Zeilen mit × → nicht eindeutig, kein Beweis")
    w3, _, gr3 = sw([ga], 160, 43)
    check(w3 is None and "neben der Ticket-Zeile" in gr3, f"× in anderer Zeile als der Anker → kein Beweis ({gr3})")
    check(sw([ga], 160, None)[0] == ga, "ohne Anker-Zeile (nur Maus-Test-Ansicht) → das eine ×")
    check(sw([], 160, 23)[0] is None and pb.maske_ascii(m, 139, 20, 9, 2) == [".#.....#.", "..#...#.."], "leer → None; ASCII-Ausschnitt fürs Log")
    # Klick-Freigabe auf dem Bild-Weg
    bw = {"punkt": (900, 600), "n_x": 1}
    check(xk(None, "", True, bw) is (not pb.BILD_TOOLTIP_PFLICHT), "Bild-Beweis ohne Tooltip → Klick nach BILD_TOOLTIP_PFLICHT")
    check(xk(None, "Close position", True, bw) is True and xk(None, "Take Profit", True, bw) is False, "Close-Tooltip ja; fremder Tooltip = Gegenbeweis")
    check(xk(None, "", False, bw) is False and xk(None, "", True, {"punkt": (1, 1), "n_x": 2}) is False and xk(None, "", True, {"n_x": 1}) is False,
          "mehrere Positionen / zwei × / ohne Punkt → kein Klick")
    check(xk(None, "", True, dict(bw, ohne_zeile=True)) is False, "Maus-Test ohne Ticket-Anker → nie bewiesen")
    check(xk([760, 700, 140, 18], "", True, bw) is False, "Zellen-Weg bleibt bei Tooltip-Pflicht, auch wenn ein Bild da ist")
    srcW = open(os.path.join(STAMM, "mt5-copier", "polar_bot.py"), encoding="utf-8").read()
    wa = srcW[srcW.index("def slave_wache("):srcW.index("# ── MAUS-TEST ×")]
    check("x_klick_erlaubt(zelle, x_tip, einzig, bild)" in wa and "x_klick_erlaubt(z, tip, True, bd)" in wa, "Wache: Parken und Klick prüfen mit dem Bild-Beweis")
    blick = wa[wa.index("if park and jetzt >= naechst_blick:"):wa.index("time.sleep(0.004)")]
    check(blick.count("parken_mit_beweis()") == 1 and "!= fenster" in blick and "slave_x_punkte(" not in blick,
          "Wache liest Zeile/× nur nach Fensterbewegung neu (nie alle 0,5 s unter der parkenden Maus)")
    check('"x_art":' in wa and '"tooltip":' in wa, "geparkt meldet x, x_art, tooltip, beweis (Live-Anzeige)")
    tx = srcW[srcW.index("def lauf_test_x("):srcW.index("# ── Start")]
    sl = tx[tx.index("einzig = len(lese[\"positionen\"]) == 1"):]
    check('res["ok"] = bool(park)' in sl and 'res["msg"] = ' in sl, "Maus-Test Slave setzt ok/msg in jedem Zweig (vorher KeyError beim Zellen-Treffer)")
    check("_kontextmenue_close_lesen(" in sl and "_kontextmenue_close_klicken" not in sl and 'taste="rechts"' in sl and "{ESC}" in sl,
          "Maus-Test belegt den Rechtsklick nur lesend (Menü lesen, Esc, nie auslösen)")
    check(sl.count("_klick_absolut(") == 1, "Maus-Test: einziger Klick ist der Rechtsklick fürs Menü — nie aufs ×")
    print('10b2) Lage-Wache des Bild-Beweises + Lesefehler ist nie „zu“ (Prüfung 21.10.2026)')
    bg = pb.bild_noch_gueltig
    bd = {"hwnd": 4242, "liste": [10, 600, 900, 800], "punkt": (886, 650), "n_x": 1}
    check(bg(bd, True, [10, 600, 900, 800], 4242) == (True, "Lage unverändert"), "Liste sichtbar, Rechteck gleich, unter dem × die Liste → gültig")
    check(bg(bd, False, [10, 600, 900, 800], 4242)[0] is False, "Liste unsichtbar (Reiter gewechselt/zu) → ungültig")
    check(bg(bd, True, [10, 560, 900, 800], 4242)[0] is False and "verändert" in bg(bd, True, [10, 560, 900, 800], 4242)[1], "Toolbox höher gezogen → ungültig")
    check(bg(bd, True, None, 4242)[0] is False, "Rechteck nicht lesbar → ungültig")
    check(bg(bd, True, [10, 600, 900, 800], 777)[0] is False and "anderes Fenster" in bg(bd, True, [10, 600, 900, 800], 777)[1],
          "F9-Dialog/Toast/Browser über dem × → ungültig")
    check(bg({"liste": [1, 2, 3, 4]}, True, [1, 2, 3, 4], 0)[0] is False and bg(None, True, None, 0)[0] is False, "ohne hwnd/Bild → ungültig")
    pz = pb.position_zu_bewiesen
    check(pz(None, 5) is False, "API-Fehler (None) nach dem ×-Klick → NICHT zu (Rückfall läuft)")
    check(pz({"positionen": [{"ticket": 5}]}, 5) is False and pz({"positionen": [{"ticket": 6}]}, 5) is True and pz({"positionen": []}, 5) is True,
          "zu nur aus gelungener Lesung ohne das Ticket")
    check(pz({"fehler": "x"}, 5) is False and pz({"positionen": None}, 5) is False, "Fehler-Antwort / Positionen fehlen → nicht zu")
    srcL = open(os.path.join(STAMM, "mt5-copier", "polar_bot.py"), encoding="utf-8").read()
    wl = srcL[srcL.index("def slave_wache("):srcL.index("# ── MAUS-TEST ×")]
    nach = wl[wl.index("stop.set()\n    if signal[\"da\"]"):]
    check("offen(lesen())" not in wl and nach.count("zu_bewiesen(lesen())") == 6, f"alle sechs Stellen nach dem Signal prüfen zu_bewiesen ({nach.count('zu_bewiesen(lesen())')})")
    check(nach.index("bild_pruefen(bild, punkt_x)") < nach.index("ob._klick_absolut(punkt_x[0], punkt_x[1])") and "punkt_x and lage_ok and x_klick_erlaubt(" in nach,
          "Lage-Wache direkt vor dem ×-Klick")
    blk = wl[wl.index("if park and jetzt >= naechst_blick:"):wl.index("time.sleep(0.004)")]
    check("bild_pruefen(bild, punkt_x)" in blk and "x_ruht, punkt_x" in blk and "tuple(neu_b[\"punkt\"]) == tuple(x_ruht)" in blk,
          "Lage-Wache alle 0,5 s; × ruht bei Abweichung, zurück nur mit frischem Foto am selben Punkt")
    sb = srcL[srcL.index("def slave_x_bild("):srcL.index("def _kontextmenue_close_lesen(")]
    check('"hwnd": lf["hwnd"]' in sb and "bild_pruefen(out, out[\"punkt\"])" in sb, "Bild-Beweis speichert hwnd und prüft schon beim Foto, dass nichts über dem × liegt")
    print("10c) Airbag: Slave-SL/TP aus beiden Fills + Master-Liquidation, Puffer fest 2,5 % (Finn 21.10.2026)")
    lv, sp = A["liq_vorgabe"], A["slave_pkt_aus_master"]
    check(A["POLAR_PUFFER_PCT"] == 2.5, "EINE Konstante POLAR_PUFFER_PCT = 2,5 (nur in polar_app)")
    check(sp(21, 29) == (21.52, 28.27) and sp(None, 29) == (None, None) and sp(21, 0) == (None, None),
          f"Plan: Slave-SL = Master-TP × 1,025, Slave-TP = Master-SL × 0,975 ({sp(21, 29)}); ohne Master-Abstand nichts")
    v = lv(150000, "konto_balance", 148000, "Boden", 20, 1, 21)
    check(v["ok"] and v["abstand_usd"] == 2000 and v["abstand_pkt"] == 100 and v["puffer_pct"] == 2.5 and v["master_tp_pkt"] == 21,
          f"150.000 → Liq 148.000, NQ 1 Kontrakt: 2.000 $ = 100 Pkt, Puffer 2,5 % ({v})")
    check(lv(150000, "x", 149000, "", 2, 5, 21)["abstand_pkt"] == 100, "MNQ 5 Kontrakte: 1.000 $ / (2 × 5) = 100 Pkt")
    check(not lv(None, None, 148000, "", 20, 1, 21)["ok"] and "Start-Balance" in lv(None, None, 148000, "", 20, 1, 21)["grund"], "ohne Start-Balance → kein Airbag")
    check(not lv(150000, "x", None, "kein Max-Drawdown", 20, 1, 21)["ok"], "ohne Liquidation → kein Airbag (Grund nennt die Regel)")
    check(not lv(150000, "x", 150500, "", 20, 1, 21)["ok"] and not lv(150000, "x", 148000, "", None, 1, 21)["ok"], "Balance unter Liq / ohne Punktwert → nein")
    srcA0 = open(os.path.join(STAMM, "polar_app.py"), encoding="utf-8").read()
    check("puffer_pkt" not in srcA0 and 'd.get("polar_pct")' not in srcA0, "Railway rechnet nirgends mehr mit Pkt-Puffer aus dem Popup")
    al = pb.airbag_level
    liq = {"ok": True, "abstand_pkt": 100, "puffer_pct": 2.5, "master_tp_pkt": 21, "liq_balance": 148000}
    a = al("sell", 29678.45, 30000.0, 30040.0, None, liq)
    check(a["ok"] and a["master_liq"] == 29900 and a["master_stop_art"] == "liq" and a["sl"] == 29719.45 and a["tp"] == 29580.95,
          f"Master BUY ohne SL: Liq 29.900, Slave SELL SL = Fill + 40 × 1,025, TP = Fill − 100 × 0,975 ({a.get('sl')} / {a.get('tp')})")
    check(a["master_tp_quelle"] == "tradingview" and a["abstand_tp_pkt"] == 40 and a["slave_tp_pkt"] == 97.5 and a["slave_sl_pkt"] == 41, "echter Master-TP aus TradingView, nicht der Plan")
    b = al("sell", 29678.45, 30000.0, 30040.0, 29960.0, liq)
    check(b["master_stop_art"] == "sl" and b["tp"] == 29639.45, f"echter Master-SL näher als die Liq → Airbag 40 × 0,975 davor ({b.get('tp')})")
    check(al("sell", 29678.45, 30000.0, 30040.0, 29850.0, liq)["master_stop_art"] == "liq", "Master-SL hinter der Liq zählt nicht")
    check(al("sell", 29678.45, 30000.0, 30040.0, 30010.0, liq)["master_stop_art"] == "liq", "Master-SL auf der Gewinnseite (unsinnig) zählt nicht")
    c = al("sell", 29678.45, 30000.0, None, None, liq)
    check(c["master_tp_quelle"] == "plan" and c["sl"] == 29699.98, f"ohne gemeldeten Master-TP: Plan-Abstand 21 × 1,025 ({c.get('sl')})")
    d = al("buy", 29678.45, 30000.0, 29960.0, None, liq)
    check(d["master_liq"] == 30100 and d["sl"] == 29637.45 and d["tp"] == 29775.95, f"gespiegelt: Master SELL, Slave BUY ({d.get('sl')} / {d.get('tp')})")
    check(al("buy", 29678.45, 30000.0, 30040.0, None, liq)["master_tp_quelle"] == "plan", "Master-TP auf der falschen Seite → Plan-Abstand")
    check(not al("sell", 29678.45, 30000.0, 30040.0, None, {"ok": False, "grund": "x"})["ok"] and not al("sell", 29678.45, 30000.0, 30040.0, None, None)["ok"],
          "ohne master.liq → kein Airbag (Slave bleibt bei den Plan-Abständen)")
    check(not al("sell", 29678.45, 30000.0, 30040.0, None, dict(liq, puffer_pct=None))["ok"], "ohne puffer_pct von Railway → kein Airbag (keine zweite Konstante im Bot)")
    check(not al("sell", 0, 30000.0, 30040.0, None, liq)["ok"] and not al("hold", 1, 1, 2, None, liq)["ok"], "Fill 0 / Richtung unbekannt → nein")
    srcS = open(os.path.join(STAMM, "mt5-copier", "polar_bot.py"), encoding="utf-8").read()
    ls = srcS[srcS.index("def lauf_slave(cmd):"):srcS.index("def uia_zeilen_lesen(")]
    check(ls.index("airbag_holen(") < ls.index("ob._sltp_klicken(") and ls.index("Notfall-SL/TP nicht setzbar") < ls.index("airbag_holen("),
          "Slave: Notfall-Level im F9 zuerst, Airbag nach dem Fill, dann Rechtsklick → Ändern (_sltp_klicken)")
    check("level_vom_fill(richtung, fill, sl_pkt, tp_pkt, digits)" in ls and '"quelle": "airbag" if ab.get("ok") else ("notfall" if ab.get("abbruch") else "plan")' in ls,
          "ohne Airbag die Plan-Abstände vom eigenen Fill; level meldet quelle")
    srcA = open(os.path.join(STAMM, "polar_app.py"), encoding="utf-8").read()
    ps = srcA[srcA.index("def polar_start():"):srcA.index("def polar_bereit():")]
    check("liq = _master_liq(plan, auftrag)" in ps and ps.count('"liq": liq') == 2, "Start rechnet die Master-Liq und legt sie unter master.liq ab (DB + Prozess)")
    check('slave_pkt_aus_master(auftrag.get("master_tp_pkt"), auftrag.get("master_sl_pkt"))' in ps and '"sl_pkt": s_sl or auftrag.get("sl_pkt")' in ps,
          "Start: alte Pläne bekommen den festen Puffer, ohne Master-Abstände die gespeicherten Werte")
    pp = srcA[srcA.index("def polar_plan():"):srcA.index("def polar_start():")]
    check('slave_pkt_aus_master(d.get("master_tp_pkt"), d.get("master_sl_pkt"))' in pp and '"polar_pct": 100 + POLAR_PUFFER_PCT' in pp, "Plan speichern rechnet sl_pkt/tp_pkt selbst (Popup-Feld fällt weg)")
    ml = srcA[srcA.index("def _master_liq("):srcA.index("def _vp_zeile(")]
    check('A["liq_regel_felder"]' in ml and 'A["liq_peak"]' in ml and 'A["liq_tagesstart"]' in ml and 'A["wd_start_balance"]' in ml,
          "Master-Liq mit denselben Helfern wie der Radar (liq_regel_felder, Peak, Tagesstart, Start-Balance)")
    print("10d) Master: „Close position“-Rückfrage nach dem × + Level aus dem Orders-Reiter (Finn 21.10.2026)")
    cm = pb.close_modal_wahl
    knz, kna = {"text": "Close position", "rect": [900, 500, 120, 32], "dn": "submit-button"}, {"text": "Cancel", "rect": [780, 500, 100, 32], "dn": ""}
    mod = {"titel": "Close position", "text": "Close position CME_MINI:MNQZ2026 · Long 1 @ 29,983.00 Cancel Close position", "knoepfe": [kna, knz]}
    k, g = cm([mod], "MNQ", "buy", 1)
    check(k is knz and g == "passt", "Modal passt (Symbol, Long, Menge 1) → genau der Knopf „Close position“, nie Cancel")
    check(cm([], "MNQ", "buy", 1) == (None, "kein_modal") and cm(None, "MNQ", "buy", 1) == (None, "kein_modal"), "kein Modal → nichts (schon zu)")
    k2, g2 = cm([dict(mod, text="Close position CME_MINI:NQZ2026 · Long 1 @ 29,983.00 Cancel Close position")], "MNQ", "buy", 1)
    check(k2 is None and "NQ" in g2, f"Modal mit anderem Symbol → kein Klick ({g2})")
    check(cm([mod], "MNQ", "sell", 1)[0] is None and "Long statt Short" in cm([mod], "MNQ", "sell", 1)[1], "Richtung passt nicht → kein Klick")
    check(cm([mod], "MNQ", "buy", 2)[0] is None and "Menge" in cm([mod], "MNQ", "buy", 2)[1], "Menge passt nicht → kein Klick")
    check(cm([dict(mod, text="Close position CME_MINI:MNQZ2026 · Short 3 @ 29,983.00")], "MNQ", "sell", 3)[0] is knz, "Short 3 → sell 3 passt")
    check(cm([mod, dict(mod)], "MNQ", "buy", 1)[0] is None, "zwei Close-Modals → nicht eindeutig, kein Klick")
    zeile_tab = {"titel": "", "text": "MNQZ2026 Long 1 29,983.00 Close position", "knoepfe": [knz]}
    check(cm([zeile_tab, mod], "MNQ", "buy", 1)[0] is knz and cm([zeile_tab], "MNQ", "buy", 1) == (None, "kein_modal"),
          "„Close position“ in der Positions-Tabelle (ohne Cancel) zählt nicht als Modal")
    check(cm([dict(mod, knoepfe=[kna])], "MNQ", "buy", 1)[0] is None and cm([dict(mod, knoepfe=[kna, knz, dict(knz)])], "MNQ", "buy", 1)[0] is None,
          "kein / zwei Knöpfe „Close position“ → kein Klick")
    check(cm([dict(mod, text="Close position Cancel Close position")], "MNQ", "buy", 1)[0] is None, "Modal ohne Symbol → kein Klick")
    oa = pb.order_zeile_arbeitet
    check(oa({"spalten": {"Status": "Working"}}) and oa({"spalten": {}}) and not oa({"spalten": {"Status": "Filled"}}) and not oa({"spalten": {"Status": "Cancelled"}}),
          "Orders-Reiter: nur aktive Orders (Working/ohne Status), nie Filled/Cancelled früherer Läufe")
    srcM = open(os.path.join(STAMM, "mt5-copier", "polar_bot.py"), encoding="utf-8").read()
    mx = srcM[srcM.index("def master_x_klicken("):srcM.index("def master_wache(")]
    fb = mx[mx.index("def flach_beweis("):mx.index("weg, dialog = (None, False)")]
    check("time.time() - t0 > 0.6" not in fb and "close_modal_wahl(s.lese_js(CLOSE_MODAL_JS" in fb and "submit-button" not in fb,
          "Modal ab dem ersten Takt (~50 ms), alter 0,6-s-Weg über submit-button ist raus")
    check('"tabu": r"cancel|abbrechen|reverse|umkehr"' in fb and "pruef=" in fb, "Klick nur mit Ziel-Beweis am Punkt, Cancel/Umkehr tabu")
    ml = srcM[srcM.index("def master_level_lesen("):srcM.index("def master_druck(")]
    check("s.klick(" not in ml and "feld_setzen" not in ml and "taste(" not in ml and '_cdp_reiter(s, "positions"' in ml,
          "Level aus dem Orders-Reiter nur lesen, danach zurück auf Positionen")
    lm2 = srcM[srcM.index("def lauf_master(cmd):"):srcM.index("def lauf_slave(cmd):")]
    check(lm2.index("master_level_lesen(") < lm2.index('melden(lauf, "level"'), "Master liest fehlende Level VOR der level-Meldung (der Slave rechnet daraus)")
    print("10e) „zu“ erst nach zwei Lesungen · Start-Balance nach Polar frisch · Airbag-Abbruch bei Master-zu (Prüfung 21.10.2026)")
    zd = pb.zu_doppelt
    schlaf = []
    leer, mit = {"positionen": []}, {"positionen": [{"ticket": 5}]}
    check(zd(lambda: mit, leer, 5, schlaf=schlaf.append) is False and schlaf == [0.15],
          "leere Liste (positions_get-Fehler), zweite Lesung zeigt das Ticket → NICHT zu (150 ms später geprüft)")
    check(zd(lambda: leer, leer, 5, schlaf=lambda _x: None) is True, "zwei Lesungen ohne Ticket → zu")
    check(zd(lambda: None, leer, 5, schlaf=lambda _x: None) is False and zd(lambda: leer, None, 5, schlaf=lambda _x: None) is False,
          "Lesefehler in einer der beiden Lesungen → nicht zu")
    schlaf2 = []
    check(zd(lambda: leer, mit, 5, schlaf=schlaf2.append) is False and schlaf2 == [], "Ticket noch da → sofort nicht zu, ohne Wartezeit")
    srcZ = open(os.path.join(STAMM, "mt5-copier", "polar_bot.py"), encoding="utf-8").read()
    wz = srcZ[srcZ.index("def slave_wache("):srcZ.index("# ── MAUS-TEST ×")]
    check("return zu_doppelt(lesen, st, ticket)" in wz and "if zu_bewiesen(st):" in wz and "if zu_bewiesen(st_v):" in wz and "not offen(" not in wz,
          "Wache (broker-zu), schon_zu, ×-/Rechtsklick-Beweis und End-zu laufen alle über die Doppel-Lesung")
    eb = A["ende_und_balance_zeit"]
    e1, b1 = eb({"master_zu_ms": 1792541100000, "slave_zu_ms": 1792541099000}, 1792541110.4)
    check(e1 == "2026-10-21T00:05:00Z" and b1 == "2026-10-21T00:05:10Z" and b1 > e1, f"ended_at = spätere zu-Meldung, Balance-Zeit danach ({e1} < {b1})")
    e2, b2 = eb({"master_zu_ms": 1792541110000}, 1792541110.2)
    check(e2 < b2, f"zu in derselben Sekunde wie die Abrechnung → ended_at 1 s davor ({e2} < {b2})")
    e3, b3 = eb({}, 1792541110.0)
    check(e3 < b3, "ohne zu-Zeiten → ended_at 1 s vor der Abrechnung")
    srcAb = open(os.path.join(STAMM, "polar_app.py"), encoding="utf-8").read()
    ab_ = srcAb[srcAb.index("def _abrechnen(z):"):srcAb.index("def laeufe_aus_plaenen(")]
    check('patch["final"] = {"balance_end": erg["master_balance_end"]' in ab_ and 'upd = {"ended_at": ende_iso}' in ab_ and '"tv_balance_at": jetzt' in ab_,
          "Abrechnung schreibt final.balance_end und tv_balance_at nach ended_at → nächster Lauf hat eine frische Start-Balance")
    ah = srcZ[srcZ.index("def airbag_holen("):srcZ.index("def reader_flach(")]
    check(ah.index('a.get("master_zu_ms")') < ah.index('m.get("liq")') and '"abbruch": True' in ah, "airbag_holen bricht bei Master-zu/Fehler sofort ab")
    ls2 = srcZ[srcZ.index("def lauf_slave(cmd):"):srcZ.index("def uia_zeilen_lesen(")]
    check('if not bestaetigt and not ab.get("abbruch"):' in ls2 and "sl, tp = sl_g, tp_g" in ls2, "Abbruch → kein Ändern-Dialog, Notfall-Level, sofort Wache")
    print("10f) Orders-Reiter: Rückkehr bewiesen, CDP-Flach nur bei sichtbarem Positions-Reiter, „Inactive“ nie aktiv (Prüfung 21.10.2026)")
    oa2 = pb.order_zeile_arbeitet
    check(not oa2({"spalten": {"Status": "Inactive"}}) and not oa2({"spalten": {"Status": "Inaktiv"}}) and oa2({"spalten": {"Status": "Active"}})
          and oa2({"spalten": {"Status": "Aktiv"}}), "Inactive/Inaktiv → nicht aktiv; Active/Aktiv → aktiv")
    srcF = open(os.path.join(STAMM, "mt5-copier", "polar_bot.py"), encoding="utf-8").read()
    mw = srcF[srcF.index("def master_wache("):]
    cdp = mw[mw.index("if time.time() >= naechst_cdp:"):mw.index("time.sleep(0.05)")]
    check(cdp.index("positions_sichtbar(s)") < cdp.index('melden(lauf, "zu", {"quelle": "cdp"') and "continue" not in cdp
          and "st2 is not None and positions_sichtbar(s)" in cdp, "CDP-Flach nur mit sichtbarem Positions-Reiter (vor und nach dem zweiten Blick)")
    mlv = srcF[srcF.index("def master_level_lesen("):srcF.index("def positions_sichtbar(")]
    check('zurueck = bool(ob._cdp_reiter(s, "positions"' in mlv and "Rückkehr auf Positionen NICHT bewiesen" in mlv, "Level-Lesung loggt, ob die Rückkehr auf Positionen gelang")
    # READER-PFLICHT VOR DEM KLICK (21.10.2026, Prüfer S2): reader_bereit — nur ein antwortender, sehender, frischer Reader lässt den Master laufen
    rb = pb.reader_bereit
    check(rb({"an": True, "positionen_ok": True, "positionen_alter_s": 0.4})[0] is True, "Reader an, Positionen 0,4 s → bereit")
    check(rb(None) == (False, "Reader (Port 8790) antwortet nicht — Tampermonkey-Reader im Puls-Chrome an?"), "keine Antwort → Abbruch mit Grund")
    check(rb({"an": False})[0] is False and rb({"an": True, "blind": True, "positionen_ok": True})[0] is False
          and rb({"an": True, "positionen_ok": False})[0] is False, "aus / blind / ohne Positionen → nicht bereit")
    check(rb({"an": True, "positionen_ok": True, "positionen_alter_s": 7})[0] is False and "7.0 s alt" in rb({"an": True, "positionen_ok": True, "positionen_alter_s": 7})[1],
          "Stand älter als 5 s → nicht bereit, nennt das Alter")
    srcB = open(os.path.join(STAMM, "mt5-copier", "polar_bot.py"), encoding="utf-8").read()
    lm = srcB[srcB.index("def lauf_master(cmd):"):srcB.index("def lauf_slave(cmd):")]
    check(0 < lm.index("reader_bereit(ob._tv_http(\"/positions\"") < lm.index("bereit_und_warten("), "Reader-Pflicht vor bereit/Feuer im Master-Lauf (Abbruch-Pfad: nichts gesendet)")
    # LIVE-ABLAUF (Finn 20.10.2026 ~23:55 Dubai: „wird geöffnet, platziert, bereit zum Drücken — die ganzen Steps dahin schreiben"):
    # schritt_text je Phase (ohne Kontonummern/Logins), Sender nie blockierend
    st = pb.schritt_text
    cm = {"richtung": "buy", "volumen": 1, "symbol": "MNQZ26", "ext_id": "GEHEIM123", "login": "9999"}
    check(st("master", "bereit", {}, cm) == "BUY 1 MNQZ26 steht vor dem Klick — wartet auf die Feuerzeit", "bereit: Richtung, Menge, Symbol")
    check(st("slave", "vorbereiten", {}, {}) == "MT5 öffnen, Ticket vorbereiten" and st("master", "vorbereiten", {}, cm).startswith("Puls-Chrome"), "vorbereiten je Seite")
    check(st("slave", "gefuellt", {"fill": 30801.5}, {}) == "gefüllt 30.801,50", "gefüllt mit deutschem Preis")
    check(st("slave", "level", {"sl": 29900, "tp": 31000, "level_ok": False}, {}).endswith("nicht bestätigt, von Hand prüfen"), "Level nicht bestätigt sagt es")
    check(st("master", "level", {"level": {"sl_soll": 29900.25, "tp_soll": 31000}}, {}) == "SL/TP gesetzt 29.900,25 / 31.000,00", "Master-Level aus sl_soll/tp_soll")
    check(st("master", "fehler", {"msg": "Fenster weg"}, {}) == "fehler: Fenster weg" and st("x", "neu_phase", {}, {}) == "neu_phase", "Fehler mit Grund, unbekannte Phase = Name")
    check(all("GEHEIM123" not in st("master", ph, {}, cm) and "9999" not in st("master", ph, {}, cm) for ph in
              ("vorbereiten", "bereit", "geklickt", "gefuellt", "level", "wache", "ende")), "nie Konto-Kennung/Login im Schritt-Text")
    class _L:   # Lauf-Attrappe: Sender darf nie warten
        test, lauf_id, token, seite = None, "l-1", "t", "master"
        import queue as _q
        _schritte = _q.Queue(maxsize=2)
        _sender = object()   # Sender gilt als gestartet
    lauf = _L()
    import time as _t
    t0 = _t.time()
    for i in range(10):
        pb.Lauf.schritt(lauf, "p", "x", i)
    check(_t.time() - t0 < 0.05 and lauf._schritte.qsize() == 2, "Sender-Queue voll → Schritt verworfen, nichts wartet")
    lauf2 = _L(); lauf2.token = None; lauf2._schritte = _L._q.Queue(maxsize=5)
    pb.Lauf.schritt(lauf2, "p", "x", 1)
    check(lauf2._schritte.qsize() == 0, "ohne Schlüssel (oder Maus-Test) wird nichts gemeldet")
    src = open(os.path.join(STAMM, "mt5-copier", "polar_bot.py"), encoding="utf-8").read()
    ph = src[src.index("    def phase(self, name, **felder):"):src.index("    def schritt(self, name, text, at_ms=None):")]
    check("self.schritt(name, schritt_text(" in ph and 'railway(lauf, "POST", "/polar/schritt", d, timeout=SCHRITT_TIMEOUT_S)' in src
          and pb.SCHRITT_TIMEOUT_S <= 5, "jede Phase meldet einen Schritt, Call im eigenen Thread mit kurzem Timeout")
    sd = src[src.index("def _schritt_sender(lauf):"):src.index("def schritte_abwarten(")]
    check("lauf._schritte.get(timeout" not in sd and "lauf._schritte.get()" in sd and "task_done()" in sd, "Sender ohne Ruhe-Timeout (stirbt nicht in der stundenlangen Wache), task_done je Schritt")
    import queue as _qq, threading as _th
    class _L2:
        _schritte = _qq.Queue()
    l2 = _L2(); l2._schritte.put({"x": 1})
    pb._SCHRITT_LAEUFE.append(l2)
    t0 = _t.time(); pb.schritte_abwarten(0.4); dt = _t.time() - t0
    check(0.35 <= dt < 1.0, f"Abwarten am Lauf-Ende hört nach max_s auf, auch wenn nichts gesendet wird ({dt:.2f} s)")
    l2._schritte.get(); l2._schritte.task_done()
    t0 = _t.time(); pb.schritte_abwarten(3); dt = _t.time() - t0
    check(dt < 0.3, f"leere Queue → kein Warten ({dt:.2f} s)")
    pb._SCHRITT_LAEUFE.remove(l2)
    check("schritte_abwarten()" in src[src.index("def main():"):], "main wartet nach dem Lauf auf die letzten Schritte")
    print()
    if FEHLER:
        print(f"FEHLER: {len(FEHLER)}")
        return 1
    print("OK — alle Prüfungen bestanden")
    return 0


if __name__ == "__main__":
    sys.exit(main())
