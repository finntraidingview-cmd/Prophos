#!/usr/bin/env python3
"""Selbsttest NG2b (23.11.2026, Master nach Prüfer-Befund S4): „KEINE Bestaetigung binnen 12 s — Grund: … (API)“ trägt „— nichts gesendet“
NUR bei API-Grund (kein Rechengrund „(API: …)“) UND wenn jede gedrückte Auslöse-Stufe nachweislich nichts gesendet hat (stufe_urteil 'nichts').
Geprüft ohne Netz/Windows: keine_bestaetigung_nichts_gesendet, stufen_ausloesen(urteile=…) mit virtueller Uhr, die Meldung in run() (Quelltext)
und das echte Frontend-Muster sfVorOrderBeleg aus prophos.html per JavaScriptCore (macOS) gegen die neue und die alte Meldung.
Aufruf: python3 tools/selftest_ng2b_nichts_gesendet.py"""
import json
import os
import re
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


N = ob.keine_bestaetigung_nichts_gesendet
API_GETRENNT = ("Terminal nicht mit dem Server verbunden", "Internet/Login des Terminals prüfen", "API")
API_GESPERRT = ("Handel am Konto gesperrt (account_info.trade_allowed = False) — Kontostand 89 987.00",
                "Konto im Dashboard der Firma prüfen und abschließen bzw. archivieren — nicht neu starten", "API")
API_MARGE = ("zu wenig freie Marge für dieses Volumen (API: nötig 5 000.00, frei 3 000.00)", "Volumen senken oder Marge prüfen", "API")
JOURNAL = ("SL/TP ungültig", "SL/TP prüfen", "Journal: [Invalid stops]")
check(N(API_GETRENNT, False, ["nichts"]) and N(API_GESPERRT, False, ["nichts", "nichts", "nichts", "nichts"]),
      "API-Grund, alle Stufen 'nichts' → nichts gesendet")
check(not N(API_GESPERRT, True, ["nichts"]), "Anfrage gesehen (Fall 17.11.) → bleibt unklar")
check(not N(API_GETRENNT, False, ["nichts", "bestaetigt"]) and not N(API_GETRENNT, False, ["bestaetigt"]),
      "Dialog nach dem Druck zu ('bestaetigt' ohne Position) → kein Beleg")
check(not N(API_GETRENNT, False, ["antwort"]) and not N(API_GETRENNT, False, ["kein_beweis"]) and not N(API_GETRENNT, False, ["gesendet"]),
      "Server-Antwort / Journal unlesbar / gesendet → kein Beleg")
check(not N(API_GETRENNT, False, []) and not N(API_GETRENNT, False, None), "keine gedrückte Stufe bekannt → kein Beleg")
check(not N(API_MARGE, False, ["nichts"]), "Rechengrund „(API: nötig … frei …)“ → nie (Marge nach dem Klick gerechnet)")
check(not N(JOURNAL, False, ["nichts"]) and not N(None, False, ["nichts"]) and not N(("x", "y"), False, ["nichts"]), "Journal-Grund / kein Grund → nie")

# ── stufen_ausloesen sammelt die Urteile je gedrückter Stufe ───────────────────────────────────────────────────────────────────
class Uhr:
    def __init__(self):
        self.t = 1000.0

    def uhr(self):
        return self.t

    def schlafen(self):
        self.t += 0.5


def lauf(lesen, wege=("A", "B", "C")):
    u, ur = Uhr(), []
    gedrueckt = []
    erg = ob.stufen_ausloesen([(n, (lambda n=n: gedrueckt.append(n))) for n in wege], lambda ab, mj: lesen(u.t), 5.0, [], "buy",
                              lambda: u.t, uhr=u.uhr, schlafen=u.schlafen, urteile=ur)
    return erg, ur, gedrueckt


