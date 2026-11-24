#!/usr/bin/env python3
"""Selbsttest LQ1 + LQ2 (LQ2 25.11.2026: Firmen-Schluss ohne eigene Marke = liquidiert, auch über der Linie; Plan-SL an der Konto-Liq mit ≤ 100 $ Luft = Konto am Ende). LQ1 (Finn 24.11.2026: „Wenn ein Trade liquidiert wird und es nicht am Tageslimit lag, dann ist der Account geblowt. Auch wenn er laut Balance
noch über dem Boden ist.“). Prüft prophos.html lqEndeUrteil (JXA, echte Funktion aus der Datei) an ECHTEN Plänen vom 23./24.11.2026 (DB, nur gelesen) und an
konstruierten Fällen, dazu die Einhängung (Abhak-Vorbelegung über wdlGeblowtUrteil, Radar-Wort, Popup-Hinweis). Nur Vorschlag, nie archivieren.
Kein Netz. macOS (osascript) nötig, sonst übersprungen."""
import json
import os
import re
import shutil
import subprocess
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def mx(art, preis, text=None):
    return {"art": art, "preis": preis, "text": text or f"x at {preis}", "quelle": "toast"}


def roh(sl=None, tp=None):
    r = []
    if tp:
        r.append(f"tp platziert sell 3 @ {tp:,.2f}")
    if sl:
        r.append(f"sl platziert sell 3 @ {sl:,.2f}")
    return r


