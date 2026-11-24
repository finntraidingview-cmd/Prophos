#!/usr/bin/env python3
"""Selbsttest RC6 (Finn 19.11.2026 ~04:20 Dubai): Moritz Tradeify 150k …9666 (d2277e5f), Zyklus −5.415,70 $ bei Max DD 4.500 $ — der Ausgleich ging auf
„von Hand planen“ und der Farmer zeigte seit 11.11. „Ziel schon voll“. Schalter accounts.wd_zyklus_regel = 'an' gibt den Ausgleich frei (TP ≈ 5.447–5.477 $,
RC3 1 NQ, Hedge im normalen €/$-Satz); ohne Schalter bleibt alles wie bisher. Rechnet app.py tradeify_zyklus_konto mit den echten Zahlen, ohne Netz und DB.

Aufruf:  python3 tools/selftest_rc6_ausgleich_gross_hand.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
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
    for _ in range(60):
        try:
            return ns[fn](*a, **k)
        except NameError as e:
            lade(str(e).split("'")[1])
    raise RuntimeError(fn)


for n in ("TRADEIFY_ZYKLUS_MIN_USD", "TRADEIFY_ZYKLUS_PUFFER", "TRADEIFY_AUSGLEICH_BESTAETIGEN", "RC3_STUFEN_STD", "RC3_MAX_MNQ_STD",
          "tradeify_zyklus_konto", "tradeify_zyklus_start_bal", "wd_zyklus_stand", "rc3_recovery_lots"):
    lade(n)
ns["wd_plan_pnl"] = lambda p: p.get("master_pl")


def ag2_stimmig(plaene, live):
    """AG2 (24.11.2026): Fehlbetrag = Trade-Summe, Balance nur Gegenprobe (> 50 $ daneben → kein Ausgleich). Die Fixtures dieses Tests variieren nur die
    Live-Balance; damit Trades und Balance zusammenpassen wie am echten Konto, ist der P&L jedes Trades die Differenz zum nächsten balance_start, der letzte
    die Differenz zur Live-Balance. Eine Payout-Abbuchung vor dem ersten Trade des Zyklus fällt in den alten Zyklus (wie am Konto)."""
    m = [dict(p) for p in (plaene or ())]
    seq = sorted([p for p in m if str(p.get("status") or "") in ("completed", "review") and isinstance(p.get("tv"), dict)
                  and p["tv"].get("balance_start") is not None], key=lambda p: str(p.get("started_at") or ""))
    for a, b in zip(seq, seq[1:]):
        a["master_pl"] = round(float(b["tv"]["balance_start"]) - float(a["tv"]["balance_start"]), 2)
    if seq and isinstance(live, (int, float)):
        seq[-1]["master_pl"] = round(float(live) - float(seq[-1]["tv"]["balance_start"]), 2)
    return m


def ag2_wrap(fn):
    def w(konto, plaene, payouts, wd_stand, wd_ziel, vorplan, live, *a, **k):
        return fn(konto, ag2_stimmig(plaene, live), payouts, wd_stand, wd_ziel, vorplan, live, *a, **k)
    return w


ns["tradeify_zyklus_konto"] = ag2_wrap(ns["tradeify_zyklus_konto"])

MORITZ = {"id": "d2277e5f-4f07-4bf2-a981-e02ff3b97d96", "name": "150k FTDFYSLX150431449666 → Winning Days", "firm": "Tradeify", "account_type": "winning_days",
          "user_id": "aff98e60", "max_drawdown": 4500}
PAY = [{"requested_at": "2026-11-02", "status": "received"}]
# echte Pläne seit dem 02.11. (trade_plans, mt5_baseline.tv.balance_start, master_pl) — der 02.11.-Trade zählt zum alten Zyklus
T = [("2026-11-02T12:14:36+00:00", 267.22, 165676.62), ("2026-11-03T09:25:27+00:00", 261.36, 161443.84), ("2026-11-04T10:58:08+00:00", 267.24, 161705.2),
     ("2026-11-05T02:28:24+00:00", -6732.76, 161972.44), ("2026-11-06T04:26:56+00:00", 253.86, 155239.68), ("2026-11-09T02:47:34+00:00", 276.24, 155493.54),
     ("2026-11-10T10:31:27+00:00", 258.36, 155769.78)]
PL = [{"status": "completed", "started_at": s, "ended_at": s, "master_pl": pl, "tv": {"balance_start": bs}} for s, pl, bs in T]
LIVE, LIVE_AT = 156028.14, "2026-11-15T16:03:30+00:00"
# Live-Werte wd_farmer_regeln (19.11.2026): fu.tradeify 266–280, staffelFirma.tradeify, recovery_lots.tradeify
SF = [{"von": 0, "eur": 75}, {"von": 2000, "eur": 80}, {"von": 4000, "eur": 85}, {"von": 6000, "eur": 110}, {"von": 8000, "eur": 125}]
VP = {"regeln": {"fu": {"tradeify": [266, 280]}, "staffelFirma": {"tradeify": SF}}}
RC = {"an": True, "stufen": [dict(x) for x in ns["RC3_STUFEN_STD"]], "max_mnq": {"25000": 20, "50000": 40, "100000": 80, "150000": 120}}
LOCK = 100.0   # liq_regeln winning_days Tradeify: Liq = 150.100


def rechne(konto, stand=5):
    return ruf("tradeify_zyklus_konto", konto, PL, PAY, stand, 5, VP, LIVE, LIVE_AT, wd_lock=LOCK, rc_regel=RC)


check(ruf("tradeify_zyklus_start_bal", PL, "2026-11-02") == 161443.84, "Zyklus-Start = balance_start des 03.11.-Trades 161.443,84 $")

# 1) wie bisher: ohne Schalter → gesperrt, kein Ausgleich, „von Hand planen“
z0 = rechne(MORITZ)
check(z0["gewinn"] == -5415.70 and z0["gesperrt"] and not z0["aktiv"] and z0.get("ausgleich_hand") and z0["ziel"] is None,
      f"ohne Schalter: −5.415,70 $, gesperrt, kein Ausgleich, ausgleich_hand ({z0['gewinn']}, {z0['grund']})")
check("von Hand planen" in z0["grund"] and "ausgleich_hand_frei" not in z0, "ohne Schalter: Grund unverändert „von Hand planen“")
for s in ("aus", "", None, "AUS"):
    zs = rechne(dict(MORITZ, wd_zyklus_regel=s))
    check(not zs["aktiv"] and zs.get("ausgleich_hand"), f"Schalter {s!r}: unverändert kein Ausgleich")

# 2) Schalter 'an' → Ausgleich mit TP = Fehl + 1 + Puffer, 1 NQ, Hedge im normalen Satz
z1 = rechne(dict(MORITZ, wd_zyklus_regel="an"))
check(z1["aktiv"] and z1["grund_code"] == "ausgleich" and z1.get("ausgleich_hand_frei") is True, f"Schalter 'an': Ausgleich aktiv ({z1['grund']})")
check(5447 <= z1["ziel"] <= 5477 and 30 <= z1["puffer"] <= 60 and z1["ziel"] == -(-(5415.70 + 1 + z1["puffer"]) // 1),
      f"TP = 5.415,70 + 1 + Puffer {z1['puffer']:.0f} aufgerundet = {z1['ziel']} $")
check(z1.get("instr") == "nq" and z1.get("instr_kt") == 1 and z1.get("kt") is None, f"RC3: TP > 2.000 → 1 NQ (instr_kt {z1.get('instr_kt')})")
satz = round(110 / 273 * 1000, 2)
check(z1["satz"] == satz and abs(z1["hedge_eur"] - round(z1["ziel"] * satz / 1000, 2)) < 0.005,
      f"Hedge wie der Recoverer: Staffel 110 € (Plus 6.028) ÷ normaler TP 273 → {satz} €/1.000 $ → hedge_eur {z1['hedge_eur']} €")
check(" · über Max DD von Hand freigegeben" in z1["grund"], "Grund nennt die Hand-Freigabe")
check(rechne(dict(MORITZ, wd_zyklus_regel=" An "))["aktiv"], "Schalter tolerant (Groß/Leerzeichen) wie beim Apex-Recoverer")

# 3) Schranken bleiben: Deckel (Puffer bis Liq), Frische, RC5 offen, WD-Stand < Ziel − 1
zd = ruf("tradeify_zyklus_konto", dict(MORITZ, wd_zyklus_regel="an"), PL, PAY, 5, 5, VP, 150000.0, LIVE_AT, wd_lock=LOCK, rc_regel=RC)
check(zd["grund_code"] == "unbekannt" and not zd["aktiv"], "Deckel bleibt: Balance unter der WD-Liq → unbekannt, kein Ausgleich")
zf = ruf("tradeify_zyklus_konto", dict(MORITZ, wd_zyklus_regel="an"), PL, PAY, 5, 5, VP, LIVE, "2026-11-10T10:00:00+00:00", wd_lock=LOCK, rc_regel=RC)
check(not zf["aktiv"] and zf["grund_code"] == "unbekannt", "Frische bleibt: Lesung vor dem Ende des letzten Trades → kein Ausgleich")
PLO = PL + [{"status": "open", "started_at": "2026-11-19T05:00:00+00:00"}]
zo = ruf("tradeify_zyklus_konto", dict(MORITZ, wd_zyklus_regel="an"), PLO, PAY, 5, 5, VP, LIVE, LIVE_AT, wd_lock=LOCK, rc_regel=RC)
check(not zo["aktiv"] and zo["grund_code"] == "laeuft", "RC5 bleibt: Trade läuft → kein neuer Ausgleich")
z3 = rechne(dict(MORITZ, wd_zyklus_regel="an"), stand=3)
check(not z3["aktiv"] and z3["gesperrt"], "WD 3/5: kein Ausgleich (normale WD), Sperre bleibt")

# 4) kleiner Fehlbetrag (≤ Max DD): Schalter ändert nichts
PLK = PL[:3]
zk0 = ruf("tradeify_zyklus_konto", MORITZ, PLK, PAY, 5, 5, VP, 161000.0, LIVE_AT, wd_lock=LOCK, rc_regel=RC)
zk1 = ruf("tradeify_zyklus_konto", dict(MORITZ, wd_zyklus_regel="an"), PLK, PAY, 5, 5, VP, 161000.0, LIVE_AT, wd_lock=LOCK, rc_regel=RC)
check(zk0["aktiv"] and zk0 == {k: v for k, v in zk1.items()}, "Fehl ≤ Max DD: mit und ohne Schalter bitgleich")

# 5) RC6 Teil 2 — Anzeige (prophos.html): Zyklus im Minus (Railway zyklus.gesperrt) → nie „Payout anfragen/anfragbar“, sondern der Zustand
check("function wdZyklusSperreTxt(id)" in html and "z.art !== 'tradeify' || !z.gesperrt" in html and "' · Recovery von Hand'" in html,
      "Helfer wdZyklusSperreTxt: nur Tradeify/Lucid-Stand mit gesperrt, Minus über Max DD → „· Recovery von Hand“")
_wh = html[html.index("function wdHinweisText(h, id){"):][:600]
check("const sp = wdZyklusSperreTxt(id)" in _wh and _wh.index("wdZyklusSperreTxt") < _wh.index("Payout anfragen"),
      "Farmer-Hinweis „Ziel schon voll“: Sperre vor „🏆 x/5 · Payout anfragen“ (gespeicherter Schlüssel-Text bleibt)")
check("q.hinweis === WD_HINWEIS_ZIEL && wdZyklusSperreTxt(q.id)" in html and "⚠ Zyklus im Minus" in html, "Ablauf-Chip: „⚠ Zyklus im Minus“ statt „🏆 Ziel erreicht“")
check("sperre = wdZyklusSperreTxt(k.id)" in html and "bereit: fehlt === 0 && !sperre" in html and html.count("filter(e => e.fehlt > 0).sort(") == 2,
      "WD-Übersicht: bereit nur ohne Sperre, „Nächster Payout“ wie bisher nur aus fehlenden Tagen")
# WE1 (19.11.2026): zwischen Sperre und „Payout anfragbar“ steht „anfragbar ab …“ (Ziel erst heute voll) — die Sperre geht weiter vor
check("_sp ? ` ✓ · ${escapeHtml(_sp)}` : _ab ?" in html and ": ' ✓ · Payout anfragbar') : ' ✓') : ''" in html, "Accounts-Zeile: „✓ · Zyklus …“ statt „✓ · Payout anfragbar“")
check(html.count("!(typeof window._wdZyklusSperreTxt === 'function' && window._wdZyklusSperreTxt(a.id))") == 2, "Finanzen: Payout-Status + Kontoauswahl nicht „anfragbar“ bei Sperre")

print()
if fehler:
    print(f"✗ {len(fehler)} Fehler")
    sys.exit(1)
print("✓ alle Prüfungen grün")
