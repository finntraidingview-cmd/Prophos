#!/usr/bin/env python3
"""Selbsttest fuer reader-server.py — rein rechnende Teile (24.09.2026, Kurs-Feed 0.7.0; 25.09.2026 Versions-Felder 0.8.1).

Aufruf:  python3 selftest_reader.py
Prueft ohne Netz und ohne Browser: Zahl- und Wurzel-Parser, Minutenkerzen,
Uebernahme des 'kurse'-Payloads (beide Symbole, Mitte aus Bid/Ask, Kerzen nur aus
sichtbarem Tab) und die Stale-Ausgabe (Userscript-Urteil ODER Alter > 45 s)."""
import importlib.util
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))


def lade():
    spec = importlib.util.spec_from_file_location("rs", os.path.join(HIER, "reader-server.py"))
    rs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rs)
    return rs


def main():
    rs = lade()
    ok = True
    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    check(rs._kurs_zahl("30,448.25") == 30448.25 and rs._kurs_zahl("29.491,75") == 29491.75
          and rs._kurs_zahl("30,448") == 30448 and rs._kurs_zahl("−1,234.50") == -1234.5 and rs._kurs_zahl("abc") is None,
          "Zahl-Parser: beide Trenner, Tausendergruppe, U+2212, Unsinn = None")
    check(rs._kurs_wurzel("NQZ2026") == "NQ" and rs._kurs_wurzel("MNQ1!") == "MNQ"
          and rs._kurs_wurzel("CME_MINI:MNQZ2026") == "MNQ" and rs._kurs_wurzel("NQ") == "NQ",
          "Wurzel: Monat, Dauerkontrakt, Boersen-Praefix, nackt")

    k, v = rs._kerze_fortschreiben(None, None, "NQ", "NQZ2026", 100.0, 60 * 1000 + 5)
    k, v = rs._kerze_fortschreiben(k, v, "NQ", "NQZ2026", 103.0, 60 * 1000 + 10)
    k, v = rs._kerze_fortschreiben(k, v, "NQ", "NQZ2026", 99.0, 60 * 1000 + 20)
    k2, v2 = rs._kerze_fortschreiben(k, v, "NQ", "NQZ2026", 101.0, 60 * 1001 + 1)
    check((k["o"], k["h"], k["l"], k["c"], k["n"]) == (100.0, 103.0, 99.0, 99.0, 3) and v is None and v2 is k and k2["o"] == 101.0,
          "Kerze: o/h/l/c/n, Minutenwechsel schiebt nach 'vor'")

    # kurse-Payload (0.7.0): beide Wurzeln, Mitte aus Bid/Ask, Titel-Rueckfall ohne Bid/Ask
    payload = {"NQ": {"bid": "30,738.50", "ask": "30,739.00", "text": "30,738.50", "ts": 1, "quelle": "legende", "stale": False},
               "MNQ": {"bid": "30,739.25", "ask": "30,739.75", "text": "30,739.25", "ts": 1, "quelle": "legende", "stale": True},
               "XYZ": {"bid": "", "ask": "", "text": "", "ts": 1},
               "kaputt": "nix"}
    kurse, k1, kv = rs._kurse_uebernehmen(payload, True, 1000.0, {}, {}, {})
    check(set(kurse) == {"NQ", "MNQ"} and kurse["NQ"]["preis"] == 30738.75 and kurse["MNQ"]["preis"] == 30739.5
          and kurse["NQ"]["bid"] == 30738.5 and kurse["MNQ"]["stale"] is True and kurse["NQ"]["sichtbar"] is True,
          "kurse: beide Wurzeln, Mitte aus Bid/Ask, stale vom Userscript, Unlesbares raus")
    check(set(k1) == {"NQ", "MNQ"} and k1["NQ"]["o"] == 30738.75 and k1["NQ"]["n"] == 1,
          "kurse: Kerzen je Wurzel aus dem sichtbaren Tab")
    kurse2, k1b, kvb = rs._kurse_uebernehmen({"NQ": {"text": "30,740", "ts": 2, "quelle": "titel"}}, False, 1002.0, kurse, k1, kv)
    check(kurse2["NQ"]["preis"] == 30740 and kurse2["NQ"]["quelle"] == "titel" and kurse2["MNQ"]["preis"] == 30739.5
          and k1b["NQ"]["n"] == 1,
          "kurse: Titel-Rueckfall ohne Bid/Ask ersetzt den Kurs, MNQ bleibt stehen, verdeckter Tab schreibt KEINE Kerze")
    aus = rs._kurse_ausgabe(kurse2, 1010.0)
    check(aus["NQ"]["alter_s"] == 8.0 and aus["NQ"]["stale"] is False and aus["MNQ"]["alter_s"] == 10.0 and aus["MNQ"]["stale"] is True
          and "empf_s" not in aus["NQ"],
          "Ausgabe: alter_s je Wurzel, stale vom Userscript bleibt")
    aus2 = rs._kurse_ausgabe(kurse2, 1000.0 + 60)
    check(aus2["NQ"]["stale"] is True, "Ausgabe: Empfang aelter als 45 s → stale, auch ohne Userscript-Urteil")

    # 0.8.0: Bar-Ring aus dem Socket — Testframes der Session „Live-Daten fuer NQ und MNQ" (24.09.2026), sonst konstruiert
    import json, re
    pfad = "/private/tmp/claude-501/-Applications-Prophos/52453f70-d3af-439b-ac22-ac0ba195aecd/scratchpad/tv-frames/tv_frames_2026-09-24.jsonl"
    bars_real = []
    try:
        for zeile in open(pfad, encoding="utf-8"):
            f = json.loads(zeile); i = 0
            while i < len(f):
                m = re.match(r"~m~(\d+)~m~", f[i:i + 24])
                if not m:
                    break
                n = int(m.group(1)); body = f[i + len(m.group(0)):i + len(m.group(0)) + n]; i += len(m.group(0)) + n
                if body.startswith("~h~"):
                    continue
                j = json.loads(body)
                if j.get("m") in ("timescale_update", "du"):
                    for sid, e in (j["p"][1] or {}).items():
                        for b in (e.get("s") or []):
                            v = b["v"]
                            bars_real.append({"wurzel": "NQ", "symbol": "CME_MINI:NQ1!", "aufloesung": "1", "minute": v[0], "o": v[1], "h": v[2], "l": v[3], "c": v[4], "vol": v[5] if len(v) > 5 else None,
                                              "_erst": j.get("m") == "timescale_update"})
    except FileNotFoundError:
        pass
    if bars_real:
        erst = [b for b in bars_real if b["_erst"]]; du = [b for b in bars_real if not b["_erst"]]
        ring, n1, w1 = rs._kerzen_uebernehmen({}, erst, True)
        ring, n2, w2 = rs._kerzen_uebernehmen(ring, du, False)
        liste = rs._kerzen_liste(ring)
        check(n1 == 30 and n2 == 5 and w1 is None and len(ring["NQ"]) == 31 and liste[-1]["minute"] == 1790267700 and liste[-2]["vol"] == 881.0,
              f"Ring aus echten Frames: 30 Bars Erstladung + 5 du auf 2 Minuten → 31 Kerzen, letzte du-Fassung gewinnt (vol 881) [{n1}/{n2}]")
        k1m = rs._kurs_1m_aus_ring(ring)
        check(len(k1m) == 2 and k1m[0]["minute"] == 1790267640 and k1m[1]["minute"] == 1790267700 and k1m[1]["quelle"] == "ws",
              "kurs_1m aus dem Ring = letzte abgeschlossene + laufende Minute")
    else:
        print("· Testframes nicht gefunden — Ring nur konstruiert geprueft")
    ring, n, w = rs._kerzen_uebernehmen({}, [{"wurzel": "MNQ", "symbol": "MNQ1!", "aufloesung": "5", "minute": 60, "o": 1, "h": 2, "l": 0.5, "c": 1.5}], False)
    check(n == 0 and ring == {} and "5 statt 1" in (w or ""), "Aufloesung 5 → verworfen mit Warnung")
    ring, n, w = rs._kerzen_uebernehmen({}, [{"wurzel": "NQ", "symbol": "NQ1!", "aufloesung": "1", "minute": 60 * i, "o": 1, "h": 2, "l": 0.5, "c": 1.5} for i in range(1, 700)], True, maximum=600)
    check(n == 699 and len(ring["NQ"]) == 600 and min(ring["NQ"]) == 60 * 100, "Ring-Deckel 600: aelteste fliegen raus")
    ring, n, w = rs._kerzen_uebernehmen(ring, [{"wurzel": "NQ", "symbol": "NQ1!", "aufloesung": "1", "minute": 60, "o": 9, "h": 9, "l": 9, "c": 9}], True)
    check(len(ring["NQ"]) == 1 and 60 in ring["NQ"], "Erstladung ersetzt den Ring der Wurzel (Serie neu geladen)")
    ring, n, w = rs._kerzen_uebernehmen(ring, [{"wurzel": "MNQ", "symbol": "MNQ1!", "aufloesung": "1", "minute": 120, "o": 1, "h": 1, "l": 1, "c": 1}, "kaputt", {"wurzel": "NQ", "aufloesung": "1", "minute": "x"}], False)
    check(n == 1 and set(ring) == {"NQ", "MNQ"} and rs._kerzen_liste(ring, seit=100) == [ring["MNQ"][120]], "zweite Wurzel, Unsinn ignoriert, seit-Filter")
    kurse, _, _ = rs._kurse_uebernehmen({"NQ": {"lp": 30700.25, "bid": "30,700.00", "ask": "30,700.50", "text": "30700.25", "ts": 1, "quelle": "ws", "lp_time": 1790268000, "modus": "delayed_streaming_600", "delay_s": 600}}, False, 2000.0, {}, {}, {})
    check(kurse["NQ"]["preis"] == 30700.25 and kurse["NQ"]["lp"] == 30700.25 and kurse["NQ"]["modus"] == "delayed_streaming_600" and kurse["NQ"]["delay_s"] == 600,
          "kurse: WS-Quelle nimmt lp als Kurs, Modus/Delay laufen mit, verdeckt egal")

    # 0.8.1: Versions-Felder — reader_version aus der Konstante, script_version aus dem letzten POST-Payload
    check(isinstance(rs.READER_VERSION, str) and rs.READER_VERSION.count(".") == 2, "READER_VERSION gesetzt (x.y.z)")
    v, t = rs._script_merken({"version": " 0.8.0 ", "positionen": []}, 500.0)
    check(v == "0.8.0" and t == 500.0, "_script_merken: Version aus dem Payload, getrimmt")
    rs._script_version, rs._script_s = v, t
    v2, t2 = rs._script_merken({"positionen": []}, 600.0)
    check(v2 == "0.8.0" and t2 == 500.0, "_script_merken: Payload ohne 'version' (Script < 0.4) laesst den letzten Stand stehen")
    v3, t3 = rs._script_merken({"version": 7}, 600.0)
    check(v3 == "0.8.0" and t3 == 500.0, "_script_merken: Unsinn im Feld wird ignoriert")
    aus = rs._versionen(512.0)
    check(aus == {"reader_version": rs.READER_VERSION, "script_version": "0.8.0", "script_alter_s": 12.0},
          "_versionen: reader_version, script_version, script_alter_s")
    rs._script_version, rs._script_s = None, 0.0
    check(rs._versionen(1.0)["script_version"] is None and rs._versionen(1.0)["script_alter_s"] is None,
          "_versionen: nie ein Script gesehen → null, null")
    ganz = rs._mit_an({"ts": 0, "positionen": []})
    check(ganz["reader_version"] == rs.READER_VERSION and "script_version" in ganz and "script_alter_s" in ganz,
          "GET /positions traegt die drei Felder")

    # 0.8.2: Kerzen-Diagnose fuer die Live-Zeile
    d = rs._kerzen_diag({"NQ": {1: {}, 2: {}}, "MNQ": {}}, {"feed": {"du_min": 12, "serien": {"sds_1": {"wurzel": "NQ", "geraten": True, "grund": "Tab-Titel"}, "sds_2": {"wurzel": "MNQ"}}, "unbekannte_serien": 0}}, None, "0.8.1")
    check(d == "Kerzen MNQ 0/NQ 2 · du/min 12 · Serien 2 (1 geraten) · unbek 0 · Aufl ok · Script 0.8.1 · Reader " + rs.READER_VERSION, f"Diagnose: Ring, du/min, Serien mit geraten, Script, Reader [{d}]")
    d = rs._kerzen_diag({"MNQ": {1: {}}}, {"feed": {"du_min": 13, "serien": {"a": {"wurzel": "MNQ"}, "b": {"wurzel": "", "symbol": "CME_MINI:ESZ2026"}, "c": {"wurzel": "", "symbol_id": "sds_sym_3"}}, "unbekannte_serien": 1, "fremd": {"b": {"symbol": "CME_MINI:ESZ2026", "bars": 366}}, "unaufgeloest": {"c": 4}}}, None, "0.8.2")
    check("Serien 3 · unbek 1 · fremd ESZ2026 (unaufgel. 1)" in d, f"Diagnose 0.8.3: fremde Serie mit Symbol, unaufgeloeste gezaehlt [{d}]")
    d = rs._kerzen_diag({}, None, "Chart-Aufloesung 5 statt 1", None)
    check(d.startswith("Kerzen leer · kein feed (Script < 0.8.0?) · Aufl-WARNUNG Chart-Aufloesung 5 statt 1 · Script ?"), f"Diagnose: leer, kein feed, Warnung, Script unbekannt [{d}]")

    # 0.8.4: Tick-Kerzen fuer Wurzeln ohne Chart-Serie (NQ nur in der Watchlist)
    ring, ok1 = rs._tick_kerze_in_ring({}, "NQ", "CME_MINI:NQZ2026", 100.0, 60 * 100 + 5)
    ring, ok2 = rs._tick_kerze_in_ring(ring, "NQ", "CME_MINI:NQZ2026", 103.0, 60 * 100 + 20)
    ring, ok3 = rs._tick_kerze_in_ring(ring, "NQ", "CME_MINI:NQZ2026", 99.0, 60 * 100 + 40)
    ring, ok4 = rs._tick_kerze_in_ring(ring, "NQ", "CME_MINI:NQZ2026", 101.0, 60 * 101 + 1)
    k0, k1 = ring["NQ"][6000], ring["NQ"][6060]
    check(ok1 and ok2 and ok3 and ok4 and (k0["o"], k0["h"], k0["l"], k0["c"], k0["n"], k0["quelle"]) == (100.0, 103.0, 99.0, 99.0, 3, "ws-tick")
          and (k1["o"], k1["n"]) == (101.0, 1) and rs._ring_ist_tick(ring["NQ"]),
          "Tick-Kerze: o/h/l/c/n, Minutenwechsel oeffnet neue Kerze, quelle ws-tick")
    k1m = rs._kurs_1m_aus_ring(ring)
    check(len(k1m) == 2 and k1m[0]["quelle"] == "ws-tick" and k1m[0]["n"] == 3 and k1m[1]["minute"] == 6060,
          "kurs_1m aus Tick-Ring traegt quelle ws-tick + n")
    liste = rs._kerzen_liste(ring)
    check(all(b["quelle"] == "ws-tick" for b in liste), "GET /kerzen: Tick-Bars tragen quelle ws-tick")
    # Serie verdraengt Tick-Kerzen: Ring der Wurzel neu, Serien-Bars mit quelle ws
    ring, n, w = rs._kerzen_uebernehmen(ring, [{"wurzel": "NQ", "symbol": "NQ1!", "aufloesung": "1", "minute": 6120, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "vol": 7}], False)
    check(n == 1 and list(ring["NQ"]) == [6120] and ring["NQ"][6120]["quelle"] == "ws" and not rs._ring_ist_tick(ring["NQ"]),
          "Serie verdraengt Tick-Kerzen (Ring der Wurzel neu), Serien-Bar quelle ws")
    ring2, ok5 = rs._tick_kerze_in_ring(ring, "NQ", "NQ1!", 50.0, 60 * 103)
    check(not ok5 and list(ring2["NQ"]) == [6120], "Wurzel mit Serie bekommt keine Tick-Kerzen mehr")
    ring2, ok6 = rs._tick_kerze_in_ring(ring, "MNQ", "MNQ1!", 50.0, 60 * 103)
    check(ok6 and rs._ring_ist_tick(ring2["MNQ"]) and not rs._ring_ist_tick(ring2["NQ"]), "andere Wurzel ohne Serie bekommt Tick-Kerzen")
    ring3, _ = rs._tick_kerze_in_ring({}, "NQ", "x", "unsinn", 1.0)
    check(ring3 == {} and rs._tick_kerze_in_ring({}, "", "x", 1.0, 1.0)[1] is False, "Tick-Kerze: Unsinn/leer ignoriert")
    d = rs._kerzen_diag(ring2, {"feed": {"du_min": 3, "serien": {}, "unbekannte_serien": 0}}, None, "0.8.2")
    check(d.startswith("Kerzen MNQ 1(tick)/NQ 1 · "), f"Live-Zeile: NQ n / MNQ n(tick) [{d}]")

    # 0.8.5: Beweis-Felder fuer den Master-zu-Waechter
    rs._blind_grund = ""
    st = {"ts": 5000, "positionen": [{"symbol": "MNQZ6", "wurzel": "MNQ", "richtung": "buy", "menge_zahl": 5, "avg_fill": 30486.79, "ts": 4990}],
          "positionen_ts": 4995, "positionen_ok": True, "konto": "PAAPEX6416990000007", "konto_ts": 4900}
    a = rs._mit_an(st)
    check(a["positionen_ok"] is True and a["positionen_ts"] == 4995 and a["konto"] == "PAAPEX6416990000007" and a["konto_ts"] == 4900
          and a["positionen"][0]["avg_fill"] == 30486.79, "Waechter-Felder: positionen_ok/ts, konto/konto_ts, avg_fill durchgereicht")
    rs._blind_grund = "Tab verdeckt"
    b = rs._mit_an(st)
    check(b["positionen_ok"] is False, "Waechter-Felder: blind → positionen_ok false, auch wenn das Script ok meldet")
    rs._blind_grund = ""
    c = rs._mit_an({"ts": 7000, "positionen": []})
    check(c["positionen_ok"] is True and c["positionen_ts"] == 7000 and c["konto"] is None, "Waechter-Felder: altes Script → positionen_ts = ts, konto null")

    # 0.8.6: mehrere Tabs an einem reader-server
    j = 1000.0
    check(rs._rang("feed", "streaming") == 3 and rs._rang("broker", "streaming") == 2 and rs._rang("feed", "delayed_streaming_600") == 1
          and rs._rang("broker", None) == 2, "Rang: Echtzeit vor verzögert, Feed vor Broker")
    q = lambda tab, rolle, modus, s_: {"tab": tab, "rolle": rolle, "modus": modus, "s": s_}
    check(rs._quelle_gewinnt(None, "b", "broker", "streaming", j, 5)
          and not rs._quelle_gewinnt(q("f", "feed", "streaming", j - 1), "b", "broker", "streaming", j, 5)
          and rs._quelle_gewinnt(q("f", "feed", "streaming", j - 6), "b", "broker", "streaming", j, 5)
          and rs._quelle_gewinnt(q("b", "broker", "delayed_streaming_600", j - 1), "f", "feed", "streaming", j, 5)
          and not rs._quelle_gewinnt(q("f", "feed", "streaming", j - 1), "b", "broker", "delayed_streaming_600", j, 5)
          and rs._quelle_gewinnt(q("f", "feed", "streaming", j - 1), "f", "feed", "delayed_streaming_600", j, 5),
          "Quelle: frischer Feed hält Broker ab, still > 5 s → Broker darf, verzögert verliert, gleicher Tab immer")
    tabs = {"f": {"rolle": "feed", "last_s": j, "stand_s": 0.0},
            "b": {"rolle": "broker", "last_s": j - 2, "stand_s": j - 2, "stand": {"positionen": [{"symbol": "MNQZ6"}], "konto_ts": 5}}}
    check(rs._broker_wahl(tabs, j) == ("b", True), "Feed leer + Broker mit Position → Broker-Stand, frisch")
    check(rs._broker_wahl({"f": tabs["f"]}, j) == (None, False), "nur Feed-Tab → kein Broker, kein Urteil")
    check(rs._broker_wahl(tabs, j + 11) == ("b", False), "Broker-Tab 11 s still → Stand bleibt, aber nicht frisch")
    tabs["b2"] = {"rolle": "broker", "last_s": j, "stand_s": j, "stand": {"positionen": [], "konto_ts": 9}}
    check(rs._broker_wahl(tabs, j)[0] == "b2", "zwei Broker-Tabs → jüngster konto_ts gewinnt")
    bft = {"f": {"rolle": "feed", "bf": {"x": 1}, "bf_s": j, "fokus": False},
           "b": {"rolle": "broker", "bf": {"summary": {"a": 1}}, "bf_s": j - 1, "fokus": False},
           "p": {"rolle": "feed", "bf": {"y": 1}, "bf_s": j - 1, "fokus": True}}
    check(rs._bf_wahl(bft, j) == "p" and rs._bf_wahl(bft, j, broker_zuerst=True) == "b"
          and rs._bf_wahl({"f": bft["f"]}, j) == "f" and rs._bf_wahl({}, j) is None,
          "Bedienfeld: Klicks → Tab mit Fokus, Summary → Broker, sonst der einzige")

    # QuickEdit aus (25.09.2026): Bit-Logik + auf Nicht-Windows kein Eingriff, auf Windows ohne Konsole kein Absturz
    check(rs._quickedit_modus(0x01F7) == 0x01B7 and rs._quickedit_modus(0x0007) == 0x0087 and rs._quickedit_modus(0x00C0) == 0x0080,
          "QuickEdit: 0x0040 raus, 0x0080 rein, übrige Bits bleiben")
    import os as _os
    check(rs.quickedit_aus() is (None if _os.name != "nt" else rs.quickedit_aus()), "QuickEdit: auf Mac/Linux None (kein Eingriff)")
    _alt = rs.os.name
    try:
        rs.os.name = "nt"
        check(rs.quickedit_aus() is False if _alt != "nt" else True, "QuickEdit: 'Windows' ohne Konsole → False statt Absturz")
    finally:
        rs.os.name = _alt

    # 0.8.8: Konsole entlasten — Entprellung und Zeilen-Drossel
    m = {}
    folge = [(0.0, True), (1.0, False), (2.0, True), (2.5, True), (3.1, True), (4.0, True), (5.0, False), (9.0, False), (13.2, False), (14.0, True)]
    gemeldet = [(t_, z) for t_, z in folge if rs._entprellt(m, z, t_)]
    check(gemeldet == [], f"Entprellen: blind nur 2 s stabil (2,0–4,0 s), dann wieder sieht → keine Meldung {gemeldet}")
    m = {}
    ts_ = [i * 0.25 for i in range(0, 200)]                     # 50 s, 4 POSTs/s
    zust = [((i // 2) % 2 == 0) for i in range(200)]              # blind/sieht wechselt alle 0,5 s
    n_meld = sum(1 for t_, z in zip(ts_, zust) if rs._entprellt(m, z, t_))
    check(n_meld == 0, f"Entprellen: Flattern alle 0,5 s über 50 s → 0 Meldungen [{n_meld}]")
    m = {}
    ts_ = [i * 0.25 for i in range(0, 200)]
    n_meld = [t_ for t_ in ts_ if rs._entprellt(m, t_ >= 5.0 and t_ < 30.0, t_)]
    check(n_meld == [8.0, 33.0], f"Entprellen: stabiler Wechsel → gemeldet nach 3 s (8,0 s BLIND, 33,0 s sieht wieder) {n_meld}")
    zm = {}
    zeilen_ = [t_ for t_ in [i * 0.25 for i in range(0, 80)] if rs._zeile_faellig(zm, "gleich", t_)]
    check(zeilen_ == [0.0, 5.0, 10.0, 15.0] and rs._zeile_faellig(zm, "anders", 15.25),
          f"Statuszeile: gleicher Inhalt alle 5 s, geänderter sofort {zeilen_}")

    print("\n" + ("alle Tests bestanden" if ok else "FEHLER"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
