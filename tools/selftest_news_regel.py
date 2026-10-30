#!/usr/bin/env python3
"""Selbsttest: NEWS-REGEL FUNDED CFD, app.py-Teil (30.10.2026, S8 8427eda9). /news/calendar cacht einen gescheiterten Abruf nicht mehr als
frisch, meldet unvollstaendig und liefert den Schalter news_regel (funded_cfd_plan_regeln.news_regel, Lesefehler = an). Ohne Netz:
requests.get und sb_select werden ersetzt. Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_news_regel.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


print("1) news_antwort (rein)")
alt = {"events": [{"id": "a"}], "fetched": 100.0, "unvollstaendig": False}
p, st, c = app.news_antwort(False, True, [], alt, 500.0)
check(st == 200 and p["unvollstaendig"] is True and p["fetched"] == 100.0 and c is None, "diese Woche fehlt + alter Cache → alter Stand, unvollständig, nicht neu cachen")
p, st, c = app.news_antwort(False, False, [], None, 500.0)
check(st == 502 and p["events"] == [] and c is None, "diese Woche fehlt ohne Cache → 502, nichts gecacht")
p, st, c = app.news_antwort(True, False, [{"id": "x"}], None, 500.0)
check(st == 200 and not p["unvollstaendig"] and c and c[1] == app.NEWS_TTL_OHNE_NAECHSTE, "nur nächste Woche fehlt → liefern, kurz cachen")
p, st, c = app.news_antwort(True, True, [{"id": "x"}], None, 500.0)
check(st == 200 and c and c[1] == app.NEWS_TTL and p["fetched"] == 500.0, "beides ok → 30 min cachen")


class Antw:
    def __init__(self, code, daten):
        self.status_code, self._d = code, daten

    def json(self):
        return self._d


EV = [{"title": "NFP", "country": "USD", "date": "2026-11-06T08:30:00-05:00", "impact": "High"}, {"title": "x", "country": "EUR", "impact": "High"}]
plan = {"this": Antw(429, None), "next": Antw(429, None)}
app.requests.get = lambda url, **k: plan["this" if "thisweek" in url else "next"]
regel = {"zeile": {"aktiv": True, "news_regel": False}, "fehler": False}


def sel(t, p):
    if regel["fehler"]:
        raise RuntimeError("Spalte fehlt")
    return [regel["zeile"]] if t == "funded_cfd_plan_regeln" else []


app.sb_select = sel
ALARME = []
app.alarm_senden = lambda *a, **k: ALARME.append(a)
cl = app.app.test_client()


def frisch():
    app._news_cache.update(ts=0, data=None, ttl=app.NEWS_TTL, fehl_bis=0.0)
    app._news_regel["at"] = 0.0


print("2) Route /news/calendar")
frisch()
r = cl.get("/news/calendar")
d = r.get_json()
check(r.status_code == 502 and d["events"] == [] and app._news_cache["data"] is None, "429 auf beiden → 502, leerer Stand NICHT gecacht")
check(d.get("news_regel") is False, "news_regel aus der Regel (false) auch im Fehlerfall")
ZAEHL = []
_g = app.requests.get
app.requests.get = lambda url, **k: (ZAEHL.append(url), _g(url, **k))[1]
cl.get("/news/calendar")
check(not ZAEHL, "nach einem Fehler 2 min keine neue FF-Anfrage")
app.requests.get = _g
app._news_cache["fehl_bis"] = 0.0
plan.update(this=Antw(200, EV), next=Antw(200, []))
r = cl.get("/news/calendar")
d = r.get_json()
check(r.status_code == 200 and [e["title"] for e in d["events"]] == ["NFP"] and d["unvollstaendig"] is False, "beides ok → nur USD, unvollstaendig false")
plan.update(this=Antw(429, None))
app._news_cache["ts"] = 0       # TTL abgelaufen
ts_vorher = app._news_cache["ts"]
r = cl.get("/news/calendar")
d = r.get_json()
check(r.status_code == 200 and d["unvollstaendig"] is True and d["events"] and app._news_cache["ts"] == 0, "später 429 → alter Stand mit unvollstaendig, Cache nicht überschrieben")
frisch()
regel["fehler"] = True
plan.update(this=Antw(200, EV), next=Antw(500, None))
d = cl.get("/news/calendar").get_json()
check(d.get("news_regel") is True, "Regel nicht lesbar → news_regel true (bleibt an)")
check(app._news_cache.get("ttl") == app.NEWS_TTL_OHNE_NAECHSTE, "nur nächste Woche fehlt → kurze TTL")
regel["fehler"] = False

print("3) 🟠 nach 2 h am Stück")
app._news_fehl.update(seit=0.0, gemeldet=False)
app._news_fehl_merken(False, 1000.0, True)
app._news_fehl_merken(False, 1000.0 + 3600, True)
check(not ALARME, "nach 1 h noch kein Alarm")
app._news_fehl_merken(False, 1000.0 + 7300, True)
app._news_fehl_merken(False, 1000.0 + 9000, True)
check(len(ALARME) == 1 and ALARME[0][1] == "news_kalender_fehlt" and ALARME[0][0] == 2, "nach > 2 h genau ein 🟠")
app._news_fehl_merken(True, 20000.0, True)
check(app._news_fehl["seit"] == 0.0 and not app._news_fehl["gemeldet"], "Kalender wieder da → zurückgesetzt")
app._news_fehl.update(seit=0.0, gemeldet=False)
app._news_fehl_merken(False, 0.5, False)
app._news_fehl_merken(False, 0.5 + 99999, False)
check(len(ALARME) == 1, "Planer aus → kein Alarm")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
