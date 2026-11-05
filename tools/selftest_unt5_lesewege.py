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


# ── 3) wd_konten_alle (SQL, nicht eingespielt) ──
def teil_wd_konten_alle():
    pfad = os.path.join(WURZEL, "sql", "2026-11-05_unt5_wd_konten_alle.sql")
    rb = os.path.join(WURZEL, "sql", "2026-11-05_unt5_wd_konten_alle_rueckbau.sql")
    if not os.path.exists(pfad):
        return
    neu, alt = open(pfad, encoding="utf-8").read(), open(rb, encoding="utf-8").read()
    fn = lambda t: t[t.index("CREATE OR REPLACE FUNCTION"):t.index("$function$;", t.index("CREATE OR REPLACE FUNCTION"))]  # noqa: E731
    import difflib, hashlib
    dazu = [z[1:] for z in difflib.unified_diff(fn(alt).splitlines(), fn(neu).splitlines(), lineterm="", n=0) if z.startswith("+") and not z.startswith("+++")]
    weg = [z for z in difflib.unified_diff(fn(alt).splitlines(), fn(neu).splitlines(), lineterm="", n=0) if z.startswith("-") and not z.startswith("---")]
    check(not weg and len(dazu) == 4 and "a.user_id = auth.uid()" in dazu[1] and "prophos_gruppe_von(a.user_id) = public.prophos_gruppe_von(auth.uid())" in dazu[3],
          "3a wd_konten_alle: einzige Änderung = Filter eigenes Unternehmen (ohne Unternehmen nur eigene), Rest zeichengleich")
    check(hashlib.md5((fn(alt) + "$function$\n").encode()).hexdigest() == "62d4b9ecdb11a7a852cccf86f309e35d", "3b Rückbau = Live-Fassung vom 05.11. (md5)")
    check("revoke execute on function public.wd_konten_alle() from anon;" in neu and "begin;" in neu and "commit;" in neu, "3c anon ohne EXECUTE, eine Transaktion")


# ── 4) pc_namen_route ──
def teil_pc_namen():
    n = lade(NEU_SRC, HELFER + ("pc_namen_zuordnen", "pc_namen_besitzer", "pc_namen_sicht"))
    live = [{"pc_name": "pc-ht0001", "user_id": M, "updated_at": "2"}, {"pc_name": "pc-ht0001", "user_id": A, "updated_at": "1"},
            {"pc_name": "pc-em0001", "user_id": X, "updated_at": "3"}, {"pc_name": "pc-oh0001", "user_id": O, "updated_at": "3"}]
    tabelle = [{"pc_id": "pc-ht0001", "name": "Mike"}, {"pc_id": "pc-em0001", "name": "Ahaj"}, {"pc_id": "pc-nix001", "name": "Unbekannt"}]
    disp = {A: "Finn + Pascal", M: "Mike", X: "Amir", O: "Neu"}
    daten = n["pc_namen_zuordnen"](tabelle, live, disp)
    bes = n["pc_namen_besitzer"](live)
    check(bes == {"pc-ht0001": M, "pc-em0001": X, "pc-oh0001": O}, "4a Besitzer = jüngste Meldung je PC")
    s = n["pc_namen_sicht"]
    ht = s(daten, bes, n["ap_unternehmen_von_login"](A, DATEN))
    em = s(daten, bes, n["ap_unternehmen_von_login"](E, DATEN))
    check(set(daten) == {"pc-ht0001", "pc-em0001", "pc-oh0001", "pc-nix001"}, "4b vorher: jeder Login bekam alle PC-Namen (auch Emins, ohne Besitzer)")
    check(ht == {k: v for k, v in daten.items() if k == "pc-ht0001"}, "4c HT-Admin: nur HT-PCs, Einträge unverändert (Name + Quelle)")
    check(set(em) == {"pc-em0001"}, "4d Emin: nur Emins PCs")
    check(set(s(daten, bes, lambda u: str(u) == O)) == {"pc-oh0001"}, "4e fail-closed/ohne Unternehmen: nur PCs der eigenen ID; PC ohne Besitzer nie")
    i = NEU_SRC.index("\ndef pc_namen_route(")
    r = NEU_SRC[i:NEU_SRC.index("\n\n\n", i)]
    check("pc_namen_sicht(daten, _pc_namen_cache.get(\"besitzer\") or {}, unt_sicht_login(me))" in r and "besitzer=besitzer" in NEU_SRC,
          "4f Route filtert je Login, Besitzer im Cache von _pc_namen_daten (Reader-Meldungen _rw_pc_namen unverändert)")


