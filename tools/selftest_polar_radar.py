#!/usr/bin/env python3
"""Selbsttest POLAR-RADAR (20.10.2026, Finn 02:45 Dubai: „Frontend ebenfalls noch mal updaten zu Polar, auch unter Radar hinzufügen, alles
komplett die Konstrukte aufbauen") — rein rechnend, ohne Netz, Platzhalter-IDs.
Aufruf:  python3 tools/selftest_polar_radar.py
Prueft: (1) app.py lt_polar_felder (per Quelltext geladen wie selftest_live_trades): Slave-Seite (Person, Konto, Lots aus polar_auftrag
bzw. multiplier × Kontrakte, Gegenrichtung, Währung), Abrechnung aus mt5_baseline.polar, Hand-Polar ohne Abrechnung; /admin/live-trades
holt route polar nur mit ?echo=1 und lädt das Slave-Konto; (2) prophos.html wdlPolarPhase (echt per osascript/JXA): Phase je Lauf-Stand
(vorbereiten → bereit → Feuer → gefüllt → zu → Ende, Abbruch/Fehler, Hand-Polar), wer zuerst zu war + ms; (3) Radar-Zeile: Sticker
„Polar", beide Seiten, kein Wartet, „Stand"-Knopf, Popup-Lauf-Modus mit Abbruch nur vor der Feuerzeit; Mobil-Regel vorhanden."""
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
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade_app():
    ns = {"re": re}

    def block(name):
        i = APP.index(f"\ndef {name}(") + 1
        return APP[i:APP.find("\n\n\n", i)]
    exec("\n".join([re.search(r"^LT_POLAR_ROUTEN = .*$", APP, re.M).group(0).split("  #")[0],
                    block("_wd_num"), block("_wd_konto_groesse"), block("lt_polar_felder")]), ns)
    return ns


# (1) Backend
a = lade_app()
F = a["lt_polar_felder"]
check(a["LT_POLAR_ROUTEN"] == ("polar",), "LT_POLAR_ROUTEN = ('polar',)")
disp = {"aaaa-master": "Marc", "bbbb-slave": "Jacob"}
sacc = {"id": "k2", "user_id": "bbbb-slave", "name": "100k …7781", "firm": "FundedNext", "external_id": "9000007781", "starting_balance": 100000, "currency": "USD"}
plan = {"id": "p1", "user_id": "aaaa-master", "route": "polar", "status": "open", "richtung": "buy", "master_contracts": 3, "multiplier": 0.5,
        "slave_account_id": "k2", "polar_slave_user_id": "bbbb-slave", "slave_name": "alt", "slave_firm": "alt",
        "mt5_baseline": {"polar_auftrag": {"lots": 1.5, "sl_pkt": 12.5, "tp_pkt": 20.0, "kontrakte": 3}}}
z = F(plan, sacc, disp)
check(z["plattform"] == "polar" and z["polar"] is None and z["polar_lauf_id"] is None, "offener Plan ohne Abrechnung: plattform polar, polar None (Hand oder Lauf — entscheidet der Tab an /polar/stand)")
check(z["slave_person"] == "Jacob" and z["slave_user_id"] == "bbbb-slave", "Slave-Person aus polar_slave_user_id über disp")
check(z["slave_konto"] == {"name": "100k …7781", "firma": "FundedNext", "groesse": 100000, "kontonr_ende": "7781", "currency": "USD"}, f"Slave-Konto (Name, Firma, Größe, …Ende, Währung) {z['slave_konto']}")
check(z["slave_lots"] == 1.5 and z["slave_richtung"] == "sell", "Lots aus polar_auftrag, Slave = Gegenrichtung (buy → sell)")
plan2 = dict(plan, mt5_baseline={}, richtung="sell")
check(F(plan2, sacc, disp)["slave_lots"] == 1.5 and F(plan2, sacc, disp)["slave_richtung"] == "buy", "ohne polar_auftrag: Lots = multiplier × Kontrakte (0,5 × 3), sell → buy")
pol = {"master_pl": 850.0, "slave_pl": -118.4, "master_fill": 24788.25, "slave_fill": 24786.9, "zu_quelle": "master", "verzug_ms": 812, "status": "fertig", "lauf_id": "lauf-1"}
plan3 = dict(plan, status="review", slave_pl=-118.4, mt5_baseline={"polar_auftrag": plan["mt5_baseline"]["polar_auftrag"], "polar": pol})
z3 = F(plan3, sacc, disp)
check(z3["polar"] == pol and z3["polar_lauf_id"] == "lauf-1" and z3["slave_pl"] == -118.4, "Abrechnung (mt5_baseline.polar) + slave_pl kommen mit")
z4 = F(dict(plan, slave_account_id=None, polar_slave_user_id=None), None, disp)
check(z4["slave_person"] is None and z4["slave_konto"]["name"] == "alt" and z4["slave_konto"]["firma"] == "alt" and z4["slave_konto"]["currency"] is None,
      "ohne Slave-Konto: Rückfall auf slave_name/slave_firm am Plan, keine Person")
