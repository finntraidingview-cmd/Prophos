#!/usr/bin/env python3
"""Selbsttest: TP/SL/Größe eines geplanten Trades von Hand (app.py ap_werte_pruefen / _ap_werte_setzen, POST /admin/auto-plan/plan
aktion „werte", 08.10.2026, Vertrag Master/Slave 5) — rein rechnend, DB nachgebaut. Aufruf: python3 tools/selftest_auto_werte.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
PID = "11111111-2222-3333-4444-555555555555"


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone}
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in ("AP_CFD_ROUTEN", "AP_7T_TZ")]
    for name in ("_wd_num", "_ap_tz", "_ap_zahl", "ap_werte_pruefen", "_ap_werte_setzen"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def main():
    ns = lade()
    P = ns["ap_werte_pruefen"]
    f = []

    def check(ok, name):
        f.append(0 if ok else 1)
        print(("OK  " if ok else "FEHL") + " " + name)

    jetzt = datetime(2026, 10, 7, 23, 55, tzinfo=timezone.utc)          # 08.10. 03:55 Dubai
    fut = {"id": PID, "user_id": "u-a", "status": "planned", "route": "tvv2", "master_symbol": "NQZ6", "master_symbol_root": "NQ",
           "master_tp": 3600, "master_sl": 2000, "master_contracts": 2, "notes": "Auto-Planer · Etappe · Rest 3.000"}
    cfd = dict(fut, route="mt5v2", master_symbol=None, master_symbol_root=None, master_contracts=1.5)

    upd, a, err = P(fut, {"tp_usd": 4000, "sl_usd": None, "groesse": 3}, jetzt)
    check(err is None and upd["master_tp"] == 4000 and upd["master_sl"] is None and upd["master_contracts"] == 3,
          f"Futures: TP 4.000, ohne SL, 3 Kontrakte ({upd}, {err})")
    check(a == {"plan_id": PID, "tp_usd": 4000, "sl_usd": None, "groesse": 3, "einheit": "NQ"}, f"Antwort-Vertrag ({a})")
    check(upd["notes"].startswith("Auto-Planer · Etappe") and upd["notes"].endswith("✎ Hand 08.10 03:55: TP 3.600 → 4.000 · SL 2.000 → ohne · Größe 2 → 3 NQ"),
          f"Notes-Zeile angehängt, Dubai-Zeit ({upd['notes'].splitlines()[-1]})")
    check(set(upd) == {"master_tp", "master_sl", "master_contracts", "notes"} and "auto_bestaetigt_at" not in upd,
          "nur die drei Werte + notes, Bestätigung unberührt")
    upd, a, err = P(fut, {"sl_usd": 1500}, jetzt)
    check(set(upd) == {"master_sl", "notes"} and a["tp_usd"] == 3600 and a["groesse"] == 2 and a["sl_usd"] == 1500,
          f"nur SL geändert, Rest bleibt ({a})")
    check(P(fut, {"sl_usd": 0}, jetzt)[0]["master_sl"] is None, "SL 0 = ohne SL (null)")
    check(P(dict(fut, master_symbol="MNQZ6", master_symbol_root="MNQ"), {"groesse": 5}, jetzt)[1]["einheit"] == "MNQ", "MNQ als Einheit")

    check(P(fut, {"groesse": 2.5}, jetzt)[2] == "Größe muss ganze Kontrakte sein (≥ 1)", "Futures 2,5 → abgelehnt")
    check(P(fut, {"groesse": 0}, jetzt)[2] == "Größe muss ganze Kontrakte sein (≥ 1)", "Futures 0 → abgelehnt")
    check(P(fut, {"groesse": "3"}, jetzt)[0]["master_contracts"] == 3, "Futures \"3\" als Text → 3")
    upd, a, err = P(cfd, {"groesse": 1.234}, jetzt)
    check(err is None and upd["master_contracts"] == 1.23 and a["einheit"] == "Lot", f"CFD 1,234 → 1,23 Lot ({upd}, {a})")
    check(upd["notes"].endswith("Größe 1,5 → 1,23 Lot"), f"Notes deutsch mit Komma ({upd['notes'].splitlines()[-1]})")
    check(P(cfd, {"groesse": "0,75"}, jetzt)[0]["master_contracts"] == 0.75, "CFD \"0,75\" (Komma) → 0,75 Lot")
    check(P(cfd, {"groesse": 0.004}, jetzt)[2] == "Größe muss > 0 Lot sein (2 Nachkommastellen)", "CFD 0,004 → gerundet 0 → abgelehnt")
    check(P(fut, {"tp_usd": 0}, jetzt)[2] == "TP muss eine Zahl > 0 sein ($)", "TP 0 → abgelehnt")
    check(P(fut, {"tp_usd": True}, jetzt)[2] == "TP muss eine Zahl > 0 sein ($)", "TP true → abgelehnt")
    check(P(fut, {"sl_usd": -5}, jetzt)[2].startswith("SL muss eine Zahl ≥ 0"), "SL negativ → abgelehnt")
    check(P(fut, {"sl_usd": "abc"}, jetzt)[2].startswith("SL muss eine Zahl ≥ 0"), "SL Text → abgelehnt")
    check(P(fut, {}, jetzt)[2].startswith("nichts zu ändern"), "leerer Body → abgelehnt")
    check(P(dict(fut, start_um_gestartet_at="2026-10-07T23:50:00+00:00"), {"tp_usd": 1}, jetzt)[2] == "Plan läuft schon — Werte nicht mehr änderbar",
          "geclaimt → „Plan läuft schon“")
    check(P(dict(fut, status="open"), {"tp_usd": 1}, jetzt)[2] == "Plan läuft schon — Werte nicht mehr änderbar", "open → „Plan läuft schon“")
    check(P(dict(fut, status="completed"), {"tp_usd": 1}, jetzt)[2].startswith("Plan ist nicht mehr geplant"), "completed → abgelehnt")
    check(P(None, {"tp_usd": 1}, jetzt)[2] == "Plan nicht gefunden", "kein Plan → nicht gefunden")

    # _ap_werte_setzen mit nachgebauter DB: Rechte, Guard in derselben Anfrage, 409 beim Wettlauf
    db = {"zeile": dict(fut), "update": [], "treffer": True}
    ns["jsonify"] = lambda d: d
    ns["sb_select"] = lambda t, p: [dict(db["zeile"])] if db["zeile"] else []
    ns["sb_update"] = lambda t, p, u: (db["update"].append((p, u)) or [dict(db["zeile"], **u)]) if db["treffer"] else []
    S = ns["_ap_werte_setzen"]
    r = S(PID, {"tp_usd": 4200}, False, "u-a")
    check(isinstance(r, dict) and r["ok"] and r["plan"]["tp_usd"] == 4200, f"eigener Plan (Nicht-Admin) → ok ({r})")
    p, u = db["update"][-1]
    check(p == {"id": f"eq.{PID}", "status": "eq.planned", "start_um_gestartet_at": "is.null", "started_at": "is.null", "orbit_gesendet_at": "is.null"},
          f"Guard in derselben Anfrage ({p})")
    r = S(PID, {"tp_usd": 4200}, False, "u-b")
    check(r[1] == 403 and r[0]["msg"] == "nur eigene Pläne", "fremder Plan (Nicht-Admin) → 403")
    r = S(PID, {"tp_usd": 4200}, True, "u-admin")
    check(isinstance(r, dict) and r["ok"], "fremder Plan als Admin → ok")
    db["treffer"] = False
    r = S(PID, {"tp_usd": 4200}, True, "u-admin")
    check(r[1] == 409 and "läuft schon" in r[0]["msg"], "Wettlauf (PC hat zwischen Lesen und Schreiben geclaimt) → 409")
    db["treffer"], db["zeile"] = True, None
    check(S(PID, {"tp_usd": 1}, True, "u-admin")[1] == 404, "Plan weg → 404")
    db["zeile"] = dict(fut)
    r = S(PID, {"groesse": 1.5}, True, "u-admin")
    check(r[1] == 400 and r[0]["msg"] == "Größe muss ganze Kontrakte sein (≥ 1)", "Klartext-400 kommt durch")

    print(f"{len(f) - sum(f)}/{len(f)} ok")
    sys.exit(1 if sum(f) else 0)


if __name__ == "__main__":
    main()
