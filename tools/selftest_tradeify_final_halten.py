#!/usr/bin/env python3
"""Selbsttest FINALER TRADEIFY HALTEN (app.py ap_tradeify_final_halten, 29.10.2026). Rein rechnend, ohne Netz.
Aufruf: python3 tools/selftest_tradeify_final_halten.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re}
    teile = [re.search(r"^TFH_STANDARD = .*$", src, re.M).group(0), re.search(r"^TFH_SLAVE_PPL = .*$", src, re.M).group(0)]
    for name in ("_wd_num", "_ist_tradeify_cfd", "tfh_param", "ap_plan_final_text", "tfh_hedge", "ap_tradeify_final_halten"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def main():
    ns = lade()
    h = ns["ap_tradeify_final_halten"]
    f = []
    ok = lambda b, t: f.append(t) if not b else None   # noqa: E731
    letzt = {"stufe": "letzter Trade (Rest bis Ziel)", "rest": 1979, "tp": 2039}
    etappe = {"stufe": "Etappe", "rest": 9000, "tp": 3500}
    ok(h({}, "Tradeify", letzt) is True, "letzter Trade Tradeify → halten (Schalter fehlt = an)")
    ok(h({"tradeify_final_halten": True}, "Tradeify", letzt) is True, "Schalter an → halten")
    ok(h({"tradeify_final_halten": False}, "Tradeify", letzt) is False, "Schalter aus → planen")
    ok(h({}, "Tradeify CFD", letzt) is False, "Tradeify CFD nie")
    ok(h({}, "Apex Trader", letzt) is False, "andere Firma nie")
    ok(h({}, "Tradeify", etappe) is False, "Etappe nicht final")
    ok(h({}, "Tradeify", {"stufe": "Etappe", "rest": 2000, "tp": 2039}) is True, "Etappe mit TP ≥ Rest → final")
    ok(h({}, "Tradeify", {"stufe": "Etappe", "rest": 0, "tp": 500}) is True, "Rest 0 → final")
    ok(h({}, "Tradeify", {"stufe": "Tage sammeln 3/5", "rest": 100, "tp": 300}) is False, "Tage sammeln nie")
    ok(h({}, "Tradeify", {"stufe": "Klein-Trade · Rest 84 $", "rest": 84, "tp": 120}) is True, "Klein-Trade final")
    ok(h({}, "Tradeify", {"stufe": "Etappe", "tp": 3000}) is False, "ohne Rest nicht final")
    # Gegenhedge-Weg (Erweiterung 29.10.2026)
    ok(h({"tradeify_final_hedge": {"an": True}}, "Tradeify", letzt) is False, "Hedge-Weg an → Planer plant finale wieder (tfh_tick stellt um)")
    tp_ = ns["tfh_param"]
    ok(tp_({})["an"] is False and tp_({"tradeify_final_hedge": {"an": True, "max_lots": 40}})["max_lots"] == 40.0, "tfh_param Standard/Werte")
    ok(tp_({"tradeify_final_hedge": {"an": "ja", "netto_faktor": 3}})["an"] is False and tp_({"tradeify_final_hedge": {"netto_faktor": 3}})["netto_faktor"] == 0.89,
       "tfh_param: nur an=True, Ungültiges → Standard")
    pf = ns["ap_plan_final_text"]
    ok(pf("Auto-Planer · letzter Trade (Rest bis Ziel) · Rest 1.979 $ bis Ziel · Balance 157.021 (TV)", 2039) is True, "Notiz letzter Trade")
    ok(pf("Auto-Planer · Etappe · Rest 9.000 $ bis Ziel · Balance 150.000 (TV)", 3500) is False, "Notiz Etappe")
    ok(pf("Auto-Planer · Etappe · Rest 2.000 $ bis Ziel", 2039) is True, "Etappe mit TP ≥ Rest")
    ok(pf("Auto-Planer · Tage sammeln 3/5 · Rest 100 $ bis Ziel", 500) is False, "Tage sammeln")
    ok(pf("Hand-Plan", 500) is None, "ohne Notiz → None")
    th = ns["tfh_hedge"]
    # 157k: Kontowert ≈ 595,4 € bei Polster 4.500 $ → Satz 0,13231 €/$; q = Satz ÷ 0,89 → Blow ≈ +669 €
    g, grund = th(595.4 / 4500, 4500, 2, 20.0, 2039)
    ok(grund is None and abs(g["slave_risk"] - 669.0) < 1.0, f"Blow ≈ +669 €: {g}")
    ok(g and abs(g["lots"] - 7.0) < 0.05 and abs(g["multiplier"] - 3.4986) < 0.01, f"Lots ≈ 7,0 / multiplier: {g}")
    ok(g and 290 < g["hedge_eur"] < 310 and g["master_risk"] == 4500, f"Pass ≈ −300 €, master_risk = Polster: {g}")
    # gleiche Lots wie der PC-Tab (hedgeMultAusRisiko): lots = slave_risk ÷ (0,85 × master_risk ÷ (ppl × kt))
    ok(g and abs(g["slave_risk"] / (0.85 * 4500 / (20 * 2)) - g["lots"]) < 0.01, "Lots wie hedgeMultAusRisiko")
    ok(th(None, 4500, 2, 20.0, 2039)[0] is None and th(0.13, None, 2, 20.0, 2039)[0] is None and th(0.13, 4500, 2, 20.0, None)[0] is None,
       "fehlende Werte → Grund")
    ok(th(0.0001, 4500, 1, 2.0, 100)[0] is None, "zu klein → Grund (min_lot)")

    if f:
        print("ROT:\n  " + "\n  ".join(f))
        sys.exit(1)
    print("OK — ap_tradeify_final_halten grün")


if __name__ == "__main__":
    main()