i = APP.find('@app.route("/admin/live-trades"')
R = APP[i:i + 16000]
check('"in.(tvv2,tsv2,mt5v2,mt5,polar)" if mit_echo else "in.(tvv2,tsv2)"' in R, "/admin/live-trades: route polar nur mit ?echo=1 (PC-Tab-Takt bleibt ohne)")
check("slave_account_id,slave_name,slave_firm,polar_slave_user_id,multiplier" in R, "/admin/live-trades: Polar-Felder im Select")
check("slave_ids = sorted(" in R and "currency" in R and "_lt_polar_zeile(p, acc, accs.get(str(p.get(\"slave_account_id\") or \"\")), disp, vorher)" in R,
      "/admin/live-trades: Slave-Konten (mit Währung) geladen, Polar-Zeile über _lt_polar_zeile, Fehler je Zeile abgefangen")
check('not in LT_ECHO_ROUTEN + LT_POLAR_ROUTEN' in R and 'not in ("echo", "polar")' in R, "Polar rechnet keine NQ-Demo und bekommt keinen Kurs")

# (2) wdlPolarPhase echt
m = re.search(r"  function wdlPolarPhase\(st, hand, jetzt\)\{\n.*?\n  \}", HTML, re.S)
check(bool(m), "wdlPolarPhase gefunden")
uhr = re.search(r"  const wdlPolarUhr = .*$", HTML, re.M)
NOW = 1_800_000_000_000
FAELLE = [
    ("Hand-Polar (404) = von Hand", [None, True], "hand"),
    ("kein Stand = unbekannt", [None, False], "unbekannt"),
    ("status start = vorbereiten", [{"status": "start", "bereit": []}, False], "vorbereiten"),
    ("ein bereit = bereit (Master bereit, Slave fehlt)", [{"status": "bereit", "bereit": ["master"]}, False], "bereit"),
    ("Feuerzeit in der Zukunft = feuer", [{"status": "feuer", "feuer_ms": NOW + 30000, "bereit": ["master", "slave"]}, False], "feuer"),
    ("Feuerzeit vorbei, kein Fill = feuer (gefeuert)", [{"status": "feuer", "feuer_ms": NOW - 3000}, False], "feuer"),
    ("beide gefüllt = gefuellt", [{"status": "offen", "feuer_ms": NOW - 9000, "master": {"gefuellt": {"fill": 1}}, "slave": {"gefuellt": {"fill": 2}}}, False], "gefuellt"),
    ("nur Master gefüllt = gefuellt (teils)", [{"status": "feuer", "feuer_ms": NOW - 9000, "master": {"gefuellt": {"fill": 1}}, "slave": {}}, False], "gefuellt"),
    ("master_zu = zu (Master zuerst, Slave schließt)", [{"status": "master_zu", "master_zu_ms": NOW - 500, "zu_quelle": "master"}, False], "zu"),
    ("beide zu, Slave zuerst = zu", [{"status": "slave_zu", "master_zu_ms": NOW - 100, "slave_zu_ms": NOW - 912, "zu_quelle": "slave"}, False], "zu"),
    ("fertig = ende", [{"status": "fertig", "master_zu_ms": NOW - 5000, "slave_zu_ms": NOW - 4188, "zu_quelle": "master"}, False], "ende"),
    ("abbruch = abbruch", [{"status": "abbruch", "grund": "vor der Feuerzeit"}, False], "abbruch"),
    ("fehler = fehler", [{"status": "fehler", "grund": "Panel 409"}, False], "fehler"),
]
if m and uhr and shutil.which("osascript"):
    js = (uhr.group(0) + "\n" + m.group(0) + "\nvar F = " + json.dumps([f[1] for f in FAELLE]) + ";\n"
          "JSON.stringify(F.map(function(a){ var r = wdlPolarPhase(a[0], a[1], " + str(NOW) + "); return [r.phase, r.kurz, r.text, r.zu] }))")
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], capture_output=True, text=True)
    try:
        v = json.loads(r.stdout.strip())
    except ValueError:
        v = None
    check(isinstance(v, list) and len(v) == len(FAELLE), f"wdlPolarPhase läuft ({(r.stderr or '').strip()[:100]})")
    if isinstance(v, list) and len(v) == len(FAELLE):
        for (name, _, soll), ist in zip(FAELLE, v):
            check(ist[0] == soll, f'wdlPolarPhase: {name} → {ist[0]} („{ist[1]}")')
        check(v[8][3] == {"quelle": "master", "ms": None, "beide": False} and "Slave schließt" in v[8][2], "zu: Master zuerst, Slave schließt noch (kein ms)")
        check(v[9][3] == {"quelle": "slave", "ms": 812, "beide": True} and "812 ms" in v[9][2], "zu: Slave zuerst, Master 812 ms später — ms aus master_zu_ms − slave_zu_ms")
        check(v[10][3]["ms"] == 812 and "abgerechnet" in v[10][2], "Ende: Text nennt Abrechnung + wer zuerst zu war")
        check("Master bereit, Slave fehlt" in v[3][2], "bereit: nennt die fehlende Seite")
