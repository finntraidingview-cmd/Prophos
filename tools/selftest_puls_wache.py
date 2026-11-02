#!/usr/bin/env python3
"""Selbsttest PULS-WACHE (mt5-copier/panel.py puls_wache_entscheiden + _puls_wache_schritt, Finn 02.11.2026 ~18:40 „Ja, einbauen“; Simon pc-pmqd8g 18:31:06:
der PULS-CHROME-NEUSTART nach einem TopstepX-Fehler startete das Puls-Chrome nur mit topstepx.com, der Prophos-Tab fehlte während eines Big Trades).
Fälle: Tab weg → nach ~60 s neu; Tab da → nichts; Puls-Lauf → wartet, danach öffnen; zweimal weg → höchstens 1 Öffnen je 5 min; Puls-Chrome aus → nichts;
Backend im Neustart → nächste Runde erneut; URL mit ?v=<Build>. Ohne Netz. Aufruf: python3 tools/selftest_puls_wache.py"""
import ast
import os
import re
import sys
import types

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "mt5-copier", "panel.py"), encoding="utf-8").read()
FEHLER = []
# Build wie die Wache ihn liest (Tab-Stand ist im Test nach 10 min alt → OS_TAB_BUILD der lokalen prophos.html); nie fest, sonst rot bei jedem Bump
BUILD = re.search(r"const OS_TAB_BUILD = '([0-9A-Za-z._-]{1,40})'", open(os.path.join(W, "prophos.html"), encoding="utf-8").read()).group(1)


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


uhr = [1000.0]
welt = {"idle": 300.0, "liste": [], "frei": True, "oeffnen": [], "antwort": (True, "Puls-Chrome (Port 9333), eigenes Fenster"), "fehler": False}


def cdp_get(p):
    if welt["fehler"]:
        raise OSError("Port 9333 zu")
    return welt["liste"]


ns = {"re": re, "os": os, "HERE": os.path.join(W, "mt5-copier"), "TAB_URL": "http://localhost:5000/",
      "TAB_NL": {"stand": {"origin": BUILD}, "stand_at": 1000.0}, "_TAB_OEFFNEN": {"geoeffnet": [], "geoeffnet_at": 0.0},
      "time": types.SimpleNamespace(time=lambda: uhr[0]), "datetime": __import__("datetime").datetime,
      "_PROPHOS_URL_RE": re.compile(r"^http://(localhost|127\.0\.0\.1):5000(/|$)"), "_cdp_get": cdp_get,
      "_browser_und_mt5_frei": lambda tv_eigen=False: welt["frei"], "_tab_oeffnen": lambda url: (welt["oeffnen"].append((uhr[0], url)), welt["antwort"])[1],
      "_tab_stand_holen": lambda pc, spur: None, "print": lambda *a, **k: None, "_win_leerlauf_s": lambda: welt["idle"]}
for n in ast.parse(SRC).body:
    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("PULS_WACHE_FEHLT_S", "PULS_WACHE_ABSTAND_S", "PULS_WACHE_IDLE_S", "_PULS_WACHE", "TAB_URL_V_RE") for t in n.targets):
        exec(ast.get_source_segment(SRC, n), ns)
    if isinstance(n, ast.FunctionDef) and n.name in ("puls_wache_entscheiden", "_puls_wache_url", "_puls_wache_schritt"):
        exec(ast.get_source_segment(SRC, n), ns)
schritt = ns["_puls_wache_schritt"]
TV = {"type": "page", "url": "https://www.tradingview.com/chart/x/"}
PRO = {"type": "page", "url": "http://localhost:5000/?v=" + BUILD + "#accounts"}


def runden(sek, takt=65):
    t_end = uhr[0] + sek
    while uhr[0] < t_end:
        schritt("pc-pmqd8g")
        uhr[0] += takt


