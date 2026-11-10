#!/usr/bin/env python3
"""Selbsttest LF1 (06.11.2026): Lucid-Final-Trade mit Gegenhedge genau wie Tradeify (Finn: Kauf Lucid 150k 170 €, Hedge 1:1, ein finaler je ID, nur HT).
Prüft mit echtem app.py-Code: tfh_param-Firmenliste (Tradeify immer, ohne Feld bitgleich), tfh_firma/tfh_plan_dabei (Lucid nur HT, nie Orbit Prio 2 →
Emins Lucid bleibt bei ah_tick), Hedge-Größen (Lucid 150k 170 € → 3,68 Lot, 222 € → 4,80 Lot, Tradeify unverändert 6,21 Lot), Texte, Schalter-Endpunkt,
SQL (3 Riegel + ein_finaler_frei, nur Lucid mit Marke hedge_art 'tradeify_final', Regeln, Rückbau-Spiegel) und die Anzeige in prophos.html.
Aufruf: python3 tools/selftest_lf1_lucid_final.py"""
import ast
import os
import re
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "app.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
SQL = open(os.path.join(W, "sql", "2026-11-06_lucid_final_hedge.sql"), encoding="utf-8").read()
RUECK = open(os.path.join(W, "sql", "2026-11-06_lucid_final_hedge_rueckbau.sql"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


baum = ast.parse(SRC)
ns = {"re": re}
KONST = ("AP_GROESSE_TOLERANZ", "AP_KW_PHASEN", "AP_KW_FUNDED", "TFH_SLAVE_PPL", "TFH_STANDARD", "TFH_FIRMEN_ERLAUBT", "TFH_FIRMA_NAME", "AP_MODELLE", "AH_FIRMA")
for x in baum.body:
    if isinstance(x, ast.Assign) and getattr(x.targets[0], "id", "") in KONST:
        exec(compile(ast.Module(body=[x], type_ignores=[]), "app.py", "exec"), ns)
for f in ("_wd_num", "_ist_tradeify_cfd", "_ap_norm", "_firm_norm", "ap_regel_finden", "ap_firma_modell", "ap_plan_modell", "tfh_param", "tfh_firma",
          "tfh_plan_dabei", "tfh_name", "ap_groesse", "ap_kw_param", "_ap_kw_kauf", "_ap_kw_wachsen", "_ap_kw_lock", "ap_kontowert", "tfh_hedge"):
    k = next((x for x in baum.body if isinstance(x, ast.FunctionDef) and x.name == f), None)
    if k is None:
        check(False, f"Funktion {f} in app.py")
        continue
    exec(compile(ast.Module(body=[k], type_ignores=[]), "app.py", "exec"), ns)
for n in ("_firm_norm", "_ap_norm"):            # die Normierer hängen an weiteren Tabellen — für diesen Test reicht a–z0–9
    if n not in ns or n == "_firm_norm":
        ns[n] = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())

P = ns["tfh_param"]
# 1 · Firmenliste
check(P({"tradeify_final_hedge": {"an": True}})["firmen"] == ("tradeify",), "ohne firmen-Feld: nur Tradeify (bitgleich wie bisher)")
check(P({"tradeify_final_hedge": {"an": True, "firmen": ["Lucid", "apex", "tradeify", "lucid"]}})["firmen"] == ("tradeify", "lucid"),
      "firmen: Tradeify immer vorne, Lucid dazu, Unerlaubtes (Apex) und Doppel raus")
check(P({"tradeify_final_hedge": {"an": True, "firmen": []}})["firmen"] == ("tradeify",), "leere Liste: Tradeify bleibt drin")
check(P({"tradeify_final_hedge": {"firmen": "lucid"}})["firmen"] == ("tradeify",), "firmen kein Array → Standard")
live = P({"tradeify_final_hedge": {"an": True, "firmen": ["tradeify", "lucid"], "netto_faktor": 1, "max_lots": 100, "min_lot": 0.01}})
check(live["an"] and live["netto_faktor"] == 1.0 and live["max_lots"] == 100.0, "Live-Parameter: an, Hedge 1:1 (netto_faktor 1), max 100 Lot")

# 2 · Firma erkennen
F = ns["tfh_firma"]
check(F("Tradeify") == "tradeify" and F("Tradeify CFD") is None, "Tradeify ja, Tradeify CFD nie")
check(F("Lucid Trading") is None and F("Lucid Trading", ("tradeify", "lucid")) == "lucid", "Lucid nur, wenn in der Firmenliste")
check(F("Apex Trader", ("tradeify", "lucid")) is None and F("", ("tradeify", "lucid")) is None, "andere Firmen nie")
check(ns["tfh_name"]({"master_firm": "Tradeify"}) == "Tradeify" and ns["tfh_name"]({"master_firm": "Lucid Trading"}) == "Lucid",
      "Anzeigename: Tradeify bitgleich, Lucid neu")

# 3 · Wer gehört dem Weg (nur HT, nie Orbit Prio 2)
D = ns["tfh_plan_dabei"]
FM = [{"namen": ["tradeify"]}, {"namen": ["lucidtrading", "lucid"]}]
FM_P2 = [{"namen": ["tradeify"]}, {"namen": ["lucidtrading", "lucid"], "modell": "orbit_prio2"}]
L2 = ("tradeify", "lucid")
GRP = {"emin"}
GM = {"emin": {"lucidtrading": "orbit_prio2"}}
check(D({"master_firm": "Tradeify", "user_id": "emin"}, L2, GRP, FM, GM), "Tradeify: auch Gruppen-IDs wie bisher")
check(D({"master_firm": "Lucid Trading", "user_id": "ht1"}, L2, GRP, FM, GM), "Lucid HT (Modell orbit_v2) → Final-Weg")
check(not D({"master_firm": "Lucid Trading", "user_id": "emin"}, L2, GRP, FM, GM), "Lucid Emin (Gruppe, orbit_prio2) → nie (bleibt ah_tick)")
check(not D({"master_firm": "Lucid Trading", "user_id": "emin"}, L2, GRP, FM, {"emin": {}}), "Lucid Gruppe auch ohne Prio 2 → nie (nur HT)")
check(not D({"master_firm": "Lucid Trading", "user_id": "ht1"}, L2, GRP, FM_P2, GM), "Lucid HT mit Modell orbit_prio2 → nie (ein Hedge je Plan)")
check(not D({"master_firm": "Lucid Trading", "user_id": "ht1"}, ("tradeify",), GRP, FM, GM), "Lucid ohne Firmenliste → nie")

# 4 · Hedge-Größen mit echtem Kontowert-Code
TR = {"boden": "nachziehend", "namen": ["tradeify"], "dd_usd": 4500, "phasen": {"challenge": {"tp": [3450, 3550], "tp_max": 3600}}, "groessen": [150000],
      "kauf_eur": 215, "ziel_pct": {"challenge": 6}}
LU = {"boden": "nachziehend", "namen": ["lucidtrading", "lucid"], "dd_usd": 4500, "phasen": {"challenge": {"tp": [3450, 3550], "tp_max": 3600}},
      "groessen": [50000, 150000], "kauf_eur": {"50000": 78, "150000": 170}, "ziel_pct": {"challenge": 6}, "daily_usd": 2700, "lock_bei_start": True,
      "je_groesse": {"50000": {"dd_usd": 2000, "kauf_eur": 78, "daily_usd": 1200, "phasen": {"challenge": {"tp": [1150, 1180], "tp_max": 1200}}}}}


def hedge(regel, bal, tp, kt, kauf=None, mll=None):
    kv = ns["ap_kontowert"]("challenge", bal, ns["ap_kw_param"](regel), kauf)
    satz, pol = kv["satz"], kv["wert"] / kv["satz"]
    if mll:   # LH1 10.11.2026: Lucid q = Kontowert ÷ MLL (tfh_satz_polster wird erst unten geladen → hier dieselbe Formel)
        satz, pol = kv["wert"] / mll, float(mll)
    h, gr = ns["tfh_hedge"](satz, pol, kt, 20.0, tp, 1.0, 0.01)
    return kv, h


kv, h = hedge(TR, 156000, 3000, 2)
check(kv["wert"] == 593 and h["lots"] == 6.21 and h["slave_risk"] == 593.0, f"Tradeify 150k unverändert: 593 € → 6,21 Lot ({h['lots']})")
kv, h = hedge(LU, 156000, 3000, 2, mll=4500)
check(kv["kauf"] == 170 and kv["wert"] == 469 and kv["polster"] == 5900 and h["lots"] == 4.9 and round(h["hedge_eur"]) == 313,
      f"Lucid 150k Kernwert 170 € (LH1: Lock bei 150.100 → Kontowert-Polster 5.900; Hedge auf MLL 4.500): 469 € → {h['lots']} Lot, Pass −{h['hedge_eur']} €")
kv, h = hedge(LU, 156000, 3000, 2, kauf=222, mll=4500)
check(kv["wert"] == 613 and h["lots"] == 6.41, f"Lucid 150k gebuchter Kauf 222 €: 613 € → {h['lots']} Lot")
check(abs(h["slave_risk"] / h["master_risk"] - kv["wert"] / 4500) < 1e-4, "LH1: Blow-Gewinn je $ = Kontowert ÷ MLL 4.500 (Daily 2.700 → Hedge +q × 2.700)")
kv, h = hedge(LU, 51800, 1200, 1, mll=2000)
check(kv["kauf"] == 78 and h is not None and h["lots"] > 0, f"Lucid 50k bleibt bei 78 € ({kv['wert']} € → {h['lots']} Lot)")

# 5 · tfh_tick: Tradeify-Weg bitgleich, Lucid nur über die Liste
tick = SRC[SRC.index("def tfh_tick("):SRC.index("# NEUE HEDGE-TRADES BESTÄTIGEN")]
check('{"master_firm": "ilike.*tradeify*"} if par["firmen"] == ("tradeify",)' in tick, "ohne Zusatz-Firma: dieselbe Abfrage ilike *tradeify*")
check('plaene = [p for p in roh if str(p.get("user_id")) not in aus and not _ist_tradeify_cfd(p.get("master_firm"))]' in tick,
      "ohne Zusatz-Firma: derselbe Plan-Filter wie bisher")
check("tfh_plan_dabei(p, par[\"firmen\"], _gids, _fm, _gm)" in tick and "not _gm_fehler or tfh_firma" in tick,
      "mit Lucid: tfh_plan_dabei + Gruppen-Lesefehler → nur Tradeify")
check(tick.count("tfh_name(p)") == 3 and 'alarm_senden(3, "tradeify_final_ohne", f"Finaler {tfh_name(p)}-Trade ohne Gegenhedge"' in SRC,
      "Texte mit Firmenname, Alarm-Schlüssel tradeify_final_ohne bleibt")
ah = SRC[SRC.index("def ah_tradeify_final("):SRC.index("def tfh_hedge(")]
check('"tradeify" in firm.lower() and not _ist_tradeify_cfd(firm) and tfh_ist_final(p, a)' in ah, "ah_tradeify_final unverändert (Emins Lucid-Finals bleiben Prio 2)")

# 6 · Schalter-Endpunkt + Anzeige
ep = SRC[SRC.index('if "tradeify_final_hedge_firma" in body:'):SRC.index("    neu = dict(ap_ausgleich_param(regeln))")]
check('tf_f.get("firma") in TFH_FIRMEN_ERLAUBT and tf_f.get("firma") != "tradeify"' in ep and 'firmen=["tradeify"] + neu_f' in ep and "an=" not in ep,
      "Endpunkt: nur Zusatz-Firma, Tradeify bleibt, Hauptschalter .an unberührt")
check('"firmen": list(p["firmen"])' in SRC, "tfh_stand zeigt die Firmenliste")
check("n === 'lucidtrading' && Array.isArray((D.tradeify_final_hedge || {}).firmen)" in HTML and "'tradeify_final_hedge_lucid'" in HTML
      and "tradeify_final_hedge_firma: { firma: 'lucid', an }" in HTML, "Planer-Einstellungen: Lucid-Slider schreibt tradeify_final_hedge_firma")
check("tradeify_final: ['Final'," in HTML and "z.hedge_art === 'tradeify_final' ? 'Final-Hedge'" in HTML and "'Tradeify final'" not in HTML,
      "Anzeige firmenneutral, Schlüssel hedge_art 'tradeify_final' bleibt")

# 7 · SQL
patches = re.findall(r"\('(\w+)',\s*\$a\$(.*?)\$a\$,\s*\$b\$(.*?)\$b\$\)", SQL, re.S)
fns = sorted({p[0] for p in patches})
check(len(patches) == 9 and fns == ["prophos_ein_finaler_frei", "trade_plans_a_final_halten", "trade_plans_ein_finaler", "trade_plans_kontoart_weg"],
      f"9 Patch-Stellen in 4 Funktionen (Halten, ein finaler + frei, Kontoart-Weg) — {len(patches)}")
check(all(a != b and a not in ("",) for _f, a, b in patches), "jede Stelle ändert etwas")
check("if strpos(def, r.neu) > 0 then" in SQL and "if n_alt <> 1 then" in SQL and "raise exception" in SQL, "idempotent + Abbruch, wenn die Stelle nicht genau 1× da ist")
check("when 'Tradeify' then true" in SQL and "coalesce(p_hedge_art, '') = 'tradeify_final' and 'Lucid Trading' = any(public.prophos_final_hedge_firmen())" in SQL,
      "Tradeify wie bisher; Lucid nur mit Marke tradeify_final + Firmenliste (Emin: Marke apex → nie)")
check(SQL.count("revoke all on function public.prophos_final_hedge_firm") == 2, "Hilfsfunktionen nicht über PostgREST aufrufbar")
check("'{\"firmen\": [\"tradeify\", \"lucid\"]}'" in SQL and "'kauf_eur', '150000'], '170'::jsonb" in SQL and "'50000'" not in SQL.split("-- Prüfen")[0],
      "Regeln: Firmenliste + Lucid 150k 170 €, 50k unberührt")
tradeify_gleich = {"'finaler ' || public.prophos_firma_key(new.master_firm) || '-Trade wartet auf Gegenhedge (TP '",
                   "'[finaler ' || public.prophos_firma_key(new.master_firm) || ' gehalten] ' || txt", "'[ein finaler ' || k || ' je ID] ' || txt"}
check(all(any(t in b for _f, _a, b in patches) for t in tradeify_gleich), "Texte aus dem Firmenschlüssel — für Tradeify Wort für Wort wie bisher")
rp = re.findall(r"\('(\w+)',\s*\$a\$(.*?)\$a\$,\s*\$b\$(.*?)\$b\$\)", RUECK, re.S)
check(rp == patches and "execute replace(def, r.neu, r.alt);" in RUECK, "Rückbau: dieselben 9 Stellen, neu → alt")
check("drop function if exists public.prophos_final_hedge_firma(text, text);" in RUECK and "- 'firmen'" in RUECK and "'222'::jsonb" in RUECK,
      "Rückbau: Hilfsfunktionen weg, Firmenliste weg, Lucid 150k zurück auf 222 €")


# LH1 (Finn 10.11.2026, Fall Simon LFE…0003 −2.817 $, Fusion +221 €): Lucid-Final rechnet q = Kontowert ÷ MLL-Betrag des Kontos (4.500), nicht ÷ (Balance − Lock)
for f in ("_ap_de", "tfh_satz_polster"):
    k = next((x for x in baum.body if isinstance(x, ast.FunctionDef) and x.name == f), None)
    check(k is not None, f"Funktion {f} in app.py")
    if k is not None:
        exec(compile(ast.Module(body=[k], type_ignores=[]), "app.py", "exec"), ns)
SP = ns["tfh_satz_polster"]
# Simon Lucid 150k, Plan 9e700e16: Kontowert 561 €, vorher Polster 6.977,61 (Balance − 150.000), q 0,0804
s_alt = 561 / 6977.61
sz, pol, gr = SP("Lucid Trading", s_alt, 561, 4500)
check(gr is None and pol == 4500.0 and abs(sz - 561 / 4500) < 1e-9, f"Lucid: Polster = MLL 4.500 $, Satz {sz:.4f} statt {s_alt:.4f}")
h, g = ns["tfh_hedge"](sz, pol, 2, 20.0, 2068, 1.0, 0.01, 0.85)
check(g is None and abs(h["q"] - 0.12467) < 1e-4 and abs(h["slave_risk"] - 561) < 0.01 and h["master_risk"] == 4500.0 and 5.8 <= h["lots"] <= 5.9,
      f"Hedge: q {h['q']} €/$, auf 4.500 $ +{h['slave_risk']} €, {h['lots']} Lot (vorher 3,61)")
check(abs(h["q"] * 2700 - 336.6) < 1, f"am Daily Loss 2.700 $: +{h['q'] * 2700:.0f} € (vorher q 0,0804 → +217 €)")
check(abs(h["q"] * 6872.5 - 856.8) < 1, "voller Blow am Lock 150.100 (−6.872,50 $): bewusst mehr als der Kontowert")
sz5, pol5, _ = SP("Lucid Trading", 0.05, 160, 2000)
check(pol5 == 2000.0 and abs(sz5 - 0.08) < 1e-9, "Lucid 50k: Polster = MLL 2.000 $")
sz2, pol2, gr2 = SP("Tradeify", 0.15, 675, None)
check((sz2, pol2, gr2) == (0.15, 4500.0, None), "Tradeify unverändert: Satz und Polster aus dem Kontowert, MLL egal")
check(SP("Tradeify CFD", 0.15, 675, 999) == (0.15, 4500.0, None), "Tradeify CFD unverändert")
check(SP("Lucid Trading", s_alt, 561, None)[2] is not None and SP("Lucid Trading", s_alt, 561, None)[0] is None, "Lucid ohne MLL: kein Hedge, Grund")
check(SP("Lucid Trading", s_alt, None, 4500)[2] is not None, "Lucid ohne Kontowert: kein Hedge, Grund")
check(SP("Lucid Trading", s_alt, 520, 4500)[1] == 4500.0, "Lucid nach Verlusttag: Polster bleibt 4.500 (kein Boden-Weg)")
check(SRC.count("tfh_satz_polster(a.get(\"firm\"), satz, wert,") == 2 and SRC.count("tfh_mll(a, ") == 3 and "def tfh_mll(a, firmen):" in SRC and "kw_lock=" not in SRC,
      "tfh_tick und tfh_vorschau rechnen Lucid über tfh_mll, kein Boden-Weg mehr")

print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
