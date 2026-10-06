#!/usr/bin/env python3
"""
Selbsttest der Copier-Rechenlogik — laeuft OHNE MetaTrader, also auch auf dem Mac.

Prueft plan_actions() aus copier.py gegen die Faelle, die im Alltag vorkommen:
Oeffnen, Reverse-Richtung, Teil-Schliessung, Komplett-Schliessung, Neustart-Recovery,
Kontraktgroessen-Umrechnung, Lot-Rundung, fehlendes Mapping.

Aufruf:  python3 selftest.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from copier import (plan_actions, check_fleet, compute_startup_skip,  # noqa: E402
                    plan_sltp, broker_abstand, find_notfall_deals, read_snapshot,
                    magic_umzug_ziel, MAGIC_UMZUG, FAMILIE_MIN, FAMILIE_MAX)

# Fusion-Markets-typische Symboldaten (beide Testkonten beim selben Broker)
FUSION = {
    "NAS100": {"volume_step": 0.01, "volume_min": 0.01, "volume_max": 100.0, "trade_contract_size": 1.0},
    "US500":  {"volume_step": 0.01, "volume_min": 0.01, "volume_max": 100.0, "trade_contract_size": 1.0},
    # Broker mit Kontraktgroesse 10 (zum Testen der Exposure-Umrechnung)
    "IDX10":  {"volume_step": 0.01, "volume_min": 0.01, "volume_max": 100.0, "trade_contract_size": 10.0},
    # Broker mit grobem Lot-Raster
    "GROB":   {"volume_step": 0.1,  "volume_min": 0.1,  "volume_max": 100.0, "trade_contract_size": 1.0},
}
MAP = {"NAS100": "NAS100", "US500": "US500", "MASTER_IDX": "IDX10", "MASTER_GROB": "GROB"}


def sym(s):
    return FUSION.get(s)


def run(name, positions, hedges, *, mult=1.0, expect_actions=None,
        expect_warn_contains=None, skip=frozenset()):
    actions, warns = plan_actions(positions, hedges, multiplier=mult, symbol_map=MAP,
                                  sym_info=sym, skip_idents=skip)
    ok = True
    detail = []

    if expect_actions is not None:
        got = [{k: a[k] for k in ("kind", "symbol", "volume") if k in a} for a in actions]
        if len(got) != len(expect_actions):
            ok = False
        else:
            for g, e in zip(got, expect_actions):
                for k, v in e.items():
                    if k == "volume":
                        if abs(g.get("volume", -1) - v) > 1e-9:
                            ok = False
                    elif g.get(k) != v:
                        ok = False
        detail.append(f"Aktionen: {got}")
        if expect_actions:
            detail.append(f"erwartet: {expect_actions}")

    if expect_warn_contains is not None:
        if not any(expect_warn_contains.lower() in w.lower() for w in warns):
            ok = False
        detail.append(f"Warnungen: {warns}")

    # Reverse-Richtung zusaetzlich pruefen, wenn eine Open-Aktion erwartet wurde
    for a in actions:
        if a["kind"] == "open":
            mtype = next((p["type"] for p in positions if p["ident"] == a["ident"]), None)
            if mtype is not None and a["hedge_type"] == mtype:
                ok = False
                detail.append(f"✗ Richtung NICHT gedreht (Master {mtype}, Hedge {a['hedge_type']})")

    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        for d in detail:
            print("    " + d)
    return ok


def main():
    results = []

    # 1) Neue Master-Position BUY -> Hedge SELL, gleiches Volumen
    results.append(run(
        "Neue Master-BUY-Position → Hedge SELL 1.0 (Richtung gedreht)",
        [{"ident": 1, "symbol": "NAS100", "type": 0, "volume": 1.0, "contract_size": 1.0}],
        {},
        expect_actions=[{"kind": "open", "symbol": "NAS100", "volume": 1.0}]))

    # 2) Master SELL -> Hedge BUY
    results.append(run(
        "Master-SELL-Position → Hedge BUY (Richtung gedreht)",
        [{"ident": 2, "symbol": "NAS100", "type": 1, "volume": 0.5, "contract_size": 1.0}],
        {},
        expect_actions=[{"kind": "open", "symbol": "NAS100", "volume": 0.5}]))

    # 3) Hedge existiert schon in richtiger Groesse -> NICHTS tun (Idempotenz)
    results.append(run(
        "Hedge bereits korrekt vorhanden → keine Aktion (Idempotenz)",
        [{"ident": 3, "symbol": "NAS100", "type": 0, "volume": 1.0, "contract_size": 1.0}],
        {3: [{"ticket": 900, "symbol": "NAS100", "type": 1, "volume": 1.0}]},
        expect_actions=[]))

    # 4) Master teil-geschlossen 1.0 -> 0.6, Hedge 1.0 -> es muessen 0.4 zu
    results.append(run(
        "Master teil-geschlossen (1.0→0.6) → Hedge 0.4 schliessen",
        [{"ident": 4, "symbol": "NAS100", "type": 0, "volume": 0.6, "contract_size": 1.0}],
        {4: [{"ticket": 901, "symbol": "NAS100", "type": 1, "volume": 1.0}]},
        expect_actions=[{"kind": "close", "symbol": "NAS100", "volume": 0.4}]))

    # 5) Master aufgestockt 1.0 -> 1.5, Hedge 1.0 -> 0.5 nachlegen
    results.append(run(
        "Master aufgestockt (1.0→1.5) → Hedge 0.5 nachlegen",
        [{"ident": 5, "symbol": "NAS100", "type": 0, "volume": 1.5, "contract_size": 1.0}],
        {5: [{"ticket": 902, "symbol": "NAS100", "type": 1, "volume": 1.0}]},
        expect_actions=[{"kind": "open", "symbol": "NAS100", "volume": 0.5}]))

    # 6) Master-Position weg -> Hedge komplett schliessen
    results.append(run(
        "Master-Position geschlossen → Hedge komplett zu",
        [],
        {6: [{"ticket": 903, "symbol": "NAS100", "type": 1, "volume": 0.8}]},
        expect_actions=[{"kind": "close", "symbol": "NAS100", "volume": 0.8}]))

    # 7) Kontraktgroessen-Umrechnung: Master cs=1, Hedge cs=10 -> 1.0 wird 0.1
    results.append(run(
        "Kontraktgroesse Master 1 vs Hedge 10 → 1.0 Lot wird 0.1",
        [{"ident": 7, "symbol": "MASTER_IDX", "type": 0, "volume": 1.0, "contract_size": 1.0}],
        {},
        expect_actions=[{"kind": "open", "symbol": "IDX10", "volume": 0.1}]))

    # 8) Multiplikator 0.427 auf 1.0 Lot -> 0.43 (auf 0.01 gerundet)
    results.append(run(
        "Multiplikator 0.427 → auf Lot-Raster 0.01 gerundet = 0.43",
        [{"ident": 8, "symbol": "NAS100", "type": 0, "volume": 1.0, "contract_size": 1.0}],
        {}, mult=0.427,
        expect_actions=[{"kind": "open", "symbol": "NAS100", "volume": 0.43}]))

    # 9) Grobes Lot-Raster 0.1: 0.427 -> 0.4
    results.append(run(
        "Grobes Lot-Raster 0.1 → 0.427 wird 0.4",
        [{"ident": 9, "symbol": "MASTER_GROB", "type": 0, "volume": 1.0, "contract_size": 1.0}],
        {}, mult=0.427,
        expect_actions=[{"kind": "open", "symbol": "GROB", "volume": 0.4}]))

    # 10) max-Lots-Grenze abgeschafft (15.08.2026, Finns Ansage): grosse Faktoren
    #     laufen ungebremst durch — Deckel ist nur noch das Broker-volume_max.
    results.append(run(
        "Keine Sicherheitsgrenze mehr: Multiplikator 10 → 10 Lots gehen durch",
        [{"ident": 10, "symbol": "NAS100", "type": 0, "volume": 1.0, "contract_size": 1.0}],
        {}, mult=10.0,
        expect_actions=[{"kind": "open", "symbol": "NAS100", "volume": 10.0}]))

    # 11) Fehlendes Symbol-Mapping -> keine Aktion, Warnung
    results.append(run(
        "Unbekanntes Master-Symbol → keine Order, Warnung",
        [{"ident": 11, "symbol": "GIBTSNICHT", "type": 0, "volume": 1.0, "contract_size": 1.0}],
        {},
        expect_actions=[], expect_warn_contains="Kein Symbol-Mapping"))

    # 12) Volumen unter Mindest-Lot -> keine Order, Warnung
    results.append(run(
        "Berechnetes Volumen unter Mindest-Lot → keine Order, Warnung",
        [{"ident": 12, "symbol": "NAS100", "type": 0, "volume": 0.001, "contract_size": 1.0}],
        {}, mult=0.001,
        expect_actions=[], expect_warn_contains="Mindest-Lot"))

    # 13) Beim Start offene Position wird uebersprungen (skip_idents)
    results.append(run(
        "Beim Start offene Master-Position wird nicht nachtraeglich gehedged",
        [{"ident": 13, "symbol": "NAS100", "type": 0, "volume": 1.0, "contract_size": 1.0}],
        {}, skip=frozenset({13}),
        expect_actions=[]))

    # 14) Neustart-Recovery: Hedge existiert, Master unveraendert -> nichts doppelt
    results.append(run(
        "Neustart mit bestehendem Hedge → kein Doppel-Hedge",
        [{"ident": 14, "symbol": "NAS100", "type": 0, "volume": 2.0, "contract_size": 1.0}],
        {14: [{"ticket": 904, "symbol": "NAS100", "type": 1, "volume": 2.0}]},
        expect_actions=[]))

    # 16) NEUSTART mit offener Master-Position UND offenem Hedge (Bug 13.08.2026):
    #     Die Startup-Position steht auf der Skip-Liste. Der bestehende Hedge darf
    #     WEDER angefasst NOCH geschlossen werden — sonst waere die laufende Position
    #     nach einem Copier-Neustart ungehedged.
    results.append(run(
        "NEUSTART: Master offen (uebersprungen) + Hedge offen → Hedge bleibt unangetastet",
        [{"ident": 20, "symbol": "NAS100", "type": 0, "volume": 1.0, "contract_size": 1.0}],
        {20: [{"ticket": 910, "symbol": "NAS100", "type": 1, "volume": 1.0}]},
        skip=frozenset({20}),
        expect_actions=[]))

    # 17) Danach schliesst der Master wirklich -> der Hedge MUSS mitgehen,
    #     obwohl die Position auf der Skip-Liste stand.
    results.append(run(
        "NEUSTART: uebersprungener Master schliesst spaeter → Hedge wird geschlossen",
        [],
        {20: [{"ticket": 910, "symbol": "NAS100", "type": 1, "volume": 1.0}]},
        skip=frozenset({20}),
        expect_actions=[{"kind": "close", "symbol": "NAS100", "volume": 1.0}]))

    # 15) Zwei Master-Positionen gleichzeitig -> zwei getrennte Hedges
    results.append(run(
        "Zwei Master-Positionen → zwei getrennte Hedges",
        [{"ident": 15, "symbol": "NAS100", "type": 0, "volume": 1.0, "contract_size": 1.0},
         {"ident": 16, "symbol": "US500", "type": 1, "volume": 0.2, "contract_size": 1.0}],
        {},
        expect_actions=[{"kind": "open", "symbol": "NAS100", "volume": 1.0},
                        {"kind": "open", "symbol": "US500", "volume": 0.2}]))

    # ── Flotten-Pruefung (Multi-Master, seit 13.08.2026) ────────────────────────
    def fleet(name, cfgs, *, expect_error_contains=None, expect_ok=False):
        errors, _ = check_fleet(cfgs)
        if expect_ok:
            ok = not errors
        else:
            ok = any(expect_error_contains.lower() in e.lower() for e in errors)
        print(("✓ " if ok else "✗ ") + name)
        if not ok:
            print(f"    Fehler: {errors}")
        return ok

    BASE = {"hedge_terminal_path": "C:\\MT5-Hedge\\terminal64.exe", "hedge_expected_login": 400002}

    # 18) Doppelte magic wird als Fehler erkannt (der kritische Audit-Fund)
    results.append(fleet(
        "FLOTTE: doppelte magic → Abbruch-Fehler",
        [dict(BASE, _file="config.json", magic=770001, snapshot_file="a.csv", master_expected_login=1),
         dict(BASE, _file="config-m2.json", magic=770001, snapshot_file="b.csv", master_expected_login=2)],
        expect_error_contains="magic 770001"))

    # 19) Doppelte snapshot_file wird als Fehler erkannt
    results.append(fleet(
        "FLOTTE: doppelte snapshot_file → Abbruch-Fehler",
        [dict(BASE, _file="config.json", magic=770001, snapshot_file="x.csv", master_expected_login=1),
         dict(BASE, _file="config-m2.json", magic=770002, snapshot_file="X.CSV", master_expected_login=2)],
        expect_error_contains="snapshot_file"))

    # 20) master_expected_login 0 ist ab zwei Mastern verboten
    results.append(fleet(
        "FLOTTE: master_expected_login 0 bei zwei Mastern → Abbruch-Fehler",
        [dict(BASE, _file="config.json", magic=770001, snapshot_file="a.csv", master_expected_login=400001),
         dict(BASE, _file="config-m2.json", magic=770002, snapshot_file="b.csv", master_expected_login=0)],
        expect_error_contains="master_expected_login"))

    # 21) Abweichendes Hedge-Terminal zwischen den Configs → Fehler
    results.append(fleet(
        "FLOTTE: unterschiedliche Hedge-Terminals → Abbruch-Fehler",
        [dict(BASE, _file="config.json", magic=770001, snapshot_file="a.csv", master_expected_login=1),
         {"_file": "config-m2.json", "magic": 770002, "snapshot_file": "b.csv",
          "master_expected_login": 2, "hedge_terminal_path": "C:\\ANDERES\\terminal64.exe",
          "hedge_expected_login": 400002}],
        expect_error_contains="hedge_terminal_path"))

    # 22) Saubere Zwei-Master-Flotte geht durch
    results.append(fleet(
        "FLOTTE: saubere Zwei-Master-Config → keine Fehler",
        [dict(BASE, _file="config.json", magic=770001, snapshot_file="a.csv", master_expected_login=400001),
         dict(BASE, _file="config-m2.json", magic=770002, snapshot_file="b.csv", master_expected_login=400003)],
        expect_ok=True))

    # ── Startup-Skip mit Hedge-Adoption (Neustart-Recovery, seit 13.08.2026) ────
    def skiptest(name, positions, hedges, adopt, expect):
        got = compute_startup_skip(positions, hedges, adopt)
        ok = got == expect
        print(("✓ " if ok else "✗ ") + name)
        if not ok:
            print(f"    erwartet {expect}, bekommen {got}")
        return ok

    # 23) Position MIT bestehendem Hedge wird adoptiert (nicht uebersprungen)
    results.append(skiptest(
        "NEUSTART: Position mit Hedge wird adoptiert, ohne Hedge uebersprungen",
        [{"ident": 30, "symbol": "NAS100", "type": 0, "volume": 1.0, "contract_size": 1.0},
         {"ident": 31, "symbol": "US500", "type": 0, "volume": 1.0, "contract_size": 1.0}],
        {30: [{"ticket": 950, "symbol": "NAS100", "type": 1, "volume": 1.0}]},
        False, {31}))

    # 24) adopt_existing=true uebernimmt alles
    results.append(skiptest(
        "NEUSTART: adopt_existing=true → nichts wird uebersprungen",
        [{"ident": 32, "symbol": "NAS100", "type": 0, "volume": 1.0, "contract_size": 1.0}],
        {}, True, set()))

    # 25) Adoptierte Position: Teil-Schliessung nach Neustart wird jetzt nachgezogen
    #     (vorher: Skip-Liste → Hedge blieb auf 1.0 stehen, bis der Master ganz zu war)
    results.append(run(
        "NEUSTART: adoptierter Master teil-geschlossen (1.0→0.4) → Hedge folgt",
        [{"ident": 33, "symbol": "NAS100", "type": 0, "volume": 0.4, "contract_size": 1.0}],
        {33: [{"ticket": 951, "symbol": "NAS100", "type": 1, "volume": 1.0}]},
        expect_actions=[{"kind": "close", "symbol": "NAS100", "volume": 0.6}]))

    # ── Provisionierung: reine Logik (13.08.2026) ───────────────────────────
    import json as _json
    import tempfile
    import provision

    def prov(name, fn):
        try:
            ok = bool(fn())
        except Exception as e:
            ok = False
            print(f"    Exception: {type(e).__name__}: {e}")
        print(("✓ " if ok else "✗ ") + name)
        return ok

    with tempfile.TemporaryDirectory() as td:
        base = {"mode": "demo", "hedge_terminal_path": "C:\\MT5-Hedge\\terminal64.exe",
                "hedge_expected_login": 400002, "master_expected_login": 400001,
                "snapshot_file": "prophos_master.csv", "magic": 770001,
                "comment_prefix": "PH", "multiplier": 1.0,
                "symbol_map": {"NAS100": "NAS100"},
                "_kommentar": "wird nicht uebernommen"}
        m2 = dict(base, magic=770002, comment_prefix="P2", snapshot_file="prophos_master2.csv")
        _json.dump(base, open(os.path.join(td, "config.json"), "w"))
        _json.dump(m2, open(os.path.join(td, "config-master2.json"), "w"))

        # 26) Vergabe: naechste freie magic 770003, Praefix P3, Snapshot nach Name
        ident = provision.alloc_identity(td, "ftmo1")
        results.append(prov(
            "PROVISION: magic/prefix/snapshot fortlaufend und kollisionsfrei vergeben",
            lambda: ident == {"magic": 770003, "prefix": "P3",
                              "snapshot": "prophos_master_ftmo1.csv"}))

        # 27) Neue Config erbt Hedge-Felder, Master-Felder neu; KEIN mode-Feld
        # mehr — auch nicht aus der Basis geerbt (25.08.2026, Modus-Ausbau:
        # der Copier sendet immer echt, das Feld ist abgeschafft)
        cfg = provision.build_master_config(base, name="ftmo1", master_login=555001,
                                            terminal_path="C:\\MT5-ftmo1\\terminal64.exe",
                                            ident=ident)
        results.append(prov(
            "PROVISION: Config erbt Hedge-Ziel, kein mode-Feld, keine _kommentare",
            lambda: cfg["hedge_expected_login"] == 400002
                    and "mode" not in cfg
                    and "mode" not in provision.build_master_config(
                        dict(base, mode="live"), name="x1",
                        master_login=1, terminal_path="C:\\x\\terminal64.exe",
                        ident=ident)
                    and cfg["master_expected_login"] == 555001
                    and cfg["magic"] == 770003
                    and "_kommentar" not in cfg))

        # 27b) magic_base pro PC (27.08.2026): teilt sich der PC das Hedge-Konto
        # mit anderen, vergibt die Provisionierung im eigenen 1000er-Block.
        # Reine Blocklogik (base verschiebt Start + Praefix zaehlt im Block):
        magic_base_logik = (
            provision.next_magic(set(), 771000) == 771001
            and provision.next_magic({771001, 771002}, 771000) == 771003
            and provision.prefix_for(771001, set(), 771000) == "PH"
            and provision.prefix_for(771002, {"PH"}, 771000) == "P2"
            # Bestands-PC ohne magic_base bleibt exakt wie bisher (Default 770000):
            and provision.next_magic({770001, 770002}) == 770003)
        # Und end-zu-end an einem FRISCHEN Ordner (= eigener PC von ID B, eigener
        # Ordner): der erste Account landet sauber im 771000er-Block mit PH.
        with tempfile.TemporaryDirectory() as td2:
            # Vorlage ohne magic/comment_prefix — genau wie die echte
            # config.vorlage.json (die ist kein Account).
            _json.dump({"hedge_expected_login": 400004,
                        "master_terminal_path": "C:\\MT5-Master\\terminal64.exe",
                        "magic_base": 771000},
                       open(os.path.join(td2, "config.vorlage.json"), "w"))
            ident_block1 = provision.alloc_identity(td2, "idb1", magic_base=771000)
        results.append(prov(
            "PROVISION: magic_base verschiebt den Block; frischer PC → magic 771001, Praefix PH",
            lambda: magic_base_logik
                    and ident_block1 == {"magic": 771001, "prefix": "PH",
                                         "snapshot": "prophos_master_idb1.csv"}))

        # 28) plan_checks faengt die Nutzerfehler ab
        probs = provision.plan_checks(td, "böse name!", "abc", "", None)
        results.append(prov(
            "PROVISION: plan_checks meldet Name/Login/Server/Vorlage-Fehler",
            lambda: len(probs) >= 4))

        # 29) Vorhandener Account wird nicht ueberschrieben
        _json.dump({}, open(os.path.join(td, "config-ftmo1.json"), "w"))
        probs2 = provision.plan_checks(td, "ftmo1", "555001", "Srv", None)
        results.append(prov(
            "PROVISION: existierende config-ftmo1.json blockiert das Anlegen",
            lambda: any("bereits angelegt" in p for p in probs2)))

    # 29b) Trade-Fenster (25.08.2026, Finns Ansage: Copier nicht 24/7 scharf):
    # 'laufend' oeffnet immer, 'geplant' nur frisch (<= 6h), 'beendet' und
    # Eintraege ohne brauchbare Zeit nie.
    from copier import plan_armed_files
    from datetime import datetime as _dt
    _now = _dt(2026, 8, 25, 12, 0, 0)
    _plans = [
        {"file": "config-a.json", "status": "laufend", "armed_at": "2026-08-20T00:00:00"},
        {"file": "config-b.json", "status": "geplant", "armed_at": "2026-08-25T09:00:00"},
        {"file": "config-c.json", "status": "geplant", "armed_at": "2026-08-24T09:00:00"},
        {"file": "config-d.json", "status": "beendet", "armed_at": "2026-08-25T11:59:00"},
        {"file": "config-e.json", "status": "geplant"},
    ]
    results.append(prov(
        "TRADE-FENSTER: laufend immer, geplant nur frisch (6h), beendet/ohne Zeit nie",
        lambda: plan_armed_files(_plans, _now) == {"config-a.json", "config-b.json"}
                and plan_armed_files([], _now) == set()
                and plan_armed_files(None, _now) == set()))

    # 30) Startdateien: Login-ini transient, StartUp-ini ohne Zugangsdaten
    ini = provision.build_login_ini(555001, "geheim", "FusionMarkets-Demo")
    sup = provision.build_startup_ini(preset="prophos-ftmo1.set")
    results.append(prov(
        "PROVISION: Login-ini mit KeepPrivate=1, StartUp-ini ohne Passwort",
        lambda: "Password=geheim" in ini and "Login=555001" in ini
                and "KeepPrivate=1" in ini
                and "Password" not in sup and "Expert=ProphosHedgeReader" in sup
                and "ExpertParameters=prophos-ftmo1.set" in sup))

    # ── Order-Bot: reine Rechenlogik (15.08.2026) ──────────────────────────
    import order_bot

    def chk(name, cond):
        results.append(cond)
        print(("✓ " if cond else "✗ ") + name)
        return cond

    sl, tp = order_bot.berechne_sl_tp("buy", 20000.0, 0.2, 1.0, sl_usd=100, tp_usd=300)
    chk("ORDER-BOT: BUY 0.2 @ 20000, SL $100/TP $300 → 19500 / 21500",
        sl == 19500.0 and tp == 21500.0)
    sl, tp = order_bot.berechne_sl_tp("sell", 20000.0, 1.0, 10.0, sl_usd=100, tp_usd=300)
    chk("ORDER-BOT: SELL, Kontraktgroesse 10 → SL 20010 / TP 19970 (gespiegelt)",
        sl == 20010.0 and tp == 19970.0)
    # F9-Direktweg (02.09.2026): SL/TP werden schon im Order-Dialog aus dem
    # Vor-Fill-Kurs gerechnet — BUY vom Ask, SELL vom Bid. Nagelt die Ref-Wahl
    # fest, damit ein Umbau sie nicht still vertauscht (waere SL/TP am falschen
    # Kursende). Ask=20002, Bid=20000, Spread 2.
    slb, tpb = order_bot.berechne_sl_tp("buy", 20002.0, 0.2, 1.0, sl_usd=100, tp_usd=300)
    chk("ORDER-BOT: F9-BUY rechnet vom Ask (SL unter, TP ueber dem Ask)",
        slb < 20002.0 < tpb)
    sls, tps = order_bot.berechne_sl_tp("sell", 20000.0, 0.2, 1.0, sl_usd=100, tp_usd=300)
    chk("ORDER-BOT: F9-SELL rechnet vom Bid (SL ueber, TP unter dem Bid)",
        tps < 20000.0 < sls)
    f = order_bot.pruefe_befehl({"symbol": "NDX100", "richtung": "buy",
                                 "volumen": 0.2, "sl_usd": 100, "tp_usd": 300})
    chk("ORDER-BOT: vollstaendiger Befehl → keine Fehler", f == [])
    f = order_bot.pruefe_befehl({"symbol": "", "richtung": "kaufen", "volumen": 0})
    chk("ORDER-BOT: kaputter Befehl → Symbol/Richtung/Volumen gemeldet (SL/TP optional)",
        len(f) == 3)
    # SL/TP-Schalter (18.08.2026): beide weg = ok, nur eines = Fehler
    f = order_bot.pruefe_befehl({"symbol": "NDX100", "richtung": "buy", "volumen": 0.2})
    chk("ORDER-BOT: Befehl OHNE SL/TP (Schalter aus) → gueltig", f == [])
    f = order_bot.pruefe_befehl({"symbol": "NDX100", "richtung": "buy",
                                 "volumen": 0.2, "sl_usd": 100})
    chk("ORDER-BOT: nur SL ohne TP → genau ein Fehler (nur zusammen)", len(f) == 1)
    f = order_bot.pruefe_befehl({"symbol": "NDX100", "richtung": "buy",
                                 "volumen": float("nan"), "sl_usd": 100, "tp_usd": 300})
    chk("ORDER-BOT: NaN-Volumen wird abgelehnt (isfinite-Wachter)", len(f) == 1)
    # SL/TP-per-Klick-Helfer (18.08.2026): reine Textlogik am Mac testbar
    chk("ORDER-BOT: Aendern-Knopf erkannt, Abbrechen/Loeschen/Schliessen nicht",
        order_bot.ist_aendern_knopf("#123 buy 0.20 NAS100 sl: 19500.00 tp: 21500.00 ändern")
        and order_bot.ist_aendern_knopf("Modify")
        and not order_bot.ist_aendern_knopf("Abbrechen")
        and not order_bot.ist_aendern_knopf("Löschen")
        and not order_bot.ist_aendern_knopf("Close #123 buy 0.20")
        and not order_bot.ist_aendern_knopf(""))
    chk("ORDER-BOT: SL/TP-Bestaetigung mit Rundungs-Toleranz, 0.0 faellt durch",
        order_bot.sltp_bestaetigt(19500.01, 21500.0, 19500.0, 21500.0, 2)
        and not order_bot.sltp_bestaetigt(0.0, 21500.0, 19500.0, 21500.0, 2)
        and not order_bot.sltp_bestaetigt(19400.0, 21500.0, 19500.0, 21500.0, 2))
    chk("ORDER-BOT: Ticket-Suche trifft nur die eigene Zeile",
        order_bot.zeile_nennt_ticket("123456789 NAS100 buy 0.20", 123456789)
        and not order_bot.zeile_nennt_ticket("9123456789 NAS100", 123456789)
        and not order_bot.zeile_nennt_ticket("", 123456789))
    # Order-Panel per UIA finden (25.09.2026, Popup-Fall): angedockt rechts vs. frei schwebend
    # mittig — beide liefern Units/TP/SL im Bereich; Reiter ohne Felder = 'ohne_felder'; ein
    # 'Markt'-Text anderswo (ohne Felder darunter) gewinnt nicht gegen das echte Ticket.
    def _roh_ticket(x, y):
        return [("Buy", (x + 10, y - 60, x + 190, y - 30), "Text"), ("Sell", (x + 200, y - 60, x + 380, y - 30), "Text"),
                ("Markt", (x + 10, y, x + 80, y + 24), "TabItem"), ("Limit", (x + 90, y, x + 150, y + 24), "TabItem"),
                ("Stop", (x + 160, y, x + 220, y + 24), "TabItem"), ("Stop Limit", (x + 230, y, x + 330, y + 24), "TabItem"),
                ("Einheiten", (x + 10, y + 60, x + 100, y + 80), "Text"), ("Take Profit, $", (x + 10, y + 140, x + 130, y + 160), "Text"),
                ("Stop-Loss, $", (x + 10, y + 220, x + 130, y + 240), "Text"), ("Kauf 5 MNQZ6 MARKT", (x + 10, y + 320, x + 380, y + 360), "Button")]
    fenster = (0, 0, 1920, 1080)
    ang = order_bot.tv_panel_bereich(_roh_ticket(1500, 250), fenster)
    pop = order_bot.tv_panel_bereich(_roh_ticket(1000, 300) + [("Markt", (600, 270, 660, 296), "Text"), ("Stop Limit", (700, 270, 790, 296), "Text"),
                                                              ("Positions", (1050, 950, 1120, 970), "TabItem"), ("Account Balance", (1200, 990, 1320, 1008), "Text")], fenster)
    ohne = order_bot.tv_panel_bereich([("Market", (600, 270, 660, 296), "Text"), ("Stop Limit", (700, 270, 790, 296), "Text")], fenster)
    def _findet(ber, x):
        u = order_bot.tv_im_panel(_roh_ticket(x, ber["reiter_y"] - 12), ber, order_bot.TV_RX_UNITS, y_von=ber["reiter_y"])
        tp = order_bot.tv_im_panel(_roh_ticket(x, ber["reiter_y"] - 12), ber, order_bot.TV_RX_TP, y_von=ber["reiter_y"])
        sl = order_bot.tv_im_panel(_roh_ticket(x, ber["reiter_y"] - 12), ber, order_bot.TV_RX_SL, y_von=ber["reiter_y"])
        return len(u) == 1 and len(tp) == 1 and len(sl) == 1
    chk("ORDER-BOT: Order-Panel angedockt rechts per UIA gefunden (Units/TP/SL im Bereich, modus angedockt)",
        ang and not ang["ohne_felder"] and ang["modus"] == "angedockt" and ang["labels"] == 3
        and ang["links"] <= 1510 and ang["rechts"] >= 1830 and ang["reiter_y"] == 262 and _findet(ang, 1500)
        and ang["spur"].startswith("Panel: angedockt @"))
    dock2 = order_bot.tv_panel_bereich(_roh_ticket(900, 300) + [("Watchlist", (1450, 120, 1550, 140), "Text"), ("NQ1!", (1450, 200, 1500, 220), "DataItem")], fenster)
    chk("ORDER-BOT: angedockt mit Watchlist rechts daneben bleibt 'angedockt' (nichts unter der Box)",
        dock2 and dock2["modus"] == "angedockt" and dock2["darunter"] == 0 and dock2["rand_rechts"] > 80
        and "0 Elemente darunter" in dock2["spur"])
    chk("ORDER-BOT: Order-Panel als Popup mittig gefunden, 'Markt'-Text anderswo gewinnt nicht (modus Popup, Elemente darunter)",
        pop and not pop["ohne_felder"] and pop["modus"] == "Popup" and pop["labels"] == 3 and pop["darunter"] == 2
        and pop["links"] <= 1010 and pop["rechts"] >= 1330 and pop["reiter_y"] == 312 and pop["market"]["punkt"][0] == 1045
        and _findet(pop, 1000) and "Popup @" in pop["spur"])
    chk("ORDER-BOT: Reiter-Zeile ohne Beschriftungen darunter → ohne_felder (kein Blindklick), keine Reiter → None",
        ohne and ohne["ohne_felder"] and ohne["modus"] == "Reiter ohne Felder"
        and order_bot.tv_panel_bereich([("Einheiten", (10, 10, 50, 30), "Text")], fenster) is None
        and order_bot.tv_panel_bereich([], None) is None)
    # Neues TradingView-Layout (25.09.2026, Finns Screenshot, angedockt): Reiterzeile 1 'Order | DOM',
    # Verkauf/Kauf, Reiterzeile 2 'Markt … Stop Limit', 'Einheiten' als AUFKLAPPMENUE (ComboBox), daneben
    # 'Ø USD Risiko', 'Take Profit, $' / 'Stop-Loss, $' ebenfalls Menues mit Schalter rechts.
    _NL = [("Order", (1500, 120, 1560, 144), "TabItem"), ("DOM", (1570, 120, 1620, 144), "TabItem"),
           ("Verkauf 30.827,25", (1500, 170, 1650, 220), "Button"), ("Kauf 30.827,75", (1660, 170, 1810, 220), "Button"),
           ("Markt", (1510, 250, 1560, 274), "TabItem"), ("Limit", (1580, 250, 1630, 274), "TabItem"),
           ("Stop", (1650, 250, 1700, 274), "TabItem"), ("Stop Limit", (1720, 250, 1810, 274), "TabItem"),
           ("Einheiten", (1510, 300, 1600, 322), "ComboBox"), ("Ø USD Risiko", (1660, 300, 1800, 322), "ComboBox"),
           ("Tick Wert 2,50 USD", (1510, 360, 1650, 378), "Text"), ("Aussteige", (1510, 400, 1600, 418), "Text"),
           ("Take Profit, $", (1510, 440, 1640, 462), "ComboBox"), ("Stop-Loss, $", (1510, 520, 1640, 542), "ComboBox"),
           ("Time-in-Force Day", (1510, 600, 1700, 618), "Text"), ("Kauf 5 MNQZ6 MARKT", (1510, 700, 1810, 740), "Button")]
    _nl_felder = [(1510, 326, 1640, 350), (1660, 326, 1800, 350), (1510, 466, 1640, 490), (1510, 546, 1640, 570)]
    _nl_werte = ["5", "12,50", "250", "100"]
    _nl_schalter = [((1770, 442, 1806, 460), True), ((1770, 522, 1806, 540), False)]
    _nb = order_bot.tv_panel_bereich(_NL, (0, 0, 1920, 1080))
    chk("ORDER-BOT (neues Layout): reiter_y auf der Markt-Zeile, nicht auf 'Order | DOM'; Beschriftungen als ComboBox gefunden",
        _nb and _nb["reiter_y"] == 262 and _nb["labels"] == 3 and _nb["modus"] == "angedockt"
        and len(order_bot.tv_im_panel(_NL, _nb, order_bot.TV_RX_UNITS, y_von=_nb["reiter_y"])) == 1
        and order_bot.tv_im_panel(_NL, _nb, order_bot.TV_RX_UNITS, y_von=_nb["reiter_y"])[0]["typ"] == "ComboBox"
        and len(order_bot.tv_im_panel(_NL, _nb, order_bot.TV_RX_TP, y_von=_nb["reiter_y"])) == 1
        and len(order_bot.tv_im_panel(_NL, _nb, order_bot.TV_RX_SL, y_von=_nb["reiter_y"])) == 1)
    _lab_u = order_bot.tv_im_panel(_NL, _nb, order_bot.TV_RX_UNITS, y_von=_nb["reiter_y"])
    _lab_tp = order_bot.tv_im_panel(_NL, _nb, order_bot.TV_RX_TP, y_von=_nb["reiter_y"])
    chk("ORDER-BOT (neues Layout): Feld unter 'Einheiten' ist das linke (nicht 'Ø USD Risiko'), Schalter zu 'Take Profit' gefunden",
        order_bot.tv_label_mit_feld(_lab_u, _nl_felder, _nb)[1] == 0
        and order_bot.tv_label_mit_feld(_lab_tp, _nl_felder, _nb)[1] == 2
        and order_bot.tv_schalter_zu(_nl_schalter, _lab_tp[0]["r"], _nb) == ((1770, 442, 1806, 460), True))
    # Rueckfall ohne jede Beschriftung: Units = oberstes Zahlenfeld, TP/SL ueber die Schalter-Zeilen
    _ohne = [e for e in _NL if e[2] != "ComboBox"]
    _nb2 = order_bot.tv_panel_bereich(_ohne, (0, 0, 1920, 1080))
    _iu = order_bot.tv_feld_ohne_label(_nl_felder, _nl_werte, {"links": 1480, "rechts": 1840}, 262)
    _zeilen = order_bot.tv_schalter_zeilen(_nl_schalter, {"links": 1480, "rechts": 1840}, 350)
    _lab_sl = {"r": (1490, _zeilen[1][1], _zeilen[1][0] - 6, _zeilen[1][3])}
    chk("ORDER-BOT (Rueckfall): ohne Beschriftungen → ohne_felder; Units = oberstes Zahlenfeld; TP/SL-Zeilen in Reihenfolge, Feld unter der SL-Zeile",
        _nb2 and _nb2["ohne_felder"] and _iu == 0 and len(_zeilen) == 2 and _zeilen[0][1] == 442 and _zeilen[1][1] == 522
        and order_bot.tv_feld_unter(_nl_felder, _lab_sl["r"], {"links": 1480, "rechts": 1840}) == 3
        and order_bot.tv_feld_ohne_label([(1510, 200, 1600, 220)], ["5"], {"links": 1480, "rechts": 1840}, 262) is None)
    # Deutsch (25.09.2026, Finn: 'Englisch geht sofort, Deutsch nicht'): Namen mit weichem Trennstrich,
    # geschuetztem Leerzeichen und Menue-Pfeil, Beschriftung als Hyperlink/Group — normalisiert getroffen
    _DE = [("Markt", (1510, 250, 1560, 274), "TabItem"), ("Stop\u00a0Limit", (1720, 250, 1810, 274), "TabItem"),
           ("Ein\u00adheiten \u25be", (1510, 300, 1600, 322), "Hyperlink"), ("Take\u00a0Profit, $ \u25be", (1510, 440, 1640, 462), "Group"),
           ("Stop-Loss, $\u25bc", (1510, 520, 1640, 542), "Menu"), ("Order", (1500, 120, 1560, 144), "TabItem")]
    _db = order_bot.tv_panel_bereich(_DE, (0, 0, 1920, 1080))
    chk("ORDER-BOT (Deutsch): weicher Trennstrich, NBSP, Menue-Pfeil, Typen Hyperlink/Group/Menu → Reiter + 3 Beschriftungen",
        _db and _db["labels"] == 3 and _db["reiter_y"] == 262
        and order_bot.tv_im_panel(_DE, _db, order_bot.TV_RX_UNITS, y_von=_db["reiter_y"])[0]["text"] == "Einheiten"
        and order_bot.tv_im_panel(_DE, _db, order_bot.TV_RX_TP, y_von=_db["reiter_y"])[0]["text"] == "Take Profit, $"
        and "$" in order_bot.tv_im_panel(_DE, _db, order_bot.TV_RX_SL, y_von=_db["reiter_y"])[0]["text"]
        and order_bot.tv_name_norm("  Ein\u00adheiten\u00a0\u25be ") == "Einheiten"
        and bool(order_bot.TV_RX_UNITS.search("Stück")) and bool(order_bot.TV_RX_UNITS.search("Anzahl"))
        and not order_bot.TV_RX_UNITS.search("Order") and not order_bot.TV_RX_TP.search("Tick Wert 2,50 USD"))
    _inv = order_bot.tv_panel_inventar(_NL, _nb, 4)
    chk("ORDER-BOT (Spur): Inventar unter der Reiterzeile nennt Typ, Name und Rechteck",
        _inv.startswith("ComboBox:Einheiten@1510,300,1600,322 | ComboBox:Ø USD Risiko@") and _inv.count("|") == 3
        and "Kauf 30" not in _inv)
    # Zuruecklesen mit Nachlesen (25.09.2026, pc-iiiiii: 'Stop loss: im Feld steht '?' statt 250.0')
    def _folge(werte):
        it = iter(werte)
        return lambda: next(it, None)
    _pausen = []
    _w = lambda: _pausen.append(1)
    r1 = order_bot.tv_wert_nachlesen(_folge([None, 250.0]), 250.0, _w)
    r2 = order_bot.tv_wert_nachlesen(_folge([25.0, 25.0, 250.0]), 250.0, _w)
    r3 = order_bot.tv_wert_nachlesen(_folge([25.0, None, 25.0]), 250.0, _w)
    r4 = order_bot.tv_wert_nachlesen(_folge([None, None, None]), 250.0, _w)
    r5 = order_bot.tv_wert_nachlesen(_folge([250.004]), 250.0, _w)
    chk("ORDER-BOT: Zuruecklesen — Feld kurz weg (None) → 2. Lesung ok; abgeschnitten '25' → bis 3 Lesungen; nie mehr als 3",
        r1 == (True, 250.0, 2) and r2 == (True, 250.0, 3) and r3 == (False, 25.0, 3) and r4 == (False, None, 3)
        and r5[0] is True and r5[2] == 1 and len(_pausen) == 1 + 2 + 2 + 2)
    # Ruecklese-Vergleich (18.08.2026, Feld zeigte '2', MT5 rechnete 0.01):
    # als Zahl vergleichen, MT5-Umformatierung und Locale duerfen nicht stoeren
    chk("ORDER-BOT: Ruecklese-Vergleich als Zahl (Umformatierung/Locale egal)",
        order_bot.zahl_gleich("2.00", "2")
        and order_bot.zahl_gleich("19 500,00", "19500.00")
        and not order_bot.zahl_gleich("0.01", "2")
        and not order_bot.zahl_gleich("", "2"))
    # Bestaetigen-Knopf vs. 'Position aendern'-Reiter (18.08.2026)
    chk("ORDER-BOT: Bestaetigen-Knopf erkannt, Reiter/Abbrechen nicht",
        order_bot.ist_bestaetigen_knopf(
            "Ändern #512345477 buy 1 NAS100 30006.46 sl: 30003.46 tp: 30339.46")
        and not order_bot.ist_bestaetigen_knopf("Position ändern")
        and not order_bot.ist_bestaetigen_knopf("Abbrechen")
        and not order_bot.ist_bestaetigen_knopf("Ändern"))
    # Handel-Zeile vs. Chart-Titel/Navigator (18.08.2026, EA-Dialog-Vorfall)
    chk("ORDER-BOT: Handel-Zeile erkannt, Chart-Titel/Navigator nicht",
        order_bot.ist_handelszeile("nas100, 512309082, buy, 1.00, 29992.33", "NAS100")
        and not order_bot.ist_handelszeile("NAS100,M1: US Tech 100 Index", "NAS100")
        and not order_bot.ist_handelszeile("ProphosHedgeReader - NAS100,M1", "NAS100")
        and not order_bot.ist_handelszeile("", "NAS100"))
    # Rueckkehr nach Prophos (28.08.2026, Finns 'Ausgangssituation'): Home-Base
    # braucht Titel UND Browser-Klasse — die Backend-Konsole heisst selbst
    # 'Prophos-Backend' (title in start-prophos.bat) und darf NIE Treffer sein.
    chk("ORDER-BOT: Prophos-Fenster erkannt (Chrome-Tab, PWA-Huelle, Firefox)",
        order_bot.ist_prophos_fenster("Prophos - Google Chrome", "Chrome_WidgetWin_1")
        and order_bot.ist_prophos_fenster("Prophos", "Chrome_WidgetWin_1")
        and order_bot.ist_prophos_fenster("Prophos — Mozilla Firefox", "MozillaWindowClass"))
    chk("ORDER-BOT: Backend-Konsole/MT5-Terminal sind KEIN Prophos-Fenster",
        not order_bot.ist_prophos_fenster("Prophos-Backend", "ConsoleWindowClass")
        and not order_bot.ist_prophos_fenster("Prophos-Backend", "CASCADIA_HOSTING_WINDOW_CLASS")
        and not order_bot.ist_prophos_fenster("400001: FTMO-Demo", order_bot.MT5_KLASSE))
    chk("ORDER-BOT: DevTools/leerer Titel/leere Klasse sind KEIN Prophos-Fenster",
        not order_bot.ist_prophos_fenster("DevTools - prophos.pages.dev/prophos", "Chrome_WidgetWin_1")
        and not order_bot.ist_prophos_fenster("", "Chrome_WidgetWin_1")
        and not order_bot.ist_prophos_fenster("Prophos", ""))
    # Orbit-Puls Schritt 1 (28.08.2026): TradingView-Fenster erkennen. Der
    # Fenstertitel ist immer der AKTIVE Tab — 'tradingview' steht mitten im
    # Titel (Chart davor, Browser-Name dahinter), daher contains; DevTools
    # tragen die URL im Titel und duerfen NIE Treffer sein.
    chk("ORDER-BOT: TradingView-Fenster erkannt (Chrome/Firefox, Chart-Titel)",
        order_bot.ist_tradingview_fenster("NQZ2026 Chart — TradingView - Google Chrome", "Chrome_WidgetWin_1")
        and order_bot.ist_tradingview_fenster("TradingView — Track All Markets — Mozilla Firefox", "MozillaWindowClass")
        and order_bot.ist_tradingview_fenster("(1) MNQ1! 1m CME — TradingView", "Chrome_WidgetWin_1"))
    chk("ORDER-BOT: DevTools/Prophos/Konsole/MT5 sind KEIN TradingView-Fenster",
        not order_bot.ist_tradingview_fenster("DevTools - www.tradingview.com/chart", "Chrome_WidgetWin_1")
        and not order_bot.ist_tradingview_fenster("Prophos - Google Chrome", "Chrome_WidgetWin_1")
        and not order_bot.ist_tradingview_fenster("tradingview", "ConsoleWindowClass")
        and not order_bot.ist_tradingview_fenster("", "Chrome_WidgetWin_1")
        and not order_bot.ist_tradingview_fenster("TradingView", order_bot.MT5_KLASSE))

    # ── Futures-Puls Neuaufbau Schritt 1 (21.09.2026): TradingView starten ──
    # Die URL kommt aus einer Config-Datei und landet in einem Browser, in dem
    # Prop-Konten eingeloggt sind — alles ausser https://…tradingview.com/ muss
    # still auf den Standard zurueckfallen.
    chk("TV-START: URL — nur https + tradingview.com, sonst Standard",
        order_bot.tv_start_url("") == order_bot.TV_START_URL
        and order_bot.tv_start_url(None) == order_bot.TV_START_URL
        and order_bot.tv_start_url("https://www.tradingview.com/chart/AbC123/") == "https://www.tradingview.com/chart/AbC123/"
        and order_bot.tv_start_url("https://de.tradingview.com/chart/") == "https://de.tradingview.com/chart/"
        and order_bot.tv_start_url("http://www.tradingview.com/chart/") == order_bot.TV_START_URL
        and order_bot.tv_start_url("https://www.tradingview.com.evil.io/chart/") == order_bot.TV_START_URL
        and order_bot.tv_start_url("https://evil.io/?x=https://www.tradingview.com/") == order_bot.TV_START_URL
        and order_bot.tv_start_url("https://www.tradingview.com/chart/ --remote-debugging-port=1") == order_bot.TV_START_URL)
    chk("TV-START: Chrome-Aufruf — eigenes Fenster, Profil nur wenn gesetzt, URL zuletzt",
        order_bot.tv_start_befehl("C:/c.exe", "") == ["C:/c.exe", "--new-window", order_bot.TV_START_URL]
        and order_bot.tv_start_befehl("C:/c.exe", "", "Profile 2")
            == ["C:/c.exe", "--profile-directory=Profile 2", "--new-window", order_bot.TV_START_URL]
        and order_bot.tv_start_befehl("C:/c.exe", "ftp://x", "  ")[-1] == order_bot.TV_START_URL)

    # ── Futures-Puls Neuaufbau Schritt 2a (21.09.2026): richtiges Konto? ──
    # Ein Fehlurteil 'richtig' hiesse spaeter: Order auf dem falschen Prop-Konto.
    _bf = lambda aktiv, schalter=True: {"konto": {"aktiv": aktiv, "schalter": ({"x": 1} if schalter else None)}}
    chk("TV-KONTO: Zustand — richtig / falsch / kein Broker",
        order_bot.tv_konto_zustand(_bf("FNFTCH-150k-4711 · Demo"), "FNFTCH150K4711") == ("richtig", "FNFTCH-150k-4711 · Demo")
        and order_bot.tv_konto_zustand(_bf("TDFYSL50K99"), "FNFTCH150K4711")[0] == "falsch"
        and order_bot.tv_konto_zustand(_bf("", schalter=False), "FNFTCH150K4711") == ("kein_broker", "")
        and order_bot.tv_konto_zustand({}, "FNFTCH150K4711")[0] == "kein_broker"
        and order_bot.tv_konto_zustand(None, "FNFTCH150K4711")[0] == "kein_broker"
        # Schalter da, Text leer: es STEHT etwas da, nur nicht lesbar -> nie 'richtig'
        and order_bot.tv_konto_zustand(_bf(""), "FNFTCH150K4711")[0] == "falsch"
        # zu kurze External ID matcht nie (Riegel aus tv_konto_passt)
        and order_bot.tv_konto_zustand(_bf("PA-12"), "12")[0] == "falsch")
    chk("TV-KONTO: Befehl — External ID Pflicht, Username optional aber sauber, geschwister = Liste",
        order_bot.pruefe_tv_konto_befehl({"ext_id": "FNFTCH4711", "tv_username": "FNF_finn"}) == []
        and order_bot.pruefe_tv_konto_befehl({"ext_id": "FNFTCH4711"}) == []
        and len(order_bot.pruefe_tv_konto_befehl({"ext_id": "12", "tv_username": ""})) == 1
        and len(order_bot.pruefe_tv_konto_befehl({"ext_id": "FNFTCH4711", "tv_username": "a b"})) == 1
        and len(order_bot.pruefe_tv_konto_befehl({"ext_id": "FNFTCH4711", "tv_username": "a\tb"})) == 1
        and len(order_bot.pruefe_tv_konto_befehl({"ext_id": "FNFTCH4711", "geschwister": "x"})) == 1
        and order_bot.pruefe_tv_konto_befehl("x") != [])
    # Finns Korrektur 21.09.2026: im Dropdown steht nur der Kontoname. Derselbe
    # Login wird ueber die Geschwister-Konten derselben Firma bewiesen.
    _g = ["APEX-123-02", "APEX-123-011"]
    chk("TV-KONTO: Geschwister — gleicher Login erkannt, fremdes Konto bleibt 'falsch'",
        order_bot.tv_konto_zustand(_bf("APEX-123-02 · PA"), "APEX-123-01", _g)[0] == "gleicher_login"
        and order_bot.tv_konto_zustand(_bf("APEX-123-01 · PA"), "APEX-123-01", _g)[0] == "richtig"
        and order_bot.tv_konto_zustand(_bf("TDFY-999-01"), "APEX-123-01", _g)[0] == "falsch"
        and order_bot.tv_konto_zustand(_bf("APEX-123-02"), "APEX-123-01", [])[0] == "falsch")
    # Teilstring-Falle: 'APEX-123-01' steckt in 'APEX-123-011'. Ohne die
    # Laengste-ID-Regel gaelte das Geschwister-Konto als das Zielkonto — und
    # die Order ginge spaeter aufs falsche Konto.
    chk("TV-KONTO: laengste passende ID gewinnt (…-01 ist nicht …-011)",
        order_bot.tv_konto_zustand(_bf("APEX-123-011"), "APEX-123-01", _g)[0] == "gleicher_login"
        and order_bot.tv_konto_zustand(_bf("APEX-123-011"), "APEX-123-011", ["APEX-123-01"])[0] == "richtig"
        and order_bot.tv_konto_bestes("APEX-123-011 · PA", ["APEX-123-01", "APEX-123-011"]) == "APEX-123-011"
        and order_bot.tv_konto_bestes("TDFY", ["APEX-123-01"]) == "")
    _e = lambda t, **k: dict({"text": t, "rect": {"x": 1, "y": 1, "w": 9, "h": 9}}, **k)
    chk("TV-KONTO: Dropdown-Eintrag — genau einer, nie der laengere Namensvetter, nie ein mehrdeutiger",
        order_bot.tv_konto_eintrag([_e("APEX-123-01"), _e("APEX-123-011"), _e("APEX-123-02")], "APEX-123-01", _g)[0]["text"] == "APEX-123-01"
        and order_bot.tv_konto_eintrag([_e("APEX-123-011"), _e("APEX-123-02")], "APEX-123-01", _g) == (None, 0)
        and order_bot.tv_konto_eintrag([_e("APEX-123-01"), _e("APEX-123-01 (2)")], "APEX-123-01", _g) == (None, 2)
        and order_bot.tv_konto_eintrag([_e("APEX-123-01", fehlt=True)], "APEX-123-01", _g) == (None, 0)
        and order_bot.tv_konto_eintrag([{"text": "APEX-123-01"}], "APEX-123-01", _g) == (None, 0)
        and order_bot.tv_konto_eintrag(None, "APEX-123-01", _g) == (None, 0))

    # Finns erster PC-Lauf 21.09.2026: richtiges Konto sichtbar im Panel, Bot
    # meldete 'kein Broker' — die data-name-Anker des Userscripts trafen nichts.
    # Nachgestellt: konto{} leer, die Kontonummer steht nur in der panel-Liste,
    # dreifach verschachtelt (Huelle > Knopf > Textspanne), Fenster 1900x990.
    _G = {"innerWidth": 1900, "innerHeight": 990, "dpr": 1}
    _P = lambda *els: {"geo": _G, "konto": {"aktiv": "", "schalter": None, "eintraege": []}, "panel": list(els)}
    _el = lambda text, x, y, w, h: {"tag": "div", "text": text, "rect": [x, y, w, h]}
    _finn = _P(_el("Tradovate", 70, 850, 120, 30),
               _el("APEX0000000000024 USD", 72, 905, 200, 34),      # Huelle
               _el("APEX0000000000024 USD", 76, 908, 190, 28),      # Knopf
               _el("APEX0000000000024", 84, 912, 130, 20),           # Textspanne
               _el("Positions", 75, 950, 80, 28))
    chk("TV-KONTO: Kontonummer im Panel-Text schlaegt fehlenden Anker (Finns Lauf 21.09.)",
        order_bot.tv_konto_zustand(_finn, "APEX0000000000024", [])[0] == "richtig"
        and order_bot.tv_konto_zustand(_finn, "APEX0000000000031", ["APEX0000000000024"])[0] == "gleicher_login"
        and order_bot.tv_konto_zustand(_finn, "TDFY123456", ["TDFY999999"])[0] == "kein_broker")
    chk("TV-KONTO: Text-Suche — verschachtelte Treffer werden EIN Element (das innerste)",
        [e["rect"] for e in order_bot.tv_konto_per_text(_finn, ["APEX0000000000024"])] == [[84, 912, 130, 20]])
    # Offene Aufklappliste: zwei bekannte Konten sichtbar -> welcher aktiv ist,
    # sagt der Text nicht -> NIE 'richtig' aus dem Text-Weg.
    _offen = _P(_el("APEX0000000000024 USD", 76, 908, 190, 28), _el("APEX0000000000031 USD", 76, 860, 190, 28))
    chk("TV-KONTO: Text-Suche — zwei bekannte Konten sichtbar = kein Urteil",
        order_bot.tv_konto_zustand(_offen, "APEX0000000000024", ["APEX0000000000031"])[0] == "kein_broker")
    chk("TV-KONTO: Text-Suche — Nummer in der oberen Fensterhaelfte zaehlt nicht, fuer Listeneintraege doch",
        order_bot.tv_konto_per_text(_P(_el("APEX0000000000024", 300, 200, 150, 20)), ["APEX0000000000024"]) == []
        and len(order_bot.tv_konto_per_text(_P(_el("APEX0000000000024", 300, 200, 150, 20)), ["APEX0000000000024"], ueberall=True)) == 1)
    chk("TV-KONTO: Text-Suche — Listeneintrag nur das ZIEL, nie der Umschalter selbst",
        [e["text"] for e in order_bot.tv_konto_per_text(_offen, ["APEX0000000000024", "APEX0000000000031"],
            nur_ziel="APEX0000000000031", ohne=(76, 908, 190, 28), ueberall=True)] == ["APEX0000000000031 USD"]
        and order_bot.tv_konto_per_text(_offen, ["APEX0000000000024"], nur_ziel="APEX0000000000024",
            ohne=(76, 908, 190, 28), ueberall=True) == [])
    chk("TV-KONTO: Diagnose — nur der untere Bereich, ohne Doppelte, klein genug fuer die Zwischenablage",
        [e["text"] for e in order_bot.tv_diagnose(dict(_finn, dump=_finn["panel"] + [_el("Trade", 1700, 20, 60, 30)]))["unten"]]
            == ["Tradovate", "APEX0000000000024 USD", "APEX0000000000024 USD", "APEX0000000000024", "Positions"]
        and order_bot.tv_diagnose(None)["unten"] == [])

    # Finns ZWEITER Lauf 21.09.2026: Dropdown ging auf, "0 Eintraege" — die
    # Liste haengt am Ende des DOM, hinter der Kappung von panel/dump. Seit
    # Userscript 0.4.2 kommt 'treffer' (gezielte Suche im ganzen DOM); ist das
    # Feld da, gilt NUR es — auch leer.
    _T = lambda treffer, *panel: dict(_P(*panel), treffer=treffer, version="0.4.2")
    _tr = lambda text, x, y, w=190, h=28: {"rect": [x, y, w, h], "text": text, "rolle": "option", "liste": True}
    _zu = _T([_tr("APEX0000000000031", 84, 912, 130, 20)])
    _auf = _T([_tr("APEX0000000000031", 84, 912, 130, 20),                 # Umschalter
               _tr("APEX0000000000024", 90, 300), _tr("APEX0000000000031", 90, 340),
               _tr("APEX0000000000047", 90, 380)])
    _ids = ["APEX0000000000024", "APEX0000000000031", "APEX0000000000047"]
    chk("TV-KONTO: 'treffer' — Zustand bei geschlossener Liste, Zieleintrag bei offener (auch oben im Fenster)",
        order_bot.tv_konto_zustand(_zu, "APEX0000000000024", _ids[1:])[0] == "gleicher_login"
        and [e["rect"] for e in order_bot.tv_konto_per_text(_auf, _ids, nur_ziel="APEX0000000000024",
             ohne=(84, 912, 130, 20), ueberall=True)] == [[90, 300, 190, 28]]
        # aktives Konto steht ZWEIMAL da (Umschalter + Liste): als Ziel gesucht
        # bleibt nur der Listeneintrag, der Umschalter ist ausgenommen
        and [e["rect"] for e in order_bot.tv_konto_per_text(_auf, _ids, nur_ziel="APEX0000000000031",
             ohne=(84, 912, 130, 20), ueberall=True)] == [[90, 340, 190, 28]])
    chk("TV-KONTO: 'treffer' vorhanden aber leer schlaegt die gekappte panel-Liste (nie beides mischen)",
        order_bot.tv_konto_per_text(_T([], _el("APEX0000000000024", 84, 912, 130, 20)), _ids) == []
        and len(order_bot.tv_konto_per_text(dict(_P(_el("APEX0000000000024", 84, 912, 130, 20)), treffer=None), _ids)) == 1)
    chk("TV-KONTO: Userscript-Mindestversion",
        order_bot.tv_version_min("0.4.2", "0.4.2") and order_bot.tv_version_min("0.5.0", "0.4.2")
        and order_bot.tv_version_min("0.4.10", "0.4.2")
        and not order_bot.tv_version_min("0.4.1", "0.4.2") and not order_bot.tv_version_min(None, "0.4.2")
        and not order_bot.tv_version_min("abc", "0.4.2"))

    # Augen ohne Userscript (21.09.2026, Finn: 'ohne Tampermonkey'): Chromes
    # Accessibility-Baum ueber Windows-UIA. Rechtecke sind echte Bildschirm-Pixel
    # (l,t,r,b). Nachgestellt: Fenster 0,0-1920,1040, Umschalter unten links,
    # offene Liste darueber, jeder Eintrag als ListItem-Huelle + Text.
    _F = (0, 0, 1920, 1040)
    _sw = ("APEX0000000000031 USD", (84, 960, 260, 984))
    _li = [("APEX0000000000024", (90, 700, 300, 728)), ("APEX0000000000024", (96, 704, 230, 724)),
           ("APEX0000000000031", (90, 740, 300, 768)), ("APEX0000000000031", (96, 744, 230, 764)),
           ("APEX0000000000047", (90, 780, 300, 808)), ("TDFY000123456", (90, 820, 300, 848))]
    chk("TV-UIA: geschlossene Liste = genau ein Element = Urteil moeglich; Klickpunkt = Mitte in Bildschirm-Pixeln",
        [(e["id"], e["punkt"]) for e in order_bot.tv_uia_filtern([_sw], _ids, _F)] == [("APEX0000000000031", (172, 972))])
    chk("TV-UIA: offene Liste — Ziel genau einmal (innerstes Element), Umschalter ausgenommen, fremdes Konto nie",
        [e["r"] for e in order_bot.tv_uia_filtern([_sw] + _li, _ids, _F, nur_ziel="APEX0000000000024", ohne=_sw[1])] == [(96, 704, 230, 724)]
        and [e["r"] for e in order_bot.tv_uia_filtern([_sw] + _li, _ids, _F, nur_ziel="APEX0000000000031", ohne=_sw[1])] == [(96, 744, 230, 764)]
        and order_bot.tv_uia_filtern([_sw] + _li, _ids, _F, nur_ziel="TDFY000123456") == []
        and len(order_bot.tv_uia_filtern([_sw] + _li, _ids, _F)) == 4)
    chk("TV-UIA: ausserhalb des Fensters / Nullgroesse / kaputtes Rechteck zaehlt nie",
        order_bot.tv_uia_filtern([("APEX0000000000024", (2500, 700, 2700, 728))], _ids, _F) == []
        and order_bot.tv_uia_filtern([("APEX0000000000024", (90, 700, 90, 728))], _ids, _F) == []
        and order_bot.tv_uia_filtern([("APEX0000000000024", None), ("APEX0000000000024", ("a", 1, 2, 3))], _ids, _F) == []
        and order_bot.tv_uia_filtern(None, _ids, _F) == [])

    # Schritt 2b (21.09.2026 nachts): Tradovate-Login wechseln. Gefunden wird
    # ueber sichtbare NAMEN — die Muster muessen eng sein, denn daneben stehen
    # Knoepfe, die NIE getroffen werden duerfen.
    chk("TV-LOGIN: Login-Knopf nur EXAKT — nie 'Sign in with Google/Apple'",
        all(order_bot.TV_RX_LOGIN.search(x) for x in ("Login", "Log in", "Sign in", "Anmelden", "login"))
        and not any(order_bot.TV_RX_LOGIN.search(x) for x in
                    ("Sign in with Google", "Sign in with Apple", "Login help", "Need help?", "Mit Google anmelden")))
    chk("TV-LOGIN: Abmelden / Connect / Demo / Broker — deutsch und englisch, nichts Benachbartes",
        all(order_bot.TV_RX_LOGOUT.search(x) for x in ("Log out", "Logout", "Sign out", "Abmelden", "Disconnect", "Verbindung trennen"))
        and not any(order_bot.TV_RX_LOGOUT.search(x) for x in ("Login", "Trading settings", "Go to broker", "Abbrechen"))
        and all(order_bot.TV_RX_CONNECT.search(x) for x in ("Connect", "Connect broker", "Verbinden"))
        and not any(order_bot.TV_RX_CONNECT.search(x) for x in ("Cannot connect to broker? Let us know", "Connected", "Disconnect"))
        and order_bot.TV_RX_DEMO.search("Demo") and not order_bot.TV_RX_DEMO.search("Demo account info")
        and order_bot.TV_RX_BROKER.search("Tradovate") and order_bot.TV_RX_BROKER.search("Tradovate 4.4")
        and not order_bot.TV_RX_BROKER.search("Tradovated") and not order_bot.TV_RX_BROKER.search("Connect Tradovate")
        and order_bot.TV_RX_KACHELSICHT.search("Paper Trading") and not order_bot.TV_RX_TRADE.search("Trade with your broker"))
    _N = [("Tradovate", (70, 850, 190, 880), "Button"), ("Tradovate", (100, 856, 170, 874), "Text"),
          ("Tradovate", (900, 300, 1000, 330), "Text"), ("Trade", (1700, 10, 1760, 40), "Button"),
          ("Unsichtbar", None, "Button"), ("Tradovate", (5000, 850, 5100, 880), "Button")]
    chk("TV-LOGIN: Namens-Filter — Bereich (unten/oben), innerstes Element, rect=None und ausserhalb raus",
        [e["r"] for e in order_bot.tv_uia_namen_filtern(_N, order_bot.TV_RX_BROKER, _F, y_von=0.5)] == [(100, 856, 170, 874)]
        and len(order_bot.tv_uia_namen_filtern(_N, order_bot.TV_RX_BROKER, _F)) == 2
        and [e["punkt"] for e in order_bot.tv_uia_namen_filtern(_N, order_bot.TV_RX_TRADE, _F, y_bis=0.15)] == [(1730, 25)]
        and order_bot.tv_uia_namen_filtern(_N, order_bot.TV_RX_TRADE, _F, y_von=0.5) == [])
    chk("TV-LOGIN: Tasten-Escape — Sonderzeichen im Username werden nicht zu Tastenkombinationen",
        order_bot.tv_tasten_escape("APEX_000000") == "APEX_000000"
        and order_bot.tv_tasten_escape("max+apex(1)") == "max{+}apex{(}1{)}"
        and order_bot.tv_tasten_escape("a^b%c~d") == "a{^}b{%}c{~}d")
    chk("TV-LOGIN: Diagnose-Inventar — kurz, ohne Doppelte, lange Texte (News) raus",
        order_bot.tv_uia_inventar(_N + [("x" * 60, (1, 1, 9, 9), "Text")]) ==
            ["Button:Tradovate@70,850", "Text:Tradovate@100,856", "Button:Trade@1700,10", "Button:Unsichtbar"])

    # Finns erster 2b-Lauf (21.09.2026 nachts): aktiv war 'PAAPEX0000000000008' —
    # darin steckt 'APEX0000000000008' als Teilstring. Zwei verschiedene Konten.
    chk("TV-KONTO: ganze Woerter statt Teilstring — PAAPEX…008 ist NICHT APEX…008",
        not order_bot.tv_konto_wort_passt("PAAPEX0000000000008 USD", "APEX0000000000008")
        and order_bot.tv_konto_wort_passt("PAAPEX0000000000008 USD", "PAAPEX0000000000008")
        and order_bot.tv_konto_wort_passt("APEX0000000000024 USD", "APEX0000000000024")
        and order_bot.tv_konto_wort_passt("APEX-123-01 · PA", "APEX12301")
        and order_bot.tv_konto_wort_passt("Konto (APEX-123-01)", "APEX-123-01")
        and not order_bot.tv_konto_wort_passt("APEX-123-011", "APEX-123-01")
        and not order_bot.tv_konto_wort_passt("PA-12", "12")
        and order_bot.tv_konto_zustand(_bf("PAAPEX0000000000008 USD"), "APEX0000000000008", [])[0] == "falsch")
    chk("TV-LOGIN: Menuepunkt 'Connect another broker…' und kontonummer-artige Namen",
        order_bot.TV_RX_ANDERER_BROKER.search("Connect another broker…")
        and order_bot.TV_RX_ANDERER_BROKER.search("Anderen Broker verbinden…")
        and not order_bot.TV_RX_ANDERER_BROKER.search("Connect broker")
        and not order_bot.TV_RX_ANDERER_BROKER.search("Trading settings…")
        and all(order_bot.TV_RX_KONTOARTIG.search(x) for x in ("PAAPEX0000000000008 USD", "APEX0000000000024", "TDFY-123456-01 EUR"))
        and not any(order_bot.TV_RX_KONTOARTIG.search(x) for x in ("Account Balance", "157,501.40", "NQU2026", "Tradovate", "29,613.75 USD")))
    _K = [("Tradovate", (640, 470, 740, 500), "Text"), ("Tradovate", (660, 400, 720, 460), "Image"),
          ("Tradovate", (110, 970, 180, 995), "Text"), ("Tradovate", (80, 965, 210, 1000), "Button")]
    chk("TV-LOGIN: Kachel — Bild-Alt neben dem Text ist EIN Ding (Typ-Vorrang), Broker-Knopf unten ausgenommen",
        [e["r"] for e in order_bot.tv_uia_namen_filtern(_K, order_bot.TV_RX_BROKER, _F, 0.08, 0.78, ohne=(80, 965, 210, 1000))] == [(640, 470, 740, 500)]
        and [e["r"] for e in order_bot.tv_uia_namen_filtern(_K, order_bot.TV_RX_BROKER, _F, y_von=0.5)] == [(110, 970, 180, 995)])
    chk("TV-LOGIN: Spur fuer die Fehlermeldung — nur Einschlaegiges, kurz",
        order_bot.tv_uia_spur([("Trade", None, "Button"), ("Indicators", None, "Button"), ("Tradovate", (1, 1, 9, 9), "Text"),
                               ("Log out", None, "MenuItem"), ("x" * 50 + "broker", None, "Text")]) == "Button:Trade | Text:Tradovate | MenuItem:Log out"
        and order_bot.tv_uia_spur([]) == "nichts Einschlaegiges")

    # Fund der Simulation (21.09.2026 nachts): der Username steckt als Teilstring
    # in einer Kontonummer — der Autofill-Vorschlag darf nur als GANZES WORT passen.
    chk("TV-LOGIN: Autofill — Username nur als ganzes Wort, nie in 'PAAPEX0000000000008'",
        order_bot.tv_konto_wort_passt("APEX_000000", "APEX_000000")
        and order_bot.tv_konto_wort_passt("APEX_000000, ••••••••", "APEX_000000")
        and order_bot.tv_konto_wort_passt("apex_000000 tradovate.com", "APEX_000000")
        and not order_bot.tv_konto_wort_passt("PAAPEX0000000000008 USD", "APEX_000000")
        and not order_bot.tv_konto_wort_passt("APEX_0000000", "APEX_000000"))

    # Direkt-Adresse zum Tradovate-Dialog (am echten TradingView bewiesen,
    # 21.09.2026 nachts) — ersetzt Knopf "Trade" + Kachel-Suche.
    chk("TV-LOGIN: trade-now-Adresse — Layout bleibt, fremde Parameter fallen weg, fremde Domain nie",
        order_bot.tv_trade_now_url("") == "https://www.tradingview.com/chart/?trade-now=TRADOVATE"
        and order_bot.tv_trade_now_url("https://www.tradingview.com/chart/BRKeE9Lw/?symbol=CME_MINI%3ANQU2026")
            == "https://www.tradingview.com/chart/BRKeE9Lw/?trade-now=TRADOVATE"
        and order_bot.tv_trade_now_url("https://evil.io/chart/") == "https://www.tradingview.com/chart/?trade-now=TRADOVATE"
        and order_bot.tv_trade_now_url("https://www.tradingview.com/symbols/NQ/") == "https://www.tradingview.com/chart/?trade-now=TRADOVATE")
    chk("TV-LOGIN: Namenslisten der gezielten Suche passen zu ihren Mustern (sonst findet die eine, was der Filter verwirft)",
        all(order_bot.TV_RX_LOGOUT.search(n) for n in order_bot.TV_NAMEN_LOGOUT)
        and all(order_bot.TV_RX_CONNECT.search(n) for n in order_bot.TV_NAMEN_CONNECT)
        and all(order_bot.TV_RX_LOGIN.search(n) for n in order_bot.TV_NAMEN_LOGIN)
        and all(order_bot.TV_RX_DEMO.search(n) for n in order_bot.TV_NAMEN_DEMO)
        and all(order_bot.TV_RX_BROKER.search(n) for n in order_bot.TV_NAMEN_BROKER))

    # Finns Screenshots 21.09.2026 22:04: die Tradovate-Anmeldung ist ein TAB im
    # selben Fenster — Chromes Adressleiste liegt als ERSTES Eingabefeld im Baum.
    class _Fd:
        def __init__(s, l, t, r, b): s._r = (l, t, r, b)
        def rectangle(s):
            return type("R", (), dict(left=s._r[0], top=s._r[1], right=s._r[2], bottom=s._r[3]))()
    _adr, _usr, _pw, _such = _Fd(160, 160, 1400, 190), _Fd(1081, 467, 1518, 508), _Fd(1081, 554, 1518, 596), _Fd(1090, 300, 1400, 330)
    chk("TV-LOGIN: Username-Feld = direkt UEBER dem Passwortfeld — nie die Adressleiste, nie ein entferntes Feld",
        order_bot.tv_feld_darueber([_adr, _usr, _pw], _pw, (1081, 554, 1518, 596)) is _usr
        and order_bot.tv_feld_darueber([_adr, _pw], _pw, (1081, 554, 1518, 596)) is None
        and order_bot.tv_feld_darueber([_adr, _such, _usr, _pw], _pw, (1081, 554, 1518, 596)) is _usr
        and order_bot.tv_feld_darueber([], _pw, (1081, 554, 1518, 596)) is None)

    # Finns Weg (22.09.2026): TradingView-Tab schliessen, neu mit dem Link
    # oeffnen. Strg+W darf NUR in einen Tab gehen, der nachweislich TradingView
    # ist — nie in den Prophos-Tab.
    chk("TV-LOGIN: Strg+W nur in TradingView — nie Prophos, nie irgendein anderer Tab",
        order_bot.tv_tab_schliessbar("NQU2026 29,613.75 ▲ +0.57% Unnamed - Google Chrome", "Chrome_WidgetWin_1")
        and order_bot.tv_tab_schliessbar("NQZ2026 Chart — TradingView - Google Chrome", "Chrome_WidgetWin_1")
        and not order_bot.tv_tab_schliessbar("Prophos - Google Chrome", "Chrome_WidgetWin_1")
        and not order_bot.tv_tab_schliessbar("Tradeify Futures - User Dashboard - Google Chrome", "Chrome_WidgetWin_1")
        and not order_bot.tv_tab_schliessbar("Cockpit | Duplikium Trade Copier - Google Chrome", "Chrome_WidgetWin_1")
        and not order_bot.tv_tab_schliessbar("", "Chrome_WidgetWin_1")
        and not order_bot.tv_tab_schliessbar("NQU2026 29,613.75 ▲ +0.57% Unnamed", "ConsoleWindowClass"))

    # Finns Idee 22.09.2026: "Don't remember me" bei jedem Verbinden setzen.
    chk("TV-LOGIN: 'Don't remember me' — erkannt in allen Schreibweisen, nichts Benachbartes",
        all(order_bot.TV_RX_NICHT_MERKEN.search(x) for x in
            ("Don't remember me", "Don’t remember me", "Do not remember me", "Nicht merken", "Nicht speichern"))
        and not any(order_bot.TV_RX_NICHT_MERKEN.search(x) for x in
                    ("Remember me", "Connect", "Demo", "Cannot connect to broker? Let us know."))
        and all(order_bot.TV_RX_NICHT_MERKEN.search(n) for n in order_bot.TV_NAMEN_NICHT_MERKEN))

    # Schritt 3 (22.09.2026): Asset ueber die Watchlist. Nachgestellt nach Finns
    # Screenshot: Fenster 0,107-2000,1190; Watchlist rechts oben mit NQZ2026 /
    # MNQZ2026, darunter der Detail-Kasten mit demselben Symbol, links oben der
    # Symbol-Knopf des Charts, im Order-Panel der Kontrakt.
    _WF = (0, 107, 2000, 1190)
    _WL = [("BTC1!", (70, 205, 130, 230), "Button"),                       # Chart-Symbol links oben
           ("NQZ2026", (1680, 333, 1740, 353), "Text"), ("MNQZ2026", (1680, 365, 1748, 385), "Text"),
           ("E-mini Nasdaq-100 Futures (Dec 2026)", (1656, 770, 1900, 790), "Text"),
           ("NQZ2026", (1690, 733, 1752, 755), "Text"),                    # Detail-Kasten UNTER der Watchlist
           ("30,787.00", (1745, 333, 1808, 353), "Text"), ("Watchlist", (1656, 256, 1720, 276), "Text")]
    chk("TV-ASSET: Watchlist — NQ und MNQ sauber getrennt, oberste Fundstelle gewinnt, nie der Chart-Knopf links",
        order_bot.tv_watchlist_zeile(_WL, "NQ", _WF)[0]["r"] == (1680, 333, 1740, 353)
        and order_bot.tv_watchlist_zeile(_WL, "MNQ", _WF)[0]["r"] == (1680, 365, 1748, 385)
        and order_bot.tv_watchlist_zeile(_WL, "ES", _WF) == (None, 0)
        and order_bot.tv_watchlist_zeile([("NQZ2026", (70, 205, 130, 230), "Button")], "NQ", _WF) == (None, 0)
        and order_bot.tv_watchlist_zeile(_WL, "", _WF) == (None, 0)
        and order_bot.tv_watchlist_zeile(None, "NQ", _WF) == (None, 0))
    chk("TV-ASSET: zwei Treffer auf derselben Hoehe = mehrdeutig, kein Klick",
        order_bot.tv_watchlist_zeile([("NQZ2026", (1680, 333, 1740, 353), "Text"), ("NQZ6", (1850, 335, 1900, 355), "Text")], "NQ", _WF) == (None, 2))
    chk("TV-ASSET: Beweis am Fenstertitel — Prophos-Symbol und TradingView-Symbol haben dieselbe Wurzel",
        order_bot.tv_titel_wurzel("NQZ2026 30,787.00 ▲ +0.01% Unnamed - Google Chrome") == order_bot.tv_symbol_root("NQZ6") == "NQ"
        and order_bot.tv_titel_wurzel("MNQZ2026 30,786.25 ▲ +0.01% Unnamed - Google Chrome") == order_bot.tv_symbol_root("MNQZ6") == "MNQ"
        and order_bot.tv_titel_wurzel("BTC1! 86,680 ▲ +0.1% Unnamed - Google Chrome") == "BTC"
        and order_bot.tv_titel_wurzel("(1) NQZ2026 30,787.00 ▼ −0.2% Unnamed") == "NQ")

    # Bruecke am Panel vorbei (22.09.2026): neue Felder reisen als '@feld=wert'
    # in der geschwister-Liste. Sie duerfen NIE als Kontonummer gelten.
    _br = order_bot.tv_bruecke_auspacken({"ext_id": "APEX1", "geschwister":
          ["@symbol=MNQZ6", "@richtung=sell", "@volumen=1", "@tp_usd=", "@boese=1", "APEX0000000000031", "@kaputt"]})
    chk("TV-BRUECKE: Marken werden Felder, verschwinden aus der Liste, Unbekanntes wird verworfen",
        _br["symbol"] == "MNQZ6" and _br["richtung"] == "sell" and _br["volumen"] == "1"
        and _br.get("tp_usd") in (None, "") and "boese" not in _br
        and _br["geschwister"] == ["APEX0000000000031", "@kaputt"]
        and order_bot.tv_konto_zustand(_bf("MNQZ6"), "APEX1XX", _br["geschwister"])[0] == "falsch")
    chk("TV-BRUECKE: ein echtes Feld im Befehl gewinnt gegen die Marke",
        order_bot.tv_bruecke_auspacken({"symbol": "NQZ6", "geschwister": ["@symbol=MNQZ6"]})["symbol"] == "NQZ6"
        and order_bot.tv_bruecke_auspacken({"geschwister": None})["geschwister"] == [])

    # Schritt 4a (22.09.2026): Order-Panel ausfuellen. Nachgestellt nach Finns
    # Screenshot — inklusive der Schnell-Knoepfe SELL/BUY links im Chart, die
    # NIE getroffen werden duerfen.
    _OP = [("SELL", (70, 275, 150, 310), "Button"), ("BUY", (188, 275, 270, 310), "Button"),
           ("Market", (1337, 415, 1383, 435), "Text"), ("Limit", (1418, 415, 1452, 435), "Text"),
           ("Stop", (1494, 415, 1523, 435), "Text"), ("Stop Limit", (1550, 415, 1617, 435), "Text"),
           ("Sell 30,827.25", (1326, 345, 1470, 398), "Button"), ("Sell", (1335, 350, 1360, 366), "Text"),
           ("Buy 30,827.75", (1472, 345, 1618, 398), "Button"), ("Buy", (1584, 350, 1608, 366), "Text"),
           ("Stop loss, $", (1325, 700, 1400, 718), "Text"), ("Market open", (1675, 911, 1750, 929), "Text"),
           ("Buy 1 MNQZ6 MARKET", (1325, 920, 1618, 978), "Button")]
    _ber = order_bot.tv_panel_bereich(_OP)
    chk("TV-ORDER: Panel-Anker aus der Reiter-Zeile; ohne 'Stop Limit' auf derselben Zeile kein Panel",
        _ber is not None and _ber["links"] == 1295 and _ber["rechts"] == 1648 and _ber["market"]["punkt"] == (1360, 425)   # seit 25.09.2026: links inkl. 'Stop loss, $' (1325 − 30), rechts inkl. Senden-Knopf (1618 + 30)
        and order_bot.tv_panel_bereich([x for x in _OP if x[0] != "Stop Limit"]) is None
        and order_bot.tv_panel_bereich([("Market", (1337, 415, 1383, 435), "Text"), ("Stop Limit", (1550, 700, 1617, 720), "Text")]) is None)
    chk("TV-ORDER: Seite nur IM Panel und nur ueber der Reiter-Zeile — nie die Schnell-Knoepfe im Chart, innerstes Element",
        [e["r"] for e in order_bot.tv_im_panel(_OP, _ber, order_bot.TV_RX_SEITE["buy"], y_von=_ber["reiter_y"] - 150, y_bis=_ber["reiter_y"] - 12)] == [(1584, 350, 1608, 366)]
        and [e["r"] for e in order_bot.tv_im_panel(_OP, _ber, order_bot.TV_RX_SEITE["sell"], y_von=_ber["reiter_y"] - 150, y_bis=_ber["reiter_y"] - 12)] == [(1335, 350, 1360, 366)])
    chk("TV-ORDER: Kauf-Knopf nur UNTER der Stop-Loss-Zeile — der Seiten-Kasten 'Buy 30,827.75' ist keiner",
        [e["text"] for e in order_bot.tv_im_panel(_OP, _ber, order_bot.TV_RX_SENDEN, y_von=718)] == ["Buy 1 MNQZ6 MARKET"]
        and len(order_bot.tv_im_panel(_OP, _ber, order_bot.TV_RX_SENDEN, y_von=_ber["reiter_y"] - 150)) == 3)
    _FR = [(1326, 485, 1460, 520), (1326, 643, 1460, 678), (1500, 643, 1617, 678), (1326, 730, 1460, 765), (160, 160, 1400, 190), None]
    chk("TV-ORDER: Wertfeld = direkt unter der Beschriftung, das LINKE; nie das Umrechnungsfeld, nie die Adressleiste",
        order_bot.tv_feld_unter(_FR, (1325, 612, 1415, 630), _ber) == 1
        and order_bot.tv_feld_unter(_FR, (1325, 700, 1400, 718), _ber) == 3
        and order_bot.tv_feld_unter(_FR, (1325, 462, 1360, 480), _ber) == 0
        and order_bot.tv_feld_unter(_FR, (1325, 900, 1400, 918), _ber) is None)
    # Finns Lauf 22.09.: "'Units' nicht eindeutig (2 Treffer)" — Text + Name des Auswahlmenues.
    _L2 = [{"text": "Units", "r": (1325, 462, 1360, 480), "punkt": (1342, 471)},
           {"text": "Units", "r": (1500, 300, 1560, 318), "punkt": (1530, 309)}]
    chk("TV-ORDER: doppelte Beschriftung — es zaehlt die MIT Eingabefeld darunter, sonst keine",
        order_bot.tv_label_mit_feld(_L2, _FR, _ber)[0]["r"] == (1325, 462, 1360, 480)
        and order_bot.tv_label_mit_feld(_L2, _FR, _ber)[1] == 0
        and order_bot.tv_label_mit_feld([_L2[1]], _FR, _ber) == (None, None)
        and order_bot.tv_label_mit_feld([], _FR, _ber) == (None, None))
    chk("TV-ORDER: Zahlen lesen — englisch, deutsch, mit Einheit; nichts Zaehlbares = None",
        order_bot.tv_zahl_lesen("17.00") == 17.0 and order_bot.tv_zahl_lesen("1,875.00") == 1875.0
        and order_bot.tv_zahl_lesen("1.875,00") == 1875.0 and order_bot.tv_zahl_lesen("12,5") == 12.5
        and order_bot.tv_zahl_lesen("1,875") == 1875.0 and order_bot.tv_zahl_lesen("25 ticks") == 25.0
        and order_bot.tv_zahl_lesen("") is None and order_bot.tv_zahl_lesen("abc") is None)
    chk("TV-ORDER: Plan — leerer SL heisst AUS (Finns Regel), Menge muss ganze Kontrakte sein",
        order_bot.tv_order_plan({"richtung": "SELL", "volumen": "1", "tp_usd": "300", "sl_usd": ""})[0] == {"richtung": "sell", "menge": 1, "tp": 300.0, "sl": None}
        and order_bot.tv_order_plan({"richtung": "buy", "volumen": 2, "tp_usd": None, "sl_usd": "0"})[0] == {"richtung": "buy", "menge": 2, "tp": None, "sl": None}
        and order_bot.tv_order_plan({"richtung": "buy", "volumen": "1.5"})[0] is None
        and order_bot.tv_order_plan({"richtung": "", "volumen": "1"})[0] is None
        and order_bot.tv_order_plan({"richtung": "buy", "volumen": "0"})[0] is None)
    # Schritt 4b (22.09.2026): der Kauf-Klick haengt an EINER ausdruecklichen Marke.
    chk("TV-ORDER 4b: scharf nur mit Marke (bool oder Bruecken-Text '1') — nie bei 'false'/'0'/leer, nie mit probe",
        order_bot.tv_ist_scharf({"scharf": True}) and order_bot.tv_ist_scharf({"scharf": "1"})
        and not order_bot.tv_ist_scharf({}) and not order_bot.tv_ist_scharf({"scharf": False})
        and not order_bot.tv_ist_scharf({"scharf": "false"}) and not order_bot.tv_ist_scharf({"scharf": "0"})
        and not order_bot.tv_ist_scharf({"scharf": ""}) and not order_bot.tv_ist_scharf({"scharf": None})
        and not order_bot.tv_ist_scharf({"scharf": True, "probe": True})
        and not order_bot.tv_ist_scharf({"scharf": "1", "probe": "1"}))
    chk("TV-ORDER 4b: die Marke reist ueber die Bruecke (altes Panel) und ist nie eine Kontonummer",
        order_bot.tv_ist_scharf(order_bot.tv_bruecke_auspacken({"scharf": False, "geschwister": ["@scharf=1", "APEX1"]}))
        and order_bot.tv_bruecke_auspacken({"geschwister": ["@scharf=1", "APEX1"]})["geschwister"] == ["APEX1"]
        and not order_bot.tv_ist_scharf(order_bot.tv_bruecke_auspacken({"geschwister": ["APEX1"]})))
    # 4b-Beweis ohne Reader (22.09.2026, Finns Lauf: Reader pausiert, Duplikium kopiert):
    # die Positions-Tabelle unten in TradingView. Anker = Kopf 'Symbol' unter dem Reiter
    # 'Positions'; Side/Qty optional (Finns Remote-Lauf 01:39: Chrome nannte nur 'Symbol').
    _PT = [("Symbol", (1656, 297, 1700, 315), "Text"),                      # Watchlist-Kopf: nie der Anker
           ("Positions", (72, 932, 130, 950), "TabItem"), ("Orders", (154, 932, 200, 950), "TabItem"),
           ("Symbol", (56, 979, 120, 997), "DataItem"), ("Side", (213, 979, 240, 997), "Text"), ("Qty", (433, 979, 456, 997), "Text"),
           ("MNQZ6", (75, 1020, 125, 1038), "Text"), ("Short", (213, 1020, 250, 1038), "Text"), ("-3", (433, 1020, 445, 1038), "Text"),
           ("NQZ6", (75, 1054, 125, 1072), "Text"), ("Long", (213, 1054, 250, 1072), "Text"), ("2", (433, 1054, 445, 1072), "Text"),
           ("MNQZ2026", (1680, 365, 1748, 385), "Text")]
    _ohne = lambda d: (d and {k: v for k, v in d.items() if k != "anker"})
    chk("TV-ORDER 4b: Positions-Tabelle — Zeile nur bei passender Wurzel UND Seite, MNQ nie NQ, Watchlist zaehlt nie",
        _ohne(order_bot.tv_positions_tabelle(_PT, "MNQZ6", "sell")) == {"menge": 3.0, "zeilen": 1, "spalten": True}
        and _ohne(order_bot.tv_positions_tabelle(_PT, "MNQZ6", "buy")) == {"menge": 0.0, "zeilen": 0, "spalten": True}
        and _ohne(order_bot.tv_positions_tabelle(_PT, "NQZ6", "buy")) == {"menge": 2.0, "zeilen": 1, "spalten": True}
        and _ohne(order_bot.tv_positions_tabelle(_PT[:6], "MNQZ6", "sell")) == {"menge": 0.0, "zeilen": 0, "spalten": True}
        and order_bot.tv_positions_tabelle(_PT, "MNQZ6", "sell")["anker"] == (56, 979, 120, 997))
    # Reiter durch Meldungen verdeckt (22.09.2026 09:50): der Anker aus dem Vorher-Blick traegt weiter
    chk("TV-ORDER 4b: ohne sichtbaren Reiter zaehlt die Tabelle nur mit dem Anker aus dem Vorher-Blick (+-20 px)",
        order_bot.tv_positions_tabelle([x for x in _PT if x[0] != "Positions"], "MNQZ6", "sell") is None
        and _ohne(order_bot.tv_positions_tabelle([x for x in _PT if x[0] != "Positions"], "MNQZ6", "sell", anker=(56, 979, 120, 997))) == {"menge": 3.0, "zeilen": 1, "spalten": True}
        and order_bot.tv_positions_tabelle([x for x in _PT if x[0] != "Positions"], "MNQZ6", "sell", anker=(56, 700, 120, 718)) is None)
    _PT2 = [x for x in _PT if x[0] not in ("Side", "Qty")]              # Finns Lauf: nur 'Symbol' benannt
    chk("TV-ORDER 4b: ohne Side/Qty zaehlen Zeilen mit der Symbol-Wurzel in der Symbol-Spalte (Menge unbekannt)",
        _ohne(order_bot.tv_positions_tabelle(_PT2, "MNQZ6", "sell")) == {"menge": 0.0, "zeilen": 1, "spalten": False}
        and _ohne(order_bot.tv_positions_tabelle(_PT2, "NQZ6", "sell")) == {"menge": 0.0, "zeilen": 1, "spalten": False}
        and _ohne(order_bot.tv_positions_tabelle(_PT2, "ESZ6", "sell")) == {"menge": 0.0, "zeilen": 0, "spalten": False})
    chk("TV-ORDER 4b: ohne Reiter 'Positions' ueber dem Kopf gibt es KEINEN Tabellen-Beweis (None, nicht 'flach')",
        order_bot.tv_positions_tabelle([x for x in _PT if x[0] != "Positions"], "MNQZ6", "sell") is None
        and order_bot.tv_positions_tabelle(_PT[:1] + _PT[6:], "MNQZ6", "sell") is None
        and order_bot.tv_positions_tabelle([], "MNQZ6", "sell") is None
        and "Symbol@56,979" in order_bot.tv_positions_zone(_PT))
    # Avg Fill je Wurzel + Tabellen-Diagnose (25.09.2026, Plan …: Nachlauf 'nicht lesbar (3 s)')
    _PTF = _PT + [("Avg Fill Price", (560, 979, 660, 997), "Text"), ("30,725.25", (560, 1020, 640, 1038), "Text"),
                  ("30.710,50", (560, 1054, 640, 1072), "Text")]
    _zf = order_bot.tv_positionen_auspacken(order_bot.tv_positions_lesen(_PTF, order_bot.tv_positions_kopf(_PTF)))
    _af = order_bot.tv_avg_fill_je_wurzel(_zf)
    chk("TV-LESEN: avg_fill_je_wurzel aus der Positions-Tabelle (englisch + deutsch), MNQ nie NQ",
        _af.get("MNQ", {}).get("avg_fill") == 30725.25 and _af.get("NQ", {}).get("avg_fill") == 30710.5
        and _af["MNQ"]["symbol"] == "MNQZ6" and order_bot.tv_avg_fill_je_wurzel([]) == {}
        and order_bot.tv_avg_fill_je_wurzel([{"symbol": "MNQZ6", "einstieg": None}]) == {}
        and order_bot.tv_avg_fill_je_wurzel([{"symbol": "MNQZ6", "einstieg": "—"}, {"symbol": "MNQZ6", "einstieg_zahl": 30100.0}])["MNQ"]["avg_fill"] == 30100.0)
    _d1 = order_bot.tv_tabellen_diagnose(_PTF, None, "MNQZ6")
    _d2 = order_bot.tv_tabellen_diagnose([x for x in _PTF if x[0] != "Positions"], None, "MNQZ6")
    _d3 = order_bot.tv_tabellen_diagnose([x for x in _PTF if x[0] != "Positions"], (56, 979, 120, 997), "MNQZ6")
    chk("TV-ORDER: Tabellen-Diagnose — Kopf/Zeilen/Einstieg-Spalte/erste Zeile/Zone, verdeckter Reiter mit und ohne Anker",
        _d1.startswith("Kopf ja · Zeilen 2 · Zeilen MNQ 1 · Einstieg-Spalte ja · erste Zeile MNQZ6 Einstieg '30,725.25'")
        and _d2.startswith("Kopf nein · Zeilen 0") and "kein Reiter 'Positions' zu sehen" in _d2
        and _d3.startswith("Kopf ja (per Anker) · Zeilen 2") and order_bot.tv_tabellen_diagnose(None, None, "X").startswith("Kopf nein"))
    # Schalter + Meldung (22.09.2026 01:50, Finns Lauf: SL vergessen, weil 'Feld bedienbar'
    # als 'Schalter an' galt). Umschalter = gleiche Zeile, rechts, der aeusserste im Panel.
    _BER = {"links": 1300, "rechts": 1630}
    _SCH = [((1580, 612, 1615, 630), False), ((1580, 700, 1615, 718), True), ((1470, 703, 1490, 717), True), ((1800, 702, 1830, 718), False)]
    chk("TV-ORDER 4b: Umschalter zur Beschriftung — gleiche Zeile, ganz rechts im Panel, nie ausserhalb",
        order_bot.tv_schalter_zu(_SCH, (1325, 612, 1415, 630), _BER) == ((1580, 612, 1615, 630), False)
        and order_bot.tv_schalter_zu(_SCH, (1325, 700, 1400, 718), _BER) == ((1580, 700, 1615, 718), True)
        and order_bot.tv_schalter_zu(_SCH, (1325, 462, 1360, 480), _BER) == (None, None)
        and order_bot.tv_schalter_zu(None, (1325, 612, 1415, 630), _BER) == (None, None))
    _TO = [("Take Profit order placed on MNQZ6", (130, 1100, 420, 1120), "Text"), ("Sell 2 at 30,858.25", (130, 1125, 300, 1140), "Text"),
           ("Order filled: Buy 1 NQZ2026", (130, 1150, 400, 1170), "Text"), ("Start creating order", (1325, 920, 1618, 978), "Button"),
           ("Take Profit order placed on ESZ6", None, "Text")]
    chk("TV-ORDER 4b: TradingViews Order-Meldungen — Symbol im Text muss die Plan-Wurzel sein, ohne Symbol zaehlt sie; nie Unsichtbares oder der Kauf-Knopf",
        order_bot.tv_order_meldungen(_TO, "MNQZ6") == ["Take Profit order placed on MNQZ6"]
        and order_bot.tv_order_meldungen(_TO, "NQZ6") == ["Order filled: Buy 1 NQZ2026"]
        and order_bot.tv_order_meldungen(_TO, "ESZ6") == []
        and order_bot.tv_order_meldungen([("Take Profit order placed on", (130, 1100, 400, 1120), "Text"), ("Stop Loss order placed on", (130, 1130, 400, 1150), "Text")], "NQZ6")
            == ["Take Profit order placed on", "Stop Loss order placed on"])
    # Fill aus der Meldung (28.09.2026, Vorfall ID C …: Einstieg aus dem Feed 12 Pkt neben dem echten Fill)
    _ME = [("Market order executed on", (130, 1040, 330, 1058), "Text"), ("MNQZ6", (335, 1040, 390, 1058), "Hyperlink"),
           ("Buy 4 at 30,838.00", (130, 1062, 300, 1078), "Text"),
           ("Take Profit order placed on", (130, 1100, 330, 1118), "Text"), ("MNQZ6", (335, 1100, 390, 1118), "Hyperlink"),
           ("Sell 4 at 30,872.75", (130, 1122, 300, 1138), "Text"), ("Buy 4 MNQZ6 MARKET", (1325, 920, 1618, 978), "Button")]
    _m1 = order_bot.tv_meldung_preise(_ME, "MNQZ6", "buy", 4)
    _m2 = order_bot.tv_meldung_preise(_ME, "MNQZ6", "buy", 4, vorher=["Buy 4 at 30,838.00"])   # alte Meldung zaehlt nie
    _m3 = order_bot.tv_meldung_preise([("Take Profit order placed on MNQZ6 · Sell 2 at 30,858.25", (130, 1100, 520, 1118), "Text")], "MNQZ6", "buy", 2)
    _m4 = order_bot.tv_meldung_preise([("Market order executed on NQZ6 · Sell 1 at 30.838,50", (130, 1100, 520, 1118), "Text")], "NQZ6", "sell", 1)
    _m5 = order_bot.tv_meldung_preise(_ME, "MNQZ6", "buy", 3)            # falsche Menge -> nichts
    _m6 = order_bot.tv_meldung_preise(_ME, "ESZ6", "buy", 4)             # Symbol-Chip MNQZ6 neben dem Titel, Plan ES -> fremd, nichts
    _m7 = order_bot.tv_meldung_preise([("Stop Loss order placed on", (130, 1100, 330, 1118), "Text"), ("Sell 4 at 30,700.00", (130, 1122, 300, 1138), "Text")], "MNQZ6", "buy", 4)
    _m8 = order_bot.tv_meldung_preise([("Sell 4 at 30,872.75", (130, 1122, 300, 1138), "Text"), ("Buy 4 at 30,838.00", (130, 1062, 300, 1078), "Text")], "MNQZ6", "buy", 4)
    chk("TV-ORDER Fill aus der Meldung: executed + Plan-Seite = Fill, TP-Order-Preis der Gegenseite, alte/fremde Menge nie, SL nie als TP",
        _m1["fill"] == 30838.0 and _m1["tp"] == 30872.75 and _m1["sl"] is None
        and _m2["fill"] is None and _m2["tp"] == 30872.75
        and _m3["fill"] is None and _m3["tp"] == 30858.25
        and _m4["fill"] == 30838.5 and _m4["tp"] is None
        and _m5["fill"] is None and _m5["tp"] is None
        and _m6["fill"] is None and _m6["tp"] is None
        and _m7["tp"] is None and _m7["sl"] == 30700.0 and _m7["fill"] is None
        and _m8["fill"] == 30838.0 and _m8["tp"] == 30872.75
        and order_bot.tv_meldung_art("Take Profit order filled on MNQZ6") == "tp" and order_bot.tv_meldung_art("Market order executed on") == "fill"
        and "Text:Buy 4 at 30,838.00" in order_bot.tv_meldung_zone(_ME))
    # Finn 28.09.2026: „Market order filled" + Bracket-Modification, DE-Format, deutsche Woerter; Rohtexte immer
    _MD = [("Market order filled", (130, 1040, 330, 1058), "Text"), ("Buy 1 at 30,816.25", (130, 1062, 300, 1078), "Text"),
           ("Limit order modified", (130, 1100, 330, 1118), "Text"), ("Sell 1 at 30,822.00", (130, 1122, 300, 1138), "Text"),
           ("Take profit, $", (1325, 500, 1420, 518), "Text"), ("Sell 1 at 30,999.00", (1325, 522, 1480, 538), "Text")]
    _d1 = order_bot.tv_meldung_preise(_MD, "MNQZ6", "buy", 1)
    _d2 = order_bot.tv_meldung_preise([("Marktorder ausgeführt", (130, 1040, 330, 1058), "Text"), ("Kaufen 1 zu 30.816,25", (130, 1062, 300, 1078), "Text")], "MNQZ6", "buy", 1)
    _r1 = order_bot.tv_meldung_roh(_MD + [("Chart", (0, 0, 50, 20), "Text")], vorher=["Chart"])
    chk("TV-ORDER Meldung: 'Market order filled' = Fill, 'Limit order modified' = TP (tv_limit), DE-Format/deutsch, Panel-Label nie, Rohtexte",
        _d1["fill"] == 30816.25 and _d1["tp"] == 30822.0
        and _d2["fill"] == 30816.25
        and order_bot.tv_meldung_art("Take profit, $") is None and order_bot.tv_meldung_art("Limit order filled on MNQZ6") == "tp"
        and "Text:Market order filled" in _r1 and "Text:Sell 1 at 30,822.00" in _r1 and not any("Chart" in x for x in _r1))
    # Finns Screenshots 28.09.2026 00:34 (PC von ID C): drei gestapelte Meldungen, sichtbar nur eine + 'Show more' (Zaehler 3)
    _ST = [("Market order placed on", (40, 900, 240, 918), "Text"), ("MNQZ6", (245, 900, 300, 918), "Button"), ("Buy 1", (40, 922, 90, 938), "Text"),
           ("Market order executed on", (40, 960, 250, 978), "Text"), ("MNQZ6", (255, 960, 310, 978), "Button"), ("Buy 1 at 30,807.25", (40, 982, 200, 998), "Text"),
           ("Take Profit order placed on", (40, 1020, 260, 1038), "Text"), ("MNQZ6", (265, 1020, 320, 1038), "Button"), ("Sell 1 at 30,812.75", (40, 1042, 200, 1058), "Text")]
    _s1 = order_bot.tv_meldung_preise(_ST, "MNQZ6", "buy", 1)
    _k1 = order_bot.tv_show_more_knopf([("Take Profit order placed on", (40, 1020, 260, 1038), "Text"), ("Show more", (40, 1070, 140, 1090), "Button"),
                                        ("Show more", (1500, 300, 1580, 320), "Button")])
    chk("TV-ORDER Stapel: executed = Fill 30807.25, TP-Limit 30812.75, 'Buy 1' ohne Preis nie; 'Show more' nur am Stapel, 'Show less' nie, fremdes nie",
        _s1["fill"] == 30807.25 and _s1["tp"] == 30812.75
        and order_bot.tv_meldung_preise(_ST, "ESZ6", "buy", 1)["fill"] is None   # Chip MNQZ6 neben dem Titel, Plan ES -> fremd
        and _k1 == {"punkt": (90, 1080), "text": "Show more"}
        and order_bot.tv_show_more_knopf([("Take Profit order placed on", (40, 1020, 260, 1038), "Text"), ("Show less 3", (40, 1070, 140, 1090), "Button")]) is None
        and order_bot.tv_show_more_knopf([("Show more", (1500, 300, 1580, 320), "Button")]) is None)
    # LIVE-BEFUND ID F … (23:07 UTC): 'Show more' geklickt, Stapel blieb zu — Aufklappen muss bewiesen werden
    _zu = [("Market order executed on", (40, 1020, 260, 1038), "Text"), ("Sell 4", (40, 1042, 85, 1058), "Text"),
           ("at 30,794.75", (90, 1042, 190, 1058), "Text"), ("Show more", (420, 936, 515, 956), "Button")]
    _auf = _zu[:3] + [("Take Profit order placed on", (40, 960, 260, 978), "Text"), ("Buy 4", (40, 982, 85, 998), "Text"),
                      ("at 30,760.75", (90, 982, 190, 998), "Text"), ("Show less", (420, 900, 515, 920), "Button")]
    chk("TV-ORDER Stapel offen/zu beweisen (ID F 23:07: Klick traf, Stapel blieb zu)",
        not order_bot.tv_stapel_offen(_zu) and order_bot.tv_stapel_offen(_auf)
        and order_bot.tv_stapel_offen(_zu[:3] + [("Take Profit order placed on", (40, 960, 260, 978), "Text")])
        and order_bot.tv_meldung_preise(_auf, "MNQZ6", "sell", 4)["tp"] == 30760.75)
    # LIVE-BEFUND .726 (Plan …, PC von ID C): ["TabItem:Positions 1", "TabItem:Orders 1", "Text:Market order executed on", "Text:Buy 1",
    # "Text:at 30,801.00"] — Seite+Menge und Preis in ZWEI Knoten; 'Show more' rechts UEBER dem Toast (Button mit Text-Kind, Zaehler 3)
    _LV = [("Positions 1", (60, 1200, 150, 1220), "TabItem"), ("Orders 1", (160, 1200, 240, 1220), "TabItem"),
           ("Market order executed on", (40, 1020, 250, 1038), "Text"), ("MNQZ6", (255, 1020, 310, 1038), "Button"),
           ("Buy 1", (40, 1042, 85, 1058), "Text"), ("at 30,801.00", (90, 1042, 190, 1058), "Text"),
           ("Show more", (230, 985, 330, 1005), "Button"), ("Show more", (240, 988, 310, 1002), "Text"), ("3", (335, 987, 351, 1003), "Text")]
    _l1 = order_bot.tv_meldung_preise(_LV, "MNQZ6", "buy", 1, vorher=["Positions", "Orders"])
    _l2 = order_bot.tv_meldung_preise([("Market order executed on", (40, 1020, 250, 1038), "Text"), ("Buy 1", (40, 1042, 85, 1058), "Text"),
                                       ("at 30,801.00", (40, 1062, 140, 1078), "Text")], "MNQZ6", "buy", 1)
    _l3 = order_bot.tv_meldung_preise([("Take Profit order placed on", (40, 1020, 260, 1038), "Text"), ("at 30,858.25", (40, 1042, 140, 1058), "Text")], "MNQZ6", "buy", 1)
    _l4 = order_bot.tv_meldung_preise(_LV, "MNQZ6", "buy", 1, vorher=["at 30,801.00"])   # alter Preis-Knoten zaehlt nie
    _rl = order_bot.tv_meldung_roh(_LV)
    chk("TV-ORDER Live .726: 'Buy 1' + 'at 30,801.00' getrennt -> Fill 30801, 'at' allein unter TP-Titel = TP, 'Show more' ueber dem Toast (Text-Kind), Umgebung in der Rohliste",
        _l1["fill"] == 30801.0 and _l2["fill"] == 30801.0 and _l3["tp"] == 30858.25 and _l3["fill"] is None and _l4["fill"] is None
        and order_bot.tv_show_more_knopf(_LV) == {"punkt": (275, 995), "text": "Show more"}
        and any(x.startswith("UMGEBUNG: ") and "Button:Show more" in x for x in _rl))
    # DEUTSCHES TRADINGVIEW (29.09.2026, ID F pc-bbbbbb, Plan …, Rohtext aus hedge.tv_meldung_roh): 'Take-Profit-Order platziert für'
    # + 'zu 30.564,75 kaufen' (Preis VOR dem Verb, deutsches Zahlenformat); Fill vermutlich 'Marktorder ausgeführt für' + '4 zu 30.600,50 verkaufen'
    _DE = [("Positionen 1", (60, 1200, 170, 1220), "TabItem"), ("Orders 1", (180, 1200, 260, 1220), "TabItem"),
           ("Take-Profit-Order platziert für", (40, 1020, 280, 1038), "Text"), ("zu 30.564,75 kaufen", (40, 1042, 200, 1058), "Text")]
    _DEF = [("Marktorder ausgeführt für", (40, 960, 250, 978), "Text"), ("4 zu 30.600,50 verkaufen", (40, 982, 230, 998), "Text")] + _DE
    _g1 = order_bot.tv_meldung_preise(_DE, "MNQZ6", "sell", 4, vorher=["Positionen 1", "Orders 1"])
    _g2 = order_bot.tv_meldung_preise(_DEF, "MNQZ6", "sell", 4)
    _g3 = order_bot.tv_meldung_preise(_DEF, "MNQZ6", "sell", 3)                       # falsche Menge am Fill -> kein Fill, TP (ohne Menge) bleibt
    _g4 = order_bot.tv_meldung_preise([("Take-Profit-Order platziert für MNQZ6 · 2 zu 30.858,25 verkaufen", (40, 1020, 480, 1038), "Text")], "MNQZ6", "buy", 2)
    _g5 = order_bot.tv_meldung_preise(_DE, "MNQZ6", "sell", 4, vorher=["zu 30.564,75 kaufen"])   # alte Preis-Zeile zaehlt nie
    chk("TV-ORDER Deutsch: 'zu 30.564,75 kaufen' unter TP-Titel = TP, '4 zu 30.600,50 verkaufen' unter 'Marktorder ausgeführt' = Fill, Menge geprueft, alte Zeile zaehlt nie",
        _g1["tp"] == 30564.75 and _g1["fill"] is None and _g2["fill"] == 30600.5 and _g2["tp"] == 30564.75
        and _g3["fill"] is None and _g3["tp"] == 30564.75 and _g4["tp"] == 30858.25 and _g5["tp"] is None
        and order_bot.tv_meldung_preise(_LV, "MNQZ6", "buy", 1, vorher=["Positions", "Orders"])["fill"] == 30801.0)   # englisch unveraendert
    # Neuheit (29.09.2026, …): gleicher Titel stand schon vorher da -> neu nur ueber Anzahl oder neue Preis-Zeile
    _alt = [("Take-Profit-Order platziert für", (40, 1020, 280, 1038), "Text"), ("zu 30.500,00 kaufen", (40, 1042, 200, 1058), "Text")]
    _nv = {str(e[0]).strip() for e in _alt}
    _zv = order_bot.tv_meldung_zaehlen(_alt, "MNQZ6")
    _jetzt_preis = [("Take-Profit-Order platziert für", (40, 1020, 280, 1038), "Text"), ("zu 30.564,75 kaufen", (40, 1042, 200, 1058), "Text")]
    _jetzt_zwei = _alt + [("Take-Profit-Order platziert für", (40, 960, 280, 978), "Text")]
    chk("TV-ORDER neue Meldung trotz gleichem Titel: neue Preis-Zeile oder mehr gleiche Titel = neu; unveraendert = nichts; neuer Titel wie bisher",
        order_bot.tv_meldungen_neu(_alt, "MNQZ6", _nv, _zv) == []
        and order_bot.tv_meldungen_neu(_jetzt_preis, "MNQZ6", _nv, _zv) == ["Take-Profit-Order platziert für · zu 30.564,75 kaufen"]
        and order_bot.tv_meldungen_neu(_jetzt_zwei, "MNQZ6", _nv, _zv) == ["Take-Profit-Order platziert für"]
        and order_bot.tv_meldungen_neu([("Market order executed on", (40, 1020, 250, 1038), "Text")], "MNQZ6", {"Positions"}, {}) == ["Market order executed on"]
        and order_bot.tv_meldungen_neu([("Jahr zu Tag in 1-tägige Intervalle", (40, 1020, 250, 1038), "Button")], "MNQZ6", set(), {}) == [])
    chk("TV-ORDER Orders-Reiter Rohzone fuer puls_diagnose: Knoten bis 260 px unter dem Reiter, Typ:Name@x,y",
        order_bot.tv_orders_roh_zone([("Orders 1", (180, 700, 260, 720), "TabItem"), ("Säulen-Einstellung", (200, 740, 300, 760), "Button"),
                                      ("Symbol", (40, 745, 90, 760), "HeaderItem"), ("weit weg", (40, 1100, 90, 1120), "Text")])
        == ["TabItem:Orders 1@180,700", "Button:Säulen-Einstellung@200,740", "HeaderItem:Symbol@40,745"])
    # Leerzeit Konto-Lesen (22.09.2026): ein sichtbar FREMDES Konto beendet die Leseschleife.
    chk("TV-KONTO: fremdes Konto erkannt — kontoartig (Buchstaben + Ziffern, ' USD'), nie eine erwartete ID, nie reine Ziffern",
        order_bot.tv_fremdes_konto(["30,849.00", "4000000", "APEX0000000000025 USD"], ["TDFYSL150310000001", "TDFYSL150310000000"]) == "APEX0000000000025 USD"
        and order_bot.tv_fremdes_konto(["APEX0000000000025 USD"], ["APEX0000000000025"]) == ""
        and order_bot.tv_fremdes_konto(["PAAPEX0000000000031"], ["APEX0000000000031"]) == ""      # Geschwister-aehnlich: kein Urteil
        and order_bot.tv_fremdes_konto(["4000000", "Sell 2 at 30,858.25"], ["APEX1"]) == ""
        and order_bot.tv_fremdes_konto(None, ["APEX1"]) == "")
    chk("TV-TAB: Chromes 'Website verlassen?' — 'Verlassen'/'Leave' wird gefunden, 'Abbrechen' nie, Unsichtbares nie",
        order_bot.tv_verlassen_knopf([("Abbrechen", (1113, 288, 1211, 322), "Button"), ("Verlassen", (1003, 288, 1101, 322), "Button")])["punkt"] == (1052, 305)
        and order_bot.tv_verlassen_knopf([("Leave", (10, 10, 60, 30), "Button")])["text"] == "Leave"
        and order_bot.tv_verlassen_knopf([("Abbrechen", (1113, 288, 1211, 322), "Button"), ("Verlassen", None, "Button")]) is None
        and order_bot.tv_verlassen_knopf([]) is None)
    chk("TV-TAB: Chart-Titel OHNE Pfeil (genau 0 %) wird erkannt — nie Prophos/DevTools/Kurse ohne Symbol",
        order_bot.tv_tab_rang("NQZ2026 30,784.50 0% Unnamed - Google Chrome", "", "") == 1
        and order_bot.tv_tab_rang("(2) MNQZ2026 30,849.00 ▲ +0.21% Unnamed", "", "") == 1
        and order_bot.tv_tab_rang("BTC1! 86,680 −0.1% Unnamed", "", "") == 1
        and order_bot.tv_tab_rang("NQZ2026 30,784.50 0% Unnamed", "", "NQZ6") == 3
        and order_bot.tv_tab_rang("Prophos - Google Chrome", "", "") == 0
        and order_bot.tv_tab_rang("DevTools - NQZ2026 30,784.50 0%", "", "") == 0
        and order_bot.tv_tab_rang("30,784.50 0% Unnamed", "", "") == 0)
    # Tradovate-Panel hoch/runter (22.09.2026, Finns PC): Kandidaten fuer den ⤢-Knopf
    _FR = (0, 107, 2000, 1190)
    _PK = [("Tradovate", (100, 1122, 170, 1140), "Button"), ("Account Balance", (1016, 1165, 1116, 1183), "Text"),
           ("Equity", (1478, 1165, 1518, 1183), "Text"), ("Profit", (1585, 1165, 1620, 1183), "Text"), ("Symbol", (1656, 297, 1700, 315), "Text")]
    _KN = [("", (1570, 1122, 1586, 1140)), ("", (1608, 1122, 1624, 1140)), ("", (170, 1122, 190, 1140)), ("Publish", (1930, 208, 1990, 228))]
    _LG = order_bot.tv_panel_lage(_PK, _KN, _FR)
    chk("TV-PANEL: Lage 'unten' erkannt; Kandidaten = unbenannte Knoepfe der Tradovate-Zeile von rechts, dann Raster ab 6 px links der 'Profit'-Kante; nie 'Publish'",
        _LG["zustand"] == "unten" and _LG["kopf_y"] == 1174 and _LG["rechts"] == 1620 and _LG["zeile_y"] == 1131
        and _LG["kandidaten"][0] == (1613, 1131, "ueber dem i von 'Profit' (-43)") and _LG["kandidaten"][1][:2] == (1613, 1137)
        and any(k[2] == "unbenannter Knopf der Panelzeile" for k in _LG["kandidaten"]) and all(1100 <= k[1] <= 1150 for k in _LG["kandidaten"])
        and not any(k[0] > 1620 for k in _LG["kandidaten"]))
    chk("TV-PANEL: 'ueber Profit' ist immer der erste Kandidat (ein benannter Knopf an derselben Stelle faellt als Doppel weg); ohne Kopfzeile Rueckfall auf Watchlist-Spalte",
        order_bot.tv_panel_lage(_PK + [("Maximize panel", (1608, 1122, 1624, 1140), "Button")], None, _FR)["kandidaten"][0][:2] == (1613, 1131)
        and order_bot.tv_panel_lage(_PK, None, _FR)["kandidaten"][0][:2] == (1613, 1131)
        and order_bot.tv_panel_lage([("Symbol", (1656, 297, 1700, 315), "Text")], None, _FR)["rechts"] == 1620)
    chk("TV-PANEL: Lage 'oben' (Panel maximiert: Kopfzeile im oberen Drittel); ohne Kopfzeile None",
        order_bot.tv_panel_lage([("Tradovate", (100, 208, 170, 226), "Button"), ("Account Balance", (1345, 252, 1445, 270), "Text"), ("Profit", (1585, 252, 1620, 270), "Text")], None, _FR)["zustand"] == "oben"
        and order_bot.tv_panel_lage([("Symbol", (1656, 297, 1700, 315), "Text")], None, _FR)["zustand"] is None
        and order_bot.tv_panel_lage(_PK, _KN, None)["zustand"] is None)
    # Klickpunkt am Fensterrand (22.09.2026 12:33, Finns PC): Umschalter ragt unter den Rand
    chk("TV-UIA: Klickpunkt bleibt 12 px ueber dem Fensterboden, wenn das Element darunter hinausragt",
        order_bot.tv_uia_filtern([("FNFTCHVORNAMENACHNAM00000 USD", (80, 1165, 330, 1200))], ["FNFTCHVORNAMENACHNAM00000"], (0, 0, 2000, 1186))[0]["punkt"] == (205, 1174)
        and order_bot.tv_uia_filtern([("FNFTCHVORNAMENACHNAM00000 USD", (80, 900, 330, 930))], ["FNFTCHVORNAMENACHNAM00000"], (0, 0, 2000, 1186))[0]["punkt"] == (205, 915))
    chk("TV-ORDER: Knopf-Beweis versteht 'MKT' wie 'MARKET' — und verwechselt Sell nie mit Buy",
        order_bot.tv_senden_text_passt("Sell 1 MNQZ6 MKT", "sell", 1)[0]
        and order_bot.tv_senden_text_passt("Buy 2 MNQZ6 MARKET", "buy", 2)[0]
        and not order_bot.tv_senden_text_passt("Sell 1 MNQZ6 MKT", "buy", 1)[0]
        and not order_bot.tv_senden_text_passt("Buy 1 BTCU6 @ 86,740 LIMIT", "buy", 1)[0]
        and not order_bot.tv_senden_text_passt("Buy 2 MNQZ6 MARKET", "buy", 1)[0])

    # ── Orbit-Puls Schritt 2 (30.08.2026): Order auf TradingView platzieren ──
    # Der Puls klickt hier nach Koordinaten, die eine Webseite meldet — jede
    # dieser Rechnungen kann still danebenliegen, deshalb stehen sie alle hier.
    chk("TV: Symbol-Wurzel — Dauerkontrakt, Monatskontrakt, Boerse, blanke Wurzel",
        order_bot.tv_symbol_root("MNQ1!") == "MNQ"
        and order_bot.tv_symbol_root("CME_MINI:MNQ1!") == "MNQ"
        and order_bot.tv_symbol_root("MNQZ2025") == "MNQ"
        and order_bot.tv_symbol_root("NQZ2026") == "NQ"
        and order_bot.tv_symbol_root("MNQ") == "MNQ"
        and order_bot.tv_symbol_root("MNQ1! 1m CME") == "MNQ"
        and order_bot.tv_symbol_root("") == "")
    # Die Falle, an der eine naive Monatsregel scheitert: in 'MNQ1!' sieht 'Q1'
    # aus wie Monat+Jahr — uebrig bliebe 'MN', und der Vergleich waere still
    # falsch statt laut.
    chk("TV: MNQ und NQ sind NIE dasselbe Instrument",
        order_bot.tv_symbol_passt("MNQ1!", "MNQ")
        and order_bot.tv_symbol_passt("MNQZ2025", "MNQ")
        and not order_bot.tv_symbol_passt("MNQ1!", "NQ")
        and not order_bot.tv_symbol_passt("NQZ2026", "MNQ")
        and not order_bot.tv_symbol_passt("", "MNQ"))
    # Tab-Suchbegriff (30.08.2026, Finns erster Live-Lauf): der Bot suchte den
    # Tab am Wort 'tradingview' und fand nichts — bei ihm heisst der Tab
    # 'NQU2026 29.491,75 ▼ −0,69 %'. Jetzt meldet die Seite ihren Titel selbst.
    chk("TV: Tab-Suchbegriff ist das Symbol, nicht der tickende Preis",
        order_bot.tv_tab_suchbegriff("NQU2026 29.491,75 ▼ −0,69 %") == "NQU2026"
        and order_bot.tv_tab_suchbegriff("MNQ1! 1m CME — TradingView") == "MNQ1!"
        and order_bot.tv_tab_suchbegriff("TradingView — Track All Markets") == "TradingView")
    chk("TV: Zaehler-Praefixe und Leeres ergeben KEINEN Suchbegriff",
        order_bot.tv_tab_suchbegriff("(1) NQU2026 29.491,75") == "NQU2026"
        and order_bot.tv_tab_suchbegriff("") == ""
        and order_bot.tv_tab_suchbegriff(None) == ""
        and order_bot.tv_tab_suchbegriff("(3) 7 %") == "")
    # Tab-Treffer (30.08.2026, Finns Fehlversuch MIT voller Spur): sein Tab
    # heisst 'NQU2026 29,491.75 ▼ −0.69% Unnamed' — kein 'tradingview' drin.
    # Der dritte Weg (Symbol-Wurzel aus dem Befehl) braucht weder Userscript
    # noch Titel und muss genau diesen Namen treffen.
    chk("TV: Tab per Symbol-Wurzel getroffen (NQU6 findet NQU2026-Tab)",
        order_bot.tv_tab_passt("NQU2026 29,491.75 ▼ −0.69% Unnamed", "", "NQU6")
        and order_bot.tv_tab_passt("MNQU2026 29,491.75", "", "MNQ")
        and order_bot.tv_tab_passt("MNQ1! 1m CME — TradingView", "", "")
        and order_bot.tv_tab_passt("NQU2026 …", "NQU2026", ""))
    chk("TV: fremde Tabs sind NIE der TradingView-Tab",
        not order_bot.tv_tab_passt("Prophos\xa0- Arbeitsspeichernutzung\xa0- 303 MB", "", "NQU6")
        and not order_bot.tv_tab_passt("Echo-Panel – Speicherauslastung – 37,3 MB", "", "NQU6")
        and not order_bot.tv_tab_passt("127.0.0.1:8770/api/instances", "", "NQU6")
        and not order_bot.tv_tab_passt("DevTools - www.tradingview.com/chart", "", "NQU6")
        and not order_bot.tv_tab_passt("", "", "NQU6"))
    # MNQ-Plan darf NIE den NQ-Tab greifen (und umgekehrt) — dieselbe Trennung
    # wie beim Instrument-Vergleich, hier nur eine Ebene frueher.
    # Der Rang loest Finns zweiten Fehlversuch (31.08.2026): Plan stand auf NQ,
    # sein Chart auf MNQ -- der Tab wurde deshalb gar nicht gefunden, obwohl er
    # offen war. Den Chart umzustellen ist aber Schritt 4 der Kette, die Suche
    # darf ihn also nicht voraussetzen. Finns ECHTER Tab-Name aus der Spur:
    _FINN_TAB = "MNQU2026 29.455,50 ▼ −0.12% Unnamed\xa0– Arbeitsspeichernutzung"
    chk("TV: Chart-Tab wird auch bei ANDEREM Symbol gefunden (Pfeil + Prozent)",
        order_bot.tv_tab_rang(_FINN_TAB, "", "NQU6") == 1
        and order_bot.tv_tab_rang(_FINN_TAB, "", "MNQ") == 3)
    chk("TV: passendes Symbol schlaegt blossen Chart-Titel (Rang 3 > 1)",
        order_bot.tv_tab_rang("NQU2026 29.491,75 ▼ −0,69%", "", "NQU6") == 3
        and order_bot.tv_tab_rang("MNQU2026 29.455,50 ▼ −0.12%", "", "NQU6") == 1
        and order_bot.tv_tab_rang("MNQ1! — TradingView", "", "NQU6") == 2)
    chk("TV: gewoehnliche Tabs bleiben bei Rang 0",
        order_bot.tv_tab_rang("Prophos\xa0– Arbeitsspeichernutzung\xa0– 149 MB", "", "NQU6") == 0
        and order_bot.tv_tab_rang("Cockpit | Duplikium Trade Copier", "", "NQU6") == 0
        and order_bot.tv_tab_rang("Tradeify Futures - User Dashboard", "", "NQU6") == 0
        and order_bot.tv_tab_rang("FundedNext - Prop Trading Firm for CFDs and Futures", "", "NQU6") == 0
        and order_bot.tv_tab_rang("DevTools - www.tradingview.com/chart", "", "NQU6") == 0
        and order_bot.tv_tab_rang("DAX -0,87%", "", "NQU6") == 0)
    chk("TV: MNQ und NQ greifen sich beim SYMBOL-Rang nicht gegenseitig",
        order_bot.tv_tab_rang("NQU2026 29,491.75", "", "MNQ") == 0
        and order_bot.tv_tab_rang("MNQU2026 29,491.75", "", "NQU6") == 0)
    # Senden-Knopf-Text (31.08.2026, aus Finns Panel-Dump): TradingView
    # beschriftet den Knopf mit "Kauf 3 NQU6 MARKT" -- Richtung, Menge, Symbol
    # und Orderart in einem String. Das ist die letzte Probe vor dem
    # unumkehrbaren Klick, also gehoert jeder Fall hier her.
    chk("TV: Senden-Knopf bestaetigt die geplante Order (de + en)",
        order_bot.tv_senden_text_passt("Kauf 3 NQU6 MARKT", "buy", 3)[0]
        and order_bot.tv_senden_text_passt("Verkauf 3 NQU6 MARKT", "sell", 3)[0]
        and order_bot.tv_senden_text_passt("Buy 3 NQU6 MARKET", "buy", 3)[0]
        and order_bot.tv_senden_text_passt("Sell 2 MNQU6 MARKET", "sell", 2)[0])
    # 'Verkauf' ENTHAELT 'kauf' — wer darauf nicht achtet, haelt einen Verkauf
    # fuer einen Kauf. Das ist die Richtungsverwechslung, gegen die der ganze
    # Rest der Kette abgesichert ist.
    chk("TV: Richtungsverwechslung wird erkannt (Verkauf enthaelt 'kauf')",
        not order_bot.tv_senden_text_passt("Verkauf 3 NQU6 MARKT", "buy", 3)[0]
        and not order_bot.tv_senden_text_passt("Kauf 3 NQU6 MARKT", "sell", 3)[0])
    chk("TV: falsche Menge und falsche Orderart stoppen den Klick",
        not order_bot.tv_senden_text_passt("Kauf 30 NQU6 MARKT", "buy", 3)[0]
        and not order_bot.tv_senden_text_passt("Kauf 3 NQU6 LIMIT", "buy", 3)[0]
        and not order_bot.tv_senden_text_passt("", "buy", 3)[0])
    chk("TV: Konto per External ID — Beiwerk egal, Trennzeichen egal",
        order_bot.tv_konto_passt("PA-1234567 · Tradeify · $50k", "PA1234567")
        and order_bot.tv_konto_passt("APEX-987654", "apex 987654")
        and not order_bot.tv_konto_passt("PA-1234567", "PA-7654321"))
    chk("TV: zu kurze External ID trifft NIE ein Konto (Fehlgriff = falsches Konto)",
        not order_bot.tv_konto_passt("PA-12", "12")
        and not order_bot.tv_konto_passt("PA-1234567", "")
        and not order_bot.tv_konto_passt("PA-1234567", None))
    chk("TV: deutsche Zahlen aus der Oberflaeche, Leeres bleibt None",
        order_bot.tv_de_zahl("1.234,5") == 1234.5
        and order_bot.tv_de_zahl("2") == 2.0
        and order_bot.tv_de_zahl("-3") == -3.0
        and order_bot.tv_de_zahl("") is None
        and order_bot.tv_de_zahl("-") is None
        and order_bot.tv_de_zahl(None) is None)
    _POS = [{"symbol": "MNQZ2025", "seite": "Long",  "menge": "2"},
            {"symbol": "MNQH2026", "seite": "Long",  "menge": "1"},
            {"symbol": "MNQZ2025", "seite": "Short", "menge": "5"},
            {"symbol": "NQZ2025",  "seite": "Long",  "menge": "9"}]
    chk("TV: Mengen-Summe zaehlt nur gleiche Wurzel UND gleiche Richtung",
        order_bot.tv_menge_summe(_POS, "MNQ", "buy") == 3.0
        and order_bot.tv_menge_summe(_POS, "MNQ", "sell") == 5.0
        and order_bot.tv_menge_summe(_POS, "NQ", "buy") == 9.0
        and order_bot.tv_menge_summe([], "MNQ", "buy") == 0.0)
    # Koordinaten: dpr traegt Windows-Skalierung UND Seiten-Zoom, die
    # Browser-Dekoration sitzt oben, der Viewport klebt links am Klientrand.
    _P, _G = order_bot.tv_bildschirm_punkt(
        [100, 50, 40, 20],
        {"dpr": 1, "innerWidth": 1920, "innerHeight": 900}, (0, 100, 1920, 980))
    chk("TV: CSS-Punkt -> Bildschirm (100 % Skalierung, 80 px Browser-Kopf)", _P == (120, 240))
    _P, _G = order_bot.tv_bildschirm_punkt(
        [100, 50, 40, 20],
        {"dpr": 1.5, "innerWidth": 1920, "innerHeight": 900}, (0, 0, 2880, 1500))
    chk("TV: CSS-Punkt -> Bildschirm (150 % Skalierung)", _P == (180, 240))
    # Der Breiten-Abgleich ist der Riegel gegen den lautlosen Fehlklick: passt
    # innerWidth*dpr nicht zur gemessenen Klientbreite, stimmt eine Annahme
    # nicht (DevTools seitlich, falsches Fenster, Prozess nicht DPI-bewusst).
    _P, _G = order_bot.tv_bildschirm_punkt(
        [100, 50, 40, 20],
        {"dpr": 1, "innerWidth": 1920, "innerHeight": 900}, (0, 0, 1000, 980))
    chk("TV: Breiten-Abgleich schlaegt fehl -> KEIN Klick, mit Begruendung",
        _P is None and "Breiten" in _G)
    _P, _G = order_bot.tv_bildschirm_punkt(
        [100, 50, 40, 20],
        {"dpr": 1, "innerWidth": 1920, "innerHeight": 900}, (0, 0, 1920, 1500))
    chk("TV: unplausible Browser-Dekoration -> KEIN Klick", _P is None and "Dekoration" in _G)
    _P, _G = order_bot.tv_bildschirm_punkt(
        [5000, 50, 40, 20],
        {"dpr": 1, "innerWidth": 1920, "innerHeight": 900}, (0, 0, 1920, 980))
    chk("TV: Ziel ausserhalb des Fensters -> KEIN Klick", _P is None)
    chk("TV: TP/SL-Einheit muss Geld sein — Ticks/Prozent zaehlen NIE",
        order_bot.tv_einheit_ist_geld("$")
        and order_bot.tv_einheit_ist_geld("USD")
        and order_bot.tv_einheit_ist_geld("Geld")
        and not order_bot.tv_einheit_ist_geld("Ticks")
        and not order_bot.tv_einheit_ist_geld("%")
        and not order_bot.tv_einheit_ist_geld(""))
    chk("TV: Zahlen deutsch schreiben — ganze Kontrakte ohne Nachkomma",
        order_bot.tv_zahl_text(2) == "2"
        and order_bot.tv_zahl_text(2.0) == "2"
        and order_bot.tv_zahl_text(300) == "300"
        and order_bot.tv_zahl_text(2.5) == "2,5")
    chk("TV: gueltiger Orbit-Befehl (mit und ohne SL/TP)",
        order_bot.pruefe_tv_befehl({"ext_id": "PA-1234567", "symbol": "MNQ",
                                    "richtung": "buy", "volumen": 2,
                                    "sl_usd": 100, "tp_usd": 300}) == []
        and order_bot.pruefe_tv_befehl({"ext_id": "PA-1234567", "symbol": "MNQ",
                                        "richtung": "sell", "volumen": 1}) == [])
    chk("TV: fehlende/zu kurze External ID wird gemeldet",
        len(order_bot.pruefe_tv_befehl({"symbol": "MNQ", "richtung": "buy", "volumen": 1})) == 1
        and len(order_bot.pruefe_tv_befehl({"ext_id": "12", "symbol": "MNQ",
                                            "richtung": "buy", "volumen": 1})) == 1)
    chk("TV: halbe Absicherung (nur SL oder nur TP) wird abgelehnt",
        len(order_bot.pruefe_tv_befehl({"ext_id": "PA-1234567", "symbol": "MNQ",
                                        "richtung": "buy", "volumen": 1,
                                        "sl_usd": 100})) == 1)
    chk("TV: Bruchteil-Kontrakte und 0/negativ werden abgelehnt",
        len(order_bot.pruefe_tv_befehl({"ext_id": "PA-1234567", "symbol": "MNQ",
                                        "richtung": "buy", "volumen": 1.5})) == 1
        and len(order_bot.pruefe_tv_befehl({"ext_id": "PA-1234567", "symbol": "MNQ",
                                            "richtung": "kauf", "volumen": 0})) == 2)
    # Remote-Close (28.08.2026): der Menuepunkt, der frueher der verbotene war —
    # jetzt Ziel, darum Praefix-Match und harter Alle-/Massen-Ausschluss.
    chk("CLOSE: Menuepunkt 'Position schließen'/'Close position' erkannt (de/en/ss)",
        order_bot.ist_close_menuepunkt("Position schließen")
        and order_bot.ist_close_menuepunkt("Position schliessen")
        and order_bot.ist_close_menuepunkt("Close position"))
    chk("CLOSE: Alle-/Massen-/Ändern-Punkte sind NIE Treffer",
        not order_bot.ist_close_menuepunkt("Alle Positionen schließen")
        and not order_bot.ist_close_menuepunkt("Close all positions")
        and not order_bot.ist_close_menuepunkt("Massenoperationen")
        and not order_bot.ist_close_menuepunkt("Ändern oder löschen")
        and not order_bot.ist_close_menuepunkt("Neue Order")
        and not order_bot.ist_close_menuepunkt(""))
    chk("CLOSE: Schliessen-Knopf nur mit EIGENEM Ticket, Ändern/Abbrechen nie",
        order_bot.ist_schliessen_knopf("Schließen #596061571 buy 1.20 NAS100 zum Marktpreis", 596061571)
        and order_bot.ist_schliessen_knopf("Close #596061571 buy 1.20 NAS100 by Market", 596061571)
        and not order_bot.ist_schliessen_knopf("Schließen #596061571 buy 1.20 NAS100", 111222333)
        and not order_bot.ist_schliessen_knopf("Ändern #596061571 buy 1 NAS100 sl: 29349.04 tp: 29570.71", 596061571)
        and not order_bot.ist_schliessen_knopf("Abbrechen", 596061571)
        and not order_bot.ist_schliessen_knopf("", 596061571))
    # Ein-Klick-Haftungsausschluss (01.09.2026): der EINE fremde Dialog, den
    # der Bot bestaetigen darf — entsprechend eng muss die Signatur sein.
    chk("CLOSE: Zustimmen-Knopf des Ein-Klick-Haftungsausschlusses erkannt (de/en)",
        order_bot.ist_einklick_akzeptieren_knopf("Ich akzeptiere die allgemeinen Geschäftsbedingungen")
        and order_bot.ist_einklick_akzeptieren_knopf("Ich akzeptiere die allgemeinen Geschaeftsbedingungen")
        and order_bot.ist_einklick_akzeptieren_knopf("I accept the terms and conditions")
        and order_bot.ist_einklick_akzeptieren_knopf("I agree to the Terms and Conditions"))
    chk("CLOSE: Abbrechen/Ablehnen und halbe Treffer sind NIE Zustimmung",
        not order_bot.ist_einklick_akzeptieren_knopf("Abbrechen")
        and not order_bot.ist_einklick_akzeptieren_knopf("Cancel")
        and not order_bot.ist_einklick_akzeptieren_knopf("Ich akzeptiere die Bedingungen NICHT")
        and not order_bot.ist_einklick_akzeptieren_knopf("I do not accept the terms")
        and not order_bot.ist_einklick_akzeptieren_knopf("Akzeptieren")
        and not order_bot.ist_einklick_akzeptieren_knopf("Geschäftsbedingungen")
        and not order_bot.ist_einklick_akzeptieren_knopf("Schließen #596061571 buy 1.20 NAS100 zum Marktpreis")
        and not order_bot.ist_einklick_akzeptieren_knopf(""))
    chk("CLOSE: Haftungs-Fenster am Titel erkannt, MT5-Hauptfenster nie",
        order_bot.ist_einklick_dialog("Ein-Klick-Handel")
        and order_bot.ist_einklick_dialog("One Click Trading")
        and not order_bot.ist_einklick_dialog("10000003 - FivePercentOnline-Real: Demokonto - Hedge")
        and not order_bot.ist_einklick_dialog(""))
    # Kennzeichen des Dialogs (01.09.2026, zweiter Anlauf): der Titel allein
    # war zu streng — ein Kind-Fenster ohne lesbare Beschriftung fiel still
    # durch. Jetzt zaehlt Titel ODER Fliesstext, und ein fremder Vertrag ohne
    # Ein-Klick-Kennzeichen bleibt draussen.
    class _FakeText:
        def __init__(self, text):
            self._t = text

        def window_text(self):
            return self._t

    class _FakeFenster:
        def __init__(self, titel, texte=()):
            self._titel = titel
            self._texte = [_FakeText(t) for t in texte]

        def window_text(self):
            return self._titel

        def descendants(self, control_type=None):
            return self._texte if control_type == "Text" else []

    chk("CLOSE: Ein-Klick-Kennzeichen greift ueber Titel ODER Fliesstext",
        order_bot._einklick_kennzeichen(_FakeFenster("Ein-Klick-Handel"))
        and order_bot._einklick_kennzeichen(_FakeFenster("", [
            "Haftungsausschluss",
            'Sie sind dabei das Handeln mit einem Klick ("One Click Trading") zu aktivieren.']))
        and not order_bot._einklick_kennzeichen(_FakeFenster("Vertrag", [
            "Ich bestaetige die Geschaeftsbedingungen des Brokers gelesen zu haben."]))
        and not order_bot._einklick_kennzeichen(_FakeFenster("")))
    f = order_bot.pruefe_befehl({"aktion": "close", "ticket": 596061571, "symbol": "NAS100"})
    chk("CLOSE: Befehl mit Ticket+Symbol → gueltig (ohne Richtung/Lots/SL/TP)", f == [])
    f = order_bot.pruefe_befehl({"aktion": "close", "ticket": 0, "symbol": ""})
    chk("CLOSE: Befehl ohne Ticket/Symbol → beide gemeldet", len(f) == 2)

    # ── Notfall-SL/TP (27.08.2026): reine Rechenlogik ──────────────────────
    # Wichtigster Fall zuerst: der in den GEWINN nachgezogene Master-SL — die
    # naive Formel 'Entry ± Faktor × Distanz' legte den Level dort VOR den
    # Master-SL und schloesse den Hedge, bevor der Master ausgestoppt ist.
    def sltp(mp, faktor=110, puffer=0, point=0.01, digits=2):
        return plan_sltp(mp, faktor=faktor, min_puffer_punkte=puffer,
                         point=point, digits=digits)

    # Kursabstand der Broker (01.10.2026, Finns Screenshots): The5ers SELL 24 @ 30355,08, Ask 30339,07
    # → P&L +384,24 $; Fusion 30372,06/30372,86 → Abstand +33,39
    chk("ABSTAND: The5ers SELL 24 Lot, Equity−Balance +384,24, Fusion-Mitte 30372,46 → +33,39",
        broker_abstand({"type": 1, "price_open": 30355.08, "volume": 24, "contract_size": 1}, 1, 200000.0, 200384.24, "USD", 30372.46) == 33.39)
    chk("ABSTAND: BUY 1 Lot cs 20, P&L −200 → Master 30354,6; Fusion 30360 → +5,4",
        broker_abstand({"type": 0, "price_open": 30364.6, "volume": 1, "contract_size": 20}, 1, 1000.0, 800.0, "USD", 30360.0) == 5.4)
    chk("ABSTAND: zwei Master-Positionen → Rueckfall Hedge-Entry − Master-Entry",
        broker_abstand({"type": 1, "price_open": 30355.08, "volume": 24, "contract_size": 1}, 2, 1.0, 2.0, "USD", 30372.46, 30382.61) == 27.53)
    chk("ABSTAND: EUR-Konto ohne Hedge-Entry → None (wie bisher, keine Verschiebung)",
        broker_abstand({"type": 1, "price_open": 30355.08, "volume": 24, "contract_size": 1}, 1, 1.0, 2.0, "EUR", 30372.46) is None)
    chk("ABSTAND: > 400 Pkt (falsches Symbol) → None",
        broker_abstand({"type": 0, "price_open": 28904.96, "volume": 2, "contract_size": 10}, 1, 0.0, 0.0, "USD", 30372.0) is None)
    # Ende-zu-Ende mit Finns Zahlen: verschobene Master-Level → Fusion-SL 30346,55 / -TP 30449,29
    _mp = {"type": 1, "price_open": 30355.08 + 33.39, "sl": 30410.37 + 33.39, "tp": 30316.97 + 33.39}
    chk("ABSTAND: The5ers-Trade auf Fusion → Hedge-SL 30346,55 (TP+10 % dahinter), Hedge-TP 30449,29 (SL+10 %)",
        sltp(_mp) == {"sl": 30346.55, "tp": 30449.29})
    chk("NOTFALL: LONG-Master, SL 2490/TP 2520 @ Entry 2500 → Hedge-TP 2489, Hedge-SL 2522 (gekreuzt, 10% dahinter)",
        sltp({"type": 0, "price_open": 2500.0, "sl": 2490.0, "tp": 2520.0})
        == {"tp": 2489.0, "sl": 2522.0})
    chk("NOTFALL: SHORT-Master, SL 2510/TP 2480 → Hedge-TP 2511, Hedge-SL 2478 (gespiegelt)",
        sltp({"type": 1, "price_open": 2500.0, "sl": 2510.0, "tp": 2480.0})
        == {"tp": 2511.0, "sl": 2478.0})
    chk("NOTFALL: LONG-SL in den Gewinn nachgezogen (2510 > Entry 2500) → Hedge-TP 2509 liegt DAHINTER (unter dem Master-SL)",
        sltp({"type": 0, "price_open": 2500.0, "sl": 2510.0, "tp": 0.0})
        == {"tp": 2509.0, "sl": 0.0})
    chk("NOTFALL: Breakeven-SL (Distanz 0) → Mindest-Puffer 100 Punkte greift (Hedge-TP 2499)",
        sltp({"type": 0, "price_open": 2500.0, "sl": 2500.0, "tp": 0.0}, puffer=100)
        == {"tp": 2499.0, "sl": 0.0})
    chk("NOTFALL: Mindest-Puffer schlaegt Prozent-Puffer, wenn er groesser ist (Distanz 1 → 1.0 statt 0.1)",
        sltp({"type": 0, "price_open": 2500.0, "sl": 2499.0, "tp": 0.0}, puffer=100)
        == {"tp": 2498.0, "sl": 0.0})
    chk("NOTFALL: Master ohne SL/TP (0.0) → beide Hedge-Level 0.0 (= loeschen)",
        sltp({"type": 0, "price_open": 2500.0, "sl": 0.0, "tp": 0.0})
        == {"tp": 0.0, "sl": 0.0})
    chk("NOTFALL: altes EA ohne Felder (None) → None, es wird NICHTS angefasst",
        sltp({"type": 0, "price_open": None, "sl": None, "tp": None}) is None
        and sltp({"type": 0, "price_open": 2500.0, "sl": None, "tp": None}) is None)
    chk("NOTFALL: Rundung auf Broker-Digits (2492.663 → 2492.66)",
        sltp({"type": 0, "price_open": 2500.0, "sl": 2493.33, "tp": 0.0})
        == {"tp": 2492.66, "sl": 0.0})

    # Snapshot-Parser v5: Entry/SL/TP werden gelesen, alte 6-Feld-Zeilen
    # degradieren auf None (nie 0 — 'Beweis oder leer').
    import tempfile as _tf
    with _tf.TemporaryDirectory() as _td:
        _v5 = os.path.join(_td, "v5.csv")
        with open(_v5, "w") as f:
            f.write("PROPHOS1;7;123;400001;Srv;2;1;10000.00;10000.00;USD;1\n"
                    "P;101;NAS100;0;1.00000000;1.00000000;20000.00000000;19900.00000000;20200.00000000\n"
                    "END;7;1\n")
        _alt = os.path.join(_td, "alt.csv")
        with open(_alt, "w") as f:
            f.write("PROPHOS1;3;123;400001;Srv;2;1\n"
                    "P;102;NAS100;0;1.00000000;1.00000000\n"
                    "END;3;1\n")
        s5 = read_snapshot(_v5)
        sa = read_snapshot(_alt)
        chk("SNAPSHOT v5: Entry/SL/TP aus der P-Zeile gelesen",
            s5 is not None and s5["positions"][0]["price_open"] == 20000.0
            and s5["positions"][0]["sl"] == 19900.0 and s5["positions"][0]["tp"] == 20200.0)
        chk("SNAPSHOT alt (6 Felder): price_open/sl/tp bleiben None, Rest liest normal",
            sa is not None and sa["positions"][0]["volume"] == 1.0
            and sa["positions"][0]["price_open"] is None and sa["positions"][0]["sl"] is None)

    # Notfall-Close-Klassifizierung: nur Broker-SL/TP-Fills (DEAL_REASON 4/5)
    # auf OUT-Deals zaehlen — Hand-Close (REASON_CLIENT=0) und Stop-Out
    # (REASON_SO=6) bleiben 'extern', schon verbuchte Deals nie doppelt.
    from types import SimpleNamespace as _NS
    _deals = [
        _NS(ticket=1, entry=1, reason=4),   # SL-Fill  → Notfall
        _NS(ticket=2, entry=1, reason=5),   # TP-Fill  → Notfall
        _NS(ticket=3, entry=1, reason=0),   # Hand     → extern
        _NS(ticket=4, entry=1, reason=6),   # Stop-Out → extern
        _NS(ticket=5, entry=0, reason=4),   # IN-Deal  → nie
        _NS(ticket=6, entry=1, reason=5),   # schon verbucht
    ]
    _nf = find_notfall_deals(_deals, {6}, out_entries=(1, 2), reason_sl=4, reason_tp=5)
    chk("NOTFALL-CLOSE: SL/TP-Fills erkannt, Hand/Stop-Out/IN/verbucht aussortiert",
        [d.ticket for d in _nf] == [1, 2])
    chk("NOTFALL-CLOSE: leere/None-Deal-Liste → leer",
        find_notfall_deals(None, set(), out_entries=(1, 2), reason_sl=4, reason_tp=5) == []
        and find_notfall_deals([], set(), out_entries=(1, 2), reason_sl=4, reason_tp=5) == [])

    # ── Order-Bot: offene Terminal-Verbindung (31.08.2026, Finns Tempo-Frage) ──
    # Gegen ein FAKE-MetaTrader5 statt gegen Vermutungen: die eine Zahl, um die
    # es geht, ist "wie oft wird initialize() gerufen" — ein Anschluss ans
    # Terminal kostet auf den PCs 0,5-2 s, sechs davon waren Finns Pausen.
    # Das echte Paket gibt es auf dem Mac nicht; die Attrappe reicht, weil hier
    # NUR das Verbindungs-Verhalten geprueft wird, nicht MT5 selbst.
    import types as _types

    class _FakeMT5:
        def __init__(self):
            self.init_calls = self.shutdown_calls = 0
            self.verbunden = False
            self.login = 10000001
            self.ai_none_mal = 0
            self.init_ok = True

        def initialize(self, path=None, **kw):
            self.init_calls += 1
            self.verbunden = bool(self.init_ok)
            return self.init_ok

        def shutdown(self):
            self.shutdown_calls += 1
            self.verbunden = False

        def last_error(self):
            return (-1, "fake")

        def account_info(self):
            if not self.verbunden:
                return None
            if self.ai_none_mal > 0:
                self.ai_none_mal -= 1
                return None
            return _types.SimpleNamespace(login=self.login)

        def positions_get(self):
            return []

    def _fake_an():
        fake = _FakeMT5()
        sys.modules["MetaTrader5"] = fake
        order_bot._MT5_PFAD = None      # Attrappe startet immer unverbunden
        order_bot._api_stat_reset()
        return fake

    _P = r"C:\MT5\terminal64.exe"
    try:
        fk = _fake_an()
        for _ in range(6):
            _r = order_bot._api_lesen(_P, 10000001)
        chk("ORDER-BOT: 6 Lesevorgaenge docken nur EINMAL an (vorher 6x)",
            fk.init_calls == 1 and fk.shutdown_calls == 0 and "positionen" in _r)
        chk("ORDER-BOT: Spur weist die API-Bilanz aus",
            "API-Lesen 6x" in order_bot._spur(["X"]))
        order_bot._api_trennen()
        order_bot._api_lesen(_P, 10000001)
        chk("ORDER-BOT: nach _api_trennen wird frisch angedockt",
            fk.shutdown_calls == 1 and fk.init_calls == 2)

        fk = _fake_an()
        order_bot._api_lesen(_P, 10000001)
        fk.ai_none_mal = 1                      # Verbindung stirbt mittendrin
        _r = order_bot._api_lesen(_P, 10000001)
        chk("ORDER-BOT: Verbindungsabriss → genau ein Wiederanlauf, Lesen klappt",
            "positionen" in _r and fk.init_calls == 2)

        fk = _fake_an(); fk.init_ok = False
        _r = order_bot._api_lesen(_P, 10000001)
        chk("ORDER-BOT: Terminal weg → Fehlertext wie bisher, hoechstens 2 Versuche",
            _r.get("fehler", "").startswith("Terminal-Verbindung") and fk.init_calls == 2)

        fk = _fake_an(); fk.login = 999999
        _r = order_bot._api_lesen(_P, 10000001)
        chk("ORDER-BOT: falsches Konto bleibt harter Riegel (kein Wiederanlauf)",
            "FALSCHEN Konto" in _r.get("fehler", "") and fk.init_calls == 1)

        fk = _fake_an()
        order_bot._api_lesen(r"C:\MT5-A\terminal64.exe", 10000001)
        order_bot._api_lesen(r"C:\MT5-B\terminal64.exe", 10000001)
        chk("ORDER-BOT: Pfadwechsel haengt sauber um (trennen, neu andocken)",
            fk.init_calls == 2 and fk.shutdown_calls == 1)
    finally:
        sys.modules.pop("MetaTrader5", None)
        order_bot._MT5_PFAD = None
        order_bot._api_stat_reset()

    # ── Order-Bot: SL/TP-Feld — Ausnahme sichtbar + Klick-Anlauf (31.08.2026) ──
    # Finns Fall: "5x geklappt, beim 6. nicht", und die Spur endete stumm mit
    # "SL NICHT uebernommen". Geprueft wird deshalb genau das: landet der Grund
    # in der Spur, und hilft der zweite Anlauf ueberhaupt?
    class _FakeRect:
        def __init__(self, l, t, r, b):
            self.left, self.top, self.right, self.bottom = l, t, r, b

        def mid_point(self):
            return _types.SimpleNamespace(x=(self.left + self.right) // 2,
                                          y=(self.top + self.bottom) // 2)

    class _FakeFeld:
        """set_focus wirft, bis 'heilt_ab' erreicht ist; danach nimmt das Feld
        den getippten Wert an."""
        def __init__(self, heilt_ab=99, rect=(10, 10, 100, 30)):
            self.heilt_ab = heilt_ab
            self.versuch = 0
            self.inhalt = ""
            self.fokussiert = False
            self._rect = _FakeRect(*rect)

        def set_focus(self):
            self.versuch += 1
            if self.versuch < self.heilt_ab:
                raise RuntimeError("Fenster nicht im Vordergrund")
            self.fokussiert = True

        def rectangle(self):
            return self._rect

        def type_keys(self, tasten, **kw):
            # Ohne Fokus kommt beim echten MT5 nichts an — die Attrappe haelt
            # sich daran, sonst wuerde der Test Erfolg zeigen, wo keiner ist.
            if not self.fokussiert:
                return
            if "DELETE" in tasten:
                self.inhalt = ""
            elif not tasten.startswith("^") and not tasten.startswith("{"):
                self.inhalt += tasten

        def get_value(self):
            return self.inhalt

    _rahmen = _types.SimpleNamespace(rectangle=lambda: _FakeRect(0, 0, 500, 400))
    _echt_klick, _echt_warte = order_bot._klick_absolut, order_bot._warte
    _klicks = []
    order_bot._klick_absolut = lambda x, y, **kw: (_klicks.append((x, y)) or True)
    order_bot._warte = lambda a, b: None
    try:
        _sp = []
        _f = _FakeFeld(heilt_ab=99)          # Feld nimmt nie Fokus an
        _ok = order_bot._feld_tippen(_f, "29311.07", "SL", _sp, rahmen=_rahmen)
        chk("ORDER-BOT: SL-Fehlschlag nennt jetzt den GRUND statt nur 'NICHT uebernommen'",
            _ok is False
            and any("SL-Versuch 1 abgebrochen: RuntimeError" in z for z in _sp)
            and any("SL NICHT uebernommen" in z for z in _sp))

        _sp, _klicks[:] = [], []
        _f = _FakeFeld(heilt_ab=2)           # zweiter Anlauf klappt
        _ok = order_bot._feld_tippen(_f, "29311.07", "SL", _sp, rahmen=_rahmen)
        chk("ORDER-BOT: zweiter Anlauf klickt ins Feld und traegt den Wert ein",
            _ok is True and len(_klicks) == 1
            and any("SL-Feld angeklickt (Versuch 2)" in z for z in _sp)
            and _f.inhalt == "29311.07")

        _sp, _klicks[:] = [], []
        _f = _FakeFeld(heilt_ab=2, rect=(900, 900, 980, 920))   # ausserhalb
        order_bot._feld_tippen(_f, "29311.07", "SL", _sp, rahmen=_rahmen)
        chk("ORDER-BOT: Feld ausserhalb des Dialogs wird NICHT blind geklickt",
            not _klicks and any("ausserhalb des Dialogs" in z for z in _sp))
    finally:
        order_bot._klick_absolut, order_bot._warte = _echt_klick, _echt_warte

    # ── Order-Bot: Anker-Merge + Stempel-Spur (01.09.2026, Tempo-Umbau) ────
    # Der Handel-Tab speichert seinen Klickpunkt jetzt in DERSELBEN Anker-Datei
    # wie der Zeilen-Scan. Geprueft wird genau der Unfall, der ohne Merge
    # passiert waere: ein Zeilen-Treffer (SL/TP oder Close) wischt den
    # Tab-Punkt weg — und umgekehrt.
    import tempfile as _tempfile
    with _tempfile.TemporaryDirectory() as _td:
        _ap = os.path.join(_td, "anker-config.json")
        chk("ORDER-BOT: Anker-Lesen ohne Datei → leeres dict, kein Fehler",
            order_bot._anker_lesen(_ap) == {} and order_bot._anker_lesen(None) == {})
        order_bot._anker_schreiben(_ap, x_frac=0.4, y_off=316)
        order_bot._anker_schreiben(_ap, handel_x_off=61, handel_y_off=42)
        order_bot._anker_schreiben(_ap, x_frac=0.5, y_off=300)
        _a = order_bot._anker_lesen(_ap)
        chk("ORDER-BOT: Anker-Schreiben MERGED — Tab-Punkt ueberlebt den Zeilen-Treffer",
            _a.get("x_frac") == 0.5 and _a.get("y_off") == 300
            and _a.get("handel_x_off") == 61 and _a.get("handel_y_off") == 42)
        # None loescht (02.09.2026, Belastung-Fehlklick): ein verworfener
        # Tab-Punkt muss WIRKLICH aus der Datei — sonst klickt der naechste
        # Lauf denselben Fehlpunkt, waehrend der Zeilen-Anker bleiben soll.
        order_bot._anker_schreiben(_ap, handel_x_off=None, handel_y_off=None,
                                   handel_x_frac=None)
        _a = order_bot._anker_lesen(_ap)
        chk("ORDER-BOT: Anker-Wert None LOESCHT den Schluessel, Rest bleibt",
            "handel_x_off" not in _a and "handel_y_off" not in _a
            and _a.get("x_frac") == 0.5 and _a.get("y_off") == 300)
        with open(_ap, "w", encoding="utf-8") as _f:
            _f.write("kaputt{")
        chk("ORDER-BOT: kaputte Anker-Datei → leeres dict statt Absturz",
            order_bot._anker_lesen(_ap) == {})

    _sp = order_bot._StempelSpur()
    _sp.append("Terminal betreten")
    _sp.append("F9-Dialog offen")
    chk("ORDER-BOT: Stempel-Spur traegt Sekunden pro Station, _spur liest sie wie bisher",
        all("s·" in z for z in _sp) and _sp[0].endswith("Terminal betreten")
        and "Terminal betreten → " in order_bot._spur(_sp))

    # UAC-/Update-Hinweis (02.09.2026): NUR bei Terminal-nicht-erreichbar, nie
    # bei Konto-/Symbol-Sachfehlern — sonst schickt er Finn an den PC, obwohl
    # gar keine Windows-Abfrage offen ist.
    chk("ORDER-BOT: UAC-Hinweis bei Verbindungsfehler, nicht bei Konto/Symbol",
        order_bot._ist_verbindungsfehler("Terminal-Verbindung fehlgeschlagen: (-1, 'x')")
        and order_bot._ist_verbindungsfehler("Kein Konto verbunden (account_info leer).")
        and not order_bot._ist_verbindungsfehler("Terminal ist im FALSCHEN Konto (999 statt 10000001).")
        and not order_bot._ist_verbindungsfehler("Broker kennt Symbol 'NDX100' nicht"))

    # ── Panel: Terminal-Zu-Entscheidung (03.09.2026) ───────────────────────
    # Geschlossen wird NUR bei frischem, warnungsfreiem Status ohne Position,
    # ohne Hedge und ohne aktiven Plan — jede einzelne Bedingung muss blocken.
    import panel
    _cfgT = {"master_terminal_path": "C:\\MT5-X\\terminal64.exe"}
    _stOK = {"running": True, "master_positions": [], "hedges": {"1": []}}
    # Hedge-Riegel (22.09.2026, Finn: "auf einmal oeffnet sich das Slave-Hedge-Terminal"):
    # zeigt master_terminal_path in den Hedge-Ordner, wird NIE geschlossen.
    _stZU = {"running": True, "master_positions": [], "hedges": {}}
    _tsb = lambda m, h: panel.terminal_schliessbar({"master_terminal_path": m, "hedge_terminal_path": h}, _stZU, 5, None)[0]
    chk("TERMINAL-ZU: Hedge-Installation wird nie geschlossen (Master- und Hedge-Pfad im selben Ordner), aehnliche Ordnernamen aber schon",
        _tsb(r"C:\MT5-A\terminal64.exe", r"C:\MT5-Hedge\terminal64.exe") is True
        and _tsb(r"C:\MT5-Hedge\terminal64.exe", r"C:\MT5-Hedge\terminal64.exe") is False
        and _tsb(r"C:\MT5-Hedge2\terminal64.exe", r"C:\MT5-Hedge\terminal64.exe") is True
        and _tsb(r"C:\MT5-A\terminal64.exe", "") is True)

    # Leerlauf-Waechter (22.09.2026): schliessen erst nach ununterbrochen leerem Lauf ab Schwelle
    chk("TERMINAL-LEERLAUF: Zaehler startet beim ersten leeren Blick, schliesst ab Schwelle, jeder nicht-leere Blick setzt zurueck",
        panel.leerlauf_entscheidung(True, None, 1000.0, 900) == (1000.0, False)
        and panel.leerlauf_entscheidung(True, 1000.0, 1500.0, 900) == (1000.0, False)
        and panel.leerlauf_entscheidung(True, 1000.0, 1900.0, 900) == (1000.0, True)
        and panel.leerlauf_entscheidung(False, 1000.0, 1900.0, 900) == (None, False)
        and panel.leerlauf_entscheidung(False, None, 1900.0, 900) == (None, False))
    chk("PANEL: Terminal-Zu nur bei frischem Status ohne Position/Hedge/Plan",
        panel.terminal_schliessbar(_cfgT, _stOK, 5, None)[0] is True
        and panel.terminal_schliessbar(_cfgT, _stOK, 99, None)[0] is False
        and panel.terminal_schliessbar(_cfgT, dict(_stOK, running=False), 5, None)[0] is False
        and panel.terminal_schliessbar(_cfgT, dict(_stOK, master_positions=[{"i": 1}]), 5, None)[0] is False
        and panel.terminal_schliessbar(_cfgT, dict(_stOK, hedges={"7": [{"ticket": 1}]}), 5, None)[0] is False
        and panel.terminal_schliessbar(_cfgT, _stOK, 5, "geplant")[0] is False
        and panel.terminal_schliessbar(_cfgT, _stOK, 5, "laufend")[0] is False
        and panel.terminal_schliessbar({}, _stOK, 5, None)[0] is False)
    chk("PANEL: Status-Warnung (note) blockt Terminal-Zu — Alt-Snapshot ist kein Beweis",
        panel.terminal_schliessbar(_cfgT, dict(_stOK, note="Snapshot eingefroren"), 5, None)[0] is False)
    # Echo V2 ohne Copier (30.09.2026, ID A): frischer Lese-EA-Snapshot ist der Beweis
    _lese0 = {"lesen": True, "master_positions": []}
    _stAlt = dict(_stOK, running=False)
    chk("PANEL: Terminal-Zu ohne Copier nur mit frischem Lese-EA, ohne Position, ohne alten Hedge",
        panel.terminal_schliessbar(_cfgT, _stAlt, 999, None, _lese0)[0] is True
        and panel.terminal_schliessbar(_cfgT, {}, None, None, _lese0)[0] is True
        and panel.terminal_schliessbar(_cfgT, _stAlt, 999, None, None)[0] is False
        and panel.terminal_schliessbar(_cfgT, _stAlt, 999, None, dict(_lese0, master_positions=[{"i": 1}]))[0] is False
        and panel.terminal_schliessbar(_cfgT, dict(_stAlt, hedges={"7": [{"ticket": 1}]}), 999, None, _lese0)[0] is False
        and panel.terminal_schliessbar(_cfgT, _stAlt, 999, "laufend", _lese0)[0] is False
        and panel.terminal_schliessbar({}, _stAlt, 999, None, _lese0)[0] is False)
    # Zufalls-Streuung: Auto-Zu wuerfelt 1-2 min (21.09.2026, vorher 1-60 min)
    # — nie sofort und nie im immer gleichen Abstand (waere selbst ein Muster).
    _vz = [panel._zufalls_verzoegerung() for _ in range(200)]
    chk("PANEL: Terminal-Zu-Verzoegerung wuerfelt immer zwischen 60 s und 120 s",
        all(60 <= v <= 120 for v in _vz) and len(set(round(v) for v in _vz)) > 10)

    # Zu-Auftrag ueberlebt den Panel-Neustart (21.09.2026): Trade-Ende schreibt
    # 'terminal_zu: offen' nach plans.json, der Panel-Start holt ihn nach, der
    # Worker loescht den Vermerk am Ende wieder.
    _pf_alt, _zs_alt = panel.PLANS_FILE, panel._terminal_zu_starten
    with tempfile.TemporaryDirectory() as _td:
        try:
            panel.PLANS_FILE = os.path.join(_td, "plans.json")
            _gestartet = []
            panel._terminal_zu_starten = lambda f, a: _gestartet.append((f, a))
            panel._save_plans([{"id": 1, "file": "config.json", "name": "X", "multiplier": 1,
                                "status": "laufend", "started_at": "x", "ended_at": None}])
            panel.advance_plans([{"file": "config.json", "alive": True,
                                  "status": {"running": True, "master_positions": []}}])
            _pl = panel._load_plans()
            chk("PANEL: Trade-Ende vermerkt den Terminal-Zu-Auftrag auf Platte und startet den Worker",
                _pl[0]["status"] == "beendet" and _pl[0].get("terminal_zu") == "offen"
                and _gestartet == [("config.json", "Trade-Ende")])
            _gestartet.clear()
            panel.terminal_zu_nachholen()
            chk("PANEL: Panel-Start holt den offenen Terminal-Zu-Auftrag genau einmal nach",
                len(_gestartet) == 1 and _gestartet[0][0] == "config.json")
            panel._terminal_zu_erledigt("config.json")
            _gestartet.clear()
            panel.terminal_zu_nachholen()
            chk("PANEL: erledigter Terminal-Zu-Auftrag wird nicht noch einmal nachgeholt",
                _gestartet == [] and "terminal_zu" not in panel._load_plans()[0])
        finally:
            panel.PLANS_FILE, panel._terminal_zu_starten = _pf_alt, _zs_alt

    # ── Panel: Terminal-Zu nach Config-Loeschung (07.09.2026, Archiv-Auftrag) ──
    # Nach dem Loeschen einer Instanz darf NUR der eigene Master-Ordner
    # geschossen werden — nie das Hedge-Terminal, nie der Ordner einer anderen
    # Config. Pfade forward-slash, damit der Test auf Mac UND Windows laeuft.
    _cfgL  = {"master_terminal_path": "/mt5/acc1/terminal64.exe",
              "hedge_terminal_path":  "/mt5/hedge/terminal64.exe"}
    _fremd = {"master_terminal_path": "/mt5/acc2/terminal64.exe",
              "hedge_terminal_path":  "/mt5/hedge/terminal64.exe"}
    chk("PANEL: Loesch-Terminal-Zu trifft den eigenen Master-Ordner",
        panel.loesch_terminal_dir(_cfgL, [_fremd]) is not None
        and panel.loesch_terminal_dir(_cfgL, []) is not None
        and panel.loesch_terminal_dir(_cfgL, None) is not None)
    chk("PANEL: Loesch-Terminal-Zu — ohne Master-Pfad (Orbit/TV) nie schiessen",
        panel.loesch_terminal_dir({}, []) is None
        and panel.loesch_terminal_dir({"master_terminal_path": "  "}, []) is None
        and panel.loesch_terminal_dir(None, []) is None)
    chk("PANEL: Loesch-Terminal-Zu — Master==Hedge-Ordner (Fehlkonfig) nie schiessen",
        panel.loesch_terminal_dir({"master_terminal_path": "/mt5/hedge/terminal64.exe",
                                   "hedge_terminal_path":  "/mt5/hedge/terminal64.exe"},
                                  []) is None)
    chk("PANEL: Loesch-Terminal-Zu — Ordner einer ANDEREN Config nie schiessen",
        panel.loesch_terminal_dir(_cfgL, [{"master_terminal_path": "/mt5/acc1/terminal64.exe"}]) is None
        and panel.loesch_terminal_dir(_cfgL, [{"hedge_terminal_path": "/mt5/acc1/terminal64.exe"}]) is None)

    # ── Magic-Umzug 11.09.2026 (The5ers-Kollision von ID C — NUR 2 Accounts) ────
    # PC-uebergreifende magic-Kollision am gemeinsamen Hedge-Konto: fremder
    # Copier schloss die frischen Hedges sofort. Der Umzug darf ausschliesslich
    # die zwei benannten Master treffen und nie einen neuen Konflikt erzeugen.
    _M1, _M2 = sorted(MAGIC_UMZUG)   # die zwei benannten Master — echte Logins stehen nur in der Logik-Tabelle (copier.py)
    chk("Magic-Umzug trifft NUR die zwei benannten Master",
        magic_umzug_ziel(_M1, 770005, set()) == 779215
        and magic_umzug_ziel(_M2, 770006, set()) == 779216
        and magic_umzug_ziel(10000004, 770007, set()) is None
        and magic_umzug_ziel(0, 770005, set()) is None
        and magic_umzug_ziel(None, 770005, set()) is None)
    chk("Magic-Umzug ist idempotent und respektiert hoehere Bloecke",
        magic_umzug_ziel(_M1, 779215, set()) is None
        and magic_umzug_ziel(_M1, 771003, set()) is None)
    chk("Magic-Umzug weicht belegtem Ziel aus (nie neuer lokaler Konflikt)",
        magic_umzug_ziel(_M1, 770005, {779215}) is None
        and magic_umzug_ziel(_M2, 770006, {779215}) == 779216)

    # ── Magic-Familie 11.09.2026 nachmittags (Erweiterung auf 760000-779999) ──
    # Die Flotte hatte alle Bestands-Bloecke 770000-776000 vergeben; erweitert
    # wurde nach UNTEN, damit Bestand und 779er-Umzugs-Reservat exakt so
    # weiterlaufen wie vorher. Der Check nagelt die Grenzen fest und beweist,
    # dass die Umzugs-Ziele in der Familie liegen — laegen sie draussen,
    # wuerden die umgezogenen Hedges von ID C auf jedem anderen PC als FREMDE
    # Position alarmiert.
    chk("Magic-Familie: 760000-779999, Bestand + Umzugs-Reservat innerhalb",
        FAMILIE_MIN == 760000 and FAMILIE_MAX == 779999
        and all(FAMILIE_MIN <= z <= FAMILIE_MAX for z in MAGIC_UMZUG.values())
        and FAMILIE_MIN <= 770000 and 778999 <= FAMILIE_MAX)

    # ── Slave-Terminal nach vorn (24.09.2026): Prozess-Erkennung ohne wmic ────
    results.append(test_terminal_pids_ohne_wmic())
    results.append(test_mt5_update_still())
    results.append(test_vordergrund_waechter_ohne_windows())
    results.append(test_kerze_fortschreiben())
    results.append(test_solo_level_und_grund())
    results.append(test_solo_zu_ring())
    results.append(test_solo_plan_kennung())
    results.append(test_solo_riegel())
    results.append(test_pc_id())
    results.append(test_lese_instanz())
    results.append(test_endlesung_bausteine())
    results.append(test_profil_riegel())
    results.append(test_fenster_treue())
    results.append(test_puls_tempo())
    results.append(test_puls_topstep())
    results.append(test_puls_augen_cdp())
    results.append(test_puls_k3())
    results.append(test_puls_cdp_login())
    results.append(test_cdp_konto_regression_865())
    results.append(test_cdp_konto_weg())
    results.append(test_cdp_connect_zweiter_versuch())
    results.append(test_tsx_k0())
    results.append(test_tsx_k1_vorbau())
    results.append(test_tsx_k2())
    results.append(test_tsx_k3a())
    results.append(test_tsx_k4())
    results.append(test_puls_win_maus())
    results.append(test_puls_nie_chrome_schliessen())
    results.append(test_tsx_konto_abgekuerzt())
    results.append(test_tsx_titel_url())
    results.append(test_tsx_zeilen())
    results.append(test_tsx_inventar_ida())
    results.append(test_tsx_beweis())
    results.append(test_tsx_order())
    results.append(test_tsx_login())
    results.append(test_tsx_bracket_b36())
    results.append(test_puls_heim())
    results.append(test_tv_tp_orders())
    results.append(test_hedge_bereit())
    results.append(test_quickedit())

    print()
    ok = sum(1 for r in results if r)
    print(f"{ok}/{len(results)} Tests bestanden")
    return 0 if ok == len(results) else 1



def test_mt5_update_still():
    """01.10.2026: MT5-Update ohne UAC-Abfrage ueber eine geplante Aufgabe."""
    import base64
    import re
    import time
    import provision as pv
    ok = True
    # Nur X:\MT5-... — Programme-Ordner, Unterordner, Sonderzeichen nie.
    for p, soll in ((r"C:\MT5-Hedge", True), (r"d:\MT5-ftmo1", True),
                    (r"C:\Program Files\MetaTrader 5", False), (r"C:\MT5-a\b", False),
                    (r"C:\MT5-", False), ("", False), (None, False)):
        if pv.ist_mt5_ordner(p) != soll:
            print(f"✗ ist_mt5_ordner({p!r}) != {soll}"); ok = False
    # Nur echt NEUERE Builds, nie zurueck, nie ohne lesbare Version.
    if not (pv.build_neuer((5, 0, 0, 5200), (5, 0, 0, 5260))
            and not pv.build_neuer((5, 0, 0, 5260), (5, 0, 0, 5260))
            and not pv.build_neuer((5, 0, 0, 5260), (5, 0, 0, 5200))
            and not pv.build_neuer(None, (5, 0, 0, 5260))
            and not pv.build_neuer((5, 0, 0, 5200), None)):
        print("✗ build_neuer vergleicht falsch"); ok = False
    # Python-Filter und Aufgaben-Skript benutzen dieselbe Ordner-Regel.
    if pv._MT5_ORDNER_RE.pattern not in pv._MT5_UPDATE_PS:
        print("✗ Ordner-Regel im Aufgaben-Skript weicht vom Python-Filter ab"); ok = False
    # Schutz-Bausteine im Skript: Merker, Signatur, laeuft-Pruefung.
    for teil in ("prophos-update.lock", "Get-AuthenticodeSignature", "MetaQuotes",
                 "'Valid'", "$neu -le $alt", "Where-Object { $_.Path -eq $exe }"):
        if teil not in pv._MT5_UPDATE_PS:
            print(f"✗ Aufgaben-Skript ohne {teil!r}"); ok = False
    # Einrichtung: Admin-only-Ordner per SID, Aufgabe mit hoechsten Rechten,
    # eingebettetes Skript ist byte-gleich mit dem Original.
    s = pv.setup_ps()
    for teil in ("*S-1-5-32-544", "/inheritance:r", "-RunLevel Highest",
                 f"-TaskName '{pv.MT5_UPDATE_TASK}'"):
        if teil not in s:
            print(f"✗ Einrichtung ohne {teil!r}"); ok = False
    b64 = re.search(r"FromBase64String\('([^']+)'\)", s)
    if not b64 or base64.b64decode(b64.group(1)).decode("utf-8") != pv._MT5_UPDATE_PS:
        print("✗ eingebettetes Skript nicht byte-gleich"); ok = False
    if len(base64.b64encode(s.encode("utf-16-le"))) > 30000:
        print("✗ -EncodedCommand zu lang fuer die Kommandozeile"); ok = False
    # Ohne Windows: alles still und folgenlos.
    if (pv.update_ausstehend() != [] or pv.update_aufgabe_ok()
            or pv.update_aufgabe_einrichten(warte_s=0) or pv._datei_version(__file__) is not None):
        print("✗ MT5-Update tut ohne Windows etwas"); ok = False
    # Kein Merker / alter Merker -> sofort weiter; frischer Merker -> wartet.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        t0 = time.time(); pv.update_abwarten(td, max_s=5)
        if time.time() - t0 > 1:
            print("✗ update_abwarten wartet ohne Merker"); ok = False
        lock = os.path.join(td, pv.UPDATE_LOCK)
        open(lock, "w").close()
        os.utime(lock, (time.time() - 700, time.time() - 700))
        t0 = time.time(); pv.update_abwarten(td, max_s=5)
        if time.time() - t0 > 1:
            print("✗ update_abwarten wartet auf einen Rest-Merker (>10 min)"); ok = False
        os.utime(lock, None)
        t0 = time.time(); pv.update_abwarten(td, max_s=3)
        if time.time() - t0 < 2.5:
            print("✗ update_abwarten wartet nicht auf einen frischen Merker"); ok = False
    if ok:
        print("✓ MT5-Update still: Ordner-Regel, nur neuere Builds, Schutz im Skript, Admin-only-Einrichtung, Merker-Warten")
    return ok


def test_terminal_pids_ohne_wmic():
    """24.09.2026: Prozess-Erkennung ohne wmic (fehlt auf Windows 11 24H2+)."""
    import provision
    import subprocess as sp
    ok = True
    # Reiner Parser des PowerShell-Wegs: nur Zeilen mit passendem Pfad zaehlen.
    inst = os.path.join(os.sep, "MT5-Hedge")
    exe = os.path.join(inst, "terminal64.exe")
    txt = f"1234|{exe}\n99|{os.path.join(os.sep, 'MT5-ftmo1', 'terminal64.exe')}\n" \
          f"abc|{exe}\n  5678 | {exe} \n\n"
    got = provision.pids_aus_ps_zeilen(txt, inst)
    if got != [1234, 5678]:
        print(f"✗ pids_aus_ps_zeilen: {got}"); ok = False
    # Auf dem Mac: Win32 → None, wmic fehlt → None, powershell fehlt → None → [] (kein Absturz).
    if provision._pids_per_winapi(inst) is not None:
        print("✗ _pids_per_winapi muss ohne Windows None liefern"); ok = False
    if provision.terminal_pids(inst) != []:
        print("✗ terminal_pids ohne jeden Weg muss [] liefern"); ok = False
    # Stub: wmic fehlt (FileNotFoundError), PowerShell liefert → PowerShell-Weg gewinnt.
    echt = sp.run
    def stub(cmd, **kw):
        if cmd[0] == "wmic":
            raise FileNotFoundError("wmic")
        class R: returncode = 0; stdout = f"4321|{exe}\n"
        return R()
    sp.run = stub
    try:
        if provision.terminal_pids(inst) != [4321]:
            print("✗ PowerShell-Rueckfall greift nicht, wenn wmic fehlt"); ok = False
        # Stub: wmic da und leer (Terminal laeuft nicht) → [] ohne PowerShell-Weg.
        def stub2(cmd, **kw):
            class R: returncode = 0; stdout = "ProcessId\n\n" if cmd[0] == "wmic" else f"7|{exe}\n"
            return R()
        sp.run = stub2
        if provision.terminal_pids(inst) != []:
            print("✗ wmic-Leerergebnis muss gelten (kein PowerShell-Weg)"); ok = False
        def stub3(cmd, **kw):
            class R: returncode = 0; stdout = "ProcessId\n\n2222\n" if cmd[0] == "wmic" else ""
            return R()
        sp.run = stub3
        if provision.terminal_pids(inst) != [2222]:
            print("✗ wmic-Weg liefert nicht die PID"); ok = False
    finally:
        sp.run = echt
    if ok:
        print("✓ terminal_pids: Win32 → wmic → PowerShell, ohne wmic kein Blindflug")
    return ok


def test_vordergrund_waechter_ohne_windows():
    """Vordergrund-Rueckgabe/-Waechter sind ohne Windows folgenlos und werfen nie."""
    import copier
    ok = True
    if copier._hedge_fenster("/x/terminal64.exe") != []:
        print("✗ _hedge_fenster ohne Windows muss [] liefern"); ok = False
    if copier._vordergrund_merken("/x/terminal64.exe") is not None:
        print("✗ _vordergrund_merken ohne Windows muss None liefern"); ok = False
    if copier._vordergrund_zurueck(None, dauer_s=1.0) != 0:
        print("✗ _vordergrund_zurueck(None) muss 0 Eingriffe liefern"); ok = False
    if copier._vordergrund_zurueck({"vorn": 1, "hedge": {}, "hpath": "/x"}, dauer_s=0.0) != 0:
        print("✗ _vordergrund_zurueck ohne Windows muss 0 liefern"); ok = False
    if copier._vordergrund_waechter_starten({"vorn": 1, "hedge": {}, "hpath": "/x"}) is not None:
        print("✗ Waechter ohne Windows darf keinen Thread starten"); ok = False
    if ok:
        print("✓ Vordergrund-Waechter: ohne Windows folgenlos")
    return ok


def test_kerze_fortschreiben():
    """Minutenkerzen aus Ticks (zweiter Kurs-Feed NAS100, 24.09.2026): o/h/l/c/n,
    Minutenwechsel schiebt die laufende Kerze nach 'vor', Wurzelwechsel oeffnet neu."""
    import copier
    ok = True
    k, v = copier.kerze_fortschreiben(None, None, "NAS100", "NAS100", 20000.5, 1000 * 60 + 5)
    k, v = copier.kerze_fortschreiben(k, v, "NAS100", "NAS100", 20003.0, 1000 * 60 + 10)
    k, v = copier.kerze_fortschreiben(k, v, "NAS100", "NAS100", 19999.0, 1000 * 60 + 20)
    if (k["o"], k["h"], k["l"], k["c"], k["n"], k["minute"]) != (20000.5, 20003.0, 19999.0, 19999.0, 3, 60000) or v is not None:
        print(f"✗ Kerze o/h/l/c/n falsch: {k} vor={v}"); ok = False
    k2, v2 = copier.kerze_fortschreiben(k, v, "NAS100", "NAS100", 20001.0, 1001 * 60 + 1)
    if v2 is not k or k2["minute"] != 1001 * 60 or k2["o"] != 20001.0 or k2["n"] != 1:
        print(f"✗ Minutenwechsel falsch: {k2} vor={v2}"); ok = False
    k3, v3 = copier.kerze_fortschreiben(k2, v2, "NQ", "NQZ2026", 30000.0, 1001 * 60 + 2)
    if v3 is not k2 or k3["wurzel"] != "NQ" or k3["n"] != 1:
        print(f"✗ Wurzelwechsel falsch: {k3} vor={v3}"); ok = False
    if ok:
        print("✓ Kerzen-Aggregation: o/h/l/c/n, Minuten- und Wurzelwechsel")
    return ok


def test_solo_level_und_grund():
    """Solo-Hedge: Lots aus eur/punkte, beide Schliess-Level, DEAL_REASON-Grund."""
    import copier
    ok = True
    si = {"volume_step": 0.01, "volume_min": 0.01, "volume_max": 100.0, "point": 0.01, "digits": 2}
    if copier.solo_lots(70, 140, 0.85, si) != 0.59 or copier.solo_lots(0.5, 140, 0.85, si) != 0.0:
        print("✗ solo_lots"); ok = False
    # 110 % (25.09.2026): SELL-Hedge SL ueber dem Fill bei 1,1 × Distanz, BUY darunter; Mindestabstand punkte + 1;
    # Alt-Weg puffer nur ohne Faktor
    if copier.solo_notfall_sl(20000, "sell", 140, faktor=1.10, point=0.01, digits=2) != 20154.0 \
            or copier.solo_notfall_sl(20000, "buy", 140, faktor=1.10, point=0.01, digits=2) != 19846.0:
        print("✗ solo_notfall_sl 110 % (Notfall-SL Master-TP-Seite)"); ok = False
    if copier.solo_notfall_sl(20000, "buy", 5, faktor=1.10, point=0.01, digits=2) != 19994.0:
        print("✗ solo_notfall_sl Mindestabstand punkte + 1 (5 × 1,1 = 5,5 < 6)"); ok = False
    if copier.solo_notfall_sl(20000, "sell", 140, faktor=None, puffer=3, point=0.01, digits=2) != 20143.0:
        print("✗ solo_notfall_sl Alt-Weg puffer ohne Faktor"); ok = False
    if copier.solo_notfall_sl(0, "buy", 10, faktor=1.1, point=0.01, digits=2) != 0.0:
        print("✗ solo_notfall_sl ohne Fill → 0"); ok = False
    # Reserve-Level Master-SL-Seite HINTER dem Master-SL (25.09.2026): SELL-Hedge TP unter dem Fill bei sl_punkte + puffer
    if copier.solo_level_tp(20000, "sell", 100, puffer=3, point=0.01, digits=2) != 19897.0 \
            or copier.solo_level_tp(20000, "buy", 100, puffer=3, point=0.01, digits=2) != 20103.0 \
            or copier.solo_level_tp(20000, "buy", 2, puffer=0, point=0.01, digits=2) != 20002.0 \
            or copier.solo_level_tp(20000, "buy", 0, puffer=3, point=0.01, digits=2) != 0.0:
        print("✗ solo_level_tp (Reserve-Level Master-SL, hinter dem SL)"); ok = False
    if [copier.solo_deal_grund(x) for x in (4, 5, 3, 0, 6, "x")] != ["level_tp", "level_sl", "close", "hand", "stopout", "unbekannt"]:
        print("✗ solo_deal_grund"); ok = False
    # explizite Lots (Popup 1 Multiplikator): 0,94 bleibt auf Raster 0,01; 0,004 → unter Mindestlot = 0.0; 0,996 → 1.0;
    # ohne lots → aus eur/punkte wie bisher
    if copier.solo_lots_waehlen(0.94, 70, 140, 0.85, si) != (0.94, 0.94, "lots"):
        print("✗ solo_lots_waehlen 0,94"); ok = False
    if copier.solo_lots_waehlen(0.004, 70, 140, 0.85, si) != (0.0, 0.004, "lots"):
        print("✗ solo_lots_waehlen 0,004 muss 0.0 (Mindestlot) liefern"); ok = False
    if copier.solo_lots_waehlen(0.996, 0, 0, 0.85, si) != (1.0, 0.996, "lots"):
        print("✗ solo_lots_waehlen 0,996 Raster"); ok = False
    if copier.solo_lots_waehlen(None, 70, 140, 0.85, si) != (0.59, None, "eur") or copier.solo_lots_waehlen(0, 70, 140, 0.85, si)[2] != "eur":
        print("✗ solo_lots_waehlen ohne lots → eur"); ok = False
    if ok:
        print("✓ Solo-Hedge: Lots, beide Level, Grund-Mapping")
    return ok


def test_solo_plan_kennung():
    """Plan-Kennung im Solo-Kommentar (25.09.2026): 'PXsolo:<plan8>', <= 31 Zeichen, Parsen mit/ohne Kennung,
    und die Kennung reist mit bekannt → Abschluss-Ring."""
    import copier
    ok = True
    k = copier.solo_kommentar("0a0a0a33-1234-4abc-9def-000000000000")
    if k != "PXsolo:0a0a0a33" or len(k) > copier.SOLO_KOMMENTAR_MAX:
        print(f"✗ solo_kommentar mit plan_id: {k!r}"); ok = False
    if copier.solo_kommentar(None) != "PXsolo" or copier.solo_kommentar("") != "PXsolo":
        print("✗ solo_kommentar ohne plan_id"); ok = False
    if copier.solo_kommentar("ab:c/d e;f\\gh12345") != "PXsolo:abcdefgh":
        print(f"✗ solo_kommentar Sonderzeichen: {copier.solo_kommentar('ab:c/d e;f')!r}"); ok = False
    if len(copier.solo_kommentar("x" * 200)) > 31:
        print("✗ Kommentar laenger als 31"); ok = False
    faelle = {"PXsolo:0a0a0a33": "0a0a0a33", " PXsolo:0a0a0a ": "0a0a0a", "PXsolo": None, "PXsoloc": None,
              "PXsolo:": None, "": None, None: None, "PX-760001": None, "PXsolo:0a0a0a33extra": "0a0a0a33"}
    for ein, soll in faelle.items():
        if copier.solo_plan8(ein) != soll:
            print(f"✗ solo_plan8({ein!r}) = {copier.solo_plan8(ein)!r}, soll {soll!r}"); ok = False
    # Kennung reist mit: bekannt-Eintrag traegt plan8/plan_id, verschwundene Position → Ring-Eintrag hat sie
    bekannt = {4711: {"symbol": "NAS100", "lots": 0.09, "plan8": "0a0a0a33", "plan_id": "0a0a0a33-1234"}}
    weg = copier.solo_zu_erkennen(bekannt, {})
    ring = copier.solo_zu_ring([], dict(weg[0], pl=-4.2))
    if ring[0].get("plan8") != "0a0a0a33" or ring[0].get("plan_id") != "0a0a0a33-1234":
        print(f"✗ Kennung im Abschluss-Ring: {ring}"); ok = False
    if ok:
        print("✓ Solo-Plan-Kennung: Kommentar PXsolo:<plan8> (≤ 31), Parsen mit/ohne Kennung, Kennung im Abschluss-Ring")
    return ok


def test_quickedit():
    """QuickEdit aus beim Start (25.09.2026, pc-cccccc: Klick ins Konsolenfenster hielt den Prozess an) —
    copier und panel: Bit-Logik, Nicht-Windows = None, 'Windows' ohne Konsole = False statt Absturz."""
    import copier, panel, os
    ok = True
    for mod in (copier, panel):
        if not (mod._quickedit_modus(0x01F7) == 0x01B7 and mod._quickedit_modus(0x0007) == 0x0087):
            print(f"✗ {mod.__name__}._quickedit_modus"); ok = False
        if os.name != "nt":
            if mod.quickedit_aus() is not None:
                print(f"✗ {mod.__name__}.quickedit_aus auf Nicht-Windows"); ok = False
            alt = mod.os.name
            try:
                mod.os.name = "nt"
                if mod.quickedit_aus() is not False:
                    print(f"✗ {mod.__name__}.quickedit_aus ohne Konsole"); ok = False
            finally:
                mod.os.name = alt
    if ok:
        print("✓ QuickEdit aus: Bit-Logik, Nicht-Windows kein Eingriff, ohne Konsole kein Absturz (copier + panel)")
    return ok


def test_hedge_bereit():
    """Neustart-Sperre 'Start steht bevor' (25.09.2026): Copier liest Restzeit, Panel setzt/verlaengert nie kuerzer."""
    import copier, json, os, tempfile, time
    ok = True
    d = tempfile.mkdtemp()
    pfad = os.path.join(d, copier.HEDGE_BEREIT)
    if copier.hedge_bereit_rest(pfad, 1000.0) != 0.0:
        print("✗ ohne Datei muss 0 sein"); ok = False
    for inhalt, jetzt, soll in (({"bis": 1180.0}, 1000.0, 180.0), ({"bis": 900.0}, 1000.0, 0.0),
                                ({"bis": 1e12}, 1000.0, 900.0), ({"bis": "kaputt"}, 1000.0, 0.0), ([1, 2], 1000.0, 0.0)):
        with open(pfad, "w", encoding="utf-8") as f:
            json.dump(inhalt, f)
        if copier.hedge_bereit_rest(pfad, jetzt) != soll:
            print(f"✗ hedge_bereit_rest({inhalt}) = {copier.hedge_bereit_rest(pfad, jetzt)}, soll {soll}"); ok = False
    with open(pfad, "w", encoding="utf-8") as f:
        f.write("{kein json")
    if copier.hedge_bereit_rest(pfad, 1000.0) != 0.0:
        print("✗ kaputtes JSON muss 0 sein"); ok = False
    # Panel-Seite: setzen, nie verkuerzen, Deckel 900 s
    import panel
    alt_here = panel.HERE
    try:
        panel.HERE = d
        os.remove(pfad)
        t0 = time.time()
        b1 = panel.hedge_bereit_setzen(180, "tv-order MNQZ6")
        b2 = panel.hedge_bereit_setzen(30, "kurz")          # darf nicht verkuerzen
        b3 = panel.hedge_bereit_setzen(5000, "zu lang")     # Deckel 900
        gel = json.load(open(pfad, encoding="utf-8"))
        if not (170 <= b1 - t0 <= 190 and b2 == b1 and 890 <= b3 - t0 <= 910 and gel["grund"] == "zu lang"
                and 890 <= copier.hedge_bereit_rest(pfad, time.time()) <= 900):
            print(f"✗ hedge_bereit_setzen: {b1 - t0:.0f}/{b2 - t0:.0f}/{b3 - t0:.0f} {gel}"); ok = False
    finally:
        panel.HERE = alt_here
    if ok:
        print("✓ Neustart-Sperre 'Start steht bevor': Restzeit, abgelaufen/kaputt = 0, Deckel 900 s, Panel verkuerzt nie")
    return ok


def test_solo_zu_ring():
    """Selbst erkannte Solo-Abschluesse: erkennen, nicht doppelt, Ring max 20, Neustart-Persistenz."""
    import copier, json, tempfile
    ok = True
    bekannt = {4711: {"symbol": "NAS100", "lots": 0.59, "richtung": "sell", "fill": 20000.5}, 4712: {"symbol": "NAS100", "lots": 0.2}}
    weg = copier.solo_zu_erkennen(bekannt, {4712: {"symbol": "NAS100"}})
    if [e["ticket"] for e in weg] != [4711] or weg[0].get("lots") != 0.59:
        print(f"✗ solo_zu_erkennen: {weg}"); ok = False
    if copier.solo_zu_erkennen(bekannt, bekannt) != [] or copier.solo_zu_erkennen({}, {1: {}}) != []:
        print("✗ solo_zu_erkennen: nichts verschwunden muss [] liefern"); ok = False
    # Schluessel als Strings (aus JSON gelesen) muessen genauso gehen
    if [e["ticket"] for e in copier.solo_zu_erkennen({"4711": {"lots": 1.0}}, {})] != [4711]:
        print("✗ solo_zu_erkennen: String-Schluessel"); ok = False
    ring = copier.solo_zu_ring([], {"ticket": 4711, "pl": -4.2, "grund": "level_tp"})
    ring = copier.solo_zu_ring(ring, {"ticket": 4711, "pl": -9.9, "grund": "hand"})   # doppelt → der Erste gewinnt
    if len(ring) != 1 or ring[0]["pl"] != -4.2:
        print(f"✗ solo_zu_ring doppelt: {ring}"); ok = False
    for t in range(1, 30):
        ring = copier.solo_zu_ring(ring, {"ticket": 5000 + t, "pl": 0.0, "grund": "close"})
    if len(ring) != 20 or ring[-1]["ticket"] != 5029 or any(r["ticket"] == 4711 for r in ring):
        print(f"✗ solo_zu_ring Laenge/Reihenfolge: {len(ring)} {ring[-1]}"); ok = False
    if copier.solo_zu_ring("kaputt", {"ticket": 1}) != [{"ticket": 1}]:
        print("✗ solo_zu_ring mit kaputtem Ring"); ok = False
    # Persistenz-Form: {zu, bekannt} — was gespeichert wird, muss nach dem Neustart identisch zurueckkommen
    d = tempfile.mkdtemp(); pf = os.path.join(d, copier.SOLO_ZU)
    json.dump({"zu": ring, "bekannt": {"4712": {"symbol": "NAS100"}}}, open(pf, "w"))
    geladen = json.load(open(pf))
    if len(geladen["zu"]) != 20 or geladen["bekannt"].get("4712", {}).get("symbol") != "NAS100":
        print("✗ Persistenz-Form"); ok = False
    if ok:
        print("✓ Solo-Abschluss-Ring: erkennen, nicht doppelt, max 20, Persistenz-Form")
    return ok


def test_solo_riegel():
    """Riegel gegen den zweiten Open (zweite Gegenpruefung 25.09.2026): zwei Auftraege derselben plan8 nacheinander
    → der zweite findet die Position des ersten und antwortet 'schon_offen' (retry_ok False, Ticket/Lots/Fill)."""
    import copier
    ok = True
    pid = "0a0a0a33-1234-4abc-9def-000000000000"
    konto = []   # offene Positionen im geteilten Fusion-Konto
    # Auftrag 1: nichts offen → kein Riegel, „Open" legt die Position mit Kommentar PXsolo:<plan8> an
    if copier.solo_schon_offen(konto, pid) is not None:
        print("✗ Riegel greift bei leerem Konto"); ok = False
    konto.append({"ticket": 555001, "magic": copier.SOLO_MAGIC, "comment": copier.solo_kommentar(pid), "type": 1,
                  "volume": 0.94, "price_open": 20000.5, "sl": 20150.0, "tp": 19890.0, "symbol": "NAS100"})
    # Auftrag 2: gleiche plan_id → Riegel
    treffer = copier.solo_schon_offen(konto, pid)
    erg = copier.solo_schon_offen_erg(treffer, pid) if treffer is not None else {}
    soll = {"ok": False, "code": "schon_offen", "retry_ok": False, "ticket": 555001, "lots": 0.94, "fill": 20000.5,
            "sl": 20150.0, "tp": 19890.0, "richtung": "sell", "plan8": "0a0a0a33"}
    if any(erg.get(k) != v for k, v in soll.items()):
        print(f"✗ zweiter Auftrag gleicher plan8: {erg}"); ok = False
    # anderer Plan, fremde magic, ohne plan_id → kein Riegel
    if copier.solo_schon_offen(konto, "77777777-aaaa") is not None:
        print("✗ Riegel greift bei fremdem Plan"); ok = False
    if copier.solo_schon_offen([dict(konto[0], magic=760001)], pid) is not None:
        print("✗ Riegel greift bei Copier-magic"); ok = False
    if copier.solo_schon_offen(konto, None) is not None or copier.solo_schon_offen(konto, "") is not None:
        print("✗ Riegel ohne plan_id muss None sein"); ok = False
    # Kommentar vom Broker gekuerzt/ueberschrieben → Zuordnung ueber Ticket→plan_id (solo_plan/solo_bekannt)
    gekuerzt = [dict(konto[0], comment="PXsolo")]
    if copier.solo_schon_offen(gekuerzt, pid) is not None:
        print("✗ ohne Kommentar-Kennung und ohne Zuordnung darf nichts greifen"); ok = False
    if copier.solo_schon_offen(gekuerzt, pid, {555001: pid}) is None or copier.solo_schon_offen(gekuerzt, pid, {"555001": {"plan_id": pid}}) is None:
        print("✗ Riegel ueber Ticket→plan_id (int- und String-Schluessel)"); ok = False
    if copier.solo_schon_offen(None, pid) is not None:
        print("✗ None-Liste"); ok = False
    if ok:
        print("✓ Solo-Riegel: zweiter Auftrag gleicher plan8 → 'schon_offen' mit Ticket/Lots/Fill; fremder Plan, Copier-magic, ohne plan_id frei; Zuordnung auch ueber Ticket→plan_id")
    return ok


def test_pc_id():
    """PC-Kennung im Panel (25.09.2026): leer → POST setzt; zweiter POST anderer Wert → bleibt; kaputte Datei → null;
    falsches Format → ValueError (Panel: 400)."""
    import panel, tempfile
    ok = True
    d = tempfile.mkdtemp(); pf = os.path.join(d, "pc_id.json")
    if panel.pc_id_lesen(pf) is not None:
        print("✗ pc_id: ohne Datei muss null kommen"); ok = False
    if panel.pc_id_setzen("pc-cccccc", pf) != ("pc-cccccc", True) or panel.pc_id_lesen(pf) != "pc-cccccc":
        print("✗ pc_id: erster POST setzt nicht"); ok = False
    if panel.pc_id_setzen("pc-dddddd", pf) != ("pc-cccccc", False) or panel.pc_id_lesen(pf) != "pc-cccccc":
        print("✗ pc_id: zweiter POST darf nicht ueberschreiben"); ok = False
    for kaputt in ("{nicht json", '{"pc_id": 5}', '{"pc_id": "PC-GROSS"}', '["pc-cccccc"]'):
        open(pf, "w").write(kaputt)
        if panel.pc_id_lesen(pf) is not None:
            print(f"✗ pc_id: kaputte Datei {kaputt!r} muss null liefern"); ok = False
    if panel.pc_id_setzen("pc-abcd12", pf) != ("pc-abcd12", True):
        print("✗ pc_id: kaputte Datei wird beim naechsten POST ersetzt"); ok = False
    for falsch in ("", None, "pc-", "pc-ab", "pc-ABCD", "pc-abcdefghijklm", "xx-abcd", "pc-abcd; rm"):
        try:
            panel.pc_id_setzen(falsch, os.path.join(d, "x.json")); print(f"✗ pc_id: Format {falsch!r} angenommen"); ok = False
        except ValueError:
            pass
    if os.path.exists(pf + ".tmp"):
        print("✗ pc_id: .tmp liegt noch"); ok = False
    if ok:
        print("✓ PC-Kennung: leer → gesetzt, zweiter Wert bleibt aussen vor, kaputte Datei → null, Format pc-[a-z0-9]{4,12}")
    return ok


def test_lese_instanz():
    """Echo V2 ohne Copier (25.09.2026, PC von ID A pc-aaaaaa: zwei Echo-V2-Trades ohne Live-P&L, weil ohne
    Copier niemand Balance/Equity schrieb): das Panel liest die Snapshot-Datei selbst. Frisch → Master-
    Felder + lesen, alive bleibt falsch; alt, fremdes Konto, halb geschrieben oder fehlend → nichts;
    läuft der Copier, gewinnt sein Status unverändert."""
    import panel, tempfile, time, json as _j
    from datetime import datetime
    ok = True
    d = tempfile.mkdtemp()
    cfg = {"snapshot_file": "prophos_m1.csv", "common_files_dir": d, "master_expected_login": 10000002}
    pfad = os.path.join(d, "prophos_m1.csv")
    def schreiben(zeilen, alter_s=0):
        open(pfad, "w", encoding="ascii").write("\n".join(zeilen) + "\n")
        t = time.time() - alter_s
        os.utime(pfad, (t, t))
    voll = ["PROPHOS1;42;0;10000002;FundedNext-Server;2;1;50000.00;50123.45;USD;1",
            "P;777;NDX100;0;0.50;1;18000.5;0;18100.0", "END;42;1"]
    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ Lese-Instanz: " + name); ok = False
    schreiben(voll)
    st = panel.lese_status(cfg)
    chk("frische Datei liefert Master-Stand", bool(st) and st["lesen"] is True and st["note"] is None
        and st["master_balance"] == 50000.0 and st["master_equity"] == 50123.45 and st["master_currency"] == "USD"
        and st["master_login"] == 10000002 and len(st["master_positions"]) == 1
        and st["master_positions"][0]["volume"] == 0.5 and "hedge_balance" not in st and "running" not in st)
    schreiben(voll, alter_s=30)
    chk("30 s alte Datei ist kein Live-Stand", panel.lese_status(cfg) is None)
    schreiben(voll)
    chk("fremdes Konto verworfen", panel.lese_status(dict(cfg, master_expected_login=999)) is None)
    chk("ohne erwarteten Login angenommen", bool(panel.lese_status(dict(cfg, master_expected_login=None))))
    schreiben(voll[:2])
    chk("halb geschrieben (ohne END) verworfen", panel.lese_status(cfg) is None)
    schreiben(["PROPHOS1;7;0;10000002;S;2;0", "END;7;0"])
    st2 = panel.lese_status(cfg)
    chk("altes EA ohne Balance → None statt 0", bool(st2) and st2["master_balance"] is None and st2["master_equity"] is None)
    os.remove(pfad)
    chk("fehlende Datei → None", panel.lese_status(cfg) is None and panel.lese_status({}) is None)
    # snapshot(): ohne Copier lesen=True/alive=False, mit frischem Copier dessen Status
    here_alt, pf_alt = panel.HERE, panel.PLANS_FILE
    try:
        h = tempfile.mkdtemp()
        panel.HERE, panel.PLANS_FILE = h, os.path.join(h, "plans.json")
        _j.dump(dict(cfg, magic=770123), open(os.path.join(h, "config-50kfundednext.json"), "w"))
        schreiben(voll)
        i = panel.snapshot()["instances"][0]
        chk("snapshot ohne Copier: lesen, alive falsch, Equity da", i["lesen"] is True and i["alive"] is False
            and i["status"]["master_equity"] == 50123.45)
        _j.dump({"running": True, "updated_at": datetime.now().isoformat(), "master_equity": 1.0, "note": None},
                open(os.path.join(h, "status-50kfundednext.json"), "w"))
        i = panel.snapshot()["instances"][0]
        chk("snapshot mit Copier: dessen Status, lesen falsch", i["alive"] is True and i["lesen"] is False
            and i["status"]["master_equity"] == 1.0)
    finally:
        panel.HERE, panel.PLANS_FILE = here_alt, pf_alt
    if ok:
        print("✓ Lese-Instanz: frisch → Master-Stand (alive bleibt falsch), alt/fremd/halb/fehlend → nichts, Copier gewinnt")
    return ok


def test_endlesung_bausteine():
    """Endlesung-Zusaetze im Bot (25.09.2026): Order-Historie lesen (EN/DE), Exit-/Einstiegs-Fill waehlen,
    Zeitformate, kompakter Befund <= 2 kB, Ende-Modus ohne Absturz beim Befehls-Fehler."""
    import order_bot as ob, io, contextlib, json as _j
    ok = True

    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ Endlesung: " + name); ok = False

    def zelle(n, x, y, w=50, typ="Text"):
        return (n, (x, y, x + w, y + 16), typ)
    en = [zelle("Positions", 10, 500, 60, "TabItem"), zelle("Orders", 80, 500, 50, "TabItem"),
          zelle("Symbol", 10, 535), zelle("Side", 120, 535), zelle("Type", 180, 535), zelle("Qty", 240, 535),
          zelle("Filled Qty", 300, 535, 70), zelle("Avg Fill Price", 380, 535, 90), zelle("Status", 480, 535),
          zelle("Placing Time", 560, 535, 90), zelle("Update Time", 680, 535, 90)]
    def zeile(y, sym, seite, typ, q, fq, preis, status, t_pl, t_up):
        return [zelle(sym, 10, y), zelle(seite, 120, y), zelle(typ, 180, y), zelle(q, 240, y), zelle(fq, 300, y),
                zelle(preis, 380, y, 90), zelle(status, 480, y), zelle(t_pl, 560, y, 110), zelle(t_up, 680, y, 110)]
    en += zeile(565, "MNQZ6", "Sell", "Market", "2", "2", "30,812.25", "Filled", "2026-09-25 01:11:13", "2026-09-25 01:11:14")
    en += zeile(590, "MNQZ6", "Buy", "Market", "2", "2", "30,745.00", "Filled", "2026-09-25 00:09:20", "2026-09-25 00:09:21")
    en += zeile(615, "NQZ6", "Sell", "Limit", "1", "0", "", "Cancelled", "2026-09-24 10:00:00", "2026-09-24 10:05:00")
    en += zeile(640, "MNQZ6", "Sell", "Limit", "2", "0", "", "Working", "2026-09-25 02:00:00", "2026-09-25 02:00:00")
    en += zeile(665, "MNQZ6", "Sell", "Market", "2", "2", "30,500.00", "Filled", "2026-09-24 01:00:00", "2026-09-24 01:00:01")
    tab = en[1][1]
    kopf = ob.tv_tabelle_kopf_unter(en, tab)
    chk("Kopf unter dem Reiter", bool(kopf) and kopf[0][1] == 535)
    sp = ob.tv_orders_spalten(en, kopf)
    namen = {b[0] for b in sp["baender"] if b[0]}
    chk("Spalten benannt (EN)", {"symbol", "seite", "typ", "menge", "menge_gef", "preis", "status", "zeit"} <= namen)
    chk("Zeit = Update Time", any(b[0] == "zeit" and b[3][0] == 680 for b in sp["baender"]))
    zl = ob.tv_orders_lesen(en, kopf)
    chk("5 Zeilen gelesen", len(zl) == 5 and zl[0]["preis"] == "30,812.25" and zl[0]["status"] == "Filled")
    w = ob.tv_fill_waehlen(zl, "MNQZ6", "buy")
    chk("Exit juengster gefuellter Sell", w["exit"] and w["exit"]["preis"] == 30812.25 and w["exit"]["menge"] == 2
        and w["exit"]["zeit"] == "2026-09-25 01:11:14" and w["wahl"] == "zeit")
    chk("Einstieg juengster Buy davor", w["einstieg"] and w["einstieg"]["preis"] == 30745.0)
    chk("Working/Cancelled/andere Wurzel zaehlen nicht", w["kandidaten"] == 3)
    w2 = ob.tv_fill_waehlen(zl, "MNQZ6", "sell")
    chk("Sell-Plan: Exit ist der Buy", w2["exit"] and w2["exit"]["preis"] == 30745.0 and w2["einstieg"] and w2["einstieg"]["preis"] == 30500.0)
    chk("ohne Richtung nichts", ob.tv_fill_waehlen(zl, "MNQZ6", "")["exit"] is None)
    ohne_zeit = [dict(z, zeit=None) for z in zl]
    w3 = ob.tv_fill_waehlen(ohne_zeit, "MNQZ6", "buy")
    chk("ohne Zeiten: oberste Zeile, Einstieg darunter", w3["wahl"] == "oben" and w3["exit"]["preis"] == 30812.25 and w3["einstieg"]["preis"] == 30745.0)
    chk("nur Einstieg, kein Exit -> nichts", ob.tv_fill_waehlen([z for z in zl if z["seite"] == "Buy"], "MNQZ6", "buy")["exit"] is None)
    # Deutsch, ohne Status-Spalte (dann zaehlt die ausgefuehrte Menge)
    de = [zelle("Positionen", 10, 500, 70, "TabItem"), zelle("Historie", 90, 500, 60, "TabItem"),
          zelle("Symbol", 10, 535), zelle("Seite", 120, 535), zelle("Menge", 240, 535), zelle("Ausgeführte Menge", 300, 535, 70),
          zelle("Durchschn. Ausführungspreis", 380, 535, 90), zelle("Zeit", 560, 535)]
    de += [zelle("NQZ6", 10, 565), zelle("Verkauf", 120, 565), zelle("1", 240, 565), zelle("1", 300, 565), zelle("30.812,25", 380, 565, 90), zelle("25.09.2026 01:11:14", 560, 565, 120)]
    de += [zelle("NQZ6", 10, 590), zelle("Kauf", 120, 590), zelle("1", 240, 590), zelle("1", 300, 590), zelle("30.745,00", 380, 590, 90), zelle("25.09.2026 00:09:21", 560, 590, 120)]
    kd = ob.tv_tabelle_kopf_unter(de, de[1][1])
    wd = ob.tv_fill_waehlen(ob.tv_orders_lesen(de, kd), "NQZ6", "buy")
    chk("deutsch: Exit 30.812,25, Einstieg 30.745", wd["exit"] and wd["exit"]["preis"] == 30812.25 and wd["einstieg"]["preis"] == 30745.0
        and wd["exit"]["zeit"] == "2026-09-25 01:11:14")
    # Zeitformate
    zt = {"2026-09-25 01:11:14": "2026-09-25 01:11:14", "25.09.2026 01:11": "2026-09-25 01:11:00",
          "09/25/2026 1:11:14 PM": "2026-09-25 13:11:14", "Sep 25, 2026 01:11:14": "2026-09-25 01:11:14",
          "25 Sep": None, "": None, "01:11:14": None}
    chk("Zeitformate", all(ob.tv_zeit_lesen(k) == v for k, v in zt.items()))
    # Befund
    gross = en + [(f"Text {i} lang lang lang", (5 + i, 700 + i, 60 + i, 716 + i), "Text") for i in range(400)] \
        + [("Account Balance", (300, 470, 400, 486), "Text"), ("150,373.00", (410, 470, 480, 486), "Text"),
           ("FTDFYSLX150100000000", (20, 460, 200, 476), "Button")]
    bf = ob.tv_befund_kompakt(gross, (0, 0, 1600, 900), {"code": "tabelle_unklar", "konto": "FTDFYSLX150100000000"})
    groesse = len(_j.dumps(bf, ensure_ascii=False).encode("utf-8"))
    chk(f"Befund <= 2 kB ({groesse})", groesse <= 2000)
    chk("Befund traegt Reiter, Kopf, Konto, Code", any(x.startswith("Positions@") for x in bf["reiter"]) and bf["panel_kopf"]
        and "FTDFYSLX150100000000" in bf["konten"] and bf["code"] == "tabelle_unklar" and bf["fenster"] == [0, 0, 1600, 900])
    chk("Befund ohne Fenster/leer wirft nicht", isinstance(ob.tv_befund_kompakt([], None), dict))
    # Ende-Modus: Befehls-Fehler darf nicht an 'ende' scheitern (Befund-Versuch ohne Windows)
    puf = io.StringIO()
    with contextlib.redirect_stdout(puf):
        ob.modus_tvlesen({"ende": True})
    try:
        r = _j.loads(puf.getvalue().strip().splitlines()[-1])
    except Exception:
        r = {}
    chk("Ende-Modus Befehls-Fehler -> code befehl + befund", r.get("code") == "befehl" and isinstance(r.get("befund"), dict))
    puf = io.StringIO()
    with contextlib.redirect_stdout(puf):
        ob.modus_tvlesen({})
    try:
        r2 = _j.loads(puf.getvalue().strip().splitlines()[-1])
    except Exception:
        r2 = {}
    chk("ohne ende kein Befund (Rundgang unveraendert)", r2.get("code") == "befehl" and "befund" not in r2)
    if ok:
        print("✓ Endlesung: Order-Historie EN/DE, Exit/Einstieg nach Zeit oder Lage, Zeitformate, Befund <= 2 kB, Ende-Modus ohne Absturz")
    return ok


def test_profil_riegel():
    """Chrome-Profil-Riegel (26.09.2026, PC von ID B): Puls benutzt nur Fenster seines Profils, nie das
    Reader-Profil ('Terminal 1'), und startet Chrome immer mit --profile-directory seines Profils."""
    import order_bot as ob
    ok = True

    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ Profil-Riegel: " + name); ok = False

    ls = {"profile": {"info_cache": {"Default": {"name": "ID B"}, "Profile 1": {"name": "Terminal 1"}}}}
    prof = ob.chrome_profile_lesen(ls)
    chk("Local State lesen", prof == {"Default": "ID B", "Profile 1": "Terminal 1"})
    chk("Relaunch mit Anfuehrungszeichen", ob.chrome_profil_aus_relaunch(
        '"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --profile-directory="Profile 1"') == "Profile 1")
    chk("Relaunch ohne Anfuehrungszeichen", ob.chrome_profil_aus_relaunch("chrome.exe --profile-directory=Default") == "Default")
    chk("Relaunch ohne Schalter", ob.chrome_profil_aus_relaunch("chrome.exe") == "")
    chk("AppID mit Profil-Endung", ob.chrome_profil_aus_appid("Chrome.Profile1", list(prof)) == "Profile 1")
    chk("AppID Standardprofil bleibt unbekannt", ob.chrome_profil_aus_appid("Chrome", list(prof)) == "")
    chk("Aufloesen per Anzeigename", ob.chrome_profil_aufloesen("terminal 1", prof) == "Profile 1")
    chk("Aufloesen per Verzeichnis", ob.chrome_profil_aufloesen("profile 1", prof) == "Profile 1")
    chk("Aufloesen unbekannt", ob.chrome_profil_aufloesen("Finn", prof) == "")

    # ID B: nichts eingetragen -> Default ist Puls-Profil, Terminal 1 gesperrt
    r = ob.puls_profil_regel(prof)
    chk("ohne Config eigen = Default", r["eigen"] == "Default" and not r["fehler"])
    chk("Reader-Profil gesperrt", not ob.profil_erlaubt("Profile 1", r))
    chk("eigenes Profil erlaubt", ob.profil_erlaubt("Default", r))
    chk("unbekanntes Fenster erlaubt (wie bisher)", ob.profil_erlaubt("", r))
    # Config per Anzeigename + ausdrueckliches Reader-Profil
    r = ob.puls_profil_regel(prof, eigen="ID B", tabu="Terminal 1")
    chk("Config per Anzeigename", r["eigen"] == "Default" and r["tabu"] == {"Profile 1"} and not r["fehler"])
    # Puls-Profil = Reader-Profil -> nie arbeiten, Fehler
    r = ob.puls_profil_regel(prof, eigen="Terminal 1", tabu="Terminal 1")
    chk("eigen == tabu -> Fehler, kein Profil", r["eigen"] == "" and r["fehler"]
        and not ob.profil_erlaubt("Profile 1", r) and not ob.profil_erlaubt("Default", r))
    # Puls bewusst im zweiten Profil
    r = ob.puls_profil_regel(prof, eigen="Profile 1")
    chk("eigen Profile 1 -> Default gesperrt", r["eigen"] == "Profile 1" and not ob.profil_erlaubt("Default", r))
    # Ein Profil (Finns PC): alles wie bisher
    r = ob.puls_profil_regel({"Default": "Person 1"})
    chk("ein Profil: erlaubt", r["eigen"] == "Default" and not r["mehrere"] and ob.profil_erlaubt("Default", r))
    # Mehrere ohne Default und ohne Config -> Fehler, sicher erkannte Profile gesperrt
    r = ob.puls_profil_regel({"Profile 1": "A", "Profile 2": "B"})
    chk("mehrere ohne Default -> Fehler", r["fehler"] and not ob.profil_erlaubt("Profile 1", r))
    # Kein Local State lesbar -> Config-Wert wie bisher, nichts gesperrt
    r = ob.puls_profil_regel({}, eigen="Profile 3")
    chk("ohne Local State Config wie bisher", r["eigen"] == "Profile 3" and ob.profil_erlaubt("Profile 9", r))
    chk("unbekanntes tv_reader_profil -> Fehler", ob.puls_profil_regel(prof, tabu="Reader X")["fehler"])

    # Start-Profil: Default statt 'zuletzt benutzt'
    alt = (ob._PROFIL_REGEL, ob._PROFIL_NAMEN)
    try:
        ob._PROFIL_REGEL, ob._PROFIL_NAMEN = ob.puls_profil_regel(prof), prof
        p, f = ob.puls_start_profil({})
        chk("Start im Default", p == "Default" and not f)
        chk("Startbefehl traegt Profil", "--profile-directory=Default" in ob.tv_start_befehl("chrome.exe", "", p))
        ob._PROFIL_REGEL = ob.puls_profil_regel(prof, eigen="Terminal 1", tabu="Terminal 1")
        p, f = ob.puls_start_profil({})
        chk("kein Start bei unklarem Profil", p == "" and f)
        ob._PROFIL_REGEL, ob._PROFIL_NAMEN = ob.puls_profil_regel({}), {}
        p, f = ob.puls_start_profil({"tv_chrome_profil": ""})
        chk("ohne Local State Start wie bisher", p == "" and not f)
        # Fenster-Sperre: gelesene Profile vorgeben (ohne Windows)
        ob._PROFIL_REGEL, ob._PROFIL_NAMEN = ob.puls_profil_regel(prof), prof
        ob._FENSTER_PROFIL.update({111: "Profile 1", 222: "Default", 333: ""})
        chk("Reader-Fenster gesperrt mit Namen", ob._fenster_gesperrt(111) == "Terminal 1 (Profile 1)")
        chk("ID B-Fenster frei", ob._fenster_gesperrt(222) == "" and ob._fenster_gesperrt(333) == "")
    finally:
        ob._PROFIL_REGEL, ob._PROFIL_NAMEN = alt
        for h in (111, 222, 333):
            ob._FENSTER_PROFIL.pop(h, None)
    if ok:
        print("✓ Profil-Riegel: Reader-Profil gesperrt, Default/Config-Profil frei, Start immer mit --profile-directory, ein Profil wie bisher")
    return ok


def test_fenster_treue():
    """Fenster-Treue (26.09.2026, B6): ein Puls-Fenster je PC, nie raten, Reader-Fenster raus, Tab statt Fenster."""
    import order_bot as ob
    ok = True

    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ Fenster-Treue: " + name); ok = False

    w = ob.puls_fenster_wahl
    chk("kein Browser-Fenster → kein_chrome", w([])[:2] == (None, "kein_chrome"))
    chk("Reader raus, Handels-Fenster mit TV → das", w([{"handle": 1, "aus": "Reader-/Fremdprofil Terminal 1", "tv": True},
                                                         {"handle": 2, "aus": "", "tv": True}])[:2] == (2, "neu"))
    chk("TV-Fenster vor Fenster ohne TV", w([{"handle": 1, "aus": "", "tv": False}, {"handle": 2, "aus": "", "tv": True}])[:2] == (2, "neu"))
    chk("zwei TV-Fenster → unklar, nicht raten", w([{"handle": 1, "aus": "", "tv": True}, {"handle": 2, "aus": "", "tv": True}])[:2] == (None, "unklar"))
    chk("ein Fenster ohne TV → das (neuer Tab kommt hinein)", w([{"handle": 5, "aus": "", "tv": False}])[:2] == (5, "neu"))
    chk("zwei ohne TV → unklar", w([{"handle": 1, "aus": "", "tv": False}, {"handle": 2, "aus": "", "tv": False}])[:2] == (None, "unklar"))
    zwei_tv = [{"handle": 1, "aus": "", "tv": True}, {"handle": 2, "aus": "", "tv": True}, {"handle": 3, "aus": "", "tv": False},
               {"handle": 9, "aus": "Reader-/Fremdprofil Terminal 1", "tv": True}]
    chk("unklar + Handels-Chrome vorn → das vordere", w(zwei_tv, vorn=2)[:2] == (2, "neu"))
    chk("vorn ist Fenster ohne TV oder Reader → bleibt unklar", w(zwei_tv, vorn=3)[:2] == (None, "unklar") and w(zwei_tv, vorn=9)[:2] == (None, "unklar"))
    chk("zwei ohne TV, eins vorn → das vordere", w([{"handle": 1, "aus": "", "tv": False}, {"handle": 2, "aus": "", "tv": False}], vorn=1)[:2] == (1, "neu"))
    chk("nur ausgeschlossene (Reader läuft, Handels-Chrome zu) → unklar, KEIN Chrome-Start",
        w([{"handle": 1, "aus": "Lage = Feed-Tab des Readers", "tv": True}])[:2] == (None, "unklar"))

    g = ob.puls_fenster_gueltig
    merk = {"hwnd": 10, "pid": 777, "profil": "Default"}
    chk("gemerktes Fenster lebt", g(merk, {"da": True, "klasse": "Chrome_WidgetWin_1", "pid": 777, "profil": "Default"}))
    chk("Chrome neu gestartet (andere pid) → ungültig", not g(merk, {"da": True, "klasse": "Chrome_WidgetWin_1", "pid": 778}))
    chk("Fenster weg → ungültig", not g(merk, {"da": False}))
    chk("anderes Profil → ungültig", not g(merk, {"da": True, "klasse": "Chrome_WidgetWin_1", "pid": 777, "profil": "Profile 1"}))
    chk("Profil unlesbar → pid entscheidet", g(merk, {"da": True, "klasse": "Chrome_WidgetWin_1", "pid": 777, "profil": ""}))

    rg = ob.reader_geo_passt
    geo = {"screenX": 100, "screenY": 50, "outerWidth": 1200, "outerHeight": 800, "dpr": 1.25}
    chk("Reader-Lage bei 125 % erkannt", rg((125, 62, 1625, 1062), geo))
    chk("Reader-Lage bei 100 % (dpr 1) erkannt", rg((100, 50, 1300, 850), dict(geo, dpr=1)))
    chk("anderes Fenster nicht", not rg((0, 0, 1920, 1040), geo) and not rg((125, 62, 1625, 1062), None))

    la = ob.lage_ausschluss
    # ID B 28.09.2026: beide Fenster maximiert (gleiche Lage), Reader in Profile 2 → eigenes Profile 1 bleibt erlaubt
    chk("deckungsgleich, Reader-Profil erklärt die Lage → eigenes Fenster erlaubt",
        la([{"profil": "Profile 1", "lage": True}, {"profil": "Profile 2", "lage": True}], "Profile 1", {"Profile 2"}) == {1})
    chk("kein Tabu-Fenster an der Stelle → Lage sperrt auch das eigene",
        la([{"profil": "Profile 1", "lage": True}], "Profile 1", {"Profile 2"}) == {0})
    chk("Profil unlesbar → Lage sperrt wie bisher",
        la([{"profil": "", "lage": True}, {"profil": "Profile 2", "lage": True}], "Profile 1", {"Profile 2"}) == {0, 1})
    chk("ohne eigenes Profil keine Ausnahme",
        la([{"profil": "Profile 1", "lage": True}, {"profil": "Profile 2", "lage": True}], "", {"Profile 2"}) == {0, 1})
    chk("andere Lage bleibt drin", la([{"profil": "Profile 1", "lage": False}], "Profile 1", set()) == set())

    fp = ob.fremdes_popup_urteil
    fen = (0, 0, 1920, 1040)
    kasten, x_oben_rechts = (440, 230, 1725, 1040), (1655, 250, 1705, 300)
    chk("Autumn-Sale-Werbung (ID B 28.09.2026) → wegklicken",
        fp("Don't miss this · Autumn sale · Up to 80% off · Offer ends in · Explore offers · Close", kasten, x_oben_rechts, fen)[0])
    chk("Order-Ticket mit X → nie anfassen",
        not fp("Buy · Sell · Market · Limit · Quantity · Take Profit · Stop Loss · Close", kasten, x_oben_rechts, fen)[0])
    chk("Broker-Connect-Dialog → nie anfassen", not fp("Tradovate · Live · Demo · Connect · Close", kasten, x_oben_rechts, fen)[0])
    chk("Upgrade-Werbung ohne Ticket-Wörter → wegklicken", fp("Upgrade to Premium · Start free trial · Close", kasten, x_oben_rechts, fen)[0])
    chk("unbekanntes Popup ohne Puls-Wörter → wegklicken", fp("What's new in TradingView · Got it · Close", kasten, x_oben_rechts, fen)[0])
    chk("X nicht oben rechts → nicht", not fp("Autumn sale · 80% off", kasten, (500, 900, 540, 940), fen)[0])
    chk("kleiner Kasten (Toast) → nicht", not fp("Autumn sale · 80% off", (1500, 900, 1700, 980), (1680, 905, 1695, 920), fen)[0])
    chk("Kasten = ganze Seite → nicht", not fp("Autumn sale · 80% off", fen, (1880, 5, 1915, 30), fen)[0])
    # 29.09.2026 (ID F pc-bbbbbb): namenloses X, Sperrwörter, Chrome-Leiste, Esc nur bei starker Werbung
    x_klein = (1675, 250, 1705, 280)
    werbung = "Don't miss this · Autumn sale · Up to 80% off · Offer ends in · Explore offers"
    chk("namenloses X im Werbe-Dialog → wegklicken", fp(werbung, kasten, x_klein, fen, knopf_name="")[0])
    chk("'×' im Werbe-Dialog → wegklicken", fp(werbung, kasten, x_klein, fen, knopf_name="×")[0])
    chk("namenloses X ohne Werbung → nie", not fp("What's new in TradingView · Got it", kasten, x_klein, fen, knopf_name="")[0])
    chk("namenloser Knopf zu groß für ein X → nie", not fp(werbung, kasten, (1600, 240, 1705, 300), fen, knopf_name="")[0])
    chk("Knopf 'Explore offers' → nie", not fp(werbung, kasten, x_klein, fen, knopf_name="Explore offers")[0])
    chk("namenloses X im Ticket mit Werbe-Wort → nie", not fp("Take Profit · 80% off · Sale", kasten, x_klein, fen, knopf_name="")[0])
    chk("X in Chromes Tab-Leiste → nie", not fp(werbung, (440, 0, 1725, 1040), (1675, 20, 1705, 50), fen, knopf_name="close")[0])
    wt = ob.tv_werbe_texte
    chk("Kopfleiste 'Upgrade'/'Explore offers' allein → kein Werbe-Dialog (kein Esc)", wt(["Upgrade", "Explore offers", "Premium"]) == [])
    chk("Autumn-Sale-Dialog → Werbe-Dialog erkannt", len(wt(["Don't miss this", "Autumn sale", "Up to 80% off", "Offer ends in"])) >= 2)
    chk("ein einzelnes Werbe-Merkmal → kein Esc", wt(["Autumn sale", "Chart", "NQ1!"]) == [])
    import inspect as _insp
    q_k = _insp.getsource(ob)
    chk("Konto-Schritt: vor dem Neu-Verbinden Popup-Check + zweiter Blick", "kein Broker nach Popup-Check" in q_k and "Konto nach Popup-Check" in q_k)
    import inspect
    q_w = inspect.getsource(ob._tv_tab_neu_mit_link)
    chk("Strg+W nur, wenn das Vordergrund-Fenster das Puls-Fenster ist", "_vorn_h != int(w.handle)" in q_w)

    tp = ob.tab_neu_plan
    chk("≥ 2 Tabs: schließen, neuer Tab", tp(3) == ["schliessen", "neuer_tab", "adresse"])
    chk("1 Tab: erst neuer Tab, dann Tab 1 schließen (Fenster bleibt)", tp(1) == ["neuer_tab", "tab_1", "schliessen", "adresse"])
    chk("Tabs unlesbar → nichts schließen", tp(0) is None and tp(None) is None)
    import inspect
    quelle = inspect.getsource(ob._tv_tab_neu_mit_link) + inspect.getsource(ob._tv_neuer_tab)
    chk("kein chrome.exe-Start und kein Strg+N beim Tab-Neuöffnen", "Popen" not in quelle and "^n" not in quelle)
    if ok:
        print("✓ Fenster-Treue: Wahl eindeutig oder abbrechen, Reader per Profil/Lage raus, gemerktes Fenster geprüft, Tab statt Fenster")
    return ok


def test_puls_tempo():
    """Puls-Tempo (27.09.2026, B13): Connect-Dialog sofort erkennen, 'Network error occurred' erkennen, kuerzere Timeouts."""
    import order_bot as ob, inspect
    ok = True

    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ Puls-Tempo: " + name); ok = False

    r = (0, 0, 80, 20)
    dialog = [("Tradovate GOLD", r, "Text"), ("Live", r, "RadioButton"), ("Demo", r, "RadioButton"),
              ("Don't remember me", r, "CheckBox"), ("Connect", r, "Button")]
    chk("Dialog sichtbar (Demo + Connect)", ob.tv_connect_dialog_sichtbar(dialog))
    chk("nur Connect oder nur Demo → kein Dialog", not ob.tv_connect_dialog_sichtbar(dialog[:3])
        and not ob.tv_connect_dialog_sichtbar([("Connect", r, "Button")]))
    chk("unsichtbare Elemente (rect None) zaehlen nicht", not ob.tv_connect_dialog_sichtbar([("Demo", None, "RadioButton"), ("Connect", None, "Button")]))
    chk("'Broker verbinden' (deutsch) zaehlt als Connect", ob.tv_connect_dialog_sichtbar([("Demo", r, "RadioButton"), ("Broker verbinden", r, "Button")]))
    fehler = dialog + [("Error! Network error occurred. Please check your internet connection and try to connect again.", r, "Text")]
    chk("'Network error occurred' erkannt", ob.tv_netzfehler_sichtbar(fehler) and not ob.tv_netzfehler_sichtbar(dialog)
        and not ob.tv_netzfehler_sichtbar([("Network error occurred", None, "Text")]))
    chk("hoechstens 3 Neu-Versuche", ob.TV_CONNECT_NETZ_MAX == 3)
    q = inspect.getsource(ob.modus_tvkonto) if hasattr(ob, "modus_tvkonto") else ""
    chk("Login-Klick: 1,5 s statt 4 s vor dem Enter", "warte_weg(1.5)" in q and "weg = warte_weg(4.0)\n                if not weg and tradovate_noch_da():\n                    trail.append(\"Login-Klick" not in q)
    chk("Netzfehler-Zweig klickt Connect erneut", "Connect (erneut" in q and "tv_netzfehler_sichtbar" in q)
    chk("Link-Start bricht das Lesen ab, wenn der Dialog steht", "Connect-Dialog steht schon da" in q)
    chk("Avg Fill wartet 1,2 s statt 3 s", "_avg_fill_nachlauf(sekunden=1.2)" in inspect.getsource(ob))
    if ok:
        print("✓ Puls-Tempo: Dialog sofort, Network error → Connect erneut (max. 3), Login-Enter nach 1,5 s, Avg Fill 1,2 s")
    return ok


def test_puls_augen_cdp():
    """Puls-Augen über CDP (29.09.2026, E0): eigenes Profil, nur 127.0.0.1:9333, WebSocket-Frames, Regel, Target-Wahl."""
    import order_bot as ob
    ok = True

    def chk(bed, text):
        nonlocal ok
        if not bed:
            print("  ✗ " + text)
            ok = False
    prof = ob.puls_chrome_profil_pfad("C:\\Users\\m\\AppData\\Local")
    arg = ob.puls_chrome_argumente("chrome.exe", prof)
    chk(any(a.startswith("--user-data-dir=") and "puls-chrome" in a for a in arg), "eigenes --user-data-dir puls-chrome")
    chk("--remote-debugging-port=9333" in arg and "--remote-debugging-address=127.0.0.1" in arg, "Port 9333 nur 127.0.0.1")
    chk(not any(a.startswith("--profile-directory") for a in arg), "nie --profile-directory")
    for falsch in ("C:\\Users\\m\\AppData\\Local\\Google\\Chrome\\User Data", "", "C:\\x\\puls-chromeX"):
        try:
            ob.puls_chrome_argumente("chrome.exe", falsch)
            chk(False, f"Standard-/fremdes Profil muss abbrechen: '{falsch}'")
        except ValueError:
            pass
    for n in (0, 5, 125, 126, 300, 65535, 65536, 70000):
        d = bytes(range(256)) * (n // 256) + bytes(range(n % 256))
        f = ob.ws_frame_bauen(d, 0x1, maske=b"\x01\x02\x03\x04")
        r = ob.ws_frame_lesen(f + b"REST")
        chk(r is not None and r[0] and r[1] == 1 and r[2] == d and r[3] == b"REST", f"WebSocket-Frame hin und zurück ({n} Bytes)")
        chk(ob.ws_frame_lesen(f[:-1]) is None, f"unvollständiger Frame ({n} Bytes) → None")
    chk(ob.cdp_ws_url_pruefen("ws://127.0.0.1:9333/devtools/page/ABC-1") == ("127.0.0.1", 9333, "/devtools/page/ABC-1"), "eigene CDP-Adresse ok")
    chk(ob.cdp_ws_url_pruefen("ws://10.0.0.5:9333/devtools/page/X") is None, "fremder Host abgelehnt")
    chk(ob.cdp_ws_url_pruefen("ws://127.0.0.1:9222/devtools/page/X") is None, "fremder Port abgelehnt")
    e = ob.augen_regel_entscheid
    chk(e(None, 1000.0) and e({"augen": "cdp", "at": 990}, 1000.0), "Regel fehlt/cdp → anstoßen")
    chk(not e({"augen": "uia", "at": 990}, 1000.0), "Regel uia frisch → nicht anstoßen")
    chk(e({"augen": "uia", "at": 0}, 1000.0), "Regel uia veraltet → anstoßen (Neu-Holen)")
    w = ob.augen_target_waehlen
    chk(w([{"type": "page", "url": "https://www.tradingview.com/", "id": "a"},
           {"type": "page", "url": "https://www.tradingview.com/chart/x/", "id": "b"},
           {"type": "service_worker", "url": "https://www.tradingview.com/chart/", "id": "c"}])["id"] == "b", "Chart-Seite gewinnt, nur type page")
    chk(w([{"type": "page", "url": "https://evil.example/tradingview.com/chart"}]) is None, "fremde Domain nie")
    fp = ob.fenster_ist_puls_chrome
    rl = '"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --user-data-dir="C:\\Users\\m\\AppData\\Local\\Prophos\\puls-chrome" --profile-directory=Default'
    chk(fp(100, 100, "") and not fp(100, 200, ""), "Puls-Chrome-Fenster per Browser-PID erkannt")
    chk(fp(1, None, rl) and fp(1, None, "chrome.exe --user-data-dir=C:\\x\\Prophos\\puls-chrome"), "Puls-Chrome-Fenster per Relaunch-Befehl erkannt")
    chk(not fp(1, None, 'chrome.exe --profile-directory="Profile 2"') and not fp(1, None, "--user-data-dir=C:\\x\\puls-chromeX"),
        "normales Chrome / ähnlicher Ordner nie als Puls-Chrome")
    import inspect as _i2
    chk("Puls-Chrome (CDP)" in _i2.getsource(ob._fenster_gesperrt), "Fenster-Wahl sperrt das Puls-Chrome")
    chk("Browser.close" in _i2.getsource(ob.modus_augen), "Regel 'uia' schließt das Puls-Chrome (Browser.close)")
    kf = ob.augen_kurzform
    st = {"ticket": {"da": True, "typ": "Market", "menge": {"wert": "4"}, "tp": {"feld": {"wert": "447.00"}}, "sl": {"feld": {"wert": "249.00"}}},
          "kauf_knopf": {"text": "Buy 4 MNQZ6 MARKET"}, "toasts": {"log": [], "gruppen": []}, "popups": []}
    chk(kf(st) == "Ticket offen · Market · Units 4 · TP 447.00 · SL 249.00 · Knopf 'Buy 4 MNQZ6 MARKET' · Toasts 0 · Popups 0",
        "Augen-Kurzform aus echter Zeile (ID B 29.09.2026): ticket.da, toasts {log, gruppen}")
    chk(kf({"toasts": {"gruppen": [1, 2], "log": [3]}}).endswith("Toasts 3 · Popups 0") and kf(None) == "kein Stand", "Kurzform zählt Toast-Einträge")
    # K1 (29.09.2026): Weiche nur lokal + nur dieser PC; Klick-Bahn/-Punkt; Summary/Positionen in Vertragsform
    import random as _rnd
    wch = ob.augen_regel_weiche
    chk(wch({"augen": "cdp", "at": 990.0, "pc": "pc-cccccc"}, 1000.0, "pc-cccccc") == "cdp", "Weiche: cdp frisch + eigener PC → cdp")
    chk(wch({"augen": "cdp", "at": 990.0, "pc": "pc-cccccc"}, 1000.0, "pc-iiiiii") == "uia", "Weiche: Regel eines anderen PCs → uia")
    chk(wch({"augen": "cdp", "at": 0.0}, 50000.0, "pc-cccccc") == "uia" and wch({"augen": "cdp", "at": 0.0}, 3 * 3600.0, "pc-cccccc") == "cdp"
        and wch(None, 1000.0, "pc-cccccc") == "uia"
        and wch({"augen": "uia", "at": 999.0}, 1000.0, "pc-cccccc") == "uia" and wch({"augen": "cdp", "at": 999.0}, 1000.0, None) == "uia",
        "Weiche: veraltet/fehlt/uia/ohne pc_id → uia (alter Pfad unverändert)")
    import inspect as _i3
    q_tl = _i3.getsource(ob.modus_tvlesen)
    chk(q_tl.lstrip().startswith("def modus_tvlesen(cmd):\n    if augen_modus_lauf() == \"cdp\":") and ("modus_tvlesen_cdp(cmd)" in q_tl or "tvlesen_cdp_mit_wiederholung(cmd)" in q_tl),
        "tvlesen: einzige Änderung vor dem alten Pfad ist die lokale Weiche")
    chk("urllib" not in _i3.getsource(ob.augen_modus_lauf) and "augen_regel_entscheid(rd" in _i3.getsource(ob.augen_modus_lauf),
        "Weiche: Netz nur über _augen_regel_holen und nur bei fehlender/alter Regel (seit 01.10.2026)")
    r_ = _rnd.Random(7)
    bahn = ob.cdp_klick_bahn((0, 0), (100, 50), rnd=r_)
    chk(len(bahn) == 8 and bahn[-1] == (100.0, 50.0) and bahn[0] != (100.0, 50.0), "Klick-Bahn: mehrere Schritte, letzter exakt am Ziel")
    # 30.09.2026, PC von ID C: Werbe-Modal („Autumn sale") über dem Connect-Dialog — werbung_weg klickt sein X, beweist das Verschwinden
    _ws = object.__new__(ob._AugenSitzung)
    _ws.trail, _ws._werbung_at = [], 0.0
    _werb = [[{"text": "Don't miss this Autumn sale Up to 80% off", "box": [200, 40, 900, 560], "x": [1050, 60, 30, 30]}], []]
    _ws.lese_js = lambda ausdruck, timeout=8: (_werb.pop(0) if _werb else []) if "MERKMALE" in ausdruck else None
    _ws._win_klick = lambda rect, name, druck=True, toast_ok=False: rect == [1050, 60, 30, 30]
    _alt_w = ob._warte
    ob._warte = lambda a, b: None
    try:
        _n = _ws.werbung_weg(zwang=True)
        _n2 = _ws.werbung_weg()            # innerhalb von 3 s: gedrosselt, kein Lesen
    finally:
        ob._warte = _alt_w
    chk(_n == 1 and _n2 == 0 and any("Werbung weg (bewiesen)" in z for z in _ws.trail), "werbung_weg: X geklickt, weg bewiesen, danach 3 s gedrosselt")
    pt = ob.cdp_klickpunkt([100, 200, 60, 30], rnd=_rnd.Random(3))
    chk(pt and 110 <= pt[0] <= 150 and 205 <= pt[1] <= 225 and ob.cdp_klickpunkt([1, 1, 1, 1]) is None, "Klickpunkt im inneren Drittel, Mini-Rect → None")
    sm = ob.cdp_summary({"balance": {"label": "Account Balance", "text": "153,756.96", "wert": 153756.96}, "equity": {"label": None, "text": "153,700.00"},
                         "today_pnl": {"label": "Total P/L", "text": "-56.96"}, "texte": {"Realized P&L": "0.00"}})
    chk(sm == {"Realized P&L": "0.00", "Account Balance": "153,756.96", "Equity": "153,700.00", "Total P/L": "-56.96"}
        and ob.cdp_summary(None) is None, "Summary → tvlesen-Form (Label: Text), Rückfall-Labels")
    pv = ob.cdp_positionen_vertrag([{"symbol": "MNQZ6", "seite": "buy", "menge": 4, "avg": 30594.25, "pl_text": "-12.50"}, "x"])
    chk(len(pv) == 1 and pv[0]["menge_zahl"] == 4 and pv[0]["einstieg_zahl"] == 30594.25 and pv[0]["pnl_zahl"] == -12.5
        and ob.tv_avg_fill_je_wurzel(pv)["MNQ"]["avg_fill"] == 30594.25, "Positionen → Vertragsform + avg_fill_je_wurzel")
    ke = ob.cdp_konto_eintrag([{"text": "TDFYSL150300000000 USD", "rect": [1, 1, 9, 9]}, {"text": "APEX0000000000025 USD", "rect": [1, 1, 9, 9]}], "TDFYSL150300000000")
    chk(ke[0] is not None and ke[1] == 1 and ob.cdp_konto_eintrag([], "X")[0] is None, "Konto-Eintrag: genau ein Treffer")
    # Aufnahme kompakt (29.09.2026: 119 Ereignisse scheiterten am 60-KB-Deckel der Route)
    z = {"tag": "button", "dn": "account-switch", "text": "TDFYSL150300000000 USD", "rect": [10, 20, 100, 30]}
    evs = [{"t": 100, "typ": "pointerdown", "ziel": z, "vorfahren": [{"tag": "div", "text": "x" * 300}] * 3},
           {"t": 105, "typ": "mousedown", "ziel": z}, {"t": 180, "typ": "click", "ziel": z},
           {"t": 900, "typ": "input", "ziel": {"tag": "input", "id": "quantity-field", "wert": "4"}, "wert": "4"}]
    k = ob.aufnahme_kompakt({"ereignisse": evs, "tab_id": "t1"})
    chk(k["zusammengefasst"] == 2 and k["ereignisse"][0]["typ"] == "klick" and k["ereignisse"][0]["typen"] == ["pointerdown", "mousedown", "click"]
        and len(k["ereignisse"][0]["vorfahren"]) == 2 and len(k["ereignisse"][0]["vorfahren"][0]["text"]) == 40 and k["ereignisse"][1]["wert"] == "4",
        "Aufnahme kompakt: Klick-Kette auf demselben Ziel = 1 Eintrag, 2 Vorfahren, Texte gekürzt")
    gross = {"ereignisse": [{"t": i, "typ": "input", "ziel": {"tag": "div", "text": "y" * 400, "rect": [i, i, 5, 5]},
                             "vorfahren": [{"text": "z" * 400}] * 3} for i in range(3000)]}
    kg = ob.aufnahme_kompakt(gross)
    import json as _js
    chk(len(_js.dumps(kg, ensure_ascii=False)) <= ob.AUFNAHME_KOMPAKT_MAX and kg.get("abgeschnitten", 0) > 0, "Aufnahme kompakt bleibt unter dem Deckel")
    # K4 (29.09.2026 abends, Finn: „den letzten Button unten drücken"): genau EIN Senden-Klick, nur scharf, gesendet VORHER True
    q_k2 = _i3.getsource(ob.modus_tvkette_cdp)
    chk(q_k2.count('"SENDEN-Knopf"') == 1 and "dispatchMouseEvent" not in q_k2
        and q_k2.index("scharf = tv_ist_scharf(cmd)") < q_k2.index("if not scharf:") < q_k2.index('"SENDEN-Knopf"')
        and q_k2.index('res["gesendet"], res["retry_ok"] = True, False') < q_k2.index('"SENDEN-Knopf"')
        and q_k2.index("cdp_ticket_ruecklesung(st, plan)") < q_k2.index('"SENDEN-Knopf"')
        and q_k2.index("k3_knopf_exakt(") < q_k2.index('"SENDEN-Knopf"') and q_k2.index('st.get("popups")') < q_k2.index('"SENDEN-Knopf"'),
        "K4: EIN Senden-Klick nur scharf, nach Rücklesung + exaktem Knopf-Text + ohne Popup, gesendet/retry_ok vorher gesetzt")
    q_tk = _i3.getsource(ob.modus_tvkette)
    chk("if augen_modus_lauf() == \"cdp\":" in q_tk and q_tk.index("augen_modus_lauf") < q_tk.index("modus_tvkonto(cmd)"),
        "tvkonto: CDP-Weiche vor dem alten Pfad, sonst unverändert")
    chk(ob.cdp_watchlist_ziel([{"symbol": "NQZ2026", "rect": [1, 1, 9, 9]}, {"symbol": "MNQZ2026", "rect": [1, 20, 9, 9]}], "MNQZ6")["symbol"] == "MNQZ2026"
        and ob.cdp_watchlist_ziel([{"symbol": "NQZ2026", "rect": [1, 1, 9, 9]}], "MNQZ6") is None, "Watchlist: MNQ nie NQ")
    chk(ob.cdp_ticket_typ_market([{"id": "Market", "aria-selected": "true", "rect": [1, 1, 5, 5]}])[1]
        and not ob.cdp_ticket_typ_market([{"id": "Market", "aria-selected": "false", "rect": [1, 1, 5, 5]}])[1], "Market-Reiter aktiv erkannt")
    chk(ob.cdp_zahl("1,050.00") == 1050.0 and ob.cdp_zahl(4) == 4.0 and ob.cdp_zahl(True) is None, "cdp_zahl")
    if ok:
        print("✓ Puls-Augen CDP: eigenes Profil, 127.0.0.1:9333, WebSocket-Frames, Regel-Entscheid, Target-Wahl, K1-Weiche + Vertrag")
    return ok


def test_puls_k3():
    """K3 scharfer Handlauf (29.09.2026, Finns Anweisung an T3): Knopf-Text exakt, Meldungen/Zeilen/Close-Knopf eindeutig,
    Sperre, Login-Blick liefert nie Feldwerte, nur Hand-Befehl führt zu modus_k3."""
    import order_bot as ob
    import inspect as _i
    import re as _re
    ok = True

    def chk(bed, text):
        nonlocal ok
        if not bed:
            print("  ✗ K3: " + text)
            ok = False
    ke = ob.k3_knopf_exakt
    chk(ke("Buy 1 MNQZ6 MARKET", "buy", 1, "MNQZ6") and ke("  Buy 1  MNQZ6 MARKET ", "buy", 1, "mnqz6"), "Knopf exakt (Leerraum egal)")
    chk(not ke("Buy 10 MNQZ6 MARKET", "buy", 1, "MNQZ6") and not ke("Sell 1 MNQZ6 MARKET", "buy", 1, "MNQZ6")
        and not ke("Buy 1 NQZ6 MARKET", "buy", 1, "MNQZ6") and not ke("Buy 1 MNQZ6 LIMIT", "buy", 1, "MNQZ6")
        and not ke("Buy 1 MNQZ6 MARKET x", "buy", 1, "MNQZ6") and not ke("", "buy", 1, "MNQZ6"), "Knopf: jede Abweichung = nein")
    # Meldungen im augen.js-Format (toasts.meldungen)
    alt = {"art": "fill", "status": "ausgefuehrt", "seite": "sell", "menge": 1, "preis": 30401.0, "text": "alt"}
    fill = {"art": "fill", "status": "ausgefuehrt", "seite": "buy", "menge": 1, "preis": 30483.25, "text": "Buy 1 at 30,483.25"}
    tp = {"art": "tp", "status": "platziert", "seite": "sell", "menge": 1, "preis": 30533.25, "text": "Sell 1 at 30,533.25"}
    sl = {"art": "sl", "status": "platziert", "seite": "sell", "menge": 1, "preis": 30458.25, "text": "Sell 1 at 30,458.25"}
    vor = [ob.k3_meldung_schluessel(alt)]
    neu = ob.k3_neue_meldungen(vor, [alt, fill, tp, sl, dict(fill)])
    chk(len(neu) == 3 and alt not in neu, "neue Meldungen: alte raus, Doppel einmal")
    om = ob.k3_order_meldungen(neu, "buy", 1)
    chk(om == {"fill": 30483.25, "tp": 30533.25, "sl": 30458.25}, f"Fill/TP/SL der eigenen Order ({om})")
    chk(ob.k3_order_meldungen([dict(fill, menge=2)], "buy", 1)["fill"] is None, "Fill mit anderer Menge zählt nicht")
    storno = [{"art": "tp", "status": "storniert", "seite": "sell", "menge": 1, "preis": 30533.25, "text": "a"},
              {"art": "sl", "status": "storniert", "seite": "sell", "menge": 1, "preis": 30458.25, "text": "b"},
              {"art": "fill", "status": "ausgefuehrt", "seite": "sell", "menge": 1, "preis": 30490.0, "text": "c"}]
    chk(ob.k3_close_meldungen(storno, "buy", 1) == (30490.0, {"tp", "sl"}), "Close-Fill Gegenseite + beide Beine storniert")
    pos = [{"symbol": "MNQZ2026", "sichtbar": True, "seite": "buy", "menge": 1}, {"symbol": "MNQZ2026", "sichtbar": False},
           {"symbol": "NQZ2026", "sichtbar": True}]
    chk(len(ob.k3_zeilen(pos, "MNQ")) == 1 and not ob.k3_zeilen(pos[1:2], "MNQ"), "nur sichtbare Zeilen der Wurzel (MNQ nie NQ)")
    ords = [{"symbol": "MNQZ2026", "sichtbar": True, "status": "Working"}, {"symbol": "MNQZ2026", "sichtbar": True, "status": "Filled"},
            {"symbol": "MNQZ2026", "sichtbar": True, "status": "Cancelled"}, {"symbol": "NQZ2026", "sichtbar": True, "status": "Working"}]
    chk(len(ob.k3_offene_orders(ords, "MNQ")) == 1, "offene Orders: nur Working der Wurzel")
    sm = {"Equity": "149,967.60", "Net Liq": "149967.60", "Open P/L": "0.00", "Total P/L": "0.00", "Account Balance": "149,967.60"}
    chk(ob.k3_summary_werte(sm) == (149967.6, 0.0) and ob.k3_summary_werte({"Account Balance": "150,012.10", "Total P/L": "-56.96"}) == (150012.1, -56.96)
        and ob.k3_summary_werte(None) == (None, None), "Summary: Account Balance + Total P/L (echte Lesung 01:30)")
    z = {"knoepfe": [{"aria": "Protect position", "rect": [800, 640, 24, 24]}, {"aria": "Reverse position", "rect": [830, 640, 24, 24]},
                     {"aria": "Close position", "rect": [860, 640, 24, 24]}]}
    k, n = ob.k3_close_knopf(z)
    chk(k and k["aria"] == "Close position" and n == 1, "Close-Knopf: genau der eine, nie Reverse/Protect")
    z2 = {"knoepfe": [{"title": "Close", "tag": "div", "rect": [855, 635, 34, 34]}, {"dn": "close-button", "tag": "button", "rect": [860, 640, 24, 24]}]}
    k2, n2 = ob.k3_close_knopf(z2)
    chk(k2 and k2["tag"] == "button" and n2 == 1, "Hülle + innerer Knopf = einer (innerer gewinnt)")
    chk(ob.k3_close_knopf({"knoepfe": [{"aria": "Close position", "rect": [1, 1, 20, 20]}, {"text": "×", "rect": [40, 1, 20, 20]}]})[0] is None
        and ob.k3_close_knopf({"knoepfe": []}) == (None, 0), "zwei Kandidaten / keiner = kein Knopf (Abbruch)")
    # echter Knopf aus dem ersten K3-Lauf (29.09.2026 13:14 UTC, pc-cccccc) — wurde vom „settings" im data-name verworfen
    echt = {"tag": "button", "text": "", "aria": "Close", "title": "Close", "dn": "close-settings-cell-button", "rect": [893, 649, 22, 22]}
    k4_, n4_ = ob.k3_close_knopf({"knoepfe": [echt]})
    chk(k4_ is echt and n4_ == 1, "echter Tradovate-Close-Knopf (data-name close-settings-cell-button) wird genommen")
    chk(ob.k3_close_knopf({"knoepfe": [{"aria": "Close", "title": "Position settings", "rect": [1, 1, 20, 20]}]})[0] is None
        and ob.k3_close_knopf({"knoepfe": [{"aria": "Reverse position", "dn": "close-reverse", "rect": [1, 1, 20, 20]}]})[0] is None,
        "sichtbare Beschriftung Settings/Reverse schließt weiter aus")
    menue = [{"text": "Trading settings", "rect": [100, 400, 180, 30]}, {"text": "Log out", "rect": [100, 430, 180, 30]}]
    chk(ob.k3_eindeutig(menue, ob.K3_RX_ABMELDEN)[0]["text"] == "Log out"
        and ob.k3_eindeutig([{"text": "Disconnect", "rect": [1, 1, 50, 20]}], ob.K3_RX_ABMELDEN)[0] is not None
        and ob.k3_eindeutig(menue[:1], ob.K3_RX_ABMELDEN) == (None, 0), "Kontextmenü: Log out/Disconnect eindeutig")
    kn = [{"text": "Connect", "rect": [10, 10, 80, 30]}, {"text": "Cancel", "rect": [100, 10, 80, 30]}]
    chk(ob.k3_eindeutig(kn, ob.K3_RX_CONNECT)[0]["text"] == "Connect"
        and ob.k3_eindeutig([dict(kn[0], aus=True)], ob.K3_RX_CONNECT) == (None, 0)
        and ob.k3_eindeutig([{"text": "Connect to Tradovate broker", "rect": [1, 1, 50, 20]}], ob.K3_RX_CONNECT)[0] is None, "Connect exakt, gesperrt zählt nicht")
    chk(ob.k3_kontonr({"text": "TDFYSL150001000000USD"}) == "TDFYSL150001000000" and ob.k3_kontonr({"kontonr": "APEX0000000000024"}) == "APEX0000000000024"
        and ob.K3_RX_TRADEIFY.match("FTDFYSLX150010000000") and ob.K3_RX_APEX.match("PAAPEX0000000000009")
        and not ob.K3_RX_TRADEIFY.match("APEX0000000000024"), "Kontonummern Tradeify/Apex")
    # echter Stand pc-cccccc 01:30 UTC (nach K2-Probelauf) — Rücklesung ok
    st = {"ticket": {"typen": [{"id": "Market", "aria-selected": "true", "rect": [952, 209, 68, 28]}], "seite": "buy",
                     "menge": {"wert": "1", "rect": [955, 278, 122, 28]},
                     "tp": {"an": True, "wert": 100, "einheit": "$", "neben": {"text": "30533.00price"}},
                     "sl": {"an": True, "wert": 50, "einheit": "$", "neben": {"text": "100ticks"}}},
          "kauf_knopf": {"text": "Buy 1 MNQZ6 MARKET", "seite": "buy", "disabled": False}}
    plan = {"richtung": "buy", "menge": 1, "tp": 100.0, "sl": 50.0}
    r_ok, r_text, r_f = ob.k3_ruecklesung(st, plan)
    chk(r_ok and "TP 100 $ AN (= 30533.00price)" in r_text and "SL 50 $ AN" in r_text, f"Rücklesung echter Stand ({r_text} {r_f})")
    st2 = {"ticket": dict(st["ticket"], sl={"an": False, "wert": 50, "einheit": "$"}), "kauf_knopf": st["kauf_knopf"]}
    chk(not ob.k3_ruecklesung(st2, plan)[0] and not ob.k3_ruecklesung(st, dict(plan, tp=120.0))[0], "Rücklesung: SL aus / falscher TP = nein")
    chk(ob.handlauf_sperre_frisch(1000.0, 1060.0) and not ob.handlauf_sperre_frisch(1000.0, 1000.0 + 16 * 60)
        and not ob.handlauf_sperre_frisch(None, 5.0) and not ob.handlauf_sperre_frisch(2000.0, 1000.0), "Sperre gilt ≤ 15 min")
    # Riegel im Quelltext
    js = ob.K3_LOGIN_BLICK_JS
    alle_v = len(_re.findall(r"\.value", js))
    sicher_v = len(_re.findall(r"\.value \|\| ''\)\.(?:length|toLowerCase\(\)\.indexOf)", js))
    chk(alle_v == 4 and alle_v == sicher_v, f"Login-Blick gibt nie Feldwerte zurück ({alle_v} Zugriffe, {sicher_v} nur Länge/Anfang)")   # 4: laenge_gleich (Auto-Login)
    q_k3 = _i.getsource(ob.modus_k3)
    chk(q_k3.count('"SENDEN-Knopf"') == 1 and q_k3.index('res["gesendet"] = True') < q_k3.index('"SENDEN-Knopf"'),
        "K3: genau EIN Senden-Klick, gesendet vorher auf True")
    chk("klick(cdp_rect(kk" not in _i.getsource(ob._cdp_ticket_fuellen), "Ticket-Helfer (K2/K3) klickt nie den Senden-Knopf")
    src = _i.getsource(ob)
    chk(src.count("modus_k3(") == 2, "modus_k3 nur aus dem Hand-Befehl in main()")
    for f in (ob.modus_tvlesen_cdp, ob.modus_tvkette_cdp, ob.modus_augen):
        chk("_handlauf_aktiv()" in _i.getsource(f), f"{f.__name__} hält bei laufendem K3 still")
    chk(len(ob.K3_PCS) == 1 and bool(_re.fullmatch(r"pc-[a-z0-9]{6}", ob.K3_PCS[0])), "K3 nur auf dem CDP-Test-PC")
    # echte Sitzungs-Klasse mit Attrappen-Verbindung (29.09.2026: Methode js() war vom Attribut self.js = augen.js überdeckt)
    class _Ws:
        def __init__(self):
            self.gesendet = []

        def rufe(self, m, p=None, timeout=10.0):
            self.gesendet.append((m, p))
            return {"result": {"value": [{"symbol": "MNQZ2026"}]}} if m == "Runtime.evaluate" else {}
    s_ = ob._AugenSitzung.__new__(ob._AugenSitzung)
    s_.trail, s_.ws, s_.js, s_.maus, s_.target_id = [], _Ws(), "/* augen.js */", (0.0, 0.0), "T"
    try:
        z_ = s_.lese_js(ob.K3_ZEILEN_JS)
    except Exception as e_:
        z_ = e_
    chk(z_ == [{"symbol": "MNQZ2026"}], f"lese_js an der echten Klasse (augen.js-Attribut überdeckt nichts): {z_!r}")
    for f_ in ("klick", "hin", "taste", "tippen", "feld_setzen", "lese_js", "rect_von", "stand"):
        chk(callable(getattr(s_, f_, None)), f"_AugenSitzung.{f_} ist aufrufbar (kein Attribut überdeckt sie)")
    for name_ in _re.findall(r"\bs\.([a-z_]+)\(", _i.getsource(ob.modus_k3) + _i.getsource(ob._k3_login_wechsel)):
        chk(callable(getattr(s_, name_, None)), f"modus_k3 ruft s.{name_}() — an der echten Klasse aufrufbar")
    if ok:
        print("✓ Puls K3: Knopf exakt, Meldungen/Zeilen/Close eindeutig, Sperre, Login-Blick ohne Feldwerte, nur Hand-Befehl")
    return ok


def test_puls_cdp_login():
    """Auto-Login im Puls-Chrome (29.09.2026, Finn: kein/falsches Tradovate-Konto selbst erkennen und wie der alte Puls über
    ?trade-now=TRADOVATE neu verbinden): wann ein Login nötig ist, Connect-Dialog + Demo + „Don't remember me", Username-Beweis,
    Riegel im Quelltext (nie Passwort tippen, nie „Allow", nur tvlesen/tvkette über CDP, K3 unberührt)."""
    import order_bot as ob
    import inspect as _i
    ok = True

    def chk(bed, text):
        nonlocal ok
        if not bed:
            print("  ✗ CDP-Login: " + text)
            ok = False
    # wann ein Login nötig ist
    chk(ob.cdp_login_noetig("kein_broker", {}) and ob.cdp_login_noetig("konto_nicht_erreicht", {"konto_treffer": 0})
        and not ob.cdp_login_noetig("konto_nicht_erreicht", {"konto_treffer": 2}) and not ob.cdp_login_noetig("konto_nicht_erreicht", {})
        and not ob.cdp_login_noetig("cdp_fehler", {"konto_treffer": 0}) and not ob.cdp_login_noetig("", None),
        "Login nur bei kein Broker oder 0 Treffern im Dropdown (mehrdeutig/Dropdown nicht erkannt = nie abmelden)")
    tv = "https://www.tradingview.com/chart/abc/?trade-now=TRADOVATE"
    chk(ob.cdp_seite_bereit("complete", tv, None) and ob.cdp_seite_bereit("interactive", tv, 1.5)
        and not ob.cdp_seite_bereit("interactive", tv, 1.4) and not ob.cdp_seite_bereit("interactive", tv, None)
        and not ob.cdp_seite_bereit("loading", tv, 30.0) and not ob.cdp_seite_bereit("complete", "about:blank", None)
        and not ob.cdp_seite_bereit("interactive", "https://evil.io/tradingview.com/", 30.0),
        "Tab bereit: complete sofort, interactive erst nach 1,5 s stabil, loading/fremde Seite nie (Jacob 01.10.2026)")
    st_ok = {"konto": {"schalter": {"rect": [70, 900, 180, 28]}, "aktiv": "APEX0000000000024 USD"}}
    chk(ob.cdp_konto_verbunden(st_ok) == "APEX0000000000024 USD" and ob.cdp_konto_verbunden({"konto": {"aktiv": "APEX0000000000024"}}) == ""
        and ob.cdp_konto_verbunden({"konto": {"schalter": {"rect": [1, 1, 50, 20]}, "aktiv": "Tradovate"}}) == ""
        and ob.cdp_konto_verbunden(None) == "", "verbunden = Umschalter UND Kontonummer")
    chk(ob.cdp_abgemeldet({"konto": {"schalter": None, "aktiv": ""}}) and not ob.cdp_abgemeldet(st_ok)
        and not ob.cdp_abgemeldet({"konto": {"schalter": None, "aktiv": "TDFYSL150001000000 USD"}}), "abgemeldet = weder Umschalter noch Nummer")
    # Connect-Dialog (Aufbau wie am 21./22.09. gesehen: Live/Demo + Don't remember me + Connect)
    dlg = {"titel": "Tradovate", "rect": [700, 300, 520, 420], "netzfehler": False,
           "knoepfe": [{"text": "Live", "role": "radio", "rect": [740, 420, 80, 30], "an": False},
                       {"text": "Demo", "role": "radio", "rect": [830, 420, 80, 30], "an": True},
                       {"text": "Connect", "rect": [900, 640, 120, 36]}, {"text": "", "aria": "Close", "rect": [1190, 310, 20, 20]}],
           "nicht_merken": {"an": False, "rect": [740, 580, 180, 20], "quelle": "kaestchen"}}
    bl = {"dialoge": [dlg], "umgebung": [{"text": "Demo", "role": "radio", "rect": [830, 420, 80, 30], "an": True},
                                         {"text": "Live", "role": "tab", "rect": [10, 10, 60, 20]}]}
    d = ob.cdp_connect_dialog(bl)
    chk(d is not None and d["connect"]["text"] == "Connect" and len(d["demo"]) == 1 and d["demo"][0].get("an") is True
        and d["nicht_merken"]["rect"] == [740, 580, 180, 20], f"Connect-Dialog erkannt, Demo einmal (doppelt gemeldet = eins): {d and len(d['demo'])}")
    chk(ob.cdp_connect_dialog({"dialoge": [dict(dlg, knoepfe=[{"text": "Sign in", "rect": [900, 640, 120, 36]}])]}) is None,
        "TradingViews eigenes 'Sign in' ist NIE der Connect-Dialog")
    chk(ob.cdp_connect_dialog({"dialoge": [dlg, dict(dlg, rect=[0, 0, 400, 300])]}) is None, "zwei Connect-Dialoge = keiner (mehrdeutig)")
    chk(ob.cdp_connect_dialog({"dialoge": [dlg], "login": {"box": [720, 320, 300, 200]}}) is None, "Dialog mit Login-Formular darin ist kein Connect-Dialog")
    chk(ob.cdp_connect_dialog({"dialoge": [dict(dlg, knoepfe=dlg["knoepfe"][2:])]})["demo"] == [], "ohne Demo: leere Liste (Aufrufer bricht ab)")
    chk(ob.cdp_connect_dialog({"dialoge": [dict(dlg, netzfehler=True)]})["netzfehler"], "Network error wird gemeldet")
    # Don't remember me
    P = ob.cdp_nicht_merken_plan
    chk(P({"an": False, "rect": [1, 1, 50, 20]}, False)[0] == "klick" and P({"an": True, "rect": [1, 1, 50, 20]}, False)[0] == "lassen"
        and P({"an": True, "rect": [1, 1, 50, 20]}, True)[0] == "klick" and P({"an": False, "rect": [1, 1, 50, 20]}, True)[0] == "lassen",
        "Haken nach sitzung_merken: Standard setzen, gemerkt = AUS")
    chk(P({"an": None, "rect": [1, 1, 50, 20]}, False)[0] == "klick" and P({"an": None, "rect": [1, 1, 50, 20]}, True)[0] == "lassen"
        and P(None, False)[0] == "fehlt" and P({"mehrdeutig": 2}, False)[0] == "fehlt" and P({"an": False, "rect": None}, False)[0] == "fehlt",
        "unlesbar: nur klicken, wenn gesetzt werden soll; fehlt/mehrdeutig = nie Abbruch, nur Hinweis")
    # Username exakt + Passwort (Werte nie gelesen)
    B = ob.cdp_login_bereit
    gut = {"user": {"gefuellt": True, "passt": True, "laenge_gleich": True}, "pw": {"gefuellt": True}}
    chk(B(gut)[0] and B(dict(gut, pw={"gefuellt": False, "autofill": True}))[0], "Username exakt + Passwort gefüllt/Autofill = bereit")
    chk(not B(dict(gut, user={"gefuellt": True, "passt": True, "laenge_gleich": False}))[0]
        and not B(dict(gut, user={"gefuellt": True, "passt": False, "laenge_gleich": True}))[0]
        and not B(dict(gut, pw={"gefuellt": False}))[0] and not B(None)[0], "längerer/anderer Username oder leeres Passwort = nicht bereit")
    tabs = [{"id": "A", "type": "page", "url": "https://trader.tradovate.com/oauth?x=1"}, {"id": "B", "type": "page", "url": "https://www.tradingview.com/chart/"},
            {"id": "C", "type": "page", "url": "https://tradovate.com.evil.io/"}, {"id": "D", "type": "service_worker", "url": "https://trader.tradovate.com/sw.js"}]
    chk([t["id"] for t in ob.cdp_tradovate_tabs(tabs)] == ["A"] and ob.cdp_tradovate_tabs(tabs, {"A"}) == [],
        "Tradovate-Tab: nur echte tradovate.com-Seiten, die nach dem Connect neu sind")
    chk(ob.tv_trade_now_url("https://www.tradingview.com/chart/AbC123/?symbol=MNQ") == "https://www.tradingview.com/chart/AbC123/?trade-now=TRADOVATE"
        and ob.tv_trade_now_url("https://evil.example/chart/") == "https://www.tradingview.com/chart/?trade-now=TRADOVATE",
        "trade-now-Adresse behält das Layout, fremde Seite → Standard")
    # Riegel im Quelltext
    q = "".join(_i.getsource(f) for f in (ob._cdp_anmelden, ob._cdp_dialog_verbinden, ob._cdp_login_ort, ob._cdp_tradovate_verbinden,
                                          ob._cdp_abmelden, ob._cdp_konto_mit_login))
    chk(q.count(".tippen(") == 1 and "tippen(benutzer)" in q, "getippt wird nur der Username — nie ein Passwort")
    chk("K3_RX_FREIGABE" not in q and '"freigabe"' in q, "Freigabe ('Allow') wird nur gemeldet, nie geklickt")
    # erster Live-Lauf .799 (29.09.2026): Enter schickte „APEX_000000TDFYU000000000" ab — jetzt Vorschlag anklicken, Enter nur nach Beweis
    q_an = _i.getsource(ob._cdp_anmelden)
    chk(q_an.count('taste("Enter")') == 1 and q_an.index("if ok3:") < q_an.index('taste("Enter")'),
        "Enter im Login-Formular nur noch EINMAL und nur nach bewiesenem Username + Passwort")
    chk("_cdp_autofill_klick(" in q_an and q_an.index("_cdp_autofill_klick(") < q_an.index("(Login)"), "erst Chrome-Vorschlag anklicken, dann Anmelden")
    F = ob.cdp_tab_frisch
    chk(F(True, None, 0) and F(False, 1_000_500.0, 1_000_000.0) and not F(False, 990_000.0, 1_000_000.0) and not F(False, None, 1_000_000.0)
        and not F(False, 5.0, 0.0), "Tradovate-Tab zählt nur, wenn neu oder seit dem Connect-Klick neu geladen (alter Fehlversuchs-Tab nicht)")
    # K4: Rücklesung vor dem Senden (TP/SL dürfen AUS sein) + Beweis nach dem Klick
    tk_ = {"typen": [{"id": "Market", "aria-selected": "true", "rect": [1, 1, 5, 5]}], "seite": "buy", "menge": {"wert": "2"},
           "tp": {"an": True, "wert": 100, "einheit": "$"}, "sl": {"an": False, "wert": 50, "einheit": "$"}}
    st_ = {"ticket": tk_, "kauf_knopf": {"text": "Buy 2 MNQZ6 MARKET", "seite": "buy"}}
    RL = ob.cdp_ticket_ruecklesung
    chk(RL(st_, {"richtung": "buy", "menge": 2, "tp": 100.0, "sl": None})[0], "Rücklesung: Plan ohne SL, SL-Schalter AUS = ok")
    chk(not RL(st_, {"richtung": "buy", "menge": 2, "tp": 100.0, "sl": 50.0})[0]
        and not RL(dict(st_, ticket=dict(tk_, sl={"an": True, "wert": 50, "einheit": "$"})), {"richtung": "buy", "menge": 2, "tp": 100.0, "sl": None})[0]
        and not RL(st_, {"richtung": "sell", "menge": 2, "tp": 100.0, "sl": None})[0]
        and not RL(st_, {"richtung": "buy", "menge": 1, "tp": 100.0, "sl": None})[0]
        and not RL(st_, {"richtung": "buy", "menge": 2, "tp": 120.0, "sl": None})[0], "Rücklesung: SL fehlt/an, falsche Seite/Menge/TP = kein Senden")
    chk(ob.k3_knopf_exakt("Buy 2 MNQZ6 MARKET", "buy", 2, "MNQZ6") and not ob.k3_knopf_exakt("Buy 2 MNQZ6 MARKET", "buy", 1, "MNQZ6")
        and not ob.k3_knopf_exakt("Sell 2 MNQZ6 MARKET", "buy", 2, "MNQZ6") and not ob.k3_knopf_exakt("Buy 2 NQZ6 MARKET", "buy", 2, "MNQZ6"),
        "Knopf-Text exakt (Seite, Menge, Symbol)")
    fill = {"art": "fill", "status": "ausgefuehrt", "seite": "buy", "menge": 2, "preis": 30637.0, "text": "Market order executed Buy 2 at 30,637.00"}
    tpm = {"art": "tp", "status": "platziert", "seite": "sell", "menge": 2, "preis": 30662.0, "text": "Take Profit order placed"}
    zeile = {"symbol": "MNQZ6", "seite": "buy", "menge": 2, "avg": 30637.25, "sichtbar": True}
    P2 = {"richtung": "buy", "menge": 2, "tp": 100.0, "sl": None}
    b1 = ob.cdp_order_beweis([fill, tpm], [zeile], P2, 0)
    chk(b1["bestaetigt"] and b1["einstieg"] == 30637.0 and b1["einstieg_quelle"] == "fill_toast" and b1["tp"] == 30662.0, f"Beweis über die Fill-Meldung ({b1})")
    b2 = ob.cdp_order_beweis([], [zeile], P2, 0)
    chk(b2["bestaetigt"] and b2["einstieg"] == 30637.25 and b2["einstieg_quelle"] == "tabelle_avg_fill", "Beweis über die Tabelle (vorher flach → Avg = Einstieg)")
    b3 = ob.cdp_order_beweis([], [dict(zeile, menge=3)], P2, 1)
    chk(b3["bestaetigt"] and b3["einstieg"] is None, "vorher schon offen: Menge gewachsen = Beweis, Avg ist dann KEIN Einstieg")
    chk(not ob.cdp_order_beweis([], [dict(zeile, menge=1)], P2, 1)["bestaetigt"] and not ob.cdp_order_beweis([], [], P2, 0)["bestaetigt"]
        and not ob.cdp_order_beweis([dict(fill, seite="sell")], [], P2, 0)["bestaetigt"], "kein Wachstum / fremde Seite = nicht bewiesen")
    # „Show more" nach dem Kauf (Finn 29.09.2026: SL fehlte, Stapel eingeklappt)
    MZ = ob.cdp_meldungen_zu
    zu_o = {"gruppe": "orders", "offen": False, "mehr": {"rect": [1500, 900, 80, 20]}, "texte": [{"text": "Sell 1"}]}
    chk(MZ({"gruppen": [{"gruppe": "alerts", "offen": False, "texte": [{"text": "x"}]}, zu_o]}) is zu_o
        and MZ({"gruppen": [dict(zu_o, offen=True)]}) is None and MZ({"gruppen": [dict(zu_o, gruppe="x"), dict(zu_o, gruppe="y")]}) is None
        and MZ(None) is None, "eingeklappter Stapel: 'orders' bevorzugt, offen/mehrdeutig = kein Klick")
    q_mehr = _i.getsource(ob.modus_tvkette_cdp)
    chk(q_mehr.count('"Show more (Meldungen') == 1 and 'not mehr["gedrueckt"] and mehr["versuche"] < 4' in q_mehr
        and 'mehr["gedrueckt"] = True' in q_mehr, "Show more: bis 4 Versuche, nach einem echten Druck nie wieder")
    SW = ob.cdp_show_more_wahl
    dn_k = {"text": "Show more 3", "dn": "toast-group-expand-button-orders", "expanded": "false", "rect": [1500, 800, 90, 22]}
    tx_k = {"text": "Show more", "dn": "", "rect": [1500, 800, 70, 22]}
    chk(SW([dn_k]) is dn_k and SW([tx_k, dn_k]) is dn_k and SW([dict(dn_k, expanded="true")]) is None
        and SW([dict(tx_k, text="Show less")]) is None and SW([]) is None, "Show-more-Wahl: data-name vor Text, offen/Show less nie")
    a_ = dict(tx_k, rect=[1500, 780, 70, 22]); b_ = dict(tx_k, rect=[200, 100, 70, 22])
    chk(SW([a_, b_], [1400, 810, 300, 120]) is a_ and SW([a_, b_]) is None and SW([a_, dict(a_)], [1400, 810, 300, 120]) is None,
        "mehrere Text-Treffer: der nächste zum Stapel, gleich nah/ohne Stapel = keiner")
    chk("@ 30,637.00" in ob.cdp_meldung_text(fill) and ob.cdp_meldung_text(None) == "", "Rohtext der Meldung mit Preis")
    # Start-Werte + Endprüfung im selben Lauf (Finn 29.09.2026: „am Ende die Werte nochmal überprüfen")
    chk(ob.cdp_summary_start({"Account Balance": "150,012.10", "Total P/L": "-56.96", "Equity": "150,000.00"})
        == {"balance_start": 150012.1, "equity_start": 150000.0, "today_pnl_start": -56.96}
        and ob.cdp_summary_start(None) == {"balance_start": None, "equity_start": None, "today_pnl_start": None}, "Start-Werte aus Account summary")
    ords = [{"symbol": "MNQZ6", "seite": "buy", "menge": 1, "typ": "Limit", "preis": 30516.5, "status": "Working", "sichtbar": True},
            {"symbol": "MNQZ6", "seite": "buy", "menge": 1, "typ": "Stop", "preis": None, "status": "Working", "sichtbar": True,
             "spalten": {"Stop Price": "30,698.50"}},
            {"symbol": "NQZ6", "seite": "buy", "menge": 1, "typ": "Limit", "preis": 1.0, "status": "Working", "sichtbar": True}]
    chk(ob.cdp_brackets_aus_orders(ords, "MNQ", "sell", 1) == (30516.5, 30698.5) and ob.cdp_brackets_aus_orders(ords, "MNQ", "buy", 1) == (None, None)
        and ob.cdp_brackets_aus_orders(ords + [dict(ords[0])], "MNQ", "sell", 1)[0] is None, "TP/SL aus dem Reiter Orders (Gegenseite, genau eine)")
    bw = {"einstieg": 30682.25, "einstieg_quelle": "fill_toast", "tp": 30516.5, "sl": 30698.5}
    PR = ob.cdp_pruefung
    chk(PR(bw, 30682.25, 30516.5, 30698.5, {"tp": 1, "sl": 1})["ok"] and not PR(bw, 30682.5, 30516.5, 30698.5, {"tp": 1, "sl": 1})["ok"]
        and PR(bw, None, None, None, {"tp": 1, "sl": 1})["ok"] and not PR({}, None, None, None, {"tp": None, "sl": None})["ok"]
        and PR(bw, 30682.25, 30516.5, 30698.5, {"tp": 1, "sl": 1})["abweichung"] == {"fill": 0.0, "tp": 0.0, "sl": 0.0},
        "Endprüfung: exakt = passt, 0,25 daneben = nicht sicher, nichts gelesen = nicht sicher")
    q_k4 = _i.getsource(ob.modus_tvkette_cdp)
    chk(q_k4.index("_cdp_today_aus_reiter(") < q_k4.index("_cdp_ticket_fuellen(") and q_k4.index('"SENDEN-Knopf"') < q_k4.index("_cdp_endpruefung(")
        and "klick(" not in _i.getsource(ob.cdp_pruefung), "Summary vor dem Ausfüllen, Endprüfung nach dem Senden (rein rechnend)")
    # Stabilität nach Live-Befunden 29.09.2026 14:4x: Seite fertig laden, augen.js nachladen, Regel bei Netzfehler behalten
    chk(ob.cdp_fehlertext({"exceptionDetails": {"text": "Uncaught", "exception": {"description": "TypeError: Cannot read properties of undefined (reading 'stand')"}}}).startswith("TypeError")
        and ob.cdp_fehlertext({"exceptionDetails": {"text": "Uncaught"}}) == "Uncaught" and ob.cdp_fehlertext({}) == "", "Ausnahme-Text statt nur 'Uncaught'")
    chk(ob.augen_fehlt("TypeError: Cannot read properties of undefined (reading 'stand')") and ob.augen_fehlt("ReferenceError: prophosAugen is not defined")
        and not ob.augen_fehlt("RangeError: Maximum call stack"), "fehlendes prophosAugen erkannt")

    class _WsN:
        def __init__(self):
            self.n, self.geladen = 0, 0

        def rufe(self, m, p=None, timeout=10.0):
            ex = (p or {}).get("expression", "")
            if "document.readyState" in ex:
                return {"result": {"value": ["complete", "https://www.tradingview.com/chart/", 9000]}}
            if ex == "/* augen.js */":
                self.geladen += 1
                return {"result": {}}
            self.n += 1
            if self.n == 1:
                return {"exceptionDetails": {"text": "Uncaught", "exception": {"description": "TypeError: Cannot read properties of undefined (reading 'stand')"}}}
            return {"result": {"value": {"konto": {"aktiv": "X"}}}}
    s2 = ob._AugenSitzung.__new__(ob._AugenSitzung)
    s2.trail, s2.ws, s2.js = [], _WsN(), "/* augen.js */"
    alt_w = ob._warte
    ob._warte = lambda a_, b_: None
    try:
        v2 = s2.stand({})
    except Exception as e_:
        v2 = e_
    finally:
        ob._warte = alt_w
    chk(v2 == {"konto": {"aktiv": "X"}} and s2.ws.geladen == 1, f"stand(): fehlt augen.js → einmal nachgeladen, dann gelesen ({v2!r})")
    import urllib.request as _ur
    alt_uo, alt_l, alt_s = _ur.urlopen, ob._augen_json_lesen, ob._augen_json_schreiben
    geschrieben = []
    try:
        _ur.urlopen = lambda *a_, **k_: (_ for _ in ()).throw(OSError("timeout"))
        ob._augen_json_lesen = lambda n: {"augen": "cdp", "at": __import__("time").time() - 60, "pc": "pc-cccccc"}
        ob._augen_json_schreiben = lambda n, d: geschrieben.append(d)
        r1 = ob._augen_regel_holen("pc-cccccc")
        e1 = ob._AUGEN_REGEL_STAND["explizit"]
        ob._augen_json_lesen = lambda n: None
        r2 = ob._augen_regel_holen("pc-cccccc")
    finally:
        _ur.urlopen, ob._augen_json_lesen, ob._augen_json_schreiben = alt_uo, alt_l, alt_s
    chk(r1 == "cdp" and e1 is False and r2 == "uia" and not geschrieben, "Netzfehler: letzte 'cdp'-Regel bleibt, Datei unverändert; ohne Merker 'uia'")
    q_au = _i.getsource(ob.modus_augen)
    chk('not _AUGEN_REGEL_STAND["explizit"]' in q_au and q_au.index('_AUGEN_REGEL_STAND["explizit"]') < q_au.index("Browser.close"),
        "Puls-Chrome wird nur bei AUSDRÜCKLICHEM 'uia' geschlossen")
    # Live 29.09.2026 14:56/14:58 UTC: Login-Abbruch im Connect-Dialog + Orders-Tabelle ohne data-label
    dlg_f = dict(dlg, text="Tradovate Live Demo Error! The login operation has been canceled Don't remember me Connect")
    chk("login operation has been canceled" in ob.cdp_connect_fehler({"dialoge": [dlg_f]}) and ob.cdp_connect_fehler({"dialoge": [dlg]}) == ""
        and ob.cdp_connect_fehler({"dialoge": [dict(dlg, text="Error! Network error occurred. Please check")]}).startswith("Error!")
        and ob.cdp_connect_fehler(None) == "", "Fehlermeldung im Connect-Dialog erkannt (Abbruch, Netzfehler), sonst leer")
    q_tv = _i.getsource(ob._cdp_tradovate_verbinden)
    chk("for versuch in (1, 2):" in q_tv and "Connect noch einmal" in q_tv and '"abgebrochen"' in _i.getsource(ob._cdp_anmelden)
        and "f_neu != fehler_alt" in _i.getsource(ob._cdp_login_ort), "Login-Abbruch: sofort erkannt, genau ein zweiter Connect")
    roh_t = {"reiter": "orders", "tabellen": [{"koepfe": ["Symbol", "Side", "Type", "Qty", "Limit Price", "Stop Price", "Status"],
             "zeilen": [[["", "MNQZ6"], ["", "Buy"], ["", "Limit"], ["", "1"], ["", "30,679.50"], ["", ""], ["", "Working"]],
                        [["", "MNQZ6"], ["", "Buy"], ["", "Stop"], ["", "1"], ["", "—"], ["", "30,806.50"], ["", "Working"]],
                        [["", "MNQZ6"], ["", "Sell"], ["", "Market"], ["", "1"], ["", ""], ["", ""], ["", "Filled"]]]}]}
    oz = ob.cdp_orders_aus_roh(roh_t)
    chk(len(oz) == 3 and ob.cdp_brackets_aus_orders(oz, "MNQ", "sell", 1) == (30679.5, 30806.5), f"Orders ohne data-label über die Spaltenköpfe ({oz[:1]})")
    roh_l = {"tabellen": [{"koepfe": [], "zeilen": [[["Symbol", "MNQZ6"], ["Side", "Buy"], ["Type", "Limit"], ["Qty", "1"], ["Limit Price", "30,679.50"], ["Status", "Working"]]]}]}
    chk(ob.cdp_brackets_aus_orders(ob.cdp_orders_aus_roh(roh_l), "MNQ", "sell", 1)[0] == 30679.5 and ob.cdp_orders_aus_roh(None) == [],
        "Orders mit data-label, leerer Blick = nichts")
    chk("Reiter orders" in ob.cdp_tabellen_kurz(roh_t) and "Köpfe Symbol/Side" in ob.cdp_tabellen_kurz(roh_t) and len(ob.cdp_tabellen_kurz(roh_t)) <= 700,
        "Tabellen-Blick kompakt für die Spur")
    chk(ob.cdp_liste_kurz([("APEX_000000", None, "ListItem"), ("••••••••", None, "Text"), ("TDFYU000000000", None, "Text"),
                           ("tradovate.com", None, "Text"), ("APEX_000000", None, "ListItem")]) == "ListItem:APEX_000000 | Text:TDFYU000000000 | Text:tradovate.com"
        and ob.cdp_liste_kurz([]) == "leer" and "Group" in ob.CDP_AUTOFILL_TYPEN, "Vorschlagsliste für die Spur: ohne Punkte, doppelte einmal")
    # Fokus-Riegel (Live 15:11 UTC: Klick gemeldet, Feld blieb leer, getippt wurde trotzdem): ohne Fokus-Beweis keine Taste
    class _WsF:
        def __init__(self, fokus):
            self.fokus, self.keys = fokus, []

        def rufe(self, m, p=None, timeout=10.0):
            if m == "Runtime.evaluate":
                return {"result": {"value": self.fokus}}
            if m == "Input.dispatchKeyEvent" and (p or {}).get("type") in ("keyDown", "rawKeyDown"):
                self.keys.append((p or {}).get("key"))
            return {}
    alt_w, alt_e = ob._warte, ob._WIN_EINGABE
    erg_f = []
    try:
        ob._warte, ob._WIN_EINGABE = (lambda a_, b_: None), False
        for fok in (False, True):
            sf = ob._AugenSitzung.__new__(ob._AugenSitzung)
            sf.trail, sf.ws, sf.maus = [], _WsF(fok), (0.0, 0.0)
            erg_f.append((sf.feld_setzen([10, 10, 100, 20], "12", "Units"), list(sf.ws.keys)))
    finally:
        ob._warte, ob._WIN_EINGABE = alt_w, alt_e
    chk(erg_f[0] == (False, []) and erg_f[1][0] is True and "1" in erg_f[1][1], f"feld_setzen: ohne Fokus keine einzige Taste, mit Fokus getippt ({erg_f})")
    q_an2 = _i.getsource(ob._cdp_anmelden)
    chk(q_an2.index("fokus_im(cdp_rect(u)") < q_an2.index('taste("a", modifiers=2)') and "_win_root_am_punkt(" in _i.getsource(ob._AugenSitzung._win_klick),
        "Login: Fokus vor Strg+A/Tippen bewiesen; jeder Windows-Klick prüft das Fenster am Zielpunkt")
    # Reiter-Wechsel beweisen (Live 15:29 UTC: Orders geklickt, aktiv blieb positions)
    leiste = [{"id": "positions", "text": "Positions 1", "role": "tab", "sel": "true", "rect": [80, 540, 80, 24]},
              {"id": "orders", "text": "Orders 2", "role": "tab", "sel": "false", "rect": [170, 540, 80, 24]},
              {"id": "", "text": "Orders 2", "role": "", "sel": None, "rect": [175, 544, 60, 16]},
              {"id": "summary", "text": "Account summary", "role": "tab", "sel": "false", "rect": [260, 540, 120, 24]}]
    chk(ob.cdp_reiter_aktiv(leiste, "positions") and not ob.cdp_reiter_aktiv(leiste, "orders")
        and ob.cdp_reiter_wahl(leiste, "orders")["id"] == "orders" and ob.cdp_reiter_wahl(leiste, "history") is None
        and "orders:Orders 2@" in ob.cdp_reiter_kurz(leiste) and "positions:Positions 1*" in ob.cdp_reiter_kurz(leiste),
        "Reiter: aktiv über aria-selected, Wahl role=tab per id/Text, Leiste kompakt")
    chk("_cdp_reiter(s, \"orders\", trail)" in _i.getsource(ob._cdp_endpruefung), "Endprüfung wechselt den Reiter nur mit Beweis")
    # Schließen über CDP (Finn 29.09.2026): Weiche, genau ein Close-Klick, Rückfrage nur submit-button mit „Close", End-Balance
    q_cl = _i.getsource(ob.modus_tvclose_cdp)
    chk('if augen_modus_lauf() == "cdp":' in _i.getsource(ob.modus_tvclose) and "modus_tvclose_cdp(cmd)" in _i.getsource(ob.modus_tvclose),
        "tvclose: CDP-Weiche vor dem alten Pfad")
    chk(q_cl.count('f"Close-Knopf der {root}-Zeile"') == 1 and q_cl.index('res["geklickt"] = True') < q_cl.index('f"Close-Knopf der {root}-Zeile"')
        and 'sub.get("dn") != "submit-button"' in q_cl and "k3_close_knopf(zeile_c)" in q_cl and '"schon_flach"' in q_cl,
        "tvclose CDP: EIN Close-Klick, geklickt vorher, Rückfrage nur submit-button, schon_flach ohne Klick")
    chk(ob.cdp_summary_ende({"Account Balance": "153,760.96", "Equity": "153,760.96", "Total P/L": "4.00"}) == {"balance_end": 153760.96, "equity_end": 153760.96}
        and ob.cdp_summary_ende(None) == {"balance_end": None, "equity_end": None}, "End-Balance/Equity aus Account summary")
    # „Session disconnected" (Live 15:48 UTC): erkennen, nie als Broker-Connect-Dialog nehmen
    sitz_d = {"titel": "Session disconnected", "rect": [500, 250, 600, 300],
              "text": "Session disconnected Your session ended because your account was accessed from another browser or device. Connect",
              "knoepfe": [{"text": "Connect", "rect": [760, 480, 90, 34]}, {"text": "", "aria": "Close", "rect": [1070, 260, 20, 20]}]}
    chk(ob.cdp_sitzung_getrennt({"dialoge": [sitz_d]})["text"] == "Connect" and ob.cdp_sitzung_getrennt({"dialoge": [dlg]}) is None
        and ob.cdp_sitzung_getrennt(None) is None and ob.cdp_connect_dialog({"dialoge": [sitz_d]}) is None,
        "Sitzungs-Dialog erkannt; Broker-Dialog ist keiner; Sitzungs-Dialog ist nie der Broker-Connect-Dialog")
    q_km = _i.getsource(ob._cdp_konto_mit_login)
    chk(q_km.index("_cdp_sitzung_zurueck(") < q_km.index("_cdp_konto_sichern("), "Sitzungs-Dialog vor dem Konto-Schritt lösen")
    # Ergebnis überlebt den Prophos-Tab (Live 15:49 UTC: Order lag, Prophos erfuhr nie davon)
    pk = ob.puls_ergebnis_paket("order", "ende", {"plan_id": "0000abcd", "ext_id": "TDFYSL150300000000", "symbol": "MNQZ6", "richtung": "buy"},
                                {"ok": True, "gesendet": True, "einstieg": "30606.0", "tp_limit": 30722.5, "trail": "x", "summary": {"a": 1}}, ["a", "b"], 5)
    chk(pk["plan_id"] == "0000abcd" and pk["art"] == "order" and pk["at_ms"] == 5 and pk["ergebnis"]["einstieg"] == "30606.0"
        and "summary" not in pk["ergebnis"] and "trail" not in pk["ergebnis"] and pk["ergebnis"]["trail_ende"] == "a > b"
        and pk["ergebnis"]["symbol"] == "MNQZ6" and pk["ergebnis"]["richtung"] == "buy"
        and ob.puls_ergebnis_paket("close", "geklickt", {}, {}, None, 1)["plan_id"] is None, "Ergebnis-Paket: bekannte Felder, Plan-ID, ohne Plan ok")
    chk(ob.tv_bruecke_auspacken({"geschwister": ["@plan_id=0000abcd", "TDFYSL1"]}) == {"geschwister": ["TDFYSL1"], "plan_id": "0000abcd"},
        "plan_id reist über die Brücke, nie als Konto")
    q_k = _i.getsource(ob.modus_tvkette_cdp)
    q_c = _i.getsource(ob.modus_tvclose_cdp)
    chk(q_k.index('"SENDEN-Knopf"') < q_k.index('_puls_ergebnis_senden("order", "geklickt"') and '_puls_ergebnis_senden("order", "ende"' in q_k
        and q_c.index('f"Close-Knopf der {root}-Zeile"') < q_c.index('_puls_ergebnis_senden("close", "geklickt"') and '_puls_ergebnis_senden("close", "ende"' in q_c
        and "tv_bruecke_auspacken(cmd)" in q_c, "Order und Schließen melden ihr Ergebnis nach dem Klick und am Ende selbst")
    chk(ob.cdp_im_bild([10, 10, 50, 20], {"innerWidth": 100, "innerHeight": 100}) and not ob.cdp_im_bild([90, 10, 50, 20], {"innerWidth": 100, "innerHeight": 100})
        and not ob.cdp_im_bild(None, {}) and '[data-name^="toast-group-"]' in ob.win_ziel_js(1, 2) and "toast:!!t" in ob.win_ziel_js(1, 2),
        "Ziel-Probe erkennt Meldungen, im-Bild-Prüfung")
    q_mz = _i.getsource(ob.modus_tvkette_cdp)
    chk("Show less (Meldungen" in q_mz and q_mz.index("Show less (Meldungen") < q_mz.index("_cdp_endpruefung("), "Stapel nach dem Lesen zuklappen, vor den Reiter-Klicks")
    # Broker-Panel nach dem Login zugeklappt (Live 16:25 UTC): aufklappen, dann Konto
    chk(ob.cdp_panel_zu({"konto": {"panel": "zu", "panel_knopf": {"rect": [1500, 900, 30, 30]}}}) is not None
        and ob.cdp_panel_zu({"konto": {"panel": "offen", "panel_knopf": {"rect": [1, 1, 30, 30]}}}) is None and ob.cdp_panel_zu(None) is None,
        "Panel zu erkannt")

    class _SP:
        def __init__(self):
            self.auf, self.klicks = False, []

        def stand(self, opts=None):
            return ({"konto": {"panel": "offen", "schalter": {"rect": [1, 1, 50, 20]}, "aktiv": "PAAPEX0000000000008 USD"}} if self.auf
                    else {"konto": {"panel": "zu", "panel_knopf": {"rect": [1500, 900, 30, 30]}, "aktiv": ""}})

        def klick(self, r, n, toast_ok=False):
            self.klicks.append(n)
            self.auf = True
            return True
    alt_w = ob._warte
    ob._warte = lambda a_, b_: None
    try:
        sp_ = _SP()
        v_ = ob._cdp_verbunden_lesen(sp_, {}, [])
    finally:
        ob._warte = alt_w
    chk(v_ == "PAAPEX0000000000008 USD" and sp_.klicks == ["Handelspanel auf (Open panel)"], f"zugeklapptes Panel → einmal auf → Konto ({v_!r})")
    # Live 29.09.2026 23:04 UTC (pc-jjjjjj): Connect-Dialog lag über „Open panel" — nicht klicken, Versuch zählt nicht; Klick ohne
    # Wirkung steht ehrlich in der Spur
    class _SPD(_SP):
        def __init__(self, frei, wirkt=True):
            super().__init__()
            self.frei, self.wirkt, self.ww = frei, wirkt, 0

        def werbung_weg(self, zwang=False):
            self.ww += 1
            return 0

        def lese_js(self, a, timeout=8):
            return {"frei": self.frei, "was": "div.backdrop"}

        def klick(self, r, n, toast_ok=False):
            self.klicks.append(n)
            self.auf = self.wirkt
            return True
    ob._warte = lambda a_, b_: None
    try:
        sd_, td_ = _SPD(False), []
        v1_ = ob._cdp_verbunden_lesen(sd_, {}, td_)
        v1b_ = ob._cdp_verbunden_lesen(sd_, {}, td_)
        sd_.frei = True
        v2_ = ob._cdp_verbunden_lesen(sd_, {}, td_)
        sn_, tn_ = _SPD(True, wirkt=False), []
        v3_ = ob._cdp_verbunden_lesen(sn_, {}, tn_)
    finally:
        ob._warte = alt_w
    chk(v1_ == "" and v1b_ == "" and sum("verdeckt" in x for x in td_) == 1 and getattr(sd_, "_panel_klicks", 0) == 1
        and v2_ == "PAAPEX0000000000008 USD" and sd_.klicks == ["Handelspanel auf (Open panel)"] and sd_.ww == 3,
        f"Dialog über „Open panel“ → kein Klick, zählt nicht, danach frei → Klick → Konto ({td_})")
    chk(v3_ == "" and tn_ == ["Handelspanel bleibt nach dem Klick zu"] and sn_._panel_klicks == 1, f"Klick ohne Wirkung → Spur ({tn_})")
    # Order-Panel eingeklappt (Finn 30.09.2026, pc-cccccc: 49 px unter der Broker-Leiste, „Dropdown nicht erkannt") → „Maximize panel"
    # EINMAL, Konto-Schritt EINMAL wiederholen; Symbol fehlt → kein_broker (Login-Weg)
    L_ = ob.cdp_panel_lage
    chk(L_(None) == "unklar" and L_({"unter_leiste": 40}) == "unklar" and L_({"leiste": [56, 686, 879, 38], "unter_leiste": True}) == "unklar"
        and L_({"leiste": [56, 686, 879, 38], "unter_leiste": 49}) == "eingeklappt"
        and L_({"leiste": [56, 587, 1199, 38], "unter_leiste": 320}) == "ok" and L_({"leiste": [1, 1, 9, 9], "unter_leiste": 150}) == "ok",
        "Order-Panel-Lage: 49 px eingeklappt, 320 px ok, ohne Leiste/Höhe unklar")
    chk('toggle-maximize-button' in ob.CDP_PANEL_LAGE_JS and 'footer-chart-panel' in ob.CDP_PANEL_LAGE_JS
        and 'id_account-manager-tabs' in ob.CDP_PANEL_LAGE_JS and "click" not in ob.CDP_PANEL_LAGE_JS, "Panel-Probe liest nur (Leiste, Reiter, Kopf-Knöpfe)")

    class _SK:
        """Attrappe Puls-Chrome: Panel eingeklappt (49 px) bis „Maximize panel", Liste geht nur bei großem Panel auf."""
        def __init__(self, knopf=True, liste=True, gross=False, aktiv="PAAPEX0000000000007USD"):
            self.gross, self.knopf, self.liste, self.aktiv, self.offen, self.klicks = gross, knopf, liste, aktiv, False, []

        def stand(self, opts=None):
            ein = [{"text": "PAAPEX0000000000007USD", "rect": [78, 600, 228, 32]}, {"text": "PAAPEX0000000000008USD", "rect": [78, 632, 228, 32]}]
            return {"konto": {"panel": "offen", "schalter": {"rect": [72, 745, 199, 28]}, "aktiv": self.aktiv,
                              "liste_offen": self.offen, "eintraege": ein if self.offen else []}}

        def lese_js(self, a, timeout=8):
            if "elementFromPoint" in a:
                return {"frei": True, "was": ""}
            return {"leiste": [56, 686, 879, 38], "unter_leiste": 320 if self.gross else 49,
                    "max_knopf": {"rect": [897, 686, 38, 38], "aria": "Maximize panel"} if self.knopf else None}

        def werbung_weg(self, zwang=False):
            return 0

        def taste(self, k, modifiers=0):
            self.klicks.append("Taste " + k)

        def klick(self, r, n, toast_ok=False):
            self.klicks.append(n)
            if "Maximize" in n:
                self.gross = True
            elif n == "Konto-Umschalter":
                self.offen = self.liste and self.gross
            elif n.startswith("Konto "):
                self.aktiv, self.offen = "PAAPEX0000000000008USD", False
            return True
    ob._warte = lambda a_, b_: None
    ob.CDP_NIE_MAXIMIEREN = False   # alter Maximize-Rückfall (Code bleibt) — seit 01.10.2026 per Schalter aus, unten geprüft
    try:
        k1_, t1_ = _SK(), []
        r1_ = ob._cdp_konto_sichern(k1_, "PAAPEX0000000000008", {}, t1_)
        k2_, t2_ = _SK(knopf=False), []
        r2_ = ob._cdp_konto_sichern(k2_, "PAAPEX0000000000008", {}, t2_)
        k3_, t3_ = _SK(gross=True, liste=False), []
        r3_ = ob._cdp_konto_sichern(k3_, "PAAPEX0000000000008", {}, t3_)
        k4_, t4_ = _SK(aktiv="PAAPEX0000000000008USD"), []
        r4_ = ob._cdp_konto_sichern(k4_, "PAAPEX0000000000008", {}, t4_)
    finally:
        ob._warte = alt_w
    chk(r1_[0] and k1_.klicks == ["Order-Panel aufklappen (Maximize panel)", "Konto-Umschalter", "Konto PAAPEX0000000000008"]
        and "Order-Panel war eingeklappt → aufgeklappt → Konto gewechselt" in t1_,
        f"eingeklappt → EIN Klick „Maximize panel“ → Umschalter → Konto gewechselt ({k1_.klicks}, {t1_})")
    chk(not r2_[0] and r2_[1] == "kein_broker" and k2_.klicks == [] and "Login-Weg" in r2_[2]
        and ob.cdp_login_noetig(r2_[1], r2_[4]), f"Symbol fehlt → kein Klick, kein_broker → Login-Weg ({r2_[2]})")
    chk(not r3_[0] and r3_[1] == "konto_nicht_erreicht" and k3_.klicks == ["Konto-Umschalter", "Taste Escape"] and "Order-Panel ok (320 px)" in r3_[2],
        f"Panel groß, Liste trotzdem nicht erkannt → ehrliche Meldung mit Panel-Lage, Umschalter nur einmal ({r3_[2]})")
    chk(r4_[0] and k4_.klicks == [] and not k4_.gross,
        f"Konto steht, Panel eingeklappt → NIE maximieren (Finn 01.10.2026: Chart sichtbar), nie deshalb scheitern ({k4_.klicks})")
    chk("_cdp_panel_aufklappen(s, trail, ohne_max=True)" in _i.getsource(ob._cdp_konto_sichern)
        and "if _cdp_panel_zurueck(s, trail):" in _i.getsource(ob._cdp_konto_sichern),
        "Konto steht → höchstens Open panel, kurz Maximiertes sofort zurück (Restore) vor Ticket/Order")
    # Open panel zuerst (Finn 01.10.2026, Live-Befund Moritz 23:08 UTC: Maximize versteckte den Chart → Symbol nicht einstellbar)
    class _SO(_SK):
        def __init__(self, open_reicht=True, **kw):
            _SK.__init__(self, **kw); self.open_reicht, self.zu = open_reicht, True

        def lese_js(self, a, timeout=8):
            d = _SK.lese_js(self, a, timeout)
            if "elementFromPoint" in a:
                return d
            d["vis_knopf"] = {"rect": [860, 686, 38, 38], "aria": "Open panel" if self.zu else "Collapse panel"}
            return d

        def klick(self, r, n, toast_ok=False):
            if "Open panel" in n:
                self.klicks.append(n); self.zu = False; self.gross = self.open_reicht
                return True
            return _SK.klick(self, r, n, toast_ok)
    ob._warte = lambda a_, b_: None
    try:
        ko1_, to1_ = _SO(), []
        ro1_ = ob._cdp_konto_sichern(ko1_, "PAAPEX0000000000008", {}, to1_)
        ko2_, to2_ = _SO(open_reicht=False), []
        ro2_ = ob._cdp_konto_sichern(ko2_, "PAAPEX0000000000008", {}, to2_)
    finally:
        ob._warte = alt_w
        ob.CDP_NIE_MAXIMIEREN = True
    # NIE MAXIMIEREN (Finn 01.10.2026 11:29 UTC, Moritz: offenes Panel 113 px → Maximize → Kontextmenü oben nicht klickbar → Login-Wechsel tot)
    class _SN(_SO):
        def __init__(self, zu=False, **kw):
            _SO.__init__(self, open_reicht=False, **kw); self.zu = zu
        def klick(self, r, n, toast_ok=False):
            if n == "Konto-Umschalter":
                self.klicks.append(n); self.offen = True; return True   # Liste geht auch im niedrigen Panel auf
            return _SO.klick(self, r, n, toast_ok)
    ob._warte = lambda a_, b_: None
    try:
        kn1_, tn1_ = _SN(zu=False), []
        rn1_ = ob._cdp_konto_sichern(kn1_, "PAAPEX0000000000008", {}, tn1_)
        kn2_, tn2_ = _SN(zu=True), []
        rn2_ = ob._cdp_konto_sichern(kn2_, "PAAPEX0000000000008", {}, tn2_)
    finally:
        ob._warte = alt_w
    chk(rn1_[0] and kn1_.klicks == ["Konto-Umschalter", "Konto PAAPEX0000000000008"] and not kn1_.gross,
        f"nie maximieren: Panel offen (49 px, „Collapse panel“) zählt als ok → direkt Umschalter → Konto ({kn1_.klicks})")
    chk(rn2_[0] and kn2_.klicks == ["Order-Panel öffnen (Open panel)", "Konto-Umschalter", "Konto PAAPEX0000000000008"]
        and not any("Maximize" in x for x in kn2_.klicks), f"nie maximieren: Panel zu → nur „Open panel“, auch wenn es niedrig bleibt ({kn2_.klicks})")
    chk(ro1_[0] and ko1_.klicks == ["Order-Panel öffnen (Open panel)", "Konto-Umschalter", "Konto PAAPEX0000000000008"]
        and not any("Maximize" in x for x in ko1_.klicks), f"eingeklappt → „Open panel“ reicht → kein Maximize ({ko1_.klicks})")
    chk(ro2_[0] and ko2_.klicks[:2] == ["Order-Panel öffnen (Open panel)", "Order-Panel aufklappen (Maximize panel)"]
        and any("Rückfall" in x for x in to2_), f"Open panel zu niedrig → Rückfall Maximize ({ko2_.klicks})")
    # Am Ende „Restore panel" (Finn 01.10.2026, erster Orbit-V3-Trade: „am Ende einfach noch mal auf Restore drücken")
    class _SR:
        def __init__(self, maxi): self.maxi, self.klicks = maxi, []
        def lese_js(self, a, timeout=8):
            if "elementFromPoint" in a:
                return {"frei": True, "was": ""}
            return {"leiste": [56, 0, 1194, 38], "unter_leiste": 915 if self.maxi else 113,
                    "max_knopf": {"rect": [1240, 0, 38, 38], "aria": "Restore panel" if self.maxi else "Maximize panel"}}
        def klick(self, r, n, toast_ok=False):
            self.klicks.append(n); self.maxi = False; return True
    ob._warte = lambda a_, b_: None
    try:
        sr1_, tr1_ = _SR(True), []
        rr1_ = ob._cdp_panel_zurueck(sr1_, tr1_)
        sr2_, tr2_ = _SR(False), []
        rr2_ = ob._cdp_panel_zurueck(sr2_, tr2_)
    finally:
        ob._warte = alt_w
    chk(rr1_ and sr1_.klicks == ["Broker-Panel am Ende wiederherstellen (Restore panel)"] and "Panel zurück in normaler Größe (Chart sichtbar)" in tr1_
        and not rr2_ and sr2_.klicks == [] and tr2_ == [] and ob._cdp_panel_zurueck(object(), []) is False,
        f"Ende: maximiert → EIN Restore-Klick, sonst nichts ({sr1_.klicks}, {tr1_})")
    chk(sum(_i.getsource(f_).count("_cdp_panel_zurueck(sitz[0], trail)") for f_ in (ob.modus_tvlesen_cdp, ob.modus_tvkette_cdp, ob.modus_tvclose_cdp)) == 3,
        "Restore am Ende in Lesen, Order und Schließen (Orbit), nicht in Topstep")
    # Ticket „Start creating order" (keine Seite, Symbol unlesbar) → erst Seite, dann ist das Symbol im Knopf (Moritz 01.10.2026 00:51 UTC)
    class _ST:
        def __init__(self): self.seite, self.klicks = None, []
        def stand(self, opts=None):
            kk = {"symbol": "MNQZ6", "seite": "buy", "text": "Buy 1 MNQZ6 MARKET", "rect": [1340, 820, 280, 50]} if self.seite else {}
            return {"ticket": {"da": True, "symbol": None, "kaufen": {"rect": [1540, 230, 90, 40]}, "verkaufen": {"rect": [1340, 230, 90, 40]}},
                    "kauf_knopf": kk}
        def klick(self, r, n, toast_ok=False):
            self.klicks.append(n)
            if n.startswith("Seite BUY"): self.seite = "buy"
            return True
        def lese_js(self, a, timeout=8): return {}
        def taste(self, k, modifiers=0): pass
    ob._warte = lambda a_, b_: None
    try:
        sy_, ty_ = _ST(), []
        ry_ = ob._cdp_ticket_fuellen(sy_, sy_.stand(), {"richtung": "buy", "menge": 1, "tp": None, "sl": None}, "MNQZ6", {}, ty_)
    finally:
        ob._warte = alt_w
    chk(sy_.klicks[:1] == ["Seite BUY (vor dem Symbol)"] and ry_[1] != "asset" and "Symbol steht: MNQZ6" in ty_,
        f"Ticket ohne Seite: erst BUY, dann Symbol lesbar — kein „Symbol nicht einstellbar“ ({sy_.klicks}, {ry_[1]}, {ty_[:3]})")
    # Erster Lauf nach > 12 h (Finn 01.10.2026 12:28 UTC): Merk-Datei alt → vor dem Lauf Railway fragen, nicht stumm UIA
    _alt_l, _alt_h, _alt_p = ob._augen_json_lesen, ob._augen_regel_holen, ob._augen_pc_id
    gefragt_ = []
    try:
        ob._augen_pc_id = lambda: "pc-test01"
        ob._augen_regel_holen = lambda pc: (gefragt_.append(pc), "cdp")[1]
        ob._augen_json_lesen = lambda n: {"augen": "cdp", "at": ob.time.time() - 13 * 3600, "pc": "pc-test01"}
        m_alt = ob.augen_modus_lauf()
        ob._augen_json_lesen = lambda n: None
        m_fehlt = ob.augen_modus_lauf()
        n_vorher = len(gefragt_)
        ob._augen_json_lesen = lambda n: {"augen": "cdp", "at": ob.time.time() - 60, "pc": "pc-test01"}
        m_frisch = ob.augen_modus_lauf()
        ob._augen_json_lesen = lambda n: {"augen": "uia", "at": ob.time.time() - 60, "pc": "pc-test01"}
        m_uia = ob.augen_modus_lauf()
        n_nachher = len(gefragt_)
    finally:
        ob._augen_json_lesen, ob._augen_regel_holen, ob._augen_pc_id = _alt_l, _alt_h, _alt_p
    chk(m_alt == "cdp" and m_fehlt == "cdp" and n_vorher == 2 and m_frisch == "cdp" and m_uia == "uia" and n_nachher == 2,
        f"Regel alt/fehlt → einmal Railway fragen (cdp), frisch cdp/uia → kein Netz ({m_alt}, {m_fehlt}, {m_frisch}, {m_uia}, {gefragt_})")
    # Seite: erster Klick ohne Hover-Beweis (kein Druck) → zweiter Versuch mit frischem Rechteck (Moritz 01.10.2026 12:50 UTC)
    class _SS(_ST):
        def __init__(self): _ST.__init__(self); self.seite, self.n = "buy", 0
        def stand(self, opts=None):
            d = _ST.stand(self, opts); d["kauf_knopf"] = {"symbol": "MNQZ6", "seite": self.seite, "text": ("Sell" if self.seite == "sell" else "Buy") + " 1 MNQZ6 MARKET", "rect": [1340, 820, 280, 50]}; return d
        def klick(self, r, n, toast_ok=False):
            self.klicks.append(n)
            if n.startswith("Seite SELL"):
                self.n += 1
                if self.n >= 2: self.seite = "sell"
                return self.n >= 2
            return True
    ob._warte = lambda a_, b_: None
    try:
        ss_, ts_ = _SS(), []
        rs_ = ob._cdp_ticket_fuellen(ss_, ss_.stand(), {"richtung": "sell", "menge": 1, "tp": None, "sl": None}, "MNQZ6", {}, ts_)
    finally:
        ob._warte = alt_w
    chk(ss_.klicks[:2] == ["Seite SELL", "Seite SELL (Versuch 2)"] and "Seite = SELL" in ts_ and "Seite steht" not in str(rs_[2]),
        f"Seite: erster Klick ohne Hover → zweiter Versuch klappt ({ss_.klicks}, {rs_[1]}, {rs_[2][:60]})")
    # Symbolwechsel setzt das Ticket auf „Start creating order" zurück → Seite NACH dem Watchlist-Klick wählen (01.10.2026 13:50 UTC)
    class _SW(_ST):
        def __init__(self): _ST.__init__(self); self.sym, self.seite = "MNQZ6", "buy"
        def stand(self, opts=None):
            kk = {"symbol": self.sym, "seite": self.seite, "text": f"Buy 1 {self.sym} MARKET", "rect": [1340, 820, 280, 50]} if self.seite else {}
            return {"ticket": {"da": True, "symbol": None, "kaufen": {"rect": [1540, 230, 90, 40]}, "verkaufen": {"rect": [1340, 230, 90, 40]},
                               "symbolsuche": {"watchlist": [{"symbol": "NQZ2026", "rect": [2380, 250, 80, 20]}]}}, "kauf_knopf": kk}
        def klick(self, r, n, toast_ok=False):
            self.klicks.append(n)
            if n.startswith("Watchlist"): self.sym, self.seite = "NQZ6", None      # Ticket zurückgesetzt, Knopf ohne Symbol
            elif n.startswith("Seite BUY"): self.seite = "buy"
            return True
    ob._warte = lambda a_, b_: None
    try:
        sw_, tw_ = _SW(), []
        rw_ = ob._cdp_ticket_fuellen(sw_, sw_.stand(), {"richtung": "buy", "menge": 1, "tp": None, "sl": None}, "NQZ6", {}, tw_)
    finally:
        ob._warte = alt_w
    chk("Seite BUY (nach dem Symbol)" in sw_.klicks and any(x.startswith("Symbol steht: NQZ6") for x in tw_) and rw_[1] != "asset",
        f"Symbolwechsel → Ticket ohne Seite → Seite nachgewählt → Symbol lesbar ({sw_.klicks}, {rw_[1]}, {[x for x in tw_ if 'Symbol' in x]})")
    fj_ = ob.cdp_panel_frei_js([1482, 907, 38, 38])
    chk("elementFromPoint(1501.0,926.0)" in fj_ and "toggle-visibility-button" in fj_ and "#overlap-manager-root" in fj_ and "toastGroup-" in fj_,
        "Frei-Probe: Knopfmitte, Dialog/Overlay verdeckt, Meldungen frei")
    chk(_i.getsource(ob._cdp_anmelden).count("_cdp_verbunden_lesen(") == 1 and "cdp_konto_verbunden(s.stand(opts))" not in _i.getsource(ob._cdp_anmelden),
        "Warten nach dem Login klappt das Panel auf")
    # Tradovate-Formular fliegt beim Laden herein (Live 16:33 UTC): erst ruhig, Fokus nicht da → neu lesen, bis 2× neu klicken
    chk(ob.cdp_rect_gleich([10, 20, 100, 30], [10.5, 20, 100, 30]) and not ob.cdp_rect_gleich([10, 20, 100, 30], [60, 20, 100, 30])
        and not ob.cdp_rect_gleich(None, [1, 1, 1, 1]), "Rechteck gleich (±1 px)")
    q_an3 = _i.getsource(ob._cdp_anmelden)
    chk(q_an3.index("_cdp_formular_ruhig(ort, trail)") < q_an3.index('"Benutzerfeld")') and "for k_versuch in range(3):" in q_an3
        and "kam dreimal nicht an" in q_an3, "Login: Formular-Ruhe vor dem Klick, Benutzerfeld bis 3 Versuche mit Fokus-Beweis")
    W = ob.tv_konto_wort_passt
    chk(W("TDFYU000000000 tradovate.com", "TDFYU000000000") and not W("APEX_000000TDFYU000000000", "TDFYU000000000")
        and not W("APEX_000000", "TDFYU000000000"), "Vorschlag nur mit dem Username als ganzem Wort (angehängter Name zählt nicht)")
    nadel = type("N", (), {"search": staticmethod(lambda n: W(n, "TDFYU000000000"))})
    liste = [("APEX_000000", (300, 400, 600, 440), "ListItem"), ("TDFYU000000000 tradovate.com", (300, 450, 600, 490), "ListItem"),
             ("TDFYU000000000", (300, 300, 600, 330), "Text")]
    gef = ob.tv_uia_namen_filtern(liste, nadel, typ_vorrang=None, ohne=(290, 295, 610, 335))
    chk(len(gef) == 1 and gef[0]["punkt"] == (450, 470), f"Vorschlagsliste: genau der Tradeify-Eintrag, das Benutzerfeld ist ausgenommen ({gef})")
    for f in (ob.modus_tvlesen_cdp, ob.modus_tvkette_cdp):
        src = _i.getsource(f)
        chk("_cdp_konto_mit_login(sitz" in src and "_cdp_sitzung_holen(cmd" in src and "s = sitz[0]" in src,
            f"{f.__name__}: Auto-Login + neue Sitzung nach dem Tab-Tausch")
    chk("_cdp_konto_mit_login" not in _i.getsource(ob.modus_k3), "K3-Handlauf bleibt unverändert (eigener Login-Wechsel)")
    chk("ziel=None" in _i.getsource(ob._AugenSitzung.__init__), "_AugenSitzung nimmt einen bestimmten Tab")
    if ok:
        print("✓ CDP-Login: nur bei kein Broker/0 Treffern, Connect-Dialog + Demo + Don't remember me, Username exakt, nie Passwort/Allow")
    return ok


def test_cdp_konto_regression_865():
    """Regression .865 (30.09.2026, pc-cccccc, Orbit-Endlesung Plan …): nach „Maximize panel" stand der Konto-Umschalter oben
    ([72,59] unter der Broker-Leiste [56,0]), augen.js ≤ 0.7.3 fand ihn nicht, hielt ihn für eine offene Liste mit 1 Zeile, das Ziel
    stand darin 0× → Login-Weg las den Login als '-' und meldete eine richtige Tradovate-Sitzung ab. Geprüft: fremde Liste = nie Beleg,
    Abmelden nur mit Beleg, unlesbar = ehrlich raus, neues augen.js findet den Umschalter in beiden Lagen (Quelltext)."""
    import order_bot as ob
    ok = True

    def chk(bed, text):
        nonlocal ok
        if not bed:
            print("  ✗ Regression .865: " + text)
            ok = False
    Z7, Z8 = "PAAPEX0000000000007", "PAAPEX0000000000008"
    MAX = {"leiste": [56, 0, 1194, 38], "unter_leiste": 735, "max_knopf": {"rect": [1212, 0, 38, 38], "aria": "Restore panel"}}

    class _Max:
        """Puls-Chrome mit maximiertem Panel (Inventar 03:13 UTC). alt=True: augen.js 0.7.3 (Umschalter unsichtbar, er selbst als
        „Liste"); alt=False: 0.7.4 (Umschalter [72,59], Liste geht erst nach dem Klick auf)."""
        ws = None

        def __init__(self, alt, aktiv=Z8 + "USD", ziele=(Z7, Z8), voll=True, offen=False, esc_wirkt=True, eintrag_druck=True):
            self.alt, self.aktiv, self.ziele, self.offen, self.klicks = alt, aktiv, ziele, offen, []
            self.voll, self.esc_wirkt, self.eintrag_druck = voll, esc_wirkt, eintrag_druck

        def stand(self, opts=None):
            if self.alt:
                return {"konto": {"panel": "offen", "schalter": None, "aktiv": "", "liste_offen": True,
                                  "eintraege": [{"text": Z8 + "USD", "rect": [72, 59, 199, 28], "aktiv": False}]}}
            ein = [{"text": z + "USD", "rect": [78, 90 + 32 * i, 228, 32], "aktiv": (z + "USD") == self.aktiv} for i, z in enumerate(self.ziele)]
            return {"konto": {"panel": "offen", "panel_lage": "maximiert", "schalter": {"rect": [72, 59, 199, 28]}, "aktiv": self.aktiv,
                              "liste_offen": self.offen, "liste_voll": self.offen and self.voll, "eintraege": ein if self.offen else []}}

        def lese_js(self, a, timeout=8):
            return {"frei": True, "was": ""} if "elementFromPoint" in a else dict(MAX)

        def werbung_weg(self, zwang=False):
            return 0

        def taste(self, k, modifiers=0):
            self.klicks.append("Taste " + k)
            if k == "Escape" and self.esc_wirkt:
                self.offen = False

        def klick(self, r, n, toast_ok=False):
            self.klicks.append(n)
            if n == "Konto-Umschalter":
                self.offen = True
            elif n.startswith("Konto "):
                if not self.eintrag_druck:
                    return False
                self.aktiv, self.offen = n.split(" ", 1)[1] + "USD", False
            return True
    alt_w = ob._warte
    ob._warte = lambda a_, b_: None
    try:
        # 1) altes augen.js im maximierten Panel: nichts gewählt, kein Login-Beleg (früher: Esc → konto_treffer 0 → Login → Log out)
        k1, t1 = _Max(alt=True), []
        r1 = ob._cdp_konto_sichern(k1, Z7, {}, t1)
        # 2) neues augen.js, maximiert, aktiv …0008, Ziel …0007: Umschalter → Liste → Ziel
        k2, t2 = _Max(alt=False), []
        r2 = ob._cdp_konto_sichern(k2, Z7, {}, t2)
        # 3) Konto steht schon (aktiv = Ziel): weder Liste noch Login noch Panel-Klick
        k3, t3 = _Max(alt=False, aktiv=Z7 + "USD"), []
        r3 = ob._cdp_konto_sichern(k3, Z7, {}, t3)
        # 4) selbst geöffnete Liste, Ziel (Tradeify) 0×, aktives Apex-Konto lesbar → Beleg über die Familie (liste_aktiv);
        #    4b) Ziel vom SELBEN Apex-User 0× → nie Beleg (steht nur außer Sicht); 5) unlesbar → kein Beleg
        TD1, TD2, TD3 = "TDFYSL150300000000", "TDFYSL150110000000", "TDFYSL150111222333"
        k4, t4 = _Max(alt=False, ziele=(Z8, "PAAPEX0000000000009")), []
        r4 = ob._cdp_konto_sichern(k4, TD1, {}, t4)
        k4b, t4b = _Max(alt=False, ziele=(Z8, "PAAPEX0000000000009")), []
        r4b = ob._cdp_konto_sichern(k4b, Z7, {}, t4b)
        k5, t5 = _Max(alt=False, aktiv="Konto wählen", ziele=(Z8,)), []
        r5 = ob._cdp_konto_sichern(k5, Z7, {}, t5)
        # Tradeify↔Tradeify (keine User-ID in der Nummer): abgeschnittene Liste bzw. Liste ohne aktives Konto → kein Beleg; vollständig → Beleg
        k6, t6 = _Max(alt=False, aktiv=TD1 + "USD", ziele=(TD1, TD3), voll=False), []
        r6 = ob._cdp_konto_sichern(k6, TD2, {}, t6)
        k7, t7 = _Max(alt=False, aktiv=TD1 + "USD", ziele=(TD3, "TDFYSL150444555666")), []
        r7 = ob._cdp_konto_sichern(k7, TD2, {}, t7)
        k7b, t7b = _Max(alt=False, aktiv=TD1 + "USD", ziele=(TD1, TD3)), []
        r7b = ob._cdp_konto_sichern(k7b, TD2, {}, t7b)
        # Konto steht, alte Liste offen → Esc, dann ok; Liste bleibt trotz Esc → ehrlich raus (Reiter lägen darunter)
        k8, t8 = _Max(alt=False, aktiv=Z7 + "USD", offen=True), []
        r8 = ob._cdp_konto_sichern(k8, Z7, {}, t8)
        k9, t9 = _Max(alt=False, aktiv=Z7 + "USD", offen=True, esc_wirkt=False), []
        r9 = ob._cdp_konto_sichern(k9, Z7, {}, t9)
        # Eintrag nicht gedrückt → Esc, ehrlich raus, keine weiteren Runden
        k10, t10 = _Max(alt=False, eintrag_druck=False), []
        r10 = ob._cdp_konto_sichern(k10, Z7, {}, t10)
        # Eval-ID gegen aktives PA-Konto gleicher Nummer: steht NICHT (Liste: nur PA-Konten → 0×)
        k11, t11 = _Max(alt=False, aktiv="PAAPEX0000000000007USD", ziele=(Z7, Z8)), []
        r11 = ob._cdp_konto_sichern(k11, "APEX0000000000007", {}, t11)
    finally:
        ob._warte = alt_w
    chk(not r1[0] and r1[1] == "konto_nicht_erreicht" and k1.klicks == ["Taste Escape"] and "konto_treffer" not in r1[4]
        and not ob.cdp_login_noetig(r1[1], r1[4]) and "kein Login" in r1[2] and any("nicht von diesem Lauf" in x for x in t1),
        f"altes augen.js maximiert: EINMAL Esc, nichts gewählt, KEIN Login-Weg ({k1.klicks}, {r1[2]})")
    chk(r2[0] and k2.klicks == ["Konto-Umschalter", "Konto " + Z7, "Broker-Panel am Ende wiederherstellen (Restore panel)"], f"maximiert: Umschalter oben → Liste → Ziel → Restore (01.10.2026) ({k2.klicks})")
    chk(r3[0] and k3.klicks == ["Broker-Panel am Ende wiederherstellen (Restore panel)"] and r3[4].get("konto_aktiv") == Z7 + "USD", f"Konto steht (maximiert) → nur Restore (01.10.2026) ({k3.klicks})")
    chk(not r4[0] and r4[4].get("konto_treffer") == 0 and r4[4].get("liste_aktiv") == Z8 + "USD" and ob.cdp_login_noetig(r4[1], r4[4])
        and k4.klicks == ["Konto-Umschalter", "Taste Escape"], f"eigene Liste, Tradeify-Ziel 0×, Apex aktiv → Login-Beleg ({r4[4]})")
    chk(not r4b[0] and r4b[4].get("konto_treffer") is None and not ob.cdp_login_noetig(r4b[1], r4b[4]) and "selben Apex-Login" in r4b[2],
        f"Ziel vom selben Apex-User 0× → nie Login ({r4b[2]})")
    chk(not r7b[0] and r7b[4].get("konto_treffer") == 0 and r7b[4].get("liste_aktiv") == TD1 + "USD",
        f"Tradeify↔Tradeify mit vollständiger Liste inkl. aktivem Konto → Beleg ({r7b[4]})")
    chk(not r5[0] and r5[4].get("konto_treffer") is None and not ob.cdp_login_noetig(r5[1], r5[4]) and "nicht lesbar" in r5[2],
        f"eigene Liste, Ziel 0×, aktiv unlesbar → kein Login ({r5[2]})")
    chk(not r6[0] and r6[4].get("konto_treffer") is None and not ob.cdp_login_noetig(r6[1], r6[4]) and "nicht vollständig" in r6[2],
        f"Tradeify: abgeschnittene Liste, Ziel 0× → kein Login-Beleg ({r6[2]})")
    chk(not r7[0] and r7[4].get("konto_treffer") is None and "steht nicht in der Liste" in r7[2],
        f"Liste ohne das aktive Konto → kein Login-Beleg ({r7[2]})")
    chk(r8[0] and k8.klicks == ["Taste Escape", "Broker-Panel am Ende wiederherstellen (Restore panel)"] and not k8.offen, f"Konto steht + alte Liste offen → Esc, dann Restore (01.10.2026) ({k8.klicks})")
    chk(not r9[0] and r9[1] == "konto_nicht_erreicht" and "geht mit Esc nicht zu" in r9[2] and k9.klicks == ["Taste Escape"],
        f"Konto steht, Liste bleibt offen → nichts lesen ({r9[2]})")
    chk(not r10[0] and k10.klicks == ["Konto-Umschalter", "Konto " + Z7, "Taste Escape"] and not k10.offen and "nicht gedrückt" in r10[2],
        f"Eintrag nicht gedrückt → Esc, ehrlich raus ({k10.klicks})")
    chk(not r11[0] and k11.klicks[:1] == ["Konto-Umschalter"] and r11[4].get("konto_treffer") is None and "selben Apex-Login" in r11[2],
        f"Eval-ID steht nicht, nur weil das PA-Konto gleicher Nummer aktiv ist ({k11.klicks}, {r11[2]})")
    P = ob.cdp_konto_passt
    chk(P("PAAPEX0000000000007USD", "PAAPEX0000000000007") and not P("PAAPEX0000000000007USD", "APEX0000000000007")
        and P("APEX0000000000007 USD", "APEX0000000000007") and P("PA-1234567 · Tradeify · $50k", "PA1234567")
        and P("TDFYSL150300000000 USD", "TDFYSL150300000000") and not P("PAAPEX00000000000071USD", "PAAPEX0000000000007")
        and not P("PAAPEX0000000000007XYZ", "PAAPEX0000000000007") and not P("PA-12", "12") and not P("x", None),
        "Konto-Abgleich streng: ganzes Wort, nur Währungs-Anhang (PA ≠ Eval)")
    chk(ob.cdp_kontonr("PAAPEX0000000000008USD") == "PAAPEX0000000000008" and ob.cdp_kontonr("Konto wählen") == "" and ob.cdp_kontonr(None) == ""
        and ob.cdp_kontonr("Apex · PAAPEX0000000000009USD") == "PAAPEX0000000000009" and ob.cdp_kontonr("TDFYSL150300000000 USD") == "TDFYSL150300000000",
        "Kontonummer aus dem Umschalter-Text (auch mit Beiwerk davor)")
    # 05.10.2026: Nummer mit nur VIER Endziffern (mindestens 10 Buchstaben davor) — vorher „steht im Dropdown 0x“
    V4 = "FNFTCHABCDEFGHIJKLMN1234"
    chk(ob.cdp_kontonr(V4 + "USD") == V4 and ob.cdp_kontonr(V4 + " USD") == V4 and ob.k3_kontonr({"text": V4 + " USD"}) == V4
        and ob.cdp_kontonr("NQZ2026") == "" and ob.cdp_kontonr("MNQZ2026") == "" and ob.cdp_kontonr("MNQZ26") == ""
        and ob.cdp_kontonr("ACCOUNTS") == "" and ob.cdp_kontonr("ABCDEFGHIJ12") == "" and ob.cdp_kontonr("ABCDEFGHI1234") == ""
        and ob.cdp_kontonr("FNFTCHABCDEFGHIJKLMN12345USD") == "FNFTCHABCDEFGHIJKLMN12345"
        and ob.k3_nr_treffer("TDFYSL150300000000").group(0) == "TDFYSL150300000000" and ob.k3_nr_treffer("NQZ2026") is None,
        "Kontonummer mit 4 Endziffern erkannt (mindestens 10 Buchstaben davor), Kontrakte und kurze Wörter nicht; alte Regel zuerst")
    chk(ob.cdp_liste_beleg({"liste_kurz": True, "eintraege": [{"text": V4 + "USD"}, {"text": "FNFTCHABCDEFGHIJKLMN56789USD"}]},
                           V4 + "USD", "FNFTCHZZZZZZZZZZZZZZ54321") == (True, "")
        and ob.cdp_konto_eintrag([{"text": V4 + "USD"}, {"text": "FNFTCHABCDEFGHIJKLMN56789USD"}], V4)[1] == 1,
        "aktives Konto mit 4 Endziffern ist lesbar (Login-Beleg) und als Listenzeile genau einmal zu finden")
    F = ob.cdp_konto_familie
    chk(F("PAAPEX0000000000008") == F("APEX0000000000007") == "apex:000000" and F("PAAPEX1111110000002") == "apex:111111"
        and F("TDFYSL150300000000") == F("FTDFYSLX150200000000") == "tradeify" and F("LFE10000000000000") == "lucid"
        and F("EXPRESS-V2-000000-00000000") == "" and F("APEX00000000000") == "" and F(None) == "",
        "Login-Familie aus der Kontonummer (Apex mit User-ID, Tradeify, Lucid)")
    chk(F("FNFTCH0000000000000") == "fundednext" and F("MFFUEVPRO000000000") == "mff"
        and ob.cdp_liste_beleg({"liste_voll": False}, "FTDFYSLX150200000000", "FNFTCH0000000000000") == (True, ""),
        "Login-Familie FundedNext Futures / MyFundedFutures — Wechsel von Tradeify auch bei scrollbarer Liste")
    chk(ob.cdp_ein_konto_beleg("TDFYSL150100000000USD", "TDFYSL150200000000") and not ob.cdp_ein_konto_beleg("TDFYSL150100000000USD", "TDFYSL150100000000")
        and not ob.cdp_ein_konto_beleg("-", "TDFYSL150200000000") and not ob.cdp_ein_konto_beleg("", "TDFYSL150200000000")
        and not ob.cdp_ein_konto_beleg("PAAPEX0000000000007USD", "PAAPEX0000000000008"),
        "Login mit einem Konto: lesbar + anderes Konto = Beleg, gleiches/unlesbares nie")
    import io as _io, contextlib as _cl, json
    _n = {"n": 0}
    def _lauf_to(c):
        _n["n"] += 1
        print(json.dumps({"ok": False, "code": "cdp_fehler", "msg": "Puls-Chrome/CDP: TimeoutError: timed out", "trail": "a"} if _n["n"] == 1
                         else {"ok": True, "code": "", "msg": "gelesen", "trail": "b"}))
    _b = _io.StringIO()
    with _cl.redirect_stdout(_b):
        ob.tvlesen_cdp_mit_wiederholung({}, lauf=_lauf_to)
    _r = json.loads(_b.getvalue().strip().splitlines()[-1])
    chk(_n["n"] == 2 and _r.get("ok") is True and "1. Versuch" in _r.get("trail", ""), "Lesen: Timeout → einmal neu, Ergebnis des zweiten Laufs")
    B = ob.cdp_liste_beleg
    ko_v = {"liste_voll": True, "eintraege": [{"text": TD1 + "USD"}]}
    chk(B({}, Z8 + "USD", TD1) == (True, "") and B({}, Z8 + "USD", "PAAPEX1111110000002") == (True, "")
        and not B(ko_v, Z8 + "USD", Z7)[0] and B(ko_v, TD1 + "USD", TD2) == (True, "") and not B({"liste_voll": False, "eintraege": ko_v["eintraege"]}, TD1, TD2)[0]
        and not B(ko_v, "-", TD2)[0], "Beleg: andere Firma/anderer Apex-User sicher, gleicher Apex-User nie, sonst nur mit voller Liste")
    class _EscS:
        def __init__(self, wirft):
            self.wirft, self.n = wirft, 0

        def taste(self, k, modifiers=0):
            self.n += 1
            if self.wirft:
                raise RuntimeError("Puls-Chrome kommt nicht in den Vordergrund")
    e1, e2, te = _EscS(False), _EscS(True), []
    chk(ob._cdp_esc(e1, {"popups": [{"titel": "Session disconnected"}]}, te, "x") is False and e1.n == 0
        and ob._cdp_esc(e2, {}, te, "y") is False and ob._cdp_esc(e1, {}, te, "z") is True and e1.n == 1,
        f"Esc nie über einem Dialog, Windows-Fehler wirft nicht ({te})")
    # Abmelde-Regel (rein rechnend)
    A = ob.cdp_abmelden_erlaubt
    beleg = {"konto_treffer": 0, "liste_aktiv": Z8 + "USD"}
    chk(A("", beleg) == (False, "unlesbar") and A("-", beleg) == (False, "unlesbar") and A(None, None) == (False, "unlesbar")
        and A("Konto wählen", beleg) == (False, "unlesbar"), "unlesbarer Login → nie abmelden")
    chk(A(Z8 + " USD", beleg) == (True, "") and A(Z8 + "USD", {}) == (False, "ohne_beleg")
        and A(Z8 + "USD", {"konto_treffer": 0}) == (False, "ohne_beleg") and A(Z8 + "USD", {"konto_treffer": None, "liste_aktiv": Z8})
        == (False, "ohne_beleg") and A("PAAPEX0000000000009USD", beleg) == (False, "anders"),
        "abmelden nur mit Beleg (eigene Liste, 0×) und gleichem aktivem Konto")

    # Login-Weg mit Attrappen: ctx (Kontextmenü neben „Tradovate") da, Konto unlesbar → login_unlesbar, KEIN _cdp_abmelden
    class _Ort:
        def __init__(self, *a, **k):
            pass

        def blick(self):
            return {"ctx": {"rect": [166, 8, 22, 22]}, "dialoge": [], "url": "https://www.tradingview.com/chart/x/"}
    gesehen = {"ab": 0, "lesen": ""}
    alt = {n: getattr(ob, n) for n in ("_K3Ort", "_cdp_verbunden_lesen", "_cdp_abmelden", "_cdp_tab_mit_link", "_cdp_login_sichern",
                                        "_cdp_sitzung_zurueck")}

    def _ab(s, opts, trail):
        gesehen["ab"] += 1
        return False, "Attrappe: nicht abgemeldet"

    def _tab(sitz, url, trail):
        raise RuntimeError("Attrappe: kein neuer Tab erwartet")
    sz = type("Sz", (), {"ws": None})()
    ob._K3Ort, ob._cdp_abmelden, ob._cdp_tab_mit_link = _Ort, _ab, _tab
    ob._cdp_verbunden_lesen = lambda s, o, t: gesehen["lesen"]
    ob._cdp_login_sichern = lambda res, trail: None
    ob._cdp_sitzung_zurueck = lambda s, o, t: False
    try:
        cmd = {"tv_username": "APEX_000000"}
        tv1 = []
        v1 = ob._cdp_tradovate_verbinden([sz], cmd, {}, tv1, beleg={"konto_treffer": 0, "liste_aktiv": Z8})
        gesehen["lesen"] = Z8 + "USD"
        v2 = ob._cdp_tradovate_verbinden([sz], cmd, {}, [], beleg={})
        v3 = ob._cdp_tradovate_verbinden([sz], cmd, {}, [], beleg={"konto_treffer": 0, "liste_aktiv": Z8 + "USD"})
        ab_vor_e2e = gesehen["ab"]
        # Ende zu Ende wie am 30.09.: kein Umschalter (kein_broker), Tradovate verbunden, Konto unlesbar → ehrlich raus, nichts abgemeldet
        gesehen["lesen"] = ""

        class _Leer(_Max):
            def stand(self, opts=None):
                return {"konto": {"panel": "offen", "schalter": None, "aktiv": "", "liste_offen": False, "eintraege": []}}
        ob._warte = lambda a_, b_: None
        res_e, tr_e = {}, []
        e2e = ob._cdp_konto_mit_login([_Leer(alt=False)], Z7, {}, cmd, tr_e, res_e)
        # altes augen.js maximiert über den ganzen Login-Weg: kein Login-Versuch
        res_a, tr_a = {}, []
        e2a = ob._cdp_konto_mit_login([_Max(alt=True)], Z7, {}, cmd, tr_a, res_a)
        # kein Umschalter, aber Tradovate zeigt ein lesbares Konto ohne Beleg → zweimal 'steht', nichts abgemeldet, Code 409-fähig
        gesehen["lesen"] = Z8 + "USD"
        res_s, tr_s = {}, []
        e2s = ob._cdp_konto_mit_login([_Leer(alt=False)], Z7, {}, cmd, tr_s, res_s)
    finally:
        for n, f in alt.items():
            setattr(ob, n, f)
        ob._warte = alt_w
    chk(v1[0] == "login_unlesbar" and "nichts abgemeldet" in v1[1] and any("NICHT abgemeldet" in x for x in tv1),
        f"ctx da, Konto unlesbar → login_unlesbar ({v1})")
    chk(v2 == ("", "", "steht"), f"Konto lesbar ohne Beleg → nicht abmelden, Konto-Schritt neu ({v2})")
    chk(v3[0] == "abmelden" and ab_vor_e2e == 1, f"nur mit Beleg wird abgemeldet (Attrappe) ({v3}, {ab_vor_e2e})")
    chk(not e2e[0] and e2e[1] == "konto_nicht_erreicht" and "nicht lesbar" in e2e[2] and gesehen["ab"] == 1
        and (res_e.get("login") or {}).get("code") == "login_unlesbar", f"kein_broker + unlesbar → ehrlich raus, nichts abgemeldet ({e2e[2]})")
    chk(not e2a[0] and "login" not in res_a and not any("[Login]" in x for x in tr_a), f"altes augen.js maximiert → kein Login-Versuch ({tr_a})")
    chk(not e2s[0] and e2s[1] == "konto_nicht_erreicht" and gesehen["ab"] == 1 and (res_s.get("login") or {}).get("durchgaenge") == 2
        and "nichts abgemeldet" in e2s[2] and "auch nach dem Tradovate-Login" not in e2s[2],
        f"zweimal 'steht' → Schluss, nichts abgemeldet, konto_nicht_erreicht ({e2s[1]}, {e2s[2]})")

    # augen.js 0.7.4 (nur Quelltext — kein Node auf dem Mac): Umschalter relativ zur Broker-Leiste, Lage, keine Ein-Zeilen-Liste ohne Umschalter
    import os as _os
    js = open(_os.path.join(_os.path.dirname(_os.path.abspath(ob.__file__)), "augen.js"), encoding="utf-8").read()
    chk("function kontoSchalter()" in js and "r.top >= lr.top - 4" in js and "var s = kontoSchalter();" in js
        and "(eintraege.length === 1 && !!s.el && !eintraege[0].aktiv)" in js and "panel_lage: lage" in js
        and "VERSION = '0.7.8'" in js, "augen.js 0.7.4+: Umschalter unter der Broker-Leiste (beide Lagen), panel_lage, Liste nur mit Umschalter")
    chk("warnung" in ob.PULS_ERGEBNIS_FELDER and "unklar" in ob.PULS_ERGEBNIS_FELDER, "Ergebnis-Paket trägt warnung + unklar")
    # Login-Abriss (30.09.2026 03:23 UTC): Verbindung weg nach „Anmelden" → Spur mit Chrome-Zustand, EINMAL neu anhängen
    import inspect as _ia
    V = ob.cdp_verbindung_weg_urteil
    ta, tb = {"id": "a", "webSocketDebuggerUrl": "ws://a"}, {"id": "b", "webSocketDebuggerUrl": "ws://b"}
    chk(V(False, [])[0] == "chrome_weg" and V(False, [ta], "a")[0] == "chrome_weg" and V(True, [ta, tb], "b") == ("neu_anhaengen", tb)
        and V(True, [ta], "b") == ("tab_weg", None) and V(True, [ta]) == ("neu_anhaengen", ta) and V(True, [ta, tb])[0] == "tab_weg"
        and V(True, [])[0] == "tab_weg", "Verbindung weg: Chrome tot / nur DERSELBE Tab wird neu angehängt / sonst Tab weg")
    q_a = _ia.getsource(ob._cdp_anmelden)
    chk("except (OSError, RuntimeError)" in q_a and "cdp_verbindung_weg_urteil(" in q_a and "not neu_dran" in q_a
        and "sitz[0] = _AugenSitzung(" in q_a and '"chrome_weg"' in q_a
        and "sitz=sitz" in _ia.getsource(ob._cdp_tradovate_verbinden), "Login-Warten: Abriss ehrlich mit Chrome-Zustand, höchstens einmal neu anhängen")
    # Verhalten: Formular bereit → Login-Klick → 1. Blick reißt ab. (a) Chrome lebt + TV-Tab da → neu anhängen, Konto kommt → OK;
    # (b) Chrome tot → 'chrome_weg'; (c) zweiter Abriss nach dem Neu-Anhängen → 'verbindung' (kein drittes Anhängen)
    class _Eing:
        def klick(self, r, n, toast_ok=False, pruef=None):
            return True

        def fokus_im(self, r, n, versuche=3):
            return True

        def taste(self, k, modifiers=0):
            pass

    class _OrtA:
        name, eigen, eingabe = "Tradovate-Tab", True, _Eing()

        def blick(self):
            return {"login": {"user": {"gefuellt": True, "passt": True, "laenge_gleich": True, "rect": [1, 1, 50, 20]},
                              "pw": {"gefuellt": True, "rect": [1, 30, 50, 20]},
                              "knoepfe": [{"text": "Login", "rect": [1, 60, 80, 30]}]}}
    alt_a = {n: getattr(ob, n) for n in ("_cdp_formular_ruhig", "_cdp_verbunden_lesen", "_cdp_http", "_AugenSitzung", "_warte")}
    faelle = {}
    try:
        ob._cdp_formular_ruhig = lambda *a, **k: None
        ob._warte = lambda a_, b_: None
        for fall, lebt, abrisse, tid, fehler in (("a", True, 1, "t1", ConnectionAbortedError), ("b", False, 1, "t1", ConnectionAbortedError),
                                                 ("c", True, 2, "t1", ConnectionAbortedError), ("d", True, 1, "anderer", ConnectionAbortedError),
                                                 ("e", True, 2, "t1", TimeoutError), ("f", True, 1, "t1", RuntimeError)):
            zahl = {"n": 0, "neu": 0}

            def _lesen(s_, o_, t_, _z=zahl, _ab=abrisse, _f=fehler):
                _z["n"] += 1
                if _z["n"] <= _ab:
                    raise _f(10053, "Verbindung abgebrochen") if _f is ConnectionAbortedError else _f("CDP Runtime.evaluate: Target crashed")
                return "PAAPEX0000000000000USD"

            class _NeuS:
                ws = None

                def __init__(self, trail, ziel=None, _z=zahl):
                    _z["neu"] += 1
            ob._cdp_verbunden_lesen = _lesen
            ob._AugenSitzung = _NeuS
            ob._cdp_http = (lambda pfad, *a, _l=lebt, **k: (({"Browser": "x"} if pfad == "/json/version" else
                                                                 [{"type": "page", "id": "t1", "url": "https://www.tradingview.com/chart/x/",
                                                                   "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/t1"}]) if _l else None))
            sz, tr = [type("S0", (), {"ws": None, "target_id": tid, "_win_hwnd": 4711})()], []
            r_ = ob._cdp_anmelden(sz[0], _OrtA(), "APEX_000000", {}, tr, None, sitz=sz)
            faelle[fall] = (r_, zahl["neu"], isinstance(sz[0], _NeuS), tr, getattr(sz[0], "_win_hwnd", None))
    finally:
        for n, f in alt_a.items():
            setattr(ob, n, f)
    chk(faelle["a"][0] == ("", "") and faelle["a"][1] == 1 and faelle["a"][2] and any("neu an denselben TradingView-Tab" in x for x in faelle["a"][3]),
        f"Abriss, Chrome lebt → einmal neu anhängen, Login gilt ({faelle['a'][0]}, {faelle['a'][3][-3:]})")
    chk(faelle["b"][0][0] == "chrome_weg" and faelle["b"][1] == 0 and "beendet" in faelle["b"][0][1] and any("ANTWORTET NICHT" in x for x in faelle["b"][3]),
        f"Abriss, Chrome tot → chrome_weg, kein Anhängen ({faelle['b'][0]})")
    chk(faelle["c"][0][0] == "verbindung" and faelle["c"][1] == 1, f"zweiter Abriss → ehrlich 'verbindung', nur EIN Neu-Anhängen ({faelle['c'][0]}, {faelle['c'][1]})")
    chk(faelle["a"][4] == 4711, "Neu-Anhängen nimmt das gemerkte Fenster mit (zu() minimiert wieder)")
    chk(faelle["d"][0][0] == "verbindung" and faelle["d"][1] == 0 and "TradingView-Tab weg" in faelle["d"][0][1] and any("tab_weg" in x for x in faelle["d"][3]),
        f"Sitzungs-Tab weg, anderer TV-Tab da → NICHT an den anderen anhängen ({faelle['d'][0]})")
    chk(faelle["e"][0] == ("", "") and faelle["e"][1] == 0 and sum("antwortet gerade nicht" in x for x in faelle["e"][3]) == 1,
        f"Zeitüberschreitung ist kein Abriss: weiter warten, kein Neu-Anhängen, einmal vermerkt ({faelle['e'][3]})")
    chk(faelle["f"][0] == ("", "") and faelle["f"][1] == 1, "CDP-Fehlerantwort (Target crashed) wie ein Abriss: einmal neu anhängen")
    import inspect as _i
    chk("trail" in _i.signature(ob._cdp_nach_link).parameters and "_cdp_nach_link(s, opts, trail)" in _i.getsource(ob._cdp_tradovate_verbinden),
        "_cdp_nach_link bekommt die Spur (NameError seit .828)")
    chk("liste_voll" in js and "function listeVoll(els, ohne)" in js and "liste_voll: !!(offenListe && voll)" in js
        and "listeVoll(zeilenEl, schalterEl)" in js and js.index("if (ar.bottom > H + 1") < js.index("ab hier kein Listen-Container mehr"),
        "augen.js meldet liste_voll (auch der hohe Container wird geprüft)")
    chk("c === document.body" in js and "if (t > 2) return nein(" in js, "listeVoll: Ausreißer außerhalb des Listen-Containers → nicht voll")
    # LOGIN-WECHSEL BEIM LESEN (05.10.2026, Finn: „erkennt das falsche Tradovate-Konto und bricht einfach ab") — zwei Live-Befunde:
    # (A) kurze, ganz sichtbare Liste ohne Ziel galt als „nicht vollständig" (FundedNext↔FundedNext) → kein Beleg → Abbruch;
    # (B) der Pfeil neben „Tradovate" trägt keine Beschriftung mehr → ctx None → „nicht abgemeldet".
    FN1, FN2, FN3 = "FNFTCH000000000011111", "FNFTCH000000000022222", "FNFTCH000000000033333"
    ko_k = {"liste_voll": False, "liste_kurz": True, "liste_voll_grund": "Container scrollt (120 > 100, Ebene 1)",
            "eintraege": [{"text": FN1 + "USD"}, {"text": FN2 + "USD"}]}
    chk(B(ko_k, FN1 + "USD", FN3) == (True, "") and not B(dict(ko_k, liste_kurz=False), FN1 + "USD", FN3)[0]
        and "augen.js: Container scrollt" in B(dict(ko_k, liste_kurz=False), FN1 + "USD", FN3)[1]
        and not B(dict(ko_k, eintraege=[{"text": FN2 + "USD"}]), FN1 + "USD", FN3)[0]
        and not B(dict(ko_k, eintraege=[{"text": Z8 + "USD"}]), Z8 + "USD", Z7)[0],
        "kurze, ganz sichtbare Liste (liste_kurz) = Beleg bei gleicher Familie; ohne aktives Konto darin / gleicher Apex-User nie; Grund im Text")
    chk("function listeKurz(els, ohne)" in js and "els.length > 8" in js and "liste_kurz: !!(offenListe && kurzOk)" in js
        and "liste_voll_grund:" in js and "if (oben < hz + 8 || H - unten < hz + 8) return false;" in js,
        "augen.js 0.7.6: liste_kurz (≤ 8 Zeilen, Platz darüber und darunter) + liste_voll_grund")
    lb = ob.K3_LOGIN_BLICK_JS
    chk("ctxq = 'pfeil'" in lb and "mg.length === 1" in lb and "e.hasAttribute('aria-expanded')" in lb
        and lb.index("context\\s*menu") < lb.index("ctxq = 'pfeil'") and "{ mehrdeutig: ctx.length }" in lb,
        "Login-Blick: Pfeil neben dem Broker-Knopf auch ohne Beschriftung (genau einer, sonst mehrdeutig/None)")
    q_ab = _i.getsource(ob._cdp_abmelden)
    chk(q_ab.index("K3_RX_ABMELDEN") < q_ab.index("cdp_abgemeldet") and 's.taste("Escape")' in q_ab,
        "Abmelden: nach dem Pfeil-Klick nur mit eindeutigem Log out, sonst Esc; abgemeldet wird bewiesen")
    # KLEINE WERBE-KACHEL (05.10.2026, Finn: „auch diese kleinen Ads unten links automatisch wegklicken") — div#charting-ad mit EINEM
    # Knopf „Close ad"; geschlossen nur über dieses X, nur vor dem Konto- und dem Login-Schritt.
    import re as _re
    KW = ob.cdp_kachel_wahl
    kach = {"id": "charting-ad", "box": [64, 568, 460, 150], "x": [497, 585, 10, 10], "wort": "close ad"}
    chk(KW([kach])["x"] == [497.0, 585.0, 10.0, 10.0] and KW([dict(kach, wort="anzeige schließen")]) is not None
        and KW([dict(kach, wort="close")]) is None and KW([dict(kach, wort="close position")]) is None and KW([dict(kach, wort="")]) is None
        and KW([dict(kach, x=[497, 585, 60, 60])]) is None and KW([dict(kach, x=[900, 585, 10, 10])]) is None and KW([dict(kach, x=None)]) is None
        and KW([dict(kach, x=["a", 1, 2, 3])]) is None and KW({"leiste": [1, 2, 3, 4]}) is None and KW(None) is None and KW([]) is None
        and KW(["x"]) is None, "Werbe-Kachel: nur mit Schließen-Wort, kleinem X und X im Kasten; alles andere (auch Attrappen-Antworten) nie")

    class _KS:
        def __init__(self, folgen, druck=True, tv=True, wirft=0):
            self.folgen, self.druck, self.tv_riegel, self.wirft, self.klicks, self.gelesen = list(folgen), druck, tv, wirft, [], 0

        def lese_js(self, ausdruck, timeout=8):
            if ausdruck != ob.CDP_KACHEL_JS:
                return None
            self.gelesen += 1
            if self.wirft and self.gelesen >= self.wirft:
                raise RuntimeError("Verbindung weg")
            return self.folgen.pop(0) if self.folgen else []

        def _win_klick(self, rect, name, druck=True, toast_ok=False, pruef=None):
            self.klicks.append((list(rect), name, toast_ok, dict(pruef or {})))
            return self.druck
    alt_kw, alt_kwin = ob._warte, ob._WIN_EINGABE
    ob._warte = lambda a, b: None
    try:
        ob._WIN_EINGABE = True
        k1, t1 = _KS([[kach], []]), []
        n1 = ob._cdp_kachel_weg(k1, t1)
        k2, t2 = _KS([[kach]], druck=False), []
        n2 = ob._cdp_kachel_weg(k2, t2)
        k3, t3 = _KS([[kach], [kach]]), []
        n3 = ob._cdp_kachel_weg(k3, t3)
        k4, t4 = _KS([[]]), []
        n4_ = ob._cdp_kachel_weg(k4, t4)
        k5, t5 = _KS([[kach], []], tv=False), []
        n5 = ob._cdp_kachel_weg(k5, t5)
        k6, t6 = _KS([[kach]], wirft=1), []
        n6 = ob._cdp_kachel_weg(k6, t6)
        k6b, t6b = _KS([[kach]], wirft=2), []
        n6b = ob._cdp_kachel_weg(k6b, t6b)
        k7, t7 = _KS([[kach], [], [kach], []]), []
        n7 = ob._cdp_kachel_weg(k7, t7)
        k8, t8 = _KS([{"leiste": [56, 0, 1194, 38]}]), []
        n8 = ob._cdp_kachel_weg(k8, t8)
        k10, t10 = _KS([[kach], [], [kach], [], [kach], []]), []
        n10 = ob._cdp_kachel_weg(k10, t10)
        ob._WIN_EINGABE = False
        k9, t9 = _KS([[kach], []]), []
        n9 = ob._cdp_kachel_weg(k9, t9)
    finally:
        ob._warte, ob._WIN_EINGABE = alt_kw, alt_kwin
    pr1 = k1.klicks[0][3] if k1.klicks else {}
    chk(n1 == 1 and len(k1.klicks) == 1 and k1.klicks[0][0] == [497.0, 585.0, 10.0, 10.0] and k1.klicks[0][2] is True
        and pr1.get("text") == "close ad" and pr1.get("aria") == "close ad" and pr1.get("rect") == [497.0, 585.0, 10.0, 10.0]
        and _re.search(pr1.get("tabu") or "x^", "close position") and not _re.search(pr1["tabu"], "close ad")
        and any("weg bewiesen" in z for z in t1), f"Kachel da: EIN Klick auf ihr X mit Ziel-Beweis close ad, weg bewiesen ({t1})")
    chk(n2 == 0 and len(k2.klicks) == 1 and any("nicht gedrückt" in z for z in t2) and n3 == 0 and len(k3.klicks) == 1
        and any("noch da" in z for z in t3), "X nicht gedrückt / Kachel bleibt: genau ein Versuch, ehrlich weiter")
    chk(n4_ == 0 and not k4.klicks and not t4 and n5 == 0 and k5.gelesen == 0 and n9 == 0 and k9.gelesen == 0 and n8 == 0 and not k8.klicks,
        "keine Kachel / TopstepX-Tab / ohne Windows-Maus / Attrappen-Antwort: kein Klick, nichts in der Spur")
    chk(n6 == 0 and not k6.klicks and any("übersprungen" in z for z in t6) and n6b == 0 and len(k6b.klicks) == 1
        and any("übersprungen" in z for z in t6b) and n7 == 2 and len(k7.klicks) == 2 and n10 == 2 and len(k10.klicks) == 2,
        "Lese-Fehler (vor und nach dem Klick) wirft nicht; höchstens zwei Kacheln und zwei Klicks je Aufruf")
    q_ks, q_tv, q_kl = _i.getsource(ob._cdp_konto_sichern), _i.getsource(ob._cdp_tradovate_verbinden), _i.getsource(ob._AugenSitzung.klick)
    chk(q_ks.count("_cdp_kachel_weg(s, trail)") == 1 and q_ks.index("_cdp_kachel_weg(s, trail)") < q_ks.index("s.stand(opts)")
        and q_tv.count("_cdp_kachel_weg(s, trail)") == 1 and q_tv.index("_cdp_kachel_weg(s, trail)") < q_tv.index(".blick()")
        and "kachel" not in q_kl and "charting-ad" not in ob.CDP_WERBUNG_JS and "charting-ad" not in ob.CDP_TOAST_ZU_JS,
        "Kachel nur VOR Konto- und Login-Schritt (vor dem ersten Lesen); klick(), Sale-Modal- und Meldungs-Logik unverändert")
    kj = ob.CDP_KACHEL_JS
    chk("getElementById('charting-ad')" in kj and "xs.length !== 1" in kj and "elementFromPoint" in kj and "q.width > 44" in kj
        and "click(" not in kj and "dispatchEvent" not in kj and ".remove(" not in kj and "style." not in kj
        and "werbung: werbung" in js and "getElementById('charting-ad')" in js,
        "Kachel-Blick: nur der Kasten #charting-ad, genau EIN unverdecktes kleines X, liest nur; augen.js meldet toasts.werbung")
    q_tk = _i.getsource(ob._cdp_ticket_fuellen) if hasattr(ob, "_cdp_ticket_fuellen") else ""
    chk(not q_tk or ("chart_frei and bw > 200" in q_tk and "s._panel_max_versucht, s._panel_open_versucht = True, False" in q_tk
                     and "chart_frei = restored" in q_tk and "Treffer ≠ Wirkung" in q_tk and "for _b in range(6):" in q_tk),
        "Shift+T: Chart-Klick nur nach gedrücktem Restore, danach NICHT wieder maximiert (höchstens Open panel); Symbol bis ~6 s warten")
    if ok:
        print("✓ Regression .865: fremde Liste kein Beleg, Abmelden nur mit Beleg, unlesbar = ehrlich raus, Umschalter auch maximiert")
    return ok


def test_cdp_konto_weg():
    """KONTO WEG (05.10.2026, Finn): zwei Endlesungen geblowter Konten endeten als Login-Fehler („… auch nach dem Tradovate-Login.
    Gehört der Username wirklich zu dieser Firma?") — der Login stimmte, die Konten gab es bei Tradovate nicht mehr. Geprüft: eigener
    Code 'konto_weg' nur nach eigenem Formular-Login + zwei gleichen Befunden + Ziel nirgends im sichtbaren Text + gleiche Firma;
    alles andere bleibt wie bisher. Alle Kennungen erfunden."""
    import order_bot as ob, inspect as _i, re
    ok = True

    def chk(bed, text):
        nonlocal ok
        if not bed:
            print("  ✗ Konto weg: " + text)
            ok = False
    FN1, FN2, FN3, TD1 = "FNFTCHMUSTERMANNMAX10001", "FNFTCHMUSTERMANNMAX20002", "FNFTCHMUSTERMANNMAX3003", "TDFYSL150300000000"
    W, S = ob.cdp_konto_weg, ob.cdp_ziel_schluessel
    ein = {"konto_treffer": 0, "liste_aktiv": FN1 + "USD", "ein_konto": True, "ziel_im_text": False}
    lst = {"konto_treffer": 0, "liste_aktiv": FN1 + "USD", "konto_eintraege": [FN1 + "USD", FN3 + "USD"], "ziel_im_text": False}
    chk(W(ein, True, FN2) == (True, 1, True) and W(lst, True, FN2) == (True, 2, False), "Einzelkonto und vollständige Liste zählen")
    chk(not W(ein, False, FN2)[0] and not W(ein, None, FN2)[0] and not W(ein, 1, FN2)[0], "ohne eigenen Formular-Login nie")
    chk(not W(dict(ein, ziel_im_text=True), True, FN2)[0] and not W(dict(ein, ziel_im_text=None), True, FN2)[0]
        and not W({k: v for k, v in ein.items() if k != "ziel_im_text"}, True, FN2)[0], "Ziel im sichtbaren Text oder nicht prüfbar → nie")
    chk(not W(dict(ein, konto_treffer=None), True, FN2)[0] and not W(dict(ein, konto_treffer=2), True, FN2)[0]
        and not W(dict(ein, liste_aktiv=""), True, FN2)[0] and not W(None, True, FN2)[0], "ohne Beleg des Konto-Schritts nie")
    chk(not W(dict(ein, liste_aktiv=TD1 + "USD"), True, FN2)[0] and not W(dict(ein, liste_aktiv="EXPRESS-V2-000000-00000000"), True, "EXPRESS-V2-000000-00000001")[0]
        and not W(dict(lst, konto_eintraege=[]), True, FN2)[0], "andere Firma / unbekannte Firma / leere Liste → nie")
    chk(S(FN3) == "NMAX3003" and S("fnftch musterMannMax 3003") == "NMAX3003" and S("AB12") == "" and S(None) == "", "Such-Schlüssel: letzte 8 Zeichen, zu kurz = keiner")
    js = ob.cdp_ziel_im_text_js(FN3)
    chk('"NMAX3003"' in js and "innerText" in js and ".click(" not in js and not re.search(r"\.value\s*=[^=]", js) and ob.cdp_ziel_im_text_js("AB") == "",
        "Text-Probe liest nur")

    class _P:
        def __init__(self, w):
            self.w = w

        def lese_js(self, a, timeout=8):
            if isinstance(self.w, Exception):
                raise self.w
            return self.w
    chk(ob._cdp_ziel_im_text(_P(True), FN2) is True and ob._cdp_ziel_im_text(_P(False), FN2) is False and ob._cdp_ziel_im_text(_P({"a": 1}), FN2) is None
        and ob._cdp_ziel_im_text(_P(RuntimeError("x")), FN2) is None and ob._cdp_ziel_im_text(_P(False), "AB") is None and ob._cdp_ziel_im_text(object(), FN2) is None,
        "Text-Probe: True/False, sonst None, wirft nie")

    # Konto-Schritt mit Attrappe: Probe läuft VOR dem Esc (Liste noch offen) und landet in extra
    MAX = {"leiste": [56, 0, 1194, 38], "unter_leiste": 735, "max_knopf": {"rect": [1212, 0, 38, 38], "aria": "Restore panel"}}

    class _S:
        ws = None

        def __init__(self, zeilen, im_text=False, liste=True):
            self.zeilen, self.im_text, self.liste, self.offen, self.spur = zeilen, im_text, liste, False, []

        def stand(self, opts=None):
            e = [{"text": z + "USD", "rect": [78, 90 + 32 * i, 228, 32], "aktiv": i == 0} for i, z in enumerate(self.zeilen)]
            return {"konto": {"panel": "offen", "panel_lage": "maximiert", "schalter": {"rect": [72, 59, 199, 28]}, "aktiv": self.zeilen[0] + "USD",
                              "liste_offen": self.offen, "liste_voll": self.offen, "eintraege": e if self.offen else []}}

        def lese_js(self, a, timeout=8):
            if "innerText" in a:
                self.spur.append("probe:" + ("offen" if self.offen else "zu"))
                return self.im_text
            return {"frei": True, "was": ""} if "elementFromPoint" in a else dict(MAX)

        def werbung_weg(self, zwang=False):
            return 0

        def taste(self, k, modifiers=0):
            self.spur.append("Taste " + k)
            self.offen = False

        def klick(self, r, n, toast_ok=False):
            self.spur.append(n)
            if n == "Konto-Umschalter" and self.liste:
                self.offen = True
            elif n.startswith("Konto "):
                z = n.split(" ", 1)[1]
                self.zeilen, self.offen = [z] + [x for x in self.zeilen if x != z], False
            return True
    alt = {n: getattr(ob, n) for n in ("_warte", "_cdp_konto_sichern", "_cdp_tradovate_verbinden", "_cdp_login_sichern", "_cdp_sitzung_zurueck")}
    ob._warte = lambda a_, b_: None
    try:
        s1 = _S([FN1, FN3])
        r1 = ob._cdp_konto_sichern(s1, FN2, {}, [])
        s2 = _S([FN1], liste=False)
        r2 = ob._cdp_konto_sichern(s2, FN2, {}, [])
        s3 = _S([FN1, FN3], im_text=True)
        r3 = ob._cdp_konto_sichern(s3, FN2, {}, [])
        s4 = _S([FN1, FN2])
        r4 = ob._cdp_konto_sichern(s4, FN2, {}, [])

        # Login-Weg mit Attrappen: Folge von Konto-Schritt-Ergebnissen, Verbinden meldet 'login' mit/ohne Formular
        def kn(extra, msg="Ziel fehlt"):
            return (False, "konto_nicht_erreicht", msg, {}, dict(extra))

        def lauf(folge, formular=True, wie="login"):
            n = {"k": 0, "v": 0}

            def _ks(s, ext, opts, trail):
                n["k"] += 1
                return folge[min(n["k"], len(folge)) - 1]

            def _tv(sitz, cmd, opts, trail, beleg=None, merk=None):
                n["v"] += 1
                if formular and isinstance(merk, dict):
                    merk["formular"] = True
                return "", "", wie
            ob._cdp_konto_sichern, ob._cdp_tradovate_verbinden = _ks, _tv
            ob._cdp_login_sichern, ob._cdp_sitzung_zurueck = (lambda res, trail: None), (lambda s, o, t: False)
            res, tr = {}, []
            aus = ob._cdp_konto_mit_login([object()], FN2, {}, {"tv_username": "FNFT_MUSTER"}, tr, res)
            return aus, res, tr, n
        a, res_a, tr_a, n_a = lauf([kn(ein), kn(ein), kn(ein)])
        b, res_b, tr_b, n_b = lauf([kn(ein), kn(dict(lst, konto_eintraege=[FN1, FN3, TD1])), kn(dict(lst, konto_eintraege=[FN1, FN3, TD1]))])
        c, res_c, tr_c, n_c = lauf([kn(ein), kn(ein), kn(ein)], formular=False)
        d, res_d, tr_d, n_d = lauf([kn(ein), kn(ein), (True, "", "", {"x": 1}, {"konto_aktiv": FN2 + "USD"})])
        e, res_e, tr_e, n_e = lauf([kn(ein), kn(ein), kn(lst)])
        f, res_f, tr_f, n_f = lauf([kn(ein), kn(dict(ein, ziel_im_text=True)), kn(dict(ein, ziel_im_text=True))])
        g, res_g, tr_g, n_g = lauf([kn(ein), kn(dict(ein, liste_aktiv=TD1 + "USD")), kn(dict(ein, liste_aktiv=TD1 + "USD"))])
        h, res_h, tr_h, n_h = lauf([kn(ein), kn(ein), kn(ein), kn(ein)], wie="selbst")
    finally:
        for n_, f_ in alt.items():
            setattr(ob, n_, f_)
    chk(r1[1] == "konto_nicht_erreicht" and r1[4].get("konto_treffer") == 0 and r1[4].get("ziel_im_text") is False and r1[4].get("liste_aktiv")
        and "probe:offen" in s1.spur and s1.spur.index("probe:offen") < s1.spur.index("Taste Escape"),
        f"Liste ohne Ziel: Text-Probe bei offener Liste vor dem Esc, Ergebnis in extra ({s1.spur}, {r1[4]})")
    chk(r2[4].get("ein_konto") is True and r2[4].get("ziel_im_text") is False and any(x.startswith("probe:") for x in s2.spur),
        f"Login mit einem Konto: Text-Probe läuft ({s2.spur}, {r2[4]})")
    chk(r3[4].get("ziel_im_text") is True and not W(r3[4], True, FN2)[0] and W(r1[4], True, FN2) == (True, 2, False), "Ziel im Text sichtbar → kein Beweis")
    chk(r4[0] is True and not any(x.startswith("probe:") for x in s4.spur), f"Konto in der Liste: wie bisher gewählt, keine Probe ({s4.spur})")
    chk(a[1] == "konto_weg" and a[4].get("retry_ok") is False and a[4].get("konten_im_login") == 1 and a[4].get("einzelkonto") is True
        and "nicht mehr vorhanden" in a[2] and "steht 1 Konto" in a[2] and "vermutlich geblowt" in a[2] and "Gehört der Username" not in a[2]
        and FN2 not in a[2] and "Konto …0002 bei" in a[2]
        and res_a["login"].get("code") == "konto_weg" and res_a["login"].get("ok") is False and n_a == {"k": 3, "v": 1}
        and any("Konto weg" in x for x in tr_a), f"Einzelkonto nach eigenem Login, zweimal gleich → konto_weg, EIN Login ({a[1]}, {a[2]}, {n_a})")
    chk(b[1] == "konto_weg" and b[4].get("konten_im_login") == 3 and b[4].get("einzelkonto") is False and "stehen 3 Konten" in b[2] and n_b == {"k": 3, "v": 1},
        f"vollständige Liste ohne Ziel → konto_weg mit Anzahl ({b[1]}, {b[2]})")
    chk(c[1] == "konto_nicht_erreicht" and "auch nach dem Tradovate-Login" in c[2] and "retry_ok" not in c[4] and n_c == {"k": 2, "v": 1},
        f"ohne Formular-Login (Tradovate war noch angemeldet) → alte Meldung, kein zweiter Blick ({c[1]}, {n_c})")
    chk(d[0] is True and d[1] == "" and res_d["login"].get("ok") is True and n_d == {"k": 3, "v": 1}, f"zweiter Blick findet das Konto → Lauf geht normal weiter ({d[:3]})")
    chk(e[1] == "konto_nicht_erreicht" and "auch nach dem Tradovate-Login" in e[2] and "retry_ok" not in e[4], f"zweiter Blick anders als der erste → alte Meldung ({e[1]}, {e[2]})")
    chk(f[1] == "konto_nicht_erreicht" and n_f == {"k": 2, "v": 1} and g[1] == "konto_nicht_erreicht" and "Gehört der Username" in g[2] and n_g == {"k": 2, "v": 1},
        "Ziel im Text sichtbar bzw. Login einer anderen Firma → alte Meldung, kein zweiter Blick")
    chk(h[1] == "konto_nicht_erreicht" and "gemerkte Tradovate-Sitzung" in h[2] and "retry_ok" not in h[4], f"gemerkte Sitzung → nie konto_weg ({h[2]})")
    q_tv, q_km, q_ks = _i.getsource(ob._cdp_tradovate_verbinden), _i.getsource(ob._cdp_konto_mit_login), _i.getsource(ob._cdp_konto_sichern)
    chk(q_tv.count('merk["formular"] = True') == 1 and q_tv.index("_cdp_anmelden(") < q_tv.index('merk["formular"] = True')
        and "if not code and isinstance(merk, dict):" in q_tv, "Formular-Beweis nur nach _cdp_anmelden ohne Fehler")
    chk(q_km.index('code = "konto_weg"') > q_km.index("zweit[1:] == erst[1:]") and 'wege[-1] == "login"' in q_km
        and q_km.count("_cdp_tradovate_verbinden(") == 1 and q_ks.index("_cdp_ziel_im_text(s, ext) if n == 0") < q_ks.index('"Konto-Liste schließen"'),
        "konto_weg nur nach zwei gleichen Befunden; Probe vor dem Esc")
    for m in (ob.modus_tvlesen_cdp, ob.modus_tvkette_cdp, ob.modus_tvclose_cdp):
        chk('**{k: v for k, v in extra.items() if k != "konto_aktiv"}' in _i.getsource(m), f"{m.__name__}: Code, retry_ok und Zähler reisen ins Ergebnis")
    if ok:
        print("✓ Konto weg: eigener Code nur nach eigenem Formular-Login + zwei gleichen Befunden + Ziel nirgends im Text; sonst alles wie bisher")
    return ok


def test_cdp_connect_zweiter_versuch():
    """WERBUNG-2 (06.10.2026): im Login-Weg scheiterte „Connect" im frisch geladenen Tab („Ziel NICHT unter dem Zeiger — kein Druck").
    Geprüft: Werbe-Kachel wird auch im neuen Tab vor dem Dialog geschlossen; ein nicht gedrückter Connect wird nach Kachel-Prüfung,
    Neulesen und Demo-Beweis genau EINMAL wiederholt; scheitert auch der zweite, nennt die Spur, was am Punkt liegt; ohne Demo kein
    zweiter Klick. Alles andere unverändert (ein gelungener Klick = ein Klick)."""
    import order_bot as ob, inspect as _i
    ok = True

    def chk(bed, text):
        nonlocal ok
        if not bed:
            print("  ✗ Connect 2. Versuch: " + text)
            ok = False
    dlg = {"titel": "Tradovate", "rect": [700, 300, 520, 420], "netzfehler": False,
           "knoepfe": [{"text": "Live", "role": "radio", "rect": [740, 420, 80, 30], "an": False},
                       {"text": "Demo", "role": "radio", "rect": [830, 420, 80, 30], "an": True},
                       {"text": "Connect", "rect": [900, 640, 120, 36]}, {"text": "", "aria": "Close", "rect": [1190, 310, 20, 20]}],
           "nicht_merken": {"an": True, "rect": [740, 580, 180, 20], "quelle": "kaestchen"}}
    bl = {"dialoge": [dlg], "umgebung": []}
    dlg_aus = dict(dlg, knoepfe=[dict(k, an=False) if k.get("text") == "Demo" else k for k in dlg["knoepfe"]])
    bl_aus = {"dialoge": [dlg_aus], "umgebung": []}
    bl_neu = {"dialoge": [dict(dlg, knoepfe=[dict(k, rect=[900, 660, 120, 36]) if k.get("text") == "Connect" else k for k in dlg["knoepfe"]])], "umgebung": []}
    blicke = [[bl]]

    class _Ort:
        def __init__(self, *a, **k):
            pass

        def blick(self):
            q = blicke[0]
            return q.pop(0) if len(q) > 1 else q[0]

    class _S:
        ws = None

        def __init__(self, folge):
            self.folge, self.klicks, self.js = list(folge), [], []

        def klick(self, r, name, toast_ok=False, pruef=None):
            self.klicks.append((name, [float(x) for x in r]))
            return self.folge.pop(0) if self.folge else True

        def lese_js(self, a, timeout=8):
            self.js.append(a[:60])
            return {"frei": False, "was": "div.toastItem-abc"}
    kachel = {"n": 0}

    def _kw(s_, trail):
        kachel["n"] += 1
        return 0
    alt = {n: getattr(ob, n) for n in ("_K3Ort", "_cdp_kachel_weg", "_cdp_http", "_puls_diagnose_senden", "_warte")}
    ob._K3Ort, ob._cdp_kachel_weg = _Ort, _kw
    ob._cdp_http = lambda pfad, *a, **k: []
    ob._puls_diagnose_senden = lambda *a, **k: None
    ob._warte = lambda a_, b_: None
    try:
        blicke[0] = [bl, bl, bl_neu]                      # 1. Blick, Fehler-Blick vor dem Klick, Neulesen nach dem Fehlversuch (Knopf verschoben)
        s1, t1 = _S([False, True]), []
        r1 = ob._cdp_dialog_verbinden(s1, False, t1)
        k1 = kachel["n"]
        blicke[0] = [bl]
        s2, t2 = _S([False, False]), []
        r2 = ob._cdp_dialog_verbinden(s2, False, t2)
        blicke[0] = [bl]
        kachel["n"] = 0
        s3, t3 = _S([True]), []
        r3 = ob._cdp_dialog_verbinden(s3, False, t3)
        k3 = kachel["n"]
        blicke[0] = [bl, bl, bl_aus]
        s4, t4 = _S([False, True]), []
        r4 = ob._cdp_dialog_verbinden(s4, False, t4)
        blicke[0] = [bl, bl, {"dialoge": [], "umgebung": []}]
        s5, t5 = _S([False, True]), []
        r5 = ob._cdp_dialog_verbinden(s5, False, t5)
    finally:
        for n_, f_ in alt.items():
            setattr(ob, n_, f_)
    chk(r1[0] == "" and isinstance(r1[2], dict) and [k[0] for k in s1.klicks] == ["Connect", "Connect (2. Versuch)"] and s1.klicks[1][1][1] == 660.0
        and k1 == 2 and any("zweiter Versuch" in x for x in t1), f"Connect nicht gedrückt → Kachel-Prüfung, Neulesen, EIN zweiter Klick mit frischem Rechteck ({s1.klicks}, {t1})")
    chk(r2[0] == "connect" and "zweimal" in r2[1] and "div.toastItem-abc" in r2[1] and len(s2.klicks) == 2 and any("am Connect-Punkt liegt" in x for x in t2)
        and any("elementFromPoint" in a for a in s2.js), f"zweimal nicht gedrückt → Fehler mit dem, was am Punkt liegt ({r2[1]})")
    chk(r3[0] == "" and len(s3.klicks) == 1 and k3 == 1, f"gelungener Klick: wie bisher ein Klick, Kachel einmal vor dem Dialog geprüft ({s3.klicks}, {k3})")
    chk(r4[0] == "connect" and len(s4.klicks) == 1 and "kein zweiter Versuch" in r4[1], f"Demo nach dem Fehlversuch nicht an → kein zweiter Klick ({r4[1]})")
    chk(r5[0] == "connect" and len(s5.klicks) == 1, "Dialog nach dem Fehlversuch weg → kein zweiter Klick")
    q = _i.getsource(ob._cdp_dialog_verbinden)
    chk(q.index("_cdp_kachel_weg(s, trail)") < q.index("cdp_connect_dialog(ort.blick())") and q.count("_cdp_kachel_weg(s, trail)") == 2
        and q.count('"Connect (2. Versuch)"') == 1 and q.index('"Connect")') < q.index('"Connect (2. Versuch)"'),
        "Kachel vor dem Dialog und vor dem zweiten Versuch; genau ein zweiter Connect-Klick")
    if ok:
        print("✓ Connect 2. Versuch: Kachel auch im neuen Tab weg, nicht gedrückter Connect genau einmal neu (Demo bewiesen), Spur nennt den Blocker")
    return ok


def test_tsx_k0():
    """K0 (30.09.2026, Topstep-Komplett-Paket Plan v2): TopstepX über das Puls-Chrome — Regel je PC klebrig, Riegel in tsxlesen/
    tsxorder/tsxinventar (nie UIA auf einem cdp-PC, ehrlich 'cdp_folgt'), TopstepX-Tab, Inventar-Kandidaten nur eindeutig und nie
    Order-/Close-Knöpfe, Login-Klick nur mit Autofill-Beweis, Größen-Deckel, Puls-Chrome bleibt auf Topstep-PCs offen."""
    import order_bot as ob
    import inspect as _i
    import io
    import contextlib
    import tempfile
    import os as _os
    import json
    import re
    import time
    ok = True

    def chk(bed, text):
        nonlocal ok
        if not bed:
            print("  ✗ TSX-K0: " + text)
            ok = False
    PC = "pc-aaaaaa"
    W = ob.tsx_regel_weiche
    chk(W({"tsx": "cdp", "tsx_pc": PC, "tsx_at": 1.0}, PC) == "cdp" and W({"tsx": "cdp", "pc": PC}, PC) == "cdp"
        and W({"tsx": "cdp", "tsx_pc": "pc-andere1"}, PC) == "uia" and W({"tsx": "uia"}, PC) == "uia" and W(None, PC) == "uia"
        and W({"tsx": "cdp"}, None) == "uia", "Regel: 'cdp' klebrig (auch uralt), nur eigener PC; sonst 'uia'")
    A = ob.tsx_regel_aus_antwort
    chk(A({"ok": True, "augen": "uia", "tsx": "cdp"}) == "cdp" and A({"ok": True, "augen": "cdp"}) is None and A({"tsx": "x"}) is None
        and A(None) is None, "Antwort ohne tsx = lokale Regel (nie stilles 'uia')")
    F = ob.tsx_cdp_folgt
    f1, f2, f3 = F("tsxlesen"), F("tsxorder"), F("tsxprobe")
    chk(f1["code"] == f2["code"] == "cdp_folgt" and (f1["etappe"], f2["etappe"], f3["etappe"]) == ("K1", "K4", "K3")
        and f2["gesendet"] is False and f2["retry_ok"] is False and "NICHT erneut starten" in f2["msg"], "cdp_folgt: Etappe, nichts gesendet, kein Neustart")
    # Regel-Datei: augen und tsx verlieren sich nie gegenseitig; ohne Netz gilt die lokale tsx-Regel
    alt_hier, alt_url = ob._AUGEN_HIER, None
    import urllib.request as _ur
    alt_url = _ur.urlopen
    d = tempfile.mkdtemp()
    try:
        ob._AUGEN_HIER = d
        ob._augen_json_schreiben("augen_regel.json", {"tsx": "cdp", "tsx_pc": PC, "tsx_at": 5.0})
        ob._augen_regel_mischen({"augen": "uia", "at": 9.0, "pc": PC})
        r1 = ob._augen_json_lesen("augen_regel.json")

        def _kaputt(*a, **k):
            raise OSError("kein Netz")
        _ur.urlopen = _kaputt
        v1 = ob._tsx_regel_holen(PC)

        class _Antw:
            def __init__(self, b):
                self.b = b

            def read(self):
                return self.b

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        _ur.urlopen = lambda *a, **k: _Antw(b'{"ok": true, "augen": "cdp", "tsx": "uia"}')
        v2 = ob._tsx_regel_holen(PC)
        r2 = ob._augen_json_lesen("augen_regel.json")
        _ur.urlopen = lambda *a, **k: _Antw(b'{"ok": true, "augen": "uia", "tsx": "cdp"}')
        v3 = ob._augen_regel_holen(PC)
        r3 = ob._augen_json_lesen("augen_regel.json")
    finally:
        _ur.urlopen = alt_url
        ob._AUGEN_HIER = alt_hier
    chk(r1.get("tsx") == "cdp" and r1.get("augen") == "uia", f"augen-Regel schreiben behält tsx ({r1})")
    chk(v1 == "cdp", "ohne Netz: lokale 'cdp'-Regel gilt (Riegel)")
    chk(v2 == "uia" and r2.get("tsx") == "uia" and r2.get("augen") == "uia", f"ausdrückliches Server-'uia' schaltet zurück ({r2})")
    chk(v3 == "uia" and r3.get("tsx") == "cdp" and r3.get("augen") == "uia", f"Augen-Abfrage nimmt tsx mit ({r3})")
    # Riegel in den drei Modi
    alt_weg, alt_lesen, alt_inv, alt_k1, alt_k1_an = (ob.tsx_weg_lauf, ob.modus_tsxlesen, ob.modus_tsxinventar_cdp, ob.modus_tsxlesen_cdp,
                                                      ob.TSX_K1_AKTIV)
    alt_k3_an = ob.TSX_K3_AKTIV
    auf = []
    try:
        ob.tsx_weg_lauf = lambda: "cdp"
        ob.modus_tsxlesen_cdp = lambda c, **kw: auf.append(("k3", c, kw.get("order")) if kw.get("order") else ("k1", c))   # echter Lauf startet Chrome
        o1 = io.StringIO()
        with contextlib.redirect_stdout(o1):
            ob.TSX_K1_AKTIV = False
            ob.modus_tsxlesen({"konto": "EXPRESS-V2-000000-10000001"})
        ob.TSX_K1_AKTIV = True
        ob.modus_tsxlesen({"konto": "EXPRESS-V2-000000-10000001"})
        o2 = io.StringIO()
        alt_k4_an = ob.TSX_K4_AKTIV
        with contextlib.redirect_stdout(o2):
            ob.TSX_K4_AKTIV = False             # Notschalter K4 aus: scharf antwortet wie vor K4
            ob.modus_tsxorder({"ext_id": "150KTC-SKU-V2-000000-20000000", "symbol": "MNQ", "richtung": "buy", "volumen": 1, "tp_usd": 40, "scharf": True})
        ob.TSX_K4_AKTIV = True                  # K4 (05.10.2026): scharf läuft dieselbe Kette, mit dem Original-Befehl für Risk / To Make
        auf4, alt_kette = [], ob.modus_tsxlesen_cdp
        ob.modus_tsxlesen_cdp = lambda c, **kw: auf4.append((c, kw.get("order"), kw.get("order_cmd")))
        ob.modus_tsxorder({"ext_id": "150KTC-SKU-V2-000000-20000000", "symbol": "MNQ", "richtung": "sell", "volumen": 2, "tp_usd": 40, "sl_usd": 20,
                           "scharf": True, "plan_id": "p-1"})
        ob.modus_tsxlesen_cdp, ob.TSX_K4_AKTIV = alt_kette, alt_k4_an
        o3 = io.StringIO()
        with contextlib.redirect_stdout(o3):
            ob.TSX_K3_AKTIV = False
            ob.modus_tsxorder({"ext_id": "150KTC-SKU-V2-000000-20000000", "symbol": "MNQ", "richtung": "buy", "volumen": 1, "tp_usd": 40})
        ob.TSX_K3_AKTIV = True                  # K3a (01.10.2026): die Probe läuft über das Puls-Chrome — auch ohne TP (SL/TP von Hand)
        ob.modus_tsxorder({"ext_id": "150KTC-SKU-V2-000000-20000000", "symbol": "MNQ", "richtung": "buy", "volumen": 1, "tp_usd": None})
        ob.modus_tsxorder({"ext_id": "150KTC-SKU-V2-000000-20000000", "symbol": "NQZ6", "richtung": "sell", "volumen": 3, "tp_usd": 90})
        o3b = io.StringIO()
        with contextlib.redirect_stdout(o3b):
            ob.TSX_K1_AKTIV = False             # K1-Notschalter hält auch die Probe auf
            ob.modus_tsxorder({"ext_id": "150KTC-SKU-V2-000000-20000000", "symbol": "MNQ", "richtung": "buy", "volumen": 1})
        ob.TSX_K1_AKTIV = True
        ob.modus_tsxinventar_cdp = lambda c: auf.append(("inv", c))
        ob.modus_tsxinventar({"x": 1})
        ob.tsx_weg_lauf = lambda: "uia"
        ob.modus_tsxlesen = lambda c, **kw: auf.append(("lesen", c, kw.get("weg")))
        ob.modus_tsxorder({"ext_id": "150KTC-SKU-V2-000000-20000000", "symbol": "MNQ", "richtung": "buy", "volumen": 1, "tp_usd": 40})
    finally:
        ob.tsx_weg_lauf, ob.modus_tsxlesen, ob.modus_tsxinventar_cdp, ob.modus_tsxlesen_cdp, ob.TSX_K1_AKTIV = (alt_weg, alt_lesen, alt_inv,
                                                                                                             alt_k1, alt_k1_an)
        ob.TSX_K3_AKTIV = alt_k3_an
    j1, j2, j3 = (json.loads(o.getvalue()) for o in (o1, o2, o3))
    chk(j1["code"] == "cdp_folgt" and j1["etappe"] == "K1", f"tsxlesen auf cdp-PC, K1 aus → cdp_folgt K1 ({j1})")
    chk(("k1", {"konto": "EXPRESS-V2-000000-10000001"}) in auf, "tsxlesen auf cdp-PC, K1 an → K1-Weg (nie UIA im Alltags-Chrome)")
    chk(j2["code"] == "cdp_folgt" and j2["etappe"] == "K4" and j2["gesendet"] is False, f"tsxorder scharf, K4 aus → cdp_folgt K4, nichts gesendet ({j2})")
    chk(len(auf4) == 1 and auf4[0][1].get("scharf") is True and auf4[0][1].get("richtung") == "sell" and auf4[0][1].get("menge") == 2
        and auf4[0][2].get("tp_usd") == 40 and auf4[0][2].get("sl_usd") == 20 and auf4[0][2].get("plan_id") == "p-1",
        f"tsxorder scharf, K4 an → Kette mit scharf und dem Original-Befehl (TP/SL in $, plan_id) ({auf4})")
    chk(j3["etappe"] == "K3", "tsxorder Probe, K3 aus → cdp_folgt K3")
    k3 = [a for a in auf if a[0] == "k3"]
    chk(len(k3) == 2 and k3[0][1] == {"konto": "150KTC-SKU-V2-000000-20000000", "firma": None}
        and {k_: k3[0][2].get(k_) for k_ in ("richtung", "menge", "wurzel", "ext", "scharf", "brackets")}
        == {"richtung": "buy", "menge": 1, "wurzel": "MNQ", "ext": "150KTC-SKU-V2-000000-20000000", "scharf": False, "brackets": None}
        and {k_: k3[1][2].get(k_) for k_ in ("richtung", "menge", "wurzel", "scharf")} == {"richtung": "sell", "menge": 3, "wurzel": "NQ", "scharf": False},
        f"tsxorder Probe, K3 an → K3a-Weg mit genau den Plan-Werten (buy 1 MNQ ohne TP; sell 3 NQ) ({[a[2] for a in k3]})")
    j3b = json.loads(o3b.getvalue())
    chk(j3b["code"] == "cdp_folgt" and j3b["etappe"] == "K3", "K1 aus, K3 an → Probe antwortet cdp_folgt (Notschalter hält die Kette auf)")
    chk(("inv", {"x": 1}) in auf, "tsxinventar auf cdp-PC → CDP-Inventar (K0)")
    chk(any(a[0] == "lesen" and a[2] == "uia" for a in auf), "uia-PC: tsxorder geht mit bestimmtem Weg in den alten Lese-Zweig (bytegleich)")
    q_o = _i.getsource(ob.modus_tsxorder)
    chk(q_o.index("tsx_weg_lauf()") < q_o.index("modus_tsxlesen("), "tsxorder prüft den Weg VOR dem Lese-Zweig")
    for f in (ob.modus_tsxinventar, ob.modus_tsxlesen):
        q = _i.getsource(f)
        chk("tsx_weg_lauf()" in q and q.index("tsx_weg_lauf()") < q.index("_StempelSpur()"), f"{f.__name__}: Riegel vor jedem UIA-Schritt")
    # Tab
    T = ob.tsx_targets
    lst = [{"type": "page", "url": "https://www.tradingview.com/chart/x/"}, {"type": "page", "url": "https://topstepx.com/login", "id": "a"},
           {"type": "page", "url": "https://topstepx.com/trade", "id": "b"}, {"type": "iframe", "url": "https://topstepx.com/trade"}]
    chk([t["id"] for t in T(lst)] == ["b", "a"] and T(None) == [], "TopstepX-Tab: /trade zuerst, nur Seiten")
    lst2 = [{"type": "page", "url": "https://topstepx.com/login", "id": "alt"}, {"type": "page", "url": "https://topstepx.com/", "id": "neu"}]
    chk([t["id"] for t in T(lst2)] == ["neu", "alt"] and ob.tsx_url_login("https://topstepx.com/login?x=1")
        and not ob.tsx_url_login("https://topstepx.com/trade"), "TopstepX-Tab: angemeldeter Tab vor der alten Login-Seite")
    # Kandidaten
    E = ob.tsx_k0_eindeutig
    k_ok = {"text": "$150K EXPRESS | EXPRESS-V2-000000-10000001", "rect": [10, 60, 300, 32]}
    chk(E([k_ok], "konto")[0] is k_ok and E([k_ok, dict(k_ok, rect=[10, 90, 300, 32])], "konto")[0] is None
        and E([dict(k_ok, aria="Close")], "konto")[0] is None and E([dict(k_ok, aus=True)], "konto")[0] is None
        and E([{"text": "Balance $150,000", "rect": [1, 1, 9, 9]}], "konto")[0] is None,
        "Konto-Auslöser: genau einer, nie gesperrt, nie mit Close-Wort, nur mit Konto-Text")
    g_ok = {"aria": "Manage Brackets", "text": "", "rect": [500, 700, 24, 24]}
    chk(E([g_ok], "bracket")[0] is g_ok and E([g_ok, {"aria": "Buy Market", "rect": [1, 1, 20, 20]}], "bracket")[0] is g_ok
        and "verworfen" in E([{"text": "Flatten", "rect": [1, 1, 20, 20]}], "bracket")[1], "Bracket-Zahnrad: Order-/Flatten-Knöpfe fallen raus")
    B = ob.tsx_login_beweis
    lg = {"seite": True, "knoepfe": 1, "knopf": {"rect": [700, 500, 200, 40]}, "user": {"autofill": True}, "pw": {"autofill": True}}
    chk(B(lg)[0] and not B(dict(lg, pw={"gefuellt": False}))[0] and not B(dict(lg, knopf=None))[0]
        and not B(dict(lg, zwei_faktor=True))[0] and not B(dict(lg, fehler_text="Invalid password"))[0] and not B(None)[0],
        "Login-Klick nur mit Autofill-Beweis, nie bei 2FA/Fehler/ohne eindeutigen Knopf")
    chk(not B(dict(lg, user={"gefuellt": True}, pw={"gefuellt": True}))[0], "gefüllt ohne Chrome-Autofill reicht nicht (Fehlversuch-Schleife)")
    chk(E([dict(k_ok, role="option")], "konto")[0] is None, "eine Listen-Zeile (role option) ist nie der Auslöser")
    P_ = ob.tsx_k0_pruef(k_ok)
    chk(P_["text"] == "EXPRESS-V2-000000-10000001" and P_["rect"] == [10, 60, 300, 32] and P_["tabu"] == ob.TSX_K0_TABU.pattern,
        f"Ziel-Merkmale für den Druck ({P_})")
    # Login-Merker: kein zweiter Klick innerhalb von 30 min (auch nicht im nächsten Lauf)
    class _SL:
        def __init__(self):
            self.klicks = []

        def lese_js(self, a, timeout=8):
            return {"login": lg}

        def klick(self, r, n, toast_ok=False, pruef=None):
            self.klicks.append((n, pruef))
            return True
    d3 = tempfile.mkdtemp()
    alt_h, alt_w = ob._AUGEN_HIER, ob._warte
    try:
        ob._AUGEN_HIER, ob._warte = d3, (lambda a_, b_: None)
        ob._augen_json_schreiben("tsx_login.json", {"at": time.time() - 120})
        sl, tl = _SL(), []
        r_sl = ob._tsx_cdp_login(sl, tl)
        _os.remove(_os.path.join(d3, "tsx_login.json"))
        sl2, tl2 = _SL(), []
        alt_t = ob.time
        uhr = {"t": 1000.0}

        class _Uhr:
            @staticmethod
            def time():
                uhr["t"] += 5.0
                return uhr["t"]
        ob.time = _Uhr
        try:
            r_sl2 = ob._tsx_cdp_login(sl2, tl2)
        finally:
            ob.time = alt_t
        merk = ob._augen_json_lesen("tsx_login.json")
    finally:
        ob._AUGEN_HIER, ob._warte = alt_h, alt_w
    chk(isinstance(r_sl, str) and "kein neuer Versuch" in r_sl and sl.klicks == [], f"Login-Klick vor 2 min → kein neuer ({r_sl})")
    # Login-Seite ohne Autofill: bis ~6 s warten, dann EINMAL neu laden (Navigation, kein Klick) — Sitzung aus einem anderen Tab zählt
    leer = {"seite": True, "knoepfe": 1, "knopf": {"rect": [700, 500, 200, 40]}, "user": {}, "pw": {}}

    class _WsN:
        def __init__(self):
            self.rufe_n = []

        def rufe(self, m, p=None, timeout=5):
            self.rufe_n.append((m, (p or {}).get("url")))
            return {}

    class _SN:
        def __init__(self, danach):
            self.ws, self.danach, self.klicks, self.geladen = _WsN(), danach, [], 0

        def lese_js(self, a, timeout=8):
            nav = any(m == "Page.navigate" for m, _u in self.ws.rufe_n)
            return {"login": (self.danach if nav else leer)}

        def _seite_abwarten(self, sek=25.0):
            return True

        def _augen_laden(self):
            self.geladen += 1

        def klick(self, r, n, toast_ok=False, pruef=None):
            self.klicks.append(n)
            return True
    d5 = tempfile.mkdtemp()
    alt_h5, alt_w5 = ob._AUGEN_HIER, ob._warte
    try:
        ob._AUGEN_HIER, ob._warte = d5, (lambda a_, b_: None)
        s_a, t_a = _SN({"seite": False}), []
        r_a = ob._tsx_cdp_login(s_a, t_a)
        s_b, t_b = _SN(leer), []
        r_b = ob._tsx_cdp_login(s_b, t_b)
        s_c, t_c = _SN(leer), []
        s_c.lese_js = lambda a, timeout=8: {"login": dict(leer, zwei_faktor=True)}
        r_c = ob._tsx_cdp_login(s_c, t_c)
        kein_merker = ob._augen_json_lesen("tsx_login.json") is None
    finally:
        ob._AUGEN_HIER, ob._warte = alt_h5, alt_w5
    chk(r_a is True and s_a.ws.rufe_n == [("Page.navigate", ob.TSX_URL)] and s_a.klicks == [] and s_a.geladen == 1
        and any("aus einem anderen Tab" in x for x in t_a), f"alte Login-Seite → einmal neu laden → angemeldet, kein Klick ({t_a})")
    chk(isinstance(r_b, str) and "nicht angemeldet" in r_b and len(s_b.ws.rufe_n) == 1 and s_b.klicks == [] and kein_merker,
        f"auch nach dem Neuladen leer → ehrlich, genau EIN Neuladen, kein Klick, kein Merker ({r_b})")
    chk(isinstance(r_c, str) and s_c.ws.rufe_n == [] and s_c.klicks == [], f"2FA/Captcha → kein Neuladen, kein Klick ({r_c})")
    d6 = tempfile.mkdtemp()
    alt_h6, alt_w6 = ob._AUGEN_HIER, ob._warte
    try:
        ob._AUGEN_HIER, ob._warte = d6, (lambda a_, b_: None)
        hand = dict(leer, user={"gefuellt": True}, pw={})           # jemand tippt gerade von Hand
        s_d, t_d = _SN(leer), []
        s_d.lese_js = lambda a, timeout=8: {"login": hand}
        r_d = ob._tsx_cdp_login(s_d, t_d)
        s_e, t_e = _SN(leer), []
        s_e.lese_js = lambda a, timeout=8: {"login": dict(leer, pw={"fokus": True})}
        r_e = ob._tsx_cdp_login(s_e, t_e)
        ob._augen_json_schreiben("tsx_login.json", {"at": time.time() - 60})
        s_f, t_f = _SN({"seite": False}), []
        r_f = ob._tsx_cdp_login(s_f, t_f)
    finally:
        ob._AUGEN_HIER, ob._warte = alt_h6, alt_w6
    chk(isinstance(r_d, str) and s_d.ws.rufe_n == [] and isinstance(r_e, str) and s_e.ws.rufe_n == [],
        "Feld von Hand gefüllt oder im Fokus → NIE neu laden (Hand-Anmeldung bleibt)")
    chk(isinstance(r_f, str) and s_f.ws.rufe_n == [] and "kein neuer Versuch" in r_f, f"innerhalb der Login-Sperre kein Neuladen ({r_f})")
    blick_gross = {"dialog_inhalt": [{"felder": [{"text": "x" * 60, "aria": "y" * 40}] * 40, "kaestchen": []}] * 2, "menues": [{"eintraege": [{"text": "z" * 80}] * 30}]}
    dk2 = ob.tsx_inventar_deckeln({"zustand": "bracket", "inventar": {"elemente": [{"t": "e" * 150}] * 45, "blatt": [], "stand": {"a": "s" * 3000},
                                                                    "chart": {"c": "k" * 3000}, "k0_blick": blick_gross}}, max_bytes=9000)
    chk(len(json.dumps(dk2, ensure_ascii=False)) <= 9000 and dk2["inventar"]["stand"] == {"gekuerzt": True} and dk2["inventar"]["chart"] == {"gekuerzt": True},
        f"Deckel kürzt nach Stand auch Chart und den Blick ({len(json.dumps(dk2, ensure_ascii=False))} Bytes)")
    js_b = ob.TSX_K0_BLICK_JS
    chk("RX_GEHEIM" in js_b and "one.?time" in js_b and r"[-+$€%.,\d\s]{1,14}" in js_b and "fokus: document.activeElement === pw" in js_b,
        "Dialog-Blick: Werte nur als Zahl und nie bei Zugangsdaten-Merkmalen; Login-Felder melden den Fokus")
    chk(isinstance(r_sl2, str) and len(sl2.klicks) == 1 and sl2.klicks[0][1] and "login" in sl2.klicks[0][1]["text"] and merk,
        f"erster Login: genau EIN Klick mit Ziel-Beweis, Merker gesetzt ({sl2.klicks}, {r_sl2})")
    # Regel-Datei: keine Sperr-/tmp-Reste; Rückschalten cdp → uia schließt TopstepX-Tabs im Puls-Chrome
    d4 = tempfile.mkdtemp()
    alt_h, alt_c, alt_z = ob._AUGEN_HIER, ob._cdp_http, ob._cdp_tab_schliessen
    zu4 = []
    ob._cdp_tab_schliessen = lambda tid: zu4.append("/json/close/" + str(tid)) or True
    try:
        ob._AUGEN_HIER = d4
        ob._augen_json_schreiben("augen_regel.json", {"tsx": "cdp", "tsx_pc": PC})
        ob._cdp_http = lambda pfad, *a, **k: (zu4.append(pfad) or ([{"type": "page", "id": "ts9", "url": "https://topstepx.com/trade"}]
                                                                   if pfad == "/json/list" else {}))
        _ur.urlopen = lambda *a, **k: _Antw(b'{"ok": true, "augen": "uia", "tsx": "uia"}')
        v5 = ob._tsx_regel_holen(PC)
        zu5 = list(zu4)
        reste = [n for n in _os.listdir(d4) if n.endswith(".tmp") or n.endswith(".lock")]
        # Rückschaltung kommt zuerst beim Augen-Prozess an → auch dort TopstepX-Tabs zu
        ob._augen_json_schreiben("augen_regel.json", {"augen": "cdp", "at": 1.0, "tsx": "cdp", "tsx_pc": PC})
        zu4.clear()
        _ur.urlopen = lambda *a, **k: _Antw(b'{"ok": true, "augen": "cdp", "tsx": "uia"}')
        v6 = ob._augen_regel_holen(PC)
        zu6 = list(zu4)
        zu4.clear()
        v7 = ob._tsx_regel_holen(PC)             # zweiter Lauf: Datei schon 'uia' → kein Schreiben, kein Schließen
        zu7 = list(zu4)
    finally:
        _ur.urlopen, ob._AUGEN_HIER, ob._cdp_http, ob._cdp_tab_schliessen = alt_url, alt_h, alt_c, alt_z
    chk(v6 == "cdp" and "/json/close/ts9" in zu6 and v7 == "uia" and zu7 == [],
        f"Rückschaltung über den Augen-Prozess schließt TopstepX-Tabs, danach nichts mehr ({zu6}, {zu7})")
    chk(v5 == "uia" and "/json/close/ts9" in zu5 and not reste, f"cdp → uia: TopstepX-Tab im Puls-Chrome zu, keine Reste ({zu5}, {reste})")
    q_z = _i.getsource(ob._tsx_k0_zustand)
    chk("pruef=tsx_k0_pruef(el)" in q_z and q_z.index("s._win_vorn()") < q_z.index("TSX_K0_BLICK_JS") and "erlaubt_dialog" in q_z,
        "Zustand: erst nach vorn, dann lesen; Druck mit Ziel-Beweis; Esc nie über fremdem Dialog")
    q_i2 = _i.getsource(ob.modus_tsxinventar_cdp)
    chk("threading.Timer(TSX_K0_WACHHUND_S" in q_i2 and "wh.cancel()" in q_i2 and ob.TSX_K0_WACHHUND_S < 150
        and '"_nicht_zu"' in q_i2, "Wachhund unter 150 s löst Sperre; Bracket nur nach bewiesen geschlossener Liste")
    q_k2 = _i.getsource(ob._AugenSitzung._win_klick)
    chk("win_ziel_pruef_js(" in q_k2 and 'not v.get("passt")' in q_k2, "Windows-Druck mit Ziel-Beweis, ohne passenden Kandidaten kein Druck")
    D = ob.tsx_inventar_deckeln
    gross = {"zustand": "grund", "inventar": {"elemente": [{"t": "x" * 200}] * 400, "blatt": [{"t": "y" * 100}] * 300, "stand": {"a": 1}}}
    dk = D(gross, max_bytes=30000)
    chk(len(json.dumps(dk, ensure_ascii=False)) <= 30000 and dk["inventar"].get("gekuerzt") and dk["zustand"] == "grund"
        and D({"inventar": {"elemente": [1]}}) == {"inventar": {"elemente": [1]}}, "Größen-Deckel: kürzt von hinten, Kopf bleibt")
    S = ob.augen_stand_sha
    chk(S({"sha": "abc"}, "augen.js") == "abc" and S({"sha": "abc"}, "augen_tsx.js") is None
        and S({"dateien": {"augen.js": "a1", "augen_tsx.js": "t1"}}, "augen_tsx.js") == "t1" and S(None, "augen.js") is None,
        "sha je Augen-Datei (alte Form nur für augen.js)")
    try:
        ob._augen_js_holen([], "../app.py")
        chk(False, "fremde Datei darf nicht geholt werden")
    except ValueError:
        pass
    # Puls-Chrome bleibt auf einem Topstep-PC offen, auch wenn TradingView dort 'uia' ist
    alt = {n: getattr(ob, n) for n in ("_augen_pc_id", "_augen_regel_holen", "_cdp_http", "_handlauf_aktiv", "_AUGEN_HIER")}
    http = []
    d2 = tempfile.mkdtemp()
    try:
        ob._AUGEN_HIER = d2
        ob._augen_json_schreiben("augen_regel.json", {"augen": "uia", "at": 1.0, "tsx": "cdp", "tsx_pc": PC})
        ob._augen_pc_id = lambda: PC
        ob._augen_regel_holen = lambda pc: "uia"
        ob._AUGEN_REGEL_STAND["explizit"] = True
        ob._AUGEN_REGEL_STAND["tsx"] = None          # Antwort ohne tsx → die Datei zählt
        ob._cdp_http = lambda *a, **k: http.append(a) or None
        ob._handlauf_aktiv = lambda: False
        o4 = io.StringIO()
        with contextlib.redirect_stdout(o4):
            ob.modus_augen({})
    finally:
        for n, v in alt.items():
            setattr(ob, n, v)
    j4 = json.loads(o4.getvalue())
    chk(j4.get("ok") and "bleibt offen" in j4.get("msg", "") and all(a[0] == "/json/list" for a in http),
        f"Topstep-PC: kein Browser.close ({j4.get('msg')}, {http})")
    # … aber TradingView-Tabs im Puls-Chrome zu (Reader-Kick 29.09.), der TopstepX-Tab bleibt
    http2 = []
    alt["_cdp_tab_schliessen"] = ob._cdp_tab_schliessen
    ob._cdp_tab_schliessen = lambda tid: http2.append("/json/close/" + str(tid)) or True
    tabs = [{"type": "page", "id": "tv1", "url": "https://www.tradingview.com/chart/x/"}, {"type": "page", "id": "ts1", "url": "https://topstepx.com/trade"}]
    try:
        ob._AUGEN_HIER = d2
        ob._augen_pc_id = lambda: PC
        ob._augen_regel_holen = lambda pc: "uia"
        ob._cdp_http = lambda pfad, *a, **k: (http2.append(pfad) or (tabs if pfad == "/json/list" else {}))
        ob._handlauf_aktiv = lambda: False
        with contextlib.redirect_stdout(io.StringIO()):
            ob.modus_augen({})
    finally:
        for n, v in alt.items():
            setattr(ob, n, v)
    chk("/json/close/tv1" in http2 and "/json/close/ts1" not in http2 and "/json/version" not in http2,
        f"Topstep-PC: nur TradingView-Tabs geschlossen ({http2})")
    # Quelltext-Riegel: Lese-Blicke klicken/tippen nie; Sitzung für TopstepX ohne TradingView-Aufräumen; Befehl 'augen start tsx'
    for js in (ob.TSX_K0_BLICK_JS, ob.TSX_K0_CHART_JS):
        chk(".click(" not in js and "dispatchEvent" not in js and ".focus(" not in js and not re.search(r"\.value\s*=[^=]", js)
            and "submit(" not in js, "K0-Blicke lesen nur")
    sig = _i.signature(ob._AugenSitzung.__init__).parameters
    q_k = _i.getsource(ob._AugenSitzung.klick)
    chk("js_datei" in sig and "tv_riegel" in sig and 'getattr(self, "tv_riegel", True)' in q_k and "if tv:" in q_k,
        "Sitzung: Augen-Datei wählbar, TopstepX ohne Werbung/Meldungen wegklicken")
    q_i = _i.getsource(ob.modus_tsxinventar_cdp)
    q_w = _i.getsource(ob._tsx_sitzung_waehlen)
    chk('js_datei="augen_tsx.js", tv_riegel=False' in q_w and "_handlauf_setzen(True)" in q_i and "_handlauf_setzen(False)" in q_i
        and "_tsx_sitzung_waehlen(trail, sitz)" in q_i and "_tsx_cdp_login(s, trail)" in q_w,
        "K0-Inventar: augen_tsx.js, Sperre für andere Puls-Chrome-Läufe, Login nur über den Beweis")
    # Sitzungswahl (30.09.2026): eigener Tab zeigt die alte Login-Seite, ein anderer TopstepX-Tab ist angemeldet
    class _FS:
        def __init__(self, trail, ziel=None, js_datei="augen.js", tv_riegel=True):
            self.ziel, self.zu_n = ziel, 0

        def lese_js(self, a, timeout=8):
            return {"login": {"seite": bool(self.ziel.get("_login"))}}

        def zu(self):
            self.zu_n += 1
    alt_s = {n: getattr(ob, n) for n in ("_tsx_tab_sicher", "_AugenSitzung", "_cdp_http", "_cdp_tab_schliessen", "_augen_json_lesen",
                                          "_tsx_cdp_login", "_puls_chrome_wo")}
    t_bot = {"type": "page", "id": "bot1", "url": "https://topstepx.com/trade", "webSocketDebuggerUrl": "ws://x", "_login": True}
    t_mensch = {"type": "page", "id": "mensch1", "url": "https://topstepx.com/trade", "webSocketDebuggerUrl": "ws://y", "_login": False}
    t_tv = {"type": "page", "id": "tv1", "url": "https://www.tradingview.com/chart/x/", "title": "NQ"}
    zu_tabs, login_ruf, erg = [], [], {}
    try:
        ob._AugenSitzung = _FS
        ob._cdp_tab_schliessen = lambda tid: zu_tabs.append(tid) or True
        ob._tsx_cdp_login = lambda s_, t_: login_ruf.append(s_.ziel["id"]) or "nicht angemeldet (Attrappe)"
        ob._puls_chrome_wo = lambda: "Puls-Chrome Port 9333, Profil X"
        for fall, tabs, eigene in (("anderer_angemeldet", [t_bot, t_mensch, t_tv], ["bot1"]), ("fremder_tab_bleibt", [t_bot, t_mensch], []),
                                   ("alle_login", [t_bot, dict(t_mensch, _login=True)], ["bot1"]), ("angemeldet", [dict(t_bot, _login=False)], [])):
            zu_tabs.clear()
            login_ruf.clear()
            ob._tsx_tab_sicher = lambda tr, _t=tabs: _t[0]
            ob._cdp_http = lambda pfad, *a, _t=tabs, **k: list(_t)
            ob._augen_json_lesen = lambda name, _e=eigene: {"ids": list(_e)}
            tr = []
            halter = [None]
            sz, r_ = ob._tsx_sitzung_waehlen(tr, halter)
            erg[fall] = (sz.ziel["id"], r_, list(zu_tabs), list(login_ruf), tr, halter[0] is sz)
    finally:
        for n, f in alt_s.items():
            setattr(ob, n, f)
    chk(erg["anderer_angemeldet"][:3] == ("mensch1", True, ["bot1"]) and erg["anderer_angemeldet"][3] == []
        and any("Tabs:" in x and "Port 9333" in x for x in erg["anderer_angemeldet"][4]),
        f"anderer TopstepX-Tab angemeldet → nehmen, eigenen Login-Tab schließen, Tabs + Profil in der Spur ({erg['anderer_angemeldet'][4]})")
    chk(erg["fremder_tab_bleibt"][:3] == ("mensch1", True, []), "ein Tab, den der Bot nicht geöffnet hat, wird nie geschlossen")
    chk(all(e[5] for e in erg.values()), "die gewählte Sitzung steht sofort beim Aufrufer (finally/Wachhund schließen sie)")
    chk(erg["alle_login"][0] == "bot1" and isinstance(erg["alle_login"][1], str) and erg["alle_login"][3] == ["bot1"] and erg["alle_login"][2] == [],
        "alle TopstepX-Tabs auf Login → Login-Blick im eigenen Tab (neu laden, Beweis)")
    chk(erg["angemeldet"][0] == "bot1" and erg["angemeldet"][3] == ["bot1"], "kein Login-Bild → normaler Weg")
    chk(ob.cdp_tabs_kurz([t_tv, {"type": "iframe", "url": "x"}, t_bot]) == "NQ (https://www.tradingview.com/chart/x/) |  (https://topstepx.com/trade)"
        and ob.cdp_tabs_kurz(None) == "keine", "Tab-Liste für die Spur")
    q_m = _i.getsource(ob.main)
    chk('cmd["tsx"] = True' in q_m and "augen start tsx" in _i.getsource(ob.modus_augen), "Befehl 'augen start tsx' öffnet den TopstepX-Tab")
    q_l = _i.getsource(ob._tsx_cdp_login)
    chk(q_l.count("s.klick(") == 1 and "tippen" not in q_l.replace("nie tippen", "") and "Enter" not in q_l.replace("nie Enter", ""),
        "Login: genau ein Klick, nie tippen, nie Enter")
    js_d = _os.path.join(_os.path.dirname(_os.path.abspath(ob.__file__)), "augen_tsx.js")
    chk(_os.path.exists(js_d) and "globalThis.prophosAugen = PROPHOS_AUGEN_TSX" in open(js_d, encoding="utf-8").read(),
        "augen_tsx.js liegt neben dem Bot (Terminal 2)")
    if ok:
        print("✓ TSX-K0: Regel klebrig, Riegel in allen tsx-Modi, TopstepX-Tab, Inventar-Kandidaten eindeutig, Login nur mit Autofill-Beweis")
    return ok


def test_tsx_k1_vorbau():
    """K1-Vorbau (30.09.2026, nicht live): stand_tsx → tv-lesen-Vertrag (alter_s nur mit Frische-Beweis), ehrliche Codes ohne Anker,
    Schalter TSX_K1_AKTIV aus = weiter cdp_folgt."""
    import order_bot as ob
    import io
    import json
    import contextlib
    ok = True

    def chk(bed, text):
        nonlocal ok
        if not bed:
            print("  ✗ TSX-K1: " + text)
            ok = False
    U = ob.tsx_frisch_urteil
    chk(U({"raf": True, "sichtbar": "visible", "ms": 34})[0] and not U({"raf": False, "sichtbar": "visible"})[0]
        and not U({"raf": True, "sichtbar": "hidden"})[0] and not U(None)[0], "Frische nur mit Frames + sichtbar")
    L = ob.tsx_cdp_lesung
    EXT = "EXPRESS-V2-000000-00000000"
    kopf = {"balance": {"text": "$150,210.50", "wert": 150210.5}, "mll": {"text": "$145,500.00"}, "rpl": {"text": "$210.50", "wert": 210.5},
            "upl": {"text": "$0.00", "wert": 0}}
    f0, c0, m0 = L({"toasts": {}}, EXT)
    chk(c0 == "anker_fehlt" and "konto/kopf/positionen_sichtbar" in m0 and f0 == {}, f"ohne Anker ehrlich ({m0})")
    st_ok = {"konto": {"aktiv": "$150K EXPRESS | " + EXT, "kontonr": EXT, "abgekuerzt": False, "liste_offen": False, "liste": []},
             "kopf": dict(kopf, balance_relativ=False), "positionen_sichtbar": True, "positionen": [], "flach": True}
    f1, c1, m1 = L(st_ok, EXT)
    chk(c1 == "" and f1["positionen"] == [] and f1["position"] == "keine" and f1["balance"] == 150210.5 and f1["mll"] == 145500.0
        and f1["today_pnl"] == 210.5 and f1["summary"]["Balance"] == "$150,210.50" and f1["konto_aktiv"] == EXT
        and f1["balance_relativ"] is False, f"flach gelesen ({f1})")
    # Vertrag tsx-0.3.1 (Terminal 2): balance_relativ ist bool|null und wird DURCHGEREICHT — der Rohwert bleibt (Express: BAL $0.00, MLL $-4,500.00)
    kopf_rel = {"balance": {"text": "$0.00", "wert": 0}, "mll": {"text": "$-4,500.00", "wert": -4500}, "rpl": {"text": "$0.00", "wert": 0},
                "upl": {"text": "$0.00", "wert": 0}, "balance_relativ": True}
    fr, cr, _ = L(dict(st_ok, kopf=kopf_rel), EXT)
    chk(cr == "" and fr["balance_relativ"] is True and fr["balance"] == 0.0 and fr["mll"] == -4500.0 and fr["summary"]["MLL"] == "-$4,500.00"
        and fr["today_pnl"] == 0.0, f"relative Balance: Merkmal durchgereicht, nichts umgerechnet ({fr})")
    fn, cn, _ = L(dict(st_ok, kopf=dict(kopf, balance_relativ=None)), EXT)
    fx, cx, _ = L(dict(st_ok, kopf=dict(kopf, balance_relativ={"text": "x", "wert": 1})), EXT)
    fo, co, _ = L(dict(st_ok, kopf=dict(kopf)), EXT)
    chk(cn == "" and fn["balance_relativ"] is None and cx == "" and fx["balance_relativ"] is None and co == "" and fo["balance_relativ"] is None,
        "balance_relativ null / falsche Form / fehlt → None (nie geraten)")
    # flach: nur mit Beweis (No Active Position + gesperrtes Close Position); null oder Widerspruch = tabelle_unklar
    _, cf1, mf1 = L(dict(st_ok, flach=None), EXT)
    _, cf2, _ = L({k: v for k, v in st_ok.items() if k != "flach"}, EXT)
    _, cf3, mf3 = L(dict(st_ok, flach=True, positionen=[{"symbol": "MNQZ26", "seite": "buy", "menge": 1, "avg": 30592.25, "pl_text": "+$12.50"}]), EXT)
    chk(cf1 == "tabelle_unklar" and "flach nicht bewiesen" in mf1 and cf2 == "tabelle_unklar" and cf3 == "tabelle_unklar" and "Widerspruch" in mf3,
        f"flach null/fehlt/Widerspruch → tabelle_unklar ({cf1}, {cf2}, {cf3})")
    B = ob.tsx_k1_bereit
    chk(B(st_ok) and B(dict(st_ok, kopf=kopf_rel)) and not B(dict(st_ok, konto={"aktiv": None, "kontonr": None}))
        and not B(dict(st_ok, kopf={"balance": None, "mll": None, "rpl": None, "upl": None, "balance_relativ": None})) and not B(None) and not B({}),
        "Bereit-Probe: Konto-Auslöser + BAL (auch BAL 0.00 zählt), Lade-Schirm nicht")
    f2, c2, _ = L(dict(st_ok, flach=False, positionen=[{"symbol": "MNQZ26", "seite": "buy", "menge": 1, "avg": 30592.25, "pl_text": "+$12.50"}],
                        kopf=dict(kopf, upl={"text": "$12.50", "wert": 12.5})), EXT)
    chk(c2 == "" and f2["offen"] and f2["positionen"][0]["einstieg_zahl"] == 30592.25 and f2["positionen"][0]["pnl_zahl"] == 12.5
        and f2["today_pnl"] == 223.0 and "UP&L" in f2["today_label"], f"offen gelesen ({f2.get('positionen')}, {f2.get('today_pnl')})")
    f3, c3, m3 = L(dict(st_ok, konto={"aktiv": "$50K COMBINE | 50KTC-V2-000000-11111111", "kontonr": "50KTC-V2-000000-11111111"}), EXT)
    chk(c3 == "konto" and "K2" in m3, f"anderes Konto → K2 ({m3})")
    f3b, c3b, _ = L(dict(st_ok, konto={"aktiv": "$150K EXPRESS | EXPRESS-…", "kontonr": "EXPRESS-", "abgekuerzt": True}), EXT)
    chk(c3b == "konto", "abgekürzte Kennung beweist das Konto nicht")
    f3c, c3c, _ = L(dict(st_ok, kopf=dict(kopf, rpl={"text": "$-50.00"}, upl={"text": "($12.50)"})), EXT)
    chk(c3c == "" and f3c["rpl"] == -50.0 and f3c["upl"] == -12.5 and f3c["today_pnl"] == -62.5, f"negative Kopfwerte aus Text ({f3c.get('rpl')}, {f3c.get('upl')})")
    f4, c4, _ = L(dict(st_ok, kopf=dict(kopf, balance={"text": "—"})), EXT)
    f5, c5, _ = L(dict(st_ok, positionen_sichtbar=False), EXT)
    chk(c4 == "balance" and c5 == "tabelle_unklar", "BAL unlesbar / Positions-Bereich unsichtbar → ehrlich")
    # Schalter aus: tsxlesen auf cdp-PC bleibt cdp_folgt; an: K1-Weg
    alt_w, alt_k, alt_a = ob.tsx_weg_lauf, ob.modus_tsxlesen_cdp, ob.TSX_K1_AKTIV
    auf = []
    try:
        ob.tsx_weg_lauf = lambda: "cdp"
        ob.modus_tsxlesen_cdp = lambda c: auf.append(c)
        o = io.StringIO()
        with contextlib.redirect_stdout(o):
            ob.TSX_K1_AKTIV = False
            ob.modus_tsxlesen({"konto": EXT})
        ob.TSX_K1_AKTIV = True
        ob.modus_tsxlesen({"konto": EXT})
    finally:
        ob.tsx_weg_lauf, ob.modus_tsxlesen_cdp, ob.TSX_K1_AKTIV = alt_w, alt_k, alt_a
    chk(json.loads(o.getvalue())["code"] == "cdp_folgt" and auf == [{"konto": EXT}], "Schalter aus = cdp_folgt, an = K1-Weg")
    chk(ob.TSX_K1_AKTIV is True, "K1 ist ausgeliefert AN (wirkt nur auf Topstep-CDP-PCs, sonst bleibt der UIA-Weg)")

    # Verhalten des ganzen Laufs (nachgebildete Sitzung): Sitzungswahl statt eigenem Tab-Weg, Bereit-Probe, kein Klick
    class _Ws:
        def rufe(self, m, par=None, timeout=10.0):
            return {}

    class _Sitz:
        def __init__(self, staende, frisch=True):
            self.staende, self.frisch, self.ws, self.gelesen, self.klicks, self.geschlossen = list(staende), frisch, _Ws(), 0, [], 0

        def lese_js(self, ausdruck, timeout=8):
            return {"raf": self.frisch, "sichtbar": "visible" if self.frisch else "hidden", "ms": 30} if ausdruck == ob.TSX_FRISCH_JS else None

        def stand(self, opts=None):
            self.gelesen += 1
            return self.staende[min(self.gelesen, len(self.staende)) - 1]

        def klick(self, *a, **k):
            self.klicks.append(a)
            return True

        def _win_vorn(self):
            return 11, ""

        def zu(self):
            self.geschlossen += 1

    laden = {"konto": {"aktiv": None, "kontonr": None, "abgekuerzt": None, "liste_offen": False, "liste": []},
             "kopf": {"balance": None, "mll": None, "rpl": None, "upl": None, "balance_relativ": None}, "positionen_sichtbar": None,
             "positionen": [], "flach": None}
    namen = ("_puls_chrome_sicher", "_tsx_sitzung_waehlen", "_handlauf_aktiv", "_puls_diagnose_senden", "_warte", "_WIN_EINGABE",
             "TSX_K1_BEREIT_S", "puls_bot_stand", "_handlauf_setzen")
    alt_m = {n: getattr(ob, n) for n in namen}
    import threading as _th
    alt_timer = _th.Timer
    timer_log = []

    class _Timer:                                         # K1-Prüfer: der echte 120-s-Wachhund darf im Test nie laufen (os._exit!)
        def __init__(self, s_, f_):
            self.f = f_
            timer_log.append(["neu", s_])

        def start(self):
            timer_log.append(["start"])

        def cancel(self):
            timer_log.append(["cancel"])
        daemon = True

    def lauf(sz, login=True, handlauf=False, chrome=True, bereit_s=8.0, uhr=None):
        gewartet = []
        ob._puls_chrome_sicher = lambda trail, **k: chrome
        ob._handlauf_aktiv = lambda: handlauf
        ob._handlauf_setzen = lambda an: None            # K2 (01.10.2026): K1 setzt die Sperre jetzt selbst — im Test nie als Datei
        ob._puls_diagnose_senden = lambda *a, **k: None

        def warte(a, b):
            gewartet.append((a, b))
            if len(gewartet) > 200:
                raise RuntimeError("Test-Riegel: _warte über 200× (Endlosschleife)")
            if uhr is not None:
                uhr[0] += 3.0
        ob._warte = warte
        _th.Timer = _Timer
        ob._WIN_EINGABE = False
        ob.TSX_K1_BEREIT_S = bereit_s
        ob.puls_bot_stand = lambda: "Bot Test"

        def waehlen(trail, sitz=None):
            if sz is not None and sitz is not None:
                sitz[0] = sz
            return sz, (login if sz is not None else "TopstepX-Tab im Puls-Chrome nicht erreichbar.")
        ob._tsx_sitzung_waehlen = waehlen
        o_ = io.StringIO()
        with contextlib.redirect_stdout(o_):
            ob.modus_tsxlesen_cdp({"konto": EXT})
        return json.loads(o_.getvalue().strip().splitlines()[-1]), gewartet
    try:
        s1 = _Sitz([laden, laden, dict(st_ok, kopf=kopf_rel)])
        r1, w1 = lauf(s1)
        chk(r1["ok"] and r1["code"] == "" and r1["balance"] == 0.0 and r1["balance_relativ"] is True and r1["mll"] == -4500.0
            and r1["position"] == "keine" and r1["alter_s"] == 0.0 and r1["weg"] == "cdp" and r1["etappe"] == "K1" and s1.gelesen == 3
            and len(w1) == 2 and all(a_ > 0 and b_ > 0 for a_, b_ in w1) and "Bereit-Probe: 3 Lesungen" in r1["trail"] and not s1.klicks
            and s1.geschlossen >= 1, f"Lauf: Lade-Schirm abgewartet (Jitter), relativ durchgereicht, kein Klick, Sitzung zu ({r1})")
        s2 = _Sitz([laden])
        r2, _ = lauf(s2, bereit_s=0.0)
        chk(not r2["ok"] and r2["code"] == "anker_fehlt" and "lädt noch" in r2["msg"] and r2["balance"] is None and s2.geschlossen >= 1
            and "NICHT bereit" not in r2["trail"], f"nie bereit (Grenze 0 s) → anker_fehlt statt „anderes Konto“, kein Wert ({r2['code']})")
        # Grenze mit Testuhr: jede Wartezeit = 3 s → 4 Lesungen (0, 3, 6, 9 s), dann Schluss mit Vermerk
        s2b = _Sitz([laden])
        uhr = [1000.0]
        echt = ob.time.time
        ob.time.time = lambda: uhr[0]
        try:
            r2b, w2b = lauf(s2b, uhr=uhr)
        finally:
            ob.time.time = echt
        chk(not r2b["ok"] and r2b["code"] == "anker_fehlt" and s2b.gelesen == 4 and len(w2b) == 3 and "nach 8 s NICHT bereit" in r2b["trail"],
            f"Bereit-Probe endet an der Grenze ({s2b.gelesen} Lesungen, {r2b['code']})")
        s3 = _Sitz([st_ok], frisch=False)
        r3, _ = lauf(s3)
        chk(not r3["ok"] and r3["code"] == "nicht_frisch" and s3.gelesen == 0 and r3["balance"] is None and r3["alter_s"] is None,
            f"nicht frisch → ehrlich nicht_frisch, nichts gelesen ({r3['code']}, {s3.gelesen})")
        s4 = _Sitz([st_ok])
        r4, _ = lauf(s4, login="TopstepX nicht angemeldet — bitte im Puls-Chrome anmelden.")
        chk(not r4["ok"] and r4["code"] == "login" and s4.gelesen == 0 and s4.geschlossen >= 1, f"Login-Fehler → nichts gelesen, Sitzung zu ({r4['code']})")
        r5, _ = lauf(None)
        r6, _ = lauf(_Sitz([st_ok]), handlauf=True)
        r7, _ = lauf(_Sitz([st_ok]), chrome=False)
        chk(r5["code"] == "tab" and r6["code"] == "handlauf" and r7["code"] == "chrome", f"Tab/Handlauf/Chrome ehrlich ({r5['code']}, {r6['code']}, {r7['code']})")
        s8 = _Sitz([dict(st_ok, konto=dict(st_ok["konto"], liste_offen=True))])
        r8, _ = lauf(s8)
        chk(r8["ok"] and "Konto-Liste steht offen" in r8["trail"] and not s8.klicks, "offene Konto-Liste: nur vermerkt, kein Klick")
        s9 = _Sitz([dict(st_ok, positionen_sichtbar=False, flach=None)])
        r9, _ = lauf(s9)
        chk(not r9["ok"] and r9["code"] == "tabelle_unklar" and r9["balance"] == 150210.5 and r9["position"] is None,
            f"offene Position (noch nicht lesbar) → tabelle_unklar, nie keine Position ({r9['code']}, {r9.get('position')})")
        chk(timer_log.count(["start"]) >= 9 and timer_log.count(["start"]) == timer_log.count(["cancel"]),
            f"Wachhund in jedem Lauf gestartet UND abgebrochen ({timer_log.count(['start'])}/{timer_log.count(['cancel'])})")
        # B3: Wachhund feuert, während der Hauptpfad noch antworten will → genau EINE Antwort (die des Wachhunds)
        ausgaben, exits = [], []
        alt_exit = ob.os._exit
        ob.os._exit = lambda c: exits.append(c)
        try:
            class _SitzHaenger(_Sitz):
                def stand(self, opts=None):
                    self.gelesen += 1
                    [e for e in timer_log if e[0] == "neu"]      # noqa: B018 (nur Lesbarkeit)
                    feuer[0].f()                                  # Wachhund feuert mitten im Lesen
                    raise ConnectionError("Sitzung geschlossen")
            feuer = [None]

            class _TimerFeuer(_Timer):
                def __init__(self, s_, f_):
                    super().__init__(s_, f_)
                    feuer[0] = self
            _th.Timer = _TimerFeuer
            o_ = io.StringIO()
            with contextlib.redirect_stdout(o_):
                sz = _SitzHaenger([st_ok])
                ob._tsx_sitzung_waehlen = lambda trail, sitz=None: (sitz.__setitem__(0, sz) if sitz is not None else None, (sz, True))[1]
                ob.modus_tsxlesen_cdp({"konto": EXT})
            ausgaben = [l for l in o_.getvalue().splitlines() if l.startswith("{")]
        finally:
            ob.os._exit = alt_exit
        chk(len(ausgaben) == 1 and json.loads(ausgaben[0])["code"] == "haenger" and exits == [0],
            f"Wachhund + Hauptpfad: genau eine Antwort ({[json.loads(a_)['code'] for a_ in ausgaben]}, exit {exits})")
    finally:
        for n, v in alt_m.items():
            setattr(ob, n, v)
        _th.Timer = alt_timer
    # K0-Inventar (Live 30.09.2026 20:48 UTC): nach dem Login erst die Bereit-Probe; nicht bereit → nur Grund-Inventar, KEIN Klick-Schritt
    namen0 = ("_puls_chrome_sicher", "_tsx_sitzung_waehlen", "_handlauf_aktiv", "_handlauf_setzen", "_puls_diagnose_senden", "_warte",
              "_augen_pc_id", "_tsx_k0_lesen", "_tsx_k0_zustand", "TSX_K1_BEREIT_S", "puls_bot_stand")
    alt0 = {n: getattr(ob, n) for n in namen0}
    schritte0 = []

    def k0_lauf(staende):
        schritte0.clear()
        sz = _Sitz(staende)
        ob._puls_chrome_sicher = lambda trail, **k: True
        ob._tsx_sitzung_waehlen = lambda trail, sitz=None: (sitz.__setitem__(0, sz) if sitz is not None else None, (sz, True))[1]
        ob._handlauf_aktiv = lambda: False
        ob._handlauf_setzen = lambda an: None
        ob._puls_diagnose_senden = lambda *a, **k: None
        ob._warte = lambda a, b: None
        ob._augen_pc_id = lambda: "pc-xxxxxx"
        ob.TSX_K1_BEREIT_S = 0.0
        ob.puls_bot_stand = lambda: "Bot Test"
        ob._tsx_k0_lesen = lambda s_, trail, zustand, pc, blick=None: (schritte0.append("lesen:" + zustand), {"arts": ["inventar_tsx_" + zustand]})[1]
        ob._tsx_k0_zustand = lambda s_, trail, pc, art, res: schritte0.append("zustand:" + art)
        _th.Timer = _Timer
        o_ = io.StringIO()
        with contextlib.redirect_stdout(o_):
            ob.modus_tsxinventar_cdp({})
        return json.loads([l for l in o_.getvalue().splitlines() if l.startswith("{")][-1]), sz
    try:
        r0a, sz0a = k0_lauf([laden])
        s0a = list(schritte0)
        r0b, sz0b = k0_lauf([st_ok])
        s0b = list(schritte0)
    finally:
        for n, v in alt0.items():
            setattr(ob, n, v)
        _th.Timer = alt_timer
    chk(r0a["ok"] and s0a == ["lesen:grund"] and any("nicht bereit" in o_ for o_ in r0a.get("offen") or []) and sz0a.gelesen >= 1 and not sz0a.klicks,
        f"K0: Seite nach dem Login nicht bereit → nur Grund-Inventar, keine Klick-Schritte ({s0a}, {r0a.get('offen')})")
    chk(r0b["ok"] and s0b == ["lesen:grund", "zustand:konto", "zustand:bracket"], f"K0: bereit → Grund, Konto, Bracket wie bisher ({s0b})")
    chk("MuiDataGrid" in ob.TSX_K0_CHART_JS, "Chart-Probe: Tabellen-Spaltenköpfe (MUI DataGrid) zählen nicht als Linien")
    # Stapel-Prüfer: genau EINE Antwort — der Verlierer wartet, bis der Gewinner geschrieben hat (nie 0 Antworten)
    import threading as _th2
    import time as _t2
    E = ob._EineAntwort()
    reihe = []

    def gewinner():
        E.nehmen()
        _t2.sleep(0.3)                                    # hängt z. B. kurz, bevor er schreibt
        reihe.append("gewinner schreibt")
        E._fertig.set()
    t_ = _th2.Thread(target=gewinner)
    t_.start()
    _t2.sleep(0.05)
    verloren = E.nehmen(warten_s=5)
    reihe.append("verlierer zurück")
    t_.join()
    chk(verloren is False and reihe == ["gewinner schreibt", "verlierer zurück"], f"Verlierer wartet auf die Ausgabe ({reihe})")
    o_ = io.StringIO()
    E2 = ob._EineAntwort()
    with contextlib.redirect_stdout(o_):
        chk(E2.nehmen() and not E2.nehmen(warten_s=0.1), "zweites nehmen verliert")
        E2.ausgeben({"ok": True, "code": ""})
    chk(o_.getvalue().count("\n") == 1 and E2._fertig.is_set(), "ausgeben: eine Zeile, danach fertig")
    import inspect as _i0
    q_k1, q_k0 = _i0.getsource(ob.modus_tsxlesen_cdp), _i0.getsource(ob.modus_tsxinventar_cdp)
    chk(all(q.index("antwort.ausgeben(res)") < q.index("_puls_diagnose_senden") and "zuerst=_schliessen" in q for q in (q_k1, q_k0))
        and q_k0.index("_schliessen()\n            _handlauf_setzen(False)") > 0,
        "erst drucken, dann Diagnose; Wachhund schließt zuerst, K0 gibt die Handlauf-Sperre zuletzt frei")
    # B9: Combine ohne Kennung im Auslöser („$150K TRADING COMBINE |") → nie „steht"
    f9, c9, m9 = L(dict(st_ok, konto={"aktiv": "$150K TRADING COMBINE |", "kontonr": None, "abgekuerzt": True}), EXT)
    chk(c9 == "konto" and "unbekannt" in m9, f"Auslöser ohne Kennung → konto/unbekannt ({c9}, {m9[:70]})")
    # B10 + B2: Teilstring und abgekürzte Gleichheit beweisen nichts (Richtung Regression .865)
    _, c10a, _ = L(dict(st_ok, konto={"aktiv": "x", "kontonr": EXT + "1", "abgekuerzt": False}), EXT)
    _, c10b, _ = L(dict(st_ok, konto={"aktiv": "x", "kontonr": "PA" + EXT, "abgekuerzt": False}), EXT)
    _, c10c, m10c = L(dict(st_ok, konto={"aktiv": "$150K Express|" + EXT + "…", "kontonr": EXT, "abgekuerzt": True}), EXT)
    chk(c10a == "konto" and c10b == "konto" and c10c == "konto" and "vielleicht" in m10c,
        f"Teilstring/abgekürzt gleich → kein Beweis ({c10a}, {c10b}, {c10c})")
    # B6: bewiesenes Konto → konto_aktiv = External ID (auch bei anderer Schreibweise), Anzeige extra
    f6, c6, _ = L(st_ok, EXT.lower())
    chk(c6 == "" and f6["konto_aktiv"] == EXT.lower() and f6["konto_anzeige"] == EXT, f"konto_aktiv = ext, konto_anzeige = Seite ({f6.get('konto_aktiv')})")
    # B1/B4: Minus vor dem Dollar (tvGeldText liest nur ein führendes Minus), auch im UIA-Weg über tsx_summary
    S = ob.tsx_summary
    chk(S({"balance": -300.0, "mll": -4500, "rpl": 12.5, "upl": None}) == {"Balance": "-$300.00", "MLL": "-$4,500.00", "RP&L": "$12.50", "UP&L": None}
        and S({"balance": -0.0})["Balance"] == "$0.00" and S({"balance": 154504.88})["Balance"] == "$154,504.88" and S(None)["Balance"] is None,
        "summary: -$300.00 / $154,504.88 / -0.0 → $0.00")
    fm, cm, _ = L(dict(st_ok, kopf=dict(kopf_rel, balance={"text": "$-300.00", "wert": -300})), EXT)
    chk(cm == "" and fm["balance"] == -300.0 and fm["summary"]["Balance"] == "-$300.00", "K1: negative relative Balance mit Minus vorn")
    import inspect as _i
    chk(_i.getsource(ob.modus_tsxlesen).count("tsx_summary(werte)") == 1 and 'f"${werte[k]' not in _i.getsource(ob),
        "UIA-Weg (Lesen + Order) nutzt dieselbe summary-Formatierung")
    # B11: Kopfzeile — bis zu drei Vorsatz-Knoten (auch leere), Wert noch nicht gezeichnet
    K = ob.tsx_kopf_werte
    kk = K([("RP&L:", None, "Text"), ("", None, "Text"), ("-", None, "Text"), ("$", None, "Text"), ("50.00", None, "Text")])
    kb = K([("BAL:", None, "Text"), ("$", None, "Text")])
    chk(kk["rpl"] == -50.0 and kb["balance"] is None, f"Vorsatz-Knoten: leer + - + $ → -50.00; nur „$“ → None ({kk['rpl']}, {kb['balance']})")
    if ok:
        print("✓ TSX-K1-Vorbau: Vertrag wie tv-lesen, balance_relativ durchgereicht, flach nur mit Beweis, Bereit-Probe, Schalter aus")
    return ok


def test_tsx_k2():
    """K2 (01.10.2026, „das mit dem Dropdown"): TopstepX-Konto im Dropdown wechseln — nur Konto, KEINE Order. Reine Regeln, der
    Wechsel gegen eine nachgebildete TopstepX-Seite (4 Konten wie beim ersten Topstep-PC: 2× Express, 2× Combine „Ineligible"; nur
    erfundene Kennungen) und die ganze Kette in EINEM Lauf: kalt (Chrome aus), ohne Tab, ausgeloggt, falsches Konto."""
    import order_bot as ob
    import io
    import json
    import contextlib
    import tempfile
    import threading as _th
    ok = True

    def chk(bed, text):
        nonlocal ok
        if not bed:
            print("  ✗ TSX-K2: " + text)
            ok = False
    E1, E2 = "EXPRESS-V2-000000-00000001", "EXPRESS-V2-000000-00000002"
    C3, C4 = "150KTC-SKU-V2-000000-00000003", "150KTC-SKU-V2-000000-00000004"
    LABEL = {E1: "$150K Express", E2: "$150K Express", C3: "$150K Trading Combine", C4: "$150K Trading Combine"}
    INELIG = {C3, C4}

    def zeile(i, kid, **extra):
        z = {"text": LABEL.get(kid, "$150K Express") + "|" + kid + (" (Ineligible)" if kid in INELIG else ""), "label": LABEL.get(kid, "$150K Express"),
             "id": kid, "markiert": None, "ineligible": kid in INELIG, "hinweis": "Ineligible" if kid in INELIG else None, "aus": False,
             "rect": [17, 47 + 30 * i, 416, 30], "zu": {"disabled": False, "readonly": False, "verdeckt": False, "oben": None}}
        z.update(extra)
        return z
    # ── reine Regeln ──
    U = ob.tsx_konto_urteil
    chk(U({"aktiv": "$150K Express|" + E1, "kontonr": E1, "abgekuerzt": False}, E1) == "ja"
        and U({"aktiv": "$150K Express|" + E1, "kontonr": E1, "abgekuerzt": False}, E2) == "nein"
        and U({"aktiv": "$150K Express|EXPRESS-…", "kontonr": "EXPRESS", "abgekuerzt": True}, E1) == "vielleicht"
        and U({"aktiv": None, "kontonr": None}, E1) == "fehlt" and U(None, E1) == "fehlt", "Konto-Urteil ja/nein/vielleicht/fehlt")
    W = ob.tsx_k2_eintrag
    liste = [zeile(0, E1), zeile(1, E2), zeile(2, C3), zeile(3, C4)]
    x, n, g = W(liste, E2)
    chk(x is not None and x["id"] == E2 and n == 1 and g == "", f"Treffer genau einmal ({g})")
    x, n, g = W(liste, C3)
    chk(x is not None and x["ineligible"] is True, "Ineligible zum LESEN wählbar (Hinweis kommt in die Antwort)")
    x, n, g = W(liste, "EXPRESS-V2-000000-00000009")
    chk(x is None and n == 0 and "nicht in der Liste" in g, f"kein Treffer ({g})")
    x, n, g = W(liste + [zeile(4, E2)], E2)
    chk(x is None and n == 2 and "nicht eindeutig" in g, f"zwei Treffer ({g})")
    x, n, g = W([zeile(0, E2, aus=True)], E2)
    x2, _, g2 = W([zeile(0, E2, zu={"verdeckt": True, "oben": {"text": "Dialog"}})], E2)
    x3, _, g3 = W([zeile(0, E2, rect=None)], E2)
    chk(x is None and x2 is None and x3 is None and "gesperrt" in g and "verdeckt" in g2 and "Rechteck" in g3, f"gesperrt/verdeckt/ohne Rechteck nie ({g}, {g2}, {g3})")
    chk(W(liste, "abc")[0] is None and W(liste, E1)[0]["id"] == E1, "kurze Kennung nie, volle Kennung exakt (kein Präfix-Treffer)")
    kopf = lambda b: {"kopf": {"balance": {"text": f"${b:,.2f}", "wert": b}, "mll": {"text": "$-4,500.00", "wert": -4500}, "rpl": {"wert": 0}, "upl": {"wert": 0}}}
    chk(ob.tsx_kopf_gleich(kopf(0.0), kopf(0.0)) and not ob.tsx_kopf_gleich(kopf(0.0), kopf(12.5))
        and not ob.tsx_kopf_gleich({"kopf": {"balance": None}}, {"kopf": {"balance": None}}), "Kopfzeile zweimal gleich (BAL lesbar)")

    # ── nachgebildete TopstepX-Seite: stand() folgt dem Zustand, klick()/taste() verändern ihn ──
    class _Tsx:
        def __init__(self, aktiv=E1, ids=(E1, E2, C3, C4), offen=False, esc_wirkt=True, zeile_druck=True, bleibt_offen=False,
                     ausloeser_verdeckt=False, eingeloggt=True, bal=None):
            self.aktiv, self.ids, self.offen, self.esc_wirkt = aktiv, list(ids), offen, esc_wirkt
            self.zeile_druck, self.bleibt_offen, self.ausloeser_verdeckt, self.eingeloggt = zeile_druck, bleibt_offen, ausloeser_verdeckt, eingeloggt
            self.bal = bal or {E1: 0.0, E2: 1250.0, C3: 150210.5, C4: 149000.0}
            self.klicks, self.pruef, self.ws, self.geschlossen = [], [], self, 0

        def rufe(self, m, par=None, timeout=10.0):
            if m == "Page.navigate":
                self.klicks.append("Neuladen")
            return {}

        def stand(self, opts=None):
            if not self.eingeloggt:
                return {"konto": {"aktiv": None, "kontonr": None, "abgekuerzt": None, "liste_offen": False, "liste": []},
                        "kopf": {"balance": None, "mll": None, "rpl": None, "upl": None, "balance_relativ": None}, "positionen_sichtbar": None,
                        "positionen": [], "flach": None, "popups": []}
            ko = {"aktiv": LABEL.get(self.aktiv, "$150K Express") + "|" + self.aktiv, "kontonr": self.aktiv, "abgekuerzt": False,
                  "rect": [68, 4, 194, 34], "zu": {"disabled": False, "readonly": False, "verdeckt": self.offen or self.ausloeser_verdeckt, "oben": None},
                  "liste_offen": self.offen, "liste": [zeile(i, k) for i, k in enumerate(self.ids)] if self.offen else []}
            b = self.bal.get(self.aktiv, 0.0)
            return {"konto": ko, "kopf": {"balance": {"text": f"${b:,.2f}", "wert": b}, "mll": {"text": "$-4,500.00", "wert": -4500},
                                          "rpl": {"text": "$0.00", "wert": 0}, "upl": {"text": "$0.00", "wert": 0}, "balance_relativ": b < 75000},
                    "positionen_sichtbar": True, "positionen": [], "flach": True, "popups": []}

        def klick(self, r, name, toast_ok=False, pruef=None):
            self.klicks.append(name)
            self.pruef.append(pruef)
            if name.startswith("PLATFORM LOGIN"):
                self.eingeloggt = True
                return True
            if name == "Konto-Auslöser":
                if not self.ausloeser_verdeckt:
                    self.offen = True
                return True
            if name.startswith("Konto "):
                if not self.zeile_druck:
                    return False
                if not self.bleibt_offen:
                    self.aktiv, self.offen = name.split(" ", 1)[1], False
                return True
            return True

        def taste(self, k, modifiers=0):
            self.klicks.append("Taste " + k)
            if k == "Escape" and self.esc_wirkt:
                self.offen = False

        def lese_js(self, ausdruck, timeout=8):
            if ausdruck == ob.TSX_FRISCH_JS:
                return {"raf": True, "sichtbar": "visible", "ms": 30}
            if ausdruck == ob.TSX_K0_BLICK_JS:
                return {"login": {"seite": not self.eingeloggt, "knopf": {"rect": [900, 600, 200, 40], "text": "PLATFORM LOGIN"},
                                  "user": {"autofill": True, "gefuellt": True}, "pw": {"autofill": True, "gefuellt": True}, "knoepfe": 1}}
            return None

        def _win_vorn(self):
            return 11, ""

        def _seite_abwarten(self, sek=25.0):
            return None

        def _augen_laden(self):
            return None

        def zu(self):
            self.geschlossen += 1
    alt_w = ob._warte
    ob._warte = lambda a, b: None
    try:
        def sichern(sz, ziel):
            t = []
            r = ob._tsx_konto_sichern(sz, ziel, sz.stand(), t)
            return r, t
        a = _Tsx()
        (ok_a, c_a, m_a, st_a, ex_a), t_a = sichern(a, E2)
        chk(ok_a and a.klicks == ["Konto-Auslöser", "Konto " + E2] and ex_a.get("konto_gewechselt") == {"von": E1, "zu": E2}
            and st_a["konto"]["kontonr"] == E2 and not st_a["konto"]["liste_offen"] and "konto_hinweis" not in ex_a,
            f"Treffer: Auslöser → Zeile → Konto steht, Liste zu ({a.klicks}, {ex_a})")
        chk(a.pruef[0]["text"] == E1 and a.pruef[1]["text"] == E2 and a.pruef[1]["rect"] == [17, 77, 416, 30] and "flatten" in a.pruef[1]["tabu"],
            f"jeder Druck mit Ziel-Beweis: Auslöser-Kennung, volle Ziel-Kennung, Rechteck der Zeile, Tabu-Wörter ({a.pruef})")
        b = _Tsx()
        (ok_b, c_b, m_b, st_b, ex_b), _ = sichern(b, "EXPRESS-V2-000000-00000009")
        chk(not ok_b and c_b == "konto_nicht_erreicht" and b.klicks == ["Konto-Auslöser", "Taste Escape"] and not b.offen and ex_b.get("konto_treffer") == 0
            and "nicht in der Liste" in m_b, f"kein Treffer: Esc, nichts gewählt ({b.klicks}, {m_b})")
        c = _Tsx(ids=(E1, E2, C3, E2))
        (ok_c, c_c, m_c, _, ex_c), _ = sichern(c, E2)
        chk(not ok_c and c.klicks == ["Konto-Auslöser", "Taste Escape"] and ex_c.get("konto_treffer") == 2 and "nicht eindeutig" in m_c,
            f"zwei Treffer: Esc, nichts gewählt ({c.klicks})")
        d = _Tsx(bleibt_offen=True)
        (ok_d, c_d, m_d, _, _), _ = sichern(d, E2)
        chk(not ok_d and d.klicks == ["Konto-Auslöser", "Konto " + E2, "Taste Escape"] and not d.offen and "blieb offen" in m_d,
            f"Liste bleibt nach dem Zeilen-Klick offen: EIN Zeilen-Druck, dann Esc ({d.klicks})")
        e_ = _Tsx()
        (ok_e, _, _, _, ex_e), _ = sichern(e_, C3)
        chk(ok_e and ex_e.get("konto_hinweis") == "Ineligible" and ex_e["konto_gewechselt"]["zu"] == C3, f"Ineligible: gewechselt, Hinweis ({ex_e})")
        f_ = _Tsx(offen=True)
        (ok_f, _, _, _, _), t_f = sichern(f_, E2)
        chk(ok_f and f_.klicks == ["Taste Escape", "Konto-Auslöser", "Konto " + E2] and any("nicht von diesem Lauf" in x_ for x_ in t_f),
            f"fremd offene Liste: erst Esc, nie daraus wählen, dann selbst öffnen ({f_.klicks})")
        f2 = _Tsx(offen=True, esc_wirkt=False)
        (ok_f2, c_f2, _, _, _), _ = sichern(f2, E2)
        chk(not ok_f2 and c_f2 == "konto_nicht_erreicht" and f2.klicks == ["Taste Escape"], f"fremd offen + Esc wirkt nicht: EIN Esc, raus ({f2.klicks})")
        g_ = _Tsx(ausloeser_verdeckt=True)
        (ok_g, c_g, m_g, _, _), _ = sichern(g_, E2)
        chk(not ok_g and g_.klicks == [] and "verdeckt" in m_g, f"Auslöser verdeckt (Dialog): kein Klick ({m_g})")
        # TSX-LADEN (05.10.2026): Lade-Schirm über dem Auslöser = warten und neu lesen, jede andere Verdeckung = sofort raus wie bisher
        LADE = {"disabled": False, "readonly": False, "verdeckt": True,
                "oben": {"tag": "div", "role": "", "text": "Loading the Ultimate Trading Experience", "rect": [0, 0, 1920, 945]}}

        class _TsxL(_Tsx):
            def __init__(self, lade_n, **k):
                super().__init__(**k)
                self.lade_n, self.staende = lade_n, 0

            def stand(self, opts=None):
                st_ = super().stand(opts)
                self.staende += 1
                if self.lade_n > 0 and isinstance(st_.get("konto"), dict) and st_["konto"].get("aktiv"):
                    self.lade_n -= 1
                    st_["konto"]["zu"] = dict(LADE)
                return st_
        LS, B1 = ob.tsx_ladeschirm, ob.tsx_k1_bereit
        chk(LS({"zu": LADE}) and not LS({"zu": dict(LADE, verdeckt=False)}) and not LS({"zu": {"verdeckt": True, "oben": {"text": "Dialog"}}})
            and not LS({"zu": {"verdeckt": True, "oben": "ausserhalb"}}) and not LS({"zu": {"verdeckt": True, "oben": None}}) and not LS(None)
            and not LS({}), "Lade-Schirm nur mit seinem Text über dem Auslöser (Dialog/außerhalb/leer nie)")
        l0 = _TsxL(1)
        st_l = l0.stand()
        l0b = _TsxL(0)
        chk(not B1(st_l) and B1(l0b.stand()) and st_l["kopf"]["balance"] is not None,
            "Bereit-Probe: Konto + BAL lesbar, aber Lade-Schirm darüber → noch nicht bereit; ohne ihn bereit wie bisher")
        l1 = _TsxL(4)                                    # 1 Lesung im Aufruf + 3 im Warten, dann frei
        (ok_l, c_l, m_l, st_l1, ex_l), t_l = sichern(l1, E2)
        chk(ok_l and l1.klicks == ["Konto-Auslöser", "Konto " + E2] and ex_l.get("konto_gewechselt") == {"von": E1, "zu": E2}
            and any("Lade-Schirm" in x and "weiter" in x for x in t_l),
            f"Lade-Schirm geht weg → danach derselbe Weg wie immer: Auslöser → Zeile ({l1.klicks}, {t_l})")
        alt_ls = ob.TSX_LADEN_K2_S
        ob.TSX_LADEN_K2_S = 0.05
        try:
            l2 = _TsxL(10 ** 9)
            (ok_l2, c_l2, m_l2, _, _), _ = sichern(l2, E2)
        finally:
            ob.TSX_LADEN_K2_S = alt_ls
        chk(not ok_l2 and c_l2 == "konto_nicht_erreicht" and l2.klicks == [] and "TopstepX lädt noch" in m_l2 and "Dialog offen" not in m_l2,
            f"Lade-Schirm bleibt → kein Klick, ehrliche Meldung lädt noch ({m_l2})")
        l3 = _TsxL(2, aktiv=E2)
        (ok_l3, _, _, _, ex_l3), _ = sichern(l3, E2)
        chk(ok_l3 and l3.klicks == [] and "konto_gewechselt" not in ex_l3, "richtiges Konto steht schon → kein Warten, kein Klick (wie bisher)")
        h = _Tsx(aktiv=E2)
        (ok_h, _, _, _, ex_h), _ = sichern(h, E2)
        chk(ok_h and h.klicks == [] and "konto_gewechselt" not in ex_h, "Konto steht schon: kein Klick")
        i_ = _Tsx(zeile_druck=False)
        (ok_i, _, m_i, _, _), _ = sichern(i_, E2)
        chk(not ok_i and i_.klicks == ["Konto-Auslöser", "Konto " + E2, "Taste Escape"] and "nicht gedrückt" in m_i and not i_.offen,
            f"Zeile ohne Druck (kein Ziel-Beweis): Esc, nichts gewechselt ({i_.klicks})")
        j = _Tsx()
        j.klick = lambda r, name, toast_ok=False, pruef=None: (j.klicks.append(name), False)[1]
        (ok_j, _, m_j, _, _), _ = sichern(j, E2)
        chk(not ok_j and j.klicks == ["Konto-Auslöser"] and "Auslöser nicht gedrückt" in m_j, f"Auslöser ohne Druck: nichts weiter ({j.klicks})")
        # Kopfzeile nach dem Wechsel: erst zweimal gleich zählt (BAL lädt nach)
        k = _Tsx(aktiv=E2)
        seq = [dict(k.stand(), kopf=dict(k.stand()["kopf"], balance={"text": "$0.00", "wert": 0.0})), k.stand(), k.stand()]
        k.stand = lambda opts=None: seq.pop(0) if seq else _Tsx(aktiv=E2).stand()
        st_k, frisch_k = ob._tsx_kopf_frisch(k, {"kopf": {"balance": {"wert": 0.0}}, "konto": {}}, E2, [])
        chk(frisch_k and st_k["kopf"]["balance"]["wert"] == 1250.0, f"Kopfzeile: nachgeladene BAL erst nach zwei gleichen Lesungen ({st_k['kopf']['balance']})")
    finally:
        ob._warte = alt_w

    # ── ganze Kette in EINEM Lauf: kalt, ohne Tab, ausgeloggt, falsches Konto → Chrome mit TopstepX, Tab auf, EIN Login-Klick, K2, K1 ──
    namen = ("_puls_chrome_sicher", "_cdp_http", "_AugenSitzung", "_handlauf_aktiv", "_handlauf_setzen", "_puls_diagnose_senden", "_warte",
             "_WIN_EINGABE", "puls_bot_stand", "_AUGEN_HIER", "_augen_js_holen", "TSX_K2_AKTIV")
    alt_m = {n: getattr(ob, n) for n in namen}
    alt_timer = _th.Timer

    class _Timer:
        def __init__(self, s_, f_):
            self.s = s_

        def start(self):
            wachhund.append(self.s)

        def cancel(self):
            pass
        daemon = True
    wachhund = []
    try:
        def kette(seite, tabs_da=False, chrome_an=False, k2=True):
            log = {"chrome": [], "neu": 0, "sperre": []}
            tab = {"id": "T1", "type": "page", "url": ob.TSX_URL, "title": "TopstepX", "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/T1"}
            zustand = {"tabs": [tab] if tabs_da else [], "chrome": chrome_an}

            def chrome(trail, **k):
                log["chrome"].append(k.get("url"))
                zustand["chrome"] = True
                return True

            def http(pfad, *a, **k):
                if not zustand["chrome"]:
                    return None
                if pfad.startswith("/json/new?"):
                    log["neu"] += 1
                    zustand["tabs"] = [tab]
                    return {"id": "T1"}
                if pfad == "/json/list":
                    return list(zustand["tabs"])
                return {}
            ob._puls_chrome_sicher = chrome
            ob._cdp_http = http
            ob._AugenSitzung = lambda trail, ziel=None, js_datei="augen.js", tv_riegel=True: seite
            ob._handlauf_aktiv = lambda: False
            ob._handlauf_setzen = lambda an: log["sperre"].append(an)
            ob._puls_diagnose_senden = lambda *a, **k: None
            ob._warte = lambda a, b: None
            ob._WIN_EINGABE = False
            ob.puls_bot_stand = lambda: "Bot Test"
            ob._AUGEN_HIER = tempfile.mkdtemp()
            ob.TSX_K2_AKTIV = k2
            _th.Timer = _Timer
            o_ = io.StringIO()
            with contextlib.redirect_stdout(o_):
                ob.modus_tsxlesen_cdp({"konto": E2, "firma": "Topstep"})
            return json.loads(o_.getvalue().strip().splitlines()[-1]), log
        s1 = _Tsx(aktiv=E1, eingeloggt=False)
        r1, l1 = kette(s1)
        chk(r1["ok"] and r1["code"] == "" and r1["konto"] == E2 and r1["balance"] == 1250.0 and r1["konto_gewechselt"] == {"von": E1, "zu": E2}
            and s1.klicks == ["PLATFORM LOGIN (Autofill bewiesen)", "Konto-Auslöser", "Konto " + E2] and l1["chrome"] and l1["chrome"][0] == ob.TSX_URL
            and l1["neu"] == 1 and l1["sperre"] == [True, False] and s1.geschlossen >= 1 and "Konto gewechselt" in r1["msg"]
            and "TopstepX-Tab geöffnet" in r1["trail"] and "K2: Konto gewechselt" in r1["trail"],
            f"Kette kalt → Tab auf → EIN Login-Klick → K2 → gelesen ({r1.get('code')}, {s1.klicks}, {l1}, {r1.get('msg')})")
        chk(wachhund and all(w_ == ob.TSX_K1_WACHHUND_S for w_ in wachhund) and ob.TSX_K1_WACHHUND_S < 150, f"Wachhund {wachhund} unter 150 s (Panel)")
        s2 = _Tsx(aktiv=E2)
        r2, l2 = kette(s2, tabs_da=True, chrome_an=True)
        chk(r2["ok"] and s2.klicks == [] and l2["neu"] == 0 and "konto_gewechselt" not in r2, f"alles schon da: kein Klick, kein neuer Tab ({s2.klicks}, {l2})")
        s3 = _Tsx(aktiv=E1)
        r3, _ = kette(s3, tabs_da=True, chrome_an=True, k2=False)
        chk(not r3["ok"] and r3["code"] == "konto" and s3.klicks == [], f"K2 aus: ehrlich code 'konto', kein Klick ({r3['code']})")
        s4 = _Tsx(aktiv=E1, ids=(E1, C3, C4))
        r4, l4 = kette(s4, tabs_da=True, chrome_an=True)
        chk(not r4["ok"] and r4["code"] == "konto_nicht_erreicht" and r4["schritt"] == "konto" and s4.klicks == ["Konto-Auslöser", "Taste Escape"]
            and r4.get("konto_treffer") == 0 and r4["balance"] is None and l4["sperre"] == [True, False],
            f"Ziel nicht in der Liste: Esc, nichts gelesen, Sperre wieder frei ({r4['code']}, {s4.klicks})")
        s5 = _Tsx(aktiv=E1)
        r5, _ = kette(s5, tabs_da=True, chrome_an=True)
        chk(r5["ok"] and r5["konto"] == E2 and r5["etappe"] == "K1" and r5["position"] == "keine", f"falsches Konto im offenen Tab: gewechselt, gelesen ({r5['code']})")
    finally:
        for n_, v_ in alt_m.items():
            setattr(ob, n_, v_)
        _th.Timer = alt_timer
    # Quelltext-Riegel: K2 klickt nie ein Order-/Close-Wort, keine Order-Funktion im Konto-Schritt
    import inspect
    q = inspect.getsource(ob._tsx_konto_sichern)
    chk("TSX_K0_TABU" in q and "pruef=" in q and not any(w_ in q for w_ in ("kaufen(", "order_senden", "flatten", "Buy", "Sell")),
        "K2: jeder Druck mit Tabu-Wörtern, keine Order-Wege")
    felder = ob.PULS_ERGEBNIS_FELDER
    chk(all(f_ in felder for f_ in ("balance", "upl", "balance_relativ")) and len(set(felder)) == len(felder),
        "PULS_ERGEBNIS_FELDER: balance/upl/balance_relativ dabei, keine Doppelten")
    # T1-Nachtrag: Vorzeichen im UIA-Weg (Drei-/Vier-Knoten-Form, Minus hinter dem Dollar)
    G = ob.tsx_geld
    K = lambda namen_: ob.tsx_kopf_werte([(n_, None, "Text") for n_ in namen_])
    chk(G("$-300.00") == -300.0 and G("-$300.00") == -300.0 and G("($300.00)") == -300.0 and G("$300.00") == 300.0
        and K(["RP&L:", "$", "-50.00"])["rpl"] == -50.0 and K(["RP&L:", "-", "$", "50.00"])["rpl"] == -50.0
        and K(["BAL:", "$", "154,504.88", "MLL:", "$-4,500.00"]) == {"balance": 154504.88, "mll": -4500.0, "rpl": None, "upl": None},
        "Vorzeichen: $-300.00 / -$300.00 / ($300.00) / RP&L $·-50.00 / -·$·50.00")
    if ok:
        print("✓ TSX-K2: Konto im Dropdown wechseln (Treffer, kein Treffer, doppelt, bleibt offen, Ineligible, fremd offen, verdeckt), "
              "Kopfzeile frisch, ganze Kette in einem Lauf (kalt, ohne Tab, ausgeloggt, falsches Konto), Felder, Vorzeichen")
    return ok


def test_tsx_k3a():
    """K3a (01.10.2026, Finn: „Contract reinklicken, MNQ oder NQ auswählen; # of Contracts reinklicken, Zahl weg, eigentliche Zahl"):
    Ticket über das Puls-Chrome füllen — Probe, NIE ein Order-Knopf. Nachbau der Order-Karte (Vorschläge MNQZ26/NQZ26/MNQH27, Menge
    1/3/15), echte Regeln + echte Schritte + echte Kette; menschliche Pausen (1–2 s, Hover 0,3–0,8 s) an der echten Sitzungs-Klasse."""
    import order_bot as ob
    import inspect as _i
    import threading as _th
    import io
    import contextlib
    import json
    import os
    import re
    ok = True

    def chk(bed, text):
        nonlocal ok
        if not bed:
            print("  ✗ TSX-K3a: " + text)
            ok = False
    E = "EXPRESS-V2-000000-30000003"
    # ── reine Regeln ─────────────────────────────────────────────────────────────────────────────────────────
    import calendar as _cal
    ts = lambda y, m, d: _cal.timegm((y, m, d, 12, 0, 0))
    chk(ob.tsx_frontmonat(ts(2026, 10, 1)) == "Z26" and ob.tsx_frontmonat(ts(2026, 12, 9)) == "Z26"
        and ob.tsx_frontmonat(ts(2026, 12, 11)) == "H27" and ob.tsx_frontmonat(ts(2026, 9, 9)) == "U26"
        and ob.tsx_frontmonat(ts(2026, 9, 11)) == "Z26", "Front-Monat wie das Frontend: Roll 8 Tage vor dem 3. Freitag, zweistelliges Jahr")
    V = [{"code": "MNQZ26", "rect": [10, 130, 400, 40], "code_rect": [40, 134, 60, 16]},
         {"code": "NQZ26", "rect": [10, 170, 400, 40], "code_rect": [40, 174, 50, 16]},
         {"code": "MNQH27", "rect": [10, 210, 400, 40], "code_rect": [40, 214, 60, 16]}]
    z = ob.tsx_k3_contract_ziel
    chk(z(V, "NQ", ts(2026, 10, 1))[0]["code"] == "NQZ26" and z(V, "MNQ", ts(2026, 10, 1))[0]["code"] == "MNQZ26"
        and z(V, "MNQ", ts(2026, 12, 11))[0]["code"] == "MNQH27", "MNQ ≠ NQ; zwei MNQ-Monate → Front-Monat")
    chk(z(V[1:2], "MNQ")[0] is None and z([], "NQ")[0] is None and z(V[:1], "MNQ")[0]["code"] == "MNQZ26"
        and z([{"code": "MNQZ26X"}], "MNQ")[0] is None, "kein passender Code → None (nie NQZ26 für MNQ, nie Teilstring)")
    chk(z([V[0], {"code": "MNQU26"}], "MNQ", ts(2026, 12, 11))[0] is None, "zwei Monate ohne den Front-Monat → None")
    # Contract gewählt? (06.10.2026, Finn live: Feld blieb 'mnq', Chart stand auf MNQZ26) — Feld = Code ODER Wurzel + Chart-Titel = Code
    cs = ob.tsx_k3_contract_steht
    T = "MNQZ26 $31,516.00 ▲ +0.63%"
    chk(cs({"wert": "MNQZ26", "offen": False}, "MNQZ26", "MNQ", None) == (True, "feld")
        and cs({"wert": "mnq", "offen": False}, "MNQZ26", "MNQ", T) == (True, "chart")
        and cs({"wert": "", "offen": False}, "MNQZ26", "MNQ", T) == (True, "chart")
        and cs({"wert": "mnqz26", "offen": False}, "MNQZ26", "MNQ", None)[0], "Contract steht: Feld = Code; Wurzel/leer im Feld + Chart-Titel = Code")
    chk(not cs({"wert": "MNQZ26", "offen": True}, "MNQZ26", "MNQ", T)[0]                       # Liste offen zählt nie
        and not cs({"wert": "nq", "offen": False}, "MNQZ26", "NQ", T)[0]                        # „nq" getippt, Chart MNQ → nie
        and not cs({"wert": "mnq", "offen": False}, "NQZ26", "MNQ", "NQZ26 $31,500.00")[0]      # Code NQZ26, Wurzel MNQ → nie
        and not cs({"wert": "mnq", "offen": False}, "MNQZ26", "MNQ", "NQZ26 $31,500.00")[0]     # Chart auf NQ → nie
        and not cs({"wert": "mnq", "offen": False}, "MNQZ26", "MNQ", None)[0]                   # ohne Titel kein Chart-Beweis
        and not cs({"wert": "mn", "offen": False}, "MNQZ26", "MNQ", T)[0]                       # halb getippt → nie
        and not cs({"wert": "NQZ26", "offen": False}, "MNQZ26", "MNQ", T)[0]                    # fremder Code im Feld → nie
        and not cs(None, "MNQZ26", "MNQ", T)[0] and not cs({"wert": "MNQZ26", "offen": False}, "", "MNQ", T)[0],
        "Contract steht NICHT: Liste offen, falsche Wurzel, Chart auf anderem Contract, kein Titel, halb/fremd getippt")
    mp = ob.tsx_k3_menge_passt
    chk(mp("1", 1) and mp(" 15 ", 15) and mp("3", 3) and not mp("3", 1) and not mp("", 1) and not mp("1.5", 1) and not mp(None, 1)
        and not mp("15a", 15), "Menge: genau die Zahl, sonst nie")
    b0, f0 = ob.tsx_order_befehl({"ext_id": E, "symbol": "MNQ", "richtung": "buy", "volumen": 1}, tp_pflicht=False)
    b1, f1 = ob.tsx_order_befehl({"ext_id": E, "symbol": "MNQ", "richtung": "buy", "volumen": 1})
    chk(b0 and not f0 and b0["brackets"] is None and b1 is None and "TP" in f1, "ohne TP: K3a-Befehl ok (brackets None), UIA-Befehl verlangt TP")

    def seite(**kw):
        z_ = dict(konto_ok=True, flach=True, ordertyp="Market", contract="MNQZ26", offen=False, menge="3", popups=None)
        z_.update(kw)
        return z_

    def stand_aus(zz, typed="", fokus=None):
        vorsch = [dict(v, text=v["code"] + " · Nasdaq", zu={"disabled": False, "verdeckt": False})
                  for v in zz.get("liste", V) if zz["offen"] and typed.upper() in str(v["code"])]    # MUI: „enthält" („nq" → MNQZ26 + NQZ26)
        n = zz["menge"] if str(zz["menge"]).isdigit() else "0"
        return {"v": zz.get("v", "tsx-0.5.0"),
                "konto": {"aktiv": f"$150K Express|{E if zz['konto_ok'] else 'EXPRESS-V2-000000-39999999'}",
                          "kontonr": E if zz["konto_ok"] else "EXPRESS-V2-000000-39999999", "abgekuerzt": False, "liste_offen": False, "liste": []},
                "kopf": {"balance": {"text": "$0.00", "wert": 0.0}, "mll": {"text": "$-4,500.00", "wert": -4500.0},
                         "rpl": {"text": "$0.00", "wert": 0.0}, "upl": {"text": "$0.00", "wert": 0.0}, "balance_relativ": True},
                "positionen": [], "positionen_sichtbar": True, "flach": True if zz["flach"] else None, "popups": zz["popups"] or [],
                "toasts": {"gruppen": [], "meldungen": []},
                "ticket": None if zz.get("ohne_ticket") else dict(
                    {"anzeigen": [{"testid": "order-card-display-value-no-position", "text": "No Active Position"}]},
                    **({} if zz.get("alt") else {
                        "k3": True,
                        "contract": {"wert": zz["contract"] if not zz["offen"] else typed, "rect": [1582, 92, 376, 28], "offen": zz["offen"],
                                     "fokus": fokus == "contract", "zu": {"disabled": False, "verdeckt": False}},
                        "vorschlaege": vorsch,
                        "menge": {"wert": zz["menge"], "rect": [1567, 188, 470, 40], "fokus": fokus == "menge",
                                  "zu": {"disabled": False, "verdeckt": False}},
                        "ordertyp": {"text": zz["ordertyp"], "rect": [1567, 138, 470, 40]},
                        "kauf": {"text": zz.get("kauf_text") or f"Buy +{n} @ Market", "rect": [1675, 416, 123, 26],
                                 "zu": {"disabled": bool(zz.get("knopf_gesperrt")), "verdeckt": False}},
                        "verkauf": {"text": zz.get("verkauf_text") or f"Sell -{n} @ Market", "rect": [1804, 416, 124, 26],
                                    "zu": {"disabled": bool(zz.get("knopf_gesperrt")), "verdeckt": False}}}))}

    class _Karte:
        """Nachbau der TopstepX-Order-Karte: Klick ins Feld = Fokus (Contract-Feld öffnet die Liste), Strg+A markiert, Rücktaste
        leert, Tippen ersetzt/füllt, Klick auf einen Vorschlag wählt ihn, Esc schließt die Liste. Klick auf einen Order-Knopf = Fehler."""
        def __init__(self, zz):
            self.z, self.fokus, self.markiert, self.typed = zz, None, False, ""
            self.klicks, self.pruef, self.tasten, self.rects = [], [], [], []

        def stand(self, opts=None):
            return stand_aus(self.z, self.typed, self.fokus)

        def klick(self, r, name, toast_ok=False, pruef=None):
            self.klicks.append(name)
            self.pruef.append(pruef)
            self.rects.append(list(r))
            ereignisse.append(("klick", name))
            if name == "Contract-Feld":
                self.fokus, self.z["offen"], self.typed = (None if self.z.get("kein_fokus") else "contract"), True, self.z["contract"]
            elif name.startswith("Contract "):
                if self.z.get("klick_wirkt", True):
                    self.z["contract"], self.z["offen"], self.fokus = name.split(" ", 1)[1], bool(self.z.get("liste_bleibt_offen")), None
                    self.typed = self.z["contract"]          # das Feld zeigt den gewählten Code — auch wenn die Liste offen bleibt
            elif name == "# of Contracts":
                self.fokus = "menge"
            else:
                raise AssertionError("unerwarteter Klick " + name)
            return True

        def fokus_im(self, r, name, versuche=3):
            # am Rechteck gemessen: nur das Feld, das den Fokus hat, überlappt
            feld = {"contract": [1582, 92, 376, 28], "menge": [1567, 188, 470, 40]}.get(self.fokus)
            return bool(feld) and not (r[0] + r[2] <= feld[0] or feld[0] + feld[2] <= r[0] or r[1] + r[3] <= feld[1] or feld[1] + feld[3] <= r[1])

        def taste(self, k, modifiers=0):
            self.tasten.append(("Strg+" if modifiers == 2 else "") + k)
            if k == "a" and modifiers == 2:
                self.markiert = True
                if self.z.get("fokus_weg_nach_strg_a"):
                    self.fokus = None
            elif k == "Backspace" and self.fokus == "menge" and self.markiert:
                self.z["menge"], self.markiert = "", False
            elif k == "Escape" and not self.z.get("esc_wirkt_nicht"):
                self.z["offen"] = False

        def tippen(self, t):
            self.tasten.append("tippe " + t)
            if self.fokus == "contract":
                self.typed = t if self.markiert else self.typed + t
                self.markiert = False
            elif self.fokus == "menge" and not self.z.get("menge_klemmt"):
                self.z["menge"] = t if self.markiert else str(self.z["menge"]) + t
                self.markiert = False

    gew, ereignisse = [], []
    alt_w, alt_fm, alt_diag = ob._warte, ob.tsx_frontmonat, ob._puls_diagnose_senden

    def probe(zz, richtung="buy", menge=1, wurzel="MNQ"):
        k = _Karte(zz)
        out = {}
        res = {"balance": 0.0, "rpl": 0.0, "upl": 0.0}
        t = []

        def raus(code, msg, schritt, ok=False, **ex):
            out.update(code=code, msg=msg, schritt=schritt, ok=ok)
            return out
        ob._tsx_k3_probe(k, k.stand(), {"richtung": richtung, "menge": menge, "wurzel": wurzel, "ext": E, "scharf": False}, res, t, raus)
        return out, k, res, t
    try:
        ob._warte = lambda a, b: (gew.append((a, b)), ereignisse.append(("warte", (a, b))))
        ob.tsx_frontmonat = lambda jetzt=None: "Z26"
        ob._puls_diagnose_senden = lambda *a, **k: None
        o, k, res, t = probe(seite())
        chk(o["ok"] and o["schritt"] == "probe" and o["msg"].startswith("Ticket bereit (nicht gesendet): Buy +1 @ Market · MNQZ26 · Konto " + E),
            f"MNQ BUY 1 aus Menge 3 → Ticket bereit ({o})")
        chk(k.klicks == ["Contract-Feld", "Contract MNQZ26", "# of Contracts"], f"genau drei Klicks, kein Order-Knopf ({k.klicks})")
        chk(all(p_ and p_["tabu"] == ob.TSX_K0_TABU.pattern for p_ in k.pruef) and k.pruef[1]["text"] == "mnqz26"
            and k.pruef[1]["rect"] == V[0]["rect"], "jeder Druck mit Ziel-Beweis + Order-Tabu; Vorschlag: Klick im Code, Beweis gegen die Zeile")
        chk(k.tasten == ["Strg+a", "tippe mnq", "Strg+a", "Backspace", "tippe 1"] and "Tab" not in k.tasten and "Enter" not in k.tasten,
            f"Tastatur: Strg+A + Wurzel; Strg+A, Rücktaste, Menge — nie Tab/Enter ({k.tasten})")
        chk(res.get("tv_symbol") == "MNQZ26" and res.get("balance_start") == 0.0, "Contract + Start-Balance in der Antwort")
        chk(k.rects[1] == V[0]["code_rect"] and k.pruef[1].get("wort") == "mnqz26",
            "Vorschlag: Klick GENAU im Code-Text, Beweis verlangt den Code als ganzes Wort am Punkt (nqz26 ≠ mnqz26)")
        vor = [ereignisse[i - 1] for i, e_ in enumerate(ereignisse) if e_[0] == "klick" and i > 0]
        chk(vor[0] == ("warte", ob.TSX_SCHRITT_PAUSE) and vor[2] == ("warte", ob.TSX_SCHRITT_PAUSE) and vor[1] == ("warte", (0.6, 0.6)),
            f"Pause steht direkt VOR jedem Klick (Feld 1–2 s, Vorschlag 0,6–1,2 s, Menge 1–2 s) ({vor})")
        chk(sum(1 for g in gew if g == ob.TSX_SCHRITT_PAUSE) >= 3 and all(b_ > 0 for a_, b_ in gew),
            f"menschliche Pausen 1–2 s zwischen den Schritten, alle mit Streuung ({gew[:6]}…)")
        o, k, _, _ = probe(seite(contract="MNQZ26", menge="3"), richtung="sell", menge=15, wurzel="NQ")
        chk(o["ok"] and "Sell -15 @ Market · NQZ26" in o["msg"] and k.klicks[1] == "Contract NQZ26", f"NQ SELL 15 → NQZ26, Menge 15 ({o})")
        o, k, _, _ = probe(seite(menge="3"), menge=3)
        chk(o["ok"] and k.klicks == ["Contract-Feld", "Contract MNQZ26"], "Menge steht schon auf 3 → Feld nicht angefasst")
        o, k, _, _ = probe(seite(liste=V[:1]), wurzel="NQ", richtung="sell")
        chk(not o["ok"] and o["code"] == "contract" and "Contract MNQZ26" not in k.klicks and "Escape" in k.tasten
            and "# of Contracts" not in k.klicks and "MNQZ26" in o["msg"],
            f"NQ-Plan, „nq“ zeigt nur MNQZ26 (MUI „enthält“) → MNQZ26 NIE gewählt, Esc ({o})")
        o, k, _, _ = probe(seite(liste=[dict(V[0], code_rect=None)]))
        chk(not o["ok"] and o["code"] == "contract" and "Contract MNQZ26" not in k.klicks,
            "Vorschlag ohne Code-Text (code_rect fehlt) → nie die Zeilenmitte klicken (Stern), ehrlich raus")
        o, k, _, _ = probe(seite(kein_fokus=True))
        chk(not o["ok"] and o["code"] == "contract" and not any(t_.startswith("tippe") for t_ in k.tasten) and "Strg+a" not in k.tasten,
            f"Contract-Feld ohne Fokus → keine einzige Taste außer Esc ({k.tasten})")
        o, k, _, _ = probe(seite(fokus_weg_nach_strg_a=True))
        chk(not o["ok"] and o["code"] == "contract" and not any(t_.startswith("tippe") for t_ in k.tasten),
            "Fokus nach Strg+A verloren → nichts getippt")
        # 06.10.2026 (Finn live, Chris-PC): Feld zeigt den Code, Liste bleibt nach der Auswahl offen → EINMAL Esc; zu + Code = gewählt
        o, k, _, _ = probe(seite(liste_bleibt_offen=True))
        chk(o["ok"] and k.tasten.count("Escape") == 1 and "# of Contracts" in k.klicks and k.klicks.count("Contract-Feld") == 1,
            f"Wert steht, Liste bleibt offen → ein Esc, dann als gewählt gezählt, weiter zur Menge ({o.get('code')}: {str(o.get('msg'))[:60]})")
        o, k, _, _ = probe(seite(liste_bleibt_offen=True, esc_wirkt_nicht=True))
        chk(not o["ok"] and o["code"] == "contract" and "# of Contracts" not in k.klicks and "Escape" in k.tasten,
            "Liste bleibt auch nach Esc offen → nie als gewählt gezählt, Menge nie angefasst, ehrlich raus")
        o, k, _, _ = probe(seite(menge_klemmt=True))
        chk(not o["ok"] and o["code"] == "menge" and k.klicks.count("# of Contracts") == 2, "Menge wird nicht übernommen → zwei Versuche, dann ehrlich raus")
        o, k, _, _ = probe(seite(kauf_text="Buy +3 @ Market"))
        chk(not o["ok"] and o["code"] == "vorpruefung" and "Knopf zeigt 'Buy +3 @ Market'" in o["msg"],
            "Knopf zeigt noch die alte Menge → Probe nicht bereit (Knopftext unabhängig vom Feld geprüft)")
        o, k, _, _ = probe(seite(kauf_text="Market Closed"))
        chk(o["ok"] and "Markt zu" in o["msg"], "Markt zu (Knopf „Market Closed“) → Probe bis hierher bestanden, mit Hinweis")
        o, k, _, _ = probe(seite(knopf_gesperrt=True))
        chk(not o["ok"] and "gesperrt" in o["msg"], "Order-Knopf gesperrt → nicht bereit")
        # Start auf NQZ26 (06.10.2026): stünde die Karte schon auf MNQZ26, zeigte das Feld nach Esc den richtigen Code — das wäre kein Fehler
        o, k, _, _ = probe(seite(klick_wirkt=False, contract="NQZ26"))
        chk(not o["ok"] and o["code"] == "contract" and k.klicks.count("Contract-Feld") == 2 and "# of Contracts" not in k.klicks,
            "Vorschlag wirkt nicht (Feld bleibt NQZ26) → zweiter Versuch, dann ehrlich raus")
        o, k, _, _ = probe(seite(ordertyp="Limit"))
        chk(not o["ok"] and o["code"] == "ordertyp" and not k.klicks, "Order-Typ nicht Market → nichts angefasst")
        o, k, _, _ = probe(seite(alt=True))
        chk(not o["ok"] and o["code"] == "anker_fehlt" and not k.klicks, "alte augen_tsx.js ohne K3-Felder → nichts angefasst")
        o, k, _, _ = probe(seite(flach=False))
        chk(not o["ok"] and o["code"] == "vorpruefung" and "flach" in o["msg"], f"nicht flach → Probe sagt es ehrlich ({o})")
        o, k, _, _ = probe(seite(konto_ok=False))
        chk(not o["ok"] and o["code"] == "vorpruefung" and "Konto" in o["msg"], "falsches Konto im Blick vor dem Urteil → nicht bereit")
        vk = ob.tsx_k3_vor_klick
        bf = {"richtung": "buy", "menge": 1}
        s_ok = stand_aus(dict(seite(menge="1")), "", None)
        chk(vk(s_ok, bf, "MNQZ26", E)[0] and not vk(s_ok, bf, "NQZ26", E)[0], "Urteil: Contract muss genau der gewählte Code sein")
        # 06.10.2026: im Feld nur die getippte Wurzel — mit Chart-Titel auf dem Code bereit, ohne Titel / falscher Chart nicht
        s_wz = dict(s_ok, ticket=dict(s_ok["ticket"], contract=dict(s_ok["ticket"]["contract"], wert="mnq")))
        bfw = dict(bf, wurzel="MNQ")
        chk(vk(dict(s_wz, titel="MNQZ26 $31,516.00 ▲ +0.63%"), bfw, "MNQZ26", E)[0]
            and not vk(s_wz, bfw, "MNQZ26", E)[0] and not vk(dict(s_wz, titel="NQZ26 $31,500.00"), bfw, "MNQZ26", E)[0]
            and not vk(dict(s_wz, titel="MNQZ26 $31,516.00"), bf, "MNQZ26", E)[0],
            "Urteil: Wurzel im Feld + Chart-Titel = Code bereit; ohne Titel, Chart auf NQ oder ohne Wurzel im Befehl nicht")
        s_pop = dict(s_ok, popups=[{"titel": "Session disconnected"}])
        s_off = stand_aus(dict(seite(menge="1", contract="MNQZ26", offen=True)), "MNQZ26", None)
        chk(any("Dialog" in f_ for f_ in vk(s_pop, bf, "MNQZ26", E)[1]) and any("Liste noch offen" in f_ for f_ in vk(s_off, bf, "MNQZ26", E)[1])
            and not vk(dict(s_ok, ticket=dict(s_ok["ticket"], ordertyp={"text": "Limit"})), bf, "MNQZ26", E)[0]
            and not vk(dict(s_ok, ticket=dict(s_ok["ticket"], verkauf=None)), {"richtung": "sell", "menge": 1}, "MNQZ26", E)[0],
            "Urteil: Dialog, offene Contract-Liste, Order-Typ Limit, fehlender Knopf → nicht bereit")
    finally:
        ob._warte, ob.tsx_frontmonat, ob._puls_diagnose_senden = alt_w, alt_fm, alt_diag
    # nie ein Order-Knopf im K3a-Code (Quelltext-Riegel)
    q = "".join(_i.getsource(f) for f in (ob._tsx_k3_probe, ob._tsx_k3_ticket, ob._tsx_k3_contract, ob._tsx_k3_menge))
    chk(q.count("s.klick(") == 3 and q.count("TSX_K0_TABU.pattern") == 3 and "_puls_ergebnis_senden" not in q
        and not re.search(r"gesendet[\"']?\]?\s*[=:]\s*True|gesendet=True", q) and "kauf" not in q.replace("verkauf", ""),
        "K3a-Quelltext: genau drei Klicks (Feld, Vorschlag, Menge), alle mit Order-Tabu, nie gesendet=True, kein puls_ergebnis")

    # ── ganze Kette: modus_tsxlesen_cdp mit order (Chrome/Tab/Login nachgebildet) ─────────────────────────────────────────
    zz = seite(menge="3")
    karte = _Karte(zz)

    class _WsK:
        def rufe(self, m, par=None, timeout=10.0):
            return {}
    karte.ws, karte.lese_js, karte.zu, karte._win_vorn = _WsK(), (lambda a, timeout=8: None), (lambda: None), (lambda: (1, ""))
    timer = []

    class _Timer:
        def __init__(self, sek, f):
            timer.append(sek)
            self.daemon = False

        def start(self):
            pass

        def cancel(self):
            pass
    namen = ("_puls_chrome_sicher", "_tsx_sitzung_waehlen", "_handlauf_aktiv", "_handlauf_setzen", "_puls_diagnose_senden", "_warte",
             "_WIN_EINGABE", "tsx_frisch_urteil", "_tsx_bereit_warten", "tsx_frontmonat", "puls_bot_stand")
    alt_m = {n: getattr(ob, n) for n in namen}
    alt_timer = _th.Timer
    try:
        ob._puls_chrome_sicher = lambda trail, url=None: True
        ob._tsx_sitzung_waehlen = lambda trail, sitz=None: (sitz.__setitem__(0, karte) if sitz is not None else None, (karte, True))[1]
        ob._handlauf_aktiv = lambda: False
        ob._handlauf_setzen = lambda an: None
        ob._puls_diagnose_senden = lambda *a, **k: None
        ob._warte = lambda a, b: None
        ob._WIN_EINGABE = False
        ob.tsx_frisch_urteil = lambda v: (True, "frisch (Test)")
        ob._tsx_bereit_warten = lambda s_, trail, sek=None: (s_.stand(), True)
        ob.tsx_frontmonat = lambda jetzt=None: "Z26"
        ob.puls_bot_stand = lambda: "Bot-Stand (Test)"
        _th.Timer = _Timer
        o_ = io.StringIO()
        with contextlib.redirect_stdout(o_):
            ob.modus_tsxlesen_cdp({"konto": E}, order={"richtung": "buy", "menge": 1, "wurzel": "MNQ", "ext": E, "scharf": False}, order_cmd={})
        j = json.loads(o_.getvalue().strip().splitlines()[-1])
    finally:
        for n_, v_ in alt_m.items():
            setattr(ob, n_, v_)
        _th.Timer = alt_timer
    chk(j.get("ok") is True and j.get("gesendet") is False and j.get("retry_ok") is True and j.get("etappe") == "K3" and j.get("schritt") == "probe"
        and j.get("balance_start") == 0.0 and j.get("tv_symbol") == "MNQZ26" and j.get("konto_aktiv") == E and j.get("summary"),
        f"ganze Kette: Probe-Antwort im tsx-konto-Vertrag ({ {k_: j.get(k_) for k_ in ('ok', 'code', 'schritt', 'gesendet', 'retry_ok', 'etappe')} })")
    chk(timer == [ob.TSX_K3_WACHHUND_S] and ob.TSX_K3_WACHHUND_S < 170, "Wachhund der Probe unter der 170-s-Grenze des Panels")
    chk(karte.klicks == ["Contract-Feld", "Contract MNQZ26", "# of Contracts"], f"Kette klickt nur das Ticket ({karte.klicks})")

    # ── Hover-Pause an der echten Sitzungs-Klasse (Windows nachgebildet) ─────────────────────────────────────────────────
    alt = {n: getattr(ob, n) for n in ("_WIN_EINGABE", "_puls_fenster_liste", "_puls_chrome_browser_pid", "_win_vordergrund", "_win_minimiert",
                                       "_win_zeigen", "_win_nach_vorn", "_klient_rechteck", "_maus_fahren", "_klick_absolut", "_dpi_bewusst",
                                       "_warte", "_win_root_am_punkt")}
    zs = {"proben": 0, "passt": [True, True], "klicks": [], "warte": []}
    f1 = {"hwnd": 11, "text": "TopstepX - Google Chrome", "klasse": "Chrome_WidgetWin_1", "sichtbar": True}

    class _Ws2:
        def rufe(self, m, par=None, timeout=10.0):
            if m != "Runtime.evaluate":
                return {}
            a = (par or {}).get("expression", "")
            if a == ob.WIN_GEO_JS:
                return {"result": {"value": {"innerWidth": 2100, "innerHeight": 900, "dpr": 1, "titel": "TopstepX"}}}
            if "elementFromPoint" in a:
                i_ = min(zs["proben"], len(zs["passt"]) - 1)
                zs["proben"] += 1
                return {"result": {"value": {"hover": True, "passt": zs["passt"][i_], "was": "x"}}}
            return {"result": {"value": None}}
    try:
        ob._WIN_EINGABE = True
        ob._puls_fenster_liste = lambda pid: [f1]
        ob._puls_chrome_browser_pid = lambda: 4711
        ob._win_vordergrund = lambda: 11
        ob._win_minimiert = lambda h: False
        ob._win_zeigen = lambda h, b: None
        ob._win_nach_vorn = lambda h: None
        ob._klient_rechteck = lambda h: (0, 87, 2100, 900)          # TopstepX-Fenster breit (Order-Karte rechts bei x ≈ 1560–2040)
        ob._maus_fahren = lambda x, y, schritte=8: None
        ob._klick_absolut = lambda x, y, taste="links", doppel=False: (zs["klicks"].append((x, y)), True)[1]
        ob._dpi_bewusst = lambda: True
        ob._warte = lambda a, b: zs["warte"].append((a, b))
        ob._win_root_am_punkt = lambda x, y: (11, "TopstepX")
        s_ = ob._AugenSitzung.__new__(ob._AugenSitzung)
        s_.trail, s_.ws, s_.js, s_.maus, s_.target_id, s_.tv_riegel = [], _Ws2(), "/* augen_tsx.js */", (0.0, 0.0), "T", False
        s_.hover_pause = ob.TSX_HOVER_PAUSE
        pr = {"rect": [1582, 92, 376, 28], "text": "", "aria": "", "tabu": ob.TSX_K0_TABU.pattern}
        chk(s_.klick([1582, 92, 376, 28], "Contract-Feld", pruef=pr) is True and len(zs["klicks"]) == 1 and ob.TSX_HOVER_PAUSE in zs["warte"]
            and zs["proben"] == 2, f"TopstepX: Hover-Pause 0,3–0,8 s vor dem Druck, Ziel danach neu bewiesen ({zs['proben']} Proben)")
        zs.update(proben=0, passt=[True, False], warte=[])
        chk(s_.klick([1582, 92, 376, 28], "Contract-Feld", pruef=pr) is False and len(zs["klicks"]) == 1
            and "nach der Hover-Pause" in s_.trail[-1], "Ziel nach der Hover-Pause weg → KEIN Druck")
        zs.update(proben=0, passt=[True, True], warte=[])
        s_.hover_pause = None                                         # Orbit-Sitzung (augen.js): unverändert
        chk(s_.klick([1582, 92, 376, 28], "Knopf", pruef=pr) is True and ob.TSX_HOVER_PAUSE not in zs["warte"] and zs["proben"] == 1,
            "Orbit-Sitzung ohne hover_pause: keine Pause, eine Probe wie bisher")
    finally:
        for n_, v_ in alt.items():
            setattr(ob, n_, v_)
    q_k2 = _i.getsource(ob._tsx_konto_sichern)
    q_lg = _i.getsource(ob._tsx_cdp_login)
    vor_druck = re.compile(r"_tsx_pause\(\)[^\n]*\n\s*if not s\.klick\(")
    chk(len(vor_druck.findall(q_k2)) == 2 and len(vor_druck.findall(q_lg)) == 1 and ob.TSX_SCHRITT_PAUSE == (1.0, 1.0)
        and ob.TSX_HOVER_PAUSE == (0.3, 0.5), "K2 (Auslöser, Zeile) und Login: 1–2 s Pause vor dem Druck")
    chk("hover_pause = TSX_HOVER_PAUSE if js_datei == \"augen_tsx.js\"" in _i.getsource(ob._AugenSitzung.__init__),
        "Hover-Pause nur für die TopstepX-Sitzung (augen_tsx.js)")
    js = open(os.path.join(os.path.dirname(os.path.abspath(ob.__file__)), "augen_tsx.js"), encoding="utf-8").read()
    chk("var VERSION = 'tsx-0.6.1'" in js and "contract-selector-input-select-contract" in js and "order-card-input-field-contracts" in js
        and "order-card-click-button-buy" in js and "k3: true" in js
        and "filter(function (z) { return RX_CODE.test(z); })" in js    # DOM-Test 01.10.2026: vor dem Code steht „■" — nie nur Zeile 1
        and ".click(" not in js.split("function contractLesen")[1].split("function ticketLesen")[0],
        "augen_tsx.js (seit tsx-0.5.0): Contract/Menge/Knöpfe gelesen, nur lesend")
    if ok:
        print("✓ TSX-K3a: Contract per Tastatur + Vorschlag (MNQ ≠ NQ, Front-Monat), Menge ersetzen + Rücklesung, Probe ohne Order-Knopf, "
              "menschliche Pausen, Kette im tsx-konto-Vertrag")
    return ok


def test_tsx_k4():
    """K4 (05.10.2026, Finn: „Market buy bzw. sell … unten auf Position gehen, Doppelklicken auf Risk und da eine Zahl eingeben"):
    scharfer Order-Knopf genau einmal, gesendet/retry_ok vor dem Klick, Fill-Beweis, Risk / To Make über die Positions-Tabelle.
    Nachbau der TopstepX-Seite als Zustands-Attrappe; reine Regeln + echte Schritte. Kennungen erfunden."""
    import order_bot as ob
    import inspect as _i
    import os
    import re
    import time as _t
    ok = True

    def chk(bed, text):
        nonlocal ok
        if not bed:
            print("  ✗ TSX-K4: " + text)
            ok = False
    E = "EXPRESS-V2-000000-30000003"
    # ── reine Regeln ──────────────────────────────────────────────────────────
    B = ob.tsx_k4_betraege
    chk(B({"tp_usd": 198, "sl_usd": 21}) == (198.0, 21.0) and B({"tp_usd": "40,5"}) == (40.5, None) and B({"tp_usd": 0, "sl_usd": -3}) == (None, None)
        and B({"sl_usd": "x"}) == (None, None) and B(None) == (None, None), "Beträge: nur Zahlen > 0, sonst None (Winning Days ohne SL)")
    BT, WG = ob.tsx_k4_betrag_text, ob.tsx_k4_wert_gleich
    chk(BT(27) == "27" and BT(3456.0) == "3456" and BT(199.5) == "199.50" and WG("27", 27) and WG("199.50", 199.5) and WG("199,5", 199.5)
        and not WG("2127", 27) and not WG("", 27) and not WG("27a", 27) and not WG(None, 27), "Tipp-Text und Rücklesung des Eingabefelds")
    L, TOL = ob.tsx_k4_level, ob.tsx_k4_toleranz
    # Finns Bild 05.10.2026: −6 MNQ @ 31.339,50 · Risk 21 $ → SL 31.341,25 · To Make 198 $ → TP 31.323,00
    chk(L(31339.5, "sell", 21, "MNQ", 6, "sl") == 31341.25 and L(31339.5, "sell", 198, "MNQ", 6, "tp") == 31323.0
        and L(31000, "buy", 4000, "NQ", 2, "tp") == 31100.0 and L(31000, "buy", 2000, "NQ", 2, "sl") == 30950.0
        and L(31000, "buy", 10, "ES", 1, "tp") is None and L(None, "buy", 10, "MNQ", 1, "tp") is None,
        "Level aus Einstieg und Dollar der ganzen Position (MNQ 2 $/Pkt, NQ 20 $/Pkt), unbekannte Wurzel → None")
    chk(abs(TOL("MNQ", 6) - 3.01) < 1e-9 and abs(TOL("NQ", 2) - 10.01) < 1e-9, "Spiel der Rücklesung = ein Tick der ganzen Position")
    bf = {"richtung": "sell", "menge": 6, "wurzel": "MNQ", "ext": E, "scharf": True}
    fill = {"art": "fill", "status": "ausgefuehrt", "aktiv": True, "seite": "sell", "menge": 6, "symbol": "MNQZ26", "typ": "market",
            "preis": 31339.5, "erst_gesehen": 10_000}
    F, MS = ob.tsx_k4_fill, ob.tsx_k4_meldung_schluessel
    st_f = {"toasts": {"meldungen": [fill]}, "positionen": []}
    chk(F(st_f, bf, set(), 9_800) == (31339.5, "fill", "") and F(st_f, bf, MS(st_f), 9_800)[0] is None
        and F({"toasts": {"meldungen": [dict(fill, erst_gesehen=5_000)]}}, bf, set(), 9_800)[0] is None
        and F({"toasts": {"meldungen": [dict(fill, seite="buy")]}}, bf, set(), 9_800)[0] is None
        and F({"toasts": {"meldungen": [dict(fill, symbol="NQZ26")]}}, bf, set(), 9_800)[0] is None
        and F({"toasts": {"meldungen": [dict(fill, menge=3)]}}, bf, set(), 9_800)[0] is None,
        "Fill-Beweis nur mit NEUER Meldung (nicht im Vorher-Stand, nach dem Klick gesehen), Richtung, Wurzel (MNQ ≠ NQ) und Menge")
    pos = {"symbol": "MNQ", "seite": "sell", "menge": 6, "avg": 31339.5}
    chk(F({"positionen": [pos]}, bf, set(), 0) == (31339.5, "position", "") and F({"positionen": [dict(pos, menge=3)]}, bf, set(), 0)[0] is None
        and F({"positionen": [dict(pos, seite="buy")]}, bf, set(), 0)[0] is None and F({"positionen": [dict(pos, symbol="NQZ26")]}, bf, set(), 0)[0] is None
        and F({"positionen": [dict(pos, avg=None)]}, bf, set(), 0)[0] is None and F(None, bf, set(), 0) == (None, "", ""),
        "Positions-Beweis nur mit Wurzel, Richtung und GENAU der Plan-Menge (Teil-Fill zählt nicht)")
    abg = {"art": "order", "status": "abgelehnt", "aktiv": False, "seite": "sell", "menge": 6, "symbol": "MNQZ26", "typ": "market", "preis": None,
           "text": "Order Rejected | Market closed", "erst_gesehen": 10_000}
    chk(F({"toasts": {"meldungen": [abg]}}, bf, set(), 9_800)[2].startswith("Order Rejected")
        and F({"toasts": {"meldungen": [abg]}}, bf, MS({"toasts": {"meldungen": [abg]}}), 9_800) == (None, "", ""),
        "neue Ablehnung → abgelehnt_text; eine alte Ablehnung zählt nicht")
    bein = {"art": "stop", "status": "abgelehnt", "aktiv": False, "seite": "buy", "menge": 6, "symbol": "MNQZ26", "typ": "stop market", "preis": 31341.25,
            "text": "Order Rejected | +6 MNQZ26 Stop Market @ 31,341.25", "erst_gesehen": 10_000}
    chk(F({"toasts": {"meldungen": [bein, fill]}}, bf, set(), 9_800) == (31339.5, "fill", "")
        and F({"toasts": {"meldungen": [bein]}, "positionen": [pos]}, bf, set(), 9_800) == (31339.5, "position", "")
        and F({"toasts": {"meldungen": [abg]}, "positionen": [pos]}, bf, set(), 9_800) == (31339.5, "position", "")
        and F({"toasts": {"meldungen": [abg, fill]}}, bf, set(), 9_800) == (31339.5, "fill", "")
        and F({"toasts": {"meldungen": [bein]}}, bf, set(), 9_800) == (None, "", "")
        and F({"toasts": {"meldungen": [dict(abg, symbol="ESZ26")]}}, bf, set(), 9_800) == (None, "", "")
        and F({"toasts": {"meldungen": [dict(abg, seite="buy")]}}, bf, set(), 9_800) == (None, "", "")
        and F({"toasts": {"meldungen": [dict(abg, symbol=None, seite=None, typ=None)]}}, bf, set(), 9_800)[2].startswith("Order Rejected")
        and F({"toasts": {"meldungen": [dict(fill, typ="limit")]}}, bf, set(), 9_800)[0] is None,
        "Prüfer 06.10.2026: Beweis gewinnt — Bracket-Bein/fremde Ablehnung nie 'abgelehnt', nur die eigene Market-Order ohne Fill und Position")
    AB = ob.tsx_k4_ablehnungen
    chk(AB({"toasts": {"meldungen": [bein, fill, abg]}}, set(), 9_800) == [bein["text"], abg["text"]]
        and AB({"toasts": {"meldungen": [bein]}}, MS({"toasts": {"meldungen": [bein]}}), 9_800) == []
        and AB({"toasts": {"meldungen": [dict(bein, erst_gesehen=5_000)]}}, set(), 9_800) == [] and AB(None, set(), 0) == [],
        "Ablehnungen eines Blicks: nur neu + frisch — Warnung neben dem Fill")
    alt_fill = dict(fill, erst_gesehen=5_000)
    st_vor, st_nach = {"toasts": {"meldungen": [alt_fill]}}, {"toasts": {"meldungen": [alt_fill, dict(alt_fill)]}}
    chk(F(st_nach, bf, MS(st_vor), 9_800) == (31339.5, "fill", "") and F(st_vor, bf, MS(st_vor), 9_800)[0] is None
        and MS(st_nach) == {ob._tsx_k4_key(fill): 2} and AB({"toasts": {"meldungen": [dict(abg, erst_gesehen=5_000)] * 2}}, MS({"toasts": {"meldungen": [dict(abg, erst_gesehen=5_000)]}}), 9_800) == [abg["text"]],
        "Nachprüfer 06.10.2026: alter gleich lautender Toast bleibt stehen → der zweite Knoten zählt über die gewachsene Anzahl als neu")

    def gitter(zeilen, da=True):
        return {"ticket": {"k4": True, "gitter": {"da": da, "zeilen": zeilen, "grund": None if da else "keine Tabelle"}}}
    Z = ob.tsx_k4_zeile
    z6 = {"symbol": "MNQ", "menge": -6}
    chk(Z(gitter([z6]), bf)[0] is z6 and Z(gitter([dict(z6, menge=6)]), bf)[0] is None and Z(gitter([z6, dict(z6)]), bf)[0] is None
        and Z(gitter([dict(z6, symbol="NQ")]), bf)[0] is None and Z(gitter([], da=False), bf) == (None, "keine Tabelle") and Z({}, bf)[0] is None,
        "Plan-Zeile: genau eine mit Wurzel, Vorzeichen und Menge — sonst keine")
    chk(re.search(ob.TSX_K4_TABU, "close position") and re.search(ob.TSX_K4_TABU, "flatten all") and re.search(ob.TSX_K4_TABU, "reverse position")
        and re.search(ob.TSX_K4_TABU, "cancel orders") and re.search(ob.TSX_K4_TABU, "join bid")
        and not re.search(ob.TSX_K4_TABU, "sell -6 @ market") and not re.search(ob.TSX_K4_TABU, "buy +3 @ market")
        and not re.search(ob.TSX_K4_TABU, "positions") and not re.search(ob.TSX_K4_TABU, "$21.00"),
        "K4-Tabu: alles, was schließt/dreht/storniert — der Order-Knopf, der Reiter und die Zellen selbst nicht")

    # ── nachgebildete Seite ───────────────────────────────────────────────────
    RK, RV, RT = [1640, 416, 120, 26], [1766, 416, 120, 26], [156, 746, 69, 28]
    RR, RM, RC = [1000, 766, 200, 22], [1300, 766, 200, 22], [1850, 766, 60, 22]

    class _T4:
        def __init__(self, richtung="sell", menge=6, avg=31339.5, **kw):
            self.o = dict(fill_nach=1, fill_toast=True, abgelehnt=False, order_druck=True, reiter=False, risk=None, to_make=None, edit_geht=True,
                          strg_a=True, tipp_extra="", enter_wirkt=True, flach_ohne_pos=True, markt_zu=False, popup_nach_enter=False, edit_fokus=True,
                          wirft_nach_klick=False, tippen_wirft=False, tasten_wirken=True, k4=True, reiter_da=True, bein_abgelehnt=False, zeile_nach=0, klick_wirft="",
                          abl_ohne_zeile=False)
            self.o.update(kw)
            self.richtung, self.menge, self.avg = richtung, menge, avg
            self.pos, self.lesungen, self.t_klick, self.reiter = False, None, 0, self.o["reiter"]
            self.n_reiter = 0
            self.werte = {"risk": self.o["risk"], "to_make": self.o["to_make"]}
            self.edit, self.eingabe, self.markiert, self.popup = None, "", False, False
            self.klicks, self.pruef, self.tasten = [], [], []

        def _feld(self, name, rect):
            if self.edit == name:
                return {"text": "", "wert": None, "rect": rect, "zu": {"disabled": False, "verdeckt": False},
                        "edit": {"offen": True, "wert": self.eingabe, "rect": rect, "fokus": bool(self.o["edit_fokus"]), "typ": "number"}}
            w = self.werte[name]
            return {"text": "" if w is None else f"${w:,.2f}", "wert": w, "rect": rect, "zu": {"disabled": False, "verdeckt": False}, "edit": {"offen": False}}

        def stand(self, opts=None):
            if self.lesungen is not None:
                self.lesungen += 1
                if self.o["wirft_nach_klick"]:
                    raise RuntimeError("CDP weg")
                if self.o["fill_nach"] and self.lesungen >= self.o["fill_nach"] and not self.o["abgelehnt"]:
                    self.pos = True
            if self.reiter:
                self.n_reiter += 1
            n = self.menge
            meld = []
            if self.pos and self.o["fill_toast"]:
                meld.append({"art": "fill", "status": "ausgefuehrt", "aktiv": True, "seite": self.richtung, "menge": n, "symbol": "MNQZ26",
                             "typ": "market", "preis": self.avg, "erst_gesehen": self.t_klick + 300})
            if self.o["abl_ohne_zeile"] and self.lesungen:
                meld.insert(0, {"art": "order", "status": "abgelehnt", "aktiv": False, "seite": None, "menge": None, "symbol": None, "typ": None,
                                "preis": None, "text": "Order Rejected | Price: 31,341.25", "erst_gesehen": self.t_klick + 250})
            if self.pos and self.o["bein_abgelehnt"]:
                meld.insert(0, {"art": "stop", "status": "abgelehnt", "aktiv": False, "seite": "buy" if self.richtung == "sell" else "sell", "menge": n,
                                "symbol": "MNQZ26", "typ": "stop market", "preis": 31341.25, "text": "Order Rejected | Stop Market @ 31,341.25",
                                "erst_gesehen": self.t_klick + 320})
            if self.o["abgelehnt"] and self.lesungen:
                meld.append({"art": "order", "status": "abgelehnt", "aktiv": False, "seite": self.richtung, "menge": n, "symbol": "MNQZ26",
                             "typ": "market", "preis": None, "text": "Order Rejected | Not allowed", "erst_gesehen": self.t_klick + 300})
            zeile = {"symbol": "MNQ", "menge": -n if self.richtung == "sell" else n, "seite": self.richtung, "avg": self.avg, "pl_text": "$0.00",
                     "risk": self._feld("risk", RR), "to_make": self._feld("to_make", RM), "close_rect": RC, "rect": [69, 766, 1930, 22]}
            kt = "MARKET CLOSED" if self.o["markt_zu"] else None
            return {"v": "tsx-0.6.0",
                    "konto": {"aktiv": f"$150K Express|{E}", "kontonr": E, "abgekuerzt": False, "liste_offen": False, "liste": []},
                    "kopf": {"balance": {"text": "$19.08", "wert": 19.08}, "mll": {"text": "$-4,500.00", "wert": -4500.0},
                             "rpl": {"text": "$-4.92", "wert": -4.92}, "upl": {"text": "$24.00", "wert": 24.0}, "balance_relativ": True},
                    "positionen": [{"symbol": "MNQZ26", "seite": self.richtung, "menge": n, "avg": self.avg, "pl_text": None}] if self.pos else [],
                    "positionen_sichtbar": True, "flach": False if self.pos else (True if self.o["flach_ohne_pos"] else None),
                    "popups": [{"titel": "Confirm Order", "text": "Confirm Order"}] if self.popup else [],
                    "toasts": {"gruppen": [], "meldungen": meld},
                    "ticket": {"k3": True, "k4": bool(self.o["k4"]), "ordertyp": {"text": "Market"},
                               "contract": {"wert": "MNQZ26", "offen": False, "fokus": False, "rect": [1582, 92, 376, 28], "zu": {}},
                               "menge": {"wert": str(n), "rect": [1567, 188, 470, 40], "fokus": False, "zu": {}}, "vorschlaege": [],
                               "kauf": {"text": kt or f"BUY +{n} @ MARKET", "rect": RK, "zu": {"disabled": False, "verdeckt": False}},
                               "verkauf": {"text": kt or f"SELL -{n} @ MARKET", "rect": RV, "zu": {"disabled": False, "verdeckt": False}},
                               "reiter": ({"positions": {"rect": RT, "aktiv": self.reiter, "text": "Positions", "zu": {"disabled": False, "verdeckt": False}}}
                                          if self.o["reiter_da"] else {}),
                               "gitter": {"da": bool(self.reiter and self.o["reiter_da"]), "spalten": ["symbol", "position", "entry price", "risk", "to make", "close"],
                                          "zeilen": [zeile] if (self.pos and self.reiter and self.n_reiter > self.o["zeile_nach"]) else [],
                                          "grund": None if self.reiter else "keine Tabelle mit den Spalten Risk und To Make im Bild"}}}

        def klick(self, r, name, toast_ok=False, pruef=None, doppel=False):
            self.klicks.append((name, bool(doppel), [float(x) for x in r]))
            self.pruef.append(pruef)
            if name.startswith("ORDER-Knopf"):
                if self.o["klick_wirft"] == "vor":
                    raise RuntimeError("CDP riss vor dem Druck")
                if self.o["klick_wirft"] == "nach":
                    self._druck_versucht = True
                    raise RuntimeError("CDP riss nach dem Druck")
                if not self.o["order_druck"]:
                    return False
                self.lesungen, self.t_klick = 0, int(_t.time() * 1000)
            elif name == "Reiter Positions":
                self.reiter = True
            elif name.startswith("Risk-Zelle") or name.startswith("To Make-Zelle"):
                feld = "risk" if name.startswith("Risk") else "to_make"
                if doppel and self.o["edit_geht"] and self.o["edit_geht"] != ("nur_" + ("to_make" if feld == "risk" else "risk")):
                    w = self.werte[feld]
                    self.edit, self.eingabe, self.markiert = feld, ("" if w is None else str(int(w))), False
            else:
                raise AssertionError("unerwarteter Klick " + name)
            return True

        def taste(self, k, modifiers=0):
            if not self.o["tasten_wirken"]:
                raise RuntimeError("Tastatur: Puls-Chrome nicht vorn")
            self.tasten.append(("Strg+" if modifiers == 2 else "") + k)
            if k == "a" and modifiers == 2:
                self.markiert = bool(self.o["strg_a"])
            elif k == "Backspace" and self.edit:
                self.eingabe, self.markiert = ("" if self.markiert else self.eingabe[:-1]), False
            elif k == "Escape":
                self.edit, self.eingabe = None, ""
            elif k == "Enter" and self.edit:
                if self.o["popup_nach_enter"]:
                    self.popup = True
                elif self.o["enter_wirkt"]:
                    tw = 0.5 * self.menge                      # MNQ: ein Tick der ganzen Position in $
                    self.werte[self.edit] = round(round(float(self.eingabe) / tw) * tw, 2)
                self.edit, self.eingabe = None, ""

        def tippen(self, t):
            if self.o["tippen_wirft"]:
                raise RuntimeError("Tastatur: Puls-Chrome nicht vorn")
            self.tasten.append("tippe " + t)
            if self.edit:
                self.eingabe = (t if self.markiert else self.eingabe + t) + self.o["tipp_extra"]
                self.markiert = False

        def lese_js(self, a, timeout=8):
            return None

    gesendet_log = []
    alt = {n: getattr(ob, n) for n in ("_warte", "_puls_diagnose_senden", "_puls_ergebnis_senden", "TSX_K4_BEWEIS_S", "_tsx_k3_ticket")}

    def lauf(seite, tp=198, sl=21, richtung="sell", menge=6, spur_alt=0.0, ueber_probe=False, scharf=True):
        res = {"ok": False, "code": "", "msg": "", "schritt": "lesen", "etappe": "K3", "gesendet": False, "retry_ok": True, "scharf": False,
               "balance": 19.08, "mll": -4500.0, "rpl": -4.92, "upl": 0.0}
        t = ob._StempelSpur()
        t._t0 -= spur_alt
        befehl = {"richtung": richtung, "menge": menge, "wurzel": "MNQ", "ext": E, "scharf": scharf, "plan_id": "p-1"}
        cmd = {"ext_id": E, "symbol": "MNQ", "richtung": richtung, "volumen": menge, "tp_usd": tp, "sl_usd": sl, "plan_id": "p-1", "scharf": scharf}

        def raus(code, msg, schritt, ok=False, **ex):
            res.update(ok=ok, code=code, msg=msg, schritt=schritt, **ex)
            return res
        st0 = seite.stand()
        if ueber_probe:
            ob._tsx_k3_probe(seite, st0, befehl, res, t, raus, cmd)
        else:
            _ok, _f, kn, _mz = ob.tsx_k3_vor_klick(st0, befehl, "MNQZ26", E)
            ob._tsx_k4_senden(seite, st0, befehl, "MNQZ26", kn, res, t, raus, cmd)
        return res, list(t)
    try:
        ob._warte = lambda a, b: None
        ob._puls_diagnose_senden = lambda *a, **k: None
        ob._puls_ergebnis_senden = lambda art, stufe, cmd, res, trail: gesendet_log.append((art, stufe, cmd.get("plan_id"), res.get("gesendet"), res.get("ok")))
        ob._tsx_k3_ticket = lambda s_, st_, b_, t_: (True, "", "", st_, "MNQZ26")
        # 1) der ganze Weg (Finns Bild: Sell 6 MNQ, Risk 21 $, To Make 198 $)
        s1 = _T4()
        r1, t1 = lauf(s1)
        namen = [k[0] for k in s1.klicks]
        chk(r1["ok"] is True and r1["schritt"] == "fertig" and r1["gesendet"] is True and r1["retry_ok"] is False and r1["etappe"] == "K4"
            and r1["einstieg"] == 31339.5 and r1["einstieg_quelle"] == "fill" and r1["sl_level"] == 31341.25 and r1["tp_level"] == 31323.0
            and r1["sl_level_quelle"] == r1["tp_level_quelle"] == "tsx_rechnung" and "warnung" not in r1 and r1["klick_at"].endswith("Z")
            and isinstance(r1["order_klick_ms"], int) and r1["positionen"] and r1["rpl"] == -4.92 and r1["upl"] == 0.0,
            f"ganzer Weg: gesendet, Einstieg aus der Fill-Meldung, SL/TP-Level wie in Finns Bild, Start-Werte von VOR dem Klick ({r1})")
        chk(namen == ["ORDER-Knopf 'SELL -6 @ MARKET'", "Reiter Positions", "Risk-Zelle (Doppelklick)", "To Make-Zelle (Doppelklick)"]
            and [k[1] for k in s1.klicks] == [False, False, True, True], f"genau vier Klicks: Order einmal, Reiter, zwei Doppelklicks ({namen})")
        chk(s1.pruef[0]["text"] == "sell -6 @ market" and s1.pruef[0]["rect"] == RV and all(p and p.get("tabu") == ob.TSX_K4_TABU for p in s1.pruef)
            and s1.pruef[2]["rect"] == RR and s1.pruef[3]["rect"] == RM, "jeder Klick mit Ziel-Beweis: exakter Knopftext, Zellen-Rechteck, K4-Tabu")
        zr, zm = s1.klicks[2][2], s1.klicks[3][2]
        chk(zr[0] >= RR[0] and zr[0] + zr[2] <= RR[0] + RR[2] * 0.5 and zm[0] + zm[2] <= RM[0] + RM[2] * 0.5
            and all(k[2][0] + k[2][2] < RC[0] for k in s1.klicks[1:]), "Doppelklick ins LINKE Stück der Zelle — nie der Stift, nie die Close-Spalte")
        chk(s1.tasten == ["Strg+a", "Backspace", "tippe 21", "Enter", "Strg+a", "Backspace", "tippe 198", "Enter"] and s1.werte == {"risk": 21.0, "to_make": 198.0},
            f"je Zelle: alles markieren, löschen, Betrag tippen, Enter ({s1.tasten})")
        chk([g[:2] for g in gesendet_log] == [("order", "geklickt"), ("order", "ende")] and gesendet_log[0][2] == "p-1" and gesendet_log[0][3] is True
            and gesendet_log[1][4] is True, f"Ergebnis-Meldung: geklickt sofort nach dem Druck, ende am Schluss ({gesendet_log})")
        # 2) Kauf, Beweis über die Positionszeile, Reiter schon offen
        s2 = _T4(richtung="buy", menge=3, avg=31000.0, fill_toast=False, reiter=True)
        r2, _ = lauf(s2, tp=60, sl=30, richtung="buy", menge=3)
        chk(r2["ok"] and r2["einstieg_quelle"] == "position" and r2["tp_level"] == 31010.0 and r2["sl_level"] == 30995.0
            and [k[0] for k in s2.klicks] == ["ORDER-Knopf 'BUY +3 @ MARKET'", "Risk-Zelle (Doppelklick)", "To Make-Zelle (Doppelklick)"],
            f"Kauf: Beweis über die Positionszeile, Reiter schon offen → kein Reiter-Klick ({r2.get('msg')})")
        # 3) Winning Day: nur To Make, Risk wird nie angefasst
        s3 = _T4()
        r3, _ = lauf(s3, tp=198, sl=None)
        chk(r3["ok"] and "sl_level" not in r3 and r3["tp_level"] == 31323.0 and not any("Risk" in k[0] for k in s3.klicks) and "warnung" not in r3,
            "Winning Day (kein SL): nur To Make, die Risk-Zelle bleibt unberührt")
        s3b = _T4(risk=45.0)
        r3b, _ = lauf(s3b, tp=198, sl=None)
        chk(r3b["ok"] and "Risk steht auf 45 $" in r3b.get("warnung", "") and not any("Risk" in k[0] for k in s3b.klicks),
            "Plan ohne SL, TopstepX hat selbst einen gesetzt → Hinweis, nichts überschrieben")
        s3c = _T4()
        r3c, _ = lauf(s3c, tp=None, sl=None)
        chk(r3c["ok"] and [k[0] for k in s3c.klicks] == ["ORDER-Knopf 'SELL -6 @ MARKET'"] and "tp_level" not in r3c, "ohne TP und SL: nur die Order")
        # 4) Knopf nicht gedrückt → nachweislich nichts gesendet
        s4 = _T4(order_druck=False)
        r4, _ = lauf(s4)
        chk(r4["code"] == "knopf" and r4["gesendet"] is False and r4["retry_ok"] is True and len(s4.klicks) == 1, f"Order-Knopf ohne Druck: gesendet false, retry ok ({r4})")
        # 5) kein Beweis / Ablehnung
        ob.TSX_K4_BEWEIS_S = 0.05
        s5 = _T4(fill_nach=0, flach_ohne_pos=False)
        r5, _ = lauf(s5)
        s5b = _T4(fill_nach=0)
        r5b, _ = lauf(s5b)
        s5c = _T4(abgelehnt=True)
        r5c, _ = lauf(s5c)
        ob.TSX_K4_BEWEIS_S = alt["TSX_K4_BEWEIS_S"]
        chk(r5["code"] == "beweis" and r5["unklar"] is True and r5["gesendet"] is True and r5["retry_ok"] is False and len(s5.klicks) == 1
            and "NICHT erneut starten" in r5["msg"], f"kein Beweis, flach nicht bewiesen → UNKLAR, kein zweiter Klick ({r5['msg']})")
        chk(r5b["code"] == "beweis" and r5b["unklar"] is False and r5b["gesendet"] is True and len(s5b.klicks) == 1,
            "kein Beweis, aber „No Active Position“ steht → beweis ohne unklar")
        chk(r5c["code"] == "abgelehnt" and "Order Rejected" in r5c.get("abgelehnt_text", "") and len(s5c.klicks) == 1, "Ablehnung → code abgelehnt, nichts weiter")
        # 6) Brackets scheitern NACH dem Fill → Order steht, ok + warnung
        s6 = _T4(edit_geht=False)
        r6, _ = lauf(s6)
        chk(r6["ok"] is True and r6["gesendet"] is True and "Risk 21 $ nicht gesetzt" in r6["warnung"] and "To Make 198 $ nicht gesetzt" in r6["warnung"]
            and "sl_level" not in r6 and r6["einstieg"] == 31339.5 and sum(1 for k in s6.klicks if k[0].startswith("ORDER")) == 1
            and sum(1 for k in s6.klicks if k[0].startswith("Risk")) == 2,
            f"Eingabefeld geht nicht auf: je Zelle zwei Versuche, dann Warnung „Brackets prüfen“ — die Order bleibt bewiesen ({r6.get('warnung')})")
        s6b = _T4(tipp_extra="9")
        r6b, _ = lauf(s6b)
        chk(r6b["ok"] and "nicht gesetzt" in r6b["warnung"] and s6b.werte == {"risk": None, "to_make": None} and "Enter" not in s6b.tasten
            and s6b.tasten.count("Escape") == 4, f"falscher Wert im Feld: nie Enter, Esc, Warnung ({s6b.tasten})")
        s6c = _T4(enter_wirkt=False)
        r6c, _ = lauf(s6c)
        chk(r6c["ok"] and "nach Enter" in r6c["warnung"] and "sl_level" not in r6c, "Enter ohne Wirkung → Rücklesung scheitert, Warnung")
        s6d = _T4(popup_nach_enter=True)
        r6d, _ = lauf(s6d)
        chk(r6d["ok"] and "fragt nach dem Eintragen" in r6d["warnung"] and "To Make 198 $ nicht gesetzt (Dialog offen)" in r6d["warnung"]
            and not any(k[0].startswith("To Make") for k in s6d.klicks) and s6d.tasten.count("Enter") == 1,
            f"Dialog nach Enter: nichts bestätigt, unter dem Dialog nichts mehr angeklickt ({r6d.get('warnung')})")
        s6e = _T4(edit_fokus=False)
        r6e, _ = lauf(s6e)
        chk(r6e["ok"] and "kein Eingabefeld mit Fokus" in r6e["warnung"] and not any(x.startswith("tippe") for x in s6e.tasten),
            "Eingabefeld ohne Fokus: nie getippt")
        # 7) Sonderfälle der Zelle
        s7 = _T4(risk=21.0, to_make=198.0)
        r7, t7 = lauf(s7)
        chk(r7["ok"] and len(s7.klicks) == 2 and not s7.tasten and r7["sl_level"] == 31341.25 and any("steht schon" in x for x in t7),
            "Werte stehen schon (TopstepX-Bracket = Plan): kein Doppelklick, Level trotzdem gemeldet")
        s7b = _T4(risk=45.0, strg_a=False)
        r7b, _ = lauf(s7b, tp=None, sl=21)
        chk(r7b["ok"] and s7b.werte["risk"] == 21.0 and s7b.tasten.count("Backspace") >= 3 and "tippe 21" in s7b.tasten,
            f"alter Wert, Strg+A greift nicht → Zeichen für Zeichen gelöscht, dann getippt ({s7b.tasten})")
        s7c = _T4()
        r7c, _ = lauf(s7c, tp=200, sl=20)                 # 6 MNQ: ein Tick = 3 $ → TopstepX rundet 200 → 201, 20 → 21
        chk(r7c["ok"] and s7c.werte == {"risk": 21.0, "to_make": 201.0} and r7c["tp_usd_ist"] == 201.0 and r7c["sl_usd_ist"] == 21.0
            and r7c["tp_level"] == 31322.75 and "warnung" not in r7c, f"TopstepX rundet auf Ticks: Rücklesung mit einem Tick Spiel, gemeldet wird der Ist-Wert ({r7c.get('msg')})")
        # 8) Riegel vor dem Klick
        s8 = _T4()
        r8, _ = lauf(s8, spur_alt=ob.TSX_K3_WACHHUND_S - ob.TSX_K4_REST_S + 5)
        chk(r8["code"] == "zeit" and r8["gesendet"] is False and r8["retry_ok"] is True and not s8.klicks, f"zu wenig Restzeit: nichts gesendet ({r8['msg']})")
        s8b = _T4(markt_zu=True)
        r8b, _ = lauf(s8b, ueber_probe=True)
        chk(r8b["code"] == "markt_zu" and not s8b.klicks and r8b["gesendet"] is False, f"Markt zu: Knopf trägt nicht Buy/Sell → nie gedrückt ({r8b['msg']})")
        s8c = _T4()
        r8c, _ = lauf(s8c, ueber_probe=True, scharf=False)
        chk(r8c["ok"] and r8c["schritt"] == "probe" and not s8c.klicks and r8c["gesendet"] is False, "Probe (scharf false) bleibt Probe: kein Order-Klick")
        s8d = _T4()
        r8d, _ = lauf(s8d, ueber_probe=True)
        chk(r8d["ok"] and r8d["schritt"] == "fertig" and r8d["gesendet"] is True, "scharf über die Probe → K4")
        alt_k4 = ob.TSX_K4_AKTIV
        ob.TSX_K4_AKTIV = False
        s8e = _T4()
        r8e, _ = lauf(s8e, ueber_probe=True)
        ob.TSX_K4_AKTIV = alt_k4
        chk(r8e["schritt"] == "probe" and not s8e.klicks, "Notschalter TSX_K4_AKTIV aus: auch scharf endet als Probe")
        # 9) Prüfer 06.10.2026
        ob.TSX_K4_BEWEIS_S = 0.05
        s9 = _T4(wirft_nach_klick=True)
        r9, _ = lauf(s9)
        ob.TSX_K4_BEWEIS_S = alt["TSX_K4_BEWEIS_S"]
        chk(r9["code"] == "beweis" and r9["unklar"] is True and r9["gesendet"] is True and r9["retry_ok"] is False and len(s9.klicks) == 1
            and "NICHT erneut starten" in r9["msg"], f"nach dem Klick keine Lesung gelungen → UNKLAR, nie „No Active Position“ aus dem alten Blick ({r9['msg']})")
        s9b = _T4(tippen_wirft=True)
        r9b, _ = lauf(s9b)
        chk(r9b["ok"] is True and r9b["gesendet"] is True and "Risk 21 $ nicht gesetzt (abgebrochen: RuntimeError" in r9b["warnung"]
            and "To Make 198 $ nicht gesetzt (abgebrochen" in r9b["warnung"] and s9b.tasten.count("Escape") == 2 and gesendet_log[-1][1] == "ende"
            and any(k[0].startswith("To Make") for k in s9b.klicks) and "tp_level" not in r9b and r9b["code"] == "" and r9b["einstieg"] == 31339.5,
            f"Ausnahme in der Zelle NACH dem Fill → ok + Warnung statt cdp_fehler, Esc je Feld, zweite Zelle noch versucht, 'ende' gesendet ({r9b.get('warnung')})")
        s9c = _T4(tippen_wirft=True, tasten_wirken=False)
        r9c, _ = lauf(s9c)
        chk(r9c["ok"] is True and "nicht mehr versucht" in r9c["warnung"] and not any(k[0].startswith("To Make") for k in s9c.klicks) and "sl_level" not in r9c,
            f"Esc wirkt nicht (Feld könnte offen sein) → keine zweite Zelle ({r9c.get('warnung')})")
        s9d = _T4(k4=False)
        r9d, _ = lauf(s9d)
        chk(r9d["code"] == "anker_fehlt" and not s9d.klicks and r9d["gesendet"] is False and r9d["retry_ok"] is True, f"alte Augen ohne K4-Vertrag → kein Klick ({r9d['msg']})")
        s9e = _T4(reiter_da=False)
        r9e, _ = lauf(s9e)
        chk(r9e["code"] == "anker_fehlt" and not s9e.klicks and r9e["gesendet"] is False, "Reiter Positions nicht gefunden + TP/SL → kein Klick")
        s9f = _T4(reiter_da=False)
        r9f, _ = lauf(s9f, tp=None, sl=None)
        chk(r9f["ok"] and len(s9f.klicks) == 1, "ohne TP/SL braucht es den Reiter nicht")
        s9g = _T4(bein_abgelehnt=True)
        r9g, _ = lauf(s9g)
        chk(r9g["ok"] is True and "TopstepX hat eine Order abgelehnt: Order Rejected | Stop Market" in r9g["warnung"] and r9g["einstieg"] == 31339.5
            and s9g.werte == {"risk": 21.0, "to_make": 198.0} and r9g["code"] == "", f"abgelehntes Bracket-Bein neben dem Fill → Order bewiesen, Warnung, Zellen gesetzt ({r9g.get('warnung')})")
        s9h = _T4(zeile_nach=3)
        r9h, _ = lauf(s9h)
        chk(r9h["ok"] and "warnung" not in r9h and s9h.werte == {"risk": 21.0, "to_make": 198.0}, f"Positions-Zeile erscheint erst nach ein paar Lesungen → abgewartet ({r9h.get('warnung')})")
        s9i = _T4(risk=0.0)
        r9i, _ = lauf(s9i, tp=None, sl=2)
        chk(r9i["ok"] and any(k[0].startswith("Risk") for k in s9i.klicks) and s9i.werte["risk"] == 3.0, f"0 $ in der Zelle zählt nie als „steht schon“ ({s9i.werte})")
        s9j = _T4(klick_wirft="vor")
        r9j, _ = lauf(s9j)
        chk(r9j["code"] == "knopf" and r9j["gesendet"] is False and r9j["retry_ok"] is True and "vor dem Druck" in r9j["msg"], f"Ausnahme VOR dem Druck → nichts gesendet ({r9j['msg']})")
        s9k = _T4(klick_wirft="nach")
        try:
            lauf(s9k)
            wirft = False
        except RuntimeError:
            wirft = True
        chk(wirft, "Ausnahme NACH dem Druck-Merker → bleibt Absturz (gesendet true, retry_ok false)")
        s9m = _T4(abl_ohne_zeile=True, fill_nach=2)
        r9m, _ = lauf(s9m)
        chk(r9m["ok"] is True and r9m["code"] == "" and r9m["einstieg"] == 31339.5 and "TopstepX hat eine Order abgelehnt: Order Rejected | Price" in r9m["warnung"]
            and s9m.werte == {"risk": 21.0, "to_make": 198.0}, f"Ablehnung ohne Order-Zeile im ersten Blick, Fill im zweiten → Fill gewinnt, Ablehnung nur Warnung ({r9m.get('warnung')})")
        ob.TSX_K4_BEWEIS_S = 0.05
        s9n = _T4(abl_ohne_zeile=True, fill_nach=0, flach_ohne_pos=False)
        r9n, _ = lauf(s9n)
        ob.TSX_K4_BEWEIS_S = alt["TSX_K4_BEWEIS_S"]
        chk(r9n["code"] == "abgelehnt" and "Price" in r9n.get("abgelehnt_text", "") and len(s9n.klicks) == 1, f"Ablehnung ohne Order-Zeile und nie ein Fill → am Ende abgelehnt ({r9n['code']})")
        s9l = _T4()
        st_l = s9l.stand()
        st_l["positionen"] = [{"symbol": "NQZ26", "seite": "buy", "menge": 1, "avg": 31000.0}]
        ok_l, f_l, _k, _m = ob.tsx_k3_vor_klick(st_l, bf, "MNQZ26", E)
        chk(not ok_l and any("offene Position gelesen" in x for x in f_l), f"Vor-Klick: gelesene Position in einem anderen Contract → keine Order ({f_l})")
        st_0 = s9l.stand()
        st_0["ticket"]["gitter"] = {"da": True, "zeilen": [{"symbol": "MNQZ26", "menge": 0, "seite": None}], "grund": None}
        ok_0, f_0, _k, _m = ob.tsx_k3_vor_klick(st_0, bf, "MNQZ26", E)
        st_1 = s9l.stand()
        st_1["ticket"]["gitter"] = {"da": True, "zeilen": [{"symbol": "NQZ26", "menge": 1, "seite": "buy"}], "grund": None}
        chk(ok_0 and not ob.tsx_k3_vor_klick(st_1, bf, "MNQZ26", E)[0], f"Vor-Klick: 0-Zeile der Tabelle ist keine Position, Zeile mit Menge ≠ 0 in anderem Contract schon ({f_0})")
    finally:
        for n, v in alt.items():
            setattr(ob, n, v)
    # ── Quelltext-Riegel ──────────────────────────────────────────────────────
    q4 = _i.getsource(ob._tsx_k4_senden)
    chk(q4.count("s.klick(") == 1 and q4.index("res.update(gesendet=True, retry_ok=False)") < q4.index("s.klick(")
        and q4.index("s.klick(") < q4.index("res.update(gesendet=False, retry_ok=True)") < q4.index('_puls_ergebnis_senden("order", "geklickt"'),
        "K4: genau EIN Order-Klick; gesendet/retry_ok davor gesetzt, nur ohne Druck zurückgenommen")
    qk = "".join(_i.getsource(f) for f in (ob._tsx_k4_senden, ob._tsx_k4_feld, ob._tsx_k4_reiter, ob._tsx_k4_feld_aus))
    chk("close_rect" not in qk and qk.count("TSX_K4_TABU") == 3 and qk.count("pruef=") == 3 and "doppel=True" in _i.getsource(ob._tsx_k4_feld)
        and "time.sleep" not in qk, "K4-Schritte: jeder Klick mit Ziel-Beweis + Tabu, Close-Zelle nie benutzt, keine festen Pausen")
    sig = _i.signature(ob._AugenSitzung.klick)
    chk(sig.parameters["doppel"].default is False and "doppel=bool(doppel and pruef)" in _i.getsource(ob._AugenSitzung._win_klick),
        "Hand: Doppelklick nur als Zusatz mit Ziel-Beweis, Standard unverändert ein Klick")
    js = open(os.path.join(os.path.dirname(os.path.abspath(ob.__file__)), "augen_tsx.js"), encoding="utf-8").read()
    neu_js = js.split("function reiterLesen()")[1].split("function positionAus")[0]
    chk("var VERSION = 'tsx-0.6.1'" in js and "-tab-positionTab$" in neu_js and "'risk'" in neu_js and "'to make'" in neu_js and "close_rect" in neu_js
        and "o.ticket.k4 = true" in js and ".click(" not in neu_js and "dispatchEvent" not in neu_js and ".focus(" not in neu_js
        and not re.search(r"\.value\s*=[^=]", neu_js), "augen_tsx.js tsx-0.6.x: Reiter + Positions-Tabelle (Risk / To Make, Bearbeiten-Zustand) — nur lesend")
    chk("zuletzt" in js and "15000" in js and "e.zuletzt = jetzt; m.erst_gesehen = e.erst;" in js, "augen_tsx.js 0.6.1: Meldungs-Merker vergisst nach 15 s (Prüfer 06.10.2026)")
    chk("s._druck_versucht = False" in q4 and q4.index("s._druck_versucht = False") < q4.index("s.klick(") and "< 30.0" in q4
        and "< 27.0" in _i.getsource(ob._tsx_k4_feld) and q4.index('raus("", msg, "fertig", ok=True)') < q4.index('_puls_ergebnis_senden("order", "ende"')
        and q4.index("if einstieg is None and abg:") < q4.index('raus("abgelehnt"') and "offen_tab" in _i.getsource(ob.tsx_k3_vor_klick)
        and _i.getsource(ob._AugenSitzung.klick).index("self._druck_versucht = False") < _i.getsource(ob._AugenSitzung.klick).index("self._win_klick(") and "self._druck_versucht = True" in _i.getsource(ob._AugenSitzung._win_klick)
        and "self._druck_versucht = True" in _i.getsource(ob._AugenSitzung.klick) and "tsx_k4_ablehnungen(st, vorher, klick_ms)" in q4
        and 'raus("tabelle_unklar", f"Konto {ext} hat eine offene Position' in _i.getsource(ob.modus_tsxlesen_cdp)
        and "offene Position gelesen" in _i.getsource(ob.tsx_k3_vor_klick),
        "Prüfer 06.10.2026: Druck-Merker vor dem Druck (je Ziel), Zeit-Schwellen 30/27 s, Antwort vor den Netz-Sendungen, Ablehnung erst am Ende, 0-Zeilen keine Position")
    if ok:
        print("✓ TSX-K4: Order-Knopf genau einmal mit Fill-Beweis, Risk / To Make per Doppelklick + Rücklesung, Warnung statt Abbruch nach dem Fill")
    return ok


def test_puls_win_maus():
    """Puls-Chrome mit echter Windows-Maus (Finn 29.09.2026, „immer nur so"): augen.js Auge, Windows Hand, :hover-Beweis vor jedem
    Druck — geprüft an der echten Sitzungs-Klasse mit nachgebildeten Windows-Funktionen."""
    import order_bot as ob
    ok = True

    def chk(bed, text):
        nonlocal ok
        if not bed:
            print("  ✗ Win-Maus: " + text)
            ok = False
    chk(ob.win_taste_text("a", 2) == "^a" and ob.win_taste_text("Tab") == "{TAB}" and ob.win_taste_text("ArrowDown") == "{DOWN}"
        and ob.win_taste_text("Escape") == "{ESC}" and ob.win_taste_text("Enter") == "{ENTER}" and ob.win_taste_text("F13") is None
        and ob.win_taste_text("t", 8) == "+t",
        "Tasten → send_keys")
    f1 = {"hwnd": 11, "text": "MNQZ2026 30,481.00 ▼ −0.28% Unnamed - Google Chrome", "klasse": "Chrome_WidgetWin_1", "sichtbar": True}
    f2 = {"hwnd": 22, "text": "Tradovate - Google Chrome", "klasse": "Chrome_WidgetWin_1", "sichtbar": True}
    dt = {"hwnd": 33, "text": "DevTools - www.tradingview.com", "klasse": "Chrome_WidgetWin_1", "sichtbar": True}
    leer = {"hwnd": 44, "text": "", "klasse": "Chrome_WidgetWin_1", "sichtbar": True}
    w = ob.puls_fenster_waehlen
    chk(w([f1, dt, leer], "MNQZ2026 30,490.25 ▲ 0.01% Unnamed") == 11, "einziges Browser-Fenster (DevTools/ohne Titel zählen nicht)")
    chk(w([f1, f2], "MNQZ2026 30,490.25 ▲") == 11 and w([f1, f2], "Tradovate") == 22, "zwei Fenster: erstes Wort des Seitentitels (Kurs ändert sich)")
    chk(w([f1, dict(f1, hwnd=12)], "MNQZ2026 x") is None and w([], "x") is None, "mehrdeutig/keins → None (nie raten)")
    chk("elementFromPoint(100.5,200.0)" in ob.win_hover_js(100.5, 200) and ":hover" in ob.win_hover_js(1, 2), "Hover-Probe liest nur")

    # echte Klasse, Windows nachgebildet
    alt = {n: getattr(ob, n) for n in ("_WIN_EINGABE", "_puls_fenster_liste", "_puls_chrome_browser_pid", "_win_vordergrund", "_win_minimiert",
                                       "_win_zeigen", "_win_nach_vorn", "_klient_rechteck", "_maus_fahren", "_klick_absolut", "_dpi_bewusst",
                                       "_warte", "_win_tasten", "_win_root_am_punkt")}
    zustand = {"hover": True, "vorn": 11, "klicks": [], "tasten": [], "gezeigt": [], "minimiert": True, "fahrten": [], "wurzel": 11}

    class _Ws:
        def rufe(self, m, par=None, timeout=10.0):
            if m != "Runtime.evaluate":
                return {}
            a = (par or {}).get("expression", "")
            if a == ob.WIN_GEO_JS:
                return {"result": {"value": {"innerWidth": 1600, "innerHeight": 773, "dpr": 1, "titel": "MNQZ2026 30,481.00 Unnamed"}}}
            if "elementFromPoint" in a:
                h_ = zustand["hover"]
                return {"result": {"value": h_(a) if callable(h_) else h_}}
            if a == ob.CDP_TOAST_ZU_JS:
                return {"result": {"value": zustand.get("zu", [])}}
            return {"result": {"value": None}}

        def zu(self):
            pass
    try:
        ob._WIN_EINGABE = True
        ob._puls_fenster_liste = lambda pid: [f1]
        ob._puls_chrome_browser_pid = lambda: 4711
        ob._win_vordergrund = lambda: zustand["vorn"]
        ob._win_minimiert = lambda h: zustand["minimiert"]
        ob._win_zeigen = lambda h, b: (zustand["gezeigt"].append(b), zustand.update(minimiert=(b in (6, 7))))
        ob._win_nach_vorn = lambda h: None
        ob._klient_rechteck = lambda h: (0, 87, 1600, 773)          # Klient 1600 breit, 87 px Tab-/Adressleiste über dem Viewport
        ob._maus_fahren = lambda x, y, schritte=8: zustand["fahrten"].append((x, y))
        ob._klick_absolut = lambda x, y, taste="links", doppel=False: (zustand["klicks"].append((x, y)), True)[1]
        ob._dpi_bewusst = lambda: True
        ob._warte = lambda a, b: None
        ob._win_tasten = lambda t: zustand["tasten"].append(t)
        ob._win_root_am_punkt = lambda x, y: (zustand["wurzel"], "Fremd")
        s_ = ob._AugenSitzung.__new__(ob._AugenSitzung)
        s_.trail, s_.ws, s_.js, s_.maus, s_.target_id = [], _Ws(), "/* augen.js */", (0.0, 0.0), "T"
        chk(s_.klick([952, 701, 282, 56], "SENDEN-Knopf") is True and len(zustand["klicks"]) == 1, "Hover bewiesen → genau EIN Druck")
        x_, y_ = zustand["klicks"][0]
        chk(952 + 282 / 3 <= x_ <= 952 + 2 * 282 / 3 + 1 and 87 + 701 + 56 / 3 <= y_ <= 87 + 701 + 2 * 56 / 3 + 1,
            f"Bildschirmpunkt im inneren Drittel inkl. Leiste oben ({x_},{y_})")
        chk(zustand["gezeigt"][:1] == [9] and "Windows-Maus, Hover bewiesen" in s_.trail[-1], "minimiertes Fenster wiederhergestellt (SW_RESTORE), Spur sagt Windows-Maus")
        zustand["hover"] = False
        chk(s_.klick([952, 701, 282, 56], "SENDEN-Knopf") is False and len(zustand["klicks"]) == 1 and "kein Druck" in s_.trail[-1],
            "kein Hover (fremdes Fenster/falsche Umrechnung) → KEIN Druck")
        zustand["hover"], zustand["wurzel"] = True, 77
        chk(s_.klick([952, 701, 282, 56], "SENDEN-Knopf") is False and len(zustand["klicks"]) == 1 and "anderes Fenster" in s_.trail[-1],
            "am Zielpunkt liegt ein anderes Fenster (WindowFromPoint) → KEIN Druck, auch mit Hover")
        zustand["wurzel"] = 11
        zustand["hover"], zustand["vorn"] = True, 99
        chk(s_.klick([952, 701, 282, 56], "SENDEN-Knopf") is False and len(zustand["klicks"]) == 1, "Puls-Chrome nicht vorn → KEIN Druck")
        zustand["vorn"] = 11
        # Live 16:13 UTC: Meldungsstapel über dem Konto-Umschalter → kein Druck aufs Ziel, erst das X der Meldungen, dann EIN neuer Klick
        n0 = len(zustand["klicks"])
        zustand["zu"] = [{"art": "gruppe", "dn": "toast-group-close-button-orders", "rect": [20, 600, 20, 20]}]
        zustand["hover"] = lambda a: {"hover": True, "toast": bool(zustand.get("zu"))} if "30.0,610.0" not in a else {"hover": True, "toast": True}

        def _klick_x(x, y, taste="links", doppel=False):
            zustand["klicks"].append((x, y))
            if len(zustand["klicks"]) == n0 + 1:
                zustand["zu"] = []                     # erster Druck = X der Gruppe → Meldungen weg
            return True
        ob._klick_absolut = _klick_x
        alt_kp = ob.cdp_klickpunkt
        ob.cdp_klickpunkt = lambda r, rnd=None: (r[0] + r[2] / 2, r[1] + r[3] / 2) if r else None
        try:
            ok_v = s_.klick([100, 700, 180, 28], "Konto-Umschalter")
        finally:
            ob.cdp_klickpunkt = alt_kp
        chk(ok_v is True and len(zustand["klicks"]) == n0 + 2 and any("von einer TradingView-Meldung verdeckt" in z for z in s_.trail)
            and any("Meldungen schließen (gruppe X)" in z for z in s_.trail), f"verdeckt → Meldungen per X weg → Ziel genau einmal ({zustand['klicks'][n0:]})")
        zustand["hover"] = True
        ob._klick_absolut = lambda x, y, taste="links", doppel=False: (zustand["klicks"].append((x, y)), True)[1]
        s_.taste("a", modifiers=2)
        s_.tippen("1+0")
        chk(zustand["tasten"] == ["^a", "1", "{+}", "0"], f"Tastatur über Windows, Sonderzeichen entschärft ({zustand['tasten']})")
        zustand["vorn"] = 99
        try:
            s_.taste("Tab")
            chk(False, "Taste ohne Vordergrund muss abbrechen")
        except RuntimeError:
            pass
        zustand["vorn"] = 11
        n_k = len(zustand["klicks"])
        chk(s_.hin([72, 630, 860, 40], "Zeile") is True and len(zustand["klicks"]) == n_k, "hin = nur fahren, kein Druck")
        s_.zu()
        chk(zustand["gezeigt"][-1] == 7, "am Ende wieder minimiert (SW_SHOWMINNOACTIVE)")
        chk(ob._k3_fenster(s_, "normal", []) is None, "Windows: kein CDP-Fensterwechsel (maximiert bliebe sonst nicht)")
    finally:
        for n, v in alt.items():
            setattr(ob, n, v)
    if ok:
        print("✓ Puls Windows-Maus: Tasten, Fensterwahl, Hover-Beweis vor jedem Druck, Vordergrund-Riegel, wieder minimiert")
    return ok


def test_puls_topstep():
    """Puls für Topstep, Etappe 1 (27.09.2026, B16): reine Teile — TopstepX nie als TradingView, Konto-Treffer, Ineligible,
    Contract MNQ/NQ, BAL US-Format, Kopfzeile, Knopf mit Menge, Position, Inventar."""
    import order_bot as ob
    ok = True

    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ Puls-Topstep: " + name); ok = False

    tsx_titel = "MNQZ26 30,922.50 ▲ +0.4% | TopstepX - Google Chrome"
    chk("TopstepX-Titel erkannt", ob.ist_topstepx_titel(tsx_titel) and ob.ist_topstepx_titel("TopstepX") and not ob.ist_topstepx_titel("Topstep Dashboard"))
    chk("TopstepX nie als TradingView-Fenster/-Tab/schliessbar", not ob.ist_tradingview_fenster(tsx_titel, "Chrome_WidgetWin_1")
        and ob.tv_tab_rang(tsx_titel, "MNQZ26", "MNQZ6") == 0 and not ob.tv_tab_schliessbar(tsx_titel, "Chrome_WidgetWin_1", "MNQZ26"))
    chk("TradingView-Chart weiter erkannt", ob.tv_tab_rang("MNQZ2026 30,922.50 ▲ +0.4% Unnamed", "", "") > 0)
    liste = ["$150K TRADING COMBINE | 150KTC-SKU-V2-000000-11000000", "$150K EXPRESS | EXPRESS-V2-000000-10000001",
             "$50K EXPRESS | EXPRESS-V2-000000-10000000 (Ineligible)"]
    chk("Konto aus Text", ob.tsx_konto_aus_text(liste[1]) == "EXPRESS-V2-000000-10000001" and ob.tsx_konto_aus_text("BAL: $11,079.66") == "")
    chk("Konto-Treffer genau einer", ob.tsx_konto_treffer(liste, "EXPRESS-V2-000000-10000001") == (1, ""))
    chk("nur Ineligible → kein Treffer mit Grund", ob.tsx_konto_treffer(liste, "EXPRESS-V2-000000-10000000")[0] is None
        and "Ineligible" in ob.tsx_konto_treffer(liste, "EXPRESS-V2-000000-10000000")[1])
    chk("Teiltreffer zählt nicht (…1000000 vs …10000001)", ob.tsx_konto_treffer(liste, "EXPRESS-V2-000000-1000000")[0] is None)
    chk("doppelt → nicht eindeutig", ob.tsx_konto_treffer(liste + [liste[1]], "EXPRESS-V2-000000-10000001")[0] is None)
    vor = ["MNQZ26 · Micro Nasdaq (Dec 2026)", "NQZ26 · Nasdaq (Dec 2026)", "MNQH27 · Micro Nasdaq (Mar 2027)"]
    chk("Contract NQ ≠ MNQ", ob.tsx_contract_wahl(vor[:2], "NQ") == 1 and ob.tsx_contract_wahl(vor[:2], "MNQ") == 0)
    chk("Contract mehrdeutig (zwei MNQ-Monate) → None", ob.tsx_contract_wahl(vor, "MNQ") is None)
    chk("BAL US-Format", ob.tsx_geld("$11,079.66") == 11079.66 and ob.tsx_geld("-$1,234.50") == -1234.5
        and ob.tsx_geld("($12.50)") == -12.5 and ob.tsx_geld("—") is None)
    kopf = [("BAL: $11,079.66", (0, 0, 9, 9), "Text"), ("MLL:", (0, 0, 9, 9), "Text"), ("$10,500.00", (0, 0, 9, 9), "Text"),
            ("RP&L: -$120.25", (0, 0, 9, 9), "Text"), ("UP&L", (0, 0, 9, 9), "Text"), ("$0.00", (0, 0, 9, 9), "Text")]
    chk("Kopfzeile: Wert im selben oder im nächsten Element", ob.tsx_kopf_werte(kopf) == {"balance": 11079.66, "mll": 10500.0, "rpl": -120.25, "upl": 0.0})
    chk("Knopf mit Menge", ob.tsx_knopf_passt("BUY +2 @ MARKET", "buy", 2) and ob.tsx_knopf_passt("SELL -3 @ MARKET", "sell", 3)
        and not ob.tsx_knopf_passt("BUY +1 @ MARKET", "buy", 2) and not ob.tsx_knopf_passt("SELL -2 @ MARKET", "buy", 2)
        and not ob.tsx_knopf_passt("BUY -2 @ MARKET", "buy", 2) and not ob.tsx_knopf_passt("BUY +2 @ LIMIT", "buy", 2))
    bw = ob.tsx_bracket_werte
    chk("Brackets: Plan MIT SL → Risk = SL, Profit = TP", bw(400, 250) == ({"profit": "400", "risk": "250"}, None)
        and bw("212.5", "122") == ({"profit": "212.5", "risk": "122"}, None))
    chk("Brackets: OHNE SL (WD und normal) → Risk wird geleert, Profit = TP", bw(400, None) == ({"profit": "400", "risk": ""}, None)
        and bw(400, 0) == ({"profit": "400", "risk": ""}, None) and bw(400, "") == ({"profit": "400", "risk": ""}, None))
    chk("Brackets: ohne TP → Abbruch", bw(None, 250)[0] is None and bw(0, None)[0] is None)
    chk("Position: No Active Position → keine, sonst unbekannt", ob.tsx_position_zustand(["No Active Position"]) == "keine"
        and ob.tsx_position_zustand(["MNQZ26 +2"]) is None)
    inv = ob.tsx_inventar_kurz([("Buy", (10, 10, 50, 30), "Button"), ("Buy", (10, 10, 50, 30), "Button"), ("", (0, 0, 9, 9), "Text"),
                               ("Weit weg", (5000, 5000, 5050, 5020), "Text"), ("Kaputt", None, "Text")], (0, 0, 1920, 1080))
    chk("Inventar: sichtbar, im Fenster, ohne Dubletten", inv == [["Buy", "Button", [10, 10, 50, 30]]])
    if ok:
        print("✓ Puls-Topstep: TopstepX nie TV, Konto exakt/nie Ineligible, Contract MNQ≠NQ, BAL US, Knopf mit Menge, Position, Inventar")
    return ok


def test_puls_nie_chrome_schliessen():
    """B17 (27.09.2026, PC von ID A): Puls klickte in TopstepX Chromes eigenes Tab-/Fenster-X („Close") und schloss Prophos.
    Jetzt: Klicks nur in der Webseite; allgemeine Strg+W-Regel; Trockenlauf mit Chromes Knöpfen im UIA-Baum."""
    import order_bot as ob, io, contextlib, json as _j, sys as _s, types as _t
    ok = True

    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ Nie-Chrome-schliessen: " + name); ok = False

    seite = (0, 120, 1920, 1040)
    chrome_x = [("Close", (1870, 0, 1920, 30), "Button"), ("Close", (400, 10, 420, 30), "Button"),
                ("Schließen", (620, 10, 640, 30), "Button")]
    banner_x = [("Close", (1800, 130, 1820, 150), "Button")]
    chk("Seitenfilter: Chromes Tab-/Fenster-X fallen raus, Seiten-X bleibt",
        ob.seiten_filter(chrome_x + banner_x, seite) == banner_x)
    chk("ohne Seitenbereich: nichts", ob.seiten_filter(chrome_x + banner_x, None) == [])
    w = ob.strg_w_erlaubt
    chk("Strg+W: TradingView vorn + 2 Tabs → ja", w("MNQZ2026 30,922.50 ▲ +0.4% Unnamed - Google Chrome", "tv", 2))
    chk("Strg+W: Prophos vorn → nie", not w("Prophos - Google Chrome", "tv", 3) and not w("Prophos", "tsx", 3))
    chk("Strg+W: nur ein Tab → nie (Fenster ginge zu)", not w("MNQZ2026 30,922.50 ▲ +0.4% Unnamed", "tv", 1))
    chk("Strg+W: TopstepX nur mit Ziel tsx, TV-Ziel nie auf TopstepX",
        w("MNQZ26 | TopstepX - Google Chrome", "tsx", 2) and not w("MNQZ26 30,922.50 | TopstepX - Google Chrome", "tv", 2))
    chk("Strg+W: leerer Titel/Tabzahl unbekannt → nie", not w("", "tv", 3) and not w("MNQZ2026 30,922.50 ▲ +0.4%", "tv", None))

    # Trockenlauf tsxlesen: Fenster = Prophos-Fenster mit TopstepX-Tab, Chromes X-Knoepfe im Baum
    alt_mod = _s.modules.get("pywinauto")
    pw = _t.ModuleType("pywinauto"); pw.Desktop = object; _s.modules["pywinauto"] = pw
    geklickt = []
    class Wf:
        def window_text(self): return "MNQZ26 30,922.50 | TopstepX - Google Chrome"
        def set_focus(self): pass
        def descendants(self, **kw): return []
    orig = {k: getattr(ob, k) for k in ("_puls_fenster", "_tv_fenster_rect", "_dpi_bewusst", "_warte", "_tv_uia_roh",
                                         "_tv_uia_klick", "_tsx_seite", "_puls_diagnose_senden", "_tsx_wachhund")}
    try:
        wf = Wf()
        ob._puls_fenster = lambda trail: (wf, "gemerkt", "")
        ob._tv_fenster_rect = lambda w_: (0, 0, 1920, 1040)
        ob._dpi_bewusst = lambda: None
        ob._warte = lambda a, b: None
        ob._tsx_seite = lambda w_: seite
        ob._puls_diagnose_senden = lambda *a, **k: None
        ob._tsx_wachhund = lambda *a, **k: None
        ob._tv_uia_roh = lambda w_, typen=None, mx=0, muster=(): chrome_x + [
            ("$150K TRADING COMBINE | 150KTC-SKU-V2-000000-20000000", (20, 160, 300, 180), "Text"),
            ("BAL: $149,210.00", (400, 130, 520, 150), "Text"), ("No Active Position", (1500, 400, 1700, 420), "Text")]
        ob._tv_uia_klick = lambda el, name, trail: (geklickt.append((name, el.get("punkt"))), (True, ""))[1]
        b = io.StringIO()
        with contextlib.redirect_stdout(b):
            ob.modus_tsxlesen({"konto": "150KTC-SKU-V2-000000-20000000"})
        r = _j.loads(b.getvalue().strip().splitlines()[-1])
        chk("Trockenlauf: Balance gelesen, kein einziger Klick auf Chromes X",
            r.get("ok") and r.get("balance") == 149210.0 and not any(p_ and p_[1] < 120 for _n, p_ in geklickt))
    finally:
        for k, v in orig.items():
            setattr(ob, k, v)
        if alt_mod is None:
            _s.modules.pop("pywinauto", None)
        else:
            _s.modules["pywinauto"] = alt_mod
    if ok:
        print("✓ Nie-Chrome-schliessen: Klicks nur in der Seite, Strg+W-Regel (Titel/Prophos/≥2 Tabs), Trockenlauf ohne Chrome-X")
    return ok


def test_tsx_konto_abgekuerzt():
    """B18 (27.09.2026, zweiter Live-Test bei ID A): Auslöser zeigt „$150K EXPRESS | EXPRESS-…" (abgekürzt) — Konto über die
    aufgeklappte Liste mit der vollen ID wählen; jeder Schritt mit Ende."""
    import order_bot as ob, io, contextlib, json as _j, sys as _s, types as _t
    ok = True

    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ TSX-Konto abgekürzt: " + name); ok = False

    chk("sichtbar: abgekürzt", ob.tsx_konto_sichtbar("$150K EXPRESS | EXPRESS-…") == ("EXPRESS", True)
        and ob.tsx_konto_sichtbar("$150K EXPRESS | EXPRESS-V2-68...") == ("EXPRESS-V2-68", True))
    chk("sichtbar: voll", ob.tsx_konto_sichtbar("$150K EXPRESS | EXPRESS-V2-000000-10000001") == ("EXPRESS-V2-000000-10000001", False)
        and ob.tsx_konto_sichtbar("BAL: $11,079.66") == ("", False))
    ext = "EXPRESS-V2-000000-10000001"
    chk("steht: voll gleich → ja, abgekürzt Präfix → vielleicht, anderes → nein",
        ob.tsx_konto_steht("$150K EXPRESS | EXPRESS-V2-000000-10000001", ext) == "ja"
        and ob.tsx_konto_steht("$150K EXPRESS | EXPRESS-…", ext) == "vielleicht"
        and ob.tsx_konto_steht("$150K TRADING COMBINE | 150KTC-…", ext) == "nein"
        and ob.tsx_konto_steht("$150K EXPRESS | EXPRESS-V2-000000-10000000", ext) == "nein")

    wu = ob.tsx_wechsel_urteil
    liste2 = ["$150K TRADING COMBINE | 150KTC-SKU-V2-000000-11000000", "$150K TRADING COMBINE | 150KTC-SKU-V2-000000-20000000",
              "$150K EXPRESS | EXPRESS-V2-000000-10000001"]
    chk("Urteil: volle Ziel-ID → bestätigt", wu("$150K TRADING COMBINE | 150KTC-SKU-V2-000000-11000000",
                                               "150KTC-SKU-V2-000000-11000000", liste2, 11079.66, 11079.66)[0])
    chk("Urteil: anderes TRADING COMBINE (gleiches Präfix, volle ID) → nein",
        not wu("$150K TRADING COMBINE | 150KTC-SKU-V2-000000-20000000", "150KTC-SKU-V2-000000-11000000", liste2, 1.0, 2.0)[0])
    chk("Urteil: abgekürzt + Präfix doppelt (zwei TRADING COMBINE) → nie bestätigt, auch wenn BAL sich ändert",
        not wu("$150K TRADING COMBINE | 150KTC-…", "150KTC-SKU-V2-000000-11000000", liste2, 11079.66, 154504.88)[0])
    chk("Urteil: abgekürzt + Präfix eindeutig + BAL geändert → bestätigt; BAL gleich → nein",
        wu("$150K EXPRESS | EXPRESS-…", "EXPRESS-V2-000000-10000001", liste2, 154504.88, 11079.66)[0]
        and not wu("$150K EXPRESS | EXPRESS-…", "EXPRESS-V2-000000-10000001", liste2, 11079.66, 11079.66)[0])
    chk("BAL US-Format aus Finns Screenshot", ob.tsx_kopf_werte([("BAL: $154,504.88", (0, 0, 9, 9), "Text")])["balance"] == 154504.88)

    alt_mod = _s.modules.get("pywinauto")
    pw = _t.ModuleType("pywinauto"); pw.Desktop = object; _s.modules["pywinauto"] = pw
    z = {"offen": False, "konto": "EXPRESS-V2-000000-11111111"}
    class Wf:
        handle = 4711
        def window_text(self): return "NQZ26 $30,921.75 | TopstepX - Google Chrome"
        def set_focus(self): pass
        def descendants(self, **kw): return []
    def roh(w_, typen=None, mx=0, muster=()):
        if z.get("alt_runden", 0) > 0:          # B21: React-Knoten bleibt nach dem Klick eine Runde alt stehen
            z["alt_runden"] -= 1
            anzeige = z["alt_konto"]
        else:
            anzeige = z["konto"]
        out = [("Close", (1870, 0, 1920, 30), "Button"), (f"$150K EXPRESS | {anzeige}", (20, 160, 300, 180), "Button"),
               ("BAL: $11,079.66", (400, 160, 520, 180), "Text"), ("MLL: $145,500.00", (540, 160, 660, 180), "Text"),
               ("No Active Position", (1500, 400, 1700, 420), "Text")]
        if z["offen"]:
            out += [("$150K TRADING COMBINE | 150KTC-SKU-V2-000000-11000000", (20, 200, 300, 220), "ListItem"),
                    ("$150K EXPRESS | EXPRESS-V2-000000-10000001", (20, 230, 300, 250), "ListItem"),
                    ("$50K EXPRESS | EXPRESS-V2-000000-10000000 (Ineligible)", (20, 260, 300, 280), "ListItem")]
        return out
    def klick(el, name, trail):
        trail.append("Klick " + name)
        if name == "Konto-Dropdown öffnen":
            z["offen"] = True
        elif name.startswith("Konto EXPRESS"):
            z.update(offen=True, alt_konto=z["konto"], konto="EXPRESS-V2-000000-10000001", alt_runden=1)   # Liste bleibt im Baum
        return True, ""
    orig = {k: getattr(ob, k) for k in ("_puls_fenster", "_tv_fenster_rect", "_dpi_bewusst", "_warte", "_tv_uia_roh",
                                         "_tv_uia_klick", "_tsx_seite", "_puls_diagnose_senden", "_tsx_wachhund")}
    try:
        wf = Wf()
        ob._puls_fenster = lambda trail: (wf, "gemerkt", "")
        ob._tv_fenster_rect = lambda w_: (0, 0, 1920, 1040)
        ob._dpi_bewusst = lambda: None
        ob._warte = lambda a, b: None
        ob._tsx_seite = lambda w_: (0, 120, 1920, 1040)
        ob._puls_diagnose_senden = lambda *a, **k: None
        ob._tsx_wachhund = lambda *a, **k: None
        ob._tv_uia_roh = roh
        ob._tv_uia_klick = klick
        b = io.StringIO()
        with contextlib.redirect_stdout(b):
            ob.modus_tsxlesen({"konto": ext})
        r = _j.loads(b.getvalue().strip().splitlines()[-1])
        chk("Trockenlauf: anderes Konto → Liste → Eintrag → alter Knoten 1 Runde, Liste bleibt im Baum → trotzdem bestätigt → Balance",
            r.get("ok") and r.get("konto_aktiv") == ext and r.get("balance") == 11079.66 and "Konto per Liste gewählt" in r.get("trail", "")
            and "Klick Konto EXPRESS" in r.get("trail", "") and "Wechsel-Prüfung (2 Runden)" in r.get("trail", ""))
        chk("Spur ohne 'TradingView' im TopstepX-Lauf", "TradingView" not in r.get("trail", ""))
        z.update(offen=False, konto="EXPRESS-V2-000000-11111111", alt_runden=0)
        b = io.StringIO()
        with contextlib.redirect_stdout(b):
            ob.modus_tsxlesen({"konto": "EXPRESS-V2-000000-99999999"})
        r2 = _j.loads(b.getvalue().strip().splitlines()[-1])
        chk("unbekanntes Konto: ehrliches Ende mit Grund + Liste", not r2.get("ok") and r2.get("code") == "konto"
            and "nicht in der Liste" in r2.get("msg", "") and len(r2.get("liste") or []) == 3)
    finally:
        for k, v in orig.items():
            setattr(ob, k, v)
        if alt_mod is None:
            _s.modules.pop("pywinauto", None)
        else:
            _s.modules["pywinauto"] = alt_mod
    if ok:
        print("✓ TSX-Konto abgekürzt: sichtbar/steht, Liste → voller Eintrag, Balance, ehrliches Ende")
    return ok


def test_tsx_titel_url():
    """B19 (27.09.2026, dritter Live-Test bei ID A): der geladene TopstepX-Tab heisst „NQZ26 $30,921.75 ▲ +0.50%" (ohne
    'TopstepX') — trotzdem TopstepX, nie TradingView; TradingView-Titel bleiben TradingView; Adresse topstepx.com."""
    import order_bot as ob
    ok = True

    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ TSX-Titel/URL: " + name); ok = False

    tsx = ["NQZ26 $30,921.75 ▲ +0.50%", "MNQZ26 $30,921.75 ▼ −0.10% – Arbeitsspeichernutzung – 188 MB",
           "(2) NQZ26 $30,921.75 ▲ +0.50%", "TopstepX", "NQH27 $31,000.00"]
    tv = ["MNQ1! 30,889.25 ▲ +0.4% Unnamed - Google Chrome", "NQZ2026 30,882.00 ▲ +0.37% Unnamed - Google Chrome",
          "MNQZ2026 30,933.75 ▲ +0.54% Unnamed", "NQZ2026 30,784.50 0% Unnamed"]
    chk("TopstepX-Titel erkannt (auch mit Zähler/Speicher-Zusatz)", all(ob.ist_topstepx_titel(t) for t in tsx))
    chk("TopstepX-Titel nie TradingView", not any(ob.ist_tradingview_fenster(t, "Chrome_WidgetWin_1") or ob.tv_tab_rang(t, "", "") > 0 for t in tsx))
    chk("TradingView-Titel bleiben TradingView, nie TopstepX", all(not ob.ist_topstepx_titel(t) and ob.tv_tab_rang(t, "", "") > 0 for t in tv))
    chk("Prophos/Gmail sind weder noch", not ob.ist_topstepx_titel("Prophos - Google Chrome") and not ob.ist_topstepx_titel("Inbox (585) - x@gmail.com"))
    chk("URL", ob.ist_topstepx_url("topstepx.com/trade") and ob.ist_topstepx_url("https://topstepx.com/trade?x=1")
        and ob.ist_topstepx_url("https://www.topstepx.com/") and not ob.ist_topstepx_url("https://www.tradingview.com/chart/")
        and not ob.ist_topstepx_url("notopstepx.com.evil.io") and not ob.ist_topstepx_url(""))
    chk("Strg+W auf TopstepX nie mit TV-Ziel", not ob.strg_w_erlaubt(tsx[0], "tv", 3))
    if ok:
        print("✓ TSX-Titel/URL: „NQZ26 $…“ = TopstepX, nie TradingView; TV-Titel unverändert; Adresse topstepx.com")
    return ok


def test_tsx_zeilen():
    """B20 (27.09.2026, Inventar bei ID A: 2 Kandidaten, aber kein Auslöser): getrennte Knoten „$150K EXPRESS" / „|" /
    „EXPRESS-…" zu einem Stück zusammenfügen — ohne die Kopfzeile (BAL …) rechts daneben mitzunehmen."""
    import order_bot as ob
    ok = True

    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ TSX-Zeilen: " + name); ok = False

    roh = [("$150K EXPRESS", (20, 160, 120, 180), "Text"), ("|", (124, 160, 128, 180), "Text"),
           ("EXPRESS-…", (132, 160, 220, 180), "Text"), ("BAL: $11,079.66", (600, 160, 720, 180), "Text"),
           ("MLL: $145,500.00", (740, 160, 860, 180), "Text"), ("Chart", (20, 400, 80, 420), "Text")]
    z = ob.tsx_zeilen(roh)
    chk("Stücke: Auslöser zusammen, Kopfzeile getrennt", ("$150K EXPRESS | EXPRESS-…", (20, 160, 220, 180)) in z
        and any(t.startswith("BAL: $11,079.66") for t, _r in z) and not any("EXPRESS" in t and "BAL" in t for t, _r in z))
    a = ob.tsx_ausloeser_waehlen(roh)
    chk("Auslöser aus Stücken, Klick-Rechteck = erster Knoten (Label)", a == ("$150K EXPRESS | EXPRESS-…", (20, 160, 120, 180), "Zeile")
        and ob.tsx_konto_steht(a[0], "EXPRESS-V2-000000-10000001") == "vielleicht")
    einzeln = [("$150K EXPRESS | EXPRESS-V2-000000-10000001", (20, 160, 300, 180), "Button")] + roh
    chk("ein einzelnes Element mit dem ganzen Muster geht vor", ob.tsx_ausloeser_waehlen(einzeln)[2] == "Button")
    liste = roh + [("$150K TRADING COMBINE", (20, 200, 150, 220), "Text"), ("|", (152, 200, 156, 220), "Text"),
                   ("150KTC-SKU-V2-000000-11000000", (160, 200, 360, 220), "Text"),
                   ("$150K EXPRESS", (20, 230, 120, 250), "Text"), ("|", (124, 230, 128, 250), "Text"),
                   ("EXPRESS-V2-000000-10000001", (132, 230, 330, 250), "Text")]
    e = ob.tsx_eintraege_waehlen(liste, 184)
    chk("Einträge unterhalb aus Stücken, volle ID", [t for t, _r, _ty in e] ==
        ["$150K TRADING COMBINE | 150KTC-SKU-V2-000000-11000000", "$150K EXPRESS | EXPRESS-V2-000000-10000001"]
        and ob.tsx_konto_treffer([t for t, _r, _ty in e], "EXPRESS-V2-000000-10000001") == (1, ""))
    chk("leer/Unsinn wirft nicht", ob.tsx_zeilen(None) == [] and ob.tsx_ausloeser_waehlen([("x", None, "Text")]) is None)
    if ok:
        print("✓ TSX-Zeilen: getrennte Knoten → Auslöser/Einträge, Kopfzeile bleibt getrennt, Einzel-Element geht vor")
    return ok


def test_tsx_inventar_ida():
    """B22 (27.09.2026, Inventar pc-aaaaaa 11:24 UTC, exakt diese Knoten): Auslöser ohne Kennung („$150K TRADING COMBINE" + „|"),
    Kopfzeile „BAL:" · „$" · „154,504.88" getrennt; Wechsel-Urteil ohne Kennung (Label + BAL / eindeutiges Label)."""
    import order_bot as ob
    ok = True

    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ TSX-Inventar ID A: " + name); ok = False

    roh = [("Weekend Hours", (75, 124, 200, 149), "Text"), (":", (199, 124, 206, 149), "Text"),
           ("We are undergoing scheduled maintenance, which may temporari", (220, 124, 1200, 149), "Text"),
           ("$150K TRADING COMBINE", (102, 180, 262, 199), "Text"), ("|", (267, 180, 280, 199), "Text"),
           ("BAL:", (346, 181, 379, 200), "Text"), ("$", (378, 181, 386, 200), "Text"), ("154,504.88", (385, 181, 455, 200), "Text"),
           ("MLL:", (484, 181, 518, 200), "Text"), ("$", (517, 181, 525, 200), "Text"), ("150,000.00", (525, 181, 594, 200), "Text"),
           ("RP&L:", (623, 181, 664, 200), "Text"), ("$0.00", (663, 181, 699, 200), "Text"),
           ("UP&L:", (727, 181, 769, 200), "Text"), ("$0.00", (768, 181, 803, 200), "Text"),
           ("Trading Lockout", (832, 181, 852, 201), "Button"), ("Chart X", (95, 218, 155, 254), "TabItem")]
    a = ob.tsx_ausloeser_waehlen(roh)
    chk("Auslöser ohne Kennung gefunden (nur Label + |), Klick-Rechteck = Label-Knoten",
        a is not None and a[0].startswith("$150K TRADING COMBINE") and a[1] == (102, 180, 262, 199))
    mit_id = [("$150K TRADING COMBINE", (102, 180, 262, 199), "Text"), ("|", (267, 180, 280, 199), "Text"),
              ("150KTC-SKU-V2-000000-11000000", (284, 180, 560, 199), "Text"), ("BAL:", (620, 181, 650, 200), "Text")]
    a2 = ob.tsx_ausloeser_waehlen(mit_id)
    chk("B24: Auslöser MIT ID (Stück bis x=560) → Klick auf den Label-Knoten, nicht in die Stück-Mitte",
        a2[1] == (102, 180, 262, 199) and (a2[1][0] + a2[1][2]) // 2 < 300)
    knopf = mit_id + [("", (90, 172, 300, 206), "Button"), ("Konto", (80, 170, 900, 210), "Button")]
    a3 = ob.tsx_ausloeser_waehlen([e for e in knopf if e[0]] + [("Kontoauswahl", (90, 172, 300, 206), "Button")])
    chk("B24: umschließender (kleinster) Button → dessen Rechteck", a3[1] == (90, 172, 300, 206))
    chk("Stand ohne Kennung = unbekannt → Liste öffnen", ob.tsx_konto_steht(a[0], "150KTC-SKU-V2-000000-11000000") == "unbekannt")
    chk("Kopfzeile aus drei Knoten: BAL/MLL/RP&L/UP&L", ob.tsx_kopf_werte(roh) == {"balance": 154504.88, "mll": 150000.0, "rpl": 0.0, "upl": 0.0})
    chk("Kopfzeile negativ getrennt: -$ und 120.25 als zwei Knoten", ob.tsx_kopf_werte([("RP&L:", None, "T"), ("-$", None, "T"), ("120.25", None, "T")])["rpl"] == -120.25)
    K_ = ob.tsx_kopf_werte
    chk("Kopfzeile aus VIER Knoten: - · $ · 50.00 (T2-Parität 30.09.2026)",
        K_([("RP&L:", None, "T"), ("-", None, "T"), ("$", None, "T"), ("50.00", None, "T")])["rpl"] == -50.0
        and K_([("UP&L:", None, "T"), ("(", None, "T"), ("$", None, "T"), ("12.50", None, "T"), (")", None, "T")])["upl"] == -12.5
        and K_([("RP&L:", None, "T"), ("$", None, "T"), ("-", None, "T"), ("7.25", None, "T")])["rpl"] == -7.25
        and K_([("BAL:", None, "T"), ("MLL:", None, "T"), ("$", None, "T"), ("150,000.00", None, "T")]) == {"balance": None, "mll": 150000.0, "rpl": None, "upl": None}
        and K_([("RP&L:", None, "T"), ("$", None, "T"), ("50.00", None, "T")])["rpl"] == 50.0
        and K_([("RP&L: -", None, "T"), ("$", None, "T"), ("50.00", None, "T")])["rpl"] == -50.0
        and K_([("UP&L:", None, "T"), ("(", None, "T"), ("$", None, "T"), ("12.50", None, "T")])["upl"] == 12.5
        and K_([("RP&L:", None, "T"), ("", None, "T"), ("-$", None, "T"), ("3.00", None, "T")])["rpl"] == -3.0
        and K_([("BAL:", None, "T"), ("x", None, "T"), ("BAL: $5.00", None, "T")])["balance"] == 5.0)
    G_ = ob.tsx_geld
    chk("Geld wie geld() in augen_tsx.js: Minus vor der ersten Ziffer, Klammer nur mit beiden Enden",
        G_("$-50.00") == -50.0 and G_("$-7.00") == -7.0 and G_("($50.00") == 50.0 and G_("($12.50)") == -12.5 and G_("-$1,234.50") == -1234.5
        and G_("$11,079.66") == 11079.66 and G_("(USD) 50.00") == 50.0 and G_("—") is None)
    liste = ["$150K TRADING COMBINE | 150KTC-SKU-V2-000000-11000000", "$150K TRADING COMBINE | 150KTC-SKU-V2-000000-20000000",
             "$150K EXPRESS | EXPRESS-V2-000000-10000001", "$50K EXPRESS | EXPRESS-V2-000000-0 (Ineligible)"]
    wu = ob.tsx_wechsel_urteil
    chk("ohne Kennung: Label passt + BAL geändert → bestätigt",
        wu("$150K TRADING COMBINE |", "150KTC-SKU-V2-000000-11000000", liste, 11079.66, 154504.88)[0])
    chk("ohne Kennung: Label doppelt + BAL gleich → nicht beweisbar (die zwei TRADING COMBINE von ID A)",
        not wu("$150K TRADING COMBINE |", "150KTC-SKU-V2-000000-11000000", liste, 154504.88, 154504.88)[0])
    chk("ohne Kennung: Label eindeutig (EXPRESS) + BAL gleich → bestätigt",
        wu("$150K EXPRESS |", "EXPRESS-V2-000000-10000001", liste, 11079.66, 11079.66)[0])
    chk("ohne Kennung: falsches Label → nein", not wu("$150K EXPRESS |", "150KTC-SKU-V2-000000-11000000", liste, 1.0, 2.0)[0])
    offen = roh + [("$150K TRADING COMBINE | 150KTC-SKU-V2-000000-11000000", (102, 230, 400, 250), "Text")]
    chk("offene Liste im Baum: Auslöser bleibt der OBERSTE (nicht der Listeneintrag mit voller ID)",
        ob.tsx_ausloeser_waehlen(offen)[1][1] == 180)
    chk("Kopfzeile ist kein Auslöser", not ob.tsx_ist_ausloeser_text("BAL: $ 154,504.88") and ob.tsx_ist_ausloeser_text("$150K TRADING COMBINE |"))
    if ok:
        print("✓ TSX-Inventar ID A: Auslöser ohne Kennung, Kopfzeile aus drei Knoten, Urteil über Label + BAL")
    return ok


def test_tsx_beweis():
    """B23 (27.09.2026, ID A .684): Wechsel klappte, Beweis scheiterte („Ziel-Label ''") — Label aus Nachbarknoten, markierter
    Listeneintrag als Beweis (vorher: steht schon; nachher: Liste erneut öffnen), Reihenfolge ID → markiert → Label + BAL."""
    import order_bot as ob, io, contextlib, json as _j, sys as _s, types as _t
    ok = True

    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ TSX-Beweis: " + name); ok = False

    roh = [("$150K TRADING COMBINE", (102, 270, 262, 288), "Text"), ("150KTC-SKU-V2-000000-20000000", (102, 289, 330, 305), "Text")]
    e = ("✓ 150KTC-SKU-V2-000000-20000000", (102, 289, 330, 305), "Text")
    chk("Label aus Nachbarknoten derselben Listenzeile", ob.tsx_eintrag_label(e, roh) == "$150K TRADING COMBINE")
    chk("Label ohne Anker im eigenen Text", ob.tsx_label("✓ $150K TRADING COMBINE | 150KTC-X") == "$150K TRADING COMBINE")
    mu = ob.tsx_markiert_urteil
    chk("markiert: Ziel / anderes / nichts", mu(["$150K TRADING COMBINE | 150KTC-SKU-V2-000000-20000000"], "150KTC-SKU-V2-000000-20000000") == "ja"
        and mu(["$150K TRADING COMBINE | 150KTC-SKU-V2-000000-11000000"], "150KTC-SKU-V2-000000-20000000") == "nein"
        and mu([], "150KTC-SKU-V2-000000-20000000") == "unbekannt" and mu(["$150K TRADING COMBINE"], "X-1-2") == "unbekannt")
    liste = ["$150K TRADING COMBINE | 150KTC-SKU-V2-000000-11000000", "$150K TRADING COMBINE | 150KTC-SKU-V2-000000-20000000"]
    chk("Urteil mit Label aus Nachbarknoten: Label + BAL geändert → ja",
        ob.tsx_wechsel_urteil("$150K TRADING COMBINE |", "150KTC-SKU-V2-000000-20000000", ["150KTC-SKU-V2-000000-20000000"],
                              154504.88, 149210.0, "$150K TRADING COMBINE")[0])

    # Trockenlauf: Auslöser ohne ID, zwei TRADING COMBINE, BAL gleich → nur der markierte Eintrag beweist
    alt_mod = _s.modules.get("pywinauto")
    pw = _t.ModuleType("pywinauto"); pw.Desktop = object; _s.modules["pywinauto"] = pw
    z = {"konto": "150KTC-SKU-V2-000000-11000000", "offen": False}
    class Wf:
        handle = 1
        def window_text(self): return "NQZ26 $30,921.75 ▲ +0.50% - Google Chrome"
        def set_focus(self): pass
        def descendants(self, **kw): return []
    def roh_f(w_, typen=None, mx=0, muster=()):
        out = [("$150K TRADING COMBINE", (102, 180, 262, 199), "Text"), ("|", (267, 180, 280, 199), "Text"),
               ("BAL:", (346, 181, 379, 200), "Text"), ("$", (378, 181, 386, 200), "Text"), ("154,504.88", (385, 181, 455, 200), "Text")]
        if z["offen"]:
            out += [(liste[0], (102, 230, 400, 250), "Text"), (liste[1], (102, 260, 400, 280), "Text")]
        return out
    def klick(el, name, trail):
        trail.append("Klick " + name)
        if "öffnen" in name:
            z["offen"] = True
        elif name.startswith("Konto 150KTC"):
            z.update(konto="150KTC-SKU-V2-000000-20000000", offen=False)
        return True, ""
    orig = {k: getattr(ob, k) for k in ("_puls_fenster", "_tv_fenster_rect", "_dpi_bewusst", "_warte", "_tv_uia_roh", "_tv_uia_klick",
                                         "_tsx_seite", "_puls_diagnose_senden", "_tsx_wachhund", "_tsx_markiert", "_tsx_esc")}
    try:
        wf = Wf()
        ob._puls_fenster = lambda t: (wf, "gemerkt", "")
        ob._tv_fenster_rect = lambda w_: (0, 0, 2560, 1381)
        ob._dpi_bewusst = lambda: None
        ob._warte = lambda a, b: None
        ob._tsx_seite = lambda w_: (0, 109, 2560, 1381)
        ob._puls_diagnose_senden = lambda *a, **k: None
        ob._tsx_wachhund = lambda *a, **k: None
        ob._tsx_esc = lambda: z.update(offen=False)
        ob._tv_uia_roh = roh_f
        ob._tv_uia_klick = klick
        ob._tsx_markiert = lambda w_: ([f"$150K TRADING COMBINE | {z['konto']}"] if z["offen"] else [])
        b = io.StringIO()
        with contextlib.redirect_stdout(b):
            ob.modus_tsxlesen({"konto": "150KTC-SKU-V2-000000-20000000"})
        r = _j.loads(b.getvalue().strip().splitlines()[-1])
        chk("Trockenlauf zwei TRADING COMBINE, BAL gleich: markierter Eintrag beweist, Balance gelesen",
            r.get("ok") and "markierter Listeneintrag = Ziel-ID" in r.get("trail", "") and r.get("balance") == 154504.88)
        z.update(konto="150KTC-SKU-V2-000000-20000000", offen=False)
        b = io.StringIO()
        with contextlib.redirect_stdout(b):
            ob.modus_tsxlesen({"konto": "150KTC-SKU-V2-000000-20000000"})
        r2 = _j.loads(b.getvalue().strip().splitlines()[-1])
        chk("Ziel stand schon (markiert vorher) → kein Klick auf den Eintrag", r2.get("ok") and "schon ausgewählt" in r2.get("trail", "")
            and "Klick Konto 150KTC" not in r2.get("trail", ""))
    finally:
        for k, v in orig.items():
            setattr(ob, k, v)
        if alt_mod is None:
            _s.modules.pop("pywinauto", None)
        else:
            _s.modules["pywinauto"] = alt_mod
    fk = ob.tsx_felder_kurz([("", (2100, 560, 2150, 600), "Edit", "1", None), ("Risk (~$)", (936, 800, 1177, 851), "Edit", "250", None),
                             ("", (940, 870, 956, 890), "CheckBox", "", 1), ("kaputt", None, "Edit", "", None)])
    chk("Inventar v2: unbenanntes Mengenfeld + Wert, Haken-Zustand, kaputtes raus",
        fk == [["", "Edit", [2100, 560, 2150, 600], "1", None], ["Risk (~$)", "Edit", [936, 800, 1177, 851], "250", None],
               ["", "CheckBox", [940, 870, 956, 890], "", 1]])
    if ok:
        print("✓ TSX-Beweis: Label aus Nachbarknoten, markierter Eintrag vorher/nachher, Reihenfolge ID → markiert → Label+BAL")
    return ok



def test_tsx_order():
    """B26 Etappe 2 (27.09.2026): Order in TopstepX — Trockenlauf mit Inventar-Rechtecken von ID A. Probe endet vor dem Knopf
    (Brackets/Contract/Menge gesetzt, kein Order-Klick), scharf klickt genau den Panel-Knopf, Riegel bei offener Position."""
    import order_bot as ob, io, contextlib, json as _j
    ok = True

    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ TSX-Order: " + name); ok = False

    # reine Teile
    b, f = ob.tsx_order_befehl({"ext_id": "150KTC-SKU-V2-000000-20000000", "symbol": "MNQ1!", "richtung": "BUY", "volumen": 2, "tp_usd": 400})
    chk("Befehl gültig", b and b["wurzel"] == "MNQ" and b["menge"] == 2 and b["brackets"] == {"profit": "400", "risk": ""} and b["scharf"] is False)
    chk("scharf nur bei echtem true", ob.tsx_order_befehl({"ext_id": "12345X", "symbol": "NQ", "richtung": "sell", "volumen": 1, "tp_usd": 50, "scharf": "true"})[0]["scharf"] is False)
    chk("Menge 1.5 / Symbol ES / ohne TP abgelehnt", ob.tsx_order_befehl({"ext_id": "12345X", "symbol": "NQ", "richtung": "buy", "volumen": 1.5, "tp_usd": 5})[0] is None
        and ob.tsx_order_befehl({"ext_id": "12345X", "symbol": "ES1!", "richtung": "buy", "volumen": 1, "tp_usd": 5})[0] is None
        and ob.tsx_order_befehl({"ext_id": "12345X", "symbol": "NQ", "richtung": "buy", "volumen": 1})[0] is None)
    lad = [("BUY +1 @ MARKET", (500, 684, 640, 718), "Button"), ("BUY +1 @ MARKET", (2094, 684, 2249, 718), "Button")]
    chk("Order-Knopf nur im Panel (DOM-Leiter ignoriert)", ob.tsx_order_knopf(lad, "buy", 1, 1917) == lad[1] and ob.tsx_order_knopf(lad, "buy", 1, 0) is None)
    felder = [("", (1976, 410, 2100, 440), "Edit", "1", None), ("Risk (~$)", (936, 800, 1177, 851), "Edit", "", None)]
    chk("Mengenfeld unter „# of Contracts\"", ob.tsx_feld_zu_label(felder, (1976, 389, 2100, 405)) == felder[0])
    hk = [("", (935, 873, 951, 889), "CheckBox", None, 0), ("", (1500, 873, 1516, 889), "CheckBox", None, 1)]
    chk("Haken neben „Automatically apply\"", ob.tsx_haken_zu_text(hk, (957, 872, 1296, 891)) == hk[0])

    # Trockenlauf
    def lauf(befehl_cmd, pos_offen=False, typ="Order Type Market", haken=0, markt=False, nach="pos", tabelle=False):
        z = {"dialog": False, "profit": "250", "risk": "100", "haken": haken, "contract": "NQZ26", "menge": 1, "pos": pos_offen, "klicks": []}

        def roh(w, typen=None):
            r = [("Contract", (1977, 278, 2448, 314), "ComboBox"), (typ, (1977, 330, 2448, 366), "ComboBox"),
                 ("# of Contracts", (1976, 389, 2040, 403), "Text"), ("Decrease quantity", (2108, 567, 2135, 594), "Button"),
                 ("1", (2157, 567, 2184, 594), "Button"), ("1", (2167, 572, 2174, 588), "Text"), ("5", (2223, 567, 2250, 594), "Button"),
                 ("Increase quantity", (2338, 567, 2365, 594), "Button"),
                 ("Position Bracket Enabled", (1977, 580, 2370, 616), "ComboBox"), ("Manage brackets", (2383, 623, 2413, 653), "Button"),
                 (f"BUY +{z['menge']} @ MARKET", (2094, 684, 2249, 718), "Button"), (f"SELL -{z['menge']} @ MARKET", (2260, 684, 2440, 718), "Button"),
                 ("BUY +1 @ MARKET", (500, 684, 640, 718), "Button"), ("CLOSE POSITION", (2094, 730, 2440, 760), "Button")]
            if not z["pos"]:
                r.append(("No Active Position", (2100, 800, 2300, 820), "Text"))
            if markt:
                r.append(("Market closed", (2094, 740, 2440, 770), "Button"))
            if z.get("toast"):
                r.append(("Order rejected: Market is closed", (2000, 1200, 2440, 1240), "Text"))
            if tabelle:
                r += [("Positions X", (194, 1056, 281, 1092), "TabItem"), ("Positions X", (196, 1061, 261, 1088), "TabItem"),
                      ("Orders X", (292, 1056, 360, 1092), "TabItem"), ("Orders X", (294, 1061, 341, 1088), "TabItem")]
                kopf = [("Contract", (86, 1095, 300, 1124)), ("Side", (300, 1095, 400, 1124)), ("Type", (400, 1095, 500, 1124)),
                        ("Status", (500, 1095, 700, 1124)), ("Price", (700, 1095, 850, 1124)), ("Reason", (850, 1095, 1400, 1124))]
                r.append(("Contract Side Type Status Price Reason", (86, 1095, 2552, 1124), "DataItem"))
                r += [(n, q, "DataItem") for n, q in kopf]
                reihen = [["MNQZ26", "Buy", "Market", "Filled", "30900.00", ""]]
                if z.get("rej"):
                    reihen.insert(0, ["MNQZ26", "Buy", "Market", "Rejected", "", "Market is closed"])
                for i, werte in enumerate(reihen):
                    y = 1130 + 30 * i
                    r += [(v, (q[0] + 4, y, q[2] - 4, y + 24), "DataItem") for v, (_n, q) in zip(werte, kopf) if v]
            if z["dialog"]:
                r += [("Position Brackets close", (906, 577, 1654, 658), "Text"), ("close", (1601, 587, 1644, 630), "Button"),
                      ("Automatically apply Risk / Profit bracket to new Positions", (957, 872, 1296, 891), "Text")]
            if z["contract"].startswith("mnq"):
                r.append(("MNQZ26 · Micro E-mini Nasdaq-100 (Dec 2026)", (1977, 320, 2448, 350), "ListItem"))
            return [e for e in r if not typen or e[2] in typen]

        def fld(w):
            r = [("Contract", (1977, 278, 2448, 314), "ComboBox", z["contract"], None), ("", (1976, 410, 2100, 440), "Edit", str(z["menge"]), None)]
            if z["dialog"]:
                r += [("Risk (~$)", (936, 800, 1177, 851), "Edit", z["risk"], None), ("Profit (~$)", (1197, 800, 1438, 851), "Edit", z["profit"], None),
                      ("", (935, 873, 951, 889), "CheckBox", None, z["haken"])]
            return r

        def klick(e, name, trail):
            z["klicks"].append(name)
            if name.startswith("Manage brackets"): z["dialog"] = True
            elif name == "Bracket-Dialog schließen": z["dialog"] = False
            elif name.startswith("Haken"): z["haken"] = 1
            elif name.startswith("Contract "): z["contract"] = "MNQZ26"
            elif name.startswith("Order senden"):
                if nach == "pos": z["pos"] = True
                elif nach == "toast": z["toast"] = True
                elif nach == "orders_rej": z["rej"] = True
            elif name.startswith("Schnellknopf "): z["menge"] = int(name.split()[-1])
            elif name == "Increase quantity": z["menge"] += 1

        def tippen(feld, text, trail, name, ist=None, liste_ok=False, **_kw):   # **_kw: klick/versuche (B36)
            if ist is not None and ob.tsx_wert_gleich(ist, text):
                return True
            z["klicks"].append("tippe " + name)
            key = {"Profit": "profit", "Risk": "risk", "Contract": "contract"}.get(name)
            if key: z[key] = str(text)
            elif name == "# of Contracts": z["menge"] = int(text)
            return True
        alt = {k: getattr(ob, k) for k in ("_tsx_seite_roh", "_tsx_felder", "_tsx_klick", "_tsx_tippen", "_warte", "_puls_diagnose_senden", "_tsx_esc", "_tv_uia_klick")}
        ob._tv_uia_klick = lambda ziel, name, trail: z["klicks"].append(name) or trail.append(name + " geklickt")
        ob._tsx_seite_roh, ob._tsx_felder, ob._tsx_klick, ob._tsx_tippen = roh, fld, klick, tippen
        ob._warte = lambda *a, **k: None
        ob._puls_diagnose_senden = lambda *a, **k: None
        ob._tsx_esc = lambda: z.update(dialog=False)
        try:
            befehl, _f = ob.tsx_order_befehl(befehl_cmd)
            res = {"position": None if pos_offen else "keine", "balance": 150000.0}
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                ob._tsx_order_nach_kopf(befehl)(object(), res, [])
            return _j.loads(buf.getvalue().strip().splitlines()[-1]), z
        finally:
            for k, v in alt.items():
                setattr(ob, k, v)

    cmd = {"ext_id": "150KTC-SKU-V2-000000-20000000", "symbol": "MNQ1!", "richtung": "buy", "volumen": 2, "tp_usd": 400, "sl_usd": None}
    r, z = lauf(cmd)
    chk(f"Probe: ok/probe/nicht gesendet ({r.get('code')}: {r.get('msg')})", r.get("ok") and r.get("schritt") == "probe" and r.get("gesendet") is False)
    chk("Probe: Brackets 400/leer, Haken an, MNQ, Menge 2", z["profit"] == "400" and z["risk"] == "" and z["haken"] == 1
        and z["contract"] == "MNQZ26" and z["menge"] == 2 and not z["dialog"])
    chk("Probe: kein Order-Klick", not any(k.startswith("Order senden") for k in z["klicks"]))
    chk("B30: Menge 2 = Schnellknopf 1 + 1× Increase, kein Tippen", "Schnellknopf 1" in z["klicks"] and z["klicks"].count("Increase quantity") == 1
        and "tippe # of Contracts" not in z["klicks"])
    chk("B30: Haken-Zustand vorher in der Spur", "war aus → geklickt → an" in r.get("trail", ""))
    chk("B33: Kontrolle nach Wiederöffnen in der Spur", "Haken nach Wiederöffnen: an" in r.get("trail", "") and r.get("haken_kontrolle") == "an"
        and z["klicks"].count("Manage brackets (Kontrolle Haken)") == 1 and not z["dialog"])
    chk("Probe: Rücklesung in der Spur", "Brackets zurückgelesen" in r.get("trail", ""))
    r, z = lauf(dict(cmd, scharf=True, sl_usd=150), haken=1)
    chk(f"Scharf: gesendet + Position steht ({r.get('code')}: {r.get('msg')})", r.get("ok") and r.get("gesendet") is True and r.get("schritt") == "fertig"
        and r.get("retry_ok") is False and z["risk"] == "150")
    chk("Scharf: genau ein Order-Klick", sum(k.startswith("Order senden") for k in z["klicks"]) == 1)
    r, z = lauf(dict(cmd, scharf=True), pos_offen=True)
    chk("Offene Position: Riegel, kein Klick", r.get("code") == "position" and not z["klicks"])
    r, z = lauf(cmd, haken=None)
    chk(f"B30: Haken unlesbar, Probe → nicht angefasst, weiter ({r.get('code')})", r.get("ok") and "nicht angefasst" in r.get("trail", "")
        and not any(k.startswith("Haken") for k in z["klicks"]))
    r, z = lauf(dict(cmd, scharf=True), haken=None)
    chk("B30: Haken unlesbar, scharf → ENDE, kein Order-Klick", r.get("code") == "bracket" and not any(k.startswith("Order senden") for k in z["klicks"]))
    r, z = lauf(cmd, haken=1)
    chk("B30: Haken schon an → nicht angefasst", r.get("ok") and "war schon an" in r.get("trail", "") and not any(k.startswith("Haken") for k in z["klicks"]))
    chk("B30: Soll-Wert steht → nichts tippen", ob.tsx_wert_gleich("", "") and ob.tsx_wert_gleich("12.00", "12") and not ob.tsx_wert_gleich("100", ""))
    chk("B30: Fokus-Beweis", ob.tsx_fokus_passt(("Edit", (940, 805, 1170, 845)), (936, 800, 1177, 851))
        and not ob.tsx_fokus_passt(("Document", (0, 0, 2560, 1400)), (936, 800, 1177, 851))
        and not ob.tsx_fokus_passt(("Edit", (1200, 805, 1430, 845)), (936, 800, 1177, 851)) and not ob.tsx_fokus_passt(None, (1, 1, 2, 2)))
    cbr = (1977, 278, 2448, 314)
    chk("B32: Contract-Suche — Fokus = ListItem der Liste unter dem Feld gilt", ob.tsx_fokus_passt(("ListItem", (1977, 318, 2448, 350)), cbr, True)
        and not ob.tsx_fokus_passt(("ListItem", (1977, 318, 2448, 350)), cbr)
        and not ob.tsx_fokus_passt(("ListItem", (500, 318, 900, 350)), cbr, True)
        and not ob.tsx_fokus_passt(("ListItem", (1977, 100, 2448, 130)), cbr, True))
    import sys as _s2, types as _t2
    tasten = []
    pw_alt = _s2.modules.get("pywinauto")
    pw = _t2.ModuleType("pywinauto"); pw.keyboard = _t2.SimpleNamespace(send_keys=lambda k, **kw: tasten.append(k)); _s2.modules["pywinauto"] = pw
    alt2 = {k: getattr(ob, k) for k in ("_uia_fokus", "_tsx_klick", "_warte", "_uia_tastatur_im_feld")}
    ob._uia_fokus = lambda: ("ListItem", (1977, 318, 2448, 350))
    ob._tsx_klick = lambda e, n, t: t.append(n + " geklickt")
    ob._warte = lambda *a, **k: None
    ob._uia_tastatur_im_feld = lambda r: False
    try:
        sp2 = []
        li = [(f"6{c}Z26", (1977, 320 + 32 * i, 2448, 350 + 32 * i), "ListItem") for i, c in enumerate("ABCD")]
        g1 = ob._tsx_tippen(("Contract", cbr, "ComboBox", "MNQZ26", None), "nq", sp2, "Contract", liste_ok=lambda: li)
        g0 = ob._tsx_tippen(("Contract", cbr, "ComboBox", "MNQZ26", None), "nq", [], "Contract", liste_ok=lambda: li[:2])
        t1 = list(tasten); tasten.clear()
        g2 = ob._tsx_tippen(("Risk (~$)", (936, 800, 1177, 851), "Edit", "100", None), "", [], "Risk", ist="100")
        t2 = list(tasten)
    finally:
        for k, v in alt2.items():
            setattr(ob, k, v)
        if pw_alt is not None: _s2.modules["pywinauto"] = pw_alt
        else: _s2.modules.pop("pywinauto", None)
    chk(f"B33: Contract mit offener Vorschlagsliste getippt, ohne Liste nicht ({t1})", g1 and "nq" in t1
        and any("Vorschlagsliste offen" in x for x in sp2) and g0 is False)
    chk(f"B32: Risk bei ListItem-Fokus NICHT getippt ({t2})", g2 is False and not t2)
    mp = ob.tsx_menge_plan
    chk("B30: Mengen-Plan", mp(2, [1, 3, 5, 10, 15]) == (1, 1) and mp(15, [1, 3, 5, 10, 15]) == (15, 0) and mp(7, [1, 3, 5, 10, 15]) == (5, 2)
        and mp(30, [1, 3, 5, 10, 15]) is None and mp(1, []) is None)
    ml = ob.tsx_mengen_leiste([("Decrease quantity", (2108, 567, 2135, 594), "Button"), ("1", (2157, 567, 2184, 594), "Button"),
                               ("1", (500, 100, 520, 120), "Button"), ("Increase quantity", (2338, 567, 2365, 594), "Button")], 1917)
    chk("B30: Mengen-Leiste nur in der ±-Zeile", list(ml["schnell"].keys()) == [1] and ml["plus"] is not None)
    chk("B30: Mengenfeld in der ±-Zeile", ob.tsx_mengenfeld([("", (1977, 565, 2100, 596), "Edit", "1", None)], ml)[1] == (1977, 565, 2100, 596))
    r, z = lauf(dict(cmd, scharf=True), markt=True, nach="toast", haken=1)
    chk(f"B31: Markt zu + scharf → Klick → abgelehnt ({r.get('code')}: {r.get('msg')})", r.get("code") == "abgelehnt" and r.get("gesendet") is True
        and r.get("retry_ok") is False and "Market is closed" in r.get("msg", "") and sum(k.startswith("Order senden") for k in z["klicks"]) == 1)
    r, z = lauf(dict(cmd, scharf=True), markt=True, nach="nichts", haken=1)
    chk(f"B31: Markt zu, keine Meldung, keine Position → beweis ({r.get('msg')})", r.get("code") == "beweis" and "vermutlich abgelehnt" in r.get("msg", ""))
    r, z = lauf(dict(cmd, scharf=True), haken=0)
    chk(f"B33-Korrektur: scharf + „war aus\" → Haken geklickt, Order gesendet ({r.get('code')})", r.get("ok") and r.get("gesendet")
        and "war aus → geklickt → an" in r.get("trail", ""))
    feldc = (1977, 278, 2448, 314)
    alt_li = [("CLX26 · Crude", (1977, 5000, 2448, 5030), "ListItem")]
    neu_li = alt_li + [(f"6{c}Z26", (1977, 320 + 32 * i, 2448, 350 + 32 * i), "ListItem") for i, c in enumerate("ABCD")]
    chk("B33: neue Vorschlagsliste unter dem Feld gezählt", ob.tsx_liste_neu(alt_li, neu_li, feldc) == 4 and ob.tsx_liste_neu(neu_li, neu_li, feldc) == 0)
    chk("B33: Bot-Stand in der Spur", ob.puls_bot_stand().startswith("Bot ") and "Datei " in ob.puls_bot_stand())
    r, z = lauf(dict(cmd, scharf=True), markt=True, nach="orders_rej", haken=1, tabelle=True)
    chk(f"B35: Orders-Reiter → neue Zeile Rejected → abgelehnt mit Grund ({r.get('code')}: {r.get('msg')})", r.get("code") == "abgelehnt"
        and "Market is closed" in r.get("msg", "") and "Reiter Orders" in z["klicks"] and r.get("gesendet") is True)
    rt = [e for e in []]
    kopf_t = [("Contract", (86, 1095, 300, 1124), "DataItem"), ("Avg Price", (300, 1095, 500, 1124), "DataItem"),
              ("Contract Avg Price", (86, 1095, 2552, 1124), "DataItem"), ("MNQZ26", (90, 1130, 296, 1154), "DataItem"),
              ("30,921.75", (304, 1130, 496, 1154), "DataItem")]
    kp, zz = ob.tsx_tabelle_lesen(kopf_t, 1090)
    chk(f"B35: Tabelle lesen ({kp}, {zz})", kp == ["Contract", "Avg Price"] and zz == [{"Contract": "MNQZ26", "Avg Price": "30,921.75"}])
    ou = ob.tsx_orders_urteil
    chk("B35: Orders-Urteil", ou([], [{"Status": "Rejected", "Reason": "Outside trading hours"}]) == ("abgelehnt", "Rejected: Outside trading hours")
        and ou([{"Status": "Filled"}], [{"Status": "Filled"}]) == (None, None) and ou([], [{"Status": "Filled", "Side": "Buy"}])[0] == "gefuellt")
    lv = ob.tsx_levels([{"Contract": "MNQZ26", "Avg Price": "30,921.75"}],
                       [{"Contract": "MNQZ26", "Type": "Limit", "Status": "Working", "Price": "30,927.75"},
                        {"Contract": "MNQZ26", "Type": "Stop", "Status": "Working", "Price": "30,800.00"},
                        {"Contract": "NQZ26", "Type": "Limit", "Status": "Working", "Price": "1.00"}], "MNQZ26")
    chk(f"B35: Levels aus Positions/Orders ({lv})", lv == {"einstieg": 30921.75, "tp_level": 30927.75, "sl_level": 30800.0})
    lv2 = ob.tsx_levels([{"Contract": "MNQZ26", "Avg Price": "30,921.75"}], [], "NQZ26")
    chk("B35: NQZ26 trifft nie MNQZ26", lv2["einstieg"] is None)
    ab = ob.tsx_ablehnung
    chk("B31: Ablehnung nur als neuer Text", ab(["Market closed", "BUY +1 @ MARKET"], ["Market closed", "Order rejected: Market is closed"])
        == "Order rejected: Market is closed" and ab(["Market closed"], ["Market closed"]) is None
        and ab([], ["Outside trading hours"]) == "Outside trading hours" and ab([], ["BUY +1 @ MARKET"]) is None)
    r, z = lauf(cmd, typ="Order Type Limit")
    chk("Order-Typ Limit: Riegel", r.get("code") == "ordertyp" and not z["klicks"])
    # B29 (ID A 16:04 UTC): ComboBox heißt nur „Order Type" — unlesbar = weiter, Knopf-Beweis entscheidet
    r, z = lauf(cmd, typ="Order Type")
    chk(f"B29: nur „Order Type\" → Probe läuft durch ({r.get('code')}: {r.get('msg')})", r.get("ok") and r.get("schritt") == "probe"
        and "Order-Typ unlesbar" in r.get("trail", ""))
    fw = ob.tsx_feld_wert
    box = [("Order Type", (1977, 330, 2448, 366), "ComboBox"), ("Market", (1990, 338, 2060, 358), "Text")]
    chk("B29: Wert als Knoten im Feld", fw("Order Type", box) == ("Market", "im_feld"))
    chk("B29: Wert unter der Beschriftung", fw("Order Type", [("Order Type", (1977, 320, 2080, 336), "Text"), ("Limit", (1980, 345, 2040, 362), "Text")])[0] == "Limit")
    chk("B29: Wert aus ValuePattern", fw("Contract", [], [("Contract", (1, 1, 9, 9), "ComboBox", "MNQZ26", None)]) == ("MNQZ26", "value"))
    chk("B29: Name mit Wert", fw("Position Bracket", [("Position Bracket Enabled", (1, 1, 9, 9), "ComboBox")]) == ("Enabled", "name"))
    chk("B29: nichts lesbar", fw("Order Type", [("Order Type", (1977, 330, 2448, 366), "ComboBox")]) == (None, None))
    if ok:
        print("✓ TSX-Order: Befehl, Mengenfeld, Haken, Panel-Knopf, Probe bis vor den Knopf, scharf mit Nachher-Beweis, Riegel")
    return ok



def test_tsx_login():
    """B27 (27.09.2026, ID A): TopstepX-Login-Seite — nur bei vorausgefüllten Feldern EIN Klick auf „PLATFORM LOGIN",
    nie tippen, Zugangsdaten nie in Spur/Inventar, leere Felder bzw. Fehlertext → ehrliches Ende 'login'."""
    import order_bot as ob
    ok = True

    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ TSX-Login: " + name); ok = False

    MAIL = "id-a.beispiel@example.com"
    knopf = ("PLATFORM LOGIN", (1100, 700, 1460, 750), "Button")
    f_user = ("Username", (1100, 520, 1460, 560), "Edit", MAIL, None, False)
    f_pw = ("Password", (1100, 600, 1460, 640), "Edit", "••••••••", None, True)
    L = ob.tsx_login_lage
    lg = L("https://topstepx.com/login", [knopf], [f_user, f_pw])
    chk("Login-Seite, beide gefüllt, Knopf eindeutig", lg["seite"] and lg["user"] and lg["pw"] and lg["knopf"] == knopf)
    chk("Seite auch ohne URL (Knopf + Passwortfeld)", L("", [knopf], [f_user, f_pw])["seite"])
    chk("Handelsseite ist keine Login-Seite", not L("https://topstepx.com/trade", [("BUY +1 @ MARKET", (1, 1, 9, 9), "Button")], [])["seite"])
    chk("Passwort leer → pw False", not L("topstepx.com/login", [knopf], [f_user, f_pw[:3] + ("", None, True)])["pw"])
    unb = [("", (1100, 520, 1460, 560), "Edit", MAIL, None, False), ("", (1100, 600, 1460, 640), "Edit", "•••", None, False)]
    lg = L("", [knopf], unb)
    chk("unbenannte Felder: die zwei Edits über dem Knopf", lg["seite"] and lg["user"] and lg["pw"])
    kurz = str(ob.tsx_felder_kurz([f_user, f_pw, ("", (1, 1, 5, 5), "Edit", MAIL, None, False), ("Profit (~$)", (1, 1, 5, 5), "Edit", "400", None)]))
    chk("Inventar maskiert Mail/Passwort, Profit bleibt", MAIL not in kurz and "••" not in kurz and "<25 Zeichen>" in kurz and "'400'" in kurz)

    def lauf(user_wert, pw_wert, nach_klick):
        z = {"seite": "login", "klicks": 0}
        spur = ob._StempelSpur()
        alt = {k: getattr(ob, k) for k in ("_tsx_ausloeser", "_chrome_url", "_tsx_seite_roh", "_tsx_felder", "_tsx_klick", "_warte", "_puls_diagnose_senden")}
        ob._tsx_ausloeser = lambda w: ("$150K TRADING COMBINE | 150KTC-X", (10, 10, 200, 30), "Button") if z["seite"] == "trade" else None
        ob._chrome_url = lambda w: "https://topstepx.com/" + z["seite"]
        ob._tsx_seite_roh = lambda w, typen=None: ([knopf] + ([("Invalid username or password", (1100, 660, 1460, 680), "Text")]
                                                             if z["seite"] == "fehler" else [])) if z["seite"] != "trade" else []
        ob._tsx_felder = lambda w: [f_user[:3] + (user_wert, None, False), f_pw[:3] + (pw_wert, None, True)] if z["seite"] != "trade" else []

        def klick(e, name, trail):
            z.setdefault("klick_uhr", uhr[0])
            z["klicks"] += 1
            trail.append(name)
            z["seite"] = nach_klick
        ob._tsx_klick = klick
        uhr = [1000.0]
        alt_time = ob.time
        ob._warte = lambda *a, **k: uhr.__setitem__(0, uhr[0] + 1.0)
        ob.time = type("Uhr", (), {"time": staticmethod(lambda: uhr[0]), "sleep": staticmethod(lambda x: None)})
        ob._puls_diagnose_senden = lambda *a, **k: None
        try:
            stand = {}
            ke = ob._tsx_warte_seite(object(), spur, 20.0, stand)
            return ke, stand, z, " > ".join(spur)
        finally:
            for k, v in alt.items():
                setattr(ob, k, v)
            ob._TSX_SEITE.clear()
            ob.time = alt_time

    ke, st, z, sp = lauf(MAIL, "••••••••", "trade")
    chk(f"B28: Klick ohne Feld-Wartezeit (Uhr {z.get('klick_uhr')})", z.get("klick_uhr", 99) <= 1002.0)
    chk(f"gefüllt → ein Klick → Handelsseite ({sp})", ke and z["klicks"] == 1 and not st.get("fehler") and "TopstepX-Login geklickt (Felder vorausgefüllt)" in sp)
    chk("Mail nie in der Spur", MAIL not in sp)
    ke, st, z, sp = lauf("", "", "trade")
    chk(f"per UIA leer (Chrome-Autofill) → nach Wartezeit EIN Klick → Handelsseite ({sp})", ke and z["klicks"] == 1
        and not st.get("fehler") and "Chrome-Autofill" in sp)
    ke, st, z, sp = lauf("", "", "login")
    chk(f"Klick ohne Erfolg → kein zweiter Klick, Ende 'login' ({st.get('fehler')})", ke is None and z["klicks"] == 1
        and st.get("fehler", ("",))[0] == "login" and "von Hand" in st["fehler"][1])
    ke, st, z, sp = lauf(MAIL, "••••", "fehler")
    chk(f"falsches Passwort → genau EIN Klick, Ende mit Fehlertext ({st.get('fehler')})", ke is None and z["klicks"] == 1
        and "Invalid username or password" in (st.get("fehler") or ("", ""))[1])
    if ok:
        print("✓ TSX-Login: Login-Seite erkannt, höchstens EIN Klick (auch bei Chrome-Autofill), abgelehnt → Ende 'login', Zugangsdaten maskiert")
    return ok




def test_tsx_bracket_b36():
    """B36 (30.09.2026, ID F pc-bbbbbb + ID A pc-aaaaaa): „Feld Risk geklickt → Fokus nicht im Feld Risk (Group)". Attrappe des
    Dialogs „Position Brackets" (Rechtecke von ID A): Edit vor Container gleichen Namens, frisches Rechteck nach Verschieben,
    Tab-Weg vom bewiesenen Profit-Feld, gesperrtes Feld, Umgebung in der Meldung — nie eine Taste ohne Fokus-Beweis."""
    import order_bot as ob, sys as _s, types as _t
    ok = True

    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ TSX-Bracket B36: " + name); ok = False

    RISK, PROF, DLG = (936, 800, 1177, 851), (1197, 800, 1438, 851), (906, 577, 1654, 910)
    # rein rechnend
    cont = ("Risk (~$)", (920, 790, 1190, 860), "ComboBox", "", None)
    edit = ("Risk (~$)", RISK, "Edit", "", None)
    chk("Edit vor Container gleichen Namens", ob.tsx_bracket_feld([cont, edit], "Risk") == edit
        and ob.tsx_bracket_feld([cont], "risk") == cont and ob.tsx_bracket_feld([], "Risk") is None)
    chk("Verschoben ±3 px", not ob.tsx_rect_verschoben(RISK, (937, 801, 1178, 852)) and ob.tsx_rect_verschoben(RISK, (936, 850, 1177, 901))
        and ob.tsx_rect_verschoben(None, RISK))
    chk("Tab-Richtung: Risk links von Profit = Shift+Tab, umgekehrt Tab", ob.tsx_tab_taste(PROF, RISK) == "+{TAB}"
        and ob.tsx_tab_taste(PROF, RISK, umgekehrt=True) == "{TAB}" and ob.tsx_tab_taste(RISK, PROF) == "{TAB}")
    chk("Fokus-Text", ob.tsx_fokus_text(("Group", DLG, "Position Brackets")) == "Group 'Position Brackets' @906,577,1654,910"
        and ob.tsx_fokus_text(("Edit", RISK)) == "Edit @936,800,1177,851" and ob.tsx_fokus_text(None) == "?")
    chk("Fokus-Beweis mit 3er-Tupel", ob.tsx_fokus_passt(("Edit", (940, 805, 1170, 845), "Risk (~$)"), RISK)
        and not ob.tsx_fokus_passt(("Group", DLG, "x"), RISK))
    roh_d = [("Position Brackets close", (906, 577, 1654, 658), "Text"), ("Risk (~$)", (953, 812, 1008, 831), "Text"),
             ("Automatically apply Risk / Profit bracket to new Positions", (957, 872, 1296, 891), "Text"), ("Chart", (0, 0, 800, 400), "Pane")]
    umg = ob.tsx_bracket_umgebung(roh_d, [("Risk (~$)", RISK, "Edit", "", None, False, False), ("Profit (~$)", PROF, "Edit", "33", None, False, True)], RISK)
    chk(f"Umgebung: Dialog-Elemente, gesperrt + Wert, Chart draußen ({umg})",
        any(u.startswith("Edit:'Risk (~$)'@936,800,1177,851 gesperrt") for u in umg) and any("='33'" in u for u in umg)
        and any(u.startswith("Text:'Position Brackets close'") for u in umg) and not any("Chart" in u for u in umg)
        and ob.tsx_bracket_umgebung(roh_d, [], None) == [])

    # Attrappe: Dialog mit Maus-/Tastatur-Zustand
    def lauf(risk_klick=True, tab="shift", verschiebt=0, gesperrt=None, risk_start="", mit_container=False, profit_start="250", schliesst=False):
        z = {"fokus": None, "risk": risk_start, "profit": profit_start, "tasten": [], "klicks": [], "dy": 0, "zu": False}

        def rr():
            return (RISK[0], RISK[1] + z["dy"], RISK[2], RISK[3] + z["dy"])

        def fld(w):
            if z["zu"]:
                return []                                  # Dialog nach dem Klick weg (ID A: 2. Klick traf das Dokument)
            r = []
            if mit_container:
                r.append(("Risk (~$)", (920, 790 + z["dy"], 1190, 860 + z["dy"]), "ComboBox", "", None))
            r += [("Risk (~$)", rr(), "Edit", z["risk"], None, False, gesperrt),
                  ("Profit (~$)", (PROF[0], PROF[1] + z["dy"], PROF[2], PROF[3] + z["dy"]), "Edit", z["profit"], None, False, True)]
            return r

        def klick(e, name, trail):
            x, y = (e[1][0] + e[1][2]) // 2, (e[1][1] + e[1][3]) // 2
            z["klicks"].append(name)
            trail.append(f"{name} geklickt @{x},{y}")
            pr = (PROF[0], PROF[1] + z["dy"], PROF[2], PROF[3] + z["dy"])
            if pr[0] <= x <= pr[2] and pr[1] <= y <= pr[3]:
                z["fokus"] = ("Edit", pr, "Profit (~$)")
            elif rr()[0] <= x <= rr()[2] and rr()[1] <= y <= rr()[3] and e[2] == "Edit" and risk_klick:
                z["fokus"] = ("Edit", rr(), "Risk (~$)")
            else:
                z["fokus"] = ("Group", DLG, "Position Brackets")
                if schliesst:
                    z["zu"] = True

        def tasten(k, **kw):
            z["tasten"].append(k)
            f = z["fokus"]
            if k in ("+{TAB}", "{TAB}"):
                if f and f[2] == "Profit (~$)" and ((k == "+{TAB}" and tab == "shift") or (k == "{TAB}" and tab == "tab")):
                    z["fokus"] = ("Edit", rr(), "Risk (~$)")
                else:
                    z["fokus"] = ("Button", (936, 677, 1154, 716), "Account must be fully flattened before switching")
                return
            key = {"Risk (~$)": "risk", "Profit (~$)": "profit"}.get(f[2]) if f and f[0] == "Edit" else None
            if not key:
                return
            if k == "{DELETE}":
                z[key] = ""
            elif k != "^a":
                z[key] += k
                if key == "profit" and verschiebt:
                    z["dy"] = verschiebt                  # Dialog schiebt sich nach dem Profit-Wert (Hypothese B36)

        pw_alt = _s.modules.get("pywinauto")
        pw = _t.ModuleType("pywinauto"); pw.keyboard = _t.SimpleNamespace(send_keys=tasten); _s.modules["pywinauto"] = pw
        alt = {k: getattr(ob, k) for k in ("_tsx_felder", "_tsx_klick", "_uia_fokus", "_warte", "_tsx_seite_roh", "_uia_tastatur_im_feld")}
        ob._tsx_felder, ob._tsx_klick, ob._uia_fokus = fld, klick, (lambda: z["fokus"])
        ob._warte = lambda *a, **k: None
        ob._tsx_seite_roh = lambda w, typen=None: roh_d
        ob._uia_tastatur_im_feld = lambda r: False
        sp = []
        try:
            erg = ob._tsx_brackets_tippen(object(), {"profit": "33", "risk": "12"}, sp)
        finally:
            for k, v in alt.items():
                setattr(ob, k, v)
            if pw_alt is not None: _s.modules["pywinauto"] = pw_alt
            else: _s.modules.pop("pywinauto", None)
        return erg, z, " > ".join(sp)

    (ok1, m1, u1), z1, sp1 = lauf(mit_container=True)
    chk(f"Risk-Container + Edit-Kind → Klick aufs Edit → getippt ({sp1})", ok1 and z1["risk"] == "12" and z1["profit"] == "33"
        and "Feld Risk geklickt @1056,825" in sp1 and "Feld Risk getippt: '12'" in sp1 and "Feld Profit getippt: '33'" in sp1)
    (ok2, m2, u2), z2, sp2 = lauf(risk_klick=False)
    chk(f"ID F-Fall: Maus trifft Risk nicht → Shift+Tab aus Profit → getippt ({sp2})", ok2 and z2["risk"] == "12"
        and "per Shift+Tab aus Feld Profit erreicht" in sp2 and "Fokus nicht im Feld Risk (Group 'Position Brackets'" in sp2
        and z2["tasten"].count("+{TAB}") == 1 and "{TAB}" not in z2["tasten"])
    (ok3, m3, u3), z3, sp3 = lauf(risk_klick=False, tab="tab")
    chk(f"Tab-Reihenfolge andersrum → zweiter Versuch mit Tab ({sp3})", ok3 and z3["risk"] == "12"
        and z3["tasten"].count("+{TAB}") == 1 and z3["tasten"].count("{TAB}") == 1 and "per Tab aus Feld Profit erreicht" in sp3)
    (ok4, m4, u4), z4, sp4 = lauf(risk_klick=False, tab="nie")
    chk(f"weder Klick noch Tab → Ende mit Fokus + Umgebung, Risk nie getippt ({m4})", not ok4 and z4["risk"] == ""
        and "Fokus: Button 'Account must be fully flattened" in m4 and "Umgebung: " in m4 and "Edit:'Risk (~$)'@936,800,1177,851" in m4
        and "12" not in z4["tasten"] and u4)
    (ok5, m5, u5), z5, sp5 = lauf(verschiebt=50)
    chk(f"Dialog verschiebt sich nach dem Profit-Wert → frisches Rechteck, Klick trifft ({sp5})", ok5 and z5["risk"] == "12"
        and "Feld Risk hat sich verschoben" in sp5 and "Feld Risk geklickt @1056,875" in sp5)
    (ok6, m6, u6), z6, sp6 = lauf(gesperrt=False)
    chk(f"Risk gesperrt → nie geklickt, klare Meldung ({m6})", not ok6 and "gesperrt" in m6 and "Feld Risk" not in " ".join(z6["klicks"])
        and z6["risk"] == "")
    (ok8, m8, u8), z8, sp8 = lauf(risk_klick=False, profit_start="33")
    chk(f"Prüfer-Befund: Profit steht schon auf 33, Risk-Klick trifft nicht → Shift+Tab aus Profit ({sp8})", ok8 and z8["risk"] == "12"
        and "Feld Profit steht schon" in sp8 and "per Shift+Tab aus Feld Profit erreicht" in sp8 and z8["tasten"].count("+{TAB}") == 1)
    (ok9, m9, u9), z9, sp9 = lauf(risk_klick=False, schliesst=True)
    chk(f"Dialog nach erstem Risk-Klick weg → kein zweiter Klick, Meldung ({m9})", not ok9 and z9["klicks"].count("Feld Risk") == 1
        and "nicht mehr im Dialog" in m9 and "12" not in z9["tasten"])
    (ok7, m7, u7), z7, sp7 = lauf(risk_start="12")
    chk(f"Risk steht schon auf 12 → kein Risk-Klick ({sp7})", ok7 and "Feld Risk steht schon" in sp7 and "Feld Risk" not in " ".join(z7["klicks"]))
    if ok:
        print("✓ TSX-Bracket B36: Edit vor Container, frisches Rechteck, Tab-Weg vom bewiesenen Profit-Feld (beide Richtungen), "
              "gesperrt/kein Fokus → Meldung mit Fokus + Umgebung, nie eine Taste ohne Beweis")
    return ok

def test_puls_heim():
    """B35 (27.09.2026, Finn): nach jedem Puls-Lauf zurück in den Prophos-Tab — nur wenn der Lauf den Vordergrund gewechselt
    hat, Prophos-Tab im Puls-Fenster anklicken (links der Mitte, nie das X), sonst Prophos-Fenster wie Echo; nie im Konto-
    Zwischenschritt der Kette."""
    import order_bot as ob
    ok = True

    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ Puls-Heim: " + name); ok = False

    w = ob.prophos_tab_wahl
    chk("Tab-Wahl", w(["NQZ26 $30,921.75 ▲", "Prophos"]) == 1 and w(["localhost:5000/prophos"]) == 0
        and w(["Prophos-Backend", "TradingView"]) is None and w(["DevTools - Prophos"]) is None and w([]) is None)

    class Tab:
        def __init__(s, n, r): s.n, s.r = n, r
        def window_text(s): return s.n
        def rectangle(s):
            import types
            return types.SimpleNamespace(left=s.r[0], top=s.r[1], right=s.r[2], bottom=s.r[3])

    class Fenster:
        def __init__(s): s.fokus = 0
        def window_text(s): return "NQZ26 $30,921.75 ▲ +0.50% - Google Chrome"
        def descendants(s, control_type=None): return [Tab("NQZ26 $30,921.75", (0, 0, 240, 40)), Tab("Prophos", (240, 0, 480, 40))]
        def set_focus(s): s.fokus += 1

    klicks = []
    alt = {k: getattr(ob, k) for k in ("_warte", "_maus_fahren", "_klick_absolut", "_zurueck_zu_prophos")}
    ob._warte = lambda *a, **k: None
    ob._maus_fahren = lambda x, y: None
    ob._klick_absolut = lambda x, y: klicks.append((x, y))
    ob._zurueck_zu_prophos = lambda: "Fenster-Weg"
    try:
        ob._PULS_HEIM.update(w=None, gewechselt=False, aus=False)
        f = Fenster()
        ob._puls_vorn_merken(f, "Prophos - Google Chrome")
        ob._puls_vorn_merken(Fenster(), "NQZ26 $1 - x")          # zweites Holen im Lauf ändert nichts
        h = ob._puls_heim()
        chk(f"Prophos-Tab angeklickt ({h}, {klicks})", h == "zurück zu Prophos (Tab Prophos)" and klicks == [(336, 20)])
        chk("nur einmal je Lauf", ob._puls_heim() is None)
        klicks.clear()
        ob._PULS_HEIM.update(w=None, gewechselt=False, aus=False)
        ob._puls_vorn_merken(Fenster(), "NQZ26 $30,921.75 ▲ +0.50% - Google Chrome")
        chk("TopstepX stand schon vorn → kein Heimweg", ob._puls_heim() is None and not klicks)
        ob._PULS_HEIM.update(w=None, gewechselt=False, aus=False)
        ob._puls_vorn_merken(Fenster(), "Prophos - Google Chrome")
        ob._PULS_HEIM["aus"] = True
        chk("im Konto-Zwischenschritt kein Heimweg", ob._puls_heim() is None)
        ob._PULS_HEIM["aus"] = False

        class OhneTab(Fenster):
            def descendants(s, control_type=None): return [Tab("NQZ26 $30,921.75", (0, 0, 240, 40))]
        ob._PULS_HEIM.update(w=None, gewechselt=False, aus=False)
        ob._puls_vorn_merken(OhneTab(), "Prophos - Google Chrome")
        chk("Prophos in anderem Fenster → Echo-Weg", ob._puls_heim() == "zurück zu Prophos (Fenster: Fenster-Weg)")
        res = {"trail": "a > b"}
        ob._PULS_HEIM.update(w=Fenster(), gewechselt=True, aus=False)
        ob._puls_heim_in(res)
        chk("Spur-Zeile an res['trail']", res["trail"].endswith(" > zurück zu Prophos (Tab Prophos)"))
    finally:
        for k, v in alt.items():
            setattr(ob, k, v)
        ob._PULS_HEIM.update(w=None, gewechselt=False, aus=False)
    if ok:
        print("✓ Puls-Heim: Prophos-Tab (links der Mitte) oder Fenster, nur nach eigenem Wechsel, einmal je Lauf, nie im Zwischenschritt")
    return ok



def test_tv_tp_orders():
    """Master 28.09.2026 (ID F …): TP-Limit aus dem Reiter „Orders", wenn der Toast-Stapel zu bleibt — Limit-Order mit
    Wurzel, Gegenseite und Menge, nicht gefüllt; Reiter mit Zähler („Orders 1") erkannt."""
    import order_bot as ob
    ok = True

    def chk(name, bed):
        nonlocal ok
        if not bed:
            print("✗ TV-TP-Orders: " + name); ok = False

    tab = ("Orders 1", (160, 1200, 240, 1220), "TabItem")
    kopf = [("Symbol", 60), ("Side", 200), ("Type", 300), ("Qty", 400), ("Limit Price", 480), ("Stop Price", 600),
            ("Fill Price", 720), ("Status", 840)]
    roh = [tab, ("Positions 1", (60, 1200, 150, 1220), "TabItem")] + [(n, (x, 1240, x + 90, 1258), "Text") for n, x in kopf]

    def zeile(y, werte):
        return [(v, (x, y, x + 90, y + 18), "Text") for v, (_n, x) in zip(werte, kopf) if v]
    roh += zeile(1270, ["MNQZ6", "Sell", "Limit", "4", "30,760.75", "", "", "Working"])
    roh += zeile(1300, ["MNQZ6", "Sell", "Market", "4", "", "", "30,794.75", "Filled"])
    k = ob.tv_tabelle_kopf_unter(roh, tab[1])
    w = ob.tv_tp_order_waehlen(roh, k, "MNQZ6", "buy", 4)
    chk(f"BUY 4 → Sell-Limit 30760.75 ({w})", w is not None and w["preis"] == 30760.75)
    chk("falsche Menge → None", ob.tv_tp_order_waehlen(roh, k, "MNQZ6", "buy", 2) is None)
    chk("gleiche Seite → None", ob.tv_tp_order_waehlen(roh, k, "MNQZ6", "sell", 4) is None)
    chk("andere Wurzel → None", ob.tv_tp_order_waehlen(roh, k, "ESZ6", "buy", 4) is None)
    roh2 = roh + zeile(1330, ["MNQZ6", "Sell", "Limit", "4", "30,770.00", "", "", "Working"])
    chk("zwei passende Limit → None", ob.tv_tp_order_waehlen(roh2, ob.tv_tabelle_kopf_unter(roh2, tab[1]), "MNQZ6", "buy", 4) is None)
    chk("Reiter mit Zähler", ob.TV_RX_ORDERS_TAB_N.search("Orders 1") and ob.TV_RX_POS_TAB_N.search("Positions 1")
        and ob.TV_RX_POS_TAB_N.search("Positions") and not ob.TV_RX_ORDERS_TAB_N.search("Order History"))
    if ok:
        print("✓ TV-TP-Orders: Limit-Order Wurzel/Gegenseite/Menge, eindeutig, Reiter mit Zähler")
    return ok


if __name__ == "__main__":
    sys.exit(main())
