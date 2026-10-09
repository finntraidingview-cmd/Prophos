#!/usr/bin/env python3
"""Selbsttest Login-Ort bei Abriss am Tradovate-Tab (mt5-copier/order_bot.py, 09.10.2026, Muster „cdp: ConnectionAbortedError
[WinError 10053]", Lauf 08.10. 13:26 UTC: Connect geklickt, 7,6 s später riss der ganze Lauf ab — als die Tradovate-Anmeldung als
eigener Tab auftauchte). Alles mit Attrappen, kein Chrome, kein Netz, keine Order.

Aufruf:  python3 tools/selftest_login_tab_abriss.py
Prueft _cdp_login_ort: (1) reisst die Verbindung zum frisch aufgetauchten Tradovate-Tab beim Lesen ab, laeuft der Login weiter und
findet die Anmeldeseite beim naechsten Blick; (2) RuntimeError („Execution context destroyed") genauso; (3) ein Abriss am
TradingView-Tab selbst wird NICHT verschluckt (der Neustart-Wrapper haengt dann neu an)."""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "mt5-copier"))
import order_bot as ob  # noqa: E402

OK = True


def check(bed, text):
    global OK
    print(("✓ " if bed else "✗ ") + text)
    OK = OK and bool(bed)


class TabWs:
    """Attrappe einer CDP-Verbindung zum Tradovate-Tab: wirft beim ersten Lesen 'fehler' (oder nie), danach Login-Seite."""

    def __init__(self, fehler=None):
        self.fehler, self.zu_n = fehler, 0

    def rufe(self, methode, params=None, timeout=10.0):
        if self.fehler is not None:
            raise self.fehler
        ausdruck = str((params or {}).get("expression") or "")
        if "performance.timeOrigin" in ausdruck:
            return {"result": {"value": 9e15}}
        return {"result": {"value": {"login": True}}}

    def zu(self):
        self.zu_n += 1


class TvWs:
    def __init__(self, fehler=None):
        self.fehler = fehler

    def rufe(self, methode, params=None, timeout=10.0):
        if self.fehler is not None:
            raise self.fehler
        return {"result": {"value": {}}}


class TvSitzung:
    def __init__(self, ws):
        self.ws = ws

    def werbung_weg(self, zwang=False):
        return 0

    def lese_js(self, ausdruck, timeout=8):
        return None


def lauf(tab_wss, tv_ws=None):
    """_cdp_login_ort mit Attrappen; tab_wss = Folge der Verbindungen, die _CdpVerbindung nacheinander liefert."""
    folge = list(tab_wss)
    alt = (ob._warte, ob._cdp_http, ob._CdpVerbindung, ob._cdp_verbunden_lesen)
    ob._warte = lambda *a, **k: None
    ob._cdp_http = lambda pfad, *a, **k: [{"type": "page", "id": "T1", "url": "https://trader.tradovate.com/welcome",
                                            "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/T1"}]
    ob._CdpVerbindung = lambda url, timeout=8.0: folge.pop(0)
    ob._cdp_verbunden_lesen = lambda s, opts, trail: ""
    trail = []
    try:
        ort, text = ob._cdp_login_ort(TvSitzung(tv_ws or TvWs()), {"ids": set(), "ms": 1.0}, "U", {}, trail, warten_s=5.0)
        return ort, text, trail, None
    except Exception as e:
        return None, "", trail, e
    finally:
        ob._warte, ob._cdp_http, ob._CdpVerbindung, ob._cdp_verbunden_lesen = alt


# (1) 10053 am Tradovate-Tab beim ersten Lesen → weiter, beim zweiten Blick Anmeldeseite
w1, w2 = TabWs(ConnectionAbortedError(10053, "abgebrochen")), TabWs()
ort, text, trail, err = lauf([w1, w2])
check(err is None, "Abriss am Tradovate-Tab reißt den Login nicht mehr mit (keine Ausnahme)")
check(getattr(ort, "name", "") == "Tradovate-Tab", "beim nächsten Blick: Anmeldeseite im Tradovate-Tab gefunden")
check(any("riss beim Lesen ab (ConnectionAbortedError)" in t for t in trail), "Spur nennt den Abriss am Tradovate-Tab mit Typ")
check(w1.zu_n == 1, "abgerissene Tab-Verbindung wird geschlossen")

# (2) RuntimeError (Kontext beim Weiterleiten zerstört) genauso
ort, text, trail, err = lauf([TabWs(RuntimeError("CDP Runtime.evaluate: Execution context was destroyed")), TabWs()])
check(err is None and getattr(ort, "name", "") == "Tradovate-Tab", "RuntimeError beim Weiterleiten → nächster Blick findet die Seite")

# (3) Abriss am TradingView-Tab selbst bleibt eine Ausnahme (Wrapper: neu anhängen, nichts gesendet)
alt_vl = ob._cdp_verbunden_lesen
ort, text, trail, err = None, "", [], None
try:
    ob._cdp_verbunden_lesen = lambda s, opts, trail: (_ for _ in ()).throw(ConnectionAbortedError(10053, "tv"))
    alt = (ob._warte, ob._cdp_http)
    ob._warte = lambda *a, **k: None
    ob._cdp_http = lambda pfad, *a, **k: []
    try:
        ob._cdp_login_ort(TvSitzung(TvWs()), {"ids": set(), "ms": 1.0}, "U", {}, trail, warten_s=5.0)
    except ConnectionAbortedError as e:
        err = e
    finally:
        ob._warte, ob._cdp_http = alt
finally:
    ob._cdp_verbunden_lesen = alt_vl
check(isinstance(err, ConnectionAbortedError), "Abriss am TradingView-Tab wird nicht verschluckt (geht an den Neustart-Wrapper)")

print("\nALLES GRÜN" if OK else "\nFEHLER")
sys.exit(0 if OK else 1)
