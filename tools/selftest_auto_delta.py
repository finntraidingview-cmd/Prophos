#!/usr/bin/env python3
"""Selbsttest Auto-Planer delta-neutral (app.py, DELTA-NEUTRAL, 06.10.2026, Vertrag .claude/master/autoplan-delta-vertrag.md).

Aufruf:  python3 tools/selftest_auto_delta.py
Lädt die Funktionen per Quelltext aus app.py (wie selftest_auto_kontowert: app.py zieht beim Import Flask und Threads).
Teil A rein rechnend: Delta je Trade (Tradeify frisch 3 NQ ≈ 2,8 €/Pkt bei Kauf 207 €/Polster 4.500), Firma × Tag nie
gegenläufig, Optimierer hält das Band, Rebalancer tauscht nur erlaubte Pläne, manueller Eingriff lehnt Regelverstöße ab.
Teil B Rauch-Lauf ohne Netz: ap_planen (Probelauf), _ap_stand_laden, ap_delta_antwort und ap_ausgleichen gegen eine
nachgebaute DB (Fixture im Test, keine echten Konten) — prüft die Verdrahtung und die Antwortfelder des Vertrags."""
import hashlib
import json
import os
import random
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")

FIRMEN = [
    {"namen": ["tradeify"], "route": "tvv2", "symbol": "NQ", "groessen": [150000], "kauf_eur": 215, "dd_usd": 4500,
     "boden": "nachziehend", "ziel_pct": {"challenge": 6},
     "phasen": {"challenge": {"sl": None, "tp": [3450, 3550], "menge": [3, 3], "dd_usd": 4500, "tp_max": 3600, "ziel_pct": 6,
                              "menge_schritt": 1, "puffer_je_menge": {"2": [15, 25], "3": [25, 40]}}}},
    {"namen": ["apextrader", "apex"], "route": "tvv2", "symbol": "NQ", "groessen": [150000], "kauf_eur": 150, "dd_usd": 4000,
     "boden": "statisch", "daily_usd": 2000, "soft": True, "ziel_pct": {"challenge": 6},
     "phasen": {"challenge": {"sl": None, "tp": None, "menge": [4, 5], "puffer": [100, 100], "ziel_pct": 6, "menge_schritt": 1}}},
    {"namen": ["fundednext"], "route": "mt5v2", "groessen": [100000], "kauf_eur": {"50000": 261, "100000": 500}, "dd_pct": 10,
     "boden": "statisch", "ziel_pct": {"phase1": 8, "phase2": 5}, "wert_groessen": [50000, 100000],
     "phasen": {"phase1": {"sl": [2500, 3500], "tp": [6000, 8000], "menge": [2.1, 3.2], "puffer": [100, 100], "ziel_pct": 8,
                           "boden_pct": 10, "menge_schritt": 0.1}}},
    {"namen": ["the5ers"], "route": "mt5v2", "groessen": [100000, 200000], "skaliert": True,
     "kauf_eur": {"100000": 146, "200000": 226}, "dd_pct": 10, "boden": "statisch", "ziel_pct": {"phase1": 8, "phase2": 5},
     "phasen": {"phase1": {"sl": [2000, 2500], "tp": [6000, 7000], "menge": [35, 45], "puffer": [50, 75], "ziel_pct": 8,
                           "boden_pct": 10, "menge_schritt": 1}}},
]
ZEITEN = {"tz": "Europe/Berlin", "fenster": [["00:00", "14:30", 40], ["14:30", "17:30", 40], ["17:30", "19:30", 20]],
          "abstand_id_min": 3, "abstand_konto_s": [60, 120], "pause_firma_min": [25, 45]}

REIN = ("_ap_norm", "ap_regel_finden", "ap_groesse", "_ap_spanne", "_ap_runden", "ap_konto_rechnen", "_ap_hhmm", "_ap_hhmm_txt",
        "ap_zeiten_verteilen", "ap_kw_param", "_ap_kw_kauf", "_ap_kw_wachsen", "ap_kontowert", "ap_trade_gewicht", "ap_sicht",
        "_wd_num", "_symbol_wurzel", "_wd_level", "_wd_futures_frontcode", "_ap_gehedgt", "_ap_ende4",
        "ap_ausgleich_param", "ap_firma_key", "ap_ppl_karte", "ap_punktwert", "ap_usd_pro_pkt", "ap_delta", "ap_punkte",
        "ap_rest_punkte", "ap_verlauf", "ap_richtungen_delta", "ap_firma_tag", "ap_firma_richtung_fest", "ap_fenster_von",
        "_ap_tranchen", "_ap_tranche_frei", "ap_umplanen", "ap_eingriff_pruefen",
        "lt_echo_live_wahl", "lt_echo_felder")
