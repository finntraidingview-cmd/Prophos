#!/usr/bin/env python3
"""Selbsttest TS-D1 „Loss-Limit-Meldung in TopstepX wegklicken“ (20.11.2026, Marc pc-7ftp5l, acht Fehlstarts 19./20.11.: „Nichts platziert ·
Konto-Auslöser verdeckt ('You Hit YourMaximum Loss Limit.Setbacks ') — Dialog offen? Nichts geklickt“. Finn: „Das muss weggeklickt werden können —
einfach wegklicken, OK oder Dismiss, alles muss gelernt werden können.“)
Ursachen: (1) TSX_RX_BLOW_DIALOG verlangte genau ein Leerzeichen („Your Maximum“), TopstepX liefert „YourMaximum“ — Meldung nie erkannt;
(2) das Modal kann ohne ARIA-Rolle kommen (wie die Time Sync Warning, TX1) — augen_tsx.js tsx-0.7.4 liefert es über den Text (limitOhneRolle).
Teile: A Regeln mit dem Text von heute (+ Gegenprobe alte Regex) · B _tsx_konto_sichern mit nachgebauter Sitzung (Marcs Fall, Ziel aktiv → geblowt,
fremdes Konto genannt, Meldung ohne lesbaren Dialog, unbekannter Dialog → Spur, nur Reset-Knöpfe → nichts) · C echte DOM-Schnipsel in Headless-Chrome
(neu vs. alte augen_tsx.js, Ziel-Beweis am OK-Knopf, ohne Meldung bitgleich). Alle Kennungen erfunden.
Aufruf: python3 tools/selftest_tsd1_mll_dialog.py   (C braucht Google Chrome; ohne Chrome wird C übersprungen und gemeldet)"""
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


ob._warte = lambda *a, **k: None
ob._tsx_pause = lambda *a, **k: None
ob._puls_diagnose_senden = lambda spur=None, schritt="": None

R_OK, R_RESET, R_X = [700, 520, 120, 36], [480, 520, 200, 36], [960, 300, 24, 24]
TEXT_HEUTE = ("You Hit YourMaximum Loss Limit.Setbacks are part of every trader's journey. Take a breath, review your trades and come back "
              "stronger. Your account can be reset whenever you're ready.")


R_KASTEN = [440, 250, 720, 340]


def popup(text=TEXT_HEUTE, knoepfe=None, titel="You Hit YourMaximum Loss Limit.", quelle="text"):
    return {"role": "", "titel": titel, "text": text[:160], "text_voll": text[:400], "quelle": quelle, "rect": R_KASTEN, "cls": "box",
            "knoepfe": knoepfe if knoepfe is not None else [{"text": "RESET ACCOUNT", "rect": R_RESET}, {"text": "OK", "rect": R_OK}]}


# ── A) Regeln ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
print("── A) Regeln mit dem Dialogtext von heute")
bd = ob.tsx_blow_dialog([popup()])
check(bd is not None and bd["art"] == "maximum_loss" and bd["konto"] == "", f"„You Hit YourMaximum Loss Limit.Setbacks …“ erkannt (maximum_loss, ohne Kennung) ({bd and bd['text'][:40]})")
check(ob.tsx_blow_dialog([popup(text="You Hit YourDaily Loss Limit.Setbacks are part …", titel="You Hit YourDaily Loss Limit.")])["art"] == "daily_loss",
      "dieselbe Form mit „Daily“ → daily_loss")
check(ob.tsx_blow_dialog([popup(text="You Hit Your Maximum Loss Limit. Account: 150KTC-SKU-V2-DLL-000000-00000001")])["konto"]
      == "150KTC-SKU-V2-DLL-000000-00000001", "alte Form mit Leerzeichen + Kennung weiter erkannt")
