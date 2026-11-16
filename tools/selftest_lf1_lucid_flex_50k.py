#!/usr/bin/env python3
"""Selbsttest LF1 (Master 16.11.2026, Finn): Lucid Flex 50k Funded als Profil im Funded-Planer Futures.
Kern: (1) DIFF-TEST gegen main vor LF1 (BASIS 1728de57) — bestehende Profile (Tradeify/Lucid 150k Pump, Apex, FTMO Futures) rechnen bitgleich,
Balance-Leser und WD-Linie unverändert außer Lucid 50k; (2) das 50k-Profil: EIN Pump-Trade aufs Ziel (pump2_pct 0, nie Trade 2), Ziel 6.000–8.000 fest je
Konto × Zyklus, 1–2 NQ, SL 1.000–1.100 (unter DLL 1.200 − Puffer), Hedge 300 € je 2.000 $ Risiko; (3) Schalter je Größe (je_groesse.<G>.an): Lucid an,
150k aus, 50k an — Planer, Balance-Leser und Abhak-Ziel lassen 150k aus; (4) WD-Linie Lucid je Größe: 50k 150 $, 150k 250 $.
Ohne Netz, Profil-Werte wie sql/2026-11-16_lucid_flex_50k.sql. Aufruf: python3 tools/selftest_lf1_lucid_flex_50k.py"""
import copy
import importlib.util
import json
import os
import random
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []
BASIS_VOR_LF1 = "1728de57"   # main-Commit vor LF1 (fest, nie ein Branch-Stand)


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


# Profile in der Form wie live (funded_plan_regeln id 1, gelesen 16.11.2026)
JG150 = {"dd": 4500, "t1_sl": [2600, 2700], "t1_tp": [4000, 8000], "ein_sl": [2600, 2700], "t1_bis": "16:00", "t1_von": "03:00", "t2_bis": "18:30", "daily_usd": 2700,
         "hedge_eur": 750, "pump2_pct": 30, "alarm_offen": "18:00", "sl_kein_pct": 50, "ziel_gewinn": [13000, 19000], "t1_kontrakte": {"2": 0.5, "3": 0.5},
         "t2_kontrakte": {"3": 1}, "t2_sl_be_pct": 50, "ein_kontrakte": {"3": 1}, "hedge_auf_usd": 4500, "sl_hinter_liq": False, "t2_abstand_min": [2, 5],
         "ziel_toleranz_pct": 10, "t2_min_fenster_min": 10}
TRADEIFY = {"an": False, "name": "Tradeify", "namen": ["tradeify"], "symbol": "NQ", "lock_usd": 100, "tp_modus": "pump2",
            "je_groesse": {"150000": dict(JG150, daily_usd=None, ein_sl=[4500, 4700], t1_sl=[4500, 4700], sl_hinter_liq=True, hedge_eur=850)}}
LUCID_ALT = {"an": False, "name": "Lucid Trading", "namen": ["lucidtrading", "lucid"], "symbol": "NQ", "lock_usd": 100, "tp_modus": "pump2",
             "je_groesse": {"150000": dict(JG150)}}
JG50 = {"an": True, "dd": 2000, "daily_usd": 1200, "ziel_gewinn": [6000, 8000], "ziel_toleranz_pct": 10, "pump2_pct": 0, "ein_kontrakte": {"1": 0.5, "2": 0.5},
        "ein_sl": [1000, 1100], "sl_kein_pct": 0, "sl_hinter_liq": False, "t1_von": "03:00", "t1_bis": "16:00", "hedge_eur": 300, "hedge_auf_usd": 2000}
