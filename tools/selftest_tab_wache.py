#!/usr/bin/env python3
"""Selbsttest TAB-WÄCHTER (30.10.2026, Finn: „ist der Tab während des Starts nicht erreichbar, wird die Order abgebrochen oder gewartet"). tab_wache_warten (order_bot) und
tab_wache_antwort (panel) per Quelltext geschnitten, Tab + Dateien + Uhr simuliert: Tab antwortet → Senden; Tab stumm → Abbruch vor dem Klick; Tab wacht nach 30 s auf →
Senden; Tab im Minuten-Takt (gedrosselt, wie Vorfall) → Abbruch. Dazu Quelltext-Vertrag: Prüfung vor dem Klick, keine Prüfung danach. Ohne Netz, ohne Windows.
Aufruf: python3 tools/selftest_tab_wache.py"""
import ast
import os
import random
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(HIER, "..", "mt5-copier", "order_bot.py")
PANEL = os.path.join(HIER, "..", "mt5-copier", "panel.py")
HTML = os.path.join(HIER, "..", "prophos.html")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def funktion(pfad, name):
    src = open(pfad, encoding="utf-8").read()
    for k in ast.parse(src).body:
        if isinstance(k, ast.FunctionDef) and k.name == name:
            return ast.get_source_segment(src, k)
    raise ValueError(name)


class Sim:
    """Uhr + Tab: der Tab fragt das Panel im Takt 'takt_s' ab dem Zeitpunkt 'wach_ab'; eine Marke sieht er bei einer Abfrage und gibt sie bei der nächsten zurück (wie hedgeFruehWache)."""

    def __init__(self, antwort, takt_s, wach_ab=0.0, stumm=False):
        self.t, self.takt, self.wach_ab, self.stumm = 1000.0, takt_s, 1000.0 + wach_ab, stumm
        self.naechste = self.wach_ab
        self.ping, self.pong, self.vorgemerkt = None, None, ""
        self.antwort = antwort

    def uhr(self):
        return self.t

    def schlaf(self, s):
        ende = self.t + s
        while not self.stumm and self.naechste <= ende:
            self.t = max(self.t, self.naechste)
            felder, zeile = self.antwort("p1", self.vorgemerkt, self.ping, self.t)
            if zeile:
                self.pong = zeile["marke"]
            self.vorgemerkt = felder.get("ping", "")
            self.naechste += self.takt
        self.t = ende

    def schreibe(self, marke):
        self.ping = {"plan_id": "p1", "marke": marke, "at": self.t}

    def lies(self):
        return self.pong