# (name, t, erwartet art) — echte Pläne (DB 24.11.2026, nur gelesen) + konstruierte Fälle
FAELLE = [
    ("Marc Apex PA …0006 754a74f3: Exit 26.055,75 am Plan-SL 26.056 → plan (NICHT liquidiert)",
     {"status": "review", "richtung": "buy", "einstieg_nq": 26523.75, "tp_level_nq": 26589.5, "master_sl": 2797,
      "hedge": {"grund": "level_sl", "master_exit": mx("stop", 26055.75, "Sell 3 at 26,055.75"), "sl_level_nq": 26055.83,
                "tv_meldung_roh": ["fill ausgefuehrt buy 3 @ 26,523.75 (Buy 3)", "tp platziert sell 3 @ 26,589.50 (Sell 3)", "sl platziert sell 3 @ 26,056.00 (Sell 3)"]},
      "final": {"quelle": "puls"}}, "plan"),
    ("Lucid 6a9ca349: Stop am Plan-SL 26.068,50 → plan",
     {"status": "review", "richtung": "buy", "einstieg_nq": 26095.75, "tp_level_nq": 26401.75, "master_sl": 1624,
      "hedge": {"grund": "level_sl", "master_exit": mx("stop", 26068.5), "tv_meldung_roh": ["sl platziert sell 3 @ 26,068.50 (Sell 3)"]}, "final": {}}, "plan"),
    ("Tradeify cc5cc860: Exit am TP → plan",
     {"status": "completed", "richtung": "sell", "einstieg_nq": 26316.25, "tp_level_nq": 26246.25,
      "hedge": {"grund": "level_tp", "master_exit": mx("tp", 26246.25), "tv_meldung_roh": ["sl platziert buy 2 @ 26,862.50 (Buy 2)"]}, "final": {}}, "plan"),
    ("Apex 7d3a1c1b (blown=true, Balance 96.859 < Boden): Market-Exit ohne Plan-SL an der Konto-Liq → liq",
     {"status": "completed", "richtung": "sell", "einstieg_nq": 26777.75, "tp_level_nq": 26595,
      "hedge": {"grund": "level_sl", "sl_art": "liquidation", "liq_art": "apex_boden", "sl_level_nq": 26814.39, "master_exit": mx("market", 26817.75),
                "tv_meldung_roh": ["tp platziert buy 2 @ 26,595.00 (Buy 2)"]}, "final": {}}, "liq"),
    ("Lucid bfb19b42 (blown=true, 47.998 ≤ 48.000), Zeile ohne Tageslimit-Kennung: Market-Exit vor dem Plan-SL ohne Liq-Linie → liq (LQ2 a, vorher null)",
     {"status": "completed", "richtung": "sell", "einstieg_nq": 26742.75, "tp_level_nq": 26252.25, "master_sl": 951,
      "hedge": {"grund": "master_ende_reader", "master_exit": mx("market", 26792.75), "tv_meldung_roh": ["sl platziert buy 1 @ 26,794.25 (Buy 1)"]}, "final": {}}, "liq"),
    ("Lucid bfb19b42 als Tageslimit-Firma (liq_regel_soft) ohne harte Linie → dll (Tagespause bleibt)",
     {"status": "completed", "richtung": "sell", "einstieg_nq": 26742.75, "tp_level_nq": 26252.25, "master_sl": 951, "liq_regel_soft": True,
      "hedge": {"grund": "master_ende_reader", "master_exit": mx("market", 26792.75), "tv_meldung_roh": ["sl platziert buy 1 @ 26,794.25 (Buy 1)"]}, "final": {}}, "dll"),
    ("Lucid ea9d35b8 (−2.762 $ ≈ DLL 2.700, Konto lebt): Balance am Tageslimit → dll, nicht liq",
     {"status": "completed", "richtung": "sell", "einstieg_nq": 25840, "tp_level_nq": 25805.5, "_soft": True,
      "hedge": {"grund": "master_ende_reader", "sl_art": "liquidation", "liq_art": "polster_tradeify", "sl_level_nq": 25950, "master_exit": mx("market", 25908.75)},
      "final": {}}, "dll"),
    ("Exit jenseits des Plan-SL (Slippage des eigenen Stops) → plan",
     {"status": "review", "richtung": "buy", "einstieg_nq": 26000, "tp_level_nq": 26100, "master_sl": 1000,
      "hedge": {"master_exit": mx("stop", 25947.0), "tv_meldung_roh": roh(sl=25950.0)}, "final": {}}, "plan"),
    ("Gewinnseite ohne TP (Auto-Close/Hand) → null",
     {"status": "review", "richtung": "buy", "einstieg_nq": 26000, "tp_level_nq": 26100, "hedge": {"master_exit": mx("market", 26050)}, "final": {}}, None),
    ("Eigener Schluss (final.ende_grund zschluss) auf der Verlustseite → null",
     {"status": "review", "richtung": "buy", "einstieg_nq": 26000, "tp_level_nq": 26100, "hedge": {"master_exit": mx("market", 25980)},
      "final": {"ende_grund": "zschluss"}}, None),
    ("Auto-Close (hedge.grund auto_close) → null",
     {"status": "review", "richtung": "buy", "einstieg_nq": 26000, "tp_level_nq": 26100, "hedge": {"grund": "auto_close", "master_exit": mx("market", 25980)}, "final": {}}, None),
    ("tv-close (positionen_danach) → null",
     {"status": "review", "richtung": "sell", "einstieg_nq": 26000, "hedge": {"master_exit": mx("market", 26020)}, "final": {"positionen_danach": []}}, None),
    ("Meldung „Account liquidated“ → liq (auch am Plan-SL vorbei)",
     {"status": "review", "richtung": "buy", "einstieg_nq": 26000, "hedge": {"master_exit": mx("market", 25990, "Auto-Liquidation: Sell 3 at 25,990")}, "final": {}}, "liq"),
    ("Meldung „Daily loss limit — liquidated“ → dll",
     {"status": "review", "richtung": "buy", "einstieg_nq": 26000, "hedge": {}, "final": {"meldung": "Daily loss limit reached - position liquidated"}}, "dll"),
    ("Demo demo_liq am weichen Tageslimit (Lucid aebbb47c) → dll",
     {"status": "review", "richtung": "sell", "einstieg_nq": 26315.5, "liq_regel_soft": True, "final": {"grund": "demo_liq"}}, "dll"),
    ("Demo demo_liq an harter Liq ohne Plan-SL (Tradeify) → liq",
     {"status": "review", "richtung": "buy", "einstieg_nq": 26000, "final": {"grund": "demo_liq"}}, "liq"),
    ("Demo demo_liq MIT Plan-SL → null (die Demo kennt den echten Ausgang nicht)",
     {"status": "review", "richtung": "buy", "einstieg_nq": 26000, "sl_art": "bracket", "sl_level_nq": 25950, "final": {"grund": "demo_liq"}}, None),
    ("Weiches Tageslimit am Liq-Regel-Level (Exit am DLL-Level) → dll",
     {"status": "review", "richtung": "buy", "einstieg_nq": 26000, "liq_regel_soft": True, "liq_gilt": "regel", "liq_regel_level_nq": 25955, "hedge": {"master_exit": mx("market", 25955.5)}, "final": {}}, "dll"),
    ("Prüfer LQ1: liq_regel_level_nq ist der Konto-Boden (liq_gilt nicht 'regel'), Exit dort, Konto-Liq bekannt → liq, nicht dll",
     {"status": "review", "richtung": "buy", "einstieg_nq": 26000, "liq_regel_soft": True, "liq_gilt": "konto", "liq_regel_level_nq": 25900, "liq_level_nq": 25900,
      "hedge": {"master_exit": mx("market", 25899)}, "final": {}}, "liq"),
    ("Prüfer LQ1: eigener Schluss (final.quelle 'close', tvV2EndeSetzen) auf der Verlustseite → null",
     {"status": "review", "richtung": "buy", "einstieg_nq": 26000, "liq_level_nq": 25900, "hedge": {"master_exit": mx("market", 25899)}, "final": {"quelle": "close"}}, None),
    ("LQ2 (a): Market-Schluss ohne eigene Marke, keine Liq-Linie, kein Tageslimit → liq (Finn 25.11.: „einfach schließt … kein Daily Stop Loss = liquidiert“)",
     {"status": "review", "richtung": "sell", "einstieg_nq": 26000, "hedge": {"grund": "master_ende_reader", "master_exit": mx("market", 26030)}, "final": {}}, "liq"),
    ("LQ2 (a): eigener Stop auf der Verlustseite, nicht am ersten Plan-SL (nachgezogener SL), ohne Liq-Linie → null (kein Firmen-Schluss)",
     {"status": "review", "richtung": "buy", "einstieg_nq": 26000, "tp_level_nq": 26100, "master_sl": 1000,
      "hedge": {"master_exit": mx("stop", 25980), "tv_meldung_roh": roh(sl=25950.0)}, "final": {}}, None),
    ("Laufender Trade → null", {"status": "open", "richtung": "buy", "einstieg_nq": 26000, "hedge": {"master_exit": mx("market", 25900)}}, None),
    # Gegenprobe 150 echte Trades 17.–24.11.2026 (Fehlalarme der ersten Fassung, jetzt nie „liq“):
    ("LQ2 (a) Tradeify WD b50f4ee2 (−1.899 $, Balance 153.483 > WD-Liq 150.100, Finn archivierte ihn geblowt): Market-Exit weit vor der Konto-Liq → liq",
     {"status": "completed", "richtung": "buy", "einstieg_nq": 26472.25, "hedge": {"grund": "master_ende_reader", "sl_art": "liquidation", "liq_art": "boden",
      "sl_level_nq": 25151.57, "master_exit": mx("market", 25998.25)}, "final": {}}, "liq"),
    # LQ2 (b): Exit am Plan-SL, danach höchstens 100 $ über der harten Konto-Liq (echte Pläne, DB 25.11.2026, nur gelesen)
    ("LQ2 (b) Marc · Lucid 150k …0001 6a9ca349: Stop am Plan-SL 26.068,50, Balance 145.529 bei Liq 145.500 → liq (Finn archivierte von Hand)",
     {"status": "review", "richtung": "buy", "einstieg_nq": 26095.75, "tp_level_nq": 26401.75, "master_sl": 1624, "_bal": 145529, "_liq": 145500,
      "hedge": {"grund": "level_sl", "master_exit": mx("stop", 26068.5, "Sell 3 at 26,068.50"), "tv_meldung_roh": ["sl platziert sell 3 @ 26,068.50 (Sell 3)"]}, "final": {}}, "liq"),
    ("LQ2 (b) Chris · Lucid 150k …0001 5b1b7bdc: Stop 26.385,75 (0,75 hinter Plan-SL 26.386,50), Balance 145.544 → liq",
     {"status": "completed", "richtung": "buy", "einstieg_nq": 26410.5, "tp_level_nq": 26696.25, "master_sl": 1489, "_bal": 145544, "_liq": 145500,
      "hedge": {"grund": "master_ende_reader", "master_exit": mx("stop", 26385.75, "Sell 3 at 26,385.75"), "tv_meldung_roh": ["sl platziert sell 3 @ 26,386.50 (Sell 3)"]}, "final": {}}, "liq"),
    ("LQ2 (b) Simon · Lucid 150k …0001 82f9d471: Stop 27.339,25 am Plan-SL 27.339,75, Balance 145.544 → liq",
     {"status": "completed", "richtung": "buy", "einstieg_nq": 27370.75, "tp_level_nq": 27639, "master_sl": 1894, "_bal": 145544, "_liq": 145500,
      "hedge": {"grund": "master_ende_reader", "master_exit": mx("stop", 27339.25, "Sell 3 at 27,339.25"), "tv_meldung_roh": ["sl platziert sell 3 @ 27,339.75 (Sell 3)"]}, "final": {}}, "liq"),
    ("LQ2 (b) Marc · Apex …0006 754a74f3 mit Balance 112.429 bei Liq 100.100 → plan (bleibt normal)",
     {"status": "review", "richtung": "buy", "einstieg_nq": 26523.75, "tp_level_nq": 26589.5, "master_sl": 2797, "_bal": 112428.52, "_liq": 100100,
      "hedge": {"grund": "level_sl", "master_exit": mx("stop", 26055.75, "Sell 3 at 26,055.75"), "tv_meldung_roh": ["sl platziert sell 3 @ 26,056.00 (Sell 3)"]}, "final": {}}, "plan"),
    ("LQ2 (b) Mike · Lucid 150k 096f23ed Tageslimit-Tag: Stop am Plan-SL, Balance 147.289 (1.789 $ Luft) → plan",
     {"status": "completed", "richtung": "buy", "einstieg_nq": 27404.5, "tp_level_nq": 27623.25, "master_sl": 2600, "_bal": 147289.5, "_liq": 145500,
      "hedge": {"grund": "level_sl", "master_exit": mx("stop", 27359.5), "tv_meldung_roh": ["sl platziert sell 3 @ 27,359.75 (Sell 3)"]}, "final": {}}, "plan"),
    ("LQ2 (b) Plan-SL nah an der Linie, aber Balance am Tageslimit (softBreach) → plan, nie liq",
     {"status": "completed", "richtung": "buy", "einstieg_nq": 27404.5, "tp_level_nq": 27623.25, "master_sl": 2600, "_soft": True,
      "hedge": {"grund": "level_sl", "master_exit": mx("stop", 27359.5), "tv_meldung_roh": ["sl platziert sell 3 @ 27,359.75 (Sell 3)"]}, "final": {}}, "plan"),
    ("LQ2 (b) Grenze: 101 $ Luft nach dem Plan-SL → plan; 100 $ → liq",
     {"status": "review", "richtung": "sell", "einstieg_nq": 26000, "tp_level_nq": 25900, "master_sl": 500, "_bal": 48101, "_liq": 48000,
      "hedge": {"master_exit": mx("stop", 26025), "tv_meldung_roh": roh(sl=26025.0)}, "final": {}}, "plan"),
    # LQ2 Prüfung: Tageslimit auch ohne weiche Zeile (Lucid Funded/WD: Tageslimit 2.700 $ aus der Funded-Zeile von liq_regeln)
    ("LQ2 Lucid Funded 150k: Market-Exit vor der Linie, Verlust 2.730 $ ≈ Tageslimit 2.700 → dll (nicht liq)",
     {"status": "completed", "richtung": "buy", "einstieg_nq": 26000, "tp_level_nq": 26300, "master_pl": -2730, "konto_typ": "funded",
      "konto": {"firma": "Lucid Trading", "name": "150k LFF15000000000001 → Funded"}, "hedge": {"grund": "master_ende_reader", "master_exit": mx("market", 25954.5)}, "final": {}}, "dll"),
    ("LQ2b Prüfer: Radar-Zeile mit master_pl als Objekt {wert, art}, Balance noch nicht gelesen, −2.730 $ am Tageslimit → dll (nicht liq)",
     {"status": "completed", "richtung": "buy", "einstieg_nq": 26000, "tp_level_nq": 26300, "master_pl": {"wert": -2730, "art": "tv"}, "konto_typ": "funded",
      "konto": {"firma": "Lucid Trading", "name": "150k LFF15000000000003 → Funded"}, "hedge": {"grund": "master_ende_reader", "master_exit": mx("market", 25954.5)}, "final": {}}, "dll"),
    ("LQ2b Prüfer: ohne master_pl, nur pl_balance −2.720 $ → dll",
     {"status": "completed", "richtung": "buy", "einstieg_nq": 26000, "tp_level_nq": 26300, "pl_balance": -2720, "konto_typ": "funded",
      "konto": {"firma": "Lucid Trading", "name": "150k LFF15000000000004 → Funded"}, "hedge": {"grund": "master_ende_reader", "master_exit": mx("market", 25954.5)}, "final": {}}, "dll"),
    ("LQ2b Prüfer: master_pl-Objekt −1.500 $ (unter dem Tageslimit) → liq",
     {"status": "completed", "richtung": "buy", "einstieg_nq": 26000, "tp_level_nq": 26300, "master_pl": {"wert": -1500, "art": "tv"}, "konto_typ": "funded",
      "konto": {"firma": "Lucid Trading", "name": "150k LFF15000000000005 → Funded"}, "hedge": {"grund": "master_ende_reader", "master_exit": mx("market", 25975)}, "final": {}}, "liq"),
    ("LQ2 Lucid WD 150k (Tageslimit über die Funded-Zeile): Verlust 1.500 $ weit unter dem Tageslimit, Market-Exit → liq",
     {"status": "completed", "richtung": "buy", "einstieg_nq": 26000, "tp_level_nq": 26300, "master_pl": -1500, "konto_typ": "winning_days",
      "konto": {"firma": "Lucid Trading", "name": "150k LFF15000000000002 → Winning Days"}, "hedge": {"grund": "master_ende_reader", "master_exit": mx("market", 25975)}, "final": {}}, "liq"),
    ("LQ2 eigener Radar-Schluss über den Kurs-Feed (hedge.grund sl_feed) ohne Plan-SL → null (kein Firmen-Schluss)",
     {"status": "completed", "richtung": "sell", "einstieg_nq": 26000, "hedge": {"grund": "sl_feed", "master_exit": mx("market", 26040)}, "final": {"grund": "sl_feed"}}, None),
    ("LQ2 (b) Grenze: 100 $ Luft → liq",
     {"status": "review", "richtung": "sell", "einstieg_nq": 26000, "tp_level_nq": 25900, "master_sl": 500, "_bal": 48100, "_liq": 48000,
      "hedge": {"master_exit": mx("stop", 26025), "tv_meldung_roh": roh(sl=26025.0)}, "final": {}}, "liq"),
    ("Lucid 9406cc36 (−2.797 $, nicht geblowt, Tageslimit-Firma): Exit vor der Polster-Linie → dll",
     {"status": "completed", "richtung": "buy", "einstieg_nq": 27348.5, "liq_regel_soft": True, "hedge": {"grund": "master_ende_reader", "sl_art": "liquidation",
      "liq_art": "polster_tradeify", "sl_level_nq": 27238.5, "master_exit": mx("market", 27278.75)}, "final": {}}, "dll"),
    ("Lucid 86413a07 (−1.228 $ = DLL 50k, Hedge liq_art daily_loss, keine Linie) → dll",
     {"status": "completed", "richtung": "sell", "einstieg_nq": 27397.75, "hedge": {"grund": "master_ende_reader", "sl_art": "liquidation", "liq_art": "daily_loss",
      "master_exit": mx("market", 27459)}, "final": {}}, "dll"),
]

