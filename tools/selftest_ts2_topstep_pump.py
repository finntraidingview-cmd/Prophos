#!/usr/bin/env python3
"""Selbsttest TS2 „Topstep im Funded-Planer Futures 1:1 wie Tradeify“ (Finn 11.11.2026 20:35: „Topstep kommt genau wie bei Tradeify, ganz genau alles gleich“;
Befund TS1 side-session-notes 2026-11-11_TS1_topstep_wie_tradeify_bauplan.md).

Prüft die REIN RECHNENDEN Teile aus app.py ohne Netz/DB (Muster selftest_ff2_pump.py) und die Einbau-Anker:
  · Weg: Topstep → tsv2 (Nova, Puls in TopstepX), alle anderen tvv2 wie bisher; Trade 2 auf dem Weg von Trade 1; 18:00-Alarm auch für tsv2
  · Symbol NQ + Frontmonat (TopstepX-Contract wie die Hand-Novas)
  · Balance 0-basiert (TopstepX Express): Planer rechnet absolut = Kontogröße + TopstepX-Stand, Liq = Größe + belegte MLL + 100 $ (TX2)
  · Trade 2 kommt: genaue Lesung von Trade 1 auch 0-basiert (beide Lesungen relativ), positive 0-basierte Stände nie als absolute Balance
Platzhalter-Konten, keine echten Kennungen.

Aufruf:  python3 tools/selftest_ts2_topstep_pump.py"""
import hashlib
import os
import random
import re
import sys
from datetime import datetime, timezone, timedelta

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.environ.get("SELFTEST_APP") or os.path.join(W, "app.py"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


try:
    from zoneinfo import ZoneInfo
except ImportError:   # pragma: no cover
    ZoneInfo = None
ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "random": random, "hashlib": hashlib, "ZoneInfo": ZoneInfo}


def quelle(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^\S)", app, re.S | re.M)
    if not m:
        raise LookupError(name)
    return m.group(0)


def lade(name, tiefe=0):
    src = quelle(name)
    for _ in range(40):
        try:
            exec(src, ns)
            return
        except NameError as e:   # Standardwerte (Konstanten) zur Definitionszeit
            lade(str(e).split("'")[1], tiefe + 1)


def ruf(fn, *a, **k):
    for _ in range(80):
        try:
            if fn not in ns:
                lade(fn)
            return ns[fn](*a, **k)
        except NameError as e:
            lade(str(e).split("'")[1])
    raise RuntimeError(fn)


SCHNITTSTELLE = ("fdp_route", "fdp_express_basis", "fdp_express_liq", "fdp_express_vor_t1", "fdp_pump_echt", "fdp_pump_konto")
fehlt = [n for n in SCHNITTSTELLE if not re.search(r"^def " + n + r"\(", app, re.M)]
if fehlt:
    for n in fehlt:
        print(f"✗ fehlt: {n} (app.py) — TS2 noch nicht gebaut")
    sys.exit(1)
ns["_cme_handelstag"] = lambda st: str(st)[:10]

# ── Weg je Firma
check(ruf("fdp_route", "Topstep") == "tsv2" and ruf("fdp_route", "topstep ") == "tsv2", "Topstep → tsv2 (Nova in TopstepX)")
check(all(ruf("fdp_route", f) == "tvv2" for f in ("Tradeify", "Lucid Trading", "Apex Trader", "FTMO Futures", None)), "Tradeify/Lucid/Apex/FTMO Futures → tvv2 wie bisher")

# ── Basis (Topstep Express 0-basiert)
TS = {"id": "aaaaaaaa-0000-0000-0000-00000000ts01", "name": "150k EXPRESS-V2-000000-00000001 → Funded", "firm": "Topstep", "account_type": "funded",
      "external_id": "EXPRESS-V2-000000-00000001", "max_drawdown": None}
TR_A = {"id": "aaaaaaaa-0000-0000-0000-00000000tr01", "name": "150k TDFY0001 → Funded", "firm": "Tradeify", "account_type": "funded"}
check(ruf("fdp_express_basis", TS, 150000.0) == 150000.0, "Topstep Express 150k → Basis 150.000 (TopstepX-Stand + Größe = absolute Balance)")
check(ruf("fdp_express_basis", TR_A, 150000.0) == 0.0, "Tradeify → Basis 0 (nichts verschoben)")
check(ruf("fdp_express_basis", TS, None) == 0.0, "Größe unbekannt → Basis 0")

