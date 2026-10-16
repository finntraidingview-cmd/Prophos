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
          # acc_balance_wahl als Attrappe: Stand = Feld „stand" am Konto; ohne Stand keine Balance (nie gelesen, Quelle C 15.10.2026)
          "acc_balance_wahl": lambda a, e, d: ((1 if (a or {}).get("stand") else None), "USD", "TV", (a or {}).get("stand") or ""),
          "ist_topstep_express": lambda a, relativ=None: bool((a or {}).get("express"))}
    for k in ("AP_BAL_FEHLT", "AP_LESE_FELDER", "AP_TYPEN"):
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
    # QUELLE C — nie gelesene Konten (15.10.2026, Marcs fünf Apex-Konten nach 16:00 Dubai angelegt, kein Lauf kannte sie)
    nie = ns["ap_bal_auto_nie_gelesen"]
    neu = [{"id": "n-1", "user_id": "u", "name": "150k APEX…0001", "account_type": "challenge", "external_id": "APEX0001"},
           {"id": "n-2", "user_id": "u", "name": "150k APEX…0002", "account_type": "challenge", "external_id": "APEX0002", "auto_planer": False},
           {"id": "n-3", "user_id": "u", "name": "150k APEX…0003", "account_type": "challenge", "external_id": ""},
           {"id": "n-4", "user_id": "u", "name": "150k APEX…0004", "account_type": "challenge", "external_id": "APEX0004", "tv_balance_at": "2026-10-15T10:00:00+00:00", "stand": "2026-10-15T10:00:00+00:00"},
           {"id": "n-5", "user_id": "u", "name": "150k Express", "account_type": "challenge", "external_id": "EXP5", "express": True},
           {"id": "n-6", "user_id": "u", "name": "50k Funded", "account_type": "funded", "external_id": "F6"},
           {"id": "n-7", "user_id": "u", "name": "150k APEX…0007", "account_type": "phase1", "external_id": "APEX0007"},
           {"id": "n-8", "user_id": "u", "name": "150k APEX…0008", "account_type": "challenge", "external_id": "APEX0008"}]
    outc = nie(neu, {"n-7"}, {}, {}, archiv={"n-8"})
    check("n-1" in outc and "nie gelesen" in outc["n-1"], "C: neues Konto ohne jede Lesung → lesen")
    check("n-2" not in outc, "C: Planer-Haken aus → nicht")
    check("n-3" not in outc, "C: ohne External ID → nicht (Lesung bringt nichts)")
    check("n-4" not in outc, "C: schon einmal gelesen → Sache von A/B, nicht C")
    check("n-5" not in outc, "C: Topstep Express → nie")
    check("n-6" not in outc, "C: Kontotyp außerhalb AP_TYPEN → nicht")
    check("n-7" not in outc, "C: schon von A/B in diesem Takt → nicht doppelt")
    check("n-8" not in outc, "C: archiviert → nicht")
    check(nie([], set(), {}, {}) == {}, "C: ohne Konten leer")
    j = 1_000_000.0
    check(darf(None, j) == (True, ""), "noch kein Auftrag → darf")
    check(darf([j - 6000], j)[0] is True, "letzter Auftrag vor 100 min → darf")
    check(darf([j - 600], j)[0] is False and "min" in darf([j - 600], j)[1], "letzter Auftrag vor 10 min → Abstand")
    check(darf([j - 20000, j - 15000, j - 10000], j)[0] is False and "Deckel" in darf([j - 20000, j - 15000, j - 10000], j)[1], "3 Aufträge heute → Deckel")
    # TAGESSTAND AUS DER DB (16.10.2026, Muster „… kein Tradovate-Username hinterlegt" 35× in 24 h: Speicher-Bremse nach Neustart leer)
    dbs = ns["ap_bal_auto_db_stand"]
    t0 = datetime(2026, 10, 15, 20, 0, tzinfo=timezone.utc).timestamp()
    ohne = {"ok": False, "msg": "Konto X steht im Dropdown 0x … Puls kann nicht selbst verbinden: für die Firma ist kein Tradovate-Username hinterlegt ("}
    rows = [{"plan_id": "konto:a", "created_at": "2026-10-15 23:00:08.3+00", "status": "fehler", "params": {"von": "auto_planer"}, "ergebnis": ohne},
            {"plan_id": "konto:a", "created_at": "2026-10-15 22:03:32+00", "status": "fehler", "params": {"von": "auto_planer"}, "ergebnis": ohne},
            {"plan_id": "konto:a", "created_at": "2026-10-15 18:28:13+00", "status": "fehler", "params": {"von": "auto_planer"}, "ergebnis": ohne},
            {"plan_id": "konto:b", "created_at": "2026-10-15 21:00:00+00", "status": "fertig", "params": {"von": "auto_planer"}, "ergebnis": {"ok": True}},
            {"plan_id": "konto:b", "created_at": "2026-10-15 20:30:00+00", "status": "fehler", "params": {"von": "besitzer"}, "ergebnis": ohne},
            {"plan_id": "konto:c", "created_at": "2026-10-15 22:00:00+00", "status": "fehler", "params": {"von": "besitzer"}, "ergebnis": {"ok": False, "msg": "Signal älter als 3 Minuten"}},
            {"plan_id": "konto:c", "created_at": "2026-10-15 21:00:00+00", "status": "fehler", "params": {"von": "auto_planer"}, "ergebnis": ohne},
            {"plan_id": "konto:d", "created_at": "2026-10-15 23:30:00+00", "status": "wartet", "params": {"von": "auto_planer"}, "ergebnis": None},
            {"plan_id": "konto:d", "created_at": "2026-10-15 21:00:00+00", "status": "fehler", "params": {"von": "auto_planer"}, "ergebnis": ohne},
            {"plan_id": "plan-xyz", "created_at": "2026-10-15 21:00:00+00", "status": "fehler", "params": {}, "ergebnis": ohne}]
    st = dbs(rows, t0)
    check(len(st["a"]["versuche"]) == 2, "DB: nur heutige Auto-Aufträge zählen (18:28 UTC = gestern Dubai)")
    check(st["a"]["ohne_username"] is True, "DB: letzte Lesung ohne Username → Sperre")
    check(darf(st["a"]["versuche"], datetime(2026, 10, 15, 23, 30, tzinfo=timezone.utc).timestamp())[0] is False, "DB: Abstand gilt auch nach Neustart")
    check(st["b"]["ohne_username"] is False and len(st["b"]["versuche"]) == 1, "DB: neuere erfolgreiche Lesung hebt Sperre auf, Hand-Auftrag zählt nicht")
    check(st["c"]["ohne_username"] is False, "DB: neuerer Hand-Auftrag (anderer Grund) hebt Sperre auf")
    check(st["d"]["ohne_username"] is True, "DB: wartender Auftrag zählt nicht als Ergebnis")
    check("plan-xyz" not in st and "xyz" not in st, "DB: Plan-Signale ignoriert")
    check(dbs([], t0) == {} and dbs(None, t0) == {}, "DB: leer")
    # BALANCE SELBST (16.10.2026, Finn: nie ein Hand-↻ nötig — Marc trug den Apex-Username ein, der Bot las trotzdem nicht)
    sp = ns["ap_bal_auto_username_sperre"]
    ts_a = st["a"]["ohne_username_at"]
    check(ts_a == datetime(2026, 10, 15, 23, 0, 8, 300000, tzinfo=timezone.utc).timestamp(), "DB: Zeitpunkt des Fehlschlags steht mit")
    check(st["b"]["ohne_username_at"] is None, "DB: ohne Sperre kein Zeitpunkt")
    check(sp(st["a"], False, ts_a + 3600)[0] is True, "Sperre: Username fehlt weiter, 1 h danach → gesperrt")
    check("von selbst" in sp(st["a"], False, ts_a + 3600)[1] and "↻" not in sp(st["a"], False, ts_a + 3600)[1], "Sperre: Text verlangt keinen Hand-Klick")
    check(sp(st["a"], True, ts_a + 60) == (False, ""), "Sperre fällt, sobald der Username eingetragen ist")
    check(sp(st["a"], False, ts_a + 6 * 3600) == (False, ""), "Sperre: nach 6 h ein Probe-Versuch")
    check(sp(st["b"], False, ts_a) == (False, ""), "ohne Username-Fehlschlag nie gesperrt")
    check(sp({}, False, ts_a) == (False, "") and sp(None, False, ts_a) == (False, ""), "leer → frei")
    print(f"\n{sum(f)} Fehler von {len(f)}")
    return sum(f)


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
