#!/usr/bin/env python3
"""Selbsttest LP1 Pump-Modell mit Tageslimit (Master 11.11.2026, Finn: „Lucid hat 2.700 $ Daily Loss überall“):
 (1) _fdp_pump_sl kappt den SL auf daily_rest − FDP_TAGES_PUFFER (vorher ohne Puffer)
 (2) Würfel „ohne SL“ bei Firmen MIT Tageslimit → SL = daily_rest − Puffer (Trade 1) bzw. E1 + daily_usd − Puffer (Trade 2); Tradeify (kein DLL) bitgleich wie vorher
 (3) fdp_tag_verlust: heutiger Verlust (Tagesstart aus dem ersten Plan heute bzw. Tagesschluss des Vortags) mindert den Daily-Loss-Rest; fdp_planen gibt ihn mit
Bitgleich-Vergleich gegen die Vorher-Fassung (SELFTEST_ALT=<app.py>, Standard: git show origin/main:app.py — vor dem Einspielen; danach den Commit davor angeben).
Ohne Netz. Aufruf: python3 tools/selftest_lp1_lucid_dll.py"""
import hashlib
import os
import random
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEU = open(os.path.join(W, "app.py"), encoding="utf-8").read()
_alt_pfad = os.environ.get("SELFTEST_ALT")
if _alt_pfad:
    ALT = open(_alt_pfad, encoding="utf-8").read()
else:
    try:
        ALT = subprocess.run(["git", "-C", W, "show", "origin/main:app.py"], capture_output=True, text=True, check=True).stdout
    except Exception:
        ALT = None
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


def ns_aus(src):
    ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "random": random, "hashlib": hashlib}

    def quelle(name):
        m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", src, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^\S)", src, re.S | re.M)
        if not m:
            raise LookupError(name)
        return m.group(0)

    def lade(name):
        s = quelle(name)
        for _ in range(40):
            try:
                exec(s, ns)
                return
            except NameError as e:
                lade(str(e).split("'")[1])

    def ruf(fn, *a, **k):
        for _ in range(80):
            try:
                if fn not in ns:
                    lade(fn)
                return ns[fn](*a, **k)
            except NameError as e:
                lade(str(e).split("'")[1])
        raise RuntimeError(fn)
    ns["_cme_handelstag"] = lambda st: str(st)[:10]   # Test: Stempel tragen den CME-Tag vorne
    return ruf, quelle


ruf, quelle = ns_aus(NEU)
for n in ("fdp_tag_verlust", "fdp_vortag"):
    check(bool(re.search(r"^def " + n + r"\(", NEU, re.M)), f"app.py hat {n}")
if fehler:
    sys.exit(1)

LU = {"ziel_gewinn": [13000, 19000], "dd": 4500, "daily_usd": 2700, "hedge_eur": 750, "hedge_auf_usd": 4500, "pump2_pct": 30, "ein_kontrakte": {"3": 1},
      "ein_sl": [2600, 2700], "t1_tp": [4000, 8000], "t1_kontrakte": {"2": 0.5, "3": 0.5}, "t1_sl": [2600, 2700], "sl_kein_pct": 50, "sl_hinter_liq": False,
      "t2_kontrakte": {"3": 1}, "t2_sl_be_pct": 50}
TR = dict(LU, daily_usd=None, ein_sl=[4500, 4700], t1_sl=[4500, 4700], sl_hinter_liq=True, hedge_eur=850)
del TR["daily_usd"]
START, LIQ, BAL = 150000.0, 150100.0, 157000.0     # Lucid 157k: Liq fest bei Start + 100 (Lock), Ziel 165.000
Z = START + 15000

# ── (1) + (2) Lucid 157k, Rest 2.700 (kein Verlust heute): SL immer ≤ 2.600, nie „ohne SL“
sls, kein = [], 0
for i in range(400):
    for weg in ("ein", "zwei"):
        r = ruf("fdp_pump_trade1", LU, weg, BAL, START, LIQ, Z, random.Random(i))
        if r.get("aktion") == "planen":
            sls.append(r["sl"])
            kein += r["sl"] is None
