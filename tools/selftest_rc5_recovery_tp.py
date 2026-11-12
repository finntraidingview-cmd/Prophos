#!/usr/bin/env python3
"""Selbsttest RC5 (Finn 12.11.2026 ~20:17 Dubai: „dass der Take Profit immer nur so ist, wie er wirklich sein muss“). Fall Mike Tradeify 150k …3058 mit den echten
Zahlen: Zyklus 2 seit der Anfrage 31.10., Ausgleich fc2c545c (+1.105,86 $) endete 11.11. 21:45:07 UTC, der nächste Ausgleich c892a4d0 wurde 13 s später mit TP 2.904 $
gewürfelt — der laufende/unbelegte Trade fehlte. Prüft app.py (wd_zyklus_offen, tradeify_zyklus_konto, wd_zyklus_konto) und prophos.html (Nachzug wdRecovererAltplanUpd,
window._wdRecoveryTpGrund, Start-Prädikat) — ohne Netz und DB.

Aufruf:  python3 tools/selftest_rc5_recovery_tp.py"""
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "timezone": timezone}


def lade(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^\S)", app, re.S | re.M)
    exec(m.group(0), ns)


def ruf(fn, *a, **k):
    for _ in range(60):
        try:
            return ns[fn](*a, **k)
        except NameError as e:
            lade(str(e).split("'")[1])
    raise RuntimeError(fn)


for n in ("TRADEIFY_ZYKLUS_MIN_USD", "TRADEIFY_ZYKLUS_PUFFER", "TRADEIFY_AUSGLEICH_BESTAETIGEN", "_wd_iso_ts", "WD_ZYKLUS_STAFFEL_VON", "WD_ZYKLUS_STAFFEL_STD",
          "WD_GOOD_DAY_MIN", "WD_FIRMEN_REGELN_STD", "wd_zyklus_offen", "tradeify_zyklus_konto", "WD_ZYKLUS_VORGABE", "wd_zyklus_konto"):
    lade(n)
exec(re.search(r"^WD_ZYKLUS_KT, WD_ZYKLUS_INSTR = .*$", app, re.M).group(0), ns)
ns["wd_plan_pnl"] = lambda p: p.get("master_pl")
ns["_cme_handelstag"] = lambda x=None: "2026-11-12"
ns["rc3_recovery_lots"] = lambda *a, **k: None

MIKE = {"id": "14e31eae", "name": "150k FTDFYSLX150393423058 → Winning Days", "firm": "Tradeify", "user_id": "32b854d1", "max_drawdown": 4500,
        "account_type": "winning_days"}
PAY = [{"requested_at": "2026-10-31", "status": "received"}]
VP = {"regeln": {"fu": {"tradeify": [268, 280]}, "staffel": [50, 60, 70, 80, 90]}}
# echte Trades des Zyklus (trade_plans, 02.–11.11.): (Start, Ende, P&L, balance_start)
T = [("2026-11-02T07:02:42+00:00", "2026-11-02T07:34:33+00:00", 264.30, 159463.32), ("2026-11-03T08:25:36+00:00", "2026-11-03T12:48:43+00:00", -30.76, 159727.62),
     ("2026-11-04T02:12:57+00:00", "2026-11-04T02:20:46+00:00", 270.36, 159696.86), ("2026-11-05T00:52:19+00:00", "2026-11-05T00:54:33+00:00", 259.86, 159967.22),
     ("2026-11-06T01:48:15+00:00", "2026-11-06T07:25:28+00:00", 264.24, 160227.08), ("2026-11-09T09:15:14+00:00", "2026-11-09T20:13:58+00:00", -4007.76, 160491.32),
     ("2026-11-10T04:14:51+00:00", "2026-11-10T21:45:09+00:00", 137.34, 156483.56)]
PL = [{"id": f"t{i}", "status": "completed", "started_at": s, "ended_at": e, "master_pl": pl, "tv": {"balance_start": bs}} for i, (s, e, pl, bs) in enumerate(T)]
FC2 = {"id": "fc2c545c", "started_at": "2026-11-11T15:24:47+00:00", "tv": {"balance_start": 156620.90}}

# ── wd_zyklus_offen ──
check(ruf("wd_zyklus_offen", PL, "2026-10-31") is None, "alle Trades belegt → kein Grund")
check(ruf("wd_zyklus_offen", PL + [dict(FC2, status="open")], "2026-10-31").startswith("Trade läuft noch"), "laufender Trade → Stand nicht belegt")
check(ruf("wd_zyklus_offen", PL + [dict(FC2, status="review", ended_at="2026-11-11T21:45:07+00:00", master_pl=None)], "2026-10-31").startswith("Trade ohne P&L"),
      "beendet, aber ohne P&L → Stand nicht belegt")
