#!/usr/bin/env python3
"""Selbsttest RV1 „Range-Würfel“ im Challenge-Planer CFD (Finn 11.11.2026 07:35 über den Master: „75 % der Trades bleiben gleich, und nur bei 25 % der Trades
wird's angepasst … Stop Loss, Take Profit und Lotanzahl, alles drei … für alle drei wird einzeln gewürfelt“). Konstrukt: side-session-notes
2026-11-11_RV1_range_wuerfel_konstrukt.md.

Rechnet die REIN RECHNENDEN Funktionen aus app.py ohne Netz/DB (Muster selftest_ff2_pump.py): rv_faktoren, rv_anwenden, rv_planer_haken mit den echten
Phasen-Werten aus auto_plan_regeln (Stand 11.11.2026, nur gelesen) und ap_konto_rechnen. Feste Zahlenbeispiele FundedNext / The5%ers / FTMO + Zufalls-Prüfung
(je Lauf neue Zufallszahlen — 20 Läufe = 20 verschiedene Stichproben). Platzhalter-Konten, keine echten Kennungen.

Aufruf:  python3 tools/selftest_rv1_range_wuerfel.py"""
import hashlib
import os
import random
import re
import sys
from datetime import datetime, timezone, timedelta

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.environ.get("SELFTEST_APP") or os.path.join(W, "app.py"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "random": random, "hashlib": hashlib}


def lade(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^\S)", app, re.S | re.M)
    if not m:
        raise LookupError(name)
    exec(m.group(0), ns)


def ruf(fn, *a, **k):
    for _ in range(80):
        try:
            return ns[fn](*a, **k)
        except NameError as e:
            lade(str(e).split("'")[1])
    raise RuntimeError(fn)


for n in ("RV_MIN_PKT", "RV_STANDARD", "RV_STUFE", "AP_SL_HINTER_BODEN", "AP_TAGES_PUFFER", "AP_CFD_ROUTEN",   # Konstanten zuerst (Standard-Argumente)
          "RV_FINAL_RE", "rv_wurf", "rv_faktoren", "rv_punkte_deckel", "rv_anwenden", "_ap_runden", "_ap_spanne", "rv_einstellung", "rv_planer_haken", "fest_wurf", "tw_wurf", "_wd_num", "ap_konto_rechnen", "ap_plan_final_text",
          "ap_klein_normal", "ap_tagesgrenze", "eh_hedge", "TT_EIN_TRADE_STUFE", "AP_PUFFER_PKT"):
    try:
        lade(n)
    except LookupError:
        print(f"✗ fehlt: {n} (app.py)")
        sys.exit(1)

# ── Phasen-Werte aus auto_plan_regeln (DB-Lesung 11.11.2026), Punktwerte aus firm_specs ──
FN = {"namen": ["fundednext"], "route": "mt5v2", "dd_pct": 10, "boden": "statisch", "groessen": [50000, 100000], "ziel_pct": {"phase1": 8, "phase2": 5},
      "phasen": {"phase1": {"sl": [2250, 3150], "tp": [5400, 7200], "menge": [2.1, 3.2], "puffer": [25, 50], "ziel_pct": 8, "boden_pct": 10, "menge_schritt": 0.1},
                 "phase2": {"sl": [2250, 3150], "tp": [5400, 7200], "menge": [2.1, 3.2], "puffer": [25, 50], "ziel_pct": 5, "boden_pct": 10, "menge_schritt": 0.1}}}
T5 = {"namen": ["the5ers"], "route": "mt5v2", "dd_pct": 10, "boden": "statisch", "groessen": [100000, 200000], "skaliert": True,
      "phasen": {"phase1": {"sl": [1800, 2160], "tp": [5400, 6300], "menge": [20, 30], "puffer": [25, 50], "ziel_pct": 8, "boden_pct": 10, "menge_schritt": 1}}}
FT = {"namen": ["ftmo"], "route": "mt5v2", "dd_pct": 10, "boden": "statisch", "groessen": [100000, 200000],
      "phasen": {"phase1": {"sl": [2070, 2475], "tp": [4500, 7200], "menge": [25, 35], "puffer": [25, 50], "ziel_pct": 10, "boden_pct": 10, "menge_schritt": 1}}}
PPL = {"fn": 10.0, "t5": 1.0, "ft": 1.0}
MITTE = {"tp": 0.5, "sl": 0.5, "menge": 0.5, "puffer": 0.5}