IO = ("_ap_gehedgt_plan", "_ap_bewerten", "_ap_iso_min", "_ap_stand_laden", "_ap_stand_plaene", "_ap_min_iso",
      "_ap_umplanungen_heute", "_ap_bot_stand", "ap_delta_antwort", "_ap_aenderungen_anwenden", "ap_ausgleichen",
      "_ap_probelauf", "ap_planen", "_ap_tz")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "random": random, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "json": json,
          "hashlib": hashlib, "time": __import__("time")}

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]

    def konst(name):
        return re.search(rf"^{name} = .*$", src, re.M).group(0)
    konstanten = ("AP_REST_MIN", "AP_GROESSE_TOLERANZ", "AP_KW_FUNDED", "AP_KW_PHASEN", "AP_TYPEN", "AP_TZ_LAUF", "AP_STILL_FIRMEN",
                  "AP_AUSGLEICH_STANDARD", "AP_TZ_TAG", "AP_BOT_ENDE_MIN", "AP_BOT_EXTRA_MIN", "AP_FAELLIG_MIN", "AP_BOT_SCHRITTE",
                  "AP_RICHTUNG_TXT", "_ap_bot", "_ap_info", "WD_HEUTE_PPL", "LT_ECHO_ROUTEN", "LT_ECHO_MAX_ALTER_S")
    exec("\n".join([konst(k) for k in konstanten] + [block(f) for f in REIN + IO]), ns)
    return ns


# ── Nachgebaute DB für Teil B (Platzhalter-IDs, keine echten Konten) ─────────────────────────────────────────────────────────
U1, U2, U3 = "00000000-0000-0000-0000-0000000000a1", "00000000-0000-0000-0000-0000000000a2", "00000000-0000-0000-0000-0000000000a3"


def fixture(jetzt):
    konten = [
        {"id": "k-1", "user_id": U1, "name": "TDFY A", "firm": "Tradeify", "account_type": "challenge", "external_id": "TDFY-000001"},
        {"id": "k-2", "user_id": U1, "name": "FN A", "firm": "FundedNext", "account_type": "phase1", "external_id": "000002"},
        {"id": "k-3", "user_id": U2, "name": "TDFY B", "firm": "Tradeify", "account_type": "challenge", "external_id": "TDFY-000003"},
        {"id": "k-4", "user_id": U2, "name": "Apex B", "firm": "Apex Trader", "account_type": "challenge", "external_id": "APEX-000004"},
        {"id": "k-5", "user_id": U2, "name": "5ers B", "firm": "The5%ers", "account_type": "phase1", "external_id": "000005"},
        {"id": "k-6", "user_id": U3, "name": "TDFY WD", "firm": "Tradeify", "account_type": "winning_days", "external_id": "TDFY-000006"},
        {"id": "k-7", "user_id": U3, "name": "Lucid", "firm": "Lucid Trading", "account_type": "challenge", "external_id": "LUC-000007"},
    ]
    bal = {"k-1": 150000, "k-2": 100000, "k-3": 153600, "k-4": 150000, "k-5": 100000, "k-6": 150000, "k-7": 50000}
    offen = [
        # U3 (nicht im Planer): Tradeify-WD läuft SHORT ohne Hedge → Firma × Tag: Tradeify heute nur short
        {"id": "p-o1", "user_id": U3, "master_account_id": "k-6", "master_firm": "Tradeify", "status": "open", "richtung": "sell",
         "master_tp": 1000, "master_sl": None, "master_contracts": 2, "master_symbol": "NQZ6", "route": "tvv2",
         "mt5_baseline": {"hedge": {"status": "fehler", "einstieg_nq": 20000}}, "start_um": None, "started_at": jetzt.isoformat()},
        # U3 Lucid ohne Kernwerte → Delta null + Hinweis
        {"id": "p-o2", "user_id": U3, "master_account_id": "k-7", "master_firm": "Lucid Trading", "status": "open", "richtung": "buy",
         "master_tp": 500, "master_sl": 500, "master_contracts": 2, "master_symbol": "MNQZ6", "route": "tvv2", "mt5_baseline": {}},
    ]
    return konten, bal, offen


