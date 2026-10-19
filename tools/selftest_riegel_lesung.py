#!/usr/bin/env python3
"""Selbsttest RIEGEL-LESUNG: review sperrt die Gegenrichtung nur, solange die Endlesung fehlt (Finn 19.10.2026 23:55 Dubai: „Solange der
beendete Trade nicht vom Auge gelesen wurde, darf kein Trade in Gegenrichtung stattfinden. Die Lesung muss ERFOLGREICH sein … Ich muss
nicht abhaken"). Anlass: abhaken_auto aus → 199 Umplanungen „noch nicht nachgelesen" an einem Tag (Marc fe1c95ea 58×, Mike c27bef98).
Aufruf:  python3 tools/selftest_riegel_lesung.py
Prueft: (1) rkPlanGelesen (echt per osascript/JXA): review gelesen = frei, review ungelesen = gesperrt — je Route, mit den Feldern, die
Endlesung (final.quelle 'puls' + balance_end), Reader-Flach-Beweis (final.balance_quelle 'reader' + balance_end, Finn 20.10.2026) und
Echo-Nachlesung (bal_nach.ok + balance) wirklich schreiben; Folgetrade-Balance nie; open nie „gelesen";
(2) v2RichtungKonflikt holt die Felder frisch aus der DB und zählt review nur ungelesen; (3) SQL-Datei: prophos_plan_gelesen mit derselben
Definition, beide Riegel-Funktionen nutzen sie, open bleibt unverändert, 72 h bleiben, Rückweg genannt; (4) app.py /richtung/frei ruft
weiter die DB-Funktion (fail-closed). Ohne Netz, Platzhalter-Werte."""
import json
import os
import re
import shutil
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
APP = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
SQL = open(os.path.join(WURZEL, "sql", "2026-10-19_gegenrichtung_review_gelesen.sql"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


# (1) rkPlanGelesen echt ausführen
m = re.search(r"  function rkPlanGelesen\(status, route, endedAt, masterPl, fin, bn\)\{\n.*?\n  \}", HTML, re.S)
check(bool(m), "rkPlanGelesen gefunden")
PULS = {"quelle": "puls", "balance_end": 147920.7, "today_pnl": -2079.3}
DEMO = {"quelle": "demo", "balance_end": 147920.7, "puls_fehler": "tabelle_unklar"}      # Balance ohne Herkunft, Endlesung gescheitert
READER = {"quelle": "demo", "balance_quelle": "reader", "balance_end": 147920.7, "balance_at": "2026-10-19T15:28:00Z"}   # Flach-Beweis des Readers
FOLGE = {"quelle": "demo", "balance_quelle": "folgetrade", "balance_end": 147920.7}   # Balance aus dem Folgetrade, kein Flach-Beweis
LEVEL = {"quelle": "level", "today_pnl": 400}
ECHO_FIN = {"master_balance": 105089.36, "closed_tickets": [1]}
BN_OK = {"ok": True, "balance": 105089.36, "quelle": "nachlesung"}
BN_NEIN = {"ok": False, "code": "ipc_timeout", "msg": "MT5 antwortet nicht"}
FAELLE = [
    # (Name, Argumente, erwartet)
    ("review Orbit V2 gelesen (quelle puls + balance_end) = frei", ["review", "tvv2", "2026-10-19T19:20:00Z", -1524.3, PULS, None], True),
    ("review Orbit V2 ungelesen (quelle demo, Balance ohne Herkunft) = gesperrt", ["review", "tvv2", "2026-10-19T19:20:00Z", -1524.3, DEMO, None], False),
    ("review Orbit V2 Reader-Balance mit Flach-Beweis (Finn 20.10.) = frei", ["review", "tvv2", "2026-10-19T19:20:00Z", -2079.3, READER, None], True),
    ("review Orbit V2 Reader-Balance ohne Zahl = gesperrt", ["review", "tvv2", "2026-10-19T19:20:00Z", -2079.3, dict(READER, balance_end=None), None], False),
    ("review Orbit V2 Balance aus Folgetrade (kein Flach-Beweis) = gesperrt", ["review", "tvv2", "2026-10-19T19:20:00Z", -2079.3, FOLGE, None], False),
    ("review TopstepX Reader-Balance = frei", ["review", "tsv2", "2026-10-19T19:20:00Z", 500, READER, None], True),
    ("review Orbit V2 ungelesen (quelle level, keine Balance) = gesperrt", ["review", "tvv2", "2026-10-19T19:20:00Z", 400, LEVEL, None], False),
    ("review Orbit V2 ohne mt5_baseline (Stand UNBEKANNT) = gesperrt", ["review", "tvv2", "2026-10-19T19:20:00Z", 400, None, None], False),
    ("review Orbit V2 gelesen, aber master_pl fehlt = gesperrt", ["review", "tvv2", "2026-10-19T19:20:00Z", None, PULS, None], False),
    ("review Orbit V2 gelesen, aber ended_at fehlt = gesperrt", ["review", "tvv2", None, 5, PULS, None], False),
    ("review TopstepX gelesen = frei", ["review", "tsv2", "2026-10-19T19:20:00Z", 3510, dict(PULS, plattform="tsx"), None], True),
    ("review Echo (mt5v2) Nachlesung ok = frei", ["review", "mt5v2", "2026-10-19T11:21:00Z", 350.4, ECHO_FIN, BN_OK], True),
    ("review Echo (mt5) Nachlesung ok = frei", ["review", "mt5", "2026-10-19T11:21:00Z", 350.4, ECHO_FIN, BN_OK], True),
    ("review Echo Nachlesung gescheitert (ok false) = gesperrt", ["review", "mt5v2", "2026-10-19T11:21:00Z", 350.4, ECHO_FIN, BN_NEIN], False),
    ("review Echo ohne final (Copier-Schluss fehlt) = gesperrt", ["review", "mt5v2", "2026-10-19T11:21:00Z", 350.4, None, BN_OK], False),
    ("review Echo bal_nach ohne Balance = gesperrt", ["review", "mt5v2", "2026-10-19T11:21:00Z", 350.4, ECHO_FIN, {"ok": True}], False),
    ("review Orbit V3 (tvplus) nie gelesen = gesperrt wie bisher", ["review", "tvplus", "2026-10-19T19:20:00Z", 3510, PULS, BN_OK], False),
    ('open nie „gelesen" (läuft)', ["open", "tvv2", None, None, PULS, None], False),
    ('completed nie „gelesen" (zählt ohnehin nicht)', ["completed", "tvv2", "2026-10-19T19:20:00Z", 5, PULS, None], False),
]
if m and shutil.which("osascript"):
    js = (m.group(0) + "\nvar F = " + json.dumps([f[1] for f in FAELLE]) + ";\n"
          "JSON.stringify(F.map(function(a){ return rkPlanGelesen(a[0], a[1], a[2], a[3], a[4], a[5]) }))")
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], capture_output=True, text=True)
    try:
        v = json.loads(r.stdout.strip())
    except ValueError:
        v = None
    check(isinstance(v, list) and len(v) == len(FAELLE), f"rkPlanGelesen läuft ({(r.stderr or '').strip()[:80]})")
    if isinstance(v, list) and len(v) == len(FAELLE):
        for (name, _, soll), ist in zip(FAELLE, v):
            check(ist is soll, f"rkPlanGelesen: {name} → {ist}")
