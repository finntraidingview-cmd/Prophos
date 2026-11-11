#!/usr/bin/env python3
"""Selbsttest NL2 TABSTREIFEN-WEG (11.11.2026, Master nach NL1/S2: Jona pc-b97zc7 + Ahaj pc-na1q6b hingen seit 19:12 Dubai auf .2181, Julian pc-6qnjpu seit
20:05 auf .2187 — „kein Chrome-Fenster mit aktivem Prophos-Tab“, kein Puls-Chrome :9333, Prophos verdeckt im normalen Chrome).
panel.tabstreifen_tabs / tabstreifen_ziel / streifen_weg_noetig + der UIA-Prozess (_TAB_STREIFEN_HAUPT) mit NACHGEBAUTEM UIA-Baum (falsches pywinauto) +
Einbau im Tab-Wächter. Ohne Netz, ohne Windows. Aufruf: python3 tools/selftest_nl2_tabstreifen.py"""
import io
import json
import os
import re
import sys
import types
import contextlib

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "mt5-copier", "panel.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


ns = {"re": re}
exec(SRC[SRC.index("_TAB_STREIFEN_WALKER = r"):SRC.index("def _streifen_lauf(")], ns)
TABS, ZIEL, NOETIG, HAUPT = ns["tabstreifen_tabs"], ns["tabstreifen_ziel"], ns["streifen_weg_noetig"], ns["_TAB_STREIFEN_HAUPT"]


# ── nachgebauter UIA-Baum ──
class El:
    def __init__(self, ct, name="", kinder=(), sel=None, handle=0, klasse="", fehler=False, waehlbar=("select",)):
        self.control_type, self.name, self._k, self.sel = ct, name, list(kinder), sel
        self.handle, self.class_name, self.fehler, self.waehlbar = handle, klasse, fehler, waehlbar
        self.betreten = 0

    def children(self):
        self.betreten += 1
        if self.fehler:
            raise OSError("COM")
        return self._k


def chrome(handle, titel, tabs, klasse="Chrome_WidgetWin_1", doc_kinder=()):
    """Fenster wie Chrome: Pane > Pane(TopContainer) > Tab(TabStrip) > TabItem …, daneben der Webinhalt (Document)."""
    doc = El("Document", "Seite", kinder=list(doc_kinder))
    strip = El("Tab", "Tabstreifen", kinder=[El("TabItem", n, sel=s) for n, s in tabs] + [El("Button", "Neuer Tab")])
    w = El("Window", titel, kinder=[El("Pane", "", kinder=[El("Pane", "", kinder=[strip]), El("Pane", "", kinder=[doc])])], handle=handle, klasse=klasse)
    w.doc = doc
    w.strip = strip
    return w


# 1) Breitensuche: Reihenfolge, Webinhalt nie betreten, Fehler einzelner Knoten
fremd = El("TabItem", "Prophos")   # ein „Tab“ IM Webinhalt (z. B. Reiter in einer Seite) — darf nie zählen
w1 = chrome(101, "TradingView - Google Chrome", [("TradingView", True), ("Prophos", False), ("Gmail", False)], doc_kinder=[fremd])
t = TABS(w1)
check([x.name for x in t] == ["TradingView", "Prophos", "Gmail"], "Walker: TabItems in Tabstreifen-Reihenfolge")
check(w1.doc.betreten == 0, "Walker: Webinhalt (Document) wird nie betreten — auch kein TabItem in einer Seite")
kaputt = El("Window", "x", kinder=[El("Pane", fehler=True), El("Tab", kinder=[El("TabItem", "Prophos", sel=False)])])
check([x.name for x in TABS(kaputt)] == ["Prophos"], "Walker: ein Knoten mit COM-Fehler kostet nicht den Rest")
tief = El("Window")
cur = tief
for _ in range(30):
    n = El("Pane")
    cur._k = [n]
    cur = n
cur._k = [El("TabItem", "Prophos")]
check(TABS(tief, max_tiefe=14) == [], "Walker: Tiefe begrenzt (max_tiefe)")
breit = El("Window", kinder=[El("Pane", kinder=[El("Pane") for _ in range(50)]) for _ in range(50)])
TABS(breit, max_knoten=100)
check(sum(1 for p in breit._k for q in p._k if q.betreten) <= 100, "Walker: Knoten begrenzt (max_knoten)")


