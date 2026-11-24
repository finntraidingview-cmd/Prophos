"""Selbsttest BK6 Kontoauszug + Abgleich (25.11.2026) — bank_auszug.py ohne Netz: Zahlen/Datum, CSV (Revolut), KI-Antwort, Art-Vorschlag,
Abgleich (±3 Tage, Cent, Duplikate), Fälligkeit, Routen mit gefälschtem Gate/Supabase/Storage (Rechte je Gruppe, nur fehlende Zeilen
übernehmen, Vorzeichen folgt der Art, Fehlerantwort ohne Inhalt).

Aufruf: python3 tools/selftest_bk6_kontoauszug.py   → „ALLES GRÜN“ oder Exit 1. Nur Beispieldaten, keine echten Konten."""
import base64
import os
import sys
import warnings
from datetime import date

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from flask import Flask  # noqa: E402

import kapital_app as K  # noqa: E402
import bank_app as BA  # noqa: E402
import bank_auszug as AZ  # noqa: E402

fehler = []


def pruef(name, ok):
    print(("  ok  " if ok else "  FEHLER ") + name)
    if not ok:
        fehler.append(name)


# ── rein rechnend ──
pruef("zahl 1.234,56", AZ.zahl("1.234,56") == 1234.56)
pruef("zahl 1,234.56", AZ.zahl("1,234.56") == 1234.56)
pruef("zahl −12,50 €", AZ.zahl("−12,50 €") == -12.5)
pruef("zahl leer → None", AZ.zahl("—") is None)
# Review BK6: weitere Formate
pruef("zahl 123,45- (Minus hinten)", AZ.zahl("123,45-") == -123.45)
pruef("zahl 1.234.567", AZ.zahl("1.234.567") == 1234567.0)
pruef("zahl 1.000 = tausend", AZ.zahl("1.000") == 1000.0)
pruef("zahl 0,125 = Dezimal", AZ.zahl("0,125") == 0.125)
pruef("datum 11/24/2026 (nur MM/DD möglich)", AZ.datum("11/24/2026") == "2026-11-24")
pruef("datum 05/11/2026 = 5. November", AZ.datum("05/11/2026") == "2026-11-05")
pruef("datum ISO mit Zeit", AZ.datum("2026-11-24 10:12:00") == "2026-11-24")
pruef("datum 24.11.26", AZ.datum("24.11.26") == "2026-11-24")
pruef("datum Unsinn → None", AZ.datum("31.02.2026") is None)

REV = ("Type,Product,Started Date,Completed Date,Description,Amount,Fee,Currency,State,Balance\n"
       "TOPUP,Current,2026-11-18 09:00:00,2026-11-18 09:01:00,OKX,6375.00,0.00,EUR,COMPLETED,6375.00\n"
       "CARD_PAYMENT,Current,2026-11-19 10:00:00,2026-11-19 10:00:05,Topstep,-215.00,0.00,EUR,COMPLETED,6160.00\n"
       "CARD_PAYMENT,Current,2026-11-20 10:00:00,2026-11-20 10:00:05,Lucid Trading,-975.00,2.50,EUR,COMPLETED,5182.50\n"
       "CARD_PAYMENT,Current,2026-11-21 10:00:00,,Apex,-99.00,0.00,EUR,PENDING,\n"
       "CARD_PAYMENT,Current,2026-11-22 10:00:00,2026-11-22 10:00:05,Tradeify,-80.00,0.00,EUR,REVERTED,5182.50\n")
c = AZ.csv_lesen(REV)
pruef("CSV: 3 gebuchte Zeilen (PENDING/REVERTED weg)", len(c["zeilen"]) == 3)
pruef("CSV: Gebühr im Betrag (−977,50)", c["zeilen"][2]["betrag"] == -977.5)
pruef("CSV: Zeitraum + Endsaldo + Währung", (c["von"], c["bis"], c["endsaldo"], c["waehrung"]) == ("2026-11-18", "2026-11-20", 5182.5, "EUR"))
c2 = AZ.csv_lesen("Buchungstag;Verwendungszweck;Betrag;Saldo\n24.11.2026;Miete;-1.200,00;3.800,00\n25.11.2026;Gehalt;2.500,00;6.300,00\n")
pruef("CSV deutsch mit ; und Komma", [z["betrag"] for z in c2["zeilen"]] == [-1200.0, 2500.0] and c2["endsaldo"] == 6300.0)
c3 = AZ.csv_lesen("Datum;Text;Betrag;Saldo\n24.11.2026;B;-10,00;90,00\n24.11.2026;A;-5,00;100,00\n20.11.2026;Z;5,00;105,00\nkaputt;x;y;z\n")
pruef("CSV absteigend: Endsaldo = oberste Zeile (90), 1 übersprungen", c3["endsaldo"] == 90.0 and c3["uebersprungen"] == 1)
try:
    AZ.csv_lesen("a,b\n1,2\n")
    pruef("CSV ohne Spalten → Fehler", False)
