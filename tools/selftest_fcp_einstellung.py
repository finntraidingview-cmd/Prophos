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
    u, f = P(ZEILE, {"firma": "FundedNext", "feld": "tp_deckel_plus", "wert": None})
    ok(u and "tp_deckel_plus" not in firma(u, "FundedNext") and app.fcp_firma_einstellung(firma(u, "FundedNext"))["tp_deckel_plus_eff"] == app.FCP_TP_DECKEL_PLUS_STANDARD,
       "TP-Deckel leer → Feld weg, Standard aus dem Code gilt")
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
    e1b()
    consistency()
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("alle Tests bestanden")


def e1b():
    """E1b (05.11.2026): Parameter mit Rückfall in der DB, eigenes Fenster, Refund an/aus, ohne_namen, tp_modus ziel."""
    print("— E1b —")
    S = app.FCP_PARAM_STANDARD
    ok(app.fcp_param({}) == S and app.fcp_param({"parameter": None}) == S, "ohne parameter → Code-Werte")
    pr = app.fcp_param({"parameter": {"tp_min_usd": 300, "refund_lots_verhaeltnis": 99, "richtung_laufend": True, "x": 1, "consistency_start_usd": True}})
    ok(pr["tp_min_usd"] == 300 and pr["refund_lots_verhaeltnis"] == S["refund_lots_verhaeltnis"] and pr["richtung_laufend"] is True
       and pr["consistency_start_usd"] == S["consistency_start_usd"] and "x" not in pr, "gültige Werte gelten, ungültige/fremde → Code-Wert")
    mit = dict(ZEILE, parameter={})
    ok(P(ZEILE, {"param": "tp_min_usd", "wert": 300})[0] is None, "Parameter ohne Spalte (SQL fehlt) → abgelehnt")
    ok(P(mit, {"param": "tp_min_usd", "wert": 300})[0] == {"parameter": {"tp_min_usd": 300.0}}, "Mindest-TP 300 → nur Spalte parameter")
    ok(P(dict(mit, parameter={"tp_min_usd": 300}), {"param": "tp_min_usd", "wert": None})[0] == {"parameter": {}}, "leer → zurück auf Code-Wert")
    ok(P(mit, {"param": "tp_min_usd", "wert": 0})[0] is None and P(mit, {"param": "refund_lots_verhaeltnis", "wert": 11})[0] is None
       and P(mit, {"param": "richtung_laufend", "wert": 1})[0] is None and P(mit, {"param": "takt_s", "wert": 60})[0] is None, "Grenzen / bool / unbekannt → abgelehnt")
    ok(P(mit, {"param": "richtung_laufend", "wert": True})[0] == {"parameter": {"richtung_laufend": True}}, "Richtungsschutz an")
    u = P(ZEILE, {"zeit": "fenster", "wert": {"von": "09:30", "bis": "20:00"}})[0]
    ok(u and u["zeiten"]["fenster"] == {"von": "09:30", "bis": "20:00"} and u["zeiten"]["vorlauf_min"] == 15, "eigenes Fenster 09:30–20:00, übrige Zeiten bleiben")
    ok(P(ZEILE, {"zeit": "fenster", "wert": {"von": "20:00", "bis": "09:00"}})[0] is None and P(ZEILE, {"zeit": "fenster", "wert": {"von": "9:30", "bis": "20:00"}})[0] is None,
       "Fenster bis vor von / falsches Format → abgelehnt")
    ok("fenster" not in P(dict(ZEILE, zeiten={"vorlauf_min": 15, "fenster": {"von": "09:00", "bis": "20:00"}}), {"zeit": "fenster", "wert": None})[0]["zeiten"],
       "Fenster leer → wie Challenge-Planer")
    ok(app.fcp_fenster_eigen({"von": "10:00", "bis": "21:00"}) == (600, 1260) and app.fcp_fenster_eigen(None) is None
       and app.fcp_fenster_eigen({"von": "24:00", "bis": "25:00"}) is None, "fcp_fenster_eigen rechnet Minuten, ungültig → None")
    u = P(ZEILE, {"firma": "The5%ers", "feld": "erster_payout", "wert": True})[0]
    ok(u and firma(u, "The5%ers")["erster_payout"] == {"ziel": [50.0, 100.0], "hedge_eur_je_dd": 0.5}, "Refund an bei Firma ohne Werte → 50–100 $ / 0,5")
    u = P(ZEILE, {"firma": "FundedNext", "feld": "erster_payout", "wert": True})[0]
    ok(u and firma(u, "FundedNext")["erster_payout"] == ZEILE["firmen"][1]["erster_payout"], "Refund an bei Firma mit Werten → Werte bleiben")
    u = P(ZEILE, {"firma": "FundedNext", "feld": "erster_payout", "wert": False})[0]
    ok(u and firma(u, "FundedNext")["erster_payout"] is False and app.fcp_erster_payout(firma(u, "FundedNext")) is None, "Refund aus → false, Planer ohne Refund")
    u = P(ZEILE, {"firma": "The5%ers", "feld": "ohne_namen", "wert": [" Flex ", "flex", "Swing"]})[0]
    ok(u and firma(u, "The5%ers")["ohne_namen"] == ["flex", "swing"], "ohne_namen klein, ohne Doppelte")
    ok(P(ZEILE, {"firma": "The5%ers", "feld": "ohne_namen", "wert": [""]})[0] is None and P(ZEILE, {"firma": "The5%ers", "feld": "ohne_namen", "wert": "flex"})[0] is None
       and P(ZEILE, {"firma": "The5%ers", "feld": "ohne_namen", "wert": ["e"]})[0] is None, "ohne_namen leeres Wort / keine Liste / unter 3 Zeichen → abgelehnt")
    fp = dict(ZEILE, firmen=[dict(ZEILE["firmen"][1], ohne_namen=["flex"])])
    ok(P(fp, {"firma": "FundedNext", "feld": "ohne_namen", "wert": []})[0] is None and P(fp, {"firma": "FundedNext", "feld": "ohne_namen", "wert": ["flex", "swing"]})[0],
       "„flex“ lässt sich nicht löschen, nur ergänzen")
    u = P(ZEILE, {"firma": "The5%ers", "feld": "tp_modus", "wert": "ziel"})[0]
    ok(u and app.fcp_tp_modus(firma(u, "The5%ers")) == "ziel", "The5ers tp_modus ziel → aufs Ziel trotz Code-Standard")
    # gleiche Werte → gleiche Pläne: viele Fälle, Standard (None) gegen Parameter aus leerer Spalte und gegen ausdrücklich gesetzte Code-Werte
    pa_leer = app.fcp_param({"parameter": {}})
    pa_gesetzt = app.fcp_param({"parameter": {k: v for k, v in S.items()}})
    faelle = 0
    gleich = True
    for f in ZEILE["firmen"]:
        jg = app.fcp_je_groesse(f, 100000)
        for bal in (100000, 100300, 100900, 101180, 101290, 99000, 101400):
            for zyklus in (1, 2, 3):
                for gew in (None, 0.0, 400.0, 1600.0):
                    for gt in (None, (1, 3), (3, 3)):
                        args = (jg, bal, 100000, zyklus, zyklus == 2, 1.0, 0.85)
                        kw = dict(regel=f, gewinne=gew, gewinntage=gt, max_sl=1000 if zyklus == 3 else None)
                        a0 = app.fcp_konto_rechnen(*args, random.Random(7), **kw)
                        a1 = app.fcp_konto_rechnen(*args, random.Random(7), param=pa_leer, **kw)
                        a2 = app.fcp_konto_rechnen(*args, random.Random(7), param=pa_gesetzt, **kw)
                        faelle += 1
                        gleich = gleich and a0 == a1 == a2
    ok(gleich, f"gleiche Werte → gleiche Pläne ({faelle} Fälle: ohne Parameter = leere Spalte = Code-Werte gesetzt)")
    ok(app.fcp_tp_deckel(ZEILE["firmen"][2], app.fcp_je_groesse(ZEILE["firmen"][2], 100000), 2) ==
       app.fcp_tp_deckel(ZEILE["firmen"][2], app.fcp_je_groesse(ZEILE["firmen"][2], 100000), 2, 1000), "TP-Deckel: Standard 1.000 ausdrücklich = wie bisher")
    # geänderter Wert wirkt: Mindest-TP 400 → Rest 210 $ wird 400
    f2 = ZEILE["firmen"][2]
    jg2 = app.fcp_je_groesse(f2, 100000)
    alt = app.fcp_konto_rechnen(jg2, 100900, 100000, 2, False, 1.0, 0.85, None, f2, gewinntage=(3, 3), param=dict(S, ziel_toleranz_pct=0.0))   # Rest bis Ziel-Mitte 1.100 = 200 $ (ZT1: ohne Toleranz)
    neu = app.fcp_konto_rechnen(jg2, 100900, 100000, 2, False, 1.0, 0.85, None, f2, gewinntage=(3, 3), param=dict(S, tp_min_usd=400.0, ziel_toleranz_pct=0.0))
    ok(alt.get("tp") == 250.0 and neu.get("tp") == 400.0, f"geänderter Mindest-TP wirkt ({alt.get('tp')} → {neu.get('tp')})")
    fn = ZEILE["firmen"][1]
    jgn = app.fcp_je_groesse(fn, 100000)
    r1 = app.fcp_konto_rechnen(jgn, 100000, 100000, 1, False, 1.0, 0.85, None, fn)
    r2 = app.fcp_konto_rechnen(jgn, 100000, 100000, 1, False, 1.0, 0.85, None, fn, param=dict(S, refund_lots_verhaeltnis=1.0))
    ok(r1["aktion"] == "planen" and r2["lots"] < r1["lots"], f"Refund-Lots-Verhältnis × 1 statt × 2 → weniger Lots ({r1['lots']} → {r2['lots']})")
    pl = [{"user_id": "u1", "master_firm": "FundedNext", "status": "open", "richtung": "sell"}]
    ok(app.fcp_fest_richtung(pl) == {} and app.fcp_fest_richtung(pl, an=True) and app.fcp_fest_richtung(pl, an=False) == {}, "Richtungsschutz folgt parameter.richtung_laufend")


