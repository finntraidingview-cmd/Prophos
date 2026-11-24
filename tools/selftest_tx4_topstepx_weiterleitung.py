#!/usr/bin/env python3
"""Selbsttest TX4 (Master 25.11.2026, Finn: Balance lesen bei TopstepX klappt nicht — „einmal auf Login drücken, dann 7–13 Sekunden warten, nicht
nochmal klicken“). Befund 23.11. 22:01 – 24.11. 23:27 Dubai: jede TopstepX-Balance-Lesung (Marc, Simon, Carsten) endete nach 2,7–3,7 s mit „Benutzer
LEER, Passwort LEER, Login-Knöpfe 0 — 2FA/Captcha auf der Seite“. Der Tab stand noch auf der Zwischenseite topstepx.com/login, die zur neuen
Anmeldung login.topstep.com („Continue with Google“) weiterleitet; der Pfad /login galt als alte Login-Seite ('alt'), und der Seitentext aus
textContent enthielt Skript-Text (reCAPTCHA) → sofort „2FA“. Geprüft (ohne Netz, ohne Chrome):
  1. tsx_login_art: /login ohne Passwortfeld/„PLATFORM LOGIN“ → 'anmeldung'; mit Formular weiter 'alt'.
  2. _tsx_google_login wartet auf der Zwischenseite (und bei leerem Blick mitten in der Weiterleitung) bis der Google-Knopf steht, drückt ihn
     GENAU EINMAL; ohne Knopf nach TSX_GOOGLE_KNOPF_S (≥ 13 s, Finn 7–13 s) kein Klick; leerer Blick heißt nie „angemeldet“.
  3. TSX_K0_BLICK_JS sucht 2FA/Fehler nur im sichtbaren Text (innerText).
Aufruf: python3 tools/selftest_tx4_topstepx_weiterleitung.py"""
import os
import re
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(W, "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


# 1) Login-Lage
la = ob.tsx_login_art
check(la({"seite": True, "pw_n": 0, "knoepfe": 0, "google_n": 0}) == "anmeldung", "/login ohne Formular (Weiterleitung) → 'anmeldung'")
check(la({"seite": True, "pw_n": 1, "knoepfe": 1, "google_n": 0}) == "alt" and la({"seite": True, "pw_n": 1}) == "alt", "/login mit Passwortfeld → 'alt' wie bisher")
check(la({"seite": True, "knoepfe": 1}) == "alt", "/login mit „PLATFORM LOGIN“ → 'alt'")
check(la({"seite": True, "google_n": 1}) == "google" and la({"signin": True}) == "anmeldung" and la({}) is None, "Google-Knopf / nur „Sign in“ / nichts wie bisher")
check(ob.TSX_GOOGLE_KNOPF_S >= 13, f"Wartezeit auf den Google-Knopf ≥ 13 s (Finn: Laden 7–13 s): {ob.TSX_GOOGLE_KNOPF_S}")

# 2) Ablauf _tsx_google_login mit falscher Uhr (nichts schläft wirklich)
GK = {"tag": "button", "text": "Continue with Google", "aria": "", "rect": [641, 574, 319, 36], "aus": False}


class Uhr:
    def __init__(self):
        self.t = 1_000_000.0

    def time(self):
        return self.t

    def sleep(self, s):
        self.t += s


class Sitzung:
    target_id = "T1"

    def __init__(self):
        self.klicks = []

    def klick(self, rect, name, pruef=None):
        self.klicks.append((list(rect), name))
        return False                       # Klick ohne Beweis → der Lauf endet sofort danach (kein Google-Fenster nötig)


def lauf(folge):
    """folge = Liste der Blicke nacheinander (der letzte bleibt stehen). -> (ergebnis, sitzung, blicke)"""
    uhr = Uhr()
    zaehler = {"n": 0}

    def blick():
        i = min(zaehler["n"], len(folge) - 1)
        zaehler["n"] += 1
        return folge[i]
    alt = {k: getattr(ob, k) for k in ("time", "_warte", "_tsx_google_sperre", "_tsx_login_tabs_zu", "_cdp_http", "_tsx_pause")}
    try:
        ob.time = uhr
        ob._warte = lambda a, b=0: uhr.sleep(a)
        ob._tsx_google_sperre = lambda grund=None: {} if grund is None else None
        ob._tsx_login_tabs_zu = lambda trail, ausser=(): 0
        ob._cdp_http = lambda pfad: []
        ob._tsx_pause = lambda *a, **k: None
        s = Sitzung()
        trail = []
        r = ob._tsx_google_login(s, trail, blick, blick())
        return r, s, zaehler["n"], uhr.t - 1_000_000.0
    finally:
        for k, v in alt.items():
            setattr(ob, k, v)


ZWISCHEN = {"seite": True, "pw_n": 0, "knoepfe": 0, "google_n": 0, "google": [], "signin": False}
NEU_OHNE = {"seite": False, "pw_n": 0, "knoepfe": 0, "google_n": 0, "google": [], "signin": True}
NEU_MIT = {"seite": False, "pw_n": 0, "knoepfe": 0, "google_n": 1, "google": [GK], "signin": True}

r, s, n, dt = lauf([ZWISCHEN, {}, ZWISCHEN, NEU_OHNE, NEU_MIT])
check(len(s.klicks) == 1 and s.klicks[0][0] == GK["rect"] and "Google" in s.klicks[0][1] and n == 5,
      f"Zwischenseite → leerer Blick → „Sign in“ ohne Knopf → Knopf: gewartet, dann GENAU EIN Klick auf „Continue with Google“ ({len(s.klicks)} Klick, {n} Blicke)")
check(isinstance(r, str) and "nicht gedrückt" in r, "Klick ohne Beweis → ehrlicher Abbruch, kein zweiter Versuch")
r, s, n, dt = lauf([ZWISCHEN])
check(not s.klicks and isinstance(r, str) and "kein Knopf" in r and dt >= 13, f"Zwischenseite bleibt: nach ≥ 13 s ({dt:.0f} s) nichts geklickt, klarer Grund")
r, s, n, dt = lauf([{}])
check(not s.klicks and r is not True and isinstance(r, str) and "nicht lesbar" in r, "nur leere Blicke: nie „angemeldet“, nichts geklickt")
r, s, n, dt = lauf([ZWISCHEN, {"seite": False, "google_n": 0, "signin": False}])
check(r is True and not s.klicks, "Weiterleitung endet angemeldet (keine Anmeldung mehr) → True, kein Klick")
r, s, n, dt = lauf([{"seite": True, "pw_n": 1, "knoepfe": 1, "google_n": 0}])
check(r is None and not s.klicks, "alte Login-Seite mit Formular → None (alter Weg), kein Klick")

# 3) JS: sichtbarer Text
js = ob.TSX_K0_BLICK_JS
check("var bt = document.body ? String(document.body.innerText || '')" in js and "var bt = document.body ? T(document.body) : '';" not in js,
      "2FA/Fehler nur aus dem sichtbaren Text (innerText), nicht aus <script>")
# Finn 25.11.: „Login with Google“ / „Continue with Google“ / „Sign in with Google“ — alle drei Texte treffen denselben einen Google-Knopf
m = re.search(r"var RX_GOOGLE = /(.*?)/i;", js)
rx = re.compile(m.group(1).replace("\\s", "\\s"), re.I) if m else None
check(bool(rx) and all(rx.search(t) for t in ("Login with Google", "Log in with Google", "Continue with Google", "Sign in with Google", "Sign in with Google Button"))
      and not any(rx.search(t) for t in ("Sign up with Google", "Continue with Facebook", "Continue to TopstepX")),
      "Google-Knopf: „Login/Log in/Continue/Sign in with Google“ ja, „Sign up with Google“/Facebook/„Continue to TopstepX“ nein")
src = open(ob.__file__, encoding="utf-8").read()
check("if not lg or tsx_login_art(lg) in (\"google\", \"anmeldung\"):" in src, "_tsx_cdp_login: leerer erster Blick geht in den wartenden Google-Weg (nie „angemeldet“)")
i = src.index("def _tsx_cdp_login(")
cl = src[i:src.index("\ndef ", i + 10)]
check("lg = blick_g()" in cl and "_tsx_google_login(s, trail, blick_g, lg)" in cl and cl.count("blick_g()") == 2
      and "    def blick():\n        b = s.lese_js(TSX_K0_BLICK_JS) or {}" in cl,
      "Prüfung: Lesefehler nur im Google-Weg geschluckt (blick_g); der alte Formular-Weg liest wie bisher (Fehler wird nie „angemeldet“)")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
