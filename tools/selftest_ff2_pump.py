#!/usr/bin/env python3
"""Selbsttest FF2 „Pump in 2 Trades“ im Funded-Planer Futures (Finn 11.11.2026: „Hochpumpen in einem einzigen Tag … zu 70 % ein einziger Trade, zu 30 % zwei
Trades“; Lucid „eins zu eins die gleiche Logik, nur bei Lucid halt Daily Drawdown … von 2,7k“). Konstrukt FINAL + Schnittstelle: side-session-notes
2026-11-11_FF2_tradeify_pump_konstrukt.md / 2026-11-11_FF2_schnittstelle_backend.md (§5 Funktionen).

Rechnet die REIN RECHNENDEN Funktionen aus app.py ohne Netz/DB (Muster selftest_zt1_ziel_toleranz.py). Solange das Backend fehlt, läuft der Test rot und
nennt je fehlender Funktion „fehlt: <name>“ — das ist der erwartete Stand vor dem Bau.

Schnittstelle (app.py, alle rein rechnend):
  fdp_pump_tag_wurf(jg, konto_id, zyklus, tag) -> {"weg": "ein"|"zwei", "ziel_gewinn": float}   fest je Konto × Zyklus × CME-Tag (Hash, kein Zufall)
  fdp_pump_trade1(jg, weg, balance, start, liq, ziel, rnd, tag_verlust=0.0)
      -> {"aktion": "planen", "tp", "sl" (None = ohne SL), "risiko", "kontrakte", "hedge_eur", "kette" (None | {von, nr, rolle})} | {"aktion": "aus", "grund"}
  fdp_pump_trade2(jg, t1, balance_start, balance_end, liq_eod, ziel, rnd)
      t1 = {"tp": TP von Trade 1}; -> ({"tp", "sl", "risiko", "kontrakte", "hedge_eur", "e1", "kette"}, None) | (None, grund)
  fdp_pump_t2_start(jg, t1_ende_utc, rnd) -> datetime (UTC) | None       Start zufällig in [Ende + t2_abstand_min, t2_bis Dubai]; Fenster < t2_min_fenster_min → None
  fdp_pump_hedge(jg, risiko) -> € | None                                hedge_eur ÷ hedge_auf_usd × Risiko; Satz fehlt → None
Regeln, die der Test festhält (aus dem Konstrukt):
  · Risiko = SL; ohne SL bzw. SL hinter der Liq = Abstand zur Liq; mit Daily Loss (Lucid) höchstens daily_usd − Tagesverlust (Trade 2: E1 + daily_usd)
  · sl_hinter_liq aus → SL höchstens Balance − Liq − FDP_LIQ_PUFFER (50); an → SL bleibt, Risiko ist der Liq-Abstand
  · Trade 2: TP = Ziel − Balance nach Trade 1; SL = E1 (Break-even auf den Tagesstart) zu t2_sl_be_pct %, sonst ohne
  · Trade 1 geblowt (≤ Liq + 50) → kein Trade 2; Trade 1 nicht am TP (E1 < TP − 100) → „Tag zu“; Ziel schon erreicht → kein Trade 2
  · Ein-Trade-Weg und Trade 1 von „ein“ tragen keine kette; Trade 1/2 von „zwei“ tragen {von: 2, nr: 1|2, rolle: "haupt"}
Platzhalter-Konten, keine echten Kennungen.

Aufruf:  python3 tools/selftest_ff2_pump.py"""
import hashlib
import os
import random
import re
import sys
from datetime import datetime, timezone, timedelta

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# SELFTEST_APP=<Datei>: gegen eine andere Datei prüfen (z. B. die Referenz-Umsetzung vor dem Einbau)
app = open(os.environ.get("SELFTEST_APP") or os.path.join(W, "app.py"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


try:
    from zoneinfo import ZoneInfo
except ImportError:   # pragma: no cover
    ZoneInfo = None
ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "random": random, "hashlib": hashlib, "ZoneInfo": ZoneInfo}


def lade(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^\S)", app, re.S | re.M)
    if not m:
        raise LookupError(name)
    exec(m.group(0), ns)


def ruf(fn, *a, **k):
    for _ in range(80):
        try:
            return ns[fn](*a, **k) if callable(ns.get(fn)) else ns[fn]
        except (NameError, KeyError) as e:
            lade(str(e).split("'")[1])
    raise RuntimeError(fn)


SCHNITTSTELLE = ("fdp_pump_tag_wurf", "fdp_pump_trade1", "fdp_pump_trade2", "fdp_pump_t2_start", "fdp_pump_hedge")
fehlt = []
for n in SCHNITTSTELLE:
    try:
        lade(n)
    except LookupError:
        fehlt.append(n)
if fehlt:
    for n in fehlt:
        print(f"✗ fehlt: {n} (app.py) — FF2-Backend noch nicht gebaut")
    print(f"\nROT: {len(fehlt)} von {len(SCHNITTSTELLE)} Funktionen der Schnittstelle fehlen (erwartet vor dem Bau).")
    sys.exit(1)

# ── Regel-Werte wie sql/2026-11-11_ff2_pump_modell.sql (Tradeify) — einzelne Fälle setzen Spannen fest, damit der Würfel nichts verdeckt
TR = {"ziel_gewinn": [13000, 19000], "dd": 4500, "hedge_eur": 850, "hedge_auf_usd": 4500, "pump2_pct": 30,
      "ein_kontrakte": {"3": 1}, "ein_sl": [4500, 4700], "t1_von": "03:00", "t1_bis": "16:00", "t1_tp": [4000, 8000], "t1_kontrakte": {"2": 0.5, "3": 0.5},
      "t1_sl": [4500, 4700], "sl_kein_pct": 50, "sl_hinter_liq": True, "t2_bis": "18:30", "t2_abstand_min": [2, 5], "t2_min_fenster_min": 10,
      "t2_kontrakte": {"3": 1}, "t2_sl_be_pct": 50}
LU = dict(TR, daily_usd=2700, ein_sl=[2600, 2700], t1_sl=[2600, 2700], sl_hinter_liq=False, hedge_eur=None)
fest = lambda base, **k: dict(base, **k)   # noqa: E731
R = lambda: random.Random(7)   # noqa: E731
START, LIQ = 150000.0, 145500.0
satz = 850 / 4500

# ── Weg- und Ziel-Würfel: fest je Konto × Zyklus × Tag, ~30 % zwei Trades
w1 = ruf("fdp_pump_tag_wurf", TR, "konto-0001", 1, "2026-11-12")
check(w1 == ruf("fdp_pump_tag_wurf", TR, "konto-0001", 1, "2026-11-12"), "Würfel fest: gleiches Konto, Zyklus, Tag → gleicher Weg und gleiches Ziel (5-min-Takt würfelt nicht neu)")
check(w1["weg"] in ("ein", "zwei") and 13000 <= w1["ziel_gewinn"] <= 19000, f"Würfel in den Grenzen ({w1})")
n_zwei = sum(ruf("fdp_pump_tag_wurf", TR, f"konto-{i:04d}", 1, "2026-11-12")["weg"] == "zwei" for i in range(2000))
check(500 <= n_zwei <= 700, f"Weg „zwei“ bei ~30 % der Konten ({n_zwei} von 2.000)")
check(sum(ruf("fdp_pump_tag_wurf", fest(TR, pump2_pct=0), f"konto-{i:04d}", 1, "2026-11-12")["weg"] == "zwei" for i in range(200)) == 0, "pump2_pct 0 → immer ein Trade")
check(sum(ruf("fdp_pump_tag_wurf", fest(TR, pump2_pct=100), f"konto-{i:04d}", 1, "2026-11-12")["weg"] == "zwei" for i in range(200)) == 200, "pump2_pct 100 → immer zwei Trades")
# Break-even-Tag → am nächsten Tag von vorn: neuer Tag = neuer Würfel (Ziel und Weg), bei vielen Konten mindestens einmal anders
# FF2b: Zielniveau fest je Konto × Zyklus (bleibt bis erreicht), Weg je Tag neu; neuer Payout-Zyklus = neues Niveau
gleich = sum(ruf("fdp_pump_tag_wurf", TR, f"konto-{i:04d}", 1, "2026-11-12")["ziel_gewinn"] == ruf("fdp_pump_tag_wurf", TR, f"konto-{i:04d}", 1, "2026-11-13")["ziel_gewinn"] for i in range(50))
check(gleich == 50, f"Zielniveau bleibt über die Tage gleich (FF2b: {gleich} von 50 Konten)")
weg_anders = sum(ruf("fdp_pump_tag_wurf", TR, f"konto-{i:04d}", 1, "2026-11-12")["weg"] != ruf("fdp_pump_tag_wurf", TR, f"konto-{i:04d}", 1, "2026-11-13")["weg"] for i in range(200))
check(weg_anders >= 40, f"Weg 70/30 je Tag neu ({weg_anders} von 200 Konten anders)")
z_neu = sum(ruf("fdp_pump_tag_wurf", TR, f"konto-{i:04d}", 1, "2026-11-12")["ziel_gewinn"] != ruf("fdp_pump_tag_wurf", TR, f"konto-{i:04d}", 2, "2026-11-12")["ziel_gewinn"] for i in range(50))
check(z_neu >= 45, f"neuer Payout-Zyklus → neues Zielniveau ({z_neu} von 50)")

# ── Hedge-Satz
check(abs(ruf("fdp_pump_hedge", TR, 4500) - 850) < 0.01, "Hedge 850 € auf 4.500 $ Risiko")
check(abs(ruf("fdp_pump_hedge", TR, 10500) - 1983.33) < 0.01, "Hedge 10.500 $ → 1.983,33 € (Satz 0,189)")
check(ruf("fdp_pump_hedge", LU, 2700) is None, "Lucid ohne Hedge-Satz → None")

# ── Fall 0: Weg „ein“ — TP = ganzes Ziel, 3 NQ, ohne kette
z16 = START + 16000
r0 = ruf("fdp_pump_trade1", fest(TR, sl_kein_pct=0, ein_sl=[4600, 4600]), "ein", START, START, LIQ, z16, R())
check(r0.get("aktion") == "planen" and r0["tp"] == 16000 and r0["kontrakte"] == 3 and r0.get("kette") is None, f"Fall 0: ein Trade TP 16.000, 3 NQ, keine kette ({r0})")
check(r0["sl"] == 4600 and abs(r0["risiko"] - 4500) < 0.01 and abs(r0["hedge_eur"] - 850) < 0.01,
      "Fall 0: SL 4.600 hinter der Liq erlaubt → Risiko = Liq-Abstand 4.500, Hedge 850 €")
r0b = ruf("fdp_pump_trade1", fest(TR, sl_kein_pct=100), "ein", START, START, LIQ, z16, R())
check(r0b["sl"] is None and abs(r0b["risiko"] - 4500) < 0.01, "Fall 0: SL-Würfel „ohne SL“ → sl None, Risiko bis zur Liq")
r0c = ruf("fdp_pump_trade1", fest(TR, sl_kein_pct=0, ein_sl=[4600, 4600], sl_hinter_liq=False), "ein", START, START, LIQ, z16, R())
check(r0c["sl"] == 4450, f"SL hinter Liq aus → SL höchstens Liq-Abstand − 50 = 4.450 ({r0c.get('sl')})")

# ── Fall A: Ziel 16.000, T1 3 NQ TP 6.000 → T2 TP 10.000
A = fest(TR, t1_tp=[6000, 6000], t1_kontrakte={"3": 1}, t1_sl=[4600, 4600], sl_kein_pct=0)
t1 = ruf("fdp_pump_trade1", A, "zwei", START, START, LIQ, z16, R())
check(t1.get("aktion") == "planen" and t1["tp"] == 6000 and t1["kontrakte"] == 3, f"Fall A: Trade 1 TP 6.000, 3 NQ ({t1})")
check((t1.get("kette") or {}).get("von") == 2 and (t1.get("kette") or {}).get("nr") == 1, "Fall A: Trade 1 trägt kette {von 2, nr 1}")
w, g = ruf("fdp_pump_trade2", fest(A, t2_sl_be_pct=0), {"tp": 6000}, START, 156000, LIQ, z16, R())
check(w is not None and w["tp"] == 10000 and w["kontrakte"] == 3 and w["sl"] is None, f"Fall A: Trade 2 TP 10.000, 3 NQ, ohne SL ({w or g})")
check(w is not None and abs(w["risiko"] - 10500) < 0.01 and abs(w["hedge_eur"] - 1983.33) < 0.01, "Fall A: ohne SL Risiko 4.500 + 6.000 = 10.500, Hedge 1.983,33 €")
check(w is not None and (w.get("kette") or {}).get("nr") == 2 and w.get("e1") == 6000, "Fall A: Trade 2 trägt kette {von 2, nr 2}, E1 6.000")
w, g = ruf("fdp_pump_trade2", fest(A, t2_sl_be_pct=100), {"tp": 6000}, START, 156000, LIQ, z16, R())
check(w is not None and w["sl"] == 6000 and abs(w["hedge_eur"] - 1133.33) < 0.01, "Fall A′: Break-even-SL = E1 6.000 → Hedge 1.133,33 €")
n_be = sum((ruf("fdp_pump_trade2", A, {"tp": 6000}, START, 156000, LIQ, z16, random.Random(s))[0] or {}).get("sl") == 6000 for s in range(400))
check(140 <= n_be <= 260, f"T2-SL-Würfel ~50 % Break-even ({n_be} von 400)")

# ── Fall B / C: Rest zum Ziel
w, g = ruf("fdp_pump_trade2", fest(TR, t2_sl_be_pct=0), {"tp": 8000}, START, 158000, LIQ, START + 13000, R())
check(w is not None and w["tp"] == 5000, f"Fall B: Ziel 13.000, T1 +8.000 → T2 TP 5.000 ({w or g})")
w, g = ruf("fdp_pump_trade2", fest(TR, t2_sl_be_pct=0), {"tp": 4000}, START, 154000, LIQ, START + 19000, R())
check(w is not None and w["tp"] == 15000, f"Fall C: Ziel 19.000, T1 +4.000 → T2 TP 15.000 ({w or g})")

# ── Fall D: T1 geblowt; „endet dazwischen“; Ziel schon erreicht
w, g = ruf("fdp_pump_trade2", A, {"tp": 6000}, START, LIQ, LIQ, z16, R())
check(w is None and g, f"Fall D: Trade 1 an der Liq → kein Trade 2 ({g})")
w, g = ruf("fdp_pump_trade2", A, {"tp": 6000}, START, 152000, LIQ, z16, R())
check(w is None and "Tag zu" in str(g), f"T1 endet weder am TP noch an der Liq (+2.000) → Tag zu ({g})")
w, g = ruf("fdp_pump_trade2", A, {"tp": 6000}, START, 147000, LIQ, z16, R())
check(w is None and "Tag zu" in str(g), f"T1 endet im Minus, nicht an der Liq → Tag zu ({g})")
w, g = ruf("fdp_pump_trade2", A, {"tp": 6000}, START, 155950, LIQ, z16, R())
check(w is not None and w["tp"] == 10050, f"T1 knapp am TP (−50 $ Schlupf) zählt als TP → T2 TP 10.050 ({w or g})")
w, g = ruf("fdp_pump_trade2", A, None, START, 156000, LIQ, z16, R())
check(w is None and g, f"Trade 1 ohne bekannten TP → kein Trade 2 ({g})")
w, g = ruf("fdp_pump_trade2", A, {"tp": 16000}, START, z16, LIQ, z16, R())
check(w is None and g, f"Ziel schon mit Trade 1 erreicht → kein Trade 2 ({g})")

# ── Rest kaum über dem T1-TP (Ziel 6.300, T1-TP 6.000) → ein Trade bis zum Ziel, keine kette
r6 = ruf("fdp_pump_trade1", A, "zwei", START, START, LIQ, START + 6300, R())
check(r6.get("aktion") == "planen" and r6["tp"] == 6300 and r6.get("kette") is None, f"Rest für Trade 2 < 500 $ → ein Trade TP = Ziel, ohne kette ({r6})")

# ── Fall E: nach BE-Tag wieder Trade 1 ab dem Tagesstart (Balance wie am Vortag)
t1e = ruf("fdp_pump_trade1", A, "zwei", START, START, LIQ, z16, R())
check(t1e.get("aktion") == "planen" and t1e["tp"] == 6000, "Fall E: nach Break-even-Tag (150.000) normaler Trade 1")

# ── Start Trade 2: zufällig bis 18:30 Dubai; Fenster zu klein oder nach 18:30 → None
dubai = (lambda h, m: datetime(2026, 11, 12, h - 4, m, tzinfo=timezone.utc))   # Dubai = UTC+4
s = ruf("fdp_pump_t2_start", TR, dubai(11, 0), R())
check(s is not None and dubai(11, 2) <= s <= dubai(18, 30), f"T2-Start zwischen Ende + 2 min und 18:30 Dubai ({s})")
starts = [ruf("fdp_pump_t2_start", TR, dubai(11, 0), random.Random(i)) for i in range(200)]
check(len({x.isoformat() for x in starts if x}) > 50, "T2-Start gestreut (nicht immer dieselbe Minute)")
check(ruf("fdp_pump_t2_start", TR, dubai(18, 40), R()) is None, "T1 endet nach 18:30 Dubai → kein Trade 2")
check(ruf("fdp_pump_t2_start", TR, dubai(18, 25), R()) is None, "Fenster unter 10 min (18:25 + 2–5 min bis 18:30) → kein Trade 2")
check(ruf("fdp_pump_t2_start", TR, datetime(2026, 11, 12, 21, 0, tzinfo=timezone.utc), R()) is None, "T1 endet nach Mitternacht Dubai (01:00, CME-Tag noch der alte) → kein Trade 2")
s2 = ruf("fdp_pump_t2_start", TR, datetime(2026, 11, 12, 7, 0), R())
check(s2 is not None and s2.tzinfo is not None and datetime(2026, 11, 12, 7, 2, tzinfo=timezone.utc) <= s2 <= dubai(18, 30), f"Ende ohne Zone = UTC (nie Ortszeit) ({s2})")

# ── Lucid: Daily Loss 2.700 ab Tagesstart
L = fest(LU, hedge_eur=850, t1_tp=[6000, 6000], t1_kontrakte={"3": 1}, t1_sl=[2650, 2650], sl_kein_pct=0)
l1 = ruf("fdp_pump_trade1", L, "zwei", START, START, LIQ, z16, R())
check(l1.get("aktion") == "planen" and l1["sl"] == 2650 and abs(l1["risiko"] - 2650) < 0.01, f"Lucid T1: SL 2.650 unter dem Daily Loss, Risiko 2.650 ({l1})")
l1b = ruf("fdp_pump_trade1", fest(L, sl_kein_pct=100), "zwei", START, START, LIQ, z16, R())
check(l1b["sl"] is None and abs(l1b["risiko"] - 2700) < 0.01, "Lucid T1 ohne SL: Risiko = Daily Loss 2.700 (nicht Liq 4.500)")
l1c = ruf("fdp_pump_trade1", fest(L, t1_sl=[3000, 3000]), "zwei", START, START, LIQ, z16, R())
check(l1c["sl"] is not None and l1c["sl"] <= 2700, f"Lucid: SL nie über dem Daily Loss ({l1c.get('sl')})")
l1d = ruf("fdp_pump_trade1", L, "zwei", START, START, LIQ, z16, R(), tag_verlust=1000)
check(l1d.get("aktion") == "planen" and l1d["sl"] is not None and l1d["sl"] <= 1700 and l1d["risiko"] <= 1700, f"Lucid: schon −1.000 heute → SL und Risiko höchstens Daily-Rest 1.700 ({l1d})")
l1e = ruf("fdp_pump_trade1", L, "zwei", START, START, LIQ, z16, R(), tag_verlust=2700)
check(l1e.get("aktion") == "aus", f"Lucid: Daily Loss heute schon ausgeschöpft → kein Plan ({l1e})")
lw, lg = ruf("fdp_pump_trade2", fest(L, t2_sl_be_pct=0), {"tp": 6000}, START, 156000, LIQ, z16, R())
check(lw is not None and lw["sl"] is None and abs(lw["risiko"] - 8700) < 0.01, f"Lucid T2 ohne SL: höchstens E1 + 2.700 = 8.700 Verlust ({lw or lg})")
lw, lg = ruf("fdp_pump_trade2", fest(L, t2_sl_be_pct=100), {"tp": 6000}, START, 156000, LIQ, z16, R())
check(lw is not None and lw["sl"] == 6000 and abs(lw["risiko"] - 6000) < 0.01, "Lucid T2 Break-even: SL = E1 6.000")
lx = ruf("fdp_pump_trade1", LU, "ein", START, START, LIQ, z16, R())
check(lx.get("aktion") == "aus" and "Hedge" in str(lx.get("grund")), f"Lucid ohne Hedge-Satz → kein Plan, Grund nennt den Hedge ({lx})")

# ── EINBAU in fdp_planen / Regeln / Takte (nur gegen app.py; die Referenz kennt diese Funktionen nicht)
if not os.environ.get("SELFTEST_APP"):
    for _n in ("GP_SLAVE_PPL", "FDP_NQ_PPL", "FDP_SLAVE_PPL", "FDP_TAGES_PUFFER", "FDP_BREAKEVEN_TOL_USD", "FDP_SL_MIN_USD", "FDP_LIQ_MIN_ABSTAND"):
        lade(_n)   # Standardwerte von Funktionsargumenten (fdp_hedge, fdp_sl_rest) — vor dem Laden der Funktionen
    REG_TR = {"name": "Tradeify", "namen": ["tradeify"], "an": False, "tp_modus": "pump2", "lock_usd": 100, "je_groesse": {"150000": dict(TR, kosten_eur=200)}}
    k = ruf("fdp_pump_konto", REG_TR, fest(TR, pump2_pct=100, ziel_gewinn=[16000, 16000], t1_tp=[6000, 6000], t1_kontrakte={"3": 1}, sl_kein_pct=100),
            START, START, START, 150000, "konto-0001", 1, "2026-11-12", R())
    check(k.get("aktion") == "planen" and k["tp"] == 6000 and k["kontrakte"] == 3 and k["sl"] is None, f"fdp_pump_konto: Trade 1 geplant ({k.get('aktion')}, {k.get('grund')})")
    check(abs(k.get("liq", 0) - 145500) < 0.01 and abs(k.get("master_risk", 0) - 4500) < 0.01, "fdp_pump_konto: Liq 145.500, Master-Risiko 4.500 (Liq-Abstand)")
    check(abs(k.get("slave_risk", 0) - 850) < 0.01 and abs(k.get("verhaeltnis", 0) - 850 / 4500) < 1e-4, "fdp_pump_konto: Fusion 850 € auf 4.500 $ (Satz 0,189 je $)")
    check(abs(k.get("hedge_tp_eur", 0) - 6000 * 850 / 4500) < 0.05, "fdp_pump_konto: Fusion am Master-TP = Satz × 6.000")
    check((k.get("kette") or {}).get("nr") == 1 and (k.get("pump") or {}).get("nr") == 1 and (k.get("pump") or {}).get("t2_bis") == "18:30", "fdp_pump_konto: kette + pump (nr 1, t2_bis)")
    k2 = ruf("fdp_pump_konto", REG_TR, fest(TR, pump2_pct=0, ziel_gewinn=[16000, 16000]), START + 16000, START + 16000, START, 150000, "konto-0001", 1, "2026-11-12", R())
    check(k2.get("aktion") == "ziel", f"fdp_pump_konto: Ziel erreicht → Winning Days ({k2.get('aktion')})")
    # FF2b: Niveau 16.000 fest — +13.500 ist NICHT erreicht (Rest 2.500), nach einem Verlusttag (−2.700) ist der TP Niveau − Balance = 18.700
    k2b = ruf("fdp_pump_konto", REG_TR, fest(TR, ziel_gewinn=[16000, 16000], pump2_pct=0), START + 13500, START + 13500, START, 150000, "konto-0001", 1, "2026-11-13", R())
    check(k2b.get("aktion") == "planen" and k2b["tp"] == 2500, f"Niveau 16.000 bei +13.500 → weiter, TP 2.500 (keine Untergrenzen-Regel mehr) ({k2b.get('aktion')}, {k2b.get('tp')})")
    k2d = ruf("fdp_pump_konto", REG_TR, fest(TR, ziel_gewinn=[16000, 16000], pump2_pct=0), START - 2700, START, START, 150000, "konto-0001", 1, "2026-11-13", R())
    check(k2d.get("aktion") == "planen" and k2d["tp"] == 18700 and abs(k2d["ziel"] - 166000) < 0.01, f"nach Verlusttag −2.700: Niveau 166.000 bleibt, TP 18.700 ({k2d.get('tp')})")
    k2e = ruf("fdp_pump_konto", REG_TR, fest(TR, ziel_gewinn=[16000, 16000], pump2_pct=0), START + 15920, START + 15920, START, 150000, "konto-0001", 1, "2026-11-13", R())
    check(k2e.get("aktion") == "ziel", f"80 $ unter dem Niveau (Schlupf am TP) → Ziel erreicht, kein Mini-Trade ({k2e.get('aktion')})")
    k2c = ruf("fdp_pump_konto", REG_TR, fest(TR, ziel_gewinn=[13000, 19000], pump2_pct=0), START + 8000, START + 8000, START, 150000, "konto-0001", 1, "2026-11-13", R())
    check(k2c.get("aktion") == "planen" and k2c["tp"] >= 5000, f"nach Teil-Tag (+8.000, Tag zu) → Rest bis zum festen Niveau ({k2c.get('aktion')}, TP {k2c.get('tp')})")
    # Liq nach Tagesend-Logik: Tageshoch intraday (156.000) zieht die Liq NICHT nach — peak_eod = Tagesstart 150.000
    k3 = ruf("fdp_pump_konto", REG_TR, fest(TR, pump2_pct=0, ziel_gewinn=[16000, 16000]), 156000, START, START, 150000, "konto-0001", 1, "2026-11-12", R())
    check(abs(k3.get("liq", 0) - 145500) < 0.01, f"Liq mit Tagesend-Hoch 150.000 bleibt 145.500 (nicht 151.500) ({k3.get('liq')})")
    from datetime import datetime as _dt
    mn = _dt(2026, 11, 12, 0, 0, tzinfo=ZoneInfo("Asia/Dubai"))
    check(ruf("fdp_pump_minute", "03:00", mn) == 180 and ruf("fdp_pump_minute", "16:00", mn) == 960, "fdp_pump_minute: 03:00 / 16:00 Dubai → 180 / 960 min")
    mb = _dt(2026, 11, 12, 0, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    check(ruf("fdp_pump_minute", "03:00", mb) == 0, "fdp_pump_minute: Fenster in deutscher Zeit — 03:00 Dubai = 00:00 Berlin (Winter)")
    # Regeln ändern: neue Schlüssel mit Grenzen, Einschalten ohne Hedge gesperrt
    REG = {"updated_at": "x", "firmen": [dict(REG_TR, je_groesse={"150000": dict(LU)})]}
    REG["firmen"][0]["name"] = "Lucid Trading"; REG["firmen"][0]["namen"] = ["lucidtrading", "lucid"]
    pa, f1 = ruf("fdp_regeln_aendern", REG, {"updated_at": "x", "firma": {"name": "Lucid Trading", "je_groesse": {"150000": {
        "pump2_pct": 25, "t1_tp": [4000, 7500], "t1_kontrakte": {"2": 0.4, "3": 0.6}, "sl_hinter_liq": True, "t2_bis": "18:15", "hedge_eur": 900}}}})
    z = (pa or {}).get("firmen", [{}])[0].get("je_groesse", {}).get("150000", {}) if pa else {}
    check(f1 is None and z.get("pump2_pct") == 25 and z.get("t1_tp") == [4000, 7500] and z.get("t1_kontrakte") == {"2": 0.4, "3": 0.6}
          and z.get("sl_hinter_liq") is True and z.get("t2_bis") == "18:15" and z.get("hedge_eur") == 900, f"Regeln ändern: Pump-Schlüssel angenommen ({f1})")
    for body, was in [({"t2_bis": "25:00"}, "Uhrzeit 25:00"), ({"pump2_pct": 120}, "Prozent 120"), ({"t1_tp": [9000, 8000]}, "von > bis"),
                      ({"t1_kontrakte": {"2": 0.4, "3": 0.4}}, "Summe 80 %"), ({"sl_hinter_liq": "ja"}, "bool als Text"), ({"t1_von": "17:00"}, "Start ab nach Start bis")]:
        _p, f = ruf("fdp_regeln_aendern", REG, {"updated_at": "x", "firma": {"name": "Lucid Trading", "je_groesse": {"150000": body}}})
        check(_p is None and f, f"Regeln ändern lehnt ab: {was} ({f})")
    _p, f = ruf("fdp_regeln_aendern", REG, {"updated_at": "x", "firma": {"name": "Lucid Trading", "an": True}})
    check(_p is None and "Hedge" in str(f), f"Lucid ohne Hedge-Satz lässt sich nicht einschalten ({f})")
    # fdp_pump_echt: Puls-Endlesung wie tt_echt, bei Orbit V3 auch die Userscript-Endlesung (reader), nie relativ
    pv3 = {"route": "tvv2", "orbit_v3": True, "mt5_baseline": {"tv": {"balance_start": 150000}, "final": {"balance_end": 156000, "balance_quelle": "reader"}}}
    check(ruf("fdp_pump_echt", pv3) == (150000.0, 156000.0), "Orbit V3: Userscript-Endlesung (reader) gilt als genau")
    check(ruf("fdp_pump_echt", dict(pv3, orbit_v3=False)) is None, "Orbit V2 ohne Puls-Endlesung: reader zählt nicht")
    check(ruf("fdp_pump_echt", {"route": "tvv2", "orbit_v3": True, "mt5_baseline": {"tv": {"balance_start": 150000},
                                "final": {"balance_end": 6000, "balance_quelle": "reader", "balance_relativ": True}}}) is None, "relative Balance zählt nie")
    check(ruf("fdp_pump_echt", {"route": "tvv2", "orbit_v3": True, "mt5_baseline": {"tv": {"balance_start": 150000},
                                "final": {"balance_end": 156000, "quelle": "puls"}}}) == (150000.0, 156000.0), "Puls-Endlesung gilt wie bisher")

    # fdp_pump_tick mit Platzhaltern für DB, Patch und Alarm (Takt für Trade 2)
    import copy
    J = datetime(2026, 11, 12, 8, 0, tzinfo=timezone.utc)   # 12:00 Dubai
    REG_T = {"aktiv": True, "firmen": [dict(REG_TR, an=True, je_groesse={"150000": fest(TR, t2_sl_be_pct=0, t2_abstand_min=[2, 2])})]}
    KONTO = {"id": "konto-1", "user_id": "u-1", "name": "150k FTDFYSLX0000000001 → Funded", "firm": "Tradeify", "account_type": "funded", "max_drawdown": 4500,
             "starting_balance": 150000, "tv_balance": 156000, "tv_balance_at": "2026-11-12T07:51:00Z"}
    def t1(pid, ende_utc, be, lesen_bis="2026-11-12T14:30:00Z", t2=None, quelle="reader", auto=True):
        fin = {"balance_end": be, "balance_quelle": quelle} if be else {}
        return {"id": pid, "user_id": "u-1", "master_account_id": "konto-1", "master_firm": "Tradeify", "master_name": KONTO["name"], "status": "review",
                "route": "tvv2", "orbit_v3": True, "started_at": "2026-11-12T06:40:00Z", "ended_at": ende_utc, "completed_at": None, "master_tp": 6000,
                "auto_bestaetigt_at": "2026-11-12T00:10:00Z" if auto else None,
                "mt5_baseline": {"tv": {"balance_start": 150000}, "final": fin, "kette": {"von": 2, "nr": 1, "rolle": "haupt", "lesen_bis": lesen_bis},
                                 "funded_plan": {"zyklus": 1, "start": 150000, "ziel": 166000,
                                                 "pump": dict({"weg": "zwei", "nr": 1, "ziel_gewinn": 16000, "tag": "2026-11-12"}, **({"t2": t2} if t2 else {}))}}}
    def lauf(plaene, jetzt=J, offen=(), nachfolger=(), belegt=(), insert_id="neu-1"):
        log = {"insert": [], "patch": [], "alarm": []}
        def sb_select(tab, prm):
            if tab == "trade_plans" and "mt5_baseline->kette->>vor" in prm:
                return list(nachfolger)
            if tab == "trade_plans" and prm.get("status") == "in.(planned,open)" and "user_id" in prm:
                return list(belegt)
            if tab == "trade_plans" and prm.get("status") == "in.(planned,open)":
                return list(offen)
            if tab == "trade_plans":
                return copy.deepcopy(plaene)
            if tab == "accounts":
                return [dict(KONTO)]
            return []
        ns.update({"sb_select": sb_select, "sb_insert": lambda tab, z: (log["insert"].append(z), {"id": insert_id} if insert_id else {})[1],
                   "_tt_patch": lambda pid, patch, key="kette": (log["patch"].append((pid, key, patch)), True)[1],
                   "alarm_senden": lambda *a, **k: log["alarm"].append((a, k)), "_fdp_regeln_laden": lambda: REG_T, "ap_unt_kontext": lambda frisch=False: None,
                   "fd_unt_reg": lambda reg, art, uid, ktx=None, streng=False: reg, "_liq_verlauf_laden": lambda ids, streng=False: [],
                   "fusion_sppl": lambda m, u: 0.85, "_wd_futures_frontcode": lambda j=None: "Z6"})
        import contextlib, io
        for _ in range(60):   # fdp_pump_tick fängt Fehler je Plan selbst ab → fehlende Hilfen aus der Meldung nachladen und den Lauf wiederholen
            for v in log.values():
                v.clear()
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                res = ruf("fdp_pump_tick", jetzt, random.Random(3))
            m = re.search(r"NameError: name '(\w+)' is not defined", buf.getvalue())
            if not m:
                break
            lade(m.group(1))
        return res, log
    e, log = lauf([t1("t1-a", "2026-11-12T07:50:00Z", 156000)])
    z = log["insert"][0] if log["insert"] else {}
    zf = ((z.get("mt5_baseline") or {}).get("funded_plan") or {})
    check(len(log["insert"]) == 1 and z.get("master_tp") == 10000 and z.get("master_contracts") == 3 and z.get("master_sl") is None,
          f"Takt: Trade 2 angelegt, TP 10.000, 3 NQ, ohne SL ({len(log['insert'])} · {z.get('master_tp')} · {z.get('master_sl')})")
    check(((z.get("mt5_baseline") or {}).get("kette") or {}).get("nr") == 2 and ((z.get("mt5_baseline") or {}).get("kette") or {}).get("vor") == "t1-a"
          and (zf.get("pump") or {}).get("nr") == 2 and (zf.get("pump") or {}).get("t1_plan_id") == "t1-a", "Takt: Trade 2 trägt kette {nr 2, vor T1} und pump {nr 2, t1_plan_id}")
    check(z.get("start_um") and z.get("auto_bestaetigt_at") and "2026-11-12T08:" <= str(z.get("start_um")) <= "2026-11-12T14:30", f"Takt: bestätigt wie Trade 1, Start bis 18:30 Dubai ({z.get('start_um')})")
    check(abs((z.get("slave_risk") or 0) - 850 / 4500 * 10500) < 0.05 and z.get("orbit_v3") is True and z.get("route") == "tvv2", f"Takt: Fusion auf 10.500 $ Risiko (Satz × Liq-Abstand) ({z.get('slave_risk')})")
    check(any(k == "funded_plan" and (pa.get("pump") or {}).get("t2", {}).get("status") == "angelegt" for _p, k, pa in log["patch"]) and not log["alarm"],
          "Takt: Entscheidung an Trade 1 (pump.t2 angelegt), keine Meldung")
    e, log = lauf([t1("t1-b", "2026-11-12T07:50:00Z", 152000)])
    check(not log["insert"] and any(k == "kette" and pa.get("tagesende") for _p, k, pa in log["patch"]) and len(log["alarm"]) == 1,
          "Takt: Trade 1 nicht am TP → kein Trade 2, Tagesende an Trade 1, eine ⚪-Meldung")
    e, log = lauf([t1("t1-c", "2026-11-12T07:50:00Z", None)])
    check(not log["insert"] and not log["patch"] and not log["alarm"], "Takt: Lesung fehlt noch (lesen_bis in der Zukunft) → warten, nichts schreiben")
    e, log = lauf([t1("t1-d", "2026-11-12T07:50:00Z", None, lesen_bis="2026-11-12T07:55:00Z")])
    check(not log["insert"] and any(k == "kette" and pa.get("tagesende") for _p, k, pa in log["patch"]) and len(log["alarm"]) == 1, "Takt: keine Lesung bis lesen_bis → Tag zu + ⚪")
    e, log = lauf([t1("t1-e", "2026-11-12T14:40:00Z", 156000)], jetzt=datetime(2026, 11, 12, 14, 45, tzinfo=timezone.utc))
    check(not log["insert"] and len(log["alarm"]) == 1, "Takt: Trade 1 endete nach 18:30 Dubai → kein Trade 2, ⚪")
    e, log = lauf([t1("t1-f", "2026-11-12T07:50:00Z", 156000, t2={"status": "angelegt"})])
    check(not log["insert"] and not log["patch"], "Takt: schon entschieden (pump.t2) → nie ein zweiter Trade 2")
    e, log = lauf([t1("t1-g", "2026-11-12T07:50:00Z", 156000)], offen=[{"id": "x"}])
    check(not log["insert"], "Takt: anderer offener Plan am Konto → kein Trade 2")

    e, log = lauf([t1("t1-h", "2026-11-12T07:50:00Z", 156000)], jetzt=datetime(2026, 11, 13, 6, 0, tzinfo=timezone.utc))
    check(not log["insert"] and len(log["alarm"]) == 1, "Takt läuft erst am Folgetag wieder → Pump-Tag vorbei, kein Trade 2 aus der gestrigen Balance")
    e, log = lauf([t1("t1-i", "2026-11-12T07:50:00Z", 156000)], nachfolger=[{"id": "t2-da", "status": "review"}])
    check(not log["insert"] and any(k == "funded_plan" and (pa.get("pump") or {}).get("t2", {}).get("plan_id") == "t2-da" for _p, k, pa in log["patch"]) and not log["alarm"],
          "Nachfolger steht schon (Patch war gescheitert) → nur Entscheidung nachtragen, nie ein zweiter Trade 2")
    e, log = lauf([t1("t1-j", "2026-11-12T07:50:00Z", 156000)], insert_id=None)
    check(len(log["insert"]) == 1 and len(log["alarm"]) == 1 and not any((pa.get("pump") or {}).get("t2", {}).get("status") == "angelegt" for _p, k, pa in log["patch"]),
          "Anlegen ohne Antwort der DB → nie stumm „angelegt“, ⚪")
    # Abstände: Firmen-Plan derselben ID um 12:30 Dubai (08:30 UTC) und Big Trade um 15:00 Dubai → Trade 2 hält 15 bzw. 90 min Abstand
    bel = [{"start_um": "2026-11-12T08:30:00Z", "status": "planned", "master_firm": "Tradeify", "route": "tvv2", "orbit_v3": False, "hedge_eur": 0},
           {"start_um": "2026-11-12T11:00:00Z", "status": "planned", "master_firm": "Apex Trader", "route": "tvv2", "orbit_v3": True, "hedge_eur": 400}]
    ok_ab = True
    for s in range(15):
        e, log = lauf([t1(f"t1-k{s}", "2026-11-12T07:50:00Z", 156000)], belegt=bel)
        st = ns["_ap_ts"](log["insert"][0]["start_um"]) if log["insert"] else None
        if st and (abs((st - datetime(2026, 11, 12, 8, 30, tzinfo=timezone.utc)).total_seconds()) < 15 * 60 or abs((st - datetime(2026, 11, 12, 11, 0, tzinfo=timezone.utc)).total_seconds()) < 90 * 60):
            ok_ab = False
    check(ok_ab, "Trade 2 hält Firmen-Abstand (15 min) und Big-Trade-Abstand der ID (90 min)")
    w, g = ruf("fdp_pump_trade2", A, {"tp": 6000}, START, 162000, LIQ, z16, R())
    check(w is None and "unplausibel" in str(g), f"Trade 1 deutlich über dem TP (+12.000 bei TP 6.000) → Tag zu, nie still „Ziel erreicht“ ({g})")
    w, g = ruf("fdp_pump_trade2", A, {"tp": 6000}, START, 156000, LIQ, START + 6300, R())
    check(w is None and "Mini" in str(g), f"Rest zum Ziel unter 500 $ → kein Mini-Trade 2 ({g})")

    # FF2c: offener Trade des 2-Trade-Wegs ab 18:00 Dubai → einmal 🔴 (Push), Ein-Trade-Weg nie, nichts schließen
    def offen(pid, weg="zwei", nr=2, start="2026-11-12T11:00:00Z", status="open"):
        return {"id": pid, "user_id": "u-1", "master_account_id": "konto-1", "master_firm": "Tradeify", "master_name": KONTO["name"], "status": status,
                "started_at": start, "mt5_baseline": {"tv": {"balance_start": 156000}, "funded_plan": {"pump": {"weg": weg, "nr": nr}}}}
    d = lambda h, m: datetime(2026, 11, 12, h - 4, m, tzinfo=timezone.utc)   # noqa: E731 — Dubai-Zeit
    check(not ruf("fdp_pump_offen_faellig", offen("o1"), d(17, 59)) and ruf("fdp_pump_offen_faellig", offen("o1"), d(18, 0)), "Meldung ab 18:00 Dubai, nicht 17:59")
    check(not ruf("fdp_pump_offen_faellig", offen("o2", weg="ein", nr=None), d(18, 30)), "Ein-Trade-Weg meldet nie")
    check(not ruf("fdp_pump_offen_faellig", offen("o3", status="completed"), d(18, 30)), "beendeter Trade meldet nicht")
    check(ruf("fdp_pump_offen_faellig", offen("o4", nr=1), d(18, 5)), "Trade 1 noch offen um 18:05 → meldet auch")
    check(not ruf("fdp_pump_offen_faellig", offen("o5"), d(18, 5), "18:30") and ruf("fdp_pump_offen_faellig", offen("o5"), d(18, 31), "18:30"), "eigene Uhrzeit aus der Einstellung (18:30)")
    def offen_lauf(plaene, jetzt, frei=True):
        log = {"alarm": []}
        ns.update({"sb_select": lambda tab, prm: copy.deepcopy(plaene) if tab == "trade_plans" else [dict(KONTO)] if tab == "accounts" else [],
                   "_fdp_regeln_laden": lambda: REG_T, "_ap_namen": lambda: ({"u-1": "ID A"}, set()), "_tm_melde_frei": lambda key: frei,
                   "alarm_senden": lambda *a, **k: log["alarm"].append((a, k))})
        import contextlib, io
        for _ in range(40):
            log["alarm"].clear()
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                res = ruf("fdp_pump_offen_tick", jetzt)
            m = re.search(r"NameError: name '(\w+)' is not defined", buf.getvalue())
            if not m:
                break
            lade(m.group(1))
        return res, log
    res, log = offen_lauf([offen("o6"), offen("o7", weg="ein", nr=None)], d(18, 10))
    check(res == ["o6"] and len(log["alarm"]) == 1 and log["alarm"][0][0][0] == 1 and "T2" in log["alarm"][0][0][3] and "ID A" in log["alarm"][0][0][3],
          f"Takt: genau ein 🔴 (Prio 1) für den offenen Trade 2, mit ID und T2 ({log['alarm'][0][0][3] if log['alarm'] else '–'})")
    res, log = offen_lauf([offen("o6")], d(18, 10), frei=False)
    check(not log["alarm"], "Takt: schon gemeldet (alarm_log) → keine zweite Meldung")
    res, log = offen_lauf([offen("o6")], d(17, 30))
    check(not log["alarm"], "Takt: vor 18:00 keine Meldung")
    check("fdp_pump_offen_tick(jetzt)" in app and "close" not in re.search(r"def fdp_pump_offen_tick.*?\n\n\n", app, re.S).group(0).lower(), "Alarm-Takt in fdp_tick, schließt nie")

    # Textanker: Takt, Tagesteilung, Auto-Close
    check("fdp_pump_tick(jetzt)" in app and 'rows = [p for p in rows if not (isinstance((p.get("mt5_baseline") or {}).get("funded_plan"), dict))]' in app,
          "fdp_tick ruft fdp_pump_tick; tt_tick lässt Funded-Planer-Pläne aus")
    html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
    check("p.mt5Baseline.funded_plan.pump))" in html, "Auto-Close am PC-Tab lässt Pump-Trades aus")

print()
if fehler:
    print(f"ROT: {len(fehler)} Prüfung(en) fehlgeschlagen")
    sys.exit(1)
print("GRÜN: FF2 Pump-Modell (Tradeify + Lucid)")