def normal(regel, bal, u=MITTE, phase="phase1", ppl=10.0):
    w, g = ruf("ap_konto_rechnen", regel, phase, bal, dict(u), ppl=ppl)
    assert w and not g, g
    return w


def fk(tp, sl, lots, regel=None, ppl=None, gr=100000.0):
    d = {"f_tp": tp, "f_sl": sl, "f_lots": lots, "pct": 25, "von": 10, "bis": 100}
    if regel:
        d["tp_max_pkt"], d["sl_max_pkt"] = ruf("rv_punkte_deckel", regel, "phase1", gr, ppl)
    return d


MIN = ns["RV_MIN_PKT"]

print("── 1. Würfel: Anteil, Spanne, fest, unabhängig ──")
check(ruf("rv_faktoren", "challenge_cfd", "konto-a", "2026-11-12", None) is None, "kein Wert → normaler Trade")
check(ruf("rv_faktoren", "challenge_cfd", "konto-a", "2026-11-12", 0) is None, "0 % → normaler Trade")
check(ruf("rv_faktoren", "challenge_cfd", "", "2026-11-12", 100) is None, "ohne Konto-ID → normaler Trade")
f100 = ruf("rv_faktoren", "challenge_cfd", "konto-a", "2026-11-12", 100)
check(bool(f100) and all(0.1 <= f100[x] <= 1.0 for x in ("f_tp", "f_sl", "f_lots")), f"100 % → immer klein, Faktoren 0,1–1,0 ({f100})")
check(ruf("rv_faktoren", "challenge_cfd", "konto-a", "2026-11-12", 100) == f100, "fest: gleiches Konto × Tag → gleiche Faktoren")
check(ruf("rv_faktoren", "challenge_cfd", "konto-a", "2026-11-12T08:00:00", 100) == f100, "Tag aus Zeitstempel (erste 10 Zeichen) → gleicher Wurf")
fv = ruf("rv_faktoren", "challenge_cfd", "konto-a", "2026-11-12", 100, 150, -5)
check(fv["von"] == 1.0 and fv["bis"] == 100.0, f"Spanne auf 1–100 begrenzt und sortiert ({fv['von']}–{fv['bis']})")
fe = ruf("rv_faktoren", "challenge_cfd", "konto-a", "2026-11-12", 100, 40, 40)
check(fe["f_tp"] == fe["f_sl"] == fe["f_lots"] == 0.4, "von = bis → genau dieser Faktor")
n, klein, tw_n, beide, gleich, fs = 0, 0, 0, 0, 0, []
for i in range(3000):
    kid, tag = f"konto-{i % 300}", f"2026-11-{10 + i // 300:02d}"
    f = ruf("rv_faktoren", "challenge_cfd", kid, tag, 25)
    n += 1
    handelt = ruf("tw_wurf", "challenge_cfd", kid, tag) * 100 < 75
    tw_n += handelt
    if f:
        klein += 1
        beide += handelt
        fs.append(f)
        gleich += f["f_tp"] == f["f_sl"] == f["f_lots"]
anteil = klein / n * 100
check(21 <= anteil <= 29, f"25 % eingestellt → {anteil:.1f} % klein (3.000 Konto-Tage)")
check(abs(beide / max(1, klein) * 100 - tw_n / n * 100) < 6, f"unabhängig vom Handels-Würfel: unter den kleinen handeln {beide / max(1, klein) * 100:.1f} % (alle {tw_n / n * 100:.1f} %)")
check(all(0.1 <= x[k] <= 1.0 for x in fs for k in ("f_tp", "f_sl", "f_lots")), "alle Faktoren in 10–100 %")
check(gleich == 0, "drei Faktoren einzeln gewürfelt (nie alle drei gleich)")
_m = lambda xs: sum(xs) / len(xs)   # noqa: E731
_kov = _m([x["f_tp"] * x["f_sl"] for x in fs]) - _m([x["f_tp"] for x in fs]) * _m([x["f_sl"] for x in fs])
_sd = (_m([x["f_tp"] ** 2 for x in fs]) - _m([x["f_tp"] for x in fs]) ** 2) ** 0.5 * (_m([x["f_sl"] ** 2 for x in fs]) - _m([x["f_sl"] for x in fs]) ** 2) ** 0.5
check(abs(_kov / _sd) < 0.12, f"TP- und SL-Faktor unkorreliert (r = {_kov / _sd:+.3f})")
check(0.5 < _m([x["f_lots"] for x in fs]) < 0.6, f"Faktor im Mittel ≈ 55 % ({_m([x['f_lots'] for x in fs]):.3f})")

