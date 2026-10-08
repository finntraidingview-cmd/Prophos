#!/usr/bin/env python3
"""Selbsttest: Fremd-Positionen-Wache (app.py fp_erkennen / fp_alarme / fp_plan_aktiv, 08.10.2026, Slave 1: Hand-Trades in MT5 ohne Plan
erkennen, Gegenhedge melden). Rein rechnend, Funktionen aus app.py geschnitten. Aufruf: python3 tools/selftest_fremd_positionen.py"""
import os
import re
import sys
from datetime import datetime, timezone, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"datetime": datetime, "timezone": timezone, "re": re}
    teile = [re.search(r"^FP_FRISCH_S = .*$", src, re.M).group(0)]
    for name in ("lt_echo_live_wahl", "_fp_ts", "fp_plan_aktiv", "fp_erkennen", "fp_konto_norm", "fp_preis_norm", "fp_erkennen_tv", "fp_alarme"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n\n".join(teile), ns)
    return ns


def main():
    ns = lade()
    E, A, AKT = ns["fp_erkennen"], ns["fp_alarme"], ns["fp_plan_aktiv"]
    f = []

    def check(ok, name):
        f.append(0 if ok else 1)
        print(("OK  " if ok else "FEHL") + " " + name)

    jetzt = datetime(2026, 10, 8, 7, 0, tzinfo=timezone.utc)
    iso = lambda s: (jetzt - timedelta(seconds=s)).isoformat()
    pos = lambda ident, typ, sym="NDX100", vol=1.0: {"ident": ident, "type": typ, "symbol": sym, "volume": vol}
    konten = {"111": {"id": "k1", "user_id": "u-finn", "firm": "FundedNext", "name": "100k FN 111", "account_type": "phase1"},
              "222": {"id": "k2", "user_id": "u-ina", "firm": "FundedNext", "name": "100k FN 222", "account_type": "phase2"},
              "333": {"id": "k3", "user_id": "u-finn", "firm": "The5%ers", "name": "100k 5ers 333", "account_type": "phase1"}}

    # 1) Plan-Position (Ticket bekannt) → nicht fremd; Hand-Trade daneben auf demselben Konto → fremd
    live = [{"master_login": "111", "hedge_login": "400004", "updated_at": iso(5), "note": None, "pos": [pos(10, 1), pos(11, 0, vol=2.5)]}]
    plaene = [{"master_account_id": "k1", "status": "open", "ticket": "10"}]
    fr, bew = E(live, konten, plaene, jetzt)
    check([x["ident"] for x in fr] == ["11"] and fr[0]["richtung"] == "buy" and fr[0]["menge"] == 2.5 and bew == {"111"},
          f"Plan-Ticket raus, Hand-Trade daneben fremd (buy 2,5) ({fr}, {bew})")
    check(fr[0]["konto_id"] == "k1" and fr[0]["user_id"] == "u-finn" and fr[0]["firma"] == "FundedNext", "Konto/ID/Firma aus accounts")

    # 2) Konto ohne Plan → jede Position fremd; Sell = type 1
    live = [{"master_login": "222", "updated_at": iso(5), "note": None, "pos": [pos(20, 1)]}]
    fr, bew = E(live, konten, [], jetzt)
    check(len(fr) == 1 and fr[0]["richtung"] == "sell" and bew == {"222"}, "ohne Plan: Position fremd (sell)")

    # 3) laufender Plan OHNE Ticket (klassisches Echo / Echo V2 vor dem Fill) → Konto unbewertet, nichts fremd, nichts schließen
    for p, wort in (({"master_account_id": "k2", "status": "open", "ticket": None}, "open ohne Ticket"),
                    ({"master_account_id": "k2", "status": "planned", "ticket": "", "start_um_gestartet_at": iso(60)}, "gestartet vor 1 min"),
                    ({"master_account_id": "k2", "status": "completed", "ticket": None, "ended_at": iso(120)}, "eben beendet")):
        fr, bew = E(live, konten, [p], jetzt)
        check(fr == [] and bew == set(), f"Plan {wort} ohne Ticket → Konto unbewertet")
    fr, bew = E(live, konten, [{"master_account_id": "k2", "status": "completed", "ticket": None, "ended_at": iso(3600)}], jetzt)
    check(len(fr) == 1, "Plan vor 1 h beendet, ohne Ticket → Position zählt wieder als fremd")
    fr, bew = E(live, konten, [{"master_account_id": "k2", "status": "planned", "ticket": None, "start_um_gestartet_at": iso(3600)}], jetzt)
    check(len(fr) == 1, "geplant, Start-Claim 1 h alt (nicht gestartet) → Konto wird bewertet")

    # 4) ungültige Lesungen: alt, note (eingefroren), keine Liste, Hedge-Login, unbekanntes Konto
    for z, wort in (({"master_login": "222", "updated_at": iso(200), "note": None, "pos": [pos(20, 1)]}, "älter als FP_FRISCH_S"),
                    ({"master_login": "222", "updated_at": iso(5), "note": "Snapshot eingefroren", "pos": [pos(20, 1)]}, "note gesetzt"),
                    ({"master_login": "222", "updated_at": iso(5), "note": None, "pos": None}, "pos keine Liste"),
                    ({"master_login": "999", "updated_at": iso(5), "note": None, "pos": [pos(20, 1)]}, "Login ohne Konto")):
        fr, bew = E([z], konten, [], jetzt)
        check(fr == [] and bew == set(), f"ungültig: {wort}")
    fr, bew = E([{"master_login": "222", "updated_at": iso(5), "note": None, "pos": [pos(20, 1)]},
                 {"master_login": "111", "hedge_login": "222", "updated_at": iso(5), "note": None, "pos": []}], konten, [], jetzt)
    check(fr == [] and bew == {"111"}, "Hedge-Login (Fusion) ist kein Prop-Konto")

    # 5) zwei Zeilen je Login: eingefrorene frischere Zeile wird ignoriert, die gültige zählt; leere gültige Lesung → bewertet, nichts fremd
    fr, bew = E([{"master_login": "222", "updated_at": iso(1), "note": "Snapshot eingefroren", "pos": []},
                 {"master_login": "222", "updated_at": iso(8), "note": None, "pos": [pos(20, 1)]}], konten, [], jetzt)
    check(len(fr) == 1, "eingefrorene Zeile auf anderem PC verdeckt die gültige nicht")
    fr, bew = E([{"master_login": "333", "updated_at": iso(5), "note": None, "pos": []}], konten, [], jetzt)
    check(fr == [] and bew == {"333"}, "gültig, keine Position → bewertet (offene Fremd-Zeilen dort schließen)")
    fr, _ = E([{"master_login": "333", "updated_at": iso(5), "note": None, "pos": [pos(30, 2), pos("", 0), "x"]}], konten, [], jetzt)
    check(fr == [], "nur Buy/Sell mit Ticket zählen (type 2, leeres Ticket, Müll raus)")

    # 5b) nie bewertet: Fusion-Konto, Duplikum-verknüpft, Gegenkonto eines laufenden Plans (Slave-2-Prüfung: Kopien/Hedges sperren sonst Starts)
    k2 = dict(konten, **{"444": {"id": "k4", "user_id": "u-finn", "firm": "Fusion Markets", "name": "Fusion 444"},
                         "555": {"id": "k5", "user_id": "u-finn", "firm": "FundedNext", "name": "FN 555", "duplikum_linked": True}})
    for lg, pl, wort in (("444", [], "Fusion-Konto"), ("555", [], "duplikum_linked"),
                         ("222", [{"master_account_id": "k1", "slave_account_id": "k2", "status": "open", "ticket": "10"}], "Gegenkonto laufender Plan")):
        fr, bew = E([{"master_login": lg, "updated_at": iso(5), "note": None, "pos": [pos(50, 0)]}], k2, pl, jetzt)
        check(fr == [] and bew == set(), f"nie fremd: {wort}")
    fr, _ = E([{"master_login": "222", "updated_at": iso(5), "note": None, "pos": [pos(50, 0)]}], k2,
              [{"master_account_id": "k1", "slave_account_id": "k2", "status": "completed", "ticket": "10", "ended_at": iso(3600)}], jetzt)
    check(len(fr) == 1, "Gegenkonto eines längst beendeten Plans → wieder bewertet")

    # 5c) Echo-V1-Restfall: Plan von Hand erledigt, Master-Position noch offen, Copier führt einen Hedge dazu → nie fremd
    z = {"master_login": "222", "updated_at": iso(5), "note": None, "pos": [pos(613921415, 0), pos(77, 1)],
         "hd": {"613921415": [{"ticket": 233263483, "volume": 1.76}], "77": []}}
    fr, bew = E([z], konten, [{"master_account_id": "k2", "status": "completed", "ticket": None, "ended_at": iso(3600)}], jetzt)
    check([x["ident"] for x in fr] == ["77"] and bew == {"222"}, f"Echo V1: Position mit Copier-Hedge nie fremd, ohne Hedge (leere Liste) schon ({fr})")
    fr, _ = E([dict(z, hd=None)], konten, [], jetzt)
    check(len(fr) == 2, "ohne hedges-Feld wie bisher")

    # 6) fp_plan_aktiv
    check(AKT({"status": "open"}, jetzt) and not AKT({"status": "planned"}, jetzt) and AKT({"status": "planned", "orbit_gesendet_at": iso(300)}, jetzt)
          and not AKT({"status": "review", "ended_at": iso(900)}, jetzt) and AKT({"status": "review", "ended_at": iso(100)}, jetzt),
          "fp_plan_aktiv: open / gesendet 5 min / beendet < 10 min")

    # 6b) TradingView/Tradovate (echoplus_live): aktives Konto je PC, nur positionen_ok, Konto mit aktivem Plan unbewertet
    T = ns["fp_erkennen_tv"]
    kt = {"TDFYSL150165040636": {"id": "t1", "user_id": "u-finn", "firm": "Tradeify", "name": "150k Tradeify 0636", "account_type": "challenge"},
          "FTDFYSLX150931730530": {"id": "t2", "user_id": "u-ina", "firm": "Tradeify", "name": "150k 0530", "account_type": "funded"}}
    tpos = lambda r="buy", fill=31304.5, sym="NQZ6": {"richtung": r, "symbol": sym, "avg_fill": fill, "menge": "2", "menge_zahl": 2}
    z1 = {"konto": "TDFYSL150165040636", "positionen_ok": True, "updated_at": iso(3), "positionen": [tpos()]}
    fr, bew = T([z1], kt, [], jetzt)
    check(len(fr) == 1 and fr[0]["ident"] == "NQZ6:buy:31304.50" and fr[0]["menge"] == 2 and fr[0]["konto_id"] == "t1" and bew == {"TDFYSL150165040636"},
          f"TV: Hand-Position ohne Plan → fremd, ident Symbol:Richtung:Einstieg ({fr})")
    fr, bew = T([z1], kt, [{"master_account_id": "t1", "status": "open"}], jetzt)
    check(fr == [] and bew == set(), "TV: Konto mit laufendem Orbit-Plan → unbewertet (Plan-Position)")
    fr, bew = T([z1], kt, [{"master_account_id": "x", "slave_account_id": "t1", "status": "planned", "orbit_gesendet_at": iso(30)}], jetzt)
    check(fr == [] and bew == set(), "TV: Gegenkonto eines startenden Plans → unbewertet")
    for z, wort in ((dict(z1, positionen_ok=False), "positionen_ok false (blind)"), (dict(z1, updated_at=iso(200)), "alt"),
                    (dict(z1, konto=None), "kein Konto"), (dict(z1, konto="UNBEKANNT1"), "Konto nicht in accounts")):
        fr, bew = T([z], kt, [], jetzt)
        check(fr == [] and bew == set(), f"TV ungültig: {wort}")
    fr, bew = T([dict(z1, konto="tdfysl-150165040636", positionen=[])], kt, [], jetzt)
    check(fr == [] and bew == {"TDFYSL150165040636"}, "TV: Kontonummer normiert, leere vollständige Lesung → bewertet (schließt)")
    fr, _ = T([dict(z1, updated_at=iso(1), positionen=[]), dict(z1, updated_at=iso(10))], kt, [], jetzt)
    check(fr == [], "TV: zwei PCs mit demselben Konto → frischeste Lesung zählt")
    fr, _ = T([dict(z1, positionen=[tpos("long"), {"richtung": "sell"}, "x", tpos("sell", 31310.0)])], kt, [], jetzt)
    check([x["ident"] for x in fr] == ["NQZ6:sell:31310.00"], "TV: nur buy/sell mit Symbol")
    # gleiche Position, andere Schreibweise des Einstiegs → gleicher ident (Slave-2-Prüfung)
    ids = {T([dict(z1, positionen=[dict(tpos(), avg_fill=v)])], kt, [], jetzt)[0][0]["ident"]
           for v in (31304.5, "31304.5", "31,304.50", "31304.50", 31304.49999, "31304.5000")}
    check(ids == {"NQZ6:buy:31304.50"}, f"TV: Schreibweisen des Einstiegs → ein ident ({ids})")
    P = ns["fp_preis_norm"]
    check(P(30801, "MNQZ6") == P("30,801.00", "MNQZ6") == "30801.00" and P(30801.13, "NQZ6") == "30801.25" and P(None) == "?"
          and P("abc") == "?" and P(1.23456, "ES") == "1.23", "fp_preis_norm: Tick 0,25 bei NQ/MNQ, sonst 2 Stellen, unlesbar „?“")

    # 7) Alarme: je Paar einmal, Hand gegen Hand nur an der kleineren id, schon gemeldete raus
    aktive = [{"id": 5, "alarm_keys": []}, {"id": 7, "alarm_keys": ["plan:p9"]}]
    k = [{"fremd_id": 5, "art": "plan", "gegen_id": "p1"}, {"fremd_id": 5, "art": "hand", "gegen_id": "7"},
         {"fremd_id": 7, "art": "hand", "gegen_id": "5"}, {"fremd_id": 7, "art": "plan", "gegen_id": "p9"},
         {"fremd_id": 8, "art": "plan", "gegen_id": "p2"}, {"fremd_id": 5, "art": "plan", "gegen_id": "p1"}]
    al = A(aktive, k)
    check([(x[0], x[1]) for x in al] == [(5, "plan:p1"), (5, "hand:5-7")],
          f"Alarme: plan:p1 + hand:5-7 einmal, plan:p9 schon gemeldet, unbekannte Zeile raus ({[(x[0], x[1]) for x in al]})")
    check(A([{"id": 5, "alarm_keys": ["plan:p1", "hand:5-7"]}, {"id": 7, "alarm_keys": []}], k[:3]) == [], "alles gemeldet → kein Alarm")

    print(f"{len(f) - sum(f)}/{len(f)} ok")
    sys.exit(1 if sum(f) else 0)


if __name__ == "__main__":
    main()
