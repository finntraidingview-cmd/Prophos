#!/usr/bin/env python3
"""Selbsttest: delta.geplant[] trägt notes + balance (app.py _ap_stand_laden / ap_delta_antwort / _ap_notes_kurz, 08.10.2026, Vertrag
Slave 7 „Wartet auf Start" bei fremden IDs) — nur Durchreichen. Nachgebaute DB aus selftest_auto_delta.
Aufruf: python3 tools/selftest_auto_notes_balance.py"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest_auto_delta as sd  # noqa: E402


def main():
    a = sd.lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    from zoneinfo import ZoneInfo
    jetzt = datetime.now(timezone.utc)
    tag = jetzt.astimezone(ZoneInfo("Europe/Berlin")) + timedelta(days=1)
    while tag.weekday() >= 5:
        tag += timedelta(days=1)
    mitt = datetime(tag.year, tag.month, tag.day, tzinfo=ZoneInfo("Europe/Berlin"))
    t0 = max(jetzt, mitt) + timedelta(minutes=60)
    ap = "Auto-Planer · Etappe · Rest 3.000 $ · TP 3.450"
    lang = ap + "\n" + "\n".join(f"✎ Hand 08.10 0{i}:00: TP 3.600 → 4.000" for i in range(40))
    geplant = [
        {"id": "p-n1", "user_id": sd.U1, "master_account_id": "k-2", "master_firm": "FundedNext", "status": "planned", "richtung": "buy",
         "master_tp": 6000, "master_sl": 3000, "master_contracts": 3.0, "route": "mt5v2", "start_um": t0.isoformat(),
         "auto_plan": True, "auto_bestaetigt_at": None, "created_at": jetzt.isoformat(), "notes": ap},
        {"id": "p-n2", "user_id": sd.U1, "master_account_id": "k-1", "master_firm": "FundedNext", "status": "planned", "richtung": "buy",
         "master_tp": 6000, "master_sl": 3000, "master_contracts": 3.0, "route": "mt5v2", "start_um": (t0 + timedelta(minutes=300)).isoformat(),
         "auto_plan": True, "auto_bestaetigt_at": None, "created_at": jetzt.isoformat(), "notes": lang},
        {"id": "p-n3", "user_id": sd.U2, "master_account_id": "k-4", "master_firm": "Apex Trader", "status": "planned", "richtung": "buy",
         "master_tp": 9100, "master_sl": None, "master_contracts": 5, "master_symbol": "NQZ6", "route": "tvv2",
         "start_um": (t0 + timedelta(minutes=5)).isoformat(), "auto_plan": False, "created_at": jetzt.isoformat()},
    ]
    reg, _g = sd.db_stubs(a, jetzt, geplant)
    stand = a["_ap_stand_laden"](reg, jetzt=max(jetzt, mitt + timedelta(minutes=1)))
    dl = a["ap_delta_antwort"](stand)
    z = {r["plan_id"]: r for r in dl["geplant"]}
    check(set(z) == {"p-n1", "p-n2", "p-n3"} and all("notes" in r and "balance" in r for r in dl["geplant"]),
          "notes + balance an jeder geplant[]-Zeile (nach der Feldliste)")
    check(z["p-n1"]["notes"] == ap, f"kurze notes unverändert ({z['p-n1']['notes']})")
    n2 = z["p-n2"]["notes"]
    check(len(n2) == a["AP_NOTES_MAX"] and n2.startswith(ap) and n2.endswith("…"),
          f"lange notes gekürzt auf {a['AP_NOTES_MAX']} Zeichen, Auto-Planer-Zeile bleibt vorn ({len(lang)} → {len(n2)})")
    check(z["p-n3"]["notes"] is None, "ohne notes → null")
    # Balance = die, mit der der Planer rechnet (bal(a) → acc_balance_wahl; im Nachbau die Fixture-Balance)
    konten, bal, _offen = sd.fixture(jetzt)
    soll = {"p-n1": bal.get("k-2"), "p-n2": bal.get("k-1"), "p-n3": bal.get("k-4")}
    check(all((z[p]["balance"] == round(float(soll[p]), 2)) if soll[p] is not None else z[p]["balance"] is None for p in soll),
          f"balance = Planer-Balance je Konto ({ {p: z[p]['balance'] for p in z} } / {soll})")
    K = a["_ap_notes_kurz"]
    check(K(None) is None and K("  ") is None and K(" x ") == "x", "_ap_notes_kurz: leer → null, Ränder getrimmt")
    print("\nNOTES/BALANCE:", "alles grün" if ok else "FEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
