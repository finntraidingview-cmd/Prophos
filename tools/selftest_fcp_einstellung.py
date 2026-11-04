#!/usr/bin/env python3
"""Selbsttest: Einstellungen Funded Planer → CFD (app.py fcp_regel_patch, fcp_firma_einstellung, fcp_code_werte; E1 04.11.2026, Finn: „Alle Inputs …
sollen unten visuell und änderbar stehen"). Ohne Netz, Regel-Zeile erfunden (Form wie live). Geprüft: jede erlaubte Änderung ergibt genau das
geänderte Feld, alles andere bleibt; ungültige Werte werden abgelehnt; die Zeile selbst wird nie verändert (Kopie); gleiche Werte → gleicher Plan.
Aufruf: python3 tools/selftest_fcp_einstellung.py"""
import copy
import json
import os
import random
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
import app  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


ZEILE = {"id": 1, "aktiv": True, "auto_bestaetigen": True, "ziel_auto_wartet": False, "updated_at": "2026-11-04T10:00:00+00:00",
         "zeiten": {"vorlauf_min": 15, "abstand_id_min": 10, "firma_abstand_min": 15},
         "firmen": [{"an": True, "name": "The5%ers", "namen": ["the5ers"], "tp_modus": "consistency50", "tp_zyklen": [750, 1500, 3000, 6000],
                     "je_groesse": {"100000": {"dd": 10000, "sl": [1000, 1200], "lots": [1.0, 1.4], "ziel": [1300, 1500], "hedge_eur": 1000, "tp_erster": 750}}},
                    {"an": True, "name": "FundedNext", "namen": ["fundednext"], "tp_deckel_plus": 1000,
                     "erster_payout": {"ziel": [50, 150], "hedge_eur_je_dd": 0.5, "lots_faktor": 0.1},
                     "je_groesse": {"100000": {"dd": 10000, "sl": [2000, 2300], "sl_1pct": [700, 780], "lots": [1.0, 1.75], "ziel": [5000, 5500], "hedge_eur": 1500}}},
                    {"an": True, "name": "Blue Guardian", "namen": ["blueguardian"], "erster_payout": {"ziel": [50, 100], "hedge_eur_je_dd": 0.5},
                     "je_groesse": {"100000": {"dd": 8000, "sl": [1500, 1800], "lots": [1.0, 1.2], "ziel": [1000, 1200], "hedge_eur": 1000,
                                               "gewinntage": {"anzahl": 3, "min": 500, "tp": [550, 650]}}}}]}
ROH = json.dumps(ZEILE, sort_keys=True)
P = app.fcp_regel_patch


def firma(upd, name):
    return next(f for f in upd["firmen"] if f["name"] == name)