def lesung(*fenster, gesperrt=""):
    return [{"hwnd": f.handle, "titel": f.name, "klasse": f.class_name, "tabs": [{"name": x.name, "sel": x.sel} for x in TABS(f)], "gesperrt": gesperrt}
            for f in fenster]


# 2) Entscheidung: hinten / vorn / fehlt / falsches Fenster / mehrdeutig
z, g = ZIEL(lesung(w1))
check(z == {"hwnd": 101, "idx": 1, "name": "Prophos", "vorher_idx": 0, "vorher_name": "TradingView", "anzahl": 3} and g == "",
      "Tab HINTEN: Ziel = Prophos-Tab, vorher = aktiver Tab im selben Fenster")
w_vorn = chrome(102, "Prophos - Google Chrome", [("Prophos", True), ("TradingView", False)])
z, g = ZIEL(lesung(w_vorn))
check(z is None and "schon vorn" in g, "Tab VORN: nichts gedrückt (Fenster-Weg zuständig)")
w_ohne = chrome(103, "TradingView - Google Chrome", [("TradingView", True), ("Gmail", False)])
z, g = ZIEL(lesung(w_ohne))
check(z is None and "kein Tab „Prophos" in g, "Tab FEHLT: nichts gedrückt, Grund nennt es")
edge = chrome(104, "TradingView - Microsoft Edge", [("TradingView", True), ("Prophos", False)])
andere = chrome(105, "Prophos", [("TradingView", True), ("Prophos", False)], klasse="MozillaWindowClass")
z, g = ZIEL(lesung(edge, andere))
check(z is None and "kein Chrome-Fenster" in g, "FALSCHES FENSTER (Edge-Titel, fremde Klasse): nie ein Ziel")
z, g = ZIEL(lesung(edge, w1))
check(z and z["hwnd"] == 101, "falsches Fenster daneben stört nicht — Ziel im echten Chrome-Fenster")
w2 = chrome(106, "Gmail - Google Chrome", [("Gmail", True), ("Prophos", False)])
z, g = ZIEL(lesung(w1, w2))
check(z is None and "2 Tabs" in g and "nichts gedrückt" in g, "zwei Prophos-Tabs (Haupt + nur ansehen?) in zwei Fenstern → nichts gedrückt")
w3 = chrome(107, "TradingView - Google Chrome", [("TradingView", True), ("Prophos", False), ("Prophos", False)])
z, g = ZIEL(lesung(w3))
check(z is None and "2 Tabs" in g, "zwei Prophos-Tabs im selben Fenster → nichts gedrückt")
w4 = chrome(108, "x - Google Chrome", [("TradingView", None), ("Prophos", False)])
z, g = ZIEL(lesung(w4))
check(z is None and "nicht eindeutig" in g, "aktiver Tab nicht lesbar (sel None) → nichts gedrückt")
w5 = chrome(109, "x - Google Chrome", [("A", True), ("B", True), ("Prophos", False)])
check(ZIEL(lesung(w5))[0] is None, "zwei aktive Tabs gelesen → nichts gedrückt")
check(ZIEL([{"hwnd": None, "titel": "x - Google Chrome", "klasse": "Chrome_WidgetWin_1", "tabs": [{"name": "A", "sel": True}, {"name": "Prophos", "sel": False}]}])[0] is None,
      "Fenster-Kennung fehlt → nichts gedrückt")
check(ZIEL(lesung(chrome(110, "x - Google Chrome", [("TV", True), ("Prophos - Speichernutzung 120 MB", False)])))[0]["idx"] == 1,
      "Tab-Name mit Chrome-Zusatz („Prophos - …“) zählt")
check(ZIEL(lesung(chrome(111, "x - Google Chrome", [("TV", True), ("Prophosfoo", False), ("Echo-Panel", False)])))[0] is None,
      "„Prophosfoo“/„Echo-Panel“ zählen nicht")
