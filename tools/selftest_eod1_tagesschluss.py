#!/usr/bin/env python3
"""Selbsttest EOD1 (Finn 16.11.2026): EOD-Trailing-Höchststand nur aus Tagesschlüssen. Fall Chris FTMO Futures 50k …9613 mit den echten Zahlen:
10.11. 50.000 → 49.145,84 · 11.11. Trade 1 49.145,84 → 51.451,68 (Zwischenstand), Trade 2 51.451,68 → 48.413,36 (Tagesschluss). Der Funded-Planer meldete
„geblowt? Konto-Boden 48.452 $ … ab Höchststand 51.451,68“ — richtig ist Boden 47.000 $ (Max DD 3.000 ab 50.000), das Konto lebt mit ~1.413 $ Luft.
Echte Funktionen aus app.py (liq_peak, _liq_peak_eod, liq_konto_boden, fdp_liq), ohne Netz/DB.

Aufruf:  python3 tools/selftest_eod1_tagesschluss.py"""
import os
import re
from datetime import datetime, timedelta, timezone

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone}


def lade(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^\S)", app, re.S | re.M)
    exec(m.group(0), ns)


def ruf(fn, *a, **k):
    for _ in range(40):
        try:
            return ns[fn](*a, **k)
        except NameError as e:
            lade(str(e).split("'")[1])
    raise RuntimeError(fn)


for n in ("_wd_num", "_cme_handelstag", "liq_peak", "_liq_peak_eod", "liq_konto_boden", "fdp_liq"):
    lade(n)

CHRIS = {"id": "29256430", "account_type": "funded", "firm": "FTMO Futures", "name": "50k FTMO409613 → Funded", "max_drawdown": 3000,
         "tv_balance": 48413.36, "tv_balance_at": "2026-11-11T16:51:46+00:00"}
V = [{"id": "8be95989", "master_account_id": "29256430", "konto_typ": "funded", "started_at": "2026-11-10T03:49:21+00:00", "ended_at": "2026-11-10T04:06:26+00:00",
      "bal_start": 50000.0, "bal_end": 49145.84},
     {"id": "38078484", "master_account_id": "29256430", "konto_typ": "funded", "started_at": "2026-11-11T15:45:52+00:00", "ended_at": "2026-11-11T16:00:20+00:00",
      "bal_start": 49145.84, "bal_end": 51451.68},
     {"id": "a8fdcf47", "master_account_id": "29256430", "konto_typ": "funded", "started_at": "2026-11-11T16:03:28+00:00", "ended_at": "2026-11-11T16:51:22+00:00",
      "bal_start": 51451.68, "bal_end": 48413.36}]
BAL = 48413.36

# ── Beleg: so kam der falsche Boden zustande (Intraday-Höchststand) ──
alt = ruf("liq_peak", {}, CHRIS, BAL, V)
check(alt == 51451.68, f"Beleg: Intraday-Höchststand 51.451,68 (Zwischenstand nach Trade 1) — {alt}")
b_alt = ruf("fdp_liq", 50000, 3000, alt, BAL, 0.0)
check(b_alt[0] is None and "51.451,68" in b_alt[1], f"Beleg: damit Boden 48.451,68 über der Balance → „geblowt?“ ({b_alt[1][:90]})")

# ── EOD1: nur Tagesschlüsse ──
pk = ruf("liq_peak", {}, CHRIS, BAL, V, eod=True)
check(pk == 50000.0, f"EOD-Höchststand = 50.000 (Tagesschluss 11.11. 48.413,36, Tagesstart 10.11. 50.000) — {pk}")
b = ruf("fdp_liq", 50000, 3000, pk, BAL, 0.0)
check(b[0] == 47000.0, f"Chris: Konto-Boden 47.000 $, Balance 48.413,36 → lebt mit {BAL - (b[0] or 0):,.2f} $ Luft ({b[1][:80]})")
check(ruf("liq_peak", {"started_at": "2026-11-16T05:00:00+00:00", "master_account_id": "29256430"}, CHRIS, BAL, V, eod=True) == 50000.0,
      "dasselbe mit einem Trade-Start heute (Radar/Nachtlauf)")

# ── echtes EOD-Hoch gilt weiter ──
V2 = V[:2]   # 11.11. endet NACH Trade 1 bei 51.451,68 (kein Trade 2) = echter Tagesschluss
pk2 = ruf("liq_peak", {}, dict(CHRIS, tv_balance=50800.0), 50800.0, V2, eod=True)
b2 = ruf("fdp_liq", 50000, 3000, pk2, 50800.0, 0.0)
check(pk2 == 51451.68 and b2[0] == 48451.68, f"echtes EOD-Hoch 51.451,68 hebt den Boden auf 48.451,68 (Balance heute 50.800) — {pk2} / {b2[0]}")

