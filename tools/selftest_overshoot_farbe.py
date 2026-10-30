#!/usr/bin/env python3
"""Selbsttest OVERSHOOT-FARBE (30.10.2026, Finn ~08:31: „Overshoot +1,3 Pkt · +6,43 €" ist immer rot): Radar-Zeile und Radar-Statistik
zeigen die WIRKUNG für uns (+ = besser als geplant → grün „Overshoot", − = Undershoot → rot, 0 neutral). Echte Hedges aus trade_plans:
  52b79294 (Apex …0003, Master SL, sl_feed, buy): Fusion-TP 28.831,87, Schluss 28.830,56 → −1,3 Pkt · −6,43 € Undershoot (rot)
  10ea8c26 (Apex …0006, Master SL, level_sl, buy): Fusion-TP 29.464,02, Schluss 29.464,48 → +0,5 Pkt Overshoot (grün)
  2b521c4e (Apex …0001 WD, Master TP, level_tp, buy): Fusion-SL 29.509,99, Schluss 29.509,23 → −0,8 Pkt Undershoot (rot)
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


# der Anzeige-Block der Radar-Zeile (zuWegZ) als eigene Funktion
i = HTML.index("      if(s.wirkPkt != null){")
block = HTML[i:HTML.index("\n      }\n", i) + 8]
code = "\n".join(["const window = {}", js_funktion("hedgeHandSchneller"), js_funktion("hedgeGrundEcht"), zeile("  const SW_WEGE ="), zeile("  const SW_WEG_TXT ="), zeile("  const SW_WEG_VON ="), js_funktion("swAuswertung"),
                  "function zeileOver(s){ const f1 = v => Number(v).toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 }); let over = ''\n"
                  + block + "\n return over }"])
H = lambda **k: {"hedge": dict({"status": "geschlossen"}, **k)}   # noqa: E731
faelle = {
    "52b79294": H(grund="sl_feed", richtung="buy", sl=28629.16, tp=28831.87, fill=28786.99, fill_close=28830.56, lots=5.49, wert_pro_punkt=0.89358, eur=699.98),
    "10ea8c26": H(grund="level_sl", richtung="buy", sl=29261.3, tp=29464.02, fill=29418.91, fill_close=29464.48, lots=5.49, wert_pro_punkt=0.89558, eur=699.98),
    "2b521c4e": H(grund="level_tp", richtung="buy", sl=29509.99, tp=30239.08, fill=29577.78, fill_close=29509.23, lots=3.31, wert_pro_punkt=0.89803, eur=181),
    "sell_tp_besser": H(grund="level_sl", richtung="sell", sl=29673.66, tp=29413.09, fill=29477.11, fill_close=29413.03, lots=6.47, wert_pro_punkt=0.8957, eur=1031.16),
    "null": H(grund="tp_feed", richtung="buy", sl=29000, tp=29500, fill=29200, fill_close=29000, lots=1, wert_pro_punkt=0.9, eur=100),
    "ohne_eur": H(grund="tp_feed", richtung="buy", sl=29000, tp=29500, fill=29200, fill_close=28998, lots=None, wert_pro_punkt=None, eur=None),
}
lauf = "const out = {}\n" + "".join(f"{{ const s = swAuswertung({json.dumps(v)}); out[{json.dumps(k)}] = {{ s, html: zeileOver(s) }} }}\n" for k, v in faelle.items()) \
    + "print(JSON.stringify(out))\n"
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

a = e["52b79294"]
soll("52b79294: Rechnung unverändert (over +1,31 Pkt, +6,43 €)", round(a["s"]["overPkt"], 2) == 1.31 and round(a["s"]["overEur"], 2) == 6.43)
soll("52b79294: Wirkung −6,43 € → rot „Undershoot −1,3 Pkt · −6,43 €“", "is-teuer" in a["html"] and "Undershoot −1,3 Pkt · −6,43 €" in a["html"])
b = e["10ea8c26"]
soll("10ea8c26: Fusion hinter seinem TP → grün „Overshoot +0,5 Pkt · +2,26 €“", "is-guenstig" in b["html"] and "Overshoot +0,5 Pkt · +2,26 €" in b["html"])
c = e["2b521c4e"]
soll("2b521c4e: Master TP, Fusion hinter seinem SL → rot Undershoot", "is-teuer" in c["html"] and "Undershoot −0,8 Pkt" in c["html"])
d = e["sell_tp_besser"]
soll("Hedge sell, Schluss unter seinem TP → grün Overshoot", "is-guenstig" in d["html"] and d["html"].count("Overshoot +") == 1)
z = e["null"]
soll("genau am Level → neutral „Overshoot ±0,0 Pkt · ±0,00 €“", "is-" not in z["html"] and "Overshoot ±0,0 Pkt · ±0,00 €" in z["html"])
o = e["ohne_eur"]
soll("ohne € → Farbe nach Punkten, kein €-Teil", "is-teuer" in o["html"] and "Undershoot −2,0 Pkt" in o["html"] and "€" not in o["html"])
soll("Radar-Statistik: kl grün bei +, rot bei −", "const kl = v => v == null ? '' : v > 0.05 ? 'is-guenstig' : v < -0.05 ? 'is-teuer' : ''" in HTML)
soll("Radar-Statistik nutzt wirk*-Felder", HTML.count("x.s.wirkPct") == 2 and HTML.count("x.s.wirkEur") == 2 and "x.s.wirkPkt" in HTML)
soll("kein „Slippage“ in der Anzeige (Finn: Undershoot)", "'Slippage'" not in HTML)

print(f"\n{'ALLES OK' if not fehler else f'{fehler} FEHLER'}")
sys.exit(1 if fehler else 0)