def main():
    ns = {"time": __import__("time"), "random": random, "TAB_WACHE_MAX_S": None}
    src_bot = open(BOT, encoding="utf-8").read()
    for name in ("TAB_WACHE_MAX_S", "TAB_WACHE_ANTWORT_S", "TAB_WACHE_NOETIG", "TAB_WACHE_KLICK_BIS_S", "TAB_WACHE_MIN_S"):
        exec(re.search(rf"^{name} = .*$", src_bot, re.M).group(0), ns)
    exec(funktion(BOT, "tab_wache_warten"), ns)
    exec(funktion(BOT, "tab_wache_grenze"), ns)
    g = ns["tab_wache_grenze"]
    check(g(5) == 60 and g(200) == 30 and g(229) == 8 and g(400) == 8, "Wartezeit wird auf das Zeitbudget gekappt, Klick spätestens ~230 s")
    check('"tab_nicht_erreichbar"' in re.search(r"^PULS_NEUSTART_NIE = .*?\)\)", src_bot, re.M | re.S).group(0), "kein Chrome-Neustart nach dem Abbruch")
    pan = {}
    exec(funktion(PANEL, "tab_wache_antwort"), pan)
    warten, antwort = ns["tab_wache_warten"], pan["tab_wache_antwort"]

    def lauf(**kw):
        s = Sim(antwort, **kw)
        ok, text = warten(s.schreibe, s.lies, uhr=s.uhr, schlaf=s.schlaf, zufall=random.Random(7).random)
        return ok, text, s.t - 1000.0

    ok, text, dauer = lauf(takt_s=0.1)
    check(ok and dauer < 5, f"Tab antwortet (0,1 s Takt): Senden nach {dauer:.1f} s")
    ok, text, dauer = lauf(takt_s=1.0)
    check(ok and dauer < 10, f"verdeckter wacher Tab (1 s Takt, Edge-Log): Senden nach {dauer:.1f} s")
    ok, text, dauer = lauf(takt_s=0.1, stumm=True)
    check(not ok and 60 <= dauer < 70 and "antwortet nicht" in text, f"Tab stumm: Abbruch nach {dauer:.0f} s")
    ok, text, dauer = lauf(takt_s=0.1, wach_ab=30.0)
    check(ok and 30 <= dauer < 40, f"Tab wacht nach 30 s auf: Senden nach {dauer:.1f} s")
    s = Sim(antwort, takt_s=0.1, stumm=True)
    ok, text = warten(s.schreibe, s.lies, uhr=s.uhr, schlaf=s.schlaf, zufall=random.Random(7).random, max_s=8.0)
    check(not ok and s.t - 1000 < 12, "gekappte Wartezeit gilt")
    ok, text, dauer = lauf(takt_s=60.0)
    check(not ok and dauer >= 60, f"gedrosselt (1×/min wie Vorfall): Abbruch nach {dauer:.0f} s")
    ok, text, dauer = lauf(takt_s=60.0, wach_ab=4.0)
    check(not ok, "gedrosselt, eine Antwort fällt zufällig in die Frist: reicht nicht")
    ok, text, dauer = lauf(takt_s=0.1, wach_ab=58.0)
    check(not ok or dauer <= 66, "wacht erst kurz vor Ablauf: endet spätestens kurz nach 60 s")

    def wirft(_m):
        raise OSError("Platte")
    s = Sim(antwort, takt_s=0.1)
    ok, _t = warten(wirft, s.lies, uhr=s.uhr, schlaf=lambda x: setattr(s, "t", s.t + x), zufall=random.Random(7).random)
    check(not ok, "Marke nicht schreibbar: kein Beweis, kein Senden")

    f, z = antwort("p1", "", {"plan_id": "p2", "marke": "m", "at": 1000.0}, 1001.0)
    check(f == {"tab_wache": 1} and z is None, "Marke eines anderen Plans wird nicht ausgeliefert")
    f, z = antwort("p1", "m", {"plan_id": "p1", "marke": "m", "at": 1000.0}, 1400.0)
    check("ping" not in f and z is None, "Marke älter als 5 min zählt nicht")
    f, z = antwort("p1", "alt", {"plan_id": "p1", "marke": "m", "at": 1000.0}, 1001.0)
    check(f.get("ping") == "m" and z is None, "falsche Antwort-Marke wird nicht abgelegt")
    f, z = antwort("p1", "m", {"plan_id": "p1", "marke": "m", "at": 1000.0}, 1001.0)
    check(z and z["marke"] == "m", "richtige Antwort wird abgelegt")

    # Vertrag
    m = funktion(BOT, "modus_tvkette_cdp")
    pruef = [x.start() for x in re.finditer(r"_tab_wache_pruefen\(cmd, trail", m)]
    klick = m.index('res["gesendet"], res["retry_ok"] = True, False')
    check(len(pruef) == 2 and all(p < klick for p in pruef), "zwei Prüfungen, beide vor dem Senden; keine danach")
    check(pruef[1] < m.index("AB HIER UNUMKEHRBAR"), "zweite Prüfung vor dem frischen Blick auf Ticket, Knopf und Konto")
    ab = m[m.index("def tab_abbruch"):m.index("if scharf and symbol:\n        tab_text")]
    check('gesendet=False' in ab and 'retry_ok=True' in ab and "_puls_ergebnis_senden" in ab and 'schritt="tab_nicht_erreichbar"' in ab, "Abbruch: nichts gesendet, eigener Schritt, Meldung an Railway")
    w = funktion(BOT, "_tab_wache_pruefen")
    check("close" not in w.lower().replace("os.close", "") and "klick" not in w, "Wächter fasst keine Order an")
    src = open(HTML, encoding="utf-8").read()
    check("pk.tab_wache === 1" in src and "..._tabWacheMarke" in src, "Tab setzt die Marke nur, wenn das Panel es kann")
    check("plan.route === 'tvv2' && plan.hedgeEur > 0 && MT5_LOCAL" in src, "nur Orbit mit Fusion-Hedge")
    check(src.count("_tabWacheMarke") == 3, "tsx-konto und Echo bleiben ohne Marke")
    check("r.code === 'tab_nicht_erreichbar'" in src and "'tab_nicht_erreichbar'])" in src, "Tab: Plan bleibt Geplant, zählt nicht als Fehlversuch")
    app = open(os.path.join(HIER, "..", "app.py"), encoding="utf-8").read()
    check('alarm_senden(1, "tab_nicht_erreichbar"' in app, "🔴 an die Master-IDs")


if __name__ == "__main__":
    main()
    if FEHLER:
        print(f"FEHLER: {len(FEHLER)}")
        sys.exit(1)
    print("OK — Tab-Wächter grün")
