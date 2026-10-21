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
    teile = [js_zeile(src, "const HEDGE_DLL_VOR_PKT"), js_zeile(src, "const hedgeLiqDllFelder")]
    teile += [js_funktion(src, n) for n in ("firmNormRichtung", "tvV2Handelstag", "liqRegelWaehlen", "liqDailyLoss", "hedgeTagesstart",
                                            "hedgeLiqDll", "hedgeLiqStart", "hedgeLiqLevel")]
    acc = [
        {"id": "marc", "name": "150k PAAPEX6843320000001 → Funded", "firm": "Apex Trader", "type": "winning_days", "startingBalance": None},
        {"id": "a100", "name": "100k PAAPEX0000000000099 → Funded", "firm": "Apex Trader", "type": "winning_days", "startingBalance": 100000},
        {"id": "tdfy", "name": "150k TDFYSL150 → WD", "firm": "Tradeify", "type": "winning_days", "startingBalance": 150000},
    ]
    stub = f"""
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
    }
    lauf = ["const out = {}"]
    for k, (rg, p, ein, ppl, kt, frueher) in faelle.items():
        lauf.append(f"_liqRegeln = {rg}; tradePlans = {json.dumps(frueher + [p])}; out[{json.dumps(k)}] = hedgeLiqLevel({json.dumps(p)}, {ein}, {ppl}, {kt})")
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
    pkt = round(4000 / 6 - 5, 2)
    check(m.get("liq_art") == "daily_loss" and m["liq_dll"]["stufe"] == 5 and m["liq_dll"]["usd"] == 4000,
          f"Marc 165.735: Stufe 5, Daily Loss 4.000 ({m.get('liq_dll')})")
    check(abs(m["liq_balance"] - 161735.2) < 0.01, f"Marc Liq-Balance 161.735,20 ({m['liq_balance']})")
    check(abs(m["sl_punkte"] - pkt) < 0.01 and abs(m["sl_level_nq"] - round(30000 - pkt, 2)) < 0.01,
          f"Marc buy 3 MNQ: {pkt} Pkt unter Einstieg = {round(30000 - pkt, 2)} ({m['sl_level_nq']})")
    check(abs(m["sl_usd_hedge"] - 4000) < 0.01 and m["liq_vor_pkt"] == 5, "Marc: Hedge-$ 4.000, 5 Pkt davor")
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
    z = r["zu_nah"]
    check(z.get("liq_art") == "daily_loss" and not z.get("liq_vor_pkt") and abs(z["sl_punkte"] - 4.38) < 0.01 and abs(z["sl_level_nq"] - 29995.62) < 0.01,
          f"Daily Loss < 5 Pkt (103.800, 20 NQ, 1.750 $ = 4,38 Pkt) → Level am DLL-Punkt selbst, nie keins ({z.get('sl_level_nq')})")

    print("\nALLES OK" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
