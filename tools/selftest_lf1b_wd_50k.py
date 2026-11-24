#!/usr/bin/env python3
"""Selbsttest LF1b-WD (Master 16.11.2026, Finn): eigene WD-TP-Schlüssel für die 50k-Größen (lucid50, fnfutures50 — wie apex100) im Winning-Day-Farmer.
Kern: (1) Schlüssel: Lucid/FNF Futures 50k → eigener Schlüssel, alles andere wie bisher (Lucid/Tradeify 150k bitgleich); (2) TP 170–190 / 220–240 als Vorgabe,
Kontrakte ohne eigene Werte = die der Firma × 50k/150k; (3) Hedge: KEIN Rückfall — ohne eigene Hedge-Tabelle plant der Farmer sichtbar nichts („Hedge-Werte
fehlen“), der Lucid-Ausgleich wird nicht aktiv (kein Trade mit Hedge 0); (4) Firmen-Regeln (E4), fester SL und Freigabe bleiben beim Firmen-Schlüssel.
Diff gegen main vor LF1 (BASIS 1728de57): Ausgleich Tradeify/Lucid 150k und die Anzeige der anderen Firmen unverändert.
Aufruf: python3 tools/selftest_lf1b_wd_50k.py"""
import importlib.util
import json
import os
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
BASIS = "1728de57"   # main vor LF1 (fest)


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


print("— 1) Schlüssel —")
S = app.wd_tp_schluessel
ok(S("Lucid Trading", "50000") == "lucid50" and S("Lucid Trading", 50000) == "lucid50" and S("FundedNext Futures", "50000") == "fnfutures50",
   "Lucid / FNF Futures 50k → lucid50 / fnfutures50")
ok(all(S(f, g) == app.fdp_wd_schluessel(f, g) for f in ("Lucid Trading", "FundedNext Futures", "Tradeify", "Apex Trader", "Topstep", "FTMO Futures", "MFFU")
       for g in ("100000", "150000", None)) and S("Tradeify", "50000") == "tradeify" and S("Apex Trader", "50000") == "apex",
   "alle anderen Größen/Firmen: wie fdp_wd_schluessel (Tradeify/Apex 50k ohne eigenen Schlüssel)")
ok(app.fdp_wd_schluessel("Lucid Trading", "50000") == "lucid", "Firmen-Schlüssel (Regeln, fester SL, Freigabe) bleibt „lucid“")
ok(app.WD_FU_STANDARD["lucid50"] == [170, 190] and app.WD_FU_STANDARD["fnfutures50"] == [220, 240], "Vorgaben: Lucid 50k 170–190 $, FNF 50k 220–240 $")

print("— 2) Anzeige „Was ist ein Winning Day“ (Funded-Planer) —")
VP_LIVE = {"instr": "mnq", "kt": 1, "regeln": {"fu": {"lucid": [268, 280], "fnfutures": [270, 290], "tradeify": [225, 244]},
                                                "kt": {"lucid": [2, 3], "fnfutures": [2, 3], "tradeify": [2, 3]}}}
LU = {"name": "Lucid Trading", "je_groesse": {"50000": {}, "150000": {}}}
z = {r["groesse"]: r for r in app.fdp_wd_anzeige(LU, VP_LIVE, None)["groessen"]}
ok(z["50000"]["schluessel"] == "lucid50" and z["50000"]["tp"] == [170, 190] and z["50000"]["tp_quelle"] == "standard" and z["50000"]["kt"] == [1, 1]
   and z["50000"]["min_usd"] == 150.0, f"Lucid 50k: TP 170–190 (Vorgabe), Kontrakte 2–3 × 1/3 → 1–1, Linie 150 $ ({z['50000']})")
ok(z["150000"]["schluessel"] == "lucid" and z["150000"]["tp"] == [268, 280] and z["150000"]["kt"] == [2, 3], "Lucid 150k: Werte des Farmers wie bisher")
z2 = {r["groesse"]: r for r in app.fdp_wd_anzeige(LU, dict(VP_LIVE, regeln=dict(VP_LIVE["regeln"], fu=dict(VP_LIVE["regeln"]["fu"], lucid50=[175, 185]),
                                                                           kt=dict(VP_LIVE["regeln"]["kt"], lucid50=[2, 2]))), None)["groessen"]}
