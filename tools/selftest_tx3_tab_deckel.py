#!/usr/bin/env python3
"""Selbsttest TX3 (Finn 24.11.2026: „Aktuell werden manchmal 20, 30 Tabs auf einmal geöffnet bei irgendeinem Fehlstart. Maximal 3 Fehlstarts
und dann aufhören, aber nicht 500 Tabs öffnen.“). Kein Chrome, kein Netz, keine Order.

Befund: die Tab-Flut waren umgeleitete TopstepX-Tabs auf login.topstep.com (pc-pmqd8g 16, pc-l5o8bv 7, pc-7ftp5l ~35 — TX2 räumt sie seit .2298);
je Plan liefen 1 + 3 Neuplanungen = 4 Starts (SF_MAX zählte Neuplanungen). Prüft:
 (1) puls_tab_deckel_urteil: höchstens PULS_TAB_DECKEL_N neue Tabs je PULS_TAB_DECKEL_S, alte Zeitpunkte fallen heraus;
 (2) _puls_tab_deckel zählt in puls_tabs_neu.json und sperrt ab dem (N+1)-ten Tab mit Spur „Tab-Deckel“;
 (3) alle Stellen, an denen der Bot im Puls-Chrome einen Tab öffnet, fragen vorher den Deckel (keine /json/new ohne Deckel);
 (4) _cdp_tab_neu öffnet bei vollem Deckel nichts (kein /json/new-Aufruf);
 (5) prophos.html: SF_MAX = 2 → höchstens 3 Starts je Plan (1 + 2 Neuplanungen)."""
import inspect
import json
import os
import re
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


N, S = ob.PULS_TAB_DECKEL_N, ob.PULS_TAB_DECKEL_S
check(N <= 6 and S >= 600, f"Deckel höchstens 6 Tabs je ≥ 10 min ({N}/{int(S)} s)")

# (1) rein rechnend
t0 = 1_000_000.0
frei, z, n = ob.puls_tab_deckel_urteil([], t0)
check(frei and z == [t0] and n == 0, "leer → frei, Zeitpunkt angehängt")
voll = [t0 - i * 10 for i in range(N)]
frei, z, n = ob.puls_tab_deckel_urteil(voll, t0)
check(not frei and n == N, f"{N} Tabs in 10 min → gesperrt")
frei, z, n = ob.puls_tab_deckel_urteil([t0 - S - 1] * 10 + voll[:N - 1], t0)
check(frei and n == N - 1 and len(z) == N, "Zeitpunkte älter als das Fenster zählen nicht")
check(ob.puls_tab_deckel_urteil(["x", None, t0 + 5], t0)[0], "Müll und Zukunft zählen nicht")

# (2) mit Datei
alt_hier = ob._AUGEN_HIER
with tempfile.TemporaryDirectory() as d:
    ob._AUGEN_HIER = d
    try:
        tr = []
        erg = [ob._puls_tab_deckel(tr, f"Tab {i}") for i in range(N + 2)]
        check(erg == [True] * N + [False, False], f"die ersten {N} frei, danach gesperrt ({erg})")
        check(sum("Tab-Deckel" in x and "nichts gesendet" in x for x in tr) == 2, "Spur „Tab-Deckel … nichts gesendet“ je gesperrtem Tab")
        check(os.path.exists(os.path.join(d, "puls_tabs_neu.json")), "Zählung in puls_tabs_neu.json neben dem Bot (alle Läufe des PCs)")

        # (4) _cdp_tab_neu bei vollem Deckel
        alt_http = ob._cdp_http
        aufrufe = []
        ob._cdp_http = lambda pfad, methode="GET", timeout=2.0: aufrufe.append(pfad) or {"id": "x", "webSocketDebuggerUrl": "ws://127.0.0.1:9333/x"}
        try:
            tr2 = []
            check(ob._cdp_tab_neu("https://www.tradingview.com/chart/", tr2) is None and not any("/json/new" in a for a in aufrufe),
                  "Deckel voll → _cdp_tab_neu öffnet nichts")
            check(ob._tsx_tab_sicher.__code__ is not None, "_tsx_tab_sicher vorhanden")
        finally:
            ob._cdp_http = alt_http
    finally:
        ob._AUGEN_HIER = alt_hier

