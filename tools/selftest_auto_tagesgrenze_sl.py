#!/usr/bin/env python3
"""Selbsttest SL UNTER DER TAGESGRENZE (app.py ap_tagesgrenze + ap_konto_rechnen, 26.10.2026, Master Teil A — Anlass FundingPips 100k …6924
am 23.10.2026: SL 2.948 $ bei Daily Loss 3 % der Tagesstart-Equity 96.463 = 2.894 $, Verlust 2.990 $). Rein rechnend, ohne Netz.

Geprüft: Grenze aus daily_pct (Basis Tagesstart bzw. Größe) oder daily_usd, soft → keine; heute realisierter Verlust zieht ab; SL über
Grenze − 100 $ wird gekappt (ohne „+50 dahinter"), darunter bleibt er; Boden enger → „SL hinter den Boden" bleibt; Tagesgrenze enger als der
Boden → sie gewinnt, die Stufe verliert „hinter den Boden"; Rest unter dem Puffer → kein Trade; ohne Grenze unverändert, Feld null;
Futures ohne SL tragen das Feld trotzdem; ein alter Lader ohne den Helfer rechnet weiter. Dazu Text-Prüfungen des Vertrags
tages_grenze_usd in app.py (Planzeile, Rückfall ohne Spalte), prophos.html (Echo-Body, Orbit-Body + Marke, Signale) und panel.py.
Aufruf: python3 tools/selftest_auto_tagesgrenze_sl.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
APP = os.path.join(WURZEL, "app.py")
FUNKTIONEN = ["_wd_num", "ap_groesse", "_ap_spanne", "_ap_runden", "ap_kw_param", "_ap_boden", "ap_kette_regel", "ap_konto_rechnen",
              "ap_klein_trade", "ap_klein_trade_fut", "_ap_de", "ap_tagesgrenze"]
KONSTANTEN = ("AP_REST_MIN", "AP_REST_MIN_CFD", "AP_KLEIN_PKT", "AP_KLEIN_PUFFER", "AP_KLEIN_SCHRITT", "AP_KLEIN_TP_PKT_HINWEIS",
              "AP_PUFFER_PKT", "AP_CFD_ROUTEN", "AP_GROESSE_TOLERANZ", "AP_KETTE_STANDARD", "AP_KETTE_TXT", "AP_SL_HINTER_BODEN",
              "AP_PUFFER_JE_KT_FUT", "AP_GEBUEHR_JE_KT_FUT", "AP_FUT_DECKEL_PLUS_USD", "AP_TAGES_PUFFER")
FEHLER = []


def check(ok, name):
    print(("OK   " if ok else "FEHL ") + name)
    if not ok:
        FEHLER.append(name)


def lade(funktionen=FUNKTIONEN):
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re}
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in KONSTANTEN]
    for name in funktionen:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns


def regel(**kw):
    # wie auto_plan_regeln.regeln.firmen[] (FundingPips-Standard-artig) — Werte frei gewählt, nicht die Live-Regel
    r = {"kauf_eur": 100, "boden": "statisch", "dd_pct": 10, "route": "mt5v2", "ziel_pct": {"phase1": 8}, "groessen": [100000],
         "phasen": {"phase1": {"menge": [1, 1], "tp": [3000, 3000], "sl": [2500, 3000], "menge_schritt": 0.1}}}
    r.update(kw)
    return r


U = {"tp": 0.0, "sl": 1.0, "menge": 0.0, "puffer": 0.0}        # SL am oberen Rand der Spanne


def main():
    ns = lade()
    tg, rechnen = ns["ap_tagesgrenze"], ns["ap_konto_rechnen"]

    # ── ap_tagesgrenze ──
    check(tg({"daily_pct": 3}, 100000, 96463.40) == 2893.90, "3 % der Tagesstart-Balance 96.463,40 → 2.893,90 (Dashboard …6924)")
    check(tg({"daily_pct": 5, "daily_basis": "groesse"}, 100000, 93000) == 5000.0, "5 % der Größe 100k → 5.000 unabhängig von der Balance")
    check(tg({"daily_usd": 3000}, 100000, 93000) == 3000.0, "daily_usd fest 3.000")
    check(tg({"daily_pct": 5, "daily_basis": "groesse", "daily_usd": 5000}, 200000, 200000) == 10000.0,
          "daily_pct geht vor daily_usd (FTMO 200k → 10.000 statt 5.000)")
    check(tg({"daily_usd": 2000, "soft": True}, 100000, 100000) is None, "soft (Apex) → keine Grenze")
    check(tg({}, 100000, 100000) is None and tg(None, 100000, 1) is None, "ohne Kernwert → keine Grenze")
    check(tg({"daily_pct": None, "daily_usd": None}, 100000, 100000) is None, "daily_pct null (Flex-Größe) → keine Grenze")
    check(tg({"daily_pct": 3}, 100000, 100000, heute_verlust=1200) == 1800.0, "heute 1.200 $ verloren → Rest 1.800")
    check(tg({"daily_pct": 3}, 100000, 100000, heute_verlust=-500) == 3000.0, "heutiger Gewinn weitet die Grenze nicht")
    check(tg({"daily_pct": 3}, 100000, 100000, heute_verlust=4000) == 0.0, "gerissene Grenze → 0, nie negativ")

    # ── ap_konto_rechnen: der Vorfall ──
    w, g = rechnen(regel(daily_pct=3), "phase1", 96463.40, U)
    check(not g and w["sl"] == 2793 and w["tages_grenze_usd"] == 2893.90,
          f"…6924: SL 3.000 → 2.793 (2.893,90 − 100), Feld 2.893,90 ({w and (w['sl'], w['tages_grenze_usd'])}, {g})")
    check(w and w["stufe"] == "Etappe, SL auf Tagesgrenze gekappt (2.894 − 100 $)" and "hinter den Boden" not in w["stufe"] and w["risiko"] == 2793,
          f"Stufe nennt die Kappung, Risiko = SL ({w and w['stufe']})")

    w, g = rechnen(regel(daily_pct=3, phasen={"phase1": {"menge": [1, 1], "tp": [3000, 3000], "sl": [1800, 2250]}}), "phase1", 96463.40, U)
    check(not g and w["sl"] == 2250 and w["tages_grenze_usd"] == 2893.90 and "Tagesgrenze" not in w["stufe"],
          f"SL 2.250 unter Grenze − Puffer bleibt, Feld trotzdem gesetzt ({w and (w['sl'], w['stufe'])})")

    # Boden enger als die Tagesgrenze: Boden-Regel bleibt (TP oder geblowt)
    w, g = rechnen(regel(daily_pct=3), "phase1", 91535, U)
    check(not g and w["sl"] == 1585 and "SL hinter den Boden (+50 $)" in w["stufe"] and "Tagesgrenze" not in w["stufe"],
          f"…6925: Boden 90.000 → SL 1.535 + 50 = 1.585, Tagesgrenze 2.746 nicht enger ({w and (w['sl'], w['stufe'])})")

    # Tagesgrenze enger als der Boden-SL: sie gewinnt, „hinter den Boden" fällt weg (echoV2Final liest sonst blow)
    w, g = rechnen(regel(daily_pct=3, phasen={"phase1": {"menge": [1, 1], "tp": [3000, 3000], "sl": [3200, 3200]}}), "phase1", 93000, U)
    check(not g and w["sl"] == 2690 and "hinter den Boden" not in w["stufe"] and w["stufe"] == "Etappe, SL auf Tagesgrenze gekappt (2.790 − 100 $)",
          f"Boden-SL 3.050 vs. Grenze 2.790 − 100 → 2.690, ohne „hinter den Boden“ ({w and (w['sl'], w['stufe'])})")

    # Rest unter dem Puffer → kein Trade
    w, g = rechnen(regel(daily_pct=3), "phase1", 100000, U, heute_verlust=2950)
    check(w is None and g and g.startswith("Tagesgrenze erreicht — nur noch 50 $"), f"Rest 50 $ ≤ Puffer → kein Trade ({g})")

    # ohne Grenze unverändert
    w, g = rechnen(regel(), "phase1", 96463.40, U)
    check(not g and w["sl"] == 3000 and w["tages_grenze_usd"] is None, f"ohne Kernwert: SL 3.000, Feld null ({w and w['sl']})")
    w, g = rechnen(regel(daily_usd=2000, soft=True), "phase1", 96463.40, U)
    check(not g and w["sl"] == 3000 and w["tages_grenze_usd"] is None, "soft: SL unverändert, Feld null")

    # je Größe: daily_pct null schaltet die Firmen-Grenze ab (FundingPips Flex)
    jg = {"100000": {"dd_pct": 12, "daily_pct": None, "ziel_pct": {"phase1": 10},
                     "phasen": {"phase1": {"menge": [1, 1], "tp": [4500, 4500], "sl": [2250, 2700], "boden_pct": 12}}}}
    w, g = rechnen(regel(daily_pct=3, je_groesse=jg), "phase1", 96463.40, U)
    check(not g and w["sl"] == 2700 and w["tages_grenze_usd"] is None, f"Flex-Größe mit daily_pct null: keine Kappung ({w and w['sl']}, {g})")

    # Futures-Challenge ohne SL: Feld aus daily_usd, kein SL
    fut = {"kauf_eur": 100, "boden": "statisch", "dd_usd": 4500, "daily_usd": 2700, "route": "tvv2", "ziel_pct": {"challenge": 6},
           "groessen": [150000], "phasen": {"challenge": {"menge": [2, 2], "tp": [4400, 4500], "tp_max": 4500, "dd_usd": 4500}}}
    w, g = rechnen(fut, "challenge", 151000, U)
    check(not g and w["sl"] is None and w["tages_grenze_usd"] == 2700.0, f"Futures ohne SL: Feld 2.700, SL null ({w and (w['sl'], w['tages_grenze_usd'])}, {g})")

    # alter Lader ohne ap_tagesgrenze (andere Selbsttests): rechnet weiter, Feld null
    alt = lade([n for n in FUNKTIONEN if n != "ap_tagesgrenze"])
    w, g = alt["ap_konto_rechnen"](regel(daily_pct=3), "phase1", 96463.40, U)
    check(not g and w["sl"] == 3000 and w["tages_grenze_usd"] is None, "Lader ohne Helfer: keine Kappung, kein NameError")

    # ── Vertrag tages_grenze_usd (Text) ──
    app = open(APP, encoding="utf-8").read()
    html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
    panel = open(os.path.join(WURZEL, "mt5-copier", "panel.py"), encoding="utf-8").read()
    check('"tages_grenze_usd": w.get("tages_grenze_usd")' in app, "app.py: Planzeile trägt tages_grenze_usd")
    check('r.status_code == 400 and "tages_grenze_usd" in (r.text or "")' in app and 'if x != "tages_grenze_usd"' in app,
          "app.py: Spalte fehlt → Pläne ohne das Feld anlegen")
    check("tagesGrenzeUsd:  row.tages_grenze_usd != null ? Number(row.tages_grenze_usd) : null" in html, "PC-Tab: rowToPlan liest das Feld")
    check("tages_grenze_usd: po.tages_grenze_usd != null ? po.tages_grenze_usd : (plan.tagesGrenzeUsd" in html,
          "PC-Tab: /api/master-order (Echo V2) trägt tages_grenze_usd")
    check("tages_grenze_usd: _tg," in html and "'@tages_grenze_usd=' + (_tg != null ? _tg : '')" in html,
          "PC-Tab: /api/tv-konto (Orbit) trägt Feld + Brücken-Marke")
    check(html.count("tages_grenze_usd: order.tages_grenze_usd != null") == 2 and "tages_grenze_usd: w.tg }" in html,
          "Signale (Echo-Remote, Order-Popup, Orbit-Remote) tragen das Feld")
    check('cmd["tages_grenze_usd"] = _tg if ohne_hedge and _tg is not None and _tg >= 0 else None' in panel,
          "panel.py: master-order reicht tages_grenze_usd an den Bot (nur Echo V2)")

    print()
    print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
