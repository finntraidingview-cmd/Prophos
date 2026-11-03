#!/usr/bin/env python3
"""Selbsttest ABHAKEN EIN KLICK (prophos.html wdlEinKlickGrund, 30.10.2026 — Finn: „Trades, bei denen nichts passiert … immer ein Klick zu viel").
Aufruf:  python3 tools/selftest_abhaken_ein_klick.py   (ohne Netz; Quelltext-Prüfung, die Fälle laufen im Stub über window._wdlEinKlickGrund)."""
import os
import sys

html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


# wdlLesungAmTp (02.11.2026, S20) steht direkt davor und gehört zur Rechnung
fn = html[html.index("function wdlLesungAmTp("):html.index("window._wdlLesungAmTp")] + html[html.index("function wdlEinKlickGrund("):html.index("window._wdlEinKlickGrund")]
for marker, name in (("wdlGeblowtUrteil(t)", "geblowt → Popup"), ("wdlBestandenChip(t)", "bestanden → Popup"), ("wdlFcfdZielErreicht(t)", "Funded-CFD-Ziel → Popup"),
                     ("zahl(t.pl_balance)", "ohne echte Lesung → Popup"), ("wdlManuell(t)", "manuell → Popup"),
                     ("t.hedge.status !== 'geschlossen'", "Hedge offen → Popup"), ("Hedge-P&L fehlt", "Hedge-P&L fehlt → Popup")):
    check(marker in fn, name)
check("mklWdEigenerPlan(" not in fn, "A1 03.11.2026: eigener Plan ist kein Popup-Grund mehr")
check("kette_tag" not in fn, "Topstep-Tagesergebnis allein erzwingt kein Popup")
oe = html[html.index("function mklWdErledigtOeffnen("):html.index("function mwdErlStatusUI(")]
check("opts.einKlick" in oe and "mklWdErledigtSpeichern(); return" in oe and "!wdhCb?.checked" in oe, "Ein Klick speichert über den Popup-Weg, Winning-Day-Vorschlag öffnet das Popup")
check("if(eigen && typeof openTradeCompleteModal === 'function' && !(opts && opts.einKlick)){ tcOeffnen(); return }" in oe
      and "if(eigen && typeof openTradeCompleteModal === 'function'){ _mwdErlId = null; tcOeffnen(); return }" in oe
      and oe.index("if(opts.nurStill){ _mwdErlId = null; return }") < oe.index("_mwdErlId = null; tcOeffnen(); return }"),
      "A1: eigener Plan bucht beim Ein-Klick über den Radar-Weg, sonst (und nie beim stillen Takt) Trades-Dialog wie bisher")
check(oe.index("opts.einKlick") < oe.index("getElementById('mwdErledigtModal')?.classList.add('open')"), "Prüfung läuft vor dem Öffnen")
check("const ein = !!t && !grund; if(ein)" in html and "Date.now() - _wdlEinKlickAt < 600" in html, "Klick fragt die Prüfung, Doppelklick bucht die nächste Zeile nicht mit")
check("Number(t.balance_end) > 0" in fn and "t.tage_mini" not in fn and "beide_in_minute" not in fn and "return 'P&L passt nicht" not in fn and "return 'Ziel oder Boden unbekannt'" not in fn and "return 'eigener Plan'" not in fn and "'Gewinn, Ziel unbekannt'" in fn and "Ergebnis unplausibel (falsches Konto?)" in fn and "'Verlust, Boden unbekannt'" in fn and "dm.status === 'liquidiert'" in fn,
      "Balance 0 → Popup; A1: kein Popup mehr für TP/SL-Abweichung und fehlenden Boden, Schutz der Buchung bleibt (Ziel bei Gewinn, falsches Konto, 0)")
