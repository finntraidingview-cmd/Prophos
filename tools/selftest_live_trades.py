#!/usr/bin/env python3
"""Selbsttest Live Trades — Liquidations-Level (app.py, LIVE TRADES, 26.09.2026) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_live_trades.py
Laedt die Funktionen per Quelltext aus app.py (wie selftest_reader_wacht: app.py zieht beim Import Flask und Threads).
Prueft Finns Regel „Der Max-Drawdown ist quasi der SL": Nicht-WD-Konten bekommen das Level aus max_drawdown auch ohne
Start-Balance (BUY/SELL, NQ/MNQ, mehrere Kontrakte), ohne max_drawdown keins; Winning Days unveraendert."""
import os
import re
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone}

    def block(name):
        i = src.index(f"def {name}(")
        return src[i:src.find("\n\n\n", i)]

    def const(name):
        return re.search(rf"^{name} = .*$", src, re.M).group(0)
    exec("\n".join([const("LT_WD_BLOW_PLUS"), const("WD_HEUTE_PPL")]
                   + [block(f) for f in ("_wd_num", "_wd_level", "_wd_konto_groesse", "ist_topstep_express", "plan_balance_relativ", "konto_basis_balance",
                                           "plan_ist_wd", "_lt_liq_balance", "_lt_liq", "_lt_demo", "kurs_jetzt_wahl", "tsx_zeile_ueberlagern",
                                           "tv_bracket_ueberlagern")]), ns)
    return ns


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    liq, ppl = a["_lt_liq"], a["WD_HEUTE_PPL"]
    # Orbit V3 (01.10.2026): tvv2 + Fusion-Hedge, aber KEIN Winning Day → Radar zeigt den Master-SL statt der Liquidation
    w_ = a["plan_ist_wd"]
    check(w_({"hedge_eur": 5}) and not w_({"hedge_eur": 5, "orbit_v3": True}) and w_({}, "winning_days")
          and not w_({"orbit_v3": True, "konto_typ": "winning_days"}, "winning_days") and not w_({}),
          "plan_ist_wd: Hedge/WD-Konto = WD, Orbit V3 nie, normaler Plan nie")
    tradeify = {"account_type": "funded", "max_drawdown": 4500, "starting_balance": 150000, "name": "Tradeify 150k"}
    plan = {"konto_typ": "funded"}
    # BUY NQ 1 Kontrakt, ohne Start-Balance: 4.500 $ / (20 $ × 1) = 225 Punkte unter dem Einstieg
    r = liq(tradeify, plan, None, 30000.0, "buy", ppl["NQ"], 1)
    check(r["level"] == 29775.0 and r["balance"] is None and r["pl_usd"] == -4500 and r["regel"] == "Max-Drawdown 4.500 $ als SL",
          "BUY NQ ×1 ohne Start-Balance → Level 29.775, keine Liq-Balance, P&L −4.500 $")
    r = liq(tradeify, plan, None, 30000.0, "sell", ppl["NQ"], 3)
    check(r["level"] == 30075.0, "SELL NQ ×3 → 75 Punkte über dem Einstieg (30.075)")
    r = liq(tradeify, plan, None, 30000.0, "buy", ppl["MNQ"], 6)
    check(r["level"] == 29625.0, "BUY MNQ ×6 → 375 Punkte unter dem Einstieg (29.625)")
    r = liq(dict(tradeify, max_drawdown=4000), plan, 151200.0, 30000.0, "sell", ppl["MNQ"], 10)
    check(r["level"] == 30200.0 and r["balance"] == 147200.0 and r["pl_usd"] == -4000,
          "SELL MNQ ×10 mit Start-Balance → Level 30.200 + Liq-Balance 147.200 zusätzlich")
    r = liq(dict(tradeify, max_drawdown=None), plan, 151200.0, 30000.0, "buy", ppl["NQ"], 1)
    check(r["level"] is None and r["balance"] is None and r["regel"] == "kein Max-Drawdown am Konto",
          "ohne max_drawdown → kein Level, nichts geraten")
    check(liq(tradeify, plan, None, None, "buy", ppl["NQ"], 1)["level"] is None
          and liq(tradeify, plan, None, 30000.0, "buy", ppl["NQ"], 0)["level"] is None,
          "ohne Einstieg oder ohne Kontrakte → kein Level")
    # Winning Day unveraendert: Kontogroesse + 100 $, braucht die Start-Balance
    wd = {"account_type": "winning_days", "starting_balance": 150000, "max_drawdown": 4500}
    r = liq(wd, {"konto_typ": "winning_days"}, None, 30000.0, "buy", ppl["NQ"], 2)
    check(r["level"] is None and r["balance"] == 150100.0, "Winning Day ohne Start-Balance → kein Level (wie bisher)")
    r = liq(wd, {"konto_typ": "winning_days"}, 152100.0, 30000.0, "buy", ppl["NQ"], 2)
    check(r["level"] == 29950.0 and r["pl_usd"] == -2000.0, "Winning Day mit Start-Balance → Level aus Kontogröße + 100 $")
    # B25: Topstep Express (XFA) startet bei 0 $ — nie „Größe + 100", sondern Max-Drawdown
    xfa = {"account_type": "winning_days", "firm": "Topstep", "external_id": "EXPRESS-V2-682437-57131691",
           "name": "$150K EXPRESS", "starting_balance": 150000, "max_drawdown": 4500}
    r = liq(xfa, {"konto_typ": "winning_days"}, 11079.66, 30000.0, "buy", ppl["NQ"], 1)
    check(r["level"] == 29775.0 and r["balance"] == 6579.66 and r["pl_usd"] == -4500 and "Max-Drawdown" in r["regel"],
          "Topstep Express als WD: Max-Drawdown statt Größe + 100 (Balance 11.079,66 − 4.500)")
    kombi = {"account_type": "challenge", "firm": "Topstep", "external_id": "150KTC-SKU-V2-000000-00000000", "name": "$150K TRADING COMBINE"}
    check(a["ist_topstep_express"](xfa) and not a["ist_topstep_express"](kombi)
          and not a["ist_topstep_express"](dict(xfa, firm="Apex")), "Express-Erkennung: Topstep + EXPRESS/XFA, Combine nicht, andere Firma nicht")
    # Gemeinsame Regel FE/BE (Master-Entscheid 01.10.2026): Topstep UND (Typ funded/winning_days ODER EXPRESS/XFA); Lesung gewinnt
    ohne_kenn = {"firm": "Topstep", "account_type": "funded", "external_id": "KONTO-TEST-1", "name": "150k topstep"}
    check(a["ist_topstep_express"](ohne_kenn) and a["ist_topstep_express"](dict(ohne_kenn, account_type="winning_days"))
          and not a["ist_topstep_express"](dict(ohne_kenn, account_type="challenge")),
          "Express-Regel: Topstep funded/winning_days ohne Kennung = Express, challenge nicht")
    check(not a["ist_topstep_express"](ohne_kenn, False) and a["ist_topstep_express"](dict(ohne_kenn, account_type="challenge"), True)
          and not a["ist_topstep_express"](dict(ohne_kenn, firm="Apex"), True),
          "balance_relativ der Lesung gewinnt (False → kein Express, True → Express), nie bei anderer Firma")
    pr = a["plan_balance_relativ"]
    check(pr({"mt5_baseline": {"tv": {"balance_relativ": True}}}) is True and pr({"mt5_baseline": {"final": {"balance_relativ": False}}}) is False
          and pr({"mt5_baseline": {"tv": {}}}) is None and pr({}) is None and pr(None) is None, "plan_balance_relativ: tv, sonst final, sonst None")
    r = liq(dict(ohne_kenn, account_type="winning_days", max_drawdown=2000), {"konto_typ": "winning_days", "mt5_baseline": {"tv": {"balance_relativ": True}}},
            0.0, 30000.0, "buy", ppl["NQ"], 1)
    check(r["level"] == 29900.0 and r["balance"] == -2000.0 and "Max-Drawdown" in r["regel"],
          "Topstep WD ohne Kennung, Lesung relativ, Start 0 → Max-Drawdown (Level 100 Pkt), nicht Größe + 100")
    check(a["konto_basis_balance"](xfa) == 0.0 and a["konto_basis_balance"]({"starting_balance": 150000}) == 150000.0,
          "Basis-Balance: Express 0 $, sonst Kontogröße")

    # Demo gegen Kerzen: das neue Level liquidiert
    k = [{"minute": "2026-09-26T10:00:00+00:00", "h": 30010, "l": 29990}, {"minute": "2026-09-26T10:01:00+00:00", "h": 30000, "l": 29770}]
    d = a["_lt_demo"]("buy", 30300.0, 29775.0, k, "2026-09-26T10:00:20+00:00")
    check(d["status"] == "liquidiert" and d["preis"] == 29775.0, "Demo: Kerze unter dem Max-Drawdown-Level → liquidiert")

    # B5: beendete Trades — Kerzen nach dem Ende zaehlen nicht
    dm = a["_lt_demo"]
    k2 = [{"minute": f"2026-09-25T{h:02d}:{m:02d}:00+00:00", "h": 30010, "l": 29990} for h, m in ((1, 0), (1, 10), (1, 17))] \
        + [{"minute": "2026-09-25T09:00:00+00:00", "h": 30400, "l": 29500}]
    d = dm("sell", 29700.0, 30350.0, k2, "2026-09-25T00:59:30+00:00", "2026-09-25T01:17:40+00:00")
    check(d["status"] == "beendet_ohne_treffer" and d["minuten"] == 3 and d["at"].startswith("2026-09-25T01:17"),
          "beendet ohne Treffer: nur Kerzen bis zur Ende-Minute, Kerze danach (TP + Liq) zaehlt nicht")
    d = dm("sell", 29700.0, 30350.0, k2, "2026-09-25T00:59:30+00:00")
    check(d["status"] == "beide_in_minute", "ohne Ende wie bisher (laufender Trade sieht spaetere Kerzen)")
    d = dm("sell", 29995.0, 30350.0, k2, "2026-09-25T00:59:30+00:00", "2026-09-25T01:17:40+00:00")
    check(d["status"] == "tp", "Treffer vor dem Ende bleibt Treffer")
    check(dm("sell", 29700.0, None, k2, "2026-09-25T02:00:00+00:00", "2026-09-25T03:00:00+00:00")["status"] == "ohne_kurs",
          "Ende ohne Kerze im Fenster → ohne_kurs")
    check(dm("sell", 29700.0, None, k2, "2026-09-25T00:59:30+00:00", "kaputt")["status"] == "tp",
          "kaputtes Ende wirft nicht, rechnet wie ohne Ende")

    # 29.09.2026: Einstiegsminute zählt nicht (Finns Plan b2f630e6: Hoch der Kauf-Minute lag VOR dem Kauf) + echter SL beendet die Demo
    kf = [{"minute": "2026-09-29T16:41:00+00:00", "h": 30558.75, "l": 30534.75}, {"minute": "2026-09-29T16:42:00+00:00", "h": 30548, "l": 30528.5},
          {"minute": "2026-09-29T16:43:00+00:00", "h": 30544, "l": 30525.25}, {"minute": "2026-09-29T16:44:00+00:00", "h": 30529.25, "l": 30517.5}]
    d = dm("buy", 30555.25, 28299.25, kf, "2026-09-29T16:41:37.551+00:00", None, 30527.75)
    check(d["status"] == "liquidiert" and d.get("stop") == "sl" and d["preis"] == 30527.75 and d["at"].startswith("2026-09-29T16:43"),
          "Finns Fall: kein TP aus der Kauf-Minute, SL um 16:43")
    d = dm("buy", 30555.25, 28299.25, kf, "2026-09-29T16:41:37.551+00:00")
    check(d["status"] == "laeuft", "ohne SL: Liquidation weit weg, TP nie nach dem Kauf → läuft")
    d = dm("buy", 30555.25, None, kf[:1], "2026-09-29T16:41:37+00:00")
    check(d["status"] == "laeuft" and d["minuten"] == 0, "nur die Kauf-Minute da → läuft (0 Minuten), nicht ohne_kurs")
    d = dm("buy", 30545.0, None, kf, "2026-09-29T16:41:37+00:00", None, 30527.75)
    check(d["status"] == "tp" and d["at"].startswith("2026-09-29T16:42"), "TP nach dem Kauf wird weiter erkannt (16:42)")

    # B35/F28: aktueller Kurs je Wurzel — jüngste Minute, fehlende Wurzel übernimmt die andere
    kw = a["kurs_jetzt_wahl"]
    kj = kw([{"wurzel": "NQ", "minute": "2026-09-27T16:00:00+00:00", "c": 30900.0},
             {"wurzel": "NQ", "minute": "2026-09-27T16:05:00+00:00", "c": 30921.75}])
    check(kj["NQ"]["kurs"] == 30921.75 and kj["MNQ"]["kurs"] == 30921.75 and kj["MNQ"]["quelle"] == "NQ",
          "kurs_jetzt: jüngste Minute, MNQ übernimmt NQ")
    check(kw([]) == {} and kw([{"wurzel": "ES", "minute": "x", "c": 1}]) == {}, "kurs_jetzt: leer/fremde Wurzel → {}")
    # F28: Topstep V2 — echte Brackets/MLL aus TopstepX
    ue = a["tsx_zeile_ueberlagern"]
    tv = {"tp_level_nq": 30927.75, "balance_start": 150000.0, "mll_start": 148000.0, "einstieg_quelle": "reader_klick"}
    u = ue("tsv2", tv, 30921.75, "buy", 2.0, 2)
    check(u["tp_level_nq"] == 30927.75 and u["level_quelle"] == "tsx" and u["liq_balance"] == 148000.0
          and u["liq_level_nq"] == 30421.75 and u["sl_level_nq"] == 30421.75 and u["sl_art"] == "liquidation"
          and u["einstieg_quelle"] == "reader_klick" and u["liq_pl_usd"] == -2000.0, "tsv2: TP aus Orders, Liquidation = MLL beim Start")
    u2 = ue("tsv2", dict(tv, sl_level_nq=30800.0), 30921.75, "buy", 2.0, 2)
    check(u2["sl_level_nq"] == 30800.0 and u2["sl_art"] == "bracket", "tsv2: echte SL-Bracket geht vor Liquidation")
    check(ue("tvv2", tv, 30921.75, "buy", 2.0, 2) == {} and ue("tsv2", {}, 1, "buy", 2.0, 2) == {}, "nur tsv2 mit Werten")
    # 29.09.2026: Orbit V2 ohne Hedge — exakte Brackets aus TradingViews Meldungen (Live-Test Plan 8fdf12d0, SELL @ 30682.25)
    tb = a["tv_bracket_ueberlagern"]
    tvo = {"einstieg_nq": 30682.25, "tp_level_nq": 30516.5, "sl_level_nq": 30698.5, "tp_level_quelle": "tv_toast"}
    b1 = tb("tvv2", tvo, None)
    check(b1 == {"tp_level_nq": 30516.5, "level_quelle": "tv_toast", "sl_level_nq": 30698.5, "sl_art": "bracket"}, "tvv2 ohne Hedge: TP/SL aus den Meldungen")
    check(tb("tvv2", tvo, {"tp_level_nq": 30516.25, "status": "offen"}) == {}, "tvv2 mit Hedge: hedge.* bleibt maßgeblich")
    check(tb("tvv2", {"einstieg_nq": 30682.25}, None) == {} and tb("tsv2", tvo, None) == {} and tb("tvv2", None, None) == {},
          "tvv2 ohne Brackets / andere Wege → nichts")
    check(tb("tvv2", {"tp_level_nq": 30516.5}, {}) == {"tp_level_nq": 30516.5, "level_quelle": "tv_toast"}, "leerer Hedge = kein Hedge, nur TP")

    print("\nALLES GRUEN" if ok else "\nFEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
