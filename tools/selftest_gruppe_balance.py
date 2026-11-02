#!/usr/bin/env python3
"""Selbsttest GRUPPE-BALANCE (app.py ap_bal_auto_gruppen_kandidaten / ap_bal_auto_gruppen_tick / _ap_bal_auto_senden, 02.11.2026). Ohne Netz, nichts wird gesendet.
Aufruf: python3 tools/selftest_gruppe_balance.py"""
import os, re, sys, time
from datetime import datetime, timedelta, timezone
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.py"), encoding="utf-8").read()
fehler = 0
def ok(b, t):
    global fehler
    print(("ok   " if b else "FEHL ") + t)
    fehler += 0 if b else 1
def fn(n):
    i = src.index(f"def {n}("); return src[i:src.index("\n\n\n", i)]
ns = {"re": re, "time": time, "datetime": datetime, "timedelta": timedelta, "timezone": timezone, "AP_BAL_AUTO_TAKT_S": 600, "AP_TYPEN": ("challenge",),
      "_ap_bal_auto_gr": {"at": 0.0, "tag": "", "versuche": {}, "gesendet": [], "uebersprungen": []}}
exec(fn("ap_bal_auto_gruppen_kandidaten"), ns); exec(fn("ap_bal_auto_gruppen_tick"), ns)
ns["ap_bal_auto_kandidaten"] = lambda lauf, tag, pl, accs, letzt, e, dd, ar=None: {str(p["master_account_id"]): "Plan" for p in pl if p["status"] == "planned"}
ns["ap_bal_auto_nie_gelesen"] = lambda l, schon, e, dd, ar=None: {a["id"]: "nie" for a in l if a.get("nie") and a["id"] not in schon}
ns["ap_bal_auto_ohne_wert"] = lambda l, schon, e, dd, ar=None: {}
konten = {"k1": {"id": "k1", "user_id": "julian", "nie": True}, "k2": {"id": "k2", "user_id": "amir"}, "k3": {"id": "k3", "user_id": "ht", "nie": True}}
gr = [{"ids": {"julian", "amir", "emin"}, "letzter_lauf": None}]
k = ns["ap_bal_auto_gruppen_kandidaten"](gr, "t", [{"master_account_id": "k2", "status": "planned"}, {"master_account_id": "k3", "status": "planned"}], konten, {}, {}, {})
ok(k == {"k1": "nie", "k2": "Plan"}, "frisches Konto + geplanter Plan der Gruppe; HT-Konto nie, auch mit Plan")
ok(ns["ap_bal_auto_gruppen_kandidaten"]([], "t", [], konten, {}, {}, {}) == {}, "keine aktive Gruppe = nichts")
# Takt mit gestellter Datenbank
sent = {}
ns.update(sb_select=lambda t, p: [{"aktiv": ns["_aktiv"]}], ap_planer_gruppen=lambda nur_aktiv=False: gr if nur_aktiv else [], _ap_tz=lambda z: timezone.utc, AP_TZ_TAG="x",
          _sb_all=lambda t, p: ns["_plaene"], _ap_konten_laden=lambda p: list(konten.values()), _ap_balance_karten=lambda: ({}, {}), ap_letzt_je_konto=lambda p: {}, _ap_archiviert=lambda: set(),
          _ap_bal_auto_senden=lambda kand, accs, d, tag, merk, uids_offen=None, wer="": sent.update(kand=kand, offen=uids_offen, merk=merk, wer=wer) or ["x"])
jetzt = datetime(2026, 11, 2, 9, tzinfo=timezone.utc)
ns["_aktiv"] = False; ns["_plaene"] = []
ok(ns["ap_bal_auto_gruppen_tick"](jetzt) is None and not sent, "Planer aus: keine Lesung")
ns["_ap_bal_auto_gr"]["at"] = 0; ns["_aktiv"] = True
ns["_plaene"] = [{"user_id": "amir", "master_account_id": "k2", "status": "open"}]
ns["ap_bal_auto_gruppen_tick"](jetzt)
ok(sent.get("offen") == {"amir"}, "offener Trade der ID geht an den Sende-Teil")
ok(sent.get("merk") is ns["_ap_bal_auto_gr"] and sent.get("wer") == " Gruppe", "eigener Speicher, HT-Speicher bleibt unberührt")
ok(ns["ap_bal_auto_gruppen_tick"](jetzt) is None, "Takt-Bremse 600 s")
# Quelltext-Riegel
t = fn("_ap_bal_auto_senden")
ok("_ap_bal_auto[" not in t and "_ap_bal_auto." not in t, "Sende-Teil schreibt nur in merk")
ok('return _ap_bal_auto_senden(kand, accs, d, tag, _ap_bal_auto)' in fn("ap_bal_auto_tick"), "HT-Takt ruft ohne uids_offen, Verhalten wie bisher")
ok("_ap_bal_auto_gr" not in src[src.index('info["balance_auto"] ='):src.index('"takt_s": AP_BAL_AUTO_TAKT_S}', src.index('info["balance_auto"] ='))], "info.balance_auto zeigt keine Gruppen-Daten")
ok(t.index("uids_offen or ()") < t.index("sb_insert("), "offener Trade wird vor dem Auftrag geprüft")
print("OK" if not fehler else f"{fehler} FEHLER"); sys.exit(1 if fehler else 0)