print("── 2. Zahlenbeispiele (Normal-Trade = Spannen-Mitte, Punkte-Deckel = normaler Trade bei maximaler Spanne) ──")
dk = {n: ruf("rv_punkte_deckel", r, "phase1", 100000.0, pv) for n, r, pv in (("fn", FN, 10.0), ("t5", T5, 1.0), ("ft", FT, 1.0))}
check(dk["fn"] == (342.86, 150.0), f"Deckel FundedNext 100k: TP 7.200 ÷ (2,1 × 10) = 342,86 Pkt, SL 3.150 ÷ 21 = 150 Pkt ({dk['fn']})")
check(dk["t5"] == (315.0, 108.0) and dk["ft"] == (288.0, 99.0), f"Deckel The5%ers 315 / 108 Pkt, FTMO 288 / 99 Pkt ({dk['t5']}, {dk['ft']})")
check(ruf("rv_punkte_deckel", T5, "phase1", 200000.0, 1.0) == (315.0, 108.0), "The5%ers 200k (skaliert ×2): Deckel in Punkten gleich")
check(ruf("rv_punkte_deckel", FN, "phase1", 100000.0, None) == (None, None), "ohne Punktwert → kein Deckel")
w = normal(FN, 100000.0, ppl=PPL["fn"])
check((w["menge"], w["tp"], w["sl"], w["stufe"]) == (2.7, 6300, 2700, "Etappe"), f"FundedNext Ph1 100k normal: 2,7 Lots · TP 6.300 · SL 2.700 ({w['menge']}, {w['tp']}, {w['sl']})")
a = ruf("rv_anwenden", w, fk(0.2, 0.9, 0.5, FN, 10.0), 0.1, PPL["fn"])
check((a["menge"], a["tp"], a["sl"], a["risiko"]) == (1.3, 1260, 1950, 1950) and a["range"]["sl_geklemmt"] == "max",
      f"FN TP 20 / SL 90 / Lots 50 % → 1,35 abgerundet 1,3 Lots · TP 1.260 · SL 2.430 wären 187 Pkt > 150 → 1.950 ({a['menge']}, {a['tp']}, {a['sl']})")
check(a["range"]["tp_pkt"] == 96.9 and a["range"]["sl_pkt"] == 150.0, f"   Punkte: TP 96,9 / SL 150 ({a['range']['tp_pkt']} / {a['range']['sl_pkt']})")
check(a["stufe"] == "Etappe · Range-Würfel TP 20 % · SL 72 % · Lots 48 %", f"   Stufe zeigt die wirklichen Anteile: {a['stufe']}")
b = ruf("rv_anwenden", w, fk(1.0, 0.1, 0.1, FN, 10.0), 0.1, PPL["fn"])
check((b["menge"], b["tp"], b["sl"]) == (0.2, 685, 270) and b["range"]["tp_geklemmt"] == "max",
      f"FN TP 100 / SL 10 / Lots 10 % → 0,2 Lots · TP 6.300 wären 3.150 Pkt → 342,86 Pkt = 685 $ · SL 270 ({b['menge']}, {b['tp']}, {b['sl']})")
w5 = normal(T5, 100000.0, ppl=PPL["t5"])
check((w5["menge"], w5["tp"], w5["sl"]) == (25, 5850, 1980), f"The5%ers 100k normal: 25 Lots · TP 5.850 · SL 1.980 ({w5['menge']}, {w5['tp']}, {w5['sl']})")
c = ruf("rv_anwenden", w5, fk(0.1, 0.1, 1.0, T5, 1.0), 1, PPL["t5"])
check((c["menge"], c["tp"], c["sl"]) == (25, 585, 250) and c["range"]["sl_geklemmt"] == "min" and c["range"]["tp_geklemmt"] is None,
      f"The5%ers TP 10 / SL 10 / Lots 100 % → SL 198 $ wären 7,9 Pkt → auf 10 Pkt = 250 $ angehoben ({c['menge']}, {c['tp']}, {c['sl']})")
c2 = ruf("rv_anwenden", w5, fk(0.5, 0.5, 0.13, T5, 1.0), 1, PPL["t5"])
check((c2["menge"], c2["tp"], c2["sl"]) == (3, 945, 324) and isinstance(c2["menge"], int),
      f"The5%ers 50/50/13 % → 3 Lots (Raster 1) · TP 2.925 → 315 Pkt = 945 $ · SL 990 → 108 Pkt = 324 $ ({c2['menge']!r}, {c2['tp']}, {c2['sl']})")
