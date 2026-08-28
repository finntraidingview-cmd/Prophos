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
                    plan_sltp, find_notfall_deals, read_snapshot)

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

    BASE = {"hedge_terminal_path": "C:\\MT5-Hedge\\terminal64.exe", "hedge_expected_login": 437804}

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
        [dict(BASE, _file="config.json", magic=770001, snapshot_file="a.csv", master_expected_login=437803),
         dict(BASE, _file="config-m2.json", magic=770002, snapshot_file="b.csv", master_expected_login=0)],
        expect_error_contains="master_expected_login"))

    # 21) Abweichendes Hedge-Terminal zwischen den Configs → Fehler
    results.append(fleet(
        "FLOTTE: unterschiedliche Hedge-Terminals → Abbruch-Fehler",
        [dict(BASE, _file="config.json", magic=770001, snapshot_file="a.csv", master_expected_login=1),
         {"_file": "config-m2.json", "magic": 770002, "snapshot_file": "b.csv",
          "master_expected_login": 2, "hedge_terminal_path": "C:\\ANDERES\\terminal64.exe",
          "hedge_expected_login": 437804}],
        expect_error_contains="hedge_terminal_path"))

    # 22) Saubere Zwei-Master-Flotte geht durch
    results.append(fleet(
        "FLOTTE: saubere Zwei-Master-Config → keine Fehler",
        [dict(BASE, _file="config.json", magic=770001, snapshot_file="a.csv", master_expected_login=437803),
         dict(BASE, _file="config-m2.json", magic=770002, snapshot_file="b.csv", master_expected_login=437873)],
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
                "hedge_expected_login": 437804, "master_expected_login": 437803,
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
            lambda: cfg["hedge_expected_login"] == 437804
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
        # Und end-zu-end an einem FRISCHEN Ordner (= Moritz' eigener PC, eigener
        # Ordner): der erste Account landet sauber im 771000er-Block mit PH.
        with tempfile.TemporaryDirectory() as td2:
            # Vorlage ohne magic/comment_prefix — genau wie die echte
            # config.vorlage.json (die ist kein Account).
            _json.dump({"hedge_expected_login": 488579,
                        "master_terminal_path": "C:\\MT5-Master\\terminal64.exe",
                        "magic_base": 771000},
                       open(os.path.join(td2, "config.vorlage.json"), "w"))
            ident_block1 = provision.alloc_identity(td2, "moritz1", magic_base=771000)
        results.append(prov(
            "PROVISION: magic_base verschiebt den Block; frischer PC → magic 771001, Praefix PH",
            lambda: magic_base_logik
                    and ident_block1 == {"magic": 771001, "prefix": "PH",
                                         "snapshot": "prophos_master_moritz1.csv"}))

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
        and not order_bot.ist_prophos_fenster("437803: FTMO-Demo", order_bot.MT5_KLASSE))
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
            f.write("PROPHOS1;7;123;437803;Srv;2;1;10000.00;10000.00;USD;1\n"
                    "P;101;NAS100;0;1.00000000;1.00000000;20000.00000000;19900.00000000;20200.00000000\n"
                    "END;7;1\n")
        _alt = os.path.join(_td, "alt.csv")
        with open(_alt, "w") as f:
            f.write("PROPHOS1;3;123;437803;Srv;2;1\n"
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

    print()
    ok = sum(1 for r in results if r)
    print(f"{ok}/{len(results)} Tests bestanden")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
