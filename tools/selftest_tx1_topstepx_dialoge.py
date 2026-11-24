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

# ── A2) Überlagerungen ohne Order-Bezug (TX1b) ──────────────────────────────────────────────────────────────────────────────
print("── A2) Werbe-Popup / Dialog ohne Text")
X = {"text": "", "aria": "Close Message", "rect": [990, 700, 24, 24]}
WERB = {"role": "dialog", "cls": "ab-iam-root", "rect": [1060, 660, 520, 220], "titel": "", "text": "", "knoepfe": [X],
        "leer": {"bilder": 1, "links": 1, "elemente": 5, "iframes": []}}
WERB_T = {"role": "dialog", "cls": "promo", "rect": [1060, 660, 520, 220], "titel": "Give 50% Off Get 50% Off",
          "text": "Give 50% Off Get 50% Off Everybody Eats This Friendsgiving! Share your referral code", "knoepfe": [{"text": "×", "rect": [990, 700, 24, 24]}]}
ul, uk = ob.tsx_ueberlagerung, ob.tsx_ueberlagerung_knopf
check((ul(WERB) or {}).get("art") == "leer" and (ul(WERB_T) or {}).get("art") == "werbung", "ohne Text → 'leer', Werbe-Wörter → 'werbung'")
for t_ in ("Confirm Order", "Buy 3 MNQ", "You hit your Maximum Loss Limit", "Sign in", "Are you sure?", "Position Brackets", "Account settings"):
    check(ul(dict(WERB_T, titel=t_, text=t_ + " 50% off")) is None, f"Order-/Konto-/Login-Bezug „{t_}“ → nie eine Überlagerung")
check(ul(dict(WERB, knoepfe=[X, {"text": "Buy", "rect": R}])) is None, "Knopf mit Order-Wort im Popup → keine Überlagerung")
check(ul({"titel": "Settings", "text": "Chart settings saved", "knoepfe": []}) is None, "unbekannter Dialog mit Text → bleibt (wie bisher)")
check(ul(TXT) is None, "Time Sync nie hier (eigener Weg)")
k_ = uk(WERB)
check(k_ and k_["aus_aria"] and k_["text"] == "Close Message", "X nur mit aria „Close Message“ → Schließ-Knopf")
check(uk(dict(WERB, knoepfe=[{"text": "Get Your Code →", "rect": R}, X]))["text"] == "Close Message", "„Get Your Code“ zählt nie, das X schon")
check(uk(dict(WERB, knoepfe=[{"text": "Get Your Code", "rect": R}])) is None and uk(dict(WERB, knoepfe=[{"text": "Upgrade now", "rect": R}])) is None,
      "nur Link-/Kauf-Knöpfe → kein Schließ-Knopf")
check(uk(dict(WERB, knoepfe=[{"text": "", "aria": "", "icon": "CloseIcon", "rect": R}]))["icon_x"], "Symbol-X ohne Text/aria (CloseIcon)")
check(uk(dict(WERB, knoepfe=[{"text": "", "icon": "CloseIcon", "rect": R}, {"text": "", "icon": "CloseIcon", "rect": [1, 1, 20, 20]}])) is None,
      "zwei namenlose X → nichts")
check(uk(dict(WERB, knoepfe=[{"text": "×", "rect": R}, {"text": "", "aria": "Close Message", "rect": [1, 1, 20, 20]}])) is None,
      "verschiedene Schließ-Wörter (× und Close Message) → nichts")
check(uk(dict(WERB, knoepfe=[{"text": "OK", "rect": R}])) is None and uk(dict(WERB, knoepfe=[{"text": "Okay", "rect": R}])) is None,
      "„OK“ zählt nie (Zustimmung: Update neu laden, Cookies, Bedingungen)")
check((uk(dict(WERB, knoepfe=[{"text": "OK", "rect": R}, X])) or {}).get("text") == "Close Message", "„OK“ + X → das X")
check((uk(dict(WERB, knoepfe=[{"text": "Got it", "rect": R}, X])) or {}).get("text") == "Close Message", "„Got it“ + X → das X (X geht vor)")
check((uk(dict(WERB, knoepfe=[{"text": "Got it", "rect": R}])) or {}).get("text") == "Got it", "„Got it“ als EINZIGER Knopf → der")
check(uk(dict(WERB, knoepfe=[{"text": "Got it", "rect": R}, {"text": "Learn more", "rect": [1, 1, 80, 20]}])) is None,
      "„Got it“ neben einem anderen Knopf → nichts")
for t_ in ("Announcement: scheduled maintenance tonight", "What's new: CME early close 12:00 CT", "Update available — reload the page",
           "We use cookies. Accept all?", "Promo! Positions will be liquidated"):
    check(ul(dict(WERB_T, titel="", text=t_, knoepfe=[X])) is None, f"Warnung im Gewand eines Hinweises bleibt: „{t_}“")
check(ul(dict(WERB_T, titel="Announcement", text="Give 50% Off " + "x " * 80, text_voll="Give 50% Off " + "x " * 80 + "open orders will be cancelled",
              knoepfe=[X])) is None, "Warnwort erst hinter Zeichen 160 (text_voll) → bleibt")
