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
L, G, D, A, SO, OF = ns["plan_fusion_lots"], ns["lots_ok_gilt"], ns["lots_deckel_lots"], ns["alarm_lots_deckel"], ns["lots_deckel_soll"], ns["alarm_lots_stop"]
P = {"id": "p1", "user_id": "u1", "status": "planned", "route": "tvv2", "hedge_eur": 400, "master_contracts": 10, "multiplier": 3.2, "slave_risk": 450, "master_risk": 1500, "master_symbol": "MNQZ6",
     "master_firm": "Apex", "master_name": "Marc"}
W = ns["lots_ok_wert"]
check(L(P) == 32.0 and D(P) == 32.0, "Vorfall Marc: 10 × 3,2 = 32 Lot → gesperrt")
check(D(dict(P, master_contracts=5)) is None and L(dict(P, master_contracts=5)) == 16.0, "genau 16 Lot gehen")
check(D(dict(P, multiplier=3.21, master_contracts=5)) == 16.05, "16,05 Lot sind gesperrt")
check(L(dict(P, hedge_eur=0)) is None and L(dict(P, route="mt5v2")) is None, "ohne Fusion-Hedge kein Deckel")
for r in ("mt5", "tvplus", "dup"):
    check(L(dict(P, route=r, hedge_eur=0, slave_firm="Fusion Markets")) == 32.0 and L(dict(P, route=r, hedge_eur=0, slave_firm="X")) is None, f"{r} mit Fusion zählt, ohne nicht")
check(L(dict(P, route="tsv2")) == 32.0, "Topstep mit Hedge zählt")
check(L(dict(P, route="polar", slave_firm="Fusion")) is None, "Polar läuft nicht auf Fusion (30 Tage: 0 Pläne)")
ok = {"lots": 32.0, "von": "x"}
check(G(P, ok) and D(dict(P, lots_ok=ok)) is None, "OK gibt genau diese Lot-Zahl frei")
check(D(dict(P, master_contracts=11, lots_ok=ok)) == 35.2 and D(dict(P, multiplier=3.3, lots_ok=ok)) == 33.0, "andere Lots: OK gilt nicht mehr")
check(not G(P, None) and not G(P, "x") and not G(P, {"lots": None}), "kein OK gilt als kein OK")
sp = dict(W(dict(P, master_contracts=3, multiplier=1)), lots=21.2)
Q = dict(P, master_contracts=3, multiplier=1, lots_sperre=sp)
check(SO(Q) == 21.2 and D(Q) == 21.2, "Meldung des Tabs zählt, auch wenn Kontrakte × Multiplikator klein aussieht")
check(D(dict(Q, lots_ok={"lots": 21.2})) is None, "OK über die gemeldete Zahl gilt")
check(D(dict(Q, multiplier=1.1)) is None and D(dict(Q, slave_risk=100)) is None, "geänderte Werte: alte Meldung zählt nicht mehr, kein Fehlalarm")
check(D(dict(Q, hedge_eur=0)) is None, "Hedge weg: alte Meldung zählt nicht mehr")
check(SO(dict(P, master_contracts=2, multiplier=None, lots_sperre=dict(W(dict(P, master_contracts=2, multiplier=None)), lots=21))) == 21, "Plan ohne Multiplikator (nur Risiko): Meldung zählt")
ev = A([P, dict(P, id="p2", master_contracts=1), dict(P, id="p3", start_um_gestartet_at="x")], {"u1": "Marc"})
check(len(ev) == 1 and ev[0][1] == 2 and ev[0][2] == "lots_deckel" and "32" in ev[0][3] and "OK" in ev[0][4], "Alarm einmal für den gesperrten Plan, keiner für kleine oder geclaimte")
o = OF(dict(P, status="open"), 21.2, {"u1": "Marc"})
check(o[1] == 1 and o[2] == "lots_stop" and "21,20" in o[3] and "OK" in o[4] and o[0].endswith("|21.2"), "Stop im Kern: 🔴 sofort, einmal je Plan und Lot-Zahl")
ST = ns["lots_stop_wert"]
T = {"status": "open", "h_st": "fehler", "h_stop": "21.2"}
check(ST(T) == 21.2 and ST(dict(T, status="planned")) == 21.2, "Stop gilt für laufende und geplante Pläne")
check(ST(dict(T, status="review")) is None and ST(dict(T, h_st="offen")) is None and ST(dict(T, h_stop=None)) is None, "Master zu oder Hedge offen: kein Stop mehr")
check(ST(dict(T, lots_ok={"lots": 21.2})) is None and ST(dict(T, lots_ok={"lots": 20})) == 21.2, "OK über die Menge beendet den Stop, kleineres OK nicht")