# ── 5) prophos_fremd_konflikte (Railway-Filter sofort + SQL, nicht eingespielt) ──
def teil_fremd_konflikte():
    n = lade(NEU_SRC, HELFER + ("ap_unternehmen_karte", "ap_unternehmen_schluessel", "fp_konflikte_filter", "fp_konflikte_je_unternehmen"))
    offen = [{"id": 1, "user_id": M}, {"id": 2, "user_id": X}, {"id": 3, "user_id": O}]
    k = [{"fremd_id": 1, "gegen_user": A, "gegen_id": "p-ht"}, {"fremd_id": 1, "gegen_user": X, "gegen_id": "p-em"},
         {"fremd_id": 2, "gegen_user": E, "gegen_id": "p-em2"}, {"fremd_id": 2, "gegen_user": M, "gegen_id": "p-ht2"},
         {"fremd_id": 3, "gegen_user": O, "gegen_id": "p-o"}, {"fremd_id": 3, "gegen_user": A, "gegen_id": "p-ht3"}]
    karte = n["ap_unternehmen_karte"](DATEN)
    erg = [x["gegen_id"] for x in n["fp_konflikte_filter"](k, offen, karte)]
    check(erg == ["p-ht", "p-em2", "p-o"], f"5a nur Konflikte im eigenen Unternehmen: HT↔HT, Emin↔Emin, ohne Unternehmen nur mit sich ({erg})")
    check([x["gegen_id"] for x in n["fp_konflikte_filter"](k[:1], offen, {})] == ["p-ht"] and
          len(n["fp_konflikte_filter"](k, offen, {})) == len(k), "5b ohne Gruppen-Tabellen: alles wie bisher")
    n["admin_gruppen_daten"] = lambda: (_ for _ in ()).throw(RuntimeError("weg"))
    check([x["gegen_id"] for x in n["fp_konflikte_je_unternehmen"](k, offen)] == ["p-o"], "5c Gruppen nicht lesbar → nur Konflikte derselben ID")
    i = NEU_SRC.index("\ndef fp_tick(")
    ft = NEU_SRC[i:NEU_SRC.index("\ndef ", i + 10)]
    check("konflikte = fp_konflikte_je_unternehmen(r.json() or [], offen)" in ft and "_admins_fuer_uid(f.get(\"user_id\"), admins or set())" in ft,
          "5d fp_tick: Konflikte je Unternehmen, Push nur an die Admins des Unternehmens")
    pfad = os.path.join(WURZEL, "sql", "2026-11-05_unt5_fremd_konflikte.sql")
    rb = os.path.join(WURZEL, "sql", "2026-11-05_unt5_fremd_konflikte_rueckbau.sql")
    if os.path.exists(pfad):
        import difflib, hashlib
        neu, alt = open(pfad, encoding="utf-8").read(), open(rb, encoding="utf-8").read()
        fn = lambda t: t[t.index("CREATE OR REPLACE FUNCTION"):t.index("end $function$", t.index("CREATE OR REPLACE FUNCTION")) + len("end $function$")]  # noqa: E731
        d = [z for z in difflib.unified_diff(fn(alt).splitlines(), fn(neu).splitlines(), lineterm="", n=0) if z[:1] in "+-" and z[:3] not in ("+++", "---")]
        weg = [z for z in d if z.startswith("-")]
        check(weg == ["-     and g.seit between f.seit - w and f.seit + w;"] and sum(1 for z in d if "prophos_gruppe_von(" in z) == 4,
              "5e SQL: beide Joins nur im eigenen Unternehmen, sonst zeichengleich")
        check(hashlib.md5((fn(alt) + "\n").encode()).hexdigest() == "9bb3a0198249043c7a3ed3cfdfbdb44f", "5f Rückbau = Live-Fassung (md5)")


# ── 6) Ziel-Wache-Push ──
def teil_ziel_wache():
    i = NEU_SRC.index("\ndef zw_tick(")
    zt = NEU_SRC[i:NEU_SRC.index("\ndef ", i + 10)]
    check('for uid in {str(a.get("user_id"))} | _admins_fuer_uid(a.get("user_id"), admins or set()):' in zt
          and '"🎯 Ziel erreicht"' in zt and "(admins or set()):\n                push_an_user(uid, \"🎯" not in zt,
          "6a zw_tick: „Ziel erreicht“ nur an Besitzer + Admins seines Unternehmens")
    n = lade(NEU_SRC, HELFER)
    emp = lambda uid: {uid} | n["_admins_fuer_uid"](uid, {A})  # noqa: E731
    check(emp(M) == {M, A} and emp(X) == {X, E} and emp(E) == {E} and emp(O) == {O}, "6b HT-Konto → Besitzer + HT-Admin (wie vorher), Emin-Konto → Besitzer + Emin, ohne Unternehmen → nur Besitzer")
    n["admin_gruppen_daten"] = lambda: (_ for _ in ()).throw(RuntimeError("weg"))
    check(emp(M) == {M}, "6c Gruppen nicht lesbar → nur der Besitzer")


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