except ValueError:
    pruef("CSV ohne Spalten → Fehler", True)

AZ.B = BA
k = AZ.ki_antwort_lesen('Hier: {"von":"2026-11-18","bis":"2026-11-24","endsaldo":"2.824,50","waehrung":"eur",'
                        '"vorschlag":{"bank":"Revolut","iban":"DE88 3704 0044 0532 0130 00"},'
                        '"zeilen":[{"datum":"18.11.2026","betrag":6375,"text":"OKX"},{"datum":"x","betrag":1},{"datum":"2026-11-22","betrag":0}]} Ende')
pruef("KI: nur gültige Zeilen, Endsaldo, Währung groß", len(k["zeilen"]) == 1 and k["endsaldo"] == 2824.5 and k["waehrung"] == "EUR")
pruef("KI: ungültige IBAN wird kein Vorschlag", k["vorschlag"]["iban"] is None and k["vorschlag"]["bank"] == "Revolut")

pruef("Art: + OKX → Zahlung von HT", AZ.art_vorschlag(6375, "OKX") == "Zahlung von HT")
pruef("Art: + TopstepTrader → Payout", AZ.art_vorschlag(3190, "TopstepTrader LLC") == "Payout")
pruef("Art: − Lucid → Account-Kauf", AZ.art_vorschlag(-975, "Lucid Trading") == "Account-Kauf")
pruef("Art: − Gebühr → Account-Kauf", AZ.art_vorschlag(-2.5, "Revolut Gebühr") == "Account-Kauf")
pruef("Art: − an Finn → Zahlung an HT", AZ.art_vorschlag(-500, "Finn Hermann") == "Zahlung an HT")

Z = [{"datum": "2026-11-18", "betrag": 6375, "text": "OKX"}, {"datum": "2026-11-21", "betrag": -217, "text": "Topstep"},
     {"datum": "2026-11-21", "betrag": -217, "text": "Topstep"}, {"datum": "2026-11-22", "betrag": -2.5, "text": "Revolut Gebühr"}]
BU = [{"id": "b1", "datum": "2026-11-18", "betrag": 6375}, {"id": "b2", "datum": "2026-11-24", "betrag": -217},
      {"id": "b3", "datum": "2026-11-20", "betrag": -217}, {"id": "b4", "datum": "2026-11-23", "betrag": -1},
      {"id": "b0", "datum": "2026-10-01", "betrag": 100}]
g = AZ.abgleich(Z, BU, start_saldo=0, von="2026-11-18", bis="2026-11-24", endsaldo=6038.5)
pruef("Abgleich: 3 passen (Duplikat −217 zweimal, je Buchung einmal)", sorted(p["buchung_id"] for p in g["passt"]) == ["b1", "b2", "b3"])
pruef("Abgleich: Gebühr fehlt in Prophos mit Vorschlag", g["fehlt"] == [{"i": 3, "art": "Account-Kauf"}])
pruef("Abgleich: −1 nur in Prophos (Oktober-Zeile nicht, außerhalb)", g["nur"] == ["b4"])
pruef("Abgleich: Saldo Prophos + Differenz", g["saldo_prophos"] == 6040.0 and g["differenz"] == -1.5)
g2 = AZ.abgleich([{"datum": "2026-11-10", "betrag": -50}], [{"id": "x", "datum": "2026-11-14", "betrag": -50}])
pruef("Abgleich: 4 Tage daneben → kein Treffer", not g2["passt"] and g2["fehlt"][0]["i"] == 0)
g3 = AZ.abgleich([{"datum": "2026-11-10", "betrag": -50.004}], [{"id": "x", "datum": "2026-11-13", "betrag": -50}])
pruef("Abgleich: 3 Tage + Cent-genau → Treffer", [p["buchung_id"] for p in g3["passt"]] == ["x"])
g4 = AZ.abgleich([{"datum": "2026-11-01", "betrag": 100}, {"datum": "2026-11-04", "betrag": 100}],
                 [{"id": "X", "datum": "2026-11-02", "betrag": 100}, {"id": "Y", "datum": "2026-10-29", "betrag": 100}])