LUCID = copy.deepcopy(LUCID_ALT)
LUCID["an"] = True
LUCID["je_groesse"]["150000"]["an"] = False
LUCID["je_groesse"]["50000"] = copy.deepcopy(JG50)
# LF1b: FundedNext Futures Flex 50k (wie sql/2026-11-16_fnf_flex_50k.sql)
JGF = {"an": True, "dd": 1500, "ziel_gewinn": [6000, 8000], "ziel_toleranz_pct": 10, "pump2_pct": 0, "ein_kontrakte": {"1": 0.5, "2": 0.5}, "ein_sl": [1300, 1400],
       "sl_kein_pct": 0, "sl_hinter_liq": False, "t1_von": "03:00", "t1_bis": "16:00", "hedge_eur": 350, "hedge_auf_usd": 1500}
FNF = {"an": True, "name": "FundedNext Futures", "namen": ["fundednextfutures"], "symbol": "NQ", "lock_usd": 100, "tp_modus": "pump2", "je_groesse": {"50000": copy.deepcopy(JGF)}}
APEX = {"an": True, "name": "Apex Trader", "namen": ["apextrader", "apex"], "lock_usd": 100, "je_groesse": {"100000": {"dd": 3000, "ziel_gewinn": [3000, 3500], "max_trade": 3000,
        "kosten_eur": 300, "kontrakte": {"2": 0.5, "3": 0.5}}, "150000": {"dd": 5000, "ziel_gewinn": [5000, 5500], "max_trade": 5000, "kosten_eur": 400, "kontrakte": {"3": 1}}}}
FTMO = {"an": True, "name": "FTMO Futures", "namen": ["ftmofutures"], "lock_usd": 0, "tp_modus": "rest",
        "je_groesse": {"50000": {"dd": 2000, "daily_usd": 1000, "ziel_gewinn": [4000, 4500], "sl": [750, 850], "hedge_eur": 300, "kontrakte": {"2": 0.5, "3": 0.5}}}}


def konto(firma, g, typ="funded", kid="k1"):
    return {"id": kid, "name": f"{g // 1000}k X-{kid} → Funded", "firm": firma, "account_type": typ, "starting_balance": g, "user_id": "u1"}


print(f"— 1) Diff-Test gegen main vor LF1 ({BASIS_VOR_LF1}) —")
alt = None
try:
    src = subprocess.run(["git", "-C", WURZEL, "show", BASIS_VOR_LF1 + ":app.py"], capture_output=True, text=True, timeout=60, check=True).stdout
    d = tempfile.mkdtemp(prefix="lf1_alt_")
    with open(os.path.join(d, "app_alt_lf1.py"), "w", encoding="utf-8") as fh:
        fh.write(src)
    sp = importlib.util.spec_from_file_location("app_alt_lf1", os.path.join(d, "app_alt_lf1.py"))
    alt = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(alt)
except Exception as e:  # noqa: BLE001
    print(f"   {BASIS_VOR_LF1} nicht ladbar: {type(e).__name__}: {e}")