check("const sicht = _mwdErlSicht, ohneHedge" in html, "Werte für Anfrage und Toast vor dem await festgehalten")
check("if(mklWdEigenerPlan(pid) && typeof loadTradePlansFromSupabase === 'function'){ try{ await loadTradePlansFromSupabase() }catch(_){} }" in html, "A1: eigener Plan lädt nach dem Buchen die Planliste nach")
sp = html[html.index("async function mklWdErledigtSpeichern("):html.index("document.getElementById('mwdErledigtClose')")]
check("wdlLokalVergessen(pid)" in sp and "Abhaken nicht gespeichert" in sp, "Fehler: Toast und Zeile zurück")
# ── Echter Lauf von wdlEinKlickGrund in JavaScriptCore (ohne Node), Helfer per Merker am Trade ──
import json
import subprocess
import tempfile
STUBS = """
const flag = n => t => !!(t && t['_' + n]);
const wdlIstPolar = flag('polar'), mklWdEigenerPlan = () => false, wdlAbhakenSperre = () => '', wdlManuell = flag('man'), wdlGeblowtUrteil = flag('blow'), wdlKontoWeg = flag('weg'),
  wdlKontoWegErg = () => '', wdlTpUndWeg = flag('tpweg'), wdlBestandenChip = flag('best'), wdlFehltChip = flag('fehlt'), wdlZielMarkiert = flag('ziel'), wdlFcfdZielErreicht = flag('fz'),
  wdlWartet = flag('wart'), wdlPlGesch = flag('gesch'), wdlLiqIstTag = flag('tag'), wdlTid = t => t.id;
const wdlBlowStand = t => t._ohneLiq ? { liq: null } : { liq: 90000 };
const WDL_UEBERGANG = { challenge: 'x', phase1: 'x', phase2: 'x' };
"""
BASIS = {"id": "p", "status": "review", "route": "mt5v2", "konto_typ": "phase1", "konto_aktuell": {"typ": "phase1", "ziel_erreicht_at": None}, "ziel_usd": 110000,
         "balance_end": 100700, "pl_balance": 700, "master_tp": 700, "master_sl": 700, "endlesung": {"balance_end": 100700, "quelle": "puls"}}
