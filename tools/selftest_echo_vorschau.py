#!/usr/bin/env python3
"""Selbsttest ECHO-HEDGE-VORSCHAU (app.py ehv_vorschau / ehv_abweichung / ehv_tick, 30.10.2026): Vorschau für alle geplanten HT-CFD-Auto-Pläne
auf Echo V2 mit derselben Rechnung wie eh_tick (eh_hedge), ohne Umstellen, ohne hedge_art; neu nur bei > 1 %; Spur bei > 5 % Abweichung.
Nutzt die nachgebaute Datenbank aus selftest_echo_hedge. Aufruf: python3 tools/selftest_echo_vorschau.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_echo_hedge as EH   # noqa: E402

APP = os.path.join(os.path.dirname(HIER), "app.py")


def tfh_vorschau_neu():
    src = open(APP, encoding="utf-8").read()
    i = src.index("\ndef tfh_vorschau_neu(") + 1
    ns = {"_wd_num": EH._wd_num}
    exec(src[i:src.find("\n\n\n", i)], ns)
    return ns["tfh_vorschau_neu"]


def main():
    f = []
    ok = lambda b, t: f.append(t) if not b else None   # noqa: E731
    ns = EH.lade()
    v = ns["ehv_vorschau"]
    h = {"lots": 1.18, "multiplier": 0.059, "q": 0.05011, "slave_risk": 50.11}
    ok(v(h, None, 1500, "t") == {"lots": 1.18, "multiplier": 0.059, "q": 0.05011, "blow_eur": 50.11, "pass_eur": -75.17, "at": "t"}, f"Vorschau {v(h, None, 1500, 't')}")
    ok(v(h, None, None, "t")["pass_eur"] is None, "ohne TP → pass leer")
    ok(v(None, "kein Satz", 1500, "t") == {"grund": "kein Satz", "at": "t"}, "Grund")
    ab = ns["ehv_abweichung"]
    ok(ab({"lots": 1.18}, 1.20) is None and ab({"lots": 1.18}, 1.18) is None, "≤ 5 % → still")
    ok("Vorschau 1,18 Lot, umgestellt 1,30 Lot (+10 %)" == ab({"lots": 1.18}, 1.30), f"> 5 % → Text ({ab({'lots': 1.18}, 1.30)})")
    ok(ab(None, 1.2) is None and ab({"grund": "x"}, 1.2) is None, "ohne Vorschau → still")

    # Takt mit nachgebauter DB (wie selftest_echo_hedge)
    jetzt = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    iso = lambda m: (jetzt + timedelta(minutes=m)).isoformat()   # noqa: E731
    plan = lambda pid, acc, uid, m, **x: dict({"id": pid, "user_id": uid, "master_account_id": acc, "master_name": pid, "master_firm": "FTMO",   # noqa: E731
                                                "master_contracts": 20, "master_risk": 1000, "master_tp": 1500, "richtung": "buy", "start_um": iso(m),
                                                "notes": "", "mt5_baseline": None, "status": "planned", "route": "mt5v2",
                                                "auto_plan": True, "auto_bestaetigt_at": None, "updated_at": "t0"}, **x)
    plaene = [plan("P1", "A1", "U1", 300), plan("P2", "A1", "U1", 600, auto_bestaetigt_at="b"), plan("P4", "A2", "U1", 10),
              plan("P5", "A3", "UE", 10), plan("P6", "A4", "U2", 12), plan("P7", "A1", "U1", 11, start_um_gestartet_at="x"),
              plan("P8", "A1", "U1", 12, hand_werte_at="x"), plan("P9", "A1", "U1", 13, mt5_baseline={"tage_mini": {"tag": "x"}})]
    regeln = {"echo_hedge": {"an": True}, "firmen": [{"namen": ["ftmo"], "route": "mt5v2"}, {"namen": ["tradeify"], "route": "tvv2"}]}
    db = EH.DB(plaene, regeln)
    spur = []
    ns = EH.lade({
        "sb_select": db.sb_select, "_sb_all": db._sb_all, "sb_update": db.sb_update, "_wt_now_iso": lambda: "2026-10-29T12:00:00+00:00",
        "_ap_namen": lambda: ({"U1": "Mike", "U2": "Ina", "UE": "Emin"}, set()), "gp_verwalter_karte": lambda: {"UE": "UE"},
        "AP_KONTO_FELDER": "id", "GP_HEDGE_KEY": "echo_hedge_account", "GP_SLAVE_PPL": 0.85,
        "ap_ppl_karte": lambda rows, norm=None: ({}, {}), "_ap_norm": lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower()),
        "_firm_norm": lambda s: s, "_ap_balance_karten": lambda: ({}, {}), "_ap_kauf_echt": lambda ids: {},
        "ap_regel_finden": lambda firmen, fi: next((r for r in firmen if re.sub(r"[^a-z0-9]", "", fi.lower()) in r["namen"]), None),
        "acc_balance_wahl": lambda a, e, d: (100000.0, "USD", "Echo", ""),
        "ap_kontowert_konto": lambda a, bal, firmen, kauf=None: {"satz_eur_pro_usd": 0.0446, "wert_eur": 446.0},
        "ap_cfd_ppl": lambda ctx, a: 1.0, "tfh_vorschau_neu": tfh_vorschau_neu()})
    ns["_eh_spur"] = lambda t: spur.append(t)
    erg = ns["ehv_tick"](jetzt=jetzt, force=True)
    um = {pid: u for pid, u in db.updates}
    vs = lambda pid: next(p for p in plaene if p["id"] == pid)["mt5_baseline"]["hedge_vorschau"]   # noqa: E731
    ok("P1" in um and "P2" in um, "unbestätigt UND bestätigt, auch weit in der Zukunft → Vorschau")
    ok(vs("P1")["lots"] == 1.18 and vs("P1")["blow_eur"] == 50.11 and vs("P1")["pass_eur"] == round(-1500 * vs("P1")["q"], 2),
       f"gleiche Zahlen wie eh_tick (1,18 Lot, slave_risk 50,11) {vs('P1')}")
    p1 = next(p for p in plaene if p["id"] == "P1")
    ok(p1["route"] == "mt5v2" and not p1.get("slave_account_id") and "hedge_art" not in p1["mt5_baseline"], "nicht umgestellt, keine hedge_art")
    ok(all(set(u) == {"mt5_baseline"} for u in um.values()), "schreibt nur mt5_baseline")
    ok("kein Echo-Hedge-Konto" in vs("P6").get("grund", ""), "ID ohne Fusion-Konto → Grund")
    ok(not ({"P4", "P5", "P7", "P8", "P9"} & set(um)), "Futures, Verwalter-Gruppe, geclaimt, Hand-Werte, Tage-Mini → nicht angefasst")
    ok(erg == {"geschrieben": 3}, f"Ergebnis {erg}")
    n = len(db.updates)
    ns["ehv_tick"](jetzt=jetzt, force=True)
    ok(len(db.updates) == n, "zweiter Takt, gleiche Zahlen → nichts geschrieben")
    # Echo-Hedge aus → keine Vorschau
    db2 = EH.DB([plan("Q1", "A1", "U1", 300)], {"echo_hedge": {"an": False}, "firmen": regeln["firmen"]})
    ns.update({"sb_select": db2.sb_select, "_sb_all": db2._sb_all, "sb_update": db2.sb_update})
    ok(ns["ehv_tick"](jetzt=jetzt, force=True) == {"geschrieben": 0} and not db2.updates, "Schalter aus → nichts")
    for t in f:
        print("✗", t)
    print("OK" if not f else f"\n{len(f)} FEHLER")
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