check(ob.tsx_dialog_offen_text([{"titel": "Position Brackets", "text": "x"}]) == "Dialog offen ('Position Brackets')", "Dialog mit Titel: Text wie bisher")
check(ob.tsx_dialog_offen_text([WERB]).startswith("Dialog ohne Text offen (ohne Text · Klasse ab-iam-root · Rolle dialog · Lage [1060, 660, 520, 220]"),
      "Dialog ohne Text: Klasse, Rolle, Lage")
check(ob.tsx_dialog_offen_text([WERB_T]).startswith("TopstepX-Werbe-Popup offen ("), "Werbe-Popup: klarer Grund")
check("ohne Text · Klasse ab-iam-root" in ob._tsx_k4_dialog_name({"popups": [WERB]}) and ob._tsx_k4_dialog_name({"popups": [{"titel": "Abc"}]}) == "Abc",
      "Bracket-Schritt: Dialog ohne Text nennt Klasse/Lage, sonst wie bisher")


def ueber_lauf(st0, staende, klick_ok=True):
    ob._TSX_UEBER_N[0] = 0
    s = Sitzung(staende)
    s.klick_ok = klick_ok
    s.klick = lambda rect, name, toast_ok=False, pruef=None, doppel=False: (s.klicks.append((list(rect), name, dict(pruef or {}))), klick_ok)[1]
    t = []
    st, grund = ob._tsx_ueberlagerung_weg(s, st0, t)
    return s, t, grund


s, t, g = ueber_lauf({"popups": [WERB]}, [{"popups": []}])
check(g is None and len(s.klicks) == 1 and s.klicks[0][2].get("aria") == "Close Message" and re.search(s.klicks[0][2]["tabu"], "Get Your Code", re.I)
      and any(x.startswith("Überlagerung weggeklickt: Dialog ohne Text ohne Text · Klasse ab-iam-root") and "Lage [" in x for x in t),
      "X gedrückt (Ziel-Beweis aria, Tabu „Get“/„Code“), Spur mit Klasse und Lage")
s, t, g = ueber_lauf({"popups": [WERB_T]}, [{"popups": []}])
check(g is None and s.klicks[0][2].get("wort") == "×" and any("TopstepX-Werbe-Popup 'Give 50% Off" in x for x in t), "Werbe-Popup mit Text: × gedrückt, Text-Auszug in der Spur")
s, t, g = ueber_lauf({"popups": [dict(WERB, knoepfe=[])]}, [])
check(not s.klicks and g and "kein eindeutiger Schließen-Knopf" in g and "Klasse ab-iam-root" in g, "kein X → nichts gedrückt, Grund mit Klasse")
GERUEST = {"role": "dialog", "cls": "leer", "rect": [0, 0, 20, 20], "titel": "", "text": "", "knoepfe": []}
s, t, g = ueber_lauf({"popups": [GERUEST, WERB]}, [{"popups": [GERUEST]}])
check(len(s.klicks) == 1 and s.klicks[0][2].get("aria") == "Close Message" and g and "kein eindeutiger" in g,
      "leeres Gerüst vor der Werbung: die Werbung mit X wird geschlossen, das Gerüst bleibt mit Grund")
pr_ = (ueber_lauf({"popups": [WERB]}, [{"popups": []}])[0].klicks or [[None, None, {}]])[0][2].get("tabu") or "x^"
check(all(re.search(pr_, w_, re.I) for w_ in ("Cancel", "Flatten", "Get Your Code", "Upgrade", "Place order")), "Ziel-Beweis-Tabu: Knopf-Tabu + Order-Tabu")
s, t, g = ueber_lauf({"popups": [WERB]}, [{"popups": [WERB]}, {"popups": [WERB]}])
check(len(s.klicks) == 2 and g and "steht nach dem Druck" in g, "bleibt stehen → höchstens 2 Drücke je Aufruf, dann Grund")
s, t, g = ueber_lauf({"popups": [{"titel": "Confirm Order", "text": "Buy 3", "knoepfe": [{"text": "Close", "rect": R}]}]}, [])
check(not s.klicks and g is None, "Order-Dialog: nichts gedrückt (bleibt für die Vorprüfung)")
# TX1c (Prüfer S2): Dialog-Bindung im Beweis + harter Riegel über Order-/Positions-Flächen
s, t, g = ueber_lauf({"popups": [WERB]}, [{"popups": []}])
check(s.klicks and s.klicks[0][2].get("dialog") == WERB["rect"], "Ziel-Beweis trägt das Popup-Rechteck (Dialog-Bindung)")
GITTER = {"da": True, "rect": [900, 640, 700, 200], "zeilen": [{"symbol": "MNQZ26", "menge": 3, "rect": [900, 680, 700, 30], "close_rect": [985, 690, 24, 24]}]}
ST_OFFEN = {"popups": [WERB], "flach": False, "ticket": {"gitter": GITTER}}
s, t, g = ueber_lauf(ST_OFFEN, [])
check(not s.klicks and g and "Close-Kreuz einer Positionszeile" in g, f"Position offen, X über dem Close-Kreuz → kein Druck, klarer Grund ({g})")
sz = ob.tsx_ueberlagerung_sperrzone
check(sz([1300, 650, 24, 24], ST_OFFEN) == "dem Positions-/Orders-Dock", "X über dem Dock bei offener Position → gesperrt")
check(sz([1300, 650, 24, 24], {"flach": True, "ticket": {"gitter": dict(GITTER, zeilen=[])}}) is None, "flach bewiesen, keine Zeile → Dock frei")
check(sz([1300, 650, 24, 24], {"ticket": {"gitter": dict(GITTER, zeilen=[])}}) == "dem Positions-/Orders-Dock", "flach NICHT bewiesen → Dock gesperrt")
check(sz([100, 100, 24, 24], {"flach": True, "ticket": {"kauf": {"rect": [110, 105, 120, 40]}}}) == "dem Kauf-Knopf", "nie neben Kauf/Verkauf (auch flach)")
check(sz([100, 100, 24, 24], ST_OFFEN) is None and not ob._tsx_rect_schnitt([0, 0, 10, 10], [17, 0, 10, 10]) and ob._tsx_rect_schnitt([0, 0, 10, 10], [15, 0, 10, 10]),
      "weit weg frei, Rand ± 6 px")
