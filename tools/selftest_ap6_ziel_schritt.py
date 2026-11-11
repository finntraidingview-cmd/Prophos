#!/usr/bin/env python3
"""Selbsttest AP6 (Finn 11.11.2026 19:49/20:02: „wenn ich auf ‚Abhaken‘ gehe, auch automatisch ‚Ziel erreicht, Winning Days‘“ / „sobald ein Typ sein Ziel erreicht hat …
entweder Waiting for Payout oder Winning Days“). app.py kz_fdp_abhak (GET /konto-ziele, Funded Futures) ohne Netz/DB mit Platzhalter-Konten, dazu die
Zuordnung „nächster Schritt bei Ziel“ (WP_SCHRITT) und die Verdrahtung im Abhak-Popup (prophos.html).
Aufruf:  python3 tools/selftest_ap6_ziel_schritt.py"""
import os
import re
import hashlib
from datetime import datetime, timezone, timedelta

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "hashlib": hashlib}


def lade(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^[A-Za-z_@#])", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^[A-Za-z_@#])", app, re.S | re.M)
    if not m:
        raise RuntimeError("nicht gefunden: " + name)
    exec(m.group(0), ns)


for n in ("_wd_num", "_liq_de", "kz_usd", "_wd_konto_groesse", "fdp_je_groesse", "fdp_ziel_gewinn", "fdp_zyklus", "fdp_tage", "fdp_konto_anzeige", "kz_fdp_abhak",
          "FDP_PUMP_TP_TOL_USD", "_fdp_pump_u", "_fdp_pump_spanne", "fdp_pump_tag_wurf"):
    lade(n)
ns["_cme_handelstag"] = lambda st: str(st)[:10]

REG = {"name": "FTMO Futures", "je_groesse": {"50000": {"ziel_gewinn": 4500, "max_trade": 3000, "dd": 2000}}}
A = {"id": "aaaaaaaa-0000-0000-0000-000000000005", "name": "50k FTMO0001 → Funded", "firm": "FTMO Futures", "account_type": "funded"}
PL = [{"status": "completed", "started_at": "2026-11-10T14:00:00Z", "master_pl": 1200, "tv": {"balance_start": 50000}}]
jg = ns["fdp_je_groesse"](REG, 50000.0)
check(bool(jg) and jg.get("ziel_gewinn") == 4500, f"Regel je Größe gefunden ({jg})")
r1 = ns["kz_fdp_abhak"](A, {"regel": REG, "pay": []}, 54753.0, PL)
check(r1 and r1["ziel_bal"] == 54500 and r1["erreicht"] is True and r1["bereit"] is True and r1["schritt"] == "winning_days", f"Ziel erreicht → Winning Days ({r1})")
check(r1 and r1["checks"][0][0] == "ok" and r1["checks"][0][1] == "Ziel bis Winning Days" and r1["checks"][0][2] == "+4.753 $ / +4.500 $", f"Zeile „Ziel bis Winning Days“ ({r1 and r1['checks']})")
r2 = ns["kz_fdp_abhak"](A, {"regel": REG, "pay": []}, 52100.0, PL)
check(r2 and r2["erreicht"] is False and "fehlen 2.400 $" in r2["fehlt_text"] and r2["checks"][0][0] == "nein", f"Ziel fehlt mit Zahlen ({r2 and r2['fehlt_text']})")
r3 = ns["kz_fdp_abhak"](A, {"regel": REG, "pay": []}, 58000.0, PL)
check(r3 and r3["erreicht"] is False and "unplausibel" in r3["fehlt_text"], "mehr als ein Trade über dem Ziel = unplausibel (wie fdp_konto_rechnen) → nicht erreicht")
r4 = ns["kz_fdp_abhak"](A, {"regel": REG, "pay": ["2026-11-05T10:00:00Z"]}, 54753.0, PL)
check(r4 and r4["zyklus"] == 2 and r4["start"] == 50000, f"Zyklus 2 nach Payout, Start = Start-Balance des ersten Trades danach ({r4 and (r4['zyklus'], r4['start'])})")
check(ns["kz_fdp_abhak"](dict(A, name="25k X → Funded"), {"regel": REG, "pay": []}, 26000.0, PL) is None, "ohne Werte für die Größe → None (Popup wie bisher)")

# Pump-Modell (Prüfer-MUSS): Ziel wie fdp_pump_konto (fdp_pump_tag_wurf), plausibel bis Ziel + dd, erreicht ab Rest < 100 $
REGP = {"name": "Tradeify", "tp_modus": "pump2", "je_groesse": {"150000": {"ziel_gewinn": [13000, 19000], "dd": 4500}}}
AP = dict(A, name="150k TDFY0001 → Funded", firm="Tradeify")
zp = 150000 + ns["fdp_pump_tag_wurf"](REGP["je_groesse"]["150000"], AP["id"], 1, "")["ziel_gewinn"]
p1 = ns["kz_fdp_abhak"](AP, {"regel": REGP, "pay": []}, zp - 50, [])
check(p1 and p1["ziel_bal"] == zp and p1["erreicht"] is True, f"Pump: 50 $ unter dem Niveau gilt als erreicht wie im Planer ({p1 and (p1['ziel_bal'], p1['erreicht'])})")
p2 = ns["kz_fdp_abhak"](AP, {"regel": REGP, "pay": []}, zp + 3000, [])
check(p2 and p2["erreicht"] is True, "Pump: 3.000 $ über dem Niveau noch plausibel (Ziel + dd)")
p3 = ns["kz_fdp_abhak"](AP, {"regel": REGP, "pay": []}, zp - 600, [])
check(p3 and p3["erreicht"] is False and "fehlen 600 $" in p3["fehlt_text"], f"Pump: 600 $ darunter → nicht erreicht ({p3 and p3['fehlt_text']})")
check('fd_unt_an(_freg, "futures", a.get("user_id"), None, True)' in app, "Regel-Auswahl streng wie fdp_planen")

# Verdrahtung
check('if typ == "funded" and isinstance(ctx.get("fdp"), dict):' in app and 'ctx["fdp"] = {"regel": _fr' in app, "konto_ziele lädt die Regel nur für Typ funded, kz_rechnen hängt abhak an")
check("funded: { art: 'fd', schritt: 'winning_days' }" in html and "challenge: { art: 'phase', schritt: 'passed' }" in html and "funded_cfd: { art: 'cfd', schritt: 'waiting' }" in html,
      "WP_SCHRITT: Funded CFD → waiting, Challenge → passed, Funded Futures → winning_days")
check("u.schritt === 'passed' || u.schritt === 'winning_days'" in html, "Popup: passed / winning_days nur hinzuwählen, nie abwählen")
check("ab2Gilt(pw.konto_typ, pw.mt5_baseline) || pw.planer_plan === true" in html, "Radar-Karte: planer_plan statt mt5_baseline.funded_plan")

print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER")
raise SystemExit(1 if fehler else 0)