check(ruf("wd_zyklus_offen", [dict(PL[0], status="review", master_pl=None, started_at="2026-10-30T07:00:00+00:00")] + PL[1:], "2026-10-31") is None, "Trade ohne P&L VOR dem Zyklus zählt nicht")
check(ruf("wd_zyklus_offen", PL + [dict(FC2, status="completed", master_pl=None)], "2026-10-31") is None, "completed ohne P&L (Altlast) sperrt nicht dauerhaft (Prüfer S3)")

# ── Mike: so kam 2.904 zustande (Stand vor RC5 wäre: Trade fehlt, alte Balance gilt als frisch) ──
alt = ruf("tradeify_zyklus_konto", MIKE, PL, PAY, 5, 5, VP, 156620.90, "2026-11-10T22:00:00+00:00")
check(alt["aktiv"] and alt["gewinn"] == -2842.42 and 2874 <= alt["ziel"] <= 2904, f"Beleg: ohne den +1.106-Trade −2.842,42 $ → TP {alt['ziel']} $ (Plan trug 2.904)")
# ── RC5: der Trade läuft / ist ohne P&L → kein Ausgleich aus diesem Stand ──
z1 = ruf("tradeify_zyklus_konto", MIKE, PL + [dict(FC2, status="open")], PAY, 5, 5, VP, 156620.90, "2026-11-10T22:00:00+00:00")
check(z1["aktiv"] is False and z1["grund_code"] == "laeuft" and "läuft" in z1["grund"] and z1["ziel"] is None, f"Trade läuft: kein Ausgleich, kein Ziel ({z1['grund'][:70]})")
check(z1["gesperrt"] is True and z1["gewinn"] == -2842.42, "Payout-Sperre rechnet weiter aus der Balance (Prüfer S2)")
z2 = ruf("tradeify_zyklus_konto", MIKE, PL + [dict(FC2, status="review", ended_at="2026-11-11T21:45:07+00:00", master_pl=None)], PAY, 5, 5, VP, 156620.90,
         "2026-11-11T21:45:10+00:00")
check(z2["aktiv"] is False and "P&L" in z2["grund"] and z2["gesperrt"] is True, "abgeschlossen, P&L fehlt: kein Ausgleich, Sperre bleibt")
# ── abgehakt + frische Balance → TP nur noch der echte Fehlbetrag ──
fertig = PL + [dict(FC2, status="completed", ended_at="2026-11-11T21:45:07+00:00", master_pl=1105.86)]
z3 = ruf("tradeify_zyklus_konto", MIKE, fertig, PAY, 5, 5, VP, 157726.76, "2026-11-11T22:44:00+00:00")
check(z3["aktiv"] and z3["gewinn"] == -1736.56 and 1768 <= z3["ziel"] <= 1798 and z3["ziel"] < 2000,
      f"Mike frisch: −1.736,56 $ → TP = Fehlbetrag + 1 + Puffer 30–60 = {z3['ziel']} $ (nicht 2.904)")
z4 = ruf("tradeify_zyklus_konto", MIKE, fertig, PAY, 5, 5, VP, 156620.90, "2026-11-11T21:40:00+00:00")
check(z4["aktiv"] is False and "nicht frisch" in z4["grund"], "abgehakt, aber Balance vor dem Trade-Ende gelesen → wie bisher unbekannt")

# ── Apex-Recoverer: offener Trade → nicht aktiv ──
APEX = {"id": "ax1", "name": "150k APEX-1 → Winning Days", "firm": "Apex Trader", "wd_farm": True, "live_balance": 152000}
pa = [{"status": "completed", "started_at": "2026-11-05T05:00:00+00:00", "master_pl": 400.0}, {"status": "completed", "started_at": "2026-11-06T05:00:00+00:00", "master_pl": -1500.0}]
ra = ruf("wd_zyklus_konto", APEX, dict(ns["WD_ZYKLUS_VORGABE"]), {}, pa, [{"requested_at": "2026-11-01", "status": "received"}])
check(ra["aktiv"] is True, f"Apex Verlusttag: Recoverer aktiv ({ra.get('grund')})")
rb = ruf("wd_zyklus_konto", APEX, dict(ns["WD_ZYKLUS_VORGABE"]), {}, pa + [{"status": "open", "started_at": "2026-11-07T05:00:00+00:00"}], [{"requested_at": "2026-11-01", "status": "received"}])
check(rb["aktiv"] is False and rb.get("grund_code", rb.get("code")) in ("laeuft", None) and "läuft" in str(rb.get("grund")), f"Apex mit laufendem Trade: nicht aktiv ({rb.get('grund')})")
check('"status": "in.(completed,review,open)",   # RC5' in app, "_wd_zyklus_anhaengen liest offene Pläne mit")

