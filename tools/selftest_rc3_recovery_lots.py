#!/usr/bin/env python3
"""Selbsttest RC3 (Finn 11.11.2026 19:24 über den Master): Lots der Recovery-/Ausgleichs-Trades nach TP — < 500 $ → 3 MNQ · 500 bis < 1.000 $ → 4 MNQ ·
1.000 bis 2.000 $ → 7 MNQ · über 2.000 $ → 1 NQ. Prüft rc3_recovery_lots (alle Stufen + Grenzen, Standard aus, Max-Kontrakte, Farmer-Instrument NQ,
kaputte Regel) und den Einbau in tradeify_zyklus_konto (Felder kt bzw. instr/instr_kt wie der Apex-Recoverer; TP, Satz und hedge_eur unverändert).
Ohne Netz, Platzhalter-IDs (Zahlen von Jacobs Konto wie selftest_tradeify_zyklus). Aufruf: python3 tools/selftest_rc3_recovery_lots.py"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


R = app.rc3_recovery_lots
AN = {"an": True}
G = 150000.0

print("1) Staffel und Grenzen (Code-Stufen, Tradeify 150k)")
faelle = [(1, 3, "mnq"), (280, 3, "mnq"), (499.99, 3, "mnq"), (500, 4, "mnq"), (500.01, 4, "mnq"), (999.99, 4, "mnq"), (1000, 7, "mnq"),
          (1500, 7, "mnq"), (2000, 7, "mnq"), (2000.01, 1, "nq"), (3023, 1, "nq"), (9000, 1, "nq")]
abw = [(tp, R(tp, AN, G)) for tp, kt, ins in faelle if not (R(tp, AN, G) and (R(tp, AN, G)["kt"], R(tp, AN, G)["instr"]) == (kt, ins))]
check(not abw, f"< 500 → 3 MNQ · 500 → 4 · 999,99 → 4 · 1.000 → 7 · 2.000 → 7 · 2.000,01 → 1 NQ · 3.023 → 1 NQ ({abw})")
check([R(tp, AN, G)["stufe"] for tp in (499, 500, 1000, 2001)] == [0, 1, 2, 3], "Stufen-Index 0–3 im Beleg")
DB = {"an": True, "stufen": [{"ab": 0, "ab_inkl": True, "kt": 3, "instr": "mnq"}, {"ab": 500, "ab_inkl": True, "kt": 4, "instr": "mnq"},
                             {"ab": 1000, "ab_inkl": True, "kt": 7, "instr": "mnq"}, {"ab": 2000, "ab_inkl": False, "kt": 1, "instr": "nq"}],
      "max_mnq": {"25000": 20, "50000": 40, "100000": 80, "150000": 120}}
check(all((R(tp, DB, G)["kt"], R(tp, DB, G)["instr"]) == (kt, ins) for tp, kt, ins in faelle), "dieselbe Staffel aus der DB-Zeile (sql/2026-11-11_rc3_recovery_lots.sql)")

print("2) Standard aus = wie heute")
check(R(3023, None, G) is None and R(3023, {}, G) is None and R(3023, {"an": False}, G) is None and R(3023, {"an": "ja"}, G) is None,
      "keine Regel / an fehlt / an False / an kein bool → None (Menge aus der Farmer-Spanne)")
check(R(0, AN, G) is None and R(-5, AN, G) is None and R(None, AN, G) is None and R("x", AN, G) is None, "TP ≤ 0 / leer / kein Wert → None")
check(R(3023, {"an": True, "stufen": [{"ab": 0, "kt": 3, "instr": "mes"}]}, G) is None and R(3023, {"an": True, "stufen": [{"ab": 0, "kt": 2.5, "instr": "mnq"}]}, G) is None
      and R(3023, {"an": True, "stufen": [{"ab": -1, "kt": 3, "instr": "mnq"}]}, G) is None, "kaputte Stufe (Instrument, halber Kontrakt, ab < 0) → ganze Staffel aus")
check(R(100, {"an": True, "stufen": [{"ab": 500, "kt": 4, "instr": "mnq"}]}, G) is None, "TP unter der ersten Stufe → None")

print("3) Max-Kontrakte des Kontos (MNQ-Äquivalent, 1 NQ = 10 MNQ) — darüber die nächstkleinere Stufe")
check(all(R(3023, AN, g)["instr"] == "nq" and R(1500, AN, g)["kt"] == 7 for g in (25000, 50000, 100000, 150000)),
      "Tradeify 25K–150K (20/40/80/120 MNQ): alle Stufen passen")
check(R(3023, AN, 75000.0) is None and R(3023, AN, None) is None, "Größe ohne bekanntes Limit / unbekannt → None (nie über ein unbekanntes Limit)")
k5 = {"an": True, "max_mnq": {"150000": 5}}
r5 = R(1500, k5, G)
check((r5["kt"], r5["instr"], r5["kleiner"], r5["stufe"], r5["stufe_tp"]) == (4, "mnq", True, 1, 2) and "statt 7 MNQ die kleinere Stufe 4 MNQ" in r5["hinweis"],
      f"Limit 5 MNQ: 7 MNQ passt nicht → nächstkleinere Stufe 4 MNQ mit Hinweis ({r5['hinweis']})")
r5n = R(3023, k5, G)
check((r5n["kt"], r5n["instr"], r5n["kleiner"]) == (4, "mnq", True), "Limit 5 MNQ: 1 NQ (10) und 7 MNQ passen nicht → 4 MNQ")
check((R(3023, {"an": True, "max_mnq": {"150000": 12}}, G)["kt"], R(3023, {"an": True, "max_mnq": {"150000": 12}}, G)["instr"]) == (1, "nq")
      and R(3023, AN, G)["kleiner"] is False and R(3023, AN, G)["hinweis"] == "", "Limit 12 MNQ: 1 NQ passt, kein Hinweis")
check(R(400, {"an": True, "max_mnq": {"150000": 2}}, G) is None and R(3023, {"an": True, "max_mnq": {"150000": 2}}, G) is None,
      "Limit 2 MNQ: keine Stufe passt → None (wie bisher)")
check(R(3023, {"an": True, "max_mnq": {"150000": 0}}, G) is None, "Limit 0 → None")
check(R(1500, AN, G, "lucid") is None and R(1500, dict(AN, max_mnq={"150000": 40}), G, "lucid")["kt"] == 7,
      "Lucid ohne eigenes Limit → None (kein Code-Wert, nicht in firm_rules.json); mit max_mnq → Staffel")
check([R(1500, AN, g, "apex")["kt"] if R(1500, AN, g, "apex") else None for g in (25000, 50000, 100000, 150000, 250000)] == [None, 7, 7, 7, None]
      and R(3023, AN, 50000.0, "apex")["instr"] == "nq", "Apex 50K/100K/150K (Half-Size 20/30/40 MNQ): Staffel; 25K/250K ohne Wert → None (1 NQ wie bisher)")

print("4) Felder am zyklus-Dict (Prüfer RC3 SOLLTE 1: MNQ ausdrücklich)")
check(app.rc3_felder(R(1500, AN, G)) == {"instr": "mnq", "instr_kt": 7, "kt": 7} and app.rc3_felder(R(3023, AN, G)) == {"instr": "nq", "instr_kt": 1, "kt": None},
      "MNQ-Stufe → instr 'mnq' + instr_kt + kt (nie das Instrument des Farmers); NQ → instr 'nq' + instr_kt, kt leer")
check(app.rc3_grund(R(1500, AN, G)) == " · 7 MNQ" and app.rc3_grund(r5).startswith(" · 4 MNQ (Max-Kontrakte 150k = 5 MNQ"), "Grund: Menge, bei kleinerer Stufe mit Hinweis")

print("5) Einbau in tradeify_zyklus_konto (Jacob, Zyklus 2 im Minus)")
JACOB = {"id": "c0000000-0000-0000-0000-00000000000c", "name": "150k TFY-STUB-0001 → Winning Days", "firm": "Tradeify", "user_id": "u1", "max_drawdown": 4500}
FRISCH = "2026-11-02T13:38:19+00:00"
PAY = [{"requested_at": "2026-10-22", "status": "received"}]
T = [("2026-10-22T08:23:00+00:00", 270.2, 166047.92), ("2026-10-23T13:32:00+00:00", 263.2, 161818.12), ("2026-10-26T06:35:00+00:00", -1440.8, 162081.32),
     ("2026-10-27T06:41:00+00:00", -1400, 160640.52), ("2026-10-28T12:00:00+00:00", 279.3, 158862.72), ("2026-10-29T09:44:00+00:00", 277.8, 159142.02),
     ("2026-10-30T04:19:00+00:00", 274.8, 159419.82), ("2026-11-02T12:53:00+00:00", 270.33, 159694.62)]
PL = [{"status": "completed", "started_at": s, "ended_at": s, "master_pl": pl, "tv": {"balance_start": bs}} for s, pl, bs in T]
VP = {"regeln": {"fu": {"tradeify": [270, 290]}, "staffel": [50, 60, 70, 80, 90]}}
TZ = app.tradeify_zyklus_konto
RN = ("kt", "instr", "instr_kt", "recovery_lots")
ohne = lambda d: {k: v for k, v in d.items() if k not in RN and k != "grund"}   # noqa: E731
FELD = lambda kt, ins: {"instr": "nq", "instr_kt": kt, "kt": None} if ins == "nq" else {"instr": "mnq", "instr_kt": kt, "kt": kt}   # noqa: E731
stufen = []
for live, soll in ((161810.0, (3, "mnq")), (161420.0, (3, "mnq")), (161260.0, (4, "mnq")), (160700.0, (7, "mnq")), (159964.95, (7, "mnq")), (159300.0, (1, "nq"))):
    z0 = TZ(JACOB, PL, PAY, 5, 5, VP, live, FRISCH)
    z1 = TZ(JACOB, PL, PAY, 5, 5, VP, live, FRISCH, rc_regel=DB)
    rl = z1.get("recovery_lots") or {}
    ok = z1["aktiv"] and (rl.get("kt"), rl.get("instr")) == soll and {k: z1.get(k) for k in ("instr", "instr_kt", "kt")} == FELD(*soll)
    ok = ok and ohne(z0) == ohne(z1) and not any(k in z0 for k in RN) and z1["grund"] == z0["grund"] + f" · {soll[0]} {soll[1].upper()}"
    stufen.append((live, z1["ziel"], soll, ok))
check(all(x[3] for x in stufen), "Ausgleichs-Trade: Menge nach TP (MNQ → instr 'mnq' + kt; NQ → instr 'nq' + instr_kt, kt leer); "
      f"TP, Satz, hedge_eur und alles andere gleich wie ohne Regel; Grund nennt die Menge ({[(x[1], x[2]) for x in stufen]})")
check(sorted({x[2] for x in stufen}) == sorted({(3, "mnq"), (4, "mnq"), (7, "mnq"), (1, "nq")}), "alle vier Stufen über echte Ausgleichs-TPs erreicht")
z3 = TZ(JACOB, PL, PAY, 3, 5, VP, 159964.95, FRISCH, rc_regel=DB)
check(not z3["aktiv"] and not any(k in z3 for k in RN), "3/5 im Minus (normaler WD, kein Ausgleich) → keine Menge (Farmer-Spanne wie heute)")
zp = TZ(JACOB, PL, PAY, 5, 5, VP, 161830.0, FRISCH, rc_regel=DB)
check(not zp["aktiv"] and not any(k in zp for k in RN), "Zyklus im Plus → keine Menge")
zn = TZ(JACOB, PL, PAY, 5, 5, dict(VP, instr="nq"), 160700.0, FRISCH, rc_regel=DB)
check(zn["aktiv"] and {k: zn.get(k) for k in ("instr", "instr_kt", "kt")} == FELD(7, "mnq"), "Farmer auf NQ + MNQ-Stufe → ausdrücklich 7 MNQ (nie 7 NQ)")
check(ohne(TZ(JACOB, PL, PAY, 5, 5, VP, 159964.95, FRISCH, rc_regel={"an": False})) == ohne(TZ(JACOB, PL, PAY, 5, 5, VP, 159964.95, FRISCH))
      and not any(k in TZ(JACOB, PL, PAY, 5, 5, VP, 159964.95, FRISCH, rc_regel={"an": False}) for k in RN), "Regel aus → bitgleich zu ohne Regel")
zl = TZ(dict(JACOB, name="150k LUCID-STUB → Winning Days", firm="Lucid"), PL, PAY, 5, 5, VP, 160700.0, FRISCH,
        rc_regel=dict(DB, max_mnq={"150000": 40}))
check((zl.get("recovery_lots") or {}).get("kt") == 7 or not zl["aktiv"], f"Lucid über denselben Weg ({zl.get('grund_code')}, {zl.get('recovery_lots')})")

print("6) Apex-Recoverer (wd_zyklus_konto, Mike 150k, Verlusttag −3.998 $)")
REGEL = {"stuetz": [{"v": 2000, "ziel": 750, "satz": 400}, {"v": 4000, "ziel": 1500, "satz": 300}],
         "firmen": ["apex", "apex100"], "ab_zyklus": 2, "bis": "2x_bester", "satz_normal": None, "kt": None, "aktiv": True}
VPA = {"regeln": {"fu": {"apex": [370, 390], "apex100": [320, 340]}, "staffelFirma": {"apex": [{"von": 0, "eur": 50}, {"von": 4000, "eur": 100}, {"von": 10000, "eur": 175}]}}}
MIKE = {"id": "k1", "name": "150k PAAPEX 0001", "firm": "Apex", "wd_farm": True, "live_balance": 160029.26}
PAYA = [{"requested_at": "2026-10-26", "status": "received"}]
pa = lambda tag, pnl: {"status": "completed", "started_at": f"{tag}T10:00:00+00:00", "master_pl": pnl, "route": "tvv2"}   # noqa: E731
MP = [pa("2026-10-27", 374.88), pa("2026-10-30", -3998.16)]
ZK = app.wd_zyklus_konto
a0, a1 = ZK(dict(MIKE), REGEL, VPA, MP, PAYA), ZK(dict(MIKE), REGEL, VPA, MP, PAYA, rc_regel=AN)
check((a0["instr"], a0["instr_kt"], a0["kt"]) == ("nq", 1, None) and "recovery_lots" not in a0, "ohne Einstellung: 1 NQ wie bisher")
check(a1["aktiv"] and a1["ziel"] == 1499 and {k: a1.get(k) for k in ("instr", "instr_kt", "kt")} == FELD(7, "mnq") and a1["grund"].endswith(" · 7 MNQ")
      and ohne(a0) == ohne(a1), f"Ziel 1.499 $ → 7 MNQ; Ziel, Satz, Hedge-€ unverändert ({a1['grund'][-40:]})")
a2 = ZK(dict(MIKE), REGEL, VPA, [pa("2026-10-27", 374.88), pa("2026-10-30", -1500.0)], PAYA, rc_regel=AN)
check(a2["aktiv"] and a2["recovery_lots"]["kt"] == 4 and 500 <= a2["ziel"] < 1000, f"kleinerer Verlust → Ziel {a2['ziel']} $ → 4 MNQ")
a3 = ZK(dict(MIKE), REGEL, VPA, MP, PAYA, rc_regel={"an": True, "stufen": [{"ab": 0, "kt": 3, "instr": "mnq"}, {"ab": 1000, "kt": 1, "instr": "nq"}]})
check({k: a3.get(k) for k in ("instr", "instr_kt", "kt")} == FELD(1, "nq"), "eigene Stufen: Ziel 1.499 → 1 NQ")
a4 = ZK(dict(MIKE), REGEL, VPA, [], [], rc_regel=AN)
check(not a4["aktiv"] and a4["instr"] is None and "recovery_lots" not in a4, "ohne Recoverer-Zyklus: nichts (normale Apex-WD wie bisher)")
a5 = ZK(dict(MIKE, name="25k PAAPEX 0002"), REGEL, VPA, MP, PAYA, rc_regel=AN)
check(a5.get("instr") == "nq" and "recovery_lots" not in a5, "Apex 25K ohne Limit-Wert → 1 NQ wie bisher")

print("7) Recoverer-Marke statt NQ-Symbol")
W = app.wd_ist_recoverer_plan
apx = {"winning_day": True, "master_firm": "Apex"}
check(W(dict(apx, master_symbol="MNQZ6", mt5_baseline={"wd_recoverer": True})) and W(dict(apx, master_symbol="MNQZ6", wd_recoverer="true")),
      "Marke (mt5_baseline bzw. Select-Alias) → Recoverer, auch auf MNQ")
check(not W(dict(apx, master_symbol="NQZ6", mt5_baseline={"wd_recoverer": False})) and not W(dict(apx, master_symbol="NQZ6", wd_recoverer="false")),
      "Marke false → kein Recoverer, auch auf NQ")
check(W(dict(apx, master_symbol="NQZ6")) and W(dict(apx, master_symbol_root="NQ", wd_recoverer=None)) and not W(dict(apx, master_symbol="MNQZ6")),
      "ohne Marke (Pläne von vorher): Apex-WD auf NQ wie bisher")
_bl = {"wd_recoverer": True, "wd_sl": None}
check(app.wd_sl_nach_rechnen(None, dict(apx, master_symbol="MNQZ6", mt5_baseline=_bl), None, None, [])[0]["ohne"] is True
      and "Recoverer" in str(app.wd_sl_nach_rechnen(None, dict(apx, master_symbol="MNQZ6", mt5_baseline=_bl), None, None, [])[0]["grund"]),
      "Rückfall-Plan mit Marke auf MNQ: kein SL-Würfel („Recoverer — kein Würfel“)")
nq = app.wd_naechster_plan([{"id": "a", "master_account_id": "k", "status": "planned", "start_um": "2026-11-12T05:00:00Z", "winning_day": True, "master_firm": "Apex",
                             "master_symbol": "MNQZ6"},
                            {"id": "b", "master_account_id": "k", "status": "planned", "start_um": "2026-11-12T09:00:00Z", "winning_day": True, "master_firm": "Apex",
                             "master_symbol": "MNQZ6", "wd_recoverer": "true"}])
check(nq["k"]["id"] == "b" and nq["k"]["recoverer"] is True, "Rang in wd_naechster_plan: MNQ-Recoverer mit Marke zuerst")
SRC = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
check(SRC.count("wd_recoverer:mt5_baseline->>wd_recoverer") == 5, "Marke in den fünf Selects (Alarm-Takt, Bestätigen-Alarm, nächster Plan, Zu bestätigen, GET /admin/wd-plaene)")
check('if (r or {}).get("wd_recoverer") is True:\n                    body["mt5_baseline"] = dict(body.get("mt5_baseline") or {}, wd_recoverer=True)' in SRC
      and 'body["mt5_baseline"] = dict(body.get("mt5_baseline") or {}, wd_ausgleich=True)' in SRC,
      "POST /admin/wd-plaene übernimmt die Marke vom Farmer (und überschreibt wd_ausgleich nicht mehr)")
i_m, i_sl = SRC.find('get("wd_recoverer") is True:\n                    body["mt5_baseline"]'), SRC.find('if sl_regel and (wd_ist_recoverer_plan(body)')
check(0 < i_m < i_sl, "Marke steht vor der SL-Würfel-Ausnahme")

print("8) Frontend (echte Funktionen aus prophos.html in JavaScriptCore)")
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
js_teile = [re.search(r"  function wdRecovererKt\(zy\)\{[^\n]*\}", HTML).group(0), re.search(r"  const wdNqOhneMenge = [^\n]*", HTML).group(0),
            re.search(r"  const wdRecovererSymbol = [^\n]*", HTML).group(0),
            HTML[HTML.index("  function planIstRecoverer(p){"):HTML.index("\n  }\n", HTML.index("  function planIstRecoverer(p){")) + 4]]
if shutil.which("osascript"):
    js = ("function run(){\n" + "\n".join(js_teile) + "\nvar Z = " + json.dumps({"m": FELD(7, "mnq"), "n": FELD(1, "nq"), "alt": {"kt": None}}) +
          ";\nvar iF = function(z){ return (z && (z.instr === 'nq' || z.instr === 'mnq')) ? z.instr : null };\n"
          "var r = { kt: [wdRecovererKt(Z.m), wdRecovererKt(Z.n), wdRecovererKt(Z.alt)],"
          " sym: [wdRecovererSymbol('MNQZ6', iF(Z.m)), wdRecovererSymbol('NQZ6', iF(Z.m)), wdRecovererSymbol('MNQZ6', iF(Z.n)), wdRecovererSymbol('MNQZ6', iF(Z.alt))],"
          " nqOhne: wdNqOhneMenge(iF(Z.n), wdRecovererKt(Z.n)),"
          " rec: [planIstRecoverer({ winningDay: true, masterFirm: 'Apex', masterSymbol: 'MNQZ6', mt5Baseline: { wd_recoverer: true } }),"
          " planIstRecoverer({ winning_day: true, master_firm: 'Apex', master_symbol: 'MNQZ6', wd_recoverer: 'true' }),"
          " planIstRecoverer({ winningDay: true, masterFirm: 'Apex', masterSymbol: 'NQZ6' }),"
          " planIstRecoverer({ winningDay: true, masterFirm: 'Apex', masterSymbol: 'NQZ6', mt5Baseline: { wd_recoverer: false } }),"
          " planIstRecoverer({ winningDay: true, masterFirm: 'Apex', masterSymbol: 'MNQZ6' })] };\nreturn JSON.stringify(r) }")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
    aus = subprocess.run(["osascript", "-l", "JavaScript", f.name], capture_output=True, text=True, timeout=30)
    os.unlink(f.name)
    check(aus.returncode == 0, f"Frontend-Funktionen laufen ({aus.stderr.strip()[:160]})")
    if aus.returncode == 0:
        j = json.loads(aus.stdout)
        check(j["kt"] == [7, 1, None], f"wdRecovererKt: 7 MNQ → 7, 1 NQ → 1 (instr_kt), alter Stand ohne Feld → null ({j['kt']})")
        check(j["sym"] == ["MNQZ6", "MNQZ6", "NQZ6", "MNQZ6"], f"wdRecovererSymbol: 'mnq' → MNQ auch aus NQ (Farmer auf NQ), 'nq' → NQ, ohne → Farmer-Symbol ({j['sym']})")
        check(j["nqOhne"] is False, "wdNqOhneMenge: 1 NQ hat seine Menge")
        check(j["rec"] == [True, True, True, False, False], f"planIstRecoverer: Marke zuerst, ohne Marke NQ wie bisher ({j['rec']})")
else:
    check(False, "osascript fehlt — Frontend-Teil nicht geprüft")
check("if(zyT && zyT.art !== 'tradeify') pr.wd_recoverer = true" in HTML, "Mac-Weg (wdPlaeneAnlegen): Marke an Railway")
check("if((zyAus && zyAus.art !== 'tradeify') || (extra && extra.instr && /apex/i.test(String(acc.firm || ''))))\n      row.mt5_baseline = Object.assign({}, row.mt5_baseline || {}, { wd_recoverer: true })" in HTML,
      "PC-Tab-Weg (wdPlanAnlegen): Marke am Plan, auch Selbstheilung mit festem Instrument bei Apex (Prüfer KANN 3)")
check("z.wd_recoverer = p.wd_recoverer ?? null" in HTML and "wd_recoverer: z.wd_recoverer ?? null })" in HTML, "WD-Karten Läuft/Wartet/Braucht dich: Marke durchgereicht (Prüfer SOLLTE 1)")
check("{ wd_recoverer: true, wd_sl: wdSlOhneWuerfel('Recoverer — kein Würfel') }" in HTML and ".update(Object.assign({}, alt.upd, { mt5_baseline: blNeu }))" in HTML, "Altplan-Weg: erst die Marke, dann umstellen")
check("instrFest = (zy && (zy.instr === 'nq' || zy.instr === 'mnq')) ? zy.instr : null" in HTML and "_tpNqMode = instrFest ? instrFest : (vp.instr === 'nq' ? 'nq' : 'mnq')" in HTML,
      "Würfel: festes Instrument (auch MNQ) vor dem des Farmers, auch für die Hedge-Rechnung")

print("9) Railway-Weg")
check('rc_regel=rc_je.get(zyklus_plus_key(k) or "tradeify"))' in SRC and "_rc_alle = _rc3_regeln_lesen()" in SRC and "rc_regel=_rc_apex)" in SRC,
      "_tradeify_zyklus_anhaengen und _wd_zyklus_anhaengen lesen recovery_lots und geben die Regel je Firma mit")
app._rc3_cache.update(bis=0.0, wert={})
_sb_alt = app.sb_select
app.sb_select = lambda t, p: (_ for _ in ()).throw(RuntimeError("weg"))
check(app._rc3_regeln_lesen() == {}, "Lesefehler / Spalte fehlt → {} (aus)")
app._rc3_cache.update(bis=0.0, wert={})
app.sb_select = lambda t, p: [{"recovery_lots": {"tradeify": DB}}] if (t == "wd_farmer_regeln" and p.get("select") == "recovery_lots") else []
check(app._rc3_regeln_lesen() == {"tradeify": DB}, "Spalte gelesen (60 s gemerkt)")
app.sb_select = _sb_alt
sq = open(os.path.join(WURZEL, "sql", "2026-11-11_rc3_recovery_lots.sql"), encoding="utf-8").read()
check("add column if not exists recovery_lots jsonb" in sq and all(f"'{f}'," in sq for f in ("tradeify", "lucid", "apex")) and "'topstep'" not in sq
      and re.search(r"'ab', 2000, 'ab_inkl', false, 'kt', 1, 'instr', 'nq'", sq) is not None,
      "SQL-Datei: Spalte + Tradeify/Lucid/Apex an (Topstep ohne Weg), 2.000 noch 7 MNQ, darüber 1 NQ")

print()
print("FEHLER: " + ", ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
