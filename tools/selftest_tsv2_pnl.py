#!/usr/bin/env python3
"""Selbsttest TSV2-PNL (app.py, 01.10.2026) — rein rechnend, ohne Flask/Netz.

Aufruf:  python3 tools/selftest_tsv2_pnl.py
Laedt wd_tsx_master_pl, _wd_endlesung_signal, _wd_endlesung_zeile und puls_ergebnis_saeubern per Quelltext aus app.py.
Prueft: Topstep-V2-P&L = Balance nachher − vorher bei gleicher Basis (auch Express 0-basiert), sonst RP&L ab dem Klick am selben
Handelstag, NIE der Tages-RP&L allein; „Jetzt lesen" bei tsv2 erst mit balance_end gesperrt; die Endlesungs-Zeile traegt balance_end;
puls_ergebnisse behalten balance/balance_relativ/upl/summary. Nur erfundene Kennungen."""
import json
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "json": json}

    def zeile(name):
        i = src.index("\n" + name + " = ") + 1
        j = i
        while True:   # Zuweisung ueber mehrere Zeilen (Tupel) bis zur schliessenden Klammer
            j = src.index("\n", j) + 1
            teil = src[i:j]
            if teil.count("(") <= teil.count(")"):
                return teil

    for name in ("PULS_ERGEBNIS_MAX", "PULS_ERGEBNIS_FELDER", "_PLAN_ID_MUSTER"):
        exec(zeile(name), ns)
    for name in ("def _wd_num(", "def wd_tsx_master_pl(", "def _wd_endlesung_signal(", "def _wd_endlesung_zeile(",
                 "def puls_ergebnis_saeubern("):
        i = src.index(name)
        exec(src[i:src.find("\n\n\n", i)], ns)
    return ns


def main():
    ns = lade()
    mpl, sig, ez, saeubern = ns["wd_tsx_master_pl"], ns["_wd_endlesung_signal"], ns["_wd_endlesung_zeile"], ns["puls_ergebnis_saeubern"]
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    tag = "2026-10-01"
    # 1) Balance-Differenz, gleiche Basis (Combine absolut, Express relativ)
    r = mpl({"balance_start": 50000, "balance_relativ": False, "today_pnl_start": 0, "datum_start": tag},
            {"balance_end": 50320, "balance_relativ": False, "today_pnl": 999, "datum": tag})
    check(r and r["wert"] == 320 and r["art"] == "balance", f"Combine: Balance 50.320 − 50.000 = 320 (nicht Tages-RP&L 999) → {r}")
    r = mpl({"balance_start": 0, "balance_relativ": True, "today_pnl_start": 200, "datum_start": tag},
            {"balance_end": -300, "balance_relativ": True, "today_pnl": -100, "datum": tag})
    check(r and r["wert"] == -300 and r["art"] == "balance", f"Express ab 0: −300 − 0 = −300 → {r}")
    # 2) Basis verschieden → RP&L ab dem Klick
    r = mpl({"balance_start": 50000, "balance_relativ": False, "today_pnl_start": 200, "datum_start": tag},
            {"balance_end": -300, "balance_relativ": True, "today_pnl": -100, "datum": tag})
    check(r and r["wert"] == -300 and r["art"] == "rpl_start", f"Basis verschieden → RP&L −100 − 200 = −300 → {r}")
    # 3) Altplan nur mit rpl_start
    r = mpl({"rpl_start": 150, "datum_start": tag}, {"today_pnl": 400, "datum": tag})
    check(r and r["wert"] == 250 and r["art"] == "rpl_start", f"Altplan rpl_start 150, Ende 400 → 250 → {r}")
    # 4) nie der Tages-RP&L allein
    check(mpl({}, {"today_pnl": 450, "datum": tag}) is None, "ohne Start → None (kein Tages-RP&L als Trade-P&L)")
    check(mpl({"today_pnl_start": 100, "datum_start": "2026-09-30"}, {"today_pnl": 450, "datum": tag}) is None,
          "Start an anderem Handelstag → None")
    check(mpl({"balance_start": 0}, {}) is None and mpl(None, None) is None, "ohne Ende → None")
    # 5) Signal „Jetzt lesen": tsv2 erst mit balance_end gesperrt
    uid = "00000000-0000-4000-8000-00000000abcd"
    base = {"tv": {"puls": "tsx"}}
    plan = {"id": "pppp1111-0000-4000-8000-000000000001", "route": "tsv2", "status": "review", "user_id": uid,
            "mt5_baseline": dict(base, final={"today_pnl": -100, "quelle": "puls", "datum": tag, "at": "2026-10-01T10:00:00Z"})}
    z, f = sig(plan)
    check(f is None and z and z["params"]["aktion"] == "endlesung", f"tsv2 nur mit Tages-RP&L → Signal geht raus ({z}, {f})")
    plan["mt5_baseline"]["final"]["balance_end"] = -300
    z, f = sig(plan)
    check(z is None and f and f[0] == 409 and "Balance" in f[1], f"tsv2 mit balance_end → 409 ({f})")
    tv_plan = {"id": "pppp2222-0000-4000-8000-000000000002", "route": "tvv2", "status": "review", "user_id": uid,
               "mt5_baseline": {"final": {"today_pnl": 450, "datum": tag}}}
    z, f = sig(tv_plan)
    check(z is None and f and f[0] == 409 and "Today" in f[1], f"tvv2 mit Today's P&L → 409 wie bisher ({f})")
    # 6) Endlesungs-Zeile traegt die Balance
    e = ez({"today_pnl": -100, "balance_end": -300, "balance_relativ": True, "plattform": "tsx", "quelle": "puls", "geheim": 1})
    check(e and e.get("balance_end") == -300 and e.get("balance_relativ") is True and e.get("plattform") == "tsx" and "geheim" not in e,
          f"Endlesungs-Zeile: balance_end/relativ/plattform, sonst nichts Fremdes → {e}")
    # 7) puls_ergebnisse behalten die TopstepX-Balance
    row = saeubern({"plan_id": "pppp1111-0000-4000-8000-000000000001", "art": "close", "stufe": "ende",
                    "ergebnis": {"ok": True, "balance": -300.0, "balance_relativ": True, "upl": 0.0,
                                 "summary": {"BAL": "$-300.00"}, "fremd": "weg"}}, "pc-xxxxxx")
    erg = (row or {}).get("ergebnis") or {}
    check(erg.get("balance") == -300.0 and erg.get("balance_relativ") is True and erg.get("upl") == 0.0
          and erg.get("summary") == {"BAL": "$-300.00"} and "fremd" not in erg, f"puls_ergebnisse: balance/relativ/upl/summary bleiben → {erg}")

    print("\nALLES GRUEN" if ok else "\nFEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
