#!/usr/bin/env python3
"""Selbsttest PN1 (23.11.2026, Master nach Prüfer-Bericht NG1): der Puls-Chrome-Neustart nach einem Puls-Fehler schloss per Browser.close
auch den Prophos-Haupt-Tab, der den Start geclaimt hatte → 2. Versuch ohne Empfänger, Plan „Geclaimt … danach kein Ergebnis" (unklar).
Geprüft — alles mit Attrappen, kein Chrome, kein Netz, keine Order:
  * puls_neustart_lage: Prophos-Seiten und die Tabs des Wegs aus /json/list, unlesbare Liste = unbekannt
  * _puls_chrome_neustart: Prophos-Tab lebt → nur sanft (neuer Tab, alte Tabs des Wegs zu), nie Browser.close; ein Tab geht nicht zu /
    kein neuer Tab → kein Neustart; Liste unlesbar → kein Neustart; ohne Prophos-Tab → harter Weg wie bisher
  * _puls_mit_neustart(ablage=…): nur Antworten ohne Sendung werden abgelegt, nie ohne Neustart-Entscheid
  * _puls_neustart_ablegen: nur scharf + plan_id + nichts gesendet; das Paket nimmt app.py puls_ergebnis_saeubern an
  * prophos.html: pulsErgebnisseUebernehmen legt die Neustart-Antwort als puls_spur an den Plan
  * PN1c: modus_augen bei Regel 'uia' — Prophos-Tab lebt → nur TV-/TSX-Tabs zu; Liste unlesbar → nichts; ohne Prophos-Tab Browser.close
Aufruf:  python3 tools/selftest_pn1_neustart_prophos_tab.py   Alle Kennungen erfunden."""
import ast
import json
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import order_bot as ob  # noqa: E402

OK = True


def check(bed, text):
    global OK
    print(("✓ " if bed else "✗ ") + text)
    OK = OK and bool(bed)


TV = "https://www.tradingview.com/chart/"
TSX = "https://topstepx.com/trade"


def seite(i, url, typ="page"):
    return {"id": f"T{i}", "type": typ, "url": url, "title": url[:20], "webSocketDebuggerUrl": f"ws://x/{i}"}


LISTE = [seite(1, "http://localhost:5000/"), seite(2, TV), seite(3, "https://www.tradingview.com/symbols/X/"),
         seite(4, TSX), seite(5, "https://topstepx.com/login"), seite(6, "chrome-extension://abc/bg.html", "background_page"),
         seite(7, "https://example.com/")]


class Chrome:
    """Attrappe der DevTools-HTTP-Schnittstelle: /json/list, /json/new, /json/close; zählt jeden Aufruf."""

    def __init__(self, liste, neu_ok=True, zu_nein=()):
        self.liste, self.neu_ok, self.zu_nein = [dict(x) for x in liste] if liste is not None else None, neu_ok, set(zu_nein)
        self.neu, self.zu, self.beenden, self.gestartet, self.json, self.tsx_ids = [], [], 0, 0, [], []

    def http(self, pfad, methode="GET", timeout=2.0):
        if pfad == "/json/list":
            return None if self.liste is None else [dict(x) for x in self.liste]
        raise AssertionError("unerwarteter Aufruf " + pfad + " (PN1b: neuer Tab nur über Target.createTarget newWindow)")

    def neues_fenster(self, url, timeout=5.0):
        self.neu.append(url)
        if not self.neu_ok:
            return None
        t = seite(90 + len(self.neu), url)
        self.liste.append(t)
        return t["id"]

    def schliessen(self, tid):
        if tid in self.zu_nein:
            return False
        self.zu.append(tid)
        self.liste = [x for x in self.liste if x.get("id") != tid]
        return True

    def hart_beenden(self, trail, *a, **k):
        self.beenden += 1
        return False, "Attrappe: hart beendet (nicht wirklich)"