# ── Liq aus der belegten MLL (TX2) + 100 $
L1 = {"master_account_id": TS["id"], "mll_start": -4500.0, "started_at": "2026-11-10T08:00:00Z"}
liq, txt = ruf("fdp_express_liq", TS, [L1], 0.0, 150000.0, 4500)
check(liq == 145600.0, f"MLL-Lesung −4.500 → Liq 150.000 − 4.500 + 100 = 145.600 ({liq}, {txt})")
liq, txt = ruf("fdp_express_liq", TS, [L1, {"master_account_id": TS["id"], "bal_end": 2000.0, "ended_at": "2026-11-10T09:00:00Z"}], 2000.0, 150000.0, 4500)
check(liq == 147600.0, f"Schluss-Balance +2.000 nach der Lesung zieht die MLL auf −2.500 → Liq 147.600 ({liq})")
liq, txt = ruf("fdp_express_liq", TS, [L1, {"master_account_id": TS["id"], "bal_end": 16000.0, "ended_at": "2026-11-10T09:00:00Z"}], 16000.0, 150000.0, 4500)
check(liq == 150100.0, f"XFA-MLL lockt bei 0 → Liq 150.100 ({liq})")
liq, txt = ruf("fdp_express_liq", TS, [], 0.0, 150000.0, 4500, frisch_ok=True)
check(liq == 145600.0 and "frisch" in txt, f"frisches Express-Konto (kein Plan, Stand 0) → Start-MLL −4.500 laut Regel, Liq 145.600 ({liq}, {txt})")
liq, txt = ruf("fdp_express_liq", TS, [{"master_account_id": TS["id"], "bal_end": 500.0, "ended_at": "2026-11-10T09:00:00Z"}], 500.0, 150000.0, 4500)
check(liq is None and txt, f"Trades ohne MLL-Lesung → unbekannt, nie raten ({txt})")
liq, txt = ruf("fdp_express_liq", TS, [], -50.0, 150000.0, 4500, frisch_ok=True)
check(liq is None, "ohne Plan, aber Stand ≠ 0 (Hand-Trades) → unbekannt")
liq, txt = ruf("fdp_express_liq", TS, [], 0.0, 150000.0, 4500)
check(liq is None, "leerer Verlauf ohne frisch_ok (Lesefehler = stilles []) → unbekannt, nie −DD (Prüfer TS2)")
check(ruf("fdp_bal_start_abs", 0.0, True, 150000.0, 150000.0) == 150000.0 and ruf("fdp_bal_start_abs", 151000.0, False, 150000.0, 150000.0) == 151000.0,
      "Start-Balance früherer Pläne: 0-basiert → + Größe, absolut gelesen → unverändert")
check(ruf("fdp_bal_start_abs", 2000.0, None, 150000.0, 150000.0) == 152000.0 and ruf("fdp_bal_start_abs", 150500.0, None, 150000.0, 150000.0) == 150500.0,
      "Basis unbekannt: kleiner Wert = 0-basiert, Wert ≈ Größe = absolut")
check(ruf("fdp_bal_start_abs", 5.0, True, 0.0, 150000.0) == 5.0 and ruf("fdp_bal_start_abs", None, True, 150000.0, 150000.0) is None, "Basis 0 / leer → unverändert")
liq, txt = ruf("fdp_express_liq", TS, [{"master_account_id": "anderes-konto", "mll_start": -1000.0, "started_at": "2026-11-10T08:00:00Z"}], 0.0, 150000.0, 4500, frisch_ok=True)
check(liq == 145600.0, "Lesungen anderer Konten zählen nicht")

# ── Genaue Lesung von Trade 1 (0-basiert)
def plan(route="tsv2", vs=0.0, ne=16000.0, rel_s=True, rel_e=True, q="puls", bq=None):
    fin = {"quelle": q, "balance_end": ne, "balance_relativ": rel_e}
    if bq:
        fin["balance_quelle"] = bq
    return {"route": route, "orbit_v3": True, "mt5_baseline": {"tv": {"balance_start": vs, "balance_relativ": rel_s}, "final": fin}}


