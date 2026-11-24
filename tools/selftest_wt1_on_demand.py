#!/usr/bin/env python3
"""Selbsttest WT1 (Finn 25.11.2026 „bei On Demand“: Waiting erst ab dem Mindest-Profit — 2 % = 2.000 $ bei 100k, ohne Toleranz; Nicht-On-Demand bleibt wie
bisher). Befund Aurel · FundedNext 100k …7785: im Lauf, der Waiting setzte, war das Flag on_demand noch nicht gesetzt → Refund-Zyklus (Ziel 104 $), Waiting
bei +96 $. Jetzt: On Demand = Flag ODER „On Demand“ im Namen (fcp_ist_on_demand) an allen Wegen. Geprüft: fcp_ist_on_demand, fcp_konto_rechnen mit
On-Demand-Regel (kein Refund, nie Waiting unter 2.000, ab 2.000 + Consistency ja), fcp_planen-Trockenlauf (Name ohne Flag → On-Demand-Weg), Nicht-On-Demand
unverändert (Toleranz 10 % gilt weiter), Quelltext der übrigen Wege. Ohne Netz. Aufruf: python3 tools/selftest_wt1_on_demand.py"""
import copy
import json
import os
import random
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


print("1) fcp_ist_on_demand")
I = app.fcp_ist_on_demand
check(I({"on_demand": True, "name": "100k 1 → Funded"}) and I({"on_demand": False, "name": "100k 14367785 → Funded · On Demand"})
      and I({"name": "100k 1 → Funded · on-demand"}) and I({"name": "100k 1 → Funded · 1% Rule · On Demand"}),
      "Flag ODER Name-Teil „ · On Demand“ (auch on-demand, nach anderen Add-ons)")
check(not I({"on_demand": False, "name": "100k 14357057 → Funded"}) and not I({}) and not I(None) and not I({"on_demand": "true", "name": "x"}),
      "ohne Flag und ohne Namenszusatz → kein On Demand")
check(not I({"name": "Simon Demand 100k"}) and not I({"name": "100k Jason-Demands"}) and not I({"name": "100k 7785 → Funded · On Demand Ina"})
      and not I({"name": "100k On Demand 7785 → Funded"}),
      "nur der Add-on-Teil zählt (Review): „Simon Demand“, „· On Demand Ina“, Kopf-Text → nein — genau das, was „On Demand aus“ wieder entfernt")

print("2) Planer-Rechnung mit On-Demand-Regel (FundedNext 100k)")
FN = {"namen": ["fundednext"], "erster_payout": {"ziel": [50, 150], "hedge_eur_je_dd": 0.5}, "on_demand": {"ziel_je_100k": [2050, 2300]},
      "je_groesse": {"100000": {"dd": 10000, "sl": [2000, 2300], "lots": [1.0, 1.75], "ziel": [1500, 1850], "hedge_eur": 1500}}}
jg = app.fcp_je_groesse(FN, 100000)
od = app.fcp_on_demand_anwenden(FN, jg, 100000)
check(od is not None and od[1].get("ziel_min") == 2000.0 and od[0].get("erster_payout") is False,
      f"On-Demand-Regel: Firmen-Minimum 2.000 (Standard min_je_100k), kein Refund-Zyklus ({od[1].get('ziel_min') if od else None})")
P0 = dict(app.fcp_param_standard(), ziel_toleranz_pct=0.0)   # On Demand ohne Toleranz (wie fcp_planen, kz_rechnen, Radar)


def rod(bal, zyk, zf, tage):
    return app.fcp_konto_rechnen(od[1], bal, 100000.0, zyk, False, 1.0, 0.85, random.Random(3), od[0], param=P0, ziel_fest=zf, tage=tage)


r = rod(100096.40, 1, {"usd": 104, "zyklus": 1}, (96.4, 1))
check(r["aktion"] != "ziel" and not r.get("erster_payout"), f"Aurel-Fall als On Demand: +96,40 (altes Refund-Ziel 104 gespeichert) → kein Waiting, kein Refund ({r['aktion']}, TP {r.get('tp')})")
r = rod(101950.0, 2, {"usd": 2161, "zyklus": 2}, {"b": 600.0, "w": 1950.0, "serie": 0, "serie_n": 0})
check(r["aktion"] != "ziel", f"+1.950 (97,5 % von 2.000) → kein Waiting, keine Toleranz ({r['aktion']})")
r = rod(102000.0, 2, {"usd": 2161, "zyklus": 2}, {"b": 600.0, "w": 2000.0, "serie": 0, "serie_n": 0})
check(r["aktion"] == "ziel", f"+2.000 = Mindest-Profit, Consistency 30 % ≤ 40 % → Waiting ({r['aktion']})")
r = rod(102100.0, 2, {"usd": 2161, "zyklus": 2}, {"b": 1500.0, "w": 2100.0, "serie": 0, "serie_n": 0})
check(r["aktion"] != "ziel", f"+2.100, aber größter Tag 1.500 > 40 % → Consistency offen, kein Waiting ({r['aktion']})")

print("3) Nicht-On-Demand bleibt wie bisher (Finn: normaler Zyklus mit Termin)")
rn = app.fcp_konto_rechnen(jg, 101445.70, 100000.0, 2, False, 1.0, 0.85, random.Random(3), FN, param=app.fcp_param_standard(), ziel_fest={"usd": 1538, "zyklus": 2})
check(rn["aktion"] == "ziel", f"Mike FundedNext 100k …7057 (kein On Demand): 1.445,70 ≥ 1.538 × 0,9 → Ziel wie bisher, nur im Bericht gelistet ({rn['aktion']})")

