#!/usr/bin/env python3
"""Selbsttest PW1 CLAIM-SCHUTZ (mt5-copier/panel.py puls_wache_halten, haupt_tab_halten, _haupt_tab_neu_waehlen; Master 16.11.2026 nach FM1).
Anlass: Aurel pc-pw1put 15.11. 23:19–23:21Z und Simon pc-pmqd8g 16.11. 04:47–04:49Z — Haupt-Tab in einem anderen Chrome claimt einen Start, Railway meldet
„Start geclaimt (< 6 min)“, die Puls-Wache öffnet trotzdem einen Tab im Puls-Chrome, der wird Haupt-Tab, der claimende fällt auf „nur ansehen“ → puls_still.
Fälle: (a) Riegel aus dem Tab-Stand nur frisch; (b) Wache hält bei lebendem, angemeldetem Haupt-Tab + Riegel, öffnet nach dem Riegel; (c) toter Haupt-Tab
→ sofort öffnen; (d) klemmender Riegel → nach 10 min trotzdem; (e) kein Haupt-Tab (Anlass 02.11.) → wie bisher; (f) Haupt-Tab-Wechsel zum Puls-Chrome-Tab
gesperrt, solange Riegel + alter lebt — über tab_gesehen UND _haupt_tab_runde-Weg; (g) toter alter Tab / klemmender Riegel → Wechsel. Ohne Netz.
Aufruf: python3 tools/selftest_pw1_claim_schutz.py"""
import ast
import os
import re
import sys
import types

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "mt5-copier", "panel.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


uhr = [100_000.0]
welt = {"liste": [], "oeffnen": []}
TV = {"type": "page", "url": "https://www.tradingview.com/chart/x/"}
ns = {"re": re, "os": os, "HERE": os.path.join(W, "mt5-copier"), "TAB_URL": "http://localhost:5000/",
      "TAB_NL": {}, "_TAB_OEFFNEN": {"geoeffnet": [], "geoeffnet_at": 0.0, "url": ""}, "_TABS": {}, "_TAB_HAUPT": {"tid": "", "puls_at": 0.0},
      "time": types.SimpleNamespace(time=lambda: uhr[0]), "datetime": __import__("datetime").datetime,
      "_PROPHOS_URL_RE": re.compile(r"^http://(localhost|127\.0\.0\.1):5000(/|$)"), "_cdp_get": lambda p: welt["liste"],
      "_browser_und_mt5_frei": lambda tv_eigen=False: welt.get("frei", True), "_win_leerlauf_s": lambda: 999.0,
      "_tab_oeffnen": lambda url: (welt["oeffnen"].append(uhr[0]), (True, "ok"))[1], "_tab_stand_holen": lambda pc, spur: None,
      "print": lambda *a, **k: None}
NAMEN_A = ("PULS_WACHE_FEHLT_S", "PULS_WACHE_ABSTAND_S", "PULS_WACHE_IDLE_S", "_PULS_WACHE", "TAB_URL_V_RE", "PULS_WACHE_HAUPT_LEBT_S",
           "CLAIM_RIEGEL_FRISCH_S", "CLAIM_HALTEN_MAX_S", "TAB_HAUPT_FRISCH_S", "TAB_HAUPT_SICHER_S", "TAB_URL_RE")
NAMEN_F = ("puls_wache_entscheiden", "_puls_wache_url", "_puls_wache_schritt", "puls_wache_halten", "claim_riegel", "_claim_riegel_jetzt",
           "haupt_tab_halten", "_haupt_tab_neu_waehlen", "haupt_tab_waehlen", "tab_gesehen", "neben_tab_frei", "haupt_tab_frei_api")
for n in ast.parse(SRC).body:
    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in NAMEN_A for t in n.targets):
        exec(ast.get_source_segment(SRC, n), ns)
    if isinstance(n, ast.FunctionDef) and n.name in NAMEN_F:
        exec(ast.get_source_segment(SRC, n), ns)
