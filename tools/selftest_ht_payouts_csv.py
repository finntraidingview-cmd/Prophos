#!/usr/bin/env python3
"""Selbsttest HT-PAYOUTS-CSV (29.10.2026, Slave 7): GET /ht/payouts.csv?token=… liefert die Payouts der Gruppe Hermann Technologies als CSV
für das Google Sheet „HT Buchhaltung 2026“ (IMPORTDATA). Geprüft ohne Netz und ohne die ganze App:
(A) ht_payouts_token_ok — fehlende/zu kurze Variable → nie offen; fehlender/falscher Token → nein; richtiger → ja.
(B) ht_payouts_ausblenden — ADMIN_EXCLUDE + Gruppen MIT Verwalter raus; Namen nie aus der Mail; leere Nutzerliste → Fehler.
(C) ht_payouts_csv — nur HT-Zeilen ab 30.05.2026, Kopf, Betrag mit Dezimalkomma, Sortierung nach Datum, keine Mails/Logins, Formel-Schutz
    (Prüfer 29.10.2026: Kontoname „=IMPORTXML(…)“ → ' davor); ohne Verwalter-Gruppe → Fehler (fail-closed).
(D) Route über den Flask-Testclient mit Attrappen: Variable fehlt / kein / falscher / richtiger Token, Lesefehler → 502 ohne Token im Log.
Aufruf: python3 tools/selftest_ht_payouts_csv.py"""
import contextlib
import hmac
import io
import os
import re
import sys

