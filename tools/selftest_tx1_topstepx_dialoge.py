#!/usr/bin/env python3
"""Selbsttest TX1 „Puls klickt zwei TopstepX-Dialoge selbst weg" (Finn 17.11.2026 ~06:30 Dubai über den Master):
(1) „Time Sync Warning" → PROCEED, auch wenn TopstepX das Modal OHNE ARIA-Rolle baut (ein Topstep-PC 17.11.: viermal „Konto-Auslöser verdeckt ('Time
    Sync WarningYour computer clock is ')", TS1 sah den Dialog nie) — höchstens dreimal je Lauf.
(2) Abgemeldet → NUR „Sign in with Google"/„Continue with Google", danach höchstens das EINE angemeldete Google-Konto; Passwort, E-Mail,
    Code/2-Step, Bestätigung, abgemeldetes Konto oder mehrere Konten → Abbruch „TopstepX-Login braucht Hand (Google fragt nach …)".
(3) Beides im Lese-Weg wie im Order-Start (beide laufen durch modus_tsxlesen_cdp / _tsx_sitzung_waehlen).
Teile: A Time-Sync-Regeln + Zähler · B Google-Regeln · C Google-Ablauf mit nachgebauter Welt · D echte DOM-Schnipsel in Headless-Chrome
(augen_tsx.js stand(), TSX_K0_BLICK_JS, TSX_GOOGLE_BLICK_JS, Ziel-Beweis am Punkt) · E Bitgleich-Nachweis gegen origin/main.
Aufruf: python3 tools/selftest_tx1_topstepx_dialoge.py   (D braucht Google Chrome; ohne Chrome wird D übersprungen und gemeldet)"""
import ast
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


R = [400, 300, 90, 32]
ob._warte = lambda *a, **k: None
ob._tsx_pause = lambda *a, **k: None
ob._puls_diagnose_senden = lambda spur=None, schritt="": None
ob._pc_id_lesen = lambda: "pc-test01"

# ── A) Time Sync: Regeln + Zähler ───────────────────────────────────────────────────────────────────────────────────────────
print("── A) Time Sync Warning")
TXT = {"role": "", "quelle": "text", "titel": "Time Sync Warning",
       "text": "Time Sync WarningYour computer clock is not synchronized with the correct time. PROCEED", "knoepfe": [{"text": "PROCEED", "rect": R}]}
LEER = {"role": "dialog", "titel": "", "text": "", "knoepfe": []}
zd = ob.tsx_zeitsync_dialog
check(zd([TXT]) is TXT, "Dialog aus dem Text-Weg (ohne ARIA-Rolle) erkannt")
check(zd([LEER, TXT]) is TXT and zd([TXT, LEER, LEER]) is TXT, "leeres Popup daneben zählt nicht als zweiter Dialog")
check(zd([TXT, {"titel": "Confirm Order", "text": "Buy 1", "knoepfe": []}]) is None, "echter zweiter Dialog → nicht (wie TS1)")
check(zd([dict(TXT, text="Time Sync Warning PROCEED")]) is None, "Titel ohne den Uhr-Text → nicht (Titel UND Text)")
check(ob.tsx_popup_leer(LEER) and not ob.tsx_popup_leer(TXT) and not ob.tsx_popup_leer({"titel": "", "text": "", "knoepfe": [{"text": "x"}]}),
      "tsx_popup_leer nur ohne Titel, Text und Knopf")


class Sitzung:
    def __init__(self, staende):
        self.staende, self.klicks = list(staende), []

    def stand(self):
        return self.staende.pop(0) if self.staende else {"popups": []}

    def klick(self, rect, name, toast_ok=False, pruef=None, doppel=False):
        self.klicks.append((list(rect), name, dict(pruef or {})))
        return True


MIT, OHNE = {"popups": [TXT]}, {"popups": []}
ob._TSX_ZEITSYNC_N[0] = 0
erg = []
for i in range(4):
    s, t = Sitzung([OHNE]), []
    st, weg = ob._tsx_zeitsync_weg(s, MIT, t)
    erg.append((weg, len(s.klicks), t))
check([e[0] for e in erg[:3]] == [True, True, True] and all(e[1] == 1 for e in erg[:3]), "erstes Mal + zweimal wieder: je ein PROCEED-Druck")
check(erg[3][0] is False and erg[3][1] == 0 and any("zum 4. Mal" in x for x in erg[3][2]), "kommt er ein viertes Mal: nichts gedrückt, Abbruch wie bisher")
check(any(x.startswith("Time-Sync-Dialog weggeklickt") and "Time Sync Warning weggeklickt (" in x for x in erg[0][2]),
      "Spur „Time-Sync-Dialog weggeklickt“ (der TS1b-Schlüssel „Time Sync Warning weggeklickt (“ bleibt)")
ob._TSX_ZEITSYNC_N[0] = 0
drucke = []
for i in range(5):                                         # Dialog bleibt nach jedem PROCEED stehen („kommt immer wieder")
    s = Sitzung([MIT, MIT, MIT])
    ob._tsx_zeitsync_weg(s, MIT, [])
    drucke.append(len(s.klicks))
check(drucke == [2, 2, 2, 0, 0], f"Dialog bleibt stehen: jedes Auftauchen zählt, nach dem 3. nichts mehr ({drucke})")
ob._TSX_ZEITSYNC_N[0] = 0
src_bot =open(os.path.join(WURZEL, "mt5-copier", "order_bot.py"), encoding="utf-8").read()
check(src_bot.count("_TSX_ZEITSYNC_N[0] = 0") == 1 and src_bot.index("_TSX_ZEITSYNC_N[0] = 0") > src_bot.index("def modus_tsxlesen_cdp("),
      "Zähler wird je Lauf (modus_tsxlesen_cdp) zurückgesetzt")

