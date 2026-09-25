#!/usr/bin/env python3
"""Selbsttest fuer den vierten Kontotyp 'winning_days' (app.py, 25.09.2026) — rein rechnend, ohne Flask.

Aufruf:  python3 tools/selftest_kontotyp_wd.py
Laedt _hq_typ, _hq_typ_trade, _hq_anteil per Quelltext aus app.py. Prueft: winning_days → 'wd' in jedem
Fall (Haken false, Risiko 4.500 $), Funded mit Haken/Faustregel wie bisher, Challenge unveraendert,
Reibungs-Anteil fuer wd/winning_days wie Funded."""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re}

    def block(name):
        i = src.index(f"def {name}(")
        j = src.find("\n\n\n", i)
        return src[i:j]

    def const(name):
        return re.search(rf"^{name} = .*$", src, re.M).group(0)

    exec("\n".join([const("HQ_REIB_ANTEIL_FUNDED"), const("HQ_REIB_ANTEIL_SONST"), const("HQ_WD_RISK"),
                    block("_hq_typ"), block("_hq_typ_trade"), block("_hq_anteil")]), ns)
    return ns


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    wd_acc, fu_acc, ch_acc = {"account_type": "winning_days"}, {"account_type": "funded"}, {"account_type": "challenge"}
    check(a["_hq_typ"](wd_acc) == "wd" and a["_hq_typ"](fu_acc) == "funded" and a["_hq_typ"]({"account_type": "Winning_Days "}) == "wd"
          and a["_hq_typ"]({}) == "—", "_hq_typ: winning_days → wd (auch mit Groß-/Leerzeichen), sonst Kontotyp")
    check(a["_hq_typ_trade"](wd_acc, {"winning_day": False, "master_risk": 4500}) == "wd"
          and a["_hq_typ_trade"](wd_acc, {}) == "wd", "winning_days-Konto: jeder Trade 'wd', Haken false und Risiko 4.500 $ ändern nichts")
    check(a["_hq_typ_trade"](fu_acc, {"winning_day": True, "master_risk": 4500}) == "wd"
          and a["_hq_typ_trade"](fu_acc, {"master_risk": 400}) == "wd"
          and a["_hq_typ_trade"](fu_acc, {"master_risk": 4500}) == "funded"
          and a["_hq_typ_trade"](fu_acc, {"winning_day": False, "master_risk": 400}) == "funded",
          "Funded-Konto: Haken schlägt Faustregel, Faustregel < 1.000 $ → wd, sonst funded (Hedge-Ära-Bestand)")
    check(a["_hq_typ_trade"](ch_acc, {"master_risk": 400}) == "challenge", "Challenge bleibt Challenge")
    # Kontotyp zum Zeitpunkt des Trades (25.09.2026): konto_typ am Plan schlägt den heutigen Kontotyp
    check(a["_hq_typ_trade"](wd_acc, {"konto_typ": "funded", "master_risk": 0, "master_pl": 10900}) == "funded",
          "Mikes Trade 2ff62bb5: Konto heute winning_days, konto_typ funded, +10.900 $ → funded")
    check(a["_hq_typ_trade"](wd_acc, {"konto_typ": "funded", "master_risk": 400}) == "wd",
          "konto_typ funded + Risiko 400 $ → Faustregel wie früher: wd")
    check(a["_hq_typ_trade"](fu_acc, {"konto_typ": "winning_days", "master_risk": 4500}) == "wd"
          and a["_hq_typ_trade"](wd_acc, {"konto_typ": None}) == "wd" and a["_hq_typ_trade"](ch_acc, {"konto_typ": "challenge"}) == "challenge",
          "konto_typ winning_days → wd; ohne konto_typ Rückfall auf den heutigen Kontotyp")
    check(a["_hq_anteil"]("winning_days") == a["_hq_anteil"]("wd") == a["_hq_anteil"]("funded") == 1.0
          and a["_hq_anteil"]("challenge") == 0.5, "Reibungs-Anteil: wd/winning_days wie Funded 1,0, Challenge 0,5")
    # HQ_VORGABEN + Firmen-Normierung (25.09.2026): FundedNext|funded = 4.000 $ ≙ 850 €, FundedNext Futures bleibt eigene Firma ohne Vorgabe
    src = open(APP, encoding="utf-8").read()

    def zuweisung(name):
        i = src.index(f"\n{name} = ") + 1
        auf = src.index(src[src.index("=", i) + 2], i)   # erstes Klammerzeichen nach „= "
        tiefe, j = 0, auf
        paare = {"{": "}", "[": "]", "(": ")"}
        zu = paare[src[auf]]
        while True:
            if src[j] == src[auf]:
                tiefe += 1
            elif src[j] == zu:
                tiefe -= 1
                if tiefe == 0:
                    return src[i:j + 1]
            j += 1
    ns = {"re": re}
    exec(zuweisung("HQ_VORGABEN") + "\n" + zuweisung("_FIRM_RULES"), ns)
    i = src.index("def _firm_norm(")
    exec(src[i:src.find("\n\n\n", i)], ns)
    V, FN = ns["HQ_VORGABEN"], ns["_firm_norm"]
    check(V.get("FundedNext|funded") == {"ziel_usd": 4000.0, "ziel_eur": 850.0}, "Vorgabe FundedNext · Funded = 4.000 $ ≙ 850 €")
    check(FN("FundedNext") == "FundedNext" and FN("FundedNext Futures") == "FundedNext Futures"
          and "FundedNext Futures|funded" not in V, "FundedNext Futures bleibt eigene Firma, keine Vorgabe")
    check("Topstep|wd" not in V, "Topstep · Winning Day bleibt auskommentiert, bis Finn den Wert bestätigt")

    print("\n" + ("alle Tests bestanden" if ok else "FEHLER"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
