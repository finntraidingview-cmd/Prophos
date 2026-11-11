#!/usr/bin/env python3
"""Selbsttest HEDGE-DLL (prophos.html hedgeLiqLevel + liqRegelWaehlen/liqDailyLoss/hedgeTagesstart/hedgeLiqDll, app.py wd_sl_zeile, 21.10.2026 —
Finn über den Master: „Ab jetzt sollte die Fusion dann schließen, wenn eben der Loss am Master reicht … Mach einfach 5 Punkte davor").
Anlass: erstes Apex-WD-Konto Marc …0001 (150k, Balance 165.735 $, Stufe 5 → Daily Loss 4.000 $); vorher schloss der Fusion-Hedge erst bei
Kontogröße + 100 = 150.100 (~15,6k tiefer), Apex hatte den Master da längst flach.

Aufruf:  python3 tools/selftest_hedge_dll.py
Ohne Netz und ohne Node: Frontend per macOS-JavaScriptCore (jsc) aus prophos.html geschnitten, liq_regeln = Live-Stand 21.10.2026 (id 4/6/7/13).
Geprüft: Marc 3 MNQ buy/sell → Level = Einstieg ∓ (4.000 / 6 − 5) Pkt, liq_art daily_loss, Stufe 5; 100k 2 NQ bei 104.300 → Stufe 3 (1.750);
früherer Trade am selben CME-Tag → Tagesstart = dessen Start-Balance (Stufe danach); Konto-Boden enger (100k bei 101.000: 99.250 vs 100.100) →
Boden ohne 5 Pkt; Tradeify-WD (art boden) und Apex ohne geladene Regeln → unverändert Kontogröße + 100; Daily Loss < 5 Pkt → Level\nam DLL-Punkt ohne Abzug (nie gar keins, Prüf-Agent)."""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HIER, "..", "prophos.html")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []

REGELN = [
    {"id": 4, "firma": "Apex Trader", "kontotyp": "funded", "groesse": "150000", "art": "stufen", "betrag_usd": None, "wie_kontotyp": None,
     "stufen": [{"ab_balance": 150000, "daily_loss_usd": 2500}, {"ab_balance": 152000, "daily_loss_usd": 2500},
                {"ab_balance": 153000, "daily_loss_usd": 2500}, {"ab_balance": 155000, "daily_loss_usd": 3000},
                {"ab_balance": 160000, "daily_loss_usd": 4000}]},
    {"id": 13, "firma": "Apex Trader", "kontotyp": "funded", "groesse": "100000", "art": "stufen", "betrag_usd": None, "wie_kontotyp": None,
     "stufen": [{"ab_balance": 100000, "daily_loss_usd": 1750}, {"ab_balance": 102000, "daily_loss_usd": 1750},
                {"ab_balance": 103000, "daily_loss_usd": 1750}, {"ab_balance": 105000, "daily_loss_usd": 2500},
                {"ab_balance": 110000, "daily_loss_usd": 3500}]},
    {"id": 3, "firma": "Apex Trader", "kontotyp": "challenge", "groesse": None, "art": "tagesstart", "betrag_usd": "2000", "stufen": None, "wie_kontotyp": None},
    {"id": 6, "firma": None, "kontotyp": "winning_days", "groesse": None, "art": None, "betrag_usd": None, "stufen": None, "wie_kontotyp": "funded"},
    {"id": 7, "firma": "Tradeify", "kontotyp": "winning_days", "groesse": None, "art": "boden", "betrag_usd": None, "stufen": None, "wie_kontotyp": None},
    # DL2 (Live-Stand 11.11.2026): Tradeify funded fest (kein Tageslimit), Lucid funded 150k Tagesstart 2.700, Lucid WD Boden
    {"id": 2, "firma": "Tradeify", "kontotyp": "funded", "groesse": None, "art": "fest", "betrag_usd": "4500", "stufen": None, "wie_kontotyp": None},
    {"id": 17, "firma": "Lucid Trading", "kontotyp": "funded", "groesse": "150000", "art": "tagesstart", "betrag_usd": "2700", "stufen": None, "wie_kontotyp": None},
    {"id": 14, "firma": "Lucid Trading", "kontotyp": "winning_days", "groesse": None, "art": "boden", "betrag_usd": None, "stufen": None, "wie_kontotyp": None},
]


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def js_funktion(src, name):
    """Funktionsquelltext per Klammerzählung (Strings/Template-Literale in diesen Funktionen sind klammer-ausgeglichen)."""
    i = src.index(f"function {name}(")
    j = src.index("{", src.index(")", i))
    tiefe = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            tiefe += 1
        elif src[k] == "}":
            tiefe -= 1
            if tiefe == 0:
                return src[i:k + 1]
    raise ValueError(name)


