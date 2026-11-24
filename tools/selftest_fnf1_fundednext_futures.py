#!/usr/bin/env python3
"""Selbsttest FNF1 (Finn 25.11.2026): FundedNext Futures 150k Challenge (Flex) im Challenge-Planer für HT, letzter Trade mit Fusion-Gegenhedge wie
Tradeify/Lucid. Screenshot: Ziel 8.000 $, Max Loss EOD 4.000 $, kein Daily Loss, Consistency 40 %. Geprüft mit echtem app.py-Code (ohne Netz):
1) Final-Weg: tfh_firma/tfh_param/tfh_plan_dabei (nur HT, nie Orbit Prio 2, FundedNext CFD nie, Tradeify/Lucid unverändert), Suchmuster master_firm;
2) Consistency 40 % gegen den Weg Erst-Trade → Rest-Trades bis Ziel (kein Tag > 40 % des Gewinns am Ende, auch der Deckel-+100-Weg), Required profit,
   ap_cons_regel (FNF 150k wie Lucid, Emins 50k ohne Lesen); 3) Frontend-Schalter und SQL-Datei.
Aufruf: python3 tools/selftest_fnf1_fundednext_futures.py"""
import fnmatch
import itertools
import os
import sys

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


# Regel FundedNext Futures wie in auto_plan_regeln id 1 (Stand 25.11.2026), nach FNF1-SQL planen true / kauf 245
FNF = {"boden": "nachziehend", "namen": ["fundednextfutures"], "route": "tvv2", "dd_usd": 4000, "planen": True, "symbol": "NQ", "groessen": [50000, 150000],
       "kauf_eur": {"50000": 74, "150000": 245}, "ziel_pct": {"challenge": 5.333333333333334}, "lock_bei_start": True,
       "phasen": {"challenge": {"sl": None, "tp": [3050, 3150], "menge": [1, 2], "dd_usd": 4000, "tp_max": 3200, "ziel_pct": 5.333333333333334,
                                "menge_schritt": 1, "puffer_je_menge": {"1": [15, 25], "2": [15, 25]}}},   # FNF1-Nachtrag (Finn): immer 1–2 NQ, nie 3
       "je_groesse": {"50000": {"dd_usd": 1500, "phasen": {"challenge": {"sl": None, "tp": [900, 980], "menge": [1, 1], "dd_usd": 1500, "tp_max": 1000,
                                                                            "ziel_pct": 5, "menge_schritt": 1, "puffer_je_menge": {"1": [15, 25]}}},
                                "ziel_pct": {"challenge": 5}}}}
HT, EMIN = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"

print("1) Final-Weg (tfh)")
par = app.tfh_param({"tradeify_final_hedge": {"an": True, "firmen": ["tradeify", "lucid", "fundednextfutures"]}})
check(par["firmen"] == ("tradeify", "fundednextfutures", "lucid"), f"tfh_param nimmt fundednextfutures auf ({par['firmen']})")
check(app.tfh_param({"tradeify_final_hedge": {"an": True, "firmen": ["tradeify", "lucid"]}})["firmen"] == ("tradeify", "lucid")
      and app.tfh_param({"tradeify_final_hedge": {"an": True}})["firmen"] == ("tradeify",), "ohne FNF im Feld: wie bisher (bitgleich)")
F = par["firmen"]
check(app.tfh_firma("FundedNext Futures", F) == "fundednextfutures" and app.tfh_firma("Funded Next Futures", F) == "fundednextfutures"
      and app.tfh_firma("FundedNextFutres", F) is None, "tfh_firma: „FundedNext Futures“ (auch mit Leerzeichen) → Schlüssel")
check(app.tfh_firma("FundedNext", F) is None and app.tfh_firma("FundedNext Futures", ("tradeify", "lucid")) is None,
      "FundedNext CFD nie; FNF nur, wenn im Feld firmen")
check(app.tfh_firma("Tradeify", F) == "tradeify" and app.tfh_firma("Tradeify CFD", F) is None and app.tfh_firma("Lucid Trading", F) == "lucid",
      "Tradeify / Tradeify CFD / Lucid unverändert")
p_ht = {"master_firm": "FundedNext Futures", "user_id": HT}
check(app.tfh_plan_dabei(p_ht, F, set(), [FNF], {}) is True, "HT-Plan FNF 150k gehört zum Final-Weg")
check(app.tfh_plan_dabei({"master_firm": "FundedNext Futures", "user_id": EMIN}, F, {EMIN}, [FNF], {}) is False,
      "Emins FNF (Verwalter-Gruppe) nie — bleibt bei Orbit Prio 2")
