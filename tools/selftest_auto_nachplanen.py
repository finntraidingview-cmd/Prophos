#!/usr/bin/env python3
"""Selbsttest NACHPLANEN neuer Konten (app.py, 08.10.2026; Master/Finn: Finn setzte um 01:20 Dubai fünf IDs in den Planer,
der Nachtlauf war durch — bis zum nächsten hätte niemand Vorschläge bekommen) — ohne Netz.

Aufruf:  python3 tools/selftest_auto_nachplanen.py
Lädt die Auto-Planer-Funktionen wie selftest_auto_delta (per Quelltext aus app.py). Geprüft: ap_nachplan_fenster (Mo–Fr,
00:00 ≤ jetzt < start_bis − 15 min), ap_nachplan_kandidaten (ohne Plan heute, Haken aus / archiviert / fester Grund raus,
Plan anderer Tage blockt nicht, open/review blocken), ap_planen(nur_konten) gegen die nachgebaute DB: nur das genannte Konto
wird angelegt, bestehender Vorschlag bleibt (kein DELETE), Protokoll quelle 'nachplanen' nur bei Treffer, Startzeit ≥ jetzt + 15 min,
ohne nur_konten unverändert (DELETE + Protokoll). Platzhalter-IDs, keine echten Konten."""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

U1, U2 = sd.U1, sd.U2


