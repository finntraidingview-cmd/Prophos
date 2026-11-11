#!/usr/bin/env python3
"""Selbsttest FE1b Funded-Planer Futures (Finn 11.11.2026 20:45, Master FE1b nach S4 93394ed2):
 (a) Tagesdeckel je ID: max_je_id_tag 0 = aus (fdp_auswahl ohne Deckel, Feld 0–6, UI „kein Tagesdeckel je ID“); fehlt → 2 wie bisher.
 (b) Ziel-Toleranz je Firma × Größe (jg.ziel_toleranz_pct, 0–50, Standard 0 = wie heute): erreicht, wenn Gewinn im Zyklus ≥ Untergrenze von ziel_gewinn × (1 − %)
     — Tradeify 13.000 × 0,9 = 11.700 („Wenn ein Account bei Tradeify auf 12.000 geht, ist er auch durch“). In fdp_pump_trade1, fdp_pump_trade2, fdp_konto_rechnen
     und im Spiegel kz_fdp_abhak (Abhak-Popup AP6).
Echte Funktionen aus app.py (wie selftest_e2_fdp_einstellungen), prophos.html als Text. Ohne Netz. Aufruf: python3 tools/selftest_fe1b_deckel_toleranz.py"""
import copy
import hashlib
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "app.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def block(name):
    i = SRC.index(f"\ndef {name}(") + 1
    return SRC[i:SRC.find("\n\n\n", i)]


HILFEN = ("_ist_tradeify_cfd", "wd_min_gewinn", "wd_firmen_regel", "_wd_num", "_liq_de", "_ap_de", "_cme_handelstag", "ist_topstep_express", "liq_konto_boden", "liq_stufe",
          "_ap_norm", "ap_regel_finden", "_wd_konto_groesse", "liq_regel_waehlen", "_ap_tz", "kz_usd", "kz_fdp_abhak")
ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "random": random, "time": time, "GP_SLAVE_PPL": 0.85,
      "_firm_norm": lambda x: str(x or ""), "hashlib": hashlib}
i, j = SRC.index("FDP_TAKT_S = 300"), SRC.index('@app.route("/admin/funded-plan"')
k0, k1 = SRC.index("FDP_FEST = ["), SRC.index('@app.route("/admin/funded-plan/regeln"')
_konst = "\n".join(z for z in SRC.splitlines() if z.startswith(("WD_GOOD_DAY_MIN = ", "WD_ZYKLUS_KT, WD_ZYKLUS_INSTR = ", "TRADEIFY_ZYKLUS_MIN_USD = ", "TRADEIFY_ZYKLUS_PUFFER = ",
                                                                  "TRADEIFY_AUSGLEICH_BESTAETIGEN = ")))
_vorg = SRC[SRC.index("WD_ZYKLUS_VORGABE = {"):SRC.index("WD_ZYKLUS_KT, WD_ZYKLUS_INSTR")]
_e4 = SRC[SRC.index("WD_FIRMEN_REGELN_STD = {"):SRC.index("\n\n\ndef wd_firmen_regel(")]
exec(_konst + "\n" + _vorg + "\n" + _e4, ns)
b0, b1 = SRC.index("def fdp_start_bestaetigt("), SRC.index("def _fdp_login(")
exec("\n".join(block(n) for n in HILFEN) + "\n" + SRC[i:j] + "\n" + SRC[b0:b1] + "\n" + SRC[k0:k1], ns)
ns["_cme_handelstag"] = lambda st: str(st)[:10]

# ── (a) Tagesdeckel
kand = [("u1", "k1"), ("u1", "k2"), ("u1", "k3"), ("u2", "k4")]
g0, u0 = ns["fdp_auswahl"](kand, {"u1": 1}, 0, random.Random(1), {})
check(len(g0) == 4 and not u0, f"max_je_id 0 = aus → alle 4 Konten gewählt, keins über dem Deckel ({g0}, {u0})")
g2, u2 = ns["fdp_auswahl"](kand, {"u1": 1}, 2, random.Random(1), {"k1": "2026-11-01", "k2": "2026-11-05", "k3": "2026-11-03"})
check(len(g2) == 2 and ("u1", "k1") in g2 and ("u2", "k4") in g2 and set(u2) == {"k2", "k3"}, f"max_je_id 2 wie bisher: u1 hat schon 1 → nur das älteste Konto ({g2}, {u2})")
plan_src = block("fdp_planen")
check('max_je_id = 2 if _mj is None else max(0, int(_mj))' in plan_src and "or 2)" not in plan_src.split("_mj = ")[1][:120],
      "fdp_planen: 0 bleibt 0 (kein „or 2“ mehr), fehlt → 2")
