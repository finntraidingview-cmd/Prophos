#!/usr/bin/env python3
"""Selbsttest: ausgelassen[]-Zeilen mit den beiden geblowt-Gründen tragen boden, boden_min, boden_art, balance, bal_stand (app.py
ap_planen + ap_boden_zeile, Vertrag Slave 6, 08.10.2026) — Planer-Lauf ohne Netz auf der nachgebauten DB aus selftest_auto_alle_ids.
Aufruf: python3 tools/selftest_auto_geblowt_felder.py"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest_auto_alle_ids as al  # noqa: E402

STAND = "2026-10-07T12:00:00+00:00"


def main():
    a = al.lade()
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
    al.db_stubs(a, jetzt)
    extra = [{"id": "k-g1", "user_id": al.U3, "name": "TDFY G1", "firm": "Tradeify", "account_type": "challenge", "external_id": "TDFY-0000G1"},
             {"id": "k-g2", "user_id": al.U3, "name": "APEX G2", "firm": "Apex", "account_type": "challenge", "external_id": "APEX-0000G2"}]
    # Tradeify: letzter Trade −4.500 $ (= ganzer DD), Balance 145.400 → „letzter Trade … — geblowt?"; Apex: 146.000 = Boden → Boden-Grund
    plan_g1 = {"id": "p-g1", "user_id": al.U3, "master_account_id": "k-g1", "master_firm": "Tradeify", "status": "completed",
               "ended_at": "2026-10-07T10:00:00+00:00", "completed_at": "2026-10-07T10:05:00+00:00", "auto_plan": True,
               "final": {"today_pnl": -4500}}
    bal = {"k-g1": 145400.0, "k-g2": 146000.0}
    alt_all, alt_bal = a["_sb_all"], a["acc_balance_wahl"]

    def _sb_all(table, params):
        rows = alt_all(table, params)
        if table == "accounts":
            ids, uids, typen = al.in_liste(params.get("id", "")), al.in_liste(params.get("user_id", "")), params.get("account_type")
            rows += [dict(k) for k in extra if (ids is None or k["id"] in ids) and (uids is None or k["user_id"] in uids)
                     and (not typen or k["account_type"] in typen)]
        if table == "trade_plans" and not params.get("status"):
            rows += [dict(plan_g1)]
        return rows
    a["_sb_all"] = _sb_all
    a["acc_balance_wahl"] = lambda k, e, d: ((bal[str(k["id"])], "USD", "TV", STAND) if str((k or {}).get("id")) in bal else alt_bal(k, e, d))

    erg = a["ap_planen"](tag.strftime("%Y-%m-%d"), trocken=True, seed=4711, ids="alle")
    aus = {z.get("konto_id"): z for z in erg.get("ausgelassen") or []}
    g1, g2 = aus.get("k-g1") or {}, aus.get("k-g2") or {}
    felder = ("boden", "boden_min", "boden_art", "balance", "bal_stand")
    check(erg.get("ok"), f"Planer-Lauf läuft durch ({erg.get('msg') or 'ok'})")
    check(str(g1.get("grund", "")).startswith("letzter Trade") and "geblowt?" in g1.get("grund", ""), f"k-g1 Grund letzter Trade … geblowt? ({g1.get('grund')})")
    check(all(k in g1 for k in felder) and g1["balance"] == 145400 and g1["bal_stand"] == STAND
          and g1["boden"] == 145500 and g1["boden_min"] == 145500 and g1["boden_art"] == "nachziehend_geschaetzt",
          f"k-g1 trägt die Felder (Tradeify geschätzt 145.500) ({ {k: g1.get(k) for k in felder} })")
    check(str(g2.get("grund", "")).startswith("Balance auf/unter dem Boden — geblowt?"), f"k-g2 Boden-Grund ({g2.get('grund')})")
    check(all(k in g2 for k in felder) and g2["balance"] == 146000 and g2["bal_stand"] == STAND
          and g2["boden"] == 146000 and g2["boden_art"] == "statisch",
          f"k-g2 trägt die Felder (Apex statisch 146.000) ({ {k: g2.get(k) for k in felder} })")
    andere = [z for z in erg.get("ausgelassen") or [] if "geblowt" not in str(z.get("grund"))]
    check(all("boden" not in z for z in andere), f"andere Gründe ohne die Felder ({len(andere)} Zeilen)")

    # ap_boden_zeile: kaputte Regel → Felder null, balance/bal_stand bleiben
    bz = a["ap_boden_zeile"]({"kauf_eur": 1, "dd_pct": "kaputt", "ziel_pct": {"challenge": 6}, "groessen": [150000], "boden": "statisch"},
                             extra[1], 146000, STAND)
    check(bz["boden"] is None and bz["boden_art"] is None and bz["balance"] == 146000 and bz["bal_stand"] == STAND,
          f"ap_boden_zeile: kaputte Regel → boden null, Balance + Stand bleiben ({bz})")
    print("\nGEBLOWT-FELDER:", "alles grün" if ok else "FEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
