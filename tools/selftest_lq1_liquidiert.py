#!/usr/bin/env python3
"""Selbsttest LQ1 (Finn 24.11.2026: „Wenn ein Trade liquidiert wird und es nicht am Tageslimit lag, dann ist der Account geblowt. Auch wenn er laut Balance
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
    ("Lucid bfb19b42 (blown=true, 47.998 ≤ 48.000): Market-Exit vor dem Plan-SL OHNE bekannte Liq-Linie → null (Prüfer: sähe aus wie Hand-Schluss; den Blow belegt die Balance-Regel)",
     {"status": "completed", "richtung": "sell", "einstieg_nq": 26742.75, "tp_level_nq": 26252.25, "master_sl": 951,
      "hedge": {"grund": "master_ende_reader", "master_exit": mx("market", 26792.75), "tv_meldung_roh": ["sl platziert buy 1 @ 26,794.25 (Buy 1)"]}, "final": {}}, None),
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
    ("Hand-Schluss in TradingView ohne Marke, keine Liq-Linie → null",
     {"status": "review", "richtung": "sell", "einstieg_nq": 26000, "hedge": {"grund": "master_ende_reader", "master_exit": mx("market", 26030)}, "final": {}}, None),
    ("Laufender Trade → null", {"status": "open", "richtung": "buy", "einstieg_nq": 26000, "hedge": {"master_exit": mx("market", 25900)}}, None),
    # Gegenprobe 150 echte Trades 17.–24.11.2026 (Fehlalarme der ersten Fassung, jetzt nie „liq“):
    ("Tradeify b50f4ee2 (−1.899 $, nicht geblowt): Market-Exit 25.998 weit VOR der Konto-Liq 25.151 → null (kein Firmen-Schluss)",
     {"status": "completed", "richtung": "buy", "einstieg_nq": 26472.25, "hedge": {"grund": "master_ende_reader", "sl_art": "liquidation", "liq_art": "boden",
      "sl_level_nq": 25151.57, "master_exit": mx("market", 25998.25)}, "final": {}}, None),
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
# wdlBlowStand-Attrappe: _soft = Balance-Beleg „am Tageslimit, Konto lebt“ (wie das Radar-Wort ⏸ Tagespause)
js = ("var escapeHtml=function(s){return s};function wdlBlowStand(t){return t&&t._soft?{geblowt:false,softBreach:true}:null}\n"
      "function wdlLiqIstTag(t){return !!(t&&t.liq_regel_soft&&t.liq_gilt==='regel')}\n") + js
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