def lade():
    a = sd.lade()
    src = open(sd.APP, encoding="utf-8").read()

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]
    exec("\n".join([re.search(rf"^{k} = .*$", src, re.M).group(0) for k in ("AP_NACHPLAN_VORLAUF_MIN", "AP_NACHPLAN_TAKT_S")]
                   + [re.search(r"^AP_NACHPLAN_FEST_GRUENDE = \([^)]*\)", src, re.M | re.S).group(0)]
                   + [block(f) for f in ("ap_nachplan_fenster", "_ap_plan_am_tag", "ap_nachplan_kandidaten")]), a)
    return a


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    tz = a["_ap_tz"]("Europe/Berlin")
    F = a["ap_nachplan_fenster"]
    z = {"start_bis": "16:30"}
    check(F(datetime(2026, 10, 8, 0, 5, tzinfo=tz), z) and F(datetime(2026, 10, 8, 16, 14, tzinfo=tz), z)
          and not F(datetime(2026, 10, 8, 16, 15, tzinfo=tz), z) and not F(datetime(2026, 10, 10, 9, 0, tzinfo=tz), z),
          "Fenster: 00:05 ja, 16:14 ja, 16:15 nein (start_bis − 15), Samstag nein")

    K = a["ap_nachplan_kandidaten"]
    tag = "2026-10-08"
    konten = [{"id": "k-1", "account_type": "phase1"}, {"id": "k-2", "account_type": "phase2"}, {"id": "k-3", "account_type": "challenge"},
              {"id": "k-4", "account_type": "funded"}, {"id": "k-5", "account_type": "phase1", "auto_planer": False},
              {"id": "k-6", "account_type": "phase1"}, {"id": "k-7", "account_type": "phase1"}, {"id": "k-8", "account_type": "phase1"}]
    plaene = [{"master_account_id": "k-1", "status": "planned", "planned_for": tag},                       # heute geplant → belegt
              {"master_account_id": "k-2", "status": "planned", "planned_for": "2026-10-09"},              # morgen → frei
              {"master_account_id": "k-3", "status": "open"},                                               # läuft → belegt
              {"master_account_id": "k-7", "status": "planned", "start_um": "2026-10-07T23:30:00+00:00"},  # 01:30 dt heute → belegt
              {"master_account_id": "k-8", "status": "completed", "planned_for": tag}]                     # erledigt → frei
    letzter = {"tag": tag, "ausgelassen": [{"konto_id": "k-6", "grund": "keine Regel für diese Firma"},
                                            {"konto_id": "k-8", "grund": "Balance nicht live (seit dem letzten Trade nicht nachgelesen)"}]}
    check(K(konten, plaene, tag, tz, letzter, set()) == ["k-2", "k-8"],
          "Kandidaten: nur Konten ohne Plan heute (k-2 morgen frei, k-8 erledigt + veränderlicher Grund), funded/Haken aus/fester Grund/open/heute raus")
    k2 = K(konten, plaene, tag, tz, {"tag": "2026-10-07", "ausgelassen": [{"konto_id": "k-2", "grund": "keine Regel für diese Firma"}]}, {"k-8"})
    check(k2 == ["k-2", "k-6"], f"Lauf eines anderen Tags zählt nicht (k-6 wieder dabei), Archiv k-8 raus ({k2})")

    # ap_planen mit nur_konten gegen die nachgebaute DB
    jetzt = datetime(2026, 10, 8, 7, 0, tzinfo=timezone.utc)
    vorschlag = {"id": "p-alt", "user_id": U1, "master_account_id": "k-2", "master_firm": "FundedNext", "status": "planned", "richtung": "buy",
                 "master_tp": 1000, "master_sl": 500, "master_contracts": 1, "auto_plan": True, "auto_bestaetigt_at": None,
                 "start_um_gestartet_at": None, "start_um": "2026-10-08T12:00:00+00:00", "planned_for": "2026-10-08", "route": "mt5v2",
                 "mt5_baseline": {}}
    reg, gesch = sd.db_stubs(a, jetzt, geplant_extra=[vorschlag])
    protokoll = []
    a["sb_insert"] = lambda table, body: protokoll.append((table, body))
    class R2:
        status_code = 201

        def raise_for_status(self):
            return None
    a["_sb_anfrage"] = lambda *x, **k: (gesch["post"].append((x, k)), R2())[1]
    konten_db = a["_sb_all"]("accounts", {})
    ziel = next((k["id"] for k in konten_db if k["user_id"] == U1 and k["id"] != "k-2" and k["account_type"] in a["AP_TYPEN"]), None)
    check(ziel is not None, f"Fixture hat ein planbares Konto für nur_konten ({ziel})")
    vorher = datetime.now(timezone.utc)
    erg = a["ap_planen"](None, quelle="nachplanen", nur_konten=[ziel], seed=7)   # heute (Dubai) wie der Takt
    geplant = erg.get("geplant") or []
    posts = [x for x in gesch["post"] if x[0][0] == "POST"]
    deletes = [x for x in gesch["post"] if x[0][0] == "DELETE"]
    check(erg.get("ok") and erg.get("quelle") == "nachplanen" and erg.get("nur_konten") == [ziel], "Lauf ok, quelle nachplanen, nur_konten in der Antwort")
    check(all(g["konto_id"] == ziel for g in geplant) and all(z["konto_id"] == ziel for z in erg.get("ausgelassen") or []),
          f"nur das genannte Konto gerechnet (geplant {len(geplant)}, ausgelassen {len(erg.get('ausgelassen') or [])})")
    check(not deletes, "kein DELETE — bestehender Vorschlag p-alt bleibt")
    if geplant:
        zeilen = posts[-1][1]["json"] if posts else []
        start = datetime.fromisoformat(zeilen[0]["start_um"]) if zeilen else None
        check(len(zeilen) == len(geplant) and start is not None and start >= vorher + timedelta(minutes=14),
              f"angelegt {len(zeilen)} Zeile(n), Start {start} ≥ jetzt + 15 min (jetzt {vorher.strftime('%H:%M')} UTC)")
        check(len(protokoll) == 1 and protokoll[0][0] == "auto_plan_lauf" and protokoll[0][1]["quelle"] == "nachplanen",
              "Protokoll genau einmal mit quelle nachplanen")
    else:
        check(not posts and not protokoll, f"nichts geplant ({(erg.get('ausgelassen') or [{}])[0].get('grund')}) → kein POST, kein Protokoll")
    # Konto ohne Chance (nur_konten mit k-2, das schon den Vorschlag hat): nichts geplant → kein Protokoll, kein DELETE
    protokoll.clear(); gesch["post"].clear()
    erg2 = a["ap_planen"](None, quelle="nachplanen", nur_konten=["k-2"], seed=7)
    check(not (erg2.get("geplant") or []) and any("schon einen geplanten" in z.get("grund", "") for z in erg2.get("ausgelassen") or [])
          and not protokoll and not gesch["post"], "bestehender Vorschlag zählt als Plan → ausgelassen, kein Protokoll, nichts geschrieben")
    # ohne nur_konten wie bisher: Vorschlag wird ersetzt (DELETE) und Protokoll geschrieben
    protokoll.clear(); gesch["post"].clear()
    erg3 = a["ap_planen"](None, quelle="hand", seed=7)
    check(erg3.get("ok") and any(x[0][0] == "DELETE" for x in gesch["post"]) and len(protokoll) == 1 and protokoll[0][1]["quelle"] == "hand",
          "ohne nur_konten unverändert: DELETE der Vorschläge + Protokoll")
    print("\nNACHPLANEN:", "alles grün" if ok else "FEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