check(ob.tsx_blow_dialog([popup(text="This account is no longer eligible for funding")]) is not None, "„no longer eligible for funding“ weiter erkannt")
check(ob.tsx_blow_dialog([{"titel": "Confirm Order", "text": "Buy 2 NQZ26 @ Market", "knoepfe": []}]) is None, "Order-Dialog ist keine Meldung")
check(ob.tsx_blow_dialog([popup(text="You Hit YourMaximum Loss Limit.Your daily routine matters — review your trades.")])["art"] == "maximum_loss",
      "MLL-Meldung, die beiläufig „daily“ erwähnt → maximum_loss (Art aus dem Treffer, Prüfer)")
try:
    alt_src = subprocess.run(["git", "-C", WURZEL, "show", "9e0b722e^:mt5-copier/order_bot.py"], capture_output=True, text=True, check=True).stdout   # fester Stand vor TS-D1 (TS-D2 20.11.2026: TS-D1 liegt jetzt auf main)
    m = re.search(r'TSX_RX_BLOW_DIALOG = re\.compile\(r"(.*?)"\s*\n\s*r"(.*?)", re\.I\)', alt_src, re.S)
    alt_rx = re.compile(m.group(1) + m.group(2), re.I) if m else None
    check(alt_rx is not None and not alt_rx.search(TEXT_HEUTE) and alt_rx.search("You Hit Your Maximum Loss Limit."),
          "Gegenprobe: die alte Regex (vor TS-D1) traf „YourMaximum“ NICHT — die Ursache der acht Fehlstarts")
except Exception as e:
    print(f"(Gegenprobe alte Regex übersprungen: {type(e).__name__})")

kn = ob.tsx_blow_dialog_knopf(popup())
check(kn is not None and kn["text"] == "OK" and kn["rect"] == R_OK, f"Knöpfe RESET ACCOUNT + OK → OK ({kn and kn.get('text')})")
for knoepfe, soll, name in (
        ([{"text": "Dismiss", "rect": R_OK}, {"text": "Restart", "rect": R_RESET}], "Dismiss", "Dismiss + Restart → Dismiss"),
        ([{"text": "Close", "rect": R_OK}, {"text": "Reset Trading Combine", "rect": R_RESET}], "Close", "Close + Reset Trading Combine → Close"),
        ([{"text": "", "aria": "", "icon": "CloseIcon", "rect": R_X}, {"text": "RESET ACCOUNT", "rect": R_RESET}], "", "nur Symbol-X + Reset → Symbol-X"),
        ([{"text": "RESET ACCOUNT", "rect": R_RESET}, {"text": "ACTIVATE", "rect": R_OK}], None, "nur Reset/Activate → nichts"),
        ([{"text": "Buy More", "rect": R_RESET}, {"text": "Restart Combine", "rect": R_OK}], None, "Buy/Restart → nichts"),
        ([{"text": "OK", "rect": R_OK}, {"text": "Close", "rect": R_RESET}], None, "zwei verschiedene Schließ-Wörter → nichts raten"),
        # TS-D1b (Stopp S2 zu 024e2b83): Weiter-/Bestätigungs-Wörter können in Back2Funded/Reset führen — nie in der Loss-Limit-Meldung
        ([{"text": "Continue", "rect": R_OK}, {"text": "Reset Trading Combine", "rect": R_RESET}], None, "Continue + Reset → nichts gedrückt"),
        ([{"text": "Got it", "rect": R_OK}, {"text": "RESET ACCOUNT", "rect": R_RESET}], None, "Got it + Reset → nichts gedrückt"),
        ([{"text": "I understand", "rect": R_OK}], None, "nur „I understand“ → nichts gedrückt"),
        ([{"text": "", "aria": "Continue", "rect": R_X, "icon": "CloseIcon"}], None, "Symbol mit aria „Continue“ → nichts (kein Schließ-X)"),
        ([{"text": "Continue", "rect": R_RESET}, {"text": "Dismiss", "rect": R_OK}], "Dismiss", "Continue + Dismiss → Dismiss")):
    k = ob.tsx_blow_dialog_knopf(popup(knoepfe=knoepfe))
    check((k is None) if soll is None else (k is not None and k.get("text") == soll), f"Knopf: {name} ({k and (k.get('text') or k.get('name'))})")

