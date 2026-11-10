#!/usr/bin/env python3
"""Selbsttest SL1 (10.11.2026, Master): WD-SL nachwürfeln — Rückfall-Pläne der PC-Tabs (wdPlanAnlegen, wd_sl „Rückfall ohne Würfel") bekommen auf Railway den
Server-Würfel (app.py wd_sl_nach_kandidat / wd_sl_nach_rechnen / wd_sl_nach_tick). Ohne Netz: die Liq-Rechnung läuft echt (Lader aus selftest_wd_sl_wuerfel),
DB-Aufrufe sind nachgebaut. Prüft Kandidaten, Recoverer/Ausgleich/Topstep Express, ein einziges Update mit Guards (Claim, updated_at, Rückfall-Grund), andere
Baseline-Schlüssel bleiben, Lesefehler = nichts schreiben, Würfel aus = nichts, und dass der PC-Tab beim Start die frische Zeile nimmt.
Aufruf: python3 tools/selftest_wd_sl_nachwuerfeln.py"""
import json
import os
import random
import subprocess
import tempfile
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, HIER)
import selftest_wd_sl_wuerfel as ws1  # noqa: E402

APP = os.path.join(WURZEL, "app.py")
HTML = os.path.join(WURZEL, "prophos.html")
FEHLER = []