check(ZIEL(lesung(chrome(112, "x - Google Chrome", [("TV", True), ("Prophos-Backend", False)])))[0] is None,
      "Backend-Konsole „Prophos-Backend“ zählt nie (wie order_bot.prophos_tab_wahl)")
z, g = ZIEL(lesung(w1, gesperrt="Terminal 1 (Profile 1)"))
check(z is None and "gesperrten Fenster" in g and "Terminal 1" in g, "Prophos im Reader-Profil/Puls-Chrome (order_bot._fenster_gesperrt) → nichts gedrückt")
z, g = ZIEL(lesung(w1, gesperrt=None))
check(z is None and "nicht lesbar" in g, "Sperre nicht lesbar → nichts gedrückt (nie raten)")
check(ZIEL([])[0] is None and ZIEL(None)[0] is None and ZIEL([1, "x"])[0] is None, "leere/kaputte Lesung → nichts")

# 3) Wann der Weg überhaupt greift
M = "kein Chrome-Fenster mit aktivem Prophos-Tab gefunden (Prophos-Tab zu oder nicht vorn in seinem Fenster) — am PC Prophos öffnen bzw. den Tab anklicken"
check(NOETIG(M, False, None) is True, "Fenster leer + :9333 zu + kein CDP-Prophos → Tabstreifen-Weg")
check(NOETIG(M, True, None) is False, ":9333 erreichbar → NICHT (Puls-Chrome zuständig: Puls-Wache/CDP)")
check(NOETIG(M, False, {"id": "p"}) is False, "Prophos per CDP da → NICHT")
check(NOETIG("„Prophos“ kam nicht nach vorn — nichts gedrückt", False, None) is False, "Fenster-Weg scheiterte anders (Fenster da) → NICHT")
check(NOETIG(M, False, None, False) is False and NOETIG(M, False, None, None) is True, "Schalter tab_streifen:false → aus, fehlt → an")

# 4) UIA-Prozess selbst mit falschem pywinauto: lesen + waehlen
CODE = ns["_TAB_STREIFEN_WALKER"] + HAUPT
compile(CODE, "<streifen>", "exec")
check(True, "UIA-Prozess-Code (Walker-Quelle + Haupt) kompiliert")
check("code = _TAB_STREIFEN_WALKER + _TAB_STREIFEN_HAUPT" in SRC and "exec(_TAB_STREIFEN_WALKER, globals())" in SRC and "inspect.getsource" not in SRC[SRC.index("_TAB_STREIFEN_WALKER"):SRC.index("def _tab_oeffnen(")],
      "Walker: EINE Quelle für Panel und Prozess (kein inspect.getsource — nach Code-Sync falsche Zeilen)")

FENSTER = {}
GEWAEHLT = []


class Wrap:
    def __init__(self, el):
        self.el = el

    def is_selected(self):
        if self.el.sel is None:
            raise RuntimeError("kein SelectionItem")
        return self.el.sel

    def select(self):
        if "select" not in self.el.waehlbar:
            raise RuntimeError("kein SelectionItem")
        GEWAEHLT.append(("select", self.el.name))

    def invoke(self):
        if "invoke" not in self.el.waehlbar:
            raise RuntimeError("kein Invoke")
        GEWAEHLT.append(("invoke", self.el.name))


class Desk:
    def __init__(self, backend):
        assert backend == "uia"

    def windows(self, class_name=None, visible_only=True):
        AUFRUF.append(visible_only)
        return [types.SimpleNamespace(element_info=f) for f in FENSTER.values() if f.class_name == class_name and (not visible_only or not getattr(f, "mini", False))]


AUFRUF = []
GESPERRT = {}


def prozess(*argv):
    pw = types.ModuleType("pywinauto")
    pw.Desktop = Desk
    ei = types.ModuleType("pywinauto.uia_element_info")
    ei.UIAElementInfo = lambda h: FENSTER[int(h)]
    ctl = types.ModuleType("pywinauto.controls")
    uw = types.ModuleType("pywinauto.controls.uiawrapper")
    uw.UIAWrapper = Wrap
    ob = types.ModuleType("order_bot")
    ob._fenster_gesperrt = lambda h: GESPERRT.get(int(h), "")
    alt = dict(sys.modules)
    sys.modules.update({"pywinauto": pw, "pywinauto.uia_element_info": ei, "pywinauto.controls": ctl, "pywinauto.controls.uiawrapper": uw, "order_bot": ob})
    argv0 = sys.argv
    sys.argv = ["-c", *[str(a) for a in argv]]
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            exec(CODE, {"__name__": "__main__"})
    finally:
        sys.argv = argv0
        sys.modules.clear()
        sys.modules.update(alt)
    return json.loads(out.getvalue().strip().splitlines()[-1])


