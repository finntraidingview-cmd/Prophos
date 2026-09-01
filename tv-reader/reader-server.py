#!/usr/bin/env python3
"""Prophos TV-Reader — lokaler Empfaenger.

Nimmt die Positionsdaten vom Tampermonkey-Reader (tv-reader.user.js) entgegen,
haelt den aktuellen Stand im Speicher, schreibt ihn atomar nach positions.json
und gibt ihn als Live-Zeile im Terminal aus.

Das ist der Andockpunkt fuer den echten Hedge-Copier: der liest entweder
GET http://127.0.0.1:8790/positions oder direkt die Datei positions.json.

Bedienfeld (30.08.2026, Orbit-Puls Schritt 2): POST /bedienfeld nimmt die
Steuerelement-Geometrie des Userscripts entgegen (Konto-Umschalter, Symbol-
Suche, Order-Ticket, Kaufen/Verkaufen — je mit Rechteck in CSS-Pixeln), GET
/bedienfeld gibt sie an den Puls. Der Puls klickt daraus mit ECHTER Maus; das
Userscript klickt bewusst nie selbst (isTrusted-Doktrin, s. tv-reader.user.js).
Der Stand wird NICHT in eine Datei geschrieben: er ist Sekunden-frisch relevant
und waere auf Platte nur eine Quelle fuer alte Koordinaten.
POST /dump-an schaltet den Kandidaten-Dump des Userscripts fuer 60 s scharf —
die Ferndiagnose, wenn Puls ein Steuerelement nicht findet (gleiche Rolle wie
modus_inspect beim MT5-Puls).

Ein/Aus-Schalter (28.08.2026, Orbit-View in Prophos — hiess damals "Echo +"): POST /schalter
{"an": false} pausiert den Reader — der Stand friert ein (stale != flat:
ein pausierter Reader meldet NIE "keine Positionen", sonst wuerde ein
spaeterer Copier-Konsument die Hedges schliessen). Persistiert als
reader_aus.flag, ueberlebt also einen Neustart des Servers. Jeder Konsument
von positions.json MUSS das Feld "an" pruefen: an=false -> nicht syncen.

Blind-Riegel (01.09.2026, Finns Tabwechsel-Fund): meldet das Userscript
{"blind": true}, wird der Stand NICHT uebernommen — er friert ein, wie bei
Pause. Grund: ein verdeckter Chrome-Tab liefert leere Tabellenzellen, und
daraus wurde bis 0.3.7 ein frisches "0 Positionen" — der einzige Fall, in dem
die Frische-Doktrin der ganzen Kette versagt, weil die Daten ja frisch SIND.
Der Copier schloss den Hedge und riss ihn im naechsten Tick wieder auf.
Dazu ein Struktur-Riegel: eine Nachricht ohne Feld 'positionen' (Liste) wird
abgelehnt statt als "flat" gelesen.

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

# Bedienfeld: letzter Stand der Steuerelement-Geometrie + Empfangszeit.
# empfangen_s ist die SERVER-Zeit — das Userscript schickt seine eigene
# Browser-Zeit mit (ts), und die beiden Uhren muessen sich nicht einig sein.
# Puls braucht "juenger als mein letzter Klick", also zaehlt hier die Uhr,
# die auch der Puls liest.
_bedienfeld = None
_bedienfeld_s = 0.0
_dump_bis = 0.0   # bis zu dieser Server-Zeit fordert der Server einen Dump an

# Blind-Zustand (01.09.2026): das Userscript ab 0.4.0 sagt selbst, wenn sein
# Lesevorgang nichts beweist (Tabelle nicht auffindbar, Zellen leer). Solche
# Staende werden NICHT uebernommen — _stand friert ein, und die Frische-
# Doktrin des Verbinders haelt daraufhin den Hedge. Der Grund wird trotzdem
# gemerkt, damit Terminal und Ferndiagnose ihn zeigen koennen.
_blind_grund = ""
_blind_seit = 0.0
_letzte_zahl = None   # letzte gemeldete Positionszahl (Beweisspur)


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
    # blind gehoert in JEDE Ausgabe, aus demselben Grund wie 'an': ein
    # Konsument darf nicht uebersehen koennen, dass dieser Stand steht.
    out["blind"] = bool(_blind_grund)
    out["blind_grund"] = _blind_grund
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
        global _stand, _bedienfeld, _bedienfeld_s, _dump_bis, _blind_grund, _blind_seit, _letzte_zahl
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

        # Bedienfeld-Geometrie vom Userscript (30.08.2026, Orbit-Puls
        # Schritt 2). BEWUSST VOR dem Pause-Gate: der Schalter friert die
        # POSITIONEN ein (stale != flat), er blendet nicht die Augen ab —
        # Geometrie ist harmlos und ohne sie kaeme der Puls nie zu einer
        # ehrlichen Fehlermeldung. Ob ueberhaupt geordert werden darf,
        # entscheidet der Puls selbst am Feld 'an' von GET /positions.
        if self.path.rstrip("/") == "/bedienfeld":
            _bedienfeld = daten
            _bedienfeld_s = time.time()
            # dump-Anforderung zurueckgeben: das Userscript haengt beim
            # NAECHSTEN Tick den Kandidaten-Dump an (nie im Dauerbetrieb —
            # der Dump laeuft durchs ganze DOM).
            self._json(200, {"ok": True, "dump": time.time() < _dump_bis})
            return

        # Kandidaten-Dump scharfschalten (Ferndiagnose, 60 s): der Puls ruft
        # das selbst auf, wenn er ein Steuerelement nicht eindeutig findet —
        # der naechste Fehlversuch bringt dann die Beweise gleich mit.
        if self.path.rstrip("/") == "/dump-an":
            _dump_bis = time.time() + 60.0
            print("\n[info] Kandidaten-Dump fuer 60 s scharf")
            self._json(200, {"ok": True, "bis_s": 60})
            return

        # Ab hier gilt: NUR /positions ist ein Positions-Stand (30.08.2026,
        # Fund an Finns PC). Vorher nahm dieser Handler JEDEN unbekannten Pfad
        # als Positionsdaten an — ein Userscript 0.3, das an einen alten Server
        # ohne /bedienfeld sendet, ueberschrieb damit alle 500 ms den echten
        # Stand mit einem Objekt ohne 'positionen'. Ergebnis: positions.json
        # meldet "flat", der Verbinder friert nicht ein (die Daten sind ja
        # frisch!), und der Copier schliesst die Hedges — der schlimmste
        # denkbare Ausgang, ausgeloest von einer Nachricht, die der Server gar
        # nicht verstand. Unbekannte Pfade werden jetzt ehrlich abgelehnt.
        if self.path.rstrip("/") not in ("/positions", ""):
            self._json(404, {"ok": False, "msg":
                f"Unbekannter Pfad {self.path!r} — dieser reader-server kennt "
                "/positions, /schalter, /bedienfeld, /dump-an. Aeltere Version?"})
            return

        # Positionsdaten vom Userscript. Pausiert: Antwort traegt an=false
        # (Badge zeigt es), der Stand friert ein — stale != flat.
        if not _an:
            self._json(200, {"ok": True, "an": False})
            return

        # Struktur-Riegel (01.09.2026): eine Nachricht OHNE Positionsliste ist
        # kein Positions-Stand. Der Pfad-Riegel vom 30.08. deckt den bekannten
        # Fall ab (Userscript 0.3 an altem Server); dieser hier deckt jeden
        # kuenftigen ab — eine leere Liste darf nur ankommen, wenn wirklich
        # eine Liste geschickt wurde.
        if not isinstance(daten.get("positionen"), list):
            self._json(400, {"ok": False, "msg":
                "Feld 'positionen' fehlt oder ist keine Liste — wird NICHT als "
                "Stand uebernommen (ein fehlendes Feld ist kein 'flat')."})
            return

        # Blind-Riegel (01.09.2026, Finns Tabwechsel-Fund): das Userscript ab
        # 0.4.0 meldet selbst, wenn sein Lesevorgang nichts beweist — Tab
        # verdeckt und die Zellen kamen leer zurueck, Panel zugeklappt, Tabelle
        # weg. Vorher wurde daraus ein FRISCHES "0 Positionen", der Verbinder
        # sah frische Daten, und der Copier machte den Hedge zu — im naechsten
        # Tick wieder auf. Genau dieses Flattern. Blinde Staende frieren den
        # Stand jetzt ein, statt ihn platt zu schreiben.
        if daten.get("blind"):
            _blind_grund = str(daten.get("blind_grund") or "Reader meldet blind")
            if not _blind_seit:
                _blind_seit = time.time()
                print(f"\n[{time.strftime('%H:%M:%S')}] Reader BLIND: {_blind_grund} — "
                      f"Stand eingefroren, Hedges bleiben stehen.")
            try:
                _schreibe_datei(_mit_an(_stand))
            except Exception as e:
                print(f"\n[WARN] positions.json nicht schreibbar: {e}")
            self._json(200, {"ok": True, "an": True, "blind": True})
            return

        if _blind_grund:
            print(f"\n[{time.strftime('%H:%M:%S')}] Reader sieht wieder "
                  f"(war {round(time.time() - _blind_seit, 1)}s blind).")
            _blind_grund = ""
            _blind_seit = 0.0

        _stand = daten
        try:
            _schreibe_datei(_mit_an(_stand))
        except Exception as e:
            # Datei-Schreibfehler soll den Empfang nicht killen
            print(f"\n[WARN] positions.json nicht schreibbar: {e}")

        pos = daten.get("positionen", [])
        zeit = time.strftime("%H:%M:%S")
        # Beweisspur bei jeder Aenderung der Positionszahl (01.09.2026).
        # Die Live-Zeile unten ueberschreibt sich selbst — ein Wechsel auf
        # "flat" war damit nach 0,25 s nicht mehr nachweisbar, obwohl genau
        # daraus der Copier einen Close ableitet. Wechsel bleiben jetzt stehen,
        # inklusive der Userscript-Version: so ist von aussen belegbar, welcher
        # Stand die Aussage getroffen hat (der Grund, warum VERSION im
        # Userscript ueberhaupt doppelt steht).
        if _letzte_zahl is None or len(pos) != _letzte_zahl:
            print(f"\n[{zeit}] Positionen {_letzte_zahl} -> {len(pos)}"
                  f" (Userscript {daten.get('version') or 'unbekannt'},"
                  f" Tab {'vorn' if daten.get('sichtbar') else 'verdeckt/unbekannt'})")
            _letzte_zahl = len(pos)
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
        # Bedienfeld: das holt sich der Puls vor jedem Klick. 'alter_s' ist
        # das einzige Feld, auf das er sich verlaesst — er wartet auf einen
        # Stand, der JUENGER ist als sein letzter Klick, statt zu hoffen,
        # dass sich die Seite inzwischen aktualisiert hat.
        if self.path.rstrip("/") == "/bedienfeld":
            if _bedienfeld is None:
                self._json(200, {"ok": False, "msg":
                    "Noch kein Bedienfeld empfangen — laeuft das Userscript "
                    "(Version 0.3+) im TradingView-Tab?"})
                return
            out = dict(_bedienfeld)
            out["ok"] = True
            out["alter_s"] = round(time.time() - _bedienfeld_s, 3)
            self._json(200, out)
            return

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
