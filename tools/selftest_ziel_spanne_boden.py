#!/usr/bin/env python3
"""Selbsttest BLOW-GRENZE FÜR DIE ZIEL-SPANNE (Finn 08.10.2026, Radar „Überprüfen": „wo stehe ich jetzt, wie viel fehlt noch").
Die Ziel-Wache (zw_tick) legt je Konto neben dem Ziel die Blow-Grenze ab (_zw["boeden"]) — dieselbe Kernwerte-Rechnung wie der
Trade-Planer (ap_regel_konto → ap_boden_sicher → ap_boden_konto). Die Radar-Zeile trägt sie als boden_usd (v. a. Echo ohne Liq).
Prüffälle aus der DB vom 08.10.2026 (Platzhalter statt Kontonummern): FN 100k statisch → 90.000; FP 50k Flex (Max-DD 12 %) → 44.000;
FN 100k Phase 1 → Ziel 108.000. Dazu der Ziel-Wache-Fix (zw_ziel mit je_groesse wie ap_konto_rechnen): FP Flex 50k → 55.000,
100k Flex → 110.000, 100k Standard → 108.000 unverändert. Rein rechnend, ohne Netz. Aufruf: python3 tools/selftest_ziel_spanne_boden.py"""
import json
import os
import re
import sys

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
FN = {"boden": "statisch", "namen": ["fundednext"], "dd_pct": 10, "groessen": [50000, 100000], "wert_groessen": [50000, 100000],
      "kauf_eur": {"50000": 261, "100000": 500}, "ziel_pct": {"phase1": 8, "phase2": 5},
      "phasen": {"phase1": {"ziel_pct": 8, "boden_pct": 10}, "phase2": {"ziel_pct": 5, "boden_pct": 10}},
      "je_groesse": {"50000": {"phasen": {"phase1": {"boden_pct": 10}, "phase2": {"boden_pct": 10}}}}}
FP = {"boden": "statisch", "namen": ["fundingpips"], "dd_pct": 10, "groessen": [50000, 100000], "wert_groessen": [50000, 100000],
      "kauf_eur": {"50000": 240, "100000": 464}, "ziel_pct": {"phase1": 8, "phase2": 5}, "je_groesse": {}, "standard_groessen": [100000],
      "phasen": {"phase1": {"tp_max": 4000, "ziel_pct": 8, "boden_pct": 10}, "phase2": {"tp_max": 2500, "ziel_pct": 5, "boden_pct": 10}},
      "flex": {"dd_pct": 12, "ab_dd_pct": 12, "je_groesse": {
          "50000": {"dd_pct": 12, "ziel_pct": {"phase1": 10, "phase2": 5}, "phasen": {"phase1": {"boden_pct": 12}, "phase2": {"boden_pct": 12}}},
          "100000": {"dd_pct": 12, "ziel_pct": {"phase1": 10, "phase2": 5}, "phasen": {"phase1": {"boden_pct": 12}, "phase2": {"boden_pct": 12}}}}}}


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "json": json, "print": print}

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]
    for k in ("AP_KW_FUNDED", "AP_KW_PHASEN", "AP_TYPEN", "AP_GROESSE_TOLERANZ"):
        exec(re.search(rf"^{k} = .*$", src, re.M).group(0), ns)
    for f in ("_wd_num", "_ap_norm", "ap_regel_finden", "ap_groesse", "ap_kw_param", "ap_konto_flex", "ap_regel_flex", "ap_regel_konto",
              "_ap_boden", "ap_boden_konto", "ap_boden_sicher", "zw_ziel"):
        exec(block(f), ns)
    return ns, src


def main():
    ns, src = lade()
    f = []

    def check(ok, name):
        f.append(0 if ok else 1)
        print(("OK  " if ok else "FEHL") + " " + name)
    firmen = [FN, FP]
    faelle = (("k-fn-p2", "FundedNext", "phase2", 90177.1, 10000, 105000.0, 90000.0),
              # Ziel-Wache-Fix 08.10.2026: FP 50k Flex P1 = 10 % (je_groesse) → 55.000, nicht 8 % = 54.000 wie die Firma
              ("k-fp-50", "FundingPips", "phase1", 45556.54, 6000, 55000.0, 44000.0),
              ("k-fp-100f", "FundingPips", "phase1", 101200.0, 12000, 110000.0, 88000.0),    # 100k Flex (Max-DD 12 %): Ziel 10 %, Boden 88.000
              ("k-fp-100s", "FundingPips", "phase1", 101200.0, 10000, 108000.0, 90000.0),    # 100k Standard: unverändert 8 % / 90.000
              ("k-fn-p1", "FundedNext", "phase1", 107963.98, 10000, 108000.0, 90000.0))
    for kid, firm, typ, bal, mdd, ziel_soll, boden_soll in faelle:
        a = {"id": kid, "firm": firm, "account_type": typ, "max_drawdown": mdd}
        regel = ns["ap_regel_konto"](ns["ap_regel_finden"](firmen, firm), a, bal)
        zg = ns["zw_ziel"](regel, typ, bal)
        bk = ns["ap_boden_sicher"](None, a, bal, regel=regel)
        boden = bk.get("boden") if bk.get("boden") is not None else bk.get("boden_min")
        check(zg and zg[0] == ziel_soll and boden == boden_soll, f"{firm} {typ} Balance {bal:,.0f} → Ziel {zg and zg[0]} · Blow {boden}".replace(",", "."))
    # Verdrahtung: zw_tick legt boeden ab, die Radar-Zeile gibt boden_usd mit
    check(re.search(r'_zw\["boeden"\]\[aid\] = ', src) is not None and '"boden_usd": (_zw.get("boeden") or {})' in src,
          "zw_tick legt _zw[\"boeden\"] ab, _wd_heute_zeile gibt boden_usd mit")
    print(f"{len(f) - sum(f)}/{len(f)} ok")
    sys.exit(1 if sum(f) else 0)


if __name__ == "__main__":
    main()