check(sls and kein == 0, f"Lucid: nie „ohne SL“ ({kein} von {len(sls)})")
check(sls and max(sls) <= 2600 and min(sls) >= 2599, f"Lucid Rest 2.700: SL immer 2.600 (Spanne 2.600–2.700 gekappt auf Rest − 100) ({min(sls)}–{max(sls)})")
r = ruf("fdp_pump_trade1", dict(LU, sl_kein_pct=0, ein_sl=[2000, 2000]), "ein", BAL, START, LIQ, Z, random.Random(1))
check(r["sl"] == 2000 and abs(r["risiko"] - 2000) < 0.01, f"SL unter dem Limit bleibt (2.000) ({r.get('sl')})")
r = ruf("fdp_pump_trade1", dict(LU, sl_kein_pct=100), "ein", BAL, START, LIQ, Z, random.Random(1))
check(r["sl"] == 2600 and abs(r["risiko"] - 2600) < 0.01 and abs(r["hedge_eur"] - round(750 / 4500 * 2600, 2)) < 0.01,
      f"Würfel „ohne SL“ → SL 2.600, Risiko 2.600, Hedge 750 €/4.500 $ × 2.600 ({r})")
# mit Vortrag (heute schon −1.000)
sls = [ruf("fdp_pump_trade1", LU, "ein", BAL - 1000, START, LIQ, Z, random.Random(i), tag_verlust=1000)["sl"] for i in range(200)]
check(max(sls) <= 1600 and min(sls) >= 1599, f"Lucid, heute schon −1.000: SL immer 1.600 (Rest 1.700 − 100) ({min(sls)}–{max(sls)})")
r = ruf("fdp_pump_trade1", LU, "ein", BAL - 2650, START, LIQ, Z, random.Random(1), tag_verlust=2650)
check(r.get("aktion") == "aus" and "Daily Loss" in r.get("grund", ""), f"Rest 50 $ → kein Plan ({r})")
r = ruf("fdp_pump_trade1", LU, "ein", BAL - 2610, START, LIQ, Z, random.Random(1), tag_verlust=2610)
check(r.get("aktion") == "aus", "Rest 90 $ (unter dem Puffer 100) → kein Plan statt SL ≤ 0")
# Trade 2
w, g = ruf("fdp_pump_trade2", dict(LU, t2_sl_be_pct=0), {"tp": 6000}, START, START + 6000, LIQ, Z, random.Random(2))
check(w and w["sl"] == min(6000 + 2700 - 100, 6000 + START - LIQ - 50) and w["sl"] == 5850,
      f"Trade 2 „ohne SL“ → SL = min(E1 + 2.700 − 100, Abstand zur Liq − 50) = 5.850 ({w}, {g})")
w, g = ruf("fdp_pump_trade2", dict(LU, t2_sl_be_pct=0), {"tp": 6000}, BAL, BAL + 6000, LIQ, Z + 5000, random.Random(2))
check(w and w["sl"] == 8600 and abs(w["risiko"] - 8600) < 0.01, f"Trade 2 weit von der Liq: SL = E1 + 2.700 − 100 = 8.600 ({w and w['sl']})")
w, g = ruf("fdp_pump_trade2", dict(LU, t2_sl_be_pct=100), {"tp": 6000}, BAL, BAL + 6000, LIQ, Z + 5000, random.Random(2))
check(w and w["sl"] == 6000, "Trade 2 Break-even bleibt SL = E1")

# ── (3) Tagesverlust
T, VT = "2026-11-12", "2026-11-11"
A = "konto-lucid"
V = [{"master_account_id": A, "started_at": VT + "T14:00:00Z", "ended_at": VT + "T15:00:00Z", "bal_start": 150000.0, "bal_end": 157000.0},
     {"master_account_id": "anderes", "started_at": T + "T01:00:00Z", "ended_at": T + "T02:00:00Z", "bal_start": 1.0, "bal_end": 1.0}]