# TX1d HubSpot-CTA (X im fremden iframe) → ausblenden, kein Klick
HS = {"role": "dialog", "cls": "go1222083472 go3508454897 hs-cta-embed__loaded go3", "rect": [1785, 893, 400, 198], "titel": "", "text": "", "knoepfe": [],
      "leer": {"bilder": 0, "links": 0, "elemente": 1, "iframes": [{"src": "https://topsteptrader-0000000.hs-sites.com/cta/abc", "titel": "", "rect": [1785, 893, 400, 198]}]}}
hw = ob.tsx_hubspot_werbung
check(hw(HS), "HubSpot-CTA aus der Spur vom 17.11. erkannt")
check(not hw(dict(HS, cls="go3 promo")) and not hw(dict(HS, text="x")) and not hw(dict(HS, knoepfe=[X])), "ohne hs-cta-embed / mit Text / mit Knopf → nicht")
check(not hw(dict(HS, leer=dict(HS["leer"], iframes=[{"src": "https://evil.example/hs-sites.com/x"}])))
      and not hw(dict(HS, leer=dict(HS["leer"], iframes=[{"src": "https://x.hs-sites.com.evil.example/"}])))
      and not hw(dict(HS, leer=dict(HS["leer"], iframes=[]))) and not hw(dict(HS, leer=dict(HS["leer"], links=1))),
      "iframe nicht von HubSpot / keins / Link daneben → nicht")


class HsSitz(Sitzung):
    def __init__(self, staende, antwort):
        super().__init__(staende)
        self.antwort, self.js = antwort, []

    def lese_js(self, a, timeout=8):
        self.js.append(a)
        return self.antwort


ob._TSX_UEBER_N[0] = 0
s = HsSitz([{"popups": []}], {"versteckt": 1})
t = []
st_, g = ob._tsx_ueberlagerung_weg(s, {"popups": [HS]}, t)
check(g is None and not s.klicks and len(s.js) == 1 and "display','none'" in s.js[0] and any(x.startswith("HubSpot-Werbung ausgeblendet (kein Klick)") for x in t),
      "HubSpot-CTA: ausgeblendet, KEIN Klick, Spur „HubSpot-Werbung ausgeblendet“")
s = HsSitz([], {"versteckt": 0, "grund": "iframe nicht von HubSpot"})
st_, g = ob._tsx_ueberlagerung_weg(s, {"popups": [HS]}, [])
check(g and "nicht ausgeblendet (iframe nicht von HubSpot)" in g and not s.klicks, "JS lehnt ab → Grund, nichts geklickt")
s = HsSitz([{"popups": [HS]}], {"versteckt": 1})
st_, g = ob._tsx_ueberlagerung_weg(s, {"popups": [HS]}, [])
check(g and "wieder da" in g, "kommt nach dem Ausblenden wieder → Grund")
s = HsSitz([{"popups": []}], {"versteckt": 1})
st_, g = ob._tsx_ueberlagerung_weg(s, {"popups": [WERB]}, [])
check(s.klicks and not s.js, "normales Werbe-Popup mit X: weiter der Klickweg (Ausblenden nur für HubSpot)")
ob._TSX_UEBER_N[0] = ob.TSX_UEBER_MAX
s = Sitzung([])
st_, g = ob._tsx_ueberlagerung_weg(s, {"popups": [WERB]}, [])
check(not s.klicks and g and "schon 4×" in g, "je Lauf höchstens 4 Überlagerungen, danach Grund")
ob._TSX_UEBER_N[0] = 0
# CF1 (23.11.2026): vierte Stelle — Contract-Feld ohne Klick-Beweis räumt Überlagerungen weg und klickt EINMAL neu (selftest_cf1_contract_feld.py)
check(src_bot.count("_TSX_UEBER_N[0] = 0") == 1 and src_bot.count("st, _ug = _tsx_ueberlagerung_weg(s, st, trail)") == 4,
      "vier Stellen: Start (Lesen + Order), vor dem Order-Klick, Bracket-Schritt, Contract-Feld (CF1); Zähler je Lauf")

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


