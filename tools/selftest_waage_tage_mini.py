#!/usr/bin/env python3
"""Selbsttest: WAAGE-TAGE-MINI (30.10.2026, Befund S6). Tage-sammeln-Minis (mt5_baseline.tage_mini) zählen nicht in der Waage und starten
ohne Waage-Prüfung (wie Apex/WD). Ohne Netz. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_waage_tage_mini.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


Z = {"plan_id": "p-mini", "user_id": "u1", "user": "Chris", "richtung": "buy", "typ": "phase1", "route": "mt5v2", "firma": "FundedNext",
     "firma_key": "fundednext", "start_min": 600.0, "gehedgt": False, "tage_mini": True, "verlust_eur": 3.6}
check(not app.ap_waage_zeile_zaehlt(Z, 600.0, laufend=True) and not app.ap_waage_zeile_zaehlt(Z, 600.0), "Tage-Mini zählt weder laufend noch geplant")
check(app.ap_waage_zeile_zaehlt(dict(Z, tage_mini=False), 600.0, laufend=True), "normaler CFD-Trade zählt weiter (laufend)")
stand = {"geplant": [Z], "laufend": [{"plan_id": "p-short", "user_id": "u2", "richtung": "sell", "typ": "phase1", "route": "mt5v2",
                                      "firma": "The5%ers", "firma_key": "the5ers", "gehedgt": False, "verlust_eur": 200}],
         "jetzt_min": 600.0, "param": {}}
try:
    L = app.ap_waage_start_lage(stand, "p-mini", "buy")
except Exception as e:
    L = {"fehler": f"{type(e).__name__}: {e}"}
check(L and L.get("zaehlt") is False and L.get("ohne_waage") and L["nachher"]["passt"] and "Tage sammeln" in L["nachher"]["grund"],
      f"Start-Lage: zählt nicht, passt, Grund Tage sammeln ({L.get('nachher', L) if L else L})")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