pruef("Abgleich: größtmögliche Zuordnung (1↔Y, 2↔X)", sorted((p["i"], p["buchung_id"]) for p in g4["passt"]) == [(0, "Y"), (1, "X")] and not g4["fehlt"])
g5 = AZ.abgleich([{"datum": "2026-11-10", "betrag": -50}], [{"id": "u", "datum": "2026-11-10", "betrag": 50, "auszug_id": "A", "auszug_zeile": 0}], auszug_id="A")
pruef("Abgleich: übernommene Zeile bleibt fest zugeordnet (auch mit anderem Vorzeichen)", g5["passt"] == [{"i": 0, "buchung_id": "u"}] and not g5["fehlt"] and not g5["nur"])
pruef("Fällig: 21 Tage ja, 20 nein, kein Auszug None",
      AZ.faellig("2026-11-01", date(2026, 11, 22)) == 21 and AZ.faellig("2026-11-02", date(2026, 11, 22)) is None and AZ.faellig(None) is None)

# ── Routen mit Fälschungen ──
HT, EMIN = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
U_HT, U_EM = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
K_HT, K_EM = "cccccccc-cccc-cccc-cccc-cccccccccccc", "dddddddd-dddd-dddd-dddd-dddddddddddd"
AU_HT = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
DB = {
    "id_gruppen": [{"id": HT, "name": "HT", "verwalter_user_id": None}, {"id": EMIN, "name": "Emin", "verwalter_user_id": U_EM}],
    "id_gruppe_mitglied": [{"user_id": U_HT, "gruppe_id": HT}, {"user_id": U_EM, "gruppe_id": EMIN}],
    "bank_konten": [{"id": K_HT, "user_id": U_HT, "start_saldo": 0}, {"id": K_EM, "user_id": U_EM, "start_saldo": 0}],
    "bank_buchungen": [dict(b, konto_id=K_HT) for b in BU],
    "bank_auszuege": [{"id": AU_HT, "konto_id": K_HT, "status": "gelesen", "zeilen": Z, "von": "2026-11-18", "bis": "2026-11-24",
                       "endsaldo": 6038.5, "datei_pfad": f"{K_HT}/{AU_HT}.pdf", "created_at": "2026-11-25T00:00:00Z"}],
}
eingefuegt, storage = [], []


def _filter(rows, params):
    out = rows
    for kk, v in (params or {}).items():
        if isinstance(v, str) and v.startswith("eq."):
            out = [r for r in out if str(r.get(kk)) == v[3:]]
        elif isinstance(v, str) and v.startswith("in.("):
            m = set(v[4:-1].split(","))
            out = [r for r in out if str(r.get(kk)) in m]
    return out


def f_sb(methode, tabelle, params=None, body=None, prefer=None, timeout=15):
    return _filter(DB.get(tabelle, []), params) if methode == "GET" else []


class Boom(Exception):
    pass


def f_insert(t, body):
    if t == "bank_auszuege":
        z = dict(body, id="ffffffff-ffff-ffff-ffff-ffffffffffff")
        DB["bank_auszuege"].append(z)
        return z
    if isinstance(body, list) and any("DE89" in str(x.get("text")) for x in body):
        raise Boom("Failing row contains (DE89370400440532013000)")
    eingefuegt.extend(body if isinstance(body, list) else [body])
    return body


def f_update(t, p, b):
    for r in _filter(DB.get(t, []), p):
        r.update(b)
    return [b]


class Antwort:
    def __init__(self, code=200, daten=None):
        self.status_code, self._d = code, daten or {}

    def json(self):
        return self._d


class Sitzung:
    def request(self, methode, url, **kw):
        storage.append((methode, url.split("/storage/v1/")[1]))
        if "/sign/" in url:
            return Antwort(200, {"signedURL": "/object/sign/x?token=t"})
        return Antwort(200)


ROLLE = {"erlaubt": None}
K._sb = f_sb
K._gate = lambda: (ROLLE["erlaubt"], None)
K._admin_uid = lambda: "tester"
AZ.threading.Thread = lambda target, args, **kw: type("T", (), {"start": lambda self: target(*args)})()   # synchron
app = Flask("t")
BA.registrieren(app, {"_sb_all": lambda t, p: _filter(DB.get(t, []), p), "sb_insert": f_insert, "sb_update": f_update,
                      "_auth_liste_anfrage": lambda: None, "SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_KEY": "k",
                      "_SB_SESSION": Sitzung()})
c = app.test_client()