ok(z2["50000"]["tp"] == [175, 185] and z2["50000"]["tp_quelle"] == "wd-farmer" and z2["50000"]["kt"] == [2, 2], "eigene Farmer-Werte für lucid50 gelten")

print(f"— 3) Lucid-Ausgleich 50k, Diff gegen {BASIS} —")
alt = None
try:
    src = subprocess.run(["git", "-C", WURZEL, "show", BASIS + ":app.py"], capture_output=True, text=True, timeout=60, check=True).stdout
    d = tempfile.mkdtemp(prefix="lf1bwd_alt_")
    with open(os.path.join(d, "app_alt_lf1bwd.py"), "w", encoding="utf-8") as fh:
        fh.write(src)
    sp = importlib.util.spec_from_file_location("app_alt_lf1bwd", os.path.join(d, "app_alt_lf1bwd.py"))
    alt = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(alt)
except Exception as e:  # noqa: BLE001
    print(f"   {BASIS} nicht ladbar: {type(e).__name__}: {e}")
FRISCH = "2026-11-02T13:38:19+00:00"
PAY = [{"requested_at": "2026-10-22", "status": "received"}]


def ag2_stimmig(plaene, live):
    """AG2 (24.11.2026): Fehlbetrag = Trade-Summe, Balance nur Gegenprobe (> 50 $ daneben → kein Ausgleich). Die Fixtures dieses Tests variieren nur die
    Live-Balance; damit Trades und Balance zusammenpassen wie am echten Konto, ist der P&L jedes Trades die Differenz zum nächsten balance_start, der letzte
    die Differenz zur Live-Balance. Eine Payout-Abbuchung vor dem ersten Trade des Zyklus fällt in den alten Zyklus (wie am Konto)."""
    m = [dict(p) for p in (plaene or ())]
    seq = sorted([p for p in m if str(p.get("status") or "") in ("completed", "review") and isinstance(p.get("tv"), dict)
                  and p["tv"].get("balance_start") is not None], key=lambda p: str(p.get("started_at") or ""))
    for a, b in zip(seq, seq[1:]):
        a["master_pl"] = round(float(b["tv"]["balance_start"]) - float(a["tv"]["balance_start"]), 2)
    if seq and isinstance(live, (int, float)):
        seq[-1]["master_pl"] = round(float(live) - float(seq[-1]["tv"]["balance_start"]), 2)
    return m


def ag2_wrap(fn):
    def w(konto, plaene, payouts, wd_stand, wd_ziel, vorplan, live, *a, **k):
        return fn(konto, ag2_stimmig(plaene, live), payouts, wd_stand, wd_ziel, vorplan, live, *a, **k)
    return w


def plaene(t, live=None):
    return ag2_stimmig([{"status": "completed", "started_at": s, "ended_at": s, "master_pl": pl, "tv": {"balance_start": bs}} for s, pl, bs in t], live)


T150 = [("2026-10-22T08:23:00+00:00", 270.2, 166047.92), ("2026-10-23T13:32:00+00:00", 263.2, 161818.12), ("2026-10-26T06:35:00+00:00", -1440.8, 162081.32),
        ("2026-11-02T12:53:00+00:00", 270.33, 160640.52)]
T50 = [("2026-10-22T08:23:00+00:00", 150.0, 51000.0), ("2026-10-23T13:32:00+00:00", 160.0, 52000.0), ("2026-10-26T06:35:00+00:00", -900.0, 52160.0),
       ("2026-11-02T12:53:00+00:00", 155.0, 51260.0)]
VP_AUS = {"regeln": {"fu": {"tradeify": [225, 244], "lucid": [268, 280]}, "staffel": [50, 60, 70, 80, 90],
                     "staffelFirma": {"lucid": [{"von": 0, "eur": 60}, {"von": 2000, "eur": 80}], "tradeify": [{"von": 0, "eur": 55}]}}}
