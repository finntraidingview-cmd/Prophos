#!/usr/bin/env python3
"""Selbsttest HANDARBEIT (app.py hand_gruppen, Finn 09.10.2026: „eine Liste mit allen Accounts, die gepasst wurden oder irgendwas manuell
Hilfe brauchen … Wo muss ich die Phase hinzufügen?"). Rein rechnend, Platzhalter-IDs, ohne Netz.
Geprüft: bestanden (Ziel-Wache, Phase alt → neu), archiviert raus, Konto mit Manuelle-Arbeit-Zeile nicht doppelt; geblowt nur, wenn der
Blow-Plan der jüngste des Kontos ist; Überprüfen erst nach 6 h, ohne Manuell-Kennzeichen; Manuelle Arbeit mit Schritt/Notiz; ausgeblendete IDs raus.
Aufruf: python3 tools/selftest_handarbeit.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone}

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]
    for k in ("HAND_UEBERPRUEFEN_H", "HAND_NACH", "HAND_PLANER_OHNE"):
        exec(re.search(rf"^{k} = .*$", src, re.M).group(0), ns)
    for f in ("_wd_num", "_ap_ts", "hand_gruppen"):
        exec(block(f), ns)
    return ns


def main():
    ns = lade()
    f = []

    def check(ok, name):
        f.append(0 if ok else 1)
        print(("OK  " if ok else "FEHL") + " " + name)
    jetzt = datetime(2026, 10, 9, 2, 0, tzinfo=timezone.utc)
    iso = lambda h: (jetzt - timedelta(hours=h)).isoformat()
    UA, UB, UX = "u-a", "u-b", "u-x"
    konten_ziel = [
        {"id": "k1", "user_id": UA, "name": "50k FundedNext", "firm": "FundedNext", "account_type": "phase2", "external_id": "FN-0001",
         "ziel_erreicht_at": iso(10), "ziel_erreicht_bal": 52600, "ziel_usd": 52500},
        {"id": "k2", "user_id": UB, "name": "100k FundedNext", "firm": "FundedNext", "account_type": "phase1", "external_id": "FN-0002",
         "ziel_erreicht_at": iso(5), "ziel_erreicht_bal": 108100, "ziel_usd": 108000},
        {"id": "k3", "user_id": UA, "name": "archiviert", "firm": "FTMO", "account_type": "phase1", "ziel_erreicht_at": iso(3)},
        {"id": "k4", "user_id": UA, "name": "200k The5ers", "firm": "The5%ers", "account_type": "phase2", "ziel_erreicht_at": iso(20)},
        {"id": "k5", "user_id": UA, "name": "Funded", "firm": "FundedNext", "account_type": "funded", "ziel_erreicht_at": iso(2)},
        {"id": "k6", "user_id": UX, "name": "ausgeblendet", "firm": "FundedNext", "account_type": "phase1", "ziel_erreicht_at": iso(2)},
    ]
    reviews = [
        {"id": "r1", "user_id": UB, "master_account_id": "k7", "master_name": "150k Tradeify", "master_firm": "Tradeify", "ended_at": iso(30)},
        {"id": "r2", "user_id": UB, "master_account_id": "k8", "master_firm": "Tradeify", "ended_at": iso(2)},
        {"id": "r3", "user_id": UA, "master_account_id": "k4", "master_firm": "The5%ers", "ended_at": iso(5),
         "manuell": {"at": iso(4), "schritt": "warten", "notiz": "Warten auf Freigabe"}},
    ]
    blown = [
        {"id": "b1", "user_id": UA, "master_account_id": "k9", "master_firm": "FundedNext Futures", "master_name": "150k FN Futures",
         "ended_at": iso(11), "master_pl": -6311.52},
        {"id": "b2", "user_id": UB, "master_account_id": "k10", "master_firm": "Tradeify", "ended_at": iso(40)},
    ]
    letzte = {"k9": ("b1", iso(12)), "k10": ("neu1", iso(1))}
    accs = {"k9": {"id": "k9", "external_id": "FNF-0045", "account_type": "challenge"}, "k7": {"id": "k7", "external_id": "TDFY-3962"}}
    lauf = {"at": iso(4), "ausgelassen": [
        {"user_id": UA, "konto_id": "k20", "firma": "Tradeify", "konto": "150k Tradeify", "typ": "challenge", "grund": "keine Balance bekannt"},
        {"user_id": UB, "konto_id": "k21", "firma": "FundedNext", "konto": "100k FundedNext", "typ": "phase1", "grund": "nur noch 36 $ bis zum Ziel — von Hand prüfen"},
        {"user_id": UB, "konto_id": "k22", "firma": "FundedNext", "grund": "Ziel erreicht — Phase umstellen"},
        {"user_id": UA, "konto_id": "k23", "firma": "The5%ers", "grund": "letzter Trade noch nicht erledigt (Überprüfen)"},
        {"user_id": UA, "konto_id": "k24", "firma": "FundingPips", "grund": "hat schon einen geplanten/laufenden Plan"},
        {"user_id": UB, "konto_id": "k2", "firma": "FundedNext", "grund": "keine Balance bekannt"},
        {"user_id": UX, "konto_id": "k25", "firma": "Tradeify", "grund": "keine Balance bekannt"}]}
    g = ns["hand_gruppen"](konten_ziel, reviews, blown, letzte, accs, {"k3"}, {UA: "Ina", UB: "Ben"}, {UX}, jetzt, lauf)
    be = g["bestanden"]
    check([z["konto_id"] for z in be] == ["k2", "k1"], f"bestanden: k2, k1 (neueste zuerst; archiviert, Funded, ausgeblendet, Manuell-Konto raus) → {[z['konto_id'] for z in be]}")
    check(be[1]["typ"] == "phase2" and be[1]["nach"] == "funded_cfd" and be[0]["nach"] == "phase2" and be[0]["user"] == "Ben" and be[1]["ende4"] == "0001",
          "Phase alt → neu (phase2 → Funded CFD, phase1 → Phase 2), Name, Kontonummer-Ende")
    check([z["konto_id"] for z in g["geblowt"]] == ["k9"] and g["geblowt"][0]["ende4"] == "0045",
          "geblowt nur, wenn der Blow-Plan der jüngste des Kontos ist (k10 hat danach neu gestartet)")
    check([z["plan_id"] for z in g["ueberpruefen"]] == ["r1"] and g["ueberpruefen"][0]["ende4"] == "3962", "Überprüfen erst nach 6 h (r2 nach 2 h noch nicht)")
    check([z["plan_id"] for z in g["manuell"]] == ["r3"] and g["manuell"][0]["notiz"] == "Warten auf Freigabe" and g["manuell"][0]["schritt"] == "warten",
          "Manuelle Arbeit mit Schritt und Notiz")
    pl = g["planer"]
    check([z["konto_id"] for z in pl] == ["k20", "k21"], f"Planer braucht dich: nur Hand-Gründe, ohne Ziel/Überprüfen/geplant, ohne Konto aus anderer Gruppe, ohne ausgeblendete → {[z['konto_id'] for z in pl]}")
    check(pl[0]["knopf"] == "balance" and pl[1]["knopf"] == "" and pl[1]["grund"].startswith("nur noch 36 $") and pl[0]["seit"] == lauf["at"],
          "Knopf „Balance lesen“ nur bei keine Balance; Grund im Klartext; seit = Lauf")
    check(ns["hand_gruppen"](konten_ziel, reviews, blown, letzte, accs, {"k3"}, {}, {UX}, jetzt)["planer"] == [], "ohne Lauf → Gruppe leer")
    print(f"{len(f) - sum(f)}/{len(f)} ok")
    sys.exit(1 if sum(f) else 0)


if __name__ == "__main__":
    main()