# ── Frontend in JavaScriptCore: _wdRecoveryTpGrund + Nachzug-Bedingung + Start-Prädikat ──
i = html.index("  const WD_RECOVERY_TP_TOL = 75")
grund_js = html[i:html.index("  function wdZyklusUngeklaert(k){", i)]
pl_ms = lambda s: s
plan = {"id": "c892a4d0", "masterAccountId": "14e31eae", "masterTp": 2904, "status": "planned"}
js = """
var window = {};
var tradePlans = [], accounts = [];
window._wdZyklus = { map: {}, geladen: true, kontoAt: {} };
window._wdZyklusRoh = function(id){ return window._wdZyklus.map[id] || null };
""" + grund_js + """
var P = %s, r = {};
var ende = Date.parse('2026-11-11T21:45:07Z');
tradePlans = [{ id: 'fc2c545c', masterAccountId: '14e31eae', status: 'open' }];
window._wdZyklus.map['14e31eae'] = { aktiv: true, ziel: 2904 };
window._wdZyklus.kontoAt['14e31eae'] = ende - 60000;
r.laeuft = window._wdRecoveryTpGrund(P);
tradePlans = [{ id: 'fc2c545c', masterAccountId: '14e31eae', status: 'completed', endedAt: '2026-11-11T21:45:07Z' }];
r.alt = window._wdRecoveryTpGrund(P);
window._wdZyklus.kontoAt['14e31eae'] = ende + 3600000;
window._wdZyklus.map['14e31eae'] = { aktiv: true, ziel: 1785 };
r.passtNicht = window._wdRecoveryTpGrund(P);
var P4 = JSON.parse(JSON.stringify(P)); P4.masterTp = 1785 + 60; r.puffer = window._wdRecoveryTpGrund(P4);
var P5 = JSON.parse(JSON.stringify(P)); P5.masterTp = 1700; r.kleiner = window._wdRecoveryTpGrund(P5);
accounts = [{ id: '14e31eae', wdTp: 400 }];
var P6 = JSON.parse(JSON.stringify(P)); P6.masterTp = 400; r.vorgabeApex = window._wdRecoveryTpGrund(P6);
accounts = [{ id: '14e31eae', wdTp: 2000 }];
var P7 = JSON.parse(JSON.stringify(P)); P7.masterTp = 2000; P7.mt5Baseline = { wd_ausgleich: true }; r.vorgabeAusgl = window._wdRecoveryTpGrund(P7);
var P8 = JSON.parse(JSON.stringify(P)); P8.mt5Baseline = { wd_ausgleich: true }; r.vorgabeZuGross = window._wdRecoveryTpGrund(P8);
accounts = [];
var P2 = JSON.parse(JSON.stringify(P)); P2.masterTp = 1785;
r.frei = window._wdRecoveryTpGrund(P2);
window._wdZyklus.map['14e31eae'] = { aktiv: false, grund: 'Zyklus im Plus' };
r.inaktiv = window._wdRecoveryTpGrund(P2);
var P3 = JSON.parse(JSON.stringify(P)); P3.handWerteAt = 'x';
r.hand = window._wdRecoveryTpGrund(P3);
window._wdZyklus.geladen = false;
r.ungeladen = window._wdRecoveryTpGrund(P2);
print(JSON.stringify(r));
""" % json.dumps(plan)
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
    check(r["laeuft"].startswith("Recovery-TP nicht prüfbar") and "läuft" in r["laeuft"], f"Tab: anderer Trade läuft → nicht starten ({r['laeuft']})")
    check("älter als der letzte Trade" in r["alt"], f"Tab: Stand vor dem Trade-Ende → nicht starten ({r['alt']})")
    check("Plan-TP 2904 $, nötig 1785 $" in r["passtNicht"], f"Tab: TP zu groß für den frischen Fehlbetrag → nicht starten, Nachzug folgt ({r['passtNicht']})")
    check(r["puffer"] == "" and r["kleiner"] == "", "Tab: Puffer-Neuwurf (+60 $) und kleinerer TP sperren nicht (Prüfer S1)")
    check(r["vorgabeApex"] == "" and r["vorgabeAusgl"] == "", "Tab: TP-Vorgabe am Konto gilt wie im Würfel — Apex = Vorgabe, Ausgleich = max(Ziel, Vorgabe) (Prüfer M2)")
    check("nötig 2000 $" in r["vorgabeZuGross"], f"Tab: Ausgleich mit Vorgabe 2.000 $, Plan 2.904 $ → zu groß ({r['vorgabeZuGross']})")
    check(r["frei"] == "", "Tab: frischer Stand + passender TP → frei")
    check("Zyklus im Plus" in r["inaktiv"], "Tab: Zyklus nicht mehr aktiv → nicht starten")
    check(r["hand"] == "", "Tab: Hand-Werte gelten")
    check("nicht geladen" in r["ungeladen"], "Tab: Stand nicht geladen → nicht starten")