if alt is not None:
    abw, n = 0, 0
    for firma, name, dd, t, live in (("Tradeify", "150k T-1 → Winning Days", 4500, T150, 159964.95), ("Lucid Trading", "150k L-1 → Winning Days", 4500, T150, 159964.95),
                                     ("Tradeify", "50k T-2 → Winning Days", 2000, T50, 51415.0)):
        for stand in (3, 4, 5):
            k = {"id": "k-" + name[:5], "name": name, "firm": firma, "user_id": "u1", "max_drawdown": dd, "account_type": "winning_days"}
            a = app.tradeify_zyklus_konto(k, plaene(t, live), PAY, stand, 5, VP_AUS, live, FRISCH)
            b = alt.tradeify_zyklus_konto(k, plaene(t, live), PAY, stand, 5, VP_AUS, live, FRISCH)
            n += 1
            abw += a != b
    ok(alt is not None and abw == 0, f"{n} Fälle Tradeify 150k / Lucid 150k / Tradeify 50k: Ausgleich wie vor LF1 ({abw} Abweichungen)")
L50 = {"id": "k-l50", "name": "50k L-5 → Winning Days", "firm": "Lucid Trading", "user_id": "u1", "max_drawdown": 2000, "account_type": "winning_days"}
z = app.tradeify_zyklus_konto(L50, plaene(T50, 51415.0), PAY, 5, 5, VP_AUS, 51415.0, FRISCH)
ok(z["gesperrt"] and not z["aktiv"] and z["grund_code"] == "hedge_fehlt" and "Hedge-Werte fehlen für Lucid 50k" in z["grund"] and not z.get("hedge_eur"),
   f"Lucid 50k ohne eigene Hedge-Tabelle: Payout gesperrt, KEIN Ausgleichs-Trade (kein Hedge 0), Grund sichtbar ({z['grund']})")
VP_50 = {"regeln": dict(VP_AUS["regeln"], staffelFirma=dict(VP_AUS["regeln"]["staffelFirma"], lucid50=[{"von": 0, "eur": 30}]))}
z = app.tradeify_zyklus_konto(L50, plaene(T50, 51415.0), PAY, 5, 5, VP_50, 51415.0, FRISCH)
ok(z["aktiv"] and z["ziel_normal"] == 180 and z["satz"] == round(30 / 180 * 1000, 2) and z["ziel"] >= 586 and z["hedge_eur"] > 0,
   f"mit eigener Tabelle lucid50 (30 €): Ausgleich aktiv, Ziel normal 180 (Mitte 170–190), Satz 30 €/180 $ ({z.get('ziel')} $ / {z.get('hedge_eur')} €)")
VP_50b = {"regeln": dict(VP_50["regeln"], fu=dict(VP_50["regeln"]["fu"], lucid50=[160, 160]))}
z = app.tradeify_zyklus_konto(L50, plaene(T50, 51415.0), PAY, 5, 5, VP_50b, 51415.0, FRISCH)
ok(z["ziel_normal"] == 160, "eigene TP-Spanne lucid50 aus dem Farmer gilt")

print("— 4) Frontend (prophos.html, JavaScriptCore) —")
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()


def fn(name):
    i = html.index(f"  function {name}(")
    return html[i:html.index("\n  }\n", i) + 4]


def zeile(praefix):
    i = html.index(praefix)
    return html[i:html.index("\n", i)] + "\n"


