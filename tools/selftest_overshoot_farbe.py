#!/usr/bin/env python3
"""Selbsttest OVERSHOOT GEGEN PLAN (Finn 30.10.2026 13:5x: „Was hätte ich verlieren oder machen sollen? Was habe ich verloren oder gemacht? Davon die Differenz"):
swAuswertung.diffEur = echter Fusion-P&L − geplanter Fusion-P&L; Radar-Zeile: − rot „Overshoot", + grün „Undershoot", nur € mit zwei Stellen, keine Punkte, keine %.
Echte Hedges aus trade_plans (SELECT 30.10.2026): sechs Master-TP-Trades + 1650a0e3 (Tradeify final, Master Liq, Plan blow_eur 675), Funded-Planer auf der SL-Seite.
Aufruf:  python3 tools/selftest_overshoot_farbe.py"""
import json
import os
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
fehler = 0


def soll(name, ok):
    global fehler
    print(("ok   " if ok else "FEHL ") + name)
    fehler += 0 if ok else 1


def js_funktion(name):
    i = HTML.index(f"  function {name}(")
    return HTML[i:HTML.index("\n  }\n", i) + 4]


def zeile(anfang):
    i = HTML.index(anfang)
    return HTML[i:HTML.index("\n", i)]


i = HTML.index("      if(s.diffEur != null){")
block = HTML[i:HTML.index("\n      }\n", i) + 8]
code = "\n".join(["const window = {}", js_funktion("hedgeHandSchneller"), js_funktion("hedgeGrundEcht"), zeile("  const SW_WEGE ="), zeile("  const SW_WEG_TXT ="), zeile("  const SW_WEG_VON ="), js_funktion("swAuswertung"),
                  "function zeileOver(s){ const f2 = v => Number(v).toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); let over = ''\n" + block + "\n return over }"])


def T(slave_pl, plan_sl=None, **h):
    return {"slave_pl": slave_pl, "hedge_plan_sl_eur": plan_sl, "hedge": dict({"status": "geschlossen"}, **h)}


