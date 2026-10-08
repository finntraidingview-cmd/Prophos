#!/usr/bin/env python3
"""Selbsttest Kontowert-Spalte (app.py, KONTOWERT-SPALTE, 07.10.2026) — GET /admin/kontowerte mit nachgebauter DB, ohne Netz.

Aufruf:  python3 tools/selftest_kontowerte.py
Lädt die Funktionen per Quelltext aus app.py (wie selftest_auto_kontowert: app.py zieht beim Import Flask und Threads) und hängt
die Route an eine eigene Flask-App. Prüft: Wert = ap_kontowert wie im Probelauf (keine zweite Rechnung), Stufe/Herkunft,
Gründe ohne Wert (keine Kernwerte, Live, keine Balance, archiviert), Gate (Admin alle, „nur eigene" und Nicht-Admin nur eigene,
nicht angemeldet 401) und den 60-s-Merker je Sicht. Kernwerte = FIRMEN aus selftest_auto_kontowert (eine Quelle)."""
import os
import re
import sys
import threading
import time

from flask import Flask, request, jsonify, g

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
sys.path.insert(0, HIER)
from selftest_auto_kontowert import FIRMEN  # noqa: E402

# Platzhalter-IDs, keine echten Konten
U1, U2 = "00000000-0000-0000-0000-0000000000b1", "00000000-0000-0000-0000-0000000000b2"
KONTEN = [
    {"id": "k-1", "user_id": U1, "name": "TDFY frisch", "firm": "Tradeify", "account_type": "challenge"},
    {"id": "k-2", "user_id": U1, "name": "TDFY E1", "firm": "Tradeify", "account_type": "challenge"},
    {"id": "k-3", "user_id": U1, "name": "FN 95k", "firm": "FundedNext", "account_type": "phase1"},
    {"id": "k-4", "user_id": U2, "name": "FN 105k", "firm": "FundedNext", "account_type": "phase1"},
    {"id": "k-5", "user_id": U2, "name": "Apex", "firm": "Apex Trader", "account_type": "challenge"},
    {"id": "k-6", "user_id": U2, "name": "BG", "firm": "Blue Guardian", "account_type": "phase1"},
    {"id": "k-7", "user_id": U2, "name": "Fusion", "firm": "Fusion Markets", "account_type": "live"},
    {"id": "k-8", "user_id": U1, "name": "ohne Balance", "firm": "Tradeify", "account_type": "challenge"},
    {"id": "k-9", "user_id": U1, "name": "alt", "firm": "Tradeify", "account_type": "challenge"},
    {"id": "k-10", "user_id": U2, "name": "Fusion CFD", "firm": "Fusion Markets", "account_type": "phase1"},
    {"id": "k-11", "user_id": U1, "name": "TDFY Funded", "firm": "Tradeify", "account_type": "funded"},
]
BAL = {"k-1": 150000, "k-2": 153600, "k-3": 95000, "k-4": 105000, "k-5": 148000, "k-6": 100000, "k-7": 5000, "k-9": 150000,
       "k-10": 100000, "k-11": 151200}


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "time": time, "threading": threading, "request": request, "jsonify": jsonify, "g": g}

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]

    def konst(name):
        return re.search(rf"^{name} = .*$", src, re.M).group(0)
    m = re.search(r"^AP_KW_TYP_NAME = \{.*?\}$", src, re.M | re.S)
    exec("\n".join([konst(k) for k in ("AP_GROESSE_TOLERANZ", "_KETTE_DLL_CACHE", "AP_KW_FUNDED", "AP_KW_PHASEN", "AP_KW_CACHE_S", "_ap_kw_cache",
                                       "_ap_kw_cache_lock")] + [m.group(0)] + [block(f) for f in (
        "_ap_norm", "ap_regel_finden", "ap_groesse", "ap_kw_param", "_ap_kw_kauf", "_ap_kw_wachsen", "_ap_kw_lock", "kette_dll_chance", "ap_kontowert",
        "_ap_kw_usd", "ap_kw_stufe", "ap_kontowert_konto", "admin_build_kontowerte", "ap_kontowerte_gemerkt", "admin_kontowerte")]), ns)
    return ns


