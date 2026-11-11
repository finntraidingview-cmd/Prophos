#!/usr/bin/env python3
"""Selbsttest FT1 (Finn 11.11.2026 20:53): FTMO Futures 50k im Funded-Planer Futures — Ziel [4.000, 4.500] und Kontrakte 50 % 1 NQ / 50 % 2 NQ, nur per
Einstellung (sql/2026-11-11_ft1_ftmo_futures_ziel_lots.sql). Rechnet mit den echten Funktionen (fdp_konto_rechnen im Rest-Modus, fdp_ziel_gewinn,
fdp_kontrakte, fdp_hedge): Ziel in der Spanne, Verteilung ~50/50, TP/SL in $ gleich, Punkte = $ ÷ (20 × Kontrakte), Fusion-Hedge in € gleich,
Läufe mit {"1": 1} bitgleich zu vorher (gleicher Zufalls-Verbrauch). Ohne Netz, Platzhalter-IDs. Aufruf: python3 tools/selftest_ft1_ftmo_futures.py"""
import os
import random
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


REGEL = {"namen": ["ftmofutures"], "an": True, "symbol": "NQ", "lock_usd": 0, "tp_modus": "rest"}
ALT = {"dd": 3000, "sl": [750, 850], "daily_usd": 1000, "hedge_eur": 450, "kontrakte": {"1": 1}, "kosten_eur": 120, "ziel_gewinn": [4750, 5000]}
NEU = dict(ALT, kontrakte={"1": 0.5, "2": 0.5}, ziel_gewinn=[4000, 4500])
G = 50000.0
R = lambda jg, bal, kid, rnd=None, kt=None: app.fdp_konto_rechnen(REGEL, jg, None, bal, G, 120.0, G, G, rnd, {}, kt_fest=kt, konto_id=kid, zyklus=1)   # noqa: E731

print("1) Ziel [4.000, 4.500] je Konto fest")
ids = [f"c0000000-0000-0000-0000-{i:012d}" for i in range(400)]
z = [app.fdp_ziel_gewinn(NEU, k, 1) for k in ids]
check(all(4000 <= x <= 4500 for x in z) and min(z) < 4100 and max(z) > 4400, f"400 Konten: Ziel immer in 4.000–4.500, Spanne genutzt ({min(z):.0f}–{max(z):.0f})")
check(app.fdp_ziel_gewinn(NEU, ids[7], 1) == app.fdp_ziel_gewinn(NEU, ids[7], 1), "fest je Konto (kein Hin und Her zwischen den Takten)")
u_alt = [(app.fdp_ziel_gewinn(ALT, k, 1) - 4750) / 250 for k in ids[:50]]
u_neu = [(app.fdp_ziel_gewinn(NEU, k, 1) - 4000) / 500 for k in ids[:50]]
check(all(abs(a - b) < 0.01 for a, b in zip(u_alt, u_neu)), "dieselbe Lage in der Spanne wie vorher (gleicher Würfel je Konto, nur neue Grenzen)")
w = R(NEU, 50000.0, ids[3])
check(w["aktion"] == "planen" and w["tp"] == round(w["ziel"] - 50000.0, 2) and 4000 <= w["tp"] <= 4500, f"frisches Konto: TP = Rest bis Ziel ({w['tp']} $, Ziel {w['ziel']})")
check(R(NEU, 50000.0 + 4600, ids[3])["aktion"] == "ziel", "Balance über dem neuen Ziel → „Ziel erreicht → Winning Days“")

print("2) Kontrakte 50 % 1 NQ / 50 % 2 NQ")
rnd = random.Random("ft1")
kts = [R(NEU, 49000.0 + i, ids[i % 400], rnd)["kontrakte"] for i in range(2000)]
n1, n2 = kts.count(1), kts.count(2)
check(set(kts) == {1, 2} and 0.45 < n1 / len(kts) < 0.55, f"2.000 Pläne: 1 NQ {n1} / 2 NQ {n2} (≈ 50/50), nie mehr als 2")
check(app.fdp_kontrakte({"1": 0.5, "2": 0.5}, None, None) == 1, "ohne Würfel der kleinere Wert (gleich wahrscheinlich → 1)")

