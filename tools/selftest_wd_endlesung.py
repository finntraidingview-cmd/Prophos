#!/usr/bin/env python3
"""Selbsttest fuer PATCH /admin/wd-plaene {aktion:'endlesung'} + die Endlesungs-Felder in /admin/wd-heute (app.py, 25.09.2026)
— rein rechnend, ohne Flask/Netz.

Aufruf:  python3 tools/selftest_wd_endlesung.py
Laedt _wd_endlesung_signal und _wd_endlesung_zeile per Quelltext aus app.py (_wd_num aus derselben Datei). Prueft: review-Plan
ohne gelesenes Today's P&L → Signal-Zeile im Namen des Besitzers (aktion 'endlesung'); schon gelesen / nicht review / andere
Route / ohne Ende / ohne Besitzer / kein Plan → Fehler mit Code; die Zeile traegt nur die puls-Felder."""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {}
    for name in ("def _wd_num(", "def _wd_endlesung_signal(", "def _wd_endlesung_zeile("):
        i = src.index(name)
        exec(src[i:src.find("\n\n\n", i)], ns)
    return ns["_wd_endlesung_signal"], ns["_wd_endlesung_zeile"]


def main():
    sig, zeile = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    uid = "32b854d1-866f-4e7e-ba0b-9bf63df2d993"
    fin = {"at": "2026-09-25T01:11:14Z", "datum": "2026-09-25", "quelle": "level", "today_pnl": None,
           "puls_versuche": 2, "puls_fehler": "konto_nicht_erreicht: …", "master_pl_schaetzung": 273}
    plan = {"id": "772fa0c3-1d4a-4af9-b146-7c7166e4a804", "route": "tvv2", "status": "review", "user_id": uid,
            "mt5_baseline": {"final": fin, "hedge": {"status": "geschlossen"}}}
    z, f = sig(plan)
    check(f is None and z == {"user_id": uid, "plan_id": plan["id"], "status": "wartet",
                              "params": {"aktion": "endlesung", "von": "admin"}}, "review ohne Zahl → Signal im Namen des Besitzers")
    z, f = sig(dict(plan, mt5_baseline={"final": dict(fin, today_pnl=271.5, quelle="puls")}))
    check(z is None and f[0] == 409 and "schon gelesen" in f[1], "schon gelesen → 409")
    z, f = sig(dict(plan, mt5_baseline={"final": dict(fin, today_pnl=0)}))
    check(z is None and f[0] == 409, "Today's P&L 0 zählt als gelesen → 409")
    check(sig(dict(plan, status="completed"))[1][0] == 409, "abgehakt → 409")
    # noch offen (seit 28.09.2026, Knopf „Beendet"): Signal mit pruefen — der PC prüft erst, ob die Position zu ist
    z, f = sig(dict(plan, status="open"))
    check(f is None and z["params"] == {"aktion": "endlesung", "von": "admin", "pruefen": True}, "noch offen → Signal mit pruefen")
    # 30.09.2026: Echo nie (P&L aus der MT5-Balance), Topstep V2 nur von Puls gestartet (tv.puls == 'tsx'), andere Wege nie
    check(sig(dict(plan, route="mt5v2"))[1][0] == 409, "Echo V2 → 409 (kein Lese-Weg über Puls)")
    check(sig(dict(plan, route="tsv2"))[1][0] == 409, "Topstep-Handplan → 409")
    z, f = sig(dict(plan, route="tsv2", mt5_baseline={"final": fin, "tv": {"puls": "tsx"}}))
    check(f is None and z["params"]["aktion"] == "endlesung", "Topstep V2 von Puls gestartet → Signal")
    check(sig(dict(plan, route="dup"))[1][0] == 409, "andere Route → 409")
    check(sig(dict(plan, mt5_baseline={}))[1][0] == 409, "ohne Ende → 409")
    check(sig(dict(plan, mt5_baseline=None))[1][0] == 409, "Baseline null → 409")
    check(sig(dict(plan, user_id=None))[1][0] == 409, "ohne Besitzer → 409")
    check(sig(None)[1][0] == 404, "kein Plan → 404")
    zl = zeile(dict(fin, puls_diagnose={"reiter": ["Positions@10,500"]}, exit_fill={"preis": 30812.25, "menge": 2, "seite": "sell"},
                    master_pl_schaetzung=273, hedge_pl=-94.29))
    check(zl and zl["puls_versuche"] == 2 and zl["exit_fill"]["preis"] == 30812.25 and "puls_diagnose" in zl
          and "master_pl_schaetzung" not in zl and "hedge_pl" not in zl and "today_pnl" not in zl, "Zeile: nur puls-Felder, None weggelassen")
    check(zeile(None) is None and zeile({}) is None and zeile({"hedge_pl": 1}) is None, "ohne puls-Felder → None")
    zb = zeile(dict(fin, puls_login_fehler=2, puls_login_at="2026-09-30T11:05:00Z", puls_login_code="login_unlesbar"))
    check(zb and zb["puls_login_fehler"] == 2 and zb["puls_login_at"] == "2026-09-30T11:05:00Z" and zb["puls_login_code"] == "login_unlesbar",
          "Login-Bremse (30.09.2026): Zähler, Zeit und Code kommen im Auszug mit (Radar „Wartet · Login prüfen“)")
    print("\nOK" if ok else "\nFEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
