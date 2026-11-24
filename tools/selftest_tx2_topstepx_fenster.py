#!/usr/bin/env python3
"""Selbsttest TX2 (24.11.2026, Auftrag Master nach Befund FS1: TopstepX-Google-Weg klickt nie — „Puls-Chrome-Fenster nicht eindeutig gefunden —
nichts geklickt", zwei Läufe in derselben Sekunde, 16 bzw. ~35 gestapelte „Topstep | Sign in"-Tabs auf pc-pmqd8g/pc-7ftp5l).
Kein Chrome, kein Netz, keine Order.

Aufruf:  python3 tools/selftest_tx2_topstepx_fenster.py
Prüft:
 (1) _handlauf_nehmen ist atomar: 8 Prozesse gleichzeitig → genau einer bekommt die Sperre; frische Sperre → False; alte (> 15 min) → neu;
     alle drei Lauf-Einstiege (tsxlesen_cdp, tsxinventar_cdp, K3) nehmen die Sperre nur noch über _handlauf_nehmen;
 (2) puls_fenster_marke: genau das eine Fenster mit der Marke, nie bei mehreren/keinem/kurzer Marke;
 (3) _AugenSitzung._win_per_marke: setzt die Marke, findet das Fenster, nimmt die Marke wieder weg, merkt sich das Fenster; ohne Treffer None
     und Titel trotzdem zurück; _win_vorn nimmt den Rückfall nur, wenn puls_fenster_waehlen nichts findet;
 (4) tsx_login_tabs_ueberzaehlig: nur https://login.topstep.com/…-Seiten, nie der eigene Tab, nie topstepx.com/TradingView/Google/Prophos;
     _tsx_login_tabs_zu räumt nur, wenn DIESER Prozess die Sperre hält; Aufrufe vor /json/new und vor dem Google-Klick;
 (5) die neue Anmeldeseite (E-Mail zuerst, „Continue with Google", live gelesen auf pc-pmqd8g) ist art 'google' mit genau einem Knopf."""
import inspect
import json
import multiprocessing
import os
import sys
import tempfile
import time

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def _nehmer(ordner, start, q):
    import order_bot as ob_
    ob_._AUGEN_HIER = ordner
    while time.time() < start:
        time.sleep(0.001)
    q.put(bool(ob_._handlauf_nehmen()))