FAELLE = [("unauffällig", {}, True), ("Hand geschlossen unter TP", {"pl_balance": 300, "endlesung": {"grund": "hand", "quelle": "puls"}}, True),
          ("SL getroffen", {"pl_balance": -700}, True), ("15 % + über TP in der Grenze", {"pl_balance": 800}, True),
          ("konto_geblowt", {"endlesung": {"konto_geblowt": {"x": 1}}}, False), ("grund tsx_geblowt", {"endlesung": {"grund": "tsx_geblowt"}}, False),
          ("puls_fehler konto_weg", {"endlesung": {"puls_fehler": "konto_weg: fehlt"}}, False), ("puls_fehler konto_nicht_erreicht", {"endlesung": {"puls_fehler": "konto_nicht_erreicht"}}, False),
          ("ohne ziel_usd, Gewinn", {"ziel_usd": None}, False), ("ohne ziel_usd, Verlust (A1)", {"ziel_usd": None, "pl_balance": -700}, True), ("ohne Liq/Boden, Gewinn (A1)", {"_ohneLiq": True}, True),
          # Stopp S2 zu 091b176c: Verlust ohne Boden bei Challenge/Phase/Funded → Popup (Blow verliert genau sein SL)
          ("Verlust genau SL ohne Boden, Phase 1", {"_ohneLiq": True, "pl_balance": -700}, False),
          ("Verlust ohne Boden, Funded CFD", {"_ohneLiq": True, "konto_typ": "funded_cfd", "konto_aktuell": {"typ": "funded_cfd"}, "route": "mt5", "slave_pl": 10, "pl_balance": -700}, False),
          ("Verlust ohne Boden, Winning-Days-Konto", {"_ohneLiq": True, "konto_typ": "winning_days", "konto_aktuell": {"typ": "winning_days"}, "pl_balance": -700}, True), ("wdlZielMarkiert", {"_ziel": True}, False),
          ("ziel_erreicht_at am Konto", {"konto_aktuell": {"typ": "phase1", "ziel_erreicht_at": "2026-10-30T10:00:00Z"}}, False),
          ("Konto in anderer Phase", {"konto_aktuell": {"typ": "phase2"}}, False), ("Konto-Stand fehlt, Gewinn", {"konto_aktuell": None}, False), ("Konto-Stand fehlt, Verlust", {"konto_aktuell": None, "pl_balance": -700}, False),
          ("P&L über das Doppelte jeder Bezugsgröße", {"pl_balance": 5000}, False), ("Verlust über das Doppelte jeder Bezugsgröße", {"pl_balance": -5000}, False), ("ohne TP/SL am Plan (A1)", {"master_tp": None, "master_sl": None}, True),
          # A1 (Finn 03.11.2026, Foto: Marc Echo The5%ers 200k …0436, BUY 51 Lot, −5.856,33 $): Verlust etwas über dem SL (Slippage) → kein Popup mehr
          ("Marc: Echo-Verlust 17 % über dem SL (A1)", {"route": "mt5", "slave_pl": 72.52, "master_tp": 5000, "master_sl": 5000, "pl_balance": -5856.33, "balance_end": 194143.67, "balance_start": 200000}, True),
          ("Gewinn 20 % über dem TP (A1)", {"pl_balance": 840}, True),
          ("Balance unter der Liq ohne Blow-Beweis", {"pl_balance": -700, "balance_end": 89000}, False),
          # Gegenprüfung A1: Gewinn nur am TP gemessen, Verlust ohne Boden enger
          ("Winning Day TP 300, +9.000 $ (falsches Konto)", {"konto_typ": "winning_days", "konto_aktuell": {"typ": "winning_days"}, "master_tp": 300, "pl_balance": 9000, "balance_start": 104500}, False),
          ("Verlust 1,7× SL ohne bekannten Boden (Winning Days)", {"_ohneLiq": True, "konto_typ": "winning_days", "konto_aktuell": {"typ": "winning_days"}, "master_sl": 1500, "pl_balance": -2600}, False),
          ("Verlust 1,4× SL ohne bekannten Boden (Winning Days)", {"_ohneLiq": True, "konto_typ": "winning_days", "konto_aktuell": {"typ": "winning_days"}, "master_sl": 1500, "pl_balance": -2100}, True), ("P&L genau 0", {"pl_balance": 0}, False), ("P&L genau 0 ohne TP/SL", {"pl_balance": 0, "master_tp": None, "master_sl": None}, False),
          ("t2_grund unplausibel", {"kette_grund": "Ergebnis unplausibel (−148.000 $)"}, False), ("Funded Futures", {"konto_typ": "funded", "konto_aktuell": {"typ": "funded"}}, False),
          ("Funded CFD unauffällig", {"konto_typ": "funded_cfd", "konto_aktuell": {"typ": "funded_cfd"}, "ziel_usd": None, "route": "mt5", "slave_pl": 0}, True),
          ("Balance 0", {"balance_end": 0, "pl_balance": -100000}, False), ("Hedge offen", {"hedge": {"status": "offen"}}, False), ("Lesung fehlt", {"pl_balance": None}, False),
          # Finn 02.11.2026: nichts passiert → direkt weg; Lesung/Hedge-P&L fehlen → Popup bleibt (Ein Klick würde eine Schätzung endgültig buchen)
          ("Tage-Mini", {"tage_mini": {"ist": 2}}, True), ("Demo an der Liq ohne Blow", {"demo": {"status": "liquidiert", "stop": "liq"}}, False), ("Demo an der Liq, Tageslimit", {"demo": {"status": "liquidiert", "stop": "liq"}, "_tag": True}, True), ("TP/Liq in derselben Minute", {"demo": {"status": "beide_in_minute"}}, True),
          ("Balance-Sprung", {"balance_sprung": True}, False), ("wartet auf Lesung", {"_wart": True}, False), ("geschätzter P&L", {"_gesch": True}, False), ("Folgetrade-Balance", {"endlesung": {"balance_quelle": "folgetrade"}}, False),
          ("Hedge-P&L fehlt", {"route": "tvv2", "hedge_eur": 400, "hedge": {"status": "geschlossen"}}, False), ("Hedge-P&L da", {"route": "tvv2", "hedge_eur": 400, "hedge": {"status": "geschlossen", "pl": -120}}, True), ("Lesung im falschen Konto (+40k)", {"pl_balance": 40000}, False),
          # Verlust ohne master_sl (Finn 02.11.2026, Marco Apex …0011, Plan 07d2a045): Bezug master_risk bzw. Abstand Start → Liq
          ("Marco: Verlust ohne SL, Tageslimit als Bezug", {"master_sl": None, "master_risk": 1500, "pl_balance": -1616.20}, True),
          ("Verlust ohne SL über dem Doppelten des Risikos", {"master_sl": None, "master_risk": 1500, "pl_balance": -4000}, False),
          ("Verlust ohne SL und Risiko, Abstand Start → Liq", {"master_sl": None, "pl_balance": -2900, "balance_start": 103000}, True),
          ("Verlust ohne SL, Risiko und Start (A1)", {"master_sl": None, "pl_balance": -700}, True),
          ("Funded-CFD-Ziel", {"_fz": True}, False), ("Konto weg", {"_weg": True}, False), ("geblowt", {"_blow": True}, False), ("bestanden-Chip", {"_best": True}, False), ("Polar", {"_polar": True}, False), ("manuell", {"_man": True}, False)]