ok(alt is not None and not hasattr(alt, "fdp_groesse_an"), f"main vor LF1 ({BASIS_VOR_LF1}) geladen als Vergleich")
if alt is not None:
    n = abw = rabw = 0
    for regel in (TRADEIFY, LUCID_ALT):
        jg = regel["je_groesse"]["150000"]
        for bal in (150000, 151200, 149000, 160500, 165000):
            for zyk in (1, 2):
                for tag in ("2026-11-17", "2026-11-18", "2026-11-19"):
                    for kid in ("k1", "k2", "k3"):
                        for tv in (0.0, 900.0):
                            ra, rb = random.Random(f"{kid}{tag}"), random.Random(f"{kid}{tag}")
                            a = app.fdp_pump_konto(regel, jg, bal, max(bal, 150000), 150000, 150000, kid, zyk, tag, ra, sppl=0.85, tag_verlust=tv)
                            b = alt.fdp_pump_konto(regel, jg, bal, max(bal, 150000), 150000, 150000, kid, zyk, tag, rb, sppl=0.85, tag_verlust=tv)
                            n += 1
                            abw += a != b
                            rabw += ra.random() != rb.random()
    for regel, g in ((APEX, 100000), (APEX, 150000)):
        jg = regel["je_groesse"][str(g)]
        for bal in (g - 1500, g, g + 1200, g + 3000):
            for seed in range(6):
                ra, rb = random.Random(seed), random.Random(seed)
                a = app.fdp_konto_rechnen(regel, jg, None, bal, max(bal, g), 300.0, g, g, ra, konto_id="k1", zyklus=1)
                b = alt.fdp_konto_rechnen(regel, jg, None, bal, max(bal, g), 300.0, g, g, rb, konto_id="k1", zyklus=1)
                n += 1
                abw += a != b
                rabw += ra.random() != rb.random()
    ok(n > 400 and abw == 0 and rabw == 0, f"{n} Fälle (Tradeify/Lucid 150k Pump, Apex normal): Ergebnis und Zufalls-Verbrauch wie vor LF1 ({abw}/{rabw})")
    alle_konten = [konto(f, g, t, f"{f[:3]}{g}{t}") for f in ("Tradeify", "Lucid Trading", "Apex Trader", "FTMO Futures", "FundingPips")
                   for g in (50000, 100000, 150000) for t in ("funded", "funded_cfd")]
    firmen_alt = [TRADEIFY, LUCID_ALT, APEX, FTMO]
    fa = app.ap_bal_gruppe_funded_filter(alle_konten, firmen_alt, [{"an": True, "name": "FundingPips", "namen": ["fundingpips"]}])
    fb = alt.ap_bal_gruppe_funded_filter(alle_konten, firmen_alt, [{"an": True, "name": "FundingPips", "namen": ["fundingpips"]}])
    ok(fa == fb, f"Balance-Leser der Gruppen: mit den alten Regeln (ohne „an“ je Größe) dieselben Konten ({len(fa)})")
    wd_abw = []
    for f in ("Tradeify", "Lucid Trading", "Apex Trader", "Topstep", "FTMO Futures", "FundedNext Futures", "Tradeify CFD"):
        for nm in ("50k A", "100k A", "150k A", "A ohne Größe"):
            for pl in (149.0, 151.0, 249.0, 251.0, 299.0, 351.0):
                k = {"firm": f, "name": nm, "account_type": "winning_days"}
                if ("lucid" in f.lower() or "fundednext futures" in f.lower()) and nm.startswith("50k"):
                    continue
                if (app.wd_min_gewinn(k), app._wd_good_day(k, pl)) != (alt.wd_min_gewinn(k), alt._wd_good_day(k, pl)):
                    wd_abw.append((f, nm, pl))
    ok(not wd_abw, f"WD-Linie aller Firmen/Größen außer Lucid 50k und FNF Futures 50k unverändert ({wd_abw[:3]})")

print("— 2) Lucid 50k: EIN Pump-Trade aufs Ziel —")
fehl, ziele, kts = [], {}, set()
for kid in ("a1", "a2", "a3", "a4", "a5"):
    for zyk in (1, 2):
        for tag in ("2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"):
            r = app.fdp_pump_konto(LUCID, JG50, 50000.0, 50000.0, 50000.0, 50000, kid, zyk, tag, random.Random(f"{kid}{zyk}{tag}"), sppl=0.85)
            zg = r["pump"]["ziel_gewinn"]
            ziele.setdefault((kid, zyk), set()).add(zg)
            kts.add(r.get("kontrakte"))
            q = round(300 / 2000 * r["sl"], 2) if r.get("sl") else None
            if not (r["aktion"] == "planen" and r["pump"]["weg"] == "ein" and r.get("kette") is None and 6000 <= zg <= 8000 and r["tp"] == zg
                    and 1000 <= r["sl"] <= 1100 and r["kontrakte"] in (1, 2) and r.get("dll") == 1200 and r["liq"] == 48000):
                fehl.append((kid, zyk, tag, r.get("aktion"), r.get("grund"), r.get("tp"), r.get("sl"), r.get("kontrakte"), r.get("liq")))