d = c.get(f"/admin/bank/auszug?konto={K_HT}").get_json()
pruef("GET: Abgleich des letzten Auszugs", d["ok"] and len(d["abgleich"]["passt"]) == 3 and d["abgleich"]["differenz"] == -1.5)
ROLLE["erlaubt"] = {EMIN}
pruef("Verwalter: fremdes Konto → 404", c.get(f"/admin/bank/auszug?konto={K_HT}").status_code == 404)
r = c.post("/admin/bank/auszug/uebernehmen", json={"auszug_id": AU_HT, "zeilen": [{"i": 3, "art": "Account-Kauf"}]})
pruef("Verwalter: fremden Auszug übernehmen → 404, nichts gebucht", r.status_code == 404 and not eingefuegt)
ROLLE["erlaubt"] = None
r = c.post("/admin/bank/auszug/uebernehmen", json={"auszug_id": AU_HT, "zeilen": [{"i": 0, "art": "Zahlung von HT"}, {"i": 3, "art": "Account-Kauf"}, {"i": 3, "art": "Account-Kauf"}]})
pruef("Übernehmen: nur die fehlende Zeile, einmal, Vorzeichen −, quelle auszug",
      r.status_code == 200 and len(eingefuegt) == 1 and eingefuegt[0]["betrag"] == -2.5 and eingefuegt[0]["quelle"] == "auszug"
      and eingefuegt[0]["auszug_id"] == AU_HT)
r = c.post("/admin/bank/auszug/uebernehmen", json={"auszug_id": AU_HT, "zeilen": [{"i": 3, "art": "Gebühr"}]})
pruef("Übernehmen: alte Art → nichts", r.status_code == 400)
pruef("Übernehmen: Zeile gemerkt (auszug_zeile)", eingefuegt[0].get("auszug_zeile") == 3)
DB["bank_buchungen"].append(dict(eingefuegt[0], id="neu1"))
r = c.post("/admin/bank/auszug/uebernehmen", json={"auszug_id": AU_HT, "zeilen": [{"i": 3, "art": "Account-Kauf"}]})
pruef("Übernehmen: dieselbe Zeile nochmal → nichts (passt jetzt)", r.status_code == 400 and len(eingefuegt) == 1)
DB["bank_buchungen"].pop()
r = c.post("/admin/bank/auszug", json={"konto_id": K_HT, "typ": "pdf", "name": "a.pdf", "daten": base64.b64encode(b"kein pdf").decode()})
pruef("Upload: kein PDF → 400", r.status_code == 400)
r = c.post("/admin/bank/auszug", json={"konto_id": K_HT, "typ": "exe", "daten": "AA=="})
pruef("Upload: falscher Typ → 400", r.status_code == 400)
r = c.post("/admin/bank/auszug", json={"konto_id": K_HT, "typ": "csv", "name": "rev.csv", "daten": base64.b64encode(REV.encode()).decode()})
neu = [a for a in DB["bank_auszuege"] if a["id"].startswith("ffff")]
pruef("Upload CSV: Datei in den Bucket, gelesen, 3 Zeilen",
      r.status_code == 200 and any(m == "POST" and u.startswith("object/kontoauszuege/") for m, u in storage)
      and neu and neu[0]["status"] == "gelesen" and len(neu[0]["zeilen"]) == 3)
r = c.post("/admin/bank/auszug/datei", json={"id": AU_HT})
pruef("Datei: signierter Link", r.status_code == 200 and "/storage/v1/object/sign/" in r.get_json()["url"])
DB["bank_auszuege"][0]["zeilen"] = Z + [{"datum": "2026-11-23", "betrag": -7, "text": "DE89370400440532013000"}]
r = c.post("/admin/bank/auszug/uebernehmen", json={"auszug_id": AU_HT, "zeilen": [{"i": 4, "art": "Payout"}]})
pruef("Übernehmen: Art mit falschem Vorzeichen → 400", r.status_code == 400 and len(eingefuegt) == 1)
r = c.post("/admin/bank/auszug/uebernehmen", json={"auszug_id": AU_HT, "zeilen": [{"i": 4, "art": "Zahlung an HT"}]})
txt = r.get_data(as_text=True)
pruef("DB-Fehler → 502 ohne Inhalt/IBAN", r.status_code == 502 and "DE89" not in txt and "Failing" not in txt)
pruef("Liste: letzter Auszug je Konto", BA.bank_auszug.letzte_je_konto([K_HT]).get(K_HT, {}).get("id") in (AU_HT, neu[0]["id"]))

# Speicher-Löschen meldet Fehlschlag (requests wirft bei 4xx nicht)
class Sitzung403(Sitzung):
    def request(self, methode, url, **kw):
        return Antwort(403)
AZ.A["_SB_SESSION"] = Sitzung403()
pruef("Datei löschen 403 → False", AZ.datei_loeschen(["x/y.pdf"]) is False)
r = c.delete("/admin/bank/konto", json={"id": K_HT})
pruef("Konto löschen: Dateien nicht löschbar → 502, Konto bleibt", r.status_code == 502)
AZ.A["_SB_SESSION"] = Sitzung()

print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER: {fehler}")
sys.exit(1 if fehler else 0)