check(ruf("fdp_pump_echt", plan(), 150000.0) == (150000.0, 166000.0), "Express: Start 0, Ende +16.000 (Puls) → (150.000, 166.000)")
check(ruf("fdp_pump_echt", plan(q="auge"), 150000.0) == (150000.0, 166000.0), "Express: Endlesung aus dem TopstepX-Auge zählt (wie ap_echte_balancen)")
check(ruf("fdp_pump_echt", plan(vs=12468.44, ne=28468.44), 150000.0) == (162468.44, 178468.44),
      "Express im Plus: positiver 0-basierter Stand wird verschoben, nie als absolute Balance genommen")
check(ruf("fdp_pump_echt", plan(vs=-2981.34, ne=3018.66), 150000.0) == (147018.66, 153018.66), "Express im Minus: negativer Start zählt (0-basiert echte Stände)")
check(ruf("fdp_pump_echt", plan(rel_e=False), 150000.0) is None, "gemischte Basis (Start relativ, Ende absolut) → keine Lesung")
check(ruf("fdp_pump_echt", plan(rel_s=None), 150000.0) is None, "Basis des Starts unbekannt → keine Lesung")
check(ruf("fdp_pump_echt", plan(bq="folgetrade"), 150000.0) is None, "Folgetrade-Wert zählt nie")
check(ruf("fdp_pump_echt", plan(q="hand"), 150000.0) is None, "Hand-/Demo-Ende zählt nie")
check(ruf("fdp_pump_echt", plan(route="tvv2"), 150000.0) is None, "Basis > 0 nur auf tsv2")
check(ruf("fdp_pump_echt", plan(route="tvv2", vs=150000.0, ne=156000.0, rel_s=False, rel_e=False)) == (150000.0, 156000.0),
      "Tradeify (tvv2, Basis 0): Puls-Endlesung wie bisher")

# ── Pump-Konto mit fester Liq (Tradeify-Werte 1:1)
TRW = {"ziel_gewinn": [13000, 19000], "dd": 4500, "hedge_eur": 850, "hedge_auf_usd": 4500, "pump2_pct": 30,
       "ein_kontrakte": {"3": 1}, "ein_sl": [4500, 4700], "t1_von": "03:00", "t1_bis": "15:00", "t1_tp": [4000, 8000], "t1_kontrakte": {"2": 0.5, "3": 0.5},
       "t1_sl": [4500, 4700], "sl_kein_pct": 50, "sl_hinter_liq": True, "t2_bis": "18:20", "t2_abstand_min": [2, 5], "t2_min_fenster_min": 10,
       "t2_kontrakte": {"3": 1}, "t2_sl_be_pct": 50}
REG = {"name": "Topstep", "namen": ["topstep"], "tp_modus": "pump2", "lock_usd": 100, "je_groesse": {"150000": TRW}}
liq_f = ruf("fdp_express_liq", TS, [], 0.0, 150000.0, 4500, frisch_ok=True)
r = ruf("fdp_pump_konto", REG, TRW, 150000.0, None, 150000.0, 150000.0, TS["id"], 1, "2026-11-12", random.Random(3), liq_fest=liq_f)
check(r.get("aktion") == "planen" and r["liq"] == 145600.0 and 163000 <= r["ziel"] <= 169000, f"frisches XFA: Pump plant, Liq 145.600, Ziel 163–169k absolut ({r.get('aktion')}, {r.get('liq')}, {r.get('ziel')})")
check(r.get("tp") and r["tp"] <= r["ziel"] - 150000.0 and r.get("kontrakte") in (2, 3), f"TP ≤ Rest bis Ziel, 2–3 NQ ({r.get('tp')}, {r.get('kontrakte')})")
check(abs(r["master_risk"] - 4400.0) < 0.01, f"Risiko-Abstand = Balance − Liq = 4.400 $ (Hedge-Basis wie Tradeify) ({r.get('master_risk')})")
r2 = ruf("fdp_pump_konto", REG, TRW, 150000.0, None, 150000.0, 150000.0, TS["id"], 1, "2026-11-12", random.Random(3), liq_fest=(None, "noch keine MLL-Lesung"))
check(r2.get("aktion") == "aus" and "Liquidation unbekannt" in r2.get("grund", ""), f"MLL unbekannt → kein Plan, genauer Grund ({r2.get('grund')})")
r3 = ruf("fdp_pump_konto", REG, TRW, 145500.0, None, 150000.0, 150000.0, TS["id"], 1, "2026-11-12", random.Random(3), liq_fest=(145600.0, "MLL"))
check(r3.get("aktion") == "aus" and "geblowt" in r3.get("grund", ""), "Balance unter der Liq → aus (geblowt?)")
zr = ruf("fdp_pump_konto", REG, TRW, 150000.0 + 19500.0, None, 150000.0, 150000.0, TS["id"], 1, "2026-11-12", random.Random(3), liq_fest=(150100.0, "MLL"))
check(zr.get("aktion") == "ziel", f"Stand über dem Niveau → Ziel erreicht → Winning Days ({zr.get('aktion')})")