# Einbau: vor dem Puls-Auftrag, an allen Start-Wegen, DB-Netz
su = html[html.index("function suStartetNichtWeil("):]
check(su[:su.index("suUnbestaetigt(p)")].count("tpLotsDeckelFehlt(p)") == 1, "Tab: Selbst-Start prüft vor dem Claim")
best = html[html.index("async function tpWdBestaetigungFehlt("):][:200]
check("tpLotsDeckelFrisch(plan)" in best and html.count("await tpWdBestaetigungFehlt(plan)") >= 2, "Tab: Hand-, Fern- und Neu-Start über dieselbe Sperre, Stand frisch aus der DB")
kern = html[html.index("async function hedgeSoloOeffnenKern("):]
kern = kern[:kern.index("notfallOpen")]
check("await tpLotsHedgeStop(plan" in kern and kern.index("await tpLotsHedgeStop(plan") < kern.index("plan.multiplier = Math.round") < kern.index("status: 'oeffnet'"), "Hedge: Stop in jedem Status, vor Frisch-Korrektur und 'oeffnet'-Merker")
tick = html[html.index("async function hedgeLotsOkTick("):]
tick = tick[:tick.index("function hedgeLiqStart(")]
check("seitStart" not in tick and "_hedgeNachgeholt" not in tick and "manuell: true" in tick and "lots_bestaetigt" in tick and "f.status !== 'open'" in tick, "Nach OK: öffnet unabhängig vom 3-min-Nachholen, nur solange der Master läuft")
check("if(da !== true){" in tick and tick.index("if(da !== true){") < tick.index("hedgeSoloOeffnen(f") and "lots_ok_wartet" in tick, "Nach OK: öffnet nur bei gesichteter Position, sonst Vermerk und weiter prüfen")
check("x.pc === pc" in tick and "Date.now() + 30000" in tick and tick.index("Date.now() + 30000") < tick.index("hedgeSoloOeffnen(f"), "Nach OK: nur am PC des Stops, ein gescheiterter Versuch kommt nach 30 s wieder")
check("h.grund_code === 'lots_deckel'" in html and "h.grund_code === 'master_flach'" in html, "Handknopf erscheint auch im Stop und nach „flach“")
check("_hedgeLotsFlachSeit.get(" in tick and tick.index("_hedgeLotsFlachSeit.get(") < tick.index("grund_code: 'master_flach'"), "Flach erst nach dem zweiten Blick endgültig")
klick = html[html.index("async function hedgeOeffnenKlick("):][:2000]
check("${_lots} Lot" in klick and "lots_bestaetigt: _lotsUeber" in klick, "Handknopf: Lot-Zahl im confirm")
check("Position gerade nicht zu sehen, erst im Master-Konto schauen" in klick and "das OK dafür liegt vor" in klick, "confirm: Sichtung und Lot-Zahl auch bei gültigem OK")
check("lots_stops" in app and "D.lotsStops" in html, "Braucht dich: Stops auch für fremde laufende Pläne")
okr = app[app.index("def admin_auto_plan_lots_ok"):app.index('@app.route("/alarm/lots-deckel"')]
check("laufend and stop is None" in okr and '"p_status": p.get("status")' in okr, "OK-Route: auch für laufende Pläne mit Stop, sonst 409")
for name in ("async function tpPreflightAndStart(", "async function tpPreflightMt5("):
    kopf = html[html.index(name):][:1200]   # WE1 (07.11.2026): davor steht jetzt die Wochenend-Sperre (tpPreflightMt5), der Lots-Deckel bleibt am Kopf
    check("await tpLotsDeckelFrisch(plan)" in kopf and "_pfRemoteMelde(plan.id" in kopf, name[15:-1] + ": Sperre am Kopf, Fern bekommt Antwort")
