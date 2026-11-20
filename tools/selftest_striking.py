"""Selbsttest: Striking für Apex (SK1, Finn 20.11.2026) — rein rechnend, ohne DB und ohne app.py (Modul striking_apex.py).
Beispiele A/B/C aus .claude/master/berichte/2026-11-20_SK1_striking_apex_konstrukt.md, je über viele Würfel-Seeds.
Aufruf: python3 tools/selftest_striking.py  → „OK …“ bzw. AssertionError (Exit 1)."""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import striking_apex as sk  # noqa: E402

CFG = sk.sk_cfg(None)
SEEDS = 300
# Prüfer 20.11.: Basis-Seed ausgeben, damit ein Fehlschlag nachstellbar ist (SK_SEED=<zahl> python3 tools/selftest_striking.py)
BASIS = int(os.environ.get("SK_SEED") or random.randrange(10 ** 6))
fehler = []


def pruef(bed, text):
    if not bed:
        fehler.append(text)


def zyklus(groesse, payout_nr, start, netto, tage, rnd, ergebnis=None, max_tage=20, probation=True):
    """Simuliert Tag für Tag: Plan des Tages → Ergebnis (Standard: TP getroffen; ergebnis(tag_nr, plan) darf einen Verlust liefern).
    → (Liste der Pläne mit Ergebnis, netto, tage)."""
    z, _cap, _txt, z_min = sk.sk_ziel(CFG, groesse, payout_nr, probation=probation, start=start)
    tage = dict(tage)
    plaene = []
    for i in range(max_tage):
        p = sk.sk_tag_tp(CFG, groesse, z, netto, tage, rnd, z_min=z_min)
        if p["aktion"] == "ziel":
            break
        pl = ergebnis(i, p) if ergebnis else None
        pl = p["tp"] if pl is None else pl
        plaene.append(dict(p, pl=pl))
        netto = round(netto + pl, 2)
        tage[f"t{len(tage) + 1:02d}"] = pl
    return plaene, netto, tage, z


# Ziele (Spezifikation „Ziel je Zyklus“)
for g, nr, soll in ((100000, 1, 4000), (100000, 2, 5000), (150000, 2, 6000), (150000, 5, 8000), (100000, 4, 6000)):
    z = sk.sk_ziel(CFG, g, nr)[0]
    pruef(z == soll, f"Ziel {g} Payout {nr}: {z} statt {soll}")
# Ohne Probation (Nachtrag 2, Jacob 100k): Z = 2 × Cap, Balance muss die Mindest-Payout-Balance 103.600 erreichen (absolut)
for g, nr, start, soll in ((100000, 2, 110105.82, 5000), (100000, 1, 100500, 4000), (100000, 1, 99000, 4600), (150000, 1, 150000, 5000),
                           (150000, 1, 149000, 5600), (100000, 1, 112000, 4000)):
    z = sk.sk_ziel(CFG, g, nr, probation=False, start=start)[0]
    pruef(z == soll, f"ohne Probation {g} Payout {nr} Start {start}: {z} statt {soll}")
pruef(sk.sk_ziel(CFG, 100000, 1, probation=True, start=112000)[0] == 4000, "Probation 100k Payout 1: max(4.000, 3.600)")
pruef(sk.sk_ziel(CFG, 100000, 1, probation=False, start=None)[0] is None, "ohne Probation braucht es den Zyklus-Start")
pruef(sk.sk_ziel(CFG, 100000, None)[0] is None, "ohne Payout-Nr. muss Striking aus sein (fail-closed)")
pruef(sk.sk_ziel(CFG, 50000, 1)[0] is None, "50k hat keine Striking-Werte")
pruef(sk.sk_deckel(CFG, 5000) == 2375 and sk.sk_deckel(CFG, 6000) == 2850, "Deckel 2.375 / 2.850")