# ── B) Google: Regeln ───────────────────────────────────────────────────────────────────────────────────────────────────────
print("── B) Google-Anmeldung: Regeln")
GK = {"tag": "button", "text": "Sign in with Google", "aria": "", "rect": [700, 400, 300, 44], "aus": False}
la = ob.tsx_login_art
check(la({"google_n": 1, "google": [GK], "signin": True}) == "google" and la({"google_n": 1, "seite": True}) == "google", "Google-Knopf → 'google' (auch neben altem Formular)")
check(la({"seite": True, "google_n": 0}) == "alt" and la({"signin": True}) == "anmeldung" and la({}) is None and la(None) is None,
      "alte Login-Seite → 'alt', nur „Sign in“ → 'anmeldung', sonst None")
kn, gr = ob.tsx_google_knopf({"google_n": 1, "google": [GK]})
check(kn is GK and gr == "", "genau ein Google-Knopf")
check(ob.tsx_google_knopf({"google_n": 2, "google": [GK, dict(GK, rect=[700, 460, 300, 44])]})[0] is None, "zwei Google-Knöpfe → nichts")
check(ob.tsx_google_knopf({"google_n": 0, "google": []})[0] is None and "kein Knopf" in ob.tsx_google_knopf({"google_n": 0})[1], "kein Google-Knopf → Grund")
check(ob.tsx_google_knopf({"google_n": 1, "google": [dict(GK, aus=True)]})[0] is None, "gesperrter Knopf → nichts")
p = ob.tsx_google_pruef(GK)
check(p["text"] == "google" and p["aria"] == "" and re.search(p["tabu"], "Sign up with Google", re.I) and re.search(p["tabu"], "Log out", re.I),
      "Ziel-Beweis: Wort „google“, Tabu Sign up / Log out")
p2 = ob.tsx_google_pruef(dict(GK, text="", gsi=True))
check(p2["text"] == "" and p2["aria"] == "google", "Google-iframe-Knopf: Beweis über den Titel")
kn_g, gr_g = ob.tsx_google_knopf({"google_n": 1, "google": [dict(GK, text="", gsi=True)]})
check(kn_g is None and "iframe" in gr_g, "Google-Knopf nur im iframe („Continue as …“, Konto nicht prüfbar) → nicht drücken")
L = [{"id": "T1", "type": "page", "url": "https://topstepx.com/login", "webSocketDebuggerUrl": "ws://x"},
     {"id": "G0", "type": "page", "url": "https://accounts.google.com/alt", "webSocketDebuggerUrl": "ws://x"}]
gz = ob.tsx_google_ziel
check(gz(L, "T1", ["T1", "G0"]) is None, "alte Google-Seite (vor dem Klick schon da) zählt nicht")
check((gz(L + [{"id": "G1", "type": "page", "url": "https://accounts.google.com/o/oauth2/v2/auth?x", "webSocketDebuggerUrl": "ws://y"}],
          "T1", ["T1", "G0"]) or {}).get("id") == "G1", "neues Google-Fenster → dieses")
check((gz([dict(L[0], url="https://accounts.google.com/v3/signin/accountchooser")], "T1", ["T1"]) or {}).get("id") == "T1",
      "eigener Tab auf accounts.google.com → der eigene Tab")
check(gz(L + [{"id": "G1", "type": "page", "url": "https://accounts.google.com/a", "webSocketDebuggerUrl": "ws://y"},
              {"id": "G2", "type": "page", "url": "https://accounts.google.com/b", "webSocketDebuggerUrl": "ws://z"}], "T1", ["T1", "G0"]) is None,
      "zwei neue Google-Fenster → keins (nichts raten)")
check(not ob.ist_google_konten_url("https://accounts.google.com.evil.example/x") and not ob.ist_google_konten_url("http://accounts.google.com/x")
      and ob.ist_google_konten_url("https://accounts.google.com/x"), "nur https://accounts.google.com")
GU = "https://accounts.google.com/v3/signin/accountchooser"
K1 = {"rect": [500, 300, 400, 60], "abgemeldet": False}
gu = ob.tsx_google_urteil
check(gu({"url": GU, "auswahl": True, "konten": [K1], "n": 1})["art"] == "konto", "Kontoauswahl mit EINEM Konto → klicken")
check(gu({"url": GU, "auswahl": True, "konten": [K1, dict(K1, rect=[500, 370, 400, 60])], "n": 2})["art"] == "mehrere", "zwei Konten → mehrere")
check(gu({"url": GU, "auswahl": True, "konten": [], "n": 0})["art"] == "keins", "Auswahl ohne Zeile → keins")
check(gu({"url": GU, "auswahl": True, "konten": [dict(K1, abgemeldet=True)], "n": 1})["art"] == "hand", "Konto abgemeldet → Hand")
for feld, wort in (({"pw": 1}, "Passwort"), ({"email": 1}, "E-Mail"), ({"code": True}, "Code")):
    u = gu(dict({"url": GU, "auswahl": True, "konten": [K1], "n": 1}, **feld))
    check(u["art"] == "hand" and wort in u["grund"], f"{wort}-Merkmal schlägt die Kontoauswahl → Hand ({u['grund']})")