sp = ob.tsx_dialoge_spur([popup(), {"titel": "Neuer Hinweis", "text": "Something we never saw", "knoepfe": [{"text": "Got it", "rect": R_OK},
                                                                                                        {"aria": "Close", "rect": R_X}]}])
check("YourMaximum Loss Limit" in sp and "'OK'" in sp and "'RESET ACCOUNT'" in sp and "Neuer Hinweis" in sp and "'Got it'" in sp and "aria:Close" in sp,
      f"tsx_dialoge_spur: Titel, Text, Quelle und alle Knöpfe in der Spur ({sp[:120]}…)")
check(ob.tsx_dialoge_spur([]) == "" and ob.tsx_dialoge_spur(None) == "", "keine Dialoge → ''")

# ── B) _tsx_konto_sichern mit nachgebauter Sitzung ──────────────────────────────────────────────────────────────────────────
print("── B) K2 mit nachgebauter Sitzung")
EXT = "150KTC-SKU-V2-DLL-000000-00000002"
ALT = "150KTC-SKU-V2-DLL-000000-00000001"
R_AUSL = [68, 4, 194, 34]


def konto(nr, popups=None, verdeckt=None):
    zu = {"verdeckt": True, "oben": {"tag": "div", "text": verdeckt}} if verdeckt else {}
    return {"konto": {"aktiv": f"150K DLL Combine|{nr}", "kontonr": nr, "abgekuerzt": False, "rect": R_AUSL, "liste_offen": False, "zu": zu},
            "popups": popups or []}


class Sitz:
    def __init__(self, staende, antworten):
        self.staende, self.i, self.antworten, self.klicks, self.pruef = staende, 1, list(antworten), [], []

    def stand(self, opts=None):
        x = self.staende[min(self.i, len(self.staende) - 1)]
        self.i += 1
        return x

    def klick(self, rect, name, pruef=None, doppel=False):
        self.klicks.append((name, list(rect)))
        self.pruef.append(pruef or {})
        return self.antworten.pop(0) if self.antworten else False

    def taste(self, *a, **k):
        pass


def lauf(staende, antworten):
    s = Sitz(staende, antworten)
    trail = ob._StempelSpur()
    ok, code, msg, st, ex = ob._tsx_konto_sichern(s, EXT, staende[0], trail)
    return ok, code, msg, ex, s, " > ".join(trail)


VERDECKT = "You Hit YourMaximum Loss Limit.Setbacks "
# B1 Marcs Fall: vorgewähltes Konto ALT, Meldung ohne Kennung über dem Auslöser → OK drücken, Meldung weg, dann wie immer zum Ziel wechseln
ok, code, msg, ex, s, sp = lauf([konto(ALT, [popup()], VERDECKT), konto(ALT), konto(ALT), konto(ALT), konto(EXT), konto(EXT)], [True, True])
check(ok and len(s.klicks) == 2 and s.klicks[0][0].startswith("Meldung schließen") and s.klicks[0][1] == R_OK and s.klicks[1][0].startswith("Konto"),
      f"Marcs Fall: erst OK der Meldung, dann der Konto-Auslöser, Ziel steht ({[k[0][:30] for k in s.klicks]}, {code})")
check("Meldung geschlossen — weiter" in sp and "TopstepX-Meldung: 'You Hit YourMaximum" in sp, "Spur: Meldung gelesen und geschlossen")
check(re.search(ob.TSX_DIALOG_TABU, "reset") is None and all("reset" not in (p.get("wort") or "") for p in s.pruef),
      "nie auf RESET gedrückt (Ziel-Beweis mit Schließ-Wort)")
check(not ex.get("blow_dialog") and EXT not in (ex.get("konto_verletzungen") or {}) and "nicht als geblowt gewertet" in sp,
      "Meldung ohne Kennung vor dem Wechsel → geht NICHT mit (galt dem vorgewählten Konto)")
