#!/usr/bin/env python3
"""Selbsttest PULS: STÖRER ÜBER DER SEITEN-KACHEL + NEULADEN NACH DEM LINK (order_bot.py, 20.10.2026, Finn 01:20 Dubai: „welche Start-Fehler
von heute können wir noch fixen?"). Zwei echte Spuren:
(A) Aurel 13:37 Dubai, Plan 919fd3a5: „Seite steht nicht auf SELL ('Buy 2 NQZ6 MARKET', 3 Versuche, auch nach Neu-Öffnen per Shift+T)" — die
    Taub-Diagnose sah beide Male „oben am Punkt video \"\"" (Werbevideo über der Sell-Kachel). Jetzt: cdp_taub_stoerer erkennt Video/iframe,
    _cdp_seite_stoerer_versuch erzwingt die Störer-Räumung (werbung_weg(zwang=True), nur bekannte Werbe-X) und klickt die Kachel genau
    EINMAL neu; die Diagnose-Zeile nennt Vorfahren-Kette + nächsten Schließ-Knopf.
(B) Finn + Pascal 15:42 Dubai, Plan 150621d2: nach ?trade-now=TRADOVATE 40 s „dialoge [], leiste null" → Abbruch; 15:59 derselbe Weg
    klappte. Jetzt: _cdp_nach_link_mit_neuladen lädt den Tab bei 'nichts' genau EINMAL neu (Page.reload, nichts geklickt) und wartet nochmal.
Ohne Windows/Chrome: Funktionen aus dem Quelltext gegen nachgebaute Sitzungen. Aufruf: python3 tools/selftest_puls_stoerer_neuladen.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(HIER, "..", "mt5-copier", "order_bot.py")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(src, name):
    i = src.index(f"\ndef {name}(") + 1
    return src[i:src.find("\n\n\n", i)]


src = open(BOT, encoding="utf-8").read()
ns = {"re": re, "_warte": lambda *a, **k: None, "cdp_rect": lambda el: (el or {}).get("rect") if isinstance(el, dict) else None,
      "_cdp_kachel_weg": lambda s, trail: 0}
exec(re.search(r"^CDP_TAUB_STOERER_TAGS = .*$", src, re.M).group(0), ns)
for name in ("cdp_taub_stoerer", "_cdp_seite_stoerer_versuch", "_cdp_tab_neu_laden", "_cdp_nach_link_mit_neuladen"):
    exec(fn(src, name), ns)
T, V, NL, NLM = ns["cdp_taub_stoerer"], ns["_cdp_seite_stoerer_versuch"], ns["_cdp_tab_neu_laden"], ns["_cdp_nach_link_mit_neuladen"]

# (A1) Erkennung aus der echten Diagnose-Zeile
check(T({"oben": 'video ""', "sperre": "", "fokus": True}) is True, "Aurel 13:37: oben am Punkt video \"\" = Störer")
check(T({"oben": 'iframe#ad "…"'}) is True and T({"oben": "video[promo]"}) is True, "iframe/video mit id/data-name = Störer")
check(T({"oben": 'div Sell'}) is False and T({"oben": "button \"Sell\""}) is False and T(None) is False and T({"oben": "videoX"}) is False,
      "Ticket-Element, Knopf, nichts, ähnliches Wort = kein Störer")

# (A2) Diagnose-JS trägt Kette + Schließ-Knopf, Diagnose-Zeile nennt sie nur beim Störer und gibt den Befund zurück
js = fn(src, "cdp_ticket_taub_js")
check("kette:kette.join(' < ')" in js and "xnah:xn||'-'" in js and "account manager|panel|collapse|chart|layout|watchlist" in js,
      "cdp_ticket_taub_js: Vorfahren-Kette + nächster Schließ-Knopf (Panel-/Chart-Knöpfe nie)")
spur = fn(src, "_cdp_ticket_taub_spur")
check("Störer-Kette" in spur and "if cdp_taub_stoerer(d) else \"\"" in spur and spur.rstrip().endswith("return d"), "_cdp_ticket_taub_spur: Kette/X nur bei Störer, Befund zurück")


# (A3) Störer-Versuch gegen nachgebaute Sitzung
class Sitzung:
    def __init__(self, seite_danach, werbung=1, kachel=True):
        self.seite, self.seite_danach, self.werbung, self.kachel = "buy", seite_danach, werbung, kachel
        self.klicks, self.zwang, self.stand_n = [], [], 0

    def werbung_weg(self, zwang=False):
        self.zwang.append(zwang)
        return self.werbung

    def stand(self, opts):
        self.stand_n += 1
        return {}

    def klick(self, rect, name):
        self.klicks.append(name)
        self.seite = self.seite_danach
        return True


def lauf(s, d):
    trail = []
    plan = {"richtung": "sell"}
    ticket = lambda: {"verkaufen": {"rect": [1180, 300, 60, 24]} if s.kachel else None, "seite": s.seite}
    knopf = lambda: {"seite": s.seite}
    ok = V(s, {}, trail, plan, ticket, knopf, d)
    return ok, trail


s = Sitzung(seite_danach="sell", werbung=1)
ok, trail = lauf(s, {"oben": 'video ""'})
check(ok is True and s.zwang == [True] and s.klicks == ["Seite SELL (nach Störer-Räumung)"], f"Störer + Räumung schließt 1 Werbung → EIN Klick, Seite steht ({s.klicks})")
check(any("Störer-Räumung erzwungen, 1 Werbung(en) geschlossen → EIN neuer Versuch" in t for t in trail) and trail[-1] == "Seite steht nach der Störer-Räumung", f"Spur nennt Räumung + Ergebnis ({trail})")
s = Sitzung(seite_danach="buy", werbung=0)
ok, trail = lauf(s, {"oben": 'video ""'})
check(ok is False and s.zwang == [True] and len(s.klicks) == 1 and trail[-1].startswith("Seite steht auch nach der Störer-Räumung nicht"), "Störer, nichts geschlossen, Seite bleibt → False (weiter Shift+T/Abbruch), nur EIN Klick")
s = Sitzung(seite_danach="sell")
ok, trail = lauf(s, {"oben": "div Sell", "fokus": True})
check(ok is False and s.zwang == [] and s.klicks == [] and trail == [], "kein Störer → kein Zwang, kein Klick, keine Spur (Weg unverändert)")
s = Sitzung(seite_danach="sell", kachel=False)
ok, trail = lauf(s, {"oben": 'video ""'})
check(ok is False and s.klicks == [] and trail[-1] == "Seiten-Kachel nach der Störer-Räumung nicht gefunden", "Kachel nach der Räumung weg → kein Klick, Grund in der Spur")
check("_cdp_seite_stoerer_versuch(s, opts, trail, plan, ticket, knopf, _d)" in src and src.count("if str(knopf().get(\"seite\") or ticket().get(\"seite\") or \"\") != plan[\"richtung\"]:") == 2,
      "Sell-Schleife: Störer-Versuch vor dem Shift+T-Weg, Abbruch-Prüfung danach erneut")


# (B) Neuladen nach dem Link gegen nachgebaute Sitzung/Blick
class Tab:
    def __init__(self, antworten, neu_laden_ok=True):
        self.antworten, self.neu, self.ws = list(antworten), 0, None
        self.neu_laden_ok = neu_laden_ok

    def neu_laden(self):
        if not self.neu_laden_ok:
            raise RuntimeError("tot")
        self.neu += 1


def nach_link(s, opts, trail):
    return s.antworten.pop(0)


ns["_cdp_nach_link"] = nach_link
t = Tab([("nichts", {"dialoge": [], "leiste": None}), ("dialog", {"dialoge": [{"titel": "Connect broker"}]})])
trail = []
art, x = NLM(t, {}, trail)
check(art == "dialog" and t.neu == 1 and not t.antworten, f"Finn+Pascal 15:42: 'nichts' → EIN Neuladen → zweiter Blick 'dialog' ({trail})")
check(any("EINMAL den ?trade-now-Tab neu laden" in z for z in trail) and any("?trade-now-Tab neu geladen" in z for z in trail), "Spur: Grund + Neuladen")
t = Tab([("nichts", {}), ("nichts", {})])
trail = []
art, x = NLM(t, {}, trail)
check(art == "nichts" and t.neu == 1, "zweimal 'nichts' → genau EIN Neuladen, dann wie bisher Abbruch 'dialog'")
t = Tab([("dialog", {"dialoge": [1]})])
trail = []
art, x = NLM(t, {}, trail)
check(art == "dialog" and t.neu == 0 and trail == [], "Dialog sofort da → kein Neuladen, keine Spur")
t = Tab([("verbunden", "LFE…0001 USD")])
art, x = NLM(t, {}, [])
check(art == "verbunden" and t.neu == 0, "von selbst verbunden → kein Neuladen")
t = Tab([("nichts", {})], neu_laden_ok=False)
trail = []
art, x = NLM(t, {}, trail)
check(art == "nichts" and t.neu == 0 and any("Neuladen nicht möglich (RuntimeError)" in z for z in trail), "Neuladen scheitert → alter Weg, Grund in der Spur, kein zweiter Blick")
check("art, x = _cdp_nach_link_mit_neuladen(s, opts, trail)" in src and src.count("art, x = _cdp_nach_link(s, opts, trail)") == 2,
      "_cdp_tradovate_verbinden nutzt den Neulade-Weg (zwei innere Blicke, einer davor, einer danach)")

print()
if FEHLER:
    print(f"FEHLER ({len(FEHLER)}):")
    for f in FEHLER:
        print("  - " + f)
    sys.exit(1)
print("ALLES GRÜN")
