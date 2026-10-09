#!/usr/bin/env python3
"""Selbsttest UNTER DEM BODEN = GEBLOWT (Finn 09.10.2026 ~07:00 Dubai, feste Regel; Anlass FN …0296 mit 90.002 $ nach SL-Kappung auf
genau den Boden). app.py: ap_konto_rechnen kappt den SL HINTER den Boden (+ AP_SL_HINTER_BODEN), ap_ende_unter_boden / _ap_blow_beim_abhaken
setzen beim „Erledigt" blown, wenn die End-Balance auf/unter dem Boden liegt, ap_planen lässt ein Konto mit als geblowt abgehaktem letztem
Trade aus. Rein rechnend bzw. mit nachgebauter DB, ohne Netz. Aufruf: python3 tools/selftest_boden_blow.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_wd_num", "ap_groesse", "_ap_spanne", "_ap_runden", "ap_kw_param", "_ap_boden", "ap_boden_konto", "ap_kette_regel",
              "ap_kette_mll", "ap_kette_trade1", "ap_konto_rechnen", "ap_klein_trade", "_ap_de", "liq_peak", "_ap_peaks", "ap_boden_sicher",
              "ap_ende_unter_boden", "ap_echte_balancen", "_ap_blow_beim_abhaken", "ap_balance_live", "ap_blow_ausschluss")
KONSTANTEN = ("AP_REST_MIN", "AP_REST_MIN_CFD", "AP_KLEIN_PKT", "AP_KLEIN_PUFFER", "AP_KLEIN_SCHRITT", "AP_KLEIN_TP_PKT_HINWEIS",
              "AP_PUFFER_PKT", "AP_CFD_ROUTEN", "AP_GROESSE_TOLERANZ", "AP_KETTE_STANDARD", "AP_KETTE_TXT", "AP_SL_HINTER_BODEN", "AP_TYPEN")
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
    # Werte frei erfunden — CFD-Firma, statischer Boden 10 % (100k → 90.000)
    regel = {"kauf_eur": 100, "route": "mt5v2", "boden": "statisch", "dd_pct": 10, "groessen": [100000],
             "ziel_pct": {"phase1": 10, "phase2": 5},
             "phasen": {"phase1": {"menge": [1, 1], "tp": [2000, 3000], "sl": [2000, 2500]},
                        "phase2": {"menge": [1, 1], "tp": [2000, 3000], "sl": [2000, 2500]}}}
    u = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}
    rechnen = ns["ap_konto_rechnen"]

    w, g = rechnen(regel, "phase1", 90002, u)
    check(w and w["sl"] == 2 + 50 and "hinter den Boden (+50 $)" in w["stufe"], f"Rest-Konto 90.002: SL 52 hinter den Boden ({w}, {g})")
    w, g = rechnen(regel, "phase1", 91000, u)
    check(w and w["sl"] == 1050 and w["risiko"] == 1050, f"91.000: SL 1.000 + 50 = 1.050, Risiko gleich ({w})")
    w, g = rechnen(regel, "phase1", 95000, u)
    check(w and w["sl"] == 2250 and "Boden" not in w["stufe"], f"95.000: SL normal 2.250, nicht gekappt ({w})")
    w, g = rechnen(regel, "phase1", 90000, u)
    check(w is None and "geblowt" in (g or ""), f"Balance auf dem Boden → kein Plan, „geblowt?“ ({g})")

    ende = ns["ap_ende_unter_boden"]
    check(ende(regel, "phase1", 90002, 89950) is True, "Ende 89.950 unter Boden 90.000 → geblowt")
    check(ende(regel, "phase1", 90100, 90000) is True, "Ende genau auf dem Boden → geblowt")
    check(ende(regel, "phase1", 92000, 90001) is False, "Ende 1 $ über dem Boden → nicht geblowt")
    check(ende(regel, "phase1", 92000, None) is False and ende(None, "phase1", 92000, 89000) is False, "ohne Balance/Regel → nie geraten")
    check(ende(regel, "phase1", 40000, 30000) is False, "Balance passt zu keiner Größe (kein Boden) → False")

    # _ap_blow_beim_abhaken mit nachgebauter DB
    db = {"accounts": [{"id": "k1", "firm": "TestFirma", "account_type": "phase1"}], "auto_plan_regeln": [{"regeln": {"firmen": [regel]}}]}
    ns["sb_select"] = lambda t, q: db.get(t, [])
    ns["ap_regel_finden"] = lambda firmen, firm: firmen[0] if firmen and firm == "TestFirma" else None
    ns["ap_regel_konto"] = lambda r, k, b: r
    blow = ns["_ap_blow_beim_abhaken"]
    p = {"id": "p1", "master_account_id": "k1", "mt5_baseline": {"tv": {"balance_start": 90200}}}
    check(blow(p, -250) is True, "Abhaken: Start 90.200 − 250 = 89.950 → blown")
    check(blow(p, +3000) is False, "Abhaken: TP-Treffer → nicht blown")
    p2 = {"id": "p2", "master_account_id": "k1", "mt5_baseline": {"balance_start": 92000, "final": {"balance_end": 89990}}}
    check(blow(p2, None) is True, "Abhaken: final.balance_end 89.990 unter Boden → blown (ohne master_pl)")
    check(blow({"id": "p3", "master_account_id": "k1", "mt5_baseline": {}}, -500) is False, "Abhaken ohne Start-Balance → nicht geraten")
    db["accounts"][0]["account_type"] = "funded"
    check(blow(p, -250) is False, "Abhaken: Funded-Konto (nicht AP_TYPEN) → kein automatisches blown")
    db["accounts"][0]["account_type"] = "phase1"
    ns["sb_select"] = lambda t, q: (_ for _ in ()).throw(ConnectionError("weg"))
    check(blow(p, -250) is False, "Abhaken: DB-Fehler → False, Abhaken läuft weiter")

    # Erledigt-Route + Planer am Quelltext
    check("blow_auto = (not blown) and bool(rows) and _ap_blow_beim_abhaken(rows[0], mpl)" in src and "elif blow_auto:" in src
          and src.index("blow_auto = (not blown)") < src.index("for _versuch in range(3):", src.index("blow_auto = (not blown)") - 400),
          "Erledigt-Route: Boden-Prüfung EINMAL vor der Retry-Schleife, setzt blown automatisch")
    check("if ap_blow_ausschluss(eig, _bw[0], _bw[3]):" in src and "master_tp,blown," in src, "Planer nutzt ap_blow_ausschluss")

    # Ausschluss mit Rückweg (Hinweis Prüfer T3): frische Lesung nach dem Blow → wieder planbar
    aus = ns["ap_blow_ausschluss"]
    blown_p = [{"ended_at": "2026-10-09T03:00:00+00:00", "blown": True}, {"ended_at": "2026-10-08T03:00:00+00:00", "blown": False}]
    check(aus(blown_p, 89950, "2026-10-09T02:00:00+00:00") is True, "letzter Trade blown, Lesung VOR dem Ende → ausgelassen")
    check(aus(blown_p, 89950, None) is True and aus(blown_p, None, None) is True, "letzter Trade blown, keine Lesung → ausgelassen")
    check(aus(blown_p, 100000, "2026-10-09T05:00:00+00:00") is False, "frische Lesung NACH dem Blow (Reset) → Ausschluss aufgehoben")
    check(aus([{"ended_at": "2026-10-09T03:00:00+00:00", "blown": False}, {"ended_at": "2026-10-08T03:00:00+00:00", "blown": True}], 95000, None) is False,
          "älterer Trade blown, letzter nicht → kein Ausschluss")
    check(aus([], 95000, None) is False, "ohne beendete Trades → kein Ausschluss")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
