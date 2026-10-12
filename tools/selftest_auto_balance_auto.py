#!/usr/bin/env python3
"""Selbsttest: Balance von selbst nachlesen (app.py ap_bal_auto_kandidaten / ap_bal_auto_darf, 13.10.2026, Finn: „der Bot soll
eigenständig die Balance aktualisieren und dann den Handel mit der neuen Balance starten") — rein rechnend, ohne Netz.
Aufruf: python3 tools/selftest_auto_balance_auto.py"""
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
          "acc_balance_wahl": lambda a, e, d: (1, "USD", "TV", (a or {}).get("stand") or "")}
    for k in ("AP_BAL_FEHLT",):
        exec(re.search(rf"^{k} = .*$", src, re.M).group(0), ns)
    for fn in ("_ap_ts", "ap_balance_live", "ap_letzt_je_konto"):
        i = src.index(f"def {fn}(")
        j = src.index("\n\n\ndef ", i)
        exec(src[i:j], ns)
    i = src.index("AP_BAL_AUTO_TAKT_S = ")
    j = src.index("\n\n\ndef ap_bal_auto_tick(", i)
    exec(src[i:j], ns)
    return ns


def main():
    ns = lade()
    kand, darf = ns["ap_bal_auto_kandidaten"], ns["ap_bal_auto_darf"]
    f = []
    def check(ok, name):
        f.append(0 if ok else 1); print(("OK  " if ok else "FEHL") + " " + name)
    accs = {"k-1": {"id": "k-1", "user_id": "u", "name": "150k A", "stand": "2026-10-13T00:00:00+00:00"},
            "k-2": {"id": "k-2", "user_id": "u", "name": "150k B", "stand": "2026-10-13T02:00:00+00:00"},
            "k-3": {"id": "k-3", "user_id": "u", "name": "150k C", "stand": ""},
            "k-4": {"id": "k-4", "user_id": "u", "name": "150k D", "stand": "", "auto_planer": False},
            "k-5": {"id": "k-5", "user_id": "u", "name": "100k E", "stand": "2026-10-12T10:00:00+00:00"},
            "k-6": {"id": "k-6", "user_id": "u", "name": "100k F", "stand": "2026-10-12T22:00:00+00:00"}}
    lauf = {"tag": "2026-10-13", "at": "2026-10-13T01:30:00+00:00", "ausgelassen": [
        {"konto_id": "k-1", "grund": "Balance nicht live (seit dem letzten Trade nicht nachgelesen)"},
        {"konto_id": "k-2", "grund": "keine Balance bekannt — Konto wurde schon gehandelt", "grund_code": "schon_gehandelt"},
        {"konto_id": "k-3", "grund": "keine Balance bekannt — keine External ID", "grund_code": "ext_fehlt"},
        {"konto_id": "k-4", "grund": "Balance nicht live (seit dem letzten Trade nicht nachgelesen)"},
        {"konto_id": "k-9", "grund": "Balance nicht live (seit dem letzten Trade nicht nachgelesen)"},
        {"konto_id": "k-7", "grund": "heute schon gehandelt — ein Trade pro Konto und Tag"}]}
    plaene = [{"master_account_id": "k-5", "status": "planned"},
              {"master_account_id": "k-5", "status": "completed", "ended_at": "2026-10-12T20:00:00+00:00"},
              {"master_account_id": "k-6", "status": "planned"},
              {"master_account_id": "k-6", "status": "completed", "ended_at": "2026-10-12T20:00:00+00:00"}]
    letzt = ns["ap_letzt_je_konto"](plaene)
    out = kand(lauf, "2026-10-13", plaene, accs, letzt, {}, {}, archiv=set())
    check("k-1" in out, "Lauf „Balance nicht live“, Stand vor dem Lauf → lesen")
    check("k-2" not in out, "Lauf „keine Balance“, aber seit dem Lauf gelesen → nicht nochmal")
    check("k-3" not in out, "ext_fehlt → Lesung bringt nichts")
    check("k-4" not in out, "Planer-Haken aus → nicht lesen")
    check("k-9" not in out, "Konto nicht mehr da (nicht in accs) → nicht lesen")
    check("k-7" not in out, "anderer Grund (heute gehandelt) → nicht lesen")
    check("k-5" in out and "geplant" in out["k-5"], "geplanter Plan, Balance vor dem letzten Trade-Ende → lesen")
    check("k-6" not in out, "geplanter Plan, Balance nach dem Trade-Ende (live) → nicht lesen")
    out2 = kand({"tag": "2026-10-12", "at": "2026-10-12T01:30:00+00:00", "ausgelassen": lauf["ausgelassen"]}, "2026-10-13", [], accs, {}, {}, {})
    check(out2 == {}, "Lauf von gestern zählt nicht")
    out3 = kand(lauf, "2026-10-13", plaene, accs, letzt, {}, {}, archiv={"k-1", "k-5"})
    check("k-1" not in out3 and "k-5" not in out3, "archivierte Konten nie")
    j = 1_000_000.0
    check(darf(None, j) == (True, ""), "noch kein Auftrag → darf")
    check(darf([j - 6000], j)[0] is True, "letzter Auftrag vor 100 min → darf")
    check(darf([j - 600], j)[0] is False and "min" in darf([j - 600], j)[1], "letzter Auftrag vor 10 min → Abstand")
    check(darf([j - 20000, j - 15000, j - 10000], j)[0] is False and "Deckel" in darf([j - 20000, j - 15000, j - 10000], j)[1], "3 Aufträge heute → Deckel")
    print(f"\n{sum(f)} Fehler von {len(f)}")
    return sum(f)


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
