#!/usr/bin/env python3
"""Selbsttest TAGE SAMMELN (app.py ap_tage_mini / ap_tage_ist / ap_konto_rechnen tage=, 09.10.2026, Korb „Bestanden" Teil 2 — Finn über
Master): Ziel erreicht, Mindesttage fehlen → EIN Mini-Trade je Handelstag statt Sperre, Balance bleibt über Ziel + Puffer.

Aufruf:  python3 tools/selftest_tage_sammeln.py
Ohne Netz. Geprüft: CFD 0,01 Lot TP 1–2 / SL ≤ 2 $; Futures 1 MNQ TP/SL 5–10 $; SL gedeckelt auf Balance − Ziel − Puffer; zu wenig Luft →
Grund statt Plan; Tage voll → wieder „Ziel erreicht"; ohne Mindesttage unverändert; Zählung wie zielFortschritt (Berlin-Tage mit Start ab
goal_since + goal_done_offset)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


CFD = {"namen": ["ftmo"], "route": "mt5v2", "groessen": [100000], "ziel_pct": {"phase1": 10, "phase2": 5},
       "phasen": {"phase1": {"sl": [2400, 2600], "tp": [3000, 4000], "menge": [2, 3], "menge_schritt": 0.01},
                  "phase2": {"sl": [2400, 2600], "tp": [2000, 3000], "menge": [2, 3], "menge_schritt": 0.01}}}
FUT = {"namen": ["tradeify"], "route": "tvv2", "symbol": "NQ", "groessen": [150000], "ziel_pct": {"challenge": 6},
       "phasen": {"challenge": {"sl": None, "tp": [4000, 4400], "menge": [2, 3], "menge_schritt": 1}}}
U = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}


def main():
    a = sd.lade()
    R = a["ap_konto_rechnen"]
    # CFD Phase 1 100k (menge_schritt 0,01), Ziel 110.000, Balance 110.420, Tage 2/4, Punktwert 1 $/Pkt/Lot
    w, g = R(CFD, "phase1", 110420.0, U, ppl=1.0, tage=(2, 4))
    tm = (w or {}).get("tage_mini") or {}
    check(w and w["menge"] == 0.01 and tm.get("sl_pkt") == 30 and tm.get("tp_pkt") == 30 and w["sl"] == 0.3 and w["tp"] == 0.3
          and w["risiko"] == w["sl"] and "symbol" not in w and tm.get("ziel") == 110000 and tm.get("puffer") == 5.0
          and w["stufe"] == "Tage sammeln 2/4 · Mini-Trade 0,01 Lot · TP 30 Pkt (0,3 $) / SL 30 Pkt (0,3 $) (Balance bleibt über Ziel + 5 $)",
          f"CFD 0,01 Lot: TP/SL 30 Pkt = 0,30 $ ({g or w})")
    wr, _ = R(CFD, "phase1", 110420.0, {"tp": 0.0, "sl": 0.999, "menge": 0.5, "puffer": 0.5}, ppl=1.0, tage=(2, 4))
    check(wr["tage_mini"]["tp_pkt"] == 20 and wr["tage_mini"]["sl_pkt"] == 40, f"CFD Spanne 20–40 Pkt ({wr['tage_mini']})")
    # kleinste Stufe der Firma: menge_schritt 1 (FTMO/The5ers) → 1 Lot, 30 Pkt = 30 $
    CFD1 = dict(CFD, phasen={"phase1": dict(CFD["phasen"]["phase1"], menge_schritt=1)})
    w1, g1 = R(CFD1, "phase1", 110420.0, U, ppl=1.0, tage=(2, 4))
    check(w1 and w1["menge"] == 1 and isinstance(w1["menge"], int) and w1["sl"] == 30 and w1["tp"] == 30 and "Mini-Trade 1 Lot ·" in w1["stufe"],
          f"menge_schritt 1 → 1 Lot, TP/SL 30 Pkt = 30 $ ({g1 or (w1['menge'], w1['tp'], w1['sl'])})")
    wk1, gk1 = R(CFD1, "phase1", 110030.0, {"tp": 0.5, "sl": 0.999, "menge": 0.5, "puffer": 0.5}, ppl=1.0, tage=(2, 4))
    check(wk1 and wk1["tage_mini"]["sl_pkt"] == 25 and wk1["sl"] == 25, f"1 Lot, Luft 25 $: SL 40 Pkt auf 25 Pkt gekürzt ({gk1 or (wk1 and wk1['tage_mini'])})")
    wn1, gn1 = R(CFD1, "phase1", 110020.0, U, ppl=1.0, tage=(2, 4))
    check(wn1 is None and "kleinste Mini-SL (20 Pkt = 20 $ bei 1 Lot)" in (gn1 or "") and ", von Hand" in (gn1 or ""),
          f"1 Lot, Luft 15 $ < 20 Pkt → kein Mini, genauer Grund ({gn1})")
    w01, _ = R(dict(CFD, phasen={"phase1": dict(CFD["phasen"]["phase1"], menge_schritt=0.1)}), "phase1", 110420.0, U, ppl=1.0, tage=(2, 4))
    check(w01 and w01["menge"] == 0.1 and w01["sl"] == 3.0, f"menge_schritt 0,1 → 0,1 Lot, 30 Pkt = 3 $ ({w01 and (w01['menge'], w01['sl'])})")
    wp, gp = R(CFD, "phase1", 110420.0, U, ppl=None, tage=(2, 4))
    check(wp is None and "kein Punktwert" in (gp or ""), f"ohne Punktwert kein Mini ({gp})")
    # Tage voll / ohne Mindesttage → wie bisher; unter dem Ziel normal
    w5, g5 = R(CFD, "phase1", 110420.0, U, ppl=1.0, tage=(4, 4))
    w6, g6 = R(CFD, "phase1", 110420.0, U, ppl=1.0)
    check(w5 is None and g5 == "Ziel erreicht — Phase umstellen" and w6 is None and g6 == g5, f"Tage voll bzw. ohne Mindesttage → „Ziel erreicht“ ({g5} / {g6})")
    w7, _ = R(CFD, "phase1", 104000.0, U, ppl=1.0, tage=(1, 4))
    check(w7 and "tage_mini" not in w7 and w7["tp"] > 100, f"unter dem Ziel: normaler Plan, kein Mini ({w7 and w7['stufe']})")
    # Futures (tvv2) Challenge 150k, Ziel 159.000, Balance 159.120, Tage 1/3 → 1 MNQ, 3–5 Pkt × 2 $
    wf, gf = R(FUT, "challenge", 159120.0, U, tage=(1, 3))
    check(wf and wf["menge"] == 1 and wf.get("symbol") == "MNQ" and wf["tage_mini"]["sl_pkt"] == 4.0 and wf["sl"] == 8.0 and wf["tp"] == 8.0
          and wf["tage_mini"]["puffer"] == 20.0 and "1 MNQ · TP 4 Pkt (8 $) / SL 4 Pkt (8 $)" in wf["stufe"], f"Futures 1 MNQ, TP/SL 4 Pkt = 8 $ ({gf or wf})")
    wk, gk = R(FUT, "challenge", 159026.0, {"tp": 0.5, "sl": 0.999, "menge": 0.5, "puffer": 0.5}, tage=(1, 3))
    check(wk and wk["tage_mini"]["sl_pkt"] == 3.0 and wk["sl"] == 6.0, f"Futures Luft 6 $: SL 5 Pkt auf 3 Pkt (6 $) gekürzt ({gk or (wk and wk['tage_mini'])})")
    wq, gq = R(FUT, "challenge", 159025.0, U, tage=(1, 3))
    check(wq is None and "kleinste Mini-SL (3 Pkt = 6 $ bei 1 MNQ)" in (gq or ""), f"Futures Luft 5 $ < 3 Pkt × 2 → kein Mini ({gq})")
    ganz = [R(FUT, "challenge", 159120.0, {"tp": x, "sl": y, "menge": 0.5, "puffer": 0.5}, tage=(1, 3))[0] for x in (0.0, 0.13, 0.37, 0.61, 0.99) for y in (0.07, 0.5, 0.93)]
    check(all(float(v["tp"]).is_integer() and float(v["sl"]).is_integer() and (v["tage_mini"]["tp_pkt"] * 2) % 1 == 0 for v in ganz),
          f"Futures MNQ: TP/SL immer ganze Dollar (Raster 0,5 Pkt) ({sorted({(v['tp'], v['sl']) for v in ganz})})")
    wu, gu = R(FUT, "challenge", 158940.0, U, tage=(1, 3))
    check(wu is None and "Tage sammeln 1/3" in (gu or ""), f"Futures Challenge 60 $ unter dem Ziel → kein Mini ({gu})")
    wt, gt = R(dict(FUT, route="tsv2"), "challenge", 159120.0, U, tage=(1, 3))
    check(wt is None and "Topstep — Mini-Trade von Hand" in (gt or ""), f"Topstep (tsv2) → kein Mini, Grund ({gt})")
    # Zählung
    T = a["ap_tage_ist"]
    konto = {"id": "k1", "goal_kind": "trading_days", "goal_target": 4, "goal_since": "2026-10-01", "goal_done_offset": 1}
    pl = [{"master_account_id": "k1", "started_at": "2026-10-06T09:00:00+00:00"}, {"master_account_id": "k1", "started_at": "2026-10-06T15:00:00+00:00"},
          {"master_account_id": "k1", "started_at": "2026-10-07T21:30:00+00:00"},   # 23:30 Berlin am 07.
          {"master_account_id": "k1", "started_at": "2026-10-07T22:30:00+00:00"},   # 00:30 Berlin am 08. → eigener Tag
          {"master_account_id": "k1", "started_at": "2026-09-30T09:00:00+00:00"},   # vor goal_since
          {"master_account_id": "k1", "started_at": None}, {"master_account_id": "k2", "started_at": "2026-10-08T09:00:00+00:00"}]
    check(T(konto, pl) == (4, 4), f"Zählung: 06./07./08. (Berlin) + Offset 1 = 4 von 4 ({T(konto, pl)})")
    check(T(dict(konto, goal_kind="winning_days"), pl) is None and T(dict(konto, goal_target=None), pl) is None, "ohne trading_days/Ziel → None")
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