def db_stubs(ns, jetzt, geplant_extra=None):
    konten, bal, offen = fixture(jetzt)
    geplant = list(geplant_extra or [])
    reg = {"id": 1, "aktiv": False, "user_ids": [U1, U2], "zeiten": ZEITEN,
           "regeln": {"firmen": FIRMEN, "ausgleich": {"aktiv": False, "takt_min": 10, "zielband_pct": 15, "auto_start": False}}}
    geschrieben = {"patch": [], "post": []}

    def _sb_all(table, params):
        if table == "accounts":
            ids = re.findall(r"[\w-]+", params.get("id", "")[4:-1]) if params.get("id") else None
            typen = params.get("account_type")
            return [dict(k) for k in konten if (ids is None or k["id"] in ids) and (not typen or k["account_type"] in typen)]
        if table == "trade_plans":
            st = params.get("status")
            if st == "eq.open":
                return [dict(p) for p in offen]
            if st == "eq.planned":
                return [dict(p) for p in geplant]
            if st:
                return []
            return [dict(p) for p in offen + geplant]
        if table == "firm_specs":
            return [{"user_id": U1, "name": "FundedNext", "ppl": "10.0000", "symbol": None, "unit": "Lots"},
                    {"user_id": U2, "name": "The5%ers", "ppl": "1.0000", "symbol": None, "unit": "Lots"},
                    {"user_id": U2, "name": "Tradeify", "ppl": "2.0000", "symbol": "MNQ", "unit": "Kontrakte"}]
        return []

    def sb_select(table, params):
        if table == "auto_plan_regeln":
            return [reg]
        if table == "auto_plan_umplanung":
            return []
        return []

    def sb_update(table, params, body):
        geschrieben["patch"].append((table, params, body))
        return [{"id": params.get("id")}]

    class R:
        status_code = 201

    ns.update({
        "_sb_all": _sb_all, "sb_select": sb_select, "sb_update": sb_update,
        "_sb_anfrage": lambda *a, **k: (geschrieben["post"].append((a, k)), R())[1], "_sb_pruefen": lambda r: None,
        "_sb_headers": lambda *a: {}, "SUPABASE_URL": "http://test", "ADMIN_EXCLUDE_EMAILS": set(),
        "_ap_namen": lambda: ({U1: "Eins", U2: "Zwei", U3: "Drei"}, set()),
        "_ap_balance_karten": lambda: ({}, {}), "_ap_archiviert": lambda: set(),
        "acc_balance_wahl": lambda a, e, d: (bal.get(str((a or {}).get("id"))), "USD", "TV", "2999-01-01"),
        "_ap_kauf_echt": lambda ids: {i: (207.0 if i == "k-1" else None) for i in ids},
        "_firm_norm": lambda n: "The5%ers" if "5" in str(n or "") else str(n or ""),
        "_kurs_jetzt": lambda: {"NQ": {"kurs": 19990.0}, "MNQ": {"kurs": 19990.0}},
        "AP_KONTO_FELDER": "x", "AP_STAND_FELDER": "x", "_auth_liste_anfrage": None,
    })
    return reg, geschrieben


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    regel = lambda firm: a["ap_regel_finden"](FIRMEN, firm)
    P = lambda firm: a["ap_kw_param"](regel(firm))
    W = lambda firm, typ, bal, kauf=None: a["ap_kontowert"](typ, bal, P(firm), kauf)

    # ── A1 Delta je Trade ──────────────────────────────────────────────────────────────────────────────────────────────
    kw = W("Tradeify", "challenge", 150000, kauf=207)
    ppe, q = a["ap_punktwert"]("tvv2", "NQZ6", "2.0000")
    upp = a["ap_usd_pro_pkt"](3, ppe)
    d = a["ap_delta"](kw["satz"], upp, "buy")
    check(ppe == 20 and q == "NQ" and upp == 60, "Tradeify NQ: 20 $/Pkt je Kontrakt (Symbol am Plan vor firm_specs MNQ), 3 Kontrakte = 60 $/Pkt")
    check(abs(kw["satz"] - 207 / 4500) < 1e-4 and abs(d - 2.76) < 0.01, f"Tradeify frisch 3 NQ, Kauf 207 €/Polster 4.500 → {d} €/Pkt ≈ 2,8")
    check(a["ap_delta"](kw["satz"], upp, "sell") == -d, "short = gleiches Delta mit Minus")
    check(a["ap_punktwert"]("tvv2", "MNQZ6", None)[0] == 2, "MNQ 2 $/Pkt")
    check(a["ap_punktwert"]("mt5v2", None, "10.0000") == (10.0, "firm_specs"), "CFD: firm_specs.ppl (Blue Guardian 10 $/Pkt je Lot)")
    check(a["ap_punktwert"]("mt5v2", None, None)[0] is None, "CFD ohne ppl → kein Punktwert (nicht geraten)")
    check(a["ap_punktwert"]("tvv2", None, None)[0] is None, "Futures ohne Symbol und ohne ppl → kein Punktwert")
    check(a["ap_delta"](None, 60, "buy") is None and a["ap_delta"](0.05, None, "buy") is None, "ohne Satz oder Punktwert → Delta null")
    check(a["ap_punkte"](3600, 60) == 60.0 and a["ap_punkte"](None, 60) is None, "TP 3.600 $ bei 60 $/Pkt = 60 Punkte")
    check(a["ap_rest_punkte"](20010, 20060, 19900, "buy") == (50.0, 110.0)
          and a["ap_rest_punkte"](20010, 19960, 20100, "sell") == (50.0, 90.0), "Restabstände TP/SL long und short")
    je_id, je_firma = a["ap_ppl_karte"]([{"user_id": "x", "name": "FTMO", "ppl": "0.85"}, {"user_id": "y", "name": "FTMO", "ppl": "0.85"},
                                         {"user_id": "z", "name": "FTMO", "ppl": "1.0"}])
    check(je_firma["ftmo"][0] == 0.85 and je_id[("z", "ftmo")][0] == 1.0, "firm_specs: eigene ID vor häufigstem Firmenwert")
    pa = a["ap_ausgleich_param"]({})
    check(pa == {"aktiv": False, "takt_min": 10, "zielband_pct": 15.0, "auto_start": False}, "Standard: Bot aus, 10 min, Band 15 %, ohne Auto-Start")
    check(a["ap_ausgleich_param"]({"ausgleich": {"aktiv": "true", "takt_min": 1, "zielband_pct": 500}})
          == {"aktiv": False, "takt_min": 2, "zielband_pct": 100.0, "auto_start": False}, "nur echtes true schaltet ein, Werte geklemmt")

    # ── A2 Firma × Tag ─────────────────────────────────────────────────────────────────────────────────────────────────
    ft = a["ap_firma_tag"]([("tradeify", "sell", "X läuft"), ("tradeify", "sell", "Y geplant"), ("apex", "buy", "Z"), ("apex", "sell", "W")])
    check(ft["tradeify"]["richtung"] == "sell" and ft["apex"]["richtung"] == "konflikt", "Firma × Tag: eine Richtung, beide = Konflikt")
    fest, verw = a["ap_firma_richtung_fest"](
        [{"key": "A|tradeify", "fkey": "tradeify", "fest": "buy", "fest_durch": "geplanter Plan"},
         {"key": "B|tradeify", "fkey": "tradeify", "fest": None},
         {"key": "C|apex", "fkey": "apex", "fest": None},
         {"key": "D|fundednext", "fkey": "fundednext", "fest": "sell", "fest_durch": "laufender Plan"},
         {"key": "E|fundednext", "fkey": "fundednext", "fest": "buy", "fest_durch": "geplanter Plan"}], ft)
    check(set(verw) == {"A|tradeify", "C|apex", "E|fundednext"} and fest["fundednext"]["richtung"] == "sell",
          "Richtungsschutz gegen die Firma des Tages / Konflikt-Firma / zweiter Schutz gegenläufig → Tranche fällt raus")
    gruppen = {"tradeify": {"fest": "sell", "tranchen": [(60, 2.0), (200, 3.0)]}, "apex": {"fest": None, "tranchen": [(100, 4.0)]},
               "fundednext": {"fest": None, "tranchen": [(120, 1.5), (300, 1.5)]}}
    r, _m = a["ap_richtungen_delta"](gruppen, 0, 0, random.Random(7), 15)
    check(set(r) == set(gruppen) and r["tradeify"] == "sell", "Richtung je FIRMA (alle Tranchen einer Firma gleich), feste Firma bleibt")

    # ── A3 Optimierer hält das Band ────────────────────────────────────────────────────────────────────────────────────
    gruppen = {"a": {"fest": None, "tranchen": [(60, 3.0)]}, "b": {"fest": None, "tranchen": [(120, 3.0)]},
               "c": {"fest": None, "tranchen": [(180, 2.0)]}, "d": {"fest": "buy", "tranchen": [(240, 1.0)]}}
    r, m = a["ap_richtungen_delta"](gruppen, 2.0, 20.0, random.Random(1), 15)
    ev = [(t, dd * (1 if r[f] == "buy" else -1)) for f, g in gruppen.items() for t, dd in g["tranchen"]]
    v = a["ap_verlauf"](2.0, 20.0, ev, 15)
    check(v["gehalten"] and m == 2.0, f"Band 15 % gehalten über den ganzen Tag (max |Netto| {m} = laufendes Netto)")
    alle = []
    for bits in range(8):
        z = {"a": "buy" if bits & 1 else "sell", "b": "buy" if bits & 2 else "sell", "c": "buy" if bits & 4 else "sell", "d": "buy"}
        alle.append(a["ap_verlauf"](2.0, 20.0, [(t, dd * (1 if z[f] == "buy" else -1)) for f, g in gruppen.items()
                                                for t, dd in g["tranchen"]], 15)["netto_max_abs"])
    check(m == min(alle), "Optimum = kleinstes größtes |Netto| aller Verteilungen")
    r2, _ = a["ap_richtungen_delta"](gruppen, 2.0, 20.0, random.Random(1), 15)
    check(r == r2, "gleicher seed → gleiche Richtungen (Probelauf = Anlegen)")
    v = a["ap_verlauf"](0, 0, [(100, 2.0), (100, -2.0), (50, 1.0)], 15, ab_min=60)
    check([x["min"] for x in v["verlauf"]] == [60, 100] and v["verlauf"][0]["netto_delta"] == 1.0 and v["verlauf"][1]["brutto_delta"] == 5.0,
          "Verlauf kumuliert, früher gestartete zählen ab jetzt, gleiche Minute zusammen")

    # ── A4 Rebalancer tauscht nur erlaubte Pläne ───────────────────────────────────────────────────────────────────────
    jm = 600.0
    plaene = [
        {"plan_id": "x1", "user_id": "A", "firma": "x", "richtung": "buy", "start_min": 620, "delta_abs": 4.0, "aenderbar": True},
        {"plan_id": "x2", "user_id": "B", "firma": "x", "richtung": "buy", "start_min": 680, "delta_abs": 2.0, "aenderbar": True},
        {"plan_id": "y1", "user_id": "A", "firma": "y", "richtung": "buy", "start_min": 625, "delta_abs": 5.0, "aenderbar": False,
         "fest_durch": "Handplan"},
        {"plan_id": "z1", "user_id": "C", "firma": "z", "richtung": "buy", "start_min": 630, "delta_abs": 5.0, "aenderbar": True},
        {"plan_id": "w1", "user_id": "C", "firma": "w", "richtung": "buy", "start_min": 640, "delta_abs": 5.0, "aenderbar": True},
        {"plan_id": "w2", "user_id": "D", "firma": "w", "richtung": "buy", "start_min": 700, "delta_abs": 1.0, "aenderbar": False,
         "fest_durch": "bestätigt und fällig"},
        {"plan_id": "v1", "user_id": "E", "firma": "v", "richtung": "buy", "start_min": 650, "delta_abs": 5.0, "aenderbar": True},
    ]
    erg = a["ap_umplanen"](plaene, 0.0, 10.0, jm, ZEITEN, 15, random.Random(3), firma_fest={"z": {"richtung": "buy", "durch": "läuft"}},
                           id_fest={"E|v": {"richtung": "buy", "durch": "geplant morgen"}})
    ids = {x["plan_id"] for x in erg["aenderungen"]}
    flips = {x["plan_id"] for x in erg["aenderungen"] if x["art"] == "richtung"}
    check(erg["aenderungen"] and ids <= {"x1", "x2", "z1", "w1", "v1"}, f"nur änderbare Pläne angefasst ({sorted(ids)})")
    check(flips <= {"x1", "x2"} and (not flips or flips == {"x1", "x2"}),
          "Richtung nur bei Firma x getauscht — ganze Firma, nie die feste (z), die halb feste (w) oder die geschützte (v)")
    check(erg["nachher"]["ueber_band"] < erg["vorher"]["ueber_band"], "Umplanung verkleinert die Bandüberschreitung")
    for x in erg["aenderungen"]:
        if x["art"] == "start":
            fen = a["ap_fenster_von"](ZEITEN, x["von_start_min"])
            check(fen[0] <= x["nach_start_min"] < fen[1] and x["nach_start_min"] >= jm + 5, f"Start {x['plan_id']} bleibt im Fenster, nicht fällig")
    ruhig = a["ap_umplanen"]([dict(plaene[0], richtung="sell", start_min=700)], 0.0, 10.0, jm, ZEITEN, 50, random.Random(3))
    check(ruhig["aenderungen"] == [] and ruhig["ausloeser"] is None, "im Band → keine Änderung")
    nichts = a["ap_umplanen"]([dict(p, aenderbar=False) for p in plaene], 0.0, 10.0, jm, ZEITEN, 15, random.Random(3))
    check(nichts["aenderungen"] == [], "nichts änderbar → nichts geändert (auch wenn über dem Band)")

    # ── A5 Manueller Eingriff ──────────────────────────────────────────────────────────────────────────────────────────
    ep = a["ap_eingriff_pruefen"]
    pl = [
        {"plan_id": "a1", "user_id": "A", "user": "Eins", "firma": "tradeify", "richtung": "buy", "start_min": 700, "aenderbar": True},
        {"plan_id": "a2", "user_id": "A", "user": "Eins", "firma": "tradeify", "richtung": "buy", "start_min": 701.5, "aenderbar": True},
        {"plan_id": "b1", "user_id": "B", "user": "Zwei", "firma": "tradeify", "richtung": "buy", "start_min": 760, "aenderbar": True},
        {"plan_id": "c1", "user_id": "A", "user": "Eins", "firma": "apex", "richtung": "sell", "start_min": 900, "aenderbar": True},
        {"plan_id": "d1", "user_id": "C", "user": "Drei", "firma": "fundednext", "richtung": "buy", "start_min": 800, "aenderbar": False,
         "fest_durch": "Handplan (nur Auto-Pläne werden umgeplant)"},
        {"plan_id": "e1", "user_id": "C", "user": "Drei", "firma": "the5ers", "richtung": "buy", "start_min": 950, "aenderbar": True},
    ]
    _x, f = ep("a1", "richtung_tauschen", pl, 600, ZEITEN)
    check(f and "anderen IDs" in f and "nie gegenläufig" in f, f"Tausch bei Firma mit anderer ID → 400: {f}")
    _x, f = ep("c1", "richtung_tauschen", pl, 600, ZEITEN, firma_fest={"apex": {"richtung": "sell", "durch": "Drei läuft"}})
    check(f and "Firma × Tag" in f, f"Tausch gegen laufende Firma → 400: {f}")
    _x, f = ep("d1", "richtung_tauschen", pl, 600, ZEITEN)
    check(f and "Handplan" in f, "Handplan → 400")
    aend, f = ep("e1", "richtung_tauschen", pl, 600, ZEITEN)
    check(not f and len(aend) == 1 and aend[0]["nach_richtung"] == "sell", "erlaubter Tausch → ganze Tranche")
    _x, f = ep("c1", "richtung_tauschen", pl, 600, ZEITEN, id_fest={"A|apex": {"richtung": "sell", "durch": "geplant morgen"}})
    check(f and "Richtungsschutz" in f, "Richtungsschutz anderer Tage → 400")
    _x, f = ep("a1", "start", pl, 600, ZEITEN, neu_start_min=20 * 60)
    check(f and "außerhalb" in f, f"Start nach 19:30 → 400: {f}")
    _x, f = ep("a1", "start", pl, 600, ZEITEN, neu_start_min=602)
    check(f and "zu früh" in f, f"Start vor jetzt + 5 min → 400: {f}")
    _x, f = ep("a1", "start", pl, 600, ZEITEN, neu_start_min=750)
    check(f and "Mindestpause" in f, f"Start 10 min neben anderer ID derselben Firma → 400: {f}")
    _x, f = ep("a1", "start", pl, 600, ZEITEN, neu_start_min=898)
    check(f and "eigener Tranche" in f, f"Start überlappt eigene Tranche → 400: {f}")
    aend, f = ep("a1", "start", pl, 600, ZEITEN, neu_start_min=650)
    check(not f and sorted((x["plan_id"], x["nach_start_min"]) for x in aend) == [("a1", 650), ("a2", 651.5)],
          "erlaubter Start → ganze Tranche verschoben, Abstände bleiben")
    _x, f = ep("zz", "start", pl, 600, ZEITEN, neu_start_min=650)
    check(f, "unbekannter Plan → 400")

    # ── B Rauch-Lauf ohne Netz ─────────────────────────────────────────────────────────────────────────────────────────
    from zoneinfo import ZoneInfo
    jetzt = datetime.now(timezone.utc)
    tag = jetzt.astimezone(ZoneInfo("Europe/Berlin")) + timedelta(days=1)     # morgen: Probelauf unabhängig von der Uhrzeit
    while tag.weekday() >= 5:
        tag += timedelta(days=1)
    tag_s = tag.strftime("%Y-%m-%d")
    reg, geschrieben = db_stubs(a, jetzt)
    erg = a["ap_planen"](tag_s, trocken=True, seed=4711)
    check(erg.get("ok") and not erg.get("probelauf_fehler"), f"Probelauf läuft durch ({erg.get('msg') or erg.get('probelauf_fehler') or 'ok'})")
    tdfy = [g for g in erg.get("geplant", []) if g["firma"] == "Tradeify"]
    check(len(tdfy) == 2 and all(g["richtung"] == "sell" for g in tdfy),
          "Tradeify bei beiden IDs short — läuft heute schon short bei einer dritten ID (Firma × Tag)")
    g1 = next((g for g in tdfy if g["konto_id"] == "k-1"), {})
    check(g1.get("delta_eur_pkt") is not None and abs(g1["delta_eur_pkt"] + 2.76) < 0.01, f"geplant[] trägt delta_eur_pkt ({g1.get('delta_eur_pkt')})")
    aus = erg.get("ausgleich") or {}
    felder = ("offen_delta_long", "offen_delta_short", "plan_delta_long", "plan_delta_short", "verlauf", "netto_max_abs", "band")
    check(all(k in aus for k in felder) and all("netto_delta" in p for p in aus["verlauf"]), "ausgleich{} mit den Vertragsfeldern")
    check(any("Lucid" in str(h.get("firma")) for h in aus.get("hinweise") or []), "Trade ohne Kontowert/Punktwert → Hinweis")
    tr = erg.get("tranchen") or []
    check(tr and all("delta_eur_pkt" in t and all("tp_punkte" in k and "sl_punkte" in k for k in t["konten"]) for t in tr),
          "tranchen[] je Konto delta_eur_pkt, tp_punkte, sl_punkte")
    check(erg["fingerabdruck"] == a["ap_planen"](tag_s, trocken=True, seed=4711)["fingerabdruck"], "gleicher seed → gleicher Fingerabdruck")

    # GET-Delta + Bot mit geplanten Auto-Plänen des Tages
    mitt = datetime(tag.year, tag.month, tag.day, tzinfo=ZoneInfo("Europe/Berlin"))
    t0 = max(jetzt, mitt) + timedelta(minutes=40)
    geplant = [
        {"id": "p-g1", "user_id": U1, "master_account_id": "k-2", "master_firm": "FundedNext", "status": "planned", "richtung": "buy",
         "master_tp": 6000, "master_sl": 3000, "master_contracts": 3.0, "route": "mt5v2", "start_um": t0.isoformat(),
         "auto_plan": True, "auto_bestaetigt_at": None, "created_at": jetzt.isoformat()},
        {"id": "p-g2", "user_id": U2, "master_account_id": "k-4", "master_firm": "Apex Trader", "status": "planned", "richtung": "buy",
         "master_tp": 9100, "master_sl": None, "master_contracts": 5, "master_symbol": "NQZ6", "route": "tvv2",
         "start_um": (t0 + timedelta(minutes=5)).isoformat(), "auto_plan": False, "created_at": jetzt.isoformat()},
    ]
    reg, geschrieben = db_stubs(a, jetzt, geplant)
    stand = a["_ap_stand_laden"](reg, jetzt=max(jetzt, mitt + timedelta(minutes=1)))
    dl = a["ap_delta_antwort"](stand)
    check(all(k in dl for k in ("um", "band", "netto_jetzt", "brutto_jetzt", "offen", "geplant", "verlauf", "umplanungen", "bot", "fenster")),
          "GET /admin/auto-plan/delta: alle Vertragsfelder")
    check(isinstance(dl["band"], float) and dl["fenster"][0]["von"] == "00:00" and "band" in dl["verlauf"][0],
          "band als Zahl €/Pkt, fenster[], verlauf[].band")
    o1 = next(x for x in dl["offen"] if x["plan_id"] == "p-o1")
    check(o1["tp_punkte_rest"] is not None and o1["delta_eur_pkt"] < 0 and o1["user_id"] == U3, f"offen: Delta short, TP-Rest {o1['tp_punkte_rest']} Pkt")
    gp = {x["plan_id"]: x for x in dl["geplant"]}
    check(gp["p-g1"]["aenderbar"] and not gp["p-g2"]["aenderbar"] and gp["p-g2"]["fest_durch"].startswith("Handplan"),
          "geplant: Auto-Plan änderbar, Handplan fest")
    check(dl["bot"]["aktiv"] is False and dl["bot"]["auto_start"] is False and dl["bot"]["naechster_lauf"] is None, "bot{}: aus, kein nächster Lauf")
    sicht = a["ap_delta_antwort"](stand, U1)
    check({x["user_id"] for x in sicht["offen"] + sicht["geplant"]} <= {U1} and sicht["netto_jetzt"] == dl["netto_jetzt"],
          "Nicht-Admin: Listen nur eigene ID, Summen über alle")
    erg = a["ap_ausgleichen"](trocken=True, seed=1, jetzt=max(jetzt, mitt + timedelta(minutes=1)))
    check(erg["ok"] and geschrieben["patch"] == [] and all(u["plan_id"] == "p-g1" for u in erg["umplanungen"]),
          f"Ausgleich trocken: nichts geschrieben, höchstens der Auto-Plan umgeplant ({len(erg['umplanungen'])})")
    erg = a["ap_ausgleichen"](trocken=False, seed=1, jetzt=max(jetzt, mitt + timedelta(minutes=1)))
    check(all(p[2] == "trade_plans" or p[0] == "trade_plans" for p in geschrieben["patch"])
          and all(p[1].get("status") == "eq.planned" and p[1].get("auto_plan") == "eq.true" for p in geschrieben["patch"]),
          "Ausgleich schreibt nur mit Guard (geplant, Auto-Plan, ungestartet)")
    check(len(geschrieben["post"]) == (1 if erg["umplanungen"] else 0), "jede Umplanung protokolliert (auto_plan_umplanung)")
    # FundedNext-Auto-Plan short verschärft das Short-Netto der laufenden WD → Bot tauscht FundedNext auf long, der Handplan bleibt
    reg, geschrieben = db_stubs(a, jetzt, [dict(geplant[0], richtung="sell"), geplant[1]])
    erg = a["ap_ausgleichen"](trocken=False, seed=1, jetzt=max(jetzt, mitt + timedelta(minutes=1)))
    pat = [(p[1]["id"], p[2]) for p in geschrieben["patch"]]
    check(erg["ok"] and ("eq.p-g1", {"richtung": "buy"}) in pat and all(i == "eq.p-g1" for i, _ in pat),
          f"Bot tauscht nur den Auto-Plan (FundedNext short → long), Handplan unberührt ({pat})")
    zeilen = geschrieben["post"][0][1]["json"] if geschrieben["post"] else []
    check(len(zeilen) == len(erg["umplanungen"]) >= 1 and all(z["quelle"] == "bot" and z["grund"] for z in zeilen),
          "Protokollzeilen mit quelle bot und Grund")
    check(erg["netto_nachher"] <= erg["netto_vorher"], f"max |Netto| {erg['netto_vorher']} → {erg['netto_nachher']} €/Pkt")

    print("ALLES OK" if ok else "FEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