ns["_TAB_OEFFNEN"].update(geoeffnet=[], geoeffnet_at=0.0, url="")
schritt, CR, PH, HH = ns["_puls_wache_schritt"], ns["claim_riegel"], ns["puls_wache_halten"], ns["haupt_tab_halten"]
GEC = "Start geclaimt (< 6 min)"


def stand(riegel, alter=30):
    ns["TAB_NL"].update(stand={"ok": True, "riegel": riegel, "origin": "2026-09-22.1"}, stand_at=uhr[0] - alter)


def reset():
    welt["oeffnen"].clear(); welt["liste"] = [TV]
    ns["_PULS_WACHE"].update(fehlt_seit=None, letzter=0.0, grund="", halten_seit=None)
    ns["_TABS"].clear(); ns["_TAB_HAUPT"].update(tid="", halten=None, halten_grund=""); welt["frei"] = True
    uhr[0] += 10_000


def runden(sek, takt=65, haupt=None):
    """Tab-Wächter-Runden; haupt = Kennung, die nebenher alle ~20 s fragt (lebt in einem anderen Chrome)."""
    t_end = uhr[0] + sek
    while uhr[0] < t_end:
        if haupt:
            ns["_TABS"][haupt]["at"] = uhr[0] - 20
        schritt("pc-pw1put")
        uhr[0] += takt


# (a) Riegel nur aus frischem Stand
check(CR({"riegel": GEC}, 100.0, 200.0) == GEC and CR({"riegel": GEC}, 0.0, 200.0) == "" and CR(None, 100.0, 100.0) == "" and CR({"riegel": " "}, 100.0, 100.0) == "",
      "a) Riegel nur aus einem Tab-Stand ≤ 150 s, leer/kein Stand → keiner")
# reine Entscheidung
j = 5000.0
check(PH(GEC, 20, True, None, j)[0] is True and PH("", 20, True, None, j)[0] is False and PH(GEC, 91, True, None, j)[0] is False
      and PH(GEC, None, True, None, j)[0] is False and PH(GEC, 20, False, None, j)[0] is False,
      "b0) halten nur mit Riegel + Haupt-Tab lebt (≤ 90 s) + angemeldet")
h = PH(GEC, 20, True, j - 599, j)
h2 = PH(GEC, 20, True, j - 600, j)
check(h[0] is True and h2[0] is False and "öffnet trotzdem" in h2[1], "d0) halten höchstens 10 min am Stück, dann mit Grund „öffnet trotzdem“")

# (b) ABLAUF AUREL: Haupt-Tab lebt woanders, Start geclaimt → Wache öffnet nicht; Riegel weg → nächste Runde geöffnet
reset()
ns["_TABS"]["alt"] = {"at": uhr[0] - 10, "login": True, "puls": False}; ns["_TAB_HAUPT"]["tid"] = "alt"
stand(GEC)
t0 = uhr[0]
for _ in range(6):                                   # ~6,5 min Claim (Riegel läuft < 6 min), Stand jede Runde frisch
    stand(GEC); runden(65, haupt="alt")
check(welt["oeffnen"] == [] and "Haupt-Tab lebt in einem anderen Chrome" in ns["_PULS_WACHE"]["grund"] and GEC in ns["_PULS_WACHE"]["grund"],
      f"b) Aurel 23:20Z: Haupt-Tab woanders + „{GEC}“ → kein Tab geöffnet ({ns['_PULS_WACHE']['grund'][:90]}…)")
stand(""); runden(65, haupt="alt")
check(len(welt["oeffnen"]) == 1, "b) Riegel weg → in der nächsten Runde geöffnet (Wache wie bisher)")

# (c) Haupt-Tab tot (fragt > 90 s nicht) → sofort öffnen trotz Riegel
reset()
ns["_TABS"]["alt"] = {"at": uhr[0] - 400, "login": True, "puls": False}; ns["_TAB_HAUPT"]["tid"] = "alt"
for _ in range(3):
    stand(GEC); runden(65)