REG = {"aktiv": True, "auto_bestaetigen": False, "updated_at": "2026-11-03T22:10:00.123+00:00", "user_ids": ["u1"],
       "zeiten": {"max_je_id_tag": 2, "firma_abstand_min": 15, "abstand_id_min": 90, "vorlauf_min": 15}, "firmen": copy.deepcopy(ns["FDP_FIRMEN_STANDARD"])}
REG["firmen"][1] = {"name": "Tradeify", "namen": ["tradeify"], "an": False, "symbol": "NQ", "lock_usd": 100, "tp_modus": "pump2",
                    "je_groesse": {"150000": {"ziel_gewinn": [13000, 19000], "dd": 4500, "hedge_eur": 850, "hedge_auf_usd": 4500}}}
aend = ns["fdp_regeln_aendern"]
p, f = aend(REG, {"updated_at": REG["updated_at"], "zeiten": {"max_je_id_tag": 0}})
check(f is None and p["zeiten"]["max_je_id_tag"] == 0, f"Einstellung: max_je_id_tag 0 wird gespeichert ({f})")
p, f = aend(REG, {"updated_at": REG["updated_at"], "zeiten": {"max_je_id_tag": 7}})
check(p is None and f, "Einstellung: 7 abgelehnt (0–6)")

# ── (b) Ziel-Toleranz
sw = ns["fdp_ziel_schwelle"]
check(sw({"ziel_gewinn": [13000, 19000], "ziel_toleranz_pct": 10}) == 11700, "Schwelle Tradeify 13.000 × 0,9 = 11.700")
check(sw({"ziel_gewinn": [13000, 19000]}) is None and sw({"ziel_gewinn": [13000, 19000], "ziel_toleranz_pct": 0}) is None, "ohne/0 % → keine Toleranz (wie heute)")
check(sw({"ziel_gewinn": 12000, "ziel_toleranz_pct": 10}) == 10800, "Ziel als Zahl (Apex) → 12.000 × 0,9 = 10.800")
check(sw({"ziel_gewinn": [10000, 12000], "ziel_toleranz_pct": 80}) == 5000, "höchstens 50 % (Grenze wie die Einstellung)")
TR = {"ziel_gewinn": [13000, 19000], "dd": 4500, "hedge_eur": 850, "hedge_auf_usd": 4500, "pump2_pct": 30, "ein_kontrakte": {"3": 1}, "ein_sl": [4500, 4700],
      "t1_tp": [4000, 8000], "t1_kontrakte": {"3": 1}, "t1_sl": [4500, 4700], "sl_kein_pct": 50, "sl_hinter_liq": True, "t2_kontrakte": {"3": 1}, "t2_sl_be_pct": 50}
