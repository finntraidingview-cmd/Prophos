#!/usr/bin/env python3
"""Selbsttest: Lader des TopstepX-Auges (29.10.2026, Finn 10:20: „Ich will, dass sich das Auge automatisch aktualisiert"). Prüft an den
ECHTEN Dateien: Marker, Versionen (@version = SCRIPT = EINGEBAUT), Kern-Paket vom Panel (augen_tsx.js + Kern, SHA-256), Lader-Stand im
Panel, Lader-Soll im PC-Tab = LADER_V im Auge. Ohne Netz.  Aufruf: python3 tools/selftest_tsx_lader.py"""
import hashlib
import os
import re
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import panel  # noqa: E402


def main():
    f = []
    ok = lambda b, t: f.append(t) if not b else print("✓", t)   # noqa: E731
    us = open(os.path.join(WURZEL, "tv-reader", "tsx-auge.user.js"), encoding="utf-8").read()
    au = open(os.path.join(WURZEL, "mt5-copier", "augen_tsx.js"), encoding="utf-8").read()
    ph = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
    ver = re.search(r"^// @version\s+([0-9.]+)\s*$", us, re.M).group(1)
    w = panel.tsx_kern_aus(us, au)
    ok(w and w["version"] == ver and re.search(r"const EINGEBAUT = '([0-9.]+)'", us).group(1) == ver,
       f"Versionen: @version = SCRIPT im Kern = EINGEBAUT ({ver})")
    ok(w and w["sha"] == hashlib.sha256(w["kern"].encode("utf-8")).hexdigest() and w["kern"].startswith(au.rstrip()[:200])
       and "prophosLader" not in w["kern"] and "var PROPHOS_AUGEN_TSX" in w["kern"] and "__prophosTsxKernAn" in w["kern"],
       "Kern-Paket: augen_tsx.js + Kern ohne Lader, SHA-256 stimmt, Riegel drin")
    ok(panel.tsx_kern_aus(us.replace("// ==KERN-ENDE==", ""), au) is None and panel.tsx_kern_aus(us + "\n// ==KERN-START==\n", au) is None
       and panel.tsx_kern_aus(us, "") is None and panel.tsx_kern_aus(b"", au) is None, "Kern-Paket: Marker fehlen/doppelt oder augen_tsx.js leer → None")
    kern = us[us.index("// ==KERN-START==\n") + 18:us.index("// ==KERN-ENDE==")]
    ok(kern.startswith("(function () {\n  'use strict';\n  // 0.3.0 DOPPELLAUF-RIEGEL") and kern.count("__prophosTsxKernAn") == 2,
       "Riegel steht ganz oben im Kern")
    for z in ("// @name         Prophos TopstepX-Auge", "// @namespace    prophos", "// @grant        GM_getValue", "// @grant        GM_setValue",
              "// @updateURL    http://127.0.0.1:8770/userscript/tsx-auge.meta.js", "// @require      https://prophos.pages.dev/mt5-copier/augen_tsx.js"):
        ok(z in us, f"Kopf: {z.strip()[:70]}")
    lv, soll = re.search(r"const LADER_V = (\d+);", us), re.search(r"TVTM_TSX_LADER_SOLL = (\d+)", ph)
    ok(lv and soll and lv.group(1) == soll.group(1), "TVTM_TSX_LADER_SOLL im PC-Tab = LADER_V im Auge")
    t = 1000.0
    panel._tsx_stand.clear()
    panel.tsx_stand_merken({"tab": "tsx-a", "script": "0.3.0", "stand": {"flach": True},
                            "lader": {"v": 1, "eval": True, "laeuft": "0.3.0", "quelle": "eingebaut", "bereit": "0.3.1", "fehler": "", "code": "x" * 500}}, t)
    a = panel.tsx_stand_ausgabe(t + 1)
    ok(a["lader"] == {"v": 1, "eval": True, "laeuft": "0.3.0", "quelle": "eingebaut", "bereit": "0.3.1", "fehler": ""},
       "Panel merkt den Lader-Stand (sechs kurze Felder) und gibt ihn aus")
    panel.tsx_stand_merken({"tab": "tsx-b", "script": "0.2.0", "stand": {}}, t + 2)
    ok(panel.tsx_stand_ausgabe(t + 3)["lader"] is None, "Panel: altes Auge ohne lader → lader None")
    panel._tsx_stand.clear()
    ok(panel.tsx_stand_herkunft_ok("chrome-extension://abc") and panel.tsx_stand_herkunft_ok("https://topstepx.com")
       and not panel.tsx_stand_herkunft_ok("https://boese.example"), "Herkunft der Kern-Route wie tsx-stand")
    for x in f:
        print("✗", x)
    print("alle Tests bestanden" if not f else f"FEHLER ({len(f)})")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
