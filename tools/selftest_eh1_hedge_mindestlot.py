#!/usr/bin/env python3
"""Selbsttest EH1 Fusion-Hedge auf das Mindest-Lot aufrunden (Finn 12.11.2026 ~20:45: „Wenn der Fusion-Hedge zu klein ist, einfach immer 0,01, immer das
Kleinste. Da geht es nur um ein paar Cent, ist echt egal.“ — Anlass Marc Tradeify CFD 100k Phase 1: „kein Echo-Hedge stellbar — Hedge 0,004 Lot unter 0,01 Lot“).
Prüft hedge_mindest_lot, eh_hedge (Challenge-Planer, Echo-Takt, Vorschau, Apex Prio 2), tfh_hedge (Tradeify final) mit den echten Funktionen aus app.py,
den Copier-Raster (mt5-copier/copier.py norm_vol) und die Einbau-Anker (Notiz, echo_hedge). Ohne Netz. Aufruf: python3 tools/selftest_eh1_hedge_mindestlot.py"""
import os
import re
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = open(os.path.join(W, "app.py"), encoding="utf-8").read()
COP = open(os.path.join(W, "mt5-copier", "copier.py"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


def quelle(src, name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", src, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^\S)", src, re.S | re.M)
    if not m:
        raise LookupError(name)
    return m.group(0)


ns = {"re": re}
for n in ("_wd_num", "EH_STANDARD", "TFH_STANDARD", "TFH_SLAVE_PPL", "hedge_mindest_lot", "hedge_auf_text", "eh_hedge", "tfh_hedge"):
    exec(quelle(APP, n), ns)
cop = {"TOL": 1e-9}
exec(quelle(COP, "norm_vol"), cop)
SI = {"volume_step": 0.01, "volume_min": 0.01, "volume_max": 100.0}
hm, eh, th = ns["hedge_mindest_lot"], ns["eh_hedge"], ns["tfh_hedge"]

# ── Kern: 0,004 → 0,01 · 0,013 → 0,01 (Schritt-Rundung wie bisher) · darüber unverändert
r = hm(0.004, 1.0, 0.01)
check(r and r[0] == 0.01 and abs(r[1] * 1.0 - 0.01) < 1e-9 and abs(r[2] - 2.5) < 1e-9, f"0,004 Lot gerechnet → 0,01 Lot, Faktor 2,5 ({r})")
check(hm(0.013, 1.0, 0.01) is None, "0,013 Lot → keine Aufrundung (Schritt-Rundung wie bisher → 0,01)")
check(hm(0.0049, 1.0, 0.01) and hm(0.0051, 1.0, 0.01) is None, "Grenze: 0,0049 rundet auf 0,00 → aufrunden; 0,0051 rundet schon auf 0,01 → unverändert")
check(hm(0, 1.0, 0.01) is None and hm(-0.003, 1.0, 0.01) is None and hm(None, 1.0, 0.01) is None, "keine belegte Rechnung (0/negativ/leer) → nie aufrunden")
check(hm(0.003, 0, 0.01) is None and hm(0.003, None, 0.01) is None, "ohne Master-Menge → nie aufrunden")

# ── Copier-Raster: menge × multiplier landet genau auf 0,01 (norm_vol rundet auf den Schritt)
ok_alle, schlecht = True, []
for menge in (0.01, 0.02, 0.05, 0.1, 0.18, 0.25, 0.3, 0.33, 0.5, 0.7, 1.0, 1.5, 2.0, 2.5, 3.0, 5.0, 7.5, 10.0):
    for roh in (0.0001, 0.001, 0.003, 0.0049):
        x = hm(roh, menge, 0.01)
        if x is None or cop["norm_vol"](SI, menge * x[1]) != 0.01:
            ok_alle = False
            schlecht.append((menge, roh, x))
check(ok_alle, f"Copier norm_vol(menge × multiplier) = 0,01 für alle Mengen 0,01–10 Lot ({schlecht[:3]})")

# ── eh_hedge (Challenge-Planer / Echo-Takt / Vorschau / Apex Prio 2)
h, g = eh(0.0446, 0.05, 1.0, 0.85, 100)
check(g is None and h["lots"] == 0.01 and h["multiplier"] == 0.2 and h["aufgerundet_von"] is not None, f"eh_hedge 0,05 Lot (0,003 gerechnet) → 0,01 Lot statt gesperrt ({h}, {g})")
check(abs(h["slave_risk"] - round(h["q"] * 100, 2)) < 0.01, "q und slave_risk passen zum aufgerundeten Hedge (slave_risk = q × master_risk)")
h2, _ = eh(0.0446, 0.18, 1.0, 0.85, 100)
check(h2["lots"] == 0.01 and "aufgerundet_von" not in h2, "0,0106 Lot → 0,01 wie bisher (Schritt-Rundung, keine Aufrundung)")
h3, _ = eh(0.0464, 2.5, 20.0, 0.85, 1500, 0.89, 0.01)
check(h3["lots"] == round(0.0464 / 0.89 * 20 / 0.85 * 2.5, 2) and "aufgerundet_von" not in h3, "normaler Hedge unverändert")
check(eh(None, 0.05, 1, 0.85, 1)[0] is None and eh(0.04, 0.05, None, 0.85, 1)[0] is None and eh(0.04, 0, 1, 0.85, 1)[0] is None,
      "fehlt Satz/Punktwert/Lots → weiter gesperrt (fail-closed)")
check(ns["hedge_auf_text"](h, 0.01) == " · Hedge auf Mindest-Lot 0,01 aufgerundet (gerechnet 0,003)" and ns["hedge_auf_text"](h3) == "",
      f"Notiz-Zusatz „Hedge auf Mindest-Lot 0,01 aufgerundet (gerechnet 0,003)“ ({ns['hedge_auf_text'](h, 0.01)!r})")

# ── tfh_hedge (Tradeify final)
k, gk = th(0.0001, 4500, 1, 2.0, 100)
check(gk is None and k["lots"] == 0.01 and k["aufgerundet_von"] is not None and cop["norm_vol"](SI, 1 * k["multiplier"]) == 0.01, f"tfh_hedge zu klein → 0,01 Lot ({k})")
k2, _ = th(595.4 / 4500, 4500, 2, 20.0, 2039)
check(k2 and "aufgerundet_von" not in k2, "tfh_hedge normal unverändert")

# ── Einbau-Anker: sichtbar in Notiz + echo_hedge / tradeify_hedge / apex_hedge, Prüfungen davor unverändert
check(APP.count("hedge_auf_text(h, par[\"min_lot\"])") == 4, "Notiz-Zusatz an Challenge-Planer, Echo-Takt, Tradeify final, Apex Prio 2")
check(APP.count('**({"aufgerundet_von": h["aufgerundet_von"]} if h.get("aufgerundet_von") is not None else {})') >= 4, "aufgerundet_von in echo_hedge (Planer + Takt), tradeify_hedge, apex_hedge")
check('keine frische Fusion-Lesung' in APP and 'kein Echo-Hedge-Konto (Fusion) bei dieser ID' in APP, "fehlende Lesung / fehlendes Hedge-Konto sperren weiter (unverändert)")
check(not re.search(r"^GP_MIN_LOT = 0\.01", APP, re.M) is None and 'f"Hedge unter {GP_MIN_LOT:.2f} Lot' in APP, "Gruppen-Planer (Emin, gp_hedge) bewusst unverändert")

print()
if fehler:
    print(f"ROT: {len(fehler)} Prüfung(en)")
    sys.exit(1)
print("GRÜN: EH1 Hedge auf Mindest-Lot 0,01 aufgerundet")
