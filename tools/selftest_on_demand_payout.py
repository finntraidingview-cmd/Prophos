#!/usr/bin/env python3
"""Selbsttest OD1 (05.11.2026, Finn über den Master — Marc FundedNext 100k …7821 + …7823 „→ Funded · On Demand“): Add-on On Demand
(1) kein Payout-Datum, keine Tage: Frontend payoutAbInfo/payoutAbBadgeHtml („Payout bei Ziel · On Demand“), finNextPayoutVorschlag leer, fcfdPayoutAb ohne
    14/21 Tage, Konto-Seite „Payout ab“ ohne Datum, SQL-Datei (Bestand + Trigger);
(2) On Demand + Refund im ERSTEN Zyklus: Ziel = On-Demand-Ziel statt Refund-Ziel — Radar/Abhak-Popup (zw_funded_cfd → fcp_konto_ziel_boden on_demand)
    wie der Planer (fcp_on_demand_anwenden). Regel = live funded_cfd_plan_regeln (FundedNext, gelesen 05.11.2026: on_demand.ziel_je_100k 2.088–2.250,
    erster_payout.ziel 50–150, 100k ziel 1.500–1.850, dd 10.000). Ohne Netz, Konto-IDs Platzhalter.
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_on_demand_payout.py"""
import copy
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("  ✓ " if b else "  ✗ ") + t)
    if not b:
        FEHLER.append(t)


FN = {"an": True, "name": "FundedNext", "namen": ["fundednext"], "on_demand": {"ziel_je_100k": [2088, 2250]},
      "je_groesse": {"50000": {"dd": 5000, "sl": [875, 1225], "lots": [1, 1.75], "ziel": [1500, 1850], "sl_1pct": [300, 400], "hedge_eur": 750},
                     "100000": {"dd": 10000, "sl": [1750, 2450], "lots": [1, 1.75], "ziel": [1500, 1850], "sl_1pct": [670, 780], "hedge_eur": 1500}},
      "erster_payout": {"ziel": [50, 150], "hedge_eur_je_dd": 0.5}, "tp_deckel_plus": 1000}
FT = {"an": True, "name": "FTMO", "namen": ["ftmo"], "je_groesse": {"100000": {"dd": 10000, "sl": [1500, 2000], "lots": [1.0, 1.5], "ziel": [1500, 2500], "hedge_eur": 1200}},
      "erster_payout": {"ziel": [50, 100], "hedge_eur_je_dd": 0.5}}
ZB = app.fcp_konto_ziel_boden

print("1) fcp_konto_ziel_boden — On Demand dominiert im 1. Zyklus")
ok(ZB(FN, 100000, 1) == (100050.0, 90000.0), f"ohne On Demand, Zyklus 1: Refund-Ziel 100.050 (wie bisher) → {ZB(FN, 100000, 1)}")
ok(ZB(FN, 100000, 1, on_demand=True) == (102088.0, 90000.0), f"On Demand, Zyklus 1: On-Demand-Ziel 102.088 statt Refund → {ZB(FN, 100000, 1, on_demand=True)}")
ok(ZB(FN, 100000, 2, on_demand=True) == (102088.0, 90000.0) and ZB(FN, 100000, 2) == (101500.0, 90000.0), "Zyklus 2: On Demand 102.088, normal 101.500 (wie bisher)")
ok(ZB(FN, 50000, 1, on_demand=True) == (51044.0, 45000.0), f"50k skaliert: 2.088 × 0,5 = 1.044 → {ZB(FN, 50000, 1, on_demand=True)}")
ok(ZB(FT, 100000, 1, on_demand=True) == ZB(FT, 100000, 1) == (100050.0, 90000.0), "Firma ohne On-Demand-Regel (FTMO): normale Regel, Refund bleibt")
_jg, _rk = app.fcp_on_demand_anwenden(FN, app.fcp_je_groesse(FN, 100000), 100000)[1], app.fcp_on_demand_anwenden(FN, app.fcp_je_groesse(FN, 100000), 100000)[0]
ok(_jg["ziel"] == [2088.0, 2250.0] and _rk["erster_payout"] is False, "dieselbe Rechnung wie der Planer (fcp_on_demand_anwenden: Ziel 2.088–2.250, kein Refund)")

