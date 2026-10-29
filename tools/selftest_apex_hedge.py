#!/usr/bin/env python3
"""Selbsttest APEX-CHALLENGE-WD-HEDGE (30.10.2026, Finn: Apex-Challenges laufen wie Winning Days mit Fusion-Gegenhedge, zählen aber nicht als WD).
Teil A rein rechnend (aus app.py exec'd): ah_param (Standard aus, max_lots vom Echo-Hedge), ah_master_ppl (NQ/MNQ), Hedge-Größe über eh_hedge
mit Satz = Kaufpreis ÷ Max DD und Polster als master_risk (Finns Beispiel 100k/50 €/3.000 $), Blow deckt Kaufpreis ÷ 0,89.
Teil B am Quelltext: ah_tick-Guard (tvv2, ungeclaimt, ohne Hedge, kein Orbit V3), Marke + winning_day false + Boden, gemeinsame
Vorgemerkt-Zählung, Schalter-Route, SQL-Ausnahme im Kontoart-Riegel, Tab: Liq-Weiche am Boden, tpWdZaehlt, Admin-Schalter.
Aufruf:  python3 tools/selftest_apex_hedge.py"""
import os
import re
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = open(os.path.join(W, "app.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
SQL = open(os.path.join(W, "sql", "2026-10-30_apex_hedge.sql"), encoding="utf-8").read()
fehler = 0


def soll(name, ok):
    global fehler
    print(("ok   " if ok else "FEHL ") + name)
    fehler += 0 if ok else 1


def block(name):
    i = APP.index(f"\ndef {name}(") + 1
    return APP[i:APP.find("\n\n\n", i)]


def konst(k):
    return re.search(rf"^{k} = .*$", APP, re.M).group(0)


def wd_num(x):
    try:
        return float(x) if x is not None and x != "" and not isinstance(x, bool) else None
    except (TypeError, ValueError):
        return None


ns = {"_wd_num": wd_num, "_wt_now_iso": lambda: "2026-10-30T10:00:00+00:00"}
exec("\n".join([konst(k) for k in ("EH_STANDARD", "EH_MARGE_RESERVE", "AH_STANDARD")]
               + [block(f) for f in ("eh_param", "eh_hedge", "eh_marge", "ah_param", "ah_master_ppl", "ah_vorschau",
                                     "plan_ist_wd", "plan_ist_apex_hedge", "plan_wd_zaehlt", "puls_heim_big_trades", "puls_heim_wd_trades",
                                     "ah_dll_balance", "_lt_liq_balance")]), ns)

# Teil A
p0 = ns["ah_param"]({})
soll("Standard aus, netto_faktor 0,89", p0["an"] is False and p0["netto_faktor"] == 0.89)
soll("max_lots vom Echo-Hedge (gemeinsame Grenze)", ns["ah_param"]({"echo_hedge": {"max_lots": 40}})["max_lots"] == 40.0)
soll("nur echtes true schaltet an", ns["ah_param"]({"apex_hedge": {"an": "true"}})["an"] is False and ns["ah_param"]({"apex_hedge": {"an": True}})["an"] is True)
soll("MNQ 2 $/Pkt, NQ 20 $/Pkt", ns["ah_master_ppl"]({"master_symbol_root": "MNQ"}) == 2.0 and ns["ah_master_ppl"]({"master_symbol": "NQZ6"}) == 20.0)
satz, polster = 50 / 3000, 3000.0          # Finn: 100k für 50 €, 3.000 $ Max DD
h, g = ns["eh_hedge"](satz, 2, 20.0, 0.85, polster, 0.89, 0.01)
soll("100k 2 NQ: Hedge rechenbar", g is None and h is not None)
q = satz / 0.89
soll("q = Kaufpreis ÷ Max DD ÷ 0,89", abs(h["q"] - round(q, 5)) < 1e-9)
soll("slave_risk = q × Polster ≈ 56 € (deckt 50 € netto)", abs(h["slave_risk"] - round(q * polster, 2)) < 0.01 and 55 < h["slave_risk"] < 57)
blow_eur = h["lots"] * (polster / (20.0 * 2)) * 0.85
soll("Blow (−Polster) bringt auf Fusion ≈ slave_risk", abs(blow_eur - h["slave_risk"]) < 1.0)
soll("Lots 100k/2 NQ ≈ 0,88", abs(h["lots"] - 0.88) < 0.02)
h3, _ = ns["eh_hedge"](150 / 4000, 3, 20.0, 0.85, 4000.0, 0.89, 0.01)
soll("150k 3 NQ: Lots ≈ 2,97", abs(h3["lots"] - 2.97) < 0.03)
ok, gr = ns["eh_marge"]({"offen": {"buy": 30, "sell": 29}, "je_lot": 277, "frei": 100000}, 2, "buy", 0, 60)
soll("60-Lot-Grenze greift (59 offen + 2 neu)", ok is False and "gleichzeitig" in gr)

vs = ns["ah_vorschau"](h, 50.0, polster, 97000.0, 600)
soll("Vorschau: Lots, €, Blow +€ = slave_risk, TP −€ = −TP × q, Boden",
     vs["lots"] == h["lots"] and vs["eur"] == 50.0 and vs["blow_eur"] == h["slave_risk"] and vs["tp_eur"] == round(-600 * h["q"], 2)
     and vs["liq_balance"] == 97000.0)
soll("Vorschau: ohne TP kein TP-€", ns["ah_vorschau"](h, 50.0, polster, 97000.0, None)["tp_eur"] is None)
ap = {"route": "tvv2", "hedge_eur": 50, "winning_day": False, "mt5_baseline": {"apex_hedge": {"status": "mit", "liq_balance": 97000}}}
wd = {"route": "tvv2", "hedge_eur": 40, "winning_day": True, "mt5_baseline": {}}
soll("Apex mit Hedge: WD-Weg ja, zählt als WD nein", ns["plan_ist_wd"](ap) and not ns["plan_wd_zaehlt"](ap))
soll("echter WD zählt weiter", ns["plan_wd_zaehlt"](wd))
soll("Auszug ohne mt5_baseline: ah_status reicht", ns["plan_ist_apex_hedge"]({"ah_status": "mit"}) and not ns["plan_ist_apex_hedge"]({"ah_status": "ohne"}))
soll("vorgemerkt (hedge_art apex, ohne Umstellung) ist noch kein Apex-Hedge",
     not ns["plan_ist_apex_hedge"]({"mt5_baseline": {"hedge_art": "apex", "apex_hedge": {"status": "ohne"}}}))
offen = dict(ap, id="a", status="open", mt5_baseline={"apex_hedge": {"status": "mit"}, "hedge": {"pc": "pc-1"}})
soll("Heim-Wache: Apex nicht als Big Trade (2.000 $) …", ns["puls_heim_big_trades"]([offen], "pc-1") == [])
soll("… sondern als Winning Day (100 $)", ns["puls_heim_wd_trades"]([offen], "pc-1") == [offen])

acc100 = {"account_type": "challenge", "max_daily_drawdown": 1500, "max_drawdown": 3000}
soll("Daily Loss aus dem Konto ab Tagesstart", ns["ah_dll_balance"](acc100, 99500)[0] == 98000.0 and ns["ah_dll_balance"]({}, 99500) == (None, None))
ap_liq = dict(ap, mt5_baseline={"apex_hedge": {"status": "mit", "liq_balance": 97000}})
soll("Liq = max(Boden, Daily Loss): Start 99.500 → 98.000 (Daily Loss)", ns["_lt_liq_balance"](acc100, ap_liq, 99500)[0] == 98000.0)
soll("Liq = max(Boden, Daily Loss): Start 98.200 → 97.000 (Boden)", ns["_lt_liq_balance"](acc100, ap_liq, 98200)[0] == 97000.0)
soll("Liq ohne Konto-Daily-Loss: Boden", ns["_lt_liq_balance"]({"account_type": "challenge"}, ap_liq, 99500)[0] == 97000.0)

# Teil B
t = block("ah_tick")
soll("Vormerken: updated_at der geschriebenen Zeile übernommen, ohne → kein Umstellen im Takt",
     'p["updated_at"] = neu[0].get("updated_at")' in t and 'not p.get("_ah_kein_guard")' in t)
lf = block("liq_regel_felder")
soll("Radar-Liq: Apex wie Challenge + Konto-Daily-Loss + Challenge-Boden",
     "wd = plan_ist_wd(plan, typ) and not ah" in lf and "ah_dll_balance(a, tagesstart" in lf and "Challenge-Boden" in lf)
soll("Konto-Selects tragen max_daily_drawdown (Live-Trades, Heim-Wache)", APP.count("max_drawdown,max_daily_drawdown,tv_balance") >= 2)
soll("Tab: Apex-Hedge-Level = max(Boden, Daily Loss)", "art === 'apex_boden' ? hedgeLiqDllApex(" in HTML and "function hedgeLiqDllApex(" in HTML)
soll("Tick: nur tvv2, ungeclaimt, ohne Hand-Werte, kein Orbit V3, ohne Hedge",
     all(x in t for x in ('"route": "eq.tvv2"', '"start_um_gestartet_at": "is.null"',
                          '"hand_werte_at": "is.null"', '"orbit_v3": "is.false"', '(hedge_eur.is.null,hedge_eur.eq.0)')))
soll("Tick: nur Apex und nur Kontoart challenge", "_firm_norm(AH_FIRMA)" in t and '== "challenge"' in t)
soll("Vormerken: hedge_art 'apex' + hedge_vorschau (Namen für S4)", 'hedge_art="apex", hedge_vorschau=vs' in t)
soll("Umstellen nur mit hedge_freigabe_at + auto_bestaetigt_at",
     'p.get("hedge_freigabe_at") and p.get("auto_bestaetigt_at")' in t and 'g["hedge_freigabe_at"] = "not.is.null"' in t)
soll("Spalte hedge_freigabe_at fehlt → nichts umstellen", "freigabe_da = False" in t and "if not freigabe_da:" in t)
z = block("ah_zurueck")
soll("Schalter aus: Marke + Vorschau weg", 'base.pop("hedge_art", None)' in z and 'base.pop("hedge_vorschau", None)' in z)
soll("Tick: winning_day false, hedge_eur = Kontowert, master_risk = Polster, Marke mit Boden",
     all(x in t for x in ('"winning_day": False', '"hedge_eur": round(wert, 2)', '"master_risk": round(polster, 2)', '"liq_balance": liq', 'apex_hedge=info')))
soll("Tick: Boden = Balance − Polster", "round(float(bal) - polster, 2)" in t)
soll("Tick: Werte von vorher gemerkt (Rückweg)", '"vorher": {k: p.get(k) for k in ("master_risk", "slave_risk", "multiplier", "hedge_faktor")}' in t)
soll("Tick: gemeinsame Vorgemerkt-Zählung + Marge", "hedge_vorgemerkt(von, jetzt)" in t and "eh_marge(" in t)
soll("Echo-Hedge nutzt dieselbe Vorgemerkt-Zählung", "vorgemerkt = hedge_vorgemerkt(von, jetzt)" in block("eh_tick"))
hv = block("hedge_vorgemerkt")
soll("Vorgemerkt zählt Echo (mt5), finalen Tradeify und Apex (tvv2)", '("echo_hedge", "mt5"), ("tradeify_hedge", "tvv2"), ("apex_hedge", "tvv2")' in hv)
soll("finaler Tradeify nutzt dieselbe Vorgemerkt-Zählung", "vorgemerkt = hedge_vorgemerkt(von, jetzt)" in block("tfh_tick"))
soll("Takt im ap_loop, eigener try", "if ah_tick() is not None:" in APP)
soll("Schalter-Route apex_hedge (bool)", '"apex_hedge" in body' in APP and '"apex_hedge = true | false"' in APP)
soll("Stand in der Delta-Antwort", '"apex_hedge": ah_stand()' in APP)
soll("SQL: Schalter Standard aus (Merge)", '{"an": false, "netto_faktor": 0.89' in SQL and "prophos_apex_hedge_an()" in SQL)
soll("SQL: Kontoart-Riegel lässt nur Apex-Challenge tvv2 + Marke + Schalter durch",
     all(x in SQL for x in ("typ = 'challenge'", "coalesce(new.route, '') = 'tvv2'", "prophos_firma_key(new.master_firm) = 'Apex Trader'",
                            "new.mt5_baseline->'apex_hedge'->>'status'", "public.prophos_apex_hedge_an()")))
soll("SQL: Echo-Hedge-Block bleibt drin", "HT ECHO-HEDGE B2" in SQL)
soll("SQL: Tradeify-Block (S4) drin, fehlende S4-Schalter-Funktion wird angelegt (Reihenfolge egal)",
     "FINALER TRADEIFY MIT GEGENHEDGE (29.10.2026)" in SQL and "to_regprocedure('public.prophos_tradeify_final_hedge_an()') is null" in SQL)
_kw = lambda t: t[t.index("create or replace function public.trade_plans_kontoart_weg()"):t.index("end $function$;", t.index("create or replace function public.trade_plans_kontoart_weg()"))]
soll("SQL: kontoart_weg Zeichen für Zeichen wie S4s Datei",
     _kw(SQL) == _kw(open(os.path.join(W, "sql", "2026-10-29_tradeify_final_hedge.sql"), encoding="utf-8").read()))
soll("Tab: Kennung + zählt-als-WD", "const tpIstApexHedge = p =>" in HTML and "const tpWdZaehlt = p => tpIstWdPlan(p) && !tpIstApexHedge(p)" in HTML)
soll("Tab: Liq am Challenge-Boden statt Größe + 100", "if(ahLiq > 0){ liq = ahLiq; art = 'apex_boden' }" in HTML)
soll("Liq am Boden auch im Backend (_lt_liq_balance)", "Apex mit Hedge: Challenge-Boden" in block("_lt_liq_balance"))
soll("Zählstellen: wd-heute, Overview, konto_typ, Good Day nehmen Apex aus",
     "or plan_ist_apex_hedge(p):" in APP and "ah_status:mt5_baseline->apex_hedge->>status" in APP
     and 'and not plan_ist_apex_hedge(plan) else None' in APP and "if f_kk is None or plan_ist_apex_hedge(plan):" in APP)
soll("Live-Zeile trägt apex_hedge", 'z["apex_hedge"] = plan_ist_apex_hedge(q)' in APP)
soll("SQL: Big-Trade-Riegel sieht Apex als WD (3 Aufrufer)", SQL.count("public.prophos_wd_wie(") == 4 and "function public.prophos_wd_wie(" in SQL)
soll("Tab: konto_typ/Sticker/Tagesplan über tpWdZaehlt", HTML.count("tpWdZaehlt(") >= 3 and "if(tpWdZaehlt(p))        return 'wd'" in HTML)
soll("Tab: Radar-Label Apex-Hedge mit Fusion-Spalte", "if(t.apex_hedge === true) return 'Apex-Hedge'" in HTML
     and HTML.count("'Winning Day', 'Apex-Hedge'") >= 3)
soll("Tradeify-Final-Hedge-Schalter: Delta-Feld, Route (bool), tfh_stand",
     '"tradeify_final_hedge": tfh_stand()' in APP and '"tradeify_final_hedge = true | false"' in APP and "def tfh_stand(" in APP)
soll("Tab: Tradeify-Final-Hedge-Schalter neben Apex", 'data-apd-schalter="tradeify_final_hedge"' in HTML
     and "${apdTradeifyHedgeSchalterHtml(v, admin)}" in HTML and "feld === 'tradeify_final_hedge'" in HTML)
soll("Tab: Admin-Schalter", 'data-apd-schalter="apex_hedge"' in HTML and "apdApexHedgeSchalterHtml(v, admin)" in HTML)
print("ALLE OK" if not fehler else f"{fehler} FEHLER")
sys.exit(1 if fehler else 0)