# ── laufender Tag: Zwischenstand zählt nie, auch ohne Trade-Start (Planer/Pump) ──
jetzt = datetime.now(timezone.utc)
h1, h2 = (jetzt - timedelta(minutes=50)).isoformat(), (jetzt - timedelta(minutes=30)).isoformat()
V3 = V + [{"id": "heute1", "master_account_id": "29256430", "konto_typ": "funded", "started_at": h1, "ended_at": h2, "bal_start": 48413.36, "bal_end": 50600.0}]
if ruf("_cme_handelstag", h1) == ruf("_cme_handelstag", None):
    pk3 = ruf("liq_peak", {}, CHRIS, 50600.0, V3, eod=True)
    check(pk3 == 50000.0, f"heute +2.186,64 (Zwischenstand 50.600) hebt den Boden nicht — Höchststand bleibt 50.000 ({pk3})")
else:
    check(True, "(Tageswechsel gerade jetzt — Fall „heute“ übersprungen)")

# ── Nachtfenster (Prüfer MUSS): Nachtlauf 02:00 Dubai plant schon den Folgetag, CME-Tag von jetzt wechselt erst 17:00 CT ──
VN = [{"id": "n1", "master_account_id": "29256430", "konto_typ": "funded", "started_at": "2026-11-13T15:00:00+00:00", "ended_at": "2026-11-13T15:30:00+00:00",
       "bal_start": 49500.0, "bal_end": 50000.0},
      {"id": "n2", "master_account_id": "29256430", "konto_typ": "funded", "started_at": "2026-11-16T15:00:00+00:00", "ended_at": "2026-11-16T15:40:00+00:00",
       "bal_start": 50000.0, "bal_end": 51500.0}]
pkn = ruf("liq_peak", {}, CHRIS, 51500.0, VN, eod=True, heute="2026-11-17")
check(pkn == 51500.0, f"Plan-Tag 17.11. (Lauf 16.11. 22:10 UTC): Tagesschluss 16.11. 51.500 zählt → Boden 48.500 — {pkn}")
check(ruf("liq_peak", {}, CHRIS, 51500.0, VN, eod=True, heute="2026-11-16") == 50000.0, "derselbe Verlauf mit Plan-Tag 16.11.: der laufende Tag zählt nicht")
check('peak = liq_peak({}, a, balance, verlauf, eod="apex" not in str(a.get("firm") or "").lower(), heute=cme_heute)' in app and
      "peak_e = liq_peak({}, a, balance, verlauf, eod=True, heute=cme_heute)" in app, "Funded-Planer (konto_rechnen + Pump) übergibt den Plan-Tag")

# ── Trade heute ohne belegte Start-Balance (Prüfer SOLLTE): Live-Balance ist dann ein Zwischenstand ──
VO = [V[0], dict(V[1], bal_start=None)]
pko = ruf("liq_peak", {}, CHRIS, 51451.68, VO, eod=True, heute="2026-11-11")
check(pko == 50000.0, f"11.11. nach Trade 1 ohne bal_start, Live 51.451,68: Höchststand bleibt 50.000 — {pko}")
check(ruf("liq_peak", {}, CHRIS, 50200.0, V[:1], eod=True, heute="2026-11-11") == 50200.0,
      "heute noch kein Trade: die Balance ist der Tagesstart und zählt (Hand-Trade/Gutschrift über Nacht)")

# ── Apex trailt intraday und bleibt wie bisher ──
e = lambda a: "apex" not in str(a.get("firm") or "").lower()   # dieselbe Bedingung wie an den Einbaustellen (Anker unten)
check(all(e({"firm": f}) for f in ("FTMO Futures", "Tradeify", "Lucid Trading", "Topstep", "FundedNext Futures", "Alpha Futures")),
      "EOD-trailing: FTMO Futures, Tradeify, Lucid, Topstep, FNF Futures, Alpha")
check(not e({"firm": "Apex Trader"}) and not e({"firm": "APEX"}), "Apex: intraday-trailing → nicht EOD")
APEX = dict(CHRIS, firm="Apex Trader")
check(ruf("liq_peak", {}, APEX, BAL, V, eod=e(APEX)) == 51451.68, "Apex mit denselben Trades: Höchststand weiter 51.451,68 (Zwischenstand zählt)")

# ── Einbau an den Stellen ──
check('peak = liq_peak({}, a, balance, verlauf, eod="apex" not in str(a.get("firm") or "").lower(), heute=cme_heute)' in app, "Funded-Planer Futures (konto_rechnen → fdp_liq): EOD-Höchststand außer Apex")
check('return {str(a["id"]): liq_peak({}, a, None, verlauf, eod="apex" not in str(a.get("firm") or "").lower()) for a in konten}' in app,
      "Challenge-Planer _ap_peaks (nachziehende Böden): EOD-Höchststand außer Apex")
check("heute = _cme_handelstag(st) if st else _cme_handelstag(None)" in app, "_liq_peak_eod: ohne Trade-Start gilt der laufende CME-Tag als heute")
check('pk = peak_eod if (peak_eod is not None and (b_regel or {}).get("maxdd_art") == "eod_trailing") else peak' in app, "Radar (liq_regel_felder) wählt bei EOD-Trailing weiter peak_eod")

print()
print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER")
raise SystemExit(1 if fehler else 0)