print("2) zw_funded_cfd (Radar-Ziel + Abhak-Vorschlag) mit nachgebauter DB")
K_OD, K_NORM = "00000000-0000-4000-8000-0000000d0001", "00000000-0000-4000-8000-0000000d0002"
KONTEN = [{"id": K_OD, "user_id": "u1", "name": "100k 00000001 → Funded · On Demand", "firm": "FundedNext", "starting_balance": 100000, "created_at": "2026-11-02T15:00:00+00:00"},
          {"id": K_NORM, "user_id": "u1", "name": "100k 00000002 → Funded", "firm": "FundedNext", "starting_balance": 100000, "created_at": "2026-11-02T15:00:00+00:00"}]
ZUST = {"od_fehler": False}


class _Antwort:
    text = "column accounts.on_demand does not exist"


def sb_all(t, p):
    if t == "accounts":
        if "on_demand" in str(p.get("select") or ""):
            if ZUST["od_fehler"]:
                import requests
                raise requests.exceptions.HTTPError("400", response=_Antwort())
            return [dict(k, on_demand=(k["id"] == K_OD)) for k in KONTEN]
        return copy.deepcopy(KONTEN)
    return []


app._fcp_regeln_laden = lambda: {"firmen": [FN, FT]}
app._sb_all = sb_all
app.fd_unt_reg = lambda reg, art, uid, ktx, streng: reg
app._zw["ziele"].clear(); app._zw["boeden"].clear()
app.zw_funded_cfd()
ok(app._zw["ziele"].get(K_OD) == 102088.0 and app._zw["ziele"].get(K_NORM) == 100050.0,
   f"Zyklus 1: On-Demand-Konto Ziel 102.088 (kein „Waiting for Payout“ nach +117 $), normales Konto 100.050 → {app._zw['ziele'].get(K_OD)} / {app._zw['ziele'].get(K_NORM)}")
ok(app._zw["boeden"].get(K_OD) == 90000.0, "Boden unverändert 90.000")
ZUST["od_fehler"] = True
app._zw["ziele"].clear(); app._zw["boeden"].clear()
app.zw_funded_cfd()
ok(app._zw["ziele"].get(K_OD) == 100050.0, "Spalte on_demand nicht lesbar → wie bisher (Refund-Ziel), kein Absturz")

print("3) Frontend + Konto-Seite + SQL (Code-Stellen)")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
sql = open(os.path.join(WURZEL, "sql", "2026-11-05_on_demand_ohne_payout_termin.sql"), encoding="utf-8").read()
ok("if(a.onDemand === true){" in html and "{ stufe: 'od', tage: null }" in html and "💸 Payout bei Ziel · On Demand" in html,
   "payoutAbInfo: On Demand → kein „Payout-Datum fehlt“/„in X T“, Chip „Payout bei Ziel · On Demand“ (heute/vergangen = „Payout jetzt“)")
ok("if(acc && acc.type === 'funded_cfd' && acc.onDemand === true) return ''" in html, "finNextPayoutVorschlag: On Demand → kein „heute + 14“")
ok("if(r.on_demand === true){" in html and "On Demand: kein Payout-Datum" in html, "fcfdPayoutAb (Waiting-Tabelle): keine 14/21 Tage bei On Demand")
ok("...(r.on_demand === undefined ? {} : { onDemand: r.on_demand === true })" in html and 'r["on_demand"] = str(r["id"]) in od_an' in src,
   "Admin → Alle Accounts: fremde Konten kennen das Add-on (Chip, Payout-Chip)")