faelle = {
    "f6424802": (T(-127.80, grund="master_ende_reader", richtung="sell", sl=28811.31, tp=26222.14, fill_close=28807.79, eur=124.99, punkte=45.67, sl_punkte=2552.62, pl=-127.8), -2.81),
    "0d9adcdd": (T(-132.05, grund="level_mt5", grund_tab="master_ende_reader", grund_copier="close", close_at="2026-10-30T07:49:41.385Z", richtung="buy", sl=28781.05, tp=30377.77, fill_close=28783.86, eur=124.99, punkte=45.67, sl_punkte=1553.3, pl=-132.05), -7.06),
    "600a4b62": (T(-87.35, grund="level_tp", richtung="buy", sl=28794.79, tp=29384.94, fill_close=28794.24, eur=79.76, punkte=69, sl_punkte=519.96, pl=-87.35), -7.59),
    "9553ddc4": (T(-89.36, grund="level_tp", richtung="buy", sl=28751.32, tp=29425.09, fill_close=28750.61, eur=79.76, punkte=68, sl_punkte=603.32, pl=-89.36), -9.60),
    "3be7bc94": (T(-89.82, grund="level_tp", richtung="buy", sl=28754.43, tp=29350.9, fill_close=28754.24, eur=80.06, punkte=68.25, sl_punkte=524.1, pl=-89.82), -9.76),
    "f6871520": (T(-139.80, grund="level_tp", richtung="buy", sl=28751.95, tp=32486.3, fill_close=28751.24, eur=125.18, punkte=68.5, sl_punkte=3678.43, pl=-139.8), -14.62),
    "1650a0e3": (T(663.91, 675, grund="sl_feed", richtung="sell", sl=28920.13, tp=28754.95, fill_close=28761.41, eur=302.85, punkte=50.48, sl_punkte=110, pl=663.91), -11.09),
    # SL-Seite ohne Vorschau: eur ÷ punkte × sl_punkte = 483,44 (funded_plan.hedge_sl_eur 483,39), echt 512,67 → besser als geplant
    "b74d6b68": (T(512.67, grund="sl_feed", richtung="sell", sl=28900, tp=28800, fill_close=28799.79, eur=1160.25, punkte=150, sl_punkte=62.5, pl=512.67), 29.23),
    "hand": (T(-866.23, grund="hand", richtung="sell", sl=28900, tp=28000, fill_close=28862.49, eur=932.99, punkte=148.13, sl_punkte=62.5, pl=-866.23), None),
    "nie_da": (T(-3, grund="master_nie_da", richtung="buy", sl=28000, tp=29000, fill_close=28100, eur=100, punkte=50, sl_punkte=20, pl=-3), None),
    "master_ende": (T(-3, grund="master_ende", richtung="buy", sl=28000, tp=29000, fill_close=28100, eur=100, punkte=50, sl_punkte=20, pl=-3), None),
    "ohne_plan_tp": (T(-3, grund="level_tp", richtung="buy", sl=28000, tp=29000, fill_close=28000, eur=None, punkte=50, sl_punkte=20, pl=-3), None),
    "ohne_plan_sl": (T(9, grund="level_sl", richtung="buy", sl=28000, tp=29000, fill_close=29000, eur=100, punkte=50, sl_punkte=0, pl=9), None),
    "ohne_slave_pl": (T(None, grund="level_tp", richtung="buy", sl=28000, tp=29000, fill_close=28000, eur=100, punkte=50, sl_punkte=20, pl=-101.5), -1.50),
    "genau": (T(-100, grund="level_tp", richtung="buy", sl=28000, tp=29000, fill_close=28000, eur=100, punkte=50, sl_punkte=20, pl=-100), 0),
}
lauf = "const out = {}\n" + "".join(f"{{ const s = swAuswertung({json.dumps(v[0])}); out[{json.dumps(k)}] = {{ s, html: zeileOver(s) }} }}\n" for k, v in faelle.items()) + "print(JSON.stringify(out))\n"
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(code + "\n" + lauf)
    pfad = f.name
r = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=60)
os.unlink(pfad)
try:
    e = json.loads(r.stdout.strip().splitlines()[-1])
except Exception:
    print(r.stdout, r.stderr)
    sys.exit(1)

for k, (_, w) in faelle.items():
    soll(f"{k}: diffEur {w}", e[k]["s"]["diffEur"] == w)
de = lambda v: f"{abs(v):.2f}".replace(".", ",")   # noqa: E731
for k in ("f6424802", "0d9adcdd", "600a4b62", "9553ddc4", "3be7bc94", "f6871520", "1650a0e3"):
    soll(f"{k}: rot „Overshoot −{de(faelle[k][1])} €“", "is-teuer" in e[k]["html"] and f"Overshoot −{de(faelle[k][1])} €" in e[k]["html"])
soll("b74d6b68: grün „Undershoot +29,23 €“", "is-guenstig" in e["b74d6b68"]["html"] and "Undershoot +29,23 €" in e["b74d6b68"]["html"])
soll("genau im Plan: neutral „Overshoot ±0,00 €“", "is-" not in e["genau"]["html"] and "Overshoot ±0,00 €" in e["genau"]["html"])
for k in ("hand", "nie_da", "master_ende", "ohne_plan_tp", "ohne_plan_sl"):
    soll(f"{k}: keine Zahl", e[k]["html"] == "")
soll("keine Punkte, keine % in der Zeile", all("Pkt" not in e[k]["html"] and "%" not in e[k]["html"] for k in faelle))
soll("alte Felder weg", not any(x in HTML for x in ("s.wirkEur", "s.wirkPkt", "s.wirkPct", "overPkt", "overEur", "overPct")))
soll("Radar-Statistik nutzt diffEur", HTML.count("x.s.diffEur") == 2 and "kl(s.diffEur)" in HTML)
print(f"\n{'ALLES OK' if not fehler else f'{fehler} FEHLER'}")
sys.exit(1 if fehler else 0)
