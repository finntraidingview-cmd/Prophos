#!/usr/bin/env python3
"""Selbsttest Richtungsschutz — EINE Quelle der Wahrheit je ID+Firma (app.py ap_id_fest + ap_firma_key, 08.10.2026; Finn: „dass der
Trade-Planer nicht in Kollision kommt mit den Winning Days oder Trades bei Orbit oder Echo — dass er sich nicht selbst gegeneinander
hedgt") — ohne Netz. Aufruf: python3 tools/selftest_id_fest.py
Fälle: WD läuft long, Planer will short → fest long (nein) · WD bestätigt für 10 min später → fest · andere Firma → frei · gleiche Firma,
gleiche Richtung → erlaubt · Firmen-Schreibweise abweichend (MyFoundedFutures/MyFundedFutures, Apex/Apex Trader, The 5%ers) → erkannt ·
unbestätigter Vorschlag legt nichts fest · Plan in 45 min legt nichts fest · geclaimter Plan = „startet gerade"."""
import os
import re
import sys

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re}

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]

    def konst(name):
        return re.search(rf"^{name} = .*$", src, re.M).group(0)
    rules = src[src.index("_FIRM_RULES = ["):]
    rules = rules[:rules.index("]\n") + 1]
    exec("\n".join([konst(k) for k in ("AP_RS_NACHLAUF_MIN", "AP_ID_FEST_HORIZONT_MIN")] + [rules]
                   + [block(f) for f in ("_firm_norm", "_ap_norm", "ap_regel_finden", "ap_firma_key", "ap_id_fest")]), ns)
    return ns


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    FK = a["ap_firma_key"]
    firmen = [{"namen": ["Apex", "Apex Trader"]}, {"namen": ["Tradeify"]}, {"namen": ["The5%ers"]}]
    check(FK(firmen, "Apex Trader") == FK(firmen, "Apex") == "apex", "Regel-Firma: Apex / Apex Trader = ein Schlüssel")
    check(FK(firmen, "The 5%ers") == FK(firmen, "The5%ers") == FK([], "the5ers") == "the5ers", "The5%ers in drei Schreibweisen = ein Schlüssel")
    check(FK([], "MyFoundedFutures") == FK([], "MyFundedFutures") == "myfundedfutures", "MyFoundedFutures (Tippfehler in accounts) = MyFundedFutures")
    check(FK([], "FundedNext Futures") != FK([], "FundedNext") and FK([], "Founded Next") == FK([], "FundedNext"),
          "FundedNext Futures ≠ FundedNext (eigene Firma), Founded Next = FundedNext")

    IF = a["ap_id_fest"]
    U = "00000000-0000-0000-0000-0000000000a1"
    k = lambda f: f"{U}|{f}"
    wd_lauf = {"plan_id": "wd-1", "user_id": U, "firma_key": "tradeify", "richtung": "buy", "route": "tvv2", "typ": "winning_days"}
    # (1) WD läuft long → Tradeify dieser ID fest long: ein Planer-Short wäre ein Selbst-Hedge
    f1 = IF([wd_lauf], [], 600)
    check(f1.get(k("tradeify"), {}).get("richtung") == "buy" and f1[k("tradeify")]["durch"] == "läuft gerade", "WD läuft long → Tradeify fest long (Planer short = nein)")
    # (2) WD bestätigt für 10 min später (Hand-Plan des Farmers) → fest
    wd_plan = {"plan_id": "wd-2", "user_id": U, "firma_key": "tradeify", "richtung": "sell", "start_min": 610, "auto_plan": False, "bestaetigt": True}
    f2 = IF([], [wd_plan], 600)
    check(f2.get(k("tradeify"), {}).get("richtung") == "sell" and "startet in 10 min" in f2[k("tradeify")]["durch"], "WD-Plan startet in 10 min → fest (Planer long = nein)")
    # (3) andere Firma → frei
    check(k("apex") not in f1 and k("apex") not in f2, "andere Firma (Apex) bleibt frei")
    # (4) gleiche Firma, gleiche Richtung → fest, aber in derselben Richtung = erlaubt
    check(f1[k("tradeify")]["richtung"] == "buy", "gleiche Richtung wie der laufende WD → erlaubt (fest = buy)")
    # (5) unbestätigter Auto-Vorschlag legt nichts fest; bestätigter schon
    vorschlag = {"plan_id": "ap-1", "user_id": U, "firma_key": "tradeify", "richtung": "sell", "start_min": 605, "auto_plan": True, "bestaetigt": False}
    check(k("tradeify") not in IF([], [vorschlag], 600) and k("tradeify") in IF([], [dict(vorschlag, bestaetigt=True)], 600),
          "unbestätigter Vorschlag legt nichts fest, bestätigter Auto-Plan schon")
    # (6) Horizont: 45 min später → nicht fest; fällig vor 5 min → fest; vor 15 min (älter als Nachlauf) → nicht
    check(k("tradeify") not in IF([], [dict(wd_plan, start_min=645)], 600) and k("tradeify") in IF([], [dict(wd_plan, start_min=595)], 600)
          and k("tradeify") not in IF([], [dict(wd_plan, start_min=585)], 600), "Horizont 30 min vor / 10 min Nachlauf")
    # (7) geclaimter Plan = startet gerade; laufender Trade hat Vorrang vor geplantem
    f7 = IF([wd_lauf], [dict(wd_plan, fest_durch="schon gestartet")], 600)
    check(f7[k("tradeify")]["durch"] == "läuft gerade" and IF([], [dict(wd_plan, geclaimt=True)], 600)[k("tradeify")]["durch"] == "startet gerade",
          "geclaimt = startet gerade, laufender Trade hat Vorrang")
    # (8) alle Wege zählen: Echo V2, Topstep V2, altes mt5/dup, Orbit V3 — ohne Typ-Filter
    for route in ("mt5v2", "tsv2", "mt5", "dup", "tvv2"):
        f = IF([dict(wd_lauf, route=route, typ="funded")], [], 600)
        check(k("tradeify") in f, f"laufender Trade auf Weg {route} (Typ funded) legt fest")
    check(IF(None, None, "x") == {} and IF([], [], 600) == {}, "leer → {}")
    print("\nID-FEST:", "alles grün" if ok else "FEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
