#!/usr/bin/env python3
"""Selbsttest: VON SELBST BESTÄTIGEN (app.py ap_auto_best_aktiv / ap_auto_best_kandidaten, 15.10.2026, Finn: „Das ist ein Knopf, den man
drücken muss. Das kann auch der Bot machen.") — rein rechnend, ohne Netz.
Aufruf: python3 tools/selftest_auto_bestaetigen.py"""
import os
import re
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone,
          # acc_balance_wahl als Attrappe: Stand = Feld „stand" am Konto
          "acc_balance_wahl": lambda a, e, d: ((1 if (a or {}).get("stand") else None), "USD", "TV", (a or {}).get("stand") or "")}
    for fn in ("_ap_ts", "ap_balance_live", "ap_letzt_je_konto"):
        i = src.index(f"def {fn}(")
        j = src.index("\n\n\ndef ", i)
        exec(src[i:j], ns)
    exec(re.search(r"^AP_CFD_ROUTEN = .*$", src, re.M).group(0), ns)   # A1: CFD-Weg (Echo / Echo V2)
    i = src.index("AP_AUTO_BEST_TAKT_S = ")
    j = src.index("\n\n\ndef ap_auto_best_tick(", i)
    exec(src[i:j], ns)
    return ns


def main():
    ns = lade()
    aktiv, kand = ns["ap_auto_best_aktiv"], ns["ap_auto_best_kandidaten"]
    f = []
    def check(ok, name):
        f.append(0 if ok else 1); print(("OK  " if ok else "FEHL") + " " + name)
    check(aktiv({"auto_bestaetigen": True}) is True, "Schalter true → an")
    check(aktiv({"auto_bestaetigen": "true"}) is False and aktiv({}) is False and aktiv(None) is False, "Schalter nur bei echtem true")
    accs = {"k-1": {"id": "k-1", "name": "150k A", "stand": "2026-10-15T10:00:00+00:00"},
            "k-2": {"id": "k-2", "name": "150k B", "stand": "2026-10-14T10:00:00+00:00"},
            "k-3": {"id": "k-3", "name": "150k C", "stand": ""},
            "k-4": {"id": "k-4", "name": "150k D", "stand": "2026-10-15T10:00:00+00:00", "auto_planer": False},
            "k-6": {"id": "k-6", "name": "150k F", "stand": "2026-10-15T10:00:00+00:00"}}
    letzt = ns["ap_letzt_je_konto"]([{"master_account_id": "k-2", "status": "completed", "ended_at": "2026-10-14T20:00:00+00:00"},
                                     {"master_account_id": "k-3", "status": "completed", "ended_at": "2026-10-14T20:00:00+00:00"}])
    basis = {"status": "planned", "auto_plan": True, "auto_bestaetigt_at": None, "user_id": "u"}
    plaene = [dict(basis, id="p-1", master_account_id="k-1", master_name="150k A"),
              dict(basis, id="p-2", master_account_id="k-2", master_name="150k B"),
              dict(basis, id="p-3", master_account_id="k-3", master_name="150k C"),
              dict(basis, id="p-4", master_account_id="k-4", master_name="150k D"),
              dict(basis, id="p-5", master_account_id="k-5", master_name="150k E"),
              dict(basis, id="p-6", master_account_id="k-6", master_name="150k F", puls_pause={"at": "x"}),
              dict(basis, id="p-7", master_account_id="k-1", master_name="150k A", auto_bestaetigt_at="2026-10-15T09:00:00+00:00"),
              dict(basis, id="p-8", master_account_id="k-1", master_name="150k A", start_um_gestartet_at="2026-10-15T09:00:00+00:00"),
              dict(basis, id="p-9", master_account_id="k-1", master_name="150k A", auto_plan=False),
              dict(basis, id="p-10", master_account_id="k-1", master_name="150k A", status="open")]
    ok, warten = kand(plaene, accs, letzt, {}, {}, archiv=set())
    warum = {w["plan_id"]: w["warum"] for w in warten}
    check(ok == ["p-1"], f"nur der Plan mit lebender Balance wird bestätigt (ist {ok})")
    check("p-2" in warum and "Balance" in warum["p-2"], "Balance vor dem letzten Trade-Ende → wartet (Balance-Takt liest)")
    check("p-3" in warum and "Balance" in warum["p-3"], "nie gelesen, aber schon gehandelt → wartet")
    check("p-4" in warum and "Haken" in warum["p-4"], "Planer-Haken aus → wartet")
    check("p-5" in warum and "Konto" in warum["p-5"], "Konto weg → wartet")
    check("p-6" in warum and "Puls-Pause" in warum["p-6"], "Puls-Pause → nie von selbst")
    check(all(p not in warum for p in ("p-7", "p-8", "p-9", "p-10")), "schon bestätigt / gestartet / Hand-Plan / offen → weder ok noch wartet")
    ok2, _ = kand(plaene, accs, letzt, {}, {}, archiv={"k-1"})
    check(ok2 == [], "archiviertes Konto → nicht bestätigen")
    # frisches Konto ohne Trade davor: ohne Lesung ist die Balance „live" (ap_balance_live ohne letzt) — der Planer rechnet mit dem Startwert
    ok3, _ = kand([dict(basis, id="p-11", master_account_id="k-3", master_name="150k C")], accs, {}, {}, {}, archiv=set())
    check(ok3 == ["p-11"], "frisches Konto ohne Trade → bestätigen (Startwert gilt, wie der Knopf)")
    check(kand([], {}, {}, {}, {}) == ([], []), "ohne Pläne leer")

    # A1 (04.11.2026, Finn: „Ja für CFD-Challenge"): Schalter "cfd" → nur CFD-Challenges, Futures bleiben von Hand
    umf = ns["ap_auto_best_umfang"]
    check(umf({"auto_bestaetigen": True}) == "alle" and umf({"auto_bestaetigen": "cfd"}) == "cfd" and umf({"auto_bestaetigen": ["cfd"]}) == "cfd",
          "Umfang: true = alle, \"cfd\" bzw. [\"cfd\"] = nur CFD")
    check(umf({"auto_bestaetigen": False}) is None and umf({"auto_bestaetigen": "CFD"}) is None and umf({"auto_bestaetigen": ["cfd", "futures"]}) is None
          and umf({}) is None and umf(None) is None, "Umfang: false / Unbekanntes / leer = aus")
    check(aktiv({"auto_bestaetigen": "cfd"}) is True and aktiv({"auto_bestaetigen": False}) is False, "aktiv auch bei \"cfd\"")
    lebt = "2026-10-15T10:00:00+00:00"
    accs_a1 = {"c-1": {"id": "c-1", "account_type": "phase1", "stand": lebt}, "c-2": {"id": "c-2", "account_type": "phase2", "stand": lebt},
               "c-3": {"id": "c-3", "account_type": "challenge", "stand": lebt}, "f-1": {"id": "f-1", "account_type": "challenge", "stand": lebt},
               "f-2": {"id": "f-2", "account_type": "challenge", "stand": lebt}, "f-3": {"id": "f-3", "account_type": "challenge", "stand": lebt},
               "d-1": {"id": "d-1", "account_type": "funded_cfd", "stand": lebt}}
    pl_a1 = [dict(basis, id="cfd-echo", master_account_id="c-1", route="mt5"),            # FTMO Phase 1 Echo mit Hedge (E3)
             dict(basis, id="cfd-v2", master_account_id="c-2", route="mt5v2"),            # Echo V2 (Alt-Plan)
             dict(basis, id="cfd-mini", master_account_id="c-3", route="mt5v2", tage_mini={"sofort_zu": True}),   # Mini „Tage sammeln"
             dict(basis, id="fut-orbit", master_account_id="f-1", route="tvv2"),          # Tradeify/Apex Futures-Challenge
             dict(basis, id="fut-topstep", master_account_id="f-2", route="tsv2"),        # Topstep-Kette
             dict(basis, id="fut-ohne", master_account_id="f-3"),                         # Weg unbekannt → von Hand
             dict(basis, id="funded-cfd", master_account_id="d-1", route="mt5")]          # Funded CFD: kein Challenge-Planer
    ok_c, w_c = kand(pl_a1, accs_a1, {}, {}, {}, archiv=set(), umfang="cfd")
    check(sorted(ok_c) == ["cfd-echo", "cfd-mini", "cfd-v2"], f"\"cfd\": CFD-Challenges (Echo, Echo V2, Mini) bestätigt ({sorted(ok_c)})")
    check(w_c == [], "\"cfd\": Futures / Funded / ohne Weg warten nicht, sie bleiben still „Zu bestätigen“ von Hand")
    ok_a, _ = kand(pl_a1, accs_a1, {}, {}, {}, archiv=set(), umfang="alle")
    check(len(ok_a) == len(pl_a1), f"true = alle: auch Futures bestätigt ({len(ok_a)} von {len(pl_a1)})")
    ok_d, _ = kand(pl_a1, accs_a1, {}, {}, {}, archiv=set())
    check(len(ok_d) == len(pl_a1), "ohne umfang (alte Aufrufer) = alle wie bisher")
    check(ns["ap_auto_best_cfd"]({"route": "mt5"}, None) is False and ns["ap_auto_best_cfd"]({"route": "mt5"}, {"account_type": "phase1"}) is True,
          "CFD-Erkennung: ohne Konto nein, Echo auf Phase 1 ja")
    src = open(APP, encoding="utf-8").read()
    t = src[src.index("def ap_auto_best_tick("):src.index("# ══ ZIEL-WACHE")]
    check("umfang = ap_auto_best_umfang(" in t and "umfang=umfang)" in t and "notes,route," in t,
          "Takt: Umfang aus dem Schalter, route mitgelesen, an die Kandidaten durchgereicht")
    check('"umfang": _ap_auto_best.get("umfang")' in src, "Admin GET /admin/auto-plan info.auto_bestaetigen zeigt den Umfang")
    print(f"\n{sum(f)} Fehler von {len(f)}")
    return sum(f)


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