for seed in range(SEEDS):
    rnd = random.Random(seed * 7919 + BASIS)

    # Schlupf am Fill (Prüfer 20.11.): jeder Gewinn-Trade bucht 0–60 $ weniger als der TP → Ziel innerhalb der Toleranz, nie ein TP < 100 $,
    # 5 Tage ≥ Schwelle, harte Bedingung erfüllt, Consistency hält
    def schlupf(i, p):
        return round(p["tp"] - rnd.uniform(0, 60), 2)
    for g, nr, prob, start in ((100000, 2, True, 110000), (150000, 2, True, 161441.12), (100000, 2, False, 110105.82), (100000, 1, False, 99500)):
        pl, netto, tage, z = zyklus(g, nr, start, 0.0, {}, rnd, ergebnis=schlupf, probation=prob)
        z_min = sk.sk_ziel(CFG, g, nr, probation=prob, start=start)[3]
        schw = 300 if g == 100000 else 350
        pruef(all(p["tp"] >= 100 - 1e-6 for p in pl), f"Schlupf {g}/{nr} seed {seed}: Mikro-TP {[p['tp'] for p in pl]}")
        pruef(z - 100 - 1e-6 <= netto <= z + 100 + 1e-6 and netto >= z_min - 1e-6, f"Schlupf {g}/{nr} seed {seed}: Ende {netto}, Ziel {z}, hart {z_min}")
        pruef(sk.sk_tage_ok(tage, schw) >= 5, f"Schlupf {g}/{nr} seed {seed}: Tage {tage}")
        pruef(max(tage.values()) <= 0.5 * netto + 1e-6, f"Schlupf {g}/{nr} seed {seed}: Consistency {max(tage.values())} / {netto}")
        pruef(len(pl) <= 8, f"Schlupf {g}/{nr} seed {seed}: {len(pl)} Trades")

    # A · 100k Payout 2, Start 110.000: 3 kleine → 2 Pump, genau 115.000, bester Tag ≤ 50 %
    pl, netto, tage, z = zyklus(100000, 2, 110000, 0.0, {}, rnd)
    arten = [p["art"] for p in pl]
    pruef(arten[:3] == ["klein"] * 3 and len(pl) == 5, f"A seed {seed}: Ablauf {arten}")
    pruef(abs(netto - 5000) < 0.005, f"A seed {seed}: Ende {110000 + netto} statt 115.000")
    pruef(all(p["tp"] <= 2375 + 1e-6 for p in pl), f"A seed {seed}: TP über dem Deckel {[p['tp'] for p in pl]}")
    pruef(max(tage.values()) <= 0.5 * netto + 1e-6, f"A seed {seed}: bester Tag {max(tage.values())} > 50 %")
    pruef(sk.sk_tage_ok(tage, 300) >= 5, f"A seed {seed}: nur {sk.sk_tage_ok(tage, 300)} Tage ≥ 300")
    pruef(all(370 <= p["tp"] <= 420 for p in pl if p["art"] == "klein"), f"A seed {seed}: kleine TPs außerhalb 370–420")

    # B · 150k Payout 2, Start 161.441,12, Tag 1 schon +1.466,72: R 4.533,28, Deckel 2.850 → 2 kleine + 2 Pump, genau 167.441,12
    start_b = 161441.12
    erst = sk.sk_tag_tp(CFG, 150000, 6000, 1466.72, {"t1": 1466.72}, random.Random(seed))
    pruef(abs(erst["rest"] - 4533.28) < 0.005 and erst["deckel"] == 2850 and erst["tage_noetig"] == 4, f"B seed {seed}: Start {erst}")
    pl, netto, tage, z = zyklus(150000, 2, start_b, 1466.72, {"t1": 1466.72}, rnd)
    arten = [p["art"] for p in pl]
    pruef(arten[:2] == ["klein", "klein"] and len(pl) == 4, f"B seed {seed}: Ablauf {arten}")
    pruef(abs(start_b + netto - 167441.12) < 0.005, f"B seed {seed}: Ende {round(start_b + netto, 2)} statt 167.441,12")
    pruef(all(p["tp"] <= 2850 + 1e-6 for p in pl), f"B seed {seed}: TP über dem Deckel")
    pruef(max(tage.values()) <= 0.5 * netto + 1e-6, f"B seed {seed}: Consistency")
    pruef(sk.sk_tage_ok(tage, 350) >= 5, f"B seed {seed}: Tage")

    # C · 100k Z 5.000: 3 kleine, dann ein Trade −2.800 → R ≈ 6.750, Deckel 2.375 → 3 Trades, Ziel genau
    def verlust4(i, p):
        return -2800.0 if i == 3 else None
    pl, netto, tage, z = zyklus(100000, 2, 110000, 0.0, {}, rnd, ergebnis=verlust4)
    nach = pl[4:]
    r_nach = pl[4]["rest"]
    pruef(5000 + 2800 - 1260 - 0.01 <= r_nach <= 5000 + 2800 - 1110 + 0.01, f"C seed {seed}: Rest nach Verlust {r_nach}")
    pruef(len(nach) == 3 and all(p["art"] in ("pump", "rest") for p in nach), f"C seed {seed}: nach Verlust {[p['art'] for p in nach]}")
    pruef(abs(netto - 5000) < 0.005, f"C seed {seed}: Ende {netto} statt +5.000")
    pruef(all(p["tp"] <= 2375 + 1e-6 for p in nach), f"C seed {seed}: TP über dem Deckel {[p['tp'] for p in nach]}")
    pruef(max(tage.values()) <= 0.5 * netto + 1e-6, f"C seed {seed}: Consistency nach Verlust")

    # SL: 60–90 % des Daily Loss, höchstens Abstand − 50
    for dll in (3500, 2500, 1750, 4000, 3000):
        s, _g = sk.sk_sl(CFG, dll, 20000, rnd)
        pruef(s is not None and 0.6 * dll - 1 <= s <= 0.9 * dll, f"SL {dll}: {s}")
    s, _g = sk.sk_sl(CFG, 3500, 1000, rnd)
    pruef(s is not None and s <= 950, f"SL am Boden gedeckelt: {s}")
    pruef(sk.sk_sl(CFG, 3500, 120, rnd)[0] is None, "SL unter 100 $ → kein Trade")

