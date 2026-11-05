#!/usr/bin/env python3
"""Selbsttest GT2 (05.11.2026, Finn — Blue Guardian 100k …7770 Funded CFD): Gewinntage bei Funded CFD
(1) Zählung = SUMME aller abgeschlossenen Trades des Kontos je Berlin-Tag ≥ Mindest-$ (auch Hand-Trades) — mit den echten Zahlen von …7770 am 05.11.:
    447,83 + 50,00 (Hand, gebucht) = 497,83 → 0/3; mit der Balance-Differenz 86,88 → 534,71 → 1/3;
(2) Korrektur von Hand accounts.fcp_gewinntage {zyklus, korrektur} — gilt nur im eigenen Zyklus, nie unter 0, in Planer/Radar/Konto-Seite verdrahtet;
(3) Account-Modal-Feld + SQL-Datei (Code-Stellen). Regel Blue Guardian 100k Funded wie live (gewinntage anzahl 3, min 500). Ohne Netz, IDs Platzhalter.
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_fcp_gewinntage_korrektur.py"""
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


K = "00000000-0000-4000-8000-0000000b7770"
GT = {"anzahl": 3, "min": 500, "tp": [550, 650]}
T1 = {"master_account_id": K, "status": "completed", "started_at": "2026-11-05T07:24:34+00:00", "ended_at": "2026-11-05T07:30:14+00:00", "master_pl": 447.83}
T2 = {"master_account_id": K, "status": "completed", "started_at": "2026-11-05T13:26:51+00:00", "ended_at": "2026-11-05T13:45:11+00:00", "master_pl": 50.00}
SEIT = "2026-11-05"
IST = app.fcp_gewinntage_ist

print("1) Zählung je Berlin-Tag-Summe (auch Hand-Trades)")
ok(IST(GT, K, [T1], SEIT) == (0, 3), "nur der Gewinntag-Trade 447,83 → 0/3")
ok(IST(GT, K, [T1, T2], SEIT) == (0, 3), "447,83 + Hand 50,00 (wie gebucht) = 497,83 < 500 → 0/3 — darum stand …7770 bei 0/3")
ok(IST(GT, K, [T1, dict(T2, master_pl=86.88)], SEIT) == (1, 3), "447,83 + Hand 86,88 (Balance 100.447,83 → 100.534,71) = 534,71 → 1/3 (SQL 2a)")
ok(IST(GT, K, [dict(T1, master_pl=300.0), dict(T2, master_pl=250.0)], SEIT) == (1, 3), "zwei Trades unter 500, zusammen 550 → zählt (Summe, nicht je Trade)")
_spaet = dict(T2, ended_at="2026-11-05T23:30:00+00:00", master_pl=86.88)   # 00:30 Berlin am 06.11. → anderer Tag
ok(IST(GT, K, [T1, _spaet], SEIT) == (0, 3), "Trade-Ende nach Mitternacht Berlin zählt zum nächsten Tag")
ok(IST(GT, K, [T1, dict(T2, status="planned", master_pl=86.88)], SEIT) == (0, 3), "nur completed/review zählen")

print("2) Korrektur von Hand (accounts.fcp_gewinntage)")
KR = app.fcp_gt_korrektur
ok(KR({"zyklus": 1, "korrektur": 1}, 1) == 1 and KR({"zyklus": 1, "korrektur": 1}, 2) == 0, "gilt nur im eigenen Zyklus (nach dem Payout → 0)")
ok(KR(None, 1) == 0 and KR({"zyklus": "x"}, 1) == 0 and KR("kaputt", 1) == 0 and KR({"zyklus": 1}, 1) == 0, "leer/kaputt → 0")
ok(KR({"zyklus": 1, "korrektur": -2}, 1) == -2 and KR({"zyklus": 1, "korrektur": 500}, 1) == 99, "negativ erlaubt, begrenzt")
ok(IST(GT, K, [T1, T2], SEIT, KR({"zyklus": 1, "korrektur": 1}, 1)) == (1, 3), "…7770: 0 gezählt + 1 von Hand → 1/3 (SQL 2b / Modal)")
ok(IST(GT, K, [T1, dict(T2, master_pl=86.88)], SEIT, -5) == (0, 3), "nie unter 0")
ok(IST(GT, K, [], SEIT, 3) == (3, 3), "Korrektur bis zum Soll → Phase B (Planer plant Ziel-Trade)")
_sa = app._sb_all
app._sb_all = lambda t, p: [{"id": K, "fcp_gewinntage": {"zyklus": 1, "korrektur": 1}}, {"id": "x", "fcp_gewinntage": None}] if t == "accounts" else []
ok(app.fcp_gt_korr_laden([K, "x"]) == {K: {"zyklus": 1, "korrektur": 1}}, "fcp_gt_korr_laden: nur Zeilen mit Wert")
def _kaputt(t, p):
    raise RuntimeError("column accounts.fcp_gewinntage does not exist")