FENSTER.update({101: chrome(101, "TradingView - Google Chrome", [("TradingView", True), ("Prophos", False)]),
                104: chrome(104, "Prophos - Microsoft Edge", [("Prophos", True)]),
                105: chrome(105, "Prophos", [("Prophos", True)], klasse="MozillaWindowClass")})
L = prozess("lesen")
check([f["hwnd"] for f in L] == [101], "Prozess lesen: nur Chrome-Hauptfenster (Edge-Titel und fremde Klasse fallen raus)")
check(L[0]["tabs"] == [{"name": "TradingView", "sel": True}, {"name": "Prophos", "sel": False}] and L[0]["klasse"] == "Chrome_WidgetWin_1"
      and L[0]["gesperrt"] == "", "Prozess lesen: Tabs mit Name + aktiv + Sperre (frei)")
check(AUFRUF and AUFRUF[-1] is False, "Prozess lesen: visible_only=False (minimierte Fenster sind UIA-offscreen)")
FENSTER[120] = chrome(120, "TradingView - Google Chrome", [("TradingView", True), ("Gmail", False)])
FENSTER[120].mini = True
check(120 in [f["hwnd"] for f in prozess("lesen")], "Prozess lesen: minimiertes Fenster wird mitgelesen")
del FENSTER[120]
GESPERRT[101] = "Puls-Chrome (CDP)"
L2 = prozess("lesen")
check(L2[0]["gesperrt"] == "Puls-Chrome (CDP)" and ZIEL(L2)[0] is None, "Prozess lesen: Sperre aus order_bot._fenster_gesperrt → kein Ziel")
del GESPERRT[101]
z, _g = ZIEL(L)
check(z and z["idx"] == 1, "Prozess lesen → Entscheidung findet den Prophos-Tab hinten")
r = prozess("waehlen", 101, 1, "Prophos")
check(r == {"ok": True, "weg": "SelectionItem"} and GEWAEHLT[-1] == ("select", "Prophos"), "Prozess waehlen: SelectionItem auf genau dem Tab")
FENSTER[101].strip._k[1].waehlbar = ("invoke",)
r = prozess("waehlen", 101, 1, "Prophos")
check(r == {"ok": True, "weg": "Invoke"} and GEWAEHLT[-1] == ("invoke", "Prophos"), "Prozess waehlen: Rückfall Invoke")
FENSTER[101].strip._k[1].waehlbar = ()
r = prozess("waehlen", 101, 1, "Prophos")
check(r["ok"] is False and "nicht wählbar" in r["msg"], "Prozess waehlen: weder SelectionItem noch Invoke → Fehler, nichts gewählt")
n0 = len(GEWAEHLT)
r = prozess("waehlen", 101, 1, "Gmail")
check(r["ok"] is False and "geändert" in r["msg"] and len(GEWAEHLT) == n0, "Prozess waehlen: Name passt nicht mehr (Tabstreifen geändert) → nichts gewählt")
r = prozess("waehlen", 101, 7, "Prophos")
check(r["ok"] is False and len(GEWAEHLT) == n0, "Prozess waehlen: Index weg → nichts gewählt")
FENSTER[101].strip._k[1].waehlbar = ("select",)
FENSTER[101].strip._k[0].name = "MNQ1! 21 034,25 ▲ +0,4 %"   # TradingView-Titel hat sich bewegt
n0 = len(GEWAEHLT)
r = prozess("zurueck", 101, 0, 2)
check(r["ok"] is True and GEWAEHLT[-1] == ("select", "MNQ1! 21 034,25 ▲ +0,4 %"), "Prüfer MUSS: zurück über Platz + Tab-Zahl, auch wenn der Titel wechselte")
r = prozess("zurueck", 101, 0, 3)
check(r["ok"] is False and len(GEWAEHLT) == n0 + 1, "zurück: Tab-Zahl anders → nichts gewählt")
r = prozess("zurueck", 101, 1, 2)
check(r["ok"] is False and len(GEWAEHLT) == n0 + 1, "zurück: Platz ist ein Prophos-Tab → nichts gewählt")
check("mouse" not in HAUPT and "click" not in HAUPT, "Prozess: keine Maus, kein Klick")