# Prüfer KRITISCH: genau so übernimmt der Aufrufer ex2 und fragt tsx_geblowt_urteil mit aktiv = jetzt das Ziel
res_auf = {k: v for k, v in ex.items() if k in ("konto_gewechselt", "konto_hinweis", "konto_verletzungen", "blow_dialog")}
check(ob.tsx_geblowt_urteil(res_auf, EXT, EXT) is None, "Aufrufer-Ebene: das gesunde Ziel gilt nach dem Wechsel NICHT als geblowt (kein Archiv)")
check(s.pruef[0].get("kasten") is True and s.pruef[0].get("dialog") == R_KASTEN and s.pruef[0].get("tabu") == ob.TSX_BLOW_PRUEF_TABU
      and all(re.search(ob.TSX_BLOW_PRUEF_TABU, w, re.I) for w in ("Reset Trading Combine", "Continue", "Got it", "I understand"))
      and not any(re.search(ob.TSX_BLOW_PRUEF_TABU, w, re.I) for w in ("OK", "Close", "Dismiss")),
      "Text-Weg: Ziel-Beweis an den Kasten gebunden + Tabu (Reset, Continue, Got it, I understand), OK/Close/Dismiss frei")
# TS-D1b Beleg von S2 als ganzer Lauf: Text-Weg-Meldung mit „Continue“ + „Reset Trading Combine“ → nichts gedrückt
ok, code, msg, ex, s, sp = lauf([konto(ALT, [popup(knoepfe=[{"text": "Continue", "rect": R_OK}, {"text": "Reset Trading Combine", "rect": R_RESET}])],
                                       VERDECKT), konto(ALT, [popup()], VERDECKT)], [True])
check(not s.klicks and "kein eindeutiger Schließ-Knopf" in sp, f"Beleg S2: Continue + Reset Trading Combine → nichts gedrückt ({code})")
check(re.search(ob.TSX_UEBER_PRUEF_TABU, "Got it", re.I) is None, "Überlagerungen unverändert: „Got it“ dort weiter nicht tabu")
ok, code, msg, ex, s, sp = lauf([konto(EXT, [popup(quelle="")]), konto(EXT), konto(EXT)], [True])
check(len(s.pruef) == 1 and "kasten" not in s.pruef[0] and "dialog" not in s.pruef[0], "ARIA-Dialog: Ziel-Beweis wie bisher (keine Kasten-Bindung)")
# Sperrzone: der OK-Knopf liegt über dem Kauf-Knopf der Order-Karte → kein Druck (wie TX1c bei Überlagerungen)
st_zone = dict(konto(ALT, [popup()], VERDECKT), ticket={"kauf": {"rect": R_OK}})
ok, code, msg, ex, s, sp = lauf([st_zone, st_zone], [True])
check(not s.klicks and "Schließ-Knopf liegt über dem Kauf-Knopf" in sp, f"Sperrzone: OK über dem Kauf-Knopf → nichts gedrückt ({sp[-120:]})")
# Order-Weg (Ziel aktiv, kein K2): Dialog-Beweis → konto_geblowt statt Ticket-Probe (Quelltext-Vertrag)
src = open(ob.__file__, encoding="utf-8").read()
i_g = src.index('if order and isinstance(geblowt, dict) and geblowt.get("quelle") == "dialog":')
check(i_g < src.index("return _tsx_k3_probe(s, st, order, res, trail, raus, order_cmd)", i_g)
      and 'raus("konto_geblowt"' in src[i_g:i_g + 900] and "Konto hat MLL erreicht (TopstepX-Dialog)" in src[i_g:i_g + 900],   # TS-D2: DLL ist kein Blow mehr
      "Order-Weg: Dialog-Beweis „Ziel geblowt“ beendet VOR der Ticket-Probe mit konto_geblowt + Grund")
check(ob.tsx_geblowt_urteil({"blow_dialog": {"art": "maximum_loss", "konto": "", "text": "x"}}, EXT, EXT)["quelle"] == "dialog",
      "Meldung ohne Kennung bei aktivem Ziel (ohne Wechsel) → Dialog-Beweis „geblowt“")

