#!/usr/bin/env python3
"""Selbsttest FH1b (10.11.2026, Master; Finn wartete): unbestätigte Funded-Vorschläge rechnet der Planer neu, wenn sich NUR die Hedge-Basis geändert hat
(app.py fdp_vorschlag_basis_neu, fdp_notiz_basis) — Fall: Vorschlag vor FH1 angelegt (echte Kosten 514,70 €), FH1 B sagt 1.470,54 €.
Aufruf: python3 tools/selftest_fh1b_vorschlag_neu.py"""
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
REGEL = dict(ns["FDP_FIRMEN_STANDARD"][0], ziel_puffer_pct=0, ziel_puffer_min_usd=0)   # FP-PUF: Puffer aus — der Fall ist ein Vorschlag von vor dem Puffer (TP = Rest)
R, JG, BN, NZ = ns["fdp_konto_rechnen"], ns["fdp_je_groesse"], ns["fdp_vorschlag_basis_neu"], ns["fdp_notiz_basis"]
j = JG(REGEL, 100000)
r = R(REGEL, j, fp.ST100, 108363.04, 108363.04, 514.70, 100000, 100000, kt_fest=2, konst={"sppl": 0.8926})
ALT = {"status": "planned", "auto_bestaetigt_at": None, "start_um": None, "start_um_gestartet_at": None, "started_at": None, "hand_werte_at": None,
       "master_tp": 3636.96, "master_sl": 2500.0, "master_contracts": 2.0, "slave_risk": 514.70,
       "notes": "Funded-Planer · Vorschlag · Zyklus 1 · Ziel 112.000 $ · Liq 100.100 $ · Stufe 4 (Daily Loss 2.500 $) · offene Kosten 515 €",
       "funded_plan": {"tp_art": "normal", "offen_eur": 514.7, "start": 100000}}

print("1) Vorschlag vor FH1 → neue Hedge-Basis")
f = BN(ALT, r)
# HB1 (16.11.2026): Basis = 350 € / 3.000 $ × Abstand 8.263 $ = 964,02 € (vorher Pfad-Simulation 1.470,54 €)
check(f and f["slave_risk"] == 964.02 and f["slave_risk"] == r["slave_risk"] and f["multiplier"] == r["multiplier"] and f["hedge_eur"] == r["hedge_eur"] and "master_tp" not in f,
      f"Hedge-Felder neu (Basis 964,02 €, Multiplikator {f and f['multiplier']}, Fusion am TP {f and f['hedge_eur']} €), TP/SL/Kontrakte bleiben")
check(NZ(ALT["notes"], r).endswith("· Hedge-Basis 964 € = theoretische Kosten (frisches Konto) · echt 515 €") and NZ("ohne Ende", r) is None, "Notiz-Ende umgeschrieben")

print("2) Guards")
ok = True
for k, v in (("status", "open"), ("auto_bestaetigt_at", "x"), ("start_um", "x"), ("start_um_gestartet_at", "x"), ("started_at", "x"), ("hand_werte_at", "x")):
    ok &= BN(dict(ALT, **{k: v}), r) is None
check(ok, "nie: offen, bestätigt, mit Startzeit, geclaimt, gestartet, Hand-Werte")
check(BN(dict(ALT, master_tp=3000.0), r) is None and BN(dict(ALT, master_sl=2000.0), r) is None and BN(dict(ALT, master_contracts=3.0), r) is None,
      "TP/SL/Kontrakte von Hand geändert oder Balance weiter → nicht")
check(BN(dict(ALT, slave_risk=800.0), r) is None, "Hedge im Popup geändert (slave_risk ≠ gespeicherte Basis) → bleibt")
r_gleich = R(REGEL, j, fp.ST100, 100000, 100000, 350, 100000, 100000, kt_fest=2, konst={"sppl": 0.8926})
alt_start = dict(ALT, master_tp=r_gleich["tp"], master_sl=r_gleich["sl"], slave_risk=350.0, funded_plan={"tp_art": "normal", "offen_eur": 350.0})
check(BN(alt_start, r_gleich) is None, "Konto am Start (Basis 350 € = B): nichts zu tun")

print("3) Einbau")
src = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
check("felder, nur_basis = fdp_vorschlag_basis_neu(lauf[0], r_neu), True" in src and "slave_risk,notes,auto_plan" in src
      and '"auto_bestaetigt_at": "is.null", "start_um": "is.null", "start_um_gestartet_at": "is.null", "hand_werte_at": "is.null"' in src,
      "im ±500-Block des Planers, gleicher Update-Filter, Planer liest slave_risk und notes")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
