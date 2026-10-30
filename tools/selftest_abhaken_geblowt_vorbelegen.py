#!/usr/bin/env python3
"""Selbsttest ABHAKEN-GEBLOWT-VORBELEGEN (20.10.2026, Slave-Terminal 3 — Finn 23:00 Dubai am Radar .1647, Gruppe „Geblowt · archivieren · 2",
zwei Tradeify-150k-Konten: „Der Account ist eigentlich geblowt. Wenn ich auf Abhaken gehe, steht trotzdem ‚Nichts ändern' vorbelegt. Das Radar
weiß schon, dass er geblowt ist — der Dialog soll das vorbelegen, ich bestätige nur.")

Ohne Netz und ohne Node: das Frontend per macOS-JavaScriptCore (jsc) aus prophos.html geschnitten (wdlBlowStand, wdlKontoWeg, wdlGeblowtUrteil).
Geprüft: Liq-Regel am Trade getroffen, Balance ÜBER dem Konto-Boden (Tradeify Challenge: Start 153.462,72, Liq 148.962,72, Balance 148.921,20,
Boden 145.500) → geblowt; Balance über der Liq → nicht; Tageslimit (soft) über dem Boden → nicht (kein Blow); Balance am Boden ohne Liq (Echo)
→ geblowt; abgehakt geblowt (blown true) → geblowt; Konto weg → geblowt; laufender Plan → nicht. Dazu der Quelltext-Vertrag: Radar-Gruppe
(istGeblowt), Radar-Dialog (mwd-erl-status) und Trades-Dialog (tc-status) fragen alle dieselbe Funktion. Alle Kennungen erfunden.
Aufruf: python3 tools/selftest_abhaken_geblowt_vorbelegen.py"""
import json
import os
import re
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HIER, "..", "prophos.html")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def js_funktion(src, name):
    """Funktionsquelltext per Klammerzählung (wie tools/selftest_balance_sprung.py)."""
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


ZU = {"status": "review", "ended_at": "2026-10-20T13:40:00Z"}
FAELLE = [  # (name, Radar-Zeile, erwartet geblowt)
    ("Liq-Regel getroffen, Balance über dem Boden (Tradeify Challenge …0002)",
     dict(ZU, balance_start=153462.72, balance_end=148921.2, liq_regel_balance=148962.72, liq_boden_balance=145500, boden_usd=145500, liq_gilt="regel"), True),
    ("Liq-Regel getroffen ab Start 150.000 (…0001)",
     dict(ZU, balance_start=150000, balance_end=145437.72, liq_regel_balance=145500, liq_boden_balance=145500, liq_gilt="regel"), True),
    ("Balance 200 $ über der Liq → nicht geblowt",
     dict(ZU, balance_start=153462.72, balance_end=149162.72, liq_regel_balance=148962.72, liq_boden_balance=145500), False),
    ("Tageslimit (soft) erreicht, Balance über dem Boden → kein Blow",
     dict(ZU, balance_start=150000, balance_end=147981, liq_regel_balance=147981, liq_regel_soft=True, liq_regel_nur_balance=147981, liq_boden_balance=146000), False),
    ("Echo ohne Liq: Balance am Boden der Kernwerte → geblowt",
     dict(ZU, route="mt5v2", balance_end=89942, boden_usd=90000), True),
    ("abgehakt geblowt (blown true) → geblowt",
     dict(ZU, blown=True, balance_end=151000, liq_regel_balance=145500), True),
    ("Konto weg (endlesung) → geblowt",
     dict(ZU, endlesung={"konto_weg": True}, liq_regel_balance=145500), True),
    ("laufender Plan → nie",
     {"status": "open", "balance_end": 140000, "liq_regel_balance": 145500}, False),
    ("ohne Zeile → nie", None, False),
    # Topstep-V2-Blow ohne Endlesung (.1754): TopstepX sperrt am MLL beim Start, Konto nach dem Blow nicht lesbar → geblowt (Schätzung)
    ("Topstep V2 geblowt ohne Endbalance (MLL beim Start) → geblowt",
     {"status": "review", "route": "tsv2", "balance_start": 151583.42, "liq_balance": 149947.32, "liq_quelle": "mll_tsx",
      "endlesung": {"grund": "tsx_geblowt", "konto_geblowt": {"art": "maximum_loss"}}}, True),
    ("Topstep V2 ohne MLL und ohne Endbalance → nicht geblowt (nicht raten)",
     {"status": "review", "route": "tsv2", "balance_start": 151583.42, "endlesung": {"grund": "tsx_geblowt", "konto_geblowt": {"art": "maximum_loss"}}}, False),
]

