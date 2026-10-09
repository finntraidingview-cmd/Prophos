#!/usr/bin/env python3
"""Selbsttest Werbe-Karte „Time to upgrade?" (mt5-copier/order_bot.py CDP_WERBUNG_JS + _AugenSitzung.werbung_weg/stand, Finn 09.10.2026
~06:25 Dubai: Karte im Trading-Panel über „Positions", Bild ESSENTIAL/PLUS/PREMIUM, Marke „AD", X oben rechts — wurde nie erkannt).
Kein Chrome, kein Netz, keine Order.

Aufruf:  python3 tools/selftest_werbung_karte.py
Prueft: (1) CDP_WERBUNG_JS ist gültiges JavaScript (macOS: osascript -l JavaScript, sonst übersprungen); (2) Textmuster der Karte
erreicht ≥ 2 Merkmale ohne HART-Treffer, auch ohne „upgrade"-Wort; normale Panel-Texte nicht; (3) „Explore our plans"/„Upgrade"
sind nie das X (NIE), „Close"/leeres X schon; (4) X nicht klickbar → KEIN Esc, Spur „[Werbung] … kein Esc"; (5) Werbe-X setzt den
K4-Druckmerker nicht; (6) stand() prüft vorher auf Werbung (TradingView), im TopstepX-Tab nicht."""
import os
import re
import shutil
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


JS = ob.CDP_WERBUNG_JS

# (1) Syntax
if shutil.which("osascript"):
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", "new Function(" + __import__("json").dumps("return " + JS) + "); 'OK'"],
                       capture_output=True, text=True)
    check(r.stdout.strip() == "OK", f"CDP_WERBUNG_JS ist gültiges JavaScript ({(r.stderr or r.stdout).strip()[:120]})")
else:
    print("· Syntax-Prüfung übersprungen (kein osascript)")


def js_rx(name):
    """Regex-Literal(e) einer var aus dem JS als Python-Regex(e)."""
    m = re.search(r"var " + name + r" = (\[.*?\]|/.*?/i);", JS, re.S)
    roh = m.group(1)
    teile = re.findall(r"/((?:\\/|[^/])+)/i", roh)
    return [re.compile(t, re.I) for t in teile]


MERKMALE, ADFREE, KARTE, HART, NIE = (js_rx(n) for n in ("MERKMALE", "ADFREE", "KARTE", "HART", "NIE"))


def punkte(text, ad=False):
    n = sum(1 for rx in MERKMALE if rx.search(text)) + (2 if ADFREE[0].search(text) else 0) + (2 if KARTE[0].search(text) else 0)
    return n + (2 if ad else 0)


# (2) Textmuster der Karte (Finns Screenshot) und Gegenproben
KARTE_TEXT = "Time to upgrade? Unlock more charts, indicators and alerts. Explore our plans ESSENTIAL PLUS PREMIUM AD"
check(punkte(KARTE_TEXT) >= 2 and not HART[0].search(KARTE_TEXT), "Karte „Time to upgrade? … Explore our plans“ wird Werbung, kein HART-Treffer")
check(punkte("Explore our plans", ad=True) >= 2, "auch nur „Explore our plans“ + AD-Marke reicht")
check(punkte("ESSENTIAL PLUS PREMIUM") >= 2, "Bildtext ESSENTIAL/PLUS/PREMIUM allein reicht")
check(punkte("Time to upgrade?") >= 2, "„Time to upgrade?“ allein reicht (vorher nur 1 Merkmal)")
for normal in ("Positions Orders Account summary Notifications log Symbol Side Qty Avg Fill Price",
               "Buy 1 MNQZ6 MARKET Take profit, $ Stop loss, $ Units",
               "Tradovate Connect Live Demo Don't remember me"):
    check(punkte(normal) < 2 or HART[0].search(normal), f"keine Werbung: „{normal[:40]}…“")