app._sb_all = _kaputt
ok(app.fcp_gt_korr_laden([K]) == {}, "Spalte fehlt → {} (Zählung wie bisher)")
app._sb_all = _sa

print("3) Radar/Abhak (zw_funded_cfd) mit Korrektur — Ziel erst, wenn die Tage voll sind")
BG = {"an": True, "name": "Blue Guardian", "namen": ["blueguardian"],
      "je_groesse": {"100000": {"dd": 8000, "sl": [1250, 1600], "lots": [1, 1.75], "ziel": [1000, 2000], "hedge_eur": 1000, "gewinntage": GT}}}
KONTO = {"id": K, "user_id": "u1", "name": "100k 00000000 → Funded", "firm": "Blue Guardian", "starting_balance": 100000, "created_at": "2026-11-05T02:08:51+00:00"}
ZU = {"korr": None}


def sb_all(t, p):
    if t == "accounts" and "fcp_gewinntage" in str(p.get("select") or ""):
        return [{"id": K, "fcp_gewinntage": ZU["korr"]}]
    if t == "accounts":
        return [dict(KONTO)]
    if t == "trade_plans":
        return [dict(T1), dict(T2)]
    return []


app._fcp_regeln_laden = lambda: {"firmen": [BG]}
app._sb_all = sb_all
app.fd_unt_reg = lambda reg, art, uid, ktx, streng: reg
app._zw["ziele"].clear(); app._zw["boeden"].clear()
app.zw_funded_cfd()
ok(K not in app._zw["ziele"] and app._zw["boeden"].get(K) == 92000.0, "0/3: kein Radar-Ziel (kein „Waiting for Payout“), Boden 92.000")
ZU["korr"] = {"zyklus": 1, "korrektur": 3}
app._zw["ziele"].clear(); app._zw["boeden"].clear()
app.zw_funded_cfd()
ok(app._zw["ziele"].get(K) == 101000.0, "mit +3 von Hand (3/3): Radar-Ziel 101.000 wieder da")
ZU["korr"] = {"zyklus": 2, "korrektur": 3}
app._zw["ziele"].clear(); app.zw_funded_cfd()
ok(K not in app._zw["ziele"], "Korrektur aus einem anderen Zyklus wirkt nicht")
app._sb_all = _sa

print("4) Verdrahtung + Frontend + SQL")
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
sql = open(os.path.join(WURZEL, "sql", "2026-11-05_fcp_gewinntage_korrektur.sql"), encoding="utf-8").read()
ok("fcp_gt_korrektur(gt_korr.get(aid), payout_n.get(aid, 0) + 1)" in src and "gt_korr = fcp_gt_korr_laden(ids)" in src, "Planer: Korrektur des laufenden Zyklus")
ok("fcp_gt_korrektur(gt_korr.get(aid), n.get(aid, 0) + 1)" in src, "Radar/Abhak: dieselbe Korrektur")
ok('out["gewinntage"] = {"ist":' in src and "gti = fcp_gewinntage_ist(gt, aid, plaene, seit, _gk)" in src, "Konto-Seite: Stand mit Korrektur + auto/korrektur/zyklus fürs Modal")
ok('id="ac-gt-feld"' in html and "async function accGtFeldSetzen(acc)" in html and "accGtFeldSetzen(editAccount)" in html
   and "fcp_gewinntage: korrektur ? { zyklus: f.zyklus, korrektur" in html, "Account-Modal: Feld „Gewinntage (dieser Payout-Zyklus)“, Setzen speichert Wert − Zählung")
ok("add column if not exists fcp_gewinntage jsonb" in sql and "set master_pl = 86.88" in sql and "and master_pl = 50.00 and pl_quelle = 'hand'" in sql,
   "SQL: Spalte + …7770 (2a) Balance-Differenz mit Guard, (2b) Alternative")

ok('ctx["fcp_gt"] = fcp_gt_korr_laden([kid]).get(kid)' in src and 'fcp_gt_korrektur(ctx.get("fcp_gt"), zyklus)' in src
   and "fcp_gt_korr_laden([aid])" not in src, "Fremd-Review: kz_rechnen bleibt rein rechnend (Korrektur über ctx aus der Route)")
ok(".eq('id', id).select('id')" in html and "if(!data || !data.length) throw new Error('Konto nicht geändert" in html, "Fremd-Review: RLS blockt → Fehler statt „✓“")
ok("if(_accGt.id === id) await accGtFeldSetzen" in html and "const f = await accGtHolen(id).catch(() => null) || g" in html,
   "Fremd-Review: nach dem Speichern nur dasselbe Konto neu laden; Korrektur gegen die frische Zählung")
ok("\n-- update public.trade_plans\n--    set master_pl = 86.88" in sql and "zählt der Tag doppelt" in sql, "Fremd-Review: SQL (2a) auskommentiert, Hinweis gegen doppeltes Zählen")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER:\n  - " + "\n  - ".join(FEHLER))
sys.exit(1 if FEHLER else 0)
