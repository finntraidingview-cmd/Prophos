#!/usr/bin/env python3
"""Selbsttest LIQUIDE MITTEL (app.py lq_parse_sheet / _lq_holen / lq_antwort / lq_kunde_flags / lq_sheet_id, 09.10.2026, Slave-Terminal 4 —
Auftrag Pascal über Finn, Vertrag .claude/master/auftraege/liquide-vertrag.md).
Fixtures = die drei echten Kunden-Sheets vom 09.10.2026, anonymisiert: Namen und Texte durch „x" ersetzt (nur die Schlüsselwörter
Payout/Abhebung/an uns/Kauf/Reset bleiben), Beträge, Daten und Aufbau unverändert. Erwartet: 3.001 / 2.271 / 361, Prüfung grün
(Referenz lqParseSheet im Kompass liefert dieselben Summen). Dazu: Login-HTML bzw. 401/403 = „nicht freigegeben", Zeile 2 Spalte B
unlesbar, Antwort-Regeln (jüngster Tag, nur aktive, Verlauf, Kunden-Flag, pending in EUR). Ohne Netz. Aufruf: python3 tools/selftest_liquide.py"""
import json
import os
import re
import sys
import threading
import types
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HIER, "..", "app.py")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


FIX_A = "x,x,x,\n,3001,,x x \n x an x,235,11.09.2026,\nx an x,160,11.09.2026,\nx x ,-160,11.09.2026,\nx x,-235,11.09.2026,\nx x an x,1000,14.09.2026,\nx x an x,1000,14.09.2026,\nx reset x,-235,14.09.2026,\nx kauf x ,-160,14.09.2026,\nx kauf x x ,-522,14.09.2026,\nx reset x,-207, 14.09.2026,\nx reset x ,-207, 15.09.2026,\nx kauf x,-235, 15.09.2026,\nx kauf x,-191,15.09.2026,\nx kauf x ,-235,15.09.2026,\nx an x x,1000,16.09.2026,\nx x x,-868,16.09.2026,\nx x ,-30,17.09.2026,\nx an x x,895,17.09.2026,\nx x kauf ,-192,17.09.2026,\nx x kauf ,-192,17.09.2026,\nx kauf,-164,17.09.2026,\nx x,-139,18.09.2026,\nx an x x x x x,2002,18.09.2026,\nx x 3x 50x x,-690,18.09.2026,\n,,,\n,,,\n,,,\nx x x x x x,1956,24.9.2026,\n,,,\n,,,\nx x 50x challenge,-190,25.09.2026,\nx x kauf,-239,25.09.2026,\nx x kauf,-239,25.09.2026,\n,,,\n,,,\n,,,\nx x kauf ,-194,30.09.2026,\nx x kauf ,-61,30.09.2026,\nx x kauf ,-178,30.09.2026,\nx 2 challenge x,-480,30.09.2026,\nx x kauf ,-879,30.09.2026,\nPayout x x x #1,3988,30.09.2026,\n,,,\nabhebung an uns (x),-2896,01.10.2026,\n50x x x x kauf ,-267,01.10.2026,\n,,,\n,,,\n,,,\n3x100x x x x,-1489,05.10.2026,\n,,,\n,,,\n,,,\nx 100x x,-439,05.10.2026,\n,,,\n,,,\nx Payout ,3919,06.10.2026,\n,,,\n,,,\n2x100x x x ,-941,06.10.2026,\n"
FIX_B = "x,x,x,,,x\n,2271,17.09.2026,,,\n1x - x,-1,17.09.2026,,,\nx x,-238,17.09.2026,,,\nx,-193,17.09.2026,,,\nx an x,238,17.09.2026,,,\nx an x,193,17.09.2026,,,\nx x --> x x --->x x --> x x,1000,18.09.2026,,,\nx x reset ,-238,18.09.2026,,,\nx x kauf ,-238,18.09.2026,,,\n,,18.09.2026,,,\n,,18.09.2026,,,\n,,,,,\n,,,,,\n,,,,,\nx x kauf ,-165,22.09.2026,,,\nx x kauf,-194,22.09.2026,,,\n,,,,,\n,,,,,\nx x abhebung x x x ,2152,,,,\nx x kauf,-176,23.09.2026,,,\nx x kauf,-176,23.09.2026,,,\nx x,-861,23.09.2026,,,\n,,23.09.2026,,,\n,,23.09.2026,,,\n,,,,,\n,,,,,\n,,,,,\nx x kauf,-235,24.09.2026,,,\nx x kauf,-235,24.09.2026,,,\nx x 50x x,-198,24.09.2026,,,\n,,24.09.2026,,,\nx x x x x x,2000,24.09.2026,,,\nx x 3x50x x,-785,24.09.2026,,,\n,,,,,\nx x,-194,25.09.2026,,,\nx x,-194,25.09.2026,,,\n,,,,,\n,,,,,\n,,,,,\n3x50x x x,-804,28.09.2026,,,\nx x x x,-80,28.09.2026,,,\nx x ,-195,28.09.2026,,,\nx x x,1000,28.09.2026,,,\n,,,,,\n,,,,,\nx x x,-867,28.09.2026,,,\nx x x,1000,30.09.2026,,,\nx x x,-867,30.09.2026,,,\nx x x x x x x x,1566,30.09.2026,,,\n,,,,,\n,,,,,\n-x x x,-131,01.10.2026,,,\nx x x kauf 2x50x,-528,01.10.2026,,,\nx x reset,-212,01.10.2026,,,\nx x reset,-212,01.10.2026,,,\n,,,,,\nx 2 x x,-444,02.10.2026,,,\nx x reset ,-213,02.10.2026,,,\n,,,,,\npayout x x x x x x x,3969,02.10.2026,,,\n,,,,,\n,,,,,\n3x100x x,-1490,02.10.2026,,,\n,,,,,\nx challenge kauf,-242,05.10.2026,,,\nx challenge reset,-242,05.10.2026,,,\n"
FIX_C = "x,x,x,,x\n,361,,,\n,,,,\nx an x,242,29.09.2026,,\nx x,-242,29.09.2026,,\nx an x,1000,2.10.2026,,\nx #1,-162,2.10.2026,,\n,,,,\n,,,,\n,,,,\n100x x x x,-436,05.10.2026,,\n,,,,\n,,,,\nx,-195,05.10.2026,,\n,,,,\n,,,,\nx x,1109,,,\nx x,-878,06.10.2025,,\n,,,,\n,,,,\n,,,,\n,,,,\nx x,1935,06.10.2025,,\n,,,,\n,,,,\n3x100x x x,-1455,06.10.2025,,\n5x150x x,-706,06.10.2025,,\n,,,,\nx x x ,2000,06.10.2025,,\n,,,,\n,,,,\n,,,,\nx x,-881,07.10.2025,,\n3x x 150x x,-599,07.10.2025,,\nx x,-141,08.10.2025,,\n,,,,\nx x,1380,08.10.2025,,\n2x100x x x,-947,08.10.2025,,\n,,,,\nx x,-131,08.10.2025,,\nx x,,08.10.2025,,\n,,,,\n,,,,\n,,,,\nx x(3x x x),-210,08.10.2025,,\nx x(3x x x),-210,08.10.2025,,\nx reset ,-213,08.10.2025,,\nx 1000 x,1000,09.10.2025,,\n,,,,\n,,,,\n,,,,\n,,,,\nx x,-439,09.10.2025,,\n,,,,\n,,,,\nx x,-230,09.10.2025,,\nx x,-230,09.10.2025,,\n"
LOGIN_HTML = '<!DOCTYPE html><html lang="de"><head><title>Google Sheets: Anmelden</title></head><body>Anmelden</body></html>'


