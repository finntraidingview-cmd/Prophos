#!/usr/bin/env python3
"""Selbsttest FIRMEN-ABSTAND ZU WINNING-DAYS-FARMER-BLÖCKEN (app.py ap_wd_block_starts + _ap_stand_laden, 08.10.2026, Master/Finn:
„Halten Starts aus dem Winning-Days-Farmer den 5-min-Abstand je Firma ein?"). Lücke: der Farmer würfelt 00:10 Dubai, seine Pläne
entstehen erst später — der Nachtlauf (01:30) und der Bot sahen die Blöcke aus wd_tagesplan nicht. Ohne Netz, Platzhalter-IDs.
Aufruf: python3 tools/selftest_auto_wd_firmen_abstand.py
Geprüft: (1) ap_wd_block_starts — Zeiten wie wdKontoZeiten (Blockstart + 80 s je AKTIVEM Konto), inaktive zählen nicht mit,
Konten mit bekanntem Plan entfallen, leere/ungewürfelte Blöcke und Zeiten außerhalb des Tags nicht; (2) _ap_firma_konflikt — ein
änderbarer Auto-Plan einer anderen ID bei derselben Firma 2 min neben einem Farmer-Konto weicht, 8 min nicht, gleiche ID / andere
Firma nicht; (3) Probelauf ap_planen mit dichten Farmer-Blöcken einer dritten ID bei Tradeify: kein Tradeify-Auto-Plan < 5 min daneben."""
import os
import random
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    a = sd.lade()
    W, K, GFA = a["ap_wd_block_starts"], a["_ap_firma_konflikt"], a["AP_FIRMA_ABSTAND_MIN"]
    firmen = sd.FIRMEN
    mn = datetime(2026, 10, 8, 0, 0, tzinfo=timezone.utc)
    U3 = sd.U3
    blk = {"user_id": U3, "name": "Drei", "status": "geplant", "start_um": "2026-10-08T02:05:00+00:00", "richtung": "buy",
           "konten": [{"id": "w1", "firm": "Tradeify", "aktiv": True}, {"id": "w2", "firm": "Topstep", "aktiv": False},
                      {"id": "w3", "firm": "Tradeify"}, {"id": "w4", "firm": "Tradeify", "aktiv": True, "plan_id": "p-bekannt"}]}
    out = W([blk], mn, firmen, bekannt=["p-bekannt"])
    zeiten = [x["start"] for x in out]
    check(len(out) == 2 and zeiten == [125.0, round(125 + 80 / 60, 2)], f"aktive Konten: Blockstart + 80 s je aktivem Konto, inaktives zählt nicht, bekannter Plan entfällt ({zeiten})")
    check(all(x["user_id"] == U3 and x["richtung"] == "buy" and x["wd"] for x in out), "user_id/Richtung/wd-Marke je Start")
    fk = out[0]["firma"]
    check(fk == a["ap_firma_key"](firmen, "Tradeify"), f"Firmen-Schlüssel wie der Planer (ap_firma_key: {fk})")
    leer = dict(blk, status="leer"); ohne = dict(blk, start_um=None); morgen = dict(blk, start_um="2026-10-09T03:00:00+00:00")
    check(W([leer, ohne, morgen], mn, firmen) == [], "leer / ungewürfelt / anderer Tag → nichts")
    laeuft = dict(blk, status="laeuft")
    check(len(W([laeuft], mn, firmen)) == 3, "laufender Block: noch nicht gestartete Konten zählen (ohne bekannten Plan alle 3 aktiven)")
    check(W([dict(blk, start_um="kaputt")], mn, firmen) == [], "kaputte Zeit → übersprungen, kein Fehler")

    # ── 2 Konflikt gegen Farmer-Start ──
    je = {"p1": {"user_id": sd.U2, "firma": fk, "aenderbar": True}}
    for d, soll, txt in ((2, True, "2 min neben Farmer-Konto einer anderen ID → weicht"), (8, False, "8 min daneben (6,7 min zum zweiten Konto) → frei")):
        z = {"p1": {"start": 125.0 + d}}
        check(K("p1", je, z, out) is soll, txt)
    # seit 09.10.2026 (Finn über Master) zählt der Firmen-Abstand NICHT mehr innerhalb derselben ID — nur zwischen IDs
    check(K("p1", {"p1": {"user_id": U3, "firma": fk, "aenderbar": True}}, {"p1": {"start": 126.0}}, out) is False, "gleiche ID wie der Farmer-Block, < 1 min daneben → frei (09.10.2026)")
    check(K("p1", {"p1": {"user_id": U3, "firma": fk, "aenderbar": True}}, {"p1": {"start": 128.0}}, out) is False, "gleiche ID, ≥ 1 min daneben → frei")
    check(K("p1", {"p1": {"user_id": sd.U2, "firma": "apextrader", "aenderbar": True}}, {"p1": {"start": 126.0}}, out) is False, "andere Firma → frei")

    # ── 3 Probelauf mit dichten Farmer-Blöcken (U3, Tradeify) ──
    jetzt = datetime(2026, 10, 7, 21, 0, tzinfo=timezone.utc)
    reg, _ = sd.db_stubs(a, jetzt)
    alt_sel = a["sb_select"]
    wd_rows, wd_zeit = [], []
    tag_dt = datetime(2026, 10, 8, 0, 0, tzinfo=timezone.utc) - timedelta(hours=2)   # Mitternacht Berlin (Sommerzeit) = 22:00 UTC Vortag
    for i in range(70):
        t = tag_dt + timedelta(minutes=30 + 15 * i)
        wd_rows.append({"tag": "2026-10-08", "user_id": U3, "name": "Drei", "status": "geplant", "start_um": t.isoformat(), "richtung": "sell",
                        "konten": [{"id": f"w{i}", "firm": "Tradeify", "aktiv": True}]})
        wd_zeit.append((t - tag_dt).total_seconds() / 60.0)   # Minuten ab Mitternacht Berlin, wie geplant[].start
    a["sb_select"] = lambda table, params: [dict(r) for r in wd_rows] if table == "wd_tagesplan" else alt_sel(table, params)
    # Feste Uhr für den Probelauf (08.10.2026, Prüfer: Test ab ~14:30 UTC rot, auch an älteren Ständen): ap_planen nahm die echte Uhr,
    # nach start_bis des 08.10. (bzw. ab dem 09.10. für immer) gab es „0 geplant" — jetzt gilt im Lauf dasselbe jetzt wie für die Stubs
    echt_dt = a["datetime"]

    class FixDT(echt_dt):
        @classmethod
        def now(cls, tz=None):
            return jetzt if tz is not None else jetzt.replace(tzinfo=None)
    a["datetime"] = FixDT
    nah, n_tdfy, laeufe = 0, 0, 0
    for seed in (1, 7, 4711):
        erg = a["ap_planen"]("2026-10-08", trocken=True, seed=seed)
        if not erg.get("ok"):
            check(False, f"Probelauf seed {seed}: {erg.get('msg') or erg.get('probelauf_fehler')}")
            continue
        laeufe += 1
        for g in erg.get("geplant", []):
            if g.get("firma") != "Tradeify" or not g.get("start"):
                continue
            n_tdfy += 1
            hh, mm = (int(x) for x in str(g["start"]).split(":")[:2])   # „HH:MM" deutsche Zeit (_ap_hhmm_txt)
            nah += any(abs(hh * 60 + mm - w) < GFA - 0.5 for w in wd_zeit)
    a["sb_select"] = alt_sel
    a["datetime"] = echt_dt
    check(laeufe == 3, "Probelauf mit wd_tagesplan läuft durch (3 Seeds)")
    check(n_tdfy > 0 and nah == 0, f"kein Tradeify-Auto-Plan < {GFA:g} min neben einem Farmer-Konto einer anderen ID ({n_tdfy} Pläne, {nah} zu nah)")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