else:
    print("… osascript fehlt — rkPlanGelesen nur per Text geprüft")
    check("(fin.quelle === 'puls' || fin.balance_quelle === 'reader') && zahl(fin.balance_end)" in (m.group(0) if m else ""), "rkPlanGelesen Orbit: quelle puls oder Reader + balance_end")
    check("bn.ok === true && zahl(bn.balance)" in (m.group(0) if m else ""), "rkPlanGelesen Echo: bal_nach.ok + balance")

# (2) v2RichtungKonflikt: Felder frisch, review nur ungelesen
k = re.search(r"  async function v2RichtungKonflikt\(o\)\{\n.*?\n  \}\n", HTML, re.S)
check(bool(k), "v2RichtungKonflikt gefunden")
K = k.group(0) if k else ""
check("',route,ended_at,master_pl,final:mt5_baseline->final,bal_nach:mt5_baseline->bal_nach'" in K,
      "frische Liste holt route, ended_at, master_pl, final, bal_nach")
check("gelesen: rkPlanGelesen(r.status, r.route, r.ended_at, r.master_pl, r.final, r.bal_nach)" in K, "frische Zeile rechnet gelesen")
# Prüfer S2 (20.10.2026): ein Zeilenkommentar hinter dem Select-String hatte `.in('status', …)` geschluckt → ALLE trade_plans geladen.
# Der Status-Filter muss am Zeilenanfang als Code stehen, in keiner Kommentarzeile.
sel = re.search(r"supabase\.from\('trade_plans'\)\.select\('id,status,richtung,master_firm.*?\n(\s*\.in\('status', \['open', 'review', 'planned'\]\))", K, re.S)
check(bool(sel) and all(not z.lstrip().startswith("//") and "//" not in z.split(".in(")[0] for z in [sel.group(1)]),
      "frischer Select: .in('status', [open, review, planned]) ist Code, nicht Kommentar")
