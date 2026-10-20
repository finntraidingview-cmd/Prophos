#!/usr/bin/env python3
"""Selbsttest POLAR-VORRANG (20.10.2026, Finn: „Wenn Polar läuft, darf gar kein einziger Trade mehr gestartet werden … keine Order,
keine Balance-Lesung, der Puls-Knopf macht nichts. Der Reader redet die ganze Zeit weiter.") — läuft OHNE Windows/MT5, also auch am Mac.

Prüft (1) den Panel-Riegel polar_panel.sperre_antwort/gesperrt: jede POST-Route außer FREI_PFADE → 409 polar_aktiv mit lauf_id,
solange das Flag auf einen lebenden Prozess zeigt; toter Prozess → Flag weg, nichts gesperrt. (2) polar_app.aktiv_liste: welche Läufe
(Bot-Prozess, polar_lauf, Hand-Polar-Plan) eine ID gerade halten — Master- und Slave-Seite, Ende-Status fällt raus, Dubletten fallen weg.

Aufruf:  python3 selftest_polar_riegel.py
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))   # polar_app.py liegt im Repo-Stamm (Railway)
import polar_panel  # noqa: E402

FEHLER = []


def chk(name, ok):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def test_panel():
    tmp = tempfile.mkdtemp(prefix="polar-riegel-")
    polar_panel.FLAG = os.path.join(tmp, "polar_aktiv.json")
    lebt = {"pid": 4711}
    polar_panel._prozess_lebt = lambda pid: bool(pid) and int(pid) == lebt["pid"]
    # ohne Flag: nichts gesperrt
    chk("ohne Flag: tv-order frei", polar_panel.sperre_antwort("/api/tv-order") is None)
    chk("ohne Flag: gesperrt() False", polar_panel.gesperrt("/api/master-order") is False)
    # Flag mit lebendem Prozess
    polar_panel._schreiben(polar_panel.FLAG, {"lauf_id": "abcdef12-0000-4000-8000-000000000001", "seite": "master", "pid": 4711, "plan_id": "p1"})
    chk("aktiv() True", polar_panel.aktiv() is True)
    for pfad in ("/api/tv-order", "/api/tv-lesen", "/api/tv-close", "/api/tv-konto", "/api/tsx-konto", "/api/master-order",
                 "/api/master-close", "/api/hedge-solo", "/api/plan", "/api/plan-delete", "/api/set-hedge", "/api/start-terminal",
                 "/api/provision", "/api/mouse-test", "/api/irgendwas-neues"):
        a = polar_panel.sperre_antwort(pfad)
        ok = bool(a) and a[0] == 409 and a[1].get("code") == "polar_aktiv" and a[1].get("lauf_id", "").startswith("abcdef12") \
            and a[1].get("gesendet") is False and a[1].get("retry_ok") is True and a[1].get("seite") == "master"
        chk(f"gesperrt 409 polar_aktiv: {pfad}", ok)
    for pfad in polar_panel.FREI_PFADE:
        chk(f"frei: {pfad}", polar_panel.sperre_antwort(pfad) is None and polar_panel.gesperrt(pfad) is False)
    chk("Antwort nennt den Lauf (8 Zeichen)", "abcdef12" in polar_panel.sperre_antwort("/api/tv-order")[1]["msg"])
    chk("stand(): aktiv + lauf_id", polar_panel.stand()["aktiv"] is True and polar_panel.stand()["lauf_id"].startswith("abcdef12"))
    # Prozess tot → Flag räumt sich weg, nichts gesperrt
    lebt["pid"] = 1
    chk("toter Prozess: tv-order frei", polar_panel.sperre_antwort("/api/tv-order") is None)
    chk("toter Prozess: Flag gelöscht", not os.path.exists(polar_panel.FLAG))
    chk("stand() nach Ende: aktiv False", polar_panel.stand()["aktiv"] is False)
    # kaputtes Flag (kein dict) → nicht aktiv
    with open(polar_panel.FLAG, "w", encoding="utf-8") as f:
        f.write(json.dumps(["kein", "dict"]))
    chk("kaputtes Flag: nicht aktiv", polar_panel.aktiv() is False)


def test_aktiv_liste():
    try:
        import polar_app
    except Exception as e:   # auf einem PC ohne Flask liegt polar_app nicht vor — dann nur den Panel-Teil prüfen
        print(f"· polar_app nicht importierbar ({type(e).__name__}) — aktiv_liste übersprungen")
        return
    A, B, C = "aaaaaaaa-0000-4000-8000-000000000001", "bbbbbbbb-0000-4000-8000-000000000002", "cccccccc-0000-4000-8000-000000000003"
    lauf = {"id": "11111111-0000-4000-8000-000000000001", "plan_id": "p-1", "master_uid": A, "slave_uid": B, "status": "offen"}
    db_lauf = {"id": "11111111-0000-4000-8000-000000000001", "plan_id": "p-1", "master_user_id": A, "slave_user_id": B, "status": "offen"}
    ende = {"id": "22222222-0000-4000-8000-000000000002", "plan_id": "p-2", "master_user_id": A, "slave_user_id": B, "status": "fertig"}
    hand = {"id": "p-3", "user_id": C, "polar_slave_user_id": A, "route": "polar", "status": "open", "started_at": "2026-10-20T00:00:00Z"}
    hand_zu = {"id": "p-4", "user_id": C, "polar_slave_user_id": A, "route": "polar", "status": "review"}
    orbit = {"id": "p-5", "user_id": A, "polar_slave_user_id": None, "route": "tvv2", "status": "open"}
    la = polar_app.aktiv_liste(A, [lauf], [db_lauf, ende], [hand, hand_zu, orbit])
    chk("Master-ID: Bot-Lauf einmal (Prozess + DB keine Dublette)", len([x for x in la if x["quelle"] == "bot"]) == 1)
    chk("Master-ID: seite master", any(x["quelle"] == "bot" and x["seite"] == "master" for x in la))
    chk("Master-ID: Hand-Plan als Slave-Seite", any(x["quelle"] == "hand" and x["seite"] == "slave" and x["plan_id"] == "p-3" for x in la))
    chk("Ende-Status/review/Orbit fallen raus", len(la) == 2 and not any(x["plan_id"] in ("p-2", "p-4", "p-5") for x in la))
    lb = polar_app.aktiv_liste(B, [lauf], [], [hand])
    chk("Slave-ID: nur der Bot-Lauf, seite slave", len(lb) == 1 and lb[0]["seite"] == "slave" and lb[0]["lauf_id"].startswith("11111111"))
    chk("fremde ID: nichts", polar_app.aktiv_liste(C, [lauf], [db_lauf], []) == [])
    chk("Hand-Plan ohne lauf_id", all(x["lauf_id"] is None for x in polar_app.aktiv_liste(C, [], [], [hand])))
    chk("leer/None verträglich", polar_app.aktiv_liste(A, None, None, None) == [])
    # EIN Select: trade_plans mit eingebettetem polar_lauf (20.10.2026) → laeufe_aus_plaenen
    rows = [{"id": "p-1", "user_id": A, "polar_slave_user_id": B, "route": "polar", "status": "planned",
             "polar_lauf": [{"id": lauf["id"], "status": "bereit", "created_at": "2026-10-20T00:00:00+00:00"},
                            {"id": ende["id"], "status": "fertig", "created_at": "2026-10-19T00:00:00+00:00"}]},
            {"id": "p-3", "user_id": C, "polar_slave_user_id": A, "route": "polar", "status": "open", "polar_lauf": []},
            {"id": "p-9", "user_id": A, "route": "polar", "status": "open", "polar_lauf": None}]
    dbl = polar_app.laeufe_aus_plaenen(rows)
    chk("laeufe_aus_plaenen: 2 Läufe mit master/slave aus dem Plan", len(dbl) == 2 and all(x["master_user_id"] == A and x["slave_user_id"] == B for x in dbl))
    le = polar_app.aktiv_liste(A, [], dbl, rows)
    chk("ein Select: Bot-Lauf (bereit, Plan noch planned) + Hand-Plan p-3 + eigener Hand-Plan p-9, fertig fällt raus",
        sorted((x["quelle"], x["plan_id"]) for x in le) == [("bot", "p-1"), ("hand", "p-3"), ("hand", "p-9")])
    chk("leere Einbettung verträglich", polar_app.laeufe_aus_plaenen([{"id": "x", "polar_lauf": None}, "kaputt", None]) == [])
    # SPERRE ERST AB DER ORDER (20.10.2026): phase vorbereiten (start/bereit) vs. order (feuer/offen/zu…), Hand-Plan immer order
    for st, ph in (("start", "vorbereiten"), ("bereit", "vorbereiten"), ("feuer", "order"), ("offen", "order"), ("master_zu", "order")):
        lx = polar_app.aktiv_liste(A, [dict(lauf, status=st)], [], [])
        chk(f"phase {st} → {ph}", len(lx) == 1 and lx[0]["phase"] == ph)
    chk("Hand-Plan phase order", polar_app.aktiv_liste(C, [], [], [hand])[0]["phase"] == "order")
    # VOR-Liste statt Positivliste (S2/Master 20.10.2026): nur start/bereit sind „vorbereiten" — jeder andere, auch unbekannte Status
    # (S3s slave_zu, künftige Namen) gilt als „order" = scharf (fail-closed); dasselbe gilt im Tab (POLAR_PHASEN_VOR) für Bot-Phasen
    for st in ("slave_zu", "geparkt_x", "x_geklickt", "zu_bestaetigt", "nicht_zu", "irgendwas_neues", ""):
        lx = polar_app.aktiv_liste(A, [dict(lauf, status=st or "start")], [], []) if st else polar_app.aktiv_liste(A, [dict(lauf, status="x")], [], [])
        chk(f"unbekannter Status {st or 'x'} → order (hart)", len(lx) == 1 and lx[0]["phase"] == "order") if st else chk("Status x → order (hart)", lx[0]["phase"] == "order")
    # PRÜF-TABELLE VOR DEM START (Finn 21.10.2026 ~23:15 Dubai): vorpruefung_zeilen — Tab, /polar/freigeben und /polar/start rechnen damit
    from datetime import datetime, timezone, timedelta
    jetzt = datetime(2026, 10, 21, 20, 0, tzinfo=timezone.utc)
    vor = lambda m: (jetzt - timedelta(minutes=m)).isoformat()
    tb = polar_app.trades_belegt([
        {"id": "o1", "user_id": A, "route": "tvv2", "status": "open", "master_name": "150k Orbit"},
        {"id": "r1", "user_id": B, "route": "mt5v2", "status": "review", "master_name": "100k Echo", "ended_at": vor(20), "endlesung": {}, "final": {}},
        {"id": "r2", "user_id": B, "route": "mt5v2", "status": "review", "ended_at": vor(20), "final": {"balance_end": 100123}},
        {"id": "r3", "user_id": B, "route": "tvv2", "status": "review", "ended_at": vor(300), "endlesung": {}},
        {"id": "pp", "user_id": A, "route": "polar", "status": "open"},
        {"id": "ich", "user_id": A, "route": "tvv2", "status": "open"}], "ich", jetzt)
    chk("belegt: open = läuft, review ohne Lesung ≤ 2 h = wartet; gelesen/alt/Polar/eigener Plan fallen raus",
        sorted((x["id"], x["art"]) for x in tb) == [("o1", "läuft"), ("r1", "wartet auf Lesung")])
    gruen = {"mu": A, "su": B, "m_name": "150k FNF", "s_name": "100k FN", "m_wer": "Finn + Pascal", "s_wer": "Chris",
             "rs_master": {"frei": True}, "rs_slave": {"frei": True}, "belegt": [], "signale": [], "polar": [],
             "pc_lesbar": True, "pc_master": {"lebt": True, "pc_name": "pc-a"}, "pc_slave": {"lebt": True, "pc_name": "pc-b"},
             "slave_ort": "da", "slave_login": "123", "reader": {"frisch": True, "pc": "pc-a", "alter_s": 3}}
    vz = polar_app.vorpruefung_zeilen
    frei, zz = vz(gruen)
    chk("alles grün → frei, 9 Zeilen, alle ✓ außer Reader (–, prüft der Master-PC)", frei is True and len(zz) == 9
        and all(z["ok"] is True for z in zz if z["key"] != "reader") and next(z for z in zz if z["key"] == "reader")["ok"] is None)
    for name, aend, key in (("Richtung Master gesperrt", {"rs_master": {"frei": False, "grund": "Long läuft"}}, "rs_master"),
                            ("Richtung Slave nicht prüfbar (fail-closed)", {"rs_slave": {"fehler": "DB weg"}}, "rs_slave"),
                            ("Orbit läuft auf der Slave-ID", {"belegt": [{"user_id": B, "route": "tvv2", "name": "150k Orbit", "art": "läuft"}]}, "trades_slave"),
                            ("Puls-Signal auf der Master-ID", {"signale": [{"user_id": A, "aktion": "orbit", "status": "laeuft"}]}, "trades_master"),
                            ("Trades nicht lesbar (fail-closed)", {"belegt": None}, "trades_master"),
                            ("anderer Polar-Lauf", {"polar": [{"quelle": "bot", "lauf_id": "x" * 36, "seite": "slave"}]}, "polar"),
                            ("Polar nicht lesbar (fail-closed)", {"polar": None}, "polar"),
                            ("Master-PC aus", {"pc_master": {"lebt": False, "alt_s": 900}}, "pc_master"),
                            ("Slave-PC ohne Tab", {"pc_slave": None}, "pc_slave"),
                            ("MT5-Login am Slave-PC weg", {"slave_ort": "weg"}, "mt5_slave")):
        f2, z2 = vz(dict(gruen, **aend))
        zeile = next(z for z in z2 if z["key"] == key)
        chk(f"{name} → gesperrt, Zeile {key} ✗", f2 is False and zeile["ok"] is False and zeile["text"])
    f3, z3 = vz(dict(gruen, signale=[{"user_id": B, "aktion": "polar_slave", "status": "wartet"}]))
    chk("eigenes polar_slave-Signal belegt nicht", f3 is True)
    f4, z4 = vz(dict(gruen, slave_ort=None))
    chk("MT5-Login nicht prüfbar → Zeile ohne Haken, sperrt nicht", f4 is True and next(z for z in z4 if z["key"] == "mt5_slave")["ok"] is None)
    # READER (Prüfer S2 21.10.2026): der Server sieht den lokalen Reader nicht → Zeile „–", sperrt nie; geprüft wird im Bot (reader_bereit)
    fr, zr = vz(dict(gruen))
    chk("Reader-Zeile vom Server nie ✗ (sonst wäre jeder Start ohne 24/7-Kursfeed gesperrt)", fr is True and next(z for z in zr if z["key"] == "reader")["ok"] is None
        and "reader_frisch" not in open(os.path.join(os.path.dirname(HERE), "polar_app.py"), encoding="utf-8").read())
    # VORRANG FÄLLT MIT DEM LAUFENDE (h): Prozess „fertig" überdeckt die alte DB-Kopie „offen"; Plan open + Bot-Lauf fertig/fehler zählt nicht
    # als Hand-Plan; Plan open nach nur abgebrochenem Lauf (vor der Feuerzeit) = Hand (Finn startete von Hand)
    for st in ("fertig", "abbruch", "fehler"):
        chk(f"Laufende {st}: Prozess überdeckt DB-offen → nichts gehalten",
            polar_app.aktiv_liste(A, [dict(lauf, status=st)], [dict(db_lauf, status="offen")], []) == [])
    po = {"id": "p-7", "user_id": A, "polar_slave_user_id": B, "route": "polar", "status": "open"}
    chk("Plan open + Bot-Lauf fertig → kein Hand-Halt (wartet nur auf _abrechnen)",
        polar_app.aktiv_liste(A, [], [], [dict(po, polar_lauf=[{"id": "l", "status": "fertig"}])]) == [])
    hf = polar_app.aktiv_liste(B, [], [], [dict(po, polar_lauf=[{"id": "l", "status": "fehler"}])])
    chk("Plan open + Bot-Lauf fehler → Hand-Halt bleibt (UNKLAR-Fälle, Prüfer S2)", len(hf) == 1 and hf[0]["quelle"] == "hand")
    hp = polar_app.aktiv_liste(A, [{"id": "l", "plan_id": "p-7", "master_uid": A, "slave_uid": B, "status": "fertig"}], [],
                               [dict(po, polar_lauf=[{"id": "l", "status": "offen"}])])
    chk("Prozess fertig + DB-Einbettung noch offen → Plan frei (Prozess zählt)", hp == [])
    hq = polar_app.aktiv_liste(A, [{"id": "l", "plan_id": "p-7", "master_uid": A, "slave_uid": B, "status": "fehler"}], [],
                               [dict(po, polar_lauf=[{"id": "l", "status": "offen"}])])
    chk("Prozess fehler + Plan open → Hand-Halt", len(hq) == 1 and hq[0]["quelle"] == "hand")
    ah = polar_app.aktiv_liste(A, [], [], [dict(po, polar_lauf=[{"id": "l", "status": "abbruch"}])])
    chk("Plan open nach nur abgebrochenem Lauf → Hand-Halt", len(ah) == 1 and ah[0]["quelle"] == "hand")
    srcA = open(os.path.join(os.path.dirname(HERE), "polar_app.py"), encoding="utf-8").read()
    ab = srcA[srcA.index("def _abrechnen(z):"):srcA.index("def laeufe_aus_plaenen(")]
    chk("Abrechnung unabhängig vom Vorrang: kein aktiv_liste/_AKTIV im Weg, schreibt master_pl/slave_pl + tv_balance beider Konten",
        "aktiv_liste" not in ab and "_AKTIV" not in ab and "master_pl" in ab and "slave_pl" in ab and ab.count('"tv_balance"') >= 2)
    f5, z5 = vz(dict(gruen, pc_lesbar=False))
    chk("PC-Stand nicht lesbar → beide PC-Zeilen nicht prüfbar, sperrt nicht", f5 is True and [z["ok"] for z in z5 if z["key"].startswith("pc_")] == [None, None])
    chk("Orbit-Treffer namentlich", "150k Orbit" in next(z for z in vz(dict(gruen, belegt=[{"user_id": A, "route": "tvv2", "name": "150k Orbit", "art": "läuft"}]))[1] if z["key"] == "trades_master")["text"])
    chk("Schalter steht an", polar_app.POLAR_AUTO is True)
    # LIVE-ABLAUF (Finn 20.10.2026 ~23:55 Dubai): Schrittliste je Seite (schritt_eintragen) + Slave-Live-P&L aus mt5_live (slave_live_pl)
    se = polar_app.schritt_eintragen
    teil = {}
    chk("Schritt neu", se(teil, "vorbereiten", "MT5 öffnen", 1000) is True and se(teil, "bereit", "steht", 3000) is True)
    chk("Dublette (gleiche Phase + Zeit) fällt weg", se(teil, "bereit", "steht", 3000) is False and len(teil["schritte"]) == 2)
    se(teil, "geklickt", "gedrückt", 2000)
    chk("nach Zeit sortiert", [x["phase"] for x in teil["schritte"]] == ["vorbereiten", "geklickt", "bereit"])
    t2 = {}
    for i in range(50):
        se(t2, f"p{i}", "x", i)
    chk("höchstens 40, die jüngsten bleiben", len(t2["schritte"]) == 40 and t2["schritte"][0]["phase"] == "p10" and t2["schritte"][-1]["phase"] == "p49")
    chk("leere Phase verworfen, Text gekürzt", se({}, "", "x", 1) is False and len((lambda t: (se(t, "a", "x" * 300, 1), t)[1])({})["schritte"][0]["text"]) == 160)
    sl = polar_app.slave_live_pl
    rows = [{"updated_at": "2026-10-21T20:00:01Z", "pos": [{"ticket": 77, "profit": -12.5}, {"ticket": 78, "profit": 3}]},
            {"updated_at": "2026-10-21T20:00:05Z", "pos": [{"ticket": 77, "profit": 40.257}]}]
    chk("Slave-P&L: jüngste Zeile mit dem Ticket, gerundet", sl(rows, 77) == {"pl": 40.26, "at": "2026-10-21T20:00:05Z"})
    chk("Slave-P&L: Ticket fehlt → None", sl(rows, 99) is None and sl([], 77) is None and sl(None, 77) is None)
    srcL = open(os.path.join(os.path.dirname(HERE), "polar_app.py"), encoding="utf-8").read()
    sr = srcL[srcL.index("def polar_schritt():"):srcL.index("@app.route(\"/polar/aktiv\"")]
    chk("/polar/schritt: Code-Schlüssel + Seite geprüft, kein Status-Wechsel, kein Wecken, KEIN eigener DB-Write (kein Wettrennen mit melden)",
        '_code_zugang' in sr and "_seite_ok(z, wer[0], seite)" in sr and "_status(" not in sr and "notify" not in sr and "_db(" not in sr)
    chk("/polar/stand liefert slave_live", '"slave_live": _slave_live(z)' in srcL)
    # WÄHREND DES LAUFS (Master 21.10.2026, Punkt 3): ein Bot-Lauf hält Master- UND Slave-ID schon ab „start" — der Tab-Start-Wächter
    # sperrt jede Polar-Zeile dieser IDs, auch in der Vorbereitung (polarStartSperre, prophos.html), also startet dort kein Orbit-Plan
    for st in ("start", "bereit", "feuer", "offen"):
        for uid, seite in ((A, "master"), (B, "slave")):
            lx = polar_app.aktiv_liste(uid, [dict(lauf, status=st)], [], [])
            chk(f"Lauf {st}: {seite}-ID gehalten", len(lx) == 1 and lx[0]["seite"] == seite)
    # Server prüft selbst (fail-closed), die Tabelle ist nur die Anzeige: /polar/start ruft _vorpruefung vor dem Lauf-Insert, /polar/freigeben
    # vor dem Setzen der Startzeit; /polar/plan setzt keine Startzeit mehr
    src = open(os.path.join(os.path.dirname(HERE), "polar_app.py"), encoding="utf-8").read()
    st = src[src.index("def polar_start():"):src.index("def polar_bereit():")]
    chk("/polar/start: _vorpruefung vor dem polar_lauf-Insert, 409 mit Liste", 0 < st.index("_vorpruefung(plan)") < st.index('sb_insert"]("polar_lauf"') and '"zeilen": zeilen}), 409' in st)
    fg = src[src.index("def polar_freigeben():"):src.index('@app.route("/polar/geblowt"')]
    chk("/polar/freigeben: _vorpruefung vor dem start_um-Update", 0 < fg.index("_vorpruefung(plan)") < fg.index('"start_um": A["_wt_now_iso"]()'))
    pl = src[src.index("def polar_plan():"):src.index("def _vp_plan(d):")]
    chk("/polar/plan: keine Startzeit, kein open", '"start_um"' not in pl and '"open"' not in pl)
    # ALTER TAB-BODY (S2 21.10.2026): ältere Tabs/Mac localhost:5000 schicken starten:true ohne neue Felder — /polar/plan liest starten/hand
    # gar nicht mehr, also wird daraus nie ein Bot-Plan (und nie open); ein Bot-Start geht nur über /polar/freigeben (neuer Tab, Prüf-Tabelle)
    chk("alter Tab-Body (starten:true, kein hand) → nur gespeichert, nie Bot", 'd.get("starten")' not in pl and 'd.get("hand")' not in pl and "plan_startart" not in srcA)
    html = open(os.path.join(os.path.dirname(HERE), "prophos.html"), encoding="utf-8").read()
    i_tick = html.index("async function tpStartUmTick(){")
    i_kand = html.index("const faellig = suKandidaten(", i_tick)
    chk("Start-Wächter fragt polarStartSperre() VOR der Kandidatenwahl", 0 < html.index("polarStartSperre()", i_tick) < i_kand)
    chk("polarStartSperre nimmt jede Phase (auch vorbereiten)", "function polarStartSperre(){" in html and "polarRiegelStand()" in html[html.index("function polarStartSperre(){"):html.index("function polarStartSperre(){") + 300])
    # RICHTUNGSSCHUTZ (20.10.2026): beide Seiten frei → frei; eine Seite gesperrt → Seite + Grund; nicht prüfbar → gesperrt
    rp = polar_app.richtungsschutz_pruefen
    chk("beide frei", rp({"frei": True}, {"frei": True}) == (True, ""))
    f, g = rp({"frei": True}, {"frei": False, "grund": "„100k X“ läuft dort LONG — SHORT wäre die Gegenrichtung"}, "FuKonto", "CfdKonto")
    chk("Slave gesperrt nennt Seite + Grund", f is False and g.startswith("Richtungsschutz Slave (CfdKonto): „100k X“ läuft dort"))
    f, g = rp({"frei": False, "grund": "x"}, {"frei": True})
    chk("Master gesperrt zuerst", f is False and g.startswith("Richtungsschutz Master"))
    f, g = rp({"frei": True}, {"fehler": "DB-Funktion prophos_gegenrichtung_frei_konto fehlt — sql/2026-10-20_polar_richtungsschutz.sql einspielen"})
    chk("nicht prüfbar = gesperrt, nennt die SQL-Datei", f is False and "nicht prüfbar" in g and "2026-10-20_polar_richtungsschutz" in g)
    chk("None/kaputt = gesperrt", rp(None, {"frei": True})[0] is False and rp({"frei": True}, "x")[0] is False and rp({}, {"frei": True})[0] is False)


def main():
    test_panel()
    test_aktiv_liste()
    print(("OK — alle Prüfungen grün" if not FEHLER else f"FEHLER: {len(FEHLER)} rot: " + "; ".join(FEHLER)))
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
