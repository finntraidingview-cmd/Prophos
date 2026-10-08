#!/usr/bin/env python3
"""Selbsttest TOPSTEP-KETTE MIT DLL IM PLANER (app.py ap_planen + _ap_peaks streng + ap_kette_trade1, 08.10.2026, Slave-Terminal 3 —
Finn: DLL 3.000; Prüfung Slave 2: „Peak-Ausfall → nie mit zu tiefem MLL planen").

Aufruf:  python3 tools/selftest_kette_mll_planer.py
Planer-Lauf ohne Netz auf der nachgebauten DB aus selftest_auto_alle_ids, dazu eine Topstep-Regel mit Kette + daily_usd 3.000 und ein
Topstep-Challenge-Konto (Platzhalter). Geprüft: (1) Verlauf nicht lesbar → KEIN Kettenplan, Grund „MLL nicht prüfbar"; (2) frisches Konto
ohne Verlauf → Plan mit MLL 145.500, Verlustgrenze 3.200, SL 1.250–1.750; (3) belegter Höchststand 152.000 bei Balance 150.000 → MLL 147.500,
„angefressen", kein Plan; (4) _ap_peaks ohne streng schluckt den Fehler weiter (kein Höchststand), mit streng → None."""
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest_auto_alle_ids as al  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


TOPSTEP = {"namen": ["topstep"], "route": "tsv2", "symbol": "NQ", "boden": "nachziehend", "dd_usd": 4500, "groessen": [150000],
           "kauf_eur": 237, "ziel_pct": {"challenge": 6}, "planen": True,
           "phasen": {"challenge": {"sl": None, "tp": [4350, 4450], "menge": [2, 3], "dd_usd": 4500, "tp_max": 4500, "ziel_pct": 6,
                                    "menge_schritt": 1, "puffer_je_menge": {"2": [15, 25], "3": [25, 40]}}},
           "kette": {"daily_usd": 3000, "t1_sl": [1250, 1750]}}
KONTO = {"id": "k-ts1", "user_id": al.U3, "name": "150k Topstep TS1", "firm": "Topstep", "account_type": "challenge",
         "external_id": "150KTC-SKU-V2-000000-00000001"}


def lauf(verlauf_fehler=False, verlauf=None):
    a = al.lade()
    jetzt = datetime.now(timezone.utc)
    tag = jetzt.astimezone(ZoneInfo("Europe/Berlin")) + timedelta(days=1)
    while tag.weekday() >= 5:
        tag += timedelta(days=1)
    reg, _g, _i = al.db_stubs(a, jetzt)
    reg["regeln"]["firmen"].append(TOPSTEP)
    alt_all, alt_bal = a["_sb_all"], a["acc_balance_wahl"]

    def _sb_all(table, params):
        if table == "trade_plans" and "konto_typ" in str(params.get("select", "")):   # _liq_verlauf_laden
            if verlauf_fehler:
                raise RuntimeError("Supabase weg (Test)")
            return [dict(z) for z in (verlauf or [])]
        rows = alt_all(table, params)
        if table == "accounts":
            ids, uids, typen = al.in_liste(params.get("id", "")), al.in_liste(params.get("user_id", "")), params.get("account_type")
            if (ids is None or KONTO["id"] in ids) and (uids is None or KONTO["user_id"] in uids) and (not typen or KONTO["account_type"] in typen):
                rows += [dict(KONTO)]
        return rows
    a["_sb_all"] = _sb_all
    a["_liq_verlauf_cache"].clear()
    a["acc_balance_wahl"] = lambda k, e, d: ((150000.0, "USD", "TV", "2999-01-01") if str((k or {}).get("id")) == KONTO["id"] else alt_bal(k, e, d))
    erg = a["ap_planen"](tag.strftime("%Y-%m-%d"), trocken=True, seed=4711, ids="alle")
    aus = {z.get("konto_id"): z for z in erg.get("ausgelassen") or []}
    plan = [z for z in erg.get("geplant") or [] if z.get("konto_id") == KONTO["id"] or z.get("master_account_id") == KONTO["id"]]
    return a, erg, aus.get(KONTO["id"]), plan


def main():
    a, erg, aus, plan = lauf(verlauf_fehler=True)
    check(erg.get("ok"), f"Planer-Lauf läuft durch ({erg.get('msg') or 'ok'})")
    check(not plan and aus and "MLL nicht prüfbar" in aus.get("grund", ""), f"Verlauf nicht lesbar → kein Kettenplan, Grund „{(aus or {}).get('grund')}“")

    a, erg, aus, plan = lauf()
    p0 = plan[0] if plan else {}
    sl = p0.get("sl")
    # die geplant-Zeile ist eine Anzeigezeile (ohne Kette-Block) — MLL/Verlustgrenze prüft selftest_auto_topstep_kette direkt
    check(plan and not aus and sl is not None and 1250 <= float(sl) <= 1750 and "Topstep-Kette 1/2" in str(p0.get("stufe")),
          f"frisches Konto ohne Verlauf → Kettenplan Trade 1, SL {sl} (1.250–1.750) ({p0 or aus})")

    hoch = [{"id": "v1", "master_account_id": KONTO["id"], "konto_typ": "challenge", "started_at": "2026-10-06T14:00:00+00:00",
             "ended_at": "2026-10-06T15:00:00+00:00", "bal_start": 150000.0, "bal_end": 152000.0},
            {"id": "v2", "master_account_id": KONTO["id"], "konto_typ": "challenge", "started_at": "2026-10-07T14:00:00+00:00",
             "ended_at": "2026-10-07T15:00:00+00:00", "bal_start": 152000.0, "bal_end": 150000.0}]
    a, erg, aus, plan = lauf(verlauf=hoch)
    check(not plan and aus and "angefressen" in aus.get("grund", "") and "Abstand MLL 2.500" in aus.get("grund", ""),
          f"Höchststand 152.000, Balance 150.000 → MLL 147.500, angefressen ({(aus or {}).get('grund')})")

    a["_liq_verlauf_cache"].clear()
    a["_sb_all"] = lambda t, p: (_ for _ in ()).throw(RuntimeError("weg"))
    check(a["_ap_peaks"]([KONTO]) == {KONTO["id"]: None} and a["_ap_peaks"]([KONTO], streng=True) is None,
          "_ap_peaks: Anzeige schluckt den Fehler (kein Höchststand), streng → None (Planer: MLL nicht prüfbar)")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