# Tab da → nichts
welt["liste"] = [TV, PRO]
runden(600)
check(welt["oeffnen"] == [], "Prophos-Tab da → nie öffnen")
# Tab weg (Simon 18:31) → nach ~60 s
welt["liste"] = [TV, {"type": "page", "url": "https://topstepx.com/trade"}]
t_weg = uhr[0]
runden(200)
check(len(welt["oeffnen"]) == 1 and 60 <= welt["oeffnen"][0][0] - t_weg <= 135, f"Tab weg → nach {welt['oeffnen'][0][0] - t_weg:.0f} s geöffnet (Takt des Tab-Wächters 60–70 s)" if welt["oeffnen"] else "Tab weg → geöffnet")
check(welt["oeffnen"][0][1] == "http://localhost:5000/?v=" + BUILD, f"URL mit ?v=<Build> ({welt['oeffnen'][0][1]})")
check(bool(ns["TAB_URL_V_RE"].fullmatch(welt["oeffnen"][0][1])) and "TAB_URL_V_RE.fullmatch(str(url or \"\"))" in SRC, "_tab_oeffnen lässt die URL mit ?v= durch (TAB_URL_V_RE)")
# stirbt sofort wieder → höchstens 1 je 5 min
runden(900)
abst = [b[0] - a[0] for a, b in zip(welt["oeffnen"], welt["oeffnen"][1:])]
check(len(welt["oeffnen"]) >= 3 and all(x >= 300 for x in abst), f"Tab stirbt immer wieder → Öffnen höchstens 1 je 5 min (Abstände {', '.join(f'{x:.0f}' for x in abst)} s)")
# Puls-Lauf → wartet, danach öffnen
welt["oeffnen"].clear(); uhr[0] += 400; welt["frei"] = False
runden(400)
check(welt["oeffnen"] == [], "Puls/Polar/MT5-Order läuft → kein Öffnen")
welt["frei"] = True
runden(70)
check(len(welt["oeffnen"]) == 1, "nach dem Lauf sofort in der nächsten Runde geöffnet")
# Puls-Chrome aus → nichts (startet es nicht)
welt["oeffnen"].clear(); uhr[0] += 400; welt["fehler"] = True
runden(400)
check(welt["oeffnen"] == [], "Puls-Chrome nicht erreichbar → die Wache öffnet nichts (startet kein Chrome)")
welt["fehler"] = False
# Backend gerade im Neustart (app.py nach .1989) → zählt nicht, nächste Runde erneut
welt["oeffnen"].clear(); uhr[0] += 400; welt["liste"] = [TV]
welt["antwort"] = (False, "lokales Backend (localhost:5000) antwortet nicht (URLError) — start-alles.bat")
runden(140)
n_versuche = len(welt["oeffnen"])
welt["antwort"] = (True, "ok")
runden(70)
check(n_versuche >= 1 and len(welt["oeffnen"]) == n_versuche + 1, "Backend im Neustart → nächster Versuch gleich in der nächsten Runde, nicht erst nach 5 min")
# S9: tippt jemand (Eingabe vor < 25 s) → wartet, offener Trade sperrt nicht
welt["oeffnen"].clear(); uhr[0] += 400; welt["liste"] = [TV]; welt["idle"] = 5.0
runden(300)
check(welt["oeffnen"] == [], "Eingabe am PC vor 5 s → kein Öffnen (Fokus)")
welt["idle"] = 30.0
runden(70)
check(len(welt["oeffnen"]) == 1, "30 s ohne Eingabe → geöffnet (nicht erst nach 120 s)")
# S9: Login-Adresse — der letzte Tab lief unter 127.0.0.1 → dieselbe Adresse
ns["_TAB_OEFFNEN"]["url"] = "http://127.0.0.1:5000/"
check(ns["_puls_wache_url"]() == "http://127.0.0.1:5000/?v=" + BUILD and ns["TAB_URL_V_RE"].fullmatch(ns["_puls_wache_url"]()),
      f"letzter Tab auf 127.0.0.1 → die Wache öffnet 127.0.0.1 (eigener Login) ({ns['_puls_wache_url']()})")
ns["_TAB_OEFFNEN"]["url"] = ""
check(ns["_puls_wache_url"]().startswith("http://localhost:5000/?v="), "ohne gemerkte Adresse → localhost:5000")
# Einbau
check("_puls_wache_schritt(pc)" in SRC and SRC.index("_puls_wache_schritt(pc)") < SRC.index("STUFEN-HEILUNG (30.10.2026)"), "im Tab-Wächter vor der Stufen-Heilung")
w = SRC[SRC.index("def _puls_wache_schritt("):SRC.index("def tab_neuladen_entscheiden(")]
check("json/close" not in w and "keybd_event" not in w and "riegel" not in w, "Wache schließt nichts, drückt keine Taste und fragt keinen Server-Riegel (offener Trade erlaubt)")
o = SRC[SRC.index("def _tab_oeffnen("):SRC.index("_TAB_PULS_OEFFNEN_CODE = (")]
check("TV_ORDER_LOCK.acquire(blocking=False)" in o and "'background': True" in SRC, "Öffnen unter dem Puls-Lock, neues Fenster im Hintergrund")
print("ROT:" if FEHLER else "alles grün", FEHLER if FEHLER else "")
sys.exit(1 if FEHLER else 0)
