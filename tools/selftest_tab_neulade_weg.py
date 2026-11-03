#!/usr/bin/env python3
"""Selbsttest NEULADE-WEG verdeckter Haupt-Tab (Betrieb 1 03.11.2026, 16:54 Dubai: 7 PC-Tabs hingen auf .2004–.2013 mit tab_bw „Tab im Hintergrund —
Panel lädt neu“), dazu S2-Stopp 03.11.2026: activate nur bei stummem PC, Rückweg zur vorher vorderen Seite, nie ?neben=1).
panel.tab_neulade_weg / cdp_vorn_erlaubt / cdp_rueckweg_seiten + Einbau im Tab-Wächter: verdeckter Haupt-Tab im Puls-Chrome → zuerst CDP genau auf ihn, nicht Strg+F5 in einem
sichtbaren Neben-Fenster. Ohne Netz. Aufruf: python3 tools/selftest_tab_neulade_weg.py"""
import os
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "mt5-copier", "panel.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


ns = {}
exec(SRC[SRC.index("def tab_neulade_weg("):SRC.index("def _win_leerlauf_s(")], ns)
F = ns["tab_neulade_weg"]
VORN = ns["cdp_vorn_erlaubt"]
RW = ns["cdp_rueckweg_seiten"]
BG = {"ok": True, "tab_bw": {"ziel": "2026-09-22.2014", "grund": "Tab im Hintergrund — Panel lädt neu", "hinter_seit": 1}}
P0 = {"id": "p1", "type": "page", "url": "http://localhost:5000/prophos"}
PN = {"id": "p2", "type": "page", "url": "http://localhost:5000/prophos?neben=1"}
check(F(BG, None, P0) == "cdp", "Haupt-Tab meldet Hintergrund, Kennung unbekannt (ein Tab) + Prophos ohne neben=1 im Puls-Chrome → CDP")
check(F({"ok": True, "tab_bw": {"grund": "Puls läuft"}}, True, P0) == "cdp", "Haupt-Tab liegt im Puls-Chrome → CDP")
check(F(BG, None, None) == "fenster", "kein Prophos im Puls-Chrome per CDP → Fenster-Weg wie bisher")
check(F({"ok": True, "tab_bw": {"grund": ""}}, False, P0) == "fenster" and F(None, None, P0) == "fenster", "sichtbarer Haupt-Tab außerhalb Puls-Chrome / kein Stand → Fenster")
# S2-Stopp 03.11.2026, Punkt 3: „verdeckt“ allein reicht nicht
check(F(BG, None, PN) == "fenster" and F(BG, True, PN) == "fenster", "Punkt 3: im Puls-Chrome nur ein ?neben=1-Tab → nie CDP (auch nicht bei Hintergrund / haupt_puls True)")
check(F(BG, False, P0) == "fenster", "Punkt 3: Haupt-Tab liegt nachweislich woanders (haupt_puls False) → Fenster, auch wenn er Hintergrund meldet")
# Punkt 1: activate nur, wenn der PC stumm ist
STUMM = {"ok": True, "riegel": "", "riegel_tv": "", "plaene_offen_tv": 0}
check(VORN(STUMM, []) is True, "Punkt 1: PC stumm (kein offener TV-/TSX-Plan, kein Riegel, kein scharfer Trade) → activate erlaubt")
check(VORN(dict(STUMM, plaene_offen_tv=1), []) is False, "Punkt 1: offener TV-/TSX-Plan → kein activate, nur Page.reload im Hintergrund")
check(VORN(dict(STUMM, plaene_offen_tv=None), []) is False and VORN({"ok": True, "riegel": ""}, []) is False, "Punkt 1: Plan-Zahl unbekannt → kein activate")
check(VORN(STUMM, ["1234"]) is False, "Punkt 1: offener scharfer TV-Trade mit Hedge → kein activate")
check(VORN(dict(STUMM, riegel="Start in ≤ 5 min"), []) is False and VORN(dict(STUMM, riegel_tv="Hedge öffnet/schließt"), []) is False, "Punkt 1: Riegel → kein activate")
check(VORN(None, []) is False and VORN({"ok": False}, []) is False and VORN(dict(STUMM, plaene_offen_tv=False), []) is False, "Punkt 1: kein/kaputter Stand → kein activate")
# Punkt 2: Rückweg zur Seite, die vorher vorn war
TSX = {"id": "t1", "type": "page", "url": "https://topstepx.com/trade"}
TV = {"id": "v1", "type": "page", "url": "https://www.tradingview.com/chart/"}
check(RW([{"id": "x", "type": "service_worker"}, TSX, TV, P0], "p1") == [TSX, TV],
      "Punkt 2: TopstepX (Fenster B) und TradingView (Fenster A) waren vor Prophos sichtbar → beide zurück, jüngste zuerst (nicht pauschal TradingView)")
