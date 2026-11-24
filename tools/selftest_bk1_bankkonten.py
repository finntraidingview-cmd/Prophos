"""Selbsttest BK1 Bankkonten (24.11.2026) — bank_app.py ohne Netz: IBAN-Prüfung, Saldo, Feldprüfung und die Routen mit
gefälschtem Gate/Supabase (Verwalter nur seine Gruppe, fremde Konten 404, Fehlerantwort ohne Zeilenwerte).

Aufruf: python3 tools/selftest_bk1_bankkonten.py   → „ALLES GRÜN“ oder Exit 1.
Nur Beispiel-IBANs aus Lehrbüchern (DE89 3704 0044 0532 0130 00), keine echten Kontodaten (Repo öffentlich)."""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from flask import Flask  # noqa: E402

import kapital_app as K  # noqa: E402
import bank_app as B  # noqa: E402

fehler = []


def pruef(name, ok):
    print(("  ok  " if ok else "  FEHLER ") + name)
    if not ok:
        fehler.append(name)


# ── rein rechnend ──
pruef("IBAN mit Leerzeichen gültig", B.iban_normal("de89 3704 0044 0532 0130 00") == "DE89370400440532013000")
pruef("IBAN falsche Prüfziffer → ''", B.iban_normal("DE88370400440532013000") == "")
pruef("IBAN Unsinn → ''", B.iban_normal("hallo") == "")
pruef("IBAN leer → None", B.iban_normal("  ") is None)

konten = [{"id": "k1", "start_saldo": 0}, {"id": "k2", "start_saldo": 100}]
buch = [{"konto_id": "k1", "betrag": 6375, "datum": "2026-11-18"}, {"konto_id": "k1", "betrag": -1500, "datum": "2026-11-19"},
        {"konto_id": "k1", "betrag": -2048, "datum": "2026-11-24"}, {"konto_id": "kX", "betrag": 999, "datum": "2026-11-24"}]
s = B.saldo_rechnen(konten, buch)
pruef("Saldo = Start + Σ (2.827)", s["k1"]["saldo"] == 2827.0 and s["k1"]["anzahl"] == 3 and s["k1"]["letzte"] == "2026-11-24")
pruef("Konto ohne Buchungen = Startsaldo", s["k2"] == {"saldo": 100.0, "anzahl": 0, "letzte": None})

f, e = B._konto_felder({"user_id": "x", "iban": "DE89 3704 0044 0532 0130 00", "bic": "cobadeffxxx"}, True)
pruef("Konto neu: Standard Account-Kauf/EUR, IBAN normalisiert, BIC groß",
      e is None and f["zweck"] == "Account-Kauf" and f["waehrung"] == "EUR" and f["iban"] == "DE89370400440532013000" and f["bic"] == "COBADEFFXXX")
pruef("BIC mit Leerzeichen nicht verkürzt", B._konto_felder({"bic": "COBA DE FF XXX"}, False)[0]["bic"] == "COBADEFFXXX")
pruef("Konto: falsche IBAN → Fehler", B._konto_felder({"iban": "DE00123"}, False)[1] is not None)
pruef("Konto: Zweck unbekannt → Fehler", B._konto_felder({"zweck": "Privat"}, False)[1] is not None)
pruef("Konto PATCH nur gesendete Felder", B._konto_felder({"bank": "N26"}, False) == ({"bank": "N26"}, None))
pruef("Buchung 0 → Fehler", B._buchung_felder({"betrag": 0}, True)[1] is not None)
f, e = B._buchung_felder({"betrag": "-217", "datum": "2026-11-25", "art": "Account-Kauf", "text": "topstep acc"}, True)
pruef("Buchung ok", e is None and f == {"betrag": -217.0, "datum": "2026-11-25", "art": "Account-Kauf", "text": "topstep acc"})
pruef("Buchung Art unbekannt → Fehler", B._buchung_felder({"betrag": 5, "art": "Lotto"}, True)[1] is not None)

# ── Routen mit Fälschungen ──
HT, EMIN = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
U_HT, U_EM = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
K_HT, K_EM = "cccccccc-cccc-cccc-cccc-cccccccccccc", "dddddddd-dddd-dddd-dddd-dddddddddddd"
DB = {
    "id_gruppen": [{"id": HT, "name": "Hermann Technologies", "verwalter_user_id": None}, {"id": EMIN, "name": "Emin", "verwalter_user_id": U_EM}],
    "id_gruppe_mitglied": [{"user_id": U_HT, "gruppe_id": HT}, {"user_id": U_EM, "gruppe_id": EMIN}],
    "bank_konten": [{"id": K_HT, "user_id": U_HT, "zweck": "Account-Kauf", "iban": "DE89370400440532013000", "start_saldo": 0, "created_at": "1"},
                    {"id": K_EM, "user_id": U_EM, "zweck": "Account-Kauf", "iban": None, "start_saldo": 50, "created_at": "2"}],
    "bank_buchungen": [{"id": "b1", "konto_id": K_HT, "datum": "2026-11-24", "betrag": 353}],
}
geschrieben = []