# B2 Ziel schon aktiv + Meldung ohne Kennung → schließen und konto_geblowt (Plan nicht starten), Grund „Konto hat MLL erreicht (TopstepX-Dialog)“
ok, code, msg, ex, s, sp = lauf([konto(EXT, [popup()]), konto(EXT), konto(EXT)], [True])
check(not ok and code == "konto_geblowt" and "Konto hat MLL erreicht (TopstepX-Dialog)" in msg and msg.startswith("TopstepX meldet „")
      and len(s.klicks) == 1 and s.klicks[0][1] == R_OK, f"Ziel aktiv + Meldung → geschlossen, konto_geblowt mit Grund ({code}: {msg[:90]})")

# B3 Ziel aktiv + Meldung nennt ein ANDERES volles Konto → schließen, Ziel bleibt gut (ok), das genannte Konto als Verletzung
ok, code, msg, ex, s, sp = lauf([konto(EXT, [popup(text=f"You Hit YourMaximum Loss Limit.Account: {ALT}")]), konto(EXT), konto(EXT)], [True])
check(ok and len(s.klicks) == 1 and ALT in (ex.get("konto_verletzungen") or {}),
      f"Ziel aktiv, Meldung nennt fremdes Konto → schließen, ok, fremdes Konto als Verletzung ({code}, {list((ex.get('konto_verletzungen') or {}))})")

# B4 Ziel aktiv + Meldung, Schließen klappt nicht (Klick ohne Beweis) → ehrlich raus, kein zweiter Druck
ok, code, msg, ex, s, sp = lauf([konto(EXT, [popup()]), konto(EXT, [popup()]), konto(EXT, [popup()])], [False])
check(not ok and len(s.klicks) == 1 and code in ("konto_geblowt", "konto_nicht_erreicht"),
      f"Schließen ohne Beweis → genau ein Druck-Versuch, ehrlich raus ({code})")

# B5 Meldung liegt über dem Auslöser, steht aber in keinem lesbaren Dialog (alte augen_tsx.js) → klarer Grund, nichts geklickt
ok, code, msg, ex, s, sp = lauf([konto(ALT, [], VERDECKT)], [])
check(not ok and code == "konto_nicht_erreicht" and "kein lesbarer Dialog" in msg and not s.klicks and "über dem Konto-Auslöser liegt" in sp,
      f"Meldung ohne Dialog → „kein lesbarer Dialog (augen_tsx.js)“, nichts geklickt, Element in der Spur ({msg[:70]})")

# B6 unbekannter Dialog über dem Auslöser → wie bisher „Dialog offen?“, aber Titel/Text/Knöpfe in der Spur (lernen), nichts geklickt
unbek = {"role": "dialog", "titel": "Platform Notice", "text": "Platform NoticeWe changed something today.", "knoepfe": [{"text": "Got it", "rect": R_OK}]}
ok, code, msg, ex, s, sp = lauf([konto(ALT, [unbek], "Platform NoticeWe changed something")], [])
check(not ok and "Dialog offen?" in msg and not s.klicks and "Dialoge: 'Platform Notice'" in sp and "'Got it'" in sp,
      f"unbekannter Dialog → nichts geklickt, Titel + Knöpfe in der Spur ({sp[-140:]})")

# B7 Meldung nur mit Reset-/Activate-Knöpfen → nichts gedrückt, Knöpfe in der Spur
ok, code, msg, ex, s, sp = lauf([konto(ALT, [popup(knoepfe=[{"text": "RESET ACCOUNT", "rect": R_RESET}, {"text": "ACTIVATE", "rect": R_OK}])], VERDECKT),
                                 konto(ALT, [popup()], VERDECKT)], [])
check(not ok and not s.klicks and "kein eindeutiger Schließ-Knopf" in sp and "'RESET ACCOUNT'" in sp,
      f"nur Reset/Activate → nichts gedrückt, Knöpfe in der Spur ({code})")

# B8 ohne Meldung: Ziel aktiv → ok wie bisher ohne Klick
ok, code, msg, ex, s, sp = lauf([konto(EXT)], [])
check(ok and not s.klicks and not ex.get("blow_dialog"), "ohne Meldung, Ziel aktiv → ok, kein Klick (wie bisher)")

