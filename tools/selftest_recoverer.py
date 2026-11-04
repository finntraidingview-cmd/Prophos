#!/usr/bin/env python3
"""Selbsttest Recoverer (app.py wd_zyklus_*, 02.11.2026) — rein rechnend, ohne Netz. Beispiele aus dem Konstrukt
(.claude/master/berichte/2026-11-01_apex-wd-konstrukt.md Abschnitt 7), Satz-Stützpunkt 0 = max(Satz aus Staffel, 400) laut Auftrag.

Aufruf:  python3 tools/selftest_recoverer.py"""
import os
import re
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HIER), "app.py")
REGEL = {"stuetz": [{"v": 2000, "ziel": 750, "satz": 400}, {"v": 4000, "ziel": 1500, "satz": 300}],
         "firmen": ["apex", "apex100"], "ab_zyklus": 2, "bis": "2x_bester", "satz_normal": None, "kt": None, "aktiv": True}
VORPLAN = {"regeln": {"fu": {"apex": [370, 390], "apex100": [320, 340]},
                      "staffelFirma": {"apex": [{"von": 0, "eur": 50}, {"von": 4000, "eur": 100}, {"von": 10000, "eur": 175}]}}}
MIKE = {"id": "k1", "name": "150k PAAPEX 0001", "firm": "Apex", "wd_farm": True, "live_balance": 160029.26}
PAY = [{"requested_at": "2026-10-26", "status": "received"}]


def lade():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re, "datetime": datetime, "timezone": timezone}
    for name in ("def _wd_num(", "def wd_tsx_master_pl(", "def _wd_konto_groesse(", "def _wd_berlin_tag(", "def wd_plan_pnl(", "def wd_zyklus_stand(",
                 "def _wd_staffel_eur(", "def wd_zyklus_firma_key(", "def wd_zyklus_normal(", "def wd_zyklus_werte(", "def wd_zyklus_bis(", "def wd_zyklus_konto("):
        i = src.index(name)
        exec(src[i:src.find("\n\n\n", i)], ns)
    i = src.index("WD_ZYKLUS_VORGABE = {")
    exec(src[i:src.index("def _wd_berlin_tag(")], ns)
    return ns


def plan(tag, pnl, status="completed", **x):
    return dict({"status": status, "started_at": f"{tag}T10:00:00+00:00", "master_pl": pnl, "route": "tvv2"}, **x)