i = html.index("  function suStartetNichtWeil(p, scharf){")
sp = html[i:html.index("  const suStartetVonSelbst", i)]
i2 = html.index("  function suRecoveryTpGrund(p){")
sg = html[i2:html.index("  function suStartetNichtWeil(p, scharf){", i2)]
check("{ const rt = suRecoveryTpGrund(p); if(rt) return rt }" in sp and "let rt = 'Recovery-TP nicht prüfbar — Prüfung nicht geladen'" in sg and "window._wdRecoveryTpGrund(p)" in sg
      and "mt5Baseline.wd_ausgleich === true" in sg, "Start-Prädikat: Recovery-Plan nur mit geprüftem TP, fehlt die Prüfung → nicht starten")
i3 = html.index("  function suKetteFrei(p, plaene, now){")
check("tpLotsDeckelFehlt(x) || suRecoveryTpGrund(x))" in html[i3:i3 + 900], "Kette: ein gesperrter Recovery-Plan hält die WD-Kette der ID nicht auf (Prüfer M1)")
check("const stufe = w && (w.quelle === 'wuerfel' || w.quelle === 'recoverer')" in html, "Nachzug: auch schon gesetzte Recovery-Pläne bis zum Start")
check("const upd = { master_sl: null, master_tp: tp," in html and "{ wd_ausgleich: true, wd_sl: wdSlOhneWuerfel('Ausgleich — kein Würfel') }" in html
      and "{ wd_recoverer: true, wd_sl: wdSlOhneWuerfel('Recoverer — kein Würfel') }" in html, "Nachzug: Recovery-Plan ohne Zufalls-SL (master_sl null, wd_sl „kein Würfel“)")
# RC5b (S7 SOLLTE): Marke + wd_sl nie VOR dem TP-Update und nie ohne Claim-Guards — alles in EINEM Update mit updated_at-Lock
i = html.index("          let blNeu = null, blAt = null")
blk = html[i:html.index("          // nie zurückdrehen, was der Richtungsschutz am Start gedreht hat", i)]
check("baselinePatch(plan.id, { wd_ausgleich" not in html and "baselinePatch(plan.id, { wd_recoverer" not in html, "keine Marke mehr per baselinePatch vor dem TP-Update")
upd = blk[blk.index(".update(Object.assign({}, alt.upd, { mt5_baseline: blNeu }))"):]
upd = upd[:upd.index(".select('*')")]
check(all(g in upd for g in (".eq('status', 'planned')", ".is('start_um_gestartet_at', null)", ".is('orbit_gesendet_at', null)", ".is('started_at', null)", ".eq('updated_at', blAt)")),
      "Marke, wd_sl und TP im selben Update: status planned, ungeclaimt, nicht gesendet, nicht gestartet, updated_at unverändert")
check(blk.index(".select('mt5_baseline,updated_at')") < blk.index(".update(Object.assign({}, alt.upd, { mt5_baseline: blNeu }))") and "Object.assign({}, (frB.mt5_baseline" in blk,
      "Reihenfolge: Baseline frisch lesen → zusammenführen → ein Update (kein anderer Schreiber geht verloren)")
check("else if(/apex/i.test(String(acc.firm || ''))) row.mt5_baseline = Object.assign({}, row.mt5_baseline || {}, { wd_recoverer: false })" in html
      and 'body["mt5_baseline"] = dict(body.get("mt5_baseline") or {}, wd_recoverer=False)' in app, "normaler Apex-WD trägt wd_recoverer:false (Tab-Rückfall + POST /admin/wd-plaene)")
lade("wd_ist_recoverer_plan")
check(ruf("wd_ist_recoverer_plan", {"winning_day": True, "master_firm": "Apex Trader", "master_symbol": "NQZ6", "mt5_baseline": {"wd_recoverer": False}}) is False,
      "Apex-WD auf NQ mit Marke false ist kein Recoverer")
check("st.kontoAt[String(id)] = atS" in html and "window._wdZyklus.kontoAt[String(k.id)] = _jetztM" in html, "Frische je Konto an beiden Ladewegen")

print()
print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER")
raise SystemExit(1 if fehler else 0)