check(app.tfh_plan_dabei(p_ht, F, set(), [dict(FNF, modell="orbit_prio2")], {}) is False, "Modell Orbit Prio 2 → nicht dieser Weg (ein Hedge je Plan)")
check(app.tfh_name({"master_firm": "FundedNext Futures"}) == "FundedNext Futures" and app.tfh_name({"master_firm": "Tradeify"}) == "Tradeify",
      "Anzeigename „FundedNext Futures“, Tradeify gleich")
mus = {k: app.TFH_FIRMA_ILIKE.get(k, f"*{k}*") for k in F}
ilike = lambda wert, m: fnmatch.fnmatchcase(wert.lower(), m.lower())   # PostgREST ilike mit * = beliebig
check(ilike("FundedNext Futures", mus["fundednextfutures"]) and ilike("Funded Next Futures", mus["fundednextfutures"])
      and not ilike("FundedNext", mus["fundednextfutures"]) and mus["tradeify"] == "*tradeify*" and mus["lucid"] == "*lucid*",
      f"Suchmuster master_firm: FNF trifft (mit Leerzeichen), FundedNext CFD nicht, Tradeify/Lucid wie bisher ({mus['fundednextfutures']})")
SRC = open(os.path.join(WURZEL, "app" + ".py"), encoding="utf-8").read()
check("master_firm.ilike.{TFH_FIRMA_ILIKE.get(k, '*' + k + '*')}" in SRC and '{"master_firm": "ilike.*tradeify*"} if par["firmen"] == ("tradeify",)' in SRC,
      "tfh_tick liest mit dem Suchmuster je Firma; nur Tradeify = Abfrage wie bisher")
check('tf_f.get("firma") in TFH_FIRMEN_ERLAUBT' in SRC, "Schalter-Endpunkt nimmt fundednextfutures (TFH_FIRMEN_ERLAUBT)")

print("2) Consistency 40 % gegen den Weg (Erst-Trade, Rest-Trades bis Ziel)")
G = 150000.0
ZIEL = G * (1 + 5.333333333333334 / 100)
check(abs(ZIEL - 158000.0) < 0.01, f"Ziel 8.000 $ ({ZIEL - G:.2f})")
GEB = app.AP_GEBUEHR_JE_KT_FUT
werte = (0.0, 0.25, 0.5, 0.75, 0.999)
pfade = schlecht = max_tag_q = 0
max_tag = 0.0
n_trades = set()
mengen = set()
beisp = []
for ut, um, up in itertools.product(werte, werte, werte):
    for ueber in (0.0, 30.0, 54.0):   # Überschuss über dem TP am Fill: 0, typisch, größter gemessener FNF-Wert (45 Tage, 38 Trades: max +54,3 $)
        bal, tage = G, []
        for _i in range(6):
            regel = dict(FNF)
            if bal >= G + (ZIEL - G) * 0.5:    # ap_cons_regel ab halbem Ziel (LC1-Weg, FNF1): _cons_p 40 reist mit
                regel["_cons_p"] = 40.0
            w, grund = app.ap_konto_rechnen(regel, "challenge", bal, {"tp": ut, "sl": 0.5, "menge": um, "puffer": up})
            if w is None:
                break
            mengen.add(float(w["menge"]))
            g = float(w["tp"]) - GEB * float(w["menge"]) + (ueber if str(w.get("stufe", "")).startswith("Etappe") else 0.0)
            tage.append(g)
            bal += g
        pfade += 1
        n_trades.add(len(tage))
        gewinn = bal - G
        mt = max(tage) if tage else 0.0
        max_tag = max(max_tag, mt)
        if bal < ZIEL or mt > 0.4 * gewinn + 0.005:
            schlecht += 1
            if len(beisp) < 3:
                beisp.append((ut, um, up, ueber, [round(x) for x in tage], round(gewinn)))
