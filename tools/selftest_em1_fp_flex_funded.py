#!/usr/bin/env python3
"""Selbsttest EM1 (Master 24.11.2026, Emin · FundingPips 100k …8250 „Funded · Striking · Flex“, Max DD 12.000): der Funded-CFD-Planer ließ das Konto
jeden Lauf mit „Flex-Konto — plant der Funded-CFD-Planer noch nicht“ aus — „flex“ ist Pflicht-Sperrwort der Firma, und FundingPips hat keine Funded-Flex-Werte.
Geprüft (Trockenlauf fcp_planen, ohne Netz): (1) ohne Flex-Variante der Firma → wie bisher ausgelassen; (2) mit Flex-Variante (regel.flex, ab_dd_pct 12, wie
BG2) und Max DD ≥ 12 % → das Sperrwort „flex“ greift nicht mehr, das Konto läuft in den Planer (Striking-Werte obendrauf); (3) Flex-Variante da, aber Konto
mit 10 % DD → Variante greift nicht → „flex“ im Namen sperrt weiter; (4) andere Sperrwörter bleiben. Aufruf: python3 tools/selftest_em1_fp_flex_funded.py"""
import copy
import json
import os
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


JETZT = datetime(2026, 11, 24, 6, 0, tzinfo=timezone.utc)
H1 = "11111111-1111-1111-1111-111111111111"
sql = open(os.path.join(WURZEL, "sql", "2026-10-30_funded_cfd_planer.sql"), encoding="utf-8").read()
FIRMEN0 = json.loads(re.search(r"'(\[\s*\{.*?\]\s*)'::jsonb", sql, re.S).group(1))
fp = next((f for f in FIRMEN0 if "fundingpips" in (f.get("namen") or [])), None)
check(fp is not None, "FundingPips-Regel in der Planer-Vorlage")
fp["ohne_namen"] = sorted(set((fp.get("ohne_namen") or []) + ["flex"]))
fp["an"] = True
FLEX = {"ab_dd_pct": 12, "name": "Flex", "je_groesse": {"100000": dict((fp.get("je_groesse") or {}).get("100000") or {}, dd=12000)}}


def konto(i, n, dd):
    return {"id": i, "user_id": H1, "name": n, "firm": "FundingPips", "account_type": "funded_cfd", "external_id": "2120" + i[-4:], "tv_balance": 100000,
            "tv_balance_at": "2026-11-24T05:00:00+00:00", "tv_balance_quelle": "mt5", "created_at": "2026-11-07T18:52:17+00:00", "max_drawdown": dd,
            "striking": True, "auto_planer": True}


EMIN = konto("e1000000-0000-0000-0000-000000008250", "100k 21208250 → Funded · Striking · Flex", 12000)
FLEX10 = konto("e1000000-0000-0000-0000-000000000010", "100k 21200010 → Funded · Flex", 10000)
DEMO = konto("e1000000-0000-0000-0000-000000000011", "100k 21200011 → Funded · Flex · Demo", 12000)
KONTEN = [EMIN, FLEX10, DEMO]
HEART = (JETZT - timedelta(minutes=2)).isoformat()
STATE = {"firmen": None}


def sb_select(t, p):
    if t == "funded_cfd_plan_regeln":
        return [{"id": 1, "aktiv": False, "auto_bestaetigen": False, "ziel_auto_wartet": False, "user_ids": [H1], "firmen": STATE["firmen"],
                 "zeiten": {"firma_abstand_min": 15, "abstand_id_min": 10, "vorlauf_min": 15}}]
    if t == "auto_plan_regeln":
        return [{"zeiten": {"fenster_tz": "Asia/Dubai", "fenster": [["04:00", "18:00"]]}}]
    return []