def check(ok, name):
    print(("  ✓ " if ok else "  ✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade():
    ns = ws1.lade()
    src = open(APP, encoding="utf-8").read()
    ns.update(timedelta=timedelta, time=__import__("time"))
    for fn in ("_ap_ts", "wd_ist_recoverer_plan"):
        i = src.index(f"\ndef {fn}(") + 1
        m = re.compile(r"\n(?=\S)").search(src, src.index("\n", i))
        exec(src[i:m.start() if m else len(src)], ns)
    i = src.index("# ══ SL1 WD-SL NACHWÜRFELN")
    exec(src[i:src.index("# ── Farmer auf V2", i)], ns)
    return ns, src


def main():
    ns, src = lade()
    std, _q = ns["wd_sl_wuerfel_regel"](ns["WD_SL_WUERFEL_STD"])
    JETZT = datetime(2026, 11, 10, 4, 0, tzinfo=timezone.utc)
    LIQ = [{"id": 1, "firma": "Tradeify", "kontotyp": "winning_days", "groesse": None, "art": "boden", "betrag_usd": None,
            "lock_ueber_start_usd": 100, "stufen": None, "wie_kontotyp": None}]
    ACC = {"id": "k-1", "name": "150k T1 → Funded", "firm": "Tradeify", "account_type": "winning_days", "max_drawdown": 4500,
           "tv_balance": 165000, "tv_balance_at": "2026-11-10T01:00:00+00:00"}
    RUECK = {"ohne": True, "stufe": None, "pct": None, "usd": None, "puffer": None, "balance": None, "liq_balance": None, "regel": "sl_wuerfel",
             "grund": "Rückfall ohne Würfel"}

    def plan(**x):
        p = {"id": "p-1", "status": "planned", "notes": "Winning-Day-Farmer", "master_account_id": "k-1", "master_firm": "Tradeify", "master_name": "150k T1",
             "master_symbol": "MNQZ6", "route": "tvv2", "winning_day": True, "master_sl": None, "start_um": (JETZT + timedelta(minutes=30)).isoformat(),
             "start_um_gestartet_at": None, "started_at": None, "orbit_gesendet_at": None, "updated_at": "2026-11-10T03:50:00.123456+00:00",
             "mt5_baseline": {"wd_sl": dict(RUECK), "start_sperre": {"art": "x"}}}
        p.update(x)
        return p

    print("1) Kandidaten")
    K = ns["wd_sl_nach_kandidat"]
    check(K(plan(), JETZT), "Farmer-Plan geplant, Rückfall-wd_sl, Start in 30 min → Kandidat")
    check(not K(plan(start_um=(JETZT + timedelta(seconds=100)).isoformat()), JETZT), "Start in < 2 min → nicht anfassen")
    check(not any(K(plan(**{f: "2026-11-10T03:59:00+00:00"}), JETZT) for f in ("start_um_gestartet_at", "started_at", "orbit_gesendet_at")),
          "geclaimt / gestartet / an Puls gesendet → nie")
    check(not K(plan(status="open"), JETZT) and not K(plan(notes="Hand"), JETZT), "nicht geplant oder kein Farmer-Plan → nie")
    check(not K(plan(mt5_baseline={"wd_sl": dict(RUECK, grund="gewürfelt: ohne SL")}), JETZT) and not K(plan(mt5_baseline={}), JETZT),
          "schon gewürfelt oder ohne wd_sl → nie (kein zweiter Würfel)")
    # Prüfer S2 (MUSS): Sperr-Marke eines laufenden Hand-/Fern-Starts
    check(not K(plan(mt5_baseline={"wd_sl": dict(RUECK), "sl_lauf_at": (JETZT - timedelta(minutes=5)).isoformat()}), JETZT)
          and K(plan(mt5_baseline={"wd_sl": dict(RUECK), "sl_lauf_at": (JETZT - timedelta(minutes=31)).isoformat()}), JETZT),
          "frische Sperr-Marke sl_lauf_at (Hand-/Fern-Start läuft) → nie; älter als 30 min (abgebrochen) → wieder Kandidat")

    print("2) Rechnen wie der POST-Weg")
    R = ns["wd_sl_nach_rechnen"]

    class Folge:
        def __init__(self, *w):
            self.w = list(w)

        def random(self):
            return self.w.pop(0)

    ws_, usd = R(std, plan(), ACC, LIQ, [], rnd=Folge(0.59, 0.53), jetzt_iso="t")
    check(usd == 2280 and ws_["usd"] == 2280 and ws_["puffer"] == 14900 and ws_["quelle"] == "nachgewuerfelt" and ws_["nach_at"] == "t",
          f"Tradeify 165k: Puffer 14.900, 15,3 % → SL 2.280 $ (wie WS1, Herkunft markiert)")
    ws_, usd = R(std, plan(), ACC, LIQ, [], rnd=Folge(0.2), jetzt_iso="t")
    check(usd is None and ws_["ohne"] and ws_["grund"] == "gewürfelt: ohne SL", "Stufe „kein SL“ gewürfelt → ohne SL, kein master_sl")
    ws_, usd = R(std, plan(master_firm="Apex", master_symbol="NQZ6"), dict(ACC, firm="Apex"), LIQ, [], rnd=Folge(0.59, 0.53))
    check(usd is None and ws_["grund"] == "Recoverer — kein Würfel", "Recoverer (Apex auf NQ) → kein Würfel, Grund wie POST")
    ws_, usd = R(std, plan(mt5_baseline={"wd_sl": dict(RUECK), "wd_ausgleich": True}), ACC, LIQ, [], rnd=Folge(0.59, 0.53))
    check(usd is None and ws_["grund"] == "Ausgleich — kein Würfel", "Tradeify-Ausgleich → kein Würfel, Grund wie POST")
    ws_, usd = R(std, plan(master_firm="Topstep"), dict(ACC, firm="Topstep", name="50k Express TS"), LIQ, [], rnd=Folge(0.59, 0.53))
    check(usd is None and ws_["ohne"] and ws_["grund"] != "Rückfall ohne Würfel",
          f"Topstep/Express: nie Rückfall-Grund, ohne Liq-Wert kein SL ({ws_['grund']})")
    _fp = ns["wd_sl_fuer_plan"]
    ns["wd_sl_fuer_plan"] = lambda *a, **k: 1 / 0
    ws_, usd = R(std, plan(), ACC, LIQ, [], rnd=Folge(0.59, 0.53))
    ns["wd_sl_fuer_plan"] = _fp
    check(usd is None and ws_["grund"] == "Rechenfehler (ZeroDivisionError)", "Rechenfehler → ohne SL mit Grund, nie Abbruch")
    check(R(None, plan(), ACC, LIQ, [])[0] is None, "Würfel aus → nichts")

    print("3) Takt gegen eine nachgebaute DB")
    DB = {"plaene": [], "upd": [], "konto_fehler": False, "liq": LIQ, "upd_antwort": None}

    def sb_select(t, p):
        if t == "trade_plans":
            return [dict(x) for x in DB["plaene"]]
        if t == "accounts":
            if DB["konto_fehler"]:
                raise RuntimeError("weg")
            return [dict(ACC)]
        return []

    def sb_update(t, f, u):
        DB["upd"].append((t, f, u))
        return DB["upd_antwort"] if DB["upd_antwort"] is not None else [dict(u, id=f["id"][3:])]
    ns.update(sb_select=sb_select, sb_update=sb_update, _liq_regeln_laden=lambda: DB["liq"], _wd_fruehere_trades=lambda mids: [],
              _wd_sl_wuerfel_lesen=lambda: (std, "db"))
    T = ns["wd_sl_nach_tick"]
    DB["plaene"] = [plan()]
    e = T(JETZT, rnd=Folge(0.59, 0.53))
    t_, f_, u_ = DB["upd"][0] if DB["upd"] else (None, {}, {})
    check(len(DB["upd"]) == 1 and t_ == "trade_plans" and u_.get("master_sl") == 2280 and u_["mt5_baseline"]["wd_sl"]["usd"] == 2280
          and u_["mt5_baseline"]["start_sperre"] == {"art": "x"} and e["gewuerfelt"] == 1,
          "EIN Update: master_sl + mt5_baseline.wd_sl zusammen, andere Baseline-Schlüssel bleiben")
    check(f_ == {"id": "eq.p-1", "status": "eq.planned", "start_um_gestartet_at": "is.null", "started_at": "is.null", "orbit_gesendet_at": "is.null",
                 "mt5_baseline->wd_sl->>grund": "eq.Rückfall ohne Würfel", "updated_at": "eq.2026-11-10T03:50:00.123456+00:00"},
          "Guard: nicht geclaimt/gestartet/gesendet, noch Rückfall, updated_at unverändert (sonst nie halb geändert)")
    DB["upd"].clear()
    T(JETZT, rnd=Folge(0.2))
    check(len(DB["upd"]) == 1 and "master_sl" not in DB["upd"][0][2] and DB["upd"][0][2]["mt5_baseline"]["wd_sl"]["grund"] == "gewürfelt: ohne SL",
          "Stufe ohne SL: nur wd_sl, master_sl unberührt")
    DB["upd"].clear()
    DB["upd_antwort"] = []
    e = T(JETZT, rnd=Folge(0.59, 0.53))
    DB["upd_antwort"] = None
    check(e["uebersprungen"] and "geclaimt" in e["uebersprungen"][0]["grund"] and not e["geaendert"], "Guard griff (Claim dazwischen) → nichts, nächster Takt")
    DB["upd"].clear()
    DB["konto_fehler"] = True
    e = T(JETZT, rnd=Folge(0.59, 0.53))
    DB["konto_fehler"] = False
    check(not DB["upd"] and "nicht lesbar" in e.get("fehler", ""), "Konten nicht lesbar → nichts schreiben (kein Dauer-„ohne SL“ aus einem Lesefehler)")
    DB["liq"] = []
    e = T(JETZT, rnd=Folge(0.59, 0.53))
    DB["liq"] = LIQ
    check(not DB["upd"] and "liq_regeln" in e.get("fehler", ""), "liq_regeln leer → nichts schreiben")
    DB["plaene"] = [plan(updated_at=None)]
    e = T(JETZT, rnd=Folge(0.59, 0.53))
    check(not DB["upd"] and e["uebersprungen"], "ohne updated_at kein sicherer Guard → nicht anfassen")
    DB["plaene"] = [plan(start_um=(JETZT + timedelta(seconds=60)).isoformat()), plan(id="p-2", start_um_gestartet_at="x")]
    e = T(JETZT)
    check(not DB["upd"] and not e["geaendert"], "kurz vor dem Start bzw. geclaimt → nicht anfassen")
    ns["_wd_sl_wuerfel_lesen"] = lambda: (None, "aus")
    DB["plaene"] = [plan()]
    check(T(JETZT) == {"aus": True} and not DB["upd"], "Würfel aus → nichts")
    ns["_wd_sl_wuerfel_lesen"] = lambda: (std, "db")
    DB["plaene"] = [plan(id=f"p-{i}") for i in range(400)]
    rnd = random.Random(20261110)
    e = T(JETZT, rnd=rnd)
    check(len(DB["upd"]) == 400 and 160 <= e["gewuerfelt"] <= 240 and e["gewuerfelt"] + e["ohne"] == 400,
          f"Verteilung wie WS1: ≈ 50 % mit SL ({e['gewuerfelt']} von 400)")

    DB["upd"].clear()
    DB["plaene"] = [plan(mt5_baseline={"wd_sl": dict(RUECK), "sl_lauf_at": (JETZT - timedelta(seconds=20)).isoformat()})]
    e = T(JETZT, rnd=Folge(0.59, 0.53))
    check(not DB["upd"] and not e["geaendert"], "Takt: Plan mit frischer Sperr-Marke bleibt unberührt")

    print("4) Einbau + Annahmen am PC-Tab")
    check("_wd_sl_nach_takt()                    # SL1" in src and "random.uniform(*WD_SL_NACH_TAKT_S)" in src,
          "Takt in ap_loop, Abstand gestreut (Jitter-Regel)")
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"async function suClaimSetzen\(planId, art, guard, startUm\)\{(.*?)\n  \}", html, re.S)
    check(bool(m) and ".is('start_um_gestartet_at', null)" in m.group(1) and "select('*')" in m.group(1),
          "Claim im Tab nur auf start_um_gestartet_at null und mit frischer Zeile (select *)")
    k = html[html.index("async function tpOrbitStartenKern("):][:6000]
    check("supabase.from('trade_plans').select('*').eq('id', plan.id).maybeSingle()" in k, "Orbit-Start liest den Plan vor der Order frisch aus der DB")
    i = html.index("const { data, error: eClaim } = await suClaimSetzen(plan.id")
    check("tradePlans[i] = rowToPlan(data[0])" in html[i:i + 800], "nach dem Claim ersetzt der Tab den Plan durch die Claim-Zeile (Echo-Start)")
    j = src.index("if sl_gewuerfelt:")
    check('_ws.get("regel") == "sl_wuerfel"' in src[j - 900:j] and 'upd.pop("master_sl", None)' in src[j:j + 200],
          "PATCH /admin/wd-plaene (Tab-Nachziehen) löscht einen nachgewürfelten master_sl nie (wd_sl.regel sl_wuerfel)")

    print("5) PC-Tab: Sperr-Marke vor dem Senden (Prüfer S2 MUSS, 10.11.2026)")
    i0 = html.index("async function tpOrbitStartenKern(")
    k_ende = html.index("\n  async function ", i0 + 10)
    kern = html[i0:k_ende]
    # das frühere _tpOrbitLaeuft der Topstep-Probe „nur lesen“ (scharf:false, keine Order) zählt nicht — geprüft wird der scharfe Weg
    a = kern.find("await wdSlStartSperre(plan)")
    b = kern.find("_tpOrbitLaeuft = true", a)
    probe = kern.find("scharf: false")
    check(0 < probe < kern.find("slaveBereitPruefen(plan)") < a < b < kern.find("const _tvBody") < kern.find("window.mtcApi('tsx-konto'", b)
          and kern.count("scharf: true") == kern[a:].count("scharf: true") >= 1
          and "sl = sp.sl" in kern[a:b] and "_nichtGesendet: true" in kern[a:b],
          "Orbit/Topstep: Sperre nach allen Vorprüfungen, vor _tpOrbitLaeuft und vor jedem Senden; SL aus der frischen Zeile; Fehler = nichts gesendet")
    j0 = html.index("async function tpPreflightMt5V2(plan)")
    v2 = html[j0:html.index("\n  // REIN RECHNEND (window._mt5OrderWiederholen", j0)]
    a2 = v2.find("await wdSlStartSperre(plan)")
    check(0 < a2 < v2.find("sfSendetHier(plan.id)") < v2.find("master-order?file=") and "po.sl_usd = sp.sl > 0 ? sp.sl : null" in v2[a2:a2 + 1200],
          "Echo V2: Sperre vor sfSendetHier/master-order, SL der Order aus der frischen Zeile")
    check("if(planWdSlUsd(plan) > 0 || wdSlIstRueckfall(plan)) delete upd.master_sl; else upd.master_sl = null" in html,
          "Order-Panel speichern: Rückfall im Speicher → master_sl nicht anfassen (Hinweis S2)")
    jsc = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
    if os.path.exists(jsc):
        f0 = html.index("  const WD_SL_RUECKFALL_GRUND = ")
        fn = html[f0:html.index("  window._wdSlStartSperre = ", f0)]
        js = """
var LOG = [], DBROW = null, MARKE_FEHLT = false, tradePlans = [{ id: 'p-1', masterSl: null }];
function tpIstWdPlan(p){ return !!p.wd }
async function baselinePatch(id, patch, st){ LOG.push(['marke', id, Object.keys(patch).join(','), st]); if(MARKE_FEHLT) throw new Error('rpc weg'); return {} }
var supabase = { from: function(t){ return { select: function(){ return { eq: function(){ return { maybeSingle: async function(){ LOG.push(['lesen']); return { data: DBROW, error: null } } } } } } } } };
function rowToPlan(r){ return { id: r.id, status: r.status, masterSl: r.master_sl, mt5Baseline: r.mt5_baseline } }
""" + fn + """
var R = { grund: 'Rückfall ohne Würfel' }, erg = {};
(async function(){
  erg.nichtWd = await wdSlStartSperre({ id: 'p-1', wd: false, mt5Baseline: { wd_sl: R } });
  erg.gewuerfelt = await wdSlStartSperre({ id: 'p-1', wd: true, mt5Baseline: { wd_sl: { grund: 'gewürfelt: ohne SL' } } });
  erg.logLeer = LOG.length;
  DBROW = { id: 'p-1', status: 'planned', master_sl: 2280, mt5_baseline: { wd_sl: { usd: 2280 } } };
  erg.rueck = await wdSlStartSperre({ id: 'p-1', wd: true, mt5Baseline: { wd_sl: R } });
  erg.log = LOG.slice(); erg.tp = tradePlans[0].masterSl;
  LOG = []; MARKE_FEHLT = true;
  erg.markeWeg = await wdSlStartSperre({ id: 'p-1', wd: true, mt5Baseline: { wd_sl: R } }); erg.logMarkeWeg = LOG.slice();
  MARKE_FEHLT = false; DBROW = { id: 'p-1', status: 'open', master_sl: 2280, mt5_baseline: {} };
  erg.offen = await wdSlStartSperre({ id: 'p-1', wd: true, mt5Baseline: { wd_sl: R } });
  erg.rueckOhne = await (async function(){ DBROW = { id: 'p-1', status: 'planned', master_sl: null, mt5_baseline: {} }; return wdSlStartSperre({ id: 'p-1', wd: true, mt5Baseline: { wd_sl: R } }) })();
  print(JSON.stringify(erg, function(k, v){ return k === 'plan' ? undefined : v }));
})().catch(function(e){ print('FEHLER ' + e) });
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as t:
            t.write(js)
        aus = subprocess.run([jsc, t.name], capture_output=True, text=True, timeout=30).stdout.strip()
        os.unlink(t.name)
        try:
            e = json.loads(aus.splitlines()[-1])
        except Exception:
            e = {}
            print("    jsc:", aus[:300])
        check(e.get("nichtWd", {}).get("ohneSperre") and e.get("gewuerfelt", {}).get("ohneSperre") and e.get("logLeer") == 0,
              "JS wdSlStartSperre: kein WD bzw. schon gewürfelt → keine Marke, kein Lesen (alle anderen Starts unverändert)")
        check(e.get("rueck", {}).get("ok") and e["rueck"].get("sl") == 2280 and e.get("tp") == 2280
              and e.get("log") == [["marke", "p-1", "sl_lauf_at", "planned"], ["lesen"]],
              "JS: Rückfall-WD → erst Marke (nur planned), DANN frisch lesen; SL 2.280 aus der DB, Plan im Speicher ersetzt")
        check(e.get("markeWeg", {}).get("ok") is False and e.get("logMarkeWeg") == [["marke", "p-1", "sl_lauf_at", "planned"]],
              "JS: Marke scheitert → nicht senden, nichts gelesen")
        check(e.get("offen", {}).get("ok") is False and e.get("rueckOhne", {}).get("ok") and e["rueckOhne"].get("sl") == 0,
              "JS: Plan nicht mehr geplant → nicht senden; nicht nachgewürfelt → Order ohne SL wie bisher")
    else:
        print("  · jsc nicht vorhanden — JS-Funktionstest übersprungen")

    print()
    print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