if not shutil.which("osascript"):
    print("· übersprungen (kein osascript)")
    sys.exit(0)

m = re.search(r"  const LQ_TOL_PKT = .*?\n  window\._lqEndeUrteil = lqEndeUrteil", HTML, re.S)
check(bool(m), "lqEndeUrteil im Frontend gefunden")
sl = re.search(r"  function wdlSlEcht\(t\)\{.*?\n  \}\n", HTML, re.S)
js = (sl.group(0) if sl else "") + (m.group(0).replace("  window._lqEndeUrteil = lqEndeUrteil", "") if m else "")
# wdlBlowStand-Attrappe: _soft = Balance-Beleg „am Tageslimit, Konto lebt“ (wie das Radar-Wort ⏸ Tagespause); _bal/_liq = Balance nach dem Trade + harte Konto-Liq (LQ2 b)
js = ("var escapeHtml=function(s){return s};function wdlBlowStand(t){if(t&&t._soft)return{geblowt:false,softBreach:true};"
      "if(t&&t._bal!=null)return{bal:t._bal,liq:t._liq,geblowt:t._bal<=t._liq+25,softBreach:false};return null}\n"
      "function wdlLiqIstTag(t){return !!(t&&t.liq_regel_soft&&t.liq_gilt==='regel')}\n"
      # Tageslimit-Quelle (LQ2): nur die Funded-Zeile Lucid 150k aus liq_regeln (id 17: 2.700 $ ab Tagesstart)
      "var _liqRegeln=[{firma:'Lucid Trading',kontotyp:'funded',groesse:150000,art:'tagesstart',betrag_usd:2700}];"
      "function liqRegelWaehlen(r,f,kt,g){return r.find(function(x){return x.firma===f&&x.kontotyp===kt&&x.groesse===g})||null}"
      "function liqDailyLoss(r,b){return r&&r.art==='tagesstart'?{dl:Number(r.betrag_usd)}:null}"
      "function tpKontoGroesseAusName(n){var m=/(\\d+)k/i.exec(n||'');return m?Number(m[1])*1000:0}\n") + js