check(len(welt["oeffnen"]) == 1, "c) Haupt-Tab tot (> 90 s still) → Wache öffnet trotz Riegel (toter Tab wird ersetzt)")

# (d) klemmender Riegel → nach 10 min trotzdem
reset()
ns["_TABS"]["alt"] = {"at": uhr[0] - 10, "login": True, "puls": False}; ns["_TAB_HAUPT"]["tid"] = "alt"
t0 = uhr[0]
while not welt["oeffnen"] and uhr[0] - t0 < 1800:
    stand("Puls/Signal läuft auf diesem PC (1)"); runden(65, haupt="alt")
dauer = (welt["oeffnen"][0] - t0) if welt["oeffnen"] else None
check(dauer is not None and 600 <= dauer <= 600 + 60 + 2 * 65, f"d) Riegel klemmt → nach {dauer:.0f} s trotzdem geöffnet (10 min + Fehlt-Frist)" if dauer else "d) Riegel klemmt → nie geöffnet")

# (e) gar kein Haupt-Tab (Anlass 02.11.: Prophos-Tab ganz weg) → wie bisher, auch mit Riegel
reset()
for _ in range(3):
    stand(GEC); runden(65)
check(len(welt["oeffnen"]) == 1, "e) kein Prophos-Tab lebt → Wache öffnet wie bisher auch bei Riegel (offener Trade)")

# (f) HAUPT-TAB-WECHSEL: Simon 04:48:53Z — neuer Tab im Puls-Chrome (angemeldet, puls True) fragt, alter claimt noch
TG = ns["tab_gesehen"]
q = lambda tid: {"tab": ["1"], "login": ["1"], "url": ["http://localhost:5000/"], "tid": [tid]}   # noqa: E731
reset()
ns["_TABS"]["alt"] = {"at": uhr[0] - 15, "login": True, "puls": False}; ns["_TAB_HAUPT"]["tid"] = "alt"
ns["_TABS"]["neu"] = {"at": uhr[0] - 3, "login": True, "puls": True}
stand(GEC)
check(TG("python-requests/2.32", q("neu")) is False and ns["_TAB_HAUPT"]["tid"] == "alt", "f) Riegel + alter Tab lebt → neuer Puls-Chrome-Tab wird NICHT Haupt-Tab (tab_gesehen)")
ns["_TABS"]["neu"]["puls"] = True
check(ns["_haupt_tab_neu_waehlen"](uhr[0]) == "alt", "f) derselbe Schutz im _haupt_tab_runde-Weg (Puls-Kennzeichen nachgezogen)")
stand("")
check(TG("python-requests/2.32", q("neu")) is True and ns["_TAB_HAUPT"]["tid"] == "neu", "f) Riegel weg → der Puls-Chrome-Tab wird Haupt-Tab wie bisher (Rang)")
check("_haupt_tab_neu_waehlen(jetzt)" in SRC[SRC.index("def _haupt_tab_runde("):SRC.index("def _haupt_tab_runde(") + 2500]
      and "_haupt_tab_neu_waehlen(jetzt, tid)" in SRC[SRC.index("def tab_gesehen("):SRC.index("def neben_tab_frei(")],
      "f) beide Aufrufer der Haupt-Tab-Wahl gehen über den Claim-Schutz")
# (g) alter Tab tot → Wechsel trotz Riegel; klemmender Riegel → Wechsel nach 10 min
reset()
ns["_TABS"]["alt"] = {"at": uhr[0] - 120, "login": True, "puls": False}; ns["_TAB_HAUPT"]["tid"] = "alt"
ns["_TABS"]["neu"] = {"at": uhr[0] - 3, "login": True, "puls": True}
stand(GEC)
check(TG("python-requests/2.32", q("neu")) is True, "g) alter Haupt-Tab 120 s still → neuer wird trotz Riegel Haupt-Tab")
reset()
ns["_TABS"]["alt"] = {"at": uhr[0] - 5, "login": True, "puls": False}; ns["_TAB_HAUPT"]["tid"] = "alt"
ns["_TABS"]["neu"] = {"at": uhr[0], "login": True, "puls": True}
t0, ab = uhr[0], None
while uhr[0] - t0 < 1200:
    stand("Hedge öffnet/schließt"); ns["_TABS"]["alt"]["at"] = uhr[0] - 5
    if TG("python-requests/2.32", q("neu")):
        ab = uhr[0] - t0
        break
    uhr[0] += 5