check(schlecht == 0, f"{pfade} Wege: alle am Ziel, kein Tag über 40 % des Gewinns am Ende ({beisp})")
check(n_trades == {3}, f"immer genau 3 Trades: 2 Etappen + letzter Trade ({sorted(n_trades)})")
check(mengen == {1.0, 2.0}, f"Kontrakte nur 1 oder 2 NQ, nie 3 — alle Trades inkl. letztem ({sorted(mengen)})")
check(max_tag <= 3204.0, f"größter Tag {max_tag:.0f} $ (Etappe ≤ 3.150 + Überschuss 54; 40 % von 8.000 = 3.200, von ≥ 8.010 ≥ 3.204)")
# Deckel-+100-Weg: Rest knapp über dem Deckel — ohne Consistency TP bis 3.300 (= 41 % von ~8.040), mit _cons_p 40 Etappe, Rest bleibt ≥ 100
bal = ZIEL - 3250.0
w_alt, _ = app.ap_konto_rechnen(dict(FNF), "challenge", bal, {"tp": 0.5, "sl": 0.5, "menge": 0.999, "puffer": 0.5})
w_neu, _ = app.ap_konto_rechnen(dict(FNF, _cons_p=40.0), "challenge", bal, {"tp": 0.5, "sl": 0.5, "menge": 0.999, "puffer": 0.5})
check(w_alt and w_alt["tp"] > 0.4 * (bal - G + w_alt["tp"]), f"ohne Consistency: Rest 3.250 → TP {w_alt and w_alt['tp']} > 40 % des Gewinns (die Lücke)")
check(w_neu and w_neu["tp"] <= 0.4 * (bal - G + w_neu["tp"]) and str(w_neu.get("stufe", "")).startswith("Etappe (Consistency 40"),
      f"mit FNF1 (_cons_p 40): Etappe, TP {w_neu and w_neu['tp']} ≤ 40 % ({w_neu and w_neu.get('stufe')})")

print("2b) Hedge des Final-Trades (Kontowert ÷ Polster, netto_faktor 1,0, Fusion 0,85 €/Pkt/Lot)")
KF = {"id": "kf", "firm": "FundedNext Futures", "account_type": "challenge", "account_size": "150000.00"}
kw = app.ap_kontowert_konto(KF, 156200.0, [FNF], 245)
satz, wert = kw.get("satz_eur_pro_usd"), kw.get("wert_eur")
pol = (wert / satz) if (satz and wert) else None
check(wert and abs(wert - 772) < 1 and pol and abs(pol - 6200) < 2 and abs(satz - 0.1245) < 0.0005,
      f"Kontowert nach +6.200 $: {wert} € auf Polster {pol and round(pol)} $ (Lock bei Start) → Satz {satz} €/$ (Master geschätzt 760 € / 0,1226; echter Code 772 / 0,1245)")
s2, p2, g2 = app.tfh_satz_polster("FundedNext Futures", satz, wert, None)
check(g2 is None and abs(s2 - satz) < 1e-9 and abs(p2 - pol) < 1e-6, "FNF nimmt die Tradeify-Rechnung (nicht die Lucid-MLL-Variante)")
H = {}
for kt in (1, 2):
    h, gr = app.tfh_hedge(s2, p2, kt, 20.0, 1800, 1.0, 0.01, None)
    H[kt] = h
    print(f"     {kt} NQ, TP 1.800 $: {h and h['lots']} Lot Fusion · Blow +{h and h['slave_risk']} € · Pass −{h and h['hedge_eur']} € ({gr})")
check(H[2] and abs(H[2]["lots"] - 5.86) < 0.02 and abs(H[2]["slave_risk"] - wert) < 1 and H[1] and abs(H[1]["lots"] - 2.93) < 0.02,
      f"2 NQ ≈ 5,86 Lot, 1 NQ ≈ 2,93 Lot (Master geschätzt ≈ 5,7 / 2,8), Blow deckt den Kontowert ({wert} €)")
check(H[1]["hedge_eur"] == H[2]["hedge_eur"], f"Pass-Kosten am TP unabhängig von der Kontraktzahl ({H[1]['hedge_eur']} €)")

print("3) Required profit + ap_cons_regel")
K150 = {"id": "k150", "firm": "FundedNext Futures", "account_type": "challenge", "account_size": "150000.00"}
K50 = {"id": "k50", "firm": "FundedNext Futures", "account_type": "challenge", "account_size": "50000.00"}
check(app.zw_cons_moeglich(FNF, K150) and not app.zw_cons_moeglich(FNF, K50), "Consistency möglich: FNF 150k ja, 50k nein (nicht belegt, kein Lesen)")
check(app.zw_cons_moeglich(FNF, dict(K150, firm="Lucid Trading", account_size="50000.00"))
      and not app.zw_cons_moeglich(FNF, dict(K150, firm="Apex Trader")) and not app.zw_cons_moeglich(FNF, dict(K150, firm="FundedNext")),
      "Lucid 50k weiter ja, Apex/FundedNext CFD nein (wie bisher)")