check(gu({"url": GU, "zustimmung": True})["art"] == "hand", "Bestätigungs-Seite → Hand")
check(gu({"url": GU, "zustimmung": True, "konten": [K1], "n": 1})["art"] == "hand", "Bestätigungs-Seite mit Konto-Chip → Hand, nie den Chip")
check(gu({"url": GU, "konten": [K1], "n": 1})["art"] == "warten", "Konto-Zeile ohne „Choose an account“ → nie klicken (warten)")
check(gu({"url": "https://topstepx.com/x", "auswahl": True, "konten": [K1], "n": 1})["art"] == "warten" and gu(None)["art"] == "warten",
      "keine Google-Seite → warten (nie klicken)")
check(gu({"url": GU, "bereit": False})["art"] == "warten", "Google lädt → warten")
check(ob.tsx_google_fertig({"url": "https://topstepx.com/trade", "login": {"seite": False, "google_n": 0, "signin": False}})
      and not ob.tsx_google_fertig({"url": "https://topstepx.com/trade", "login": {"google_n": 1}})
      and not ob.tsx_google_fertig({"url": GU, "login": {}}), "fertig nur auf topstepx.com ohne Anmeldung")
check(ob.tsx_google_hand_text("Passwort").startswith("TopstepX-Login braucht Hand (Google fragt nach Passwort)"), "Abbruchtext wie bestellt")

# ── C) Google-Ablauf mit nachgebauter Welt ──────────────────────────────────────────────────────────────────────────────────
print("── C) Google-Ablauf (nachgebaut)")
ob.TSX_GOOGLE_WARTEN_S = 0.4
ob.TSX_GOOGLE_KNOPF_S = 0.2
SPEICHER = {}
ob._augen_json_lesen = lambda name: SPEICHER.get(name)
ob._augen_json_schreiben = lambda name, d: SPEICHER.__setitem__(name, d)
LOGIN = {"url": "https://topstepx.com/login", "login": {"seite": False, "google_n": 1, "google": [GK], "signin": True}}
TRADE = {"url": "https://topstepx.com/trade", "login": {"seite": False, "google_n": 0, "google": [], "signin": False}}


class Welt:
    """phase: login → (Google-Klick) google → (Konto-Klick) fertig. popup=True: Google in eigenem Fenster, sonst im selben Tab."""

    def __init__(self, google_blick, popup=True, nach_konto="fertig", auto_fertig=False, start=None):
        self.phase, self.gb, self.popup, self.nach_konto, self.auto = "login", google_blick, popup, nach_konto, auto_fertig
        self.start = start or LOGIN
        self.klicks, self.lesungen_google = [], 0

    def tsx(self):
        if self.phase == "login":
            return self.start
        if self.phase == "fertig":
            return TRADE
        return {"url": GU, "login": {}} if not self.popup else LOGIN

    def liste(self):
        t = [{"id": "T1", "type": "page", "url": self.tsx()["url"], "webSocketDebuggerUrl": "ws://t"}]
        if self.phase == "google" and self.popup:
            t.append({"id": "G1", "type": "page", "url": GU, "webSocketDebuggerUrl": "ws://g"})
        return t


class TsxSitz:
    def __init__(self, w):
        self.w, self.target_id, self.geladen = w, "T1", 0

    def lese_js(self, a, timeout=8):
        if a is ob.TSX_K0_BLICK_JS:
            return self.w.tsx()
        if a is ob.TSX_GOOGLE_BLICK_JS and not self.w.popup and self.w.phase == "google":
            return self.w.gb
        return None

    def klick(self, rect, name, pruef=None, **k):
        self.w.klicks.append((name, dict(pruef or {})))
        if self.w.phase == "login":
            self.w.phase = "fertig" if self.w.auto else "google"
        elif self.w.phase == "google":
            self.w.phase = self.w.nach_konto
        return True

    def _seite_abwarten(self, sek=25.0):
        pass

    def _augen_laden(self):
        self.geladen += 1

    def zu(self):
        pass


class GFenster(TsxSitz):
    def __init__(self, trail, ziel=None, js_datei="", tv_riegel=True, w=None):
        super().__init__(w)
        self.target_id, self.trail, self._win_hwnd = ziel.get("id"), trail, 4711

    def lese_js(self, a, timeout=8):
        return self.w.gb if a is ob.TSX_GOOGLE_BLICK_JS else None

    def klick(self, rect, name, pruef=None, **k):
        if getattr(self.w, "konto_fail", False):            # Hand schreibt den Text am Punkt mit (wie win_beweis_spur) — mit Adresse
            self.w.klicks.append((name, dict(pruef or {})))
            self.trail.append(f"{name}: am Zielpunkt liegt nicht das Ziel ('konto eins konto1@example.com') — kein Druck")
            return False
        return super().klick(rect, name, pruef=pruef, **k)

    def zu(self):
        self.w.zu_hwnd = self._win_hwnd                    # Google-Fenster: ohne „Offen bleiben"/Minimieren schließen


def google_lauf(w, sperre=None):
    SPEICHER.clear()
    if sperre:
        SPEICHER["tsx_google_login.json"] = sperre
    ob._cdp_http = lambda pfad, methode="GET", timeout=2.0: w.liste() if pfad == "/json/list" else None
    ob._AugenSitzung = lambda trail, ziel=None, js_datei="", tv_riegel=True: GFenster(trail, ziel, js_datei, tv_riegel, w=w)
    s, trail = TsxSitz(w), []
    r = ob._tsx_google_login(s, trail, lambda: (s.lese_js(ob.TSX_K0_BLICK_JS) or {}).get("login") or {}, w.start["login"])
    return r, trail, s