# Hedge: 112k, Boden 100.100 → 11.900 $ → 2.380 €
off, ab = sk.sk_hedge_offen(CFG, 112000, 100100)
pruef(off == 2380 and ab == 11900, f"Hedge 112k: {off} € / {ab} $")
pruef(sk.sk_hedge_offen(CFG, 100000, 100100)[0] is None, "Balance unter dem Boden → kein Hedge")

# Ziel erreicht → nichts mehr planen; nie über das Ziel
p = sk.sk_tag_tp(CFG, 100000, 5000, 5000.0, {"a": 400, "b": 400, "c": 400, "d": 1900, "e": 1900}, random.Random(1))
pruef(p["aktion"] == "ziel", "Ziel erreicht → aktion ziel")
p = sk.sk_tag_tp(CFG, 100000, 5000, 4700.0, {"a": 400, "b": 400, "c": 400, "d": 1700, "e": 1800}, random.Random(1))
pruef(p["art"] == "rest" and abs(p["tp"] - 300) < 0.005, f"Rest 300 → genau 300: {p}")

# Toleranz (Prüfer 20.11.): Rest 50 $, alle Tage da, harte Bedingung erfüllt → Ziel erreicht; harte Bedingung NICHT erfüllt → Trade mit TP ≥ 100
fuenf = {"a": 400, "b": 400, "c": 400, "d": 1900, "e": 1850}
p = sk.sk_tag_tp(CFG, 100000, 5000, 4950.0, fuenf, random.Random(1), z_min=3600)
pruef(p["aktion"] == "ziel", f"Rest 50 $ mit erfüllter Bedingung → ziel: {p}")
p = sk.sk_tag_tp(CFG, 100000, 3600, 3570.0, {"a": 400, "b": 400, "c": 400, "d": 1200, "e": 1170}, random.Random(1), z_min=3600)
pruef(p["aktion"] == "planen" and p["tp"] >= 100, f"harte Bedingung fehlt 30 $ → Trade mit TP ≥ 100: {p}")
# Tage (Prüfer 20.11.): Rest 425, noch 2 Tage nötig → Ziel angehoben, zwei kleine Trades statt Ziel ohne Tage
p = sk.sk_tag_tp(CFG, 100000, 5000, 4575.0, {"a": 400, "b": 400, "c": 3775}, random.Random(1), z_min=3600)
pruef(p["art"] == "klein" and p["z_eff"] > 5000 and p["hinweis"] and 4575 + p["tp"] + 370 <= p["z_eff"] + 1e-6,
      f"Tage-Anhebung: {p}")

