#!/usr/bin/env python3
"""Selbsttest HEDGE-ZU-7S (02.11.2026, Plan e67ec7b9: Close 7,17 s zwischen Tab und Panel, Glied unbekannt). Nur Messung, ohne Netz:
- panel.hedge_solo_zeiten: Stempel in zeiten_ms, Copier-Stempel bleiben, unlesbare Werte fehlen, kein dict bleibt unverändert
- Quelltext: app.py stempelt nur hedge-solo, das Panel stempelt am Anfang von do_POST, der Tab schreibt close_zeiten bei Erfolg und Fehler
Aufruf: python3 tools/selftest_hedge_zeiten.py"""
import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEHLER = []


def lies(name):
    return open(os.path.join(WURZEL, name), encoding="utf-8").read()


def ok(bed, txt):
    print(("  ok   " if bed else "  FEHL ") + txt)
    if not bed:
        FEHLER.append(txt)


PANEL, APP, HTML = lies("mt5-copier/panel.py"), lies("app.py"), lies("prophos.html")
i = PANEL.index("\ndef hedge_solo_zeiten(") + 1
ns = {}
exec(PANEL[i:PANEL.index("\n\n\n", i)], ns)
Z = ns["hedge_solo_zeiten"]

e = Z({"ok": True, "pl": 1, "zeiten_ms": {"panel": 5, "fertig": 9}}, "1000", 2.0, 3.5)
ok(e["zeiten_ms"] == {"panel": 5, "fertig": 9, "proxy_ein": 1000, "panel_ein": 2000, "panel_aus": 3500}, "alle Stempel, Copier-Stempel bleiben")
ok(e["ok"] is True and e["pl"] == 1, "Ergebnis sonst unverändert")
ok(Z({"ok": False, "code": "copier_stumm"}, None, 2.0, 3.0)["zeiten_ms"] == {"panel_ein": 2000, "panel_aus": 3000}, "ohne Copier-Quittung und ohne app.py-Stempel")
ok("proxy_ein" not in Z({}, "quatsch", None, None)["zeiten_ms"], "unlesbarer Proxy-Stempel fehlt")
ok(Z(None, "1", 1.0, 1.0) is None, "kein dict bleibt unverändert")
ein = {"zeiten_ms": {"a": 1}}
Z(ein, "1", 1.0, 1.0)
ok(ein == {"zeiten_ms": {"a": 1}}, "Eingabe wird nicht verändert")

i = APP.index("\ndef _copier_proxy_lauf(")
ok('if path == "hedge-solo":\n        h["X-Prophos-Proxy-Ms"]' in APP[i:i + 500], "app.py stempelt nur hedge-solo, vor dem Aufruf des Panels")
i = PANEL.index("    def do_POST(self):")
ok(PANEL[i:i + 60].split("\n")[1].strip().startswith("self._t_ein = time.time()"), "Panel stempelt in der ersten Zeile von do_POST")
i = HTML.index("async function hedgeSoloSchliessen(")
b = HTML[i:HTML.index("function hedgePuffer()", i)]
ok(b.count("close_zeiten: closeZeiten") == 2, "Tab schreibt close_zeiten bei Erfolg und bei Fehler")
ok(b.index("const closeZeiten") < b.index("await schliesstP"), "tab_antwort vor dem Warten auf den Supabase-Patch")

print("\nALLES OK" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
