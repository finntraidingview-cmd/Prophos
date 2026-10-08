#!/usr/bin/env python3
"""Selbsttest Kontowert + Probelauf-Helfer des Auto-Planers (app.py, KONTOWERT, 06.10.2026) — rein rechnend, ohne Netz.

Aufruf:  python3 tools/selftest_auto_kontowert.py
Lädt die Funktionen per Quelltext aus app.py (wie selftest_liq_regeln: app.py zieht beim Import Flask und Threads).
Regeln = auto_plan_regeln.regeln.firmen nach sql/2026-10-05_auto_planer.sql + sql/2026-10-06_auto_plan_kernwerte.sql.
Prüfwerte: Finns Beispiele (FundedNext 500 € · 95k → 250 · 105k → 750, Apex 150 € · 148k → 75) und die Hedge-Ära
(Kapitel 1, Hedge-Verlust je gewonnenem Trade): Tradeify T1 −152 € (n=137), FundedNext P1 −234 € (n=105), Kosten bis
Tradeify-Funded 927 € bei Kauf ~207 € (25 Ketten)."""
import os
import random
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")

FIRMEN = [
    {"namen": ["tradeify"], "route": "tvv2", "symbol": "NQ", "groessen": [150000], "kauf_eur": 215, "dd_usd": 4500,
     "boden": "nachziehend", "ziel_pct": {"challenge": 6},
     "phasen": {"challenge": {"sl": None, "tp": [3450, 3550], "menge": [2, 3], "dd_usd": 4500, "tp_max": 3600, "ziel_pct": 6,
                              "menge_schritt": 1, "puffer_je_menge": {"2": [15, 25], "3": [25, 40]}}}},
    {"namen": ["apextrader", "apex"], "route": "tvv2", "symbol": "NQ", "groessen": [150000], "kauf_eur": 150, "dd_usd": 4000,
     "boden": "statisch", "daily_usd": 2000, "soft": True, "ziel_pct": {"challenge": 6},
     "phasen": {"challenge": {"sl": None, "tp": None, "menge": [4, 5], "puffer": [100, 100], "ziel_pct": 6, "menge_schritt": 1}}},
    {"namen": ["fundednext"], "route": "mt5v2", "groessen": [100000], "kauf_eur": {"50000": 261, "100000": 500}, "dd_pct": 10,
     "boden": "statisch", "ziel_pct": {"phase1": 8, "phase2": 5}, "wert_groessen": [50000, 100000],
     "phasen": {"phase1": {"sl": [2500, 3500], "tp": [6000, 8000], "menge": [2.1, 3.2], "puffer": [100, 100], "ziel_pct": 8,
                           "boden_pct": 10, "menge_schritt": 0.1},
                "phase2": {"sl": [2500, 3500], "tp": [6000, 8000], "menge": [2.1, 3.2], "puffer": [100, 100], "ziel_pct": 5,
                           "boden_pct": 10, "menge_schritt": 0.1}}},
    {"namen": ["the5ers"], "route": "mt5v2", "groessen": [100000, 200000], "skaliert": True,
     "kauf_eur": {"100000": 146, "200000": 226}, "dd_pct": 10, "boden": "statisch", "ziel_pct": {"phase1": 8, "phase2": 5},
     "phasen": {"phase1": {"sl": [2000, 2500], "tp": [6000, 7000], "menge": [35, 45], "puffer": [50, 75], "ziel_pct": 8,
                           "boden_pct": 10, "menge_schritt": 1}}},
    {"namen": ["topstep"], "planen": False, "route": "tvv2", "groessen": [150000], "kauf_eur": 237, "dd_usd": 4500,
     "boden": "nachziehend", "tp_max": 4500, "ziel_pct": {"challenge": 6}},
    {"namen": ["ftmo"], "planen": False, "route": "mt5v2", "groessen": [100000, 200000], "kauf_eur": 446, "dd_pct": 10,
     "boden": "statisch", "ziel_pct": {"phase1": 10, "phase2": 5}},
    {"namen": ["altefirma"], "groessen": [100000], "phasen": {"phase1": {"ziel_pct": 8}}},   # ohne Kernwerte
    # 07.10.2026 nach sql/2026-10-07_fundednext_futures_regel.sql: nachziehend mit Lock beim Start (Boden nie über 150.000)
    {"namen": ["fundednextfutures"], "route": "tvv2", "symbol": "NQ", "groessen": [150000], "kauf_eur": 258, "dd_usd": 4000,
     "boden": "nachziehend", "lock_bei_start": True, "ziel_pct": {"challenge": 5.333333333333334},
     "phasen": {"challenge": {"sl": None, "tp": [3050, 3150], "menge": [2, 3], "dd_usd": 4000, "tp_max": 3200,
                              "ziel_pct": 5.333333333333334, "menge_schritt": 1, "puffer_je_menge": {"2": [15, 25], "3": [25, 40]}}}},
]


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "random": random}

    def block(name):
        i = src.index(f"def {name}(")
        return src[i:src.find("\n\n\n", i)]

    def konst(name):
        m = re.search(rf"^{name} = .*$", src, re.M)
        return m.group(0)
    exec("\n".join([konst(k) for k in ("AP_REST_MIN", "AP_GROESSE_TOLERANZ", "AP_FENSTER_WUERFE", "_KETTE_DLL_CACHE", "AP_KW_FUNDED", "AP_KW_PHASEN", "AP_START_BIS_STANDARD", "AP_CFD_AB_STANDARD", "AP_ABSTAND_ID_FIRMA_MIN", "AP_ABSTAND_ID_MIN", "AP_ABSTAND_STUFEN", "AP_GROSS_NAH_MIN", "AP_FIRMA_ABSTAND_MIN", "AP_KETTE_STANDARD", "AP_KETTE_TXT")] + [block(f) for f in (
        "_ap_norm", "ap_regel_finden", "ap_groesse", "_ap_spanne", "_ap_runden", "_ap_boden", "ap_kette_regel", "ap_kette_mll", "ap_kette_trade1", "ap_konto_rechnen", "ap_start_bis", "ap_cfd_ab", "ap_zeiten_verteilen", "_ap_zeiten_verteilen_einmal",
        "ap_kw_param", "_ap_kw_kauf", "_ap_kw_wachsen", "_ap_kw_lock", "kette_dll_chance", "ap_kontowert", "ap_trade_gewicht", "ap_sicht", "_ap_hhmm")]), ns)
    return ns


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("✓ " if bed else "✗ ") + text)
        ok = ok and bool(bed)

    regel = lambda firm: a["ap_regel_finden"](FIRMEN, firm)
    P = lambda firm: a["ap_kw_param"](regel(firm))
    W = lambda firm, typ, bal, kauf=None: a["ap_kontowert"](typ, bal, P(firm), kauf)
    nahe = lambda x, soll, tol: abs(x - soll) <= tol

    # 1) Finns Prüfbeispiele (06.10.2026)
    check(W("FundedNext", "phase1", 95000)["wert"] == 250, "FundedNext P1 500 € · 95.000 → 250 €")
    check(W("FundedNext", "phase1", 105000)["wert"] == 750, "FundedNext P1 500 € · 105.000 → 750 €")
    check(W("Apex Trader", "challenge", 148000)["wert"] == 75, "Apex 150 € · 148.000 → 75 €")
    check(W("Apex Trader", "challenge", 145900)["wert"] == 0, "Apex unter Boden 146.000 → 0 €")

    # 2) Tradeify-Treppe (Kauf 215): Etappen 3.600/3.600/1.800 gegen 4.500 nachziehend
    t = [W("Tradeify", "challenge", b)["wert"] for b in (150000, 153600, 157200, 159000)]
    check(t == [215, 387, 697, 975], f"Tradeify 215 → 387 → 697 → 975 (ist {t})")
    check(nahe(975 * 207 / 215, 927, 40), "Kosten bis Funded ≈ gemessen 927 € (Kauf 207, 25 Ketten)")
    t1 = W("Tradeify", "challenge", 150000)["satz"] * 3390
    check(nahe(t1 * 207 / 215, 152, 152 * 0.15), f"Tradeify T1 Hedge {t1 * 207 / 215:.0f} € ≈ gemessen 152 € (±15 %)")
    check(W("Tradeify", "challenge", 147000)["wert"] == round(215 * 1500 / 4500), "Tradeify unter Start: Polster schrumpft")
    fd = W("Tradeify", "funded", 150000)
    check(fd["wert"] == 975 and nahe(fd["satz"], 0.2167, 0.001), "Tradeify Funded = bestanden 975 €, Satz ≈ 0,217 €/$ (Finn: 1.000/4.500)")
    check(nahe(W("Tradeify", "winning_days", 164500)["wert"], 975 / 4500 * (14500 + 4500), 2), "Tradeify WD nach Big Trade +14.500 ≈ 4.118 €")

    # 3) CFD-Phasen + Messung
    fn1 = W("FundedNext", "phase1", 100000)
    check(nahe(fn1["satz"] * 4391, 234, 234 * 0.15), f"FundedNext P1 Etappe 4.391 $ → {fn1['satz'] * 4391:.0f} € ≈ gemessen 234 €")
    check(W("FundedNext", "phase2", 100000)["wert"] == 900, "FundedNext P2-Start = Wert am P1-Ziel 900 €")
    check(W("FundedNext", "funded_cfd", 100000)["wert"] == 1350, "FundedNext Funded = 1.350 €")
    check(W("FundedNext", "phase1", 48000)["wert"] == round(261 * 3000 / 5000), "FundedNext 50k (wert_groessen) 48.000 → 157 €")
    check(W("The5%ers", "phase1", 200000)["wert"] == 226 and W("The5ers", "phase1", 100000)["wert"] == 146, "The5ers Kauf je Größe")
    check(W("FundedNext", "phase1", 100000, kauf=480)["wert"] == 480, "echter Kauf hat Vorrang")
    check(W("Topstep", "winning_days", 13489, kauf=2986)["wert"] == W("Topstep", "winning_days", 13489)["wert"],
          "unplausibler Kauf (2.986 € an Topstep-WD = Gebühr/Sammelbuchung) → Firmenwert")

    # 4) planen:false-Firmen haben Werte, ohne Kernwerte kein Wert
    ts = W("Topstep", "winning_days", 13489)
    check(ts and ts["wert"] == round(237 * 4 * (13489 + 4500) / 4500), f"Topstep Express ab 0: WD 13.489 → {ts and ts['wert']} €")
    check(W("Topstep", "phase1", 154500)["wert"] == 474, "Topstep als phase1 geführt → erste Phase (Combine Tag 1 = 474 €)")
    check(W("FTMO", "phase1", 100000)["wert"] == 446 and W("FTMO", "phase2", 100000)["wert"] == 892, "FTMO P1 446 → P2 892")
    check(a["ap_kw_param"](regel("AlteFirma")) is None, "Firma ohne Kernwerte → kein Wert")
    check(W("Tradeify", "challenge", 120000) is None, "Größe passt nicht → kein Wert")

    # 5) Gewicht im Ausgleich
    g = a["ap_trade_gewicht"](W("Tradeify", "challenge", 153600), P("Tradeify"), 3600, None)
    check(g["verlust_eur"] == 387 and g["gewinn_eur"] == round(387 / 4500 * 3600), "Tradeify ohne SL: Verlust = ganzer Wert")
    kw = W("Apex Trader", "challenge", 150000)
    g = a["ap_trade_gewicht"](kw, P("Apex Trader"), 9100, None)
    check(g["verlust_eur"] == round(150 / 4000 * 2000), "Apex ohne SL: Verlust = Satz × Daily 2.000 (Soft Breach)")
    g = a["ap_trade_gewicht"](W("FundedNext", "phase1", 102463), P("FundedNext"), 3000, 2800)
    check(g["gewinn_eur"] == 150 and g["verlust_eur"] == 140 and g["gewicht_eur"] == 145, "FundedNext 3.000/2.800 → +150/−140")
    check(a["ap_trade_gewicht"](None, None, 1, 1) is None, "ohne Wert kein Gewicht")

    # 6) Planer: Ziel/Boden aus den Kernwerten — gleiche Zahlen wie vorher aus phasen{}
    u = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}
    w, grund = a["ap_konto_rechnen"](regel("FundedNext"), "phase2", 104617, u)
    check(not grund and w["rest"] == 383 and w["tp"] == 483, "FundedNext P2 104.617: Rest 383, TP 483 (wie Nachtlauf 06.10.)")
    w, grund = a["ap_konto_rechnen"](regel("FundedNext"), "phase1", 89000, u)
    check(grund and "Boden" in grund, "FundedNext unter Boden (dd_pct) → ausgelassen")
    w, grund = a["ap_konto_rechnen"](regel("Tradeify"), "challenge", 153600, u)
    check(not grund and w["ziel"] == 159000, "Tradeify Ziel 159.000 aus ziel_pct")

    # 6b) FundedNext Futures (Finn 07.10.2026): Kauf 258, DD 4.000 nachziehend mit Lock bei 150.000, Ziel +8.000 in 3.200er Etappen
    check(regel("FundedNext Futures")["namen"] == ["fundednextfutures"] and regel("FundedNext")["namen"] == ["fundednext"],
          "„FundedNext Futures\" ≠ „FundedNext\" (eigene Regel)")
    f = [W("FundedNext Futures", "challenge", b) for b in (150000, 153200, 156400, 157200, 158000)]
    check(f[0]["wert"] == 258 and f[0]["polster"] == 4000, "FN Futures frisch = 258 €, Polster 4.000")
    check(f[1]["wert"] == round(258 * 1.8) and f[1]["polster"] == 4000, f"FN Futures +3.200 → 258 × 1,8 = {f[1]['wert']} € (Boden 149.200)")
    wl = 258 * 1.8 * 1.8
    check(f[2]["wert"] == round(wl) and f[2]["polster"] == 6400, f"FN Futures +6.400 → Lock: {f[2]['wert']} €, Polster 6.400 (Boden 150.000)")
    check(f[3]["wert"] == round(wl * 7200 / 6400) and f[4]["wert"] == round(wl * 8000 / 6400),
          f"FN Futures nach Lock statisch: 157.200 → {f[3]['wert']} €, 158.000 → {f[4]['wert']} €")
    check(nahe(f[2]["satz"], f[4]["satz"], 1e-4), "FN Futures nach Lock: Satz r bleibt (statisch)")
    check(W("FundedNext Futures", "challenge", 148000)["wert"] == round(258 * 2000 / 4000), "FN Futures unter Start: Polster schrumpft")
    check(W("FundedNext Futures", "funded", 150000)["wert"] == round(wl * 8000 / 6400), "FN Futures Funded-Start = Wert am Ziel")
    check(W("Tradeify", "challenge", 157200)["wert"] == 697 and "lock_bei_start" in P("Tradeify") and not P("Tradeify")["lock_bei_start"],
          "Tradeify ohne Lock unverändert")
    et = []
    for b in (150000, 153100, 156200):
        w, grund = a["ap_konto_rechnen"](regel("FundedNext Futures"), "challenge", b, u)
        et.append((w["tp"], w["stufe"]) if w else grund)
    check(et[0][0] == 3100 and et[1][0] == 3100 and et[2][1].startswith("letzter Trade"),
          f"FN Futures Planer: Etappe 3.100 · 3.100 · Rest (ist {et})")
    w, grund = a["ap_konto_rechnen"](regel("FundedNext Futures"), "challenge", 146000, u)
    check(grund and "Boden" in grund, "FN Futures auf Boden 146.000 → ausgelassen")
    w, grund = a["ap_konto_rechnen"](regel("FundedNext Futures"), "challenge", 157990, u)
    check(grund and "Ziel erreicht" in grund, "FN Futures 10 $ vor Ziel → Ziel erreicht (Futures-Challenge, Rest < 100, 07.10.2026)")
    # 07.10.2026 (Finn: nur Konten auf Live-Stand, geblasene/fertige raus): Boden aus dd_usd, Futures-Challenge Rest < 100 = Ziel
    w, grund = a["ap_konto_rechnen"](regel("Apex Trader"), "challenge", 146000, u)
    check(grund and "Boden" in grund, "Apex 146.000 = Boden (statisch 150k − 4.000) → geblowt?")
    w, grund = a["ap_konto_rechnen"](regel("Apex Trader"), "challenge", 146500, u)
    check(w and not grund, "Apex 146.500 über dem Boden → wird geplant")
    w, grund = a["ap_konto_rechnen"](regel("Tradeify"), "challenge", 145400, u)
    check(grund and "Boden" in grund, "Tradeify 145.400 ≤ Start − 4.500 → geblowt?")
    w, grund = a["ap_konto_rechnen"](regel("Tradeify"), "challenge", 146000, u)
    check(w and not grund and w["sl"] is None, "Tradeify 146.000 → geplant, SL bleibt ungekappt (keiner)")
    w, grund = a["ap_konto_rechnen"](regel("Tradeify"), "challenge", 158950, u)
    check(grund and "Ziel erreicht" in grund, "Tradeify 50 $ vor 159.000 → Ziel erreicht – Phase umstellen")
    w, grund = a["ap_konto_rechnen"](regel("FundedNext"), "phase1", 107950, u)
    check(grund and "Hand" in grund, "CFD Phase 1 50 $ vor Ziel → weiter „von Hand prüfen“")
    w, grund = a["ap_konto_rechnen"](regel("FundedNext"), "phase1", 89000, u)
    check(grund and "Boden" in grund, "CFD unter Start × (1 − dd_pct) → geblowt?")
    w, grund = a["ap_konto_rechnen"](regel("FundedNext Futures"), "challenge", 158000, u)
    check(grund and "Ziel erreicht" in grund, "FN Futures 158.000 = Ziel erreicht")

    # 7) Zeitverteilung: info ändert nichts am Ergebnis (Probelauf = Nachtlauf bei gleichem seed)
    tr = [{"key": f"u{i}|f{i % 3}", "user": f"u{i % 4}", "firma": f"f{i % 3}", "dauer_min": 3} for i in range(9)]
    zeiten = {"fenster": [["02:00", "14:00", 37], ["14:00", "15:30", 25], ["15:30", "16:30", 18], ["16:30", "17:30", 20]]}
    info = {}
    m1 = a["ap_zeiten_verteilen"](tr, zeiten, random.Random(42), 0)
    m2 = a["ap_zeiten_verteilen"](tr, zeiten, random.Random(42), 0, info=info)
    check(m1 == m2 and set(info) == set(m2), "seed gleich → gleiche Startzeiten, info je Tranche")

    # 8) Sicht: Nicht-Admin bekommt nur die eigenen Zeilen, Summen bleiben
    erg = {"geplant": [{"user_id": "A"}, {"user_id": "B"}], "ausgelassen": [{"user_id": "B"}], "tranchen": [{"user_id": "A"}],
           "ausgleich": {"offen_long_eur": 500, "offen": [{"user_id": "B"}, {"user_id": "A"}]}}
    s = a["ap_sicht"](erg, "A")
    check(len(s["geplant"]) == 1 and not s["ausgelassen"] and len(s["ausgleich"]["offen"]) == 1
          and s["ausgleich"]["offen_long_eur"] == 500 and s["sicht"] == "eigene", "ap_sicht filtert Listen, Summen bleiben")

    print("ALLES OK" if ok else "FEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
