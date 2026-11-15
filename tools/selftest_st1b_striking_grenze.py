#!/usr/bin/env python3
"""Selbsttest ST1b Variante (a) (Prüfer S2 MUSS, Master 15.11.2026): Striking-Verlustgrenze im Bot-cmd.
Echo mit Hedge: nachzieh_cmd löscht die Tagesgrenze, sl_ausloeser zieht erst ab Plan × 1,15 nach — ein Striking-Trade konnte so über 1 % verlieren.
Jetzt: cmd.verlust_grenze_usd (Planer → funded_plan → PC-Tab → panel.py) bleibt bei Echo mit Hedge stehen und wirkt wie die Tagesgrenze
(SL am Fill auf min(sl_usd, Grenze)). Ohne das Feld bitgleich (Diff-Test über nachzieh_cmd gegen den main-Stand vor ST1b); Hedge folgt über copier.plan_sltp.
Aufruf: python3 tools/selftest_st1b_striking_grenze.py      (ohne Netz, ohne Klick: _sltp_klicken/_api_lesen gestubbt)"""
import itertools
import os
import re
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import copier  # noqa: E402
import order_bot as ob  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


BASIS_VOR_ST1 = "92e49a11"   # main-Commit vor ST1b (fest, nie ein Branch-Stand)
print(f"— 1) nachzieh_cmd ohne verlust_grenze_usd bitgleich wie main vor ST1b ({BASIS_VOR_ST1}) —")
alt_src = subprocess.run(["git", "-C", WURZEL, "show", BASIS_VOR_ST1 + ":mt5-copier/order_bot.py"], capture_output=True, text=True, timeout=60).stdout
m = re.search(r"\ndef nachzieh_cmd\(cmd\):\n(?:    .*\n|\n)+?(?=\S)", alt_src)
ns = {}
if m:
    exec(m.group(0), ns)   # nur die reine Funktion aus dem Basis-Stand (kein Import des alten Moduls)
alt_nc = ns.get("nachzieh_cmd")
ok(alt_nc is not None and "verlust_grenze_usd" not in (m.group(0) if m else ""), f"nachzieh_cmd aus {BASIS_VOR_ST1} geladen (ohne Striking)")
faelle = abw = 0
if alt_nc:
    for oh, fin, tg, fg in itertools.product((None, False, True), (None, "", "pass", "beide", "blow", "gewinntag", "x"), (None, "", 0, 500.0, -3, "abc"),
                                             (None, "", "Ziel")):
        cmd = {"richtung": "buy", "sl_usd": 826.0, "tp_usd": 700.0}
        for k, v in (("ohne_hedge", oh), ("final", fin), ("tages_grenze_usd", tg), ("final_grund", fg)):
            if v is not None:
                cmd[k] = v
        for extra in ({}, {"verlust_grenze_usd": None}, {"verlust_grenze_usd": ""}, {"verlust_grenze_usd": 0}, {"verlust_grenze_usd": -5}):
            c = dict(cmd, **extra)
            faelle += 1
            neu, alt = ob.nachzieh_cmd(c), alt_nc(c)
            if neu != alt or (neu is c) != (alt is c):
                abw += 1
ok(faelle > 1000 and abw == 0, f"{faelle} Aufträge ohne gültige Grenze (fehlt/leer/0/negativ): Ergebnis und Identität wie vor ST1b ({abw} Abweichungen)")

print("— 2) nachzieh_cmd mit Striking-Grenze —")
h = ob.nachzieh_cmd({"final": "blow", "tages_grenze_usd": 500.0, "verlust_grenze_usd": 950.0, "sl_usd": 826.0})
ok(h["tages_grenze_usd"] == 950.0 and h["grenze_art"] == "striking" and h["final"] is None, "Echo mit Hedge: Grenze 950 bleibt (statt None), Tagesgrenze 500 und 'blow' weiter aus")
h = ob.nachzieh_cmd({"final": "gewinntag", "verlust_grenze_usd": "950", "sl_usd": 750.0})
ok(h["tages_grenze_usd"] == 950.0 and h["final"] == "gewinntag", "Gewinntag-TP-Seite bleibt, Grenze als Zahl auch aus Text")
v2 = {"ohne_hedge": True, "tages_grenze_usd": 500.0, "verlust_grenze_usd": 950.0}
ok(ob.nachzieh_cmd(v2) is v2, "Echo V2: Tagesgrenze 500 ist schon enger → derselbe cmd")
v2b = ob.nachzieh_cmd({"ohne_hedge": True, "tages_grenze_usd": 1200.0, "verlust_grenze_usd": 950.0})
ok(v2b["tages_grenze_usd"] == 950.0 and v2b["grenze_art"] == "striking", "Echo V2: Striking-Grenze 950 enger als Tagesgrenze 1.200 → 950")

print("— 3) Lauf am Fill (Klick gestubbt): 10 $/Pkt, Fill 20.000, Kauf —")
klicks = []


class Stumm:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def klick(w, ticket, symbol, sl_text, tp_text, trail, anker_pfad=None, beweis=None):
    klicks.append((sl_text, tp_text))
    return {"ok": True}


def lesen(path, expected):
    k = klicks[-1]
    return {"positionen": [{"ticket": 7, "sl": float(k[0]), "tp": float(k[1])}]}