# ── Trade 2 kommt (aus der 0-basierten Lesung), Liq nach Tagesend-Logik wie Tradeify
A2 = dict(TRW, t2_sl_be_pct=0)
bs, be = ruf("fdp_pump_echt", plan(vs=0.0, ne=6000.0), 150000.0)
T1 = {"master_account_id": TS["id"], "mll_start": -4500.0, "started_at": "2026-11-12T07:00:00Z", "ended_at": "2026-11-12T08:00:00Z", "bal_end": 6000.0}
vor = ruf("fdp_express_vor_t1", [L1, T1], "2026-11-12T07:00:00Z")
check(len(vor) == 2 and vor[1]["bal_end"] is None and vor[1]["mll_start"] == -4500.0, "Verlauf vor Trade 1: Schluss von Trade 1 fällt weg, seine MLL-Lesung bleibt")
liq2, _t = ruf("fdp_express_liq", TS, vor, bs - 150000.0, 150000.0, 4500)
check(liq2 == 145600.0, f"Liq für Trade 2 = MLL des Tagesstarts (EOD, zieht erst am Tagesschluss nach) → 145.600 ({liq2})")
w, grund = ruf("fdp_pump_trade2", A2, {"tp": 6000}, bs, be, liq2, 166000.0, random.Random(5))
check(grund is None and w and w["tp"] == 10000 and w["kontrakte"] == 3, f"Trade 1 +6.000 am TP → Trade 2 TP 10.000, 3 NQ ({w}, {grund})")
check(w and abs(w["risiko"] - 10400.0) < 0.01, f"Trade 2 ohne SL: Risiko bis zur Liq 10.400 $ wie Tradeify (Abstand nach Tagesend-Logik) ({w and w['risiko']})")
check(ruf("fdp_express_vor_t1", [L1, T1], None) == [L1, T1], "Start von Trade 1 unbekannt → Verlauf unverändert (vorsichtig)")
wb, gb = ruf("fdp_pump_trade2", A2, {"tp": 6000}, bs, 145620.0, liq2, 166000.0, random.Random(5))
check(wb is None and "geblowt" in gb, "Trade 1 bis an die Liq → kein Trade 2")

# ── 40-%-Consistency (Topstep RTP): nur Hinweis, blockt nie
h = ruf("fdp_topstep_cons_hinweis", {}, 16000.0, "Topstep")
check(h.startswith("Hinweis Topstep-Consistency") and "100 %" in h and "40.000" in h, f"Pump 16.000 im frischen Zyklus → Hinweis 100 % > 40 %, Payout ab ≈ 40.000 ({h})")
check(ruf("fdp_topstep_cons_hinweis", {"2026-11-03": 9000.0, "2026-11-04": 9000.0, "2026-11-05": 9000.0}, 6000.0, "Topstep") == "",
      "bester Tag 9.000 von 33.000 (27 %) → kein Hinweis")
check(ruf("fdp_topstep_cons_hinweis", {}, 16000.0, "Tradeify") == "", "Tradeify → nie ein Hinweis")
check(ruf("fdp_topstep_cons_hinweis", {}, 0.0, "Topstep") == "" and ruf("fdp_topstep_cons_hinweis", {"t": -5000.0}, 3000.0, "Topstep") == "",
      "kein Gewinn bzw. Netto ≤ 0 → kein Hinweis")

