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
anders = sum(ruf("fdp_pump_tag_wurf", TR, f"konto-{i:04d}", 1, "2026-11-12") != ruf("fdp_pump_tag_wurf", TR, f"konto-{i:04d}", 1, "2026-11-13") for i in range(50))
check(anders >= 45, f"Folgetag würfelt neu (BE-Tag → morgen von vorn: {anders} von 50 Konten anders)")

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

print()
if fehler:
    print(f"ROT: {len(fehler)} Prüfung(en) fehlgeschlagen")
    sys.exit(1)
print("GRÜN: FF2 Pump-Modell (Tradeify + Lucid)")
