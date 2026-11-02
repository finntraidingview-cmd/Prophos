#!/usr/bin/env python3
"""Selbsttest USD→EUR LIVE (app.py, 03.11.2026, Finn „Ja, live holen“; Anlass Payout Jacob Tradeify 150k mit 0,85 statt EZB-Kurs).

Aufruf:  python3 tools/selftest_fx_live.py
Ohne Netz und ohne Datenbank: der Block wird aus app.py geladen, Abruf/Supabase sind Attrappen. Prüft Kurswahl (Live gewinnt, sonst erster
Eintrag, sonst 0,85), Plausibilität 0,7–1,1, Schreiben nur bei neuem EZB-Tag für alle IDs, Fehler → nichts schreiben, nur Railway startet,
alle Leser (Admin, WD, Liquide) über fx_aus_zeilen, Frontend zeigt die Quelle und speichert Hand-Eingaben mit quelle 'hand'."""
import json
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
SRC = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        FEHLER.append(text)


i, j = SRC.index("# ══ USD→EUR LIVE"), SRC.index("start_fx_live()\n\n")
ns = {"json": json, "re": re, "os": os}
exec(SRC[i:j], ns)

# Kurswahl
zeile = lambda v: {"value": v}
f = ns["fx_aus_zeilen"]
check(f([]) == 0.85, "kein Eintrag → Standard 0,85")
check(f([zeile({"rate": 0.8935})]) == 0.8935, "Hand-Eintrag ohne Quelle (alt) gilt")
check(f([zeile(0.9)]) == 0.9 and f([zeile('{"rate": 0.88}')]) == 0.88, "alte Formen (Zahl, JSON-Text) gelten weiter")
check(f([zeile({"rate": 0.8935, "quelle": "hand"}), zeile({"rate": 0.8916, "quelle": "live", "datum": "2026-11-02"}),
         zeile({"rate": 0.8901, "quelle": "live", "datum": "2026-10-31"})]) == 0.8916, "jüngster Live-Kurs gewinnt (Admin = alle IDs gleich)")
check(f([zeile({"rate": 3}), zeile({"rate": None}), zeile({"rate": 0.87})]) == 0.87, "unplausible Zeilen übersprungen")
# S9 zu .2006: Hand-Eingabe jünger als der Live-Kurs gewinnt, ältere nicht (Formate wie Tab …Z und Railway …+00:00)
live2 = zeile({"rate": 0.89158, "quelle": "live", "datum": "2026-11-02", "at": "2026-11-02T22:43:30.123456+00:00"})
check(f([live2, zeile({"rate": 0.8935, "quelle": "hand", "at": "2026-11-03T00:10:00.000Z"})]) == 0.8935, "Hand nach dem Live-Lauf → Hand gilt")
check(f([live2, zeile({"rate": 0.8935, "quelle": "hand", "at": "2026-11-02T20:10:00.000Z"})]) == 0.89158, "Hand vor dem Live-Lauf → Live gilt")
check(f([zeile({"rate": 0.89158, "quelle": "live", "datum": "2026-11-02"}), zeile({"rate": 0.8935, "quelle": "hand", "at": "2026-11-02T09:00:00Z"})]) == 0.8935,
      "Live ohne at: Hand am EZB-Tag gilt")
check(f([live2, zeile({"rate": 0.8935, "quelle": "hand", "at": "2026-11-03T00:10:00Z"}),
         zeile({"rate": 0.9, "quelle": "hand", "at": "2026-11-03T01:00:00Z"})]) == 0.9, "mehrere Hand-Eingaben → die jüngste")
check(f([live2, zeile({"rate": 0.8935, "quelle": "hand", "at": "2026-11-03T00:10:00Z"}),
         zeile({"rate": 0.8902, "quelle": "live", "datum": "2026-11-03", "at": "2026-11-03T16:00:00+00:00"})]) == 0.8902, "nächster Live-Kurs löst die Hand ab")

# Plausibilität
p = ns["fx_live_pruefen"]
check(p({"date": "2026-11-02", "rates": {"EUR": 0.89158}}) == (0.89158, "2026-11-02"), "frankfurter-Antwort → (Kurs, Tag)")
check(p({"date": "2026-11-02", "rates": {"EUR": 0.65}}) is None and p({"date": "2026-11-02", "rates": {"EUR": 1.2}}) is None, "außerhalb 0,7–1,1 → verworfen")
check(p({"rates": {"EUR": 0.9}}) is None and p({}) is None and p(None) is None, "kaputte Antwort → verworfen")