else:
    print("… osascript fehlt — wdlPolarPhase nur per Text geprüft")
    check("if(status === 'fertig') return { phase: 'ende'" in (m.group(0) if m else ""), "wdlPolarPhase: fertig → ende")

# (2b) LIVE-ABLAUF (21.10.2026, Finn: „rechts Master, links Slave … Live-P&Ls, Take-Profits"): polarLiveWerte echt per JXA
ml = re.search(r"\n  function polarLiveWerte\(st, o\)\{.*?\n  \}\n", HTML, re.S)
ende = re.search(r"^  const WDL_POLAR_ENDE = .*$", HTML, re.M)
check(bool(ml and ende), "polarLiveWerte + WDL_POLAR_ENDE gefunden")
if ml and ende and shutil.which("osascript"):
    js = (ende.group(0) + "\n" + ml.group(0) + "\nvar st = {status: 'offen', master: {gefuellt: {fill: 30800}, level: {sl_soll: 30650, tp_soll: 30950}}, "
          "slave: {gefuellt: {fill: 30801}, level: {sl: 30951, tp: 30649}}, slave_live: {pl: -12.5}};\n"
          "var o = {richtung: 'buy', kontrakte: 1, symbol: 'MNQZ26', lots: 0.3, slavePpl: 1, kurs: 30810};\n"
          "JSON.stringify([polarLiveWerte(st, o), polarLiveWerte(Object.assign({}, st, {status: 'fertig'}), o), polarLiveWerte(st, Object.assign({}, o, {symbol: 'NQZ6', kurs: null})), polarLiveWerte(null, {})])")
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], capture_output=True, text=True)
    try:
        v = json.loads(r.stdout.strip())
    except ValueError:
        v = None
    check(isinstance(v, list) and len(v) == 4, f"polarLiveWerte läuft ({(r.stderr or '').strip()[:100]})")
    if isinstance(v, list) and len(v) == 4:
        m0, s0 = v[0]["master"], v[0]["slave"]
        check(m0["pl"] == 20 and m0["tpBetrag"] == 300 and m0["slBetrag"] == -300, "Master MNQ BUY 1: Kurs +10 Pkt = +20 $, TP +300 $, SL −300 $")
        check(s0["pl"] == -12.5 and s0["dir"] == -1 and s0["tpBetrag"] == 45.6 and s0["slBetrag"] == -45, "Slave Gegenrichtung: P&L aus slave_live, TP/SL-Betrag × Lots × $/Pkt")
        check(v[1]["master"]["pl"] is None and v[1]["slave"]["pl"] is None and v[1]["ende"] is True, "nach dem Ende kein Live-P&L mehr (Abrechnung zählt)")
        check(v[2]["master"]["pl"] is None and v[2]["master"]["tpBetrag"] == 3000, "ohne Kurs kein Master-P&L; NQ = 20 $/Pkt")
        check(v[3]["master"]["fill"] is None and v[3]["slave"]["pl"] is None, "leerer Stand verträglich")
check("+ spalte('Slave'," in HTML and HTML.index("+ spalte('Slave',") < HTML.index("+ spalte('Master',"), "Live-Ablauf: Slave links, Master rechts")
check("polarLiveStarten(_polarCheckPlan)" in HTML and "setInterval(polarLiveTick, 2000)" in HTML, "Prüf-Popup wechselt nach „Polar starten\" in den Live-Ablauf (2 s)")
check("? polarAblaufHtml(st, { richtung: t.richtung" in HTML, "Radar-Popup zeigt denselben Live-Ablauf")

