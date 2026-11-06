#!/usr/bin/env python3
"""Selbsttest EIN BESTÄTIGEN JE TRADE (app.py ap_ids_hedge_felder / ap_hedge_freigabe_ids / _ap_eingriff, 30.10.2026). Ohne Netz.
Aufruf: python3 tools/selftest_ein_bestaetigen.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {}
    teile = [re.search(r"^HEDGE_ARTEN = .*$", src, re.M).group(0)]
    for name in ("ap_ids_hedge_felder", "ap_hedge_freigabe_ids", "hf_frei_bei_kennung"):
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("from datetime import datetime, timezone\n" + "\n".join(teile), ns)
    return ns, src


def main():
    ns, src = lade()
    f = []
    ok = lambda b, t: f.append(t) if not b else None   # noqa: E731
    hf, ids = ns["ap_ids_hedge_felder"], ns["ap_hedge_freigabe_ids"]
    vs = {"lots": 5.6, "hedge_eur": 535, "pass_eur": -250}
    ok(hf({"hart": "apex", "hvs": vs}) == {"hedge_art": "apex", "hedge_vorschau": vs, "hedge_frei": False, "hedge_weg": None}, "Apex mit Vorschau")
    ok(hf({"hart": "tradeify_final", "hvs": "kaputt", "hedge_freigabe_at": "2026-10-30T01:00:00Z"})
       == {"hedge_art": "tradeify_final", "hedge_vorschau": None, "hedge_frei": True, "hedge_weg": None}, "Tradeify ohne Objekt, schon frei")
    ok(hf({"hart": "echo", "hvs": vs}) == {"hedge_art": None, "hedge_vorschau": None, "hedge_frei": False, "hedge_weg": None}, "fremde Art → kein Hedge")
    ok(hf({"route": "mt5v2", "hvs": vs}) == {"hedge_art": None, "hedge_vorschau": vs, "hedge_frei": False, "hedge_weg": "echo"}, "Echo V2 mit Vorschau → Chip, ohne hedge_art")
    ok(hf({"route": "mt5", "hvs": {"grund": "x"}})["hedge_weg"] == "echo" and hf({"route": "tvv2", "hvs": vs})["hedge_weg"] is None, "Echo mit Hedge ja, Orbit ohne Art nein")
    ok(hf({"route": "mt5v2"})["hedge_vorschau"] is None and hf({"route": "mt5v2"})["hedge_weg"] is None, "Echo ohne Vorschau → nichts")
    ok(hf({}) == {"hedge_art": None, "hedge_vorschau": None, "hedge_frei": False, "hedge_weg": None}, "normaler Plan")
    z = [{"id": "a", "mt5_baseline": {"hedge_art": "apex"}},
         {"id": "b", "mt5_baseline": {"hedge_art": "tradeify_final"}, "hedge_freigabe_at": "x"},
         {"id": "c", "mt5_baseline": None},
         {"id": "d", "mt5_baseline": {"hedge_art": "tradeify_final"}},
         {"id": "a", "mt5_baseline": {"hedge_art": "apex"}},
         {"id": "e", "mt5_baseline": {"echo_hedge": {"status": "mit"}}}]
    ok(ids(z) == ["a", "d"], "nur Hedge-Pläne ohne Freigabe, ohne Doppelte")
    ok(ids(None) == [] and ids([]) == [], "leer")
    # Verdrahtung: nur bei bestaetigen in Admin-Sicht, Guard wie die Freigabe-Route, a0-Riegel unberührt
    i = src.index("\ndef _ap_eingriff(")
    eing = src[i:src.find("\n\n\n", i)]
    # seit HF2 (06.11.2026, Finn: „einfach einmal ‚Bestätigen', fertig"): JEDES Bestätigen gibt frei — jede Sicht, jede Gruppe (vorher ADMIN-VOLL:
    # nur voller Admin mit sicht None); zurueck/loeschen nie
    ok('_ap_hedge_mit_freigeben(zeilen, uid) if aktion == "bestaetigen" else 0' in eing
       and "voll = admin or (" not in eing, "HF2: jedes Bestätigen gibt frei (nur aktion bestaetigen)")
    i = src.index("\ndef _ap_hedge_mit_freigeben(")
    mit = src[i:src.find("\n\n\n", i)]
    for g in ('"status": "eq.planned"', '"start_um_gestartet_at": "is.null"', '"hedge_freigabe_at": "is.null"', '"mt5_baseline->>hedge_art"'):
        ok(g in mit, "Guard " + g)
    ok("_ap_namen()" not in mit and "not in aus" not in mit, "HF2: keine Gruppen-Ausnahme (ADMIN_EXCLUDE) mehr beim Bestätigen")
    i = src.index("\ndef ap_auto_best_tick(")
    ab = src[i:src.find("\n\n\n", i)]
    ok('_ap_hedge_mit_freigeben(zeilen, "auto_bestaetigen")' in ab, "HF2: Auto-Bestätigen gibt Hedge-Pläne mit frei")
    fk = ns["hf_frei_bei_kennung"]
    from datetime import datetime, timezone
    t0 = datetime(2026, 11, 6, 1, 0, tzinfo=timezone.utc)
    ok(fk({"auto_bestaetigt_at": "x", "hedge_freigabe_at": None}, t0) == {"hedge_freigabe_at": t0.isoformat(), "hedge_freigabe_von": "bestaetigt"},
       "HF2: bestätigt, ohne Freigabe → Freigabe im selben Update")
    ok(fk({"auto_bestaetigt_at": None, "hedge_freigabe_at": None}, t0) == {}, "HF2: unbestätigt → keine Freigabe")
    ok(fk({"auto_bestaetigt_at": "x", "hedge_freigabe_at": "y"}, t0) == {}, "HF2: schon freigegeben → nichts")
    ok(fk({"auto_bestaetigt_at": "x"}, t0) == {}, "HF2: Spalte nicht mitgelesen (ah-Rückfall) → nichts")
    ok(src.count("**hf_frei_bei_kennung(p))") == 3, "HF2: Kennung tfh (2×) + ah (1×) gibt schon bestätigte Pläne mit frei")
    j = src.index("\ndef _hedge_freigabe_schreiben(")
    schreib = src[j:src.find("\n\n\n", j)]
    ok("_hedge_freigabe_schreiben(" in mit and "hedge_freigabe_von" in schreib and '"auto_bestaetigt_at"' not in schreib and mit.split('"""')[2].count("auto_bestaetigt_at") == 1 and '"auto_bestaetigt_at": "not.is.null"' in mit,   # HF2: nur als Guard, nie geschrieben
       "setzt nur die Freigabe-Spalten (start_um nur bei überfälligem Plan, FINAL-FREIGABE-SPAET)")
    ok("hvs:mt5_baseline->hedge_vorschau" in src and "**ap_ids_hedge_felder(p)" in src, "/ids liefert die Hedge-Felder")
    for t in f:
        print("✗", t)
    print("OK" if not f else f"\n{len(f)} FEHLER")
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