if __name__ == "__main__":
    # (1) atomare Sperre
    with tempfile.TemporaryDirectory() as d:
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        start = time.time() + 2.0
        ps = [ctx.Process(target=_nehmer, args=(d, start, q)) for _ in range(8)]
        for p_ in ps:
            p_.start()
        for p_ in ps:
            p_.join(30)
        erg = [q.get(timeout=5) for _ in ps]
        check(erg.count(True) == 1, f"8 Läufe gleichzeitig → genau einer hält die Sperre ({erg.count(True)}× True)")
        alt_hier = ob._AUGEN_HIER
        ob._AUGEN_HIER = d
        try:
            pfad = os.path.join(d, ob.HANDLAUF_SPERRE)
            check(ob._handlauf_nehmen() is False and ob._handlauf_aktiv(), "frische Sperre steht → zweiter Lauf bekommt sie nicht")
            alt_t = time.time() - ob.HANDLAUF_SPERRE_S - 60
            os.utime(pfad, (alt_t, alt_t))
            check(ob._handlauf_nehmen() is True and ob._handlauf_pid() == os.getpid(), "alte Sperre (Absturz, > 15 min) → neu genommen, eigene PID")
            ob._handlauf_setzen(False)
            check(ob._handlauf_nehmen() is True and not ob._handlauf_nehmen(), "freie Sperre → genommen, danach belegt")
            ob._handlauf_setzen(False)
            # alte Sperre: per Umbenennen übernommen, keine .alt-Reste; war die umbenannte frisch → zurück, nichts genommen (Prüfer TX2)
            with open(pfad, "w") as f_:
                f_.write("1")
            os.utime(pfad, (alt_t, alt_t))
            check(ob._handlauf_nehmen() is True and not [x for x in os.listdir(d) if ".alt" in x], "alte Sperre übernommen, kein .alt-Rest")
            ob._handlauf_setzen(False)
            echt_mtime = ob.os.path.getmtime
            zaehler = {"n": 0}

            def mtime_trick(pf):          # 1. Blick: alt — nach dem Umbenennen: frisch (ein anderer Lauf war schneller)
                zaehler["n"] += 1
                return alt_t if zaehler["n"] == 1 else time.time()
            with open(pfad, "w") as f_:
                f_.write("2")
            ob.os.path.getmtime = mtime_trick
            try:
                r_ = ob._handlauf_nehmen()
            finally:
                ob.os.path.getmtime = echt_mtime
            check(r_ is False and os.path.exists(pfad) and open(pfad).read() == "2" and not [x for x in os.listdir(d) if ".alt" in x],
                  "umbenannte Sperre war frisch → zurückgelegt, dieser Lauf bekommt nichts")
            ob._handlauf_setzen(False)
            echt_open = ob.os.open
            n_pe = {"n": 0}

            def open_pe(*a, **k):         # Windows: Datei wird gerade gelöscht → PermissionError, beim 2. Mal frei
                n_pe["n"] += 1
                if n_pe["n"] == 1:
                    raise PermissionError("delete pending")
                return echt_open(*a, **k)
            ob.os.open = open_pe
            try:
                r_ = ob._handlauf_nehmen()
            finally:
                ob.os.open = echt_open
            check(r_ is True and n_pe["n"] == 2, "PermissionError (Löschen läuft) → kurz warten, erneut, dann genommen — nie ohne Datei „genommen“")
            ob._handlauf_setzen(False)
        finally:
            ob._AUGEN_HIER = alt_hier
    for fn in (ob.modus_tsxlesen_cdp, ob.modus_tsxinventar_cdp, ob.modus_k3):
        q_ = inspect.getsource(fn)
        check("_handlauf_nehmen()" in q_ and "_handlauf_setzen(True)" not in q_, f"{fn.__name__}: Sperre nur noch atomar (_handlauf_nehmen)")

    # (2) puls_fenster_marke
    def f(h, t, k="Chrome_WidgetWin_1", s=True):
        return {"hwnd": h, "text": t, "klasse": k, "sichtbar": s}
    M = "PULS-1a2b3c4d"
    zwei = [f(1, "Topstep | Sign in - Google Chrome"), f(2, "Topstep | Sign in - Google Chrome")]
    check(ob.puls_fenster_waehlen(zwei, "Topstep | Sign in") is None, "Ausgangslage: zwei gleich betitelte Fenster → alter Wähler findet keins")
    check(ob.puls_fenster_marke([zwei[0], f(2, M + " Topstep | Sign in - Google Chrome")], M) == 2, "Marke → genau das Fenster mit der Marke")
    check(ob.puls_fenster_marke(zwei, M) is None, "Marke (noch) nicht im Titel → None")
    check(ob.puls_fenster_marke([f(1, M + " a"), f(2, M + " b")], M) is None, "Marke in zwei Fenstern → None (nichts raten)")
    check(ob.puls_fenster_marke([f(1, M + " a", k="Chrome_RenderWidgetHostHWND")], M) is None, "nur Browser-Fenster (Chrome_WidgetWin_1)")
    check(ob.puls_fenster_marke([f(1, M + " a", s=False)], M) is None, "unsichtbares Fenster zählt nicht")
    check(ob.puls_fenster_marke([f(1, "PULS x")], "PULS") is None, "zu kurze Marke → None")

    # (3) _win_per_marke mit Attrappen
    alt = (ob._puls_fenster_liste, ob._puls_chrome_browser_pid, ob._warte)
    try:
        ob._puls_chrome_browser_pid = lambda: 4711
        ob._warte = lambda *a, **k: None
        titel = {"t": "Topstep | Sign in"}
        js_log = []

        def lese_js(ausdruck, timeout=8):
            js_log.append(ausdruck)
            if ausdruck.startswith(ob.WIN_MARKE_SETZEN_JS):
                m = json.loads(ausdruck[len(ob.WIN_MARKE_SETZEN_JS) + 1:-1])
                titel["m"] = m
                titel["t"] = m + " " + titel["t"]
            elif ausdruck.startswith(ob.WIN_MARKE_WEG_JS):
                m = json.loads(ausdruck[len(ob.WIN_MARKE_WEG_JS) + 1:-1])
                if titel["t"].startswith(m):
                    titel["t"] = titel["t"][len(m) + 1:]
            return True
        ob._puls_fenster_liste = lambda pid: [f(11, "Topstep | Sign in - Google Chrome"), f(22, titel["t"] + " - Google Chrome")]
        s = object.__new__(ob._AugenSitzung)
        s.trail = []
        s.lese_js = lese_js
        h = s._win_per_marke()
        check(h == 22 and titel["t"] == "Topstep | Sign in", f"Fenster über Marke gefunden (22), Titel danach wieder wie vorher ({h}, {titel['t']!r})")
        check(any("über Titel-Marke eindeutig gefunden" in z for z in s.trail), "Spur nennt den Titel-Marke-Weg")
        n_js = len(js_log)
        check(s._win_per_marke() == 22 and len(js_log) == n_js, "zweiter Aufruf im selben Lauf: gemerktes Fenster, kein neues Titel-Flackern")
        check(titel["m"].startswith("PULS-") and len(titel["m"]) == 13, "Marke zufällig je Lauf (PULS-xxxxxxxx)")

        s2 = object.__new__(ob._AugenSitzung)
        s2.trail = []
        titel["t"] = "Topstep | Sign in"
        s2.lese_js = lese_js
        ob._puls_fenster_liste = lambda pid: [f(11, "Topstep | Sign in - Google Chrome"), f(22, "Topstep | Sign in - Google Chrome")]
        js_log.clear()
        check(s2._win_per_marke() is None and titel["t"] == "Topstep | Sign in" and any(x.startswith(ob.WIN_MARKE_WEG_JS) for x in js_log),
              "Marke taucht nicht auf → None, Titel trotzdem zurückgesetzt")
    finally:
        ob._puls_fenster_liste, ob._puls_chrome_browser_pid, ob._warte = alt
    qv = inspect.getsource(ob._AugenSitzung._win_vorn)
    check(qv.index("puls_fenster_waehlen(") < qv.index("self._win_per_marke()") < qv.index('"Puls-Chrome-Fenster nicht eindeutig gefunden"')
          and "if not hwnd:\n            hwnd = self._win_per_marke()" in qv,
          "_win_vorn: Titel-Marke nur als Rückfall, wenn der alte Wähler nichts findet")
    for js in (ob.WIN_MARKE_SETZEN_JS, ob.WIN_MARKE_WEG_JS):
        check("click" not in js and "dispatch" not in js and "document.title" in js, "Marke ändert nur document.title (kein Klick, keine Taste)")

    # (4) Anmelde-Tabs
    L = [{"id": "eigen", "type": "page", "url": "https://login.topstep.com/interaction/AAA"},
         {"id": "a", "type": "page", "url": "https://login.topstep.com/interaction/BBB"},
         {"id": "b", "type": "page", "url": "https://login.topstep.com/interaction/CCC"},
         {"id": "tsx", "type": "page", "url": "https://topstepx.com/trade"},
         {"id": "tv", "type": "page", "url": "https://www.tradingview.com/chart/x/"},
         {"id": "g", "type": "page", "url": "https://accounts.google.com/o/oauth2"},
         {"id": "p", "type": "page", "url": "http://localhost:5000/#accounts"},
         {"id": "fake", "type": "page", "url": "https://login.topstep.com.evil.example/x"},
         {"id": "sw", "type": "service_worker", "url": "https://login.topstep.com/sw.js"}]
    check(ob.tsx_login_tabs_ueberzaehlig(L, ("eigen",)) == ["a", "b"], "nur fremde login.topstep.com-Seiten, nie eigener Tab/TopstepX/TV/Google/Prophos")
    check(ob.tsx_login_tabs_ueberzaehlig([{"id": str(i), "type": "page", "url": "https://login.topstep.com/i"} for i in range(100)]).__len__()
          == ob.TSX_LOGIN_TABS_MAX, "höchstens TSX_LOGIN_TABS_MAX je Aufruf")
    alt2 = (ob._handlauf_pid, ob._cdp_http, ob._cdp_tab_schliessen)
    try:
        zu = []
        ob._cdp_http = lambda pfad, methode="GET", timeout=2.0: L if pfad == "/json/list" else None
        ob._cdp_tab_schliessen = lambda i: zu.append(i) or True
        ob._handlauf_pid = lambda: os.getpid() + 1
        tr = []
        check(ob._tsx_login_tabs_zu(tr, ("eigen",)) == 0 and not zu, "Sperre gehört einem anderen Lauf → nichts geschlossen")
        ob._handlauf_pid = lambda: os.getpid()
        check(ob._tsx_login_tabs_zu(tr, ("eigen",)) == 2 and zu == ["a", "b"] and any("2 von 2 alten Topstep-Anmelde-Tabs" in z for z in tr),
              "eigene Sperre → die zwei fremden Anmelde-Tabs zu, Spur mit Anzahl")
    finally:
        ob._handlauf_pid, ob._cdp_http, ob._cdp_tab_schliessen = alt2
    qs, qg = inspect.getsource(ob._tsx_tab_sicher), inspect.getsource(ob._tsx_google_login)
    check(qs.index('"/json/new?" + TSX_URL') < qs.index('_tsx_login_tabs_zu(trail, ausser=tuple(eigene[-2:]) + (str(neu.get("id")),))'),
          "ERST neuer TopstepX-Tab, DANN alte Anmelde-Tabs zu (nie den letzten Tab, Chrome bliebe offen); neuer + zwei jüngste Bot-Tabs bleiben (Prüfer)")
    check(qg.index('_tsx_login_tabs_zu(trail, ausser=(getattr(s, "target_id", None),))') < qg.index("vorher = [") < qg.index("s.klick(kn[\"rect\"]"),
          "vor dem Google-Klick aufräumen (eigener Tab bleibt), Tab-Liste für das Google-Fenster danach")

    # (5) neue Anmeldeseite (live pc-pmqd8g 24.11.2026, TSX_K0_BLICK_JS.login)
    LG = {"seite": False, "knoepfe": 0, "knopf": None, "pw_n": 0, "fehler_text": None, "zwei_faktor": False,
          "google": [{"tag": "button", "text": "Continue with Google", "aria": "", "title": "", "role": "", "testid": "",
                      "rect": [769, 601, 382, 44], "aus": False, "popup": "", "offen": ""}], "google_n": 1, "signin": True}
    kn, gr = ob.tsx_google_knopf(LG)
    check(ob.tsx_login_art(LG) == "google" and kn and kn["text"] == "Continue with Google" and not gr,
          "neue Topstep-Anmeldeseite (E-Mail zuerst) → art 'google', genau der Knopf „Continue with Google“")
    pr = ob.tsx_google_pruef(kn)
    import re
    check(pr["text"] == "google" and not re.search(ob.TSX_GOOGLE_TABU, "Continue with Google", re.I)
          and re.search(ob.TSX_GOOGLE_TABU, "Sign Up", re.I), "Ziel-Beweis „google“, „Sign Up“ bleibt tabu")

    print()
    print("ALLES OK" if not FEHLER else f"{len(FEHLER)} FEHLER")
    sys.exit(1 if FEHLER else 0)