def db(ns, zaehler):
    def _sb_all(table, params):
        assert table == "accounts", table
        zaehler["accounts"] += 1
        uid = (params.get("user_id") or "")[3:]
        return [dict(k) for k in KONTEN if not uid or k["user_id"] == uid]

    def sb_select(table, params):
        assert table == "auto_plan_regeln", table
        return [{"regeln": {"firmen": FIRMEN}}]

    def kauf_echt(ids):
        zaehler["kauf_ids"] = sorted(ids)
        return {i: (207.0 if i == "k-1" else 5.0 if i == "k-2" else None) for i in ids}   # k-2: Gebühr, unplausibel → Firmenwert
    ns.update({"_sb_all": _sb_all, "sb_select": sb_select, "_ap_archiviert": lambda: {"k-9"},
               "_ap_balance_karten": lambda: ({}, {}), "_ap_kauf_echt": kauf_echt, "AP_KONTO_FELDER": "x",
               "acc_balance_wahl": lambda a, e, d: (BAL.get(str(a.get("id"))), "USD", "TV", "")})


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    zaehler = {"accounts": 0, "kauf_ids": None}
    db(a, zaehler)
    P = lambda firm: a["ap_kw_param"](a["ap_regel_finden"](FIRMEN, firm))

    # 1) Rechnung = ap_kontowert wie im Probelauf
    w = a["admin_build_kontowerte"](None)
    check(set(w) == {k["id"] for k in KONTEN}, "alle Konten in der Antwort (Admin-Sicht)")
    check(w["k-1"]["wert_eur"] == 207 and w["k-1"]["quelle"] == "kauf_echt" and w["k-1"]["stufe"] == "Challenge · frisch",
          f"Tradeify frisch mit echtem Kauf 207 € → 207 €, „Challenge · frisch\" ({w['k-1']})")
    soll = a["ap_kontowert"]("challenge", 153600, P("Tradeify"), 5.0)["wert"]
    check(w["k-2"]["wert_eur"] == soll == 387 and w["k-2"]["quelle"] == "kernwerte" and w["k-2"]["stufe"] == "Challenge · nach Etappe 1",
          f"Tradeify +3.600 $: 215 × (1+3.600/4.500) = 387 €, Gebühr 5 € ignoriert, „nach Etappe 1\" ({w['k-2']['wert_eur']})")
    check(w["k-3"]["wert_eur"] == 250 and w["k-3"]["stufe"] == "Phase 1 · −5.000 $", f"FundedNext 95k → 250 € · {w['k-3']['stufe']}")
    check(w["k-4"]["wert_eur"] == 750 and w["k-4"]["stufe"] == "Phase 1 · +5.000 $", f"FundedNext 105k → 750 € · {w['k-4']['stufe']}")
    check(w["k-5"]["wert_eur"] == 75 and w["k-5"]["satz_eur_pro_usd"] == round(150 / 4000, 4), "Apex 148k → 75 €, Satz 150/4.000 €/$")
    check(w["k-11"]["wert_eur"] == a["ap_kontowert"]("funded", 151200, P("Tradeify"), None)["wert"]
          and w["k-11"]["stufe"] == "Funded · +1.200 $", f"Tradeify Funded wie ap_kontowert · {w['k-11']['stufe']}")
    # 2) ohne Wert: Grund statt Zahl
    check(w["k-6"]["wert_eur"] is None and "Kernwerte" in w["k-6"]["hinweis"] and "Blue Guardian" in w["k-6"]["hinweis"],
          f"Blue Guardian ohne Kernwerte → null + Hinweis ({w['k-6']['hinweis']})")
    check(w["k-10"]["wert_eur"] is None and "Kernwerte" in w["k-10"]["hinweis"], "Fusion (Phase) ohne Kernwerte → null + Hinweis")
    check(w["k-7"]["wert_eur"] is None and "Live" in w["k-7"]["hinweis"], "Live-Konto → null + Hinweis")
    check(w["k-8"]["wert_eur"] is None and w["k-8"]["hinweis"] == "keine Live-Balance", "keine Balance → null + Hinweis")
    check(w["k-9"]["wert_eur"] is None and w["k-9"]["hinweis"] == "archiviert", "archiviert → null + Hinweis")
    check("k-9" not in zaehler["kauf_ids"] and "k-7" not in zaehler["kauf_ids"], "Kauf-Kette nur für aktive Nicht-Live-Konten gelesen")

    # 3) Route: Gate + 60-s-Merker
    app = Flask("selftest_kontowerte")
    app.add_url_rule("/admin/kontowerte", "admin_kontowerte", a["admin_kontowerte"], methods=["GET", "OPTIONS"])
    rolle = {"wer": None, "admin": False, "nur": False}

    def admin_auth():
        if not rolle["wer"]:
            return None, (jsonify({"error": "Nicht angemeldet"}), 401)
        request.environ["prophos.admin_uid"] = rolle["wer"]
        return (None, (jsonify({"error": "Nur für Admins"}), 403)) if not rolle["admin"] else ("admin@x", None)

    def wd_login():
        return (rolle["wer"], None) if rolle["wer"] else (None, (jsonify({"error": "Nicht angemeldet"}), 401))
    a.update({"_admin_auth": admin_auth, "_wd_login": wd_login, "admin_zugang_nur_eigene": lambda uid: rolle["nur"]})
    c = app.test_client()

    r = c.get("/admin/kontowerte")
    check(r.status_code == 401, "nicht angemeldet → 401")
    check(c.open("/admin/kontowerte", method="OPTIONS").status_code == 200, "OPTIONS → 200")

    a["_ap_kw_cache"].clear()
    zaehler["accounts"] = 0
    rolle.update(wer=U1, admin=True, nur=False)
    d = c.get("/admin/kontowerte").get_json()
    check(d["ok"] and d["alle"] and set(d["werte"]) == {k["id"] for k in KONTEN} and d["werte"]["k-4"]["wert_eur"] == 750,
          "Admin → alle Konten beider IDs")
    d2 = c.get("/admin/kontowerte").get_json()
    check(d2 == d and zaehler["accounts"] == 1, "zweiter Aufruf in 60 s aus dem Merker (accounts nur einmal gelesen)")

    rolle.update(nur=True)
    d = c.get("/admin/kontowerte").get_json()
    check(not d["alle"] and set(d["werte"]) == {k["id"] for k in KONTEN if k["user_id"] == U1} and zaehler["accounts"] == 2,
          "Admin mit „nur eigene\" → nur eigene Konten (eigener Merker)")

    rolle.update(wer=U2, admin=False, nur=False)
    d = c.get("/admin/kontowerte").get_json()
    check(not d["alle"] and set(d["werte"]) == {k["id"] for k in KONTEN if k["user_id"] == U2} and zaehler["accounts"] == 3,
          "Nicht-Admin → nur eigene Konten")

    a["_ap_kw_cache"]["*"] = (time.time() - 1, {})       # abgelaufen → neu rechnen
    rolle.update(wer=U1, admin=True, nur=False)
    d = c.get("/admin/kontowerte").get_json()
    check(len(d["werte"]) == len(KONTEN) and zaehler["accounts"] == 4, "nach 60 s neu gerechnet")

    def kaputt(table, params):
        raise RuntimeError("DB weg")
    a["_sb_all"] = kaputt
    a["_ap_kw_cache"].clear()
    r = c.get("/admin/kontowerte")
    check(r.status_code == 500 and r.get_json()["ok"] is False and "DB weg" in r.get_json()["error"], "DB-Fehler → 500 mit Grund, kein Merker")
    check("*" not in a["_ap_kw_cache"], "Fehler wird nicht gemerkt")

    print("\nALLES GRÜN" if ok else "\nFEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