check(ruf("fdp_tag_verlust", 156000.0, T, T, V, A) == (1000.0, "Tagesschluss des Vortags"), "Hand-Trade heute −1.000 ohne Plan: Tagesschluss Vortag 157.000 − 156.000")
check(ruf("fdp_tag_verlust", 157400.0, T, T, V, A)[0] == 0.0, "heute im Plus → 0")
check(ruf("fdp_tag_verlust", 156000.0, T, VT, V, A) == (0.0, None), "Nachts vor dem neuen CME-Tag (Plan-Tag ≠ laufender Tag) → 0, Tageslimit neu")
V2 = V + [{"master_account_id": A, "started_at": T + "T09:00:00Z", "ended_at": T + "T10:00:00Z", "bal_start": 157200.0, "bal_end": 155700.0}]
check(ruf("fdp_tag_verlust", 155500.0, T, T, V2, A) == (1700.0, "Start-Balance des ersten Trades heute"), "erster Plan heute: Tagesstart 157.200 − 155.500 = 1.700")
check(ruf("fdp_tag_verlust", 156000.0, "2026-11-16", "2026-11-16", [dict(V[0], ended_at="2026-11-13T15:00:00Z")], A)[0] == 1000.0, "Montag: Vortag = Freitag")
check(ruf("fdp_tag_verlust", 156000.0, T, T, [dict(V[0], ended_at="2026-11-09T15:00:00Z")], A) == (0.0, None), "nur ältere Schlüsse → nichts belegt → 0")
check(ruf("fdp_tag_verlust", None, T, T, V, A) == (0.0, None), "ohne Balance → 0")
check(ruf("fdp_tag_verlust", 146500.0, T, T, [dict(V[0], bal_end=-4000.0)], A, 150000.0)[0] == 0.0
      and ruf("fdp_tag_verlust", 150000.0 - 1500, T, T, [dict(V[0], bal_end=-500.0)], A, 150000.0)[0] == 1000.0,
      "Topstep Express: 0-basierte Schlüsse + Basis (−500 → 149.500; jetzt 148.500 → 1.000)")
planen = quelle("fdp_planen")
check('fdp_tag_verlust(balance, cme_heute, _cme_handelstag(jetzt.isoformat()), verlauf, str(a["id"]), basis)' in planen and "tag_verlust=_tv," in planen,
      "fdp_planen gibt den Tagesverlust an fdp_pump_konto (nur Firmen mit daily_usd)")
check('if _wd_num((jg or {}).get("daily_usd")) else (0.0, None)' in planen, "ohne daily_usd (Tradeify) kein Tagesverlust — bitgleich")

# ── Tradeify (kein Tageslimit) bitgleich mit der Vorher-Fassung
if ALT and "fdp_pump_trade1" in ALT:
    ruf_a, _q = ns_aus(ALT)
    # Aufwärmen: ruf lädt fehlende Namen beim ersten Aufruf nach und ruft dann neu — mit einem schon angebrauchten Würfel; erst danach vergleichen
    for _f, _a in (("fdp_pump_trade1", (TR, "zwei", START, START, 145500.0, Z)), ("fdp_pump_trade2", (TR, {"tp": 6000}, START, START + 6000, 145500.0, Z))):
        for _r in (ruf, ruf_a):
            for _ in range(3):
                _r(_f, *_a, random.Random(0))
    gleich, n = 0, 0
    for i in range(300):
        for weg in ("ein", "zwei"):
            for bal in (150000.0, 154000.0, 161000.0):
                n += 1
                gleich += ruf("fdp_pump_trade1", TR, weg, bal, START, 145500.0, Z, random.Random(i)) == ruf_a("fdp_pump_trade1", TR, weg, bal, START, 145500.0, Z, random.Random(i))
    check(gleich == n, f"Tradeify Trade 1 bitgleich mit vorher ({gleich}/{n})")
    gleich, n = 0, 0
    for i in range(300):
        for e1 in (4000.0, 6000.0, 8000.0):
            n += 1
            a = ruf("fdp_pump_trade2", TR, {"tp": e1}, START, START + e1, 145500.0, Z, random.Random(i))
            b = ruf_a("fdp_pump_trade2", TR, {"tp": e1}, START, START + e1, 145500.0, Z, random.Random(i))
            gleich += a == b
    check(gleich == n, f"Tradeify Trade 2 bitgleich mit vorher ({gleich}/{n})")
else:
    check(False, "Vorher-Fassung nicht lesbar (SELFTEST_ALT angeben)")

print()
if fehler:
    print(f"ROT: {len(fehler)} Prüfung(en)")
    sys.exit(1)
print("GRÜN: LP1 Daily Loss im Pump-Modell (Lucid) — Tradeify bitgleich")