cz = app.zw_cons_ziel(FNF, K150, 158040.0, {"2026-11-20": 3300.0, "2026-11-21": 3100.0, "2026-11-22": 1640.0})
check(cz and cz["p"] == 40 and cz["ziel_cons"] == 158250.0 and not cz["erfuellt"], f"größter Tag 3.300 → Required profit 8.250, nicht erreicht ({cz})")
cz = app.zw_cons_ziel(FNF, K150, 158040.0, {"2026-11-20": 3140.0, "2026-11-21": 3120.0, "2026-11-22": 1780.0})
check(cz and cz["erfuellt"], f"Weg mit Etappen ≤ 3.150: Ziel zählt ({cz and cz['ziel_cons']})")
check(app.zw_cons_ziel(FNF, K50, 52540.0, {"2026-11-20": 1500.0}) is None, "Emins 50k: keine Consistency-Vorgabe → None")
gelesen = []
app._zw_cons_tage_laden = lambda ids: (gelesen.append(tuple(ids)), {i: {"2026-11-20": 3140.0} for i in ids})[1]
r = app.ap_cons_regel(FNF, dict(FNF), K150, 154500.0, [])
check(r.get("_cons_p") == 40 and gelesen, f"ap_cons_regel FNF 150k ab halbem Ziel: _cons_p 40 (LC1-Weg wie Lucid) ({r.get('_cons_p')})")
gelesen.clear()
r = app.ap_cons_regel(FNF, dict(FNF), K150, 153900.0, [])
check("_cons_p" not in r and not gelesen, "unter halbem Ziel: nichts lesen, Regel unverändert")
r = app.ap_cons_regel(FNF, dict(FNF), K50, 51300.0, [])
check("_cons_p" not in r and not gelesen, "Emins 50k: nichts lesen, Regel unverändert")
r = app.ap_cons_regel(FNF, dict(FNF), dict(K150, firm="Tradeify"), 156000.0, [])
check("_cons_p" not in r, "Tradeify: kein _cons_p (wie vor FNF1)")

print("4) Frontend + SQL")
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("n === 'fundednextfutures' && Array.isArray((D.tradeify_final_hedge || {}).firmen)" in HTML
      and "'tradeify_final_hedge_fundednextfutures'" in HTML and "tradeify_final_hedge_fundednextfutures: 'fundednextfutures'" in HTML,
      "Schalter „Final-Trade mit Gegenhedge wie Tradeify“ bei FundedNext Futures, sendet tradeify_final_hedge_firma")
SQL = open(os.path.join(WURZEL, "sql", "2026-11-25_fnf1_fundednext_futures_150k.sql"), encoding="utf-8").read()
check("enable row level security" in SQL and "revoke all on fnf1_auto_plan_regeln_20261125 from public, anon, authenticated" in SQL,
      "Sicherung mit RLS + revoke")
check("when 'FundedNext Futures' then coalesce(p_hedge_art, '') = 'tradeify_final'" in SQL and "then array['FundedNext Futures']" in SQL
      and "when 'Lucid Trading' then coalesce(p_hedge_art, '') = 'tradeify_final'" in SQL, "DB: FNF nur mit Marke tradeify_final, Lucid/Tradeify wie LF1")
check("'[\"fundednextfutures\"]'::jsonb" in SQL and "'planen'], 'true'::jsonb" in SQL and "'kauf_eur', '150000'], '245'::jsonb" in SQL
      and "f.v->'namen' ? 'fundednextfutures'" in SQL, "Regeln: firmen += fundednextfutures, planen true, Kauf 150k 245 €")
check("'phasen', 'challenge', 'menge'], '[1, 2]'::jsonb" in SQL and "'puffer_je_menge'], '{\"1\": [15, 25], \"2\": [15, 25]}'::jsonb" in SQL
      and "'je_groesse'" not in SQL.split("commit;")[0], "150k: 1–2 NQ + Puffer je Menge 1/2; 50k (je_groesse) unberührt")
check("ERST NACH dem Backend-Push" in SQL, "Reihenfolge: SQL erst nach dem Backend-Push")

print()
if FEHLER:
    print(f"✗ {len(FEHLER)} Fehler")
    sys.exit(1)
print("✓ alle Prüfungen grün")