# (3) Radar-Zeile + Popup + Mobil
check("function wdlIstPolar(t){ return !!t && (t.plattform === 'polar' || t.route === 'polar') }" in HTML, "wdlIstPolar")
check("if(wdlIstPolar(t)) return 'Polar'" in HTML, "wdlWeg: Sticker „Polar\"")
check("['Mit Hedge', ['Echo', 'Orbit', 'Winning Day', 'Polar']]" in HTML and "'Polar': 'var(--teal-soft, var(--teal))'" in HTML, "Modell-Chip + Blockfarbe Polar")
check("if(wdlIstPolar(t)) return null   // Polar (20.10.2026): keine Puls-Nachlesung" in HTML, "wdlWartet: Polar kennt kein Wartet")
check("if(offen && polar){" in HTML and 'data-wdl-polar="${escapeHtml(wdlTid(t))}"' in HTML, "Läuft-Zeile Polar mit „Stand\"-Knopf")
check("polSlaveWer" in HTML and "<span class=\"wdl-pol-s\"><b>${escapeHtml(String(t.slave_person || '?'))}</b>" in HTML, "Zeile zeigt Slave-ID + Slave-Konto als zweite Zeile")
check("${lots(t.slave_lots)} Lot</span>`, { tip: 'oben Master (Futures), unten Slave (CFD)' })" in HTML, "Richtung/Menge beider Seiten")
check("let erg = polar ? wdlPolarErg(t).html :" in HTML and "} else if(polar){\n        // Polar erledigt (Verlauf)" in HTML, "Überprüfen + Verlauf: wer zuerst zu war + beide P&L")
check("function wdlPolarPlZ(t, zelle, sig, col){" in HTML and "Slave ${sig(sp, cur === 'EUR' ? '€' : cur === 'USD' ? '$' : cur, 2)}" in HTML, "P&L-Zelle: Master $ + Slave in Kontowährung")
check("try{ await wdlPolarLaden() }catch(_){}" in HTML and "wdlPolarSig()])" in HTML, "wdlLaden holt /polar/stand je offenem Plan, Stand in der Signatur")
check("if(r.status === 404) wdl.polar[pid] = { stand: null, hand: true" in HTML, "404 kein Lauf = Hand-Polar")
check('<div id="pol-lauf" hidden>' in HTML and 'id="pol-lauf-abbruch" hidden' in HTML and 'id="polarTitel"' in HTML, "Popup: Lauf-Block + Abbruch-Knopf im #polarModal")
check("const feuer = st && Number(st.feuer_ms) || null, vorFeuer = !!(st && t.status === 'open' && !hand && !WDL_POLAR_ENDE.includes(String(st.status || '')) && !feuer)" in HTML
      and "ab.hidden = !vorFeuer" in HTML, "Abbruch nur vor der Feuerzeit sichtbar")
check("if(st.feuer_ms){ if(typeof atToast === 'function') atToast('⛔ Polar: Feuerzeit steht schon" in HTML and "window.mtcApi('polar-abbruch'" in HTML, "Abbruch → Panel /api/polar-abbruch, Riegel bei gesetzter Feuerzeit")
check("window.mtcApi('polar-stand'" in HTML and "trail_ende" in HTML, "Popup: Bot-Phase + letzte Log-Zeile vom Panel (nur am PC)")
check("document.getElementById('polarClose')?.addEventListener('click', wdlPolarPopupZurueck)" in HTML, "Schließen setzt das Popup zurück in den Plan-Modus (eigene Verdrahtung)")
check("if(wdlIstEcho(t) || wdlIstPolar(t)) return" in HTML, "Zeilen-Klick: Polar wählt keine Chart-Linien")
check("#dashboard-view .wdl-z-polar .wdl-z-ri .wdl-pol-s{display:none}" in HTML and "#polarModal .pol-lauf-seiten{grid-template-columns:1fr}" in HTML, "Mobil-Regeln (Slave-Richtung weg, Popup einspaltig)")
check("rkSaldoDrehen(plan, k, grundTxt){\n    const alt = plan.richtung" in HTML, "Drehen/CFD-Waage unangetastet")

print()
if FEHLER:
    print(f"FEHLER ({len(FEHLER)}):")
    for f in FEHLER:
        print("  - " + f)
    sys.exit(1)
print("ALLES GRÜN")