def sb_all(t, p):
    if t == "accounts" and p.get("account_type") == "eq.funded_cfd":
        return [dict(a) for a in KONTEN]
    if t == "accounts":
        return [{"id": "f1", "user_id": H1, "external_id": "900001", "name": "Fusion f1", "firm": "Fusion Markets"}]
    if t == "user_settings":
        return [{"user_id": H1, "value": {"accountId": "f1"}}]
    if t == "firm_specs":
        return [{"user_id": H1, "name": "FundingPips", "ppl": 20.0, "unit": "Lots"}]
    if t == "id_gruppe_mitglied":
        return [{"user_id": H1, "gruppe_id": "ht"}]
    return []


app.sb_select, app._sb_all = sb_select, sb_all
app.sb_insert = lambda t, z: None
app.sb_update = lambda t, f, u: [{"id": f.get("id", "")[3:]}]
app._sb_anfrage = lambda m, *a, **k: None
app._sb_pruefen = lambda r: None
app._ap_archiviert = lambda streng=False: set()
app._ap_namen = lambda: ({H1: "Emin"}, set())
app.admin_gruppen_daten = lambda: {"gruppen": [{"id": "ht", "name": "Hermann Technologies", "verwalter_id": None}], "mitglieder": [{"user_id": H1, "gruppe_id": "ht"}]}
app.alarm_senden = lambda *a, **k: (1, 1)
app.tw_pause_grund = lambda *a, **k: None
app._ap_balance_karten = lambda: ({a["external_id"]: (100000, "USD", HEART) for a in KONTEN}, {})


def lauf(firmen):
    STATE["firmen"] = firmen
    e = app.fcp_planen(trocken=True, jetzt=JETZT, seed=7)
    g = {z["konto_id"]: z for z in e.get("geplant") or []}
    a = {z["konto_id"]: z.get("grund") for z in e.get("ausgelassen") or []}
    return g, a


print("1) ohne Funded-Flex-Werte (heute)")
g0, a0 = lauf(copy.deepcopy(FIRMEN0))
check(a0.get(EMIN["id"]) == "Flex-Konto — plant der Funded-CFD-Planer noch nicht" and EMIN["id"] not in g0,
      f"Emin …8250 → ausgelassen wie bisher ({a0.get(EMIN['id'])})")

print("2) mit Flex-Variante der Firma (regel.flex wie BG2)")
f2 = copy.deepcopy(FIRMEN0)
next(f for f in f2 if "fundingpips" in (f.get("namen") or []))["flex"] = copy.deepcopy(FLEX)
f2_fp = next(f for f in f2 if "fundingpips" in (f.get("namen") or []))
f2_fp["ohne_namen"] = sorted(set(f2_fp["ohne_namen"] + ["demo"]))
g2, a2 = lauf(f2)
check(EMIN["id"] in g2, f"Emin …8250 (Max DD 12.000) → „flex“ sperrt nicht mehr, Konto geplant ({'geplant' if EMIN['id'] in g2 else a2.get(EMIN['id'])})")
rfx = app.fcp_regel_konto(f2_fp, EMIN)
check(rfx.get("flex_konto") is True and app.fcp_konto_ziel_boden(rfx, 100000, 1, EMIN["name"]) is not None
      and app.fcp_konto_ziel_boden(f2_fp, 100000, 1, EMIN["name"]) is None,
      "Radar (fcp_konto_ziel_boden): mit greifender Flex-Variante Ziel/Boden wie im Planer, ohne Variante weiter None (Review EM1)")
z = g2.get(EMIN["id"]) or {}
check(not z or z.get("striking") is True, f"Striking-Werte gelten obendrauf ({z.get('striking')})")
check(a2.get(FLEX10["id"]) == "Flex-Konto — plant der Funded-CFD-Planer noch nicht", "Flex im Namen, aber 10 % DD → Variante greift nicht → gesperrt wie bisher")
check(a2.get(DEMO["id"]) == "Name enthält „demo“ — nicht planen (Einstellung der Firma)", f"anderes Sperrwort bleibt ({a2.get(DEMO['id'])})")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ alle Prüfungen grün")
