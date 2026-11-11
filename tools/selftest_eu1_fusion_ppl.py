#!/usr/bin/env python3
"""Selbsttest EU1 · Fusion €/Punkt aus dem echten Kurs statt fest 0,85 (06.11.2026, Slave 4 — Befund OV1 S5: Hedges ~5 % zu groß).

Ohne Netz: app.py importiert (fusion_eur_pkt_waehlen, fusion_sppl_wahl, tfh_hedge, fdp_hedge, gp_multiplikator) mit Zahlenbeispiel
vorher (0,85) / nachher (0,893 = gemessener hedge.wert_pro_punkt), dazu der Vertrag im Quelltext (keine feste 0,85 mehr an den
Fusion-Nachschlage-Stellen). Frontend per macOS-JavaScriptCore (jsc): fusionEurPktWaehlen, fusionEurPkt (jüngster gemessener Wert aus
tradePlans → FX → 0,85), tpPresetPpl (Fusion-€-Zeile 0,85 → echter Kurs; 0,852 / $-Zeile / andere Firmen unverändert),
hedgeMultAusRisiko mit Finns Beispiel 250 $ / 1 MNQ / 100 €. Alle Kennungen erfunden.
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_eu1_fusion_ppl.py"""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

HTML = os.path.join(HIER, "..", "prophos.html")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


ECHT = 0.893
# ── app.py: Quelle ──────────────────────────────────────────────────────────────────────────────────────────
W = app.fusion_eur_pkt_waehlen
check(W(0.89305, 0.8935) == (0.89305, "gemessen"), "gemessen vor FX")
check(W(None, 0.8935) == (0.8935, "fx") and W("x", 0.8935) == (0.8935, "fx"), "ohne Messung → Live-FX")
check(W(None, None) == (0.85, "rueckfall") and W(5.0, 0.01) == (0.85, "rueckfall"), "nichts Plausibles → 0,85")
S = app.fusion_sppl_wahl
check(S(None, ECHT) == ECHT and S(0.85, ECHT) == ECHT and S("0.8500", ECHT) == ECHT, "firm_specs fehlt / alter Festwert 0,85 (auch $-Zeile) → echter Kurs")
check(S(0.852, ECHT) == 0.852 and S(0.9, ECHT) == 0.9, "bewusst gesetzt (0,852, 0,90) → bleibt")
app._FUSION_EUR_PKT.update(at=1e18, wert=ECHT, quelle="gemessen", je_id={"u-emin": "0.8520", "u-jacob": "0.8500"})
check(app.fusion_sppl(None, "u-emin") == 0.852 and app.fusion_sppl(None, "u-jacob") == ECHT and app.fusion_sppl(None, "u-neu") == ECHT,
      "fusion_sppl ohne Karte: je-ID-Wert aus firm_specs (0,852 bleibt, 0,85 → echter Kurs)")

# ── app.py: Zahlen vorher/nachher ──────────────────────────────────────────────────────────────────────────
alt, _ = app.tfh_hedge(0.04, 3000, 2, 20, 1500, 0.89, 0.01)                 # ohne sppl = wie bisher (TFH_SLAVE_PPL 0,85)
neu, _ = app.tfh_hedge(0.04, 3000, 2, 20, 1500, 0.89, 0.01, sppl=ECHT)
check(alt and neu and abs(alt["lots"] - 2.12) < 0.011 and abs(neu["lots"] - 2.01) < 0.011,
      f"TFH: q 0,0449 · Polster 3.000 $ · 2 NQ → Lots {alt['lots']} (0,85) → {neu['lots']} (0,893)")
check(alt and neu and abs(alt["hedge_eur"] - neu["hedge_eur"]) <= 1.0, f"TFH: Verlust am TP gleich ({alt['hedge_eur']} € → {neu['hedge_eur']} €), nur die Lots passen")
m_alt = app.gp_multiplikator(250, 1, 100, 2, 0.85)
m_neu = app.gp_multiplikator(250, 1, 100, 2, ECHT)
check(abs(m_alt - 0.9412) < 0.001 and abs(m_neu - 0.8959) < 0.001, f"Finns Beispiel 250 $ / 1 MNQ / 100 €: Multiplikator {m_alt:.4f} → {m_neu:.4f} (−{(1 - m_neu / m_alt) * 100:.1f} %)")
fa = app.fdp_hedge(400, 150000, 145500, 2000, None, 2) if hasattr(app, "fdp_hedge") else None
fn = app.fdp_hedge(400, 150000, 145500, 2000, None, 2, sppl=ECHT) if hasattr(app, "fdp_hedge") else None
if isinstance(fa, dict) and isinstance(fn, dict) and fa.get("lots") and fn.get("lots"):
    check(fn["lots"] < fa["lots"], f"FDP: Lots {fa['lots']} (0,85) → {fn['lots']} (0,893)")

src = open(os.path.join(HIER, "..", "app.py"), encoding="utf-8").read()
check('_firm_norm("Fusion Markets")))) or (None,))[0]) or GP_SLAVE_PPL' not in src, "keine Fusion-Nachschlage-Stelle mehr mit festem GP_SLAVE_PPL-Rückfall")
check(src.count("fusion_sppl(ppl, uid)") + src.count('fusion_sppl(ctx_ppl.get("ppl"), uid)') == 6, "alle 6 Planer-Stellen über fusion_sppl")
check(src.count('sppl=K.get("sppl") or FDP_SLAVE_PPL)') == 2 and 'konst["sppl"] = fusion_sppl(None, a.get("user_id")) if "fusion_sppl" in globals() else None' in src,
      "FDP: rein rechnend, € je Punkt kommt von außen (konto_rechnen)")
