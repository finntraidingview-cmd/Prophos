#!/usr/bin/env python3
"""Selbsttest NACHHOLEN PARALLEL (app.py _ap_nachholen + _AP_NACHHOL_LOCK, 08.10.2026, Slave-Terminal 4 — Befund Slave 2 zu 96a89a6:
zwei Tabs derselben ID (gleiche pc_id, Fall pc-40mali) rufen „nachholen" gleichzeitig für verschiedene verpasste Pläne auf; beide laden
denselben Stand und bekamen dieselbe freie Minute → zwei Starts zu eng).
Ohne Netz: die echten _ap_nachholen / _ap_nachholen_kern / ap_nachhol_minute (samt Regeln) laufen gegen eine Fake-DB; das Laden des
Stands wartet künstlich 0,3 s, damit sich zwei Threads sicher überlappen. Geprüft:
  1 zwei verpasste Pläne derselben ID (andere Firmen) parallel → ≥ 5 min auseinander (PC-Regel; 20 min je ID seit 08.10.2026 weg)
  2 zwei IDs, gleiche Firma, parallel → ≥ 1 min auseinander (Firmen-Abstand, seit 08.10.2026 1 statt 5 min)
  3 Gegenprobe OHNE Lock: dieselben zwei Aufrufe landen < 5 min auseinander — der Test misst also wirklich die Serialisierung
  4 der Lock steht im Quelltext genau um _ap_nachholen_kern
Aufruf: python3 tools/selftest_auto_nachholen_parallel.py"""
import contextlib
import os
import random
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_nachholen as sn  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


MITTERNACHT = datetime(2026, 10, 8, 0, 0, tzinfo=timezone.utc)
JETZT_MIN = 300.0                                   # 05:00 — fest, unabhängig von der echten Uhr


def welt(plaene):
    """Fake-DB + Stubs für _ap_nachholen_kern. plaene: {plan_id: {user_id, firma, richtung, start_min}}."""
    db = {pid: dict(p) for pid, p in plaene.items()}
    db_lock = threading.Lock()

    def sb_select(tab, q):
        if tab == "auto_plan_regeln":
            return [{"id": 1}]
        pid = str(q.get("id", "")).replace("eq.", "")
        with db_lock:
            p = db.get(pid)
            return [{"id": pid, "user_id": p["user_id"], "status": "planned", "start_um": None, "started_at": None,
                     "orbit_gesendet_at": None, "master_firm": p["firma"], "richtung": p["richtung"], "mt5_baseline": {}}] if p else []

    def stand_laden(reg, jetzt):
        with db_lock:
            schnapp = [dict(p, plan_id=pid) for pid, p in db.items()]
        time.sleep(0.3)                              # beide Threads haben jetzt denselben (alten) Stand gelesen — ohne Lock
        return {"plaene": schnapp, "starts_heute": [], "id_fest": {}, "jetzt_min": JETZT_MIN, "zeiten": {"start_bis": "16:30"},
                "param": {}, "offen": [], "firmen": [], "mitternacht": MITTERNACHT}

    def sb_update(tab, filt, werte):
        pid = str(filt.get("id", "")).replace("eq.", "")
        neu = datetime.fromisoformat(werte["start_um"])
        with db_lock:
            db[pid]["start_min"] = round((neu - MITTERNACHT).total_seconds() / 60.0, 2)
            return [{"id": pid}]

    class _R:
        pass
    stubs = {"sb_select": sb_select, "_ap_stand_laden": stand_laden, "_ap_stand_plaene": lambda st: st["plaene"],
             "ap_firma_key": lambda firmen, f: f, "sb_update": sb_update, "jsonify": lambda d: d,
             "_ap_tz": lambda z: timezone.utc, "AP_7T_TZ": "UTC", "_sb_anfrage": lambda *a, **k: _R(), "SUPABASE_URL": "",
             "_sb_headers": lambda: {}, "_sb_pruefen": lambda r: None, "datetime": datetime, "timezone": timezone,
             "timedelta": timedelta, "threading": threading, "random": random}
    return db, stubs


def lade(mit_lock=True):
    a = sn.lade()
    src = open(sn.sd.APP, encoding="utf-8").read()
    i = src.index("\n_AP_NACHHOL_LOCK = ") + 1
    teil = src[i:src.find("\n\n\ndef ap_werte_pruefen(", i)]
    return a, teil, src


def lauf(plaene, aufrufe, mit_lock=True):
    a, teil, _ = lade()
    db, stubs = welt(plaene)
    ns = dict(a)
    ns.update(stubs)
    exec(teil, ns)
    if not mit_lock:
        ns["_AP_NACHHOL_LOCK"] = contextlib.nullcontext()
    erg = {}

    def eins(pid, uid):
        erg[pid] = ns["_ap_nachholen"](pid, False, uid)
    th = [threading.Thread(target=eins, args=(pid, uid)) for pid, uid in aufrufe]
    for t in th:
        t.start()
    for t in th:
        t.join()
    return db, erg


def main():
    U, V = "u-test-1", "u-test-2"
    GFA, PC = lade()[0]["AP_FIRMA_ABSTAND_MIN"], 3 + 2   # Firmen-Abstand / PC-Regel (abstand_id_min 3 + Laufdauer 2)
    # 1: zwei verpasste Pläne derselben ID, andere Firmen
    p1 = {"p-a": {"user_id": U, "firma": "tradeify", "richtung": "buy", "start_min": 125.0},
          "p-b": {"user_id": U, "firma": "topstep", "richtung": "sell", "start_min": 283.0}}
    db, erg = lauf(p1, [("p-a", U), ("p-b", U)])
    ma, mb = db["p-a"]["start_min"], db["p-b"]["start_min"]
    check(all(isinstance(x, dict) and x.get("ok") for x in erg.values()), f"beide Aufrufe ok ({erg})")
    check(abs(ma - mb) >= PC, f"1 gleiche ID parallel → ≥ {PC} min auseinander (PC-Regel) ({ma} / {mb})")
    check(min(ma, mb) >= JETZT_MIN + 2, "frühestens jetzt + 2 min")
    # 2: zwei IDs, gleiche Firma
    p2 = {"q-a": {"user_id": U, "firma": "fundednext", "richtung": "sell", "start_min": 200.0},
          "q-b": {"user_id": V, "firma": "fundednext", "richtung": "sell", "start_min": 210.0}}
    db, _ = lauf(p2, [("q-a", U), ("q-b", V)])
    qa, qb = db["q-a"]["start_min"], db["q-b"]["start_min"]
    check(abs(qa - qb) >= GFA, f"2 zwei IDs gleiche Firma parallel → ≥ {GFA:g} min (Firmen-Abstand) ({qa} / {qb})")
    # 3: Gegenprobe ohne Lock
    db, _ = lauf(p1, [("p-a", U), ("p-b", U)], mit_lock=False)
    oa, ob = db["p-a"]["start_min"], db["p-b"]["start_min"]
    check(abs(oa - ob) < PC, f"3 Gegenprobe ohne Lock: Kollision nachgewiesen ({oa} / {ob}) — der Test misst die Serialisierung")
    # 4: Quelltext
    _, teil, src = lade()
    check(re.search(r"def _ap_nachholen\(pid, alle, uid, jetzt=None\):\n(?:    .*\n)*?    with _AP_NACHHOL_LOCK:\n        return _ap_nachholen_kern\(", src) is not None,
          "4 _ap_nachholen hält _AP_NACHHOL_LOCK um _ap_nachholen_kern")
    check("_ap_nachholen(pid, alle, uid)" in src, "Route ruft weiter _ap_nachholen (mit Lock)")
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
