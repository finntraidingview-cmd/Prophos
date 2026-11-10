#!/usr/bin/env python3
"""Selbsttest ZT1 Ziel-Toleranz im Funded-CFD-Planer (Finn 10.11.2026: „Gib dem Ziel so grob 10 % Puffer … für mich ist der Account quasi schon gepasst“).
Rechnet die echten Funktionen aus app.py ohne Netz/DB: fcp_ziel_schwelle, fcp_konto_rechnen (ohne/mit Consistency), fcp_cons_finn (fertig ab Schwelle),
Consistency bleibt Pflicht; dazu im Frontend wdlFcfdZielAb (Radar) per jsc und die Einstellung im Panel.
Fall (Platzhalter-Konto): FundedNext 50k Funded CFD, Zyklus 2, Ziel fest +1.566 $, Gewinn +1.441,70 $ (fehlen 124,30 $ = 7,9 %).

Aufruf:  python3 tools/selftest_zt1_ziel_toleranz.py"""
import json
import os
import random
import re
import subprocess
import tempfile
from datetime import datetime, timezone, timedelta

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "random": random}


def lade(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^\S)", app, re.S | re.M)
    exec(m.group(0), ns)


def ruf(fn, *a, **k):
    for _ in range(80):
        try:
            return ns[fn](*a, **k) if callable(ns.get(fn)) else ns[fn]
        except (NameError, KeyError) as e:
            n = str(e).split("'")[1]
            lade(n)
    raise RuntimeError(fn)


for n in ("FCP_ZIEL_TOLERANZ_PCT", "fcp_ziel_schwelle", "fcp_ziel_toleranz_info", "fcp_param_standard", "fcp_konto_rechnen", "fcp_cons_finn", "fcp_je_groesse"):
    lade(n)

P = ruf("fcp_param_standard")
check(P.get("ziel_toleranz_pct") == 10.0, "Standard der Einstellung: 10 %")
check(ruf("fcp_ziel_schwelle", 1566, P) == 1409.4, "Schwelle 1.566 × 0,9 = 1.409,40")
check(ruf("fcp_ziel_schwelle", 1566, dict(P, ziel_toleranz_pct=0.0)) == 1566.0, "Toleranz 0 → genau das Ziel (wie vor ZT1)")
check(ruf("fcp_ziel_schwelle", 1000, dict(P, ziel_toleranz_pct=25.0)) == 750.0, "Toleranz 25 % → 750 von 1.000")
check(ruf("fcp_ziel_schwelle", 1000, dict(P, ziel_toleranz_pct=80.0)) == 900.0, "ungültig (> 50 %) → Standard 10 %")
check(ruf("fcp_ziel_schwelle", 1000, None) == 900.0, "ohne Parameter → Standard 10 %")
check(ruf("fcp_ziel_schwelle", None, P) is None, "ohne Ziel → keine Schwelle")
info = ruf("fcp_ziel_toleranz_info", 1566, 1441.7, P)
check(info and info["fehlt"] == 124.3 and info["pct"] == 10.0, f"Info: −124,30 $ in Toleranz ({info})")
check(ruf("fcp_ziel_toleranz_info", 1566, 1600, P) is None and ruf("fcp_ziel_toleranz_info", 1566, 1300, P) is None, "Info nur, wenn erst dank Toleranz erreicht")
check("fcp_ziel_schwelle(" in app and '"ziel_toleranz_pct": (0, 50)' in app, "Grenze der Einstellung 0–50 % (FCP_PARAM_GRENZEN)")

# Planer ohne Consistency (FundedNext 50k, Werte wie funded_cfd_plan_regeln)
FN = {"namen": ["fundednext"], "je_groesse": {"50000": {"dd": 5000, "sl": [875, 1225], "lots": [1, 1.75], "ziel": [1500, 1850], "sl_1pct": [300, 400], "hedge_eur": 750}},
      "erster_payout": {"ziel": [50, 150], "hedge_eur_je_dd": 0.5}, "tp_modus": "ziel"}