print("3) TP/SL in $, Punkte aus den Kontrakten, Hedge in € gleich")
abw = []
for i in range(200):
    bal = 47000.0 + 30 * i
    w1 = R(NEU, bal, ids[i], random.Random(f"x{i}"), kt=1)
    w2 = R(NEU, bal, ids[i], random.Random(f"x{i}"), kt=2)
    if w1["aktion"] != "planen" or w2["aktion"] != "planen":
        if w1["aktion"] != w2["aktion"]:
            abw.append((bal, "aktion", w1["aktion"], w2["aktion"]))
        continue
    gleich = all(w1[k] == w2[k] for k in ("tp", "sl", "ziel", "offen_eur", "hedge_eur", "hedge_sl_eur", "hedge_tp_eur", "slave_risk"))
    pkt = abs(w1["tp_pkt"] - round(w1["tp"] / 20, 2)) < 0.011 and abs(w2["tp_pkt"] - round(w2["tp"] / 40, 2)) < 0.011 and abs(w2["sl_pkt"] - round(w2["sl"] / 40, 2)) < 0.011
    if not (gleich and pkt and w1["kontrakte"] == 1 and w2["kontrakte"] == 2):
        abw.append((bal, {k: (w1.get(k), w2.get(k)) for k in ("tp", "sl", "hedge_eur", "hedge_sl_eur", "hedge_tp_eur", "slave_risk", "multiplier", "tp_pkt")}))
check(not abw, f"200 Balancen: TP, SL, Ziel, Hedge-€ (am TP/SL), Slave-Risiko gleich; Punkte = $ ÷ (20 × Kontrakte) ({abw[:2]})")
w1, w2 = R(NEU, 49000.0, ids[1], random.Random("y"), kt=1), R(NEU, 49000.0, ids[1], random.Random("y"), kt=2)
l1, l2 = round(w1["multiplier"] * 1, 2), round(w2["multiplier"] * 2, 2)
check(w1["multiplier"] == w2["multiplier"] and abs(l2 - 2 * l1) < 0.02 and l2 <= app.LOTS_DECKEL,
      f"Multiplikator je Kontrakt gleich → Fusion-Lots doppelt bei 2 NQ (halbe Punkte, gleiche €): {l1} → {l2} Lot, unter dem Lots-Deckel {app.LOTS_DECKEL:g}")

print("4) Vorher bitgleich (gleicher Zufalls-Verbrauch)")
ra, rb = random.Random("z"), random.Random("z")
alt = [R(ALT, 48000.0 + 50 * i, ids[i], ra) for i in range(50)]
alt2 = [R(ALT, 48000.0 + 50 * i, ids[i], rb) for i in range(50)]
check(alt == alt2 and all(x.get("kontrakte") in (1, None) for x in alt), "{\"1\": 1} wie vorher: immer 1 NQ")
ra, rb = random.Random("z"), random.Random("z")
a = [R(ALT, 48000.0 + 50 * i, ids[i], ra).get("sl") for i in range(50)]
b = [R(dict(ALT, kontrakte={"1": 0.5, "2": 0.5}), 48000.0 + 50 * i, ids[i], rb).get("sl") for i in range(50)]
check(a == b, "neue Verteilung verbraucht genauso viele Würfe — SL-Würfel und alle weiteren Werte im Lauf bleiben gleich")

print("5) SQL-Datei")
sq = open(os.path.join(WURZEL, "sql", "2026-11-11_ft1_ftmo_futures_ziel_lots.sql"), encoding="utf-8").read()
check("'{je_groesse,50000,ziel_gewinn}', '[4000, 4500]'::jsonb" in sq and "'{je_groesse,50000,kontrakte}', '{\"1\": 0.5, \"2\": 0.5}'::jsonb" in sq
      and "f->'namen' ? 'ftmofutures'" in sq and re.search(r"where r\.id = 1", sq), "setzt genau ziel_gewinn und kontrakte bei ftmofutures 50k, sonst nichts")
check("kontrakte" in app._FDP_GR_KT and "ziel_gewinn" in app._FDP_GR_FELDER, "dieselben Felder speichert der Reiter (feldweise, _FDP_GR_KT / _FDP_GR_FELDER)")

print()
print("FEHLER: " + ", ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