wf = normal(FT, 100000.0, ppl=PPL["ft"])
check((wf["menge"], wf["tp"], wf["sl"]) == (30, 5850, 2272), f"FTMO 100k normal: 30 Lots · TP 5.850 · SL 2.272 ({wf['menge']}, {wf['tp']}, {wf['sl']})")
d = ruf("rv_anwenden", wf, fk(0.5, 0.5, 0.5, FT, 1.0), 1, PPL["ft"])
check((d["menge"], d["tp"], d["sl"]) == (15, 2925, 1136), f"FTMO alle 50 % → 15 Lots · TP 2.925 (195 Pkt) · SL 1.136 (75,7 Pkt) ({d['menge']}, {d['tp']}, {d['sl']})")
d2 = ruf("rv_anwenden", wf, fk(0.1, 0.1, 0.01, FT, 1.0), 1, PPL["ft"])
check((d2["menge"], d2["tp"], d2["sl"]) == (1, 288, 99), f"FTMO Lots 1 % → mindestens 1 Lot · TP/SL auf 288 / 99 Pkt geklemmt ({d2['menge']}, {d2['tp']}, {d2['sl']})")

print("── 3. Nur die Etappe, Boden, Hedge ──")
wl = normal(FN, 106000.0, ppl=PPL["fn"])
l1 = ruf("rv_anwenden", wl, fk(0.5, 0.6, 0.7, FN, 10.0), 0.1, PPL["fn"])
check(wl["stufe"] == "letzter Trade (Rest bis Ziel)" and l1["tp"] < wl["rest"] and l1["stufe"].startswith("Etappe · Range-Würfel") and l1["stufe"].endswith("(Ziel erst später)")
      and l1["range"]["statt_letzter"], f"letzter Trade klein, TP {l1['tp']} < Rest {wl['rest']} → „Etappe … (Ziel erst später)“ ({l1['stufe']})")
check(not ns["TT_EIN_TRADE_STUFE"].search(l1["stufe"]) and ns["TT_EIN_TRADE_STUFE"].search(wl["stufe"]),
      "Prüfer-MUSS: kleiner letzter Trade ist für Trades pro Tag eine Etappe (TT_EIN_TRADE_STUFE trifft nicht), der normale bleibt Ein-Trade")
_pf = round(ns["AP_PUFFER_PKT"] * 2.7 * 10.0 / 3)
for _ft, _soll in ((round((wl["rest"] + 5) / wl["tp"], 4), True), (round((wl["rest"] + _pf + 2) / wl["tp"], 4), False)):
    _l = ruf("rv_anwenden", wl, fk(_ft, 0.5, 1.0, FN, 10.0), 0.1, PPL["fn"])
    check(_l["range"]["statt_letzter"] is _soll, f"Prüfer-SOLL Puffer: TP {_l['tp']} bei Rest {wl['rest']} + Puffer {_pf:.0f} → {'kein' if _soll else 'weiter'} letzter Trade")
l2 = ruf("rv_anwenden", wl, fk(1.0, 0.5, 1.0, FN, 10.0), 0.1, PPL["fn"])
check(l2["tp"] >= wl["rest"] and l2["stufe"].startswith("letzter Trade (Rest bis Ziel) · Range-Würfel"), f"TP erreicht das Ziel noch → bleibt letzter Trade ({l2['tp']}, {l2['stufe']})")
nf = ns["ap_plan_final_text"]
_notiz = lambda st, rest: f"Auto-Planer · {st} · Rest {rest:,} $ bis Ziel · Balance 106.000".replace(",", ".")   # noqa: E731
check(nf(_notiz(wl["stufe"], wl["rest"]), wl["tp"]) is True and nf(_notiz(l1["stufe"], wl["rest"]), l1["tp"]) is False,
      "ap_plan_final_text: normaler letzter Trade final, kleiner (statt letzter Trade) nicht final")