ok("On Demand — sobald Ziel + Consistency erfüllt (kein Datum, keine Tage)" in src, "Konto-Seite: „Payout ab“ ohne Datum bei On Demand")
ok("on_demand=aid in od_ids" in src, "zw_funded_cfd übergibt on_demand")
ok("and not coalesce(new.on_demand, false)" in sql and "create trigger accounts_on_demand_termin" in sql and "create trigger pending_payouts_on_demand_termin" in sql
   and "set payout_ready_at = null" in sql, "SQL: Bestand leeren, Anlege-Trigger ohne Termin, On Demand an → künftiger Termin weg, Anfrage → Termin weg")

print("4) Nachbesserung nach Fremd-Review (Stopp 1/2, Hinweis 3–5)")
_sel0 = app.sb_select
_SEL = {"od": [{"id": "k1", "account_type": "funded_cfd", "on_demand": True}], "norm": [{"id": "k2", "account_type": "funded_cfd", "on_demand": False}],
        "fut": [{"id": "k3", "account_type": "funded", "on_demand": True}]}
def _sel(t, p):
    if t == "accounts":
        if p.get("id") == "eq.kaputt":
            raise RuntimeError("weg")
        return _SEL.get(str(p.get("id"))[3:], [])
    return []
app.sb_select = _sel
ok(app._konto_on_demand("od") is True and app._konto_on_demand("norm") is False and app._konto_on_demand("fut") is False
   and app._konto_on_demand("kaputt") is False and app._konto_on_demand("") is False, "_konto_on_demand: nur Funded CFD mit on_demand, Lesefehler → False (wie bisher)")
app.sb_select = _sel0
ok(src.count("if naechster and _konto_on_demand(aid):") == 2, "Anfragen UND Erhalten (Admin-Routen): bei On Demand kein nächster Termin — auch mit vorbelegtem „+ 14“")
ok("if(konto && konto.on_demand === true){ $('adm-receive-next').value = ''" in html, "Admin → Payout erhalten: bei On Demand nichts vorbelegt")
ok("(admData?.accounts || []).find(x => String(x.id) === String(r.account_id || r.id)) || {}).on_demand === true" in html,
   "Admin → Payouts „Anfragen“: On Demand fremder Konten aus admData.accounts → kein „+ 14“")
ok("if(a.type === 'funded_cfd' && a.onDemand === true && tage > 0) return null" in html, "payoutReadyInfo: künftiges Datum gilt bei On Demand nirgends (Finanzen, Filter)")
ok("or waiting_payout_since is null" in sql, "SQL (1): Waiting-for-Payout-Konten behalten ihr vergangenes Datum")
_FNg = dict(FN, je_groesse={"100000": dict(FN["je_groesse"]["100000"], gewinntage={"anzahl": 3, "min": 500, "tp": [550, 650]})})
_FTg = dict(FT, je_groesse={"100000": dict(FT["je_groesse"]["100000"], gewinntage={"anzahl": 3, "min": 500, "tp": [550, 650]})})
_j = app.fcp_on_demand_anwenden(_FNg, app.fcp_je_groesse(_FNg, 100000), 100000)
ok(_j and "gewinntage" not in _j[1] and app.fcp_on_demand_anwenden(_FTg, app.fcp_je_groesse(_FTg, 100000), 100000) is None,
   "Gewinntage: On Demand mit Regel ohne Tage; Firma ohne On-Demand-Regel → None → normale Gewinntage (zw_funded_cfd _gt_jg wie der Planer)")
ok("def _gt_jg(a):" in src and "_o = fcp_on_demand_anwenden(_r, _j, _g) if str(a[\"id\"]) in od_ids else None" in src, "zw_funded_cfd: Gewinntage-Ausnahme nur mit On-Demand-Regel")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER:\n  - " + "\n  - ".join(FEHLER))
sys.exit(1 if FEHLER else 0)