TT = dict(TR, ziel_toleranz_pct=10)
S, L, Z = 150000.0, 145500.0, 150000.0 + 17000
r = ns["fdp_pump_trade1"](TT, "ein", S + 12000, S, L, Z, random.Random(2))
check(r["aktion"] == "ziel" and "Toleranz 10 %" in r["grund"] and "11.700" in r["grund"], f"Pump: Gewinn 12.000 ≥ 11.700 → Ziel erreicht → WD ({r})")
r = ns["fdp_pump_trade1"](TT, "ein", S + 11000, S, L, Z, random.Random(2))
check(r["aktion"] == "planen" and r["tp"] == 6000, f"Pump: Gewinn 11.000 < 11.700 → weiter pumpen, TP bis zum ganzen Niveau ({r.get('aktion')}, {r.get('tp')})")
r = ns["fdp_pump_trade1"](TR, "ein", S + 12000, S, L, Z, random.Random(2))
check(r["aktion"] == "planen", "Pump ohne Toleranz: 12.000 von 17.000 → weiter wie heute")
w, g = ns["fdp_pump_trade2"](TT, {"tp": 6000}, S + 6000, S + 12000, L, Z, random.Random(2), start=S)
check(w is None and g.startswith("Ziel schon"), f"Trade 2: nach Trade 1 bei +12.000 (≥ 11.700) → kein Trade 2 ({g})")
w, g = ns["fdp_pump_trade2"](TT, {"tp": 6000}, S + 6000, S + 12000, L, Z, random.Random(2))
check(w is not None, "Trade 2 ohne Zyklus-Start (alter Aufruf) → ohne Toleranz wie bisher")
tick = block("fdp_pump_tick")
check('start=_wd_num(fp.get("start"))' in tick, "fdp_pump_tick gibt den Zyklus-Start an Trade 2")
AX = {"ziel_gewinn": 12000, "max_trade": 6000, "kosten_eur": 350, "dd": 3000, "kontrakte": {"2": 0.5, "3": 0.5}}
reg_ax = {"name": "Apex Trader", "namen": ["apex"], "an": True, "symbol": "NQ", "lock_usd": 100}
args = dict(stufen=None, balance=110900.0, peak=110900.0, offen=300.0, start=100000.0, groesse=100000.0, rnd=random.Random(1), tage={}, konto_id="k-apex", zyklus=1)
ra = ns["fdp_konto_rechnen"](reg_ax, dict(AX, ziel_toleranz_pct=10), **args)
check(ra["aktion"] == "ziel" and "Toleranz" in ra["grund"], f"Apex (normal): Gewinn 10.900 ≥ 10.800 → Ziel erreicht ({ra.get('aktion')}, {ra.get('grund')})")
rb = ns["fdp_konto_rechnen"](reg_ax, AX, **dict(args, rnd=random.Random(1)))
check(rb["aktion"] != "ziel" and rb.get("ziel") == 112000, f"Apex ohne Toleranz → nicht erreicht, Ziel 112.000 wie bisher ({rb.get('aktion')}, {rb.get('grund')})")
# Spiegel im Abhak-Popup
A = {"id": "aaaaaaaa-0000-0000-0000-0000000fe1b1", "name": "150k TDFY0001 → Funded", "firm": "Tradeify", "account_type": "funded"}
REGP = {"name": "Tradeify", "tp_modus": "pump2", "je_groesse": {"150000": dict(TR, ziel_toleranz_pct=10)}}
k1 = ns["kz_fdp_abhak"](A, {"regel": REGP, "pay": []}, S + 12000, [])
check(k1 and k1["erreicht"] is True and k1["schritt"] == "winning_days", f"Abhak-Popup Pump: +12.000 mit 10 % Toleranz → erreicht ({k1 and k1['erreicht']})")
k2 = ns["kz_fdp_abhak"](A, {"regel": {"name": "Tradeify", "tp_modus": "pump2", "je_groesse": {"150000": TR}}, "pay": []}, S + 12000, [])
check(k2 and k2["erreicht"] is False, "Abhak-Popup ohne Toleranz → nicht erreicht (wie heute)")
AA = dict(A, name="100k APEX0001 → Funded", firm="Apex Trader")
k3 = ns["kz_fdp_abhak"](AA, {"regel": {"name": "Apex Trader", "je_groesse": {"100000": dict(AX, ziel_toleranz_pct=10)}}, "pay": []}, 110900.0, [])
check(k3 and k3["erreicht"] is True, "Abhak-Popup Apex: +10.900 ≥ 10.800 → erreicht (wie fdp_konto_rechnen)")
# Einstellung
p, f = aend(REG, {"updated_at": REG["updated_at"], "firma": {"name": "Tradeify", "je_groesse": {"150000": {"ziel_toleranz_pct": 10}}}})
check(f is None and p["firmen"][1]["je_groesse"]["150000"]["ziel_toleranz_pct"] == 10, f"Einstellung: ziel_toleranz_pct 10 neu an der Größe gespeichert ({f})")
p, f = aend(REG, {"updated_at": REG["updated_at"], "firma": {"name": "Tradeify", "je_groesse": {"150000": {"ziel_toleranz_pct": 60}}}})
check(p is None and f, "Einstellung: 60 % abgelehnt (0–50)")
p, f = aend(REG, {"updated_at": REG["updated_at"], "firma": {"name": "Tradeify", "je_groesse": {"150000": {"max_trade": 5000}}}})
check(p is None and "nicht hinterlegt" in (f or ""), "andere neue Schlüssel weiter abgelehnt (nur per SQL)")

# ── Frontend
check("ziel_toleranz_pct: ['Ziel-Toleranz', '%'" in HTML and "function e2ZtFeld(" in HTML and "e2ZtFeld(p, w, darfR, g)" in HTML, "UI: Feld Ziel-Toleranz je Größe mit Schwelle in $")
check("Object.assign({}, w, { ziel_toleranz_pct: 0 })" in HTML, "UI: Speichern schickt eine neue Toleranz auch ohne gespeicherten Wert")
check(HTML.count("Number(z.max_je_id_tag) === 0 ? 'kein Tagesdeckel je ID'") == 1 and "Number(Q.zeiten.max_je_id_tag) === 0 ? 'kein Tagesdeckel je ID'" in HTML,
      "UI: 0 zeigt „kein Tagesdeckel je ID“ statt 2")
check("0 = kein Tagesdeckel (FE1b)" in HTML, "UI: Hinweis 0 = aus am Feld")

print()
if FEHLER:
    print(f"{len(FEHLER)} FEHLER")
    sys.exit(1)
print("GRÜN: FE1b Tagesdeckel aus + Ziel-Toleranz")