def lade():
    src = open(APP, encoding="utf-8").read()

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]

    def konst(name):
        return re.search(rf"^{name} = .*$", src, re.M).group(0)
    ns = {"re": re, "json": json, "threading": threading, "datetime": datetime, "timezone": timezone}
    teile = [konst(k) for k in ("LQ_NICHT_FREI", "LQ_TOLERANZ_EUR")]
    teile += [block(f) for f in ("_wd_num", "lq_csv", "lq_num", "lq_datum", "lq_parse_sheet", "lq_sheet_id", "_lq_holen",
                                  "lq_kunde_flags", "lq_antwort")]
    exec("\n".join(teile), ns)
    return src, ns


def main():
    src, a = lade()
    P = a["lq_parse_sheet"]

    # 1 die drei echten Sheets (anonymisiert)
    soll = [(FIX_A, 3001, 8248, -10258, 7907, -2896, 0, "2026-10-06"), (FIX_B, 2271, 9149, -10848, 3969, 0, -1, "2026-10-05"),
            (FIX_C, 361, 8666, -8305, 0, 0, 0, "2025-10-09")]
    for i, (csv_, bal, ein, kauf, pay, uns, diff, letzte) in enumerate(soll):
        r = P(csv_)
        check(r["fehler"] is None and r["kontostand"] == bal and r["pruefung_ok"] is True and r["diff"] == diff,
              f"Sheet {i + 1}: Kontostand {bal} €, Prüfung grün (Δ {diff}) ({r['kontostand']}, {r['diff']}, {r['fehler']})")
        check((r["einzahlungen"], r["kaeufe"], r["payouts"], r["an_uns"], r["letzte_buchung"]) == (ein, kauf, pay, uns, letzte),
              f"Sheet {i + 1}: Einzahlungen/Käufe/Payouts/an uns/letzte Buchung wie lqParseSheet ({r})")
    check(P(FIX_A)["n"] == 40 and P(FIX_B)["n"] == 39 and P(FIX_C)["n"] == 25, "Anzahl Buchungen wie die Referenz (40/39/25)")

    # 2 Fehler, nie stumm 0
    for fall, txt in (("Login-HTML", LOGIN_HTML), ("HTML mit Leerzeichen", "\n  <html><body>x</body></html>")):
        r = P(txt)
        check(r["fehler"] == a["LQ_NICHT_FREI"] and r["kontostand"] is None, f"{fall} statt CSV → „nicht freigegeben“, Kontostand null")
    r = P("x,x\n,abc,\nEinzahlung,100,01.10.2026\n")
    check(r["kontostand"] is None and r["fehler"] == "Zeile 2 Spalte B (Kontostand) nicht lesbar: abc", f"B2 unlesbar → Text mit Wert ({r['fehler']})")
    check(P("")["fehler"] == "Sheet leer" and P("x\n")["fehler"] == "Sheet leer", "leeres Sheet → „Sheet leer“")
    r = P('x,x,x\n,"1.234,50",\n"Kauf, Reset","-34,50",01.10.2026\nEinzahlung,"1.269,00",02.10.2026\n')
    check(r["kontostand"] == 1234.5 and r["einzahlungen"] == 1269.0 and r["kaeufe"] == -34.5 and r["diff"] == 0.0 and r["n"] == 2,
          f"deutsche Zahlen + Anführungszeichen ({r})")

    # 3 HTTP-Fälle (_lq_holen mit nachgebautem requests)
    class Antw:
        def __init__(self, code, text="", ctype="text/csv"):
            self.status_code, self.text, self.headers, self.encoding = code, text, {"content-type": ctype}, None

    def mit(antw):
        a["requests"] = types.SimpleNamespace(get=lambda *x, **k: antw, exceptions=types.SimpleNamespace(RequestException=Exception))
        return a["_lq_holen"]("ID")
    check(mit(Antw(403))["fehler"] == a["LQ_NICHT_FREI"] and mit(Antw(401))["fehler"] == a["LQ_NICHT_FREI"], "HTTP 401/403 → nicht freigegeben")
    check(mit(Antw(200, LOGIN_HTML, "text/html; charset=utf-8"))["fehler"] == a["LQ_NICHT_FREI"], "200 mit Login-Seite (text/html) → nicht freigegeben")
    check(mit(Antw(404))["fehler"].startswith("Sheet nicht gefunden") and mit(Antw(500))["fehler"] == "HTTP 500", "404 / 500 → Klartext")
    check(mit(Antw(200, FIX_A))["kontostand"] == 3001, "200 CSV → geparst")

    # 4 Link → Sheet-ID
    L = a["lq_sheet_id"]
    check(L("https://docs.google.com/spreadsheets/d/AbCdEfGhIjKlMnOpQrStUvWx_-12/edit#gid=0") == "AbCdEfGhIjKlMnOpQrStUvWx_-12"
          and L("AbCdEfGhIjKlMnOpQrStUvWx_-12") == "AbCdEfGhIjKlMnOpQrStUvWx_-12" and L("kein link") is None and L("") is None,
          "Sheet-ID aus Link oder nackter ID, sonst None")

    # 5 Antwort (lq_antwort)
    sh = [{"id": "s1", "person_uid": "u1", "person_name": "A", "sheet_id": "S1", "aktiv": True},
          {"id": "s2", "person_uid": "u2", "person_name": "B", "sheet_id": "S2", "aktiv": True},
          {"id": "s3", "person_uid": "u3", "person_name": "C", "sheet_id": "S3", "aktiv": False}]
    st = [{"sheet_id": "S1", "day": "2026-10-08", "kontostand": 2900, "diff": 0},
          {"sheet_id": "S1", "day": "2026-10-09", "kontostand": 3001, "diff": 0, "einzahlungen": 8248},
          {"sheet_id": "S2", "day": "2026-10-09", "kontostand": None, "diff": None, "fehler": a["LQ_NICHT_FREI"]},
          {"sheet_id": "S3", "day": "2026-10-09", "kontostand": 500, "diff": 0}]
    nutzer = [("u1", "kunde1@x.de"), ("ufinn", "admin@x.de"), ("uemin", "aus@x.de"), ("u2", "kunde2@x.de")]
    pend = [{"user_id": "u1", "amount": 100, "currency": "USD", "requested_at": "2026-10-08"},
            {"user_id": "uemin", "amount": 50, "currency": "EUR", "requested_at": "2026-10-07"}]
    A = a["lq_antwort"](sh, st, nutzer, [{"user_id": "u2", "ist_kunde": False}], pend, 0.9, {"admin@x.de"}, frozenset({"uemin"}))
    s1 = next(x for x in A["sheets"] if x["id"] == "s1")
    s2 = next(x for x in A["sheets"] if x["id"] == "s2")
    check(s1["stand"]["day"] == "2026-10-09" and s1["stand"]["kontostand"] == 3001 and s1["stand"]["pruefung_ok"] is True,
          "je Sheet der jüngste Tag, Prüfung grün")
    check(s2["stand"]["kontostand"] is None and s2["stand"]["pruefung_ok"] is False and s2["stand"]["fehler"] == a["LQ_NICHT_FREI"],
          "Fehler-Sheet: Kontostand null, Prüfung nicht grün, Fehlertext")
    check(A["summe_kunden_eur"] == 3001, f"summe_kunden_eur nur aktive mit Kontostand ({A['summe_kunden_eur']})")
    check(A["verlauf_bank"] == [{"day": "2026-10-08", "summe": 2900}, {"day": "2026-10-09", "summe": 3001}],
          f"verlauf_bank je Tag, nur aktive ({A['verlauf_bank']})")
    check(A["kunde"] == {"u1": True, "ufinn": False, "u2": False}, f"Kunden-Flag: Default Kunde, Admin nein, Zeile gewinnt, Ausgeblendete raus ({A['kunde']})")
    check(A["pending"] == [{"user_id": "u1", "betrag_eur": 90.0, "betrag": 100.0, "waehrung": "USD", "account_name": "", "account_firm": "",
                            "liegt_bei": "", "requested_at": "2026-10-08"}], f"pending in EUR (USD × fx), Ausgeblendete raus ({A['pending']})")
    check(A["ok"] and A["fx_usd_eur"] == 0.9 and A["generated"] and set(A) >= {"sheets", "summe_kunden_eur", "verlauf_bank", "kunde", "pending"},
          "Antwortform wie im Vertrag")
    A2 = a["lq_antwort"](sh + [{"id": "s4", "person_uid": "uemin", "person_name": "E", "sheet_id": "S4", "aktiv": True}],
                         st + [{"sheet_id": "S4", "day": "2026-10-09", "kontostand": 999, "diff": 0}], nutzer, [], [], 0.9, {"admin@x.de"},
                         frozenset({"uemin"}))
    check(all(x["id"] != "s4" for x in A2["sheets"]) and A2["summe_kunden_eur"] == 3001 and A2["verlauf_bank"][-1]["summe"] == 3001,
          "Sheet einer ausgeblendeten Person (Emin) kommt nicht vor — weder Zeile noch Summe noch Verlauf")
    check([x["person_name"] for x in A["sheets"]] == ["A", "B", "C"] and set(s1) == {"id", "person_uid", "person_name", "sheet_id", "aktiv", "stand"},
          "Sheets nach Name, Felder wie im Vertrag")

    # 5b Knopf-Abruf wartet nicht am Lock (Master 09.10.2026: Railway-Threads knapp) — läuft schon einer: None, sonst Anzahl
    blk = src[src.index("\ndef _lq_abrufen("):src.index("\n\n\n", src.index("\ndef _lq_abrufen("))]
    geholt = []
    ns2 = {"_lq_lock": threading.Lock(), "_lq_info": {}, "datetime": datetime, "timezone": timezone,
           "_sb_all": lambda t, p: [{"sheet_id": "S1"}, {"sheet_id": "S2"}], "_lq_sheet_abrufen": lambda r: geholt.append(r["sheet_id"])}
    exec(blk, ns2)
    check(ns2["_lq_abrufen"](warten=False) == 2 and geholt == ["S1", "S2"] and not ns2["_lq_lock"].locked(), "Abruf holt alle aktiven Sheets, Lock danach frei")
    ns2["_lq_lock"].acquire()
    check(ns2["_lq_abrufen"](warten=False) is None and geholt == ["S1", "S2"], "läuft schon ein Abruf: Knopf wartet nicht, holt nichts (None)")
    ns2["_lq_lock"].release()
    check("_lq_abrufen(warten=False)" in src and "abruf_laeuft=_lq_lock.locked()" in src and "n = _lq_abrufen()" in src,
          "Knopf ohne Warten, Antwort mit abruf_laeuft, Takt wartet wie bisher")

    # 6 Quelltext: Gate, Routen, Takt
    for r_ in ('"/admin/liquide"', '"/admin/liquide/abruf"', '"/admin/liquide/sheet"', '"/admin/liquide/sheet/aktiv"', '"/admin/liquide/kunde"'):
        check(f"@app.route({r_}, methods=" in src, f"Route {r_}")
    g = src[src.index("\ndef _lq_gate("):src.index("\n\n\n", src.index("\ndef _lq_gate("))]
    check("_admin_auth()" in g and "admin_sicht_lesen(" in g and "if sicht is not None:" in g and "403" in g,
          "Gate: ADMIN_EMAILS + nur Voll-Admins (eingeschränkt → 403)")
    check(src.count("err = _lq_gate()") == 5, "alle fünf Routen hinter dem Gate")
    check("LQ_TAKT_S = 6 * 3600" in src and "start_liquide()\n" in src and 'os.environ.get("PROPHOS_FRONTEND")' in src[src.index("def start_liquide"):],
          "Takt alle 6 h, nur auf Railway")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
