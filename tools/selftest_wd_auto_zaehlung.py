#!/usr/bin/env python3
"""Selbsttest Winning Days automatisch (Finn 03.11.2026 ~01:35 Dubai, Fall Mike Apex 100k …0002: drei Gewinn-Tage, gezählt 2).
Rechnet app.py wd_* und prophos.html zielWdAuto/zielWdMin mit denselben Fällen, ohne Netz und ohne DB.

Aufruf:  python3 tools/selftest_wd_auto_zaehlung.py"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


from datetime import datetime, timedelta, timezone  # noqa: E402
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


for n in ("WD_GOOD_DAY_MIN", "wd_min_gewinn", "wd_auto_konto", "_wd_iso_ts", "wd_auto_tage", "wd_gezaehlte_tage", "wd_auto_stand", "_wd_good_day_konto_upd", "_cme_handelstag"):
    lade(n)
ns["ap_klasse"] = lambda route=None, firma=None: "futures" if re.search(r"tradeify|apex|topstep|lucid|futur", str(firma or ""), re.I) else "cfd"

MIKE = {"id": "m2", "name": "100k PAAPEX6708370000002 → Winning Days", "firm": "Apex Trader", "account_type": "winning_days", "goal_kind": "winning_days",
        "goal_manual": True, "goal_target": 5, "goal_done_offset": 2, "goal_wd_korrektur": 0, "goal_wd_seit": None, "created_at": "2026-10-26T10:00:00+00:00"}
PL = [("2026-10-28T15:00:00+00:00", -1756.20), ("2026-10-29T15:00:00+00:00", 1773.80), ("2026-10-30T15:00:00+00:00", 5963.80), ("2026-11-02T15:00:00+00:00", 6043.80)]
PLAENE = [{"master_account_id": "m2", "status": "completed", "master_pl": v, "ended_at": t} for t, v in PL]
check(ruf("wd_min_gewinn", MIKE) == 300, "Apex 100k: Mindestgewinn 300 $")
check(ruf("wd_auto_konto", MIKE) and not ruf("wd_auto_konto", {k: v for k, v in MIKE.items() if k != "goal_wd_korrektur"}), "Automatik nur, wenn die Spalte gelesen wurde")
check(ruf("wd_auto_stand", MIKE, PLAENE) == 3, f"Mike: 3 Gewinn-Tage (Verlusttag zählt nicht) → {ruf('wd_auto_stand', MIKE, PLAENE)}")
zwei = PLAENE + [{"master_account_id": "m2", "status": "review", "master_pl": 200, "ended_at": "2026-11-02T18:00:00+00:00"}]
check(ruf("wd_auto_stand", MIKE, zwei) == 3, "zwei Trades am selben CME-Tag = ein Tag")
klein = [{"master_account_id": "m2", "status": "completed", "master_pl": 250, "ended_at": "2026-11-03T15:00:00+00:00"}]
check(ruf("wd_auto_stand", MIKE, PLAENE + klein) == 3, "Tagessumme unter dem Mindestgewinn (250 < 300) zählt nicht")
check(ruf("wd_auto_stand", dict(MIKE, goal_wd_seit="2026-10-31T00:00:00+00:00"), PLAENE) == 1, "nur ab Zyklus-Start (Payout-Anfrage)")
check(ruf("wd_auto_stand", dict(MIKE, goal_wd_korrektur=-1), PLAENE) == 2 and ruf("wd_auto_stand", dict(MIKE, goal_wd_korrektur=1), PLAENE) == 4, "Korrektur von Hand ±")
check(ruf("wd_min_gewinn", {"firm": "Tradeify", "name": "150k"}) == 250 and ruf("wd_min_gewinn", {"firm": "Topstep"}) == 150
      and ruf("wd_min_gewinn", {"firm": "Apex Trader", "name": "150k …"}) == 350 and ruf("wd_min_gewinn", {"firm": "Tradeify CFD"}) is None, "Mindestgewinn je Firma wie WD_GOOD_DAY_MIN")
u = ruf("_wd_good_day_konto_upd", dict(MIKE, goal_manual_last=None, goal_wd_hand_tage=["2026-10-29"]), "2026-11-03", 1500, "2026-11-03")
check(u and "goal_wd_korrektur" not in u and u["goal_wd_hand_tage"] == ["2026-10-29", "2026-11-03"], "Haken legt den CME-Tag des Trades in die Menge, keine Korrektur")
# Stopp S9 zu b140ad39 a): A +200 abgehakt (Hand-Tag), B +150 am selben Tag → Summe 350 zählt automatisch — der Tag zählt EINMAL
AB = PLAENE + [{"master_account_id": "m2", "status": "completed", "master_pl": 200, "ended_at": "2026-11-03T14:00:00+00:00"},
               {"master_account_id": "m2", "status": "completed", "master_pl": 150, "ended_at": "2026-11-03T16:00:00+00:00"}]
check(ruf("wd_auto_stand", dict(MIKE, goal_wd_hand_tage=["2026-11-03"]), AB) == 4, "Haken + Automatik am selben Tag = ein Tag (S9 Fall a)")
# b): A +400 abgehakt, B −200 am selben Tag → Summe 200 < 300, die Automatik zählt nicht — der Haken bleibt
AB2 = PLAENE + [{"master_account_id": "m2", "status": "completed", "master_pl": 400, "ended_at": "2026-11-03T14:00:00+00:00"},
                {"master_account_id": "m2", "status": "completed", "master_pl": -200, "ended_at": "2026-11-03T16:00:00+00:00"}]
check(ruf("wd_auto_stand", dict(MIKE, goal_wd_hand_tage=["2026-11-03"]), AB2) == 4, "Haken bleibt, auch wenn die Tagessumme später unter die Linie fällt (S9 Fall b)")
check(ruf("wd_auto_stand", dict(MIKE, goal_wd_seit="2026-11-01T00:00:00+00:00", goal_wd_hand_tage=["2026-10-20"]), PLAENE) == 1, "Hand-Tage vor dem Zyklus-Start zählen nicht")
u = ruf("_wd_good_day_konto_upd", {k: v for k, v in MIKE.items() if k != "goal_wd_korrektur"}, "2026-11-03", 1500)
check(u and u["goal_done_offset"] == 3, "ohne Spalte: alter Weg goal_done_offset +1")

lade("payout_anfrage_konto_felder")
ns.setdefault("WD_BALANCE_FUTURES", ("tradeify", "apex", "topstep", "futur", "mffu", "lucid"))
f = ruf("payout_anfrage_konto_felder", MIKE, None, "2026-11-04")
check(f.get("goal_wd_korrektur") == 0 and f.get("goal_wd_hand_tage") == [] and f.get("goal_wd_seit") and f.get("goal_done_offset") == 0, "Payout-Anfrage: neuer Zyklus ab jetzt, Korrektur 0, Hand-Tage leer")

if shutil.which("osascript"):
    def fn(name):
        i = html.index("function " + name + "(")
        return html[i:html.index("\n  }\n", i) + 5]
    js = """function run(){ var window = {}, tradePlans = %s;
function tvV2Handelstag(d){ var ms = d == null ? Date.now() : (typeof d === 'number' ? d : Date.parse(d)); var t = new Date(ms + 7*3600*1000 - 6*3600*1000); return t.toISOString().slice(0,10) }
""" % json.dumps([{"masterAccountId": "m2", "status": "completed", "masterPl": v, "endedAt": t} for t, v in PL]) + fn("zielWdMin") + fn("zielWdAuto") + """
var a = { id: 'm2', firm: 'Apex Trader', name: '100k PAAPEX6708370000002', goalWdKorrektur: 0, goalWdSeit: null, createdAt: '2026-10-26T10:00:00+00:00', goalWdHandTage: [] };
return JSON.stringify({ n: zielWdAuto(a).count, k: zielWdAuto(Object.assign({}, a, { goalWdKorrektur: -1 })).count, fremd: zielWdAuto(Object.assign({}, a, { goalWdStand: 4 })).count, min: zielWdMin(a),
  hand: zielWdAuto(Object.assign({}, a, { goalWdHandTage: ['2026-10-30', '2026-11-03'] })).count }) }"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
        t.write(js)
    try:
        r = subprocess.run(["osascript", "-l", "JavaScript", t.name], capture_output=True, text=True, timeout=30)
    finally:
        os.unlink(t.name)
    check(r.returncode == 0, "Frontend-Rechnung läuft (" + r.stderr[:200] + ")")
    if r.returncode == 0:
        d = json.loads(r.stdout)
        check(d == {"n": 3, "k": 2, "fremd": 4, "min": 300, "hand": 4}, f"Frontend zielWdAuto wie Railway: Mike 3, Korrektur −1 → 2, fremd = Railway-Stand, Apex 100k 300, Hand-Tage als Menge (30.10. doppelt → 4) ({d})")
check("if(k.manual && k.kind === 'winning_days' && a.goalWdKorrektur !== undefined)" in html, "zielFortschritt nutzt die Automatik nur mit gelesener Spalte")
print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
