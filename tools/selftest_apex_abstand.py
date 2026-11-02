#!/usr/bin/env python3
"""Selbsttest APEX-HEDGE AUF DEN ABSTAND (02.11.2026, Finn/Eingang, Geld-Pfad): Der Hedge war auf den ganzen DD (3.000 $) gerechnet, der Master endet am Tageslimit.
Prüffälle von heute …0044, …0010, …0015, …0009: hedge_eur 45, 0,71 Lot, Master −1.500 bis −1.576 $, Fusion +19 bis +21 € statt 45 €. Soll: master_risk 1.500, ~0,706, 1,41 Lot,
Blow ≈ +45 €, TP-Seite doppelt. Dazu Nachziehen schon umgestellter, ungestarteter Pläne, laufende nie. Aufruf: python3 tools/selftest_apex_abstand.py"""
import os
import re
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = open(os.path.join(W, "app.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def block(name):
    i = APP.index(f"\ndef {name}(") + 1
    return APP[i:APP.find("\n\n\n", i)]


def wd_num(x):
    try:
        return float(x) if x is not None and x != "" and not isinstance(x, bool) else None
    except (TypeError, ValueError):
        return None


ns = {"_wd_num": wd_num, "_wt_now_iso": lambda: "2026-11-02T10:00:00+00:00"}
exec("\n".join([re.search(r"^EH_STANDARD = .*$", APP, re.M).group(0)] + [block(f) for f in ("eh_hedge", "ah_werte", "ah_dll_balance", "ah_abstand", "ah_vorschau")]), ns)
SP, MP, KT, F = 0.85, 20.0, 2, 1.0     # Fusion €/Pkt je Lot, NQ $/Pkt, 2 NQ, netto_faktor seit 29.10. 1,0
KONTO_100K = {"max_daily_drawdown": 1500}


def hedge(bal, polster, wert, acc):
    ab, art = ns["ah_abstand"](bal, polster, acc)
    h, g = ns["eh_hedge"](wert / ab, KT, MP, SP, ab, F, 0.01)
    return dict(h, abstand=ab, art=art)


def fusion_eur(lots, master_pl):   # was der Fusion-Hedge bringt, wenn der Master master_pl $ macht (ohne Spread)
    return round(lots * (abs(master_pl) / (MP * KT)) * SP, 2)


# Die vier Prüffälle (Balance 100.000, Polster 3.000, Kaufpreis 45 €), Master-Ende aus der DB
for ext, pl, alt_eur in (("…0044", -1526.2, 19.42), ("…0010", -1546.2, 18.98), ("…0015", -1576.2, 20.30), ("…0009", -1500.0, 21.14)):
    h = hedge(100000.0, 3000.0, 45.0, KONTO_100K)
    neu = fusion_eur(h["lots"], pl)
    check(h["abstand"] == 1500 and h["art"] == "daily_loss" and abs(h["multiplier"] - 0.7059) < 0.001 and h["lots"] == 1.41 and h["slave_risk"] == 45.0,
          f"{ext}: master_risk 1.500 (Daily Loss), ×{h['multiplier']}, {h['lots']} Lot, slave_risk {h['slave_risk']} €")
    check(44 <= neu <= 47.5 and fusion_eur(0.71, pl) < 24, f"{ext}: Master {pl:.0f} $ → Fusion ≈ +{neu} € statt bisher 0,71 Lot ≈ +{fusion_eur(0.71, pl)} € (echt {alt_eur} €)")
h = hedge(100000.0, 3000.0, 45.0, KONTO_100K)
vs = ns["ah_vorschau"](h, 45.0, 3000.0, 97000.0, 6040)
alt = ns["eh_hedge"](45 / 3000, KT, MP, SP, 3000, F, 0.01)[0]
check(vs["tp_eur"] == -181.2 and abs(vs["tp_eur"] / round(-6040 * alt["q"], 2) - 2) < 0.01, f"TP-Seite doppelt: {vs['tp_eur']} € statt {round(-6040 * alt['q'], 2)} €")
check(vs["abstand_usd"] == 1500 and vs["polster_usd"] == 3000 and vs["blow_eur"] == 45.0, "Vorschau zeigt Abstand, Polster und Blow")
# Grenzfälle
h = hedge(98505.7, 1505.7, 22.59, KONTO_100K)
check(h["abstand"] == 1500 and h["art"] == "daily_loss", "bdfbb01b (98.505,70, Polster 1.505,70): Ende am Daily Loss 1.500 vor dem Boden")
h = hedge(97800.0, 800.0, 12.0, KONTO_100K)
check(h["abstand"] == 800 and h["art"] == "boden" and h["slave_risk"] == 12.0, "Polster unter dem Daily Loss: Ende am Boden, Abstand = Polster")
h = hedge(100000.0, 3000.0, 45.0, {})
check(h["abstand"] == 3000 and h["art"] == "boden" and h["lots"] == 0.71, "Konto ohne Daily Loss: wie bisher Polster")
h = hedge(150000.0, 4000.0, 60.0, {"max_daily_drawdown": 2000})
check(h["abstand"] == 2000 and h["slave_risk"] == 60.0, "150k: Daily Loss 2.000 vor dem Polster 4.000")
check(ns["ah_abstand"](None, 3000, KONTO_100K) == (None, None) and ns["ah_abstand"](100000, 0, KONTO_100K) == (None, None), "ohne Balance oder Polster kein Abstand")

# Am Quelltext: Rechnen, Umstellen, Nachziehen
t = block("ah_tick")
check('eh_hedge(wert / abstand, p.get("master_contracts")' in t and 'ah_abstand(bal, polster, dll_konto.get(str(a["id"])) or a)' in t, "rechnen: Satz = Kontowert ÷ Abstand, Daily Loss aus dem Konto")
check('"select": "id,max_daily_drawdown"' in t, "Daily Loss wird je Konto gelesen (fehlt in AP_KONTO_FELDER)")
check('"master_risk": h["abstand"]' in t and '"hedge_eur": round(wert, 2)' in t, "Umstellen: master_risk = Abstand, slave_risk/hedge_eur = Kontowert")
check('"mt5_baseline->apex_hedge->>status": "eq.mit"' in t and 'nach_filt.pop("or")' in t, "Nachziehen holt umgestellte Pläne (Marke mit)")
check('"start_um_gestartet_at": "is.null"' in t and 'g = _ah_guard(p, mit=True)' in t and '"status": "eq.planned"' in block("_ah_guard"),
      "Nachziehen nur ungeclaimt und planned (Guard), laufende nie")
check("eh_marge(les, h[\"lots\"], p.get(\"richtung\"), max(0.0, vorgemerkt.get(login, 0.0) - " in t, "Nachziehen prüft die Marge ohne die eigenen alten Lots doppelt")
check('plaene = [p for p in plaene if not p.get("_ah_nach")]' in t, "Vormerken und Umstellen sehen die nachzuziehenden Pläne nicht")
check("abs((_wd_num(p.get(\"multiplier\")) or 0) - (_wd_num(alt.get(\"multiplier\")) or 0)) > 0.0005" in t and t.index('_ah["hand"].add(') < t.index("h, wert, polster, bal, liq, fehl = rechnen(p, a)\n        if fehl or abs("),
      "Nachziehen: Multiplikator von Hand geändert → überspringen, einmal Spur, vor dem Rechnen")
check('Hedge zu am Daily Loss {float(bal) - h[\'abstand\']:.0f} $ (Boden {liq:.0f} $)' in t, "Notiz nennt bei Daily Loss den Daily-Loss-Stand, sonst den Boden")
# Hand-Riegel gegen eine Kopie des Schritts (3): nur der Vergleich, ohne DB
def hand(plan_mult, alt_mult):
    return abs((wd_num(plan_mult) or 0) - (wd_num(alt_mult) or 0)) > 0.0005
check(hand(0.3, 0.7059) and not hand(0.7059, 0.7059) and not hand("0.7059", 0.70588) and hand(0.7059, None), "Hand-Vergleich: gesenkt → Hand, gerundet gleich → kein Hand, alte Marke ohne Wert → Hand")
print("ROT:" if FEHLER else "alles grün", FEHLER if FEHLER else "")
sys.exit(1 if FEHLER else 0)
