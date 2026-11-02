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
    code = html[html.index("  function wdFarmHedgeKern("):html.index("  async function wdVorplanRegelnSpeichern(")]
    check("function wdRecovererAltplanUpd" in code and i_a > 0, "Altplan: Funktion liegt zwischen wdFarmHedgeKern und wdVorplanRegelnSpeichern")
    q_ab = html[html.index("  async function wdAbgleich("):]
    q_ab = q_ab[:q_ab.index("(3) Zustand spiegeln")]
    check(".is('orbit_gesendet_at', null).is('started_at', null).is('hedge_freigabe_at', null).is('auto_bestaetigt_at', null).is('hand_werte_at', null)" in q_ab and "select('wd_tp')" in q_ab and "wdRecovererAltplanUpd(plan" in q_ab,
          "Altplan: Schreiben mit Riegel in der DB, wurde er bestätigt oder von Hand geändert, bleibt er")
    if shutil.which("osascript"):
        test = """function run(){
var window = {}; var _tpNqMode = 'mnq', TP_WD_SLAVE_FIRM = 'Fusion';
function hedgePplFuer(s){ return /^MNQ/.test(s || '') ? 2 : /^NQ/.test(s || '') ? 20 : 0 } function tpMasterPpl(){ return 2 } function tpWdSlavePpl(){ return 0.85 }
function tpCalcMultiplier(f, s, risk, kt, eur){ return Math.round(eur / (risk / (2 * kt) * kt * 0.85) * 10000) / 10000 }
function wdFarmHedge(pr, riskMaster, slaveEur, an, ddListe){ return wdFarmHedgeKern(pr, riskMaster, slaveEur, an, ddListe) }
""" + code + """
var plan = { status: 'planned', winningDay: true, route: 'tvv2', hedgeEur: 170.99, slaveRisk: 175, masterTp: 376, masterContracts: 3, masterRisk: 376, masterFirm: 'Apex', masterSymbol: 'MNQZ6' };
var K = { slave: 175, wuerfel: { tp: 376, kt: 3, quelle: 'wuerfel' } };
var acc = { wdTp: null, wdSl: null, maxRisikoTrade: 0 }, zy = { ziel: 1499, hedge_eur: 449.93, kt: null }, z = { basis: 'recoverer', slaveEur: 449.93 };
function mit(o, p){ var r = {}, k; for(k in o) r[k] = o[k]; for(k in p) r[k] = p[k]; return r }
var U0 = wdRecovererAltplanUpd, U = function(p, c, y, zz, an, dd, kk){ return U0(p, c, y, zz, an, dd, kk === undefined ? K : kk) }, a = U(plan, acc, zy, z, true, []);
return JSON.stringify({ a: a,
  freigabe: U(mit(plan, {hedgeFreigabeAt: 'x'}), acc, zy, z, true, []), auto: U(mit(plan, {autoBestaetigtAt: 'x'}), acc, zy, z, true, []),
  hand: U(mit(plan, {handWerteAt: 'x'}), acc, zy, z, true, []), vorgabe: U(plan, mit(acc, {wdTp: 500}), zy, z, true, []),
  gestartet: U(mit(plan, {startUmGestartetAt: 'x'}), acc, zy, z, true, []), keinwd: U(mit(plan, {winningDay: false}), acc, zy, z, true, []),
  ohneregel: U(plan, acc, null, z, true, []), staffel: U(plan, acc, zy, mit(z, {basis: 'staffel'}), true, []), ohnehedge: U(mit(plan, {hedgeEur: null}), acc, zy, z, true, []),
  ohnesymbol: U(mit(plan, {masterSymbol: ''}), acc, zy, z, true, []), handtp: U(mit(plan, {masterTp: 800}), acc, zy, z, true, []), handkt: U(mit(plan, {masterContracts: 4}), acc, zy, z, true, []),
  handhedge: U(mit(plan, {slaveRisk: 150}), acc, zy, z, true, []), schonrec: U(plan, acc, zy, z, true, [], {slave: 175, wuerfel: {tp: 376, kt: 3, quelle: 'recoverer'}}),
  ohnewuerfel: U(plan, acc, zy, z, true, [], {slave: 175}), keink: U(plan, acc, zy, z, true, [], null), kt: U(plan, acc, mit(zy, {kt: 4}), z, true, []) });
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
            check(a and a["tp"] == 1499 and a["upd"]["master_tp"] == 1499 and abs(a["upd"]["hedge_eur"] - 450.20) < 0.5 and a["upd"]["multiplier"] == 0.7062 and a["vor"]["lots"] == 2.12 and a["upd"]["slave_risk"] == 449.93 and a["upd"]["master_risk"] == 1499,
                  f"Altplan: Mike → 1.499 $ / ~450 €, altes Risiko 376 nicht übernommen ({a and a['upd']})")
            check(a and a["kt"] == 3 and a["upd"]["master_contracts"] == 3 and a["vor"]["eur"] == a["upd"]["hedge_eur"], "Altplan: Kontrakte bleiben, Vorschau passt zum Plan")
            check("hedge_freigabe_at" not in a["upd"] and "start_um" not in a["upd"] and "richtung" not in a["upd"], "Altplan: keine Freigabe, Start und Richtung unberührt")
            for fall in ("freigabe", "auto", "hand", "vorgabe", "gestartet", "keinwd", "ohneregel", "staffel", "ohnehedge", "ohnesymbol", "handtp", "handkt", "handhedge", "schonrec", "ohnewuerfel", "keink"):
                check(r[fall] is None, f"Altplan: {fall} → nichts ändern")
            check(r["kt"]["upd"]["master_contracts"] == 4, "Altplan: Kontrakte aus der Regel, wenn sie welche vorgibt")

    print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