(aus, anf), ur, gd = lauf(lambda t: (False, False, None, "", True))
check(aus == "C" and anf is False and ur == ["nichts", "nichts", "nichts"] and gd == ["A", "B", "C"], f"Journal lesbar, nie eine Anfrage → je Stufe 'nichts' ({ur})")
(aus, anf), ur, gd = lauf(lambda t: (False, False, None, "", False))
check(anf is True and ur == ["kein_beweis"] and gd == ["A"], f"Journal unlesbar → 'kein_beweis', keine 2. Stufe ({ur})")
(aus, anf), ur, gd = lauf(lambda t: (False, True, None, "", True))
check(ur == ["bestaetigt"] and gd == ["A"] and not N(API_GETRENNT, anf, ur), f"Dialog zu nach Stufe 1 → 'bestaetigt', nie „nichts gesendet“ ({ur}, {anf})")
(aus, anf), ur, gd = lauf(lambda t: (False, False, "'1': market buy 1 NAS100", "", True))
check(anf is True and ur == ["gesendet"], "Anfrage im Journal → 'gesendet'")
ur2 = []
ob.stufen_ausloesen([("A", lambda: None)], lambda ab, mj: (False, False, None, "", True), 1.0, [], "buy", lambda: 0.0,
                    uhr=iter([0.0, 2.0, 2.0, 2.0]).__next__, schlafen=lambda: None)
check(ur2 == [], "ohne urteile-Liste wie bisher (kein Pflichtfeld)")

# ── Meldung in run() ───────────────────────────────────────────────────────────────────────────────────────────────────────────
src = open(os.path.join(WURZEL, "mt5-copier", "order_bot.py"), encoding="utf-8").read()
check("urteile=_stufen_urteile)" in src and "_stufen_urteile = []" in src
      and src.index("_stufen_urteile = []") < src.index("ausgeloest, anfrage_gesehen = stufen_ausloesen("), "run(): Urteile werden gesammelt")
blk = src[src.index("_ng = keine_bestaetigung_nichts_gesendet(grund, anfrage_gesehen, _stufen_urteile)"):]
blk = blk[:blk.index('"trail": _spur(trail)}')]
check('"Dialog geschlossen" + (" — nichts gesendet (Journal auf allen Stufen ohne Anfrage)" if _ng else "")' in blk
      and blk.index("nichts gesendet") < blk.index(". Spur: ["), "Zusatz steht im Kopf VOR „ Spur:“")
sa = src[src.index('"vom Server abgelehnt — nichts platziert. Spur:'):]
check(src.count("keine_bestaetigung_nichts_gesendet(") == 2, "nur der eine Rückweg (API-Grund ohne Server-Beleg) nutzt den Beleg")

# ── Frontend: sfVorOrderBeleg aus prophos.html per JavaScriptCore ─────────────────────────────────────────────────────────────
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
a = html.index("const SF_BELEG_NICHT_PLATZIERT = [")
b = html.index("window._sfVorOrderBeleg = sfVorOrderBeleg")
code = html[a:b]


def meldung(grund, ng):
    return (f"KEINE Bestaetigung binnen 12 s — Grund: {grund[0]} ({grund[2]}) → {grund[1]}. Position nicht am Konto, Dialog geschlossen"
            + (" — nichts gesendet (Journal auf allen Stufen ohne Anfrage)" if ng else "") + ". Spur: [0.0s·Start > 4.1s·Fokus+Leertaste] · Dialog: x")


faelle = {"getrennt_ng": meldung(API_GETRENNT, True), "gesperrt_ng": meldung(API_GESPERRT, True),
          "getrennt_alt": meldung(API_GETRENNT, False), "gesperrt_alt": meldung(API_GESPERRT, False)}
if os.path.exists(JSC):
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "t.js")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(code + "\nvar F = " + json.dumps(faelle, ensure_ascii=False) + ";\nvar o = {};\nfor (var k in F) o[k] = sfVorOrderBeleg(F[k]);\nprint(JSON.stringify(o));\n")
        r = subprocess.run([JSC, f], capture_output=True, text=True)
        try:
            o = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            o = {"fehler": (r.stdout + r.stderr)[-300:]}
    check(o.get("getrennt_ng") is True and o.get("gesperrt_ng") is True, f"Frontend: neue Meldung → Beleg „nicht platziert“ (sauberer Fehlstart) ({o})")
    check(o.get("getrennt_alt") is False and o.get("gesperrt_alt") is False, f"Frontend: ohne Zusatz weiter kein Beleg (unklar bleibt) ({o})")
else:
    print("· JavaScriptCore fehlt — Frontend-Prüfung übersprungen")

print("\n" + ("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER"))
sys.exit(1 if FEHLER else 0)