jg = ruf("fcp_je_groesse", FN, 50000)
zf = {"at": "2026-11-09T10:43:20+00:00", "usd": 1566, "zyklus": 2}
r = ruf("fcp_konto_rechnen", jg, 51441.7, 50000.0, 2, False, 1.0, 0.85, random.Random(3), FN, param=P, ziel_fest=zf)
check(r["aktion"] == "ziel", f"Fall: Gewinn +1.441,70 bei Ziel fest 1.566 → Ziel erreicht, kein neuer Trade ({r.get('aktion')}, {r.get('grund')})")
r0 = ruf("fcp_konto_rechnen", jg, 51441.7, 50000.0, 2, False, 1.0, 0.85, random.Random(3), FN, param=dict(P, ziel_toleranz_pct=0.0), ziel_fest=zf)
check(r0["aktion"] == "planen", f"Toleranz 0 → wie bisher noch ein Trade ({r0.get('aktion')}, TP {r0.get('tp')})")
r1 = ruf("fcp_konto_rechnen", jg, 51300.0, 50000.0, 2, False, 1.0, 0.85, random.Random(3), FN, param=P, ziel_fest=zf)
check(r1["aktion"] == "planen", f"Gewinn +1.300 (unter 1.500 × 0,9 = 1.350) → weiter planen ({r1.get('aktion')})")

# Prüfer S1: Bezug = festes Ziel (wie /konto-ziele) — festes Ziel 1.850 → Schwelle 1.665; Gewinn 1.550 liegt über dem unteren Wert 1.500, aber darunter
zf_hoch = {"at": "2026-11-09T10:43:20+00:00", "usd": 1850, "zyklus": 2}
rs = ruf("fcp_konto_rechnen", jg, 51550.0, 50000.0, 2, False, 1.0, 0.85, random.Random(3), FN, param=P, ziel_fest=zf_hoch)
check(rs["aktion"] == "planen", f"festes Ziel 1.850, Gewinn 1.550 → weiter planen (Schwelle 1.665) ({rs.get('aktion')}, TP {rs.get('tp')})")
rs2 = ruf("fcp_konto_rechnen", jg, 51700.0, 50000.0, 2, False, 1.0, 0.85, random.Random(3), FN, param=P, ziel_fest=zf_hoch)
check(rs2["aktion"] == "ziel" and (rs2.get("ziel_toleranz") or {}).get("fehlt") == 150.0, f"festes Ziel 1.850, Gewinn 1.700 → Ziel, −150 $ in Toleranz ({rs2.get('ziel_toleranz')})")
check(ruf("fcp_konto_rechnen", jg, 51441.7, 50000.0, 2, False, 1.0, 0.85, random.Random(3), FN, param=P, ziel_fest=zf)["ziel_toleranz"]["fehlt"] == 124.3,
      "Planer und Konto-Seite rechnen dieselben −124,30 $ (festes Ziel 1.566)")

# Prüfer M1: On Demand = Payout-Mindestsumme der Firma, im Planer ohne Toleranz (param ziel_toleranz_pct 0 je Konto)
check('param=(dict(param_u, ziel_toleranz_pct=0.0) if od_an else param_u)' in app and app.count("ziel_toleranz_pct=0.0)") >= 3,
      "On Demand ohne Toleranz: Planer, /konto-ziele und Radar")
OD = dict(FN, consistency_pct=40, tp_modus=None, erster_payout=False)
jod = dict(jg, ziel=[2000.0, 2250.0])
tw_od = {"b": 600.0, "w": 1810.0, "serie": 0, "serie_n": 0}
ro = ruf("fcp_konto_rechnen", jod, 101810.0, 100000.0, 3, False, 1.0, 0.85, random.Random(3), OD, param=dict(P, ziel_toleranz_pct=0.0), tage=tw_od,
         ziel_fest={"usd": 2000, "zyklus": 3})
check(ro["aktion"] != "ziel", f"On Demand 100k, Gewinn 1.810 bei 2.000 → kein Ziel (ohne Toleranz) ({ro.get('aktion')})")

# Prüfer S3: Meldung nennt die Toleranz
lade("fcp_wartet_meldung"); lade("_liq_de")
_t, txt, _d = ruf("fcp_wartet_meldung", dict(r, user="ID", konto="50k …0000"))
check("Ziel 1.566 $ · −124 $ in Toleranz (10 %)" in txt, f"Meldung: „Gewinn 1.442 $ / Ziel 1.566 $ · −124 $ in Toleranz (10 %)“ ({txt})")

