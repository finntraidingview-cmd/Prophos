#!/usr/bin/env python3
"""Selbsttest UNT5 (05.11.2026, Master/Finn: „Finn + Pascal sehen als HT-Admins nichts von Emin, und Emin sieht nichts von HT"): Lesewege im
Backend nur im eigenen Unternehmen, fail-closed (Unternehmen unbekannt → nur die eigene ID). Ohne Netz, Platzhalter-IDs:
HT = A (Admin, ADMIN_EMAILS), M (Mitglied); Emin-Gruppe = E (Verwalter), X (Mitglied); O = ohne Unternehmen.
Je Weg: HT-Admin-Sicht VORHER (app.py aus BASIS, git show) == NACHHER ohne die Emin-Zeilen; Emin-Zeilen nie bei HT; fail-closed.
Aufruf: python3 tools/selftest_unt5_lesewege.py [basis-commit, Standard: 53f924ac = main vor UNT5]"""
import json
import os
import re
import subprocess
import sys
import types

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
BASIS = sys.argv[1] if len(sys.argv) > 1 else "53f924ac"   # main-Commit vor UNT5
FEHLER = []
A, M, E, X, O = ("00000000-0000-4000-8000-00000000000a", "00000000-0000-4000-8000-00000000000b", "00000000-0000-4000-8000-00000000000e",
                 "00000000-0000-4000-8000-00000000000f", "00000000-0000-4000-8000-000000000001")
DATEN = {"gruppen": [{"id": "g-ht", "name": "Hermann Technologies", "verwalter_id": None}, {"id": "g-emin", "name": "Emin", "verwalter_id": E}],
         "mitglieder": [{"user_id": A, "gruppe_id": "g-ht"}, {"user_id": M, "gruppe_id": "g-ht"}, {"user_id": X, "gruppe_id": "g-emin"}]}
USERS = [{"id": A, "email": "finn@example.invalid", "user_metadata": {"name": "Finn + Pascal"}},
         {"id": M, "email": "mike@example.invalid", "user_metadata": {"name": "Mike"}},
         {"id": E, "email": "emin@example.invalid", "user_metadata": {"name": "Emin"}},
         {"id": X, "email": "amir@example.invalid", "user_metadata": {"name": "Amir"}},
         {"id": O, "email": "neu@example.invalid", "user_metadata": {"name": "Neu"}}]


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        FEHLER.append(text)


NEU_SRC = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
ALT_SRC = subprocess.run(["git", "-C", WURZEL, "show", f"{BASIS}:app.py"], capture_output=True, text=True).stdout


def block(src, name):
    i = src.index(f"\ndef {name}(") + 1
    j = src.find("\n\n\n", i)
    return src[i:j]


def lade(src, namen, extra=None):
    """Funktionen aus src in einen Namensraum; Namen, die es dort nicht gibt (Basis vor UNT5), fallen weg."""
    ns = {"re": re, "json": json, "print": lambda *a, **k: None, "admin_gruppen_daten": lambda: DATEN}
    ns.update(extra or {})
    code = [block(src, n) for n in namen if f"\ndef {n}(" in src]
    exec("\n".join(code), ns)
    return ns


class _Antwort:
    def __init__(self, d):
        self._d = d

    def json(self):
        return self._d


HELFER = ("_admin_verwalter_gruppen_ids", "ap_unternehmen_filter", "ap_unternehmen_ids", "ap_unternehmen_von_login", "unt_sicht_login",
          "ap_admins_fuer", "_admins_fuer_uid")


# ── 0) Helfer ──
def teil_helfer():
    n = lade(NEU_SRC, HELFER)
    s = n["ap_unternehmen_von_login"]
    ht, em, oh = s(A, DATEN), s(X, DATEN), s(O, DATEN)
    check(ht(A) and ht(M) and not ht(E) and not ht(X) and not ht(O), "0a HT-Login sieht HT (A, M), nicht Emin (E, X), nicht ohne Unternehmen (O)")
    check(em(E) and em(X) and not em(A) and not em(M) and not em(O), "0b Emin-Login (Mitglied) sieht Emin + Verwalter, nicht HT")
    check(oh(O) and not oh(A) and not oh(X), "0c ohne Unternehmen: nur sich selbst")
    n["admin_gruppen_daten"] = lambda: (_ for _ in ()).throw(RuntimeError("weg"))
    f = n["unt_sicht_login"](A)
    check(f(A) and not f(M), "0d Gruppen nicht lesbar → nur die eigene ID (fail-closed)")
    a = n["ap_admins_fuer"]
    check(a(M, {A}, DATEN) == {A} and a(X, {A}, DATEN) == {E} and a(E, {A}, DATEN) == {E} and a(O, {A}, DATEN) == set(),
          "0e Admins je Unternehmen: HT → HT-Admins, Emin → Emin, ohne Unternehmen → keiner")
    check(n["_admins_fuer_uid"](M, {A}) == set(), "0f Admins: Gruppen nicht lesbar → keiner (nur Besitzer)")
    check(a(M, {A}, {"gruppen": [], "mitglieder": []}) == {A}, "0g ohne Gruppen-Tabellen: wie vor den Gruppen (HT-Admins)")