ok(not fehl, f"40 Pump-Tage: immer EIN Trade (kein Trade 2), TP = ganzes Ziel 6.000–8.000, SL 1.000–1.100, 1–2 NQ, Liq 48.000, DLL 1.200 ({fehl[:2]})")
ok(all(len(v) == 1 for v in ziele.values()) and len({min(v) for v in ziele.values()}) > 3, "Ziel fest je Konto × Zyklus (an allen Tagen gleich), über Konten gestreut")
ok(kts == {1, 2}, f"Kontrakte 1 und 2 NQ kommen beide vor ({sorted(kts)})")
r = app.fdp_pump_konto(LUCID, JG50, 50000.0, 50000.0, 50000.0, 50000, "a1", 1, "2026-11-17", random.Random(1), sppl=0.85)
rk = app.fdp_pump_trade1(JG50, "ein", 50000.0, 50000.0, 48000.0, 50000.0 + r["pump"]["ziel_gewinn"], random.Random(1))
ok(rk["hedge_eur"] == round(300 / 2000 * rk["risiko"], 2) and rk["risiko"] == rk["sl"], f"Hedge 300 € je 2.000 $ Risiko: SL {rk['sl']:g} $ → {rk['hedge_eur']:g} €")
r = app.fdp_pump_konto(LUCID, JG50, 50000.0, 50000.0, 50000.0, 50000, "a1", 1, "2026-11-17", random.Random(3), sppl=0.85, tag_verlust=300.0)
ok(r["aktion"] == "planen" and r["sl"] <= 1200 - 300 - 100, f"heute schon −300 $: SL ≤ DLL-Rest − Puffer (800) → {r.get('sl')}")
r = app.fdp_pump_konto(LUCID, JG50, 55500.0, 55500.0, 50000.0, 50000, "a1", 1, "2026-11-17", random.Random(3), sppl=0.85)
ok(r["aktion"] == "ziel", f"Gewinn 5.500 ≥ Untergrenze 6.000 × 0,9 (Toleranz 10 %) → Ziel erreicht → Winning Days ({r.get('grund')})")
r = app.fdp_pump_konto(LUCID, JG50, 49100.0, 50000.0, 50000.0, 50000, "a1", 1, "2026-11-17", random.Random(3), sppl=0.85)
ok(r["aktion"] == "planen" and r["sl"] <= 49100 - 48000 - 50, f"Balance 49.100 (Liq 48.000): SL ≤ Abstand − 50 → {r.get('sl')}")

print("— 2b) LF1b FundedNext Futures Flex 50k: EIN Pump-Trade, ohne Daily Loss —")
fehl, ziele = [], {}
for kid in ("f1", "f2", "f3", "f4"):
    for tag in ("2026-11-17", "2026-11-18", "2026-11-19"):
        r = app.fdp_pump_konto(FNF, JGF, 50000.0, 50000.0, 50000.0, 50000, kid, 1, tag, random.Random(f"{kid}{tag}"), sppl=0.85)
        ziele.setdefault(kid, set()).add(r["pump"]["ziel_gewinn"])
        if not (r["aktion"] == "planen" and r["pump"]["weg"] == "ein" and r.get("kette") is None and 6000 <= r["tp"] <= 8000 and 1300 <= r["sl"] <= 1400
                and r["kontrakte"] in (1, 2) and r["liq"] == 48500 and r.get("dll") is None):
            fehl.append((kid, tag, r.get("aktion"), r.get("grund"), r.get("sl"), r.get("liq"), r.get("dll")))