check(ab is not None and 600 <= ab <= 610, f"g) Riegel klemmt → Wechsel nach {ab} s (10 min)")
check(HH({"a": {"at": 1000.0}}, 1000.0, "a", "a", GEC, None) == ("a", None) and HH({}, 1000.0, "", "b", GEC, None) == ("b", None),
      "g) gleiche Wahl bzw. kein bisheriger → nichts zu halten, Zeitgeber aus")
# (h) /api/haupt-tab: „nur ansehen“-Tab bekommt während Riegel + lebendem Haupt-Tab kein „frei“ (kein Neulade-Kreis)
api = SRC[SRC.index('if path == "/api/haupt-tab":'):SRC.index('if path == "/api/tab-zustand":')]
check("haupt_tab_frei_api(tid, login, time.time())" in api and "neben_tab_frei(" not in api, "h) /api/haupt-tab geht über haupt_tab_frei_api (Claim-Schutz, gemeinsamer Zeitgeber)")
tabs = {"alt": {"at": 1000.0 - 10, "login": True}, "neu": {"at": 1000.0, "login": True, "puls": True}}
check(HH(tabs, 1000.0, "alt", "neu", GEC, None)[0] == "alt" and HH(tabs, 1000.0, "alt", "neu", "", None)[0] == "neu",
      "h) gleiche Regel: mit Riegel bleibt „alt“ (→ frei False), ohne Riegel „neu“")
# (i) Prüfer MUSS 1: bisheriger Haupt-Tab NICHT angemeldet → angemeldeter Tab übernimmt sofort, auch mit Riegel (ein Tab ohne Login claimt nichts)
reset()
ns["_TABS"]["alt"] = {"at": uhr[0] - 5, "login": False, "puls": False}; ns["_TAB_HAUPT"]["tid"] = "alt"
ns["_TABS"]["neu"] = {"at": uhr[0], "login": True, "puls": True}
stand("Start in ≤ 5 min")
check(TG("python-requests/2.32", q("neu")) is True and ns["_TAB_HAUPT"]["tid"] == "neu", "i) alter Haupt-Tab ohne Login → angemeldeter neuer wird trotz Riegel Haupt-Tab")
check(HH({"alt": {"at": 995.0, "login": None}}, 1000.0, "alt", "neu", GEC, None)[0] == "neu", "i) Login unbekannt (alter Tab ohne Angabe) zählt nicht als angemeldet")

# (j) Prüfer SOLLTE 2 — ECHTER ABLAUF mit klemmendem Riegel: alter Tab fragt per tab_gesehen alle 20 s, der neue fragt 90 s lang /api/instances (gesperrt),
# danach lädt er als „nur ansehen“ neu und fragt nur noch /api/haupt-tab alle 60 s. Spätestens nach 10 min (+ eine Abfrage) muss er frei bekommen.
reset()
ns["_TABS"]["alt"] = {"at": uhr[0], "login": True, "puls": False}; ns["_TAB_HAUPT"]["tid"] = "alt"
t0, frei_ab, naechst_alt, naechst_neu, neben = uhr[0], None, uhr[0], uhr[0], False
while uhr[0] - t0 < 1500 and frei_ab is None:
    stand("Hedge öffnet/schließt")
    if uhr[0] >= naechst_alt:
        TG("python-requests/2.32", q("alt")); naechst_alt = uhr[0] + 20
    if uhr[0] >= naechst_neu:
        if not neben:
            ns["_TABS"].setdefault("neu", {"at": 0.0, "login": True, "puls": True})
            if TG("python-requests/2.32", q("neu")):
                frei_ab = uhr[0] - t0
            ns["_TABS"]["neu"]["puls"] = True
            ns["_haupt_tab_neu_waehlen"](uhr[0])                    # _haupt_tab_runde (Puls-Kennzeichen)
            naechst_neu = uhr[0] + 5
            neben = uhr[0] - t0 >= 90
        else:
            ns["_TABS"]["neu"].update(neben_at=uhr[0])
            if ns["haupt_tab_frei_api"]("neu", True, uhr[0]):
                frei_ab = uhr[0] - t0
            naechst_neu = uhr[0] + 60
    uhr[0] += 5