# ── SQL (T5): Topstep = Tradeify-Einstellung, an bleibt false, idempotent
sq = open(os.path.join(W, "sql", "2026-11-11_ts2_topstep_pump.sql"), encoding="utf-8").read()
code = "\n".join(z for z in sq.splitlines() if not z.strip().startswith("--"))
check("t->'namen' ? 'tradeify' and t->>'tp_modus' = 'pump2'" in code and "'an', false" in code, "SQL: Werte von Tradeify (pump2), an = false")
check("not (f ? 'tp_modus')" in code and code.count("where r.id = 1") == 1, "SQL: nur solange Topstep noch kein Modell hat (überschreibt Finns Änderungen nie)")

# ── Einbau-Anker
planen = quelle("fdp_planen")
tick = quelle("fdp_pump_tick")
offen = quelle("fdp_pump_offen_tick")
check('"route": fdp_route(a.get("firm"))' in planen and '"route": "tvv2"' not in planen, "fdp_planen: Weg nach Firma, kein festes tvv2 mehr")
check('"master_symbol": "NQ" + frontcode' in planen, "fdp_planen: Symbol NQ + Frontmonat (TopstepX-Contract wie die Hand-Novas)")
check('liq_fest=fdp_express_liq(a, verlauf, balance - basis, basis, (jg or {}).get("dd"), frisch_ok=not pl)' in planen and "fdp_express_basis(a, g)" in planen, "fdp_planen: Express-Adapter (Basis + Liq aus der MLL)")
check('zeile["balance"] = round(zeile["balance"] + _basis, 2)' in planen and 'fdp_bal_start_abs(p.get("bal_start"), p.get("bal_rel"), _basis, g)' in planen
      and "bal_rel:mt5_baseline->tv->balance_relativ" in planen,
      "fdp_planen: Balance und Start-Balancen früherer Pläne absolut (Zyklus-Start nach Payout)")
check("nur im Pump-Modell" in planen, "fdp_planen: Topstep Express ohne Pump-Modell → nie geplant")
check('p.get("route") if p.get("route") in ("tvv2", "tsv2") else fdp_route(a.get("firm"))' in tick and '"route": "tvv2"' not in tick, "fdp_pump_tick: Trade 2 auf dem Weg von Trade 1")
check("fdp_pump_echt(p, basis)" in tick and "fdp_express_liq(a, fdp_express_vor_t1(verlauf, p.get(\"started_at\")), bs - basis, basis, dd)" in tick,
      "fdp_pump_tick: 0-basierte Lesung + Liq aus der MLL nach Tagesend-Logik")
check('"route": "in.(tvv2,tsv2)"' in offen, "fdp_pump_offen_tick: 18:00-Alarm auch für Topstep")
check('fdp_topstep_cons_hinweis(fdp_tage(pl, ab), (r_p.get("ziel") or 0) - balance, a.get("firm"))' in planen and 'notiz += " · " + r["hinweis"]' in planen
      and 'aktion="aus"' not in planen.split("fdp_topstep_cons_hinweis(")[1][:400], "fdp_planen: Consistency-Hinweis in die Plan-Notiz, kein Block")
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
check("function tpIstFundedPump(p)" in HTML and "!tpIstWdPlan(p) && !tpIstFundedPump(p)) return 'Topstep V2 — startet nur von Hand'" in HTML
      and HTML.count("!tpIstWdPlan(p) && !tpIstFundedPump(p))") == 2, "PC-Tab: Nova-Pump (auch Ein-Trade-Weg ohne kette) startet zur Zeit wie die Kette (Prüfer TS2)")
check('bal_quelle != "TSX"' in quelle("kz_fdp_abhak") and 'kz_fdp_abhak(a, ctx["fdp"], bal, plaene, ctx.get("bal_quelle"))' in app, "Abhak-Popup: alter TSX-Sync (absolut) wird nicht verschoben")
check("fdp_express_basis(a, g)" in quelle("kz_fdp_abhak"), "kz_fdp_abhak (Abhak-Popup): Topstep Express absolut wie der Planer")

print()
if fehler:
    print(f"ROT: {len(fehler)} Prüfung(en) fehlgeschlagen")
    sys.exit(1)
print("GRÜN: TS2 Topstep im Pump-Modell (Route, Symbol, Balance 0-basiert, Trade 2)")