# Prüfer 2 (20.11.): nie „Ziel“, solange Tage fehlen — auch bei Netto ≥ Ziel (Hand-Trade) bzw. Rest ≤ Toleranz; kein TP unter 100 $
vier = {"a": 400, "b": 400, "c": 400, "d": 400}
for netto, tage_x in ((4910.0, vier), (5000.0, {"a": 400, "b": 400, "c": 4200}), (5600.0, {"a": 400, "b": 400, "c": 4800}), (4970.0, {"a": 400, "b": 400, "c": 400})):
    p = sk.sk_tag_tp(CFG, 100000, 5000, netto, tage_x, random.Random(3), z_min=3600)
    pruef(p["aktion"] == "planen" and p["tp"] >= 100 and netto + p["tp"] <= p["z_eff"] + 1e-6 and p["hinweis"],
          f"Tage fehlen, Netto {netto} → muss planen (TP ≥ 100, Ziel angehoben): {p}")
# großer Schlupf (bis 90 $ unter dem TP, Trade zählt dann evtl. nicht als Tag): Zyklus endet trotzdem mit 5 Tagen ≥ Schwelle
for seed in range(SEEDS):
    rnd = random.Random(seed * 104729 + BASIS)
    for g, nr, prob, start in ((100000, 1, True, 112288.54), (150000, 2, True, 161441.12), (100000, 2, False, 110105.82)):
        pl, netto, tage, z = zyklus(g, nr, start, 0.0, {}, rnd, ergebnis=lambda i, p: round(p["tp"] - rnd.uniform(0, 90), 2), probation=prob, max_tage=30)
        schw = 300 if g == 100000 else 350
        pruef(sk.sk_tage_ok(tage, schw) >= 5 and all(p["tp"] >= 100 - 1e-6 for p in pl) and len(pl) < 30,
              f"Schlupf 90 {g}/{nr} seed {seed}: Tage {sk.sk_tage_ok(tage, schw)}, TPs {[p['tp'] for p in pl]}")

# Consistency: früherer Tag 3.000 > 50 % von 5.000 → Ziel 6.000
p = sk.sk_tag_tp(CFG, 100000, 5000, 3000.0, {"a": 3000}, random.Random(1))
pruef(p["z_eff"] == 6000 and p["hinweis"], f"Consistency-Anhebung: {p}")

if fehler:
    print("FEHLER:\n  " + "\n  ".join(fehler[:20]) + (f"\n  … {len(fehler)} insgesamt" if len(fehler) > 20 else ""))
    print(f"Basis-Seed {BASIS} (nachstellen: SK_SEED={BASIS} python3 tools/selftest_striking.py)")
    raise SystemExit(1)
print(f"OK selftest_striking (Seed {BASIS}): Ziele mit/ohne Probation, A/B/C + Schlupf über {SEEDS} Seeds, SL, Hedge, Toleranz, Tage, Consistency")