def consistency():
    """E1b Zusatz 3 (05.11.2026): Consistency als % je Firma — p = 50 genau wie bis .2035, Rechenbeispiele 40 % und 30 %."""
    print("— Consistency % —")
    t5 = ZEILE["firmen"][0]                                     # The5ers: tp_modus consistency50 (alt)
    t5_pct = dict(t5, consistency_pct=50)                       # nach der Migration
    t5_pct.pop("tp_modus")
    ok(app.fcp_consistency_pct(t5) == 50.0 and app.fcp_consistency_pct(t5_pct) == 50.0 and app.fcp_consistency_pct({"namen": ["the5ers"]}) == 50.0
       and app.fcp_consistency_pct(ZEILE["firmen"][1]) is None and app.fcp_consistency_pct(dict(t5, consistency_pct=0)) is None,
       "p: tp_modus consistency50 = 50, consistency_pct 50 = 50, Code-Standard = 50, andere Firma = keine, 0 = aus")
    jg = app.fcp_je_groesse(t5, 100000)
    gleich, n = True, 0
    for bal in (100000, 100400, 100750, 101100, 101290, 101450, 99800):
        for gew in (None, 0.0, -200.0, 120.0, 400.0, 750.0, 1100.0):
            for zyk in (1, 2, 3):
                a0 = app.fcp_konto_rechnen(jg, bal, 100000, zyk, False, 1.0, 0.85, random.Random(5), t5, gewinne=gew)
                a1 = app.fcp_konto_rechnen(jg, bal, 100000, zyk, False, 1.0, 0.85, random.Random(5), t5_pct, gewinne=gew)
                gleich, n = gleich and a0 == a1, n + 1
    ok(gleich, f"tp_modus consistency50 = consistency_pct 50 ({n} Fälle, gleicher Plan)")
    # WEG A (Finn 05.11.2026 ~04:20 Dubai): F = max(Z, B ÷ p × 1,02) · c = p × F × 0,95 · R = F − G · n = ceil(R ÷ c) · TP = R ÷ n (≥ 50, ≤ c)
    C = app.fcp_cons_rechnen
    a = C(50, 1450, 0, (0.0, 0))
    ok(a["n"] == 3 and a["tp"] == 483.0 and a["deckel"] == 688.75 and round(a["tp"] / 1450 * 100) == 33,
       f"Finn 1 (p 50, frisch, Z 1.450): {a['n']} Trades à {a['tp']:g} $ · Deckel {a['deckel']:g} · größter Tag {a['tp'] / 1450:.0%}")
    b = C(50, 1450, 1450, (760.0, 2))
    ok(b["ende"] == 1550 and b["n"] == 1 and b["tp"] == 100.0 and round(760 / 1550.4 * 100) == 49,
       f"Finn 2 (nach +760 / +690, G 1.450, B 760): Endziel {b['ende']:g}, TP {b['tp']:g} $, Ende {760 / 1550.4:.0%}")
    c3 = C(50, 1500, -4000, (0.0, 3))
    ok(c3["deckel"] == 712.5 and c3["n"] == 8 and c3["tp"] == 688.0 and c3["ende"] == 1500,
       f"Finn 3 (Konto 96.000, G −4.000, Z 1.500): Deckel {c3['deckel']:g}, {c3['n']} Trades à {c3['tp']:g} $ → Ende 101.500")
    d = C(40, 1450, 0, (0.0, 0))
    ok(d["deckel"] == 551.0 and d["n"] == 3 and d["tp"] == 483.0, f"p 40, frisch, Z 1.450: Deckel {d['deckel']:g}, {d['n']} Trades à {d['tp']:g} $")
    e = C(40, 1450, 900, (600.0, 2))
    ok(e["ende"] == 1530 and e["n"] == 2 and e["tp"] == 315.0, f"p 40, G 900, B 600: Endziel {e['ende']:g} (600 ÷ 0,4 × 1,02), {e['n']} Trades à {e['tp']:g} $")
    f_ = C(50, 1450, 300, None)
    ok(f_["tp"] == 688.0 and f_["lesbar"] is False, f"Zyklus nicht lesbar → F = Z, TP = Deckel {f_['tp']:g} $ (kleinster sichere Trade)")
    g_ = C(50, 1400, 1500, (760.0, 2))
    ok(g_["n"] == 1 and g_["tp"] == 50.0, f"Rest 50,4 $ → TP mindestens 50 $ ({g_['tp']:g})")
    ok(C(50, 1450, 1600, (760.0, 2))["fertig"] is True, "G 1.600 ≥ Endziel 1.550 → fertig")
    ok(C(50, 1400, 1525, (760.0, 3))["fertig"] is True, "G 1.525 ≥ B ÷ p = 1.520 (unter dem Planungs-Puffer 1.550) → fertig, kein 50-$-Extra-Trade")
    h = C(50, 5000, 4900, None)
    ok(h["tp"] == 100.0, f"nicht lesbar, Rest 100 $ → TP {h['tp']:g} (nie über den Rest)")
    ok(C(1, 1000, 0, (0.0, 0))["tp"] == 50.0, "p 1 % (Deckel 9,50 $) → TP 50 $ (Mindest), nie 0")
    bgc = dict(ZEILE["firmen"][2], consistency_pct=50)
    jb = app.fcp_je_groesse(bgc, 100000)
    rb = app.fcp_konto_rechnen(jb, 100300, 100000, 2, False, 1.0, 0.85, None, bgc, gewinntage=(3, 3), tage=(300.0, 3))
    ok(rb["tp_art"] == "consistency" and rb["tp"] <= rb["consistency"]["deckel"], f"Gewinntage erfüllt + Consistency → Weg A statt „ganzer Rest“ (TP {rb['tp']:g} ≤ Deckel {rb['consistency']['deckel']:g})")
    ok(app.fcp_tage_zyklus([{"status": "completed", "master_pl": None, "ended_at": "2026-10-20T10:00:00+00:00"},
                            {"status": "completed", "master_pl": 300, "ended_at": "2026-11-03T10:00:00+00:00"}], "2026-11-01") == (300.0, 1),
       "alter Trade ohne P&L aus früherem Zyklus stört nicht")
    # durch fcp_konto_rechnen: The5ers (Ziel 1.300–1.500, rnd None → Mitte 1.400)
    r1 = app.fcp_konto_rechnen(jg, 100000, 100000, 2, False, 1.0, 0.85, None, t5_pct, tage=(0.0, 0))
    # seit O1 (05.11.2026) Consistency nach Finn (fcp_cons_finn): TP (p − 5 %) … p der Distanz, höchstens p × Summe Gewinn-Tage am Ende × 0,95
    ok(r1["aktion"] == "planen" and r1["tp_art"] == "consistency" and 0.45 * 1400 - 1 <= r1["tp"] <= 665.0 and r1["consistency"]["n"] == 3,
       f"Konto-Rechnung The5ers frisch: TP {r1.get('tp')} (45–50 % von 1.400, Deckel 665), Trade 1 von 3")
    r2 = app.fcp_konto_rechnen(jg, 101600, 100000, 2, False, 1.0, 0.85, None, t5_pct, tage=(760.0, 2))
    ok(r2["aktion"] == "ziel", "G 1.600, B 760 → Ziel erreicht (Endziel 1.550, größter Tag 47 %)")
    r3 = app.fcp_konto_rechnen(jg, 101320, 100000, 2, False, 1.0, 0.85, None, t5_pct, tage=(760.0, 2))
    ok(r3["aktion"] == "planen" and r3["consistency"]["ende"] == 1550, f"G 1.320 ≥ Ziel-von 1.300, aber B 760 > 50 % → weiter (TP {r3.get('tp')}, Endziel 1.550)")
    r4 = app.fcp_konto_rechnen(jg, 101320, 100000, 2, False, 1.0, 0.85, None, t5_pct, tage=None)
    ok(r4["aktion"] == "ziel", "G 1.320 ≥ Ziel-von, Zyklus nicht lesbar → Ziel erreicht wie bisher (kein Trade auf Verdacht)")
    ok(r1["sl"] == app.fcp_konto_rechnen(jg, 100000, 100000, 2, False, 1.0, 0.85, None, t5, tage=(0.0, 0))["sl"] and r1["lots"] > 0, "SL / Lots / Hedge unverändert gerechnet")
    tz = app.fcp_tage_zyklus([{"status": "completed", "master_pl": 400, "ended_at": "2026-11-03T10:00:00+00:00"},
                              {"status": "completed", "master_pl": 360, "ended_at": "2026-11-03T14:00:00+00:00"},
                              {"status": "completed", "master_pl": -200, "ended_at": "2026-11-04T10:00:00+00:00"},
                              {"status": "completed", "master_pl": 900, "ended_at": "2026-10-20T10:00:00+00:00"}], "2026-11-01")
    ok(tz == (760.0, 3), f"größter Tag = Tagessumme Berlin (400 + 360), alter Zyklus zählt nicht → {tz}")
    ok(app.fcp_tage_zyklus([{"status": "completed", "master_pl": None, "ended_at": "2026-11-03T10:00:00+00:00"}]) is None, "Trade ohne master_pl → nicht lesbar")
    # Patch
    u = P(ZEILE, {"firma": "The5%ers", "feld": "consistency_pct", "wert": 40})[0]
    ok(u and firma(u, "The5%ers")["consistency_pct"] == 40.0 and "tp_modus" not in firma(u, "The5%ers"), "Patch: Consistency 40 %, tp_modus abgelöst")
    u = P(ZEILE, {"firma": "The5%ers", "feld": "consistency_pct", "wert": None})[0]
    ok(u and firma(u, "The5%ers")["consistency_pct"] == 0 and app.fcp_consistency_pct(firma(u, "The5%ers")) is None, "Patch: Consistency leer → 0 = aus (Code-Standard greift nicht)")
    u = P(ZEILE, {"firma": "FundedNext", "feld": "consistency_pct", "wert": 50})[0]
    ok(u and app.fcp_consistency_pct(firma(u, "FundedNext")) == 50.0, "Patch: Consistency bei einer anderen Firma einschalten")
    ok(P(ZEILE, {"firma": "The5%ers", "feld": "consistency_pct", "wert": 100})[0] is None and P(ZEILE, {"firma": "The5%ers", "feld": "consistency_pct", "wert": True})[0] is None,
       "Patch: 100 % / true → abgelehnt")
    u = P(ZEILE, {"firma": "The5%ers", "feld": "tp_erster_alle", "wert": 800})[0]
    ok(u and all(g["tp_erster"] == 800.0 for g in firma(u, "The5%ers")["je_groesse"].values()), "Patch: Start-TP 800 für alle Größen")
    u = P(ZEILE, {"firma": "The5%ers", "feld": "tp_erster_alle", "wert": None})[0]
    ok(u and all("tp_erster" not in g for g in firma(u, "The5%ers")["je_groesse"].values()), "Patch: Start-TP leer → Standard (Feld weg)")
    u = P(ZEILE, {"firma": "FundedNext", "groesse": "100000", "feld": "gewinntage", "wert": True})[0]
    ok(u and firma(u, "FundedNext")["je_groesse"]["100000"]["gewinntage"] == {"anzahl": 3, "min": 500.0, "tp": [550.0, 650.0]}, "Patch: Gewinntage an → 3 × ≥ 500, TP 550–650")
    u = P(ZEILE, {"firma": "Blue Guardian", "groesse": "100000", "feld": "gewinntage", "wert": False})[0]
    ok(u and "gewinntage" not in firma(u, "Blue Guardian")["je_groesse"]["100000"], "Patch: Gewinntage aus → Feld weg")
    u = P(ZEILE, {"firma": "The5%ers", "feld": "gewinntage_alle", "wert": True})[0]
    ok(u and all(g["gewinntage"] == {"anzahl": 3, "min": 500.0, "tp": [550.0, 650.0]} for g in firma(u, "The5%ers")["je_groesse"].values()),
       "Gewinntage je Firma an → alle Größen (Standard je Größe)")
    zz = dict(ZEILE, firmen=[dict(ZEILE["firmen"][1], je_groesse={"50000": dict(ZEILE["firmen"][1]["je_groesse"]["100000"]), "100000": dict(ZEILE["firmen"][1]["je_groesse"]["100000"])})])
    u = P(zz, {"firma": "FundedNext", "feld": "gewinntage_alle", "wert": True})[0]
    ok(u and firma(u, "FundedNext")["je_groesse"]["50000"]["gewinntage"]["min"] == 250.0 and firma(u, "FundedNext")["je_groesse"]["100000"]["gewinntage"]["min"] == 500.0,
       "Gewinntage an bei 50k + 100k → je Größe 0,5 % (250 / 500)")
    u2 = P(dict(zz, firmen=u["firmen"]), {"firma": "FundedNext", "feld": "gewinntage_alle.tp", "wert": [300, 350]})[0]
    ok(u2 and firma(u2, "FundedNext")["je_groesse"]["100000"]["gewinntage"]["tp"] == [600.0, 700.0], "TP 300–350 für 50k → 100k anteilig 600–700")
    u = P(ZEILE, {"firma": "Blue Guardian", "feld": "gewinntage_alle.min", "wert": 600})[0]
    ok(u and firma(u, "Blue Guardian")["je_groesse"]["100000"]["gewinntage"]["min"] == 600.0, "Gewinntage je Firma: Mindestgewinn 600 in alle Größen")
    ok(P(ZEILE, {"firma": "The5%ers", "feld": "gewinntage_alle.min", "wert": 600})[0] is None, "Gewinntage-Wert ohne eingeschaltete Gewinntage → abgelehnt")
    u = P(ZEILE, {"firma": "Blue Guardian", "feld": "gewinntage_alle", "wert": False})[0]
    ok(u and "gewinntage" not in firma(u, "Blue Guardian")["je_groesse"]["100000"], "Gewinntage je Firma aus → überall weg")
    u = P(ZEILE, {"firma": "Blue Guardian", "groesse": "100000", "feld": "gewinntage", "wert": True})[0]
    ok(u and firma(u, "Blue Guardian")["je_groesse"]["100000"]["gewinntage"] == ZEILE["firmen"][2]["je_groesse"]["100000"]["gewinntage"], "Patch: Gewinntage an bei vorhandenen Werten → bleiben")


if __name__ == "__main__":
    main()
