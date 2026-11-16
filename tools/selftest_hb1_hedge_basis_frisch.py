#!/usr/bin/env python3
"""Selbsttest HB1 Hedge-Basis im Funded-Planer Futures (Finn 16.11.2026 über den Master: „Theoretische Pumpkosten“ = die normalen Kosten eines FRISCHEN
Kontos, also der Satz wie AH2 — hedge_eur ÷ dd der Regel, fehlt hedge_eur: kosten_eur ÷ dd, Apex 100k 350 € auf 3.000 $ = 0,117 €/$ — angewendet auf den
aktuellen Abstand Balance − Liq, keine Pfad-Simulation). Bedingung Balance ≥ Zyklus-Start und max(echte offene Kosten, kb) bleiben.
Fälle = die drei geplanten Apex-Pläne vom 15.11.2026 (Live-DB gelesen): …0006 (Balance 101.454,44, echt −821,16 €), …0005 (101.967,58, echt −1.518,82 €),
…0007 (101.881,40, echt +313,02 € > Satz × Abstand → bleibt echt). Echte Funktionen aus app.py (Lader von selftest_funded_planer). Ohne Netz.
Aufruf: python3 tools/selftest_hb1_hedge_basis_frisch.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest_funded_planer as fp  # noqa: E402

fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = fp.laden()
REGEL = ns["FDP_FIRMEN_STANDARD"][0]
R, JG, FS = ns["fdp_konto_rechnen"], ns["fdp_je_groesse"], ns["fdp_frisch_satz"]
j100 = JG(REGEL, 100000)
SATZ = 350 / 3000

# ── Satz eines frischen Kontos
s = FS(j100)
check(s and abs(s[0] - SATZ) < 1e-12 and s[1:] == (350.0, 3000.0, "kosten_eur") if s else False, f"Apex 100k: 350 € je 3.000 $ (kosten_eur) = 0,117 €/$ ({s})")
check(FS({"hedge_eur": 450, "kosten_eur": 120, "dd": 3000})[1:] == (450.0, 3000.0, "hedge_eur"), "hedge_eur geht vor kosten_eur")
check(FS({"kosten_eur": 350}) is None and FS({}) is None and FS(None) is None, "ohne dd bzw. ohne Beträge → None")


def fall(name, bal, echt, ziel_basis, echt_bleibt=False):
    # Peak 104.000 (über Größe + DD + 100): Liq fest bei 100.100 wie bei den echten Konten (funded_plan.liq 100.100)
    r = R(REGEL, j100, fp.ST100, bal, 104000, echt, 100000, 100000, kt_fest=2, konst={"sppl": 0.8926})
    check(r["liq"] == 100100, f"{name}: Liq 100.100 (Lock) wie im Live-Plan")
    abst = round(bal - r["liq"], 2)
    erw = echt if echt_bleibt else round(SATZ * abst, 2)
    lots = r.get("lots")
    check(r["aktion"] == "planen" and abs(r["offen_eur"] - erw) < 0.011 and (ziel_basis is None or abs(r["offen_eur"] - ziel_basis) < 1.0),
          f"{name}: Balance {bal:,.2f}, Liq {r['liq']:,.0f}, Abstand {abst:,.2f} $, echt {echt:+,.2f} € → Hedge-Basis {r['offen_eur']:,.2f} € · {lots} Lot · "
          f"Fusion am TP {r['hedge_eur']:,.2f} € · {r.get('hedge_quelle') or 'echte Kosten'}")
    return r


r6 = fall("…0006", 101454.44, -821.16, 158.0)
check(r6["hedge_basis"] == "pump_b" and r6["hedge_quelle"].startswith("theoretische Kosten (frisches Konto): 350 € je 3.000 $ (kosten_eur) × 1.354")
      and r6["hedge_quelle"].endswith("echt -821 €"), "…0006: Text nennt Satz, Abstand und die echten Kosten")
check(r6["lots"] <= 6.0 and r6["lots"] >= 4.5, f"…0006: ~5 Fusion-Lots statt ~17 (Deckel 16) ({r6['lots']})")
r5 = fall("…0005", 101967.58, -1518.82, 217.9)
check(4.5 <= r5["lots"] <= 6.0, f"…0005: ~5 Lots statt 13,7 ({r5['lots']})")
r7 = fall("…0007", 101881.40, 313.02, 313.02, echt_bleibt=True)
check("hedge_basis" not in r7 and "hedge_quelle" not in r7, "…0007: echte offene Kosten 313 € > Satz × Abstand (208 €) → echte Kosten wie bisher, kein B")

# ── Rand: unter dem Zyklus-Start wie bisher (echt bzw. AH2), sehr großer Abstand skaliert linear
u = R(REGEL, j100, fp.ST100, 99500, 99500, -498, 100000, 100000, kt_fest=2)
check(u.get("hedge_basis") == "ah2" and abs(u["offen_eur"] - round(SATZ * (99500 - u["liq"]), 2)) < 0.011, "unter dem Start, im Plus → AH2-Satz wie bisher")
e = R(REGEL, j100, fp.ST100, 99500, 99500, 400, 100000, 100000, kt_fest=2)
check("hedge_basis" not in e and e["offen_eur"] == 400, "unter dem Start, echte Kosten > 0 → echte Kosten wie bisher")
g8 = R(REGEL, j100, fp.ST100, 108363.04, 108363.04, 514.70, 100000, 100000, kt_fest=2)
check(abs(g8["offen_eur"] - round(SATZ * (108363.04 - g8["liq"]), 2)) < 0.011, f"weit über dem Start (108.363): Satz × Abstand ({g8['offen_eur']} €), keine Pfad-Simulation")

src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"), encoding="utf-8").read()
blk = src[src.index("def fdp_konto_rechnen("):src.index("FDP_FENSTER_TZ = ")]
check("fdp_kosten_theorie(" not in blk and "fs = fdp_frisch_satz(jg)" in blk, "fdp_konto_rechnen nutzt fdp_frisch_satz, nicht mehr fdp_kosten_theorie")
check("def fdp_kosten_theorie(" in src, "fdp_kosten_theorie bleibt (Erklärung/Selbsttests)")

print()
if fehler:
    print(f"ROT: {len(fehler)} Prüfung(en)")
    sys.exit(1)
print("GRÜN: HB1 Hedge-Basis = Satz eines frischen Kontos × Abstand")