# (3) Welche Knöpfe das X sein dürfen
for w in ("Explore our plans", "Upgrade", "Get started", "Premium"):
    check(bool(NIE[0].search(w)), f"„{w}“ wird nie gedrückt")
for w in ("Close", "close-button", "Schließen"):
    check(not NIE[0].search(w), f"„{w}“ darf das X sein")
XTABU = js_rx("XTABU")[0]
for w in ("Close account manager", "Collapse panel", "Close chart", "Maximize panel"):
    check(bool(NIE[0].search(w) or XTABU.search(w)), f"Panel-Knopf „{w}“ ist nie das Werbe-X")
check(not XTABU.search("Close") and not XTABU.search("close-button"), "einfaches Close bleibt erlaubt")
check("[class*=\"Close\"]" in JS and "elementFromPoint" in JS, "X auch mit Klasse „Close…“, nur wenn es oben liegt (elementFromPoint)")

# (4)+(5) werbung_weg: X nicht klickbar → kein Esc; Werbe-X lässt den K4-Druckmerker unberührt
alt_w = ob._warte
ob._warte = lambda *a, **k: None
try:
    s = object.__new__(ob._AugenSitzung)
    s.trail, s._werbung_at, s._druck_versucht = [], 0.0, False
    tasten = []
    s.taste = lambda key, modifiers=0: tasten.append(key)
    kand = [{"text": KARTE_TEXT[:120], "box": [10, 600, 500, 160], "x": [480, 604, 20, 20], "ad": True}]
    s.lese_js = lambda ausdruck, timeout=8: list(kand) if "MERKMALE" in ausdruck else None
    s._win_klick = lambda rect, name, druck=True, toast_ok=False: False
    n = s.werbung_weg(zwang=True)
    check(n == 0 and not tasten, "X nicht klickbar → kein Esc, nichts gedrückt")
    check(any(z.startswith("[Werbung]") and "kein Esc" in z for z in s.trail), "Spur „[Werbung] … eigenes X nicht klickbar … kein Esc“")

    s2 = object.__new__(ob._AugenSitzung)
    s2.trail, s2._werbung_at, s2._druck_versucht = [], 0.0, False
    folge = [list(kand), []]
    s2.lese_js = lambda ausdruck, timeout=8: (folge.pop(0) if folge else []) if "MERKMALE" in ausdruck else None

    def x_klick(rect, name, druck=True, toast_ok=False):
        s2._druck_versucht = True               # wie der echte _win_klick: setzt den Merker vor dem Druck
        return True
    s2._win_klick = x_klick
    n2 = s2.werbung_weg(zwang=True)
    check(n2 == 1 and any("[Werbung]" in z and "(AD)" in z and "über eigenes X geschlossen" in z for z in s2.trail),
          "Karte über eigenes X geschlossen, Spur mit (AD)")
    check(s2._druck_versucht is False, "Werbe-X setzt den K4-Druckmerker nicht (vorher False → danach False)")

    # (6) stand() prüft vorher auf Werbung — nur TradingView, nicht im TopstepX-Tab
    alt_win = ob._WIN_EINGABE
    ob._WIN_EINGABE = True
    try:
        for riegel, soll in ((True, 1), (False, 0)):
            s3 = object.__new__(ob._AugenSitzung)
            s3.trail, s3.tv_riegel = [], riegel
            aufrufe = []
            s3.werbung_weg = lambda zwang=False: aufrufe.append(zwang) or 0
            s3.ws = type("W", (), {"rufe": staticmethod(lambda *a, **k: {"result": {"value": {"ok": 1}}})})
            st = s3.stand({})
            check(st == {"ok": 1} and len(aufrufe) == soll, f"stand(): Werbe-Prüfung {'ja' if soll else 'nein'} (tv_riegel={riegel})")
    finally:
        ob._WIN_EINGABE = alt_win
finally:
    ob._warte = alt_w

print("\nALLES GRÜN" if not FEHLER else f"\nFEHLER: {FEHLER}")
raise SystemExit(1 if FEHLER else 0)
