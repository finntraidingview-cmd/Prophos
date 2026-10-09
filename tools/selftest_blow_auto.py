#!/usr/bin/env python3
"""Selbsttest GEBLOWT AUTOMATISCH ABHAKEN (Finn über Master 09.10.2026 ~20:45 Dubai, Fall Echo-V2-Challenge mit MT5-Balance nach dem Trade
unter dem Boden, die in „Überprüfen" stehen blieb). app.py: ap_echte_balancen (nur echte Lesungen), ap_blow_auto_pruefen (rein rechnend),
_ap_blow_beim_abhaken liest jetzt auch Echo V2, ap_loop ruft ap_blow_auto_tick. Werte frei erfunden, ohne Netz.
Aufruf: python3 tools/selftest_blow_auto.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_wd_num", "ap_groesse", "_ap_spanne", "_ap_runden", "ap_kw_param", "_ap_boden", "ap_boden_konto", "ap_kette_regel",
              "ap_regel_konto", "ap_ende_unter_boden", "ap_echte_balancen", "ap_blow_auto_pruefen", "_ap_blow_beim_abhaken")
KONSTANTEN = ("AP_TYPEN", "AP_KETTE_STANDARD", "AP_GROESSE_TOLERANZ", "AP_BLOW_AUTO_ROUTEN")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re}
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in KONSTANTEN]
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns, src


def main():
    ns, src = lade()
    # CFD-Firma, statischer Boden 10 % (100k → 90.000)
    regel = {"kauf_eur": 100, "route": "mt5v2", "boden": "statisch", "dd_pct": 10, "groessen": [100000],
             "ziel_pct": {"phase1": 10, "phase2": 5},
             "phasen": {"phase1": {"menge": [1, 1], "tp": [2000, 3000], "sl": [2000, 2500]},
                        "phase2": {"menge": [1, 1], "tp": [2000, 3000], "sl": [2000, 2500]}}}
    acc = {"id": "k1", "user_id": "u1", "firm": "TestFirma", "account_type": "phase2"}
    echo = lambda **kw: dict({"id": "p1", "route": "mt5v2", "status": "review", "blown": False, "master_account_id": "k1",
                              "mt5_baseline": {"master_balance": 90180.0, "bal_nach": {"ok": True, "balance": 89940.0},
                                               "final": {"master_balance": 89940.0}}}, **kw)
    echt, pr = ns["ap_echte_balancen"], ns["ap_blow_auto_pruefen"]

    check(echt(echo()) == (90180.0, 89940.0, "mt5_nachlesung"), f"Echo V2: vorher master_balance, nachher bal_nach ({echt(echo())})")
    p = echo(mt5_baseline={"master_balance": 90180.0, "bal_nach": {"ok": False, "balance": 1.0}, "final": {"master_balance": 89940.0}})
    check(echt(p) == (90180.0, 89940.0, "mt5_final"), "Echo V2: Nachlesung nicht ok → final.master_balance")
    check(echt(echo(mt5_baseline={"final": {"master_balance": 89940.0}})) is None, "Echo V2 ohne Balance vorher → None")
    orbit = lambda q: {"id": "p2", "route": "tvv2", "status": "review", "mt5_baseline": {"tv": {"balance_start": 90180.0},
                                                                                       "final": {"quelle": q, "balance_end": 89940.0}}}
    check(echt(orbit("puls")) == (90180.0, 89940.0, "puls"), "Orbit V2: Puls-Endlesung zählt")
    check(all(echt(orbit(q)) is None for q in ("demo", "hand", "level", "reader_leer", "close", None)),
          "Orbit V2: Demo/Hand/Level/Reader/close → nie")
    check(echt({"route": "tsv2", "mt5_baseline": {"tv": {"balance_start": 1}, "final": {"quelle": "puls", "balance_end": 1}}}) is None,
          "Topstep V2 → nicht hier (eigene MLL-Kette)")

    k = pr(echo(), acc, regel)
    check(k is not None and k["boden"] == 90000.0 and k["pl"] == -240.0 and k["nachher"] == 89940.0,
          f"Ausgangsfall: 89.940 ≤ Boden 90.000 → geblowt, P&L −240 ({k})")
    k = pr(echo(mt5_baseline={"master_balance": 90180.0, "bal_nach": {"ok": True, "balance": 90000.0}}), acc, regel)
    check(k is not None and k["nachher"] == 90000.0, "genau auf dem Boden → geblowt")
    check(pr(echo(mt5_baseline={"master_balance": 90180.0, "bal_nach": {"ok": True, "balance": 90000.01}}), acc, regel) is None,
          "1 Cent über dem Boden → nicht geblowt")
    check(pr(echo(status="completed"), acc, regel) is None and pr(echo(status="open"), acc, regel) is None, "nur Überprüfen (review)")
    check(pr(echo(blown=True), acc, regel) is None, "schon blown → nichts")
    check(pr(echo(), dict(acc, account_type="funded"), regel) is None, "Funded (nicht AP_TYPEN) → nichts")
    check(pr(echo(konto_typ="phase1"), dict(acc, account_type="funded"), regel) is not None, "konto_typ des Plans geht vor dem Kontotyp")
    check(pr(echo(), acc, None) is None and pr(echo(), None, regel) is None, "ohne Regel/Konto → nie geraten")
    check(pr(echo(), acc, dict(regel, kette={"tagesziel": 4500})) is None, "Firma mit Topstep-Kette → nichts (eigene MLL-Logik)")
    p = echo(); p["mt5_baseline"] = dict(p["mt5_baseline"], hedge={"status": "zu"})
    check(pr(p, acc, regel) is None, "Plan mit Hedge → bleibt beim Abhaken von Hand")
    check(pr(dict(orbit("demo"), master_account_id="k1"), acc, regel) is None, "Orbit mit Demo-Ende → nie automatisch")
    check(pr(dict(orbit("puls"), master_account_id="k1"), acc, regel) is not None, "Orbit mit Puls-Endlesung unter dem Boden → geblowt")

    # Klick-Weg „Erledigt" liest jetzt auch Echo V2 (vorher nur tv.balance_start / final.balance_end)
    db = {"accounts": [dict(acc)], "auto_plan_regeln": [{"regeln": {"firmen": [regel]}}]}
    ns["sb_select"] = lambda t, q: db.get(t, [])
    ns["ap_regel_finden"] = lambda firmen, firm: firmen[0] if firmen and firm == "TestFirma" else None
    check(ns["_ap_blow_beim_abhaken"](echo(), None) is True, "Erledigt-Klick bei Echo V2 unter dem Boden → blown")
    check(ns["_ap_blow_beim_abhaken"](echo(mt5_baseline={"master_balance": 90180.0, "bal_nach": {"ok": True, "balance": 91000.0}}), None) is False,
          "Erledigt-Klick bei Echo V2 über dem Boden → nicht blown")

    # Verdrahtung am Quelltext
    check("ap_blow_auto_tick()" in src[src.index("\ndef ap_loop("):src.index("\ndef start_auto_planer(")], "ap_loop ruft ap_blow_auto_tick")
    t = src[src.index("\ndef _ap_blow_auto_abhaken("):src.index("\ndef ap_blow_auto_tick(")]
    check('{"id": f"eq.{pid}", "status": "eq.review", "blown": "not.is.true"}' in t and 'upd["blown"] = True' in t,
          "Abhaken nur mit Sperre: noch review und nicht blown")
    check('_konto_archiv_eintragen(uid, aid, "blown"' in t and "push_an_user(" in t, "Archiv als blown + Push an Inhaber/Admins")
    check('_konto_archiv_eintragen(uid, aid, "blown" if blown else "passed_pending"' in src, "Erledigt-Route nutzt denselben Archiv-Helfer")
    check('orbit_v3,blown")' in src and '"blown": bool(p.get("blown"))})' in src, "Radar-Zeile trägt blown (Chip auch bei Echo)")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