js += "\nJSON.stringify([" + ",".join(f"(function(){{var u=lqEndeUrteil({json.dumps(t)});return u?u.art:null}})()" for _, t, _e in FAELLE) + "])"
r = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], capture_output=True, text=True)
try:
    erg = json.loads(r.stdout.strip())
except Exception:
    erg = None
    check(False, f"JXA lief nicht: {r.stderr[:200]}")
for (name, _t, soll), ist in zip(FAELLE, erg or []):
    check(ist == soll, f"{name} (ist {ist})")

# Einhängung
check("function wdlGeblowtVorschlag(t){ return wdlGeblowtUrteil(t) || " in HTML and "lqEndeUrteil" not in re.search(r"function wdlGeblowtUrteil\(t\)\{.*?\}\n", HTML, re.S).group(0),
      "Liq-Verdacht NICHT in wdlGeblowtUrteil (Gruppe „Geblowt · archivieren“/Sammel), nur in wdlGeblowtVorschlag (Prüfer LQ1)")
check(HTML.count("wdlGeblowtVorschlag(pw)") == 1 and HTML.count("if(tr && wdlGeblowtVorschlag(tr)){") == 1, "beide Abhak-Dialoge belegen über wdlGeblowtVorschlag „geblowt“ vor")
check("return 'vermutlich liquidiert — bitte prüfen'" in HTML and "'vermutlich liquidiert — bitte prüfen'" not in re.search(r"const WDL_SAMMEL_BLOW = new Set\(\[.*?\]\)", HTML).group(0),
      "Ein-Klick/Sammel bucht einen Liq-Verdacht nie (eigener Grund, nicht in WDL_SAMMEL_BLOW)")
check("💀 vermutlich liquidiert</b>" in HTML and "(b.softBreach || (lq && lq.art === 'dll')) ? WDL_TAGESLIMIT_ERG" in HTML,
      "Radar-Wort: „💀 vermutlich liquidiert“ bzw. „⏸ Tagespause“")
check("msgEl.textContent = `💀 vermutlich liquidiert — ${lq.grund}" in HTML, "Abhak-Popup nennt den Grund")
lq_block = m.group(0) if m else ""
check(not re.search(r"archiveAccount|\.update\(|\.insert\(|fetch\(", lq_block), "lqEndeUrteil rechnet nur (kein Archivieren, kein Schreiben)")

print()
print("ALLES OK" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
