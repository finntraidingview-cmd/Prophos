#!/usr/bin/env python3
"""Selbsttest WD-FUSION-HEDGE: PUNKTWERT AUS DEM PLAN-SYMBOL (.1712, Vorfall Marc 22.10.2026, Apex 150k PAAPEX6843320000001,
Plan 842453ce: 3 MNQ SELL, TP 386 $, Risiko Master 386 $, Staffel 175 € — am Plan multiplier 10,6675 → 32,00 Lot BUY, Start-Check hielt
mit „Fusion-Marge … zu wenig" an). Ursache: wdFarmHedge rechnete mit dem globalen Umschalter _tpNqMode, der an Marcs PC-Tab auf NQ stand
(20 $/Pkt statt 2) — Faktor 10. Prüft per macOS-jsc die echten Funktionen aus prophos.html:
  • wdFarmHedge mit master_symbol MNQZ6 → 3,20 Lot, auch wenn der Umschalter auf NQ steht; Umschalter danach unverändert
  • NQZ6 2 Kt / TP 7.500 $ / 1.500 € (Marcs Plan 387a2f50 vom 21.10.) → 9,41 Lot wie damals gespeichert
  • ohne Symbol: alter Weg über den Umschalter (Würfel/Anlegen setzen ihn vorher)
  • fusionHedgeLots (Start-Check Fusion-Marge) = Lots von hedgeSoloOeffnenKern (frisch aus Risiko), nicht der falsche multiplier
Ohne Netz. Aufruf: python3 tools/selftest_wd_hedge_symbol.py"""
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(os.path.dirname(HIER), "prophos.html")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"


def js_funktion(src, name):
    """Funktionsquelltext per Klammerzählung (wie tools/selftest_cfd_tp_fill.py)."""
    i = src.index(f"function {name}(")
    j = src.index("{", src.index(")", i))
    tiefe = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            tiefe += 1
        elif src[k] == "}":
            tiefe -= 1
            if tiefe == 0:
                return src[i:k + 1]
    raise ValueError(name)


def main():
    src = open(HTML, encoding="utf-8").read()
    teile = [js_funktion(src, n) for n in ("tvSymbolWurzel", "hedgePplFuer", "tpMultiplierAusRisiko", "hedgeRisikoMaster",
                                           "hedgeMultAusRisiko", "wdFarmHedge", "wdFarmHedgeKern", "fusionHedgeLots")]
    # Umgebung wie im PC-Tab: Apex Trader = Custom-Firma MNQ (firm_specs), Umschalter _tpNqMode, Fusion 0,85 €/Pkt
    js = """
let _tpNqMode = 'nq'
const TP_WD_SLAVE_FIRM = 'Fusion Markets'
const accounts = []
const tpWdSlavePpl = () => 0.85
function tpMasterPpl(firm){ return _tpNqMode === 'nq' ? 20 : 2 }
function tpCalcMultiplier(mf, sf, risk, kt, sr){ return tpMultiplierAusRisiko(risk, kt, sr, tpMasterPpl(mf), 0.85) }
function tpOrbitWerte(plan){ return { symbol: plan.masterSymbol } }
""" + "\n".join(teile) + """
const aus = []
function check(ok, txt){ aus.push((ok ? 'OK ' : 'ERR ') + txt) }
const lots = pr => Math.round(pr.master_contracts * pr.multiplier * 100) / 100

// 1) Marc 22.10.2026: MNQZ6 3 Kt, TP 386 $, Staffel 175 € — Umschalter steht auf NQ (wie an seinem PC-Tab)
_tpNqMode = 'nq'
let pr = { master_firm: 'Apex Trader', master_symbol: 'MNQZ6', master_contracts: 3, master_tp: 386, master_risk: 386 }
wdFarmHedge(pr, 0, 175, true, [4000])
check(lots(pr) === 3.2, 'MNQZ6 3 Kt / 386 $ / 175 € bei Umschalter NQ → 3,20 Lot (war 32,00): ' + lots(pr))
check(Math.abs(pr.hedge_eur - 175) < 0.5, 'Verlust am TP ≈ 175 €: ' + pr.hedge_eur)
check(_tpNqMode === 'nq', 'Umschalter danach unverändert (nq)')

// 2) Gegenprobe NQ: Marcs Plan 387a2f50 (21.10.) NQZ6 2 Kt, TP/Risiko 7.500 $, 1.500 € — Umschalter steht auf MNQ
_tpNqMode = 'mnq'
pr = { master_firm: 'Apex Trader', master_symbol: 'NQZ6', master_contracts: 2, master_tp: 7500, master_risk: 7500 }
wdFarmHedge(pr, 0, 1500, true, [])
check(Math.abs(pr.multiplier - 4.7059) < 0.0001 && lots(pr) === 9.41, 'NQZ6 2 Kt / 7.500 $ / 1.500 € bei Umschalter MNQ → 9,41 Lot (×4,7059): ' + lots(pr))
check(_tpNqMode === 'mnq', 'Umschalter danach unverändert (mnq)')

// 3) ohne Symbol: alter Weg über den Umschalter
_tpNqMode = 'mnq'
pr = { master_firm: 'Apex Trader', master_contracts: 3, master_tp: 386, master_risk: 386 }
wdFarmHedge(pr, 0, 175, true, [])
check(lots(pr) === 3.2, 'ohne Symbol, Umschalter MNQ → 3,20 Lot: ' + lots(pr))

// 4) Start-Check Fusion-Marge: Plan wie in der DB (falscher multiplier 10,6675) → Lots wie beim Öffnen
const plan = { route: 'tvv2', hedgeEur: 174.99, masterContracts: 3, multiplier: 10.6675, masterSymbol: 'MNQZ6', masterRisk: 386, masterTp: 386, slaveRisk: 175, richtung: 'sell' }
check(fusionHedgeLots(plan) === 3.2, 'Start-Check: Plan 842453ce (multiplier 10,6675) → 3,20 Lot statt 32,00: ' + fusionHedgeLots(plan))
// Echo (Weg mt5/dup): weiter Kontrakte × multiplier
check(fusionHedgeLots({ route: 'dup', masterContracts: 2, multiplier: 1.055 }) === 2.11, 'Echo: 2 Kt × 1,055 = 2,11 Lot (unverändert)')
print(aus.join('\\n'))
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        pfad = f.name
    try:
        out = subprocess.run([JSC, pfad], capture_output=True, text=True, timeout=30)
    finally:
        os.unlink(pfad)
    text = (out.stdout or "") + (out.stderr or "")
    zeilen = [z for z in text.splitlines() if z.strip()]
    for z in zeilen:
        print(("✓ " + z[3:]) if z.startswith("OK ") else ("✗ " + z[4:]) if z.startswith("ERR ") else z)
    gut = zeilen and all(z.startswith("OK ") for z in zeilen)
    print("ALLES GRÜN" if gut else "FEHLER")
    sys.exit(0 if gut else 1)


if __name__ == "__main__":
    main()