fr = html[html.index("async function tpLotsDeckelFrisch("):][:900]
check(".select('*')" in fr and "plan.status !== 'planned'" in fr and "start_um_gestartet_at: null" in fr, "Frisch: liest immer die DB, nur vor dem Start, gibt einen Claim zurück")
check("tpWdWartetAufBestaetigung(x) || tpLotsDeckelFehlt(x)" in html, "Kette: offenes OK hält die ID nicht an")
check("D.lotsRaus" in html and "Dl.lotsRaus" in html and "stop: !!t.stop, sicht: 'admin'" in html, "Braucht dich: Knopf auch für Winning Days und Funded, Verwalter gilt")
check("before update of start_um_gestartet_at" in sql and "lots <= 16" in sql and "ok->>'lots'" in sql and "round(" in sql and "'dup'" in sql and "coalesce(new.start_claim_art, 'start') <> 'start'" in sql, "SQL: Netz am Claim, 16 geht, Verbrauchs-Claims gehen durch")
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
var OK = { lots: 32 };
var kor = mit(P, {masterContracts: 3, multiplier: 1, frisch: 21.2, mt5Baseline: {lots_ok: {lots: 21.2}}}); kor.multiplier = 7.0667;
return JSON.stringify({ lots: tpFusionLots(P), gesperrt: tpLotsDeckelFehlt(P), g16: tpLotsDeckelFehlt(mit(P, {masterContracts: 5})), frisch: tpLotsDeckelFehlt(mit(P, {masterContracts: 3, multiplier: 1, frisch: 21.2})),
  ok: tpLotsDeckelFehlt(mit(P, {mt5Baseline: {lots_ok: OK}})), okKt: tpLotsDeckelFehlt(mit(P, {masterContracts: 11, mt5Baseline: {lots_ok: OK}})), okMult: tpLotsDeckelFehlt(mit(P, {multiplier: 3.3, mt5Baseline: {lots_ok: OK}})),
  korrektur: tpLotsDeckelFehlt(kor), maxDb: tpFusionLots(mit(P, {frisch: 3.2})), maxTab: tpFusionLots(mit(P, {masterContracts: 3, multiplier: 1, frisch: 21.2})), ohneMult: tpFusionLots(mit(P, {multiplier: null, frisch: 21})),
  ohneHedge: tpFusionLots(mit(P, {hedgeEur: 0})), echo: tpFusionLots({ route: 'mt5', slaveFirm: 'Fusion', masterContracts: 10, multiplier: 3.2 }), plus: tpFusionLots({ route: 'tvplus', slaveFirm: 'Fusion', masterContracts: 10, multiplier: 3.2 }), polar: tpFusionLots({ route: 'polar', slaveFirm: 'Fusion', masterContracts: 10, multiplier: 3.2 }) });
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
        check(r["ok"] is False and r["okKt"] is True and r["okMult"] is True, "Tab: OK gilt, bei anderen Lots nicht mehr")
        check(r["korrektur"] is False, "Tab: Frisch-Korrektur am Multiplikator entwertet das OK nicht (Marc-Fall)")
        check(r["maxDb"] == 32 and r["maxTab"] == 21.2 and r["ohneMult"] == 21, "Tab: das Größere aus gespeichert und Open-Rechnung, Knopf auch wenn nur das DB-Netz sperrt")
        check(r["ohneHedge"] is None and r["echo"] == 32 and r["plus"] == 32 and r["polar"] is None, "Tab: ohne Hedge kein Deckel, Copier-Wege mit Fusion zählen")

print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
