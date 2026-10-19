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