def _filter(rows, params):
    out = rows
    for k, v in (params or {}).items():
        if not isinstance(v, str):
            continue
        if v.startswith("eq."):
            out = [r for r in out if str(r.get(k)) == v[3:]]
        elif v.startswith("in.("):
            menge = set(v[4:-1].split(",")) if v[4:-1] else set()
            out = [r for r in out if str(r.get(k)) in menge]
    return out


def f_sb(methode, tabelle, params=None, body=None, prefer=None, timeout=15):
    if methode == "GET":
        return _filter(DB.get(tabelle, []), params)
    if methode == "DELETE":
        geschrieben.append(("DELETE", tabelle, params))
        return []
    return None


class Boom(Exception):
    pass


def f_insert(tabelle, body):
    if body.get("text") == "boom":
        raise Boom("Failing row contains (DE89370400440532013000)")
    geschrieben.append(("POST", tabelle, body))
    return dict(body, id="neu")


ROLLE = {"erlaubt": None}
K._sb = f_sb
K._gate = lambda: (ROLLE["erlaubt"], None)
K._admin_uid = lambda: "tester"
app = Flask("t")
B.registrieren(app, {"_sb_all": lambda t, p: _filter(DB.get(t, []), p), "sb_insert": f_insert,
                     "sb_update": lambda t, p, b: [dict(b, id="x")], "_auth_liste_anfrage": lambda: None})
c = app.test_client()

ROLLE["erlaubt"] = None                       # Finn/Pascal
d = c.get("/admin/bank?ansicht=admin").get_json()
pruef("Admin Standard = HT, nur HT-Konto, Saldo 353", d["gruppe"]["id"] == HT and [k["id"] for k in d["konten"]] == [K_HT] and d["konten"][0]["saldo"] == 353.0)
d = c.get(f"/admin/bank?ansicht=admin&gruppe={EMIN}").get_json()
pruef("Admin Chip Emin → Emin-Konto", [k["id"] for k in d["konten"]] == [K_EM])

ROLLE["erlaubt"] = {EMIN}                     # Verwalter Emin
d = c.get(f"/admin/bank?ansicht=admin&gruppe={HT}").get_json()
pruef("Verwalter fragt HT → bekommt seine Gruppe", d["gruppe"]["id"] == EMIN and [k["id"] for k in d["konten"]] == [K_EM])
r = c.post("/admin/bank/konto", json={"user_id": U_HT, "iban": "DE89370400440532013000"})
pruef("Verwalter: Konto für HT-ID → 403", r.status_code == 403)
r = c.post("/admin/bank/buchung", json={"konto_id": K_HT, "betrag": 5, "datum": "2026-11-24"})
pruef("Verwalter: Buchung auf HT-Konto → 404", r.status_code == 404)
r = c.delete("/admin/bank/konto", json={"id": K_HT})
pruef("Verwalter: HT-Konto löschen → 404, nichts gelöscht", r.status_code == 404 and not any(x[0] == "DELETE" for x in geschrieben))
r = c.post("/admin/bank/buchung", json={"konto_id": K_EM, "betrag": -20, "datum": "2026-11-24", "art": "Gebühr"})
pruef("Verwalter: Buchung eigenes Konto ok, quelle hand", r.status_code == 200 and geschrieben[-1][2]["quelle"] == "hand")

ROLLE["erlaubt"] = None
r = c.post("/admin/bank/konto", json={"user_id": U_HT, "iban": "DE88370400440532013000"})
pruef("falsche IBAN → 400, nichts geschrieben", r.status_code == 400 and geschrieben[-1][1] != "bank_konten")
r = c.post("/admin/bank/buchung", json={"konto_id": K_HT, "betrag": 5, "datum": "2026-11-24", "text": "boom"})
txt = r.get_data(as_text=True)
pruef("DB-Fehler → 502 ohne Zeilenwerte/IBAN", r.status_code == 502 and "DE89" not in txt and "Failing" not in txt)
r = c.post("/admin/bank/konto", json={"user_id": "cccccccc-0000-0000-0000-000000000000"})
pruef("ID ohne Unternehmen → 403", r.status_code == 403)

print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER: {fehler}")
sys.exit(1 if fehler else 0)