wk, _g = ruf("ap_konto_rechnen", FN, "phase1", 107950.0, dict(MITTE), ppl=PPL["fn"])
check(bool(wk) and ruf("rv_anwenden", wk, fk(0.1, 0.1, 0.1), 0.1, PPL["fn"]) is wk, f"Klein-Trade bleibt ({(wk or {}).get('stufe')})")
check(ruf("rv_anwenden", w, None, 0.1, PPL["fn"]) is w and ruf("rv_anwenden", w, fk(0.5, 0.5, 0.5), 0.1, None) is w, "ohne Faktoren / ohne Punktwert → unverändert")
wb = normal(FN, 91500.0, ppl=PPL["fn"])
hb = f", SL hinter den Boden (+{ns['AP_SL_HINTER_BODEN']} $)"
check(wb["sl"] == 1550 and hb in wb["stufe"], f"FN 91.500: SL hinter den Boden 1.550 ({wb['sl']}, {wb['stufe']})")
e1 = ruf("rv_anwenden", wb, fk(0.5, 0.5, 0.5), 0.1, PPL["fn"])
check(e1["sl"] == 775 and hb not in e1["stufe"], f"SL 50 % = 775 liegt vor dem Boden → Zusatz „hinter den Boden“ weg ({e1['stufe']})")
e2 = ruf("rv_anwenden", wb, fk(0.5, 0.99, 0.5), 0.1, PPL["fn"])
check(e2["sl"] > 1500 and hb in e2["stufe"], f"SL 99 % = {e2['sl']} weiter hinter dem Boden → Zusatz bleibt")
e3 = ruf("rv_anwenden", wb, fk(0.5, 1500 / 1550, 0.5), 0.1, PPL["fn"])
check(e3["sl"] == 1500 and hb in e3["stufe"], f"Prüfer-SOLL: SL genau auf dem Boden (1.500) → Zusatz bleibt (Blow-Abgleich) ({e3['sl']})")
# (d) Fusion-Hedge folgt dem Master: Lots ∝ Master-Lots, slave_risk ∝ Master-SL (Multiplier aus Plänen der letzten 5 Tage: The5%ers 0,0082, FN 0,28)
for name, mult, wn, an in (("The5%ers", 0.0082, w5, ruf("rv_anwenden", w5, fk(0.3, 1.0, 0.1, T5, 1.0), 1, 1.0)), ("FundedNext", 0.28, w, b)):
    hn, _ = ruf("eh_hedge", mult, wn["menge"], 1.0, 1.0, wn["sl"], 1.0, 0.01)
    hk, gk = ruf("eh_hedge", mult, an["menge"], 1.0, 1.0, an["sl"], 1.0, 0.01)
    check(hk is not None and hk["lots"] >= 0.01, f"{name}: kleinster Trade {an['menge']} Lots → Hedge {hk and hk['lots']} Lot ≥ 0,01 ({gk or 'ok'})")
    check(hk and abs(hk["lots"] - mult * an["menge"]) <= 0.005 and abs(hk["slave_risk"] - mult * an["sl"]) < 0.01,
          f"{name}: Hedge {hn['lots']} → {hk and hk['lots']} Lot, Slave-Risiko {hn['slave_risk']} → {hk and hk['slave_risk']} (folgt Lots und SL)")

print("── 4. Planer-Haken: nur Echo-CFD-Challenge, Einstellung je Unternehmen ──")
KTX = {"ok": True, "gid_von": {"uid-emin": "gid-emin"}}
WERTE = {("challenge_cfd", ""): {"pct": 100.0, "von": 10.0, "bis": 100.0}}
a_ht = {"id": "konto-ht", "user_id": "uid-ht", "account_type": "phase1"}
h1 = ruf("rv_planer_haken", w, a_ht, FN, "2026-11-12", PPL["fn"], WERTE, KTX)
fx = ruf("rv_faktoren", "challenge_cfd", "konto-ht", "2026-11-12", 100, 10, 100)
check(h1 is not w and h1["range"]["f_tp"] == fx["f_tp"] and h1["menge"] <= w["menge"], f"HT 100 % → klein mit den Konto-Faktoren ({h1['stufe']})")
check((h1["range"]["tp_max_pkt"], h1["range"]["sl_max_pkt"]) == dk["fn"], f"Punkte-Deckel im Beleg (für den Folge-Haupt) {h1['range']['tp_max_pkt']} / {h1['range']['sl_max_pkt']}")
check(ruf("rv_planer_haken", w, dict(a_ht, user_id="uid-emin"), FN, "2026-11-12", PPL["fn"], WERTE, KTX) is w, "Unternehmen ohne eigene Zeile → aus (erbt HT nicht)")
check(ruf("rv_planer_haken", w, dict(a_ht, account_type="challenge"), FN, "2026-11-12", PPL["fn"], WERTE, KTX) is w, "Futures-Challenge (Kontoart challenge) → unverändert")
check(ruf("rv_planer_haken", w, a_ht, dict(FN, route="tvv2"), "2026-11-12", PPL["fn"], WERTE, KTX) is w, "Route Orbit (tvv2) → unverändert")
check(ruf("rv_planer_haken", w, a_ht, FN, "2026-11-12", PPL["fn"], {}, KTX) is w, "Tabelle leer/fehlt → aus")
check(ruf("rv_planer_haken", w, a_ht, FN, "2026-11-12", PPL["fn"], WERTE, {"ok": False}) is w, "Unternehmens-Kontext nicht lesbar → aus")
w50 = dict(normal(dict(FN, je_groesse={"50000": {"phasen": {"phase1": dict(FN["phasen"]["phase1"], menge=[1, 1.5], menge_schritt=0.5)}}}), 50000.0, ppl=PPL["fn"]))
h50 = ruf("rv_planer_haken", w50, a_ht, dict(FN, je_groesse={"50000": {"phasen": {"phase1": dict(FN["phasen"]["phase1"], menge=[1, 1.5], menge_schritt=0.5)}}}),
          "2026-11-12", PPL["fn"], WERTE, KTX)
