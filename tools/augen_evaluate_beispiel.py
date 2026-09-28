"""Beispiel: Prophos-Augen per Chrome DevTools Protocol auswerten (29.09.2026, Projekt „Script-Augen", Variante B).

Für T3/Puls als Vorlage — kein Teil des laufenden Systems. Ablauf:
  1. Puls-Chrome läuft mit eigenem Profil und Debug-Port, z. B.
       chrome.exe --user-data-dir=C:\\Prophos\\puls-chrome --remote-debugging-port=9223
     (Chrome ab 136 erlaubt den Port NICHT auf dem Standard-Profil. Der Port hört nur auf 127.0.0.1 —
      trotzdem kann jeder lokale Prozess ihn nutzen, also nur im eigenen Puls-Profil.)
  2. GET http://127.0.0.1:9223/json → Tab mit tradingview.com wählen → webSocketDebuggerUrl
  3. Runtime.evaluate mit dem INHALT von mt5-copier/augen.js + Aufruf, returnByValue=True.
     NIE per fetch/Script-Tag nachladen: tradingview.com blockt Abrufe von localhost (CSP, live gesehen 29.09.2026).
  4. Rückgabe = reines JSON (augenStand/augenInventar werfen nie und klicken nie). Geklickt wird mit der echten Maus;
     Bildschirm-Punkt aus rect + geo (siehe bildschirm_punkt).

Abhängigkeit: websocket-client (pip install websocket-client). Aufruf zum Ausprobieren:
  python augen_evaluate_beispiel.py 9223 stand
  python augen_evaluate_beispiel.py 9223 inventar > inventar.json
"""
import json
import os
import sys
import urllib.request

AUGEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mt5-copier", "augen.js")


def tv_tab(port):
    """webSocketDebuggerUrl des (ersten) TradingView-Tabs — oder None."""
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=3).read())
    for t in tabs:
        if t.get("type") == "page" and "tradingview.com" in (t.get("url") or ""):
            return t.get("webSocketDebuggerUrl")
    return None


def augen(port, was="stand", opts=None, timeout=5):
    """augenStand(opts) bzw. augenInventar(opts) im TradingView-Tab ausführen. -> dict (oder {'ok': False, 'fehler': …})"""
    import websocket                      # websocket-client
    ws_url = tv_tab(port)
    if not ws_url:
        return {"ok": False, "fehler": "kein TradingView-Tab im Puls-Chrome"}
    with open(AUGEN, encoding="utf-8") as f:
        quelle = f.read()
    aufruf = "augenInventar" if was == "inventar" else "augenStand"
    ausdruck = quelle + "\n" + aufruf + "(" + json.dumps(opts or {}) + ")"
    ws = websocket.create_connection(ws_url, timeout=timeout)
    try:
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                            "params": {"expression": ausdruck, "returnByValue": True, "awaitPromise": False}}))
        while True:
            antwort = json.loads(ws.recv())
            if antwort.get("id") == 1:
                break
    finally:
        ws.close()
    r = antwort.get("result") or {}
    if r.get("exceptionDetails"):
        return {"ok": False, "fehler": str(r["exceptionDetails"].get("text") or r["exceptionDetails"])[:300]}
    return (r.get("result") or {}).get("value") or {"ok": False, "fehler": "leere Antwort"}


def bildschirm_punkt(rect, geo):
    """Mitte eines rect [l, t, b, h] (CSS-Pixel im Viewport) als Bildschirm-Pixel. Näherung wie beim Reader-Bedienfeld:
    Chrome-Leisten = outerHeight − innerHeight (unten kein Rand angenommen), Faktor = devicePixelRatio (Windows-Skalierung
    und Seiten-Zoom). Puls prüft das Ergebnis gegen das gemessene Fenster-Rechteck, bevor er klickt."""
    dpr = float(geo.get("dpr") or 1)
    rand_x = max(0, (geo["outerWidth"] - geo["innerWidth"]) / 2)
    leiste = max(0, geo["outerHeight"] - geo["innerHeight"] - rand_x)
    x = geo["screenX"] + rand_x + rect[0] + rect[2] / 2
    y = geo["screenY"] + leiste + rect[1] + rect[3] / 2
    return int(round(x * dpr)), int(round(y * dpr))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9223
    was = sys.argv[2] if len(sys.argv) > 2 else "stand"
    print(json.dumps(augen(port, was), ensure_ascii=False, indent=1))