ok(not fehl and all(len(v) == 1 for v in ziele.values()), f"12 Pump-Tage: EIN Trade, Ziel 6–8k fest je Konto, SL 1.300–1.400, 1–2 NQ, Liq 48.500 (MLL 1.500), kein DLL ({fehl[:2]})")
rk = app.fdp_pump_trade1(JGF, "ein", 50000.0, 50000.0, 48500.0, 57000.0, random.Random(2))
ok(rk["hedge_eur"] == round(350 / 1500 * rk["sl"], 2), f"Hedge 350 € je 1.500 $ Risiko: SL {rk['sl']:g} $ → {rk['hedge_eur']:g} €")
r = app.fdp_pump_konto(FNF, JGF, 49700.0, 50000.0, 50000.0, 50000, "f1", 1, "2026-11-17", random.Random(5), sppl=0.85)
ok(r["aktion"] == "planen" and r["sl"] <= 49700 - 48500 - 50, f"Balance 49.700 (Liq 48.500): SL höchstens Abstand − 50 = 1.150 → {r.get('sl')}")
liq_lock = app.fdp_liq(50000, 1500, 51700, 51700, 100.0)[0]
ok(liq_lock == 50100, f"MLL-Lock: ab Höchststand 51.600 fest bei 50.100 (Größe + 100) → {liq_lock}")
r = app.fdp_pump_konto(dict(LUCID, je_groesse=dict(LUCID["je_groesse"], **{"50000": dict(JG50, hedge_eur=300)})), dict(JG50, hedge_eur=300), 50000.0, 50000.0, 50000.0,
                       50000, "a1", 1, "2026-11-17", random.Random(1), sppl=0.85)
ok(r["aktion"] == "planen", "Lucid mit Hedge 300 € (Finn-Nachtrag) plant")

print("— 3) Schalter je Größe —")
ok(app.fdp_groesse_an(LUCID, konto("Lucid Trading", 50000)) is True and app.fdp_groesse_an(LUCID, konto("Lucid Trading", 150000)) is False,
   "Lucid: 50k an, 150k aus")
ok(all(app.fdp_groesse_an(r_, konto(r_["name"], g)) for r_ in (TRADEIFY, LUCID_ALT, APEX, FTMO) for g in (50000, 100000, 150000)) and app.fdp_groesse_an(None, {}),
   "Profile ohne „an“ je Größe: immer an (nur der Firmen-Schalter zählt)")
ok(app.fdp_groesse_an(FNF, konto("FundedNext Futures", 50000)) and not app.fdp_groesse_an(FNF, konto("FundedNext Futures", 100000))
   and not app.fdp_groesse_an(FNF, konto("FundedNext Futures", 150000)) and not app.fdp_groesse_an(LUCID, konto("Lucid Trading", 100000)),
   "LF1b: Firma mit Schaltern je Größe — Größen ohne Werte (FNF 100k/150k, Lucid 100k) sind aus, nicht „keine Werte“ und nicht gelesen")
alle = [konto("Lucid Trading", 50000, kid="l50"), konto("Lucid Trading", 150000, kid="l150"), konto("Tradeify", 150000, kid="t150"),
        konto("Lucid Trading", 150000, "funded_cfd", "lcfd")]
f2 = [a["id"] for a in app.ap_bal_gruppe_funded_filter(alle, [LUCID, dict(TRADEIFY, an=True)], [{"an": True, "name": "Lucid Trading", "namen": ["lucidtrading", "lucid"]}])]
ok(f2 == ["l50", "t150", "lcfd"], f"Balance-Leser (Gruppe): Lucid 150k Futures aus, 50k und Tradeify an, Funded CFD unberührt ({f2})")
f3 = [a["id"] for a in app.ap_bal_gruppe_funded_filter(alle, lambda a: [LUCID], lambda a: [])]
ok(f3 == ["l50"], f"Balance-Leser je Unternehmen (UNT4-Weg): nur Lucid 50k ({f3})")
reg = {"updated_at": "x", "firmen": [copy.deepcopy(LUCID), copy.deepcopy(TRADEIFY)]}
p, f_ = app.fdp_regeln_aendern(reg, {"updated_at": "x", "firma": {"name": "Lucid Trading", "je_groesse": {"50000": {"an": False}, "150000": {"an": True}}}})
lu = [x for x in (p or {}).get("firmen", []) if x.get("name") == "Lucid Trading"]
ok(lu and lu[0]["je_groesse"]["50000"]["an"] is False and lu[0]["je_groesse"]["150000"]["an"] is True and reg["firmen"][0]["je_groesse"]["50000"]["an"] is True,
   f"Einstellung: Schalter je Größe änderbar (50k aus, 150k an) — {f_}")
