#!/usr/bin/env python3
"""Selbsttest: Userscript-Version-Wache (app.py skript_wacht_pruefen / skript_wacht_ht_filter / _version_neuer, 29.10.2026) — nur
HT-PCs, alte Version, frisch, nach der Karenz, nicht doppelt. Rein rechnend, ohne Netz. Kennungen frei erfunden.
Aufruf: python3 tools/selftest_skript_wacht.py"""
import os
import re
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_version_neuer", "skript_wacht_pruefen", "skript_wacht_ht_filter", "tsx_wacht_zeilen")
KONSTANTEN = ("SKRIPT_WACHT_TAKT_S", "SKRIPT_WACHT_KARENZ_S", "SKRIPT_WACHT_WIEDER_S")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone}
    teile = []
    for k in KONSTANTEN:
        m = re.search(rf"^(\w+, )*{k}\b[^\n]*$", src, re.M)
        teile.append(m.group(0))
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def main():
    ns = lade()
    f = []
    ok = lambda b, t: f.append(t) if not b else None   # noqa: E731
    jetzt = 1_800_000_000.0
    iso = lambda s: datetime.fromtimestamp(jetzt - s, timezone.utc).isoformat()   # noqa: E731
    rows = [{"pc_name": "pc-aaaa01", "script_version": "0.9.8", "updated_at": iso(60)},
            {"pc_name": "pc-aaaa02", "script_version": "0.10.1", "updated_at": iso(60)},
            {"pc_name": "pc-aaaa03", "script_version": "0.9.7", "updated_at": iso(60)},
            {"pc_name": "pc-aaaa04", "script_version": "0.9.7", "updated_at": iso(60)},
            {"pc_name": "pc-aaaa05", "script_version": "0.9.7", "updated_at": iso(3600)}]
    live = [{"pc_name": "pc-aaaa01", "user_id": "ht-1"}, {"pc_name": "pc-aaaa01", "user_id": "emin-alt"},
            {"pc_name": "pc-aaaa02", "user_id": "ht-2"}, {"pc_name": "pc-aaaa03", "user_id": "emin-1"},
            {"pc_name": "pc-aaaa05", "user_id": "ht-3"}]
    fremd = lambda u: u.startswith("emin")   # noqa: E731
    gefiltert = ns["skript_wacht_ht_filter"](rows, live, fremd)
    ok([r["pc_name"] for r in gefiltert] == ["pc-aaaa01", "pc-aaaa02", "pc-aaaa05"],
       f"Filter: Emin-PC raus, PC ohne ID raus, jüngste mt5_live-Zeile zählt ({[r['pc_name'] for r in gefiltert]})")
    ok(ns["skript_wacht_ht_filter"](rows, [], fremd) == [], "Filter: ohne mt5_live nie eine Meldung (fail-closed)")
    tr = ns["skript_wacht_pruefen"](gefiltert, "0.10.1", jetzt, jetzt - 3600, {})
    ok(tr == [("pc-aaaa01", "0.9.8")], f"Wache: alte Version + frisch → Meldung, aktuell/alt-Stand nicht ({tr})")
    ok(ns["skript_wacht_pruefen"](gefiltert, "0.10.1", jetzt, jetzt - 60, {}) == [], "Wache: in der Karenz nach dem Deploy still")
    ok(ns["skript_wacht_pruefen"](gefiltert, "0.10.1", jetzt, jetzt - 3600, {("pc-aaaa01", "0.10.1"): jetzt - 100}) == [],
       "Wache: (PC, Soll) in 24 h schon gemeldet → still")
    ok(ns["_version_neuer"]("0.10.1", "0.9.13") and not ns["_version_neuer"]("0.9.13", "0.10.1"), "Versionsvergleich je Stelle (0.10 > 0.9)")
    # TopstepX-Auge: Zeilen aus mt5_live.status.tsx_auge (jüngste je PC, laeuft vor script), dann dieselbe Wache
    live_tsx = [{"pc_name": "pc-aaaa01", "updated_at": iso(30), "user_id": "ht-1", "tsx": {"script": "0.3.0", "laeuft": "0.2.0"}},
                {"pc_name": "pc-aaaa01", "updated_at": iso(90), "user_id": "ht-1", "tsx": {"script": "0.1.0"}},
                {"pc_name": "pc-aaaa02", "updated_at": iso(30), "user_id": "ht-2", "tsx": None},
                {"pc_name": "pc-aaaa03", "updated_at": iso(30), "user_id": "emin-1", "tsx": {"script": "0.2.0"}},
                {"pc_name": "pc-aaaa05", "updated_at": iso(30), "user_id": "ht-3", "tsx": {"script": "0.3.0", "laeuft": "0.3.0"}}]
    z = ns["tsx_wacht_zeilen"](live_tsx)
    ok([(r["pc_name"], r["script_version"]) for r in z] == [("pc-aaaa01", "0.2.0"), ("pc-aaaa03", "0.2.0"), ("pc-aaaa05", "0.3.0")],
       f"Auge-Zeilen: jüngste je PC, laeuft zählt, PC ohne Auge raus ({z})")
    tz = ns["skript_wacht_pruefen"](ns["skript_wacht_ht_filter"](z, live_tsx, fremd), "0.3.0", jetzt, jetzt - 3600, {})
    ok(tz == [("pc-aaaa01", "0.2.0")], f"Auge-Wache: alter Kern auf HT-PC gemeldet, Emin-PC und aktueller PC still ({tz})")
    for t in f:
        print("✗", t)
    print("alle Tests bestanden" if not f else f"FEHLER ({len(f)})")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