# ── 1) Liquide ──
def liquide_lauf(src, login, daten_fehler=False):
    sheets = [{"id": 1, "person_uid": M, "person_name": "Mike", "sheet_id": "s-m", "aktiv": True},
              {"id": 2, "person_uid": X, "person_name": "Amir", "sheet_id": "s-x", "aktiv": True}]
    staende = [{"sheet_id": "s-m", "day": "2026-11-05", "kontostand": 1000, "diff": 0}, {"sheet_id": "s-x", "day": "2026-11-05", "kontostand": 700, "diff": 0}]
    pending = [{"user_id": M, "amount": 100, "currency": "EUR", "requested_at": "1"}, {"user_id": X, "amount": 50, "currency": "EUR", "requested_at": "2"},
               {"user_id": E, "amount": 70, "currency": "EUR", "requested_at": "3"}]

    def _sb_all(tab, q):
        return {"kunden_sheets": sheets, "bank_staende": staende, "liq_personen": [], "pending_payouts": pending}[tab]
    req = types.SimpleNamespace(environ={"prophos.admin_uid": login})
    extra = {"_sb_all": _sb_all, "_auth_liste_anfrage": lambda: _Antwort({"users": USERS}), "request": req, "datetime": __import__("datetime").datetime,
             "timezone": __import__("datetime").timezone, "_ap_tz": __import__("zoneinfo").ZoneInfo, "LQ_VERLAUF_TAGE": 30, "LQ_TOLERANZ_EUR": 1,
             "ADMIN_EXCLUDE_EMAILS": {"emin@example.invalid"}, "ADMIN_EMAILS": {"finn@example.invalid"}, "_lq_fx": lambda: 0.9,
             "_wd_num": lambda v: float(v) if v is not None else None}
    if daten_fehler:
        extra["admin_gruppen_daten"] = lambda: (_ for _ in ()).throw(RuntimeError("weg"))
    ns = lade(src, HELFER + ("lq_kunde_flags", "lq_antwort", "_lq_antwort_laden"), extra)
    if daten_fehler:
        ns["admin_gruppen_daten"] = extra["admin_gruppen_daten"]
    return ns["_lq_antwort_laden"]()


def teil_liquide():
    alt, neu = liquide_lauf(ALT_SRC, A), liquide_lauf(NEU_SRC, A)
    check(any(p["user_id"] == X for p in alt["pending"]) and X in alt["kunde"], "1a vorher: Emins Mitglied stand in HTs Liquide (Payout + Kunden-Flag) — Lücke belegt")
    weg_x = lambda d: {**d, "sheets": [s for s in d["sheets"] if s["person_uid"] != X], "pending": [p for p in d["pending"] if p["user_id"] != X],  # noqa: E731
                       "kunde": {k: v for k, v in d["kunde"].items() if k not in (X, O)}}
    vergl = lambda d: json.dumps({k: d[k] for k in ("sheets", "pending", "kunde")}, sort_keys=True, default=str)  # noqa: E731
    check(vergl(neu) == vergl(weg_x(alt)), "1b nachher: HT-Admin-Sicht = vorher ohne Emins Mitglied und ohne ID ohne Unternehmen")
    check(neu["summe_kunden_eur"] == 1000 and alt["summe_kunden_eur"] == 1700, "1c Summe Kundengeld nur HT (1.000 statt 1.700)")
    fz = liquide_lauf(NEU_SRC, A, daten_fehler=True)
    check(not fz["sheets"] and not fz["pending"] and set(fz["kunde"]) <= {A}, "1d Gruppen nicht lesbar → nur der Login selbst (nichts Fremdes)")


# ── 2) Kundenzahlungen ──
def kz_lauf(src, login, daten_fehler=False):
    rows = [{"id": 1, "user_id": M, "kind": "einzahlung", "amount": 300}, {"id": 2, "user_id": X, "kind": "einzahlung", "amount": 200},
            {"id": 3, "user_id": A, "kind": "einzahlung", "amount": 100}]
    req = types.SimpleNamespace(environ={"prophos.admin_uid": login})
    extra = {"_sb_all": lambda tab, q: [dict(r) for r in rows], "_auth_liste_anfrage": lambda: _Antwort({"users": USERS}), "request": req,
             "jsonify": lambda d: d, "_wb_info": {}}
    ns = lade(src, HELFER + ("_wb_antwort",), extra)
    if daten_fehler:
        ns["admin_gruppen_daten"] = lambda: (_ for _ in ()).throw(RuntimeError("weg"))
    return ns["_wb_antwort"]()


def teil_kundenzahlungen():
    alt, neu = kz_lauf(ALT_SRC, A), kz_lauf(NEU_SRC, A)
    ids = lambda d: sorted(z["user_id"] for z in d["zahlungen"])  # noqa: E731
    check(X in ids(alt), "2a vorher: Kundenzahlung von Emins Mitglied in HTs Liste — Lücke belegt")
    check(ids(neu) == sorted([M, A]) and [z for z in neu["zahlungen"]] == [z for z in alt["zahlungen"] if z["user_id"] != X],
          "2b nachher: HT-Admin-Sicht = vorher ohne Emins Zeile (Reihenfolge, Felder, E-Mail gleich)")
    check(ids(kz_lauf(NEU_SRC, A, daten_fehler=True)) == [A], "2c Gruppen nicht lesbar → nur die eigenen Zeilen des Logins")


def main():
    if not ALT_SRC:
        check(False, f"Basis {BASIS}:app.py nicht lesbar")
        return 1
    teil_helfer()
    teil_liquide()
    for name, f in list(globals().items()):
        if name.startswith("teil_") and name not in ("teil_helfer", "teil_liquide") and callable(f):   # weitere Wege in Reihenfolge
            f()
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
