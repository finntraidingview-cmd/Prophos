#!/usr/bin/env python3
"""Selbsttest DL2 (11.11.2026, Fall WH1 Emin Tradeify 150k …0887, Plan 51c33a09): Hedge offen jenseits des Schließ-Levels → 🟠 nach 5 min.
Die ECHTEN Funktionen aus app.py (hedge_jenseits_urteil, hedge_jenseits_ereignisse) laufen mit dem Kurs-Verlauf des Falls; dazu der Einbau
(hedge_jenseits_tick im alarm_tick, Verwalter-Gruppe an den Verwalter). Ohne Netz. Aufruf: python3 tools/selftest_dl2_hedge_jenseits.py
Kennungen gekürzt (Plan-ID erfunden)."""
import os
import re
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = open(os.path.join(os.path.dirname(HIER), "app.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        FEHLER.append(text)


def block(name):
    i = APP.index(f"\ndef {name}(") + 1
    return APP[i:APP.index("\n\n\n", i)]


ns = {"datetime": datetime, "re": re}
exec(block("_wd_num"), ns)
exec(block("_liq_de"), ns)
for k in ("HEDGE_JENSEITS_S", "HEDGE_JENSEITS_KURS_MAX_S"):
    exec(re.search(rf"^{k} = .*$", APP, re.M).group(0), ns)
exec(block("hedge_jenseits_urteil"), ns)
exec(block("hedge_jenseits_ereignisse"), ns)
U, E = ns["hedge_jenseits_urteil"], ns["hedge_jenseits_ereignisse"]

check(U("sell", 28368, 28367.42) and not U("sell", 28300, 28367.42) and U("buy", 27000, 27100) and not U("buy", 27200, 27100),
      "Urteil: SELL jenseits = Kurs ≥ Level, BUY = Kurs ≤ Level")
check(not U("sell", 28368, None) and not U("sell", None, 28367) and not U("long", 28368, 28367), "ohne Level/Kurs/Richtung → nie jenseits")

# Fall 0887: SELL 3 MNQ @ 28.092,50, Hedge-Level (neu, DL2) 28.367,42 = Daily Loss 1.750 $ − 16,75 Pkt; alt Boden 29.798,30
plan = lambda lvl, st="offen": {"id": "51c33a09-0000-4000-8000-000000000887", "user_id": "u-emin", "status": "open", "richtung": "sell",
                                "master_name": "150k …0887 → Winning Days", "master_firm": "Tradeify", "master_symbol_root": "MNQ",
                                "hedge": {"status": st, "sl_level_nq": lvl, "liq_art": "daily_loss", "ticket": 430095, "symbol_nq": "MNQZ6"}}
t0 = datetime(2026, 11, 11, 11, 50, tzinfo=timezone.utc).timestamp()   # 15:50 Dubai
verlauf = [(0, 28300), (5, 28390), (6, 28395), (8, 28401), (10, 28410), (11, 28420), (15, 28450)]   # Minuten nach t0, Kurs
seit, gem = {}, []
for m, k in verlauf:
    jetzt = t0 + m * 60
    kurse = {"MNQ": {"kurs": k, "minute": datetime.fromtimestamp(jetzt - 30, timezone.utc).isoformat()}}
    for ev in E([plan(28367.42)], kurse, seit, jetzt):
        gem.append((m, ev))
check(gem and gem[0][0] == 10 and "Daily-Loss-Level 28.367" in gem[0][1][2] and "#430095" in gem[0][1][2],
      f"0887 neu: ab Minute 5 jenseits, 🟠 nach 5 min (Minute 10) mit Level und Ticket ({[m for m, _e in gem]})")
seit2, gem2 = {}, []
for m, k in verlauf:
    jetzt = t0 + m * 60
    kurse = {"MNQ": {"kurs": k, "minute": datetime.fromtimestamp(jetzt - 30, timezone.utc).isoformat()}}
    gem2 += E([plan(29798.3)], kurse, seit2, jetzt)
check(not gem2, "0887 mit altem Boden-Level 29.798: nie jenseits (so blieb es heute still)")

# zurück diesseits → Zähler neu
seit3 = {}
E([plan(28367.42)], {"MNQ": {"kurs": 28400, "minute": datetime.fromtimestamp(t0, timezone.utc).isoformat()}}, seit3, t0 + 30)
E([plan(28367.42)], {"MNQ": {"kurs": 28300, "minute": datetime.fromtimestamp(t0 + 200, timezone.utc).isoformat()}}, seit3, t0 + 230)
r3 = E([plan(28367.42)], {"MNQ": {"kurs": 28400, "minute": datetime.fromtimestamp(t0 + 400, timezone.utc).isoformat()}}, seit3, t0 + 430)
check(not r3 and seit3.get(plan(0)["id"]) == t0 + 430, "zwischendurch wieder diesseits → 5-min-Zähler beginnt neu")

# alter Kurs, Hedge zu, Plan nicht open → nichts
alt = {"MNQ": {"kurs": 28400, "minute": datetime.fromtimestamp(t0 - 3600, timezone.utc).isoformat()}}
s4 = {plan(0)["id"]: t0 - 900}
check(not E([plan(28367.42)], alt, s4, t0) and not s4, "Reader-Minute > 5 min alt → kein Beleg, Zähler weg")
frisch = {"MNQ": {"kurs": 28400, "minute": datetime.fromtimestamp(t0 - 30, timezone.utc).isoformat()}}
check(not E([plan(28367.42, "geschlossen")], frisch, {plan(0)["id"]: t0 - 900}, t0), "Hedge schon geschlossen → nichts")
check(not E([dict(plan(28367.42), status="review")], frisch, {plan(0)["id"]: t0 - 900}, t0), "Plan nicht mehr open → nichts")
nq = dict(plan(28367.42), master_symbol_root="NQ")
check(E([nq], {"NQ": {"kurs": 28400, "minute": datetime.fromtimestamp(t0 - 30, timezone.utc).isoformat()}}, {nq["id"]: t0 - 400}, t0),
      "NQ-Plan liest die NQ-Wurzel")

# Punkt 2: Pflicht-SL vor dem Daily Loss, wenn der Würfel „ohne SL“ ergab (wd_sl_dll_pflicht)
for k in ("WD_SL_FEST_MIN_USD", "WD_SL_DLL_PUFFER"):
    exec(re.search(rf"^{k} = .*$", APP, re.M).group(0), ns)
exec(block("wd_sl_dll_pflicht"), ns)
P = ns["wd_sl_dll_pflicht"]
ohne = {"ohne": True, "stufe": 0, "usd": None, "puffer": 1750.0, "grund": "gewürfelt: ohne SL"}
r = P(ohne, {"usd": 1750.0, "art": "daily_loss"})
check(r["ohne"] is False and r["usd"] == 1650 and r.get("pflicht_dll") and "1.750" in r["grund"], f"0887: ohne SL + Daily Loss 1.750 $ → SL 1.650 $ ({r})")
check(P(ohne, {"usd": 9000.0, "art": "liq"}) is ohne, "Puffer ist die Liquidation (kein Tageslimit) → ohne SL bleibt (WD-Regel)")
check(P(dict(ohne), {"usd": 150.0, "art": "daily_loss"})["ohne"] is True, "Daily Loss nur 150 $ entfernt → kein Pflicht-SL (< 100 $), Hedge schließt am DLL-Level")
mit = {"ohne": False, "usd": 900, "stufe": 2}
check(P(mit, {"usd": 1750.0, "art": "daily_loss"}) is mit, "gewürfelter SL bleibt, wie er ist")
check(P({"ohne": True, "sperre": True}, {"usd": 1750.0, "art": "daily_loss"}).get("sperre"), "Sperre (FT2 fest) bleibt Sperre")
check(P(None, {"usd": 1750.0, "art": "daily_loss"}) is None, "Würfel aus (None) → nichts")
fp = block("wd_sl_fuer_plan")
check("return wd_sl_dll_pflicht(wd_sl_wuerfeln(regel, puffer, bal, liq, rnd=rnd, grund=mv.get(\"grund\")), mv)" in fp, "wd_sl_fuer_plan hängt den Pflicht-SL an")
hv = block("hf_wd_master_verlust")
check('kd = _wd_num(a.get("dll_usd"))' in hv and "regel is None or k_lvl > regel" in hv and "regel, regel_soft = k_lvl, True" in hv,
      "hf_wd_master_verlust: Konto-Limit dll_usd (engeres gilt, Soft Breach → art daily_loss)")
check(APP.count("_wd_sl_konten_select({") == 2 and ',dll_usd"' in block("_wd_sl_konten_select"), "beide Konto-Abfragen des WD-SL lesen dll_usd (mit Rückfall ohne Spalte)")

# Einbau
tick = block("hedge_jenseits_tick")
at = block("alarm_tick")
check("hedge_jenseits_tick(jetzt)" in at and at.index("hedge_jenseits_tick(jetzt)") < at.index("echo_frost_tick("), "alarm_tick ruft die Wache (eigenes try)")
check('"status": "eq.open", "hedge_eur": "gt.0"' in tick and "_alarm_fremd_verwaltet" not in tick, "eigene Abfrage ALLER offenen Hedge-Pläne (auch Verwalter-Gruppen)")
check("if uid in karte:" in tick and "push_an_user(karte[uid]" in tick and tick.index("if uid in karte:") < tick.index("alarm_senden(2,"),
      "Verwalter-Gruppe (Emin) → Push an den Verwalter, nie an die Master-IDs; HT → alarm_senden 🟠")
check("alarm_im_log(" in tick and 'f"hedge_jenseits:{pid}"' in tick and "(schon and key in schon)" in tick,
      "einmal je Plan (HT auch nach Neustart über alarm_log 24 h; alarm_im_log None bei Lesefehler → trotzdem melden)")
check(not re.search(r"(close|schliess|order_send)\(", tick), "Wache schließt nichts")
print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER: " + "; ".join(FEHLER))
sys.exit(1 if FEHLER else 0)
