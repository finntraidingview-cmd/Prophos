#!/usr/bin/env python3
"""Selbsttest Lots-Deckel (Finn 02.11.2026: > 16 Fusion-Lots starten erst nach OK). Rechnet die echten Funktionen aus app.py und prophos.html, ohne Netz und ohne DB.

Aufruf:  python3 tools/selftest_lots_deckel.py"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
app = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
sql = open(os.path.join(WURZEL, "sql", "2026-11-02_lots_deckel.sql"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = {"re": re}
i = app.index("LOTS_DECKEL = 16.0")
exec(app[i:app.index('@app.route("/admin/auto-plan/lots-ok"')], ns)
L, G, D, A = ns["plan_fusion_lots"], ns["lots_ok_gilt"], ns["lots_deckel_lots"], ns["alarm_lots_deckel"]
P = {"id": "p1", "user_id": "u1", "status": "planned", "route": "tvv2", "hedge_eur": 400, "master_contracts": 10, "multiplier": 3.2, "slave_risk": 450, "master_risk": 1500, "master_symbol": "MNQZ6",
     "master_firm": "Apex", "master_name": "Marc"}
check(L(P) == 32.0 and D(P) == 32.0, "Vorfall Marc: 10 × 3,2 = 32 Lot → gesperrt")
check(D(dict(P, master_contracts=5)) is None and L(dict(P, master_contracts=5)) == 16.0, "genau 16 Lot gehen")
check(D(dict(P, multiplier=3.21, master_contracts=5)) == 16.05, "16,05 Lot sind gesperrt")
check(L(dict(P, hedge_eur=0)) is None and L(dict(P, route="mt5v2")) is None, "ohne Fusion-Hedge kein Deckel")
check(L(dict(P, route="mt5", hedge_eur=0, slave_firm="Fusion Markets")) == 32.0 and L(dict(P, route="mt5", hedge_eur=0, slave_firm="X")) is None, "Echo mit Fusion-Hedge zählt, Echo ohne nicht")
check(L(dict(P, route="tsv2")) == 32.0, "Topstep mit Hedge zählt")
ok = ns["lots_ok_wert"](P)
check(G(P, ok) and D(dict(P, lots_ok=ok)) is None, "OK gibt genau diesen Stand frei")
for feld, wert in (("master_contracts", 11), ("multiplier", 3.3), ("slave_risk", 500), ("master_risk", 1400), ("master_symbol", "NQZ6")):
    check(not G(dict(P, **{feld: wert}), ok) and D(dict(P, **{feld: wert}, lots_ok=ok)) is not None, f"OK gilt nicht mehr, wenn sich {feld} ändert")
check(D(dict(P, master_contracts=3, multiplier=1, lots_sperre={"lots": 21.2})) == 21.2, "Meldung des Tabs zählt, auch wenn Kontrakte × Multiplikator klein aussieht")
check(not G(P, None) and not G(P, "x"), "kein OK gilt als kein OK")
ev = A([P, dict(P, id="p2", master_contracts=1), dict(P, id="p3", start_um_gestartet_at="x")], {"u1": "Marc"})
check(len(ev) == 1 and ev[0][1] == 2 and ev[0][2] == "lots_deckel" and "32" in ev[0][3] and "OK" in ev[0][4], "Alarm einmal für den gesperrten Plan, keiner für kleine oder geclaimte")

# Einbau: vor dem Puls-Auftrag, an allen Start-Wegen, DB-Netz
su = html[html.index("function suStartetNichtWeil("):]
check(su[:su.index("suUnbestaetigt(p)")].count("tpLotsDeckelFehlt(p)") == 1, "Tab: Selbst-Start prüft vor dem Claim")
best = html[html.index("async function tpWdBestaetigungFehlt("):][:200]
check("tpLotsDeckelFrisch(plan)" in best and html.count("await tpWdBestaetigungFehlt(plan)") >= 2, "Tab: Hand-, Fern- und Neu-Start über dieselbe Sperre, Stand frisch aus der DB")
kern = html[html.index("async function hedgeSoloOeffnenKern("):]
check("const lotsSoll = hedgeLotsSoll(plan, kt, ppl)" in kern and "tpLotsDeckelFrisch(plan)" in kern[:kern.index("notfallOpen")], "Hedge: eine Lots-Rechnung, letzte Linie vor dem Open")
check("before update of start_um_gestartet_at" in sql and "lots <= 16" in sql and "coalesce(new.start_claim_art, 'start') <> 'start'" in sql, "SQL: Netz am Claim, 16 geht, Verbrauchs-Claims gehen durch")
check("[data-tpl-lotsok]" in html and "/lots-ok" in html, "Knopf OK in Braucht dich, im Nur-Lesen-Riegel eingetragen")
route = app[app.index("def admin_auto_plan_lots_ok"):app.index('@app.route("/alarm/lots-deckel"')]
check("_planer_schreib_gate()" in route and "_admin_voll()" in route and '"von"' not in route and "von=von" in route and '"at"' not in route and "at=jetzt.isoformat()" in route, "OK nur für Admins, speichert wer und wann")
check("hedge_freigabe_at" not in route, "OK setzt keine Freigabe, Apex-Bestätigung bleibt eigener Schritt")

if shutil.which("osascript"):
    def fn(name, anfang="function "):
        i = html.index(anfang + name)
        e = html.index("\n  }\n", i) + 5
        return html[i:e]
    a = html.index("  const HEDGE_LOTS_DECKEL = 16")
    code = fn("hedgeLotsSoll") + html[a:html.index("  const tpLotsDeckelText =", a)]
    test = """function run(){
var window = {}; var hedgeMultAusRisiko = function(plan){ return plan.frisch ? { lots: plan.frisch } : null };
function hedgePplFuer(s){ return /^NQ/.test(s) ? 20 : 2 } function tpOrbitWerte(p){ return { symbol: p.masterSymbol } }
""" + code + """
var P = { route: 'tvv2', hedgeEur: 400, masterContracts: 10, multiplier: 3.2, slaveRisk: 450, masterRisk: 1500, masterSymbol: 'MNQZ6' };
function mit(o, p){ var r = {}, k; for(k in o) r[k] = o[k]; for(k in p) r[k] = p[k]; return r }
var OK = { kt: 10, mult: 3.2, sr: 450, mr: 1500, sym: 'MNQZ6' };
return JSON.stringify({ lots: tpFusionLots(P), gesperrt: tpLotsDeckelFehlt(P), g16: tpLotsDeckelFehlt(mit(P, {masterContracts: 5})), frisch: tpLotsDeckelFehlt(mit(P, {masterContracts: 3, multiplier: 1, frisch: 21.2})),
  ok: tpLotsDeckelFehlt(mit(P, {mt5Baseline: {lots_ok: OK}})), okKt: tpLotsDeckelFehlt(mit(P, {masterContracts: 11, mt5Baseline: {lots_ok: OK}})), okMult: tpLotsDeckelFehlt(mit(P, {multiplier: 3.3, mt5Baseline: {lots_ok: OK}})),
  okNull: tpLotsDeckelFehlt(mit(P, {slaveRisk: 0, masterRisk: 0, mt5Baseline: {lots_ok: mit(OK, {sr: null, mr: null})}})), okSym: tpLotsDeckelFehlt(mit(P, {mt5Baseline: {lots_ok: mit(OK, {sym: ''})}})),
  ohneHedge: tpFusionLots(mit(P, {hedgeEur: 0})), echo: tpFusionLots({ route: 'mt5', slaveFirm: 'Fusion', masterContracts: 10, multiplier: 3.2 }) });
}"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(test)
    try:
        aus = subprocess.run(["osascript", "-l", "JavaScript", f.name], capture_output=True, text=True, timeout=30)
    finally:
        os.unlink(f.name)
    check(aus.returncode == 0, "Tab-Rechnung läuft (" + aus.stderr[:160] + ")")
    if aus.returncode == 0:
        r = json.loads(aus.stdout)
        check(r["lots"] == 32 and r["gesperrt"] is True and r["g16"] is False, "Tab: 32 Lot gesperrt, 16 Lot frei")
        check(r["frisch"] is True, "Tab: nimmt denselben Wert wie das Open (Risiko vor multiplier)")
        check(r["ok"] is False and r["okKt"] is True and r["okMult"] is True, "Tab: OK gilt, bei geänderten Werten nicht mehr")
        check(r["okNull"] is False and r["okSym"] is False, "Tab: leer und 0 gleich, Plan ohne Symbol hängt nicht")
        check(r["ohneHedge"] is None and r["echo"] == 32, "Tab: ohne Hedge kein Deckel, Echo mit Fusion zählt")

print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