CH1 = {"url": GU, "bereit": True, "auswahl": True, "konten": [K1], "n": 1}
w = Welt(CH1, popup=True)
r, t, s = google_lauf(w)
check(r is True and [k[0] for k in w.klicks][0].startswith("TopstepX „Sign in with Google“") and len(w.klicks) == 2 and s.geladen == 1,
      f"Popup, ein Konto: Google-Knopf + das eine Konto, danach TopstepX geladen ({[k[0] for k in w.klicks]})")
check(w.klicks[1][1].get("text") == "@" and re.search(w.klicks[1][1]["tabu"], "Use another account", re.I), "Konto-Klick mit Ziel-Beweis „@“, nie „Use another account“")
check(not SPEICHER.get("tsx_google_login.json", {}).get("at") and any("angemeldet (über Google)" in x for x in t), "Erfolg: Sperre gelöst, Spur")
check(not any("@" in x for x in t), "keine E-Mail-Adresse in der Spur")
check(getattr(w, "zu_hwnd", "x") is None, "Google-Fenster-Sitzung ohne Fenster-Nachlauf geschlossen (Marke bleibt beim TopstepX-Fenster)")
w = Welt(CH1)
w.konto_fail = True
r, t, s = google_lauf(w)
check(isinstance(r, str) and "Klick ohne Beweis" in r and len(w.klicks) == 2 and not any("@" in x for x in t) and any("[E-Mail]" in x for x in t),
      "Konto-Klick ohne Beweis: Abbruch, die Adresse aus der Spur der Hand ist geschwärzt")
w = Welt(CH1, popup=False)
r, t, s = google_lauf(w)
check(r is True and len(w.klicks) == 2, "Weiterleitung im selben Tab: ebenso")
w = Welt(CH1, auto_fertig=True)
r, t, s = google_lauf(w)
check(r is True and len(w.klicks) == 1, "Google meldet von selbst an (keine Auswahl): nur der Google-Knopf")
for gb, wort in ((dict(CH1, konten=[K1, dict(K1, rect=[500, 370, 400, 60])], n=2), "2 Google-Konten"),
                 ({"url": GU, "bereit": True, "pw": 1}, "Passwort"), ({"url": GU, "bereit": True, "email": 1}, "E-Mail"),
                 ({"url": GU, "bereit": True, "code": True}, "Code/2-Step"), (dict(CH1, konten=[dict(K1, abgemeldet=True)]), "abgemeldet"),
                 ({"url": GU, "bereit": True, "zustimmung": True}, "Bestätigung")):
    w = Welt(gb)
    r, t, s = google_lauf(w)
    check(isinstance(r, str) and r.startswith("TopstepX-Login braucht Hand (") and wort in r and len(w.klicks) == 1
          and SPEICHER.get("tsx_google_login.json", {}).get("at"), f"{wort}: nur der Google-Knopf, Abbruch „{r[:70]}…“, Sperre gesetzt")
w = Welt(CH1, nach_konto="google")                              # Auswahl bleibt nach dem Konto-Klick stehen
r, t, s = google_lauf(w)
check(isinstance(r, str) and "nicht angemeldet" in r and len(w.klicks) == 2, "Auswahl bleibt stehen: kein zweiter Konto-Druck, Abbruch nach der Frist")
w = Welt({"url": GU, "bereit": False})
r, t, s = google_lauf(w)
check(isinstance(r, str) and "nicht angemeldet" in r and len(w.klicks) == 1, "Google bleibt leer/lädt: Abbruch nach der Frist")
w = Welt(CH1, start={"url": "https://topstepx.com/x", "login": {"seite": False, "google_n": 0, "google": [], "signin": True}})
r, t, s = google_lauf(w)
check(isinstance(r, str) and "kein Knopf „Sign in with Google“" in r and not w.klicks, "„Sign in“ ohne Google-Knopf: nichts geklickt, klarer Grund")
w = Welt(CH1, start={"url": "https://topstepx.com/x", "login": {"seite": False, "google_n": 2, "google": [GK, dict(GK, rect=[1, 1, 300, 44])], "signin": True}})
r, t, s = google_lauf(w)
check(isinstance(r, str) and "nicht eindeutig" in r and not w.klicks, "zwei Google-Knöpfe: nichts geklickt")
w = Welt(CH1, start={"url": "https://topstepx.com/login", "login": {"seite": True, "google_n": 0, "signin": True}})
r, t, s = google_lauf(w)
check(r is None and not w.klicks, "alte Login-Seite (Passwort + PLATFORM LOGIN, kein Google) → None, alter Weg bleibt")
w = Welt(CH1)
r, t, s = google_lauf(w, sperre={"at": time.time() - 120, "grund": "Passwort"})
check(isinstance(r, str) and "kein neuer Versuch" in r and not w.klicks, "Sperre (letzter Google-Versuch < 30 min ohne Erfolg): kein Klick")
w = Welt(CH1)
r, t, s = google_lauf(w, sperre={"at": time.time() - 31 * 60, "grund": "Passwort"})
check(r is True, "Sperre abgelaufen: neuer Versuch")
# _tsx_cdp_login: Weiche
w = Welt(CH1)
SPEICHER.clear()
ob._cdp_http = lambda pfad, methode="GET", timeout=2.0: w.liste() if pfad == "/json/list" else None
ob._AugenSitzung = lambda trail, ziel=None, js_datei="", tv_riegel=True: GFenster(trail, ziel, js_datei, tv_riegel, w=w)
s = TsxSitz(w)
check(ob._tsx_cdp_login(s, []) is True and len(w.klicks) == 2, "_tsx_cdp_login nimmt bei Google-Knopf den Google-Weg")
w2 = Welt(CH1, start=TRADE)
s2 = TsxSitz(w2)
check(ob._tsx_cdp_login(s2, []) is True and not w2.klicks, "_tsx_cdp_login ohne Anmeldung: True, kein Klick (wie bisher)")
check(src_bot.count("tsx_login_art(bl[\"login\"])") == 2 and "return bool(tsx_login_art(b.get(\"login\")))" in src_bot,
      "Lese-Weg und Order-Start (modus_tsxlesen_cdp nach der Bereit-Probe), Auge-Reparatur und Tab-Wahl erkennen die Google-Anmeldung")