# Consistency bleibt Pflicht (Firma mit 50 % Consistency)
C = dict(FN, consistency_pct=50, tp_modus=None)
tw_gut = {"b": 500.0, "w": 1442.0, "serie": 0, "serie_n": 0}
tw_schlecht = {"b": 1000.0, "w": 1442.0, "serie": 0, "serie_n": 0}
rc = ruf("fcp_konto_rechnen", jg, 51441.7, 50000.0, 2, False, 1.0, 0.85, random.Random(3), C, param=P, tage=tw_gut, ziel_fest=zf)
check(rc["aktion"] == "ziel", f"Consistency erfüllt + Gewinn in Toleranz → Ziel erreicht ({rc.get('aktion')}, {rc.get('grund')})")
rc2 = ruf("fcp_konto_rechnen", jg, 51441.7, 50000.0, 2, False, 1.0, 0.85, random.Random(3), C, param=P, tage=tw_schlecht, ziel_fest=zf)
check(rc2["aktion"] != "ziel", f"Consistency verletzt (größter Tag 1.000 > 50 % von 1.442) → kein Ziel trotz Toleranz ({rc2.get('aktion')}, {rc2.get('grund')})")
cf = ruf("fcp_cons_finn", 50.0, 1566.0, 1441.7, tw_gut, None, ziel_min=1409.4)
check(cf["fertig"] is True, "fcp_cons_finn: fertig ab der Schwelle")
cf0 = ruf("fcp_cons_finn", 50.0, 1566.0, 1441.7, tw_gut, None)
check(cf0["fertig"] is False, "fcp_cons_finn ohne ziel_min: wie bisher erst am Ziel")
cf2 = ruf("fcp_cons_finn", 50.0, 1566.0, 1441.7, tw_gut, None, ziel_min=2000)
check(cf2["fertig"] is False, "ziel_min über dem Ziel wird ignoriert (nie strenger als das Ziel)")

# /konto-ziele + Radar (Quelltext): gleiche Schwelle, Anzeige „Ziel erreicht (−… $ in Toleranz)“
check("erreicht = wartet or bal >= ziel_bal or (_sw is not None and gewinn >= _sw - 0.005)" in app and "in Toleranz)\" if zt_info else \"\")" in app,
      "/konto-ziele: Ziel-Check mit Toleranz, Text „Ziel erreicht (−… $ in Toleranz)“")
check('"ziel_erreicht_ab": (_zw.get("ziele_tol") or {})' in app, "Radar-Zeile trägt ziel_erreicht_ab")

# Frontend: wdlFcfdZielAb per jsc
i = html.index("  function wdlFcfdZielAb(t){")
fn = html[i:html.index("\n  }", i) + 4]
js = fn + "\nprint(JSON.stringify([wdlFcfdZielAb({ ziel_usd: 51500, ziel_erreicht_ab: 51350 }), wdlFcfdZielAb({ ziel_usd: 51500 }), wdlFcfdZielAb({ ziel_usd: 51500, ziel_erreicht_ab: 52000 }), wdlFcfdZielAb({})]))"
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
rr = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d.name], capture_output=True, text=True)
os.unlink(d.name)
e = json.loads(rr.stdout.strip().splitlines()[-1]) if rr.returncode == 0 else None
check(e == [51350, 51500, 52000, None], f"Radar: Ziel ab Toleranz-Schwelle (auch über dem unteren Wert bei festem Ziel), ohne Feld wie bisher ({e} {rr.stderr[:200]})")
check("zielRest(b.bal, wdlFcfdZielAb(t))" in html and "Number(b.bal) < wdlFcfdZielAb(t)" in html, "Radar-Vorauswahl und Ein-Klick-Prüfung nutzen die Schwelle")
check("{ param: 'ziel_toleranz_pct' }" in html and "'Ziel-Toleranz'" in html, "Einstellung „Ziel-Toleranz“ im Funded Planer → CFD")

print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER")
raise SystemExit(1 if fehler else 0)