JS_TEST = r"""
// Attrappen der Lese-Helfer: Konto weg nur, wenn der Auszug es sagt
function tvV2KontoWeg(e){ return !!(e && e.konto_weg) }
function tvV2KontoVermutetOffen(e){ return false }
const F = %s
print(JSON.stringify(F.map(f => wdlGeblowtUrteil(f[1]))))
"""


def main():
    if not os.path.exists(JSC):
        print("✗ jsc fehlt — Frontend-Teil nicht ausführbar")
        sys.exit(1)
    html = open(HTML, encoding="utf-8").read()
    konto_weg = re.search(r"^\s*const wdlKontoWeg = .*$", html, re.M).group(0)
    # seit 21.10.2026 fragt wdlKontoWeg zuerst wdlTpUndWeg („TP + nicht mehr im Dropdown" = wahrscheinlich bestanden) → mit schneiden
    weg_min = re.search(r"^\s*const TV_LIQ_WEG_MIN = .*$", html, re.M).group(0)
    # seit .1754 (27.10.2026) fällt wdlBlowStand ohne gelesene Endbalance auf die Topstep-Blow-Schätzung zurück → echten Helfer + Tooltip-Text mitschneiden
    tsx_tip = re.search(r"^\s*const WDL_TSX_SCHAETZ_TIP = .*$", html, re.M).group(0)
    js = "\n".join([weg_min, js_funktion(html, "wdlTpUndWeg"), konto_weg, tsx_tip, js_funktion(html, "wdlTsxBlowSchaetzung"),
                    js_funktion(html, "wdlBlowStand"), js_funktion(html, "wdlGeblowtUrteil")])
    js += JS_TEST % json.dumps([[n, z] for n, z, _s in FAELLE])
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
    try:
        r = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(f.name)
    if r.returncode != 0:
        print("✗ jsc:", (r.stdout + r.stderr)[-800:])
        sys.exit(1)
    aus = json.loads(r.stdout.strip().splitlines()[-1])
    for (name, _z, soll), ist in zip(FAELLE, aus):
        check(ist is soll, f"wdlGeblowtUrteil {name}: {ist}")

    # Quelltext-Vertrag: eine Wahrheit für Gruppe und beide Dialoge
    check("const istGeblowt = wdlGeblowtUrteil" in html, 'Radar-Gruppe „Geblowt · archivieren" fragt wdlGeblowtUrteil')
    # seit 30.10.2026: danach Funded CFD am Ziel → 'waiting' (fb90d54f); seit 21.10.2026: Polar-Pläne ausgenommen (!_mwdErlPolar), dazwischen „TP + weg" → 'passed' (_tw) — geblowt bleibt die erste Wahl
    check(re.search(r"mwd-erl-status\"\]\[value=\"\$\{\((?:!_mwdErlPolar && )?typeof wdlGeblowtUrteil === 'function' && wdlGeblowtUrteil\(pw\)\) \? 'blown' : (?:_tw \? 'passed' : )?(?:\(!_mwdErlPolar && wdlFcfdZielErreicht\(pw\)\) \? 'waiting' : )?'none'\}", html) is not None,
          "Radar-Dialog (fremde Pläne) belegt mwd-erl-status aus wdlGeblowtUrteil vor")
    i = html.index("function openTradeCompleteModal(")
    block = html[i:html.index("tcWinningDayPrepare(p)", i)]
    check("wdlGeblowtUrteil(tr)" in block and "input[name=\"tc-status\"][value=\"blown\"]" in block and "p.status !== 'completed'" in block,
          "Trades-Dialog (eigene Pläne) belegt tc-status aus wdlGeblowtUrteil der Radar-Zeile vor (nicht für abgehakte)")
    check(block.index("tcPopulateStatusAccountPicker(p)") < block.index("wdlGeblowtUrteil(tr)"), 'Vorbelegung NACH dem Reset auf „Nichts ändern"')
    check("window._mklWdErledigtOeffnen = mklWdErledigtOeffnen" in html, "Test-Haken für den Stub vorhanden")

    print()
    if FEHLER:
        print(f"{len(FEHLER)} FEHLER:", *FEHLER, sep="\n  ")
        sys.exit(1)
    print(f"alle {len(FAELLE) + 5} Prüfungen bestanden")


if __name__ == "__main__":
    main()
