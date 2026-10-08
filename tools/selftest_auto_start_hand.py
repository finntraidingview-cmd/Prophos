#!/usr/bin/env python3
"""Selbsttest: Startzeit per Klick (app.py ap_start_zeit / ap_start_hand_pruefen / ap_werte_pruefen start / _ap_werte_setzen,
POST /admin/auto-plan/plan aktion „werte" mit start_um, 08.10.2026, Vertrag Master/Slave 5) — rein rechnend, Stand nachgebaut.
Aufruf: python3 tools/selftest_auto_start_hand.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
PID = "11111111-2222-3333-4444-555555555555"
KONST = ("AP_CFD_ROUTEN", "AP_7T_TZ", "AP_TZ_TAG", "AP_START_HAND_VORLAUF_MIN", "AP_VERTEIL_GEGEN_MIN", "AP_FIRMA_ABSTAND_MIN", "AP_RICHTUNG_TXT")
FUNK = ("_wd_num", "_ap_norm", "ap_firma_key", "_ap_tz", "_ap_ts", "_ap_zahl", "_ap_hhmm_txt", "ap_start_zeit", "ap_start_hand_pruefen", "ap_werte_pruefen",
        "_ap_werte_setzen")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone}
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in KONST]
    for name in FUNK:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def plan(pid, uid, firma, richtung, start, **kw):
    return dict({"plan_id": pid, "user_id": uid, "firma": firma, "richtung": richtung, "start_min": start}, **kw)


def main():
    ns = lade()
    Z, P = ns["ap_start_zeit"], ns["ap_start_hand_pruefen"]
    f = []

    def check(ok, name):
        f.append(0 if ok else 1)
        print(("OK  " if ok else "FEHL") + " " + name)

    # ── ap_start_zeit: HH:MM Dubai heute, vorbei → Fehler, ISO ──
    jetzt = datetime(2026, 10, 8, 0, 30, tzinfo=timezone.utc)            # 04:30 Dubai
    d, e = Z("05:02", jetzt)
    check(e is None and d == datetime(2026, 10, 8, 1, 2, tzinfo=timezone.utc), f"„05:02“ = heute 05:02 Dubai = 01:02 UTC ({d}, {e})")
    check(Z("04:10", jetzt)[1] == "Startzeit 04:10 (Dubai) liegt schon vorbei", "„04:10“ vorbei → Fehler, kein Sprung auf morgen")
    check(Z("2026-10-08T03:00:00Z", jetzt)[0] == datetime(2026, 10, 8, 3, 0, tzinfo=timezone.utc), "ISO wird übernommen")
    check(Z("25:00", jetzt)[1].startswith("start_um = HH:MM") and Z("quatsch", jetzt)[1].startswith("start_um = HH:MM") and Z("", jetzt)[1],
          "ungültige Eingaben → Klartext")

    # ── ap_start_hand_pruefen: Minuten ab 00:00 dt; jetzt = 300 (05:00 dt) ──
    U, V = "u-a", "u-b"
    plaene = [plan("p1", U, "the5ers", "buy", 600), plan("p2", U, "the5ers", "buy", 620),
              plan("q1", V, "the5ers", "sell", 400), plan("r1", U, "fundednext", "sell", 500),
              plan("s1", U, "the5ers", "sell", 900)]
    starts = [{"user_id": V, "firma": "fundednext", "start": 450.0, "richtung": "buy"}]
    check(P("p1", 330, plaene, starts, {}, 300) == (None, None), "freie Zeit 05:30 dt → ok")
    g, v = P("p1", 301, plaene, starts, {}, 300)
    check(g.startswith("Startzeit zu früh") and v == 302, f"jetzt + 1 min → zu früh, Vorschlag jetzt + 2 ({g}, {v})")
    # seit 08.10.2026 1 min statt 5, und für jeden Start derselben Firma (auch derselben ID) — Finn: „Nur eben nicht gleichzeitig"
    g, v = P("p1", 400, plaene, starts, {}, 300)
    check(g.startswith("Firmen-Abstand: andere ID") and v == 401, f"andere ID derselben Firma um 400 → Abstand 1 min, Vorschlag 401 ({g}, {v})")
    check(P("p1", 399, plaene, starts, {}, 300)[0] is None and P("p1", 398, plaene, starts, {}, 300)[0] is None, "genau 1 min davor → ok (5 min gelten nicht mehr)")
    check(P("r1", 450, plaene, starts, {}, 300)[0].startswith("Firmen-Abstand"), "Start einer anderen ID (gestartet heute) zählt beim Abstand")
    g, v = P("p1", 620, plaene, starts, {}, 300)
    check(g.startswith("Firmen-Abstand: diese ID") and v == 621, f"eigener Plan derselben Firma zur selben Minute → 1 min ({g}, {v})")
    check(P("p1", 610, plaene, starts, {}, 300)[0] is None, "eigener Plan derselben Firma 10 min weiter → ok (60 min je ID × Firma weg)")
    g, v = P("p1", 800, plaene, starts, {}, 300)
    check(g.startswith("Richtungsschutz") and "short" in g and v == 1020, f"Gegenrichtung derselben ID × Firma um 900 (Laufzeit 120) → Vorschlag 1020 ({g}, {v})")
    check(P("p1", 800, plaene, starts, {}, 300, laufzeit_min=60)[0] is None, "mit Laufzeit 60 min ist 800 frei")
    fest = {f"{U}|the5ers": {"richtung": "sell", "durch": "läuft gerade", "plan_id": "x"}}
    g, v = P("p1", 330, plaene, starts, fest, 300)
    check(g.startswith("Richtungsschutz: bei dieser ID und Firma läuft gerade short") and v == 420,
          f"Gegenrichtung läuft gerade → abgelehnt, Vorschlag nach der Laufzeit ab jetzt (300 + 120) ({g}, {v})")
    check(P("p1", 330, plaene, starts, {f"{U}|the5ers": {"richtung": "buy", "durch": "läuft gerade"}}, 300)[0] is None,
          "gleiche Richtung läuft → ok")
    check(P("p1", 1440, plaene, starts, {}, 300)[0].startswith("Startzeit liegt nach dem Planer-Tag"), "nach 24:00 dt → nur heute")
    check(P("zz", 330, plaene, starts, {}, 300)[0].startswith("Startzeit ändern geht nur"), "Plan unbekannt → Klartext")
    fremd = plan("m1", U, "the5ers", "buy", None)                       # Plan liegt bisher an einem anderen Tag
    check(P(fremd, 330, plaene, starts, {}, 300) == (None, None) and P(fremd, 400, plaene, starts, {}, 300)[0].startswith("Firmen-Abstand"),
          "Plan aus einem anderen Tag (als Objekt) wird gegen den Ziel-Tag geprüft")
    check(P("p1", 300 + 130, plaene, starts, fest, 300)[0] is None, "läuft gerade short, Start nach der Laufzeit (120 min ab jetzt) → ok")
    check(P("p1", 400, plaene, starts, {}, 300, zeit=lambda m: "DUBAI")[0].endswith("um DUBAI — mindestens 1 min Abstand"),
          "Meldung mit Zeit-Formatierer (Route: Dubai)")

    # ── ap_werte_pruefen mit start: Notes „Start 15:08 → 05:02“, Bestätigung bleibt ──
    pl = {"id": PID, "user_id": U, "status": "planned", "route": "tvv2", "master_symbol_root": "NQ", "master_tp": 3600, "master_sl": None,
          "master_contracts": 2, "notes": "Auto-Planer · Etappe", "start_um": "2026-10-08T11:08:00+00:00"}
    upd, a, err = ns["ap_werte_pruefen"](pl, {"start_um": "05:02"}, jetzt, start={"iso": "2026-10-08T01:02:00+00:00", "alt_txt": "15:08", "neu_txt": "05:02"})
    check(err is None and upd["start_um"] == "2026-10-08T01:02:00+00:00" and upd["notes"].endswith("Start 15:08 → 05:02")
          and set(upd) == {"start_um", "notes"} and a["start_um"] == "2026-10-08T01:02:00+00:00",
          f"nur start_um + notes, Notes-Zeile „Start 15:08 → 05:02“ ({upd.get('notes', '').splitlines()[-1] if upd else err})")
    check(ns["ap_werte_pruefen"](pl, {}, jetzt)[2].endswith("start_um angeben"), "leerer Body nennt start_um")

    # ── _ap_werte_setzen mit nachgebautem Stand ──
    mitt = datetime(2026, 10, 7, 22, 0, tzinfo=timezone.utc)             # 00:00 dt am 08.10.
    stand = {"firmen": [], "mitternacht": mitt, "jetzt_min": 150.0, "starts_heute": [], "id_fest": {}, "param": {"laufzeit_min": 120}, "zeiten": {},
             "geplant": []}
    ns.update({"jsonify": lambda d: d, "_ap_stand_laden": lambda reg, j=None, tag=None: (tage.append(tag), stand)[1],
               "_ap_stand_plaene": lambda st: [plan(PID, U, "the5ers", "buy", 790), plan("q1", V, "the5ers", "sell", 155)],
               "_ap_hand_spalte_fehlt": lambda e: False, "AP_FEST_HAND": "Werte von Hand geändert"})
    geschrieben, tage = [], []
    ns["sb_select"] = lambda t, p: [{"id": 1}] if t == "auto_plan_regeln" else [dict(pl)]
    ns["sb_update"] = lambda t, p, u: (geschrieben.append((p, u)) or [dict(pl, **u)])
    echt_now = ns["datetime"]

    class FixDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 8, 0, 30, tzinfo=timezone.utc)      # = 150 min ab 00:00 dt, 04:30 Dubai
    ns["datetime"] = FixDT
    r = ns["_ap_werte_setzen"](PID, {"start_um": "05:02"}, True, "adm")
    p_, u_ = geschrieben[-1] if geschrieben else ({}, {})
    check(isinstance(r, dict) and r["ok"] and u_.get("start_um", "").startswith("2026-10-08T01:02:00") and u_.get("hand_werte_at")
          and "auto_bestaetigt_at" not in u_ and p_.get("start_um_gestartet_at") == "is.null",
          f"05:02 Dubai frei → start_um gesetzt, hand_werte_at, Guard, Bestätigung unberührt ({u_.get('start_um')})")
    check(tage and tage[-1] == "2026-10-08", f"Stand des Ziel-Tages (deutsche Zeit) geladen ({tage})")
    check(u_.get("notes", "").endswith("Start 15:08 → 05:02"), f"Notes in Dubai-Zeit ({u_.get('notes', '').splitlines()[-1] if u_ else ''})")
    r = ns["_ap_werte_setzen"](PID, {"start_um": "04:35"}, True, "adm")
    check(isinstance(r, tuple) and r[1] == 400 and r[0]["msg"].startswith("Firmen-Abstand") and r[0]["vorschlag_dubai"] == "04:36"
          and "um 04:35" in r[0]["msg"] and r[0]["vorschlag"].startswith("2026-10-08T00:36:00"),
          f"04:35 Dubai auf derselben Minute wie andere ID um 04:35 → 400 mit Vorschlag 04:36 ({r[0] if isinstance(r, tuple) else r})")
    r = ns["_ap_werte_setzen"](PID, {"start_um": "2026-10-08T01:20:30.000Z"}, True, "adm")
    check(isinstance(r, dict) and r["ok"] and r["plan"]["start_um"].startswith("2026-10-08T01:20:30"), "ISO-UTC mit Sekunden (Vertrag Slave 5) → ok")
    r = ns["_ap_werte_setzen"](PID, {"start_um": "04:00"}, True, "adm")
    check(isinstance(r, tuple) and r[1] == 400 and "vorbei" in r[0]["msg"], "vorbei → 400")
    ns["datetime"] = echt_now
    print(f"{len(f) - sum(f)}/{len(f)} ok")
    sys.exit(1 if sum(f) else 0)


if __name__ == "__main__":
    main()
