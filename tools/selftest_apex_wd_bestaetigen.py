#!/usr/bin/env python3
"""Selbsttest APEX-WD BESTÄTIGEN (02.11.2026). Rein rechnend, ohne Netz, liest app.py, prophos.html und die SQL-Datei als Text.
Aufruf: python3 tools/selftest_apex_wd_bestaetigen.py"""
import os, re, sys
from datetime import datetime, timedelta, timezone
W = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
lies = lambda n: open(os.path.join(W, n), encoding="utf-8").read()
app, html, sql = lies("app.py"), lies("prophos.html"), lies("sql/2026-11-02_apex_wd_bestaetigen.sql")
fehler = 0
def ok(b, t):
    global fehler
    print(("ok   " if b else "FEHL ") + t); fehler += 0 if b else 1
def fn(n):
    i = app.index(f"def {n}("); return app[i:app.index("\n\n\n", i)]
ns = {"HEDGE_ARTEN": ("apex", "tradeify_final"), "re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta}
for n in ("hf_basis", "hf_ist_wd", "hf_wd_sichtbar", "wd_ist_recoverer_plan", "alarm_wd_bestaetigen", "_alarm_ts"):
    exec(fn(n), ns)
b0, b1 = ns["hf_basis"]([]), ns["hf_basis"](["apex"])
ok("or" not in b0 and b0["mt5_baseline->>hedge_art"] == "in.(apex,tradeify_final)", "Schalter leer: Filter wie vor dem Gate")
ok("winning_day.is.true,notes.ilike.*Winning-Day-Farmer*,master_firm.ilike.*apex*" in b1["or"], "Gate an: nur Farmer-WD der Firma")
w = {"winning_day": True, "notes": "Winning-Day-Farmer", "master_firm": "Apex Trader"}
ok(ns["hf_ist_wd"](w, ["apex"]), "Apex-Farmer-WD zählt")
for firma in ("Tradeify", "Topstep", "Lucid", "FTMO Futures"):
    ok(not ns["hf_ist_wd"](dict(w, master_firm=firma), ["apex"]), f"{firma} nie")
ok(not ns["hf_ist_wd"](dict(w, notes="Hand"), ["apex"]), "Hand-WD nie")
ok(not ns["hf_ist_wd"](dict(w, art="apex"), ["apex"]), "Hedge-Art bleibt im alten Weg")
ok(ns["hf_wd_sichtbar"](dict(w, user_id="ex"), ["apex"], {"emin"}), "ADMIN_EXCLUDE ohne Gruppe: steht in der Liste")
ok(not ns["hf_wd_sichtbar"](dict(w, user_id="emin"), ["apex"], {"emin"}), "Verwalter-Gruppe: nicht in der Liste, wartet auch nicht")
j = datetime(2026, 11, 2, 6, tzinfo=timezone.utc)
p = dict(w, id="p", user_id="u", status="planned", start_um=(j - timedelta(minutes=1)).isoformat())
a = ns["alarm_wd_bestaetigen"]
ok(len(a([p], ["apex"], {"u": "M"}, j)) == 1, "⚪ ab Startzeit")
ok(a([dict(p, start_um=(j + timedelta(minutes=5)).isoformat())], ["apex"], {}, j) == [], "kein ⚪ vor der Startzeit")
ok(a([dict(p, hedge_freigabe_at="x")], ["apex"], {}, j) == [], "kein ⚪ nach Bestätigung")
# Text-Riegel: Startwege im Tab
for f, marke in (("async function tpOrbitStartenKern", "fern.melde({ ok:false, msg: _wdFehlt })"), ("async function tpJetztStarten", "atToast(_wdFehlt")):
    i = html.index(f); ok(marke in html[i:i + 1400], f"{f}: Hand-Start gesperrt")
ok("if(tpWdWartetAufBestaetigung(p)) return 'wartet auf deine Bestätigung" in html, "Start-Prädikat kennt das Gate")
ok("!tpBestaetigenAusgenommen() && tpBestaetigenFirmen()" in html, "Tab kennt die Verwalter-Ausnahme")
i = html.index("const tpWdWartetAufBestaetigung = p =>"); t = html[i:html.index("  /* Verwalter-Gruppen sind ausgenommen", i)]
ok("p.winningDay !== true" in t and "start_sperre" not in t, "Tab prüft winning_day, Netz-Marke hält nicht")
ok("trade_plans_a0_hedge_freigabe" in lies("sql/2026-11-02_apex_wd_bestaetigen_rueckbau.sql"), "Rückbau-Datei da")
ok("hedge_freigabe_at,mt5_baseline')" in html and "!!p.hedgeFreigabeAt !== !!r.hedge_freigabe_at" in html, "Abgleich lädt die Bestätigung nach")
# SQL
ok("wd_bestaetigen_ich_ausgenommen" in sql and "grant execute on function public.wd_bestaetigen_ich_ausgenommen() to authenticated" in sql, "RPC für den Tab angelegt")
z = sql[sql.index("APEX-WD BESTÄTIGEN (02.11.2026): nur Netz"):sql.index("ss := new.mt5_baseline->'start_sperre'")]
ok("start_um" not in z, "WD-Zweig schiebt start_um nicht")
ok("start_claim_art" in z, "Verbrauchs-Claims gehen durch")
print("OK" if not fehler else f"{fehler} FEHLER"); sys.exit(1 if fehler else 0)
