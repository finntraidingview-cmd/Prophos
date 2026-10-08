#!/usr/bin/env python3
"""Selbsttest BALANCE-SPRUNG (app.py lt_balance_sprung + prophos.html tvBalanceSprung/_autoPnlTvV2Gelesen/balanceSprungText, 08.10.2026,
Slave-Terminal 3 — Master nach der Gegenprüfung, Fall ea91e359: Tradeify-WD, Balance 165.039,22 → 159.950,02 = −5.089,20, Today's P&L −589,20;
dazwischen eine Auszahlung von 4.500 $ — die Balance-Differenz wäre als Master-P&L übernommen worden).

Aufruf:  python3 tools/selftest_balance_sprung.py
Ohne Netz und ohne Node: das Backend aus app.py (Funktionsblöcke), das Frontend per macOS-JavaScriptCore (jsc) aus prophos.html geschnitten.
Geprüft (beide Seiten gleich): ea91e359 → Sprung {−5.089,20 · −589,20 · −4.500}; Balance höchstens 100 $ unter dem Tages-P&L → kein Sprung;
nur nach unten (Balance ÜBER dem Tages-P&L → nie); hängendes Total P/L (Ende = Start, Fall 8da04bfe) → kein Sprung; anderer Handelstag /
ohne Startwert → kein Sprung (wie bisher); Topstep V2 mit rpl_start; TopstepX relativ/absolut → nie (Prüfung Slave 2 / Master 08.10.2026). Frontend: Auto-P&L übernimmt im
Sprung-Fall NICHTS (masterPnl null, quelle balance_sprung, Vorschlag = Tages-P&L), sonst unverändert die Balance-Differenz; Tooltip
„Balance −5.089 · Tages-P&L −589 · Differenz −4.500 (Auszahlung?)"."""
import json
import os
import re
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HIER, "..", "app.py")
HTML = os.path.join(HIER, "..", "prophos.html")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def lade_py():
    src = open(APP, encoding="utf-8").read()
    ns = {"re": re}

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]
    konst = re.search(r"^LT_BALANCE_SPRUNG_USD = .*$", src, re.M).group(0)
    exec("\n".join([konst] + [block(f) for f in ("_wd_num", "lt_pl_balance", "lt_balance_sprung")]), ns)
    return ns


def js_funktion(src, name):
    """Funktionsquelltext per Klammerzählung (Strings/Template-Literale in diesen Funktionen sind klammer-ausgeglichen)."""
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


EA = {"tv": {"balance_start": 165039.22, "today_pnl_start": 0, "datum_start": "2026-10-07"},
      "fin": {"balance_end": 159950.02, "today_pnl": -589.2, "datum": "2026-10-07", "quelle": "puls"}}
FAELLE = [  # (name, route, tv, fin, erwartet Sprung (balance, tages) | None)
    ("ea91e359 Auszahlung 4.500", "tvv2", EA["tv"], EA["fin"], (-5089.2, -589.2)),
    ("Balance 90 $ unter dem Tages-P&L (Gebühren)", "tvv2", {"balance_start": 150000, "today_pnl_start": 12.6, "datum_start": "2026-10-08"},
     {"balance_end": 149410, "today_pnl": -487.4, "datum": "2026-10-08"}, None),
    ("8da04bfe: Total P/L hängt (12,6 vor und nach), Balance −50,40", "tvv2", {"balance_start": 153907.12, "today_pnl_start": 12.6, "datum_start": "2026-10-08"},
     {"balance_end": 153856.72, "today_pnl": 12.6, "datum": "2026-10-08"}, None),
    ("hängendes Total P/L bei echtem −3.000", "tvv2", {"balance_start": 150000, "today_pnl_start": 0, "datum_start": "2026-10-08"},
     {"balance_end": 147000, "today_pnl": 0, "datum": "2026-10-08"}, None),
    ("Balance ÜBER dem Tages-P&L (+500) → nie", "tvv2", {"balance_start": 150000, "today_pnl_start": 0, "datum_start": "2026-10-08"},
     {"balance_end": 151000, "today_pnl": 500, "datum": "2026-10-08"}, None),
    ("normaler Trade (Balance = Tages-P&L − 4 $ Gebühr)", "tvv2", {"balance_start": 150000, "today_pnl_start": 0, "datum_start": "2026-10-08"},
     {"balance_end": 151996, "today_pnl": 2000, "datum": "2026-10-08"}, None),
    ("anderer Handelstag", "tvv2", dict(EA["tv"], datum_start="2026-10-06"), EA["fin"], None),
    ("ohne Startwert", "tvv2", {"balance_start": 165039.22, "datum_start": "2026-10-07"}, EA["fin"], None),
    ("Topstep V2 rpl_start, Kette Trade 2", "tsv2", {"balance_start": 147500, "rpl_start": -2500, "datum_start": "2026-10-09"},
     {"balance_end": 140000, "today_pnl": -4520, "datum": "2026-10-09"}, (-7500.0, -2020.0)),
    ("TopstepX relativ gegen absolut", "tsv2", {"balance_start": 150000, "today_pnl_start": 0, "datum_start": "2026-10-09", "balance_relativ": False},
     {"balance_end": 2000, "today_pnl": -500, "datum": "2026-10-09", "balance_relativ": True}, None),
]