def main():
    # Schalter / Zeiten
    u, f = P(ZEILE, {"schalter": "auto_bestaetigen", "wert": False})
    ok(u == {"auto_bestaetigen": False} and f is None, "Schalter auto_bestaetigen → nur diese Spalte")
    ok(P(ZEILE, {"schalter": "news", "wert": True})[0] is None and P(ZEILE, {"schalter": "aktiv", "wert": "ja"})[0] is None, "unbekannter Schalter / kein bool → abgelehnt")
    u, f = P(ZEILE, {"zeit": "firma_abstand_min", "wert": 20})
    ok(u == {"zeiten": {"vorlauf_min": 15, "abstand_id_min": 10, "firma_abstand_min": 20}}, "Zeit firma_abstand_min 20, übrige Zeiten bleiben")
    ok(P(ZEILE, {"zeit": "firma_abstand_min", "wert": 999})[0] is None and P(ZEILE, {"zeit": "x", "wert": 5})[0] is None, "Zeit > 240 / unbekannt → abgelehnt")
    # Firma an/aus
    u, f = P(ZEILE, {"firma": "FundedNext", "an": False})
    ok(firma(u, "FundedNext")["an"] is False and firma(u, "The5%ers")["an"] is True, "Firma FundedNext aus, andere unverändert")
    ok(P(ZEILE, {"firma": "Gibtsnicht", "an": False})[0] is None, "unbekannte Firma → abgelehnt")
    # Werte je Größe
    u, f = P(ZEILE, {"firma": "The5%ers", "groesse": "100000", "feld": "ziel", "wert": [1400, 1600]})
    ok(firma(u, "The5%ers")["je_groesse"]["100000"]["ziel"] == [1400.0, 1600.0], "Ziel als Bereich 1.400–1.600")
    ok(P(ZEILE, {"firma": "The5%ers", "groesse": "100000", "feld": "ziel", "wert": [1600, 1400]})[0] is None, "Bereich von > bis → abgelehnt")
    u, f = P(ZEILE, {"firma": "The5%ers", "groesse": "100000", "feld": "hedge_eur", "wert": 1200})
    ok(firma(u, "The5%ers")["je_groesse"]["100000"]["hedge_eur"] == 1200.0, "Hedge € 1.200")
    ok(P(ZEILE, {"firma": "The5%ers", "groesse": "100000", "feld": "lots", "wert": [1, 99]})[0] is None, "Lots über 50 → abgelehnt")
    ok(P(ZEILE, {"firma": "The5%ers", "groesse": "100000", "feld": "dd", "wert": 0})[0] is None, "DD 0 → abgelehnt")
    ok(P(ZEILE, {"firma": "The5%ers", "groesse": "100000", "feld": "sl", "wert": None})[0] is None, "SL leer → abgelehnt (Pflichtfeld)")
    u, f = P(ZEILE, {"firma": "The5%ers", "groesse": "100000", "feld": "tp_erster", "wert": None})
    ok("tp_erster" not in firma(u, "The5%ers")["je_groesse"]["100000"], "Consistency-Start leer → Feld weg (dann 750 fest im Code)")
    ok(P(ZEILE, {"firma": "The5%ers", "groesse": "50000", "feld": "sl", "wert": [1, 2]})[0] is None, "nicht hinterlegte Größe → abgelehnt")
    ok(P(ZEILE, {"firma": "The5%ers", "groesse": "100000", "feld": "geheim", "wert": 1})[0] is None, "unbekanntes Feld → abgelehnt")
    # Firmen-Felder
    u, f = P(ZEILE, {"firma": "FundedNext", "feld": "tp_deckel_plus", "wert": 800})
    ok(firma(u, "FundedNext")["tp_deckel_plus"] == 800.0, "TP-Deckel + 800")
    u, f = P(ZEILE, {"firma": "The5%ers", "feld": "tp_zyklen", "wert": [750, 1500, 3000]})
    ok(firma(u, "The5%ers")["tp_zyklen"] == [750.0, 1500.0, 3000.0], "TP-Zyklen 750 · 1.500 · 3.000")
    ok(P(ZEILE, {"firma": "The5%ers", "feld": "tp_zyklen", "wert": []})[0] is None, "leere Zyklen → abgelehnt")
    u, f = P(ZEILE, {"firma": "FundedNext", "feld": "tp_modus", "wert": "consistency50"})
    ok(firma(u, "FundedNext")["tp_modus"] == "consistency50", "tp_modus consistency50 setzen")
    ok(P(ZEILE, {"firma": "FundedNext", "feld": "tp_modus", "wert": "irgendwas"})[0] is None, "tp_modus unbekannt → abgelehnt")
    u, f = P(ZEILE, {"firma": "FundedNext", "feld": "erster_payout.ziel", "wert": [60, 160]})
    ok(firma(u, "FundedNext")["erster_payout"]["ziel"] == [60.0, 160.0], "Refund-Ziel 60–160")
    ok(P(ZEILE, {"firma": "The5%ers", "feld": "erster_payout.ziel", "wert": [60, 160]})[0] is None, "Refund-Wert bei Firma ohne Refund → abgelehnt")
    ok(P(ZEILE, {"firma": "FundedNext", "feld": "erster_payout.lots_faktor", "wert": 2})[0] is None, "Lots-Faktor > 1 → abgelehnt")
    u, f = P(ZEILE, {"firma": "Blue Guardian", "groesse": "100000", "feld": "gewinntage.anzahl", "wert": 4})
    ok(firma(u, "Blue Guardian")["je_groesse"]["100000"]["gewinntage"]["anzahl"] == 4, "Gewinntage Anzahl 4")
    ok(P(ZEILE, {"firma": "The5%ers", "groesse": "100000", "feld": "gewinntage.anzahl", "wert": 4})[0] is None, "Gewinntage bei Größe ohne Gewinntage → abgelehnt")
    # Grenzen aus dem Fremd-Review (04.11.2026)
    ok(P(ZEILE, {"zeit": "firma_abstand_min", "wert": 0})[0] is None and P(ZEILE, {"zeit": "vorlauf_min", "wert": 0})[0] is None,
       "Abstand je Firma / Vorlauf 0 → abgelehnt (Planer läse 15)")
    ok(P(ZEILE, {"zeit": "abstand_id_min", "wert": 0})[0] == {"zeiten": {"vorlauf_min": 15, "abstand_id_min": 0, "firma_abstand_min": 15}}, "Abstand je ID 0 erlaubt")
    ok(P(ZEILE, {"firma": "The5%ers", "groesse": "100000", "feld": "ziel", "wert": [0, 0]})[0] is None
       and P(ZEILE, {"firma": "The5%ers", "groesse": "100000", "feld": "hedge_eur", "wert": 0})[0] is None, "Ziel 0 / Hedge 0 → abgelehnt")
    ok(P(ZEILE, {"firma": "Blue Guardian", "groesse": "100000", "feld": "gewinntage.min", "wert": 0})[0] is None
       and P(ZEILE, {"firma": "Blue Guardian", "groesse": "100000", "feld": "gewinntage.tp", "wert": [0, 0]})[0] is None, "Gewinntage min 0 / TP 0 → abgelehnt")
    ok(P(ZEILE, {"firma": "The5%ers", "groesse": "100000", "feld": "lots", "wert": True})[0] is None
       and P(ZEILE, {"firma": "FundedNext", "feld": "tp_deckel_plus", "wert": False})[0] is None, "true/false als Zahl → abgelehnt")
    ok(P(ZEILE, {"firma": "FundedNext", "feld": "erster_payout.hedge_eur_je_dd", "wert": 0})[0] is None, "Refund-Hedge 0 → abgelehnt")
    ohne = dict(ZEILE, firmen=[{"an": True, "namen": ["tradeifycfd"], "je_groesse": {"100000": {"dd": 1, "sl": [1, 2], "lots": [1, 1], "ziel": [1, 2], "hedge_eur": 1}}}])
    u, f = P(ohne, {"firma": "tradeifycfd", "an": False})
    ok(u and u["firmen"][0]["an"] is False, "Firma ohne name: über namen[0] änderbar (wie die Anzeige)")
    # Zeile selbst nie verändert
    ok(json.dumps(ZEILE, sort_keys=True) == ROH, "Eingabe-Zeile unverändert (nur Kopie geändert)")
    # Anzeige: Standard aus dem Code + wirksame Werte
    e5 = app.fcp_firma_einstellung(ZEILE["firmen"][0])
    ok(e5["tp_modus_eff"] == "consistency50" and e5["weg"] == "Echo" and e5["tp_deckel_plus"] is None and e5["tp_deckel_plus_eff"] == app.FCP_TP_DECKEL_PLUS_STANDARD,
       "Anzeige The5ers: Consistency, Weg Echo, Deckel-Plus aus dem Code")
    efn = app.fcp_firma_einstellung(ZEILE["firmen"][1])
    ok(efn["erster_payout_eff"]["ziel"] == [50, 150] and efn["tp_modus_eff"] is None, "Anzeige FundedNext: Refund aus der Regel, kein Consistency")
    cw = app.fcp_code_werte()
    ok(cw["tp_min_usd"] == 250 and cw["consistency_start_usd"] == 750 and cw["weg"]["route"] == "mt5" and json.dumps(cw), "Code-Werte (250, 750, Echo mt5) serialisierbar")
    # gleiche Werte → gleicher Plan (fcp_konto_rechnen mit Regel vor/nach einem No-Op-Patch)
    u, f = P(ZEILE, {"firma": "The5%ers", "groesse": "100000", "feld": "ziel", "wert": [1300, 1500]})
    r_alt, r_neu = ZEILE["firmen"][0], firma(u, "The5%ers")
    a = app.fcp_konto_rechnen(app.fcp_je_groesse(r_alt, 100000), 100500, 100000, 2, False, 1.0, 0.85, random.Random(3), r_alt, gewinne=750.0)
    n = app.fcp_konto_rechnen(app.fcp_je_groesse(r_neu, 100000), 100500, 100000, 2, False, 1.0, 0.85, random.Random(3), r_neu, gewinne=750.0)
    ok(a == n, "gleiche Werte → gleicher Plan")
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("alle Tests bestanden")


if __name__ == "__main__":
    main()
