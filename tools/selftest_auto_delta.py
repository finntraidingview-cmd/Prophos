#!/usr/bin/env python3
"""Selbsttest Auto-Planer delta-neutral (app.py, DELTA-NEUTRAL, 06.10.2026, Vertrag .claude/master/autoplan-delta-vertrag.md).

Aufruf:  python3 tools/selftest_auto_delta.py
Lädt die Funktionen per Quelltext aus app.py (wie selftest_auto_kontowert: app.py zieht beim Import Flask und Threads).
Teil A rein rechnend: Delta je Trade (Tradeify frisch 3 NQ ≈ 2,8 €/Pkt bei Kauf 207 €/Polster 4.500), Richtung je Tranche
(Korrektur Finn 06.10.2026 abends: keine Firma × Tag-Regel, keine festen Minuten — nur je PC nie zwei Puls-Starts gleichzeitig
+ Richtungsschutz, dicht gegenläufig derselben Firma = weicher Malus), Optimierer hält das Band, Rebalancer tauscht nur
erlaubte Pläne, manueller Eingriff lehnt nur Richtungsschutz/PC-Überlappung ab.
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

REIN = ("ap_id_fest", "ap_id_misch", "ap_ext_fehlt", "_ap_norm", "ap_regel_finden", "ap_groesse", "_ap_spanne", "_ap_runden", "ap_konto_rechnen", "_ap_hhmm", "_ap_hhmm_txt",
        "ap_zeiten_verteilen", "ap_kw_param", "_ap_kw_kauf", "_ap_kw_wachsen", "ap_kontowert", "ap_trade_gewicht", "ap_sicht", "ap_sicht_uid", "ap_eingriff_filter",
        "_wd_num", "_symbol_wurzel", "_wd_level", "_wd_futures_frontcode", "_ap_gehedgt", "_ap_ende4",
        "ap_ausgleich_param", "ap_firma_key", "ap_ppl_karte", "ap_punktwert", "ap_usd_pro_pkt", "ap_delta", "ap_punkte",
        "ap_rest_punkte", "ap_verlauf", "_ap_gegen_dicht", "ap_dicht_paare", "ap_richtungen_delta", "ap_fenster_von",
        "_ap_tranchen", "_ap_tranche_frei", "_ap_firma_konflikt", "ap_verteil_gruppen", "ap_verteilung", "ap_umplanen", "ap_eingriff_pruefen", "ap_start_bis", "ap_einsatz_lage", "ap_gross_ab", "ap_consistency_etappe", "ap_regel_konto", "ist_topstep_express", "ap_cfd_ab",
        "ap_richtung_konflikte", "lt_echo_live_wahl", "lt_echo_felder",
        "ap_balance_live", "ap_letzt_je_konto", "_ap_boden", "ap_boden_konto", "ap_boden_sicher", "ap_boden_zeile", "_ap_notes_kurz", "_ap_hand_spalte_fehlt", "_ap_plaene_mit_hand", "liq_peak", "_ap_peaks", "_liq_verlauf_laden")   # 08.10.2026: Balance live (Guard/Delta/ids), Boden für den Balance-Balken
IO = ("_ap_gehedgt_plan", "_ap_bewerten", "_ap_iso_min", "_ap_stand_laden", "_ap_stand_plaene", "_ap_min_iso",
      "_ap_umplanungen_heute", "_ap_bot_stand", "ap_delta_antwort", "_ap_aenderungen_anwenden", "pc_stand_zusammenfassen", "_ap_pc_lebt", "_ap_verpufft", "_ap_dubai_versatz", "ap_ausgleichen",
      "_ap_probelauf", "ap_planen", "_ap_tz", "_ap_eur_bei", "_ap_konten_laden", "ap_einsatz_kontext", "ap_richtung_fest_plan", "ap_letzter_trade_geblasen", "_ap_rk_flag",
      "ap_richtungsschutz")


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
                  "AP_RICHTUNG_TXT", "AP_GEGEN_DICHT_MIN", "AP_GEGEN_WUERFE", "AP_EUR_STUFE", "AP_START_BIS_STANDARD", "AP_CFD_AB_STANDARD", "AP_CFD_ROUTEN", "AP_TRANCHE_LUECKE_MIN", "AP_ABSTAND_ID_FIRMA_MIN", "AP_ABSTAND_ID_MIN", "AP_ABSTAND_STUFEN", "AP_GROSS_NAH_MIN", "AP_FIRMA_ABSTAND_MIN", "AP_VERTEIL_VORLAUF_MIN", "AP_VERTEIL_JITTER_MIN", "AP_VERTEIL_GEGEN_MIN", "AP_VERTEIL_VERSATZ", "AP_VERTEILUNG_BAND_TOLERANZ_EUR", "AP_VORZIEHEN_AB_MIN", "AP_VORZIEHEN_JITTER_MIN", "AP_VORZIEHEN_HYSTERESE_EUR", "AP_VORZIEHEN_RUECKFALL_MIN", "PC_STAND_LEBT_S", "_ap_bot", "_ap_info", "WD_HEUTE_PPL", "LT_ECHO_ROUTEN", "LT_ECHO_MAX_ALTER_S",
                  "AP_RS_HORIZONT_MIN", "AP_RS_NACHLAUF_MIN", "AP_RS_ROUTEN", "AP_EINGRIFF_MAX", "AP_SICHT_ADMIN", "AP_ID_FEST_HORIZONT_MIN", "AP_RUHE_JE_PLAN_MIN", "AP_HYSTERESE_EUR", "AP_ID_MISCH_AB", "AP_ID_MISCH_MAX",
                  "AP_GRUND_EXT", "AP_GRUND_BAL_LIVE", "AP_FEST_HAND", "AP_NOTES_MAX", "LIQ_VERLAUF_CACHE_S", "_liq_verlauf_cache")
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
        {"id": "k-11", "user_id": U3, "name": "TDFY C", "firm": "Tradeify", "account_type": "challenge", "external_id": "TDFY-000011"},
    ]
    bal = {"k-1": 150000, "k-2": 100000, "k-3": 153600, "k-4": 150000, "k-5": 100000, "k-6": 150000, "k-7": 50000, "k-11": 159000}
    offen = [
        # U3 (nicht im Planer): Tradeify-WD läuft SHORT ohne Hedge → Firma × Tag: Tradeify heute nur short
        {"id": "p-o1", "user_id": U3, "master_account_id": "k-6", "master_firm": "Tradeify", "status": "open", "richtung": "sell",
         "master_tp": 1000, "master_sl": None, "master_contracts": 2, "master_symbol": "NQZ6", "route": "tvv2",
         "mt5_baseline": {"hedge": {"status": "fehler", "einstieg_nq": 20000}}, "start_um": None, "started_at": jetzt.isoformat()},
        # U3 Tradeify-Challenge (159k = Ziel erreicht → Kontowert 975 € wie der WD) läuft SHORT ohne Hedge — der WD oben zählt in
        # offen[] seit 07.10.2026 nicht mehr (Finn: „Winning Days raus"), die Basis für Bot/Band bleibt damit gleich
        {"id": "p-o3", "user_id": U3, "master_account_id": "k-11", "master_firm": "Tradeify", "status": "open", "richtung": "sell",
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
        "AP_KONTO_FELDER": "x", "AP_KONTO_FELDER_OHNE_CONS": "x", "AP_STAND_FELDER": "x", "requests": __import__("requests"), "_auth_liste_anfrage": None,
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
    check(pa == {"aktiv": False, "takt_min": 10, "zielband_pct": 15.0, "auto_start": False, "gross_ab_eur": 300.0, "laufzeit_min": 180},
          "Standard: Bot aus, 10 min, Band 15 %, ohne Auto-Start, groß ab 300 €")
    check(a["ap_ausgleich_param"]({"ausgleich": {"aktiv": "true", "takt_min": 1, "zielband_pct": 500}})
          == {"aktiv": False, "takt_min": 2, "zielband_pct": 100.0, "auto_start": False, "gross_ab_eur": 300.0, "laufzeit_min": 180},
          "nur echtes true schaltet ein, Werte geklemmt")

    # ── A2 Keine Firma × Tag-Regel mehr, nur Richtungsschutz + weicher Malus (Finn 06.10.2026 abends) ─────────────────────
    T = lambda fest, user, firma, start, d: {"fest": fest, "user": user, "firma": firma, "start": start, "delta_abs": d}
    tr = {"A|tradeify": T(None, "A", "tradeify", 60, 3.0), "B|tradeify": T(None, "B", "tradeify", 300, 3.0)}
    r, m = a["ap_richtungen_delta"](tr, 0, 0, random.Random(7), 15)
    check(r["A|tradeify"] != r["B|tradeify"] and m == 3.0,
          "dieselbe Firma bei zwei IDs gegenläufig erlaubt, wenn es das Netto ausgleicht (kein Firma × Tag)")
    tr = {"A|tradeify": T("buy", "A", "tradeify", 60, 3.0), "B|apex": T(None, "B", "apex", 100, 3.0)}
    r, _m = a["ap_richtungen_delta"](tr, 0, 0, random.Random(7), 15)
    check(r["A|tradeify"] == "buy" and r["B|apex"] == "sell", "Richtungsschutz ID+Firma bleibt fest, die andere gleicht aus")
    # weicher Malus: zwei gleich gute Lösungen — die mit dicht gegenläufiger Firma verliert
    tr = {"A|tradeify": T(None, "A", "tradeify", 100, 2.0), "B|tradeify": T(None, "B", "tradeify", 103, 2.0),
          "C|apex": T(None, "C", "apex", 100, 2.0), "D|apex": T(None, "D", "apex", 103, 2.0)}
    for s in range(5):
        r, _m = a["ap_richtungen_delta"](tr, 0, 0, random.Random(s), 15)
        check(r["A|tradeify"] == r["B|tradeify"] and r["C|apex"] == r["D|apex"] and r["A|tradeify"] != r["C|apex"],
              f"Malus (seed {s}): dicht gegenläufig derselben Firma gemieden, ausgeglichen über die andere Firma")
    paare = a["ap_dicht_paare"]({"A|x": T(None, "A", "x", 100, 1)}, [{"user_id": "B", "firma": "x", "start": 105, "richtung": "sell"}])
    check(a["_ap_gegen_dicht"]({"A|x": "buy"}, paare) == 1 and a["_ap_gegen_dicht"]({"A|x": "sell"}, paare) == 0,
          "Malus auch gegen schon gestartete Trades derselben Firma")
    # 07.10.2026 (Finn: „Tradeify long bei Jacob, eine Minute später Tradeify short bei Moritz" praktisch nie): innerhalb des
    # Delta-Bands geht der Malus vor dem kleinsten Netto — lieber schlechter ausgeglichen als dicht gegenläufig
    tr = {"A|tradeify": T(None, "A", "tradeify", 100, 3.0), "B|tradeify": T(None, "B", "tradeify", 101, 3.0)}
    for s in range(5):
        r, m = a["ap_richtungen_delta"](tr, 0, 0, random.Random(s), 100)
        check(r["A|tradeify"] == r["B|tradeify"] and m == 6.0, f"Malus vor Netto im Band (seed {s}): dicht gleich gerichtet, Netto 6 statt 0")
    # ohne Einsatz-Kontext (Delta-Modus): erst Delta-Band, dann Malus — reißt gleich gerichtet das
    # Band, gewinnt das Band
    r, m = a["ap_richtungen_delta"](tr, 0, 0, random.Random(1), 25)
    check(r["A|tradeify"] != r["B|tradeify"], "Delta-Band vor Malus: gegenläufig, wenn gleich gerichtet das Band reißt")
    # nur wenn es gar nicht anders geht (beide Richtungen fest) bleibt das Paar — nie eine Ablehnung
    tr = {"A|tradeify": T("buy", "A", "tradeify", 100, 3.0), "B|tradeify": T("sell", "B", "tradeify", 101, 3.0)}
    r, m = a["ap_richtungen_delta"](tr, 0, 0, random.Random(2), 25)
    check(r["A|tradeify"] == "buy" and r["B|tradeify"] == "sell", "beide fest → bleibt gegenläufig (Malus ist nie Verbot)")
    # PC: Zeitverteilung belegt je ID nie zwei Starts gleichzeitig, auch gegen schon geplante; keine Firmen-Pause
    zt = {"fenster": [["10:00", "10:30", 1]], "abstand_id_min": 3}
    trz = [{"key": f"A|f{i}", "user": "A", "firma": f"f{i}", "dauer_min": 4} for i in range(3)] + \
          [{"key": "B|f0", "user": "B", "firma": "f0", "dauer_min": 4}]
    mz = a["ap_zeiten_verteilen"](trz, zt, random.Random(5), 0, bestehend=[{"user": "A", "start": 615, "dauer_min": 2}])
    ss = sorted([mz[k] for k in mz if k.startswith("A|")] + [615])
    check(all(b - a_ >= 4 + 3 for a_, b in zip(ss, ss[1:])), f"PC der ID nie doppelt belegt (Starts {ss})")

    # ── A3 Optimierer hält das Band ────────────────────────────────────────────────────────────────────────────────────
    gruppen = {"a": T(None, "A", "a", 60, 3.0), "b": T(None, "B", "b", 120, 3.0), "c": T(None, "C", "c", 180, 2.0),
               "d": T("buy", "D", "d", 240, 1.0)}
    r, m = a["ap_richtungen_delta"](gruppen, 2.0, 20.0, random.Random(1), 15)
    ev = [(g["start"], g["delta_abs"] * (1 if r[f] == "buy" else -1)) for f, g in gruppen.items()]
    v = a["ap_verlauf"](2.0, 20.0, ev, 15)
    check(v["gehalten"] and m == 2.0, f"Band 15 % gehalten über den ganzen Tag (max |Netto| {m} = laufendes Netto)")
    alle = []
    for bits in range(8):
        z = {"a": "buy" if bits & 1 else "sell", "b": "buy" if bits & 2 else "sell", "c": "buy" if bits & 4 else "sell", "d": "buy"}
        alle.append(a["ap_verlauf"](2.0, 20.0, [(g["start"], g["delta_abs"] * (1 if z[f] == "buy" else -1)) for f, g in gruppen.items()],
                                    15)["netto_max_abs"])
    check(m == min(alle), "Optimum = kleinstes größtes |Netto| aller Verteilungen")
    r2, _ = a["ap_richtungen_delta"](gruppen, 2.0, 20.0, random.Random(1), 15)
    check(r == r2, "gleicher seed → gleiche Richtungen (Probelauf = Anlegen)")
    gross = {f"U{i}|f{i % 4}": T(None, f"U{i}", f"f{i % 4}", 60 + 20 * i, 1.0 + (i % 3)) for i in range(16)}
    r, m = a["ap_richtungen_delta"](gross, 0, 0, random.Random(9), 15, versuche=300)
    check(len(r) == 16 and m <= 3.0, f"16 Tranchen (Würfe + Einzeltausch): max |Netto| {m}")
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
        {"plan_id": "w1", "user_id": "C", "firma": "w", "richtung": "buy", "start_min": 640, "delta_abs": 5.0, "aenderbar": True},
        {"plan_id": "w2", "user_id": "C", "firma": "w", "richtung": "buy", "start_min": 641, "delta_abs": 1.0, "aenderbar": False,
         "fest_durch": "bestätigt und fällig"},
        {"plan_id": "v1", "user_id": "E", "firma": "v", "richtung": "buy", "start_min": 650, "delta_abs": 5.0, "aenderbar": True},
    ]
    erg = a["ap_umplanen"](plaene, 0.0, 10.0, jm, ZEITEN, 15, random.Random(3),
                           id_fest={"E|v": {"richtung": "buy", "durch": "geplant morgen"}})
    ids = {x["plan_id"] for x in erg["aenderungen"]}
    flips = {x["plan_id"] for x in erg["aenderungen"] if x["art"] == "richtung"}
    check(erg["aenderungen"] and ids <= {"x1", "x2", "v1"}, f"nur änderbare Tranchen angefasst ({sorted(ids)})")
    check(flips <= {"x1", "x2"}, "Richtung nur bei freien Tranchen — nie Handplan (y), halb feste Tranche (w) oder Richtungsschutz (v)")
    check(erg["nachher"]["ueber_band"] < erg["vorher"]["ueber_band"], "Umplanung verkleinert die Bandüberschreitung")
    tr_n = {}
    for x in plaene:
        tr_n.setdefault(x["user_id"], []).append(next((c["nach_start_min"] for c in erg["aenderungen"] if c["plan_id"] == x["plan_id"]),
                                                      x["start_min"]))
    for x in erg["aenderungen"]:
        if x["art"] == "start":
            fen = a["ap_fenster_von"](ZEITEN, x["von_start_min"])
            check(fen[0] <= x["nach_start_min"] < fen[1] and x["nach_start_min"] >= jm + 5, f"Start {x['plan_id']} bleibt im Fenster, nicht fällig")
    ruhig = a["ap_umplanen"]([dict(plaene[0], richtung="sell", start_min=700)], 0.0, 10.0, jm, ZEITEN, 50, random.Random(3))
    check(ruhig["aenderungen"] == [] and ruhig["ausloeser"] is None, "im Band → keine Änderung")
    nichts = a["ap_umplanen"]([dict(p, aenderbar=False) for p in plaene], 0.0, 10.0, jm, ZEITEN, 15, random.Random(3))
    check(nichts["aenderungen"] == [], "nichts änderbar → nichts geändert (auch wenn über dem Band)")
    # DÄMPFUNG (Vorschlag 1, 08.10.2026): Ruhezeit je Plan + Hysterese am Band — beide dürfen die alte Rechnung sonst nicht ändern
    ruhe = a["ap_umplanen"](plaene, 0.0, 10.0, jm, ZEITEN, 15, random.Random(3), zuletzt={"x1": jm - 10, "x2": jm - 10, "v1": jm - 10})
    check(not {x["plan_id"] for x in ruhe["aenderungen"]} & {"x1", "x2", "v1"} and set(ruhe["daempfung"]["ruhig"]) >= {"x1", "x2", "v1"},
          f"Ruhezeit: eben erst (10 min) angefasste Pläne ruhen ({ruhe['daempfung']['ruhig']})")
    fest_v = {"E|v": {"richtung": "buy", "durch": "geplant morgen"}}
    alt_genug = a["ap_umplanen"](plaene, 0.0, 10.0, jm, ZEITEN, 15, random.Random(3), id_fest=fest_v, zuletzt={"x1": jm - a["AP_RUHE_JE_PLAN_MIN"] - 1})
    check({x["plan_id"] for x in alt_genug["aenderungen"]} == ids and alt_genug["daempfung"]["ruhig"] == [],
          f"Ruhezeit: nach {a['AP_RUHE_JE_PLAN_MIN']} min ist der Plan wieder frei — Ergebnis wie ohne Ruhezeit")
    check(a["ap_umplanen"](plaene, 0.0, 10.0, jm, ZEITEN, 15, random.Random(3))["daempfung"]["hysterese"] == 0.0,
          "Hysterese: in der €/Pkt-Rechnung (ohne einsatz) 0 — Verhalten wie bisher")
    hyst = a["ap_umplanen"](plaene, 0.0, 10.0, jm, ZEITEN, 15, random.Random(3), hysterese=erg["vorher"]["ueber_band"] + 1)
    check(hyst["aenderungen"] == [] and hyst["ausloeser"] is None and hyst["daempfung"]["hysterese"] > 0,
          "Hysterese: Überschreitung unter der Schwelle → kein Eingriff, kein Auslöser")
    hyst0 = a["ap_umplanen"](plaene, 0.0, 10.0, jm, ZEITEN, 15, random.Random(3), id_fest=fest_v, hysterese=0)
    check([x["plan_id"] for x in hyst0["aenderungen"]] == [x["plan_id"] for x in erg["aenderungen"]], "Hysterese 0 → identisch zur alten Rechnung")
    check(a["AP_RUHE_JE_PLAN_MIN"] == 30 and a["AP_HYSTERESE_EUR"] == 200.0, "Dämpfungs-Konstanten: 30 min Ruhe je Plan, 200 € Hysterese (Vorschlag 1)")
    einzel = a["ap_umplanen"]([plaene[0], dict(plaene[1], richtung="buy")], 5.0, 5.0, jm, ZEITEN, 15, random.Random(3), schritte=1)
    check([x["plan_id"] for x in einzel["aenderungen"]] in (["x1"], ["x2"]) and einzel["aenderungen"][0]["art"] == "richtung",
          "Bot tauscht eine Tranche — dieselbe Firma bei der anderen ID darf gegenläufig bleiben")

    # ── A5 Manueller Eingriff: nur Richtungsschutz oder PC-Überlappung lehnen ab ─────────────────────────────────────────
    ep = a["ap_eingriff_pruefen"]
    pl = [
        {"plan_id": "a1", "user_id": "A", "user": "Eins", "firma": "tradeify", "richtung": "buy", "start_min": 700, "aenderbar": True},
        {"plan_id": "a2", "user_id": "A", "user": "Eins", "firma": "tradeify", "richtung": "buy", "start_min": 701.5, "aenderbar": True},
        {"plan_id": "b1", "user_id": "B", "user": "Zwei", "firma": "tradeify", "richtung": "buy", "start_min": 702, "aenderbar": True},
        {"plan_id": "c1", "user_id": "A", "user": "Eins", "firma": "apex", "richtung": "sell", "start_min": 900, "aenderbar": True},
        {"plan_id": "d1", "user_id": "C", "user": "Drei", "firma": "fundednext", "richtung": "buy", "start_min": 800, "aenderbar": False,
         "fest_durch": "Handplan (nur Auto-Pläne werden umgeplant)"},
        {"plan_id": "e1", "user_id": "C", "user": "Drei", "firma": "the5ers", "richtung": "buy", "start_min": 950, "aenderbar": True},
    ]
    aend, f = ep("a1", "richtung_tauschen", pl, 600, ZEITEN)
    check(not f and sorted(x["plan_id"] for x in aend) == ["a1", "a2"] and all(x["nach_richtung"] == "sell" for x in aend),
          "Tausch erlaubt, obwohl dieselbe Firma bei anderer ID 2 min später long startet → ganze Tranche")
    _x, f = ep("c1", "richtung_tauschen", pl, 600, ZEITEN, id_fest={"A|apex": {"richtung": "sell", "durch": "geplant morgen"}})
    check(f and "Richtungsschutz" in f, f"Richtungsschutz anderer Tage → 400: {f}")
    _x, f = ep("d1", "richtung_tauschen", pl, 600, ZEITEN)
    check(f and "Handplan" in f, "Handplan → 400")
    _x, f = ep("a1", "start", pl, 600, ZEITEN, neu_start_min=20 * 60)
    check(f and "außerhalb" in f, f"Start nach 19:30 → 400: {f}")
    _x, f = ep("a1", "start", pl, 600, ZEITEN, neu_start_min=602)
    check(f and "zu früh" in f, f"Start vor jetzt + 5 min → 400: {f}")
    _x, f = ep("a1", "start", pl, 600, ZEITEN, neu_start_min=898)
    check(f and "nie zwei Puls-Starts gleichzeitig" in f, f"Start überlappt den PC derselben ID → 400: {f}")
    aend, f = ep("a1", "start", pl, 600, ZEITEN, neu_start_min=703)
    check(not f and sorted((x["plan_id"], x["nach_start_min"]) for x in aend) == [("a1", 703), ("a2", 704.5)],
          "Start 1 min neben derselben Firma bei anderer ID erlaubt — ganze Tranche verschoben, Abstände bleiben")
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
    check(len(tdfy) == 2 and all(g["richtung"] in ("buy", "sell") for g in tdfy) and "firma_tag" not in (erg.get("ausgleich") or {}),
          "Tradeify bei beiden IDs geplant, Richtung je Tranche, kein firma_tag mehr")
    g1 = next((g for g in tdfy if g["konto_id"] == "k-1"), {})
    check(g1.get("delta_eur_pkt") is not None and abs(abs(g1["delta_eur_pkt"]) - 2.76) < 0.01, f"geplant[] trägt delta_eur_pkt ({g1.get('delta_eur_pkt')})")
    st = {}
    for g in erg.get("geplant", []):
        st.setdefault(g["user_id"], []).append(g["start"])
    check(all(len(v) == len(set(v)) for v in st.values()), "je ID keine zwei Starts in derselben Minute")
    check(all(any(w.startswith("Pause zu") or w.startswith("keine andere ID") for w in t["warum"]) for t in erg.get("tranchen") or []),
          "warum[] nennt „Pause zu … bei …: x min“ statt Firma × Tag")
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
    check(dl["geplant"] and all(k in x for x in dl["geplant"] for k in ("balance_live", "boden", "boden_min", "boden_art", "konto_id", "start_fehler", "geclaimt", "notes", "balance")) and all(x["konto_id"] for x in dl["geplant"]),
          f"geplant[]: balance_live + boden/boden_min/boden_art an jeder Zeile (08.10.2026) — z. B. {[(x.get('boden'), x.get('boden_art')) for x in dl['geplant']][:3]}")
    # Prüfer 08.10.2026: kaputte Firmen-Regel beim Boden kippt das Delta nicht — Felder null, Rest da
    boden_echt = a["ap_boden_konto"]
    a["ap_boden_konto"] = lambda *x, **y: (_ for _ in ()).throw(ValueError("kaputte Regel"))
    dl_k = a["ap_delta_antwort"](a["_ap_stand_laden"](reg, jetzt=max(jetzt, mitt + timedelta(minutes=1))))
    a["ap_boden_konto"] = boden_echt
    check(len(dl_k["geplant"]) == len(dl["geplant"]) and all(x["boden"] is None and x["boden_art"] is None and x["plan_id"] and "delta_eur_pkt" in x
                                                              for x in dl_k["geplant"]) and dl_k["offen"] == dl["offen"],
          "kaputte Regel beim Boden → boden null, alle Zeilen und offen[] trotzdem da")
    check(not any(x["plan_id"] == "p-o1" for x in dl["offen"]) and all(x["typ"] in ("challenge", "phase1", "phase2") for x in dl["offen"]),
          "offen[]: Winning-Days-Trade fehlt, nur challenge/phase1/phase2 (Finn 07.10.2026)")
    check(stand["id_fest"].get(f"{U3}|tradeify", {}).get("richtung") == "sell", "Richtungsschutz sieht den laufenden WD weiter (Tradeify bei U3 short)")
    o1 = next(x for x in dl["offen"] if x["plan_id"] == "p-o3")
    check(o1["tp_punkte_rest"] is not None and o1["delta_eur_pkt"] < 0 and o1["user_id"] == U3, f"offen: Delta short, TP-Rest {o1['tp_punkte_rest']} Pkt")
    gp = {x["plan_id"]: x for x in dl["geplant"]}
    check(gp["p-g1"]["aenderbar"] and not gp["p-g2"]["aenderbar"] and gp["p-g2"]["fest_durch"].startswith("Handplan"),
          "geplant: Auto-Plan änderbar, Handplan fest")
    check(dl["bot"]["aktiv"] is False and dl["bot"]["auto_start"] is False and dl["bot"]["naechster_lauf"] is None, "bot{}: aus, kein nächster Lauf")
    sicht = a["ap_delta_antwort"](stand, U1)
    check({x["user_id"] for x in sicht["offen"] + sicht["geplant"]} <= {U1} and sicht["netto_jetzt"] == dl["netto_jetzt"],
          "Nicht-Admin: Listen nur eigene ID, Summen über alle")
    # TRADE-PLANER-ALLE-IDS (07.10.2026): ?sicht=alle öffnet alle IDs — außer admin_zugang „nur eigene"; ohne Parameter wie bisher
    su = a["ap_sicht_uid"]
    check(su(True, U1, True, None) is None and su(True, U1, False, "eigene") is None, "sicht: Admin immer alle IDs")
    # seit 08.10.2026 (Finn als Moritz: „immer nur die jeweilige ID"): ?sicht=alle öffnet für Nicht-Admins nichts mehr, nur ?sicht=admin (Admin-Reiter)
    check(su(False, U1, False, "alle") == U1 and su(False, U1, False, " Alle ") == U1, "sicht: Planer-ID mit ?sicht=alle → nur eigene ID (08.10.2026)")
    check(su(False, U1, False, "admin") is None and su(False, U1, False, " Admin ") is None, "sicht: Nicht-Admin mit ?sicht=admin (Admin-Reiter) → alle IDs")
    check(su(False, U1, True, "admin") == U1 and su(False, U1, True, "alle") == U1, "sicht: nur-eigene (admin_zugang) bleibt bei der eigenen ID")
    check(su(False, U1, False, None) == U1 and su(False, U1, False, "") == U1 and su(False, U1, False, "eigene") == U1,
          "sicht: ohne Parameter / anderer Wert → eigene ID wie bisher")
    # BESTÄTIGEN FÜR ALLE IDS (07.10.2026): Guard-Filter der Admin-Routen = Frontend-Bedingungen, Nicht-Admin nur eigene ID
    ef = a["ap_eingriff_filter"]
    P1, P2 = "0a530c7a-a734-4d11-a497-b898bc3fe32e", "DE5AC8CA-B89A-4C2F-9A68-228FB8CF8C83"
    pr, bo, art = ef("bestaetigen", [P1, P2, P1, "x", None])
    check(pr["id"] == f"in.({P1},{P2.lower()})" and pr["status"] == "eq.planned" and pr["auto_plan"] == "eq.true" and pr["auto_bestaetigt_at"] == "is.null"
          and "user_id" not in pr and bo["auto_bestaetigt_at"] and art == "patch", "bestaetigen: in.(…) ohne Doppelte/Müll, Guard planned+auto+unbestätigt, Admin ohne user_id")
    pr, bo, art = ef("zurueck", [P1], U1)
    check(pr["id"] == "eq." + P1 and pr["start_um_gestartet_at"] == "is.null" and pr["user_id"] == "eq." + U1 and bo == {"auto_bestaetigt_at": None} and art == "patch",
          "zurueck: eq.-Filter, ungestartet, Nicht-Admin auf eigene ID, Body setzt null")
    pr, bo, art = ef("loeschen", [P1])
    check(pr["auto_plan"] == "eq.true" and pr["start_um_gestartet_at"] == "is.null" and bo is None and art == "delete", "loeschen: DELETE mit Guard planned+auto+ungestartet")
    check(ef("egal", [P1])[0] is None and ef("bestaetigen", ["nix", ""])[0] is None and ef("bestaetigen", [P1] * 1 + ["%s-%03d" % (P1[:-4], i) for i in range(a["AP_EINGRIFF_MAX"])])[0] is None,
          "Fehler: unbekannte Aktion, keine gültige ID, zu viele IDs")
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
