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
    print(f"\n{sum(f)} Fehler von {len(f)}")
    return sum(f)


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