# Bitgleich gegen den FESTEN Stand vor TX1 (main vor 2ffb0f7e, live .2245 enthält TX1–TX1c) — wie SB1c; TX1d prüft E2 zusätzlich gegen origin/main
BASIS = "2ffb0f7e~1"


def git_alt(pfad, ref=BASIS):
    try:
        return subprocess.run(["git", "-C", WURZEL, "show", f"{ref}:{pfad}"], capture_output=True, text=True, check=True).stdout
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
    # TX1b Werbe-Popup unten rechts (Finns Bild): Grafik mit Link, X nur als Symbol mit aria-label
    "werbung_grafik": ("TopstepX", TRADE_BODY + '<div role="dialog" aria-modal="true" class="ab-iam-root promo-x" style="position:fixed;right:20px;bottom:20px;'
                       'width:520px;height:220px;background:#222"><a class="promo" href="#code" style="position:absolute;left:10px;top:10px;width:400px;height:200px">'
                       '<img alt="" width="400" height="200"></a><button aria-label="Close Message" class="ab-close-button" style="position:absolute;right:6px;top:6px;'
                       'width:24px;height:24px"><svg width="14" height="14"><path d="M1 1l12 12M13 1L1 13" stroke="#fff"/></svg></button></div>'),
    # TX1d: HubSpot-CTA-Embed wie in der Spur vom 17.11. — role=dialog, Klasse hs-cta-embed__loaded, darin NUR ein fremdes iframe (hs-sites.com)
    "hubspot": ("TopstepX", TRADE_BODY + '<div role="dialog" class="go1222083472 go3508454897 hs-cta-embed__loaded go3" style="position:fixed;'
                'right:20px;bottom:20px;width:400px;height:198px"><iframe src="https://topsteptrader-0000000.hs-sites.com/cta/abc" '
                'style="width:400px;height:198px;border:0"></iframe></div>'),
    "hubspot_fremd": ("TopstepX", TRADE_BODY + '<div role="dialog" class="hs-cta-embed__loaded" style="position:fixed;right:20px;bottom:20px;'
                      'width:400px;height:198px"><iframe src="https://example.org/cta" style="width:400px;height:198px;border:0"></iframe></div>'),
    "pos_close": ("TopstepX", TRADE_BODY + '<div role="grid" style="position:fixed;left:900px;top:640px;width:700px;height:200px">'
                  '<div role="row"><div role="columnheader">Symbol</div></div><div role="row" style="display:flex;height:30px">'
                  '<div role="gridcell">MNQZ26</div><div role="gridcell"><button class="kreuz" style="width:24px;height:24px">'
                  '<svg width="12" height="12"><path d="M1 1l10 10M11 1L1 11" stroke="#fff"/></svg></button></div></div></div>'),
    "werbung_iframe": ("TopstepX", TRADE_BODY + '<div role="dialog" class="ab-iam-root ab-html" style="position:fixed;right:20px;bottom:20px;width:520px;height:220px">'
                       '<iframe title="Modal Message" srcdoc="&lt;h3&gt;Give 50% Off Get 50% Off&lt;/h3&gt;&lt;a href=&quot;#&quot;&gt;Get Your Code&lt;/a&gt;" '
                       'style="width:480px;height:200px;border:0"></iframe><button aria-label="Close" style="position:absolute;right:6px;top:6px;width:24px;height:24px">'
                       '<svg width="14" height="14"><path d="M1 1l12 12M13 1L1 13" stroke="#fff"/></svg></button></div>'),
    "werbung_text": ("TopstepX", TRADE_BODY + '<div role="dialog" class="promo" style="position:fixed;right:20px;bottom:20px;width:520px;height:220px;background:#222">'
                     '<h3>Give 50% Off Get 50% Off</h3><p>Everybody Eats This Friendsgiving! Share your referral code &amp; earn 50% off your next purchase.*</p>'
                     '<a href="#code">Get Your Code →</a><small>*Limited-time only. Terms &amp; conditions apply.</small>'
                     '<button style="position:absolute;right:6px;top:6px;width:24px;height:24px">×</button></div>'),
    "order_dialog": ("TopstepX", TRADE_BODY + '<div role="dialog" class="box" style="position:fixed;left:500px;top:200px"><h2>Confirm Order</h2>'
                     '<p>Buy 3 MNQZ26 @ Market</p><button>Close</button><button>Confirm</button></div>'),
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
                                   "--no-first-run", "--no-default-browser-check", "--window-size=1600,900",
                                   "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",   # kein Netz (HubSpot-iframe lädt nicht nach draußen)
                                   "about:blank"],
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
        # 0.7.4 = TS-D1 (Loss-Limit-Meldung ohne Rolle), Time-Sync unverändert — Kommentar hier, NICHT mitten im Ausdruck (Prüfer TS-D1)
        check(st.get("v") in ("tsx-0.7.3", "tsx-0.7.4") and len(pp) == 1 and pp[0].get("quelle") == "text" and pp[0].get("titel") == "Time Sync Warning"
              and dlg and kn and kn["text"] == "PROCEED", f"Modal OHNE ARIA-Rolle (Finns Bild): Popup aus dem Text-Weg, PROCEED gefunden ({pp[:1]})")
        alt_pp = (c.stand(ALT_AUGEN).get("popups") or []) if ALT_AUGEN else None
        check(alt_pp == [], "Gegenprobe: die alte augen_tsx.js (vor TX1) sah dieses Modal NICHT — die Ursache der Fehlstarts am 17.11.")
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
            n2 = ohne(n)
            for p_ in (n2.get("popups") or []):              # TX1b: jedes Popup trägt jetzt cls (nur bei einem offenen Dialog)
                p_.pop("cls", None)
            check(ALT_AUGEN and ohne(a) == n2 and (name != "trade" or not n.get("popups")),
                  f"stand() bitgleich zum Stand vor TX1 ({name}{'; Popups nur + cls' if n.get('popups') else ', ganz ohne Popup'})")
        # TX1b Werbe-Popup (Finns Bild 17.11.): role=dialog nur mit Grafik + Link „Get Your Code" + X (aria „Close Message")
        c.laden(*F["werbung_grafik"])
        pp = c.stand(NEU_AUGEN).get("popups") or []
        u = ob.tsx_ueberlagerung(pp[0]) if pp else None
        kn = ob.tsx_ueberlagerung_knopf(pp[0]) if pp else None
        check(len(pp) == 1 and not pp[0].get("text") and (pp[0].get("leer") or {}).get("bilder", 0) >= 1 and pp[0].get("cls")
              and u and u["art"] == "leer" and kn and kn.get("aus_aria"), f"Werbe-Popup ohne DOM-Text: als Überlagerung erkannt, X über aria ({pp[:1]})")
        check("Dialog ohne Text offen (ohne Text · Klasse" in ob.tsx_dialog_offen_text(pp) and "Lage [" in ob.tsx_dialog_offen_text(pp)
              and "Bilder 1" in ob.tsx_dialog_offen_text(pp), f"Vorprüfung nennt Klasse, Rolle, Lage ({ob.tsx_dialog_offen_text(pp)[:120]})")
        if kn:
            pr = {"rect": kn["rect"], "text": "", "aria": kn["text"], "tabu": ob.TSX_UEBER_PRUEF_TABU, "dialog": pp[0]["rect"]}
            v = c.ziel(kn["rect"], pr)
            check(v.get("hover") and v.get("passt") and v.get("dialog") is True, f"Ziel-Beweis mit Dialog-Bindung am X passt ({v.get('was')})")
            v_falsch = c.ziel(kn["rect"], dict(pr, dialog=[0, 0, 300, 100]))
            check(not v_falsch.get("passt") and "nicht im Popup" in str(v_falsch.get("was")), "falsches Popup-Rechteck → passt nicht")
            # S2-Fall 2: Popup liegt NICHT oben — ein anderes namenloses Element deckt das X
            c.js("(function(){var d=document.createElement('button');d.style.cssText='position:fixed;left:%dpx;top:%dpx;width:24px;height:24px;z-index:5000';"
                 "document.body.appendChild(d);})()" % (kn["rect"][0], kn["rect"][1]))
            v_alt = c.ziel(kn["rect"], {"rect": kn["rect"], "text": "", "aria": "", "tabu": ob.TSX_UEBER_PRUEF_TABU})
            v_neu = c.ziel(kn["rect"], {"rect": kn["rect"], "text": "", "aria": "", "tabu": ob.TSX_UEBER_PRUEF_TABU, "dialog": pp[0]["rect"]})
            check(v_alt.get("passt") and not v_neu.get("passt"),
                  "Popup liegt nicht oben (namenloser Knopf darüber): ohne Bindung hätte der Beweis gepasst, mit Bindung kein Druck")
            c.laden(*F["werbung_grafik"])
            lk = c.js("(function(){var r=document.querySelector('a.promo').getBoundingClientRect();return [r.left,r.top,r.width,r.height];})()")
            v2 = c.ziel(lk, dict(pr, rect=lk))
            check(not v2.get("passt"), "derselbe Beweis am Link „Get Your Code“ schlägt fehl (nie ein Link)")
        # TX1d: HubSpot-CTA mit Cross-Origin-iframe
        c.laden(*F["hubspot"])
        time.sleep(0.3)
        pp = c.stand(NEU_AUGEN).get("popups") or []
        check(len(pp) == 1 and ob.tsx_hubspot_werbung(pp[0]) and not ob.tsx_ueberlagerung_knopf(pp[0])
              and c.js("document.querySelector('iframe').contentDocument === null"),
              f"HubSpot-CTA: als HubSpot erkannt, kein Knopf sichtbar, iframe ist fremder Herkunft ({ob.tsx_ueberlagerung_name(pp[0]) if pp else '-'})")
        if pp:
            v = c.js(ob.tsx_hubspot_weg_js(pp[0]["rect"])) or {}
            pp2 = c.stand(NEU_AUGEN).get("popups") or []
            check(v.get("versteckt") == 1 and pp2 == [], f"ausgeblendet → stand() ohne Popup ({v})")
            v2 = c.js(ob.tsx_hubspot_weg_js(pp[0]["rect"])) or {}
            check(not v2.get("versteckt"), "zweiter Aufruf findet nichts mehr (nichts anderes betroffen)")
        c.laden(*F["hubspot_fremd"])
        time.sleep(0.3)
        pp = c.stand(NEU_AUGEN).get("popups") or []
        v = c.js(ob.tsx_hubspot_weg_js(pp[0]["rect"])) if pp else {}
        check(pp and not ob.tsx_hubspot_werbung(pp[0]) and not (v or {}).get("versteckt") and (c.stand(NEU_AUGEN).get("popups") or []),
              "gleiche Klasse, iframe NICHT von HubSpot → nicht ausgeblendet, Popup bleibt")
        c.laden(*F["werbung_grafik"])
        pp = c.stand(NEU_AUGEN).get("popups") or []
        check(pp and not (c.js(ob.tsx_hubspot_weg_js(pp[0]["rect"])) or {}).get("versteckt"), "normales Werbe-Popup wird nie ausgeblendet (dort gilt das X)")
        # S2-Fall 1: Popup verschwindet vor dem Druck → am Punkt liegt das textlose Close-Kreuz der Positionszeile
        c.laden(*F["pos_close"])
        kreuz = c.js("(function(){var r=document.querySelector('.kreuz').getBoundingClientRect();return [r.left,r.top,r.width,r.height];})()")
        alt_pr = {"rect": kreuz, "text": "", "aria": "", "tabu": ob.TSX_UEBER_PRUEF_TABU}
        v_alt = c.ziel(kreuz, alt_pr)
        v_neu = c.ziel(kreuz, dict(alt_pr, dialog=[1060, 573, 520, 220]))
        check(v_alt.get("passt") and not v_neu.get("passt") and "nicht im Popup" in str(v_neu.get("was")),
              f"Popup weg, Punkt auf dem Close-Kreuz: TX1b-Beweis hätte gedrückt, mit Bindung kein Druck ({v_neu.get('was')})")
        c.laden(*F["werbung_iframe"])
        pp = c.stand(NEU_AUGEN).get("popups") or []
        kn = ob.tsx_ueberlagerung_knopf(pp[0]) if pp else None
        check(len(pp) == 1 and (ob.tsx_ueberlagerung(pp[0]) or {}).get("art") == "leer" and kn and kn["text"] == "Close"
              and "iframe ['Modal Message']" in ob.tsx_dialog_offen_text(pp), f"Werbe-Popup mit Text im iframe: erkannt, X „Close“, Spur nennt das iframe")
        if kn:
            v = c.ziel(kn["rect"], {"rect": kn["rect"], "text": "", "aria": "Close", "tabu": ob.TSX_UEBER_KNOPF_TABU})
            check(v.get("hover") and v.get("passt"), "Ziel-Beweis am X neben dem iframe passt")
        c.laden(*F["werbung_text"])
        pp = c.stand(NEU_AUGEN).get("popups") or []
        u = ob.tsx_ueberlagerung(pp[0]) if pp else None
        check(u and u["art"] == "werbung" and (ob.tsx_ueberlagerung_knopf(pp[0]) or {}).get("text") in ("×", "Close")
              and ob.tsx_dialog_offen_text(pp).startswith("TopstepX-Werbe-Popup offen ('Give 50% Off"), "Werbe-Popup mit Text: „TopstepX-Werbe-Popup“, X gefunden")
        c.laden(*F["order_dialog"])
        pp = c.stand(NEU_AUGEN).get("popups") or []
        check(pp and ob.tsx_ueberlagerung(pp[0]) is None and ob.tsx_dialog_offen_text(pp) == "Dialog offen ('Confirm Order')",
              "Order-Bestätigung bleibt unangetastet, Text wie bisher")
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
print("── E) Bitgleich gegen den Stand vor TX1 (" + BASIS + ")")
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
    GEAENDERT = {"tsx_zeitsync_dialog", "_tsx_zeitsync_weg", "_tsx_cdp_login", "_tsx_sitzung_waehlen", "_tsx_auge_konto", "modus_tsxlesen_cdp",
                 "_tsx_k3_probe", "_tsx_k4_senden", "tsx_k3_vor_klick", "_tsx_k4_dialog_name"}
    GEAENDERT.add("win_ziel_pruef_js")   # TX1c: Weiche zu win_ziel_pruef_dialog_js NUR mit pruef.dialog — Ausgabe sonst buchstabengleich (s. u.)
    GEAENDERT.add("_tsx_konto_sichern")  # TS-D1 (20.11.2026): Loss-Limit-Meldung bei aktivem Ziel + Dialog-Spur bei „verdeckt“ — geprüft in selftest_tsd1_mll_dialog.py
    GEAENDERT.update({"tsx_blow_dialog", "_tsx_blow_dialog_weg"})   # TS-D1: Art aus dem Treffer; Text-Weg mit Sperrzone + Kasten-Bindung (ebd.)
    GEAENDERT.add("tsx_blow_dialog_knopf")   # TS-D1b (Stopp S2): nur ok/okay/close/dismiss/schließen/× — nie Continue/Got it/I understand (ebd.)
    GEAENDERT.update({"tsx_verletzungen_aus_liste", "tsx_geblowt_urteil", "_tsx_geblowt_merken", "tsx_blow_dialog_verletzung"})   # TS-D2 (20.11.2026): DLL = Tagesstopp statt geblowt — geprüft in selftest_tsd2_dll_tagesstopp.py
    GEAENDERT.add("_tsx_k3_contract")   # CF1 (23.11.2026): Contract-Feld ohne Klick-Beweis → Überlagerungen weg, EIN zweiter Klick — geprüft in selftest_cf1_contract_feld.py
    GEAENDERT.update({"_puls_mit_neustart", "_tsx_order_cdp_mit_neustart", "modus_tvkette_cdp_mit_neustart"})   # CF1b: Spur + Fehlerfoto des 1. Versuchs vor dem Neustart — ebd.
    # 23.11.2026 (Master): Änderungen außerhalb der TopstepX-Dialoge, je mit eigenem Selbsttest — der Wächter meldete sie seit ihrem Push als „nicht bitgleich“
    GEAENDERT.update({"_cdp_konto_sichern", "_cdp_liste_scrollen"})   # PS1/PS1b: Konto-Liste scrollen, Ziel-Beweis beim Konto-Klick
    GEAENDERT.update({"_puls_chrome_neustart", "modus_augen"})   # PN1/PN1c: Neustart ohne den Prophos-Tab — selftest_pn1_neustart_prophos_tab.py
    GEAENDERT.update({"run", "stufen_ausloesen"})   # NG2b: „nichts gesendet“ beim Echo-Bestätigungs-Timeout — selftest_ng2b_nichts_gesendet.py
    # 24.11.2026 (Slave 1, Auftrag Master): BF1b und TX2, je mit eigenem Selbsttest
    GEAENDERT.add("_cdp_einheit_auf_dollar")   # BF1b: neues TP/SL-Einheitenmenü (Text-Weg, nur neue Gruppen am Wähler) — selftest_bf1_werbung_einheit.py
    GEAENDERT.update({"_AugenSitzung", "_tsx_google_login", "_tsx_tab_sicher", "modus_k3", "modus_tsxinventar_cdp"})   # TX2: Fenster per Titel-Marke,
    # Anmelde-Tabs aufräumen, Puls-Chrome-Sperre atomar (_handlauf_nehmen) — selftest_tx2_topstepx_fenster.py
    GEAENDERT.add("cdp_konto_familie")   # KL1 (24.11.2026): FTMO Futures als eigene Login-Familie 'ftmo' — selftest_kl1_ftmo_konto_weg.py
    GEAENDERT.update({"_cdp_tab_neu", "_tsx_auge_reparieren", "_cdp_tab_eigenes_fenster", "modus_augen"})   # TX3 (24.11.2026): Tab-Deckel je PC vor jedem neuen Tab — selftest_tx3_tab_deckel.py
    GEAENDERT.add("_echo_scharf_abwarten")   # PE1 (24.11.2026): Status-Datei bei PermissionError kurz nachlesen — selftest_pe1_status_nachlesen.py
    ns_alt = {"json": json, "WIN_HOVER_ELTERN_JS": ob.WIN_HOVER_ELTERN_JS}
    exec(alt_d["win_ziel_pruef_js"], ns_alt)
    proben = [{"rect": [1, 2, 3, 4], "text": "", "aria": "", "tabu": "x"}, {"rect": [5, 6, 7, 8], "text": "proceed", "aria": "", "tabu": "y", "wort": "proceed"},
              {"rect": [1, 1, 9, 9], "text": "", "aria": "close", "tabu": "z", "zelle": [1, 1, 9, 9]}, {"rect": [2, 2, 5, 5], "text": "abc", "aria": "", "tabu": "q", "karte": [0, 0, 50, 20]}]
    check(all(ns_alt["win_ziel_pruef_js"](10.5, 20.5, p_) == ob.win_ziel_pruef_js(10.5, 20.5, p_) for p_ in proben),
          "win_ziel_pruef_js ohne pruef.dialog: erzeugter Beweis buchstabengleich zum Stand vor TX1 (alle Order-Klicks unverändert)")
    anders = sorted(n for n in alt_d if n not in GEAENDERT and alt_d[n] != neu_d.get(n))
    check(not anders, f"alle übrigen {len(alt_d) - len(GEAENDERT)} Funktionen/Klassen bitgleich, auch _AugenSitzung, _tsx_konto_sichern, _tsx_k3_probe, "
                      f"_tsx_k4_senden, tsx_k3_vor_klick, _tsx_blow_dialog_weg ({anders[:6]})")
    weg_erlaubt = {
        "_tsx_zeitsync_weg": 1,          # alte Spurzeile (jetzt mit „Time-Sync-Dialog weggeklickt" davor)
        "_tsx_cdp_login": 0,             # nur die Google-Weiche davor
        "_tsx_sitzung_waehlen": 1,       # login_seite: seite → tsx_login_art
        "_tsx_auge_konto": 1,            # Bedingung nach der Bereit-Probe
        "modus_tsxlesen_cdp": 4,         # Bedingung nach der Bereit-Probe (Lesen + Order-Start); TS-D2: K2-Felder + Schritt konto_tagesstopp (2 Zeilen); TX2: _handlauf_setzen(True) → _handlauf_nehmen (1 Zeile)
        "_tsx_k3_probe": 0,              # TX1b: vor dem Order-Klick nur der Überlagerungs-Zweig dazu (hinter tsx_ueberlagerung)
        "_tsx_k4_senden": 1,             # TX1b: Überlagerungs-Zweig dazu, g_ nimmt den klaren Grund (_ug), sonst wie bisher
        "tsx_k3_vor_klick": 1,           # TX1b: Text „Dialog offen" über tsx_dialog_offen_text (mit Titel/Text gleich, s. A2)
        "_tsx_k4_dialog_name": 0,        # TX1b: ohne Titel/Text Klasse/Rolle/Lage
    }
    for name in ("_tsx_k3_probe", "_tsx_k4_senden"):
        neu_z = [x[1:] for x in difflib.unified_diff(alt_d[name].splitlines(), neu_d[name].splitlines(), lineterm="", n=0)
                 if x.startswith("+") and not x.startswith("+++")]
        check(neu_z and all(any(w_ in z for w_ in ("ueberlagerung", "Überlagerung", "_ug", "zeitsync", "_zs"))
                            or z.strip() in ("try:", "except Exception as e_:") for z in neu_z),
              f"{name}: neue Zeilen nur im Überlagerungs-Zweig ({len(neu_z)})")
    for name, n_erlaubt in weg_erlaubt.items():
        d = [x for x in difflib.unified_diff(alt_d[name].splitlines(), neu_d[name].splitlines(), lineterm="", n=0)
             if x.startswith("-") and not x.startswith("---")]
        check(len(d) == n_erlaubt, f"{name}: genau {n_erlaubt} alte Zeile(n) ersetzt, sonst nur Neues ({[x[:90] for x in d]})")
    ab = [x for x in difflib.unified_diff(js_konstante(ALT_BOT, "TSX_K0_BLICK_JS").splitlines(), js_konstante(src_bot, "TSX_K0_BLICK_JS").splitlines(),
                                          lineterm="", n=0) if x.startswith("-") and not x.startswith("---")]
    check(not ab, "TSX_K0_BLICK_JS: nur Zeilen dazu, keine alte Zeile geändert")
    ab = [x for x in difflib.unified_diff(ALT_AUGEN.splitlines(), NEU_AUGEN.splitlines(), lineterm="", n=0) if x.startswith("-") and not x.startswith("---")]
    check(len(ab) == 1 and "var VERSION = 'tsx-0.7.2'" in ab[0], f"augen_tsx.js: nur VERSION geändert, sonst nur Neues ({[x[:60] for x in ab]})")

