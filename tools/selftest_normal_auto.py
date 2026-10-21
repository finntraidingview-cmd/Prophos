#!/usr/bin/env python3
"""Selbsttest NORMALE TRADES AUTOMATISCH ABHAKEN (Finn 14.10.2026 am Radar „Erledigt · Abhaken 8“: normale Trades ohne Blow/Bestanden
nicht mehr zeigen, selbst abhaken). app.py: ap_normal_auto_pruefen (rein rechnend), Verdrahtung im ap_loop nach ap_blow_auto_tick.
Seit 21.10.2026 (Finn: „automatisch nur, wenn NICHTS passiert ist“): Rest < 500 $, Ende nicht am TP/SL, Konto weg → Finn; zwei Schalter
(abhaken_auto_normal / abhaken_auto_blow), der alte abhaken_auto schaltet nie mehr den Blow-Takt; Tage-Mini nie mehr automatisch.
Werte frei erfunden, ohne Netz. Aufruf: python3 tools/selftest_normal_auto.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
FUNKTIONEN = ("_wd_num", "ap_groesse", "_ap_spanne", "_ap_runden", "ap_kw_param", "_ap_boden", "ap_boden_konto", "ap_kette_regel",
              "ap_regel_konto", "ap_echte_balancen", "lt_pl_balance", "lt_balance_sprung", "zw_ziel", "zw_erreicht", "ap_normal_tpsl_ende",
              "ap_normal_auto_pruefen", "ap_auto_abhaken_schalter_lesen")
KONSTANTEN = ("AP_TYPEN", "AP_KETTE_STANDARD", "AP_GROESSE_TOLERANZ", "AP_BLOW_AUTO_ROUTEN", "AP_NORMAL_AUTO_ROUTEN",
              "LT_BALANCE_SPRUNG_USD", "AP_REST_MIN", "AP_FEHLT_ZEIGEN_USD", "AP_NORMAL_TPSL_TOL", "AP_NORMAL_TPSL_MIN_USD",
              "AP_NORMAL_HAND_GRUENDE")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re}
    teile = [re.search(rf"^{k} = .*$", src, re.M).group(0) for k in KONSTANTEN]
    for name in FUNKTIONEN:
        i = src.index(f"\ndef {name}(") + 1
        teile.append(src[i:src.find("\n\n\n", i)])
    exec("\n".join(teile), ns)
    return ns, src


def main():
    ns, src = lade()
    # CFD-Firma, statischer Boden 10 % (100k → 90.000), Ziel Phase 1 +10 % (110.000), Phase 2 +5 % (105.000)
    regel = {"kauf_eur": 100, "route": "mt5v2", "boden": "statisch", "dd_pct": 10, "groessen": [100000],
             "ziel_pct": {"phase1": 10, "phase2": 5},
             "phasen": {"phase1": {"menge": [1, 1], "tp": [2000, 3000], "sl": [2000, 2500]},
                        "phase2": {"menge": [1, 1], "tp": [2000, 3000], "sl": [2000, 2500]}}}
    acc = {"id": "k1", "user_id": "u1", "firm": "TestFirma", "account_type": "phase2"}
    echo = lambda nach=101200.0, **kw: dict({"id": "p1", "route": "mt5v2", "status": "review", "blown": False, "master_account_id": "k1",
                                             "master_tp": 1000, "master_sl": 1000,
                                             "mt5_baseline": {"master_balance": 100180.0, "bal_nach": {"ok": True, "balance": nach}}}, **kw)
    orbit = lambda q="puls", nach=99500.0, **kw: dict({"id": "p2", "route": "tvv2", "status": "review", "master_account_id": "k1",
                                                      "master_tp": 1000, "master_sl": 1000,
                                                      "mt5_baseline": {"tv": {"balance_start": 100500.0},
                                                                       "final": {"quelle": q, "balance_end": nach}}}, **kw)
    pr = ns["ap_normal_auto_pruefen"]

    k = pr(echo(), acc, regel)
    check(k is not None and k["pl"] == 1020.0 and k["boden"] == 90000.0 and k["ziel"] == 105000.0 and k["ende"] == "tp",
          f"Echo V2 +1.020 $, zwischen Boden 90.000 und Ziel 105.000 → normal ({k})")
    k = pr(orbit(), acc, regel)
    check(k is not None and k["pl"] == -1000.0, "Orbit V2 −1.000 $ mit Puls-Endlesung → normal")
    check(pr(orbit("demo"), acc, regel) is None and pr(orbit("hand"), acc, regel) is None, "Demo/Hand-Ende → nie automatisch")
    check(pr(echo(105000.0), acc, regel) is None, "Ende genau auf dem Ziel → bestanden, nicht automatisch")
    check(pr(echo(104999.0, master_tp=4819), acc, regel) is None, "1 $ unter dem Ziel → „fehlen noch“ → Finn (21.10.2026)")
    check(pr(echo(90000.0), acc, regel) is None, "Ende auf dem Boden → Blow (Blow-Takt), nicht hier")
    check(pr(echo(90000.01, master_sl=10180), acc, regel) is not None, "1 Cent über dem Boden, am SL → normal")
    check(pr(echo(), dict(acc, ziel_erreicht_at="2026-10-13T10:00:00Z"), regel) is None, "Konto mit Ziel-Tag → Finn sieht es")
    mini = echo(106000.0); mini["mt5_baseline"] = dict(mini["mt5_baseline"], tage_mini={"ist": 3, "soll": 5})
    check(pr(mini, dict(acc, ziel_erreicht_at="2026-10-13T10:00:00Z"), regel) is None, "Tage-Mini auf bestandenem Konto → bestanden → Finn (seit 21.10.2026)")
    p = echo(); p["mt5_baseline"] = dict(p["mt5_baseline"], hedge={"status": "zu"})
    check(pr(p, acc, regel) is None and pr(echo(hedge_eur=120), acc, regel) is None, "mit Hedge → von Hand")
    p = echo(); p["mt5_baseline"] = dict(p["mt5_baseline"], manuell={"at": "2026-10-13T10:00:00Z", "schritt": "geparkt"})
    check(pr(p, acc, regel) is None, "Manuelle Arbeit / Review-Kennzeichen → von Hand")
    p = echo(); p["mt5_baseline"] = dict(p["mt5_baseline"], manuell=None)
    check(pr(p, acc, regel) is not None, "manuell_weg (null) zählt nicht als Kennzeichen")
    sp = orbit(nach=95000.0); sp["mt5_baseline"]["tv"].update(today_pnl_start=0.0, datum_start="2026-10-13")
    sp["mt5_baseline"]["final"].update(today_pnl=-500.0, datum="2026-10-13")
    check(pr(sp, acc, regel) is None, "Balance-Sprung (−5.500 Balance, Tages-P&L −500) → von Hand")
    check(pr(echo(status="completed"), acc, regel) is None and pr(echo(blown=True), acc, regel) is None, "nur review, nie blown")
    check(pr(echo(), dict(acc, account_type="funded"), regel) is None, "Funded → nicht automatisch")
    check(pr(echo(konto_typ="phase1"), acc, regel) is None, "Plan phase1, Konto jetzt phase2 → nicht automatisch")
    check(pr(echo(), acc, None) is None and pr(echo(), None, regel) is None, "ohne Regel/Konto → nie geraten")
    check(pr(echo(), acc, dict(regel, kette={"tagesziel": 4500})) is None, "Topstep-Kette → nicht hier")
    check(pr(dict(echo(), route="tsv2"), acc, regel) is None and pr(dict(echo(), route="mt5"), acc, regel) is None, "nur Orbit V2 / Echo V2")

    # ── 21.10.2026: nur wenn NICHTS passiert ist (Rest, TP/SL-Ende, Konto weg) ──
    check(pr(echo(104970.0, master_tp=4790), acc, regel) is None, "Rest 30 $ bis Ziel (TP getroffen) → nicht abhaken, Finn entscheidet")
    k = pr(echo(104400.0, master_tp=4200), acc, regel)
    check(k is not None and k["ende"] == "tp", f"Rest 600 $ bis Ziel, Ende am TP → abhaken ({k})")
    check(pr(echo(104500.0, master_tp=4320), acc, regel) is not None and pr(echo(104500.01, master_tp=4320), acc, regel) is None,
          "Grenze wie der Radar-Chip (rest < 500): Rest 500 $ → abhaken, 499,99 $ → „fehlen noch“")
    check(pr(echo(100580.0), acc, regel) is None, "Echo +400 $ bei TP 1.000 / SL 1.000 → von Hand geschlossen → nicht abhaken")
    check(pr(echo(101330.0), acc, regel) is not None and pr(echo(101340.0), acc, regel) is None,
          "Echo-Toleranz: +1.150 $ ≈ TP 1.000 (15 %) ja, +1.160 $ nein")
    o = orbit(nach=101500.0); o["mt5_baseline"]["final"]["grund"] = "beendet_knopf"
    check(pr(o, acc, regel) is None, "Orbit „Schließen“-Knopf (grund beendet_knopf), P&L = TP → trotzdem nicht abhaken")
    o = orbit(nach=101500.0); o["mt5_baseline"]["final"]["ende_quelle"] = "close"
    check(pr(o, acc, regel) is None, "Orbit Auto-Close/Schließen (ende_quelle close) → nicht abhaken")
    o = orbit(nach=101800.0, master_tp=None); o["mt5_baseline"]["final"]["grund"] = "demo_tp"
    check((pr(o, acc, regel) or {}).get("ende") == "tp", "Orbit Demo-Ende demo_tp mit echtem Plus → TP (Schlupf egal)")
    o = orbit(nach=99800.0); o["mt5_baseline"]["final"]["grund"] = "demo_tp"
    check(pr(o, acc, regel) is None, "demo_tp, aber echte Balance im Minus → unklar → nicht abhaken")
    o = orbit(); o["mt5_baseline"]["final"]["grund"] = "demo_liq"
    check(pr(o, acc, regel) is None, "Orbit-Ende an der Liquidation (über dem Boden = Tageslimit) → Finn")
    o = orbit(); o["mt5_baseline"]["final"]["grund"] = "demo_sl"
    check((pr(o, acc, regel) or {}).get("ende") == "sl", "Orbit demo_sl mit Minus → SL → abhaken")
    o = orbit(); o["mt5_baseline"]["final"]["konto_weg"] = True
    check(pr(o, acc, regel) is None, "Endlesung „Konto weg“ → Finn")
    o = orbit(); o["mt5_baseline"]["final"]["puls_fehler"] = "konto_nicht_erreicht: Konto nicht in der Liste"
    check(pr(o, acc, regel) is None, "Endlesung „Konto nicht erreicht“ (unklare Lesung) → Finn")
    check(pr(echo(89000.0, master_sl=11180), acc, regel) is None, "geblowt (unter dem Boden, am SL) → Normal-Takt nie")
    mini2 = echo(100190.0, master_tp=500); mini2["mt5_baseline"] = dict(mini2["mt5_baseline"], tage_mini={"ist": 2, "soll": 5})
    check(pr(mini2, acc, regel) is None, "Tage-Mini (+10 $, sofort zu — weder TP noch SL) → nicht automatisch (Finn: „genau wie ich es gesagt habe“)")

    sl_ = ns["ap_auto_abhaken_schalter_lesen"]
    check(sl_({"abhaken_auto": True}) == {"normal": True, "blow": False}, "alter Schalter abhaken_auto → nur Normal-Takt, nie Blow-Takt")
    check(sl_({"abhaken_auto_normal": True}) == {"normal": True, "blow": False}, "abhaken_auto_normal → Normal-Takt")
    check(sl_({"abhaken_auto_blow": True}) == {"normal": False, "blow": True}, "abhaken_auto_blow → nur Blow-Takt")
    check(sl_({}) == {"normal": False, "blow": False} and sl_(None) == {"normal": False, "blow": False}
          and sl_({"abhaken_auto_blow": "true", "abhaken_auto_normal": 1}) == {"normal": False, "blow": False}, "Standard aus, nur echtes true zählt")

    loop = src[src.index("\ndef ap_loop("):src.index("\ndef start_auto_planer(")]
    blk = loop[loop.index("sch = ap_auto_abhaken_an()"):loop.index('_ap_blow_auto["fehler"] = ""')]
    check('if sch["blow"]:\n                takt = ap_blow_auto_tick() is not None' in blk and blk.count("ap_blow_auto_tick(") == 1,
          "ap_loop: Blow-Takt nur unter sch[\"blow\"]")
    check('if sch["normal"]:\n                    ap_normal_auto_tick()' in blk and "ap_review_weiter_tick()" in blk,
          "ap_loop: Normal-Takt nur unter sch[\"normal\"], review-weiter immer im Takt")
    t = src[src.index("\ndef ap_normal_auto_tick("):src.index("\n# REVIEW OHNE ABHAKEN")]
    check("master_tp,master_sl" in t and "ap_blow_auto" not in t, "Normal-Takt liest master_tp/master_sl, ruft nie den Blow-Takt")
    t = src[src.index("\ndef _ap_normal_auto_abhaken("):src.index("\ndef ap_normal_auto_tick(")]
    check('"status": "eq.review", "blown": "not.is.true"' in t and 'filt["updated_at"]' in t and "_wd_erledigt_upd(" in t
          and "blown" not in t.split("upd, fehler")[1].split("filt")[0], "Abhaken: Sperre review + updated_at, gleiches Update wie der Knopf, nie blown")
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
