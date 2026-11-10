#!/usr/bin/env python3
"""Selbsttest FH1 Variante B (Finn 10.11.2026: „ja top, dann bau das mal so"): Hedge-Basis im Funded-Planer Futures = max(echte offene Kosten, Pump-Kosten bis
zur Balance — Planer-Weg simuliert, app.py fdp_kosten_theorie), nur ab Zyklus-Start; darunter wie bisher (echte Kosten, ≤ 0 → AH2-Satz).
Pflichtfall (Finn): Pump +6.000 → Apex-EOD-Trailing zieht die Liq nach (Lock bei Größe + 100) → Pump +6.000, für 150k und 100k — Abstand, Lots, Fusion bei TP/SL
je Schritt für heute (echt), A (linear 0,183 €/$, nur zum Vergleich) und B. Gedruckt wird die Tabelle aus den echten Funktionen.
Aufruf: python3 tools/selftest_fh1_hedge_basis_b.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_funded_planer as fp  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


ns = fp.laden()
REGEL = ns["FDP_FIRMEN_STANDARD"][0]
R, JG, KB, LIQ, HEDGE = ns["fdp_konto_rechnen"], ns["fdp_je_groesse"], ns["fdp_kosten_theorie"], ns["fdp_liq"], ns["fdp_hedge"]
A_SATZ = 0.183    # Variante A (nur Vergleich, nicht gebaut): € je $ über Start, gemessen über alle Apex-Funded-Trades (FH1-Konstrukt)

print("1) fdp_kosten_theorie (rein)")
j100, j150 = JG(REGEL, 100000), JG(REGEL, 150000)
check(KB(j100, 100000, 100000, 100000) == 350 and KB(j150, 150000, 150000, 150000) == 550, "am Start = Kontokosten (350 / 550 €)")
check(abs(KB(j100, 100000, 108363.04, 100000) - 1470.6) < 1.0, f"Chris 100k 108.363 $: B ≈ 1.471 € ({KB(j100, 100000, 108363.04, 100000)})")
check(abs(KB(j100, 100000, 112000, 100000) - 2118.0) < 1.0, "100k bis 112.000 $: B ≈ 2.118 € (Chris' echter Pump bis ~111,8k kostete 2.118,72 €)")
check(KB(j100, 100000, 99000, 100000) is None and KB({}, 100000, 105000, 100000) is None and KB(dict(j100, max_trade=None), 100000, 105000, 100000) is None,
      "unter dem Start / ohne Daten → None (Aufrufer rechnet wie heute)")
# Trailing ohne Lock: +3.000 auf 150k → Liq zieht auf 149.000 nach (Abstand bleibt 4.000), erst ab Höchststand 154.100 fest bei 150.100
liq_a, _t = LIQ(150000, 4000, 153000, 153000, 100.0)
liq_b, _t = LIQ(150000, 4000, 156000, 156000, 100.0)
check(liq_a == 149000 and liq_b == 150100, f"Liq zieht nach (153k → {liq_a}) und bleibt nach dem Lock bei Größe + 100 (156k → {liq_b})")
j150_3k = dict(j150, max_trade=3000)
check(abs(KB(j150_3k, 150000, 156000, 150000) - (550 * (1 + 3000 / 4000) * (1 + 3000 / 4000))) < 0.02,
      "zwei Schritte à 3.000 vor dem Lock: beide auf 4.000 $ Abstand (Liq zieht nach) — 550 × 1,75 × 1,75")

print("2) Pflichtfall Finn: +6.000 → EOD-Trailing → +6.000 (TP je 6.000 $, 2 NQ)")
zeilen = []
for name, g, dd, kauf, st in (("150k", 150000, 4000, 550, fp.ST150), ("100k", 100000, 3000, 350, fp.ST100)):
    jg = dict(JG(REGEL, g), max_trade=6000)          # Finns Beispiel: je Schritt +6.000
    bal, echt = float(g), float(kauf)
    for schritt in (1, 2):
        kb = KB(jg, g, bal, g)
        r = R(REGEL, jg, st, bal, bal, echt, g, g, kt_fest=2)
        dist = round(bal - r["liq"], 2)
        check(r["aktion"] == "planen" and r["tp"] == 6000 and abs(r["offen_eur"] - max(echt, kb)) < 0.02,
              f"{name} Pump {schritt}: Balance {bal:,.0f} · Liq {r['liq']:,.0f} · Abstand {dist:,.0f} · Hedge-Basis {r['offen_eur']:,.2f} € = max(echt {echt:,.2f}, B {kb:,.2f})")
        ka = kauf + A_SATZ * (bal - g)
        ha = HEDGE(ka, bal, r["liq"], r["tp"], r["sl"], 2)
        zeilen.append((name, schritt, bal, r["liq"], dist, echt, kb, ka, r["lots"], r["hedge_tp_eur"], r["hedge_sl_eur"], ha["lots"], ha["hedge_tp_eur"], ha["hedge_sl_eur"], r["sl"]))
        check(abs(r["hedge_tp_eur"] - r["offen_eur"] / dist * 6000) < 0.05, f"{name} Pump {schritt}: Fusion am TP = Basis ÷ Abstand × TP")
        echt = round(echt + r["hedge_tp_eur"], 2)     # Pump gewinnt → Fusion verliert hedge_tp_eur → echte Kosten steigen
        bal += 6000
    check(abs(KB(jg, g, bal, g) - echt) < 0.05, f"{name}: nach zwei Pumps B = echte Kosten ({echt:,.2f} €) — B trägt das Nachziehen genau wie der echte Weg")
liq2_150 = [z for z in zeilen if z[0] == "150k" and z[1] == 2][0][3]
liq2_100 = [z for z in zeilen if z[0] == "100k" and z[1] == 2][0][3]
check(liq2_150 == 150100 and liq2_100 == 100100, "nach Pump 1 steht die Liq fest bei Start + 100 (150.100 / 100.100), Abstand 5.900 $")

print("3) Regel Balance ≥ Start → max(echt, B); darunter wie heute")
c = R(REGEL, j100, fp.ST100, 108363.04, 108363.04, 514.70, 100000, 100000, kt_fest=2)
check(c["hedge_basis"] == "pump_b" and abs(c["offen_eur"] - 1470.6) < 1 and c["offen_kosten_eur"] == 514.70
      and c["hedge_quelle"].startswith("Pump-Kosten bis Balance (B) 1.47") and c["hedge_quelle"].endswith("echt 515 €"),
      f"Chris …0006 nach WD (echt 515 €): Basis B {c['offen_eur']} € · {c['lots']} Lot (heute 2,79) · „{c['hedge_quelle']}“")
j = R(REGEL, j100, fp.ST100, 98081.4, 98081.4, 144.94, 100000, 100000, kt_fest=2)
check("hedge_basis" not in j and j["offen_eur"] == 144.94, "Jacob …0003 unter dem Start (98.081): echte Kosten wie heute")
x = R(REGEL, j100, fp.ST100, 104000, 104000, 2500, 100000, 100000, kt_fest=2)
check("hedge_quelle" not in x and x["offen_eur"] == 2500, "echte Kosten über B (teure Vorgeschichte): echt gilt, bitgleich wie heute")

print()
print("Tabelle (Fusion bei TP = Verlust, bei SL = Gewinn; an der Liq zahlt Fusion genau die Basis zurück):")
print(f"{'Konto':5} {'Schritt':7} {'Balance':>9} {'Liq':>9} {'Abstand':>7} | {'heute=B €':>9} {'Lots':>6} {'TP €':>7} {'SL €':>6} | {'A €':>7} {'Lots':>6} {'TP €':>7} {'SL €':>6} | SL $")
for (n, s, b, l, d, e, kb, ka, lo, tp, sl, la, ta, sa, slu) in zeilen:
    print(f"{n:5} Pump {s}  {b:9,.0f} {l:9,.0f} {d:7,.0f} | {max(e, kb):9,.0f} {lo:6.2f} {-tp:7,.0f} {sl:+6,.0f} | {ka:7,.0f} {la:6.2f} {-ta:7,.0f} {sa:+6,.0f} | {slu:,.0f}")
print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