# ── E2) TX1d gegen origin/main (live .2245 mit TX1–TX1c): nur _tsx_ueberlagerung_weg bekommt den HubSpot-Zweig, sonst nur neue Funktionen ──
print("── E2) TX1d gegen origin/main")
MAIN_BOT = git_alt("mt5-copier/order_bot.py", "origin/main")
if MAIN_BOT and "tsx_hubspot_werbung" not in MAIN_BOT:
    m_d, n_d = defs(MAIN_BOT), defs(src_bot)
    anders2 = sorted(n for n in m_d if m_d[n] != n_d.get(n))
    check(anders2 == ["_tsx_ueberlagerung_weg"], f"gegenüber origin/main nur _tsx_ueberlagerung_weg geändert ({anders2})")
    weg2 = [x for x in difflib.unified_diff(m_d["_tsx_ueberlagerung_weg"].splitlines(), n_d["_tsx_ueberlagerung_weg"].splitlines(), lineterm="", n=0)
            if x.startswith("-") and not x.startswith("---")]
    neu2 = [x[1:] for x in difflib.unified_diff(m_d["_tsx_ueberlagerung_weg"].splitlines(), n_d["_tsx_ueberlagerung_weg"].splitlines(), lineterm="", n=0)
            if x.startswith("+") and not x.startswith("+++")]
    check(not weg2 and neu2 and neu2[0].strip().startswith("hs = next(") and all("hs" in z or "was" in z or "name" in z or "grund" in z
                                                                                or z.strip() in ("continue", "p, u = hs[0], hs[1]") for z in neu2),
          f"_tsx_ueberlagerung_weg: nur der HubSpot-Zweig dazu, nur hinter „kein Knopf“, keine Zeile entfernt ({len(neu2)} neu)")
    neu_namen = sorted(set(n_d) - set(m_d))
    check(neu_namen == ["_tsx_hubspot_weg", "tsx_hubspot_weg_js", "tsx_hubspot_werbung"], f"neue Funktionen nur HubSpot ({neu_namen})")
    check(git_alt("mt5-copier/augen_tsx.js", "origin/main") == NEU_AUGEN, "augen_tsx.js unverändert gegenüber origin/main")
else:
    print("(E2 übersprungen: origin/main enthält TX1d schon)")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER: {FEHLER}")
sys.exit(1 if FEHLER else 0)