JS_TEST = r"""
const F = %s
const aus = { sprung: F.map(f => tvBalanceSprung(f[1], f[2], f[3])), text: balanceSprungText(tvBalanceSprung('tvv2', F[0][2], F[0][3])) }
const plan = (f, route) => ({ id: 'x', route: route || 'tvv2', hedgeEur: 50, mt5Baseline: { tv: f[2], final: f[3] } })
aus.auto = F.map(f => { const r = _autoPnlTvV2Gelesen(plan(f, f[1])); return r ? { m: r.masterPnl, q: r.quelle, v: r.vorschlag == null ? null : r.vorschlag, h: r.hinweis || '' } : null })
print(JSON.stringify(aus))
"""


def main():
    py = lade_py()
    S = py["lt_balance_sprung"]
    for name, route, tv, fin, soll in FAELLE:
        r = S(route, tv, fin)
        ok = (r is None) if soll is None else (r is not None and r["balance"] == soll[0] and r["tages"] == soll[1]
                                              and r["differenz"] == round(soll[0] - soll[1], 2))
        check(ok, f"Backend {name}: {r}")

    if not os.path.exists(JSC):
        print("✗ jsc fehlt — Frontend-Teil nicht ausführbar")
        sys.exit(1)
    html = open(HTML, encoding="utf-8").read()
    konst = re.search(r"^\s*const TV_BALANCE_SPRUNG_USD = .*$", html, re.M).group(0)
    js = "\n".join([konst] + [js_funktion(html, n) for n in ("tvBalanceBasisGleich", "tvBalanceSprung", "balanceSprungText", "_autoPnlTvV2Gelesen")])
    js += JS_TEST % json.dumps([[n, r, tv, fin] for n, r, tv, fin, _s in FAELLE])
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
    try:
        r = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(f.name)
    if r.returncode != 0:
        print("✗ jsc:", (r.stdout + r.stderr)[-800:])
        sys.exit(1)
    a = json.loads(r.stdout.strip().splitlines()[-1])
    gleich = all((py_r is None and js_r is None) or (py_r and js_r and py_r["balance"] == js_r["balance"] and py_r["tages"] == js_r["tages"]
                                                      and py_r["differenz"] == js_r["differenz"])
                 for py_r, js_r in zip([S(r_, tv, fin) for _n, r_, tv, fin, _s in FAELLE], a["sprung"]))
    check(gleich, "Frontend tvBalanceSprung = Backend lt_balance_sprung in allen Fällen")
    check(a["text"] == "Balance −5.089 · Tages-P&L −589 · Differenz −4.500 (Auszahlung?)", f"Tooltip: „{a['text']}“")
    e = a["auto"][0]
    check(e and e["m"] is None and e["q"] == "balance_sprung" and e["v"] == -589.2 and "nicht automatisch" in e["h"],
          f"Auto-P&L ea91e359: nichts übernommen, Vorschlag Tages-P&L −589,20 ({e})")
    b = a["auto"][1]
    check(b and b["q"] == "balance" and b["m"] == -590.0, f"Balance 90 $ unter dem Tages-P&L: wie bisher Balance-Differenz −590 ({b})")
    h = a["auto"][2]
    check(h and h["q"] == "balance" and h["m"] == -50.4, f"8da04bfe hängendes Total P/L: wie bisher Balance-Differenz −50,40, kein Vorschlag 0 ({h})")
    h3 = a["auto"][3]
    check(h3 and h3["q"] == "balance" and h3["m"] == -3000.0, f"hängendes Total P/L bei −3.000: Balance-Differenz −3.000 bleibt ({h3})")
    nt = a["auto"][5]
    check(nt and nt["q"] == "balance" and nt["m"] == 1996.0, f"normaler Trade unverändert: +1.996 aus der Balance ({nt})")
    c = a["auto"][6]
    check(c and c["q"] == "balance" and c["m"] == -5089.2, f"anderer Handelstag: wie bisher Balance-Differenz ({c})")
    d = a["auto"][8]
    check(d and d["q"] == "balance_sprung" and d["v"] == -2020.0, f"Topstep V2 Kette Trade 2: Vorschlag −2.020 (RP&L ab dem Klick) ({d})")

    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