# ── D) Echte DOM-Schnipsel in Headless-Chrome ───────────────────────────────────────────────────────────────────────────────
print("── D) DOM-Schnipsel in echtem Chrome (headless)")


def git_alt(pfad):
    try:
        return subprocess.run(["git", "-C", WURZEL, "show", "origin/main:" + pfad], capture_output=True, text=True, check=True).stdout
    except Exception:
        return None


ALT_BOT = git_alt("mt5-copier/order_bot.py")
ALT_AUGEN = git_alt("mt5-copier/augen_tsx.js")
NEU_AUGEN = open(os.path.join(WURZEL, "mt5-copier", "augen_tsx.js"), encoding="utf-8").read()


def js_konstante(src, name):
    m = re.search(name + r' = r"""(.*?)"""', src, re.S)
    return m.group(1) if m else None


ALT_BLICK = js_konstante(ALT_BOT or "", "TSX_K0_BLICK_JS")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
for kand in (CHROME, shutil.which("google-chrome") or "", shutil.which("chromium") or ""):
    if kand and os.path.exists(kand):
        CHROME = kand
        break
else:
    CHROME = None

SEITE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>%s</title><style>
body{margin:0;width:1600px;height:900px;font-family:sans-serif;background:#111;color:#ddd}
.kopf{position:absolute;left:10px;top:10px;width:600px;height:40px}
.schleier{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:1000;display:flex;align-items:center;justify-content:center}
.box{width:450px;padding:24px;background:#1e2229;border:1px solid #333}
.knopf{display:block;width:400px;height:36px;margin-top:20px;border:1px solid #c9a227;color:#c9a227;background:none;text-align:center;line-height:36px;cursor:pointer}
.g{display:flex;gap:8px;align-items:center;width:320px;height:44px;margin:12px auto;border:1px solid #888;background:#fff;color:#000;cursor:pointer}
li{list-style:none} .konto{display:block;width:420px;height:56px;margin:4px 0;cursor:pointer}
</style></head><body>%s</body></html>"""
TRADE_BODY = ('<div class="kopf"><button data-testid="account-selector" aria-expanded="false">$150K Express | EXPRESS-V2-000000-00000000</button></div>'
              '<div style="position:absolute;left:10px;top:60px">BAL: $150,000.00 MLL: $145,500.00</div>'
              '<div data-testid="order-card-container" style="position:absolute;right:10px;top:100px;width:300px;height:400px">'
              '<div>No Active Position</div><button data-testid="order-card-click-button-close-position" disabled>Close Position</button></div>')
TS_BOX = ('<div class="schleier"><div class="box"><div style="font-size:18px">Time Sync Warning</div>'
          '<div style="margin-top:12px">Your computer clock is not synchronized with the correct time. This may affect your trading accuracy. '
          'Please update your system clock to match the current time.</div>%s</div></div>')
F = {
    # Time Sync Warning wie auf Finns Bild: eigenes Modal OHNE role/aria-modal, ein Knopf PROCEED
    "ts_ohne_rolle": ("TopstepX", TRADE_BODY + TS_BOX % '<button class="knopf">PROCEED</button>'),
    "ts_div_knopf": ("TopstepX", TRADE_BODY + TS_BOX % '<div class="knopf">PROCEED</div>'),
    "ts_mui": ("TopstepX", TRADE_BODY + '<div role="presentation" class="schleier"><div role="dialog" class="box"><h2>Time Sync Warning</h2>'
               '<p>Your computer clock is not synchronized with the correct time.</p><button class="knopf">PROCEED</button></div></div>'),
    "ts_zwei_knoepfe": ("TopstepX", TRADE_BODY + TS_BOX % '<button class="knopf">PROCEED</button><button class="knopf">Proceed</button>'),
    "ts_ohne_uhrtext": ("TopstepX", TRADE_BODY + '<div class="schleier"><div class="box"><div>Time Sync Warning</div><button class="knopf">PROCEED</button></div></div>'),
    "ts_mit_leerem": ("TopstepX", TRADE_BODY + '<div role="dialog" style="position:fixed;left:0;top:0;width:20px;height:20px"></div>'
                      + TS_BOX % '<button class="knopf">PROCEED</button>'),
    "trade": ("MNQZ26 $27,369.75 ▲ +0.31%", TRADE_BODY),
    "trade_bracket": ("TopstepX", TRADE_BODY + '<div role="dialog" class="box" style="position:fixed;left:500px;top:200px"><h2>Position Brackets</h2>'
                      '<button aria-label="close">x</button></div>'),
    # Anmeldung
    "login_google": ("Topstep | Sign in", '<div class="box" style="margin:100px auto"><h1>Sign in</h1>'
                     '<button class="g"><img alt="" width="18" height="18">Sign in with Google</button>'
                     '<button class="g">Sign in with Apple</button><a href="#" style="display:block">Sign up with Google</a></div>'),
    "login_dialog": ("TopstepX", TRADE_BODY + '<div role="dialog" class="schleier"><div class="box"><h2>Sign In</h2><p>Your session has expired.</p>'
                     '<div role="button" class="g" tabindex="0"><span>Continue with Google</span></div></div></div>'),
    "login_gsi": ("Topstep | Sign in", '<div class="box" style="margin:100px auto"><h1>Sign in</h1>'
                  '<iframe title="Sign in with Google Button" style="width:300px;height:44px;border:0;display:block"></iframe></div>'),
    "login_ohne_google": ("Topstep | Sign in", '<div class="box" style="margin:100px auto"><h1>Sign in</h1><button class="g">Sign in</button></div>'),
    "login_nur_signup": ("Topstep | Sign up", '<div class="box" style="margin:100px auto"><button class="g">Sign up with Google</button></div>'),
    "login_alt": ("TopstepX", '<form class="box" style="margin:100px auto"><input type="text" name="u"><input type="password" name="p">'
                  '<button type="button" class="g">PLATFORM LOGIN</button></form>'),
    # Google
    "g_eins": ("Sign in - Google Accounts", '<h1>Choose an account</h1><p>to continue to Topstep</p><ul>'
               '<li><div role="link" class="konto" tabindex="0" data-identifier="konto1@example.com"><div>Konto Eins</div><div>konto1@example.com</div></div></li>'
               '<li><div role="link" class="konto" tabindex="0"><div>Use another account</div></div></li></ul>'),
    "g_zwei": ("Sign in - Google Accounts", '<h1>Choose an account</h1><ul>'
               '<li><div role="link" class="konto" tabindex="0" data-identifier="konto1@example.com">Konto Eins konto1@example.com</div></li>'
               '<li><div role="link" class="konto" tabindex="0" data-identifier="konto2@example.com">Konto Zwei konto2@example.com</div></li>'
               '<li><div role="link" class="konto" tabindex="0">Use another account</div></li></ul>'),
    "g_text": ("Sign in - Google Accounts", '<h1>Konto auswählen</h1><ul><li><div role="link" class="konto" tabindex="0">Konto Eins konto1@example.com</div></li>'
               '<li><div role="link" class="konto" tabindex="0">Anderes Konto verwenden</div></li></ul>'),
    "g_abgemeldet": ("Sign in - Google Accounts", '<h1>Choose an account</h1><ul><li><div role="link" class="konto" tabindex="0" '
                     'data-identifier="konto1@example.com">Konto Eins konto1@example.com Signed out</div></li></ul>'),
    "g_passwort": ("Sign in - Google Accounts", '<h1>Welcome</h1><p>konto1@example.com</p><input type="password" name="Passwd"><button>Next</button>'),
    "g_email": ("Sign in - Google Accounts", '<h1>Sign in</h1><input type="email" name="identifier"><button>Next</button>'),
    "g_2step": ("Sign in - Google Accounts", '<h1>2-Step Verification</h1><p>Check your phone</p><button>Try another way</button>'),
    "g_zustimmung": ("Sign in - Google Accounts", '<h1>Sign in to Topstep</h1><div role="button" data-email="konto1@example.com">konto1@example.com</div>'
                     '<p>Google will allow Topstep to access this info about you</p><button>Cancel</button><button>Continue</button>'),
    "g_unten": ("Sign in - Google Accounts", '<h1>Choose an account</h1><ul>'
                '<li><div role="link" class="konto" tabindex="0" data-identifier="konto1@example.com">Konto Eins konto1@example.com</div></li>'
                '<li style="margin-top:1400px"><div role="link" class="konto" tabindex="0" data-identifier="konto2@example.com">Konto Zwei konto2@example.com</div></li></ul>'),
}


class Chrome:
    def __init__(self):
        self.port = 9477
        self.dir = tempfile.mkdtemp(prefix="tx1-chrome-")
        self.p = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={self.port}", f"--user-data-dir={self.dir}",
                                   "--no-first-run", "--no-default-browser-check", "--window-size=1600,900", "about:blank"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ende, ws = time.time() + 20, None
        while time.time() < ende and not ws:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=1) as r:
                    ws = [x for x in json.loads(r.read()) if x.get("type") == "page"][0]["webSocketDebuggerUrl"]
            except Exception:
                time.sleep(0.3)
        if not ws:
            raise RuntimeError("Chrome antwortet nicht")
        alt = ob.cdp_ws_url_pruefen
        ob.cdp_ws_url_pruefen = lambda url, port=None: alt(url, port=self.port)
        self.v = ob._CdpVerbindung(ws, timeout=15.0)

    def laden(self, titel, body):
        html = SEITE % (titel, body)
        self.v.rufe("Page.navigate", {"url": "data:text/html;charset=utf-8," + urllib.parse.quote(html)}, timeout=15)
        for _ in range(50):
            if self.js("document.readyState") == "complete" and self.js("document.title") == titel:
                break
            time.sleep(0.1)

    def js(self, a):
        r = self.v.rufe("Runtime.evaluate", {"expression": a, "returnByValue": True, "awaitPromise": True}, timeout=15)
        if r.get("exceptionDetails"):
            raise RuntimeError(json.dumps(r["exceptionDetails"])[:300])
        return (r.get("result") or {}).get("value")

    def stand(self, quelle):
        self.js(quelle)
        return self.js("globalThis.prophosAugen.stand({})")

    def ziel(self, rect, pruef):
        x, y = rect[0] + rect[2] / 2, rect[1] + rect[3] / 2
        self.v.rufe("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "buttons": 0}, timeout=5)
        time.sleep(0.15)
        return self.js(ob.win_ziel_pruef_js(x, y, pruef)) or {}

    def zu(self):
        try:
            self.v.zu()
        finally:
            self.p.terminate()
            try:
                self.p.wait(5)
            except Exception:
                self.p.kill()
            shutil.rmtree(self.dir, ignore_errors=True)


def ohne(d, *weg):
    d = json.loads(json.dumps(d))
    for k in ("ts", "v"):
        d.pop(k, None)
    for k in weg:
        d.pop(k, None)
    return d


if not CHROME:
    print("(D übersprungen: kein Google Chrome gefunden)")
    FEHLER.append("D nicht gelaufen (kein Chrome)")
else:
    c = Chrome()
    try:
        # Time Sync
        c.laden(*F["ts_ohne_rolle"])
        st = c.stand(NEU_AUGEN)
        pp = st.get("popups") or []
        dlg = ob.tsx_zeitsync_dialog(pp)
        kn = ob.tsx_zeitsync_knopf(dlg) if dlg else None
        check(st.get("v") == "tsx-0.7.3" and len(pp) == 1 and pp[0].get("quelle") == "text" and pp[0].get("titel") == "Time Sync Warning"
              and dlg and kn and kn["text"] == "PROCEED", f"Modal OHNE ARIA-Rolle (Finns Bild): Popup aus dem Text-Weg, PROCEED gefunden ({pp[:1]})")
        alt_pp = (c.stand(ALT_AUGEN).get("popups") or []) if ALT_AUGEN else None
        check(alt_pp == [], "Gegenprobe: die alte augen_tsx.js (origin/main) sah dieses Modal NICHT — die Ursache der Fehlstarts am 17.11.")
        if kn:
            pr = {"rect": kn["rect"], "text": "PROCEED", "aria": "", "tabu": ob.TSX_DIALOG_TABU, "wort": "proceed"}
            v = c.ziel(kn["rect"], pr)
            check(v.get("hover") and v.get("passt"), f"Ziel-Beweis am PROCEED-Punkt passt (hover + passt) ({v.get('was')})")
        c.laden(*F["ts_div_knopf"])
        pp = c.stand(NEU_AUGEN).get("popups") or []
        check(len(pp) == 1 and ob.tsx_zeitsync_knopf(ob.tsx_zeitsync_dialog(pp) or {}), "PROCEED als div (kein button) → genau ein Knopf")
        c.laden(*F["ts_mui"])
        pp = c.stand(NEU_AUGEN).get("popups") or []
        check(len(pp) == 1 and pp[0].get("role") == "dialog" and not pp[0].get("quelle") and ob.tsx_zeitsync_dialog(pp),
              "ARIA-Dialog (wie TS1 erwartet): genau EIN Popup, kein Doppel aus dem Text-Weg")
        c.laden(*F["ts_zwei_knoepfe"])
        check((c.stand(NEU_AUGEN).get("popups") or []) == [], "zwei PROCEED-Knöpfe → kein Popup aus dem Text-Weg (nichts raten)")
        c.laden(*F["ts_ohne_uhrtext"])
        check((c.stand(NEU_AUGEN).get("popups") or []) == [], "Titel ohne den Uhr-Text → kein Popup aus dem Text-Weg")
        c.laden(*F["ts_mit_leerem"])
        pp = c.stand(NEU_AUGEN).get("popups") or []
        check(len(pp) == 2 and ob.tsx_zeitsync_dialog(pp) is not None, "leerer role=dialog daneben + Modal ohne Rolle → trotzdem erkannt")
        # Bitgleich ohne Time-Sync: stand() alt == neu (bis auf v/ts)
        for name in ("trade", "trade_bracket", "login_google", "login_alt"):
            c.laden(*F[name])
            a, n = c.stand(ALT_AUGEN), c.stand(NEU_AUGEN)
            check(ALT_AUGEN and ohne(a) == ohne(n), f"stand() ohne Time-Sync-Dialog bitgleich zu origin/main ({name})")
        # Anmeldung: TSX_K0_BLICK_JS
        erwart = {"login_google": ("google", 1), "login_dialog": ("google", 1), "login_gsi": ("google", 1), "login_ohne_google": ("anmeldung", 0),
                  "login_nur_signup": (None, 0), "login_alt": ("alt", 0), "trade": (None, 0), "trade_bracket": (None, 0), "ts_ohne_rolle": (None, 0)}
        for name, (art, n) in erwart.items():
            c.laden(*F[name])
            b = c.js(ob.TSX_K0_BLICK_JS) or {}
            lg = b.get("login") or {}
            check(ob.tsx_login_art(lg) == art and lg.get("google_n") == n, f"Login-Lage {name}: {ob.tsx_login_art(lg)} / Google-Knöpfe {lg.get('google_n')}")
            if ALT_BLICK:
                a = c.js(ALT_BLICK) or {}
                nb = json.loads(json.dumps(b))
                for k in ("google", "google_n", "signin"):
                    (nb.get("login") or {}).pop(k, None)
                check(a == nb, f"TSX_K0_BLICK_JS {name}: alle alten Schlüssel bitgleich, nur google/google_n/signin neu")
            if name == "login_gsi":
                check(ob.tsx_google_knopf(lg)[0] is None, "Google-iframe-Knopf erkannt, aber nicht gedrückt (Grund: Konto nicht prüfbar)")
            elif art == "google":
                kn, _g = ob.tsx_google_knopf(lg)
                v = c.ziel(kn["rect"], ob.tsx_google_pruef(kn)) if kn else {}
                check(kn and v.get("hover") and v.get("passt"), f"Ziel-Beweis am Google-Knopf ({name}) passt ({v.get('was')})")
        # Google-Seiten: TSX_GOOGLE_BLICK_JS
        erwart_g = {"g_eins": "konto", "g_text": "konto", "g_zwei": "mehrere", "g_abgemeldet": "hand", "g_passwort": "hand",
                    "g_email": "hand", "g_2step": "hand", "g_zustimmung": "hand", "g_unten": "mehrere"}
        for name, art in erwart_g.items():
            c.laden(*F[name])
            gb = c.js(ob.TSX_GOOGLE_BLICK_JS) or {}
            check("@" not in json.dumps(gb.get("konten")), f"{name}: keine Adresse im Blick")
            gb["url"] = GU                                   # Schnipsel liegt auf data:, das Urteil verlangt accounts.google.com
            u = ob.tsx_google_urteil(gb)
            check(u["art"] == art, f"Google {name}: {u['art']} ({u['grund']})")
            if name == "g_eins":
                r_ = u["konto"]["rect"]
                v = c.ziel(r_, {"rect": r_, "text": "@", "aria": "", "tabu": ob.TSX_GOOGLE_KONTO_TABU})
                check(v.get("hover") and v.get("passt"), "Ziel-Beweis an der einen Konto-Zeile passt")
                anders = c.js("(function(){var e=[].slice.call(document.querySelectorAll('[role=link]')).filter(function(x){return /another/i.test(x.textContent)})[0];"
                              "var r=e.getBoundingClientRect();return [r.left,r.top,r.width,r.height];})()")
                v2 = c.ziel(anders, {"rect": anders, "text": "@", "aria": "", "tabu": ob.TSX_GOOGLE_KONTO_TABU})
                check(not v2.get("passt"), "„Use another account“ besteht den Ziel-Beweis nie")
    finally:
        c.zu()

# ── E) Bitgleich: Order-Klickpfad ohne Dialog unverändert ───────────────────────────────────────────────────────────────────
print("── E) Bitgleich gegen origin/main")
if not ALT_BOT:
    print("(E übersprungen: origin/main nicht lesbar)")
    FEHLER.append("E nicht gelaufen")
else:
    def defs(src):
        baum, out = ast.parse(src), {}
        zeilen = src.splitlines()
        for k in baum.body:
            if isinstance(k, (ast.FunctionDef, ast.ClassDef)):
                out[k.name] = "\n".join(zeilen[k.lineno - 1 - len(k.decorator_list):k.end_lineno])
        return out
    alt_d, neu_d = defs(ALT_BOT), defs(src_bot)
    GEAENDERT = {"tsx_zeitsync_dialog", "_tsx_zeitsync_weg", "_tsx_cdp_login", "_tsx_sitzung_waehlen", "_tsx_auge_konto", "modus_tsxlesen_cdp"}
    anders = sorted(n for n in alt_d if n not in GEAENDERT and alt_d[n] != neu_d.get(n))
    check(not anders, f"alle übrigen {len(alt_d) - len(GEAENDERT)} Funktionen/Klassen bitgleich, auch _AugenSitzung, _tsx_konto_sichern, _tsx_k3_probe, "
                      f"_tsx_k4_senden, tsx_k3_vor_klick, _tsx_blow_dialog_weg ({anders[:6]})")
    weg_erlaubt = {
        "_tsx_zeitsync_weg": 1,          # alte Spurzeile (jetzt mit „Time-Sync-Dialog weggeklickt" davor)
        "_tsx_cdp_login": 0,             # nur die Google-Weiche davor
        "_tsx_sitzung_waehlen": 1,       # login_seite: seite → tsx_login_art
        "_tsx_auge_konto": 1,            # Bedingung nach der Bereit-Probe
        "modus_tsxlesen_cdp": 1,         # Bedingung nach der Bereit-Probe (Lesen + Order-Start)
    }
    for name, n_erlaubt in weg_erlaubt.items():
        d = [x for x in difflib.unified_diff(alt_d[name].splitlines(), neu_d[name].splitlines(), lineterm="", n=0)
             if x.startswith("-") and not x.startswith("---")]
        check(len(d) == n_erlaubt, f"{name}: genau {n_erlaubt} alte Zeile(n) ersetzt, sonst nur Neues ({[x[:90] for x in d]})")
    ab = [x for x in difflib.unified_diff(js_konstante(ALT_BOT, "TSX_K0_BLICK_JS").splitlines(), js_konstante(src_bot, "TSX_K0_BLICK_JS").splitlines(),
                                          lineterm="", n=0) if x.startswith("-") and not x.startswith("---")]
    check(not ab, "TSX_K0_BLICK_JS: nur Zeilen dazu, keine alte Zeile geändert")
    ab = [x for x in difflib.unified_diff(ALT_AUGEN.splitlines(), NEU_AUGEN.splitlines(), lineterm="", n=0) if x.startswith("-") and not x.startswith("---")]
    check(len(ab) == 1 and "var VERSION = 'tsx-0.7.2'" in ab[0], f"augen_tsx.js: nur VERSION geändert, sonst nur Neues ({[x[:60] for x in ab]})")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER: {FEHLER}")
sys.exit(1 if FEHLER else 0)