def lauf(abstand, cmd_extra=None, sl_usd=1000.0):
    klicks.clear()
    spur = []
    cmd = dict({"richtung": "buy", "sl_usd": sl_usd, "tp_usd": 2000.0}, **(cmd_extra or {}))
    erg = ob._sltp_nachziehen_lauf(None, "x", 1, {"ticket": 7}, cmd, "NAS100", 20000.0, 1.0, 10.0, 2, 20000.0 - abstand, 20210.0, spur, "a")
    return erg, spur


alt = (ob._kommission_lesen, ob._sltp_klicken, ob._api_lesen, ob._warte, ob._EchoUnruhe)
try:
    ob._kommission_lesen, ob._sltp_klicken, ob._api_lesen = (lambda *a: 0.0), klick, lesen
    ob._warte, ob._EchoUnruhe = (lambda *a, **k: None), Stumm
    e0, s0 = lauf(105.0)
    ok(not klicks and not e0["nachgezogen"] and e0["sl"] == 19895.0, "ohne Grenze (wie bisher): Plan 1.000 $, echter Verlust 1.050 $ (≤ + 15 %) → kein Klick")
    e1, s1 = lauf(105.0, {"verlust_grenze_usd": 950.0})
    ok(e1["nachgezogen"] and klicks == [("19905.00", "20210.00")] and e1["sl"] == 19905.0 and e1["tp"] == 20210.0,
       f"Striking-Grenze 950: Verlust 1.050 $ reißt sie → SL am Fill auf 950 $ (19.905), TP unverändert ({klicks})")
    ok(any("Striking-Grenze (Verlust je Trade < 1 %)" in x for x in s1) and any("(SL wegen Striking-Grenze)" in x for x in s1)
       and (e1.get("tagesgrenze") or {}).get("art") == "striking" and e1["tagesgrenze"]["ueber"] is True, "Spur und Rückgabe nennen die Striking-Grenze")
    e2, _ = lauf(94.0, {"verlust_grenze_usd": 950.0}, sl_usd=826.0)
    ok(not klicks and not e2["nachgezogen"], "Plan 826 $, echter Verlust 940 $ (unter Grenze und unter Plan + 15 %) → kein Klick")
    e3, s3 = lauf(109.0, {"verlust_grenze_usd": 950.0}, sl_usd=826.0)
    ok(e3["nachgezogen"] and klicks == [("19917.40", "20210.00")], f"S2-Fall: Plan 826 $, echter Verlust 1.090 $ → SL am Fill auf 826 $ (19.917,40) ({klicks})")
    e4, _ = lauf(109.0, {"verlust_grenze_usd": 950.0, "final": "gewinntag"}, sl_usd=826.0)
    ok(e4["nachgezogen"] and klicks == [("19917.40", "20200.00")], "Gewinntag: TP am Fill (20.200) und SL an der Grenze zusammen")
    ok(e3["soll_sl"] == 19917.4 and round((20000.0 - e3["soll_sl"]) * 10.0, 2) <= 950.0, "Verlust bis zum neuen SL ≤ Grenze")
finally:
    ob._kommission_lesen, ob._sltp_klicken, ob._api_lesen, ob._warte, ob._EchoUnruhe = alt
mp = {"price_open": 20000.0, "sl": 19895.0, "tp": 20210.0, "type": 0}
z1 = copier.plan_sltp(mp, faktor=105, min_puffer_punkte=1.0, point=0.01, digits=2)
z2 = copier.plan_sltp(dict(mp, sl=19905.0), faktor=105, min_puffer_punkte=1.0, point=0.01, digits=2)
ok(z2["tp"] > z1["tp"] and z1["sl"] == z2["sl"], "Hedge: Notfall-TP folgt dem neuen Master-SL (copier.plan_sltp, Formel unverändert)")

print("— 4) Weg Planer → PC-Tab → Panel —")
panel = open(os.path.join(WURZEL, "mt5-copier", "panel.py"), encoding="utf-8").read()
ok('if _vg is not None and _vg > 0:\n                cmd["verlust_grenze_usd"] = _vg' in panel, "panel.py: Feld nur, wenn > 0 (sonst kein Schlüssel im cmd)")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
ok("...(stGrenzeUsd(plan) ? { verlust_grenze_usd: stGrenzeUsd(plan) } : {})" in html and "fp.striking === true ? Number(fp.verlust_grenze_usd)" in html,
   "PC-Tab (Echo mit Hedge): Body nur bei Striking-Plänen erweitert")
app_src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
ok('"verlust_grenze_usd": r.get("verlust_grenze_usd")' in app_src and 'r["verlust_grenze_usd"] = fcp_striking_verlust_grenze(regel, g)' in app_src,
   "Planer: funded_plan.verlust_grenze_usd nur bei Striking")
ok(ob.NACHZIEH_SL_TOLERANZ == 0.15, "Bot-Toleranz 0,15 (FCP_STRIKING_NACHZIEH_TOLERANZ − 1 in app.py)")

print()
print("alle Tests bestanden" if not FEHLER else f"{len(FEHLER)} ROT")
sys.exit(1 if FEHLER else 0)