check(not re.search(r"//[^\n]*\.in\('status'", K), "kein .in('status') hinter einem Zeilenkommentar")
check("gelesen: rkPlanGelesen(p.status, p.route, p.endedAt, p.masterPl, p.mt5Baseline && p.mt5Baseline.final, p.mt5Baseline && p.mt5Baseline.bal_nach)" in K,
      "tradePlans-Zeile rechnet gelesen (Popup-Weg)")
check("const zaehlt = rkZaehlt(p.status, p.geclaimt, p.sf) || (p.status === 'review' && !p.gelesen)" in K,
      "review zählt nur ungelesen als laufend")
check("rkSaldoDrehen(plan, k, grundTxt){\n    const alt = plan.richtung" in HTML and "if(k && k.lauf === altSeite) return null" in HTML,
      "rkSaldoDrehen unverändert (Finn 00:02: CFD-Waage und Drehen bleiben)")
check("async function rkRichtungDrehen(plan, k, ziel, zusatz){\n    const { data, error } = await supabase.from('trade_plans').update({ richtung: ziel })" in HTML,
      "rkRichtungDrehen unverändert (kein RPC vor dem Drehen)")

# (3) SQL-Datei
check("create or replace function public.prophos_plan_gelesen(p_plan uuid)" in SQL, "SQL: prophos_plan_gelesen(uuid) boolean")
check(re.search(r"p\.status is distinct from 'review' or p\.ended_at is null or p\.master_pl is null then\s+return false", SQL) is not None,
      "SQL: nur review mit ended_at + master_pl kann gelesen sein")
check("(fin->>'quelle' = 'puls' or fin->>'balance_quelle' = 'reader')" in SQL and "(fin->>'balance_end')::numeric > 0" in SQL,
      "SQL Orbit: final.quelle puls ODER balance_quelle reader (Finn 20.10.), je + balance_end > 0")
check("(fin.quelle === 'puls' || fin.balance_quelle === 'reader') && zahl(fin.balance_end)" in HTML, "JS Orbit: dieselbe Zeile wie SQL (puls oder reader)")
check("bn->>'ok' = 'true'" in SQL and "(bn->>'balance')::numeric > 0" in SQL and "fin is not null and bn is not null" in SQL,
      "SQL Echo: final da + bal_nach.ok + balance > 0")
check(SQL.count("and not (p.status = 'review' and public.prophos_plan_gelesen(p.id))") == 2,
      "SQL: beide Riegel-Funktionen (gegenrichtung_frei + gegenhedge_konflikt) sieben gelesene reviews aus")
check(SQL.count("and p.status in ('open', 'review')") == 2 and SQL.count("interval '72 hours'") == 2, "SQL: open unverändert, 72 h bleiben")
check("create or replace function public.prophos_gegenrichtung_frei(p_plan uuid, p_richtung text default null)" in SQL
      and "create or replace function public.prophos_gegenhedge_konflikt(p_id uuid, p_user uuid, p_firma text, p_richtung text, p_ref timestamptz)" in SQL,
      "SQL: Signaturen wie 2026-10-13 (Trigger/Route rufen sie weiter)")
check("grant execute on function public.prophos_plan_gelesen(uuid) to authenticated, service_role" in SQL, "SQL: grant für Tab + Railway")
check("Rückweg: sql/2026-10-13_gegenrichtung_review.sql" in SQL, "SQL: Rückweg genannt")
check(not re.search(r"\b(create|drop) (trigger|table)\b", SQL), "SQL: keine Trigger/Tabellen angefasst")

# (4) app.py
i = APP.find('@app.route("/richtung/frei", methods=["POST"])')
R = APP[i:i + 3500]
check("rest/v1/rpc/prophos_gegenrichtung_frei" in R and '"frei": erg.get("frei") is True' in R, "/richtung/frei fragt weiter die DB-Funktion, frei nur bei true")
check("REVIEW GELESEN = FREI" in R and "sql/2026-10-19_gegenrichtung_review_gelesen.sql" in R, "/richtung/frei nennt die Regel + SQL-Datei")

print()
if FEHLER:
    print(f"FEHLER ({len(FEHLER)}):")
    for f in FEHLER:
        print("  - " + f)
    sys.exit(1)
print("ALLES GRÜN")