check(frei_ab is not None and 600 <= frei_ab <= 600 + 65, f"j) Riegel klemmt, echter Ablauf (alter fragt, neuer „nur ansehen“) → frei nach {frei_ab} s (10 min)")
check(ns["tab_gesehen"]("python-requests/2.32", q("neu")) is True, "j) nach „frei“ lädt der neue als Haupt-Tab und bleibt es (Zeitgeber abgelaufen)")
# ohne Klemmen: kurzer Claim (3 min) → danach sofort frei
reset()
ns["_TABS"]["alt"] = {"at": uhr[0], "login": True, "puls": False}; ns["_TABS"]["neu"] = {"at": 0.0, "login": True, "puls": True, "neben_at": uhr[0]}
ns["_TAB_HAUPT"]["tid"] = "alt"
stand(GEC)
gesperrt = ns["haupt_tab_frei_api"]("neu", True, uhr[0])
uhr[0] += 180; ns["_TABS"]["alt"]["at"] = uhr[0] - 3; stand("")
check(gesperrt is False and ns["haupt_tab_frei_api"]("neu", True, uhr[0]) is True, "j) Claim vorbei (Riegel weg) → „nur ansehen“-Tab bekommt frei")

# (k) Prüfer SOLLTE 3: Runden mit belegtem Lock während des Haltens setzen den Zeitgeber der Wache nicht zurück
reset()
ns["_TABS"]["alt"] = {"at": uhr[0] - 10, "login": True, "puls": False}; ns["_TAB_HAUPT"]["tid"] = "alt"
t0, k = uhr[0], 0
while not welt["oeffnen"] and uhr[0] - t0 < 1800:
    welt["frei"] = (k % 3 != 2); k += 1                          # jede dritte Runde Puls/MT5-Order läuft
    stand("Puls/Signal läuft auf diesem PC (1)"); runden(65, haupt="alt")
dauer = (welt["oeffnen"][0] - t0) if welt["oeffnen"] else None
check(dauer is not None and dauer <= 600 + 60 + 3 * 65, f"k) belegter Lock zwischendurch → trotzdem nach {dauer:.0f} s geöffnet (nicht gedehnt)" if dauer else "k) nie geöffnet")
w = SRC[SRC.index("def _puls_wache_schritt("):SRC.index("def tab_neuladen_entscheiden(")]
check(w.count("_claim_riegel_jetzt()") == 1 and "puls_wache_halten(_claim_riegel_jetzt()" in w and 'riegel' not in SRC[SRC.index("def puls_wache_entscheiden("):SRC.index("# ══ PW1 CLAIM-SCHUTZ")],
      "k) die Wache liest den Riegel genau an einer Stelle (Claim-Schutz); puls_wache_entscheiden selbst bleibt ohne Riegel")
check("_tab_stand_holen(pc, \"\")" in w and w.index("_tab_stand_holen(pc, \"\")") < w.index("puls_wache_halten("), "k) vor dem Halten-Urteil wird der Tab-Stand frisch geholt (SOLLTE 4)")
print("ROT:" if FEHLER else "alles grün", FEHLER if FEHLER else "")
sys.exit(1 if FEHLER else 0)
