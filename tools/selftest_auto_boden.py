#!/usr/bin/env python3
"""Selbsttest: Boden je Konto für den Balance-Balken (app.py ap_boden_konto / _ap_boden, 08.10.2026, Master/Slave 4: Skala
Liquidations-Level → Ziel) — rein rechnend, ohne Netz. Gleiche Rechnung wie der SL-Deckel in ap_konto_rechnen.
Aufruf: python3 tools/selftest_auto_boden.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_wd_num", "ap_groesse", "_ap_spanne", "_ap_runden", "ap_kw_param", "_ap_boden", "ap_boden_konto", "ap_kette_regel", "ap_kette_mll", "ap_kette_trade1", "ap_konto_rechnen", "ap_klein_trade", "_ap_de",
              "liq_peak", "_liq_peak_eod", "_cme_handelstag", "_ap_peaks", "ap_boden_sicher")   # EOD1 16.11.2026: _ap_peaks nimmt den EOD-Weg
KONSTANTEN = ("AP_REST_MIN", "AP_REST_MIN_CFD", "AP_KLEIN_PKT", "AP_KLEIN_PUFFER", "AP_KLEIN_SCHRITT", "AP_KLEIN_TP_PKT_HINWEIS", "AP_PUFFER_PKT", "AP_CFD_ROUTEN", "AP_GROESSE_TOLERANZ", "AP_KETTE_STANDARD", "AP_KETTE_TXT", "AP_SL_HINTER_BODEN", "AP_SL_MIN_PKT")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": __import__("datetime").datetime, "timezone": __import__("datetime").timezone}   # EOD1: _cme_handelstag
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in KONSTANTEN]
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def regel(**kw):
    # Kernwerte wie in auto_plan_regeln.regeln.firmen[] (kauf_eur, dd, ziel_pct, Größen) — Werte frei erfunden
    r = {"kauf_eur": 100, "ziel_pct": {"phase1": 10, "challenge": 6}, "groessen": [100000, 150000],
         "phasen": {"phase1": {"menge": [1, 1], "tp": [500, 600], "sl": [3000, 3000]},
                    "challenge": {"menge": [1, 1], "tp": [500, 600], "sl": [3000, 3000]}}}
    r.update(kw)
    return r


def main():
    ns = lade()
    bk, rechnen = ns["ap_boden_konto"], ns["ap_konto_rechnen"]
    f = []

    def check(ok, name):
        f.append(0 if ok else 1)
        print(("OK  " if ok else "FEHL") + " " + name)

    st = bk(regel(boden="statisch", dd_pct=10), "phase1", 100500)
    check(st == {"boden": 90000.0, "boden_min": 90000.0, "boden_art": "statisch"}, f"statisch 10 % von 100k → 90.000 ({st})")
    st2 = bk(regel(boden="statisch", dd_usd=4000), "challenge", 151000)
    check(st2["boden"] == 146000.0 and st2["boden_art"] == "statisch", f"statisch 4.000 $ bei 150k → 146.000 ({st2})")

    lk = regel(boden="nachziehend", dd_usd=4000, lock_bei_start=True)
    a, b, c = bk(lk, "challenge", 147000), bk(lk, "challenge", 153500), bk(lk, "challenge", 156000)
    check(a["boden"] == 146000.0 and b["boden"] == 149500.0 and c["boden"] == 150000.0 and a["boden_art"] == "nachziehend_lock",
          f"nachziehend mit Lock: 147k → 146.000, 153,5k → 149.500, 156k → 150.000 fest ({a['boden']}, {b['boden']}, {c['boden']})")

    # nachziehend ohne Lock (Tradeify 150k, DD 4.500): geschätzt aus dem Höchststand, nie unter Start − DD (Master 08.10.2026)
    td = regel(boden="nachziehend", dd_usd=4500)
    fr = bk(td, "challenge", 150000)
    check(fr == {"boden": 145500.0, "boden_min": 145500.0, "boden_art": "nachziehend_geschaetzt"},
          f"ohne Lock, frisch ohne Trade → genau Start − DD = 145.500 ({fr})")
    gw = bk(td, "challenge", 153000, 153000)
    check(gw["boden"] == 148500.0 and gw["boden_art"] == "nachziehend_geschaetzt", f"ohne Lock, nach Gewinn auf 153.000 → 148.500 ({gw})")
    vl = bk(td, "challenge", 149500, 153000)
    check(vl["boden"] == 148500.0, f"ohne Lock, nach Verlust vom Hoch 153.000 auf 149.500 → Boden bleibt 148.500 ({vl})")
    ub = bk(td, "challenge", 147000, None)
    check(ub["boden"] == 145500.0 and ub["boden_min"] == 145500.0, f"ohne Lock, Verlust ohne bekannten Hoch → nie unter Start − DD ({ub})")
    check(bk(td, "challenge", 151000)["boden"] == 146500.0, "ohne Lock, aktuelle Balance über dem Start zählt als Höchststand")

    ohne = regel(boden="statisch", dd_pct=10)
    ohne.pop("kauf_eur")
    leer = {"boden": None, "boden_min": None, "boden_art": None}
    check(bk(ohne, "phase1", 100500) == leer, "ohne Kernwerte (kein Kaufpreis) → null, auch wenn ein DD da ist")
    check(bk(None, None, None) == leer and bk(regel(boden="statisch", dd_pct=10), "phase1", None) == leer,
          "ohne Regel / ohne Balance → null")
    check(bk(regel(boden="statisch", dd_pct=10), "phase1", 40000) == leer, "Balance passt zu keiner Größe → null")

    # gleiche Rechnung wie der Planer: SL wird auf Balance − Boden gekappt (3.000 → 2.000 bei 92.000 über 90.000) — seit 09.10.2026
    # + AP_SL_HINTER_BODEN dahinter (Finn: auch nur kurz unter dem Boden = geblowt; Ende TP oder geblowt, kein Rest-Konto)
    u = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}
    w, grund = rechnen(regel(boden="statisch", dd_pct=10), "phase1", 92000, u)
    check(w is not None and w["sl"] == 92000 - bk(regel(boden="statisch", dd_pct=10), "phase1", 92000)["boden"] + ns["AP_SL_HINTER_BODEN"]
          and ns["AP_SL_HINTER_BODEN"] == 50 and "hinter den Boden" in w["stufe"],
          f"SL-Deckel im Planer = Balance − boden + 50 ({(w or {}).get('sl')}, {(w or {}).get('stufe')}, {grund})")
    # Rest-Konto FN …0296 (90.002 über Boden 90.000): SL 2 + 50 = 52 → Ende sicher unter dem Boden
    wr, _ = rechnen(regel(boden="statisch", dd_pct=10), "phase1", 90002, u)
    check(wr is not None and wr["sl"] == 52, f"Rest-Konto 90.002 → SL 52 (hinter den Boden) ({(wr or {}).get('sl')})")
    # ungekappt bleibt ungekappt (Balance weit über dem Boden)
    wu, _ = rechnen(regel(boden="statisch", dd_pct=10), "phase1", 99000, u)
    check(wu is not None and wu["sl"] == 3000 and "Boden" not in wu["stufe"], f"weit über dem Boden: SL 3.000 unverändert ({(wu or {}).get('sl')})")
    w2, _ = rechnen(lk, "challenge", 148000, u)
    check(w2 is not None and w2["sl"] - ns["AP_SL_HINTER_BODEN"] == 148000 - bk(lk, "challenge", 148000)["boden"] == 2000,
          f"Lock: SL-Deckel im Planer = Balance − boden + 50 ({(w2 or {}).get('sl')})")

    # Nur Anzeige: der Planer kappt den SL bei Tradeify weiter nicht (kein Boden im Planer ohne Lock)
    w3, _ = rechnen(td, "challenge", 149000, u)
    check(w3 is not None and w3["sl"] == 3000 and "gekappt" not in w3["stufe"], f"Planer-SL bei Tradeify unberührt ({(w3 or {}).get('sl')})")
    # SB2 (Master 24.11.2026): The5%ers 200k a1d268f9 — 4 $ über dem Boden, 60 Lot → SL 54 $ läge im Spread (Vorprüfung: ≈ 129 $ am Mindestabstand)
    r60 = regel(boden="statisch", dd_pct=10, phasen={"phase1": {"menge": [60, 60], "tp": [500, 600], "sl": [3000, 3000]}})
    ws, gs = rechnen(r60, "phase1", 90004, u, ppl=1.0)
    check(ws is None and gs.startswith("am Boden → von Hand") and "54 $" in gs and "180 $" in gs,
          f"SB2: 60 Lot, 4 $ über dem Boden → kein Plan, „am Boden → von Hand“ (Mindest-SL 3 Pkt × 60 × 1 $ = 180) ({gs})")
    wf, gf = rechnen(regel(boden="statisch", dd_pct=10), "phase1", 90002, u, ppl=1.0)
    check(wf is not None and wf["sl"] == 52, f"SB2: FN …0296 1 Lot, SL 52 ≥ Mindest-SL 3 $ → weiter geplant wie bisher ({gf})")
    wn, _ = rechnen(r60, "phase1", 90004, u)
    check(wn is not None and wn["sl"] == 54, "SB2: ohne Punktwert (ppl) keine Prüfung — wie bisher (Futures/unbekannt)")
    wg, _ = rechnen(r60, "phase1", 92000, u, ppl=1.0)
    check(wg is not None and wg["sl"] == 2050, f"SB2: 2.000 $ über dem Boden, SL 2.050 ≥ 180 → normal geplant ({(wg or {}).get('sl')})")
    # ap_boden_sicher (Prüfer 08.10.2026): kaputte Regel → Felder null, kein Abbruch; ohne Konto → null; gute Regel → wie ap_boden_konto
    leer3 = {"boden": None, "boden_min": None, "boden_art": None}
    check(ns["ap_boden_sicher"](None, {"id": "k-x", "account_type": "phase1"}, 100500, regel=regel(boden="statisch", dd_pct="kaputt")) == leer3,
          "ap_boden_sicher: kaputte Regel → null")
    check(ns["ap_boden_sicher"](None, None, 100500) == leer3, "ap_boden_sicher: ohne Konto → null")
    check(ns["ap_boden_sicher"](None, {"id": "k-1", "account_type": "challenge"}, 149500, {"k-1": 153000}, regel=td)["boden"] == 148500.0,
          "ap_boden_sicher: Höchststand aus peaks je Konto-id")
    # _ap_peaks: Ladefehler → {} (Boden schätzt dann ab Start/Balance)
    ns["_liq_verlauf_laden"] = lambda ids, **kw: (_ for _ in ()).throw(ConnectionError("weg"))
    check(ns["_ap_peaks"]([{"id": "k-1"}]) == {}, "_ap_peaks: Ladefehler → leer, kein Abbruch")
    ns["_liq_verlauf_laden"] = lambda ids, **kw: [{"id": "p1", "master_account_id": "k-1", "konto_typ": "challenge", "ended_at": "2026-10-07T20:00:00+00:00",
                                             "bal_end": 153000}, {"id": "p2", "master_account_id": "k-1", "konto_typ": "phase1",
                                             "ended_at": "2026-10-01T20:00:00+00:00", "bal_end": 160000}]
    pk = ns["_ap_peaks"]([{"id": "k-1", "account_type": "challenge"}])
    check(pk == {"k-1": 153000}, f"_ap_peaks: Höchststand nur aus derselben Phase (153.000, nicht 160.000 aus phase1) ({pk})")
    print(f"{len(f) - sum(f)}/{len(f)} ok")
    sys.exit(1 if sum(f) else 0)


if __name__ == "__main__":
    main()