def js_zeile(src, anfang):
    i = src.index(anfang)
    return src[i:src.index("\n", i)]


def main():
    src = open(HTML, encoding="utf-8").read()
    teile = [js_zeile(src, "const HEDGE_DLL_VOR_PKT"), js_zeile(src, "const HEDGE_DLL_VOR_USD"), js_zeile(src, "const hedgeLiqDllFelder"),
             # Hedge Teil 2 (30.10.2026): hedgeIstWd/hedgeLiqLevel fragen nach finalem Tradeify (S4) und Apex mit Hedge (S1)
             js_zeile(src, "const hedgeIstTradeifyFinal"), js_zeile(src, "const tpIstApexHedge")]
    # istTradeifyCfd: firmNormRichtung fragt seit .1726 danach (Tradeify CFD eigene Firma)
    teile += [js_funktion(src, n) for n in ("istTradeifyCfd", "firmNormRichtung", "tvV2Handelstag", "liqRegelWaehlen", "liqDailyLoss", "hedgeTagesstart",
                                            "hedgeLiqDll", "hedgeLiqDllApex", "hedgeLiqStart", "hedgeLiqLevel",
                                            "planWdSlUsd", "hedgeDllVorPkt", "hedgeDllVorEff", "liqDllSchutz", "hedgeFeedEntscheidDetail")]   # DL2 (11.11.2026): Puffer ≥ 100 $ vor dem Daily Loss   # WS1 (09.11.2026): hedgeLiqLevel fragt nach dem Würfel-SL des Plans
    acc = [
        {"id": "marc", "name": "150k PAAPEX6843320000001 → Funded", "firm": "Apex Trader", "type": "winning_days", "startingBalance": None},
        {"id": "a100", "name": "100k PAAPEX0000000000099 → Funded", "firm": "Apex Trader", "type": "winning_days", "startingBalance": 100000},
        {"id": "tdfy", "name": "150k TDFYSL150 → WD", "firm": "Tradeify", "type": "winning_days", "startingBalance": 150000},
        # DL2 (11.11.2026): Konto-Feld dll_usd 1.750 an den Kursen von …0887 (synthetisch — laut Finn 21:30 hat Tradeify selbst KEIN DLL), dll_usd 0 = keins,
        # Lucid-WD (Tageslimit aus der Funded-Zeile id 17; live seit 21:30 zusätzlich id 18 winning_days 150k)
        {"id": "d0887", "name": "150k FTDFYSLX150600000000887 → Winning Days", "firm": "Tradeify", "type": "winning_days", "startingBalance": 150000, "dllUsd": 1750},
        {"id": "flex", "name": "150k FTDFYSLX150600000000001 → Winning Days", "firm": "Tradeify", "type": "winning_days", "startingBalance": 150000, "dllUsd": 0},
        {"id": "lucid", "name": "150k LUCID0000000001 → Winning Days", "firm": "Lucid Trading", "type": "winning_days", "startingBalance": 150000},
    ]
    regeln_schutz = [dict(r, dll_schutz=True) if r["id"] in (4, 13) else r for r in REGELN]
    stub = f"""
const REGELN_SCHUTZ = {json.dumps(regeln_schutz)}
let _liqRegeln = null, tradePlans = []
const accounts = {json.dumps(acc)}
const REGELN = {json.dumps(REGELN)}
function liqRegelnLaden(){{ return Promise.resolve(null) }}
function tvKontoBalanceVorStart(){{ return null }}
function tpKontoGroesseAusName(n){{ const m = /^(\\d+)k/i.exec(String(n || '')); return m ? Number(m[1]) * 1000 : 0 }}
"""
    def plan(pid, acc_id, richtung, bal, started="2026-10-22T01:20:00Z"):
        return {"id": pid, "masterAccountId": acc_id, "richtung": richtung, "startedAt": started, "kontoTyp": "winning_days",
                "mt5Baseline": {"tv": {"balance_start": bal}}}
    faelle = {
        "marc_buy": ("REGELN", plan("p1", "marc", "buy", 165735.2), 30000, 2, 3, []),
        "marc_sell": ("REGELN", plan("p2", "marc", "sell", 165735.2), 30000, 2, 3, []),
        "a100": ("REGELN", plan("p3", "a100", "buy", 104300), 30000, 20, 2, []),
        "a100_frueher": ("REGELN", plan("p4", "a100", "buy", 104300, "2026-10-22T03:00:00Z"), 30000, 20, 2,
                         [plan("p0", "a100", "buy", 105200, "2026-10-22T01:00:00Z")]),
        "a100_boden": ("REGELN", plan("p5", "a100", "buy", 101000), 30000, 20, 2, []),
        "tdfy": ("REGELN", plan("p6", "tdfy", "buy", 152000), 30000, 2, 3, []),
        "ohne_regeln": ("null", plan("p7", "marc", "buy", 165735.2), 30000, 2, 3, []),
        "zu_nah": ("REGELN", plan("p8", "a100", "buy", 103800), 30000, 20, 20, []),
        # DL2-Schalter: Apex-Zeile mit dll_schutz true → DL2-Puffer
        "marc_schutz": ("REGELN_SCHUTZ", plan("p1s", "marc", "buy", 165735.2), 30000, 2, 3, []),
        # DL2: 0887 SELL 3 MNQ @ 28.092,50, Start-Balance 160.329 (−2.980 $ bei 28.589 → ~157.350)
        "d0887": ("REGELN", plan("p9", "d0887", "sell", 160329), 28092.5, 2, 3, []),
        "d0887_ohne_regeln": ("null", plan("p10", "d0887", "sell", 160329), 28092.5, 2, 3, []),
        "flex": ("REGELN", plan("p11", "flex", "sell", 160329), 28092.5, 2, 3, []),
        "lucid": ("REGELN", plan("p12", "lucid", "buy", 157000), 28000, 2, 3, []),
        # Kante „zu nah“ (Prüfer DL2): nur noch 105 $ bis zum Konto-Limit (Tagesstart 160.329, Start-Balance 158.684 → 1.645 $ Verlust heute)
        "d0887_knapp": ("REGELN", plan("p13", "d0887", "sell", 158684, "2026-10-22T03:00:00Z"), 28092.5, 2, 3,
                        [plan("p0b", "d0887", "sell", 160329, "2026-10-22T01:00:00Z")]),
    }
    lauf = ["const out = {}"]
    for k, (rg, p, ein, ppl, kt, frueher) in faelle.items():
        lauf.append(f"_liqRegeln = {rg}; tradePlans = {json.dumps(frueher + [p])}; out[{json.dumps(k)}] = hedgeLiqLevel({json.dumps(p)}, {ein}, {ppl}, {kt})")
    # DL2 Kurs-Verlauf 0887 (WH1, 11.11.2026): Einstieg 28.092,50 06:25 Dubai, TP 28.045,50, gegen den Master bis 28.600,5 um 20:53 — je Stand der
    # Wächter-Entscheid mit dem neuen Level (Tab: hedgeFeedEntscheidDetail(richtung, kurs, tpL, slL, puffer, hoch, tief)) und mit dem alten Boden-Level
    lauf.append("const verlauf = [28092.5, 28150, 28300, 28366, 28368, 28384.25, 28450, 28600.5]")
    lauf.append("out.verlauf_neu = verlauf.map(k => { const d = hedgeFeedEntscheidDetail('sell', k, 28045.5, out.d0887.sl_level_nq, 0.25, null, null); return d ? d.grund : null })")
    lauf.append("out.verlauf_alt = verlauf.map(k => { const d = hedgeFeedEntscheidDetail('sell', k, 28045.5, 29798.3, 0.25, null, null); return d ? d.grund : null })")
    lauf.append("print(JSON.stringify(out))")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(stub + "\n".join(teile) + "\n" + "\n".join(lauf))
        pfad = f.name
    try:
        aus = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=30)
    finally:
        os.unlink(pfad)
    if aus.returncode != 0 or not aus.stdout.strip().startswith("{"):
        print(aus.stdout, aus.stderr)
        sys.exit("✗ jsc-Lauf gescheitert")
    r = json.loads(aus.stdout.strip().splitlines()[-1])

    m = r["marc_buy"]
    vor = 5   # DL2-Schalter: Apex (stufen, dll_schutz leer) exakt wie vor DL2 — 5 Pkt
    pkt = round(4000 / 6 - vor, 2)
    check(m.get("liq_art") == "daily_loss" and m["liq_dll"]["stufe"] == 5 and m["liq_dll"]["usd"] == 4000,
          f"Marc 165.735: Stufe 5, Daily Loss 4.000 ({m.get('liq_dll')})")
    check(abs(m["liq_balance"] - 161735.2) < 0.01, f"Marc Liq-Balance 161.735,20 ({m['liq_balance']})")
    check(abs(m["sl_punkte"] - pkt) < 0.01 and abs(m["sl_level_nq"] - round(30000 - pkt, 2)) < 0.01,
          f"Marc buy 3 MNQ: {pkt} Pkt unter Einstieg = {round(30000 - pkt, 2)} ({m['sl_level_nq']})")
    check(abs(m["sl_usd_hedge"] - 4000) < 0.01 and m["liq_vor_pkt"] == vor and m["liq_dll"].get("dll_schutz") is False,
          "Marc: Hedge-$ 4.000, 5 Pkt davor — Apex ohne DL2-Schalter bitgleich wie vor DL2")
    ms = r["marc_schutz"]
    check(ms["liq_vor_pkt"] == 16.75 and abs(ms["sl_punkte"] - round(4000 / 6 - 16.75, 2)) < 0.01 and ms["liq_dll"].get("dll_schutz") is True,
          f"Apex mit dll_schutz true (Finns Entscheid): 16,75 Pkt (≥ 100 $) davor ({ms.get('sl_punkte')})")
    check(abs(r["marc_sell"]["sl_level_nq"] - round(30000 + pkt, 2)) < 0.01, f"Marc sell: Level über dem Einstieg ({r['marc_sell']['sl_level_nq']})")
    a = r["a100"]
    check(a.get("liq_art") == "daily_loss" and a["liq_dll"]["stufe"] == 3 and abs(a["liq_balance"] - 102550) < 0.01
          and abs(a["sl_punkte"] - round(1750 / 40 - 5, 2)) < 0.01, f"100k 2 NQ bei 104.300: Stufe 3, 1.750 $, 38,75 Pkt ({a.get('sl_punkte')})")
    af = r["a100_frueher"]
    check(af["liq_dll"]["tagesstart"] == 105200 and af["liq_dll"]["stufe"] == 4 and abs(af["liq_balance"] - 102700) < 0.01
          and abs(af["sl_punkte"] - round(1600 / 40 - 5, 2)) < 0.01, f"100k zweiter Trade des Tages: Tagesstart 105.200, Stufe 4, Liq 102.700 ({af.get('liq_dll')})")
    ab = r["a100_boden"]
    check(ab.get("liq_art") == "boden" and abs(ab["liq_balance"] - 100100) < 0.01 and abs(ab["sl_punkte"] - round(900 / 40, 2)) < 0.01,
          f"100k bei 101.000: Boden 100.100 enger als DLL 99.250, ohne 5 Pkt ({ab.get('liq_balance')}, {ab.get('sl_punkte')})")
    t = r["tdfy"]
    check(t.get("liq_art") == "boden" and abs(t["liq_balance"] - 150100) < 0.01 and not t.get("liq_dll"), "Tradeify-WD: unverändert 150.100")
    o = r["ohne_regeln"]
    check(abs(o["liq_balance"] - 150100) < 0.01 and o.get("liq_regeln_geladen") is False, "ohne geladene Regeln: wie bisher 150.100, Wächter trägt nach")
    # ── DL2 ──
    d = r["d0887"]
    pkt0887 = round(1750 / 6 - 16.75, 2)
    check(d.get("liq_art") == "daily_loss" and d["liq_dll"]["usd"] == 1750 and d["liq_dll"].get("dl_quelle") == "konto" and abs(d["liq_balance"] - 158579) < 0.01,
          f"DL2 0887: Konto-Limit 1.750 $ ab Tagesstart 160.329 → Liq 158.579 ({d.get('liq_dll')}, {d.get('liq_balance')})")
    check(abs(d["sl_punkte"] - pkt0887) < 0.01 and abs(d["sl_level_nq"] - round(28092.5 + pkt0887, 2)) < 0.01 and d["sl_level_nq"] < 28092.5 + 1750 / 6,
          f"DL2 0887 SELL: Level {round(28092.5 + pkt0887, 2)} liegt vor dem DLL-Punkt {round(28092.5 + 1750 / 6, 2)} (statt Boden ≈ 29.798) → {d.get('sl_level_nq')}")
    check(r["d0887_ohne_regeln"].get("liq_art") == "daily_loss" and r["d0887_ohne_regeln"].get("liq_regeln_geladen") is True,
          "DL2: Konto-Limit braucht keine geladenen Regeln (Level sofort, kein Nachtrag nötig)")
    f_ = r["flex"]
    check(f_.get("liq_art") == "boden" and abs(f_["liq_balance"] - 150100) < 0.01 and not f_.get("liq_dll"), "DL2: Flex (dll_usd 0) → kein Tageslimit, Boden 150.100")
    lu = r["lucid"]
    check(lu.get("liq_art") == "daily_loss" and lu["liq_dll"]["usd"] == 2700 and lu["liq_dll"].get("dl_quelle") == "liq_regeln_funded" and lu["liq_dll"]["regel_id"] == 17
          and abs(lu["liq_balance"] - 154300) < 0.01, f"DL2: Lucid-WD ohne Tageslimit in der WD-Zeile → Funded-Zeile id 17, 2.700 $ ab 157.000 ({lu.get('liq_dll')})")
    check(t.get("liq_art") == "boden" and not t.get("liq_dll"), "DL2: Tradeify-WD ohne Konto-Feld bleibt Boden (Funded-Zeile ist 'fest', kein Tageslimit)")
    vn, va = r["verlauf_neu"], r["verlauf_alt"]
    check(vn == [None, None, None, None, "sl_feed", "sl_feed", "sl_feed", "sl_feed"] and va == [None] * 8,
          f"DL2 Kurs-Verlauf 0887: neu schließt der Wächter ab 28.368 (vor dem DLL-Punkt 28.384,17, Tradeify schloss dort den Master), alt nie (Boden 29.798) — {vn} / {va}")
    k = r["d0887_knapp"]
    check(k.get("liq_art") == "daily_loss" and abs(k["sl_punkte"] - 5) < 0.01 and abs(k["liq_vor_pkt"] - 12.5) < 0.01,
          f"DL2 Kante: 105 $ bis zum DLL (17,5 Pkt) → Puffer auf 12,5 Pkt gekürzt, Level 5 Pkt vom Einstieg statt 0,75 ({k.get('sl_punkte')}, {k.get('liq_vor_pkt')})")
    z = r["zu_nah"]
    check(z.get("liq_art") == "daily_loss" and not z.get("liq_vor_pkt") and abs(z["sl_punkte"] - 4.38) < 0.01 and abs(z["sl_level_nq"] - 29995.62) < 0.01,
          f"Daily Loss < 5 Pkt (103.800, 20 NQ, 1.750 $ = 4,38 Pkt) → Level am DLL-Punkt selbst, nie keins ({z.get('sl_level_nq')})")

    print("\nALLES OK" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