ok(app.fdp_regeln_aendern(reg, {"updated_at": "x", "firma": {"name": "Tradeify", "je_groesse": {"150000": {"an": False}}}})[0] is None,
   "Größe ohne Schalter (Tradeify 150k): nicht änderbar (nur per SQL anlegen)")
ok(app.fdp_regeln_aendern(reg, {"updated_at": "x", "firma": {"name": "Lucid Trading", "je_groesse": {"50000": {"an": "ja"}}}})[0] is None, "an nur true/false")

print("— 4) WD-Linie Lucid je Größe —")
w = lambda n, t="winning_days": {"firm": "Lucid Trading", "name": n, "account_type": t}   # noqa: E731
ok(app.wd_min_gewinn(w("50k L1 → WD")) == 150.0 and app.wd_min_gewinn(w("150k L1 → WD")) == 250.0 and app.wd_min_gewinn(w("L1 ohne Größe")) == 250.0
   and app.wd_min_gewinn(w("100k L1")) == 250.0, "wd_min_gewinn: 50k 150 $, 150k/100k/unbekannt 250 $")
wf = lambda n: {"firm": "FundedNext Futures", "name": n, "account_type": "winning_days"}   # noqa: E731
ok(app.wd_min_gewinn(wf("50k F1")) == 200.0 and app.wd_min_gewinn(wf("100k F1")) == 250.0 and app.wd_min_gewinn(wf("F1")) == 250.0
   and app._wd_good_day(wf("50k F1"), 210) is True and app._wd_good_day(wf("50k F1"), 190) is False, "LF1b: FNF Futures 50k Benchmark Day ab 200 $, sonst 250 $")
ok(app._wd_good_day(w("50k L1"), 160) is True and app._wd_good_day(w("150k L1"), 160) is False and app._wd_good_day(w("50k L1"), 150) is False,
   "Good Day: 50k ab > 150 $, 150k erst > 250 $")
ok(app.wd_min_gewinn(dict(w("50k L1"), goal_min_profit=200)) == 200.0, "goal_min_profit am Konto gilt weiter vor der Firma")

print("— 5) Verdrahtung —")
SRC = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
fp = SRC[SRC.index("def fdp_planen("):SRC.index("def fdp_planen(") + 12000]
ok("and fdp_groesse_an(ap_regel_finden(an_von(a.get(\"user_id\")), a.get(\"firm\")), a)]" in fp and "else FDP_GRUND_GROESSE_AUS" in fp,
   "fdp_planen: Größe aus = nicht geplant, in „Heute nicht drin“ mit eigenem Grund")
ok("if ap_regel_finden(an, a.get(\"firm\")) and (globals().get(\"fdp_groesse_an\") or (lambda _r, _a: True))(ap_regel_finden(an, a.get(\"firm\")), a)]" in SRC, "Balance-Takt HT: Größe aus → keine Lesung")
ok("if _fr and fdp_groesse_an(_fr, a):" in SRC, "Abhaken (AP6 Ziel → WD): Größe aus wie Firma aus")
ok('_FDP_GR_BOOL = ("sl_hinter_liq", "an")' in SRC, "Einstellung: an je Größe als Schalter")
sq = open(os.path.join(WURZEL, "sql", "2026-11-16_lucid_flex_50k.sql"), encoding="utf-8").read()
ok("'{je_groesse,150000,an}', 'false'::jsonb" in sq and '"pump2_pct": 0' in sq and '"hedge_eur": 300' in sq and "where not exists" in sq
   and "insert into public.liq_regeln (firma," in sq, "SQL: Firma an, 150k aus, 50k-Profil, liq_regeln 50k idempotent (id = Identity, nicht mitgegeben)")