check(abs(h50["menge"] / 0.5 - round(h50["menge"] / 0.5)) < 1e-9, f"Raster je Kontogröße (je_groesse 50k, Schritt 0,5) → {h50['menge']} Lots")
_jg1 = {"50000": {"phasen": {"phase1": {k: v for k, v in dict(FN["phasen"]["phase1"], menge=[2, 3]).items() if k != "menge_schritt"}}}}
_w1 = normal(dict(FN, je_groesse=_jg1), 50000.0, ppl=PPL["fn"])
_h1 = ruf("rv_planer_haken", _w1, a_ht, dict(FN, je_groesse=_jg1), "2026-11-12", PPL["fn"], WERTE, KTX)
check(isinstance(_h1["menge"], int), f"Prüfer-SOLL: je_groesse ohne menge_schritt → Raster 1 wie ap_konto_rechnen ({_w1['menge']!r} → {_h1['menge']!r})")
# Folge-Haupt (tt_folge_rechnen): der Beleg am Plan (kette.range) taugt als Faktoren und gibt bei gleicher Balance dieselben Werte
h2 = ruf("rv_anwenden", w, h1["range"], 0.1, PPL["fn"])
check((h2["menge"], h2["tp"], h2["sl"]) == (h1["menge"], h1["tp"], h1["sl"]), "kette.range als Faktoren → derselbe Haupt-Trade (Folge-Teil)")