# 5) Ausführung + Einbau (Textanker)
ex = SRC[SRC.index("def _prophos_tab_neuladen_streifen("):SRC.index("def _tab_oeffnen(")]
check("TV_ORDER_LOCK.acquire(blocking=False)" in ex and "_browser_und_mt5_frei(tv_eigen=True)" in ex, "Riegel: TV_ORDER_LOCK + keine MT5-Order/Polar")
check("_tipp_sperre_versuchen()" in ex and 'if art != "frei":' in ex and "_tipp_sperre_frei(tipp)" in ex, "Riegel: PC-Tipp-Sperre der Echo-Läufe (belegt/unbekannt = abbrechen), wird wieder frei")
check(ex.index('_cdp_get("/json/version", timeout=5.0)') < ex.index('_streifen_lauf("lesen")') < ex.index("TV_ORDER_LOCK.acquire(blocking=False)"),
      "Prüfer SOLLTE: :9333 vor dem Weg nochmal mit 5 s prüfen; Lesen vor den Sperren (kürzere Haltezeit)")
check("def _streifen_lauf(*args, timeout=20):" in SRC, "Prozess-Zeitlimit 20 s")
check('ECHO_TIPP_MUTEX_PANEL = "Local\\\\ProphosEchoTipp"' in SRC and 'ECHO_TIPP_MUTEX = "Local\\\\ProphosEchoTipp"' in open(os.path.join(W, "mt5-copier", "order_bot.py"), encoding="utf-8").read(),
      "Tipp-Sperre: derselbe Mutex-Name wie order_bot")
i_waehl, i_titel, i_f5 = ex.index('_streifen_lauf("waehlen", hwnd, ziel["idx"]'), ex.index("_PROPHOS_TAB_RE.match(titel)"), ex.index("u32.keybd_event(0x74")
check(i_waehl < i_titel < i_f5, "Reihenfolge: wählen → Titel-Beweis „Prophos …“ → erst dann Strg+F5")
check(ex.count("GetForegroundWindow() or 0) != hwnd") >= 2, "Vordergrund-Beweis direkt vor dem Druck")
check('_streifen_lauf("zurueck", hwnd, ziel["vorher_idx"], ziel["anzahl"])' in ex and "if gewaehlt:" in ex and "SW_MINIMIZE" in ex, "Rückweg: vorheriger Tab, minimiert bleibt minimiert (auch nach Fehler)")
check('_TAB_OEFFNEN["zuletzt"] >= t0' in ex, "Beweis: Tab fragt nach dem Neuladen wieder beim Panel")
wa = SRC[SRC.index("def _tab_neulade_waechter("):SRC.index("# ══ TAB WECKEN (F1")]
check("elif streifen_weg_noetig(msg, cdp_da, pro, (base_config() or {}).get(\"tab_streifen\")):" in wa
      and "ok, msg = _prophos_tab_neuladen_streifen()" in wa, "Einbau: nach Fenster-Weg und CDP-Rückfall, nur über streifen_weg_noetig")
check(wa.index("if pro:") < wa.index("elif streifen_weg_noetig("), "Einbau: CDP-Prophos geht vor dem Tabstreifen")
check("pro, cdp_da = None, False" in wa, "Einbau: :9333 wirft → cdp_da False")
check('msg = f"per Tabstreifen im normalen Chrome (kein Puls-Chrome): {msg}"' in wa and "TAB_NL.update(ergebnis=grund" in wa,
      "Ergebnis in die tab-stand-Spur (ergebnis + grund wie die anderen Wege)")

print(f"\n{'ALLES GRÜN' if not FEHLER else str(len(FEHLER)) + ' ROT'}")
sys.exit(1 if FEHLER else 0)