js = ("const istTradeifyCfd = f => /tradeify/i.test(String(f || '')) && /cfd/i.test(String(f || ''));\n"
      + zeile("  const TP_VP_VORGABE = ") + zeile("  function wdBasisKey(") + zeile("  function wd50kName(") + zeile("  function wdIst50kKey(") + fn("kontoIstTradeifyLive") + zeile("  const TP_VP_FIRMEN = ")   # TL1 (19.11.2026): Tradeify Live
      + fn("tpVpLucidWieTradeify") + fn("tpVpApex100") + fn("tpVp50k") + fn("tpVorplanFirmaKey") + fn("wdKtSpanne")
      + zeile("  function tpVorplanSpanne(") + zeile("  function tpVorplanIstFunded(") + fn("tpVorplanZeile") + fn("tpWdHedgeFehlt") + fn("tpWdHedgeEur") + """
const tpTopstepMll = () => 0, kontoIstTopstepExpress = () => false, tpKontoGroesseAusName = () => 50000, wdZyklusVon = () => null, tpVorplanSlaveWaehrung = e => e;
const tpVorplanStaffel = (plus, l) => Array.isArray(l) && l.length ? Number(l[0].eur || 0) : 0;
const K = (firm, name, sb) => ({ firm, name, startingBalance: sb, type: 'winning_days', maxDrawdown: 2000 });
const vp = { kt: 1, regeln: { kt: { lucid: [2, 3], fnfutures: [2, 3], tradeify: [2, 3] } } };
const R = { fu: { lucid: [268, 280], tradeify: [225, 244] }, staffel: [{ von: 0, eur: 50 }], staffelFirma: { lucid: [{ von: 0, eur: 60 }] } };
const r = {};
r.keys = [tpVorplanFirmaKey('Lucid Trading', K('Lucid Trading', '50k L1 → WD')), tpVorplanFirmaKey('Lucid Trading', K('Lucid Trading', '150k L1 → WD')),
  tpVorplanFirmaKey('Lucid Trading', K('Lucid Trading', 'L1 ohne Größe', 50000)), tpVorplanFirmaKey('Lucid Trading', K('Lucid Trading', 'L1 ohne Größe')),
  tpVorplanFirmaKey('FundedNext Futures', K('FundedNext Futures', '50k F1')), tpVorplanFirmaKey('FundedNext Futures', K('FundedNext Futures', '150k F1')),
  tpVorplanFirmaKey('Tradeify', K('Tradeify', '50k T1')), tpVorplanFirmaKey('Apex Trader', K('Apex Trader', '100k A1')), tpVorplanFirmaKey('FundedNext', K('FundedNext', '50k C1'))];
r.basis = [wdBasisKey('lucid50'), wdBasisKey('fnfutures50'), wdBasisKey('apex100'), wdBasisKey('lucid')];
r.kt = [wdKtSpanne('lucid50', vp), wdKtSpanne('fnfutures50', vp), wdKtSpanne('lucid', vp), wdKtSpanne('lucid50', { kt: 1, regeln: { kt: { lucid: [2, 3], lucid50: [2, 2] } } }),
  wdKtSpanne('lucid50', { kt: 1, regeln: { kt: {} } }), wdKtSpanne('lucid50', { kt: 1, regeln: { kt: { lucid: [6, 9] } } })];
const z1 = tpVorplanZeile(K('Lucid Trading', '50k L1 → WD'), { regeln: R, live: 51000, zufall: 0.5 });
const z2 = tpVorplanZeile(K('Lucid Trading', '50k L1 → WD'), { regeln: Object.assign({}, R, { staffelFirma: { lucid: R.staffelFirma.lucid, lucid50: [{ von: 0, eur: 25 }] } }), live: 51000, zufall: 0.5 });
const z3 = tpVorplanZeile(K('Lucid Trading', '150k L1 → WD', 150000), { regeln: R, live: 151000, zufall: 0.5 });
const z4 = tpVorplanZeile(K('FundedNext Futures', '50k F1'), { regeln: R, live: 51000, zufall: 0.5 });
r.z = [z1.fehler || null, z2.fehler || null, z2.slaveEur, z2.tpVon, z2.tpBis, z3.fehler || null, z3.slaveEur, z3.tpVon, z4.fehler || null];
// LF1e: Hand-Popup Winning Day — Vorbelegung „Risiko Slave“
var accounts = [Object.assign(K('Lucid Trading', '50k L1 → WD'), { id: 'a50' }), Object.assign(K('Lucid Trading', '150k L1 → WD', 150000), { id: 'a150' }),
  Object.assign(K('FundedNext Futures', '50k F1'), { id: 'f50' }), Object.assign(K('Tradeify', '150k T1', 150000), { id: 't150', maxDrawdown: 0 })];
let _vpR = R; const wdVorplanRegeln = () => ({ regeln: _vpR }), tpVorplanLive = a => (a.startingBalance || 50000) + 1000;
r.he = [tpWdHedgeEur('a50', 0), tpWdHedgeFehlt('a50'), tpWdHedgeEur('a150', 0), tpWdHedgeFehlt('a150'), tpWdHedgeEur('f50', 0), tpWdHedgeEur('t150', 0), tpWdHedgeEur('a50', 40)];
_vpR = Object.assign({}, R, { staffelFirma: { lucid: R.staffelFirma.lucid, lucid50: [{ von: 0, eur: 25 }] } });
r.he2 = [tpWdHedgeEur('a50', 0), tpWdHedgeFehlt('a50')];
JSON.stringify(r);
""")
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
    fh.write(js)