print("── 5. Zufalls-Prüfung je Firma (je Lauf neue Stichprobe) ──")
rnd = random.Random()
for name, regel, ppl, schritt, bal_von, bal_bis in (("FundedNext", FN, 10.0, 0.1, 90500, 107500), ("The5%ers", T5, 1.0, 1, 90500, 107500),
                                                     ("FTMO", FT, 1.0, 1, 90500, 109500)):
    verstoss, n_et, n_fin = [], 0, 0
    for _ in range(1500):
        u = {x: rnd.random() for x in ("tp", "sl", "menge", "puffer")}
        bal = round(rnd.uniform(bal_von, bal_bis), 2)
        w0, g0 = ruf("ap_konto_rechnen", regel, "phase1", bal, u, ppl=ppl)
        if not w0:
            continue
        f = fk(round(rnd.uniform(0.1, 1), 4), round(rnd.uniform(0.1, 1), 4), round(rnd.uniform(0.1, 1), 4), regel, ppl, w0["groesse"])
        w1 = ruf("rv_anwenden", w0, f, schritt, ppl)
        st0 = str(w0["stufe"])
        if not (st0.startswith("Etappe") or ns["RV_FINAL_RE"].match(st0)):
            if w1 is not w0:
                verstoss.append(("Klein/Mini/Gewinntag verändert", st0))
            continue
        if ns["RV_FINAL_RE"].match(st0):
            n_fin += 1
            _statt = w1["tp"] < w0["rest"] + round(ns["AP_PUFFER_PKT"] * float(w1["menge"]) * ppl / 3)
            if _statt != w1["stufe"].startswith("Etappe") or _statt != w1["stufe"].endswith("(Ziel erst später)") or (_statt and ns["TT_EIN_TRADE_STUFE"].search(w1["stufe"])):
                verstoss.append(("letzter Trade Stufe", w0["rest"], w1["tp"], w1["stufe"]))
        n_et += 1
        m = float(w1["menge"])
        tpp, slp = w1["tp"] / (m * ppl), w1["sl"] / (m * ppl)
        if not (m <= w0["menge"] + 1e-9 and m >= schritt - 1e-9 and abs(m / schritt - round(m / schritt)) < 1e-6):
            verstoss.append(("Lots", w0["menge"], m))
        if m > w0["menge"] * f["f_lots"] + 1e-9 and m != schritt:
            verstoss.append(("Lots nicht abgerundet", w0["menge"], f["f_lots"], m))
        if w1["tp"] > w0["tp"] or w1["sl"] > w0["sl"] or w1["risiko"] != w1["sl"]:
            verstoss.append(("über dem normalen Wert", w0["tp"], w1["tp"], w0["sl"], w1["sl"]))
        if (tpp < MIN - 1e-6 and w1["tp"] != w0["tp"]) or (slp < MIN - 1e-6 and w1["sl"] != w0["sl"]):
            verstoss.append(("enger als Mindest-Pkt", tpp, slp))
        if tpp > f["tp_max_pkt"] + 1e-6 or slp > f["sl_max_pkt"] + 1e-6:
            verstoss.append(("weiter als der Deckel", tpp, f["tp_max_pkt"], slp, f["sl_max_pkt"]))
        if not w1["range"]["tp_geklemmt"] and abs(w1["tp"] - w0["tp"] * f["f_tp"]) > 0.51:
            verstoss.append(("TP ≠ Faktor", w0["tp"], f["f_tp"], w1["tp"]))
        if not w1["range"]["sl_geklemmt"] and abs(w1["sl"] - w0["sl"] * f["f_sl"]) > 0.51:
            verstoss.append(("SL ≠ Faktor", w0["sl"], f["f_sl"], w1["sl"]))
        if hb in w1["stufe"] and w1["sl"] < w0["sl"] - ns["AP_SL_HINTER_BODEN"]:
            verstoss.append(("Boden-Zusatz falsch", w0["sl"], w1["sl"]))
        if ns["RV_STUFE"] not in w1["stufe"]:
            verstoss.append(("Stufe ohne Range-Würfel", w1["stufe"]))
    check(n_et > 300 and n_fin > 20 and not verstoss, f"{name}: {n_et} Trades ({n_fin} letzte) × Zufalls-Faktoren — nie über dem Normal-Trade, Raster, {MIN:g} Pkt bis Deckel, Boden-Zusatz, Stufe {verstoss[:2]}")

print("── 6. Einbau in app.py ──")
ap = re.search(r"^def ap_planen\(.*?(?=^def )", app, re.S | re.M).group(0)
i_rv, i_tt, i_tf = ap.find("rv_planer_haken("), ap.find("tt_planer_haken("), ap.find("ap_tradeify_final_halten(")
check("rv_punkte_deckel(" in re.search(r"^def rv_planer_haken\(.*?(?=^\S)", app, re.S | re.M).group(0), "Planer-Haken gibt den Punkte-Deckel mit")
check(0 < i_rv < i_tf < i_tt, "ap_planen: Range-Würfel nach dem Rechnen, vor Tradeify-final und Trades pro Tag")
check('range=w["range"]' in ap and '_b["kette"] = dict(_b["kette"], range=w["range"])' in ap, "Plan-Zeile: mt5_baseline.range und kette.range")
check(re.search(r'"abstand_mll", "tag", "range"\)', app) is not None, "Folge-Teil trägt kette.range weiter (_tt_zeile)")
check(re.search(r'w_h = rv_anwenden\(w_h, k\["range"\]', app) is not None, "Folge-Haupt mit denselben Faktoren (tt_folge)")
check("rv_" not in re.search(r"^def gp_planen\(.*?(?=^def )", app, re.S | re.M).group(0), "Gruppen-Planer (gp_planen) unberührt (wie TW1)")
check("planer_range_wuerfel" not in re.search(r"^def tw_werte\(.*?(?=^def )", app, re.S | re.M).group(0), "Handels-Würfel liest seine Tabelle unverändert")

print("── 7. RV1d: Deckel unter dem Mindestabstand, kein TP-Gleichstand nach dem Würfel ──")
for n in ("RV_TP_FREI_SCHRITTE", "rv_tp_frei"):
    lade(n)