# ── C) Echte DOM-Schnipsel in Headless-Chrome ───────────────────────────────────────────────────────────────────────────────
print("── C) DOM-Schnipsel in echtem Chrome (headless)")
NEU_AUGEN = open(os.path.join(WURZEL, "mt5-copier", "augen_tsx.js"), encoding="utf-8").read()
try:
    ALT_AUGEN = subprocess.run(["git", "-C", WURZEL, "show", "9e0b722e^:mt5-copier/augen_tsx.js"], capture_output=True, text=True, check=True).stdout   # fester Stand vor TS-D1 (s. o.)
except Exception:
    ALT_AUGEN = None
CHROME = None
for kand in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", shutil.which("google-chrome") or "", shutil.which("chromium") or ""):
    if kand and os.path.exists(kand):
        CHROME = kand
        break

SEITE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>TopstepX</title><style>
body{margin:0;width:1600px;height:900px;font-family:sans-serif;background:#111;color:#ddd}
.kopf{position:absolute;left:10px;top:10px;width:600px;height:40px}
.schleier{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:1000;display:flex;align-items:center;justify-content:center}
.box{width:520px;padding:24px;background:#1e2229;border:1px solid #333;position:relative}
.knopf{display:inline-block;width:200px;height:36px;margin:20px 10px 0 0;border:1px solid #c9a227;color:#c9a227;background:none}
.x{position:absolute;right:8px;top:8px;width:24px;height:24px}
</style></head><body>%s</body></html>"""
TRADE = ('<div class="kopf"><button data-testid="account-selector" aria-expanded="false">150K DLL Combine (...1094)MLL</button></div>'
         '<div style="position:absolute;left:10px;top:60px">BAL: $147,000.00 MLL: $145,500.00</div>')
MELDUNG = ('<div class="box"><h2><span>You Hit Your</span><span>Maximum Loss Limit.</span></h2><p>Setbacks are part of every trader\'s journey. '
           'Take a breath and come back stronger.</p>%s</div>')
F = {
    "ohne_rolle": TRADE + '<div class="schleier">' + MELDUNG % '<button class="knopf">RESET ACCOUNT</button><button class="knopf">OK</button>' + '</div>',
    "mit_rolle": TRADE + '<div class="schleier"><div role="dialog">' + MELDUNG % '<button class="knopf">RESET ACCOUNT</button><button class="knopf">OK</button>' + '</div></div>',
    "nur_x": TRADE + '<div class="schleier">' + MELDUNG % ('<button class="knopf">RESET ACCOUNT</button><button class="x" aria-label="">'
                                                          '<svg data-testid="CloseIcon" width="14" height="14"><path d="M1 1l12 12M13 1L1 13" stroke="#fff"/></svg></button>') + '</div>',
    "ohne_meldung": TRADE,
    # Prüfer: derselbe Text als Banner im Panel (kein fixiertes Overlay), Knöpfe daneben → KEIN Popup (nie ein Kasten neben Order-Karte/Dock)
    "banner": TRADE + ('<div style="position:absolute;left:900px;top:400px;width:600px;height:300px"><div><span>You Hit Your</span>'
                       '<span>Maximum Loss Limit.</span></div><button>Close</button><button class="x" aria-label=""><svg data-testid="CloseIcon" '
                       'width="12" height="12"></svg></button></div>'),
}


class Chrome:
    def __init__(self):
        self.port = 9481
        self.dir = tempfile.mkdtemp(prefix="tsd1-chrome-")
        self.p = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={self.port}", f"--user-data-dir={self.dir}", "--no-first-run",
                                   "--no-default-browser-check", "--window-size=1600,900", "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
                                   "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

    def laden(self, body):
        self.v.rufe("Page.navigate", {"url": "data:text/html;charset=utf-8," + urllib.parse.quote(SEITE % body)}, timeout=15)
        for _ in range(50):
            if self.js("document.readyState") == "complete":
                break
            time.sleep(0.1)

    def js(self, a):
        r = self.v.rufe("Runtime.evaluate", {"expression": a, "returnByValue": True, "awaitPromise": True}, timeout=15)
        if r.get("exceptionDetails"):
            raise RuntimeError(json.dumps(r["exceptionDetails"])[:300])
        return (r.get("result") or {}).get("value")

    def stand(self, quelle):
        self.js("delete globalThis.prophosAugen")
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


def ohne(d):
    d = json.loads(json.dumps(d))
    for k in ("ts", "v"):
        d.pop(k, None)
    return d


if not CHROME:
    print("(C übersprungen: kein Google Chrome gefunden)")
    FEHLER.append("C nicht gelaufen (kein Chrome)")
else:
    c = Chrome()
    try:
        c.laden(F["ohne_rolle"])
        st = c.stand(NEU_AUGEN)
        pp = st.get("popups") or []
        bd = ob.tsx_blow_dialog(pp)
        kn = ob.tsx_blow_dialog_knopf(bd["popup"]) if bd else None
        check(st.get("v") == "tsx-0.7.4" and len(pp) == 1 and pp[0].get("quelle") == "text" and bd and kn and kn["text"] == "OK",
              f"Modal OHNE ARIA-Rolle: Popup aus dem Text-Weg, Meldung erkannt, Knopf OK ({[(p.get('titel'), [b.get('text') for b in p.get('knoepfe') or []]) for p in pp]})")
        if ALT_AUGEN:
            check((c.stand(ALT_AUGEN).get("popups") or []) == [], "Gegenprobe: die alte augen_tsx.js (vor TS-D1) sah dieses Modal NICHT")
        if kn:
            # genau der Beweis, den _tsx_blow_dialog_weg für den Text-Weg baut: Kasten-Bindung + strenge Tabu-Liste
            pr = {"rect": kn["rect"], "text": "OK", "aria": "", "tabu": ob.TSX_UEBER_PRUEF_TABU, "wort": "ok", "dialog": pp[0]["rect"], "kasten": True}
            v = c.ziel(kn["rect"], pr)
            check(v.get("hover") and v.get("passt") and v.get("dialog"), f"Ziel-Beweis am OK-Punkt mit Kasten-Bindung passt ({v.get('was')})")
            rk = [b for b in pp[0]["knoepfe"] if b.get("text") == "RESET ACCOUNT"]
            v2 = c.ziel(rk[0]["rect"], pr) if rk else {}
            check(rk and not v2.get("passt"), "Gegenprobe Ziel-Beweis: auf RESET ACCOUNT passt der OK-Beweis NICHT")
            v3 = c.ziel(kn["rect"], dict(pr, dialog=[0, 0, 300, 50]))
            check(not v3.get("passt") and not v3.get("dialog"), "Gegenprobe Kasten-Bindung: anderes Kasten-Rechteck → passt NICHT")
        c.laden(F["banner"])
        check((c.stand(NEU_AUGEN).get("popups") or []) == [], "Banner im Panel (kein fixiertes Overlay) → kein Popup, nichts zum Drücken")
        c.laden(F["mit_rolle"])
        pp = c.stand(NEU_AUGEN).get("popups") or []
        check(len(pp) == 1 and pp[0].get("quelle") != "text" and ob.tsx_blow_dialog(pp), "Modal MIT role=dialog: genau ein Popup (ARIA), nicht doppelt")
        c.laden(F["nur_x"])
        pp = c.stand(NEU_AUGEN).get("popups") or []
        kn = ob.tsx_blow_dialog_knopf(ob.tsx_blow_dialog(pp)["popup"]) if ob.tsx_blow_dialog(pp) else None
        check(kn is not None and kn.get("icon_x"), f"nur Symbol-X + RESET → das X ({kn and kn.get('name')})")
        c.laden(F["ohne_meldung"])
        n_neu = ohne(c.stand(NEU_AUGEN))
        n_alt = ohne(c.stand(ALT_AUGEN)) if ALT_AUGEN else n_neu
        check(n_neu == n_alt and n_neu.get("popups") == [], "ohne Meldung: Stand der neuen augen_tsx.js gleich dem alten (bitgleich)")
    finally:
        c.zu()

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER: {FEHLER}")
sys.exit(1 if FEHLER else 0)
