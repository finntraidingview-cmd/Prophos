#!/usr/bin/env python3
"""Selbsttest RC4 (Finn 12.11.2026 ~20:00 Dubai: „Nein, automatisch.“ — Recovery-/Ausgleichs-WD nicht mehr einzeln bestätigen; überholt das „yes“ vom 03.11.).
Prüft die echten Funktionen aus app.py (hf_basis, hf_ist_wd, hf_zeile_fuer, alarm_wd_bestaetigen) und aus prophos.html (tpWdWartetAufBestaetigung in
JavaScriptCore), die Marke wd_ausgleich im POST /admin/wd-plaene (bleibt, nur ohne Bestätigung) und die SQL-Datei des Claim-Riegels.

Aufruf:  python3 tools/selftest_rc4_ausgleich_automatisch.py"""
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone, timedelta

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
sql = open(os.path.join(W, "sql", "2026-11-12_rc4_ausgleich_automatisch.sql"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


def fn(n):
    m = re.search(r"^def " + re.escape(n) + r"\(.*?(?=^\S)", app, re.S | re.M)
    return m.group(0)


ns = {"HEDGE_ARTEN": ("apex", "tradeify_final"), "re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta}
for n in ("hf_basis", "hf_ist_wd", "hf_wd_sichtbar", "hf_zeile_fuer", "wd_ist_recoverer_plan", "alarm_wd_bestaetigen", "_alarm_ts"):
    exec(fn(n), ns)

check(re.search(r"^TRADEIFY_AUSGLEICH_BESTAETIGEN = False", app, re.M) is not None and "„Nein, automatisch.“" in app, "Schalter aus, Finns Satz im Kommentar")
b0, b1 = ns["hf_basis"]([]), ns["hf_basis"](["apex"])
check("wd_ausgleich" not in b0["or"] and "wd_ausgleich" not in b1["or"], f"„Zu bestätigen“-Filter ohne Ausgleich ({b0['or'][:60]} …)")
check("hedge_art.in.(apex,tradeify_final)" in b0["or"] and "winning_day.is.true" in b1["or"], "Hedge-Arten und Apex-Liste bleiben im Filter")

wd = {"winning_day": True, "notes": "Winning-Day-Farmer", "master_firm": "Tradeify", "master_symbol": "MNQZ6"}
aus = dict(wd, aus="true")
check(not ns["hf_ist_wd"](aus, []) and not ns["hf_ist_wd"](aus, ["tradeify"]), "Ausgleich nie bestätigungspflichtig (auch wenn die Firma in der Liste steht)")
apex = dict(wd, master_firm="Apex Trader")
check(ns["hf_ist_wd"](apex, ["apex"]), "normaler Apex-WD mit Liste: weiter bestätigen")
check(not ns["hf_ist_wd"](dict(apex, wd_recoverer="true"), ["apex"]), "Recoverer mit Marke: nie")
check(not ns["hf_ist_wd"](dict(apex, master_symbol="NQZ6"), ["apex"]), "Recoverer ohne Marke (Apex-WD auf NQ): nie")
check(ns["hf_ist_wd"](dict(apex, master_symbol="NQZ6", wd_recoverer="false"), ["apex"]), "Apex auf NQ mit Marke false: normaler WD, bestätigen")
check(not ns["hf_ist_wd"](dict(apex, art="apex"), ["apex"]), "Hedge-Art bleibt im eigenen Weg")
z = ns["hf_zeile_fuer"]
check(not z(dict(aus, user_id="g1"), {"g1"}, set(), [], set()), "Verwalter: Ausgleich seiner Gruppe nicht mehr in der Liste")
check(z(dict(wd, user_id="g1", art="apex"), {"g1"}, set(), [], set()), "Verwalter: Orbit-Prio-2-Hedge seiner Gruppe bleibt")
check(not z(dict(aus, user_id="ex"), None, {"ex"}, [], set()), "Admin: Ausgleich einer fremden Gruppe nicht mehr in der Liste")
check(z(dict(wd, user_id="ht"), None, set(), [], set()), "Admin: HT-Zeilen wie bisher")
j = datetime(2026, 11, 12, 6, tzinfo=timezone.utc)
check(ns["alarm_wd_bestaetigen"]([dict(aus, id="p", user_id="u", status="planned", start_um=(j - timedelta(minutes=1)).isoformat())], [], {}, j) == [],
      "keine Bestätigungs-Meldung mehr für Ausgleich")

# POST /admin/wd-plaene: Marke bleibt (kein SL-Würfel), ohne Bestätigung
i = app.index('@app.route("/admin/wd-plaene"')
post = app[i:app.index("\n@app.route", i + 10)]
check('if (r or {}).get("wd_ausgleich") is True:\n                    body["mt5_baseline"] = dict(body.get("mt5_baseline") or {}, wd_ausgleich=True)' in post,
      "Marke wd_ausgleich wird weiter gesetzt — unabhängig vom Schalter")
check('(r or {}).get("wd_ausgleich") is True):' in post and '"Ausgleich — kein Würfel"' in post, "Ausgleich würfelt weiter keinen SL")
tick = fn("alarm_tick")
check('or str(r.get("aus") or "").lower() == "true"' not in tick, "Alarm-Takt: keine Ausnahme mehr für Ausgleich")

# Frontend: tpWdWartetAufBestaetigung in JavaScriptCore
i = html.index("  const tpWdWartetAufBestaetigung = p =>")
code = html[i:html.index("  /* Verwalter-Gruppen sind ausgenommen", i)]
pi = html.index("  function planIstRecoverer(p){")
rec = html[pi:html.index("\n  }\n", pi) + 4]
js = f"""
var window = {{}};
var _wdRegeln = {{ row: {{ bestaetigen_firmen: LISTE_ }} }}, LISTE_ = null;
function tpBestaetigenAusgenommen(){{ return false }}
function tpIstFarmerPlan(p){{ return /Winning-Day-Farmer/.test(String((p && p.notes) || '')) }}
function tpBestaetigenFirmen(){{ var l = _wdRegeln.row.bestaetigen_firmen; return (Array.isArray(l) ? l : []).map(function(k){{ return String(k).toLowerCase() }}) }}
{rec}
{code}
var basis = {{ status: 'planned', winningDay: true, notes: 'Winning-Day-Farmer', masterFirm: 'Tradeify', masterSymbol: 'MNQZ6', mt5Baseline: {{}} }};
function mit(o){{ var x = {{}}; for(var k in basis) x[k] = basis[k]; for(var k2 in o) x[k2] = o[k2]; return x }}
var r = {{}};
_wdRegeln.row.bestaetigen_firmen = [];
r.ausLeer = tpWdWartetAufBestaetigung(mit({{ mt5Baseline: {{ wd_ausgleich: true }} }}));
_wdRegeln.row.bestaetigen_firmen = ['tradeify', 'lucid', 'apex'];
r.ausListe = tpWdWartetAufBestaetigung(mit({{ mt5Baseline: {{ wd_ausgleich: true }} }}));
r.lucidAus = tpWdWartetAufBestaetigung(mit({{ masterFirm: 'Lucid Trading', mt5Baseline: {{ wd_ausgleich: true }} }}));
r.recMarke = tpWdWartetAufBestaetigung(mit({{ masterFirm: 'Apex Trader', mt5Baseline: {{ wd_recoverer: true }} }}));
r.recNq = tpWdWartetAufBestaetigung(mit({{ masterFirm: 'Apex Trader', masterSymbol: 'NQZ6' }}));
r.apexNormal = tpWdWartetAufBestaetigung(mit({{ masterFirm: 'Apex Trader' }}));
r.apexFrei = tpWdWartetAufBestaetigung(mit({{ masterFirm: 'Apex Trader', hedgeFreigabeAt: 'x' }}));
print(JSON.stringify(r));
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as d:
    d.write(js)
rr = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d.name], capture_output=True, text=True)
os.unlink(d.name)
try:
    r = json.loads(rr.stdout.strip().splitlines()[-1])
except Exception:
    r = {}
    check(False, f"jsc lief nicht: {rr.stderr[:300]} {rr.stdout[:300]}")
if r:
    check(r["ausLeer"] is False and r["ausListe"] is False and r["lucidAus"] is False, f"Tab: Ausgleich (Tradeify/Lucid) wartet nie, auch mit Liste ({r})")
    check(r["recMarke"] is False and r["recNq"] is False, "Tab: Recoverer (Marke oder Apex-NQ) wartet nie")
    check(r["apexNormal"] is True and r["apexFrei"] is False, "Tab: normaler Apex-WD der Liste wartet weiter, bestätigt nicht")
check("|| String(z.aus || '').toLowerCase() === 'true')" not in html, "WD-Übersicht: Ausgleich nicht mehr in „Zu bestätigen“")
check("'Apex-WD — startet erst nach deinem „Bestätigen\" · Zeiten Dubai'" in html, "Listen-Text ohne Ausgleich")

# SQL: Claim-Riegel
check("create or replace function public.trade_plans_a0_hedge_freigabe()" in sql, "SQL ersetzt den Claim-Riegel")
check("and coalesce(new.mt5_baseline->>'wd_ausgleich', '') <> 'true'" in sql and "or (coalesce(new.mt5_baseline->>'wd_ausgleich', '') = 'true'" not in sql,
      "SQL: Ausgleich nicht mehr gesperrt")
check("coalesce(new.mt5_baseline->>'wd_recoverer', '') <> 'true'" in sql and "~* '^NQ'" in sql, "SQL: Recoverer (Marke oder Apex-NQ) nicht gesperrt")
check("public.wd_bestaetigen_noetig(new.winning_day, new.master_firm, new.user_id)" in sql and "not in ('apex', 'tradeify_final')" in sql,
      "SQL: Apex-Liste und Hedge-Arten unverändert")

print()
print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER")
raise SystemExit(1 if fehler else 0)
