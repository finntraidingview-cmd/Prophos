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


def T(slave_pl, master_tp, master_pl, **h):
    return {"slave_pl": slave_pl, "master_tp": master_tp, "master_pl": master_pl, "hedge": dict({"status": "geschlossen"}, **h)}


# Prüfwerte Finn 02.11.2026 (alle TP, echte Pläne): Satz = eur ÷ master_tp, Plan = −Satz × master_pl
faelle = {
    "0431": (T(-118.53, 278, 271.80, grund="master_ende_reader", eur=111.06, pl=-118.53), -9.95),
    "3058": (T(-132.92, 275, 270.05, grund="level_tp", eur=127.78, pl=-132.92), -7.44),
    "2833": (T(-132.31, 276, 272.20, grund="master_ende_reader", eur=124.34, pl=-132.31), -9.68),
    "3656": (T(-139.80, 275, 267.30, grund="level_tp", eur=125.06, pl=-139.8), -18.24),
    "1889": (T(-133.50, 272, 269.20, grund="level_tp", eur=121.96, pl=-133.5), -12.80),
    # SL-Seite, gleicher Satz mit dem echten Master-Verlust (…3058 30.10.: 125,08 ÷ 270 × 1.543,80 = +715,18, echt +750,17)
    "sl_3058": (T(750.17, 270, -1543.80, grund="master_ende_reader", eur=125.08, pl=750.17), 34.99),
    "tradeify": (T(-100, 250, 250, grund="level_tp", eur=100, pl=-100), 0),
    "tradeify_500": (T(-210, 250, 500, grund="sl_feed", eur=100, pl=-210), -10.0),
    "hand": (T(-866.23, 7500, 7300, grund="hand", eur=932.99, pl=-866.23), None),
    "nie_da": (T(-3, 250, 0, grund="master_nie_da", eur=100, pl=-3), None),
    "master_ende": (T(-3, 250, 200, grund="master_ende", eur=100, pl=-3), None),
    "ohne_master_pl": (T(-100, 250, None, grund="level_tp", eur=100, pl=-100), None),
    "ohne_master_tp": (T(-100, None, 250, grund="level_tp", eur=100, pl=-100), None),
    "ohne_eur": (T(-100, 250, 250, grund="level_tp", eur=None, pl=-100), None),
    "ohne_slave_pl": (T(None, 250, 250, grund="level_tp", eur=100, pl=-101.5), -1.50),
    # so liefert /admin/live-trades master_pl: Objekt {wert, at, quelle}
    "objekt_0431": (T(-118.53, 278, {"wert": 271.80, "at": "2026-11-02T07:45:27Z", "quelle": "plan"}, grund="master_ende_reader", eur=111.06, pl=-118.53), -9.95),
    "objekt_ohne_wert": (T(-118.53, 278, {"wert": None, "at": None, "quelle": "rundgang"}, grund="master_ende_reader", eur=111.06, pl=-118.53), None),
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
for k in ("0431", "3058", "2833", "3656", "1889", "tradeify_500"):
    soll(f"{k}: rot „Overshoot −{de(faelle[k][1])} €“", "is-teuer" in e[k]["html"] and f"Overshoot −{de(faelle[k][1])} €" in e[k]["html"])
soll("SL-Seite …3058: grün „Undershoot +34,99 €“", "is-guenstig" in e["sl_3058"]["html"] and "Undershoot +34,99 €" in e["sl_3058"]["html"])
soll("Tradeify 250 $ → genau 100 €: neutral „Overshoot ±0,00 €“", "is-" not in e["tradeify"]["html"] and "Overshoot ±0,00 €" in e["tradeify"]["html"])
soll("ohne Punkte gerechnet", "punkte" not in code.split("function swAuswertung")[1].split("const diffEur")[0].split("*/")[-1])
for k in ("hand", "nie_da", "master_ende", "ohne_master_pl", "ohne_master_tp", "ohne_eur"):
    soll(f"{k}: keine Zahl", e[k]["html"] == "")
soll("keine Punkte, keine % in der Zeile", all("Pkt" not in e[k]["html"] and "%" not in e[k]["html"] for k in faelle))
soll("alte Felder weg", not any(x in HTML for x in ("s.wirkEur", "s.wirkPkt", "s.wirkPct", "overPkt", "overEur", "overPct")))
soll("Radar-Statistik nutzt diffEur", HTML.count("x.s.diffEur") == 2 and "kl(s.diffEur)" in HTML)
print(f"\n{'ALLES OK' if not fehler else f'{fehler} FEHLER'}")
sys.exit(1 if fehler else 0)