e1 = ruf("rv_anwenden", w5, {"f_tp": 1.0, "f_sl": 1.0, "f_lots": 1.0, "tp_max_pkt": 8.0, "sl_max_pkt": 5.0}, 1, PPL["t5"])
check((e1["tp"], e1["sl"], e1["range"]["tp_geklemmt"], e1["range"]["sl_geklemmt"]) == (250, 250, "min", "min"),
      f"Deckel 8 / 5 Pkt unter 10 Pkt, Faktor 100 % → TP/SL genau 10 Pkt = 250 $ (vorher ungedeckelt 5.850 / 1.980) ({e1['tp']}, {e1['sl']})")
e2 = ruf("rv_anwenden", w5, {"f_tp": 0.02, "f_sl": 0.02, "f_lots": 1.0, "tp_max_pkt": 8.0, "sl_max_pkt": 5.0}, 1, PPL["t5"])
check((e2["tp"], e2["sl"]) == (250, 250), f"Deckel unter 10 Pkt, Faktor klein → ebenfalls 10 Pkt ({e2['tp']}, {e2['sl']})")
w_klein = dict(w5, tp=200, sl=150)
e3 = ruf("rv_anwenden", w_klein, {"f_tp": 1.0, "f_sl": 1.0, "f_lots": 1.0, "tp_max_pkt": 8.0, "sl_max_pkt": 5.0}, 1, PPL["t5"])
check((e3["tp"], e3["sl"]) == (200, 150), f"nie über den alten Wert (alt schon unter 10 Pkt → bleibt) ({e3['tp']}, {e3['sl']})")
F = lambda w, b: ruf("rv_tp_frei", w, set(b), PPL["ft"])   # noqa: E731
check(F(d, []) is d and F(wf, [wf["tp"]]) is wf, "kein Gleichstand bzw. kein Range-Beleg → unverändert")
f1 = F(d, [2925])
check(f1["tp"] == 2924 and f1["range"]["tp_gleichstand"] == 2925 and f1["range"]["tp_pkt"] == round(2924 / 15, 1) and f1["sl"] == d["sl"] and f1["menge"] == d["menge"],
      f"Gleichstand 2.925 → 2.924 (−1 $), Beleg nachgezogen, SL/Lots gleich ({f1['tp']})")
check(f1["stufe"] == "Etappe · Range-Würfel TP 50 % · SL 50 % · Lots 50 %" and d["tp"] == 2925, f"   Stufe mit echtem Anteil, Eingabe unverändert ({f1['stufe']})")
check(F(d, [2925, 2924])["tp"] == 2926, "−1 auch belegt → +1")
check(F(d2, [288])["tp"] == 287, "TP genau am Deckel (288 Pkt bei 1 Lot) → nach unten")
w_min = dict(d2, tp=10, range=dict(d2["range"], statt_letzter=True))
check(F(w_min, [10])["tp"] == 10, "am Mindestabstand und klein gewürfelter letzter Trade (nur nach unten) → kein freier Wert, unverändert")
check(F(dict(d, range=dict(d["range"], statt_letzter=True)), [2925, 2924])["tp"] == 2923, "„Ziel erst später“: nur nach unten (−2 statt +1)")
check(F(dict(d, stufe="letzter Trade (Rest bis Ziel) · Range-Würfel TP 50 % · SL 50 % · Lots 50 %"), [2925])["tp"] == 2925, "gekappter letzter Trade bleibt (wie die Planer-Schleife)")
check(F(d, list(range(2875, 2976)))["tp"] == 2925 and F(d, list(range(2876, 2976)))["tp"] == 2875 and F(d, list(range(2875, 2975)))["tp"] == 2975,
      "höchstens ±50 $ — alles belegt → unverändert; −50 bzw. +50 frei → genommen")
w_u = {"menge": 1, "tp": 230, "sl": 300, "stufe": "Etappe · Range-Würfel TP 100 % · SL 100 % · Lots 100 %", "range": {"normal": {"menge": 1, "tp": 230, "sl": 300}}}
check(ruf("rv_tp_frei", w_u, {230}, 25.0)["tp"] == 230, "Normal-TP schon unter 10 Pkt (230 $ bei 25 $/Pkt) → nie darüber (Prüfer RV1d KANN), bleibt")
i_frei, i_add =ap.find("rv_tp_frei(w, tps_tranche"), ap.find("tps_tranche.add(w.get(\"tp\"))")
check(i_rv < i_frei < i_tf < i_add, "ap_planen: Gleichstand-Prüfung direkt nach dem Range-Würfel, vor Tradeify-final und dem Eintrag in tps_tranche")

print()
if fehler:
    print(f"ROT: {len(fehler)} Prüfung(en) fehlgeschlagen")
    sys.exit(1)
print("GRÜN: alle Prüfungen bestanden")
