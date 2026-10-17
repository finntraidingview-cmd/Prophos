#!/usr/bin/env python3
"""Selbsttest FREMD WEG_AT (app.py fp_tick, S4 18.10.2026): eine Fremd-Zeile bekommt weg_at, sobald eine frische, vollständige Lesung
des Kontos die Position nicht mehr zeigt — auch wenn die Zeile älter als 3 min ist (bis dahin endete der Takt bei „aktiv == 0" vor dem
Schließen; 5 TV-Zeilen blieben so seit 09.–16.10. offen). Ohne frische Lesung bleibt die Zeile. DB als Attrappe, ohne Netz.

Aufruf:  python3 tools/selftest_fremd_weg_at.py
Lädt die Funktionen per Quelltext aus app.py (Muster selftest_auto_ext: app.py zieht beim Import Flask und Threads)."""
import os
import re
import sys
import time
import types
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")

DB = {"fremd": [], "echoplus": [], "accounts": [], "calls": []}


def sb_select(t, p):
    DB["calls"].append(("select", t))
    if t == "echoplus_live":
        return [dict(z) for z in DB["echoplus"]]
    if t == "accounts":
        return [dict(a) for a in DB["accounts"]]
    if t == "fremd_positionen":
        ab = str(p.get("zuletzt_gesehen") or "gt.")[3:]          # Filter „gt.<Zeit>" wie PostgREST (alter Stand las so)
        return [dict(f) for f in DB["fremd"] if f["weg_at"] is None and f["zuletzt_gesehen"] > ab]
    return []


def sb_update(t, filt, val):
    DB["calls"].append(("update", t))
    n = 0
    if "master_login" in filt:
        logins = filt["master_login"][4:-1].split(",")
        for f in DB["fremd"]:
            if (f["weg_at"] is None and f["quelle"] == filt["quelle"][3:] and f["master_login"] in logins
                    and f["zuletzt_gesehen"] < filt["zuletzt_gesehen"][3:]):
                f.update(val)
                n += 1
    return n


class _Antwort:
    def json(self):
        return []


def lade():
    src = open(APP, encoding="utf-8").read()

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]
    ns = {"time": time, "re": re, "datetime": datetime, "timezone": timezone,
          "requests": types.SimpleNamespace(exceptions=types.SimpleNamespace(HTTPError=Exception)),
          "sb_select": sb_select, "sb_update": sb_update, "SUPABASE_URL": "x",
          "_sb_anfrage": lambda *a, **k: DB["calls"].append(("post", a[1].rsplit("/", 1)[-1])) or _Antwort(),
          "_sb_pruefen": lambda r: None, "_sb_headers": lambda *a: {}, "_ap_archiviert": lambda: set(),
          "lt_echo_live_wahl": lambda rows: {}, "_ap_namen": lambda: ({}, {}), "_zw_admin_uids": lambda: set(),
          "push_an_user": lambda *a, **k: None}
    for k in ("FP_TAKT_S", "FP_FRISCH_S"):
        exec(re.search(rf"^{k} = .*$", src, re.M).group(0), ns)
    i = src.index("\n_fp = {") + 1                   # _fp steht über zwei Zeilen — bis die Klammer zu ist
    j, tiefe = i, 0
    while True:
        tiefe += {"{": 1, "}": -1}.get(src[j], 0)
        j += 1
        if tiefe == 0 and src[j - 1] == "}":
            break
    exec(src[i:j], ns)
    for f in ("_fp_ts", "fp_plan_aktiv", "fp_erkennen", "fp_konto_norm", "fp_preis_norm", "fp_erkennen_tv", "fp_alarme",
              "_fp_richtung", "_fp_tabelle_fehlt", "fp_tick"):
        exec(block(f), ns)
    return ns


def main():
    ns = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    jetzt = lambda: datetime.now(timezone.utc).isoformat()
    alt = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    DB["fremd"] = [{"id": 1, "quelle": "tv", "master_login": "APEX0000000000001", "weg_at": None, "zuletzt_gesehen": alt,
                    "alarm_keys": [], "gegen": []},
                   {"id": 2, "quelle": "tv", "master_login": "MFFU000000000002", "weg_at": None, "zuletzt_gesehen": alt,
                    "alarm_keys": [], "gegen": []}]
    DB["accounts"] = [{"id": "a1", "user_id": "u1", "firm": "Apex", "name": "Apex", "account_type": "challenge",
                       "external_id": "APEX0000000000001"},
                      {"id": "a2", "user_id": "u2", "firm": "MFFU", "name": "MFFU", "account_type": "funded",
                       "external_id": "MFFU000000000002"}]
    tick = lambda: ns["fp_tick"](force=True)

    tick()
    check(all(f["weg_at"] is None for f in DB["fremd"]), "keine Lesung → beide Altzeilen bleiben")
    check(ns["_fp"]["offen"] == 2 and ns["_fp"]["aktiv"] == 0, "offen zählt Altzeilen (2), aktiv nur die letzten 3 min (0)")

    DB["echoplus"] = [{"konto": "APEX0000000000001", "positionen": [], "positionen_ok": False, "updated_at": jetzt()}]
    tick()
    check(DB["fremd"][0]["weg_at"] is None, "Lesung nicht vollständig (positionen_ok false) → bleibt")

    DB["echoplus"] = [{"konto": "APEX0000000000001", "positionen": [], "positionen_ok": True, "updated_at": jetzt()}]
    tick()
    check(DB["fremd"][0]["weg_at"] is not None, "frisch + vollständig + flach → weg_at (Altzeile, aktiv war 0)")
    check(DB["fremd"][1]["weg_at"] is None, "anderes Konto ohne Lesung → bleibt")

    DB["calls"].clear()
    DB["echoplus"] = [{"konto": "TDFY0000000000003", "positionen": [], "positionen_ok": True, "updated_at": jetzt()}]
    tick()
    check(("update", "fremd_positionen") not in DB["calls"], "flaches Konto ohne offene Zeile → kein PATCH")

    DB["fremd"][1]["weg_at"] = "x"
    tick()
    DB["calls"].clear()
    tick()
    check(ns["_fp"]["offen"] == 0 and ("select", "fremd_positionen") not in DB["calls"], "nichts offen → früher Ausstieg ohne Schreiben")

    print("\nALLES OK" if ok else "\nFEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