try:
    aus = subprocess.run(["osascript", "-l", "JavaScript", fh.name], capture_output=True, text=True, timeout=30)
    jr = json.loads(aus.stdout.strip() or "{}")
    if not jr:
        print(aus.stderr[:900])
finally:
    os.unlink(fh.name)
ok(jr.get("keys") == ["lucid50", "lucid", "lucid50", "lucid", "fnfutures50", "fnfutures", "tradeify", "apex100", "sonst"],
   f"tpVorplanFirmaKey: 50k (Name oder Startbalance) → eigener Schlüssel, sonst wie bisher ({jr.get('keys')})")
ok(jr.get("basis") == ["lucid", "fnfutures", "apex100", "lucid"], "wdBasisKey: 50k → Firma (E4-Regeln, fester SL), andere unverändert")
ok(jr.get("kt") == [[1, 1], [1, 1], [2, 3], [2, 2], [1, 1], [2, 3]],
   f"Kontrakte 50k ohne eigene Werte = Firma × 1/3 (2–3 → 1–1, 6–9 → 2–3), eigene Werte gelten, Firma unverändert ({jr.get('kt')})")
zz = jr.get("z") or [None] * 9
ok(zz[0] and "Hedge-Werte fehlen für Lucid 50k" in zz[0] and zz[8] and "FundedNext Futures 50k" in zz[8],
   f"ohne eigene Hedge-Tabelle: sichtbarer Fehler statt Standard-Tabelle — Lucid 50k / FNF 50k ({zz[0]})")
ok(zz[1] is None and zz[2] == 25 and zz[3] == 170 and zz[4] == 190, f"mit eigener Tabelle: Hedge 25 € aus lucid50, TP 170–190 (Vorgabe) ({zz[1:5]})")
ok(zz[5] is None and zz[6] == 60 and zz[7] == 268, "Lucid 150k: Tabelle und TP der Firma wie bisher")
ok("firmen[(typeof wdBasisKey === 'function') ? wdBasisKey(k) : k]" in html and "e4RegelnHtml(wdBasisKey(k))}" in html,
   "fester SL je Firma und Payout-Regeln (E4) lesen den Firmen-Schlüssel")
ok("wdBasisKey(k) !== k ? 'fehlt' : 'wie Standard'" in html, "Hedge-Tabelle im Farmer: 50k ohne eigene Tabelle zeigt „fehlt“")
he, he2 = jr.get("he") or [None] * 7, jr.get("he2") or [None] * 2
ok(he[0] is None and "Hedge-Werte fehlen für Lucid 50k" in str(he[1]) and he[4] is None,
   f"LF1e Hand-Popup: Lucid/FNF 50k ohne Tabelle → keine Vorbelegung (null), Hinweis-Text da ({he[:2]}, FNF {he[4]})")
ok(he[2] == 60 and he[3] == "" and he[5] == 50 and he[6] == 40,
   f"Lucid 150k aus seiner Tabelle (60), kein Hinweis; Konto ohne DD wie bisher Standard-Staffel (50); bestehender Wert bleibt (40) ({he[2:]})")
ok(he2 == [25, ""], f"mit eigener Tabelle lucid50: Vorbelegung 25 €, kein Hinweis ({he2})")
ok("else if(v == null){   // LF1e" in html and "el.placeholder = 'Hedge-Werte fehlen'" in html
   and "if(_hf && !(_sv > 0)){ msg(_hf + ' — oder „Risiko Slave (€)“ von Hand eintragen. Nicht gespeichert.', 'err'); return }" in html,
   "Popup: Feld leer mit Hinweis, Speichern ohne Wert gesperrt (Wert von Hand bleibt möglich)")

print()
print("alle Tests bestanden" if not FEHLER else f"{len(FEHLER)} ROT")
sys.exit(1 if FEHLER else 0)
