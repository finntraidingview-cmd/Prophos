#!/usr/bin/env python3
"""Prophos TV-Reader — lokaler Empfaenger.

Nimmt die Positionsdaten vom Tampermonkey-Reader (tv-reader.user.js) entgegen,
haelt den aktuellen Stand im Speicher, schreibt ihn atomar nach positions.json
und gibt ihn als Live-Zeile im Terminal aus.

Das ist der Andockpunkt fuer den echten Hedge-Copier: der liest entweder
GET http://127.0.0.1:8790/positions oder direkt die Datei positions.json.

Ein/Aus-Schalter (28.08.2026, Orbit-View in Prophos — hiess damals "Echo +"): POST /schalter
{"an": false} pausiert den Reader — der Stand friert ein (stale != flat:
ein pausierter Reader meldet NIE "keine Positionen", sonst wuerde ein
spaeterer Copier-Konsument die Hedges schliessen). Persistiert als
reader_aus.flag, ueberlebt also einen Neustart des Servers. Jeder Konsument
von positions.json MUSS das Feld "an" pruefen: an=false -> nicht syncen.

Nur Python-Standardbibliothek — kein pip, keine Cloud, keine Schluessel.
Laeuft auf Mac/Windows/Linux gleich.
"""
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8790
HIER = os.path.dirname(os.path.abspath(__file__))
DATEI = os.path.join(HIER, "positions.json")
AUS_FLAG = os.path.join(HIER, "reader_aus.flag")   # Datei vorhanden = pausiert

# Letzter bekannter Stand (wird von POST gesetzt, von GET/Datei gelesen)
_stand = {"ts": 0, "positionen": []}
_an = not os.path.exists(AUS_FLAG)


def _schreibe_datei(stand):
    """Atomar schreiben, damit ein mitlesender Copier nie eine halbe Datei sieht."""
    tmp = DATEI + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(stand, f, ensure_ascii=False)
    os.replace(tmp, DATEI)


def _mit_an(stand):
    """Stand + Schalter-Zustand — 'an' gehoert in JEDE Ausgabe (Datei und GET),
    damit kein Konsument den Schalter uebersehen kann."""
    out = dict(stand)
    out["an"] = _an
    return out


def _schalte(an_neu):
    """Schalter setzen + persistieren + positions.json sofort aktualisieren
    (damit ein Datei-Konsument den neuen Zustand ohne naechsten Tick sieht)."""
    global _an
    _an = bool(an_neu)
    try:
        if _an:
            if os.path.exists(AUS_FLAG):
                os.remove(AUS_FLAG)
        else:
            with open(AUS_FLAG, "w", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        print(f"\n[WARN] Schalter-Flag nicht schreibbar: {e}")
    try:
        _schreibe_datei(_mit_an(_stand))
    except Exception as e:
        print(f"\n[WARN] positions.json nicht schreibbar: {e}")


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        # Chrome Private-Network-Access: erlaubt einer HTTPS-Seite (Prophos auf
        # pages.dev) den Zugriff auf 127.0.0.1 — noetig fuer die Orbit-View.
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def _json(self, code, obj):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        global _stand
        laenge = int(self.headers.get("Content-Length", 0) or 0)
        roh = self.rfile.read(laenge) if laenge else b""
        try:
            daten = json.loads(roh)
        except Exception:
            self.send_response(400)
            self._cors()
            self.end_headers()
            return

        # Schalter (Orbit-View): POST /schalter {"an": true/false}
        if self.path.rstrip("/") == "/schalter":
            if "an" not in daten:
                self._json(400, {"ok": False, "msg": "Feld 'an' fehlt"})
                return
            _schalte(daten["an"])
            zeit = time.strftime("%H:%M:%S")
            print(f"\n[{zeit}] Schalter: Reader {'AN' if _an else 'PAUSIERT'}")
            self._json(200, {"ok": True, "an": _an})
            return

        # Positionsdaten vom Userscript. Pausiert: Antwort traegt an=false
        # (Badge zeigt es), der Stand friert ein — stale != flat.
        if not _an:
            self._json(200, {"ok": True, "an": False})
            return

        _stand = daten
        try:
            _schreibe_datei(_mit_an(_stand))
        except Exception as e:
            # Datei-Schreibfehler soll den Empfang nicht killen
            print(f"\n[WARN] positions.json nicht schreibbar: {e}")

        pos = daten.get("positionen", [])
        zeit = time.strftime("%H:%M:%S")
        if pos:
            zeilen = " · ".join(
                f"{p.get('symbol')} {p.get('seite')} {p.get('menge')}"
                f"@{p.get('einstieg')} SL {p.get('sl') or '-'} TP {p.get('tp') or '-'}"
                f" P&L {p.get('pnl')}"
                for p in pos
            )
        else:
            zeilen = "flat"
        # \r haelt es als eine aktualisierende Live-Zeile
        print(f"\r[{zeit}] {len(pos)} Pos · {zeilen}".ljust(160)[:160], end="", flush=True)

        self._json(200, {"ok": True, "an": True})

    def do_GET(self):
        # Aktuellen Stand abfragbar machen (fuer den Copier, die Orbit-View
        # oder zum Reinschauen im Browser) — inkl. Schalter-Zustand.
        self._json(200, _mit_an(_stand))

    def log_message(self, *a):
        pass  # kein Request-Log-Spam ueber der Live-Zeile


if __name__ == "__main__":
    print(f"Prophos TV-Reader-Empfaenger laeuft auf http://127.0.0.1:{PORT}")
    print(f"Schreibt den Stand nach {DATEI}")
    print(f"Reader ist {'AN' if _an else 'PAUSIERT (reader_aus.flag liegt)'}")
    print("Warte auf Daten vom Tampermonkey-Reader … (Strg+C zum Beenden)\n")
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nbeendet.")