check('"mt5_baseline->hedge->>waehrung": "eq.EUR"' in src, "Messung nur aus EUR-Hedges")
check(src.count("fusion_sppl(None,") == 4, "TFH-Aufrufe (Vorschau + Takt), FDP und FF2-Pump-Takt (Trade 2) mit dem Wert der ID")   # FF2 11.11.2026: + fdp_pump_tick
check("lots = slave_risk / (TFH_SLAVE_PPL * pkt)" not in src, "TFH rechnet nicht mehr fest")

# ── Frontend (jsc) ─────────────────────────────────────────────────────────────────────────────────────────
html = open(HTML, encoding="utf-8").read()


def js_funktion(name):
    i = html.index(f"function {name}(")
    j = html.index("{", html.index(")", i))
    t = 0
    for k in range(j, len(html)):
        t += {"{": 1, "}": -1}.get(html[k], 0)
        if t == 0:
            return html[i:k + 1]
    raise ValueError(name)


JS = r"""
var window = { _fxUsdEur: 0.8935 }
const FUSION_EUR_PKT_RUECKFALL = 0.85
const _fusionEurPktC = { at: 0, v: FUSION_EUR_PKT_RUECKFALL, q: 'rueckfall' }
let tradePlans = []
let accounts = []
const tpIstApexHedge = () => false
%s
const jetzt = new Date().toISOString(), alt = new Date(Date.now() - 5 * 864e5).toISOString()
const aus = {}
aus.fx = fusionEurPkt(); aus.fxQ = _fusionEurPktC.q
tradePlans = [{ startedAt: alt, mt5Baseline: { hedge: { wert_pro_punkt: 0.95, opened_at: alt } } },
              { startedAt: jetzt, mt5Baseline: { hedge: { wert_pro_punkt: 0.89305, opened_at: jetzt } } }]
_fusionEurPktC.at = 0
aus.gem = fusionEurPkt(); aus.gemQ = _fusionEurPktC.q
const fusion = v => tpPresetPpl({ label: 'Fusion Markets', currency: '€', ppl: v, _custom: true })
aus.p085 = fusion(0.85); aus.p0852 = fusion(0.852); aus.pStd = tpPresetPpl({ label: 'Fusion Markets', currency: '€', ppl: 0.9 })
aus.pDollar = tpPresetPpl({ label: 'Fusion Markets', currency: '$', ppl: 0.85, _custom: true })
aus.pFtmo = tpPresetPpl({ label: 'FTMO', currency: '$', ppl: 1, _custom: true })
const tpWdSlavePpl = () => fusionEurPkt()
const plan = { masterRisk: 250, slaveRisk: 100, masterAccountId: 'x' }
aus.mult = hedgeMultAusRisiko(plan, 1, 2)
print(JSON.stringify(aus))
"""
if not os.path.exists(JSC):
    check(False, "jsc fehlt — Frontend-Teil nicht ausführbar")
else:
    js = JS % "\n".join(js_funktion(n) for n in ("fusionEurPktWaehlen", "fusionEurPkt", "tpPresetPpl", "hedgeRisikoMaster", "hedgeMultAusRisiko"))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
    try:
        r = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(f.name)
    try:
        a = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        a = None
        check(False, "jsc: " + (r.stdout + r.stderr)[-600:])
    if a:
        check(a["fx"] == 0.8935 and a["fxQ"] == "fx", "Frontend: ohne Messung → Live-FX 0,8935")
        check(a["gem"] == 0.89305 and a["gemQ"] == "gemessen", "Frontend: jüngster gemessener wert_pro_punkt (≤ 3 Tage) gewinnt, alter (5 Tage) zählt nicht")
        check(a["p085"] == 0.89305 and a["pStd"] == 0.89305, "Preset Fusion € 0,85 (eigene Zeile) und Standard-Preset → echter Kurs")
        check(a["p0852"] == 0.852 and a["pDollar"] == 0.89305 and a["pFtmo"] == 1, "0,852 bleibt · $-Zeile 0,85 → echter Kurs (wie Railway) · andere Firma unverändert")
        m = a["mult"] or {}
        check(abs(m.get("lots", 0) - 0.90) < 0.011, f"hedgeMultAusRisiko: Finns Beispiel 0,94 Lot (0,85) → {m.get('lots')} Lot (0,893)")

check("lots = sr / (0.85 * pkt)" not in html, "Frontend: hedgeMultAusRisiko ohne feste 0,85")
check("tpNqGetSlavePpl(slaveFirm)  ?? tpPresetPpl(s))" in html and "return p ? tpPresetPpl(p) : null" in html, "Frontend: Multiplikator-Popup und tpFirmPpl über tpPresetPpl")
check("const wpp = n(h.wert_pro_punkt), sPplT" in html, "Overshoot-Auswertung: Satz mit dem €/Pkt des Trades selbst")
check("[tpWdSlavePpl(), FUSION_EUR_PKT_RUECKFALL, Number(window._fxUsdEur)].some(" in html, "Recoverer-Altplan: Betrag mit 0,85 oder heutigem Wert gilt als eigene Rechnung")

print()
if FEHLER:
    print(f"{len(FEHLER)} FEHLER:", *FEHLER, sep="\n  ")
    sys.exit(1)
print("alle Prüfungen bestanden")
