#!/usr/bin/env python3
"""Selbsttest PULS-MODUS-WARNUNG (30.10.2026, Slave 6 — Master: „Prophos meldet je PC mit Namen ‚Userscript nicht im Puls-Chrome-Modus‘";
Anlass Simon pc-pmqd8g, /positions: nur Tab „t…" Rolle feed mit login_im_feed, positionen_tab null). pulsModusFehlt per macOS-JavaScriptCore
(jsc) aus prophos.html geschnitten; dazu der Quelltext-Vertrag (Tick, Drossel, Route) und die Railway-Route per Flask-Testclient-freiem
Quelltext-Check (alarm_senden 🟠 mit PC-Namen, 24-h-Drossel _tm_melde_frei).
Aufruf: python3 tools/selftest_pulsmodus.py"""
import json
import os
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HIER, "..", "prophos.html")
APP = os.path.join(HIER, "..", "app.py")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def js_funktion(src, name):
    """Funktionsquelltext per Klammerzählung (wie tools/selftest_kurz_summary_keys.py)."""
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
    simon = {"tabs": [{"tab_id": "tmvu6eqsyft4461", "rolle": "feed", "version": "0.10.4", "konto": None, "blind": False,
                       "login_im_feed": "FTDFYSLX0000000000", "alter_s": 0.3}], "positionen_tab": None, "positionen_ok": False}
    faelle = [
        ("Simon: nur Tab t… Rolle feed mit Broker-Login → fehlt", simon, "tmvu6eqsyft4461"),
        ("frischer Tab puls-… da → fehlt nicht", {"tabs": [{"tab_id": "puls-abc", "rolle": "broker", "alter_s": 0.2},
                                                          {"tab_id": "tfeed1", "rolle": "feed", "alter_s": 0.1}]}, None),
        ("puls-Tab da, daneben t… mit Login → fehlt nicht (Puls-Tab zählt)", {"tabs": [{"tab_id": "puls-abc", "rolle": "broker", "alter_s": 3},
                                                                                       {"tab_id": "tx", "rolle": "feed", "login_im_feed": "K", "alter_s": 1}]}, None),
        ("t… Rolle broker (normaler Modus mit Konto), kein puls → fehlt", {"tabs": [{"tab_id": "tbrk", "rolle": "broker", "alter_s": 2}]}, "tbrk"),
        ("nur Feed-Tab ohne Login (Kurse) → fehlt nicht", {"tabs": [{"tab_id": "tfeed", "rolle": "feed", "alter_s": 0.5}]}, None),
        ("Broker-Tab alt (alter_s 300) → fehlt nicht", {"tabs": [{"tab_id": "tbrk", "rolle": "broker", "alter_s": 300}]}, None),
        ("puls-Tab alt (300 s), t… frisch mit Login → fehlt", {"tabs": [{"tab_id": "puls-a", "rolle": "broker", "alter_s": 300},
                                                                       {"tab_id": "tz", "rolle": "feed", "login_im_feed": "K", "alter_s": 1}]}, "tz"),
        ("ohne tabs → fehlt nicht", {"positionen_ok": True}, None),
        ("kein Stand → fehlt nicht", None, None),
    ]
    code = js_funktion(src, "pulsModusFehlt") + "\nvar F = " + json.dumps([f[1] for f in faelle]) + \
        ";\nprint(JSON.stringify(F.map(function (x) { var t = pulsModusFehlt(x); return t ? t.tab_id : null; })));\n"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(code)
    aus = json.loads(subprocess.run([JSC, f.name], capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])
    os.unlink(f.name)
    for (name, _st, soll), ist in zip(faelle, aus):
        check(ist == soll, name)
    # Vertrag Tick: nur mit tvv2-Plan dieses PCs, ≥ 2 min stabil, je 24 h, Meldung an /alarm/userscript-update
    tick = js_funktion(src, "pulsModusTick")
    check("p.route === 'tvv2'" in tick and "tvV2EndlesungPcPasst(p)" in tick, "Tick: nur mit Orbit-Plan (tvv2) dieses PCs")
    check("PULSMODUS_SEIT_MS" in tick and "PULSMODUS_MELDE_MS" in tick and "prophos_pulsmodus_gemeldet_at" in tick, "Tick: 2 min stabil, 24 h je PC")
    check("puls_modus_fehlt: true" in tick and "/alarm/userscript-update" in tick and "window._tabNebenSofort" in tick, "Tick: Meldung an Railway, nie im Neben-Tab")
    check("setInterval(pulsModusTick, 60000 + Math.floor(Math.random() * 30000))" in src, "Tick: gestreut alle 60–90 s")
    app = open(APP, encoding="utf-8").read()
    i = app.index('if not tsx and d.get("puls_modus_fehlt") is True:')
    blk = app[i:i + 1500]
    check('key = f"tm|{pc}|tv|pulsmodus"' in blk and "_tm_melde_frei(key)" in blk, "Route: 24-h-Drossel je PC")
    check('alarm_senden(2, "userscript_pulsmodus"' in blk and "PC von" in blk and "Puls-Chrome (Orbit V3) — einschalten" in blk,
          "Route: 🟠 an die Master-IDs mit PC-Namen und dem Klick")
    check(app.index('if not tsx and d.get("puls_modus_fehlt") is True:') > app.index('if str(uid) in _aus or _alarm_fremd_verwaltet(uid):'),
          "Route: nach dem HT-Filter (Emin-Gruppe nie)")
    if FEHLER:
        print(f"\nFEHLER ({len(FEHLER)})")
        sys.exit(1)
    print("\nalle Tests bestanden")


if __name__ == "__main__":
    main()
