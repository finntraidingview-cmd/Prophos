#!/usr/bin/env python3
"""Selbsttest Bulk-Vorlagen (app.py, BULK-VORLAGEN, 27.09.2026, B11) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_bulk_vorlagen.py
Prueft bulk_vorlage_pruefen: nur Tabellen-Spalten, Typen, name Pflicht, Leeren mit ''/None, fehlende Schluessel bleiben weg."""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    i = src.index("BULK_VORLAGE_TEXT = (")
    j = src.index("@app.route(\"/admin/bulk-vorlagen\"", i)
    ns = {"re": re}
    exec(src[i:j], ns)
    return ns


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    p = a["bulk_vorlage_pruefen"]
    b, f = p({"name": " Tradeify 150k Funded ", "firm": "Tradeify", "account_type": "funded", "account_size": "150000",
              "max_drawdown": 4500, "purchase_cost": "95,50", "goal_target": 5, "wd_farm": False, "aktiv": True,
              "sortierung": "3", "id": "egal", "user_id": "boese", "updated_by": "boese"})
    check(f is None and b["name"] == "Tradeify 150k Funded" and b["account_size"] == 150000.0 and b["purchase_cost"] == 95.5
          and b["goal_target"] == 5 and b["sortierung"] == 3 and b["wd_farm"] is False and b["aktiv"] is True,
          "gueltige Vorlage: getrimmt, Zahlen aus Text (auch Komma), ganze Zahlen, bool")
    check(not any(k in b for k in ("id", "user_id", "updated_by")), "unbekannte/gesperrte Schluessel fliegen raus (updated_by setzt der Server)")
    check("firm" in b and "max_daily_drawdown" not in b, "fehlende Schluessel bleiben weg (Aendern laesst sie unveraendert)")
    b2, _ = p({"name": "X", "firm": "", "max_drawdown": None, "goal_target": ""})
    check(b2["firm"] is None and b2["max_drawdown"] is None and b2["goal_target"] is None, "'' / None leeren das Feld")
    check(p({"firm": "Tradeify"})[1] == "name ist Pflicht" and p({"name": "  "})[1] == "name ist Pflicht"
          and "80" in (p({"name": "n" * 81})[1] or ""), "name Pflicht, hoechstens 80 Zeichen")
    check("Zahl" in p({"name": "X", "max_drawdown": "viel"})[1] and "Zahl" in p({"name": "X", "account_size": True})[1]
          and "ganze" in p({"name": "X", "goal_target": 2.5})[1] and "true/false" in p({"name": "X", "wd_farm": "ja"})[1]
          and "Text" in p({"name": "X", "firm": {"a": 1}})[1] and "Bereich" in p({"name": "X", "purchase_cost": 1e12})[1],
          "Typen: Zahl/ganze Zahl/bool/Text/Bereich geprueft")
    check(p(None) == (None, "vorlage fehlt"), "ohne Vorlage → Fehler")

    print("\nALLES GRUEN" if ok else "\nFEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