def neustart_lauf(chrome, url):
    alt = {n: getattr(ob, n) for n in ("_cdp_http", "_cdp_tab_schliessen", "_puls_chrome_beenden", "_puls_chrome_sicher",
                                       "_augen_json_schreiben", "_augen_json_lesen", "_warte", "_cdp_tab_eigenes_fenster")}
    ob._cdp_http, ob._cdp_tab_schliessen, ob._puls_chrome_beenden = chrome.http, chrome.schliessen, chrome.hart_beenden
    ob._cdp_tab_eigenes_fenster = chrome.neues_fenster
    ob._augen_json_lesen = lambda name: {"ids": list(chrome.tsx_ids)} if name == "tsx_tabs.json" else None
    ob._puls_chrome_sicher = lambda *a, **k: (_ for _ in ()).throw(AssertionError("Chrome-Start im sanften Weg"))
    ob._augen_json_schreiben = lambda name, d: chrome.json.append((name, d))
    ob._warte = lambda *a, **k: None
    trail = []
    try:
        r = ob._puls_chrome_neustart(trail, url)
    finally:
        for n, f in alt.items():
            setattr(ob, n, f)
    return r, trail


def main():
    # ── puls_neustart_lage ─────────────────────────────────────────────────────────────────────────────────────────────────────
    L = ob.puls_neustart_lage
    p, a = L(LISTE, TV)
    check([x["id"] for x in p] == ["T1"] and sorted(x["id"] for x in a) == ["T2", "T3"], f"TV-Weg: Prophos T1, alte TradingView-Tabs T2/T3 ({p}, {a})")
    p, a = L(LISTE, TSX)
    check([x["id"] for x in p] == ["T1"] and sorted(x["id"] for x in a) == ["T4", "T5"], "TopstepX-Weg: alte TopstepX-Tabs T4/T5, TradingView bleibt")
    check(L(None, TV) == (None, None) and L({"x": 1}, TV) == (None, None), "Liste unlesbar → unbekannt (None, None)")
    check(L([seite(1, "http://127.0.0.1:5000/prophos.html#login"), seite(2, "https://prophos.pages.dev/prophos")], TV)[0].__len__() == 2
          and L([seite(1, "http://localhost:50001/")], TV)[0] == [] and L([seite(1, "http://localhost:5000/", "service_worker")], TV)[0] == [],
          "Prophos = localhost/127.0.0.1:5000 oder prophos.pages.dev, nur type page (kein :50001, kein Service-Worker)")

    # ── _puls_chrome_neustart ──────────────────────────────────────────────────────────────────────────────────────────────────
    c1 = Chrome(LISTE)
    r1, t1 = neustart_lauf(c1, TV)
    check(r1 is True and c1.beenden == 0 and c1.neu == [TV] and sorted(c1.zu) == ["T2", "T3"] and "T1" not in c1.zu
          and any("kein Browser.close" in x for x in t1), f"Prophos-Tab lebt → sanft: neuer TV-Tab, nur alte TV-Tabs zu, nie hart ({c1.zu}, {t1})")
    c2 = Chrome(LISTE)
    r2, t2 = neustart_lauf(c2, TSX)
    check(r2 is True and c2.beenden == 0 and sorted(c2.zu) == ["T4", "T5"] and c2.json and c2.json[-1][0] == "tsx_tabs.json"
          and c2.json[-1][1]["ids"] == [c2.liste[-1]["id"]], "TopstepX-Weg sanft: alte TopstepX-Tabs zu, neuer Tab als bot-eigen gemerkt")
    c3 = Chrome(LISTE, zu_nein={"T3"})
    r3, t3 = neustart_lauf(c3, TV)
    check(r3 is False and c3.beenden == 0 and any("gingen nicht zu" in x for x in t3), f"ein alter Tab geht nicht zu → kein Neustart, nie hart ({t3})")
    c2b = Chrome(LISTE, zu_nein={"T5"})
    c2b.tsx_ids = ["T5", "T4", "ALT"]
    r2b, t2b = neustart_lauf(c2b, TSX)
    check(r2b is False and c2b.json and c2b.json[-1][1]["ids"][:-1] == ["T5"] and c2b.json[-1][1]["ids"][-1].startswith("T9"),
          f"PN1b: TopstepX-Tab geht nicht zu → seine bot-eigene ID bleibt gemerkt, der neue kommt dazu ({c2b.json})")
    c4 = Chrome(LISTE, neu_ok=False)
    r4, t4 = neustart_lauf(c4, TV)
    check(r4 is False and c4.beenden == 0 and c4.zu == [], "kein neuer Tab → alte bleiben, kein Neustart")
    c5 = Chrome(None)
    r5, t5 = neustart_lauf(c5, TV)
    check(r5 is False and c5.beenden == 0 and c5.neu == [] and any("nicht lesbar" in x for x in t5), "Tab-Liste unlesbar → kein Neustart")
    c6 = Chrome([x for x in LISTE if x["id"] != "T1"])
    r6, t6 = neustart_lauf(c6, TV)
    check(r6 is False and c6.beenden == 1 and c6.neu == [] and c6.zu == [], "ohne Prophos-Tab im Puls-Chrome → harter Weg wie bisher (Attrappe)")

    # ── PN1c: Aufräumen bei Regel 'uia' (modus_augen) ─────────────────────────────────────────────────────────────────────────
    import contextlib
    import io
    import tempfile
    U = ob.puls_uia_aufraeumen_ziele
    pu, zu_u = U(LISTE)
    check([x["id"] for x in pu] == ["T1"] and sorted(x["id"] for x in zu_u) == ["T2", "T3", "T4", "T5"] and U(None) == (None, None),
          "PN1c rein: Prophos T1, zu schließen alle TradingView-/TopstepX-Tabs, unlesbare Liste = unbekannt")

    class WsAttrappe:
        rufe_log = []

        def __init__(self, *a, **k):
            pass

        def rufe(self, methode, *a, **k):
            WsAttrappe.rufe_log.append(methode)
            return {}

        def zu(self):
            pass

    def uia_lauf(liste):
        WsAttrappe.rufe_log = []
        zu = []
        namen = ("_augen_pc_id", "_augen_regel_holen", "_cdp_http", "_cdp_tab_schliessen", "_handlauf_aktiv", "_AUGEN_HIER", "_CdpVerbindung")
        alt = {n: getattr(ob, n) for n in namen}
        stand_alt = dict(ob._AUGEN_REGEL_STAND)
        try:
            ob._AUGEN_HIER = tempfile.mkdtemp()
            ob._augen_pc_id = lambda: "pc-xxxxxx"
            ob._augen_regel_holen = lambda pc: "uia"
            ob._AUGEN_REGEL_STAND.update(explizit=True, tsx="uia")
            ob._handlauf_aktiv = lambda: False
            ob._cdp_http = lambda pfad, *a, **k: ({"webSocketDebuggerUrl": "ws://x"} if pfad == "/json/version"
                                                  else ([dict(x) for x in liste] if (pfad == "/json/list" and liste is not None) else None))
            ob._cdp_tab_schliessen = lambda tid: zu.append(tid) or True
            ob._CdpVerbindung = WsAttrappe
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                ob.modus_augen({})
        finally:
            for n, v in alt.items():
                setattr(ob, n, v)
            ob._AUGEN_REGEL_STAND.clear()
            ob._AUGEN_REGEL_STAND.update(stand_alt)
        return json.loads(out.getvalue().strip().splitlines()[-1]), zu, list(WsAttrappe.rufe_log)
    j1, z1, w1 = uia_lauf(LISTE)
    check(j1.get("ok") and sorted(z1) == ["T2", "T3", "T4", "T5"] and "T1" not in z1 and "Browser.close" not in w1 and "Prophos-Tab bleibt" in j1.get("msg", ""),
          f"PN1c: Prophos-Tab lebt → nur TradingView-/TopstepX-Tabs zu, kein Browser.close ({j1.get('msg')}, {z1}, {w1})")
    j2, z2, w2 = uia_lauf(None)
    check(j2.get("ok") and z2 == [] and "Browser.close" not in w2 and "nicht lesbar" in j2.get("msg", ""),
          f"PN1c: Tab-Liste unlesbar → nichts geschlossen ({j2.get('msg')})")
    j3, z3, w3 = uia_lauf([x for x in LISTE if x["id"] != "T1"])
    check(j3.get("ok") and z3 == [] and w3 == ["Browser.close"] and "geschlossen" in j3.get("msg", ""),
          f"PN1c: ohne Prophos-Tab → wie bisher Browser.close ({j3.get('msg')}, {w3})")

    # ── Ablage im Wrapper ──────────────────────────────────────────────────────────────────────────────────────────────────────
    def erg(**k):
        d = {"ok": False, "code": "", "msg": "", "schritt": "", "trail": "x", "gesendet": False, "retry_ok": True}
        d.update(k)
        return d

    def wrap(r1_, r2_, neustart_ok=True, lesung=None):
        abl, aus = [], []
        res = ob._puls_mit_neustart("tvv2", lambda: (json.dumps(r1_), dict(r1_)),
                                    lambda frist: ((json.dumps(r2_), dict(r2_)) if r2_ else ("", {})),
                                    (lambda spur: lesung) if lesung is not None else None, "https://x/",
                                    neustart=lambda spur, url: neustart_ok, jetzt=lambda: 30.0, t0=0.0, ausgeben=aus.append,
                                    diagnose=lambda **k: None, ablage=abl.append)
        return res, abl, aus
    _, ab, au = wrap(erg(code="login", msg="Nichts platziert · Login"), erg(code="login", msg="Nichts platziert · Login 2"))
    check(len(ab) == 1 and ab[0]["msg"] == "Nichts platziert · Login 2" and au[-1] is not None, "2. Versuch ohne Sendung → genau einmal abgelegt")
    _, ab, _ = wrap(erg(code="login"), erg(ok=True, gesendet=True, bestaetigt=True))
    check(ab == [], "2. Versuch hat gesendet → nichts abgelegt (das meldet der Lauf selbst)")
    _, ab, _ = wrap(erg(ok=True), None)
    check(ab == [], "kein Neustart (1. Versuch ok) → nichts abgelegt")
    _, ab, _ = wrap(erg(code="konto_nicht_erreicht", schritt="konto"), None)
    check(ab == [], "Neustart-Entscheid nein (Konto-Fehler) → nichts abgelegt")
    _, ab, _ = wrap(erg(code="login", msg="erster"), None, neustart_ok=False)
    check(len(ab) == 1 and ab[0]["msg"] == "erster", "Neustart scheitert (erster raus) → die Antwort des 1. Versuchs wird abgelegt")
    leer = {"ok": True, "positionen_sichtbar": True, "pos_root": 0, "orders_gelesen": True, "orders_root": 0, "today_pnl": 0.0, "balance": 1.0}
    _, ab, _ = wrap(erg(code="unklar", schritt="unklar", gesendet=True, retry_ok=False, today_pnl_start=0.0, balance_start=1.0), erg(code="login"), lesung=leer)
    check(ab == [], "1. Versuch hatte geklickt (Lesungs-Weg) → nie abgelegt, auch wenn der 2. nichts sendet")

    # ── _puls_neustart_ablegen + Annahme in app.py ────────────────────────────────────────────────────────────────────────────
    gesendet = []
    alt = ob._puls_ergebnis_senden
    ob._puls_ergebnis_senden = lambda art, stufe, cmd, res, trail: gesendet.append((art, stufe, cmd, res, trail))
    try:
        cmd = {"scharf": True, "plan_id": "11111111-2222-3333-4444-555555555555", "ext_id": "FTMO100001", "symbol": "MNQ", "richtung": "buy"}
        ob._puls_neustart_ablegen(cmd, erg(code="login", msg="Nichts platziert · X", trail="a > b"))
        ob._puls_neustart_ablegen(dict(cmd, scharf=False), erg(code="login"))
        ob._puls_neustart_ablegen(dict(cmd, probe=True), erg(code="login"))
        ob._puls_neustart_ablegen(dict(cmd, plan_id=""), erg(code="login"))
        ob._puls_neustart_ablegen(cmd, erg(code="unklar", gesendet=True))
        ob._puls_neustart_ablegen(cmd, "kein dict")
    finally:
        ob._puls_ergebnis_senden = alt
    check(len(gesendet) == 1 and gesendet[0][:2] == ("order", "ende") and gesendet[0][3]["quelle"] == "chrome_neustart",
          f"nur scharf + plan_id + nichts gesendet → abgelegt (stufe ende, quelle chrome_neustart) ({[g[:2] for g in gesendet]})")
    paket = ob.puls_ergebnis_paket("order", "ende", cmd, gesendet[0][3], gesendet[0][4])
    app_src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
    baum = ast.parse(app_src)
    teile = [n for n in baum.body if (isinstance(n, ast.Assign) and any(getattr(t, "id", "") in ("PULS_ERGEBNIS_MAX", "PULS_ERGEBNIS_FELDER", "_PLAN_ID_MUSTER") for t in n.targets))
             or (isinstance(n, ast.FunctionDef) and n.name == "puls_ergebnis_saeubern")]
    ns = {"re": re, "json": json}
    exec(compile(ast.Module(body=teile, type_ignores=[]), "app.py", "exec"), ns)
    zeile = ns["puls_ergebnis_saeubern"](paket, "pc-xxxxxx")
    check(isinstance(zeile, dict) and zeile["stufe"] == "ende" and zeile["ergebnis"].get("quelle") == "chrome_neustart"
          and zeile["ergebnis"].get("gesendet") is False and "trail_ende" in zeile["ergebnis"],
          "app.py puls_ergebnis_saeubern nimmt das Paket an (ohne Änderung an app.py/DB)")

    # ── Verdrahtung ───────────────────────────────────────────────────────────────────────────────────────────────────────────
    bot = open(os.path.join(WURZEL, "mt5-copier", "order_bot.py"), encoding="utf-8").read()
    check(bot.count("ablage=lambda r: _puls_neustart_ablegen(") == 2, "beide Order-Wege (Orbit, Topstep) reichen die Ablage durch")
    neu = bot[bot.index("def _puls_chrome_neustart("):bot.index("def _puls_lauf_abfangen(")]
    check(neu.index("puls_neustart_lage(") < neu.index("_puls_chrome_beenden(trail)") and neu.index("return _puls_chrome_sanft_neu(") < neu.index("_puls_chrome_beenden(trail)"),
          "Prophos-Prüfung und sanfter Weg stehen VOR dem harten Beenden")
    sanft = bot[bot.index("def _puls_chrome_sanft_neu("):bot.index("def _puls_chrome_neustart(")]
    check("/json/new" not in sanft and "_cdp_tab_eigenes_fenster(url)" in sanft and "\"newWindow\": True" in bot[bot.index("def _cdp_tab_eigenes_fenster("):bot.index("def _puls_chrome_sanft_neu(")],
          "PN1b: neuer Tab nur in einem eigenen Fenster (Target.createTarget newWindow), nie /json/new")
    check("Browser.close\"" not in sanft and "rufe(\"Browser.close\"" not in sanft and "taskkill" not in sanft and "_puls_prozesse_beenden" not in sanft,
          "sanfter Weg: kein Browser.close, kein taskkill")
    html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
    pe = html[html.index("async function pulsErgebnisseUebernehmen()"):html.index("window._pulsErgebnisseUebernehmen = pulsErgebnisseUebernehmen")]
    check("e.quelle === 'chrome_neustart' && plan.status === 'planned' && !e.gesendet && !e.ok && !e.geklickt" in pe
          and "puls_spur: { at: zAt" in pe and pe.index("e.quelle === 'chrome_neustart'") < pe.index("if(plan.status !== 'planned' || !(e.gesendet || e.ok))")
          and "quelle: 'puls_ergebnisse' } }, 'planned')" in pe and "(claim0 && sp0At >= claim0 - 5000)" in pe,
          "Tab: Neustart-Antwort ohne Sendung → puls_spur am Plan, vor dem Abhaken, Plan bleibt Geplant")
    print("\n" + ("ALLES GRÜN" if OK else "FEHLER"))
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