# Abruf mit Attrappen
class Antw:
    def __init__(self, code, daten):
        self.status_code, self._d, self.text = code, daten, json.dumps(daten)

    def json(self):
        return self._d

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


lage = {"ezb": {"date": "2026-11-02", "rates": {"EUR": 0.89158}}, "zeilen": [], "post": []}
ns.update(
    requests=type("R", (), {"get": staticmethod(lambda url, timeout=None: Antw(200, lage["ezb"]) if lage["ezb"] else Antw(503, {}))}),
    _sb_all=lambda t, q: lage["zeilen"],
    _auth_liste_anfrage=lambda: Antw(200, {"users": [{"id": "u1"}, {"id": "u2"}, {"id": "u3"}]}),
    _sb_anfrage=lambda m, url, **kw: lage["post"].append(kw["json"]) or Antw(201, {}),
    _sb_headers=lambda prefer=None: {}, SUPABASE_URL="https://x",
    datetime=__import__("datetime").datetime, timezone=__import__("datetime").timezone,
)
takt = ns["_fx_live_takt"]
lage["zeilen"] = [zeile({"rate": 0.8935, "quelle": "hand"})]
out = takt()
check(len(lage["post"]) == 1 and len(lage["post"][0]) == 3 and all(z["value"]["quelle"] == "live" and z["value"]["rate"] == 0.89158
      and z["value"]["datum"] == "2026-11-02" and z["key"] == "fx_usd_eur" for z in lage["post"][0]), f"neuer EZB-Tag → alle 3 IDs geschrieben ({out})")
out = takt()
check(len(lage["post"]) == 1, f"gleicher Tag nochmal → nichts geschrieben, Hand-Eingabe danach bleibt ({out})")
ns["_fx_info"]["datum"] = None
lage["zeilen"] = [zeile({"rate": 0.89158, "quelle": "live", "datum": "2026-11-02"})]
takt()
check(len(lage["post"]) == 1, "nach Neustart: gespeicherter Live-Tag erkannt → kein Überschreiben beim Deploy")
lage["ezb"] = {"date": "2026-11-03", "rates": {"EUR": 0.8902}}
takt()
check(len(lage["post"]) == 2 and lage["post"][1][0]["value"]["rate"] == 0.8902, "nächster EZB-Tag → neu geschrieben")
for name, ezb in (("Abruf scheitert", None), ("unplausibel", {"date": "2026-11-04", "rates": {"EUR": 0.5}})):
    lage["ezb"] = ezb
    try:
        takt()
        geworfen = False
    except Exception:
        geworfen = True
    check(geworfen and len(lage["post"]) == 2, f"{name} → Fehler gemeldet, nichts geschrieben (alter Wert bleibt, nie 0,85)")

# Verdrahtung
start = SRC[SRC.index("def start_fx_live():"):SRC.index("start_fx_live()\n\n")]
check("RAILWAY_ENVIRONMENT" in start and "return" in start, "nur Railway startet den Abruf")
check("fx = fx_aus_zeilen(fx_rows)" in SRC, "Admin-Übersicht/Kapitel lesen über fx_aus_zeilen")
for fn in ("def _wd_fx():", "def _lq_fx():"):
    k = SRC[SRC.index(fn):SRC.index(fn) + 200]
    check("fx_aus_zeilen(" in k, f"{fn[4:-3]} liest über fx_aus_zeilen (Kapital-Rückfall = _lq_fx)")
check("quelle: 'hand'" in HTML and "window._fxInfo = data.value" in HTML and 'id="fxUsdEurQuelle"' in HTML,
      "Frontend: Quelle mit Datum, Hand-Eingabe als quelle 'hand'")
check("fxErstLaden" in HTML and "setInterval(() => { if(currentUserId) loadFxRate()" in HTML, "Frontend lädt den Kurs bis zum Login nach und alle 3 h frisch")

print("ROT:" if FEHLER else "alles grün", FEHLER if FEHLER else "")
sys.exit(1 if FEHLER else 0)
