#!/usr/bin/env python3
"""Selbsttest: Werte von Hand (trade_plans.hand_werte_at, 08.10.2026, Master/Finn) — aktion „werte" setzt die Spalte, _ap_stand_laden
macht den Plan für den Bot fest („Werte von Hand geändert"), Hand-Eingriffe bleiben möglich, ohne Spalte läuft alles wie vorher.
Rein rechnend auf der nachgebauten DB aus selftest_auto_delta. Aufruf: python3 tools/selftest_auto_hand_werte.py"""
import os
import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import requests  # noqa: E402

import selftest_auto_delta as sd  # noqa: E402
import selftest_auto_werte as sw  # noqa: E402


class Antwort:
    text = 'column trade_plans.hand_werte_at does not exist'


def fehlt():
    e = requests.exceptions.HTTPError("400")
    e.response = Antwort()
    return e


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
    t0 = max(jetzt, mitt) + timedelta(minutes=120)
    # zwei unbestätigte Auto-Vorschläge derselben ID bei zwei Firmen; p-h1 hat Werte von Hand
    geplant = [
        {"id": "p-h1", "user_id": sd.U1, "master_account_id": "k-2", "master_firm": "FundedNext", "status": "planned", "richtung": "buy",
         "master_tp": 6000, "master_sl": 3000, "master_contracts": 3.0, "route": "mt5v2", "start_um": t0.isoformat(),
         "auto_plan": True, "auto_bestaetigt_at": None, "created_at": jetzt.isoformat(), "hand_werte_at": jetzt.isoformat()},
        {"id": "p-h2", "user_id": sd.U1, "master_account_id": "k-1", "master_firm": "FundedNext", "status": "planned", "richtung": "buy",
         "master_tp": 6000, "master_sl": 3000, "master_contracts": 3.0, "route": "mt5v2", "start_um": (t0 + timedelta(minutes=300)).isoformat(),
         "auto_plan": True, "auto_bestaetigt_at": None, "created_at": jetzt.isoformat()},
    ]
    reg, _g = sd.db_stubs(a, jetzt, geplant)
    stand = a["_ap_stand_laden"](reg, jetzt=max(jetzt, mitt + timedelta(minutes=1)))
    z = {r["plan_id"]: r for r in stand["geplant"]}
    h1, h2 = z.get("p-h1") or {}, z.get("p-h2") or {}
    check(h1.get("fest_durch") == a["AP_FEST_HAND"] and h1.get("aenderbar") is False, f"Stand: p-h1 fest „Werte von Hand geändert“ ({h1.get('fest_durch')})")
    check(h2.get("aenderbar") is True and h2.get("bestaetigt") is False, "Stand: p-h2 ohne Hand-Werte bleibt änderbar, Bestätigung unberührt")
    check(h1.get("bestaetigt") is False and h1.get("auto_plan") is True, "Stand: p-h1 bleibt unbestätigter Auto-Vorschlag (Start-Regel unberührt)")

    plaene = a["_ap_stand_plaene"](stand)
    tr = a["_ap_tranchen"](plaene)
    t = next(x for x in tr.values() if "p-h1" in x["plan_ids"])
    check(t["aenderbar"] is False and t["fest_durch"] == a["AP_FEST_HAND"], "Bot: Tranche mit Hand-Plan ist gesperrt")
    erg = a["ap_umplanen"](plaene, 50.0, 50.0, max(0.0, stand["jetzt_min"]), stand["zeiten"], 1.0, random.Random(1),
                           einsatz={"basis": 5000.0, "brutto": 5000.0, "gross_ab": 100000.0, "laufzeit": 180})
    check(not any(x["plan_id"] == "p-h1" for x in erg["aenderungen"]), f"Bot: Hand-Plan wird nie gedreht/verschoben ({[x['plan_id'] for x in erg['aenderungen']]})")
    aend, fehler = a["ap_eingriff_pruefen"]("p-h1", "richtung_tauschen", plaene, stand["jetzt_min"], stand["zeiten"], {})
    check(fehler is None and any(x["plan_id"] == "p-h1" for x in aend or []), f"Hand-Eingriff (Richtung tauschen) bleibt möglich ({fehler})")

    # Nachtlauf: Hand-Plan p-h1 ist kein ersetzbarer Vorschlag (Konto k-2 hat weiter seinen Plan), p-h2 schon; DELETE lässt Hand-Pläne stehen
    loesch = []

    class R:
        status_code = 201

        def raise_for_status(self):
            return None
    a["_sb_anfrage"] = lambda meth, url, **k: (loesch.append((meth, k.get("params"))), R())[1]
    a["_sb_pruefen"] = lambda r: None
    a["sb_insert"] = lambda table, body: {"id": 1}
    erg = a["ap_planen"](tag.strftime("%Y-%m-%d"), trocken=False, seed=4711)
    aus = {x.get("konto_id"): x.get("grund") for x in erg.get("ausgelassen") or []}
    gepl = {x.get("konto_id") for x in erg.get("geplant") or []}
    check("schon einen geplanten" in str(aus.get("k-2")) and "k-2" not in gepl, f"Nachtlauf: Konto mit Hand-Plan bleibt beim Hand-Plan ({aus.get('k-2')})")
    check("k-1" not in aus or "schon einen geplanten" not in str(aus.get("k-1")), f"Nachtlauf: Vorschlag ohne Hand-Werte gilt als ersetzbar ({aus.get('k-1')})")
    dels = [p for m, p in loesch if m == "DELETE"]
    check(dels and dels[0].get("hand_werte_at") == "is.null" and dels[0].get("auto_bestaetigt_at") == "is.null",
          f"DELETE der alten Vorschläge nur mit hand_werte_at is.null ({dels[:1]})")

    # ohne Spalte: Lesen fällt auf den alten select zurück, anderer Fehler fliegt durch
    alt = a["_sb_all"]
    aufrufe = []

    def ohne_spalte(table, params):
        aufrufe.append(params["select"])
        if "hand_werte_at" in params["select"]:
            raise fehlt()
        return alt(table, params)
    a["_sb_all"] = ohne_spalte
    rows = a["_ap_plaene_mit_hand"]({"select": "id,status", "status": "eq.planned"})
    check(len(rows) == 2 and aufrufe == ["id,status,hand_werte_at", "id,status"], f"ohne Spalte: zweiter Versuch ohne hand_werte_at ({aufrufe})")
    a["_sb_all"] = lambda table, params: (_ for _ in ()).throw(ConnectionError("weg"))
    try:
        a["_ap_plaene_mit_hand"]({"select": "id"})
        check(False, "anderer Fehler muss durchfliegen")
    except ConnectionError:
        check(True, "anderer Fehler (Netz) fliegt durch, kein stiller Rückfall")
    a["_sb_all"] = alt

    # aktion werte setzt hand_werte_at; ohne Spalte schreibt sie ohne
    w = sw.lade()
    w.update({"_ap_hand_spalte_fehlt": a["_ap_hand_spalte_fehlt"], "requests": requests, "jsonify": lambda d: d})
    plan = {"id": sw.PID, "user_id": "u-a", "status": "planned", "route": "tvv2", "master_symbol_root": "NQ",
            "master_tp": 3600, "master_sl": 2000, "master_contracts": 2, "notes": ""}
    geschrieben = []
    w["sb_select"] = lambda t, p: [dict(plan)]
    w["sb_update"] = lambda t, p, u: (geschrieben.append(u) or [dict(plan, **u)])
    r = w["_ap_werte_setzen"](sw.PID, {"tp_usd": 4000}, True, "admin")
    check(r["ok"] and geschrieben and geschrieben[-1].get("hand_werte_at"), "werte setzt hand_werte_at")

    def ohne(t, p, u):
        if "hand_werte_at" in u:
            raise fehlt()
        geschrieben.append(u)
        return [dict(plan, **u)]
    w["sb_update"] = ohne
    r = w["_ap_werte_setzen"](sw.PID, {"tp_usd": 4100}, True, "admin")
    check(r["ok"] and "hand_werte_at" not in geschrieben[-1] and geschrieben[-1]["master_tp"] == 4100, "werte ohne Spalte: schreibt die Werte trotzdem")

    print("\nHAND-WERTE:", "alles grün" if ok else "FEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