js = STUBS + fn + "\nconst F = " + json.dumps([dict(BASIS, **f[1]) for f in FAELLE], ensure_ascii=False) + "; print(JSON.stringify(F.map(wdlEinKlickGrund)));"
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d.name], capture_output=True, text=True)
os.unlink(d.name)
check(r.returncode == 0, f"jsc läuft ({r.stderr[:200]})")
erg = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else []
for (name, _f, soll), g in zip(FAELLE, erg):
    check((g == "") is soll, f"{name}: {'Ein Klick' if not g else 'Popup: ' + g}")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.py"), encoding="utf-8").read()
# ── VORMERKEN statt Popup ohne Lesung (Finn 02.11.2026): Abhaken ohne Lesung → vorgemerkt, versteckt → Lesung kommt → Ein-Klick-Weg mit echtem Wert ──
check("if(t && wdlVormerkbar(t, grund)){ _wdlEinKlickAt = Date.now(); wdlVormerken(pid, t, grund); return }" in html, "Klick ohne Lesung merkt vor statt Popup, nur wenn der Wert noch kommen kann")
check("if(ev.target.closest('[data-wdl-vm-weg]')){ wdlVormerkenWeg(); return }" in html and "aktion: 'vormerken_weg'" in html, "„n vorgemerkt ×“ nimmt die Vormerkung zurück")
check("if(opts.nurStill){ _mwdErlId = null; return }" in oe, "vorgemerkt: der Takt öffnet nie ein Popup von selbst")
check('"vorgemerkt": base.get("abhaken_vorgemerkt")' in src and '"p_patch": {"abhaken_vorgemerkt": vm}, "p_status": "review"' in src and '"vormerken", "vormerken_weg"' in src, "Railway: Kennzeichen nur an Plänen in Überprüfen, live-trades liefert es")
check("wdl.daten = d; wdl.fehler = ''\n      setTimeout(() => { try{ wdlVorgemerktTick() }" in html, "Takt nach jedem Radar-Abruf")
vm = html[html.index("  const WDL_VORMERK_GRUENDE"):html.index("  function wdlAbhakenSperre(")]
vm = vm[:vm.index("  async function wdlVormerken(")] + vm[vm.index("  // Abhaken, sobald die Lesung da ist"):]
js2 = STUBS + fn + """
const window = {};
const document = { getElementById: () => ({ classList: { contains: () => false } }) };
let geoeffnet = []; function mklWdErledigtOeffnen(pid, t, o){ geoeffnet.push([pid, !!o.einKlick, !!o.nurStill]) }
const wdl = { daten: { trades: [] } };
""" + vm + """
const T = """ + json.dumps(dict(BASIS, id="v1", pl_balance=None, _wart=True)) + """;
const vorher = wdlEinKlickGrund(T);
T.vorgemerkt = { at: new Date().toISOString(), grund: vorher }; wdl.daten.trades = [T];
const versteckt = wdlVorgemerktVersteckt(T); wdlVorgemerktTick(); const ohneLesung = geoeffnet.length;
T.pl_balance = 650; T.balance_end = 100650; T._wart = false;
const sichtbar = !wdlVorgemerktVersteckt(T); wdlVorgemerktTick(); const nachLesung = geoeffnet.slice(); wdlVorgemerktTick();
const jetztIso = new Date().toISOString();
const B = """ + json.dumps(dict(BASIS, id="v2", pl_balance=None)) + """; B.vorgemerkt = { at: jetztIso }; wdl.daten.trades = [B];
B.pl_balance = 650; B._blow = true; const blowSichtbar = !wdlVorgemerktVersteckt(B); wdlVorgemerktTick();
const F = """ + json.dumps(dict(BASIS, id="v3", pl_balance=None)) + """; F.vorgemerkt = { at: jetztIso }; wdl.daten.trades = [F];
F.pl_balance = 40000; const falschSichtbar = !wdlVorgemerktVersteckt(F); wdlVorgemerktTick();
const A = """ + json.dumps(dict(BASIS, id="v4", pl_balance=None, _wart=True)) + """; A.vorgemerkt = { at: jetztIso };
const wartetVersteckt = wdlVorgemerktVersteckt(A);
A.vorgemerkt = { at: new Date(Date.now() - 7 * 3600000).toISOString() }; const fristSichtbar = !wdlVorgemerktVersteckt(A);
const P = """ + json.dumps(dict(BASIS, id="v5", pl_balance=None, endlesung={"puls_aufgegeben": True})) + """; P.vorgemerkt = { at: jetztIso };
const aufgegebenSichtbar = !wdlVorgemerktVersteckt(P), aufgegebenVormerkbar = wdlVormerkbar(P, wdlEinKlickGrund(P));
const K = """ + json.dumps(dict(BASIS, id="v6", pl_balance=None)) + """; const fertigOhneWert = wdlVormerkbar(K, wdlEinKlickGrund(K));
print(JSON.stringify({ vorher, versteckt, ohneLesung, sichtbar, nachLesung, zweimal: geoeffnet.length, blowSichtbar, falschSichtbar, wartetVersteckt, fristSichtbar, aufgegebenSichtbar, aufgegebenVormerkbar, fertigOhneWert }));
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d2:
    d2.write(js2)
r2 = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d2.name], capture_output=True, text=True)
os.unlink(d2.name)
try:
    v = json.loads(r2.stdout.strip().splitlines()[-1])
except Exception:
    v = {}
    print("JS:", r2.stdout[-600:], r2.stderr[-600:])
check(v.get("vorher") == "wartet auf Lesung" and v.get("versteckt") is True and v.get("ohneLesung") == 0, "wartet auf Lesung: vorgemerkt, aus „Erledigt“ raus, nichts abgehakt")
check(v.get("wartetVersteckt") is True and v.get("fristSichtbar") is True, "nach 6 h wieder sichtbar")
check(v.get("aufgegebenSichtbar") is True and v.get("aufgegebenVormerkbar") is False and v.get("fertigOhneWert") is False, "Puls aufgegeben bzw. Lesung fertig ohne Wert: nie versteckt, Klick öffnet das Popup")
check(v.get("sichtbar") is True and v.get("nachLesung") == [["v1", True, True]] and v.get("zweimal") == 1, "Lesung da: genau ein stiller Ein-Klick mit der echten Lesung, kein zweiter binnen 60 s")
check(v.get("blowSichtbar") is True and v.get("zweimal") == 1, "nach der Lesung Blow: zurück in „Erledigt“, kein stilles Abhaken (Popup beim Klick)")
check(v.get("falschSichtbar") is True and v.get("zweimal") == 1, "Lesung im falschen Konto (+40k): kein stilles Abhaken, zurück in „Erledigt“ mit Popup")

check('"master_symbol_root,master_tp,master_sl,master_risk,master_pl,hedge_eur,hedge_faktor,start_um,start_um_gestartet_at' in src and '"master_risk": _wd_num(p.get("master_risk"))' in src, "live-trades liest und liefert master_risk")
check('daten.get("nur_review") is True and plan and plan.get("status") != "review"' in src and "einKlick ? { nur_review: true }" in html, "nur_review: Ein Klick bekommt 409, wenn der Trade nicht mehr in Überprüfen steht")
print(f"\n{'selftest_abhaken_ein_klick: alle Prüfungen grün' if not FEHLER else f'✗ {len(FEHLER)} Fehler'}")
sys.exit(1 if FEHLER else 0)