print("4) fcp_planen-Trockenlauf: Name „On Demand“ ohne Flag → On-Demand-Weg")
JETZT = datetime(2026, 11, 25, 6, 0, tzinfo=timezone.utc)
H1 = "11111111-1111-1111-1111-111111111111"
sql = open(os.path.join(WURZEL, "sql", "2026-10-30_funded_cfd_planer.sql"), encoding="utf-8").read()
FIRMEN = json.loads(re.search(r"'(\[\s*\{.*?\]\s*)'::jsonb", sql, re.S).group(1))
for f in FIRMEN:
    f["an"] = True
K = {"id": "a1000000-0000-0000-0000-000000007785", "user_id": H1, "name": "100k 14367785 → Funded · On Demand", "firm": "FundedNext",
     "account_type": "funded_cfd", "external_id": "14367785", "tv_balance": 100096.4, "tv_balance_at": "2026-11-25T05:00:00+00:00", "tv_balance_quelle": "mt5",
     "created_at": "2026-11-02T12:25:08+00:00", "on_demand": False, "auto_planer": True, "max_drawdown": 10000, "fcp_ziel": {"usd": 104, "zyklus": 1}}
HEART = (JETZT - timedelta(minutes=2)).isoformat()


def sb_select(t, p):
    if t == "funded_cfd_plan_regeln":
        return [{"id": 1, "aktiv": False, "auto_bestaetigen": False, "ziel_auto_wartet": False, "user_ids": [H1], "firmen": copy.deepcopy(FIRMEN),
                 "zeiten": {"firma_abstand_min": 15, "abstand_id_min": 10, "vorlauf_min": 15}}]
    if t == "auto_plan_regeln":
        return [{"zeiten": {"fenster_tz": "Asia/Dubai", "fenster": [["04:00", "18:00"]]}}]
    return []


def sb_all(t, p):
    if t == "accounts" and p.get("account_type") == "eq.funded_cfd":
        return [dict(K)]
    if t == "accounts":
        return [{"id": "f1", "user_id": H1, "external_id": "900001", "name": "Fusion f1", "firm": "Fusion Markets"}]
    if t == "user_settings":
        return [{"user_id": H1, "value": {"accountId": "f1"}}]
    if t == "firm_specs":
        return [{"user_id": H1, "name": "FundedNext", "ppl": 10.0, "unit": "Lots"}]
    if t == "id_gruppe_mitglied":
        return [{"user_id": H1, "gruppe_id": "ht"}]
    return []


app.sb_select, app._sb_all = sb_select, sb_all
app.sb_insert = lambda t, z: None
app.sb_update = lambda t, f, u: [{"id": f.get("id", "")[3:]}]
app._sb_anfrage = lambda m, *a, **k: None
app._sb_pruefen = lambda r: None
app._ap_archiviert = lambda streng=False: set()
app._ap_namen = lambda: ({H1: "Aurel"}, set())
app.admin_gruppen_daten = lambda: {"gruppen": [{"id": "ht", "name": "Hermann Technologies", "verwalter_id": None}], "mitglieder": [{"user_id": H1, "gruppe_id": "ht"}]}
app.alarm_senden = lambda *a, **k: (1, 1)
app.tw_pause_grund = lambda *a, **k: None
app._ap_balance_karten = lambda: ({"14367785": (100096.4, "USD", HEART)}, {})
e = app.fcp_planen(trocken=True, jetzt=JETZT, seed=7)
z = next((x for k in ("geplant", "ziel", "ausgelassen") for x in (e.get(k) or []) if x.get("konto_id") == K["id"]), {})
kz = next((x for x in (e.get("konten_stand") or []) if x.get("konto_id") == K["id"]), {})
check(z and z.get("aktion") != "ziel" and z.get("tp_art") != "erster_payout_refund" and not z.get("erster_payout"),
      f"Aurel …7785 (Name On Demand, Flag aus): kein Refund-Ziel, kein Waiting ({z.get('aktion')}, {z.get('tp_art')}, {z.get('grund')})")
check(z.get("on_demand") is True or kz.get("on_demand") is True, f"Konto läuft als On Demand ({z.get('on_demand')}/{kz.get('on_demand')})")

print("5) übrige Wege")
src = open(os.path.join(WURZEL, "app" + ".py"), encoding="utf-8").read()
check(src.count("fcp_ist_on_demand(") >= 7 and 'a.get("on_demand") is True' not in src,
      "fcp_planen, /konto-ziele, Radar-Ziel, Radar-Waiting, Payout-Termin (2×) nutzen fcp_ist_on_demand — kein Flag-only-Vergleich mehr")
check('"select": "id,account_type,on_demand,name"' in src, "Payout-Termin liest den Namen mit")
check('"select": "id,name,on_demand", "account_type": "eq.funded_cfd"}) or [])\n                 if fcp_ist_on_demand(a)}' in src,
      "/admin/overview: on_demand der Admin-Zeilen = Flag ODER Name (Admin → Payouts, Erhalten, Waiting-Liste lesen es)")
check('"or": "(on_demand.is.true,name.ilike.*demand*)"' in src and "not fcp_ist_on_demand(a) or not a.get(\"waiting_payout_since\")" in src,
      "Radar Bestanden → Waiting (BS1): Abfrage und Prüfung mit Name")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("String(row.name || '').split('·').some(t => /^on[\\s-]*demand$/i.test(t.trim()))" in html, "eigene Konten (rowToAccount): onDemand = Flag ODER Add-on-Teil (wie ADDON_OD_RE)")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ alle Prüfungen grün")