_i = sq.index("'{\n          \"an\"")
sql_jg = json.loads(sq[_i + 1:sq.index("}'::jsonb", _i) + 1])
sqf = open(os.path.join(WURZEL, "sql", "2026-11-16_fnf_flex_50k.sql"), encoding="utf-8").read()
_j = sqf.index("'{\n          \"an\"")
ok(json.loads(sqf[_j + 1:sqf.index("}'::jsonb", _j) + 1]) == JGF and '"tp_modus": "pump2"' in sqf and '"lock_usd": 100' in sqf,
   "LF1b: Profil im Test = Profil in sql/2026-11-16_fnf_flex_50k.sql (pump2, Lock 100)")
ok(sql_jg == JG50, "Profil im Test = Profil in der SQL-Datei")

print("— 6) Frontend (prophos.html, JavaScriptCore) —")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()


def fn(name):
    i = html.index(f"  function {name}(")
    return html[i:html.index("\n  }\n", i) + 4]


i0 = html.index("  const TC_GOOD_DAY_MIN")
js = "const istTradeifyCfd = f => /tradeify/i.test(String(f || '')) && /cfd/i.test(String(f || ''));\nconst tpVpApex100 = a => /100k/i.test(String(a && a.name || ''));\n" \
     + html[i0:html.index("\n", i0)] + "\n" + fn("tcGoodDayGrenze") + fn("zielWdMin") + """
const L = (f, n) => ({ firm: f, name: n });
JSON.stringify({ tc: [tcGoodDayGrenze(L('Lucid Trading', '50k A')), tcGoodDayGrenze(L('Lucid Trading', '150k A')), tcGoodDayGrenze(L('Lucid Trading', 'A')),
  tcGoodDayGrenze(L('Apex Trader', '100k A')), tcGoodDayGrenze(L('Apex Trader', '150k A')), tcGoodDayGrenze(L('Tradeify', '50k A')), tcGoodDayGrenze(L('Topstep', '50k A'))],
  zw: [zielWdMin(L('Lucid Trading', '50k A')), zielWdMin(L('Lucid Trading', '150k A')), zielWdMin(L('Tradeify', '50k A')), zielWdMin(L('Apex Trader', '100k A')), zielWdMin(L('FTMO Futures', '50k A')),
       zielWdMin(L('FundedNext Futures', '50k A')), zielWdMin(L('FundedNext Futures', '100k A'))],
  fnf: [tcGoodDayGrenze(L('FundedNext Futures', '50k A')), tcGoodDayGrenze(L('FundedNext Futures', '150k A'))] });
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
    fh.write(js)
try:
    aus = subprocess.run(["osascript", "-l", "JavaScript", fh.name], capture_output=True, text=True, timeout=30)
    jr = json.loads(aus.stdout.strip() or "{}")
    if not jr:
        print(aus.stderr[:600])
finally:
    os.unlink(fh.name)
ok(jr.get("tc") == [150, 250, 250, 300, 350, 250, 150], f"tcGoodDayGrenze: Lucid 50k 150 / 150k 250 / ohne Größe 250, Apex/Tradeify/Topstep unverändert ({jr.get('tc')})")
ok(jr.get("zw") == [150, 250, 250, 300, 200, 200, 250], f"zielWdMin: Lucid 50k 150, FNF 50k 200, Rest unverändert ({jr.get('zw')})")
ok(jr.get("fnf") == [200, 250], f"tcGoodDayGrenze: FNF Futures 50k 200 / 150k 250 ({jr.get('fnf')})")
ok("an: ['Diese Größe im Planer'" in html and "titel !== 'Größe im Planer' || ks.some(k => w[k] !== undefined)" in html,
   "Einstellung: Schalter „Diese Größe im Planer“ nur, wo er per SQL steht")

print()
print("alle Tests bestanden" if not FEHLER else f"{len(FEHLER)} ROT")
sys.exit(1 if FEHLER else 0)