from flask import Flask, Response, request

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HIER, "..", "app.py")
FEHLER = []
TOKEN = "t" * 40


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade(stubs):
    src = open(APP, encoding="utf-8").read()
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in ("HT_PAYOUTS_CSV_TOKEN_MIN", "HT_PAYOUTS_AB")]
    for name in ("_admin_verwalter_gruppen_ids", "ht_payouts_token_ok", "ht_payouts_csv_sicher", "ht_payouts_ausblenden", "ht_payouts_csv"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    i = src.index('@app.route("/ht/payouts.csv"')
    teile.append(src[i:src.find("\n\n\n", i)])
    app = Flask("selftest")
    ns = {"hmac": hmac, "os": os, "request": request, "Response": Response, "app": app}
    ns.update(stubs)
    exec("\n".join(teile), ns)
    return ns, app


A, B, C, D, E = ("aaaaaaaa-0000-4000-8000-000000000001", "bbbbbbbb-0000-4000-8000-000000000002",
                 "cccccccc-0000-4000-8000-000000000003", "dddddddd-0000-4000-8000-000000000004", "eeeeeeee-0000-4000-8000-000000000005")
USERS = [
    {"id": A, "email": "finn@example.com", "user_metadata": {"name": "Finn + Pascal"}},
    {"id": B, "email": "moritz@example.com", "user_metadata": {}},                       # ohne Namen → user_id[:8], nie die Mail
    {"id": C, "email": "ausgeblendet@example.com", "user_metadata": {"name": "Raus"}},   # ADMIN_EXCLUDE
    {"id": D, "email": "d@example.com", "user_metadata": {"name": "@Kunde"}},            # Name mit @ vorne → ' davor
    {"id": E, "email": "emin@example.com", "user_metadata": {"name": "Emin"}},           # Verwalter einer Gruppe → raus
]
GRUPPEN = {"gruppen": [{"id": "g1", "name": "Emin", "verwalter_id": E}], "mitglieder": []}
TXS = [
    {"id": "t2", "user_id": A, "account_firm": "Tradeify", "account_name": "150k TDFYSL150000000001 → Winning Days", "amount": 4050, "currency": "usd", "occurred_at": "2026-10-23"},
    {"id": "t1", "user_id": B, "account_firm": "Apex Trader", "account_name": "", "amount": "3476.14", "currency": "EUR", "occurred_at": "2026-09-25T10:00:00+00:00"},
    {"id": "t3", "user_id": C, "account_firm": "X", "account_name": "Y", "amount": 100, "currency": "EUR", "occurred_at": "2026-10-01"},
    {"id": "t5", "user_id": A, "account_firm": "Alt", "account_name": "vor dem Zeitraum", "amount": 999, "currency": "EUR", "occurred_at": "2026-05-29T23:00:00+00:00"},
    {"id": "t6", "user_id": A, "account_firm": "=IMPORTXML(\"https://x.example\",\"//a\")", "account_name": "", "amount": 50, "currency": "EUR", "occurred_at": "2026-10-24"},
    {"id": "t7", "user_id": D, "account_firm": "+Firma", "account_name": "", "amount": 10, "currency": "-1+1", "occurred_at": "2026-10-25"},
    {"id": "t4", "user_id": E, "account_firm": "Z", "account_name": "W", "amount": 200, "currency": "EUR", "occurred_at": "2026-10-02"},
]


class _Antwort:
    def __init__(self, users):
        self._u = users

    def json(self):
        return {"users": self._u}


def main():
    stubs = {"ADMIN_EXCLUDE_EMAILS": {"ausgeblendet@example.com"},
             "_auth_liste_anfrage": lambda: _Antwort(USERS),
             "admin_gruppen_daten": lambda: GRUPPEN,
             "_sb_all": lambda tabelle, params: TXS if (tabelle == "transactions" and params.get("kind") == "eq.payout") else []}
    ns, app = lade(stubs)

    # (A) Token
    ok = ns["ht_payouts_token_ok"]
    check(not ok(TOKEN, None), "A1 Variable fehlt → nie offen")
    check(not ok("kurz", "kurz"), "A2 Variable zu kurz → nie offen")
    check(not ok(None, TOKEN), "A3 kein Token → nein")
    check(not ok(TOKEN[:-1] + "x", TOKEN), "A4 falscher Token → nein")
    check(ok(TOKEN, TOKEN), "A5 richtiger Token → ja")

    # (B) Abgrenzung
    disp, aus = ns["ht_payouts_ausblenden"](USERS, {"ausgeblendet@example.com"}, GRUPPEN)
    check(aus == {C, E}, "B1 ausgeblendet = ADMIN_EXCLUDE + Verwalter-Gruppe")
    check(disp[B] == B[:8] and not {u["email"] for u in USERS} & set(disp.values()), "B2 Namen nie aus der Mail")
    try:
        ns["ht_payouts_ausblenden"]([], set(), {})
        check(False, "B3 leere Nutzerliste → Fehler")
    except RuntimeError:
        check(True, "B3 leere Nutzerliste → Fehler")
    for leer, name in (({}, "id_gruppen leer/fehlt"), ({"gruppen": [{"id": "g1", "name": "HT", "verwalter_id": None}], "mitglieder": []}, "nur Gruppe ohne Verwalter")):
        try:
            ns["ht_payouts_ausblenden"](USERS, set(), leer)
            check(False, f"B4 {name} → Fehler (fail-closed)")
        except RuntimeError:
            check(True, f"B4 {name} → Fehler (fail-closed)")

    # (C) CSV
    text = ns["ht_payouts_csv"](TXS, disp, aus)
    zeilen = text.strip().split("\n")
    check(zeilen[0] == "Datum,Betrag,Währung,ID,Zweck,Transaktions-ID", "C1 Kopfzeile")
    check(len(zeilen) == 5, f"C2 nur die vier HT-Payouts ab 30.05.2026 (ausgeblendete + t5 vom 29.05. fehlen) ({len(zeilen) - 1})")
    check("t5" not in text and "vor dem Zeitraum" not in text, "C2b Payout vor dem 30.05.2026 fehlt")
    check(zeilen[1].startswith('2026-09-25,"3476,14",EUR,bbbbbbbb,Apex Trader,t1'), "C3 Sortierung + Dezimalkomma + ID ohne Namen")
    check(zeilen[2].startswith('2026-10-23,"4050,00",USD,Finn + Pascal,Tradeify · 150k TDFYSL150000000001 → Winning Days,t2'), "C4 Zweck = Firma · Konto, Währung groß")
    check("example.com" not in text.replace("x.example", ""), "C5 keine Mailadressen im CSV")
    check(zeilen[3].startswith('2026-10-24,"50,00",EUR,Finn + Pascal,"\'=IMPORTXML('), f"C6 Zweck mit = vorne → ' davor ({zeilen[3]})")
    check(zeilen[4] == "2026-10-25,\"10,00\",'-1+1,'@Kunde,'+Firma,t7", f"C7 Währung/ID/Zweck mit - @ + vorne → ' davor ({zeilen[4]})")
    sicher = ns["ht_payouts_csv_sicher"]
    check(sicher("\tx") == "'\tx" and sicher("\rx") == "'\rx" and sicher("Apex") == "Apex" and sicher(None) == "", "C8 Tab/CR vorne → ' davor, normaler Text bleibt")

    # (D) Route
    cl = app.test_client()
    os.environ.pop("HT_PAYOUTS_CSV_TOKEN", None)
    check(cl.get(f"/ht/payouts.csv?token={TOKEN}").status_code == 404, "D1 Variable fehlt → 404")
    os.environ["HT_PAYOUTS_CSV_TOKEN"] = TOKEN
    check(cl.get("/ht/payouts.csv").status_code == 404, "D2 ohne Token → 404")
    check(cl.get("/ht/payouts.csv?token=falsch").status_code == 404, "D3 falscher Token → 404")
    r = cl.get(f"/ht/payouts.csv?token={TOKEN}")
    check(r.status_code == 200 and r.headers["Content-Type"].startswith("text/csv") and r.headers.get("Cache-Control") == "no-store",
          "D4 richtiger Token → 200, text/csv, no-store")
    check(r.get_data(as_text=True) == text, "D5 Inhalt = CSV der HT-Payouts")
    check(cl.post(f"/ht/payouts.csv?token={TOKEN}").status_code == 405, "D6 nur GET")
    ns["admin_gruppen_daten"] = lambda: {}
    r = cl.get(f"/ht/payouts.csv?token={TOKEN}")
    check(r.status_code == 502 and "Emin" not in r.get_data(as_text=True), "D8 id_gruppen leer → 502, Emin-Gruppe nie ungefiltert")
    ns["admin_gruppen_daten"] = lambda: GRUPPEN
    def kaputt(tabelle, params):
        raise RuntimeError("Supabase weg")
    ns["_sb_all"] = kaputt
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        r = cl.get(f"/ht/payouts.csv?token={TOKEN}")
    check(r.status_code == 502 and TOKEN not in log.getvalue() and TOKEN not in r.get_data(as_text=True), "D7 Lesefehler → 502, Token nicht im Log")
    os.environ.pop("HT_PAYOUTS_CSV_TOKEN", None)

    print(f"\n{'ALLES GRÜN' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