def main():
    ns = lade()
    f, stand = ns["wd_zyklus_konto"], ns["wd_zyklus_stand"]
    fehler = []

    def check(bed, text):
        print(("✓ " if bed else "✗ ") + text)
        if not bed:
            fehler.append(text)

    mike = [plan("2026-10-27", 374.88), plan("2026-10-28", 383.88), plan("2026-10-29", 388.38), plan("2026-10-30", -3998.16)]

    # Stand
    st = stand(mike, PAY)
    check(st["nr"] == 2 and st["start"] == "2026-10-26", "Zyklus-Nr = Anfragen + 1, Start = jüngste Anfrage")
    check(st["profit"] == -2851.02 and st["bester"] == 388.38 and st["verlust"] == 3998.16, "Mike: Profit −2.851,02, bester 388,38, Verlust 3.998,16")
    check(stand([plan("2026-10-26", 500)] + mike, PAY)["profit"] == -2851.02, "Trade am Anfrage-Tag zählt zum alten Zyklus")
    check(stand(mike + [plan("2026-10-30", 100, status="planned")], PAY)["profit"] == -2851.02, "nur completed/review zählen")
    check(stand(mike, PAY + [{"requested_at": "2026-10-29", "status": "storniert"}])["nr"] == 2, "stornierte Anfrage zählt nicht")
    zwei = stand([plan("2026-11-02", 100), plan("2026-11-02", -700)], PAY)
    check(zwei["tage"] == [{"tag": "2026-11-02", "pnl": -600.0}] and zwei["verlust"] == 600.0, "mehrere Trades am Tag werden je Tag summiert")
    check(ns["wd_plan_pnl"]({"tv": {"today_pnl_start": 100, "datum_start": "x"}, "fin": {"today_pnl": 300, "datum": "x"}}) == 200, "ohne master_pl: Endlesung − Start am selben Tag")
    check(ns["wd_plan_pnl"]({"status": "completed"}) is None, "ohne Wert → None, kein 0")
    check(ns["wd_plan_pnl"]({"master_pl": 356.2, "tv": {"today_pnl_start": 0, "datum_start": "x"}, "fin": {"today_pnl": 374.88, "datum": "x"}}) == 374.88, "Endlesung am selben Tag schlägt master_pl (Konstrukt Abschnitt 2)")
    check(ns["wd_plan_pnl"]({"master_pl": -3998.16, "tv": {"today_pnl_start": 0, "datum_start": "x"}, "fin": {"today_pnl": 0, "datum": "y"}}) == -3998.16, "Endlesung vom anderen Tag: master_pl, Verlusttag bleibt")
    check(ns["wd_plan_pnl"]({"master_pl": 356.2, "fin": {}}) == 356.2, "ohne Endlesung: master_pl")

    # Beispiel 5 (Mike) inkl. „bis erfüllt“
    z = f(MIKE, REGEL, VORPLAN, mike, PAY)
    check(z["aktiv"] and z["ziel"] == 1499, f"Mike −3.998 → Ziel 1.499 $ (ist {z['ziel']})")
    check(abs(z["hedge_eur"] - 450) < 1, f"Mike → Hedge ~450 € (ist {z['hedge_eur']})")
    check(z["tage_geschaetzt"] == 4, f"Mike → 4 Tage bis erfüllt (ist {z['tage_geschaetzt']})")
    check(z["rest_bis_erfuellt"] == 5996, f"Mike → noch 5.996 $ (ist {z['rest_bis_erfuellt']})")

    # Nur Verlusttage: erster Trade nach dem Payout (Gegenprüfung 02.11.2026)
    nur = f(MIKE, REGEL, VORPLAN, [plan("2026-10-27", -3998.16)], PAY)
    check(nur["aktiv"] and nur["ziel"] == 1499 and nur["tage_geschaetzt"] == 5, f"nur −3.998 im Zyklus: Regel an, nicht „erfüllt“ (ist {nur['grund_code']}, {nur['tage_geschaetzt']} Tage)")
    nur2 = f(MIKE, REGEL, VORPLAN, [plan("2026-10-27", -1000), plan("2026-10-28", -1000)], PAY)
    check(nur2["aktiv"] and not nur2["erfuellt"], "−1.000, −1.000: Regel an")
    check("−" in f(MIKE, REGEL, VORPLAN, mike, PAY)["grund"] and "," not in f(MIKE, REGEL, VORPLAN, mike, PAY)["grund"].split(":")[1].replace(", Profit", ""), "Grundtext: deutsche Zahlen, echtes Minus")

    # Finns Satz: 4 × 400, dann −400 → aus
    s = f(MIKE, REGEL, VORPLAN, [plan("2026-11-0%d" % i, 400) for i in (2, 3, 4, 5)] + [plan("2026-11-06", -400)], PAY)
    check(not s["aktiv"] and s["grund_code"] == "erfuellt" and s["ziel"] is None, "4 × 400, dann −400: Profit 1.200 ≥ 800 → Regel aus")

    # Weitere Zeilen der Tabelle
    z1 = f(MIKE, REGEL, VORPLAN, [plan("2026-10-20", 380), plan("2026-10-21", -1500)], [])
    check(not z1["aktiv"] and z1["grund_code"] == "zyklus_1" and z1["nr"] == 1, "Zeile 1: Zyklus 1 → aus")
    z2 = f(dict(MIKE, live_balance=164027), REGEL, VORPLAN, mike[:3], PAY)
    check(not z2["aktiv"] and z2["grund_code"] == "kein_verlust", "Zeile 2: kein Verlusttag → aus")
    check(z2["staffel_eur"] == 175 and z2["plus"] == 14027, "Zeile 2: 150k → Plus über der Größe, Staffel 175 €")
    z3 = f(dict(MIKE, live_balance=157000), REGEL, VORPLAN, [plan("2026-10-27", 380), plan("2026-10-28", -1000)], PAY)   # Plus 7.000 → Staffel 100 €
    check(z3["ziel"] == 565 and z3["satz"] == 400, f"Zeile 3 (−1.000): Ziel 565 $, Satz 400 (Stützpunkt 0 = max(Staffel, 400)) — ist {z3['ziel']}/{z3['satz']}")
    z4 = f(MIKE, REGEL, VORPLAN, [plan("2026-10-27", 380), plan("2026-10-28", -2000)], PAY)
    check(z4["ziel"] == 750 and z4["hedge_eur"] == 300 and z4["tage_geschaetzt"] == 5, "Zeile 4 (−2.000): 750 $ / 300 €, 5 Tage")
    z5b = f(MIKE, REGEL, VORPLAN, [plan("2026-10-27", 380), plan("2026-10-28", -6000)], PAY)
    check(z5b["ziel"] == 1500 and z5b["hedge_eur"] == 450, "Zeile 5b: über −4.000 Deckel 1.500 $ / 450 €")
    z6 = f(MIKE, REGEL, VORPLAN, [plan("2026-10-27", 380), plan("2026-10-28", -600), plan("2026-10-29", -600)], PAY)
    check(z6["verlust"] == 600 and z6["ziel"] == 491, "Zeile 6: zählt der Einzeltag (600), nicht der Netto-Verlust → 491 $")
    z7 = f(MIKE, REGEL, VORPLAN, mike + [plan("2026-11-0%d" % i, 1499) for i in (2, 3, 4, 5)], PAY)
    check(not z7["aktiv"] and z7["grund_code"] == "erfuellt", "Zeile 7: nach 4 × 1.499 erfüllt → aus")

    # Satz nie unter Staffel, fester Satz als Parameter
    hoch = f(dict(MIKE, live_balance=164100), REGEL, VORPLAN, [plan("2026-10-27", 380), plan("2026-10-28", -1000)], PAY)
    check(hoch["satz"] > 400, f"Plus ≥ 10.000: Stützpunkt 0 = Satz_normal 461, sinkt nie unter Staffel (ist {hoch['satz']})")
    fest = f(MIKE, dict(REGEL, satz_normal=450), VORPLAN, [plan("2026-10-27", 380), plan("2026-10-28", -1000)], PAY)
    check(fest["satz"] == 425, f"satz_normal = 450 setzt Stützpunkt 0 fest (−1.000: 425, ist {fest['satz']})")

    # Schalter und Bedingungen
    aus = f(dict(MIKE, wd_zyklus_regel="aus"), REGEL, VORPLAN, mike, PAY)
    check(not aus["aktiv"] and aus["grund_code"] == "schalter_aus", "Schalter aus → nie")
    an1 = f(dict(MIKE, wd_zyklus_regel="an"), REGEL, VORPLAN, [plan("2026-10-20", 380)], [])
    check(an1["aktiv"] and an1["ziel"] is None, "Schalter an ohne Verlusttag: aktiv, aber Normalwerte")
    an2 = f(dict(MIKE, wd_zyklus_regel="an", wd_farm=False), REGEL, VORPLAN, mike, PAY)
    check(not an2["aktiv"] and an2["grund_code"] == "kein_farm", "Schalter an ohne wd_farm: aus")
    check(not f(dict(MIKE, wd_farm=False), REGEL, VORPLAN, mike, PAY)["aktiv"], "ohne wd_farm → aus")
    check(not f(MIKE, dict(REGEL, aktiv=False), VORPLAN, mike, PAY)["aktiv"], "Hauptschalter aus → aus")
    ohne = f(MIKE, None, VORPLAN, mike, PAY)
    check(not ohne["aktiv"] and ohne["grund_code"] == "keine_regel" and ohne["ziel"] is None, "Spalte zyklus_regel fehlt (SQL nicht drin) → aus")
    check(ns["wd_zyklus_firma_key"]({"firm": "Tradeify", "name": "150k"}) is None, "andere Firma: kein Schlüssel, bekommt kein Feld")
    check(ns["wd_zyklus_firma_key"]({"firm": "Apex", "name": "100k x"}) == "apex100", "100k = apex100")
    check(ns["wd_zyklus_firma_key"]({"firm": "Apex", "name": "50k x"}) == "apex", "50k = apex, wie tpVpApex100")
    h100 = f({"id": "k", "name": "100k x", "firm": "Apex", "wd_farm": True, "live_balance": 100000}, REGEL, VORPLAN, [plan("2026-10-27", 330), plan("2026-10-28", -1000)], PAY)
    check(h100["ziel_normal"] == 330 and h100["ziel"] == 540, f"apex100: Normal 330, −1.000 → 540 (ist {h100['ziel']})")

    # _wd_zyklus_anhaengen gegen eine Fake-DB: Abfragen, Zuordnung je Konto, Fehlerweg
    src = open(APP, encoding="utf-8").read()
    i = src.index("def _wd_zyklus_regelzeile(")
    exec(src[i:src.find("\n\n\n", i)], ns)
    i = src.index("def _wd_zyklus_anhaengen(")
    exec(src[i:src.find("\n\n\n", i)], ns)
    # Tradeify „Zyklus im Plus" (03.11.2026) hängt am selben Weg — hier nur Apex-Konten, der Tradeify-Teil hat tools/selftest_tradeify_zyklus.py
    ns.setdefault("tradeify_zyklus_firma", lambda k: False)
    ns.setdefault("_tradeify_zyklus_anhaengen", lambda *a, **k: None)
    fragen = []

    class Fehler(Exception):
        pass

    class Req:
        class exceptions:
            HTTPError = Fehler

    def sb_all(tab, params):
        fragen.append((tab, dict(params)))
        if tab == "pending_payouts":
            return [{"account_id": "k1", "requested_at": "2026-10-26", "status": "received", "received_tx_id": "tx1"}]
        if tab == "transactions":
            return [{"id": "tx1", "account_id": "k1", "occurred_at": "2026-10-30T10:00:00+00:00"}, {"id": "tx2", "account_id": "k4", "occurred_at": "2026-10-20T10:00:00+00:00"}]
        return [dict(plan("2026-10-27", 374.88), master_account_id="k1"), dict(plan("2026-10-30", -3998.16), master_account_id="k1")]
    ns.update(requests=Req, _sb_all=sb_all, sb_select=lambda t, p: [{"vorplan": VORPLAN, "zyklus_regel": REGEL}])
    ns["print"] = lambda *a, **k: None
    ka = [dict(MIKE), {"id": "k2", "name": "150k x", "firm": "Tradeify", "wd_farm": True}, {"id": "k3", "name": "150k y", "firm": "Apex", "wd_farm": True, "live_balance": 151000}]
    ns["_wd_zyklus_anhaengen"](ka)
    check(ka[0]["zyklus"]["aktiv"] and ka[0]["zyklus"]["verlust"] == 3998.16, "Anhängen: Apex-Konto bekommt zyklus aus den Fake-Zeilen")
    check("zyklus" not in ka[1], "Anhängen: andere Firma bekommt kein Feld (Frontend wie heute)")
    check(ka[2]["zyklus"]["nr"] == 1 and not ka[2]["zyklus"]["aktiv"], "Anhängen: Konto ohne Anfrage = Zyklus 1")
    check(ka[0]["zyklus"]["nr"] == 2 and ka[0]["zyklus"]["start"] == "2026-10-26", "Anhängen: verknüpfte Buchung zählt nicht doppelt, Start bleibt die Anfrage")
    kc = [{"id": "k4", "name": "150k z", "firm": "Apex", "wd_farm": True}]
    ns["_wd_zyklus_anhaengen"](kc)
    check(kc[0]["zyklus"]["nr"] == 2 and kc[0]["zyklus"]["start"] == "2026-10-20", "Anhängen: direkt gebuchter Payout ohne Anfrage zählt wie payouts_n")
    check(any(t == "trade_plans" and p.get("started_at", "").startswith("gte.2026-10-20") for t, p in fragen), "Anhängen: Pläne ab dem ältesten Zyklus-Start")

    def kaputt(tab, params):
        raise RuntimeError("weg")
    ns["_sb_all"] = kaputt
    kb = [dict(MIKE)]
    check(ns["_wd_zyklus_anhaengen"](kb) is False and "zyklus" not in kb[0], "Anhängen: DB-Fehler → False, Konto ohne Feld, kein Absturz")

    def ohne_spalte(t, p):
        if "zyklus_regel" in p["select"]:
            e = Fehler("zyklus_regel does not exist")
            e.response = None
            raise e
        return [{"vorplan": VORPLAN}]
    ns["sb_select"] = ohne_spalte
    check(ns["_wd_zyklus_regelzeile"]() == (None, VORPLAN), "Regelzeile: Spalte fehlt → (None, vorplan), kein Fehler")

    # ── Recoverer-Altplan (prophos.html wdRecovererAltplanUpd + echte wdFarmHedgeKern, Mike a5e60a7f) ──
    import shutil
    import subprocess
    import tempfile
    html = open(os.path.join(os.path.dirname(HIER), "prophos.html"), encoding="utf-8").read()
    i_a = html.index("  function wdRecovererAltplanUpd(")
    code = html[html.index("  function wdFarmHedge(pr,"):html.index("  async function wdVorplanRegelnSpeichern(")]
    def _fn(name):   # echte Funktion aus prophos.html, bis zur schließenden Klammer auf Einrückung 2
        i = html.index("function " + name + "(")
        return html[i:html.index("\n  }\n", i) + 5]
    code_ppl = _fn("tpNqIsProjectx") + "\n" + _fn("tpNqGetMasterPpl") + "\n" + _fn("tpMasterPpl") + "\n" + _fn("tpMultiplierAusRisiko")
    check("function wdRecovererAltplanUpd" in code and i_a > 0, "Altplan: Funktion liegt zwischen wdFarmHedgeKern und wdVorplanRegelnSpeichern")
    q_ab = html[html.index("  async function wdAbgleich("):]
    q_ab = q_ab[:q_ab.index("(3) Zustand spiegeln")]
    check(".eq('master_tp', plan.masterTp).eq('master_symbol', plan.masterSymbol).eq('master_contracts', plan.masterContracts).eq('slave_risk', plan.slaveRisk).eq('hedge_eur', plan.hedgeEur)" in q_ab and "select('*').eq('id', plan.id).maybeSingle()" in q_ab,
          "Altplan: alte Werte im Riegel, bei 0 Zeilen frisch lesen statt vergeblich weiterschreiben")
    check(".is('orbit_gesendet_at', null).is('started_at', null).is('hedge_freigabe_at', null).is('auto_bestaetigt_at', null).is('hand_werte_at', null)" in q_ab and "select('wd_tp')" in q_ab and "wdRecovererAltplanUpd(plan" in q_ab,
          "Altplan: Schreiben mit Riegel in der DB, wurde er bestätigt oder von Hand geändert, bleibt er")
    if shutil.which("osascript"):
        test = """function run(){
var window = {}; var _tpNqMode = 'mnq', TP_WD_SLAVE_FIRM = 'Fusion';
var FIRM_PRESETS = { projectx: { ppl: 2 } }; function firmToPreset(){ return 'projectx' }
function hedgePplFuer(s){ return /^MNQ/.test(s || '') ? 2 : /^NQ/.test(s || '') ? 20 : 0 } function tpWdSlavePpl(){ return 0.85 }
function tpCalcMultiplier(f, s, risk, kt, eur){ return tpMultiplierAusRisiko(risk, kt, eur, tpMasterPpl(f), 0.85) }
""" + code_ppl + code + """
var plan = { status: 'planned', winningDay: true, route: 'tvv2', hedgeEur: 170.99, multiplier: 1.0695, slaveRisk: 175, masterTp: 376, masterContracts: 3, masterRisk: 376, masterFirm: 'Apex', masterSymbol: 'MNQZ6' };
var K = { slave: 175, wuerfel: { tp: 376, kt: 3, quelle: 'wuerfel' } };
var acc = { wdTp: null, wdSl: null, maxRisikoTrade: 0 }, zy = { ziel: 1499, hedge_eur: 449.93, kt: null }, z = { basis: 'recoverer', slaveEur: 449.93 };
function mit(o, p){ var r = {}, k; for(k in o) r[k] = o[k]; for(k in p) r[k] = p[k]; return r }
var ZN = mit(zy, {instr: 'nq', instr_kt: 1}), P2 = mit(plan, {masterTp: 1499, masterRisk: 1499, slaveRisk: 449.93, hedgeEur: 450.2, multiplier: 0.7062}), K2 = {slave: 449.93, wuerfel: {tp: 1499, kt: 3, quelle: 'recoverer'}};
var U0 = wdRecovererAltplanUpd, U = function(p, c, y, zz, an, dd, kk){ return U0(p, c, y, zz, an, dd, kk === undefined ? K : kk) }, a = U(plan, acc, zy, z, true, []);
var hK = {kt: null, wuerfel: {kt: 1, instr: 'nq'}}, hLeer = {kt: null, wuerfel: {instr: 'nq'}}, hMenge = function(k){ return k.kt || (k.wuerfel && k.wuerfel.kt) };
return JSON.stringify({ a: a, hk: hMenge(hK), nqSperre: [wdNqOhneMenge('nq', hMenge(hLeer)), wdNqOhneMenge('nq', 0), wdNqOhneMenge('nq', hMenge(hK)), wdNqOhneMenge(null, undefined)],
  freigabe: U(mit(plan, {hedgeFreigabeAt: 'x'}), acc, zy, z, true, []), auto: U(mit(plan, {autoBestaetigtAt: 'x'}), acc, zy, z, true, []),
  hand: U(mit(plan, {handWerteAt: 'x'}), acc, zy, z, true, []), vorgabe: U(plan, mit(acc, {wdTp: 500}), zy, z, true, []),
  gestartet: U(mit(plan, {startUmGestartetAt: 'x'}), acc, zy, z, true, []), keinwd: U(mit(plan, {winningDay: false}), acc, zy, z, true, []),
  ohneregel: U(plan, acc, null, z, true, []), staffel: U(plan, acc, zy, mit(z, {basis: 'staffel'}), true, []), ohnehedge: U(mit(plan, {hedgeEur: null}), acc, zy, z, true, []),
  ohnesymbol: U(mit(plan, {masterSymbol: ''}), acc, zy, z, true, []), handtp: U(mit(plan, {masterTp: 800}), acc, zy, z, true, []), handkt: U(mit(plan, {masterContracts: 4}), acc, zy, z, true, []),
  handslave: U(mit(plan, {slaveRisk: 150}), acc, zy, z, true, []), handhedge: U(mit(plan, {hedgeEur: 300}), acc, zy, z, true, []), ohnemult: U(mit(plan, {multiplier: null}), acc, zy, z, true, []), schonrec: U(plan, acc, zy, z, true, [], {slave: 175, wuerfel: {tp: 376, kt: 3, quelle: 'recoverer'}}),
  ohnewuerfel: U(plan, acc, zy, z, true, [], {slave: 175}),
  nq: U(plan, acc, ZN, z, true, []), nq2: U(P2, acc, ZN, z, true, [], K2), nqdone: U(mit(P2, {masterSymbol: 'NQZ6', masterContracts: 1, multiplier: 7.0624, hedgeEur: 449.8}), acc, ZN, z, true, [], {slave: 449.93, wuerfel: {tp: 1499, kt: 1, quelle: 'recoverer', instr: 'nq'}}),
  nqhand: U(mit(P2, {masterSymbol: 'MNQZ6'}), acc, ZN, z, true, [], {slave: 449.93, wuerfel: {tp: 1499, kt: 1, quelle: 'recoverer', instr: 'nq'}}),
  solo: (function(){ var pkt = 1499 / (20 * 1), lots = 449.93 / (0.85 * pkt); return { punkte: Math.round(pkt * 100) / 100, lots: Math.round(lots * 100) / 100 } })(), keink: U(plan, acc, zy, z, true, [], null), kt: U(plan, acc, mit(zy, {kt: 4}), z, true, []) });
}"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(test)
        try:
            aus = subprocess.run(["osascript", "-l", "JavaScript", f.name], capture_output=True, text=True, timeout=30)
        finally:
            os.unlink(f.name)
        check(aus.returncode == 0, "Altplan: Rechnung läuft (" + aus.stderr[:120] + ")")
        if aus.returncode == 0:
            import json
            r = json.loads(aus.stdout)
            a = r["a"]
            check(a and a["tp"] == 1499 and a["upd"]["master_tp"] == 1499 and abs(a["upd"]["hedge_eur"] - 450.20) < 0.5 and abs(a["upd"]["multiplier"] - 0.7062) < 0.0001 and a["vor"]["lots"] == 2.12 and a["upd"]["slave_risk"] == 449.93 and a["upd"]["master_risk"] == 1499,
                  f"Altplan: Mike → 1.499 $ / ~450 €, altes Risiko 376 nicht übernommen ({a and a['upd']})")
            check(a and a["kt"] == 3 and a["upd"]["master_contracts"] == 3 and a["vor"]["eur"] == a["upd"]["hedge_eur"], "Altplan: Kontrakte bleiben, Vorschau passt zum Plan")
            check("hedge_freigabe_at" not in a["upd"] and "start_um" not in a["upd"] and "richtung" not in a["upd"], "Altplan: keine Freigabe, Start und Richtung unberührt")
            for fall in ("freigabe", "auto", "hand", "vorgabe", "gestartet", "keinwd", "ohneregel", "staffel", "ohnehedge", "ohnesymbol", "handtp", "handkt", "handslave", "handhedge", "ohnemult", "schonrec", "ohnewuerfel", "keink"):
                check(r[fall] is None, f"Altplan: {fall} → nichts ändern")
            check(r["kt"]["upd"]["master_contracts"] == 4, "Altplan: Kontrakte aus der Regel, wenn sie welche vorgibt")
            check(r["hk"] == 1 and r["nqSperre"] == [True, True, False, False], f"1 NQ: k.kt leer → Menge 1 aus dem Würfel; ohne Menge kein NQ-Plan, MNQ unberührt ({r['hk']}, {r['nqSperre']})")
            n2 = r["nq2"]
            check(n2 and n2["upd"]["master_symbol"] == "NQZ6" and n2["upd"]["master_contracts"] == 1 and n2["upd"]["master_tp"] == 1499 and n2["instr"] == "nq",
                  f"1 NQ: Mike schon auf 1.499 $ / 3 MNQ wird einmal umgestellt ({n2 and n2['upd']})")
            check(n2 and n2["vor"]["lots"] == 7.06 and abs(n2["upd"]["multiplier"] - 7.0624) < 0.001 and abs(n2["upd"]["hedge_eur"] - 450.2) < 1, f"1 NQ: ~7,06 Lot (Finn: 3 MNQ = 2,12 → 1 NQ ≈ 7,07), Hedge-Euro bleibt ({n2 and n2['vor']})")
            check(r["nq"] and r["nq"]["upd"]["master_symbol"] == "NQZ6" and r["nq"]["upd"]["master_contracts"] == 1, "1 NQ: Würfel-Altplan (376 $ / 3 MNQ) direkt auf 1 NQ")
            check(r["nqdone"] is None and r["nqhand"] is None, "1 NQ: nach der Umstellung Ruhe, Hand-Rückstellung auf MNQ bleibt")
            check(r["solo"] == {"punkte": 74.95, "lots": 7.06}, f"1 NQ: Start-Rechnung (hedgeSoloOeffnenKern/hedgeMultAusRisiko) trifft dieselben Lots ({r['solo']})")
    # Regel liefert 1 NQ nur mit eigenen Werten; Notfall, Marge und Alarm bei 7 Lot, echte Funktionen aus copier.py / app.py
    zk = ns["wd_zyklus_konto"](dict(MIKE), REGEL, VORPLAN, [plan("2026-10-27", 374.88), plan("2026-10-30", -3998.16)], PAY)
    check(zk["aktiv"] and zk["kt"] is None and zk["instr_kt"] == 1 and zk["instr"] == "nq" and zk["ziel"] > 0, f"Regel: 1 NQ in eigenen Feldern, kt bleibt leer für alte Tabs ({zk.get('kt')}, {zk.get('instr')})")
    z0 = ns["wd_zyklus_konto"](dict(MIKE), REGEL, VORPLAN, [], [])
    check(z0["kt"] is None and z0["instr"] is None and z0["instr_kt"] is None, "Regel: ohne Recoverer kein NQ, normale Apex-WDs bleiben MNQ")
    src_c = open(os.path.join(os.path.dirname(HIER), "mt5-copier", "copier.py"), encoding="utf-8").read()
    i_n = src_c.index("def solo_notfall_sl(")
    nc = {}
    exec(src_c[i_n:src_c.find("\n\n\n", i_n)], nc)
    sl = nc["solo_notfall_sl"](28000.0, "sell", 74.95, faktor=1.05, point=0.01, digits=2)
    check(abs(sl - 28078.70) < 0.01, f"Notfall: 105 % von 74,95 Pkt = 78,70 Pkt hinter dem Fill ({sl})")
    src_a = open(APP, encoding="utf-8").read()
    ns["EH_MARGE_RESERVE"] = 0.20
    for name in ("def eh_marge(", "def wd_ist_recoverer_plan("):
        i_m = src_a.index(name)
        exec(src_a[i_m:src_a.find("\n\n\n", i_m)], ns)
    les = {"frei": 10000.0, "je_lot": 500.0, "offen": {"buy": 0.0, "sell": 0.0}}
    check(ns["eh_marge"](les, 7.06, "sell", 0, 60.0, 0.20)[0] is True, "Marge: 7,06 Lot bei 500 €/Lot passen in 10.000 € frei (3.530 € + 20 % Reserve)")
    check(ns["eh_marge"](dict(les, frei=4000.0), 7.06, "sell", 0, 60.0, 0.20)[0] is False, "Marge: bei 4.000 € frei gesperrt, nicht still kleiner")
    R = ns["wd_ist_recoverer_plan"]
    check(R({"winning_day": True, "master_firm": "Apex Trader", "master_symbol": "NQZ6"}) and not R({"winning_day": True, "master_firm": "Apex Trader", "master_symbol": "MNQZ6"})
          and not R({"winning_day": True, "master_firm": "Topstep", "master_symbol": "NQZ6"}) and not R({"winning_day": False, "master_firm": "Apex", "master_symbol": "NQZ6"}),
          "Markierung: nur Apex-WD auf NQ ist Recoverer")
    q_h = html
    q_an = q_h[q_h.index("  async function wdPlanAnlegen("):q_h.index("  async function wdAbgleich(")]
    check("master_contracts: k.kt || (k.wuerfel && k.wuerfel.kt), instr:" in q_ab + q_h and "if(wdNqOhneMenge(instrA, extra ? extra.master_contracts : wdRecovererKt(zyA))) return { fehler:" in q_an, "1 NQ: Heilung holt die Menge aus dem Würfel, ohne Menge kein Plan")
    check("(plan.winningDay !== true && symbol.toUpperCase() === stdSym.toUpperCase()) ? null : symbol" in q_h, "1 NQ: Popup leert das Symbol bei Winning Days nicht")
    check("const zyA = extra ? null : wdZyklusVon(acc.id), instrA = extra ? (extra.instr || null)" in q_an, "1 NQ: Selbstheilung nimmt Symbol und Menge zusammen aus der Tageszeile, nie 3 NQ")
    check("recoverer: !!window._planIstRecoverer?.(" in q_h and "if(p && typeof p.recoverer === 'boolean') return p.recoverer" in q_h, "Markierung: Läuft/Wartet-Karten prüfen das echte Symbol, nicht den NQ-Rückfall")
    check(q_h.count("window._planRecovererChipHtml?.(") >= 5 and "_planRecovererChipHtml = planRecovererChipHtml" in q_h, "Markierung: Chip in Zu bestätigen, Winning-Days-Übersicht und beiden Plan-Zeilen")

    # ── E4b (05.11.2026): Recoverer in WD → Einstellungen → Firmen → Apex. Echte e4bZyklusMerge aus prophos.html (JavaScriptCore), Ergebnis in wd_zyklus_konto ──
    import json
    import copy
    mike2 = [plan("2026-10-27", 374.88), plan("2026-10-30", -3998.16)]
    zk0 = ns["wd_zyklus_konto"](dict(MIKE), REGEL, VORPLAN, mike2, PAY)
    m_js = html[html.index("  const E4B_ZYKLUS_STD = {"):html.index("  window._e4bZyklusMerge = e4bZyklusMerge")]
    std_js = re.search(r"const E4B_ZYKLUS_STD = (\{.*?\})   //", m_js).group(1)
    check(json.loads(re.sub(r"(\w+):", r'"\1":', std_js).replace("'", '"')) == ns["WD_ZYKLUS_VORGABE"], "E4b: Frontend-Vorgabe = app.py WD_ZYKLUS_VORGABE")
    alt = dict(copy.deepcopy(REGEL), eigen="bleibt")   # fremder Schlüssel muss den Merge überleben
    faelle = {
        "gleich":    [alt, "apex", True, 2, [{"v": 2000, "ziel": 750, "satz": 400}, {"v": 4000, "ziel": 1500, "satz": 300}]],
        "ziel":      [alt, "apex", True, 2, [{"v": 2000, "ziel": 900, "satz": 400}, {"v": 4000, "ziel": 1800, "satz": 300}]],
        "ab3":       [alt, "apex", True, 3, []],
        "aus150":    [alt, "apex", False, 2, []],
        "beideaus":  [dict(alt, firmen=["apex"]), "apex", False, 2, []],
        "wiederan":  [dict(alt, firmen=["apex"], aktiv=False), "apex100", True, 2, []],
        "ungueltig": [alt, "apex", True, 0, [{"v": None, "ziel": -5, "satz": 0}, {"v": 4000, "ziel": 1500, "satz": 300}]],
        "ohneregel": [None, "apex", None, 3, []],
    }
    if shutil.which("osascript"):
        js = "function run(){ var _wd = {}; function escapeHtml(s){ return s }\n" + m_js + "\nvar F = " + json.dumps(faelle) + ", r = {};\n" \
             "for(var k in F){ var a = F[k]; r[k] = e4bZyklusMerge(a[0], a[1], a[2], a[3], a[4]) }\nreturn JSON.stringify(r) }"
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(js)
        aus = subprocess.run(["osascript", "-l", "JavaScript", f.name], capture_output=True, text=True, timeout=30)
        os.unlink(f.name)
        check(aus.returncode == 0, f"E4b: Merge läuft in JavaScriptCore ({aus.stderr.strip()[:200]})")
        if aus.returncode == 0:
            m = json.loads(aus.stdout)
            zk = lambda regel, konto=MIKE: ns["wd_zyklus_konto"](dict(konto), regel, VORPLAN, mike2, PAY)   # noqa: E731
            g = zk(m["gleich"])
            check(m["gleich"] == alt and (g["aktiv"], g["ziel"], g["satz"], g["hedge_eur"]) == (zk0["aktiv"], zk0["ziel"], zk0["satz"], zk0["hedge_eur"]),
                  f"E4b: gleiche Werte gespeichert → gleiche Regel, gleiches Farmer-Ergebnis ({g['ziel']} $ / {g['hedge_eur']} €)")
            check(m["gleich"]["eigen"] == "bleibt" and m["gleich"]["bis"] == "2x_bester" and m["gleich"]["satz_normal"] is None and "kt" in m["gleich"], "E4b: Merge statt Ersetzen — bis, satz_normal, kt, Fremdes bleiben")
            z2 = zk(m["ziel"])
            check(z2["aktiv"] and z2["ziel"] > zk0["ziel"] and z2["hedge_eur"] > zk0["hedge_eur"], f"E4b: Wert geändert wirkt — Ziel {zk0['ziel']} → {z2['ziel']} $, Hedge {zk0['hedge_eur']} → {z2['hedge_eur']} €")
            z3 = zk(m["ab3"])
            check(m["ab3"]["ab_zyklus"] == 3 and not z3["aktiv"] and z3["grund_code"] == "zyklus_1" and m["ab3"]["stuetz"] == REGEL["stuetz"], "E4b: ab Zyklus 3 wirkt — Mike im Zyklus 2 ohne Recoverer, Staffel unverändert")
            a1 = zk(m["aus150"])
            a2 = zk(m["aus150"], dict(MIKE, name="100k PAAPEX 0002", live_balance=104000))
            check(m["aus150"]["firmen"] == ["apex100"] and a1["grund_code"] == "firma" and a2["firma_key"] == "apex100" and a2["aktiv"],
                  f"E4b: Schalter je Firma — Apex 150k aus, Apex 100k bleibt an ({a1['grund_code']}, {a2['grund_code']})")
            b = zk(m["beideaus"])
            check(m["beideaus"]["aktiv"] is False and b["grund_code"] == "regel_aus", "E4b: letzte Firma aus → aktiv false (leere Liste fiele auf die Vorgabe zurück)")
            check(m["wiederan"]["aktiv"] is True and m["wiederan"]["firmen"] == ["apex100"], "E4b: aus allen wieder an → nur diese Firma an, nicht die alte Liste")
            check(m["ungueltig"]["ab_zyklus"] == 2 and m["ungueltig"]["stuetz"] == REGEL["stuetz"], "E4b: ungültige Eingaben behalten den alten Wert")
            o = m["ohneregel"]
            check(o["aktiv"] is False and o["ab_zyklus"] == 3 and zk(o)["grund_code"] == "regel_aus", "E4b: ohne DB-Regel schaltet eine Feldänderung den Recoverer nicht ein")

    print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