# (3) jede Tab-Öffnung hinter dem Deckel
src = open(os.path.join(WURZEL, "mt5-copier", "order_bot.py"), encoding="utf-8").read()
for fn in (ob._cdp_tab_neu, ob._tsx_tab_sicher, ob._tsx_auge_reparieren if hasattr(ob, "_tsx_auge_reparieren") else None,
           ob._cdp_tab_eigenes_fenster):
    if fn is None:
        continue
    q = inspect.getsource(fn)
    if '_cdp_http("/json/new' in q or 'rufe("Target.createTarget"' in q:
        i_d = q.find("_puls_tab_deckel(")
        i_o = min(x for x in (q.find('_cdp_http("/json/new'), q.find('rufe("Target.createTarget"')) if x >= 0)   # der Aufruf, nicht der Docstring
        check(0 <= i_d < i_o, f"{fn.__name__}: Deckel vor dem Öffnen")
offen = [m.start() for m in re.finditer(r'_cdp_http\("/json/new\?|_cdp_http\(f?"/json/new|"Target\.createTarget"', src)]
ungeschuetzt = []
for pos in offen:
    davor = src[max(0, pos - 900):pos]
    if "_puls_tab_deckel(" not in davor:
        zeile = src.count("\n", 0, pos) + 1
        ungeschuetzt.append(zeile)
check(not ungeschuetzt, f"jede /json/new bzw. Target.createTarget im Bot hat den Deckel direkt davor (ohne: Zeilen {ungeschuetzt})")

# (4b) Prüfer TX3: nach einem Deckel-Stopp kein harter Chrome-Neustart (der Neustart startet Chrome mit URL — am Deckel vorbei)
neu_n, aus = [], []
alt_flag = ob._TAB_DECKEL_ZU[0]
try:
    ob._TAB_DECKEL_ZU[0] = True
    r1 = {"ok": False, "code": "tab", "msg": "TopstepX-Tab im Puls-Chrome nicht erreichbar.", "trail": "x > Tab-Deckel: schon 6 neue Tabs"}
    erg = ob._puls_mit_neustart("tsv2", lambda: (json.dumps(r1), dict(r1)), lambda frist: (None, None), None, "https://topstepx.com/trade",
                                neustart=lambda *a, **k: neu_n.append(1) or True, jetzt=lambda: 10.0, t0=0.0, ausgeben=aus.append,
                                diagnose=lambda *a, **k: None, foto=None, ablage=None)
    check(not neu_n and len(aus) == 1 and "chrome_neustart: nein — Tab-Deckel" in str(aus[0].get("trail")),
          "Deckel-Stopp → kein Chrome-Neustart, eine Antwort mit Grund „Tab-Deckel“")
    ob._TAB_DECKEL_ZU[0] = False
    art, _g, _r = ob.neustart_entscheid(dict(r1), "tsv2", 10.0, lesung_moeglich=False)
    check(art != "nein", f"Gegenprobe: ohne Deckel-Stopp hätte derselbe Fehler neu gestartet (art {art!r}) — der Test misst den Riegel")
finally:
    ob._TAB_DECKEL_ZU[0] = alt_flag

# (5) Frontend
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("const SF_MAX = 2, SF_WARTE_MS" in html, "prophos.html SF_MAX = 2 → 1 Start + 2 Neuplanungen = höchstens 3 Starts je Plan")
check("sfFehlversuche(sf) >= SF_MAX" in html, "Deckel weiter über sfFehlversuche ≥ SF_MAX (Neuplanungen ohne Windows-Abfragen)")
check("Start ${sfFehlversuche(sf) + 1} von ${SF_MAX + 1} gescheitert" in html and "Start ${n + 2}/${SF_MAX + 1}" in html
      and "Versuch ${n + 1}/${SF_MAX}" not in html, "Texte zählen Starts (von SF_MAX + 1 = 3), nicht Neuplanungen")

print()
print("ALLES OK" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