check(RW([TV, P0, TSX], "p1") == [TV] and RW([P0, TV], "p1") == [], "Punkt 2: nur die Seiten vor Prophos; Prophos war schon vorn → kein Rückweg")
check(RW([TV, TSX], "p1") == [TV] and RW([], "p1") == [] and len(RW([dict(TV, id=str(i)) for i in range(20)] + [P0], "p1")) == 8,
      "Punkt 2: Prophos nicht in der Liste → vorderste Seite; leer → keiner; höchstens 8")
c = SRC[SRC.index("def _prophos_tab_neuladen_cdp("):SRC.index("def _prophos_tab_neu_oeffnen(")]
check("if vorn:\n                _cdp_get(f\"/json/activate/{pro['id']}\")" in c and c.count("/json/activate/{pro['id']}") == 1,
      "Punkt 1: activate des Prophos-Tabs nur unter „if vorn:“")
check("vorn = cdp_vorn_erlaubt(stand, scharf_konto_fest())" in c and "vorher = cdp_rueckweg_seiten(liste, pro.get(\"id\")) if vorn else []" in c,
      "Punkt 1/2: vorn aus dem Tab-Stand, vorher vorn liegende Seite gemerkt")
check("for t in reversed(vorher):\n                        _cdp_get(f\"/json/activate/{t['id']}\")" in c and "/json/activate/{tv['id']}" not in c, "Punkt 2: Rückweg aktiviert die vorher vorderen Seiten (älteste zuerst, je Fenster die jüngste zuletzt), nie pauschal tv[0]")
check(c.index("finally:\n            zurueck") > c.index("c.rufe('Page.reload'"), "Punkt 2: Rückweg auch nach einem Page.reload-Fehler (finally)")
check('if "neben=1" in str(pro.get("url") or ""):' in c and c.index('"neben=1"') < c.index("c.rufe('Page.reload'"), "Punkt 3: Neuladen selbst lädt nie einen ?neben=1-Tab")
check("TV_ORDER_LOCK.release()\n                gehalten = False" in c and "if gehalten:\n            TV_ORDER_LOCK.release()" in c,
      "im Hintergrund: Lock nach dem Page.reload frei, kein doppeltes release")
check('"neuladen": lambda: _prophos_tab_neuladen_cdp(stand)' in SRC, "Selbstheiler Stufe 2 reicht den Tab-Stand durch (activate nur, wenn der PC stumm ist)")
w = SRC[SRC.index("def _tab_neulade_waechter():"):SRC.index("# ══ TAB WECKEN")]
check("weg = tab_neulade_weg(stand, (_TABS.get(_TAB_HAUPT.get(\"tid\")) or {}).get(\"puls\"), pro0)" in w
      and w.index("_prophos_tab_neuladen_cdp(stand)") < w.index("ok, msg = _prophos_tab_neu_laden()") and "_prophos_tab_neuladen_cdp()" not in w,
      "Wächter: Weg wählen mit pro0 (nicht bool), CDP vor Strg+F5, Tab-Stand durchgereicht")
check('if weg != "cdp" and not ok and "kein Chrome-Fenster mit aktivem Prophos-Tab" in str(msg):' in w, "Fenster-Weg behält den CDP-Rückfall, kein Doppel-Neuladen")
k = w.index("laden, grund, TAB_NL[\"hinter_seit\"] = tab_neuladen_entscheiden(")
check(w.index("if laden:", k) > k, "Riegel unverändert: tab_neuladen_entscheiden (Server-Riegel, Puls/MT5-Lock, 120 s Ruhe, 15 min Abstand) entscheidet vorher")
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
